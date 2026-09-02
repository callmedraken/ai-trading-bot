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

Even after a future reviewed authorization replaces that disabled boundary,
the real `execute_next_retained_native_phase` entrypoint accepts only a requested
phase. It accepts no caller evidence, path, environment input, or operations
adapter. It derives authority only from the fixed evidence root, strictly loads
and validates the latest snapshot when the root exists, and requires the
requested phase to equal the one exact legal next phase. An absent root can
start only from a new empty `HarnessEvidence` and only for read-only preflight.
The separately pure-testable runner receives fake stores and fake operations;
the ordinary CLI and real entrypoint expose no such injection surface.
The generic `NativeWindowsPhaseOperations.execute` rejects a real ctypes
adapter; its in-memory evidence parameter remains a fake-test surface only.
Real dispatch is private to the fixed-root entrypoint after retained-state
validation and durable pre-effect transitions.

The source contains typed, lazy bindings and the exact future phase bodies so
they can be reviewed without being used. They cover:

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

`NativeWindowsPhaseOperations` contains the future read-only preflight,
machine creation/validation, current-user shadow, elevated TEST effect,
principal-denial, and final-reconciliation bodies. `CtypesNativeApi` contains
the exact lazy NCrypt/token/security implementation, while tests inject only a
fake adapter. These bodies remain unreachable because the source gate is still
false. A later review must replace that disabled source gate before the bodies
can load a DLL or make a native call. Merely setting an environment variable,
passing a caller assertion, importing the module, or invoking the ordinary CLI
cannot authorize them.

The future native implementation owns every provider, key, process-token, and
`LocalFree` allocation with a one-owner release helper. Successful acquisition
is released at most once, nonexistent handles are never released, and release
failure is retained as an uncertain phase result. `NCryptDeleteKey` is absent.

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

Each result records its code-owned expected actor SID, a canonical immutable
snapshot of the security-relevant state that justified the result, the snapshot
digest, and the predecessor/result digests. A missing, duplicated, reordered,
tampered, failed, blocked, or uncertain prior result prevents a later result.
Later sessions must load and validate retained evidence; they cannot replace it
with CLI claims. The evidence chain is sanitized test evidence, not production
authority.

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

The pre-dispatch validator additionally requires the exact in-progress state
for the effect-bearing create phases: the machine attempt and name retirement
must already be retained before machine dispatch, and the shadow attempt must
already be retained before shadow dispatch. Machine creation failure or
uncertainty therefore cannot reach shadow dispatch. Elevated-effect dispatch
requires both keys and pristine signature/export-attempt state; it cannot be
used as a retry surface. Trading, ordinary-user, and final dispatch each require
the exact immediately preceding success. The ordinary-user phase remains
ineligible while its exact SID is blocked.

The fixed-root runner durably publishes and reloads the machine or shadow
`begin_*` transition before it constructs the real operations adapter or
dispatches the native create. A mismatch, publication error, reload error, or
validation error at that boundary prevents the effect call.
An attempt marker found by a later invocation is not permission to resume or
retry creation: the runner refuses that unresolved attempt state.

## Phase-specific completion proofs

A generic `SUCCEEDED` outcome is insufficient. Each success record must include
the exact pure, sanitized completion type for its phase:

- preflight proves both-scope absence, evidence-root absence, provider security-
  descriptor support, and the frozen elevated operator SID;
- machine completion binds exact machine metadata/public identity plus property,
  security-descriptor, and independent-reopen verification;
- shadow completion binds both scope-qualified metadata/public identities and
  successful non-substitution proof;
- elevated-effect completion requires the single successful TEST signature,
  independent verification with the machine public identity, and the complete
  accepted private-export denial matrix;
- Trading and future ordinary-user success each require a dedicated denial
  completion bound to the exact actor SID; and
- final reconciliation requires every predecessor success, retained keys,
  complete evidence reconciliation, no unresolved effect, and no cleanup.

