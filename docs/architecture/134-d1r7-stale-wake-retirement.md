# Architecture 134-D1R7 - exact stale one-shot wake retirement

Status: source implementation, pending exact GitHub review. This grants no host
execution authority. The real stale task is preserved throughout implementation.

## Source and incident admission

Branch: `feature/robinhood-production-paper-stale-wake-retirement`.
Worktree: `F:\AI\worktrees\ai-trading-bot-production-paper-stale-wake-retirement`.
Canonical parent HEAD `a36de3bfe81a6e1a94fb3deeec7e579145939f52`,
TREE `6cde732e02e92eb2b34281672cdb7744250355b1`.
Accepted R3 executable/test source is `e6defea5aa7b9266f78c7d2f22ebac90bf568dd7` /
`f9ad06c9b26beb681ceb3429fd66452e4aef88a9`, CI #572 / 38737407813.

D1R7 requires explicit expected HEAD/tree, exact own path, branch, origin,
tracking and live remote equality, clean index/tracked/untracked source, registered
worktrees and imports exclusively from its own src. It descends from the canonical
parent. D1R5 remains exact at HEAD `7aa54bb618f63bfb2b470ff8fc88ba8d27ef9343`,
TREE `c826c2a71e6d907866ce3f80afce479d38ab7842`, on its existing qualification
branch/worktree. The old live D1R6 worktree stays clean on
`feature/robinhood-production-paper-overnight-wake-arming` at HEAD
`3cf4284d017e362eee58a2f27526ab4de8f292a2`, TREE
`16a48a12756bb6d810799444859334ce6305001d`. Its remote intentionally advanced;
no remote equality or synchronization is required for that frozen predecessor.

All source/target/frozen identity checks, qualification parent safety, consumed
incident parsing, absence checks and principal/task observations repeat immediately
before durable delete intent. The evidence parent is the existing fixed external
`F:\AI\temp\qualification`; no directory/ACL provisioning is available.

The immutable consumed D1R6 journal is exactly:

```text
arch134-d1r6-2026-10-15-7aa54bb618f63bfb2b470ff8fc88ba8d27ef9343-3cf4284d017e362eee58a2f27526ab4de8f292a2-16a48a12756bb6d810799444859334ce6305001d.jsonl
16917 bytes
b62959f9988dcc42e4881e45ed95abcf4abc2b6d2932514c7253165e1223955c
```

Reuse R3 public `read_consumed_predecessor`: exact name, regular single-link file,
no reparse point, size/SHA and canonical seven events ending
TASK_CREATE_RETURNED -> FINAL/INDETERMINATE, one consumed create, zero effects,
reconstructed source/target/session/facts. Never write or relabel this journal.
Require no original launch fence, no D1R5 result, no recovery artifact and no
competing same-session arm. Require current principal name/SID equal consumed plan.

## Closed native authority

Runtime CLI modes are only `preflight`, `retire`, `reconcile`. Only retire accepts
`--retire AUTHORIZE_ARCH134_D1R7_ONE_STALE_WAKE_RETIREMENT`.
Preflight is entirely read only; RETIREMENT_READY grants no effect authority.

Dedicated PowerShell modes are only Observe and Delete. Observe returns the
current principal and fixed-task observation; no separate principal mode is needed.
Binary stdin is canonical JSON plus one raw LF and EOF. Native argv is the fixed
PowerShell executable with `-NoProfile -NonInteractive -ExecutionPolicy Bypass
-File`, fixed helper and mode. No shell/environment/policy/path overrides or
structured command-line payloads. Output is bounded and duplicate fields rejected.
Delete input contains only the literal interlock. The helper independently reads\nthe fixed incident file with a bounded read and exact 16917-byte/SHA fence,\nextracts its frozen principal, and requires the current identity to match it.\nIt repeats that incident/principal check immediately before the task observation.

R3 boundary conversion functions are copied exactly: explicit-offset instants
normalize to UTC seconds, fractional drift fails, principal resolves to canonical
SID, and zero durations normalize as in R3. All remaining fields match the frozen
plan exactly. Additional fingerprint: state 3/READY, LastTaskResult 2,
LastRunTime wall text `2026-10-15T06:20:00` in Windows Pacific Standard Time,
NextRunTime exactly COM no-run sentinel 1899-12-30 midnight projected as null.
A different next run, even historical, blocks. Only the fixed task path
`\AITradingBot-Arch134-D1R6-OvernightWake-v1` can be observed/deleted.

