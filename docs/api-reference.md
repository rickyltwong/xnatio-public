# API Reference

This document provides a comprehensive reference for using xnatio as a Python library.

## Installation

```bash
pip install "xnatio @ git+https://github.com/rickyltwong/xnatio.git@main"
```

## Quick Start

### Using Services (Recommended)

```python
from xnatio import load_config
from xnatio.services import XNATConnection, ProjectService

# Load configuration from .env file
config = load_config()

# Create connection and services
conn = XNATConnection.from_config(config)
projects = ProjectService(conn)

# Verify connection
version = conn.test_connection()
print(f"Connected to XNAT version: {version}")

# Use services
subjects = projects.list_subjects("MY_PROJECT")
```

### Using XNATClient Facade

```python
from xnatio import XNATClient, load_config

# Load configuration from .env file
config = load_config()

# Create authenticated client (facade for all services)
client = XNATClient.from_config(config)

# Verify connection
version = client.test_connection()
print(f"Connected to XNAT version: {version}")
```

## Architecture Overview

xnatio uses a **service-oriented architecture**:

| Component | Description |
|-----------|-------------|
| `XNATConnection` | Core HTTP client, authentication, pyxnat wrapper |
| `ProjectService` | Projects, subjects, sessions, experiments |
| `ScanService` | Scan CRUD operations |
| `UploadService` | DICOM and resource uploads |
| `DownloadService` | Session and scan downloads |
| `AdminService` | Catalog refresh, user groups, subject renaming |
| `XNATClient` | Backward-compatible facade combining all services |

```python
# Services can be imported from xnatio.services
from xnatio.services import (
    XNATConnection,
    ProjectService,
    ScanService,
    UploadService,
    DownloadService,
    AdminService,
)

# Or use the unified facade
from xnatio import XNATClient
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `XNAT_SERVER` | Yes | - | Base URL of XNAT server (e.g., `https://xnat.example.org`) |
| `XNAT_USERNAME` | Yes | - | XNAT username |
| `XNAT_PASSWORD` | Yes | - | XNAT password |
| `XNAT_VERIFY_TLS` | No | `true` | Whether to verify TLS certificates |

### load_config()

```python
def load_config(env_path: Optional[Path] = None) -> Dict[str, object]:
    """
    Load configuration from environment variables.

    Parameters
    ----------
    env_path : Path | None
        Optional path to .env file. If provided, loads with override=True.
        If None and .env exists in cwd, loads it with override=False.

    Returns
    -------
    dict
        Configuration dict with keys: server, user, password, verify_tls

    Raises
    ------
    FileNotFoundError
        If env_path is provided but file doesn't exist
    RuntimeError
        If required environment variables are missing
    """
```

**Example:**

```python
from pathlib import Path
from xnatio import load_config

# Load from default .env
config = load_config()

# Load from specific file
config = load_config(Path(".env.prod"))
```

## XNATClient

### Constructor

```python
class XNATClient:
    def __init__(
        self,
        server: str,
        username: str,
        password: str,
        *,
        verify_tls: bool = True,
        http_timeouts: Tuple[int, int] = (120, 604800),
        logger: Optional[logging.Logger] = None,
    ):
        """
        Create a new XNAT client.

        Parameters
        ----------
        server : str
            Base URL of the XNAT server
        username : str
            XNAT username
        password : str
            XNAT password
        verify_tls : bool
            Whether to verify TLS certificates (default: True)
        http_timeouts : tuple[int, int]
            (connect_timeout, read_timeout) in seconds
            Default: (120, 604800) - 2 min connect, 7 days read
        logger : logging.Logger | None
            Custom logger; if None, uses module logger
        """
```

### Factory Method

```python
@classmethod
def from_config(cls, cfg: Dict[str, object]) -> "XNATClient":
    """
    Construct client from configuration dict.

    Parameters
    ----------
    cfg : dict
        Dict with keys: server, user, password, verify_tls (optional)

    Returns
    -------
    XNATClient
        Configured client instance
    """
```

---

## Connection Methods

### test_connection()

