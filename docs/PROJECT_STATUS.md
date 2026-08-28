# Project Status and Roadmap

This document is the canonical high-level status/roadmap for AI Trading Bot.
Detailed architecture documents remain authoritative for their individual
subsystems and historical decisions.

## Long-term objective

Build a conservative automated trading platform that can progress safely from
deterministic historical research to simulated paper trading, broker-paper
operation, restricted live trading, and finally a polished end-user
application.

The platform is not permanently paper-only. Live trading is a long-term product
goal, but it remains unavailable until all separately reviewed safety,
credential, brokerage, reconciliation, operator-control, and acceptance gates
are complete.

## Current production status

**Production/live trading: NO-GO.**

C2 is complete and merged. The Windows transactional authority is available as
a reviewed runtime boundary behind the C1 `ValidatedProductionAuthority`
capability, but the production effect boundary is intentionally still inert on
this GUI branch. The active C3 production-security work continues separately on
`feature/windows-effectful-market-data-capture`; GUI work must not bypass or
reimplement those authority boundaries.

## Implemented foundations

The repository currently includes:

- deterministic trade proposal, risk, execution, portfolio, and ledger models;
- historical market-data providers and deterministic NYSE/XNYS calendar support;
- single- and multi-symbol backtesting with complete-frame and next-open semantics;
- baseline strategies, walk-forward/research infrastructure, optimization, analytics, and human-readable reporting;
- simulated paper-account and paper-operation/recovery infrastructure;
- durable evidence, deterministic UUID5/canonical serialization contracts, and historical-evaluation integrity rules;
- Windows authority provisioning, schema, validation, capability, and transactional-authority milestones through C2;
- a canonical production transactional SQLite artifact and reviewed lifecycle/recovery/concurrency boundaries;
- a native PySide6 GUI foundation with read-only research exploration/comparison, one bounded read-only paper-operation inspection view, and one bounded offline-verified market-snapshot inspection view.

## Completed Windows authority milestones

### Architecture / transactional design

Architecture 77 defines the transactional capture-authority state machine,
durable evidence, capabilities, recovery rules, and lifecycle ordering.

### Production authority foundation

The completed Windows authority milestones provide fixed production paths,
provisioning/security validation, the canonical production SQLite schema,
C1 `ValidatedProductionAuthority`, and C2 `WindowsTransactionalAuthority`.

Architecture 81 is the current C2 service contract.

C2 final certification completed with:

- combined service + Architecture-77 suite: 775 passed;
- complete repository suite: 2,725 passed, 13 skipped, 0 failed;
- production SQL unchanged at 118,896 bytes with SHA-256
  `aa61df2f5db0090f8373222d1f5e492a58f4c10273afacfab45e382bacd4bb58`.

## Current production milestone: C3 effectful market-data capture

C3 converts the intentionally inert C2 external-effect boundary into a reviewed,
contained production market-data capture path. That work is isolated on its own
branch and remains authoritative for any production provider, credential,
process, publication, or selection boundary.

C3 does **not** add brokerage order execution or live trading.

## GUI track status

The GUI remains an isolated presentation/operator track on
`feature/gui-foundation`. It must consume reviewed application/service
boundaries rather than becoming an alternative trading, authority, credential,
or recovery engine.

### GUI-A1 through GUI-A4

Accepted GUI foundations include:

- native PySide6 application shell and stable navigation;
- Qt-free presentation/service contracts;
- explicit read-only local research-report loading;
- bounded research result table presentation;
- deterministic sorting/filtering and report replacement behavior;
- read-only comparison of two to four research variants;
- bounded comparison tables/charts with truthful return/drawdown/turnover semantics.

### GUI-A5 — paper-operation inspection: ACCEPTED

Architecture 91 defines a strictly read-only GUI boundary for one exact
paper-operation inspection result.

Accepted implementation sequence:

- `26833e8326f6cffef2c638543fb3174f1984e85f` — define Architecture 91 and Qt-free paper presentation/service contracts;
- `b3cdce458a1f884f6d25b6fa82039cc1b31e1015` — formatting-only follow-up;
- `bb057bc6864c4f340fa05651a4a63245ee491854` — add the concrete Qt-free read-only paper inspection adapter;
- `fbf8fcb8068fff394bb1b144d1fdddbf3c50e06f` — render the bounded Paper page in Qt;
- `86f1308dad98e763856fcf5c8504bff26804baf9` — update the older GUI-A2 research test fixture for the expanded GUI service contract;
- `6f1945172a6e8dad46327a0212c6bce0fac68256` — update the older GUI-A4 comparison test fixture for the expanded GUI service contract.

