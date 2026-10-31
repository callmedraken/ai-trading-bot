# AI Trading Bot — Project Status

## Current checkpoint — Architecture 147 P4 source-only desktop supervisor

Accepted/integrated P3 starts this checkpoint at
`b9d52c4934517ea67b8c18f4d6f967bfd576ecf7`, tree
`755054f71489491f0214489e35827ba2bb51c74e`. Develop #814 / run
`41151276520` / attempt 1 succeeded with exact-feature certification reuse.
The P3 real offline campaign and existing Research GUI inspection are complete.
Accepted campaign `11d55269-7e13-57aa-a3bf-1e20e486204b` contains 255
candidates and a 32-candidate walk-forward shortlist. Its immutable bundle is
`b771cf92-a09f-5f18-86d3-e03b65e04fe9`. Exact research results and commitments
belong to the Architecture-147 validation record.

P4 adds the ordinary private single-user desktop lifecycle: explicit GUI Start
runs one inert local trading worker and one independent offline research worker
concurrently; Stop cancels research, reconciles/closes trading, and reports
STOPPED only after closure is confirmed. An asynchronous coordinator keeps the
GUI event loop responsive. External trading transport is NOT_CONNECTED and
deferred to P5; simulated paper is the default and LIVE is disabled.

Research may verify an existing local P3 bundle through a bounded queue. It does
not rerun the optimizer or select a trading strategy. Trading receives no
research files, results, ledger, risk, broker or credential authority. The
existing read-only Research page and historical Supervisor models are preserved.
No P3 candidate is promoted; qualification_policy remains null, FINAL_HOLDOUT
remains sealed, and no PAPER_CANDIDATE or final-holdout admission is created.

The current source checkpoint is `arch147-desktop-supervisor`, branch
`feature/research-desktop-supervisor-current`; preflight/execute are absent.
Canonical FULL belongs to GitHub, with the current P4 tests explicitly supported.
The P3 source-only research checkpoint remains registered for its own branch.
No real desktop runtime, production journal, acquisition, campaign, provider,
credential, broker, paper-account, scheduler, ACL, holdout or live effect runs
during implementation, admission or CI. Tests use synthetic/local temporary state.

The production lifecycle journal is ordinary JSONL at
`F:\AI\desktop-bot-state\p4\lifecycle.jsonl`, outside the source checkout.
A durable unresolved lifecycle, malformed journal, stale lock or unconfirmed
closure blocks Start and requires visible operator reconciliation. There is no
automatic restart, destructive recovery or force-kill-as-success.

The application never updates itself. Manual source/configuration updates occur
only after a confirmed Stop; a later owner Start begins a new generation.
Architecture 133/134 installation and Architecture 146 protected custody remain
historical/deferred, with their authority checks and consumed evidence preserved.
Architecture 134 R3 remains parked; LIVE remains NO-GO.

## Immediate next step

Finish focused tests, current/historical source authority and both-context
admission on one atomic P4 candidate, push once, and wait for terminal mapped
GitHub FULL. Stop for ChatGPT independent exact-source/CI review; Codex performs
no PR or merge. After acceptance/integration, verify develop exact-feature reuse,
launch `scripts/run_desktop_bot.py` for one no-network Start/Stop GUI smoke,
confirm concurrent RUNNING and durable reconciled STOPPED, then proceed to P5
Robinhood MCP unattended paper-soak source design/implementation. P5 effects
require their own reviewed composition; P4 grants no brokerage access.

## Roadmap

    P1  desktop research simplification — accepted
    P2  real SPY acquisition + verification + freeze — accepted
    P3  optimizer / walk-forward campaign + Research Results GUI — accepted, real run complete
    P4  desktop concurrent workers + GUI Start/Stop — current source-only checkpoint
    P5  unattended synthetic/forward paper soak using official Robinhood MCP foundations
    P6  explicitly armed tiny restricted live through official Robinhood MCP / Agentic Trading
    P7  production soak / monitoring / backup / restart / reconnect / credential rotation
