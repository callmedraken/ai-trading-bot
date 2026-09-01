# Architecture 97: P3-R1 recovery signing trust re-establishment

## Status

**DRAFT -- DOCS-ONLY ARCHITECTURE CHECKPOINT -- REVIEW REQUIRED**

This document defines a proposed correction to the Architecture-96 signing
trust decision. It does not authorize source implementation, key creation,
signing, deployment, retained-staging access, production recovery, provider
access, P4, or live trading.

After acceptance, this document is a mandatory addendum to Architectures 95
and 96. It supersedes only Architecture 96's reuse of the bootstrap signing
identity and bootstrap pinned-key registry. Architecture 95's retained-staging
recovery semantics and Architecture 96's strict authorization schema,
canonicalization, recovery-domain framing, release binding, and process-local
permit remain mandatory except where the signing key ID and registry are
explicitly corrected here.

## Purpose and incident classification

Architecture 96 required an external signer able to produce a detached P-256
signature for the recovery-specific domain. Signer discovery did not identify
or prove access to the private signer corresponding to the existing bootstrap
public key. The frozen incident facts are:

```text
EXISTING_BOOTSTRAP_KEY_ID=AITradingBot/Authority/Bootstrap/v1
EXISTING_BOOTSTRAP_PUBLIC_SEC1=04a73d90064e8b97e4a8373f48cac44718eb375ca52581233d614365294164efba40c6758f0f4cc455f6b2bf9b222696f9bc83c91ddf625fd01de46a6e7cd9c52e
EXISTING_BOOTSTRAP_PUBLIC_SEC1_BYTES=65
EXISTING_BOOTSTRAP_PUBLIC_SEC1_SHA256=72234cbe62bf0f82f8783b2a17854b263489cfc7f4bacbbcb3c8b04c74d6dbb4

SIGNING_PROCEDURE_IDENTIFIED=False
SIGNING_KEY_PUBLIC_IDENTITY_PROVED=False
SIGNATURE_CREATED=False
ORIGINAL_BOOTSTRAP_PRIVATE_SIGNER=OPERATIONALLY_UNAVAILABLE
```

No matching P-256 certificate/key was found in accessible certificate stores,
CNG/KSP inventories, repository history, or retained Trading Bot evidence.
This is an operational-availability conclusion, not proof that the private key
has been cryptographically destroyed.

The resulting correction is to establish a separate, recovery-only signing
trust anchor after this architecture is accepted. It is not bootstrap-key
rotation and grants no authority over the historical bootstrap.

## Historical Bootstrap/v1 preservation

`AITradingBot/Authority/Bootstrap/v1` is immutable historical trust material.
Architecture 97 must not replace, rotate, remove, alias, or reinterpret it.

The already-deployed historical `authority.bootstrap.json` and
`authority.bootstrap.sig` must continue to verify against the exact existing
uncompressed SEC1 public key through the bootstrap-only validation path and
`PRODUCTION_PINNED_BOOTSTRAP_KEYS`. Bootstrap canonical bytes, signature bytes,
key ID, public key, and verification behavior remain unchanged.

No new recovery key may:

- validate, resign, amend, migrate, or retroactively authorize the historical
  bootstrap;
- cause the bootstrap verifier to consult a recovery-key registry;
- be accepted under the `Bootstrap/v1` key ID; or
- make an old bootstrap signature valid for recovery-domain bytes.

Preserving this old trust anchor is required even though its corresponding
private signer is operationally unavailable.

## Recovery-only trust decision

The exact proposed recovery signing identity is:

```text
RECOVERY_SIGNING_KEY_ID=AITradingBot/Authority/P3R1Recovery/v1
```

The ID is code-owned, exact, versioned, and distinct from the bootstrap ID. It
is not selected by an authorization document, caller, CLI option, environment
variable, registry value, path, key-container enumeration, database row, or
release evidence.

Source implementation must introduce a distinct source-pinned production
registry, conceptually:

```text
PRODUCTION_PINNED_P3_R1_RECOVERY_KEYS
```

The recovery registry must have a recovery-specific model/type or an equally
strong nominal boundary that prevents accidental interchange with
`PRODUCTION_PINNED_BOOTSTRAP_KEYS`. Production recovery verification uses only
the source-pinned recovery registry. Bootstrap verification uses only the
existing bootstrap registry. Neither production entry point accepts a
caller-created registry. Explicitly named test-only verification seams may use
test-only keys and registries, but they cannot issue production-provenance
permits or reach production mutation.

The corrected source must prove this matrix:

```text
Bootstrap/v1 signature + exact bootstrap bytes                    -> PASS
P3R1Recovery/v1 signature + exact recovery-domain bytes           -> PASS
Bootstrap/v1 signature used as a recovery signature               -> FAIL
P3R1Recovery/v1 signature used as a bootstrap signature           -> FAIL
wrong recovery key ID                                             -> FAIL
caller-created recovery registry presented to production entry    -> NO AUTHORITY
```

