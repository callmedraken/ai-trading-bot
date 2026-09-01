# P3-R1 KSP machine-key security contract validation plan

## Status and scope

**DRAFT -- DOCS-ONLY VALIDATION CONTRACT -- REVIEW REQUIRED**

This plan validates Architecture 98. It designs future review gates but executes
none of them in this checkpoint. It does not authorize a production or
disposable key, signature, source implementation, deployment, retained-staging
access, recovery, provider call #7, P4, or live trading.

Architectures 95, 96, and 97 and their validation plans remain mandatory.
Architecture 98 supplies only the Windows CNG/KSP security contract deferred by
Architecture 97.

## A. Startup and docs-only gate

For this checkpoint require exact:

```text
WORKTREE=F:\AI\worktrees\ai-trading-bot-p3-r1
BRANCH=feature/p3-r1-recovery-implementation
HEAD=ec902c03e1debcb7bd595a0133ef055eeb87dfe1
TREE=30e3d86892f0ea545ded5281d02895a2da378a64
START_STATUS=CLEAN
```

Architecture 98 and both exact new paths must be absent before work. Any
mismatch is a stop condition; never checkout, switch, reset, rebase, clean,
prune, amend, or mutate a worktree to repair it.

Only these two untracked files may exist at completion:

```text
docs/architecture/98-p3-r1-ksp-machine-key-security-contract.md
docs/validation/reliable-manual-paper-cycle-p3-r1-ksp-machine-key-security-contract.md
```

No pytest or native test runs in the docs checkpoint. Any later Windows pytest
uses a fresh explicit `F:\AI\temp\pytest\<unique-name>` basetemp and normally
`-p no:cacheprovider`; historical pytest/cache evidence is not repaired.

## B. Fixed identity gate

Require exact immutable values:

```text
RECOVERY_KEY_ID=AITradingBot/Authority/P3R1Recovery/v1
PROVIDER=Microsoft Software Key Storage Provider
ALGORITHM=ECDSA_P256
ALGORITHM_GROUP=ECDSA
KEY_LENGTH_BITS=256
SCOPE=local-machine
CREATE_FLAG=NCRYPT_MACHINE_KEY_FLAG / 0x00000020
PERSISTED_CONTAINER=AITradingBot-P3R1-Recovery-v1
PUBLIC_ENCODING=65-byte uncompressed SEC1 P-256
SIGNATURE=ECDSA P-256 / SHA-256 / IEEE P1363 r||s / 64 bytes
```

Reject caller-selected provider, algorithm, scope, name, key ID, legacy key
spec, flag, alternate container, default provider, generated name, and fallback.

## C. Authoritative API/constant gate

Review the harness only against Microsoft Learn and the installed Windows SDK
headers. Require direct, typed bindings and checked return values for:

```text
NCryptOpenStorageProvider
NCryptCreatePersistedKey
NCryptOpenKey
NCryptSetProperty
NCryptGetProperty
NCryptFinalizeKey
NCryptExportKey
NCryptFreeObject
```

Require literal property identifiers and numeric constants to match Architecture
98 and the installed SDK. Reject filesystem ACLs, certificate-store defaults,
backing filenames, display-name authority, undocumented provider behavior,
blogs, or shell output as a security source.

## D. Provider support gate

Before any test or future production create:

1. open exactly `Microsoft Software Key Storage Provider` with flags zero;
2. read `NCRYPT_SECURITY_DESCR_SUPPORT_PROPERTY` from that handle;
3. require exactly four bytes and `DWORD == 1`; and
4. record only sanitized provider/status/value evidence.

Any other value, size, status, or `NTE_NOT_SUPPORTED` fails closed before
creation. No fallback provider, default permissions, filesystem ACL, or
best-effort continuation exists.

## E. Create-new and scope gate

For an approved TEST-only container:

- prove the reviewed machine-scope name absent;
- call `NCryptCreatePersistedKey` with `ECDSA_P256`, exact name, legacy spec
  zero, and `NCRYPT_MACHINE_KEY_FLAG` only;
- never pass `NCRYPT_OVERWRITE_KEY_FLAG`;
- prove the same no-overwrite call cannot replace an existing key; and
- prove a same-name current-user TEST key does not satisfy machine-scope open.

After independent reopen require:

```text
NCryptOpenKey flags        = 0x00000060
NCRYPT_KEY_TYPE_PROPERTY   = 0x00000020 exactly
NCRYPT_NAME_PROPERTY       = exact reviewed TEST name
provider name              = Microsoft Software Key Storage Provider
```

