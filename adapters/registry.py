"""Explicit adapter registry; arbitrary imports/shell strings are not accepted."""

from __future__ import annotations

from .base import ProjectAdapter
from .demo.adapter import DemoAdapter


def get_adapter(name: str) -> ProjectAdapter:
    if name == "demo":
        return DemoAdapter()
    raise KeyError(f"unknown adapter: {name}")
