# Restart-safe paper-operation coordinator: manual end-to-end validation

## 1. Scope and non-goals

This report records the completed manual validation of the restart-safe,
locally single-writer paper-operation coordinator on the repository state
identified below. It covers explicit input verification, one-shot `NO_ACTION`
execution, verified successor commitment, receipt commitment and recovery,
terminal deterministic failure, restart inspection, and copy-only tamper
detection.

The validation did not use a scheduler, daemon, service, loop, polling,
database, cloud registry, distributed lock, multi-host coordination, broker
account, real-money path, or coordinator provider call. Daily snapshot capture
remained a separate explicit Alpaca snapshot command. No validation case
modified source lineage, checkpoints, snapshots, finalized source evidence, or
tracked test fixtures.

## 2. Repository commit and branch used

| Item | Value |
| --- | --- |
| Branch | `feature/restart-safe-paper-operations` |
| Commit | `12bb78aa3cc8ff6f310fbac24ca3c1d14305fca2` |
| Commit subject | `Support verified successor priors in checkpoint CLI` |
| Commit timestamp | `2026-07-29T01:17:05-07:00` |

The generated validation roots and inputs are ignored local evidence beneath
`local-paper-operation-validation/`; they were not staged or committed.

## 3. Source lineage, terminal checkpoint, and snapshot evidence

The verified prior lineage evidence ID was
`ffb61e3a-2ad2-5840-a546-fd5e28ec3edb`. Its source manifest, terminal, and
corrected completed snapshot were all verified offline before the successful
operation.

| Artifact | Domain ID / evidence | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `paper-account-lineage.json` | prior-lineage evidence `ffb61e3a-2ad2-5840-a546-fd5e28ec3edb` | 2423 | `cec82e64219cee260f6f27cefce1e003e7b722460b983cbbbea415343c05dc67` |
| Sequence-2 terminal checkpoint | `d351a551-f701-5c9d-89bd-dfd3842ad24c` | 1273 | `019408976c7eed80dc9f2bc6f76c4b9b8578b1982a78c6173f23163c8da05591` |
| Corrected completed daily snapshot | `21164c17-9b52-56d2-aa9f-75e9668ecbfd` | 1460 | `e0d86c29d1e6d074324d7ff2b0af6d3d75b8fb91445bdf7f6d73c84d9b51f914` |

The terminal had sequence `2`, cash `10000`, empty positions, and `as_of`
`2026-07-28T09:46:16.061234Z`. The corrected snapshot was captured at
`2026-07-29T06:43:50.311210Z`, strictly later than that terminal time, and its
offline verifier passed with required `SPY` and `QQQ` daily evidence.

## 4. Case 1: inspect-only `PENDING`

Case 1 used an empty root and explicit schema-1 operation configuration. The
strict configuration loaders and UTF-8-without-BOM checks passed. Inspect-only
returned `PENDING`, exit `0`, terminal
`d351a551-f701-5c9d-89bd-dfd3842ad24c`, operation
`f14b59c5-f1bd-5ea4-9b3c-dfd939a535ea`, and application
`1ce5d9fe-853a-55a1-bc73-784cacdf68c4`. The operation root remained empty.

## 5. Initial chronology blocker and safe failure

The first Case-2 execution used the Case-1 identity and passed inspect-only but
returned `BLOCKED` / `RUNTIME_EXCEPTION`, exit `1`, during the admitted cycle.
Diagnosis established a cross-artifact chronology conflict: the cycle's
explicit execution timeline did not satisfy the later snapshot relationship
required by the checkpointed verified-snapshot runtime. The empty Case-2 root
contained no final transition, staging, receipt, or other ambiguous operation
state. It was preserved and never retried.

This demonstrated that inspection verifies the explicit evidence and current
predecessor, while runtime admission additionally enforces the cross-artifact
chronology contract. It also demonstrated fail-closed handling before any
account-state commit.

## 6. Corrected snapshot capture and chronology

