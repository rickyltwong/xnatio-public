"""
Label fixes for subjects and experiments.

This module provides functions to:
1. Rename subjects based on regex patterns (from config JSON)
2. Fix experiment labels to standard convention: {SUBJECT}_{VISIT}_{SESSION}_{MODALITY}
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, time
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Sequence

if TYPE_CHECKING:
    from .xnat_client import XNATClient

log = logging.getLogger(__name__)

# XSI type to modality code mapping
XSI_MODALITY_MAP = {
    "xnat:mrsessiondata": "MR",
    "xnat:petsessiondata": "PET",
    "xnat:ctsessiondata": "CT",
    "xnat:crsessiondata": "CR",
    "xnat:dxsessiondata": "DX",
    "xnat:dx3dsessiondata": "DX3D",
    "xnat:mgsessiondata": "MG",
    "xnat:nmsessiondata": "NM",
    "xnat:ussessiondata": "US",
    "xnat:megsessiondata": "MEG",
    "xnat:eegsessiondata": "EEG",
}

DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d")
TIME_FORMATS = ("%H:%M:%S", "%H:%M")
DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y/%m/%d %H:%M:%S",
)


def load_patterns_config(config_path: Path) -> dict:
    """
    Load patterns configuration from JSON file.

    Expected format:
    {
        "patterns": [
            {
                "project": "MYPROJECT",
                "match": "^(ABC\\d{3})$",
                "to": "{project}_00{1}",
                "description": "Optional description"
            }
        ]
    }
    """
    with open(config_path) as f:
        return json.load(f)


def _parse_datetime(value: str) -> Optional[datetime]:
    """Parse datetime from various formats."""
    if not value:
        return None
    for fmt in DATETIME_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _parse_date(value: str) -> Optional[date]:
    """Parse date from various formats."""
    if not value:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    dt = _parse_datetime(value)
    return dt.date() if dt else None


def _parse_time(value: str) -> Optional[time]:
    """Parse time from various formats."""
    if not value:
        return None
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    dt = _parse_datetime(value)
    return dt.time() if dt else None


def _modality_from_xsi(xsi_type: str) -> Optional[str]:
    """Convert XSI type to modality code."""
    key = (xsi_type or "").strip().lower()
    return XSI_MODALITY_MAP.get(key)


def _build_target_label(
    subject_label: str,
    visit_index: int,
    session_index: int,
    modality: str,
) -> str:
    """Build standardized experiment label."""
    return f"{subject_label}_{visit_index:02d}_SE{session_index:02d}_{modality}"


def apply_subject_patterns(
    client: "XNATClient",
    project: str,
    patterns: list[dict],
    *,
    execute: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Apply subject rename patterns to a project.

    Parameters
    ----------
    client : XNATClient
        Authenticated XNAT client
    project : str
        Project ID
    patterns : list[dict]
        List of pattern dicts with 'match' and 'to' keys
    execute : bool
        If True, apply changes. If False, dry-run only.
    verbose : bool
        Show skipped subjects in output

    Returns
    -------
    dict
        Results with keys: renamed, merged, skipped, errors
    """
    if not patterns:
        log.info(f"No subject rename patterns for project {project}")
        return {"renamed": 0, "merged": 0, "skipped": 0, "errors": 0}

    dry_run = not execute
    mode = "DRY-RUN" if dry_run else "EXECUTE"

    log.info("=" * 60)
    log.info(f"Subject rename: {mode}")
    log.info(f"Project: {project}")
    log.info(f"Patterns: {len(patterns)}")
    log.info("=" * 60)

    total_renamed = 0
    total_merged = 0
    total_skipped = 0
    total_errors = 0

    for pattern in patterns:
        match = pattern.get("match")
        to = pattern.get("to")
        desc = pattern.get("description", "")

        if not match or not to:
            log.warning("Invalid pattern entry (missing match/to); skipping.")
            total_errors += 1
            continue

        log.info("-" * 60)
        log.info(f"Pattern: {match}")
        log.info(f"To:      {to}")
        if desc:
            log.info(f"         ({desc})")

        try:
            result = client.rename_subjects_pattern(
                project=project,
                match_pattern=match,
                to_template=to,
                dry_run=dry_run,
            )
        except Exception as exc:
            log.error(f"Error processing pattern {match}: {exc}")
            total_errors += 1
            continue

        renamed = result.get("renamed", {})
        merged = result.get("merged", {})
        skipped = result.get("skipped", [])

        if renamed:
            log.info(f"Renamed ({len(renamed)}):")
            for old, new in renamed.items():
                log.info(f"  {old} -> {new}")

        if merged:
            log.info(f"Merged ({len(merged)}):")
            for old, new in merged.items():
                log.info(f"  {old} -> {new}")

        if skipped and verbose:
            log.info(f"Skipped ({len(skipped)}):")
            for label, reason in skipped:
                log.info(f"  {label}: {reason}")

        total_renamed += len(renamed)
        total_merged += len(merged)
        total_skipped += len(skipped)

        if not renamed and not merged:
            log.info("No subjects matched this pattern.")

    log.info("=" * 60)
    log.info(
        f"Subject summary: {total_renamed} renamed, {total_merged} merged, {total_skipped} skipped"
    )
    if dry_run:
        log.info("This was a DRY-RUN. Use --execute to apply changes.")
    log.info("=" * 60)

    return {
        "renamed": total_renamed,
        "merged": total_merged,
        "skipped": total_skipped,
        "errors": total_errors,
    }


