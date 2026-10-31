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

P5 architecture/discovery is now the current milestone. The goal is the shortest
safe path to a usable unattended simulated-paper prototype, then Robinhood MCP
read/review forward-paper operation, then restart/recovery/multi-session paper
soak. Existing RiskManager, review-paper ledger/store, Robinhood MCP adapters,
paper-cycle components and GUI account surfaces should be reused where they
simplify the product. Historical Architecture 133/134 deployment ceremony and
Architecture 146 protected custody remain non-prerequisites.

## Immediate next step

Run the read-only P5 architecture/discovery checkpoint using Astra as lead with
explicitly authorized parallel subagents. Map Robinhood MCP, local
strategy/risk/order/ledger/reconciliation, P4 runtime/recovery, GUI/operator and
test/CI surfaces, then synthesize one implementation DAG before source edits.

The preferred shape to validate is P5A local unattended simulated paper with
durable restart/idempotency and GUI visibility; P5B Robinhood MCP
account/quote/history/review-only composition with zero order placement; P5C
unattended multi-session reconnect/recovery/health/kill-switch soak. P6 remains
the first separately reviewed broker-mutation/live boundary.

Do not create a new admission framework, revive retired deployment/custody
machinery, open FINAL_HOLDOUT, read credentials or perform provider/broker
effects during architecture discovery.

## Roadmap

    P1  desktop research simplification — accepted
    P2  real SPY acquisition + verification + freeze — accepted
    P3  optimizer / walk-forward campaign + Research Results GUI — accepted, real run complete
    P4  desktop concurrent workers + GUI Start/Stop — accepted and smoke complete
    P5  unattended synthetic/forward paper soak using official Robinhood MCP foundations — current architecture/design
    P6  explicitly armed tiny restricted live through official Robinhood MCP / Agentic Trading
    P7  production soak / monitoring / backup / restart / reconnect / credential rotation
