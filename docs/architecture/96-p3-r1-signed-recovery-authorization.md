# Architecture 96: P3-R1 signed recovery authorization

## Purpose

This checkpoint closes the authority-binding gap discovered during exact-diff
review of P3-R1 implementation commit
`2b82222fbaee857e02519a0ea3627679d309276d`.

Architecture 95 correctly requires recovery to run only under the exact elevated
Administrator operator and the exact accepted post-build release/deployment
identity. The first implementation represented those facts as a caller-created
`P3R1RecoveryDeploymentExpectation`. That shape is rejected: caller-selected
SIDs, paths, filenames, digests, lengths, manifests, reconstructed objects, or
environment values are evidence inputs only and cannot create recovery
authority.

The retained-root rename ordering, descendant identity continuity, crash-state
semantics, ordinary-publisher separation, and frozen incident state from
Architecture 95 remain unchanged. This checkpoint only defines the missing
non-circular authorization mechanism and the corresponding implementation
correction.

## Rejected authority patterns

P3-R1 must not authorize recovery from any of the following:

- a caller-created dataclass containing the current operator SID;
- a caller-selected installed `RECORD` digest or byte length;
- a source constant that attempts to predict the digest of the wheel built from
  that same source;
- a command-line argument, environment variable, path, filename, PID, process
  name, report field, or reconstructed evidence object;
- an unsigned release/deployment manifest;
- a raw wheel hash or installed-package hash without an independently trusted
  binding;
- successful C1 validation by itself.

These facts may be checked as evidence, but none is an authority source.

## Trust decision

P3-R1 uses a detached, cryptographically signed, domain-separated recovery
authorization created only after the exact release candidate has been built and
reviewed.

The recovery verifier reuses the already source-pinned production P-256 public
trust material from the C1 trust boundary. The private signing material remains
external and non-exportable. Reuse of the key material is permitted only through
a dedicated recovery-authorization verifier with a distinct signed domain. The
recovery artifact must never be passed to the bootstrap parser or interpreted as
a bootstrap signature.

The signed recovery domain is:

```text
ai-trading-bot/p3-r1-recovery-authorization/v1
```

The signing preimage must be an unambiguous domain-separated construction over
the exact canonical authorization bytes. The implementation must define one
exact byte representation and test cross-purpose rejection. A bootstrap
signature must not validate as a recovery authorization, and a recovery
signature must not validate as a bootstrap.

If the existing external signer cannot safely sign the dedicated recovery
domain, implementation must stop. Do not invent a new trust source, weaken the
signature requirement, or fall back to caller assertions.

## Canonical authorization artifact

The authorization is a strict, versioned, canonical, secret-free document. Its
field set is exact. At minimum it binds:

```text
schema/purpose = p3-r1-recovery-authorization/v1
machine_authority_id = 223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1
approved_trading_sid = S-1-5-21-1397534616-3988210162-180023805-1009
administrator_operator_sid = <exact reviewed elevated operator SID>
paper_account_id = d1510a4b-6ebf-58ef-92a4-e743ca91151e
genesis_checkpoint_id = 7b7b83ba-69e2-5ed8-a033-b4306cd1ffc7
bootstrap_sha256 = 53b8b72ab18b1c477c5eab50857e4dc2d47efc6e74030e380ed6a53387922ae4
authority_database_sha256 = 6a8fb988d1cb223fbb66b09e8dab1e0de4b6aafd148dfdf01df08029203f4b76
authority_database_bytes = 331776
source_commit = <accepted final P3-R1 source commit>
source_tree = <accepted final P3-R1 source tree>
wheel_sha256 = <accepted post-build wheel digest>
wheel_bytes = <accepted post-build wheel length>
installed_record_sha256 = <accepted installed RECORD digest>
installed_record_bytes = <accepted installed RECORD length>
staging_root = F:\AITradingBot\.Paper.provisioning-v1
final_root = F:\AITradingBot\Paper
```

The final schema may include explicit signature/key identifiers and a reviewed
release-certificate identifier when needed, but it must not include optional
caller policy, alternate roots, replacement behavior, cleanup behavior, retry
behavior, account selection, or generic recovery flags.

Canonicalization must reject duplicate keys, unknown fields, missing fields,
non-canonical UUID/SID/digest text, alternate path spellings, and non-canonical
serialization.

## Non-circular build and authorization sequence

The release identity is necessarily learned after source freeze. The authority
chain is therefore:

```text
accepted corrected source commit/tree
-> isolated exact source export
-> offline exact wheel build
-> wheel/package/RECORD reconciliation
-> freeze wheel SHA-256/length and expected installed RECORD identity
-> obtain exact elevated Administrator operator SID
-> construct canonical P3-R1 authorization bytes
-> sign the dedicated recovery domain using the external production P-256 signer
-> independently verify the signature against the source-pinned public key
-> freeze authorization bytes/signature/hash/length as release evidence
-> deploy exactly the authorized wheel through the separately reviewed sealed
   runtime deployment gate
-> prove installed RECORD and every hashed installed payload
-> perform a separate read-only retained-staging revalidation
-> require explicit operator approval for the one P3-R1 recovery invocation
-> run recovery using the signed authorization
```

The wheel does not contain a prediction of its own future digest. The signed
post-build authorization binds the accepted source/release facts after they are
known.

## Runtime authorization verification

Before any Paper staging object is opened, the recovery entry point must:

1. require Windows and an elevated Administrator token;
2. parse exact canonical authorization bytes;
3. verify the detached signature against the dedicated recovery domain and the
   source-pinned production public key;
4. require the signed Administrator SID to equal the actual current-token SID;
5. require execution from the exact sealed production runtime;
6. require the signed machine authority, Trading SID, bootstrap digest, paper
   account ID, genesis ID, database identity, and fixed paths to equal the
   frozen P3-R1 incident values;
