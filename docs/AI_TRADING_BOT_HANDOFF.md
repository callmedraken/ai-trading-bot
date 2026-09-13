# AI Trading Bot — Project Development Roadmap & Handoff

**Repository:** `callmedraken/ai-trading-bot`  
**Integration branch:** `develop`  
**Primary product branch:** `feature/personal-desktop-paper-runtime`  
**Primary worktree:** `F:\AI\worktrees\ai-trading-bot-personal-desktop`  
**Production/live trading:** NO-GO

> This Git-tracked handoff is the canonical cross-chat resume document. Uploaded
> copies are mirrors. Prove worktree, branch, HEAD, tree, origin, and clean state
> before acting.

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

## 2. Primary development line

```text
integration develop baseline:
bd88ee966bff455f9fc897d6cfdfafdd807f27e2

Architecture-94 P2 product base:
a810122a96b6fc90da25d71eede8da64b7272c98

final PD4 certified source commit:
248cd8de6a3539aab21d5719d96cb7ff1aa0d14c

final PD4 certified source tree:
5e867f1bfc6d945ad67f6c56be252b534645aeb2

branch:
feature/personal-desktop-paper-runtime

worktree:
F:\AI\worktrees\ai-trading-bot-personal-desktop

development interpreter:
F:\AI\ai-trading-bot\.venv\Scripts\python.exe

production interpreter:
F:\AITradingBot\runtime\python.exe
```

The branch may contain later **docs-only** closeout commits. Do not mistake the
documentation HEAD for the exact source tree that received the PD4 broad
certification; the certified source identity is the commit/tree above.

Before every bounded task:

```text
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git show -s --format=%T HEAD
git rev-parse origin/feature/personal-desktop-paper-runtime
git status --short
```

Any unexpected mismatch is a STOP. Do not self-correct with checkout/switch/
reset/rebase/clean.

## 3. Windows pytest and source-checkout rules

Normal pytest collection uses `pyproject.toml`'s `pythonpath = ["src"]`. Do not
persistently export `PYTHONPATH` for ordinary pytest runs.

Controlled pytest on John's Windows development account must use a fresh
external basetemp because the default
`C:\Users\John\AppData\Local\Temp\pytest-of-John` has a known WinError-5 access
condition:

```powershell
$BaseTemp = "F:\AI\temp\pytest\<purpose>-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Force 'F:\AI\temp\pytest' | Out-Null
& $Python -m pytest ... --basetemp="$BaseTemp" -p no:cacheprovider
```

Do not globally alter `TEMP` or `TMP` to work around that condition.

Source-checkout operator CLIs that must run independently of cwd or ambient
package resolution use a reviewed `scripts/` launcher that explicitly selects
the checkout's `src`. Before an actual Trading-principal host invocation, run an
import/help probe with the production interpreter against that launcher.

## 4. ChatGPT / Codex workflow

ChatGPT/Sol owns architecture, native Windows/security/authority review, exact
GitHub diff review, debugging strategy, test/certification gates,
merge/deployment/production decisions, small tightly scoped project changes,
and next-step planning.

Current routing:

```text
tiny/simple                                  -> ChatGPT direct
known contract + known files/test surface    -> Luna Extra High
discovery-aware/cross-module bounded work    -> Astra
native Windows/security/authority/recovery   -> Sol High
```

Tiny status, handoff, workflow, completion-record, and frozen architecture docs
should normally be handled directly by ChatGPT rather than delegated.

After a reviewed checkpoint passes, automatically continue to the next safe
scoped checkpoint. Stop at protected effect boundaries or genuine architecture
ambiguity. Model choice never transfers architecture or acceptance authority.
Do not use subagents unless explicitly requested.

Codex runs focused tests during implementation. Broad/full certification is
normally user-run locally only after ChatGPT reviews the exact source. Exact-
file stage only; never `git add .` or `git add -A`.

No amend/rebase/merge/force-push/PR-metadata/review-thread changes without
explicit approval.

## 5. Standing authorization model

The user has authorized automatically continuing to the next best safe scoped
checkpoint when the preceding reviewed checkpoint passes.

