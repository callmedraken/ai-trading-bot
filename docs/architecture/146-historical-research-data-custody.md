# Architecture 146 — Historical Research Data Custody and Partition Contract

Status: **DESIGN ACCEPTED / DOCUMENTATION ONLY.** This is not Architecture 145-B.
No acquisition, import, source enforcement, holdout admission/evaluation,
promotion, production deployment or trading authority is granted by this design.

## Problem and verified prerequisite failure

At design base:

    develop HEAD a637f1b34565a715c14874d0f9a9686388319c16
    TREE         e870cc8f28138076d1e247eb92358d88a89c2f26
    Source Gates #716 / 40169845896 attempt 1: SUCCESS

The repository-local data directory is empty. Repository CSV files inventoried
during the prerequisite diagnostic are synthetic examples/test fixtures and are
not research datasets. No historical research campaign ran; performance,
drawdown, turnover, trades/fills, folds, sensitivity, stability and stress
reconciliation remain NOT EVALUATED.

The existing CSVHistoricalDataProvider validates every row in a symbol CSV before
date filtering. Therefore a development reader pointed at a file that also
contains final-holdout rows has inspected those rows even when its request uses a
narrower interval. Request boundaries alone are not a holdout-sealing control.

Architecture 145-A currently binds one logical historical_data_fingerprint across
its DEVELOPMENT, WALK_FORWARD and FINAL_HOLDOUT partition records. That existing
fingerprint semantics include request bounds, provider identity and OHLCV
material. Physically split files therefore cannot be represented as though their
individual current fingerprints were one identical full-dataset fingerprint.
Architecture 146 requires an additive manifest/custody enforcement layer rather
than reinterpreting or modifying accepted 145-A schemas.

## Design decisions

### Initial instrument and research scope

Architecture 146 v1 is deliberately single-symbol:

    symbol               SPY
    security class       US ETF
    primary calendar     XNYS / NYSE regular sessions
    strategy family      not selected by this data contract

SPY matches the current production/research lineage without selecting a specific
research candidate or parameter configuration. QQQ and any multi-symbol universe
remain future additive dataset snapshots. A future stock universe requires
point-in-time membership/source review so survivorship bias is not hidden by a
present-day constituent list.

This data contract does not infer a research candidate from production history,
tests, filenames, prior rankings or current strategy parameters. Candidate and
configuration authority remain separate Architecture-145 inputs.

### Vendor and acquisition semantics

The approved v1 source design is Alpaca Market Data API historical stock data,
using the same market-data family already reviewed elsewhere in the repository.

Bars request semantics are frozen as:

    host          data.alpaca.markets
    endpoint      GET /v2/stocks/SPY/bars
    timeframe     1Day
    adjustment    raw
    asof          -
    feed          sip
    currency      USD
    sort          asc
    pagination    follow next_page_token until absent

There is no IEX fallback, alternate vendor fallback, inferred-bar fallback,
adjusted-data substitution or synthetic fill-in. If SIP access/entitlement is
unavailable at acquisition time, acquisition BLOCKS and is separately reviewed.

Corporate-action provenance uses the same vendor:

    endpoint      GET /v1/corporate-actions
    symbol        SPY
    region        us
    sort          asc
    pagination    follow next_page_token until absent
    types         all supported returned types

The future acquisition checkpoint must reverify the then-current Alpaca API
contract, account entitlement and permitted use before network access. This
design permits local private development/research only and no redistribution of
vendor data. A change in vendor terms or feed semantics is a STOP/review event,
not an automatic substitution.

### Coverage and ex-ante partition calendar

The v1 semantic coverage is frozen before acquisition or result inspection:

    FULL COVERAGE
    [2016-01-01T00:00:00Z, 2026-10-24T00:00:00Z)

    DEVELOPMENT
    [2016-01-01T00:00:00Z, 2020-01-01T00:00:00Z)

    WALK_FORWARD
    [2020-01-01T00:00:00Z, 2024-01-01T00:00:00Z)

    FINAL_HOLDOUT
    [2024-01-01T00:00:00Z, 2026-10-24T00:00:00Z)

These are half-open UTC boundaries. Only actual admitted XNYS regular-session
bars are present; non-session dates are not synthesized. Walk-forward fold
granularity inside the WALK_FORWARD parent interval remains a later frozen
Architecture-145 policy decision and must be chosen before its results are used
for selection.

The coverage end is the day after the last completed Friday session available at
this design checkpoint. A future extension beyond 2026-10-24 is a new snapshot
version, never an in-place append to v1.

