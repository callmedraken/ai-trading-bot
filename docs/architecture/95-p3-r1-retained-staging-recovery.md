# Architecture 95: P3-R1 retained-staging recovery

## Purpose

This checkpoint defines the only reviewed recovery path for the retained
Architecture-94 production staging tree after the first native Administrator
publication attempt stopped at the root-rename boundary.

The recovery is deliberately separate from the ordinary P3 publisher. It does
not make the existing publisher resumable and does not authorize cleanup,
replacement, regeneration, a new account identifier, P4 execution, provider
call #7, or production/live trading.

**Architecture 96 is a mandatory addendum to this document.** It closes the
post-build release/operator authority-binding gap found during review of the
first P3-R1 implementation. Any implementation of this architecture must also
satisfy the signed-recovery-authorization contract in Architecture 96. A
caller-created SID/digest/deployment-expectation object is not recovery
authority.

## Frozen incident state

The accepted production facts before any P3-R1 implementation are:

```text
FINAL = F:\AITradingBot\Paper
STAGING = F:\AITradingBot\.Paper.provisioning-v1

FINAL_EXISTS=False
STAGING_EXISTS=True
PUBLICATION_STATE=STAGING_REQUIRES_MANUAL_RECOVERY

PAPER_ACCOUNT_ID=d1510a4b-6ebf-58ef-92a4-e743ca91151e
GENESIS_CHECKPOINT_ID=7b7b83ba-69e2-5ed8-a033-b4306cd1ffc7
GENESIS_SHA256=b6172753ee4f30a82265ff38b341c3de42869ba6af7ccb69739234135183026d
GENESIS_BYTES=534
ANCHOR_SHA256=650b977db5ea5f5f1d89e3ed5bf52dfb5b2c5c44c3b34ccceb6d22dd492df871
ANCHOR_BYTES=411

AUTHORITY_DB_SHA256=6a8fb988d1cb223fbb66b09e8dab1e0de4b6aafd148dfdf01df08029203f4b76
AUTHORITY_DB_BYTES=331776

PROVIDER_CALL_7_AUTHORIZED=False
PRODUCTION_LIVE=NO-GO
P4_PRODUCTION_EXECUTION=BLOCKED
```

The retained staging forensic proved exact root/genesis-directory/genesis-file/
anchor security, exact frozen genesis and anchor bytes, canonical GENESIS
verification, exact inventory, stable object identities, final-root absence,
and unchanged authority database. The staging tree is therefore preserved as
immutable recovery evidence rather than treated as damaged state.

## Native failure diagnosis

Disposable native Windows diagnostics established the actual production failure
mechanism:

```text
absolute-path retained-root rename with no open descendants    -> PASS
open child directory retained across root rename               -> ERROR_ACCESS_DENIED
open direct child file retained across root rename             -> ERROR_ACCESS_DENIED
open nested child file retained across root rename             -> ERROR_ACCESS_DENIED
full Architecture-94 publisher descendant-handle topology      -> ERROR_ACCESS_DENIED
same tree after every descendant handle is closed              -> PASS
adding FILE_SHARE_DELETE to the root handle                    -> still ERROR_ACCESS_DENIED
```

A stronger follow-up proved the absolute destination form used by the publisher
is valid on this machine: after a successful root-only
`SetFileInformationByHandle(FileRenameInfo)` call,
`GetFinalPathNameByHandleW` immediately returned the exact intended final path
and the final namespace entry was visible while the retained root handle
remained open.

Therefore the defect is not the frozen bundle, the staging ACLs, the target
path, or the authority database. The defect is the assumption that descendant
handles may remain open across a directory-root rename on the production
Windows filesystem.

## Recovery authority boundary

P3-R1 is an Administrator-only, sealed-runtime, exact-state recovery operation.
It accepts no caller-selected root, account ID, genesis ID, replacement mode,
cleanup mode, or generic resume flag.

The operation is callable only when all of the following hold:

1. current token is the exact elevated Administrator operator;
2. execution is from the exact sealed production runtime;
3. installed C1 is complete and matches the exact frozen machine authority and
   Trading SID;
