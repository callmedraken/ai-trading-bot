# GUI-A14 — Production runtime evidence validation

## Current checkpoint

Implemented for exact source review on `feature/gui-production-runtime-status`,
from `2f122958366d1db282fea51abbd461b83fa893d9` /
`c3fb82add37bdbea12ebad9836ca10000b924fe1`. This is a local checkpoint,
not source acceptance. The user selected local commit/no push because the
pre-push bootstrap requires ChatGPT review without changing frozen R1/R2 pins.
Dedicated GUI CI and existing source-gate CI have not run on this checkpoint.

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
No local ROBINHOOD/FULL profile is selected. No R1/R2 executable,
checkpoint registry, source authority pin or global source-gate topology changes.

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

ChatGPT reviews the exact local checkpoint and chooses a separate narrowly
reviewed CI-bootstrap path. Do not self-register with the first GUI push,
modify frozen R1/R2 source pins, claim missing CI as PASS, merge or perform any
production effect. After approved bootstrap and ordinary push, require terminal
dedicated GUI and existing source-gate coverage on the exact source before
ChatGPT source acceptance. No repeated local broad certification is needed.

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
