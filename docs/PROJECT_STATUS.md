# AI Trading Bot — Project Status

## Current correction — completed-close composition; source review pending

The history-only design was abandoned after four consumed P6 preflights. The
replacement starts at HEAD `bbffca862719c61c445952403877b543a80f3111`, tree
`a267b8295d965b8d7d22a9072e27afde46eed45e`. P6 intentionally composes the exact
60 selected completed XNYS sessions from 59 historical daily closes and one typed
Robinhood official close for the final session. No synthetic OHLC bar is created.
The existing baseline quote read supplies that official close: one quote call
and one historical call remain the ceilings. Missing, stale, interpolated or
mismatched official-close data blocks; no quote-price substitution or retry exists.
The plan binds `ROBINHOOD_HISTORY59_PLUS_OFFICIAL_CLOSE_V1` and the new signal basis.

All four consumed attempts and diagnostics remain untouched. Source work and
synthetic tests perform no real OAuth/provider/preflight/order/live operation.
After independent exact-source acceptance, exact fast-forward integration and
terminal develop certification reuse, the next protected boundary is one fresh
guarded read-only preflight of this new architecture. A failure to obtain the
exact official close stops this path; a dedicated strategy market-data source
would then require a new design. Live placement remains unauthorized.

## Current checkpoint - P6 kill-operator accepted/integrated

The accepted P5B Robinhood read/reconciliation baseline is the exact source
`7ff86d06a99bcdf349d5e20846d139a554d8be46`, tree
`095c51cedc1c656616123c3acf88148b16b71aa2`. Its protected evidence is PASS:
Agentic account resolution, SPY quote, portfolio, positions and order schemas
worked; position and order baselines were zero; review/place/cancel and all
mutation counts were zero; and production state remained unchanged. The
account fingerprint is loaded from the external report and is not hard-coded
in source or documentation.

The P6 placement and cancel consumed-attempt truthfulness corrections are
complete and accepted/integrated at exact HEAD
`14c2a20b19381ca9ffb27d67faa873d8cecc283b`, tree
`a949f9bad6f1538d2243c489cdddfc02deaf4f1d`. Feature CI run `41535508444`
passed on attempt 1 with canonical FULL. Develop CI run `41554499626` passed on
attempt 1 and reused the exact feature certification. No provider or live
effect occurred during source publication or integration.

P6 is a separate source/effect boundary in
`F:\AI\worktrees\ai-trading-bot-p6-tiny-live-current`, branch
`feature/robinhood-p6-tiny-live-current`. It is restricted to SPY,
`FILTERED_TREND_BASE_MA / filtered-trend-base-ma/v1`, the accepted 35/50
configuration, long equities, one working order and a maximum $10 order and
$10 gross exposure. P5A remains `PAPER_EVALUATION` with `live_eligible=False`;
P6 does not rewrite or promote that historical binding.

The P6 source includes a schema-discovered explicit live transport, immutable
sanitized plans, P5B continuity checks, completed raw daily history, existing
RiskManager composition, bounded review/reconciliation, create-only attempt
markers and a disarmed-by-default execution entry point. No provider,
credential, broker, order, live-state or FINAL_HOLDOUT effect occurs during
this source checkpoint. The GUI exposes cached sanitized state only and has
no arm, placement or cancellation control.
The additive exact-owned kill-operator implementation is accepted/integrated at
implementation source `f1558b97e60bb32fae2a9f1de23226d261418d99`, tree
`ed4a5a962aa6edd98235bf90dffb10e84a935b40`. Feature canonical FULL run
`41575733423` passed on attempt 1; develop integration CI run `41588005188`
passed on attempt 1 and reused the exact feature certification. The implementation
has an exact-owned durable plan/local/provider binding, a separate kill arm,
bounded reconciliation, no arbitrary provider-order input and no liquidation.
No protected provider, credential, broker, preflight, placement, cancellation,
production-state or FINAL_HOLDOUT effect has occurred.

## Immediate next step

Complete synthetic focused verification, FEATURE/PROSPECTIVE_DEVELOP admission,
one atomic publication and terminal GitHub-owned FULL for the 59+1 correction.
Independent exact-source review precedes integration and any fresh preflight.
The parallel research next step is a bounded strategy/filter comparison contract
using the existing platform, followed by explicit selection and a separately
reviewed small-money live pilot. Paper soak is not the current priority.

## Roadmap

    P1-P4 accepted; real research and desktop lifecycle smoke complete
    P5A accepted; B1 35/50 SPY binding and B2 OPEN_REPLAY smoke complete
    P5B-lite accepted/integrated; reviewed read-only provider baseline PASS
    P6 kill-operator accepted/integrated; 59+1 close-composition source review next, then
        integrated/certified read-only preflight, followed by one
        explicitly armed <= $10 live trial and post-trade reconciliation
    P7 production monitoring / backup / restart / reconnect / credential rotation

LIVE remains disabled. FINAL_HOLDOUT remains sealed. Architecture 131 stays a
frozen historical contract. Current paper accounting remains independent of
Robinhood observations. P4 accepted smoke is not repeated; unclean process
recovery remains a separate boundary.