The second PASS is not executable until the separately reviewed recovery key
exists, its public identity is frozen, and corrected source pins that identity.

## Cryptographic contract

The recovery key and signatures use exactly:

```text
key algorithm        = ECDSA P-256
hash                 = SHA-256
signature envelope   = detached
signature encoding   = IEEE P1363 r || s
signature length     = 64 bytes
public encoding      = uncompressed SEC1 P-256 point, 65 bytes
```

RSA, other curves, other hashes, DER signatures, variable-length signatures,
key lookup by filename/container alone, and weakened domain separation are not
accepted.

No defect was found in the Architecture-96 recovery-domain framing. It remains
exactly:

```text
uint16be(length("ai-trading-bot/p3-r1-recovery-authorization/v1"))
|| "ai-trading-bot/p3-r1-recovery-authorization/v1"
|| uint64be(length(canonical_authorization_bytes))
|| canonical_authorization_bytes
```

The signature is ECDSA P-256/SHA-256 over that exact preimage. Recovery
authorization bytes must never be passed to the bootstrap parser or verified
as unframed bootstrap bytes.

## Revised Architecture-96 authorization binding

The Architecture-96 authorization schema remains strict, exact, canonical,
secret-free, and closed to unknown or optional fields. Its existing incident,
operator, source, wheel, installed-RECORD, database, and fixed-path fields
remain unchanged.

The exact schema correction is:

```text
signing_key_id=AITradingBot/Authority/P3R1Recovery/v1
```

Once corrected source is implemented, `AITradingBot/Authority/Bootstrap/v1`
must be rejected as a recovery authorization signing key. This rejection must
not change the existing bootstrap validator's continued acceptance of the
historical C1 bootstrap.

The authorization's key ID is an asserted field that must equal the one
code-owned recovery ID; it does not choose a key. The production verifier first
requires that exact field value and then obtains the only permitted public key
from its source-pinned recovery registry.

## Private-key location and authority

The recovery private key remains outside all of the following:

- the Git repository and every worktree or Git object;
- source distributions and wheels;
- the sealed Python runtime and installed package;
- the production Paper tree and retained staging tree;
- the authority database and bootstrap files;
- recovery authorization/signature/release evidence; and
- application configuration, environment variables, and registry-based trust
  selection.

Source contains only the frozen public uncompressed SEC1 point. A key path,
provider name, persisted container name, registry value, filename, environment
variable, key handle, or caller-supplied digest is never a substitute for
cryptographically reproving the public identity.

Trading must have no private-key use, read, export, delete, ACL-control,
ownership, or administrative authority. The application runtime does not
create the production key and source/test tooling never opens, generates,
uses, signs with, or deletes it.

## Separately reviewed one-time key-creation ceremony

The ceremony may be designed and run only after Architecture 97 is reviewed
and accepted. It is a separate elevated Administrator procedure and a security
effect. Its fixed proposed identity is:

```text
PROVIDER=Microsoft Software Key Storage Provider
ALGORITHM=ECDSA_P256
SCOPE=local-machine
CREATE_FLAG=NCRYPT_MACHINE_KEY_FLAG
PERSISTED_CONTAINER=AITradingBot-P3R1-Recovery-v1
RECOVERY_KEY_ID=AITradingBot/Authority/P3R1Recovery/v1
```

The procedure must be frozen and reviewed before execution. It must perform the
following fail-closed sequence:

1. prove Windows host identity, exact elevated-token state, and the exact
   reviewed Administrator SID before opening the provider;
2. open exactly `Microsoft Software Key Storage Provider` and use the fixed
   algorithm, local-machine scope, container name, and flags above;
3. require the exact persisted name to be absent and use create-new semantics;
   never pass an overwrite flag or fall back to a generated name;
4. configure signing-only usage and an export policy that permits no private
   key export or private-key archiving, then read those settings back before
   finalization;
5. apply the separately accepted machine-key security descriptor and prove
   Trading has no private use/control authority;
6. finalize the key exactly once;
7. export only the public P-256 material, convert it to the exact 65-byte
   uncompressed SEC1 form, and freeze its byte length and SHA-256 as external
   ceremony evidence;
8. close the original key/provider handles;
9. independently reopen the key by the exact provider, container name, and
   local-machine scope;
10. re-export only the public material and require exact SEC1 byte equality
    with the frozen public identity;
11. read back and validate provider/name, algorithm/group/curve, key length,
    machine scope, finalized state, signing usage, export/archiving policy,
    unique persisted identity as applicable, owner, DACL/security descriptor,
    and absence of Trading private-use/control authority; and
12. close all handles, freeze sanitized evidence, and stop without creating a
    signature.

