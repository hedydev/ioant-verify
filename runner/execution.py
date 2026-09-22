"""End-to-end exact-SHA execution orchestration."""

from __future__ import annotations

import platform
from pathlib import Path
from typing import Any

from adapters.base import RunContext
from adapters.registry import get_adapter

from .diagnostics import DiagnosticSession
from .exact_sha import ExactRevision, ExactRevisionError
from .report_writer import ReportWriter
from .schema import load_json, validate_instance
from .state_store import RunRecord, StateStore
from .util import utc_now

_RESULT_ORDER = {"infra_error": 5, "blocked": 4, "fail": 3, "skipped": 2, "pass": 1}


def _overall_result(cases: list[dict[str, Any]]) -> str:
    if not cases:
        return "pass"
    return max((case["result"] for case in cases), key=lambda value: _RESULT_ORDER[value])


class ExecutionEngine:
    def __init__(self, *, state_db: str | Path, report_root: str | Path, diagnostics_root: str | Path) -> None:
        self.state = StateStore(state_db)
        self.reports = ReportWriter(report_root)
        self.diagnostics_root = Path(diagnostics_root)

    def run(self, *, project: str, adapter_name: str, repo: str | Path, requested_commit: str, suite_path: str | Path, mode: str, rerun: bool = False) -> tuple[RunRecord, dict[str, Any], bool]:
        suite = load_json(suite_path)
        validate_instance(suite, "suite.schema.json")
        if suite["project"] != project:
            raise ValueError(f"suite project {suite['project']!r} does not match requested project {project!r}")

        inspection = ExactRevision.inspect(repo, requested_commit)
        record, created = self.state.reserve(project=project, requested_commit=inspection.requested_commit, suite=suite["name"], suite_version=suite["version"], mode=mode, rerun=rerun)
        if not created and record.report_dir:
            report = load_json(Path(record.report_dir) / "report.json")
            return record, report, False

        diagnostic = DiagnosticSession(self.diagnostics_root, record.run_id)
        diagnostic.event("run_started", operation_id=record.run_id, requested_commit=inspection.requested_commit, tested_commit=inspection.tested_commit, suite=suite["name"], attempt=record.attempt)
        started_at = record.started_at
        cases: list[dict[str, Any]] = []
        artifacts: list[str] = [str(diagnostic.path)]
        result = "infra_error"
        environment: dict[str, Any] = {"platform": platform.platform(), "python": platform.python_version(), "adapter": adapter_name}
        tested_commit = inspection.tested_commit

        try:
            self.state.transition(record.run_id, "QUEUED", "validated suite and reserved logical identity")
            self.state.transition(record.run_id, "PREPARING", inspection.message)
            self.state.update_tested_commit(record.run_id, tested_commit)
            if not inspection.matches:
                cases.append({
                    "id": "exact-sha",
                    "title": "Requested revision equals tested revision",
                    "result": "infra_error",
                    "expected": inspection.requested_commit,
                    "observed": tested_commit,
                    "duration_seconds": 0.0,
                    "evidence": ["git rev-parse requested", "git rev-parse HEAD"],
                    "failure_reason": inspection.message,
                })
                raise ExactRevisionError(inspection.message)

            adapter = get_adapter(adapter_name)
            context = RunContext(record.run_id, project, inspection.repo, inspection.requested_commit, tested_commit, mode)
            environment.update(adapter.identify_project(context))
            environment.update(adapter.suite_environment(context))
            adapter.prepare_revision(context)
            self.state.transition(record.run_id, "RUNNING", "adapter execution started")
            cases.extend(adapter.execute(context, suite))
            self.state.transition(record.run_id, "COLLECTING", "collecting verifier-owned artifacts")
            artifacts.extend(adapter.collect_diagnostics(context))
            self.state.transition(record.run_id, "EVALUATING", "evaluating deterministic case results")
            result = _overall_result(cases)
        except ExactRevisionError as exc:
            result = "infra_error"
            diagnostic.event("exact_sha_rejected", operation_id=record.run_id, level="error", reason=str(exc))
        except Exception as exc:
            result = "infra_error"
            if not cases:
                cases.append({
                    "id": "verifier-exception",
                    "title": "Verifier execution completes without infrastructure exception",
                    "result": "infra_error",
                    "expected": "no verifier exception",
                    "observed": type(exc).__name__,
                    "duration_seconds": 0.0,
                    "evidence": [str(diagnostic.path)],
                    "failure_reason": str(exc),
                })
            diagnostic.event("verifier_exception", operation_id=record.run_id, level="error", error_type=type(exc).__name__, message=str(exc))

        finished_at = utc_now()
        report = {
            "schema_version": 1,
            "run_id": record.run_id,
            "project": project,
            "requested_commit": inspection.requested_commit,
            "tested_commit": tested_commit,
            "suite": suite["name"],
            "suite_version": suite["version"],
            "attempt": record.attempt,
            "mode": mode,
            "started_at": started_at,
            "finished_at": finished_at,
            "result": result,
            "environment": environment,
            "cases": cases,
            "artifacts": artifacts,
            "device_required_followups": suite["device_required_followups"],
        }
        run_dir = self.reports.write(report)
        record = self.state.finish(record.run_id, result=result.upper(), tested_commit=tested_commit, report_dir=str(run_dir))
        diagnostic.event("run_finished", operation_id=record.run_id, result=result, report_dir=str(run_dir))
        return record, report, True
