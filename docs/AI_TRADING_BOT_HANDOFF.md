# AI Trading Bot — Project Development Roadmap & Handoff

**Repository:** `callmedraken/ai-trading-bot`
**Integration branch:** `develop`
**Recently integrated source branch:** `feature/operator-observability-o1-forward-integration`
**Recently integrated source worktree:** `F:\AI\worktrees\ai-trading-bot-operator-observability-o1-forward-integration`
**Armed/historical D5 branch:** `feature/personal-desktop-paper-runtime`
**Historical D6/D7 branch:** `feature/pd4-unattended-decision-publication`
**Armed/historical D5 worktree:** `F:\AI\worktrees\ai-trading-bot-personal-desktop`
**Historical D6/D7 worktree:** `F:\AI\worktrees\ai-trading-bot-decision-publication`
**Production/live trading:** NO-GO

> This Git-tracked handoff is the canonical cross-chat resume document. Uploaded
> copies are mirrors. Prove worktree, branch, HEAD, tree, origin, and clean state
> before acting. The armed D5 branch/worktree must remain stable while capture-
> only warm-up continues; new source/design work belongs on the isolated D6/D7
> branch/worktree.

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

## 2. Current repository and deployment provenance

Integration/product baselines:

```text
current develop integration:
c2de20c35a67e7f6c164d25e08dd0d2fc7d52641
tree: f38913b50e28ec571969050596d7495d55e1cf95
accepted PR #10 head: 4a397df25fe34fcfb581ea2e4409128a4ed2b168
accepted PR #9 head: 2df0af89f53f12e4dd42975e36d56794dc1e3c95

replacement-certified observability executable/source:
HEAD 4c2a064e31d460dd3c7534fadad6c50204ffcd82
TREE 9d341fcfd6eb5493887012814c5943850d903744

Architecture-94 P2 product base:
a810122a96b6fc90da25d71eede8da64b7272c98
```

Historical PD4 Architecture-110 source-foundation certification:

```text
commit 248cd8de6a3539aab21d5719d96cb7ff1aa0d14c
tree   5e867f1bfc6d945ad67f6c56be252b534645aeb2
5588 passed, 17 skipped in 1519.25s (0:25:19)
```

The later Architecture-111/112 and D5 capture-warm-up source is accepted at:

```text
branch feature/personal-desktop-paper-runtime
HEAD   8c2af5801cbc8f4df869b832a3b78b1eaa2f8996
TREE   f0591e966463c7e1e66dc00ad76fd895500a076f
```

GitHub read-only verification on September 15, 2026 confirmed the remote branch
still pointed exactly at that HEAD/tree before the D6/D7 branch was created.
Do not alter that armed branch merely to continue development.

The isolated D6/D7 branch was created from exactly that accepted D5 HEAD:

```text
feature/pd4-unattended-decision-publication
base HEAD 8c2af5801cbc8f4df869b832a3b78b1eaa2f8996
base TREE f0591e966463c7e1e66dc00ad76fd895500a076f
```

Docs-only catch-up commits may therefore advance the D6/D7 branch beyond its
base without changing the accepted D5 source/deployment tree.

Development interpreter:

```text
F:\AI\ai-trading-bot\.venv\Scripts\python.exe
```

Production interpreter:

```text
F:\AITradingBot\runtime\python.exe
```

Before every bounded local task:

```text
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git show -s --format=%T HEAD
git rev-parse origin/<expected-branch>
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

Sol Medium is no longer part of the default routing ladder. Model choice never
transfers architecture or acceptance authority. Do not use subagents unless the
user explicitly requests them.

Codex runs focused tests/checks during implementation. Broad/full certification
is normally user-run locally only after ChatGPT reviews the exact source. If a
broad local certification exposes a failure, diagnose/fix only the affected
area and rerun focused verification before asking for the broad suite again.

Exact-file stage only; never `git add .` or `git add -A`. Preserve unrelated
generated/untracked artifacts and historical permission-warning test folders.

No amend/rebase/merge/force-push/PR-metadata/review-thread changes without
explicit approval.

## 5. Standing authorization model

The user has authorized automatically continuing to the next best **safe,
source-only/read-only** scoped checkpoint when the preceding reviewed checkpoint
passes. Stop at protected effect boundaries or genuine architecture ambiguity.

This does **not** automatically authorize:

```text
manual/ad hoc provider calls or retries outside the reviewed D5 boundary
real decision publication
real Paper-v2 receipt-recovery mutation
production namespace provisioning effects
additional Task Scheduler mutation/enabling/manual start
first real unattended Paper-v2 settlement/execution
broker submission
live trading
changing a closed production/recovery/supervised/unattended gate outside an exact reviewed boundary
v1 cleanup/repair/migration
account/group/password changes
LSA policy/right changes
KSP/signing/private-export effects
unrelated project effects
merge/rebase/amend/force-push/PR metadata changes
```

## 6. Production identity and C3 lineage

Historical C3 source:

```text
82ba29ae2c2cc6bb3544077db0ee21868e6d5693
```

Historical manual C3 acceptance:

```text
call #5: FAILED / CONFIRMED
call #6: SUCCEEDED / CONFIRMED / SUCCESS_SELECTED
```

Selected call #6:

```text
selection_id: 36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280
snapshot_id: eba46838-44ae-5bec-97bf-98c6639ae6a7
SHA-256: 31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
length: 1291
captured_at: 2026-08-29T09:46:43.769105+00:00
```

Architecture 111 later introduced a separate closed-by-default unattended
market-data gate and source-owned zero-argument capture/session derivation. The
first unattended D3/D4 C3 acceptance capture selected session `2026-09-11`:

```text
selection_id: 7c42363d-4785-5823-be7e-93bf94426eac
snapshot_id:  8ddc60ed-3940-5379-a868-b46b9b7c95af
SHA-256:      704c1d0966acec3489a355fd6ef5369439b07e0e0a8e15c5f68cc2d847aa607f
length:       1289
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

## 7. Architecture 94 product composition

Accepted product work:

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

Architecture 111 adds a two-phase unattended path without replacing the final
Architecture-94 plan format:

```text
selected current C3 close + C3-authoritative history + account predecessor
-> PreparedManualPaperStrategyDecision
-> durable pre-open decision intent (contains no future execution-session open)
-> later current-C1 selected C3 open for intended execution session
-> existing ManualPaperStrategyPlanArtifactBinding
-> existing PD4 / Architecture-67 Paper-v2 authority
```

## 8. Paper-v2 deployment

Fixed production paths:

```text
final authority root: F:\AITradingBot\Paper-v2
A67 operation root:   F:\AITradingBot\Paper-v2\runtime
receipt parent:       F:\AITradingBot\Paper-v2\runtime\paper-operations
unattended invocation namespace:
                      F:\AITradingBot\Paper-v2\runtime\unattended-invocations
Architecture-111 decision namespace concept:
                      F:\AITradingBot\Paper-v2\runtime\unattended-decisions
```

Architecture 113 and D6 source certification have accepted the fixed decision
namespace path/security/publication contract. Production provisioning and
publication remain separately protected D7 checkpoints.

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

## 9. Completed historical milestones

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

### PD4 Architecture-110 source foundation — COMPLETE

Architecture:

```text
docs/architecture/110-personal-desktop-unattended-paper-operation-authority.md
```

Validation/completion records:

```text
docs/validation/pd4-unattended-personal-desktop-paper-plan.md
docs/validation/pd4-unattended-personal-desktop-paper-completion.md
```

Accepted source checkpoints:

```text
PD4-A    durable unattended invocation model and verification
PD4-B    durable invocation storage/read/publication/provisioning boundaries
PD4-C    read-only startup qualification under the same PD2A mutex
PD4-D    unattended Paper-v2 execution composition with effects closed
PD4-D-R1 explicit non-private shared composition interfaces
PD4-E    zero-semantic-argument launcher + frozen scheduler contract
PD4-F1   production read-only host-validation harness
PD4-F2   final source certification
PD4-F3   Trading-principal real-host read-only qualification
```

Final certified source:

```text
commit 248cd8de6a3539aab21d5719d96cb7ff1aa0d14c
tree   5e867f1bfc6d945ad67f6c56be252b534645aeb2
```

Final broad certification:

```text
5588 passed, 17 skipped in 1519.25s (0:25:19)
Ruff check PASS
Ruff format --check PASS (486 files)
git diff --check PASS
git diff --cached --check PASS
worktree/index clean
local HEAD == origin feature HEAD
```

