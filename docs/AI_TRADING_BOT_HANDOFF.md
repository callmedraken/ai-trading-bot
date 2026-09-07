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

**deterministic research → supervised simulated paper → unattend simulated
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
physical machine control. The bot still protects against practical
ordinary-process/configuration/credential/state/duplicate-effect/risk-bypass/
recovery failures.

## 2. Primary development line

```text
integration develop baseline:
bd88ee966bff455f9fc897d6cfdfafdd807f27e2

Architecture-94 P2 product base:
a810122a96b6fc90da25d71eede8da64b7272c98

branch:
feature/personal-desktop-paper-runtime

worktree:
F:\AI\worktrees\ai-trading-bot-personal-desktop
```

Before every bounded task:

```text
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git show -s --format=%T HEAD
git status --short
```

Any mismatch is a STOP. Do not self-correct with
checkout/switch/reset/rebase/clean.

## 3. ChatGPT / Codex workflow

ChatGPT/Sol owns architecture, native Windows/security/authority review, exact
GitHub diff review, debugging strategy, test/certification gates,
merge/deployment/production decisions, and next-step planning.

Current Codex routing:

```text
tiny/simple                                   -> ChatGPT direct
known contract + known files/test surface    -> Luna Extra High
discovery-aware/cross-module bounded work    -> Astra
native Windows/security/authority/recovery   -> Sol High
```

Model choice does not transfer architecture or acceptance authority. If
implementation discovers that the contract itself must change, stop and return
to ChatGPT/Sol. Do not use subagents unless explicitly requested.

Codex uses focused tests during implementation. Broad/full certification is
normally user-run locally only after ChatGPT reviews the exact source. Exact-file
stage only; never `git add .` or `git add -A`.

No amend/rebase/merge/force-push/PR-metadata/review-thread changes without
explicit approval.

Shared-interpreter worktree provenance must be explicit:

```text
interpreter:
F:\AI\ai-trading-bot\.venv\Scripts\python.exe

PYTHONPATH:
F:\AI\worktrees\ai-trading-bot-personal-desktop\src
```

Controlled pytest uses a fresh external
`E:\AI\temp\pytest\<unique>` plus `-p no:cacheprovider`.

## 4. Standing authorization model

The user has authorized automatically continuing to the next best scoped
checkpoint when the preceding reviewed checkpoint passes.

This does **not** automatically authorize:

```text
provider call #7
broker submission
live trading
unattended scheduling
first real Paper-v2 runtime mutation
v1 cleanup/repair/migration
account/group/password changes
LSA policy/right changes
KSP/signing/private-export effects
unrelated project effects
merge/rebase/amend/force-push/PR metadata changes
```

## 5. Frozen C3 production state

Accepted C3 release source:

```text
82ba29ae2c2cc6bb3544077db0ee21868e6d5693
```

All six authorized real-provider effects are consumed.

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

## 8. PD1 — personal-desktop Paper-v2 authority — COMPLETE

Completion record:

```text
docs/validation/pd1-personal-desktop-paper-v2-completion.md
```

Final accepted production-read source:

```text
commit a353d58230b5b37231d00e7799fa828ddf31bf30
tree   db750395e9a4a837269c1b93befea453ed604380
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

Published account:

```text
paper_account_id:     9415cd7b-bf36-5fba-bd58-a0f99119dc21
GENESIS checkpoint:   1832a2b5-8b63-501a-8f7d-f1722c32307b
starting cash:        Decimal("25000")
GENESIS as_of:        2026-08-29T09:46:43.769105+00:00
machine_authority_id: 223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1
Trading SID:          S-1-5-21-1397534616-3988210162-180023805-1009
```

Frozen artifacts:

```text
GENESIS  SHA-256 d1a7ff14425c8a797a952860a1102489a4c81cac2a24a45bc3127eb8eb2e9548  length 533
anchor   SHA-256 16c4dba01835c5bc2def91f0103ad79c3da0b5d18af72091b4fdd37fe4353c85  length 465
manifest SHA-256 8fe1d705d59a79207ab6236af71becee0051042dc7b3ecaf23bb7f5531cb0029  length 532
freeze Git blob b125cbb1c80a827f74018cf2955b9a27ba69fa90
```

Occupancy:

```text
F:\AITradingBot\Paper-v2                     PRESENT / VERIFIED
F:\AITradingBot\.Paper-v2.provisioning      ABSENT
F:\AITradingBot\Paper                       ABSENT
F:\AITradingBot\.Paper.provisioning-v1      PRESENT / RETAINED / UNTOUCHED
```

Both source gates remain False:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED   = False
```

