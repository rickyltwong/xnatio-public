from __future__ import annotations

import argparse
import logging
import zipfile
from pathlib import Path

from ..config import load_config
from ..services import DownloadService, XNATConnection


def register(subparsers: argparse._SubParsersAction) -> None:
    dl = subparsers.add_parser(
        "download-session",
        help="Download scans and resources for a session as ZIPs",
    )
    dl.add_argument("project", help="Project ID")
    dl.add_argument("subject", help="Subject ID")
    dl.add_argument("session", help="Session/experiment ID")
    dl.add_argument("output", type=Path, help="Output directory")
    dl.add_argument(
        "--env",
        dest="env_file",
        type=Path,
        default=None,
        help="Path to .env file that overrides environment variables",
    )
    dl.add_argument(
        "--include-assessors",
        action="store_true",
        help="Also download assessor resources",
    )
    dl.add_argument(
        "--include-recons",
        action="store_true",
        help="Also download reconstruction resources",
    )
    dl.add_argument(
        "--unzip",
        action="store_true",
        help="Extract downloaded ZIPs into folders and remove the ZIP files",
    )
    dl.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    def handle_download_session(
        args: argparse.Namespace, parser: argparse.ArgumentParser = dl
    ) -> int:
        cfg = load_config(args.env_file)
        conn = XNATConnection.from_config(cfg)
        downloads = DownloadService(conn)
        out_dir: Path = args.output
        downloads.download_session(
            project=args.project,
            subject=args.subject,
            session=args.session,
            output_dir=out_dir,
            include_assessors=args.include_assessors,
            include_recons=args.include_recons,
        )
        if args.unzip:
            session_dir = out_dir / args.session
            downloads.extract_session_downloads(session_dir)
            for zip_path in session_dir.glob("*.zip"):
                try:
                    zip_path.unlink()
                except Exception:
                    logging.getLogger(__name__).warning(f"Failed to remove {zip_path}")
        return 0

    dl.set_defaults(func=handle_download_session)

    ex = subparsers.add_parser(
        "extract-session",
        help="Extract all zips in a session directory into scans/ and resources/<label>/",
    )
    ex.add_argument("session_dir", type=Path, help="Session directory containing downloaded ZIPs")
    ex.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    def handle_extract_session(
        args: argparse.Namespace, parser: argparse.ArgumentParser = ex
    ) -> int:
        session_dir = args.session_dir
        if not session_dir.exists() or not session_dir.is_dir():
            parser.error(f"Session directory not found: {session_dir}")

        for zip_path in sorted(session_dir.glob("*.zip")):
            name = zip_path.name
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
            logging.getLogger(__name__).info(f"Extracting {name} -> {target_dir}")
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(target_dir)
            logging.getLogger(__name__).info(f"Extracted {name}")
        return 0

    ex.set_defaults(func=handle_extract_session)
