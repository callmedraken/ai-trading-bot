# P3-R1 disposable KSP test harness runbook boundary

## Status

**INERT SOURCE HARNESS — NATIVE EXECUTION NOT AUTHORIZED**

This document describes the test-only harness structure implemented for
Architectures 97 and 98. It is not an operator procedure and intentionally
contains no command that can enable a native phase. Acceptance of this source
does not authorize a disposable key, production key, signature, private-export
request, KSP property or ACL change, cleanup, provider call, recovery, P4, or
live trading.

The bounded implementation is:

```text
scripts/run_p3_r1_ksp_disposable_test.py
tests/runtime/test_p3_r1_ksp_disposable_test.py
```

The script remains outside the production `trading_bot` package. Its ordinary
CLI only prints the frozen, non-authorizing contract. It has no CLI or
environment option for a container name, evidence root, native phase, cleanup,
or native-execution authorization.

## Frozen disposable identities

The code-owned textual name is exactly:

```text
AITradingBot-P3R1-KSP-TEST-800CA51-v1
```

It is used by exactly these future scope-qualified identities:

```text
MACHINE_TEST_KEY=(
  Microsoft Software Key Storage Provider,
  local-machine,
  AITradingBot-P3R1-KSP-TEST-800CA51-v1
)

CURRENT_USER_SHADOW_KEY=(
  Microsoft Software Key Storage Provider,
  current-user of S-1-5-21-1397534616-3988210162-180023805-1005,
  AITradingBot-P3R1-KSP-TEST-800CA51-v1
)
```

Source guards require that exact TEST name and reject equality,
case-normalized equality, separator-insensitive aliasing, or production-prefix
equivalence with:

```text
AITradingBot-P3R1-Recovery-v1
```

The future evidence root is fixed as:

```text
F:\AI\p3-r1-ksp-disposable-test-v1
```

It is not created by this checkpoint. A future effect procedure must require
it absent and publish with create-new/no-overwrite semantics. Pure tests use
only pytest `tmp_path` through an explicitly test-only publisher.

## Inert execution boundary

The native-effect authorization constant is false and its authorization ID is
explicitly marked not authorized. The authorization check runs before loading
`ncrypt.dll`, `advapi32.dll`, or `kernel32.dll`, and before dispatching any
native phase operation. No command-line or environment value can change it.

The source contains typed, lazy bindings so they can be reviewed without being
used. They cover:

```text
NCryptOpenStorageProvider
NCryptCreatePersistedKey
NCryptOpenKey
NCryptSetProperty
NCryptGetProperty
NCryptFinalizeKey
NCryptExportKey
NCryptSignHash
NCryptFreeObject
```

It also binds the Windows SID, token, security-descriptor, ACL-construction,
and semantic-inspection APIs required by Architecture 98. `NCryptDeleteKey` is
deliberately absent. Cleanup must be implemented and authorized in a separate
future executable surface.

This checkpoint implements no native phase body. A later review must supply
the exact effect implementation and replace the disabled source gate. Merely
setting an environment variable or passing a caller assertion can never
authorize it.

## Multi-session phase contract

The retained state machine has this exact order:

```text
READ_ONLY_PREFLIGHT
MACHINE_CREATE_AND_VALIDATE
SHADOW_CREATE_AND_SCOPE_PROOF
ELEVATED_MACHINE_EFFECT_TEST
TRADING_DENIAL
ORDINARY_NONADMIN_DENIAL
FINAL_EVIDENCE_RECONCILIATION
```

Each result records its code-owned expected actor SID and is linked to the
previous result digest. A missing, duplicated, reordered, tampered, failed,
blocked, or uncertain prior result prevents a later result. Later sessions must
load and validate retained evidence; they cannot replace it with CLI claims.
The evidence chain is sanitized test evidence, not production authority.

Future phase responsibility is:

1. `READ_ONLY_PREFLIGHT` proves the exact elevated operator, provider support,
   fixed evidence-root absence, production guards, and absence of the TEST name
   in both machine and exact-operator current-user scope before either create.
2. `MACHINE_CREATE_AND_VALIDATE` creates the machine object first, without
   overwrite, and performs the exact Architecture-98 pre-finalization property,
   security-descriptor, finalization, public export, close/reopen, and readback
   sequence.
3. `SHADOW_CREATE_AND_SCOPE_PROOF` creates the same-text current-user object
   only after machine success and proves distinct public identity, scope, and
   key type. The shadow receives no production authority, signature, private-
   export request, or machine-security acceptance role.
4. `ELEVATED_MACHINE_EFFECT_TEST` performs the reviewed machine-only private-
   export denial matrix and consumes the one TEST signing attempt only after
   every prerequisite has succeeded.
5. `TRADING_DENIAL` runs under the genuine non-elevated Trading token.
6. `ORDINARY_NONADMIN_DENIAL` runs under a separately frozen genuine ordinary
   non-admin token.
7. `FINAL_EVIDENCE_RECONCILIATION` verifies the complete retained state and
   stops with both TEST keys retained. It performs no cleanup.

## Ordinary non-admin identity blocker