The production name is never probed, opened, enumerated, or used by the
disposable harness.

## F. Usage and export-policy timing gate

Before finalization, set with flags `0x80000040` and read with flags
`0x00000040`:

```text
NCRYPT_KEY_USAGE_PROPERTY  = 0x00000002
NCRYPT_EXPORT_POLICY_PROPERTY = 0x00000000
```

Require four-byte exact equality:

1. immediately after each pre-finalization set;
2. after finalization on the original handle; and
3. after close and independent machine-scope reopen.

Reject any additional usage bit, all-usages value, export/archival bit, size
drift, default inference, or post-finalization repair.

## G. Exact owner and principal gate

Require SID comparison, never display-name comparison:

```text
OWNER=BUILTIN\Administrators / S-1-5-32-544
ALLOW_1=LOCAL SYSTEM / S-1-5-18
ALLOW_2=BUILTIN\Administrators / S-1-5-32-544
NO_ACE=Trading / S-1-5-21-1397534616-3988210162-180023805-1009
NO_USER_ACE=P3-R1 Administrator / S-1-5-21-1397534616-3988210162-180023805-1005
```

The future production ceremony separately verifies the actual token is the
exact elevated P3-R1 Administrator. The DACL authority boundary is the
Administrators group plus explicit SYSTEM, not a per-user operator ACE.

Reject owner defaulting, alternate owner, name lookup substitution, an explicit
Trading allow/deny, or authority inferred from an account's display name.

## H. Exact DACL mask and structure gate

Build exactly two explicit allow ACEs in this input order:

```text
1. ACCESS_ALLOWED_ACE_TYPE, flags 0, S-1-5-18,     mask 0x001F019B
2. ACCESS_ALLOWED_ACE_TYPE, flags 0, S-1-5-32-544, mask 0x001F019B
```

`0x001F019B` is the concrete Microsoft `CryptoKeyRights.FullControl` mask. It
contains the documented cryptographic-key data/attribute rights and
`DELETE | READ_CONTROL | WRITE_DAC | WRITE_OWNER | SYNCHRONIZE`. It contains no
generic bit.

Do not use `GENERIC_ALL / 0x10000000`; the NCrypt documentation does not publish
the Microsoft Software KSP generic mapping. The disposable test must prove the
provider's exact acceptance, persistence/canonicalization, and enforcement of
`0x001F019B`. A different readback or behavior blocks production and requires
review; it never authorizes an inferred mapping or broader mask.

Reject a NULL/missing/empty DACL, any third ACE, inherited ACE, deny ACE,
nonzero ACE flag, different mask, duplicate, callback/object ACE, unknown ACE,
Everyone, Users, Authenticated Users, Creator Owner, application-package, or
ordinary-user grant.

## I. DACL protection gate

The absolute input descriptor must be built with explicit owner/DACL state and:

```text
SetSecurityDescriptorOwner(..., AdministratorsSid, FALSE)
SetSecurityDescriptorDacl(..., TRUE, ExactAcl, FALSE)
SetSecurityDescriptorControl(..., SE_DACL_PROTECTED, SE_DACL_PROTECTED)
```

After conversion to self-relative form and every readback require:

```text
SE_DACL_PRESENT          = set
SE_DACL_PROTECTED        = set
SE_DACL_DEFAULTED        = clear
SE_DACL_AUTO_INHERIT_REQ = clear
SE_DACL_AUTO_INHERITED   = clear
SE_OWNER_DEFAULTED       = clear
ACE inheritance flags    = 0
```

The disposable test must prove the Microsoft Software KSP preserves this state
after independent reopen. Filesystem inheritance is not evidence. Any default,
inherited, unprotected, missing, or ambiguous state fails.

## J. Security-property flags and timing gate

Set owner and DACL together before finalization:

```text
property = NCRYPT_SECURITY_DESCR_PROPERTY
set flags = NCRYPT_PERSIST_FLAG
          | NCRYPT_SILENT_FLAG
          | OWNER_SECURITY_INFORMATION
          | DACL_SECURITY_INFORMATION
          = 0x80000045
get flags = NCRYPT_SILENT_FLAG
          | OWNER_SECURITY_INFORMATION
          | DACL_SECURITY_INFORMATION
          = 0x00000045
```

