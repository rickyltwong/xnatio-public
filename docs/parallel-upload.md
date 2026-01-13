# Parallel Upload Strategies

xnatio supports parallel DICOM uploads to significantly speed up large data transfers. This document explains the available strategies and how to tune them.

## Overview

Large DICOM sessions (thousands of files) can take hours to upload sequentially. xnatio solves this by:

1. **Splitting files into batches** - Files are divided into N independent batches
2. **Parallel archive creation** - Multiple archives are created simultaneously
3. **Concurrent uploads** - Multiple batches upload to XNAT in parallel

This approach can reduce upload times by 10-20x for large sessions.

## Transport Options

### Parallel REST Import (Default)

Uses XNAT's REST import service with parallel archive uploads.

```bash
# Default: 42 batches, 42 upload workers
xio upload-dicom PROJECT SUBJECT SESSION /path/to/dicom_dir

# Custom parallelism
xio upload-dicom PROJECT SUBJECT SESSION /path/to/dicom_dir \
    --num-batches 20 \
    --upload-workers 20 \
    --archive-workers 5

# Use ZIP instead of TAR (slower but more compatible)
xio upload-dicom PROJECT SUBJECT SESSION /path/to/dicom_dir \
    --archive-format zip
```

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--num-batches` | 42 | Number of file batches to create |
| `--upload-workers` | 42 | Concurrent upload threads |
| `--archive-workers` | 5 | Concurrent archive creation threads |
| `--archive-format` | tar | Archive format (tar or zip) |
| `--timeout` | 10800 | HTTP timeout in seconds (3 hours) |

### DICOM C-STORE

Uses DICOM network protocol with parallel associations.

```bash
xio upload-dicom PROJECT SUBJECT SESSION /path/to/dicom_dir \
    --transport dicom-store \
    --dicom-host 192.168.1.10 \
    --dicom-port 8104 \
    --dicom-called-aet XNAT \
    --num-batches 45
```

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--num-batches` | 45 | Number of parallel C-STORE associations |
| `--dicom-calling-aet` | XNATIO | Local AE title |

## Programmatic Usage

### Parallel REST Upload

```python
from xnatio.uploaders import upload_dicom_parallel_rest
from pathlib import Path

def progress_handler(progress):
    print(f"[{progress.phase}] {progress.current}/{progress.total}: {progress.message}")

result = upload_dicom_parallel_rest(
    server="https://xnat.example.com",
    username="admin",
    password="secret",
    verify_tls=True,
    source_dir=Path("/data/dicom/session001"),
    project="MYPROJECT",
    subject="SUBJ001",
    session="SESS001",
    num_batches=20,
    upload_workers=20,
    archive_workers=5,
    archive_format="tar",
    progress_callback=progress_handler,
)

if result.success:
    print(f"Uploaded {result.total_files} files in {result.duration:.1f}s")
    print(f"Throughput: {result.total_size_mb / result.duration:.1f} MB/s")
else:
    print(f"Failed: {result.errors}")
```

### DICOM C-STORE Upload

```python
from xnatio.uploaders import send_dicom_store
from pathlib import Path

result = send_dicom_store(
    source_dir=Path("/data/dicom/session001"),
    host="192.168.1.10",
    port=8104,
    called_aet="XNAT",
    calling_aet="XNATIO",
    num_batches=45,
)

if result.success:
    print(f"Sent {result.total_files} files")
else:
    print(f"Failed: {result.errors}")
```

## Tuning Guidelines

### Optimal Batch Count

The ideal number of batches depends on:

- **File count**: More files = more batches beneficial
- **Network latency**: Higher latency = more parallelism helps
- **Server capacity**: Don't overwhelm the XNAT server

**Rules of thumb:**

| File Count | Recommended Batches |
|------------|---------------------|
| < 1,000 | 5-10 |
| 1,000 - 5,000 | 10-20 |
| 5,000 - 20,000 | 20-40 |
| > 20,000 | 40-50 |

### Archive Workers

Archive creation is CPU-bound. Set `--archive-workers` to your available CPU cores (typically 4-8). More workers than cores provides diminishing returns.

### Upload Workers

Upload workers should match or slightly exceed batch count. Each worker handles one batch upload concurrently.

**Warning:** Setting workers too high can:
- Exhaust server connections
- Trigger rate limiting
- Cause import conflicts

Start with defaults and adjust based on observed performance.

## Performance Comparison

Example session with 15,000 DICOM files (2.5 GB):

| Method | Workers | Duration | Throughput |
|--------|---------|----------|------------|
| Sequential | 1 | 45 min | 0.9 MB/s |
| Parallel REST | 10 | 8 min | 5.2 MB/s |
| Parallel REST | 20 | 4.5 min | 9.3 MB/s |
| Parallel REST | 42 | 3.5 min | 12 MB/s |

*Results vary based on network conditions and server load.*

## Troubleshooting

### "Connection refused" or timeouts

Reduce `--upload-workers` to lower concurrent connections.

### "Import handler busy" errors

The XNAT import service may be overloaded. Reduce batch count or add delays.

### Partial upload failures

Check `result.errors` for failed batches. Re-run the upload - XNAT handles duplicates gracefully with `--overwrite delete`.

### Memory issues with large sessions

For sessions > 50,000 files, consider:
- Using TAR format (streams better than ZIP)
- Reducing archive workers
- Splitting into multiple upload commands

## See Also

- [Resource Upload vs DICOM Upload](resource-upload-vs-dicom-upload.md) - Choosing the right upload method
- [DICOM C-STORE Upload](dicom-store-upload.md) - DICOM network protocol details
- [API Reference](api-reference.md) - Full programmatic API
