# AI Trading Bot — Project Development Roadmap & Handoff

**Repository:** `callmedraken/ai-trading-bot`  
**Integration branch:** `develop`  
**Primary product branch:** `feature/personal-desktop-paper-runtime`  
**Primary worktree:** `F:\AI\worktrees\ai-trading-bot-personal-desktop`  
**Production/live trading:** NO-GO

> This Git-tracked handoff is the canonical cross-chat resume document. Uploaded
> copies are mirrors. Prove worktree, branch, HEAD, tree, and clean state before
> acting.

## 1. Product goal and threat model

Build a conservative automated trading platform for a **closed, single-owner
personal Windows desktop**:

**deterministic research → supervised simulated paper → unattended simulated
paper → broker-paper → long paper soak → personal-desktop live-readiness → tiny
restricted live → mature operation → polished GUI.**

Stable constraints:

```text
US stocks / ETFs
long-only
no margin / leverage / options / shorts / crypto
deterministic risk approval
paper-by-default
complete auditability
```

Architecture 102 trusts the owner/Administrator, Windows kernel/boot/SYSTEM, and
physical machine control. The bot still protects against practical ordinary-
process/configuration/credential/state/duplicate-effect/risk-bypass/recovery
failures.

## 2. Primary development line and local provenance

```text
integration develop baseline:
bd88ee966bff455f9fc897d6cfdfafdd807f27e2

Architecture-94 P2 product base:
a810122a96b6fc90da25d71eede8da64b7272c98

branch:
feature/personal-desktop-paper-runtime

worktree:
F:\AI\worktrees\ai-trading-bot-personal-desktop

interpreter:
F:\AI\ai-trading-bot\.venv\Scripts\python.exe

PYTHONPATH:
F:\AI\worktrees\ai-trading-bot-personal-desktop\src
```

Before every bounded task:

```text
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git show -s --format=%T HEAD
git status --short
```

Any mismatch is a STOP. Do not self-correct with checkout/switch/reset/rebase/
clean. Controlled pytest uses a fresh external
`F:\AI\temp\pytest\<unique>` plus `-p no:cacheprovider`.

## 3. ChatGPT / Codex workflow

ChatGPT/Sol owns architecture, native Windows/security/authority review, exact
GitHub diff review, debugging strategy, test/certification gates,
merge/deployment/production decisions, and next-step planning.

Current routing:

```text
tiny/simple                                  -> ChatGPT direct
known contract + known files/test surface    -> Luna Extra High
discovery-aware/cross-module bounded work    -> Astra
native Windows/security/authority/recovery   -> Sol High
```

After a reviewed checkpoint passes, automatically continue to the next safe
scoped checkpoint. Model choice does not transfer architecture or acceptance
authority. If implementation discovers that the contract itself must change,
stop and return to ChatGPT/Sol. Do not use subagents unless explicitly
requested.

Codex runs focused tests during implementation. Broad/full certification is
normally user-run locally only after ChatGPT reviews the exact source. Exact-
file stage only; never `git add .` or `git add -A`.

No amend/rebase/merge/force-push/PR-metadata/review-thread changes without
explicit approval.

## 4. Standing authorization model

The user has authorized automatically continuing to the next best safe scoped
checkpoint when the preceding reviewed checkpoint passes.

This does **not** automatically authorize:

```text
provider call #7
broker submission
live trading
unattended scheduling
changing the PD2C supervised-execution gate to True
first real Paper-v2 runtime mutation
v1 cleanup/repair/migration
account/group/password changes
LSA policy/right changes
KSP/signing/private-export effects
unrelated project effects
merge/rebase/amend/force-push/PR metadata changes
```

Read-only qualification work may proceed through its reviewed source/test gates.
Any step that would actually enable or perform the first durable Paper-v2
mutation stops for fresh explicit user authorization.

## 5. Frozen C3 production state

Accepted C3 release source:

```text
82ba29ae2c2cc6bb3544077db0ee21868e6d5693
```

All six authorized real-provider effects are consumed:

```text
call #5: FAILED / CONFIRMED
call #6: SUCCEEDED / CONFIRMED / SUCCESS_SELECTED
call #7: NOT AUTHORIZED
```

