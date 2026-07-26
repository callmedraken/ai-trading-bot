# Deterministic daily market-data snapshot

## Milestone-A boundary

The daily snapshot subsystem accepts one provider-neutral response for one
caller-owned finite symbol universe and produces either one complete immutable
snapshot or a deterministic rejection. It does not implement an HTTP adapter,
credentials, provider schema, CLI, filesystem output, scheduling, caching,
pagination, retry, fallback, strategy, paper cycle, risk evaluation, broker
submission, or automatic research-result use.

The subsystem reuses `Symbol`, `Bar`, `Timeframe.DAY_1`,
`AdjustmentType.RAW`, `TradingSession`, and the existing `MarketCalendar`
behavior. It does not change historical CSV data, aligned historical data,
calendar calculations, paper runtime behavior, or research transport.

## Calendar binding and completed session

`CalendarDescriptor` identifies one exact calendar implementation. Schema 1
accepts only:

```text
calendar_id: XNYS
version: nyse-regular-sessions-1998-2100-v1
exchange_timezone: America/New_York
```

An `IdentifiedMarketCalendar` must expose the same descriptor as the capture
request. `BoundMarketCalendar` can bind the existing `NYSEMarketCalendar`
without changing it.

The target is frozen before the provider attempt. It is the most recent modeled
XNYS session strictly before the New York date of the aware, UTC-normalized
`requested_at`. Same-local-date data is never accepted. This conservatively
avoids inferring close or finalization times that the date-only calendar does
not model.

## Provider-neutral request and response

`DailySnapshotCaptureRequest` contains a caller UUID, 1-100 unique `Symbol`
values in caller order, `requested_at`, the exact calendar descriptor, daily
timeframe, and RAW adjustment.

`DailyProviderRequest` adds the frozen target and a nonsecret
`ProviderDescriptor`. A `DailySnapshotProvider.fetch` call represents exactly
one request and one response. `capture_daily_snapshot` invokes it once and
never retries.

`DailyProviderResponse` retains the exact request, provider-order candidates,
capture and optional provider-as-of timestamps, optional remote request ID,
source-payload SHA-256/length/media-type evidence, and an explicit pagination
completion flag. Source payload evidence contains no provider-specific schema
or raw payload bytes.

Candidates remain untrusted until acceptance. Accepted values use the existing
`Bar` constructor, so OHLC prices are exact finite positive `Decimal` values,
volume is an exact nonnegative integer excluding `bool`, timestamps are aware
and normalized to UTC, and existing OHLC invariants apply.

## Complete acceptance and diagnostics

Acceptance requires exactly one valid target-session candidate for every
requested symbol, no unexpected symbol, exact sequential zero-based response
ordinals, and a complete nonpaginated response. Provider response order is
retained in audit evidence; accepted bars are normalized into caller symbol
order.

Missing, extra, duplicate, malformed, stale, future, non-session,
timestamp/session mismatch, and mixed-session values reject the entire
response. There is no partial snapshot, fill, inference, fallback, or cache.

All independently discoverable diagnostics are retained. Their fixed order is:

1. request/response mismatch
2. incomplete pagination
3. invalid response ordinal
4. malformed candidate
5. timestamp/session mismatch
6. unexpected symbol
7. duplicate symbol
8. missing symbol
9. non-session
10. mixed session
11. future session
12. stale session

Top-level rejection classification precedence is:

1. `REQUEST_RESPONSE_MISMATCH`
2. `INCOMPLETE_RESPONSE`
3. `MALFORMED_CANDIDATE`
4. `UNEXPECTED_SYMBOL`
5. `DUPLICATE_SYMBOL`
6. `MISSING_SYMBOL`
7. `NON_SESSION`
8. `MIXED_SESSION`
9. `FUTURE`
10. `STALE`

`ACCEPTED` requires a complete snapshot, `CURRENT` freshness, and no rejection
diagnostics. `REJECTED` requires no snapshot and at least one diagnostic.

## Canonical material, evidence, and identity

Canonical scalars are ASCII and framed as
`<base-10-byte-length>:<value>`. Canonical Decimal text is exponent-free,
context-independent, removes insignificant fractional zeros, and renders every
signed zero as `0`.

Canonical bar material version `daily-market-snapshot-bars-v1` binds each
caller-order position, symbol, session, normalized UTC source timestamp, OHLC,
and volume. `CanonicalBarsEvidence` retains its SHA-256 and exact byte length.

Snapshot UUID5 material version `daily-market-snapshot-identity-v1` binds:

- caller request UUID and symbol order
- exact calendar descriptor and target session
- timeframe and adjustment
- complete provider descriptor, including feed
- complete accepted canonical bars

It excludes requested/capture/provider clocks, remote request ID,
source-payload evidence, serialized bytes, paths, credentials, and mutable
services.

Audit material version `daily-market-snapshot-audit-v1` separately binds the
snapshot ID, requested and captured timestamps, optional provider-as-of and
remote request ID, source-payload evidence, and provider response symbol order.
Its SHA-256 changes without changing the snapshot identity.

## Canonical JSON and offline replay

Schema 1 has one UTF-8 JSON representation: sorted keys, compact separators,
`ensure_ascii=True`, canonical scalar text, and one final newline. The payload
limit is 4 MiB.

Strict parsing rejects BOM, invalid UTF-8, duplicate, missing, and unknown
fields, nonstandard constants, comments, trailing data, wrong scalar types,
noncanonical UUID/hash/timestamp/Decimal/symbol text, and invalid immutable
models.

Offline verification accepts bytes and an identified calendar. It optionally
checks caller-supplied outer SHA-256 and byte length, strictly parses the
snapshot, recomputes the prior-session rule, completeness, session/timestamp
mapping, canonical bar evidence, UUID5, audit hash, and canonical serialized
bytes. It invokes no provider, clock, runtime, network, broker, or filesystem
output behavior.

Replay accepts only a complete `PASS` result and exposes the exact immutable
retained bars. It deliberately implements neither a provider interface nor a
paper-runtime adapter.

## Deferred work

The fixed Alpaca provider adapter, runtime credential boundary, one-attempt
HTTPS transport, capture command, and no-clobber staged snapshot output are
implemented separately by `57-alpaca-daily-snapshot-capture.md`. A standalone
verification command, official exchange schedules, same-day post-close
capture, raw response retention, signatures, schedulers, paper-runtime
integration, and broker behavior remain deferred.
