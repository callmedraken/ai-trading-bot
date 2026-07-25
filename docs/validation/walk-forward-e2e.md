# Schema-2 walk-forward end-to-end validation

`tests/integration/test_walk_forward_e2e.py` executes the real offline
walk-forward command against the small local fixture in
`tests/fixtures/market_data/walk-forward-e2e/`. The strict schema-2
configuration supplies two explicit candidates, two chronological folds, an
explicit training ranking policy, and an explicit aggregate distribution
policy.

The validation writes all outputs below pytest's temporary directory. It
compares repeated JSON and CSV bytes, confirms aggregate flags do not change
the upstream walk-forward artifacts, and reconciles aggregate observations,
exact rational means, source result identities, and selected-variant
frequencies to the walk-forward audit.

The aggregate checks also reject fields that would imply totals, compounding,
a continuous equity curve, annualization, ranking, scoring, or recommendations.
The fixtures use no network access, clock, randomness, external market data, or
generated report files.