Selected call #6:

```text
selection_id: 36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280
snapshot_id: eba46838-44ae-5bec-97bf-98c6639ae6a7
SHA-256: 31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
length: 1291
captured_at: 2026-08-29T09:46:43.769105+00:00
```

Host/deployment:

```text
host: DESKTOP-I4DOKM7
Trading account: DESKTOP-I4DOKM7\Trading
Trading SID: S-1-5-21-1397534616-3988210162-180023805-1009
creator/John SID ending: -1005
machine_authority_id: 223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1
authority_epoch_id: e6f3de5d-1412-40ad-a022-8b33e72a5f6d
runtime: F:\AITradingBot\runtime\python.exe
authority DB: F:\AITradingBot\Authority\authority.sqlite3
credential policy: windows-credential-manager-alpaca-market-data/v2
```

## 6. Architecture 94 accepted product work

```text
P1 pure strategy history / deterministic strategy plan
1028e60b99c27cef0994f40d6ce381392abfb0f8

P2 read-only selected-C3 snapshot authority
a810122a96b6fc90da25d71eede8da64b7272c98
```

Preserve:

```text
selected verified C3 snapshot
+ explicit deterministic strategy history
+ authoritative paper-account tip
-> deterministic strategy plan
-> planner/proposal
-> deterministic portfolio risk
-> simulated paper execution
-> successor checkpoint + full-lineage verification
-> Architecture-67 durable transition + receipt
```

## 7. Architecture 103 / Paper-v2 deployment

Fixed production paths:

```text
final authority root:       F:\AITradingBot\Paper-v2
provisioning staging root:  F:\AITradingBot\.Paper-v2.provisioning
A67 operation root:         F:\AITradingBot\Paper-v2\runtime
receipt parent:             F:\AITradingBot\Paper-v2\runtime\paper-operations
```

Retained failed v1 state:

```text
F:\AITradingBot\Paper                     ABSENT
F:\AITradingBot\.Paper.provisioning-v1   PRESENT / RETAINED / UNTOUCHED
```

Never rerun the v1 publisher or delete/repair/rename/migrate/reuse the retained
v1 staging tree as incidental cleanup.

Published Paper-v2 account:

```text
paper_account_id:   9415cd7b-bf36-5fba-bd58-a0f99119dc21
GENESIS checkpoint: 1832a2b5-8b63-501a-8f7d-f1722c32307b
starting cash:      Decimal("25000")
GENESIS as_of:      2026-08-29T09:46:43.769105+00:00
```

Frozen artifacts:

```text
GENESIS  SHA-256 d1a7ff14425c8a797a952860a1102489a4c81cac2a24a45bc3127eb8eb2e9548  length 533
anchor   SHA-256 16c4dba01835c5bc2def91f0103ad79c3da0b5d18af72091b4fdd37fe4353c85  length 465
manifest SHA-256 8fe1d705d59a79207ab6236af71becee0051042dc7b3ecaf23bb7f5531cb0029  length 532
freeze Git blob b125cbb1c80a827f74018cf2955b9a27ba69fa90
```

## 8. Completed PD milestones

### PD1 — personal-desktop Paper-v2 authority — COMPLETE

Completion record:

```text
docs/validation/pd1-personal-desktop-paper-v2-completion.md
```

Canonical state:

```text
PD1_ARCHITECTURE_ACCEPTED    = YES
PD1_SOURCE_ACCEPTED          = YES
PD1_SOURCE_CERTIFIED         = YES
PD1_PRODUCTION_READY         = YES
PD1_V2_PUBLISHED             = YES
PD1_TRADING_RUNTIME_VERIFIED = YES
PD1                          = COMPLETE
```

### PD2A — paper-account runtime mutex + supervised admission — COMPLETE

Completion record:

```text
docs/validation/pd2a-paper-account-runtime-mutex-completion.md
```

Accepted source:

```text
38212c07e0c06c7cf25152c5a362434ded7c3adf
tree 9dc5087b87cfd2c16ef76d97c04fd20d41ba7187
```

