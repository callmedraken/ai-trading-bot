# Architecture 134-F1 â€” five-session current-product live-paper soak authority

Status: **SOURCE IMPLEMENTED; exact-source acceptance pending; CI owns ROBINHOOD.**

This document specializes Architecture 134-F's generic requirement for a fresh
multi-session live-paper soak into a bounded current-product authority model.
It grants no scheduler, provider, credential, D1R7, D1R8, D1R9, paper, broker,
promotion or live-money effect.

## Objective

Architecture 134-F1 defines one parent authorization for exactly five
consecutive published regular NYSE sessions. The series exercises the accepted
current-production strategy decision and synthetic review-paper path under live
market-data conditions while preserving the one-attempt/no-retry semantics of
the accepted D1R9 supervisor.

The five-session window is the minimum operational window aligned with the
Architecture-144 research eligibility policy. Completing the operational soak
does not itself establish research eligibility, profitability or promotion
authority.

F1 does **not** emit or construct Architecture-144 v1 observations. That accepted
v1 contract is historically D1R9-specific and remains frozen. Truthful F1-to-144
composition is deferred to a separate pure Architecture-144-C successor after the
final F1 source HEAD/TREE are accepted.

## Current integration base

The source implementation starts from current remote `develop`:

```text
HEAD  b3b605fdc0886cd90367027e72d43ecaf8ce5b4c
TREE  1b2b783211aa41d9add5e3c29d3a336c33a75c3c
```

Feature branch:

`feature/robinhood-production-paper-134f-five-session-soak`

Fixed worktree:

`F:\AI\worktrees\ai-trading-bot-production-paper-134f-five-session-soak`

The retired history compatibility branch is not a predecessor and must not be
recreated.

## Accepted D1R9 semantic predecessor

Accepted D1R9 remains immutable evidence on:

```text
branch feature/robinhood-production-paper-d1-arbitrary-time-supervisor
HEAD   efd1e6763dc4663d9c4b2444e785eb1c32adf8e8
TREE   25a962daf3922c4226c7e395eba8613e1b03bbaf
```

Reviewed D1R9 executable blobs include:

```text
src/trading_bot/review_paper/d1_session_supervisor.py
  b35d47931ceb0a861b6e47ab6fb7853ac1f674ce
src/trading_bot/review_paper/d1_session_supervisor_store.py
  a0ebf56afa089c245dbaaebcf2182bdb9486bf49
src/trading_bot/review_paper/d1_session_supervisor_host.py
  ba1bd91d528f820e399bc93a3209239e09fdf7ba
scripts/arch134_d1r9_bridge.py
  edf3bb8eee81ac73815e6807a3dbc556b456517d
scripts/arch134_d1r9_d1r7_child.py
  8574331c1a9249d438ecffabb7c651f1fb5a0126
scripts/arch134_d1r9_d1r8_child.py
  d3788070ec84c262f5a3385ebe7e5c51a3802091
scripts/arch134_d1r9_scheduler.ps1
  d66cf32dd1d00357af1b37d597e37bbee398050f
scripts/run_arch134_d1r9.py
  fe53ef0a43669adc84aa81b8c299c68b1c8a2d9f
```

The D1R9 branch and current `develop` have diverged. F1 must not merge,
rebase or cherry-pick that branch wholesale. D1R9's fixed worktree/branch/task
identity also means its executable files cannot simply be copied and run from
the F1 worktree.

F1 instead treats D1R9 as a frozen semantic predecessor: tests must prove the
new one-session child behavior preserves D1R9's accepted state, timing,
reconciliation and effect ceilings while changing only the authority source
from a human one-session interlock to one durable child grant issued by the F1
parent.

## Parent authorization

Frozen top-level interlock:

`AUTHORIZE_ARCH134_F1_FIVE_SESSION_LIVE_DATA_SYNTHETIC_PAPER_SOAK`

The interlock is accepted only from an interactive top-level authorization
entry point. One accepted parent authorization may bind exactly one five-session
series and may never be reused for another series.

No caller chooses the symbol, strategy, account, provider, exchange, session
dates, quantity, evidence paths, child source, scheduler arguments or retry
policy.

## Session selection

Use only `NYSEPublishedRegularSessionAuthority` plus an aware UTC clock.

At authorization:

1. If the current New York date is a published regular session and current time
   is before that session's regular close minus five minutes, session 1 is that
   date.
2. Otherwise session 1 is the next published regular session.
3. Sessions 2-5 are the next four published regular sessions in authority order.
4. Weekends and holidays are skipped.
5. Early closes use the published close.
6. The five dates are durably frozen before any scheduler or child effect.
7. The series never rolls a missed/blocked session into a later replacement.

## Durable parent series

F1 owns one append-only parent journal with a deterministic identity derived
from:

- schema/version;
- exact F1 source HEAD/TREE;
- exact production contract and strategy identity;
- symbol `SPY`;
- ordered five-session tuple;
- accepted D1R7/D1R8 and D1R9 semantic predecessor identities;
- fixed scheduler/task policy; and
- fixed F1 effect ceilings.