GUI-A5 accepted behavior:

- presentation scope is exactly one explicit inspected paper-operation root, not history/account/fill/order discovery;
- classifications are limited to `PENDING`, `ALREADY_APPLIED`, `CONFLICTING`, and `BLOCKED`;
- the presentation diagnostic vocabulary mirrors the reviewed closed inspection codes;
- the concrete adapter receives one explicit operation root and already-verified `VerifiedPaperOperationInputs`;
- GUI widgets do not construct paper-operation authority or enumerate arbitrary roots;
- inspection/adaptation failures collapse to bounded sanitized `UNAVAILABLE` state without raw exception text;
- `MainWindow` obtains the paper state once during construction; navigation does not reinspect;
- the Paper page renders classification, diagnostic, operation/checkpoint/application UUIDs, and optional bounded receipt path only;
- service-derived text is forced to literal Qt plain text;
- there are no execute/run/retry/resume/recover/cancel/refresh/open-receipt or other mutation/effect controls;
- no paper execution, filesystem history scan, production SQLite, C1/C2/C3, Credential Manager, Alpaca, brokerage, scheduler, or production-child path is connected.

Final GUI-A5 acceptance evidence at
`6f1945172a6e8dad46327a0212c6bce0fac68256`:

- targeted compatibility regression: 2 passed;
- complete GUI suite: 93 passed;
- manual visual gate: PASSED for both unavailable and populated read-only Paper presentation;
- complete repository regression: 2,822 passed, 13 skipped, 0 failed;
- Ruff check on `src tests`: passed;
- Ruff format check on `src tests`: 342 files already formatted;
- `git diff --check`: clean;
- final GitHub compare from A5b2 to accepted head: exactly 2 commits, 2 test files, 8 added lines, zero production-source changes;
- known unrelated generated/untracked artifacts and historical permission-warning directories remained untouched.

**GUI-A5 is fully ACCEPTED.**

### GUI-A6 — offline-verified market-snapshot inspection: ACCEPTED

Architecture 92 defines a strictly read-only Market Data presentation boundary
for one exact local daily-snapshot artifact that has passed the existing offline
snapshot verifier. The GUI does not claim that this artifact is the active
production C3-selected snapshot.

Accepted checkpoint sequence:

- `994fa3b6f452cb004d842aaa7f59166c6b1c4d4b` — define Architecture 92;
- `fd04e40cb1fa9af294e8fe1181446b66f614a715` — add the GUI-A6 validation plan;
- `3885e0c6e4e576e647e656401891c1a25e7c2d54` — accepted A6a Qt-free presentation/service contract;
- `e98b84bdb42066ef03593f3134b42dadf520f200` — accepted A6b1 explicit-path offline verification adapter;
- `f4015e4adefba123c7f3c1f1ee5df70158f6a9db` — accepted A6b2 native Qt Market Data rendering source.

GUI-A6 accepted behavior:

- presentation scope is exactly one explicitly supplied local daily-snapshot artifact;
- the adapter performs one bounded read of that exact artifact and calls the existing `verify_daily_snapshot(...)` verifier exactly once per state acquisition;
- only a complete verifier `PASS` becomes `VERIFIED` GUI state;
- verifier PASS proves canonical snapshot serialization, XNYS calendar/session consistency, complete requested-symbol coverage, canonical accepted-bar evidence, audit hash, deterministic snapshot identity, and optional artifact SHA-256/byte-length evidence;
- the bounded presentation exposes only snapshot/session identity, retained symbol order, provider identity/operation/feed, artifact digest/size, capture/provider-as-of timestamps, and retained source-payload digest/size/media type;
- read, parse, verification, model, calendar, or adaptation failures collapse to sanitized `UNAVAILABLE` state without raw exception or diagnostic-detail text;
- the adapter does not enumerate directories or choose a "latest" artifact;
- `MainWindow` obtains Market Data state once during construction; navigation does not reread or reverify;
- service/model-derived Qt text is forced to literal plain text;
- there are no Capture/Refresh/Retry/Reverify/Select/Publish/Recover/database/credential/provider controls;
- no network, Alpaca transport, environment credential, Windows Credential Manager, production SQLite, C1/C2/C3 capability, capture, paper execution, strategy, risk, or artifact mutation path is connected;
- `VERIFIED` means offline verification of the supplied artifact only; it does not mean C3 selected the artifact, that it is newest, or that a capture is authorized.

