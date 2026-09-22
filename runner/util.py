"""Small deterministic utilities shared by runner modules."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def expand_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()
