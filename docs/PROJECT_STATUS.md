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
latest accepted PD2D2 source: f05921244057052158a57b360e9bf556209b9654
latest accepted PD2D2 tree:   35a5a7e1d59bbe90ca303b6037d29dc7fc085f4c
```

Architecture checkpoints:

```text
Architecture 102 adoption:          fab1d776abcdcbf09fb26a257ea7fc86f6201b26
Architecture 103 + validation plan: 12e41c4e407a79d63ea896773bf8462038ebba27
Architecture 104:                   supervised A67 execution boundary
Architecture 105:                   first-mutation qualification
Architecture 106:                   first Paper-v2 execution preparation
Architecture 107:                   first Paper-v2 output authority hardening
Architecture 108:                   first Paper-v2 post-mutation reconciliation
Architecture 108 R1:                f05921244057052158a57b360e9bf556209b9654
```

## Mandatory personal-desktop security baseline

- steady-state trading runs under the dedicated non-admin `Trading` account;
- credentials stay outside source/plain config and use reviewed Windows-backed
  storage;
- paper is default; future live requires a separate explicit arming boundary;
- every executable order passes deterministic risk authority;
- strategy/optimizer/GUI/AI/scheduler/adapters cannot bypass risk;
- durable state outranks process-local assumptions;
- ambiguous provider/broker effects are reconciled or fail closed rather than
  blindly retried;
- source-governed runtime/config/state locations use practical least privilege;
- crash/restart, duplicate invocation, stale input, corruption/conflict, and
  receipt recovery remain roadmap gates.

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

## PD1 — personal-desktop paper-account authority v2 — COMPLETE

Completion record:

```text
docs/validation/pd1-personal-desktop-paper-v2-completion.md
```

Canonical status:

```text
PD1_ARCHITECTURE_ACCEPTED    = YES
PD1_SOURCE_ACCEPTED          = YES
PD1_SOURCE_CERTIFIED         = YES
PD1_PRODUCTION_READY         = YES
PD1_V2_PUBLISHED             = YES
PD1_TRADING_RUNTIME_VERIFIED = YES
PD1                          = COMPLETE
```

Published account:

```text
paper_account_id:     9415cd7b-bf36-5fba-bd58-a0f99119dc21
GENESIS checkpoint:   1832a2b5-8b63-501a-8f7d-f1722c32307b
starting cash:        Decimal("25000")
GENESIS as_of:        2026-08-29T09:46:43.769105+00:00
```

Frozen artifacts:

```text
GENESIS  SHA-256 d1a7ff14425c8a797a952860a1102489a4c81cac2a24a45bc3127eb8eb2e9548  length 533
anchor   SHA-256 16c4dba01835c5bc2def91f0103ad79c3da0b5d18af72091b4fdd37fe4353c85  length 465
manifest SHA-256 8fe1d705d59a79207ab6236af71becee0051042dc7b3ecaf23bb7f5531cb0029  length 532
freeze Git blob b125cbb1c80a827f74018cf2955b9a27ba69fa90
```

Durable occupancy:

```text
F:\AITradingBot\Paper-v2                    PRESENT / VERIFIED
F:\AITradingBot\.Paper-v2.provisioning      ABSENT
F:\AITradingBot\Paper                       ABSENT
F:\AITradingBot\.Paper.provisioning-v1      PRESENT / RETAINED / UNTOUCHED
```

Never rerun the old v1 publisher or delete, repair, rename, migrate, or reuse
the retained v1 staging tree as incidental cleanup.

## PD2A — account mutex + supervised admission — COMPLETE

Completion record:

```text
docs/validation/pd2a-paper-account-runtime-mutex-completion.md
```

Accepted correction/source checkpoint:

```text
38212c07e0c06c7cf25152c5a362434ded7c3adf
tree 9dc5087b87cfd2c16ef76d97c04fd20d41ba7187
```

PD2A provides the deterministic account-scoped Windows mutex, fixed 30-second
wait, exact kernel owner/DACL validation, explicit `ABANDONED_OWNER`, process-
wide same-account non-reentrancy, and process-lifetime poison after uncertain
`ReleaseMutex` failure.

Final certification: `4720 passed, 17 skipped`; Ruff/diff clean.

## PD2B — supervised paper composition — COMPLETE

Completion record:

```text
docs/validation/pd2b-supervised-paper-composition-completion.md
```

Accepted source:

```text
PD2B1 84f12f030221207fa41de2f39bf8c1e4aef42160
PD2B2 d0f6dc29be273df6fec44a5d7c8eaa65448bf3e3
PD2B3 f86f8c8758b3e8941e5bbfa26d40892433cf0110
tree  9f883335ec13a9385113b2c310c6009a8a0e72aa
```

PD2B removed caller-path authority from semantic A67 inputs and retains the
production operation root/raw A67 inputs only inside an active process-local
binding under the same account mutex. `ABANDONED_OWNER` blocks before P1/A67
preparation.

Final certification: `4754 passed, 17 skipped`; Ruff/diff clean.

## PD2C — supervised Architecture-67 execution boundary — COMPLETE

Completion record:

```text
docs/validation/pd2c-supervised-paper-execution-boundary-completion.md
```

Accepted source:

```text
commit 8d590d06d346140002a3a20eefa9b5a7d087326d
tree   ed322f18b1f98ff88f144ac11bfbcc3fd353d9a3
```

The dedicated supervised-execution gate exists and is normally closed:

```text
PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED = False
```

The publisher/recovery gates are also normally closed:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED   = False
```