## 9. PD2A — paper-account runtime mutex + supervised admission — COMPLETE

Completion record:

```text
docs/validation/pd2a-paper-account-runtime-mutex-completion.md
```

Accepted source:

```text
initial PD2A:
7e9ca73cef578ad28b97036755f7b4723bb832fc
feat: add paper account runtime mutex

PD2A-R1:
38212c07e0c06c7cf25152c5a362434ded7c3adf
tree 9dc5087b87cfd2c16ef76d97c04fd20d41ba7187
fix: fail closed after paper mutex release failure
```

Canonical state:

```text
PD2A_ARCHITECTURE_ACCEPTED = YES
PD2A_SOURCE_ACCEPTED       = YES
PD2A_SOURCE_CERTIFIED      = YES
PD2A                       = COMPLETE
```

Mutex contract:

```text
label  = personal-desktop-paper-account-mutex/v1
prefix = Global\AITradingBot-PaperAccount-v1-
identity = length-framed exact label + canonical lowercase paper_account_id
wait = fixed 30,000 ms
```

Protected DACL:

```text
Administrators: MUTEX_ALL_ACCESS
SYSTEM:         MUTEX_ALL_ACCESS
Trading SID:    MUTEX_MODIFY_STATE | READ_CONTROL | SYNCHRONIZE
```

Key semantics:

- production admission requires a genuine registered
  `ValidatedPersonalDesktopPaperAccount`;
- caller cannot select production name, UUID, timeout, path, or native handle;
- kernel owner/protected DACL/exact ACEs are verified before waiting;
- `WAIT_OBJECT_0` -> `OWNED`;
- timeout/wait failure/unknown result -> fail closed;
- `WAIT_ABANDONED` -> explicit `ABANDONED_OWNER`;
- process-wide same-account non-reentrancy blocks Win32 recursive ownership;
- `ReleaseMutex` failure poisons that account for the process lifetime, closes
  the handle, raises a typed error, and blocks later same-account admission
  before any native operation.

Certification:

```text
focused PD2A after R1: 34 passed
full suite:            4720 passed, 17 skipped
Ruff check:            PASS
Ruff format --check:   PASS (424 files)
git diff --check:      PASS
worktree/index:        clean
```

No production filesystem access/mutation, real production mutex acquisition,
provider call, broker action, scheduling effect, or live effect was authorized
or performed.

## 10. Current checkpoint — PD2B supervised composition design

PD2B is next. Begin with architecture/source composition only. The first real
`Paper-v2\runtime` mutation remains a later explicit production-effect gate.

Required ordering:

```text
genuine C1/Trading paper-account authority
-> pre-lock paper-account read
   (immutable account identity only)
-> acquire PD2A account mutex
-> post-lock genuine paper-account reread/revalidation
-> authoritative fresh terminal checkpoint
+ selected verified C3 snapshot
+ deterministic strategy history
-> strategy plan
-> proposal/planner
-> deterministic risk
-> simulated execution
-> successor + full-lineage verification
-> Architecture-67 transition commitment
-> receipt commitment or zero-runtime recovery/reconciliation
-> release mutex only after terminal durable outcome
```

Freeze these rules before implementation:

