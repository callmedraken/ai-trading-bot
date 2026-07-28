# Deterministic full-lineage offline verification

Milestone 2F adds one read-only boundary that verifies a unique explicit path
from a canonical genesis checkpoint to one caller-selected terminal checkpoint.
It consumes exact artifact payloads through `verify_paper_account_lineage`, or a
strict manifest through the thin command adapter. It never discovers artifacts,
scans transition parents, contacts a provider or broker, writes output, or uses
a clock, registry, database, scheduler, subprocess, or global lock.

## Explicit artifact index

The caller supplies exactly one genesis artifact and finite collections of
successor checkpoints, checkpointed-cycle reports, and daily snapshots. Each
record binds a claimed domain UUID, lowercase SHA-256, nonnegative byte length,
and exact bytes. Collections are sorted by domain UUID and digest for stable
validation. Repeated records with the same kind, UUID, evidence, and exact bytes
are normalized. A reused UUID with different material and exact bytes claimed
under different identities fail before artifact parsing.

The optional schema-1 JSON manifest has these exact root fields:

```text
schema_version
genesis_checkpoint
terminal_checkpoint_id
successor_checkpoints
cycle_reports
snapshots
```

Every artifact entry has exactly `artifact_id`, `path`, `sha256`, and
`byte_length`. Paths are resolved only from explicit entries relative to the
manifest, unless already absolute. The manifest and artifacts must be real
regular files with no symbolic-link or reparse-point component and stable file
identity across the bounded read. Paths and filesystem metadata never enter
lineage evidence identity.

## Verification order

The genesis artifact evidence and complete genesis verification run first. The
remaining artifacts are evidence-checked, deterministically deduplicated,
strictly parsed or verified, and indexed by domain UUID. Global reconciliation
rejects conflicting checkpoint, report, and snapshot references; actual-parent
sequence or lineage disagreement; forks; cycles; report reuse; and application
ID reuse with different material.

The verifier then walks the one supplied child path from genesis. Every required
report and snapshot must be present. Each edge is verified by the existing
one-edge verifier with the immediate `VerifiedPriorCheckpoint`; only a complete
PASS edge can authorize the next successor. No successor bytes are trusted in
isolation and no predecessor is assumed to be genesis after the first edge.

Diagnostics use the declaration order of
`PaperAccountLineageVerificationCode` as the fixed validation precedence. FAIL
exposes one stable code and no lineage evidence, terminal checkpoint, or ledger.

## Immutable evidence

PASS returns frozen, slotted `PaperAccountLineageEvidence` containing genesis
and terminal checkpoint IDs, terminal lineage ID, edge count, ordered checkpoint,
application, cycle-result, and snapshot IDs, ordered artifact hashes and byte
lengths, and the exact terminal compact ledger state. The result additionally
exposes the completely verified terminal checkpoint and compact-restored ledger.

Evidence UUID5 material version `paper-account-lineage-evidence-v1` binds those
ordered identities, transport-evidence values, and terminal compact-state UUID.
It excludes paths, serialized bytes, filesystem timestamps, diagnostic text,
mutable objects, provider state, clocks, and process-local identity.
