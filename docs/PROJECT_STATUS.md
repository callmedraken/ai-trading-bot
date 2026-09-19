# Project Status and Roadmap

## Current observability checkpoint — 2026-09-19

O4 source is accepted at HEAD `2fab48301530a89df21391c047f848eb3fd97272`,
TREE `f8df06396a5203367bb9b0abdbcfd167bfa46d67`; operator-supplied verification:
266 focused tests passed, Ruff check/format PASS, both diff checks PASS, clean
worktree. See [O4 acceptance](validation/pd4-operator-observability-o4-acceptance.md).

Strategy explanation is read-only and uses the source-owned MA3/MA5 evaluator.
GUI output is non-authoritative for D7. D5 is READY 6/6 through 2026-09-18;
D7-A is accepted for candidate `f2188b5e-e6a4-5398-be41-8867d9268355`, execution
session 2026-09-21. Namespace PRESENT_VALID makes D7-B unnecessary. D7-C remains
protected and unauthorized; D8-B remains protected/not run. All eight gates
remain committed false. Earlier checkpoint descriptions below are historical
where superseded by this current state.

Bounded review found an inherited ambient-Decimal dependency in averages and
proposal-ID normalization. Identical inputs produced different IDs at different
precisions, including in pre-O4 source. Implementation stopped at the production
identity contract boundary; no source/test change was made. See the
[review escalation](validation/pd4-operator-observability-o4-review-escalation.md).
Fresh focused verification: 69 passed; Ruff check/format PASS (14 files).

Next safe milestone: Sol High review of the Decimal/identity compatibility
contract, then resume unfinished observability hardening/integration preparation.
No production work is authorized. O4 historical acceptance does not certify
ambient-context independence or combined-tree integration readiness.

This is the canonical high-level project status for AI Trading Bot. Detailed
subsystem contracts live under `docs/architecture/` and `docs/validation/`;
`docs/AI_TRADING_BOT_HANDOFF.md` is the canonical cross-chat resume document.

## D5 warm-up — 6/6 READY

Read-only Trading-principal evidence on 2026-09-19 established the exact current
six-session selected-C3 window:

```text
classification: READY
required:
  2026-09-11
  2026-09-14
  2026-09-15
  2026-09-16
  2026-09-17
  2026-09-18

selected:
  2026-09-11
  2026-09-14
  2026-09-15
  2026-09-16
  2026-09-17
  2026-09-18

selected_count: 6
target_count:   6
current session: 2026-09-18
current snapshot: 680b260f-08c9-5923-87bb-b5f0a4701380
```

All eight effect gates remained false. G5 reported
`NO_NEW_COMPLETED_SESSION`, confirming the Sep 18 C3 snapshot is already
durably selected. Do not backfill or force another capture.

The production critical path has therefore moved from waiting for D5 history to
repairing the read-only historical Paper-v2 configuration reconstruction
blocker before D7-A.

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

## Current branch/worktree roles

### Armed D5 production warm-up — frozen

```text
branch: feature/personal-desktop-paper-runtime
worktree: F:\AI\worktrees\ai-trading-bot-personal-desktop
accepted HEAD: 8c2af5801cbc8f4df869b832a3b78b1eaa2f8996
accepted TREE: f0591e966463c7e1e66dc00ad76fd895500a076f
```

Do not modify this armed worktree merely to continue development.

### D7 decision-publication source — certified/frozen

```text
branch: feature/pd4-unattended-decision-publication
worktree: F:\AI\worktrees\ai-trading-bot-decision-publication
certified source HEAD: 3dfa9e2cab372f8cb034b90256ed3fba9da6c878
certified source TREE: bb1de2e7c2933ba3a777523f2a0e2feee5fa8c39
post-certification docs tip: 489b96a97d36fd28822142db9a69f0f0dd2d3d72
```

Leave this source tree stable until the natural D5 six-session suffix is ready
and a protected D7 production checkpoint is explicitly entered.

### Operator observability — O2 source accepted / real-host read-only qualification next

```text
branch: feature/pd4-operator-observability
worktree: F:\AI\worktrees\ai-trading-bot-operator-observability
O1 accepted HEAD: ee1f44022340563f94f334f897a5e88859f7c6c7
O1 accepted TREE: 76f98eb64a3205a88dcd86a2c541feaaea9939fa
O2 accepted source HEAD: 70672c65c7ecf0923516da7c2b57934dc950dbc8
O2 accepted source TREE: 762dc13000f435c58f31c9750c0cd22aac582840
```

