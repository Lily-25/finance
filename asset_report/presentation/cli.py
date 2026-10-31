"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from ..application.app import FinancialAnalysisApp
from ..data_access.json_repository import DataValidationError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="financial-report",
        description="Generate a polished HTML financial-position report from JSON data.",
    )
    parser.add_argument(
        "input",
        type=Path,
        nargs="*",
        help="one or more JSON period files for a time-frame report",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("build/time-frame-report.html"),
        help="output HTML path (default: build/time-frame-report.html)",
    )
    parser.add_argument("--title", help="optional browser-page title")
    parser.add_argument(
        "--ui",
        action="store_true",
        help="start the local browser UI instead of generating a report",
    )
    parser.add_argument("--host", default="127.0.0.1", help="UI bind host")
    parser.add_argument("--port", type=int, default=8765, help="UI bind port")
    parser.add_argument("--version", action="version", version="financial-report 5.0.0")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.ui:
        if args.input:
            print(
                "financial-report: error: input files are not accepted with --ui",
                file=sys.stderr,
            )
            return 1
        from .web import serve

        serve(args.host, args.port)
        return 0
    if not args.input:
        print(
            "financial-report: error: provide input files or start the UI with --ui",
            file=sys.stderr,
        )
        return 1
    try:
        output = FinancialAnalysisApp().generate_time_frame_report(
            args.input, args.output, title=args.title
        )
    except (DataValidationError, ValueError, OSError) as exc:
        print(f"financial-report: error: {exc}", file=sys.stderr)
        return 1
    print(f"Financial report written to {output}")
    return 0
