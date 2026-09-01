# P3-R1 recovery signing trust re-establishment validation plan

## Status and scope

**DRAFT -- DOCS-ONLY VALIDATION CONTRACT -- REVIEW REQUIRED**

This plan validates Architecture 97 and its correction of Architecture 96. It
defines gates; it does not execute them in this checkpoint. It does not
authorize a key ceremony, signature, source implementation, release build,
deployment, retained-staging access, production recovery, provider call #7,
P4, or live trading.

Architectures 95 and 96 and their validation plans remain mandatory. Where the
Architecture-96 plan says the recovery verifier reuses bootstrap trust
material, this plan replaces that requirement with the separate
`P3R1Recovery/v1` identity and recovery-only registry. All other strict schema,
domain, permit, release, recovery-ordering, identity, crash, and no-effect
requirements continue unchanged.

## A. Startup/worktree gate

Before any later docs, implementation, test, ceremony, packaging, or deployment
checkpoint, prove the exact worktree, branch, HEAD, tree, and clean/expected
status supplied for that checkpoint. A mismatch is a stop condition. Never
self-correct with checkout, switch, reset, rebase, clean, prune, worktree
mutation, or cross-worktree copying.

For this docs checkpoint the frozen startup values are:

```text
WORKTREE=F:\AI\worktrees\ai-trading-bot-p3-r1
BRANCH=feature/p3-r1-recovery-implementation
HEAD=1941d470e8f3ede1f770e1aeca755e6f5e835391
TREE=82ba56ce9fbae32d032b18d2a53a4743b4c1be16
```

Only the two Architecture-97 documents may be untracked at completion. No test
is required for this docs-only checkpoint. If a later controlled Windows pytest
gate runs, it uses a fresh external `--basetemp` beneath
`F:\AI\temp\pytest\...` and normally `-p no:cacheprovider`; it never repairs or
deletes historical pytest/cache evidence.

## B. Old Bootstrap/v1 preservation gate

Freeze and compare the historical bootstrap trust material:

```text
KEY_ID=AITradingBot/Authority/Bootstrap/v1
PUBLIC_SEC1=04a73d90064e8b97e4a8373f48cac44718eb375ca52581233d614365294164efba40c6758f0f4cc455f6b2bf9b222696f9bc83c91ddf625fd01de46a6e7cd9c52e
PUBLIC_SEC1_BYTES=65
PUBLIC_SEC1_SHA256=72234cbe62bf0f82f8783b2a17854b263489cfc7f4bacbbcb3c8b04c74d6dbb4
```

Require exact historical `authority.bootstrap.json` and
`authority.bootstrap.sig` verification to continue passing through the
bootstrap-only verifier and `PRODUCTION_PINNED_BOOTSTRAP_KEYS`. Source diff and
tests must prove the bootstrap key, registry, canonical parser, signed bytes,
and signature verification behavior are unchanged. No recovery key may
authorize or reinterpret the bootstrap.

## C. Recovery key-ID and registry separation gate

Require exactly:

```text
RECOVERY_SIGNING_KEY_ID=AITradingBot/Authority/P3R1Recovery/v1
RECOVERY_REGISTRY=PRODUCTION_PINNED_P3_R1_RECOVERY_KEYS
```

Prove production recovery validation does not import, alias, wrap as authority,
or default to `PRODUCTION_PINNED_BOOTSTRAP_KEYS`. Prove bootstrap validation
cannot consult the recovery registry. Prefer nominally distinct immutable key
and registry types so cross-passing fails before cryptographic verification.

The production recovery entry point accepts no caller registry. If a low-level
test seam supports registry injection, it must be explicitly test-only and
unable to mint production-provenance recovery permits.

Required cases:

```text
exact recovery key ID + pinned recovery key        -> eligible for verification
Bootstrap/v1 as recovery signing_key_id             -> reject
unknown/wrong/mutated recovery key ID                -> reject
bootstrap registry supplied to recovery verifier     -> reject/no authority
recovery registry supplied to bootstrap verifier     -> reject/no authority
caller-created recovery registry                     -> no production authority
```

## D. Source contains public recovery key only

After the accepted ceremony and in the later source checkpoint, inspect the
exact diff and packaged source. Require only one 65-byte uncompressed SEC1
recovery public point and its exact key ID in the recovery-only source registry.

