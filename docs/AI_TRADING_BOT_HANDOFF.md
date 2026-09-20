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

Next checkpoint: A8b Qt-free startup configuration plus composite service and
focused tests. Luna Extra High is the preferred bounded implementation route
once the contract is frozen; ChatGPT retains exact diff review and acceptance.