One new explicit `SPY`/`QQQ` daily snapshot was captured through the supported
Alpaca daily-snapshot path and then verified offline. No coordinator provider
call or paper-account connection was used. Fresh caller-authored request,
target, and caller-idempotency UUIDs were used for the corrected request; its
planning, submission, and fill timestamps were explicit, strictly ordered, and
later than both the sequence-2 terminal `as_of` and the new snapshot
`captured_at`.

The corrected files were strict canonical UTF-8 JSON without BOM:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `local-paper-operation-validation/inputs/case-02b-checkpointed-cycle-config.json` | 1569 | `0b6a944b12575dcb1c20fdbc2f9e080ebddd8250d9ae8faa679c7ad3c4ed9182` |
| `local-paper-operation-validation/inputs/case-02b-paper-operation-config.json` | 1252 | `6df128991a6ccfd1bc695217b449c3056d7c652dfefdfe875a21c1c78f0ca54e` |

Case-02b inspect-only in a new empty root returned `PENDING`, exit `0`, for
operation `d02f39e4-e076-561a-8b5a-0f7620fe66c3` and application
`fc27db15-b8ca-501a-9e5f-53f6b1b0f802`, with no root mutation.

## 7. Successful `NO_ACTION` operation

Exactly one `--execute-once` invocation was admitted from Case-02b `PENDING`.
It returned `COMPLETED` / `NO_ACTION`, exit `0`, with:

| Item | ID |
| --- | --- |
| Operation | `d02f39e4-e076-561a-8b5a-0f7620fe66c3` |
| Application | `fc27db15-b8ca-501a-9e5f-53f6b1b0f802` |
| Cycle result | `7d696e4f-1a7d-5b26-aab1-725a7cd5802d` |
| Report | `94b0b2fa-9145-5f66-bc47-5fe0f09eddcf` |
| Successor checkpoint | `2b713146-81f0-5b5a-9714-fe0602d58811` |

The finalized root has exactly one two-file transition and one one-file
operation receipt, with no transition or receipt staging:

```text
local-paper-operation-validation/case-02b-success-root/
  paper-account-transition-fc27db15-b8ca-501a-9e5f-53f6b1b0f802/
    checkpointed-paper-cycle-report-7d696e4f-1a7d-5b26-aab1-725a7cd5802d.json
    paper-account-checkpoint-2b713146-81f0-5b5a-9714-fe0602d58811.json
  paper-operations/
    paper-operation-d02f39e4-e076-561a-8b5a-0f7620fe66c3/
      paper-operation-receipt-d02f39e4-e076-561a-8b5a-0f7620fe66c3.json
```

## 8. Sequence-3 successor evidence

| Artifact | Bytes | SHA-256 | Verified result |
| --- | ---: | --- | --- |
| Transition report | 3212 | `5111d899c32ea3eac2fad95b4fd380fdd73cae92fadd19f729ad54d238f6b721` | `NO_ACTION` |
| Successor checkpoint | 1266 | `201a06c625e3c0c6da7490d532bfa1a903fc1c0536ca2a1176ea19663d10c628` | sequence `3`; predecessor is sequence-2 terminal; cash `10000`; positions empty |
| Completed receipt | 10097 | `206e2b7ccd4cfb525a99ac1d9045fc428f855ef3174f3443142eb92adfd408ae` | `COMPLETED` / `NO_ACTION` |

The successor edge verifier passed after verified prior authority was supplied.
The complete successor-lineage verifier passed with evidence ID
`9203c0eb-a317-50af-8164-bc71c0c009a6`, terminal
`2b713146-81f0-5b5a-9714-fe0602d58811`, and edge count `3`. The milestone-1
offline receipt verifier also passed with the exact operation and application
IDs above.

## 9. Standalone edge-verifier defect and fix

The initial standalone edge-verifier invocation returned exit `6` even though
the coordinator's finalized verification and full-lineage verification passed.
The standalone CLI accepted a raw prior checkpoint only, so it could validate a
genesis-rooted edge but could not authenticate a prior checkpoint that was
itself a verified successor.

