# Architecture 148-B2 — Read-only Intraday Acquisition Plan

Status: **B2-A SOURCE/CERTIFICATION ACCEPTED / FAST-FORWARD INTEGRATED;
B2-B ATTEMPT CONSUMED / BLOCKED / PAGE_LIMIT_REACHED / NO RETRY. B2-A-C1
CORRECTION REQUIRES A NEW SOURCE CHECKPOINT AND ACCEPTANCE.** This plan
authorizes no Alpaca credential read, provider request, Robinhood/broker
action, production mutation or FINAL_HOLDOUT access.

B2-A accepted/certified executable source:
`6957afa159647ece18af876289d8a20637cfc6eb` /
`43701fcaef23990a793359d08a8213d43e434780`. Feature source-gate
`44485930260` and develop source-gate `44489803571` are terminal SUCCESS;
develop reused the exact feature certification and ran no duplicate seven-lane
FULL. The canonical feature and documented local integration worktrees were
verified clean at that executable identity.

The previously documented docs-only invocation-source shortcut is no longer
available for the correction described here because B2-A-C1 changes executable
source and tests. Any future provider invocation requires a newly published and
certified exact source, independent ChatGPT source acceptance, integration and
canonical worktree catch-up, followed by review of a separately named fresh
successor invocation. It is not a retry of the consumed attempt.

## Consumed B2-B attempt

Attempt: `fd8aa437-c748-4d5b-a52f-1e58b2ca5953`
Retained directory:
`F:\AI\temp\arch148-b2-fd8aa437-c748-4d5b-a52f-1e58b2ca5953`
Outcome: CONSUMED / BLOCKED / PAGE_LIMIT_REACHED / NO RETRY.
Classification: ARCH148_B2_PROVIDER_STREAM_SCOPE_ASSUMPTION_DEFECT /
ARCH148_B2_PAGINATION_CEILING_UNDERSIZED.
Credential reads: 1. Provider attempts: 64. Successful pages: 64.
Unresolved intent: NONE. Automatic retry: FORBIDDEN.

The attempt requested QQQ only; TQQQ and SQQQ were never requested. Its 64 raw
pages contained 162426 unique QQQ bars from 2016-01-01T00:00:00Z through
2019-12-31T12:30:00Z. Exactly 78057 timestamps matched B1 regular-session slots
and 84369 did not. There were no duplicate timestamps. Every page retained a
next_page_token. Page sizes ranged from 2246 to 2669 bars, median 2568. The
attempt did not qualify the required B1 dataset. Robinhood, broker, order,
production, FINAL_HOLDOUT and baseline effects were all zero. This retained
evidence is immutable and must not be resumed, replayed or treated as retry
authority.

## Frozen predecessor

Design base:

```text
HEAD  e64353318a300dd93e9812c38ed346f77129840e
TREE  b358ffc33d3d378e37b1d08a3d61c2c29db93ad8
BRANCH feature/robinhood-live-prototype-current
DEVELOP e64353318a300dd93e9812c38ed346f77129840e
```

Architecture 148-B1 is accepted/integrated. Its core data, schedule, parser,
custody and simulator semantics remain unchanged.

## Authority split

148-B2-A is a source-only/fake-only implementation checkpoint. It may implement
the operator/evidence boundary described below and run fake/focused tests, Ruff,
diff/admission and mapped source certification. B2-A must perform zero real
credential reads and zero real provider calls.

The initial B2-B attempt recorded above is consumed and cannot be resumed or
retried. B2-A-C1 is a source-only/fake-only corrective checkpoint. Any future
real read-only acquisition requires its own separately reviewed fresh successor
invocation after the corrected exact source is published, certified, accepted,
integrated and reconciled locally. No provider or credential operation is
authorized by this plan.

## Provider and dataset contract

