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
```

Architecture checkpoints:

```text
Architecture 102 adoption:          fab1d776abcdcbf09fb26a257ea7fc86f6201b26
Architecture 103 + validation plan: 12e41c4e407a79d63ea896773bf8462038ebba27
Architecture 104:                   supervised A67 execution boundary
Architecture 105:                   first-mutation qualification
```

## Mandatory personal-desktop security baseline

- steady-state trading runs under the dedicated non-admin `Trading` account;
- credentials stay outside source/plain config and use reviewed Windows-backed storage;
- paper is default; future live requires a separate explicit arming boundary;
- every executable order passes deterministic risk authority;
- strategy/optimizer/GUI/AI/scheduler/adapters cannot bypass risk;
- durable state outranks process-local assumptions;
- ambiguous provider/broker effects are reconciled or fail closed rather than blindly retried;
- source-governed runtime/config/state locations use practical least privilege;
- crash/restart, duplicate invocation, stale input, corruption/conflict, and receipt recovery remain roadmap gates.

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

Canonical status:

```text
PD2A_ARCHITECTURE_ACCEPTED = YES
PD2A_SOURCE_ACCEPTED       = YES
PD2A_SOURCE_CERTIFIED      = YES
PD2A                       = COMPLETE
```

PD2A provides the deterministic account-scoped Windows mutex, fixed 30-second
wait, exact kernel owner/DACL validation, explicit `ABANDONED_OWNER`, process-
wide same-account non-reentrancy, and process-lifetime poison after uncertain
`ReleaseMutex` failure.

Final certification:

```text
4720 passed, 17 skipped
Ruff check: PASS
Ruff format --check: PASS (424 files)
git diff --check: PASS
worktree/index: clean
```

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

Canonical status:

```text
PD2B1_SOURCE_ACCEPTED = YES
PD2B1                  = COMPLETE
PD2B2_SOURCE_ACCEPTED = YES
PD2B2                  = COMPLETE
PD2B3_SOURCE_ACCEPTED = YES
PD2B3                  = COMPLETE
PD2B_SOURCE_ACCEPTED  = YES
PD2B_SOURCE_CERTIFIED = YES
PD2B                  = COMPLETE
```

Final certification:

```text
4754 passed, 17 skipped
Ruff check: PASS
Ruff format --check: PASS (430 files)
git diff --check: PASS
worktree/index: clean
```

PD2B removed caller-path authority from semantic A67 inputs and retains the
production operation root/raw A67 inputs only inside an active process-local
binding under the same account mutex. `ABANDONED_OWNER` blocks before P1/A67
preparation.

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

Canonical status:

```text
PD2C_ARCHITECTURE_ACCEPTED = YES
PD2C_SOURCE_ACCEPTED       = YES
PD2C_SOURCE_CERTIFIED      = YES
PD2C                       = COMPLETE
```

PD2C adds the public supervised execution boundary and a dedicated gate:

```text
PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED = False
```

The existing publisher/recovery gates also remain false:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED   = False
```

When the PD2C gate is false, the production execution API fails after genuine
C1/P2 validation but before entering PD2B3, acquiring the account mutex,
rereading Paper-v2, retrieving the private A67 binding, or invoking A67. The
future enabled path requires the exact Architecture-103 runtime root, calls the
existing A67 execute-once boundary exactly once, reconciles operation and
application identities, strips paths/raw inputs from its result, and unwinds the
same account-mutex scope on success or failure.

Final certification:

```text
4775 passed, 17 skipped
Ruff check: PASS
Ruff format --check: PASS (432 files)
git diff --check: PASS
worktree/index: clean
```

No production/native/provider/broker effect or Paper-v2 mutation occurred.

## Current milestone — PD2D1 read-only first-mutation qualification

Architecture:

```text
docs/architecture/105-personal-desktop-first-paper-mutation-qualification.md
```

Validation plan:

```text
docs/validation/pd2d1-first-paper-mutation-qualification-plan.md
```

Accepted and verified source:

```text
commit bd95d522f5bcf398a243ec2b5fdb8cdc18f63afc
tree   90b9fc8abb21a61e78e8beae9cdfc9e11e4ebd5c
```

PD2D1-F1 first-cycle pure-input freeze is complete at commit
`45291c3053a23de02e118f5b853bd67b5cf36ca8` (tree
`e3fdf3af20d3d8cbceb1e9bedbf59603f9913c9e`). PD2D1-F2 freezes the offline
market evidence as:

```text
seed_id: 5dc95e10-ba22-5b91-94b2-0d851aa8e2d7
seed SHA-256: 40dda54c82324f358d640cce89e467295b8f5b73a32fed76c52e7ca90d398e64
seed byte length: 1060
SPY 2026-08-31 caller-asserted open reference: Decimal("767.33")
```

Current checkpoint state:

```text
PD2D1_SOURCE_ACCEPTED                = YES
PD2D1_SOURCE_VERIFIED                = YES
PD2D1_RH0_PLANNING_ACCEPTED          = YES
PD2D1_NON_MARKET_DATA_PROFILE_FROZEN = YES
PD2D1_F1_COMPLETE                    = YES
PD2D1_F2_OFFLINE_EVIDENCE_FROZEN     = YES
PD2D1_REAL_HOST_QUALIFIED            = NO
PD2D2_AUTHORIZED                     = NO
```

The exact first-cycle non-market-data profile is frozen in
`docs/validation/pd2d1-first-cycle-input-freeze.md`; its offline market evidence
is frozen in `docs/validation/pd2d1-first-cycle-market-data-evidence.md`. No
PD2D1 real-host qualification has occurred. The next checkpoint is review and
freeze of the read-only real-host operator harness, and PD2D2 remains
**NOT AUTHORIZED**.

PD2D1 must answer one question without writing anything: **if the exact current
production authority, selected snapshot, post-lock account state, and planning
inputs were presented to A67 now, does the existing read-only inspection classify
the operation as clean `PENDING`?**

Required qualification ordering:

```text
genuine C1/P2
-> enter PD2B3
-> acquire PD2A account mutex
-> post-lock genuine Paper-v2 reread
-> exact P1 replay verification
-> private active A67 binding
-> exact fixed F:\AITradingBot\Paper-v2\runtime root
-> existing inspect_paper_operation_root (read-only)
-> reconcile inspection identities
-> non-authorizing READY / NOT_READY evidence
-> private binding expires
-> mutex release
```

Qualification never calls `execute_paper_operation_once`, never enables the
PD2C execution gate, and never creates/renames/writes/deletes a Paper-v2 object.
A later real-host qualification may perform read-only filesystem/native mutex
operations under `Trading`; that evidence still grants no execution authority.

Only `PENDING` + `PENDING` inspection is `READY`. `ALREADY_APPLIED`,
`CONFLICTING`, `BLOCKED`, staging/recovery conditions, identity mismatches, or
any uncertainty are `NOT_READY`/fail-closed.

## Primary roadmap

```text
PD0   personal-desktop profile adoption                     COMPLETE
PD1   personal-desktop paper-account authority v2           COMPLETE
PD2   reliable supervised manual paper cycle                CURRENT
  PD2A account-scoped Windows mutex + admission             COMPLETE
  PD2B supervised source-only composition                   COMPLETE
  PD2C supervised A67 execution boundary                    COMPLETE
  PD2D1 read-only first-mutation qualification              CURRENT / F1 COMPLETE / F2 EVIDENCE FROZEN
  PD2D2 enable gate + first real Paper-v2 mutation          NOT AUTHORIZED
PD3   supervised crash/recovery validation
PD4   unattended simulated paper under Trading
PD5   broker-paper integration
PD6   broker-paper soak / operational hardening
PD7   personal-desktop live-readiness
PD8   tiny restricted live -> gradual maturity
```

## Still not authorized

```text
provider call #7
broker order submission
live trading
unattended scheduling
changing the PD2C supervised-execution gate to True
first real Paper-v2 runtime mutation
old v1 publisher rerun
v1 staging delete/repair/rename/migration/reuse
Paper-v2 manual mutation outside reviewed PD2 effect checkpoints
account/group/password changes
LSA rights/policy changes
KSP/signing/private-export effects
merge/rebase/force-push/amend/PR metadata changes without explicit approval
```

## Workflow invariants

- ChatGPT/Sol owns architecture/security review, exact GitHub diff review, test gates, merge/deployment/production decisions, and next milestones.
- After a reviewed checkpoint passes, automatically continue to the next safe scoped checkpoint; stop at explicitly protected production/effect boundaries.
- Tiny scoped status/handoff/docs closeouts are ChatGPT-direct by default.
- Codex uses Luna Extra High for frozen/local mechanical work, Astra for bounded discovery-aware/cross-module work, and Sol High for native Windows/security/authority/order/crash/recovery and other safety-sensitive implementation.
- Model choice never transfers architecture or acceptance authority.
- No subagents unless explicitly requested.
- Codex runs focused tests/checks during implementation; broad/full certification is normally user-run locally at the final gate.
- Never `git add .` or `git add -A`; exact-file stage only.
- Worktree/branch/HEAD mismatch is a STOP; do not self-correct.
- Controlled Windows pytest uses a fresh external `F:\AI\temp\pytest\<unique>` and normally `-p no:cacheprovider`.
- Preserve unrelated generated/untracked reports and historical evidence.
- No merge/rebase/force-push/amend/PR metadata/review-thread changes without explicit approval.

## Documentation workflow

At accepted checkpoints review/update:

```text
README.md
docs/PROJECT_STATUS.md
docs/AI_TRADING_BOT_HANDOFF.md
```

Completion records belong under `docs/validation/`. Reusable workflow changes
belong in `docs/AI_DEVELOPMENT_WORKFLOW.md`.
