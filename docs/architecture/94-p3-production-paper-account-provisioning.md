# Architecture 94 P3 production paper-account provisioning

## Status

This document freezes the one-time production provisioning boundary required
before native Architecture-94 P3 acceptance may touch `F:\AITradingBot\Paper`.
It is additive to Architectures 61, 66, 67, and 94. It does not change any
accepted checkpoint, lineage, paper-operation, C1/C2/C3, or P3 runtime schema.

The accepted P3 source checkpoint before this clarification is:

```text
3d997ced083e6910e689b1d69193e0864485d844
```

Production paper-root creation remains blocked until a separately reviewed P3
provisioning implementation, release artifact, sealed-runtime deployment, and
frozen provisioning bundle exist.

Provider call #7 remains unauthorized. Production/live trading remains NO-GO.

## Why provisioning is a separate authority boundary

Architecture 61 intentionally converts an explicit opening-account assertion
into a deterministic immutable GENESIS checkpoint. It does not decide what the
production opening balance, positions, realized P&L, metadata, or timestamp
should be. Those values are identity material and therefore cannot be invented
inside an Administrator shell or native acceptance test.

Architecture 94 P3 likewise validates one fixed production root and immutable
anchor, but ordinary P3 runtime is read-only and deliberately contains no
provisioning API. Native P3 acceptance must therefore consume a paper account
that was established by a separately reviewed, one-time, Administrator-only
publication operation.

The provisioning boundary must not turn a caller path, current wall clock,
random UUID, provider response, GUI value, environment variable, or filesystem
enumeration result into paper-account authority.

## Production v1 opening-state policy

The first operational paper account is a fresh simulated account. Its GENESIS
request uses the existing Architecture-61 `PaperAccountGenesisRequest` and
`create_genesis_paper_account_checkpoint(...)` implementation unchanged.

Production v1 fixes the shape of the opening assertion to:

- cash-only account;
- no positions;
- cumulative realized profit/loss exactly `0`;
- no open orders;
- empty application metadata;
- one explicit positive starting-cash Decimal selected and approved before the
  provisioning bundle is frozen;
- one explicit UTC `as_of` selected and frozen before provisioning.

There is no code default for starting cash. Tests may use arbitrary valid values,
but the production value must appear in the reviewed bundle evidence before any
production filesystem mutation.

For the current Architecture-94 rollout, the GENESIS `as_of` is derived from the
already accepted call-#6 daily snapshot and is fixed to that snapshot's exact
strictly verified `snapshot.audit.captured_at`. This is a chronology seed only.
It does not make the C3 snapshot, its path, or P2 permit part of paper-account
identity or grant any C3 effect authority. Bundle construction must verify the
exact accepted call-#6 artifact before reading this timestamp. Provisioning itself
must not perform a provider request or discover/select another snapshot.

This choice guarantees the later verified-snapshot chronology requirement
`account_state.as_of <= snapshot.captured_at` without using a provisioning-time
clock.

## Deterministic paper-account ID

Production provisioning must not call `uuid4()` or otherwise mint a random
paper-account identity during publication.

The v1 paper-account UUID is derived with UUID5 using this dedicated namespace:

```text
32a20ea3-acb3-556f-ac96-2518bbf52f01
```

The UUID5 name is the existing byte-length-framed concatenation pattern over
these exact ordered UTF-8 strings:

```text
manual-paper-account-provisioning-id-v1
<machine_authority_id>
<approved_trading_sid>
<genesis_checkpoint_id>
<genesis_sha256>
<genesis_byte_length as base-10 text>
```

The resulting UUID is the anchor's `paper_account_id` and later selects the P3
account-mutex identity. It deliberately excludes C1 authority epoch, provider,
credential version, wall clock, paths, P2 selection ID, and mutable C3 state.

Changing the exact GENESIS artifact necessarily changes the production account
ID. An unrelated future C1 epoch does not.

## Frozen provisioning bundle

Production publication consumes exact prebuilt bytes. It does not construct a
GENESIS request from command-line scalars at the moment of publication.

