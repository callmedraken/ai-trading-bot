# Architecture 147 P6 — Tiny live production boundary

P6 is the first narrowly bounded production-trial source boundary. It is an
additive successor to the accepted P5B Robinhood read/reconciliation baseline;
P5B remains independently read-only and its transport is not extended.

## Frozen policy

`TinyLivePolicy` is the only policy accepted by this checkpoint:

- SPY only;
- `FILTERED_TREND_BASE_MA`, `filtered-trend-base-ma/v1`, accepted 35/50;
- purpose `LIVE_PRODUCTION_TRIAL`;
- long equities only, no leverage, shorting, options or crypto;
- at most one working order;
- maximum `$10.00` order and `$10.00` bot gross exposure;
- regular-hours GFD market orders with a dollar amount.

The historical P5A `PaperStrategyBinding` remains
`PAPER_EVALUATION`, has no qualification policy, and remains `live_eligible=False`.
P6 is not a promotion of that binding.

## Boundaries

The P6 transport discovers the complete advertised tool surface and validates
the review/place/cancel schemas before any call. Review and placement must
advertise `account_number`, `symbol`, `side`, `type`, `market_hours`,
`time_in_force` and `dollar_amount`; placement must also advertise `ref_id`.
The stable base fields `account_number`, `symbol`, `side`, `type` must be in
both provider unconditional required sets; cancel must advertise and require
`account_number` and `order_id`. P6 itself requires dollar sizing. The provider
may expose `quantity` as an alternative and need not include `dollar_amount`
in JSON Schema `required`. P6 never sends quantity or falls back to shares.
`LIVE_DOLLAR_ORDER_SCHEMA_MISSING` means this P6 dollar-order capability surface
is absent, not that the provider must unconditionally require dollar sizing.

Review receives exactly those seven order fields, with SPY/buy/market,
regular_hours/gfd and the bounded dollar amount. Placement receives the same
order contract plus `ref_id`; review receives no placement idempotency field.
Neither sends `client_order_id`, `idempotency_key`, limit/stop/tax-lot fields
or quantity. Provider `ref_id` is the canonical UUID5 of immutable
`plan.plan_sha256` under fixed P6 namespace
`5c888a69-0b50-5ff8-90c0-b98d4b0d04fb`. It is deterministic, account-independent
and separate from the unchanged 64-character local ownership SHA256 and durable
attempt marker; it never grants retry authority.

Review parsing explicitly receives that exact request contract. Provider echoes
must confirm SPY, buy, market and the exact dollar amount. Regular hours and GFD
are bound request facts; missing echoes are allowed, contradictory echoes block.
`data.order_checks` must be an object: `{}` is clean and any nonempty object
blocks READY with only `ROBINHOOD_ORDER_CHECKS_PRESENT` in sanitized evidence.
Optional `customer_approval_required` must be boolean; true blocks autonomous
READY with `ROBINHOOD_CUSTOMER_APPROVAL_REQUIRED`. The separate fetched approval
setting still blocks independently. Raw alerts and approval reasons are never
copied into evidence. The review digest binds the exact order contract and
sanitized alert/approval state, without accounts or provider text.
There is no generic public tool dispatcher. The mutation methods are explicit
`review_equity_order`, `place_equity_order`, and `cancel_equity_order`, and the
cancel path accepts only one exact owned order identifier.

Preflight admits only a clean source whose remote P6 feature branch and remote
`develop` both equal the local HEAD, and whose prospective-develop/current
source authority passes. Those guards run before the external attempt
directory is created. It then discovers exactly one matching PASS report under
the stable external P5B checkpoint root, requiring the accepted P5B HEAD/tree,
zero mutation/review/place/cancel effects and unchanged production state. It
resolves the canonical Agentic account, compares the runtime fingerprint,
confirms zero positions and working orders, acquires at least 60 completed raw
regular daily bars through the strict Robinhood history parser, composes the
existing `RiskManager`, and returns a sanitized immutable plan. Preflight never
places or cancels.

