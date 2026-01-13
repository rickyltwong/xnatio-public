"""Scan management service.

This module handles scan-level operations:
- Scan creation and listing
- Scan deletion (with dry-run support)
- Scan resource management
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from ..core import (
    # Exceptions
    LogContext,
    get_audit_logger,
    get_logger,
    # Validation
    validate_project_id,
    validate_scan_id,
    validate_session_id,
    validate_subject_id,
    validate_workers,
)
from .base import XNATConnection
from .projects import ProjectService


class ScanService:
    """Service for scan operations.

    Handles:
    - Scan creation with auto-incrementing IDs
    - Scan listing
    - Scan deletion (single, batch, with dry-run)
    - Scan attribute management
    """

    def __init__(self, connection: XNATConnection) -> None:
        """Initialize scan service.

        Args:
            connection: XNAT connection instance.
        """
        self.conn = connection
        self.log = get_logger(__name__)
        self._audit = get_audit_logger()
        self._projects = ProjectService(connection)

    # =========================================================================
    # Scan Listing
    # =========================================================================

    def list_scans(
        self,
        project: str,
        subject: str,
        session: str,
    ) -> List[str]:
        """List scan IDs for a session.

        Args:
            project: Project identifier.
            subject: Subject identifier.
            session: Session identifier.

        Returns:
            List of scan IDs as strings.
        """
        project = validate_project_id(project)
        subject = validate_subject_id(subject)
        session = validate_session_id(session)

        sess = self.conn.interface.select.project(project).subject(subject).experiment(session)
        scans_coll = sess.scans()

        ids: List[str] = []

        # Try to get IDs directly
        try:
            raw_ids = scans_coll.get("ID")
            if raw_ids:
                candidate = [str(i) for i in raw_ids]
                if all(s.isdigit() for s in candidate):
                    ids = candidate
        except Exception as e:
            self.log.debug("Could not get scan IDs by 'ID' column: %s", e)

        # Fallback: parse from generic listing
        if not ids:
            try:
                raw_list = scans_coll.get() or []
            except Exception as e:
                self.log.debug("Could not get scans list: %s", e)
                raw_list = []

            extracted: List[str] = []
            for entry in raw_list:
                s = str(entry)
                m = re.search(r"/scans/(\d+)", s)
                if m:
                    extracted.append(m.group(1))
                    continue
                if s.isdigit():
                    extracted.append(s)

            # Deduplicate while preserving order
            ids = list(dict.fromkeys(extracted))

        return ids

    # =========================================================================
    # Scan Creation
    # =========================================================================

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
        """Create a scan with auto-incremented ID.

        Args:
            project: Project identifier.
            subject: Subject identifier.
            session: Session identifier.
            xsi_type: XNAT scan type (default: xnat:mrScanData).
            scan_type: Optional scan type label (T1, T2, etc.).
            params: Additional scan attributes.

        Returns:
            The new scan ID.
        """
        project = validate_project_id(project)
        subject = validate_subject_id(subject)
        session = validate_session_id(session)

        with LogContext(
            "add_scan",
            self.log,
            project=project,
            subject=subject,
            session=session,
        ):
            # Ensure container hierarchy exists
            self._projects.ensure_subject(project, subject)
            self._projects.ensure_session(project, subject, session)

            # Get existing scans to determine next ID
            existing_ids = self.list_scans(project, subject, session)
            numeric_ids = []
            for sid in existing_ids:
                try:
                    numeric_ids.append(int(sid))
                except ValueError:
                    continue

            next_id = (max(numeric_ids) + 1) if numeric_ids else 1
            scan_id = str(next_id)

            # Create the scan
            sess = self.conn.interface.select.project(project).subject(subject).experiment(session)
            scan_obj = sess.scan(scan_id)

            if not scan_obj.exists():
                scan_obj.insert(scans=xsi_type)

            # Set attributes
            try:
                if scan_type:
                    scan_obj.attrs.set(f"{xsi_type}/type", scan_type)
                if params:
                    scan_obj.attrs.mset(params)
            except Exception as e:
                self.log.debug("Failed to set scan attributes for scan %s: %s", scan_id, e)

            self.log.info("Created scan %s in session %s", scan_id, session)

            self._audit.log_operation(
                "add_scan",
                project=project,
                subject=subject,
                session=session,
                details={"scan_id": scan_id, "type": scan_type},
                user=self.conn.username,
                success=True,
            )

            return scan_id

    # =========================================================================
    # Scan Deletion
    # =========================================================================

    def delete_scans(
        self,
        project: str,
        subject: str,
        session: str,
        scan_ids: Optional[List[str]] = None,
        *,
        dry_run: bool = False,
        parallel: bool = False,
        max_workers: int = 2,
    ) -> Dict[str, Any]:
        """Delete scans from a session.

        Args:
            project: Project identifier.
            subject: Subject identifier.
            session: Session identifier.
            scan_ids: List of scan IDs to delete, or None for all.
            dry_run: If True, only report what would be deleted.
            parallel: If True, delete in parallel.
            max_workers: Max parallel workers.

        Returns:
            Dict with keys:
            - 'deleted': List of deleted scan IDs
            - 'failed': Dict of {scan_id: error_message}
            - 'skipped': List of skipped scan IDs (not found)
            - 'dry_run': Boolean indicating if this was a dry run
        """
        project = validate_project_id(project)
        subject = validate_subject_id(subject)
        session = validate_session_id(session)
        max_workers = validate_workers(max_workers, "max_workers", max_value=10)

        with LogContext(
            "delete_scans",
            self.log,
            project=project,
            subject=subject,
            session=session,
            dry_run=dry_run,
        ):
            # Get available scans
            available_scans = self.list_scans(project, subject, session)

            if not available_scans:
                self.log.info("No scans found for %s/%s/%s", project, subject, session)
                return {"deleted": [], "failed": {}, "skipped": [], "dry_run": dry_run}

            # Determine which scans to delete
            if scan_ids is None:
                scans_to_delete = available_scans
            else:
                # Validate scan IDs
                scans_to_delete = []
                skipped = []
                for sid in scan_ids:
                    sid = validate_scan_id(sid)
                    if sid in available_scans:
                        scans_to_delete.append(sid)
                    else:
                        skipped.append(sid)
                        self.log.warning("Scan %s not found, skipping", sid)

            if not scans_to_delete:
                return {
                    "deleted": [],
                    "failed": {},
                    "skipped": skipped if scan_ids else [],
                    "dry_run": dry_run,
                }

            self.log.info(
                "%s %d scans: %s",
                "[DRY-RUN] Would delete" if dry_run else "Deleting",
                len(scans_to_delete),
                ", ".join(scans_to_delete),
            )

            if dry_run:
                return {
                    "deleted": scans_to_delete,
                    "failed": {},
                    "skipped": skipped if scan_ids else [],
                    "dry_run": True,
                }

            # Perform deletion
            deleted: List[str] = []
            failed: Dict[str, str] = {}

            def _delete_one(sid: str) -> tuple[str, Optional[str]]:
                try:
                    self.conn.interface.select.project(project).subject(subject).experiment(
                        session
                    ).scan(sid).delete(delete_files=True)
                    self.log.info("Deleted scan %s", sid)
                    return (sid, None)
                except Exception as e:
                    self.log.error("Failed to delete scan %s: %s", sid, e)
                    return (sid, str(e))

            if parallel and len(scans_to_delete) > 1:
                worker_count = min(max_workers, len(scans_to_delete))
                with ThreadPoolExecutor(max_workers=worker_count) as ex:
                    for sid, error in ex.map(_delete_one, scans_to_delete):
                        if error:
                            failed[sid] = error
                        else:
                            deleted.append(sid)
            else:
                for sid in scans_to_delete:
                    sid, error = _delete_one(sid)
                    if error:
                        failed[sid] = error
                    else:
                        deleted.append(sid)

            self.log.info(
                "Deleted %d/%d scans (%d failed)",
                len(deleted),
                len(scans_to_delete),
                len(failed),
            )

            self._audit.log_operation(
                "delete_scans",
                project=project,
                subject=subject,
                session=session,
                details={
                    "deleted": deleted,
                    "failed_count": len(failed),
                },
                user=self.conn.username,
                success=len(failed) == 0,
            )

            return {
                "deleted": deleted,
                "failed": failed,
                "skipped": skipped if scan_ids else [],
                "dry_run": False,
            }
