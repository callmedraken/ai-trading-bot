# C3 isolated child provider execution validation

## Boundary

This validates Architecture 83 / C3-B2 only. Tests run the child core directly
with injected child-local services. No real Credential Manager entry, Alpaca
network request, `CreateProcessW`, Job Object, final artifact publication, C2 SQL
mutation, scheduler, brokerage credential, or order is permitted by this gate.

## Required matrix

The deterministic child-core suite must prove:

- exact canonical A2 request snapshot/reparse before runtime use;
- one attempt object can execute once only;
- post-admission provider fence is entered before SID, Credential Manager,
  provider construction, or transport;
- derived daily-snapshot request/provider target equals the A2 authorized XNYS
  session before any credential read;
- wrong SID performs zero credential reads and zero transport calls;
- Credential Manager errors produce `CREDENTIAL_FAILED` and zero transport calls;
- exactly one provider fetch can delegate at most one underlying transport call;
- a hidden second transport call is blocked before delegation;
- sanitized HTTP failure retains only valid status/request-ID evidence;
- transport failure carries no fabricated HTTP evidence;
- malformed HTTP-200 provider entity maps to `PROVIDER_RESPONSE_INVALID`;
- deterministic incomplete/stale/mixed/unexpected data maps to
  `SNAPSHOT_REJECTED`;
- serialization or child-side verification failure maps to
  `SERIALIZATION_FAILED`;
- staging write/flush failure maps to `STAGING_FAILED`;
- unexpected core failures map to `INTERNAL_FAILED` without raw exception text;
- successful candidate bytes are canonical, pass `verify_daily_snapshot`, and
  have child claims equal to exact SHA-256/byte length/snapshot UUID;
- successful result remains child evidence only and cannot issue
  `VerifiedCapturedSnapshot`;
- B1 credential scope closes before serialization, staging, or result return;
- unsafe or overlong provider request IDs are omitted from the child result;
- serialized child results contain no credential values, provider body, raw
  exception text, paths, environment values, or native handles.

## Credential/failure ordering

Use the real B1 reader with an injected native Credential API where possible so
B2 tests cover the actual fixed-target and cleanup implementation rather than a
second fake credential policy.

Events are recorded deterministically. Expected success ordering is:

```text
fence
-> SID
-> key read/release
-> secret read/release
-> provider transport
-> credential scope close
-> serialize
-> child verify
-> staging write
-> staging flush
-> result
```

Native Credential Manager entries may be released before provider transport once
B1 has copied the bounded values into the scoped holder; the scoped Python secret
references remain live only through provider execution and are closed before
serialization/staging.

## Regression gate

At minimum run:

- B2 child-core tests;
- B1 credential tests;
- A1 capture-contract tests;
- A2 child-protocol tests;
- A3 composition tests;
- affected Alpaca transport/provider tests;
- daily-snapshot provider, acceptance, serialization, identity, and verification
  tests;
- Ruff check and Ruff format check on changed source/tests;
- `git diff --check`;
- exact production SQL size/hash assertion.

A full repository suite is deferred until the C3 integration/release gate unless
a B2 change unexpectedly touches broader shared behavior.

## Completion

B2 passes only when the same reviewed source tree is green and no test requires
real credentials or a live network call. C3-C is the next checkpoint and will
bind this core to the actual suspended Windows child, inherited request/result/
staging handles, Job Object containment, and resume fence.
