# Fixed-layout checkpoint transition output validation

Run from the repository root:

```text
.venv\Scripts\python.exe -m pytest tests\cli\test_checkpoint_transition.py -q
.venv\Scripts\python.exe -m pytest
.venv\Scripts\ruff.exe check --no-cache .
.venv\Scripts\ruff.exe format --check --no-cache .
git diff --check
```

Focused coverage creates and verifies the fixed genesis layout, creates an
accepted successor transition, verifies its one edge offline, and proves
destination-local `ALREADY_APPLIED` returns byte-identical existing artifacts.
