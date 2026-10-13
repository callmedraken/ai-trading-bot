# Architecture 134-D1R3 — Alpaca authentication qualification

Status: implemented source checkpoint; ChatGPT acceptance and fresh protected
qualification authorization remain required. Base HEAD
`d595450daa029f37e2f69bbb6b20263dc7e0e987`, TREE
`4822a6723b10fd223a138df580aa7a3daf2ee5bc`; base source CI #518 / 38454451965
SUCCESS. Branch `feature/robinhood-production-paper-alpaca-auth-qualification`;
worktree `F:\AI\worktrees\ai-trading-bot-production-paper-alpaca-auth-qualification`.
The one implementation commit's exact HEAD/TREE and terminal source CI are supplied
in the implementation handoff; no self-referential Git identity is fabricated.

## Purpose and frozen incident

D1Q established storage/readability, whereas the separately authorized D1R2
recovery first read received 401 after its recovery CAS was consumed. These are
different readiness claims. D1R3 qualifies remote authentication independently
of session authority. October 13 remains permanently consumed: operation
`8e8c5102-8b52-5534-8288-b3261f65b2d4`, successor contract
`93091b0e-a1a6-52fd-930f-f88eb2009c05`, BLOCKED, recovery_count=1, alpaca_reads=1,
HTTP_FAILED/401, history_session=2026-10-07, zero strategy/PREPARE/EXECUTE/
Robinhood/paper/broker effects. No reopening, migration, reclaim or retry exists.
HTTP 401 remains non-recovery-eligible. All accepted D1/R1/R2 executable pins and
frozen predecessor dictionaries remain intact.

## Protected authority and one-attempt composition

Production qualification is a separate, explicitly authorized operation:

- Exactly two fixed Windows credential record reads on successful pair readiness,
  via `read_current_product_alpaca_secrets()`, for
  `AITradingBot/MarketData/Alpaca/ApiKeyId/v2` and
  `AITradingBot/MarketData/Alpaca/ApiSecretKey/v2`. A failed underlying read may stop
  before the second record; the reused reader never retries. Evidence records
  pair attempts/success, never invents an exact per-record failed-read count.
- At most one HTTPS request through `StdlibAlpacaHistoricalBarsTransport` and
  `build_alpaca_historical_bars_request`. The invocation-local consumed-attempt
  guard precedes the call; no retry, pagination or fallback exists.
- Zero production SQLite reads/writes, reservations/recoveries, strategy evaluations,
  Robinhood calls, PREPARE, EXECUTE, paper mutations, broker placements, scheduler
  calls or ACL mutations. Fresh external evidence publication and read-only Git
  source admission are the only surrounding host effects.

No environment/config/command-line secrets or alternate HTTP client are added.
The pair scope closes and mutable credential copies are cleared by the accepted
reader. Existing immutable Python strings cannot be guaranteed zeroized; no
credential value is logged, hashed or persisted. The qualification retains no
provider body, headers, request ID, free text, bars or response hash. Errors are
caught without formatting upstream exception repr/str/context. CLI argument and
host failures emit only `ALPACA_AUTH_QUALIFICATION_HOST_BLOCKED`, exit 2, and no
success artifact. Import/help does not qualify credentials or make a request.

The strict parser validates the response first. The qualification then checks
exact symbol-map membership (including unexpected empty symbol arrays), one
candidate, completed session and exact New York midnight, and reuses domain Bar
OHLCV validation. No snapshot, strategy seed, session or trading result is created.

## Immutable probe

The UUID5 request selector uses versioned fixed semantic material independent of
clock/source/filesystem. Selector October 8 midnight New York derives completed
XNYS session October 7 via the accepted calendar. The provider request is exactly:

```text
GET https://data.alpaca.markets/v2/stocks/bars
symbols=SPY
timeframe=1Day
start=2026-10-07T04:00:00Z
end=2026-10-08T03:59:59.999999Z
limit=1
adjustment=raw
asof=-
feed=sip
currency=USD
sort=asc
```

These are the exact D1 October-7 network semantics. Expected bar timestamp is
2026-10-07T04:00:00Z, with no additional/missing symbol or bar and no page token.
Provider authentication/metadata/body rejection fails closed. The accepted
transport keeps its 15-second timeout and 4-MiB entity bound; no shared transport,
parser, strategy or recovery implementation is changed.

## Closed canonical evidence

Schema `alpaca-authentication-qualification/v1`; exactly fifteen fields:

```text
schema
source_head
source_tree
probe_session
probe_method
probe_host
probe_target
status
reason
credential_pair_read_attempts
credential_pair_read_succeeded
alpaca_request_attempts
http_status
provider_code
source_readmitted
```

