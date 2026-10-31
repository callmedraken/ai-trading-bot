# AI Trading Bot — Current Handoff

## Current boundary — Architecture 147 P5A accepted/integrated; filtered-trend research next

Current accepted develop source:

    HEAD 1b7dae71e2988f82074dd285d099bf3227944266
    TREE 333514e7051cb07dcb6edc32fb82f4de9147d0d6
    branch develop

P5A feature CI `41209242802` / attempt 1 passed source-static, active-tests and
all seven canonical FULL lanes. ChatGPT exact-source review accepted the feature
chain and fast-forwarded develop to the exact C1 SHA. Develop CI
`41235406233` / attempt 1 passed source-static/source-gates with exact-feature
certification reuse; duplicate active/FULL execution was skipped.

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

## Accepted checkpoint — ARCH147_P5A_DESKTOP_SIMULATED_PAPER

Checkpoint: `arch147-desktop-paper-cycle`.
Feature branch: `feature/research-desktop-paper-cycle-current`.
Canonical certification profile: `full`, GitHub-owned.
`preflight=None`; `execute=None`.

The original source commit
`834a0eb638a75f00385144b8473152402bad31f5` / tree
`071b222c8a1ee78d0e2e787659268c6cdf782098` remains preserved with CI
`41198164554` / attempt 1 terminal red after broad-5 exposed a stale current
route assertion. That is immutable `PREPUBLICATION_COVERAGE_DEFECT` evidence.

Corrective child `ARCH147_P5A_C1_PREPUBLICATION_COVERAGE` is accepted at
`1b7dae71e2988f82074dd285d099bf3227944266` / tree
`333514e7051cb07dcb6edc32fb82f4de9147d0d6`. Its focused gate passed 1,070
cases; current/routed authority and FEATURE/PROSPECTIVE_DEVELOP admission passed
with stable identity. Feature CI `41209242802` / attempt 1 passed all source,
active and seven FULL lanes. Develop integration CI `41235406233` / attempt 1
passed with exact-feature certification reuse.

P5A provides the local SIMULATED_PAPER / PAPER_EVALUATION infrastructure:
transactional SQLite financial state, deterministic effect identities, OPEN-only
no-lookahead replay, existing RiskManager/OrderEngine/PaperLedger authority,
durable kill/new-buy controls, clean Stop/reopen and cached GUI presentation.
The strategy and symbol are immutable typed bindings rather than hard-coded
55/100/SPY assumptions.

No production/default PAPER_EVALUATION binding exists. The descriptive P3
55/100 candidate `cc8b7b1d-c480-5fb9-9836-d7230ea2690d` remains historical
research evidence only. Without an accepted binding, production reports
`PAPER_EVALUATION_SELECTION_REQUIRED`, creates no P5 financial state and admits
no trading. FINAL_HOLDOUT remains sealed and no live/broker authority exists.

P5 uses
`F:\AI\desktop-bot-state\p5\simulated-paper.sqlite` and
`F:\AI\desktop-bot-state\p5\lifecycle.jsonl` only after a real accepted
binding is supplied and the runtime is explicitly launched. Neither was created
during P5A source work. P4 state and its accepted smoke remain untouched.
Unclean application-death recovery is intentionally deferred to P5C.

## Immediate next milestone — filtered-trend / multi-asset research

Start a bounded source-only research successor from this exact develop source.
Freeze the planned ETF universe:

    SPY QQQ IWM EFA EEM TLT GLD PDBC

Test the predeclared moving-average confirmation families without combinatorial
stacking: baseline MA, percentage band, ADX, Donchian confirmation and long-term
momentum; ATR is descriptive/risk research rather than a new directional vote in
the first campaign.

The successor must keep strategy selection and runtime binding separate. It
must not install a P5 PAPER_EVALUATION binding automatically, launch P5
production state, contact Robinhood, create broker/live effects, or access the
existing FINAL_HOLDOUT. Any real multi-asset data acquisition is a separately
reviewed effect after source acceptance/integration.

After the research campaign returns its deterministic shortlist, ChatGPT reviews
cross-asset/regime robustness and issues a separate small PAPER_EVALUATION
binding checkpoint. Only after that binding exists is a production P5 simulated
paper smoke eligible.

Also remove or update any tests and docs that referenced the old behavior.
