# Architecture 134-F1R1 — Rename-free immutable-release pivot and non-regression decision

## Decision

The current forward production-release architecture is pivoting to a
**rename-free immutable-release model**.

This decision retires directory rename/publication as a required correctness
boundary for Architecture 134-F1R1 and its successors. It preserves the security
properties that motivated immutable releases while removing the Windows
directory-rename mechanism that repeatedly blocked forward progress.

This record is normative together with the matching rules in `AGENTS.md` and
`docs/AI_DEVELOPMENT_WORKFLOW.md`.

## Why the pivot is required

The earlier Architecture-134 F1 paper soak successfully started because its
runtime admitted and launched exact frozen Git worktrees/D1R7/D1R8 source. It did
not require a freshly materialized immutable release directory to be promoted by
rename before execution.

F1R1 deliberately hardened that model by separating production runtime from the
mutable development checkout and requiring an immutable installed release. That
hardening was sound, but the implementation retained a directory publication
transition:

    exact release materialization
    -> verify .installing image
    -> rename .installing to final
    -> admit final release

The repository already had substantial historical evidence that Windows
directory rename choreography was fragile in this environment. Architecture-133
included repeated rename qualification/reconciliation/recovery work, including
closed-descendant qualification. Earlier Architecture-125/133 work had already
motivated reducing ACTIVE/STAGE/ARCHIVE rename choreography.

The same failure family then reappeared in F1R1:

1. Corrected D1S3 source was accepted/integrated at
   `ad4c3d3334048054df6d8f046040349619c277f2`.
2. D1S3 materialized and verified the exact immutable staging release, but its
   protected installation stopped at PUBLICATION with
   `INDETERMINATE / MAY_HAVE_OCCURRED /
   PRESERVE_INSTALLATION_EVIDENCE_NO_RETRY`.
3. Read-only reconciliation proved FINAL absent, exact STAGING present and
   stable, with repeated identical image replay.
4. D1S3-R5 was then built specifically to remove installation/materialization
   from the recovery and attempt only one exact no-replace publication of that
   already verified staging image.
5. R5 source plus bounded C1 was accepted at
   `ca30771c0cb441b7e4f9dc63f4cc784771cdcd44`, tree
   `663782b1f1dd7f0d849637846fb40fbbf8a46c86`; mapped CI #702 /
   `40078441427` was terminal green.
6. The registered R5 production preflight on 2026-10-24 returned
   `PASS / READY_FOR_EXACT_PRESERVED_RELEASE_PUBLICATION`.
7. The one-shot protected R5 publication then returned
   `INDETERMINATE / MAY_HAVE_OCCURRED /
   PRESERVE_PUBLICATION_EVIDENCE_NO_RETRY`. Evidence:
   `F:\AI\temp\ai-trading-bot-checkpoints\arch134-f1r1-d1s3-r5-successor-release-publication-recovery\execute-20261024T091006.081295Z\report.json`.
8. The registered post-attempt read-only R5 preflight returned
   `BLOCKED / CONSUMED_RECOVERY_ATTEMPT`. Evidence:
   `F:\AI\temp\ai-trading-bot-checkpoints\arch134-f1r1-d1s3-r5-successor-release-publication-recovery\preflight-20261024T091402.387900Z\report.json`.
   Under the accepted R5 classifier this means the separate R5 latch is consumed
   while the exact verified staging image remains and FINAL is absent.

The recovery designed solely to cross the rename boundary therefore failed to
commit that same boundary. This crosses the project's pivot threshold: do not
build another increasingly elaborate recovery around the same primitive.

## Forward invariant

A future immutable deployment has one source-owned unique directory identity.
That path exists before bytes are materialized and never changes.

Conceptually:

    accepted source
      -> allocate unique immutable deployment path
      -> create/materialize only inside that path
      -> flush/seal
      -> verify exact manifest/inventory/Python/ACL/source identity
      -> persist admission evidence
      -> bind runtime explicitly to that same exact path

There is no filesystem promotion step between "materialized" and "runnable".
Runnable status is represented by verified evidence/binding, not by changing the
directory's name.

