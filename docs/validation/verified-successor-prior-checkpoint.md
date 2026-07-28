# Verified successor prior checkpoint validation

Run from the repository root:

```text
.venv\Scripts\python.exe -m pytest tests\runtime\test_checkpointed_paper_cycle_successor.py -q
.venv\Scripts\python.exe -m pytest
.venv\Scripts\ruff.exe check --no-cache .
.venv\Scripts\ruff.exe format --check --no-cache .
git diff --check
```

Focused coverage proves that a complete first successor edge creates a verified
prior, the compact state starts a later cycle exactly, the later report and
second successor edge replay with explicitly supplied immediate dependencies,
and unrelated predecessor bytes fail closed.
