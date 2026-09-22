"""Validated JSON + Markdown evidence report writer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import validate_instance


class ReportWriter:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def write(self, report: dict[str, Any]) -> Path:
        validate_instance(report, "report.schema.json")
        run_dir = self.root / report["project"] / report["requested_commit"] / report["run_id"]
        run_dir.mkdir(parents=True, exist_ok=True)
        json_path = run_dir / "report.json"
        json_path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        (run_dir / "report.md").write_text(self._markdown(report), encoding="utf-8")
        return run_dir

    @staticmethod
    def _markdown(report: dict[str, Any]) -> str:
        lines = [
            "# Ioant Verify Report",
            "",
            f"- **Run:** `{report['run_id']}`",
            f"- **Project:** `{report['project']}`",
            f"- **Suite:** `{report['suite']} v{report['suite_version']}`",
            f"- **Attempt:** `{report['attempt']}`",
            f"- **Mode:** `{report['mode']}`",
            f"- **Result:** **{report['result'].upper()}**",
            f"- **Requested commit:** `{report['requested_commit']}`",
            f"- **Tested commit:** `{report['tested_commit'] or 'unavailable'}`",
            "",
            "## Cases",
            "",
        ]
        for case in report["cases"]:
            lines.extend([
                f"### {case['result'].upper()} — {case['title']}",
                "",
                f"- id: `{case['id']}`",
                f"- expected: `{case['expected']}`",
                f"- observed: `{case['observed']}`",
                f"- duration: `{case['duration_seconds']:.6f}s`",
                f"- failure reason: `{case['failure_reason'] or 'none'}`",
                "",
            ])
        lines.extend(["## Device-required follow-ups", ""])
        if report["device_required_followups"]:
            lines.extend(f"- {item}" for item in report["device_required_followups"])
        else:
            lines.append("- none")
        lines.append("")
        return "\n".join(lines)
