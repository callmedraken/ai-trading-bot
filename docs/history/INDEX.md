# Project History Index

Status: **PRE-CUTOVER**

This index exists so the project can move toward bounded current-state handoff
documents without losing historical provenance.

Until HIST-2 is accepted, the authoritative current-state files remain:

- `docs/AI_TRADING_BOT_HANDOFF.md`
- `docs/PROJECT_STATUS.md`

Do not use this pre-cutover index as a substitute for those files.

## Deep architecture history

The repository already stores milestone-specific design and contract history
under `docs/architecture/`. In particular, the long-running productionization
line has dedicated records for Architectures 102 through 137, including the
large Architecture 131, 132, 133, and 134 records.

Use those architecture files when the question is about a specific contract,
feature boundary, or accepted design. The future history ledger should point to
them rather than reproducing their full text.

## Legacy snapshot cutover

HIST-2 will add immutable snapshots of the two pre-cutover cumulative canonical
documents under:

- `docs/history/legacy/`

The snapshot names, source identity, byte counts, and SHA-256 digests will be
recorded here during that cutover.

No legacy snapshot has been created by HIST-1.

## Future compact ledger

After cutover, this index should provide targeted pointers to compact history
records grouped by a bounded scheme such as year/month or architecture family.
Each entry should be sufficient to locate the authoritative deeper record
without forcing every new handoff to load the legacy snapshots.

Recommended lookup order for historical questions:

1. this index;
2. the referenced compact history record;
3. the referenced architecture/validation document;
4. the frozen legacy snapshot only if the compact record is insufficient;
5. Git history for exact source-era reconstruction when necessary.

## Cutover acceptance requirements

HIST-2 is not complete unless all of the following are demonstrated:

- exact pre-cutover handoff bytes are preserved in the legacy snapshot;
- exact pre-cutover project-status bytes are preserved in the legacy snapshot;
- archived byte counts and SHA-256 digests are recorded;
- the new handoff contains the current checkpoint, source/evidence boundary,
  active blocker/next action, critical invariants, and handoff reading order;
- the new project status contains the current phase, completed foundations,
  active work, protected boundary, and roadmap;
- current workflow rules explicitly distinguish current state from history;
- targeted references to architecture/validation history remain valid; and
- no protected trading, broker, provider, scheduler, credential, or production
  effect is performed as part of the documentation migration.
