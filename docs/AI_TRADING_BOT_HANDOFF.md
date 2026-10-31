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

## Current checkpoint — ARCH147_P5A_DESKTOP_SIMULATED_PAPER

Accepted implementation base:

    HEAD 79dff6341241af8e126c37060bf4c0968af36778
    TREE 226e974ec43512d53aa1591eb5efeb0f808bf1cb
    branch develop

Primary worktree: `F:\AI\worktrees\ai-trading-bot-desktop-paper-cycle-current`.
Feature branch: `feature/research-desktop-paper-cycle-current`.
Checkpoint: `arch147-desktop-paper-cycle`; `preflight=None`, `execute=None`;
canonical certification `full`, GitHub-owned. The initial P5A source candidate
was published once at HEAD
`834a0eb638a75f00385144b8473152402bad31f5`, tree
`071b222c8a1ee78d0e2e787659268c6cdf782098`. Feature CI run `41198164554`,
attempt 1, is preserved terminal red: source-static and active tests passed,
while canonical FULL failed only in broad-5 on the stale P4-first assertion.
The classification is `PREPUBLICATION_COVERAGE_DEFECT`; the red commit remains
immutable and grants no runtime operation.

The current corrective child is
`ARCH147_P5A_C1_PREPUBLICATION_COVERAGE`. It closes the stale current-route
assertion and adds that module to the required P5A prepublication coverage.
The child is pending its affected/full focused checks, authority, admission,
one ordinary push and terminal mapped GitHub FULL, followed by exact-source
review and integration.

No production/default PAPER_EVALUATION binding exists. The descriptive P3
55/100 candidate `cc8b7b1d-c480-5fb9-9836-d7230ea2690d` is not an accepted
production or default paper strategy. P5 requires an explicit immutable typed
PaperStrategyBinding (family/version, symbol, parameters, research provenance,
PAPER_EVALUATION purpose, no qualification policy and no live eligibility).
Without an accepted binding, production reports
`PAPER_EVALUATION_SELECTION_REQUIRED` and admits no trading. Synthetic injected
fixtures are tests only. OPEN observation acquisition and strategy selection
remain separate; FINAL_HOLDOUT stays sealed.

P5 uses `F:\AI\desktop-bot-state\p5\simulated-paper.sqlite` and
`F:\AI\desktop-bot-state\p5\lifecycle.jsonl`; tests inject fresh external
temporary paths. Neither production P5 file is created during implementation.
The P4 journal and accepted smoke remain untouched. P5 uses DesktopSupervisor
and a distinct instance of the accepted LifecycleJournal. Clean Stop/reopen and
SQLite commit-before-ack idempotency are supported; stale lifecycle locks or
unresolved process-death evidence fail closed without repair. P5C owns recovery.

The C1 child must complete its focused checks, current/routed authority,
FEATURE/PROSPECTIVE_DEVELOP admission, one normal child publication and
terminal mapped GitHub FULL before exact-source acceptance and integration.
Filtered-trend/multi-asset research and explicit strategy selection remain the
next milestone only after that green acceptance/integration boundary; this
child does not start it. Production P5 smoke remains blocked because no
`PAPER_EVALUATION` strategy is selected. SPY/QQQ/IWM/EFA/EEM/TLT/GLD/PDBC are
representable bindings only; no acquisition or new strategy-family
implementation is included. Do not launch during source work. No production,
provider, account, credentials, Robinhood, Alpaca, broker, holdout, scheduler,
ACL or live operation is authorized by source PASS. P5B read/review-only
transport follows separately; P6 remains the separately reviewed
broker-mutation boundary.

Also remove or update any tests and docs that referenced the old behavior.
