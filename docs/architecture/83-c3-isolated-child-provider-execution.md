# C3 isolated child provider execution

## 1. Scope

This document refines Architecture 82 for C3-B2 without changing C1 or C2 authority.
It freezes the executable child core that sits between the already-canonical A2
child request and the later C3-C native process/bootstrap boundary.

C3-B2 adds no `CreateProcessW`, Job Object, inherited-handle bootstrap, parent
artifact publication, C2 SQL changes, scheduler, brokerage adapter, or live-order
path. Those remain outside this checkpoint.

## 2. Controlling input

The B2 core accepts one exact `IsolatedCaptureChildRequest` whose canonical bytes
have already passed the A2 parser. The request carries the complete nonsecret C2
`capture_request/v2` object, its digest, reservation/execution binding, authorized
snapshot session, reservation-bound daily-snapshot request UUID, exact Alpaca
descriptor, fixed credential target names, C1-approved Trading SID, and approved
release-manifest digest.

Unparseable or transport-truncated request bytes are not converted into a
fabricated structured child result by B2. Such bytes may not contain trustworthy
reservation/execution identities. C3-C owns bounded pipe admission and the parent
classification when no trustworthy child result can be emitted.

The B2 attempt snapshots the canonical request bytes before execution and reparses
those retained bytes after entering the provider-attempt fence. Caller mutation of
an object after attempt construction cannot redirect the retained request.

## 3. One-shot attempt fence

One B2 attempt object can execute once. Reuse is rejected before any SID,
credential, provider, transport, serialization, or staging operation.

For the admitted canonical request, execution order begins:

```text
retain canonical request bytes
-> consume the one B2 attempt object
-> C3_PROVIDER_ATTEMPT_ENTERED
-> reparse/reconcile retained canonical request bytes
-> continue with child runtime effects
```

After `C3_PROVIDER_ATTEMPT_ENTERED`, every later failure consumes the C3 attempt
for C2 purposes. A credential failure therefore remains a confirmed C3 attempt
even if no HTTP request was sent. The fence is intentionally more conservative
than remote-server receipt evidence.

## 4. Runtime reconciliation

After the fence, B2 reconstructs the exact existing `DailySnapshotCaptureRequest`
from the retained child request and independently rebuilds the provider request
using the identified XNYS calendar. The derived target session must equal the
A2-authorized snapshot session exactly before Credential Manager is entered.

The executable release itself is pinned by the later C3-C process-launch boundary.
B2 retains and reparses the A3-supplied release-manifest digest as semantic child
request evidence; it does not introduce a second caller-selected release source.

## 5. Credential boundary

B2 consumes the C3-B1 `WindowsAlpacaCredentialManagerReader` contract.

The fixed sequence is:

```text
verify current token SID == approved Trading SID
-> CredReadW exact API-key target
-> validate/decode API key
-> CredReadW exact secret target
-> validate/decode secret
-> release/clear acquired native Credential Manager entries
-> enter short-lived ScopedAlpacaSecrets
```

There is no environment, `.env`, config-file, command-line, alternate-target, or
parent-secret fallback.

B2 uses the scoped values only to construct the exact existing
`AlpacaDailySnapshotProvider` inside the child. The credential scope is closed as
soon as the one provider fetch and deterministic acceptance step finish, whether
that step succeeds or raises. Snapshot serialization, child-side verification,
and staging occur only after the credential scope has been closed.

Python immutable strings still cannot be proven zeroized; B1/B2 only drop their
references as early as practical and never claim stronger zeroization.

## 6. Provider and transport budget

B2 constructs exactly one existing Alpaca daily-snapshot provider and calls its
`fetch` method at most once.

A child-local transport guard permits at most one call to the underlying Alpaca
transport. This is defense in depth against a future accidental retry inside a
provider implementation. A second transport call is blocked before another HTTP
operation is delegated.

There is no reconnect loop, fallback feed, alternate endpoint, pagination
continuation issuing another request, provider replacement, or automatic retry.