The narrow fix added an optional explicit `--prior-lineage-manifest` input. It
fully verifies that manifest, requires its terminal checkpoint's ID, SHA-256,
and byte length to match `--prior-checkpoint`, derives
`VerifiedPriorCheckpoint` through the public conversion API, and only then
calls the unchanged public successor-edge verifier. It does not infer authority
from sequence number, path, filename, timestamps, or checkpoint contents.

With the fixed CLI and `--prior-lineage-manifest .\\paper-account-lineage.json`,
the Case-02b edge passed with exit `0`. Genesis behavior without that option
remained covered by focused tests.

## 10. Repeated-invocation `ALREADY_APPLIED` evidence

One repeated `--execute-once` invocation against the finalized Case-02b root
returned initial and final `ALREADY_APPLIED`, diagnostic `ALREADY_APPLIED`, and
exit `0`. It emitted the existing transition and receipt paths and no new
cycle-result or successor IDs.

Before and after inventories were exactly equal: two root entries, three
directories, three regular files, identical relative paths, SHA-256 values,
byte lengths, and modification timestamps. A subsequent inspect-only command
also returned `ALREADY_APPLIED`, exit `0`, without writes. Receipt, edge, and
three-edge lineage reverification all passed.

## 11. Committed-transition receipt recovery

Case 3 used a separate root containing an exact verified Case-02b transition
but no receipt. `--execute-once` performed recovery, returned
`RECEIPT_RECOVERED`, and did not invoke the cycle runtime. It wrote only the
canonical receipt in the fixed operation layout. The report and successor
checkpoint retained their original bytes, hashes, and lengths; the recovered
receipt was byte-identical to the completed Case-02b receipt.

This confirms the final transition directory is the authoritative account-state
commit point, and a missing operation receipt can be reconstructed only after
the existing transition, successor edge, and complete successor lineage verify.

## 12. Crash-left receipt staging behavior

Case 4 created only the recognized empty directory:

```text
local-paper-operation-validation/case-04-crash-staging-root/
  paper-operations/
    .paper-operation-d02f39e4-e076-561a-8b5a-0f7620fe66c3.staging/
```

Inspect-only and one `--execute-once` invocation both returned `BLOCKED`,
diagnostic `OPERATION_STAGING_EXISTS`, and exit `8`. No runtime execution,
cleanup, finalization, receipt, transition, staging replacement, or other write
occurred. The empty staging directory and all pre-invocation paths and mtimes
remain preserved for manual review.

## 13. Deterministic `INSUFFICIENT_CASH` `FAILED` receipt

Case 5 used a fresh explicit request, target, and caller key. Its target was
`SPY = 0`, `QQQ = 14`, and cash `543.14`; the close-marked QQQ notional
`9456.86` plus target cash equals `10000`. The caller-asserted QQQ next open
was `715`, so the required buy cost was `10010`, strictly greater than
available cash. The pure in-memory precheck raised exactly
`CheckpointedVerifiedSnapshotPaperCycleInsufficientCashError`.

| Item | Value |
| --- | --- |
| Request ID | `f5381e38-a098-4e6b-9405-189e64561fe7` |
| Target ID | `a5289932-30cd-4f6c-8e4d-0b442e19a23e` |
| Caller idempotency key | `256c20fa-ad8b-4d88-b872-720eff0268bd` |
| Operation ID | `813c84f5-bef9-56d0-ba09-d53892229ef3` |
| Application ID | `e447660a-6eb2-53d6-a554-cf464264f736` |
| Cycle configuration | 1574 bytes; `f03445a247ea753750537fc79b3cc8922a63dd1f20962df30da53ca116a9e945` |
| Operation configuration | 1258 bytes; `83acf0e15de3da487411f0c224815c455f107195e34109c6cdd9f4c840e6dad4` |
| Failed receipt | 6904 bytes; `e38d38d8c0291b899994945d57bc2c03b04566bb704c28d52a0971a46b873e1e` |

The admitted command returned `EXECUTION_FAILED` /
`INSUFFICIENT_CASH`, exit `6`, and finalized exactly one canonical `FAILED`
receipt. Offline receipt replay passed. No transition directory or transition
staging directory was created.

