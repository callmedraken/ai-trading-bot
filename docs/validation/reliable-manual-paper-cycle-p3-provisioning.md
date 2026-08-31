# Architecture 94 P3 production paper-account provisioning validation

## Purpose

This plan validates the one-time production paper-account provisioning boundary
before any native P3 production acceptance touches `F:\AITradingBot\Paper`.

It is intentionally separate from P3 ordinary runtime verification and from the
future P4/A67 production object-creation seam.

Base source checkpoint for this clarification:

```text
3d997ced083e6910e689b1d69193e0864485d844
```

No provider call #7, Credential Manager access, network/provider request,
brokerage action, paper transition execution, or live trading is authorized by
this plan.

## A. Pure provisioning-bundle gate

Implement and test a pure boundary that accepts only explicit already-known
inputs and returns immutable provisioning evidence/bytes. It performs no
production filesystem I/O.

Required inputs include:

- exact machine-authority ID assertion;
- exact approved Trading SID assertion;
- explicit positive starting-cash Decimal;
- exact accepted call-#6 verified snapshot evidence sufficient to obtain the
  canonical `snapshot.audit.captured_at` for the rollout GENESIS `as_of`.

The production v1 GENESIS request must be exactly:

```text
as_of = exact accepted call-#6 snapshot.audit.captured_at
cash = explicitly approved positive Decimal
positions = ()
realized_profit_loss = Decimal("0")
metadata = ()
open_orders = ()
```

No current clock, environment timestamp, random identifier, GUI field, provider
request, or broker state may contribute.

The pure builder must:

1. create the exact Architecture-61 GENESIS checkpoint through the existing
   public builder;
2. serialize exact canonical GENESIS bytes;
3. compute exact GENESIS SHA-256 and byte length;
4. derive the exact P3 production paper-account UUID using namespace
   `32a20ea3-acb3-556f-ac96-2518bbf52f01` and the frozen framed material;
5. create the existing canonical `manual-paper-account-authority/v1` anchor;
6. serialize exact anchor bytes and compute SHA-256/length;
7. create one strict canonical `manual-paper-account-provisioning/v1` manifest
   binding those identities and artifact facts;
8. round-trip/reverify all three artifacts before returning success.

### Pure bundle negative tests

Reject at minimum:

- zero/negative/non-Decimal starting cash;
- nonempty positions, nonzero realized P&L, metadata, or open orders for the
  production-v1 builder;
- unverified/mismatched call-#6 snapshot bytes;
- an `as_of` not equal to the strictly verified accepted call-#6 captured-at;
- malformed/noncanonical machine UUID or Trading SID;
- random/caller-supplied production paper-account UUID substitution;
- anchor/genesis/manifest hash, length, ID, or field mismatch;
- duplicate/unknown manifest fields;
- noncanonical JSON or trailing bytes.

The generic Architecture-61 builder itself remains unchanged and may continue to
support its broader valid state space for tests/offline callers.

## B. Deterministic identity gate

For fixed inputs, repeated bundle construction under different process runs,
Decimal contexts, locale settings, environment variables, and clocks must return
byte-identical GENESIS, anchor, and manifest artifacts and the same account UUID.

Changing any one of these must change the deterministic account UUID:

- machine-authority ID;
- approved Trading SID;
- genesis checkpoint ID;
- genesis SHA-256;
- genesis byte length.

Changing unrelated C1 authority epoch/provider/credential data must not change
the account UUID.

No path, mtime, process ID, current user name, enumeration order, or release
working directory may enter account identity.

## C. Fixed path and no-clobber gate

Production publisher paths are code-owned:

```text
FINAL   = F:\AITradingBot\Paper
STAGING = F:\AITradingBot\.Paper.provisioning-v1
```

Tests must prove:

- caller-selected final or staging roots are rejected;
- C1 `F:\AITradingBot\Authority` path guards remain unchanged and continue to
  reject the paper paths;
- unsafe alias, UNC, device, GLOBALROOT, alternate-volume, reparse, reserved-name,
  `.`/`..`, trailing-dot/space, ADS, or case-fold collision paths fail closed;