```python
def test_connection(self) -> str:
    """
    Validate connectivity by fetching XNAT version.

    Returns
    -------
    str
        XNAT version string or message if unavailable

    Raises
    ------
    requests.HTTPError
        If connection fails
    """
```

---

## Project & Container Methods

### create_project()

```python
def create_project(
    self, project_id: str, description: Optional[str] = None
) -> None:
    """
    Create a new project if it doesn't exist.

    Parameters
    ----------
    project_id : str
        Project ID (used for ID, secondary_ID, and name)
    description : str | None
        Optional project description
    """
```

### ensure_subject()

```python
def ensure_subject(
    self, project: str, subject: str, *, auto_create: bool = True
) -> None:
    """
    Ensure a subject exists in the project.

    Parameters
    ----------
    project : str
        Project ID
    subject : str
        Subject label
    auto_create : bool
        If True, create subject if missing (default: True)

    Raises
    ------
    RuntimeError
        If auto_create=False and subject may need creation
    """
```

### ensure_session()

```python
def ensure_session(self, project: str, subject: str, session: str) -> None:
    """
    Ensure a session exists for the subject.

    Creates an MR session (xnat:mrSessionData) if it doesn't exist.
    Best-effort; silently continues on failure.

    Parameters
    ----------
    project : str
        Project ID
    subject : str
        Subject label
    session : str
        Session/experiment label
    """
```

---

## Subject Listing Methods

### list_subjects()

```python
def list_subjects(self, project: str) -> list[Dict[str, str]]:
    """
    List all subjects in a project.

    Parameters
    ----------
    project : str
        Project ID

    Returns
    -------
    list[dict]
        List of dicts with keys: 'ID', 'label'
    """
```

### list_subject_experiments()

```python
def list_subject_experiments(
    self, project: str, subject: str
) -> list[Dict[str, str]]:
    """
    List experiments belonging to a subject.

    Parameters
    ----------
    project : str
        Project ID
    subject : str
        Subject label

    Returns
    -------
    list[dict]
        List of dicts with keys: 'ID', 'label', 'xsiType'
    """
```

### list_subject_experiments_detailed()

```python
def list_subject_experiments_detailed(
    self, project: str, subject: str
) -> list[Dict[str, str]]:
    """
    List experiments with timing metadata.

    Parameters
    ----------
    project : str
        Project ID
    subject : str
        Subject label

    Returns
    -------
    list[dict]
        List of dicts with keys: 'ID', 'label', 'xsiType', 'date',
        'time', 'insert_date', 'insert_time'
    """
```

---

## Scan Operations

### add_scan()

```python
def add_scan(
    self,
    project: str,
    subject: str,
    session: str,
    *,
    xsi_type: str = "xnat:mrScanData",
    scan_type: Optional[str] = None,
    params: Optional[Dict[str, str]] = None,
) -> str:
    """
    Create a scan with auto-generated ID.

    Parameters
    ----------
    project : str
        Project ID
    subject : str
        Subject label
    session : str
        Session label
    xsi_type : str
        XNAT type (default: xnat:mrScanData)
    scan_type : str | None
        Optional scan type (e.g., 'T1', 'T2')
    params : dict | None
        Additional scan attributes

    Returns
    -------
    str
        New scan ID
    """
```

### list_scans()

```python
def list_scans(
    self, project: str, subject: str, session: str
) -> list[str]:
    """
    List scan IDs for a session.

    Parameters
    ----------
    project : str
        Project ID
    subject : str
        Subject label
    session : str
        Session label

    Returns
    -------
    list[str]
        Scan IDs as strings
    """
```

### delete_scans()

```python
def delete_scans(
    self,
    project: str,
    subject: str,
    session: str,
    scan_ids: Optional[list[str]] = None,
    *,
    parallel: bool = False,
    max_workers: int = 2,
) -> list[str]:
    """
    Delete scans from a session.

    Parameters
    ----------
    project : str
        Project ID
    subject : str
        Subject label
    session : str
        Session label
    scan_ids : list[str] | None
        Specific scan IDs to delete, or None for all
    parallel : bool
        Delete scans in parallel (default: False)
    max_workers : int
        Max threads when parallel=True (default: 2)

    Returns
    -------
    list[str]
        IDs of successfully deleted scans
    """
```

