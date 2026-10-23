# Validation — Architecture 134-F1R1-D1S3

Checkpoint: `arch134-f1r1-d1s3-successor-release-installation-operator`

This is a source-only ROBINHOOD-mapped checkpoint. It must prove exact D1S2
predecessor identity, source remote/ref/HEAD/tree admission, clean source
inventory, deterministic release declaration, canonical binding, fixed
production release/runtime paths, and an exact registration with a read-only
preflight and protected execute dispatch. Source CI never invokes protected
execute.

The D1S3 attempt path is the fresh fixed namespace
`F:\AI\temp\arch134-f1r1-d1s3-installation-attempt\attempt.json`; the
historical Architecture-133 AG latch and all original F1/C2/D1R7/D1R8
namespaces are non-substitutable. Preflight is read-only and never creates the
latch. Execute requires the exact authorization interlock, durably consumes
the latch before installer entry, calls the accepted installer once, preserves
ambiguity as consumed `INDETERMINATE`, and never retries automatically.

Focused tests cover source identity and inventory, release/binding replay,
mutable checkout rejection, FINAL/staging classifications, exact installed
ACK and post-install re-observation, preflight read-only behavior, one-shot
ordering and ambiguity, absent/exact/conflicting successor-root behavior,
D1S2 composition reuse, no scheduler/service/boot/logon/resume capability,
zero protected effects, exact current-document mutability, predecessor
dictionary/digest preservation, exact AST/inventory overlays, and the
registered checkpoint. Retained D1S2, D1S1, F1R1-A/B/C1, and relevant
Architecture-133 installation/runtime tests remain in the checkpoint tuple.

## Preserved C2 evidence and D1S3-R1 recovery

The initial D1S3 publication remains preserved at
`2d21714a7c38011c8913b1a23ddb6aaafd7c2e82`, with CI run
`39860583854` attempt 1 failing Ruff formatting. C1 remains preserved at
`a4fb7907d1bb3d11af753b848c277b622625005c`, with CI run `39861185223`
attempt 1 failing on eleven stale inventory consumers. C2 remains preserved
at `8b76d9469c0a092a2617824e1ecd9fa63b302ccd`, tree
`e3293357f27fb6fedc7f8c37c2e5a73c197069cb`, with CI run `39862983181`
attempt 1. C2 source-static passed; active tests recorded 1,932 total with
1,931 passed and 1 failed; canonical ROBINHOOD recorded 10,659 total with
10,652 passed, 6 skipped, and 1 failed. The sole failure was
`tests/runtime/checkpoint_runner/test_core.py::test_arch145a_successor_removal_restores_predecessor_failure`.

C2 proved that clearing `ARCH145A_TEST_PIN_OVERRIDES` could still pass because
a current D1S3 blob was returned before the predecessor lineage was validated.
It also recorded Robinhood summed testcase times of 237.839 seconds in
robinhood-1 and 287.630 seconds in robinhood-2, with elapsed times of 251.911
and 301.285 seconds. D1S3-R1 is the explicitly ChatGPT-reviewed recovery: all
audited D1S3 fast paths validate their predecessor overlays before applying a
terminal successor, static D1S3 authority probes the accepted C1/B/D1S2/
144-C/145-A material, and the new single D1S3 pin moves
`tests/review_paper/test_d1_session_execution.py` to lane 0. The preserved
proxy is approximately 264.568/260.901 summed testcase seconds; the 300-second
ceiling, two-lane topology, ownership, coverage, FULL topology, and
LEGACY/EXHAUSTIVE topology are unchanged.

D1S3-R1 remains source-only and not source accepted. Develop remains accepted
D1S2. No installation has run, the successor root remains absent, original F1
and C2 evidence is untouched, and provider/paper/broker/live effects remain
unauthorized with live NO-GO.

## D1S3-R1 terminal evidence and D1S3-R2 rationale

D1S3-R1 was published at
`c4d315e8eb2328594febb63e0e0c0c75c5f228ad` with CI run `39866210805`, attempt
1. Source-static passed, but active tests failed at
`tests/review_paper/test_arch134_f1r1_d1s2_successor_readiness.py::test_removing_d1s2_overlay_restores_d1s1_resolution`
because `ARCH134_D1S2_SOURCE_PINS = None` raised `ValueError: D1S2 source
overlay drift`. Canonical ROBINHOOD retained the reviewed two-lane shape at
55/54 modules, with elapsed times 278.765/278.779 seconds and a 280.368-second
wall; it recorded 10,669 cases, 10,662 passed, 6 skipped, 1 failed, and 0
errors. The hygiene ceiling passed, but the run was terminal red and remains
preserved.

