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

latest accepted PD3 source:
e690ce83d6c53507d9e93dca97bcb79191c62a0b

latest accepted PD3 tree:
522f41115d2079ae777f667a19e5179c1d492e1f

branch:
feature/personal-desktop-paper-runtime

worktree:
F:\AI\worktrees\ai-trading-bot-personal-desktop

development interpreter:
F:\AI\ai-trading-bot\.venv\Scripts\python.exe

production interpreter:
F:\AITradingBot\runtime\python.exe
```

Before every bounded task:

```text
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git show -s --format=%T HEAD
git rev-parse origin/feature/personal-desktop-paper-runtime
git status --short
```

Any mismatch is a STOP. Do not self-correct with checkout/switch/reset/rebase/
clean.

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
merge/deployment/production decisions, and next-step planning.

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
scoped checkpoint. Model choice does not transfer architecture or acceptance
authority. If implementation discovers that the contract itself must change,
stop and return to ChatGPT/Sol. Do not use subagents unless explicitly
requested.

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
provider call #7
real Paper-v2 receipt-recovery mutation
unattended scheduling or unattended Paper-v2 execution
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
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED           = False
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED             = False
PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED     = False
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

Independent read-only reconciliation returned `RECONCILED` and
`ALREADY_APPLIED`, with cash `25000`, zero positions, and one lineage edge.

Final PD2 source:

```text
f05921244057052158a57b360e9bf556209b9654
tree 35a5a7e1d59bbe90ca303b6037d29dc7fc085f4c
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

Accepted source chain:

```text
PD3-A  cbca467b07c74217c0bb595b9426086a1f1ad8bd
PD3-B  f0cf65cefd432c14b9a519c11b0636cc68b6a6c4
PD3-C  b54046d08739babc7e1aed3c461f487984a12267
PD3-D1 b9f411aa43fdc6c8b10af7fb081449f57afb4d00
PD3-D2 3ebeff8f279b4e2391bf7a4c6404f0a4dce99007
D2-R1  8a3ce8eb110fb7d2be31de130fdfe51955731ae8
PD3-F  78c90da32abb2e7dfd88d933af44e95f110a237a
launcher 034637e7cf76258a90644161f075c959940d6e1e
format   dd36f164636beaf62ac1383217654767ed49dab1
final    f246d099bf1f236ecbe59df746c0c93516da8023
accepted e690ce83d6c53507d9e93dca97bcb79191c62a0b
tree     522f41115d2079ae777f667a19e5179c1d492e1f
```

Architecture 109 reuses Architecture-67's existing completed-receipt recovery.
The recovery-only A67 entry point cannot execute a fresh paper cycle. The
personal-desktop layer adds terminal-missing-receipt qualification, exact
original-operation reconstruction from explicit semantic inputs, the same PD2A
account mutex, a dedicated closed receipt-recovery gate, and a receipt-only
output capability that cannot create transition output.

Accepted production recovery ordering:

```text
genuine C1 + genuine P2
-> pre-lock qualification
-> same PD2A account mutex
-> post-lock qualification
-> exact target agreement
-> original-operation reconstruction
-> four-gate check
-> receipt-only output capability
-> A67 reinspection
-> recovery-only A67 call at most once
-> strict account reread
-> final ALREADY_APPLIED inspection
-> capability close
-> mutex release
```

Exact states:

```text
verified terminal transition + missing receipt
-> same canonical receipt only
-> zero strategy/runtime execution
-> no new transition

verified complete transition + receipt
-> ALREADY_APPLIED
-> zero writes

ambiguous/staging/malformed/conflicting state
-> BLOCKED
-> no repair, cleanup, replacement, or blind retry
```

Final PD3 broad certification:

```text
5285 passed, 17 skipped in 1478.19s
Ruff check PASS
Ruff format --check PASS (467 files)
git diff --check PASS
worktree/index clean
```