A failed or ambiguous deployment is simply an inert unique deployment. It is not
renamed, promoted, repaired or cleaned in order to continue. A fresh attempt uses
a fresh unique path. Historical failed deployment directories remain evidence
until a separately reviewed housekeeping boundary says otherwise.

This retains the desired security properties:

- production does not execute from the mutable development checkout;
- source HEAD/tree and complete inventory remain bound and reproducible;
- Python/runtime identity remains explicit;
- release ACL/security policy remains exact and read-only admitted;
- unattended runtime performs no Git/update/install/publication operation;
- prior verified releases remain independently addressable for supervised
  rollback/rebinding;
- runtime selection is an explicit reviewed binding to an exact immutable path.

## Retired mechanisms

The following are not forward deployment mechanisms:

- D1S3 `.installing` -> FINAL publication;
- D1S3-R5 preserved-image publication;
- Architecture-133 ACTIVE/STAGE/ARCHIVE rename recovery/qualification paths;
- Architecture-125 historical protected replacement rename choreography;
- any future "current", "active", "final", alias, junction or symlink promotion
  whose namespace mutation is required to make an immutable release runnable.

Their source/evidence may remain for historical certification, incident
reconstruction or LEGACY coverage. They may not be invoked to recover the
current F1R1 path.

No further D1S3 or R5 protected execute is authorized. Their consumed authorities
remain consumed.

## Required machine enforcement in the successor checkpoint

Documentation alone is insufficient. The next rename-free source checkpoint must
make this decision executable.

It must add source-owned authority/tests that fail closed if the current
deployment path:

- imports or invokes the retired D1S3/R5 publication writers;
- imports or invokes historical 125/133 rename operators as a deployment
  shortcut;
- requires `SetFileInformationByHandle(FileRenameInfo)`, `MoveFile*`,
  `os.rename`, `Path.rename`, replace-existing directory publication, or
  equivalent directory namespace promotion for release readiness;
- binds runtime to a path before exact complete verification;
- treats a failed deployment path as reusable retry authority;
- requires cleanup/repair of a failed deployment before a fresh unique attempt.

The successor must also update the current checkpoint inventory/dispatch so R5
cannot be selected as the forward production deployment operator. Historical
tests/evidence may remain in LEGACY or explicit incident coverage.

## Architecture-reversal gate

Reintroducing directory-rename publication later is forbidden by default.

It may happen only through a new explicit architecture-reversal decision that:

1. identifies this decision and the D1S3/R5 incident evidence;
2. demonstrates why the rename-free architecture cannot satisfy the then-current
   requirement;
3. receives explicit user approval to reverse the invariant;
4. qualifies the exact proposed primitive on disposable host-owned state;
5. defines migration, failure reconciliation and non-regression behavior;
6. completes fresh exact-source and protected-effect review.

An inherited old branch, stale test, historical helper, compatibility argument,
small correction or "temporary" workaround is never sufficient authority to
reverse this decision.

## Current preserved incident state

At the time of this decision:

- original D1S3 installation attempt: CONSUMED;
- R5 publication attempt: CONSUMED;
- R5 post-attempt reconciliation:
  `BLOCKED / CONSUMED_RECOVERY_ATTEMPT`;
- exact D1S3/R5 staging image remains the preserved incident object;
- FINAL remains absent under the accepted R5 classifier;
- automatic retry is NOT_AUTHORIZED;
- no manual rename, delete, repair or cleanup is authorized;
- successor root remains uncreated;
- runtime start remains unauthorized;
- live remains NO-GO.

## Next architecture

The next source milestone is a rename-free F1R1 immutable deployment checkpoint.
Its detailed naming may be frozen during implementation planning, but its
contract must follow this decision.

After rename-free immutable deployment is accepted and host-qualified:

    rename-free immutable deployment
    -> exact read-only deployment admission
    -> successor-root write-authority/ACL review
    -> manual-start successor soak
    -> fresh F1 successor evidence
    -> Architecture 145-B
    -> Research Results GUI
    -> large strategy campaigns

No further rename-recovery checkpoint belongs between the current incident and
the rename-free successor.
