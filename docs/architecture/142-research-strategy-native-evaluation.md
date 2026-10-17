# Architecture 142 / RCL-5 — Strategy-native research evaluation

Status: **142-A SOURCE ACCEPTED; 142-B SOURCE NOT IMPLEMENTED**.

## 142-A source acceptance

Architecture 142-A / RCL-5 is SOURCE ACCEPTED on the isolated safe-side branch:

```text
branch  feature/research-strategy-native-evaluation-current
base    d9960c7480b2eebc2c6e4530b2bafaec47292036
HEAD    9ce66811aa37a47ee4f5d769cea1ff4c33b8dcae
TREE    447656468e1214b27028aff8516f80146d1cc398
```

Accepted lineage is
`d9960c7 -> 262adc5 -> 5027aff -> 9ce6681`.

The initial implementation commit
`262adc52b5c17644a05c1d4872f6d1454fa2917e` introduced the strategy-native
definition, evaluation policy, deterministic offline backtest evidence, exact
in-memory completed-result carrier, external replay verification, focused tests
and additive package exports. Checkpoint Source Gates #619 /
`39074231322` preserved its red result: static source authority rejected the
new `tests/scripts/certification_runner/test_profiles.py` blob because the
current successor overlay had not yet admitted it.

Corrective C1 `5027aff238c865041e1bb98274fc4aeadcc19395` added only the
mechanically required Architecture-142 current-inventory pin overlay and
successor composition. #620 / `39074576264` then passed static admission; its
FULL shards exposed only stale current FULL/EXHAUSTIVE inventory assertions and
one retained predecessor test that had not yet composed the new overlay.

Corrective C2 `9ce66811aa37a47ee4f5d769cea1ff4c33b8dcae` changed only
`scripts/checkpoint_runner.py` and the current inventory/pin tests required by
that mechanically exposed successor layer. Final Checkpoint Source Gates #621 /
`39075494778`, workflow_dispatch attempt 1, is terminal SUCCESS on exact final
HEAD/tree. Static diff/Ruff/format admission passed. All four FULL shards passed
with `PYTEST=0` in 75.282 / 98.325 / 90.395 / 85.452 seconds, all below the
300-second hygiene ceiling, and source-gates passed.

Final implementation blobs include:

```text
research_strategy_definition.py  f018076cc9adc17a06d3b335c7f297ecba6f2c38
research_strategy_backtest.py    44cdc57901b5b63b611ff8ad1a53b95f22b7837f
test_research_strategy_definition.py 5418ecb926bc73b1b91a8a9fad7c5a0d4debd0cf
test_research_strategy_backtest.py   d3a4e54edc182c95c2f54bd91ed665099bb7d440
checkpoint_runner.py              93d62b15519948b822181b161ebc30956e755ecc
```

The workflow blob remains exactly
`fe6aceac62721338eba4fcb40e2e7fde0d976e18`.

Accepted behavior:

- fixed production family/version are carried by construction;
- exact `Symbol` and exact `MovingAverageCrossoverConfig` are immutable
  definition semantics;
- every behavior-affecting BacktestConfig/RiskLimits value is bound explicitly;
- only caller-supplied exact RAW daily single-symbol `HistoricalDataResult`
  is accepted;
- no symbol or strategy mapping is inferred;
- run IDs, historical fingerprints, complete-result fingerprints and evidence
  IDs are deterministic UUID5 values over canonical semantic material;
- the supplied-data adapter is in-memory only and rejects any request other than
  the exact bound request;
- the unchanged `BacktestEngine`, `MovingAverageCrossoverStrategy`,
  `NYSEMarketCalendar` and `PerformanceAnalyzer` perform the offline
  computation;
- the result fingerprint covers the complete behaviorally material
  `BacktestResult` audit, including the complete `TradingSession` semantic
  model (currently exact session date);
- external verification reruns the engine/analyzer and requires exact result,
  report and evidence reconciliation;
