# Architecture 103: Personal-desktop paper-account authority v2

## Status and scope

**FROZEN DESIGN CHECKPOINT -- DOCS ONLY -- NO PRODUCTION EFFECT AUTHORIZATION**

Architecture 103 defines the PD1 operational simulated-paper account authority for the Architecture-102 personal-desktop threat model.

It replaces the *product-roadmap requirement* to finish the high-assurance P3-R1 recovery/KSP/account-ceremony line before simulated paper operation. It does not invalidate Architectures 95-101; those remain preserved on the high-assurance branch and become blocking again if the deployment threat model changes as described by Architecture 102.

Architecture 103 reuses the accepted deterministic paper-account primitives instead of inventing a new paper engine:

- Architecture 61 GENESIS checkpoint;
- Architectures 62/63 successor checkpoint and edge validation;
- Architecture 66 full-lineage verification;
- Architecture 67 restart-safe paper-operation transition and receipt semantics;
- Architecture 94 P1 deterministic strategy/history plan;
- Architecture 94 P2 read-only selected-C3 snapshot authority.

This architecture remains **simulated paper only**. It authorizes no broker request, provider call #7, scheduling, live trading, credential change, account/group/LSA/KSP mutation, or production filesystem effect.

## Security objective under Architecture 102

The purpose of this boundary is practical protection of a single-owner desktop bot, not hostile-administrator resistance.

Trusted:

- the machine owner and deliberately elevated local administrators;
- Windows kernel/boot/SYSTEM authority;
- physical machine control.

Still protected against:

- accidental use of a caller-selected or redirected paper root;
- unrelated non-admin processes rewriting immutable account identity;
- accidental execution as the wrong Windows principal;
- duplicate or conflicting paper transitions;
- stale, malformed, noncanonical, or internally inconsistent lineage;
- automatic retry after ambiguous filesystem publication;
- accidental interaction with the retained failed v1 publication;
- strategy/GUI/AI/scheduler bypass of deterministic risk in later composition.

The design does not claim to withstand arbitrary malicious code already executing as Administrator/SYSTEM or arbitrary malicious code intentionally granted the `Trading` account's full runtime authority.

## Fixed v2 production paths

The new authority never reuses the failed v1 final or staging names.

```text
final authority root:
  F:\AITradingBot\Paper-v2

provisioning staging root:
  F:\AITradingBot\.Paper-v2.provisioning

Architecture-67 operation root:
  F:\AITradingBot\Paper-v2\runtime

operation receipt parent:
  F:\AITradingBot\Paper-v2\runtime\paper-operations
```

The retained v1 state remains separate and untouchable:

```text
F:\AITradingBot\Paper                       must remain absent
F:\AITradingBot\.Paper.provisioning-v1     retained historical staging
```

No v2 code may interpret either v1 path as a fallback, recovery source, migration source, or alternate account.

## Fixed v2 layout

Initial publication produces exactly:

```text
F:\AITradingBot\Paper-v2\
  personal-desktop-paper-account-authority.json
  paper-account-genesis-<genesis-checkpoint-id>\
    paper-account-checkpoint-<genesis-checkpoint-id>.json
  runtime\
    paper-operations\
```

Later Architecture-67 state is confined to `runtime`:

```text
runtime\
  paper-account-transition-<application-id>\
    ... existing Architecture-67 transition artifacts ...
  paper-operations\
    paper-operation-<operation-id>\
      ... existing Architecture-67 receipt artifact ...
```

The immutable authority anchor and GENESIS artifact are never written by the steady-state `Trading` process.

## Canonical authority anchor

Schema:

```text
personal-desktop-paper-account-authority/v1
```

Closed fields:

```text
schema
layout
paper_account_id
machine_authority_id
approved_trading_sid
genesis_checkpoint_id
genesis_sha256
genesis_byte_length
```

`layout` is exactly:

```text
personal-desktop-paper-layout/v1
```