Statuses are PASS/BLOCKED. Reasons are PASS, CREDENTIAL_READ_FAILED,
TRANSPORT_FAILED, HTTP_REJECTED, RESPONSE_INVALID, SOURCE_DRIFT. PASS is possible
only with successful fixed pair readiness, one request, HTTP 200, validated
metadata, bounded body, existing strict Alpaca parsing, exact SPY probe and final
source readmission. All other reasons are BLOCKED; HTTP 401/403/429/5xx never PASS
and never retry. RESPONSE_INVALID means a 200 entity failed exact probe acceptance.
TRANSPORT_FAILED includes request/response-start/metadata/body acquisition or
validation failures. HTTP_REJECTED retains only exact integer status 100..599
excluding 200 and optional already-sanitized integer code 0..2^63-1. Neither
request ID nor provider text is retained. SOURCE_DRIFT supersedes any outcome.

Strict types exclude bool-as-int; pair/request attempts are 0 or 1, and a request
requires successful pair readiness. Both source hashes must be canonical lowercase
40-hex values. Probe fields must equal the fixed request. The parser rejects
unknown/missing/duplicate fields, unsupported reasons, incoherent PASS/failure
facts, nonstandard constants, BOM, invalid UTF-8, noncanonical representation,
trailing bytes and payloads above 4096 bytes. Serialization is compact sorted
UTF-8 JSON with exactly one trailing newline. Parsing failures are raised outside
handlers with fixed text and no underlying raw exception context.

The host requires an absolute fresh `.json` path under an existing real external
parent. All Git worktrees and the production `F:\AITradingBot` tree are excluded;
symlinks/reparse parents and existing files are rejected. `xb` reserves the evidence
before credentials; flush/fsync completes before canonical stdout. Race/open/write/
fsync failure returns nonzero, never retries, never overwrites, and may leave a
consumed empty/partial/nonqualified destination. Preserve it; its existence is
not PASS. Evidence publication failure cannot trigger a second provider call.

## Source and host

`python -B -m trading_bot.review_paper.alpaca_authentication_host` is the narrow
noninteractive module entry point. Required arguments are `--expected-head`,
`--expected-tree`, `--evidence`, and `--qualify-auth` with the exact interlock
`AUTHORIZE_ARCH134_D1R3_ONE_ALPACA_AUTH_QUALIFICATION`. No effectful operator command
is authorized by source review or CI.

Admission enforces fixed Windows worktree and branch, exact local HEAD/tree,
clean tracked/index/untracked state, intended origin, exact remote-tracking
HEAD/tree, live origin branch HEAD and unmixed executing package paths. It runs
before evidence admission, before credentials, immediately before transport and
after external read, including failed reads. Drift before transport yields zero
provider attempts; drift afterward invalidates PASS. Failed initial host admission
has no credential/provider/evidence effects. Successful CLI evidence exits 0 only
for PASS; BLOCKED artifact exits 1, sanitized host failures exit 2.

## Source verification and stop condition

Fake-only tests cover compatible 200, 401/403/429/5xx/other statuses, request,
response-start, metadata and body failures; malformed/oversized/strict JSON;
missing/wrong/additional symbol/session/bar data; no pagination; credential failure;
source drift before/after request; reentrant second-call denial; canonical parser;
secret-free output/evidence/repr/errors; fresh/external/reparse evidence; module
entry; source-only registration and frozen predecessors.

Runner registration is `arch134-alpaca-authentication-qualification`, source only,
with no preflight/execute hook. ACTIVE grows from 62 to 63 before the retained
Architecture-134 six-checkpoint suffix; its AST digest and workflow list are updated
atomically. Only changed CI/profile/registry tests receive narrow D1R3 pin overlays; frozen
D1/R1/R2 dictionaries remain byte-for-byte semantically unchanged. The automatically
owned new test enters FULL/ROBINHOOD; frozen baselines remain untouched. Resulting
source inventory is FULL=171, ROBINHOOD=95, LEGACY=215, EXHAUSTIVE=386.

Focused checks use `-B`, `-p no:cacheprovider`, and a fresh external
`F:\AI\temp\pytest\arch134d1r3-*` root. Both non-mutating Ruff phases and
`git diff --check` are required. Existing integration workflow already admits
`feature/robinhood-*`; mapped CI runs source static, active tests and canonical
ROBINHOOD certification, with full fallback skipped. No duplicate local broad
certification or real qualification is run during implementation.

Stop after terminal source CI. ChatGPT owns exact GitHub source acceptance and
fresh authorization for any real D1R3 credential/provider qualification. PASS
only means REMOTE_ALPACA_AUTH_READY for this source/request/read observation; no
ongoing validity, reservation, D1 launch or D2 authority is implied. A later reviewed
operator step must bind and consume this evidence before a fresh future D1 session.
