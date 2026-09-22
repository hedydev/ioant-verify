"""Owned subprocess lifecycle for verifier-started background services."""

from __future__ import annotations

import os
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Mapping


@dataclass
class ManagedProcess:
    name: str
    process: subprocess.Popen[str]
    log_path: Path
    log_handle: IO[str]

    @property
    def pid(self) -> int:
        return self.process.pid


class ProcessManager:
    def __init__(self) -> None:
        self._processes: dict[str, ManagedProcess] = {}

    def start(
        self,
        name: str,
        command: list[str],
        *,
        cwd: str | Path,
        log_path: str | Path,
        env: Mapping[str, str] | None = None,
    ) -> ManagedProcess:
        if name in self._processes:
            raise RuntimeError(f"managed process already exists: {name}")
        if not command:
            raise ValueError("command must not be empty")
        log = Path(log_path)
        log.parent.mkdir(parents=True, exist_ok=True)
        handle = log.open("w", encoding="utf-8")
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        try:
            process = subprocess.Popen(
                command,
                cwd=str(Path(cwd)),
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
                env=merged_env,
                start_new_session=True,
            )
        except Exception:
            handle.close()
            raise
        managed = ManagedProcess(name, process, log, handle)
        self._processes[name] = managed
        return managed

    def get(self, name: str) -> ManagedProcess | None:
        return self._processes.get(name)

    def stop(self, name: str, *, timeout: float = 10.0) -> None:
        managed = self._processes.pop(name, None)
        if managed is None:
            return
        process = managed.process
        try:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
        finally:
            managed.log_handle.flush()
            managed.log_handle.close()

    def stop_all(self) -> None:
        errors: list[Exception] = []
        for name in list(reversed(self._processes)):
            try:
                self.stop(name)
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise RuntimeError("; ".join(str(error) for error in errors))
