# Architecture 134-D1R8 — D1-session execution consumer

Status: SOURCE IMPLEMENTED; pending exact GitHub review and separate SOURCE
ACCEPTED. Operational publication/execution remains unauthorized. No real D1R7
artifact is published by this checkpoint. No real host, credential, provider,
runtime/store, scheduler, broker, D2 or live operation is invoked in validation.

## Frozen admission and successor

Base develop HEAD `3b3a11e822ad42a4dadfe0ac05577df3281bd2bb`, TREE
`e559bc6e03ba63e2c276840e647f72461bdaabee`; source gate #599 / 38998238712
push / attempt 1 / SUCCESS. Origin is exactly
`https://github.com/callmedraken/ai-trading-bot.git`.
Consumer branch `feature/robinhood-production-paper-d1-session-execution` uses
`F:\AI\worktrees\ai-trading-bot-production-paper-d1-session-execution`.
The Git worktree registry supplies canonical registration; the checkout is not
an app-managed worktree. No other checkout or preserved scratch is changed.

Option C introduces a narrow successor controller. Historical D1/D1Q/D1R1–D1R7
executable implementations remain frozen. D1R8 never calls the historical armed
controller/host, recovery controller, nested EXECUTE/operator chain, or D1R7 host.
There is no D1R7 continuation. The sole future interactive interlock is
`AUTHORIZE_ARCH134_D1R8_ONE_D1R7_BOUND_SYNTHETIC_PAPER_SESSION`.
Historical ARM/recovery interlocks cannot confer D1R8 authority.

The host admits both fixed worktrees, branch, clean index/tree, exact origin,
tracking and live remote HEAD/TREE, worktree registry, and unmixed consumer
imports. Git admission is read-only. Caller inputs are reviewed accepted
consumer HEAD/TREE, reviewed D1R7 length/SHA256, and explicit reviewed completion
assertion `--publication-confirmed YES`. These assertions never confer source
acceptance. The completion assertion is permitted only after unambiguous D1R7
publication completion or separately accepted reconciliation. Terminal-looking
bytes from an ambiguous publication are insufficient. No selectable branch,
session, strategy, provider, account, store, price, quantity, evidence path or
order ID exists at the CLI.

## Mandatory immutable prerequisite

The public D1R7 canonical parser and stable reader admit the original seven
events ending `READY_FOR_SEPARATE_D1_SESSION_AUTHORIZATION`. Producer branch is
`feature/robinhood-production-paper-d1-session-authorization`, HEAD
`30322c49b13b80af8d20acee4bdb1efd83d86260`, TREE
`b7dc7f054fca50c3ab784505f264b6f716a45dff`.
The intended branch/HEAD/TREE must equal the separately accepted consumer.
Canonical reconstruction binds the unchanged ProductionStrategyContract,
complete D1 policy, all zero integer predecessor budgets/effects and all false
authority flags. The current NY date determines the sole target; there is no
next-session fallback or sleeper. The exact source-owned D1R7 basename is read
only beneath `F:\AI\temp\qualification`. Reviewed size/hash, regular single-link
identity, all ancestors, opened handles, immutable rereads and publication
observation/expiry are mandatory. D1R7 evidence is never changed.

Execution is limited to regular open + 300 seconds through strictly before
regular close − 300 seconds, on that target only, with nondecreasing aware UTC
observations. Time is rechecked after slow admissions and effects. Source,
prerequisite bytes/identity, runtime identities/schemas, durable paper history,
session and relevant prepared risk/quote state are readmitted before every
effect and before final success acknowledgement.

## One-shot durability and evidence

Schema `arch134-d1r8-d1-session-execution-consumer/v1` is closed canonical JSONL,
at most 1048576 bytes. Unknown/missing/duplicate fields, noncanonical transport,
boolean/float counters and unknown classifications are rejected. Full canonical
binding facts occur once; subsequent rows retain their SHA256. Every row records
separate hard ceilings and actual attempted counts. Only fixed semantic facts,
closed classifications and hashes are recorded: no account identifiers,
credentials, provider bodies, exception text or secrets.
The closed `result_sha256` field binds verified history/seed, strategy decision,
prepared prices/risk outcome and acknowledged order/fill material at their four
corresponding states. Credential/account contents are never hashed into evidence.
Independent parsing and incremental appends share one closed replay reducer;
stable readback still verifies all previously acknowledged bytes. Native reads
use the admitted current byte length within the hard total bounds, rejecting
growth/substitution rather than allocating the maximum buffer on every reread.

Read-only source/prerequisite/session/path/runtime/prior-reservation/paper-history
admissions precede reservation. The deterministic exclusive journal filename is
`arch134-d1r8-SPY-<target>.jsonl`; its identity depends only on SPY/target and never
on revisions, prerequisite digest, caller input, order ID or observation time.
Exclusive creation, flush, fsync and identity/readback verification consume it,
including an empty or partial file. No reclaim, deletion, rename, compensation,
resume or retry exists. Every append is flushed, fsynced and independently read
back through its original identity. Close and independent canonical reread are
required before returning success. Terminal-looking evidence whose final
acknowledgement is ambiguous remains consumed and requires separate read-only
reconciliation; the parser alone never proves operational completion.

