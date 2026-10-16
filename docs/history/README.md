# Project History Storage

Status: **post-cutover policy; HIST-2 exact snapshot and canonical cutover are
complete**.

## Purpose and information layers

This directory stores closed project history for audit, reconstruction, and
targeted handoff recovery. It is not routine startup material.

The current information layers are:

1. standing workflow rules: `AGENTS.md` and
   `docs/AI_DEVELOPMENT_WORKFLOW.md`;
2. bounded current state: `docs/PROJECT_STATUS.md` and
   `docs/AI_TRADING_BOT_HANDOFF.md`;
3. architecture and validation contracts: `docs/architecture/` and
   `docs/validation/`;
4. closed historical record: `docs/history/`.

Current-state documents must remain bounded. Cumulative chronological
narratives must not grow back into them. Closed detail belongs once in the
relevant architecture, validation, or history record.

## Canonical bounded handoff branch

The ongoing canonical new-chat handoff/history branch is:

`feature/project-history-storage-foundation`

It is maintained as a **fast-forward mirror of the latest accepted bounded-docs
descendant of the active product lineage**. It must not become an independent
source line. Accepted checkpoint docs close on the active product lineage first;
only after that descendant is accepted may this branch fast-forward to the same
commit. A non-fast-forward relationship is a STOP for reconciliation.

This branch is the routine startup surface for bounded status/handoff and
history routing. It is not executable-source, provider, broker, or trading
authority; protected source admission must independently verify the active
product branch and exact HEAD/tree.

## HIST-2B exact snapshot and cutover

The former cumulative handoff and project-status documents are frozen at
`docs/history/legacy/HIST-2B-2026-10-13/`. Their exact source identity, byte
counts, digests, and manifest are recorded in [INDEX.md](INDEX.md).

The immutable snapshots remain available for audit and deep reconstruction;
they do not override the bounded current documents. Load them only when a task
requires older provenance, incident reconstruction, predecessor semantics, or
disputed historical evidence.

Immutable legacy snapshots must be Git-stored byte-for-byte. The repository
invariant `docs/history/legacy/** -text` prevents line-ending normalization,
including for their manifests. A manifest digest therefore refers to the exact
Git-stored archival bytes, not merely a pre-stage Windows working-tree
representation.

## Exact-archive tooling retained

`scripts/archive_project_history.py` remains the exact-archive utility for a
future separately reviewed snapshot. It reads the two canonical documents as
raw bytes and supports a read-only inventory:

```text
python -B scripts/archive_project_history.py --dry-run --cutover-id HIST-2A
```

Dry-run reports source HEAD/TREE, proposed destination, byte counts, SHA-256,
and informational line counts without writing. Without `--cutover-id`, it uses
the lexical placeholder `docs/history/legacy/<cutover-id>/`.

Real archive mode requires a safe single-component identifier, a clean
repository, exact source admission, an unused destination, and explicit
`text: unset` Git attributes for every output document and `manifest.json`.
It writes only beneath the requested legacy destination, verifies exact bytes
and digests, and cleans up on failure. It must not be used to rewrite the
immutable HIST-2B snapshot or to bypass a separately reviewed cutover.

## Corrections and records

Frozen legacy snapshots are historical evidence. Do not rewrite them to make
old terminology look current. Historical corrections are additive: add a later
correction record or an index annotation that clearly identifies what it
supersedes. Never silently rewrite immutable evidence.

Compact history records should preserve, when applicable, the date,
architecture/checkpoint identifier, terminal state, branch, accepted source
identity, CI or certification identity, evidence path and digest, protected-
effect classification, material invariants, successor boundary, and links to
the authoritative architecture or validation document. Never copy secrets,
credential values, private keys, or tokens into history.

## Retrieval rule

New sessions normally resolve
`feature/project-history-storage-foundation` and read its `AGENTS.md`,
`docs/AI_DEVELOPMENT_WORKFLOW.md`, `docs/PROJECT_STATUS.md`,
`docs/AI_TRADING_BOT_HANDOFF.md`, and the relevant architecture or validation
document. Then independently verify the active product branch and exact
HEAD/tree before source or protected work. Read [INDEX.md](INDEX.md) or a
specific legacy snapshot only for targeted reconstruction. This keeps routine
handoffs bounded while retaining the full audit trail.
