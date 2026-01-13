# apply-label-fixes

Automated subject and experiment label corrections for XNAT projects.

## Overview

The `apply-label-fixes` command applies two types of label corrections:

1. **Subject renames** - Pattern-based renaming of subject labels to standard convention
2. **Experiment label fixes** - Automatic assignment of standardized experiment labels

This command is designed for scheduled execution (e.g., daily via cron or a job runner) to ensure data quality across XNAT projects.

## Naming Conventions

### Subject Labels

```
{PROJECT_ID}_{SUBJECT_CODE}
```

Example: `DEMO_SITE_00000001`

### Experiment Labels

```
{SUBJECT_LABEL}_{VISIT:02d}_SE{SESSION:02d}_{MODALITY}
```

Example: `DEMO_SITE_00000001_01_SE01_MR`

| Component | Format | Description |
|-----------|--------|-------------|
| SUBJECT_LABEL | `DEMO_SITE_00000001` | Full subject label |
| VISIT | `01`, `02`, ... | Visit number (by date order) |
| SESSION | `SE01`, `SE02`, ... | Session number within visit (by time order) |
| MODALITY | `MR`, `PET`, `CT`, ... | Imaging modality from XSI type |

## Configuration File

The command uses a JSON configuration file to define subject rename patterns per project.

### Format

```json
{
  "patterns": [
    {
      "project": "MYPROJECT",
      "match": "^(ABC\\d{3})$",
      "to": "{project}_00{1}",
      "description": "ABCNNN -> MYPROJECT_00ABCNNN"
    }
  ]
}
```

### Pattern Fields

| Field | Required | Description |
|-------|----------|-------------|
| `project` | Yes | XNAT project ID |
| `match` | Yes | Regex pattern to match subject labels |
| `to` | Yes | Template for new label. Use `{project}` for project ID, `{1}`, `{2}` for capture groups |
| `description` | No | Human-readable description |

### Example Configuration

See `config/patterns.example.json` for a sample configuration:

```json
{
  "patterns": [
    {
      "project": "DEMO_SITE",
      "match": "^(SUBJ\\d{3})$",
      "to": "{project}_00{1}",
      "description": "SUBJNNN -> DEMO_SITE_00SUBJNNN"
    },
    {
      "project": "STUDY01_SITE",
      "match": "^STUDY-?(\\d{3})$",
      "to": "{project}_STUDY{1}",
      "description": "STUDY-NNN or STUDYNNN -> STUDY01_SITE_STUDYNNN"
    },
    {
      "project": "PROJECT_SITE",
      "match": "^HC(\\d{2})$",
      "to": "{project}_HC0000{1}",
      "description": "HCNN -> PROJECT_SITE_HC0000NN (healthy controls)"
    },
    {
      "project": "PROJECT_SITE",
      "match": "^PT(\\d{2})$",
      "to": "{project}_PT0000{1}",
      "description": "PTNN -> PROJECT_SITE_PT0000NN (patients)"
    }
  ]
}
```

## CLI Usage

```bash
xio apply-label-fixes CONFIG [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `CONFIG` | Path to patterns JSON config file |

### Options

| Option | Description |
|--------|-------------|
| `--project PROJECT` | Limit to specific project (repeatable) |
| `--subject SUBJECT` | Limit experiment fixes to specific subject (repeatable) |
| `--subject-pattern PATTERN` | Regex to filter subjects for experiment fixes |
| `--modality MODALITY` | Modality filter for experiment fixes (default: MR) |
| `--execute` | Apply changes (default: dry-run) |
| `--env ENV` | Environment (dev/test/prod) or path to .env file |
| `-v, --verbose` | Enable verbose logging |

### Examples

```bash
# Dry-run all projects in config
xio apply-label-fixes config/patterns.json --env prod -v

# Execute changes for all projects
xio apply-label-fixes config/patterns.json --execute --env prod -v

# Dry-run specific project
xio apply-label-fixes config/patterns.json --project MYPROJECT --env prod -v

# Dry-run specific subject
xio apply-label-fixes config/patterns.json \
  --project MYPROJECT \
  --subject MYPROJECT_00SUBJ022 \
  --env prod -v

# Include PET sessions (default is MR only)
xio apply-label-fixes config/patterns.json \
  --modality MR --modality PET \
  --execute --env prod -v