`FAILED`, `UNCERTAIN`, and `BLOCKED` remain one-way terminal outcomes. They do
not accept a success-completion object and cannot acquire successors.

## Ordinary non-admin identity blocker

Read-only local-user, local-group, nested-group, and current-token inspection
was repeated on 2026-09-01. The sanitized relevant facts were:

- `...-1007` (`CodexSandboxOffline`) and `...-1008`
  (`CodexSandboxOnline`) are enabled local accounts, direct members of
  `Users` and `CodexSandboxUsers`, and not direct members of Administrators.
  The current `...-1007` process token was a genuine medium-integrity
  interactive token. Both sandbox identities are nevertheless infrastructure
  identities; interactive tokens on this host also receive `Performance Log
  Users` through the local `INTERACTIVE` group, so neither was silently
  promoted to the frozen ordinary-test role.
- `...-1003` (`defaultuser0`) is enabled but is an old Windows setup/default
  identity with no current suitability proof.
- `...-1005` is the frozen Administrator, `...-1009` is Trading, and the
  built-in Guest/DefaultAccount/WDAG/Administrator identities are excluded or
  disabled.

Zero candidates could therefore be confidently qualified without review, and
multiple sandbox identities remain materially plausible. The harness records:

```text
ORDINARY_NONADMIN_TEST_IDENTITY_BLOCKED=True
ORDINARY_NONADMIN_TEST_SID=None
ORDINARY_NONADMIN_SELECTION_REQUIRES_REVIEW=True
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
production container are rejected before native dispatch. Each required format
has one fixed result slot with the states:

```text
NOT_ATTEMPTED
ATTEMPTED_UNCERTAIN
DENIED_AS_REQUIRED
UNSUPPORTED_FORMAT
FAILED
```

The gate writes `ATTEMPTED_UNCERTAIN` before a future native request. Every
other outcome is terminal, and neither an uncertain nor a terminal result can
be retried. `UNSUPPORTED_FORMAT` stays distinguishable from a policy denial and
does not satisfy elevated-effect success. This source performs no probe.

## Hash-linked evidence integrity

Every phase snapshot deterministically commits, as applicable, to lifecycle
attempt/created/name-retired facts, the typed completion proof, machine/shadow
scope-qualified public metadata, signature attempt/outcome, and every private-
export probe result. The phase-record digest separately commits the actor SID,
phase, outcome, predecessor digest, and snapshot digest. Historical snapshots
remain stable when legitimate later phases add state; validation instead
requires current one-way state not to regress or contradict a committed fact.

Changing a snapshot without updating its digest, breaking predecessor linkage,
or changing current lifecycle/signature/probe state contrary to a committed
phase is detected. These unkeyed SHA-256 links provide deterministic integrity
and accidental/tamper evidence. They do not authenticate evidence against an
adversarial Administrator who can rewrite the evidence and recompute every
unkeyed digest. The evidence is never production authority.

The corrected canonical evidence schema is explicitly versioned
`p3-r1-ksp-disposable-test-evidence/v2`; no native v1 evidence exists or is
adopted.

The retained-evidence loader accepts only canonical ASCII v2 JSON. It rejects
v1, duplicate JSON keys, unknown or missing fields, wrong primitive types,
unknown enum/completion values, non-canonical bytes, malformed public-key hex,
and broken snapshot/record digests. It reconstructs every typed record and
runs `validate_harness_evidence` before returning evidence to a later session.
The future source-gated publisher creates the fixed root only for the first
successful preflight publication and then adds deterministic
`snapshot-<sequence>-<phase-count>-<canonical-sha256>.json` files with
exclusive-create mode. Sequence numbers must be gap-free from one; every
filename digest and phase count is re-proved, every prior snapshot is strictly
loaded, and every later snapshot must contain the exact prior phase prefix and
one-way lifecycle/signature/probe state. Unknown root entries fail closed. The
loader therefore selects the latest validated retained snapshot rather than a
caller assertion. The publisher never overwrites a prior snapshot. The phase
implementation invokes the configured retainer after every lifecycle
transition, probe/signature attempt marker, terminal probe/signature result,
and phase result; the real ctypes factory cannot be constructed without that
retainer and the still-disabled source authorization.

Persistent authority advances only after exclusive append, file flush and
`fsync`, strict reload, canonical validation, and exact equality with the
intended typed evidence. Retention failure has a dedicated uncertain error
classification. Before an effect, it prevents dispatch. After an effect may
have started, it stops immediately with `effect_may_have_occurred=True`; it
does not retry the effect and does not recursively attempt a best-effort
uncertain record. The last confirmed evidence pointer therefore never advances
to an unconfirmed state.
A simultaneous handle-release failure preserves the retention-uncertain
classification and both errors without calling the failed retainer again.

## Fixed TEST-signature domain

The future elevated effect phase first completes the machine-only
private-export denial matrix and then consumes exactly one signature attempt.
The fixed deterministic preimage is:

```text
ASCII("AITradingBot/P3R1/DisposableKSPValidation/TestSignature/v1")
|| 0x00
|| uint32_be(len(message))
|| ASCII("TEST-ONLY;NO-BOOTSTRAP;NO-P3R1-RECOVERY-AUTHORIZATION;NO-PRODUCTION-ORDER-OR-TRADING-AUTHORITY")
```

NCrypt signs only `SHA-256(preimage)`. The result must be exactly 64-byte IEEE
P1363 `r || s` and independently verify against the frozen machine TEST SEC1
public point. The explicit domain and message prevent the artifact from being
interpreted as bootstrap, recovery authorization, a production order, or
trading authority. The shadow is never signed with.

## Native property and security decoding

The future adapter reads every DWORD as exactly four bytes and every string as
exact null-terminated UTF-16 without embedded or trailing material. Property
size probes and data calls must agree. Only `NTE_BAD_KEYSET` is the reviewed
absence result; only `NTE_PERM` is the reviewed access/policy-denial result.
`NTE_NOT_SUPPORTED` is retained as `UNSUPPORTED_FORMAT` and cannot satisfy the
private-export denial matrix.

Provider identity is read from the provider handle using the documented
`NCRYPT_NAME_PROPERTY` (`"Name"`) and must equal
`Microsoft Software Key Storage Provider` exactly. The harness defines and
uses no invented `"Provider Name"` property. A successful
`NCryptCreatePersistedKey` status without a non-NULL returned key handle is
classified as an uncertain effect outcome, never ordinary success.
Likewise, a successful signature API status with an invalid required/returned
output length remains an uncertain consumed attempt.

Before calling any pointer-taking Windows validator, the native security-
descriptor decoder manually parses the 20-byte self-relative header and
bounds-checks owner/DACL offsets, exact SID lengths, ACL size/count, every ACE
header/size, and every embedded SID against the returned byte-string ranges.
Malformed data therefore cannot reach `IsValidSecurityDescriptor`, SID, ACL,
or ACE callbacks. Only after that complete pure bounds pass does it call the
bound Windows validity, owner, DACL, ACL, ACE, SID, and SID-string APIs as
secondary consistency checks; every returned pointer, size, count, and control
value must match the manually proven offsets and lengths. Descriptor, DACL,
ACE, SID, trailing-byte, pointer, or allocation-release ambiguity fails closed.
The resulting `SecurityDescriptorSemantic` is still passed to the pure verifier
as the sole semantic authority.

## Evidence restrictions

Canonical evidence contains only fixed identities, lifecycle booleans, typed
sanitized completion records, scope-qualified public metadata, hash-linked
phase snapshots/results, signature outcome state, and sanitized denial-probe
results. It contains no private key material, private blob, provider/key handle,
credentials, Credential Manager data, broker/provider secret, or production
permit. Publication is create-new/no-overwrite.

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
