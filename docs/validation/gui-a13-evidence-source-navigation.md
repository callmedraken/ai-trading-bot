# GUI-A13 Read-Only Evidence -> Source Page Navigation Validation Plan

## Purpose

Validate Architecture 120,
`docs/architecture/120-gui-evidence-source-navigation.md`.

A13 must remain page coordination over already-acquired GUI presentation state.

## A13a pure target gate

Add the Qt-free closed source-page enum/target and mapper.

Verify:

- exact enum validation;
- exact closed mapping for all five Evidence sources;
- mismatched source/page pairs fail explicitly;
- target retains no identifier/hash/path/runtime object;
- mapper performs no I/O.

## A13b Evidence page gate

Add one presentation-only `View source page` control to rendered evidence
cards.

Verify:

- one target emitted per card;
- filtering does not change target source;
- read-only identifier/hash fields remain selectable;
- no execution/effect semantics are introduced.

## A13c MainWindow integration gate

Wire the Evidence signal through `MainWindow`.

Verify:

- Research target selects page ID `research`;
- Paper Operation target selects `paper`;
- Paper Account target selects `paper-account`;
- Market Data target selects `market-data`;
- Operations target selects `operations`;
- service call count remains exactly six.

Do not add destination-page rereads or exact-row-selection claims.

## A13d regression gate

At minimum run:

```text
tests/gui/test_gui_a13_evidence_source_navigation.py
tests/gui/test_gui_a12_system_evidence_navigation.py
tests/gui/test_gui_a11_evidence_explorer.py
tests/gui/test_gui_a10_evidence_timeline_page_qt.py
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

At 920x620 inspect a populated Evidence page and navigate:

- Research evidence -> Research page;
- Market Data evidence -> Market Data page.

Confirm:

- controls fit cleanly;
- they read as navigation, not an operational action;
- destination pages are already-rendered page state;
- no extra loading/discovery appears;
- no path, receipt, authority, credential, scheduler, or effect data appears.

## Final certification

After visual PASS:

1. broad repository suite excluding the two Architecture-77 modules;
2. Architecture-77 from a clean detached exact-tree harness;
3. repository-wide Ruff/diff checks;
4. exact HEAD/tree/status verification;
5. independent GitHub diff review.

## Stop conditions

Stop and redesign before adding:

- service rereads for source navigation;
- destination artifact rediscovery;
- exact-row selection that requires new domain reads;
- production O2/C1/C2/C3;
- credentials or scheduler access;
- provider/broker calls;
- paper/live execution;
- settlement/recovery;
- durable writes.
