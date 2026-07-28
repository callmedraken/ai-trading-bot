# Full-lineage offline verification validation

Run from the repository root:

```text
.venv\Scripts\python.exe -m pytest tests\runtime\test_paper_account_lineage_verification.py tests\cli\test_checkpoint_lineage.py -q
.venv\Scripts\python.exe -m pytest
.venv\Scripts\ruff.exe check --no-cache .
.venv\Scripts\ruff.exe format --check --no-cache .
git diff --check
.venv\Scripts\python.exe -c "from trading_bot.runtime import PaperAccountLineageEvidence, verify_paper_account_lineage"
.venv\Scripts\python.exe scripts\verify_paper_account_lineage.py --help
```

Focused runtime coverage verifies genesis-only, one-edge, multi-edge, APPLIED,
NO_ACTION, cumulative negative and positive realized P&L, exact total-cost-basis
carry-forward, deterministic evidence identity, exact-reference deduplication,
missing artifacts, duplicate-ID and duplicate-byte conflicts, snapshot mismatch,
forks, unreachable terminals, and external-I/O sentinels. Manifest coverage
verifies strict fields, safe regular files, hostile link rejection where the
platform permits link creation, ignored unlisted files, command execution, and
equal evidence from different filesystem roots.