- parser methods prove canonical self-consistency only.

Architecture 139 and Architecture 141 remain immutable; 141 remains
`NOT_ESTABLISHED`. 142-A creates no `ProductionStrategyContract`, positive
compatibility, PAPER_CANDIDATE, promotion, provider acquisition, credential
access, production/paper runtime mutation, broker effect, scheduler effect,
D1/D2 or live authority.

Final inventory is FULL 184 / ROBINHOOD 101 / LEGACY 222 / EXHAUSTIVE 406.
Required frozen baselines remain FULL 122 / ROBINHOOD 49. Architecture 142-A is
research-only and is not an ACTIVE production checkpoint.

The feature source is not merged by this acceptance closeout.

The next safe-side source checkpoint is **Architecture 142-B** on the same
isolated strategy-native research lineage. 142-B may consume accepted 142-A
definition/policy/backtest evidence to add strategy-native walk-forward evidence
and qualification only. It still cannot create positive compatibility,
ProductionStrategyContract, PAPER_CANDIDATE, promotion or any operational
authority.

## Purpose

Architecture 142 creates a new research evidence family whose strategy semantics
are production-equivalent **by construction**. It does not retrofit the accepted
Architecture-139 SHADOW candidate or reinterpret Architecture-141
`NOT_ESTABLISHED` evidence.

The accepted portfolio-research chain remains immutable:

- Architecture 139-B remains one SHADOW portfolio-research candidate;
- Architecture 141 remains `NOT_ESTABLISHED` compatibility evidence;
- no old `variant_id`, rank, metadata, symbol universe or numeric coincidence
  becomes a production mapping.

The current production strategy family is exactly
`MovingAverageCrossoverStrategy` / `1.0.0`, with an exact `Symbol` and
`MovingAverageCrossoverConfig`. Architecture 142 creates a separate
strategy-native research definition carrying those semantics explicitly and
evaluates that definition only through the existing deterministic
single-symbol `BacktestEngine` and `PerformanceAnalyzer`.

Architecture 142 grants no production contract, paper-candidate, promotion,
provider, broker, scheduler, D1/D2 or live authority.

## Exact design base and isolated lineage

Design base:

```text
develop HEAD  157b621228af7cb5da56dab8e8427d9129ffcaff
develop TREE  a995091015dc83ce27700df892afe5bec4e77588
```

Implementation worktree:

`F:\AI\worktrees\ai-trading-bot-research-strategy-native-evaluation-current`

Implementation branch:

`feature/research-strategy-native-evaluation-current`

Architecture 142 is split into two independently reviewable source checkpoints
on that branch:

1. **142-A** — strategy definition, evaluation policy, deterministic single-
   symbol backtest evidence and pure offline runner/verifier.
2. **142-B** — strategy-native walk-forward evidence, qualification policy,
   qualification result and WALK_FORWARD_PASSED research evidence.

142-B may begin only after 142-A source acceptance. Each sub-checkpoint is one
logical atomic commit/push and one planned CI admission attempt, with bounded
mechanical C1/C2 continuation under the canonical workflow rules.

## 142-A — strategy-native definition

New module:

`src/trading_bot/experiments/research_strategy_definition.py`

Schema:

`research-strategy-definition/v1`

Identity version:

`research-strategy-definition-identity/v1`

UUID5 namespace:

`0b64cd96-bc4a-569e-aaa6-8cee8a0c037d`

Immutable fields:

```text
schema
definition_id
strategy_source_head
strategy_source_tree
production_strategy_schema
strategy_id
strategy_version
symbol
strategy_config
```

Runtime types are exact:

- `symbol`: exact `Symbol`;
- `strategy_config`: exact `MovingAverageCrossoverConfig`.

V1 production identity is frozen, not caller-selectable:

```text
production_strategy_schema = production-strategy-contract/v1
strategy_id                = MovingAverageCrossoverStrategy
strategy_version           = 1.0.0
```