7. require installed C1 to be complete and reconciled;
8. require the actual installed `RECORD` digest/length to equal the signed
   values;
9. parse the `RECORD` strictly and reconcile every hashed installed package
   payload that can affect recovery;
10. require loaded `trading_bot` module provenance to be inside the authorized
    sealed package and covered by the reconciled installed release; and
11. require runtime quiescence before entering the retained-staging proof.

An unsigned or incorrectly signed artifact, an alternate operator, another
wheel/RECORD, source/import drift, or any incident-field mismatch blocks before
Paper staging access.

## Process-local recovery permit

Successful authorization verification issues a private process-local recovery
permit. The permit is not serialized authority and must follow the same general
provenance discipline used elsewhere in the project:

- private issuer token;
- exact concrete type;
- immutable;
- non-pickleable/non-serializable;
- no public reconstruction path from its fields;
- scoped only to this frozen P3-R1 incident and this process invocation.

The native recovery mutation boundary requires the permit directly. Raw
authorization bytes, signature bytes, parsed fields, hashes, paths, or evidence
objects must not substitute for the permit.

The permit does not authorize provider calls, Credential Manager access, broker
operations, P4, scheduling, retries, cleanup, replacement, or live trading.

## One-invocation and retry semantics

The signed authorization is release/operator authority for the reviewed manual
recovery invocation; it is not a generic retry token.

The implementation performs no automatic retry and exposes no loop or resume
path. If an invocation fails before the rename boundary, the staging tree remains
retained evidence and that failed operator attempt is retained. This checkpoint
does not authorize a second invocation merely because the same signed bytes
still verify. Any later retry decision requires a new explicit architecture and
operator review of the failed evidence.

After a successful rename, the namespace itself no longer satisfies the required
`FINAL absent / STAGING present` admission state, so the authorization cannot be
used to perform another publication.

At or after the native rename call, Architecture-95 ambiguity semantics remain
unchanged: no cleanup, reverse rename, replacement, retry, or inferred success.

## P3-R1 integration correction

Implementation commit `2b82222fbaee857e02519a0ea3627679d309276d` is retained as
historical implementation evidence but is not an accepted source candidate.

The correction must:

- remove caller-authoritative `P3R1RecoveryDeploymentExpectation` semantics;
- add strict canonical signed authorization parsing and verification;
- issue and require the process-local recovery permit;
- preserve the already-reviewed descendant-close-before-rename ordering;
- preserve exact root and descendant native-identity continuity checks;
- preserve conservative crash/ambiguity classifications;
- keep the ordinary publisher unable to invoke recovery;
- keep all existing frozen incident constants exact; and
- make no production mutation during implementation or testing.

## Native disposable test scratch

New native disposable tests must not intentionally use a worktree
`.pytest_cache` as their scratch authority or filesystem root.

Use pytest `tmp_path`/`tmp_path_factory` or another explicitly supplied
disposable root. Local Windows invocations use a fresh external
`--basetemp` under `F:\AI\temp\pytest\...` and normally disable the pytest cache
provider when cache behavior is irrelevant.

No native regression may touch:

```text
F:\AITradingBot\Paper
F:\AITradingBot\.Paper.provisioning-v1
```

## Required tests

Source tests must prove at minimum:

- unsigned authorization rejected;
- signature tampering rejected;
- canonical-byte tampering rejected;
- bootstrap/recovery cross-purpose signatures rejected;
- wrong key identifier rejected;
- alternate Administrator SID rejected even when elevated;
- caller-created field objects cannot mint the permit;
- wrong machine/Trading/bootstrap/database/account/genesis/path values rejected;
- wrong wheel/installed RECORD identity rejected;
- unlisted, unhashed, path-escaping, duplicate, or modified installed payloads
  rejected;
- import provenance outside the authorized installed package rejected;
- permit serialization/reconstruction rejected;
- recovery native mutation cannot be entered without the real permit;
- no Paper object is opened before authorization verification succeeds;
- all Architecture-95 handle-ordering, identity, crash, and no-effect regressions
  continue to pass;
- opt-in native rename scratch remains disposable and outside production paths.

## Production gates

A source/test PASS still does not authorize production recovery.

The required chain becomes:

```text
corrected source accepted
-> broad source certification
-> exact release wheel freeze
-> canonical signed P3-R1 authorization freeze
-> separately reviewed sealed-runtime deployment
-> installed release/RECORD reconciliation
-> read-only retained-staging revalidation
-> explicit one-time operator approval
-> Administrator P3-R1 recovery
-> close Administrator shell
-> non-admin Trading P3 acceptance
```

## Non-authorizations

```text
PRODUCTION_RECOVERY_RENAME=NOT_AUTHORIZED
PUBLISHER_RERUN=FORBIDDEN
STAGING_DELETE_OR_REPAIR=FORBIDDEN
UNSIGNED_RECOVERY_AUTHORIZATION=FORBIDDEN
CALLER_ASSERTED_RECOVERY_AUTHORITY=FORBIDDEN
P3_TRADING_ACCEPTANCE=BLOCKED_PENDING_RECOVERY
P4_PRODUCTION_EXECUTION=BLOCKED
PROVIDER_CALL_7=NOT_AUTHORIZED
PRODUCTION_LIVE=NO-GO
```

## Next milestone

Use Codex Sol High for one bounded correction pass on top of retained commit
`2b82222fbaee857e02519a0ea3627679d309276d`. The correction must implement this
signed-authorization boundary, fix the disposable native scratch location, run
focused tests only with the mandatory isolated Windows pytest rules, and stop
without commit/push for ChatGPT exact-diff review.
