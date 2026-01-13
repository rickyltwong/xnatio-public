# XNATIO Onboarding Guide (Internal Admins)

This guide gets new team members productive with XNATIO for daily XNAT admin tasks.

## 1) Install and Run

```bash
git clone https://github.com/rickyltwong/xnatio.git
cd xnatio

# Option 1: uv (recommended)
uv sync
uv run xnatio --help

# Option 2: pip
python -m venv .venv
source .venv/bin/activate
pip install -e .
xnatio --help
```

## 2) Configure Credentials

Create `.env` at the repo root:

```
XNAT_SERVER=https://your-xnat.example.org
XNAT_USERNAME=your_user
XNAT_PASSWORD=your_password
XNAT_VERIFY_TLS=true

# Optional for DICOM C-STORE transport
XNAT_DICOM_HOST=your-xnat.example.org
XNAT_DICOM_PORT=8104
XNAT_DICOM_CALLED_AET=XNAT
XNAT_DICOM_CALLING_AET=XNATIO
```

## 3) Common Daily Workflows

```bash
# Upload a directory via parallel REST import (default)
xio upload-dicom PROJECT SUBJECT SESSION /path/to/dicom_dir --env dev -v

# Upload via DICOM C-STORE
xio upload-dicom PROJECT SUBJECT SESSION /path/to/dicom_dir \
  --transport dicom-store \
  --dicom-host 192.168.1.10 --dicom-port 8104 \
  --dicom-called-aet XNAT --dicom-calling-aet XNATIO --env dev -v

# Upload session resources (BIDS, derivatives)
xio upload-resource PROJECT SUBJECT SESSION BIDS /path/to/bids_dir --env dev -v

# Download a session and extract zips
xio download-session PROJECT SUBJECT SESSION ./out --unzip --env dev -v

# Refresh catalogs for a project (safe to test with --limit)
xio refresh-catalogs PROJECT --option append --option checksum --limit 10 --env dev -v

# Rename subjects using a pattern (dry-run first)
xio rename-subjects-pattern PROJECT --match "^(OXD\\d{3})$" --to "{project}_00{1}" \
  --dry-run --env dev -v

# Add a user to groups
xio add-user-to-groups username --projects "PRJ01,PRJ02" --role member --env dev -v

# Apply label fixes (dry-run then execute)
xio apply-label-fixes config/patterns.json --env dev -v
xio apply-label-fixes config/patterns.json --execute --env dev -v
```

## 4) Safety Tips

- Use `--dry-run` where available before making changes.
- `delete-scans` requires explicit confirmation unless `--confirm` is provided.
- Run against a non-production XNAT first when testing new workflows.

## 5) Read Next

- `docs/resource-upload-vs-dicom-upload.md`
- `docs/rename-subjects-pattern.md`
- `docs/apply-label-fixes.md`
- `docs/dicom-store-upload.md`
- `docs/commands.md`
