# Verified-snapshot paper-cycle report validation

Run from the repository root:

```text
.venv\Scripts\python.exe -m pytest tests\runtime\test_verified_snapshot_serialization.py -q
.venv\Scripts\python.exe -m pytest
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
git diff --check
```

The focused suite pins canonical report bytes indirectly through the exact byte
length and SHA-256 together with preparation, runtime, adapter, engine-state,
and ledger-state UUIDs. It also proves strict round-trip parsing, byte-identical
independent executions, hostile Decimal-context isolation, exactly one runtime
replay, and complete PASS-only result access.

Negative vectors cover invalid UTF-8, BOM, duplicate/missing/unknown fields,
comments or trailing input, wrong schema, JSON floats and constants,
noncanonical UUID/hash/timestamp/Decimal values, reordered JSON, outer
hash/length mismatch, mismatched snapshot bytes, and independent tampering of
snapshot linkage, marks, account state, bootstrap evidence, quantity and cash
targets, asserted opening references, policy, timestamps, preparation identity,
planner/proposal/risk/order/fill evidence, state IDs, final account state,
status, and adapter result identity.

Provider, network, and filesystem sentinels must remain uncalled. No generated
report is created or modified by validation.

The CLI suite also validates strict cycle configuration parsing, no-clobber
report staging, report replay, quiet output, and stable failure exit codes.