This does **not** automatically authorize:

```text
provider call #7 / unattended C3 provider capture
real Paper-v2 receipt-recovery mutation
unattended invocation-storage provisioning effect
Task Scheduler installation/modification/enabling/running
first real unattended Paper-v2 execution
broker submission
live trading
changing a closed production/recovery/supervised/unattended effect gate
v1 cleanup/repair/migration
account/group/password changes
LSA policy/right changes
KSP/signing/private-export effects
unrelated project effects
merge/rebase/amend/force-push/PR metadata changes
```

Read-only architecture, source, review, and qualification work may continue when
it does not cross an effect boundary.

## 6. Frozen C3 production state

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

## 7. Architecture 94 accepted product work

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

## 8. Paper-v2 deployment

Fixed production paths:

```text
final authority root: F:\AITradingBot\Paper-v2
A67 operation root:   F:\AITradingBot\Paper-v2\runtime
receipt parent:       F:\AITradingBot\Paper-v2\runtime\paper-operations
unattended namespace: F:\AITradingBot\Paper-v2\runtime\unattended-invocations
```

Retained failed v1 state:

```text
F:\AITradingBot\Paper                    ABSENT
F:\AITradingBot\.Paper.provisioning-v1  PRESENT / RETAINED / UNTOUCHED
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

All current Paper-v2 effect gates are closed:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED                       = False
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED                         = False
PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED             = False
PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED                 = False
PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED             = False
PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED  = False
```

## 9. Completed milestones

### PD1 — Paper-v2 authority — COMPLETE

Completion record:

```text
docs/validation/pd1-personal-desktop-paper-v2-completion.md
```

### PD2 — reliable supervised manual paper cycle — COMPLETE

Completion records:

```text
docs/validation/pd2a-paper-account-runtime-mutex-completion.md
docs/validation/pd2b-supervised-paper-composition-completion.md
docs/validation/pd2c-supervised-paper-execution-boundary-completion.md
docs/validation/pd2d2-first-real-paper-operation-completion.md
```

First durable operation:

```text
operation_id:         307f769a-f09a-539d-b12d-3fb51b973809
application_id:       78a1bae8-51ac-5bf0-b159-500768c758fc
cycle_result_id:      854f133e-d9cd-5a9d-be63-0eb4137787db
successor checkpoint: ed4640e5-0630-525d-b916-d50e31e3ba2a
receipt_status:       COMPLETED
receipt_outcome:      NO_ACTION
```

Final PD2 certification:

```text
5146 passed, 17 skipped in 1505.92s
Ruff check PASS
Ruff format --check PASS (457 files)
git diff --check PASS
```

### PD3 — supervised crash/recovery validation — COMPLETE

Architecture:

```text
docs/architecture/109-personal-desktop-paper-receipt-recovery-authority.md
```

Completion record:

```text
docs/validation/pd3-personal-desktop-receipt-recovery-completion.md
```

Final accepted PD3 source:

```text
commit e690ce83d6c53507d9e93dca97bcb79191c62a0b
tree   522f41115d2079ae777f667a19e5179c1d492e1f
```

Architecture 109 reuses Architecture-67's existing completed-receipt recovery.
The recovery-only A67 entry point cannot execute a fresh paper cycle. Healthy
completed state is `ALREADY_APPLIED` with zero writes; exact terminal missing
receipt may reconstruct only the same canonical receipt; ambiguous or staging
state blocks without repair or blind retry.

Final PD3 broad certification:

```text
5285 passed, 17 skipped in 1478.19s
Ruff check PASS
Ruff format --check PASS (467 files)
git diff --check PASS
worktree/index clean
```

Real-host acceptance under the intended non-admin Trading account passed with no
real recovery mutation.

### PD4 — unattended simulated-paper source foundation — COMPLETE

Architecture:

```text
docs/architecture/110-personal-desktop-unattended-paper-operation-authority.md
```

Validation plan:

```text
docs/validation/pd4-unattended-personal-desktop-paper-plan.md
```

Completion record:

```text
docs/validation/pd4-unattended-personal-desktop-paper-completion.md
```