Immediately before the sole `.DeleteTask(...)`, the helper independently observes
this entire frozen task/state fingerprint and current principal again. It accepts
no caller task name, folder, XML, action, expected task dictionary or command.
Mismatch returns NOT_CALLED/deletion_attempts=0. Set native attempted flag directly
before DeleteTask; return CALL_RETURNED/deletion_attempts=1 on return. A post-entry
exception returns INDETERMINATE/deletion_attempts=1. There is exactly one DeleteTask
site, zero RegisterTaskDefinition/Run/Stop/NewTask/Create sites, and no update mode.

## Durable authority and reconciliation

Schema: `arch134-d1r7-stale-wake-retirement/v1`. Fixed external journal:
`arch134-d1r7-stale-wake-retirement-2026-10-15.jsonl`. Its identity deliberately
excludes the current source revision: a different revision cannot reset the budget.
Any matching retirement candidate blocks preflight; exclusive xb reservation makes
concurrent attempts consume the same destination. No retry, repair or cleanup.

```text
RETIREMENT_RESERVED
D1R7_SOURCE_ADMITTED
D1R5_TARGET_ADMITTED
CONSUMED_INCIDENT_ADMITTED
STALE_TASK_CONFIRMED
TASK_DELETE_INTENT
TASK_DELETE_RETURNED
TASK_ABSENCE_CONFIRMED
FINAL / RETIRED
```

Each canonical LF record binds current source, entire original plan, incident
name/size/SHA, closed budgets, all zero non-delete effects, delete_budget_consumed
and deletion_attempts. Intent sets consumed=1 with unknown native attempt count;
returned sets attempts=1. Proven NOT_CALLED permits FINAL/BLOCKED with attempts=0
but leaves the durable budget consumed and destination permanently reserved.
Pre-intent failure is BLOCKED. Process-entry uncertainty is INDETERMINATE.

Every record is written, flushed and fsynced before progressing. Mark intent
uncertainty before attempting its write. Never retry journal IO after write,
flush or fsync ambiguity, even when complete bytes are visible. Close/reread
ambiguity after intent also returns INDETERMINATE. Existing partial files block
future deletes. Where safe, append FINAL/INDETERMINATE after intent ambiguity;
never append following an IO durability failure.

Only exact CALL_RETURNED/1 followed by two independently exact ABSENT observations
permits absence confirmation. Re-admit all nonscheduler authorities afterward,
then append FINAL/RETIRED, close and independently bounded-reread/parse. Any task
reappearance or uncertainty consumes the attempt and stops. Task replacement races
cannot be made transactional with COM; observation is repeated at the native
boundary and any post-call uncertainty is non-retryable.

Read-only reconcile requires exact current source, complete canonical matching
journal FINAL/RETIRED with one consumed/returned delete, actual fixed-task absence,
unchanged original incident and no launch/result/recovery. Absence alone never
confers PASS. INDETERMINATE remains STOP even if absent; later read-only review is
required, and no second delete is available. No automatic recreation or rollback.

## Effect budgets and source gate

```text
TASK_DELETE_BUDGET=1
TASK_CREATE_BUDGET=0
TASK_UPDATE_BUDGET=0
TASK_RUN_BUDGET=0
D1R5_EXECUTION_BUDGET=0
D1_OPERATIONS=0
D2_OPERATIONS=0
LIVE_EFFECTS=0
```

Zero credential/provider/Robinhood/strategy/PREPARE/EXECUTE/paper/broker/
production-SQLite/ACL effects. No D1R5 child/process seam exists. D1R6 executable
source and all D1R5 artifacts stay frozen; the D1R6 test changes only inventory
expectations. A closed successor test-pin overlay preserves predecessor pin maps.
The dedicated source checkpoint maps to ROBINHOOD, with no protected runner hooks.
Frozen workflow branch-family admission already covers the new branch; workflow
bytes/topology stay unchanged. Recomputed inventory: FULL 177, ROBINHOOD 100,
LEGACY 215, EXHAUSTIVE 392. Exactly one new owned test module, no baseline changes.

After focused checks, exact-file commit and ordinary push, require attempt-1
source-static/active-tests/certification-tests (ROBINHOOD)/source-gates SUCCESS,
full-tests SKIPPED, canonical wall <300 seconds. Stop for ChatGPT exact GitHub
review. Status/handoff remain current accepted-state authority pending acceptance.
No real scheduler observation, preflight, retirement, task run, D1R5 invocation or
qualification evidence creation is authorized by this source checkpoint.
