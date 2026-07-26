# Alpaca daily-snapshot capture validation

## Scope

Milestone-B tests use injected fake transports and fake HTTPS connection
factories only. No test opens a network socket, reads real credentials,
contacts Alpaca, invokes paper runtime, or creates files outside pytest
temporary directories.

## Provider and request coverage

Focused tests prove:

- the exact provider descriptor remains fixed
- EST and EDT request targets match reviewed golden strings
- symbols retain caller order
- timeframe, bounds, limit, RAW, disabled symbol mapping, SIP, USD, and sort are
  explicit
- no page token or authentication value enters the request target or public
  request representation
- each New York local midnight is converted independently, including a
  daylight-saving transition vector
- one provider-neutral capture performs exactly one transport call
- the injected clock is read once for `requested_at` and once after the
  successful entity read for `captured_at`
- a non-null next-page token rejects without follow-up
- SIP entitlement failure does not fall back to IEX

## Transport and redaction coverage

Fake connection tests prove:

- fixed verified TLS, host, port, method, timeout, and headers
- authentication is inserted only at the concrete transport boundary
- one response is read in fixed 64 KiB chunks
- entity SHA-256 and byte length match the same streamed read
- 4 MiB limits are enforced
- compression, conflicting length/transfer headers, invalid media types,
  duplicate request IDs, and missing successful request IDs fail closed
- every non-200 status is sanitized
- timeout, TLS, socket, and HTTP failures do not expose lower exception text
- test credentials do not appear in stdout, stderr, exception or object
  representations, serialized artifacts, request targets, or output paths
- a socket-opening sentinel is never reached

## Parsing and provider-neutral mapping

Tests cover:

- strict UTF-8 JSON and duplicate-key rejection
- exact root and bar field sets
- optional USD currency
- direct `Decimal` parsing without float conversion
- exact nonnegative integer volume and trade count with `bool` rejection
- optional trade count, VWAP, and exchange validation without canonical
  promotion
- provider response order and sequential zero-based ordinals
- source-payload hash, length, media type, and request-ID retention
- delegation of caller-order normalization, complete-universe validation,
  temporal diagnostics, canonical bar evidence, audit evidence, and UUID5
  identity to unchanged Milestone-A code

## Configuration and output coverage

Tests prove:

- the exact version-one configuration schema
- canonical UUID and symbol text
- exact calendar, provider, feed, timeframe, and adjustment
- duplicate, missing, unknown, and nonstandard JSON rejection
- destination validation precedes credential access
- rejection and in-memory verification failures create no staging
- exact and case-fold final/staging collisions are rejected
- staging uses exclusive creation and retains exact canonical bytes
- staged verification requires expected hash, length, model equality, and
  unchanged snapshot ID
- hard-link finalization is no-clobber and has no rename or copy fallback
- an unsupported hard link cleans only invocation-owned staging
- a concurrent final-name winner is preserved
- a post-install staging unlink failure returns success with a warning
- equivalent captures in separate destinations have identical identity, bytes,
  hash, and length

## Regression commands

```text
pytest tests/market_data/test_alpaca_daily_snapshot.py
pytest tests/market_data/test_alpaca_http.py
pytest tests/cli/test_daily_snapshot_config.py
pytest tests/cli/test_daily_snapshot_capture.py
pytest tests/scripts/test_capture_daily_market_snapshot.py
pytest tests/market_data/test_daily_snapshot_*.py
pytest
ruff check .
ruff format --check .
git diff --check
```

Public API and thin-script imports are smoke-tested separately. Existing
Milestone-A golden vectors must remain byte-for-byte unchanged.
