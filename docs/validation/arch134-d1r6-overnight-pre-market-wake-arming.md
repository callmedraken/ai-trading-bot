# Architecture 134-D1R6 validation

Contract: ../architecture/134-d1r6-overnight-pre-market-wake-arming.md.
Source implementation only. No real host preflight, scheduler observation or
mutation, D1R5 invocation, real clock sleep or qualification evidence is allowed.

Focused tests use fake Git/clock/principal/scheduler/child seams and disposable
external pytest basetemp, no cache. Cover DST/holidays/early closes/18-hour
boundaries, canonical closed evidence including prefixes/collisions/size/types,
exact task/action/principal/settings, durable intent before one fake create,
ambiguous entry and stable readback, both sources and mixed import rejection,
preflight zero writes, exact one child delegation, unchanged D1R5 parsing and
all reconciliation dispositions. Static closure forbids operational imports,
generic execution and scheduler effects beyond one fixed COM registration.

Run new D1R6, frozen D1R5, NYSE calendar, affected runner/profile/lane and
Architecture-134 authority modules. Run both Ruff check and format check on
touched Python (emit non-mutating diffs on either failure), then git diff --check.
Do not run a local broad certification. Mapped CI owns ROBINHOOD; require
source-static, active-tests, certification-tests and terminal source-gates
SUCCESS on the exact pushed HEAD, attempt 1, certification wall <300 seconds.
On CI failure preserve evidence and STOP, with no rerun/amend.

All real implementation/test/CI counters must equal zero:
PRODUCTION_SQLITE_READS, PRODUCTION_SQLITE_WRITES, CREDENTIAL_READS,
CREDENTIAL_WRITES, PROVIDER_CALLS, ROBINHOOD_READS, ROBINHOOD_REVIEWS,
PAPER_MUTATIONS, BROKER_PLACEMENTS, STRATEGY_EVALUATIONS, PREPARE_ATTEMPTS,
EXECUTE_ATTEMPTS, ACL_MUTATIONS, REAL_SCHEDULER_READS,
REAL_SCHEDULER_MUTATIONS, REAL_TASK_RUNS, REAL_D1R5_EXECUTIONS,
REAL_CLOCK_SLEEPS, D1_OPERATIONS, D2_OPERATIONS, LIVE_EFFECTS.
Fake creates and temporary evidence are allowed. Future separately authorized
arm permits SCHEDULER_TASK_CREATE_CALLS <=1 with zero trading/provider effects.

After source CI report exact parent/HEAD/tree/paths/blobs, frozen predecessors,
overlay/resolvers/digests, inventories, focused counts and CI evidence, then
STOP. ChatGPT owns exact GitHub acceptance. Later real read-only preflight,
one protected arm, unattended D1R5 and morning read-only reconciliation each
remain separately reviewed boundaries; none is run by this checkpoint.

## D1R6R1 process-scoped transport regression

The reported real-host preflight passed Git/source admission and then failed
before principal/scheduler observation: default Windows PowerShell policy blocked
the fixed helper. No scheduler mutation or D1R5 invocation occurred. Correct
only the fixed child-process `-ExecutionPolicy Bypass` tokens, on both the
Python-to-helper argv and Task-Scheduler-to-launcher action. No persistent policy
mutation (including Set-ExecutionPolicy), registry/Group Policy change,
environment policy override or profile edit is authorized.

Mock all three scheduler transport modes and assert the complete fixed argv,
including the exact executable, policy case, script and mode. Assert the exact
scheduled action string independently and statically match the PowerShell
creator to it. Reject caller policy/script selection and assert the creator
contains no Set-ExecutionPolicy and exactly one TASK_CREATE registration call.
Retain all existing no-retry, scheduler and trading-authority closure tests.
Use PowerShell syntax parsing only; never invoke the real scheduler helper.

The existing D1R6 checkpoint and ROBINHOOD mapping remain unchanged. Refresh only
the six genuinely changed D1R6 source/script/test/doc pins. Inventory remains
FULL 176 / ROBINHOOD 99 / LEGACY 215 / EXHAUSTIVE 391. Focused D1R6, frozen D1R5,
NYSE, runner, profile/lane and predecessor authority checks precede exact-file
commit/push. Require attempt-1 static/active/canonical/terminal CI SUCCESS,
full-tests SKIPPED and canonical wall <300 seconds, then stop for ChatGPT review.
REAL_D1R6_PREFLIGHTS, REAL_SCHEDULER_MUTATIONS, REAL_TASK_RUNS and
REAL_D1R5_EXECUTIONS remain zero during this correction. Do not rerun preflight
or arm the scheduler after publication. PROJECT_STATUS and HANDOFF are reserved
for post-acceptance closeout.

