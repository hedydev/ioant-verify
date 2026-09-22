# Ioant Verify Architecture — Phase 0

## Boundary

Phase 0 proves the verifier can be trusted before any product automation is added.

```text
CLI
→ schema validation
→ exact Git revision inspection
→ idempotent SQLite run ledger
→ project adapter
→ execution engine
→ durable diagnostics
→ schema-validated JSON + Markdown report
```

IWB-specific paths, commands, bundle identifiers, Simulator settings and fixtures are intentionally absent.

## Exact revision contract

Every run accepts a **full 40-character commit SHA**. The runner resolves both:

```text
requested_commit = git rev-parse <requested>^{commit}
tested_commit    = git rev-parse HEAD^{commit}
```

The Phase 0 adapter only executes when they are identical. A mismatch is `INFRA_ERROR`, never `FAIL`, and the report preserves both SHAs.

Phase 1 will replace the current active-checkout preparation with a verifier-owned dedicated clone/check-out strategy. The exact-SHA report contract remains unchanged.

## Logical identity and attempts

The SQLite logical key is:

```text
project + requested commit + suite + suite version
```

The same logical request returns the existing run by default. `--rerun` creates the next attempt while preserving the same logical identity.

## State lifecycle

The state ledger records transitions based on the concept model:

```text
DISCOVERED
→ QUEUED
→ PREPARING
→ RUNNING
→ COLLECTING
→ EVALUATING
→ PASS / FAIL / BLOCKED / INFRA_ERROR / SKIPPED
→ ARCHIVED
```

`result` is stored separately from final `ARCHIVED` lifecycle state.

## Adapter boundary

`adapters/base.py` owns the stable project adapter contract. Generic runner code does not know product-specific paths or commands.

The `demo` adapter is deliberately internal and deterministic. Its only job is to prove the Phase 0 chain and exact-SHA enforcement.

## Report contract

Every report is schema-validated before persistence and includes:

- run ID;
- project;
- requested and tested exact SHAs;
- suite name/version;
- attempt;
- mode;
- start/finish times;
- result;
- environment;
- cases;
- artifact references;
- device-required follow-ups.

The report writer emits both `report.json` and `report.md`.

## Concurrency and ownership

Phase 0 uses a process file lock for one heavy run at a time. Later phases can add per-project locks while preserving the global heavy-run gate.

Cleanup and future process control must apply only to verifier-owned resources. Ioant Verify must never kill arbitrary user applications by name.

## Deferred to Phase 1+

- verifier-owned dedicated project clones/checkouts;
- IWB Adapter;
- native macOS deterministic fixture;
- Accessibility-driven product interactions;
- screenshot/log collection beyond verifier diagnostics;
- iOS Simulator and XCUITest;
- commit watcher and trailer scheduler;
- Chrome dashboard/native messaging.
