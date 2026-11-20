# Architecture 148 — TQQQ/SQQQ application-runtime pivot

Status: **DESIGN ACCEPTED / DOCUMENTATION ONLY.**

This architecture is the current product direction. It supersedes extending the
Architecture-147 L43 checkpoint chain as the application architecture. Existing
accepted Architecture-147 broker, state, reconciliation, source-authority,
research, risk, session, GUI and testing components remain reusable safety
infrastructure and historical evidence. No real provider call, state
provisioning, review, placement, cancellation, Q1 retry, Q63 action or
`FINAL_HOLDOUT` access is authorized by this document.

## Product objective

Build the first understandable end-to-end unattended trading application around
a deliberately narrow universe:

- **TQQQ** when the source-owned market-regime engine is bullish;
- **SQQQ** when the source-owned market-regime engine is bearish;
- **FLAT** when direction is neutral, stale, conflicted or unproven.

The first version is intraday-only and long-only. It may own TQQQ, SQQQ or
nothing, never both at once. It never shorts either ETF and never carries an
Architecture-148 position intentionally across the regular-session close.

TQQQ targets 3x the daily performance of the Nasdaq-100 and SQQQ targets -3x
the daily performance of the Nasdaq-100. Their issuer explicitly warns that
returns over periods longer than one day may differ significantly from the
daily target. Intraday-only v1 is therefore a deliberate risk and validation
constraint rather than a claim that overnight holding is always inappropriate.

Reference:
- https://www.proshares.com/our-etfs/leveraged-and-inverse/tqqq
- https://www.proshares.com/our-etfs/leveraged-and-inverse/sqqq

## Reference application and reuse policy

Primary application-shape reference:

- `siropkin/robinhood-ai-trading-bot`
- reviewed main: `1a778749cfbe92c7ab9444b12e3cc73587533ade`
- MIT licensed

The useful pattern is the simple application loop:

`authenticate -> broker snapshot -> candidate/market data -> indicators ->
decision -> deterministic validation -> execute -> record -> repeat`.

Do not import its brokerage implementation wholesale. In particular, do not
adopt direct username/password/TOTP Robinhood login, `robin_stocks`, generic
retry around broker writes, prompt-only risk limits or its lack of durable
ambiguous-order reconciliation.

Any source copied rather than independently reimplemented from the MIT project
must retain the applicable copyright/license notice.

Other existing public-reference evidence remains relevant, including
`EUGMsub/RobinhoodAgenticTrader`, `kevin1chun/robinhood-for-agents` and
`abiemann/RobinhoodEquityTradingAgent`. Architecture 148 requires an explicit
parity matrix before source publication rather than a prose-only survey. The
canonical full-pin source/runtime/public-reference adoption matrix is
[`docs/validation/arch148-runtime-parity.md`](../validation/arch148-runtime-parity.md).
It records the reviewed Lumiwealth, QuantConnect/Lean, Hummingbot, Freqtrade,
Robinhood, and siropkin references; local source/tests; license handling; and
behavior explicitly declined. No third-party implementation code is copied
into the accepted Architecture 148 public-reference completion source.

## Final application shape

The production application owns one obvious cycle:

1. lifecycle/GUI Start authorizes the application to run, not to bypass risk;
2. prove current session and single-run ownership;
3. obtain a fresh broker snapshot;
4. obtain current market/research inputs;
5. compute one market-regime decision;
6. derive at most one desired target position: TQQQ, SQQQ or FLAT;
7. run deterministic account, buying-power, tradability, order-scope, risk,
   stop-protection and source/state gates;
8. review the exact broker order where the current Robinhood contract requires
   or provides that safety preview;
9. persist an exact durable intent and deterministic provider `ref_id`;
10. place at most the explicitly admitted effect;
11. reconcile broker facts before any next effect;
12. publish state/results to the GUI and research history;
13. repeat on the configured cadence while Start remains enabled.

