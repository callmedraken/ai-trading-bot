# AI Trading Bot — Current Handoff

## Current boundary — Architecture 147 P4 integrated; smoke pending

Accepted integrated source:

    HEAD e5e800ad99da8dd1c09fa36202d5ff8b648c1daf
    TREE 1d2f57afb1d5cddc9487352519f92cced5554f9d
    branch develop
    checkpoint arch147-desktop-supervisor
    preflight=None; execute=None

P4 source was independently accepted before integration. Original source
`5fb96f758b6f2bb2af302f5725fdf7ad03bfc138` produced preserved failed feature
CI #815 / run `41172155619`: Qt-backed tests were collected without PySide6.
Corrective child `e5e800ad99da8dd1c09fa36202d5ff8b648c1daf` changed only
`.github/workflows/checkpoint-source-gates.yml` and
`tests/runtime/checkpoint_runner/test_ci.py` to install the exact PySide6
bound in test-bearing source-gate jobs and prove that coverage deterministically.

Feature CI #816 / run `41175037719` / attempt 1 is terminal SUCCESS with
canonical FULL. Develop CI #817 / run `41177055270` / attempt 1 is terminal
SUCCESS with exact-feature certification reuse: source-static and source-gates
succeeded; active-tests, fallback full-tests, Robinhood certification and all
seven canonical FULL lanes were skipped. Do not repeat canonical FULL locally or
rerun either immutable CI result.

P4 has five lifecycle states: STOPPED, STARTING, RUNNING, STOPPING, FAILED.
Explicit Start admits one generation with exactly one trading and one research
worker. Duplicate Start is a no-op. Stop is idempotent, signals both workers,
then requires research closure plus trading reconciliation/closure before
STOPPED. Fatal failure stops the peer and leaves FAILED; there is no automatic
restart or force-kill-as-success.

Trading is deliberately inert and NOT_CONNECTED: no strategy, orders, positions,
ledger, broker, credentials or network. Research only verifies the accepted P3
campaign bundle through the bounded public reader and never selects or promotes a
strategy. LIVE remains disabled and FINAL_HOLDOUT sealed.

The production JSONL journal and lifetime lock live outside source at
`F:\AI\desktop-bot-state\p4\lifecycle.jsonl` and `.lock`. Malformed or
unresolved state, stale ownership or unconfirmed closure blocks Start. Preserve
such state for explicit reconciliation; do not delete, overwrite, manufacture a
STOPPED record or automatically retry.

## Immediate operator boundary

The main checkout is not assumed to be on `develop` and must not be switched or
cleaned to satisfy this milestone. The current canonical develop worktree created
for integration is:

    F:\AI\worktrees\ai-trading-bot-p4-integration-e5e800a

Before the smoke, synchronize that worktree only by a reviewed fetch plus
fast-forward to the current remote docs-closeout commit. Then launch the
source-owned desktop bot with its existing venv. No credentials or network are
involved.

The reviewed operator performs one smoke only:

1. Start the GUI.
2. Click Start once.
3. Confirm trading and research both report RUNNING and the accepted P3
   campaign/bundle identity is displayed.
4. Click Stop once.
5. Confirm durable STOPPED only after research closure and trading
   reconciliation/closure.
6. Close the GUI normally.

If Start is blocked, state becomes FAILED/attention, closure is unconfirmed, or
the launcher exits nonzero, preserve the journal/lock and diagnostics and stop.
Do not retry, delete or repair the runtime state without review.

After a successful smoke, continue automatically to Architecture 147 P5
architecture/discovery. The user has explicitly authorized parallel Codex
subagents for that architecture work. Use them read-only to map Robinhood MCP,
risk/order/reconciliation, runtime recovery, GUI/operator and test/CI surfaces,
then synthesize one implementation DAG before source changes. Retired
Architecture 133/134 deployment ceremony and Architecture 146 protected custody
must not become P5 prerequisites. LIVE remains NO-GO.