Reject any private scalar, private blob, PFX, PEM, PKCS#8, encrypted private
material, key-generation seed, signing fixture derived from the production key,
container-opening production test, or secret-bearing release evidence. Scan
source, tests, fixtures, wheel contents, and installed package. Test signatures
must use clearly test-only keys and registries.

Paths, provider/container names, environment variables, registry values, and
caller-supplied public-key digests must not be treated as public-key identity.
Cryptographic operations use the source-pinned SEC1 bytes.

## E. Exact recovery canonical schema gate

Retain the Architecture-96 exact field set, strict UTF-8 canonical JSON, and
frozen incident/release values. Change only:

```text
signing_key_id=AITradingBot/Authority/P3R1Recovery/v1
```

Reject duplicate, unknown, optional, or missing fields; alternate serialization;
non-canonical UUID/SID/digest/path/key-ID text; old unsigned authorization
bytes; and optional policy/retry/replacement/cleanup/account-selection fields.

Keep the exact Architecture-96 domain and length framing unchanged. Require the
detached signature to be exactly 64-byte IEEE P1363 `r || s` using ECDSA P-256
and SHA-256. Reject DER, RSA, other curves, hashes, encodings, and domains.

## F. Old bootstrap key cannot authorize recovery

Using test-only representations of the historical public key and controlled
vectors, prove:

- a signature valid for exact bootstrap bytes cannot validate recovery-domain
  bytes;
- a signature made by the Bootstrap/v1 private test counterpart over the exact
  recovery preimage is still rejected because the recovery key ID/registry is
  distinct;
- substituting Bootstrap/v1 in canonical authorization bytes is rejected before
  a production permit can be issued; and
- no parser or verification fallback tries bootstrap trust after recovery trust
  fails.

The test must not discover or use the production bootstrap private signer.

## G. Recovery key cannot authorize bootstrap

With a test-only recovery key counterpart, prove:

- a valid recovery-domain signature is rejected by bootstrap verification;
- a recovery-key signature over bootstrap bytes is rejected because the key ID
  is absent from the bootstrap registry;
- placing the recovery key ID in bootstrap bytes is rejected/not pinned; and
- bootstrap verification never falls back to the recovery registry.

## H. Wrong or mutated key/signature rejection

Require rejection for a wrong recovery public point, point mutation, wrong
curve/length/prefix, duplicate registry ID, unknown key ID, signature length
other than 64, all-zero/out-of-range/mutated signature components, canonical
authorization byte mutation, domain mutation, and length-framing mutation.

Successful evidence reports only sanitized key ID, authorization digest, and
signature length. It must not expose provider handles, sensitive native
metadata, or private material.

## I. One-time key-creation ceremony validation

Before the ceremony, independently review an exact elevated Windows procedure.
It must freeze:

```text
PROVIDER=Microsoft Software Key Storage Provider
ALGORITHM=ECDSA_P256
SCOPE=local-machine
CREATE_FLAG=NCRYPT_MACHINE_KEY_FLAG
PERSISTED_CONTAINER=AITradingBot-P3R1-Recovery-v1
KEY_ID=AITradingBot/Authority/P3R1Recovery/v1
```

Dry/source review must prove the procedure:

1. validates exact machine and exact elevated Administrator SID first;
2. has no caller-selected provider, algorithm, scope, name, key ID, or flags;
3. requires the fixed name absent and uses create-new/no-overwrite semantics;
4. never deletes, repairs, renames, replaces, or chooses another existing key;
5. sets signing-only use and no private export/archiving before finalization;
6. finalizes once;
7. exports only public material;
8. freezes exact 65-byte uncompressed SEC1 bytes and SHA-256;
9. closes and independently reopens the exact key;
10. reproves public identity and all required security metadata; and
11. stops without signing.

No application source/test command is part of this gate. Running the ceremony
requires separate explicit approval after procedure review.

## J. Provider, key-name, public-identity, and security readback gate

The independently reopened key must match the frozen provider, container,
machine scope, algorithm/group/curve, 256-bit key length, finalized state,
signing usage, no-private-export/no-archiving policy, public SEC1 bytes/length/
SHA-256, unique persisted identity where applicable, owner, protected/inherited
state, and exact canonical security descriptor/ACE set.

Trading must have no private-key use, export, delete, owner, DACL, or control
authority. Unexpected, unreadable, ambiguous, or default-assumed metadata
fails. Container-name equality alone is insufficient.