The historical completion record correctly says that Architecture 110 source
completion alone did **not** authorize operational unattended deployment. Do not
rewrite it to pretend later D5 deployment evidence existed at that time.

## 10. Architecture 111 — unattended daily-cycle authority

Architecture and validation plan:

```text
docs/architecture/111-personal-desktop-unattended-daily-cycle-authority.md
docs/validation/pd4-unattended-daily-cycle-plan.md
```

The frozen unattended cycle is two-phase:

> A strategy decision targeting session `E` must be durably finalized strictly
> before `regular_open(E)`. After `E` is complete, an independently selected C3
> daily snapshot for `E` supplies the verified daily-bar open used to settle
> that already-finalized decision; its verified close becomes the newest
> strategy observation for the following decision.

Important rules:

- scheduler = untrusted wake only; no semantic trading arguments;
- source-owned v1 XNYS regular open = 09:30 America/New_York;
- selected-C3 session-indexed read authority; no filesystem/newest-file/caller
  selection identity;
- production rolling history must be C3-selected and consecutive;
- MA short=3/long=5 requires six consecutive selected C3 sessions before the
  first fully C3-backed unattended decision;
- the pre-open decision contains no execution-session open;
- late wake at/after intended open cannot manufacture the missing decision;
- `MISSED_DECISION_DEADLINE` and `SESSION_GAP` fail closed;
- no automatic multi-session catch-up;
- market-data capture and decision publication use separate effect gates.

## 11. Architecture 112 / D5 — capture-only warm-up

Architecture and validation plan:

```text
docs/architecture/112-personal-desktop-capture-only-warmup-authority.md
docs/validation/pd4-d5-capture-only-warmup-plan.md
```

D5 uses a distinct zero-semantic-argument capture-only launcher. One wake:

```text
requires all eight gates false
-> opens only market-data gate process-locally
-> calls G5 exactly once
-> restores market-data gate in finally
-> requires all eight gates false again
-> calls effects-closed G6 at most once when G5 state is safe
```

G5 exceptions/ambiguous outcomes never trigger a second call in-process or a
blind scheduler retry. D5 never opens the decision-publication or Paper-v2
effect gates.

### D5-A — accepted task qualification

The installed task matched the frozen D2 contract. Accepted predecessor XML:

```text
da851985d9bfb04c65a83cb64b5441a2f7fd50391924a844749e365ee282d6ec
```

### D5-B — accepted action-only task mutation

The reviewed mutation changed only the launcher action to:

```text
-I F:\AI\worktrees\ai-trading-bot-personal-desktop\scripts\run_personal_desktop_unattended_capture_warmup.py
```

The first mutation call failed with a credential authentication error. That was
not treated as retry authority. Read-only reconciliation first proved the exact
D2 task remained registered with the identical predecessor XML hash. Only then
did a credential-aware second attempt proceed under the existing explicit D5-B
authorization.

Accepted post-mutation D5 task XML:

```text
8005373fad791c85776b4a35b662d46e06fec4ea40ac9ebfead9f413715da457
```

### D5-C — first scheduled capture-only wake ACCEPTED

Canonical evidence:

```text
session:                2026-09-14
terminal:               SUCCEEDED
provider disposition:   CONFIRMED
selection_id:           dea50bc9-95b4-5f63-ac40-a7353133be53
attempt_id:             70f5f586-a05b-56c5-adde-bfa5d027864b
snapshot_id:            b3737822-35ee-5238-a87f-401b4597df46
artifact SHA-256:       db16bd7d6edda1709aeea64158f8751c02714ed45e9c6441935640e43ffa5487
artifact identity SHA:  bfd131801558be6cbbed96b1e176c428b98df4e9c6dcccffb77c74acdc4870ba
account predecessor:    ed4640e5-0630-525d-b916-d50e31e3ba2a
```

Current authoritative strategy history:

```text
2026-09-11
2026-09-14
selected_count = 2/6
G6 = WARMING_UP
G5 post-capture = NO_NEW_COMPLETED_SESSION
```

All eight committed gate constants were false before and after the accepted
wake. The armed task should continue accumulating eligible completed sessions
naturally. Do not manually start it, backfill history, or modify its source/task
contract while this evidence is accumulating.

The 2/6 D5 facts above are historical predecessor evidence. Later D7
qualification reached the required 6/6 READY suffix through completed session
2026-09-18; D7 publication/reconciliation then closed and D7 was integrated.
Keep the D5 source/task as historical deployment evidence rather than treating
this subsection as current warm-up status.

## 12. Historical D7-D source preparation checkpoint

D6-A through D6-D source certification is **ACCEPTED** under Architecture 113.

```text
certified D6 source HEAD: fb00e9898c2e5cdd3db27cd91c393f5994c7cca9
certified D6 source TREE: eef138bb3ed144d153ae60193aaacdcb7584c513
final full suite: 6007 passed, 17 skipped in 1502.66s
source-certification completion record:
docs/validation/pd4-d6-unattended-decision-publication-source-certification.md
```

The certified source independently reconstructs the current-C1 selected-C3
six-session MA(3,5), desired-quantity-1 candidate under the PD2A mutex, enforces
the strict pre-open deadline, and contains the one-shot decision-only
publication boundary. Source certification authorizes no production effect.

D7-A read-only qualification source preparation is **ACCEPTED**:

```text
accepted D7-A source commit: c72ca6c8665b62c0b8d4f735fc2261a513cb81d5
accepted D7-A source tree:   3b05c68ff1487a1c7d5984a200ee9f20d7b92fca
focused verification:       910 passed
production qualification:   NOT RUN
```

The accepted D7-A source adds a separate zero-semantic-argument Trading
diagnostic boundary and fixed-namespace missing/present/security qualification.
It issues no permit, opens no writer or effect gate, and performs no
provisioning, capture, Paper-v2 mutation/recovery, scheduler, broker, or live
effect. Its sanitized output is not reusable D7-C authority; D7-C must rederive
production truth independently.

D7-D independent Trading-principal post-publication reconciliation was the
then-current source-only checkpoint. It had to rederive the exact expected decision
from fresh current-C1, selected-C3 history, and Paper-v2 account authority,
discover and reread the finalized decision through genuine same-process
provenance, and prove the account predecessor remains unchanged under the PD2A
mutex. D7-D is reconciliation rather than fresh publication admission: an exact
already-finalized decision remains reconcilable at or after its intended regular
open. D7-D cannot issue a permit, open a writer or effect gate, provision or
repair storage, or perform any provider, Paper-v2, scheduler, broker, or live
effect. No production D7-D invocation is authorized by source preparation.

D5 remains armed and unchanged:

```text
D5 HEAD: 8c2af5801cbc8f4df869b832a3b78b1eaa2f8996
D5 TREE: f0591e966463c7e1e66dc00ad76fd895500a076f
latest accepted read-only state: WARMING_UP, 2/6
selected sessions: 2026-09-11, 2026-09-14
```

D7-A production qualification is waiting for natural current six-session
`6/6 READY` history and an open publication deadline. Preserve the armed D5
worktree/task and do not synthesize history or manually invoke capture.

The protected sequence remains D7-A Trading read-only qualification, conditional
separately approved D7-B Administrator provisioning if missing, explicitly
approved D7-C publication, and independent D7-D read-only reconciliation.
**D7-C remains protected and explicitly unauthorized.** No production D7-A
qualification, provisioning, publication, or settlement is authorized by this
source-only preparation checkpoint.

## 13. Roadmap

```text
PD0   personal-desktop profile adoption                     COMPLETE
PD1   personal-desktop paper-account authority v2           COMPLETE
PD2   reliable supervised manual paper cycle                COMPLETE
PD3   supervised crash/recovery validation                  COMPLETE
PD4   unattended simulated-paper
  Architecture-110 source foundation                       COMPLETE
  Architecture-111 daily-cycle source/design               ACCEPTED
  D3/D4 first unattended C3 acceptance                     ACCEPTED
  Architecture-112 / D5 capture-only warm-up predecessor   COMPLETE
  Architecture-113 / D6-A through D6-D source              ACCEPTED
  D7 qualification/publication/reconciliation              COMPLETE
  D7 integration into develop                              COMPLETE
  D8/D9 settlement source integration                      COMPLETE
  operator observability O1-O4 source                      COMPLETE
  operator observability integration                       COMPLETE
  D8-A Trading-principal qualification                     NEXT PROTECTED OPERATIONAL CHECKPOINT
  D8-B effectful settlement                                PROTECTED / UNAUTHORIZED
  operational unattended simulated-paper acceptance        NOT YET COMPLETE
PD5   broker-paper integration                              NOT STARTED
PD6   broker-paper soak / operational hardening             NOT STARTED
PD7   personal-desktop live-readiness                       NOT STARTED
PD8   tiny restricted live -> gradual maturity              NOT STARTED
```

