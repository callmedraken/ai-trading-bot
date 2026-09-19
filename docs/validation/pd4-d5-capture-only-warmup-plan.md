# PD4-D5 Capture-Only Warm-Up Validation Plan

Status: source-planning checkpoint for Architecture 112; documentation only; no new provider call or scheduler mutation is authorized.

Architecture:

```text
docs/architecture/112-personal-desktop-capture-only-warmup-authority.md
```

## 1. Accepted starting point

D3/D4 provider-call #7 and read-only reconciliation are accepted.

The accepted selected C3 warm-up starting session is:

```text
session       2026-09-11
selection_id  7c42363d-4785-5823-be7e-93bf94426eac
snapshot_id   8ddc60ed-3940-5379-a868-b46b9b7c95af
sha256        704c1d0966acec3489a355fd6ef5369439b07e0e0a8e15c5f68cc2d847aa607f
byte_length   1289
```

The current production read-only state has been proven under the genuine non-admin `Trading` principal as:

```text
G5                         NO_NEW_COMPLETED_SESSION
Paper-v2 account reread    PASS
history                    WARMING_UP
G6                         WARMING_UP
all eight effect gates     False
```

The current source checkpoint immediately before Architecture-112 docs is:

```text
commit  f39e46e3d3c19e35f35ec0dc63283177cb538c7f
tree    8b0f8d741982f296590e6bf3f6bf41cb2ec1cea9
```

The three D5 source-readiness compatibility corrections already accepted are:

1. retain the P2 reader while replaying the frozen first Paper-v2 configuration;
2. reserve the `unattended-decisions` namespace during strict Paper-v2 account reads;
3. retain every G6 selected-C3 reader for the lifetime of one production dependency bundle.

## 2. Non-negotiable invariants

During Architecture-112 source implementation:

```text
PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_UNATTENDED_DECISION_PUBLICATION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED = False
```

The installed scheduler task remains on the accepted D2 launcher throughout source implementation and focused testing.

Do not modify the existing D2 launcher in place to arm provider effects.

Do not run another real provider call during source implementation.

## 3. Source checkpoint D5-S1 — Pure D5 scheduler/action contract

### Goal

Freeze the exact capture-warm-up action while preserving all accepted D2 scheduler semantics.

### Required behavior

Add a source-owned D5 contract that reuses the D2:

- task path;
- principal/SID;
- production interpreter and `-I`;
- working directory;
- 01:30 Pacific daily trigger;
- `StartWhenAvailable` policy;
- power/wake settings;
- `IgnoreNew` scheduler setting;
- no automatic retries;
- one-hour execution limit;
- priority;
- no semantic arguments;
- no scheduler-owned environment.

The D5 contract changes only the source launcher action to:

```text
scripts\run_personal_desktop_unattended_capture_warmup.py
```

and freezes that replacing an exact D2 task requires a separate operator effect checkpoint.

### Required tests

- exact equality of all unchanged D2 fields;
- exact D2 -> D5 launcher path change;
- no semantic args/environment;
- absent task is not silently installed during D5 replacement;
- exact D2 predecessor accepted for later replacement planning;
- any other predecessor/conflict blocks;
- pure contract code cannot inspect or mutate Task Scheduler.

## 4. Source checkpoint D5-S2 — Capture-only runtime boundary

### Goal

Implement the source-owned one-wake/one-G5 operational composition without changing G5 or G6 authority semantics.

### Required ordering

```text
require all eight gates false
-> process-local market-data gate True
-> call G5 exactly once
-> process-local market-data gate False in finally
-> require all eight gates false
-> if G5 outcome permits, call G6 exactly once
-> return sanitized D5 result
```

### Required behavior

The runtime boundary must:

- accept no semantic trading inputs;
- never open a companion gate;
- never call G5 twice;
- never interpret scheduler exit/history as retry authority;
- map a G5 exception after admission conservatively to ambiguous/blocked evidence;
- stop before G6 for G5 `SESSION_GAP`, `PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS`, or `BLOCKED`;
- permit `NO_NEW_COMPLETED_SESSION` and one successful `CAPTURE_REQUIRED + invocation` result to reach effects-closed G6;
- reject `CAPTURE_REQUIRED` without invocation evidence once the gate was open;
- leave all eight gates false on every normal/exception return path that remains in-process;
- report whether a real capture effect was performed without exposing reusable authority.

### Required tests

At minimum:

- every invalid/open initial gate blocks before G5;
- exact false tuple admits runtime;
- G5 observes market-data true and every other gate false;
- gate closes after no-op, capture, unsafe result, and exception;
- G5 call count exactly one;
- G5 exception call count remains one;
- no G6 call on unsafe G5 state;
- one G6 call on safe G5 state;
- G6 observes all eight gates false;
- a successful capture followed by `WARMING_UP` reports capture performed + warm-up;
- history-ready G6 `DECISION_READY` performs no publication and reports handoff readiness;
- unsafe G6 classification propagates conservatively;
- result cannot carry permits, handles, credentials, raw provider payloads, or mutation authority.

## 5. Source checkpoint D5-S3 — Zero-argument capture-only launcher

### Goal

Expose the D5-S2 boundary through a fixed source-checkout script suitable for the later protected scheduler action change.

