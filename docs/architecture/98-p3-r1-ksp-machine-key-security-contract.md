# Architecture 98: P3-R1 KSP machine-key security contract

## Status

**DRAFT -- DOCS-ONLY ARCHITECTURE CHECKPOINT -- REVIEW REQUIRED**

This document resolves the design portion of the Windows CNG/KSP machine-key
security blocker intentionally left open by accepted Architecture 97. It does
not authorize a production key, a disposable test key, a signature, source
implementation, deployment, retained-staging access, recovery, provider access,
P4, or live trading.

The future production ceremony remains blocked until the separately reviewed
disposable native test in this document proves the exact Microsoft Software Key
Storage Provider behavior on the intended Windows host. That empirical gate is
mandatory because Microsoft documents the general NCrypt security-descriptor
contract but does not publish the provider-specific generic-rights mapping,
security-descriptor canonicalization, or every property-timing detail needed to
accept a production private-key boundary without host evidence.

Architecture 97 remains fully accepted. This document is its mandatory security
addendum. It does not alter Architectures 95 or 96 except to supply the security
contract that Architecture 97 explicitly deferred.

## Fixed production identity

The future production identity is exact and not caller-selectable:

```text
RECOVERY_KEY_ID=AITradingBot/Authority/P3R1Recovery/v1
PROVIDER=Microsoft Software Key Storage Provider
ALGORITHM=ECDSA_P256
ALGORITHM_GROUP=ECDSA
KEY_LENGTH_BITS=256
SCOPE=local-machine
CREATE_FLAG=NCRYPT_MACHINE_KEY_FLAG
PERSISTED_CONTAINER=AITradingBot-P3R1-Recovery-v1
PUBLIC_ENCODING=65-byte uncompressed SEC1 P-256
SIGNATURE=ECDSA P-256 / SHA-256 / IEEE P1363 r||s / 64 bytes
```

This checkpoint does not create or open that key.

## Authority sources and installed definitions

The normative API sources are Microsoft Learn and the installed Windows SDK
10.0.26100.0 headers. The reviewed Microsoft references are:

- [NCryptOpenStorageProvider](https://learn.microsoft.com/en-us/windows/win32/api/ncrypt/nf-ncrypt-ncryptopenstorageprovider)
- [NCryptCreatePersistedKey](https://learn.microsoft.com/en-us/windows/win32/api/ncrypt/nf-ncrypt-ncryptcreatepersistedkey)
- [NCryptOpenKey](https://learn.microsoft.com/en-us/windows/win32/api/ncrypt/nf-ncrypt-ncryptopenkey)
- [NCryptSetProperty](https://learn.microsoft.com/en-us/windows/win32/api/ncrypt/nf-ncrypt-ncryptsetproperty)
- [NCryptGetProperty](https://learn.microsoft.com/en-us/windows/win32/api/ncrypt/nf-ncrypt-ncryptgetproperty)
- [NCryptFinalizeKey](https://learn.microsoft.com/en-us/windows/win32/api/ncrypt/nf-ncrypt-ncryptfinalizekey)
- [NCryptExportKey](https://learn.microsoft.com/en-us/windows/win32/api/ncrypt/nf-ncrypt-ncryptexportkey)
- [NCryptFreeObject](https://learn.microsoft.com/en-us/windows/win32/api/ncrypt/nf-ncrypt-ncryptfreeobject)
- [key storage property identifiers](https://learn.microsoft.com/en-us/windows/win32/seccng/key-storage-property-identifiers)
- [CNG algorithm identifiers](https://learn.microsoft.com/en-us/windows/win32/seccng/cng-algorithm-identifiers)
- [BCRYPT_ECCKEY_BLOB](https://learn.microsoft.com/en-us/windows/win32/api/bcrypt/ns-bcrypt-bcrypt_ecckey_blob)
- [security-descriptor control](https://learn.microsoft.com/en-us/windows/win32/secauthz/security-descriptor-control)
- [SetSecurityDescriptorControl](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-setsecuritydescriptorcontrol)
- [SetSecurityDescriptorDacl](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-setsecuritydescriptordacl)
- [standard access rights](https://learn.microsoft.com/en-us/windows/win32/secauthz/standard-access-rights)
- [generic access rights](https://learn.microsoft.com/en-us/windows/win32/secauthz/generic-access-rights)
- [CryptoKeyRights](https://learn.microsoft.com/en-us/dotnet/api/system.security.accesscontrol.cryptokeyrights?view=netframework-4.8.1)
- [order of ACEs in a DACL](https://learn.microsoft.com/en-us/windows/win32/secauthz/order-of-aces-in-a-dacl)
- [LocalSystem account](https://learn.microsoft.com/en-us/windows/win32/services/localsystem-account)

The installed headers freeze the relevant literal definitions:

```text
NCRYPT_MACHINE_KEY_FLAG                 = 0x00000020
NCRYPT_SILENT_FLAG                      = 0x00000040
NCRYPT_OVERWRITE_KEY_FLAG               = 0x00000080
NCRYPT_PERSIST_ONLY_FLAG                = 0x40000000
NCRYPT_PERSIST_FLAG                     = 0x80000000

NCRYPT_ALLOW_DECRYPT_FLAG               = 0x00000001
NCRYPT_ALLOW_SIGNING_FLAG               = 0x00000002
NCRYPT_ALLOW_KEY_AGREEMENT_FLAG         = 0x00000004
NCRYPT_ALLOW_ALL_USAGES                 = 0x00ffffff

NCRYPT_ALLOW_EXPORT_FLAG                = 0x00000001
NCRYPT_ALLOW_PLAINTEXT_EXPORT_FLAG      = 0x00000002
NCRYPT_ALLOW_ARCHIVING_FLAG             = 0x00000004
NCRYPT_ALLOW_PLAINTEXT_ARCHIVING_FLAG   = 0x00000008

OWNER_SECURITY_INFORMATION              = 0x00000001
DACL_SECURITY_INFORMATION               = 0x00000004

ACCESS_ALLOWED_ACE_TYPE                 = 0x00
OBJECT_INHERIT_ACE                      = 0x01
CONTAINER_INHERIT_ACE                   = 0x02
NO_PROPAGATE_INHERIT_ACE                = 0x04
INHERIT_ONLY_ACE                        = 0x08
INHERITED_ACE                           = 0x10

SE_DACL_PRESENT                         = 0x0004
SE_DACL_DEFAULTED                       = 0x0008
SE_DACL_AUTO_INHERIT_REQ                = 0x0100
SE_DACL_AUTO_INHERITED                  = 0x0400
SE_DACL_PROTECTED                       = 0x1000
SE_SELF_RELATIVE                        = 0x8000

DELETE                                  = 0x00010000
READ_CONTROL                            = 0x00020000
WRITE_DAC                               = 0x00040000
WRITE_OWNER                             = 0x00080000
SYNCHRONIZE                             = 0x00100000
GENERIC_ALL                             = 0x10000000
```

The exact property names are:

```text
NCRYPT_NAME_PROPERTY                    = L"Name"
NCRYPT_UNIQUE_NAME_PROPERTY             = L"Unique Name"
NCRYPT_ALGORITHM_PROPERTY               = L"Algorithm Name"
NCRYPT_LENGTH_PROPERTY                  = L"Length"
NCRYPT_EXPORT_POLICY_PROPERTY           = L"Export Policy"
NCRYPT_KEY_USAGE_PROPERTY               = L"Key Usage"
NCRYPT_KEY_TYPE_PROPERTY                = L"Key Type"
NCRYPT_SECURITY_DESCR_SUPPORT_PROPERTY  = L"Security Descr Support"
NCRYPT_SECURITY_DESCR_PROPERTY          = L"Security Descr"
NCRYPT_ALGORITHM_GROUP_PROPERTY         = L"Algorithm Group"
```

No blog, certificate-store default, filesystem path, backing key filename, or
filesystem ACL is a security authority for this contract.

## Frozen NCrypt call contract

All native return values are checked as `SECURITY_STATUS`. Any unexpected
status, size, type, value, canonical form, or UI requirement fails closed.
Handles are never reused after release.

### NCryptOpenStorageProvider

Open exactly `MS_KEY_STORAGE_PROVIDER`, whose literal value is
`Microsoft Software Key Storage Provider`, with `dwFlags=0`. A null provider
name is forbidden because it selects a default provider. The returned provider
handle must later report the exact provider name. Release it with
`NCryptFreeObject` after all associated key handles have been released.

### NCryptCreatePersistedKey

The future production call is exact:

```text
pszAlgId       = BCRYPT_ECDSA_P256_ALGORITHM / L"ECDSA_P256"
pszKeyName     = L"AITradingBot-P3R1-Recovery-v1"
dwLegacyKeySpec= 0
dwFlags        = NCRYPT_MACHINE_KEY_FLAG / 0x00000020
```

`NCRYPT_OVERWRITE_KEY_FLAG` is forbidden. Before creation, an exact machine-
scope `NCryptOpenKey` absence probe must return the reviewed not-found status.
The no-overwrite create call must return `NTE_EXISTS` if the name is present.
No generated, alternate, retried, user-scope, or fallback name exists.

### NCryptOpenKey

Every independent production reopen is exact:

```text
provider       = the exact opened Microsoft Software KSP
pszKeyName     = L"AITradingBot-P3R1-Recovery-v1"
dwLegacyKeySpec= 0
dwFlags        = NCRYPT_MACHINE_KEY_FLAG | NCRYPT_SILENT_FLAG
               = 0x00000060
```

Omitting `NCRYPT_MACHINE_KEY_FLAG`, accepting a current-user key, omitting
silent operation, or opening by unique name alone is forbidden. Same container
text in the wrong scope is not the production identity.

### NCryptSetProperty and NCryptGetProperty

All `DWORD` properties use exactly four input/output bytes and exact equality.
Strings must be well-formed, null-terminated UTF-16 values with exact text.
Size-probe and data calls must agree; trailing or malformed material fails.

Usage and export-policy writes before finalization use:

```text
NCryptSetProperty flags = NCRYPT_PERSIST_FLAG | NCRYPT_SILENT_FLAG
                         = 0x80000040
```

Their readbacks use `NCRYPT_SILENT_FLAG / 0x00000040`, not
`NCRYPT_PERSIST_ONLY_FLAG`.

The security-descriptor set is one owner-plus-DACL operation:

```text
NCryptSetProperty property = NCRYPT_SECURITY_DESCR_PROPERTY
dwFlags = NCRYPT_PERSIST_FLAG
        | NCRYPT_SILENT_FLAG
        | OWNER_SECURITY_INFORMATION
        | DACL_SECURITY_INFORMATION
        = 0x80000045
```

The corresponding get is:

```text
NCryptGetProperty property = NCRYPT_SECURITY_DESCR_PROPERTY
dwFlags = NCRYPT_SILENT_FLAG
        | OWNER_SECURITY_INFORMATION
        | DACL_SECURITY_INFORMATION
        = 0x00000045
```

`NCRYPT_PERSIST_ONLY_FLAG` is forbidden with
`NCRYPT_SECURITY_DESCR_PROPERTY`, as Microsoft explicitly documents. The
security descriptor is a built-in persisted-key property; this contract uses
`NCRYPT_PERSIST_FLAG` to request persistence and requires close/reopen proof.
The high-bit numeric overlap between `NCRYPT_PERSIST_FLAG` and
`PROTECTED_DACL_SECURITY_INFORMATION` is recorded rather than interpreted as a
second authority. DACL protection is encoded in and verified from the security
descriptor's `SE_DACL_PROTECTED` control bit. The disposable native test must
prove that the exact `0x80000045` call is accepted and that the expected owner,
DACL, and control state persist. Any rejection or different interpretation
blocks production and requires architecture review.

### NCryptFinalizeKey

Finalize the newly created handle exactly once with
`NCRYPT_SILENT_FLAG / 0x00000040`. Do not use legacy-store, no-validation, or
other flags. No operation that uses or exports the key may occur before
successful finalization.

### NCryptExportKey

Production export is public-only:

```text
hExportKey      = NULL
pszBlobType     = BCRYPT_ECCPUBLIC_BLOB
pParameterList  = NULL
dwFlags         = NCRYPT_SILENT_FLAG
```

Use the documented size-query followed by one exact allocation and export.
Require `BCRYPT_ECDSA_PUBLIC_P256_MAGIC`, `cbKey=32`, and exactly:

```text
BCRYPT_ECCKEY_BLOB header (8 bytes)
X (32-byte unsigned big-endian)
Y (32-byte unsigned big-endian)
total = 72 bytes
```

The frozen SEC1 public value is `0x04 || X || Y`, exactly 65 bytes. No private,
opaque-transport, PKCS#8, PFX, PEM, archival, or wrapped-private request may be
made against the production key.

### NCryptFreeObject

Every provider and key handle is released exactly once. Closing the original
key handle is mandatory before the independent reopen. `NCryptDeleteKey` is not
part of any production procedure.

## Provider security-descriptor support gate

Before the production name is probed or created, call `NCryptGetProperty` on
the exact provider handle for `NCRYPT_SECURITY_DESCR_SUPPORT_PROPERTY` with
`NCRYPT_SILENT_FLAG`. Require a four-byte `DWORD` equal to exactly `1`.

Any other value, malformed length, `NTE_NOT_SUPPORTED`, or other failure blocks
the ceremony before creation. There is no provider fallback, default-permission
fallback, certificate-store fallback, filesystem-ACL substitution, or
best-effort mode.

## Key usage contract

The exact value is:

```text
NCRYPT_KEY_USAGE_PROPERTY = NCRYPT_ALLOW_SIGNING_FLAG = 0x00000002
```

No decrypt, key agreement, envelope/import, attestation, future bit, unknown
bit, or `NCRYPT_ALLOW_ALL_USAGES` is accepted. Set and read it before
finalization, then read exact equality after finalization and after independent
close/reopen. If the provider adds, drops, aliases, or refuses this exact value,
production creation remains blocked.

## Private-export policy

The exact value is:

```text
NCRYPT_EXPORT_POLICY_PROPERTY = 0x00000000
```

Therefore none of the private-export, plaintext-private-export, private-
archival, or plaintext-private-archival bits is enabled. Set and read exact
zero before finalization, then read exact zero after finalization and independent
reopen. Public `BCRYPT_ECCPUBLIC_BLOB` export remains required.

The production ceremony never probes a private blob. Denial of private export
is exercised only against a separately authorized disposable key.

## Machine scope, algorithm, size, and identity readback

After independent reopen, require all of the following:

```text
provider name              = Microsoft Software Key Storage Provider
NCRYPT_NAME_PROPERTY       = AITradingBot-P3R1-Recovery-v1
NCRYPT_KEY_TYPE_PROPERTY   = 0x00000020 exactly
NCRYPT_ALGORITHM_PROPERTY  = ECDSA_P256
NCRYPT_ALGORITHM_GROUP_PROPERTY = ECDSA
NCRYPT_LENGTH_PROPERTY     = 256
NCRYPT_KEY_USAGE_PROPERTY  = 0x00000002
NCRYPT_EXPORT_POLICY_PROPERTY = 0x00000000
```

Authoritative identity is the conjunction of the exact provider open, exact
machine-scope open, exact container name, exact `NCRYPT_KEY_TYPE_PROPERTY`,
algorithm/group/length properties, exact public SEC1 bytes, and exact security
descriptor. Container text alone is never authority.

`NCRYPT_UNIQUE_NAME_PROPERTY` is provider-generated. It must be non-empty and
stable between post-finalization observation and independent reopen, but it is
informational evidence rather than a caller-selected identity or a filesystem
path authority. A backing filename is never opened or ACL-inspected.

Microsoft exposes no separate documented `finalized` property. Successful
post-finalization public export, for which `NTE_BAD_KEY_STATE` is the documented
unfinalized failure, plus independent reopen and exact readback are the
production ceremony's no-signature finalization evidence. The disposable test
also proves one authorized test-key signature.

## Principal and ownership decision

The security principals are SID-based:

```text
BUILTIN\Administrators = S-1-5-32-544
LOCAL SYSTEM           = S-1-5-18
Trading                = S-1-5-21-1397534616-3988210162-180023805-1009
P3-R1 Administrator    = S-1-5-21-1397534616-3988210162-180023805-1005
```

The exact owner is `BUILTIN\Administrators / S-1-5-32-544`. A group owner is
the durable administrative authority boundary and avoids making one account SID
the only recovery route. The ceremony still separately requires the actual
elevated token SID to equal the frozen P3-R1 Administrator SID; that operator
identity gate does not change the key's group-owned recovery boundary.

The exact Administrator account has no separate ACE. Its authority derives
only from enabled membership in `BUILTIN\Administrators` in the reviewed
elevated token. A filtered/non-elevated token must not obtain access from a
disabled or deny-only administrators SID.

`LOCAL SYSTEM` receives an explicit ACE. Microsoft documents LocalSystem as a
powerful operating-system/service identity and its token composition can depend
on access context; the key contract does not rely on implicit Administrators
membership. Explicit SYSTEM authority also avoids accidental loss of operating-
system/KSP maintenance access while keeping the allow-list closed.

Trading and every ordinary non-admin account have no ACE. There is no explicit
deny ACE: the exact protected allow-list DACL denies unmatched principals and
avoids deny-order and group-interaction hazards.

## Exact DACL and ACE contract

The DACL contains exactly two explicit access-allowed ACEs:

| Order for construction | ACE type | ACE flags | Principal SID | Access mask |
| --- | --- | --- | --- | --- |
| 1 | `ACCESS_ALLOWED_ACE_TYPE / 0x00` | `0x00` | `S-1-5-18` | `0x001F019B` |
| 2 | `ACCESS_ALLOWED_ACE_TYPE / 0x00` | `0x00` | `S-1-5-32-544` | `0x001F019B` |

`0x001F019B` is the concrete Microsoft `CryptoKeyRights.FullControl` value:

```text
ReadData                 0x00000001
WriteData                0x00000002
ReadExtendedAttributes   0x00000008
WriteExtendedAttributes  0x00000010
ReadAttributes           0x00000080
WriteAttributes          0x00000100
DELETE                   0x00010000
READ_CONTROL             0x00020000
WRITE_DAC                0x00040000
WRITE_OWNER              0x00080000
SYNCHRONIZE               0x00100000
combined                  0x001F019B
```

No generic bit is stored. Although `GENERIC_ALL` is numerically `0x10000000`,
Windows requires each securable object type to supply a generic mapping, and
Microsoft's NCrypt documentation does not publish the Microsoft Software KSP's
mapping. This contract therefore does not invent or depend on that mapping.

The disposable test must still prove that the Microsoft Software KSP accepts,
preserves or documentedly canonicalizes, and enforces `0x001F019B` as intended.
If it returns a different mask or behavior, the production ceremony stays
blocked; the result is evidence for a reviewed architecture correction, not
permission to broaden or guess.

The DACL must have exactly two ACEs and no Trading, operator-user, Users,
Authenticated Users, Everyone, Creator Owner, service, application-package,
inherited, deny, audit, callback, object-specific, or unknown ACE. A NULL DACL,
missing DACL, empty DACL, defaulted DACL, or extra ACE fails.

## DACL protection and inheritance

Build an absolute security descriptor with:

1. `SetSecurityDescriptorOwner(..., AdministratorsSid, FALSE)`;
2. an explicitly allocated ACL containing only the two ACEs above;
3. `SetSecurityDescriptorDacl(..., TRUE, ExactAcl, FALSE)`; and
4. `SetSecurityDescriptorControl(..., SE_DACL_PROTECTED,
   SE_DACL_PROTECTED)`.

Convert to a valid self-relative descriptor for the NCrypt property buffer.
The intended semantic control state is:

```text
SE_DACL_PRESENT          = set
SE_DACL_PROTECTED        = set
SE_DACL_DEFAULTED        = clear
SE_DACL_AUTO_INHERIT_REQ = clear
SE_DACL_AUTO_INHERITED   = clear
SE_OWNER_DEFAULTED       = clear
```

All ACE flags are zero, so no ACE claims object/container inheritance. CNG keys
are not treated as filesystem children and no filesystem inheritance behavior
is assumed. `SE_SELF_RELATIVE` is representation metadata and is expected on
the property buffer, but is not an authority difference after parsing.

Microsoft documents how to set and inspect `SE_DACL_PROTECTED`, but does not
explicitly promise how the Microsoft Software KSP persists that control bit
through `NCRYPT_SECURITY_DESCR_PROPERTY`. The exact disposable test must prove
it after independent reopen. Loss of protection, insertion of default/inherited
ACEs, or other control drift blocks production.

## Property timing and ceremony ordering

Microsoft documents that after `NCryptCreatePersistedKey`, properties may be
set with `NCryptSetProperty`, and that the key cannot be used until
`NCryptFinalizeKey`. It does not separately enumerate the pre-finalization
timing of every built-in property for the Microsoft Software KSP.

The frozen candidate production order is:

```text
prove host + exact elevated Administrator token
-> open exact provider
-> require security-descriptor support == 1
-> require exact machine-scope production name absent
-> create exact named machine key without overwrite
-> set usage 0x00000002 with flags 0x80000040
-> get/readback usage == 0x00000002
-> set export policy 0 with flags 0x80000040
-> get/readback export policy == 0
-> set owner + protected DACL in one operation with flags 0x80000045
-> get/semantically verify owner + protected DACL with flags 0x00000045
-> finalize exactly once with flags 0x00000040
-> read all exact properties and security again
-> export public blob only and freeze SEC1
-> release original key handle
-> independently reopen exact provider/container/machine scope
-> re-read all exact properties and security
-> re-export public blob only and require identical SEC1
-> release reopened key and provider handles
-> freeze sanitized evidence and stop without signing
```

Usage, export policy, and the security descriptor are required before
finalization so no finalized production key is intentionally exposed with
unaccepted policy. Post-finalization writes are forbidden in the production
procedure.

The exact disposable test must prove that all three pre-finalization sets and
readbacks work and persist through close/reopen. If the Microsoft Software KSP
requires `NCRYPT_SECURITY_DESCR_PROPERTY` only after finalization, that result
is an Architecture-97 ceremony-order contradiction. The test must retain its
key/evidence and stop with:

```text
ARCHITECTURE_97_NARROW_CORRECTION_REQUIRED=True
```

No such contradiction is established by the authoritative documentation
review in this checkpoint. Therefore:

```text
ARCHITECTURE_97_NARROW_CORRECTION_REQUIRED=False
```

for this docs-only checkpoint. Empirical failure can change that result only
through a later reviewed correction; it cannot silently reorder production.

## Canonical semantic security comparison

Raw `SECURITY_DESCRIPTOR` bytes are not an acceptance identity. Windows may
convert absolute descriptors to self-relative form and may canonicalize an ACL.
The verifier must parse and normalize the returned descriptor.

Required checks are:

1. `IsValidSecurityDescriptor` succeeds;
2. owner is present, non-defaulted, and exactly `S-1-5-32-544`;
3. `GetSecurityDescriptorDacl` reports DACL present;
4. the DACL pointer is non-NULL;
5. DACL defaulted is false;
6. control bits match the required semantic state above;
7. ACL revision is valid for the ACE set;
8. ACE count is exactly two;
9. each ACE parses completely with no trailing or malformed data;
10. each ACE type, flags, principal SID, and access mask matches exactly; and
11. no unexpected or duplicate ACE exists.

The input construction order is SYSTEM then Administrators. Both are explicit
allow ACEs with identical flags and masks, so Windows canonical order does not
define a security-significant order between them. The semantic verifier
normalizes each ACE to:

```text
(ace_type, ace_flags, principal_sid_canonical_string, access_mask)
```

and sorts by that tuple before comparing to the frozen two-entry set. It also
records the provider-returned physical order as evidence. Reordering those two
equal-class allows is permitted; any different type, flags, SID, mask, count,
or inherited/default state fails. This is semantic canonicalization, not a
license to discard unknown fields.

## Disposable native test-key gate

No disposable key is created by this checkpoint. A later native harness
requires a separate ChatGPT/Sol review and explicit security-effect approval.
It must use the exact Microsoft Software KSP, ECDSA_P256, and machine scope, but
a reviewed TEST-only container that can never equal or alias:

```text
AITradingBot-P3R1-Recovery-v1
```

The test name must be unique, fixed in the reviewed procedure, preflight-absent,
and never reused after any creation attempt. The harness must prove:

1. exact provider name and security-descriptor support `DWORD == 1`;
2. absent-name/create-new behavior and no overwrite;
3. exact pre-finalization property-set/readback timing and flags;
4. signing-only usage equals `0x00000002` before/after/reopen;
5. export policy equals zero before/after/reopen;
6. exact machine scope and wrong-scope non-substitution;
7. exact ECDSA_P256/ECDSA/256 properties and stable names;
8. exact owner, DACL, protection, ACE types/flags/SIDs/masks after reopen;
9. close/reopen persistence and stable public/unique identity evidence;
10. `BCRYPT_ECCPUBLIC_BLOB` export and exact SEC1 conversion succeed;
11. all relevant private/opaque/PKCS#8 export requests are denied;
12. the elevated authorized operator performs exactly one TEST-key signature;
13. that signature verifies with the exported TEST public point;
14. Trading cannot open/use the private key or sign;
15. Trading cannot change owner/DACL, delete, or privately export the key;
16. a same-name current-user TEST key cannot substitute for the machine key; and
17. altered/default/unprotected/unexpected ACL states are rejected by the
    semantic verifier.

Where a negative operation cannot be attempted without first obtaining a key
handle, the expected access-denied open is sufficient and the evidence must say
that the downstream operation was unreachable. The test must not weaken the
DACL merely to reach a later negative assertion.

The Trading-perspective and ordinary-non-admin-perspective checks must execute
under genuine tokens, not mocked SID strings. The elevated test-key signature
is a test effect only. No production public or private key is involved.

## Disposable failure and cleanup

Disposable-key creation is a security effect with one-way evidence semantics.

If every reviewed test passes, stop with the test key retained. A later,
separately reviewed cleanup phase may open and delete only that exact disposable
container, then independently prove the exact machine-scope name absent.

If any test fails or any return/outcome becomes uncertain after creation:

- retain the disposable key and sanitized evidence;
- do not delete, repair, overwrite, rename, refinalize, or automatically retry;
- do not reuse its container name;
- do not broaden usage, export, or ACL policy; and
- stop for review.

A retry requires a newly reviewed, distinct TEST container. None of these
cleanup semantics applies to the fixed production container, which remains
absent until an explicitly authorized production ceremony.

## Required production-ceremony inputs and evidence

The later non-executable production procedure must freeze at least:

```text
host identity and expected machine authority
exact elevated Administrator SID and elevation facts
provider name
provider security-descriptor support value
algorithm and algorithm group
container and machine scope
create/open/finalize/export flags
key usage and export policy values
owner SID
DACL present/non-NULL/protected/default/inheritance state
ACE count, order evidence, types, flags, principal SIDs, and masks
security-property set/get flags
property timing and every readback phase
name and unique-name evidence
public BCRYPT blob header/length
public SEC1 bytes/length/SHA-256
independent reopen results
every native status code and sanitized failure boundary
handle-close completion
SIGNATURE_CREATED=False
PRIVATE_EXPORT_REQUESTED=False
```

Evidence must never contain private material, a key handle, raw process/token
secrets, a private blob, or a path treated as key identity.

## Architecture-97 trust separation preserved

This checkpoint does not modify:

- historical `AITradingBot/Authority/Bootstrap/v1` trust or bytes;
- `AITradingBot/Authority/P3R1Recovery/v1` as the recovery-only key ID;
- the separation of bootstrap and recovery registries;
- Architecture-96 canonical authorization/domain/permit rules;
- the prohibition on signing the old unsigned authorization;
- immutable old release, RECORD, authorization, and staging evidence;
- Architecture-95 retained-staging recovery semantics; or
- isolated installation with `python.exe -I -m pip --isolated install` and the
  accepted no-index/no-deps/no-cache/no-input restrictions.

## Non-authorizations and remaining gate

```text
PRODUCTION_KEY_CREATED=False
PRODUCTION_KEY_OPENED=False
DISPOSABLE_TEST_KEY_CREATED=False
SIGNATURE_CREATED=False
PRIVATE_EXPORT_REQUESTED=False
KSP_PROPERTY_MUTATED=False
KSP_ACL_MUTATED=False
SEALED_RUNTIME_MUTATED=False
PRODUCTION_PAPER_PATH_ACCESSED=False
PRODUCTION_RECOVERY_RENAME=NOT_AUTHORIZED
PROVIDER_CALL_7=NOT_AUTHORIZED
P4_PRODUCTION_EXECUTION=BLOCKED
PRODUCTION_LIVE=NO-GO
```

Architecture 98 is ready for ChatGPT/Sol review as a docs-only proposed
contract. Acceptance authorizes only review/preparation of the separate
disposable native harness. Production key creation remains blocked until that
harness and its host evidence are separately accepted.