Canonical config transport contains exactly:

```text
short_window
long_window
desired_quantity
```

Identity material is length-framed UTF-8 in this exact order:

```text
research-strategy-definition-identity/v1
schema
strategy_source_head
strategy_source_tree
production_strategy_schema
strategy_id
strategy_version
symbol
short_window
long_window
canonical desired_quantity
```

Source HEAD/TREE are exact lowercase 40-hex provenance only. They do not prove
GitHub acceptance.

The definition has no target session, rank, variant name, metadata, optimizer
settings, compatibility flag, verified flag, lifecycle stage or promotion
field. A different strategy family/version requires a separately reviewed
schema/evaluator.

## 142-A — evaluation policy

The definition module also owns the pure policy:

Schema:

`research-strategy-evaluation-policy/v1`

Identity version:

`research-strategy-evaluation-policy-identity/v1`

UUID5 namespace:

`26c58998-5378-5140-928c-fa3db4488b77`

The runtime model contains exact `RiskLimits` and binds every
`BacktestConfig` / `RiskLimits` value that changes behavior. No hidden
defaults are permitted.

Required semantics are exactly:

```text
starting_cash
fixed_commission
slippage_basis_points
trading_enabled
allow_missing_sessions
max_position_percent
max_total_exposure_percent
max_order_notional
max_new_position_percent
minimum_cash_reserve_percent
allow_fractional_shares
fractional_increment
allow_buying
allow_selling
estimated_commission
```

All fields are mandatory even where the underlying engine has defaults.
`estimated_commission` must equal `fixed_commission`, matching the existing
`BacktestConfig` invariant.

Decimal, optional-Decimal and Boolean values use exact canonical transport and
identity semantics. Floats, bool-as-int, random seeds, caller metadata and
economic qualification thresholds are absent.

## 142-A — immutable historical input

Architecture 142-A accepts only an already supplied exact
`HistoricalDataResult` for the exact definition symbol.

It must require:

- exact `HistoricalDataResult`;
- request symbol exactly equals `definition.symbol`;
- exact RAW daily request semantics required by `BacktestConfig`;
- nonempty validated chronological bars;
- no symbol inference from metadata, filenames, universe position or path;
- no market-data acquisition.

The new research path intentionally uses the single-symbol result directly.
It does not accept `MultiSymbolHistoricalDataResult` and does not convert the
portfolio experiment universe into strategy semantics.

A private or narrowly exported canonical single-symbol material helper may be
introduced. Canonical historical material is exactly:

```text
fingerprint version
request symbol
request start
request end
request timeframe
request adjustment
provider_name
for each ordered bar:
  symbol
  timestamp
  canonical open
  canonical high
  canonical low
  canonical close
  exact volume
```

No filesystem path or serialized object bytes participate.

## 142-A — backtest evidence and runner

New module:

`src/trading_bot/experiments/research_strategy_backtest.py`

Schema:

`research-strategy-backtest-evidence/v1`

Identity version:

`research-strategy-backtest-evidence-identity/v1`

UUID5 namespace:

`b7e51d04-4d94-5b1c-b04d-6381c99dce27`

The runner is pure/offline. It may construct exactly:

- one in-memory `HistoricalDataProvider` adapter over the supplied immutable
  `HistoricalDataResult`;
- one pure `NYSEMarketCalendar`;
- one `BacktestConfig` from the exact evaluation policy;
- one `MovingAverageCrossoverStrategy(definition.strategy_config)`;
- one `BacktestEngine`;
- one `PerformanceAnalyzer`.

The adapter must accept only the exact request bound to the supplied data and
return that exact immutable result. It has no filesystem, network, provider or
clock capability.

`backtest_run_id` is deterministic UUID5 over:

```text
run identity version
definition_id
evaluation_policy_id
historical_data_fingerprint
fold_role
```

For standalone 142-A evaluation, `fold_role` is exactly `STANDALONE`.
142-B may reuse the same deterministic function with explicit fold roles.

