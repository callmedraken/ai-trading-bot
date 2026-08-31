# Architecture 94 P3 lineage replay clarification

## Status

This document is a normative Architecture-94 P3 clarification discovered during
the architecture-to-code reconnaissance after P2 acceptance. It supplements
`94-reliable-manual-paper-cycle-authority.md` for P3 only. If an older P3
sentence is ambiguous about historical daily-snapshot replay dependencies, this
document controls. It does not change accepted P1 or P2 semantics and does not
change Architectures 61, 63, 64, 66, or 67.

P3 remains a simulated-paper authority milestone. Production/live trading is
NO-GO and provider call #7 is not authorized.

## Why this clarification is required

Architecture 64 deliberately finalizes each paper-account transition directory
with exactly two artifacts:

```text
paper-account-transition-<application-id>/
  checkpointed-paper-cycle-report-<cycle-result-id>.json
  paper-account-checkpoint-<successor-checkpoint-id>.json
```

The daily-snapshot bytes used by the producing cycle are not copied into the
transition directory. Architecture 63 requires the exact verified daily snapshot
to replay an edge, and Architecture 66 requires explicit snapshot artifacts and
performs no filesystem discovery. Architecture 67 likewise treats the finalized
transition as the account-state commit point without embedding snapshot bytes.

Therefore P3 cannot prove a non-genesis operational account from the paper root
alone. P3 must assemble the exact historical snapshot replay dependencies without
changing the accepted transition layout or inventing a caller-controlled lineage
manifest.

## Fixed historical snapshot replay source

Production P3 is constructed only from a genuine
`ValidatedProductionAuthority`. P3 may attenuate that capability only to bind:

- the exact `machine_authority_id`;
- the exact approved Trading SID;
- the fixed C1 capture-output root already established by production authority.

P3 gains no C2/C3 mutation method, credential method, capture method, provider
adapter, retry authority, or selection-mutation authority from this dependency.
The production paper authority must not expose the underlying C1 capability.

For every recognized finalized paper transition, P3 performs this exact replay
sequence:

1. safely and boundedly read the transition's one canonical cycle-report file;
2. strictly parse the report with the existing canonical report parser;
3. obtain the immutable `request.snapshot_reference` containing exactly
   `snapshot_id`, `artifact_sha256`, and `artifact_byte_length`;
4. derive exactly one C3-v1 path under the fixed capture-output root:
   `daily-market-data-snapshot-<snapshot-id>.json`;
5. safely open only that exact regular file, rejecting reparse/symlink/device or
   unstable-identity substitution according to the reviewed Windows production
   file-safety pattern;
6. boundedly reread the bytes;
7. require the reread SHA-256 and byte length to equal the report's immutable
   snapshot reference;
8. require strict `verify_daily_snapshot(...)` PASS and exact snapshot-ID match;
9. use those exact bytes only as the `DAILY_SNAPSHOT` replay dependency supplied
   to the existing Architecture-63/66 verifier APIs.

There is no capture-output directory scan, newest/latest selection, timestamp
selection, fallback filename, alternate root, provider recovery, or network
lookup. Missing, unsafe, malformed, changed, or mismatched historical snapshot
bytes block P3 authority.

## What historical replay does not prove

Historical snapshot replay is not a retrospective C3 selection proof. P3 does
not query the C3 authority database to prove that every historical paper-cycle
snapshot was once a selected production snapshot. The committed paper transition
already immutably binds the exact snapshot reference used for deterministic
paper-account replay.

This distinction is deliberate:

- P3 proves the existing paper-account graph from its committed deterministic
  transition evidence and exact retained snapshot dependencies;
- P2 proves the one exact currently selected production C3 snapshot that may be
  admitted into a new Architecture-94 cycle;
- P4 later requires the current-cycle P1 assertion, P2 audit/permit, and P3
  account-tip evidence to belong to the same exact operation.

Reproducing historical snapshot bytes or knowing their UUID/path/digest cannot
mint a P2 permit, C3 capture authority, or provider authority.

## Inventory-to-lineage completeness

P3 derives authority from the fixed production paper root, never from a caller
lineage manifest.

The bounded root inventory must identify exactly one immutable anchor, exactly
the anchored genesis object, and every recognized finalized transition. The
candidate terminal checkpoint is derived from the graph as the unique reachable
checkpoint with no recognized successor; it is not caller-supplied.

P3 then constructs the explicit Architecture-66 artifact set from:

- the exact anchored genesis bytes;
- every recognized finalized transition's exact cycle-report bytes;
- every recognized finalized transition's exact successor-checkpoint bytes;
- the exact historical daily-snapshot bytes derived from each report as above.

