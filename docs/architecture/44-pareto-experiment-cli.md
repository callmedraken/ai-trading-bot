# Pareto historical experiment CLI

Pareto analysis is an optional derived audit over the single compact report
built by the historical experiment command. Its strict schema-1 policy remains
separate from unchanged schema-3 experiment configuration.

The command supports `--pareto-policy`, `--pareto-json`,
`--pareto-json-pretty`, and `--pareto-csv`, including policy-only mode. One
compact report is shared exactly with compact serializers, pairwise comparison,
and the single Pareto analyzer call.

JSON schema 1 retains only Pareto policy, frontier, variant summaries, and
dominance evidence. The unified 21-column CSV emits caller-ordered `VARIANT`
rows followed by record/objective-ordered `DOMINANCE` rows. Repeated canonical
`policy_objectives`, frontier, and metadata columns keep zero-dominance results
self-describing.

All seven destinations share normalized collision checks, overwrite policy,
and the existing coordinated staging writer. Serialization completes before
staging; replacements are individually atomic in full, compact, pairwise, then
Pareto order. The sequence is not an aggregate filesystem transaction.

Policy/read errors retain exits 3 and 4; domain analysis uses exit 6; output
failures use exit 7. Artifacts are audits, not checkpoints. Existing artifact
bytes and upstream identities remain independent of Pareto policy.

The layer infers no winner or recommendation and performs no scoring,
normalization, epsilon dominance, constraints, hypervolume, crowding distance,
statistics, charts, tuning, execution, networking, persistence, concurrency,
GPU, or AI work.
