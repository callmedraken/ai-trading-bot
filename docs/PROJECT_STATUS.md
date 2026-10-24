# AI Trading Bot — Project Status

## Current checkpoint

Architecture 134-F1R1 has reached a **rename-publication retirement / rename-free
pivot**.

The last accepted R5 executable source remains:

    branch feature/robinhood-production-paper-134f1r1-d1s3-r5-publication-recovery-current
    accepted source HEAD ca30771c0cb441b7e4f9dc63f4cc784771cdcd44
    accepted source TREE 663782b1f1dd7f0d849637846fb40fbbf8a46c86
    docs-closeout parent 24b390d1db62264d60a9c79e6ad67303bb996e19

R5 mapped CI #702 / run `40078441427`, attempt 1 was terminal green:
10,874 canonical ROBINHOOD cases, 10,868 passed, 6 skipped, 0 failed/errors,
244.382 seconds. Source acceptance is not in question.

## Production incident and retirement decision

Corrected D1S3 had already materialized and repeatedly verified an exact immutable
staging release, but its one-shot installation stopped INDETERMINATE at
PUBLICATION and the original installation latch became permanently CONSUMED.

R5 was then intentionally reduced to one task: independently reprove that exact
preserved staging image and issue one separate no-replace publication attempt.

Registered R5 preflight on 2026-10-24 returned:

    PASS / READY_FOR_EXACT_PRESERVED_RELEASE_PUBLICATION
    IDENTITY_STABLE=True

The one-shot R5 protected execute then returned:

    INDETERMINATE
    PRESERVE_PUBLICATION_EVIDENCE_NO_RETRY
    MAY_HAVE_OCCURRED
    IDENTITY_STABLE=True

Evidence:
`F:\AI\temp\ai-trading-bot-checkpoints\arch134-f1r1-d1s3-r5-successor-release-publication-recovery\execute-20261024T091006.081295Z\report.json`.

The registered post-attempt R5 preflight returned:

    BLOCKED / CONSUMED_RECOVERY_ATTEMPT
    IDENTITY_STABLE=True

Evidence:
`F:\AI\temp\ai-trading-bot-checkpoints\arch134-f1r1-d1s3-r5-successor-release-publication-recovery\preflight-20261024T091402.387900Z\report.json`.

Under the accepted R5 state machine this closes the current namespace as consumed
R5 authority with exact STAGING still present and FINAL absent. Do not rerun R5,
rerun D1S3 installation, manually rename, delete, repair or clean either incident.

The rename/publication mechanism is now retired as a forward F1R1 path. This is
formalized in
[the rename-free pivot decision](architecture/134-f1r1-rename-free-immutable-release-pivot.md)
and as a normative non-regression rule in `AGENTS.md` and
`docs/AI_DEVELOPMENT_WORKFLOW.md`.

## Forward architecture

Keep immutable production releases, but remove directory publication/promotion.

The successor model is:

    accepted source
    -> fresh unique immutable deployment path
    -> materialize in that same path
    -> flush/seal/verify
    -> persist exact admission evidence
    -> explicitly bind runtime to that same exact path

No `.installing`->FINAL, STAGE->ACTIVE, ACTIVE->ARCHIVE, alias/junction/symlink
swap or equivalent directory namespace promotion may be required to make a
release runnable. A failed deployment stays inert and preserved; a new attempt
uses a new unique path.

The next rename-free checkpoint must add machine-enforced authority/tests so an
older branch/helper cannot silently reintroduce rename publication.

## Operational boundary and roadmap

No further D1S3/R5 protected execute is authorized. Successor root remains
uncreated and still requires a separate write-authority/ACL review before
provisioning. Runtime start, scheduler effects, credentials/provider access,
paper/broker effects, D1/D2 and live effects remain unauthorized. Original F1 is
FINAL / INDETERMINATE / CONSUMED; C2 remains consumed and immutable. Live remains
**NO-GO**.

    145-A SOURCE ACCEPTED and integrated
    -> F1R1 rename-free immutable deployment
    -> exact deployment admission
    -> successor-root write-authority review
    -> fresh manual-start F1 successor soak
    -> 145-B results/campaign bundle
    -> Research Results GUI
    -> large strategy campaigns

## Next step

Design and implement the rename-free immutable-deployment successor checkpoint.
Do not build D1S3-R6 as another rename qualification/recovery attempt.

The successor source must create a fresh unique immutable path, verify it without
renaming it, bind runtime explicitly to that exact path only after verification,
and machine-enforce the rename-free non-regression rule. No production deployment
effect is authorized by this documentation checkpoint.
