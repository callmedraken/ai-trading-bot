# Architecture 147 L40 restricted-live contract

## Scope and acceptance

L40 is an effect-disabled successor contract, prepared from canonical closeout
`f7f13f805ad6a0eea7041cb6d13c561149a13f6e`, tree
`4cf5d8fd19a8089103e9f119e4d8d338a08819d0`, on
`feature/robinhood-live-prototype-current` in
`F:\AI\worktrees\ai-trading-bot-live-prototype-current`.
The local mechanical owner is `live_prototype/live_contract.py`; its pure
admission/reservation results are necessary constraints, never broker effect
authority or a durable persistence implementation. Publication and green CI
require independent ChatGPT exact-source acceptance and integration before L41.
No L40 source, test, constructor or help path reads credentials or a provider.
No readiness label is granted.

P6 `TinyLivePolicy`, `LiveExecutionPlan`, `LiveStateStore`, `OwnedOrderBinding`,
placement and exact-owned cancel remain frozen predecessor contracts. Their
one-shot markers and consumed attempts cannot be imported into a new lifecycle
as unused authority. The successor does not relax their $10 gross/order checks.
D33 remains CONSUMED / BLOCKED / NO RETRY; D34 remains CONSUMED SUCCESSFULLY /
NO RETRY. Their operators are not the production runtime signal service.

## Fixed product and acquisition limits

The product is the private single-user Windows desktop, SPY cash long equity
only, using the retained `BASE_MA35_50_V1` control. No leverage, shorting,
options, crypto, provider fallback or paper soak. FINAL_HOLDOUT remains sealed.
A live session pins source HEAD/tree, configuration and strategy binding.
Research cannot promote or replace that binding. Updates happen manually while
stopped; no self-update, hot reload or automatic state/budget reset.

Initial successor authority permits at most one entry intent and one reducing
exit intent, with at most $10 requested new acquisition and $10 cumulative
requested entry dollars in the durable lineage. It does not grant repeated
sessions, new capital or a replenishing budget. Reserve the complete entry
request at durable intent creation. Restart, new market date, rejection,
cancellation, partial fill and exit do not refund that reservation or restore
the entry attempt. An unused balance is not permission for a second entry.

The $10 bound controls requested new acquisition. Dollar-based market orders
compute shares from a price; the bound does not guarantee fill price, fill
notional, mark-to-market value, maximum loss or exit proceeds. A hard loss or
execution-price promise cannot be inferred from a market order. Fees and
slippage do not authorize a larger request.

## Exact ownership and partial fills

Durable state must bind account fingerprint, SPY, strategy/binding identity,
configuration digest, source HEAD/tree, lifecycle identity, local intent/order
identity, provider order ID when known, baseline broker position, confirmed
cumulative entry/sell fills, exact owned remainder, working remainder, reserved
entry dollars/remaining budget, consumed entry/exit counts, lifecycle and effect
disposition. Raw account identifiers and credentials are not report fields.
L40 defines validated snapshots; L42 must implement their durable store and
factual reconciliation, including exact-order provenance of every fill.

Ownership comes from exact local intent to provider-order binding and confirmed
monotone cumulative fills. An acknowledgement is not a fill. Position alone,
agentic tagging, one SPY row, matching amount, ref_id, or a synthetic fixture is
not ownership. `owned = confirmed buys - confirmed sells`; no negative result.
Every account position must equal the recorded baseline plus exact owned
remainder, with sellable shares corroborated separately. Missing/excess shares,
manual additions, unknown orders, missing ownership binding, account drift or
source/config drift block mutation. A nonzero initial baseline without exact
pre-existing durable ownership proof blocks. The initial implementation may
conservatively require a flat baseline; it must never adopt manual shares.

Partial entry consumes the original full requested-dollar reservation, while
only confirmed filled quantity becomes owned. Cancellation acknowledgement
leaves the order unresolved until terminal broker observation. Partial exit
decreases ownership only by confirmed cumulative sell fill. Rejected/canceled
exit preserves unsold owned shares and consumed exit authority. No automatic
replacement exit is created. Residuals remain recorded and blocked for a
separately reviewed recovery; never round up or sell manual holdings.

## Entry, strategy exit and safety exit

All effects require exact source/config/account/session/binding, fresh factual
read-only reconciliation, valid risk and readiness, and no unresolved effect.
Entry requires a legitimate current BUY while flat, adequate cash, the entry
budget, and sufficient accepted exit capability. No forced signal or fabricated
BUY is permitted. Stale/unavailable signal data blocks ordinary trading.