### upload_scan_resource()

```python
def upload_scan_resource(
    self,
    *,
    project: str,
    subject: str,
    session: str,
    scan_id: str,
    resource_label: str,
    file_path: Path,
    remote_name: Optional[str] = None,
) -> None:
    """
    Upload a file to a scan resource.

    Parameters
    ----------
    project : str
        Project ID
    subject : str
        Subject label
    session : str
        Session label
    scan_id : str
        Scan ID
    resource_label : str
        Resource label (e.g., 'DICOM', 'NIFTI')
    file_path : Path
        Local file to upload
    remote_name : str | None
        Remote filename; if None, uses local filename

    Raises
    ------
    ValueError
        If file doesn't exist
    """
```

---

## DICOM Upload

### upload_dicom_zip()

```python
def upload_dicom_zip(
    self,
    archive: Path,
    *,
    project: str,
    subject: str,
    session: str,
    import_handler: str = "DICOM-zip",
    ignore_unparsable: bool = True,
    dest: Optional[str] = None,
    overwrite: str = "delete",
    overwrite_files: bool = True,
    quarantine: bool = False,
    trigger_pipelines: bool = True,
    rename: bool = False,
    srcs: Optional[Sequence[str]] = None,
    http_session_listener: Optional[str] = None,
    direct_archive: bool = False,
) -> None:
    """
    Upload a DICOM archive via XNAT import service.

    Parameters
    ----------
    archive : Path
        Path to ZIP/TAR archive
    project : str
        Project ID
    subject : str
        Subject label
    session : str
        Session label
    import_handler : str
        XNAT import handler (default: "DICOM-zip")
    ignore_unparsable : bool
        Discard non-DICOM files (default: True)
    dest : str | None
        Optional destination route
    overwrite : str
        "none" | "append" | "delete" (default: "delete")
    overwrite_files : bool
        Allow file overwrites (default: True)
    quarantine : bool
        Place in quarantine (default: False)
    trigger_pipelines : bool
        Run AutoRun pipeline (default: True)
    rename : bool
        Rename incoming files (default: False)
    srcs : list[str] | None
        Server-side sources (rarely used)
    http_session_listener : str | None
        Tracking identifier (rarely used)
    direct_archive : bool
        Direct-to-archive mode (default: False)

    Raises
    ------
    ValueError
        If overwrite is not 'none', 'append', or 'delete'
    """
```

---

## Resource Upload Methods

### upload_session_resource_file()

```python
def upload_session_resource_file(
    self,
    *,
    project: str,
    subject: str,
    session: str,
    resource_label: str,
    file_path: Path,
    remote_name: Optional[str] = None,
) -> None:
    """
    Upload a single file to a session resource.

    Parameters
    ----------
    project : str
        Project ID
    subject : str
        Subject label
    session : str
        Session label
    resource_label : str
        Resource label (e.g., 'BIDS', 'ANALYSIS')
    file_path : Path
        Local file to upload
    remote_name : str | None
        Remote filename; if None, uses local filename

    Raises
    ------
    ValueError
        If file doesn't exist
    """
```

### upload_session_resource_dir()

```python
def upload_session_resource_dir(
    self,
    *,
    project: str,
    subject: str,
    session: str,
    resource_label: str,
    local_dir: Path,
) -> None:
    """
    Upload a directory, preserving structure.

    Uploads each file individually to the resource.

    Parameters
    ----------
    project : str
        Project ID
    subject : str
        Subject label
    session : str
        Session label
    resource_label : str
        Resource label
    local_dir : Path
        Local directory to upload

    Raises
    ------
    ValueError
        If directory doesn't exist
    """
```

### upload_session_resource_zip_dir()

