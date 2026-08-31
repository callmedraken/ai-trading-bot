# P3-R1 retained-staging recovery validation plan

## Scope

Validate the Architecture-95 recovery boundary for the already retained
production staging tree created by the failed Architecture-94 Administrator
publication attempt.

**Architecture 96 and
`docs/validation/reliable-manual-paper-cycle-p3-r1-signed-authorization.md` are
mandatory addenda to this plan.** The first P3-R1 implementation proved the
native rename correction but exposed a caller-asserted operator/release identity
shape that is not accepted authority. The corrected source must pass both plans.

This plan covers source/fake-native/native-disposable validation only until a
separate production recovery authorization is issued.

No test or implementation step in this checkpoint authorizes deletion or repair
of the production staging tree, rerunning the original publisher, P4 execution,
provider call #7, brokerage activity, or production/live trading.

## A. Incident regression

Encode the discovered native Windows behavior as a regression:

- absolute-path `FileRenameInfo` of a directory succeeds with no descendant
  handles open;
- any retained descendant directory/file handle causes `ERROR_ACCESS_DENIED`;
- closing every descendant before the same rename permits success;
- adding delete sharing to the retained root does not make retained descendants
  compatible;
- after success, the retained root resolves to the exact final path and the
  destination namespace entry is visible.

The fake Win32 kernel must reproduce these semantics instead of allowing the old
invalid retained-descendant topology.

## B. Ordinary publisher correction

Verify the ordinary clean-state publisher:

1. validates all staging descendants while their handles are retained;
2. records exact native identities;
3. closes every descendant successfully before publication;
4. blocks before rename if any close fails;
5. retains the trusted parent and staging-root handles;
6. revalidates root identity/security and final absence;
7. performs exact absolute-path no-replace root rename;
8. proves the retained root final path;
9. reopens final descendants read-only;
10. requires exact pre/post native identity equality;
11. reruns full final security/inventory/byte verification.

The ordinary publisher must still reject any preexisting staging root and must
never invoke recovery implicitly.

## C. Dedicated recovery admission

The recovery seam accepts exactly the frozen retained-state condition:

```text
FINAL absent
STAGING present
paper account d1510a4b-6ebf-58ef-92a4-e743ca91151e
genesis 7b7b83ba-69e2-5ed8-a033-b4306cd1ffc7
exact frozen genesis/anchor/manifest evidence
exact machine authority + Trading SID
exact initialized supported C1
valid Architecture-96 signed post-build authorization
actual elevated Administrator SID == signed exact operator SID
actual installed RECORD/package == signed accepted release identity
```

Reject before Paper staging access or mutation when:

- the recovery authorization is absent, unsigned, tampered, wrong-purpose, or
  signed by an untrusted key;
- the current Administrator SID differs from the signed exact operator SID;
- installed RECORD/package provenance differs from the signed release identity;
- caller-created SID/digest/path/deployment objects are presented instead of the
  process-local Architecture-96 permit;
- final exists;
- final and staging both exist;
- staging is absent;
- staging is an unsafe type/reparse/alias;
- root/child owner or DACL differs;
- root/child native identity changes during validation;
- inventory differs;
- genesis/anchor bytes, hashes, lengths, IDs, or canonical verification differ;
- installed C1/runtime provenance differs;
- authority database identity differs;
- production runtime is not quiescent.

No recovery API accepts a caller path, account ID, replacement flag, cleanup
flag, new-account option, caller-selected operator SID, caller-selected release
digest, or generic retry/resume flag.

## D. Recovery ordering gate

Instrument the recovery seam and require this ordering:

```text
signed authorization verification + process-local permit issuance
preconditions
open parent/root
open descendants
complete staging proof
record all native identities
revalidate staging proof
close all descendants
prove all closes succeeded
revalidate retained root + final absence
FIRST_PRODUCTION_MUTATION=P3_R1_ROOT_RENAME
absolute no-replace retained-root rename
retained-root final-path proof
namespace final/staging proof
reopen final descendants
pre/post descendant identity equality
complete final proof
DB before/after equality
```

No descendant close is itself a production mutation marker. The mutation marker
is immediately before the native root rename.

## E. Crash-state gate

Inject faults at every boundary.

Before the rename marker:

- final must remain absent;
- existing staging remains the retained recovery state;
- no cleanup/retry/resume is performed;
- a previously valid signed authorization does not become implicit retry
  authority after a failed invocation.

At or after the rename marker:

- outcome is conservative/ambiguous until state is re-resolved;
- no reverse rename, delete, repair, overwrite, or retry occurs;
- final candidate state, if present, is validated only through read-only gates.

A failed recovery attempt is retained historical evidence and is never silently
rerun.

## F. Identity continuity gate

For every descendant:

- capture native volume/file identity before handles are closed;
- after root publication reopen the corresponding exact final object;
- require reopened native identity to equal the recorded staging identity;
- require exact role/type/final path/security;
- require exact bytes for immutable files.

Root identity must remain stable on the retained handle across the rename.

## G. Isolation / no-effect gate

Focused and native-disposable tests must prove:

```text
PROVIDER_CALL_PERFORMED=False
PROVIDER_CALL_7_AUTHORIZED=False
CREDENTIAL_MANAGER_READ=False
BROKER_OPERATION_PERFORMED=False
PAPER_TRANSITION_MUTATION=False
P4_PRODUCTION_EXECUTION=False
```

Disposable native tests operate outside `F:\AITradingBot\Paper` and
`F:\AITradingBot\.Paper.provisioning-v1`.

New disposable native tests must use pytest-managed temporary paths or another
explicit external scratch root. They must not intentionally use the worktree
`.pytest_cache` as general filesystem scratch.

## H. Source verification

During implementation, run focused tests only, including:

- `tests/runtime/test_windows_paper_account_provisioning.py`;
- recovery tests;
- Architecture-96 authorization/permit tests;
- relevant P3 authority/security/provisioning regression tests;
- Ruff check/format checks for changed files.

Every controlled Windows pytest invocation uses a fresh explicit
`--basetemp` beneath `F:\AI\temp\pytest\...` and normally
`-p no:cacheprovider`. Do not use the default user-temp pytest hierarchy or
repair retained historical cache/temp state merely to make a gate pass.

Do not run broad/full-suite certification repeatedly during iteration. Reserve a
single broad suite for the final corrected source candidate after ChatGPT exact-
diff acceptance.

## I. Production remains blocked

Source/fake/native-disposable PASS does not authorize production recovery.

After ChatGPT/Sol accepts the corrected exact implementation diff, separately
perform:

```text
one broad isolated-basetemp source certification
-> new release wheel freeze
-> wheel/RECORD/package reconciliation
-> collect exact elevated Administrator SID
-> construct/sign/freeze Architecture-96 canonical recovery authorization
-> sealed-runtime deployment of exactly authorized wheel
-> installed RECORD/package reconciliation
-> read-only retained-staging revalidation
-> explicit one-time operator recovery approval
-> Administrator P3-R1 recovery
-> non-admin Trading P3 acceptance
```

Until then:

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