## 14. Repeated failed-operation behavior

One repeated `--execute-once` invocation fully verified the failed receipt,
returned the recorded `EXECUTION_FAILED` / `INSUFFICIENT_CASH` result with exit
`6`, and made no writes or runtime retry. Inspect-only returned `BLOCKED`,
diagnostic `VALID_FAILED_RECEIPT`, exit `8`. The failed receipt remains the
terminal audit evidence; it has no result, report, successor checkpoint, or
state advance.

## 15. Tamper detection

Each tamper case used a newly created isolated copy. Initial copied inventories
matched their source files by SHA-256 and byte length. Exactly one byte in one
copied JSON artifact changed; no source artifact was edited.

| Case | Intentional mutation | Before SHA-256 | After SHA-256 | Result |
| --- | --- | --- | --- | --- |
| Completed receipt | offset `361`, ASCII `e` (`101`) to `0` (`48`), 10097 bytes | `206e2b7ccd4cfb525a99ac1d9045fc428f855ef3174f3443142eb92adfd408ae` | `0938bc81b9f4c03751460c09ce6de06d90010ffa71dfe42fa4e95093fd55967b` | Offline receipt verifier `RECEIPT_SCHEMA_FAILURE`; inspect and execute both `BLOCKED` / `INVALID_RECEIPT`, exit `4` |
| Transition report | offset `1030`, ASCII `0` (`48`) to `1` (`49`), 3212 bytes | `5111d899c32ea3eac2fad95b4fd380fdd73cae92fadd19f729ad54d238f6b721` | `829fe5224847c2231c0fe86bdc10dded0584806f9eed177105094272c363907d` | Edge CLI failed, exit `6`; lineage `REPORT_REFERENCE_CONFLICT`; receipt `TRANSITION_EVIDENCE_MISMATCH`; inspect and execute `BLOCKED` / `INVALID_RECEIPT`, exit `4` |
| Failed receipt | offset `340`, ASCII `e` (`101`) to `0` (`48`), 6904 bytes | `e38d38d8c0291b899994945d57bc2c03b04566bb704c28d52a0971a46b873e1e` | `b26c7573724847ae2bf141654d0b856e4e06bdb23f53bab39e80e7f1b4c10cf5` | Strict parse and offline verifier failed with `RECEIPT_SCHEMA_FAILURE`; inspect and execute `BLOCKED` / `INVALID_RECEIPT`, exit `4` |

All non-mutated copied files remained byte-identical to their source. In every
tamper root, coordinator invocations performed no repair, overwrite, staging,
replacement, cleanup, transition mutation, or retry.

## 16. Hashes, byte lengths, IDs, classifications, and exit codes

The tables in sections 3, 6, 7, 8, 13, and 15 are the authoritative compact
record of artifacts and immutable values. Classifications and exit results are
summarized in the acceptance matrix below. IDs are taken from verified content
or command output, not from directory or filename assumptions.

## 17. Filesystem invariants and no-write evidence

All operation roots were created separately beneath
`local-paper-operation-validation/`. The successful root retained the exact
fixed layout: one finalized two-file transition plus one finalized one-file
receipt. Repeated, recovery, staging, failed, and tamper cases used recursive
before/after inventories. Hashes and byte lengths were the authoritative
evidence; unchanged mtimes were supplemental evidence only.

No case created an unexpected transition, receipt, staging directory, marker,
lock, temporary file, or output under `reports/`. Staging was never removed;
incomplete staging stayed blocked. The successful source transition and
receipt, the recovered transition copy, the original source manifest,
checkpoints, and snapshot remained unchanged.

## 18. Platform-dependent skipped symlink tests

The repository's safety suites conditionally skip symlink tests when Windows
directory-symlink creation is unavailable. Relevant tests explicitly record
this platform limitation in the daily-snapshot, checkpoint-lineage,
paper-operation receipt-output, and research-session validation suites. This
manual validation did not create links, symlinks, or reparse points, so it does
not claim runtime coverage of an unavailable platform capability. The
coordinator's documented fail-closed link/reparse policy remains unchanged.

