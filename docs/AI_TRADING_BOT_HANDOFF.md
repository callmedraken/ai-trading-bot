# AI Trading Bot — Current Handoff

## Current boundary — Architecture 147 filtered-trend C2 provider compatibility correction pending

Current accepted develop source before this coordination closeout:

    HEAD e48f55bb5bfce2725a1244e9fba97bdaa8c74b47
    TREE b04fef2ffa44e680e70bd1462d51a90d40256317
    branch develop

Filtered-trend corrective feature CI `41250779521` / attempt 1 passed
source-static, active-tests and all seven canonical FULL lanes. ChatGPT
exact-source review accepted the corrected feature chain and fast-forwarded
develop to the exact C1 SHA. Develop CI `41254635989` / attempt 1 passed
source-static/source-gates with exact-feature certification reuse; duplicate
active/FULL execution was skipped.

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

## Accepted checkpoint — filtered-trend / multi-asset research

Checkpoint: `arch147-filtered-trend-multi-asset-research`.
Feature branch: `feature/research-filtered-trend-multi-asset-current`.
Canonical certification: GitHub-owned FULL.

The initial source commit
`d1e9d881f99121f56d6d24639d0b594cd68b107a` / tree
`af5592e93cffe484ee73471a4070ea4f722c564b` passed GitHub run
`41246258225` / attempt 1. Exact-source review found one semantic defect:
both ADX variants required rising ADX.

Corrective child
`3e99e8adc28e5f390edd9eb65bdbed80d1f100ca` / tree
`133ba237812c0b0ade9352d440793697c1c79691` preserves the 30-candidate grid
while implementing the frozen policies exactly:

    ADX20         Wilder ADX(14) >= 20
    ADX25_RISING  Wilder ADX(14) >= 25 AND current ADX > prior ADX

Its focused union passed 1,426 cases; FEATURE/PROSPECTIVE_DEVELOP admission
passed with stable identity; GitHub run `41250779521` / attempt 1 passed
source-static, active-tests and all seven FULL lanes. Develop integration run
`41254635989` / attempt 1 passed with exact-feature certification reuse.

The accepted research contract freezes:

    universe  SPY QQQ IWM EFA EEM TLT GLD PDBC
    period    2016-01-01 through 2024-01-01 exclusive
    basis     ALPACA_ALL_ADJUSTED_PRICE_V1
    grid      30 exact configurations
    regimes   2019, 2020, 2021, 2022, 2023 + continuous 2019-2023

No filter stacking or post-result grid expansion is allowed. FINAL_HOLDOUT
remains sealed. The campaign produces descriptive research only:
`qualification_policy=null`, `paper_binding=null`, `live_eligible=false`.

The filtered-trend source and ADX C1 are accepted and integrated. Before real
acquisition began, exact-source compatibility review found that the parser
rejected Alpaca's documented optional top-level `currency` response field.
C2 changes only provider response-shape compatibility. Real acquisition has
not started and is not authorized until C2 is accepted and integrated.

## Immediate next operation — C2 provider-response correction

Complete the bounded C2 source correction and its focused gates. Do not perform
real Alpaca acquisition, access credentials, run the real campaign, access
FINAL_HOLDOUT, launch P5 production, or contact Robinhood/broker/live paths.
After C2 is accepted and integrated, the separately reviewed next operation is
one real acquisition of the fixed eight-symbol adjusted dataset using the
accepted integrated develop identity, the existing bounded Alpaca HTTPS
transport and hidden ephemeral interactive research credentials.

## Post-C2 reviewed real acquisition boundary

The operation must:

- verify exact clean local `develop` and matching `origin/develop` before
  prompting or networking;
- use `adjustment=all`, SIP, USD, daily bars and the frozen 2016-2023 bounds;
- contact only Alpaca market-data historical bars;
- make no broker/trading/Robinhood/P5/FINAL_HOLDOUT call;
- use a fresh create-only destination;
- never print or persist credentials;
- make no automatic retry or repair;
- validate complete exact NYSE-session coverage for all eight symbols before
  accepting the dataset.

After acquisition succeeds, run the accepted offline
`scripts/run_filtered_trend_research.py` exactly once against that dataset and
a fresh report directory. Return dataset identity, campaign ID, bundle ID,
top-10 shortlist and report paths to ChatGPT. Do not install a P5 strategy
binding automatically.

Also remove or update any tests and docs that referenced the old behavior.
