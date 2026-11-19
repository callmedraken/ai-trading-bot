# Architecture 148-B2 — Read-only Intraday Acquisition Plan

Status: **DESIGN FROZEN / SOURCE NOT YET IMPLEMENTED.** This plan authorizes no
Alpaca credential read, provider request, Robinhood/broker action, production
mutation or FINAL_HOLDOUT access.

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

148-B2-B is one later separately reviewed real read-only acquisition attempt on
the exact accepted/integrated B2-A source. B2-B is not automatically authorized
by B2-A success. There is no provider retry or fallback.

## Provider and dataset contract

Use only the accepted B1 request builder and parser for QQQ, TQQQ and SQQQ, in
that order. Each symbol uses the exact OPEN request contract: `5Min`,
`adjustment=all`, `asof=-`, SIP, USD, ascending order, limit 10,000 and
pagination to `next_page_token=None`.

The provider end is inclusive, so B1's exact
`2023-12-31T23:59:59.999999Z` end remains required for the half-open OPEN
dataset ending 2024-01-01.

The accepted session/schedule contracts imply:

```text
OPEN sessions                    2012
early-close sessions               15
expected 5-minute slots/symbol  156396
expected total bars             469188
minimum pages/symbol at 10000       16
B2 page ceiling/symbol               64
B2 provider-attempt ceiling         192
```

Fewer/more bars, missing/unexpected slots, unequal symbol timestamps, duplicate
timestamps, off-grid data, noncanonical OHLCV, pagination loops, unexpected
symbols or any other B1 validation failure block qualification.

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

A mismatch blocks before any further provider request. Source drift discovered
after a provider attempt preserves the partial attempt and returns a blocked
result; it never retries or repairs source.

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

The current-product credential reader may be invoked at most once. The credential
scope is closed on every exit. The provider attempt counter increments before
each transport invocation.

No automatic retry is allowed for transport failure, HTTP failure, 401/403,
429, 5xx, malformed response, repeated token, pagination bound or process/source
ambiguity. Alpaca's generic recommendation to retry some server failures does
not override this project's one-shot evidence discipline.

The stricter B2 ceiling is 64 provider pages per symbol and 192 total attempts.
Exceeding either ceiling blocks before the next request.

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

Use schema `arch148-b2-readonly-acquisition-evidence/v1`.

It must bind exact source identity, both live refs, attempt identity, B1
contract identities, schedule identity/digest, request digest, price basis,
expected counts, credential/provider attempt counts, ordered per-page body
digests/sizes/request-ID digests, pagination exhaustion, dataset/custody
identities and canonical artifact digests/sizes.

It must also state:

```text
automatic_retry = FORBIDDEN
robinhood_calls = 0
broker_calls = 0
order_mutations = 0
production_state_mutations = 0
final_holdout_accesses = 0
baseline_backtests = 0
```

Raw credentials, authentication headers, raw request IDs, environment values,
tracebacks, arbitrary exception text and raw provider bodies must not appear in
`evidence.json`. Raw successful OPEN page bodies are separate bounded
artifacts under the attempt directory.

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

## Required B2-A focused tests

Cover source/ref/cleanliness drift; output path aliases/reparse/preexistence;
attempt claim/write-once behavior; credential read 0/1 accounting; exact request
order; 64-page and 192-request ceilings; no retry on every transport/HTTP
failure class; request intent before transport; ambiguous intent-without-result;
raw response persistence before parse progression; request-ID/token digest-only
evidence; 156,396-slot qualification; wrong/missing/duplicate slot rejection;
dataset/custody canonical roundtrip; artifact read-back drift; post-provider
source drift; secret/exception leakage; and explicit zero Robinhood/broker/
FINAL_HOLDOUT/baseline effects.

Use only fake transports/credentials/filesystem seams in B2-A tests.

## Publication and later real attempt

Codex Sol High coordinates B2-A only; Luna Extra High implements and runs focused
checks. Codex must not implement, stage, commit, push, merge or execute B2-B.

B2-A publication uses one coherent atomic feature commit, general admission,
one ordinary feature push and one mapped FULL run. After ChatGPT exact-source
acceptance, use the canonical local fast-forward integration procedure and
closeout/catch-up before any B2-B provider action.

Only then may ChatGPT review an exact B2-B invocation. The real operator must
print canonical `evidence.json` plus its SHA-256 and byte length. ChatGPT must
review that evidence before any baseline backtest. Baseline analysis uses the
accepted B1 simulator and performs no provider request.
