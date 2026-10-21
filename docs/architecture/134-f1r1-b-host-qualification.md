# Architecture 134-F1R1-B: Host Binding and No-Effect Qualification

Status: source/design/test-only checkpoint. This document does not authorize
F1, a successor soak, installation, scheduler mutation, credential access,
provider calls, paper or broker effects, D1/D2 operation, or live trading.

## Boundary

F1R1-B composes independently verified Architecture-133 release, binding,
installed-image, and runtime-host evidence into the immutable
`InstalledRuntimeMaterial` contract established by F1R1-A. The composition
replays the verified bundle and binding, then requires every overlapping
release, manifest, binding, source-root, launcher, Python, image, dependency,
and source-inventory identity to agree. The result is path-independent for
runtime identity and can be admitted repeatedly without consulting Git,
GitHub, remote refs, worktrees, development HEAD, development cleanliness, or
mutable development files.

The binder is an evidence join, not a replacement for Architecture-133
admission. A caller cannot turn arbitrary strings into host proof: all inputs
must be the exact accepted evidence types and a successful Architecture-133
`RuntimeAdmissionResult` with `RuntimeAdmissionEvidence`.

## Durable lifecycle evidence

The B journal is a versioned canonical JSONL append-only store with a fixed
runtime identity header, bounded bytes and records, exact sequence numbers,
closed lifecycle events, replay-before-append validation, and read-back after
the injected storage seam reports a flush/fsync commit. A malformed, partial,
noncanonical, mismatched, over-budget, or terminally extended journal fails
closed. No repair, truncation, timestamp, secret, credential, provider body,
exception text, arbitrary environment, or caller-selected production path is
part of the schema.

The production adapter has a code-owned destination and is not executed by
this source-only checkpoint. Tests use only disposable temp files or an
in-memory storage seam.

## Effect-entry successor composition

`SuccessorExternalEffectAdapter` is an inert composition around the frozen
F1R1-A effect primitive. It records `INTENT`, persists `ENTRY_ADMITTED` before
calling its injected seam, records sanitized `DIAGNOSTIC` and consumes a
post-entry failure as `AMBIGUOUS`, or records `ACK` after success. It has no
provider, credential, broker, paper, scheduler, or trading implementation.

## Qualification host

`QualificationHost` accepts immutable material, performs fresh local
admission, and requires an injected disposable `QualificationHostLease`.
Only an exact `True` lease acquisition permits `SUPERVISOR_LOCK_ACQUIRED`,
loop entry, or safe waiting. A rejected lease records only `HOST_ENTERED`,
never releases another host's lease, and cannot claim host authority. An
acquired lease is released only after a durable `NORMAL_RETURN` or
`CAUGHT_INTERNAL_FAILURE` record. The seam has no operating-system lock,
installation, scheduler, provider, credential, paper, broker, or trading
capability.

The host exposes deterministic status/evidence and no heartbeat authority.
The focused harness keeps this cooperative host alive while tests perform
disposable development-directory, Git-status, file, and subprocess activity.
Those disturbances cannot alter the admitted runtime identity. The pure
`assess_host_qualification_readiness` boundary returns the closed
`READY_FOR_F1R1_HOST_QUALIFICATION` result only for an exact revalidated and
admitted `Architecture133HostBinding`; it grants no operational capability.

## Reboot and successor readiness

Production reboot remains exactly:

`RUNNING -> STOPPED after shutdown/restart -> optional read-only
reconciliation -> explicit human manual start with fresh admission -> RUNNING`.

The positive source result is `READY_FOR_F1R1_HOST_QUALIFICATION`. It means
only that the source contracts and no-effect harness are ready for a separately
reviewed operator qualification. It grants no soak, scheduler, provider,
credential, paper, broker, or production authority. The consumed original F1
remains consumed.

## Frozen predecessor and successor overlays

F1R1-B adds a successor overlay for the current runner, certification-profile,
lane, and test-inventory consumers. Each changed consumer has an exact
predecessor digest and exact successor path set. Missing, extra, wrong-blob, or
wrong-predecessor material fails closed; removing the B overlay resolves back
to the predecessor layer. Frozen D1R7, D1R8, F1, Architecture-133, and F1R1-A
source blobs are not edited.