```python
def upload_session_resource_zip_dir(
    self,
    *,
    project: str,
    subject: str,
    session: str,
    resource_label: str,
    local_dir: Path,
    zip_name: Optional[str] = None,
) -> None:
    """
    Zip a directory and upload with server-side extraction.

    More efficient than upload_session_resource_dir() for
    directories with many files.

    Parameters
    ----------
    project : str
        Project ID
    subject : str
        Subject label
    session : str
        Session label
    resource_label : str
        Resource label
    local_dir : Path
        Local directory to zip and upload
    zip_name : str | None
        ZIP filename; if None, uses '{resource_label}.zip'

    Raises
    ------
    ValueError
        If directory doesn't exist
    """
```

---

## Download Methods

### download_session()

```python
def download_session(
    self,
    project: str,
    subject: str,
    session: str,
    output_dir: Path,
    *,
    include_assessors: bool = False,
    include_recons: bool = False,
    parallel: bool = True,
    max_workers: int = 4,
) -> None:
    """
    Download a complete session.

    Creates output_dir/session/ containing:
    - scans.zip (all scan files)
    - resources_<label>.zip (each session resource)
    - assessor_resources.zip (if include_assessors=True)
    - recon_resources.zip (if include_recons=True)

    Parameters
    ----------
    project : str
        Project ID
    subject : str
        Subject label
    session : str
        Session label
    output_dir : Path
        Output directory
    include_assessors : bool
        Download assessor resources (default: False)
    include_recons : bool
        Download reconstruction resources (default: False)
    parallel : bool
        Download in parallel (default: True)
    max_workers : int
        Max parallel downloads (default: 4)
    """
```

### extract_session_downloads()

```python
def extract_session_downloads(self, session_dir: Path) -> None:
    """
    Extract downloaded ZIPs into structured folders.

    Layout after extraction:
    - scans.zip → scans/
    - resources_<label>.zip → resources/<label>/
    - assessor_resources.zip → assessors/
    - recon_resources.zip → reconstructions/

    Parameters
    ----------
    session_dir : Path
        Directory containing downloaded ZIPs

    Raises
    ------
    ValueError
        If directory doesn't exist
    """
```

---

## Subject/Experiment Management

### rename_subjects()

```python
def rename_subjects(
    self, project: str, mapping: Mapping[str, str]
) -> Dict[str, str]:
    """
    Batch rename subjects using old->new mapping.

    Skips if source doesn't exist or target already exists.

    Parameters
    ----------
    project : str
        Project ID
    mapping : dict[str, str]
        {old_label: new_label} mapping

    Returns
    -------
    dict[str, str]
        {old: new} for successfully renamed subjects
    """
```

### rename_subjects_pattern()

```python
def rename_subjects_pattern(
    self,
    project: str,
    match_pattern: str,
    to_template: str,
    *,
    dry_run: bool = False,
) -> Dict[str, object]:
    """
    Rename subjects matching a regex pattern.

    Supports merging when target subject already exists.

    Parameters
    ----------
    project : str
        Project ID
    match_pattern : str
        Regex pattern to match subject labels
    to_template : str
        Template for new label. Use {project} for project ID,
        {1}, {2}, etc. for capture groups.
    dry_run : bool
        If True, only report what would happen

    Returns
    -------
    dict with keys:
        - renamed: {old: new} for simple renames
        - merged: {old: new} for merged subjects
        - skipped: [(label, reason)] for skipped subjects

    Raises
    ------
    ValueError
        If regex pattern is invalid
    """
```

### move_experiment_to_subject()

```python
def move_experiment_to_subject(
    self, project: str, experiment_id: str, new_subject: str
) -> None:
    """
    Move an experiment to a different subject.

    Parameters
    ----------
    project : str
        Project ID
    experiment_id : str
        Experiment ID (not label)
    new_subject : str
        Target subject label
    """
```

### rename_experiment()

```python
def rename_experiment(
    self, project: str, experiment_id: str, new_label: str
) -> None:
    """
    Rename an experiment label.

    Parameters
    ----------
    project : str
        Project ID
    experiment_id : str
        Experiment ID (not label)
    new_label : str
        New experiment label
    """
```

### delete_subject()

```python
def delete_subject(self, project: str, subject: str) -> None:
    """
    Delete a subject from the project.

    The subject should be empty (no experiments).

    Parameters
    ----------
    project : str
        Project ID
    subject : str
        Subject label
    """
```

---

## Admin Methods

