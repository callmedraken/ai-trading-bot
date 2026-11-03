# AI Trading Bot — Project Status

## Current checkpoint - P6 kill-operator source candidate pending exact review

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
The additive exact-owned kill-operator source candidate is pending independent
exact-source review and integration. It adds create-only placement ownership,
a separate kill arm, at most one exact-owned cancel and bounded terminal
reconciliation without liquidation. This candidate is not accepted/integrated.
P6 preflight has not run and live execution has not occurred.

## Immediate next step

The immediate next step is ChatGPT exact-source review of the published P6
kill-operator candidate, its mapped GitHub FULL evidence and integration
readiness. P6 preflight must not run until that boundary is accepted,
integrated and closed out. A source PASS grants no provider, credential,
broker or live authority. P7 still follows the P6 live trial and reconciliation
boundary.

## Roadmap

    P1-P4 accepted; real research and desktop lifecycle smoke complete
    P5A accepted; B1 35/50 SPY binding and B2 OPEN_REPLAY smoke complete
    P5B-lite accepted/integrated; reviewed read-only provider baseline PASS
    P6 baseline integrated; kill-operator source candidate pending exact review
    P7 production monitoring / backup / restart / reconnect / credential rotation

LIVE remains disabled. FINAL_HOLDOUT remains sealed. Architecture 131 stays a
frozen historical contract. Current paper accounting remains independent of
Robinhood observations. P4 accepted smoke is not repeated; unclean process
recovery remains a separate boundary.
