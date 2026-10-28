# Architecture 132 — Tiered certification profiles

Current infrastructure ownership and prepublication admission are governed by
[Architecture 134 authority separation](134-current-authority-historical-decoupling.md).
R3M/R3N exact overlays below preserve historical evidence; they do not own current
mutable test/workflow bytes. General admit uses the shared FEATURE and
PROSPECTIVE_DEVELOP evaluator before publication. Canonical mapped profiles
remain GitHub-owned. Required baselines are unchanged; current FULL placement
is corrected by 146-B1-C4 below.

## Current FULL correction — Architecture 146-B1-C4

Current FULL uses exactly seven deterministic nonempty whole-module lanes,
`broad-1` through `broad-7`, with no serial lane. Its sole current frozen timing
map comes from canonical FULL #784 / run `40689830781`, attempt 1: 209 modules,
14,722 cases, 14,716 passed, six skipped and zero failed/errors. Every raw module
total is positive; raw and canonical totals both equal 1,749,660 ms. Sorted
compact JSON timing-map SHA256:
`a3b23aab842af7bb042c848b58d8aa0f17704d40937b89d85a3e11c524935710`.

The existing descending-time / ascending-path / lowest-total / lowest-index
greedy algorithm yields module counts 29/29/30/30/30/31/30 and lane totals
249953/249953/249950/249952/249952/249951/249949 ms. Six lanes modeled about
291.612 seconds before collection/process overhead, leaving inadequate room
under the unchanged 300-second ceiling. Runtime acceptance still requires
canonical FULL wall strictly below 300 seconds. There are no lane pins, runtime
JUnit reads or adaptive history. Future owned modules retain the 1000-ms fallback.
The exact counts/order differ from the planning approximation; they follow
from the frozen map and existing algorithm, with the reviewed 249.953-second maximum.

ROBINHOOD remains four lanes; LEGACY/EXHAUSTIVE and required baselines are unchanged.