O1 provides immutable Qt-free view models and pure adapters over already
verified/read-only selected-C3 history and gate-state evidence.

O2 source is accepted: 32 focused O1+O2 tests passed; Ruff check/format and diff
checks passed; worktree clean. O2 adds a zero-semantic-argument Trading-principal
read-only operator snapshot command for effects-closed G6 state, selected C3
history, Paper-v2 account/lineage facts, and all eight effect gates. It remains
non-authoritative and does not modify the armed D5, certified D7, or certified
D8/D9 operational boundaries.

O2 real-host qualification now reaches the full sanitized snapshot. The Windows
CRLF portability defect in the frozen first-operation history seed was corrected
with an explicit text/eol=lf checkout contract plus an exact-byte regression
test; the seed artifact itself did not change.

Current real-host evidence: all eight gates false; C1 valid; G5
NO_NEW_COMPLETED_SESSION for 2026-09-18; selected-C3 history READY 6/6; Paper-v2
account read PASS with cash 25000, no positions, realized P&L 0; O2 reports
real_effect_performed=false. G6 still classifies BLOCKED downstream. Diagnose
the remaining G6 tail in order: finalized-decision discovery, authoritative
history binding, next-decision construction, then read-only publication
qualification.

### D8/D9 settlement source — certified/frozen source boundary

```text
branch: feature/pd4-unattended-settlement
worktree: F:\AI\worktrees\ai-trading-bot-unattended-settlement
base: 489b96a97d36fd28822142db9a69f0f0dd2d3d72

accepted D8-A/R1 HEAD: 170b50743458c8c973d472476b9e7abf140b6b1d
accepted D8-A/R1 TREE: b2a202faf45bf61d5e3c1043c69a6cafcb00b6e3

accepted D8-B/R1 HEAD: 260d80f60db9acfd352b1bc89ff963fc2a590a38
accepted D8-B/R1 TREE: bc4fb96d2ecb30e607262de2c0b268510bd43835

accepted D9-A / certified final source HEAD:
0df4ccb97a750e5727ef65dae7a365a3c7355254

certified final source TREE:
f6c27fcff1a6cec839d8f6ec395d658dbbbbe36c
```

Docs-only commits after `0df4ccb...` do not alter that certified source boundary.
The certification record is:

```text
docs/validation/pd4-d9-settlement-source-certification.md
```

## Mandatory personal-desktop security baseline

- steady-state trading runs under the dedicated non-admin `Trading` account;
- credentials stay outside source/plain config and use reviewed Windows-backed
  storage;
- paper is default; future live requires a separate explicit arming boundary;
- every executable order passes deterministic risk authority;
- strategy/optimizer/GUI/AI/scheduler/adapters cannot bypass risk;
- durable state outranks process-local assumptions;
- ambiguous provider/broker effects reconcile or fail closed rather than being
  blindly retried;
- source-governed runtime/config/state locations use practical least privilege;
- crash/restart, duplicate invocation, stale input, corruption/conflict, and
  receipt recovery fail closed unless exact reviewed authority is present.

Production identities remain:

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

## Architecture checkpoints

```text
Architecture 102  personal-desktop profile adoption
Architecture 103  Paper-v2 deployment/provisioning authority
Architecture 104  supervised A67 execution boundary
Architecture 105  first-mutation qualification
Architecture 106  first Paper-v2 execution preparation
Architecture 107  first Paper-v2 output authority hardening
Architecture 108  first Paper-v2 post-mutation reconciliation
Architecture 109  personal-desktop Paper-v2 receipt-recovery authority
Architecture 110  personal-desktop unattended Paper-v2 operation authority
Architecture 111  personal-desktop unattended daily-cycle authority
Architecture 112  personal-desktop capture-only warm-up authority
Architecture 113  personal-desktop unattended decision-publication authority
Architecture 114  personal-desktop unattended Paper-v2 settlement authority
```

## Architecture 94 product composition

Accepted product work:

```text
P1 pure strategy history / deterministic strategy plan
1028e60b99c27cef0994f40d6ce381392abfb0f8

P2 read-only selected-C3 snapshot authority
a810122a96b6fc90da25d71eede8da64b7272c98
```

Preserve the composition:

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

Architecture 111 adds the two-phase unattended path:

```text
selected current C3 close + C3-authoritative history + account predecessor
-> PreparedManualPaperStrategyDecision (pre-open; no execution-session open)
-> durable pre-open decision intent
-> later selected C3 open for intended execution session
-> existing Architecture-94 ManualPaperStrategyPlan
-> existing PD4 / Architecture-67 Paper-v2 reconciliation and settlement
```

## Paper-v2 production authority

Fixed paths:

```text
Paper-v2 root:       F:\AITradingBot\Paper-v2
A67 operation root: F:\AITradingBot\Paper-v2\runtime
receipt parent:     F:\AITradingBot\Paper-v2\runtime\paper-operations
unattended invocation namespace:
                    F:\AITradingBot\Paper-v2\runtime\unattended-invocations
unattended decision namespace:
                    F:\AITradingBot\Paper-v2\runtime\unattended-decisions
```

Published account:

```text
paper_account_id:   9415cd7b-bf36-5fba-bd58-a0f99119dc21
GENESIS checkpoint: 1832a2b5-8b63-501a-8f7d-f1722c32307b
starting cash:      Decimal("25000")
GENESIS as_of:      2026-08-29T09:46:43.769105+00:00
```

First durable Paper-v2 operation:

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

Never rerun the old v1 publisher or delete, repair, rename, migrate, or reuse
the retained v1 staging tree as incidental cleanup.

## Completed historical milestones

```text
PD1  personal-desktop Paper-v2 authority             COMPLETE
PD2  reliable supervised manual paper cycle          COMPLETE
PD3  supervised crash/recovery validation            COMPLETE
PD4  Architecture-110 unattended source foundation   COMPLETE
```

Historical completion records remain authoritative for the scope they certify.
Later operational extensions do not rewrite those historical records.

Important source certifications:

```text
PD2 final broad certification:
5146 passed, 17 skipped in 1505.92s

PD3 final broad certification:
5285 passed, 17 skipped in 1478.19s

PD4 Architecture-110 source-foundation certification:
HEAD 248cd8de6a3539aab21d5719d96cb7ff1aa0d14c
TREE 5e867f1bfc6d945ad67f6c56be252b534645aeb2
5588 passed, 17 skipped in 1519.25s
```

## PD4 unattended daily-cycle extension — Architecture 111

Key frozen rules:

- Task Scheduler is an untrusted wake-up source and supplies no semantic trading
  authority;
- version-1 regular open is 09:30 America/New_York;
- a decision targeting session `E` must be finalized strictly before
  `regular_open(E)`;
- the pre-open decision contains no `open(E)` or later market-data fact;
- after `E` completes, only a current-C1 selected C3 snapshot for `E` may bind
  its verified daily-bar open for settlement;
- C3-selected history, not the old offline seed, is production authority;
- current MA short=3/long=5 requires six consecutive selected C3 sessions before
  the first fully C3-backed decision;
- no automatic multi-session catch-up is authorized;
- an internal history gap is `SESSION_GAP`;
- unattended market-data capture and decision publication have separate
  closed-by-default source-owned gates.

## PD4-D5 capture-only warm-up — ACTIVE at 3/6

Architecture and validation plan:

```text
docs/architecture/112-personal-desktop-capture-only-warmup-authority.md
docs/validation/pd4-d5-capture-only-warmup-plan.md
```

D5-A/D5-B accepted scheduler evidence:

```text
D2 predecessor XML SHA-256:
da851985d9bfb04c65a83cb64b5441a2f7fd50391924a844749e365ee282d6ec

D5 launcher:
-I F:\AI\worktrees\ai-trading-bot-personal-desktop\scripts\run_personal_desktop_unattended_capture_warmup.py

D5 task XML SHA-256:
8005373fad791c85776b4a35b662d46e06fec4ea40ac9ebfead9f413715da457
```

Accepted first scheduled capture-only wake for session `2026-09-14`:

```text
terminal:               SUCCEEDED
provider disposition:   CONFIRMED
selection_id:           dea50bc9-95b4-5f63-ac40-a7353133be53
attempt_id:             70f5f586-a05b-56c5-adde-bfa5d027864b
snapshot_id:            b3737822-35ee-5238-a87f-401b4597df46
artifact SHA-256:       db16bd7d6edda1709aeea64158f8751c02714ed45e9c6441935640e43ffa5487
artifact identity SHA:  bfd131801558be6cbbed96b1e176c428b98df4e9c6dcccffb77c74acdc4870ba
account predecessor:    ed4640e5-0630-525d-b916-d50e31e3ba2a
```

