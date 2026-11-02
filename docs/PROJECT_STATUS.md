# AI Trading Bot — Project Status

## Current checkpoint — Architecture 147 P5B-lite C2 source correction

P5B source was accepted and integrated at `c820f09edb68c85ff16eb77034ab4e3c15365b3e`;
develop integration run `41389597879` succeeded. The first protected invocation
stopped before attempt creation because `python -m` loaded the runner as both
`__main__` and `scripts.checkpoint_runner`, causing a CLI module-identity
registration mismatch. Normal source authority and Git identities were clean.
The C2 correction changes only registration comparison; provider/read
implementation remains unchanged. No credential, provider, broker or live
effect occurred, and the protected provider attempt remains unused.

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
Its corrective source is pending exact review, terminal mapped FULL and
integration reuse.
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
