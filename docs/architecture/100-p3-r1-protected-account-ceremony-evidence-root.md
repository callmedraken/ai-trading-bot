# Architecture 100: P3-R1 protected account-ceremony evidence root

## Status and scope

**DOCS-ONLY SECURITY-ARCHITECTURE CHECKPOINT -- REVIEW REQUIRED**

This contract resolves the filesystem-authority blocker discovered while preparing
the Architecture-99 ordinary non-admin test-principal ceremony. It changes only
the retained **account-ceremony evidence** boundary. It authorizes no filesystem
mutation, account or group mutation, password prompt, KSP operation, recovery
signing, provider call, production recovery, or P4/live operation.

Architectures 97, 98, and 99 remain authoritative except where this document
explicitly supersedes the Architecture-99 account-ceremony evidence-root location
and inherited-security assumption. The source-certified disabled account helper at
commit `d509537b88f66ef244d326e5417d38d9e5f25f53`, tree
`046ab722e6c888f6459bd7a8a28a3932c16d8cb9`, remains disabled and unchanged by
this architecture checkpoint.

The separate disposable KSP evidence root remains exactly
`F:\AI\p3-r1-ksp-disposable-test-v1`. Architecture 100 does not move, create,
repair, populate, or authorize that root.

## Blocker being resolved

The stopped read-only readiness inspection proved that default/NULL-security
creation below `F:\AI` is incompatible with the accepted retained-evidence threat
model:

- `F:\AI` inherits and contains untrusted write-capable ACEs;
- `NT AUTHORITY\Authenticated Users`, `DESKTOP-I4DOKM7\CodexSandboxUsers`, and
  one unresolved SID have effective `DELETE` on `F:\AI`;
- `F:\AI` grants no untrusted `FILE_DELETE_CHILD`, `WRITE_DAC`, or `WRITE_OWNER`;
- a protected child DACL would exclude inherited writers from that child, but
  would not prevent cross-run displacement of the writable `F:\AI` ancestor;
- while the helper's retained no-delete-share guards are held, that specific
  ancestor-rename avenue is conditionally blocked, but once the handles close
  the pathname is not persistently anchored.

The finding establishes a pathname-availability/integrity failure for the strict
cross-run contract. It does **not** establish that forged evidence could satisfy
the helper's record, owner, DACL, or identity checks.

Architecture 100 does not weaken `TrustedWriter` and does not modify the existing
ACL of `F:\` or `F:\AI` to make the old path pass.

## Decision: the evidence root itself is the protected top-level anchor

Do not introduce a separately provisioned intermediate anchor whose lifecycle
would require another create/adopt/recovery ceremony. Instead, the
account-ceremony evidence root itself becomes the protected top-level directory
under the already observed fixed NTFS volume root.

The exact new path is:

```text
F:\p3-r1-ordinary-nonadmin-principal-v2
```

The old path:

```text
F:\AI\p3-r1-ordinary-nonadmin-principal-v1
```

is retired before any effect occurred. It must remain absent and must never be
created, adopted, repaired, redirected to, or used as a fallback by Architecture
100 source or ceremony execution.

The new evidence schema version is:

```text
p3-r1-ordinary-nonadmin-principal-evidence/v2
```

No v1 evidence exists to migrate. There is no v1-to-v2 adoption or conversion
path.

## Why a top-level protected root is materially different

The reviewed read-only descriptor capture showed that untrusted effective ACEs
on `F:\` did **not** grant `FILE_DELETE_CHILD`, `WRITE_DAC`, or `WRITE_OWNER`.
They did include ordinary creation/write rights and an effective `DELETE` bit on
the volume-root object itself.

For the top-level evidence-root pathname, the architecture therefore requires
both normal namespace-removal routes to be absent for every untrusted principal:

```text
DELETE on F:\p3-r1-ordinary-nonadmin-principal-v2 = absent
FILE_DELETE_CHILD on F:\                         = absent
```

The protected child DACL supplies the first property. A fresh parent-authority
proof supplies the second. The design does not depend on the special semantics of
attempting to rename/delete a mounted volume root merely because its descriptor
contains `DELETE`; it binds the parent handle to the intended local NTFS volume
identity and treats any failure to establish that identity as a STOP.

Untrusted `FILE_ADD_SUBDIRECTORY` on `F:\` remains relevant only before creation:
an untrusted principal may pre-create the fixed name and cause a fail-closed
collision. That is an accepted denial-of-service risk. It never authorizes
adoption, deletion, repair, alternate-name selection, or retry.

## Trusted and untrusted principals

For this boundary, trusted security writers remain limited to:

```text
exact P3-R1 creator SID
  S-1-5-21-1397534616-3988210162-180023805-1005