Execution is disarmed by default and requires both the reviewed arm token
`AI_TRADING_BOT_P6_LIVE_ARM=LIVE_SPY_MAX_10_USD` and the exact plan SHA256 in
`AI_TRADING_BOT_P6_PLAN_SHA256`. It repeats account, broker-state, review and
source/session drift checks. The protected runner repeats the integrated
feature/develop source admission before creating its execution attempt, so a
feature-only source cannot run P6. It creates a durable attempt marker before
place, places at most once, and classifies an exception as `MAY_HAVE_OCCURRED`
with no automatic retry. Placement count and attempt consumption are separate:
a failure before marker creation has zero place calls; an existing or partial
marker consumes the attempt even if placement has not been invoked. After
placement invocation, parsing, observation, reconciliation and lifecycle-write
exceptions retain exactly one place call, a consumed attempt and
`MAY_HAVE_OCCURRED`. Diagnostic-write failure cannot erase that classification.
Only a successfully persisted terminal reconciliation returns a receipt; all
consumed attempts prohibit another placement on a second invocation. The marker
and any partial lifecycle evidence are preserved without repair. Post-trade
history and position reconciliation is finite and sanitized: only terminal broker states reconcile successfully;
partial, pending, open or other working states remain stopped with the consumed
attempt marker. The first successful fill disables additional buys by default;
the kill path may cancel only the exact owned open order and never liquidates a
fill. Cancellation consumes its own create-only marker before invoking the exact
owned order's cancel method. A request acknowledgement or transport exception
returns one cancel call, zero placement calls, a consumed attempt and
`MAY_HAVE_OCCURRED`, without a terminal cancellation receipt. An existing cancel
marker blocks another invocation with zero new calls and preserves uncertainty.
Marker persistence failure before invocation reports zero calls and retains any
partial marker as consumed. The exact-owned kill operator below supplies the
separate operator boundary. Operator reachability is implemented and accepted
in the current P6 source, but the operator remains protected and disarmed until
it is explicitly invoked under its reviewed interlocks.

The GUI is presentation-only. It may display sanitized cached plan/state facts,
but it has no arm, place or cancel control. P6 state is separate from the P5
simulated-paper store and is not created by imports, tests, admission or CI.

No provider, credential, broker, order or live-state effect is performed by the
source checkpoint itself. The registered preflight and execute boundaries are
later operator actions and are not run during publication.


## Exact-owned-order kill operator

This additive current capability is accepted/integrated at implementation source
`f1558b97e60bb32fae2a9f1de23226d261418d99`, tree
`ed4a5a962aa6edd98235bf90dffb10e84a935b40`, under
`arch147-p6-tiny-live` on `feature/robinhood-p6-tiny-live-current`. It grants no
protected invocation by itself: the operator remains protected/disarmed until
its reviewed interlocks are explicitly satisfied. No real kill invocation has
occurred. The GUI remains presentation-only, with no arm, place or cancel
controls. P6 read-only preflight is next; live placement remains a later,
separate protected boundary.

Placement requires a root object, `data` object, `data.order` object and a
usable `data.order.id`, passed through the existing provider-order validator
(1-128 ASCII letters, digits, hyphens or underscores). Flat `data.id` and
`data.order_id` are rejected. `ref_id` is never a provider order ID substitute.
Missing or malformed nested IDs retain one place call, consumed authority,
`MAY_HAVE_OCCURRED` and no retry. Before any subsequent broker observation, it creates and fsyncs
`owned-order.json` alongside the existing P6 placement marker under
`F:\AI\desktop-bot-state\p6`. Its schema is `arch147-p6-owned-order/v1` and
binds the immutable plan SHA256, deterministic `p6-local-order/v1` SHA256 and
exact provider order ID. This protected local binding retains the raw ID for
cancellation; kill evidence uses its SHA256.
Existing bindings, including identical, mismatched or partial bindings, are
never overwritten or repaired. A placement marker or existing binding blocks
another placement. Binding persistence failure after invocation remains one
place call, consumed, `MAY_HAVE_OCCURRED`, and no automatic retry. Missing
ownership evidence never permits guessing from broker order similarities.

The source-owned CLI is `python -m trading_bot.desktop_live.kill_operator`.
It accepts only `--plan`, `--plan-sha256` and `--evidence-dir`; there is no
provider-order-ID input or generic tool dispatcher. Use a Python environment
bound to this exact source and launch from the admitted repository root.
The evidence destination must be fresh, absolute, outside the source tree and
free of aliases/reparse points. Admission reuses the existing P6 evaluator:
clean source, reviewed origin, remote P6 feature == local HEAD, remote develop
== local HEAD, prospective-develop/current authority PASS and stable HEAD/tree.
This admission runs before transport or credential construction. Then the
immutable READY plan and supplied exact digest, plan source, zero initial P6
position/order baseline and durable ownership binding must validate. The
binding must name the same plan and deterministic local order. Last, require
`AI_TRADING_BOT_P6_KILL_ARM=CANCEL_EXACT_OWNED_P6_ORDER`.
The kill path has no dependency on `AI_TRADING_BOT_P6_LIVE_ARM`; disabling
BUY/placement authority must leave the kill boundary available.

