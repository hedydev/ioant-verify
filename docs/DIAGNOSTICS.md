# Diagnostics Architecture

Ioant Verify uses the Hero Skills `cli-worker` diagnostic profile.

## Session identity

Every verification run ID is also the verifier diagnostic session ID. Long-running operations use the same value as the initial operation ID in Phase 0; later adapters may create narrower operation IDs for build, launch, fixture and case execution.

## Durable sink

Verifier diagnostics are append-only JSON Lines files under the configured `diagnostics_root`:

```text
<diagnostics_root>/<run-id>.jsonl
```

The runner writes diagnostics during execution instead of waiting until the report succeeds, so exact-SHA rejection and verifier exceptions leave evidence.

## Redaction

Structured diagnostic serialization redacts exact keys commonly used for credentials:

- token;
- password;
- secret;
- authorization;
- cookie;
- api_key.

Adapters must still avoid dumping arbitrary environments, headers, user files or command arguments.

## Retention

Phase 0 intentionally does not auto-delete diagnostic sessions. The default directory is outside the source repository. Before unattended long-running operation is enabled, retention limits by age/count/bytes must be added and validated.

## Export

The Phase 0 report references its JSONL diagnostic path. A bounded diagnostic ZIP/export format belongs to a later phase when product logs and screenshots exist.

## Failure semantics

- exact revision mismatch → `INFRA_ERROR`;
- verifier exception → `INFRA_ERROR`;
- missing later-phase permission/resource → `BLOCKED`;
- deterministic product assertion mismatch → `FAIL`.

Diagnostics never rewrite these classifications.
