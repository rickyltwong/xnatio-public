"""XNATClient - Backward-compatible facade for XNAT operations.

This module provides a unified client interface that combines all services
for backward compatibility with existing code. New code should prefer using
the individual services directly for better modularity.

Usage:
    # Legacy style (still works)
    from xnatio import XNATClient, load_config

    cfg = load_config()
    client = XNATClient.from_config(cfg)
    client.create_project("MYPROJECT")

    # New modular style (preferred)
    from xnatio.services import XNATConnection, ProjectService

    conn = XNATConnection.from_config(cfg)
    projects = ProjectService(conn)
    projects.create_project("MYPROJECT")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .config import XNATConfig
from .core import get_logger
from .services import (
    AdminService,
    DownloadService,
    ProjectService,
    ScanService,
    UploadService,
    XNATConnection,
)


class XNATClient:
    """Unified client for XNAT operations.

    This class provides a backward-compatible interface that delegates to
    specialized service classes. It combines functionality from:
    - XNATConnection (base HTTP and authentication)
    - ProjectService (project, subject, session management)
    - ScanService (scan operations)
    - UploadService (file uploads)
    - DownloadService (file downloads)
    - AdminService (administrative tasks)

    For new code, consider using the individual services directly for
    better separation of concerns and testability.
    """

    def __init__(
        self,
        server: str,
        username: str,
        password: str,
        *,
        verify_tls: bool = True,
        http_timeouts: tuple[int, int] = (120, 604800),
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """Create a new XNAT client.

        Args:
            server: XNAT server URL.
            username: XNAT username.
            password: XNAT password.
            verify_tls: Whether to verify TLS certificates.
            http_timeouts: (connect_timeout, read_timeout) in seconds.
            logger: Optional logger instance.
        """
        self.log = logger or get_logger(__name__)

        # Create connection
        self._conn = XNATConnection(
            server=server,
            username=username,
            password=password,
            verify_tls=verify_tls,
            connect_timeout=http_timeouts[0],
            read_timeout=http_timeouts[1],
            logger=self.log,
        )

        # Initialize services
        self._projects = ProjectService(self._conn)
        self._scans = ScanService(self._conn)
        self._uploads = UploadService(self._conn)
        self._downloads = DownloadService(self._conn)
        self._admin = AdminService(self._conn)

    @classmethod
    def from_config(cls, cfg: XNATConfig) -> "XNATClient":
        """Create client from configuration dictionary.

        Args:
            cfg: Configuration from load_config().

        Returns:
            Configured XNATClient instance.
        """
        return cls(
            server=cfg["server"],
            username=cfg["user"],
            password=cfg["password"],
            verify_tls=cfg.get("verify_tls", True),
            http_timeouts=(
                cfg.get("http_connect_timeout", 120),
                cfg.get("http_read_timeout", 604800),
            ),
        )

    # =========================================================================
    # Properties for service access
    # =========================================================================

    @property
    def connection(self) -> XNATConnection:
        """Access the underlying connection."""
        return self._conn

    @property
    def interface(self):
        """Access pyxnat Interface for advanced operations."""
        return self._conn.interface

    @property
    def server(self) -> str:
        """XNAT server URL."""
        return self._conn.server

    @property
    def username(self) -> str:
        """XNAT username."""
        return self._conn.username

    @property
    def http_timeouts(self) -> tuple[int, int]:
        """HTTP timeouts (connect, read)."""
        return self._conn.http_timeouts

    # =========================================================================
    # Connection methods
    # =========================================================================

    def test_connection(self) -> str:
        """Test connection and return XNAT version."""
        return self._conn.test_connection()

    # =========================================================================
    # Project operations (delegated to ProjectService)
    # =========================================================================

    def create_project(self, project_id: str, description: Optional[str] = None) -> None:
        """Create a new project."""
        self._projects.create_project(project_id, description=description)

    def ensure_subject(self, project: str, subject: str, *, auto_create: bool = True) -> None:
        """Ensure a subject exists."""
        self._projects.ensure_subject(project, subject, auto_create=auto_create)

    def ensure_session(self, project: str, subject: str, session: str) -> None:
        """Ensure a session exists."""
        self._projects.ensure_session(project, subject, session)

    def list_subjects(self, project: str) -> List[Dict[str, str]]:
        """List subjects in a project."""
        return self._projects.list_subjects(project)

    def list_subject_experiments(self, project: str, subject: str) -> List[Dict[str, str]]:
        """List experiments for a subject."""
        return self._projects.list_subject_experiments(project, subject)

    def list_subject_experiments_detailed(self, project: str, subject: str) -> List[Dict[str, str]]:
        """List experiments with timing metadata."""
        return self._projects.list_subject_experiments_detailed(project, subject)

    def move_experiment_to_subject(
        self, project: str, experiment_id: str, new_subject: str
    ) -> None:
        """Move experiment to different subject."""
        self._projects.move_experiment_to_subject(project, experiment_id, new_subject)

    def rename_experiment(self, project: str, experiment_id: str, new_label: str) -> None:
        """Rename an experiment."""
        self._projects.rename_experiment(project, experiment_id, new_label)

    def delete_subject(self, project: str, subject: str) -> None:
        """Delete a subject."""
        self._projects.delete_subject(project, subject)

    # =========================================================================
    # Scan operations (delegated to ScanService)
    # =========================================================================

    def list_scans(self, project: str, subject: str, session: str) -> List[str]:
        """List scan IDs for a session."""
        return self._scans.list_scans(project, subject, session)

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
        """Create a new scan."""
        return self._scans.add_scan(
            project, subject, session, xsi_type=xsi_type, scan_type=scan_type, params=params
        )

    def delete_scans(
        self,
        project: str,
        subject: str,
        session: str,
        scan_ids: Optional[List[str]] = None,
        *,
        parallel: bool = False,
        max_workers: int = 2,
    ) -> List[str]:
        """Delete scans from a session.

        Returns list of deleted scan IDs for backward compatibility.
        """
        result = self._scans.delete_scans(
            project,
            subject,
            session,
            scan_ids,
            parallel=parallel,
            max_workers=max_workers,
        )
        return result["deleted"]

    # =========================================================================
    # Upload operations (delegated to UploadService)
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
        """Upload file to scan resource."""
        self._uploads.upload_scan_resource(
            project=project,
            subject=subject,
            session=session,
            scan_id=scan_id,
            resource_label=resource_label,
            file_path=file_path,
            remote_name=remote_name,
        )

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
        """Upload file to session resource."""
        self._uploads.upload_session_resource_file(
            project=project,
            subject=subject,
            session=session,
            resource_label=resource_label,
            file_path=file_path,
            remote_name=remote_name,
        )

    def upload_session_resource_dir(
        self,
        *,
        project: str,
        subject: str,
        session: str,
        resource_label: str,
        local_dir: Path,
    ) -> None:
        """Upload directory to session resource."""
        self._uploads.upload_session_resource_dir(
            project=project,
            subject=subject,
            session=session,
            resource_label=resource_label,
            local_dir=local_dir,
        )

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
        """Zip directory and upload with server-side extraction."""
        self._uploads.upload_session_resource_zip_dir(
            project=project,
            subject=subject,
            session=session,
            resource_label=resource_label,
            local_dir=local_dir,
            zip_name=zip_name,
        )

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
        """Upload DICOM archive via import service."""
        self._uploads.upload_dicom_zip(
            archive,
            project=project,
            subject=subject,
            session=session,
            import_handler=import_handler,
            ignore_unparsable=ignore_unparsable,
            dest=dest,
            overwrite=overwrite,
            overwrite_files=overwrite_files,
            quarantine=quarantine,
            trigger_pipelines=trigger_pipelines,
            rename=rename,
            srcs=srcs,
            http_session_listener=http_session_listener,
            direct_archive=direct_archive,
        )

    # =========================================================================
    # Download operations (delegated to DownloadService)
    # =========================================================================

    def download_scans_zip(self, project: str, subject: str, session: str, out_dir: Path) -> Path:
        """Download all scans as ZIP."""
        return self._downloads.download_scans_zip(project, subject, session, out_dir)

    def download_session_resources_zip(
        self, project: str, subject: str, session: str, out_dir: Path
    ) -> Path:
        """Download session resources as ZIPs."""
        self._downloads.download_session_resources_zip(project, subject, session, out_dir)
        return out_dir

    def download_assessor_or_recon_resources_zip(
        self,
        project: str,
        subject: str,
        session: str,
        out_dir: Path,
        *,
        kind: str,
    ) -> Optional[Path]:
        """Download assessor or reconstruction resources."""
        return self._downloads.download_assessor_or_recon_resources_zip(
            project, subject, session, out_dir, kind=kind
        )

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
        """Download all session data."""
        self._downloads.download_session(
            project,
            subject,
            session,
            output_dir,
            include_assessors=include_assessors,
            include_recons=include_recons,
            parallel=parallel,
            max_workers=max_workers,
        )

    def extract_session_downloads(self, session_dir: Path) -> None:
        """Extract downloaded ZIPs."""
        self._downloads.extract_session_downloads(session_dir)

    # =========================================================================
    # Admin operations (delegated to AdminService)
    # =========================================================================

    def refresh_project_experiment_catalogs(
        self,
        project: str,
        options: Optional[List[str]] = None,
        *,
        limit: Optional[int] = None,
        experiment_ids: Optional[Sequence[str]] = None,
        parallel: bool = False,
        max_workers: int = 4,
    ) -> List[str]:
        """Refresh catalog XMLs for project experiments."""
        return self._admin.refresh_project_experiment_catalogs(
            project,
            options,
            limit=limit,
            experiment_ids=experiment_ids,
            parallel=parallel,
            max_workers=max_workers,
        )

    def rename_subjects(self, project: str, mapping: Mapping[str, str]) -> Dict[str, str]:
        """Rename subjects using mapping.

        Returns dict of old->new for backward compatibility.
        """
        result = self._admin.rename_subjects(project, mapping)
        return result["renamed"]

    def rename_subjects_pattern(
        self,
        project: str,
        match_pattern: str,
        to_template: str,
        *,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Rename subjects matching pattern with merge support."""
        return self._admin.rename_subjects_pattern(
            project, match_pattern, to_template, dry_run=dry_run
        )

    def add_user_to_groups(self, username: str, groups: List[str]) -> Dict[str, Any]:
        """Add user to XNAT groups."""
        return self._admin.add_user_to_groups(username, groups)