Accepted PD4 source surface:

```text
PD4-A   durable unattended invocation model and verification
PD4-B   durable invocation storage/read/publication/provisioning boundaries
PD4-C   read-only startup qualification under the same PD2A mutex
PD4-D   unattended Paper-v2 execution composition with effects closed
PD4-D-R1 explicit non-private shared composition interfaces
PD4-E   zero-semantic-argument launcher + frozen scheduler contract
PD4-F1  production read-only host-validation harness
PD4-F2  final source certification
PD4-F3  Trading-principal read-only qualification
```

Final certified source:

```text
commit 248cd8de6a3539aab21d5719d96cb7ff1aa0d14c
tree   5e867f1bfc6d945ad67f6c56be252b534645aeb2
```

The final source contains the import-cycle correction in
`src/trading_bot/runtime/__init__.py`: CLI-dependent PD4 unattended
startup/execution facade exports are lazy-loaded so importing the base runtime
package cannot recursively import partially initialized CLI modules.

Focused final import-regression gate:

```text
132 passed in 13.46s
Ruff check PASS
Ruff format --check PASS
git diff --check PASS
git diff --cached --check PASS
worktree/index clean
```

Final PD4 broad certification:

```text
5588 passed, 17 skipped in 1519.25s (0:25:19)
Ruff check PASS
Ruff format --check PASS (486 files)
git diff --check PASS
git diff --cached --check PASS
worktree/index clean
local HEAD == origin feature HEAD
```

Real-host PD4-F3 ran under:

```text
principal: DESKTOP-I4DOKM7\Trading
SID: S-1-5-21-1397534616-3988210162-180023805-1009
integrity: Medium Mandatory Level
BUILTIN\Administrators membership: absent
production interpreter: F:\AITradingBot\runtime\python.exe
```

The frozen unattended launcher returned:

```text
status: EFFECTS_CLOSED
diagnostic: SOURCE_ONLY_ZERO_ARGUMENT_BOUNDARY
qualification_performed: false
invocation_published: false
execution_performed: false
recovery_performed: false
scheduler_modified: false
exit: 0
```

The read-only PD4 harness returned:

```text
result: VALIDATED
all_effect_gates_false: true
qualification_status: BLOCKED
qualification_diagnostic: QUALIFICATION_BLOCKED
unattended_operation_authorized: false
selection_id: 36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280
selected_snapshot_id: null
invocation_published: false
execution_performed: false
recovery_performed: false
provider_call_performed: false
database_mutation_performed: false
scheduler_modified: false
exit: 0
```

`BLOCKED` is the accepted fail-closed host result for this read-only checkpoint:
no unavailable/non-authorized unattended condition may be converted into
execution authority.

Canonical PD4 source-foundation state:

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
PD4_SOURCE_FOUNDATION                      = COMPLETE
PD4_UNATTENDED_DEPLOYMENT_ACCEPTED         = NO
REAL_UNATTENDED_PAPER_EXECUTION_PERFORMED  = NO
UNATTENDED_PROVIDER_CAPTURE_AUTHORIZED     = NO
```

PD4 source completion is **not** operational unattended deployment acceptance.
No scheduled task was installed/modified/enabled/run; no invocation was
published; no real unattended Paper-v2 execution/recovery/provider/broker/live
effect occurred.

## 10. Current milestone — PD4 unattended deployment acceptance design

The next safe checkpoint is source/design only. Freeze the intended unattended
deployment and acceptance sequence while every effect gate remains false.
At minimum cover:

```text
session/timing eligibility policy
scheduler trigger and verification contract
unattended invocation-storage provisioning checkpoint
first real unattended Paper-v2 acceptance ordering
strict post-run reconciliation and evidence requirements
separate unattended C3/provider authority checkpoint
```

Do not install or modify a task, provision storage, invoke provider call #7,
perform a real unattended Paper-v2 cycle, or enable any effect gate merely
because the source/design plan is accepted. Those remain explicit protected
operator checkpoints.

## 11. Roadmap

```text
PD0   personal-desktop profile adoption                     COMPLETE
PD1   personal-desktop paper-account authority v2           COMPLETE
PD2   reliable supervised manual paper cycle                COMPLETE
  PD2A account mutex + supervised admission                 COMPLETE
  PD2B supervised source-only composition                   COMPLETE
  PD2C supervised A67 execution boundary                    COMPLETE
  PD2D1 read-only first-mutation qualification              COMPLETE
  PD2D2 first real Paper-v2 mutation + reconciliation       COMPLETE
