# AI Trading Bot - Project Status

## Current phase

Architecture 134-D1R6R3 canonical Task Scheduler observation and exact consumed-arm
recovery is **SOURCE ACCEPTED**.

Accepted R3 executable/test source:

```text
branch  feature/robinhood-production-paper-overnight-wake-arming
HEAD    e6defea5aa7b9266f78c7d2f22ebac90bf568dd7
TREE    f9ad06c9b26beb681ceb3429fd66452e4aef88a9
CI      #572 / 38737407813 / SUCCESS / attempt 1
```

Independent GitHub review confirmed exactly one seven-file source commit over the
frozen live-task base `3cf4284d017e362eee58a2f27526ab4de8f292a2` /
`16a48a12756bb6d810799444859334ce6305001d`. The registered-task launcher,
D1R5 child launcher, fixed runner, D1R5 source/tests/validation and source-gate
workflow remain byte-for-byte frozen.

Checkpoint #572 passed source-static, 2,599 active tests and canonical ROBINHOOD
certification with 9,565 passed / 1 skipped / 0 failed / 0 errors in 164.700
seconds. Inventory remains FULL 176 / ROBINHOOD 99 / LEGACY 215 / EXHAUSTIVE 391.
Static evidence records authority PASS, stable exact HEAD/tree and scheduler,
provider, production and broker/live effects NOT_RUN.

R3 corrects only post-registration observation/recovery semantics. Task Scheduler
start/end boundaries are parsed as explicit-offset DateTimeOffset values,
normalized to exact UTC seconds and compared by canonical instant. Observed
principal IDs are canonicalized to a SecurityIdentifier, resolving short account
names through NTAccount when necessary. Registration behavior is unchanged and
still contains exactly one TASK_CREATE=2 path with no update/delete/run authority.

The consumed incident remains immutable and is pinned exactly:

```text
predecessor HEAD   3cf4284d017e362eee58a2f27526ab4de8f292a2
predecessor TREE   16a48a12756bb6d810799444859334ce6305001d
journal bytes      16917
journal SHA-256    b62959f9988dcc42e4881e45ed95abcf4abc2b6d2932514c7253165e1223955c
target session     2026-10-15
terminal state     FINAL / INDETERMINATE
native create      consumed exactly once
```

R3 never makes that predecessor directly authoritative. Its separate
`arch134-d1r6-consumed-arm-recovery/v1` path has zero scheduler-create/update/
delete, task-run and D1R5-execution budgets and could publish only one separate
exclusive recovery artifact after repeated read-only admission.

However, that incident-specific recovery gate deliberately requires
`current_time < original trigger` (2026-10-15 06:20 Pacific). That trigger is
now in the past. Therefore the October 15 consumed task is **not recoverable by
R3 now**, and no recovery preflight or recovery-evidence publication should be
attempted for it.

The live registered-task worktree was intentionally left frozen at the
predecessor during R3 implementation. Do not fast-forward it merely to revive
the expired October 15 recovery path. The current safe next boundary is
post-trigger read-only reconciliation of the consumed task/evidence, followed by
a separately designed next-session scheduler cleanup/replacement/arming
authority if another D1R5 qualification is desired.

The fixed D1R5 target remains:

```text
HEAD  7aa54bb618f63bfb2b470ff8fc88ba8d27ef9343
TREE  c826c2a71e6d907866ce3f80afce479d38ab7842
```

No fresh D1 session, PREPARE, EXECUTE, paper/broker mutation, D2 or live trading
is authorized.

## Operational checkpoint

The one-shot D1R4 authentication qualification is **PASS / consumed**.

```text
evidence  F:\AI\temp\qualification\arch134-d1r4-auth-234614a21d68680f5b1e0ccd.json
bytes     635
SHA256    100e3590543b8ba36002d50d890578533100035b9f618434dd2c9adc2f3505c4
status    PASS
reason    PASS
HTTP      200
requests  1
source    234614a21d68680f5b1e0ccdb5854347a6a8d090
tree      f70459d91c393c6ea7a4a6358f02a2073b246574
```

