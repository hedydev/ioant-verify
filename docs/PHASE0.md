# Phase 0 Acceptance Plan

Phase 0 exists to prove trustworthiness before IWB automation begins.

## Automated evidence

Run:

```bash
bash scripts/verify-self-test.sh
```

Required outcomes:

1. unit tests pass;
2. demo suite validates against `suite.schema.json`;
3. isolated exact-SHA smoke attempt 1 is `PASS`;
4. duplicate request reuses attempt 1;
5. manual retry after advancing HEAD becomes attempt 2 and `INFRA_ERROR`;
6. mismatch report retains both requested and tested SHAs;
7. JSON and Markdown reports both exist;
8. doctor returns structured prerequisite/permission state.

## Human review boundary

Automated validation does not complete the AI development task. The task remains awaiting human acceptance until the user reviews the Phase 0 evidence.

## Next allowed work

Only after Phase 0 acceptance:

- add the IWB adapter;
- add verifier-owned checkout preparation;
- add the first deterministic Mac fixture/smoke suite.

Do not start Chrome extension/dashboard work yet.