Do not move to broker-paper merely because D5 market-data warm-up succeeds.
The critical path is safe unattended data → safe unattended decision → safe
unattended Paper-v2 settlement → operational soak.

## 14. Effect gates and still-protected actions

All eight production gate constants remain committed false:

```text
PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED            = False
PERSONAL_DESKTOP_UNATTENDED_DECISION_PUBLICATION_EFFECTS_ENABLED            = False
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED                       = False
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED                         = False
PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED             = False
PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED                 = False
PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED             = False
PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED  = False
```

Architecture 112 permits the D5 runtime to open only the **process-local**
market-data gate around exactly one G5 call. That does not authorize ad hoc
manual provider calls or retries.

Still protected/not authorized outside exact reviewed checkpoints:

```text
manual/ad hoc provider effects or retries outside D5
first real D6/D7 decision publication
real Paper-v2 receipt-recovery mutation
decision/storage namespace provisioning effect
additional scheduler mutation/manual start
first real unattended Paper-v2 settlement/execution
broker order submission
live trading
old v1 publisher rerun
v1 staging delete/repair/rename/migration/reuse
Paper-v2 manual mutation outside reviewed effect checkpoints
account/group/password changes
LSA rights/policy changes
KSP/signing/private-export effects
merge/rebase/force-push/amend/PR metadata changes without explicit approval
```

## 15. Resume procedure

1. Read `AGENTS.md`, `docs/PROJECT_STATUS.md`, this handoff,
   `docs/AI_DEVELOPMENT_WORKFLOW.md`, Architectures 110–112, the PD4 source-
   foundation completion, the Architecture-111 daily-cycle plan, and the
   Architecture-112 D5 plan before new implementation.
2. Prove exact worktree/branch/HEAD/tree/origin/clean state before edits or
   operator work. Never self-correct a mismatch.
3. Treat PD1, PD2, PD3, Architecture-110 source foundation, Architecture 111,
   D3/D4, and accepted D5-A/B/C evidence as established predecessors.
4. Preserve the armed D5 branch at accepted source HEAD/tree while its scheduler
   accumulates warm-up sessions. Do not use that worktree for D6/D7 development.
5. Preserve the dedicated non-admin Trading principal, C1/P2 authority, PD2A
   mutex, Architecture-67 durability/idempotency, and PD3 recovery rules.
6. Remember D5 warm-up is currently `2/6` and `WARMING_UP`; there is no authority
   to synthesize missing history from the offline seed.
7. Treat Architecture 113, its validation plan, the D6 source-certification
   record, and D7-A source commit
   `c72ca6c8665b62c0b8d4f735fc2261a513cb81d5` as accepted. Continue the
   isolated D7-D source-only preparation; wait for natural 6/6 READY before any
   protected production qualification or publication.
8. Use Sol High for Architecture 113 and any implementation changing Windows
   publication security, authority, ordering, crash ambiguity, or effect
   containment. Use Luna/Astra only for bounded work after the contract is
   frozen according to `AGENTS.md`.
9. Stop before any real decision-publication, storage-provisioning, Paper-v2,
   recovery, scheduler, broker, or live effect unless explicitly authorized.
10. Use fresh external `--basetemp` for controlled Windows pytest and keep full
    repository certification for the final meaningful source gate.
11. After each accepted checkpoint, update/review this handoff and
    `docs/PROJECT_STATUS.md` before treating the checkpoint as closed.
12. Always include the next recommended milestone/step in milestone and
    verification reports.

## 16. Definition of project success

The project is not complete merely when it can place trades. It succeeds when
the platform can research deterministically, acquire trusted data safely, apply
deterministic risk, interact safely with a brokerage, reconcile external
outcomes after failures/restarts, run unattended, fail closed when authority or
state is uncertain, expose durable evidence, operate under strict real-money
controls, recover predictably, remain understandable/stoppable by its operator,
and expose the reviewed system through a polished GUI without giving AI or
presentation code alternate authority paths.


## D7-A production milestone

D7-A production read-only qualification is accepted from exact certified source
`3dfa9e2cab372f8cb034b90256ed3fba9da6c878` /
`bb1de2e7c2933ba3a777523f2a0e2feee5fa8c39`.

Accepted evidence:

```text
completed session:          2026-09-18
history:                    READY 6/6
selected snapshot:          680b260f-08c9-5923-87bb-b5f0a4701380
candidate decision:         f2188b5e-e6a4-5398-be41-8867d9268355
execution session:          2026-09-21
regular open:               2026-09-21T13:30:00+00:00
account predecessor:        ed4640e5-0630-525d-b916-d50e31e3ba2a
namespace:                  PRESENT_VALID
storage:                    ABSENT
deadline open:              true
all eight gates closed:     true
real effect performed:      false
```

D7-B is skipped because the namespace already exists and validates. The next
production checkpoint is protected D7-C first publication. Do not run D7-C
without explicit operator approval. After D7-C, run fresh D7-D independent
read-only reconciliation before accepting publication.


## Replacement D7 source certification

Replacement D7 source is accepted at:

```text
HEAD: acd606a41ac50f172ac62377ce6d4e7c8c4d3a32
TREE: 784695d05865a767ba187adf38fd4924897127a9
```

Certification:

```text
5534 passed, 17 skipped outside Architecture-77
775 passed in the clean Architecture-77 harness
6309 passed, 17 skipped combined
Ruff check/format PASS
diff checks PASS
worktree/index clean
```

The correction freezes moving-average Decimal arithmetic and proposal quantity
normalization to historical/default Python Decimal semantics and adds the LF
checkout contract for the frozen strategy-history seed. The seed remains 1060
bytes with SHA-256
`40dda54c82324f358d640cce89e467295b8f5b73a32fed76c52e7ca90d398e64`.

The old D7-A READY result and candidate
`f2188b5e-e6a4-5398-be41-8867d9268355` are historical evidence only. Fresh
D7-A must run read-only from a disposable checkout pinned to the exact
replacement source and compare the reconstructed candidate. D7-C remains
protected and unauthorized.


## Replacement D7-A production qualification

Fresh read-only D7-A from exact replacement certified source:

```text
HEAD: acd606a41ac50f172ac62377ce6d4e7c8c4d3a32
TREE: 784695d05865a767ba187adf38fd4924897127a9
```

returned exit code 0 with:

```text
READY
candidate:                    f2188b5e-e6a4-5398-be41-8867d9268355
completed session:            2026-09-18
selected history:             6/6
selected snapshot:            680b260f-08c9-5923-87bb-b5f0a4701380
intended execution session:   2026-09-21
regular open:                 2026-09-21T13:30:00+00:00
account predecessor:          ed4640e5-0630-525d-b916-d50e31e3ba2a
namespace:                    PRESENT_VALID
storage:                      ABSENT
deadline open:                true
all eight gates closed:       true
real effect performed:        false
```

The candidate exactly matches the earlier historical D7-A result after the
Decimal correction. D7-B remains unnecessary. The next step is the protected
D7-C first publication boundary. It requires explicit operator approval and
must perform a fresh preflight before any effect.


## D7-C first approved attempt — fail-closed evidence

Fresh D7-A preflight passed, but the one approved publication invocation
returned `BLOCKED`, exit 6, with null decision/session fields and
`real_effect_performed=false`. No retry was attempted; D7-D was not run.

Review identified the shared production selected-C3 history reader lifetime as
the likely pre-effect failure: permits are weakly bound to their P2 reader, while
the older history helper lets its local reader leave scope before G4 decision
construction revalidates the binding. D7-A explicitly retains readers and
therefore does not hit this path.

Next: source-only lifetime fix in an isolated branch, focused tests, full
replacement certification, then fresh read-only D7-A. D7-C requires a new
explicit approval after those checks.


## Certified D7 selected-C3 reader-lifetime correction

Replacement certified D7 source:

```text
HEAD: 8bc6d436142531dec17bf7b960a7ac1eb2e45b09
TREE: 18255e5272728a5bf2b8f8633fff23cf940b77be
```

Certification:

