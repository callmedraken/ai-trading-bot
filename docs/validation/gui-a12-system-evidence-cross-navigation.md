# GUI-A12 Read-Only System / Evidence Cross-Navigation Validation Plan

## Purpose

Validate Architecture 119,
`docs/architecture/119-gui-system-evidence-cross-navigation.md`.

A12 must remain page coordination over already-built bounded presentation state.

## A12a pure navigation target gate

Add the immutable Qt-free navigation target and exact System-source mapper.

Verify:

- exact `EvidenceTimelineSource` validation;
- canonical bounded identifier;
- exact closed source mapping;
- unknown source fails closed;
- no retained path/hash/runtime object;
- no I/O import.

## A12b System page gate

Add a presentation-only `View in Evidence` control to mappable System audit
cards.

Verify:

- one target is emitted per selected card;
- control is absent for unmappable sources;
- audit identifiers/hashes remain read-only/selectable;
- System state is not mutated;
- no execution/effect control is added.

## A12c MainWindow / Evidence integration gate

Wire System navigation through `MainWindow` to the existing Evidence Explorer.

Verify:

- navigation selects page ID `evidence`;
- Evidence source filter is the exact mapped source;
- Evidence search is the exact audit identifier;
- resulting visible cards match that source/identifier;
- Evidence scroll resets to the top;
- service call count remains exactly six.

## A12d regression gate

At minimum run:

```text
tests/gui/test_gui_a12_system_evidence_navigation.py
tests/gui/test_gui_a9_system_health_page_qt.py
tests/gui/test_gui_a10_evidence_timeline_page_qt.py
tests/gui/test_gui_a11_evidence_explorer.py
tests/gui/test_main_window.py
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

Use a populated read-only startup and inspect System -> Evidence transitions.

Cover at least:

- Research audit entry;
- Market Data or Paper Account audit entry;
- 920x620 minimum size.

Confirm:

- `View in Evidence` is clearly navigation, not an action/effect;
- exact source and identifier filters are visible after navigation;
- matching evidence remains readable/selectable;
- read-only/not-authority scope remains visible;
- no path, receipt, credential, authority, scheduler, or effect data appears.

## Final certification

After visual PASS:

1. broad repository suite excluding the two Architecture-77 modules;
2. Architecture-77 from a clean detached exact-tree harness;
3. repository-wide Ruff/diff checks;
4. exact HEAD/tree/status verification;
5. independent GitHub diff review.

## Stop conditions

Stop and redesign before adding:

- service rereads for navigation;
- filesystem/artifact discovery;
- runtime authority or capability objects;
- production O2/C1/C2/C3;
- credentials or scheduler access;
- provider/broker calls;
- paper/live execution;
- settlement/recovery;
- durable writes.
