# AI Trading Bot — Project Status

## Current checkpoint — Architecture 147 P6 tiny-live source checkpoint

The accepted P5B Robinhood read/reconciliation baseline is the exact source
`7ff86d06a99bcdf349d5e20846d139a554d8be46`, tree
`095c51cedc1c656616123c3acf88148b16b71aa2`. Its protected evidence is PASS:
Agentic account resolution, SPY quote, portfolio, positions and order schemas
worked; position and order baselines were zero; review/place/cancel and all
mutation counts were zero; and production state remained unchanged. The
account fingerprint is loaded from the external report and is not hard-coded
in source or documentation.

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
no arm or placement control.

## Immediate next step

Complete the single P6 atomic publication and GitHub-owned canonical FULL.
ChatGPT then reviews the exact source and integration readiness. Do not invoke
the registered P6 preflight or execute boundary during implementation,
admission or CI. A source PASS grants no provider, credential, broker or live
authority; any later protected action requires the separately reviewed exact
P5B evidence and operator interlocks.

## Roadmap

    P1-P4 accepted; real research and desktop lifecycle smoke complete
    P5A accepted; B1 35/50 SPY binding and B2 OPEN_REPLAY smoke complete
    P5B-lite read/account/reconciliation source and then one reviewed read-only preflight
    P6 separate source/effect checkpoint for tiny explicitly armed live with hard notional limits
    P7 production monitoring / backup / restart / reconnect / credential rotation

LIVE remains disabled. FINAL_HOLDOUT remains sealed. Architecture 131 stays a
frozen historical contract. Current paper accounting remains independent of
Robinhood observations. P4 accepted smoke is not repeated; unclean process
recovery remains a separate boundary.
