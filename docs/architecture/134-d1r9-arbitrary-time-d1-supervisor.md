# Architecture 134-D1R9 — arbitrary-time one-session D1 supervisor/reconciler

Status: DESIGN FROZEN; source implementation is the next milestone. This
successor corrects the arbitrary-time startup regression discovered on
2026-10-17. Accepted D1R7 and D1R8 remain frozen and byte-identical. This design
authorizes no real scheduler, credential, provider, D1R7, D1R8 or paper effect.

## Standing requirement

The standing Architecture-134 end state requires arbitrary-time startup while the
PC is ON. A supervisor derives legal state from current authoritative time,
published NYSE session authority and durable state. Startup before market, after
market, on weekends or holidays resolves the next published session and waits
instead of terminating on an expired/non-session date. Restart recomputes current
reality and never trusts an old sleep duration. Task Scheduler, if retained,
supplies only automatic start/restart plumbing and never market-session authority.

D1R7 and D1R8 intentionally proved narrower boundaries: D1R7 accepts only the
current New York session and has no next-session rollover; D1R8 accepts only an
admitted current session and has no sleeper. D1R9 supplies the missing
orchestration above those accepted primitives.

The 2026-10-17 D1R7 attempt is PRE_RESERVATION_REJECTED: that date was Saturday,
the D1R7 Plan rejected before source admission, predecessor reads or O_EXCL
reservation, and no D1R7 slot/effect was consumed.

## Fixed lineage

Implementation branch:
`feature/robinhood-production-paper-d1-arbitrary-time-supervisor`

Fixed worktree:
`F:\AI\worktrees\ai-trading-bot-production-paper-d1-arbitrary-time-supervisor`

D1R9 must pin/re-admit these accepted children without modifying them:

- D1R7 branch `feature/robinhood-production-paper-d1-session-authorization`
  HEAD `30322c49b13b80af8d20acee4bdb1efd83d86260`
  TREE `b7dc7f054fca50c3ab784505f264b6f716a45dff`.
- D1R8 branch `feature/robinhood-production-paper-d1-session-execution`
  HEAD `aa07c5ba94e0b55cbd8f920464fcc5bd9efcabd2`
  TREE `fcbfc348dab307fb9c456ce9e17aad0e53d7bd4f`.

D1R5/D1R6 predecessor evidence remains immutable through D1R7.

## One-command authority

One top-level interactive D1R9 authorization represents one current-or-future
NYSE session attempt. The operator may start it at any arbitrary time while the
PC is ON. No caller chooses session/date, exchange, strategy, symbol, provider,
account, price, quantity, evidence destination, child interlock or scheduler
command.

Frozen top-level interlock:

`AUTHORIZE_ARCH134_D1R9_ONE_RECONCILING_SYNTHETIC_PAPER_SESSION`

That grant may bind exactly one target session and may delegate at most one
accepted D1R7 prerequisite publication plus one accepted D1R8 synthetic-paper
session for the same target. It grants no broker placement, D2, live trading,
promotion or repeated-session authority. Another session requires a fresh
top-level authorization.

## Target selection

Use only `NYSEPublishedRegularSessionAuthority` and an aware UTC clock.

At authorization:
1. Convert current time to New York.
2. If today is a published session and time is before regular close minus five
   minutes, bind today.
3. Otherwise scan forward within the frozen calendar authority and bind the first
   published session.
4. Weekends/holidays are skipped. Emergency closures are not inferred.
5. Once durably bound, target is immutable and never rolls to another session.

## Durable supervisor state

D1R9 owns one append-only external authorization/supervisor journal per target.
Its deterministic slot depends on schema, SPY, target session and exact accepted
D1R7/D1R8 identities; caller filename, clock instant and retry nonce do not change
the slot.

Use exclusive creation, closed canonical records, flush/fsync, stable identity and
bounded readback. The supervisor journal is restart/reconciliation authority.

Required closed states include:
AUTHORIZATION_RESERVED, SOURCES_ADMITTED, TARGET_BOUND, SUPERVISOR_READY,
NEXT_SESSION_WAIT, PREMARKET_WAIT, D1R7_DELEGATION_INTENT, D1R7_READY,
D1R8_WAIT, D1R8_DELEGATION_INTENT, and FINAL classifications NO_SIGNAL,
RISK_REJECTED, PAPER_EXECUTED, SESSION_MISSED, BLOCKED, INDETERMINATE.

## Waiting and reconciliation

The supervisor waits only in bounded quanta and then recomputes authoritative
time/session/durable state. Maximum wait quantum is 60 seconds. No persisted sleep
duration is authority.

For a future target:
- NEXT_SESSION_WAIT covers prior dates/weekends/holidays.
- PREMARKET_WAIT covers the target date before D1R7 launch.
- Normally delegate D1R7 at regular open minus 10 minutes.
- If started later but before close-minus-five, delegate D1R7 immediately.
- After D1R7 READY, wait until regular open plus 5 minutes before D1R8.
- If already at/after open+5 and before close-minus-five, proceed after fresh
  re-admission.
