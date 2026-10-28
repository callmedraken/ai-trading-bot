# Architecture 146-B — Historical Research Acquisition and Custody

Status: **DESIGN FROZEN / DOCUMENTATION ONLY.** No provider, credential,
filesystem, ACL, holdout, backtest, paper, broker, production or live effect is
authorized by this document.

## Purpose

Architecture 146-A already supplies the immutable SPY v1 manifest/snapshot
contracts and pure verification over caller-supplied material. 146-B adds the
bounded path that can eventually acquire the real vendor bytes, normalize them,
separate OPEN from FINAL_HOLDOUT custody, and produce one externally verifiable
v1 snapshot without exposing holdout OHLCV to normal research tooling.

The production-host Architecture 134 blocker is independent and remains parked.

## Frozen predecessor

Current planning base:

    develop HEAD 99654f3547140dc8fd005ee1525ac9a77987b946
    develop TREE 5b04b8d4baf70b3a936d10a5972ffcd26c03dd3c

Architecture 146-A C2 is an exact ancestor:

    HEAD 6906ba01bfb6a353029d695e584b2097587b81b9
    TREE aa1efe5057e047e0d1778f2422e45f26cbc9f5d6
    CI   #720 / 40178730059 / attempt 1 / SUCCESS

146-B must reuse the accepted
`trading_bot.experiments.historical_research_dataset` contracts. It may add
successor acquisition/custody source, but it must not reinterpret 146-A IDs,
partition bounds, schemas, fingerprints or 145-A identities.

## Dataset remains frozen

    symbol           SPY
    calendar         XNYS
    timeframe        1Day / 1D
    adjustment       raw
    feed             sip
    currency         USD
    price semantics  PRICE_RETURN

    FULL COVERAGE
    [2016-01-01T00:00:00Z, 2026-10-24T00:00:00Z)

    DEVELOPMENT
    [2016-01-01T00:00:00Z, 2020-01-01T00:00:00Z)

    WALK_FORWARD
    [2020-01-01T00:00:00Z, 2024-01-01T00:00:00Z)

    FINAL_HOLDOUT
    [2024-01-01T00:00:00Z, 2026-10-24T00:00:00Z)

No extension, QQQ/multi-symbol expansion, total-return adjustment or holdout
boundary change is part of 146-B.

## Vendor contract reverified for this design

Public Alpaca Market Data documentation was rechecked on 2026-10-27.

Bars remain:

    GET https://data.alpaca.markets/v2/stocks/SPY/bars
    timeframe=1Day
    start=2016-01-01T00:00:00Z
    end=2026-10-24T00:00:00Z
    adjustment=raw
    feed=sip
    currency=USD
    sort=asc
    limit=10000
    page_token=<returned token until absent>

The API documents the end parameter as inclusive. 146-B therefore must reject,
not silently filter, any returned bar whose normalized timestamp is at or after
the frozen half-open dataset end. The expected dataset contains only admitted
XNYS regular sessions.

Corporate-action provenance remains:

    GET https://data.alpaca.markets/v1/corporate-actions
    symbols=SPY
    region=us
    start=2016-01-01
    end=2026-10-24
    data_quality=complete
    sort=asc
    limit=1000
    page_token=<returned token until absent>

The `types` filter is deliberately omitted so every type supported by the
endpoint is returned. The current endpoint includes additional types introduced
after the original 146 design, including partial_call, reorganization and
capital_gains_distribution. Raw response pages are preserved byte-for-byte, so
future or unfamiliar returned action groups cannot be silently dropped.

Alpaca documents that corporate-action availability may be delayed. Therefore
the sidecar is provenance observed at the frozen acquisition, not a guarantee
that the vendor has disclosed every future correction. Any continuity-changing
event found in the returned material blocks downstream admissibility until
reviewed.

A change to endpoint semantics, entitlement, authentication method, feed access
or permitted use before B2 execution is a STOP/review condition.