D1S3-R2 restores the accepted D1S2 rollback sentinel. The source resolver now
validates the exact predecessor dictionary and predecessor blob first, returns
the predecessor when the successor overlay is exactly `None`, and only then
requires a non-`None` successor overlay to be an exact dictionary before
applying the terminal D1S3 successor pin. No accepted D1S2 test is weakened,
and the R1 predecessor-authority fix, lane pin/topology, and installation
operator remain unchanged. R2 is source-only; D1S3 remains NOT SOURCE ACCEPTED
pending terminal CI and ChatGPT exact-source review.

No production release, successor root, credential, provider, paper, broker,
D1, D2, scheduler, service, startup, or live effect is authorized or created.
Original F1 remains FINAL / INDETERMINATE / CONSUMED and C2 remains consumed
and non-reusable. The next action after terminal source-gate success is
ChatGPT exact-source review; only after SOURCE ACCEPTED may a separate
read-only protected preflight be reviewed.

## D1S3-R3 native read-only recovery

R2 is terminal green at `c09ddb9efde8f3297d3e5ab35200126f5f017bd8` /
`d31d7a80359326d525b686c67960a918c233e223`, CI `39868108451`. ChatGPT
exact-source review rejected D1S3 because its production protected-boundary
composition was not supplied. All earlier failed publications remain intact.

The reviewed R3A model distinguishes permanent per-child consumption from
root-level continuation, phase-complete evidence, quiescent parent/session-01
progression, and `ACTIVE_CURRENT_EXACT` with no fresh-start authority. R3 adds
the required exact phase/date invariant: empty root -> session 01; progression-
ready root -> session 02. A proved mismatch is
`BLOCKED / MANUAL_START_SESSION_MISMATCH`, retaining root/process observations.

R3 supplies source-owned read-only native installation/image, fixed-root replay,
current runtime/substrate, and exact process-ownership adapters. Pre-install
assessment needs no runtime process. Exact installation with an absent root
returns `READY_FOR_D1_SUCCESSOR_ROOT_PROVISIONING_REVIEW`; it never provisions.
Full readiness still requires genuinely applicable immutable manual runtime
admission. No native production preflight or execute was invoked in source work.

D1S3 remains NOT SOURCE ACCEPTED pending terminal R3 mapped CI and ChatGPT
exact-source review. FULL remains pending until that acceptance. Develop
remains accepted D1S2. All protected effects remain zero; original F1/C2
evidence is untouched; successor execution is unauthorized; live remains NO-GO.

Next owner: ChatGPT exact-source review after the single combined R3 publication
reaches terminal CI. On red, preserve evidence and stop; no automatic R3-C1/C2.
Only after source acceptance may the fresh FULL obligation be satisfied before
any merge/release-readiness boundary or protected preflight review.

R3 source tests derive empty, progression, active-01/02, completed/halted,
malformed and alias/replacement classifications from injected native facts and
actual disposable D1 replay bytes. Exact-owner tests cover PID reuse, exit,
wrong executable, denied/unprovable queries, oversized PIDs and handle closure.
Current-process/substrate observations are exercised through accepted runtime
admission with injected Win32/token/filesystem seams; mutable Python rejects.
Registered preflight reaches the real native factory under injected read-only
adapters and proves no latch/root/release/process creation. Full D1S2 readiness
retains exact phase/date and genuine applicable runtime requirements.

Retained local verification passed 1,133 affected Architecture-133 installation/
runtime, F1R1-A/B/C1, D1S1, checkpoint authority, and profile/lane cases. The
combined D1S2/D1S3 focused run passed 111 cases before the final runtime-path
and unreadable-state refinements; eight affected refinement cases also passed.
Final source/pin/Ruff checks and the complete affected D1S2/D1S3 modules are
required before the single R3 commit/push. No local canonical profile is run.

Only the unaccepted D1S3 overlay supersedes the reviewed D1S2 source/docs/tests;
predecessor maps/digests remain intact and are validated before substitution.
The current-doc mutable exception remains exactly two paths. Source inventory,
two Robinhood lanes, R1 placement pin, and the 300-second ceiling are unchanged.

Also remove or update any tests and docs that referenced the old behavior.
