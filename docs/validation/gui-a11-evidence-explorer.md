# GUI-A11 Read-Only Evidence Explorer Validation Plan

## Purpose

Validate Architecture 118,
`docs/architecture/118-gui-read-only-evidence-explorer.md`.

A11 must remain a local presentation refinement over the accepted A10
`EvidenceTimelinePageState`.

## A11a pure filter contract

Add `EvidenceTimelineFilter` and
`filter_evidence_timeline_entries(...)`.

Verify:

- query is bounded to 200 characters;
- invalid source/type/control text fails explicitly;
- blank query means no text restriction;
- exact source filtering;
- case-insensitive text search;
- matching uses only fields already represented by A10;
- output preserves A10 ordering;
- no I/O imports or wall-clock reads.

## A11b Qt page gate

Enhance the existing Evidence page with:

- bounded search input;
- source selector;
- showing/total count;
- distinct no-match state.

Verify:

- changing search/source updates cards locally;
- no service call occurs;
- no effect button exists;
- identifier/hash fields remain read-only and selectable;
- underlying empty state remains truthful;
- initial scroll position remains at the top.

## A11c integration regression

At minimum run:

```text
tests/gui/test_gui_a11_evidence_explorer.py
tests/gui/test_gui_a10_evidence_timeline_page_qt.py
tests/gui/test_main_window.py
tests/gui/test_gui_a10_evidence_timeline_adapter.py
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

Inspect default and populated Evidence views, then activate a source/text filter
at 920x620.

Confirm:

- controls fit without clipping;
- read-only scope remains visible;
- count changes correctly;
- matching cards remain in original timeline order;
- no-match text is distinct from no-evidence text;
- IDs/hashes remain selectable;
- no authority/effect control appears.

## Final certification

After visual PASS:

1. broad repository suite excluding the two Architecture-77 modules;
2. Architecture-77 in a clean detached exact-tree worktree;
3. repository-wide Ruff/diff checks;
4. exact HEAD/tree/status verification;
5. independent GitHub diff review.

## Stop conditions

Stop and redesign before adding:

- service rereads for filtering;
- new artifact reads or discovery;
- production O2/C1/C2/C3;
- credentials or scheduler access;
- provider/broker calls;
- paper/live execution;
- settlement/recovery;
- durable writes.
