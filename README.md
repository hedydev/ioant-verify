# Ioant Verify

Ioant Verify is a Mac-local external acceptance runner for AI-assisted product development. Its first invariant is simple: **the report must prove which exact Git commit was tested**.

Phase 0 intentionally contains no IWB-specific automation. It establishes the generic trust chain first:

```text
exact commit request
→ schema-validated suite
→ idempotent local run state
→ adapter boundary
→ deterministic execution
→ JSON + Markdown evidence report
```

## Requirements

- Python 3.11+
- Git
- macOS for the full doctor permission checks
- Xcode tools are reported by `doctor` but are not required for the Phase 0 demo suite

Install for development:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

## Phase 0 commands

Inspect prerequisites without changing system permissions:

```bash
ioant-verify doctor
ioant-verify doctor --json
```

Validate a declarative suite:

```bash
ioant-verify validate-suite adapters/demo/suites/demo-smoke.json
```

Run the deterministic self-test:

```bash
ioant-verify self-test
```

The self-test creates an isolated temporary Git repository. Attempt 1 tests its exact HEAD and must PASS. It then advances HEAD and manually retries the original logical test identity; attempt 2 must become `INFRA_ERROR` because requested and tested SHAs differ. This proves Ioant Verify does not silently substitute the current revision.

Run a suite explicitly:

```bash
SHA="$(git rev-parse HEAD)"
ioant-verify run \
  --project demo \
  --adapter demo \
  --repo . \
  --commit "$SHA" \
  --suite adapters/demo/suites/demo-smoke.json \
  --mode static
```

By default local state and generated reports live under:

```text
~/Library/Application Support/IoantVerify/
```

See `config/local.example.yaml` for the complete configuration shape.

## Result semantics

- `PASS`: product assertions passed.
- `FAIL`: product behavior violated a deterministic assertion.
- `BLOCKED`: an explicitly required permission/device/resource is unavailable.
- `INFRA_ERROR`: verifier/environment/revision preparation failed.
- `SKIPPED`: a case is not applicable.

Infrastructure errors are never converted into product failures.

## Next phase boundary

IWB Adapter, verifier-owned checkouts, macOS fixture automation and iOS Simulator/XCUITest belong to later phases. They should start only after the Phase 0 acceptance evidence is reviewed.
