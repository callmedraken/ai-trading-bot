# AI Trading Bot - Current Handoff

## Purpose and authority

This is the bounded active-session and current-boundary handoff. It records
what a new ChatGPT session needs to understand the current product state,
protected boundaries, and immediate next step. It is not a chronological
journal.

`docs/PROJECT_STATUS.md` is the bounded current dashboard and roadmap.
`AGENTS.md` and `docs/AI_DEVELOPMENT_WORKFLOW.md` remain the standing workflow
authority. Detailed architecture, validation, and closed chronology belong in
their authoritative records and in `docs/history/`.

The ongoing canonical bounded new-chat handoff/history branch is
`feature/project-history-storage-foundation`. It is documentation/current-state
authority only and must remain a fast-forward mirror of the latest accepted
bounded-docs descendant of the active product lineage. It is not executable-
source, provider, broker, or trading authority.

The current product/source branch at this checkpoint is
`feature/robinhood-production-paper-premarket-wake-qualification`. Exact
source HEAD/tree and CI must always be verified on that active branch before
source or protected work. Real-money trading remains **NO-GO**.

## New-session reading order

Resolve `feature/project-history-storage-foundation` and read, in order:

1. its `AGENTS.md`;
2. its `docs/AI_DEVELOPMENT_WORKFLOW.md`;
3. its `docs/PROJECT_STATUS.md`;
4. this file from the same canonical branch;
5. the relevant current architecture or validation document;
6. then verify the separately named active product branch, exact HEAD/tree,
   recent diff and applicable CI before source/protected work.

Read `docs/history/INDEX.md` or an immutable legacy snapshot only when older
provenance, incident reconstruction, predecessor semantics, or disputed
historical evidence is actually required. Do not routinely load the legacy
megafiles during startup.

## Current operational checkpoint

Architecture 134-D1R6R3 **canonical observation + exact consumed-arm recovery**
is SOURCE ACCEPTED:

```text
branch  feature/robinhood-production-paper-overnight-wake-arming
HEAD    e6defea5aa7b9266f78c7d2f22ebac90bf568dd7
TREE    f9ad06c9b26beb681ceb3429fd66452e4aef88a9
CI      #572 / 38737407813 / SUCCESS / attempt 1
```

Exact GitHub review confirmed the seven-file commit and frozen task launcher,
D1R5 child, runner, D1R5 predecessor and source-gate workflow. R3 canonicalizes
Task Scheduler offset-bearing trigger strings to the original UTC instants and
resolves observed UserId values to canonical SIDs. It does not change task
registration behavior or add scheduler update/delete/run authority.

The exact October 15 consumed incident is hard-pinned by predecessor HEAD/TREE,
journal filename, 16917 bytes and SHA-256
`b62959f9988dcc42e4881e45ed95abcf4abc2b6d2932514c7253165e1223955c`.
Its durable terminal classification remains FINAL/INDETERMINATE after
TASK_CREATE_RETURNED; the one native create attempt remains consumed.

R3 adds only a separate recovery artifact path with zero scheduler mutation,
task-run and D1R5-execution budgets. The consumed predecessor alone never grants
launch authority.

Checkpoint #572 independently passed source-static and active tests (2,599 /
2,599) plus canonical ROBINHOOD (9,565 passed / 1 skipped / 0 failed/errors,
164.700s wall). Static authority passed with scheduler/provider/production/
broker effects NOT_RUN.

Operationally, the incident-specific recovery window has expired. Recovery
requires current time strictly before the original 2026-10-15 06:20 Pacific
trigger; that trigger is now past. Therefore do not fast-forward the live task
worktree for the purpose of recovering today's task and do not run
recover-preflight/recover.

The current next boundary is read-only post-trigger reconciliation of the
existing task, launch fence and D1R5 evidence. Expected behavior is fail-closed:
the predecessor launcher cannot accept FINAL/INDETERMINATE, but this must be
confirmed from the real host before any future scheduler cleanup/replacement.

D1R5 remains:

```text
HEAD  7aa54bb618f63bfb2b470ff8fc88ba8d27ef9343
TREE  c826c2a71e6d907866ce3f80afce479d38ab7842
```

No D1/PREPARE/EXECUTE/paper/broker/D2/live authority follows from R3 source
acceptance.

## Exact D1R4 state

The one-shot D1R4 authentication qualification has now completed successfully
and is permanently consumed. The accepted canonical authentication evidence is:

```text
path    F:\AI\temp\qualification\arch134-d1r4-auth-234614a21d68680f5b1e0ccd.json
bytes   635
SHA256  100e3590543b8ba36002d50d890578533100035b9f618434dd2c9adc2f3505c4
status  PASS
reason  PASS
source  234614a21d68680f5b1e0ccdb5854347a6a8d090
tree    f70459d91c393c6ea7a4a6358f02a2073b246574
```

The qualification read the staged pair once, succeeded, made exactly one Alpaca
request, received HTTP 200, retained no provider code, and re-admitted the exact
source. The generation journal is now irreversibly provider-fenced; its post-auth
SHA-256 is
`344f64a1c421c41174142aa4f30f2574537bb26e70901dd77cf56ec930ec7434`.
The authentication invocation must never be rerun from this generation.

The consumed fresh `/v3` provisioning effect was executed from:

```text
HEAD  ae19cc933f00445d00f196f7b7963bf01b5433ae
TREE  b361c153035ec1dca3ffacc5c819398239f55da6
```

The preserved generation evidence is:

```text
path    F:\AI\temp\qualification\arch134-d1r4-v3-generation-b206df8a30964c4c9a807d306b54c0b9.json
bytes   4881
SHA256  3cb18e50b821c4f7361b213f2095d148dd18a172f60cdf72255e36838eaa7ce3
schema  alpaca-v3-credential-generation-journal/v1
policy  windows-credential-manager-alpaca-market-data/v3
```

The expected nonsecret UTF-8 lengths are key 26 and secret 44. The accepted
journal sequence is:

```text
PROVISIONING_RESERVED
LOCK_ACQUIRED
EXPECTED_GENERATION
INITIAL_STATE_ACCEPTED
KEY_WRITE_INTENT
KEY_WRITE_CONFIRMED
SECRET_WRITE_INTENT
SECRET_WRITE_CONFIRMED
PAIR_CONFIRMED
FINAL / LOCAL_EXACT_MATCH
```

The provisioning classification remains
`LOCAL_V3_PAIR_EXACTLY_PROVISIONED`, but the journal now also contains the
durable `V3_PROVIDER_EFFECT_INTENT` fence consumed by the accepted
authentication qualification. Provisioning and authentication are both
consumed and must not be rerun.

Remote Alpaca authentication is now proven only for the fixed qualification
probe and exact accepted source. This still does not establish D1 session
readiness, paper-session readiness, D2 readiness, broker readiness, or
live-trading authority.

## Current protected boundary

The October 15 wake incident is post-trigger reconciled and fail-closed.

The one-time task fired at 06:20 Pacific and returned exit code 2. Its frozen
launcher was still sourced from local HEAD
`3cf4284d017e362eee58a2f27526ab4de8f292a2`, while the live remote branch had
already advanced. The accepted predecessor host's exact source admission checks
`ls-remote` against local HEAD before loading arm authority, so the scheduled
launch necessarily stopped at source admission.

Durable external facts:

```text
consumed arm journal bytes/SHA exact      YES
launch fence                              ABSENT
D1R5 result                               ABSENT
recovery artifact count                   0
task LastRunTime                           2026-10-15 06:20 Pacific
task LastTaskResult                        2
task current state                         READY
task next run                              none
```

Therefore D1R5 was not delegated and the October 15 incident grants no D1
authority.

Do not run arm, recover, recover-preflight, manual task run, update or deletion.
The next protected boundary is a new source-reviewed stale-task retirement
checkpoint with one exact delete budget and zero recreation/delegation/trading
authority. After retirement is independently reconciled, a fresh next-session
wake generation may be planned.

## Standing safety and effect invariants

- Paper trading is the default. Real-money trading, live brokerage, and live
  credentials remain unavailable until their separately reviewed gates pass.
- No credential values, private keys, tokens, or other secrets belong in the
  repository or these documents.
- Strategies produce proposals; deterministic risk validation approves,
  resizes, or rejects every order before execution. AI recommendations cannot
  bypass risk, authority, execution, reconciliation, or audit controls.
- Simulated, paper, broker-paper, and future live decisions and transactions
  remain auditable. Broker and live effects are separate from this history
  checkpoint.
- Ambiguous or partially consumed protected effects stop and require read-only
  reconciliation; they are never silently retried, repaired, or reused.
- Deterministic research preserves chronological folds, raw identities, caller
  ordering, Decimal correctness, and explicit missing-data failures. No
  look-ahead or test-period leakage is acceptable.

