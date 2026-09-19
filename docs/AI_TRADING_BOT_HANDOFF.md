# AI Trading Bot — Project Development Roadmap & Handoff

**Repository:** `callmedraken/ai-trading-bot`  
**Integration branch:** `develop`  
**Armed D5 branch:** `feature/personal-desktop-paper-runtime`  
**D7 certified branch:** `feature/pd4-unattended-decision-publication`  
**D8/D9 certified branch:** `feature/pd4-unattended-settlement`  
**Armed D5 worktree:** `F:\AI\worktrees\ai-trading-bot-personal-desktop`  
**D7 worktree:** `F:\AI\worktrees\ai-trading-bot-decision-publication`  
**D8/D9 worktree:** `F:\AI\worktrees\ai-trading-bot-unattended-settlement`  
**Production/live trading:** NO-GO

> This Git-tracked handoff is the canonical cross-chat resume document. Uploaded
> copies are mirrors. Prove worktree, branch, HEAD, tree, origin, and clean state
> before acting. Keep the armed D5, certified D7, and certified D8/D9 source
> boundaries stable; use a separate branch/worktree for unrelated parallel
> product development.

## Parallel operator-observability checkpoint

The isolated side-project branch is:

```text
branch: feature/pd4-operator-observability
worktree: F:\AI\worktrees\ai-trading-bot-operator-observability
```

O1 is accepted:

```text
HEAD  ee1f44022340563f94f334f897a5e88859f7c6c7
TREE  76f98eb64a3205a88dcd86a2c541feaaea9939fa
16 focused tests passed
Ruff check/format PASS
diff checks PASS
worktree CLEAN
```

O1 contains only Qt-free immutable presentation models/adapters and focused
tests. It performs no production I/O and changes no authority or effect gate.

O2 source is accepted:

```text
HEAD  70672c65c7ecf0923516da7c2b57934dc950dbc8
TREE  762dc13000f435c58f31c9750c0cd22aac582840
32 focused O1+O2 tests passed
Ruff check/format PASS
diff checks PASS
worktree CLEAN
```

O2 provides one zero-semantic-argument source-checkout operator snapshot command
for genuine non-admin `Trading`. It validates/reads C1, effects-closed G6
status, selected C3/history, Paper-v2 account/operation state, and all eight gate
states. It does not call an effectful boundary, alter Task Scheduler, publish
D7, settle D8, recover receipts, provision storage, or submit broker/live
orders.

Next checkpoint: run the accepted O2 command once under the real Trading
principal and preserve its sanitized JSON evidence.

The observability branch remains separate while the protected natural D5 -> D7
-> D8/D9 production sequence is validated. After the first accepted unattended
end-to-end core cycle, merge the accepted core forward into observability,
reverify the combined tree, then merge to `develop` only with explicit
operator approval.

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

## 2. Current repository and source provenance

Integration/product baselines:

```text
integration develop baseline:
bd88ee966bff455f9fc897d6cfdfafdd807f27e2

Architecture-94 P2 product base:
a810122a96b6fc90da25d71eede8da64b7272c98
```

Historical PD4 Architecture-110 source-foundation certification:

```text
HEAD 248cd8de6a3539aab21d5719d96cb7ff1aa0d14c
TREE 5e867f1bfc6d945ad67f6c56be252b534645aeb2
5588 passed, 17 skipped in 1519.25s
```

Armed Architecture-111/112 D5 capture-warm-up source:

```text
branch feature/personal-desktop-paper-runtime
HEAD   8c2af5801cbc8f4df869b832a3b78b1eaa2f8996
TREE   f0591e966463c7e1e66dc00ad76fd895500a076f
```

Do not alter that armed branch merely to continue development.

D6/D7 decision-publication source certification:

```text
branch feature/pd4-unattended-decision-publication
certified source HEAD 3dfa9e2cab372f8cb034b90256ed3fba9da6c878
certified source TREE bb1de2e7c2933ba3a777523f2a0e2feee5fa8c39
pytest 6302 passed, 17 skipped in 1571.33s
post-certification docs tip 489b96a97d36fd28822142db9a69f0f0dd2d3d72
```

D8/D9 settlement source certification:

```text
branch feature/pd4-unattended-settlement
base 489b96a97d36fd28822142db9a69f0f0dd2d3d72
worktree F:\AI\worktrees\ai-trading-bot-unattended-settlement

accepted D8-A/R1 HEAD 170b50743458c8c973d472476b9e7abf140b6b1d
accepted D8-A/R1 TREE b2a202faf45bf61d5e3c1043c69a6cafcb00b6e3

accepted D8-B/R1 HEAD 260d80f60db9acfd352b1bc89ff963fc2a590a38
accepted D8-B/R1 TREE bc4fb96d2ecb30e607262de2c0b268510bd43835

accepted D9-A / certified final source HEAD
0df4ccb97a750e5727ef65dae7a365a3c7355254

certified final source TREE
f6c27fcff1a6cec839d8f6ec395d658dbbbbe36c
```

Certification record:

```text
docs/validation/pd4-d9-settlement-source-certification.md
```

Docs-only commits after `0df4ccb...` do not alter the certified source boundary.

Development interpreter:

```text
F:\AI\ai-trading-bot\.venv\Scripts\python.exe
```

Production interpreter:

```text
F:\AITradingBot\runtime\python.exe
```

Before bounded local tasks:

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

Controlled pytest on John's Windows development account uses a fresh external
basetemp:

```powershell
$BaseTemp = "F:\AI\temp\pytest\<purpose>-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Force 'F:\AI\temp\pytest' | Out-Null
& $Python -m pytest ... --basetemp="$BaseTemp" -p no:cacheprovider
```

Do not globally alter `TEMP` or `TMP`.

Architecture-77 process-rendezvous tests are a special case: they intentionally
use a fixed repository-local namespace under
`.pytest_cache/ai-trading-bot-lifecycle-arbiters-v1` so independently spawned
processes rendezvous on the same lock path. Do not rewrite that contract to
follow `--basetemp` merely to avoid a local ACL condition.

During D9-B, the settlement worktree's parent `.pytest_cache` was inaccessible
to the John development principal. The source was not changed and that cache was
not deleted, ACL-reset, taken over, or redirected. The already validated split
certification pattern was used instead: broad nonlegacy tests from the D9
worktree plus byte-identical legacy Architecture-77 tests from a clean
integration harness while imports were proven to resolve from D9 source.

Source-checkout operator CLIs that must run independently of cwd or ambient
package resolution use a reviewed `scripts/` launcher that explicitly selects
the checkout's `src`.

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

Model choice never transfers architecture or acceptance authority. No subagents
unless explicitly requested.

Use focused tests during intermediate implementation. Run one broad
certification only after the exact source tree is declared final for the
milestone. Exact-file stage only; never `git add .` or `git add -A`. Preserve
unrelated generated/untracked artifacts and historical permission-warning test
folders.

No amend/rebase/merge/force-push/PR-metadata/review-thread changes without
explicit approval.

## 5. Standing authorization model

Automatically continue to the next best **safe, source-only/read-only** scoped
checkpoint when the preceding reviewed checkpoint passes. Stop at protected
effect boundaries or genuine architecture ambiguity.

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

Historical manual C3 selected call #6:

```text
selection_id: 36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280
snapshot_id: eba46838-44ae-5bec-97bf-98c6639ae6a7
SHA-256: 31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
length: 1291
captured_at: 2026-08-29T09:46:43.769105+00:00
```

First unattended D3/D4 selected session `2026-09-11`:

```text
selection_id: 7c42363d-4785-5823-be7e-93bf94426eac
snapshot_id:  8ddc60ed-3940-5379-a868-b46b9b7c95af
SHA-256:      704c1d0966acec3489a355fd6ef5369439b07e0e0a8e15c5f68cc2d847aa607f
length:       1289
```

## 7. Architecture 94 product composition

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

Architecture 111 adds:

```text
selected current C3 close + C3-authoritative history + account predecessor
-> PreparedManualPaperStrategyDecision
-> durable pre-open decision intent (no future execution-session open)
-> later current-C1 selected C3 open for intended execution session
-> existing Architecture-94 final plan
-> existing PD4 / Architecture-67 Paper-v2 authority
```

Architecture 114 freezes the zero-argument production composition that consumes
that finalized decision only after its execution session has completed.

## 8. Paper-v2 deployment

Fixed production paths:

```text
final authority root: F:\AITradingBot\Paper-v2
A67 operation root:   F:\AITradingBot\Paper-v2\runtime
receipt parent:       F:\AITradingBot\Paper-v2\runtime\paper-operations
unattended invocation namespace:
                      F:\AITradingBot\Paper-v2\runtime\unattended-invocations
unattended decision namespace:
                      F:\AITradingBot\Paper-v2\runtime\unattended-decisions
```

Published Paper-v2 account:

```text
paper_account_id:   9415cd7b-bf36-5fba-bd58-a0f99119dc21
GENESIS checkpoint: 1832a2b5-8b63-501a-8f7d-f1722c32307b
starting cash:      Decimal("25000")
GENESIS as_of:      2026-08-29T09:46:43.769105+00:00
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

Retained failed v1 state:

```text
F:\AITradingBot\Paper                    ABSENT
F:\AITradingBot\.Paper.provisioning-v1  PRESENT / RETAINED / UNTOUCHED
```

Never rerun the v1 publisher or delete/repair/rename/migrate/reuse the retained
v1 staging tree as incidental cleanup.

## 9. Historical milestones

```text
PD1  Paper-v2 authority                              COMPLETE
PD2  reliable supervised manual paper cycle         COMPLETE
PD3  supervised crash/recovery validation           COMPLETE
PD4  Architecture-110 source foundation             COMPLETE
```

Important certifications:

```text
PD2: 5146 passed, 17 skipped
PD3: 5285 passed, 17 skipped
PD4 Architecture-110:
  HEAD 248cd8de6a3539aab21d5719d96cb7ff1aa0d14c
  TREE 5e867f1bfc6d945ad67f6c56be252b534645aeb2
  5588 passed, 17 skipped
```

Historical completion records remain historical; later extensions do not
rewrite them.

## 10. Architecture 111 — unattended daily-cycle authority

Frozen rules:

- scheduler is an untrusted wake only;
- XNYS regular open is 09:30 America/New_York;
- selected-C3 session-indexed read authority is production market-data truth;
- production rolling history must be C3-selected and consecutive;
- MA short=3/long=5 requires six consecutive selected C3 sessions before the
  first fully C3-backed unattended decision;
- the pre-open decision contains no execution-session open;
- late wake at/after intended open cannot manufacture a missing decision;
- `MISSED_DECISION_DEADLINE` and `SESSION_GAP` fail closed;
- no automatic multi-session catch-up;
- market-data capture and decision publication use separate effect gates.

## 11. Architecture 112 / D5 — capture-only warm-up ACTIVE at 3/6

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
blind scheduler retry. D5 never opens decision-publication or Paper-v2 effect
gates.

Accepted scheduler deployment evidence:

```text
D2 predecessor XML SHA-256:
da851985d9bfb04c65a83cb64b5441a2f7fd50391924a844749e365ee282d6ec

D5 action:
-I F:\AI\worktrees\ai-trading-bot-personal-desktop\scripts\run_personal_desktop_unattended_capture_warmup.py