After journal reservation, bounded rollback-only readiness qualifies both
existing SQLite stores. Missing/incompatible stores, overlap, links/reparse or
hardlinks, substitution, extra runtime paths and SQLite sidecars fail closed.
The unchanged public `ArmedSessionStore.reserve` atomically claims
`armed-paper-session/v1:SPY:<target>`. Its canonical v1 evidence uses the
nonrecoverable `EXECUTE_STARTED` status with zero historical effect counts.
It is a compatibility fence, not a historical invocation. The historical store
schema is unchanged. A crash between journal and fence sacrifices availability.
Readiness and compatibility attempts have additional explicit ceilings of one.

## State and effects

Transitions are SESSION_RESERVED → SOURCE_AND_D1R7_BOUND →
WRITE_READINESS_STARTED → WRITE_READINESS_CONFIRMED →
LEGACY_SESSION_FENCE_CLAIMED → CREDENTIAL_READ_INTENT →
CREDENTIAL_READ_CONFIRMED → four ordered HISTORY_READ_INTENT /
HISTORY_READ_CONFIRMED pairs → HISTORY_READY → STRATEGY_STARTED →
STRATEGY_DECIDED. NO_SIGNAL ends in FINAL. Otherwise PREPARE_STARTED →
QUOTE_INTENT → QUOTE_CONFIRMED → PREPARED precedes either FINAL / RISK_REJECTED
or EXECUTE_STARTED → ACCOUNT_READ → BASELINE_ORDER_READS → REVIEW_INTENT →
REVIEW_CONFIRMED → POST_REVIEW_ORDER_READS → PAPER_WRITE_INTENT →
PAPER_WRITE_ACKNOWLEDGED → FINAL / PAPER_EXECUTED.

Within a state, accounting rows use the same event with action INTENT/ACK and a
closed counter. These rows do not advance the state machine. They expose each
credential record and order-history page independently. Replay enforces exact
state progression, required counts at transitions and one outstanding intent.
An unacknowledged intent is INDETERMINATE and consumed. Other closed terminals
are BLOCKED and SESSION_EXPIRED. Interrupted journals cannot be resumed.

Ceilings: Alpaca history 4; Alpaca credentials 2; proposal-only Robinhood
credentials 2; credentials total 4; strategy 1; PREPARE 1; quote 1; account 1;
order history 202 conservative; review 1; EXECUTE 1; synthetic fill 1.
The controller stops before page 101 of either order window (200 actual maximum,
within the frozen 202 conservative ceiling) and stops at the first failure.
Credential writes/deletes, refresh/browser/callback/registration, broker
placement/cancellation, options/crypto, scheduler, ACL, D2 and live ceilings are
all zero. Fixed token/client records are each read once and reused in memory.
Public persisted SDK models and a single-yield endpoint-bound bearer Auth
replace refresh-capable OAuth construction. Authentication rejection is terminal.

The fixed D1R7 policy remains MovingAverageCrossoverStrategy 1.0.0; SPY;
windows 2/3; desired quantity 1; starting cash 10000; opening/closing 300 s;
quote age 60 s; snapshot age 600 s; default RiskLimits; MARKET/DAY; zero slippage
and commission. Existing public history, strategy, risk preview, intent bridge,
typed review/read adapter, account resolution and durable accounting are reused.
Current prepared history/risk equality, quote freshness, typed review echo and
empty real-order windows are mandatory before the guarded synthetic mutation.
No broker mutation capability is composed.

NO_SIGNAL qualifies a bounded decision only. RISK_REJECTED is safe but does not
qualify execution. Only completely acknowledged FINAL / PAPER_EXECUTED can later
qualify the execution-dependent paper-soak prerequisite. It grants no soak,
scheduler, D2 or live authority.

## Source registration and next boundary

Checkpoint `arch134-d1r8-d1-session-execution-consumer` maps explicitly to
`robinhood`; preflight/execute/remote_head_env are None. Workflow YAML and its
frozen fallback batch remain unchanged; D1R8 routes dynamically. A final
test-only successor overlay follows D1R7 exactly once. The D1R7 pinned test is
explicitly resolved; all predecessor dictionaries/digests remain unchanged.
Canonical expected inventory is ACTIVE 67 / FULL 182 / ROBINHOOD 101 /
LEGACY 222 / EXHAUSTIVE 404 / GUI 51.

One atomic commit/push and one push-triggered attempt; red means STOP with no
rerun or fix-forward. After terminal green STOP for ChatGPT exact GitHub source
review. No real D1R7 publication or D1R8 execution is authorized.
