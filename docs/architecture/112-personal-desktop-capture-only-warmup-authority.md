# Architecture 112 — Personal-Desktop Capture-Only Warm-Up Authority

Status: frozen PD4-D5 source-design checkpoint; documentation only; no new provider call, scheduler mutation, decision publication, Paper-v2 effect, broker effect, or live effect is authorized by this document.

## 1. Scope and decision

Architecture 112 defines the missing operational boundary for PD4-D5 capture-only warm-up after the accepted Architecture-111 D3/D4 first capture and read-only reconciliation.

The central decision is:

> D5 uses a separate reviewed zero-semantic-argument capture-only launcher. The installed D2 scheduler task remains unchanged during source development and continues to invoke the effects-closed D2 launcher. Only at a separately authorized D5 deployment checkpoint may the existing task action be modified to invoke the capture-only launcher. The capture-only launcher treats every invocation as an untrusted wake, opens only the Architecture-111 market-data gate process-locally for exactly one G5 call, closes that gate in `finally`, and performs all downstream G6 reconciliation only after all eight effect gates are closed again.

The scheduler does not become provider authority. The launcher does not accept a session, symbol, selection ID, provider, retry count, effect flag, account ID, path, or any other semantic trading input.

## 2. Controlling predecessor contracts

Architecture 112 composes and must not weaken:

- Architecture 77/82 C2/C3 transactional provider-call, crash/recovery, selection, and at-most-once authority;
- Architecture 94 P2 selected-C3 provenance;
- Architecture 102 dedicated non-admin `Trading` security profile;
- Architectures 103–109 Paper-v2 account, execution, and recovery authority;
- Architecture 110 scheduler-as-wakeup-only and zero-semantic-argument policy;
- Architecture 111 G5 zero-argument C3 composition, G6 all-eight-closed daily controller, session-gap rules, and C3-authoritative rolling history;
- the accepted D2 scheduler definition and D3/D4 provider-call #7 evidence.

No Task Scheduler metadata, task history, previous exit code, trigger count, task state, PID, working directory, environment variable, or wall-clock value becomes retry or provider authority.

## 3. Why D5 requires a distinct launcher

The accepted D2 launcher intentionally requires all eight production effect gates to be false and calls only effects-closed G6. G6 independently requires all eight gates false.

D5 must not weaken either contract.

A distinct capture-only launcher therefore provides the outer operational composition needed for warm-up:

```text
untrusted zero-argument wake
-> validate D5 source-owned scheduler/action contract
-> require all eight gates initially closed
-> enter capture-only runtime boundary
-> open only market-data capture gate in this process
-> invoke G5 exactly once
-> close market-data gate in finally
-> require all eight gates closed again
-> if G5 state is safe, invoke G6 exactly once effects-closed
-> emit bounded sanitized result
```

The D2 launcher remains available as the closed diagnostic/read-only launcher.

## 4. Source-development safety

During D5 source implementation and focused testing:

```text
installed scheduler action = existing D2 launcher
new D5 capture-only launcher = not installed
all eight source gate constants = False
```

This separation is mandatory so that merely fast-forwarding the source worktree for tests cannot arm the already-installed scheduled task for provider effects.

Source implementation must not change the existing D2 task path or D2 launcher semantics in place.

## 5. D5 scheduler action contract

D5 reuses the accepted D2 task identity, principal, interpreter, trigger, timing, power settings, overlap policy, and working directory.

The reviewed D5 task modification changes only the source-owned launcher action from:

```text
scripts\run_personal_desktop_unattended_paper_operation.py
```

to:

```text
scripts\run_personal_desktop_unattended_capture_warmup.py
```

The task still supplies:

```text
semantic arguments = NONE
scheduler-owned environment = NONE
interpreter = F:\AITradingBot\runtime\python.exe
interpreter arguments = -I
principal = DESKTOP-I4DOKM7\Trading
run level = LeastPrivilege / LUA
```

All other accepted D2 scheduler fields remain unchanged.

Before modification, the installed task must exactly match the accepted D2 contract. After modification, it must exactly match the D5 capture-warm-up contract. A missing task, an already-conflicting task, or any mismatch outside the reviewed action change is `BLOCKED`; no repair or broad rewrite is implied.

Actual Task Scheduler modification remains a separate operator effect checkpoint.

## 6. Capture-only runtime admission

The capture-only runtime boundary may begin only when the exact eight-gate state is:

```text
market-data capture        = False
decision publication       = False
Paper-v2 production        = False
Paper-v2 recovery          = False
supervised execution       = False
receipt recovery           = False
unattended execution       = False
storage provisioning       = False
```

Any non-boolean or open gate blocks before G5.

The runtime boundary then changes only the process-local market-data gate to `True`, invokes the existing zero-semantic-argument G5 production API exactly once, and restores that gate to `False` in `finally`.

No other gate may be opened or assigned by the capture-only boundary.

The committed source value of every production gate remains `False`.

## 7. Exactly one G5 call per wake

One capture-only launcher invocation has a G5 call budget of exactly one.

The boundary must not perform a read-only G5 call followed by a second effectful G5 call, because the clock/session could cross a boundary between calls and because the second call would create an unnecessary retry surface.

Instead:

```text
all gates closed
-> process-local market-data gate True
-> one G5 call
-> process-local market-data gate False in finally
```

G5 itself performs durable read-only preflight before any provider root can be constructed.

Therefore:

- existing selected session -> `NO_NEW_COMPLETED_SESSION`, no provider effect;
- exact fresh eligible session -> at most one existing C3 capture attempt;
- consumed/ambiguous state -> no blind retry;
- session gap -> stop;
- invalid state -> stop.

## 8. Exception and ambiguity rule

