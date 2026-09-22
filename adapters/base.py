"""Stable project-adapter contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunContext:
    run_id: str
    project: str
    repo: Path
    requested_commit: str
    tested_commit: str
    mode: str


class ProjectAdapter(ABC):
    name: str

    @abstractmethod
    def identify_project(self, context: RunContext) -> dict[str, Any]: ...

    @abstractmethod
    def prepare_revision(self, context: RunContext) -> dict[str, Any]: ...

    def build_mac(self, context: RunContext) -> dict[str, Any]:
        return {"supported": False}

    def start_mac(self, context: RunContext) -> dict[str, Any]:
        return {"supported": False}

    def stop_mac(self, context: RunContext) -> dict[str, Any]:
        return {"supported": False}

    def build_ios_simulator(self, context: RunContext) -> dict[str, Any]:
        return {"supported": False}

    def install_ios_simulator(self, context: RunContext) -> dict[str, Any]:
        return {"supported": False}

    def launch_ios_simulator(self, context: RunContext) -> dict[str, Any]:
        return {"supported": False}

    def collect_diagnostics(self, context: RunContext) -> list[str]:
        return []

    def suite_environment(self, context: RunContext) -> dict[str, Any]:
        return {}

    @abstractmethod
    def execute(self, context: RunContext, suite: dict[str, Any]) -> list[dict[str, Any]]: ...

    def cleanup(self, context: RunContext) -> None:
        return None
