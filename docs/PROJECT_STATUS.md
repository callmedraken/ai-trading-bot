# AI Trading Bot — Project Status

## Current checkpoint — Architecture 147 P5B-lite source preparation

Real adjusted acquisition and the frozen filtered-trend campaign are complete.
B1 is accepted/integrated at `6924085675d9058b79324120faec9cb4025b6329`,
tree `e18653587334655c380dbc528510a364d58aaf19`. Feature CI `41366532747`
and develop integration CI `41367640239` succeeded.

The accepted PAPER_EVALUATION binding is FILTERED_TREND_BASE_MA,
`filtered-trend-base-ma/v1`, SPY, fast=35 / slow=50. The external bundle
remains mandatory; P3's descriptive 55/100 candidate is not a fallback.
RiskManager, OrderEngine, paper accounting, kill/new-buy controls and durable
cursor/idempotency remain the local simulated-paper authorities.

The first B2 import attempt was a non-consuming STOP. Corrected B2 passed
IMPORT_SOURCE_AUTHORITY and OPEN_REPLAY_SMOKE: first fill BUY 1 SPY at cursor
51, restart 51 -> 52, fill count 1 -> 1, no duplicate fill, network attempts
0, FINAL_HOLDOUT accesses 0, final runtime STOPPED. Production P5 SQLite and
lifecycle state remained absent. No prolonged paper soak is planned.

P5B-lite adds source for a separate Robinhood read/account/reconciliation
baseline through the official Trading MCP. It observes existing account
activity and expects zero locally attributable broker effects. It does not
supply paper risk/account authority, review an order or enable broker mutation.
Its source is pending exact review, terminal mapped FULL and integration.
See the [P5B-lite contract](architecture/147-p5b-robinhood-read-reconciliation.md).

## Immediate next step

Complete the single P5B-lite atomic publication and GitHub-owned canonical FULL.
ChatGPT then reviews the exact source and integration readiness. Only after
accepted develop integration may ChatGPT issue the one protected read-only
`ops.ps1 preflight arch147-p5b-robinhood-read-reconcile` boundary. Do not invoke
it during implementation, admission or CI. No OAuth/provider read has occurred
in this current desktop lineage. A source PASS grants no provider authority.

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