The anchor is strict canonical UTF-8 JSON using the repository's established canonical conventions: sorted keys, compact separators, ASCII escaping, canonical lowercase UUID/SHA-256 text, no duplicate/missing/unknown fields, no floats/non-finite constants, and exactly one final newline.

The anchor is identity evidence, not a mutable pointer. Paths are fixed by source and are not stored as caller-selected authority.

## Deterministic paper-account identity

Dedicated UUID5 namespace:

```text
022bbd87-6bea-5fd0-a323-5fa355616643
```

The framed ordered material is:

```text
personal-desktop-paper-account-id-v1
<machine_authority_id>
<approved_trading_sid>
<genesis_checkpoint_id>
<genesis_sha256>
<genesis_byte_length as canonical base-10 text>
```

The resulting UUID is `paper_account_id`.

Excluded from identity:

- filesystem paths;
- provisioning time / wall clock;
- random UUIDs;
- current process ID;
- C3 provider credential version;
- C3 selection ID or artifact path;
- environment variables;
- GUI/configuration location;
- staging/final file identities.

The machine-authority and approved-Trading bindings are retained because they are cheap, already-reviewed practical deployment identities. No recovery-signing key or KSP key is required.

## Opening-state policy

PD1 v2 starts as a fresh simulated cash-only account using the existing Architecture-61 GENESIS model unchanged.

Production v2 opening state is fixed to:

- one explicit positive starting-cash Decimal approved before publication;
- no positions;
- cumulative realized P&L exactly zero;
- no open orders;
- empty application metadata.

There is **no code default** for starting cash.

For the first PD1 rollout, GENESIS `as_of` is the exact strictly verified `captured_at` timestamp of the already accepted selected C3 call-#6 snapshot. The P2 read boundary supplies this timestamp after exact selected-snapshot verification. This is chronology material only; it grants no provider effect or C3 mutation authority.

## Offline provisioning bundle

A pure/offline preparation API produces three exact byte strings:

1. canonical Architecture-61 GENESIS checkpoint bytes;
2. canonical v2 authority-anchor bytes;
3. canonical provisioning manifest bytes.

Provisioning manifest schema:

```text
personal-desktop-paper-account-provisioning/v1
```

Closed fields bind at minimum:

```text
schema
paper_account_id
machine_authority_id
approved_trading_sid
genesis_checkpoint_id
genesis_sha256
genesis_byte_length
anchor_sha256
anchor_byte_length
```

The manifest is deployment evidence only and is **not installed** under `Paper-v2`.

Preparation must independently verify the exact selected C3 snapshot through P2 before deriving `as_of`, create/verify the Architecture-61 GENESIS bytes, derive the account ID, build/parse the anchor, and finally build/parse the manifest. No network/provider call occurs.

Before any future production publication, ChatGPT/Sol freezes the exact manifest, anchor, GENESIS SHA-256 values and byte lengths plus the chosen starting cash.

### Trading preparation and administrator publication are separate planes

The Trading runtime plane uses genuine process-local `ValidatedProductionAuthority` plus P2 to prepare and contextually revalidate the bundle during readiness. C1 runtime acquisition still requires the exact non-elevated Trading process. That capability and the P2 permit are not serialized, transferred into an Administrator process, or recreated by publication.

The Administrator publication plane obtains complete installation-conformance evidence internally through `validate_installed_authority_complete()` and requires `require_initialized_supported_authority_evidence()`. The evidence must reconcile the installed signed bootstrap, machine-authority ID, approved Trading SID, and initialized/supported authority database. It is administrative evidence, not executable Trading authority.

The bridge is an immutable source-owned `PersonalDesktopPaperPublicationFreeze`, populated only by a later reviewed PD1E source diff. It binds canonical machine/account UUID text, the exact approved Trading SID, explicit positive Decimal starting cash, exact UTC GENESIS `as_of`, and SHA-256/byte length for each of GENESIS, anchor, and provisioning manifest. No environment variable, CLI argument, config file, caller-supplied freeze, or disposable test seam configures the production freeze.

