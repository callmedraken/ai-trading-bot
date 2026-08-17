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
capability, but the production effect boundary is intentionally still inert.
There is no approved production provider transport, real child-process capture
path, unattended scheduler, brokerage live-order transport, or authorization to
place real-money orders.

## Implemented foundations

The repository currently includes:

- deterministic trade proposal, risk, execution, portfolio, and ledger models;
- historical market-data providers and deterministic NYSE/XNYS calendar support;
- single- and multi-symbol backtesting with complete-frame and next-open semantics;
- baseline strategies, walk-forward/research infrastructure, optimization, analytics, and human-readable reporting;
- simulated paper-account and paper-operation/recovery infrastructure;
- durable evidence, deterministic UUID5/canonical serialization contracts, and historical-evaluation integrity rules;
- Windows authority provisioning, schema, validation, capability, and transactional-authority milestones through C2;
- a canonical production transactional SQLite artifact and reviewed lifecycle/recovery/concurrency boundaries.

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

## Current milestone: C3 effectful market-data capture

C3 converts the intentionally inert C2 external-effect boundary into a reviewed,
contained production market-data capture path.

C3 should implement and validate:

1. Approved market-data provider construction and transport.
2. Reviewed credential retrieval through Windows Credential Manager or the approved OS secret-store boundary.
3. An isolated child process for effectful capture work.
4. `CreateProcessW` with the child initially suspended.
5. Job Object containment established before execution proceeds.
6. `ResumeThread` only after the reviewed durable authority/evidence ordering is satisfied.
7. Process lifecycle, exit, cleanup, and containment evidence.
8. Actual captured snapshot/content verification rather than caller-supplied digest trust.
9. Authorization of verified captured content before it becomes selectable market data.
10. Native Windows acceptance covering the real provider/process/credential/containment boundary.

C3 must preserve the durable intent/receipt, lifecycle arbitration,
one-shot-capability, recovery, crash-ambiguity, and fail-closed semantics already
established by C1/C2.

C3 does **not** add brokerage order execution or live trading.

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
