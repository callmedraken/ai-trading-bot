# Fixed-layout checkpoint transition output validation

Run from the repository root:

```text
.venv\Scripts\python.exe -m pytest tests\cli\test_checkpoint_transition.py -q
.venv\Scripts\python.exe -m pytest
.venv\Scripts\ruff.exe check --no-cache .
.venv\Scripts\ruff.exe format --check --no-cache .
git diff --check
```

Focused coverage preserves genesis-start behavior, creates and verifies the
fixed genesis layout, creates an accepted successor transition, and starts a
sequence-two cycle only after a complete explicit sequence-one producing edge
passes verification. It rejects missing, genesis-inapplicable, wrong, and
tampered predecessor-edge artifacts before execution, and proves
destination-local `ALREADY_APPLIED` returns byte-identical existing artifacts.
