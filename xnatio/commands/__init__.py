from __future__ import annotations

import argparse

from .admin import register as register_admin
from .download import register as register_download
from .maintenance import register as register_maintenance
from .upload import register as register_upload


def register_all(subparsers: argparse._SubParsersAction) -> None:
    """Register all CLI command groups."""
    register_upload(subparsers)
    register_download(subparsers)
    register_admin(subparsers)
    register_maintenance(subparsers)


__all__ = ["register_all"]
