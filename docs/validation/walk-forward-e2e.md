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

Schema-3 coverage extends the same temporary-directory workflow through the
stability analyzer and stability JSON/CSV projections. It verifies exact source
identity handoff, optional aggregate provenance, retained fold ordering,
directional transitions including self-transitions, first-appearance
frequencies, exact timedelta microseconds, Decimal and integer scalar types,
rational persistence, range, median, median absolute deviation, and direct
nonzero sign changes. Existing walk-forward and aggregate artifact bytes remain
independent of stability destinations.

The schema-3 validation also requests a research-session manifest from the real
command. It reconciles the manifest's family result IDs to the three immutable
JSON results and verifies canonical artifact order, relative paths,
serializer-contract schema versions, exact byte lengths, and SHA-256 hashes for
all six primary artifact bytes. Repeated runs produce identical primary and
manifest bytes, and every generated file remains below pytest's temporary
directory.

Separate retained-manifest reconstruction and read-only artifact verification
are covered by `docs/validation/walk-forward-manifest-verification.md`. That
offline command does not rerun or reinterpret any part of this financial
workflow.

Copy-only relocation of the verified session into a fixed portable directory
layout is covered by `docs/validation/walk-forward-research-bundle.md`. Bundle
validation retains every primary artifact byte and the manifest identity.