D5 task XML SHA-256:
8005373fad791c85776b4a35b662d46e06fec4ea40ac9ebfead9f413715da457
```

First scheduled D5 capture for `2026-09-14`:

```text
selection_id:           dea50bc9-95b4-5f63-ac40-a7353133be53
attempt_id:             70f5f586-a05b-56c5-adde-bfa5d027864b
snapshot_id:            b3737822-35ee-5238-a87f-401b4597df46
artifact SHA-256:       db16bd7d6edda1709aeea64158f8751c02714ed45e9c6441935640e43ffa5487
artifact identity SHA:  bfd131801558be6cbbed96b1e176c428b98df4e9c6dcccffb77c74acdc4870ba
terminal:               SUCCEEDED
provider disposition:   CONFIRMED
```

Natural September-16 scheduler wake captured `2026-09-15`:

```text
selection_id:           2e633276-abd1-55f0-94a5-f6cca5b56e5e
session_id:             e0d23ea2-2efd-5f79-9ed3-a7d0298f18cc
attempt_id:             3866c94b-5a38-5072-a1d4-eb72b4da6617
terminal_id:            954a78f1-81ae-5e66-b61b-b8b7920da98c
snapshot_id:            88edd831-0d70-5303-a3c6-b81184f1b0d9
artifact SHA-256:       7b84b84dc36a239cabc651fe5aca8be9a4e1a73b6f1294e67c795fa114bf42bd
artifact identity SHA:  ecb64c2aaa1ad469fc3cfa2fef12cd61063feef69352923ff91d8cea2721c161
terminal:               SUCCEEDED
provider disposition:   CONFIRMED
```

Current authoritative history through completed session `2026-09-15`:

```text
required:
2026-09-08
2026-09-09
2026-09-10
2026-09-11
2026-09-14
2026-09-15

selected:
2026-09-11
2026-09-14
2026-09-15

selected_count = 3/6
classification = WARMING_UP
```

Current G6 read-only state:

```text
completed session = 2026-09-15
G6 = WARMING_UP
market-data classification = NO_NEW_COMPLETED_SESSION
selected snapshot = 88edd831-0d70-5303-a3c6-b81184f1b0d9
real_effect_performed = false
all eight gates false before and after
```

Scheduler health observed read-only on September 16:

```text
state = Ready
last run = 2026-09-16 01:30:30
last result = 0x00000000
next run = 2026-09-17 01:30:30
principal = Trading
run level = Limited
restart count = 0
```

Manual review of the selected C3 artifacts showed one raw SPY OHLCV bar per
selected session plus provider/capture/integrity evidence. The read-only review
performed no provider call and no database mutation.

Do not manually start the scheduler, call G5, run the D5 warm-up launcher, or
backfill missing older sessions. D5 becomes complete only when the rolling
six-session selected suffix becomes ready naturally.

## 12. Architecture 113 / D6-D7 — decision-publication source CERTIFIED

```text
D6 HEAD fb00e9898c2e5cdd3db27cd91c393f5994c7cca9
D6 TREE eef138bb3ed144d153ae60193aaacdcb7584c513
6007 passed, 17 skipped