The natural `2026-09-16 01:30:30` scheduler wake then successfully supplied the
selected C3 snapshot for session `2026-09-15`:

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

Current authoritative rolling window through completed session `2026-09-15`:

```text
required sessions:
2026-09-08
2026-09-09
2026-09-10
2026-09-11
2026-09-14
2026-09-15

selected sessions:
2026-09-11
2026-09-14
2026-09-15

selected_count = 3 / 6
classification = WARMING_UP
```

Current effects-closed G6 observation:

```text
completed session = 2026-09-15
G6 = WARMING_UP
market-data classification = NO_NEW_COMPLETED_SESSION
selected snapshot = 88edd831-0d70-5303-a3c6-b81184f1b0d9
real_effect_performed = false
all eight gates false before and after
```

Read-only scheduler inspection on `2026-09-16`:

```text
state: Ready
last run: 2026-09-16 01:30:30
last result: 0x00000000
next run: 2026-09-17 01:30:30
principal: Trading
run level: Limited
restart count: 0
```

The selected market data currently retained by the rolling history is one raw
SPY daily OHLCV bar per selected session. Manual review proved the P2 read path
performed no provider call and no database mutation.

Do **not** manually start the scheduler, call G5, run the D5 launcher, retry, or
backfill the missing older sessions. The six-session window must become ready
through natural selected captures.

## D6/D7 decision-publication source — CERTIFIED

```text
D6 certified HEAD: fb00e9898c2e5cdd3db27cd91c393f5994c7cca9
D6 certified TREE: eef138bb3ed144d153ae60193aaacdcb7584c513
D6 suite: 6007 passed, 17 skipped

D7-A accepted source HEAD: c72ca6c8665b62c0b8d4f735fc2261a513cb81d5
D7-A accepted source TREE: 3b05c68ff1487a1c7d5984a200ee9f20d7b92fca
focused: 910 passed

D7 final certified source HEAD: 3dfa9e2cab372f8cb034b90256ed3fba9da6c878
D7 final certified source TREE: bb1de2e7c2933ba3a777523f2a0e2feee5fa8c39
D7 suite: 6302 passed, 17 skipped in 1571.33s
record: docs/validation/pd4-d7-read-only-source-certification.md
```

Production D7 state:

```text
D7-A real-host qualification: NOT RUN / waiting for natural 6/6 READY
D7-B provisioning:            PROTECTED / conditional only if required
D7-C first publication:       PROTECTED / UNAUTHORIZED
D7-D production reconciliation: NOT RUN
```

## Architecture 114 / D8-D9 settlement source — CERTIFIED

Architecture/plan:

```text
docs/architecture/114-personal-desktop-unattended-paper-settlement-authority.md
docs/validation/pd4-unattended-settlement-plan.md
```

D8-A/R1 accepted:

```text
HEAD 170b50743458c8c973d472476b9e7abf140b6b1d
TREE b2a202faf45bf61d5e3c1043c69a6cafcb00b6e3
focused: 233 passed
production invocation: NOT RUN
```

D8-B/R1 accepted / effects closed:

```text
HEAD 260d80f60db9acfd352b1bc89ff963fc2a590a38
TREE bc4fb96d2ecb30e607262de2c0b268510bd43835
focused: 134 passed
production invocation: NOT RUN
```

D9-A independent all-gates-closed reconciliation source accepted:

```text
HEAD 0df4ccb97a750e5727ef65dae7a365a3c7355254
TREE f6c27fcff1a6cec839d8f6ec395d658dbbbbe36c
focused: 422 passed
production invocation: NOT RUN
```

Final D8/D9 source certification accepted on the exact same source tree:

```text
certified HEAD: 0df4ccb97a750e5727ef65dae7a365a3c7355254
certified TREE: f6c27fcff1a6cec839d8f6ec395d658dbbbbe36c

replacement split certification:
  broad nonlegacy:        5709 passed
  Architecture-77 legacy:  758 passed
  combined:               6467 passed, 17 skipped
  failures/errors:        0

Ruff check: PASS
Ruff format --check: PASS (547 files)
git diff --check: PASS
git diff --cached --check: PASS
worktree/index: clean at certified source boundary
local source HEAD == origin source HEAD: YES
```

