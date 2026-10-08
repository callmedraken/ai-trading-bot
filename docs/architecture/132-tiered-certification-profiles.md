# Architecture 132 — Tiered certification profiles

## 2026-10-07 — Architecture 132-R2-B SOURCE ACCEPTED; historical CI gap localizes R2-B2

Architecture 132-R2-B is **SOURCE/TOPOLOGY ACCEPTED**.

Accepted implementation source:

```text
BRANCH  feature/test-suite-rationalization-132r2
HEAD    40aa7ef55a528fe7b7d9482d083ef1dcfed4dfb1
TREE    0781d9ecb3dcaf87888506e2b833fb8106f35990
CI      #291 / 37726690416 SUCCESS
```

Evidence/docs descendant:

```text
HEAD    4c89d5b968da5a26a0967766c164b49349c158f0
TREE    f795a236fb7d220e6dbc5a806c3d1ce81ddc2710
CI      #292 / 37727527551 SUCCESS
```

ChatGPT exact-source review found no correction required. No production
`src/` file changed. The checkpoint-runner authority-function edits are
coverage/registration/test-path migrations required by the split, while
production source pins and production authority chaining remain intact.
Certification ownership remains fail-closed: current split runner/certification
infrastructure is supported FULL/ROBINHOOD, the retained Architecture 128/130
runner replacement is LEGACY-required, FULL and LEGACY remain disjoint, and
unknown ownership remains rejected.

Independent relocation verification found all original test functions preserved:

```text
old checkpoint-runner functions       230
new checkpoint-runner functions       236
missing original runner functions       0

old certification-runner functions     37
new certification-runner functions     38
missing original certification funcs    0

original functions total              267
missing originals                       0
```

The six additional proof functions cover R2-B selectability, external JUnit
evidence, predecessor invocation/failure propagation, full real-chain PASS, and
retained individual verification. The repeated predecessor propagation test name
exists in two different split modules and is intentional.

R2-B terminal active source CI:

```text
CHECKPOINTS        36
TEST_PATHS         47
RUFF_PATHS        127
pytest             4,611 passed / 1 skipped / 0 failed / 0 errors
pytest wall        352.07 s
command elapsed    353.5722111 s
```

This is a 55.44% pytest-time reduction from R2-A's 790.08 s, but historical
same-workflow evidence proves the suite is still materially slower than its
pre-regression baseline.

### Historical same-workflow baseline

The comparison below uses successful non-docs **Checkpoint Source Gates** runs
whose `Verify batch source checkpoints` step actually executed; docs-only
20-40 second fast paths are excluded.

```text
run   checkpoints paths  passed  pytest_s  workflow_s
#224      32       57    4,508    215.40      266
#227      33       58    4,770    198.08      250
#229      34       59    4,926    178.74      234
#239      37       62    5,251    159.04      195
#247      37       62    5,255    150.67      200
#252      37       62    5,255    223.56      266
#256      38       62    5,291    234.87      288
#259      39       63    5,436    161.31      212
#260      39       63    5,466    220.10      265
#265      40       64    5,671    174.69      212
```

For those ten successful full gates:

```text
historical pytest median    188.41 s
historical pytest range     150.67 - 234.87 s
historical workflow median  242 s
historical workflow range   195 - 288 s

R2-B pytest               352.07 s   (+86.86% vs historical median)
R2-B workflow             406 s      (+67.77% vs historical median)
```

R2-B therefore recovered most of the R2-A/L-M explosion but is **not yet back
to the original sub-300-second CI regime**. It has fewer active cases and paths
than many historical gates, so raw test count is not the explanation.

The regression becomes visible around Architecture 133-I/J and compounds through
L/M:

```text
#265  40 checkpoints / 64 paths / 5,671 passed -> 174.69 s
#269  40 checkpoints / 64 paths / 5,680 passed -> 307.58 s
#274  41 / 65 / 5,805                         -> 324.17 s
#276  42 / 66 / 5,963                         -> 300.17 s
#279  43 / 67 / 6,154                         -> 378.51 s
#282  43 / 67 / 6,169                         -> 522.90 s
#286  44 / 68 / 6,393                         -> 696.12 s
#288  36 / 42 / 4,849                         -> 790.08 s
#291  36 / 47 / 4,611                         -> 352.07 s
```

### R2-B JUnit localization

R2-B's newly retained JUnit artifact makes the remaining cost explicit:

```text
all recorded testcase time                    344.615 s

checkpoint-runner infrastructure              323.247 s / 1,293 cases
                                               93.8% of testcase time

  Architecture 131 runner                     172.955 s / 698
  Architecture 133 L-M                         55.094 s / 129
  Architecture 133 A-G                         44.751 s / 205
  Architecture 133 H-K                         43.902 s / 153
  CI contracts                                  6.433 s / 58
  core runner                                   0.112 s / 50

all non-checkpoint-runner tests combined       ~21.368 s
```

