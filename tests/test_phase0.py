from __future__ import annotations

import json
import subprocess
from importlib import resources
from pathlib import Path

from runner.exact_sha import ExactRevision
from runner.schema import validate_instance
from runner.self_test import run_self_test
from runner.state_store import StateStore


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-C", str(repo), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return completed.stdout.strip()


def test_demo_suite_schema() -> None:
    suite = resources.files("adapters.demo.suites").joinpath("demo-smoke.json")
    data = json.loads(suite.read_text(encoding="utf-8"))
    validate_instance(data, "suite.schema.json")


def test_exact_revision_inspection(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@ioant.invalid")
    (repo / "x").write_text("1", encoding="utf-8")
    _git(repo, "add", "x")
    _git(repo, "commit", "-m", "one")
    sha = _git(repo, "rev-parse", "HEAD")
    inspection = ExactRevision.inspect(repo, sha)
    assert inspection.matches is True
    assert inspection.requested_commit == inspection.tested_commit == sha


def test_unknown_requested_sha_is_rejected_with_tested_head(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@ioant.invalid")
    (repo / "x").write_text("1", encoding="utf-8")
    _git(repo, "add", "x")
    _git(repo, "commit", "-m", "one")
    head = _git(repo, "rev-parse", "HEAD")
    requested = "f" * 40
    inspection = ExactRevision.inspect(repo, requested)
    assert inspection.matches is False
    assert inspection.requested_commit == requested
    assert inspection.tested_commit == head
    assert "not available" in inspection.message


def test_state_idempotency_and_attempts(tmp_path: Path) -> None:
    sha = "a" * 40
    state = StateStore(tmp_path / "state.sqlite3")
    first, created = state.reserve(project="demo", requested_commit=sha, suite="demo-smoke", suite_version=1, mode="static", rerun=False)
    assert created is True
    duplicate, created = state.reserve(project="demo", requested_commit=sha, suite="demo-smoke", suite_version=1, mode="static", rerun=False)
    assert created is False
    assert duplicate.run_id == first.run_id
    retry, created = state.reserve(project="demo", requested_commit=sha, suite="demo-smoke", suite_version=1, mode="static", rerun=True)
    assert created is True
    assert retry.attempt == 2


def test_self_test_end_to_end() -> None:
    result = run_self_test()
    assert result["result"] == "pass"
    assert all(result["checks"].values())
    assert result["requested_commit"] == result["pass_tested_commit"]
    assert result["requested_commit"] != result["mismatch_tested_commit"]
