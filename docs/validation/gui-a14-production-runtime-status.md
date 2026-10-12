# GUI-A14 — Production runtime evidence validation

## Current checkpoint

The GUI-A14 implementation was ordinary-pushed as HEAD
`693c0d15b8521d4d6c9bdcc6c090143299767b72`, TREE
`4786038698de47a71971f4072c7b7b4d495d013a`. Dedicated GUI CI
[38316319422](https://github.com/callmedraken/ai-trading-bot/actions/runs/38316319422)
SUCCEEDED: 470 passed, zero skips, real PySide6 6.10.3, Ruff/diff PASS.
Default-branch dispatch bootstrap is accepted on develop HEAD
`011051e9ac4e79e4c42da984e34022e3767713ff`, TREE
`8ac2cb990be1178d47d00b70230d7d3736aae409`; bootstrap CI
[#505 / 38318201408](https://github.com/callmedraken/ai-trading-bot/actions/runs/38318201408)
SUCCEEDED.

The first repository workflow_dispatch
[38320329303](https://github.com/callmedraken/ai-trading-bot/actions/runs/38320329303)
FAILED during source-static: 62 of 63 active authorities passed. Only the
historical supervised-release-publication-recovery authority failed with
`publication recovery runner authority drift`; diff/Ruff passed, pytest was
SKIP and source identity remained stable. Full-tests never started. This was
an intentional historical closure fuse, not a GUI behavior failure. Preserve
that run; do not rerun it.

This correction retires only
`arch133-robinhood-supervised-release-publication-recovery` from CURRENT ACTIVE
CI (63 -> 62), preserving its registry, source, protected bindings and historical
pins. REGISTERED HISTORICAL CHECKPOINT != CURRENT ACTIVE CI CHECKPOINT. Its
unchanged authority now returns exactly, in order, `publication recovery
registration drift` and `publication recovery runner authority drift`: the
historical active-registration requirement and stale `_checkpoint_specs` AST
pin independently keep recovery closed. No other active member is removed or
reordered. Current tuple AST SHA-256 is
`06a3101a319f6b268404deb67299d87d484fd238212131074c5f86cfea9a6440`.
Directly affected topology/count assertions and their test-only source hashes
are updated; production executable pins and frozen R1/R2 branches remain exact.
GUI-A14's five added legacy test modules make current inventory FULL 169,
ROBINHOOD 94, LEGACY 210, EXHAUSTIVE 379.

GUI-A14 source acceptance remains pending a fresh exact-source repository gate
following ChatGPT's exact GitHub correction review. Codex owns this one normal
correction commit/ordinary push and terminal dedicated GUI CI, without adding
the GUI branch to the repository push allowlist or changing workflow_dispatch.
ChatGPT owns the fresh repository workflow_dispatch; no local broad profile or
protected operator is selected. No production effect occurred.

## Verification performed

Python 3.14.3, PySide6 6.10.3, pytest 8.4.2; QT_QPA_PLATFORM=offscreen.
Real Qt imports are mandatory in the new Qt/startup/integration tests.
Complete `tests/gui`: **470 passed, 0 skipped, 0 failed, 0 errors**.
A9–A13/navigation/layout focused gate: **42 passed**. New A14 coverage includes
strict immutable models, bounded fields/counts, duplicate keys, malformed/
oversized/deep JSON, schema/SHA/digest/UUID/date/timestamp rejection, sensitive
unknown-field rejection, sanitized I/O failures, source conflict, default zero
reads, explicit-only single acquisition and cached failed acquisitions.

The initial Runtime layout check caught minimum-width overflow. The corrected
layout uses wrapping/selectable labels, an explicit grid-column minimum and
ignored horizontal size hints for values. Visual QA also caught caption/value
overlap; a geometry assertion now verifies that the columns remain separated.
At 710x620 page space inside the 920x620
window it scrolls vertically without horizontal overflow. There are zero effect
buttons. Long HEAD/tree/digest/contract/proposal/order/fill values are selectable.
Seven application-service reads and three unique explicit opens are recorded;
Runtime/System/Evidence and Evidence -> Runtime navigation add zero reads.
A11 filtering and all existing GUI pages remain covered by complete regression.

Synthetic tracked fixtures are in `tests/fixtures/gui/runtime`: PROVISIONED ACL,
READY qualification, WAITING_FOR_MARKET session, PAPER_EXECUTED session and
STOPPED_AFTER_APPLY ACL. Principal/source digests and UUIDs are deterministic
fake values, unrelated to the user's production evidence. Invalid/conflicting
variants are generated only in test-owned external temporary directories.

Both focused GUI Ruff phases and git diff --check pass. The two existing R1/R2
source-only authority checks pass unchanged. All three dedicated-workflow
PowerShell blocks parse successfully without executing their commands.
Visual QA uses a synthetic 920x620 offscreen capture with Segoe UI explicitly
loaded in the temporary preview helper because offscreen font discovery on
this host returned missing-glyph boxes. No GUI font/runtime configuration was
changed by that preview helper.
The original GUI implementation selected no local ROBINHOOD/FULL profile and
changed no R1/R2 executable, checkpoint registry, source authority pin or global
source-gate topology. The present CI correction changes only current active
topology and directly affected test metadata; historical recovery and production
executable pins remain unchanged. Complete real-PySide6 offscreen GUI regression
was repeated for this correction: 470 passed, zero skips.

## Topology correction focused verification

The initial 214-case focused selection produced 208 passes and six failures:
R1/R2 detected the changed core-test blob, and four tests retained pre-GUI
LEGACY/EXHAUSTIVE counts. Those directly affected assertions/hashes were corrected.
The 11-case affected rerun passed, including three newly affected inventory cases,
for **217 distinct focused cases verified**. Publication-recovery, runner core/CI,
R1/R2 and every changed topology/count assertion are covered. Complete GUI:
**470 passed, 0 skipped**, real PySide6 6.10.3, offscreen. Focused Ruff check,
Ruff format --check (18 touched Python files), and git diff --check pass.

All 62 current active authority functions passed against final local edits;
publication recovery is excluded and its direct historical test returns exactly
the two closure failures. The official source-static-only runner must run on the
clean correction commit before push, because verify-batch requires a clean
worktree. No local pytest/broad profile is selected by that batch. This sequencing
preserves the runner's clean-source admission and the one-commit boundary.

Only six directly affected test-file hashes in the R1 source-owned metadata are
refreshed: runner helpers/core/CI, certification profile inventory and production
strategy contract/decision inventory tests. R1/R2 authority functions and all
production executable/native/source AST pins remain unchanged. The historical
publication-recovery function, source pins, runner pins, registry and bindings
are unchanged. Repository branch triggers, workflow_dispatch, the dedicated GUI
workflow and GUI runtime source/tests/fixtures are unchanged.

## Review contract

Inspect Runtime model/service imports and the exact composition diff for any
production module, SQLite, Credential Manager, network/provider/broker,
scheduler, ACL, subprocess or discovery capability. Only explicit read-only JSON
opens are allowed. The final RuntimePageState contains no path/raw JSON/raw
exception; classification/identity metadata only. ACL/qualification entries
must stay untimed. Qualification/session mismatch must stay ATTENTION/CONFLICTING.
System and timeline adapters remain pure over already-acquired state.

```text
DIRECT_PRODUCTION_SQLITE_ACCESS=False
CREDENTIAL_MANAGER_ACCESS=False
ALPACA_NETWORK_ACCESS=False
ROBINHOOD_NETWORK_ACCESS=False
SCHEDULER_ACCESS=False
ACL_MUTATION=False
PAPER_EXECUTION=False
BROKERAGE_ACCESS=False
FILESYSTEM_DISCOVERY=False
LATEST_EVIDENCE_DISCOVERY=False
EXPLICIT_EVIDENCE_ONLY=True
SERVICE_REREADS_ON_NAVIGATION=0
PRODUCTION_SQLITE_READS=0
CREDENTIAL_READS=0
PROVIDER_CALLS=0
BROKER_CALLS=0
SCHEDULER_CALLS=0
ACL_MUTATIONS=0
PAPER_MUTATIONS=0
REAL_PRODUCTION_EVIDENCE_READS_DURING_TESTS=0
```

## Next owner and stop condition

ChatGPT reviews the exact ordinary-pushed correction after dedicated GUI CI
becomes terminal, then issues a fresh repository workflow_dispatch against that
exact corrected HEAD. All 62 current active authorities must pass before the
broad fallback starts; the direct historical recovery test must still prove its
two closure failures. Preserve failed run 38320329303. Do not manually rerun or
dispatch the repository gate from Codex, broaden push triggers, merge, perform
production effects or claim GUI-A14 source acceptance. CI owns the fresh broad
fallback; no local ROBINHOOD/FULL/broad shards are selected.

Optional exact local GUI re-verification (already completed, not a new gate):

```powershell
& {
  Set-Location 'F:\AI\worktrees\ai-trading-bot-gui-production-runtime-status'
  $env:QT_QPA_PLATFORM = 'offscreen'
  $GuiTemp = Join-Path $env:TEMP ('gui-a14-' + [guid]::NewGuid().ToString('N'))
  & 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider tests/gui --basetemp $GuiTemp
  if ($LASTEXITCODE -ne 0) { throw 'GUI verification failed' }
}
```
