# Project Status and Roadmap

This is the canonical high-level project status for AI Trading Bot. Detailed
subsystem contracts live under `docs/architecture/` and `docs/validation/`;
`docs/AI_TRADING_BOT_HANDOFF.md` is the canonical cross-chat resume document.

## Product objective and deployment profile

Build a conservative automated trading platform for a **closed, single-owner
personal Windows desktop**, progressing through deterministic research,
supervised simulated paper, unattended simulated paper, broker-paper, long
paper soak, personal-desktop live-readiness, tiny restricted live operation,
and a polished GUI.

Stable constraints:

```text
US stocks / ETFs
long-only
no margin / leverage / options / shorts / crypto
deterministic risk approval
paper-by-default
complete auditability
```

**Production/live trading remains NO-GO.**

## Primary development line

```text
repository: callmedraken/ai-trading-bot
integration baseline: bd88ee966bff455f9fc897d6cfdfafdd807f27e2
Architecture-94 P2 base: a810122a96b6fc90da25d71eede8da64b7272c98
branch: feature/personal-desktop-paper-runtime
worktree: F:\AI\worktrees\ai-trading-bot-personal-desktop
latest accepted PD4-D source: 6e606531bf0c6c11793fd89b2adb54f0db170869
latest accepted PD4-D tree:   2b1315f9332148fac20b087d760630b699db6fb1
```

Architecture checkpoints:

```text
Architecture 102  personal-desktop profile adoption
Architecture 103  Paper-v2 deployment/provisioning authority
Architecture 104  supervised A67 execution boundary
Architecture 105  first-mutation qualification
Architecture 106  first Paper-v2 execution preparation
Architecture 107  first Paper-v2 output authority hardening
Architecture 108  first Paper-v2 post-mutation reconciliation
Architecture 109  personal-desktop Paper-v2 receipt-recovery authority
Architecture 110  personal-desktop unattended Paper-v2 operation authority
```

## Mandatory personal-desktop security baseline

- steady-state trading runs under the dedicated non-admin `Trading` account;
- credentials stay outside source/plain config and use reviewed Windows-backed
  storage;
- paper is default; future live requires a separate explicit arming boundary;
- every executable order passes deterministic risk authority;
- strategy/optimizer/GUI/AI/scheduler/adapters cannot bypass risk;
- durable state outranks process-local assumptions;
- ambiguous provider/broker effects reconcile or fail closed rather than being
  blindly retried;
- source-governed runtime/config/state locations use practical least privilege;
- crash/restart, duplicate invocation, stale input, corruption/conflict, and
  receipt recovery fail closed unless exact reviewed authority is present.

## Frozen C3 production state

Accepted C3 release source:

```text
82ba29ae2c2cc6bb3544077db0ee21868e6d5693
```

All six authorized real-provider effects are consumed. Call #5 is permanently
`FAILED / CONFIRMED`. Call #6 is permanently
`SUCCEEDED / CONFIRMED / SUCCESS_SELECTED`. **Provider call #7 is not
authorized.**

Selected call #6:

```text
selection_id: 36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280
snapshot_id: eba46838-44ae-5bec-97bf-98c6639ae6a7
artifact SHA-256: 31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
artifact byte length: 1291
captured_at: 2026-08-29T09:46:43.769105+00:00
```

Production identities:

```text
host: DESKTOP-I4DOKM7
Trading account: DESKTOP-I4DOKM7\Trading
Trading SID: S-1-5-21-1397534616-3988210162-180023805-1009
machine_authority_id: 223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1
authority_epoch_id: e6f3de5d-1412-40ad-a022-8b33e72a5f6d
runtime: F:\AITradingBot\runtime\python.exe
authority DB: F:\AITradingBot\Authority\authority.sqlite3
credential policy: windows-credential-manager-alpaca-market-data/v2
```

## Architecture 94 accepted product work

```text
P1 pure strategy history / deterministic strategy plan
1028e60b99c27cef0994f40d6ce381392abfb0f8

P2 read-only selected-C3 snapshot authority
a810122a96b6fc90da25d71eede8da64b7272c98
```

Preserve the product composition:

```text
selected verified C3 snapshot
+ explicit deterministic strategy history
+ authoritative paper-account tip
-> deterministic strategy plan
-> planner / proposal
-> deterministic portfolio risk
-> simulated paper execution
-> successor checkpoint + full-lineage verification
-> Architecture-67 durable transition + receipt
```

## Paper-v2 production authority

Fixed paths:

```text
Paper-v2 root:       F:\AITradingBot\Paper-v2
A67 operation root: F:\AITradingBot\Paper-v2\runtime
receipt parent:     F:\AITradingBot\Paper-v2\runtime\paper-operations
```

Published account:

```text
paper_account_id:   9415cd7b-bf36-5fba-bd58-a0f99119dc21
GENESIS checkpoint: 1832a2b5-8b63-501a-8f7d-f1722c32307b
starting cash:      Decimal("25000")
GENESIS as_of:      2026-08-29T09:46:43.769105+00:00
```

Frozen publication artifacts:

```text
GENESIS  SHA-256 d1a7ff14425c8a797a952860a1102489a4c81cac2a24a45bc3127eb8eb2e9548  length 533
anchor   SHA-256 16c4dba01835c5bc2def91f0103ad79c3da0b5d18af72091b4fdd37fe4353c85  length 465
manifest SHA-256 8fe1d705d59a79207ab6236af71becee0051042dc7b3ecaf23bb7f5531cb0029  length 532
freeze Git blob b125cbb1c80a827f74018cf2955b9a27ba69fa90
```

Retained failed v1 state:

```text
F:\AITradingBot\Paper                    ABSENT
F:\AITradingBot\.Paper.provisioning-v1  PRESENT / RETAINED / UNTOUCHED
```

Never rerun the old v1 publisher or delete, repair, rename, migrate, or reuse
the retained v1 staging tree as incidental cleanup.

## PD1 — personal-desktop Paper-v2 authority — COMPLETE

Completion record:

```text
docs/validation/pd1-personal-desktop-paper-v2-completion.md
```

## PD2 — reliable supervised manual paper cycle — COMPLETE

Completion records:

```text
docs/validation/pd2a-paper-account-runtime-mutex-completion.md
docs/validation/pd2b-supervised-paper-composition-completion.md
docs/validation/pd2c-supervised-paper-execution-boundary-completion.md
docs/validation/pd2d2-first-real-paper-operation-completion.md
```

Canonical PD2 state:

```text
PD2A = COMPLETE
PD2B = COMPLETE
PD2C = COMPLETE
PD2D1 = COMPLETE
PD2D2 = COMPLETE
PD2 = COMPLETE
```

First durable Paper-v2 operation:

```text
operation_id:         307f769a-f09a-539d-b12d-3fb51b973809
application_id:       78a1bae8-51ac-5bf0-b159-500768c758fc
cycle_result_id:      854f133e-d9cd-5a9d-be63-0eb4137787db
successor checkpoint: ed4640e5-0630-525d-b916-d50e31e3ba2a
receipt_status:       COMPLETED
receipt_outcome:      NO_ACTION
```

Independent post-mutation reconciliation proved:

```text
result:                    RECONCILED
lineage_edge_count:        1
account_cash:              25000
position_count:            0
inspection_classification: ALREADY_APPLIED
inspection_diagnostic:     ALREADY_APPLIED
```

PD2 final broad certification:

```text
5146 passed, 17 skipped in 1505.92s
Ruff check: PASS
Ruff format --check: PASS (457 files)
git diff --check: PASS
```

## PD3 — supervised crash/recovery validation — COMPLETE

Architecture:

```text
docs/architecture/109-personal-desktop-paper-receipt-recovery-authority.md
```

Completion record:

```text
docs/validation/pd3-personal-desktop-receipt-recovery-completion.md
```

PD3 wraps the existing Architecture-67 restart-safe receipt-recovery behavior;
it does not introduce a second recovery engine. The accepted production
composition is:

```text
genuine C1 + genuine P2
-> pre-lock recovery qualification
-> existing PD2A account mutex
-> fresh authoritative post-lock qualification
-> exact target agreement
-> reconstruct original operation from explicit semantic inputs
-> exact four-gate check
-> receipt-only output capability
-> A67 reinspection
-> recovery-only A67 call at most once
-> strict ordinary account reread
-> exact ALREADY_APPLIED verification
-> capability close
-> mutex release
```

Exact recovery semantics:

```text
finalized transition + missing receipt + exact verification
-> same canonical receipt may be reconstructed
-> strategy/runtime execution count = 0
-> no new transition

verified completed transition + completed receipt
-> ALREADY_APPLIED
-> writes = 0

staging / malformed / altered / ambiguous / mismatched evidence
-> BLOCKED
-> no cleanup, repair, replacement, or blind retry
```

Accepted PD3 source:

```text
commit e690ce83d6c53507d9e93dca97bcb79191c62a0b
tree   522f41115d2079ae777f667a19e5179c1d492e1f
```

Final broad source certification:

```text
5285 passed, 17 skipped in 1478.19s
Ruff check: PASS
Ruff format --check: PASS (467 files)
git diff --check: PASS
worktree/index: clean
```

Real-host acceptance ran under `DESKTOP-I4DOKM7\Trading`, SID
`S-1-5-21-1397534616-3988210162-180023805-1009`, non-elevated, with exact
branch/HEAD/tree/origin/clean provenance. The production-interpreter launcher
probe passed, followed by one actual read-only validation:

```text
result:                         VALIDATED
all_effect_gates_false:         true
qualification_status:           NO_RECOVERY_REQUIRED
qualification_diagnostic:       VERIFIED_COMPLETE_ACCOUNT
inspection_classification:      ALREADY_APPLIED
inspection_diagnostic:          ALREADY_APPLIED
receipt_status:                 COMPLETED
receipt_outcome:                NO_ACTION
account_cash:                   25000
position_count:                 0
recovery_invocation_performed:  false
receipt_evidence_produced:      false
exit:                           0
```

Canonical PD3 state:

```text
ARCH109_DESIGN_ACCEPTED                 = YES
PD3_RECOVERY_ONLY_A67_ACCEPTED          = YES
PD3_RECOVERY_QUALIFIER_ACCEPTED         = YES
PD3_ORIGINAL_OPERATION_RECONSTRUCTION   = YES
PD3_EFFECT_CONTAINMENT_ACCEPTED         = YES
PD3_PERSONAL_DESKTOP_BOUNDARY_ACCEPTED  = YES
PD3_SOURCE_CERTIFIED                    = YES
PD3_REAL_HOST_READ_ONLY_VALIDATED       = YES
ALL_EFFECT_GATES_CLOSED                 = YES
REAL_RECOVERY_MUTATION_PERFORMED        = NO
PD3                                     = COMPLETE
```

## Current milestone — PD4 unattended simulated paper under Trading

Architecture 110 is the accepted unattended-operation contract:

```text
docs/architecture/110-personal-desktop-unattended-paper-operation-authority.md
```

Accepted PD4 source checkpoints now cover:

```text
PD4-A   durable unattended invocation identity/model and verification
PD4-B   durable invocation storage/read/publication/provisioning boundaries
PD4-C   read-only unattended startup qualification under the same PD2A mutex
PD4-D   unattended Paper-v2 execution composition with effects still closed
PD4-D-R1 explicit non-private shared composition interfaces
```

The accepted PD4-D/R1 source is:

```text
commit 6e606531bf0c6c11793fd89b2adb54f0db170869
tree   2b1315f9332148fac20b087d760630b699db6fb1
```

PD4 preserves these authority rules:

- Task Scheduler is only an untrusted wake-up source and supplies no semantic
  trading arguments;
- durable unattended invocation state, the PD2A account mutex, and Architecture
  67 remain the authority for identity, duplicate suppression, execution, and
  restart recovery;
- missing receipt never becomes permission for a fresh execution;
- the selected verified C3 snapshot remains authoritative; no unattended
  provider capture is authorized;
- startup and post-run reconciliation revalidate C1, P2, all six effect gates,
  durable invocation storage, A67 state, receipt/lineage evidence, and account
  state before releasing the mutex;
