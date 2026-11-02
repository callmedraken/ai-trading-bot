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
the review/place schemas before any call. `dollar_amount` is required; a
missing dollar capability blocks the trial and cannot fall back to shares.
There is no generic public tool dispatcher. The mutation methods are explicit
`review_equity_order`, `place_equity_order`, and `cancel_equity_order`, and the
cancel path accepts only one exact owned order identifier.

Preflight loads the external accepted P5B report, resolves the canonical
Agentic account, compares the runtime fingerprint, confirms zero positions and
working orders, acquires at least 60 completed raw regular daily bars through
the strict Robinhood history parser, composes the existing `RiskManager`, and
returns a sanitized immutable plan. Preflight never places or cancels.

Execution is disarmed by default and requires both the reviewed arm token
`AI_TRADING_BOT_P6_LIVE_ARM=LIVE_SPY_MAX_10_USD` and the exact plan SHA256 in
`AI_TRADING_BOT_P6_PLAN_SHA256`. It repeats account, broker-state, review and
source/session drift checks, creates a durable attempt marker before place,
places at most once, and classifies an exception as `MAY_HAVE_OCCURRED` with no
automatic retry. Post-trade history and position reconciliation is finite and
sanitized. The first successful fill disables additional buys by default; the
kill path may cancel only the exact owned open order and never liquidates a
fill.

The GUI is presentation-only. It may display sanitized cached plan/state facts,
but it has no arm, place or cancel control. P6 state is separate from the P5
simulated-paper store and is not created by imports, tests, admission or CI.

No provider, credential, broker, order or live-state effect is performed by the
source checkpoint itself. The registered preflight and execute boundaries are
later operator actions and are not run during publication.
