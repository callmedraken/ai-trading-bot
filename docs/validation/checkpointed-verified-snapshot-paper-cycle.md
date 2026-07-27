# Checkpointed verified-snapshot paper-cycle validation

Run from the repository root:

```text
.venv\Scripts\python.exe -m pytest tests\runtime\test_checkpointed_verified_snapshot_execution.py -q
.venv\Scripts\python.exe -m pytest
.venv\Scripts\ruff.exe check --no-cache .
.venv\Scripts\ruff.exe format --check --no-cache .
git diff --check
```

The focused suite covers verified genesis restoration, nonzero positive and
negative cumulative realized profit and loss, authoritative total-basis
preservation, zero-cash invested state, buys, partial and full sells, mixed
sell/buy ordering, commissions, no action, complete risk rejection, resized and
mixed risk outcomes, atomic gap-up failure, exact one-call runtime invocation,
reserved metadata, pinned deterministic application and result identities,
equal independent execution, ambient Decimal isolation, result reconciliation,
private-state containment, complete-PASS enforcement, and provider, network,
filesystem, and broker-boundary sentinels.

The complete suite retains the existing standalone verified-cycle report bytes
and identities, compact-state and genesis-checkpoint identities, ledger
behavior, simulations, and daily-snapshot behavior. Validation creates no
checkpoint, cycle, report, or other generated artifact.