Final certification: `4775 passed, 17 skipped`; Ruff/diff clean.

## PD2D — first real supervised Paper-v2 operation — COMPLETE

Completion record:

```text
docs/validation/pd2d2-first-real-paper-operation-completion.md
```

PD2D1 completed the read-only first-mutation qualification and froze the exact
first-cycle plan, selected C3 snapshot, GENESIS predecessor, strategy-history
seed, caller idempotency key, open reference, policies, and timestamps. The
real-host qualification classified the exact operation as ready without
mutating Paper-v2.

PD2D2 then performed exactly one explicitly authorized supervised execution.
The durable identities are:

```text
paper_account_id:       9415cd7b-bf36-5fba-bd58-a0f99119dc21
GENESIS checkpoint:     1832a2b5-8b63-501a-8f7d-f1722c32307b
operation_id:           307f769a-f09a-539d-b12d-3fb51b973809
application_id:         78a1bae8-51ac-5bf0-b159-500768c758fc
cycle_result_id:        854f133e-d9cd-5a9d-be63-0eb4137787db
successor checkpoint:   ed4640e5-0630-525d-b916-d50e31e3ba2a
terminal checkpoint:    ed4640e5-0630-525d-b916-d50e31e3ba2a
receipt_status:         COMPLETED
receipt_outcome:        NO_ACTION
```

After execution the supervised gate was closed. Architecture 108 then performed
a separate read-only production reconciliation under the Trading principal.
After R1 fixed the selected-C3 reader lifetime bug, the reconciliation returned:

```text
result:                    RECONCILED
all_effect_gates_false:    true
lineage_edge_count:        1
account_cash:              25000
position_count:            0
inspection_classification: ALREADY_APPLIED
inspection_diagnostic:     ALREADY_APPLIED
exit:                      0
```

The `ALREADY_APPLIED` result proves the durable transition/receipt lineage is
recognized and the completed operation is not admitted as a new execution.

Final accepted source:

```text
commit f05921244057052158a57b360e9bf556209b9654
tree   35a5a7e1d59bbe90ca303b6037d29dc7fc085f4c
```

Final broad certification:

```text
5146 passed, 17 skipped in 1505.92s
Ruff check: PASS
Ruff format --check: PASS (457 files)
git diff --check: PASS
worktree/index: clean
```

The first invalid broad attempt hit the already-known host-specific pytest temp
permission failure at `C:\Users\John\AppData\Local\Temp\pytest-of-John` during
fixture setup. The successful controlled run used a fresh explicit external
`--basetemp`. This was an environment/setup failure, not a source regression.

Canonical PD2 state:

```text
PD2A = COMPLETE
PD2B = COMPLETE
PD2C = COMPLETE
PD2D1 = COMPLETE
PD2D2 = COMPLETE
PD2 = COMPLETE
```

## Current milestone — PD3 supervised crash/recovery validation

PD3 must validate the personal-desktop recovery authority around the existing
Architecture-67 restart-safe coordinator; it must not create a second recovery
engine.

The existing generic semantics already distinguish the important states:

```text
finalized transition + missing receipt + exact verification
-> reconstruct the same canonical completed receipt
-> runtime invocation count = 0

verified completed transition + completed receipt
-> ALREADY_APPLIED
-> writes = 0
-> runtime invocation count = 0

staging / malformed / altered / ambiguous / mismatched evidence
-> BLOCKED
-> no cleanup, repair, replacement, or blind retry
```

PD3's personal-desktop layer must preserve the dedicated non-admin Trading
principal, genuine production authority, account mutex, exact Paper-v2 root,
read/reconciliation-before-effect ordering, and a separately reviewed recovery
gate that remains false by default. Recovery effects are not yet authorized.

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
PD3   supervised crash/recovery validation                  CURRENT
PD4   unattended simulated paper under Trading
PD5   broker-paper integration
PD6   broker-paper soak / operational hardening
PD7   personal-desktop live-readiness
PD8   tiny restricted live -> gradual maturity
```

## Still not authorized

```text
provider call #7
Paper-v2 recovery effects
broker order submission
live trading
unattended scheduling
changing any closed production/recovery/supervised effect gate without a reviewed checkpoint
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
- Worktree/branch/HEAD mismatch is a STOP; do not self-correct.
- Controlled Windows pytest uses a fresh external
  `F:\AI\temp\pytest\<purpose>-<unique>` via explicit `--basetemp` and normally
  `-p no:cacheprovider`; do not globally change `TEMP`, `TMP`, or persistently
  set `PYTHONPATH` for normal pytest collection.
- Preserve unrelated generated/untracked reports and historical evidence.
- No merge/rebase/force-push/amend/PR metadata/review-thread changes without
  explicit approval.

## Documentation workflow

At accepted checkpoints review/update:

```text
README.md
docs/PROJECT_STATUS.md
docs/AI_TRADING_BOT_HANDOFF.md
```

Completion records belong under `docs/validation/`. Reusable workflow changes
belong in `docs/AI_DEVELOPMENT_WORKFLOW.md`.