A strategy exit requires the accepted invested-state SELL decision. A separately
armed SAFETY EXIT may reduce exact-owned risk while the strategy says HOLD; it
bypasses that signal condition only, never ownership, reconciliation, account,
source, session, capability or reducing-risk checks. It is not acquisition and
has no $10 exit-notional ceiling: appreciation above $10 must not by itself
prevent reduction. A safety exit is not an implicit GUI Stop/close action.

Exit is a quantity-based SPY sell, market, regular hours, good for day, no short.
Requested quantity must be positive, no larger than exact durable owned
remainder or broker-available sellable shares, and exactly representable under
accepted broker rules. A whole-account close is forbidden unless identical to
proven owned quantity. Never substitute dollars for owned shares, round upward,
truncate an unsupported residual silently, or increase exposure. If an exact
remaining fraction cannot legally/truthfully be sold, BLOCK and preserve it.

## Outstanding effects, persistence and recovery

L42 must serialize ticks/Start/Stop and persist intent and budget consumption
with successful flush/fsync/close BEFORE invocation. An invoked-unknown effect
excludes every further mutation, including cancel or exit. A factually known
working order excludes new placements; only a separately reviewed exact-owned
cancel may target it after current factual reconciliation, under its own
serialized one-shot authority. No overlapping mutable invocation is allowed.
STOP prevents new work,
joins workers and reconciles read-only; it never silently cancels or liquidates.

After invocation may have reached the broker, timeout, malformed response,
missing provider ID, binding-write failure, audit-write failure or crash means
MAY_HAVE_OCCURRED / UNKNOWN. No blind retry, automatic replacement, fresh
identity, fresh session or ref_id restores authority. Even metadata describing
idempotent retries does not override this stricter project rule.

Every startup/reconnect loads durable state, validates compatible source/config,
resolves the exact account, reads orders and positions, reconciles exact owned
orders/fills and position, reconstructs effect and budget state, then checks
session and current inputs. UNKNOWN cannot self-clear with a flag or elapsed
time; only factual read-only reconciliation under an accepted recovery contract
can establish the actual outcome. It does not unconsume the original intent.
Crash testing must cover before/after persistence and invocation, all writes,
partial fills, canceled remainders, rejection, working/terminal reconnect,
unrelated orders, drift and a new market session.

## Capability facts and L41 evidence boundary

Current tool descriptions were inspected as metadata only; no Robinhood tool
was invoked. Keep the following evidence classes separate:

| Class | Closed fact | Limit |
| --- | --- | --- |
| ADVERTISED | review/place accept side=sell and quantity; fractional market orders in regular hours for eligible accounts, up to six decimal places, no short sells | Six decimal places is an advertised interface bound, not an account/provider fill or residual guarantee |
| SOURCE_SUPPORTED | lower transport passes generic argument mappings; read-only review adapter can express quantity | P6 generates/reviews/places BUY plus dollar_amount only; generic transport is not a guarded sell implementation |
| SYNTHETICALLY_TESTED | local quantity-review and P6 buy/placement fakes exercise their own contracts | No real fractional sell, account eligibility or residual-close qualification |
| PROVIDER/ACCOUNT_UNPROVEN | actual account eligibility, quantity increment/minimum, sell minimum notional, full residual handling and exact sell-review behavior | L41 evidence or explicit first-owned-position qualification is required |

`review_equity_order` is advertised as simulation without placement; review PASS
is not a fill guarantee, order authority or permission to place. L41 never
chains review into placement even when a provider guide suggests doing so.
Never fabricate a position solely to test an exit or review shares the bot does
not own. Review requiring a genuine owned position is
DEFER_TO_FIRST_OWNED_POSITION / DEFER_TO_L43_OWNED_POSITION_EVIDENCE.

| L41_EVIDENCE_REQUIRED | Safest observation | Why |
| --- | --- | --- |
| Account is the intended agentic account and eligible for fractional SPY selling | Read the explicitly selected account/type and SPY get_equity_tradability fractional_tradability/account_type_tradabilities, plus official rules; selection alone is insufficient | Generic metadata does not prove account-specific eligibility |
| Fractional quantity increment and minimum quantity | Official provider rules or exposed capability fields, bound to the exact route/account | Numeric/string schema and observed position precision do not prove legal order sizes |
| Minimum sell notional or explicit absence | Official rule or account/route evidence, including any full-close exception | Unknown is not zero; a quote-based estimate is not a market-fill guarantee |
| Exact residual/full-owned close semantics | Official rule, then exact owned-position review/qualification if required | Prevent oversell, rounding and stranded residual claims |
| Review is nonmutating and echoes exact sell/quantity contract | Official tool contract plus later exact-owned read-only review, never fabricated inventory | Preview must not substitute quantity or create order/approval effects |

