# Daily market-data snapshot validation

## Scope

Milestone A is verified entirely with deterministic provider-neutral values.
Tests do not open sockets, read credentials, invoke a CLI, stage filesystem
output, or call trading workflows.

## Model and calendar coverage

Focused tests prove:

- one to 100 unique `Symbol` values retain caller order
- empty, duplicate, oversized, and wrong-type universes fail
- only `Timeframe.DAY_1`, `AdjustmentType.RAW`, and the exact XNYS descriptor
  are accepted
- aware request times normalize to UTC
- weekday, Monday, weekend, and holiday requests select the strictly prior
  modeled session
- a mismatched calendar descriptor fails before provider work
- a provider is invoked exactly once with the already-frozen target

## Acceptance coverage

Tests construct deterministic response envelopes and verify:

- provider order can differ while accepted bars use caller order
- original response symbol order remains separate audit evidence
- exact sequential response ordinals are required
- missing, unexpected, duplicate, malformed, stale, future, non-session,
  timestamp/session mismatch, mixed-session, and incomplete responses reject
- exact finite positive Decimal OHLC and existing `Bar` invariants apply
- boolean and other noninteger volumes reject
- every discoverable diagnostic is retained in fixed order
- top-level rejection uses the documented explicit precedence
- accepted results always contain one complete snapshot
- rejected results never contain a snapshot

## Golden deterministic vectors

Reviewed tests pin:

- canonical scalar and Decimal rendering
- complete canonical bar material
- canonical bar material byte length and SHA-256
- complete UUID5 identity material and snapshot UUID
- complete audit material and audit SHA-256
- canonical JSON byte length and SHA-256

The vectors also run Decimal rendering under a deliberately constrained ambient
context. Separate tests prove changing clocks, remote request ID, or source
payload evidence changes the audit hash but not snapshot identity.

## Serialization and verification coverage

The strict parser rejects:

- UTF-8 BOM and invalid UTF-8
- missing final newline, duplicate final newline, and trailing data
- duplicate, missing, and unknown fields
- NaN and other nonstandard JSON constants
- comments
- booleans where integers are required
- noncanonical UUID, UTC timestamp, Decimal, symbol, and SHA-256 text

Verification tests prove:

- exact canonical bytes pass and reconstruct the original immutable model
- optional outer byte-length and SHA-256 mismatches remain distinct
- bar evidence, audit evidence, and snapshot UUID are independently recomputed
- semantically valid pretty JSON is rejected as noncanonical bytes
- the supplied calendar descriptor must equal the retained descriptor
- replay rejects every non-PASS result
- successful replay returns the exact retained symbol and bar tuples

## Required implementation checks

During implementation run:

```text
pytest tests/market_data/test_daily_snapshot_*.py
pytest
ruff check .
ruff format --check .
git diff --check
```

Also import every new public model, provider-neutral function, serializer,
verifier, and replay function from `trading_bot.market_data`.