- Reaching close-minus-five without a safe D1R8 terminal finishes SESSION_MISSED.
- Never roll the same authorization into another session.

This preserves D1R7's current-date rule and D1R8's open+5 admission without
requiring operator attendance.

## Automatic D1R7 -> D1R8 proof bridge

Before child entry, re-admit accepted source identities and immutable predecessor
state and durably record a delegation intent.

Invoke D1R7 through a D1R9-owned fixed child adapter/process using the exact
accepted D1R7 implementation and exact D1R7 interlock. The child adapter exposes
no semantic selectors.

After child return or restart reconciliation, never trust stdout alone.
Independently derive the D1R7 filename, stable-read and parse the accepted
canonical evidence, require FINAL /
READY_FOR_SEPARATE_D1_SESSION_AUTHORIZATION, exact target, predecessor/policy
bindings and intended D1R8 HEAD/TREE, then compute exact bytes/SHA-256.

Only this complete source-owned proof permits the D1R8 bridge. Partial, invalid
or ambiguous D1R7 evidence is consumed and BLOCKED/INDETERMINATE; never delete,
repair or automatically retry it.

Invoke D1R8 through a separate fixed child adapter/process using the exact
accepted D1R8 implementation, a ReviewedProof built from the validated D1R7
bytes/hash, publication_confirmed=True, and the exact D1R8 interlock. The operator
does not re-enter a D1R8 prompt. Separate processes keep D1R7/D1R8 imports unmixed.

## Automatic reconciliation is not automatic retry

A complete canonical D1R7 READY artifact may be recognized after restart.
A complete canonical D1R8 terminal journal may be recognized after restart.
Timing waits may resume automatically.

But an unacknowledged child-launch/effect intent, partial artifact, source/runtime
drift, ambiguous native acknowledgement or uncertain child liveness is
INDETERMINATE/BLOCKED. No second D1R7 or D1R8 protected entry is allowed for that
authorization. No repair/delete/rename/truncate/overwrite/compensation exists.

## PC-ON start/restart plumbing

D1R9 must satisfy the PC-ON arbitrary-time requirement. A fixed Windows Task
Scheduler entry may be used only as automatic start/restart plumbing. If used,
it must have a new D1R9-specific task path, no market-time trigger as authority,
and no D1R6 WakeToRun dependency. The supervisor itself derives target/session
state from authoritative time and durable evidence on every start.

A noninteractive resume mode is permitted only when a durable D1R9 authorization
exists. With no active authorization or with a terminal authorization it exits
without provider/credential/paper effects.

Scheduler create/update/run effects, if needed, are separately journaled and
bounded. Source tests fake every scheduler/process/native edge.

## Effect ceilings

One D1R9 authorization may delegate at most one D1R7 publication attempt and one
D1R8 session attempt. D1R8's accepted ceilings remain unchanged: write readiness
1; compatibility reservation 1; Alpaca history 4; Alpaca credentials 2;
Robinhood credentials <=2 proposal-only; total credential reads <=4; strategy 1;
PREPARE 1; quote 1; account 1; order-history attempts <=202; order review 1;
EXECUTE 1; synthetic paper fill <=1.

Credential writes/deletes, OAuth refresh/browser/callback/registration, broker
placements/cancellations, options/crypto, ACL, D2 and live effects remain zero.
Scheduler/process effects are supervisor plumbing only and cannot confer session
or trading authority.

## Terminal semantics

NO_SIGNAL and RISK_REJECTED are valid consumed one-session outcomes but do not
qualify execution-dependent soak. Only fully acknowledged PAPER_EXECUTED may
later qualify an execution-dependent soak milestone.

SESSION_MISSED, BLOCKED and INDETERMINATE are consumed for that D1R9
authorization and never auto-roll to another session.

## Source checkpoint

D1R9 implementation is SOURCE-ONLY. Checkpoint-runner registration has no
preflight/execute/remote-head effect hook. Tests use fake clocks, disposable
external evidence, fake child/scheduler/process edges, fake credentials/providers
and disposable paper/session stores.

Required focused coverage: Friday night/Saturday/Sunday/holiday startup; premarket,
admitted and after-close startup; DST/early-close; restart from every wait state;
clock movement; no stale long-sleep trust; immutable target; source/predecessor
re-admission; complete D1R7 proof auto-bridge; partial/ambiguous D1R7 no retry;
D1R8 terminal reconciliation; child-launch ambiguity/no duplicate entry; unmixed
imports; scheduler cannot confer session authority; exact D1R8 effect ceilings;
zero broker/live/D2/credential-write/OAuth-renewal authority; CLI no semantic
date/session/provider/account/evidence selectors.

Compose source/tests/docs/runner overlays before publication. Run focused tests,
Ruff and diff checks, exact-file stage, one atomic commit/push and mapped CI to
terminal. Corrective pushes are separately declared checkpoints. No real D1R7,
D1R8, scheduler, provider, credential or paper effect is authorized by source
implementation.
