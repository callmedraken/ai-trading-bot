# Baseline moving-average strategy and offline command

The first baseline strategy is a deterministic, stateless moving-average
crossover for one long-only symbol of daily bars. It consumes only a
`BacktestContext` and returns a `TradeProposal` or `None`; risk validation,
orders, fills, and accounting remain outside the strategy.

## Public API

`MovingAverageCrossoverConfig` contains positive `short_window` and
`long_window` integers plus a positive finite Decimal `desired_quantity`.
The long window must exceed the short window. Invalid configuration raises
`MovingAverageCrossoverConfigError`.

`MovingAverageCrossoverStrategy.evaluate(context)` uses closing prices from
the immutable history ending at the current bar. It needs `long_window + 1`
bars so both previous and current averages can be calculated.

## Signal and position semantics

A bullish crossover requires the previous short average to be less than or
equal to the previous long average and the current short average to be
strictly greater than the current long average. A bearish crossover reverses
those comparisons. Equality at the current bar is not a crossover; equality
at the previous bar may lead into one.

The crossover is detected before account state is examined. A bullish signal
is actionable only while flat, and a bearish signal only while invested.
Filtering a genuine signal because of account state does not defer it: the
strategy will not buy or sell later merely because the averages remain on the
same side. Buy proposals use configured desired quantity. Sell proposals use
the complete quantity in `BacktestContext.positions`.

Proposal identifiers are UUID5 values derived from a fixed strategy namespace,
run ID, short and long windows, canonical desired quantity, step index, and
side. Proposal timestamps equal the current source bar timestamp exactly.

## Offline command

From the repository root, run:

```text
python -m scripts.run_backtest --csv-root tests/fixtures/backtesting --symbol MATEST --start 2026-01-02T05:00:00Z --end 2026-01-16T05:00:00Z --short-window 2 --long-window 3 --quantity 10
```

The command composes only the local CSV provider, deterministic NYSE calendar,
backtest engine, and baseline strategy. It constructs explicit conservative
risk limits, including an estimated commission equal to fixed commission.
It never downloads data or connects to a broker.

Fixture bars use source-provided timestamps such as 20:00 UTC that remain on
their intended New York local calendar dates. These timestamps are daily-bar
identifiers supplied by the source; they are not inferred or asserted NYSE
closing timestamps.

The console summary reports symbol, bar count, starting and final cash, final
equity, realized and unrealized profit and loss, proposal and fill counts,
approved/resized/rejected risk-decision counts, end-of-data proposal count,
and final position.

Optional `--json-report PATH` writes numeric report schema version 2. Its deliberate
sections are configuration, summary, final positions, proposals, risk
decisions, fills, and equity history. Decimal values are strings, timestamps
are ISO-8601 strings, UUIDs are canonical strings, enums use their values, and
symbols use normalized ticker strings. Internal engine objects are not
recursively serialized.

Performance analytics now extend this command and its deliberate numeric JSON
schema as documented in `09-performance-analytics.md`.

## Deferred scope

Networking, broker connectivity, Robinhood, AI, optimization, multiple
symbols, concurrent orders, performance ratios, charting, adjusted prices,
and intraday signals remain outside this feature.