PD3   supervised crash/recovery validation                  COMPLETE
PD4   unattended simulated-paper source foundation          COMPLETE
      unattended operational deployment                     PENDING / PROTECTED
PD5   broker-paper integration                              NOT STARTED
PD6   broker-paper soak / operational hardening             NOT STARTED
PD7   personal-desktop live-readiness                       NOT STARTED
PD8   tiny restricted live -> gradual maturity              NOT STARTED
```

The next roadmap milestone after operational PD4 acceptance is PD5 broker-paper
integration. Do not treat source-only PD4 completion as implicit broker or
scheduler authority.

## 12. Still NOT authorized

```text
provider call #7 / unattended C3 provider capture
real Paper-v2 receipt-recovery mutation
unattended invocation-storage provisioning effect
Task Scheduler installation/modification/enabling/running
first real unattended Paper-v2 execution
broker order submission
live trading
changing any closed effect gate without review
old v1 publisher rerun
v1 staging delete/repair/rename/migration/reuse
Paper-v2 manual mutation outside reviewed effect checkpoints
account/group/password changes
LSA rights/policy changes
KSP/signing/private-export effects
merge/rebase/force-push/amend/PR metadata changes without explicit approval
```

## 13. Resume procedure

1. Read `AGENTS.md`, `docs/PROJECT_STATUS.md`, this handoff,
   `docs/AI_DEVELOPMENT_WORKFLOW.md`, Architecture 110, the PD4 validation plan,
   and the PD4 completion record before new implementation.
2. Prove exact worktree/branch/HEAD/tree/origin/clean state before edits or local
   operator work. If docs-only closeout commits are ahead of the certified
   source commit, confirm the intervening diff is documentation-only.
3. Treat PD1, PD2, PD3, and the **PD4 source foundation** as accepted. Do not
   rerun the first PD2D2 execution harness or manufacture a PD3 recovery state
   in real Paper-v2.
4. Preserve the final certified PD4 source identity:
   `248cd8de6a3539aab21d5719d96cb7ff1aa0d14c` / tree
   `5e867f1bfc6d945ad67f6c56be252b534645aeb2`.
5. Preserve the dedicated non-admin Trading principal, genuine C1/P2 authority,
   PD2A account mutex, durable unattended invocation state, Architecture-67
   durability/idempotency, and PD3 recovery rules.
6. Keep all six current effect gates false during the next source/design work.
7. Continue with the PD4 unattended deployment acceptance design: timing/session
   policy, scheduler deployment verification, storage provisioning checkpoint,
   first unattended Paper-v2 acceptance ordering, and separate unattended C3
   capture authority.
8. Stop before any scheduler/storage/provider/Paper-v2/recovery effect unless
   the user explicitly authorizes that protected checkpoint.
9. Do not authorize broker submission or live operation as part of PD4.
10. Use a fresh explicit `--basetemp` under `F:\AI\temp\pytest\` for controlled
    Windows pytest runs; do not persistently export `PYTHONPATH`.
11. Do not rerun the broad suite solely for docs-only closeout commits. A new
    broad certification is needed only after meaningful source change at the
    next final source gate.
12. Include the next milestone/step in every milestone and verification report.

## 14. Definition of project success

The project is not complete merely when it can place trades. It succeeds when
the platform can research deterministically, acquire trusted data safely, apply
deterministic risk, interact safely with a brokerage, reconcile external
outcomes after failures/restarts, run unattended, fail closed when authority or
state is uncertain, expose durable evidence, operate under strict real-money
controls, recover predictably, remain understandable/stoppable by its operator,
and expose the reviewed system through a polished GUI without giving AI or
presentation code alternate authority paths.