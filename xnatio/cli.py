from __future__ import annotations

import argparse
import logging
from typing import Optional

from .commands import register_all


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for the xnatio CLI."""
    parser = argparse.ArgumentParser(prog="xnatio", description="XNAT CLI utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_all(subparsers)
    return parser


def run_cli(argv: Optional[list[str]] = None) -> int:
    """Run the xnatio command-line interface."""
    parser = build_parser()
    args = parser.parse_args(argv)

    verbose = bool(getattr(args, "verbose", False))
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARN,
        format="%(asctime)s %(levelname)s %(name)s ┊ %(message)s",
    )

    if not hasattr(args, "func"):
        parser.error("No handler registered for the selected command")

    return int(args.func(args))
