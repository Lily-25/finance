"""Allow both module and direct-file command-line execution."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from asset_report.presentation.cli import main
else:
    from .presentation.cli import main


def default_arguments() -> list[str]:
    """Return a runnable example when the module is started without arguments."""

    project_root = Path(__file__).resolve().parents[1]
    return [
        str(project_root / "sample_data" / "main_input.json"),
        "--output",
        str(project_root / "build" / "main_report.html"),
        "--title",
        "Orion 2025 Financial Position Report",
    ]


raise SystemExit(main(sys.argv[1:] or default_arguments()))