The exact KSP security descriptor, property APIs, inheritance semantics, owner,
ACE masks, and byte/semantic comparison are a blocker until separately
reviewed. Do not run the ceremony with default or best-effort permissions.

## K. Private export forbidden gate

Source review and post-finalization readback must prove no private export or
archiving policy. The procedure must contain no private export call and no
private-material serialization path.

In a separately reviewed disposable test-key harness only, exercise the exact
policy semantics needed to prove private scalar/blob/PFX/PEM/PKCS#8/opaque
private export and archiving are denied while public export succeeds. The
disposable harness must use a distinct test provider name/container and must
never open the production container. A failure blocks the production ceremony;
it does not trigger relaxed policy.

## L. Non-circular release binding gate

Require this exact order:

```text
accepted Architecture-97 docs
-> accepted key ceremony procedure and security contract
-> one-time recovery-key creation/public freeze/reopen proof
-> source pins frozen recovery public key
-> exact source review + focused tests + final certification
-> isolated exact Git export
-> exact offline wheel build
-> wheel/package/RECORD reconciliation
-> deterministic installed-RECORD dual-clone derivation
-> collect exact elevated Administrator SID
-> construct new canonical authorization with P3R1Recovery/v1
-> freeze authorization unsigned
-> reopen exact key and reprove public identity/security
-> separately authorize exact signing preimage
-> sign once
-> independently verify with corrected source
-> freeze signature evidence
```

Reject source constants predicting their own future wheel/RECORD identity,
caller-provided release digests as authority, skipped steps, old-design
artifacts, or authorization construction before release facts are frozen.

## M. Installer `-I` and pip `--isolated` gate

Freeze the observed unacceptable resolution:

```text
F:\AITradingBot\runtime\python.exe -m pip
-> C:\Users\John\AppData\Roaming\Python\Python314\site-packages\pip
-> FAIL
```

The separately reviewed privileged deployment command must use:

```text
F:\AITradingBot\runtime\python.exe -I -m pip --isolated install <exact-wheel>
```

and all of:

```text
--no-index
--no-deps
--no-cache-dir
--disable-pip-version-check
--no-input
--force-reinstall
```

Before install, clear/reject ambient Python/pip configuration, prove pip imports
from the sealed runtime and is version 25.3, and reprove the exact offline wheel
identity. After install, reconcile installed `RECORD` and every hashed payload.
Omitting either Python `-I` or pip `--isolated`, accepting the user-site pip, or
allowing index/network/dependency resolution fails the gate.

## N. New wheel and installed-RECORD freeze gate

Retain and never reuse:

```text
F:\AI\p3-r1-recovery-release-v1                 FAILED_RETAINED
F:\AI\p3-r1-recovery-release-v2                 FAILED_RETAINED
F:\AI\p3-r1-recovery-release-v3                 ACCEPTED_OLD_SIGNING_DESIGN
F:\AI\p3-r1-installed-record-derivation-v1      ACCEPTED_OLD_SIGNING_DESIGN
```

The corrected chain uses new preflight-absent versioned roots and create-new/
no-overwrite publication. Freeze exact source commit/tree, Git export inventory,
wheel bytes/length/SHA-256, package-to-export equality, wheel `RECORD`, and all
payload hashes.

Install the exact wheel into two clean, separate, non-production offline clones
with the frozen isolated installer semantics. Require byte-identical installed
`RECORD` bytes and identical reconciled payloads. Any nondeterminism blocks.
Freeze the resulting expected installed-RECORD digest/length only after the
dual-clone proof.

## O. New unsigned-authorization freeze gate

Retain unchanged:

```text
F:\AI\p3-r1-recovery-authorization-freeze-v1
STATUS=ACCEPTED_UNSIGNED_OLD_SIGNING_DESIGN
```

Never sign, edit, rename, reuse, or promote that authorization with the new
key. Construct a new canonical authorization from the corrected accepted
source/release/RECORD/operator facts and exact recovery key ID. Publish it
unsigned into a new, versioned, preflight-absent evidence root with exact bytes,
length, and SHA-256. Reparse and require byte-for-byte canonical round trip
before any signing-key access.

## P. Independent post-signature verification gate

Immediately before signing, reopen the exact production recovery key and
reprove public SEC1 identity and security. Require separate authorization for
the exact frozen domain-preimage digest and length. Sign once.

