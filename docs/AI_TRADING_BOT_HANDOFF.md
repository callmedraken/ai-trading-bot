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

The repository default/integration branch is `develop`. The bounded
new-chat/current-state mirror remains
`feature/project-history-storage-foundation`; after an accepted integration
they must converge to the same accepted descendant rather than forming parallel
source histories. Neither branch name grants provider, scheduler, broker,
production-effect, or trading authority.

The protected operational D1R6 source that produced the accepted October 16
wake evidence remains `feature/robinhood-production-paper-overnight-wake-arming`
at exact HEAD/TREE recorded below. Exact source and evidence must still be
re-proven before any later protected operation. Real-money trading remains
**NO-GO**.

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

The October 16 D1R6 overnight wake and bounded D1R5 qualification completed
successfully and are now read-only reconciled.

```text
D1R6 branch       feature/robinhood-production-paper-overnight-wake-arming
D1R6 HEAD         a36de3bfe81a6e1a94fb3deeec7e579145939f52
D1R6 TREE         6cde732e02e92eb2b34281672cdb7744250355b1
remote HEAD       a36de3bfe81a6e1a94fb3deeec7e579145939f52
source admission  PASS

reconcile         PASS
evidence          PASS
task              MATCH
exit              0
```

The frozen D1R5 target is:

```text
HEAD  7aa54bb618f63bfb2b470ff8fc88ba8d27ef9343
TREE  c826c2a71e6d907866ce3f80afce479d38ab7842
```

At the accepted D1R6 source, reconciliation can classify D1R5 evidence as PASS
only after bounded reading, canonical D1R5 parsing, exact target
HEAD/TREE/session matching, and a terminal `FINAL / PASS`. `task=MATCH` is
an independent scheduler-definition observation and cannot substitute for
evidence authority.

The accepted D1R5 success sequence is:

```text
QUALIFICATION_RESERVED
SOURCE_ADMITTED
WAITING_FOR_MARKET
WAKE_OBSERVED
SOURCE_READMITTED
FINAL / PASS
```

The user-reported reconciliation effect map is entirely zero. No arm retry,
operator task run, scheduler create/update/delete, evidence mutation, D1,
PREPARE, EXECUTE, strategy evaluation, paper mutation, broker placement,
provider/credential access, D2, or live effect was performed during
reconciliation.

The October 15 FINAL/INDETERMINATE incident remains immutable historical
evidence, but it is no longer the current blocker. Do not run its expired
recovery path.

D1R5 PASS is a prerequisite result only. It grants no D1 session, PREPARE,
EXECUTE, paper/broker, D2, scheduler mutation, or live-trading authority.

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

The next protected boundary is a **new D1-session authorization checkpoint**
that may consume the accepted October 16 D1R5 PASS only under a separately
implemented, source-reviewed and explicitly authorized contract.

Until that boundary exists and is accepted:

- do not invoke D1;
- do not invoke PREPARE or EXECUTE;
- do not perform Robinhood paper or broker effects;
- do not invoke D2 or live trading;
- do not rerun D1R6 ARM or the consumed D1R5 qualification;
- do not manually run/update/delete/recreate the scheduler task as an implicit
  cleanup step.

Any scheduler retirement or replacement remains a separate protected effect
boundary with its own fencing and reconciliation requirements.

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

## Canonical integrated checkpoint

The accepted canonical integration candidate combines the product/D1R6 lineage
with the already accepted Architecture 138/139 research and Architecture 140
GUI safe-side lineage:

```text
branch  feature/test-suite-canonical-handoff-integration-current
HEAD    e2b46c104168c007263c688450beb79d71637a94
TREE    eaec980bda6e0669878e54d622cb8694ef3e2fc4

CI      #591 / 38957936922 / push / attempt 1 / SUCCESS
GUI     #20 / 38957942329 / pull_request / attempt 1 / SUCCESS
```

Checkpoint #591 passed source-static plus four broad shards at 88.401 / 73.968 /
92.000 / 63.715 seconds. GUI #20 passed all 1,001 real-PySide6 tests and Ruff /
diff checks. Integrated inventory is ACTIVE 65 / FULL 180 / ROBINHOOD 99 /
LEGACY 222 / EXHAUSTIVE 402 / GUI 51.

The integration preserves D1R6 source authority while incorporating accepted
Architecture 139-B SHADOW research and GUI-A16/A17/A18. A16 remains the sole
five-artifact local acquisition/linkage boundary; A17 remains immutable audit
presentation; A18 remains a read-only lifecycle boundary map. No
`PAPER_CANDIDATE`, `AWAITING_HUMAN_PROMOTION`, production compatibility,
automatic promotion, promotion authority, trading authority, provider effect,
or scheduler mutation is created by this merge.

The A16, A17 and A18 predecessor overlays stay frozen. The canonical integration
adds one separate seven-path current-inventory overlay only where product and
safe-side test bytes legitimately meet.

## Immediate next step

After the atomic `develop` merge reaches terminal-green GitHub source-gate CI,
fast-forward `feature/project-history-storage-foundation` to the exact same
merge descendant without creating a second implementation state or a new
docs-only commit merely to synchronize branch names.

For product progression, the next protected milestone is the separately designed
D1-session-authorization checkpoint that may consume the accepted D1R5 PASS
without implicitly granting PREPARE/EXECUTE or scheduler mutation.

For safe-side progression, preserve Architecture 139-B SHADOW and
GUI-A16/A17/A18 read-only semantics. No integration step itself authorizes
production conversion or promotion.

Workflow invariant for the next checkpoint: compose source, tests, workflow
changes, status/handoff and predictable cleanup before publication; use one
atomic commit/push and one push-triggered GitHub CI admission run. A failure ends
that logical checkpoint attempt. Any later push is a separately declared
corrective checkpoint, not a fix-forward loop.

Every accepted checkpoint/merge report must automatically provide the next
milestone and exact actionable next step; the user should not need to ask what
comes next.

No fresh D1, PREPARE, EXECUTE, Robinhood paper effect, broker action, D2, or
live trading is authorized by this handoff.

## Historical reconstruction

Use [history/INDEX.md](history/INDEX.md) for routing. Use the immutable legacy
snapshot at `docs/history/legacy/HIST-2B-2026-10-13/` only for targeted
chronological reconstruction, audit, predecessor semantics, or disputed
evidence. Use the linked architecture and validation records for detailed
contracts. Use Git history for exact source-era reconstruction. Historical
corrections are additive records or index annotations, never silent rewrites
of the immutable snapshot.
