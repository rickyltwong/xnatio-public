"""Download service for XNAT resources.

This module handles file downloads:
- Session scans download
- Session resources download
- Assessor and reconstruction downloads
- ZIP extraction
"""

from __future__ import annotations

import logging
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from ..core import (
    # Exceptions
    SessionDownloadError,
    # Logging
    get_audit_logger,
    get_logger,
    LogContext,
    # Validation
    validate_path_exists,
    validate_path_writable,
    validate_project_id,
    validate_session_id,
    validate_subject_id,
    validate_workers,
)
from .base import XNATConnection


class DownloadService:
    """Service for downloading files from XNAT.

    Handles:
    - Session scans download (as ZIP)
    - Session resources download
    - Assessor and reconstruction resources
    - ZIP extraction with organized folder structure
    """

    def __init__(self, connection: XNATConnection) -> None:
        """Initialize download service.

        Args:
            connection: XNAT connection instance.
        """
        self.conn = connection
        self.log = get_logger(__name__)
        self._audit = get_audit_logger()

    # =========================================================================
    # Private Helpers
    # =========================================================================

    def _download_stream(self, url: str, out_path: Path) -> None:
        """Stream a URL to a local file.

        Logs progress at 5MB intervals.

        Args:
            url: XNAT API URL to download.
            out_path: Local output path.
        """
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with self.conn.get(url, stream=True) as resp:
            resp.raise_for_status()

            with open(out_path, "wb") as f:
                total = 0
                report_threshold = 5 * 1024 * 1024  # 5 MB
                next_report = report_threshold

                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    f.write(chunk)
                    total += len(chunk)

                    if total >= next_report:
                        self.log.info("%s: downloaded %s bytes", out_path.name, f"{total:,}")
                        next_report += report_threshold

                self.log.info("%s: download complete (%s bytes)", out_path.name, f"{total:,}")

    # =========================================================================
    # Scan Downloads
    # =========================================================================

    def download_scans_zip(
        self,
        project: str,
        subject: str,
        session: str,
        out_dir: Path,
    ) -> Path:
        """Download all scan files as a single ZIP.

        Args:
            project: Project identifier.
            subject: Subject identifier.
            session: Session identifier.
            out_dir: Output directory.

        Returns:
            Path to downloaded scans.zip file.
        """
        project = validate_project_id(project)
        subject = validate_subject_id(subject)
        session = validate_session_id(session)

        base = f"/data/projects/{project}/subjects/{subject}/experiments/{session}"
        out = out_dir / "scans.zip"

        self._download_stream(f"{base}/scans/ALL/files?format=zip", out)
        return out

    # =========================================================================
    # Resource Downloads
    # =========================================================================

    def download_session_resources_zip(
        self,
        project: str,
        subject: str,
        session: str,
        out_dir: Path,
    ) -> List[Path]:
        """Download all session-level resources as separate ZIPs.

        Args:
            project: Project identifier.
            subject: Subject identifier.
            session: Session identifier.
            out_dir: Output directory.

        Returns:
            List of downloaded resource ZIP paths.
        """
        project = validate_project_id(project)
        subject = validate_subject_id(subject)
        session = validate_session_id(session)

        # List resources using object API
        sess = self.conn.interface.select.project(project).subject(subject).experiment(session)

        try:
            labels = sess.resources().get("label")
        except Exception as e:
            self.log.debug("Could not get resource labels, falling back: %s", e)
            labels = [r for r in (sess.resources().get() or [])]

        base = f"/data/projects/{project}/subjects/{subject}/experiments/{session}"
        downloaded: List[Path] = []

        for label in labels:
            label_q = quote(label)
            filename_safe = label.replace("/", "_").replace(" ", "_")
            out = out_dir / f"resources_{filename_safe}.zip"
            self._download_stream(f"{base}/resources/{label_q}/files?format=zip", out)
            downloaded.append(out)

        return downloaded

    def download_assessor_or_recon_resources_zip(
        self,
        project: str,
        subject: str,
        session: str,
        out_dir: Path,
        *,
        kind: str,
    ) -> Optional[Path]:
        """Download assessor or reconstruction resources as ZIP.

        Args:
            project: Project identifier.
            subject: Subject identifier.
            session: Session identifier.
            out_dir: Output directory.
            kind: 'assessors' or 'reconstructions'.

        Returns:
            Path to downloaded ZIP, or None if empty.
        """
        if kind not in {"assessors", "reconstructions"}:
            raise ValueError("kind must be 'assessors' or 'reconstructions'")

        project = validate_project_id(project)
        subject = validate_subject_id(subject)
        session = validate_session_id(session)

        base = f"/data/projects/{project}/subjects/{subject}/experiments/{session}"
        name = "assessor_resources.zip" if kind == "assessors" else "recon_resources.zip"
        out = out_dir / name

        try:
            self._download_stream(f"{base}/{kind}/ALL/resources/ALL/files?format=zip", out)
            return out
        except Exception as e:
            self.log.debug("Could not download %s: %s", kind, e)
            return None

    # =========================================================================
    # Full Session Download
    # =========================================================================

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
    ) -> Path:
        """Download all data for a session.

        Downloads scans and resources, optionally including assessors
        and reconstructions.

        Args:
            project: Project identifier.
            subject: Subject identifier.
            session: Session identifier.
            output_dir: Output directory.
            include_assessors: Include assessor resources.
            include_recons: Include reconstruction resources.
            parallel: Download in parallel.
            max_workers: Max parallel workers.

        Returns:
            Path to session directory containing downloads.
        """
        project = validate_project_id(project)
        subject = validate_subject_id(subject)
        session = validate_session_id(session)
        output_dir = validate_path_writable(output_dir)
        max_workers = validate_workers(max_workers, "max_workers")

        with LogContext(
            "download_session",
            self.log,
            project=project,
            subject=subject,
            session=session,
        ):
            output_dir.mkdir(parents=True, exist_ok=True)
            session_dir = output_dir / session
            session_dir.mkdir(parents=True, exist_ok=True)

            # Build task list
            tasks = [
                lambda: self.download_scans_zip(project, subject, session, session_dir),
                lambda: self.download_session_resources_zip(project, subject, session, session_dir),
            ]

            if include_assessors:
                tasks.append(
                    lambda: self.download_assessor_or_recon_resources_zip(
                        project, subject, session, session_dir, kind="assessors"
                    )
                )

            if include_recons:
                tasks.append(
                    lambda: self.download_assessor_or_recon_resources_zip(
                        project, subject, session, session_dir, kind="reconstructions"
                    )
                )

            # Execute downloads
            if parallel and len(tasks) > 1:
                with ThreadPoolExecutor(max_workers=min(max_workers, len(tasks))) as ex:
                    list(ex.map(lambda fn: fn(), tasks))
            else:
                for fn in tasks:
                    fn()

            self.log.info("Session download complete: %s", session_dir)

            self._audit.log_operation(
                "download_session",
                project=project,
                subject=subject,
                session=session,
                user=self.conn.username,
                success=True,
            )

            return session_dir

    # =========================================================================
    # ZIP Extraction
    # =========================================================================

    def extract_session_downloads(self, session_dir: Path) -> None:
        """Extract all downloaded ZIPs into organized folders.

        Layout after extraction:
        - scans.zip -> scans/
        - resources_<label>.zip -> resources/<label>/
        - assessor_resources.zip -> assessors/
        - recon_resources.zip -> reconstructions/

        Args:
            session_dir: Session directory containing ZIP files.
        """
        session_dir = validate_path_exists(session_dir, must_be_dir=True)

        with LogContext("extract_session", self.log, session_dir=str(session_dir)):
            for zip_path in sorted(session_dir.glob("*.zip")):
                name = zip_path.name

                # Determine target directory based on filename
                if name == "scans.zip":
                    target_dir = session_dir / "scans"
                elif name.startswith("resources_") and name.endswith(".zip"):
                    label = name[len("resources_") : -len(".zip")]
                    target_dir = session_dir / "resources" / label
                elif name == "assessor_resources.zip":
                    target_dir = session_dir / "assessors"
                elif name == "recon_resources.zip":
                    target_dir = session_dir / "reconstructions"
                else:
                    target_dir = session_dir / zip_path.stem

                target_dir.mkdir(parents=True, exist_ok=True)
                self.log.info("Extracting %s -> %s", name, target_dir)

                with zipfile.ZipFile(zip_path) as zf:
                    zf.extractall(target_dir)

                self.log.info("Extracted %s", name)
