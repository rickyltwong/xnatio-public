from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..config import load_config
from ..services import AdminService, XNATConnection


def register(subparsers: argparse._SubParsersAction) -> None:
    refresh_catalogs = subparsers.add_parser(
        "refresh-catalogs",
        help="Refresh catalog XMLs for experiments in a project",
    )
    refresh_catalogs.add_argument("project", help="Project ID")
    refresh_catalogs.add_argument(
        "--option",
        action="append",
        choices=["checksum", "delete", "append", "populateStats"],
        default=None,
        help=(
            "Refresh options (can be repeated). checksum: generate missing checksums; "
            "delete: remove entries without files; append: add entries for new files; "
            "populateStats: update resource stats"
        ),
    )
    refresh_catalogs.add_argument(
        "--parallel",
        action="store_true",
        help="Refresh experiments in parallel (faster for many experiments)",
    )
    refresh_catalogs.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Max worker threads when --parallel is used (default: 4)",
    )
    refresh_catalogs.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of experiments processed",
    )
    refresh_catalogs.add_argument(
        "--experiment",
        action="append",
        default=[],
        help="Experiment IDs to target (repeatable)",
    )
    refresh_catalogs.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format: text (default) or json for scripting",
    )
    refresh_catalogs.add_argument(
        "--env",
        dest="env_file",
        type=Path,
        default=None,
        help="Path to .env file that overrides environment variables",
    )
    refresh_catalogs.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    def handle_refresh_catalogs(
        args: argparse.Namespace, parser: argparse.ArgumentParser = refresh_catalogs
    ) -> int:
        cfg = load_config(args.env_file)
        conn = XNATConnection.from_config(cfg)
        admin = AdminService(conn)
        refreshed = admin.refresh_project_experiment_catalogs(
            project=args.project,
            options=args.option,
            limit=args.limit,
            experiment_ids=args.experiment,
            parallel=args.parallel,
            max_workers=args.max_workers,
        )
        if args.format == "json":
            print(
                json.dumps(
                    {
                        "project": args.project,
                        "experiments_refreshed": refreshed,
                        "count": len(refreshed),
                    }
                )
            )
        elif refreshed:
            print(f"Refreshed catalogs for {len(refreshed)} experiments:")
            for exp_id in refreshed:
                print(f"- {exp_id}")
        else:
            print("No experiments found to refresh.")
        return 0

    refresh_catalogs.set_defaults(func=handle_refresh_catalogs)

    label_fixes = subparsers.add_parser(
        "apply-label-fixes",
        help="Apply subject/experiment label fixes from a JSON config",
    )
    label_fixes.add_argument(
        "config",
        type=Path,
        help="Path to JSON config file (see docs/apply-label-fixes.md)",
    )
    label_fixes.add_argument(
        "--projects",
        default=None,
        help="Comma-separated project IDs to limit scope",
    )
    label_fixes.add_argument(
        "--subjects",
        default=None,
        help="Comma-separated subject labels to limit scope",
    )
    label_fixes.add_argument(
        "--subject-pattern",
        default=None,
        help="Regex pattern to filter subject labels",
    )
    label_fixes.add_argument(
        "--modalities",
        default=None,
        help="Comma-separated modalities to limit (e.g., MR,PET)",
    )
    label_fixes.add_argument(
        "--execute",
        action="store_true",
        help="Execute changes (default is dry-run).",
    )
    label_fixes.add_argument(
        "--env",
        dest="env_file",
        type=Path,
        default=None,
        help="Path to .env file that overrides environment variables",
    )
    label_fixes.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    def handle_apply_label_fixes(
        args: argparse.Namespace, parser: argparse.ArgumentParser = label_fixes
    ) -> int:
        config_path: Path = args.config
        if not config_path.exists():
            parser.error(f"Config file not found: {config_path}")

        cfg = load_config(args.env_file)
        conn = XNATConnection.from_config(cfg)

        from ..label_fixes import apply_label_fixes

        result = apply_label_fixes(
            conn,
            config_path,
            projects=args.projects,
            subjects=args.subjects,
            subject_pattern=args.subject_pattern,
            modalities=args.modalities,
            execute=args.execute,
            verbose=args.verbose,
        )
        return 1 if result["failed"] else 0

    label_fixes.set_defaults(func=handle_apply_label_fixes)
