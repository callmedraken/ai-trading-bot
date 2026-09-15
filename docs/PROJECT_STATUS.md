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

## Primary development lines

The currently armed capture-only warm-up deployment remains on the frozen
personal-desktop branch/worktree:

```text
repository: callmedraken/ai-trading-bot
integration baseline: bd88ee966bff455f9fc897d6cfdfafdd807f27e2
Architecture-94 P2 base: a810122a96b6fc90da25d71eede8da64b7272c98

D5 deployed/warm-up branch:
feature/personal-desktop-paper-runtime

D5 deployed/warm-up worktree:
F:\AI\worktrees\ai-trading-bot-personal-desktop

D5 accepted source HEAD:
8c2af5801cbc8f4df869b832a3b78b1eaa2f8996

D5 accepted source tree:
f0591e966463c7e1e66dc00ad76fd895500a076f
```

Do not modify the armed D5 worktree merely to continue development. New D6/D7
source/design work is isolated on:

```text
branch: feature/pd4-unattended-decision-publication
planned local worktree: F:\AI\worktrees\ai-trading-bot-decision-publication
base commit: 8c2af5801cbc8f4df869b832a3b78b1eaa2f8996
base tree:   f0591e966463c7e1e66dc00ad76fd895500a076f
```

The earlier PD4 unattended source-foundation certification remains an important
historical certification boundary:

```text
final PD4 source-foundation certified commit:
248cd8de6a3539aab21d5719d96cb7ff1aa0d14c

final PD4 source-foundation certified tree:
5e867f1bfc6d945ad67f6c56be252b534645aeb2

full suite:
5588 passed, 17 skipped in 1519.25s (0:25:19)
```

Later Architectures 111/112 and D5 source/deployment work extend that accepted
foundation; they do not retroactively change the historical PD4-F certification
record.

Architecture checkpoints now include:

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

## C3 production and unattended capture state

Historical C3 release source:

```text
82ba29ae2c2cc6bb3544077db0ee21868e6d5693
```

The earlier manual C3 acceptance established:

```text
call #5: FAILED / CONFIRMED
call #6: SUCCEEDED / CONFIRMED / SUCCESS_SELECTED
```

Selected call #6:

```text
selection_id: 36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280
snapshot_id: eba46838-44ae-5bec-97bf-98c6639ae6a7
artifact SHA-256: 31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
artifact byte length: 1291
captured_at: 2026-08-29T09:46:43.769105+00:00
```

Architecture 111 subsequently froze a separate unattended market-data gate and
the zero-semantic-argument daily-cycle model. D3/D4 then accepted the first
unattended C3 capture and read-only reconciliation for session `2026-09-11`:

```text
selection_id: 7c42363d-4785-5823-be7e-93bf94426eac
snapshot_id:  8ddc60ed-3940-5379-a868-b46b9b7c95af
artifact SHA-256: 704c1d0966acec3489a355fd6ef5369439b07e0e0a8e15c5f68cc2d847aa607f
artifact byte length: 1289
```

Architecture 112 then constrained normal warm-up wakes to exactly one G5 call,
with only the market-data gate opened process-locally and restored in `finally`.
No scheduler exit code, process failure, or provider ambiguity grants retry
authority.

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

Architecture 111 adds a two-phase unattended composition without weakening that
final plan contract:

```text
selected current C3 close + C3-authoritative history + account predecessor
-> PreparedManualPaperStrategyDecision (pre-open; no execution-session open)
-> durable pre-open decision intent
-> later selected C3 open for the intended execution session
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
future decision namespace from Architecture 111:
                    F:\AITradingBot\Paper-v2\runtime\unattended-decisions
```

The exact decision-namespace storage/ACL/publication contract must be frozen and
accepted before any D6/D7 production publication effect.

Published account:

```text
paper_account_id:   9415cd7b-bf36-5fba-bd58-a0f99119dc21
GENESIS checkpoint: 1832a2b5-8b63-501a-8f7d-f1722c32307b
starting cash:      Decimal("25000")
GENESIS as_of:      2026-08-29T09:46:43.769105+00:00
```

