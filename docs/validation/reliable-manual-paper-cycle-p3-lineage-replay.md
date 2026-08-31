# Architecture 94 P3 lineage replay validation additions

## Status

This document is the focused P3 validation companion to
`docs/architecture/94-p3-lineage-replay-clarification.md`. It supplements the P3
section of `reliable-manual-paper-cycle-plan.md` and is required reading for P3
implementation.

P3 is routed to Codex Sol High. No provider call #7, credential access, network
request, broker operation, production paper mutation, or live operation is
authorized by this plan.

## Source gate

Before implementation, prove:

```text
worktree = F:\AI\ai-trading-bot-paper
branch = feature/reliable-manual-paper-cycle
upstream = origin/feature/reliable-manual-paper-cycle
HEAD = the accepted P3 clarification checkpoint
tracked worktree = clean
```

Stop before modification on mismatch. Preserve unrelated generated/untracked
artifacts and historical pytest/cache directories. Do not use the GUI worktree.

## Historical snapshot replay tests

Using disposable paper roots and explicit disposable production-authority seams,
cover at least:

- genesis-only account requires no historical snapshot dependency and verifies
  to the anchored genesis tip;
- one valid transition derives its snapshot only from the report's canonical
  `request.snapshot_reference`;
- multiple valid transitions derive the complete ordered snapshot dependency
  set and pass full-lineage verification;
- the derived C3-v1 filename is exactly
  `daily-market-data-snapshot-<snapshot-id>.json` under the fixed capture-output
  root;
- no capture-output directory scan or fallback path is performed;
- report snapshot ID, SHA-256, or byte-length tampering blocks;
- missing historical snapshot blocks;
- wrong snapshot bytes at the canonical path block;
- strict daily-snapshot verification failure blocks;
- snapshot ID mismatch after verification blocks;
- symlink/reparse/device/unsafe-object substitution blocks;
- file-identity instability across the bounded read blocks;
- an unrelated extra snapshot in capture-output is ignored and cannot become a
  dependency;
- historical replay does not query the C3 selection database and cannot issue a
  P2 permit;
- provider, Credential Manager, child-launch, and network paths are unreachable.

## Fixed-root and anchor tests

Cover:

- production construction requires genuine `ValidatedProductionAuthority`;
- production root is fixed to `F:\AITradingBot\Paper`;
- caller-selected production roots are rejected/unavailable;
- disposable roots require an explicit test-only seam;
- canonical anchor schema is exactly `manual-paper-account-authority/v1`;
- anchor accepts one exact canonical UUID `paper_account_id` and binds exact
  machine-authority ID, approved Trading SID, genesis checkpoint ID, genesis
  SHA-256, and genesis byte length;
- authority epoch, provider ID, credential version, path, mtime, and wall clock
  do not enter anchor identity material;
- unknown/missing/duplicate/noncanonical anchor fields block;
- missing anchor blocks;
- alternate or mutated genesis blocks;
- anchor genesis evidence mismatch blocks;
- root/anchor/genesis owner/DACL/inheritance/object/reparse validation blocks on
  unsafe state;
- production preflight cannot create, overwrite, repair, or replace the anchor;
- the P3 public authority/evidence does not expose the underlying C1 capability
  or provider/C2/C3 mutation methods.

Do not weaken or widen the existing C1 `F:\AITradingBot\Authority` path guards.
If implementation appears to require that, stop for architecture review.

## Inventory and graph-completeness tests

Cover:

- exact anchored genesis directory/file layout;
- exact finalized transition directory naming and exactly two expected files;
- unique terminal is graph-derived, not caller-supplied;
- filename, UUID, timestamp, mtime, and directory enumeration order do not select
  the tip;
- one and multiple valid successor transitions produce the expected unique tip;
- fork from one predecessor blocks;
- competing successors block;
- disconnected alternate genesis blocks;
- cycle/reuse conflicts block;
- report reuse or application-ID conflict blocks;
- malformed recognized transition blocks;
- transition staging remnants block;
- receipt staging/unsafe recognized operation state blocks according to the
  existing fail-closed Architecture-67 classification and is never repaired;
- case-fold collision blocks;
- enumeration bound exceeded blocks;
- unknown root state that cannot be safely classified blocks;
- every recognized finalized transition must be consumed by the one verified
  anchored lineage;
- a valid anchored chain plus one unused recognized transition blocks rather
  than silently ignoring the extra transition;
- the explicit artifact set passed to `verify_paper_account_lineage(...)`
  contains exactly the anchored genesis, all recognized successor/report
  artifacts, and all exact derived historical snapshot artifacts;
