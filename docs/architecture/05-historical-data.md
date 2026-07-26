# Historical market data

The historical market-data layer provides deterministic, offline daily bars to
a future backtest engine. A `HistoricalDataRequest` is passed to a
source-independent `HistoricalDataProvider`, which returns an immutable
`HistoricalDataResult`. Providers reuse the domain `Symbol` and `Bar` models.

Requests use timezone-aware timestamps normalized to UTC and a half-open
`[start, end)` interval. The initial timeframe is `Timeframe.DAY_1` (`"1D"`).
Adjustment intent may be raw, split-adjusted, or total-return, but the local CSV
provider supports `RAW` only and explicitly rejects adjusted requests.

`CSVHistoricalDataProvider` reads `<root_directory>/<SYMBOL>.csv` using the
standard library. Every file must contain exactly these headers, in any order:

```text
timestamp,symbol,open,high,low,close,volume
```

Every row is validated before interval filtering. Timestamps must be ISO-8601
with a timezone, prices are finite positive `Decimal` values, volume is a
nonnegative integer, symbols must match the requested file symbol, and domain
OHLC invariants apply. Malformed rows are never skipped, including rows outside
the requested interval. The provider validates the full file, sorts bars,
rejects duplicate timestamps, filters the requested interval, and then builds
the result. Results contain chronologically ordered bars and a nonblank
`provider_name`.

This layer does not download data, use pandas, interpret market calendars,
cache results, persist data, run strategies or backtests, execute orders,
connect to brokers, or call AI services. Adjustments, intraday data, calendars,
large-file indexing, provenance metadata, and network sources remain deferred.

The provider-neutral completed daily snapshot boundary documented in
`56-daily-market-data-snapshot.md` is separate from this historical-data
contract. It reuses `Symbol`, `Bar`, `Timeframe`, and `AdjustmentType` without
changing CSV parsing, historical requests/results, or their identities.
