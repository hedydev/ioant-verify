"""Read and deterministically project a product's canonical .ai-work ledger."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TaskProjection:
    task_id: str
    display_id: str
    current_ai_session_id: str
    task_type: str
    module: str
    objective: str
    status: str
    priority: str
    acceptance_criteria: list[str]
    verification_methods: list[str]
    evidence: list[Any]
    next_action: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "display_id": self.display_id,
            "current_ai_session_id": self.current_ai_session_id,
            "type": self.task_type,
            "module": self.module,
            "objective": self.objective,
            "status": self.status,
            "priority": self.priority,
            "acceptance_criteria": self.acceptance_criteria,
            "verification_methods": self.verification_methods,
            "evidence": self.evidence,
            "next_action": self.next_action,
        }


def _git_head(repo: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "HEAD^{commit}"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "cannot resolve ledger commit"
        raise ValueError(detail)
    return completed.stdout.strip().lower()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def _event_sort_key(event: dict[str, Any]) -> tuple[str, str]:
    return (str(event.get("occurred_at", "")), str(event.get("event_id", "")))


def _change_to(value: Any) -> Any:
    if isinstance(value, dict) and "to" in value:
        return value["to"]
    return value


def project_task(task_dir: Path) -> TaskProjection:
    task = _read_json(task_dir / "task.json")
    task_id = str(task["task_id"])
    created_by = task.get("created_by") or {}

    state: dict[str, Any] = {
        "current_ai_session_id": str(created_by.get("ai_session_id") or "unassigned"),
        "task_type": "feature",
        "module": "",
        "objective": str(task.get("objective") or ""),
        "status": "todo",
        "priority": "P2",
        "acceptance_criteria": list(task.get("acceptance_criteria") or []),
        "verification_methods": [],
        "evidence": [],
        "next_action": None,
    }

    events_dir = task_dir / "events"
    events: list[dict[str, Any]] = []
    if events_dir.is_dir():
        for path in sorted(events_dir.glob("*.json")):
            event = _read_json(path)
            if str(event.get("task_id")) != task_id:
                raise ValueError(f"{path}: task_id does not match directory task")
            events.append(event)

    for event in sorted(events, key=_event_sort_key):
        changes = event.get("changes") or {}
        if not isinstance(changes, dict):
            raise ValueError(f"{task_dir}: event changes must be an object")

        for source_key, target_key in (
            ("current_ai_session_id", "current_ai_session_id"),
            ("task_type", "task_type"),
            ("module", "module"),
            ("objective", "objective"),
            ("status", "status"),
            ("priority", "priority"),
            ("acceptance_criteria", "acceptance_criteria"),
            ("verification_methods", "verification_methods"),
            ("next_action", "next_action"),
        ):
            if source_key in changes:
                state[target_key] = _change_to(changes[source_key])

        event_type = str(event.get("event_type") or "")
        if event_type in {"assigned", "handoff_recorded"}:
            assigned = _change_to(changes.get("current_ai_session_id"))
            if assigned:
                state["current_ai_session_id"] = assigned
        elif event_type == "task_completed":
            state["status"] = "completed"
        elif event_type == "task_reopened" and state["status"] == "completed":
            state["status"] = _change_to(changes.get("status")) or "todo"

        evidence = event.get("evidence")
        if isinstance(evidence, list):
            state["evidence"].extend(evidence)

    return TaskProjection(
        task_id=task_id,
        display_id=str(task.get("display_id") or task_id),
        current_ai_session_id=str(state["current_ai_session_id"] or "unassigned"),
        task_type=str(state["task_type"] or "feature"),
        module=str(state["module"] or ""),
        objective=str(state["objective"] or ""),
        status=str(state["status"] or "todo"),
        priority=str(state["priority"] or "P2"),
        acceptance_criteria=[str(item) for item in (state["acceptance_criteria"] or [])],
        verification_methods=[str(item) for item in (state["verification_methods"] or [])],
        evidence=list(state["evidence"]),
        next_action=None if state["next_action"] is None else str(state["next_action"]),
    )


def active_projection(repo: str | Path, project: str) -> dict[str, Any]:
    repo_path = Path(repo).expanduser().resolve()
    tasks_root = repo_path / ".ai-work" / "tasks"
    if not tasks_root.is_dir():
        raise ValueError(f"task ledger not found: {tasks_root}")

    tasks: list[TaskProjection] = []
    for task_dir in sorted(path for path in tasks_root.iterdir() if path.is_dir()):
        task_file = task_dir / "task.json"
        if not task_file.is_file():
            continue
        projected = project_task(task_dir)
        if projected.status != "completed":
            tasks.append(projected)

    tasks.sort(key=lambda item: (item.priority, item.display_id, item.task_id))
    return {
        "schema_version": 1,
        "project": project,
        "ledger_commit": _git_head(repo_path),
        "tasks": [task.as_dict() for task in tasks],
    }


def select_tasks(projection: dict[str, Any], task_ids: list[str]) -> list[dict[str, Any]]:
    wanted = set(task_ids)
    selected = [
        task for task in projection.get("tasks", [])
        if task.get("task_id") in wanted or task.get("display_id") in wanted
    ]
    found = {task.get("task_id") for task in selected} | {task.get("display_id") for task in selected}
    missing = [task_id for task_id in task_ids if task_id not in found]
    if missing:
        raise ValueError(f"requested task(s) are not active in represented ledger: {', '.join(missing)}")
    return selected
