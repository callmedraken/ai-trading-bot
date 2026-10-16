# GUI-A17 — Research Lifecycle Audit Validation

Status: local implementation validation; stop for ChatGPT exact GitHub source
review after both terminal source gates. This record does not declare acceptance.

## Required source-only gates

Use `F:\AI\ai-trading-bot\.venv\Scripts\python.exe` (Python 3.14), real
PySide6 6.10.3 and `QT_QPA_PLATFORM=offscreen`. Each pytest invocation uses a
fresh external basetemp under `F:\AI\temp\pytest`, with `-p no:cacheprovider`.

1. New combined A17 module: pure in-memory fixtures, exact frozen/slotted types,
   deterministic five-artifact/five-source composition, three coverage margins,
   exact integers excluding bool, non-authoritative rank, nine zero counters,
   fixed governance, empty unavailable/attention audits and exact diagnostics.
2. Real Qt checks at both 920x620 and 1180x760 with the MainWindow navigation
   width reserved: selectable complete identifiers, wrapping height, vertical
   scrolling, no horizontal overflow, no editable/action controls or external
   links. Repeated construction/scrolling with file and service reads replaced
   by failing sentinels must pass.
3. All retained A16 modules; A12/A13 navigation; all A14/A15 modules and
   `test_main_window.py`. Existing nine-state one-acquisition and page ordering
   assertions remain mandatory.
4. Complete `tests/gui` once with real PySide6.
5. Seven inventory/authority modules plus production-runtime, Alpaca staging,
   authentication, generation and pre-market-wake source regressions. Synthetic
   test boundaries only; no protected operator CLI or real effects.
6. Ruff check and format check, both non-mutating and `--no-cache`, for all
   touched Python files; report diffs for either failed phase. `git diff --check`.

No local FULL/ROBINHOOD/LEGACY/EXHAUSTIVE certification profile is selected.
Workflows and GUI LEGACY ownership remain unchanged.

## Local results

Python 3.14.3 / PySide6 6.10.3 / offscreen:

- New A17 module: 104 passed.
- Retained A12/A13/A14/A15/A16 and MainWindow: 562 passed in 15.20 s.
- Seven inventory modules plus five relevant D1Q/D1R3/D1R4/D1R4R/D1R5
  source-regression modules: 1,410 passed in 62.55 s.
- Complete GUI run (one local invocation): 984 passed in 26.06 s.
- Final affected A17 + A16 page regression: 111 passed in 11.07 s.

Visual QA identified two bounded presentation issues: setting a new QLabel
size policy dropped height-for-width, and unstretched numeric grid columns
received zero width. Both are corrected. The final focused regression covers
actual text height, nonzero visible coverage-column widths, full UUID/hash
tokens and both resolutions. Windows offscreen has no system font families;
the test explicitly loads Segoe UI before file-read sentinels are installed.
Font setup belongs only to tests, not product code. Font-enabled synthetic
previews were inspected outside the worktree.

The single local complete GUI run precedes the final bounded grid-width
correction; only affected tests were rerun locally. The mandatory automatic
GUI Source Gates run must validate the complete GUI suite on the exact final
pushed source. No full certification profile or protected operation was run.

## Freeze and successor evidence

The new module's AST admits only `dataclasses` and the A16 page-state type,
with an explicit closed call set. All 15 frozen A16 product blobs and both
workflow blobs are asserted literally. A16 tests retain their domain-byte and
34 predecessor-dictionary freezes. A17 repeats the dictionary freezes and adds
the exact A16 overlay digest:
`887064885ca3be46514075efed384ccf1c6eb778d78dcc3f06bc402bff1a4e4f`.

A17 overlay sorted-key JSON SHA-256:
`dc11d4c1e6099c1eec3346cafb85220e42f495e472d220cf81ac741ccff524c3`.

| Successor inventory test | A17 Git blob |
| --- | --- |
| tests/scripts/certification_runner/test_profiles.py | e8212d9d29b648868472812e3b87d86ba0a52b7e |
| tests/strategies/test_production_strategy_contract.py | 71a795f9a52568fd0459fbd84b0ce9c08e61d60b |
| tests/strategies/test_production_strategy_decision.py | a188f948e335a25d611991465a93c8de93b5ec3f |
| tests/review_paper/test_production_strategy_cycle.py | 83a50eb19dc230a366a39dae293f4006b7dbef52 |
| tests/review_paper/test_supervised_deployment_qualification.py | 8f9a142d408fcaaaa3ef55a049445859cef3377a |
| tests/review_paper/test_supervised_runtime_host_admission.py | 2a9d81b1cb2a4d0969251db45bff88ca114c0e3f |
| tests/review_paper/test_supervised_maintenance_rebind.py | e200dc0d0357ddc654d8253fc311464d28992ff6 |

Tests reject missing/extra/product overlay paths, wrong before/after pins,
A16 predecessor drift and older overlay drift. Discovery must report ACTIVE 64 /
FULL 179 / ROBINHOOD 98 / LEGACY 221 / EXHAUSTIVE 400 / GUI 50.

## Publication protocol

After local PASS, verify empty initial index and exact intended path set, stage
only those paths, check staged names and `git diff --cached --check`, create one
normal commit `feat: add research lifecycle provenance audit GUI`, and push the
isolated feature branch normally. Do not move another branch.

The pre-existing reviewed GUI workflow admits `feature/gui-*` (unchanged at the
accepted A16 base); GitHub workflow ID 382615376 is active and A16 push run
38684121623 succeeded on attempt 1. A17 makes no self-registration or workflow
change. Require exactly one fresh automatic push run on the exact commit, attempt
1, terminal SUCCESS: real PySide6, complete GUI suite, combined Ruff and static
diff gates. Do not rerun a failed HEAD; preserve evidence and correct source.

Only after that success, dispatch exactly one Checkpoint Source Gates run on
the same exact HEAD. Preserve A16 parallel-GUI routing: source-static, four
broad shards each below 300 seconds, terminal source-gates; active/profile jobs
skip as expected. Require attempt 1/SUCCESS/no retries and unchanged workflows.

Reverify remote HEAD/tree, intended changed files and final blobs, frozen A16
blobs/dictionaries, inventory, clean worktree/index, and unchanged D1R6 refs.
Return terminal CI run/job identities and shard walls in the implementation
handoff. Stop for ChatGPT source review. Do not update PROJECT_STATUS or
AI_TRADING_BOT_HANDOFF, integrate product/history refs, acquire observations,
promote, materialize later stages or begin Architecture 141.
