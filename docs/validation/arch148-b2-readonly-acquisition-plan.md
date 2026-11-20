# Architecture 148-B2 — Read-only Intraday Acquisition Plan

Status: **B2-A-C1 SOURCE/CERTIFICATION ACCEPTED / FAST-FORWARD INTEGRATED;
EARLIER B2-B CONSUMED / BLOCKED / PAGE_LIMIT_REACHED / NO RETRY; LATER
ACQUISITION COMPLETE BUT ORIGINAL B1 QUALIFICATION CONSUMED / BLOCKED /
QUALIFICATION_BAR_COUNT_MISMATCH / NO RETRY; PUBLIC-REFERENCE COMPLETION SOURCE
AND OFFLINE SPARSE REQUALIFICATION EVIDENCE INDEPENDENTLY ACCEPTED.** This plan
authorizes no new Alpaca credential read, provider request, Robinhood/broker
action, production mutation or FINAL_HOLDOUT access. The follow-on
[Architecture 148 churn study](arch148-churn-research.md) is now
source/certification/evidence accepted and integrated; its OPEN result rejects
all four tested variants economically and selects none.

B2-A-C1 accepted executable source:
`0ebeaef7ea8ee83677d775fe66d037efa76c8cf1` /
`e16fe3aeec6a862c0d7ad7dd35e4171c1d3385e7`, direct parent
`298bba38cf61d506fec68cb7034fc66a58218078`. Feature source-gate
`44507842755`, attempt 1, is terminal SUCCESS with source-static, active-tests,
source-gates and all seven mapped FULL lanes passing. Develop source-gate
`44616906540`, attempt 1, is terminal SUCCESS with exact feature-certification
reuse, `IDENTITY_STABLE=True`, and no duplicate FULL.

The original B2-A accepted executable predecessor remains
`6957afa159647ece18af876289d8a20637cfc6eb` /
`43701fcaef23990a793359d08a8213d43e434780`; feature source-gate
`44485930260` and develop source-gate `44489803571` remain preserved historical
certification evidence.

B2-A-C1 changed executable source/tests, so the earlier docs-descendant shortcut
was not used to accept the correction itself. The correction is now
accepted/integrated. This post-acceptance docs-only closeout does not change its
executable/test/workflow bytes. A future provider acquisition still requires a
separately reviewed fresh invocation bound to the exact then-current integrated
invocation source after docs closeout/catch-up. The later `bb1a...` attempt
recorded below already consumed its own acquisition boundary; it is not a retry
of the earlier `fd8aa...` attempt. The offline requalification review is
accepted; another provider invocation is not authorized. The fixed churn study
in [`arch148-churn-research.md`](arch148-churn-research.md) is also
independently accepted/integrated with evidence SHA-256
`5baa7ef9e035f72428c623c798fb9653aa43339027c03e8e417d16c52e08aca8`.
Its OPEN comparison selected no variant and grants no provider or holdout
authority.

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

## Later completed acquisition with qualification mismatch

Attempt: `bb1a784b-98d1-41fd-8d95-aa9fa463d5c9`
Retained directory:
`F:\AI\temp\arch148-b2-bb1a784b-98d1-41fd-8d95-aa9fa463d5c9`
Outcome: acquisition complete; original downstream qualification CONSUMED /
BLOCKED / `QUALIFICATION_BAR_COUNT_MISMATCH` / NO RETRY.
Credential reads: 1. Pages: 430 of 430. Unresolved pagination intents: 0.
End cursor: null for QQQ, TQQQ and SQQQ. Automatic retry: FORBIDDEN.

| Symbol | Pages | Raw bars | Observed B1 slots | Missing expected slots |
|---|---:|---:|---:|---:|
| QQQ | 148 | 349805 | 156379 | 17 |
| TQQQ | 141 | 331112 | 156376 | 20 |
| SQQQ | 141 | 328679 | 156376 | 20 |

