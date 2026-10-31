# AI Trading Bot — Project Status

## Current checkpoint — Architecture 147 P4 accepted/complete; P5 architecture current

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

The source-only checkpoint is `arch147-desktop-paper-cycle` on
`feature/research-desktop-paper-cycle-current`, with no preflight/execute and
GitHub-owned canonical FULL. Exact-source review and integration remain pending;
implementation, admission and CI do not launch the production P5 application.
P4 remains intact as the accepted inert launcher with separate frozen state.
P5A supports SQLite financial durability, not automatic recovery of an unclean
application death: stale/unresolved lifecycle evidence remains failed/attention.
P5C owns the later process-recovery adapter.

## Immediate next step

Complete P5A implementation and focused verification, then stop before commit
or push for ChatGPT's strategy/publication decision. Eventual publication still
requires one atomic candidate, FEATURE/PROSPECTIVE_DEVELOP admission, terminal
GitHub canonical FULL and exact-source review. The next operational milestone
is filtered-trend/multi-asset research and explicit paper strategy selection;
no production P5 smoke is ready. Planned SPY/QQQ/IWM/EFA/EEM/TLT/GLD/PDBC
symbols are representable bindings only, not acquisition or execution authority.
No real P5 launch or production-state creation occurs during source work.

## Roadmap

    P1  desktop research simplification — accepted
    P2  real SPY acquisition + verification + freeze — accepted
    P3  optimizer / walk-forward campaign + Research Results GUI — accepted, real run complete
    P4  desktop concurrent workers + GUI Start/Stop — accepted and smoke complete
    P5  unattended synthetic/forward paper soak using official Robinhood MCP foundations — current architecture/design
    P6  explicitly armed tiny restricted live through official Robinhood MCP / Agentic Trading
    P7  production soak / monitoring / backup / restart / reconnect / credential rotation