`verify_paper_account_lineage(...)` must PASS with the graph-derived terminal.
P3 must additionally reconcile the complete inventory against the returned
lineage evidence so that every recognized finalized transition is consumed by
the one anchored chain. No extra recognized transition may be silently ignored.
A fork, cycle, disconnected/alternate genesis, competing successor, report or
application reuse conflict, unused recognized transition, missing dependency,
or unverifiable edge blocks authority.

The resulting terminal is current only because the complete fixed-root graph and
full-lineage proof establish one unique anchored chain. Filename order, UUID
order, directory enumeration order, mtime, timestamps, and a `latest`/`current`
file never define the tip.

## Finalized receipts are a non-authoritative audit namespace

Architecture 67's finalized transition directory is the authoritative
paper-account state commit point. A finalized receipt is a separate audit
commitment. P3 recognizes this fixed audit layout:

```text
<paper-root>/paper-operations/
  paper-operation-<operation-id>/
    paper-operation-receipt-<operation-id>.json
```

P3 retains all safe-object, reparse/device, stable-identity, bounded-enumeration,
and bounded-read protections for this namespace. Each finalized operation
directory must contain exactly the one expected receipt file. The existing
public `parse_paper_operation_receipt(...)` parser must accept its strict
canonical bytes, and both the parsed receipt ID and intent operation ID must
equal the canonical UUID represented by the directory and filename.

Successful parsing establishes structural/canonical validity only. P3 must not
call `verify_paper_operation_receipt(...)`, require cycle-configuration or
foreign lineage/snapshot/report/successor dependencies, infer caller-idempotency
conflicts, or treat parsed receipts as operation authority. Receipts never enter
`PaperAccountLineageEvidence` or change the graph-derived terminal. A valid
finalized `COMPLETED` or `FAILED` receipt with unavailable external verifier
dependencies does not prevent an otherwise valid account preflight. Adding or
removing such a receipt leaves account lineage, `VerifiedPriorCheckpoint`, and
terminal-tip evidence unchanged.

Any receipt staging entry, malformed/noncanonical receipt, directory/file/parsed
operation identity mismatch, unsafe object, case-fold collision, unexpected
contents, or enumeration overflow still blocks P3 and is never repaired.

P4 and the existing Architecture-67 inspection boundary later establish exact
operation-specific receipt authority. Architecture 67's existing
`FOREIGN_RECEIPT_DEPENDENCIES_UNAVAILABLE` classification remains unchanged when
those verifier dependencies are actually required. This clarification changes
neither Architecture 67 semantics nor the account commit point.

## Fixed paper root and immutable anchor

Production P3 remains bound to:

```text
F:\AITradingBot\Paper
```

The runtime does not accept another production paper root. Tests may use only an
explicit disposable seam.

The production root contains one canonical bounded anchor file with schema
`manual-paper-account-authority/v1`. The anchor binds:

- exact `paper_account_id` as canonical UUID text;
- exact `machine_authority_id` from genuine C1;
- exact approved Trading SID from genuine C1;
- exact genesis checkpoint ID;
- exact genesis artifact SHA-256;
- exact genesis artifact byte length.

The anchor does not bind the C1 authority epoch, provider identity, credential
version, path strings, wall clock, or mutable C3 state. A later unrelated C1
epoch change must not silently create a second paper account.

Anchor provisioning is a separate administrator-controlled operation. Ordinary
P3 runtime code can read/validate the anchor but cannot create, overwrite,
repair, rotate, or replace it. P3 implementation in this checkpoint does not
provision `F:\AITradingBot\Paper`.

The root/anchor/genesis security policy must validate exact approved principal,
owner/DACL/inheritance, real-object type, and reparse/device exclusions. Existing
C1 helpers that are deliberately fixed to `F:\AITradingBot\Authority` must not
be widened to accept the paper root. P3 may reuse public low-level Windows
security primitives but must implement a paper-specific path/security boundary.

## P4 production output-security prerequisite

Production P3 validates exact reviewed Windows security on finalized transition
and receipt output objects. The existing generic Architecture-67 output helpers
create transition staging directories with `os.mkdir`, report/checkpoint files
with ordinary `os.open`/`O_CREAT`, `paper-operations` with `os.mkdir`, receipt
staging directories with `os.mkdir`, and receipt files with ordinary
`os.open`/`O_CREAT`. These creation paths do not supply the P3 Windows security
descriptor. The current P3 root/output policy is protected and non-inheriting;
production P4 must not simply call those generic paths against
`F:\AITradingBot\Paper` and assume the resulting objects satisfy P3.

Before P4 production mutation is implemented, ChatGPT/Sol must freeze and
separately review a narrow production object-creation seam for the existing A67
output algorithm. That seam must satisfy all of these requirements:

- transition/receipt staging directories and files receive the exact reviewed
  P3 output security descriptor at creation time;