No private scalar, private blob (including opaque private export), PFX, PEM,
PKCS#8, archive, exportable backup, or escrow copy is permitted. Only the
public point may leave the provider.

### Machine-key security blocker

The exact machine-key ACL/security-descriptor API, inheritance behavior,
owner, canonical ACE set, access masks, and readback comparison are a mandatory
separate implementation decision. They are not safely inferable from path ACLs
or generic certificate-store practice. Until a reviewed Windows CNG/KSP
security contract proves that only the intended elevated administrative
principals can use/control the private key and that Trading cannot, the key
ceremony is **BLOCKED**. The later procedure must not substitute default or
best-effort permissions.

No signature is created as part of the key-creation ceremony.

## Ceremony failure and retry semantics

Key creation is a security effect. If an attempt creates or finalizes the fixed
persisted key and any later gate fails:

- retain all available sanitized evidence;
- do not automatically delete the key;
- do not overwrite it;
- do not silently generate another key or choose a new name;
- do not promote incomplete evidence; and
- stop for separately reviewed state resolution and recovery.

The original fixed name being present is a stop condition, not idempotent proof
of a valid completed ceremony. Only independently reviewed retained evidence
may establish what happened.

Signing is a separate explicit audited security effect. If signing has been
attempted, retain the produced signature and all evidence, do not sign again
automatically, do not choose among multiple signatures, and stop for review.
An uncertain signing return is still a signing attempt.

## Public-key freeze and source implementation gate

After an accepted ceremony, the exact recovery public SEC1 bytes, 65-byte
length, and SHA-256 become external frozen evidence. A later bounded source
implementation must pin exactly those bytes under
`AITradingBot/Authority/P3R1Recovery/v1` in the recovery-only registry.

That implementation must remove the current recovery module's dependency on
`PRODUCTION_PINNED_BOOTSTRAP_KEYS` and its recovery use of
`AITradingBot/Authority/Bootstrap/v1`. It must not change the bootstrap public
key or bootstrap verifier. Tests use test-only P-256 keys/registries and may not
generate, discover, open, or exercise the production recovery private key.

Source acceptance requires exact review, focused tests, and final source
certification before any release export. Source/test PASS creates no production
authority and no signature.

## Historical artifact treatment

The following old-design evidence roots remain retained and immutable:

```text
F:\AI\p3-r1-recovery-release-v1
STATUS=FAILED_RETAINED

F:\AI\p3-r1-recovery-release-v2
STATUS=FAILED_RETAINED

F:\AI\p3-r1-recovery-release-v3
STATUS=ACCEPTED_OLD_SIGNING_DESIGN

F:\AI\p3-r1-installed-record-derivation-v1
STATUS=ACCEPTED_OLD_SIGNING_DESIGN

F:\AI\p3-r1-recovery-authorization-freeze-v1
STATUS=ACCEPTED_UNSIGNED_OLD_SIGNING_DESIGN
```

They must not be deleted, repaired, renamed, overwritten, reused, or promoted.
The unsigned authorization in the old freeze must never be signed with the new
recovery key. Its old `Bootstrap/v1` binding is historical evidence, not input
to the corrected chain.

The corrected source/release chain must use new, preflight-absent, versioned
evidence roots. At minimum these are distinct roots for recovery-key ceremony
evidence, the exact Git export/release wheel, installed-RECORD derivation, the
new unsigned authorization freeze, and post-signature evidence. A separately
reviewed operator procedure must freeze their exact names, prove each is absent
before creation, and use create-new/no-overwrite publication. The next natural
versions are release `v4`, installed-RECORD derivation `v2`, and authorization
freeze `v2`; their use is not authorized by this document and must be checked
for absence rather than assumed.

## Non-circular recovery and release pipeline

The blocked Architecture-96 sequence is replaced by this mandatory order:

```text
accepted Architecture-97 docs
-> separately reviewed one-time recovery-key creation ceremony
-> freeze recovery PUBLIC SEC1 identity
-> independently reopen key and reprove PUBLIC identity/security
-> source implementation pins recovery PUBLIC key
-> exact source review
-> focused tests
-> final source certification
-> isolated exact Git export
-> exact offline release-wheel build
-> wheel/package/RECORD reconciliation
-> deterministic installed-RECORD dual-clone derivation
-> exact elevated Administrator SID
-> construct NEW canonical recovery authorization with recovery key ID
-> unsigned authorization freeze
-> reopen exact persisted recovery key
-> reprove PUBLIC identity before signing
-> explicit signing authorization
-> sign exact recovery-domain preimage once
-> independently verify signature through corrected source
-> freeze signature evidence
-> sealed-runtime deployment
-> installed RECORD/payload reconciliation
-> read-only retained-staging revalidation
-> separate explicit one-time recovery approval
-> Administrator recovery
-> non-admin Trading acceptance
```