The top 100 slowest tests account for only 77.04 s, so optimizing only the
headline L/M cases cannot recover the historical baseline. The dominant next
target is the broad Architecture-131 source-authority mutation matrix, followed
by Architecture-133 chained authority tests.

### Certification decision

R2-B deliberately changed certification inventory topology, so a **FULL
current-product certification remains required before Architecture 132-R2 is
closed**. It is intentionally deferred until R2-B2 because R2-B2 will modify the
test source again; certifying 40aa7ef now would create knowingly stale evidence
and force a duplicate broad certification. This is a selected/deferred
certification, not a waiver.

### R2-B2 frozen checkpoint — recover active authority-test efficiency

R2-B2 is the final source-only performance checkpoint before FULL certification.
It does not change product behavior, production authority, certification
ownership, or profile module topology.

1. Preserve all R2-B split files and ownership.
2. Do not delete logical test dimensions.
3. Keep production authority functions and predecessor chaining real and
   fail-closed.
4. Apply the immediate-predecessor isolation pattern already accepted for
   Architecture 133 I-M to expensive **Architecture 131 local mutation/unit
   tests** and, where independently justified by JUnit evidence, Architecture
   133 A-G local mutation/unit tests.
5. A local authority mutation test may stub only the already-separately-proven
   predecessor authority call. It must execute the real local authority layer
   under test.
6. For every isolated production chain edge preserve separate tests proving:
   - the real predecessor is invoked;
   - predecessor rejection propagates fail-closed;
   - the accepted full real chain passes.
7. Registration/workflow/order tests may be isolated only when equivalent
   dedicated real-chain integration proves the same edge. Do not silently
   convert all workflow/order coverage to mocked predecessors.
8. Do not change source/registration pins merely for performance.
9. Keep R2-A timing and R2-B JUnit evidence. Report per-module testcase time
   from the terminal JUnit artifact.
10. Timing remains diagnostic. The historical envelope is a comparison target,
    not a PASS/FAIL threshold. The desired outcome is to return routine pytest
    close to the historical 150-235 second range and end-to-end CI below roughly
    300 seconds without dropping logical coverage.
11. Do not begin R2-C legacy deletion/provenance work or R2-D parallelization.
12. After terminal-green R2-B2 exact-source review, run one fresh FULL
    certification on that final source identity; do not run FULL during
    implementation.

Real Architecture 133-M remains paused. Q133-2V is consumed/non-retryable.
Q133-3 and Q133-4 remain unauthorized.

## 2026-10-07 — Architecture 132-R2-B terminal source CI green; review pending

R2-B is implemented and ordinary-pushed on
`feature/test-suite-rationalization-132r2`.

```text
IMPLEMENTATION HEAD 40aa7ef55a528fe7b7d9482d083ef1dcfed4dfb1
IMPLEMENTATION TREE 0781d9ecb3dcaf87888506e2b833fb8106f35990
SOURCE CI           #291 / 37726690416 SUCCESS
PYTEST              4,611 passed / 1 skipped / 0 failed / 0 errors
PYTEST WALL         352.07 s
COMMAND ELAPSED     353.5722111 s
ACTIVE CHECKPOINTS  36 (reviewed sequence unchanged)
TEST_PATHS          42 -> 47
RUFF_PATHS          120 -> 127
```

All 36 authority results passed, source identity stayed stable, and production,
scheduler, provider and broker/live fields remained `NOT_RUN`. The single skip
is the existing optional `mcp.shared.auth` import in the Windows OAuth test;
the source-gate environment does not install `mcp`.

Against accepted R2-A's 790.08 s, this run's pytest wall time is 438.01 s
(55.44%) lower. Command elapsed decreased from 792.1711838 s to 353.5722111 s.
This is observed cross-run evidence, with no timing threshold or performance
claim beyond the measured runs. Splitting increases path counts while reducing
routine collection from 4,850 to 4,612 outcomes and redundant predecessor work.