Frozen publication artifacts:

```text
GENESIS  SHA-256 d1a7ff14425c8a797a952860a1102489a4c81cac2a24a45bc3127eb8eb2e9548  length 533
anchor   SHA-256 16c4dba01835c5bc2def91f0103ad79c3da0b5d18af72091b4fdd37fe4353c85  length 465
manifest SHA-256 8fe1d705d59a79207ab6236af71becee0051042dc7b3ecaf23bb7f5531cb0029  length 532
freeze Git blob b125cbb1c80a827f74018cf2955b9a27ba69fa90
```

Retained failed v1 state:

```text
F:\AITradingBot\Paper                    ABSENT
F:\AITradingBot\.Paper.provisioning-v1  PRESENT / RETAINED / UNTOUCHED
```

Never rerun the old v1 publisher or delete, repair, rename, migrate, or reuse
the retained v1 staging tree as incidental cleanup.

## PD1 — personal-desktop Paper-v2 authority — COMPLETE

Completion record:

```text
docs/validation/pd1-personal-desktop-paper-v2-completion.md
```

## PD2 — reliable supervised manual paper cycle — COMPLETE

Completion records:

```text
docs/validation/pd2a-paper-account-runtime-mutex-completion.md
docs/validation/pd2b-supervised-paper-composition-completion.md
docs/validation/pd2c-supervised-paper-execution-boundary-completion.md
docs/validation/pd2d2-first-real-paper-operation-completion.md
```

Canonical PD2 state:

```text
PD2A = COMPLETE
PD2B = COMPLETE
PD2C = COMPLETE
PD2D1 = COMPLETE
PD2D2 = COMPLETE
PD2 = COMPLETE
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

Independent post-mutation reconciliation proved:

```text
result:                    RECONCILED
lineage_edge_count:        1
account_cash:              25000
position_count:            0
inspection_classification: ALREADY_APPLIED
inspection_diagnostic:     ALREADY_APPLIED
```

PD2 final broad certification:

```text
5146 passed, 17 skipped in 1505.92s
Ruff check: PASS
Ruff format --check: PASS (457 files)
git diff --check: PASS
```

## PD3 — supervised crash/recovery validation — COMPLETE

Architecture:

```text
docs/architecture/109-personal-desktop-paper-receipt-recovery-authority.md
```

Completion record:

```text
docs/validation/pd3-personal-desktop-receipt-recovery-completion.md
```

Accepted PD3 source:

```text
commit e690ce83d6c53507d9e93dca97bcb79191c62a0b
tree   522f41115d2079ae777f667a19e5179c1d492e1f
```

Final broad source certification:

```text
5285 passed, 17 skipped in 1478.19s
Ruff check: PASS
Ruff format --check: PASS (467 files)
git diff --check: PASS
worktree/index: clean
```

Real-host read-only acceptance ran under `DESKTOP-I4DOKM7\Trading`, non-elevated,
and returned healthy completed-account evidence with no recovery mutation.

## PD4 — unattended simulated-paper source foundation — COMPLETE

Architecture 110 source-foundation completion remains historical and accepted:

```text
completion record:
docs/validation/pd4-unattended-personal-desktop-paper-completion.md

final certified source commit:
248cd8de6a3539aab21d5719d96cb7ff1aa0d14c