## 19. Final acceptance criteria

| Case | Expected result | Actual result | Exit code | Filesystem mutation | Status |
| --- | --- | --- | ---: | --- | --- |
| 1: new intent inspection | `PENDING` | `PENDING` | 0 | none | PASS |
| 2: initial execution | safe failure on invalid chronology | `BLOCKED` / `RUNTIME_EXCEPTION` | 1 | none | PASS |
| 2b: corrected inspection | `PENDING` | `PENDING` | 0 | none | PASS |
| 2b: one-shot success | completed `NO_ACTION` | `COMPLETED` / `NO_ACTION` | 0 | one final transition and one receipt | PASS |
| 2b: successor verification | edge and 3-edge lineage pass | PASS | 0 | none | PASS |
| Standalone later-edge CLI | authenticated later prior passes | PASS with explicit manifest | 0 | none | PASS |
| Repeated completed invocation | `ALREADY_APPLIED`, zero execution | `ALREADY_APPLIED` | 0 | none | PASS |
| 3: transition-only recovery | `RECEIPT_RECOVERED`, zero execution | `RECEIPT_RECOVERED` | 0 | receipt only | PASS |
| 4: receipt staging | fail closed and preserve staging | `BLOCKED` / `OPERATION_STAGING_EXISTS` | 8 | none | PASS |
| 5: deterministic failure | terminal failed receipt | `EXECUTION_FAILED` / `INSUFFICIENT_CASH` | 6 | failed receipt only | PASS |
| 5: repeated failure | recorded failure, zero retry | `EXECUTION_FAILED` / `INSUFFICIENT_CASH` | 6 | none | PASS |
| 5: failed inspection | valid failed receipt blocks | `BLOCKED` / `VALID_FAILED_RECEIPT` | 8 | none | PASS |
| 6A: completed receipt tamper | unverifiable and non-executing | `BLOCKED` / `INVALID_RECEIPT` | 4 | intentional copied-byte change only | PASS |
| 6B: report tamper | edge, lineage, receipt, coordinator fail | all failed closed | 6 edge; 4 coordinator | intentional copied-byte change only | PASS |
| 6C: failed receipt tamper | invalid failed receipt and no retry | `BLOCKED` / `INVALID_RECEIPT` | 4 | intentional copied-byte change only | PASS |

All stated version-one acceptance criteria passed: explicit inputs, verified
predecessor and snapshot, at most one admitted runtime attempt, verified
successor and lineage, immutable receipt evidence, restart-safe recovery,
terminal failed receipt behavior, and fail-closed tamper/staging handling.

## 20. Remaining limitations

- The coordinator assumes one local writer; it has no distributed lock or
  multi-host coordination.
- Invocation is manual and one-shot only; no scheduler, daemon, service, loop,
  polling, or background process exists.
- It has no broker reconciliation path and no external paper-account or
  real-money path.
- It has no mutable operation registry.
- Schema-1 receipt-only operation directories cannot provide complete global
  caller-idempotency-key reuse discovery. A foreign receipt establishes a
  conflict only when every exact dependency is available and the milestone-1
  offline verifier passes. Otherwise the coordinator fails closed with
  `FOREIGN_RECEIPT_DEPENDENCIES_UNAVAILABLE`, rather than inferring authority
  from parseable receipt fields, filenames, hashes, or paths.

## 21. Recommendation for the next architecture milestone

Keep the coordinator manual while the single-writer and dependency-retention
assumptions hold. Before unattended scheduling is considered, define explicit
scheduling and ownership policy, stale-invocation handling, bounded immutable
dependency retention, alerting and manual-review procedures, credentials and
provider boundaries, broker reconciliation requirements, and stronger global
caller-key authority. A future schema with an immutable dependency bundle, or
an explicitly governed authoritative registry, may address the foreign-receipt
discovery limitation; neither should be retrofitted into schema version 1.
