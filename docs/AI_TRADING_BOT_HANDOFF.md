# AI Trading Bot - Current Handoff

>
> **Parallel-branch scope note:** this GUI branch is not canonical product/current-operational authority. Resolve `feature/project-history-storage-foundation` and the separately named active product branch for protected product state. This closeout records only the accepted safe-side GUI-A18 source and does not replay, authorize, retry, or mutate D1R6/D1R5 operations.
>

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

Architecture 134-D1R5 source and the Architecture 132-R3H certification-hygiene
correction are accepted on:

```text
branch  feature/robinhood-production-paper-premarket-wake-qualification
source  a7f985c6e4c723fdd4c4a1c49798531ddabe9e4a
tree    9fcbc170e8339e0b4a93844466e8924ff8ef7f36
CI      #557 / 38549244176 / SUCCESS
```

Canonical ROBINHOOD certification passed 9,182 cases with 9,181 passed, one
skipped, zero failed/errors, wall 253.493 seconds. The later docs-only accepted
descendant before this canonical-branch designation is
`ed2eb3ef60e9c04ed9cfa89061fb28d2dfcc562c` /
`c3831fb1508e254c464470db8d67ae14ac4c4985`, with Checkpoint Source
Gates #559 SUCCESS.

The next protected boundary is the separately reviewed real D1R5 pre-market
`WAITING_FOR_MARKET` / wake / source-readmission qualification. It has not yet
run. No fresh D1 session, PREPARE, EXECUTE, paper/broker effect, D2, or live
trading is authorized.

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

D1R4 authentication is complete and consumed. The next product boundary is the
still-required Architecture 134 pre-market start / `WAITING_FOR_MARKET` / wake
qualification before any fresh D1 session may be authorized.

The independent D1R5 timing/source qualifier must start before the admission
window, durably enter `WAITING_FOR_MARKET`, wake at the admission boundary,
re-admit source, and stop. Its source is **ACCEPTED** at HEAD
`a7f985c6e4c723fdd4c4a1c49798531ddabe9e4a`, TREE
`9fcbc170e8339e0b4a93844466e8924ff8ef7f36`; Checkpoint Source Gates
#557 / `38549244176` is SUCCESS. See
[the D1R5 contract](validation/arch134-d1r5-pre-market-wake-qualification.md).
It never enters D1 or the production armed-session effect path. Source acceptance
does not authorize the separately reviewed real bounded wait qualification.

No D1 launch is authorized by the authentication PASS itself.

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

## Parallel safe-side checkpoints

Architecture 138 / RCL-2 is SOURCE ACCEPTED at
`a9c3682231f8540be6e9dc6f2bfecd06ecf1a8b1` / tree
`55841f5119228dbf302747256326d43ff7d32e23`, CI #561 / `38634855492`.

Architecture 139-A / RCL-3A remains SOURCE ACCEPTED at
`bf500ffecefe0a8be8117e315228e3bc07ffdf54` / tree
`69d4ee1d6e7b3c2ca095b3ddf3cf05fdb7e3babd`, CI #562 / `38640090298`.

Architecture 139-B / RCL-3B is now SOURCE ACCEPTED on
`feature/research-candidate-shadow-qualification-current` as two separately
gated exact source checkpoints:

```text
B1 HEAD  3bf604f407445da0c587cfd91545c113c99e341f
B1 TREE  732f75cc09c8296ce09f244edc36ca8bda61e7b7
B1 CI    #563 / 38664134287 / attempt 1 / SUCCESS

B2 HEAD  bf98553592d2ef740d6a6ffdc104c6cd28023379
B2 TREE  34627f90f3ad8fc441346cc3d567a3f15495219b
B2 CI    #564 / 38665480838 / attempt 1 / SUCCESS
```

B1 provides canonical, caller-supplied, no-effect observation evidence tied to
the exact accepted 139-A binding and complete external predecessor chain. B2
provides deterministic coverage qualification plus an immutable
`ResearchCandidateStage.SHADOW` successor. Canonical parsers prove
self-consistency only; the public external verifiers rebuild against the exact
independently supplied chain. The B1 continuation PASS was internal permission
for B2, not final acceptance; ChatGPT independently reviewed both exact GitHub
commits, trees, diffs, blobs, overlays, dictionaries, inventories and CI runs
before granting this SOURCE ACCEPTED status.

The accepted 139-B research-domain inventory remains ACTIVE 64 / FULL 179 /
ROBINHOOD 98 / LEGACY 215 / EXHAUSTIVE 394 / GUI 44 at that checkpoint. All
seventeen recorded 139-B operational effect counters remain zero. No real SHADOW
observation occurred.

Architecture 140 safe-side GUI presentation is SOURCE ACCEPTED through
GUI-A18:

```text
A16 HEAD  6d092b8e05372d241dc4183b7b392f0eb83b4500
    TREE  fd17ccfd338266c04d24dd03e303ee36dd72b0ca
    GUI   #8 / 38684121623 / SUCCESS / 880 passed
    CI    #565 / 38684312270 / SUCCESS

A17 HEAD  56f3e8ef73f8aa62e2444c7fc9c75dfb212ff246
    TREE  5de6706064424aa4734b53cad4efffe5011284f4
    GUI   #10 / 38848617395 / SUCCESS / 984 passed
    CI    #580 / 38848782422 / SUCCESS

A18 HEAD  4debec8661edd475ecb6aa58b61b9aa115648fb7
    TREE  c2392063383a863dff0be40bf08badae080374c7
    GUI   #14 / 38860442146 / SUCCESS / attempt 1 / 1001 passed
    CI    #582 / 38860589811 / SUCCESS / attempt 1
```

A16 remains the sole explicit local five-artifact acquisition and local SHADOW
successor-linkage boundary. A17 consumes only that immutable page state and adds
a Qt-free retained-state audit. A18 consumes only the immutable A17 audit
presentation and adds the Qt-free lifecycle boundary map plus one read-only
table on the existing page. A18 explicitly records that historical/external
qualification was not re-run, real acquisition and promotion are not connected,
production compatibility is not established, PAPER_CANDIDATE and
AWAITING_HUMAN_PROMOTION are not materialized, automatic promotion is disabled,
and trading authority is NONE.

A18 preserves the A16 overlay digest
`887064885ca3be46514075efed384ccf1c6eb778d78dcc3f06bc402bff1a4e4f`
and A17 digest
`dc11d4c1e6099c1eec3346cafb85220e42f495e472d220cf81ac741ccff524c3`;
its own successor-overlay digest is
`a82247963625dea0f6842d4dc59a851c6986d9f3d8d0c0f40d452aaea2a35af5`.
Inventory is ACTIVE 64 / FULL 179 / ROBINHOOD 98 / LEGACY 222 /
EXHAUSTIVE 401 / GUI 51. No workflow, product, acquisition, provider,
scheduler, promotion, or live-money authority changed.

To preserve the canonical handoff invariant, do not move
`feature/project-history-storage-foundation` onto this research branch. The
canonical history branch and active product branch remain at
`7aa54bb618f63bfb2b470ff8fc88ba8d27ef9343` / tree
`c826c2a71e6d907866ce3f80afce479d38ab7842` until a later separately
reviewed product-lineage integration/replay says otherwise.

## Next safe-side boundary

The research lifecycle domain remains stopped at accepted Architecture 139-B.
Architecture 140 / GUI-A18 is the accepted safe-side presentation descendant at
`4debec8661edd475ecb6aa58b61b9aa115648fb7` /
`c2392063383a863dff0be40bf08badae080374c7`.

A16 remains the sole acquisition/linkage boundary; A17 remains the sole audit
composition boundary; A18 adds only the already-acquired-state lifecycle
boundary map. Any future real-market/provider SHADOW observation acquisition,
production compatibility, promotion, or post-SHADOW stage remains a separate
architecture/effect boundary requiring a new explicit contract and review.

Further GUI-only work may continue automatically only as another separately
frozen read-only presentation successor that consumes already acquired
presentation state.

## Immediate next step

For the product line, D1R4 authentication is accepted and consumed and D1R5
source is accepted. The next operational boundary remains the **separately
reviewed real bounded D1R5 clock/sleep/external-evidence qualification** on the
exact accepted product source; this closeout does not execute it.

For the parallel safe-side line, preserve accepted Architecture 139-B domain
semantics, GUI-A16 acquisition/linkage semantics, GUI-A17 audit-presentation
semantics, and GUI-A18 lifecycle-boundary-map semantics. A18's current inventory
is ACTIVE 64 / FULL 179 / ROBINHOOD 98 / LEGACY 222 / EXHAUSTIVE 401 / GUI 51.

Do not invoke real SHADOW acquisition, integrate into the product/history lineage,
materialize a post-SHADOW stage, convert to production, or promote a strategy from
this handoff alone. The next GUI milestone may proceed automatically only as
another separately frozen, read-only, already-acquired-state presentation
contract.

No fresh D1 session, PREPARE, EXECUTE, Robinhood paper effect, broker action,
D2, or live trading is authorized.

## Historical reconstruction

Use [history/INDEX.md](history/INDEX.md) for routing. Use the immutable legacy
snapshot at `docs/history/legacy/HIST-2B-2026-10-13/` only for targeted
chronological reconstruction, audit, predecessor semantics, or disputed
evidence. Use the linked architecture and validation records for detailed
contracts. Use Git history for exact source-era reconstruction. Historical
corrections are additive records or index annotations, never silent rewrites
of the immutable snapshot.