`NCRYPT_PERSIST_ONLY_FLAG` is forbidden. Record the high-bit numeric overlap
between `NCRYPT_PERSIST_FLAG` and `PROTECTED_DACL_SECURITY_INFORMATION`; prove
the exact call on the disposable key instead of inferring its provider-specific
interpretation. Protection acceptance comes from parsed `SE_DACL_PROTECTED`
readback.

Require semantic owner/DACL readback:

1. before finalization;
2. after finalization on the original handle; and
3. after independent reopen.

If the pre-finalization set/readback is not accepted exactly, retain the test
key/evidence and stop. Do not try post-finalization mutation under the same
approval. A separately reviewed result proving the security descriptor can only
be applied after finalization requires:

```text
ARCHITECTURE_97_NARROW_CORRECTION_REQUIRED=True
```

and blocks production until Architecture 97 is narrowly corrected. The current
documentation review result remains `False` because Microsoft generally permits
property setting after create and before finalize and no authoritative source
establishes a conflict.

## K. Canonical semantic readback gate

Do not compare raw descriptor bytes as authority. Parse and require:

- valid security descriptor;
- exact owner SID and non-defaulted owner;
- DACL present and non-NULL;
- exact control/protection/default state;
- exactly two fully parsed ACEs;
- exact ACE type, flags, SID, and mask;
- no duplicate, trailing, malformed, or unexpected material.

Normalize each ACE as:

```text
(ace_type, ace_flags, canonical_sid, access_mask)
```

Sort those tuples and compare to the frozen two-entry set. Record the returned
physical order, but permit only reordering between the two same-class explicit
allow ACEs. `SE_SELF_RELATIVE` and absolute allocation layout are representation
details; every authority-bearing semantic is exact.

## L. Algorithm, finalization, name, and public-export gate

After finalization and again after independent reopen require:

```text
NCRYPT_ALGORITHM_PROPERTY       = ECDSA_P256
NCRYPT_ALGORITHM_GROUP_PROPERTY = ECDSA
NCRYPT_LENGTH_PROPERTY          = 256
NCRYPT_NAME_PROPERTY            = exact reviewed TEST name
NCRYPT_UNIQUE_NAME_PROPERTY     = non-empty and stable
```

Unique name is informational and must not become a path or identity authority.

Finalize exactly once with `NCRYPT_SILENT_FLAG`. Successful public export after
finalization and independent reopen supplies no-signature finalized-state
evidence. Export only `BCRYPT_ECCPUBLIC_BLOB` and require:

```text
blob bytes = 72
magic      = BCRYPT_ECDSA_PUBLIC_P256_MAGIC
cbKey      = 32
SEC1       = 0x04 || X[32] || Y[32]
SEC1 bytes = 65
```

Require identical SEC1 bytes across original and reopened handles.

## M. Private-export denial gate

Only the disposable test key may exercise private-export denial. With export
policy zero, attempt each reviewed private-bearing format supported/relevant to
the software KSP, including ECC private, generic private, opaque transport, and
PKCS#8 private export. Require denial and no returned private material.

Public export must still succeed. No certificate, PFX, PEM, archive, escrow,
backup, or private serialization is created. An unsupported format is recorded
separately from access/policy denial and cannot alone prove the policy; the
harness must obtain enough direct denials to establish the accepted behavior.

The production key is never subjected to any private export request.

## N. Authorized TEST signature gate

After every property/security/reopen gate passes, the exact elevated authorized
operator may perform one and only one TEST-key ECDSA P-256/SHA-256 signature.
Require a 64-byte P1363 signature and independent verification using only the
exported TEST SEC1 public point.

Any return after the signing call begins is an attempted test signature. Retain
all sanitized output, never sign again automatically, and never use a produced
test signature as production trust material.

## O. Trading and ordinary-user denial gate

Use genuine non-elevated tokens. For Trading and at least one reviewed ordinary
non-admin perspective, require the machine-scope TEST-key open needed for
private use/control to fail with the expected access-denied classification.

Prove Trading cannot:

- sign or otherwise use private key material;
- set usage/export/security properties;
- change owner or DACL;
- delete the key; or
- export any private-bearing blob.

When key open itself is denied, record downstream operations as unreachable; do
not weaken the DACL to exercise them. Also prove a same-name current-user key
cannot substitute for the machine key.

## P. Unexpected-state rejection gate

Pure/fake tests for the semantic verifier must reject individually:

