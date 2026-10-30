"""Allow both module and direct-file command-line execution."""

from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from asset_report.presentation.cli import main
else:
    from .presentation.cli import main

raise SystemExit(main(main([
    "../sample_data/main_input.json",
    "--output", "../build/main_report.html",
    "--title", "Orion 2025 Asset Report",
])))