Pure reconciliation verifies the existing PD1A manifest -> anchor -> Architecture-61 GENESIS chain, all three exact byte hashes/lengths, account identity, opening cash/chronology, and machine/SID agreement with complete Administrator C1 evidence. This does not recreate a P2 permit: the later reviewed source freeze binds the bytes whose P2 provenance was established in the Trading/readiness phase.

The certified production freeze is `PERSONAL_DESKTOP_PAPER_V2_PUBLICATION_FREEZE = None` (unconfigured). The production publisher accepts only the bundle, obtains Administrator evidence itself, and fails closed before mutation while the freeze is absent. No current production freeze values are selected by PD1C.

## Trusted-administrator provisioning boundary

Provisioning is a deliberately invoked one-time owner/admin operation. The high-assurance account ceremony is not required.

### Administrator gate

The publisher requires:

- Windows host;
- a primary process token;
- elevated administrator membership;
- no active thread impersonation token;
- complete administrator C1 installation-conformance evidence, including an initialized/supported production authority database;
- exact machine-authority ID matching the frozen bundle;
- exact C1-approved Trading SID matching the frozen bundle.

The publisher does not require or accept `ValidatedProductionAuthority` or a P2 permit. It requires the exact source-owned PD1E publication freeze and never issues Trading runtime authority from the Administrator process.

The publisher does not enumerate LSA account rights, create test users, change groups, prompt for or reset passwords, create KSP keys, or sign a recovery authorization.

### Fixed-parent gate

Before any create call, the publisher validates the fixed `F:\AITradingBot` parent chain using existing/reused Windows no-follow helpers where practical:

- local fixed filesystem;
- NTFS with persistent ACL support;
- canonical fixed path;
- no reparse point in the governed path;
- current parent security continues to prevent unrelated non-admin principals from replacing the new fixed child name.

Architecture 103 does not require a separate multi-gate parent-security ceremony or frozen volume serial. Failure of the direct safety assertions blocks publication.

### Occupancy gate

Before mutation:

```text
Paper-v2 final absent
.Paper-v2.provisioning staging absent
```

Any existing final or staging object is a STOP. The publisher never overwrites, merges, repairs, empties, or chooses a different path.

### Publication sequence

The publication algorithm is one-way and no-clobber:

1. complete all administrator/C1/bundle/parent/occupancy checks;
2. create the fixed staging root only;
3. create the exact GENESIS directory, GENESIS file, authority-anchor file, `runtime` directory, and `runtime\paper-operations` directory under staging;
4. write anchor/GENESIS with create-new semantics and flush exact bytes;
5. apply the final reviewed ACL policy to every staged object;
6. reread exact staged bytes and re-run strict anchor, GENESIS, manifest, identity, layout, path, object-type, and ACL validation;
7. flush handles/metadata as supported and close write handles;
8. rename the staging root to the fixed final root with same-parent no-clobber semantics;
9. reopen the final root by the fixed canonical path and repeat exact bytes/layout/type/ACL/account-identity verification;
10. only then report `PUBLISHED_AND_VERIFIED`.

The rename is the publication commit point.

Unlike the high-assurance v1 design, the staging tree does not need every final ACL at object creation. The reason is explicit: the staging namespace exists beneath a trusted administrator-controlled parent, is not authority until publication, and is validated after final ACL application but before rename. No untrusted principal may gain write authority to staging during preparation.

## Practical Windows ACL policy

Architecture 103 uses a small role-based policy rather than a ceremony-specific protected-evidence tree.

All final v2 authority objects use explicit protected DACLs; inherited accidental grants are rejected at verification.

### Immutable root / authority / GENESIS

Owner:

```text
BUILTIN\Administrators (S-1-5-32-544)
```

Allowed principals:

```text
SYSTEM          Full Control
Administrators  Full Control
Trading         read/list/traverse as appropriate
```

`Trading` receives no write/delete/owner/DACL authority to:

- `Paper-v2` immutable top-level authority material;
- `personal-desktop-paper-account-authority.json`;
- the GENESIS directory;
- the GENESIS checkpoint file.