```text
5538 passed, 17 skipped outside Architecture-77
775 passed in the clean Architecture-77 harness
6313 passed, 17 skipped combined
Ruff check/format PASS
diff checks PASS
worktree/index clean
```

This source fixes the D7-C/G6 selected-C3 reader lifetime defect without
weakening process-local permit provenance. The failed first D7-C attempt remains
effects-closed evidence only.

Next: fresh read-only D7-A from the exact certified source. Require reproduction
of candidate `f2188b5e-e6a4-5398-be41-8867d9268355`, namespace
`PRESENT_VALID`, storage `ABSENT`, deadline open, and all eight gates closed.
Only after that may a new D7-C approval be considered.


## Post-reader-lifetime-fix D7-A qualification

Fresh read-only qualification from exact certified source:

```text
HEAD: 8bc6d436142531dec17bf7b960a7ac1eb2e45b09
TREE: 18255e5272728a5bf2b8f8633fff23cf940b77be
```

returned exit code 0 and:

```text
classification:             READY
candidate:                  f2188b5e-e6a4-5398-be41-8867d9268355
completed session:          2026-09-18
selected history:           6/6
selected snapshot:          680b260f-08c9-5923-87bb-b5f0a4701380
intended execution session: 2026-09-21
regular open:               2026-09-21T13:30:00+00:00
account predecessor:        ed4640e5-0630-525d-b916-d50e31e3ba2a
namespace:                  PRESENT_VALID
storage:                    ABSENT
deadline open:              true
all eight gates closed:     true
real effect performed:      false
```

The exact production candidate is unchanged after the reader-lifetime repair.
The next checkpoint is again D7-C first-decision publication, but the prior
approval was consumed by the blocked no-effect attempt. A new explicit approval
is required before any second D7-C invocation.


## Durable D7-C acceptance and D7-D admission defect

Post-publication D7-A independently proves the finalized decision is exact:

```text
ALREADY_FINALIZED
candidate:                f2188b5e-e6a4-5398-be41-8867d9268355
storage:                  FINALIZED_IDENTICAL
completed session:        2026-09-18
selected history:         6/6
namespace:                PRESENT_VALID
all eight gates closed:   true
real effect performed:    false
```

The D7-A CLI returns exit 0 for `ALREADY_FINALIZED`. D7-C is therefore
durably accepted; do not republish.

D7-D's all-default BLOCKED result is a source bug at mutex admission:
`read_personal_desktop_paper_account` returns a validated account capability,
but D7-D immediately replaces it with immutable evidence and passes that
evidence to `supervised_paper_cycle_admission`, which requires the genuine
validated capability. Keep capability and evidence separate, use evidence for
comparison, and pass the capability into admission. D8 remains blocked until a
corrected, certified D7-D reconciles the durable decision.


## Certified D7-D account-admission correction

Replacement-certified D7 source:

```text
HEAD: ca05b2c583f79039e9de64f4a01b8de2ff2ab3ad
TREE: d1c3e73eccaba6701bac86f38fb71a99d08ff2d5
```

Certification:

```text
5540 passed, 17 skipped outside Architecture-77
775 passed in clean Architecture-77 harness
6315 passed, 17 skipped combined
Ruff check/format PASS
diff checks PASS
worktree/index clean
```

The final D7 lineage now contains the Decimal, LF checkout, selected-C3 reader
lifetime, and D7-D account-admission ordering corrections.

The durable D7 decision remains:
`f2188b5e-e6a4-5398-be41-8867d9268355`, already proven
`FINALIZED_IDENTICAL` by post-publication D7-A.

Next: run D7-D read-only from a fresh checkout pinned to the exact certified
source. Require `RECONCILED`, exact expected/finalized decision identity,
`FINALIZED_IDENTICAL`, `PRESENT_VALID`, 6/6 history, all eight gates closed,
and no real effect. Do not republish and do not proceed to D8 before acceptance.


## D7 closed

The corrected, replacement-certified D7 source has now passed real production
D7-D reconciliation:

```text
classification: RECONCILED
expected_decision_id:  f2188b5e-e6a4-5398-be41-8867d9268355
finalized_decision_id: f2188b5e-e6a4-5398-be41-8867d9268355
selected history: 6/6
namespace: PRESENT_VALID
session discovery: FINALIZED
storage: FINALIZED_IDENTICAL
all eight gates closed: true
real effect performed: false
exit code: 0
```

D7 is closed. Authoritative executable source remains
`ca05b2c583f79039e9de64f4a01b8de2ff2ab3ad` /
`d1c3e73eccaba6701bac86f38fb71a99d08ff2d5`.

Next: review the consolidated D7 branch against current `develop`, then merge
only with explicit operator approval. After merge, perform post-merge
verification and forward-integrate the accepted develop source into the D8/D9
settlement lineage before any D8 effect.


## D7 integration completed

The closed D7 lineage was merged through PR #8 into `develop`.

```text
merge commit: 9cf436be71d2f37820190c2a920692abb8802b82
tree:         12169f7414a6ccb53db6e27150926bb72e111c72
```

Post-merge branch inventory found no additional branch that should be merged
directly into `develop` now. D7 predecessor/fix branches are subsumed. Historical
P3-R1, reliable-manual, C2/C3 certification, and early scheduling branches are
superseded and should remain historical. The certified D8/D9 settlement branch
and its descendant operator-observability branch remain parked because they were
built before the final D7 corrections.

Next: create a fresh D8/D9 forward-integration branch from current `develop`,
bring forward only the accepted settlement source, resolve against the final D7
contracts, review exact diff, and perform replacement certification before any
D8 production action.


## D8/D9 settlement source forward integration — REPLACEMENT-CERTIFIED PRE-MERGE

The D8/D9 settlement source has now been forward-integrated onto the final D7
source line and replacement-certified on
`feature/d8-d9-settlement-forward-integration`. D7 remains integrated and
closed. This records the pre-merge source-only certification; it authorized no
production or live effect.

Replacement-certified candidate:

```text
candidate files:                       22
certified source commit:               da093791cf6d879f1b07d605665900c28b9a7e9d
certified source tree:                 1c9f6840eeae7feb5456892f9d8119eb45466af9
parent/current-develop integration base:
                                      252655f690165d74fe9d762810111a399c3ff073
tracked candidate aggregate diff hash: 79e6317a28ab531df132d14dd4b8b1abd53fda81
```

Replacement certification passed:

```text
broad non-Architecture-77:          5,704 passed, 17 skipped
Architecture-77:                       775 passed, 0 skipped
total:                               6,479 passed, 17 skipped
Ruff check:                          PASS
Ruff format --check:                 PASS (548 files already formatted)
git diff --check:                    PASS
git diff --cached --check:           PASS
frozen history seed length:          1060 bytes
frozen history seed SHA-256:         40dda54c82324f358d640cce89e467295b8f5b73a32fed76c52e7ca90d398e64
post-certification candidate snapshot comparison: PASS
all 22 files:                        byte-for-byte unchanged through certification
```

The initial final no-change verification stopped because an additional
hard-coded expected-hash table contained an incorrect expected value for
`pd4_read_only_settlement_reconciliation.py`. The reported actual hash matched
its pre-certification snapshot, and no repository mutation occurred. A
follow-up frozen-candidate integrity verification proved all 22 files
byte-for-byte unchanged, so no test rerun was required.

The historical `feature/pd4-unattended-settlement` branch remains reference /
audit history and must not subsequently be merged into `develop`.
`feature/pd4-operator-observability` remains parked and must be
forward-integrated separately only after settlement integration is accepted.
D8-B effectful settlement remains unauthorized, and no production/live
authorization is implied by source certification.

The post-certification integration step and its closeout are recorded below.


## D8/D9 settlement integration — CLOSED

PR #9 was accepted and merged into `develop` as the normal history-preserving
integration of the accepted D8/D9 settlement source.

```text
merge/current integration commit: a18dd765523ddcc55b2a10d312e28410a92b81c7
resulting tree:                   d50cbcfcf800417fe2dc90b9be5957354809a2d9
accepted PR #9 head:              2df0af89f53f12e4dd42975e36d56794dc1e3c95
```

The GitHub post-merge comparison proved that `develop` is the normal
history-preserving merge of PR head `2df0af89...`, with no resulting tree or
file difference from that accepted head.

D7 is integrated and closed. The replacement-certified executable source
remains `da093791cf6d879f1b07d605665900c28b9a7e9d`, with certified source tree
`1c9f6840eeae7feb5456892f9d8119eb45466af9`; the merge does not redefine that
certified source identity.

