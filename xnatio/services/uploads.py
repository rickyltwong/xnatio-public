"""Upload service for XNAT resources.

This module handles file uploads:
- Session resource uploads (single file, directory, zip)
- Scan resource uploads
- DICOM archive uploads via import service
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Sequence
from urllib.parse import quote

from ..core import (
    # Exceptions
    ArchiveUploadError,
    ResourceUploadError,
    ValidationError,
    # Logging
    get_audit_logger,
    get_logger,
    LogContext,
    # Utils
    zip_dir_to_temp,
    # Validation
    validate_archive_path,
    validate_overwrite_mode,
    validate_path_exists,
    validate_project_id,
    validate_resource_label,
    validate_scan_id,
    validate_session_id,
    validate_subject_id,
)
from .base import XNATConnection
from .projects import ProjectService


class UploadService:
    """Service for uploading files to XNAT.

    Handles:
    - Session resource uploads (file, directory, zip+extract)
    - Scan resource uploads
    - DICOM archive uploads via import service
    """

    def __init__(self, connection: XNATConnection) -> None:
        """Initialize upload service.

        Args:
            connection: XNAT connection instance.
        """
        self.conn = connection
        self.log = get_logger(__name__)
        self._audit = get_audit_logger()
        self._projects = ProjectService(connection)

    # =========================================================================
    # Session Resource Uploads
    # =========================================================================

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
        """Upload a single file to a session resource.

        Args:
            project: Project identifier.
            subject: Subject identifier.
            session: Session identifier.
            resource_label: Resource label (e.g., 'BIDS').
            file_path: Local file path.
            remote_name: Optional remote filename (defaults to local name).

        Raises:
            PathValidationError: If file doesn't exist.
            ResourceUploadError: If upload fails.
        """
        project = validate_project_id(project)
        subject = validate_subject_id(subject)
        session = validate_session_id(session)
        resource_label = validate_resource_label(resource_label)
        file_path = validate_path_exists(file_path, must_be_file=True)

        with LogContext(
            "upload_resource_file",
            self.log,
            project=project,
            session=session,
            resource=resource_label,
        ):
            self._projects.ensure_subject(project, subject)
            self._projects.ensure_session(project, subject, session)

            base = f"/data/projects/{project}/subjects/{subject}/experiments/{session}"
            remote = quote(remote_name or file_path.name)
            url = f"{base}/resources/{quote(resource_label)}/files/{remote}?inbody=true"

            size_mb = file_path.stat().st_size / (1024 * 1024)
            self.log.info(
                "Uploading %s (%.1f MB) -> %s/%s",
                file_path.name,
                size_mb,
                resource_label,
                remote,
            )

            try:
                with open(file_path, "rb") as f:
                    resp = self.conn.put(
                        url,
                        data=f,
                        headers={"Content-Type": "application/octet-stream"},
                    )
                resp.raise_for_status()
                self.log.info("Upload complete (%d)", resp.status_code)

                self._audit.log_operation(
                    "upload_resource_file",
                    project=project,
                    session=session,
                    details={"resource": resource_label, "file": file_path.name, "size_mb": size_mb},
                    user=self.conn.username,
                    success=True,
                )

            except Exception as e:
                raise ResourceUploadError(resource_label, str(file_path), str(e)) from e

    def upload_session_resource_dir(
        self,
        *,
        project: str,
        subject: str,
        session: str,
        resource_label: str,
        local_dir: Path,
    ) -> dict[str, int]:
        """Upload all files from a directory to a session resource.

        Files are uploaded preserving relative paths.

        Args:
            project: Project identifier.
            subject: Subject identifier.
            session: Session identifier.
            resource_label: Resource label.
            local_dir: Local directory path.

        Returns:
            Dict with 'uploaded' and 'failed' counts.
        """
        project = validate_project_id(project)
        subject = validate_subject_id(subject)
        session = validate_session_id(session)
        resource_label = validate_resource_label(resource_label)
        local_dir = validate_path_exists(local_dir, must_be_dir=True)

        with LogContext(
            "upload_resource_dir",
            self.log,
            project=project,
            session=session,
            resource=resource_label,
        ):
            self._projects.ensure_subject(project, subject)
            self._projects.ensure_session(project, subject, session)

            base = f"/data/projects/{project}/subjects/{subject}/experiments/{session}"
            uploaded = 0
            failed = 0

            for path in sorted(local_dir.rglob("*")):
                if not path.is_file():
                    continue

                rel_path = path.relative_to(local_dir).as_posix()
                url = f"{base}/resources/{quote(resource_label)}/files/{quote(rel_path)}?inbody=true"

                try:
                    with open(path, "rb") as f:
                        resp = self.conn.put(
                            url,
                            data=f,
                            headers={"Content-Type": "application/octet-stream"},
                        )

                    if resp.status_code in (200, 201):
                        uploaded += 1
                        self.log.debug("OK %s", rel_path)
                    else:
                        failed += 1
                        self.log.warning("%s -> %d", rel_path, resp.status_code)

                except Exception as e:
                    failed += 1
                    self.log.warning("%s -> error: %s", rel_path, e)

            self.log.info("Upload complete: %d ok, %d failed", uploaded, failed)
            return {"uploaded": uploaded, "failed": failed}

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
        """Zip a directory and upload with server-side extraction.

        More efficient than upload_session_resource_dir for many files.

        Args:
            project: Project identifier.
            subject: Subject identifier.
            session: Session identifier.
            resource_label: Resource label.
            local_dir: Local directory to zip.
            zip_name: Optional name for the zip file.
        """
        project = validate_project_id(project)
        subject = validate_subject_id(subject)
        session = validate_session_id(session)
        resource_label = validate_resource_label(resource_label)
        local_dir = validate_path_exists(local_dir, must_be_dir=True)

        with LogContext(
            "upload_resource_zip",
            self.log,
            project=project,
            session=session,
            resource=resource_label,
        ):
            self._projects.ensure_subject(project, subject)
            self._projects.ensure_session(project, subject, session)

            base = f"/data/projects/{project}/subjects/{subject}/experiments/{session}"
            remote_zip_name = zip_name or f"{resource_label}.zip"
            url = (
                f"{base}/resources/{quote(resource_label)}/files/{quote(remote_zip_name)}"
                f"?extract=true&inbody=true"
            )

            self.log.info("Creating ZIP from %s", local_dir)
            tmp_zip = zip_dir_to_temp(local_dir)
            size_mb = tmp_zip.stat().st_size / (1024 * 1024)
            self.log.info("ZIP ready (%.1f MB). Uploading with extract=true...", size_mb)

            try:

                def _do_upload() -> None:
                    with open(tmp_zip, "rb") as f:
                        resp = self.conn.put(
                            url,
                            data=f,
                            headers={"Content-Type": "application/zip"},
                        )
                    resp.raise_for_status()
                    self.log.info("Extract upload complete (%d)", resp.status_code)

                self.conn.retry_on_network_error(_do_upload, operation="upload_zip")

                self._audit.log_operation(
                    "upload_resource_zip",
                    project=project,
                    session=session,
                    details={"resource": resource_label, "size_mb": size_mb},
                    user=self.conn.username,
                    success=True,
                )

            finally:
                try:
                    tmp_zip.unlink()
                except Exception as e:
                    self.log.debug("Failed to remove temp zip %s: %s", tmp_zip, e)

    # =========================================================================
    # Scan Resource Uploads
    # =========================================================================

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
        """Upload a file to a scan resource.

        Args:
            project: Project identifier.
            subject: Subject identifier.
            session: Session identifier.
            scan_id: Scan identifier.
            resource_label: Resource label.
            file_path: Local file path.
            remote_name: Optional remote filename.
        """
        project = validate_project_id(project)
        subject = validate_subject_id(subject)
        session = validate_session_id(session)
        scan_id = validate_scan_id(scan_id)
        resource_label = validate_resource_label(resource_label)
        file_path = validate_path_exists(file_path, must_be_file=True)

        with LogContext(
            "upload_scan_resource",
            self.log,
            project=project,
            session=session,
            scan=scan_id,
            resource=resource_label,
        ):
            self._projects.ensure_subject(project, subject)
            self._projects.ensure_session(project, subject, session)

            base = (
                f"/data/projects/{project}/subjects/{subject}/experiments/{session}"
                f"/scans/{quote(scan_id)}"
            )
            remote = quote(remote_name or file_path.name)
            url = f"{base}/resources/{quote(resource_label)}/files/{remote}?inbody=true"

            size_mb = file_path.stat().st_size / (1024 * 1024)
            self.log.info(
                "Uploading %s (%.1f MB) -> scan %s/%s/%s",
                file_path.name,
                size_mb,
                scan_id,
                resource_label,
                remote,
            )

            with open(file_path, "rb") as f:
                resp = self.conn.put(
                    url,
                    data=f,
                    headers={"Content-Type": "application/octet-stream"},
                )
            resp.raise_for_status()
            self.log.info("Scan resource upload complete (%d)", resp.status_code)

    # =========================================================================
    # DICOM Archive Uploads
    # =========================================================================

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
        """Upload DICOM archive via import service.

        Args:
            archive: Path to ZIP/TAR archive.
            project: Project identifier.
            subject: Subject identifier.
            session: Session identifier.
            import_handler: XNAT import handler (default: DICOM-zip).
            ignore_unparsable: Ignore non-DICOM files.
            dest: Optional destination route.
            overwrite: Overwrite mode ('none', 'append', 'delete').
            overwrite_files: Allow file overwrites for merges.
            quarantine: Place in quarantine.
            trigger_pipelines: Run AutoRun pipelines.
            rename: Rename incoming DICOM files.
            srcs: Server-side sources.
            http_session_listener: Web uploader tracking ID.
            direct_archive: Use direct-to-archive mode.
        """
        project = validate_project_id(project)
        subject = validate_subject_id(subject)
        session = validate_session_id(session)
        archive = validate_archive_path(archive)
        overwrite = validate_overwrite_mode(overwrite)

        with LogContext(
            "upload_dicom",
            self.log,
            project=project,
            subject=subject,
            session=session,
            archive=archive.name,
        ):
            self._projects.ensure_subject(project, subject)

            size_gb = archive.stat().st_size / (1024 * 1024 * 1024)
            self.log.info(
                "Starting DICOM upload of %s (%.2f GB); direct-archive=%s",
                archive.name,
                size_gb,
                direct_archive,
            )

            params = {
                "import-handler": import_handler,
                "Ignore-Unparsable": "true" if ignore_unparsable else "false",
                "project": project,
                "subject": subject,
                "session": session,
                "overwrite": overwrite,
                "overwrite_files": "true" if overwrite_files else "false",
                "quarantine": "true" if quarantine else "false",
                "triggerPipelines": "true" if trigger_pipelines else "false",
                "rename": "true" if rename else "false",
                "Direct-Archive": "true" if direct_archive else "false",
            }

            if dest:
                params["dest"] = dest
            if http_session_listener:
                params["http-session-listener"] = http_session_listener
            if srcs:
                params["src"] = ",".join(srcs)

            try:
                with open(archive, "rb") as f:
                    files = {"file": (archive.name, f)}
                    resp = self.conn.post(
                        "/data/services/import",
                        params=params,
                        files=files,
                    )
                    resp.raise_for_status()

                self.log.info("DICOM import complete (%d)", resp.status_code)

                self._audit.log_operation(
                    "upload_dicom",
                    project=project,
                    subject=subject,
                    session=session,
                    details={"archive": archive.name, "size_gb": round(size_gb, 2)},
                    user=self.conn.username,
                    success=True,
                )

            except Exception as e:
                self._audit.log_operation(
                    "upload_dicom",
                    project=project,
                    subject=subject,
                    session=session,
                    details={"archive": archive.name},
                    user=self.conn.username,
                    success=False,
                    error=str(e),
                )
                raise ArchiveUploadError(str(archive), str(e)) from e
