# Walk-forward historical experiment evaluation

## Responsibility and boundary

`trading_bot.experiments.walk_forward` performs deterministic, out-of-sample
evaluation over explicit caller-authored folds. It orchestrates the existing
historical experiment runner, explicit ranking comparator, and compact report
builder. It does not generate folds, calculate aggregate statistics, tune
parameters, or select a policy direction.

The layer performs no CLI, serialization, provider, filesystem, brokerage,
network, persistence, concurrency, GPU, or AI work. Its output is an immutable
audit, not a restart checkpoint.

## Explicit folds

Each fold contains explicit adjacent half-open intervals:

```text
[training_start, training_end)
[test_start, test_end)
training_end == test_start
```

Training and test schedules are nonempty, strictly increasing UTC timestamps
inside their corresponding intervals and present in the source data. Folds
remain in caller order. Training starts are nondecreasing, training ends and
test bounds are strictly increasing, and test intervals are disjoint.

Equal training starts express anchored training; increasing starts express
rolling training. Training windows may overlap and a later training window may
include observations from an earlier test period. A training window can never
include its own test period.

## Train/test isolation

Every interval is sliced into a new public
`MultiSymbolHistoricalDataResult` while retaining the exact source frame and
bar objects. Slicing never sorts, fills, interpolates, or synthesizes data.
Training frames are never prepended to the test slice.

Before any experiment executes, every training and test slice is validated
against every candidate variant's observation count and schedule. Thus a test
rebalance must have sufficient history entirely within its own test interval.
Missing timestamps or insufficient observations fail the whole request before
partial execution.

## Training selection and test execution

The explicit walk-forward selection policy embeds one existing
`HistoricalExperimentRankingPolicy`. Each fold runs all candidates on training
data, applies that exact policy, and selects the exact source run assigned rank
one. Ranking directions, criterion order, and tie-breaking remain explicit;
the general ranking layer retains its descriptive meaning.

The exact selected variant object is inserted into a new single-variant test
request only after training ranking completes. Each training and test
experiment begins from the request's same immutable initial-state
specification. Test folds are independent simulations, not a continuous
portfolio.

## Compact provenance

Each fold result retains a ranked compact training report, a selection
certificate, and an unranked one-row test report. The certificate links the
training report and comparison to the rank-one caller ordinal, training run,
and variant. The test provenance links that variant to its independent test
run and rolling result.

Full experiment results, rolling trees, the source historical result,
simulator factories, and mutable services are not retained.

## Deterministic identity

UUID5 identities use the private version
`historical-experiment-walk-forward-v1`. Caller UUIDs identify the request,
folds, and selection policy. Derived child request UUIDs bind the stage, parent
request, fold ordinal and UUID, exact bounds and schedule, source historical
fingerprint, and selection policy. Test request identity additionally binds the
selected training run and variant.

The aggregate result UUID binds the request and source fingerprint, embedded
ranking policy, ordered metadata, complete ordered fold specifications,
training and test report UUIDs, selection certificates, slice fingerprints,
and test run and rolling-result UUIDs. Typed canonical material excludes
clocks, UUID4, paths, serialized artifacts, Python hashes, locale, object
identity, and mutable services.

## Failure and reconciliation

Execution is sequential, fail-fast, all-or-nothing, and has no retry or
fallback selection. Fold failures retain the fold ordinal, fold UUID, stage,
and narrow known cause. Reconciliation verifies ordered coverage, unique child
requests, exact report linkage, rank-one selection, exact selected-variant
handoff, one-row unranked test output, immutable inputs, and canonical aggregate
identity.

No aggregate out-of-sample metric is produced. Independent fold returns, P&L,
drawdowns, and costs must not be summed, compounded, averaged, or ranked by this
layer because the folds do not define continuous capital.

## Deferred work

Deferred work includes fold generation, CLI and serialization, continuous
capital, aggregate analytics and statistics, Pareto-based selection,
optimization, parameter search, and tuning.
