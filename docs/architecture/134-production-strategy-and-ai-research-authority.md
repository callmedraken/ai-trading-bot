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

134-B's original source-accepted entry point remains a **legacy compatibility
adapter** for Architecture-94 callers. It still accepts an exact
`ManualPaperStrategyDecisionRequest`, requires a genuine construction-protected
`VerifiedPriorCheckpoint`, and returns the same closed
`ProductionStrategyDecision` outcomes. That compatibility path is retained so
historical Architecture-94 plan/replay behavior does not regress.

It is **not** the current Robinhood production materialization path.

The accepted current-product path is Architecture 134-B2 below. Both the
historical adapter and the current Robinhood adapter enter the same extracted
pure daily-decision core, which evaluates the existing
`MovingAverageCrossoverStrategy` exactly once.

The closed production output remains exactly:

~~~text
NO_SIGNAL
TRADE_PROPOSAL
~~~

No adapter may substitute a research candidate, create broker authority, or
perform provider/OAuth/network/scheduler execution.

## 134-B2 — Current-product production-decision materialization

The original 134-B compatibility adapter accepts an Architecture-94
`ManualPaperStrategyDecisionRequest`; Architecture 134-B2 does **not** require
that legacy request or its protected prior authority. Retaining the compatibility
adapter does not make the historical personal-desktop Paper-v2/C3 runtime part
of Architecture 134 production authority.

Architecture 134-B2 is source accepted on the production live-paper branch. The
current Robinhood lane now materializes decisions from current-product evidence:

- exact 134-A production contract;
- verified daily snapshot/history evidence for the contract symbol/session;
- current synthetic-paper prior/account state derived from
  `ReviewPaperStore`;
- explicit deterministic planning/idempotency/policy inputs.

Architecture-94's `VerifiedPriorCheckpoint` is construction-protected authority
from the historical checkpoint-lineage system. The Robinhood adapter must
**never fabricate or synthesize that capability** from ReviewPaperStore.

134-B2 extracted/reuses the already-reviewed pure strategy-decision core beneath
the Architecture-94 request adapter. The existing Architecture-94 entry point
continues to validate/translate its legacy `VerifiedPriorCheckpoint`; the new
Robinhood entry point validates/translates independently verified
`ReviewPaperStore` state into a construction-protected current-product prior.
Both paths call the same pure decision core, which performs exactly one existing
strategy evaluation. The accepted 134-B closed `NO_SIGNAL` / `TRADE_PROPOSAL` contract
remains the production output boundary. It must not read
or repair D10/Windows/Paper-v2/C1/C3 personal-desktop state, use historical
Alpaca operational authority, or infer missing market history.

The materializer itself is source/provider-free. Real current market-history
acquisition/persistence remains the next source checkpoint and is separately
reviewed; it cannot be silently folded into SHADOW PREPARE.

A 2026-10-11 read-only diagnostic found a DACL mismatch only on
`F:\AITradingBot\Paper-v2` while its relevant descendants remained exact.
That legacy drift is not an Architecture-134 blocker and grants no ACL-repair
authority.


### 134-B2 accepted source

~~~text
BRANCH feature/robinhood-production-strategy-live-paper
HEAD   1e3c74649aeb6f0f90881b1495fec0350c22ae5e
TREE   b9ac7a11a39d07252ab85fd7b197b31590a825b9
CI     #478 / 38175971808 SUCCESS
~~~

The accepted implementation adds a current-product
`build_current_production_strategy_decision(...)` adapter, a read-only
`ReviewPaperStrategyPrior`, shared pure `daily_decision` logic, and provider-
free strategy-history primitives. The historical runtime history module is now
a compatibility export rather than the owner of the reusable history model.

Current profile inventory at this source is FULL **163**, ROBINHOOD **88**,
LEGACY **205**, EXHAUSTIVE **368**.

No separate broad certification is run at 134-B2. The pending ROBINHOOD
certification obligation is deliberately batched with the next current-history
acquisition/materialization checkpoint so that one coherent current-decision
source is certified exactly once before any protected SHADOW PREPARE.

## 134-B3 — Current Robinhood market-history evidence (CERTIFIED/CLOSED)

The current source checkpoint remains `arch134-production-strategy-live-paper`
on `feature/robinhood-production-strategy-live-paper`, with no preflight/execute
registration. B3 adds two owned test modules to that existing source gate;
active count stays 60. FULL/ROBINHOOD/LEGACY/EXHAUSTIVE inventory is now
165/90/205/370. Frozen required baselines remain 122/49.

B3 source/certification closeout:

~~~text
BRANCH      feature/robinhood-production-strategy-live-paper
HEAD        7ef32ec87dbcfeea4d5436c424cdbb0eb16e1058
TREE        738f078722337903ba7daf950bf19078167a75e4
CHECKPOINT  arch134-production-strategy-live-paper
CI          #482 / 38181823892 SUCCESS
~~~

