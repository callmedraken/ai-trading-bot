# AI Trading Bot — Current Handoff

## Current boundary — Architecture 147 P4 complete; P5 architecture current

Current accepted develop source before this P4 operational closeout:

    HEAD 545f21621c15c682f19d10df3a3d1ecf86f8a77c
    TREE 07bb44a2975c44fd62e68a9cc8f3b9f99a0bbd8e
    branch develop

P4 source is accepted/integrated. Feature CI #816 / run `41175037719` /
attempt 1 succeeded with canonical FULL. Develop CI #817 / run
`41177055270` / attempt 1 succeeded using exact-feature certification reuse;
no duplicate broad lane ran. Docs-only closeout CI #818 succeeded.

The reviewed one-shot P4 production smoke is also complete and must not be
repeated. It ran at the exact source above with no network or credentials:

    SMOKE_HEAD=545f21621c15c682f19d10df3a3d1ecf86f8a77c
    SMOKE_TREE=07bb44a2975c44fd62e68a9cc8f3b9f99a0bbd8e
    P4_GUI_EXIT=0
    ARCH147_P4_NO_NETWORK_SMOKE=PASS

Generation 1 visibly reached Application/Trading/Research RUNNING with
Diagnostic NONE, transport NOT_CONNECTED and the accepted P3 identities:

    campaign 11d55269-7e13-57aa-a3bf-1e20e486204b
    bundle   b771cf92-a09f-5f18-86d3-e03b65e04fe9

The durable shutdown chronology was:

    sequence 5 STOP_REQUESTED
    sequence 6 RESEARCH_STOPPED
    sequence 7 TRADING_RECONCILED
    sequence 8 TRADING_STOPPED
    sequence 9 STOPPED

Every record used generation 1 and diagnostic NONE. This proves the P4 contract:
research closure precedes final STOPPED, trading reconciliation precedes trading
closure, both workers close before durable STOPPED, and the launcher can exit 0.
The journal is accepted evidence; do not delete, rewrite or manufacture a second
smoke merely to refresh it.

LIVE remains disabled. FINAL_HOLDOUT remains sealed. P4 grants no broker/order
authority.

## Current next milestone — P5 architecture/discovery

The product target is a private single-user Windows desktop trading bot, not a
hostile-administrator deployment platform. The owner explicitly authorizes
parallel Codex subagents for P5 architecture/discovery and subsequent bounded
implementation where interfaces are frozen.

Architecture discovery is read-only. It should map and reuse existing components
before proposing new ones, especially:

- `trading_bot.risk.RiskManager`;
- `ReviewPaperStore` and review-paper ledger/account reconstruction;
- `RobinhoodReviewPaperCycle`;
- typed `trading_bot.robinhood_mcp` account/quote/history/review boundaries;
- existing order/execution and paper-account presentation primitives;
- the accepted P4 DesktopSupervisor worker/lifecycle seam.

Treat old Architecture 133/134 installation/rename/scheduler/ACL machinery and
Architecture 146 protected custody as historical/deferred. Treat older PD2 /
personal-desktop production-authority machinery as selective reuse candidates,
not inherited prerequisites: justify any piece that genuinely simplifies P5.

The preferred implementation decomposition to validate is:

    P5A local unattended SIMULATED_PAPER
        strategy -> RiskManager -> exact intent -> durable synthetic fill/account
        -> restart/idempotency -> GUI visibility

    P5B Robinhood MCP read/review forward paper
        account/quotes/history/review-only transport
        -> local strategy/risk remain authoritative
        -> zero order placement

    P5C unattended multi-session paper soak
        cadence/session handling -> reconnect/backoff -> startup reconciliation
        -> stale-data rejection -> health/audit -> kill switch

    P6 separately reviewed broker mutation
        explicit live arming + tiny limits + exact Robinhood execution

P5 architecture/discovery performs no provider operation, credential read,
broker mutation, FINAL_HOLDOUT access, branch publication or runtime-state
mutation. Once ChatGPT accepts the synthesized DAG, freeze interfaces and use
parallel bounded implementation worktrees/subagents where dependencies allow.
Each publication remains one atomic prepared checkpoint, focused verification,
both-context admission where applicable, one push and one terminal CI. Do not
use CI as an edit/debug loop.

Also remove or update any tests and docs that referenced the old behavior.
