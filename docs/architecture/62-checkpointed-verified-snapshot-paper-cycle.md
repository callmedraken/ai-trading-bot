# Checkpointed verified-snapshot paper-cycle execution

## Boundary

Milestone 2C coordinates one in-memory paper cycle from a complete `PASS`
paper-account checkpoint verification and a complete `PASS` daily-snapshot
verification. The caller supplies explicit cycle intent but cannot supply
account state. The coordinator restores the checkpoint through the public exact
compact-ledger API, derives preparation account input, calls the existing
verified-snapshot preparation boundary, and invokes `PaperPortfolioRuntime`
exactly once with a fresh empty `OrderEngine`.

The boundary does not create or serialize a successor checkpoint, verify a
lineage edge or full lineage, add a CLI, stage or finalize files, contact a
provider or broker, schedule work, select strategies, optimize targets, retry,
or add execution policy.

## Request and coordinator metadata

`CheckpointedVerifiedSnapshotPaperCycleRequest` deliberately omits account
state. It retains the caller request UUID, snapshot reference, exact quantity
target and target cash, caller-asserted next-session open references, policies,
planning/submission/fill timestamps, and ordered metadata. Caller metadata using
`checkpoint.`, `lineage.`, or `application.` prefixes is rejected.

The coordinator appends ordered bindings for the prior checkpoint identity and
sequence, prior lineage identity, and application identity. The application
UUID5 uses dedicated versioned, UTF-8 byte-length-framed material containing
only the prior checkpoint UUID and caller request UUID.

## Restoration, preparation, and execution

The accepted verified checkpoint is replayed only to validate its complete
`PASS` evidence. Its immutable compact state is restored again through
`restore_paper_ledger_from_compact_state`; the verification-owned mutable ledger
is never used as runtime authority. Restoration must retain exact cash,
position quantities, authoritative total cost bases, derived averages,
cumulative realized profit and loss, checkpoint `as_of`, empty fill membership,
and the compact-restored marker.

Preparation uses the existing public preparation API unchanged. Its derived
account cash, holdings, averages, account identity, and `as_of` must reconcile
with the opening compact state. The existing runtime then preserves planning,
proposal, collective risk, sells-before-buys order construction, paper
submission, deterministic full-fill generation, and atomic fill application.
Caller-asserted open references remain assertions, not independently verified
official opening prints.

## Immutable result and identity

`CheckpointedVerifiedSnapshotPaperCycleResult` is additive and does not alter
`VerifiedSnapshotPaperCycleResult`. It retains prior checkpoint, sequence,
lineage and account-state identities; checkpoint artifact evidence; application
identity; compact restoration evidence; opening and final exact compact states;
preparation; the existing runtime result; opening and final cumulative realized
profit and loss; status; and stable diagnostics. It exposes no engine, ledger,
runtime, orchestrator, or mutable coordinator state.

`NO_ACTION` is successful and advances only final compact `as_of` to the
caller-supplied fill timestamp. `APPLIED` requires at least one applied fill and
retains exact post-fill cash, cost basis, commissions, positions, and cumulative
realized profit and loss. Any runtime or reconciliation failure raises without
returning partial evidence.

The result UUID5 has its own namespace and framed material. It binds prior
checkpoint identity, sequence, lineage and artifact evidence; application and
caller request identities; snapshot identity and artifact evidence; preparation
and runtime identities; pre/post component fingerprints; opening and final
compact-state identities; exact fills; status; and diagnostic codes. It does
not directly include paths, serialized bytes, filesystem metadata, clocks,
mutable objects, providers, object identity, or diagnostic text.
