# Validation — D1S3-R5 preserved-release publication recovery

Source-only checkpoint:
`arch134-f1r1-d1s3-r5-successor-release-publication-recovery`.
Base HEAD `ad4c3d3334048054df6d8f046040349619c277f2`, tree
`b4cbf3039171673d3fba44e4999b172e658a4f91`.

The [architecture](../architecture/134-f1r1-d1s3-r5-successor-release-publication-recovery.md)
owns exact incident, source, release, image, Python and new latch constants.
Never refresh those constants from production state merely to pass tests.

Focused source tests cover read-only staging and consumed-final reconciliation,
all closed namespace cases, exact incident digests/semantics, original latch
non-reuse, exclusive new latch reservation, flush/fsync/readback failures,
source/host/incident rejection, exact native handle-relative no-replace record,
one call only, lazy writer import after durable readback, repeated FINAL replay,
identity preservation, exact parent namespace delta and terminal post-fence
ambiguity including KeyboardInterrupt/SystemExit. Native seams are injected;
no production preflight, protected execute or production mutation is run.

Retain D1S1/D1S2/D1S3, affected checkpoint authority and certification inventory
coverage. The new review_paper test module is automatically supported/Robinhood
owned. Required 122/49 baselines, accepted measured timing maps, six/four-lane
algorithms, historical serial lane and 300-second ceiling remain unchanged. The
new module uses the reviewed timing fallback. Historical 133-AJ remains inactive
in source CI and cannot substitute for R5.

Run focused pytest with fresh unique `F:\AI\temp\pytest\...` basetemp, combined
non-mutating Ruff lint/format diagnostics and `git diff --check` before the one
atomic commit/ordinary push. GitHub owns mapped canonical ROBINHOOD; do not run
a duplicate local certification. Terminal CI and ChatGPT exact-source review
precede acceptance. Preserve failed evidence; a bounded mechanical C1/C2 is a
separate declared corrective checkpoint under the repository workflow.

No recovery execution has occurred. After accepted-source review, a separately
reviewed registered read-only preflight must independently prove the incident
and image; the ad hoc diagnostic is not authority. Successor-root policy and
provisioning remain separate architecture/effect boundaries.

## Preserved initial CI and bounded C1

Initial source `2ca63594fc00fbc3dda941f1c07aa8156d0b1875`, tree
`45babb6a6736dac03b426d132f2791b56f4bc5e0`, push run #701 /
`40077868296`, attempt 1, is terminal FAILURE and remains preserved.
Source-static passed. Active tests recorded 2,139 passed / 7 failed. Canonical
ROBINHOOD selected 110 modules in 28/27/29/26-module lanes: 10,873 cases,
10,860 passed, six skipped, seven failed, zero errors, 164.587 seconds wall.
The unchanged 300-second hygiene gate passed.

All seven failures were the positive source-admission test fixture raising
R5_IMPORT_SOURCE_REJECTED because it assumed the fixed operator worktree on a
relocated CI checkout. C1 supplies an explicitly relocated synthetic source root
and matching imported-module path to that fixture on every host. A separate
negative case rejects a mismatched import origin before Git observation, and
the real production worktree constant remains independently frozen. Production
admission/recovery/native code, authority semantics and predecessor maps are
unchanged. Only this test, its R5 blob pin and this validation record change.
No production preflight or recovery execute runs in C1. The replacement ordinary
push owns one fresh mapped ROBINHOOD run; the failed run is never rerun unchanged.

Also remove or update any tests and docs that referenced the old behavior.
