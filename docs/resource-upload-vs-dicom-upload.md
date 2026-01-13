# Resource Upload vs DICOM Upload

This guide explains the differences between the two upload methods available in xnatio and when to use each.

## Overview

xnatio provides two distinct upload mechanisms:

| Method | CLI Command | Purpose |
|--------|-------------|---------|
| **DICOM Upload** | `upload-dicom` | Import DICOM sessions via REST (parallel) or DICOM C-STORE |
| **Resource Upload** | `upload-resource` | Upload files/directories to session resources |

## Key Differences

| Aspect | **DICOM Upload** | **Resource Upload** |
|--------|------------------|---------------------|
| **API Endpoint** | `/data/services/import` (REST) or DICOM C-STORE | `/resources/{label}/files/{name}` |
| **HTTP Method** | `POST` (REST) or DICOM association | `PUT` (raw binary with `?inbody=true`) |
| **Purpose** | Import DICOM sessions with metadata parsing | Store arbitrary files in session resources |
| **Processing** | XNAT parses DICOM headers, creates scans, extracts metadata | No parsing; files stored as-is |
| **Scope** | Creates/updates entire session structure | Single resource catalog within a session |
| **Extraction** | Built-in DICOM processing | `?extract=true` for ZIP extraction |
| **Overwrite Behavior** | Configurable: `none`, `append`, `delete` | Always overwrites existing files |

## When to Use DICOM Upload

Use `upload-dicom` when:

- Uploading raw DICOM files from a scanner or PACS
- You want XNAT to automatically parse DICOM headers
- You need XNAT to create the session/scan structure based on DICOM metadata
- Files are in standard DICOM format (.dcm, or valid DICOM without extension)

### DICOM Upload Command

```bash
# Upload from ZIP archive
xio upload-dicom PROJECT SUBJECT SESSION /path/to/dicoms.zip --env prod -v

# Upload from directory (parallel REST import, multiple archives)
xio upload-dicom PROJECT SUBJECT SESSION /path/to/dicom_folder --env prod -v

# Upload from TAR archive
xio upload-dicom PROJECT SUBJECT SESSION /path/to/dicoms.tar.gz --env prod -v

# Upload via DICOM C-STORE transport
xio upload-dicom PROJECT SUBJECT SESSION /path/to/dicom_folder \
  --transport dicom-store \
  --dicom-host 192.168.1.10 --dicom-port 8104 \
  --dicom-called-aet XNAT --dicom-calling-aet XNATIO --env prod -v
```

### DICOM Upload Options

REST (default) options:
- `--batches`, `--upload-workers`, `--archive-workers`
- `--archive-format` (`tar` or `zip`)
- `--direct-archive` / `--no-direct-archive`
- `--overwrite` and `--ignore-unparsable`

DICOM C-STORE options:
- `--transport dicom-store`
- `--dicom-host`, `--dicom-port`, `--dicom-called-aet`, `--dicom-calling-aet`
- `--dicom-batches`

## When to Use Resource Upload

Use `upload-resource` when:

- Uploading non-DICOM files (BIDS, NIfTI, analysis results, etc.)
- Adding supplementary data to an existing session
- You want files stored without DICOM parsing
- Uploading derived data or processed outputs

### Resource Upload Command

```bash
# Upload a single file
xio upload-resource PROJECT SUBJECT SESSION RESOURCE_LABEL /path/to/file.nii.gz --env prod -v

# Upload a directory (zipped and extracted server-side)
xio upload-resource PROJECT SUBJECT SESSION BIDS /path/to/bids_folder --env prod -v

# Upload with custom ZIP name
xio upload-resource PROJECT SUBJECT SESSION BIDS /path/to/folder --zip-name custom.zip --env prod -v
```

### Resource Upload Behavior

| Input Type | Behavior |
|------------|----------|
| **File** | Uploaded directly with original filename |
| **Directory** | Zipped locally, uploaded, extracted server-side with `?extract=true` |

## Decision Tree

