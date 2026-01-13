"""Project, subject, and session management service.

This module handles CRUD operations for XNAT container hierarchy:
- Projects
- Subjects
- Sessions (experiments)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from ..core import (
    # Exceptions
    ResourceAccessDeniedError,
    ResourceExistsError,
    ResourceNotFoundError,
    # Logging
    get_audit_logger,
    get_logger,
    LogContext,
    # Validation
    validate_project_id,
    validate_session_id,
    validate_subject_id,
)
from .base import XNATConnection


class ProjectService:
    """Service for project, subject, and session management.

    Handles:
    - Project creation
    - Subject creation and listing
    - Session (experiment) creation and listing
    - Container existence checks
    """

    def __init__(self, connection: XNATConnection) -> None:
        """Initialize project service.

        Args:
            connection: XNAT connection instance.
        """
        self.conn = connection
        self.log = get_logger(__name__)
        self._audit = get_audit_logger()

    # =========================================================================
    # Project Operations
    # =========================================================================

    def create_project(
        self,
        project_id: str,
        *,
        description: Optional[str] = None,
    ) -> bool:
        """Create a new project if it doesn't exist.

        Args:
            project_id: Project identifier.
            description: Optional project description.

        Returns:
            True if project was created, False if it already existed.

        Raises:
            ResourceAccessDeniedError: If user cannot create projects.
        """
        project_id = validate_project_id(project_id)

        with LogContext("create_project", self.log, project=project_id):
            project = self.conn.interface.select.project(project_id)

            if project.exists():
                self.log.info("Project %s already exists", project_id)
                return False

            try:
                project.insert()
                self.log.info("Created project: %s", project_id)

                if description:
                    self._set_project_description(project_id, description)

                self._audit.log_operation(
                    "create_project",
                    project=project_id,
                    user=self.conn.username,
                    success=True,
                )
                return True

            except Exception as e:
                self._audit.log_operation(
                    "create_project",
                    project=project_id,
                    user=self.conn.username,
                    success=False,
                    error=str(e),
                )
                raise

    def _set_project_description(self, project_id: str, description: str) -> None:
        """Set project description (best effort)."""
        try:
            project = self.conn.interface.select.project(project_id)
            project.attrs.set("xnat:projectData/description", description)
        except Exception as e:
            # Some XNAT versions restrict description updates
            self.log.debug("Failed to set project description for %s: %s", project_id, e)

    def project_exists(self, project_id: str) -> bool:
        """Check if project exists.

        Args:
            project_id: Project identifier.

        Returns:
            True if project exists.
        """
        project_id = validate_project_id(project_id)
        return self.conn.interface.select.project(project_id).exists()

    # =========================================================================
    # Subject Operations
    # =========================================================================

    def ensure_subject(
        self,
        project: str,
        subject: str,
        *,
        auto_create: bool = True,
    ) -> bool:
        """Ensure a subject exists in the project.

        Args:
            project: Project identifier.
            subject: Subject identifier.
            auto_create: If True, create subject if missing.

        Returns:
            True if subject exists or was created.

        Raises:
            ResourceNotFoundError: If subject doesn't exist and auto_create is False.
        """
        project = validate_project_id(project)
        subject = validate_subject_id(subject)

        subj = self.conn.interface.select.project(project).subject(subject)

        try:
            if subj.exists():
                return True

            if not auto_create:
                raise ResourceNotFoundError("subject", subject, project)

            subj.insert()
            self.log.debug("Created subject %s in project %s", subject, project)
            return True

        except ResourceNotFoundError:
            raise
        except Exception as e:
            self.log.debug("Failed to ensure subject %s in project %s: %s", subject, project, e)
            return False

    def subject_exists(self, project: str, subject: str) -> bool:
        """Check if subject exists.

        Args:
            project: Project identifier.
            subject: Subject identifier.

        Returns:
            True if subject exists.
        """
        project = validate_project_id(project)
        subject = validate_subject_id(subject)
        return self.conn.interface.select.project(project).subject(subject).exists()

    def list_subjects(self, project: str) -> List[Dict[str, str]]:
        """List all subjects in a project.

        Args:
            project: Project identifier.

        Returns:
            List of dicts with keys: 'ID', 'label'.
        """
        project = validate_project_id(project)

        with LogContext("list_subjects", self.log, project=project, log_entry_exit=False):
            resp = self.conn.get(
                f"/data/projects/{project}/subjects",
                params={"columns": "ID,label", "format": "json"},
            )
            resp.raise_for_status()

            payload = resp.json()
            results = payload.get("ResultSet", {}).get("Result", []) or []

            subjects: List[Dict[str, str]] = []
            for entry in results:
                subj_id = str(entry.get("ID") or "").strip()
                label = str(entry.get("label") or "").strip()
                if subj_id and label:
                    subjects.append({"ID": subj_id, "label": label})

            return subjects

    def delete_subject(self, project: str, subject: str) -> bool:
        """Delete a subject from the project.

        Args:
            project: Project identifier.
            subject: Subject identifier.

        Returns:
            True if subject was deleted.

        Raises:
            ResourceNotFoundError: If subject doesn't exist.
        """
        project = validate_project_id(project)
        subject = validate_subject_id(subject)

        with LogContext("delete_subject", self.log, project=project, subject=subject):
            subj = self.conn.interface.select.project(project).subject(subject)

            if not subj.exists():
                raise ResourceNotFoundError("subject", subject, project)

            subj.delete()
            self.log.info("Deleted subject %s from project %s", subject, project)

            self._audit.log_operation(
                "delete_subject",
                project=project,
                subject=subject,
                user=self.conn.username,
                success=True,
            )
            return True

    # =========================================================================
    # Session (Experiment) Operations
    # =========================================================================

    def ensure_session(
        self,
        project: str,
        subject: str,
        session: str,
        *,
        session_type: str = "xnat:mrSessionData",
        auto_create: bool = True,
    ) -> bool:
        """Ensure a session exists for the subject.

        Args:
            project: Project identifier.
            subject: Subject identifier.
            session: Session identifier.
            session_type: XNAT session type (default: MR session).
            auto_create: If True, create session if missing.

        Returns:
            True if session exists or was created.
        """
        project = validate_project_id(project)
        subject = validate_subject_id(subject)
        session = validate_session_id(session)

        sess = self.conn.interface.select.project(project).subject(subject).experiment(session)

        try:
            if sess.exists():
                return True

            if not auto_create:
                raise ResourceNotFoundError("session", session, project)

            sess.insert(experiments=session_type)
            self.log.debug(
                "Created session %s for subject %s in project %s",
                session,
                subject,
                project,
            )
            return True

        except ResourceNotFoundError:
            raise
        except Exception as e:
            self.log.debug("Failed to ensure session %s for subject %s: %s", session, subject, e)
            return False

    def session_exists(self, project: str, subject: str, session: str) -> bool:
        """Check if session exists.

        Args:
            project: Project identifier.
            subject: Subject identifier.
            session: Session identifier.

        Returns:
            True if session exists.
        """
        project = validate_project_id(project)
        subject = validate_subject_id(subject)
        session = validate_session_id(session)
        return (
            self.conn.interface.select.project(project)
            .subject(subject)
            .experiment(session)
            .exists()
        )

    def list_subject_experiments(self, project: str, subject: str) -> List[Dict[str, str]]:
        """List experiments for a subject.

        Args:
            project: Project identifier.
            subject: Subject identifier.

        Returns:
            List of dicts with keys: 'ID', 'label', 'xsiType'.
        """
        project = validate_project_id(project)
        subject = validate_subject_id(subject)

        resp = self.conn.get(
            f"/data/projects/{project}/subjects/{quote(subject)}/experiments",
            params={"format": "json"},
        )
        resp.raise_for_status()

        payload = resp.json()
        results = payload.get("ResultSet", {}).get("Result", []) or []

        experiments: List[Dict[str, str]] = []
        for entry in results:
            exp_id = str(entry.get("ID") or entry.get("id") or "").strip()
            label = str(entry.get("label") or "").strip()
            xsi_type = str(entry.get("xsiType") or "").strip()
            if exp_id:
                experiments.append({"ID": exp_id, "label": label, "xsiType": xsi_type})

        return experiments

    def list_subject_experiments_detailed(
        self,
        project: str,
        subject: str,
    ) -> List[Dict[str, str]]:
        """List experiments with timing metadata.

        Args:
            project: Project identifier.
            subject: Subject identifier.

        Returns:
            List of dicts with keys: 'ID', 'label', 'xsiType', 'date', 'time',
            'insert_date', 'insert_time'.
        """
        project = validate_project_id(project)
        subject = validate_subject_id(subject)

        url = f"/data/projects/{project}/subjects/{quote(subject)}/experiments"
        params = {
            "format": "json",
            "columns": "ID,label,xsiType,date,time,start_time,insert_date,insert_time",
        }

        try:
            resp = self.conn.get(url, params=params)
            resp.raise_for_status()
        except Exception:
            self.log.warning("Experiment listing with columns failed; retrying without columns")
            resp = self.conn.get(url, params={"format": "json"})
            resp.raise_for_status()

        payload = resp.json()
        results = payload.get("ResultSet", {}).get("Result", []) or []

        experiments: List[Dict[str, str]] = []
        for entry in results:
            exp_id = str(entry.get("ID") or entry.get("id") or "").strip()
            if not exp_id:
                continue
            experiments.append({
                "ID": exp_id,
                "label": str(entry.get("label") or "").strip(),
                "xsiType": str(entry.get("xsiType") or "").strip(),
                "date": str(entry.get("date") or entry.get("session_date") or "").strip(),
                "time": str(entry.get("time") or entry.get("start_time") or "").strip(),
                "insert_date": str(entry.get("insert_date") or "").strip(),
                "insert_time": str(entry.get("insert_time") or "").strip(),
            })

        return experiments

    def move_experiment_to_subject(
        self,
        project: str,
        experiment_id: str,
        new_subject: str,
    ) -> None:
        """Move an experiment to a different subject.

        Args:
            project: Project identifier.
            experiment_id: Experiment ID to move.
            new_subject: Target subject identifier.
        """
        project = validate_project_id(project)
        new_subject = validate_subject_id(new_subject)

        with LogContext(
            "move_experiment",
            self.log,
            project=project,
            experiment=experiment_id,
            new_subject=new_subject,
        ):
            resp = self.conn.put(
                f"/data/projects/{project}/experiments/{quote(experiment_id)}",
                params={"xnat:experimentData/subject_ID": new_subject},
            )
            resp.raise_for_status()
            self.log.info("Moved experiment %s to subject %s", experiment_id, new_subject)

            self._audit.log_operation(
                "move_experiment",
                project=project,
                session=experiment_id,
                details={"new_subject": new_subject},
                user=self.conn.username,
                success=True,
            )

    def rename_experiment(
        self,
        project: str,
        experiment_id: str,
        new_label: str,
    ) -> None:
        """Rename an experiment.

        Args:
            project: Project identifier.
            experiment_id: Experiment ID to rename.
            new_label: New label for the experiment.
        """
        project = validate_project_id(project)

        with LogContext(
            "rename_experiment",
            self.log,
            project=project,
            experiment=experiment_id,
            new_label=new_label,
        ):
            resp = self.conn.put(
                f"/data/projects/{project}/experiments/{quote(experiment_id)}",
                params={"label": new_label},
            )
            resp.raise_for_status()
            self.log.info("Renamed experiment %s -> %s", experiment_id, new_label)

            self._audit.log_operation(
                "rename_experiment",
                project=project,
                session=experiment_id,
                details={"new_label": new_label},
                user=self.conn.username,
                success=True,
            )
