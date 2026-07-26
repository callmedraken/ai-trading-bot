# Alpaca daily-snapshot capture

## Milestone-B boundary

Milestone B connects the provider-neutral completed-daily-snapshot boundary to
one fixed Alpaca Market Data API operation and one local artifact command. It
does not connect snapshots to paper runtime, strategies, risk, brokers, or
research selection. It implements no scheduler, retry, pagination follow-up,
provider fallback, cache, or raw-response artifact.

The provider contract was checked against Alpaca's official historical-bars,
market-data authentication, request-ID, plan-limit, SDK-model, and market-data
FAQ documentation on 2026-07-26. Provider-controlled facts are isolated in the
adapter. Selection of SIP, RAW, USD, no symbol remapping, one attempt, strict
schema handling, and all output behavior are project policy.

## Fixed provider semantics

The provider descriptor is:

```text
provider_id: alpaca-market-data
adapter_version: 1
operation: historical-stock-bars-v2-raw-usd-no-asof
feed: sip
```

The descriptor participates in the existing snapshot UUID5 identity. No
Milestone-A identity, canonical material, audit material, serializer, verifier,
or replay contract changes.

The adapter sends one `GET` to
`https://data.alpaca.markets/v2/stocks/bars`. Query parameters appear once in
this order:

```text
symbols=<caller-order comma-separated symbols>
timeframe=1Day
start=<target New York midnight converted to UTC>
end=<next New York midnight minus one microsecond converted to UTC>
limit=<symbol count>
adjustment=raw
asof=-
feed=sip
currency=USD
sort=asc
```

Start and end are derived as separate `America/New_York` local datetimes before
UTC conversion. The request never derives end by adding 24 UTC hours. It sends
no `page_token`, never follows `next_page_token`, and never falls back to IEX.

## Configuration and credentials

The strict version-one JSON configuration contains exactly:

```json
{
  "schema_version": 1,
  "request_id": "00000000-0000-0000-0000-000000000000",
  "symbols": ["SPY", "QQQ"],
  "calendar": {
    "calendar_id": "XNYS",
    "version": "nyse-regular-sessions-1998-2100-v1",
    "exchange_timezone": "America/New_York"
  },
  "timeframe": "1D",
  "adjustment": "RAW",
  "provider": {
    "provider_id": "alpaca-market-data",
    "adapter_version": 1,
    "operation": "historical-stock-bars-v2-raw-usd-no-asof",
    "feed": "sip"
  }
}
```

The loader rejects BOM, invalid UTF-8, duplicate, missing, or unknown fields,
nonstandard JSON constants, noncanonical UUID or symbol text, and every value
outside the fixed descriptors. `request_id` is caller-supplied.
`requested_at` is read from the injected UTC clock after configuration,
calendar, and destination-parent validation.

Trading API credentials are loaded at runtime from `APCA_API_KEY_ID` and
`APCA_API_SECRET_KEY`. They are rejected when missing, blank,
whitespace-padded, multiline, or containing CR, LF, or NUL. A private redacted
holder retains them only for the provider attempt. Public request and result
models, URLs, artifacts, logs, diagnostics, and exception messages contain no
credentials.

## HTTPS and response boundary

The standard-library transport uses `http.client.HTTPSConnection`, a verified
default TLS context, fixed host and port, a 15-second socket timeout, and an
injectable connection factory. It performs one GET without proxy discovery,
redirect handling, retry, SDK, subprocess, or third-party HTTP behavior.

The transport requests `application/json` with identity content encoding. It
reads the entity in 64 KiB chunks, rejects content above 4 MiB, and computes
SHA-256 and byte length during the same read. Duplicate or conflicting
Content-Length, Transfer-Encoding, Content-Encoding, Content-Type, or
X-Request-ID values fail closed. Compressed responses are unsupported.

Status must be exactly 200. Every other status produces a sanitized failure
containing only status, optional safe numeric provider code, and optional safe
request ID. Provider bodies and lower exception representations are not
exposed. A successful response requires exactly one printable ASCII
`X-Request-ID`.

Strict JSON parsing rejects duplicate keys, nonstandard constants, invalid
UTF-8, unknown root or bar fields, and wrong scalar types. Required bar fields
are `t`, `o`, `h`, `l`, `c`, and `v`; optional `n`, `vw`, and `x` values are
validated without becoming canonical bars. Prices parse directly as
`Decimal`. Volume and trade count require exact nonnegative integers excluding
`bool`. Optional top-level currency, when present, must be `USD`.

Observed symbol-map and array order become sequential zero-based response
ordinals. A null `next_page_token` means complete; a non-null string reaches
Milestone A as incomplete and causes whole-response rejection. `captured_at`
is read only after the complete successful entity body is read.
`provider_as_of` remains `None` because the endpoint exposes no documented
data-as-of timestamp.

## Capture and output

Capture validates configuration, calendar, and the existing real destination
directory before loading credentials. The existing provider-neutral capture
function freezes the prior modeled XNYS target before the one provider call and
performs all completeness, temporal, ordering, diagnostic, hashing, audit, and
identity work.

An accepted snapshot is serialized with the existing canonical serializer and
verified in memory before staging exists. Output names are:

```text
daily-market-data-snapshot-<snapshot-id>.json
.daily-market-data-snapshot-<snapshot-id>.json.staging
```

The destination must be an existing real directory. Exact and case-fold
collisions, symlinks, dangling links, detectable reparse points, parent
identity changes, and pre-existing staging are rejected. Staging is
exclusively created, receives the already verified bytes in one write, and is
flushed and `fsync`ed.

The staged file is safely reopened, bounded, and verified with expected
SHA-256 and byte length. PASS, exact model equality, and unchanged snapshot ID
are mandatory. Final exposure uses a same-directory no-clobber hard link and
has no copy or replacing-rename fallback.

Before final exposure, the invocation cleans only a regular staging file whose
filesystem identity matches the file it created. Once the final link exists,
the final artifact is never removed and success is not converted to failure.
A staging unlink or supported post-install durability failure becomes a
sanitized cleanup warning. Unsupported directory `fsync`, including portable
Python limitations on Windows, produces no warning.

## Command

```text
python scripts/capture_daily_market_snapshot.py \
  --config <path> \
  --destination-directory <existing-directory>
```

Exit codes are:

- `0`: success
- `2`: argparse usage
- `3`: configuration read or JSON failure
- `4`: configuration, domain, or calendar failure
- `5`: credentials, TLS, transport, HTTP status, or rate limit
- `6`: successful-HTTP schema, mapping, pagination, or acceptance rejection
- `7`: serialization, verification, destination, staging, cleanup, or finalization

A standalone verification CLI, raw-payload persistence, scheduler, retry,
fallback, pagination continuation, and paper-runtime integration remain
deferred.