Read-only account and Administrators-group inspection on the development host
showed enabled non-administrator account candidates. None was already reviewed
and frozen as a suitable distinct ordinary non-admin test principal. The
harness therefore records:

```text
ORDINARY_NONADMIN_TEST_IDENTITY_BLOCKED=True
ORDINARY_NONADMIN_TEST_SID=None
```

It does not choose a candidate, create an account, accept a caller SID, reuse
Trading as the additional perspective, or skip the phase. The ordinary-user
phase and final reconciliation remain structurally unreachable until a later
review freezes one exact suitable SID.

## Pure security-descriptor verifier

The pure semantic verifier requires:

```text
owner = S-1-5-32-544, non-defaulted
DACL = present, non-NULL, explicit, non-defaulted, protected
SE_DACL_AUTO_INHERIT_REQ = clear
SE_DACL_AUTO_INHERITED = clear
ACE count = 2
ACE type = ACCESS_ALLOWED_ACE_TYPE
ACE flags = 0
ACE mask = 0x001F019B
SIDs = S-1-5-18 and S-1-5-32-544 exactly once each
```

It permits only physical reordering of the two same-class allow ACEs after
normalizing their semantic tuples. It rejects invalid/malformed descriptors,
trailing material, wrong/defaulted owner, missing/NULL/empty/defaulted/
unprotected DACLs, control drift, invalid ACL revisions, missing/extra/
duplicate ACEs, deny/unknown ACEs, nonzero or inherited flags, wrong SIDs,
Trading/operator-user grants, wrong masks, and `GENERIC_ALL` substitution.
Raw descriptor-byte equality is never authority.

The future native decoder must use the bound SID and security APIs to produce
this semantic representation. Display names, shell parsing, backing filenames,
and filesystem ACLs are not accepted as key authority.

## Public identity and scope proof

The pure public-key normalizer accepts only an exact 72-byte
`BCRYPT_ECCPUBLIC_BLOB` with:

```text
magic = BCRYPT_ECDSA_PUBLIC_P256_MAGIC
cbKey = 32
X = 32 bytes
Y = 32 bytes
```

It additionally proves that the unsigned big-endian coordinates are in the
P-256 field and satisfy the P-256 curve equation, then emits exactly
`0x04 || X || Y`. Short, long, trailing, wrong-magic, wrong-length, out-of-field,
and off-curve inputs fail.

The scope verifier requires the machine open to report key type `0x20` and the
current-user open to lack the machine bit. Both must match their frozen
provider, scope, container, algorithm/group/length, and public point, and their
public identities must differ. Equal container text alone never passes.

## Lifecycle and one-way effects

The evidence model retains independently:

```text
MACHINE_TEST_KEY_CREATION_ATTEMPTED
MACHINE_TEST_KEY_CREATED
CURRENT_USER_SHADOW_CREATION_ATTEMPTED
CURRENT_USER_SHADOW_CREATED
```

The first machine create attempt retires the textual TEST name. A failed or
uncertain machine attempt makes the shadow phase unreachable. A failed or
uncertain shadow attempt retains the machine key. Any later failure retains
every possibly created scope-qualified key and all available sanitized
evidence. There is no automatic delete, repair, overwrite, rename, refinalize,
or retry path.

The signature gate accepts only `MACHINE_TEST_KEY`, requires retained success
through the scope-proof phase, and records the single attempt before the native
call. Its initial result is uncertain, so an exception or ambiguous return
cannot allow a second call. Final success or failure also leaves the attempt
consumed. The shadow and production identity are rejected structurally.

Private-export denial probes likewise require retained scope-proof success and
route only to `MACHINE_TEST_KEY`. Duplicate probes, the shadow, and the
production container are rejected before native dispatch. This source does not
perform any probe.

## Evidence restrictions

Canonical evidence contains only fixed identities, lifecycle booleans,
hash-linked phase results, sanitized outcome state, and the names of attempted
denial probes. It contains no private key material, private blob, provider/key
handle, credentials, Credential Manager data, broker/provider secret, or
production permit. Publication is create-new/no-overwrite.

Successful future native validation retains both scope-qualified TEST objects.
Deletion remains a separate reviewed checkpoint that must name each exact
provider/scope/container identity and prove absence independently in both
scopes. This harness contains no cleanup fallback.

## Current no-effect result

For this implementation and pure-test checkpoint:

```text
DISPOSABLE_TEST_KEY_CREATION=NOT_AUTHORIZED
CURRENT_USER_SHADOW_CREATION=NOT_AUTHORIZED
TEST_SIGNATURE=NOT_AUTHORIZED
PRODUCTION_RECOVERY_KEY_CREATION=NOT_AUTHORIZED
KSP_ACL_MUTATION=NOT_AUTHORIZED
KSP_PROPERTY_MUTATION=NOT_AUTHORIZED
PRIVATE_EXPORT_REQUEST=NOT_AUTHORIZED
PRODUCTION_RECOVERY_RENAME=NOT_AUTHORIZED
PROVIDER_CALL_7=NOT_AUTHORIZED
P4_PRODUCTION_EXECUTION=BLOCKED
PRODUCTION_LIVE=NO-GO
```
