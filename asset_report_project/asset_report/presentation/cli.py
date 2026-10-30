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
        prog="asset-report",
        description="Generate a polished, stand-alone HTML asset report from JSON data.",
    )
    parser.add_argument("input", type=Path, help="path to the structured asset JSON file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("build/asset-report.html"),
        help="output HTML path (default: build/asset-report.html)",
    )
    parser.add_argument("--title", help="optional browser-page title")
    parser.add_argument("--version", action="version", version="asset-report 1.0.0")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        output = FinancialAnalysisApp().generate_asset_report(
            args.input, args.output, title=args.title
        )
    except (DataValidationError, ValueError, OSError) as exc:
        print(f"asset-report: error: {exc}", file=sys.stderr)
        return 1
    print(f"Asset report written to {output}")
    return 0
