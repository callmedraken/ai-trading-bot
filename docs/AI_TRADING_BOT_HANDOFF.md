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

The history-storage branch is not trading authority. The operational product
branch and this history-storage branch must remain distinct:

- operational branch: `feature/robinhood-production-paper-alpaca-auth-qualification`;
- history-storage branch: `feature/project-history-storage-foundation`.

This history checkpoint performs no credential, provider, broker, trading,
scheduler, production, deployment, ACL, SQLite, OAuth, PREPARE, EXECUTE, D1,
or D2 effect. Real-money trading remains **NO-GO**.

## New-session reading order

Read, in order:

1. `AGENTS.md`;
2. `docs/AI_DEVELOPMENT_WORKFLOW.md`;
3. `docs/PROJECT_STATUS.md`;
4. this file;
5. the relevant current architecture or validation document.

Read `docs/history/INDEX.md` or an immutable legacy snapshot only when older
provenance, incident reconstruction, predecessor semantics, or disputed
historical evidence is actually required. Do not routinely load the legacy
megafiles during startup.

## Current operational checkpoint

The current operational product lane is Architecture 134 and its D1R4 Alpaca
authentication qualification sequence. The current canonical operational branch
state before this history cutover is:

```text
branch  feature/robinhood-production-paper-alpaca-auth-qualification
HEAD    a2d4e4aca8e31fa9c72b4e21372c4d97f45b74fa
TREE    2d29744b4d116c9567fe8a5894f5adaece4578cf
```

The history-storage branch is only carrying the bounded-document and history
cutover. It does not replace, advance, or authorize the operational branch.

## Exact D1R4 state

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

The only accepted classification is
`LOCAL_V3_PAIR_EXACTLY_PROVISIONED`. `V3_PROVIDER_EFFECT_INTENT` is absent,
Alpaca/provider requests are 0, and ambiguity is none. The provisioning
invocation is consumed and must not be rerun. Ordinary fresh `/v3`
provisioning must now block because the accepted staging pair exists.

This state does not establish remote Alpaca authentication, D1 readiness,
paper readiness, D2 readiness, broker readiness, or live-trading authority.

## Current protected boundary

The next operational boundary is a separately reviewed one-shot D1R4
authentication qualification. Before any possible Alpaca request, its host
must:

1. re-admit the exact reviewed operational source;
2. acquire and use the fixed mutex required by the accepted D1R4 contract;
3. read the same locally staged pair;
4. reproduce the accepted journal witnesses;
5. durably append `V3_PROVIDER_EFFECT_INTENT`; and
6. only then permit the bounded authentication request.

Once that provider-effect fence is appended, this generation can never
authorize a second authentication qualification, regardless of HTTP result,
transport outcome, ambiguity, interruption, or failure. HIST-2B.2 does not
authorize that request.

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

## Recent transitions that still matter

- HIST-2B froze the former cumulative handoff and status documents as the
  immutable snapshot `HIST-2B-2026-10-13`. Its source identity, exact bytes,
  and manifest are recorded in [history/INDEX.md](history/INDEX.md) and
  [history/legacy/HIST-2B-2026-10-13/manifest.json](history/legacy/HIST-2B-2026-10-13/manifest.json).
- Exact Git preservation was finalized at HEAD
  `83d0ec7d599f7494bb964c756a8b5717ac567d6c`, TREE
  `f6badbe010bd85cbb3dbfd0dd71be7842bbe3612`; the earlier normalized storage
  state is historical and superseded.
- The D1R4 local `/v3` pair was accepted only as local exact provisioning. The
  next provider boundary remains separately protected as described above.

## Immediate next step

For this checkpoint, the next step is exact source review and acceptance of the
bounded history-storage change. For the operational product lane, the next
step is the separately reviewed one-shot D1R4 authentication qualification
readiness sequence. Stop before any provider request unless every fixed
source, mutex, witness, journal, and provider-intent condition is proven.

## Historical reconstruction

Use [history/INDEX.md](history/INDEX.md) for routing. Use the immutable legacy
snapshot at `docs/history/legacy/HIST-2B-2026-10-13/` only for targeted
chronological reconstruction, audit, predecessor semantics, or disputed
evidence. Use the linked architecture and validation records for detailed
contracts. Use Git history for exact source-era reconstruction. Historical
corrections are additive records or index annotations, never silent rewrites
of the immutable snapshot.