The immutable evidence fields are exactly:

```text
schema
evidence_id
definition_id
evaluation_policy_id
evaluation_source_head
evaluation_source_tree
historical_data_fingerprint
data_request_symbol
data_request_start
data_request_end
data_request_timeframe
data_request_adjustment
provider_name
backtest_run_id
backtest_result_fingerprint
bar_count
start_timestamp
end_timestamp
total_return
maximum_drawdown_percentage
final_equity
```

The runner returns the evidence plus the exact `BacktestResult` and
`PerformanceReport` as in-memory completed evidence, or provides an explicit
completed-result carrier that keeps those exact objects available for external
verification. It does not serialize every engine object into a second shadow
format.

The result fingerprint must be deterministic UUID5 over a canonical projection
of the complete result audit, including at minimum:

- exact run/config identity and provider name;
- ordered bars and step/session timestamps;
- proposal IDs/symbols/sides/quantities/timestamps;
- risk outcome/reason/resized quantity;
- order IDs/status and ordered order-event identities;
- fill IDs/order IDs/side/quantity/price/commission/timestamp;
- ordered account snapshot cash/equity/exposure;
- final positions and final equity;
- unexecuted final-bar proposal identities;
- start/end timestamps.

No `repr`, Python hash, object identity, pickle/serialized Python bytes,
filesystem path, clock or random UUID may contribute.

An independent verifier must rebuild the exact definition/policy/config/data
fingerprints, rerun the engine and analyzer, require exact
`BacktestResult` / `PerformanceReport` equality, recompute the result
fingerprint and rebuild the evidence exactly.

`from_json()` proves canonical self-consistency only and never runs research
or proves source acceptance.

## 142-B — strategy-native walk-forward

New module:

`src/trading_bot/experiments/research_strategy_walk_forward.py`

This module is frozen by Architecture 142 but is not part of 142-A
implementation.

It owns these schemas/namespaces:

```text
research-strategy-walk-forward-evidence/v1
namespace 18a84b75-90fe-546a-8444-0bb6bfd495dd

research-strategy-walk-forward-qualification-policy/v1
namespace e865a7f0-abad-5352-b2f8-8ff500ebebc9

research-strategy-walk-forward-qualification/v1
namespace 44710283-8780-58d4-b34b-dce20d66447f

research-strategy-walk-forward-passed/v1
namespace f3e48591-0eb4-5c26-a15b-2f8863ada223
```

142-B owns a new pure `ResearchStrategyWalkForwardFold`; it does not reuse the
portfolio-specific `HistoricalExperimentWalkForwardFold`.

The fold contains only deterministic strategy-native interval provenance:

```text
fold_id
training_start
training_end
test_start
test_end
```

Required chronology:

- training_start < training_end;
- training_end == test_start;
- test_start < test_end;
- folds are exact, ordered and non-overlapping under the frozen policy;
- training/test slices are derived from the supplied immutable single-symbol
  historical result;
- no rebalance schedule, metadata or variant selection exists.

Each fold uses exactly the same `definition_id` and evaluation policy. Training
and test runs use deterministic run IDs with explicit fold-role material
containing the fold ID and `TRAINING` / `TEST`.

Walk-forward evidence retains, per fold:

```text
fold_id
training_backtest_evidence_id
test_backtest_evidence_id
training_start
training_end
test_start
test_end
training_historical_fingerprint
test_historical_fingerprint
training_bar_count
test_bar_count
```

There is no rank-one winner, variant selection or configuration change between
folds.

## 142-B — qualification

The qualification policy retains the accepted RCL-2 threshold shape:

```text
minimum_fold_count
minimum_fold_return
minimum_median_return
maximum_fold_drawdown_percentage
require_equal_test_window_bar_count
```

All are mandatory and exact; no weakening defaults.

