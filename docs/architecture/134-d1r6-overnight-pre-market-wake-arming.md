# Architecture 134-D1R6 â€” overnight D1R5 wake arming

Status: frozen implementation contract; source review and every real host effect
remain pending. This checkpoint publishes source only. D1R5 remains unchanged.

## Source and predecessor

Base branch: feature/robinhood-production-paper-premarket-wake-qualification.
Base HEAD: 7aa54bb618f63bfb2b470ff8fc88ba8d27ef9343.
Base TREE: c826c2a71e6d907866ce3f80afce479d38ab7842.
Successor branch: feature/robinhood-production-paper-overnight-wake-arming.
Successor worktree: F:\AI\worktrees\ai-trading-bot-production-paper-overnight-wake-arming.
The external D1R5 target stays at the base identity in
F:\AI\worktrees\ai-trading-bot-production-paper-premarket-wake-qualification.
Both sources require exact local/tracking/live origin identity, exact branch,
clean tracked/untracked state, canonical worktree and unmixed package imports.
D1R6 identity is supplied explicitly for preflight/arm and recorded immutably;
launch/reconcile obtain it from the sole journal for the current source.
No remote movement is silently adopted.

Frozen predecessor blobs:

- pre_market_wake_qualification.py: c751590126453a51442ae10bbaf638f0a32c92b8
- pre_market_wake_qualification_host.py: 809da0dd5f1d0fbe5fea515e51b0b6af3497ac8a
- test_pre_market_wake_qualification.py: f6f4dfaf3b13e9d2d643ebf085b6ddacfbd168cd
- arch134-d1r5-pre-market-wake-qualification.md: 3449492fd680a813c1fbc59aad1f16bf6cc378fc
- checkpoint-source-gates.yml: fe6aceac62721338eba4fcb40e2e7fde0d976e18

## Session and scheduler authority

Only NYSEPublishedRegularSessionAuthority derives sessions. Observe aware UTC,
search today/next date in New York within its frozen 2026â€“2028 authority, and
select the first trigger strictly later than observation and at most 18 hours
away (inclusive). Trigger is regular open minus 10 minutes; end boundary is
regular open plus 5 minutes. Admission closes at regular close minus 5 minutes.
Holidays/weekends are skipped; emergency closures are not inferred. No caller
supplies session, exchange, boundaries, duration, task, command or principal.
Source/evidence/task admission must also pass; collisions block, never skip
forward into another session or reuse prior evidence.

Fixed task: \AITradingBot-Arch134-D1R6-OvernightWake-v1.
One enabled TimeTrigger, no repetition/random delay. WakeToRun true;
StartWhenAvailable false; RestartCount zero with no restart interval;
AllowDemandStart false; RunOnlyIfIdle/RunOnlyIfNetworkAvailable false;
DisallowStartIfOnBatteries/StopIfGoingOnBatteries false; Hidden false;
MultipleInstancesPolicy IgnoreNew; ExecutionTimeLimit PT20M;
AllowHardTerminate true; idle stop/restart false. InteractiveToken, least
privilege, current observed principal name and SID; no password dependency.
The fixed action is System32 Windows PowerShell -NoProfile -NonInteractive
-File against the fixed D1R6 task launcher. Its working directory is the fixed
D1R6 worktree. The launcher selects the fixed development Python and isolated
source launcher. No environment executable/source override is accepted.

Local COM transport uses TASK_CREATE=2 once, TASK_LOGON_INTERACTIVE_TOKEN=3,
TASK_RUNLEVEL_LUA=0. It never updates, runs, stops, deletes or toggles a task.
A fixed read-only observer distinguishes only file-not-found from unavailable.
Two exact stable post-create projections must match the canonical definition;
unknown fields/defaults/drift fail closed. Scheduler state/result never proves
D1R5 PASS. A locked logged-in desktop and normal sleep are supported intentions;
logoff/full shutdown are unsupported. WakeToRun does not prove hardware/power
policy support. No power-policy or ACL mutation is granted.

## Evidence and one-attempt fencing

Fixed existing parent: F:\AI\temp\qualification, outside repositories and
F:\AITradingBot. Reject links/reparse ancestors and nonregular files. No parent
provisioning. Names are bounded from session + complete D1R5 HEAD and (for arm)
D1R6 HEAD/TREE. Any arm for that target source/session or D1R5 result consumes
that destination. Exclusive creation only; no overwrite/resume/repair/rename.