BUILTIN\Administrators
  S-1-5-32-544
NT AUTHORITY\SYSTEM
  S-1-5-18
```

Every other SID is untrusted unless a later architecture checkpoint explicitly
changes the threat model. Display-name familiarity is not authority. An
unresolved SID remains untrusted.

`Trading` (`...-1009`), the future `P3R1KspTestUser`, Authenticated Users,
BUILTIN\Users, Codex sandbox identities, and ordinary interactive/logon SIDs are
not security writers for this evidence root.

## Create-time security descriptor

The root must be protected **at the successful create operation**. There is no
permitted sequence of:

```text
create with inherited/default DACL
-> later replace or repair DACL
```

The future creator uses an explicit `SECURITY_ATTRIBUTES` / security descriptor
with:

```text
owner:
  S-1-5-21-1397534616-3988210162-180023805-1005

DACL control:
  DACL present
  non-NULL
  SE_DACL_PROTECTED set

explicit allow ACEs, canonical order, and no others:
  NT AUTHORITY\SYSTEM       FULL_CONTROL  OBJECT_INHERIT | CONTAINER_INHERIT
  BUILTIN\Administrators    FULL_CONTROL  OBJECT_INHERIT | CONTAINER_INHERIT
```

Conceptual SDDL:

```text
O:S-1-5-21-1397534616-3988210162-180023805-1005D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)
```

The implementation must construct and validate the native descriptor rather than
trusting textual SDDL equality alone. The primary-group field is not an access
authority in this contract and is not used to admit a writer; it must still be
safely decoded and retained as an observation if Windows supplies one.

There is deliberately no Users read/execute ACE. The ordinary test account does
not need direct filesystem access to its account-creation evidence; its genuine
interactive qualification facts are transferred through the already reviewed
sanitized operator-observation boundary. Adding an ordinary-user ACE requires a
new architecture review.

Default-created evidence records below the protected root may inherit only the
SYSTEM and Administrators ACEs above. Any additional inherited/effective ACE,
DACL de-protection, unexpected owner, malformed descriptor, or unresolved access
state is a STOP.

## Exact create-new boundary

The future helper must retain one code-owned path and no caller/environment path
override. It must prove the final component definitely absent and then call one
reviewed Win32 create-new operation with the explicit protected descriptor.

`CreateDirectoryW` with non-NULL security attributes is an acceptable baseline
surface because the security descriptor is applied to the directory at creation.
The source checkpoint may select an equivalent documented Windows create-new
surface only if Architecture 100 is amended before execution.

Required outcomes:

| Creation result | Disposition |
| --- | --- |
| Success | Retain the directory permanently; immediately obtain/hold a no-delete-share directory handle and independently verify identity/security before any record publication or account effect. |
| `ERROR_ALREADY_EXISTS` | STOP. Never adopt, delete, inspect as candidate evidence, repair, rename, or select a suffix. |
| Any other failure/exception/lost return | STOP with root-creation outcome uncertain only when the implementation cannot prove whether creation occurred. Perform read-only reconciliation only; never retry. |

A successful create followed by failed identity/security verification leaves the
root retained and blocks the ceremony. No ACL repair or root recreation exists.

## Parent and volume authority gate

Immediately before root creation, and on every later process entry that consumes
or extends the evidence chain, prove read-only that `F:\` is the intended local
volume root and that its effective namespace authority still satisfies this
contract.

At minimum bind and verify:

- drive type is fixed/local;
- handle-resolved path is a volume root, not a reparse traversal;
- filesystem is NTFS with persistent ACL support;
- volume GUID and volume serial equal the values frozen by the accepted
  execution-readiness checkpoint;
- `F:\` itself is not a reparse point;
- owner/DACL can be decoded completely and canonically;
- no untrusted effective ACE grants `FILE_DELETE_CHILD`, `WRITE_DAC`, or
  `WRITE_OWNER` on the parent;
- no untrusted authority otherwise demonstrated by the reviewed Windows access
  model can replace the protected child despite its own missing `DELETE` right.

The September 2 diagnostic observations:

```text
volume GUID:   \\?\Volume{16af2363-e432-4684-be5a-9861a99741b4}\
volume serial: 0x6E962F80
filesystem:    NTFS
```

are discovery evidence, not perpetual authority. The next full readiness freeze
must re-observe and explicitly accept them before any effect is authorized. A
changed/missing volume identity is a STOP, not permission to update the expected
value in place.

## Root identity and cross-run continuity

After successful creation, open the exact final component as a directory using
`OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS` and a share mode that excludes
`FILE_SHARE_DELETE`. Hold the parent/root guards required by the accepted helper
through every in-run publication boundary.

Independently prove and retain at minimum:

```text
volume GUID
volume serial
root file identity
root owner SID
root DACL semantic form
SE_DACL_PROTECTED
reparse-point absence
resolved final path
```

Every later process entry must reopen with reparse-point-safe semantics and prove
all frozen root and volume identities before trusting existing records. Path text,
a matching directory name, owner alone, DACL alone, or hash-chain validity alone
cannot re-establish retained evidence authority.

If the expected path is missing, refers to a different file identity, is a
reparse point, is on another volume, has a changed owner/DACL, or cannot be
proved completely, STOP. Do not search for a moved root, follow a junction,
repair the path, copy records, or adopt another object.

## Evidence publication and v2 root identity

Architecture 99's create-new, gap-free, hash-linked, write-through, flush,
close, reload, strict-schema, one-way lifecycle, and failure-retention semantics
remain unchanged except for the root path/schema version and the strengthened
root-identity binding below.

Every v2 record's `ceremony.evidence_root` is exactly:

```text
F:\p3-r1-ordinary-nonadmin-principal-v2
```

The v2 `PREFLIGHT` `root_identity` object must contain the accepted immutable
root/volume binding, including at least:

```text
volume_guid
volume_serial
file_id
owner_sid
dacl_semantic_identity
dacl_protected
reparse_point
```

The source checkpoint must freeze exact canonical field names/types and the
semantic DACL-identity encoding before any effect is authorized. Raw native
pointers, handles, arbitrary exception text, or caller-provided security strings
are never evidence authority.

Record files inherit only the protected root's reviewed ACEs. Record publication
must still use create-new semantics and retain/reload exact bytes before any
dependent Windows mutation.

## Failure and retry policy

Security-root creation is itself a separately gated Windows filesystem/security
effect. Architecture 100 authorizes none.

Once an authorized root-creation call may have begun, it is one-shot for the
fixed v2 pathname. Ambiguity never becomes permission to call create again.
Read-only reconciliation may classify the retained object; it cannot adopt,
repair, overwrite, rename, delete, or resume the ceremony.

A pre-existing-name collision remains fail-closed denial of service. Do not
weaken the DACL, change `TrustedWriter`, grant `FILE_DELETE_CHILD`, modify
`F:\`/`F:\AI`, or choose another evidence path merely to get past that failure.

## Superseded account-ceremony clauses

For the account ceremony only, Architecture 100 supersedes these clauses in the
accepted creation-ceremony document and disabled helper contract:

```text
old root:
  F:\AI\p3-r1-ordinary-nonadmin-principal-v1

