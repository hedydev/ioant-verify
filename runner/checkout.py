"""Verifier-owned Git checkout management."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .errors import ExactRevisionError

_FULL_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
_PROJECT = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass(frozen=True)
class CheckoutResult:
    project: str
    path: Path
    branch: str
    requested_commit: str
    tested_commit: str
    origin_url: str


class VerifierCheckout:
    """Owns isolated clones under the Ioant Verify application data root."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _run(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            list(args),
            cwd=str(cwd) if cwd else None,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if check and completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or f"command failed: {' '.join(args)}"
            raise ExactRevisionError(detail)
        return completed

    @staticmethod
    def _normalize_url(value: str) -> str:
        normalized = value.strip().rstrip("/")
        return normalized[:-4] if normalized.endswith(".git") else normalized

    def prepare(
        self,
        *,
        project: str,
        repository_url: str,
        branch: str,
        commit: str,
    ) -> CheckoutResult:
        if not _PROJECT.fullmatch(project):
            raise ValueError(f"invalid project id: {project!r}")
        if not repository_url.strip():
            raise ValueError("repository_url is required")
        if not branch.strip():
            raise ValueError("branch is required")
        if not _FULL_SHA.fullmatch(commit):
            raise ExactRevisionError("requested commit must be a full 40-character SHA")

        requested = commit.lower()
        checkout = self.root / project

        created = False
        if not checkout.exists():
            self._run("git", "clone", "--no-checkout", "--origin", "origin", repository_url, str(checkout))
            created = True
        elif not (checkout / ".git").exists():
            raise ExactRevisionError(f"verifier checkout path is not a Git clone: {checkout}")

        configured_origin = self._run("git", "remote", "get-url", "origin", cwd=checkout).stdout.strip()
        if self._normalize_url(configured_origin) != self._normalize_url(repository_url):
            raise ExactRevisionError(
                f"verifier checkout origin mismatch: configured {configured_origin!r}, requested {repository_url!r}"
            )

        if not created:
            dirty = self._run("git", "status", "--porcelain", "--untracked-files=all", cwd=checkout).stdout.strip()
            if dirty:
                raise ExactRevisionError(
                    f"verifier-owned checkout is unexpectedly dirty; refusing to discard evidence: {checkout}"
                )

        self._run(
            "git",
            "fetch",
            "--no-tags",
            "origin",
            f"refs/heads/{branch}:refs/remotes/origin/{branch}",
            cwd=checkout,
        )

        available = self._run(
            "git",
            "cat-file",
            "-e",
            f"{requested}^{{commit}}",
            cwd=checkout,
            check=False,
        )
        if available.returncode != 0:
            raise ExactRevisionError(f"requested commit is not available after fetching origin/{branch}: {requested}")

        ancestor = self._run(
            "git",
            "merge-base",
            "--is-ancestor",
            requested,
            f"refs/remotes/origin/{branch}",
            cwd=checkout,
            check=False,
        )
        if ancestor.returncode != 0:
            raise ExactRevisionError(f"requested commit {requested} is not contained in origin/{branch}")

        self._run("git", "checkout", "--detach", requested, cwd=checkout)
        tested = self._run("git", "rev-parse", "--verify", "HEAD^{commit}", cwd=checkout).stdout.strip().lower()
        if tested != requested:
            raise ExactRevisionError(f"exact checkout mismatch: requested {requested}, tested {tested}")

        final_dirty = self._run("git", "status", "--porcelain", "--untracked-files=all", cwd=checkout).stdout.strip()
        if final_dirty:
            raise ExactRevisionError(f"verifier checkout became dirty during preparation: {checkout}")

        return CheckoutResult(
            project=project,
            path=checkout,
            branch=branch,
            requested_commit=requested,
            tested_commit=tested,
            origin_url=configured_origin,
        )
