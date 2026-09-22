"""Durable, bounded JSONL diagnostics for verifier runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .util import utc_now

_SENSITIVE_KEYS = {"token", "password", "secret", "authorization", "cookie", "api_key"}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: ("<redacted>" if key.lower() in _SENSITIVE_KEYS else _redact(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


class DiagnosticSession:
    def __init__(self, root: str | Path, session_id: str) -> None:
        self.session_id = session_id
        self.path = Path(root) / f"{session_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, event: str, *, operation_id: str | None = None, level: str = "info", **fields: Any) -> None:
        payload = {
            "timestamp": utc_now(),
            "session_id": self.session_id,
            "operation_id": operation_id,
            "level": level,
            "event": event,
            "fields": _redact(fields),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n")