The historical `feature/pd4-unattended-settlement` branch remains reference /
audit history and must not later be merged into `develop`.
`feature/pd4-operator-observability` remains parked and must later be
forward-integrated separately onto the accepted current `develop`.
D8-B effectful settlement remains unauthorized. No production or live
authorization is implied.

The next protected operational checkpoint is a fresh read-only **D8-A
Trading-principal qualification** from the current integrated source.

## Operator observability O1-O4 — integrated and closed

Integration/source identity:

```text
historical feature branch: feature/operator-observability-o1-forward-integration
base develop HEAD:         f7a177db37d6783d4e9865cc5bb98292f4907274
base develop TREE:         8fe7d9175f5286bf6c88924f5dc3829012b13cd2
certified source HEAD:     4c2a064e31d460dd3c7534fadad6c50204ffcd82
certified source TREE:     9d341fcfd6eb5493887012814c5943850d903744
accepted PR #10 head:      4a397df25fe34fcfb581ea2e4409128a4ed2b168
merge commit:              c2de20c35a67e7f6c164d25e08dd0d2fc7d52641
resulting tree:            f38913b50e28ec571969050596d7495d55e1cf95
```

GitHub post-merge verification showed the merge is the normal history-preserving
merge of the accepted PR head and that there is no file/tree difference between
the PR head and merge result. The certified executable/source identity remains
the pre-docs source HEAD/TREE above.

O1-O4 are accepted:

- O1: bounded Qt-free observability models/adapters.
- O2: zero-semantic-argument read-only production snapshot. The accepted O2
  correction retains selected-C3 provenance for the full proof lifetime.
- O3: read-only Operations page/navigation/service wiring. Default GUI startup
  remains unavailable and does not invoke production O2.
- O4: pure deterministic strategy preview. It calls the current canonical
  moving-average evaluator, preserves current Decimal/proposal identity, and
  returns only bounded presentation scalars. Ordinary evaluation errors fail
  closed to sanitized `BLOCKED`.

Final exact-tree certification:

```text
focused O1-O4:                    122 passed
A4/MainWindow regression:          23 passed
broad non-Architecture-77:       5,789 passed, 17 skipped
Architecture-77 clean harness:     758 passed
combined:                        6,547 passed, 17 skipped
Ruff check:                      PASS
Ruff format --check:             PASS (564 files)
diff checks:                     PASS
worktree/index:                  clean
```

The feature-worktree Architecture-77 attempt failed only because the harness's
fixed repository-local lifecycle-arbiter path was not writable. The exact
candidate commit/tree passed all 758 tests in a clean detached certification
worktree; no source mutation or permission workaround was used.

The source certification authorizes no production/effectful action. All eight
committed effect gates remain false. An earlier safe D8-A invocation while the
runtime's current completed session was still 2026-09-18 returned
`NO_SETTLEMENT_PENDING`; that historical read-only result does not satisfy the
later D8-A checkpoint for the intended settlement session.

Completion record:
`docs/validation/pd4-operator-observability-o1-o4-source-certification.md`.

Operator observability is integrated and closed.

The docs-only D8-A readiness checkpoint at
`docs/validation/pd4-d8a-read-only-settlement-readiness.md` was reviewed and
merged through PR #11.

```text
accepted PR #11 head: 81200de26467f59e84cb732edaa944e4c262fd60
merge commit:         e29ee911983044a89efe8e68fd0e45a8907b572e
merge tree:           d6a1e3a81959e91ae63277c4f1a72db703cad45b
PR-head -> merge:     no file differences
```

The current source-inheritance audit found zero changes among the 22
replacement-certified D8/D9 settlement candidate files. The combined certified
source `4c2a064e31d460dd3c7534fadad6c50204ffcd82` /
`9d341fcfd6eb5493887012814c5943850d903744` remains the preferred exact
source checkout for the first meaningful D8-A unless a later replacement
certification supersedes it.

The next protected operational step remains one fresh read-only D8-A only after
the source-owned calendar derives completed session `2026-09-21` and current
selected-C3 evidence for that session exists. The frozen timing policy uses the
strict previous XNYS session and the accepted D5 task wakes at 01:30 Pacific
daily, so the preferred first meaningful attempt is after the normal
2026-09-22 D5 wake has completed. The earlier `NO_SETTLEMENT_PENDING`
invocation remains historical only. D8-B remains protected and unauthorized.

## GUI-A8 read-only multi-source composition — active parallel milestone

While D8-A waits for the normal 2026-09-22 D5 wake and selected C3(E), GUI work
continues safely on:

```text
branch: feature/gui-a8-read-only-composition
base develop: f90b0c77e19cb00cbe3813d6b811e9d2cf1b561a
```

A8a is accepted through Architecture 115 and
`docs/validation/gui-a8-read-only-multi-source-composition.md`.

The frozen scope is a normal-startup composition layer for already-reviewed
read-only Research, offline-verified Market Data, and offline-verified Paper
Account adapters. Input selection is explicit only; no directory discovery or
operational-current/latest inference is allowed. Paper Operation remains
unavailable unless already-verified execution inputs are supplied by a future
reviewed boundary. Ordinary startup must not invoke production O2, C1/C2/C3,
credentials, provider transport, settlement/recovery, Task Scheduler, brokerage,
or live effects.

A8b is accepted at source HEAD
`f5a0545c147b5f56af125886c77c36a77cec48f4` / tree
`6381588ff509e9962169338e11c5263a13f98d79`.

Accepted evidence:

```text
focused A8b + affected adapter/MainWindow regression: 102 passed
Ruff check: PASS
Ruff format --check: PASS
git diff --check: PASS
final worktree/index: clean before commit; formatter commit pushed normally
```

The final A8b commit only organized one import block and applied Ruff formatting
to two test files. It did not change runtime behavior.

A8c is accepted at source HEAD
`d050538149879d01b1d6f2e251878800d8d49f75` / tree
`3f26a8977c468da9c45ca55c36fc86b689ab3290`.

Accepted evidence:

```text
focused A8c + affected adapter/startup regression: 102 passed
complete tests/gui regression:                    283 passed
Ruff check src/trading_bot/gui tests/gui:          PASS
Ruff format --check:                               PASS after formatter-only follow-up
git diff --check:                                  PASS
```

The final A8c commit only reformatted the new integration test; independent
GitHub diff review found no semantic change.

A8d and final GUI-A8 source certification are accepted.

```text
certified source HEAD:  f8d90ffedd97594d32e179df845d494bba4df61c
certified source TREE:  f5162c47716ed8cb01b519e45be09316bda39bc0
base develop:           f90b0c77e19cb00cbe3813d6b811e9d2cf1b561a

broad non-Architecture-77:     5,826 passed, 17 skipped
Architecture-77 clean harness:   758 passed
combined:                      6,584 passed, 17 skipped
Ruff check:                    PASS
Ruff format --check:           PASS (567 files)
diff checks:                   PASS
visual gate:                   PASS
```

Visual certification covered default startup, combined Research + Market Data +
GENESIS, successor Paper Account, 1180x760 normal size, and 920x620 minimum
size. The final correction added the missing Paper Account Overview card,
replaced stale Market Data overview wording with truthful explicit-artifact
wording, and kept complete SHA-256 values visible/selectable at minimum width.

Independent final GitHub review found 15 expected changed files, 26 commits
ahead and 0 behind the exact base, with no source path into production O2,
C1/C2/C3, credentials, provider network access, paper execution, settlement,
recovery, scheduler mutation, brokerage, or live effects. Paper Operation and
Operations remain unavailable under ordinary GUI startup.

GUI-A8 is integrated and closed through PR #12.

```text
accepted PR head:     b091c81607e56dbe7e4b937e5264ea9256907385
merge commit:         eab3a77d30875927c78d15a94c00fb899bc756b2
resulting merge tree: 6d328f07212bc237e7cfa4a034e68b41febf2fc0
PR-head -> merge:     no file differences
```

The authoritative executable/source certification remains
`f8d90ffedd97594d32e179df845d494bba4df61c` /
`f5162c47716ed8cb01b519e45be09316bda39bc0`.

Final PR review also recorded one intentional fail-closed limitation: ordinary
A8 successor startup does not synthesize or discover
`VerifiedPriorCheckpoint` lineage evidence. A complete successor edge whose
prior verifies as GENESIS is supported directly; later successor-after-successor
inspection requires a future separately reviewed boundary that supplies
already-verified prior lineage evidence. The GUI does not guess or traverse
lineage to make such a page available.

