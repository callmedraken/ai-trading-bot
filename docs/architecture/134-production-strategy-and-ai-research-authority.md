# Architecture 134 — Production strategy and AI-research authority

## 2026-10-11 — Architecture 134-C CERTIFIED/CLOSED

Architecture **134-C — Human-started production live-paper cycle** is
**CERTIFIED/CLOSED** at this exact source-certification boundary:

~~~text
BRANCH      feature/robinhood-production-strategy-live-paper
HEAD        bcda794f8b371b097143a331d678009143cb91b1
TREE        96a36cf38133ae3547175fe75547a4e16f1deb48
CI          #471 / 38133206242 SUCCESS
CHECKPOINT  arch134-production-strategy-live-paper
CORRECTION  bcda794f8b371b097143a331d678009143cb91b1
SUBJECT     test: stabilize checkpoint topology assertions
~~~

### Preserved failed FULL and bounded source correction

The first FULL attempt on prior source
`144a66928d9f3fb3d7ff5396059c998839e17a99` /
`04f7ade45d5fdf1e4e6969db8a9b1db5484fa8b2` found 22 stale historical
test-topology assertions after the active inventory grew to 60 checkpoints.
Its failed evidence is preserved and must not be overwritten or reused:

~~~text
F:\AI\temp\certification\arch134c-full-e210ffcf373748d593a2df83f7b39512
~~~

The bounded test-only correction:

- replaced fragile end-relative checkpoint slices with named/local adjacency;
- removed historical tests' unowned repository-wide eventual-count assumptions;
- confined generic registration mutations to their intended `CheckpointSpec`;
- preserved the dedicated canonical full-topology expectation;
- preserved production behavior, authority, registration, workflow and source
  pins.

The separately approved publication-recovery test expectation proves that only
the historical whole-registry pin differs after later registrations and that
the unchanged protected authority rejects that drift exactly. It does not
refresh a pin or reopen historical recovery authority.

