# refresh-catalogs

Refresh catalog XMLs for experiments in an XNAT project.

## Overview

The `refresh-catalogs` command synchronizes XNAT's catalog metadata with the actual files on disk. This is useful when:

- Files have been added to the archive outside of XNAT
- Checksums need to be computed or verified
- Orphaned catalog entries need cleanup
- Resource statistics need updating

## Usage

```bash
xio refresh-catalogs PROJECT [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `PROJECT` | XNAT project ID (e.g., `MYPROJECT`) |

### Options

| Option | Description |
|--------|-------------|
| `--option {checksum,delete,append,populateStats}` | Refresh operation(s) to perform. Can be specified multiple times. |
| `--experiment EXPERIMENT_ID` | Limit refresh to specific experiment IDs or labels. Can be specified multiple times. |
| `--limit N` | Limit number of experiments to refresh (useful for testing) |
| `--env {dev,test,prod}` | Environment name or path to .env file |
| `-v, --verbose` | Enable verbose logging |

## Refresh Options Explained

| Option | Description | When to Use |
|--------|-------------|-------------|
| `checksum` | Compute checksums for files missing them | After bulk uploads or file system restores |
| `delete` | Remove catalog entries for files that no longer exist | After manual file deletion or archive cleanup |
| `append` | Add catalog entries for files that exist but aren't cataloged | After adding files via filesystem (not through XNAT) |
| `populateStats` | Update resource statistics (file count, total size) | After any modification to ensure accurate metadata |

If no `--option` is specified, XNAT performs all operations (equivalent to specifying all four options).

## Examples

### Refresh All Experiments in a Project

```bash
# Perform all refresh operations on all experiments
xio refresh-catalogs MYPROJECT --env prod -v

# Only compute missing checksums
xio refresh-catalogs MYPROJECT --option checksum --env prod -v

# Add new files and update statistics
xio refresh-catalogs MYPROJECT --option append --option populateStats --env prod -v
```

### Refresh Specific Experiments

```bash
# Refresh by experiment ID
xio refresh-catalogs MYPROJECT \
  --experiment XNAT_E00001 \
  --experiment XNAT_E00002 \
  --env prod -v

# Refresh by experiment label
xio refresh-catalogs MYPROJECT \
  --experiment MYPROJECT_00000001_01_SE01_MR \
  --experiment MYPROJECT_00000002_01_SE01_MR \
  --env prod -v
```

### Testing with Limited Scope

```bash
# Refresh only first 10 experiments (useful for testing)
xio refresh-catalogs MYPROJECT --option populateStats --limit 10 --env test -v

# Dry run: check what would be refreshed
xio refresh-catalogs MYPROJECT --limit 5 --env test -v
```

### Common Workflows

#### After Bulk File Upload via Filesystem

When files are added directly to the XNAT archive (not through the web UI or API):

```bash
# 1. Add catalog entries for new files
xio refresh-catalogs MYPROJECT --option append --env prod -v

# 2. Compute checksums for verification
xio refresh-catalogs MYPROJECT --option checksum --env prod -v

# 3. Update resource statistics
xio refresh-catalogs MYPROJECT --option populateStats --env prod -v
```

#### After Archive Cleanup

When files have been manually deleted from the archive:

```bash
# Remove orphaned catalog entries
xio refresh-catalogs MYPROJECT --option delete --env prod -v
```

#### Routine Maintenance

```bash
# Full refresh with all operations
xio refresh-catalogs MYPROJECT --env prod -v
```

## Programmatic Usage

```python
from xnatio import XNATClient, load_config

config = load_config()
client = XNATClient.from_config(config)

# Refresh all experiments with specific options
refreshed = client.refresh_project_experiment_catalogs(
    project="MYPROJECT",
    options=["append", "checksum", "populateStats"],
)
print(f"Refreshed {len(refreshed)} experiments")

# Refresh specific experiments only
refreshed = client.refresh_project_experiment_catalogs(
    project="MYPROJECT",
    experiment_ids=["XNAT_E00001", "MYPROJECT_00000001_01_SE01_MR"],
    options=["checksum"],
)

# Limit for testing
refreshed = client.refresh_project_experiment_catalogs(
    project="MYPROJECT",
    limit=10,
)
```

### Method Signature

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
        Maximum number of experiments to refresh (for testing)
    experiment_ids : Sequence[str] | None
        Specific experiment IDs or labels to refresh.
        If None, all experiments in the project are refreshed.

    Returns
    -------
    list[str]
        List of experiment IDs that were refreshed
    """
```

## Performance Considerations

- **Large Projects:** Refreshing catalogs can be slow for projects with many experiments. Use `--limit` to test first.
- **Checksums:** Computing checksums for large files is CPU-intensive. Consider running during off-peak hours.
- **Specific Experiments:** When possible, target specific experiments with `--experiment` rather than refreshing the entire project.

## Troubleshooting

### No Experiments Found

```
No experiments found to refresh.
```

**Cause:** The project has no experiments, or the specified experiment IDs don't match any experiments.

**Solution:**
- Verify the project ID is correct
- Check experiment IDs/labels with the XNAT web UI
- Ensure you have permission to access the project

### Refresh Seems Stuck

**Cause:** Large projects with many experiments or files can take significant time.

**Solution:**
- Use `--limit` to process in batches
- Use `--experiment` to target specific experiments
- Run with `-v` to see progress

### Permission Denied

**Cause:** Your XNAT user doesn't have sufficient permissions.

**Solution:** Ensure you have at least Member or Owner role on the project.

## See Also

- [resource-upload-vs-dicom-upload.md](./resource-upload-vs-dicom-upload.md) - Upload methods comparison
- [rename-subjects-pattern.md](./rename-subjects-pattern.md) - Pattern-based subject renaming
- [add-user-to-groups.md](./add-user-to-groups.md) - User group management
