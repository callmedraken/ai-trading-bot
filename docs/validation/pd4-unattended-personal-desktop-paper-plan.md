# PD4 Unattended Personal-Desktop Paper Validation Plan

Status: **FROZEN SOURCE-ONLY PLAN — NO UNATTENDED EFFECT AUTHORIZATION**

Architecture:

```text
docs/architecture/110-personal-desktop-unattended-paper-operation-authority.md
```

## Goal

Move the accepted Paper-v2 pipeline from manual/supervised invocation to
unattended simulated paper operation under the dedicated non-admin `Trading`
account without weakening C1/P2, the PD2A account mutex, Architecture-67 durable
idempotency, PD3 receipt recovery, or deterministic strategy/risk authority.

The scheduler is only a wake-up source. The application must retain durable,
exact semantic invocation facts before execution so restart/recovery never has
to guess caller idempotency or operation identity from filesystem state.

No scheduled task is installed and no unattended Paper-v2 effect is performed
by this plan.

## Frozen starting baseline

PD3 final accepted source:

```text
commit e690ce83d6c53507d9e93dca97bcb79191c62a0b
tree   522f41115d2079ae777f667a19e5179c1d492e1f
branch feature/personal-desktop-paper-runtime
```

PD3 completion record:

```text
docs/validation/pd3-personal-desktop-receipt-recovery-completion.md
```

Final PD3 source certification:

```text
5285 passed, 17 skipped in 1478.19s
Ruff check PASS
Ruff format --check PASS (467 files)
git diff --check PASS
```

Real-host PD3 read-only acceptance:

```text
Trading principal non-admin: PASS
production-interpreter launcher probe: PASS
qualification: NO_RECOVERY_REQUIRED / VERIFIED_COMPLETE_ACCOUNT
A67 inspection: ALREADY_APPLIED / ALREADY_APPLIED
recovery invocation performed: false
receipt evidence produced: false
exit: 0
```

Publication freeze remains:

```text
b125cbb1c80a827f74018cf2955b9a27ba69fa90
```

## Standing gates

