# Architecture 123 — D10 Runtime-Verifiable Deployment Identity Attestation

Status: design frozen for the Architecture-122 prerequisite. This architecture does not authorize signing, provisioning, scheduler mutation, or trading effects.

## Problem

Architecture 122 requires the zero-argument unattended D10 runtime to reject a source upgrade during the bounded one-week soak.

The certification runner can prove a checkout's Git HEAD and tree, but the Trading runtime must not trust `.git`, caller arguments, Task Scheduler history, environment variables, or process memory as source-identity authority. The activation-lease implementation therefore stopped correctly: a lease containing HEAD/TREE strings would only assert them.

## Resolution

D10 uses a separately signed deployment-identity attestation.

The runtime does not reconstruct a Git commit from the filesystem. Instead it verifies an administrator-installed detached-signed canonical attestation binding:

1. the externally certified Git source HEAD and tree;
2. one canonical executable-file-manifest digest;
3. the exact fixed D10 source root and launcher;
4. the exact D10 scheduler-contract schema;
5. the approved Trading SID;
6. the exact production Python executable and reviewed version;
7. a deterministic deployment identity.

The runtime then independently verifies that deployed executable files match the signed executable manifest. HEAD/TREE are externally attested certification facts; the runtime proves that the bytes it is about to execute are the bytes bound to that attestation. No `.git` read is required.

## Trust boundary

This protects against accidental/stale/mismatched deployment, ordinary source drift, manifest substitution, and unsigned rollback.

It does not claim to defend against malicious Administrator/SYSTEM/physical control or malicious code already controlling the trusted Trading token. That matches Architecture 77's existing trusted-Trading-token boundary.

This is not a general executable-signing platform and grants no broker/live authority.

## Fixed D10 trust root

Use a new dedicated root rather than widening Architecture 77's exact Authority object set:

```text
F:\AITradingBot\D10\
  deployment.attestation.json
  deployment.attestation.sig
  executable-manifest.json
```

The D10 root and three final files are Administrator-owned, protected-DACL, local NTFS, non-reparse objects. Trading receives only reviewed read/traverse rights and no create/delete/rename/WRITE_DAC/WRITE_OWNER rights.

Reserved same-directory temporary names are source-owned for the later administrator publication checkpoint. Unexpected final or temporary state fails closed. Runtime never repairs it.

## Signing trust

Use a D10-specific exact signing-key ID and schema/domain. The production public key may reuse the already approved P-256 key material only under that distinct protocol identity; private signing material remains external and non-exportable.

Repository/runtime code contains verification/public-key material only. Production signing is a separately approved administrator/operator effect.

Detached signatures remain P-256 / SHA-256 / 64-byte IEEE P1363 unless a later architecture changes the contract.

## Canonical executable manifest

`executable-manifest.json` is strict canonical UTF-8 JSON with sorted keys and no insignificant whitespace.

It contains a sorted exact tuple of entries with only:

```text
relative_path
byte_length
sha256
```

The governed set contains every regular tracked file under `src/trading_bot` in the certified executable tree, including runtime resources, plus the exact D10 launcher script used by Task Scheduler.

Paths are canonical repository-relative forward-slash paths. Absolute, empty, parent-traversal, alternate-separator, ADS/device/UNC, duplicate, or case-colliding paths are invalid. Entries sort lexicographically by relative path.

The runtime compares the complete governed deployment inventory to the manifest. Missing or extra governed executable files, symlink/reparse state, byte-length mismatch, or SHA-256 mismatch block D10.

Transient Python cache material is not authority. Source implementation must define and test a deterministic policy that prevents an unverified alternate bytecode artifact from becoming runtime authority.

## Canonical deployment attestation

The signed attestation contains exactly:

```text
schema = personal-desktop-d10-deployment-attestation/v1
signing_key_id
certified_source_head
certified_source_tree
source_root
launcher
scheduler_contract_schema
approved_trading_sid
production_python
production_python_version
executable_manifest_sha256
executable_file_count
deployment_id
```

HEAD/tree are 40-character lowercase Git object IDs.

The source root is fixed:

```text
F:\AI\worktrees\ai-trading-bot-personal-desktop
```

The launcher is the exact source-owned D10 launcher beneath that root.

