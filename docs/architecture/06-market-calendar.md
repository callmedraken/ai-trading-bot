# Market calendar

The market-calendar layer identifies deterministic regular NYSE trading
session dates for future historical-data and backtesting workflows. It exposes
a source-independent `MarketCalendar` protocol, immutable `TradingSession`
date values, immutable `TradingSessionRange` results, and an offline
`NYSEMarketCalendar` implementation.

Public methods accept timezone-aware `datetime` values. Inputs are normalized
to UTC, converted to `America/New_York`, and reduced internally to the
exchange-local `date`. `TradingSession` deliberately stores a `datetime.date`;
it does not represent an opening or closing time. Ranges retain their original
request bounds normalized to UTC and apply exchange-local `[start, end)` date
semantics.

A regular session is a Monday through Friday that is not a modeled NYSE
holiday. The deterministic rules cover New Year's Day, Martin Luther King Jr.
Day, Washington's Birthday, Good Friday, Memorial Day, Juneteenth from 2022,
Independence Day, Labor Day, Thanksgiving, and Christmas. Saturday and Sunday
observance rules are explicit, including the NYSE exception that does not move
a Saturday New Year's Day to the prior year-end Friday. Columbus Day and
Veterans Day remain sessions. Easter and Good Friday use a pure-Python
Gregorian computus.

The supported range is exposed as `MIN_SUPPORTED_YEAR` (1998) through
`MAX_SUPPORTED_YEAR` (2100). Dates outside it fail closed. Each calculated
year's holidays are stored in a deterministic per-instance cache as a
`frozenset[date]`. Next and previous searches use iterative calendar-day loops.
The implementation reads neither a clock nor external data, so identical
inputs produce identical results.

This version does not calculate market hours, half days, emergency closures,
presidential funeral closures, circuit breakers, or intraday schedules. Future
extensions may add versioned official schedules, richer session models, other
exchanges, and explicit early-close metadata without changing the core
calendar protocol.

The daily snapshot boundary binds this implementation to an explicit versioned
XNYS descriptor. Because this calendar has dates but no close/finalization
times, snapshot schema 1 accepts only the most recent modeled session strictly
before the exchange-local request date. It does not infer same-day completion.