No step may be skipped because an artifact from the old signing design exists.
The source does not predict its wheel or installed-RECORD identity. The new
canonical authorization is constructed only after the corrected source,
release wheel, and deterministic installed-RECORD identities are known. It is
frozen unsigned before the signing key is opened.

Immediately before signing, the exact persisted key must be reopened by the
fixed provider/name/scope and its public SEC1 identity and security metadata
must again match the accepted ceremony evidence. Signing requires a separate
explicit authorization naming the exact frozen preimage digest/length and is
performed once. Independent verification must use corrected source and the
source-pinned recovery public key before signature evidence is accepted.

## Deterministic installed-RECORD binding

The expected installed `RECORD` identity must be derived after the exact wheel
is frozen by installing it offline into two separately created, clean,
non-production clones under an exact frozen procedure. Both clones must produce
byte-identical installed `RECORD` material and matching reconciled package
payloads. Any difference blocks authorization construction. Neither clone is
the sealed runtime, and neither derivation authorizes deployment.

The new authorization binds the accepted source commit/tree, wheel digest and
length, and deterministically derived installed-RECORD digest and length. The
deployed runtime must later reprove the signed installed `RECORD` and every
hashed recovery-relevant payload.

## Sealed-runtime installer isolation

The discovered production runtime behavior is frozen:

```text
F:\AITradingBot\runtime\python.exe -m pip
-> resolved C:\Users\John\AppData\Roaming\Python\Python314\site-packages\pip
-> NOT ACCEPTABLE FOR PRIVILEGED DEPLOYMENT

F:\AITradingBot\runtime\python.exe -s -m pip
-> resolved sealed local pip 25.3

F:\AITradingBot\runtime\python.exe -I -m pip
-> resolved sealed local pip 25.3
```

Privileged deployment must use the isolated interpreter and pip semantics:

```text
F:\AITradingBot\runtime\python.exe -I -m pip --isolated install <exact-wheel> \
  --no-index \
  --no-deps \
  --no-cache-dir \
  --disable-pip-version-check \
  --no-input \
  --force-reinstall
```

The reviewed deployment procedure must clear and reject ambient Python/pip
influence, including inherited Python path/home and pip configuration/index/
target/user variables, prove the imported pip is the sealed runtime's exact pip
25.3 before installation, use only the frozen offline wheel, and reprove wheel
identity immediately before the command. `-I` and pip `--isolated` are both
required. This is a deployment trust boundary, not a performance optimization.

Deployment remains separately reviewed and is not performed or authorized by
this checkpoint.

## Preservation of Architecture-95 recovery semantics

All Architecture-95 semantics remain unchanged, including:

- exact frozen incident values and admission state;
- authorization and permit validation before Paper staging access;
- descendant handles retained for proof and successfully closed before rename;
- retained trusted parent and staging-root handles;
- absolute, no-replace `FileRenameInfo` root rename;
- pre/post native root and descendant identity continuity;
- mutation marker immediately before rename;
- conservative crash and ambiguous-outcome handling;
- no cleanup, reverse rename, repair, overwrite, retry, publisher rerun, or new
  account; and
- authority database byte identity and no-provider/no-credential/no-P4 effects.

The recovery-specific trust correction neither authorizes recovery nor weakens
the process-local permit. The native mutation boundary continues to require a
valid production-provenance permit issued only after all corrected signed
authorization and sealed-release checks succeed.

## Production and effect prohibitions

```text
KEY_CREATION=NOT_AUTHORIZED
SIGNING=NOT_AUTHORIZED
SEALED_RUNTIME_DEPLOYMENT=NOT_AUTHORIZED
PRODUCTION_RECOVERY_RENAME=NOT_AUTHORIZED
PUBLISHER_RERUN=FORBIDDEN
STAGING_DELETE_OR_REPAIR=FORBIDDEN
PROVIDER_CALL_7=NOT_AUTHORIZED
P4_PRODUCTION_EXECUTION=BLOCKED
PRODUCTION_LIVE=NO-GO
```

No source/test procedure may generate or use the production recovery private
key. No step may touch production Paper paths, the sealed runtime, production
Authority objects, Credential Manager, Alpaca/provider transport, broker
operations, or live trading unless a later separately reviewed checkpoint
explicitly authorizes that exact effect.

## Acceptance boundary and next step

Architecture 97 is ready for ChatGPT/Sol architecture review as a docs-only
proposal. Acceptance of the documents authorizes only the preparation and
review of the separate key-creation/security procedure; it does not authorize
running that procedure.

The mandatory next step after document acceptance is to resolve and review the
machine-key ACL/security blocker and produce an exact, no-overwrite,
no-signature Administrator ceremony procedure with sanitized evidence fields.
