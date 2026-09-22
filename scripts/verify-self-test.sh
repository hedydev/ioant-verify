#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m pytest -q
python -m runner.main validate-suite adapters/demo/suites/demo-smoke.json
python -m runner.main self-test --json
python -m runner.main doctor --json