Clock instant, caller path, retry nonce, process ID and scheduler runtime state
are not identity inputs.

Required parent states include:

```text
SOAK_RESERVED
SOURCES_ADMITTED
WINDOW_BOUND
SCHEDULER_CREATE_INTENT
SCHEDULER_CREATE_ACK
SOAK_READY
SCHEDULER_RUN_INTENT
SCHEDULER_RUN_ACK
SESSION_1_GRANT_INTENT
SESSION_1_FINAL
...
SESSION_5_GRANT_INTENT
SESSION_5_FINAL
FINAL
```

The journal uses exclusive creation, canonical closed records, flush/fsync,
bounded readback and append-only state transitions. Restart/reconciliation
authority comes only from the durable parent and child journals.

## One-session child grants

The parent may issue at most one durable child grant for each frozen target
session. A grant binds:

- parent series identity/digest;
- exact child ordinal and target session;
- exact F1 source HEAD/TREE;
- exact D1R7/D1R8 predecessor identities;
- exact production contract/strategy/symbol;
- runtime binding;
- effect counters initially zero; and
- the D1R9-equivalent timing/state policy.

A child grant is not the accepted D1R9 human interlock and must never be passed
to D1R9's existing `authorize()` entry point. F1 implements a current-lineage
one-session child boundary whose positive effect semantics are proven equivalent
to D1R9 after durable parent authorization.

Each child can delegate at most:

- one accepted D1R7 prerequisite publication; and
- one accepted D1R8 synthetic-paper session

for its exact target.

There is no provider reacquisition/retry loop and no second child grant for the
same target.

## Child terminal semantics

The accepted one-session terminal classifications remain:

```text
NO_SIGNAL
RISK_REJECTED
PAPER_EXECUTED
SESSION_MISSED
BLOCKED
INDETERMINATE
```

For F1 operational progression:

- `NO_SIGNAL`, `RISK_REJECTED` and `PAPER_EXECUTED` close that child and
  permit the parent to advance to the next frozen target;
- `SESSION_MISSED`, `BLOCKED` or `INDETERMINATE` halt the entire series;
- after a halt, all later child effect ceilings are zero;
- no automatic retry, replacement date, backfill, repair or catch-up is allowed.

A completed five-session soak may still fail Architecture-144 eligibility.
In particular, `RISK_REJECTED` is operationally terminal but nonqualifying
for the frozen Architecture-144 v1 eligibility policy.

## Waiting and restart model

Preserve D1R9's arbitrary-time PC-ON model:

- authoritative current time and published session state are recomputed after
  every bounded wait/restart;
- no persisted sleep duration is authority;
- maximum in-process wait quantum remains 60 seconds;
- wake-from-sleep is not added;
- Task Scheduler is process-start/restart plumbing only;
- scheduler state never creates session/effect authority.

The controller may remain alive across the five-session window while the PC is
on. A logon-triggered restart may resume only after exact parent/child durable
reconciliation.

## Scheduler surface

F1 owns a new task identity:

`AITradingBot-Arch134-F1-FiveSessionSoak-v1`

The task must preserve the accepted D1R9 scheduler safety shape:

- exactly one current-user logon trigger;
- exactly one executable action;
- zero caller/session/strategy semantic arguments;
- standard user, no elevation;
- `WakeToRun = false`;
- `StartWhenAvailable = false`;
- demand start allowed;
- `MultipleInstances = IgnoreNew`;
- three process restart attempts at one-minute intervals;
- unlimited execution-time setting;
- no trigger repetition interval/duration;
- no scheduler-derived market/session authority.

The task points only at the fixed F1 worktree/current-lineage host. It must not
execute the historical D1R9 worktree.

Source implementation and certification perform zero real scheduler mutation.
Task creation/run/retirement are later separately reviewed protected effects.

## End-of-window evidence

A successful F1 operational series ends only after all five child journals are
independently re-read and reconciled. The parent FINAL record binds, in order:

- each target date;
- child journal bytes/digest;
- child terminal classification;
- D1R7 proof identity/digest;
- D1R8 proof identity/digest where applicable;
- final effect counters; and
- scheduler/task reconciliation state.

The effectful F1 controller must not create Architecture-144 observations,
eligibility artifacts, candidates or promotion state.

The accepted Architecture-144 v1 verifier and v1 observation schema remain
D1R9-bound and must not be loosened to admit F1 provenance. F1 end-of-window
evidence instead preserves truthful current-lineage source HEAD/TREE, parent
series identity/digest, ordered child identities/digests, exact D1R7/D1R8 proof
bindings and terminal classifications.

After F1 source acceptance, a separate pure Architecture-144-C successor will pin
the exact final F1 source identity and define a generic paper-authority v2
observation/eligibility path. That successor is the only allowed F1-to-144
admission path. The real soak remains closed until 144-C is source-accepted.