The existing provider owns strict Alpaca response parsing. The existing daily
snapshot acceptance layer owns deterministic completeness/freshness/session
acceptance. B2 does not duplicate either rule set.

## 7. Candidate artifact construction

After credentials are closed, an accepted snapshot follows:

```text
canonical daily-snapshot serialization
-> child-side offline verification of those exact bytes
-> exact snapshot/request/session/provider reconciliation
-> one write of the canonical candidate bytes to the child staging writer
-> staging flush
```

The B2 staging writer is an internal child service boundary, not caller-selected
artifact authority. C3-C will bind it to the one inherited staging handle created
by the parent. B2 never accepts a filesystem path or final filename.

Child-side verification is defense in depth only. It does not issue
`VerifiedCapturedSnapshot`; parent verification/publication remains the sole
production issuer later in C3.

## 8. Sanitized result mapping

B2 emits only the existing A2 `IsolatedCaptureChildResult` vocabulary.

| B2 observation | Child classification |
| --- | --- |
| retained canonical request fails post-fence reconciliation | `REQUEST_INVALID` |
| exact Trading SID mismatch | `SID_REJECTED` |
| Credential Manager/read/cleanup failure | `CREDENTIAL_FAILED` |
| request/connect/write path fails before a response is obtained | `TRANSPORT_REQUEST_FAILED` |
| response/status-line acquisition fails | `TRANSPORT_RESPONSE_START_FAILED` |
| response header/framing/metadata validation fails | `TRANSPORT_RESPONSE_METADATA_FAILED` |
| bounded response body read or entity-length reconciliation fails | `TRANSPORT_RESPONSE_BODY_FAILED` |
| sanitized transport failure has no assignable stage | `TRANSPORT_FAILED` |
| sanitized non-200 response | `HTTP_FAILED` |
| HTTP 200 entity violates fixed Alpaca schema | `PROVIDER_RESPONSE_INVALID` |
| deterministic daily-snapshot acceptance rejects | `SNAPSHOT_REJECTED` |
| canonical serialization or child verification fails | `SERIALIZATION_FAILED` |
| staging write or flush fails | `STAGING_FAILED` |
| unexpected reviewed-core failure | `INTERNAL_FAILED` |
| accepted, serialized, verified, staged, flushed | `SUCCEEDED` |

Provider request IDs are retained only when they satisfy the stricter A2 child
result bound. Unsafe/oversized IDs are omitted rather than copied into result
evidence.

The transport classifications persist only a closed sanitized stage. Raw
transport exception text, errno or TLS strings, host-derived details, headers,
provider body bytes, credentials, paths, tracebacks, environment data, and
native handle values are never placed in the structured result.

`SUCCEEDED` requires credential cleanup to be complete and contains only the
claimed snapshot UUID plus SHA-256/byte length of the exact staged canonical
bytes. It is still untrusted child evidence.

## 9. Composition rule

A bare `WindowsTransactionalAuthority(authority)` remains effectfully inert. C3
continues to expose no public production adapter injection surface.

C3-B2 exposes an explicit injected test factory so fake credentials, transport,
clock, and staging services can prove ordering and failure behavior without real
secrets or network calls. A production child factory that binds real inherited
handles is intentionally deferred to C3-C.

## 10. Completion gate

C3-B2 is complete when deterministic tests prove:

- one admitted attempt cannot execute twice;
- the fence is entered before SID/credential/provider effects;
- runtime request/session reconciliation occurs before Credential Manager;
- exact B1 credential ordering and cleanup are preserved;
- provider fetch count and underlying transport count are both at most one;
- all failure classes map to valid sanitized A2 results;
- credentials are closed before serialization/staging/result return;
- success bytes pass existing offline verification and match the child claims;
- child success cannot issue parent snapshot authority;
- A1/A2/A3/B1 and existing Alpaca/daily-snapshot regressions remain green.

The next checkpoint is C3-C native Windows isolation and resume orchestration.
