from __future__ import annotations

from pathlib import Path
from typing import List, Sequence

DICOM_EXTENSIONS = {".dcm", ".ima", ".img", ".dicom"}


def collect_dicom_files(root: Path, *, include_extensionless: bool = True) -> List[Path]:
    """Recursively collect DICOM-like files under a root directory."""
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Not a directory: {root}")

    files: List[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in DICOM_EXTENSIONS:
            files.append(path)
        elif include_extensionless and suffix == "" and not path.name.startswith("."):
            files.append(path)

    return sorted(files)


def split_into_batches(files: Sequence[Path], num_batches: int) -> List[List[Path]]:
    """Split files into roughly even batches using round-robin assignment."""
    if not files:
        return []

    if num_batches <= 0:
        return [list(files)]

    actual_batches = min(num_batches, len(files))
    batches: List[List[Path]] = [[] for _ in range(actual_batches)]

    for idx, file_path in enumerate(files):
        batches[idx % actual_batches].append(file_path)

    return batches