Real-host acceptance under the intended non-admin Trading account passed exact
repo provenance, production-interpreter launcher import/help probe, and one
actual read-only validation:

```text
result:                        VALIDATED
all_effect_gates_false:        true
qualification_status:          NO_RECOVERY_REQUIRED
qualification_diagnostic:      VERIFIED_COMPLETE_ACCOUNT
inspection_classification:     ALREADY_APPLIED
inspection_diagnostic:         ALREADY_APPLIED
receipt_status:                COMPLETED
receipt_outcome:               NO_ACTION
account_cash:                  25000
position_count:                0
recovery_invocation_performed: false
receipt_evidence_produced:     false
exit:                          0
```

No real recovery mutation was performed or required.

## 10. Current milestone — PD4 unattended simulated paper under Trading

PD4 is now the active milestone. It must take the reviewed Paper-v2 operation
from manual/supervised invocation to unattended operation under the same
non-admin `Trading` account without weakening any existing authority.

Before implementation, freeze a new architecture/validation contract covering:

```text
source-owned unattended invocation identity
explicit trading-session/schedule eligibility policy
production interpreter + Trading principal provenance
durable original semantic invocation record for PD3 restart recovery
same PD2A account mutex and A67 duplicate/idempotency authority
startup reconciliation before any fresh effect
post-run strict reread and durable evidence
stale/missing/ambiguous input fail-closed behavior
closed-by-default unattended execution gate
operator-visible deterministic audit/exit status
no implicit provider/broker/live authority expansion
```

A scheduler may trigger the reviewed application boundary, but scheduler state
must never be the authority for account state, duplicate suppression, operation
identity, or recovery. Durable Paper-v2/A67 state and the existing account mutex
remain authoritative.

PD4 must explicitly solve how the original semantic facts required by PD3-C are
retained across process restart. Do not rely on in-memory values, filesystem
name inference, or re-deriving caller idempotency from a transition after a
crash.

No unattended execution or scheduler installation is authorized merely because
PD4 is current.

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
PD4   unattended simulated paper under Trading              CURRENT
PD5   broker-paper integration
PD6   broker-paper soak / operational hardening
PD7   personal-desktop live-readiness
PD8   tiny restricted live -> gradual maturity
```

## 12. Still NOT authorized

```text
provider call #7
real Paper-v2 receipt-recovery mutation
unattended scheduling or unattended Paper-v2 execution
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
   `docs/AI_DEVELOPMENT_WORKFLOW.md`, Architecture 109, and the PD3 completion
   record.
2. Prove exact worktree/branch/HEAD/tree/origin/clean state before edits or local
   operator work.
3. Treat PD1, PD2, and PD3 as complete. Do not rerun the first PD2D2 execution
   harness and do not manufacture a PD3 recovery state in real Paper-v2.
4. Continue with PD4 architecture/validation design before unattended source
   implementation.
5. Preserve the dedicated non-admin Trading principal, genuine C1/P2 authority,
   PD2A account mutex, A67 durable state/idempotency, and PD3 recovery rules.
6. Ensure PD4 durably retains the original semantic invocation facts required
   for restart recovery.
7. Keep every current effect gate false during source-only architecture work.
8. Do not authorize a real unattended run, scheduler installation, provider
   call, broker effect, or recovery mutation merely because source tests pass.
9. Use a fresh explicit `--basetemp` under `F:\AI\temp\pytest\` for controlled
   Windows pytest runs; do not persistently export `PYTHONPATH`.
10. Include the next milestone/step in every milestone and verification report.

## 14. Definition of project success

The project is not complete merely when it can place trades. It succeeds when
the platform can research deterministically, acquire trusted data safely, apply
deterministic risk, interact safely with a brokerage, reconcile external
outcomes after failures/restarts, run unattended, fail closed when authority or
state is uncertain, expose durable evidence, operate under strict real-money
controls, recover predictably, remain understandable/stoppable by its operator,
and expose the reviewed system through a polished GUI without giving AI or
presentation code alternate authority paths.
