# Restart-safe paper-operation coordinator validation

## Milestone boundary

Milestone 2 provides strict operation-input loading, explicit dependency
verification, bounded operation-root inspection, deterministic classification,
and an inspect-only command. Milestone 3 adds one explicit execution attempt and
verified transition commit. Neither milestone creates or recovers a receipt or
contacts a provider, external broker, network service, scheduler, or clock.

The command is:

```text
python scripts/run_paper_operation.py \
  --config <operation-config.json> \
  --operation-root <existing-directory> \
  --inspect-only
```

`--inspect-only` remains the explicit read-only mode.

Milestone-3 execution is:

```text
python scripts/run_paper_operation.py \
  --config <operation-config.json> \
  --operation-root <existing-directory> \
  --execute-once
```

Exactly one of `--inspect-only` and `--execute-once` is required.

## Configuration schema

The strict UTF-8 JSON root contains exactly:

```json
{
  "schema_version": 1,
  "caller_idempotency_key": "<canonical-lowercase-uuid>",
  "prior_lineage_manifest": {
    "artifact_id": "<canonical-lowercase-uuid>",
    "path": "<transport-path>",
    "sha256": "<lowercase-sha256>",
    "byte_length": 1
  },
  "terminal_checkpoint": {
    "artifact_id": "<canonical-lowercase-uuid>",
    "path": "<transport-path>",
    "sha256": "<lowercase-sha256>",
    "byte_length": 1
  },
  "completed_snapshot": {
    "artifact_id": "<canonical-lowercase-uuid>",
    "path": "<transport-path>",
    "sha256": "<lowercase-sha256>",
    "byte_length": 1
  },
  "cycle_configuration": {
    "artifact_id": "<canonical-lowercase-uuid>",
    "path": "<transport-path>",
    "sha256": "<lowercase-sha256>",
    "byte_length": 1
  }
}
```

Relative artifact paths resolve against the operation-configuration directory.
Paths are transport-only and do not enter the deterministic operation identity.
The parser rejects missing, unknown, or duplicate fields; BOMs; invalid UTF-8;
floats and non-finite constants; noncanonical UUIDs or hashes; unsafe or
overlong paths; nonpositive lengths; and oversized configuration bytes.

## Verification order

Inspection safely reads and evidence-checks the explicit lineage manifest,
verifies the full lineage to `PASS`, and requires its evidence UUID to match the
manifest reference. The explicit terminal checkpoint must match the verified
terminal artifact by UUID, SHA-256, byte length, and exact bytes.

It then safely reads and verifies the completed snapshot, parses the exact
existing transition configuration, requires its request UUID to match the
configuration artifact UUID, and requires its snapshot reference to match the
verified snapshot. Only then does it derive the milestone-1 operation UUID and
existing checkpoint application UUID.

## Fixed layouts and safety

The root recognizes finalized transition directories and this operation layout:

```text
<operation-root>/
  paper-account-transition-<application-id>/
  paper-operations/
    paper-operation-<operation-id>/
      paper-operation-receipt-<operation-id>.json
```

It also recognizes transition staging at the root and operation staging below
`paper-operations`. Enumeration is bounded. Recognized directories must be real
directories with exact canonical names and exact contents. Reads require real,
stable, bounded regular files and a safe parent chain. Symlinks, reparse points,
case-fold collisions, parent identity changes, malformed names, unexpected
contents, ambiguous duplicates, and incomplete staging fail closed. Inspection
performs no filesystem mutation.

## Classification

- `PENDING`: all inputs verify and no relevant receipt, transition, staging, or
  verified competing successor exists.
- `ALREADY_APPLIED`: the exact completed receipt passes full milestone-1 offline
  verification with all exact dependencies.
- `CONFLICTING`: a different same-key receipt or competing successor is fully
  verifiable from the available exact dependencies.
- `BLOCKED`: stale predecessor, valid failed receipt, crash-left staging,
  finalized requested transition without its receipt, unsafe or ambiguous
  layout, unavailable foreign dependencies, or invalid evidence.

