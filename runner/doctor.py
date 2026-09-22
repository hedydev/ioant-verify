"""Read-only prerequisite and macOS permission preflight checks."""

from __future__ import annotations

import ctypes
import importlib.util
import platform
import shutil
import subprocess
import sys
from typing import Any


def _command(name: str) -> dict[str, Any]:
    path = shutil.which(name)
    return {"status": "pass" if path else "blocked", "path": path}


def _module(name: str) -> dict[str, Any]:
    present = importlib.util.find_spec(name) is not None
    return {"status": "pass" if present else "blocked", "present": present}


def _mac_permission(symbol: str, framework: str) -> dict[str, Any]:
    if platform.system() != "Darwin":
        return {"status": "not_applicable", "granted": None, "method": symbol}
    try:
        library = ctypes.CDLL(framework)
        function = getattr(library, symbol)
        function.restype = ctypes.c_bool
        granted = bool(function())
        return {"status": "pass" if granted else "blocked", "granted": granted, "method": symbol}
    except Exception as exc:
        return {"status": "unknown", "granted": None, "method": symbol, "detail": str(exc)}


def _simctl() -> dict[str, Any]:
    if shutil.which("xcrun") is None:
        return {"status": "blocked", "detail": "xcrun not found"}
    completed = subprocess.run(["xcrun", "simctl", "help"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, check=False, timeout=10)
    return {"status": "pass" if completed.returncode == 0 else "blocked", "detail": completed.stderr.strip() or None}


def doctor() -> dict[str, Any]:
    python_ok = sys.version_info >= (3, 11)
    core = {
        "python": {"status": "pass" if python_ok else "blocked", "version": platform.python_version(), "required": ">=3.11"},
        "git": _command("git"),
        "jsonschema": _module("jsonschema"),
        "yaml": _module("yaml"),
    }
    tooling = {
        "xcodebuild": _command("xcodebuild"),
        "xcrun": _command("xcrun"),
        "simctl": _simctl() if platform.system() == "Darwin" else {"status": "not_applicable", "detail": "Simulator checks require macOS"},
    }
    permissions = {
        "accessibility": _mac_permission("AXIsProcessTrusted", "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"),
        "screen_recording": _mac_permission("CGPreflightScreenCaptureAccess", "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"),
    }
    blocked_core = [name for name, item in core.items() if item["status"] != "pass"]
    overall = "blocked" if blocked_core else ("ready" if platform.system() == "Darwin" else "limited")
    return {
        "schema_version": 1,
        "overall": overall,
        "platform": {"system": platform.system(), "release": platform.release(), "machine": platform.machine()},
        "core": core,
        "tooling": tooling,
        "permissions": permissions,
        "notes": [
            "doctor never requests or bypasses macOS privacy permissions",
            "Accessibility and Screen Recording are required only by later suites that declare those capabilities",
            "Xcode/Simulator are reported now but are not required by the Phase 0 static demo suite",
        ],
    }
