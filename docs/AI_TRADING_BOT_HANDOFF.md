# AI Trading Bot — Current Handoff

## Verified boundary

Architecture 134-F1R1-D1S3-R5 plus bounded C1 is **SOURCE ACCEPTED**.

Accepted source identity:

    branch feature/robinhood-production-paper-134f1r1-d1s3-r5-publication-recovery-current
    base   ad4c3d3334048054df6d8f046040349619c277f2
    HEAD   ca30771c0cb441b7e4f9dc63f4cc784771cdcd44
    TREE   663782b1f1dd7f0d849637846fb40fbbf8a46c86
    parent 2ca63594fc00fbc3dda941f1c07aa8156d0b1875

Corrected D1S3 remains accepted/integrated at
`ad4c3d3334048054df6d8f046040349619c277f2` /
`b4cbf3039171673d3fba44e4999b172e658a4f91`. Its registered read-only
preflight passed INSTALL_REQUIRED after attempting the fixed latch read and
establishing AVAILABLE from absence; it did not create, consume or mutate the
latch.

The later protected installation consumed its one-shot attempt and stopped
INDETERMINATE at PUBLICATION / MAY_HAVE_OCCURRED /
PRESERVE_INSTALLATION_EVIDENCE_NO_RETRY. Automatic retry and installation rerun
are forbidden. Subsequent registered preflight was BLOCKED /
INSTALLATION_BLOCKED with the original attempt CONSUMED.

Read-only localization proved exact FINAL absent, exact STAGING present at
identity `(1855336320, 281474982917732)`, stable repeated namespace and two
identical immutable staging replays without error. Exact incident paths/digests,
release/image/Python identities and source constants are frozen in the
[R5 architecture](architecture/134-f1r1-d1s3-r5-successor-release-publication-recovery.md).

## R5 accepted source

Checkpoint:
`arch134-f1r1-d1s3-r5-successor-release-publication-recovery`.

Worktree:
`F:\AI\worktrees\ai-trading-bot-production-paper-134f1r1-d1s3-r5-publication-recovery-current`.

R5 has its own separate recovery latch:
`F:\AI\temp\arch134-f1r1-d1s3-r5-publication-recovery-attempt\attempt.json`.
The original D1S3 installation latch is non-substitutable and permanently
non-reusable.

The accepted source implements:

- read-only reconciliation both before and after any R5 latch consumption;
- repeated frozen incident/source/namespace/image admission;
- a separate durable one-shot R5 fence;
- lazy import of the native mutation module only after durable latch readback;
- one exact handle-relative `SetFileInformationByHandle` rename request with
  ReplaceIfExists FALSE;
- repeated exact FINAL replay after publication;
- terminal post-fence ambiguity with automatic retry NOT_AUTHORIZED.

Historical `installation_reconciliation.py`, `publication_recovery.py` and
`native_publication.py` are byte-identical to the accepted predecessor.
The D1S3 installation operator and corrected native-read adapter are also
unchanged. Historical 133-AJ dispatch cannot substitute for R5.

## CI and bounded C1

Initial R5 commit `2ca63594fc00fbc3dda941f1c07aa8156d0b1875`, tree
`45babb6a6736dac03b426d132f2791b56f4bc5e0`, preserved failed mapped CI
#701 / run `40077868296`, attempt 1. Source-static passed; seven active/canonical
failures were all `test_exact_current_source_admission_rejects_drift` fixture
cases raising `R5_IMPORT_SOURCE_REJECTED` because the test assumed the fixed
operator worktree while CI executes from a relocated checkout.

Bounded C1 `ca30771c0cb441b7e4f9dc63f4cc784771cdcd44` changes only that test fixture,
the validation record and their blob pins. It supplies an explicit relocated
synthetic source root, preserves the real production worktree constant, and adds
a negative wrong-import-origin test before Git observation. No production/native
R5 code or predecessor authority changed.

Mapped CI #702 / run `40078441427`, attempt 1 is terminal green:
source-static, active-tests, certification-tests and source-gates PASS; full-tests
is intentionally skipped. Canonical ROBINHOOD selected 110 modules in
28/27/29/26 lanes and completed 10,874 cases / 10,868 passed / 6 skipped /
0 failed / 0 errors in 244.382 seconds. Artifact
`canonical-certification-robinhood` ID 12554615460 has SHA256
`38bbdc9f95f008c40f2ff811ba1f99abc9f0d63ba14309cf31f7310b18097a91`.

Do not duplicate canonical certification locally.

## Next action and stop boundary

Next is a separately reviewed **registered R5 read-only production preflight**.
It may observe exact current R5 source, the immutable incident records,
Administrator status, the preserved FINAL/STAGING namespace, exact image replay
and R5 latch state. It must not create the R5 latch, issue publication, repair or
clean state, provision the successor root, start runtime, touch scheduler,
credentials/providers, paper/broker state, or create D1/D2/live effects.

Expected unchanged-state result:

    PASS / READY_FOR_EXACT_PRESERVED_RELEASE_PUBLICATION
    execute_eligible = true
    attempt_state = AVAILABLE
    namespace = EXACT_STAGING_ONLY

Any BLOCKED or INDETERMINATE result stops progression. A preflight PASS still
does **not** authorize protected R5 execute. Protected publication requires a
fresh separate effect review and explicit user execution of the exact reviewed
command.

Publication success would grant neither successor-root provisioning nor runtime
start. Root remains uncreated; its future reserve/append write-authority question
needs separate architecture review because IMAGE_ACES grants Trading
read/execute only.

Original F1 remains FINAL / INDETERMINATE / CONSUMED; C2 remains consumed and
immutable. Fixed 2026-11-02/03 successor sessions retain manual-start,
reboot-stop and fresh-admission behavior. Scheduler, credentials, provider,
paper, broker, D1/D2 and live actions remain excluded. Live remains NO-GO.

Roadmap: F1R1 recovery/hardening -> fresh F1 successor soak -> 145-B -> Research
Results GUI -> large strategy campaigns. Accepted 145-A remains separate/offline.
