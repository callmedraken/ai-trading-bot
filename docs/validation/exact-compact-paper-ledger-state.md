# Exact compact paper-ledger state validation

Run from the repository root:

```text
.venv\Scripts\python.exe -m pytest tests\ledger\test_checkpoint_state.py -q
.venv\Scripts\python.exe -m pytest
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
git diff --check
```

The focused suite covers cash-only, zero-cash invested, multi-position,
positive/negative realized-profit-and-loss, nonreconstructible partial-sale
basis, hostile Decimal contexts, ordering, pinned UUID5 identity, independent
restoration, exact-type and numeric bounds, signed zero, empty historical fill
membership, and equivalent future buy/sell accounting.

The complete suite retains the existing ledger, public initialization, state
fingerprint, verified-snapshot preparation/execution/report, and optimized
simulation regression coverage. Validation creates no report or checkpoint
artifact.
