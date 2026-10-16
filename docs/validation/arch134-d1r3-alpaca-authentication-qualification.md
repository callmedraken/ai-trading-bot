# Architecture 134-D1R3 â€” Alpaca authentication qualification

## Historical snapshot — current operator superseded by D1R4

The material below records D1R3 source acceptance, its original `/v2` operator
contract and the consumed real HTTP 401 result. Original future-tense commands
and unexecuted statements are retained historical snapshots, not current
authority. Do not rerun D1R3. Current preparation is governed by
[D1R4 validation](arch134-d1r4-alpaca-v3-credential-generation.md) and the reviewed
v3 concurrency amendment; real provisioning/authentication remain protected.

## 2026-10-13 — D1R3 real authentication qualification BLOCKED / HTTP 401

The separately authorized Architecture 134-D1R3 real authentication
qualification was executed once against the accepted docs-descendant operational
source HEAD `5dd510a73e9eb15ade4a4fa7ed90152d2ac85b3b`, TREE
`df8f208224ae8646e79d4d5ce92a70bb18e900d3`, after a zero-effect preflight
proved the exact source/import/probe/evidence boundary.

The preflight performed zero credential reads and zero Alpaca HTTPS requests.
The real qualification then crossed exactly one D1R3 authority boundary and
published canonical external evidence at:

```text
F:\AI\temp\qualification\arch134-d1r3-auth-bb7ebdbb0669479d82b13f2ff9171781.json
```

Canonical outcome:

```text
schema                           alpaca-authentication-qualification/v1
status                           BLOCKED
reason                           HTTP_REJECTED
http_status                      401
provider_code                    null
credential_pair_read_attempts    1
credential_pair_read_succeeded   true
alpaca_request_attempts          1
source_readmitted                true
probe_session                    2026-10-07
probe_method                     GET
probe_host                       data.alpaca.markets
```

Because pair readiness succeeded, the accepted reader consumed the two fixed
Windows Credential Manager records exactly once each. Exactly one Alpaca HTTPS
request was attempted. The qualification made no production SQLite access,
session reservation/recovery, strategy evaluation, Robinhood call,
PREPARE/EXECUTE, paper mutation, broker placement, scheduler/ACL mutation, D1
launch or D2 invocation. The accepted source was re-admitted after the external
read. The result is definitive and non-ambiguous: the current fixed credential
pair is locally readable but rejected by Alpaca.

The D1R3 invocation is consumed. **Do not rerun D1R3 unchanged.**

The current reader is hard-coded to the accepted Architecture-84 `/v2` targets:

```text
AITradingBot/MarketData/Alpaca/ApiKeyId/v2
AITradingBot/MarketData/Alpaca/ApiSecretKey/v2
```

Architecture 84A already freezes the post-first-provider-effect immutability
rule: once a real provider effect has used `/v2`, those two targets are
historical credential-reference state and must not be overwritten, deleted for
replacement, or silently rebound to another Alpaca pair. D1R2 had already used
the `/v2` pair; D1R3 now independently confirms remote rejection. Therefore
manual replacement of either existing `/v2` entry is **not authorized**.

The next production milestone is **Architecture 134-D1R4 — versioned Alpaca
credential rotation to `/v3` plus fresh authentication requalification
authority**. It must freeze a new credential policy and exact new target names,
preserve `/v2` as immutable historical evidence, reuse the existing
secret-free local witness discipline, prohibit fallback, update the D1R3
qualification path to the new fixed pair, and keep actual generation/provisioning
and the later real authentication probe as separately reviewed protected
operator boundaries.

Until D1R4 source/deployment/provisioning is accepted and a fresh `/v3`
authentication qualification passes, no fresh D1 session is authorized.
The still-required pre-market start/WAITING_FOR_MARKET/wake qualification remains
after remote Alpaca authentication is proven. D2 remains disconnected and
real-money trading remains **NO-GO**.

Status: **SOURCE ACCEPTED** at HEAD `2a106c10178efa38eb7a24c7d97866201e0d2b76` / TREE `03be6ef612542f204b4d5d80924473b5274aa25d`; Checkpoint Source Gates #520 / 38462482959 attempt 2 SUCCESS. Real qualification remains separately protected and unexecuted.

## Acceptance evidence

Exact accepted source is the two-commit descendant of the D1R2 operational closeout:
implementation `0cfd621ab3d91c349df4394e5d757d98d25f5ba1` /
`f24fd9321a71ce982f05c4b7bd883c47f6fbd47a`, then correction
`2a106c10178efa38eb7a24c7d97866201e0d2b76` /
`03be6ef612542f204b4d5d80924473b5274aa25d`. The correction changes no D1R3
production module and no D1/D1R2 executable source.

