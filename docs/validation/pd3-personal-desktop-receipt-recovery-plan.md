# PD3 Personal-Desktop Receipt-Recovery Validation Plan

Status: **FROZEN SOURCE-ONLY PLAN — NO PRODUCTION RECOVERY EFFECT AUTHORIZATION**

Architecture:

```text
docs/architecture/109-personal-desktop-paper-receipt-recovery-authority.md
```

## Goal

Validate a narrow personal-desktop authority layer around the existing
Architecture-67 completed-receipt recovery path. PD3 must prove that a crash
after transition finalization but before receipt finalization can be recovered
without rerunning the paper cycle, while a healthy or ambiguous account remains
non-mutating and fail-closed.

The current production Paper-v2 account is healthy and already verifies the
first operation as `ALREADY_APPLIED`. PD3 production validation is therefore
read-only. No artificial crash is created in the real account.

## Frozen baseline

Starting checkpoint for PD3 design/implementation:

```text
commit 4861292af48a53f6c01240c6a1ba947d7e6121f3
tree   6ca11ae9c8c0852024de866292196e0dad459730
branch feature/personal-desktop-paper-runtime
```

PD2 final accepted source remains:

```text
commit f05921244057052158a57b360e9bf556209b9654
tree   35a5a7e1d59bbe90ca303b6037d29dc7fc085f4c
```

Final PD2 certification:

```text
5146 passed, 17 skipped
Ruff check PASS
Ruff format --check PASS (457 files)
git diff --check PASS
```

Publication freeze remains:

```text
b125cbb1c80a827f74018cf2955b9a27ba69fa90
```

## Gate separation checkpoint

