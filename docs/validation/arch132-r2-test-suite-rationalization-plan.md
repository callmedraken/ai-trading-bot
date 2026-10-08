# Architecture 132-R2 — Test Suite Rationalization Validation Plan

## 2026-10-07 — Architecture 132-R2-A ACCEPTED; R2-B split/selection frozen

Architecture 132-R2-A is **SOURCE/TOPOLOGY ACCEPTED**.

Accepted executable/test source:

```text
BRANCH  feature/test-suite-rationalization-132r2
HEAD    d86c13c00b72f8800bddb15a57c582dbd790b774
TREE    8c06d080fb936c40bccf74c523572e5152c6d12d
CI      #288 / 37713529571 SUCCESS
```

Evidence/docs descendant:

```text
HEAD    8129bac92ce84628048ccafc76815f6511c0990d
TREE    3ee934821ace692e74bebe201445300062487d17
CI      #289 / 37714920814 SUCCESS
```

ChatGPT exact-source review found no correction required. The retained eight
Architecture 128/130 checkpoints remain registered, individually runnable and
available to explicit retained-only or mixed `verify-batch` calls. The routine
workflow invokes exactly the 36 active Architecture 131/133 checkpoints in
reviewed order. First-seen batch de-duplication, active source/registration
pins, authority checks, docs-only classification, clean identity requirements,
and protected `NOT_RUN` semantics remain fail-closed.

R2-A adds only observational timing evidence. `elapsed_seconds` is measured
with a monotonic timer and does not participate in PASS/FAIL. Pytest top-100
durations remain in uploaded stdout evidence.

No additional FULL or ROBINHOOD certification is required for R2-A.
`scripts/run_test_certification.py`, certification ownership, frozen FULL and
ROBINHOOD required baselines, lane semantics and protected-opt-in rejection are
unchanged. Source gate #288 already exercised the changed runner together with
the complete active checkpoint requirement union and every active authority
check. A product certification would not add material evidence for this
source-gate topology-only change.

R2-A measurement outcome:

```text
routine checkpoints   44 -> 36
test paths            68 -> 42
ruff paths           150 -> 120
cases              6,393 -> 4,850 collected outcomes
R2-A pytest         4,849 passed / 1 skipped
R2-A pytest time    790.08 s
command elapsed     792.1711838 s
```

The smaller routine union did not reduce wall time in this single comparison.
The diagnostic evidence localizes the next bottleneck: **all 100 slowest R2-A
tests are in the checkpoint-runner infrastructure suite**, led by repeated
133-L/133-M/H authority mutation tests. Therefore R2-B must improve
selectability and repeated-test cost before R2-D parallelization.

### R2-B frozen contract — split infrastructure without losing logical coverage

R2-B remains test/workflow infrastructure only. It grants no production,
provider, credential, scheduler, wake, broker or live authority. Real
Architecture 133-M remains paused.

#### 1. Split checkpoint-runner tests by responsibility

Replace the monolithic
`tests/runtime/test_checkpoint_runner.py` with independently collectible
modules under a dedicated runtime subpackage. The target responsibility split
is:

```text
tests/runtime/checkpoint_runner/test_core.py
tests/runtime/checkpoint_runner/test_ci.py
tests/runtime/checkpoint_runner/test_arch131.py
tests/runtime/checkpoint_runner/test_arch133_a_g.py
tests/runtime/checkpoint_runner/test_arch133_h_k.py
tests/runtime/checkpoint_runner/test_arch133_l_m.py
tests/runtime/checkpoint_runner/test_retained_arch128_130.py
```

A `conftest.py` and/or non-test helper module may hold inert shared fixtures.
Do not leave duplicate collected copies of moved tests in the old monolith.

The first six modules are current supported test infrastructure. The retained
Architecture 128/130 module is LEGACY compatibility. Routine active source CI
must not collect the retained module merely because every checkpoint shares a
common test path.

`COMMON_TESTS` must become a genuinely small core/CI contract, not a new alias
for every historical/current runner test. Architecture-specific runner contract
modules must be attached only to the checkpoints whose source/authority
contracts they protect. Explicit retained checkpoint verification must still
select the retained runner contract.

