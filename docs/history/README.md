# Project History Storage

Status: **post-cutover policy active; HIST-2 exact snapshot preserved**

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
4. compact closed records and immutable historical snapshots:
   `docs/history/`.

Current-state documents must remain bounded. Cumulative chronological narratives
must not grow back into them. Closed detail belongs once in the relevant
architecture, validation, or history record.

## Default startup reference and retired compatibility/history mirror

Current remote `develop` is the sole primary/default startup integration
reference for bounded reconstruction. The former
`feature/project-history-storage-foundation` compatibility/history mirror is
retired at final synchronized tip
`19e5859fa83656cc50dbe69f89f3badd57841165`, which was identical to `develop`.
Do not recreate or synchronize that branch. Historical references to it are
retrieval context only.

Startup documentation is not executable-source, provider, broker, or trading
authority; independently verify the active product branch and exact executable
HEAD/tree before source or protected work.

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

## Corrections and compact records

Frozen legacy snapshots are historical evidence. Do not rewrite them to make old
terminology look current. Historical corrections are additive: add a later
compact record or an index annotation that clearly identifies what it
supersedes.

Compact records should preserve, when applicable, the date, architecture or
checkpoint identifier, terminal state, accepted source identity, CI or
certification identity, evidence path/digest, protected-effect classification,
material invariants, successor boundary, and links to authoritative
architecture/validation documents. Never copy secrets, credential values,
private keys, or tokens into history.

## Retrieval rule

New sessions resolve current remote `develop` and read, in order, its
`AGENTS.md`, `docs/AI_DEVELOPMENT_WORKFLOW.md`, bounded
`docs/PROJECT_STATUS.md`, bounded `docs/AI_TRADING_BOT_HANDOFF.md`, then
relevant architecture/validation documents. Separately verify the active remote
product branch and exact executable HEAD/tree before source or protected work.
Read [INDEX.md](INDEX.md), a compact record, or the legacy snapshot only for
targeted reconstruction.