Canonical state:

```text
PD2A_ARCHITECTURE_ACCEPTED = YES
PD2A_SOURCE_ACCEPTED       = YES
PD2A_SOURCE_CERTIFIED      = YES
PD2A                       = COMPLETE
```

Key semantics: fixed 30-second deterministic account mutex, exact kernel
security validation, explicit `ABANDONED_OWNER`, same-account non-reentrancy,
and process-lifetime poison after uncertain `ReleaseMutex` failure.

Final certification: `4720 passed, 17 skipped`; Ruff/diff clean.

### PD2B — supervised composition — COMPLETE

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

Canonical state:

```text
PD2B_SOURCE_ACCEPTED  = YES
PD2B_SOURCE_CERTIFIED = YES
PD2B                  = COMPLETE
```

Accepted ordering:

```text
genuine C1
-> pre-lock read for immutable paper_account_id only
-> PD2A mutex
-> post-lock genuine Paper-v2 reread
-> authoritative post-lock prior/lineage
+ genuine P2 selected snapshot
+ pure P1 planning inputs
-> P1 build + exact replay verification
-> PaperOperationIntent
-> path-independent VerifiedPaperOperationExecutionInputs
```

PD2B2 removed caller-path authority from A67 semantic inputs. PD2B3 keeps the
production root and raw A67 inputs inside a private active binding that expires
before mutex release. `ABANDONED_OWNER` blocks before preparation.

Final certification: `4754 passed, 17 skipped`; Ruff/diff clean.

### PD2C — supervised A67 execution boundary — COMPLETE

Architecture:

```text
docs/architecture/104-personal-desktop-supervised-paper-execution-boundary.md
```

Completion record:

```text
docs/validation/pd2c-supervised-paper-execution-boundary-completion.md
```

Accepted source:

```text
commit 8d590d06d346140002a3a20eefa9b5a7d087326d
tree   ed322f18b1f98ff88f144ac11bfbcc3fd353d9a3
```

Canonical state:

```text
PD2C_ARCHITECTURE_ACCEPTED = YES
PD2C_SOURCE_ACCEPTED       = YES
PD2C_SOURCE_CERTIFIED      = YES
PD2C                       = COMPLETE
```

Dedicated execution gate:

```text
PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED = False
```

