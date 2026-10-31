"""Runtime directory helpers shared by tests and interactive tasks."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile


def create_run_directory(base_directory: str | Path, prefix: str) -> Path:
    """Create and preserve a unique timestamped directory below ``base_directory``."""

    base = Path(base_directory).expanduser().resolve()
    base.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(tempfile.mkdtemp(prefix=f"{prefix}-{timestamp}-", dir=str(base))).resolve()