The [terminal source run](https://github.com/callmedraken/ai-trading-bot/actions/runs/37726690416)
uploaded [evidence artifact 11528162705](https://github.com/callmedraken/ai-trading-bot/actions/runs/37726690416/artifacts/11528162705).
Its batch prefix is `source-gate-batch-20261008T041656.870000Z/`:
`report.json` contains command timings and authority/effect evidence;
`commands/01-pytest.stdout.txt` contains all top-100 durations; and
`pytest-results.xml` contains exact total/per-module case counts.

All 100 slowest entries are calls in supported runner infrastructure: 41 in
133-L–M, 20 in 133-H–K, 29 in Architecture 131, eight in CI, and two in 133-A–G.
The slowest three are real-chain 133-M runner ordering/registration mutations:
1.94 s duplicate, 1.93 s missing, and 1.91 s order. The validation plan records
every split module's CI and focused counts, all original test mappings, exact
unions and required-baseline migration.

All 2,003 distinct focused infrastructure cases passed; focused Ruff
check/format and diff checks passed. No FULL/ROBINHOOD/LEGACY/EXHAUSTIVE
certification was run locally. This separate docs-only checkpoint records
terminal implementation evidence and grants no source/topology or certification
acceptance. ChatGPT owns exact GitHub diff review and final certification
selection; FULL is expected after source acceptance unless exact review
establishes stronger equivalent evidence.

R2-C/R2-D have not started. No historical production source was deleted.
Real 133-M remains paused. Q133-2V remains consumed/non-retryable;
Q133-3/Q133-4 and all protected/provider/credential/scheduler/broker operations
remain unauthorized and were not run.


## 2026-10-07 — Architecture 132-R2-B implementation (source review pending)

R2-B splits test infrastructure by responsibility and isolates redundant
predecessor work in local authority mutation tests. R2-C/R2-D have not started.
The implementation does not claim ChatGPT source/topology or certification
acceptance. Terminal source CI evidence is recorded above in the separate
docs-only evidence checkpoint after implementation source CI completed.

The exact 36 active and eight retained checkpoint sequences are unchanged.
All product test/Ruff requirements retain first-seen order. All eight production
source-pin dictionaries are unchanged. All 46 authority-function ASTs preserve
their logic after accounting only for family test selection and migrated source
registration hashes. Production chaining M → L → K → J → I → H remains real.
Local I–M pin/runtime tests replace only the immediate predecessor with PASS;
workflow/order mutation tests retain the complete real predecessor chain;
separate tests prove predecessor calls, rejection propagation, and complete real
chain PASS. H mutations use the real H layer with no predecessor stub.

`COMMON_TESTS` is exactly:

```text
tests/runtime/checkpoint_runner/test_core.py
tests/runtime/checkpoint_runner/test_ci.py
```

Architecture 131, 133-A–G, 133-H–K, 133-L–M, and retained 128/130 checkpoints
select only their own runner family module in addition to that common pair.
Inventory-dependent checkpoints select only
`tests/scripts/certification_runner/test_profiles.py`; the other four
certification modules remain independently runnable FULL/ROBINHOOD contracts.
The workflow preserves `feature/test-suite-*`, its docs-only fast path, and one
serial source-gate job. Existing R2-A monotonic timing and top-100 flags are
unchanged; an external `pytest-results.xml` is additionally uploaded for exact
per-module case accounting.

| Inventory / union | Before | R2-B |
| --- | ---: | ---: |
| FULL modules | 127 | 136 |
| ROBINHOOD modules | 54 | 63 |
| LEGACY modules | 204 | 205 |
| EXHAUSTIVE modules | 331 | 341 |
| FULL required baseline | 113 | 122 |
| ROBINHOOD required baseline | 40 | 49 |
| Active TEST_PATHS | 42 | 47 |
| Active RUFF_PATHS | 120 | 127 |
| Retained TEST_PATHS | 27 | 29 |
| Retained RUFF_PATHS | 32 | 36 |

Path counts rise because files are split; no speedup is inferred from path
counts. The required legacy replacement is explicitly pinned in
`LEGACY_REQUIRED_MODULES` for LEGACY/EXHAUSTIVE selection. Unknown files in the
new runner infrastructure namespace fail closed instead of inheriting the broad
historical runtime family. FULL/LEGACY remain disjoint, their union equals
EXHAUSTIVE, and ROBINHOOD remains a subset of FULL.

All 2,003 distinct final focused cases passed; Ruff check/format and diff checks
passed. The validation plan records exact commands, module counts and every
original test relocation. The original 1,941 collected cases are accounted for
in that split inventory. The 36 additional required-baseline mutation cases exercise the expanded
replacement baselines. Original missing/changed pins, registration, workflow,
ordering, callback/capability, wrong source/authority configuration, and
predecessor rejection dimensions remain covered.

The requested `F:\AI\ai-trading-bot.venv\Scripts\python.exe` is absent.
Focused checks use the existing `F:\AI\ai-trading-bot\.venv\Scripts\python.exe`
and fresh external `F:\AI\temp\pytest-r2b-*` basetemps. No certification
profile run or protected host/provider/credential/scheduler/broker operation
was performed. Real 133-M remains paused; Q133-2V is consumed/non-retryable;
Q133-3/Q133-4 remain unauthorized.

Next owner: ChatGPT for exact GitHub diff review and source acceptance, then
final certification selection. FULL current-product certification is expected
because inventory topology changed, unless exact review establishes stronger
equivalent evidence. Do not begin R2-C/R2-D or resume real 133-M here.


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

## Revision 132-R1: supported product versus legacy compatibility

Architecture 132-R1 revises this architecture rather than introducing
Architecture 133. It explicitly changes the meaning of FULL while preserving
the accepted Robinhood contract:

- FULL = all CURRENTLY SUPPORTED functionality.
- LEGACY = retained retired architecture.
- EXHAUSTIVE = every test still present in the repository, preserving the
  original Architecture 132 all-repository FULL behavior.
- ROBINHOOD = the accepted Architecture 131 product and direct shared-core
  subset of FULL.

The CLI accepts `--profile full`, `--profile robinhood`, `--profile legacy`,
and `--profile exhaustive`. The default remains FULL, including when the option
is omitted. Existing callers wanting the original all-repository scope must
now explicitly use `--profile exhaustive`; default invocations intentionally
adopt current-supported scope. Unknown profiles are rejected.

At startup HEAD `2577225dafcff2d616fcbf018d7045aebaab1ff5`, tree
`e0af9fb359872c77ab08248e9a101a281a357fa9`:

| Profile | Modules | Exact lanes |
| --- | ---: | --- |
| full | 113 | broad-1, broad-2 |
| robinhood | 40 | robinhood-1, robinhood-2 |
| legacy | 204 | legacy-1, legacy-2, serial |
| exhaustive | 317 | broad-1, broad-2, serial |

Counts describe this tree, not hard limits on future admitted additions.
The FULL 113-module and Robinhood 40-module required baselines below remain
frozen so deletion/renaming cannot silently reduce certification.

## 132-R1 accepted certification — 2026-10-04

Architecture 132-R1 is **CERTIFIED** after exact source review, source-gate CI,
focused implementation verification, and final FULL-supported certification.

Certified source identity:

```text
BRANCH  feature/robinhood-review-paper-side-foundation
PARENT  2577225dafcff2d616fcbf018d7045aebaab1ff5
HEAD    91cafa03f9244523fc45df0716427402028257a7
TREE    cb044a9014132b4e73310e19da5dfeba0fd89c3b
SUBJECT fix: separate supported and legacy certification
CI      #178 / 37238601866 SUCCESS
```

Focused implementation verification: 450 passed; Ruff check, Ruff format
`--check`, `git diff --check`, and `git diff --cached --check` all PASS.

Final FULL-supported certification:

| Lane | Modules | Cases | Passed | Skipped | Failed | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| broad-1 | 55 | 1,985 | 1,985 | 0 | 0 | 0 |
| broad-2 | 58 | 1,709 | 1,709 | 0 | 0 | 0 |
| Total | 113 | 3,694 | 3,694 | 0 | 0 | 0 |

```text
profile: full
wall 201.655 s
ARCH132_R1_FULL_CERTIFICATION_EXIT=0
ARCH132_R1_FULL_CERTIFICATION=PASS
```

Evidence:

```text
F:\AI\temp\pytest\certification-evidence-a1860dc18fac474ba2fd9e163eaba684
```

Worktree/index remained clean after certification. This docs-only closeout
changes no executable source; no second broad certification is required after
accepted docs-only review.

The accepted certification also closes 131-S: source HEAD
`69327a7d5fbea7499329902ff96fd98e77a62591`, tree
`8e39547005c320387ef231c8dfd5e914d2f02322`, was accepted with CI
#176 / 37235257282 SUCCESS. Its executable source is unchanged in the certified
132-R1 descendant; no standalone second 131-S certification was required.

At the certified tree, final profile counts remain FULL 113 (default),
Robinhood 40, LEGACY 204, and EXHAUSTIVE 317. The required subset/disjoint/union
invariants hold, and unknown ownership fails closed before profile selection.
The historical five-module serial lane remains exclusive to LEGACY/EXHAUSTIVE.
Research/backtesting/strategy/portfolio/analytics/shared deterministic core and
Architecture 131 remain supported; pre-Robinhood GUI, D10, Windows authority,
Paper-v2/personal-desktop, and Alpaca operational capture remain legacy.

Production/live real-money placement remains **NO-GO**. Certification does not
authorize provider/broker effects. 131-Q PREPARE remains a protected read-only
provider boundary requiring fresh explicit authorization. 131-Q EXECUTE remains
a separate protected boundary requiring fresh explicit authorization after
accepted PREPARE. `READY_TO_PROCEED` is never execution authorization.
131-S adds schedule authority only, not provider/execution authority; 132-R1 is
test/workflow infrastructure only. The protected operational sequence remains
separate and unchanged; this closeout grants no new authority.

## Tier policy and handoff

```text
FOCUSED
-> SOURCE-GATE CI
-> ROBINHOOD when appropriate
-> FULL at coherent current-product boundaries
-> LEGACY/EXHAUSTIVE only when explicitly relevant
-> PROTECTED separately authorized
```

| Level | Trigger |
| --- | --- |
| FOCUSED | Every implementation/correction; Codex runs affected tests and focused checks. |
| SOURCE-GATE CI | Every pushed registered checkpoint; retain existing registered GitHub source-gate batching. |
| ROBINHOOD | When ChatGPT declares a coherent Architecture 131 integration boundary; before protected Robinhood qualification; after material changes to shared domain/execution/ledger/risk foundations used by Architecture 131. |
| FULL | After certification-topology changes; at coherent current-product boundaries; before major develop/release integration or consequential production/live-readiness transitions; after sufficiently broad supported shared-core changes; or when ChatGPT explicitly determines accumulated checkpoints warrant current-product regression. |
| LEGACY / EXHAUSTIVE | Only when explicitly justified by legacy architecture changes, interpreter/dependency migrations spanning both eras, broad repository restructuring, deliberate legacy removal, or backward compatibility investigation. |
| PROTECTED | Always separate fresh authorization. |

FULL is not mechanically tied to every accepted source checkpoint or
Architecture 131 letter. Normal current-product certification does not require
LEGACY or EXHAUSTIVE. ChatGPT owns exact source review, acceptance, and the
certification-tier decision. The normal handoff remains:

```text
implementation + focused checks
-> exact-file commit/push
-> ChatGPT exact GitHub commit/tree review
-> source acceptance
-> appropriate certification tier
-> docs closeout (PROJECT_STATUS + HANDOFF after certification acceptance)
```

Local patch-first review is fallback-only. This revision modifies neither
`scripts/checkpoint_runner.py` nor `.github/workflows/checkpoint-source-gates.yml`.
No actual certification profile is run during bounded implementation.

## Supported FULL ownership

Whole-directory families (including descendant test modules):

```text
tests/analytics/
tests/backtesting/
tests/domain/
tests/execution/
tests/experiments/
tests/integration/
tests/ledger/
tests/market_calendar/
tests/multi_backtesting/
tests/optimization/
tests/portfolio/
tests/portfolio_analytics/
tests/rebalancing/
tests/review_paper/
tests/risk/
tests/robinhood_mcp/
tests/simulation/
tests/strategies/
```

Reviewed exact supported tests in mixed directories and infrastructure/root:

```text
tests/cli/test_create_research_session_bundle.py
tests/cli/test_historical_experiment.py
tests/cli/test_historical_experiment_pairwise_config.py
tests/cli/test_historical_experiment_pairwise_serialization.py
tests/cli/test_historical_experiment_pareto_config.py
tests/cli/test_historical_experiment_pareto_serialization.py
tests/cli/test_historical_experiment_report_serialization.py
tests/cli/test_optimized_simulation.py
tests/cli/test_research_session_archive.py
tests/cli/test_research_session_archive_cli.py
tests/cli/test_research_session_bundle.py
tests/cli/test_research_session_manifest.py
tests/cli/test_research_session_restore.py
tests/cli/test_restore_research_session_archive.py
tests/cli/test_rolling_historical.py
tests/cli/test_verify_research_session_manifest.py
tests/cli/test_walk_forward_aggregate_config.py
tests/cli/test_walk_forward_aggregate_serialization.py
tests/cli/test_walk_forward_experiment.py
tests/cli/test_walk_forward_experiment_config.py
tests/cli/test_walk_forward_experiment_serialization.py
tests/cli/test_walk_forward_stability_config.py
tests/cli/test_walk_forward_stability_serialization.py
tests/market_data/test_csv_historical_provider.py
tests/market_data/test_historical_models.py
tests/market_data/test_multi_symbol_models.py
tests/market_data/test_multi_symbol_provider.py
tests/runtime/test_checkpoint_runner.py
tests/scripts/test_create_walk_forward_research_bundle.py
tests/scripts/test_research_session_archive_scripts.py
tests/scripts/test_run_backtest.py
tests/scripts/test_run_historical_experiment.py
tests/scripts/test_run_rolling_historical_simulation.py
tests/scripts/test_run_test_certification.py
tests/scripts/test_run_walk_forward_experiment.py
tests/test_config.py
```

Root `tests/test_robinhood_*.py` is also supported. New tests in supported
whole-directory families and matching root Robinhood tests enter FULL
automatically. The mixed research CLI, market-data, and scripts namespaces
use exact ownership; new files there require an explicit reviewed support
classification, even when their names suggest research. Unrelated root test
names are likewise unclassified.

The frozen current FULL required baseline is exactly 113 modules:

```text
tests/analytics/test_analyzer.py
tests/backtesting/test_backtest_engine.py
tests/backtesting/test_backtest_models.py
tests/cli/test_create_research_session_bundle.py
tests/cli/test_historical_experiment.py
tests/cli/test_historical_experiment_pairwise_config.py
tests/cli/test_historical_experiment_pairwise_serialization.py
tests/cli/test_historical_experiment_pareto_config.py
tests/cli/test_historical_experiment_pareto_serialization.py
tests/cli/test_historical_experiment_report_serialization.py
tests/cli/test_optimized_simulation.py
tests/cli/test_research_session_archive.py
tests/cli/test_research_session_archive_cli.py
tests/cli/test_research_session_bundle.py
tests/cli/test_research_session_manifest.py
tests/cli/test_research_session_restore.py
tests/cli/test_restore_research_session_archive.py
tests/cli/test_rolling_historical.py
tests/cli/test_verify_research_session_manifest.py
tests/cli/test_walk_forward_aggregate_config.py
tests/cli/test_walk_forward_aggregate_serialization.py
tests/cli/test_walk_forward_experiment.py
tests/cli/test_walk_forward_experiment_config.py
tests/cli/test_walk_forward_experiment_serialization.py
tests/cli/test_walk_forward_stability_config.py
tests/cli/test_walk_forward_stability_serialization.py
tests/domain/test_market.py
tests/domain/test_orders.py
tests/domain/test_positions.py
tests/domain/test_proposals.py
tests/execution/test_execution_models.py
tests/execution/test_order_engine.py
tests/execution/test_paper_fill_application.py
tests/execution/test_paper_fills.py
tests/execution/test_paper_submission.py
tests/execution/test_portfolio_orders.py
tests/experiments/test_comparison.py
tests/experiments/test_grid.py
tests/experiments/test_historical.py
tests/experiments/test_pairwise.py
tests/experiments/test_pareto.py
tests/experiments/test_report.py
tests/experiments/test_walk_forward.py
tests/experiments/test_walk_forward_analytics.py
tests/experiments/test_walk_forward_stability.py
tests/integration/test_walk_forward_e2e.py
tests/integration/test_walk_forward_research_archive_e2e.py
tests/integration/test_walk_forward_research_bundle_e2e.py
tests/integration/test_walk_forward_research_restore_e2e.py
tests/integration/test_walk_forward_research_transport_e2e.py
tests/ledger/test_checkpoint_state.py
tests/ledger/test_initialization.py
tests/ledger/test_ledger.py
tests/ledger/test_models.py
tests/market_calendar/test_calendar_models.py
tests/market_calendar/test_nyse_calendar.py
tests/market_data/test_csv_historical_provider.py
tests/market_data/test_historical_models.py
tests/market_data/test_multi_symbol_models.py
tests/market_data/test_multi_symbol_provider.py
tests/multi_backtesting/test_engine.py
tests/multi_backtesting/test_models.py
tests/multi_backtesting/test_strategy_contract.py
tests/optimization/test_cpu_mean_cvar.py
tests/portfolio/test_historical_scenarios.py
tests/portfolio/test_mean_cvar.py
tests/portfolio/test_models.py
tests/portfolio/test_optimized_targets.py
tests/portfolio/test_optimizer_protocol.py
tests/portfolio/test_scenarios.py
tests/portfolio_analytics/test_analyzer.py
tests/portfolio_analytics/test_models.py
tests/portfolio_analytics/test_optimized_simulation.py
tests/rebalancing/test_models.py
tests/rebalancing/test_planner.py
tests/rebalancing/test_proposals.py
tests/review_paper/test_forward_preview.py
tests/review_paper/test_intent_bridge.py
tests/review_paper/test_nyse_published_regular_sessions.py
tests/review_paper/test_performance.py
tests/review_paper/test_prepare_qualification.py
tests/review_paper/test_risk_context.py
tests/review_paper/test_risk_price_acquisition.py
tests/review_paper/test_risk_prices.py
tests/review_paper/test_session_admission.py
tests/review_paper/test_store.py
tests/review_paper/test_supervised_forward_paper.py
tests/risk/test_manager.py
tests/risk/test_orchestration.py
tests/risk/test_risk_models.py
tests/robinhood_mcp/test_account_resolution.py
tests/robinhood_mcp/test_adapter.py
tests/robinhood_mcp/test_sdk_transport.py
tests/robinhood_mcp/test_windows_oauth.py
tests/runtime/test_checkpoint_runner.py
tests/scripts/test_create_walk_forward_research_bundle.py
tests/scripts/test_research_session_archive_scripts.py
tests/scripts/test_run_backtest.py
tests/scripts/test_run_historical_experiment.py
tests/scripts/test_run_rolling_historical_simulation.py
tests/scripts/test_run_test_certification.py
tests/scripts/test_run_walk_forward_experiment.py
tests/simulation/test_optimized_paper_portfolio.py
tests/simulation/test_paper_portfolio.py
tests/simulation/test_rolling_historical.py
tests/strategies/test_moving_average.py
tests/test_config.py
tests/test_robinhood_forward_paper_cycle.py
tests/test_robinhood_live_qualification_verifier.py
tests/test_robinhood_paper_cycle.py
tests/test_robinhood_paper_operator.py
tests/test_robinhood_paper_pipeline.py
tests/test_robinhood_prepare_qualification_verifier.py
```

## Preserved Robinhood ownership

Robinhood ownership remains exactly the accepted direct-file patterns:

```text
tests/domain/test_*.py
tests/execution/test_*.py
tests/ledger/test_*.py
tests/risk/test_*.py
tests/review_paper/test_*.py
tests/robinhood_mcp/test_*.py
tests/test_robinhood_*.py
tests/runtime/test_checkpoint_runner.py
tests/scripts/test_run_test_certification.py
```

New matching direct-directory or root files are admitted automatically. FULL
owns descendant modules recursively, but this revision does not expand
Robinhood's direct-directory contract. All current Architecture 131 registered
test modules remain in Robinhood and therefore in FULL. Tests inspect
registrations to prove coverage; production certification code does not depend
on private checkpoint-runner helpers.

The preserved 40-module required baseline is:

```text
tests/domain/test_market.py
tests/domain/test_orders.py
tests/domain/test_positions.py
tests/domain/test_proposals.py
tests/execution/test_execution_models.py
tests/execution/test_order_engine.py
tests/execution/test_paper_fill_application.py
tests/execution/test_paper_fills.py
tests/execution/test_paper_submission.py
tests/execution/test_portfolio_orders.py
tests/ledger/test_checkpoint_state.py
tests/ledger/test_initialization.py
tests/ledger/test_ledger.py
tests/ledger/test_models.py
tests/review_paper/test_forward_preview.py
tests/review_paper/test_intent_bridge.py
tests/review_paper/test_nyse_published_regular_sessions.py
tests/review_paper/test_performance.py
tests/review_paper/test_prepare_qualification.py
tests/review_paper/test_risk_context.py
tests/review_paper/test_risk_price_acquisition.py
tests/review_paper/test_risk_prices.py
tests/review_paper/test_session_admission.py
tests/review_paper/test_store.py
tests/review_paper/test_supervised_forward_paper.py
tests/risk/test_manager.py
tests/risk/test_orchestration.py
tests/risk/test_risk_models.py
tests/robinhood_mcp/test_account_resolution.py
tests/robinhood_mcp/test_adapter.py
tests/robinhood_mcp/test_sdk_transport.py
tests/robinhood_mcp/test_windows_oauth.py
tests/runtime/test_checkpoint_runner.py
tests/scripts/test_run_test_certification.py
tests/test_robinhood_forward_paper_cycle.py
tests/test_robinhood_live_qualification_verifier.py
tests/test_robinhood_paper_cycle.py
tests/test_robinhood_paper_operator.py
tests/test_robinhood_paper_pipeline.py
tests/test_robinhood_prepare_qualification_verifier.py
```

## Reviewed legacy ownership and EXHAUSTIVE

At the current tree:

| Legacy population | Modules |
| --- | ---: |
| tests/acceptance/ | 1 |
| tests/cli/ | 34 |
| tests/gui/ | 34 |
| tests/market_data/ | 8 |
| tests/runtime/ | 126 |
| tests/scripts/ | 1 |
| Total | 204 |

Reviewed whole legacy namespaces are `tests/acceptance/`, `tests/gui/`, and
`tests/runtime/`, including descendants, with the exact supported
`tests/runtime/test_checkpoint_runner.py` exception. New tests in these
namespaces remain legacy by ownership until explicitly reclassified.

Mixed CLI/market-data/scripts legacy ownership is frozen to these exact files:

```text
tests/cli/test_checkpoint_lineage.py
tests/cli/test_checkpoint_transition.py
tests/cli/test_daily_snapshot_capture.py
tests/cli/test_daily_snapshot_config.py
tests/cli/test_paper_operation_config.py
tests/cli/test_paper_operation_execution.py
tests/cli/test_paper_operation_failed_receipt.py
tests/cli/test_paper_operation_inspection.py
tests/cli/test_paper_operation_receipt_output.py
tests/cli/test_pd2d1_b1_readonly_diagnostic.py
tests/cli/test_pd2d1_first_paper_qualification.py
tests/cli/test_pd2d1_p1_readonly_diagnostic.py
tests/cli/test_pd2d1_preparation_readonly_diagnostic.py
tests/cli/test_pd2d2_first_paper_execution.py
tests/cli/test_pd2d2_post_mutation_reconciliation.py
tests/cli/test_pd3_read_only_recovery_launcher.py
tests/cli/test_pd3_read_only_recovery_validation.py
tests/cli/test_pd4_operator_observability_snapshot.py
tests/cli/test_pd4_operator_observability_source_launcher.py
tests/cli/test_pd4_read_only_decision_qualification.py
tests/cli/test_pd4_read_only_decision_reconciliation.py
tests/cli/test_pd4_read_only_settlement_qualification.py
tests/cli/test_pd4_read_only_settlement_reconciliation.py
tests/cli/test_pd4_read_only_single_deferred_settlement_qualification.py
tests/cli/test_pd4_read_only_single_deferred_settlement_reconciliation.py
tests/cli/test_pd4_read_only_unattended_validation.py
tests/cli/test_pd4_single_deferred_settlement_execution.py
tests/cli/test_pd4_unattended_settlement_execution.py
tests/cli/test_personal_desktop_unattended_capture_warmup_launcher.py
tests/cli/test_personal_desktop_unattended_decision_publication_launcher.py
tests/cli/test_personal_desktop_unattended_paper_launcher.py
tests/cli/test_production_daily_snapshot_capture.py
tests/cli/test_verified_snapshot_paper_cycle.py
tests/cli/test_windows_authority.py
tests/market_data/test_alpaca_daily_snapshot.py
tests/market_data/test_alpaca_http.py
tests/market_data/test_daily_snapshot_acceptance.py
tests/market_data/test_daily_snapshot_identity.py
tests/market_data/test_daily_snapshot_models.py
tests/market_data/test_daily_snapshot_provider.py
tests/market_data/test_daily_snapshot_serialization.py
tests/market_data/test_daily_snapshot_verification.py
tests/scripts/test_capture_daily_market_snapshot.py
```

Legacy includes retired Alpaca/daily-snapshot capture, checkpointed
verified-snapshot/old PaperAccount operation, PD2/PD3/PD4 operational CLIs,
personal-desktop Paper-v2, D10 scheduler/deployment/recovery, Windows
transactional/effectful capture authority, Architecture-77/78 native acceptance,
and the current pre-Robinhood GUI implementation.

GUI remains a future product goal. Its existing implementation is legacy
because it is tied to the retired operational artifact/runtime model; a future
Robinhood-integrated GUI milestone must explicitly reclassify or replace it.
D10/Windows/Paper-v2/Alpaca operational paths are historical compatibility,
not current product certification requirements.

LEGACY is the complement of FULL only after every discovered module has
reviewed supported or legacy ownership. Unknown ownership never defaults to
legacy. EXHAUSTIVE equals complete `tests/**/test_*.py` discovery over that
admitted repository and is the backward compatibility/repository archaeology
gate. It is not routine current-product certification.

## Fail-closed invariants and lanes

Every profile first admits the full repository classification and both required
baselines. Missing/renamed required FULL or Robinhood modules stop all profiles.
A wholly unknown namespace, an unknown test in a mixed namespace, overlapping
ownership, duplicate modules, or an invalid support partition fails closed and
requires an explicit support-status decision.

Require:

```text
robinhood subset of full
full intersection legacy == empty
full union legacy == exhaustive
exhaustive == complete discovered repository inventory
```

All profiles use the existing deterministic descending-file-size balancing,
with stable path/lane ties and whole-file allocation. FULL and Robinhood have
exactly two nonempty balanced lanes and no historical serial lane. LEGACY and
EXHAUSTIVE retain the exact historical five-module serial allowlist:

```text
tests/runtime/test_windows_transactional_capture_authority.py
tests/runtime/test_windows_authority_schema.py
tests/runtime/test_windows_authority.py
tests/runtime/test_windows_effectful_capture_native_acceptance.py
tests/acceptance/test_windows_authority_provisioning_acceptance.py
```

Architecture-77 remains serial; unrestricted parallel safety is not established.
Both non-serial compatibility lanes must be nonempty. All lanes are checked
before any pytest starts; an empty module list must never trigger accidental
repository-wide collection. Partitions must be complete/disjoint for the
selection, and success requires the exact expected profile-specific lane names,
successful exits/JUnit validation, unchanged source identity, and successful
whole-repository static checks.

## Source checks and evidence compatibility

All profiles preserve exact worktree/branch/HEAD/tree verification, local
tracking-ref and live-origin proof, clean admission and post-test/final source
verification, protected-opt-in rejection, unique external basetemp, timeouts,
JUnit validation, and evidence outside the worktree. Actual runs require
`F:\AI\temp\pytest`. `--plan` verifies admission and records topology without
launching pytest or static checks.

Every profile retains whole-repository post-test static checks:

```text
ruff check --no-cache .
ruff format --check --no-cache .
git diff --check
```

`results.json` preserves `profile`, `repository_inventory`, `selected_inventory`,
`excluded_inventory`, `lanes`, source and result fields. Existing `inventory`
remains the flattened selected lane inventory.

`inventory.json` preserves `all` and `repository` as complete repository
inventory, with `profile`, `selected`, `excluded`, `broad`, `serial`, and `lanes`.
Only EXHAUSTIVE has `selected == all`. FULL selects supported modules,
Robinhood selects its supported subset, and LEGACY selects the admitted
supported complement. FULL/Robinhood retain empty `serial` metadata without
an empty process.

Both evidence files add `classification` with policy `architecture-132-r1`,
`supported_inventory`, `legacy_inventory`, all four `profile_counts`, and
reviewed `ownership` (whole directories, exact module lists, root pattern,
and Robinhood infrastructure). This makes retained support status auditable
independently of the selected profile.

## Protected boundary and focused verification

All profiles reject the same `PROTECTED_OPT_INS`, even false-looking values.
No profile grants or invokes native Windows acceptance opt-ins, provider access,
Robinhood calls, OAuth interaction, broker effects, or production effects.
PROTECTED always requires separate fresh authorization.

Implementation verifies only `tests/scripts/test_run_test_certification.py`,
Ruff check/format on changed Python files, and Git diff checks. Tests construct
independent baseline expectations and prove counts, support invariants, new
owned-file admission, missing/renamed baselines, unknown ownership rejection,
all lane sets, protected rejection, static commands, source identity, plan-only
behavior, and evidence semantics. The final FULL-supported certification above
is accepted; canonical status/handoff documentation records this docs-only
closeout. Executable source is unchanged, so accepted docs-only review requires
no second broad certification.