The first monolithic D9-B attempt was environment-invalid only for the two
legacy Architecture-77 modules because the fixed repository-local
`.pytest_cache/ai-trading-bot-lifecycle-arbiters-v1` namespace was inaccessible.
The accepted replacement used the previously validated clean-harness split and
proved the legacy test modules were byte-identical and all relevant imports came
from the D9 source tree. The inaccessible cache was not deleted, ACL-reset,
taken over, or redirected.

Certification record:

```text
docs/validation/pd4-d9-settlement-source-certification.md
```

Production/effect state remains:

```text
D8-A production qualification:  NOT RUN
D8-B first real settlement:     PROTECTED / NOT AUTHORIZED
D9-A production reconciliation: NOT RUN
receipt recovery:               CLOSED
```

The later protected sequence is still:

```text
accepted D7 publication + D7-D reconciliation
-> wait until intended execution session E completes
-> exact selected C3(E)
-> fresh D8-A Trading read-only qualification
-> explicit approval for one D8-B settlement invocation
-> fresh-process D9-A durable reconciliation
```

D10 soak remains future until the first accepted unattended settlement sequence
exists to soak.

## Primary roadmap

```text
PD0   personal-desktop profile adoption                     COMPLETE
PD1   personal-desktop paper-account authority v2           COMPLETE
PD2   reliable supervised manual paper cycle                COMPLETE
PD3   supervised crash/recovery validation                  COMPLETE
PD4   unattended simulated-paper source foundation          COMPLETE
  G0-G7 daily-cycle source/design foundation                ACCEPTED
  D3/D4 first unattended C3 capture/reconciliation          ACCEPTED
  D5 capture-only warm-up                                   ACTIVE (3/6; WARMING_UP)
  D6 decision-publication source                            ACCEPTED
  D7 read-only qualification/reconciliation source          CERTIFIED
  D7-A production qualification                             WAITING FOR NATURAL 6/6 READY
  D7-C first pre-open decision publication                  PROTECTED / UNAUTHORIZED
  Architecture 114 D8/D9 settlement contract               ACCEPTED / SOURCE-ONLY
  D8-A read-only settlement qualification source            ACCEPTED
  D8-B settlement-only production source                    ACCEPTED / EFFECTS CLOSED
  D9-A independent reconciliation source                    ACCEPTED
  D9-B final D8/D9 source certification                     ACCEPTED
  D8-B first real unattended Paper-v2 settlement            FUTURE / PROTECTED
  D10 bounded unattended simulated-paper soak               FUTURE / PROTECTED
  unattended operational deployment                         NOT YET COMPLETE
PD5   broker-paper integration                              NOT STARTED
PD6   broker-paper soak / operational hardening             NOT STARTED
PD7   personal-desktop live-readiness                       NOT STARTED
PD8   tiny restricted live -> gradual maturity              NOT STARTED
```

Safe parallel development while D5 warms may proceed only on a separate branch/
worktree. The armed D5, certified D7, and certified D8/D9 operational worktrees
should remain stable. A suitable next source-only product milestone is read-only
operator observability over existing authorities: D5 warm-up/history, selected
market-data audit, gate state, scheduler health, Paper-v2 account/lineage, and
D7/D8/D9 readiness. Such a GUI/operator layer must remain presentation-only and
must not acquire alternate trading authority.

## Effect gates and protected actions

All eight production gate constants remain committed `False`:

```text
PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED            = False
PERSONAL_DESKTOP_UNATTENDED_DECISION_PUBLICATION_EFFECTS_ENABLED           = False
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED                       = False
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED                         = False
PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED             = False
PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED                 = False
PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED             = False
PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED  = False
```

The D5 capture-only runtime may temporarily change only the process-local
market-data gate around exactly one reviewed G5 call and restores it in
`finally`. This does not authorize ad hoc/manual provider calls.

Still protected/not authorized outside exact reviewed checkpoints:

```text
manual/ad hoc provider effects or retries outside D5 capture-only authority
real D7 decision publication before protected acceptance
real Paper-v2 receipt-recovery mutation
unattended decision/storage provisioning effect unless separately authorized
Task Scheduler changes/manual start beyond accepted D5 deployment
first real unattended Paper-v2 settlement/execution
broker order submission
live trading
old v1 publisher rerun
v1 staging delete/repair/rename/migration/reuse
Paper-v2 manual mutation outside reviewed effect checkpoints
account/group/password changes
LSA rights/policy changes
KSP/signing/private-export effects
merge/rebase/force-push/amend/PR metadata/review-thread changes without explicit approval
```