4. the accepted P3 production bundle and post-build release/deployment identity
   are independently bound by the valid signed Architecture-96 recovery
   authorization, and the signed exact Administrator SID equals the actual
   current-token SID;
5. `F:\AITradingBot\Paper` is absent;
6. `F:\AITradingBot\.Paper.provisioning-v1` exists;
7. the staging tree validates exactly as the previously accepted forensic state;
8. the authority database is exact and unchanged;
9. relevant production runtime processes are quiescent;
10. no provider, credential, broker, strategy, risk, paper-transition, or P4
    authority is invoked.

A caller-supplied SID, installed-RECORD digest/length, release path, environment
value, manifest, or reconstructed expectation object may be evidence but cannot
satisfy item 4. Architecture 96 defines the non-circular signed post-build
binding and process-local recovery permit required before the native mutation
boundary.

Any other state fails closed. In particular, final present, final+staging,
staging absent, unexpected staging inventory, identity/security drift, frozen
byte mismatch, account-ID mismatch, release/authorization mismatch, or database
drift must block without mutation.

## Required retained-handle ordering

P3-R1 must preserve the original anti-TOCTOU intent while respecting the native
Windows constraint established by the diagnostics.

The required order is:

```text
validate immutable signed-release authorization/bundle/C1 inputs
-> retain safe parent handle
-> retain staging-root handle with delete authority and no replacement sharing
-> open and retain every expected staging descendant
-> validate exact security, final paths, identities, inventory, bytes, hashes,
   canonical anchor, canonical GENESIS, and deterministic IDs
-> record native identity facts for root and every descendant
-> revalidate all retained handles and inventories
-> require final path still absent
-> close every descendant handle
-> prove every descendant handle close succeeded
-> retain only the safe parent and exact staging-root handles
-> revalidate retained staging root identity/security/final path
-> require final path still absent
-> perform one absolute-path, no-replace retained-root rename
-> require native rename success
-> require retained root final path == \\?\F:\AITradingBot\Paper
-> require staging namespace absent and final namespace present
-> reopen every final descendant read-only
-> require each reopened native identity equals its recorded pre-rename identity
-> revalidate exact final ACL/owner/type/final path/inventory/bytes/hashes
-> reverify canonical anchor/GENESIS relationship and genesis-only state
-> require authority database before == after
-> close all handles
-> return recovered publication validation evidence
```

The close-descendants boundary is intentional. Once a descendant handle is
closed, its previously recorded native identity is audit evidence only. It does
not authorize publication. Publication remains authorized solely by the valid
Architecture-96 process-local recovery permit together with the retained staging
root, retained trusted parent, exact fixed destination, and the complete
pre-rename proof.

After rename, every descendant must be reopened and matched to its exact
pre-rename native identity before P3-R1 can report success.

## Root rename primitive

P3-R1 must use the already reproduced production-compatible primitive:

- `SetFileInformationByHandle`;
- information class `FileRenameInfo`;
- `ReplaceIfExists` / flags equivalent to false/zero;
- no caller destination;
- exact absolute destination `F:\AITradingBot\Paper`;
- retained staging-root handle as the object being renamed.

Do not change to the unproven parent-handle-relative form. Disposable diagnostics
returned `ERROR_INVALID_PARAMETER` for that form on this environment.

Immediately after successful rename, the retained root handle must be checked
with `GetFinalPathNameByHandleW` before any final descendant is trusted.

## Crash and ambiguity semantics

P3-R1 is one-way and nonretryable once its production mutation boundary is
crossed.

Before the root rename, failure leaves the existing retained staging tree and no
final tree. The recovery attempt is retained failed evidence and must not be
rerun blindly. A previously valid signed authorization is not generic retry
authority after a failed invocation.

The first production mutation marker must occur immediately before the native
root rename.

At or after the rename call, any exception or uncertain return is an ambiguous
publication outcome. The code must not clean up, reverse, retry, or infer state
from intended ordering. A separate read-only state-resolution pass must classify
final/staging visibility and validate any final candidate.

If rename succeeds but final validation fails, the final tree is a published
candidate. No overwrite, delete, replacement, or recreation is permitted.

