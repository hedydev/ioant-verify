"""Deterministic isolated Phase 0 end-to-end self-test."""

from __future__ import annotations

import subprocess
import tempfile
from importlib import resources
from pathlib import Path
from typing import Any

from .execution import ExecutionEngine


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-C", str(repo), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return completed.stdout.strip()


def run_self_test() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ioant-verify-self-test-") as temp:
        base = Path(temp)
        repo = base / "repo"
        repo.mkdir()
        _git(repo, "init", "-b", "main")
        _git(repo, "config", "user.name", "Ioant Verify Self Test")
        _git(repo, "config", "user.email", "self-test@ioant.invalid")
        (repo / "fixture.txt").write_text("phase0\n", encoding="utf-8")
        _git(repo, "add", "fixture.txt")
        _git(repo, "commit", "-m", "phase0 fixture")
        exact_sha = _git(repo, "rev-parse", "HEAD")

        suite = resources.files("adapters.demo.suites").joinpath("demo-smoke.json")
        engine = ExecutionEngine(state_db=base / "state.sqlite3", report_root=base / "reports", diagnostics_root=base / "diagnostics")
        first_record, first_report, first_created = engine.run(project="demo", adapter_name="demo", repo=repo, requested_commit=exact_sha, suite_path=str(suite), mode="static")
        if first_report["result"] != "pass" or first_report["requested_commit"] != first_report["tested_commit"]:
            raise AssertionError(f"exact-SHA PASS self-test failed: {first_report}")

        duplicate_record, duplicate_report, duplicate_created = engine.run(project="demo", adapter_name="demo", repo=repo, requested_commit=exact_sha, suite_path=str(suite), mode="static")
        if duplicate_created or duplicate_record.run_id != first_record.run_id or duplicate_report["attempt"] != 1:
            raise AssertionError("idempotency self-test failed")

        (repo / "fixture.txt").write_text("phase0\nadvanced\n", encoding="utf-8")
        _git(repo, "add", "fixture.txt")
        _git(repo, "commit", "-m", "advance fixture")
        advanced_sha = _git(repo, "rev-parse", "HEAD")
        second_record, second_report, second_created = engine.run(project="demo", adapter_name="demo", repo=repo, requested_commit=exact_sha, suite_path=str(suite), mode="static", rerun=True)
        if not second_created or second_report["result"] != "infra_error":
            raise AssertionError(f"mismatch rejection self-test failed: {second_report}")
        if second_report["requested_commit"] == second_report["tested_commit"] or second_report["tested_commit"] != advanced_sha:
            raise AssertionError("mismatch report did not preserve exact revision evidence")
        if second_report["attempt"] != 2:
            raise AssertionError("manual rerun did not increment attempt")

        return {
            "schema_version": 1,
            "result": "pass",
            "checks": {
                "exact_sha_pass": True,
                "idempotent_duplicate": True,
                "mismatch_rejected_as_infra_error": True,
                "retry_attempt_incremented": True,
                "json_and_markdown_reports": (Path(first_record.report_dir) / "report.json").exists() and (Path(first_record.report_dir) / "report.md").exists(),
            },
            "requested_commit": exact_sha,
            "pass_tested_commit": first_report["tested_commit"],
            "mismatch_tested_commit": second_report["tested_commit"],
            "pass_run_id": first_report["run_id"],
            "mismatch_run_id": second_report["run_id"],
        }
