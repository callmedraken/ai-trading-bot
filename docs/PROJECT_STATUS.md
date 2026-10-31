# AI Trading Bot — Project Status

## Current checkpoint — Architecture 147 P4 accepted/integrated; runtime smoke pending

P4 is accepted and integrated on `develop` at
`e5e800ad99da8dd1c09fa36202d5ff8b648c1daf`, tree
`1d2f57afb1d5cddc9487352519f92cced5554f9d`. The original P4 source commit
`5fb96f758b6f2bb2af302f5725fdf7ad03bfc138` reached feature CI #815 but that
run failed because Qt-backed tests were collected without the required PySide6
dependency. That red run is preserved. Corrective child `e5e800ad...` changed
only source-gate dependency coverage plus its deterministic CI regression.
Feature CI #816 / run `41175037719` / attempt 1 succeeded with canonical FULL.
Develop CI #817 / run `41177055270` / attempt 1 then succeeded using
`exact_feature_certification` reuse: source-static and source-gates passed and
the active, fallback FULL, Robinhood and seven canonical FULL lanes were skipped.

P4 provides the ordinary private single-user desktop lifecycle: explicit GUI
Start runs one inert local trading worker and one independent offline research
worker concurrently; Stop cancels research, reconciles/closes trading, and
reports STOPPED only after closure is confirmed. External trading transport
remains NOT_CONNECTED and deferred to P5; simulated paper is the default and
LIVE remains disabled. Research only verifies the accepted existing P3 bundle;
it does not rerun the optimizer, choose a strategy, promote a candidate or open
FINAL_HOLDOUT.

The production lifecycle journal remains ordinary JSONL at
`F:\AI\desktop-bot-state\p4\lifecycle.jsonl`, outside source. Unresolved,
malformed or stale ownership blocks Start and must be preserved for explicit
operator reconciliation. There is no automatic restart, destructive recovery,
force-kill-as-success or self-update. Architecture 133/134 deployment ceremony
and Architecture 146 protected custody remain historical/deferred rather than
current product prerequisites.

## Immediate next step

Run exactly one reviewed no-network P4 GUI Start/Stop smoke from a canonical
`develop` worktree synchronized to the current remote. Click Start once and
confirm both workers reach RUNNING plus the accepted P3 campaign/bundle identity;
then click Stop and confirm durable STOPPED only after research closure, trading
reconciliation and trading closure. If the runtime enters FAILED/attention or
the journal is unresolved, preserve the journal and lock evidence and stop:
do not delete, repair or automatically retry.

After a successful smoke, proceed directly to P5 architecture/discovery. For P5,
parallel read-only Codex subagents are explicitly authorized to map the existing
Robinhood MCP foundations, local risk/order/reconciliation path, runtime recovery,
GUI/operator surfaces and current test/CI ownership. Synthesize those findings
before implementation so bounded implementation slices can run in parallel
without reviving retired deployment/ACL/scheduler/custody gates. P5 effects and
all later live effects require their own separately reviewed composition.

## Roadmap

    P1  desktop research simplification — accepted
    P2  real SPY acquisition + verification + freeze — accepted
    P3  optimizer / walk-forward campaign + Research Results GUI — accepted, real run complete
    P4  desktop concurrent workers + GUI Start/Stop — accepted/integrated; no-network smoke pending
    P5  unattended synthetic/forward paper soak using official Robinhood MCP foundations
    P6  explicitly armed tiny restricted live through official Robinhood MCP / Agentic Trading
    P7  production soak / monitoring / backup / restart / reconnect / credential rotation