Checkpoint machinery certifies this application; it must not become the
user-facing runtime architecture.

## V1 signal instrument and regime engine

The traded universe is fixed to `TQQQ` and `SQQQ`. The primary directional
reference is `QQQ`; the leveraged ETFs themselves are execution instruments,
not the sole market-direction oracle.

Use only completed bars. V1 starts with a deterministic, backtestable technical
regime classifier on completed 5-minute QQQ bars:

- BULLISH candidate:
  - last completed close > session VWAP;
  - EMA(20) > EMA(50);
  - RSI(14) >= 55.
- BEARISH candidate:
  - last completed close < session VWAP;
  - EMA(20) < EMA(50);
  - RSI(14) <= 45.
- otherwise NEUTRAL.

A BULLISH or BEARISH candidate becomes entry-eligible only after two consecutive
completed 5-minute bars classify in the same direction. No entry uses an
in-progress bar.

The thresholds are a v1 baseline for research/backtesting, not a claim of
optimal profitability. Architecture-134/142/146 research infrastructure remains
available to compare and later promote improved classifiers through the existing
research/promotion discipline.

AI/research may produce explanation, confidence, alternate signals and
experiments in v1, but it may not directly choose quantity, bypass a deterministic
gate or turn NEUTRAL into a live order. A later accepted milestone may make an
AI classifier trade-authoritative only under an explicit tested contract.

## Entry rules

Initial session policy:

- no entry before 15 minutes after the official regular-session open;
- no new entry during the final 30 minutes before the official regular-session
  close;
- official XNYS session authority owns open/close timing, including shortened
  sessions;
- BULLISH target -> long TQQQ;
- BEARISH target -> long SQQQ;
- NEUTRAL target -> no new position;
- never hold both TQQQ and SQQQ;
- never flip directly in one effect: exit, reconcile exact FLAT, then a later
  cycle may enter the opposite ETF;
- fresh account state, buying power, symbol tradability/fractional capability,
  approval state, open orders and current positions must be re-derived at the
  live effect boundary;
- exact order arguments must receive broker review when supported by the
  accepted Robinhood contract;
- quantity/notional is deterministic source-owned risk output, never model text.

The currently accepted Architecture-147 <=$10 tiny-live acquisition authority
is not silently enlarged by this pivot. Any larger live notional or whole-share
requirement needs a separately reviewed risk change.

## Exit rules

V1 exits are deterministic and have strict priority:

1. hard stop;
2. source/state/broker safety failure requiring flattening;
3. confirmed regime exit/reversal;
4. scheduled forced-flat before the regular-session close.

A regime exit occurs after two consecutive completed 5-minute QQQ bars no
longer support the held direction. An opposite confirmed regime is still an
exit first; it is not same-cycle authority to enter the inverse ETF.

The forced-flat boundary begins five minutes before the official regular-session
close. No new Architecture-148 entry follows that boundary during the session.

No fixed take-profit target is required in v1. Research may evaluate take-profit,
trailing-stop and alternate exit policies without giving them live authority.

## Hard stop-loss invariant

The v1 hard stop is **3.00% below the reconciled average entry fill price of the
held ETF**.

For an entry average fill `P`, the immutable initial stop price is
`P * 0.97`, rounded only according to the exact accepted broker price contract.

Rules:

- the stop is based on actual reconciled fill facts, not signal/quote price;
- it can never be widened downward after entry;
- a software risk check treats price at/below the threshold as mandatory EXIT;
- the preferred live protection is a broker-resident sell stop-market order
  covering the entire exact owned quantity as soon as the position is
  reconciled enough to place it safely;
- if exact full-position broker stop protection cannot be proven, live entry is
  not considered fully ready for promotion;
- restart/recovery with an owned TQQQ/SQQQ position and missing, malformed,
  conflicting or under-sized protection blocks new entries and prioritizes
  protective reconciliation/exit;
- stop cancellation/replacement is an effect and must obey the same durable
  intent, `ref_id`, no-ambiguous-retry and reconciliation rules as other
  writes.

