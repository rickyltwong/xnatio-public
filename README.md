# XNAT IO

> **Version 0.2.0**

Production-grade CLI and Python library for interacting with XNAT neuroimaging data servers.

Inspired by niptools 

## Install

### From GitHub (pip, no clone)

```bash
# Latest from main
python -m pip install "xnatio @ git+https://github.com/rickyltwong/xnatio.git@main"

# Or pin to a tag (recommended once you create one)
python -m pip install "xnatio @ git+https://github.com/rickyltwong/xnatio.git@v0.1.0"

# Test the installation
xnatio --help
# or use the shorter alias:
xio --help
```

### From Source (Recommended)

```bash
git clone https://github.com/rickyltwong/xnatio.git
cd xnatio
pip install .

# Test the installation
xnatio --help
# or use the shorter alias:
xio --help
```

### For Development

```bash
git clone https://github.com/rickyltwong/xnatio.git
cd xnatio

# Option 1: Using uv (fast)
uv sync
uv run xnatio --help

# Option 2: Using pip with virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
xnatio --help
```

### Using pipx (Isolated Installation)

```bash
# No clone (install directly from GitHub)
pipx install "xnatio@git+https://github.com/rickyltwong/xnatio.git@main"
# Or pin to a tag (recommended once you create one)
pipx install "xnatio@git+https://github.com/rickyltwong/xnatio.git@v0.1.0"
xnatio --help
```

## New Employee Quickstart

If you are new to XNAT operations, start with:
- `docs/onboarding.md` for setup + daily workflows.
- `docs/resource-upload-vs-dicom-upload.md` for choosing the right upload path.
- `docs/commands.md` for a command-by-domain overview.

## Programmatic Usage

xnatio can be used as a Python library with two styles:

### Modular Services (Recommended)

```python
from xnatio import load_config
from xnatio.services import XNATConnection, ProjectService, UploadService

# Load configuration from .env file
config = load_config()

# Create connection and services
conn = XNATConnection.from_config(config)
projects = ProjectService(conn)
uploads = UploadService(conn)

# Use services
projects.create_project("PROJECT_ID")
uploads.upload_dicom_zip(
    archive_path,
    project="PROJECT_ID",
    subject="SUBJECT_ID",
    session="SESSION_ID"
)
```

### XNATClient Facade (Simpler API)

```python
from xnatio import XNATClient, load_config

# Load configuration from .env file
config = load_config()

# Create unified client
client = XNATClient.from_config(config)

# Use client methods
client.create_project("PROJECT_ID")
client.upload_dicom_zip(
    archive_path,
    project="PROJECT_ID",
    subject="SUBJECT_ID",
    session="SESSION_ID"
)
```

### Error Handling

```python
from xnatio import XNATClient, load_config
from xnatio.core import XNATError, ValidationError, UploadError

try:
    config = load_config()
    client = XNATClient.from_config(config)
    client.upload_dicom_zip(...)
except ValidationError as e:
    print(f"Invalid input: {e}")
except UploadError as e:
    print(f"Upload failed: {e}")
except XNATError as e:
    print(f"XNAT error: {e}")
```

## Configure

Create a `.env` (or `.env.dev`) at the project root with:

```
XNAT_SERVER=https://your-xnat.example.org
XNAT_USERNAME=your_user
XNAT_PASSWORD=your_password
# optional
XNAT_VERIFY_TLS=true
# optional (DICOM C-STORE transport)
XNAT_DICOM_HOST=your-xnat.example.org
XNAT_DICOM_PORT=8104
XNAT_DICOM_CALLED_AET=XNAT
XNAT_DICOM_CALLING_AET=XNATIO
```

- Set `XNAT_VERIFY_TLS=false` for dev servers with self-signed or untrusted certs.
- Use `--env dev` to load `.env.dev` instead of `.env`, `--env test` to load `.env.test`, `--env prod` to load `.env.prod`.

## CLI

### Commands

- **upload-dicom**: Upload a DICOM session via REST (parallel direct-archive by default) or DICOM C-STORE
- **download-session**: Download scans and all session resources; optional assessors and reconstructions; can auto-extract and clean up zips
- **extract-session**: Extract all zips in a session directory into structured folders (local operation, no XNAT connection required)
- **upload-resource**: Upload a local file or directory into a session resource. Directories are zipped locally and extracted server-side
- **create-project**: Create a new project in XNAT (ID, secondary_ID, name set to the provided value)
- **delete-scans**: Delete specific scan files or all scans for a given project, subject, and session (use with caution!)
- **list-scans**: List scan IDs for a session
- **rename-subjects**: Batch rename subjects within a project using a JSON mapping of old:new labels
- **rename-subjects-pattern**: Rename subjects matching a regex pattern, with merge support for duplicates (see [docs](docs/rename-subjects-pattern.md))
- **refresh-catalogs**: Refresh catalog XMLs for experiments in a project with optional checksum/delete/append/populateStats actions (see [docs](docs/refresh-catalogs.md))
- **add-user-to-groups**: Add a user to one or more XNAT project groups with role-based access (see [docs](docs/add-user-to-groups.md))
- **apply-label-fixes**: Apply subject and experiment label fixes from a JSON config file for automated data quality (see [docs](docs/apply-label-fixes.md))

> **Tip**: You can use the shorter alias `xio` instead of `xnatio` for all commands (e.g., `xio --help`, `xio upload-dicom`, etc.)

### Help