Treat any return after the signing call begins as an attempted security effect.
Retain all output/evidence, do not retry, and do not select among signatures.

Verification must occur in a separate process/context through the exact
corrected, certified source-pinned recovery verifier. Require exact canonical
authorization digest/length, exact recovery key ID, 64-byte P1363 signature,
and valid recovery-domain verification. Re-run the cross-purpose negative
matrix before freezing signature evidence into a new versioned root.

## Q. Architecture-95 recovery semantics regression gate

All Architecture-95 validation remains mandatory:

- authorization and production-provenance permit before Paper staging access;
- frozen incident/admission facts and exact C1/runtime/database identity;
- descendants retained during proof and successfully closed before rename;
- retained parent/root revalidation and final absence immediately before rename;
- exactly one absolute no-replace retained-root `FileRenameInfo` call;
- mutation marker immediately before that call;
- retained-root final-path proof and namespace proof;
- reopened descendants with exact pre/post native identity equality;
- complete final owner/DACL/inventory/bytes/canonical genesis/anchor proof;
- authority database before/after byte equality;
- conservative pre-rename failure and at/after-rename ambiguity treatment; and
- no cleanup, reverse rename, replacement, repair, retry, publisher rerun,
  alternate account, provider, credential, broker, paper transition, or P4
  effect.

The only corrected Architecture-96 behavior is recovery signing trust. The
strict authorization, sealed-runtime reconciliation, private process-local
permit, and one-invocation boundary remain unchanged.

## R. Production no-effect and source/test gates

During docs/source/test work require:

```text
PRODUCTION_KEY_CREATED=False
PRODUCTION_KEY_OPENED=False
PRODUCTION_SIGNATURE_CREATED=False
PRODUCTION_PRIVATE_KEY_USED=False
PRODUCTION_PAPER_PATH_ACCESSED=False
PRODUCTION_PAPER_PATH_MUTATED=False
PRODUCTION_AUTHORITY_MUTATED=False
SEALED_RUNTIME_MUTATED=False
CREDENTIAL_MANAGER_READ=False
PROVIDER_CALL_PERFORMED=False
PROVIDER_CALL_7_AUTHORIZED=False
BROKER_OPERATION_PERFORMED=False
P4_PRODUCTION_EXECUTION=False
PRODUCTION_LIVE=NO-GO
```

Focused tests use test-only keys and registries, fake/native-disposable roots,
and the mandated external pytest basetemp. No test opens the fixed production
container or either production Paper path. Final source certification, release
build, ceremony, signing, deployment, staging revalidation, and recovery are
separate checkpoints and trust contexts.

## S. Separate explicit production-recovery authorization gate

Even a valid signed artifact and successful deployment do not authorize the
rename. Require the remaining sequence:

```text
sealed-runtime deployment through reviewed isolated installer
-> installed RECORD/payload reconciliation
-> read-only retained-staging revalidation
-> separate explicit one-time operator recovery approval
-> exact elevated Administrator recovery
-> close Administrator shell
-> exact non-admin Trading acceptance
```

The approval must identify the exact authorization/signature/release evidence
and the still-valid Architecture-95 incident state. It grants one recovery
invocation only. A prior attempt, state drift, or ambiguous evidence requires a
new architecture/operator review; the same signature is not generic retry
authority.

Until that explicit gate:

```text
PRODUCTION_RECOVERY_RENAME=NOT_AUTHORIZED
PUBLISHER_RERUN=FORBIDDEN
STAGING_DELETE_OR_REPAIR=FORBIDDEN
PROVIDER_CALL_7=NOT_AUTHORIZED
P4_PRODUCTION_EXECUTION=BLOCKED
PRODUCTION_LIVE=NO-GO
```

## Failure and retry acceptance

For key creation, any persisted-key creation/finalization followed by failure
retains evidence and stops. Never automatically delete, overwrite, regenerate,
rename, or choose a second key.

For signing, any attempted call retains its signature/evidence and stops on
failure or uncertainty. Never automatically sign again or choose among
multiple signatures.

For recovery, Architecture-95 one-way and ambiguity semantics remain exact. No
automatic retry exists at any security-effect boundary.

## Review readiness

This validation contract covers gates A through S requested for Architecture
97. It is ready for ChatGPT/Sol review together with the architecture document.
The known blocker is the exact Windows KSP machine-key security/ACL contract;
the ceremony must not run until that separate contract and exact procedure are
reviewed and accepted.