Next safe GUI milestone: GUI-A9 read-only System Health / Audit. D8-A remains a
separate protected operational checkpoint; D8-B remains protected and
unauthorized.

## GUI-A9 read-only System Health & Audit — source certified

GUI-A9 is source-certified on:

```text
branch: feature/gui-a9-system-health-audit
base develop: 0eb39514ba45f39fb7dc7f02c06a458a56f4fc5e
HEAD: 92e08a5d115521c89f5798dc9706ae83c5e9d8d2
TREE: ce23f4de89bcd9fb65aaaba70ab8d146b2f4a7a1
```

Architecture 116 freezes A9 as a pure in-memory presentation milestone. The
System page is upgraded to System Health & Audit by adapting the exact Research,
Paper Operation, Paper Account, Market Data, and Operations states already
acquired by `MainWindow`. No new `GuiApplicationService` method is added and
System navigation causes no reread.

Accepted final evidence:

```text
broad non-Architecture-77:     5,841 passed, 17 skipped
Architecture-77 clean harness:   758 passed
combined:                      6,599 passed, 17 skipped
Ruff check:                    PASS
Ruff format --check:           PASS (573 files)
diff checks:                   PASS
visual gate:                   PASS
```

Earlier GUI gates also passed: 49 focused A9 tests, 301 complete GUI tests,
18 post-format focused tests, 9 formatter sanity tests, and 12 scroll/style
correction tests.

Visual certification covered default, populated GENESIS, successor/minimum-size,
and styled ATTENTION states. The final page keeps bounded audit IDs/hashes
selectable, opens at the top when populated, distinguishes blocked from
unavailable state, and makes explicit that read-only health is not
production/trading readiness.

Independent final GitHub review found 13 expected changed files, 24 commits
ahead and 0 behind the exact base. No source path was added into production O2,
C1/C2/C3, filesystem discovery, Credential Manager, provider/network access,
Task Scheduler, paper execution, settlement, recovery, brokerage, or live
effects. Audit state does not retain research source paths or paper receipt
paths.

GUI-A9 is integrated and closed through PR #13.

```text
accepted PR head:     d035b189c7c800a7f36ce92cebe3511f1dc0b5fc
merge commit:         8d88229bd9936652cea514dd65284734309c51f6
resulting merge tree: 29af3c95f2d8995da5feca69863c24bb5dcc0522
PR-head -> merge:     no file differences
```

The authoritative executable/source certification remains
`92e08a5d115521c89f5798dc9706ae83c5e9d8d2` /
`ce23f4de89bcd9fb65aaaba70ab8d146b2f4a7a1`.

Final PR review confirmed the A9 page is derived solely from already-acquired
GUI presentation state, System navigation causes no service reread, audit
evidence stays bounded to approved IDs/hashes, and no production/runtime
authority or effect path was introduced.

Next safe GUI candidate: GUI-A10 read-only Audit History / Evidence Timeline
using explicit offline artifacts only. D8-A remains a separate protected
operational checkpoint; D8-B remains protected and unauthorized.

## GUI-A10 read-only Evidence Timeline — source certified

GUI-A10 is source-certified on:

```text
branch: feature/gui-a10-evidence-timeline
base develop: 74039dd4f25affea3086e3ed2703ec2415c8e70a
HEAD: 6638eea47163fbaa8db3c0fb4bd9c9b5b4ae2e75
TREE: f5f6809e21b45116a4aa5334a8afdfe7616e1efb
```

Architecture 117 freezes A10 as a presentation-only Evidence Timeline. The
timeline is built from the exact Research, Paper Operation, Paper Account,
Market Data, and Operations states that `MainWindow` already acquires. No new
`GuiApplicationService` method is added; MainWindow still performs exactly six
service reads and Evidence navigation adds no reread.

Accepted final evidence:

```text
focused A10/integration:         68 passed
complete GUI regression:       314 passed
broad non-Architecture-77:   5,853 passed, 17 skipped
Architecture-77 clean harness: 758 passed
combined:                    6,611 passed, 17 skipped
Ruff check:                  PASS
Ruff format --check:        PASS (579 files)
diff checks:                PASS
visual gate:                PASS
```

Visual certification covered the default empty timeline, populated Research +
Market Data + GENESIS, and a successor Paper Account at 920x620. Timestamped
entries are deterministic newest-first, untimed evidence follows stably, long
identifiers/hashes remain selectable, and the initial view stays at the top.

Independent final GitHub review found 16 expected changed files, 25 commits
ahead and 0 behind the exact base. The A10 source introduces no new runtime I/O
or discovery and no path into production O2, C1/C2/C3, Credential Manager,
provider/broker calls, Task Scheduler, paper execution, settlement, recovery,
or live effects. Research source paths and Paper receipt paths are not retained
in timeline state.

GUI-A10 is integrated and closed through PR #14.

```text
accepted PR head:     ab7f12cfea741747035c6a40e9d70c9860226751
merge commit:         f14847c99d85bbb415bbbd25120766595cbfcdca
resulting merge tree: ca45c5d882c8c20185eb9ab36caa129a949ab8ff
PR-head -> merge:     no file differences
```

The authoritative executable/source certification remains
`6638eea47163fbaa8db3c0fb4bd9c9b5b4ae2e75` /
`f5f6809e21b45116a4aa5334a8afdfe7616e1efb`.

Final PR review confirmed A10 is derived solely from already-acquired GUI
presentation state, Evidence navigation causes no service reread, timeline
ordering is deterministic, path/receipt disclosure is excluded, and no
production/runtime authority or effect path was introduced.

Resume GUI development automatically with the next bounded read-only
presentation milestone. D8-A remains separate and protected; D8-B remains
protected and unauthorized.

## GUI-A11 read-only Evidence Explorer — source certified

GUI-A11 is source-certified on:

```text
branch: feature/gui-a11-evidence-explorer
base develop: 269fec43adfe73ffce09f5c83e6218efcb1d0c02
HEAD: 2aba51e544d1cf356730ad8bc01a7b909af515ce
TREE: 3dd12a94615748d05df784cbaa8ac49576f9d032
```

Architecture 118 keeps A11 entirely inside the accepted A10 presentation
boundary. `EvidenceTimelineFilter` and
`filter_evidence_timeline_entries(...)` operate only on the immutable A10
timeline state. The Evidence page adds local search, source filtering, match
counts, and a distinct no-match state; filtering performs no service call or
artifact I/O.

Accepted final evidence:

```text
focused A11:                   24 passed
complete GUI regression:     324 passed
broad non-Architecture-77: 5,863 passed, 17 skipped
Architecture-77 exact-tree:  758 passed
combined:                  6,621 passed, 17 skipped
Ruff check:                PASS
Ruff format --check:       PASS (581 files)
diff checks:               PASS
visual gate:               PASS
```

The final Architecture-77 run used a pre-existing detached certification
worktree, not a newly-created directory. The worktree was clean and matched the
certified A11 HEAD/TREE exactly, and pytest used a fresh external basetemp with
cache disabled.

Visual certification covered empty, populated, filtered/minimum-size, and
no-match states. Search/source filtering preserves A10 order, identifiers and
hashes remain selectable, and the read-only/not-authority scope remains visible.

Independent final GitHub review found 9 expected changed files, 13 commits ahead
and 0 behind the exact base. No new runtime I/O, discovery, production O2,
C1/C2/C3, Credential Manager, provider/broker call, Task Scheduler, paper/live
execution, settlement, recovery, durable write, or path/receipt disclosure was
introduced. Filter changes and Evidence navigation cause zero service rereads.

GUI-A11 is integrated and closed through PR #15.

```text
accepted PR head:     d092f99e3aefb5823d123271ffa5963245e8ad1e
merge commit:         65f4edeee9ba4c35121d19e8930af49353049dbf
resulting merge tree: 74932fdad0d003b057afb6c46c858cee1cc23019
PR-head -> merge:     no file differences
```

The authoritative executable/source certification remains
`2aba51e544d1cf356730ad8bc01a7b909af515ce` /
`3dd12a94615748d05df784cbaa8ac49576f9d032`.

Final PR review confirmed the Evidence Explorer is pure presentation behavior
over accepted A10 state, filter changes and Evidence navigation cause zero
service rereads, A10 ordering is preserved, and no runtime I/O, discovery,
production authority, credential, scheduler, provider/broker, execution,
settlement, recovery, durable-write, or path/receipt-disclosure path was added.

