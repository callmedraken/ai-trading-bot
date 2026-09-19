# PD4 D6 Unattended Decision Publication Source Certification

Status: **ACCEPTED**

This record closes the Architecture-113 D6 source checkpoint. It records source acceptance only. It does not authorize a real D7 decision publication, decision-storage provisioning, Paper-v2 mutation, Task Scheduler mutation, provider effect, broker effect, or live effect.

## Certified source boundary

```text
branch: feature/pd4-unattended-decision-publication
certified source HEAD: fb00e9898c2e5cdd3db27cd91c393f5994c7cca9
certified source TREE: eef138bb3ed144d153ae60193aaacdcb7584c513
remote HEAD at certification: fb00e9898c2e5cdd3db27cd91c393f5994c7cca9
```

The final certified source commit is a test-only portability closeout. The production D6 implementation immediately beneath it is:

```text
implementation commit: d3af7d72ff182a54370897bcdf2fc9968990ad7a
implementation tree:   869853ec8b65bf0207de673a36436616a9f97fb6
```

The frozen D6-A architecture/test-contract checkpoint is:

```text
D6-A commit: ece746462b2c1426e1bb982417039dda385fef1b
D6-A tree:   14456c239949c1ed0a6e70757a67af8cbac492c6
Architecture-113 blob: 9443b587b74ac859ecca99ce2d835f3d99187e09
validation-plan blob:  5834c6417fae074ec506d42e271a1fd6f16c829d
```

## Accepted implementation scope

D6 is the Architecture-113 zero-semantic-argument decision-only production boundary. The accepted source:

- requires all eight production effect gates to be exact booleans and false at admission;
- independently re-derives current C1, exact Paper-v2 account/predecessor, selected C3 history, source-owned MA 3/5 strategy decision, intended execution session, deadline, and fixed decision-storage state;
- reuses the existing PD2A account mutex across predecessor-sensitive construction, publication, durable reread, and final account reconciliation;
- treats G6 output as diagnostic only and never as publication authority;
- permits fresh publication only from genuine `ABSENT` storage;
- treats `FINALIZED_IDENTICAL` as strict zero-write convergence;
- blocks staging, conflicting, malformed/unknown, provenance/security, and reparse contradictions;
- enforces `observed_now < regular_open(E)` and maps at/after-open admission to `MISSED_DECISION_DEADLINE`;
- allows at most one permit, one writer, and one `publish()` attempt per invocation;
- temporarily opens only the process-local decision-publication gate at the reviewed writer boundary and restores it in `finally`;
- accepts publication only after all gates are closed and a fresh production storage reread proves exact `FINALIZED_IDENTICAL` while the account predecessor still matches under the held mutex;
- performs no G5/provider capture, Paper-v2 execution/recovery, storage provisioning, scheduler mutation, broker submission, or live effect.

No real D6 production publication occurred during source implementation, focused verification, portability repair, or final certification.

## Focused verification

The D6 implementation focused source gate completed with:

```text
239 passed
Ruff check: PASS on changed files
Ruff format --check: PASS on changed files
```

Coverage included zero-semantic-argument launcher behavior, all-eight-gate containment, PD2A mutex ordering, current-C1 re-derivation, exact account/predecessor binding, selected-C3/history reconstruction, deadline edges, fixed-storage classifications, duplicate convergence, one-shot permit/writer semantics, failure/ambiguity handling, post-publication durable reread, predecessor drift, native writer failure seams, and prohibited-effect boundaries.

## Broad-certification portability correction

The first broad D6-D run exposed two historical test-harness portability problems rather than a D6 runtime regression:

1. PD2D1 tests could resolve the frozen strategy-history seed through the armed D5 worktree instead of isolating the checkout fixture;
2. frozen-source identity tests hashed raw Windows checkout bytes, so CRLF working-tree conversion differed from the tracked LF Git blob.

The correction changed tests only:

```text
tests/cli/test_pd2d1_first_paper_qualification.py
tests/cli/test_pd2d1_preparation_readonly_diagnostic.py
tests/runtime/test_personal_desktop_supervised_paper_operation_execution.py
tests/runtime/test_personal_desktop_supervised_paper_operation_qualification.py
tests/runtime/test_personal_desktop_unattended_scheduler_contract.py
```

Portability-correction verification:

```text
318 passed
Ruff check: PASS on exactly changed tests
Ruff format --check: PASS on exactly changed tests
git diff --check: PASS
git diff --cached --check: PASS
```

The correction did not change production code, fixtures, frozen expected hashes, architecture, validation contracts, configuration, D5 source, or the scheduler.

## Final D6-D broad source certification

The final unchanged source tree passed the complete repository suite:

```text
6007 passed, 17 skipped in 1502.66s (0:25:02)
full repository pytest gate: PASS
D6-D FINAL SOURCE CERTIFICATION: PASS
```

The certification also required repository-wide Ruff check and Ruff format-check gates, exact commit/tree/remote identity, diff checks, Architecture-113 and validation-plan blob identity, D6 source provenance, and read-only reconciliation that the armed D5 source remained exact.

Accepted armed D5 identity after D6-D certification:

```text
D5 HEAD: 8c2af5801cbc8f4df869b832a3b78b1eaa2f8996
D5 TREE: f0591e966463c7e1e66dc00ad76fd895500a076f
```

## Post-certification D5 readiness observation

A later effects-closed read-only observation under `DESKTOP-I4DOKM7\Trading` reconfirmed:

```text
D5 HEAD: 8c2af5801cbc8f4df869b832a3b78b1eaa2f8996
D5 TREE: f0591e966463c7e1e66dc00ad76fd895500a076f
G5: NO_NEW_COMPLETED_SESSION
G6: WARMING_UP
history window: WARMING_UP
selected_count: 2 / 6
selected sessions: 2026-09-11, 2026-09-14
completed session: 2026-09-14
selected snapshot: b3737822-35ee-5238-a87f-401b4597df46
account predecessor: ed4640e5-0630-525d-b916-d50e31e3ba2a
all eight gates closed before: true
all eight gates closed after: true
real_effect_performed: false
```

The six source-owned sessions required by that point-in-time history window were:

```text
2026-09-04
2026-09-08
2026-09-09
2026-09-10
2026-09-11
2026-09-14
```

Only the final two had authoritative selected C3 evidence, so no offline-seed backfill, manual D5 start, ad hoc provider invocation, or historical decision publication is authorized.

## Next checkpoint

D6-A through D6-D are complete. The next protected sequence remains D7:

```text
D7-A  Trading-principal real-host read-only qualification
D7-B  conditional Administrator decision-namespace provisioning only if D7-A proves it missing
D7-C  one explicitly approved first real decision publication under Trading
D7-D  fresh independent all-gates-closed post-publication reconciliation
```

D7-A production qualification must not be treated as eligible until D5 naturally reaches a current candidate decision with the required six consecutive selected-C3 sessions and the publication deadline remains open.

While D5 is still `WARMING_UP`, source-only preparation of the D7-A read-only qualification harness and D7-D reconciliation tooling may proceed on the isolated development branch. That preparation must not modify the armed D5 worktree/task, open any effect gate, provision storage, publish a decision, mutate Paper-v2, or perform broker/live effects.
