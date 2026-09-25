# Architecture 125 - D10 Signing-Key Bootstrap and CNG External Signer

Status: design frozen; A125-1 source implementation is separate from protected
key creation. This document authorizes no production key creation, signing,
trust publication, deployment, scheduler mutation, or trading effect.

## 1. Purpose and key transition

The private signer corresponding to the currently pinned legacy P-256 public
key is operationally unavailable. It must not be reconstructed, derived,
substituted, exported, or invented. D10 therefore requires a new dedicated
signing key.

The future logical key ID is exactly:

AITradingBot/D10/DeploymentAttestation/v3

The fixed persisted key name is exactly:

AITradingBot-D10-DeploymentAttestation-v3

The current v2 signing-key ID and public key remain unchanged during A125-1.
They are historical only after the later public-key migration. No existing
governed D10 verifier or signing-key constant changes in A125-1.

## 2. Frozen provider, algorithm, scope, and policy

The key identity is fixed in source and cannot be selected by a caller:

- Provider: Microsoft Software Key Storage Provider.
- Persisted key, machine scope, using NCRYPT_MACHINE_KEY_FLAG.
- ECDSA P-256 only (ECDSA_P256, 256 bits).
- Signing use only (NCRYPT_ALLOW_SIGNING_FLAG exactly).
- Private-key export policy exactly zero: no export or archive policy.
- Create-only; no overwrite, replacement, delete, or caller-chosen identity.

The source-owned security descriptor is exactly:

O:BAG:SYD:P(A;;FA;;;SY)(A;;FA;;;BA)

It has BUILTIN Administrators as owner, SYSTEM as primary group, a protected
DACL, and only SYSTEM and BUILTIN Administrators full-control ACEs. The D10
Trading SID is absent. The complete descriptor and protected state are read
back on the finalized, reopened persisted machine key. Inability to set or
exactly verify it blocks the operation.

The key remains Administrator/SYSTEM controlled. Trading has no key access.
The signing API does not accept caller-selected provider, key name, algorithm,
scope, logical key ID, export policy, ACL, key bytes, or message bytes.

## 3. Protected P125-1 enrollment contract

scripts.d10_signing_key_windows.prepare_d10_signing_key() is the zero-argument
operator entry point prepared for a later, separately authorized P125-1 run.
Importing the module has no native side effects. The function:

1. Requires an elevated Administrator token.
2. Opens only the fixed Microsoft Software Key Storage Provider.
3. Requires the fixed key name absent in the operator user namespace and the
   machine namespace. Only a positive not-found result proves absence; unknown
   or inaccessible state blocks.
4. Creates the fixed algorithm/name with NCRYPT_MACHINE_KEY_FLAG and without
   NCRYPT_OVERWRITE_KEY_FLAG.
5. Sets the exact protected Administrator/SYSTEM descriptor before key
   finalization, followed by signing-only usage and export-policy zero. There
   is no descriptor readback on the unfinalized creation handle.
6. Calls NCryptFinalizeKey exactly once.
7. Closes the creation handle and reopens the fixed persisted key with
   NCRYPT_MACHINE_KEY_FLAG.
8. On the finalized, reopened key, authoritatively reads back the exact
   provider, name, ECDSA_P256/ECDSA algorithm, 256-bit P-256 size, machine-key
   type, signing-only usage, zero export policy, and full OWNER|GROUP|DACL
   descriptor: protected DACL, Administrators owner, SYSTEM primary group,
   only SYSTEM and Administrators full-control ACEs, and Trading absent.
9. Exports only the public ECCPUBLICBLOB, validates its P-256 point, and
   normalizes it to the verifier's 65-byte uncompressed SEC1 point
   04 || X || Y.
10. Returns a bounded deterministic canonical transcript and public material
    only. The transcript records provider/key identity, public point and
    SHA-256, exact security/property facts, and PASS or BLOCKED. It contains
    no timestamp, path, handle, credential, or private-key material.

The transcript is capped at 8 KiB. It contains no data from exception text.
Enrollment does not create or publish a D10 attestation, signature, manifest,
lease, or other trust file. It does not touch the D10 root, Task Scheduler, a
market-data provider, settlement, broker-paper, or live trading.

A failed or ambiguous step returns BLOCKED. Every CNG handle and native
allocation is released once; any cleanup ambiguity also blocks. A failure after
create-only key creation is not rolled back by deleting or replacing the
persisted name. The operator must retain the blocked transcript and resolve
state through a separately reviewed procedure. Successful descriptor setting
alone cannot produce PASS or permit public-key export; complete reopened-state
verification is required first.

The first protected P125-1 attempt returned BLOCKED with
`cng_security_descriptor_unavailable` during the pre-finalization readback.
Read-only post-attempt diagnosis opened the Microsoft Software Key Storage
Provider and observed `Security Descr Support = DWORD 1`; the fixed key name
returned `NTE_BAD_KEYSET (0x80090016)` in both user and machine scopes. No v3
key persisted, no public key was produced, and no P124 operation occurred.
This evidence is not a P125-1 PASS or authorization for another attempt.

## 4. Concrete P124-3 ExternalSigner implementation

WindowsCngExternalSigner implements the accepted
d10_protected_deployment.ExternalSigner protocol using only the fixed
persisted machine key. Its SigningIdentity exposes v3,
ECDSA-P256/SHA-256/IEEE-P1363, and private_key_exportable=False.

For every sign_digest call it requires Administrator, opens only the fixed
Microsoft Software KSP and fixed machine key, then rereads and verifies all
provider, name, algorithm/group, curve/size, machine-scope, signing-usage,
zero-export-policy, and protected security-descriptor facts before signing.
It accepts only the exact SigningRequest carrying a 32-byte SHA-256 digest
and the frozen v3 protocol. It passes that exact digest once to
NCryptSignHash, requires exactly 64 bytes of IEEE-P1363 r || s, and applies
the existing scalar-canonicality check before returning a detached signature.

No message input, key material, private-key import/export path, or generic key
name/provider/algorithm API is exposed. Provider/key handles close once per
operation. Native/property/signing/cleanup ambiguity raises a fail-closed
DeploymentBlocked result. The signer does not create D10 trust files or
perform a publication or trading effect.

## 5. Migration and deployment gates

The current S5 source certification remains historically accepted, but it
cannot be deployed until A125 completes. P125-1 is a separately authorized
protected key-creation checkpoint; source work does not create a production
key.

After P125-1, ChatGPT must review the protected transcript and public point.
Only then may the separate A125-2 source checkpoint replace the governed D10
signing-key ID and pinned public point, the P124-1/P124-3 operator verifier
public-key constants, and directly related tests. A125-2 must not invent or
substitute public material.

The public-key change alters the certified executable D10 tree. A new exact
tree S5-R1 certification is mandatory after A125-2. P124-2 and P124-3 remain
blocked until the new public key is pinned and S5-R1 has passed. The current v2
key ID/public key are historical after migration; they are not a fallback.

A125-1 does not run P125-1, P124-2, P124-3, or P124-1, and does not change the
currently pinned D10 public key.
