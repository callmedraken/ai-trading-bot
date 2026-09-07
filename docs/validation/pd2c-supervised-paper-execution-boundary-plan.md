# PD2C Supervised Paper Execution Boundary — Validation Plan

## Scope

Implement and certify the Architecture-104 source-only supervised execution boundary.

PD2C consumes one active PD2B3 prepared operation and routes it to the existing Architecture-67 execute-once machinery only through a source-owned effect gate and fixed production-root contract.

PD2C source work must not perform a real production Paper-v2 mutation.

## Starting invariants

Expected accepted source before PD2C implementation:

```text
PD2B3 commit: f86f8c8758b3e8941e5bbfa26d40892433cf0110
PD2B3 tree:   9f883335ec13a9385113b2c310c6009a8a0e72aa
```

Documentation-only closeout commits may appear on top of that source before Codex starts; the task prompt must pin the actual then-current HEAD/tree.

Both Paper-v2 effect gates must remain false throughout PD2C implementation/certification.

## Required source behavior

The production-facing PD2C API must:

1. require genuine production authority and the same genuine P2/provenance inputs needed by PD2B3;
2. internally enter the existing PD2B3 supervised preparation rather than accept a caller-created preparation;
3. consume the private active prepared binding only while PD2B3 is active;
4. reconcile the binding operation root exactly to `F:\AITradingBot\Paper-v2\runtime`;
5. reject a mismatching root before calling Architecture 67;
6. fail closed before Architecture-67 execution while the production execution gate is false;
7. use an injected/disposable executor seam for tests only;
8. when execution is allowed through that test seam, invoke the existing Architecture-67 execute-once contract exactly once;
9. never automatically retry runtime execution;
10. keep the PD2A account mutex held through the entire executor call and terminal result handling;
11. remove/expire the private prepared binding before mutex release through the existing PD2B3 context semantics;
12. return only immutable non-authorizing result/audit evidence.

`ABANDONED_OWNER` remains blocked before PD2C execution through PD2B3 and must not be bypassed.

## Prohibited production API inputs

The production-facing function must not accept any of the following from callers:

```text
operation_root
Path
VerifiedPaperOperationExecutionInputs
PaperOperationIntent
application_id
operation_id
paper_account_id
lineage/prior checkpoint
a prebuilt PD2B3 preparation
mutex name
Trading SID
native handle
timeout
production effect gate override
executor override
recovery-mode override
```

A private test-only factory may inject an executor and disposable supervised preparation factory, but those seams must not be exported as production authority.

## Test requirements

Focused tests must prove at least:

- invalid/forged C1 fails before P2/B1/executor;
- forged/disposable P2 cannot enter the production boundary;
- production boundary does not accept a prebuilt preparation;
- private prepared binding is consumed only while active;
- executor observes that PD2B3/B1 scope is still active during the call;
- exact fixed Paper-v2 runtime root is required;
- a mismatching root blocks before executor invocation;
- production gate false blocks before executor invocation;
- caller cannot override the gate;
- injected disposable test seam can exercise one execute-once call without enabling production effects;
- executor is called exactly once on the allowed test path;
- executor exceptions propagate/fail closed without retry;
- blocked/conflicting/failed/success/recovered Architecture-67 classifications are passed through without being reinterpreted as permission for another runtime;
- result does not expose raw execution inputs or operation-root authority;
- body/return/exception paths unwind the account mutex;
- PD2A poisoned-release semantics remain intact;
- `ABANDONED_OWNER` still blocks before PD2C executor invocation;
- no provider/broker/live/scheduling imports/effects are added;
- production and recovery effect gates remain false;
- publication freeze remains unchanged.

## Focused verification

During implementation run only:

```text
new PD2C tests
PD2B3 preparation tests
PD2B1 supervised-cycle tests
PD2A mutex tests if cleanup/lifetime surfaces are touched
Architecture-67 inspection/execution focused tests if interface surfaces are touched
Ruff check on changed files
Ruff format --check on changed files
git diff --check
```

Do not run the full repository suite during iteration.

## Broad certification gate

After ChatGPT/Sol exact-diff review accepts PD2C source, the user runs one broad repository certification using pinned worktree provenance and a fresh external pytest base temp.

PD2C is complete only if:

```text
full pytest: PASS
Ruff check: PASS
Ruff format --check: PASS
git diff --check: PASS
worktree/index: clean
production effect gate: False
recovery effect gate: False
publication freeze: unchanged
no production Paper-v2 mutation occurred
```

## Production-effect boundary

PD2C source certification does not authorize a real Paper-v2 write.

A later PD2D or separately named production-effect checkpoint must explicitly review and authorize any source gate enablement and the first real one-shot mutation.
