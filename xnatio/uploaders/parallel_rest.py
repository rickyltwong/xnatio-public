from __future__ import annotations

import logging
import os
import shutil
import tarfile
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple
from zipfile import ZIP_DEFLATED, ZipFile

import requests

from .common import collect_dicom_files, split_into_batches
from .constants import (
    DEFAULT_ARCHIVE_FORMAT,
    DEFAULT_ARCHIVE_WORKERS,
    DEFAULT_IMPORT_HANDLER,
    DEFAULT_NUM_BATCHES,
    DEFAULT_OVERWRITE,
    DEFAULT_TIMEOUT,
    DEFAULT_UPLOAD_WORKERS,
)


@dataclass
class UploadProgress:
    """Progress information for upload callbacks."""

    phase: str
    current: int = 0
    total: int = 0
    message: str = ""
    batch_id: int = 0
    success: bool = True
    errors: List[str] = field(default_factory=list)


@dataclass
class UploadResult:
    """Result of a single batch upload."""

    batch_id: int
    success: bool
    duration: float
    file_count: int
    archive_size: int
    error: str = ""


@dataclass
class UploadSummary:
    """Summary of the complete upload operation."""

    success: bool
    total_files: int
    total_size_mb: float
    duration: float
    batches_succeeded: int
    batches_failed: int
    errors: List[str] = field(default_factory=list)


