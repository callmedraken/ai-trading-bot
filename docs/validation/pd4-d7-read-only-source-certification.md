# PD4 D7 Read-Only Source Certification

## Status

**ACCEPTED**

This record closes the D7-A/D7-D source-preparation certification boundary under Architecture 113. It authorizes no production D7 invocation and no external effect.

## Certified source identity

```text
branch: feature/pd4-unattended-decision-publication
certified source HEAD: 3dfa9e2cab372f8cb034b90256ed3fba9da6c878
certified source TREE: bb1de2e7c2933ba3a777523f2a0e2feee5fa8c39
```

The certified source includes the previously accepted D7-A Trading-principal read-only qualification source and the D7-D independent read-only post-publication reconciliation source.

D7-A accepted predecessor source:

```text
commit: c72ca6c8665b62c0b8d4f735fc2261a513cb81d5
tree:   3b05c68ff1487a1c7d5984a200ee9f20d7b92fca
focused verification: 910 passed
production qualification: NOT RUN
```

D7-D source-preparation checkpoint:

```text
commit: 3dfa9e2cab372f8cb034b90256ed3fba9da6c878
tree:   bb1de2e7c2933ba3a777523f2a0e2feee5fa8c39
focused verification: 593 passed
production reconciliation: NOT RUN
```

## Consolidated final certification

The final intended D7 source tree was certified once after D7-A and D7-D source work were complete:

```text
pytest: 6302 passed, 17 skipped in 1571.33s (0:26:11)
Ruff check: PASS
Ruff format --check: PASS (532 files)
git diff --check: PASS
git diff --cached --check: PASS
worktree/index: clean
final HEAD: 3dfa9e2cab372f8cb034b90256ed3fba9da6c878
final TREE: bb1de2e7c2933ba3a777523f2a0e2feee5fa8c39
```

The 17 skips are the existing expected opt-in/platform/symlink acceptance skips and do not invalidate this source certification.

## Accepted source properties

D7-A remains a zero-semantic-argument, Trading-principal, read-only qualification boundary. It re-derives current production authority and fixed decision-namespace state without issuing a permit, opening an effect gate, provisioning storage, or performing provider, Paper-v2, scheduler, broker, or live effects. Its sanitized result is diagnostic only and is not reusable publication authority.

D7-D is an independent zero-semantic-argument read-only reconciliation boundary. It independently reconstructs the exact source-owned candidate, requires a `PRESENT_VALID` decision namespace, requires exact finalized discovery for the intended execution session, requires `FINALIZED_IDENTICAL` storage, proves current-C1 same-process provenance for discovery/storage reads, and holds the PD2A mutex through final Paper-v2 account/C1/token/namespace/gate reconciliation. D7-D does not convert wall-clock deadline state into publication authority; an already-finalized exact decision remains reconcilable at or after its intended regular open.

Both boundaries remain effects-closed. No source in this certification authorizes a production D7-A, D7-B, D7-C, or D7-D invocation.

## Production state at certification

The armed D5 capture-only deployment remains separate and must continue naturally. The last accepted read-only warm-up state before this certification was:

```text
selected sessions: 2026-09-11, 2026-09-14
selected_count: 2 / 6
G6: WARMING_UP
```

No manual capture, backfill, scheduler start, decision publication, storage provisioning, Paper-v2 execution/recovery, broker submission, or live effect is authorized by this certification.

D7-C first publication remains **PROTECTED / UNAUTHORIZED**.

## Next checkpoint

Return to the armed D5 worktree and perform a fresh **read-only** D5/G6 readiness check. Do not manually start the scheduler or backfill history. Interpret the result as follows:

- `CAPTURE_REQUIRED`: wait for the normal scheduled D5 capture; no manual action.
- `WARMING_UP`: continue natural accumulation; no manual action.
- `DECISION_READY`: proceed to the separately reviewed real-host D7-A read-only qualification preflight, not D7-C.
- `SESSION_GAP`, `BLOCKED`, contradictory authority/state, or unexpected source identity: stop and diagnose; do not synthesize history or retry effects.

A future docs-only commit containing this certification record does not alter the certified source identity above and does not require another full repository suite.
