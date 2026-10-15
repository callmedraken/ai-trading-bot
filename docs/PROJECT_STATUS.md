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

Architecture **134-D1R7R1 exact stale-wake retirement is SOURCE ACCEPTED**.

Accepted source:

```text
branch  feature/robinhood-production-paper-stale-wake-retirement
HEAD    768da215977a3553dcfb76cdc903bada002f8684
TREE    160fbd44a198e4563797ccf37c4b63c9a277ab0d
parent  2ec415c15c83b752be4c0e1fc20291e0f9280b3f
commit  fix: correct D1R7 production worktree literal
CI      #578 / 38809542455 / SUCCESS / attempt 1
```

D1R7R1 corrected the only blocker found during exact source review: the production
retirement WORKTREE literal had contained a U+0007/BEL byte. The accepted blob now
pins exactly:

```text
F:\AI\worktrees\ai-trading-bot-production-paper-stale-wake-retirement
```

and the D1R7 tests independently assert that exact literal and reject
non-whitespace C0 control bytes in the production module.

The accepted D1R7 retirement remains a closed one-effect surface:

```text
TASK_DELETE_BUDGET      1
TASK_CREATE_BUDGET      0
TASK_UPDATE_BUDGET      0
TASK_RUN_BUDGET         0
D1R5_EXECUTION_BUDGET   0
D1_OPERATIONS           0
D2_OPERATIONS           0
LIVE_EFFECTS            0
```

The fixed helper supports only Observe/Delete, contains exactly one
`.DeleteTask(`, and contains no RegisterTaskDefinition/Run/Stop/NewTask/Create
authority. The delete target is fixed to
`\AITradingBot-Arch134-D1R6-OvernightWake-v1`. Retirement intent is durably
consumed before native effect entry; ambiguity after intent is non-retryable and
becomes INDETERMINATE. RETIRED requires the single returned delete plus two
independent ABSENT observations and durable FINAL/RETIRED evidence.

The October 15 consumed incident remains frozen:

```text
D1R6 predecessor HEAD   3cf4284d017e362eee58a2f27526ab4de8f292a2
D1R6 predecessor TREE   16a48a12756bb6d810799444859334ce6305001d
arm bytes                16917
arm SHA-256              b62959f9988dcc42e4881e45ed95abcf4abc2b6d2932514c7253165e1223955c
task LastRunTime         2026-10-15 06:20 Pacific
task LastTaskResult      2
launch fence             ABSENT
D1R5 result              ABSENT
recovery artifacts       0
```

The #575/#576 failures were diagnosed source-correction events, not retries.
#575 exposed stale active-checkpoint registration expectations; #576 exposed one
remaining predecessor-overlay assertion. Each was corrected by a new commit.
#577 passed but was not accepted because exact review found the BEL path defect.
#578 is the new exact-head attempt-1 acceptance run.

#578 independently passed:

```text
source-static         SUCCESS
active-tests          SUCCESS   2,770 / 2,770
certification-tests   SUCCESS   ROBINHOOD
full-tests            SKIPPED
source-gates          SUCCESS

ROBINHOOD
cases                 9,737
passed                9,736
skipped               1
failed/errors         0 / 0
canonical wall        260.394 s
```

No real D1R7 preflight, retirement journal, scheduler delete, D1R5 execution,
D1 operation, D2 operation, live effect, or October 16 arm has occurred.

The live D1R6 task worktree remains intentionally preserved at the consumed
predecessor identity. Source acceptance does not authorize changing it.

## Current blocker / protected boundary

The immediate protected boundary is now the **first real D1R7 read-only retirement
preflight**.

Source acceptance alone does **not** authorize scheduler deletion.

Before any host action:

- preserve the live D1R6 worktree at exact HEAD
  `3cf4284d017e362eee58a2f27526ab4de8f292a2` / TREE
  `16a48a12756bb6d810799444859334ce6305001d`;
- preserve the consumed October 15 arm journal byte-for-byte;
- do not fast-forward, modify, run or delete the D1R6 task;
- do not create retirement evidence during read-only preflight;
- do not invoke D1R5;
- do not arm a future wake.

A separately authorized D1R7 preflight may only observe/admit source, frozen
predecessor/target, consumed incident, current principal and the exact stale task
fingerprint. If that preflight passes, a second explicit authorization is still
required for the one-shot retirement effect.

Any future retirement attempt has one native DeleteTask budget total. No blind
retry is authorized after TASK_DELETE_INTENT or any ambiguous native entry.

## Roadmap

### Now

- Preserve accepted D1R7R1 source at
  `768da215977a3553dcfb76cdc903bada002f8684`.
- Preserve the live D1R6 worktree at its frozen October 15 predecessor identity.
- Run no host action until a separately authorized read-only D1R7 preflight.
- Keep scheduler mutation, D1R5, D1, PREPARE, EXECUTE, paper/broker, D2 and live
  authority at zero.

### Next

- Run one read-only D1R7 retirement preflight under an explicit host boundary.
- If and only if it passes, separately authorize one exact stale-task retirement.
- Reconcile the retirement read-only; never automatically retry an
  INDETERMINATE deletion.
- Only after canonical RETIRED evidence plus independently observed task absence
  may the no-longer-referenced D1R6 worktree be fast-forwarded.
- Then prepare a fresh future-session D1R6 wake generation with new evidence
  identity; never reuse the consumed October 15 arm/recovery/retirement authority.

### Later

- Only after a future canonical D1R5 PASS is independently accepted may a fresh
  D1-session authorization be considered.
- Keep PREPARE/EXECUTE, paper/broker, D2 and real-money trading behind their own
  separately reviewed authority boundaries.

## History and deep-reference pointers

The immutable snapshot is indexed at [docs/history/INDEX.md](history/INDEX.md).
Its exact files and manifest are under
`docs/history/legacy/HIST-2B-2026-10-13/`. The legacy snapshot is for targeted
audit and reconstruction, not routine startup. Read the relevant architecture
or validation record first; use Git history when exact source-era provenance is
required. Do not grow this dashboard back into a cumulative milestone journal.