If the one G5 call raises after the market-data gate has been opened, the outer D5 boundary must assume the provider attempt may have been consumed or become ambiguous.

It must:

1. close the process-local market-data gate in `finally`;
2. not call G5 again in that process;
3. not perform a fresh provider retry;
4. emit a sanitized conservative result equivalent to `PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS` or `BLOCKED` according to the implemented evidence contract;
5. require later durable C2/C3 reconciliation before another authorized wake may proceed.

Task Scheduler failure or process exit is never retry authority.

## 9. Post-G5 G6 reconciliation

G6 may run only after the market-data gate has been restored to false and all eight gates are reverified closed.

If G5 returns a safe converged state:

```text
NO_NEW_COMPLETED_SESSION
or
CAPTURE_REQUIRED + exact invocation evidence from the one authorized G5 call
```

then D5 calls G6 exactly once.

G6 remains unchanged and effects-closed. It may return, among other classifications:

```text
WARMING_UP
DECISION_READY
DECISION_ALREADY_FINALIZED
SESSION_GAP
RECEIPT_RECOVERY_REQUIRED
MISSED_DECISION_DEADLINE
BLOCKED
```

`DECISION_READY` is only evidence that warm-up history is sufficient and the next protected D6/D7 publication checkpoint may be considered. D5 does not open the decision-publication gate.

## 10. Warm-up progression

The accepted current authoritative warm-up seed is the selected C3 session:

```text
2026-09-11
selection_id = 7c42363d-4785-5823-be7e-93bf94426eac
snapshot_id  = 8ddc60ed-3940-5379-a868-b46b9b7c95af
```

For `MovingAverageCrossoverConfig(short_window=3, long_window=5)`, the first C3-only decision requires six consecutive selected sessions in the rolling suffix.

Leading missing sessions before the first selected warm-up session are normal `WARMING_UP`. Once the chain begins, a missing required session is `SESSION_GAP` and D5 stops. D5 does not backfill from the old offline seed and does not perform multi-session catch-up.

## 11. Result and launcher output

The D5 public result is bounded sanitized evidence only. It may expose:

```text
schema
status/classification
completed session
G5 classification
G6 classification when reached
capture_performed boolean
real_effect_performed boolean
scheduler_modified = false for ordinary launches
```

It must not expose:

```text
credential material
SID/path/security descriptor details
native handles
provider secrets
process-local permits/capabilities
raw C1/C2/C3 authority objects
unbounded provider payloads
```

A successful provider capture may set `capture_performed=true` / `real_effect_performed=true` in this D5-specific result. That does not change the invariant that G6 results themselves remain non-authorizing and `real_effect_performed=false`.

## 12. Unsafe classifications and exit behavior

The capture-only launcher must return conservative nonzero status for at least:

```text
BLOCKED
SESSION_GAP
PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS
RECEIPT_RECOVERY_REQUIRED
MISSED_DECISION_DEADLINE
```

Normal warm-up classifications such as `WARMING_UP`, and the terminal warm-up handoff classification `DECISION_READY`, may return zero while still performing no decision or Paper-v2 effect.

Exit status is diagnostic only and grants no retry authority.

## 13. Required tests

Source acceptance must prove at least:

- parser accepts no semantic arguments;
- D5 contract mismatch blocks before runtime entry;
- any initially open/non-boolean gate blocks before G5;
- only market-data gate becomes true inside the exact G5 call;
- all seven companion gates remain false;
- market-data gate is false after success, safe no-op, and exception paths;
- G5 is called exactly once per launcher invocation;
- G5 exception never triggers a second attempt;
- `NO_NEW_COMPLETED_SESSION` reaches G6 with all eight closed;
- successful capture evidence reaches G6 with all eight closed;
- unsafe G5 classifications stop before G6;
- G6 is called at most once;
- D5 launcher cannot publish a decision, execute/recover Paper-v2, provision storage, mutate Task Scheduler, submit broker orders, or enter live execution;
- source committed gate constants remain false;
- D2 launcher behavior remains unchanged;
- D5 scheduler contract differs from D2 only in explicitly frozen D5 action/authorization metadata;
- launcher remains `-I`/source-checkout/cwd/PYTHONPATH independent.

No source test may require a real provider call.

## 14. Protected deployment sequence

After source implementation, exact review, focused verification, and replacement broad certification on the final unchanged source tree:

```text
D5-A  read-only verify installed task == accepted D2 contract
D5-B  separately authorize exact task-action modification to D5 launcher
D5-C  read back installed task == exact D5 capture-warm-up contract
D5-D  all eight gates closed read-only launcher qualification
D5-E  allow normal scheduled wakes to enter capture-only boundary
```

The task modification itself is a protected Windows effect and requires explicit operator approval.

No manual provider call is authorized merely by source acceptance or task-contract creation.

## 15. Stop conditions

D5 warm-up stops and requires operator review on:

```text
SESSION_GAP
PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS
BLOCKED
receipt-recovery requirement
unexpected decision state
scheduler contract mismatch
source/tree mismatch
unexpected gate state
worktree mutation
```

No stop condition authorizes cleanup, backfill, task repair, provider retry, decision publication, Paper-v2 execution, broker-paper, or live trading.

## 16. Acceptance criteria

Architecture 112 is accepted when source and later protected deployment prove:

```text
D2 launcher remains effects-closed and unchanged in authority semantics
D5 uses a separate zero-argument capture-only launcher
scheduler remains wake-up only
source tests can be deployed without arming the currently installed D2 task
one wake grants at most one G5 call
only market-data gate opens process-locally
market-data gate closes in finally
all downstream G6 work occurs with all eight gates closed
C3 durable authority controls duplicate/retry behavior
history gaps stop rather than backfill
decision/Paper-v2/broker/live effects remain closed
actual task modification remains a separately approved effect checkpoint
```
