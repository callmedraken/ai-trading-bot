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
- a lock-scoped mutation-admission proof cannot be reused after lock release.

Ordinary tests must not depend on a global Windows object. Native Windows tests
remain explicit opt-in.

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
