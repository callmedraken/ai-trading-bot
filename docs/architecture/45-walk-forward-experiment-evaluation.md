## 1. Files

Create:

- `src/trading_bot/experiments/walk_forward.py`
- `tests/experiments/test_walk_forward.py`
- `docs/architecture/45-walk-forward-experiment-evaluation.md`

Update narrowly:

- `src/trading_bot/experiments/exceptions.py`
- `src/trading_bot/experiments/__init__.py`

No CLI, serializers, providers, runners outside `experiments`, or existing domain behavior should change.

## 2. Public API and immutable models

Recommended API:

```python
@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardFold:
    fold_id: UUID
    training_start: datetime
    training_end: datetime
    test_start: datetime
    test_end: datetime
    training_rebalance_timestamps: tuple[datetime, ...]
    test_rebalance_timestamps: tuple[datetime, ...]
    metadata: tuple[MetadataEntry, ...] = ()


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardSelectionPolicy:
    policy_id: UUID
    ranking_policy: HistoricalExperimentRankingPolicy
    metadata: tuple[MetadataEntry, ...] = ()


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardRequest:
    request_id: UUID
    historical_data: MultiSymbolHistoricalDataResult
    folds: tuple[HistoricalExperimentWalkForwardFold, ...]
    initial_state: HistoricalExperimentInitialState
    variants: tuple[HistoricalExperimentVariant, ...]
    selection_policy: HistoricalExperimentWalkForwardSelectionPolicy
    metadata: tuple[MetadataEntry, ...] = ()


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardSelection:
    training_report_id: UUID
    training_experiment_result_id: UUID
    training_comparison_result_id: UUID
    ranking_policy_id: UUID
    selected_rank: int
    selected_caller_ordinal: int
    selected_variant_id: UUID
    selected_training_run_id: UUID


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardFoldResult:
    ordinal: int
    fold: HistoricalExperimentWalkForwardFold
    training_request_id: UUID
    training_historical_fingerprint: UUID
    training_report: HistoricalExperimentReport
    selection: HistoricalExperimentWalkForwardSelection
    test_request_id: UUID
    test_historical_fingerprint: UUID
    test_report: HistoricalExperimentReport
    test_run_id: UUID
    test_rolling_result_id: UUID


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardResult:
    result_id: UUID
    request_id: UUID
    source_historical_fingerprint: UUID
    selection_policy: HistoricalExperimentWalkForwardSelectionPolicy
    folds: tuple[HistoricalExperimentWalkForwardFoldResult, ...]
    metadata: tuple[MetadataEntry, ...] = ()


class HistoricalExperimentWalkForwardRunner:
    def __init__(
        self,
        simulator_factory: HistoricalExperimentSimulatorFactory,
    ) -> None:
        ...

    def run(
        self,
        request: HistoricalExperimentWalkForwardRequest,
    ) -> HistoricalExperimentWalkForwardResult:
        ...
```

The result should not retain the source historical result, full training/test experiment results, simulator factory, or mutable services.

## 3. Fold specification and validation

Version one should accept only explicit, prebuilt folds. Do not introduce a schedule factory.

All datetimes must be timezone-aware and normalized to UTC. Intervals use `[start, end)`.

Per fold require:

```text
training_start < training_end
training_end == test_start
test_start < test_end
```

Requiring adjacency reflects “the immediately following test fold” and prevents an ambiguous unaccounted interval.

Schedules must be:

- Nonempty
- UTC-aware and normalized
- Strictly increasing
- Unique
- Entirely inside their corresponding interval
- Exact timestamps present in the sliced historical result

Fold IDs and metadata keys must be unique. Reserve the prefix:

```text
historical_experiment_walk_forward_
```

Across folds require:

- Caller order already chronological
- Strictly increasing `training_end`
- Strictly increasing `test_start` and `test_end`
- Disjoint test intervals:

```text
previous.test_end <= current.test_start
```

Training windows may overlap. Require `training_start` to be nondecreasing:

- Equal starts express anchored training.
- Increasing starts express rolling training.
- A mixture is valid when explicitly authored.

A later training interval may contain an earlier fold’s test data. That is valid walk-forward behavior because those observations are historical by the later selection time. It may never contain its own or a future test interval.

## 4. Training-selection contract

Version one should use the existing deterministic ranking policy through an explicit wrapper:

```python
HistoricalExperimentWalkForwardSelectionPolicy(
    policy_id=...,
    ranking_policy=...,
    metadata=...,
)
```

Its sole version-one rule is:

```text
Select the exact training run assigned rank 1 by the embedded ranking policy.
```

The wrapper is valuable because it makes “rank 1 is used for selection” an explicit walk-forward policy rather than silently changing the meaning of the general ranking layer. Do not add a one-member selection-rule enum.

Validation requires:

- Exact UUID
- Exact `HistoricalExperimentRankingPolicy`
- Ordered, unique metadata
- No reserved metadata keys

The ranking comparator remains unchanged. Ranking directions, criteria order, and tie-breaker remain entirely explicit.

## 5. Exact train/test isolation rules

For each fold, construct two independent historical results through existing public market-data models:

```text
training slice = source frames in [training_start, training_end)
test slice     = source frames in [test_start, test_end)
```

Rules:

- Preserve exact source frame and bar objects.
- Never sort, fill, interpolate, synthesize, or reinterpret timestamps.
- Never prepend training frames to the test slice.
- Never use test frames for training scenario warm-up.
- Never derive selection inputs from the test slice.
- Build the test experiment request only after training ranking has selected the variant.

The consequence is deliberate: the first test rebalance must have sufficient observation history entirely inside the test interval. If the selected variant needs four observations, the test slice must contain four test observations by that rebalance. Training observations cannot satisfy that requirement.

Before any experiment executes, prevalidate:

- Every training slice against every candidate variant’s observation requirements.
- Every test slice against every candidate variant’s observation requirements.

Validating every candidate test requirement is conservative but ensures insufficient data is discovered before selection or partial fold execution. It also avoids selection-dependent validation timing.

## 6. Execution flow

The runner should:

1. Validate the complete request and all fold relationships.
2. Capture source, fold, variant, initial-state, and policy invariants.
3. Slice and validate every training and test interval.
4. Validate every schedule and candidate observation requirement.
5. Derive deterministic training and test request IDs.
6. For each fold in caller order:
   1. Create one training experiment request with all candidate variants.
   2. Run one `HistoricalExperimentRunner`.
   3. Run one `HistoricalExperimentComparator` with the embedded ranking policy.
   4. Build one ranked training `HistoricalExperimentReport`.
   5. Select the exact rank-one source run.
   6. Create one test experiment request containing only that exact variant object.
   7. Run one test `HistoricalExperimentRunner`.
   8. Build one unranked single-row test report.
   9. Build selection certification and the immutable fold result.
7. Reconcile all folds and source invariants.
8. Compute the aggregate UUID.
9. Construct the aggregate result last.

No retry, partial aggregate, mutation, concurrency, or fallback selection is allowed.

Each training and test experiment begins from the same request-level immutable initial-state specification. Test folds are independent out-of-sample evaluations, not a continuous portfolio simulation.

## 7. Result provenance

Retaining compact reports rather than full experiment results is the appropriate boundary.

The training report supplies:

- Training experiment request/result IDs
- Training historical fingerprint
- All candidate variant IDs and run IDs
- Exact metrics
- Ranking policy fingerprint and ID
- Ranking comparison ID
- Rank and comparison values

The selection record explicitly links:

```text
training report
→ training comparison
→ rank-one caller ordinal
→ selected training run
→ selected variant
```

The test report supplies:

- Test experiment request/result IDs
- Test historical fingerprint
- The single selected variant ID
- Exact out-of-sample metrics
- Test experiment run ID
- Test rolling result ID

The fold result therefore proves:

```text
which training evidence selected the variant
→ which exact variant was selected
→ which independent test execution evaluated it
```

Do not retain variant names separately; they already exist in compact report rows and do not establish identity.

## 8. Deterministic identity

Use a private namespace and:

```text
historical-experiment-walk-forward-v1
```

Use caller-provided request, fold, and policy UUIDs. Derive child request IDs with UUID5 from:

- Version and stage marker
- Walk-forward request ID
- Fold ordinal and fold ID
- Exact training or test bounds
- Ordered schedule
- Source historical fingerprint
- Selection-policy ID
- For test requests, selected training run ID and selected variant ID

Aggregate result identity should include:

- Request ID
- Source historical fingerprint
- Selection-policy ID
- Embedded ranking policy identity and canonical fingerprint
- Ordered walk-forward metadata
- Every ordered fold specification
- Every training report ID
- Every selection record field
- Every test report ID
- Training and test historical fingerprints
- Test run and rolling-result IDs

Use explicit markers:

```text
DATETIME|
DECIMAL|
INTEGER|
BOOLEAN|
ENUM|
UUID|
STRING|
```

Datetime material uses normalized UTC ISO-8601 text. Decimal material uses a private sufficient local context and `canonical_decimal`.

Do not use clocks, UUID4, paths, artifact bytes, object identity, Python hashes, locale, or mutable service identities.

## 9. Validation and exception hierarchy

Add:

- `HistoricalExperimentWalkForwardError`
- `InvalidHistoricalExperimentWalkForwardRequestError`
- `HistoricalExperimentWalkForwardFoldError`
- `HistoricalExperimentWalkForwardDataError`
- `HistoricalExperimentWalkForwardSelectionError`
- `HistoricalExperimentWalkForwardExecutionError`
- `HistoricalExperimentWalkForwardReconciliationError`
- `InconsistentHistoricalExperimentWalkForwardResultError`

`HistoricalExperimentWalkForwardFoldError` should retain:

- Fold ordinal
- Fold ID
- Stage
- Narrow known cause, when applicable

Suggested stages:

```text
TRAINING_EXPERIMENT
TRAINING_RANKING
TRAINING_REPORT
SELECTION
TEST_EXPERIMENT
TEST_REPORT
```

Do not catch broad `Exception`.

Missing data, insufficient observations, schedule mismatches, and downstream failures are fatal. No fold is skipped, marked incomplete, or silently shortened.

