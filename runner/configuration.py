"""Local configuration loading with schema validation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from .schema import validate_instance
from .util import expand_path


def default_base_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / "IoantVerify"


def default_config() -> dict[str, Any]:
    base = default_base_dir()
    return {
        "schema_version": 1,
        "state_db": str(base / "state" / "state.sqlite3"),
        "report_root": str(base / "reports"),
        "diagnostics_root": str(base / "diagnostics"),
        "checkout_root": str(base / "checkouts"),
        "projects": {},
    }


def load_config(path: str | Path | None) -> dict[str, Any]:
    selected = Path(path).expanduser() if path else None
    if selected is None:
        env_path = os.environ.get("IOANT_VERIFY_CONFIG")
        selected = Path(env_path).expanduser() if env_path else None
    if selected is None:
        candidate = Path("config/local.yaml")
        selected = candidate if candidate.exists() else None
    if selected is None:
        config = default_config()
    else:
        with selected.open("r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle)
        if not isinstance(config, dict):
            raise ValueError(f"{selected}: configuration must be an object")
    validate_instance(config, "verify.schema.json")
    for key in ("state_db", "report_root", "diagnostics_root", "checkout_root"):
        config[key] = str(expand_path(config[key]))
    return config
