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