Source gate [#471](https://github.com/callmedraken/ai-trading-bot/actions/runs/38133206242)
is terminal green:

| Job | Conclusion |
| --- | --- |
| source-static | SUCCESS |
| active-tests | SUCCESS |
| full-tests | SKIPPED, correct active-branch behavior |
| source-gates | SUCCESS |

### Final cheap gates before FULL

Exact source/FULL topology plan, `git diff --check`, Ruff check and Ruff
format check all passed before the expensive suite. Ruff format check reported
919 files already formatted. The plan evidence is:

~~~text
F:\AI\temp\certification\arch134c-final-full-plan-ae24aee5c593433683993fbccafa70d7
~~~

### Final FULL certification

| Lane | Modules | Cases | Passed | Skipped | Failed | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| broad-1 | 80 | 4,764 | 4,764 | 0 | 0 | 0 |
| broad-2 | 81 | 4,320 | 4,320 | 0 | 0 | 0 |
| Total | 161 | 9,084 | 9,084 | 0 | 0 | 0 |

~~~text
profile full PASS
wall 446.814 s
evidence F:\AI\temp\certification\arch134c-final-full-e971d0c5bfda496ebde97a6fc04d1afb
~~~

No separate ROBINHOOD run was required: ROBINHOOD is a strict subset of FULL,
and this selected FULL certification satisfies the narrower source-certification
obligation on the same source. No LEGACY/EXHAUSTIVE run was required. No
provider/OAuth/paper/scheduler/broker/protected effect occurred.

Current exact inventories are active **60**, FULL **161**, ROBINHOOD **86**,
LEGACY **205**, EXHAUSTIVE **366**. The executable/test source is unchanged by
this six-file docs-only closeout. **Do not rerun FULL on that unchanged source.**

### Immediate next boundary: separately authorized SHADOW PREPARE

The next step is a **human-started 134-C SHADOW PREPARE**, using the already
accepted Architecture-131 provider-read path. It requires fresh explicit
authorization because a trade proposal performs real Robinhood/provider/OAuth
read activity. No effectful command is ordinary verification, and this closeout
stops at that protected authorization boundary.

PREPARE is shadow/live-data preview only; it performs no paper fill.
`NO_SIGNAL` has zero provider/paper effects. **`READY_TO_PROCEED` is evidence,
not execution authorization.** Only after a separately authorized PREPARE
returns and ChatGPT reviews its evidence may a separate paper EXECUTE
authorization be considered if the retained result is `READY_TO_PROCEED` and
Architecture-131 revalidation still passes. Real broker placement remains
impossible. 134-C certification does not authorize 134-D scheduling/arming;
134-D remains later.

### Docs-only closeout and repository rules

This atomic checkpoint changes exactly the six approved `docs/**` files and
uses the existing docs-only classifier's cheap validation path. It changes no
Python, tests, scripts, workflow YAML, checkpoint registration or runtime
behavior and manufactures no test rerun.

`AGENTS.md` was reviewed and remains compatible: it already forbids repeated
expensive full-suite runs and delegates detailed certification behavior to
Architecture 132 and the workflow document. It remains unchanged because it is
outside `docs/**`. A future naturally necessary non-docs workflow checkpoint
may mirror the detailed wording there without creating a standalone duplicate-
test event.

## 2026-10-11 — Architecture 134-B SOURCE ACCEPTED

Architecture **134-B — Production Strategy Decision Bridge** is source accepted.

~~~text
BRANCH  feature/robinhood-production-strategy-decision
HEAD    695fa6195b2d8cc1437ba87f5d48c527afa28da7
TREE    00871d80bc9ae0a3f60906d23c92b30e42c670c4
CI      #465 / 38128865894 SUCCESS
~~~

The accepted bridge consumes the exact 134-A production contract plus the
existing Architecture-94 verified strategy-decision request/calendar boundary.
It checks contract config and verified seed symbol/config before the builder,
invokes `build_manual_paper_strategy_decision(...)` exactly once, then requires
the prepared config/symbol/intended session to remain inside the production
contract.

Closed outcomes are exactly `NO_SIGNAL` or `TRADE_PROPOSAL`; a proposal is the
exact Architecture-94 proposal object by identity, not a newly generated or
research-selected proposal.

Source gate #465 passed static diff/Ruff/format/authority, focused pytest, stable
identity and terminal source-gates. The earlier #462/#464 failures were
mechanical Ruff formatting only and are superseded.

Current exact inventories are active **59**, FULL **160**, ROBINHOOD **85**,
LEGACY **205**, EXHAUSTIVE **365**. Broad certification remains deferred until
the first coherent live-paper integration boundary.

134-B owns no Robinhood/provider/OAuth, paper-store mutation, risk execution,
scheduler, clock/sleep, research/AI promotion or broker placement authority.

Next milestone is **134-C — Human-started production live-paper cycle**.
`PREPARE` will serve as the shadow/live-data preview: for a `TRADE_PROPOSAL`,
reuse the accepted Architecture-131 supervised PREPARE path to obtain one live
Robinhood quote, session admission and deterministic risk preview with no paper
mutation. `NO_SIGNAL` performs no provider call. A separate explicit EXECUTE
may then reuse the accepted Architecture-131 review-paper execution path to
record one synthetic local paper fill; real broker placement remains impossible.

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

### 134-C — Human-started production live-paper cycle

134-C composes the accepted 134-B decision with Architecture-131 supervised
review-paper PREPARE/EXECUTE. It does not reimplement strategy, quote, risk or
paper accounting logic.

`NO_SIGNAL` is a true zero-provider/zero-paper outcome. A trade proposal must
match the exact 134-B retained proposal and target session before PREPARE can
reach Architecture 131.

134-C is CERTIFIED/CLOSED at the source identity recorded above. PREPARE is
the shadow boundary: at most one quote acquisition and risk preview, with no
review order and no synthetic fill. `READY_TO_PROCEED` grants no execution
authorization. EXECUTE is separately authorized and is a distinct explicit
call allowed only from exact `READY_TO_PROCEED` preparation; it additionally
binds expected source HEAD/TREE to the production strategy contract and delegates
once to Architecture-131 execution.

Real broker order placement remains impossible and out of scope.

## 134-B — Production Strategy Decision Bridge

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


## 134-B — Production Strategy Decision Bridge

134-B binds the session-scoped production selection to the repository's existing
verified daily strategy-decision path. It deliberately does **not** create a
second strategy-history/account reconstruction implementation.

### Inputs

Exactly:

- one `ProductionStrategyContract` from 134-A;
- one `ManualPaperStrategyDecisionRequest` from Architecture 94;
- one `IdentifiedMarketCalendar` accepted by the Architecture-94 builder.

Before invoking strategy evaluation, require:

- request `strategy_config == contract.strategy_config`;
- verified history-seed `strategy_config == contract.strategy_config`;
- verified history-seed symbol exactly equals `contract.symbol`.

Then call `build_manual_paper_strategy_decision(request, calendar)` exactly once.
That accepted builder independently replays the verified daily snapshot, seed,
prior paper checkpoint/account state and calendar and evaluates the existing
`MovingAverageCrossoverStrategy` exactly once.

After that single call require:

- prepared `strategy_config == contract.strategy_config`;
- prepared `symbol == contract.symbol`;
- prepared `intended_execution_session.session_date ==
  contract.target_session_date`;
- prepared signal/proposal combination remains exactly consistent with the
  existing `ManualPaperStrategySignalStatus` contract.

### Closed output

`ProductionStrategyDecisionStatus` has exactly:

~~~text
NO_SIGNAL
TRADE_PROPOSAL
~~~

`ProductionStrategyDecision` retains:

- the exact `ProductionStrategyContract` object;
- the exact `PreparedManualPaperStrategyDecision` returned by Architecture 94;
- the matching closed status;
- `proposal=None` for `NO_SIGNAL`, otherwise the exact retained `TradeProposal`
  object by identity.

The bridge does not generate a new proposal, order ID, risk decision, strategy
identity or source identity. It cannot substitute a research candidate.

### Capability boundary

Allowed direct dependencies are limited to the production contract, existing
Architecture-94 strategy-decision model/builder, domain proposal types and
market-calendar typing needed for the pure composition.

Forbidden capabilities include Robinhood/MCP/OAuth, network, filesystem/Git/
environment, SQLite/paper store, risk evaluation, review/execution/order engine,
scheduler, clock/sleep, runtime/native host code, experiments/optimization/AI,
candidate selection or promotion.

134-B has no registered preflight or execute callback. Source acceptance grants
only the right to proceed to 134-C design.


## 134-B2 — Current-product production-decision materialization

134-B's pure bridge intentionally accepts an Architecture-94
`ManualPaperStrategyDecisionRequest`; that type reuse does **not** make the
historical personal-desktop Paper-v2/C3 runtime part of Architecture 134
production authority.

The current Robinhood lane requires a dedicated materialization boundary that
constructs the exact 134-B request from current-product evidence:

- exact 134-A production contract;
- verified daily snapshot/history evidence for the contract symbol/session;
- current synthetic-paper prior/account state derived from
  `ReviewPaperStore`;
- explicit deterministic planning/idempotency/policy inputs.

It must preserve Architecture-94 verification semantics and call the accepted
134-B bridge rather than reimplementing strategy evaluation. It must not read
or repair D10/Windows/Paper-v2/C1/C3 personal-desktop state, use historical
Alpaca operational authority, or infer missing market history.

The materializer itself is source/provider-free. Any later live market-history
acquisition or persistence boundary is separately reviewed and cannot be
silently folded into SHADOW PREPARE.

A 2026-10-11 read-only diagnostic found a DACL mismatch only on
`F:\AITradingBot\Paper-v2` while its relevant descendants remained exact.
That legacy drift is not an Architecture-134 blocker and grants no ACL-repair
authority.