The post-auth generation journal SHA-256 is
`344f64a1c421c41174142aa4f30f2574537bb26e70901dd77cf56ec930ec7434`;
its provider-effect fence is now irreversible. Authentication must not be retried.

The accepted fresh `/v3` provisioning effect was executed from:

```text
HEAD  ae19cc933f00445d00f196f7b7963bf01b5433ae
TREE  b361c153035ec1dca3ffacc5c819398239f55da6
```

Its preserved generation journal is:

```text
path    F:\AI\temp\qualification\arch134-d1r4-v3-generation-b206df8a30964c4c9a807d306b54c0b9.json
bytes   4881
SHA256  3cb18e50b821c4f7361b213f2095d148dd18a172f60cdf72255e36838eaa7ce3
schema  alpaca-v3-credential-generation-journal/v1
policy  windows-credential-manager-alpaca-market-data/v3
```

The journal is exactly:

```text
PROVISIONING_RESERVED -> LOCK_ACQUIRED -> EXPECTED_GENERATION
-> INITIAL_STATE_ACCEPTED -> KEY_WRITE_INTENT -> KEY_WRITE_CONFIRMED
-> SECRET_WRITE_INTENT -> SECRET_WRITE_CONFIRMED -> PAIR_CONFIRMED
-> FINAL / LOCAL_EXACT_MATCH
```

The expected UTF-8 lengths are key 26 and secret 44. The only accepted
classification is `LOCAL_V3_PAIR_EXACTLY_PROVISIONED`. There is no
`V3_PROVIDER_EFFECT_INTENT`, no Alpaca/provider request, and no ambiguity.
The provisioning invocation is consumed and must not be rerun. Ordinary fresh
`/v3` provisioning must block because the accepted staging pair exists.

The provisioning record alone did not establish remote authentication, but the
subsequent one-shot D1R4 qualification now does establish
`REMOTE_ALPACA_AUTH_READY` for the fixed accepted probe/source observation.
It does not establish D1 session, paper, D2, broker, or live-trading readiness.

## Completed foundations

- Architecture 131 provides the reviewed Robinhood paper, risk, execution, and
  audit foundation ([architecture/131-robinhood-review-paper-trading.md](architecture/131-robinhood-review-paper-trading.md)).
- Architecture 132 provides the tiered current/legacy certification model and
  source-gate topology ([architecture/132-tiered-certification-profiles.md](architecture/132-tiered-certification-profiles.md)).
- Architecture 133 preserves supervised immutable-release and unattended
  review-paper runtime boundaries ([architecture/133-robinhood-single-session-unattended-review-paper-authority.md](architecture/133-robinhood-single-session-unattended-review-paper-authority.md)).
- Architecture 134 is the current production strategy and AI-research
  authority ([architecture/134-production-strategy-and-ai-research-authority.md](architecture/134-production-strategy-and-ai-research-authority.md)).
- The D1R4 `/v3` provisioning contract and accepted evidence are preserved in
  [architecture/134-d1r4-alpaca-v3-provisioning-concurrency.md](architecture/134-d1r4-alpaca-v3-provisioning-concurrency.md) and
  [validation/arch134-d1r4-alpaca-v3-credential-generation.md](validation/arch134-d1r4-alpaca-v3-credential-generation.md).

## Active work

The October 15 D1R6 arm attempt is consumed. Its native TASK_CREATE returned,
but historical R2 confirmation rejected Windows' equivalent post-registration
serialization and durably recorded FINAL/INDETERMINATE. Read-only diagnostics
proved the registered task's trigger instants and principal SID were semantically
identical to the frozen plan.

R3 source is accepted, but its exact recovery preflight requires the task still
be READY/HAS_NOT_RUN and the clock remain before the original 06:20 Pacific
trigger. That time boundary has passed. Do not run `recover-preflight`,
`recover`, `arm`, or any task mutation for the October 15 incident.

The immediate boundary is a **post-trigger read-only reconciliation** from the
still-frozen live task worktree and external qualification directory. It should
determine, without mutation:

- whether the scheduler task actually fired;
- its current state and LastTaskResult;
- whether the D1R6 launch fence exists;
- whether any D1R5 result evidence exists;
- whether the historical consumed arm journal remains byte-identical.