Existing gates remain false:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED           = False
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED             = False
PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED     = False
```

PD4 will introduce:

```text
PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED = False
```

No source-only test may arm a real production gate. Future-enabled behavior is
tested through disposable one-shot seams.

## PD4-A — Canonical unattended invocation model

Create a pure deterministic model and canonical serializer/verifier for the
unattended invocation bundle.

The model must bind the exact semantic facts needed to reproduce the operation
and satisfy PD3 recovery after restart. At minimum freeze:

```text
schema/version
invocation_id
paper_account_id
predecessor checkpoint identity
intended trading session
selection_id / selected_snapshot_id / snapshot digest+length
strategy-history seed bytes/evidence
strategy configuration
caller idempotency UUID
open reference
paper-cycle policies
planning/submitted/filled timestamps
metadata
unattended policy/version identity
```

Requirements:

- deterministic UUID5 identity from explicit versioned semantic material;
- canonical UTF-8/JSON serialization consistent with project conventions;
- detached verification/replay;
- no filesystem paths, clock reads, environment values, Python hashes, UUID4,
  object identity, or scheduler metadata in deterministic identity;
- immutable caller input snapshot before identity derivation;
- exact rejection of duplicate/malformed/noncanonical data;
- pure source/test only; no filesystem, C1, P2, provider, scheduler, or Paper-v2
  effect.

## PD4-B — Fixed invocation-bundle storage authority

Add a fixed source-owned production namespace:

```text
F:\AITradingBot\Paper-v2\runtime\unattended-invocations
```

Freeze canonical staging/final names before implementation.

Add read authority that classifies at least:

```text
ABSENT
FINALIZED_IDENTICAL
STAGING_PRESENT
CONFLICTING
BLOCKED
```

Add a narrow output capability that may publish only one canonical unattended
invocation bundle in that namespace. It must not be able to write:

- A67 transition directories;
- A67 receipt directories/files;
- C3 market-data output;
- broker/live artifacts;
- arbitrary caller paths.

Reuse hardened Windows fixed-parent, ACL/owner, no-follow/pinned-object,
write-through, no-clobber rename, reread/reverify, and one-shot capability
patterns.

The real opener remains unreachable while the unattended gate is false.

## PD4-C — Read-only startup qualification/reconciliation

Build a production read-only qualifier under genuine C1/P2 and the existing
PD2A account mutex.

Required ordering:

```text
genuine C1 + genuine P2
-> strict pre-lock account read for immutable account ID
-> acquire same PD2A mutex
-> strict post-lock account reread
-> inspect invocation namespace
-> inspect relevant A67 durable state
-> classify exactly
-> release mutex
```

It must distinguish at least:

```text
HEALTHY_NO_PENDING_INVOCATION
READY_SAME_INVOCATION
ALREADY_APPLIED
RECEIPT_RECOVERY_REQUIRED
BLOCKED
```

Rules:

- `RECEIPT_RECOVERY_REQUIRED` can never be converted to fresh execution;
- ambiguous/staging/conflicting invocation or A67 state blocks;
- no state cleanup/repair/rewrite;
- scheduler history and process exit status are ignored as authority;
- public evidence is sanitized and non-authorizing.

## PD4-D — Unattended execution composition, gate false

Compose the production-facing unattended paper boundary while the new gate
remains false.

Expected order:

```text
C1/P2 validation
-> pre-lock account identity read
-> same PD2A mutex
-> post-lock strict account read
-> resolve/finalize exact invocation bundle
-> reconstruct operation only from verified durable invocation facts
-> A67 inspection
-> block on recovery-required/ambiguous state
-> exact unattended-gate check
-> narrow production output capability
-> A67 execution at most once
-> strict account reread
-> final ALREADY_APPLIED verification
-> capability close
-> mutex release
```

Do not call the supervised public boundary as a shortcut if doing so couples
unattended authority to the supervised gate. Reuse lower-level reviewed
preparation/execution primitives without duplicating strategy/risk/A67 logic.

`ABANDONED_OWNER` blocks before any effect.

## PD4-E — No-argument launcher and scheduler contract

Add a source-owned `scripts/` launcher using the accepted checkout-selection
pattern. The production launcher exposes no semantic trading arguments.

Freeze the intended Windows Task Scheduler contract as documentation and pure
validation only. At minimum specify:

- exact launcher path and production interpreter;
- dedicated non-admin Trading principal;
- non-elevated execution;
- source-owned working-directory independence;
- no semantic CLI parameters;
- no credential material on command line/environment;
- trigger timing is wake-up only, not trading authority;
- task overlap settings are defense-in-depth only; PD2A mutex remains authority;
- task installation/modification requires a separate explicit operator effect
  checkpoint.

Do not install or modify a task in source-only PD4-E.

## PD4-F — Final source certification and read-only host qualification

After exact source review, run one broad repository certification using a fresh
external Windows pytest basetemp.

Then under the genuine non-admin Trading principal:

1. verify branch/HEAD/tree/origin/clean provenance;
2. run production-interpreter launcher import/help probe;
3. run a read-only unattended qualification with all effect gates false;
4. require no Paper-v2 write, no invocation-bundle publication, no recovery,
   no provider call, no broker call, and no scheduler mutation.

The healthy current account must remain unchanged.

## Market-data automation boundary

Architecture 110 intentionally keeps unattended C3 provider capture separate.
PD4 source may consume a genuine already-selected P2 snapshot, but a complete
daily unattended product eventually requires a separately reviewed checkpoint
that extends C3 from manually invoked provider capture to unattended invocation.

That future checkpoint must preserve Architecture-77/82 reservation, one-shot
provider attempt, credential containment, isolated child, lifecycle-arbiter
ordering, verified snapshot selection, and conservative recovery.

Until separately authorized:

```text
provider call #7 = NOT AUTHORIZED
```

No Paper-v2 unattended gate implies provider authority.

## Focused regression matrix

At minimum prove:

1. canonical invocation identity is deterministic and versioned;
2. every recovery-relevant semantic input changes invocation identity or fails
   exact verification according to the frozen contract;
3. paths/cwd/environment/scheduler metadata do not enter identity;
4. canonical invocation serialization replays exactly;
5. invocation storage ABSENT/FINALIZED_IDENTICAL/STAGING/CONFLICTING behavior;
6. bundle staging blocks rather than being cleaned;
7. narrow capability cannot create A67 transition/receipt output;
8. parent/ACL/owner/object drift blocks;
9. duplicate wakeups converge on the same invocation identity;
10. same-account overlap is serialized by the existing PD2A mutex;
11. abandoned mutex blocks;
12. pre-lock account state is not mutation authority;
13. post-lock reread is authoritative;
14. completed A67 operation returns ALREADY_APPLIED with zero writes;
15. terminal missing receipt returns RECOVERY_REQUIRED and never fresh execution;
16. conflicting/staging A67 state blocks;
17. unattended gate exists and is False;
18. disabled gate blocks after complete qualification and before output/A67
    execution;
19. disposable future-enabled execution calls A67 at most once;
20. strict post-run account reread is mandatory;
21. final A67 inspection must be ALREADY_APPLIED;
22. capability closes before mutex release;
23. exceptions release/poison according to existing mutex semantics;
24. launcher is cwd/package-root independent;
25. production launcher has no semantic CLI override;
26. provider/recovery/broker/live/scheduler-install callables are absent or
    sentinel-unreachable in source-only tests;
27. publication freeze remains unchanged;
28. all real effect gates remain false.

## Verification cadence

Use focused tests during PD4-A through PD4-E. Do not repeatedly run the full
repository suite.

On John's Windows development account, pytest commands that may use temp
fixtures must use a fresh explicit external basetemp:

```powershell
$BaseTemp = "F:\AI\temp\pytest\pd4-<purpose>-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Force 'F:\AI\temp\pytest' | Out-Null
& $Python -m pytest <focused files> --basetemp="$BaseTemp" -p no:cacheprovider
```

Do not persistently set `PYTHONPATH` and do not globally alter `TEMP` or `TMP`.

Run the full suite once at the final exact-reviewed PD4 source tree or earlier
only if a focused failure indicates broad regression risk.

## Real-effect boundaries

The following remain separately authorized effects even after source tests pass:

```text
Windows Task Scheduler task creation/modification
first unattended Paper-v2 execution
receipt-recovery mutation
unattended C3 provider invocation / provider call #7
broker-paper order submission
live trading
```

No source checkpoint or disposable test grants these effects.

## Completion criteria

PD4 source-level foundation may be considered accepted when:

```text
ARCH110_DESIGN_ACCEPTED                    = YES
PD4_INVOCATION_MODEL_ACCEPTED              = YES
PD4_INVOCATION_STORAGE_AUTHORITY_ACCEPTED  = YES
PD4_STARTUP_RECONCILIATION_ACCEPTED        = YES
PD4_UNATTENDED_BOUNDARY_ACCEPTED           = YES
PD4_LAUNCHER_CONTRACT_ACCEPTED             = YES
PD4_SOURCE_CERTIFIED                       = YES
PD4_REAL_HOST_READ_ONLY_VALIDATED          = YES
ALL_REAL_EFFECT_GATES_CLOSED               = YES
```

Full PD4 product completion additionally requires separately reviewed operator
acceptance for the intended unattended deployment and, before truly autonomous
daily operation, a reviewed unattended market-data acquisition checkpoint.

The next roadmap milestone after PD4 is broker-paper integration (PD5).