- full-lineage PASS evidence cardinalities reconcile exactly with the inventory.

P3 must use existing public parsers/verifiers. It must not import another
module's private helper or redefine Architecture-63/66 verification semantics.

## Finalized receipt audit-namespace tests

P3 structurally validates the known `paper-operations` namespace without granting
receipt authority. Cover:

- genesis-only account plus empty `paper-operations` passes;
- a valid transition chain plus a canonical finalized `COMPLETED` receipt passes
  with the same graph-derived tip, even without its external verifier dependencies;
- a valid transition chain plus a canonical finalized `FAILED` receipt passes
  with the same graph-derived tip, even without its external verifier dependencies;
- adding/removing valid finalized receipts leaves complete lineage evidence,
  `VerifiedPriorCheckpoint`, and terminal-tip evidence unchanged;
- P3 never calls `verify_paper_operation_receipt(...)`, requires receipt verifier
  dependencies, infers caller-key conflicts, or adds receipts to lineage artifacts;
- receipt staging, malformed/noncanonical bytes, directory/file/embedded operation
  identity mismatches, and extra receipt-directory contents block;
- unsafe/reparse/device receipt objects, unstable identities, case-fold collisions,
  unexpected audit-namespace contents, and enumeration overflow block.

Retain the unchanged Architecture-67 inspection/recovery regression gate, including
`FOREIGN_RECEIPT_DEPENDENCIES_UNAVAILABLE` when exact operation-specific receipt
authority actually requires unavailable dependencies. Structural P3 acceptance
does not establish that authority.

Record these focused classifications:

```text
FINALIZED_RECEIPTS_NONAUTHORITATIVE=PASS
RECEIPT_STAGING_FAIL_CLOSED=PASS
GRAPH_TIP_INDEPENDENT_OF_RECEIPTS=PASS
```

## Mutex tests

The paper mutex is separate from the C2 lifecycle mutex identity.

Cover pure identity material and, in opt-in Windows tests, native behavior:

- canonical label is `manual-paper-account/v1`;
- canonical mutex name starts with `Global\\AITradingBot-Paper-v1-` and the suffix
  is the lowercase SHA-256 of exact sorted-key compact JSON containing only
  label and canonical paper-account UUID;
- changed paper-account ID changes mutex identity;
- machine path, process ID, clock, Python hash, authority epoch, and C2 launch
  reservation do not affect mutex identity;
- exact protected DACL matches the reviewed lifecycle-mutex ACE policy;
- unexpected owner/DACL or unprotected descriptor blocks;
- one holder serializes a competing holder according to the chosen test seam;
- release/close occur exactly once;
- `WAIT_ABANDONED` is retained as explicit acquisition evidence;
- an abandoned acquisition cannot skip complete account revalidation;
- optional `expected` must exactly equal the complete pre-lock evidence before
  mutex acquisition;
- acquisition uses the pre-lock evidence's paper-account ID;
- complete post-acquisition evidence must exactly equal complete pre-lock
  evidence even when `locked_revalidate()` is called without `expected`;
- a valid successor published between the initial preflight and acquisition
  blocks default admission before any live scope is issued, for both ordinary
  and abandoned acquisition, and the mutex is released;
- changes to anchor, tip, lineage, historical dependencies, transition count,
  or any other retained P3 evidence block admission;
- a lock-scoped mutation-admission proof cannot be reused after lock release.

Ordinary tests must not depend on a global Windows object. Native Windows tests
remain explicit opt-in.

## Future P4 production output-security gate

P3 production validation requires exact reviewed Windows security on finalized
transition/receipt objects. Existing generic A67 helpers create transition
staging directories with `os.mkdir`, report/checkpoint files with ordinary
`os.open`/`O_CREAT`, `paper-operations` with `os.mkdir`, receipt staging
directories with `os.mkdir`, and receipt files with ordinary `os.open`/`O_CREAT`.
They do not supply the P3 Windows security descriptor. The protected,
non-inheriting P3 root/output policy therefore does not permit production P4 to
assume that calling those paths against `F:\AITradingBot\Paper` is sufficient.

Before P4 production mutation is implemented, ChatGPT/Sol must freeze and
separately review a narrow production object-creation seam for the existing A67
algorithm. Future native Windows tests must establish this sequence:

```text
A67 production creation seam
-> exact P3 ACL on staging
-> exact P3 ACL on finalized transition
-> exact P3 ACL on paper-operations/receipt
-> subsequent P3 preflight PASS
```

