# Ioant Verify — AI Entry

Read this file before changing anything in this repository.

## Mission

Ioant Verify is an external, exact-revision acceptance runner for AI-assisted development. It verifies consuming products without embedding acceptance-only behavior into them.

The current implementation priority is **Phase 0** from `hedydev/hero-skills/ideas/ioant-verify/CONCEPT.md`: trustworthy repository foundations, exact-SHA execution, schemas, local state, reports, self-test, doctor, and the project-adapter boundary. Do not begin IWB-specific automation until Phase 0 acceptance is proven.

## Required Hero Skills

Read `.hero-skills.yaml` and the pinned Hero Skills revision before implementation. At minimum, apply:

- `track-ai-development-tasks` + `ai-development-task-tracking`;
- `work-evidence-first` + `evidence-based-fixes` for defects;
- `git-safe-delivery` + `git-delivery`;
- `build-diagnostic-sessions` + `diagnostic-sessions`;
- `structure-modular-code` + `code-modularity`.

## Git authority and safety

- Canonical development branch: `main`.
- Before every shared-history write, resolve the exact remote `main` HEAD. If the repository is unborn, record that explicitly.
- Never reset, clean, stash, rebase, force-push, switch branches, merge branches, or delete branches merely to obtain a convenient state.
- Preserve unrelated work.
- Every AI-authored commit must carry `AI-Agent` and the current conversation's eight-character `AI-Session` trailers.
- Re-check the remote HEAD immediately before moving `main`, and verify the post-write remote SHA.
- Generated reports, local state databases, checkouts, caches, and temporary artifacts are not source history.

## Verification invariants

1. Never silently test "current main" when a specific commit was requested.
2. A logical verification identity is project + exact commit SHA + suite name + suite version; retries add an attempt number.
3. Keep product FAIL distinct from BLOCKED and INFRA_ERROR.
4. Preserve partial evidence on failures.
5. Unattended verification must use verifier-owned resources; it must not mutate a user's active product worktree.
6. Generic runner code must not contain product-specific paths or commands. Put those behind adapters.
7. Schema-validate AI-authored suite/config/report/state structures before execution or persistence.
8. Cleanup only resources owned by the run.
9. Simulator evidence never substitutes for real-device acceptance.
10. Chrome/dashboard work is optional and must never become the core executor.

## Phase 0 acceptance

Phase 0 is complete only when repository validation proves all of the following:

- `ioant-verify doctor` returns useful prerequisite/permission state without bypassing system security;
- suite/config/report/run-state schemas are present and validated;
- local state enforces exact logical identity and idempotency;
- a deterministic demo smoke suite produces a PASS JSON + Markdown report;
- the report visibly records identical requested and tested exact commit SHAs;
- a deliberate SHA mismatch is rejected rather than silently testing another revision;
- the adapter interface exists without IWB-specific implementation;
- self-test runs the complete Phase 0 smoke chain.

## Task ledger

The canonical AI development ledger is `.ai-work/` on `main`. AI-authored task history requires a registered current-session identity and append-only events. Automated validation is evidence; human acceptance is still required before task completion.

## Documentation

Keep current project architecture and implementation state in this repository. Hero Skills remains the reusable source of cross-project method. Do not present the incubating Ioant Verify concept as a validated Hero capability until implementation evidence justifies promotion.