## Workflow invariants

- ChatGPT/Sol owns architecture/security review, exact GitHub diff review, test
  gates, merge/deployment/production decisions, and next milestones.
- After a reviewed checkpoint passes, automatically continue to the next safe,
  scoped checkpoint; stop at explicitly protected production/effect boundaries.
- Small, tightly scoped, low-risk mechanical work may be handled directly by
  ChatGPT when delegation adds no useful isolation.
- Codex uses Luna Extra High for frozen/local mechanical work, Astra for bounded
  discovery-aware/cross-module work, and Sol High for native Windows/security/
  authority/order/crash/recovery and other safety-sensitive implementation.
- Model choice never transfers architecture or acceptance authority.
- No subagents unless explicitly requested.
- Codex runs focused tests/checks during implementation. Run the complete
  repository suite only when ChatGPT has declared the exact tree final for the
  milestone.
- Never `git add .` or `git add -A`; exact-file stage only.
- Worktree/branch/HEAD/tree/origin mismatch is a STOP; do not self-correct.
- Controlled Windows pytest uses a fresh external
  `F:\AI\temp\pytest\<purpose>-<unique>` via explicit `--basetemp` and normally
  `-p no:cacheprovider`; do not globally change `TEMP`, `TMP`, or persistently
  set `PYTHONPATH` for normal pytest collection.
- Architecture-77 legacy process-rendezvous tests intentionally use their fixed
  repository-local arbiter namespace; do not rewrite that contract to follow
  `--basetemp` merely to avoid a local ACL condition.
- Preserve unrelated generated/untracked reports and historical evidence.
- No merge/rebase/force-push/amend/PR metadata/review-thread changes without
  explicit approval.

## PD4 operator observability — PARALLEL DEVELOPMENT

O1 and O2 source are accepted on the isolated observability branch.

```text
HEAD  ee1f44022340563f94f334f897a5e88859f7c6c7
TREE  76f98eb64a3205a88dcd86a2c541feaaea9939fa
16 focused tests passed
Ruff check/format PASS
diff checks PASS
worktree CLEAN
```

O2 accepted source:

```text
HEAD  70672c65c7ecf0923516da7c2b57934dc950dbc8
TREE  762dc13000f435c58f31c9750c0cd22aac582840
32 focused O1+O2 tests passed
Ruff check/format PASS
diff checks PASS
worktree CLEAN
```

The next step is O2 real-host read-only qualification under
`DESKTOP-I4DOKM7\Trading`. It grants no publication, settlement, retry,
scheduler, provider-capture, or broker authority.

## Documentation workflow

At every accepted milestone, review/update as applicable:

```text
README.md
docs/PROJECT_STATUS.md
docs/AI_TRADING_BOT_HANDOFF.md
relevant docs/architecture/*
relevant docs/validation/*
```

Historical subsystem completion records remain historical unless a later
extension explicitly belongs in them. Current operational extension state is
recorded in the canonical status/handoff plus the relevant Architecture/plan.

Docs-only closeouts do not require a new full repository suite when exact diff
review proves no source/test change.


### D7-A qualification checkout note

The certified D7 operational worktree remains clean at docs tip
`489b96a97d36fd28822142db9a69f0f0dd2d3d72`, whose only delta from the
certified D7 source `3dfa9e2cab372f8cb034b90256ed3fba9da6c878` is the certification
document. However, system Git has `core.autocrlf=true` and that frozen worktree's
first-operation history seed is physically CRLF/1061 bytes even though Git's
filtered blob is canonical.

Do not rewrite the frozen D7 worktree. Real-host D7-A should use a disposable
detached qualification worktree at the exact certified source commit, created
with `core.autocrlf=false` for checkout, and must prove the seed raw worktree
blob equals the tracked blob before invoking the read-only launcher.


### Operator observability O3 — ACCEPTED

The native read-only Operations page is accepted at:

```text
HEAD: fd504503d1fb468c0a2791e00d296da983afeb5a
TREE: bb2a19189dc72a939456653db2cbd745fa237822
focused pytest: 71 passed
Ruff/diff checks: PASS
worktree: clean
```

The page presents bounded O2-derived cycle/session state, selected-C3 history,
all eight gates, Paper-v2 account summary, and strategy readiness. It has no
production-runtime imports or effect controls. O4 deterministic MA3/MA5 strategy
explanation is the next observability checkpoint.
