# Manual guarded capture-only runner validation

The focused validation covers strict nonsecret configuration, deterministic
session/launch identities, guard contention and abandoned ownership, lineage
and production-hours fail-closed behavior, fixed SPY/QQQ policy binding,
Credential Manager reference isolation, pointer-selected attempt history,
readiness decision publication, exactly-one allocation, child-request and
process-evidence binding, successful and failed terminal publication, timeout
ambiguity, snapshot verification, selection, readiness re-evaluation, lease
release, redacted CLI output, and the no-scheduling boundary.

The tests use injected native/artifact boundaries and never connect to a real
brokerage or provision real credentials. The default DACL is intentionally
reported as unhardened, and unresolved official XNYS-hours provenance remains a
typed blocked result. The runner must not be described as unattended-ready.

Validation commands:

```text
.venv\Scripts\python.exe -m pytest -q tests\cli\test_guarded_capture_runner.py
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
git diff --check
```
