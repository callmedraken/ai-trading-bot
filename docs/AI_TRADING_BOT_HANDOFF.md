# AI Trading Bot — Current Handoff

## Verified boundary

Architecture 134-F1R1 has pivoted away from filesystem rename publication.

Accepted R5 source remains `ca30771c0cb441b7e4f9dc63f4cc784771cdcd44` /
`663782b1f1dd7f0d849637846fb40fbbf8a46c86`; mapped CI #702 /
`40078441427` was terminal green. The issue is operational, not source
certification.

The R5 registered preflight proved the exact preserved staging release ready for
one publication attempt. That protected attempt then stopped:

    PRIMARY_STATUS=INDETERMINATE
    PRIMARY_REASON=PRESERVE_PUBLICATION_EVIDENCE_NO_RETRY
    EFFECT_DISPOSITION=MAY_HAVE_OCCURRED
    IDENTITY_STABLE=True

Execute evidence:
`F:\AI\temp\ai-trading-bot-checkpoints\arch134-f1r1-d1s3-r5-successor-release-publication-recovery\execute-20261024T091006.081295Z\report.json`.

The required registered reconciliation then returned:

    PRIMARY_STATUS=BLOCKED
    PRIMARY_REASON=CONSUMED_RECOVERY_ATTEMPT
    IDENTITY_STABLE=True

Reconciliation evidence:
`F:\AI\temp\ai-trading-bot-checkpoints\arch134-f1r1-d1s3-r5-successor-release-publication-recovery\preflight-20261024T091402.387900Z\report.json`.

Accepted R5 semantics therefore establish consumed R5 authority with exact
STAGING still present and FINAL absent. R5 execute must never be run again.

## Normative pivot

The forward release architecture is now **rename-free**. Read
[Architecture 134-F1R1 rename-free pivot](architecture/134-f1r1-rename-free-immutable-release-pivot.md)
plus the normative rules in `AGENTS.md` and
`docs/AI_DEVELOPMENT_WORKFLOW.md` before any new deployment work.

Do not create another rename-recovery checkpoint.

Do not use or adapt as a current deployment path:

- D1S3 `.installing`->FINAL publication;
- R5 preserved-image publication;
- Architecture-133 ACTIVE/STAGE/ARCHIVE rename operators;
- Architecture-125 historical protected replacement rename choreography;
- any alias/junction/symlink/current-name swap required to make a release
  runnable.

The new model keeps immutable production copies but gives each deployment one
unique path that never changes. Materialize, seal and verify that same path;
runtime admission then binds explicitly to it. A failed path stays inert and
preserved, while a later attempt uses a new unique path.

The first rename-free implementation must add machine-enforced authority/tests
that reject reintroduction of the retired primitives in the current production
deployment path. Reintroducing directory publication later requires an explicit
architecture-reversal decision and explicit user approval; it cannot arrive via
an old branch, compatibility patch, C1/C2 correction or "temporary" workaround.

## Preserved incident boundary

Do not:

- rerun D1S3 installation;
- rerun R5 publication;
- delete or rewrite either consumed latch;
- manually rename the preserved staging directory;
- delete/repair/clean the preserved staging/final namespace;
- reuse historical 125/133 recovery operators;
- provision successor root;
- start runtime;
- touch scheduler, credentials/providers, paper/broker, D1/D2 or live effects.

The preserved incident is evidence, not a blocker that must be repaired before
forward progress.

## Next milestone

Next: **rename-free F1R1 immutable deployment source checkpoint**.

Required contract:

    fresh unique immutable deployment path
    -> create/materialize only there
    -> flush and seal
    -> exact repeated verification
    -> durable admission evidence
    -> runtime binds to that exact unchanged path

No directory promotion/rename step exists.

After source acceptance and separate host qualification:

    exact rename-free deployment admission
    -> successor-root write-authority/ACL review
    -> manual-start fresh F1 successor soak
    -> 145-B
    -> Research Results GUI
    -> large strategy campaigns

Original F1 remains FINAL / INDETERMINATE / CONSUMED; C2 remains consumed and
immutable; live remains NO-GO.
