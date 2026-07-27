# Successor paper-account checkpoint edge validation

Run from the repository root:

```text
.venv\Scripts\python.exe -m pytest tests\runtime\test_checkpointed_paper_cycle_successor.py -q
.venv\Scripts\python.exe -m pytest
.venv\Scripts\ruff.exe check --no-cache .
.venv\Scripts\ruff.exe format --check --no-cache .
git diff --check
```

The focused suite covers applied, no-action, partial-sale, and full-sale
successors; canonical report and checkpoint round trips; exact final compact
state and P&L retention; deterministic successor identities; supplied artifact
hash and length evidence; strict report and successor tampering; canonical
identity-preserving report tampering; exactly one replay invocation; and
PASS-only exposure of reconstructed state.

The complete suite retains standalone verified-snapshot report schemas, bytes,
identities, and verifier behavior, alongside existing checkpoint, ledger,
backtesting, and simulation behavior. Validation creates no tracked artifact.
