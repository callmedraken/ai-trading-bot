# GUI-A10 Read-Only Evidence Timeline Validation Plan

## Purpose

Validate Architecture 117,
`docs/architecture/117-gui-read-only-evidence-timeline.md`.

A10 must remain pure presentation composition over states already acquired by
`MainWindow`.

## A10a model/adapter gate

Add immutable Qt-free timeline models and a pure adapter.

Verify:
- exact enum/type validation;
- bounded text/counts;
- exact lowercase SHA-256 validation;
- timezone-aware timestamps;
- deterministic ordering;
- no retained paths or runtime objects;
- no I/O imports.

## A10b mapping gate

Cover:
- Research loaded/unavailable;
- Paper inspected/unavailable;
- Paper Account verified/unavailable;
- Market Data verified/unavailable;
- Operations available/unavailable.

Assert:
- Market Data uses `captured_at`;
- Paper Account uses `as_of`;
- untimed Research/Paper entries follow timed entries;
- source and receipt paths never appear;
- Operations fields are presentation-only.

## A10c MainWindow/page gate

Add `evidence` to stable page IDs and navigation.

MainWindow must still perform exactly six service reads. It builds the timeline
from local state variables already acquired for the existing pages.

Tests must prove Evidence navigation performs no additional service call.

The page must use read-only selectable fields for identifiers/hashes and expose
no button/effect control.

## A10d regression gate

Run at least:

```text
tests/gui/test_gui_a10_evidence_timeline_models.py
tests/gui/test_gui_a10_evidence_timeline_adapter.py
tests/gui/test_gui_a10_evidence_timeline_page_qt.py
tests/gui/test_main_window.py
tests/gui/test_gui_models.py
tests/gui/test_gui_a8_startup_composition.py
tests/gui/test_gui_a9_system_health_adapter.py
tests/gui/test_gui_a9_system_health_page_qt.py
```

Then run all `tests/gui`.

Use a fresh external `--basetemp` and `-p no:cacheprovider`.

## Static gate

Run:

```text
ruff check src/trading_bot/gui tests/gui
ruff format --check src/trading_bot/gui tests/gui
git diff --check
git diff --cached --check
```

## Visual gate

Inspect default and populated startup at 1180x760 plus successor startup at
920x620.

Confirm:
- zero-state is truthful;
- newest timed evidence is first;
- untimed evidence follows timed evidence;
- IDs/hashes remain selectable;
- no path, receipt, credential, authority, or effect data appears;
- no effect controls exist.

## Final certification

After visual PASS:
1. run the broad repository suite excluding the two Architecture-77 modules;
2. run Architecture-77 from a clean detached exact-tree worktree;
3. run repository-wide Ruff/diff checks;
4. verify exact HEAD/tree/status;
5. perform independent GitHub diff review.

## Stop conditions

Stop and redesign before adding any:
- new runtime reader;
- filesystem discovery/latest selection;
- production O2/C1/C2/C3 access;
- Credential Manager access;
- scheduler access;
- provider/broker call;
- D8/D9 invocation;
- recovery/retry/mutation.