## D1R6R2 binary stdin regression

Reported diagnosis: R1 solved script execution policy; text-mode Principal still
returned NOT_CALLED / registration_attempts=0. The identical fixed helper/argv
with raw LF stdin returned the valid current Windows principal, identifying
Python text-mode newline translation as the cause. Scheduler/D1R5/qualification-
evidence effects remained zero. This source correction repeats no real probe.

All three mocked modes must preserve exact R1 argv and assert bytes-only stdin:
Principal/Observe `b"{}\n"`; Create exact sorted compact canonical request bytes
plus one LF. Reject text/encoding/errors/environment/universal-newline/shell
transport options; restoring text=True or str input must fail regression tests.
Mock stdout as bytes, prove ordinary CRLF JSON output works unchanged, and test
the raw 16,384-byte output bound. Keep the PowerShell helper's strict LF/EOF
request parsing and its accepted blob unchanged. Syntax parsing is permitted;
executing Principal/Observe/Create or real preflight is forbidden.

Only the host, existing D1R6 test module, these two docs and four associated
D1R6 source pins change. Inventory/checkpoint mapping and all R1 scheduled-
action/launcher, D1R5 and workflow blobs stay frozen. Follow the existing focused
checks and attempt-1 mapped CI gate, then stop for ChatGPT exact source review.


## D1R6R3 incident recovery source verification

Use the existing D1R6 module only. Synthetic external temporary evidence uses
explicit test-only byte/hash pins; it never reads or writes the real incident.
Separately assert every production incident pin literally. Modeled native
projection fixtures cover both equivalent offsets, both boundaries, John/SID,
malformed/offset-less/nonintegral timestamps and unresolvable accounts. Static
conversion assertions anchor the actual PowerShell algorithms; parser syntax
validation must not invoke any helper statements or real Principal/Observe/Create.

Cover exact seven-record consumption and reject name/size/hash/link/type/event/
count/classification/session/source/target/fact/effect/budget drift. Require every
recovery-ready predicate individually. Assert no scheduler create or child entry
in preflight/recovery, interlock exactness, two final observations/readmissions,
deterministic separate xb path, flush/fsync/reread validation, second recovery
rejection and consumed write/flush/fsync/close/reread/parse ambiguity. The original
journal bytes remain unchanged throughout modeled recovery and launch.

Prove predecessor alone cannot launch; valid recovery delegates exactly once;
source/target/artifact/task/principal/result/fence drift blocks. Reconciliation
requires valid recovery and exact task but only canonical D1R5 evidence grants
PASS. Retain ordinary ARMED, launch fence, one-create/no-retry, fixed argv/raw-LF,
source-pins/inventory and all frozen D1R5 coverage. No new checkpoint/module or
workflow change. Inventory FULL 176 / ROBINHOOD 99 / LEGACY 215 / EXHAUSTIVE 391.

Run focused D1R6/D1R5/NYSE/runner/profile/lane/predecessor tests, combined Ruff
check/format diagnostics, PowerShell parser only and git diff --check. Commit
exactly the seven intended paths from the detached build and ordinary-push
HEAD explicitly after exact predecessor verification. Require exact-head attempt-1
source-static/active-tests/certification-tests (ROBINHOOD)/source-gates SUCCESS,
full-tests SKIPPED and canonical wall <300 seconds. No blind CI retry. Stop for
ChatGPT source review without live fast-forward or real recovery.

Implementation counters remain zero: REAL_D1R6_PREFLIGHTS, REAL_D1R6_ARMS,
REAL_RECOVERY_PREFLIGHTS, REAL_RECOVERY_EVIDENCE_WRITES, REAL_SCHEDULER_READS,
REAL_SCHEDULER_MUTATIONS, REAL_TASK_CREATE_ATTEMPTS, REAL_TASK_RUNS,
REAL_D1R5_EXECUTIONS, D1_OPERATIONS, D2_OPERATIONS and LIVE_EFFECTS.
