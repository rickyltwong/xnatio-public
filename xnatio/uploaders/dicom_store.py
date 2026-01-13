from __future__ import annotations

import logging
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import pydicom
from pydicom.errors import InvalidDicomError
from pynetdicom import AE

from .common import collect_dicom_files, split_into_batches
from .constants import DEFAULT_DICOM_CALLING_AET, DEFAULT_DICOM_STORE_BATCHES

VERIFICATION_UID = "1.2.840.10008.1.1"
try:
    from pynetdicom.sop_class import VerificationSOPClass  # pre-3.1 path
except (ImportError, AttributeError):
    VerificationSOPClass = VERIFICATION_UID  # type: ignore

try:
    from pynetdicom import StoragePresentationContexts  # 2.x/3.0.x
except ImportError:
    from pynetdicom import sop_class as _sc
    from pynetdicom.presentation import build_context

    _uids = [getattr(_sc, name) for name in dir(_sc) if name.endswith("Storage")]
    StoragePresentationContexts = [build_context(uid) for uid in _uids]  # type: ignore


@dataclass
class DICOMStoreSummary:
    total_files: int
    sent: int
    failed: int
    log_dir: Path
    workspace: Path
    success: bool


def ensure_sop_uids(ds) -> None:
    """Populate missing SOP UID attributes from file-meta."""
    if not getattr(ds, "SOPClassUID", None):
        uid = getattr(ds.file_meta, "MediaStorageSOPClassUID", None)
        if uid:
            ds.SOPClassUID = uid
    if not getattr(ds, "SOPInstanceUID", None):
        uid = getattr(ds.file_meta, "MediaStorageSOPInstanceUID", None)
        if uid:
            ds.SOPInstanceUID = uid


def c_echo(host: str, port: int, calling: str, called: str) -> bool:
    """Send a C-ECHO to verify connectivity and AETs."""
    ae = AE(ae_title=calling)
    ae.add_requested_context(VerificationSOPClass)
    assoc = ae.associate(host, port, ae_title=called)
    if not assoc.is_established:
        return False
    status = assoc.send_c_echo()
    assoc.release()
    return bool(status and status.Status == 0x0000)


def send_batch(
    batch_id: str,
    files: List[Path],
    host: str,
    port: int,
    calling: str,
    called: str,
    logdir: Path,
) -> Tuple[int, int]:
    """Send one batch of DICOM files over a single association."""
    sent = failed = 0
    log_path = logdir / f"{batch_id}.log"

    with log_path.open("w") as log:
        ae = AE(ae_title=calling)
        ae.requested_contexts = list(StoragePresentationContexts)  # type: ignore
        ae.add_requested_context("1.3.12.2.1107.5.9.1")

        assoc = ae.associate(host, port, ae_title=called)
        if not assoc.is_established:
            log.write("Association rejected/aborted\n")
            return sent, len(files)

        for fp in files:
            try:
                ds = pydicom.dcmread(fp, force=True)
            except InvalidDicomError:
                failed += 1
                log.write(f"Skip non-DICOM {fp}\n")
                continue

            ensure_sop_uids(ds)

            try:
                status = assoc.send_c_store(ds)
            except (AttributeError, ValueError) as exc:
                failed += 1
                log.write(f"Store error {fp}: {exc}\n")
                continue

            if status and status.Status == 0x0000:
                sent += 1
            else:
                failed += 1
                log.write(f"Failed {fp} status {hex(status.Status if status else 0)}\n")

        assoc.release()

    return sent, failed


def send_dicom_store(
    *,
    dicom_root: Path,
    host: str,
    port: int,
    called_aet: str,
    calling_aet: str = DEFAULT_DICOM_CALLING_AET,
    batches: int = DEFAULT_DICOM_STORE_BATCHES,
    cleanup: bool = False,
    logger: Optional[logging.Logger] = None,
) -> DICOMStoreSummary:
    """Send a directory of DICOM files to an SCP using C-STORE."""
    log = logger or logging.getLogger(__name__)

    if not dicom_root.exists() or not dicom_root.is_dir():
        raise ValueError(f"dicom_root is not a directory: {dicom_root}")

    work = Path(tempfile.mkdtemp(prefix="xnatio_dicom_store_"))
    logs = work / "logs"
    logs.mkdir(parents=True, exist_ok=True)

    try:
        log.info(
            "Pre-flight C-ECHO %s -> %s @ %s:%s",
            calling_aet,
            called_aet,
            host,
            port,
        )
        if not c_echo(host, port, calling_aet, called_aet):
            raise RuntimeError("C-ECHO failed - check host/port/AET settings")

        files = collect_dicom_files(dicom_root)
        if not files:
            raise RuntimeError("No DICOM files found")

        chunks = split_into_batches(files, batches)
        log.info("Discovered %s files under %s", len(files), dicom_root)
        log.info("Using %s batches (requested: %s)", len(chunks), batches)

        sent_total = failed_total = 0
        max_workers = max(1, len(chunks))

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(
                    send_batch,
                    f"{i:03d}",
                    chunk,
                    host,
                    port,
                    calling_aet,
                    called_aet,
                    logs,
                ): i
                for i, chunk in enumerate(chunks)
            }
            for future in as_completed(futures):
                sent, failed = future.result()
                sent_total += sent
                failed_total += failed
                log.info(
                    "Batch %s complete: %s sent, %s failed",
                    f"{futures[future]:03d}",
                    sent,
                    failed,
                )

        return DICOMStoreSummary(
            total_files=len(files),
            sent=sent_total,
            failed=failed_total,
            log_dir=logs,
            workspace=work,
            success=failed_total == 0,
        )
    finally:
        if cleanup:
            shutil.rmtree(work, ignore_errors=True)