D7 final source HEAD 3dfa9e2cab372f8cb034b90256ed3fba9da6c878
D7 final source TREE bb1de2e7c2933ba3a777523f2a0e2feee5fa8c39
6302 passed, 17 skipped in 1571.33s
record: docs/validation/pd4-d7-read-only-source-certification.md
```

Production D7 state:

```text
D7-A real-host qualification  NOT RUN / waiting for natural 6/6 READY
D7-B provisioning             PROTECTED / conditional only if required
D7-C first publication        PROTECTED / UNAUTHORIZED
D7-D production reconciliation NOT RUN
```

A G6 or D7-A result is diagnostic only and cannot be reused as D7-C publication
authority. D7-C independently rederives production truth.

## 13. Architecture 114 / D8-D9 — source CERTIFIED

D8-A/R1 accepted:

```text
HEAD 170b50743458c8c973d472476b9e7abf140b6b1d
TREE b2a202faf45bf61d5e3c1043c69a6cafcb00b6e3
233 focused tests passed
production qualification NOT RUN
```

D8-B/R1 accepted / effects closed:

```text
HEAD 260d80f60db9acfd352b1bc89ff963fc2a590a38
TREE bc4fb96d2ecb30e607262de2c0b268510bd43835
134 focused tests passed
production settlement NOT RUN
```

D9-A independent read-only reconciliation accepted:

```text
HEAD 0df4ccb97a750e5727ef65dae7a365a3c7355254
TREE f6c27fcff1a6cec839d8f6ec395d658dbbbbe36c
422 focused tests passed
production reconciliation NOT RUN
```

D9-A independently reconstructs current settlement truth and classifies only:

```text
RECONCILED
NOT_APPLIED
RECEIPT_RECOVERY_REQUIRED
BLOCKED
```

It remains structurally read-only and does not import D8-A/D8-B authority as a
shortcut.

Final D8/D9 source certification:

```text
certified HEAD 0df4ccb97a750e5727ef65dae7a365a3c7355254
certified TREE f6c27fcff1a6cec839d8f6ec395d658dbbbbe36c

broad nonlegacy:         5709 passed
Architecture-77 legacy:  758 passed
combined:                6467 passed, 17 skipped
failures/errors:         0

Ruff check PASS
Ruff format --check PASS (547 files)
git diff --check PASS
git diff --cached --check PASS
```

The initial monolithic D9-B run was environment-invalid only for the fixed
Architecture-77 repo-local arbiter namespace because the settlement worktree's
`.pytest_cache` was inaccessible to John. No source change was required. The
accepted replacement certification used the clean integration harness for only
the byte-identical legacy tests while proving all relevant imports came from the
D9 source tree.

Certification record:

```text
docs/validation/pd4-d9-settlement-source-certification.md
```

No real D8/D9 production invocation has occurred.

Protected future production sequence:

```text
accepted D7 publication + D7-D reconciliation
-> intended execution session E completes
-> exact selected C3(E)
-> fresh D8-A Trading read-only qualification
-> explicit approval for one D8-B settlement invocation
-> fresh-process D9-A durable reconciliation
```

A successful D8 return is not acceptance authority; D9 durable evidence is.
Receipt recovery remains separate and closed.

## 14. Roadmap

```text
PD0   personal-desktop profile adoption                     COMPLETE
PD1   personal-desktop paper-account authority v2           COMPLETE
PD2   reliable supervised manual paper cycle                COMPLETE
PD3   supervised crash/recovery validation                  COMPLETE
PD4   unattended simulated-paper
  Architecture-110 source foundation                       COMPLETE
  Architecture-111 daily-cycle source/design               ACCEPTED
  D3/D4 first unattended C3 acceptance                     ACCEPTED
  Architecture-112 / D5 capture-only warm-up               ACTIVE (3/6; WARMING_UP)
  Architecture-113 / D6-D7 source                          CERTIFIED
  D7-A production qualification                            WAITING FOR NATURAL 6/6 READY
  D7-C first decision publication                          PROTECTED / UNAUTHORIZED
  Architecture-114 settlement contract                     ACCEPTED / SOURCE-ONLY
  D8-A settlement qualification source                     ACCEPTED
  D8-B settlement-only production source                   ACCEPTED / EFFECTS CLOSED
  D9-A independent reconciliation source                   ACCEPTED
  D9-B final D8/D9 source certification                    ACCEPTED
  D8-B first real unattended settlement                    FUTURE / PROTECTED
  D10 bounded unattended simulated-paper soak              FUTURE / PROTECTED
  operational unattended simulated-paper acceptance         NOT YET COMPLETE