Classification: `CERTIFICATION_TOPOLOGY_CAPACITY_DEFECT / STALE_FULL_TIMING_AUTHORITY`.
R3L's older six-lane map and 1,231,440-ms total below are frozen historical
Architecture 132 evidence, superseded as current FULL authority. #782, #783 and
#784 remain immutable. This candidate is pending terminal CI and ChatGPT exact-
source acceptance; no integration or protected effect follows. See the
[C4 validation boundary](../validation/arch146-b-historical-research-acquisition-custody-plan.md#146-b1-c4--current-full-timing-capacity-correction).

## Architecture 132-R3M — predecessor exact develop certification reuse

A develop push retains mandatory source-static classification, exact local
HEAD/tree/branch and origin admission, fast-forward ancestry proof, full-batch
static/authority verification, workflow topology checks and terminal source-gates.
Only redundant broad execution may be skipped. Reuse is optional and requires
one terminal-success push run from an exact registered checkpoint in the reviewed
feature/robinhood-*, feature/research-* or feature/test-suite-* family, for the
identical commit SHA and tree in the exact repository/workflow. Reusable feature
certification is limited to the original push-triggered first attempt: the run,
run detail and every required job must report `run_attempt == 1`. An unchanged-
source rerun, including a coherent successful attempt 2, is never reusable
integration evidence. Source-static, active-tests, source-gates and the
explicitly checkpoint/profile-named canonical certification job and its
execution/hygiene steps must all have succeeded in that same first attempt. The
source-owned profile mapping remains authoritative.

GitHub Actions metadata is read with job-scoped actions:read. The lookup uses
bounded complete metadata pages and records the selected run/attempt/jobs in
source-static's develop-integration-reuse.json evidence. Missing, malformed,
truncated, unavailable, stale or ambiguous evidence means ordinary four-shard
develop broad fallback. SHA changes, including tree-equivalent commits, are
ineligible. Caller-supplied run IDs and artifact names are not certification proof.
Older runs without the explicit checkpoint/profile job binding also fall back.

Feature FULL/ROBINHOOD execution, active source-only checkpoints, docs-only and
pull_request routing remain unchanged. FULL retains six timing-aware lanes;
ROBINHOOD retains four; neither has a serial lane. The 300-second ceilings,
inventories and predecessor authority pins stay intact through an additive R3M
overlay. This checkpoint's reviewed test-suite branch uses normal broad source
CI; no new feature certification mapping or local canonical run is introduced.
ChatGPT owns exact-source review and any selected certification before integration.
No provider, holdout, ACL, scheduler, runtime, broker or live authority follows.

## Architecture 132-R3N — workflow throughput and current-contract consolidation

R3N's initial implementation is preserved at the exact develop integration
identity below. It remains pending ChatGPT exact-source acceptance; terminal
R3N CI #729 / run `40238669278` / attempt 1 succeeded and is preserved
unchanged. Architecture 132-R3N corrective C1 is the separately named source
correction for the two general-throughput gaps found during that review.

    HEAD 029d72e81a1589e8bd3b3134531682f500087810
    TREE ea120b292a9252e3234ab4db8b64ff2c89851fea

R3M's preserved feature chronology is #722 failure, #723 success, #724
failure, #725 failure, #726 failure and #727 terminal success. Develop
integration #728 / `40233946706` / attempt 1 succeeded, and primary local
develop was reconciled to the same exact identity before R3N work began. The
final bootstrap broad execution in #728 is preserved because R3M recognized
only mapped canonical feature evidence; it is not a requirement for an exact
future broad feature gate.

R3N keeps R3M's fail-closed develop admission and exact mapped FULL/ROBINHOOD
reuse, and additionally admits exact successful broad feature source-gate
evidence in both current broad shapes: registered ACTIVE plus the four broad
shards, or unregistered FULL plus the four broad shards. Broad reuse requires
the same repository ID/full name, active workflow ID/path/name, push event,
original attempt (`run_attempt == 1`), exact SHA/tree, admitted feature branch
family, terminal success, exact route-specific job topology, successful
source-static/source-gates and required execution/hygiene steps, and one unique
qualifying run. Missing, malformed, truncated, ambiguous or unavailable
evidence, unexpected active/certification routing, and all attempt-2-or-later
runs fall back to the normal broad develop route. Artifact names are not proof.

Corrective chronology remains immutable: #729 / `40238669278` SUCCESS,
C1 #730 / `40265181160` FAILURE, C2 #731 / `40265822617` FAILURE, and
C3 #732 / `40266767289` SUCCESS (all original attempt 1). C4 follows C3
source `711c45f46efdba9b490d8e7e138879e432cfd9b7`, tree
`bc517481d0cd1ca0a149402ec9080a8f392ee48e`, and is SOURCE ACCEPTED / INTEGRATED at
`61836d6adadf25907c0347d42012bc4200a179ff`, tree
`eabbf166db2d14ce7fed603df3f8b6762394e3c7`. Feature #733 / `40271136792`
and develop #734 / `40271802280` both succeeded on attempt 1. #734 reused
`exact_feature_broad_source_gate`; no duplicate broad execution occurred.

C4's exact skipped-job identity and rejection rules are defined once in the
[current R3N workflow contract](../AI_DEVELOPMENT_WORKFLOW.md#architecture-132-r3n--workflow-throughput-and-current-contract-consolidation).
The current proof binds that source-owned name to the reviewed workflow and
retains exact job-set equality, route-specific conclusions and attempt-1 checks.
Its additive authority layer preserves all R3M/R3N/C1/C2/C3 literals.

The current non-effectful pre-publication admission is the GENERAL ordinary-
feature gate `ops.ps1 admit`, not an R3N-only gate. It performs a read-only
remote identity check against the exact current `origin/develop` commit/tree,
requires a clean strict descendant in one reviewed feature family and a
nonempty feature diff, then checks changed-path classification, diff/Ruff
checks, current authority and workflow topology, inventory/profile
reconciliation, and nonempty FULL/ROBINHOOD/LEGACY/EXHAUSTIVE lane
construction. It does not reset, rebase, merge, repair or rewrite source
history; it runs only the small current profile/lane/CI contract tests and does
not run protected effects, provider/broker/live paths, canonical
FULL/ROBINHOOD, or the broad checkpoint union. Current count/topology assertions live in
`tests/scripts/certification_runner/test_profiles.py`,
`test_lanes.py`, and `tests/runtime/checkpoint_runner/test_ci.py`. Historical
Architecture-133/134 tests retain predecessor, authority, and incident
evidence without re-owning current counts or workflow AST merely because
current source changed.

One logical checkpoint receives one atomic commit/push and one CI admission.
Terminal-red evidence is retained. A reproducible bounded mechanical
correction is separately named and must pass the complete focused/local
pre-publication gate before its new atomic push; Codex continues across such
corrections until terminal green without an arbitrary C1/C2/C3 cap. Semantic,
security, authority, protected-effect, unexpected-state, non-reproducible or
material-scope failures stop for ChatGPT review. No provider, holdout, ACL,
scheduler, runtime, broker or live authority follows R3N.

## Current accepted closeout — Architecture 132-R3L

Architecture 132-R3L is SOURCE/CERTIFICATION ACCEPTED and integrated. The
accepted/certified executable identity inherited by D1S3 is:

    HEAD a6b6791db9237e4df6b0768ba1013d30052d00a7
    TREE 7dcd80ce63ffcf188621d8149779c08721aaceb4
    parent / accepted D1S3-R4 e515f2d4b8f75ee04b95f7e89162e37c7890e0a4

The successful canonical six-lane FULL covered all 198 selected modules exactly
once: 13,145 cases, 13,142 passed, three explicit symlink-capability skips, zero
failed/errors, 240.311 seconds wall and 59.689 seconds headroom under the
unchanged 300-second ceiling. The D1S3 branch was then fast-forwarded to this
exact tree; mapped Checkpoint Source Gates run 40038165748 attempt 1 passed
source-static, active tests, canonical four-lane ROBINHOOD and source-gates.
Develop integration run 40039433032 attempt 1 also completed SUCCESS.

The R3L section below intentionally preserves its pre-acceptance design and
evidence chronology. Statements there that merge remained blocked or FULL was
pending are historical, not current authority.


## Architecture 132-R3L — six-lane current-local FULL topology

R3L is the certification-only successor of ChatGPT SOURCE ACCEPTED D1S3-R4
HEAD e515f2d4b8f75ee04b95f7e89162e37c7890e0a4 / tree
ee326a61a87f543e85a00ec162bbf990bf17e507. Its one fresh four-lane FULL
was functionally passing (13,131 passed, 3 symlink-capability skips, zero
failures/errors across 198 modules) but failed the unchanged 300-second
ceiling at 356.885 seconds. R4 product source stays accepted; merge remains
blocked pending exact R3L source review and one successful six-lane FULL.

The sole current-local FULL timing authority is the preserved R4 evidence:
F:\AI\temp\certification\arch134-d1s3-r4-full-86ff71accd8f4c468c9807361333c795.
All four lane inventories reconcile to exactly 198 unique selected modules
and 1,231,439 raw testcase milliseconds. Only
tests/domain/test_proposals.py measured zero. It normalizes to 1 ms before
source freezing, producing 198 positive tuple-pair entries totaling
1,231,440 ms. Sorted compact JSON timing-map SHA256:
65e9c1cc30d09d33db08f70c93be354ef5d3746ea45ef460467848f9f42998f9.
This supersedes the previous active FULL table (1,149,907 ms); there is one
active FULL map, with the unchanged 1000-ms future-module fallback.

Four lanes have a raw testcase lower bound of 307.85975 seconds and cannot
meet the ceiling. Five lanes were modeled only: 246.288 seconds per lane,
with the reported child-work lower bound 267.9152 seconds and insufficient
credible contention margin. Six lanes are selected directly, without a
four/five/seven-lane runtime alternative. Their exact module counts are
32/32/33/33/34/34, each modeled at 205240 ms. The conservative pre-edit bound
205240 + 81674 = 286914 ms passes with 13086 ms remaining. This is a design
admission check; actual runtime acceptance remains wall strictly <300 seconds.

FULL now uses exactly broad-1 through broad-6, six deterministic nonempty
whole-module lanes, with no serial lane. The existing descending timing /
ascending path / lowest total / lowest index greedy algorithm preserves
assignment order. No runtime JUnit reads, adaptive state, byte-size placement,
lane pins, ownership changes, removed tests, or skip policy are introduced.
FULL/ROBINHOOD/LEGACY/EXHAUSTIVE ownership remains 198/109/222/420 modules;
the frozen required baselines remain 122/49.

Accepted R3K ROBINHOOD is unchanged: 109 modules, four lanes with
27/30/26/26 modules, 856950 ms total, and timing-map SHA256
0c0c79f710ab8b3a9ffc08de4720c026f257e2ffefc8dc6989c3a70fba2d2898.
LEGACY/EXHAUSTIVE retain their exact historical serial safety and planner.
R3J/R3K maps/digests/AST data and R4 Administrator-before-latch/native product
pins remain frozen. The exact R3L overlay covers only the three changed
current pinned certification consumers; current-doc mutability, D1S2 None
rollback, D1S3 registration and mapped ROBINHOOD remain intact.

R3L is intentionally unmapped from ACTIVE_CI_CHECKPOINTS and
CI_CERTIFICATION_PROFILES. One atomic publication uses normal broad fallback
source CI. Only terminal green permits one canonical local six-lane FULL on
that exact pushed tree. That later run is not duplicated by fallback CI.
No merge or protected preflight/effect is part of R3L implementation.
The historical sections below retain their then-current topology facts.
Exact raw/normalized timings, both analysis models, membership and hashes are
in [R3L validation](../validation/arch132-r3l-full-six-lane-topology.md).


## Architecture 132-R3K — four-lane current-local ROBINHOOD topology

R3K is the certification-topology successor to published R3J. It is based
exactly on R3J HEAD `de627d741891972b35fec458dbb9e66d46d1f4ac` and tree
`45bf73e5136d69ae8a1e1246340ac3b4f6791f41`. R3J's source implementation was
structurally correct, but its one authorized canonical local ROBINHOOD run
failed the unchanged 300-second hygiene ceiling. R3K changes only current
ROBINHOOD placement and its certification evidence; D1S3 product behavior is
unchanged, R4 remains unpublished and parked in its separate worktree, and no
protected operation is added.

### Raw R3J-D1 diagnostic evidence

The preserved diagnostic evidence is
`F:\AI\temp\certification\arch132-r3j-d1-isolated-186da70cc66942dfb26a763f150958f6`.
Its `robinhood-1.xml`, `robinhood-2.xml`, and `analysis.json` were independently
reconciled using the exact R3J interpreter
`F:\AI\ai-trading-bot\.venv\Scripts\python.exe` (Python 3.14.3). The evidence
contains 109 unique canonical modules and exactly 856949 ms of testcase work.
Exactly one module measured zero milliseconds:
`tests/domain/test_positions.py = 0 ms`. All other modules retain their exact
positive evidence-derived integer totals.

The R3J GitHub-derived timing table and its two-lane result remain historical
R3J evidence only. They are not a second current timing authority and are not
used by R3K placement.

### Canonical R3K positive source-placement model

Architecture-132 source timing weights are positive placement estimates. A
measured zero-duration module is therefore normalized to the reviewed positive
1-ms minimum before it becomes frozen source data. This is evidence
normalization, not a relaxation of runtime validation: a zero supplied directly
to `ROBINHOOD_MODULE_TIMINGS_MS` remains rejected fail-closed, as do bool,
negative, malformed, duplicate, noncanonical, and stale entries.

The canonical R3K source table has 109 unique tuple-pair entries, all positive,
with `tests/domain/test_positions.py = 1 ms` and every other value copied
exactly from the raw evidence. Its total is 856950 ms. The sorted compact JSON
map material (`sort_keys=True`, separators `,`/`:`, UTF-8, no trailing newline)
has SHA256:

```text
0c0c79f710ab8b3a9ffc08de4720c026f257e2ffefc8dc6989c3a70fba2d2898
```

R3K applies the unchanged deterministic whole-module greedy algorithm directly
to four lanes: descending frozen/fallback milliseconds, ascending canonical
path, lowest modeled total, then lowest lane index. The exact current-local
model is:

```text
robinhood-1  27 modules  214237 ms  cc0a6556faf54386fe4e8c0a192ac0ad6543da814d5926e86f7c8bc867470a51
robinhood-2  30 modules  214237 ms  904166863dfa5354fad29773877c70eb991ba240b3f117ccb163766f8fc71198
robinhood-3  26 modules  214240 ms  a5620743bd21fbb59d16f0994290e2908bfeeba71bfc3a15bed0fb2cadb42aa3
robinhood-4  26 modules  214236 ms  e51754fe142e84fac06f2a27184aa948f1a2de73f5868f6fef45f3d174a62b45
total        109 modules  856950 ms
```

The exact ordered lane membership is frozen in
`docs/validation/arch132-r3k-robinhood-four-lane-topology.md` and is derived
from the source table, not manually pinned. Reversed inventory input and
existing-module byte-size changes produce the same ordered lanes. Future
admitted modules absent from the table receive `ROBINHOOD_FALLBACK_MS = 1000`
for placement and remain covered exactly once.

### Four-lane decision and rejected three-lane model

The raw evidence gives a two-lane mathematical lower bound of
`856949 / 2 = 428474.5 ms`; two lanes are impossible. The raw three-lane lower
bound is `285649.667 ms`, and the normalized model is `856950 / 3 = 285650 ms`.
Three lanes are rejected without a publication attempt: they leave only about
14.35 seconds below the 300-second ceiling, while isolated child/process
overhead was already 8.197 s and 8.422 s and the observed two-child concurrent
slowdown was +7.960% JUnit work (+8.337% child elapsed). Four lanes are the
smallest evidence-backed topology with credible sub-300-second margin. R3K
selects four directly; it does not try three first and has no automatic fifth
lane path.

The 300-second hygiene ceiling is unchanged. ROBINHOOD ownership, directory
ownership, required-module semantics, selected inventory, FULL membership,
LEGACY membership, EXHAUSTIVE membership, JUnit validation, historical lane
pin constants, and protected fail-closed behavior remain unchanged. The four
historical `ROBINHOOD_*_LANE_PINS` dictionaries remain provenance only and no
R3K lane pin is added or applied. R3K remains intentionally unmapped from
`ACTIVE_CI_CHECKPOINTS` and `CI_CERTIFICATION_PROFILES`; source-gate fallback
remains the broad safety net. R3J remains preserved as published but
certification-rejected evidence, and R3K has no D1S3 source-acceptance effect.

## Architecture 132-R3J — ROBINHOOD timing-aware lane stabilization

R3J is a certification-topology-only correction on the exact R3 product
inventory. It does not change D1S3 production behavior, publish R4, or add a
protected operation. The unpublished R4 draft remains parked in its separate
worktree and is not part of this checkpoint.

R4 exposed structural instability in the old ROBINHOOD byte-size proxy. The
affected selected test module changed from 45,332 to 47,488 and then 47,247
bytes during the R4 work, moving 71/109 modules on the initial R4 comparison
and 30/109 after R4 compaction. Further test shrinking was rejected because it
would optimize source bytes rather than measured certification work.

R3J freezes the preserved canonical ROBINHOOD timing evidence from GitHub run
`39903070805`, artifact `canonical-certification-robinhood`, exact R3 HEAD
`b40038c16a93f9bd9eb46cba5a30c14ba23b48ec`, and artifact digest
`sha256:5b8af9ad5c731cd74c3c83f6c635cd0c9c6eef6f9558bbad3d3ded20e5cd1a6f`.
The two XML files derive 109 module totals and 543684 positive integer
milliseconds. The sorted compact JSON timing map SHA256 is
`b4e7b62c1c63e273546cc83c324be6634d7809a8194540b27f950117dce73c99`.

The source-owned R3J model sorts descending frozen or 1000-ms fallback weight,
then canonical path, and greedily assigns whole modules to the lowest modeled
lane total with the lowest lane index as the tie-break. It never reads module
byte size, mutable timing files, JUnit, or prior CI artifacts at runtime.
The exact R3 inventory result is:

```text
robinhood-1  54 modules  271842 ms  91b85f6104620e3040821b3a55cf9b8875e54c9d47b6ac0532e4808c5d46eb24
robinhood-2  55 modules  271842 ms  96bae036e5cd7f7b5148a3402151351c16a1bcc3a01b412d58f8de941147e99f
total        109 modules 543684 ms
```

The D1S3 operator module remains in `robinhood-2` with its preserved 10946-ms
weight. New future supported ROBINHOOD modules receive exactly 1000 ms as a
placement estimate and remain covered exactly once. ROBINHOOD ownership,
required baseline, two-lane whole-module topology, JUnit validation, and the
unchanged 300-second hygiene ceiling remain unchanged. FULL's timing table and
four-lane topology, LEGACY/EXHAUSTIVE topology, serial safety rules, and
protected rejection remain unchanged.

The historical `ROBINHOOD_LANE_PINS`, `ROBINHOOD_F1_LANE_PINS`,
`ROBINHOOD_F1R1_B_LANE_PINS`, and `ROBINHOOD_D1S3_LANE_PINS` constants remain
byte-for-byte preserved as provenance. R3J supersedes them for current
ROBINHOOD placement; `build_lanes(..., "robinhood")` does not apply them and
R3J adds no new pin. The R3J branch is intentionally unmapped from
`ACTIVE_CI_CHECKPOINTS` and `CI_CERTIFICATION_PROFILES`, so source-gate CI
uses the reviewed unmapped broad fallback. R3J does not satisfy the separate
D1S3 FULL obligation.

## 2026-10-18 — Architecture 132-R3I FULL-only timing-aware hygiene correction

R3I changes only CURRENT FULL placement to four deterministic nonempty
whole-module timing-aware lanes: `broad-1`, `broad-2`, `broad-3`, `broad-4`.
ROBINHOOD retains exactly two lanes and the accepted R3H placement overlay,
byte/behavior unchanged. LEGACY/EXHAUSTIVE retain their historical
two-broad-plus-serial topology. Historical R1/R2/R3/R3H descriptions below record
their accepted topology at the time; this section supersedes only current FULL
placement, not their historical facts.

The preserved Architecture-143 FULL evidence is
`F:\\AI\\temp\\pytest\\arch143-full-bfda654ee4334d479c63e5ea0314b631`, from
`feature/research-strategy-production-compatibility-current` at exact HEAD
`33b14eab4e9577f15b2afa559918415e4d471d55`, TREE
`d19ef77620881343cc38010290029865fd43c1f4`. It selected 186 supported modules,
93 in each lane. The run was functionally passing but failed hygiene:

| Evidence | broad-1 | broad-2 | Total |
| --- | ---: | ---: | ---: |
| Passed | 6,504 | 5,796 | 12,300 |
| Skipped | 0 | 3 | 3 |
| Failed / errors | 0 / 0 | 0 / 0 | 0 / 0 |
| Cases | 6,504 | 5,799 | 12,303 |
| Child elapsed seconds | 331.064 | 704.807 | 1035.871 |

Wall time was 709.756 seconds; measured JUnit testcase work was approximately
1001.177 seconds. Even ideal redistribution of observed child elapsed work
across two lanes has a lower bound of 1035.871 / 2 = approximately 517.936
seconds, so two-lane rebalancing is mathematically insufficient at measured
cost. Greedy whole-module models over raw JUnit testcase work give:

| Lanes | Modeled testcase seconds |
| --- | --- |
| 3 | 333.726 / 333.726 / 333.725 |
| 4 | 250.295 / 250.294 / 250.294 / 250.294 |

Four lanes are the smallest measured topology with credible sub-300-second
headroom. These models are provenance, not a guarantee: CPU, disk, memory and
antivirus contention remain explicit uncertainties for the later real run.
The frozen 300-second hygiene ceiling remains exactly unchanged.

`scripts/run_test_certification.py` owns a frozen 186-entry table of integer
milliseconds, derived only by summing testcase times by canonical module path
from those two JUnit files. The sole measured zero, `tests/test_config.py`, uses
a documented positive 1-ms minimum. Thus the source-owned positive model totals
1001178 ms (one millisecond above raw evidence), retains module counts
46 / 47 / 46 / 47, and yields exact lane totals
250295 / 250295 / 250294 / 250294 ms. The canonical table SHA256 is
`e23c35fcebadd578e26beb349d09e84a308aeb229e5a2aef87863f6119e19d36`, over
UTF-8 sorted compact JSON object material (`sort_keys=True`, separators `,`/`:`,
no trailing newline). Source pairs preserve duplicate paths for validation.

FULL validates canonical paths, exact positive integer values (bool excluded),
unique semantic paths and membership in selected FULL; malformed, duplicate or
stale entries fail closed before children launch. New supported modules absent
from the table receive exactly 1000 ms. This is only a deterministic placement
estimate and must never exclude a newly supported module or infer ownership.
The runner never reads prior evidence, mutable timings, clocks or profiling for
placement. It sorts selected modules by descending weight then ascending path,
assigns each whole module to the lowest-total lane, breaks equal lane loads by
lowest index, updates that total and preserves assignment order.

Ownership and discovery are unchanged: FULL 186, ROBINHOOD 101, LEGACY 222,
EXHAUSTIVE 408; frozen required baselines remain FULL 122 and ROBINHOOD 49.
No tests are removed, skipped or reclassified. No slow-test deduplication,
product/research/Architecture-143 semantics, Architecture-141/142 artifact
source, D1R9, provider, broker, production or scheduler behavior changes.
All exact-source/remote admission, protected rejection, JUnit validation,
whole-repository Ruff/diff/static checks and external evidence rules remain.

Architecture-143 semantic source was admitted at
`33b14eab4e9577f15b2afa559918415e4d471d55` /
`d19ef77620881343cc38010290029865fd43c1f4`; the Architecture-132-R3I implementation was admitted at
`9fb082d21f00326bc98103abb8d357e6368df72f`. The first post-R3I FULL exposed
the stale Architecture-143 successor assertion; its failed evidence remains
preserved as historical failure. C1 changed only
`tests/experiments/test_research_strategy_production_compatibility.py`,
composing that assertion through `ARCH132_R3I_CURRENT_TEST_PIN_OVERRIDES`.

Checkpoint Source Gates #630 / run `39117841927` / push / attempt 1 is terminal
SUCCESS on final R3I-C1 source `c5225d8f3f584eb0eb60d62e5381f1caa3c56cb2`,
TREE `bf7019b1610c29563282ccb5f19be2bcb6501849`. The canonical local FULL was
required exactly once because this unmapped feature checkpoint required
materially distinct timing evidence; it must not be treated as routine manual
duplication of mapped CI certification:

```text
broad-1  46 modules  2666 cases  2666 passed  0 skipped  0 failed  0 errors  282.944 s
broad-2  47 modules  2886 cases  2886 passed  0 skipped  0 failed  0 errors  282.968 s
broad-3  46 modules  3430 cases  3430 passed  0 skipped  0 failed  0 errors  282.991 s
broad-4  47 modules  3372 cases  3369 passed  3 skipped  0 failed  0 errors  283.018 s
TOTAL    12354 cases / 12351 passed / 3 skipped / 0 failed / 0 errors
WALL     287.176 s
```

The 300-second ceiling therefore passed with 12.824 seconds of headroom. No
test ownership or effect boundary changed, and no Architecture 144 work is
included. Status and handoff now record the accepted closeout.

## 2026-10-14 — Architecture 132-R3H measured two-lane hygiene correction

Architecture 134-D1R5 exposed a certification-lane imbalance without a product
test failure. Checkpoint Source Gates #553 ran the exact ROBINHOOD inventory
successfully: 9,179 passed, one skipped, zero failed/errors across 9,180 cases.
Its canonical wall time was 339.725 seconds, so the existing 300-second hygiene
gate correctly rejected the source.

The preserved JUnit evidence showed the byte-size balancing proxy no longer
tracked runtime cost. The measured testcase time was approximately 326.329
seconds in robinhood-1 versus 87.068 seconds in robinhood-2. Four current
runtime outliers dominated the skew:

- `tests/runtime/checkpoint_runner/test_arch133_l_m.py`;
- `tests/runtime/checkpoint_runner/test_arch133_h_k.py`;
- `tests/runtime/checkpoint_runner/test_arch131.py`;
- `tests/review_paper/test_arch133_scheduler_installation.py`.

R3H preserves the exact Architecture-132 profile ownership, exact two-lane
FULL/ROBINHOOD topology, whole-module partitioning, deterministic ordering,
JUnit validation, static checks and 300-second ceiling. It does not remove,
skip or reclassify any test and does not add shards.

The ordinary byte-size greedy assignment remains the default. ROBINHOOD adds
one source-owned deterministic placement overlay for only the four measured
outliers: `arch131` and `arch133_h_k` remain in lane 0; `arch133_l_m` and
the scheduler-installation module are placed in lane 1. Missing overlay modules
are inert so frozen/minimal profile fixtures remain valid. On the exact #553
timing evidence, applying only this placement changes the observed lane work
from about 326.329/87.068 seconds to 207.890/205.507 seconds.

The placement is not learned dynamically and does not read prior CI artifacts
at certification runtime. Any future timing/topology change remains separately
reviewed and the 300-second gate continues to fail closed.

R3H is **SOURCE/CERTIFICATION ACCEPTED** on the D1R5 branch at HEAD
`a7f985c6e4c723fdd4c4a1c49798531ddabe9e4a`, TREE
`9fcbc170e8339e0b4a93844466e8924ff8ef7f36`. Checkpoint Source Gates
#557 / `38549244176` passed. Canonical ROBINHOOD retained all 98 modules
and ran exactly two whole-file lanes: 47 modules / 4,828 passed in lane 1 and
51 modules / 4,353 passed plus one skip in lane 2. Total: 9,182 cases,
9,181 passed, one skipped, zero failed/errors, wall 253.493 seconds. This
restores the frozen sub-300-second hygiene requirement without adding shards,
dropping tests, changing ownership, or increasing the ceiling.


## 2026-10-13 — HIST-2 certification inventory integration

HIST-2 adds `tests/scripts/test_archive_project_history.py` as one supported
FULL-only infrastructure module. It is intentionally not Robinhood product
coverage and does not change the frozen FULL/Robinhood required baselines,
legacy ownership, serial safety lane, checkpoint routing, or protected-effect
authority.

The current source-discovered inventory is ACTIVE 63, FULL 174, ROBINHOOD 97,
LEGACY 215, EXHAUSTIVE 389. The added archive test is admitted through the
reviewed FULL exact-module surface; unknown `tests/scripts/` modules continue
to fail closed. Architecture-134 current authority resolves a separate reviewed
HIST-2 test-pin overlay after the frozen D1R4R pins for the five inventory tests
whose count assertions changed; all predecessor pin dictionaries remain frozen.

## Current D1Q inventory and certification route

Current GUI-A15/D1Q-R2 source-discovered inventory is ACTIVE 62, FULL 169,
ROBINHOOD 94, LEGACY 215, EXHAUSTIVE 384. A15 adds five legacy GUI test
modules, making `tests/gui/` 44 rather than the accepted A14 inventory of 39;
source classification and frozen required baselines/lane rules are unchanged.
Historical AJ publication recovery remains registered but deliberately closed
and excluded from active CI. Earlier inventories are historical. D1Q/R2's
explicit mapping remains CI-owned robinhood certification. GUI-A15's unmapped
repository dispatch uses the four-shard source-gate fallback; no local broad
profile is selected.

## 2026-10-11 — Architecture 132-R3 CI-owned selected certification

R3 serializes the expedited verification path without changing profile ownership
or the R2 lane topology.

An exact active checkpoint may be explicitly mapped in source to one canonical
CI-owned profile: `robinhood` or `full`. No profile is inferred from branch
name, changed paths, or product naming. A mapping change is itself reviewed
workflow/certification authority.

For a mapped non-docs push, GitHub runs:

~~~text
source-static
+ active checkpoint tests
+ scripts/run_test_certification.py --profile <mapped-profile>
-> source-gates
~~~

The four-shard checkpoint-union broad job is skipped only for that mapped push,
because the active checkpoint covers checkpoint-owned integration tests while
the canonical profile independently discovers/admit all tests owned by that
profile. Unmapped active pushes keep active + four-shard broad CI. FULL fallback
and docs-only behavior remain distinct and fail closed.

The canonical profile still uses exactly the Architecture-132 inventory,
required-baseline, two-lane FULL/ROBINHOOD topology, JUnit validation,
whole-repository Ruff/diff checks, protected-opt-in rejection, and exact
source/live-remote admission before/after execution. Hosted GitHub execution may
place pytest basetemps only below `RUNNER_TEMP`; human/local execution retains
the frozen `F:\AI\temp\pytest` root.

A successful CI-owned profile is final certification evidence for that exact
HEAD/tree. Repeating the same profile locally is prohibited duplicate work unless
the CI evidence is invalid/incomplete or a materially different host-specific
gate is explicitly required.

Both the checkpoint-union broad shard and CI-owned canonical profile have a
**300-second hygiene ceiling**. Reaching or exceeding it fails the source gate
and requires an audit before acceptance. Do not raise the ceiling as a substitute
for fixing test-topology growth.

134-D1 supplied the transition evidence: after broad CI was restored and stale
topology corrected, its exact accepted source
`e9e75bed815f5cdcffd474c4d01fad9c98a6403e` /
`74b3dc7c1d550c5dbc4787ab475a0e7d0d8a4c8b` passed the selected ROBINHOOD
profile **8,420/8,420** across 92 modules. Local wall time was **306.239 s**,
which triggers this R3 serialization/hygiene response rather than another
duplicated local run.

R3 itself is **ACCEPTED/CLOSED** on
`fecc7a7aacefa2b7253f36f5077935c6b76b5810` /
`1eb3d2882af4fb06e17c9e8753d0418830e34790`, CI
**#498 / 38217916400 SUCCESS**. The CI-owned ROBINHOOD profile selected the same
92 modules in 45/47-module lanes and recorded **8,416 passed / 1 skipped /
0 failed / 0 errors** in **170.058 s**. The active checkpoint passed,
checkpoint-union `full-tests` was correctly skipped, whole-repository static
certification checks passed, and terminal source-gates passed. This is the
normative proof that a mapped terminal-green CI profile satisfies the selected
profile obligation without a second human-run copy.

## 2026-10-11 — Normative test and certification workflow

Verification is fail-fast before longer pytest/certification execution.
These rules are normative and preserve Architecture 132's reviewed profile
ownership, required baselines, lane topology and protected boundaries.

### 1. Cheap deterministic gates first

Before longer pytest/certification execution, complete applicable source/
admission/topology checks, `git diff --check`, Ruff check, Ruff format check and
cheap static/authority checks. If a cheap gate fails, STOP before the longer
test scope. Retain the combined Ruff diagnostic rule: both non-mutating Ruff
phases run and failed phases emit `--diff` diagnostics before the Ruff gate
stops. Required final/post-test identity and static checks remain required;
this ordering rule does not remove them or modify the runner.

### 2. Do not run the same tests twice

For the same exact HEAD/tree and unchanged environment/evidence validity, do
not ask the human operator to rerun a scope already satisfactorily covered by
Codex and/or terminal-green GitHub Actions. Codex normally performs focused
verification during implementation; reviewed source-gate CI follows its
bounded commit/push. The human operator must not repeat those tests merely for
confidence.

A separate user-run test is justified only when it supplies materially
different required coverage/certification evidence, the source changed after
prior evidence, prior evidence was invalid/incomplete, or ChatGPT identifies
a distinct required gate not already covered. Independent required coverage
is not duplicate execution. A docs-only closeout does not change already
certified executable/test source and must not manufacture a repeat test event.

### 3. FULL is rare and is not an iteration loop

FULL is a consequential/current-product certification boundary, not a debugging
suite or a routine post-checkpoint confidence run. Preserve a failed FULL as
diagnostic evidence; do not immediately rerun it. Diagnose from that evidence,
make the bounded correction, pass cheap gates before focused tests, and run
only affected focused tests while iterating. Then exact-file commit/push,
obtain terminal-green source-gate CI, and obtain ChatGPT exact GitHub review/
source acceptance. Only then run one fresh FULL if the consequential boundary
still requires it.

After a passing FULL, do not rerun it on unchanged executable/test source while
its environment/evidence validity remains intact. Adjacent source-only
checkpoints may explicitly batch a pending FULL obligation until the next
genuine consequential boundary under the existing Architecture-132 conditions.
This does not permit crossing a protected effect, merge, major integration,
release or readiness boundary with an unsatisfied certification obligation.

### 4. Select certification tiers; do not stack them blindly

FOCUSED -> SOURCE-GATE CI is routine. ChatGPT selects ROBINHOOD or FULL according
to the required boundary; they are not cumulative confidence runs. When FULL
is selected for unchanged source at a boundary where ROBINHOOD would otherwise
also apply, FULL's strict superset coverage satisfies that narrower Robinhood
source-certification obligation. Do not run ROBINHOOD and then FULL merely
because both trigger descriptions apply. LEGACY/EXHAUSTIVE remain exceptional
compatibility gates. PROTECTED always requires separate fresh authorization;
no source certification grants it.

### 5. Latest audited current-product certification topology

The older two-broad-plus-one-serial all-repository FULL layout is historical
provenance. It predates the current/legacy ownership split and must not be
reintroduced for routine current-product verification.

The latest reviewed current topology is 146-B1-C4 FULL and R3K ROBINHOOD:

- FULL runs seven deterministic nonempty whole-module timing-aware lanes,
  `broad-1` through `broad-7`, with no serial lane;
- ROBINHOOD runs exactly four deterministic nonempty timing-aware lanes,
  `robinhood-1` through `robinhood-4`, with accepted R3K and no serial lane;
- LEGACY and EXHAUSTIVE alone retain the exact five-module serial safety lane.

A canonical current-product certification therefore uses
`scripts/run_test_certification.py --profile full` (or the selected
`--profile robinhood`). Under R3 this normally runs in GitHub when the exact
checkpoint has an explicit CI profile mapping; otherwise the human operator runs
the materially distinct selected gate. Never reconstruct a three-lane repository
suite or use raw monolithic pytest as certification. Focused tests remain focused.

Audit chronology:

- the pre-R1 all-repository suite used two broad lanes plus serial;
- 132-R1 separated supported/legacy ownership and moved current FULL/ROBINHOOD
  to two-lane selected profiles; accepted FULL wall time was **201.655 s**;
- 132-R2 retained those profile lane semantics while rationalizing test
  ownership/collection; accepted 136-module FULL wall time was **259.314 s**,
  and accepted routine source CI was approximately **250 s**;
- R2-B3/R2-B4 later reduced routine source-CI cost but explicitly left
  certification topology unchanged.

The 134-C FULL is larger than the R2 certified inventory. Its higher wall time
is evidence to monitor, not permission to regress to an older lane model. Any
future performance/topology change requires a separately reviewed,
measurement-driven Architecture-132 checkpoint.

### 6. Bounded Codex commit/push and direct ChatGPT GitHub review

For an authorized bounded implementation/correction, Codex stages only the
exact intended files after proving the index is clean, verifies the staged
filename set and `git diff --cached --check`, creates one normal commit, and
ordinary-pushes only the existing feature branch. That authority includes no
merge, rebase, amend, force-push or PR metadata change. ChatGPT retrieves the
exact GitHub commit/diff/CI directly; do not require pasted GitHub diffs when
retrieval tools can obtain them.

### 7. Docs-only closeout preserves accepted test evidence

Keep a docs-only closeout strictly under `docs/**` so the existing classifier
uses its cheap validation path. Do not modify `AGENTS.md` merely to mirror
these details and thereby trigger a redundant non-docs test run. It was reviewed
for this closeout and remains compatible: it already forbids repeatedly
rerunning expensive full suites and delegates detailed certification behavior
to Architecture 132/workflow docs. A future naturally necessary non-docs
workflow checkpoint may mirror this wording without a standalone duplicate-test
event. Docs-only verification uses appropriate source/docs checks, including
exact admission, exact changed-file review, `git diff --check` and staged diff
check; it does not rerun pytest, FULL/ROBINHOOD or Ruff over unchanged Python.

## 2026-10-08 — Architecture 132-R2-B4 SOURCE ACCEPTED; CI hygiene restored; Architecture 133 resumes

Architecture 132-R2-B4 is **SOURCE ACCEPTED** and the temporary CI-hygiene
interlude is **CLOSED**.

Accepted source:

```text
BRANCH  feature/test-suite-rationalization-132r2b4
PARENT  49e2c0371998b632bee94947cc5028b919588ea3
HEAD    e7365dc17e9c67799766fc1666172b55f0ce30bc
TREE    433bbb826a34c0c03fd0265b57242f1c98a1b104
CI      #327 / 37865395473 SUCCESS
```

The exact implementation diff changes only:

```text
tests/runtime/checkpoint_runner/helpers.py
tests/runtime/checkpoint_runner/test_arch131.py
tests/runtime/checkpoint_runner/test_arch133_a_g.py
```

No production `src/`, scripts, authority implementation, source/registration
pin, protected callback, `ACTIVE_CI_CHECKPOINTS`, `RETAINED_CHECKPOINTS`,
source-gate workflow, certification ownership, external-effect policy or
certification profile topology changed.

### Exact review

B4 replaces repeated full `scripts/checkpoint_runner.py` fixture copies with a
bounded original-source contract fixture. The helper parses the complete
accepted runner text only to select the original source segments that own:

- `ACTIVE_CI_CHECKPOINTS`;
- `ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH`;
- the complete `_checkpoint_specs` registry; and
- every `CheckpointSpec` constructor, including constructors outside the
  registry.

The selected material is copied as original source text rather than
`ast.unparse`, preserving registration hashes, literal spellings, mutation
anchors and existing parameter identities. Extraction is cached only by the
complete source text. No authority result, mutated fixture, runner AST parser
or production authority function is cached or replaced.

Every mutation still executes the real authority parser. Existing accepted-copy
baseline cases now prove both compact and complete runner material. Existing
exact-once predecessor PASS/rejection and complete-chain proofs remain, and B4
adds explicit tests proving exact AST contract preservation, rejection of
missing/duplicate contract owners, independence from unrelated later authority
implementation growth, and full-runner real-chain accepted/pin/registration/
workflow behavior.

Independent JUnit comparison against accepted B3 source gate #325 proves all
**5,419** B3 testcase identities remain with zero missing/renamed identities
and exactly **12** additional proof cases.

Terminal #327 evidence:

```text
CHECKPOINTS       41
TEST_PATHS        52
RUFF_PATHS        155
pytest cases      5,431
passed            5,430
skipped           1
failed/errors     0
pytest elapsed    179.3632095 s
workflow elapsed  244 s
AUTHORITY         41/41 PASS
IDENTITY_STABLE   True
OVERALL           PASS
```

All production, provider, scheduler-mutation and broker/live effects are
`NOT_RUN`.

B4 reduces the two targeted unchanged runner modules from the accepted B3
measurements:

```text
test_arch131       724 / 112.651 s  -> 736 / 19.163 s
test_arch133_a_g   211 /  28.767 s  -> 211 /  4.443 s
```

while retaining every prior identity and adding coverage.

### Certification-tier decision

No ROBINHOOD, FULL, LEGACY or EXHAUSTIVE certification is selected for B4.
This checkpoint changes test fixture/coverage mechanics only; no supported
production behavior or certification topology changed. The registered source
gate exercised every changed module and all 41 active authority checks.

Routine serial source CI is restored to the accepted operating envelope:

```text
R2-B2 accepted    pytest 199.4257606 s / workflow 250 s
B3                pytest 322.6453311 s / workflow 387 s
B4                pytest 179.3632095 s / workflow 244 s
```

B4 is below both the accepted R2-B2 pytest and workflow measurements. Therefore
the R2-D deterministic parallelization phase remains **DEFERRED**; adding CI
parallelism now would add topology/maintenance complexity without a measured
need.

### Architecture 133 resumes

The CI-hygiene interlude no longer blocks Architecture 133. Resume from the
corrected Architecture 133-R operator topology and its separately protected
read-only reprovision-admission diagnostic boundary.

The previous real 133-R diagnostic authorization was consumed by the
`PREDECESSOR_RUNTIME` fail-closed invocation performed from detached HEAD. The
operator worktree was subsequently corrected to the expected named tracking
branch, and the bound 133-G checkout was independently verified.

A further real 133-R read-only diagnostic requires **new fresh explicit
authorization**. The prior authorization does not transfer.

The consumed Architecture 133-Q read-only plan MUST NOT be rerun.
Architecture 133-Q `execute-once`, Q133-3, Q133-4, provider/OAuth access,
unattended wake execution and production/live broker effects remain
unauthorized / NO-GO.

## 2026-10-08 — Architecture 132-R2-B3 SOURCE ACCEPTED; hygiene continues before R2-D

Architecture 132-R2-B3 is **SOURCE ACCEPTED** as a test-only routine source-gate
hygiene correction.

Accepted source:

```text
BRANCH  feature/test-suite-rationalization-132r2b3
PARENT  d811bfefcf7b6dbb7f1e72d6c847aef1d3c573eb
HEAD    06ee31e020d6d46d327e9fb3b6dbda1b97947809
TREE    c110f86a25cb88cd880e50ad40ca28cf72887dc0
CI      #325 / 37863303291 SUCCESS
```

The exact implementation diff changes only:

```text
tests/review_paper/test_arch133_scheduler_installation.py
tests/runtime/checkpoint_runner/helpers.py
tests/runtime/checkpoint_runner/test_arch133_h_k.py
tests/runtime/checkpoint_runner/test_arch133_l_m.py
```

No production `src/`, scripts, authority implementation, source/registration
pin, protected callback, `ACTIVE_CI_CHECKPOINTS`, retained/active
classification, source-gate workflow, certification ownership, external-effect
policy or certification profile topology changed.

Exact review confirms the optimization preserves the security/authority test
contract:

- local pin/capability mutation matrices isolate only independently proven
  immediate predecessors;
- runner/workflow/order mutations retain H's real whole-batch validator plus
  each local authority's own checks;
- dedicated copied-source baselines prove local and workflow fixtures PASS;
- predecessor invocation/rejection propagation remains explicit through O/P;
- complete H->P real-chain tests prove accepted PASS plus predecessor-pin,
  runner-registration and workflow rejection;
- P pin coverage expands from the original eight explicit paths to all thirty
  local scheduler-installation pins.

Independent JUnit comparison against accepted 133-R source gate #322 proves all
**5,350** prior testcase identities remain, with zero missing/renamed identities
and exactly **69** additional proof cases.

Terminal #325 evidence:

```text
CHECKPOINTS       41
TEST_PATHS        52
RUFF_PATHS        155
pytest cases      5,419
passed            5,418
skipped           1
failed/errors     0
pytest elapsed    322.6453311 s
workflow elapsed  387 s
AUTHORITY         41/41 PASS
IDENTITY_STABLE   True
OVERALL           PASS
```

Compared with #322, pytest elapsed fell from 492.8505088 s to 322.6453311 s, a
34.53% reduction. The affected focused modules reduced their summed JUnit
testcase time from 303.844 s to 131.578 s while adding proof coverage.

### Certification-tier decision

No ROBINHOOD, FULL, LEGACY or EXHAUSTIVE certification is selected for B3.
This checkpoint changes test setup/coverage structure only; no supported
production behavior or certification topology changed. The registered source
gate exercised every changed module, all active checkpoint requirements and all
41 authority checks. A broad product certification would not add evidence about
a changed production surface.

B3 is accepted, but the CI-hygiene interlude is **not closed**. The 387-second
workflow remains materially above the accepted R2-B2 approximately 250-second
operating envelope.

The largest remaining cost is the unchanged
`tests/runtime/checkpoint_runner/test_arch131.py`: 724 identities consumed
112.651 s in #325 versus 71.088 s in R2-B2 #294. The unchanged
`test_arch133_a_g.py` also rose from 18.983 s to 28.767 s. This demonstrates
that old runner-contract tests still contain a source-topology growth
multiplier even when their testcase identities do not grow.

### Immediate next checkpoint

Continue test hygiene with **Architecture 132-R2-B4** before R2-D
parallelization. B4 is a bounded test/helper refactor targeting repeated
runner-source parsing/copying/accepted-baseline work in the unchanged
Architecture-131 and early-133 runner-contract suites. Preserve every logical
authority invariant and prior testcase identity wherever practical, using the
same accepted B2/B3 pattern: one explicit accepted baseline, isolated local
mutation checks, exact-once predecessor/rejection proofs, and explicit complete
real-chain integration proofs.

Timing remains diagnostic only. If B4 restores serial routine CI near the
accepted operating envelope, R2-D remains deferred. If redundant work is
exhausted and serial CI remains materially expensive, proceed to the already
defined R2-D deterministic parallel active-source-gate lanes.

Architecture 133 protected work remains paused during this hygiene checkpoint.
The consumed 133-Q plan MUST NOT be rerun; 133-Q `execute-once`, Q133-3,
Q133-4, provider/OAuth access, wake execution and production/live broker effects
remain unauthorized / NO-GO.

## 2026-10-07 — Architecture 132-R2 COMPLETE; FULL CERTIFIED

Architecture 132-R2 test-suite rationalization is **ACCEPTED and CLOSED**.

Final certified checkout:

```text
BRANCH  feature/test-suite-rationalization-132r2
HEAD    9d6e1b1c376c5f366e2dbac43d430b5683b7ad28
TREE    792bbc7b5010cdcbfa833ef548a672f8f23ec910

R2-B2 implementation
HEAD    ff21c05b93d862d2299dd1574c2f931b9ea5acb5
TREE    3e714d054516dfd156def89c2a21e51b85e8861e
CI      #294 / 37731218114 SUCCESS

R2-B2 acceptance/policy source gate
CI      #296 / 37732562660 SUCCESS
```

Fresh FULL current-product certification on the exact final checkout:

```text
profile     full
broad-1     67 modules / 3,259 cases / 3,257 passed / 2 skipped
broad-2     69 modules / 2,632 cases / 2,631 passed / 1 skipped

TOTAL       136 modules
cases       5,891
passed      5,888
skipped     3
failed      0
errors      0
wall        259.314 s
evidence    F:\AI\temp\certification\arch132-r2b2-full-9d6e1b1
```

The certification runner admitted and re-admitted the exact clean source,
current live feature ref and current live develop ref, then completed whole-
repository Ruff check, Ruff format check and git-diff check through the accepted
FULL profile. No protected opt-in was enabled.

### Final R2 outcome

Routine current-product source CI is restored to its historical operating
envelope without reducing logical authority coverage:

```text
                         pre-R2 / regression     final R2-B2
routine checkpoints              44                  36
active TEST_PATHS                68                  47
active RUFF_PATHS               150                 127
source-CI pytest              696-790 s          198.14 s
source-CI workflow             >13 min              250 s
```

Historical successful non-docs source-gate medians were 188.41 s pytest and
242 s workflow. Final R2-B2 is +5.16% and +3.31% respectively, inside the
historical operating range.

All accepted R2-B logical test identities remain, with additional proof cases.
Production authority code/pins/chaining were not weakened. The final
certification topology is:

```text
FULL        136 modules
ROBINHOOD    63 modules
LEGACY      205 modules
EXHAUSTIVE  341 modules

required FULL       122 modules
required ROBINHOOD   49 modules

ACTIVE_CI_CHECKPOINTS   36
RETAINED_CHECKPOINTS     8
```

### R2-C / R2-D disposition

R2-C retained-source/test provenance cleanup and R2-D source-gate
parallelization are **deferred maintenance**, not blockers for current product
work.

- R2-C remains useful before any deliberate historical source deletion, but
  routine current-product CI no longer executes the retained Architecture
  128/130 checkpoints or retained runner contracts.
- R2-D is not justified as an immediate prerequisite now that serial routine CI
  is back to the historical ~4-minute end-to-end regime. Parallelization may be
  revisited if current-product growth again makes the measured serial gate
  materially expensive.

Do not delete retained production/security primitives merely because R2 is
closed. Any future R2-C removal still requires provenance classification
`KEEP_COMPAT`, `DISTILL_INVARIANTS`, or `DELETE_WITH_SOURCE`.

### Project resumes Architecture 133

The test-suite interlude no longer blocks Architecture 133. Resume from the
already source-accepted Architecture 133-M credential-free stage diagnostic.
Q133-2V remains consumed and non-retryable. Q133-3 scheduler installation and
Q133-4 unattended wake remain unauthorized. The real 133-M diagnostic remains a
separately protected one-attempt read-only boundary and requires fresh explicit
authorization before invocation.

Production/live real-money placement remains **NO-GO**.

## 2026-10-07 — Architecture 132-R2-B2 SOURCE ACCEPTED; FULL certification next

Architecture 132-R2-B2 is **SOURCE/TOPOLOGY ACCEPTED**.

Accepted executable/test implementation:

```text
BRANCH  feature/test-suite-rationalization-132r2
HEAD    ff21c05b93d862d2299dd1574c2f931b9ea5acb5
TREE    3e714d054516dfd156def89c2a21e51b85e8861e
CI      #294 / 37731218114 SUCCESS
```

Implementation-evidence docs descendant before this closeout:

```text
HEAD    ad43c9c45b3ff10e33833c49823fc74cd6b2ba91
TREE    e1e7485d9a607194ac8d142af87c57f4d2c6f15e
CI      #295 / 37731687297 SUCCESS
```

ChatGPT exact-source review found no correction required. The implementation
diff changes only:

```text
tests/runtime/checkpoint_runner/helpers.py
tests/runtime/checkpoint_runner/test_arch131.py
tests/runtime/checkpoint_runner/test_arch133_a_g.py
```

No production `src/`, source-gate workflow, checkpoint registration,
production authority function, certification runner, profile ownership, source
pin or protected capability changed.

Independent JUnit identity comparison against accepted R2-B source gate #291
proves all **4,612** prior testcase identities remain in R2-B2, with **zero**
missing and exactly **32** new proof cases. Those additions are 21 copied-closure
baseline PASS cases, ten predecessor PASS/rejection cases for five real G/H
edges, and one complete transparent real-chain PASS trace.

The only newly isolated predecessor edges are:

```text
131-G agentic account -> direct MCP
131-G agentic account -> MCP schema
131-G agentic account -> paper cycle
131-H paper operator  -> 131-G agentic account
131-H paper operator  -> Windows OAuth
```

Isolation is confined to wholly local G/H source mutations. The real local
authority body still executes. Separate tests prove each predecessor is invoked
exactly once, predecessor rejection propagates fail-closed, and the complete
real H -> G -> direct MCP -> schema -> paper-cycle plus Windows-OAuth chain
passes on accepted source. G transport/adapter/registration mutations, H
predecessor-source/registration/workflow mutations, and all 30 H-M
workflow/order cases retain real chaining.

Terminal source evidence was independently checked from artifact
`checkpoint-source-gate-evidence`:

```text
CHECKPOINTS       36
TEST_PATHS        47
RUFF_PATHS       127
pytest            4,643 passed / 1 skipped / 0 failed / 0 errors
pytest wall       198.14 s
command elapsed   199.42576060000002 s
workflow elapsed  250 s
identity stable   true
all source/static commands exit 0
```

R2-B2 therefore restores routine source CI to the historical operating envelope
without reducing logical coverage. Pytest is 5.16% above the historical median
188.41 s and end-to-end workflow time is 3.31% above the historical median
242 s; timing remains diagnostic only.

Certification topology is unchanged from accepted R2-B:

```text
FULL / ROBINHOOD modules      136 / 63
LEGACY / EXHAUSTIVE modules   205 / 341
required FULL / ROBINHOOD     122 / 49
active / retained checkpoints 36 / 8
```

The deferred R2-B certification obligation is now due. The immediate next gate
is exactly one fresh **FULL current-product certification** on the clean current
R2 branch checkout. R2-C, R2-D and real Architecture-133 protected work remain
paused until FULL is reviewed.

Q133-2V remains consumed/non-retryable. Q133-3 and Q133-4 remain unauthorized.
Production/live real-money placement remains **NO-GO**.

## 2026-10-07 — Architecture 132-R2-B2 terminal source CI green; review/FULL pending

R2-B2 is implemented and its source gate is terminal **SUCCESS**. This is
implementation evidence only; ChatGPT exact-source acceptance and the deferred
FULL current-product certification remain pending.

```text
BRANCH  feature/test-suite-rationalization-132r2
HEAD    ff21c05b93d862d2299dd1574c2f931b9ea5acb5
TREE    3e714d054516dfd156def89c2a21e51b85e8861e
CI      #294 / 37731218114 SUCCESS
```

The change is confined to three checkpoint-runner test/helper files. Twenty
copy helpers now defer accepted-source PASS checks to 21 dedicated cases rather
than repeating them before every mutation. Five Architecture-131 G/H predecessor
edges are isolated only for wholly local source mutations; separate invocation,
rejection-propagation and complete real-chain PASS proofs remain. All original
mutation matrices and all 4,612 prior CI case identities remain; 32 proof cases
are added. No production source, authority implementation/chaining, pin,
registration, workflow, certification ownership or module topology changed.
The 30 H-M workflow/order cases retain real chaining.

```text
active / retained checkpoints   36 / 8 (exact order unchanged)
TEST_PATHS / RUFF_PATHS          47 / 127
FULL / ROBINHOOD modules         136 / 63
LEGACY / EXHAUSTIVE modules      205 / 341
required FULL / ROBINHOOD        122 / 49 (accepted R2-B migrated baselines)
focused tests                   1,627 passed / 0 failed
source CI                       4,643 passed / 1 skipped / 0 failed / 0 errors
pytest wall                     198.14 s
pytest command elapsed_seconds  199.42576060000002
workflow end-to-end             250 s
```

Observed pytest time decreased 43.72% from R2-B's 352.07 s;
workflow time decreased 38.42% from 406 s. Relative to historical
medians (188.41 s / 242 s), pytest is +5.16% and workflow is
+3.31%. Timing is diagnostic and has no PASS/FAIL threshold.
Recorded testcase time totals 192.039 s; checkpoint-runner
infrastructure contributes 175.592 s / 1325 cases /
91.44%, and other tests contribute 16.447 s.

See the R2-B2 terminal implementation report in
`docs/validation/arch132-r2-test-suite-rationalization-plan.md` for the exact
isolated edges, coverage accounting, active path unions, JUnit module timings,
commands, deviations and all top-100 durations. Source evidence is retained in
[CI #294](https://github.com/callmedraken/ai-trading-bot/actions/runs/37731218114) as `checkpoint-source-gate-evidence`, including
`pytest-results.xml`, `report.json`, and command output.

Next owner: **ChatGPT** for exact GitHub source review against frozen parent
`bd9729e2dc8ca728908fc75ad906d78ddfa833b5`. If accepted, supply one fresh FULL
certification command against this final executable/test source. FULL remains
deferred, not waived. Do not begin R2-C/R2-D, run real 133-M, retry Q133-2V,
perform Q133-3/Q133-4, or cross credential/scheduler/provider/broker/live
boundaries. Production/live real-money placement remains **NO-GO**.

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
FOCUSED -> SOURCE-GATE CI
-> ChatGPT selects ROBINHOOD or FULL for the required boundary
   (FULL covers the narrower ROBINHOOD source obligation)
-> LEGACY/EXHAUSTIVE only for explicitly relevant compatibility
PROTECTED always separately authorized
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
Architecture 131 letter. A certification-topology change creates a pending FULL
obligation, but adjacent source-only checkpoints with focused verification and
terminal-green source-gate CI may explicitly batch that obligation until the
next coherent current-product/readiness boundary, provided no protected effect,
merge, major integration or release boundary occurs in between. The final exact
source must complete FULL before crossing such a consequential boundary.
Normal current-product certification does not require LEGACY or EXHAUSTIVE.
ChatGPT owns exact source review, acceptance, and the certification-tier
decision. The normal handoff remains:

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

At the historical pre-GUI-A14 inventory tree (provenance only; current inventory
is stated at the top of this document and `tests/gui/` now contains 44 modules):

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

FULL uses seven deterministic nonempty whole-module timing-aware lanes as
specified by 146-B1-C4 above. Robinhood retains four deterministic timing-aware lanes
under accepted R3K. Both have no serial lane. Only the historical
LEGACY/EXHAUSTIVE broad lanes retain descending-file-size balancing
with stable path/lane ties and whole-file allocation. LEGACY and EXHAUSTIVE
retain the exact historical two-broad-plus-serial topology and five-module
serial allowlist:

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

Every executing profile requires exact Ruff 0.17.3 and whole-repository static
checks after source admission and inventory/topology construction, before any
pytest child starts. Static failure persists canonical evidence with no children.
Post-test/final source identity checks and result accounting remain required.
Local FULL-mode prepublication admission shares the exact version and Ruff roots;
a version mismatch stops before static checks or pytest without installing tools.
Plan-only operation remains non-executing. The canonical non-mutating checks are:

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
