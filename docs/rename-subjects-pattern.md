# rename-subjects-pattern

Pattern-based subject renaming with merge support for XNAT projects.

## Overview

The `rename-subjects-pattern` command allows you to rename multiple subjects in a project using regex pattern matching. Unlike the basic `rename-subjects` command (which requires a JSON mapping), this command automatically finds subjects matching a pattern and renames them using a template.

**Key feature:** When the target subject already exists (e.g., duplicate entries created by different labs), the command will **merge** by moving all experiments from the source subject to the target, then deleting the empty source.

## Naming Convention

This tool helps enforce a consistent naming convention:

| Component | Format | Example |
|-----------|--------|---------|
| **Project ID** | `CODE_SITE` | 3-letter code + 2-digit study + 3-letter site |
| **Subject ID** | `PROJECT_XXXXXXXX` | Project ID + underscore + 4-8 char subject code |

Common issues this tool fixes:
- Users entering just the subject code (e.g., `SUBJ022` instead of `PROJECT_SITE_00SUBJ022`)
- Different labs creating separate subjects for the same participant
- Typos or inconsistent formatting

## Usage

```bash
xio rename-subjects-pattern PROJECT --match "PATTERN" --to "TEMPLATE" [--dry-run] [--env ENV] [-v]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `PROJECT` | XNAT project ID (e.g., `MYPROJECT`) |
| `--match` | Regex pattern to match subject labels. Use capture groups `()` for parts you want to reuse. |
| `--to` | Template for the new label. Use `{project}` for the project ID, `{1}`, `{2}` for capture groups. |
| `--dry-run` | Preview changes without making them |
| `--env` | Environment name (dev/test/prod) or path to .env file |
| `-v` | Verbose logging |

## Template Syntax

The `--to` template supports these placeholders:

| Placeholder | Replaced With |
|-------------|---------------|
| `{project}` | The project ID argument (e.g., `MYPROJECT`) |
| `{1}` | First capture group from regex |
| `{2}` | Second capture group from regex |
| ... | Additional capture groups |

### Examples

| Pattern | Template | Project | Input | Output |
|---------|----------|---------|-------|--------|
| `^(SUBJ\d{3})$` | `{project}_00{1}` | `STUDY_SITE` | `SUBJ022` | `STUDY_SITE_00SUBJ022` |
| `^STUDY-(\d{3})$` | `{project}_STUDY{1}` | `PRJ01_SITE` | `STUDY-123` | `PRJ01_SITE_STUDY123` |
| `^(\d{8})$` | `{project}_{1}` | `DEMO_SITE` | `00000001` | `DEMO_SITE_00000001` |

## Experiment Label Convention

> MRI/PET operators must enter the **Experiment Label as the Patient Name** in the DICOM header. Typos here will misroute data across the platform.

An experiment label is the subject ID plus visit, session, and modality codes:

```
<PROJECT_ID>_<SUBJECT_CODE>_<VISIT_CODE>_<SESSION_CODE>_<MODALITY_CODE>
```

Example: `DEMO_SITE_00000001_02_SE03_MR`

| Component | Format | Example | Notes |
|-----------|--------|---------|-------|
| Project ID | `CODE_SITE` | `DEMO_SITE` | Project code + site identifier |
| Subject Code | `00000001` | `00000001` | 4–8 alphanumeric; avoid PHI and location/visit info |
| Visit Code | `\d{2}` | `02` | Increment per visit (01 baseline, 02 follow-up, etc.) |
| Session Code | `SE\d{2}` | `SE03` | Increment per continuous acquisition block within a visit |
| Modality Code | `A–Z{2,4}` | `MR` | Choose from approved modality list below |

Guidelines:
- Keep subject codes unique per project and consistent across modalities/sites.
- Visits are trips to the site; sessions are consecutive acquisitions within a visit.
- Use only approved modality codes; keep them consistent per acquisition.

### Supported Modality Codes

| Modality | Code | Modality | Code |
|----------|------|----------|------|
| Magnetic Resonance | MR | Positron Emission Tomography | PET |
| Computed Tomography | CT | Ultrasound | US |
| Electroencephalography | EEG | Magnetoencephalography | MEG |
| Computed Radiography | CR | Digital Radiography | DX |
| 3D Digital Radiography | DX3D | Digital Mammography | MG |
| Nuclear Medicine | NM | Ophthalmic Photography | OP |
| Ophthalmic Tomography | OPT | Hemodynamic | HD |
| Radiofluoroscopy | RF | Radiotherapy | RT |
| X-ray Angiography | XA | X-ray 3D Angiography | XA3D |
| Visible Light Photography | XC | Video Photography | XCV |
| Visible Light Endoscopy | ES | Video Endoscopy | ESV |
| Visible Light Microscopy | GM | Video Microscopy | GMV |
| Electrocardiography | ECG | Electrophysiology | EPS |
| Visible Light Slide-Coordinates Microscopy | SM | — | — |

## Regex Pattern Syntax

The `--match` pattern uses Python regex syntax. Common patterns:

| Pattern | Matches | Capture Groups |
|---------|---------|----------------|
| `^(SUBJ\d{3})$` | `SUBJ001`, `SUBJ022`, `SUBJ999` | `{1}` = full match (e.g., `SUBJ022`) |
| `^STUDY-(\d{3})$` | `STUDY-001`, `STUDY-123` | `{1}` = the number (e.g., `001`) |
| `^(\d{8})$` | `00000001`, `12345678` | `{1}` = 8-digit code |
| `^([A-Z]+)-(\d+)$` | `ABC-123`, `XY-1` | `{1}` = letters, `{2}` = numbers |

**Important:** The pattern must match the **entire** subject label (uses `fullmatch`).

## Real-World Examples

### Example: Short Code to Full Format

Users often create subjects with short codes but the correct format includes the project prefix:

```bash
# Preview changes first (always do this!)
xio rename-subjects-pattern STUDY_SITE \
  --match "^(SUBJ\d{3})$" \
  --to "{project}_00{1}" \
  --dry-run \
  --env prod -v

