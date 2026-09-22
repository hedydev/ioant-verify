"""Explicit adapter registry; arbitrary imports/shell strings are not accepted."""

from __future__ import annotations

from .base import ProjectAdapter
from .demo.adapter import DemoAdapter
from .iwb.adapter import IwbAdapter


def get_adapter(name: str) -> ProjectAdapter:
    if name == "demo":
        return DemoAdapter()
    if name == "iwb":
        return IwbAdapter()
    raise KeyError(f"unknown adapter: {name}")