A pure, offline preparation boundary must produce:

1. exact canonical Architecture-61 GENESIS checkpoint bytes;
2. exact canonical P3 `manual-paper-account-authority/v1` anchor bytes;
3. one strict canonical provisioning manifest with schema
   `manual-paper-account-provisioning/v1`.

The manifest binds at minimum:

- `paper_account_id`;
- `machine_authority_id`;
- approved Trading SID;
- genesis checkpoint ID;
- genesis SHA-256;
- genesis byte length;
- anchor SHA-256;
- anchor byte length.

The manifest must reconcile exactly with parsed GENESIS and anchor bytes and with
the deterministic account-ID derivation above. The manifest does not become a
runtime account-tip object and is not installed under `F:\AITradingBot\Paper`.
It is deployment evidence only.

Before production publication, ChatGPT/Sol review must freeze the exact manifest,
GENESIS, and anchor SHA-256/byte-length values. A filesystem path to those files
is transport only and cannot authorize different bytes.

The production publisher must reject any bundle whose exact evidence was not
supplied as the reviewed deployment expectation. It must not accept an
unreviewed alternate internally valid GENESIS account.

## Fixed final and staging paths

The only final production root is:

```text
F:\AITradingBot\Paper
```

The only v1 publication staging root is:

```text
F:\AITradingBot\.Paper.provisioning-v1
```

Neither path is caller-selected. Existing C1 path guards remain fixed to
`F:\AITradingBot\Authority`; they must not be widened to admit either paper path.
Paper provisioning requires its own fixed-path guard and native object boundary.

The final v1 genesis-only layout is exactly:

```text
F:\AITradingBot\Paper\
  manual-paper-account-authority.json
  paper-account-genesis-<genesis-checkpoint-id>\
    paper-account-checkpoint-<genesis-checkpoint-id>.json
```

`paper-operations` is intentionally absent at initial provisioning. The later P4
at-creation security seam owns creation of that namespace under the already
frozen P4/A67 output-security prerequisite.

## Preconditions

Production publication may begin only when all of these are true:

- code is running from the separately accepted, sealed P3+provisioning release
  under `F:\AITradingBot\runtime`;
- the current process is an elevated Administrator token;
- the reviewed local Trading account still resolves to the expected standard-user
  SID;
- the existing signed production C1 authority validates completely and yields
  the exact machine-authority ID and approved Trading SID bound by the bundle;
- the exact reviewed provisioning manifest, GENESIS bytes, and anchor bytes are
  rehashed and reconciled before any production paper-root mutation;
- relevant trading-bot runtime processes are quiescent;
- `F:\AITradingBot` resolves through a safe local fixed parent chain;
- neither the final paper root nor the fixed staging root is already occupied.

If the final root exists, the provisioner does not overwrite, replace, repair,
or create another account. If the staging root exists, provisioning is blocked
for manual recovery review. If both exist, provisioning is likewise blocked.

## At-creation Windows security

Every object is created with its final reviewed P3 security descriptor from the
start. Publication must not rely on process-token default DACLs, inherited ACLs,
or post-creation normalization.

The staging root receives the exact P3 `root` policy. Its children receive:

- anchor file: exact `anchor` policy;
- genesis directory: exact `genesis-directory` policy;
- genesis checkpoint file: exact `genesis-file` policy.

The immutable root/anchor/genesis owner remains Administrators as required by P3.
The exact protected/non-inheriting DACLs are the existing P3 policy; provisioning
must reuse that public policy rather than define a second ACL model.

The publisher must use Win32 create-new/no-follow semantics and retain handles for
identity/security/readback validation. It must never create a destination with
replace semantics.

## Publication sequence

The production algorithm is one-way and no-clobber:

1. validate Administrator identity, fixed parent, installed C1 authority, Trading
   SID, exact reviewed bundle, final-root absence, and staging-root absence;
2. create the fixed staging root with the exact final P3 root descriptor;
3. create the exact genesis staging directory with the exact final P3
   genesis-directory descriptor;
