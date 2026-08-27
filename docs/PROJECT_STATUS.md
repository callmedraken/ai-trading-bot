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
- a native PySide6 GUI foundation with read-only research exploration/comparison and one bounded read-only paper-operation inspection view.

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

## Next GUI milestone: GUI-A6 read-only selected market-snapshot status

The next recommended GUI checkpoint is a read-only Market Data presentation
boundary. Its purpose is to expose already-reviewed market-snapshot/session
state without introducing capture controls or direct production authority access.

Initial GUI-A6 architecture should determine the smallest existing reviewed
source boundary that can truthfully provide, when available:

- snapshot/session identity and date;
- provider identity and operation;
- selected/available/unavailable presentation status;
- bounded artifact identity/digest/size metadata if already part of reviewed
  nonsecret state;
- bounded human-readable diagnostics when no selected snapshot is available.

GUI-A6 must not:

- launch or retry a C3 capture;
- read Windows Credential Manager;
- open production SQLite directly from Qt widgets;
- infer selection authority from files or directory enumeration;
- expose raw provider responses, credentials, native errors, or arbitrary paths;
- add refresh/recovery/capture controls unless a later architecture checkpoint
  explicitly defines their authority and lifecycle.

The dependency direction should remain:

```text
Qt Market Data page
    -> Qt-free GUI market-data presentation models
    -> GuiApplicationService.get_market_data_state()
    -> reviewed/injected read-only selected-snapshot adapter
    -> existing reviewed domain/application inspection boundary
```

The initial boundary/adapter design is a **Sol Medium** task because the data
contract must be selected carefully across existing market-data and authority
interfaces. Once that contract is frozen, mechanical Qt rendering and focused
presentation tests should be suitable for **Luna Extra High**. Any proposal that
would directly traverse C3 production authority, credentials, or effect ordering
requires **Sol High** review instead.

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
