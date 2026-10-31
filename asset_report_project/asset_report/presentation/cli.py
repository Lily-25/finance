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
        description="Generate a polished HTML asset and liability report from JSON data.",
    )
    parser.add_argument(
        "input",
        type=Path,
        nargs="+",
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
    parser.add_argument("--version", action="version", version="financial-report 3.0.0")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        output = FinancialAnalysisApp().generate_time_frame_report(
            args.input, args.output, title=args.title
        )
    except (DataValidationError, ValueError, OSError) as exc:
        print(f"financial-report: error: {exc}", file=sys.stderr)
        return 1
    print(f"Financial report written to {output}")
    return 0