```
Do you have DICOM files from a scanner?
├── Yes → Use upload-dicom
│         (XNAT will parse headers and create scan structure)
│
└── No → What type of data?
         ├── BIDS, NIfTI, or analysis outputs → Use upload-resource
         ├── Processed DICOM (already in XNAT) → Use upload-resource
         └── Non-imaging data (spreadsheets, docs) → Use upload-resource
```

## Examples

### Scenario 1: New MRI Session from Scanner

```bash
# MRI tech exports DICOM from scanner to ZIP
xio upload-dicom MYPROJECT MYPROJECT_00000001 MYPROJECT_00000001_01_SE01_MR \
  /scanner/export/session_001.zip --env prod -v
```

XNAT will:
1. Parse all DICOM files
2. Extract patient/study/series metadata
3. Create scans with proper series descriptions
4. Link files to appropriate scan resources

### Scenario 2: Adding BIDS Derivatives

```bash
# Upload FreeSurfer outputs to an existing session
xio upload-resource MYPROJECT MYPROJECT_00000001 MYPROJECT_00000001_01_SE01_MR \
  FREESURFER /derivatives/sub-001/ --env prod -v
```

Files will be stored in the `FREESURFER` resource catalog, preserving directory structure.

### Scenario 3: Adding Analysis Results

```bash
# Upload a single analysis report
xio upload-resource MYPROJECT MYPROJECT_00000001 MYPROJECT_00000001_01_SE01_MR \
  ANALYSIS /results/qc_report.pdf --env prod -v
```

## Programmatic Usage

### DICOM Upload

```python
from xnatio import XNATClient, load_config
from pathlib import Path

config = load_config()
client = XNATClient.from_config(config)

client.upload_dicom_zip(
    archive=Path("/path/to/dicoms.zip"),
    project="MYPROJECT",
    subject="MYPROJECT_00000001",
    session="MYPROJECT_00000001_01_SE01_MR",
    overwrite="append",  # Merge with existing data
    trigger_pipelines=True,
)
```

### Resource Upload

```python
from xnatio import XNATClient, load_config
from pathlib import Path

config = load_config()
client = XNATClient.from_config(config)

# Upload a file
client.upload_session_resource_file(
    project="MYPROJECT",
    subject="MYPROJECT_00000001",
    session="MYPROJECT_00000001_01_SE01_MR",
    resource_label="ANALYSIS",
    file_path=Path("/results/report.pdf"),
)

# Upload a directory
client.upload_session_resource_zip_dir(
    project="MYPROJECT",
    subject="MYPROJECT_00000001",
    session="MYPROJECT_00000001_01_SE01_MR",
    resource_label="BIDS",
    local_dir=Path("/bids/sub-001/"),
)
```

## Common Mistakes

### Mistake 1: Using Resource Upload for Raw DICOM

**Problem:** Uploading raw DICOM via `upload-resource` bypasses XNAT's DICOM parsing.

**Result:** Files are stored but XNAT doesn't create proper scan structure or extract metadata.

**Solution:** Use `upload-dicom` for raw DICOM files.

### Mistake 2: Using DICOM Upload for Non-DICOM Files

**Problem:** Using `upload-dicom` for BIDS/NIfTI data.

**Result:** XNAT's DICOM parser will reject or ignore non-DICOM files (with `ignore_unparsable=True`).

**Solution:** Use `upload-resource` for non-DICOM data.

### Mistake 3: Forgetting Resource Labels

**Problem:** Not specifying a meaningful resource label.

**Result:** Data is harder to organize and find.

**Solution:** Use descriptive labels: `BIDS`, `FREESURFER`, `ANALYSIS`, `QC`, etc.

## See Also

- [XNAT REST API Documentation](https://wiki.xnat.org/display/XAPI)
- [rename-subjects-pattern.md](./rename-subjects-pattern.md) - Pattern-based subject renaming
- [refresh-catalogs.md](./refresh-catalogs.md) - Catalog refresh operations
- [add-user-to-groups.md](./add-user-to-groups.md) - User group management