Use the accepted B1 request builder and page parser for QQQ, TQQQ and SQQQ in
that order. Each request is one symbol with `5Min` bars over OPEN
`[2016-01-01, 2024-01-01)`, inclusive provider end
`2023-12-31T23:59:59.999999Z`, `adjustment=all`, `asof=-`, SIP, USD,
ascending sort, requested limit 10000, and pagination through
`next_page_token=None`. Limit 10000 is a maximum, not an expected page size;
the provider may return fewer bars while more remain. Historical stock minute
bars include pre-market and aftermarket activity, and the endpoint provides no
regular-session-only filter. This provider behavior was independently
rechecked on 2026-11-18:
- [Stock bars](https://docs.alpaca.markets/us/reference/stockbars)
- [About market data](https://docs.alpaca.markets/us/docs/about-market-data-api)
- [Historical API](https://docs.alpaca.markets/us/docs/historical-api)

The provider end remains inclusive for the half-open OPEN dataset ending
2024-01-01. The accepted session/schedule contracts imply:

```text
OPEN sessions                    2012
early-close sessions               15
expected 5-minute slots/symbol  156396
expected total bars             469188
MAX_PAGES_PER_SYMBOL              192
MAX_PROVIDER_REQUEST_ATTEMPTS     576
minimum delay between request starts 0.5 seconds
```

Before projection, validate every parsed raw bar for exact requested symbol,
strict chronological order and duplicate prevention. Derive the exact accepted
slot set from B1 `expected_open_slots()`. Raw bars outside that set remain
byte-for-byte in their raw page artifacts but are excluded from the normalized
B1 dataset. The unchanged B1 dataset/custody constructor still requires exactly
156396 qualified regular-session bars per symbol, 469188 total, identical
QQQ/TQQQ/SQQQ timestamps and every existing B1 qualification. Missing,
duplicate, reordered, malformed or unexpected expected-slot data fails closed.

## Reuse requirements

B2-A must reuse, not fork:

- `trading_bot.experiments.arch148_intraday` request construction, page parser,
  collection semantics, dataset and custody models;
- `read_current_product_alpaca_secrets` for one current-product Windows
  credential scope;
- `StdlibAlpacaHistoricalBarsTransport` for fixed-host TLS GETs;
- the current source-authority/checkpoint route for the canonical feature branch.

Do not revive Architecture-146's interactive research credential source and do
not add environment credential fallback.

## Source admission

Before any output creation, and again immediately before credentials, after the
provider phase and before terminal SUCCESS, prove:

```text
canonical worktree
feature/robinhood-live-prototype-current
expected local HEAD/tree
canonical origin URL
tracked/index/untracked clean
origin feature HEAD == local HEAD
origin develop HEAD == local HEAD
FEATURE source authority PASS
PROSPECTIVE_DEVELOP source authority PASS
```

For a future invocation, operator flags `--expected-head` and `--expected-tree` bind the exact current reviewed source; the accepted B2-A executable provenance remains the predecessor identity recorded above.

A mismatch blocks
before any further provider request. Source drift discovered after a provider
attempt preserves the partial attempt and returns a blocked result; it never
retries or repairs source.

## Attempt durability and output

Use exactly one fresh directory:

```text
F:\AI\temp\arch148-b2-<canonical-uuid>
```

The parent must resolve exactly to the reviewed F:\AI\temp parent and every
existing ancestor must be non-reparse. The attempt path must not already exist.

Create an immutable attempt claim before credential access. Before each GET,
write a nonsecret create-once request-intent record. After a successful response,
write the result record and raw page bytes create-once before advancing
pagination. Request intent/result records must contain only bounded nonsecret
facts. Store pagination token and request ID only as SHA-256 digests, never raw.

No delete, overwrite, cleanup, resume or automatic retry belongs to B2-B.

## Credential and provider accounting

The existing `read_current_product_alpaca_secrets` credential reader may be
invoked at most once. Its secret scope closes on every exit. Use the existing
`StdlibAlpacaHistoricalBarsTransport` for fixed-host TLS GETs. There is no
environment fallback, Architecture-146 interactive-research credential
fallback, alternate HTTP client, redirect or decompression. Provider attempts are counted before transport invocation because a
transport exception can be ambiguous as to whether the GET reached the provider.

B2-owned ceilings are 192 pages per symbol and 576 provider request attempts
total. Stop before the next GET at either ceiling; do not use the B1 generic
10000-page ceiling or create an unbounded path. Insert a deterministic,
injectable/monkeypatchable minimum delay of 0.5 seconds between provider-request
starts after the first. Pace before authoring the next request intent, then
recheck exact source immediately before that intent and its GET. Focused tests
must not sleep.

No automatic retry or fallback is allowed for HTTP 401/403, 429, 5xx, transport
failure or ambiguity, malformed response, repeated token, page or total
ceiling, source drift, process ambiguity or qualification failure. Pacing does
not authorize wait-and-retry.

## Success artifacts

After all three symbols exhaust pagination and pass the unchanged B1 dataset
constructor, write create-once:

```text
raw/QQQ/<ordinal>.json
raw/TQQQ/<ordinal>.json
raw/SQQQ/<ordinal>.json
normalized/QQQ.csv
normalized/TQQQ.csv
normalized/SQQQ.csv
dataset.json
custody-evidence.json
evidence.json
```

`dataset.json` is the exact canonical B1 dataset serialization.
`custody-evidence.json` is the exact canonical B1 custody serialization.
Read back and verify all terminal artifact hashes and byte lengths before
claiming success.

## Terminal evidence

Use schema `arch148-b2-readonly-acquisition-evidence/v2`.

Bind exact source identity and both live refs; attempt identity; B1 contract,
dataset and custody identities; schedule identity/digest; request digest; price
basis; OPEN bounds; symbols; expected counts; credential and provider attempt
counts; ordered per-page body SHA-256/size/request-ID-digest vectors; pagination
exhaustion; canonical dataset, custody and normalized artifact hashes/sizes;
and sanitized failure classification when applicable.

For each symbol, successful terminal evidence explicitly reports raw provider
bar count, qualified regular-session bar count and excluded non-regular-slot
bar count, and proves:

`raw_bar_count = qualified_regular_session_bar_count + excluded_non_regular_bar_count`

B1 dataset and custody schemas and identities remain unchanged. Evidence also
states:

```text
automatic_retry = FORBIDDEN
robinhood_calls = 0
broker_calls = 0
order_mutations = 0
production_state_mutations = 0
final_holdout_accesses = 0
baseline_backtests = 0
```

Raw pagination tokens, raw request IDs, credentials, authentication headers,
environment values, tracebacks, arbitrary exception text and raw provider
bodies must not appear in terminal/failure evidence. Raw successful OPEN page
bodies remain separate create-once files under the attempt directory.

SUCCESS is exactly
`READY_FOR_INDEPENDENT_B2_EVIDENCE_REVIEW`. It grants no dataset acceptance,
strategy result, profitability claim or live authority.

## B2-A implementation surface

Prefer one additive coordinator module:

`src/trading_bot/experiments/arch148_b2_operator.py`

with one focused test module:

`tests/experiments/test_arch148_b2_operator.py`.

Add only the minimal existing-route ownership changes required to include the
new source/tests/Ruff surface under `arch147-live-prototype` FULL. Do not add a
new provider-capable checkpoint execute callback; checkpoint `execute=None`
remains unchanged.

The operator must expose an effect-free source/local preflight and an explicit
one-shot acquisition entry point with an exact interlock string. Import,
construction, help, source preflight and every source/fake test must prove zero
credential/provider calls.

## Required B2-A-C1 focused tests

Cover source/ref/cleanliness drift; output path aliases, reparse and
preexistence; attempt claim/write-once behavior; credential read 0/1
accounting; exact request order; 192-page-per-symbol and 576-total ceilings;
no retry on every transport/HTTP failure class; request intent before
transport; ambiguous intent-without-result; raw response persistence before
parse/projection; request-ID/token digest-only evidence; 156396-slot
qualification; wrong/missing/duplicate slot rejection; dataset/custody
canonical roundtrip; artifact read-back drift; post-provider source drift;
secret/exception leakage; and explicit zero Robinhood/broker/FINAL_HOLDOUT/
baseline effects.

Also prove that a mixed pre-market/regular/after-hours page preserves all raw
bytes while only exact B1 slots enter qualified bars; raw/qualified/excluded
counts reconcile exactly; missing expected regular slots reject final dataset
construction; duplicate/out-of-order raw timestamps fail before projection;
pagination tokens are exhausted sequentially; pacing occurs between request
starts but never before the first attempt and causes no real test sleep; and v2
success evidence binds all three counts per symbol without exposing raw
tokens, request IDs or secrets.

Use only fake transports, credentials and filesystem seams in B2-A-C1 tests.

## Publication and later real attempt

B2-A-C1 is a source-only/fake-only checkpoint. It does not perform real
credential access or contact Alpaca. The correction must complete focused checks, then exact-file staging and one
atomic commit. Run general `ops.ps1 admit` on that clean candidate and require
FEATURE plus PROSPECTIVE_DEVELOP PASS before one ordinary feature push. The
single push-triggered CI run owns the mapped canonical FULL. Do not duplicate
that FULL locally. Do not add a provider-capable
checkpoint callback; checkpoint `execute=None` remains unchanged. Preserve any
terminal CI evidence and do not rerun an unchanged source gate.

ChatGPT owns independent exact-source review and acceptance. Only after that
acceptance, integration and canonical worktree catch-up may ChatGPT review an
exact, separately named fresh successor invocation. The real operator must
print canonical `evidence.json` plus SHA-256 and byte length; ChatGPT reviews
that exact evidence before any baseline backtest. Baseline analysis uses the
accepted B1 simulator and performs no provider request. The consumed B2-B
attempt is never retried.