The corrected controlled stale-CAS tests prove either caller can be the sole real
exact-byte CAS winner while the other stale CAS rejects before history publication;
exactly one reacquisition/evaluation occurs and downstream trading effects remain
zero. A separate real disposable SQLite `BEGIN EXCLUSIVE` test deterministically
proves `SQLITE_BUSY` blocks without consuming predecessor bytes or calling the
provider. The narrow correction pin covers only the directly changed retained
armed-session test blob `4e06e2d922f6ca784681cffe8ccda6b4806bc14f`; initial D1R3 and all frozen
accepted predecessor dictionaries remain unchanged.

CI #520 attempt 1 executed the exact final source with 8,899 passed, one optional
SDK skip and zero failures/errors, but failed the hygiene gate because canonical
wall time was 331.725 seconds. The single certification retry used the unchanged
HEAD/tree and is accepted as an infrastructure/performance retry, not a semantic
retry. Attempt 2 is terminal SUCCESS: 8,899 passed / one skipped / zero
failures/errors, wall 255.502 seconds. Artifact 11848066370 records 95 ROBINHOOD
modules, exact source identity before/after tests and successful repository-wide
git-diff/Ruff check/Ruff format checks. source-static, active-tests and terminal
source-gates are SUCCESS; full-tests are intentionally skipped.

All implementation/correction/CI operational effect counts remain zero. Source
acceptance grants no real credential/provider operation. The next boundary is one
fresh explicitly authorized real D1R3 authentication qualification.
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

Stop only after terminal successful mapped source CI on the exact final HEAD/tree.
Bounded test/registration corrections may iterate through ordinary commits and
pushes without widening production authority. ChatGPT owns exact source acceptance and
fresh authorization for any real D1R3 credential/provider qualification. PASS
only means REMOTE_ALPACA_AUTH_READY for this source/request/read observation; no
ongoing validity, reservation, D1 launch or D2 authority is implied. A later reviewed
operator step must bind and consume this evidence before a fresh future D1 session.


## D1R3 failed-CI correction

Implementation `0cfd621ab3d91c349df4394e5d757d98d25f5ba1` /
`f24fd9321a71ce982f05c4b7bd883c47f6fbd47a` produced mapped CI #519 /
38458088952 FAILURE: active 658 passed/one retained concurrency failure;
ROBINHOOD 8,887 passed/ten stale topology failures/one skipped, zero errors.
All 84 D1R3 tests and source-static passed. This correction leaves qualification
and every production executable/native/CAS/recovery/credential boundary unchanged.

The grouped disposable concurrency diagnostic captured two SQLITE_BUSY (code 5)
exceptions at RECOVERY_STARTED. The existing zero-timeout store may block both
contenders before either CAS consumes authority; the test incorrectly required
one NO_SIGNAL result for uncontrolled SQLite lock timing. No fixture/global-state
or provider-counter leak was required to reproduce it. Function-scoped fixtures,
fresh SQLite roots, fixed fake identities and joined worker lifetimes remain.

The corrected test first barriers two equal stale predecessor reads, then uses
bounded test-only events to choose either caller's real exact-byte CAS first.
The second real UPDATE must reject those stale bytes, and the winner waits for
that rejection before publishing history. Both possible winners are covered;
exactly one consumes/reacquires, four history requests and one evaluation occur,
and PREPARE/EXECUTE/paper/broker effects remain zero. A separate deterministic
BEGIN EXCLUSIVE lock on a disposable database proves actual SQLITE_BUSY still
blocks without changing predecessor bytes or making a provider request. No
production wait, mutex, retry, timeout or CAS behavior is added.

Ten retained topology tests now assert 63 checkpoints, the exact new checkpoint
at position -7, and their correctly shifted exact historical predecessor pairs.
No exact tuple assertion becomes a membership/subset approximation. Inventory
is recomputed through the canonical discovery/selection functions; module
ownership is unchanged. One separately named narrow correction test-pin overlay
owns only tests/review_paper/test_armed_production_paper_session.py; every frozen
accepted D1/R1/R2 and initial D1R3 source dictionary is retained unchanged.

Focused verification covers all directly changed test modules, all previously
failing nodes, D1R3 registration, repeated isolated CAS cases and representative
runtime/qualification grouping with fresh external basetemp roots. Both Ruff
phases and unstaged/staged diff checks are required before ordinary publication.
Mapped CI must finish source-static/active-tests/certification-tests/source-gates
SUCCESS, full-tests SKIPPED, zero failures/errors and ROBINHOOD wall below 300s.
Final correction identity, exact pins, focused counts and CI evidence belong in
the implementation handoff. No local broad certification or real qualification
is performed by this correction.