# Execute the rename
xio rename-subjects-pattern STUDY_SITE \
  --match "^(SUBJ\d{3})$" \
  --to "{project}_00{1}" \
  --env prod -v
```

### Example: Remove Hyphens

Users create subjects with hyphens but the correct format has no hyphen:

```bash
# Preview
xio rename-subjects-pattern PRJ01_SITE \
  --match "^STUDY-(\d{3})$" \
  --to "{project}_STUDY{1}" \
  --dry-run \
  --env prod -v

# Execute
xio rename-subjects-pattern PRJ01_SITE \
  --match "^STUDY-(\d{3})$" \
  --to "{project}_STUDY{1}" \
  --env prod -v
```

### Example: Just Subject Code Entered

When users enter only the subject code without the project prefix:

```bash
# Subjects like "00000001" should become "DEMO_SITE_00000001"
xio rename-subjects-pattern DEMO_SITE \
  --match "^(\d{8})$" \
  --to "{project}_{1}" \
  --dry-run \
  --env prod -v
```

## Merge Behavior

When both the source subject and target subject exist (common when different labs create their own entries for the same participant):

**Before:**
```
SUBJ022              ← has PET experiments (created by PET centre)
STUDY_SITE_00SUBJ022 ← has MR experiments (created by MR unit)
```

**What happens:**
1. Pattern matches `SUBJ022`
2. Target `STUDY_SITE_00SUBJ022` already exists
3. All experiments from `SUBJ022` are moved to `STUDY_SITE_00SUBJ022`
4. Empty `SUBJ022` subject is deleted

**After:**
```
STUDY_SITE_00SUBJ022 ← has both PET and MR experiments
```

## Output

The command reports three categories:

- **Renamed**: Subjects that were simply renamed (target didn't exist)
- **Merged**: Subjects whose experiments were moved to an existing target
- **Skipped**: Subjects that couldn't be processed (with reason)

Example output:
```
Renamed subjects:
  SUBJ021 -> STUDY_SITE_00SUBJ021
  SUBJ023 -> STUDY_SITE_00SUBJ023

Merged subjects (experiments moved to existing target):
  SUBJ022 -> STUDY_SITE_00SUBJ022

Skipped subjects:
  STUDY_SITE_00SUBJ024: already matches target format

Summary: 2 renamed, 1 merged, 1 skipped
```

## Best Practices

1. **Always use `--dry-run` first** to preview changes
2. **Use `-v` (verbose)** to see detailed logging
3. **Use `{project}` in templates** to avoid hardcoding project IDs
4. **Anchor patterns with `^` and `$`** to match exact labels (e.g., `^SUBJ\d{3}$` not just `SUBJ\d{3}`)
5. **Test on a small project** before running on production data

## Common Regex Patterns

| Use Case | Pattern |
|----------|---------|
| 3-digit number | `\d{3}` |
| 8-digit subject code | `\d{8}` |
| Any digits | `\d+` |
| Uppercase letters | `[A-Z]+` |
| Alphanumeric (4-8 chars) | `[A-Za-z0-9]{4,8}` |
| Optional hyphen | `-?` |
| Literal dot | `\.` |