- the public PD4-C qualification result is not reusable execution authority.

The next source checkpoint is **PD4-E**: add the reviewed source-checkout
launcher with **no semantic command-line arguments** and freeze the Windows Task
Scheduler task contract. PD4-E is source-only. It must not install, modify, run,
or enable a real scheduled task and must not authorize a real unattended
Paper-v2 execution.

After PD4-E exact review, PD4-F performs final source certification plus the
Trading-principal read-only qualification. Any actual Task Scheduler
installation/modification remains a separate protected Windows effect boundary.

## Primary roadmap

```text
PD0   personal-desktop profile adoption                     COMPLETE
PD1   personal-desktop paper-account authority v2           COMPLETE
PD2   reliable supervised manual paper cycle                COMPLETE
  PD2A account-scoped Windows mutex + admission             COMPLETE
  PD2B supervised source-only composition                   COMPLETE
  PD2C supervised A67 execution boundary                    COMPLETE
  PD2D1 read-only first-mutation qualification              COMPLETE
  PD2D2 first real Paper-v2 mutation + reconciliation       COMPLETE
PD3   supervised crash/recovery validation                  COMPLETE
PD4   unattended simulated paper under Trading              CURRENT
PD5   broker-paper integration
PD6   broker-paper soak / operational hardening
PD7   personal-desktop live-readiness
PD8   tiny restricted live -> gradual maturity
```

## Effect gates and still-not-authorized actions

All current Paper-v2 effect gates remain closed:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED                       = False
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED                         = False
PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED             = False
PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED                 = False
PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED             = False
PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED  = False
```

Still not authorized:

```text
provider call #7
real Paper-v2 receipt-recovery mutation
Task Scheduler installation/modification or real unattended Paper-v2 execution
broker order submission
live trading
changing any closed effect gate without a reviewed checkpoint
old v1 publisher rerun
v1 staging delete/repair/rename/migration/reuse
Paper-v2 manual mutation outside reviewed effect checkpoints
account/group/password changes
LSA rights/policy changes
KSP/signing/private-export effects
merge/rebase/force-push/amend/PR metadata changes without explicit approval
```

## Workflow invariants

- ChatGPT/Sol owns architecture/security review, exact GitHub diff review, test
  gates, merge/deployment/production decisions, and next milestones.
- After a reviewed checkpoint passes, automatically continue to the next safe
  scoped checkpoint; stop at explicitly protected production/effect boundaries.
- Tiny scoped status/handoff/docs closeouts are ChatGPT-direct by default.
- Codex uses Luna Extra High for frozen/local mechanical work, Astra for bounded
  discovery-aware/cross-module work, and Sol High for native Windows/security/
  authority/order/crash/recovery and other safety-sensitive implementation.
- Model choice never transfers architecture or acceptance authority.
- No subagents unless explicitly requested.
- Codex runs focused tests/checks during implementation; broad/full
  certification is normally user-run locally at the final gate.
- Never `git add .` or `git add -A`; exact-file stage only.
- Worktree/branch/HEAD/tree mismatch is a STOP; do not self-correct.
- Controlled Windows pytest uses a fresh external
  `F:\AI\temp\pytest\<purpose>-<unique>` via explicit `--basetemp` and normally
  `-p no:cacheprovider`; do not globally change `TEMP`, `TMP`, or persistently
  set `PYTHONPATH` for normal pytest collection.
- Source-checkout operator CLIs that must run independently of the current
  working directory/package environment use a reviewed `scripts/` launcher that
  selects the checkout `src` explicitly; production-interpreter import probes
  must exercise that launcher before real-host invocation.
- Preserve unrelated generated/untracked reports and historical evidence.
- No merge/rebase/force-push/amend/PR metadata/review-thread changes without
  explicit approval.

## Documentation workflow

At accepted milestones review/update:

```text
README.md
docs/PROJECT_STATUS.md
docs/AI_TRADING_BOT_HANDOFF.md
relevant docs/architecture/*
relevant docs/validation/*
```

Docs-only closeouts do not require a new full repository suite when exact diff
review proves no source/test change.