PD5   broker-paper integration                              NOT STARTED
PD6   broker-paper soak / operational hardening             NOT STARTED
PD7   personal-desktop live-readiness                       NOT STARTED
PD8   tiny restricted live -> gradual maturity              NOT STARTED
```

Do not move to broker-paper merely because D5 market-data warm-up succeeds. The
critical path remains safe unattended data → safe unattended decision → safe
unattended Paper-v2 settlement → operational soak.

Safe parallel development while D5 warms belongs on a separate branch/worktree,
not the three operational/certified worktrees. A strong next source-only product
milestone is a read-only operator-observability surface over existing authority:
D5 warm-up/history, selected-market-data audit, effect-gate state, scheduler
health, Paper-v2 account/lineage, and D7/D8/D9 readiness. Presentation/GUI code
must never become alternate trading authority.

## 15. Effect gates and still-protected actions

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

Architecture 112 permits D5 to open only the process-local market-data gate
around exactly one G5 call. That does not authorize ad hoc manual provider calls
or retries.

Still protected/not authorized outside exact reviewed checkpoints:

```text
manual/ad hoc provider effects or retries outside D5
first real D7 decision publication
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

## 16. Resume procedure

1. Read `AGENTS.md`, `docs/PROJECT_STATUS.md`, this handoff,
   `docs/AI_DEVELOPMENT_WORKFLOW.md`, Architectures 110–114, the PD4
   source-foundation completion, the Architecture-111 daily-cycle plan, the D5
   plan, D7 certification record, Architecture-114 settlement plan, and D9
   certification record before new implementation.
2. Prove exact worktree/branch/HEAD/tree/origin/clean state before edits or
   operator work. Never self-correct a mismatch.
3. Treat PD1, PD2, PD3, Architecture-110 source foundation, Architectures
   111–114, D3/D4, D5-A/B/C, D7 source certification, D8-A/R1, D8-B/R1, D9-A,
   and D9-B source certification as established predecessors.
4. Preserve armed D5 source `8c2af580... / f0591e96...` while natural captures
   accumulate. Current accepted history is **3/6**, selected sessions
   `2026-09-11`, `2026-09-14`, and `2026-09-15`, classification `WARMING_UP`.
5. Do not manually capture/backfill/start the scheduler. The latest read-only
   scheduler evidence is healthy and the next normal wake follows the frozen
   01:30 Pacific schedule.
6. Preserve D7 certified source `3dfa9e2... / bb1de2e...`; wait for natural 6/6
   READY before protected D7 production qualification/publication.
7. Preserve D8/D9 certified source `0df4ccb... / f6c27fc...`. Docs-only branch
   tips after it do not change the source certification.
8. Do not run D8 production merely because source is certified. It requires an
   accepted D7 publication, completed intended execution session, exact selected
   C3(E), fresh D8-A, explicit approval for one D8-B effect, and fresh D9-A.
9. D10 operational soak remains future until the first unattended settlement
   sequence has actually been accepted.
10. Use a separate branch/worktree for safe parallel product work such as
    read-only operator observability; do not repurpose D5/D7/D8-D9 operational
    worktrees.
11. Stop before any real decision-publication, storage-provisioning, Paper-v2,
    recovery, scheduler, broker, or live effect unless explicitly authorized.
12. After each accepted checkpoint, review/update this handoff,
    `docs/PROJECT_STATUS.md`, and relevant validation/architecture records before
    treating the checkpoint as closed.
13. Always include the next recommended milestone/step in milestone and
    verification reports.

## 17. Definition of project success

The project is not complete merely when it can place trades. It succeeds when
the platform can research deterministically, acquire trusted data safely, apply
deterministic risk, interact safely with a brokerage, reconcile external
outcomes after failures/restarts, run unattended, fail closed when authority or
state is uncertain, expose durable evidence, operate under strict real-money
controls, recover predictably, remain understandable/stoppable by its operator,
and expose the reviewed system through a polished GUI without giving AI or
presentation code alternate authority paths.
