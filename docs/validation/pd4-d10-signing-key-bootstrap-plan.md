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
without overwrite; sets the exact protected Administrator/SYSTEM descriptor,
signing-only usage, and zero export policy before finalization; finalizes once;
closes the creation handle; reopens the fixed persisted machine key; then
reads back the OWNER|GROUP|DACL binary descriptor through native structural
verification and all frozen properties before exporting a valid public P-256
point. The unfinalized creation handle has no descriptor readback. A successful set alone cannot yield PASS. It
returns only a bounded canonical transcript and public material.
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
- Administrator requirement; exact descriptor, signing-only usage, and zero
  export policy set before the single finalize; creation handle closed before
  machine reopen; no descriptor read on the creation handle.
- Authoritative readback on the reopened key of provider, persisted name,
  ECDSA_P256/ECDSA, 256-bit P-256, machine scope, signing-only usage, zero
  export policy, and exact protected owner/group/DACL with Trading absent,
  all before public export.
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
result, or cleanup failure. A post-finalization verification failure remains
BLOCKED. Do not delete, replace, or retry over uncertain key state.

The first protected P125-1 attempt is BLOCKED evidence, not PASS: reason
`cng_security_descriptor_unavailable` at pre-finalization readback, no public
key, and no P124 operation. A read-only post-attempt diagnostic found the
provider openable with `Security Descr Support = DWORD 1`, while both user and
machine fixed-key opens returned `NTE_BAD_KEYSET (0x80090016)`. No key
persisted. A second protected attempt is outside this source correction.

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


## E. Attempt-#2 read-only recovery source checkpoint

P125-1 attempt #1 blocked on pre-finalization security readback and left no
persisted key. Attempt #2 finalized the fixed machine key but returned BLOCKED
and no public key because its exact SDDL serialization differed. Read-only
inspection found the fixed user key absent and the persisted machine key's
provider, algorithm, group, size, type 0x20, usage 0x02, and export policy zero
correct. Its owner is S-1-5-32-544; observed primary group is
S-1-5-21-1397534616-3988210162-180023805-1005. The protected DACL has
exactly two zero-flag allowed ACEs ordered SYSTEM then Administrators, both
mask 0xD01F01FF. Requested FA was 0x001F01FF. The persisted mask and group
are pinned exact host observations, not general normalization rules; primary
group is not an access grant. Trading has no ACE.

Source validation must use only pure/mock/native-adapter seams. Verify malformed
native descriptor/ACL/SID/ACE/control and cleanup failure block; exact owner,
group, protected DACL, ACL revision, ACE order/type/flags/trustees/masks;
provider and all cryptographic properties; and public export only after
verification. Verify the distinct recovery function has no create/set/finalize/
delete/sign route, enrollment still blocks an existing key, and signer uses the
same verifier before signing. Run focused signing-key and directly overlapping
protected-deployment tests, changed-file Ruff check/format check, and diff
checks using fresh F:\AI\temp\pytest\<unique> with -p no:cacheprovider.

No third enrollment attempt is planned. Do not run recovery qualification
against the real key during this source checkpoint. After exact source review,
a separately authorized read-only production qualification may return public
evidence. Only a PASS and ChatGPT review may feed A125-2. P124-2/P124-3/
P124-1 remain blocked.

### Exact attempt-#2 control and defaulted-field freeze

A further read-only native diagnostic of the existing persisted key observed
descriptor revision 1, control exactly 0x9004 (DACL present, protected, and
self-relative with no extra flags), owner/group/DACL defaulted false, ACL
revision 2, and two ordered allow ACEs: SYSTEM type 0/flags 0/size 20/
mask 0xD01F01FF, then Administrators type 0/flags 0/size 24/
mask 0xD01F01FF. Exact owner/group and SID facts remain those in section E.
The control word is an equality requirement, not a required-bit subset.
Tests must block every extra control bit, each missing required bit, wrong
descriptor revision, and either native owner/group defaulted output.
Native synthetic parsing must report all of these frozen fields. The shared
verifier must block drift before public export or signing, and PASS recovery
evidence must include them.

Observed acl_bytes_in_use=52, acl_bytes_free=0, and binary descriptor
SHA-256 ba4b328efe2fd3df0160302a957c641eed40dd40f4b3a31c955f300d51290d04
are diagnostics only; they and raw binary serialization are not authority
requirements. No production qualification has run and no production key
mutation occurred in this source checkpoint. The read-only qualification
remains the next separately authorized protected checkpoint.
