"""Ioant Verify command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .configuration import load_config
from .doctor import doctor
from .execution import ExecutionEngine
from .locks import heavy_run_lock
from .schema import load_json, validate_instance
from .self_test import run_self_test
from .state_store import StateStore


def _print_json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def _doctor(args: argparse.Namespace) -> int:
    result = doctor()
    if args.json:
        _print_json(result)
    else:
        print(f"Ioant Verify doctor: {result['overall'].upper()}")
        for section in ("core", "tooling", "permissions"):
            print(f"\n{section}:")
            for name, item in result[section].items():
                print(f"  {name}: {item['status']}")
        for note in result["notes"]:
            print(f"\n- {note}")
    return 2 if result["overall"] == "blocked" else 0


def _validate_suite(args: argparse.Namespace) -> int:
    suite = load_json(args.path)
    validate_instance(suite, "suite.schema.json")
    print(f"valid suite: {suite['name']} v{suite['version']} ({suite['project']})")
    return 0


def _run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    engine = ExecutionEngine(state_db=config["state_db"], report_root=config["report_root"], diagnostics_root=config["diagnostics_root"])
    lock_path = Path(config["state_db"]).with_suffix(".lock")
    with heavy_run_lock(lock_path):
        record, report, created = engine.run(project=args.project, adapter_name=args.adapter, repo=args.repo, requested_commit=args.commit.lower(), suite_path=args.suite, mode=args.mode, rerun=args.rerun)
    payload = {"created": created, "state": record.as_dict(), "report": report}
    if args.json:
        _print_json(payload)
    else:
        print(f"{report['result'].upper()} {report['suite']} attempt={report['attempt']}")
        print(f"requested: {report['requested_commit']}")
        print(f"tested:    {report['tested_commit']}")
        print(f"report:    {record.report_dir}")
        if not created:
            print("idempotent: existing logical run returned")
    return 0 if report["result"] == "pass" else 1


def _latest(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    record = StateStore(config["state_db"]).latest(project=args.project, commit=args.commit)
    if record is None:
        return 1
    if args.json:
        _print_json(record.as_dict())
    else:
        print(f"{record.result or record.lifecycle_state} {record.project} {record.suite} attempt={record.attempt}")
        print(f"requested: {record.requested_commit}")
        print(f"tested:    {record.tested_commit}")
        print(f"report:    {record.report_dir}")
    return 0


def _self_test(args: argparse.Namespace) -> int:
    result = run_self_test()
    if args.json:
        _print_json(result)
    else:
        print("Ioant Verify Phase 0 self-test: PASS")
        for name, passed in result["checks"].items():
            print(f"  {'PASS' if passed else 'FAIL'} {name}")
        print(f"  requested: {result['requested_commit']}")
        print(f"  pass tested: {result['pass_tested_commit']}")
        print(f"  mismatch tested: {result['mismatch_tested_commit']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ioant-verify", description="Exact-revision external acceptance runner")
    parser.add_argument("--config", help="local YAML configuration path")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor_parser = sub.add_parser("doctor", help="inspect prerequisites and macOS permission state")
    doctor_parser.add_argument("--json", action="store_true")
    doctor_parser.set_defaults(func=_doctor)

    validate = sub.add_parser("validate-suite", help="schema-validate a suite file")
    validate.add_argument("path")
    validate.set_defaults(func=_validate_suite)

    run = sub.add_parser("run", help="run one exact-SHA suite")
    run.add_argument("--project", required=True)
    run.add_argument("--adapter", required=True)
    run.add_argument("--repo", required=True)
    run.add_argument("--commit", required=True, help="full 40-character commit SHA")
    run.add_argument("--suite", required=True)
    run.add_argument("--mode", required=True, choices=["none", "static", "simulator", "mac", "mac+simulator", "device-required", "manual-only"])
    run.add_argument("--rerun", action="store_true", help="create a new attempt for the same logical identity")
    run.add_argument("--json", action="store_true")
    run.set_defaults(func=_run)

    latest = sub.add_parser("latest", help="show latest persisted run")
    latest.add_argument("--project")
    latest.add_argument("--commit")
    latest.add_argument("--json", action="store_true")
    latest.set_defaults(func=_latest)

    self_test = sub.add_parser("self-test", help="run isolated deterministic Phase 0 acceptance")
    self_test.add_argument("--json", action="store_true")
    self_test.set_defaults(func=_self_test)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"ioant-verify: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
