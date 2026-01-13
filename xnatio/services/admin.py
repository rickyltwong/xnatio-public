"""Administrative service for XNAT operations.

This module handles administrative tasks:
- Catalog refresh
- User group management
- Subject renaming (single, batch, pattern-based)
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import quote

from ..core import (
    # Exceptions
    LogContext,
    get_audit_logger,
    get_logger,
    # Validation
    validate_project_id,
    validate_regex_pattern,
    validate_workers,
)
from .base import XNATConnection
from .projects import ProjectService


class AdminService:
    """Service for XNAT administrative operations.

    Handles:
    - Catalog XML refresh
    - User group management
    - Subject renaming (direct, batch, pattern-based with merge)
    """

    def __init__(self, connection: XNATConnection) -> None:
        """Initialize admin service.

        Args:
            connection: XNAT connection instance.
        """
        self.conn = connection
        self.log = get_logger(__name__)
        self._audit = get_audit_logger()
        self._projects = ProjectService(connection)

    # =========================================================================
    # Catalog Management
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
        """Refresh catalog XMLs for project experiments.

        Args:
            project: Project identifier.
            options: Refresh options (checksum, delete, append, populateStats).
            limit: Optional limit on experiments to refresh.
            experiment_ids: Optional specific experiments to refresh.
            parallel: Refresh in parallel.
            max_workers: Max parallel workers.

        Returns:
            List of successfully refreshed experiment IDs.
        """
        project = validate_project_id(project)
        max_workers = validate_workers(max_workers, "max_workers")

        with LogContext("refresh_catalogs", self.log, project=project):
            # Get experiments list
            resp = self.conn.get(
                f"/data/projects/{project}/experiments",
                params={"columns": "ID,subject_ID,label", "format": "json"},
            )
            resp.raise_for_status()

            payload = resp.json()
            results = payload.get("ResultSet", {}).get("Result", []) or []

            experiments: List[Tuple[str, str, str]] = []
            for entry in results:
                exp_id = str(entry.get("ID") or entry.get("id") or entry.get("label") or "").strip()
                exp_label = str(entry.get("label") or "").strip()
                subject_id = str(
                    entry.get("subject_ID")
                    or entry.get("subjectid")
                    or entry.get("subject_label")
                    or ""
                ).strip()

                if exp_id and subject_id:
                    experiments.append((subject_id, exp_id, exp_label))

            if not experiments:
                self.log.info("No experiments found for project %s", project)
                return []

            # Filter by specific IDs if provided
            if experiment_ids:
                targets = {eid.strip() for eid in experiment_ids if eid.strip()}
                experiments = [exp for exp in experiments if exp[1] in targets or exp[2] in targets]

            # Apply limit
            if limit is not None and limit >= 0:
                experiments = experiments[:limit]

            if not experiments:
                self.log.info("No experiments matched selection for project %s", project)
                return []

            # Prepare options parameter
            options_param = None
            if options:
                cleaned = [opt.strip() for opt in options if opt.strip()]
                if cleaned:
                    options_param = ",".join(dict.fromkeys(cleaned))

            def _refresh_one(exp: Tuple[str, str, str]) -> Optional[str]:
                subject_id, exp_id, _label = exp
                resource_path = (
                    f"/archive/projects/{project}/subjects/{subject_id}/experiments/{exp_id}"
                )
                params: Dict[str, str] = {"resource": resource_path}
                if options_param:
                    params["options"] = options_param

                try:

                    def _do_refresh() -> None:
                        r = self.conn.post("/data/services/refresh/catalog", params=params)
                        r.raise_for_status()

                    self.conn.retry_on_network_error(_do_refresh, operation="refresh_catalog")
                    self.log.info(
                        "Refreshed catalog for experiment %s (subject %s)", exp_id, subject_id
                    )
                    return exp_id

                except Exception as e:
                    self.log.error("Failed to refresh catalog for %s: %s", exp_id, e)
                    return None

            refreshed: List[str] = []

            if parallel and len(experiments) > 1:
                worker_count = max(1, min(max_workers, len(experiments)))
                with ThreadPoolExecutor(max_workers=worker_count) as ex:
                    for result in ex.map(_refresh_one, experiments):
                        if result:
                            refreshed.append(result)
            else:
                for exp in experiments:
                    result = _refresh_one(exp)
                    if result:
                        refreshed.append(result)

            self._audit.log_operation(
                "refresh_catalogs",
                project=project,
                details={"refreshed_count": len(refreshed), "total": len(experiments)},
                user=self.conn.username,
                success=True,
            )

            return refreshed

    # =========================================================================
    # User Management
    # =========================================================================

    def add_user_to_groups(
        self,
        username: str,
        groups: List[str],
    ) -> Dict[str, Any]:
        """Add a user to XNAT groups.

        Args:
            username: XNAT username.
            groups: List of group names.

        Returns:
            Dict with 'added' (list) and 'failed' (dict of group: error).
        """
        with LogContext("add_user_to_groups", self.log, username=username):
            self.log.info("Adding user %s to %d groups", username, len(groups))

            resp = self.conn.put(
                f"/xapi/users/{quote(username)}/groups",
                json=groups,
            )

            if resp.status_code == 200:
                self.log.info("User %s added to all groups: %s", username, groups)
                self._audit.log_operation(
                    "add_user_to_groups",
                    details={"username": username, "groups": groups},
                    user=self.conn.username,
                    success=True,
                )
                return {"added": groups, "failed": {}}

            elif resp.status_code == 202:
                # Partial success
                failed_list = None
                if resp.content:
                    try:
                        result = resp.json()
                        if isinstance(result, list):
                            failed_list = result
                    except ValueError:
                        pass

                if failed_list is None:
                    failed_list = groups

                failed = {g: "failed" for g in failed_list}
                added = [g for g in groups if g not in failed]

                self.log.warning(
                    "User %s: partial success - added to %d/%d groups",
                    username,
                    len(added),
                    len(groups),
                )

                return {"added": added, "failed": failed}

            else:
                resp.raise_for_status()
                return {"added": [], "failed": {g: "unknown error" for g in groups}}

    # =========================================================================
    # Subject Renaming
    # =========================================================================

    def rename_subjects(
        self,
        project: str,
        mapping: Mapping[str, str],
        *,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Rename subjects using a mapping.

        Args:
            project: Project identifier.
            mapping: Dict of old_label -> new_label.
            dry_run: If True, only report what would be renamed.

        Returns:
            Dict with 'renamed' (dict), 'skipped' (list of tuples).
        """
        project = validate_project_id(project)

        with LogContext("rename_subjects", self.log, project=project, dry_run=dry_run):
            renamed: Dict[str, str] = {}
            skipped: List[Tuple[str, str]] = []

            for old_raw, new_raw in mapping.items():
                old = (old_raw or "").strip()
                new = (new_raw or "").strip()

                if not old or not new:
                    skipped.append((old_raw, "empty old/new label"))
                    continue

                if old == new:
                    skipped.append((old, "old and new labels match"))
                    continue

                # Check if source exists
                current = self.conn.interface.select.project(project).subject(old)
                if not current.exists():
                    skipped.append((old, "subject not found"))
                    continue

                # Check if target already exists
                target = self.conn.interface.select.project(project).subject(new)
                if target.exists():
                    skipped.append((old, f"target '{new}' already exists"))
                    continue

                if dry_run:
                    self.log.info("[DRY-RUN] Would rename %s -> %s", old, new)
                    renamed[old] = new
                    continue

                try:
                    resp = self.conn.put(
                        f"/data/projects/{project}/subjects/{quote(old)}",
                        params={"label": new},
                    )
                    resp.raise_for_status()
                    renamed[old] = new
                    self.log.info("Renamed subject %s -> %s", old, new)

                except Exception as e:
                    self.log.error("Failed to rename %s -> %s: %s", old, new, e)
                    skipped.append((old, str(e)))

            if not dry_run:
                self._audit.log_operation(
                    "rename_subjects",
                    project=project,
                    details={"renamed_count": len(renamed), "skipped_count": len(skipped)},
                    user=self.conn.username,
                    success=True,
                )

            return {"renamed": renamed, "skipped": skipped, "dry_run": dry_run}

    def rename_subjects_pattern(
        self,
        project: str,
        match_pattern: str,
        to_template: str,
        *,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Rename subjects matching a regex pattern with merge support.

        Args:
            project: Project identifier.
            match_pattern: Regex pattern with capture groups.
            to_template: Template with {1}, {2}, {project} placeholders.
            dry_run: If True, only report what would happen.

        Returns:
            Dict with 'renamed', 'merged', 'skipped' keys.
        """
        project = validate_project_id(project)
        pattern = validate_regex_pattern(match_pattern, "match_pattern")

        with LogContext(
            "rename_subjects_pattern",
            self.log,
            project=project,
            pattern=match_pattern,
            dry_run=dry_run,
        ):
            subjects = self._projects.list_subjects(project)
            self.log.info("Found %d subjects in project %s", len(subjects), project)

            current_labels = {s["label"] for s in subjects}

            renamed: Dict[str, str] = {}
            merged: Dict[str, str] = {}
            skipped: List[Tuple[str, str]] = []

            for subj in subjects:
                label = subj["label"]
                match = pattern.fullmatch(label)
                if not match:
                    continue

                # Build target name
                groups = match.groups()
                target = to_template.replace("{project}", project)
                for i, g in enumerate(groups, start=1):
                    target = target.replace(f"{{{i}}}", g or "")

                if target == label:
                    skipped.append((label, "already matches target format"))
                    continue

                target_exists = target in current_labels

                if dry_run:
                    if target_exists:
                        exps = self._projects.list_subject_experiments(project, label)
                        self.log.info(
                            "[DRY-RUN] Would MERGE %s -> %s (%d experiments)",
                            label,
                            target,
                            len(exps),
                        )
                        merged[label] = target
                    else:
                        self.log.info("[DRY-RUN] Would RENAME %s -> %s", label, target)
                        renamed[label] = target
                    continue

                # Actual execution
                if target_exists:
                    # Merge: move experiments, then delete source
                    exps = self._projects.list_subject_experiments(project, label)

                    if not exps:
                        try:
                            self._projects.delete_subject(project, label)
                            merged[label] = target
                            current_labels.discard(label)
                        except Exception as e:
                            skipped.append((label, f"failed to delete empty subject: {e}"))
                        continue

                    self.log.info(
                        "Merging %s -> %s: moving %d experiments", label, target, len(exps)
                    )
                    move_failed = False

                    for exp in exps:
                        try:
                            self._projects.move_experiment_to_subject(project, exp["ID"], target)
                        except Exception as e:
                            self.log.error("Failed to move experiment %s: %s", exp["ID"], e)
                            move_failed = True
                            break

                    if move_failed:
                        skipped.append((label, "failed to move some experiments"))
                        continue

                    try:
                        self._projects.delete_subject(project, label)
                        merged[label] = target
                        current_labels.discard(label)
                    except Exception as e:
                        self.log.warning(
                            "Experiments moved but failed to delete source %s: %s", label, e
                        )
                        merged[label] = target

                else:
                    # Simple rename
                    try:
                        resp = self.conn.put(
                            f"/data/projects/{project}/subjects/{quote(label)}",
                            params={"label": target},
                        )
                        resp.raise_for_status()
                        renamed[label] = target
                        current_labels.discard(label)
                        current_labels.add(target)
                        self.log.info("Renamed subject %s -> %s", label, target)
                    except Exception as e:
                        skipped.append((label, f"rename failed: {e}"))

            if not dry_run:
                self._audit.log_operation(
                    "rename_subjects_pattern",
                    project=project,
                    details={
                        "renamed_count": len(renamed),
                        "merged_count": len(merged),
                        "skipped_count": len(skipped),
                    },
                    user=self.conn.username,
                    success=True,
                )

            return {
                "renamed": renamed,
                "merged": merged,
                "skipped": skipped,
                "dry_run": dry_run,
            }