### Runtime container

`Paper-v2\runtime` and `runtime\paper-operations` remain administrator-owned but grant the exact approved `Trading` SID the ordinary data rights required to create/read/write Architecture-67 runtime state. They do not grant `WRITE_DAC` or `WRITE_OWNER` through the reviewed ACL.

Runtime-created transition/operation staging and finalized objects may be owned by `Trading`; their accepted policy permits the data mutation needed by Architecture 67 while retaining SYSTEM/Administrators full control and excluding unrelated principals.

Architecture 103 treats same-`Trading` malicious code as inside the steady-state trading authority boundary; later broker/live phases must contain financial damage with deterministic risk, broker reconciliation, credential separation, and live arming rather than pretending NTFS can distinguish two processes carrying the same token.

## Runtime principal gate

Steady-state account authority is issued only to the exact C1-approved Trading SID.

The runtime gate proves at least:

- exact current user SID equals the approved Trading SID;
- primary process token;
- no thread impersonation token;
- token is not elevated;
- Administrators membership is not enabled.

It performs no LSA-right enumeration and has no dependency on `P3R1KspTestUser` or Performance Log Users rights classification.

## Read-only operational account authority

A v2 read authority is constructed from genuine `ValidatedProductionAuthority`; caller strings do not mint authority.

It:

1. derives the fixed `Paper-v2` and `runtime` paths from source constants;
2. verifies current token as exact Trading;
3. opens/pins the fixed parent/root/anchor/GENESIS/runtime objects with no-follow semantics;
4. strictly parses the anchor;
5. requires exact machine-authority and Trading-SID binding to C1;
6. re-derives `paper_account_id`;
7. verifies exact GENESIS SHA-256/length and Architecture-61 canonical semantics;
8. boundedly inventories recognized runtime transition/receipt layouts;
9. uses Architecture-66 full-lineage verification to determine the unique valid terminal checkpoint;
10. rejects malformed, unsafe, unexpected recognized collisions, duplicate/conflicting successor edges, stale anchor identity, unsafe object types, or ACL drift;
11. exposes one verified prior-checkpoint/account evidence object only after complete success.

Filesystem enumeration can supply candidates only. Names, timestamps, directory order, paths, or newest-file selection never create lineage authority.

The authority exposes no provider, broker, credential, scheduler, GUI, strategy, or live-order operation.

## Architecture-67 composition

For the personal-desktop line, the Architecture-67 `operation-root` is fixed by authority to:

```text
F:\AITradingBot\Paper-v2\runtime
```

PD2 may not accept an arbitrary caller-provided production operation root.

The verified v2 account authority supplies the exact prior-lineage evidence/terminal checkpoint needed by the existing deterministic paper-cycle composition. Architecture 67 continues to own:

- one-shot execution admission;
- prospective successor verification;
- staged transition write/readback;
- no-clobber transition finalization;
- committed-transition reread;
- receipt commitment;
- zero-runtime-call receipt recovery;
- no automatic retry after ambiguous staging/finalization.

Architecture 103 does not weaken those rules.

## Concurrency

Before PD2 can mutate the v2 runtime, one account-scoped exclusive Windows mutex is required.

Its name is deterministically derived from `paper_account_id` under a source-owned prefix and is never caller-selected. Acquisition is bounded and fail-closed. A detached preflight never substitutes for holding the mutex through inspection, execution, publication, and receipt commitment.

The mutex does not create account authority; it only prevents concurrent authorized writers.

Implementation of the mutex may reuse the accepted P3 concept, but the new branch must implement/review it independently rather than importing source by branch accident.

## Crash and provisioning recovery semantics

No automatic provisioning retry exists.

If the publisher exits unexpectedly after staging creation may have begun, that invocation's production-effect authorization is consumed. The operator performs read-only reconciliation before any new effect.

Reconciliation states:

```text
final absent, staging absent
  -> no durable publication observed; a NEW explicit authorization may later be considered

final absent, staging present
  -> incomplete/unpublished staging; automatic rerun forbidden

final present, staging absent
  -> validate final exactly; if valid, publication may be accepted after review

final present, staging present
  -> ambiguous/conflicting; block
```

A later personal-desktop recovery utility may, under a separate explicit owner/admin authorization, either finalize an *exact fully verified* staging tree by no-clobber rename or remove a reviewed unusable uncommitted staging tree. Such recovery requires exact frozen manifest/byte evidence but does **not** require KSP signing.

No recovery action is part of PD1 source implementation unless separately frozen.

## Source effect gate

During PD1 implementation and testing, production v2 mutation remains hard-disabled.

The production publisher/CLI must contain a source-owned gate whose default certified state is:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED=false
```

The effect check is the first executable gate, before freeze access, Administrator validation, or native API construction. The separate source-owned publication freeze remains unconfigured; enabling effects without configuring an accepted PD1E freeze still fails closed before mutation. A future PD1E source diff must populate the reviewed freeze and separately enable effects; neither operation is a caller-selectable runtime control.

Tests may exercise pure preparation and isolated disposable test-root logic, but must not mutate `F:\AITradingBot\Paper-v2` or the retained v1 paths.

A later tiny separately reviewed checkpoint may enable the production effect only after source certification, artifact/deployment review, exact bundle freeze, read-only readiness, and explicit user authorization.

## Rejected alternatives

Architecture 103 rejects the following shortcuts:

- use the failed v1 staging tree as the new account;
- rename or repair v1 as an incidental migration;
- allow a CLI path to choose the production paper root;
- use `uuid4()` for production paper-account identity;
- use current time as unreviewed GENESIS identity material;
- infer the Trading SID from a username without C1 reconciliation;
- store secrets in the paper anchor/manifest;
- permit admin/elevated steady-state trading;
- accept newest/lexicographically-last transition as authority;
- silently delete crash-left v2 staging and retry;
- weaken Architecture-67 duplicate/ambiguity semantics;
- require KSP/LSA/test-account ceremonies merely to satisfy the personal-desktop profile.

## PD1 implementation slices

### PD1A -- pure authority and bundle model

Implement without Windows effects:

- v2 anchor model/strict canonical parser/serializer;
- deterministic account-ID derivation;
- v2 provisioning manifest model/parser/serializer;
- pure bundle preparation from explicit starting cash + verified P2 selected snapshot evidence;
- exhaustive malformed/noncanonical/identity-mismatch tests.

Recommended model routing: **Luna Extra High** if kept strictly mechanical to this frozen contract; **Sol Medium** if integration with existing P2/Architecture-61 APIs proves subtle.

### PD1B -- Windows read-only authority and ACL/path policy

Implement:

- fixed v2 path constants;
- runtime Trading token gate;
- role-based ACL policy/inspection;
- no-follow fixed-object reader;
- bounded v2 inventory;
- C1/anchor/GENESIS/full-lineage reconciliation;
- account-scoped mutex contract if needed for the read/mutation seam.

Because this is native Windows security/authority code, use **Sol High**.

### PD1C -- disabled production publisher + disposable publication tests

Implement the one-shot publisher with the production effect gate still false, plus isolated disposable-root tests of create/flush/ACL/readback/no-clobber/crash classifications. No production v2 path effect is allowed.

Use **Sol High**.

### PD1D -- source certification and separate effect-readiness freeze

Only after A-C source review:

- focused tests;
- broad suite using the established Windows test workflow;
- exact GitHub diff review;
- source certification;
- separately freeze production bundle values and readiness checks;
- separately discuss enabling the production effect.

## Acceptance boundary

Architecture 103 design is accepted when this document and its validation plan are reviewed on the personal-desktop branch.

PD1 implementation is not accepted merely because unit tests pass. It requires exact source review and source certification while production effects remain disabled.

A future successful v2 publication will establish only a simulated paper-account authority. It will not authorize broker-paper or live trading.