Existing publisher/recovery gates remain false:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED   = False
```

With the execution gate false, the public PD2C API validates genuine C1/P2 then
blocks before entering PD2B3, acquiring the account mutex, rereading Paper-v2,
retrieving the private binding, or invoking A67. The future enabled branch uses
the exact source-owned runtime root, executes A67 once, reconciles operation and
application identities, and returns only non-authorizing audit fields.

Final certification:

```text
4775 passed, 17 skipped
Ruff check: PASS
Ruff format --check: PASS (432 files)
git diff --check: PASS
worktree/index: clean
```

No production/native/provider/broker effect or Paper-v2 mutation occurred.

## 9. Current checkpoint — PD2D1 read-only first-mutation qualification

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

The first-cycle non-market-data profile is frozen in
`docs/validation/pd2d1-first-cycle-input-freeze.md`; its exact offline
`strategy-history-seed/v1` and SPY `2026-08-31` open-reference provenance are
frozen in `docs/validation/pd2d1-first-cycle-market-data-evidence.md`. No PD2D1
real-host qualification has occurred. The next checkpoint is review and freeze
of the read-only real-host operator harness, and PD2D2 remains **NOT
AUTHORIZED**.

PD2D1 is a non-mutating readiness checkpoint. It prepares the exact would-be
operation under genuine production authority and the same account-mutex lifetime,
then calls the existing read-only `inspect_paper_operation_root` rather than the
A67 executor.

Required ordering:

```text
genuine C1/P2
-> PD2B3 preparation
-> PD2A mutex + post-lock Paper-v2 reread
-> exact P1 replay verification
-> private active A67 binding
-> exact fixed F:\AITradingBot\Paper-v2\runtime
-> inspect_paper_operation_root only
-> reconcile inspection operation/application/terminal identities
-> READY only for exact PENDING/PENDING
-> private binding expires
-> mutex release
```

Qualification must preserve these rules:

1. The PD2C execution gate remains false and qualification must refuse to act if
   it is already true.
2. Qualification never calls `execute_paper_operation_once` and never imports a
   mutation coordinator as an injected production seam.
3. Production-facing callers cannot supply a root, raw A67 inputs, preparation,
   inspector override, IDs, prior/lineage, mutex values, or a readiness override.
4. The inspector result must exactly reconcile operation ID, application ID,
   and terminal checkpoint ID to the active prepared inputs.
5. Only `PaperOperationClassification.PENDING` with diagnostic `PENDING` is
   READY. Every other valid classification is NOT_READY; wrong types/identity
   mismatches fail closed.
6. The result exposes no filesystem path or raw execution input and grants no
   permission to execute later.
7. `ABANDONED_OWNER` remains blocked by PD2B3 before inspection.
8. Focused source tests use fake/disposable seams. A later real-host
   qualification may acquire the real mutex and perform read-only Paper-v2
   inspection under `Trading`, but still performs no durable mutation.
9. Provider call #7, brokerage, live trading, scheduling, credentials, and
   Windows security/account mutation remain out of scope.

PD2D1 remains Sol-High territory because it qualifies the exact production
state immediately before the future mutation boundary.

## 10. Architecture-67 ordering facts to preserve

- finalized transition directory is the authoritative account-state commit;
- prospective successor edge/full lineage verify before transition publication;
- staged and finalized transition bytes are reread/reverified;
- receipt commitment occurs only after committed transition rereads/verifies;
- crash after transition finalization but before receipt may use existing
  zero-runtime receipt recovery when exact reconciliation proves the state;
- invalid/staging/ambiguous/mismatched state blocks rather than being blindly
  retried or repaired;
- the account mutex must span the entire future production critical section.

## 11. Roadmap

```text
PD0   personal-desktop profile adoption                     COMPLETE
PD1   personal-desktop paper-account authority v2           COMPLETE
PD2   reliable supervised manual paper cycle                CURRENT
  PD2A account mutex + supervised admission                 COMPLETE
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

## 12. Still NOT authorized

```text
provider call #7
broker order submission
live trading
unattended scheduling
changing PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED to True
first real Paper-v2 runtime mutation
old v1 publisher rerun
v1 staging delete/repair/rename/migration/reuse
Paper-v2 manual mutation outside reviewed PD2 effect checkpoints
account/group/password changes
LSA rights/policy changes
KSP/signing/private-export effects
merge/rebase/force-push/amend/PR metadata changes without explicit approval
```

## 13. Resume procedure

1. Read `AGENTS.md`, `docs/PROJECT_STATUS.md`, this handoff,
   `docs/AI_DEVELOPMENT_WORKFLOW.md`, Architectures 103–105, and the PD1/PD2A/
   PD2B/PD2C completion records.
2. Prove exact worktree/branch/HEAD/tree/clean state.
3. For PD2D1, review PD2B3 private-binding lifetime, PD2C gate semantics,
   `inspect_paper_operation_root`, account-read authority, and PD2A cleanup.
4. Use Codex Sol High for PD2D1 source implementation.
5. Keep implementation source-only/fake-disposable; user runs the broad suite
   only after exact GitHub review.
6. After source certification, perform a separately reviewed read-only Trading-
   host qualification. That run may read Paper-v2 and acquire/release its mutex
   but must not execute A67 or mutate Paper-v2.
7. Stop before any source gate enablement or first real mutation and obtain
   fresh explicit user authorization.
8. Include the next milestone in every verification/acceptance report.

## 14. Definition of project success

The project is not complete merely when it can place trades. It succeeds when
the platform can research deterministically, acquire trusted data safely, apply
deterministic risk, interact safely with a brokerage, reconcile external
outcomes after failures/restarts, run unattended, fail closed when authority or
state is uncertain, expose durable evidence, operate under strict real-money
controls, recover predictably, remain understandable/stoppable by its operator,
and expose the reviewed system through a polished GUI without giving AI or
presentation code alternate authority paths.