old schema:
  p3-r1-ordinary-nonadmin-principal-evidence/v1

old root creation:
  CreateDirectoryW(path, NULL)
  then verify inherited security

old parent assumption:
  F:\AI and ancestors must already make default inheritance safe
```

All other ceremony contracts remain in force: exact actor/token authority, dual
name absence, secure password handling, NetUserAdd one-shot semantics, Users
baseline branch, qualification, sanitized evidence, no cleanup/repair/retry, and
separate effect authorization.

The KSP evidence-root contract is explicitly **not** superseded.

## Required source-only follow-up

After Architecture 100 is accepted, the next source checkpoint is bounded to the
account-ceremony helper, wrapper if required, and focused tests. Effects remain
disabled.

That checkpoint must:

1. replace the v1 `F:\AI` root and schema constants with the exact v2 contract;
2. implement explicit protected-DACL construction at create time;
3. reject any extra/untrusted effective root ACE and require the exact trusted
   owner/protection semantics;
4. implement parent `FILE_DELETE_CHILD` / `WRITE_DAC` / `WRITE_OWNER` and fixed
   volume-identity gates without treating unrelated read/execute rights as
   writer authority;
5. preserve the existing no-delete-share in-run guard and strengthen re-entry to
   require frozen volume/root identity;
6. update canonical v2 root-identity evidence and strict loader validation;
7. keep `ACCOUNT_EFFECT_EXECUTION_AUTHORIZED=false` and all mutation/password
   paths unreachable in ordinary invocation/tests;
8. add focused fake/native-model tests for unsafe parent delete-child authority,
   DACL de-protection, wrong owner, extra ACEs, wrong volume/file identity,
   reparse substitution, pre-created-name collision, uncertain create, and
   successful protected-root inheritance.

No production files, KSP harness source, recovery key material, provider code, or
unrelated subsystem may change in that source checkpoint.

## Readiness restart rule

Source certification does not resume the old readiness run after the prior DACL
STOP. The complete read-only execution-readiness freeze must restart from its
first gate against the new reviewed source and v2 root contract.

That future freeze must establish, among its other already-required facts:

- exact Git/source hashes and disabled effect gate;
- exact candidate-account absence;
- old v1 root absence and new v2 root absence before first creation;
- exact `F:\` volume/parent security and namespace-removal authority;
- builtin Users mapping;
- special-group topology and the INTERACTIVE/Performance Log Users provenance;
- password/account policy and logon-right prerequisites;
- exact Windows PowerShell 5.1, helper, Git, and Netapi32 identities;
- the exact future source-enablement diff.

Only a separately reviewed authorization after that complete freeze may permit
one protected-root creation and the already frozen account/group effects.

## Non-authorizations

```text
ACL_MUTATION=NOT_AUTHORIZED
PROTECTED_EVIDENCE_ROOT_CREATION=NOT_AUTHORIZED
CEREMONY_EVIDENCE_PUBLICATION=NOT_AUTHORIZED
ACCOUNT_CREATION=NOT_AUTHORIZED
WINDOWS_GROUP_MUTATION=NOT_AUTHORIZED
PASSWORD_PROMPT=NOT_AUTHORIZED
DISPOSABLE_NATIVE_EXECUTION=NOT_AUTHORIZED
DISPOSABLE_TEST_KEY_CREATION=NOT_AUTHORIZED
CURRENT_USER_SHADOW_CREATION=NOT_AUTHORIZED
TEST_SIGNATURE=NOT_AUTHORIZED
PRIVATE_EXPORT_REQUEST=NOT_AUTHORIZED
PRODUCTION_RECOVERY_KEY_CREATION=NOT_AUTHORIZED
PRODUCTION_SIGNING=NOT_AUTHORIZED
PROVIDER_CALL_7=NOT_AUTHORIZED
P3_TRADING_ACCEPTANCE=BLOCKED
P4_PRODUCTION_EXECUTION=BLOCKED
PRODUCTION_LIVE=NO-GO
```

## Acceptance criteria for this architecture checkpoint

Architecture 100 is acceptable only if review confirms all of the following:

- the old `F:\AI` root is abandoned without mutation or migration;
- the evidence root itself, not a new intermediate anchor, is the protected
  top-level namespace object;
- creation applies the protected DACL atomically with object creation;
- ordinary/untrusted principals receive no ACE on the root;
- parent `FILE_DELETE_CHILD`, root `DELETE`, reparse, owner/DACL, volume, and
  file-identity continuity are all explicit gates;
- pre-creation name squatting remains fail-closed denial of service;
- no recovery path adopts, repairs, deletes, renames, or retries an uncertain
  root;
- Architecture 99's account/group/password and one-way evidence semantics remain
  otherwise unchanged;
- the separate KSP evidence root remains untouched;
- every Windows/security/account/KSP/production effect remains separately gated.
