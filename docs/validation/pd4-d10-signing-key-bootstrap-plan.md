# PD4 D10 Signing-Key Bootstrap Validation Plan

Status: frozen source-validation and protected-checkpoint plan. Source
acceptance does not authorize key creation or any D10 production effect.

## A. A125-1 source-only implementation

Implement the fixed Windows CNG policy and operator boundary in
scripts/d10_signing_key_windows.py, plus focused pure/mock tests. Keep the
current governed v2 key ID/public key and P124 verifier constants unchanged.

The P125-1 operator contract is source-owned and zero-argument. It requires
elevated Administrator; opens only Microsoft Software Key Storage Provider;
proves the fixed name absent; creates only a machine-scoped ECDSA P-256 key
without overwrite; applies exact signing-only usage, zero export policy and
the protected Administrator/SYSTEM security descriptor; finalizes once;
reopens and verifies every property; and exports only a valid public P-256
point. It returns only a bounded canonical transcript and public material.
It never creates or publishes D10 trust files.

The concrete ExternalSigner opens the same fixed machine key and verifies all
key/provider/security properties before each sign. It accepts only the future
v3 SigningRequest with exactly one 32-byte SHA-256 digest, calls NCryptSignHash
on those digest bytes, requires a canonical 64-byte P1363 signature, and
closes all CNG handles exactly once. Every ambiguity blocks.

### Focused mock-test acceptance

Tests must cover:

- Exact provider, key name, ECDSA_P256, machine creation/open flags, no
  overwrite, and existing user- or machine-scoped name blocking.
- Administrator requirement, signing-only usage, export-policy zero, and
  exact protected owner/group/DACL with Trading absent.
- Readback mismatch; wrong provider/name/algorithm/group/curve/size/scope;
  exportable or archive-enabled policy; incorrect key usage; descriptor drift.
- Public-only ECC blob export, valid SEC1 normalization, malformed blob,
  coordinate, and off-curve rejection.
- Deterministic bounded PASS/BLOCKED enrollment transcripts with public-key
  SHA-256 and no private material.
- Fixed v3 signer identity/protocol, fixed machine-key open, per-sign property
  revalidation, exactly one 32-byte digest input, and exact returned protocol.
- CNG signing failure, short/long/noncanonical signatures, and cleanup failure.
- No private-key byte input/output/export API and no reachable D10 trust-root,
  lease, scheduler, market-provider, settlement, broker-paper, or live effect.

Use only fake/mock CNG APIs. Do not execute a native enrollment during source
verification. Run the focused A125 tests and directly overlapping
tests/runtime/test_d10_protected_deployment.py tests, Ruff check, Ruff format
check, and diff checks. Use a fresh external pytest --basetemp under
F:\AI\temp\pytest; do not run broad certification in A125-1.

## B. P125-1 separately authorized protected key creation

P125-1 is not part of source work or A125-1 acceptance. An authorized
Administrator operator later invokes the reviewed zero-argument function on
the intended Windows host. Retain and review only the public SEC1 point and
bounded transcript. Do not run P124-2/P124-3/P124-1, sign a production
attestation, create trust files, or mutate Task Scheduler or trading/provider
state during P125-1.

Stop on existing name, non-Administrator context, unexpected provider or key
property, security descriptor mismatch, malformed public blob, ambiguous native
result, or cleanup failure. Do not delete, replace, or retry over uncertain key
state.

## C. A125-2 public-key migration and S5-R1

After ChatGPT reviews P125-1 evidence, a separate source checkpoint may update
the D10 signing-key ID/public point, P124-1/P124-3 verifier constants, and
directly related tests to the v3 identity and reviewed public point. Do not
reuse the unavailable legacy private signer.

Because the pinned key is part of governed D10 executable source, run fresh
exact-tree S5-R1 certification after A125-2. S5-R1 is mandatory before
deployment. P124-2 and P124-3 remain blocked until the new public key is pinned
and S5-R1 passes; P124-1 remains behind its frozen protected sequence.

## D. Current status and stop conditions

The existing S5 commit/tree remains historically accepted, but cannot be
deployed until A125 completes. No production key is created by A125-1. The
currently pinned v2 public key remains unchanged in A125-1 and becomes
historical only after A125-2 migrates the verifiers.

This source-only checkpoint does not execute P125-1, P124-2, P124-3, or
P124-1; sign a production attestation; touch F:\AITradingBot; access the
production D10 root; mutate Task Scheduler; or perform market-provider,
settlement, broker-paper, or live effects.