Before entry, official route rules plus observed account/instrument eligibility
must establish quantity precision/minimum/notional/full-close rules sufficient
to reduce the fractions that the proposed bounded acquisition can create.
If that cannot be proven, entry remains blocked. A later genuine-position review
can qualify that exact instance and its fills; only this instance-specific
observation may be deferred. Deferral never substitutes for the pre-entry rule
and eligibility proof, and never authorizes acquisition merely to discover
whether disposal is possible.

If an upper quantity rule is represented, record its finite supported bound or
explicit evidence that the route has no maximum. An omitted/zero maximum does
not mean unlimited capacity; conflicting bounded/unbounded claims block.

L41 classifies each fact PROVEN, UNPROVEN_BUT_NOT_REQUIRED_BEFORE_ENTRY,
BLOCKING_L42 or DEFER_TO_FIRST_OWNED_POSITION with evidence digest and rationale.
Unresolved rules needed to enter and exit the bounded fraction block readiness;
unknown facts are never silently classified nonblocking. L41 incompatibility
stops L42 finalization for contract review, with no workaround.

A live L41 collector is deliberately deferred to a minimal source child: current
metadata exposes neither numeric minimum rules nor an account fractional-sell
attestation, and truthful review may need the first owned position. L40 adds no
provider dispatch or speculative collector claiming these facts. After L40
acceptance/integration, first freeze an exact read-only observation plan from
these remaining facts, source-review any required collector, then invoke only
the independently reviewed observation. No consumed P6/D33/D34 retry.

## Dependency and publication plan

L40 acceptance/integration -> L41 capability evidence -> consolidated L42 + I53
source -> Q61 human native Windows UAT -> Q62 fresh protected read-only
readiness -> canonical DOCS_ONLY readiness closeout -> L43 bounded genuine
entry/recovery/exact-owned safety-exit qualification -> Q63 exact delivery.
Labels define dependencies, not permission from numeric ordering.

Use the existing `arch147-live-prototype` source-only checkpoint with mapped
GitHub-owned FULL. L40 adds its focused test to that current owner; it does not
add a provider gate or workflow family. Before one atomic commit/admission/push,
run affected pure tests, current/historical authority and both publication
contexts, combined Ruff and diff checks. No local FULL or manual CI dispatch.
Stop after terminal CI for independent exact-source acceptance/integration;
effect-free L42 analysis may continue unpublished.

The principal next broad source publication should consolidate durable
controller/ownership/budget, exact-owned exits/recovery, reusable runtime Alpaca
inputs, accepted binding, LiveApplicationService, protocol-based GUI service,
explicit live/synthetic composition, independent research worker, guarded
emergency operators and Q62/Q63 support. Runtime inputs reuse accepted D34
published-close semantics, never its consumed operator: exactly 60 completed
XNYS sessions, SPY 1Day, adjustment=all, asof=-, SIP/USD, no fallback. Refresh
when a new completed published session can exist, cache sanitized facts, show
stale evidence truthfully and block trading on it.

Native Q61 and real Q62/L43 evidence are distinct from source tests. Q61 has no
broker mutation; Q62 has no place/cancel/sell and requires fresh exact source,
configuration, account, capability, ownership, budget, session/input and recovery
truth. L43 may enter only on a genuine BUY with at most $10 requested new risk;
otherwise record NO_ACTION_SIGNAL. Qualification exits use only the exact owned
fill and separate consumed reducing authority. Any ambiguity stops mutation.
Q63 assembles accepted identities, state/backup locations, real startup/stop,
recovery/cancel/safety-exit commands and evidence; no invented readiness label.

## Verification surface

Focused mechanical tests: `tests/live_prototype/test_live_contract.py`.
Existing route/absence-of-effects checks:
`tests/runtime/checkpoint_runner/test_arch147_prototype.py`.
L42 must add crash/restart and concurrency/failure injection, actual durable
store/reconciliation and fake end-to-end application tests before publication.
No L40 PASS substitutes for those unimplemented components or real evidence.

## Effect-free L42/I53 preparation from the Luna audits

These are implementation assignments for the next accepted contract, not source
acceptance or permission to skip L41. Keep edits disjoint and compose one
candidate centrally before publication.

