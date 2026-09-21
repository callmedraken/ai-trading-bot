# GUI-A9 Read-Only System Health and Audit Validation Plan

## 1. Purpose

Validate Architecture 116,
`docs/architecture/116-gui-system-health-audit.md`.

GUI-A9 must derive System Health entirely from already-acquired GUI presentation
state.

## 2. A9a model/adapter gate

Add Qt-free models and a pure adapter.

Verify:

- exact enum/type validation;
- bounded component count and audit-entry count;
- bounded text;
- exact lowercase SHA-256 validation;
- deterministic ordering;
- no object retention beyond presentation values;
- no I/O imports in the adapter.

## 3. Status mapping gate

Cover all relevant status combinations.

Expected rules:

```text
Research LOADED                       AVAILABLE
Research UNAVAILABLE                  UNAVAILABLE

Paper UNAVAILABLE                     UNAVAILABLE
Paper PENDING / ALREADY_APPLIED       AVAILABLE
Paper BLOCKED / CONFLICTING           BLOCKED

Paper Account VERIFIED                AVAILABLE
Paper Account UNAVAILABLE             UNAVAILABLE

Market Data VERIFIED                  AVAILABLE
Market Data UNAVAILABLE               UNAVAILABLE

Operations UNAVAILABLE                UNAVAILABLE
Operations AVAILABLE + all gates shut AVAILABLE
Operations blocked preview            BLOCKED
Operations any displayed gate open    BLOCKED
```

Overall status is `ATTENTION` only when at least one component is BLOCKED.

## 4. Audit evidence gate

For loaded/verified/inspected state, copy only bounded presentation evidence.

Verify:

- Research: report ID and experiment result ID;
- Paper: operation ID, terminal checkpoint ID, application ID;
- Paper Account: checkpoint ID and artifact SHA-256;
- Market Data: snapshot ID and artifact SHA-256;
- Operations: selected snapshot ID when present and account checkpoint ID when
  present.

Assert that source paths, receipt paths, exception text, credentials, authority
objects, and provider bodies are absent.

## 5. MainWindow gate

Update MainWindow to:

1. call each existing service getter once;
2. build the A9 state from those local variables;
3. add `SystemHealthPage`;
4. preserve all page IDs/order.

No `get_system_health_state()` service method is permitted in A9.

Tests must prove navigation to/from System does not increase service call count.

## 6. Qt page gate

The page must contain:

- `System Health & Audit`;
- read-only/no-authority scope notice;
- overall health label;
- environment/mode;
- component status presentation;
- selectable audit identifier/hash fields.

No QPushButton or effect control is required or permitted.

## 7. Focused regression

Run at least:

```text
tests/gui/test_gui_a9_system_health_models.py
tests/gui/test_gui_a9_system_health_adapter.py
tests/gui/test_gui_a9_system_health_page_qt.py
tests/gui/test_main_window.py
tests/gui/test_gui_models.py
tests/gui/test_gui_a8_startup_composition.py
```

Then run the entire `tests/gui` suite.

Use a fresh external `--basetemp` and `-p no:cacheprovider`.

## 8. Static gate

Run:

```text
ruff check src/trading_bot/gui tests/gui
ruff format --check src/trading_bot/gui tests/gui
git diff --check
git diff --cached --check
```

## 9. Visual gate

Inspect default and A8-populated startups at 1180x760 and 920x620.

Confirm:

- no clipping that hides the status meaning;
- long IDs/hashes remain selectable;
- unavailable is neutral;
- blocked/attention is clearly distinct;
- page never claims production readiness;
- no effect controls exist.

## 10. Final certification

After the final semantic source tree and visual PASS:

1. run the broad repository suite excluding the two Architecture-77 modules;
2. run the two Architecture-77 modules from a clean detached exact-tree
   worktree;
3. run repository-wide Ruff and diff checks;
4. verify exact HEAD/tree/status;
5. perform independent GitHub diff review.

## 11. Stop conditions

Stop before implementation proceeds if A9 would require:

- a new runtime reader;
- production O2 invocation;
- C1/C2/C3 access;
- filesystem discovery;
- Task Scheduler inspection;
- Credential Manager;
- provider/broker network access;
- D8/D9 invocation;
- recovery/retry/mutation.

Those belong to a later separately reviewed architecture boundary.

## 12. Next candidate

After A9 integration, the next safe GUI candidate should be selected from
read-only audit/history presentation that can consume explicit offline artifacts
without current-production discovery. Operational controls remain deferred.