Because the frozen predecessor launcher requires FINAL/ARMED, the expected
fail-closed outcome is no D1R5 delegation, but real-host evidence should confirm
that before cleanup or future-session planning.

Any future cleanup/replacement/re-arming is a separate protected effect boundary
with no blind retry and no reuse of the consumed October 15 authority.

## Current blocker / protected boundary

Remote Alpaca authentication is proven for the fixed probe and D1R5 source is
accepted, but the required real pre-market / `WAITING_FOR_MARKET` / wake
qualification has not yet been executed or accepted. No fresh D1 session is
authorized until that protected boundary is complete.
The D1R4 authentication invocation is permanently consumed and must not be
retried. Real-money trading is **NO-GO**.

## Verification and certification posture

Architecture 132 remains the governing posture:

```text
FOCUSED -> SOURCE-GATE CI
-> ChatGPT selects ROBINHOOD or FULL at a coherent current-product boundary
-> LEGACY / EXHAUSTIVE only when explicitly relevant
PROTECTED only at the exact separately reviewed effect boundary
```

Mapped certification remains CI-owned; local repetition of the same valid
profile is not routine. Checkpoint Source Gates #549 accepted the integrated
operational source: static authority and active tests passed, and canonical
ROBINHOOD certification passed 9,065 / 9,066 cases with one skip and zero
failures/errors in 200.417 seconds. Artifact `11875285428` has SHA-256
`02c29f3debd0cf274e85986ab5bd74ebbfc7b9ce9ec234e04fd9d3ad93240b2e`.
Current inventory after accepted D1R5 is FULL 175 / ROBINHOOD 98 /
LEGACY 215 / EXHAUSTIVE 390. The earlier #549 result remains historical
integrated-source evidence. Current D1R5/R3H acceptance is Checkpoint Source
Gates #557 / `38549244176`: static authority PASS, active tests PASS, canonical
ROBINHOOD 9,182 cases / 9,181 passed / one skipped / zero failed/errors, wall
253.493 seconds (below the frozen 300-second hygiene ceiling). FULL covers currently supported
functionality, while LEGACY/EXHAUSTIVE retain explicit historical
compatibility. This acceptance grants no protected authority. See the
[tiered certification profile](architecture/132-tiered-certification-profiles.md)
and [development workflow](AI_DEVELOPMENT_WORKFLOW.md).

## Roadmap

### Now

- Preserve accepted D1R6R3 source at
  `e6defea5aa7b9266f78c7d2f22ebac90bf568dd7` /
  `f9ad06c9b26beb681ceb3429fd66452e4aef88a9`.
- Preserve the consumed October 15 arm journal exactly; never rewrite or relabel
  FINAL/INDETERMINATE.
- Do not run the expired R3 recovery path for October 15.
- Perform one source-owned/read-only post-trigger reconciliation of the existing
  task, launch fence and D1R5 evidence.
- Keep D1, PREPARE, EXECUTE, paper, broker, D2 and live effects closed.

### Next

- If post-trigger evidence confirms fail-closed/no D1R5 delegation, design a
  separately reviewed next-session cleanup/replacement authority for the stale
  one-time task and consumed journal.
- Create any new wake authority with a fresh session/task-generation/evidence
  identity rather than retrying or repurposing the consumed October 15 attempt.
- Run a fresh read-only preflight before any future scheduler mutation.
- Only a separately authorized future task creation may schedule another D1R5
  qualification.

### Later

- After a future canonical D1R5 PASS is independently accepted, consider the
  next fresh D1-session boundary.
- Keep real-money trading unavailable until every explicit production/live gate
  is implemented, accepted and separately enabled.

## History and deep-reference pointers

The immutable snapshot is indexed at [docs/history/INDEX.md](history/INDEX.md).
Its exact files and manifest are under
`docs/history/legacy/HIST-2B-2026-10-13/`. The legacy snapshot is for targeted
audit and reconstruction, not routine startup. Read the relevant architecture
or validation record first; use Git history when exact source-era provenance is
required. Do not grow this dashboard back into a cumulative milestone journal.
