"""IWB-specific adapter; all product paths and commands live here."""

from __future__ import annotations

import platform
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from adapters.base import ProjectAdapter, RunContext
from ios.simulator import SimulatorController, SimulatorLease
from runner.process_manager import ProcessManager
from task_sync.ledger import active_projection, select_tasks


class IwbAdapter(ProjectAdapter):
    name = "iwb"
    bundle_id = "com.ioant.workbench.mobile"

    def __init__(self) -> None:
        self.processes = ProcessManager()
        self.simulator = SimulatorController()
        self.simulator_lease: SimulatorLease | None = None
        self.simulator_launched = False
        self._artifacts: list[Path] = []

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

    @staticmethod
    def _port_available(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                return False
        return True

    @staticmethod
    def _wait_for_metro(process: subprocess.Popen[str], port: int, timeout: float = 60.0) -> None:
        deadline = time.monotonic() + timeout
        last_error = "Metro did not become ready"
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"Metro exited before readiness with code {process.returncode}")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=1.0) as response:
                    body = response.read().decode("utf-8", errors="replace").strip()
                if body == "packager-status:running":
                    return
                last_error = f"unexpected Metro status response: {body!r}"
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = str(exc)
            time.sleep(0.25)
        raise RuntimeError(f"Metro readiness timed out on port {port}: {last_error}")

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
            "iwb.simulator.smoke": lambda params: self._simulator_smoke(context, params),
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

    def _simulator_smoke(self, context: RunContext, params: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        if platform.system() != "Darwin":
            return {
                "id": "simulator-smoke",
                "title": "IWB Native app launches on iOS Simulator",
                "result": "blocked",
                "expected": "macOS with Xcode Simulator",
                "observed": platform.system(),
                "duration_seconds": max(0.0, time.perf_counter() - started),
                "evidence": [],
                "failure_reason": "Simulator automation requires macOS",
            }
        if context.artifact_dir is None:
            raise RuntimeError("run artifact directory is unavailable")

        port = int(params.get("port", 18082))
        if port < 1 or port > 65535:
            raise ValueError("simulator Metro port must be between 1 and 65535")
        if not self._port_available(port):
            return {
                "id": "simulator-smoke",
                "title": "IWB Native app launches on iOS Simulator",
                "result": "blocked",
                "expected": f"IV-owned Metro port {port} is free",
                "observed": "port already in use",
                "duration_seconds": max(0.0, time.perf_counter() - started),
                "evidence": [],
                "failure_reason": "IV will not reuse or kill an unknown process on its configured Metro port",
            }

        mobile_dir = context.repo / "apps" / "mobile"
        requested_udid = params.get("udid")
        if requested_udid is not None and not isinstance(requested_udid, str):
            raise ValueError("simulator udid must be a string")

        try:
            device = self.simulator.select(udid=requested_udid)
            self.simulator_lease = self.simulator.ensure_booted(device)

            metro_log = context.artifact_dir / "metro.log"
            self._artifacts.append(metro_log)
            metro = self.processes.start(
                "metro",
                ["npm", "run", "start:metro", "--", "--host", "127.0.0.1", "--port", str(port)],
                cwd=mobile_dir,
                log_path=metro_log,
            )
            self._wait_for_metro(metro.process, port)

            install_case = self._command_case(
                case_id="simulator-install",
                title="Build and install exact IWB revision on Simulator",
                cwd=mobile_dir,
                command=["npm", "run", "ios:simulator", "--", "--port", str(port)],
            )
            if install_case["result"] != "pass":
                install_case["title"] = "IWB Native Simulator build/install"
                return install_case

            launch_output = self.simulator.launch(self.simulator_lease.device.udid, self.bundle_id)
            self.simulator_launched = True
            time.sleep(2.0)
            screenshot = self.simulator.screenshot(
                self.simulator_lease.device.udid,
                context.artifact_dir / "simulator.png",
            )
            self._artifacts.append(screenshot)
            return {
                "id": "simulator-smoke",
                "title": "IWB Native app launches on iOS Simulator",
                "result": "pass",
                "expected": self.bundle_id,
                "observed": launch_output or "simctl launch succeeded",
                "duration_seconds": max(0.0, time.perf_counter() - started),
                "evidence": [
                    f"simulator: {self.simulator_lease.device.name} ({self.simulator_lease.device.udid})",
                    f"runtime: {self.simulator_lease.device.runtime}",
                    f"metro_port: {port}",
                    f"metro_log: {metro_log}",
                    f"screenshot: {screenshot}",
                ],
                "failure_reason": None,
            }
        except Exception as exc:
            return {
                "id": "simulator-smoke",
                "title": "IWB Native app launches on iOS Simulator",
                "result": "infra_error",
                "expected": "Simulator + IV-owned Metro + exact IWB build launch successfully",
                "observed": type(exc).__name__,
                "duration_seconds": max(0.0, time.perf_counter() - started),
                "evidence": [str(path) for path in self._artifacts],
                "failure_reason": str(exc),
            }

    def cleanup(self, context: RunContext) -> None:
        errors: list[str] = []
        if self.simulator_lease is not None and self.simulator_launched:
            try:
                self.simulator.terminate(self.simulator_lease.device.udid, self.bundle_id)
            except Exception as exc:
                errors.append(f"terminate app: {exc}")
        try:
            self.processes.stop_all()
        except Exception as exc:
            errors.append(f"stop managed processes: {exc}")
        try:
            self.simulator.shutdown_if_owned(self.simulator_lease)
        except Exception as exc:
            errors.append(f"shutdown owned Simulator: {exc}")
        if errors:
            raise RuntimeError("; ".join(errors))

    def collect_diagnostics(self, context: RunContext) -> list[str]:
        return [str(path) for path in self._artifacts if path.exists()]