- final-root presence prevents all provisioning mutation;
- staging-root presence prevents all provisioning mutation and yields a bounded
  manual-recovery classification;
- both roots present blocks;
- no replace/delete/repair API is exposed.

## D. At-creation security gate

The publisher must use the existing public P3 security policies exactly.

Prove each object is created with the final descriptor from the start:

| Object | P3 role |
| --- | --- |
| fixed staging/final root | `root` |
| `manual-paper-account-authority.json` | `anchor` |
| anchored genesis directory | `genesis-directory` |
| anchored genesis checkpoint file | `genesis-file` |

Required tests:

- owner must be Administrators for immutable production objects;
- DACL protected state must be exact;
- ACE order/masks/flags must be exact;
- no inherited ACEs;
- no process-token default-DACL dependence;
- no post-create ACL normalization;
- no `WRITE_DAC`/`WRITE_OWNER` grant to Trading;
- anchor/genesis are immutable to Trading under the reviewed policy;
- root permissions remain exactly the current P3 root policy and are not widened.

Use fake-native tests for ordinary source gates. Real global/fixed production
objects remain explicit opt-in acceptance only.

## E. Publication algorithm gate

Instrument the native seam and prove exact ordering:

```text
validate all immutable inputs
validate final absent
validate staging absent
create staging root CREATE_NEW/no-clobber equivalent
create genesis directory with exact descriptor
create+flush+reread exact genesis file
verify Architecture-61 PASS
create+flush+reread exact anchor
verify canonical anchor and deterministic account ID
verify exact staging inventory
revalidate staging identity/security
recheck final absent
no-replace rename retained staging root -> final root
reopen/read-only validate final tree
```

No final-root child may be published individually before the root rename.

Tests must verify no create/rename call occurs before complete bundle
verification.

## F. Crash-state gate

Inject deterministic failures at every publication boundary.

### Before root rename

Any simulated crash after staging creation but before final rename must leave no
final root. The resulting staging root is preserved. A second publication attempt
must block without deleting, reusing, or resuming it.

### At/after root rename

If final rename succeeds and the process fails before final validation returns,
the final root is a published candidate. A second publication attempt must not
write to it. Read-only validation is the only permitted next step.

Tests must cover:

- failure creating staging root;
- failure creating genesis directory;
- partial/failed genesis write;
- genesis reread mismatch;
- failed genesis verification;
- failed anchor write/reread/parse;
- unexpected staging inventory;
- staging identity/security change;
- final path appearing before rename;
- rename failure;
- final identity/security/readback mismatch after rename;
- final+staging ambiguous coexistence.

No test may assert that automatic cleanup/repair/retry is correct behavior.

## G. Existing-boundary regression gate

Focused regressions must prove the provisioning implementation does not alter:

- Architecture-61 GENESIS identity/canonicalization vectors;
- P3 anchor parser/serializer;
- P3 paper-specific path/security policy;
- P3 graph-derived genesis-only preflight;
- P3 account mutex identity/security;
- C1 fixed-root guards and authority provisioning;
- A67 source and commit/recovery semantics.

Do not modify Architecture-61, -66, or -67 schemas.

## H. Release/deployment prerequisite

No production paper-root mutation occurs from a development worktree or mutable
editable install.

Before Administrator publication:

1. source checkpoint is accepted by ChatGPT/Sol review;
2. build one isolated wheel from the exact accepted source;
3. verify wheel RECORD and exact package/source bytes offline;
4. freeze wheel SHA-256 and byte length;
5. deploy the exact wheel to `F:\AITradingBot\runtime` using the established
   sealed-runtime Administrator sequence;
6. reconcile installed RECORD/source/import provenance and fixed schema/resource
   bytes;
7. republish the reviewed Trading runtime RX boundary if deployment temporarily
   revokes it;
8. close deployment shell before separate provisioning/Trading acceptance phases.

The provisioning code must not be copied ad hoc into `site-packages`.

## I. Provisioning-bundle freeze checkpoint

Before the Administrator production publication command is authorized, retain a
reviewed record containing at minimum:

```text
P3_PROVISIONING_SOURCE_HEAD=<exact sha>
P3_PROVISIONING_WHEEL_SHA256=<exact sha256>
P3_PROVISIONING_WHEEL_BYTES=<exact length>
PAPER_ACCOUNT_STARTING_CASH=<exact canonical Decimal>
PAPER_ACCOUNT_GENESIS_AS_OF=<exact UTC timestamp>
PAPER_ACCOUNT_ID=<deterministic UUID>
GENESIS_CHECKPOINT_ID=<UUID>
GENESIS_SHA256=<sha256>
GENESIS_BYTES=<length>
ANCHOR_SHA256=<sha256>
ANCHOR_BYTES=<length>
PROVISIONING_MANIFEST_SHA256=<sha256>
PROVISIONING_MANIFEST_BYTES=<length>
MACHINE_AUTHORITY_ID=<exact installed value>
TRADING_SID=<exact installed value>
PROVIDER_CALL_7_AUTHORIZED=False
PRODUCTION_LIVE=NO-GO
```

The actual production command must reprove these exact values before mutation.

## J. Native Administrator provisioning acceptance

Run only from an elevated Administrator shell after the freeze checkpoint.

Prove:

- exact Administrator/elevated identity;
- exact sealed runtime import provenance;
- exact installed C1 authority validation;
- exact expected machine-authority ID and Trading SID;
- runtime quiescence;
- exact frozen bundle hashes/lengths;
- final and staging absence before first publication;
- exact object ACL/owner/type/final-path evidence;
- exact final inventory and artifact byte identity after publication;
- staging absent after successful rename;
- no database mutation;
- no network/provider/credential/broker activity.

A successful Administrator phase does not itself prove P3 runtime authority,
because genuine production P3 construction is later performed under the Trading
principal through genuine C1.

## K. Native non-admin Trading P3 acceptance

After the Administrator shell is closed, run from exact non-elevated/non-admin
Trading.

Require:

```text
C1_AUTHORITY_ACQUIRED=PASS
P3_AUTHORITY_CONSTRUCTED=PASS
P3_PREFLIGHT=PASS
P3_FINALIZED_TRANSITION_COUNT=0
P3_HISTORICAL_SNAPSHOT_DEPENDENCY_COUNT=0
P3_TERMINAL_KIND=GENESIS
P3_TERMINAL_SEQUENCE=0
P3_TERMINAL_ID=<exact frozen genesis id>
P3_PAPER_ACCOUNT_ID=<exact frozen account id>
P3_NATIVE_MUTEX_ACQUIRED=PASS
P3_LOCKED_REVALIDATION=PASS
P3_LOCK_SCOPE_INVALID_AFTER_RELEASE=PASS
ANCHOR_WRITE_BLOCKED=True
GENESIS_WRITE_BLOCKED=True
PROVIDER_CALL_PERFORMED=False
CREDENTIAL_MANAGER_READ=False
NETWORK_OPERATION_PERFORMED=False
AUTHORITY_DATABASE_MUTATION=False
PAPER_TRANSITION_MUTATION=False
PRODUCTION_LIVE=NO-GO
```

The account mutex may create/open its reviewed kernel object. That is the only
P3 acceptance synchronization effect; it is not paper-account mutation.

## L. P4 remains blocked

P3 provisioning acceptance does not authorize the first paper cycle.

P4 production execution remains blocked until its separately reviewed at-creation
A67 output-security seam proves:

```text
A67 production creation seam
-> exact P3 ACL on staging
-> exact P3 ACL on finalized transition
-> exact P3 ACL on paper-operations/receipt
-> subsequent P3 preflight PASS
```

No provisioning code may be reused as a second transition/receipt commit
algorithm.

## M. Required milestone reporting

Every provisioning implementation/verification report must state the next step
and retain these negative facts explicitly:

```text
PROVIDER_CALL_7=NOT_AUTHORIZED
PRODUCTION_LIVE=NO-GO
P4_PRODUCTION_EXECUTION=BLOCKED
```