Robinhood currently supports stop-market equity orders for agents. A stop price
does not guarantee execution price: when triggered it becomes a market order
and may fill below the stop, particularly in volatile conditions. The hard stop
is therefore an exit trigger/protection invariant, not a guaranteed maximum
loss.

Whole-share entry sizing uses a fresh price with cash, unleveraged buying power
and existing risk controls, while retaining the <=$10 acquisition ceiling. A
quantity-denominated market order has no capped fill price and does not
guarantee a <=$10 fill. Live use remains blocked pending reviewed exact
whole-share risk authority and provider capability.

Reference:
- https://robinhood.com/us/en/support/articles/trading-with-your-agent/
- https://robinhood.com/us/en/support/articles/stop-order/

## Broker parity requirements carried into Architecture 148

The new runtime must not repeat the L43 parity omissions. Before any real
Architecture-148 observation/effect, source must demonstrate:

- fresh account active/agentic eligibility;
- fresh portfolio/cash/buying-power facts;
- fresh TQQQ/SQQQ/QQQ tradability and applicable fractional capability;
- fresh trade-approval state and typed handling of a provider-created approval
  request;
- exact pre-trade broker review with current warnings;
- deterministic per-logical-order `ref_id`;
- `ref_id` retained in normalized broker order facts;
- exhaustive current order/position reads with bounded pagination;
- durable intent persisted before an ambiguous write;
- no automatic retry after a write that may have landed;
- factual reconciliation of an unbound ambiguous write by stable `ref_id` plus
  exact order facts;
- single-writer application/state ownership;
- stop-order lifecycle represented durably, including partial fill, cancel,
  reject, unknown and restart;
- current provider schema parity tests against the accepted live tool surface.

## Existing work retained

Reuse rather than rewrite accepted components where their contracts fit:

- Robinhood MCP OAuth/session and structured-content transport;
- account resolution and agentic-account constraints;
- RHC2/RHC3 account-wide order-scope evidence;
- durable MAY_HAVE_OCCURRED/UNKNOWN semantics;
- RHC3P factual settlement/reconciliation;
- source identity and exact-state continuity;
- XNYS calendar/session authority;
- Alpaca/research acquisition where useful;
- deterministic risk engine;
- research/backtest/campaign infrastructure;
- GUI Start/Stop, status and kill controls;
- checkpoint/source authority and mapped certification topology.

Architecture-147 Q1 remains CONSUMED / BLOCKED / NO AUTOMATIC RETRY. Its
standalone L43 state-provisioning successor is superseded as the immediate
milestone. If Architecture 148 reuses that state implementation it must provision
or migrate it as part of the new complete application dependency closure, not
as permission to rerun Q1.

Q63 remains NOT RUN and `FINAL_HOLDOUT` remains SEALED.

## First source milestone: 148-A runtime skeleton and parity closure

148-A is source-only/fake-only. It must not invoke real Robinhood, OAuth,
browser, Alpaca, broker review/place/cancel, production state preparation or
`FINAL_HOLDOUT`.

Deliver one coherent runtime skeleton with:

- explicit `MarketRegime = BULLISH | BEARISH | NEUTRAL`;
- fixed v1 symbols QQQ/TQQQ/SQQQ;
- completed-bar indicator calculation and two-bar confirmation;
- desired-position planner;
- 3% hard-stop policy object;
- intraday session admission/forced-flat policy;
- deterministic transition planner that forbids simultaneous TQQQ/SQQQ and
  same-cycle flips;
- broker snapshot/provider protocols containing all parity facts above;
- durable intent/ref-id model including protective-stop intent;
- application-cycle service that is completely fakeable and effect-free unless
  handed an explicit admitted effect executor;
- GUI-facing cycle/status projection;
- a written parity matrix mapping the siropkin application loop, accepted P6,
  current Architecture-147 safety components and current Robinhood MCP
  requirements into Architecture 148.

