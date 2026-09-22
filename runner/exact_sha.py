"""Exact Git revision inspection without mutating the target worktree."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .errors import ExactRevisionError

_FULL_SHA = re.compile(r"^[0-9a-fA-F]{40}$")


@dataclass(frozen=True)
class RevisionInspection:
    repo: Path
    requested_commit: str
    tested_commit: str | None
    matches: bool
    message: str


class ExactRevision:
    @staticmethod
    def _git(repo: Path, *args: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(repo), *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or "git command failed"
            raise ExactRevisionError(detail)
        return completed.stdout.strip()

    @classmethod
    def inspect(cls, repo: str | Path, requested_commit: str) -> RevisionInspection:
        repo_path = Path(repo).expanduser().resolve()
        if not repo_path.is_dir():
            raise ExactRevisionError(f"repository path does not exist: {repo_path}")
        if not _FULL_SHA.fullmatch(requested_commit):
            raise ExactRevisionError("requested commit must be a full 40-character SHA")
        tested = cls._git(repo_path, "rev-parse", "--verify", "HEAD^{commit}").lower()
        requested_input = requested_commit.lower()
        try:
            requested = cls._git(repo_path, "rev-parse", "--verify", f"{requested_input}^{{commit}}").lower()
        except ExactRevisionError:
            return RevisionInspection(
                repo_path,
                requested_input,
                tested,
                False,
                f"requested commit is not available in repository: {requested_input}",
            )
        matches = requested == tested
        message = "requested commit equals checkout HEAD" if matches else f"requested {requested} but checkout HEAD is {tested}"
        return RevisionInspection(repo_path, requested, tested, matches, message)