### Required behavior

The launcher must:

- accept zero semantic arguments;
- validate the exact D5 source-owned scheduler/action contract;
- validate all gates initially false before runtime entry;
- invoke the D5-S2 runtime once;
- emit bounded JSON only;
- never mutate Task Scheduler;
- never directly manipulate provider credentials or call Alpaca;
- never open decision/Paper-v2/broker/live gates;
- use conservative nonzero exit for unsafe classifications;
- remain independent of cwd, `PYTHONPATH`, and alternate installed packages through the established source-checkout script pattern.

The launcher output schema must include at least:

```text
schema
classification/status
completed_session
market_data_classification
cycle_classification
capture_performed
real_effect_performed
scheduler_modified=false
```

## 6. Source checkpoint D5-S4 — Exact source review and focused gate

Review the exact diff from the accepted pre-Architecture-112 source tree.

Expected source surface should remain bounded to:

```text
new D5 scheduler/action contract support
new D5 capture-only runtime boundary
new D5 CLI launcher
new source-checkout script
focused tests
Architecture-112 / D5 validation docs
```

Existing G5 and G6 should not be weakened merely to make D5 work.

Run focused tests for:

- D2 scheduler contract regression;
- D2 launcher regression;
- D5 scheduler/action contract;
- G5 capture authority;
- G6 daily controller;
- D5 capture-only runtime;
- D5 capture-only launcher;
- source-checkout isolation.

Then run focused Ruff and diff checks.

## 7. Replacement broad certification

Because Architecture-112 implementation changes source after the last accepted broad G7/D2 certification, run one replacement full-suite certification after the exact D5 source tree is final.

Required final gate:

```powershell
$Python = 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe'
$Ruff = 'F:\AI\ai-trading-bot\.venv\Scripts\ruff.exe'
$BaseTemp = "F:\AI\temp\pytest\pd4-d5-final-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Force 'F:\AI\temp\pytest' | Out-Null

& $Python -m pytest --basetemp="$BaseTemp" -p no:cacheprovider
& $Ruff check .
& $Ruff format --check .
git diff --check
git diff --cached --check
git status --short
```

Record exact commit/tree before and after, and require local/origin equality.

Docs-only closeout after this certification does not require another full suite.

## 8. Genuine Trading-principal source qualification before task modification

Before modifying Task Scheduler, use the production interpreter under genuine non-elevated `DESKTOP-I4DOKM7\Trading` while the installed task still points at D2.

The new D5 launcher must be exercised only through a disposable/no-effect test seam or a mode that cannot open the production capture boundary. A normal production invocation of the capture-only launcher is itself an effect-capable boundary and is not authorized by source certification alone.

Acceptance requires:

```text
source/tree exact
Trading SID/non-admin/Medium exact
all eight gates initially false
existing D2 scheduled task unchanged
no provider call
no scheduler mutation
no decision publication
no Paper-v2 effect
```

## 9. Protected deployment D5-A — Read-only D2 task qualification

Using administrator read-only inspection, require the installed task to match the accepted D2 contract exactly.

Any mismatch is `STOP`; do not repair or replace it automatically.

## 10. Protected deployment D5-B — Exact scheduler action modification

Only after explicit operator approval may the existing exact D2 task be modified to the D5 capture-warm-up action.

The mutation budget is exactly one reviewed task modification.

Do not change:

- task path;
- principal/SID/logon/run level;
- executable;
- interpreter `-I`;
- working directory;
- trigger/timezone/start-when-available;
- retry, overlap, power, wake, hidden, priority, or execution-limit settings;
- environment;
- semantic arguments.

Change only the reviewed launcher path/action required by Architecture 112.

Immediately read back and require exact D5 contract equality.

## 11. Protected deployment D5-C — Capture-only warm-up operation

After exact task readback and all-eight-closed preflight, ordinary task wakes may enter the source-owned capture-only boundary.

One wake may produce at most one G5 call.

Expected warm-up progression is one selected completed session per eligible wake until the rolling six-session suffix is complete.

Normal result before readiness:

```text
capture may or may not be required for this wake
G6 = WARMING_UP
publication = closed
Paper-v2 effects = closed
```

When the six-session suffix becomes ready, expected handoff evidence is:

```text
G6 = DECISION_READY
capture-only D5 performs no publication
```

Then stop D5 and proceed to separately reviewed D6/D7 publication authority.

## 12. Stop conditions

Stop D5 immediately on:

```text
SESSION_GAP
PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS
BLOCKED
unexpected receipt-recovery state
scheduler contract mismatch
unexpected source/tree
unexpected gate state
worktree mutation
nonzero/partial/uncertain provider-effect result
```

Do not authorize automatic retry, cleanup, backfill, task repair, decision publication, Paper-v2 execution, broker-paper, or live trading from those states.

## 13. Model routing

D5-S1 pure frozen scheduler/action contract is localized and mechanical once Architecture 112 is fixed.

D5-S2/S3 cross authority, process-local gate admission, external-effect containment, exception ambiguity, and scheduler operational boundary are security-sensitive. Use Sol High for implementation/review.

ChatGPT retains exact diff acceptance, test-gate decisions, deployment sequencing, and protected-effect authorization boundaries.
