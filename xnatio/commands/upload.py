from __future__ import annotations

import argparse
import logging
from pathlib import Path
from urllib.parse import urlparse

from ..config import load_config
from ..core import is_allowed_archive
from ..services import UploadService, XNATConnection
from ..uploaders.constants import (
    DEFAULT_ARCHIVE_FORMAT,
    DEFAULT_ARCHIVE_WORKERS,
    DEFAULT_DICOM_CALLING_AET,
    DEFAULT_DICOM_STORE_BATCHES,
    DEFAULT_NUM_BATCHES,
    DEFAULT_UPLOAD_WORKERS,
)


def register(subparsers: argparse._SubParsersAction) -> None:
    upload = subparsers.add_parser(
        "upload-dicom",
        help="Upload a DICOM session via REST import or DICOM C-STORE",
    )
    upload.add_argument("project", help="Project ID")
    upload.add_argument("subject", help="Subject ID")
    upload.add_argument("session", help="Session/experiment ID")
    upload.add_argument(
        "input",
        type=Path,
        help="Path to ZIP/TAR(.gz)/TGZ archive or a directory of DICOM files",
    )
    upload.add_argument(
        "--transport",
        choices=["rest", "dicom-store"],
        default="rest",
        help="Upload transport: rest (parallel direct-archive) or dicom-store (C-STORE)",
    )
    upload.add_argument(
        "--env",
        dest="env_file",
        type=Path,
        default=None,
        help="Path to .env file that overrides environment variables",
    )
    upload.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    rest_opts = upload.add_argument_group("REST (parallel) options")
    rest_opts.add_argument(
        "--batches",
        type=int,
        default=DEFAULT_NUM_BATCHES,
        help="Number of archive batches for parallel upload (default: %(default)s)",
    )
    rest_opts.add_argument(
        "--upload-workers",
        type=int,
        default=DEFAULT_UPLOAD_WORKERS,
        help="Max parallel upload workers (default: %(default)s)",
    )
    rest_opts.add_argument(
        "--archive-workers",
        type=int,
        default=DEFAULT_ARCHIVE_WORKERS,
        help="Max parallel archive creation workers (default: %(default)s)",
    )
    rest_opts.add_argument(
        "--archive-format",
        choices=["tar", "zip"],
        default=DEFAULT_ARCHIVE_FORMAT,
        help="Archive format for REST upload (default: %(default)s)",
    )
    rest_opts.add_argument(
        "--overwrite",
        choices=["none", "append", "delete"],
        default="delete",
        help="Overwrite mode for import service (default: %(default)s)",
    )
    rest_opts.add_argument(
        "--direct-archive",
        dest="direct_archive",
        action="store_true",
        default=True,
        help="Enable Direct-Archive mode (default)",
    )
    rest_opts.add_argument(
        "--no-direct-archive",
        dest="direct_archive",
        action="store_false",
        help="Disable Direct-Archive mode",
    )
    rest_opts.add_argument(
        "--ignore-unparsable",
        dest="ignore_unparsable",
        action="store_true",
        default=True,
        help="Ignore non-DICOM files in archives (default)",
    )
    rest_opts.add_argument(
        "--no-ignore-unparsable",
        dest="ignore_unparsable",
        action="store_false",
        help="Fail on non-DICOM files in archives",
    )

    dicom_opts = upload.add_argument_group("DICOM store (C-STORE) options")
    dicom_opts.add_argument(
        "--dicom-host",
        help="DICOM SCP hostname or IP (or XNAT_DICOM_HOST)",
    )
    dicom_opts.add_argument(
        "--dicom-port",
        type=int,
        help="DICOM SCP port (or XNAT_DICOM_PORT)",
    )
    dicom_opts.add_argument(
        "--dicom-called-aet",
        help="Called AE Title for SCP (or XNAT_DICOM_CALLED_AET)",
    )
    dicom_opts.add_argument(
        "--dicom-calling-aet",
        default=None,
        help=f"Calling AE Title (default: {DEFAULT_DICOM_CALLING_AET})",
    )
    dicom_opts.add_argument(
        "--dicom-batches",
        type=int,
        default=DEFAULT_DICOM_STORE_BATCHES,
        help="Number of parallel C-STORE batches (default: %(default)s)",
    )
    dicom_opts.add_argument(
        "--dicom-cleanup",
        action="store_true",
        help="Delete temporary DICOM send workspace after completion",
    )

    def handle_upload_dicom(
        args: argparse.Namespace, parser: argparse.ArgumentParser = upload
    ) -> int:
        inp: Path = args.input
        log = logging.getLogger(__name__)

        if args.transport == "dicom-store":
            from ..uploaders.dicom_store import send_dicom_store

            cfg = load_config(args.env_file, require_credentials=False)

            if not inp.exists() or not inp.is_dir():
                parser.error("dicom-store transport requires a directory input")

            host = args.dicom_host or cfg.get("dicom_host")
            if not host and cfg.get("server"):
                host = urlparse(str(cfg["server"])).hostname
                if host:
                    log.info("Using DICOM host derived from XNAT_SERVER: %s", host)

            port = args.dicom_port or cfg.get("dicom_port")
            called_aet = args.dicom_called_aet or cfg.get("dicom_called_aet")
            calling_aet = (
                args.dicom_calling_aet or cfg.get("dicom_calling_aet") or DEFAULT_DICOM_CALLING_AET
            )

            if not host:
                parser.error("Missing DICOM host (use --dicom-host or XNAT_DICOM_HOST)")
            if not port:
                parser.error("Missing DICOM port (use --dicom-port or XNAT_DICOM_PORT)")
            if not called_aet:
                parser.error(
                    "Missing DICOM called AET (use --dicom-called-aet or XNAT_DICOM_CALLED_AET)"
                )

            try:
                summary = send_dicom_store(
                    dicom_root=inp,
                    host=str(host),
                    port=int(port),
                    called_aet=str(called_aet),
                    calling_aet=str(calling_aet),
                    batches=args.dicom_batches,
                    cleanup=args.dicom_cleanup,
                    logger=log,
                )
            except Exception as exc:
                log.error("DICOM store upload failed: %s", exc)
                return 1

            log.info(
                "DICOM store complete: %s total, %s sent, %s failed",
                summary.total_files,
                summary.sent,
                summary.failed,
            )
            if not args.dicom_cleanup:
                log.info("DICOM store logs: %s", summary.log_dir)
                log.info("Workspace: %s", summary.workspace)

            return 0 if summary.success else 1

        from ..uploaders.parallel_rest import upload_dicom_parallel_rest

        cfg = load_config(args.env_file)

        if inp.is_dir():

            def progress_logger(progress) -> None:
                if not args.verbose:
                    return
                log.info("[%s] %s", progress.phase, progress.message)

            summary = upload_dicom_parallel_rest(
                server=str(cfg["server"]),
                username=str(cfg["user"]),
                password=str(cfg["password"]),
                verify_tls=bool(cfg.get("verify_tls", True)),
                source_dir=inp,
                project=args.project,
                subject=args.subject,
                session=args.session,
                num_batches=args.batches,
                upload_workers=args.upload_workers,
                archive_workers=args.archive_workers,
                archive_format=args.archive_format,
                ignore_unparsable=args.ignore_unparsable,
                overwrite=args.overwrite,
                direct_archive=args.direct_archive,
                progress_callback=progress_logger,
                logger=log,
            )

            log.info(
                "REST upload complete: %s files, %.1f MB, %ss",
                summary.total_files,
                summary.total_size_mb,
                int(summary.duration),
            )
            if summary.errors:
                for error in summary.errors[:5]:
                    log.error("Upload error: %s", error)
                if len(summary.errors) > 5:
                    log.error("... and %s more errors", len(summary.errors) - 5)

            return 0 if summary.success else 1

        if inp.is_file():
            if not is_allowed_archive(inp):
                parser.error(
                    "Unsupported archive type. Accepted: .zip, .tar, .tar.gz, .tgz "
                    "(or pass a directory)"
                )
            conn = XNATConnection.from_config(cfg)
            uploads = UploadService(conn)
            uploads.upload_dicom_zip(
                inp,
                project=args.project,
                subject=args.subject,
                session=args.session,
                import_handler="DICOM-zip",
                ignore_unparsable=args.ignore_unparsable,
                overwrite=args.overwrite,
                direct_archive=args.direct_archive,
            )
            return 0

        parser.error(f"Input not found: {inp}")

    upload.set_defaults(func=handle_upload_dicom)

    upload_resource = subparsers.add_parser(
        "upload-resource",
        help=(
            "Upload a file or directory to a session resource "
            "(dir is zipped and extracted server-side)"
        ),
    )
    upload_resource.add_argument("project", help="Project ID")
    upload_resource.add_argument("subject", help="Subject ID")
    upload_resource.add_argument("session", help="Session/experiment ID")
    upload_resource.add_argument("resource", help="Resource label (e.g., BIDS)")
    upload_resource.add_argument("path", type=Path, help="Local file or directory to upload")
    upload_resource.add_argument(
        "--zip-name",
        default=None,
        help="Optional zip filename to use on server (defaults to <resource>.zip)",
    )
    upload_resource.add_argument(
        "--env",
        dest="env_file",
        type=Path,
        default=None,
        help="Path to .env file that overrides environment variables",
    )
    upload_resource.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    def handle_upload_resource(
        args: argparse.Namespace, parser: argparse.ArgumentParser = upload_resource
    ) -> int:
        p: Path = args.path
        if not p.exists():
            parser.error(f"Path not found: {p}")

        cfg = load_config(args.env_file)
        conn = XNATConnection.from_config(cfg)
        uploads = UploadService(conn)
        if p.is_dir():
            uploads.upload_session_resource_zip_dir(
                project=args.project,
                subject=args.subject,
                session=args.session,
                resource_label=args.resource,
                local_dir=p,
                zip_name=args.zip_name,
            )
        else:
            uploads.upload_session_resource_file(
                project=args.project,
                subject=args.subject,
                session=args.session,
                resource_label=args.resource,
                file_path=p,
            )
        return 0

    upload_resource.set_defaults(func=handle_upload_resource)
