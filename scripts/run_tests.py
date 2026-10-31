"""Run unittest and preserve its output in a unique directory below output/."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from asset_report.runtime import create_run_directory


def main() -> int:
    project_root = PROJECT_ROOT
    run_directory = create_run_directory(project_root / "output", "unittest")
    result_path = run_directory / "unittest-results.txt"
    summary_path = run_directory / "summary.json"
    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
    started_at = datetime.now(timezone.utc)
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=project_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    duration = time.monotonic() - started
    result_path.write_text(completed.stdout, encoding="utf-8")
    summary = {
        "command": command,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(duration, 3),
        "exit_code": completed.returncode,
        "result_file": str(result_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(completed.stdout, end="")
    print(f"\nUnittest results: {result_path}")
    print(f"Run summary: {summary_path}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