- rename preserves that descriptor into each finalized object;
- `paper-operations` itself is created with its reviewed descriptor;
- generic/offline A67 callers and deterministic schemas/identities remain
  unchanged;
- A67 no-clobber ordering, staging/reread verification, the transition account
  commit point, the separate receipt commitment, and recovery rules remain
  unchanged.

There must be no second A67 commit algorithm, caller-selected production root,
reliance on process-token default DACLs, reliance on ACL inheritance under the
non-inheriting P3 policy, or ACL normalization/repair after durable commit. No P4
production execution may be admitted until this creation seam has been
separately reviewed. If an at-creation security seam cannot preserve A67
semantics, stop for ChatGPT architecture review instead of changing those
semantics.

Future P4 native Windows validation must prove the production creation seam
establishes exact P3 ACLs on staging, finalized transitions, and
`paper-operations`/receipts, followed by a passing P3 preflight, including
crash/recovery windows. This P3 correction only freezes that prerequisite. It
does not implement the P4 seam, weaken P3 security, add ACL repair, or authorize
production mutation.

## Account-scoped Windows mutex

P3 uses a separate paper-account mutex identity. It must not reuse or forge the
Architecture-77 C2 lifecycle identity material.

The v1 canonical mutex name is:

```text
Global\AITradingBot-Paper-v1-<sha256>
```

where `<sha256>` is the lowercase SHA-256 of canonical sorted-key compact UTF-8
JSON containing exactly:

```json
{"label":"manual-paper-account/v1","paper_account_id":"<canonical-uuid>"}
```

The mutex follows the existing reviewed Win32 lifecycle-mutex security pattern:
`CreateMutexExW`, exact protected DACL validation, `WaitForSingleObject`,
`ReleaseMutex`, and `CloseHandle`. The exact Trading ACE uses
`MUTEX_MODIFY_STATE | READ_CONTROL | SYNCHRONIZE`; SYSTEM and Administrators
retain the reviewed full-control entries. An owner may be Administrators,
SYSTEM, or the exact approved Trading SID as permitted by the current token.

`WAIT_ABANDONED` means the mutex was acquired after an abandoned owner. It does
not validate account state. The complete root/anchor/inventory/historical
snapshot/full-lineage proof must run again after every acquisition, including an
abandoned acquisition.

Locked admission retains the complete pre-lock P3 evidence as `before`. If the
caller supplies `expected`, it must exactly equal `before` before acquisition.
The mutex is keyed from `before.paper_account_id`. After acquisition, complete
fresh preflight evidence must always exactly equal `before`, whether or not
`expected` was supplied. Any change in anchor, tip, lineage, historical
dependencies, transition count, or any other retained P3 evidence blocks before
a `LockedManualPaperAccount` is issued. `expected` is an optional additional
caller assertion; stale-state protection is unconditional.

P3 may expose read-only preflight without holding the final mutation lock. Any
future mutation admission must use a lock-scoped revalidation object whose
validity cannot be reused after lock release. P4 owns the first composition that
holds this mutex through the complete Architecture-67 execute/recover return.
P3 itself does not call the paper-cycle runtime or mutate the paper account.

## P3 output boundary

A successful P3 preflight returns immutable nonsecret evidence sufficient for
P4 to bind the account state, including at minimum:

- `paper_account_id`;
- `machine_authority_id` and approved Trading SID;
- anchored genesis checkpoint ID/SHA-256/byte length;
- complete Architecture-66 lineage evidence;
- exact verified terminal checkpoint ID/sequence/SHA-256/byte length;
- `VerifiedPriorCheckpoint` derived from the complete full-lineage PASS result;
- recognized finalized-transition count;
- exact historical snapshot dependency IDs and artifact evidence.

Paths may appear only as bounded transport/audit hints where necessary and must
not create account identity or tip authority. Raw native errors, secrets,
credential values, provider bodies, and unbounded filesystem diagnostics are not
part of public P3 evidence.

## Implementation stop conditions

P3 implementation must stop for ChatGPT/Sol architecture review if it appears to
require any of the following:

- changing Architecture-63, -64, -66, or -67 schemas or semantics;
- copying historical snapshot artifacts into the paper transition layout;
- widening C1 fixed-root path guards to include the paper root;
- querying C3 for `latest`/newest selection or manufacturing historical P2
  permits;
- adding provider, credential, network, broker, strategy, risk, or paper-cycle
  execution behavior;
- caller-selected production paper roots or caller-selected current tips;
- automatic cleanup/repair of staging or ambiguous Architecture-67 state;
- provisioning or mutating the production paper root during ordinary P3
  preflight.

No provider call #7 is authorized. Production/live trading remains NO-GO.