final certified source tree:
5e867f1bfc6d945ad67f6c56be252b534645aeb2
```

Accepted source-foundation checkpoints cover:

```text
PD4-A    durable unattended invocation identity/model and verification
PD4-B    durable invocation storage/read/publication/provisioning boundaries
PD4-C    read-only startup qualification under the same PD2A mutex
PD4-D    unattended Paper-v2 execution composition with effects closed
PD4-D-R1 explicit non-private shared composition interfaces
PD4-E    zero-semantic-argument launcher + frozen scheduler contract
PD4-F1   genuine production read-only host-validation harness
PD4-F2   final exact-tree source certification
PD4-F3   Trading-principal real-host read-only qualification
```

Final PD4 source-foundation broad certification:

```text
5588 passed, 17 skipped in 1519.25s (0:25:19)
Ruff check: PASS
Ruff format --check: PASS (486 files)
git diff --check: PASS
git diff --cached --check: PASS
worktree/index: clean
local HEAD == origin feature HEAD: YES
```

That completion record must remain historical: it correctly states that the
Architecture-110 source foundation alone did not authorize operational
unattended deployment.

## PD4 unattended daily-cycle extension — Architecture 111

Architecture 111 and its validation plan are accepted design/source contracts:

```text
docs/architecture/111-personal-desktop-unattended-daily-cycle-authority.md
docs/validation/pd4-unattended-daily-cycle-plan.md
```

Key frozen rules:

- Task Scheduler is an untrusted wake-up source and supplies no semantic trading
  authority;
- version-1 regular open is 09:30 America/New_York for the modeled XNYS session;
- a decision targeting session `E` must be finalized strictly before
  `regular_open(E)`;
- the pre-open decision contains no `open(E)` or later market-data fact;
- after `E` completes, only a current-C1 selected C3 snapshot for `E` may bind
  its verified daily-bar open for settlement;
- C3-selected history, not the old offline seed, is production authority;
- the current MA 3/5 profile requires six consecutive selected C3 sessions
  before the first fully C3-backed decision;
- no automatic multi-session catch-up is authorized; an internal history gap is
  `SESSION_GAP`;
- unattended market-data capture and decision publication have separate
  closed-by-default source-owned gates.

## PD4-D5 capture-only warm-up — ACTIVE / FIRST SCHEDULED WAKE ACCEPTED

Architecture and validation plan:

```text
docs/architecture/112-personal-desktop-capture-only-warmup-authority.md
docs/validation/pd4-d5-capture-only-warmup-plan.md
```

D5-A read-only Task Scheduler qualification was accepted. The exact accepted D2
predecessor task XML SHA-256 was:

```text
da851985d9bfb04c65a83cb64b5441a2f7fd50391924a844749e365ee282d6ec
```

D5-B then changed only the existing task launcher action to:

```text
-I F:\AI\worktrees\ai-trading-bot-personal-desktop\scripts\run_personal_desktop_unattended_capture_warmup.py
```

The first credential-less mutation call failed authentication. Read-only
reconciliation proved the installed task remained exactly D2 with the same XML
hash, so no ambiguous scheduler state was retried blindly. A separately
credential-aware attempt under the existing D5-B authorization then succeeded.
The accepted D5 task XML SHA-256 is:

```text
8005373fad791c85776b4a35b662d46e06fec4ea40ac9ebfead9f413715da457
```

D5-C first scheduled capture-only wake was accepted with:

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

The authoritative selected warm-up history is currently:

```text
2026-09-11
2026-09-14
selected_count = 2 / 6
G6 = WARMING_UP
G5 post-capture = NO_NEW_COMPLETED_SESSION
```

All eight committed source effect gates were false before and after the accepted
wake. D5 ordinary wakes may open only the market-data gate process-locally for
one exact G5 call and must restore it in `finally`; decision publication and all
Paper-v2 effect gates remain closed.

The armed D5 task should remain untouched while it accumulates sessions
naturally. Do not manually start it, backfill from the old offline seed, alter
its source/scheduler contract, or turn a failed/ambiguous provider outcome into
a blind retry.

## Current milestone — PD4 D6/D7 unattended decision publication

While D5 warm-up continues, development moves to a separate branch so the armed
D5 source/deployment evidence remains stable.

The next source/design checkpoint is **Architecture 113 — Personal-Desktop
Unattended Decision Publication Authority** plus its D6/D7 validation plan.

Freeze before implementation:

```text
canonical pre-open decision-intent schema and verifier
deterministic decision/publication identity
exact six-selected-C3 provenance binding
strict pre-open deadline admission
process-local one-shot publication permit
fixed decision namespace + ACL/path/no-reparse contract
ABSENT / FINALIZED_IDENTICAL / STAGING / CONFLICT / BLOCKED read classifications
exclusive staging + flush + no-clobber finalization + exact reread verification
duplicate-wake convergence
crash/ambiguous-publication behavior
MISSED_DECISION_DEADLINE and SESSION_GAP handling
future D8/D9 settlement compatibility without enabling settlement
```

D6/D7 must publish decision intent only. It must not authorize market-data
capture, Paper-v2 execution, receipt recovery, storage provisioning, scheduler
mutation, broker-paper submission, or live trading.

No real D6/D7 publication effect is authorized by architecture/source work.
When D5 eventually reaches `DECISION_READY`, the first production publication
remains a separately protected acceptance checkpoint.

## Primary roadmap

```text
PD0   personal-desktop profile adoption                     COMPLETE
PD1   personal-desktop paper-account authority v2           COMPLETE
PD2   reliable supervised manual paper cycle                COMPLETE
PD3   supervised crash/recovery validation                  COMPLETE
PD4   unattended simulated-paper source foundation          COMPLETE
  G0-G7 daily-cycle source/design foundation                ACCEPTED
  D3/D4 first unattended C3 capture/reconciliation          ACCEPTED
  D5 capture-only warm-up                                   ACTIVE (2/6)
  D6/D7 first pre-open decision publication                 NEXT / DESIGN
  D8/D9 settlement through existing Paper-v2 authority      FUTURE / PROTECTED
  unattended operational deployment                         NOT YET COMPLETE