```

## Docker Usage

### Build Image

```bash
docker build -t xnatio:latest .
```

### Run Dry-Run

```bash
docker run --rm \
  -e XNAT_SERVER=https://xnat.example.org \
  -e XNAT_USERNAME=admin \
  -e XNAT_PASSWORD=secret \
  -v /path/to/config:/config:ro \
  xnatio:latest apply-label-fixes /config/patterns.json -v
```

### Run Execute

```bash
docker run --rm \
  -e XNAT_SERVER=https://xnat.example.org \
  -e XNAT_USERNAME=admin \
  -e XNAT_PASSWORD=secret \
  -v /path/to/config:/config:ro \
  xnatio:latest apply-label-fixes /config/patterns.json --execute -v
```

### Docker Compose

```bash
# Build
docker-compose build

# Dry-run
docker-compose run --rm xnatio apply-label-fixes /config/patterns.json -v

# Execute
docker-compose run --rm xnatio apply-label-fixes /config/patterns.json --execute -v
```

## Programmatic Usage

```python
from xnatio import XNATClient, load_config
from xnatio.label_fixes import apply_label_fixes
from pathlib import Path

config = load_config()
client = XNATClient.from_config(config)

result = apply_label_fixes(
    client,
    config_path=Path("config/patterns.json"),
    projects=["MYPROJECT"],  # Optional: limit to specific projects
    execute=False,  # Dry-run mode
    verbose=True,
)

# Check results
if result["failed"]:
    print("Some operations failed!")
else:
    print("All operations completed successfully")
```

## How It Works

### Step 1: Subject Renames

For each project in the config:

1. Load patterns for that project
2. For each pattern:
   - Find subjects matching the `match` regex
   - Compute target label using `to` template
   - If target exists: merge experiments and delete source
   - If target doesn't exist: rename subject

### Step 2: Experiment Label Fixes

For each subject with project prefix:

1. List all experiments with detailed metadata
2. Group experiments by date (visit)
3. Within each date, order by time (session)
4. Compute target label: `{SUBJECT}_{VISIT:02d}_SE{SESSION:02d}_{MODALITY}`
5. Rename experiments that don't match target

### Ordering Rules

- **Visits**: Ordered by experiment date (earliest = 01)
- **Sessions**: Ordered by experiment time within same date (earliest = SE01)
- **Tie-breaking**: insert_datetime, then label, then ID

## Output

```
============================================================
Subject rename: DRY-RUN
Project: MYPROJECT
Patterns: 1
============================================================
------------------------------------------------------------
Pattern: ^(SUBJ\d{3})$
To:      {project}_00{1}
         (SUBJNNN -> MYPROJECT_00SUBJNNN)
------------------------------------------------------------
Renamed (2):
  SUBJ021 -> MYPROJECT_00SUBJ021
  SUBJ023 -> MYPROJECT_00SUBJ023

Merged (1):
  SUBJ022 -> MYPROJECT_00SUBJ022

============================================================
Subject summary: 2 renamed, 1 merged, 0 skipped
This was a DRY-RUN. Use --execute to apply changes.
============================================================

============================================================
Experiment label fixes: DRY-RUN
Project: MYPROJECT
Modalities: MR
============================================================
Subject: MYPROJECT_00SUBJ021
Renames (2):
  XNAT_E00001 SUBJ021_MR -> MYPROJECT_00SUBJ021_01_SE01_MR
  XNAT_E00002 SUBJ021_MR_2 -> MYPROJECT_00SUBJ021_02_SE01_MR

============================================================
Experiment summary: 2 planned/renamed, 0 skipped
This was a DRY-RUN. Use --execute to apply changes.
============================================================
```

## Best Practices

1. **Always dry-run first** - Review changes before executing
2. **Schedule during off-hours** - Run when users aren't actively uploading
3. **Monitor logs** - Check task logs for failures
4. **Version control config** - Keep patterns.json in git
5. **Test on dev/test first** - Validate patterns on non-production XNAT

## See Also

- [rename-subjects-pattern.md](./rename-subjects-pattern.md) - Manual subject renaming
- [refresh-catalogs.md](./refresh-catalogs.md) - Catalog maintenance
- [api-reference.md](./api-reference.md) - Full API documentation
