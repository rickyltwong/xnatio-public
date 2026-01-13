# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

xnatio is a Python CLI tool for interacting with XNAT neuroimaging data servers, focused on admin tasks like DICOM upload, session management, and catalog maintenance. Inspired by niptools.

**Key directories:**
- `xnatio/` - Core package with services, commands, and uploaders
- `docs/` - Feature documentation (API reference, command guides, upload strategies)
- `tests/` - Unit tests for core modules
- `scripts/` - Project-specific admin utilities (not part of the package)

## Development Commands

```bash
# Install for development (recommended)
uv sync
uv run xnatio --help

# Or with pip
pip install -e .
xnatio --help

# Run specific CLI command
uv run xnatio upload-dicom PROJECT SUBJECT SESSION /path/to/archive.zip --env test -v
uv run xio download-session PROJECT SUBJECT SESSION ./output --env dev -v
```

The CLI has two equivalent entry points: `xnatio` and `xio` (shorter alias).

## Configuration

The tool requires XNAT credentials via environment variables or `.env` files:
- `XNAT_SERVER`, `XNAT_USERNAME`, `XNAT_PASSWORD` (required)
- `XNAT_VERIFY_TLS` (optional, default true)

Use `--env dev|test|prod` to load `.env.dev`, `.env.test`, or `.env.prod` instead of `.env`.

## Architecture

```
xnatio/
├── __init__.py         # Package exports (services, exceptions, validation)
├── cli.py              # CLI entry point and command registration
├── client.py           # XNATClient facade (backward-compatible unified API)
├── config.py           # load_config() for .env-based configuration
├── label_fixes.py      # Label fixes for subjects and experiments
├── core/               # Foundation modules
│   ├── __init__.py     # Unified core exports
│   ├── exceptions.py   # Custom exception hierarchy (20+ types)
│   ├── logging.py      # Structured logging with correlation IDs
│   ├── validation.py   # Input validation for all user data
│   └── utils.py        # Archive detection and temp zip helpers
├── services/           # Modular service classes
│   ├── __init__.py     # Service exports
│   ├── base.py         # XNATConnection (HTTP, auth, pyxnat wrapper)
│   ├── admin.py        # AdminService (catalogs, user groups, renaming)
│   ├── downloads.py    # DownloadService (session/scan downloads)
│   ├── projects.py     # ProjectService (projects, subjects, sessions)
│   ├── scans.py        # ScanService (scan CRUD operations)
│   └── uploads.py      # UploadService (DICOM, resources)
├── commands/           # CLI command parsers and handlers
│   ├── admin.py        # Admin commands (create-project, rename, etc.)
│   ├── download.py     # Download commands
│   ├── maintenance.py  # Maintenance commands (refresh-catalogs, etc.)
│   └── upload.py       # Upload commands
└── uploaders/          # DICOM upload transports
    ├── parallel_rest.py # Parallel REST import (direct-archive)
    └── dicom_store.py   # DICOM C-STORE sender
```

### Service Architecture (Preferred)

New code should use **modular services** directly:

```python
from xnatio.services import XNATConnection, ProjectService, ScanService
from xnatio import load_config

cfg = load_config()
conn = XNATConnection.from_config(cfg)
projects = ProjectService(conn)
scans = ScanService(conn)
```

| Service | Responsibility |
|---------|----------------|
| `XNATConnection` | HTTP client, authentication, pyxnat wrapper |
| `ProjectService` | Projects, subjects, sessions, experiments |
| `ScanService` | Scan CRUD, listing, deletion |
| `UploadService` | DICOM and resource uploads |
| `DownloadService` | Session and scan downloads |
| `AdminService` | Catalog refresh, user groups, subject renaming |

### XNATClient Facade (Backward Compatible)

For simpler usage or legacy code, `XNATClient` provides a unified facade:

```python
from xnatio import XNATClient, load_config

cfg = load_config()
client = XNATClient.from_config(cfg)
client.create_project("MYPROJECT")
```

**CLI** (cli.py) builds argparse commands that:
1. Load config via `load_config(env_file)`
2. Create `XNATConnection.from_config(cfg)`
3. Instantiate appropriate service(s)
4. Call service methods

## CLI Commands

| Command | Description |
|---------|-------------|
| `upload-dicom` | Upload DICOM via parallel REST import (default) or DICOM C-STORE |
| `download-session` | Download scans and resources with optional unzip |
| `extract-session` | Extract downloaded ZIPs into structured folders (local only) |
| `upload-resource` | Upload file/directory to session resource |
| `create-project` | Create new XNAT project |
| `delete-scans` | Delete specific or all scans (supports parallel deletion) |
| `list-scans` | List scan IDs for a session |
| `rename-subjects` | Batch rename subjects via JSON mapping |
| `rename-subjects-pattern` | Pattern-based rename with merge support for duplicates |
| `refresh-catalogs` | Refresh catalog XMLs for project experiments |
| `add-user-to-groups` | Add a user to XNAT project groups (supports `--projects` and `--role`) |
| `apply-label-fixes` | Apply subject and experiment label fixes from JSON config |

## Coding Style

- Python 3.8+; 4-space indentation with type hints
- Module/function names: `snake_case`; CLI commands: `hyphen-case` (e.g., `upload-dicom`)
- Imports grouped: stdlib, third-party, local
- Use `ruff check xnatio` and `ruff format xnatio` for linting/formatting
- `pre-commit install` to enable local hooks

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_validation.py -v
```

- Use `--dry-run` where available before destructive operations
- Test against non-production XNAT servers

## Commit Guidelines

- Short, descriptive messages with optional scope prefix (e.g., `feat(core):`, `fix(upload):`)
- Do not commit `.env` files or credentials
- Document new configuration in README.md or docs/

## Security & DICOM Configuration

Required environment variables:
- `XNAT_SERVER`, `XNAT_USERNAME`, `XNAT_PASSWORD`
- `XNAT_VERIFY_TLS` (optional, default true)

DICOM C-STORE options:
- `XNAT_DICOM_HOST`, `XNAT_DICOM_PORT`
- `XNAT_DICOM_CALLED_AET`, `XNAT_DICOM_CALLING_AET`

Use `.env`, `.env.test`, or `.env.dev` with `--env` flag to isolate environments.
