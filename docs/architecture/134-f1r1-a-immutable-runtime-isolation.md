# Architecture 134-F1R1-A: Immutable Runtime Isolation

Status: source/design/test-only checkpoint. This document does not authorize
installation, scheduler changes, credential access, provider calls, paper
mutations, broker operations, live effects, D1R7/D1R8 operation, D2, or any
change to preserved F1 evidence.

## Boundary and objective

F1R1-A prepares the successor runtime contract on branch
`feature/robinhood-production-paper-134f1r1-runtime-isolation-current`, based
on `develop` `ef66dc848fd3bc031220c7e8ccd4f462d762e829` (tree
`a63fb5bdcdf3d9a38645ffa07a91e2a55099f0d3`). The future unattended process
will execute an already-installed Architecture-133 release. After local
release admission, its identity is derived from the immutable manifest,
source inventory, launcher/Python identities, strategy and risk identities, and
durable-store identities. Repeated admission consumes only that material; it
does not consult Git, GitHub, remote refs, worktrees, development cleanliness,
or mutable development files.

This checkpoint does not install a release. Qualification that development
activity cannot interrupt a running admitted release belongs to F1R1-B.

## Runtime admission

`InstalledRuntimeMaterial` is immutable and path-independent for identity. Its
`runtime_id` is a versioned SHA-256 identity over the Architecture-133 release
manifest and local binding/store identities. `admit_installed_runtime` returns
an admitted proof or a closed failure reason for identity/state drift. The
proof includes the deterministic installed release projection, but no host
probe or source lookup is performed by this module.

## Effect entry and diagnostics

The effect journal distinguishes `INTENT`, `PRE_ENTRY_REJECTED`,
`ENTRY_ADMITTED`, `DIAGNOSTIC`, and `ACK`. The durable `ENTRY_ADMITTED` record
is appended before the external seam is called. A pre-entry rejection proves
the seam was not entered. A failure after entry is `AMBIGUOUS`, remains
consumed, and cannot be retried by this primitive. A successful return is
acknowledged only after the `ACK` record is persisted.

Diagnostic evidence is bounded, canonical, versioned, and limited to a closed
enumeration. It accepts no credentials, tokens, provider payloads, account or
order material, exception text, stack traces, or arbitrary environment/path
text.

## Lifecycle and reboot

The bounded lifecycle recorder can record host entry, lock acquisition, loop
entry, safe waiting, normal return, and caught internal failure. A replay that
ends without a terminal event is classified as abrupt process disappearance;
there is no heartbeat authority and no wall-clock identity input.

Production reboot semantics remain unchanged:

`RUNNING -> shutdown/restart -> STOPPED after boot/login -> optional read-only
reconciliation -> explicit human manual start with fresh admission -> RUNNING`.

The F1 soak's isolated logon-resume behavior is not promoted into production.

## Preserved F1 evidence and predecessor chain

The accepted F1 authority remains permanently consumed. Its terminal state was
parent `FINAL / INDETERMINATE`, child `FINAL / INDETERMINATE`, one D1R7 attempt,
one D1R8 attempt, no future child grant, zero broker placements, zero paper fill
mutations, and zero live effects. D1R8 durably reached quote `INTENT` after
history, strategy, and credential preparation, then became indeterminate; it
did not prove provider entry and did not reach quote acknowledgement,
confirmation, preparation completion, execution, account/order reads, review,
paper write, or broker placement. The supervisor survived into the actual
session window. Codex/environment interaction remains an unproven
environmental confounder; F1R1-A removes dependence on mutable development
state by construction rather than attributing the disappearance.

Accepted D1R7, D1R8, F1, and Architecture-133 source dictionaries and literal
digests remain frozen. Any current consumer that changes uses an exact
successor overlay: predecessor digest and path set are required, missing or
extra paths fail closed, wrong predecessor/successor blobs fail closed, and
removing the overlay restores predecessor resolution.

## Verification boundary

The focused test module uses disposable fakes only and covers local repeated
admission, development isolation, forbidden live-Git helpers, effect entry and
consumption, diagnostic redaction, bounded lifecycle replay, zero added host or
effect capabilities, frozen predecessor proof, fail-closed overlays, and
production reboot/manual-start semantics. No protected host, credential,
provider, broker, paper, scheduler, or production store is accessed.