## Effect ceilings

Across one F1 parent authorization:

```text
parent series                  <= 1
frozen target sessions         == 5
D1R7 delegations               <= 5 total, <= 1 per target
D1R8 delegations               <= 5 total, <= 1 per target
scheduler CREATE               <= 1
scheduler demand RUN           <= 1 initial parent-authorized start
provider retry/reacquisition   == 0
replacement/backfill sessions  == 0
broker order placement         == 0
D2 operations                  == 0
strategy promotion             == 0
real-money effects             == 0
```

Process restarts caused by the reviewed scheduler restart policy are plumbing,
not fresh child/provider authorization. They must reconcile durable intent before
any effect and may not increase the effect ceilings.

## Explicit non-goals

F1 does not authorize:

- real Robinhood order placement/cancel/replace;
- options or crypto;
- live-money trading;
- D2;
- research candidate materialization;
- automatic promotion;
- AI-generated strategy changes;
- more than five target sessions;
- retry after ambiguous provider or paper outcome;
- catch-up after a missed session;
- reusing the historical D10 task/deployment/lease authority;
- reusing the consumed 2026-10-19 D1R9 authorization;
- merging/cherry-picking the historical D1R9 branch into current develop; or
- performing any operational effect during source implementation/certification.

Real-money trading remains **NO-GO**.

## Source checkpoint

F1 source implementation is a security/authority-sensitive cross-module task.

Owner/model: **Codex / Sol High**.

The implementation checkpoint must remain source-only with
`preflight=None` and `execute=None`. It must provide focused proof of all
authority/effect ceilings and complete current-inventory/pin integration.

Because F1 changes only the current Robinhood/review-paper production authority
surface plus its owned checkpoint infrastructure, its terminal selected
certification profile is **ROBINHOOD**, not FULL. Map the terminal checkpoint to
CI-owned `robinhood` before publication so one final push owns the canonical
selected profile. Do not run FULL merely because the milestone is security-
sensitive; FULL is reserved for materially broader supported-surface coverage.
Do not ask the human to run a duplicate ROBINHOOD or FULL.

## Architecture-144 successor dependency

F1 source acceptance is intentionally **before** Architecture 144-C because the
pure successor must bind the exact final F1 source HEAD/TREE. The required order
is:

```text
134-F1 source + focused verification
-> CI-owned ROBINHOOD
-> ChatGPT exact-source acceptance
-> 144-C pure F1 evidence-admission successor
-> 144-C source acceptance
-> protected 134-F preflight
-> only then the real five-session soak
```

Architecture 144-C must keep the existing v1 D1R9 verifier, observation schema,
eligibility schema, identities and canonical bytes unchanged. It may add only a
separate v2/generic-authority path with truthful F1 provenance.

## Implemented source/evidence surface

`five_session_soak_store.py` is a standard-library-only closed parent/child
codec shared by the current-lineage controller and fixed child bridges.
`five_session_soak.py` derives and freezes the five published targets;
`five_session_soak_child.py` preserves the accepted D1R9 one-session reducer.
`five_session_soak_host.py`, `arch134_f1_bridge.py`, the two fixed F1 child
adapters, `arch134_f1_scheduler.ps1`, and `run_arch134_f1.py` own only the F1
worktree/task identity. There is no historical D1R9 runtime import or invocation.

The exclusive parent slot is `arch134-f1-five-session-soak-v1.jsonl` beneath the
fixed existing qualification parent. A consumed, malformed or terminal slot
cannot authorize another series. Child UUID5 identities bind the semantic
parent identity, exact ordinal/window/contract and source policy. Clocks,
runtime file metadata and serialized journal bytes are excluded from UUID
material. Exact runtime identities and canonical journal digests are separately
bound in evidence. Both F1 schemas and UUID identity version are v1.

A child binds `parent_prefix` (length/SHA256) through its parent's durable
`SESSION_n_GRANT_INTENT`. Parent FINAL binds its own pre-FINAL prefix digest,
plus the ordered five child identities, journal length/digests, exact targets,
contracts, D1R7/D1R8 proof length/digests, terminal classifications, per-child
attempts and complete D1R8 effect counters. This avoids a circular hash while
allowing a future pure verifier to recompute every digest from supplied bytes.
Each earlier finalized child and its underlying accepted proofs are re-read
before later progression. Successful finalization also requires five exact
children, matching saved summaries, idle child transport and scheduler MATCH.

Incomplete/ambiguous child evidence halts without inventing a positive proof or
repairing its consumed slot. Underlying durable child/D1R8 intents remain the
effect evidence. Parent counters track its own grant/scheduler entries; actual
D1R7/D1R8 attempts are recorded by their child journals and ordered summaries,
including consumed intents, rather than a stale parent copy of child counters. The F1 checkpoint is `arch134-f1-five-session-soak`, with
`preflight=None`, `execute=None`, and CI `robinhood` mapping. Architecture-144 v1
source remains unchanged; Architecture 144-C is not implemented here.