## Current production architecture

The current architecture is layered and the history cutover does not change
its authority boundaries:

- Architecture 131 preserves the reviewed Robinhood paper-trading, risk,
  execution, and audit composition ([architecture/131-robinhood-review-paper-trading.md](architecture/131-robinhood-review-paper-trading.md)).
- Architecture 132 owns tiered certification profiles, source admission, and
  source-gate topology ([architecture/132-tiered-certification-profiles.md](architecture/132-tiered-certification-profiles.md)).
- Architecture 133 preserves the supervised runtime, immutable-release, and
  unattended review-paper boundaries ([architecture/133-robinhood-single-session-unattended-review-paper-authority.md](architecture/133-robinhood-single-session-unattended-review-paper-authority.md)).
- Architecture 134 is the current production strategy and AI-research
  authority ([architecture/134-production-strategy-and-ai-research-authority.md](architecture/134-production-strategy-and-ai-research-authority.md)).
- The D1R4 provisioning concurrency and fixed-mutex contract is recorded in
  [architecture/134-d1r4-alpaca-v3-provisioning-concurrency.md](architecture/134-d1r4-alpaca-v3-provisioning-concurrency.md), with the accepted generation evidence in
  [validation/arch134-d1r4-alpaca-v3-credential-generation.md](validation/arch134-d1r4-alpaca-v3-credential-generation.md).
- The D1R3 `/v2` qualification is historical, consumed predecessor evidence
  only; it is not current authority.

## Accepted history integration

- HIST-2B is accepted: its exact legacy snapshot is sealed, and these bounded
  current handoff and status documents are accepted. Its source identity,
  exact bytes, and manifest are recorded in [history/INDEX.md](history/INDEX.md)
  and [history/legacy/HIST-2B-2026-10-13/manifest.json](history/legacy/HIST-2B-2026-10-13/manifest.json).
- Exact Git preservation was finalized at HEAD
  `83d0ec7d599f7494bb964c756a8b5717ac567d6c`, TREE
  `f6badbe010bd85cbb3dbfd0dd71be7842bbe3612`; the earlier normalized storage
  state is historical and superseded.
- The D1R4 local `/v3` pair was accepted only as local exact provisioning. The
  next provider boundary remains separately protected as described above.
- Checkpoint Source Gates #549 accepted the integrated operational source:
  static authority passed; active tests passed; canonical ROBINHOOD certification
  passed 9,065 / 9,066 cases with one skip and zero failures/errors in
  200.417 seconds. Artifact `11875285428` has SHA-256
  `02c29f3debd0cf274e85986ab5bd74ebbfc7b9ce9ec234e04fd9d3ad93240b2e`.
  HIST-2 adds one FULL-only archive-tool test, so current inventory is FULL 174,
  ROBINHOOD 97, LEGACY 215, EXHAUSTIVE 389; frozen predecessor authority pins
  remain preserved through the reviewed HIST-2 test-pin overlay.

- Architecture 134-D1R5 and the Architecture 132-R3H hygiene correction are
  source/certification accepted at HEAD
  `a7f985c6e4c723fdd4c4a1c49798531ddabe9e4a`, TREE
  `9fcbc170e8339e0b4a93844466e8924ff8ef7f36`. Checkpoint Source Gates
  #557 / `38549244176` passed static authority, expanded active tests, and
  canonical ROBINHOOD certification: 9,182 cases, 9,181 passed, one skipped,
  zero failed/errors, wall 253.493 seconds. Current inventory is FULL 175,
  ROBINHOOD 98, LEGACY 215, EXHAUSTIVE 390. No real D1R5 host/effect ran.

## Immediate next step

D1R4 authentication is accepted and consumed, and D1R5 source is accepted.
The immediate safe next step is the **separately reviewed real bounded D1R5
clock/sleep/external-evidence qualification** on the exact accepted source.
Do not invoke a fresh D1 session, PREPARE, EXECUTE, Robinhood paper effect,
broker action, D2, or live trading until that real qualification is accepted.

## Historical reconstruction

Use [history/INDEX.md](history/INDEX.md) for routing. Use the immutable legacy
snapshot at `docs/history/legacy/HIST-2B-2026-10-13/` only for targeted
chronological reconstruction, audit, predecessor semantics, or disputed
evidence. Use the linked architecture and validation records for detailed
contracts. Use Git history for exact source-era reconstruction. Historical
corrections are additive records or index annotations, never silent rewrites
of the immutable snapshot.
