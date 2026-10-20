# Architecture 134-F2 — five-session soak protected readiness validation plan

Status: **DESIGN FROZEN; source implementation is next.**

This plan validates the read-only F2 readiness checkpoint defined by
`docs/architecture/134-f2-five-session-live-paper-soak-readiness.md`.

No source test, CI job, or F2 preflight may reserve F1 authority, create/run a
scheduled task, read credentials, contact Alpaca/Robinhood, invoke D1R7/D1R8,
write production SQLite, mutate paper/session state, or place a broker/live order.

## Starting identities

Design predecessor:

```text
develop HEAD 71c147b2fd21994f5af81e5ce685974183370d0d
develop TREE 9568290b4d587b838d9cbd08f33d1ea86005143a
```

Accepted operational F1:

```text
HEAD b59ad3b44540a55a30f612d5c4e3e38e26a95b02
TREE e8a94e3512d7950f2fbc9c4d102a58b63e03244f
```

F2 implementation branch/worktree:

```text
feature/robinhood-production-paper-134f2-five-session-soak-readiness
F:\AI\worktrees\ai-trading-bot-production-paper-134f2-five-session-soak-readiness
```

Checkpoint:

`arch134-f2-five-session-soak-readiness`

## Source admission tests

Use fake/local disposable repositories and subprocess fakes. Prove READY requires:

- exact F1 worktree path/branch/HEAD/TREE;
- exact D1R7 and D1R8 worktree paths/branches/HEAD/TREE;
- exact origin fetch/push URL;
- exact upstream remote refs;
- clean tracked/index/untracked state;
- one common expected worktree registry;
- exact read-only `ls-remote` branch tips.

Mutation cases include wrong branch, wrong HEAD, wrong tree, dirty tracked file,
staged file, untracked file, wrong origin, wrong push URL, wrong upstream, remote
tip drift, missing worktree, extra/mismatched registry and path redirection.

Statically prove the F2 implementation invokes no mutating Git verbs including:

```text
fetch pull checkout switch reset merge rebase clean add commit push branch update-ref
```

## Frozen F1 blob tests

Pin and verify the seven accepted F1 operational blobs from the architecture
contract. A one-byte drift in any blob blocks readiness.

F2 tests must also prove no accepted F1 operational file is modified by the F2
source checkpoint.

## Parent namespace tests

Using disposable qualification roots, cover:

- clean absent parent/children/claims/locks -> eligible for continued checks;
- parent journal present and active -> BLOCKED;
- parent journal present and FINAL -> BLOCKED;
- malformed parent bytes -> still BLOCKED by existence, without repair;
- child journal without parent -> BLOCKED;
- D1R7/D1R8 child claim without parent -> BLOCKED;
- scheduler create/run claim without parent -> BLOCKED;
- unexpected F1 lock artifact -> BLOCKED.

The preflight must never call F1 `Journal.reserve`, `exclusive`, `lock`, or
append methods. Source/AST tests must enforce that no authority file can be
created or changed.

## Predecessor evidence tests

Using bounded synthetic copies matching the accepted D1R5/D1R6 contracts, prove:

- exact accepted predecessor pair passes;
- wrong bytes/digest/schema/source/session/final state blocks;
- missing or unreadable evidence blocks;
- evidence redirection/reparse ambiguity blocks;
- no D1R7 publication function is invoked;
- no evidence repair/delete/overwrite path exists.

## Runtime tests

Mock the accepted read-only runtime inspection and prove:

- `PRESENT_COMPATIBLE` passes;
- `ABSENT` blocks;
- `BLOCKED` blocks;
- exception/unknown status blocks;
- bounded paper/session counts are retained only as sanitized data;
- write-readiness remains exactly `NOT_CHECKED`;
- credential/provider readiness remains exactly `NOT_CHECKED`.

Statically forbid calls to runtime provisioning, rollback/write-readiness
qualification, writable SQLite connect modes, store initialization/migration or
repair.

## Scheduler tests

Mock the fixed accepted scheduler script.

Prove F2 sends exactly:

```text
-Mode Observe
```

and accepts READY only from exact canonical `{"status":"ABSENT"}`.

Prove `MATCH`, `CREATED`, `STARTED`, `BLOCKED`, malformed JSON, native
stderr/exit ambiguity, timeout and COM/unavailable state all block.

Static source checks must prove F2 contains no Create/Run mode invocation,
RegisterTaskDefinition, Task.Run, task update/delete, scheduler claim creation or
PowerShell mutation command.