The missing-slot sets share 17 timestamps and have a 23-timestamp union. The
accepted dense B1 contract expects 156396 slots for each symbol; the preserved
acquisition therefore does not qualify as the original B1 dataset. Keep this
attempt separate from the older `fd8aa...` PAGE_LIMIT_REACHED incident above;
neither consumed attempt can be resumed or retried.

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

Both B2 attempts recorded above are consumed and cannot be resumed or retried.
B2-A-C1 was the source-only/fake-only corrective checkpoint and is now
accepted/integrated. A new provider acquisition is not authorized by this plan;
any later attempt requires its own separately reviewed invocation after this
docs update is integrated and the canonical worktrees are reconciled locally.
The latest preserved acquisition is complete but failed the original dense B1
qualification, so the immediate review boundary is offline requalification,
not another provider request.

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
strategy result, profitability claim or live authority. This status means the
acquisition evidence is complete; it does not override a downstream B1
qualification failure. The later `bb1a...` attempt is consumed and blocked by
`QUALIFICATION_BAR_COUNT_MISMATCH` as recorded above.

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

## B2-A-C1 publication, integration and later real attempt

B2-A-C1 completed focused verification, exact-file staging, one atomic feature
commit and general `ops.ps1 admit` before one ordinary feature push. Feature
run `44507842755`, attempt 1, supplied the mapped canonical FULL and is terminal
SUCCESS. Independent ChatGPT exact-source review accepted HEAD
`0ebeaef7ea8ee83677d775fe66d037efa76c8cf1` / tree
`e16fe3aeec6a862c0d7ad7dd35e4171c1d3385e7`.

The accepted commit was fast-forwarded locally onto develop and the ordinary
develop push succeeded. Develop run `44616906540`, attempt 1, is terminal
SUCCESS with `DEVELOP_CERTIFICATION_REUSE=True`, reason
`exact_feature_certification`, `IDENTITY_STABLE=True`, and no duplicate FULL.

The first integration wrapper then raised a PowerShell `NativeCommandError`
after that successful push because it combined
`$ErrorActionPreference='Stop'` with redirected native Git stderr. GitHub
proved both remote refs had already reached the accepted SHA, and a separate
read-only local proof established the integration checkout was clean at the
accepted HEAD/tree. No second push or merge was performed. This is
`ARCH148_B2_A_C1_TRANSITION_NATIVE_STDERR_REGRESSION`; the existing workflow
rule against stderr-unsafe native-command handling remains authoritative.

The later acquisition's raw provider facts are preserved, but its original
dense B1 qualification failed. The offline requalification source at
`src/trading_bot/experiments/arch148_b2_requalify.py` and sparse replay source
at `src/trading_bot/experiments/arch148_sparse_backtest.py` are accepted in
`6fb78af8c2e07d906629fd95277343eb6d54fde3` / tree
`01091cea96aa3aba6e5de8b88b64d8f722f116ba`. The exact offline result is
independently accepted at
`F:\AI\temp\arch148-b2-offline-requalification-b9a8babd-4869-466d-a81f-fae08fe2aae5\evidence.json`,
65,688 bytes, SHA-256
`bdad3ab1f387617e2cef35644680e397c94d113f77f48cc242857151b352788d`.
It binds dataset `0308b694-c718-5b1a-a51c-9fcc4516bb81` and custody
`dbcced6a-b4cc-5d36-a33b-5e6df3d82baa`, reports zero fully missing sessions,
and records zero new credential/network/provider/Robinhood/broker/order/
production/FINAL_HOLDOUT/baseline effects. Keep the dense B1 contract unchanged.
No provider retry or broker effect is authorized by this plan. The accepted
sparse observations and baseline are the fixed inputs to the accepted churn
comparison in [`arch148-churn-research.md`](arch148-churn-research.md).
Its independently reviewed OPEN evidence rejects all four tested variants and
must not overwrite or reinterpret this plan's immutable acquisition or
requalification evidence.