## 10. Reconciliation and no-look-ahead guarantees

Reconciliation must verify:

- Complete ordered fold coverage
- Exact explicit fold objects retained
- Sequential fold-result ordinals
- Unique fold and child request IDs
- Training/test bounds and slice fingerprints differ as required
- No shared frames between a fold’s training and test slices
- Test intervals remain disjoint and caller ordered
- Training report source matches the training child request
- Ranking comparison covers exactly the training candidates
- Selected rank is exactly 1
- Selected run and variant are exact members of the training report
- Selected variant object is the exact object inserted into the test request
- Test request contains exactly one variant
- Test report contains exactly one row
- Test row variant UUID equals the selected training variant UUID
- Test run and rolling IDs equal the test report row
- No test report/range/fingerprint participates in training selection identity or construction
- Source data, folds, variants, initial state, and policy remain unchanged
- Aggregate UUID is canonical

Object identity may be used transiently to certify the exact variant handoff, as existing compact-report linkage does. It must not enter any retained model or UUID.

## 11. Relationship boundaries

The new layer may depend on public contracts from:

- `trading_bot.market_data`
- `trading_bot.experiments.historical`
- `trading_bot.experiments.comparison`
- `trading_bot.experiments.report`
- `trading_bot.portfolio.MetadataEntry`

It should orchestrate:

- `HistoricalExperimentRunner`
- `HistoricalExperimentComparator`
- `HistoricalExperimentReportBuilder`

It must not depend on:

- Pairwise or Pareto analysis
- CLI or serializers
- Providers or files
- Rolling internals
- Optimization or scenario internals
- Ledger, execution, runtime, or risk internals
- Brokers or networks
- Schedulers, persistence, concurrency, GPU, or AI

The supplied simulator factory remains the existing trust boundary. The walk-forward layer must not construct brokers, engines, ledgers, or simulators directly.

## 12. Focused test plan

Cover:

- Explicit fold and request validation
- UTC normalization and naive datetime rejection
- Adjacency and `[start, end)` behavior
- Nonempty, ordered schedules
- Anchored, rolling, and overlapping training windows
- Disjoint chronological test windows
- Duplicate fold IDs and metadata restrictions
- Empty/duplicate variants
- Exact ranking policy reuse
- Training runner called once per fold
- Comparator called once per fold
- Training report built once per fold
- Test runner called once per fold
- Test report built once per fold
- Rank-one selection under ascending and descending criteria
- Deterministic tie-break behavior
- Exact selected variant object passed to test
- Test request contains one variant
- No training frame in the test slice
- No test frame in the training slice
- Test warm-up uses test observations only
- Insufficient training data
- Insufficient test data
- Missing schedule timestamps
- Fail-fast behavior before execution for invalid slices
- Downstream failure at every stage
- No retries and no later-fold execution after failure
- Compact provenance linkage
- Independent common initial state for every child experiment
- Repeated deterministic result
- Identity sensitivity to folds, schedules, ranking policy, variants, selection, and test result
- Decimal-context independence
- Defensive tuple copying and input immutability
- Malformed retained fold/result relationships
- No full experiment or rolling trees retained
- No pairwise, Pareto, CLI, provider, network, broker, persistence, concurrency, GPU, or AI dependency

Use small deterministic local historical fixtures and lightweight existing simulator factories. Do not mock financial calculations when existing deterministic components can execute them.

## 13. Documentation

Create:

```text
docs/architecture/45-walk-forward-experiment-evaluation.md
```

Document:

- Domain responsibility and package placement
- Explicit prebuilt folds
- Anchored and rolling training expressed through bounds
- Adjacent train/test semantics
- Test-window disjointness
- Permitted overlap with earlier historical test periods
- Existing ranking policy as explicit training selection
- Exact rank-one rule
- Test-only historical slicing and warm-up
- Independent fold initial states
- Compact training/test provenance
- Exact selected-variant linkage
- UUID5 hierarchy
- All-or-nothing, fail-fast behavior
- No aggregate out-of-sample metrics
- Audit-not-checkpoint status
- Deferred fold generation, CLI, serialization, continuous capital, aggregate analytics, statistics, Pareto selection, optimization, and tuning

## 14. Risks and unresolved decisions

Resolved for version one:

- Folds are explicitly authored.
- No fold-generation factory is added.
- Both anchored and rolling windows are representable through explicit bounds.
- Training selection uses one explicit existing ranking policy.
- Rank one is the sole explicit selection rule.
- The exact selected training variant object is reused in the test request.
- Stable IDs certify the retained linkage.
- Fold results retain compact reports, not full experiment trees.
- Invalid or insufficient folds fail the complete run.
- Training windows may overlap.
- Test windows must remain disjoint and chronological.
- No aggregate out-of-sample metric is reported.

One important limitation remains: independent test folds do not form a continuous investable equity curve. Their returns, P&L, drawdowns, and costs must not be summed, compounded, averaged, or ranked by this layer. A future aggregate analytics milestone must first define capital continuity, weighting, overlapping exposure, and metric-composition semantics explicitly.