Qualification is applied only after every fold's exact backtest evidence is
independently verified. It derives PASS/FAIL and ordered failure reasons. A
threshold failure is valid `FAILED` evidence. Malformed provenance, different
definition/config/policy, chronology drift, data mismatch or unverifiable
backtest evidence raises and must never be converted to `FAILED`.

The passed artifact may exist only for exact PASS and remains research evidence.
It grants no SHADOW, paper, production compatibility, approval or execution
authority.

## Explicit separation from old RCL evidence

Architecture 142 creates a **new** strategy-native research chain.

It must not:

- convert an Architecture-139 candidate;
- change an Architecture-139 stage;
- change Architecture-141 status/blockers;
- reuse old `variant_id`, rank, metadata or portfolio metrics as strategy
  semantics;
- claim that the old SHADOW candidate is now compatible;
- construct a compatibility-success artifact.

Architecture 139/141 bytes, identity and meaning remain frozen.

## Allowed imports

142-A definition may import only:

- standard library;
- `Symbol`;
- exact `MovingAverageCrossoverConfig`;
- inert production identity constants
  `PRODUCTION_STRATEGY_SCHEMA`, `MOVING_AVERAGE_STRATEGY_ID`,
  `MOVING_AVERAGE_STRATEGY_VERSION`;
- exact `RiskLimits` for the evaluation policy.

142-A backtest runner may additionally import only the pure components required
for:

- `HistoricalDataResult` / `HistoricalDataRequest`;
- `BacktestConfig`, `BacktestResult`, `BacktestEngine`;
- `MovingAverageCrossoverStrategy`;
- `NYSEMarketCalendar`;
- `PerformanceAnalyzer` / `PerformanceReport`;
- domain audit model types needed only for canonical result fingerprinting.

142-B may import 142-A evidence plus standard-library/Decimal utilities needed
for fold/qualification computation.

## Prohibited capabilities

Static/source tests must reject imports or capability paths for:

```text
ProductionStrategyContract
build_production_strategy
HistoricalExperimentRunner
HistoricalExperimentWalkForwardRunner
OptimizedPaperPortfolioSimulator
MultiSymbolBacktestEngine
review_paper
runtime
Robinhood
Alpaca/provider clients
credential APIs
broker/execution adapters
filesystem I/O
socket/network
subprocess
scheduler
ACL/native host mutation
production stores/SQLite
GUI
current clock acquisition
UUID4/randomness
```

The existing pure backtest engine's internal `OrderEngine`, `PaperLedger`
and `RiskManager` use is allowed because those are deterministic in-memory
backtest components, not broker/paper-runtime effects.

## Effect boundary

Offline deterministic computation over caller-supplied immutable data is
permitted. It is not an external/provider/paper/broker effect.

Operational effects remain exactly zero:

```text
PRODUCTION_SQLITE_READS=0
PRODUCTION_SQLITE_WRITES=0
CREDENTIAL_READS=0
EXTERNAL_PROVIDER_CALLS=0
ROBINHOOD_READS=0
BROKER_CALLS=0
SCHEDULER_CALLS=0
ACL_MUTATIONS=0
PAPER_RUNTIME_MUTATIONS=0
PRODUCTION_CONTRACTS_CREATED=0
STRATEGY_PROMOTIONS=0
PAPER_CANDIDATES_CREATED=0
D1_OPERATIONS=0
D1R5_OPERATIONS=0
D1R7_OPERATIONS=0
D1R8_OPERATIONS=0
D1R9_OPERATIONS=0
D2_SUPERVISOR_EXECUTIONS=0
LIVE_EFFECTS=0
```

## Canonical transport and verification

Every new artifact uses:

- compact sorted JSON with no trailing newline;
- exact field set;
- duplicate/missing/unknown field rejection;
- exact canonical UUID/source/Decimal/timestamp/enum/Boolean transport;
- length-framed UTF-8 UUID5 semantic identity;
- no bool-as-int;
- no non-finite Decimal;
- no floats;
- no ambient environment/path/current-time/object-identity dependence.