Do not delete accepted L43/P6 source during 148-A. Compose around it or add the
new vertical runtime first; removal of obsolete paths is a later separately
reviewed cleanup after parity tests prove replacement coverage.

## Verification strategy

Focused implementation tests should cover at minimum:

- bullish two-bar confirmation targets TQQQ;
- bearish two-bar confirmation targets SQQQ;
- neutral/no confirmation targets FLAT;
- in-progress bars never influence a decision;
- no entry in the opening exclusion window;
- no entry in the closing exclusion window;
- forced-flat starts exactly five minutes before official close;
- simultaneous TQQQ+SQQQ is impossible;
- reversal produces EXIT first and no same-cycle inverse entry;
- 3% stop derives from reconciled average fill;
- stop never widens;
- threshold breach produces mandatory EXIT;
- restart with unprotected owned position blocks entry;
- exact broker-stop coverage is required for live-ready state;
- account/buying-power/tradability/approval/review facts are part of effect
  admission;
- deterministic `ref_id` is stable for one logical intent and changes for a
  new intent;
- ambiguous placement cannot automatically retry;
- reconciliation can identify a unique order by `ref_id`;
- provider calls/effects remain zero under import, construction, help and all
  fake/source tests.

Codex/Luna should run focused tests only while iterating. The repository's
general `ops.ps1 admit` remains the required broad prepublication admission
before the one atomic feature push. The user retains final local broad
verification ownership unless repository admission itself requires it.

## 148-A exact-source acceptance and integration

Architecture 148-A is SOURCE/CERTIFICATION ACCEPTED and FAST-FORWARD INTEGRATED at `df48cdd40bcd18f2bfdc65dda201cfe2b6f199bd` / tree `2e139bdd886ee6ce8f92da57cc11ea38f341114f`, parent `ec0f33b7c15521c1901d749d5a933564360448c7`. Feature mapped FULL run `44411012023`, attempt 1, and develop run `44423510835`, attempt 1, are terminal SUCCESS. Develop reused exact feature certification with stable identity; no duplicate FULL ran.

Independent exact-source review accepted the source-only runtime and confirmed that it exposes no executor/provider composition. The review preserves two explicit live-promotion blockers for later closure rather than weakening them: protective stop-market compatibility under the current tiny-live notional, and provider approval-ID linkage when an approval-originated order does not retain the original `ref_id`. No real provider/broker effect or production state preparation occurred.

`ARCH148_A_CONNECTOR_INTEGRATION_MECHANISM_DEVIATION` records the connector-only non-force expected-old-SHA GitHub ref fast-forward used for this integration instead of the workflow-preferred admitted local `merge --ff-only` plus ordinary push. The exact accepted one-parent result and certification provenance were preserved.

## 148-B1 OPEN data and simulator contract

Architecture-148 intraday research uses the frozen OPEN interval
`[2016-01-01, 2024-01-01)` UTC and exactly `QQQ`, `TQQQ`, and `SQQQ` on
`5Min` bars with `adjustment=all`, `feed=sip`, and `currency=USD`. `QQQ` is the
signal instrument; `TQQQ` and `SQQQ` are the only simulated position symbols.
The frozen price basis is `ALPACA_ALL_ADJUSTED_INTRADAY_PRICE_V1`.
`FINAL_HOLDOUT` begins at 2024-01-01 and remains sealed.

The accepted Architecture-146 authority commits published session dates. It
does not encode Architecture-148's projected 5-minute open/close schedule.
Architecture 148 therefore owns a separate immutable schedule commitment,
which binds the accepted Architecture-146 authority identity/digest and source
bundle/manifest, `America/New_York`, the 09:30 regular open, 16:00 regular
close, 13:00 early close, schema/version, and this exact 2016-2023 early-close
set:

- 2016-11-25
- 2017-07-03, 2017-11-24
- 2018-07-03, 2018-11-23, 2018-12-24
- 2019-07-03, 2019-11-29, 2019-12-24
- 2020-11-27, 2020-12-24
- 2021-11-26
- 2022-11-25
- 2023-07-03, 2023-11-24

No other dates are modeled as early closes by this projection.

The schedule identity is
`4fe981d0-34ef-57be-a7d1-ffd017460bf5`, version
`arch148-intraday-session-schedule-identity/v1`, with SHA-256
`a33be70499cdafbfa21f45a04c854ab834425807b6c0314814b7442749aa2bad` over
canonical schedule material. The dataset and custody evidence identities and
serialized forms bind both values; parsing rejects any mismatch. The
Architecture-146 date authority alone cannot stand in for this projected
schedule commitment. The required commitment fields are carried by dataset and
custody schema v2, with corresponding v2 semantic identity versions.

Backtest signals use completed bar N and cannot execute before bar N+1 OPEN.
After an entry fills at that open using configured buy slippage, its 3% hard
stop is active for the rest of the entry bar. If the bar OPEN is at or below the
threshold, the conservative stop exit uses the OPEN; otherwise, if the bar LOW
reaches the threshold, the exit uses the threshold. The same cost/slippage model
applies to the stop sell. A stop may therefore produce `entry_at == exit_at`,
zero holding duration, one stop hit, and a FLAT simulator state; no other entry
may occur in that cycle/bar. Stop remains ahead of regime and forced-flat exits.
This protective-stop observation does not authorize a same-bar signal fill.
Non-stop regime and scheduled forced-flat exits continue to use the next bar
OPEN.

148-B1 is source-only/fake-only. It performs no provider acquisition, reads no
credentials, does not open `FINAL_HOLDOUT`, and does not authorize B2.

## 148-B2 read-only acquisition and evidence boundary

B2-A was the source-only/fake-only operator and custody checkpoint. Its accepted
and integrated executable source is HEAD `6957afa159647ece18af876289d8a20637cfc6eb`
/ tree `43701fcaef23990a793359d08a8213d43e434780`. Feature source-gate
`44485930260` and develop source-gate `44489803571` were terminal SUCCESS;
develop reused the exact feature certification. B2-A itself performed zero
credential reads and zero provider requests.

### Consumed B2-B attempt

The separately reviewed B2-B attempt
`fd8aa437-c748-4d5b-a52f-1e58b2ca5953` is CONSUMED / BLOCKED /
PAGE_LIMIT_REACHED / NO RETRY. Its retained directory is
`F:\AI\temp\arch148-b2-fd8aa437-c748-4d5b-a52f-1e58b2ca5953`. It read Alpaca
credentials once, made 64 provider attempts and received 64 successful pages.
It requested QQQ only; TQQQ and SQQQ were never requested. The incident is
classified ARCH148_B2_PROVIDER_STREAM_SCOPE_ASSUMPTION_DEFECT /
ARCH148_B2_PAGINATION_CEILING_UNDERSIZED. Detailed counts and chronology are
preserved in [the B2 acquisition plan](../validation/arch148-b2-readonly-acquisition-plan.md).
The attempt is immutable evidence, not retry authority; automatic retry is
forbidden. Robinhood, broker, order, production, FINAL_HOLDOUT and baseline
effects were all zero.

### Later completed acquisition with failed original qualification

Attempt `bb1a784b-98d1-41fd-8d95-aa9fa463d5c9`, retained under
`F:\AI\temp\arch148-b2-bb1a784b-98d1-41fd-8d95-aa9fa463d5c9`, completed its
provider acquisition: one credential read, 430 of 430 pages, zero unresolved
pagination intents, and a null end cursor for each symbol. It is CONSUMED /
BLOCKED / `QUALIFICATION_BAR_COUNT_MISMATCH` / NO RETRY because its preserved
data does not satisfy the original dense B1 downstream qualification contract.
The older `fd8aa...` page-limit incident above remains a separate immutable
event and is not rewritten.