There is no path that abandons this deterministic account and silently creates a
new account ID.

## Ordinary publisher correction

The ordinary clean-state Architecture-94 publisher must also be corrected so a
future clean publication does not retain descendant handles across its root
rename.

Its new ordering must mirror the proven native constraint:

```text
complete staging validation with descendants retained
-> record descendant identities
-> close descendants successfully
-> retain/revalidate parent + root
-> no-replace absolute root rename
-> prove retained root final path
-> reopen final descendants
-> compare exact pre/post native identities
-> full final read-only validation
```

The ordinary publisher must continue to reject an existing staging root. It must
not call or implicitly invoke P3-R1 recovery.

## Test model correction

The fake-Win32 test kernel must model the native rule discovered in production:
a root rename fails with an access-denied result whenever any descendant handle
is still open.

Tests must prove:

- the previous retained-descendant ordering now fails in the fake model;
- ordinary publisher success requires all descendants closed before rename;
- the retained root remains open through rename and final-path proof;
- reopened final descendants have the same native identities as the recorded
  staging descendants;
- a close failure blocks before mutation;
- final appearing before rename blocks;
- rename failure preserves staging and never creates final;
- ambiguous/after-rename failures never trigger cleanup or retry;
- recovery rejects clean-state absence of staging;
- recovery rejects final present or final+staging;
- recovery rejects any staging security/identity/inventory/byte mismatch;
- recovery performs no provider/network/credential/P4/paper-transition effect;
- Architecture-96 signed-authorization and permit gates cannot be bypassed by
  caller-selected evidence.

Add an opt-in native disposable Windows regression that reproduces at minimum:

```text
retained descendant -> ERROR_ACCESS_DENIED
same tree, descendants closed -> rename PASS
retained root final path -> exact intended absolute final path
```

The native regression must use pytest-managed/external-basetemp scratch rather
than intentionally using a worktree `.pytest_cache`. No native test may touch
either production Paper path.

## Release and production recovery gates

P3-R1 source implementation does not authorize production recovery.

After source review:

```text
accepted corrected P3-R1/Architecture-96 source checkpoint
-> focused/fake-native tests
-> opt-in disposable native Windows rename regression
-> one broad source-certification suite
-> exact isolated wheel build
-> wheel/RECORD/package reconciliation
-> freeze new wheel SHA-256/length
-> construct/sign/freeze canonical Architecture-96 recovery authorization
-> separately reviewed sealed-runtime deployment of the authorized wheel
-> installed RECORD/payload reconciliation
-> read-only revalidation of the retained production staging tree
-> explicit operator authorization for exactly one P3-R1 production recovery
-> Administrator recovered-publication validation
-> close Administrator shell
-> exact non-admin Trading P3 acceptance
```

A sealed-runtime deployment must not modify, delete, rename, or inspect the
retained production staging tree beyond separately reviewed read-only gates.

## Non-authorizations

This architecture checkpoint does not authorize any of the following:

```text
PRODUCTION_RECOVERY_RENAME=NOT_AUTHORIZED
PUBLISHER_RERUN=FORBIDDEN
STAGING_DELETE_OR_REPAIR=FORBIDDEN
CALLER_ASSERTED_RECOVERY_AUTHORITY=FORBIDDEN
UNSIGNED_RECOVERY_AUTHORIZATION=FORBIDDEN
P3_TRADING_ACCEPTANCE=BLOCKED_PENDING_RECOVERY
P4_PRODUCTION_EXECUTION=BLOCKED
PROVIDER_CALL_7=NOT_AUTHORIZED
PRODUCTION_LIVE=NO-GO
```

## Next milestone

Implementation commit `2b82222fbaee857e02519a0ea3627679d309276d` is retained as a
correction-required checkpoint: its rename/identity/crash design is useful, but
its caller-asserted deployment/operator expectation is not accepted authority.

Use Sol High for one bounded correction implementing Architecture 96 on top of
that retained checkpoint, including the signed authorization/process-local
permit boundary and disposable-native-scratch fix. Production recovery remains
blocked until ChatGPT/Sol reviews and accepts the corrected exact diff and the
later release/deployment/authorization evidence.
