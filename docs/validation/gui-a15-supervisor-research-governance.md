# GUI-A15 — Supervisor, Research & Strategy Governance validation

## Source and verification scope

Branch/worktree and exact base are recorded in Architecture 136. Acceptance
remains pending ChatGPT exact GitHub source/CI review. Synthetic contracts,
synthetic runtime fixtures and the existing historical compact-report fixture
are used; no production/operator evidence is read.

Five new test modules bring actual tests/gui inventory to 44. Current inventory
is ACTIVE 62, FULL 169, ROBINHOOD 94, LEGACY 215, EXHAUSTIVE 384. Direct
current count assertions and three affected test-file blob pins are reconciled.
No production executable/native/AST pin or active registration is changed.

## Required evidence

- Strict immutable model types/bounds and exact Decimal presentation.
- No selected strategy path: zero strategy I/O and no reader instantiation.
- Explicit local file only; consumed CLI flag; config Path type validation.
- Binary 16 KiB + one-byte bounded read; unmodified strict UTF-8 text reaches
  the existing canonical ProductionStrategyContract.from_json parser.
- Cached success/failure; at most one selected-file open; malformed JSON,
  duplicates, unknown/noncanonical data, UTF-8, size, semantic UUID/hash/config
  failures and unsupported/UNC paths yield fixed diagnostics without leakage.
- Contract-only AVAILABLE / NOT_CHECKED; exact session match CONSISTENT;
  contract ID, HEAD, TREE or target-session mismatch CONFLICTING / ATTENTION.
- Historical research evidence availability and bounded report/result IDs;
  no source-path copy or process-active inference.
- Recorded WAITING_FOR_MARKET, disconnected D2 and clearly future D2 vocabulary.
- Fixed automatic=false, human-required=true, authority-connected=false,
  research-replacement=false; no promotion/execution controls.
- Plain-text selectable Qt labels, vertical scrolling and no horizontal
  overflow at 920x620; real PySide6 import is mandatory for A15 Qt tests.
- Exactly eight ordered startup service acquisitions; navigation/filtering,
  System/Evidence/Supervisor construction and source navigation add zero reads.
- Supervisor System status/audit mapping, untimed one-contract Evidence entry,
  A11 filter and closed A12/A13 navigation mappings.
- Static direct-import/call checks forbid effect dependencies and discovery.
- Dedicated GUI CI retains its Windows/Python/PySide6/full-GUI/Ruff/diff contract
  and changes only the GUI branch selector; repository allowlist remains frozen.

## Local results before publication

New A15 tests: **61 passed** in complete GUI verification. Complete offscreen
real-PySide6 GUI: **531 passed, 0 skipped**. Focused profile/authority checks, combined Ruff and
final diff evidence are reported with the final implementation handoff.
No local FULL/ROBINHOOD/LEGACY/EXHAUSTIVE certification is run.

After ordinary push, require dedicated GUI Source Gates SUCCESS on the exact
HEAD, then a fresh Checkpoint Source Gates workflow_dispatch on that exact
branch. Its unmapped route requires source-static, four full-tests shards,
active-tests/certification-tests skipped, and terminal source-gates SUCCESS.
Preserve any failed run; never rerun historical failures. At most one directly
stale inventory/test-file-pin correction cycle is authorized. Any wider CI
failure is STOP. CI identities/results belong in the final report and later
ChatGPT docs closeout, not an invented acceptance claim here.

## Zero-effect evidence

```text
PRODUCTION_SQLITE_READS=0
PRODUCTION_SQLITE_WRITES=0
CREDENTIAL_READS=0
PROVIDER_CALLS=0
BROKER_CALLS=0
SCHEDULER_CALLS=0
ACL_MUTATIONS=0
PAPER_MUTATIONS=0
RESEARCH_EXECUTIONS=0
STRATEGY_PROMOTIONS=0
D2_SUPERVISOR_EXECUTIONS=0
```

A15 imports only inert production strategy contract material. It does not compose
production runtime, provider/credential/store/scheduler/broker adapters or D2.
No D1 ARM/qualification, operational-source reconciliation or protected effects
are performed. Frozen R1/R2 identities are verified again before final handoff.
