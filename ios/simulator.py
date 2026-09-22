"""Deterministic, ownership-aware iOS Simulator control via simctl."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SimulatorDevice:
    udid: str
    name: str
    state: str
    runtime: str


@dataclass(frozen=True)
class SimulatorLease:
    device: SimulatorDevice
    booted_by_verify: bool


def _runtime_key(runtime: str) -> tuple[int, ...]:
    match = re.search(r"iOS-(\d+(?:-\d+)*)$", runtime)
    if not match:
        return (0,)
    return tuple(int(part) for part in match.group(1).split("-"))


class SimulatorController:
    @staticmethod
    def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            ["xcrun", "simctl", *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if check and completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or "simctl command failed"
            raise RuntimeError(detail)
        return completed

    def available_devices(self, *, name_prefix: str = "iPhone") -> list[SimulatorDevice]:
        payload = json.loads(self._run("list", "devices", "available", "--json").stdout)
        devices: list[SimulatorDevice] = []
        for runtime, entries in (payload.get("devices") or {}).items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                name = str(entry.get("name") or "")
                if name_prefix and not name.startswith(name_prefix):
                    continue
                if entry.get("isAvailable") is False:
                    continue
                udid = str(entry.get("udid") or "")
                if not udid:
                    continue
                devices.append(
                    SimulatorDevice(
                        udid=udid,
                        name=name,
                        state=str(entry.get("state") or "Unknown"),
                        runtime=str(runtime),
                    )
                )
        return devices

    def select(self, *, udid: str | None = None, name_prefix: str = "iPhone") -> SimulatorDevice:
        devices = self.available_devices(name_prefix=name_prefix)
        if udid:
            matches = [device for device in devices if device.udid == udid]
            if len(matches) != 1:
                raise RuntimeError(f"requested Simulator UDID is not uniquely available: {udid}")
            return matches[0]

        booted = [device for device in devices if device.state == "Booted"]
        if len(booted) > 1:
            names = ", ".join(f"{device.name} ({device.udid})" for device in booted)
            raise RuntimeError(f"multiple booted iPhone Simulators; specify a UDID: {names}")
        if len(booted) == 1:
            return booted[0]
        if not devices:
            raise RuntimeError(f"no available Simulator matches prefix {name_prefix!r}")

        devices.sort(key=lambda device: (_runtime_key(device.runtime), device.name, device.udid), reverse=True)
        return devices[0]

    def ensure_booted(self, device: SimulatorDevice) -> SimulatorLease:
        if device.state == "Booted":
            return SimulatorLease(device=device, booted_by_verify=False)
        self._run("boot", device.udid)
        self._run("bootstatus", device.udid, "-b")
        return SimulatorLease(
            device=SimulatorDevice(
                udid=device.udid,
                name=device.name,
                state="Booted",
                runtime=device.runtime,
            ),
            booted_by_verify=True,
        )

    def launch(self, udid: str, bundle_id: str) -> str:
        return self._run("launch", udid, bundle_id).stdout.strip()

    def terminate(self, udid: str, bundle_id: str) -> None:
        completed = self._run("terminate", udid, bundle_id, check=False)
        if completed.returncode not in (0, 3):
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(detail or f"failed to terminate {bundle_id}")

    def screenshot(self, udid: str, path: str | Path) -> Path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        self._run("io", udid, "screenshot", str(output))
        return output

    def shutdown_if_owned(self, lease: SimulatorLease | None) -> None:
        if lease is None or not lease.booted_by_verify:
            return
        self._run("shutdown", lease.device.udid)