Before implementation, preserve these existing gates unchanged and false:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED           = False
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED             = False
PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED = False
```

The existing `PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED` is reserved for
Architecture-103 provisioning-staging recovery. PD3 introduces a separate
steady-state receipt-recovery gate:

```text
PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED = False
```

No test may enable a real production gate. Focused tests exercise future-enabled
behavior only through private disposable authority seams.

## PD3-A — Recovery-only Architecture-67 primitive

Add a public/reusable generic recovery-only coordinator entry point in the
Architecture-67 layer rather than calling the dual-purpose
`execute_paper_operation_once()` from production recovery code.

Required contract:

- accepts exact operation root, verified execution inputs, and an output
  capability;
- performs read-only inspection before any output effect;
- only exact `BLOCKED / FINALIZED_TRANSITION_WITHOUT_RECEIPT` may enter existing
  completed-receipt recovery logic;
- exact `ALREADY_APPLIED` returns benign no-op evidence;
- all other states return blocked/conflicting evidence without mutation;
- no code path invokes `execute_checkpointed_verified_snapshot_paper_cycle`;
- no new transition is created;
- no failed receipt is created;
- no retry or replacement operation exists;
- transition bytes remain unchanged through recovery.

Focused tests must include a runtime sentinel that raises if called and prove the
sentinel remains uncalled for every recovery-only classification.

## PD3-B — Dedicated recovery qualification authority

Do not relax `read_personal_desktop_paper_account()`. Its current rejection of a
finalized transition without a verified receipt remains an ordinary-account
safety invariant.

Add a dedicated recovery read/qualification path that can establish one of:

```text
NO_RECOVERY_REQUIRED
RECEIPT_RECOVERY_REQUIRED
BLOCKED
```

`RECEIPT_RECOVERY_REQUIRED` requires exactly one terminal lineage edge whose
finalized transition fully verifies and whose matching receipt is absent, with
no receipt staging or other incomplete/ambiguous state.

Qualification must independently verify:

- fixed anchor/GENESIS identity and bytes;
- exact Trading token and genuine C1 identity;
- complete transition graph and unique A66 lineage tip;
- every transition edge/report/successor/snapshot;
- every installed non-target receipt;
- bounded exact historical configuration dependencies;
- absence of transition and receipt staging;
- exact terminal missing-receipt target;
- reconstructed original operation/application identities;
- read-only A67 inspection exactly reports
  `FINALIZED_TRANSITION_WITHOUT_RECEIPT`.

Nonterminal missing receipt, more than one missing receipt, invalid receipt,
staging, malformed layout, conflicting lineage, unsafe object, or missing
historical dependency must block.

## PD3-C — Original-operation reconstruction

The transition does not contain all operation identity material, especially the
caller idempotency UUID. Recovery therefore must not infer missing identity from
filesystem names or transition fields.

The production-facing PD3 API accepts genuine C1/P2 provenance plus the exact
semantic facts of the original operation:

```text
history seed
strategy configuration
caller idempotency UUID
open reference
policies
planning/submitted/filled timestamps
metadata
bounded historical cycle-configuration payloads
```

It accepts no caller-selected root, SID, mutex, native API, output capability,
raw A67 inputs, prior-lineage object, target transition path, inspector, recovery
callable, or gate override.

Inside the account mutex, qualification derives the predecessor-lineage prefix
for the terminal missing-receipt edge and rebuilds the original plan/request and
operation/application IDs. Detached plan verification and exact transition
reconciliation are mandatory before recovery can be considered.

## PD3-D — Personal-desktop recovery boundary

Add a production-facing function whose effectful branch is disabled by default.
The boundary must preserve this order:

```text
genuine C1/P2
-> acquire PD2A account mutex
-> dedicated recovery qualification
-> exact original-operation reconstruction
-> require FINALIZED_TRANSITION_WITHOUT_RECEIPT
-> require receipt-recovery gate true
-> require publication/provisioning-recovery/supervised-execution gates false
-> open recovery-only output capability
-> re-inspect/reverify
-> recovery-only Architecture-67 call exactly once
-> require RECEIPT_RECOVERED or benign ALREADY_APPLIED
-> ordinary Paper-v2 account reread must now succeed
-> read-only A67 inspection must now be ALREADY_APPLIED
-> close capability
-> release mutex
```

`ABANDONED_OWNER` blocks before recovery. The public result exposes only
non-authorizing IDs/classifications/booleans and no paths or raw evidence.

## PD3-E — Recovery-only output capability gate

Reuse the existing fixed-namespace output capability implementation if practical,
but add a distinct production opener for receipt recovery. The existing PD2C
execution opener remains unchanged.

The recovery opener succeeds only when:

```text
receipt recovery gate = True
production publication gate = False
provisioning recovery gate = False
supervised execution gate = False
```

Focused tests must prove every other gate combination fails closed and that the
returned capability is one-shot and never escapes the recovery boundary.

## Focused regression matrix

At minimum cover:

1. exact terminal finalized transition + no receipt -> qualified recovery;
2. same state -> recovery-only A67 returns `RECEIPT_RECOVERED`;
3. recovered receipt bytes equal canonical expected bytes;
4. transition report/checkpoint bytes before and after recovery are identical;
5. paper-cycle runtime sentinel called zero times;
6. exact completed receipt -> `ALREADY_APPLIED`, zero writes;
7. nonterminal missing receipt -> blocked;
8. two missing receipts -> blocked;
9. transition staging -> blocked;
10. receipt staging -> blocked;
11. invalid/malformed receipt -> blocked;
12. mismatched application/operation/caller key -> blocked;
13. stale or conflicting lineage -> blocked;
14. missing historical configuration -> blocked;
15. wrong P2 provenance -> blocked;
16. wrong/non-genuine C1 -> blocked;
17. wrong/elevated Trading principal -> blocked;
18. mutex abandoned -> blocked;
19. output capability wrong gate combination -> blocked;
20. ordinary account reader still rejects missing-receipt state;
21. post-recovery ordinary account reader succeeds and verifies receipt;
22. post-recovery A67 inspection reports `ALREADY_APPLIED`;
23. disposable test seam rejects genuine production callables;
24. all four production gates remain false in committed source.

Preserve the existing Architecture-67 receipt-recovery tests as regressions.

## Expected implementation surface

The exact file set is not frozen until Sol-High implementation planning reviews
the current seams, but implementation should remain narrow. Likely areas are:

```text
src/trading_bot/cli/paper_operation_execution.py
src/trading_bot/runtime/personal_desktop_paper_runtime_output.py
new personal-desktop receipt-recovery runtime module(s)
runtime/__init__.py only if a new public API is intentionally exported
focused tests for generic recovery-only and personal-desktop recovery authority
```

Do not modify the generic paper-cycle engine, deterministic strategy/risk logic,
C3 provider authority, broker interfaces, or publication freeze unless a concrete
architecture contradiction is found. Such a contradiction is a STOP and returns
to ChatGPT for architecture review.

## Verification cadence

During implementation, run focused tests only, with the known Windows basetemp
rule when pytest may use temp fixtures:

```powershell
$BaseTemp = "F:\AI\temp\pytest\pd3-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Force 'F:\AI\temp\pytest' | Out-Null
& $Python -m pytest <focused PD3 files> --basetemp="$BaseTemp" -p no:cacheprovider
```

Do not persistently export `PYTHONPATH`, `TEMP`, or `TMP` for normal pytest.
Run targeted Ruff and `git diff --check` during the checkpoint.

A full repository suite is deferred until the final PD3 source tree is exact-
reviewed. At that final gate use a fresh explicit external `--basetemp`.

## Real-host validation

After source certification, run one read-only Trading-principal qualification
against the current healthy Paper-v2 account with every effect gate false.
Expected result:

```text
NO_RECOVERY_REQUIRED / ALREADY_APPLIED
```

The current first operation is already complete, so real-host validation must
perform no write and must not enable the new recovery gate.

Do not create, delete, rename, alter, or hide any real transition or receipt to
manufacture a recoverable condition.

## Production recovery authorization boundary

A real receipt-recovery mutation is not part of routine PD3 acceptance. If a
future genuine operation crashes after transition commit and before receipt
commit, the operator must first obtain exact read-only qualification evidence.
Only then may a separate reviewed source/gate checkpoint and fresh explicit user
authorization permit one recovery invocation.

No retry, new paper cycle, provider call, broker call, scheduler action, or
unrelated filesystem repair is implied by receipt-recovery authorization.

## Completion criteria

PD3 may be marked complete when all are true:

```text
ARCH109_DESIGN_ACCEPTED              = YES
PD3_RECOVERY_ONLY_A67_ACCEPTED       = YES
PD3_RECOVERY_QUALIFIER_ACCEPTED      = YES
PD3_PERSONAL_DESKTOP_BOUNDARY_ACCEPTED = YES
PD3_SOURCE_CERTIFIED                 = YES
PD3_REAL_HOST_READ_ONLY_VALIDATED    = YES
ALL_EFFECT_GATES_CLOSED              = YES
PD3                                  = COMPLETE
```

The next milestone is PD4 unattended simulated paper operation under the
non-admin Trading account. PD4 must durably retain the exact original invocation
facts required to reconstruct a PD3 recovery target after process restart.