- wrong owner;
- owner or DACL defaulted;
- missing, NULL, empty, or unprotected DACL;
- protection/control drift;
- extra, missing, duplicate, inherited, deny, callback, or unknown ACE;
- nonzero ACE flags;
- wrong SID or mask;
- `GENERIC_ALL` substitution;
- Trading/operator-user allow ACE;
- wrong scope/provider/container/algorithm/group/length;
- extra usage/export bit;
- unstable public or unique identity; and
- malformed/trailing security-descriptor or property bytes.

These verifier tests use constructed byte fixtures only and create no native
key.

## Q. Disposable key naming and isolation gate

The separately reviewed native harness must freeze one TEST-only machine-key
container that:

- is visibly marked TEST;
- is preflight-absent;
- cannot equal, normalize to, prefix-match, or alias
  `AITradingBot-P3R1-Recovery-v1`;
- is never caller-selected; and
- is never reused after any creation attempt.

The harness must contain a structural guard that rejects the production
container before any provider call. No enumeration or open of production
private material occurs.

## R. Failure, retention, and cleanup gate

After disposable creation, any failed or uncertain gate means:

```text
RETAIN_TEST_KEY=True
AUTOMATIC_DELETE=False
AUTOMATIC_REPAIR=False
AUTOMATIC_RETRY=False
REUSE_TEST_NAME=False
```

Retain sanitized evidence and stop. A later retry uses a newly reviewed distinct
container.

If every test passes, the test key still remains until a separate reviewed
cleanup phase. That phase may delete only the exact disposable machine key and
must independently prove the exact name absent afterward. Cleanup approval does
not apply to the production container.

## S. Production ceremony review gate

After disposable evidence is accepted, review a non-executable production
procedure that freezes:

- exact host/machine authority and elevated Administrator SID;
- provider/algorithm/container/scope and all numeric flags;
- security-descriptor support value;
- usage and export policy;
- owner/DACL/control/ACE SIDs/types/flags/masks;
- security-property set/get flags and timing;
- finalization ordering;
- public blob/SEC1 conversion;
- every post-finalization and independent-reopen property;
- canonical semantic readback;
- sanitized evidence schema and handle-close proof; and
- explicit `SIGNATURE_CREATED=False` and
  `PRIVATE_EXPORT_REQUESTED=False` assertions.

The production procedure is a later security-effect checkpoint. Architecture
98 does not provide an executable key-creation script.

## T. Architecture-97 and trust-separation regression gate

Require unchanged:

- historical Bootstrap/v1 bytes, public key, registry, and validation;
- exact recovery key ID and recovery-only registry;
- Architecture-96 canonical schema/domain/process-local permit;
- prohibition on signing old unsigned authorization evidence;
- retained Architecture-95 incident/recovery semantics;
- immutable old release/RECORD/authorization evidence; and
- isolated `python.exe -I -m pip --isolated install` deployment rules.

Current docs result:

```text
ARCHITECTURE_97_NARROW_CORRECTION_REQUIRED=False
```

The later disposable timing result can require a correction, but cannot silently
supersede Architecture 97.

## U. No-effect gate

For this docs checkpoint require:

```text
PRODUCTION_KEY_CREATED=False
PRODUCTION_KEY_OPENED=False
DISPOSABLE_TEST_KEY_CREATED=False
PRODUCTION_SIGNATURE_CREATED=False
TEST_SIGNATURE_CREATED=False
PRODUCTION_PRIVATE_KEY_USED=False
PRIVATE_EXPORT_REQUESTED=False
KSP_PROPERTY_MUTATED=False
KSP_ACL_MUTATED=False
KEY_DELETED=False
CERTIFICATE_CREATED=False
CREDENTIAL_MANAGER_ACCESSED=False
PRODUCTION_PAPER_PATH_ACCESSED=False
PRODUCTION_PAPER_PATH_MUTATED=False
PRODUCTION_AUTHORITY_MUTATED=False
SEALED_RUNTIME_MUTATED=False
PROVIDER_CALL_PERFORMED=False
PROVIDER_CALL_7_AUTHORIZED=False
P4_PRODUCTION_EXECUTION=False
PRODUCTION_LIVE=NO-GO
```

## Review readiness

This validation plan covers the exact provider, property, ACL, timing,
canonicalization, disposable-test, failure, cleanup, and production-input gates
required by Architecture 98. It is ready for ChatGPT/Sol review with the
architecture document.

Review acceptance authorizes only preparation/review of the separately approved
disposable native harness. It does not authorize running that harness or
creating the production recovery key.
