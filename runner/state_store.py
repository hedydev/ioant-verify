"""SQLite-backed idempotent run ledger."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .schema import validate_instance
from .util import utc_now

TERMINAL_RESULTS = {"PASS", "FAIL", "BLOCKED", "INFRA_ERROR", "SKIPPED"}


@dataclass
class RunRecord:
    schema_version: int
    run_id: str
    logical_key: str
    project: str
    requested_commit: str
    tested_commit: str | None
    suite: str
    suite_version: int
    attempt: int
    mode: str
    lifecycle_state: str
    result: str | None
    started_at: str
    finished_at: str | None
    report_dir: str | None

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        validate_instance(value, "run-state.schema.json")
        return value


class StateStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _init_db(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    logical_key TEXT NOT NULL,
                    project TEXT NOT NULL,
                    requested_commit TEXT NOT NULL,
                    tested_commit TEXT,
                    suite TEXT NOT NULL,
                    suite_version INTEGER NOT NULL,
                    attempt INTEGER NOT NULL,
                    mode TEXT NOT NULL,
                    lifecycle_state TEXT NOT NULL,
                    result TEXT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    report_dir TEXT,
                    UNIQUE(logical_key, attempt)
                );
                CREATE TABLE IF NOT EXISTS transitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    lifecycle_state TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    message TEXT,
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                );
                CREATE INDEX IF NOT EXISTS idx_runs_logical_key ON runs(logical_key, attempt DESC);
                """
            )

    @staticmethod
    def logical_key(project: str, commit: str, suite: str, version: int) -> str:
        return f"{project}:{commit}:{suite}:v{version}"

    def reserve(self, *, project: str, requested_commit: str, suite: str, suite_version: int, mode: str, rerun: bool) -> tuple[RunRecord, bool]:
        logical_key = self.logical_key(project, requested_commit, suite, suite_version)
        with self._connect() as db:
            row = db.execute("SELECT * FROM runs WHERE logical_key = ? ORDER BY attempt DESC LIMIT 1", (logical_key,)).fetchone()
            if row is not None and not rerun:
                return self._row(row), False
            attempt = 1 if row is None else int(row["attempt"]) + 1
            record = RunRecord(1, str(uuid.uuid4()), logical_key, project, requested_commit, None, suite, suite_version, attempt, mode, "DISCOVERED", None, utc_now(), None, None)
            record.as_dict()
            db.execute(
                """INSERT INTO runs (run_id, logical_key, project, requested_commit, tested_commit, suite, suite_version, attempt, mode, lifecycle_state, result, started_at, finished_at, report_dir)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (record.run_id, record.logical_key, record.project, record.requested_commit, record.tested_commit, record.suite, record.suite_version, record.attempt, record.mode, record.lifecycle_state, record.result, record.started_at, record.finished_at, record.report_dir),
            )
            db.execute("INSERT INTO transitions (run_id, lifecycle_state, occurred_at, message) VALUES (?, ?, ?, ?)", (record.run_id, "DISCOVERED", record.started_at, "run reserved"))
            return record, True

    def transition(self, run_id: str, lifecycle_state: str, message: str | None = None) -> None:
        now = utc_now()
        with self._connect() as db:
            db.execute("UPDATE runs SET lifecycle_state = ? WHERE run_id = ?", (lifecycle_state, run_id))
            db.execute("INSERT INTO transitions (run_id, lifecycle_state, occurred_at, message) VALUES (?, ?, ?, ?)", (run_id, lifecycle_state, now, message))

    def finish(self, run_id: str, *, result: str, tested_commit: str | None, report_dir: str) -> RunRecord:
        if result not in TERMINAL_RESULTS:
            raise ValueError(f"invalid result: {result}")
        now = utc_now()
        with self._connect() as db:
            db.execute("UPDATE runs SET lifecycle_state = ?, result = ?, tested_commit = ?, finished_at = ?, report_dir = ? WHERE run_id = ?", (result, result, tested_commit, now, report_dir, run_id))
            db.execute("INSERT INTO transitions (run_id, lifecycle_state, occurred_at, message) VALUES (?, ?, ?, ?)", (run_id, result, now, "result recorded"))
            db.execute("UPDATE runs SET lifecycle_state = ? WHERE run_id = ?", ("ARCHIVED", run_id))
            db.execute("INSERT INTO transitions (run_id, lifecycle_state, occurred_at, message) VALUES (?, ?, ?, ?)", (run_id, "ARCHIVED", utc_now(), "run archived"))
            row = db.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        assert row is not None
        record = self._row(row)
        record.as_dict()
        return record

    def update_tested_commit(self, run_id: str, tested_commit: str | None) -> None:
        with self._connect() as db:
            db.execute("UPDATE runs SET tested_commit = ? WHERE run_id = ?", (tested_commit, run_id))

    def latest(self, *, project: str | None = None, commit: str | None = None) -> RunRecord | None:
        clauses, params = [], []
        if project:
            clauses.append("project = ?")
            params.append(project)
        if commit:
            clauses.append("requested_commit = ?")
            params.append(commit)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connect() as db:
            row = db.execute(f"SELECT * FROM runs{where} ORDER BY started_at DESC, attempt DESC LIMIT 1", params).fetchone()
        return self._row(row) if row is not None else None

    @staticmethod
    def _row(row: sqlite3.Row) -> RunRecord:
        return RunRecord(**dict(row), schema_version=1)
