# AI Trading Bot — Project Status

## Current checkpoint — Architecture 147 filtered-trend C2 accepted/integrated; real acquisition next

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

The filtered-trend / multi-asset source milestone, ADX C1 correction, and C2
provider-response compatibility correction are accepted and integrated.

C2 is exact commit `bed872c660bb36384f057e5e9c556dbbb7609037`, tree
`4fff6ac66c097608634d4e024f4cc0c6c29b7579`, direct child of accepted
develop `e48f55bb5bfce2725a1244e9fba97bdaa8c74b47`. It changes only the
documented Alpaca response compatibility contract: `bars` and
`next_page_token` remain required; optional `currency`, when present, must
be exact `USD`; arbitrary extra root fields remain rejected.

The first C2 publication run `41284238424` / attempt 1 is preserved terminal
red because the new correction branch was not mapped to the filtered-trend
checkpoint and therefore used the legacy four-shard generic FULL fallback.
Its shard 2 verification passed but the fallback shard wall time reached
349.572 seconds and tripped the 300-second hygiene guard. That run was not
rerun and is not classified as PREPUBLICATION_COVERAGE_DEFECT.

The exact same C2 commit was then fast-forwarded to the registered
`feature/research-filtered-trend-multi-asset-current` checkpoint branch.
Canonical run `41342652706` / attempt 1 resolved
`arch147-filtered-trend-multi-asset-research`, route ACTIVE, profile FULL;
source-static, active-tests, broad-1 through broad-7, and source-gates all
passed. Generic full-tests and Robinhood certification were skipped.

ChatGPT exact-source review accepted C2 and fast-forwarded `develop` to the
exact C2 SHA. Develop integration run `41343862704` / attempt 1 passed
source-static/source-gates, proved exact-feature certification reuse, and
skipped duplicate active/FULL execution.

No Alpaca call, credential read, real dataset, campaign, FINAL_HOLDOUT, P5
production state, Robinhood, broker, or live effect occurred through C2
integration.

The next reviewed effect is one create-only acquisition of the fixed
SPY/QQQ/IWM/EFA/EEM/TLT/GLD/PDBC 2016-2023 dataset using
`ALPACA_ALL_ADJUSTED_PRICE_V1`. It must run from the clean dedicated develop
worktree at the accepted coordination-closeout identity, use hidden ephemeral
credentials and the existing bounded Alpaca HTTPS transport, perform no retry,
and leave any partial destination visible on failure. After dataset validation
succeeds, run the accepted offline filtered-trend campaign exactly once and
return its deterministic top-10 shortlist for review. Do not install a
PAPER_EVALUATION binding automatically.

## Roadmap

    P1  desktop research simplification — accepted
    P2  real SPY acquisition + verification + freeze — accepted
    P3  optimizer / walk-forward campaign + Research Results GUI — accepted, real run complete
    P4  desktop concurrent workers + GUI Start/Stop — accepted and smoke complete
    P5A local unattended simulated-paper infrastructure — accepted/integrated; strategy selection pending filtered-trend research
    P5B Robinhood read/review forward paper — follows explicit PAPER_EVALUATION selection
    P6  explicitly armed tiny restricted live through official Robinhood MCP / Agentic Trading
    P7  production soak / monitoring / backup / restart / reconnect / credential rotation
