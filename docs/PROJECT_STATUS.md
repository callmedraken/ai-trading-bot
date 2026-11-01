# AI Trading Bot — Project Status

## Current checkpoint — Architecture 147 filtered-trend source accepted/integrated; real acquisition next

P4 is fully accepted. Source is integrated at
`e5e800ad99da8dd1c09fa36202d5ff8b648c1daf`, tree
`1d2f57afb1d5cddc9487352519f92cced5554f9d`. Feature CI #816 /
run `41175037719` / attempt 1 succeeded with canonical FULL. Develop CI #817 /
run `41177055270` / attempt 1 succeeded with exact-feature certification
reuse and no duplicate broad execution. The coordination closeout at
`545f21621c15c682f19d10df3a3d1ecf86f8a77c`, tree
`07bb44a2975c44fd62e68a9cc8f3b9f99a0bbd8e`, passed docs-only CI #818.

The one reviewed no-network production Start/Stop smoke then succeeded at that
exact source. Generation 1 reached RUNNING with both trading and research
RUNNING, accepted P3 campaign `11d55269-7e13-57aa-a3bf-1e20e486204b` and
bundle `b771cf92-a09f-5f18-86d3-e03b65e04fe9`, transport NOT_CONNECTED and
diagnostic NONE. Stop produced the durable ordered journal sequence
RESEARCH_STOPPED -> TRADING_RECONCILED -> TRADING_STOPPED -> STOPPED, with
diagnostic NONE throughout. The launcher exited 0 and
`ARCH147_P4_NO_NETWORK_SMOKE=PASS`. Do not repeat the smoke.

P4 therefore establishes the ordinary private single-user desktop lifecycle:
manual Start, concurrent trading/research workers, manual Stop, deterministic
closure/reconciliation and no automatic restart or self-update. P4 trading
remains intentionally inert; LIVE remains disabled and FINAL_HOLDOUT sealed.

P5A implements the frozen local unattended SIMULATED_PAPER / PAPER_EVALUATION
prototype on OPEN_REPLAY, with independent paper risk policy, transactional
SQLite account/effect history, clean Stop/reopen and cached GUI visibility.
No production/default PAPER_EVALUATION strategy is accepted or selected.
The descriptive P3 candidate `cc8b7b1d-c480-5fb9-9836-d7230ea2690d`
(55/100 moving averages) is historical research evidence, not selection authority.
P5 consumes an immutable typed strategy binding and a narrow injected evaluator;
absent an explicitly accepted binding, trading fails closed with
`PAPER_EVALUATION_SELECTION_REQUIRED`. Synthetic fixtures grant no qualification,
PAPER_CANDIDATE promotion or live eligibility.
FINAL_HOLDOUT remains sealed and no live or broker authority is introduced.

The initial P5A source publication at
`834a0eb638a75f00385144b8473152402bad31f5`, tree
`071b222c8a1ee78d0e2e787659268c6cdf782098`, is preserved with feature CI
`41198164554` / attempt 1 terminal red after canonical FULL broad-5 found a
stale P4-first current-route assertion. That incident is classified
`PREPUBLICATION_COVERAGE_DEFECT` and remains immutable evidence.

Corrective child `ARCH147_P5A_C1_PREPUBLICATION_COVERAGE` is accepted at
`1b7dae71e2988f82074dd285d099bf3227944266`, tree
`333514e7051cb07dcb6edc32fb82f4de9147d0d6`. Feature CI
`41209242802` / attempt 1 passed source-static, active-tests and all seven
GitHub-owned canonical FULL lanes. ChatGPT exact-source review accepted the
two-commit chain and fast-forwarded `develop` to the exact C1 SHA. Develop CI
`41235406233` / attempt 1 then passed source-static/source-gates and correctly
reused the exact-feature certification, skipping duplicate active/FULL work.

No P5A production runtime, SQLite/journal, provider, credential, broker,
Robinhood, Alpaca, live or FINAL_HOLDOUT effect occurred during implementation,
certification or integration. P4 remains intact as the accepted inert launcher
with separate frozen state. P5A supports SQLite financial durability and clean
Stop/reopen, but not automatic recovery of an unclean application death:
stale/unresolved lifecycle evidence remains failed/attention. P5C owns the later
process-recovery adapter.

## Immediate next step

The filtered-trend / multi-asset source milestone is accepted and integrated.

Initial source commit `d1e9d881f99121f56d6d24639d0b594cd68b107a`, tree
`af5592e93cffe484ee73471a4070ea4f722c564b`, passed feature CI
`41246258225` / attempt 1, including all seven GitHub-owned FULL lanes.
ChatGPT exact-source review then found the MA_ADX policy mismatch. Corrective
child `3e99e8adc28e5f390edd9eb65bdbed80d1f100ca`, tree
`133ba237812c0b0ade9352d440793697c1c79691`, corrected ADX20 to
threshold-only and ADX25_RISING to threshold-plus-rising without changing the
30-configuration identity grid. Child CI `41250779521` / attempt 1 passed
source-static, active-tests and all seven canonical FULL lanes.

ChatGPT accepted the corrected two-commit chain and fast-forwarded `develop`
to `3e99e8adc28e5f390edd9eb65bdbed80d1f100ca`. Develop integration CI
`41254635989` / attempt 1 passed source-static/source-gates and reused the
exact-feature certification; duplicate active/FULL execution was skipped.

No Alpaca call, credential read, real dataset, campaign, FINAL_HOLDOUT, P5
production state, Robinhood, broker or live effect occurred during source work,
certification or integration.

The next reviewed effect is one create-only acquisition of the fixed
SPY/QQQ/IWM/EFA/EEM/TLT/GLD/PDBC 2016-2023 dataset using
`ALPACA_ALL_ADJUSTED_PRICE_V1`. Acquisition must use the accepted integrated
develop identity, hidden ephemeral credentials, the existing bounded HTTPS
transport, no retry, and a fresh destination. After dataset validation succeeds,
the explicit offline campaign runs once and returns the deterministic top-10
shortlist for ChatGPT review. No PAPER_EVALUATION binding is installed yet.

## Roadmap

    P1  desktop research simplification — accepted
    P2  real SPY acquisition + verification + freeze — accepted
    P3  optimizer / walk-forward campaign + Research Results GUI — accepted, real run complete
    P4  desktop concurrent workers + GUI Start/Stop — accepted and smoke complete
    P5A local unattended simulated-paper infrastructure — accepted/integrated; strategy selection pending filtered-trend research
    P5B Robinhood read/review forward paper — follows explicit PAPER_EVALUATION selection
    P6  explicitly armed tiny restricted live through official Robinhood MCP / Agentic Trading
    P7  production soak / monitoring / backup / restart / reconnect / credential rotation