4. create the exact canonical GENESIS file with `CREATE_NEW`, flush its bytes,
   reread from the retained handle, and reconcile identity/security/hash/length
   and complete Architecture-61 verification;
5. create the exact canonical anchor with `CREATE_NEW`, flush its bytes, reread
   from the retained handle, and reconcile identity/security/hash/length and
   canonical P3 parsing;
6. require the staging inventory to contain exactly the anchor and anchored
   genesis directory/file and no other state;
7. recheck the fixed final path is absent while the retained staging root is
   still the same safe object;
8. rename the retained staging-root object to exactly
   `F:\AITradingBot\Paper` without replacement;
9. reopen and read-only validate the complete final root, exact object security,
   final paths, exact bytes, anchor/genesis relationship, and genesis-only graph;
10. close Administrator handles and end the Administrator phase.

The rename is the one publication point for the complete initial account tree.
No individually published final anchor/genesis objects are allowed before that
root publication.

The implementation may reuse public Windows security primitives such as security
attribute construction and handle inspection. It must not widen private C1 path
helpers or copy private helper implementations across modules.

## Crash and recovery semantics

Provisioning never automatically deletes or repairs ambiguous state.

Before final rename:

- a crash may leave only `F:\AITradingBot\.Paper.provisioning-v1`;
- any later provisioning attempt must detect that staging root and stop;
- no automatic cleanup, reuse, or resume is authorized.

After final rename:

- `F:\AITradingBot\Paper` is a published candidate account even if the process
  crashes before post-publication validation completes;
- later code must not recreate, overwrite, or repair it;
- read-only Administrator validation and then non-elevated Trading P3 validation
  determine whether it is acceptable;
- any mismatch requires manual architecture/recovery review.

A state where both fixed staging and final roots exist is ambiguous and blocks.

There is no "try again with a new account ID" path.

## Separation from P4/A67 mutation

This one-time provisioner creates only the immutable genesis account root. It is
not the P4 production object-creation seam for Architecture 67.

It must not create:

- transition directories;
- `paper-operations`;
- receipts;
- strategy plans;
- risk/order/execution output;
- C3 state;
- provider or broker effects.

P4 remains blocked until the separately frozen A67 at-creation output-security
seam is implemented and reviewed.

## Native production acceptance order

After source review, release freezing, sealed-runtime deployment, and one-time
provisioning, P3 production acceptance is split into explicit phases.

### Administrator publication evidence

Retain only bounded nonsecret facts such as:

- exact installed source/release identity;
- exact reviewed provisioning-manifest SHA-256/length;
- deterministic paper-account ID;
- exact genesis ID/SHA-256/length;
- exact anchor SHA-256/length;
- exact Trading SID and machine-authority ID;
- fixed final path;
- exact object-security validation PASS;
- staging root absent after successful publication;
- no provider/network/credential/broker activity.

### Trading acceptance evidence

After closing the elevated shell, run from the exact non-admin/non-elevated
Trading account and require:

- genuine C1 acquisition;
- genuine production P3 construction;
- P3 preflight PASS;
- exact paper-account ID/anchor/genesis evidence;
- `finalized_transition_count == 0`;
- empty historical snapshot dependency set;
- graph-derived terminal equals the anchored GENESIS checkpoint at sequence 0;
- native P3 account mutex acquire and lock-scoped complete revalidation PASS;
- lock scope invalid after release;
- immutable anchor/genesis writes denied;
- no provider call, credential access, network access, C2/C3 mutation, paper
  transition mutation, or broker activity.

Only after both phases pass may P3 production acceptance be declared complete.
This does not authorize P4 or production/live trading.

## Implementation stop conditions

Stop for ChatGPT/Sol architecture review instead of proceeding if implementation
appears to require any of the following:

- changing Architecture-61 GENESIS schema or deterministic identities;
- caller-selected final/staging production roots;
- runtime generation of random paper-account IDs;
- a production-time wall clock as GENESIS identity material;
- provider/network/Credential Manager access;
- copying or mutating C3 evidence;
- widening C1 fixed-root guards;
- ACL inheritance/default-DACL assumptions or post-publication ACL repair;
- automatic staging cleanup or provisioning resume;
- replacing an existing final paper root;
- creation of A67 transition/receipt state;
- a second P4/A67 commit algorithm.

## Accepted production bundle freeze

The production-v1 bundle is frozen and accepted from source commit
`bc1536316e153048833db7a2769f811007382d0e` and tree
`ff3428b459ebfa0ebd36e15d889efcf2d5628da7`.

The first attempted release envelope is retained historical evidence only:

```text
F:\AI\p3-paper-provisioning-freeze-v1
state = FAILED_RETAINED
reuse = FORBIDDEN
```

It must not be deleted, repaired, overwritten, or reused. The accepted bundle is
under the separate retained v2 envelope:

```text
F:\AI\p3-paper-provisioning-freeze-v2
state = ACCEPTED
regeneration = FORBIDDEN
```

The v2 bundle was created offline after independent Trading-account retention of
the already accepted call-#6 bytes and Administrator revalidation of installed C1.
No P2 selected read was rerun, no provider request occurred, provider call #7 was
not authorized, and `F:\AITradingBot\Paper` remained absent.

The exact frozen deployment facts are:

```text
P3_PROVISIONING_SOURCE_HEAD=bc1536316e153048833db7a2769f811007382d0e
P3_PROVISIONING_SOURCE_TREE=ff3428b459ebfa0ebd36e15d889efcf2d5628da7
MACHINE_AUTHORITY_ID=223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1
TRADING_SID=S-1-5-21-1397534616-3988210162-180023805-1009
C1_BOOTSTRAP_DIGEST=53b8b72ab18b1c477c5eab50857e4dc2d47efc6e74030e380ed6a53387922ae4
PAPER_ACCOUNT_STARTING_CASH=100000
PAPER_ACCOUNT_GENESIS_AS_OF=2026-08-29T09:46:43.769105+00:00
CALL6_SNAPSHOT_ID=eba46838-44ae-5bec-97bf-98c6639ae6a7
CALL6_ARTIFACT_SHA256=31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
CALL6_ARTIFACT_BYTES=1291
PAPER_ACCOUNT_ID=d1510a4b-6ebf-58ef-92a4-e743ca91151e
GENESIS_CHECKPOINT_ID=7b7b83ba-69e2-5ed8-a033-b4306cd1ffc7
GENESIS_SHA256=b6172753ee4f30a82265ff38b341c3de42869ba6af7ccb69739234135183026d
GENESIS_BYTES=534
ANCHOR_SHA256=650b977db5ea5f5f1d89e3ed5bf52dfb5b2c5c44c3b34ccceb6d22dd492df871
ANCHOR_BYTES=411
PROVISIONING_MANIFEST_SHA256=8505eddd07be2f90d1211ee49a9cac4829d0faff9d88d0dc4c609b209a2e8801
PROVISIONING_MANIFEST_BYTES=522
FREEZE_EVIDENCE_SHA256=7f2824adf5105f66e16b62aa4c6659d16669dea8208bbd2496eb96adbab0e034
FREEZE_EVIDENCE_BYTES=1353
P2_SELECTED_READ_RERUN=False
PROVIDER_CALL_PERFORMED=False
PROVIDER_CALL_7_AUTHORIZED=False
PRODUCTION_PAPER_ROOT_CREATED=False
```

These values are immutable release evidence for this production-v1 account. A
path, regenerated internally valid bundle, different starting cash, different
snapshot, or different artifact bytes cannot substitute for them.

The next authorized gate is release preparation only:

```text
exact bc153631 source
-> isolated Git export
-> offline wheel build
-> wheel/RECORD/package exact-match certification
-> freeze wheel SHA-256/length
-> separately reviewed sealed-runtime deployment
```

Production publication remains a later explicit approval point. This docs
checkpoint does not authorize creation of `F:\AITradingBot\Paper`, P4 execution,
provider call #7, or production/live trading.
