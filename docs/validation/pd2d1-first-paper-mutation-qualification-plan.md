# PD2D1 First Paper Mutation Qualification — Validation Plan

## Scope

Implement and certify Architecture 105: a read-only qualification boundary for
the exact supervised Paper-v2 operation immediately before any source gate
enablement or first durable mutation.

PD2D1 must not execute Architecture 67 and must not mutate the published
Paper-v2 account.

## Starting source

Accepted PD2C source:

```text
commit 8d590d06d346140002a3a20eefa9b5a7d087326d
tree   ed322f18b1f98ff88f144ac11bfbcc3fd353d9a3
```

Documentation-only closeout/Architecture-105 commits may appear on top before
implementation. The Codex task must pin the actual then-current HEAD/tree.

All three effect gates must remain false:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED = False
```

Publication freeze must remain:

```text
b125cbb1c80a827f74018cf2955b9a27ba69fa90
```

## Required production-facing API

Prefer a narrow runtime module such as:

```text
src/trading_bot/runtime/personal_desktop_supervised_paper_operation_qualification.py
```

and a public function such as:

```text
qualify_supervised_personal_desktop_paper_operation(...)
```

The production signature should match the genuine C1/P2 + pure planning inputs
used by PD2B3/PD2C.

It must not accept:

```text
operation_root
Path
VerifiedPaperOperationExecutionInputs
PaperOperationIntent
paper_account_id
prior/lineage
application_id
operation_id
terminal_checkpoint_id
prebuilt PD2B3 preparation
mutex name
Trading SID
native handle
timeout
inspector override
readiness override
execution gate override
recovery-mode override
```

## Required behavior

1. Require the dedicated PD2C supervised-execution gate to be exactly `False`.
   If it is already true, fail closed before creating/entering PD2B3.

2. Use the existing public
   `supervised_personal_desktop_paper_operation_preparation(...)` constructor so
   genuine C1/P2 provenance remains the production admission path.

3. Enter that one-shot preparation and consume its existing private active
   binding only while the same PD2A account mutex remains held.

4. Require the private binding operation root to equal exactly:

   ```text
   F:\AITradingBot\Paper-v2\runtime
   ```

5. Call the existing `inspect_paper_operation_root(...)` exactly once. Do not
   duplicate its classification logic.

6. Do not import/call `execute_paper_operation_once` or any transition/receipt
   writer from the new production qualification module.

7. Require the exact `PaperOperationInspectionResult` type.

8. Reconcile exactly:

   ```text
   inspection.operation_id == active.operation_id
   inspection.application_id == active.application_id
   inspection.terminal_checkpoint_id ==
       private execution inputs verified prior checkpoint ID
   ```

9. Map to `READY` only when:

   ```text
   classification == PENDING
   diagnostics == (PENDING,)
   ```

10. Every other valid inspection classification/code is `NOT_READY`. Preserve
    the classification/code as audit evidence but do not reinterpret it as
    permission to execute.

11. Return a frozen non-authorizing result with safe identities/classification
    only. Do not expose raw inputs, root/paths, private binding, or an execute
    method.

12. Normal return, NOT_READY, inspector exception, wrong type, or identity
    mismatch must unwind PD2B3/PD2A normally. Never retry the inspector or
    mutate state to make qualification pass.

13. `ABANDONED_OWNER` remains blocked through PD2B3 before inspection.

## Private focused-test seam

A private injected test path may accept a fake PD2B3 preparation and fake
inspector, but it must require an explicit private one-shot issuer/token or
comparable barrier and must not be exported through `trading_bot.runtime`.

The production function must use the real `inspect_paper_operation_root` and
must expose no inspector override.

## Focused tests

Prove at minimum:

- execution gate true blocks before preparation/mutex/inspection;
- execution gate false is the accepted qualification state;
- forged C1 fails through the genuine preparation admission path;
- forged/disposable P2 cannot enter production qualification;
- production signature contains no prohibited authority/path/inspector inputs;
- private test seam requires a genuine one-shot test issuer;
- preparation is active and mutex lifetime retained during inspection;
- fixed root mismatch blocks before inspector call;
- inspector receives exact prepared execution inputs;
- inspector is called exactly once;
- inspector exception is never retried and unwinds preparation;
- wrong return type fails closed and unwinds;
- operation/application/terminal identity mismatches fail closed;
- exact PENDING/PENDING maps READY;
- ALREADY_APPLIED, CONFLICTING, and representative BLOCKED diagnostics map
  NOT_READY without mutation/retry;
- qualification result contains no root/Path/raw inputs/private binding/execute
  surface;
- ABANDONED_OWNER never reaches inspector;
- no A67 executor/writer import or call exists in the new production module;
- all three effect gates remain false;
- publication freeze remains unchanged;
- no provider/broker/live/scheduler/security-account effects are introduced.

## Focused verification during implementation

Run only:

```text
new PD2D1 test module
PD2B3 preparation tests
PD2C execution-boundary tests where shared lifetime/gate surfaces matter
A67 inspection tests if interface behavior is touched
PD2A mutex tests only if cleanup/lifetime code is modified
Ruff check on changed files
Ruff format --check on changed files
git diff --check
```

Do not run the full repository suite during iteration.

## Broad source certification

After ChatGPT/Sol exact-diff review accepts source, the user runs one full local
repository suite with pinned worktree provenance and a fresh external pytest
base temp.

PD2D1 source certification requires:

```text
full pytest: PASS
Ruff check: PASS
Ruff format --check: PASS
git diff --check: PASS
worktree/index: clean
all three effect gates: False
publication freeze: unchanged
no production Paper-v2 mutation occurred
```

## Real-host read-only qualification

After source certification, run a separately reviewed one-shot qualification on
the intended Windows host under the dedicated non-elevated `Trading` account.

The real-host run may acquire/release the production account mutex and read the
fixed C1/P2/Paper-v2 objects because those are qualification reads. It must call
only the read-only A67 inspector and must produce no filesystem mutation.

Acceptance requires at minimum:

```text
C1 production authority: genuine / current Trading token
P2 selected snapshot: genuine / authority-matched
PD2A mutex acquisition: OWNED (not ABANDONED_OWNER)
post-lock Paper-v2 read: PASS
prepared operation root: exact fixed Paper-v2 runtime
A67 inspection classification: PENDING
A67 inspection diagnostic: PENDING
qualification: READY
all three source effect gates: False
```

Any NOT_READY, exception, abandoned ownership, recovery-required state, staging
artifact, identity mismatch, or changed gate is a STOP. Do not repair or retry
blindly.

The qualification result is point-in-time evidence only and does not authorize
execution.

## Explicit stop before PD2D2

After real-host qualification passes, stop.

Do not automatically:

- change `PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED` to
  `True`;
- invoke the production PD2C executor;
- create any Paper-v2 transition/receipt;
- rerun after an ambiguous/interrupted attempt.

PD2D2 requires fresh explicit user authorization for the exact gate change and
first one-shot real Paper-v2 mutation.
