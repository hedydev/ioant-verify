"""Deterministic adapter used only to prove the generic Phase 0 chain."""

from __future__ import annotations

import time
from typing import Any

from adapters.base import ProjectAdapter, RunContext


class DemoAdapter(ProjectAdapter):
    name = "demo"

    def identify_project(self, context: RunContext) -> dict[str, Any]:
        return {"adapter": self.name, "project": context.project}

    def prepare_revision(self, context: RunContext) -> dict[str, Any]:
        if context.requested_commit != context.tested_commit:
            raise RuntimeError(f"exact SHA mismatch: requested {context.requested_commit}, tested {context.tested_commit}")
        return {"requested_commit": context.requested_commit, "tested_commit": context.tested_commit}

    def suite_environment(self, context: RunContext) -> dict[str, Any]:
        return {"adapter": self.name, "deterministic": True}

    def execute(self, context: RunContext, suite: dict[str, Any]) -> list[dict[str, Any]]:
        started = time.perf_counter()
        matches = context.requested_commit == context.tested_commit
        return [{
            "id": "exact-sha",
            "title": "Requested revision equals tested revision",
            "result": "pass" if matches else "infra_error",
            "expected": context.requested_commit,
            "observed": context.tested_commit,
            "duration_seconds": max(0.0, time.perf_counter() - started),
            "evidence": ["report.requested_commit", "report.tested_commit"],
            "failure_reason": None if matches else "exact SHA mismatch",
        }]