class XNATSession:
    """XNAT session using session-based authentication."""

    def __init__(
        self,
        server: str,
        username: str,
        password: str,
        *,
        verify_tls: bool = True,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.server = server.rstrip("/")
        self.username = username
        self.password = password
        self.verify_tls = verify_tls
        self.timeout = timeout
        self.session: Optional[requests.Session] = None

    def __enter__(self) -> "XNATSession":
        self.open_session()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close_session()

    def open_session(self) -> None:
        url = f"{self.server}/data/JSESSION"
        self.session = requests.Session()
        self.session.verify = self.verify_tls

        response = self.session.post(
            url,
            auth=(self.username, self.password),
            timeout=self.timeout,
        )

        if response.status_code != 200:
            raise ConnectionError(f"Failed to connect to XNAT: {response.status_code}")

        if "<html" in response.text.lower():
            raise ConnectionError("Authentication failed - password may have expired")

    def close_session(self) -> None:
        if not self.session:
            return
        try:
            url = f"{self.server}/data/JSESSION"
            self.session.delete(url, timeout=self.timeout)
        except Exception:
            pass

    def upload_archive(
        self,
        project: str,
        subject: str,
        session_label: str,
        archive_path: Path,
        *,
        import_handler: str = DEFAULT_IMPORT_HANDLER,
        ignore_unparsable: bool = True,
        overwrite: str = DEFAULT_OVERWRITE,
        direct_archive: bool = True,
        overwrite_files: bool = True,
        quarantine: bool = False,
        trigger_pipelines: bool = True,
        rename: bool = False,
    ) -> Tuple[bool, str]:
        if not self.session:
            raise RuntimeError("XNAT session is not open")

        name = archive_path.name.lower()
        if name.endswith((".tar", ".tar.gz", ".tgz")):
            content_type = "application/x-tar"
        else:
            content_type = "application/zip"

        headers = {"Content-Type": content_type}
        upload_url = f"{self.server}/data/services/import"
        params = {
            "import-handler": import_handler,
            "Ignore-Unparsable": "true" if ignore_unparsable else "false",
            "project": project,
            "subject": subject,
            "session": session_label,
            "overwrite": overwrite,
            "overwrite_files": "true" if overwrite_files else "false",
            "quarantine": "true" if quarantine else "false",
            "triggerPipelines": "true" if trigger_pipelines else "false",
            "rename": "true" if rename else "false",
            "Direct-Archive": "true" if direct_archive else "false",
            "inbody": "true",
        }

        try:
            with archive_path.open("rb") as data:
                response = self.session.post(
                    upload_url,
                    params=params,
                    headers=headers,
                    data=data,
                    timeout=self.timeout,
                )

            if response.status_code == 200:
                return True, ""
            return False, f"Status {response.status_code}: {response.text[:200]}"
        except requests.exceptions.Timeout:
            return False, "Upload timed out"
        except Exception as exc:
            return False, str(exc)


def create_tar_archive(files: List[Path], output_path: Path, base_dir: Path) -> int:
    """Create a TAR archive from files and return its size in bytes."""
    with tarfile.open(output_path, "w") as tf:
        for file_path in files:
            arcname = os.path.relpath(file_path, base_dir)
            tf.add(file_path, arcname=arcname)
    return output_path.stat().st_size


def create_zip_archive(files: List[Path], output_path: Path, base_dir: Path) -> int:
    """Create a ZIP archive from files and return its size in bytes."""
    with ZipFile(output_path, "w", compression=ZIP_DEFLATED, allowZip64=True) as zf:
        for file_path in files:
            arcname = os.path.relpath(file_path, base_dir)
            zf.write(file_path, arcname)
    return output_path.stat().st_size


def create_archive(
    files: List[Path],
    output_path: Path,
    base_dir: Path,
    archive_format: str,
) -> int:
    """Create an archive from files."""
    if archive_format == "tar":
        return create_tar_archive(files, output_path, base_dir)
    if archive_format == "zip":
        return create_zip_archive(files, output_path, base_dir)
    raise ValueError(f"Unsupported archive format: {archive_format}")


def upload_batch(
    *,
    server: str,
    username: str,
    password: str,
    verify_tls: bool,
    timeout: int,
    batch_id: int,
    archive_path: Path,
    file_count: int,
    project: str,
    subject: str,
    session: str,
    import_handler: str,
    ignore_unparsable: bool,
    overwrite: str,
    direct_archive: bool,
) -> UploadResult:
    archive_size = archive_path.stat().st_size
    start_time = time.time()

    try:
        with XNATSession(
            server,
            username,
            password,
            verify_tls=verify_tls,
            timeout=timeout,
        ) as conn:
            success, error = conn.upload_archive(
                project,
                subject,
                session,
                archive_path,
                import_handler=import_handler,
                ignore_unparsable=ignore_unparsable,
                overwrite=overwrite,
                direct_archive=direct_archive,
            )

        duration = time.time() - start_time
        return UploadResult(
            batch_id=batch_id,
            success=success,
            duration=duration,
            file_count=file_count,
            archive_size=archive_size,
            error=error,
        )
    except Exception as exc:
        duration = time.time() - start_time
        return UploadResult(
            batch_id=batch_id,
            success=False,
            duration=duration,
            file_count=file_count,
            archive_size=archive_size,
            error=str(exc),
        )


def upload_dicom_parallel_rest(
    *,
    server: str,
    username: str,
    password: str,
    verify_tls: bool,
    source_dir: Path,
    project: str,
    subject: str,
    session: str,
    num_batches: int = DEFAULT_NUM_BATCHES,
    upload_workers: int = DEFAULT_UPLOAD_WORKERS,
    archive_workers: int = DEFAULT_ARCHIVE_WORKERS,
    archive_format: str = DEFAULT_ARCHIVE_FORMAT,
    import_handler: str = DEFAULT_IMPORT_HANDLER,
    ignore_unparsable: bool = True,
    overwrite: str = DEFAULT_OVERWRITE,
    direct_archive: bool = True,
    timeout: int = DEFAULT_TIMEOUT,
    progress_callback: Optional[Callable[[UploadProgress], None]] = None,
    logger: Optional[logging.Logger] = None,
) -> UploadSummary:
    """Upload a DICOM session using parallel archives via the REST import service."""
    log = logger or logging.getLogger(__name__)
    total_start = time.time()
    errors: List[str] = []

    def report(progress: UploadProgress) -> None:
        if progress_callback:
            progress_callback(progress)

    try:
        files = collect_dicom_files(source_dir)
    except Exception as exc:
        return UploadSummary(
            success=False,
            total_files=0,
            total_size_mb=0.0,
            duration=time.time() - total_start,
            batches_succeeded=0,
            batches_failed=0,
            errors=[f"Failed to scan directory: {exc}"],
        )

    if not files:
        return UploadSummary(
            success=False,
            total_files=0,
            total_size_mb=0.0,
            duration=time.time() - total_start,
            batches_succeeded=0,
            batches_failed=0,
            errors=["No DICOM files found"],
        )

    batches = split_into_batches(files, num_batches)
    report(
        UploadProgress(
            phase="archiving",
            message=f"Split {len(files)} files into {len(batches)} batches",
        )
    )

    ext = ".tar" if archive_format == "tar" else ".zip"
    temp_dir = Path(tempfile.mkdtemp(prefix="xnatio_parallel_"))
    archive_paths: List[Path] = []
    total_archive_size = 0

    try:
        for i in range(len(batches)):
            archive_paths.append(temp_dir / f"batch_{i + 1}{ext}")

        report(
            UploadProgress(
                phase="archiving",
                total=len(batches),
                message="Creating archives...",
            )
        )

        archive_workers = max(1, archive_workers)
        create_workers = min(archive_workers, len(batches))
        source_path = source_dir.expanduser().resolve()

        with ThreadPoolExecutor(max_workers=create_workers) as executor:
            archive_futures = {}
            for i, batch in enumerate(batches):
                future = executor.submit(
                    create_archive,
                    batch,
                    archive_paths[i],
                    source_path,
                    archive_format,
                )
                archive_futures[future] = i

            completed = 0
            for future in as_completed(archive_futures):
                completed += 1
                size = future.result()
                total_archive_size += size
                report(
                    UploadProgress(
                        phase="archiving",
                        current=completed,
                        total=len(batches),
                        message=f"Created archive {completed}/{len(batches)}",
                    )
                )

        report(
            UploadProgress(
                phase="uploading",
                total=len(batches),
                message="Starting upload...",
            )
        )

        results: List[UploadResult] = []
        upload_workers = max(1, upload_workers)
        worker_count = min(upload_workers, len(batches))

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {}
            for i, (batch, archive_path) in enumerate(zip(batches, archive_paths)):
                future = executor.submit(
                    upload_batch,
                    server=server,
                    username=username,
                    password=password,
                    verify_tls=verify_tls,
                    timeout=timeout,
                    batch_id=i + 1,
                    archive_path=archive_path,
                    file_count=len(batch),
                    project=project,
                    subject=subject,
                    session=session,
                    import_handler=import_handler,
                    ignore_unparsable=ignore_unparsable,
                    overwrite=overwrite,
                    direct_archive=direct_archive,
                )
                futures[future] = i + 1

            for future in as_completed(futures):
                result = future.result()
                results.append(result)

                if not result.success:
                    errors.append(f"Batch {result.batch_id}: {result.error}")

                succeeded = sum(1 for r in results if r.success)
                report(
                    UploadProgress(
                        phase="uploading",
                        current=len(results),
                        total=len(batches),
                        batch_id=result.batch_id,
                        success=result.success,
                        message=(f"Uploaded {len(results)}/{len(batches)} ({succeeded} succeeded)"),
                    )
                )

        total_duration = time.time() - total_start
        batches_succeeded = sum(1 for r in results if r.success)
        batches_failed = len(results) - batches_succeeded
        success = batches_failed == 0

        report(
            UploadProgress(
                phase="complete" if success else "error",
                current=len(results),
                total=len(batches),
                message=(
                    "Upload complete!"
                    if success
                    else f"Upload completed with {batches_failed} failures"
                ),
                success=success,
                errors=errors,
            )
        )

        if not success:
            log.warning("Upload completed with %s failures", batches_failed)

        return UploadSummary(
            success=success,
            total_files=len(files),
            total_size_mb=total_archive_size / 1024 / 1024,
            duration=total_duration,
            batches_succeeded=batches_succeeded,
            batches_failed=batches_failed,
            errors=errors,
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