| Symbol | Pages | Raw bars | Observed B1 slots | Missing expected slots |
|---|---:|---:|---:|---:|
| QQQ | 148 | 349805 | 156379 | 17 |
| TQQQ | 141 | 331112 | 156376 | 20 |
| SQQQ | 141 | 328679 | 156376 | 20 |

The missing-slot sets have 17 common timestamps and a 23-timestamp union. The
original B1 contract remains unchanged at 156396 expected slots per symbol;
these counts do not constitute an accepted dense B1 dataset. The sparse
requalification implementation at
`src/trading_bot/experiments/arch148_b2_requalify.py` and sparse-backtest
semantics in `src/trading_bot/experiments/arch148_sparse_backtest.py` are
accepted in source `6fb78af8c2e07d906629fd95277343eb6d54fde3` / tree
`01091cea96aa3aba6e5de8b88b64d8f722f116ba`. The exact offline result is
independently accepted with evidence SHA-256
`bdad3ab1f387617e2cef35644680e397c94d113f77f48cc242857151b352788d`,
dataset identity `0308b694-c718-5b1a-a51c-9fcc4516bb81`, and custody identity
`dbcced6a-b4cc-5d36-a33b-5e6df3d82baa`. It reports zero fully missing
sessions and zero requalification provider/broker/production/FINAL_HOLDOUT
effects. The preserved acquisition is never fetched again or retried.

### Corrected B2-A-C1 source contract

