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

No production release, successor root, credential, provider, paper, broker,
D1, D2, scheduler, service, startup, or live effect is authorized or created.
Original F1 remains FINAL / INDETERMINATE / CONSUMED and C2 remains consumed
and non-reusable. The next action after terminal source-gate success is
ChatGPT exact-source review; only after SOURCE ACCEPTED may a separate
read-only protected preflight be reviewed.

Also remove or update any tests and docs that referenced the old behavior.