Parsing proves self-consistency only. External verification defensively validates
or copies caller inputs, recomputes the entire evidence chain and requires exact
equality. There is no persisted `verified` flag.

## 142-A expected implementation surface

Expected new paths:

- `src/trading_bot/experiments/research_strategy_definition.py`;
- `src/trading_bot/experiments/research_strategy_backtest.py`;
- `tests/experiments/test_research_strategy_definition.py`;
- `tests/experiments/test_research_strategy_backtest.py`.

Expected additive/current updates only when mechanically required:

- `src/trading_bot/experiments/__init__.py`;
- optionally `src/trading_bot/market_data/fingerprints.py` and its exports/tests
  if a reusable single-symbol canonical material helper is chosen;
- `scripts/run_test_certification.py`;
- `scripts/checkpoint_runner.py`;
- current inventory/source-pin assertions directly affected by the two new tests;
- Architecture-142 validation record.

Do not modify production strategy semantics, BacktestEngine semantics,
Architecture-139/141 domain behavior, D1R9 source, workflow YAML or protected
runtime code.

## 142-A required tests

At minimum prove:

1. exact definition and policy construction;
2. canonical JSON and deterministic UUID5 identities;
3. every semantic field changes identity where type-valid;
4. strict UUID/source/Decimal/Boolean/type handling;
5. fixed production family/version cannot be caller-selected;
6. no rank/name/metadata/compatibility/stage fields exist;
7. symbol must exactly match supplied historical data;
8. no multi-symbol conversion/inference path exists;
9. all BacktestConfig/RiskLimits semantics are bound with no hidden defaults;
10. estimated commission equals fixed commission;
11. deterministic historical fingerprint;
12. deterministic run ID;
13. direct equivalence with independently constructed `BacktestEngine` using
    the same strategy/config/data/calendar;
14. next-open behavior and no look-ahead remain inherited unchanged;
15. deterministic complete-result fingerprint;
16. exact external verifier rerun/reconciliation;
17. parser does not execute research;
18. Decimal-context/object-identity/path/environment independence;
19. caller inputs remain unchanged on success/failure;
20. no ProductionStrategyContract/production builder;
21. no old HistoricalExperiment runner/walk-forward/simulator;
22. no filesystem/network/provider client/credential/paper/scheduler/broker/D1R9
    capability;
23. Architecture-139/141 tests remain unchanged in meaning;
24. Architecture 142 remains outside ACTIVE production checkpoints;
25. actual final inventory and successor overlays are recomputed, never guessed.

## Publication discipline

142-A implementation must be fully composed before publication. Use exact
staging only; never `git add .` or `git add -A`.

Run focused 142-A tests, directly affected pure backtest/strategy/market-data
tests, retained Architecture-139/141 tests needed to prove separation, affected
authority/checkpoint-runner tests, Ruff and diff checks.

Do not run duplicate broad FULL/ROBINHOOD locally when GitHub CI owns them.

One atomic implementation commit/push produces one planned CI admission run.
If it fails, preserve the failed attempt. Codex remains in the delegated task
for fully classified bounded mechanical C1/C2 corrections under the canonical
workflow rule; do not rerun unchanged CI or rewrite failed evidence.

After terminal green, stop for ChatGPT exact-source review before 142-B.

## Next reviewed boundaries

After 142-A source acceptance:

1. implement 142-B strategy-native walk-forward evidence/qualification;
2. exact-source review and acceptance;
3. Architecture 143 / RCL-6 separately defines a positive compatibility proof
   consuming only the new strategy-native definition plus verified 142-B
   evidence and accepted production strategy semantics;
4. Architecture 143 still must not construct `ProductionStrategyContract` or
   `PAPER_CANDIDATE`;
5. a later separately reviewed boundary may define `PAPER_CANDIDATE`;
6. human promotion remains later and explicit.

Real-money trading remains **NO-GO**.
