# P3-R1 signed recovery authorization validation plan

## Scope

Validate Architecture 96, which replaces caller-asserted P3-R1 deployment/operator
expectations with a signed, domain-separated, post-build recovery authorization.

This checkpoint is source/test/release-procedure validation only. It does not
authorize production recovery, rerunning the original publisher, deleting or
repairing staging, provider call #7, P4, brokerage activity, or live trading.

Implementation commit `2b82222fbaee857e02519a0ea3627679d309276d` is retained but
remains correction-required until this plan passes.

## A. Startup and workflow gate

Before Codex reads or modifies source, require exact:

```text
worktree = F:\AI\worktrees\ai-trading-bot-p3-r1
branch   = feature/p3-r1-recovery-implementation
HEAD     = <exact checkpoint supplied by ChatGPT>
```

Run:

```text
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
```

Any mismatch is a stop condition. Codex must not self-correct by switching,
resetting, rebasing, moving/creating/deleting worktrees, or modifying files.

Every Windows pytest command uses a fresh external basetemp beneath
`F:\AI\temp\pytest\...`; when cache behavior is not under test, use
`-p no:cacheprovider`. Do not use the default `%TEMP%` pytest root and do not
repair historical `.pytest_cache`/pytest temp directories to make a gate pass.

## B. Authorization schema gate

Require one exact canonical schema for
`p3-r1-recovery-authorization/v1`.

Tests must reject:

- duplicate or unknown fields;
- missing fields;
- non-canonical JSON/serialization;
- non-canonical UUID/SID/digest/path text;
- alternate production/staging path spellings;
- optional caller policy, replacement, cleanup, resume, retry, or new-account
  fields.

The schema must bind the exact incident plus accepted source/release identities,
including source commit/tree, wheel SHA-256/length, installed RECORD
SHA-256/length, exact Administrator SID, C1 machine/Trading/bootstrap identity,
Paper account/genesis identity, authority DB identity, and fixed Paper roots.

## C. Signature and domain-separation gate

Use a dedicated P3-R1 verifier over the source-pinned production P-256 public
trust material.

Require:

- valid recovery authorization/signature -> PASS;
- unsigned artifact -> reject;
- one-byte authorization mutation -> reject;
- signature mutation -> reject;
- wrong key identifier/key -> reject;
- bootstrap signature supplied as recovery signature -> reject;
- recovery signature supplied to bootstrap validation -> reject;
- alternate signing domain -> reject.

The recovery verifier must not route recovery bytes through the bootstrap parser.
Private signing material remains external to the repository/runtime.

## D. Non-circular release binding gate

Prove the expected lifecycle:

```text
accepted source commit/tree
-> isolated exact source export
-> offline wheel build
-> wheel/package/RECORD reconciliation
-> freeze wheel + expected installed RECORD identity
-> construct canonical recovery authorization
-> detached recovery-domain signature
-> independent signature verification
-> sealed-runtime deployment
-> installed RECORD/payload reconciliation
```

No source constant may predict the wheel/RECORD digest produced from that same
source. Caller-provided post-build digests alone must never authorize mutation.

## E. Exact operator gate

Before Paper staging access:

- current token is elevated Administrator;
- actual current-token SID equals the signed exact Administrator operator SID;
- another elevated Administrator SID is rejected;
- non-elevated/admin-state mismatch is rejected;
- caller-supplied SID values outside the signed artifact have no authority.

Tests should mock only the native identity primitive necessary to prove these
branches; no real production mutation is performed.

## F. Installed release reconciliation gate

Before Paper staging access, require:

- exact sealed runtime executable and source location;
- actual installed RECORD SHA-256/length equals signed authorization;
- strict RECORD paths: no duplicates, absolute paths, traversal, malformed
  separators, or unsupported entries;
- every recovery-relevant package payload is hashed and matches RECORD;
- imported `trading_bot` modules resolve only from the reconciled sealed package;
- unlisted/unhashed/modified payloads block;
- accepted C1 identity and authority DB remain exact.

The signed wheel digest is release/deployment evidence. Recovery runtime directly
proves the signed installed RECORD identity and complete relevant installed
payload reconciliation.

## G. Process-local permit gate

Successful signed-authorization validation issues one private process-local
permit.

Prove:

- public construction fails;
- field reconstruction fails;
- wrong concrete type fails;
- assignment/deletion fails;
- pickle/serialization fails;
- test provenance cannot substitute for production provenance unless a clearly
  named test-only boundary is used;
- native recovery mutation requires the permit directly;
- raw canonical bytes, signature bytes, parsed model, SID, hashes, or paths
  cannot substitute for the permit.

## H. P3-R1 regression gate

All accepted Architecture-95 behavior remains mandatory:

- descendant handles close before root rename;
- any uncertain descendant close blocks before mutation and is not retried;
- retained parent/root revalidated immediately before rename;
- final still absent immediately before rename;
- one absolute no-replace retained-root `FileRenameInfo` call;
- mutation marker immediately before native rename;
- retained-root exact final-path proof immediately after success;
- final/staging namespace proof;
- final descendants reopen read-only;
- exact pre/post native identity equality;
- complete final ACL/inventory/bytes/canonical genesis/anchor verification;
- authority DB before/after equality;
- conservative ambiguous/published-candidate classifications;
- no cleanup, reverse rename, replacement, implicit retry, or new account ID;
- ordinary publisher rejects retained staging and cannot invoke recovery.

## I. Native disposable scratch gate

The opt-in native regression must use pytest `tmp_path`/`tmp_path_factory` or an
explicit disposable root supplied by the test harness.

It must not intentionally create scratch under the worktree `.pytest_cache`.
Local execution uses a fresh path such as:

```text
F:\AI\temp\pytest\p3-r1-native-rename-v1
```

and must prove the scratch root is outside both production Paper paths before
creating anything.

Required native behavior remains:

```text
retained descendant -> ERROR_ACCESS_DENIED
close descendant     -> absolute root rename PASS
retained root path    -> exact intended final path
```

## J. No-effect gate

Focused/fake/native-disposable tests must prove or structurally guarantee:

```text
PROVIDER_CALL_PERFORMED=False
PROVIDER_CALL_7_AUTHORIZED=False
CREDENTIAL_MANAGER_READ=False
BROKER_OPERATION_PERFORMED=False
PAPER_TRANSITION_MUTATION=False
P4_PRODUCTION_EXECUTION=False
PRODUCTION_PAPER_PATH_MUTATION=False
```

## K. Test usage gate

During correction, run focused tests only. Every Windows invocation must include
a fresh external `--basetemp` and normally `-p no:cacheprovider`.

Do not run the full repository suite until ChatGPT accepts the corrected exact
diff as the final source candidate. After exact-diff acceptance, run one broad
source-certification suite on another fresh external basetemp.

Ruff check, Ruff format check, and `git diff --check` remain required for changed
files.

## L. Release and production gate

After corrected source certification:

```text
exact release wheel freeze
-> wheel/package/RECORD reconciliation
-> collect exact elevated Administrator SID
-> construct canonical P3-R1 authorization
-> sign dedicated recovery domain
-> independently verify/freeze authorization evidence
-> sealed-runtime deployment of exactly authorized wheel
-> installed RECORD/payload reconciliation
-> read-only retained-staging revalidation
-> explicit one-time operator approval
-> Administrator P3-R1 recovery
-> close Administrator shell
-> non-admin Trading P3 acceptance
```

A signed artifact is not by itself permission to run the production recovery;
explicit operator approval remains a separate gate.

## M. Non-authorizations

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
