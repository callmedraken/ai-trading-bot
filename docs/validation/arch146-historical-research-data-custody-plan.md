# Architecture 146 — Historical Research Data Contract Validation Plan

Status: **DESIGN ACCEPTED / DOCUMENTATION ONLY.** No acquisition or host custody
effect is part of this checkpoint.

## Exact design base

    develop HEAD a637f1b34565a715c14874d0f9a9686388319c16
    TREE         e870cc8f28138076d1e247eb92358d88a89c2f26
    Source Gates #716 / 40169845896 attempt 1: SUCCESS

Architecture 146 is independent of Architecture 145-B. Its purpose is to close
the missing historical-data prerequisite without opening the final holdout.

## Frozen v1 design vectors

Instrument:

    SPY

Vendor bars:

    GET https://data.alpaca.markets/v2/stocks/SPY/bars
    timeframe=1Day
    adjustment=raw
    asof=-
    feed=sip
    currency=USD
    sort=asc
    paginate to next_page_token exhaustion

Corporate actions:

    GET https://data.alpaca.markets/v1/corporate-actions
    symbols=SPY
    region=us
    sort=asc
    all returned supported action types
    paginate to next_page_token exhaustion

Coverage:

    [2016-01-01T00:00:00Z, 2026-10-24T00:00:00Z)

Partitions:

    DEVELOPMENT  [2016-01-01T00:00:00Z, 2020-01-01T00:00:00Z)
    WALK_FORWARD [2020-01-01T00:00:00Z, 2024-01-01T00:00:00Z)
    FINAL_HOLDOUT[2024-01-01T00:00:00Z, 2026-10-24T00:00:00Z)

Open development root:

    F:\AI\ai-trading-bot\data\research\arch146-v1

Holdout custody root:

    F:\AI\research-holdout\arch146-v1

No path is created by this validation plan.

## Architecture-review findings that future enforcement must cover

### Full-file CSV inspection

CSVHistoricalDataProvider parses and validates the complete symbol CSV before
filtering a requested interval. A file containing holdout rows is therefore
ineligible as a development input even if a request excludes those rows.

146-A must prove the admitted OPEN normalized file ends before
2024-01-01T00:00:00Z and contains no final-holdout row.

### Architecture-145 logical fingerprint bridge

Architecture 145-A requires one historical_data_fingerprint across all three
policy partitions. Current canonical historical fingerprint material includes
request bounds, provider identity and OHLCV values, so physically split OPEN and
FINAL_HOLDOUT files necessarily have distinct physical-partition fingerprints.

146-A must add a separate immutable dataset snapshot/commitment layer. It may not
rewrite 145-A. Tests must prove a full logical fingerprint is externally bound to
the two exact partition manifests while each physical partition keeps its own
current canonical fingerprint.

### Corporate-action semantics

RAW bars are not adjusted. Tests and future acquisition evidence must distinguish:

- raw OHLCV;
- cash-dividend provenance;
- split/stock-dividend/spin-off provenance;
- symbol/name change or other continuity events.

No test may relabel adjusted prices as RAW. Current backtest return metrics must
remain described as price return, not total return, unless separately changed.

## Required Architecture 146-A source tests

A future 146-A implementation must prove at least:

1. exact schema fields and deterministic UUID5 identities for partition manifest
   and dataset snapshot;
2. canonical JSON roundtrip and rejection of unknown/missing/duplicate fields;
3. paths, clocks, hostnames, PIDs, locale, object IDs and ambient hash never enter
   semantic identity;
4. file SHA256, byte size, row count, interval, symbol, provider semantics and
   canonical historical fingerprint are all bound;
5. changing any semantic field changes identity;
6. an OPEN manifest cannot contain a timestamp at or after the holdout boundary;
7. a HOLDOUT manifest cannot contain a timestamp before its boundary;
8. overlap, reversed intervals, gaps in the frozen partition calendar or wrong
   role ordering fail closed;
9. duplicate/unsorted timestamps fail;
10. nonfinite/nonpositive prices, invalid OHLC relationships and invalid volume
    fail under existing public bar/CSV rules;
