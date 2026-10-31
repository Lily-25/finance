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
    sample_root = project_root / "sample_data"
    return [
        str(sample_root / "orion_industrial_group_ltd_2023.json"),
        str(sample_root / "orion_industrial_group_ltd_2024.json"),
        str(sample_root / "orion_industrial_group_ltd_2025.json"),
        str(sample_root / "orion_industrial_group_ltd_2026Q3.json"),
        "--output",
        str(project_root / "build" / "time-frame-report.html"),
        "--title",
        "Orion 2023–2026Q3 Trend Report",
    ]


raise SystemExit(main(sys.argv[1:] or default_arguments()))
