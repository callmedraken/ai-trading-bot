# Walk-forward aggregate CLI and exports

## Command and configuration

The existing offline `scripts.run_walk_forward_experiment` command owns optional
aggregate distribution analysis. Its existing `--json` and `--csv` artifacts
remain unchanged. Separate `--aggregate-json` and `--aggregate-csv` destinations
export aggregate schema 1; `--aggregate-json-pretty` affects only aggregate JSON.

Walk-forward configuration schema 1 is unchanged and defines no aggregate
analysis. Strict schema 2 adds one required `aggregate_policy` containing a
canonical UUID, a nonempty caller-ordered metric-policy array, and ordered
metadata. Every metric policy names an exact public aggregate metric and an
operation array. Empty operation arrays retain observations without derived
statistics. Domain models remain authoritative for eligibility and canonical
operation order.

## Execution and immutable boundaries

All destinations are normalized, collision checked, and preflighted before
configuration parsing. Aggregate destinations with schema 1 fail before
historical loading. The command loads history once and invokes the walk-forward
runner exactly once. Every successful schema-2 run invokes the aggregate
analyzer exactly once, including summary-only and quiet runs, using the exact
immutable walk-forward result returned by that runner.

Existing serializers consume only the immutable walk-forward result. Aggregate
serializers consume only the immutable aggregate result. Serialization is a
projection: it does not run or reproduce providers, experiments, comparisons,
report building, aggregate analysis, or statistics.

## Aggregate JSON and CSV

Aggregate JSON schema 1 retains source and aggregate identities, the complete
explicit policy, fold counts, caller-ordered fold summaries, policy-ordered
metric summaries, exact observations and statistics, and first-selection-order
variant frequencies. Decimal observations are canonical strings; integers
remain integers. Equal-fold arithmetic means are reduced integer numerator and
positive denominator objects and have no approximate representation.

Aggregate CSV is fold-major and policy-metric-minor long form. Each row retains
fold and test provenance, selected variant provenance, scalar type, exact
observation, enabled summary fields, rational numerator and denominator, sign
counts, and immutable selection frequencies. Disabled statistics use blank
cells. It has no totals row.

## Interpretation and output

Terminal output prominently states that folds are independent simulations and
that statistics describe a distribution, not a continuous portfolio or equity
curve. Selection frequencies imply no quality ordering.

Every requested artifact is fully serialized before staging. Replacement order
is existing JSON, existing CSV, aggregate JSON, then aggregate CSV. Replacement
remains individually atomic rather than transactional. Paths, formatting,
overwrite, quiet mode, and output choices do not enter domain identity.

Generated artifacts belong under ignored report paths. Continuous capital,
compounding, annualization, totals, weighting, scoring, ranking,
recommendations, optimization, search, and tuning remain outside this command.
