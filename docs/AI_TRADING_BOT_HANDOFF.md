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

latest accepted PD2D2 source:
f05921244057052158a57b360e9bf556209b9654

latest accepted PD2D2 tree:
35a5a7e1d59bbe90ca303b6037d29dc7fc085f4c

branch:
feature/personal-desktop-paper-runtime

worktree:
F:\AI\worktrees\ai-trading-bot-personal-desktop

interpreter:
F:\AI\ai-trading-bot\.venv\Scripts\python.exe
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
clean.

Normal pytest collection uses `pyproject.toml`'s `pythonpath = ["src"]`. Do not
persistently export `PYTHONPATH` for ordinary pytest runs. Standalone provenance
checks may insert the selected worktree `src` into `sys.path` inside that one
Python process only.

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

Tiny status, handoff, and workflow-documentation closeouts should normally be
handled directly by ChatGPT rather than delegated.

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
Paper-v2 recovery effects
broker submission
live trading
unattended scheduling
changing a closed production/recovery/supervised effect gate
v1 cleanup/repair/migration
account/group/password changes
LSA policy/right changes
KSP/signing/private-export effects
unrelated project effects
merge/rebase/amend/force-push/PR metadata changes
```

Read-only architecture, source, review, and qualification work may continue when
it does not cross an effect boundary. Any real recovery effect, unattended run,
broker effect, or later live effect requires a separately reviewed checkpoint
and fresh explicit authorization where required.

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

Dedicated execution gate:

```text
PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED = False
```

Existing publisher/recovery gates remain false:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED   = False
```

Final certification: `4775 passed, 17 skipped`; Ruff/diff clean.

### PD2D — first real supervised Paper-v2 operation — COMPLETE

Completion record:

```text
docs/validation/pd2d2-first-real-paper-operation-completion.md
```

PD2D1 completed the read-only qualification and froze the exact first-cycle
inputs. PD2D2 then performed exactly one explicitly authorized real Paper-v2
mutation under the dedicated non-admin Trading account.

Durable first-operation identities:

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

After the mutation, the supervised gate was closed again. Architecture 108
performed an independent read-only production reconciliation under Trading.
Architecture-108 R1 fixed one P2 reader-lifetime composition bug without
altering P2 provenance checks or durable Paper-v2 state.

Accepted final source:

```text
commit f05921244057052158a57b360e9bf556209b9654
tree   35a5a7e1d59bbe90ca303b6037d29dc7fc085f4c
```

Accepted reconciliation:

```text
result:                    RECONCILED
all_effect_gates_false:    true
lineage_edge_count:        1
account_cash:              25000
position_count:            0
receipt_status:            COMPLETED
receipt_outcome:           NO_ACTION
inspection_classification: ALREADY_APPLIED
inspection_diagnostic:     ALREADY_APPLIED
exit:                      0
```

Final broad certification:

```text
5146 passed, 17 skipped in 1505.92s
Ruff check: PASS
Ruff format --check: PASS (457 files)
git diff --check: PASS
worktree/index: clean
```

Canonical PD2 state:

```text
PD2A  = COMPLETE
PD2B  = COMPLETE
PD2C  = COMPLETE
PD2D1 = COMPLETE
PD2D2 = COMPLETE
PD2   = COMPLETE
```

## 9. Current checkpoint — PD3 supervised crash/recovery validation

PD3 is now the active milestone. It should validate a personal-desktop recovery
authority around the **existing Architecture-67 restart-safe recovery
semantics**, not introduce a second recovery implementation.

Existing generic behavior to preserve:

```text
verified finalized transition + missing receipt
-> reconstruct the same canonical completed receipt
-> runtime invocation count = 0
-> transition bytes unchanged

verified completed transition + completed receipt
-> ALREADY_APPLIED
-> runtime invocation count = 0
-> writes = 0

receipt staging / transition staging / malformed or altered evidence /
ambiguous layout / lineage mismatch
-> BLOCKED
-> no deletion, cleanup, repair, replacement, finalization, or blind retry
```

PD3 must keep the real-host composition proportional to the closed single-user
desktop threat model:

```text
dedicated non-admin Trading principal
-> genuine C1 authority
-> exact Paper-v2 identity
-> PD2A account mutex
-> post-lock genuine Paper-v2 reread/reconciliation
-> exact crash-state classification
-> recovery gate checked separately
-> only the already-reviewed zero-runtime receipt-recovery path may be admitted
-> reread/reverify durable state
-> mutex release
```

Recovery effects remain disabled and unauthorized until a separately reviewed
source/effect checkpoint explicitly opens them. PD3 must never turn a failed,
ambiguous, or already-complete operation into a new trading-cycle attempt.

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
PD2   reliable supervised manual paper cycle                COMPLETE
  PD2A account mutex + supervised admission                 COMPLETE
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

## 12. Still NOT authorized

```text
provider call #7
Paper-v2 recovery effects
broker order submission
live trading
unattended scheduling
changing any closed production/recovery/supervised effect gate without review
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
   `docs/AI_DEVELOPMENT_WORKFLOW.md`, Architecture 108, the PD2D2 completion
   record, and the existing restart-safe paper-operation validation document.
2. Prove exact worktree/branch/HEAD/tree/clean state before edits or local
   operator work.
3. Treat PD2D2 as complete; do not rerun the first execution harness.
4. For PD3, begin with source-only architecture/validation design around the
   existing zero-runtime missing-receipt recovery behavior.
5. Preserve the PD2A mutex and genuine post-lock Paper-v2 reread as authority;
   do not grant recovery from pre-lock or caller-supplied state.
6. Keep `PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED` false through
   architecture/source review and focused tests.
7. Do not authorize a real recovery effect merely because source tests pass.
8. Use a fresh explicit `--basetemp` under `F:\AI\temp\pytest\` for controlled
   Windows pytest runs; do not persistently export `PYTHONPATH`.
9. Include the next milestone in every verification/acceptance report.

## 14. Definition of project success

The project is not complete merely when it can place trades. It succeeds when
the platform can research deterministically, acquire trusted data safely, apply
deterministic risk, interact safely with a brokerage, reconcile external
outcomes after failures/restarts, run unattended, fail closed when authority or
state is uncertain, expose durable evidence, operate under strict real-money
controls, recover predictably, remain understandable/stoppable by its operator,
and expose the reviewed system through a polished GUI without giving AI or
presentation code alternate authority paths.