### refresh_project_experiment_catalogs()

```python
def refresh_project_experiment_catalogs(
    self,
    project: str,
    options: Optional[list[str]] = None,
    limit: Optional[int] = None,
    experiment_ids: Optional[Sequence[str]] = None,
) -> list[str]:
    """
    Refresh catalogs for experiments in a project.

    Parameters
    ----------
    project : str
        Project ID
    options : list[str] | None
        Refresh options: checksum, delete, append, populateStats
        If None, all operations are performed.
    limit : int | None
        Max experiments to refresh (for testing)
    experiment_ids : list[str] | None
        Specific experiment IDs/labels to refresh

    Returns
    -------
    list[str]
        Experiment IDs that were refreshed
    """
```

### add_user_to_groups()

```python
def add_user_to_groups(
    self,
    username: str,
    groups: list[str],
) -> dict[str, object]:
    """
    Add a user to XNAT groups.

    Parameters
    ----------
    username : str
        XNAT username
    groups : list[str]
        Group names (e.g., ['PROJECT_SITE_member'])

    Returns
    -------
    dict with keys:
        - added: list of successful groups
        - failed: {group: error} for failures
    """
```

---

## Utility Functions

### is_allowed_archive()

```python
from xnatio.core import is_allowed_archive

def is_allowed_archive(path: Path) -> bool:
    """
    Check if path is a supported archive format.

    Supported: .zip, .tar, .tar.gz, .tgz

    Parameters
    ----------
    path : Path
        File path to check

    Returns
    -------
    bool
        True if supported archive format
    """
```

### zip_dir_to_temp()

```python
from xnatio.core import zip_dir_to_temp

def zip_dir_to_temp(dir_path: Path) -> Path:
    """
    Create a temporary ZIP from a directory.

    Parameters
    ----------
    dir_path : Path
        Directory to zip

    Returns
    -------
    Path
        Path to created ZIP file in temp directory
    """
```

---

## Error Handling

xnatio provides a comprehensive exception hierarchy in `xnatio.core`:

| Exception | Cause |
|-----------|-------|
| `XNATError` | Base class for all xnatio errors |
| `ConfigurationError` | Missing or invalid configuration |
| `ValidationError` | Invalid input parameters |
| `ConnectionError` | Authentication or server connectivity issues |
| `ResourceError` | Resource not found or already exists |
| `UploadError` | Upload failures (DICOM, archive, resource) |
| `DownloadError` | Download failures |
| `OperationError` | Batch operations with partial failures |
| `NetworkError` | Network timeouts or retry exhaustion |

**Example error handling:**

```python
from xnatio import XNATClient, load_config
from xnatio.core import (
    XNATError,
    ValidationError,
    UploadError,
    ConnectionError,
)
from pathlib import Path

config = load_config()
client = XNATClient.from_config(config)

try:
    client.upload_dicom_zip(
        archive=Path("/path/to/archive.zip"),
        project="PROJECT",
        subject="SUBJECT",
        session="SESSION",
    )
except ValidationError as e:
    print(f"Invalid input: {e}")
except UploadError as e:
    print(f"Upload failed: {e}")
except ConnectionError as e:
    print(f"Connection error: {e}")
except XNATError as e:
    print(f"XNAT error: {e}")
```

### Structured Logging

xnatio includes structured logging with correlation IDs:

```python
from xnatio.core import setup_logging, get_logger, LogContext

# Configure logging at startup
setup_logging(level="INFO", json_output=False)

# Get a logger
log = get_logger(__name__)

# Use context managers for operation tracking
with LogContext("upload_session", log, project="PROJ", session="SESS") as ctx:
    log.info("Starting upload")
    ctx.add_detail("files", 100)
    # ... perform operations
```

---

## See Also

- [resource-upload-vs-dicom-upload.md](./resource-upload-vs-dicom-upload.md) - Upload methods comparison
- [rename-subjects-pattern.md](./rename-subjects-pattern.md) - Pattern-based renaming
- [refresh-catalogs.md](./refresh-catalogs.md) - Catalog refresh
- [add-user-to-groups.md](./add-user-to-groups.md) - User management
