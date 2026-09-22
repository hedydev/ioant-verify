"""IWB-specific adapter; all product paths and commands live here."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from adapters.base import ProjectAdapter, RunContext
from task_sync.ledger import active_projection, select_tasks


class IwbAdapter(ProjectAdapter):
    name = "iwb"

    def _assert_layout(self, repo: Path) -> None:
        required = [
            repo / "AGENTS.md",
            repo / ".hero-skills.yaml",
            repo / ".ai-work" / "tasks",
            repo / "apps" / "mobile" / "package.json",
            repo / "apps" / "mobile" / "package-lock.json",
            repo / "scripts" / "check_mac.sh",
        ]
        missing = [str(path.relative_to(repo)) for path in required if not path.exists()]
        if missing:
            raise RuntimeError(f"IWB checkout is missing required path(s): {', '.join(missing)}")

    @staticmethod
    def _command_case(
        *,
        case_id: str,
        title: str,
        cwd: Path,
        command: list[str],
    ) -> dict[str, Any]:
        started = time.perf_counter()
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        elapsed = max(0.0, time.perf_counter() - started)
        output = completed.stdout or ""
        tail = "\n".join(output.splitlines()[-80:])
        passed = completed.returncode == 0
        return {
            "id": case_id,
            "title": title,
            "result": "pass" if passed else "fail",
            "expected": "exit code 0",
            "observed": f"exit code {completed.returncode}",
            "duration_seconds": elapsed,
            "evidence": [
                f"command: {' '.join(command)}",
                f"cwd: {cwd}",
                f"output_tail:\n{tail}",
            ],
            "failure_reason": None if passed else tail or "command failed without output",
        }

    def identify_project(self, context: RunContext) -> dict[str, Any]:
        self._assert_layout(context.repo)
        projection = active_projection(context.repo, "iwb")
        return {
            "adapter": self.name,
            "project": "iwb",
            "ledger_commit": projection["ledger_commit"],
        }

    def prepare_revision(self, context: RunContext) -> dict[str, Any]:
        self._assert_layout(context.repo)
        if context.requested_commit != context.tested_commit:
            raise RuntimeError(
                f"exact SHA mismatch: requested {context.requested_commit}, tested {context.tested_commit}"
            )
        return {
            "requested_commit": context.requested_commit,
            "tested_commit": context.tested_commit,
        }

    def suite_environment(self, context: RunContext) -> dict[str, Any]:
        projection = active_projection(context.repo, "iwb")
        return {
            "ledger_commit": projection["ledger_commit"],
            "active_task_count": len(projection["tasks"]),
            "device_mode": "simulator-first",
            "physical_device_automation": "deferred",
        }

    def execute(self, context: RunContext, suite: dict[str, Any]) -> list[dict[str, Any]]:
        handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "iwb.assert.active-tasks": lambda params: self._assert_active_tasks(context, params),
            "iwb.prepare.mobile-deps": lambda params: self._mobile_deps(context),
            "iwb.validate.mobile-typecheck": lambda params: self._mobile_typecheck(context),
            "iwb.validate.mac-check": lambda params: self._mac_check(context),
        }
        cases: list[dict[str, Any]] = []
        for action in [*suite.get("steps", []), *suite.get("assertions", [])]:
            action_name = action["action"]
            handler = handlers.get(action_name)
            if handler is None:
                cases.append({
                    "id": action["id"],
                    "title": f"Supported IWB action: {action_name}",
                    "result": "infra_error",
                    "expected": "known allowlisted IWB adapter action",
                    "observed": action_name,
                    "duration_seconds": 0.0,
                    "evidence": [],
                    "failure_reason": "suite requested an action not implemented by the IWB adapter",
                })
                continue
            case = handler(action.get("params") or {})
            case["id"] = action["id"]
            cases.append(case)
        return cases

    def _assert_active_tasks(self, context: RunContext, params: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        task_ids = params.get("task_ids")
        if not isinstance(task_ids, list) or not task_ids or not all(isinstance(item, str) for item in task_ids):
            raise ValueError("iwb.assert.active-tasks requires a non-empty string task_ids array")
        projection = active_projection(context.repo, "iwb")
        selected = select_tasks(projection, task_ids)
        return {
            "id": "active-tasks",
            "title": "Suite task references are active in the represented IWB ledger",
            "result": "pass",
            "expected": task_ids,
            "observed": [task["display_id"] for task in selected],
            "duration_seconds": max(0.0, time.perf_counter() - started),
            "evidence": [
                f"ledger_commit: {projection['ledger_commit']}",
                *[
                    f"{task['display_id']}: status={task['status']} priority={task['priority']}"
                    for task in selected
                ],
            ],
            "failure_reason": None,
        }

    def _mobile_deps(self, context: RunContext) -> dict[str, Any]:
        return self._command_case(
            case_id="mobile-deps",
            title="IWB mobile dependencies match package-lock",
            cwd=context.repo / "apps" / "mobile",
            command=["npm", "ci"],
        )

    def _mobile_typecheck(self, context: RunContext) -> dict[str, Any]:
        return self._command_case(
            case_id="mobile-typecheck",
            title="IWB mobile TypeScript validation",
            cwd=context.repo / "apps" / "mobile",
            command=["npm", "run", "typecheck"],
        )

    def _mac_check(self, context: RunContext) -> dict[str, Any]:
        return self._command_case(
            case_id="mac-check",
            title="IWB canonical macOS validation",
            cwd=context.repo,
            command=["bash", "scripts/check_mac.sh"],
        )