11. missing regular XNYS sessions are explicitly surfaced and cannot be silently
    filled with zeros;
12. raw vendor-page order/digests and normalized bytes reconcile;
13. corrupt raw or normalized bytes fail;
14. an IEX feed, adjusted bars, changed asof, changed currency, alternate symbol
    or alternate vendor fails the v1 contract;
15. corporate-action sidecar digest is mandatory;
16. a self-consistent partition manifest alone cannot claim membership in a
    dataset snapshot;
17. a self-consistent dataset snapshot alone cannot prove physical bytes without
    external verification;
18. OPEN and HOLDOUT physical fingerprints may differ while the privileged full
    logical fingerprint remains one separately verified snapshot commitment;
19. existing Architecture-145 schemas/namespaces/identities remain byte/behavior
    unchanged;
20. no test imports or calls provider, credential, scheduler, production,
    broker/paper or host-ACL capability.

All tests use synthetic fixtures only and a fresh external basetemp.

## Future acquisition/custody validation

Architecture 146-B, not 146-A, owns real acquisition and host custody. Before any
network call it must separately prove:

- exact current source HEAD/TREE and terminal CI;
- exact reviewed endpoints/query semantics;
- current Alpaca entitlement permits SIP historical access;
- current vendor terms permit the intended local private research use;
- open and holdout destinations are absent or exact immutable replay targets;
- holdout custody root ACL is exact and protected;
- no ordinary development process can enumerate/open holdout content;
- raw responses and pagination can be durably persisted without ordinary logs
  containing holdout OHLCV.

After acquisition it must reconcile:

- every page/request and digest;
- normalized CSV bytes;
- row counts and complete XNYS session expectations;
- partition boundaries;
- corporate actions;
- OPEN/HOLDOUT manifests;
- full dataset snapshot commitment;
- no tracked source/data mutation.

Unexpected or partially persisted state is STOP/reconciliation; no blind retry.

## No-effect accounting for 146-A

146-A source/tests must establish:

    PROVIDER_CALLS=0
    CREDENTIAL_READS=0
    HOLDOUT_HOST_READS=0
    HOLDOUT_HOST_WRITES=0
    ACL_MUTATIONS=0
    STRATEGY_RUNS=0
    BACKTEST_RUNS=0
    ARCH145_HOLDOUT_ADMISSIONS=0
    ARCH145_ELIGIBILITY_CREATED=0
    ARCH145_B_BUNDLES=0
    PRODUCTION_EFFECTS=0
    PAPER_EFFECTS=0
    BROKER_EFFECTS=0
    LIVE_EFFECTS=0

## Publication discipline

146-A will be a separate source checkpoint from this design. It should use a new
feature worktree from the then-current reviewed develop tip, focused tests, Ruff
check/format-check and diff-check, one atomic commit, one ordinary push and one
terminal CI admission. No acquisition follows automatically from source
acceptance.

## 146-A source verification surface (pending review)

Synthetic in-memory fixtures cover the two exact contracts, canonical rejection,
field binding, physical containment/order/OHLCV, external raw/normalized/sidecar
integrity, missing/unexpected sessions, distinct physical/full fingerprints,
full reconstruction, OPEN-only commitments and the additive policy bridge.
The accepted Architecture-145 source blob and its existing focused tests remain
unchanged.

The source-only checkpoint is
`arch146-a-historical-research-dataset-enforcement` on
`feature/research-arch146-a-historical-research-dataset-enforcement-current`.
The branch uses the pre-existing `feature/research-*` push family. Exact runner
registration selects CI-owned FULL; no duplicate local FULL/ROBINHOOD is needed.
Preflight/execute/remote effect admission are absent. Current supported test
inventory gains one experiments module automatically; historical required
baselines and predecessor pin maps remain frozen behind an additive successor.

Calendar coverage uses existing public NYSE rules, including their existing
historical-calendar limitations. A real acquisition must reconcile any published
calendar discrepancy separately; synthetic PASS does not certify real coverage.
Opaque raw-page and corporate-action digest verification is integrity evidence,
not proof of provider pagination, normalization economics or corporate-action
admissibility. No real data, acquisition or holdout authority follows.