## Window preview tests

With fake aware clocks and published session authority, cover:

- current published session before close-minus-five;
- after cutoff;
- weekend;
- holiday;
- early close;
- DST transitions.

Exactly five ordered published regular sessions must be reported.

Changing the preview timestamp may change preview targets and must not alter any
identity or durable state. No test may treat preview dates as authorization.

## Final-readmission race tests

Arrange drift after the first successful observation and before return:

- F1 source moves/gets dirty;
- D1R7/D1R8 source moves;
- parent/child/claim artifact appears;
- runtime becomes incompatible;
- scheduler changes from ABSENT;
- predecessor evidence changes.

Every case must return BLOCKED. No retry loop or repair is allowed.

## Capability/effect tests

Instrument or statically prove F2 cannot reach:

- Credential Manager or OAuth secret readers;
- Alpaca/Robinhood transports;
- D1R7 `publish_prerequisite`;
- D1R8 `run_session`;
- F1 `authorize`, `supervise`, `Journal.reserve`, append, lock or exclusive;
- runtime write-readiness/provisioning;
- paper/session write stores;
- scheduler Create/Run/update/delete;
- broker/D2/promotion/live surfaces.

The positive preflight evidence must report the zero-effect fields frozen in the
architecture contract.

Allowed observations are bounded filesystem reads, read-only Git commands,
read-only production SQLite inspection, predecessor evidence reads and scheduler
Observe.

## Result-schema tests

Require exact closed fields and sanitized enums. At minimum bind:

```text
schema
status
observed_at
f2_source_head
f2_source_tree
f1_source_head
f1_source_tree
d1r7_source_head
d1r7_source_tree
d1r8_source_head
d1r8_source_tree
f1_source_status
predecessor_status
runtime_status
paper_records
session_reservations
runtime_write_readiness
credential_readiness
provider_readiness
parent_slot_status
child_artifact_count
claim_artifact_count
lock_artifact_count
scheduler_status
preview_targets
effects
```

Unknown/missing/alternate fields or noncanonical timestamp/date/count/status
representations fail closed.

No raw paths other than reviewed fixed contract paths, native exception strings,
SIDs, credential metadata, tokens, account identifiers, provider bodies or
environment data may appear in evidence.

## Runner/checkpoint tests

Register F2 exactly once with:

```text
remote_branch feature/robinhood-production-paper-134f2-five-session-soak-readiness
preflight     <F2 read-only callback>
execute       None
CI profile    robinhood
```

Prove:

- existing F1 checkpoint remains `preflight=None`, `execute=None`;
- F1 accepted source/profile pins remain unchanged;
- F2 branch is already admitted by `feature/robinhood-*`;
- `ops.ps1 verify arch134-f2-five-session-soak-readiness` is source-only;
- `ops.ps1 preflight arch134-f2-five-session-soak-readiness` appears only after
  registration and uses the runner's clean/exact-source admission;
- no `ops.ps1 execute` choice exists for F2.

## Focused verification

During implementation use fresh external pytest basetemps and run only the
affected F2/F1/checkpoint/current-inventory tests.

Run both non-mutating Ruff phases and `git diff --check`.

Use the registered source verification surface before publication:

```powershell
.\ops.ps1 verify arch134-f2-five-session-soak-readiness
```

Do **not** run the real F2 preflight against the host during source
implementation. Host preflight is a post-source-acceptance protected-readiness
observation.

Do not run local ROBINHOOD or FULL. The mapped terminal feature push owns
canonical ROBINHOOD.

## One-publication rule

Compose the complete source, tests, runner registration/profile mapping,
current-inventory/pin/timing updates and truthful status/handoff changes before
publication.

Then exactly:

```text
focused/local source verification
-> one atomic commit
-> one ordinary feature-branch push
-> one push-triggered source gate
-> terminal active + canonical ROBINHOOD
-> ChatGPT exact-source review
```

A terminal failure ends the attempt. Never rerun unchanged CI. Any bounded
replacement is a separately declared corrective checkpoint under the standing
workflow.

## Acceptance and next boundary

F2 source acceptance authorizes only a separately invoked read-only F2 preflight.

A preflight PASS still grants no F1 authorization. ChatGPT must review the
preserved preflight evidence before providing any exact interactive F1
authorization command.

Any BLOCKED/ambiguous preflight result is a STOP with no automatic repair or
retry.

Real-money trading remains **NO-GO**.