Final GUI-A6 acceptance evidence at
`f4015e4adefba123c7f3c1f1ee5df70158f6a9db`:

- A6a contract gate: 8 passed;
- A6a+A6b1 focused gate: 16 passed;
- A6b2 focused Qt gate: 24 passed;
- complete GUI integration suite: 114 passed;
- manual visual gate: PASSED for both unavailable and populated verified Market Data presentations;
- complete repository regression: 2,843 passed, 13 skipped, 0 failed;
- all 13 skips are the repository's expected Windows opt-in/symlink environment skips;
- Ruff check on `src tests`: passed;
- Ruff format check on `src tests`: 348 files already formatted;
- `git diff --check`: clean;
- final GitHub compare from accepted A5 closeout `a5f5b91efe855e5b2e4e11898e950733001ff10f` to A6 source head: 24 commits, 16 files, all within Architecture 92/A6 presentation, adapter, Qt rendering, validation, and stale GUI test-fixture compatibility scope;
- no C3/runtime authority, provider credential, production SQLite, strategy, risk, order, or brokerage source changed;
- known unrelated generated/untracked artifacts and historical permission-warning directories remained untouched.

**GUI-A6 is fully ACCEPTED.**

## Next GUI milestone: GUI-A7 read-only verified paper-account state

The next recommended GUI checkpoint is a read-only paper-account presentation
boundary. Its purpose is to expose already-verified simulated account state such
as cash, positions, realized P&L, checkpoint/account identity, and as-of time
without adding execution controls or pretending that an arbitrary file is the
current operational account.

The branch already contains two materially different reviewed offline proof
paths that Architecture 93 should reconcile at the presentation boundary:

- `verify_genesis_paper_account_checkpoint(...)` can completely verify one exact GENESIS checkpoint and reconstruct its compact `PaperLedger` state;
- `verify_checkpointed_paper_cycle_successor_edge(...)` can verify one successor only by replaying and reconciling the exact prior checkpoint, verified market snapshot, checkpointed-cycle report, and successor checkpoint edge.

Initial GUI-A7 architecture should determine the smallest common Qt-free
presentation contract that can truthfully represent either a completely verified
GENESIS state or a completely verified successor state. Likely bounded facts
include:

- checkpoint kind, sequence, checkpoint ID, lineage ID, and account-state ID;
- exact as-of timestamp;
- exact cash and realized P&L;
- bounded ordered positions with symbol, quantity, total cost basis, and average cost;
- artifact SHA-256 and byte-length evidence;
- successor-only application/cycle/snapshot references only if they are already part of the complete reviewed PASS result and can be presented without claiming history traversal.

GUI-A7 must not:

- discover or select a "latest" checkpoint by scanning directories;
- traverse checkpoint lineage automatically;
- claim an explicitly supplied checkpoint is the current operational account;
- run or resume a paper cycle;
- create orders/fills or call strategy/risk/execution paths;
- mutate, repair, publish, or replace checkpoint artifacts;
- expose raw parser/runtime exception text or arbitrary filesystem paths;
- open production SQLite, C1/C2/C3 authority, Credential Manager, Alpaca, or brokerage paths.

The intended dependency direction is:

```text
Qt Paper Account page
    -> Qt-free GUI paper-account presentation models
    -> GuiApplicationService.get_paper_account_state()
    -> reviewed/injected read-only checkpoint adapter
    -> existing offline checkpoint/edge verifier
```

Architecture/data-boundary selection is a **Sol Medium** task because GENESIS and
successor verification have different proof requirements and must not be
silently conflated. Once the common presentation contract and adapter semantics
are frozen, mechanical Qt rendering should be suitable for **Luna Extra High**.
Any proposal to identify the operationally current account by traversing durable
runtime state, production authority, or automatic lineage selection requires
**Sol High** review instead.

## Roadmap after C3

### 1. Reliable manual paper cycle

Establish one trustworthy end-to-end manual cycle:

verified market snapshot -> strategy -> proposals -> deterministic risk ->
paper execution -> durable before/after evidence.

The goal is an operator-verifiable cycle with no hidden manual state repair.

### 2. Unattended paper operation

Add the operational controls needed to run safely without a person driving each
cycle:

- authoritative XNYS session scheduling;
- Task Scheduler/service integration;
- startup reconciliation and crash recovery;
- health monitoring, alerts, and durable run status;
- stale-data and missing-data fail-closed behavior.

### 3. Long paper soak

Run the complete unattended paper system long enough to expose operational,
recovery, data-quality, scheduling, and reconciliation failures before adding a
real broker transport.

### 4. Broker-paper integration

Add a real brokerage adapter in paper/sandbox mode with:

- account and position reads;
- submit, cancel, and replace;
- broker order/fill identifiers;
- rejects and partial fills;
- durable reconciliation and idempotency;
- ambiguous-submit recovery;
- startup broker reconciliation.

Broker-paper must continue to pass through deterministic risk and the reviewed
application/runtime boundaries.

### 5. Live-readiness milestone

Before any real-money order path can be enabled, implement and accept:

- explicit operating-mode authority;
- credentials separated from paper credentials;
- exact brokerage account verification;
- strict initial live risk/exposure limits;
- kill switch / emergency stop;
- stale-data, market-halt, provider-outage, and brokerage-outage behavior;
- startup broker reconciliation before new orders are permitted;
- operator-visible health and reconciliation state;
- clear recovery procedures for ambiguous external outcomes.

### 6. Tiny restricted live deployment

Only after the live-readiness gates are accepted, permit a deliberately tiny,
long-only live deployment with conservative symbols, exposure, frequency, and
order-size limits.

Live mode must remain explicitly enabled and fail closed.

### 7. Mature operations and deepen AI

Expand strategies, optimization, and AI only after the platform demonstrates
trustworthy operations, durable evidence, reconciliation, and recovery.

AI may assist analysis and proposal generation but may never bypass deterministic
risk, authority, brokerage, or operator-control boundaries.

## 100% product-completion goal: user-friendly GUI

The final product milestone is a polished graphical application that makes the
reviewed platform usable without requiring routine command-line or database
inspection.

The completed GUI should provide, at minimum:

- portfolio value, cash, positions, allocation, P&L, and account dashboards;
- market/session, provider, scheduler, capture, brokerage, and system-health status;
- strategy selection/configuration and parameter management;
- backtest, walk-forward, optimization, and comparison workflows;
- price, equity, drawdown, allocation, entry/exit, and performance charts;
- proposal -> risk decision -> order -> fill traceability;
- simulated paper, broker-paper, and future live operational views;
- orders, fills, rejects, partial fills, positions, and reconciliation status;
- operator recovery workflows with clear explanations and confirmations;
- searchable audit/history views over durable evidence;
- risk, scheduling, notification, storage, provider, and operational settings;
- unmistakable backtest/paper/broker-paper/live mode indicators;
- future live account identity, enablement state, strict risk controls, and emergency-stop controls;
- actionable human-readable errors and recovery guidance rather than raw Python/SQLite failures.

The GUI is a presentation and operator-control layer, not an alternative trading
engine. It must call the same reviewed application/service boundaries used by
CLI, automation, tests, and unattended operation. It may not implement or bypass
independent trading, risk, authority, brokerage, reconciliation, credential, or
deterministic identity logic.

Core functionality must remain usable and testable without the GUI. Narrow
operator interfaces may be introduced before the final GUI milestone when they
are required for safe paper or live operation.

## Stable product constraints

Unless a later explicit architecture milestone changes them, the conservative
initial product constraints remain:

- long-only US stocks and ETFs;
- no margin or leverage;
- no options;
- no short selling;
- no crypto;
- deterministic risk approval for every order;
- paper mode by default;
- complete auditability of decisions and transactions.

## Documentation workflow

At each major milestone boundary:

1. Update this document's current/completed milestone status.
2. Keep detailed architecture documents as historical and subsystem records rather than rewriting prior decisions to look current.
3. Update the README only when the public project description or broad product status changes.
4. Keep `AGENTS.md` focused on stable development, safety, architecture, testing, and AI-workflow rules.
5. Start implementation tasks by reading `AGENTS.md`, this status document, and the architecture documents directly relevant to the milestone.