Continue automatically with GUI-A12 read-only System/Evidence
cross-navigation derived only from already-rendered bounded identities. D8-A
remains separate and protected; D8-B remains protected and unauthorized.

## GUI-A12 read-only System / Evidence cross-navigation — source certified

GUI-A12 is source-certified on:

```text
branch: feature/gui-a12-system-evidence-cross-navigation
base develop: 360063ddcfce58056c2a7ab1499c9d5d13ae8107
HEAD: dc79e74164345d97163a8a16a8c540cc870778c0
TREE: 2ee3fde29ea9489e8ae5efbece5bd89371396c11
```

Architecture 119 keeps A12 inside accepted A9-A11 presentation boundaries.
System audit entries map through a closed source vocabulary into immutable
`EvidenceNavigationTarget` values containing only source + identifier.
MainWindow performs the page coordination and reuses the existing Evidence
Explorer controls; no service reread or artifact I/O occurs.

Accepted final evidence:

```text
focused A12:                   30 passed
complete GUI regression:     333 passed
broad non-Architecture-77: 5,872 passed, 17 skipped
Architecture-77:             758 passed
combined:                  6,630 passed, 17 skipped
Ruff check:                PASS
Ruff format --check:       PASS (583 files)
diff checks:               PASS
visual gate:               PASS
```

Visual certification covered the populated System page plus Research and Market
Data System -> Evidence transitions at 920x620. Exact source/identifier filters
are visibly applied and the resulting Evidence card remains readable/selectable.

Independent final GitHub review found 9 expected changed files, 8 commits ahead
and 0 behind the exact base. Exact-navigation semantics are preserved with a
closed System-source map and exact source/identifier equality. Identifiers over
the accepted A11 200-character search bound fail closed rather than truncating.

No new runtime I/O, discovery, production O2, C1/C2/C3, Credential Manager,
provider/broker call, Task Scheduler, paper/live execution, settlement,
recovery, durable write, or path/receipt disclosure was introduced.
Cross-navigation causes zero service rereads.

GUI-A12 is integrated and closed through PR #16.

```text
accepted PR head:     9123ffee3f48f73cc791de92ae9f90385184fab1
merge commit:         ae0d34c12e6b1e0633b20c6997afa7769b05ad11
resulting merge tree: 59f8d6950272bd90c902b3a35495835995fe465b
PR-head -> merge:     no file differences
```

The authoritative executable/source certification remains
`dc79e74164345d97163a8a16a8c540cc870778c0` /
`2ee3fde29ea9489e8ae5efbece5bd89371396c11`.

Final PR review confirmed A12 is presentation-only page coordination over
already-acquired state, uses a closed System -> Evidence source map and exact
identifier equality, fails closed for unsupported/overlong identities, causes
zero service rereads, and adds no runtime I/O, discovery, authority, credential,
scheduler, provider/broker, execution, settlement, recovery, durable-write, or
path/receipt-disclosure path.

Continue automatically with GUI-A13 read-only Evidence -> Source Page
navigation using only already-acquired presentation state. D8-A remains separate
and protected; D8-B remains protected and unauthorized.

## GUI-A13 read-only Evidence -> Source Page navigation — source certified

GUI-A13 is source-certified on:

```text
branch: feature/gui-a13-evidence-source-navigation
base develop: 9f0f8e01e47c950972d355d42017fc0d08dd0377
HEAD: df1c2536aef918edbe1dda987904d6040e022ab4
TREE: a6cad1cdfff770483178e3f2b2bdabfcad279f57
```

Architecture 120 keeps A13 entirely inside accepted GUI presentation
boundaries. One immutable `EvidenceSourcePageTarget` maps an existing
`EvidenceTimelineEntry.source` through a closed enum to the existing Research,
Paper, Paper Account, Market Data, or Operations page. The target retains no
identifier/hash/path/runtime object and MainWindow performs only the existing
presentation-only page selection.

Accepted final evidence:

```text
focused A13:                   34 passed
complete GUI regression:     340 passed
broad non-Architecture-77: 5,879 passed, 17 skipped
Architecture-77 clean:       758 passed
combined:                  6,637 passed, 17 skipped
Ruff check:                PASS
Ruff format --check:       PASS (585 files)
diff checks:               PASS
visual gate:               PASS
```

Visual certification covered a populated Evidence view at 920x620 and
Research/Market Data source-page navigation. The destination pages are the
already-rendered states; A13 does not promise exact-row selection or reacquire
an artifact. The Research page's existing report-path display is pre-existing
destination behavior and is not copied into Evidence state by A13.

Independent final GitHub review found 8 expected changed files, 4 commits ahead
and 0 behind the exact base. Every accepted Evidence source maps to exactly one
closed destination, mismatched targets fail explicitly, and source navigation
causes zero service rereads. Existing A11 filtering and A12 exact
System -> Evidence behavior remain green.

No new runtime I/O, discovery, production O2, C1/C2/C3, Credential Manager,
provider/broker call, Task Scheduler, paper/live execution, settlement,
recovery, durable write, or new path/receipt disclosure was introduced.

GUI-A13 is integrated and closed through PR #17.

```text
accepted PR head:     e24fd8ba7dda3020786b320c988d7c3508199412
merge commit:         12cd178ad7efbe989863587669dd7c00c509b679
resulting merge tree: fd2e64d0bcc46cefd3b5a1652d6d1a6a4ab45acd
PR-head -> merge:     no file differences
```

The authoritative executable/source certification remains
`df1c2536aef918edbe1dda987904d6040e022ab4` /
`a6cad1cdfff770483178e3f2b2bdabfcad279f57`.

Final PR review confirmed A13 is presentation-only page coordination over
already-acquired state, uses a closed Evidence-source -> existing-page mapping,
causes zero service rereads, preserves A11 filtering and A12 exact targeting,
and adds no runtime I/O, discovery, authority, credential, scheduler,
provider/broker, execution, settlement, recovery, durable-write, or new
path/receipt-disclosure path.

Pause the GUI track after GUI-A13 and return to the primary PD4 operational
track. GUI-A14 remains a future bounded read-only presentation candidate.

Next: obtain fresh read-only post-D5 evidence for the 2026-09-21 execution
session, then review D8-A eligibility. Do not invoke D8-A merely because the
wall-clock time is after the 01:30 Pacific D5 wake; first prove the wake/capture
completed, current-C1 selected C3(2026-09-21) exists, the finalized decision is
still exact, the Trading principal / approved production runtime are correct,
and all eight effect gates remain false. D8-A is read-only but still a protected
operational checkpoint. D8-B remains protected and unauthorized.

## D8-A blocked-startup diagnostic source checkpoint — 2026-09-22

After the preceding operational transition, one protected D8-A read-only run
reconstructed completed session `2026-09-21`, decision
`f2188b5e-e6a4-5398-be41-8867d9268355`, decision selected snapshot
`680b260f-08c9-5923-87bb-b5f0a4701380`, execution selected snapshot
`bf0ca2a7-1236-5240-9b1e-6c31cf2388ed`, final plan
`29c880dc-f10e-566c-a6e1-e3d73fa04c69`, and account predecessor
`ed4640e5-0630-525d-b916-d50e31e3ba2a`. PD4-C then returned `BLOCKED`.
All eight gates remained closed and `real_effect_performed=false`; no
invocation/application/operation/terminal identity was surfaced.

The source-only diagnostic checkpoint uses
`F:\AI\worktrees\ai-trading-bot-d8a-blocked-diagnostics`, branch
`feature/pd4-d8a-blocked-diagnostics`, starting HEAD
`749aa0082bd6a8e5064415403e530dc4c70f04f2` / tree
`38ae0f8ff96094af59ad951a0eb0445380c3f4d1`. Local and remote `origin/develop`
matched that starting HEAD, and the initial index/worktree were clean.

### Bounded PD4-C BLOCKED branch inventory

Every returned BLOCKED result has diagnostic `QUALIFICATION_BLOCKED`. In the
table, omitted fields are `None`; M means `mutex_acquisition_state`, S means
`storage_classification`, and O/D mean `operation_classification` and
`operation_diagnostic`. These are existing fields, not new branch codes.

