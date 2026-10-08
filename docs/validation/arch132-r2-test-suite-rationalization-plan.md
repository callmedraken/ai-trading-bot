# Architecture 132-R2 — Test Suite Rationalization Validation Plan

## 2026-10-07 — Architecture 132-R2 test-suite rationalization interlude

Architecture 133-M is source-accepted and docs-closed, but the real protected
133-M diagnostic is intentionally paused while routine CI/test topology is
rationalized.

Current accepted source baseline for this infrastructure interlude:

```text
PARENT  0e856691c2d1ce350d1846720182bba2bea64f0a
TREE    1536e7a45a67d214ee97454290e2781b3b7001d9
BRANCH  feature/test-suite-rationalization-132r2
```

Current certification ownership at that parent is FULL 127, ROBINHOOD 54,
LEGACY 204, EXHAUSTIVE 331. Architecture 132-R1 already defines LEGACY and
EXHAUSTIVE as explicit, non-routine gates, but routine source-gate CI still
batches eight retained Architecture 128/130 checkpoints ahead of the active
Architecture 131/133 checkpoints.

The latest accepted source gate #286 / 37708975995 ran one deduplicated batch:

```text
CHECKPOINTS 44
TEST_PATHS  68
RUFF_PATHS  150
pytest      6,393 passed / 3 skipped / 0 failed / 0 errors
PYTEST      0
RUFF_CHECK  0
RUFF_FORMAT 0
GIT_DIFF    0
```

This routine source gate therefore overlaps substantially with broad current-
product certification and also reintroduces retained compatibility coverage
that Architecture 132-R1 intentionally removed from routine FULL/ROBINHOOD
certification.

Architecture 132-R2 fixes test topology before any additional protected
Architecture 133 operation. It is a test/workflow-infrastructure change only and
grants no new production, provider, scheduler, credential, wake, broker or live
authority.

### 132-R2 phased plan

**R2-A — measure and correct routine CI scope**

1. Persist source-gate timing evidence: pytest elapsed time, top-100 pytest
   durations, and existing command/lane elapsed data. Timing is diagnostic only
   and cannot affect PASS/FAIL.
2. Replace the single routine checkpoint sequence with explicit
   `ACTIVE_CI_CHECKPOINTS` and `RETAINED_CHECKPOINTS`.
3. The retained set is exactly:
   - `arch128-parent-acl-repair`
   - `arch128-r4`
   - `arch128-r5-substrate`
   - `arch128-r5-trading`
   - `arch128-r6`
   - `arch128-r7`
   - `arch128-r8-terminal-halt`
   - `arch130-r8i-d1`
4. Every retained checkpoint remains registered, authority-pinned, individually
   runnable, and available to explicit batch verification. No retained source
   or test is deleted in R2-A.
5. Routine current-product GitHub source-gate batching executes only the active
   Architecture 131/133 sequence. All active checkpoint tests, Ruff paths,
   authority checks, order pins and source-identity invariants remain enforced.
6. R2-A does not change FULL/ROBINHOOD/LEGACY/EXHAUSTIVE ownership or the frozen
   Architecture 132-R1 required baselines.

**R2-B — split monolithic test infrastructure without deleting coverage**

Split `tests/runtime/test_checkpoint_runner.py` by responsibility so core
runner/batch/CI classification and active Architecture 131/133 contracts are
independently selectable from retained Architecture 128/130 compatibility
contracts. Split `tests/scripts/test_run_test_certification.py` into independently
selectable profile/inventory, lane construction, source admission, child/JUnit,
and protected-opt-in/result areas. Preserve all tests initially; this phase is
structural/selectability work.

**R2-C — retained source+test provenance audit**

Audit all 204 LEGACY modules and their exercised production/source surfaces.
Classify each cohort `KEEP_COMPAT`, `DISTILL_INVARIANTS`, or
`DELETE_WITH_SOURCE`. No deletion is allowed merely because a test is old.
Any retained Windows/security primitive used or source-pinned by current
Architecture 133 stays until its current invariant is migrated and independently
proved.

**R2-D — parallelize only after scope/selectability cleanup**

After R2-A/R2-B measurements are accepted, create deterministic parallel active
source-gate lanes. Do not parallelize today's oversized routine workload first.

### Immediate checkpoint

The next implementation checkpoint is **132-R2-A** only: timing evidence plus
active/retained source-gate separation. Use Astra because the change crosses
checkpoint registration, workflow topology, authority pins, and tests, but does
not change production authority. Focused verification only during implementation;
ChatGPT performs exact-source review and decides whether any broader
certification is necessary afterward.

The real Architecture 133-M diagnostic remains ready but paused. Q133-2V remains
consumed/non-retryable. Q133-3 and Q133-4 remain unauthorized.



## R2-A acceptance contract

R2-A is accepted only if all of the following are true:

- routine source-gate CI has an explicit active checkpoint sequence containing
  all current Architecture 131 and 133 registered source checkpoints in their
  reviewed order;
- the exact eight Architecture 128/130 retained checkpoints are excluded from
  routine current-product batching but remain registered and explicitly
  runnable;
- explicit verification of a retained checkpoint still runs its complete
  existing test/Ruff/authority contract;
- batch verification still accepts an explicit caller-provided mix of active and
  retained checkpoints, so LEGACY/recovery investigation remains possible;
- workflow source pins prove the executable routine batch contains exactly the
  active sequence once, with exit propagation intact;
- no Architecture 131/133 checkpoint loses any test path, Ruff path, authority
  check, or source pin as a side effect of the separation;
- `run_test_certification.py` profile ownership and frozen required baselines
  are byte-for-byte unchanged in R2-A unless a review-proven test relocation
  requires a later R2-B change;
- source-gate reports record pytest elapsed time and retain top-100 pytest
  duration output as evidence, but timing never affects gate status;
- source-gate test collection remains deterministic, de-duplicated and
  first-seen ordered;
- docs-only classification remains unchanged;
- no protected/native/provider/scheduler/credential/wake/broker action is
  introduced.

## Focused verification for R2-A

Implementation should run only the affected runner/workflow/certification tests
and non-mutating static checks. Use fresh `--basetemp` under
`F:\AI\temp\pytest`. Do not run FULL, LEGACY, EXHAUSTIVE, real Architecture
133 diagnostics, or protected operations during implementation.

After ordinary push, follow the source gate to terminal and report:

- exact active and retained checkpoint lists;
- deduplicated routine test/Ruff path counts before vs after;
- pytest case count and elapsed time from terminal CI;
- top-duration evidence location/output;
- exact commit/tree and terminal workflow run;
- confirmation retained checkpoints remain explicitly runnable;
- any changed source-authority hashes/order pins.

ChatGPT then reviews the exact GitHub diff and decides the next R2-B split
checkpoint.
