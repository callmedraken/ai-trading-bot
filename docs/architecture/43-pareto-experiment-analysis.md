# Deterministic Pareto historical experiment analysis

## Responsibility

Pareto analysis belongs in `trading_bot.experiments`. It is a pure descriptive
projection of one completed immutable `HistoricalExperimentReport` under one
explicit immutable policy. The compact report is its sole input.

The layer reuses `HistoricalExperimentRankingMetric` and
`HistoricalExperimentRankingDirection` only as the explicit vocabulary for all
26 scalar experiment metrics. It does not invoke ranking, pairwise comparison,
grid generation, experiment execution, or report construction.

## Dominance

A variant dominates another only when it is no worse on every objective and
strictly better on at least one. Lower is better for `ASCENDING`; higher is
better for `DESCENDING`. Values are compared directly as exact same-type
`Decimal` or integer scalars. There is no tolerance, float conversion,
normalization, weighting, score, or tie-breaker.

Equal objective vectors and incomparable variants do not dominate each other.
Duplicate vectors remain distinct frontier members. One-objective policies and
one-variant reports are valid.

Every unordered caller-order pair is evaluated once. Emitted dominance records
remain in source-pair order even when the right member dominates the left.
Frontier members, variant summaries, and relationship UUIDs remain in source
caller order.

## Audit evidence and identity

Each dominance record retains the exact values and strict-better flag for every
policy objective, including equal objectives. Results retain only the source
report UUID, policy, caller-order frontier UUIDs, variant relationship
summaries, and dominance evidence. They do not retain names, metric models,
ranks, grids, or nested execution trees.

Result UUIDs use UUID5, version `historical-experiment-pareto-v1`, ordered
typed material, and context-independent Decimal canonicalization. Identity
material has explicit Decimal, integer, Boolean, enum, UUID, and string
markers. It excludes clocks, paths, object identity, Python hashes, and source
report bytes.

Analysis is all-or-nothing: local pair coverage, evidence, relationships,
frontier, and source invariants reconcile before the aggregate immutable result
is constructed. There is no mutation, partial result, retry, filesystem,
network, broker, scheduler, persistence, concurrency, GPU, or AI behavior.

## Deferred work

JSON/CSV CLI integration is a separate future milestone. Epsilon dominance,
constrained Pareto sets, hypervolume, crowding distance, visualization,
statistics, confidence analysis, selection, recommendations, execution
pruning, and parameter tuning are deliberately deferred.
