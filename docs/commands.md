# Command Map

This page summarizes the CLI commands by operational domain so new team members
can quickly locate the right tool.

## CLI Entry Points

The CLI has two equivalent entry points:
- `xnatio` - Full name
- `xio` - Short alias

## Upload

- `upload-dicom`: DICOM import via REST (parallel) or DICOM C-STORE.
- `upload-resource`: Upload files or directories into session resources.

Examples:
```bash
xio upload-dicom PRJ SUBJ SESS /path/to/dicom_dir --env dev -v
xio upload-dicom PRJ SUBJ SESS /path/to/dicom_dir --transport dicom-store \
  --dicom-host xnat.example.org --dicom-port 8104 --dicom-called-aet XNAT --env dev -v
xio upload-resource PRJ SUBJ SESS BIDS /path/to/bids_dir --env dev -v
```

## Download

- `download-session`: Download scans/resources for a session.
- `extract-session`: Extract downloaded ZIPs into structured folders.

Examples:
```bash
xio download-session PRJ SUBJ SESS ./out --unzip --env dev -v
xio extract-session ./out/SESS -v
```

## Admin

- `create-project`: Create a project if missing.
- `list-scans`: List scans for a session.
- `delete-scans`: Delete scans (requires confirmation).
- `rename-subjects`: Rename via explicit JSON mapping.
- `rename-subjects-pattern`: Regex-based rename with merge support.
- `add-user-to-groups`: Add a user to project groups.

## Maintenance

- `refresh-catalogs`: Rebuild or append catalog XMLs.
- `apply-label-fixes`: Apply subject/experiment label conventions.

## Safety Checklist

- Always test on non-production first.
- Use `--dry-run` where supported before changes.
- Keep backups of JSON mappings and label fix configs.

## Programmatic Access

All CLI commands use the modular service architecture internally. You can use the same services directly in Python:

```python
from xnatio import load_config
from xnatio.services import XNATConnection, ProjectService, AdminService

config = load_config()
conn = XNATConnection.from_config(config)

# Use services
projects = ProjectService(conn)
admin = AdminService(conn)

# Perform operations
projects.create_project("MY_PROJECT")
admin.refresh_project_experiment_catalogs("MY_PROJECT")
```

See `docs/api-reference.md` for full API documentation.