def apply_experiment_label_fixes(
    client: "XNATClient",
    project: str,
    *,
    subjects: Optional[Sequence[str]] = None,
    subject_pattern: Optional[str] = None,
    modalities: Optional[Sequence[str]] = None,
    execute: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Fix experiment labels to standard convention.

    Target format: {SUBJECT_LABEL}_{VISIT:02d}_SE{SESSION:02d}_{MODALITY}

    Parameters
    ----------
    client : XNATClient
        Authenticated XNAT client
    project : str
        Project ID
    subjects : list[str] | None
        Limit to specific subject labels
    subject_pattern : str | None
        Regex to filter subject labels
    modalities : list[str] | None
        Limit to specific modalities (default: ["MR"])
    execute : bool
        If True, apply changes. If False, dry-run only.
    verbose : bool
        Show skipped experiments in output

    Returns
    -------
    dict
        Results with keys: renamed, skipped, failed, skipped_subjects
    """
    if modalities is None:
        modalities = ["MR"]
    modalities_set = set(m.upper() for m in modalities)

    dry_run = not execute
    mode = "DRY-RUN" if dry_run else "EXECUTE"

    log.info("=" * 60)
    log.info(f"Experiment label fixes: {mode}")
    log.info(f"Project: {project}")
    log.info(f"Modalities: {', '.join(sorted(modalities_set))}")
    if subjects:
        log.info(f"Subject filter: {', '.join(subjects)}")
    if subject_pattern:
        log.info(f"Subject pattern: {subject_pattern}")
    log.info("=" * 60)

    subject_re = re.compile(subject_pattern) if subject_pattern else None
    subjects_data = client.list_subjects(project)
    subject_labels = [s["label"] for s in subjects_data]

    if subjects:
        wanted = set(subjects)
        subject_labels = [s for s in subject_labels if s in wanted]

    if subject_re:
        subject_labels = [s for s in subject_labels if subject_re.search(s)]

    total_renamed = 0
    total_skipped = 0
    skipped_subjects = 0
    total_failed = 0

    prefix = f"{project}_"

    for subj_label in subject_labels:
        # Check subject has project prefix
        if not subj_label.startswith(prefix):
            if verbose:
                log.info(f"Skipping subject {subj_label}: not normalized to project prefix")
            skipped_subjects += 1
            continue

        experiments = client.list_subject_experiments_detailed(project, subj_label)
        if not experiments:
            continue

        existing_labels = {e.get("label", "") for e in experiments if e.get("label")}
        by_date: dict[date, list[dict]] = {}
        skipped: list[tuple[str, str, str]] = []

        for exp in experiments:
            exp_id = exp.get("ID", "")
            exp_label = exp.get("label", "")
            modality = _modality_from_xsi(exp.get("xsiType", ""))

            if not modality:
                skipped.append((exp_id, exp_label, "unknown modality from xsiType"))
                continue

            if modality not in modalities_set:
                skipped.append((exp_id, exp_label, f"modality {modality} not in filter"))
                continue

            session_date = _parse_date(exp.get("date", ""))
            if not session_date:
                skipped.append((exp_id, exp_label, "missing session date"))
                continue

            session_time = _parse_time(exp.get("time", ""))
            insert_dt = _parse_datetime(exp.get("insert_date", ""))
            if not insert_dt:
                insert_date = _parse_date(exp.get("insert_date", ""))
                insert_time = _parse_time(exp.get("insert_time", ""))
                if insert_date and insert_time:
                    insert_dt = datetime.combine(insert_date, insert_time)

            order_time = session_time or (insert_dt.time() if insert_dt else None)
            by_date.setdefault(session_date, []).append(
                {
                    "ID": exp_id,
                    "label": exp_label,
                    "modality": modality,
                    "order_time": order_time,
                    "insert_dt": insert_dt,
                }
            )

        rename_plan: list[tuple[str, str, str]] = []
        seen_targets: dict[str, str] = {}

        for visit_idx, session_date in enumerate(sorted(by_date.keys()), start=1):
            group = by_date[session_date]

            # Check if we can determine order for same-day experiments
            if len(group) > 1 and any(g["order_time"] is None for g in group):
                for g in group:
                    skipped.append(
                        (
                            g["ID"],
                            g["label"],
                            "missing time for same-day experiments; cannot assign SE order",
                        )
                    )
                continue

            group_sorted = sorted(
                group,
                key=lambda g: (
                    g["order_time"] or time.min,
                    g["insert_dt"] or datetime.min,
                    g["label"],
                    g["ID"],
                ),
            )

            for session_idx, g in enumerate(group_sorted, start=1):
                target = _build_target_label(subj_label, visit_idx, session_idx, g["modality"])

                if target == g["label"]:
                    continue

                if target in existing_labels and target != g["label"]:
                    skipped.append((g["ID"], g["label"], f"target label exists: {target}"))
                    continue

                prior = seen_targets.get(target)
                if prior and prior != g["ID"]:
                    skipped.append((g["ID"], g["label"], f"target label conflict: {target}"))
                    continue

                seen_targets[target] = g["ID"]
                rename_plan.append((g["ID"], g["label"], target))

        if rename_plan:
            log.info(f"Subject: {subj_label}")
            log.info(f"Renames ({len(rename_plan)}):")
            for exp_id, old_label, new_label in rename_plan:
                log.info(f"  {exp_id} {old_label} -> {new_label}")

        if skipped and verbose:
            log.info(f"Skipped ({len(skipped)}):")
            for exp_id, old_label, reason in skipped:
                log.info(f"  {exp_id} {old_label}: {reason}")

        if execute:
            for exp_id, old_label, new_label in rename_plan:
                try:
                    client.rename_experiment(project, exp_id, new_label)
                    total_renamed += 1
                except Exception as exc:
                    total_failed += 1
                    log.error(f"Failed to rename {exp_id} ({old_label}) -> {new_label}: {exc}")
        else:
            total_renamed += len(rename_plan)

        total_skipped += len(skipped)

    log.info("=" * 60)
    log.info(f"Experiment summary: {total_renamed} planned/renamed, {total_skipped} skipped")
    if skipped_subjects:
        log.info(f"Skipped subjects (not normalized): {skipped_subjects}")
    if execute and total_failed:
        log.error(f"FAILED: {total_failed} renames")
    if not execute:
        log.info("This was a DRY-RUN. Use --execute to apply changes.")
    log.info("=" * 60)

    return {
        "renamed": total_renamed,
        "skipped": total_skipped,
        "failed": total_failed,
        "skipped_subjects": skipped_subjects,
    }


def apply_label_fixes(
    client: "XNATClient",
    config_path: Path,
    *,
    projects: Optional[Sequence[str]] = None,
    subjects: Optional[Sequence[str]] = None,
    subject_pattern: Optional[str] = None,
    modalities: Optional[Sequence[str]] = None,
    execute: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Apply both subject and experiment label fixes from config.

    This is the main entry point for scheduled/automated runs.

    Parameters
    ----------
    client : XNATClient
        Authenticated XNAT client
    config_path : Path
        Path to patterns JSON config file
    projects : list[str] | None
        Limit to specific projects (default: all projects in config)
    subjects : list[str] | None
        Limit experiment fixes to specific subject labels
    subject_pattern : str | None
        Regex to filter subject labels for experiment fixes
    modalities : list[str] | None
        Modalities for experiment fixes (default: ["MR"])
    execute : bool
        If True, apply changes. If False, dry-run only.
    verbose : bool
        Show skipped items in output

    Returns
    -------
    dict
        Combined results with keys: subject_results, experiment_results, failed
    """
    config = load_patterns_config(config_path)
    patterns = config.get("patterns", [])

    # Determine projects to process
    if projects:
        project_ids = list(projects)
    else:
        project_ids = sorted({p.get("project") for p in patterns if p.get("project")})

    if not project_ids:
        log.error("No projects found in config. Provide --project explicitly.")
        return {"subject_results": {}, "experiment_results": {}, "failed": True}

    log.info(f"Processing {len(project_ids)} project(s): {', '.join(project_ids)}")

    overall_failed = False
    subject_results = {}
    experiment_results = {}

    for project_id in project_ids:
        log.info(f"\n{'#' * 60}")
        log.info(f"# PROJECT: {project_id}")
        log.info(f"{'#' * 60}\n")

        # Step 1: Apply subject patterns
        project_patterns = [p for p in patterns if p.get("project") == project_id]
        subj_result = apply_subject_patterns(
            client,
            project_id,
            project_patterns,
            execute=execute,
            verbose=verbose,
        )
        subject_results[project_id] = subj_result

        if subj_result["errors"]:
            log.error("Subject step had errors; skipping experiment step for this project.")
            overall_failed = True
            continue

        # Step 2: Apply experiment label fixes
        exp_result = apply_experiment_label_fixes(
            client,
            project_id,
            subjects=subjects,
            subject_pattern=subject_pattern,
            modalities=modalities,
            execute=execute,
            verbose=verbose,
        )
        experiment_results[project_id] = exp_result

        if exp_result["failed"]:
            overall_failed = True

    # Final summary
    log.info(f"\n{'=' * 60}")
    log.info("FINAL SUMMARY")
    log.info("=" * 60)

    for project_id in project_ids:
        subj = subject_results.get(project_id, {})
        exp = experiment_results.get(project_id, {})
        log.info(
            f"{project_id}: subjects({subj.get('renamed', 0)} renamed, "
            f"{subj.get('merged', 0)} merged) | "
            f"experiments({exp.get('renamed', 0)} renamed)"
        )

    if not execute:
        log.info("\nThis was a DRY-RUN. Use --execute to apply changes.")

    return {
        "subject_results": subject_results,
        "experiment_results": experiment_results,
        "failed": overall_failed,
    }