### Daily-bar timestamp and price semantics

Vendor daily bars are trade aggregates for the New York trading day. Preserve
the vendor timestamp and normalize its timezone-aware instant to UTC for the
repository CSV representation. Do not relabel a bar using an acquisition clock or
filesystem date.

v1 is RAW only:

- no split adjustment;
- no dividend adjustment;
- no spin-off adjustment;
- no symbol mapping because asof=-;
- no total-return transformation;
- no synthetic prices;
- no zero-valued bars for missing sessions.

The normalized export contains exactly:

    timestamp,symbol,open,high,low,close,volume

with the existing CSVHistoricalDataProvider validation rules.

Cash dividends are not credited by the current historical backtest path.
Therefore v1 return metrics are explicitly **price-return research metrics**, not
SPY total return. They must never be labeled total-return performance.

Cash-dividend events are retained as provenance but do not alter v1 OHLCV.
Any split, stock dividend, spin-off, symbol/name change, merger, redemption,
worthless removal or other event capable of invalidating continuity requires an
explicit acquisition/research admissibility decision before the snapshot is used.
No event is silently adjusted away.

### Storage and custody layout

The existing repository-local data root remains the development anchor. The
exact v1 open-data root is:

    F:\AI\ai-trading-bot\data\research\arch146-v1

It contains only material that development/walk-forward consumers may inspect:

    vendor-raw\open\...
    normalized\open\SPY.csv
    manifests\open-partition.json
    manifests\holdout-commitment.json
    manifests\dataset-commitment.json

The normalized open SPY.csv contains only DEVELOPMENT + WALK_FORWARD rows:

    [2016-01-01T00:00:00Z, 2024-01-01T00:00:00Z)

No final-holdout OHLCV bytes may exist anywhere under the repository, a Git
worktree, ordinary F:\AI\temp, test basetemp, generated-report directory or the
open-data root.

The physically separate final-holdout custody root is:

    F:\AI\research-holdout\arch146-v1

Its intended future contents are:

    vendor-raw\holdout\...
    normalized\holdout\SPY.csv
    corporate-actions\...
    manifest.json

The root does not exist merely because this design names it. No directory or ACL
mutation is authorized in Architecture 146 design.

Future custody implementation must use a protected Windows DACL owned by
BUILTIN\Administrators with only:

- BUILTIN\Administrators: FullControl;
- NT AUTHORITY\SYSTEM: FullControl.

No ordinary user ACE, trading-service ACE, worktree account or broad inherited
ACE is permitted. The DACL must be protected. Normal development research runs
must be unelevated and unable to open or enumerate the holdout root.

Administrator membership is not treated as cryptographic secrecy from the human
operator. The control is capability separation and auditable non-use: normal
research tooling lacks the capability; deliberate elevation crosses a reviewed
holdout-admission boundary.

### Copy and temporary-file rules

Holdout vendor bytes and normalized holdout CSV must never be copied into:

- repository/worktree paths;
- ordinary development data roots;
- ordinary temporary directories;
- GUI/report directories;
- test fixtures.

Future holdout evaluation reads only through the separately reviewed custody
surface. Any temporary material required by a future implementation must retain
equivalent protected ACLs, exact identity evidence and fail-closed cleanup
semantics reviewed before use. Architecture 146 design authorizes none.

### Immutable snapshot and manifest identity

Future source enforcement must add immutable additive schemas rather than
changing Architecture 145-A:

    historical-research-partition-manifest/v1
    historical-research-dataset-snapshot/v1

Reserved deterministic UUID5 namespaces:

    partition manifest  8fdd2b9e-be93-5aaf-84b2-b9b7a7381edb
    dataset snapshot    61a9b6ef-3fe3-564c-8f73-96478e0857a9

A partition manifest binds at least:

- schema/version and deterministic partition-manifest ID;
- role: OPEN or FINAL_HOLDOUT;
- symbol and XNYS calendar identity;
- UTC half-open interval;
- timeframe and RAW adjustment convention;
- vendor/provider descriptor, feed, currency and asof semantics;
- normalized schema/version;
- normalized file SHA256 and byte size;
- row count;
- first/last bar timestamp;
- canonical current historical-data fingerprint for that exact physical
  partition;
- raw vendor-page digests/order;
- corporate-action sidecar digest;
- normalization version.

The full dataset snapshot binds at least:

- schema/version and deterministic snapshot ID;
- SPY and complete coverage interval;
- exact DEVELOPMENT/WALK_FORWARD/FINAL_HOLDOUT boundaries;
- open partition-manifest ID;
- holdout partition-manifest ID;
- a custodian-computed canonical **full logical historical-data fingerprint** for
  the complete v1 bars;
- corporate-action provenance;
- vendor descriptor/semantics.

Paths, acquisition clocks, process IDs, hostnames and object identity do not
enter deterministic dataset IDs.

File SHA256 is an integrity field, not a replacement for repository historical
fingerprint semantics.

The public holdout commitment available to development may disclose only
non-price metadata needed for lineage verification: schema/version, snapshot ID,
partition-manifest ID, symbol, interval, row count, byte digest, canonical
historical fingerprint and corporate-action digest. It contains no OHLCV values.

### Architecture-145 compatibility boundary

Architecture 146 must not alter:

- ResearchStrategyRobustnessQualificationPolicy;
- ResearchStrategyRobustnessPartition;
- ResearchStrategyRobustnessEvidence;
- ResearchStrategyFinalHoldoutAdmission;
- ResearchStrategyLiveCanaryEligibility;
- any accepted Architecture-145 namespace, schema or identity.

A later Architecture-146 source checkpoint must instead introduce additive
dataset/partition manifest models plus verification functions proving:

1. the open physical partition is exactly the OPEN manifest material;
2. the holdout commitment belongs to the same immutable dataset snapshot;
3. the full logical historical fingerprint was produced by a privileged custody
   construction over exactly OPEN + FINAL_HOLDOUT content;
4. Architecture-145 policy partition bounds equal the frozen Architecture-146
   boundaries;
5. the policy historical_data_fingerprint equals the full logical fingerprint;
6. development and walk-forward evidence was produced only from the OPEN
   partition and never by opening holdout bytes;
7. holdout content becomes readable only after separate Architecture-145 holdout
   admission and exact frozen policy/candidate/source reconciliation.

A caller-supplied UUID or self-consistent manifest cannot establish these facts
without external verification.

## Acquisition and normalization boundary

Architecture 146 design performs no network call and creates no dataset.

The later acquisition/import checkpoint must be separately reviewed. It must:

- use the exact vendor endpoints/semantics above;
- preserve every raw response page in order;
- record SHA256 and bounded response metadata;
- paginate to completion;
- normalize deterministically to strict CSV;
- validate all rows and XNYS session coverage;
- reject duplicates, unsorted timestamps, malformed/nonfinite prices, invalid
  OHLC relationships and unexplained missing regular sessions;
- preserve raw bytes and normalized bytes immutably;
- never overwrite an existing snapshot;
- split OPEN and FINAL_HOLDOUT before making development material available;
- write holdout material directly to the protected custody surface;
- avoid rendering/logging holdout OHLCV into ordinary operator output;
- leave generated data and reports untracked.

No acquisition retry occurs after ambiguous partial persistence without a
separate reconciliation.

## Corporate actions, delistings and universe limitations

v1 is SPY-only and therefore makes no claim about point-in-time constituent
membership of an equity universe.

The corporate-action sidecar is mandatory provenance. Cash dividends are
recorded but not economically credited by the current RAW backtest. Other
continuity-changing events require review before use.

A future universe expansion must additionally bind:

- point-in-time constituent membership;
- listing/delisting history;
- symbol/CUSIP or equivalent durable identity mapping;
- survivor and non-survivor inclusion policy.

Current-symbol discovery must never be backfilled across history as if it were a
point-in-time universe.

## Authority boundary

Architecture 146 design grants zero authority for:

- network/provider calls;
- credential reads;
- dataset creation/import;
- holdout root creation or ACL mutation;
- holdout content reads;
- strategy/backtest execution;
- Architecture 145-B;
- eligibility construction;
- promotion;
- scheduler/runtime/deployment changes;
- paper/broker/live effects.

The production deployment candidate remains intentionally unfrozen through the
weekend.

## Next checkpoint

The next safe source checkpoint is **Architecture 146-A — historical research
dataset manifest and partition enforcement**.

146-A is pure/source-only. It implements canonical manifest/commitment models and
external verification over caller-supplied bytes/metadata using synthetic test
fixtures only. It must not create the real directories, read credentials, call
Alpaca, acquire data, open a real holdout, run Architecture 145-B or touch
production.

Only after 146-A source acceptance/integration may ChatGPT separately review an
Architecture 146-B bounded acquisition/custody checkpoint.