PD5   broker-paper integration                              NOT STARTED
PD6   broker-paper soak / operational hardening             NOT STARTED
PD7   personal-desktop live-readiness                       NOT STARTED
PD8   tiny restricted live -> gradual maturity              NOT STARTED
```

## Effect gates and protected actions

All eight production gate constants remain committed `False`:

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

The D5 capture-only runtime may temporarily change only the process-local
market-data gate for exactly one reviewed G5 call. That does not make the
committed source gate true and does not authorize ad hoc/manual provider calls.

Still protected/not authorized outside their exact reviewed checkpoints:

```text
manual/ad hoc provider effects or retries outside D5 capture-only authority
real unattended decision publication before D6/D7 protected acceptance
real Paper-v2 receipt-recovery mutation
unattended decision/storage provisioning effect unless separately authorized
Task Scheduler changes beyond the already accepted D5 task action
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

## Workflow invariants

- ChatGPT/Sol owns architecture/security review, exact GitHub diff review, test
  gates, merge/deployment/production decisions, and next milestones.
- After a reviewed checkpoint passes, automatically continue to the next safe
  scoped checkpoint; stop at explicitly protected production/effect boundaries.
- Tiny scoped status/handoff/docs closeouts are ChatGPT-direct by default.
- Codex uses Luna Extra High for frozen/local mechanical work, Astra for bounded
  discovery-aware/cross-module work, and Sol High for native Windows/security/
  authority/order/crash/recovery and other safety-sensitive implementation.
- Model choice never transfers architecture or acceptance authority.
- No subagents unless explicitly requested.
- Codex runs focused tests/checks during implementation; broad/full
  certification is normally user-run locally at the final gate.
- Never `git add .` or `git add -A`; exact-file stage only.
- Worktree/branch/HEAD/tree mismatch is a STOP; do not self-correct.
- Controlled Windows pytest uses a fresh external
  `F:\AI\temp\pytest\<purpose>-<unique>` via explicit `--basetemp` and normally
  `-p no:cacheprovider`; do not globally change `TEMP`, `TMP`, or persistently
  set `PYTHONPATH` for normal pytest collection.
- Source-checkout operator CLIs that must run independently of the current
  working directory/package environment use a reviewed `scripts/` launcher that
  selects the checkout `src` explicitly; production-interpreter import probes
  must exercise that launcher before real-host invocation.
- Preserve unrelated generated/untracked reports and historical evidence.
- No merge/rebase/force-push/amend/PR metadata/review-thread changes without
  explicit approval.

## Documentation workflow

At accepted milestones review/update:

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