| Existing return path | Existing additional evidence |
| --- | --- |
| Pre-lock recovery qualification is BLOCKED | None |
| Pre-lock recovery status is neither recovery-required nor no-recovery-required | None (defensive branch) |
| Pre-lock recovery/account identity mismatch | None |
| Recovery-path mutex is not OWNED or has the wrong account | M only |
| Held recovery requalification differs from pre-lock recovery | M only |
| Final recovery requalification differs from held recovery | M only |
| Healthy-path mutex is not OWNED or has the wrong account | M only |
| Post-lock recovery result has wrong type, status, or account | M only |
| Post-lock account identity differs from pre-lock account | M only |
| Invocation storage has wrong type/expected ID or unsafe classification | M and S when the storage result has the exact expected type; account/snapshot/invocation IDs |
| Initial A67 inspection has wrong type, IDs, classification, or diagnostic | M, S, O/D when inspection has the exact expected type; account/snapshot/invocation/operation/application/terminal IDs |
| Final account evidence differs from post-lock evidence | M, S, initial O/D; the same bounded IDs |
| Final A67 inspection differs or is unsafe | M, S, final O/D when exact typed; the same bounded IDs |
| Any Exception caught by `_qualify_startup`, including validation, replay, reader, admission, incomplete reconciliation, revalidation, result construction, or scope-exit failure | None; existing evidence is discarded by the existing catch |

The verified-plan wrapper's authority/plan/input validation occurs before
`_qualify_startup`; failures there raise to D8-A's existing generic BLOCKED
catch and yield no startup result. BaseException outside Exception is not
converted into a startup BLOCKED result. An exact inspection with no first
diagnostic would also fall through the existing generic exception catch.

The five surfaced enums distinguish available mutex, invocation-storage, and
A67 diagnostic classes. They cannot uniquely identify every return site:
generic early/caught failures collapse together, OWNED-only failures collapse
together, and some final account/operation drift shares existing safe enum
values. The observed production result cannot be retrospectively assigned to
one branch. No authority/mutex/recovery/ordering/effect semantic change is
needed for this pass-through; deeper discrimination would require separate
review and is outside this checkpoint.

### Implementation and review boundary

`SettlementQualificationResult` adds exact-type-checked optional
`startup_diagnostic`, `startup_storage_classification`,
`startup_operation_classification`, `startup_operation_diagnostic`, and
`startup_mutex_acquisition_state`. D8-A copies those fields from the already
validated PD4-C result after the existing final authority/gate checks. No
classification or identity changes. The CLI already serializes these StrEnum
values and None deterministically, so its source and zero-argument contract
remain unchanged. No extra production reader, I/O, discovery, credential,
capability, mutation, recovery, provider/broker call, or scheduler action is
introduced.

Focused verification: **118 passed** across the D8-A runtime, PD4-C startup,
and D8-A CLI modules with a fresh external basetemp and cache disabled. Tests
cover full/partial diagnostic pass-through, unchanged classifications/IDs and
dependency call counts, closed gates/no effects, safe JSON, and rejection of
raw or forged diagnostic data. Broad and Architecture-77 certification have
not been run for this checkpoint.

After an import-format correction, the CLI module alone passed again:
**10 passed**. Focused Ruff check and format checks passed for all three
changed Python files; `git diff --check` passed.

Next action: ChatGPT exact-commit/diff review, followed by final local
certification of the reviewed tree before considering a separately approved
D8-A diagnostic rerun. Do not infer execution readiness from diagnostic
fields. D8-A was not rerun during this task; D8-B remains unauthorized.

## D8-A blocked-startup diagnostic source certification accepted — 2026-09-22

ChatGPT exact-diff review accepted the diagnostic pass-through and then required
one narrow result-contract hardening correction. The final accepted
executable/source identity is:

```text
HEAD: 4aa2fb05331f34407ec2f9a12cf662abe17c08d6
TREE: aacedc5a571d3cf7b08f0d945c83648db4948f58
```

Chronology:

```text
bfeb0c9bda3b38803c7bc2474d7a12afb744d64c
  preserve bounded D8-A startup diagnostics

4aa2fb05331f34407ec2f9a12cf662abe17c08d6
  enforce D8-A startup result contract mapping
```

Final accepted certification of that exact executable/source tree:

```text
broad non-Architecture-77:      5,975 passed, 17 skipped in 574.72s
Architecture-77 clean harness:    713 passed in 978.23s
combined:                       6,688 passed, 17 skipped
Ruff check:                     PASS
Ruff format --check:            PASS (548 files)
git diff --check:               PASS
feature worktree:               clean, exact certified HEAD/TREE
Architecture-77 harness:        clean, detached, exact certified HEAD/TREE
pytest basetemps:               fresh external paths, cache disabled
```

Accepted contract:

- D8-A surfaces only the five already-sanitized PD4-C startup enums:
  diagnostic, invocation-storage classification, operation classification,
  operation diagnostic, and mutex acquisition state.
- `SettlementQualificationResult` requires the exact startup-status ->
  top-level classification/diagnostic mapping.
- No startup diagnostic evidence may exist without `startup_status`.
- Any surfaced startup result requires `all_eight_gates_closed=True`.
- Generic outer D8-A `BLOCKED` with no startup result remains valid.
- Partial PD4-C `BLOCKED` storage/operation/mutex evidence remains valid.
- The CLI remains deterministic, zero-semantic-argument, sanitized, and
  non-authorizing.

No PD4-C qualification, authority, identity, gate, mutex, ordering, recovery,
execution, provider/broker, scheduler, or effect semantics changed. No new
production reader, filesystem discovery, credential/capability surface, C1 raw
authority, path, handle, or mutation capability was introduced.

The diagnostic fields distinguish existing evidence classes but do not uniquely
identify every PD4-C `BLOCKED` return site. Generic early/caught failures and
several mutex-owned failures remain intentionally indistinguishable. Therefore
the cause of the earlier production `BLOCKED` result cannot be inferred
retrospectively.

Operational state remains:

```text
D8-A diagnostic source             SOURCE CERTIFIED
D8-A production diagnostic rerun   NOT AUTHORIZED
D8-B                               NOT AUTHORIZED
D9-A                               NOT APPLICABLE YET
REAL EFFECT                        FALSE
ALL 8 GATES                        CLOSED for the prior protected D8-A observation
```

This closeout is documentation-only and does not change the accepted
executable/source identity. A fresh production D8-A diagnostic invocation
remains a separate protected operator approval after integration/source
preflight.

Next: ChatGPT exact review of this docs-only closeout, then merge-readiness
review of `feature/pd4-d8a-blocked-diagnostics` against `develop`. Stop at
the merge approval boundary.

## D8-A blocked-startup diagnostics integration closeout — PR #18

PR #18 (`Preserve bounded D8-A startup diagnostics`) was reviewed and merged
into `develop` after final source certification.

```text
base develop:          749aa0082bd6a8e5064415403e530dc4c70f04f2
accepted PR head:      9aa7487b6291b24ba2c95f54e63650dc901f832a
merge commit:          cc6a4cc919af925a57d093a7fd3007ea877a2231
resulting merge tree:  3d2379fe56ee31891adbadfb6a981fc7d63cd0ea
PR-head -> merge files: none
```

The PR contained exactly five expected files: the D8-A settlement runtime, its
runtime and CLI tests, `docs/PROJECT_STATUS.md`, and this handoff. Deep review
confirmed that the implementation only forwards existing sanitized PD4-C enum
evidence, preserves the exact startup-status/classification/diagnostic
contract, adds no extra reader or call, and changes no mutex, recovery,
authority, ordering, gate, or effect semantics. The CLI remains
zero-semantic-argument and non-authorizing.

PR review state at merge:

```text
mergeable:              true
review submissions:     none
review comments:        none
unresolved threads:     none
PR-head workflow runs:  none
synthetic merge diff:   no files relative to PR head
```

The authoritative executable/source certification remains:

```text
HEAD: 4aa2fb05331f34407ec2f9a12cf662abe17c08d6
TREE: aacedc5a571d3cf7b08f0d945c83648db4948f58
broad: 5,975 passed, 17 skipped
Architecture-77: 713 passed
combined: 6,688 passed, 17 skipped
Ruff / format / diff: PASS
```

The docs-only branch closeout and history-preserving merge do not alter that
executable/source identity and therefore do not require another broad suite.

Current operational state:

```text
D8-A diagnostic source             INTEGRATED / SOURCE CERTIFIED
D8-A production diagnostic rerun   NOT AUTHORIZED
D8-B                               NOT AUTHORIZED
D9-A                               NOT APPLICABLE YET
```

Next checkpoint: prepare and verify an isolated production qualification
checkout/runtime for this integrated diagnostic source, including exact source
identity and Trading-principal/runtime preflight. Do not invoke D8-A during that
preparation. The diagnostic rerun remains a separate protected operator
approval.