1. The pre-lock read may establish immutable `paper_account_id` only. It cannot
   supply mutable execution state.
2. The post-lock reread is the authoritative account state for the cycle.
3. The same genuine C1/Trading authority chain anchors both reads.
4. Production operation root remains source-owned as
   `F:\AITradingBot\Paper-v2\runtime`; callers cannot choose it.
5. The account mutex spans post-lock state validation through durable
   Architecture-67 receipt commitment or exact reconciliation.
6. `ABANDONED_OWNER` requires durable state/receipt reconciliation before any
   new transition.
7. PD2B source verification uses fake/disposable boundaries only. It does not
   mutate the published production account.

PD2B remains Sol-High territory because it composes native Windows authority,
ordering, abandoned-owner/recovery semantics, and the future mutation boundary.

## 11. Architecture-67 ordering context

Preserve existing Architecture-67 facts:

- finalized transition directory is the authoritative account-state commit;
- prospective successor edge/full lineage verify before transition publication;
- staged and finalized transition bytes are reread/reverified;
- receipt commitment occurs only after committed transition rereads/verifies;
- crash after transition finalization but before receipt may use existing
  zero-runtime receipt recovery when exact reconciliation proves the state;
- receipt staging, invalid transition/receipt evidence, or dependency mismatch
  blocks rather than being automatically repaired/retried;
- the account mutex must span the whole critical section through receipt or
  reconciliation.

## 12. Roadmap

```text
PD0  personal-desktop profile adoption                     COMPLETE
PD1  personal-desktop paper-account authority v2           COMPLETE
PD2  reliable supervised manual paper cycle                CURRENT
  PD2A account mutex + supervised admission                COMPLETE
  PD2B supervised composition                              DESIGN NEXT / SOURCE-ONLY
  first real Paper-v2 runtime mutation                     NOT AUTHORIZED
PD3  supervised crash/recovery validation
PD4  unattended simulated paper under Trading
PD5  broker-paper integration
PD6  broker-paper soak / operational hardening
PD7  personal-desktop live-readiness
PD8  tiny restricted live -> gradual maturity
```

## 13. Still NOT authorized

```text
provider call #7
broker order submission
live trading
unattended scheduling
first real Paper-v2 runtime mutation
old v1 publisher rerun
v1 staging delete/repair/rename/migration/reuse
Paper-v2 manual mutation outside reviewed PD2 effect checkpoints
account/group/password changes
LSA rights/policy changes
KSP/signing/private-export effects
merge/rebase/force-push/amend/PR metadata changes without explicit approval
```

## 14. Resume procedure

1. Read `AGENTS.md`, `docs/PROJECT_STATUS.md`, this handoff,
   `docs/AI_DEVELOPMENT_WORKFLOW.md`, Architecture 103, the PD1 completion
   record, and the PD2A completion record.
2. Prove exact worktree/branch/HEAD/tree/clean state.
3. For PD2B, review the PD2A mutex/admission source, genuine Paper-v2 read
   authority, Architecture 67, Architecture 94 P1/P2 composition, and directly
   associated tests.
4. ChatGPT/Sol freezes the PD2B authority/order contract before implementation.
5. Use Codex Sol High for PD2B because it is authority/order/recovery-sensitive.
6. Keep PD2B source-only until a later explicit effect checkpoint authorizes any
   real production Paper-v2 mutation.
7. Codex runs focused tests; user runs the broad suite only at the next final
   certification gate.
8. Include the next milestone in every verification/acceptance report.

## 15. Definition of project success

The project is not complete merely when it can place trades. It succeeds when
the platform can research deterministically, acquire trusted data safely, apply
deterministic risk, interact safely with a brokerage, reconcile external
outcomes after failures/restarts, run unattended, fail closed when
authority/state is uncertain, expose durable evidence, operate under strict
real-money controls, recover predictably, remain understandable/stoppable by
its operator, and expose the reviewed system through a polished GUI without
giving AI or presentation code alternate authority paths.
