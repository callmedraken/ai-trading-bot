# Verified successor prior checkpoint

Milestone 2F-0 introduces a small public `VerifiedPriorCheckpoint` boundary.
It represents either a fully verified genesis checkpoint or a fully verified
`CYCLE_SUCCESSOR` edge. The boundary retains only the checkpoint identity,
lineage, sequence, canonical compact ledger state, empty-engine identity, and
exact checkpoint artifact hash and length required for one later cycle.

A successor becomes a prior only through
`verified_prior_from_successor_edge`. That factory accepts a complete PASS edge
result containing the replayed predecessor, producing report, snapshot, parsed
successor, and exact compact-ledger restoration. Successor bytes on their own
are never accepted as authority. The public model is construction-protected so
normal callers cannot fabricate an unverified prior.

Checkpointed execution restores the compact ledger afresh through the public
ledger restoration API and preserves the prior checkpoint's sequence, lineage,
account-state identity, artifact evidence, and application-ID derivation.
Report and successor-edge verification can receive the verified boundary and
the exact corresponding predecessor payload explicitly. They perform one
disposable replay; they do not discover dependencies or traverse a lineage.

This is deliberately not a general lineage resolver, index, registry, or
multi-edge verifier. Each later edge must be independently supplied with the
complete verified immediate predecessor boundary and its exact artifact bytes.
