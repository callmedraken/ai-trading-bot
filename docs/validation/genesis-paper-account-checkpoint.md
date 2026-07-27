# Genesis paper-account checkpoint validation

Run from the repository root:

```text
.venv\Scripts\python.exe -m pytest tests\runtime\test_paper_account_checkpoint.py -q
.venv\Scripts\python.exe -m pytest
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
git diff --check
```

The focused suite covers supported opening accounts, ordered positions and
metadata, exact partial-sale basis, pinned account/lineage/checkpoint/compact
and empty-engine identities, canonical bytes and artifact hash, strict parsing,
tampering, hostile Decimal contexts, bounded invalid inputs, absent references,
empty restored history, and PASS-only replay access. The complete suite retains
existing ledger, snapshot, cycle-report, and simulation behavior and does not
create a checkpoint artifact.
