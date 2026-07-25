# Walk-forward stability CLI and exports

## Command and configuration

The existing `scripts.run_walk_forward_experiment` command owns optional
stability analysis. Configuration schemas 1 and 2 are unchanged. Strict schema
3 adds two required root members: nullable `aggregate_policy` and non-null
`stability_policy`.

The stability policy contains an exact UUID, a nonempty ordered metric-policy
array, and ordered metadata. Each metric policy contains an exact metric,
operation array, and comparability rule. Configuration parsing is structural;
domain policy models remain authoritative for eligibility, comparability, and
canonical operation ordering.

Schema 3 runs stability analysis even without an output destination. A null
aggregate policy disables aggregate analysis. A non-null aggregate policy uses
the existing aggregate configuration shape and behavior.

The additive destinations are:

```text
--stability-json PATH
--stability-json-pretty
--stability-csv PATH
```

Pretty formatting requires a stability JSON destination.

## Execution and immutable handoff

All six destinations are normalized, collision checked, and preflighted before
configuration parsing. Destination compatibility is checked after parsing and
before historical loading.

The command loads history once and invokes the walk-forward runner exactly
once. Schema 3 invokes the aggregate analyzer zero or one time according to the
nullable policy, then invokes the stability analyzer exactly once. The
stability analyzer receives the exact immutable walk-forward result and the
optional exact immutable aggregate result from that execution.

Stability serializers accept only the exact immutable stability result. They do
not inspect upstream results or invoke providers, runners, comparison, report
construction, aggregation, or stability analysis.

## Terminal interpretation

Schema-1 and schema-2 summaries are unchanged. Schema 3 appends ordered
selection observations, consecutive runs, directional transitions including
self-transitions, first-appearance frequencies, and policy-ordered metric
evidence.

The summary states that folds are independent simulations and that the evidence
describes the retained fold order only. It defines no continuous capital,
compounding, annualization, combination across capital paths, or causal
interpretation.

## JSON schema 1

Stability JSON contains numeric `schema_version` 1 and one
`walk_forward_stability_result` object. It retains source and optional aggregate
identities, the complete explicit policy, fold count, selection evidence, and
metric evidence.

Decimals use canonical strings, integers and booleans retain JSON types, UUIDs
use canonical text, rational values use reduced integer numerator and
denominator objects, and timedeltas use exact integer microseconds. Disabled
statistics use null. Object keys are sorted and output ends in one newline.

## CSV schema

Stability CSV uses one fixed header with a `record_type` discriminator. Record
order is selection observations, runs, transitions, transition frequencies,
variant frequencies, then for each policy-ordered metric its fold observations,
adjacent changes, and summary.

Directional pairs remain ordered and self-transitions remain present.
First-appearance order is retained. Fields irrelevant to a record type are
blank. Exact scalar types are explicit. CSV uses UTF-8, comma delimiter,
`QUOTE_MINIMAL`, `\n` line endings, and one final newline.

## Artifact independence and coordinated output

Existing walk-forward and aggregate serializers are unchanged. Stability output
paths, formatting, overwrite state, and quiet mode do not enter any domain
identity. Requesting stability artifacts cannot change upstream artifact bytes
or identities.

All requested artifacts are serialized before staging. Replacement order is
walk-forward JSON, walk-forward CSV, aggregate JSON, aggregate CSV, stability
JSON, then stability CSV. Replacement remains individually atomic rather than
transactional. Later failure does not roll back an earlier successful
replacement.

## Errors

Existing exit-code mappings remain unchanged: configuration and destination
compatibility failures use 4, domain execution or analysis failures use 6, and
serialization or output failures use 7. Expected failures are fail-fast and
never retry or rerun domain work.
