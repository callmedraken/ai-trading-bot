# AI Trading Bot — Current Handoff

## Current boundary — P5B-lite source only, no provider attempt

Implementation worktree:
`F:\AI\worktrees\ai-trading-bot-p5b-read-reconcile-current`.
Branch: `feature/robinhood-p5b-read-reconcile-current`.
Direct parent must remain accepted develop:

    HEAD 6924085675d9058b79324120faec9cb4025b6329
    TREE e18653587334655c380dbc528510a364d58aaf19

B1 is accepted/integrated. Feature CI `41366532747` and develop integration
CI `41367640239` succeeded. Real adjusted acquisition and the frozen
filtered-trend campaign are complete. Accepted binding:

    FILTERED_TREND_BASE_MA / filtered-trend-base-ma/v1
    SPY / fast=35 / slow=50 / PAPER_EVALUATION / live_eligible=False
    campaign 48ae05d5-ede1-5461-9da9-b5d7744cefad
    bundle 3b86c5e0-6053-53af-a499-d297265f3cd8
    candidate 31397ce5-5dc7-5887-b29a-efc5075c5ebf
    bundle SHA256 80ff955ce2544f0799d8c1fdc1f77f9c337ecf2b25d01731dda1add90ef392f7

B2's first import attempt was a non-consuming STOP. Corrected B2:
IMPORT_SOURCE_AUTHORITY=PASS; OPEN_REPLAY_SMOKE=PASS; first fill BUY 1 SPY at
cursor 51; restart 51 -> 52; fill count 1 -> 1; no duplicate fill; network
attempts 0; FINAL_HOLDOUT accesses 0; final runtime STOPPED. Production P5
SQLite and lifecycle remained absent. Do not repeat the smoke or start a soak.

## Next milestone — P5B-lite read baseline

Registered checkpoint: `arch147-p5b-robinhood-read-reconcile`.
Canonical certification: GitHub-owned FULL, broad-1 through broad-7.
Verify/source authority is effect-free; preflight is the sole later provider
entry; execute=None. Source publication is pending exact-source review and
integration. Do not merge as part of implementation.

The successor transport exposes get_accounts, get_portfolio,
get_equity_positions, get_equity_quotes and get_equity_orders only. Frozen
Architecture 131 transport bytes and its historical four-tool allowlist remain
unchanged. P5A's accepted external bundle, 35/50 SPY binding, OPEN_REPLAY,
RiskManager/OrderEngine, controls and idempotency remain authoritative.

After terminal feature green, ChatGPT owns exact-source review and
fast-forward integration readiness. Only after accepted develop integration
will ChatGPT issue the bounded protected command:

    .\ops.ps1 preflight arch147-p5b-robinhood-read-reconcile

This is future readiness material, not authorization to run it now. The
preflight requires exact clean source matching both feature and remote develop;
creates fresh external attempt/evidence files; permits only necessary official
OAuth/token-storage access, capability discovery, and the five reviewed read
tools; has no retry loop; and requires unchanged production SQLite/lifecycle
identities. Maximum review, preview, placement, cancel, broker mutation, P5
financial-state mutation, FINAL_HOLDOUT access and Alpaca call counts are zero.
Sanitized evidence contains only account SHA256 and bounded observation
summaries/commitments. Raw account number, tokens and provider payloads are not
persisted. See [contract](architecture/147-p5b-robinhood-read-reconciliation.md)
and [validation](validation/arch147-p5b-robinhood-read-reconciliation.md).

No OAuth, Credential Manager read, Robinhood MCP request, brokerage read,
production launch or live effect is performed during this source checkpoint.
After a successful separately reviewed read baseline, continue toward P6 tiny
explicitly armed live through a separate source/effect checkpoint with hard
notional limits; no prolonged paper soak is planned. LIVE remains unavailable
until those separate gates are implemented and accepted.
