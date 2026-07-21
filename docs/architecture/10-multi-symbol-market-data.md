# Multi-symbol historical market data

The multi-symbol market-data layer composes the existing source-independent
`HistoricalDataProvider`. `CoordinatingHistoricalDataProvider` issues one
single-symbol request at a time in requested-symbol order, then aligns the
validated results into an immutable `MultiSymbolHistoricalDataResult`. CSV
parsing and all existing single-symbol APIs remain unchanged.

## Public contract and canonical representation

`MultiSymbolHistoricalDataRequest` stores a nonempty, duplicate-free tuple of
`Symbol` values in caller-specified order. Every symbol shares one UTC
half-open `[start, end)` interval, `Timeframe`, `AdjustmentType`, and
`MissingBarPolicy`.

The canonical result is timestamp-first: `frames` is a strictly increasing
tuple of `AlignedMarketFrame` values. A frame contains one exact normalized UTC
timestamp, an immutable mapping of available symbols to their exact `Bar`, and
the ordered complement as `missing_symbols`. Mapping and missing-symbol
iteration follow requested-symbol order. `bars_for(symbol)` derives an
immutable `SymbolBars` view in frame order without maintaining duplicate
mutable state. `frame_at(timestamp)` normalizes one aware datetime to UTC and
performs exact matching only.

Aligned timestamps are source-provided bar identities. They are not inferred
NYSE sessions, market opens, market closes, nearest timestamps, or local-date
matches. `TradingSession` remains the date-based concern of the separate
market-calendar layer.

## Alignment and missing data

`MissingBarPolicy.UNION` is the default. It sorts the union of all exact bar
timestamps, retains every observation, omits unavailable symbols from a frame
mapping, and lists them explicitly in `missing_symbols`. Every union frame has
at least one real bar. Union does not make an incomplete frame suitable for
portfolio valuation: future backtesting must explicitly request intersection
or reject incomplete frames.

`MissingBarPolicy.INTERSECTION` sorts the timestamp intersection. Every frame
contains every requested symbol and has no missing symbols. Neither policy
forward-fills, backfills, interpolates, substitutes sentinel prices, or treats
missing data as zero.

Existing `HistoricalDataResult` permits zero bars. Union therefore retains an
empty constituent symbol as missing in every frame when another symbol has
data. An empty constituent makes intersection empty. An empty alignment under
either policy raises `EmptyAlignedHistoricalDataError`.

## Validation, failure behavior, and determinism

Requests defensively copy symbols, preserve their order, normalize aware
timestamps to UTC, reject duplicates, reject empty universes, and require a
valid interval and enum values. Frames defensively copy caller mappings,
reconstruct available entries in requested order, validate exact symbol and
timestamp agreement, and wrap only the new mapping in `MappingProxyType`.
Results validate nonempty ordered frames, interval containment, universe
agreement, at least one bar per frame, and complete intersection frames.

At the provider boundary, every constituent result must be a
`HistoricalDataResult` whose request equals the exact derived single-symbol
request. Constituent provider and CSV exceptions propagate unchanged. All
constituents load before alignment is returned, so failures expose no partial
result. The coordinator owns a stable provider name derived from the wrapped
provider class; constituent `provider_name` equality is not required and
per-symbol provenance is deferred.

No mutable indexes or caches exist. Construction performs full validation;
accessors perform only argument checks and immutable lookups or scans. Equal
requests and equal provider data produce value-equal results independent of
mapping identity, provider object identity, or filesystem path formatting.

## Calendar independence and compatibility

The coordinator does not depend on `MarketCalendar`, infer exchange-local
dates, accept expected sessions, or validate holidays. A future orchestration
layer may combine aligned timestamps with an explicit timestamp-to-session
policy. The current single-symbol provider protocol, CSV provider, domain
models, calendar, and backtest engine remain unchanged.

## Deferred scope

Multi-symbol backtesting, synchronized valuation policy, timestamp-to-session
mapping, data imputation, corporate-action adjustment implementation, intraday
alignment, caching, persistence, streaming, parallel loading, heterogeneous
per-symbol provenance, pandas, NumPy, networking, brokers, AI, scenario
generation, portfolio optimization, CUDA, RAPIDS, cuOpt, and cuFOLIO remain
deferred.