The manifest digest is SHA-256 over exact canonical manifest bytes.

`deployment_id` is UUID5 over versioned canonical material containing all authority-bearing attestation facts except the deployment ID and detached signature. No wall clock, UUID4, Python hash, filesystem order, locale, or object identity enters it.

## Certification-time builder

A source-only builder may run in the clean detached certification checkout. Git is permitted only at this certification/build boundary to:

- verify exact expected HEAD/tree and clean state;
- enumerate governed tracked files;
- read exact file bytes;
- construct canonical executable-manifest bytes;
- construct canonical unsigned deployment-attestation bytes.

The builder emits bytes/digests only. It does not sign, provision, mutate Task Scheduler, or perform trading effects.

The detached signature is produced later by the separately approved external signing process.

Docs-only commits after executable certification do not redefine the attested executable deployment. The production D10 checkout is pinned to the exact certified executable source identity.

## Trading runtime verification

The production verifier is zero-semantic-argument and source-owned.

Before any D10 effect gate may open, it:

1. proves the exact Trading token and current C1 as required by existing authority;
2. opens only the fixed D10 root/files through reviewed native no-follow reads;
3. proves exact final path, object kind, local volume, owner/DACL, no reparse, stable identity/content, and no reserved temporary state;
4. parses exact canonical manifest/attestation bytes;
5. verifies the detached D10 P-256 signature;
6. requires signed SID/Python/scheduler/source-root/launcher facts to equal source-owned values;
7. verifies every governed deployed file against the manifest and rechecks inventory for drift;
8. returns sanitized same-process deployment evidence.

No public result carries raw trust bytes, caller-selected paths, handles, keys, capabilities, or reusable authority. Reconstructed public results cannot satisfy later provenance.

## Relationship to the activation lease

The D10 activation lease is built only after deployment identity is verified.

The lease binds exact `deployment_id` and signed-attestation digest plus activation/end time.

Every scheduled wake independently requires:

```text
verified deployment identity
AND
verified ACTIVE activation lease
```

before any market-data, settlement, or decision-publication gate can open.

Expired lease, changed deployment bytes, changed attestation, changed executable inventory, or source checkout update blocks all new D10 effects. Task Scheduler's end boundary remains defense in depth.

## Upgrade policy

No in-place executable source upgrade is allowed during the active week.

Any executable source change requires closing the current soak authority, new source certification, a new executable manifest, a new signed deployment attestation, and a new bounded activation authorization. The old lease cannot authorize a new deployment.

## Acceptance criteria

Source acceptance requires tests proving canonical JSON/field sets, deterministic deployment ID, HEAD/tree shape validation, canonical file ordering independent of filesystem enumeration, unsafe/duplicate/case-colliding paths blocked, missing/extra/file-byte drift blocked, manifest tamper blocked, bad signature/key/schema blocked, wrong SID/Python/root/launcher/scheduler schema blocked, native path/security/reparse/identity/content drift blocked, same-process provenance cannot be reconstructed, no `.git` read in the production verifier, and no scheduler/provider/publication/settlement/recovery/broker/live effect.

Architecture 123 source completion authorizes no signing, provisioning, scheduler mutation, activation lease, or D10 trading effect.


## Architecture 124 pre-source prerequisite

A3 implementation exposed a circular trust boundary: the old scheduler target
would execute source-tree Python before an in-process verifier could prove that
source.

Architecture 124 is therefore a mandatory predecessor to A3/A4 deployment
identity enforcement.

The signed deployment model is revised as follows:

- recurring D10 source is deployed to sealed
  `F:\AITradingBot\D10\source`, not executed from the mutable Git worktree;
- Task Scheduler invokes fixed protected
  `F:\AITradingBot\D10\launch-guard.py`;
- the deployment attestation additionally binds exact launch-guard byte length
  and SHA-256;
- the pre-source guard verifies signed deployment/source identity before any
  `trading_bot` module or D10 source launcher is imported/executed;
- Architecture-123 A4 remains an in-source defense-in-depth re-verifier, not the
  first trust boundary.

The previously accepted A1/A2 implementation must receive a narrow source-model
revision for these guard/source-root fields before it is used to build final D10
deployment material. Its existing canonicalization, HEAD-tree/blob proof, and
Git-environment hardening remain valid.
