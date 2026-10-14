# Project History Storage

Status: foundation only; canonical cutover has not happened yet.

## Purpose

This directory is the long-term home for closed project history that is useful
for audit, reconstruction, and targeted handoff recovery but should not be
loaded on every new session.

The current canonical project-state files remain:

- `docs/AI_TRADING_BOT_HANDOFF.md`
- `docs/PROJECT_STATUS.md`

until a separately reviewed cutover replaces them with bounded current-state
documents. Nothing in this directory overrides those files before that cutover.

## Information layers

The project should keep four distinct information layers:

1. **Workflow and standing rules**
   - `AGENTS.md`
   - `docs/AI_DEVELOPMENT_WORKFLOW.md`
2. **Current state**
   - `docs/PROJECT_STATUS.md`
   - `docs/AI_TRADING_BOT_HANDOFF.md`
3. **Architecture and validation contracts**
   - `docs/architecture/`
   - `docs/validation/`
4. **Closed historical record**
   - `docs/history/`

Current-state files must not become cumulative project journals again after the
cutover.

## Migration strategy

The history migration is intentionally staged.

### HIST-1 — storage foundation

Add the history policy and index without changing the active canonical handoff
or status files. This permits the work to proceed independently from protected
production-paper qualification.

### HIST-2 — exact legacy snapshot and canonical cutover

At a separately reviewed source boundary:

1. freeze the then-current full handoff and project-status files as immutable
   legacy snapshots under `docs/history/legacy/`;
2. verify the archived bytes against the pre-cutover source before replacing the
   canonical files;
3. replace the canonical handoff with a bounded session bootstrap/current-state
   handoff;
4. replace project status with a bounded current dashboard/roadmap;
5. add the history index entries needed to locate the legacy snapshots and
   current architecture records;
6. update `AGENTS.md` and `docs/AI_DEVELOPMENT_WORKFLOW.md` so new sessions
   read history only when targeted reconstruction is needed; and
7. enable size/structure guardrails only after the cutover succeeds.

The migration must never infer that old prose is expendable merely because a
shorter summary exists. The exact legacy snapshots remain available for deep
reconstruction.

### HIST-3 — optional historical distillation

After the exact snapshots are safely archived, older milestone history may be
distilled into compact yearly/monthly or architecture-family ledgers. Distilled
records supplement the frozen snapshots; they do not silently replace them.

## Post-cutover current-document policy

The initial targets are deliberately generous and should be reviewed during
HIST-2:

- `AI_TRADING_BOT_HANDOFF.md`: target <= 96 KiB;
- `PROJECT_STATUS.md`: target <= 64 KiB;
- retain only a small recent-transition window in either current-state file;
- closed milestone narratives move to history/architecture records rather than
  being copied into both current-state files.

These are post-cutover targets, not active CI limits yet.

## History record requirements

A compact milestone/event record should preserve, when applicable:

- date;
- architecture/checkpoint identifier;
- terminal state or classification;
- branch;
- accepted or effect source HEAD and TREE;
- CI run/checkpoint identity;
- certification profile and result;
- evidence path, byte count, digest, schema, or artifact identity;
- protected-effect classification and whether provider/broker/credential effects
  occurred;
- invariants or frozen contracts that still matter;
- explicit successor or next boundary; and
- links to the authoritative architecture/validation document.

Do not copy secrets, credential values, private keys, tokens, or other sensitive
material into history records.

## Immutability and corrections

Frozen legacy snapshots are historical evidence. Do not rewrite them to make
old terminology look current.

If a historical statement needs correction, add a later correction record or an
index annotation that clearly identifies what it supersedes. Current authority
belongs in the current-state/workflow/architecture documents, not by silently
editing old evidence.

## Retrieval rule for handoffs

A new session should normally reconstruct state in this order:

1. `AGENTS.md`;
2. `docs/AI_DEVELOPMENT_WORKFLOW.md`;
3. `docs/PROJECT_STATUS.md`;
4. `docs/AI_TRADING_BOT_HANDOFF.md`;
5. the current architecture/validation record.

Read `docs/history/INDEX.md` or a specific legacy snapshot only when the task
requires older provenance, a predecessor contract, incident reconstruction, or
a disputed historical boundary.

This keeps routine handoffs bounded while retaining the full audit trail.