#### 2. Split certification-runner tests by responsibility

Replace the monolithic
`tests/scripts/test_run_test_certification.py` with independently collectible
supported modules covering at least:

```text
profile / inventory classification
lane construction
source identity / admission
child execution + JUnit aggregation
protected opt-in + result/evidence semantics
```

Shared inert fixtures/helpers may live in non-collected support files. Routine
Architecture 131/133 source checkpoints should include only the certification
test module(s) actually needed by their source/inventory authority contract;
they must no longer pull the entire certification-runner regression suite merely
because one inventory assertion is relevant.

#### 3. Deliberately update Architecture-132 ownership

Because the two old supported monoliths are being replaced by multiple test
modules, R2-B is an explicit certification-topology change.

Update `run_test_certification.py` ownership and required baselines
deliberately:

- current/core/Architecture-131/Architecture-133 runner split modules are FULL
  and ROBINHOOD infrastructure;
- retained Architecture-128/130 runner tests are LEGACY, not ROBINHOOD/FULL;
- all certification-runner split modules remain supported infrastructure and
  retain their appropriate FULL/ROBINHOOD ownership;
- FULL ∩ LEGACY remains empty;
- FULL ∪ LEGACY remains EXHAUSTIVE;
- unknown ownership remains fail-closed;
- no required baseline may silently disappear because a monolith was renamed.

Record the exact old-to-new baseline mapping and new profile module counts.
Module counts may rise because one file becomes several; that is expected and
must not be mistaken for broader product scope.

#### 4. Preserve logical tests while removing recursive test-harness waste

R2-B does **not** weaken production authority functions or their source pins.

For expensive chained authority mutation tests (especially 133-H/L/M), retain
the full missing/changed pin matrix and runtime/workflow/callback rejection
coverage, but unit tests for a checkpoint's *local* authority layer need not
re-execute every already-proven predecessor authority layer for every
parameterized mutation.

It is acceptable and preferred to isolate local-layer tests by replacing only
the predecessor authority function with a deterministic PASS stub in the test
process, provided separate integration tests prove:

- each production authority function invokes its real predecessor;
- predecessor failures propagate fail-closed;
- the complete real chain passes on the accepted repository;
- workflow/order/registration checks remain real where they are the subject of
  the test.

Do not mock the local layer under test. Do not weaken the production chain.
Do not remove any missing/changed source-pin dimension merely for speed.

The goal is to preserve logical coverage while eliminating thousands of
redundant predecessor source reads/copies/AST checks caused by parameterization.

#### 5. Measure R2-B rather than guessing

Keep R2-A timing instrumentation. Terminal R2-B CI must report:

- active TEST_PATHS/RUFF_PATHS before vs after;
- total pytest cases/passed/skipped;
- pytest wall time and command elapsed time;
- top-100 durations;
- case counts by each new infrastructure test module;
- confirmation retained-only explicit verification still selects its retained
  runner tests;
- profile module counts and old-to-new required baseline mapping.

No timing threshold is a correctness gate.

#### 6. No deletion/provenance audit or parallelization yet

R2-B may remove the two old monolith files only as a test relocation after all
logical coverage is accounted for. It may not delete historical production
source or retire legacy behavioral suites. That belongs to R2-C.

Do not implement parallel source-gate lanes in R2-B. R2-D remains after accepted
R2-B measurements.

### R2-B verification/acceptance

Implementation uses Astra. Run focused split-module, checkpoint registration,
inventory/classification and source-authority tests with fresh external
basetemps. No FULL/ROBINHOOD/LEGACY/EXHAUSTIVE certification during
implementation. After exact source review, because R2-B deliberately changes
certification inventory topology, ChatGPT will select the final certification
tier; a FULL current-product certification is expected unless the reviewed
evidence establishes a stronger equivalent.

R2-B does not authorize the real 133-M diagnostic. Q133-2V remains consumed;
Q133-3 and Q133-4 remain unauthorized.

## 2026-10-07 — Architecture 132-R2-A terminal CI green (source review pending)

