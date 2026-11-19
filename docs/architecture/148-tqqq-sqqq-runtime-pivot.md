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
parity matrix before source publication rather than a prose-only survey.

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

## Subsequent milestones

After accepted/integrated 148-A:

- 148-B1: source-only/fake-only 5-minute QQQ/TQQQ/SQQQ acquisition/custody and no-lookahead backtest contract, reusing existing evidence/holdout authority and selecting only an eligible pre-holdout range; no real provider call;
- 148-B2: one separately reviewed read-only historical acquisition/qualification on accepted B1 source, followed by the deterministic baseline backtest against flat/QQQ controls with drawdown, whipsaw and turnover reporting. Existing daily-only research history is not sufficient evidence for these intraday rules;
- 148-C: desktop/demo integration and GUI status/control path;
- 148-D: current Robinhood read-only parity/preflight using the new complete
  runtime dependency closure;
- 148-E: separately reviewed protective-order and tiny-live effect boundary only
  after exact stop compatibility and risk/notional authority are proven.

No milestone automatically authorizes the next protected effect.