## Two-step authority boundary

### 146-B1 — source checkpoint

B1 implements the operator and tests it entirely with injected transports,
synthetic response pages and disposable test filesystem/ACL adapters.

B1 may add:

- exact request construction and pagination state;
- raw-page digesting and persistence plans;
- deterministic bar normalization into the existing 146-A CSV format;
- corporate-action sidecar preservation;
- OPEN/FINAL_HOLDOUT split planning;
- snapshot/manifest construction through 146-A public contracts;
- bounded evidence/report models;
- crash/reconciliation state classification;
- Windows custody ACL code that is unreachable from tests without an injected
  explicit effect adapter.

B1 may not:

- read real credentials;
- make a real HTTP request;
- create either real dataset root;
- mutate a real ACL;
- read or write real holdout bytes;
- run 145-B or any strategy/backtest;
- touch production/runtime/scheduler/paper/broker/live state.

Expected implementation checkpoint:

    arch146-b1-historical-research-acquisition-custody-source

Expected branch:

    feature/research-arch146-b-acquisition-custody-current

Because the operator crosses credential/network/Windows-custody boundaries when
later executed, implementation/review model is Sol High. GitHub owns canonical
FULL certification. Local work uses focused tests, Ruff and diff-check only.

### 146-B2 — one reviewed acquisition/custody execution

B2 is separate from source acceptance. It may run only after exact B1
source/CI/integration review.

B2 may perform exactly one manually initiated attempt that:

1. proves exact source and clean state;
2. verifies current Alpaca endpoint/entitlement/credential prerequisites without
   exposing secret values;
3. creates a fresh protected holdout acquisition root with the reviewed DACL;
4. fetches every bars page and every corporate-action page by GET only;
5. persists raw response bytes before normalization;
6. normalizes and validates the complete dataset;
7. writes FINAL_HOLDOUT material only under protected custody;
8. reconstructs and verifies the full 146-A snapshot/manifest chain;
9. publishes OPEN material to the development root only after full verification;
10. emits a non-price evidence report containing identities, digests, counts,
    request metadata and final state, never holdout OHLCV or credential values.

A network error, authentication/entitlement rejection, ambiguous persistence,
ACL mismatch, unexpected pre-existing destination, malformed vendor response,
calendar mismatch or crash is terminal for that attempt. No blind retry or
cleanup may make an ambiguous attempt look fresh. Reconciliation, if needed, is
a later reviewed read-only checkpoint.

## Storage boundary

Development OPEN root remains:

    F:\AI\ai-trading-bot\data\research\arch146-v1

Protected custody root remains:

    F:\AI\research-holdout\arch146-v1

Normal development/research processes must not be able to enumerate or open
FINAL_HOLDOUT content. Holdout vendor bytes, normalized CSV and temporary
persistence never enter the repository, worktrees, ordinary
`F:\AI\temp`, GUI/report directories or test fixtures.

The protected root DACL remains the Architecture 146 design:

- BUILTIN\Administrators: FullControl;
- NT AUTHORITY\SYSTEM: FullControl;
- protected inheritance;
- no ordinary-user, Trading-service or broad inherited allow ACE.

B2 may use a fresh protected acquisition child under the custody root while the
attempt is incomplete. Any attempt/evidence record outside that root contains
non-price metadata only.

## Publication rule

OPEN material is the only dataset content available to normal research. It is
published only after the protected holdout material, both partition manifests
and full snapshot all verify.

No B2 result authorizes opening FINAL_HOLDOUT for model/parameter selection.
Architecture 145's later explicit final-holdout admission remains separate.

## Explicit non-scope

146-B does not:

- change Architecture 145 policy thresholds;
- select a strategy or parameters;
- run 145-B campaigns;
- build the Results GUI;
- promote a strategy;
- modify Architecture 134 host admission;
- schedule unattended production;
- authorize paper, broker or live trading.

LIVE remains NO-GO.