R2-A separates the routine source batch from retained compatibility without
changing the checkpoint registry or certification ownership. The exact 36 active
Architecture 131/133 checkpoints retain their previous relative order and all
registered tests, Ruff paths, source pins and authority boundaries. The eight
Architecture 128/130 checkpoints listed in the frozen R2-A contract remain
registered, individually verifiable and selectable in retained-only or mixed
explicit batches. First-seen requirement deduplication is unchanged.

Measured requirement unions against the admitted frozen design parent:

| Routine source gate | Before | R2-A |
| --- | ---: | ---: |
| Checkpoints | 44 | 36 |
| Test paths | 68 | 42 |
| Ruff paths | 150 | 120 |

Accepted baseline CI #286 / 37708975995 recorded 6,393 passed / 3 skipped
in 696.12 seconds. Implementation CI **#288 / 37713529571 SUCCESS** recorded
**4,849 passed / 1 skipped / 0 failed / 0 errors in 790.08 seconds**.
All 36 authority results passed, identity remained stable, and protected
production/scheduler/provider/broker evidence remained `NOT_RUN`.

```text
IMPLEMENTATION HEAD d86c13c00b72f8800bddb15a57c582dbd790b774
IMPLEMENTATION TREE 8c06d080fb936c40bccf74c523572e5152c6d12d
PYTEST             0 / elapsed_seconds 792.1711838
RUFF_CHECK         0 / elapsed_seconds 0.130218000000013
RUFF_FORMAT        0 / elapsed_seconds 0.120859800000062
GIT_DIFF           0 / elapsed_seconds 0.038282099999833
```

The pytest-reported duration was 93.96 seconds higher than the accepted
baseline despite the smaller file union. This single cross-run comparison does
not establish a speedup or explain the timing difference. No timing threshold
was applied.

The [source workflow](https://github.com/callmedraken/ai-trading-bot/actions/runs/37713529571)
uploaded [checkpoint-source-gate-evidence](https://github.com/callmedraken/ai-trading-bot/actions/runs/37713529571/artifacts/11522378514).
Within that artifact, machine-readable command timings are in
`source-gate-batch-20261008T013401.428982Z/report.json`, and the complete top-100
pytest output is in the adjacent `commands/01-pytest.stdout.txt`. All 100 slowest
entries came from `tests/runtime/test_checkpoint_runner.py`. The slowest three
were 133-L import-closure pin drift (5.79s), 133-H complete-authority pin drift
(4.72s), and 133-M import-closure pin drift (3.70s). These are source tests;
the real protected 133-M diagnostic was not run.

Command reports add observational `elapsed_seconds` from a monotonic timer.
Pytest stdout preserves `--durations=100 --durations-min=0.0` output in the
existing uploaded command evidence. Timing has no PASS/FAIL threshold. Report
schema, authority results, source identity and protected `NOT_RUN` fields remain
unchanged. Active tuple AST pins now freeze
`8aaf63458ec12dea75e130e257577c0d00ba3bba5a4bb7a4db4059c7a8ab8b2a`;
production source and registration pins are unchanged.

The workflow adds only the explicitly requested `feature/test-suite-*` push
family. Its active invocation and docs-only classification remain source-pinned.
Terminal implementation measurements are recorded above in this separate
docs-only evidence checkpoint. This records implementation evidence and does
not claim source/topology or certification acceptance.
ChatGPT owns exact GitHub source review, topology acceptance and certification
choice. R2-B has not started. Real 133-M remains paused; Q133-2V is consumed and
Q133-3/Q133-4 remain unauthorized. No protected operation was invoked.

The requested development interpreter path `F:\AI\ai-trading-bot.venv` was
absent; implementation uses the existing `F:\AI\ai-trading-bot\.venv` instead,
with fresh explicit external basetemp directories under `F:\AI\temp\pytest...`.

Focused verification exercised all 1,491 runner cases: the first pass reported
1,488 passed / 3 failed in 725.29 seconds. Those three existing workflow-mutation
cases still targeted retained names; they were corrected to mutate active names.
The affected five-case group then passed (5 passed / 1,486 deselected).
Focused Ruff check/format and `git diff --check` passed. No certification profile
suite was run locally; `run_test_certification.py` and its tests are unchanged.


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