After local admission, create-only sanitized external attempt evidence is
persisted before constructing the existing explicit current-live transport.
Resolve the canonical Agentic account and require its fingerprint to equal
the plan. A bounded observation uses the existing strict account, portfolio,
position, quote and Agentic-order parser and its finite page/item/seven-day
window limits. Find exactly the ID from the binding; no other SPY order can
substitute. SPY, buy, Agentic placement and the plan's target session corroborate
ownership. Missing, duplicated, incompatible or unknown-state observations
stop without cancellation. The seven-day window never authorizes a fallback
for an older missing order.

An already terminal order yields zero cancel calls and truthful terminal facts.
FILLED remains a surviving position; CANCELED/CANCELLED and REJECTED are
reported only with internally consistent cumulative fills and SPY position.
No sell, liquidation, options, crypto, review or placement call is reachable
from this operator. Terminal cancellation of a partially filled order means
cancellation of the remainder: cumulative fill must not decrease and SPY
position must exactly equal the plan baseline plus the cumulative fill. The
filled position survives and additional BUY remains disabled. Rejection
requires zero fill. FILLED requires positive fill and matching position.

For a working bound order, `kill_owned_order` reloads the durable binding,
requires it still equals the observed binding,
creates its existing cancel-attempt marker and invokes cancel at most once.
A cancel API acknowledgement is never terminal proof. One deterministic,
immediate bounded read-only observation follows an acknowledged invocation;
there is no sleep, polling loop or automatic retry. Still-working, missing,
malformed, account-drift or inconsistent post-cancel observations are STOPPED,
consumed and `MAY_HAVE_OCCURRED`. Cancel transport failure retains one call,
consumed uncertainty and no retry. Marker write/race failures preserve the
accepted primitive's per-invocation counts and consumption semantics.

An existing cancel marker permits a fresh bounded read-only observation, never
a second cancel. A now-terminal order reports terminal broker facts with zero
new cancel calls; a still-working order remains consumed/unreconciled. Never
erase, replace or repair the marker. Every recovery invocation needs fresh
external evidence and the same local/source/kill interlocks.

Evidence uses fixed diagnostics and order-ID SHA256 rather than the raw ID,
and records HEAD/tree, plan/local-order identity, pre/post states, cancel count,
fill/position quantities, disposition, consumption, reconciliation and
`automatic_retry=NO_AUTOMATIC_RETRY`. It excludes raw account identifiers,
OAuth material and provider exception text. Evidence-write failure preserves
returned effect/count/consumption facts and reports STOPPED. The typed kill
result is separate from the placement `ExecutionResult` and receipt contract.
No source test, admission or CI invocation runs this real CLI or creates
production P6 state. No P6 preflight follows this publication automatically.


## Current provider-contract correction and preserved observations

This correction starts at integrated `c8eba0fd7fe8f629820b28db40aa5a4e8de7c5e0`,
tree `bdeddc8e1c2a2d5f7475e42c91f0dccc800974e0`. It changes only current P6
transport/order handling, synthetic regressions and directly related docs;
shared runner, registry, workflow and historical authority are unchanged.
Review requires the observed direct `data` object, not synthetic `data.result`.

Preserve both external P6 read-only preflight attempts under
`F:\AI\temp\ai-trading-bot-checkpoints` without editing or rerunning them:

- `arch147-p6-readonly-preflight-ba74d5b258a54279916537e5cf7435d5` returned
  historical opaque `P6_PREFLIGHT_BLOCKED` from pre-truthfulness source.
- `arch147-p6-readonly-preflight-fa90be4add304d82a6bcc007a1af2ab4` returned
  `P6_PLAN_BUILD_BLOCKED` / `LIVE_DOLLAR_ORDER_SCHEMA_MISSING`; all provider
  invocation counts, including review/place/cancel, were zero, production state
  was unchanged and source identity remained stable.

The two subsequent schema-only observations invoked no Robinhood tools and are
diagnostics, not P6 preflight attempts. Their observed input/output contract is
the basis for this correction; implementation must not repeat those observations.
After independent exact-source acceptance, exact ff-only integration and terminal
develop certification reuse, the next protected step is exactly one fresh P6
read-only preflight through the non-terminating guarded wrapper. Source success
never authorizes live placement. Neither prior attempt is retried or repointed.