The first ROBINHOOD certification on
`fde8cb35256e4448fef20e666f00b0d687b3f423` ran 8,269 cases and failed only
three stale current-profile inventory assertions. Its failed evidence is
preserved at:

~~~text
F:\AI\temp\certification\arch134b3-robinhood-4eaa0b0201cf43a19c420d00d5bbced5
~~~

The bounded test-only correction changed no production behavior, authority,
classification, topology or baselines. Final ROBINHOOD certification on the
exact HEAD/TREE above passed **8,269/8,269** cases across **90** modules:
robinhood-1 3,865/3,865 and robinhood-2 4,404/4,404, zero
skips/failures/errors, wall 325.912 s. Evidence:

~~~text
F:\AI\temp\certification\arch134b3-robinhood-b14f5add0e5040599b093c7238b01a54
~~~

No FULL/LEGACY/EXHAUSTIVE rerun and no protected provider/OAuth/paper/scheduler/
broker effect was required for B3 closure.


`RobinhoodDailyHistoryRequest` derives exactly `long_window + 1` consecutive
sessions through the exact bound XNYS calendar, checks them against the existing
NYSE published regular-session authority, and admits only completed sessions.
Published coverage remains 2026-2028; requests requiring earlier history fail
closed. The MCP range runs from the first regular open through the last regular
close. The only request is `get_equity_historicals` with one exact contract
symbol, explicit UTC bounds, `interval=day`, `bounds=regular`, and
`adjustment_type=none`. No interval/adjustment defaults, pagination, retries,
interpolation, alternate provider, CSV, quotes-as-history or inferred bars.

The strict parser requires the documented structured `data/results/bars` and
`guide` shape, one exact result, exact symbol/daily/regular semantics, all
required bar fields, explicit `session=reg` and `interpolated=false`, positive
integer traded volume and bounded positive decimal OHLC. Unknown fields,
missing/unresolved symbols, malformed/non-UTC timestamps, unknown/midnight
labels, duplicate/missing/out-of-order/nonconsecutive sessions, extra bars,
invalid OHLCV, split/dividend adjustment echoes or insufficient history fail
closed. Optional adjustment echo must be `none` if present. Bars must have
left-edge labels equal to the published regular opens; DST and early closes
are calendar-bound. No transformation or invented daily aggregation occurs.

`materialize_production_strategy_history` replays retained canonical structured
response bytes and checks exact contract symbol/config/session and capture time.
The prior completed session goes through existing snapshot acceptance,
serialization and `verify_daily_snapshot` to obtain
`DailySnapshotVerificationResult`. The snapshot audit hashes the canonical
structured response (not purported raw HTTP bytes). The preceding configured
consecutive bars go through `create_strategy_history_seed`, canonical
serialization and `verify_strategy_history_seed` to obtain
`VerifiedStrategyHistorySeed`. Existing history-seed schema, IDs, verifier,
`OFFLINE_SEED` classification and `authoritative=false` remain unchanged.
Provider provenance belongs to an outer `robinhood-strategy-history-evidence/v1`
envelope retaining request, structured response, XNYS session sequence and times.
Hashes are audit evidence only, never deterministic semantic identity material.
Canonical snapshot, seed and outer bytes are returned in memory; this checkpoint
adds no filesystem persistence or paper-store mutation boundary.

`acquire_production_strategy_history` permits exactly one adapter historical
read and one caller-injected capture-time observation. Production invocation
is separately protected; source tests inject fakes. The pure
`build_production_strategy_decision_from_history` replays all evidence and
delegates exactly once to accepted 134-B2. No legacy Paper-v2/D10/C1/C3/Alpaca
authority, `VerifiedPriorCheckpoint`, new evaluator, research promotion,
SHADOW PREPARE or paper execution is introduced.

The exact application read/review allowlist is now four public tools:
`review_equity_order`, `get_equity_quotes`, `get_equity_orders`, and
`get_equity_historicals`; `get_accounts` is private/internal. Capability
enumeration requires all four; extra advertised broker tools never become
application capabilities. Placement/cancel/options/crypto remain excluded.

B3 source/certification is closed. Real-server qualification remains the next
separately protected boundary. The published tool metadata documents raw
`none` request semantics but no required response adjustment echo; request
honoring must be qualified. Daily regular-open left-edge labels and explicit
false interpolation/regular-session flags must also be qualified. `close_price`
means the last trade in the regular daily bar, not an official settled close.
Any mismatch blocks materialization rather than weakening the parser. The
qualification may perform only the explicitly authorized read-only provider/OAuth
effect; persistence/operator wiring, SHADOW PREPARE, paper execution, scheduler
mutation and broker placement remain outside this closure.
