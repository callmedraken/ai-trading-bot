# Architecture 134 — Production strategy and AI-research authority

## 2026-10-11 — Architecture 134-A SOURCE ACCEPTED

Architecture **134-A — Production Strategy Contract** is source accepted.

~~~text
BRANCH  feature/robinhood-production-strategy-contract
HEAD    d49f6e718b27207acad39ad323c76db196b6d7a9
TREE    239513ff3063610b675213a124208edb933846ac
COMMITS
4831aaaa53769e01cec4d9a8a1a25dec7bd221f7  feat: add production strategy contract
d49f6e718b27207acad39ad323c76db196b6d7a9  test: satisfy production strategy source gate
CI      #459 / 38125675113 SUCCESS
~~~

Exact GitHub review confirmed the implementation is the frozen inert boundary:

- canonical `production-strategy-contract/v1`;
- one explicit target date, one exact `Symbol`, exact reviewed source HEAD/TREE;
- `MovingAverageCrossoverStrategy` / `1.0.0` with the existing validated config;
- deterministic UUID5 semantic identity and strict canonical JSON replay;
- construction of the existing pure strategy only; no evaluation;
- no provider/MCP/OAuth, market-data, paper-store, risk, scheduler, clock,
  filesystem, research/AI, optimization, dynamic import or execution authority;
- checkpoint `arch134-production-strategy-contract` has `preflight=None` and
  `execute=None` and one exact active branch route.

Source gate #459 on the exact accepted head passed:

~~~text
source-static  SUCCESS
  git diff --check  PASS
  Ruff check        PASS
  Ruff format       PASS
  authority         PASS
  identity stable   True

active-tests   SUCCESS
  pytest            PASS
  identity stable   True

full-tests     SKIPPED
source-gates   SUCCESS
~~~

Current exact inventories are active **58**, FULL **159**, ROBINHOOD **85**,
LEGACY **205**, EXHAUSTIVE **364**. No broad certification is selected at this
pure-model checkpoint.

A separate source-gate failure #460 on
`feature/robinhood-production-strategy-decision` used this same HEAD before
134-B had any registered route. It is not a 134-A failure and grants no 134-B
acceptance.

Next milestone is **134-B — Production Strategy Decision Bridge**: provider-free
composition of the accepted production contract with verified daily strategy
history/current bar and authoritative paper-account state, evaluating the
selected strategy exactly once and returning a closed `NO_SIGNAL` or exact
`TradeProposal`. 134-B still has no provider call, paper mutation, scheduler,
arming, risk execution or broker effect.

## Product goal

The bot is operator-armed before an NYSE session, waits until the admitted
regular-session window, and trades a **single session-locked production
strategy** through the review-paper path while an independent AI/research lane
may develop and evaluate candidate strategies.

Production and research are intentionally asymmetric:

- production is boring, deterministic, bounded, and session-locked;
- research is exploratory and may create many candidates;
- research can never promote itself, change production risk, or write the
  production paper account;
- only an explicit human promotion can select a candidate for a future session.

Real-money order placement remains outside Architecture 134. The first target is
Robinhood-backed **live-data synthetic paper trading**: provider quotes/order
review are real reads; fills/accounting remain local synthetic paper effects.

## Reused accepted foundations

Architecture 134 reuses rather than replaces:

- `MovingAverageCrossoverStrategy` and `MovingAverageCrossoverConfig`;
- Architecture-94 verified daily-history strategy planning lessons;
- deterministic `TradeProposal` and risk manager contracts;
- Architecture-131 session admission, live quote acquisition, risk preview,
  PREPARE/EXECUTE and Robinhood review-paper pipeline;
- durable `ReviewPaperStore` and performance/account reconstruction;
- published XNYS/NYSE session authority;
- existing backtest, analytics, optimization and walk-forward research tools.

## Non-negotiable production/research separation

A production strategy selection is immutable for its target session once armed.
Research may observe copies/read-only evidence and write only research-owned
artifacts. Research must not:

- rewrite or select the armed production contract;
- change production strategy parameters mid-session;
- change production risk limits or trading-enabled state;
- mutate the production paper store;
- invoke the production provider/review execution path;
- enable/start/alter the production scheduler;
- mint execution, retry, wake or broker authority;
- place/cancel equity, options or crypto orders.

Promotion is always a future-session transition. Candidate quality, confidence,
backtest performance or AI recommendation is evidence only, never authority.

## 134-A — Production Strategy Contract

### Purpose

134-A creates the smallest pure object needed to answer: **what exact strategy
is production allowed to evaluate for this session?**

Expected public model:

~~~text
ProductionStrategyContract
  schema
  contract_id
  target_session_date
  source_head
  source_tree
  strategy_id
  strategy_version
  symbol
  strategy_config
~~~

V1 constraints:

- `schema == production-strategy-contract/v1`;
- exactly one `Symbol`;
- exactly one explicit `date` target session (calendar validity is checked by a
  later session-aware composition, not by this pure model);
- source HEAD/TREE are lowercase 40-hex reviewed identities;
- strategy is exactly `MovingAverageCrossoverStrategy` / `1.0.0`;
- config is exactly the existing validated `MovingAverageCrossoverConfig`;
- semantic ID is deterministic UUID5 over versioned, length-framed/canonical
  semantic material; serialized bytes/hash/path are not semantic authority;
- canonical JSON has exact fields, no duplicates/unknown fields, canonical
  decimals, and strict byte-for-byte round-trip;
- helper construction may return the existing
  `MovingAverageCrossoverStrategy(config)` only.

### Explicit exclusions

134-A has no filesystem, environment, subprocess, Git, network, MCP/OAuth,
market-data, clock, sleep, scheduler, SQLite, paper-store, risk, execution,
broker, AI/model, optimization, experiment, dynamic import, plugin loading or
arbitrary-code capability.

It does not decide whether the target date is an NYSE session, evaluate a
strategy, produce a proposal, arm a bot, or persist an approval. It is inert
contract material only.

### Source checkpoint

~~~text
branch      feature/robinhood-production-strategy-contract
checkpoint  arch134-production-strategy-contract
preflight   None
execute     None
~~~

The checkpoint's authority check pins the production model and its focused test
surface. It is source-only and gains no protected runtime capability.

## Subsequent production lane

### 134-B — Production Strategy Decision Bridge

Consume an exact 134-A contract plus verified daily history/current bar and
authoritative paper-account state. Reuse existing strategy evaluation exactly
once and emit a closed result: `NO_SIGNAL` or the exact strategy
`TradeProposal`. No provider or paper mutation.

### 134-C — Human-started live-paper cycle

Compose 134-B with the accepted Architecture-131 live quote/risk/review-paper
path. Support a read-only shadow mode and one explicit paper mode. Paper mode
may call the already-qualified non-placement Robinhood review path and create
one local synthetic paper result. Broker placement remains impossible.

### 134-D — Armed session mode

Introduce `ARMED -> SESSION_OPEN -> RUNNING -> TERMINAL` control around one
target NYSE session. Operator arms before market; no early execution is
possible. Session timing is derived from published session authority, not a
hard-coded 06:30 offset. DST therefore follows the exchange calendar.

### 134-E/F — unattended proof

First qualify one unattended integration session, then a fresh multi-session
paper soak. These validate scheduling/restart/idempotency and operational
behavior, not strategy promotion.

## Research lane

Research is a later parallel source family. It should define explicit candidate
artifacts and lifecycle states such as:

~~~text
EXPERIMENTAL
BACKTESTED
WALK_FORWARD_PASSED
SHADOW
PAPER_CANDIDATE
AWAITING_HUMAN_PROMOTION
~~~

Research reuses existing historical experiments, optimization, backtesting,
analytics and walk-forward machinery. It can rank/recommend candidates but has
no API that returns or writes an armed production contract. Human promotion
creates a new production selection for a future session through a separately
reviewed boundary.

## Deployment

The simplified fixed-worktree deployment model remains in force. Architecture
134 does not revive STAGING/FINAL publication, AG/AJ retry, automatic code
deployment or self-modification.
