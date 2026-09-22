from __future__ import annotations

import json
import subprocess
from importlib import resources
from pathlib import Path

from runner.checkout import VerifierCheckout
from runner.schema import validate_instance
from task_sync.ledger import active_projection


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def _init_repo(repo: Path) -> str:
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@ioant.invalid")
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "baseline")
    return _git(repo, "rev-parse", "HEAD")


def test_verifier_checkout_uses_isolated_exact_clone(tmp_path: Path) -> None:
    source = tmp_path / "source"
    sha = _init_repo(source)
    (source / "untracked-user-file.txt").write_text("do not touch\n", encoding="utf-8")

    manager = VerifierCheckout(tmp_path / "checkouts")
    result = manager.prepare(
        project="iwb",
        repository_url=str(source),
        branch="main",
        commit=sha,
    )

    assert result.tested_commit == sha
    assert result.path != source
    assert (source / "untracked-user-file.txt").read_text(encoding="utf-8") == "do not touch\n"
    assert _git(result.path, "status", "--porcelain") == ""


def test_active_projection_replays_events_and_exposes_ledger_commit(tmp_path: Path) -> None:
    repo = tmp_path / "ledger"
    _init_repo(repo)

    task_a = repo / ".ai-work" / "tasks" / "task-a"
    events_a = task_a / "events"
    events_a.mkdir(parents=True)
    (task_a / "task.json").write_text(
        json.dumps({
            "schema_version": 2,
            "task_id": "task-a",
            "display_id": "IWB-001",
            "created_at": "2026-09-22T00:00:00Z",
            "created_by": {"actor_type": "ai", "ai_name": "ChatGPT", "ai_session_id": "aaaaaaaa"},
            "ledger_branch": "main",
            "development_branch": "main",
            "objective": "Verify scrolling",
            "scope": [],
            "target_ids": [],
            "acceptance_criteria": ["scroll works"],
            "deduplication_key": "a",
            "parent_task_id": None,
            "relations": [],
        }),
        encoding="utf-8",
    )
    (events_a / "001.json").write_text(
        json.dumps({
            "schema_version": 2,
            "event_id": "event-a",
            "task_id": "task-a",
            "event_type": "task_updated",
            "occurred_at": "2026-09-22T00:01:00Z",
            "actor": {"actor_type": "ai", "ai_name": "ChatGPT", "ai_session_id": "bbbbbbbb"},
            "changes": {
                "current_ai_session_id": {"from": "aaaaaaaa", "to": "bbbbbbbb"},
                "status": {"from": "todo", "to": "awaiting_automated_validation"},
                "priority": {"from": "P2", "to": "P1"},
                "module": {"from": None, "to": "Live Window"},
                "verification_methods": {"from": None, "to": ["ioant-verify:iwb-live-scroll"]},
            },
            "evidence": [{"kind": "commit", "source": "abc"}],
        }),
        encoding="utf-8",
    )

    task_b = repo / ".ai-work" / "tasks" / "task-b"
    events_b = task_b / "events"
    events_b.mkdir(parents=True)
    (task_b / "task.json").write_text(
        json.dumps({
            "schema_version": 2,
            "task_id": "task-b",
            "display_id": "IWB-999",
            "created_at": "2026-09-22T00:00:00Z",
            "created_by": {"actor_type": "ai", "ai_name": "ChatGPT", "ai_session_id": "cccccccc"},
            "ledger_branch": "main",
            "development_branch": "main",
            "objective": "Completed work",
            "scope": [],
            "target_ids": [],
            "acceptance_criteria": ["done"],
            "deduplication_key": "b",
            "parent_task_id": None,
            "relations": [],
        }),
        encoding="utf-8",
    )
    (events_b / "001.json").write_text(
        json.dumps({
            "schema_version": 2,
            "event_id": "event-b",
            "task_id": "task-b",
            "event_type": "task_completed",
            "occurred_at": "2026-09-22T00:02:00Z",
            "actor": {"actor_type": "ai", "ai_name": "ChatGPT", "ai_session_id": "cccccccc"},
            "changes": {"status": {"from": "awaiting_user_acceptance", "to": "completed"}},
            "evidence": [],
        }),
        encoding="utf-8",
    )

    _git(repo, "add", ".ai-work")
    _git(repo, "commit", "-m", "ledger")
    head = _git(repo, "rev-parse", "HEAD")

    projection = active_projection(repo, "iwb")
    assert projection["ledger_commit"] == head
    assert [task["display_id"] for task in projection["tasks"]] == ["IWB-001"]
    task = projection["tasks"][0]
    assert task["status"] == "awaiting_automated_validation"
    assert task["priority"] == "P1"
    assert task["current_ai_session_id"] == "bbbbbbbb"


def test_packaged_iwb_suite_schema() -> None:
    suite = resources.files("adapters.iwb.suites").joinpath("iwb-high-priority-static.json")
    data = json.loads(suite.read_text(encoding="utf-8"))
    validate_instance(data, "suite.schema.json")
    assert data["task_refs"] == ["IWB-001", "IWB-003", "IWB-004", "IWB-006"]