| Exclusive semantic surface | Suggested current files | Focused verification |
| --- | --- | --- |
| Durable schema, journal/fold, budget and exact order provenance | new durable_state.py | new test_durable_state.py; crash at write/flush/fsync/close and fold boundaries |
| Serialized decision/effect controller and read-only recovery | new live_controller.py | new test_live_controller_recovery.py; concurrent tick/Start/Stop and no duplicate invocation |
| Reusable current Alpaca input/cache | new signal_provider.py | new test_signal_provider.py; 60 sessions, holiday/DST/early close, cutoff/cache/failure freshness |
| Mode-specific source/config and immutable live binding | additive configuration owner, preserving synthetic/research contracts | configuration tests; missing or mismatched identities block |
| Cached workers, report isolation and Start/Stop | new live_service.py | new test_live_service.py; no I/O at construction/snapshot, shutdown confirmation |
| Protocol, window and explicit composition | contracts.py, window.py, scripts/run_live_prototype.py | launcher/application acceptance; no implicit mode fallback or generic effects |
| Guarded readiness, safety exit and delivery package | later separately reviewed current operator files | fake effect counters, interlocks and truthful failure evidence before host use |

`PrototypeApplicationService` currently declares snapshot/submit only, while
`PrototypeWindow` additionally calls request_report/shutdown_complete. Generalize
the protocol's real required surface before replacing concrete synthetic typing.
Live state cannot reuse the synthetic fresh-root marker as a durable store.
`SelectedStrategyBinding` is research-only/live_eligible=False; the report reader
returns descriptive ResearchView and cannot become live strategy authority.
`CompletedSignalInputs` structurally permits a historical Robinhood basis, so
runtime live admission must explicitly require ALPACA_ALL_ADJUSTED_PRICE_V1.

Do not build runtime reads by repeatedly creating fresh D34 one-shot observation
services. Use the public pure session/cutoff/request/math building blocks and a
neutral current runtime composition. If needed, add a reviewed public pure
response-to-input helper while preserving historical D34 source behavior; never
import its private helpers or operator. Runtime refresh/failure scheduling is a
new deterministic source-owned policy, not recycled D34 attempt authority.

| Required adversarial scenario | Expected result |
| --- | --- |
| Manual initial SPY, extra manual shares, smaller/larger position, missing/wrong exact order ID, stale account | Block mutation; never adopt by similarity or account-wide position |
| $10 entry, over-$10 request, partial/rejected/canceled entry, restart/new date | Cap requested dollars; retain full consumed reservation and one-entry allowance |
| Actual fill dollars or marked value above $10 | Preserve factual amounts; allow otherwise valid reducing exit without inventing a fill/loss guarantee |
| Six-decimal fraction, unsupported increment, below-minimum residual or provider-suggested different quantity | Exact validated quantity only; unsupported fraction blocks and remains recorded |
| Partial/rejected/canceled exit, duplicate/decreasing cumulative fills | Count exact confirmed monotone fills once; consume exit allowance, preserve remainder |
| Timeout before/after receipt, malformed response, missing provider ID, failed binding/audit/fill write | Persist uncertainty; read-only recovery only, no replay/fresh-identity workaround |
| Crash before/after each persistence step and provider boundary | No invocation before durable close; possible invocation consumes authority and budget |
| Duplicate Start, concurrent ticks, Stop during read or working order | Serialize, prevent new effects, join workers; no implicit cancel/liquidation |
| Restart/reconnect working, terminal, unrelated order, source/config drift | Factual exact-owned reconciliation before readiness; unknown never self-clears |
| New published session, stale cache, Alpaca down, Robinhood read failure | Cached display remains truthful; unavailable/stale prerequisites block trading |
| Concurrent research, malformed report, GUI refresh/close | No live-binding mutation, independent failure containment, cached rendering and confirmed shutdown |

Q61 is human native Windows evidence after accepted L42/I53: help/launch, all
five pages, 1366x768 and 1920x1080/scaling, keyboard navigation, unavailable facts,
Start/Stop/close during work, no orphan workers, fresh isolated synthetic state,
report loading, and disarmed real composition with zero broker mutations.
Record exact source/config/environment and sanitized observations under a fresh
`F:\AI\temp\arch147-q61-<unique-id>` evidence directory; preserve state.
Normalize worktree identities with Resolve-Path, use an invoked guarded
PowerShell block and an explicit approved Python interpreter. Existing launcher
supports synthetic only; do not invent live/readiness/recovery commands before
their source exists. Q63 must package the actual accepted commands and durable
state/backup/restore procedure with Q61/Q62/L43 evidence and exact interlocks.