```bash
xnatio --help
# or use the shorter alias:
xio --help

xnatio upload-dicom --help
xnatio download-session --help
xnatio extract-session --help
xnatio upload-resource --help
xnatio create-project --help
xnatio delete-scans --help
xnatio list-scans --help
xnatio rename-subjects --help
xnatio rename-subjects-pattern --help
xnatio refresh-catalogs --help
xnatio add-user-to-groups --help
xnatio apply-label-fixes --help
```

### Examples

Upload a DICOM session from an archive (single REST import):

```bash
xnatio upload-dicom DEMO_PRJ DEMO_SUBJ DEMO_SESS \
  /path/to/ARCHIVE.zip --env test -v

# or using the shorter alias:
xio upload-dicom DEMO_PRJ DEMO_SUBJ DEMO_SESS \
  /path/to/ARCHIVE.zip --env test -v
```

Upload a DICOM session from a directory (parallel REST import, multiple archives):

```bash
xio upload-dicom DEMO_PRJ DEMO_SUBJ DEMO_SESS \
  /path/to/dicom_dir --env test -v

# Send via DICOM C-STORE instead of REST
xio upload-dicom DEMO_PRJ DEMO_SUBJ DEMO_SESS \
  /path/to/dicom_dir --transport dicom-store \
  --dicom-host 192.168.1.10 --dicom-port 8104 \
  --dicom-called-aet XNAT --dicom-calling-aet XNATIO --env test -v

See [docs/dicom-store-upload.md](docs/dicom-store-upload.md) for details.
```

Download a session into `outdir/SESSION_LABEL`, include assessors/recons, unzip and remove zips:

```bash
xio download-session DEMO_PRJ DEMO_SUBJ DEMO_SESS outdir \
  --include-assessors --include-recons --unzip --env dev -v
```

Upload a directory as a session resource (zipped and extracted server-side):

```bash
xio upload-resource DEMO_PRJ DEMO_SUBJ DEMO_SESS \
  BIDS /path/to/bids_directory --env test -v
```

Delete scans for a session:

```bash
# Delete all scans (interactive confirmation required)
xio delete-scans DEMO_PRJ DEMO_SUBJ DEMO_SESS \
  --scan "*" --env test -v

# Delete specific scans by ID
xio delete-scans DEMO_PRJ DEMO_SUBJ DEMO_SESS \
  --scan "1,2,3,4,6" --env test -v

# Skip confirmation prompt with --confirm flag
xio delete-scans DEMO_PRJ DEMO_SUBJ DEMO_SESS \
  --scan "*" --confirm --env test -v

# Batch rename subjects from JSON mapping (inline)
xio rename-subjects MYPROJECT '{"SUBJ001": "MYPROJECT_00SUBJ001", "SUBJ002": "MYPROJECT_00SUBJ002"}' --env dev -v

# Or load mapping from a JSON file
xio rename-subjects MYPROJECT mappings.json --env prod -v

# Pattern-based rename: rename all SUBJNNN subjects to MYPROJECT_00SUBJNNN
# Use --dry-run first to preview changes; {project} is replaced with MYPROJECT
xio rename-subjects-pattern MYPROJECT \
  --match "^(SUBJ\d{3})$" \
  --to "{project}_00{1}" \
  --dry-run --env prod -v

# Execute the pattern-based rename (merges duplicates automatically)
xio rename-subjects-pattern MYPROJECT \
  --match "^(SUBJ\d{3})$" \
  --to "{project}_00{1}" \
  --env prod -v

# Refresh catalogs for all experiments in a project (e.g., add new files, compute checksums)
xio refresh-catalogs DEMO_PRJ --option append --option checksum --env test -v

# Refresh catalogs for specific experiments only
xio refresh-catalogs DEMO_PRJ --experiment DEMO_E00001 --experiment DEMO_E00002 --env test -v

# Refresh with limit for testing (first 10 experiments)
xio refresh-catalogs DEMO_PRJ --option populateStats --limit 10 --env test -v

# Add a user to project groups using convenience flags
xio add-user-to-groups username123 \
  --projects "PRJ01,PRJ02,PRJ03" \
  --role member \
  --site SITE1 \
  --env prod -v

# Add a user to specific groups directly
xio add-user-to-groups username123 \
  PRJ01_SITE1_member PRJ02_SITE1_collaborator PRJ03_SITE1_owner \
  --env prod -v
```

## Docker

xnatio is available as a Docker image for scheduled/automated tasks.

### Build

```bash
docker build -t xnatio:latest .
```

### Run

```bash
# Dry-run label fixes
docker run --rm \
  -e XNAT_SERVER=https://xnat.example.org \
  -e XNAT_USERNAME=admin \
  -e XNAT_PASSWORD=secret \
  -v /path/to/config:/config:ro \
  xnatio:latest apply-label-fixes /config/patterns.json -v

# Execute label fixes
docker run --rm \
  -e XNAT_SERVER=... \
  -v /path/to/config:/config:ro \
  xnatio:latest apply-label-fixes /config/patterns.json --execute -v
```

## Requirements

- Python 3.8 or higher
- Access to an XNAT server
- Valid XNAT credentials

## Notes

- Accepted upload formats: `.zip`, `.tar`, `.tar.gz`, `.tgz`. Directories use parallel REST uploads by default.
- Use `--transport dicom-store` for C-STORE uploads (requires DICOM host/port/AET settings).
- Session downloads are parallelized and show byte-progress logs if `-v` is set.
- Environment variables can be exported directly instead of `.env` if preferred.
- Use `--env dev` to load `.env.dev` instead of `.env`, `--env test` to load `.env.test`, `--env prod` to load `.env.prod`.