A verified requested transition without a receipt is reported but never repaired
in milestones 2 and 3.

## One-shot execution and commit

Execution proceeds only from an exact `PENDING` inspection. The coordinator
rechecks the operation-root identity and transition destination before invoking
the runtime. Non-pending, unsafe, stale, conflicting, staged, ambiguous, and
missing-receipt states invoke the runtime zero times.

An admitted operation invokes the existing checkpointed verified-snapshot
runtime exactly once. There is no retry path. The result remains private while
the coordinator:

1. serializes the report and successor checkpoint;
2. verifies the prospective successor edge;
3. appends exactly the current snapshot, new report, and new successor to the
   verified prior artifacts;
4. verifies the complete prospective successor lineage;
5. creates `.paper-account-transition-<application-id>.staging` exclusively;
6. writes and flushes the fixed report and checkpoint files;
7. safely rereads the staging directory and repeats edge and lineage
   verification;
8. renames staging to the final transition directory without clobber;
9. safely rereads the final directory and repeats edge and lineage verification.

Only then is `TRANSITION_COMMITTED` returned. The final transition directory is
the authoritative account-state commit point.

Both `APPLIED` and `NO_ACTION` produce the same fixed two-file transition
layout. `NO_ACTION` still commits its successor checkpoint because the ledger
time advances.

Any crash or failure before rename leaves no final transition. Once staging has
been created, it is preserved for manual review; no cleanup, repair, merge, or
overwrite occurs. A failure after rename preserves the finalized transition and
reports fail-closed. Until milestone 4 adds receipt recovery, that transition
without a receipt remains blocked on later inspection.

## Caller-key limitation

Schema-1 receipt-only operation directories do not support complete global
caller-key reuse verification. Canonical receipt parsing, directory names,
filename UUIDs, receipt fields, and hash claims are not authority.

A foreign same-key receipt establishes a conflict only after the existing
milestone-1 offline receipt verifier passes with every exact required
dependency. If any required foreign lineage, snapshot, cycle configuration,
report, or successor checkpoint dependency is unavailable, the result is
`BLOCKED` with `FOREIGN_RECEIPT_DEPENDENCIES_UNAVAILABLE`. The candidate is not
classified as conflicting and is not skipped to reach pending.

A future schema, immutable dependency bundle, or authoritative operation
registry may make conflict discovery complete. No such extension is part of
milestone 2.

## Exit codes and output

- `0`: `PENDING` or `ALREADY_APPLIED`
- `2`: usage or missing `--inspect-only`
- `3`: configuration, manifest, artifact read, or syntax failure
- `4`: input, snapshot, terminal, receipt, transition, or lineage verification
  failure
- `5`: stale terminal or deterministic idempotency/lineage conflict
- `8`: incomplete, ambiguous, unsafe, or crash-left state requiring manual
  review

Execution additionally uses:

- `0`: `TRANSITION_COMMITTED`
- `4`: prospective, staged, or finalized edge/lineage verification failure
- `5`: stale terminal or verified conflict
- `6`: recognized deterministic paper-cycle rejection
- `7`: serialization, runtime exception, staging, rename, or output-safety
  failure
- `8`: staging, ambiguity, or a finalized transition without its receipt

Human output is limited to the operation UUID when derivable, classification,
terminal checkpoint UUID, application UUID when derivable, a receipt path only
for a fully verified receipt, and stable diagnostic codes.

## Verification commands

```text
python -m pytest tests/cli/test_paper_operation_config.py tests/cli/test_paper_operation_inspection.py -q
python -m pytest tests/cli/test_paper_operation_execution.py -q
python -m pytest tests/runtime/test_paper_operation.py -q
python -m pytest tests/cli/test_checkpoint_transition.py tests/cli/test_checkpoint_lineage.py tests/runtime/test_paper_account_lineage_verification.py -q
python -m pytest
ruff check .
ruff format --check .
git diff --check
```
