from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..config import load_config
from ..services import AdminService, ProjectService, ScanService, XNATConnection


def _load_mapping(mapping_arg: str) -> dict[str, str]:
    """Load a JSON mapping from an inline string or a file path."""
    path = Path(mapping_arg)
    raw = path.read_text() if path.exists() else mapping_arg
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("mapping JSON must be an object of {old: new}")
    mapping: dict[str, str] = {}
    for old, new in data.items():
        if not isinstance(old, str) or not isinstance(new, str):
            raise ValueError("mapping keys and values must be strings")
        mapping[old] = new
    return mapping


def register(subparsers: argparse._SubParsersAction) -> None:
    create_proj = subparsers.add_parser(
        "create-project",
        help="Create a new XNAT project via REST API",
    )
    create_proj.add_argument("project_id", help="Project ID (used for ID, secondary_ID, and name)")
    create_proj.add_argument(
        "--description",
        default=None,
        help="Optional project description",
    )
    create_proj.add_argument(
        "--env",
        dest="env_file",
        type=Path,
        default=None,
        help="Path to .env file that overrides environment variables",
    )
    create_proj.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    def handle_create_project(
        args: argparse.Namespace, parser: argparse.ArgumentParser = create_proj
    ) -> int:
        cfg = load_config(args.env_file)
        conn = XNATConnection.from_config(cfg)
        projects = ProjectService(conn)
        projects.create_project(args.project_id, description=args.description)
        return 0

    create_proj.set_defaults(func=handle_create_project)

    delete_scans = subparsers.add_parser(
        "delete-scans",
        help="Delete scan files for a given project, subject, and session",
    )
    delete_scans.add_argument("project", help="Project ID")
    delete_scans.add_argument("subject", help="Subject ID")
    delete_scans.add_argument("session", help="Session/experiment ID")
    delete_scans.add_argument(
        "--scan",
        required=True,
        help=(
            "Scan IDs to delete: use '*' to delete all scans, or "
            "comma-separated list like '1,2,3,4,6' for specific scans"
        ),
    )
    delete_scans.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be deleted without making changes",
    )
    delete_scans.add_argument(
        "--confirm",
        action="store_true",
        help="Skip confirmation prompt (required for deletion)",
    )
    delete_scans.add_argument(
        "--parallel",
        action="store_true",
        help="Delete scans in parallel (faster for many scans)",
    )
    delete_scans.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Max worker threads when --parallel is used (default: 4)",
    )
    delete_scans.add_argument(
        "--env",
        dest="env_file",
        type=Path,
        default=None,
        help="Path to .env file that overrides environment variables",
    )
    delete_scans.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    def handle_delete_scans(
        args: argparse.Namespace, parser: argparse.ArgumentParser = delete_scans
    ) -> int:
        cfg = load_config(args.env_file)

        scan_ids_to_delete = args.scan
        if scan_ids_to_delete == "*":
            scan_ids = None
            scan_description = "ALL scans"
        else:
            scan_ids = [s.strip() for s in scan_ids_to_delete.split(",")]
            scan_description = f"scans {', '.join(scan_ids)}"

        # Use new service for dry-run support
        conn = XNATConnection.from_config(cfg)
        scans_svc = ScanService(conn)

        if args.dry_run:
            result = scans_svc.delete_scans(
                project=args.project,
                subject=args.subject,
                session=args.session,
                scan_ids=scan_ids,
                dry_run=True,
            )
            deleted = result.get("deleted", [])
            if deleted:
                print(f"[DRY-RUN] Would delete {len(deleted)} scans:")
                print("  Scan IDs:", ", ".join(deleted))
            else:
                print("[DRY-RUN] No scans would be deleted.")
            return 0

        if not args.confirm:
            print(f"WARNING: This will permanently delete {scan_description} for:")
            print(f"  Project: {args.project}")
            print(f"  Subject: {args.subject}")
            print(f"  Session: {args.session}")
            print()
            print("This action cannot be undone!")
            print("  Tip: Use --dry-run to preview changes first.")
            print()
            response = input("Type 'DELETE' to confirm, or anything else to cancel: ")
            if response != "DELETE":
                print("Operation cancelled.")
                return 1

        result = scans_svc.delete_scans(
            project=args.project,
            subject=args.subject,
            session=args.session,
            scan_ids=scan_ids,
            parallel=args.parallel,
            max_workers=args.max_workers,
        )

        deleted = result.get("deleted", [])
        failed = result.get("failed", {})

        if deleted:
            print(f"Deletion complete. Removed {len(deleted)} scans.")
            print("Deleted scan IDs:", ", ".join(deleted))

        if failed:
            print(f"Failed to delete {len(failed)} scans:")
            for scan_id, error in failed.items():
                print(f"  {scan_id}: {error}")
            return 1

        if not deleted:
            print("No scans were deleted.")

        return 0

    delete_scans.set_defaults(func=handle_delete_scans)

    list_scans = subparsers.add_parser(
        "list-scans",
        help="List scan IDs for a given project, subject, and session",
    )
    list_scans.add_argument("project", help="Project ID")
    list_scans.add_argument("subject", help="Subject ID")
    list_scans.add_argument("session", help="Session/experiment ID")
    list_scans.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format: text (default) or json for scripting",
    )
    list_scans.add_argument(
        "--env",
        dest="env_file",
        type=Path,
        default=None,
        help="Path to .env file that overrides environment variables",
    )
    list_scans.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    def handle_list_scans(
        args: argparse.Namespace, parser: argparse.ArgumentParser = list_scans
    ) -> int:
        cfg = load_config(args.env_file)
        conn = XNATConnection.from_config(cfg)
        scans = ScanService(conn)
        ids = scans.list_scans(args.project, args.subject, args.session)
        if args.format == "json":
            print(json.dumps({"scan_ids": ids, "count": len(ids)}))
        elif ids:
            print("\n".join(ids))
        return 0

    list_scans.set_defaults(func=handle_list_scans)

    rename_subj = subparsers.add_parser(
        "rename-subjects",
        help="Batch rename subjects using a JSON mapping of old:new labels",
    )
    rename_subj.add_argument("project", help="Project ID")
    rename_subj.add_argument(
        "mapping",
        help="JSON object or path to JSON file mapping old subject labels to new labels",
    )
    rename_subj.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be renamed without making changes",
    )
    rename_subj.add_argument(
        "--env",
        dest="env_file",
        type=Path,
        default=None,
        help="Path to .env file that overrides environment variables",
    )
    rename_subj.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    def handle_rename_subjects(
        args: argparse.Namespace, parser: argparse.ArgumentParser = rename_subj
    ) -> int:
        try:
            mapping = _load_mapping(args.mapping)
        except Exception as exc:
            parser.error(f"Invalid mapping JSON: {exc}")

        cfg = load_config(args.env_file)
        conn = XNATConnection.from_config(cfg)
        admin_svc = AdminService(conn)

        result = admin_svc.rename_subjects(
            project=args.project,
            mapping=mapping,
            dry_run=args.dry_run,
        )

        renamed = result.get("renamed", {})
        skipped = result.get("skipped", [])
        prefix = "[DRY-RUN] " if args.dry_run else ""

        if renamed:
            print(f"{prefix}Renamed subjects:")
            for old, new in renamed.items():
                print(f"  {old} -> {new}")

        if skipped:
            print(f"{prefix}Skipped subjects:")
            for label, reason in skipped:
                print(f"  {label}: {reason}")

        if not renamed and not skipped:
            print(f"{prefix}No subjects matched the mapping.")
        elif renamed:
            print(f"\n{prefix}Summary: {len(renamed)} renamed, {len(skipped)} skipped")

        return 0

    rename_subj.set_defaults(func=handle_rename_subjects)

    rename_pat = subparsers.add_parser(
        "rename-subjects-pattern",
        help="Rename subjects matching a regex pattern with merge support for duplicates",
    )
    rename_pat.add_argument("project", help="Project ID")
    rename_pat.add_argument(
        "--match",
        required=True,
        help="Regex pattern for matching subject labels (use capture groups)",
    )
    rename_pat.add_argument(
        "--to",
        dest="to_template",
        required=True,
        help="Replacement template, supports {project} and regex groups (e.g., {1})",
    )
    rename_pat.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them",
    )
    rename_pat.add_argument(
        "--env",
        dest="env_file",
        type=Path,
        default=None,
        help="Path to .env file that overrides environment variables",
    )
    rename_pat.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    def handle_rename_subjects_pattern(
        args: argparse.Namespace, parser: argparse.ArgumentParser = rename_pat
    ) -> int:
        cfg = load_config(args.env_file)
        conn = XNATConnection.from_config(cfg)
        admin_svc = AdminService(conn)

        try:
            result = admin_svc.rename_subjects_pattern(
                project=args.project,
                match_pattern=args.match,
                to_template=args.to_template,
                dry_run=args.dry_run,
            )
        except ValueError as exc:
            parser.error(str(exc))

        renamed = result.get("renamed", {})
        merged = result.get("merged", {})
        skipped = result.get("skipped", [])

        prefix = "[DRY-RUN] " if args.dry_run else ""

        if renamed:
            print(f"{prefix}Renamed subjects:")
            for old, new in renamed.items():
                print(f"  {old} -> {new}")

        if merged:
            print(f"{prefix}Merged subjects (experiments moved to existing target):")
            for old, new in merged.items():
                print(f"  {old} -> {new}")

        if skipped:
            print(f"{prefix}Skipped subjects:")
            for label, reason in skipped:
                print(f"  {label}: {reason}")

        total = len(renamed) + len(merged)
        if total == 0 and not skipped:
            print(f"{prefix}No subjects matched the pattern.")
        else:
            summary = (
                f"\n{prefix}Summary: {len(renamed)} renamed, "
                f"{len(merged)} merged, {len(skipped)} skipped"
            )
            print(summary)

        return 0

    rename_pat.set_defaults(func=handle_rename_subjects_pattern)

    add_user = subparsers.add_parser(
        "add-user-to-groups",
        help="Add a user to XNAT project groups with role-based access",
    )
    add_user.add_argument("username", help="XNAT username to add")
    add_user.add_argument(
        "groups",
        nargs="*",
        help="Explicit group names (comma-separated lists allowed)",
    )
    add_user.add_argument(
        "--projects",
        default=None,
        help="Comma-separated project IDs to build groups automatically",
    )
    add_user.add_argument(
        "--role",
        default="member",
        help="Role name used with --projects (default: member)",
    )
    add_user.add_argument(
        "--site",
        default=None,
        help="Site suffix used with --projects (e.g., SITE1)",
    )
    add_user.add_argument(
        "--env",
        dest="env_file",
        type=Path,
        default=None,
        help="Path to .env file that overrides environment variables",
    )
    add_user.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    def handle_add_user_to_groups(
        args: argparse.Namespace, parser: argparse.ArgumentParser = add_user
    ) -> int:
        cfg = load_config(args.env_file)
        conn = XNATConnection.from_config(cfg)
        admin = AdminService(conn)

        groups = []
        if args.groups:
            for entry in args.groups:
                groups.extend([g.strip() for g in entry.split(",") if g.strip()])
        if args.projects:
            project_ids = [p.strip() for p in args.projects.split(",") if p.strip()]
            for proj in project_ids:
                groups.append(f"{proj}_{args.site}_{args.role}")

        if not groups:
            parser.error("No groups specified. Provide group names or use --projects with --role.")

        result = admin.add_user_to_groups(
            username=args.username,
            groups=groups,
        )
        added = result.get("added", [])
        failed = result.get("failed", {})

        if added:
            print(f"User {args.username} added to groups:")
            for g in added:
                print(f"  - {g}")
        if failed:
            print("Failed to add user to groups:")
            for g, err in failed.items():
                print(f"  - {g}: {err}")
        return 0 if not failed else 1

    add_user.set_defaults(func=handle_add_user_to_groups)