Cover exact reviewed descriptors at creation for all transition/receipt staging
directories and files and for `paper-operations` itself, descriptor preservation
through rename, and crash/recovery windows. Staging remnants must continue to
fail P3 closed; a subsequent P3 PASS requires a valid finalized state under the
unchanged A67 recovery rules, not automatic P3 cleanup or repair.

The separate review and tests must preserve generic/offline A67 callers,
deterministic schemas/identities, no-clobber ordering, staging/reread
verification, the transition commit point, the separate receipt commitment,
and recovery rules. Reject a duplicated commit algorithm, caller-selected
production root, process-token default DACL assumptions, ACL inheritance
assumptions under the non-inheriting policy, and ACL normalization/repair after
durable commit. No production P4 execution may be admitted before separate
review. If the seam cannot preserve A67 semantics, stop for ChatGPT architecture
review.

This correction freezes the prerequisite only: do not implement the seam,
change A67 source, weaken P3 object security, or run native production/P3
acceptance as part of this gate. Record the current correction separately from
future native acceptance:

```text
DEFAULT_LOCKED_TIP_DRIFT_BLOCKED=PASS
P4_OUTPUT_SECURITY_PREREQUISITE_FROZEN=PASS
```

## P3 output/evidence tests

A successful read-only P3 result must bind exact immutable nonsecret evidence:

- paper-account ID;
- machine-authority ID;
- approved Trading SID;
- anchored genesis ID/SHA-256/byte length;
- complete full-lineage evidence;
- terminal checkpoint ID/sequence/SHA-256/byte length;
- `VerifiedPriorCheckpoint` derived from that full-lineage result;
- recognized transition count;
- exact historical snapshot dependency IDs/SHA-256/byte lengths.

Cover forgery/lookalike/copy/serialization behavior appropriate to any
process-local P3 authority object. UUID/path/digest knowledge alone must not mint
production paper authority.

Public evidence must not contain credentials, provider bodies, raw native error
text, unbounded directory listings, or a C1 capability object.

## Negative effect boundary

P3 implementation/tests must prove that the P3 surface cannot:

- construct `WindowsEffectfulDailySnapshotCapture`;
- access Windows Credential Manager;
- allocate C2 attempts/claims/reservations/executions;
- mutate the C3 authority database;
- call Alpaca or any provider;
- execute strategy/risk/order/paper-cycle runtime;
- write/finalize a paper transition or receipt;
- provision the production paper root;
- choose a current C3 selection;
- perform provider call #7.

## Focused implementation gate

Codex should run focused tests only while implementing. Use fresh external pytest
scratch under `F:\AI`, for example:

```powershell
python -m pytest -q tests\runtime\test_manual_paper_account_authority.py --basetemp F:\AI\pytest-p3-account-authority
python -m pytest -q tests\runtime\test_windows_paper_account_mutex.py --basetemp F:\AI\pytest-p3-paper-mutex
```

If the final file names differ, report the exact equivalents. Do not run the full
repository suite.

Also run:

- directly affected Architecture-61/63/66/67 focused regression nodes;
- Ruff check on changed Python/test paths;
- Ruff format check on changed Python/test paths;
- `git diff --check`.

If the known worktree-local `.pytest_cache` lifecycle-arbiter problem affects a
required unchanged regression test, preserve the cache and use the documented
known-good harness + exact reviewed-source import-provenance method rather than
mutating historical scratch.

## Stop conditions

Stop and report an architecture blocker instead of implementing if P3 appears to
require:

- any Architecture-63/64/66/67 schema or semantic change;
- storing/copying historical snapshots into the paper root;
- changing production SQL;
- widening C1 fixed-root guards;
- provider/Credential Manager/network access;
- C3 selection mutation or historical P2 permit manufacture;
- a second paper transition/receipt commit algorithm;
- P4 composition, P5 CLI, provisioning, or production deployment;
- automatic cleanup/repair/retry of ambiguous state.

Expected focused completion classification:

```text
P3_FIXED_ROOT_ANCHOR=PASS
P3_HISTORICAL_SNAPSHOT_REPLAY=PASS
P3_GRAPH_DERIVED_TIP=PASS
P3_FULL_INVENTORY_LINEAGE_RECONCILIATION=PASS
P3_ACCOUNT_MUTEX=PASS
P3_EFFECT_BOUNDARY=PASS
P3_FOCUSED_SOURCE_GATE=PASS
```

No provider call #7 is authorized. Production/live trading remains NO-GO.