Provider documentation was rechecked on 2026-11-18. For
`GET https://data.alpaca.markets/v2/stocks/bars`, `limit=10000` is a maximum,
not an expected page size; fewer bars may be returned while more remain, so
callers must exhaust `next_page_token`. Historical stock minute bars include
pre-market and aftermarket activity, and the endpoint has no regular-session-
only filter. No separate entitlement-probe request is issued; account-specific
401/403 remains a runtime fact of the first reviewed acquisition request.
References:
[stock bars](https://docs.alpaca.markets/us/reference/stockbars),
[market data API](https://docs.alpaca.markets/us/docs/about-market-data-api),
and [historical API](https://docs.alpaca.markets/us/docs/historical-api).

The B2-A-C1 correction preserves the accepted B1 schedule, dataset, parser,
custody, simulator, price basis, 156396 expected slots per symbol, 469188 total
bars, no-lookahead semantics and FINAL_HOLDOUT boundary. The accepted B1 request
surface remains one symbol per request, `5Min`, OPEN
`[2016-01-01, 2024-01-01)`, inclusive provider end
`2023-12-31T23:59:59.999999Z`, `adjustment=all`, `asof=-`, `feed=sip`,
`currency=USD`, `sort=asc` and requested `limit=10000`. Acquisition order
remains QQQ, TQQQ, SQQQ, with sequential pagination within each symbol.

B2 validates each parsed raw provider bar for the exact requested symbol,
strict chronological order and duplicate prevention before projection. It
derives the exact accepted slot set from B1 `expected_open_slots()`. A
validated raw bar outside that set stays byte-for-byte in its raw page artifact
but is excluded from the normalized B1 dataset. This deterministic projection
does not alter raw provider evidence. The unchanged B1 dataset and custody
constructors still require exactly 156396 accepted regular-session bars per
symbol, 469188 total, identical QQQ/TQQQ/SQQQ timestamps and all existing B1
validation. Missing or malformed expected-slot data fails closed.

Terminal schema advances to
`arch148-b2-readonly-acquisition-evidence/v2`. Per symbol it reports the raw
provider bar count, qualified regular-session bar count and excluded
non-regular-slot bar count, and proves
`raw_bar_count = qualified_regular_session_bar_count + excluded_non_regular_bar_count`.
Ordered raw-page SHA-256, raw-page size and request-ID digest vectors remain
bound. Raw pages are persisted and verified before parsing or projection
advances. Terminal and failure evidence contain no raw pagination token, raw
request ID, credential, authentication header, environment value, traceback or
arbitrary exception text. B1 dataset and custody schemas and identities remain
unchanged.

The corrected B2-local ceilings are `192` pages per symbol and `576` provider
request attempts total. Provider-request starts are separated by a deterministic
minimum `0.5-second` delay after the first. Pacing occurs before authoring the
next request intent; source identity is rechecked immediately before each
intent and GET. Pacing grants no retry. HTTP 401/403, 429, 5xx, transport
ambiguity, malformed data, repeated token, source drift or either ceiling ends
the attempt immediately. No wait-and-retry, alternate feed, alternate client
or credential fallback is allowed.

The exact requalification result for preserved `bb1a...` has been
independently accepted. After this closeout is terminal green and the main
checkout `F:\AI\ai-trading-bot` is established as the exact canonical
`develop` checkout, the accepted pure sparse simulator may run OPEN zero-cost
and conservative-cost baselines against flat and QQQ controls, reporting
drawdown, whipsaw and turnover. Baseline execution makes no provider request
and does not access FINAL_HOLDOUT.

### B2-A-C1 acceptance and integration

B2-A-C1 is SOURCE/CERTIFICATION ACCEPTED and FAST-FORWARD INTEGRATED at HEAD
`0ebeaef7ea8ee83677d775fe66d037efa76c8cf1` / tree
`e16fe3aeec6a862c0d7ad7dd35e4171c1d3385e7`, parent
`298bba38cf61d506fec68cb7034fc66a58218078`. Feature mapped FULL run
`44507842755`, attempt 1, is terminal SUCCESS. Develop run `44616906540`,
attempt 1, is terminal SUCCESS with `DEVELOP_CERTIFICATION_REUSE=True`, reason
`exact_feature_certification`, and `IDENTITY_STABLE=True`; no duplicate FULL
ran. C1 source/certification/integration performed zero credential/provider,
Robinhood, broker, order, production, baseline or FINAL_HOLDOUT effects.

### Current research boundary

The C1 executable correction, public-reference source checkpoint and exact
sparse offline requalification result remain independently accepted. The
current follow-on proposal is the source-only
[Architecture 148 churn study](../validation/arch148-churn-research.md). It
fixes four descriptive variants, two existing cost cases, calendar-year OPEN
partitions and required diagnostics before any evaluation. No churn evaluation
result or new CI result is claimed here; the checkpoint does not run the OPEN
evaluation. After exact local commit and general source admission, the
separately authorized OPEN comparison is planned before publication so its
evidence can be independently reviewed; mapped CI is not a prerequisite for
that offline run. A docs/source/preflight PASS grants no credential or provider
authority. No new provider request, Robinhood, broker, order, production, Q63 or
FINAL_HOLDOUT action follows from this documentation update.

## Subsequent milestones

After accepted/integrated 148-A:

- 148-B1: source-only/fake-only 5-minute QQQ/TQQQ/SQQQ acquisition/custody and no-lookahead backtest contract, reusing existing evidence/holdout authority and selecting only an eligible pre-holdout range; no real provider call;
- 148-B2: the earlier `fd8aa...` page-limit incident and later `bb1a...` completed-but-unqualified acquisition remain separate immutable consumed attempts. The original dense B1 qualification is unchanged. Sparse offline requalification source and exact result are independently accepted; no provider retry is authorized;
- 148 churn research: the source-only proposal in [`arch148-churn-research.md`](../validation/arch148-churn-research.md) defines four fixed descriptive variants and two existing cost cases. Its separate OPEN evaluation remains pending and must be independently reviewed; no winner or promotion rule is defined;
- 148-C: desktop/demo integration and GUI status/control path;
- 148-D: current Robinhood read-only parity/preflight using the new complete
  runtime dependency closure;
- 148-E: separately reviewed protective-order and tiny-live effect boundary only
  after exact stop compatibility and risk/notional authority are proven.

No milestone automatically authorizes the next protected effect.