Schema arch134-d1r6-overnight-wake-arming/v1, maximum 65536 bytes. Sorted compact
UTF-8 JSON objects, each with exactly one LF. Closed fields/types, duplicate-key
rejection and byte-for-byte canonical reserialization. Immutable facts include
both source identities, published session/open/close/admission, trigger/end,
principal name/SID, fixed task/settings/action, derived result path, observation,
zero trading effects and scheduler-create budget. All complete nonterminal
prefixes are consumed; partial/corrupt bytes are invalid and consumed.

ARMING_RESERVED -> D1R6_SOURCE_ADMITTED -> D1R5_TARGET_ADMITTED ->
TASK_ABSENCE_CONFIRMED -> TASK_CREATE_INTENT -> TASK_CREATE_RETURNED ->
TASK_CONFIRMED -> FINAL/ARMED.
Every append flushes and fsyncs. Intent is durable before transport entry.
Recheck both sources, clock/session, principal, task and destinations immediately
before intent. Once transport is entered, any exception/ambiguous acknowledgement,
readback drift or write failure consumes the attempt as INDETERMINATE (or an
incomplete consumed prefix if durable recording fails). No retry. Earlier
failures are BLOCKED without scheduler entry. Upper budget is one create call.
The arm interlock is AUTHORIZE_ARCH134_D1R6_ONE_OVERNIGHT_WAKE_ARMING.

## Host modes and launch

Modes: preflight, arm, launch, reconcile. Exact explicit expected HEAD/TREE are
required for preflight/arm; arm additionally requires the complete literal.
Preflight only inspects sources/calendar/clock/parent/absence/principal/task;
it writes nothing. Output is a closed sanitized disposition with zero forbidden
counters, no exception text or arbitrary paths. Import/help has no host effects.

Launch requires the single current-source canonical FINAL/ARMED journal,
re-admits both sources, validates all immutable facts and fresh result absence,
then starts the fixed Python isolated child exactly once. Child establishes only
the fixed D1R5 src, imports its accepted host, and supplies frozen HEAD/TREE,
derived evidence and AUTHORIZE_ARCH134_D1R5_ONE_PREMARKET_WAKE_QUALIFICATION.
D1R5 independently admits imports/source/actual timing; it retains 15-minute
lead, 5-minute buffer, 20-minute sleep and 60-second lateness. A separate exclusive, flushed/fsynced deterministic -launch.jsonl intent
(schema arch134-d1r6-overnight-wake-launch/v1; exactly schema/event/facts/
d1r5_delegation_budget/effects; event D1R5_LAUNCH_INTENT, budget one) fences
child delegation before process entry, including D1R5 rejection before result
reservation. Any existing/partial launch fence is consumed. It has no resume
or repair parser; reconciliation still uses only D1R5 result authority. No retry or continuation into D1.
Read-only Git and fixed PowerShell transports are narrowly scoped native host
plumbing; no general subprocess/command API is exposed.

## Morning reconciliation and authority

Read-only, bounded parsing. ARM_EVIDENCE_INVALID for absent/ambiguous/invalid or
incomplete arm; task observation drift/missing reports TASK_DRIFT_OR_MISSING
alongside the independent evidence disposition. Evidence disposition is PASS,
D1R5_TERMINAL_FAILURE, D1R5_INCOMPLETE, D1R5_INVALID, NO_D1R5_EVIDENCE, or
PENDING. Pending ends at admission-open + 20 minutes (latest admitted start plus the
fixed task execution bound);
existing canonical terminal evidence is authoritative even before that deadline.
D1R5 parsing uses the unchanged public canonical parser and additionally requires
exact target source/session/timing. Task result cannot replace evidence authority.
No repair/rerun/cleanup. No D1, PREPARE, EXECUTE, strategies, paper/store/SQLite,
credential, OAuth, provider, Robinhood, broker, ACL, D2 or live authority.
Real-money trading remains NO-GO. D1R5 PASS still stops before D1.

## Source gate

arch134-d1r6-overnight-wake-arming maps the exact successor branch to robinhood.
No protected runner hook. Existing workflow family/topology is frozen. Its literal fallback batch remains
the exact D1R5 baseline; the new branch routes dynamically through the registered
D1R6 checkpoint. The workflow notary compares the frozen baseline after removing
only this explicitly registered successor from the current active tuple. Successor
test-only pin overlay follows HIST2 then D1R5 at every predecessor resolver;
D1R5 dictionaries stay frozen. Inventory is discovered, not reassigned.
One exact-file implementation commit/push after focused PASS, attempt-1 mapped
CI with canonical wall below 300 seconds, then STOP for ChatGPT exact review.
PROJECT_STATUS.md and AI_TRADING_BOT_HANDOFF.md remain untouched.
