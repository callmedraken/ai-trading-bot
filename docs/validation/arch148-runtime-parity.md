# Architecture 148-A runtime parity matrix

Status: **SOURCE/CERTIFICATION ACCEPTED / FAST-FORWARD INTEGRATED**.

This matrix records how the effect-free runtime in `src/trading_bot/live_runtime/`
maps the reviewed application shape, accepted P6/L43 safety contracts and the
current Robinhood MCP advertisement into Architecture 148-A. It is not provider
qualification, production readiness or authority to create durable state or
place/cancel an order. All runtime facts below are injected typed values; 148-A
does not construct an OAuth session or call Robinhood, Alpaca or an executor.

The v1 indicator contract is typical-price session VWAP `(high + low + close) / 3`
weighted by volume, reset at each official session open; EMA20/EMA50 seeded with
the first full simple average and then `2 / (period + 1)`; and RSI14 seeded from
14 close changes then Wilder-smoothed. Flat RSI is 50; gain-only/loss-only RSI
is 100/0; equal classifier comparisons remain NEUTRAL. Arithmetic uses an
explicit 48-digit ROUND_HALF_EVEN context. Only completed, five-minute-contiguous
bars through the latest completed slot are accepted; the held ETF quote must be
no older than 15 seconds. Expected-value tests pin these details.

## Pinned source references

- The reviewed MIT application loop is pinned at
  [`siropkin/robinhood-ai-trading-bot` `main.py`, lines 148–332](https://github.com/siropkin/robinhood-ai-trading-bot/blob/1a778749cfbe92c7ab9444b12e3cc73587533ade/main.py#L148-L332).
- Its Robinhood wrapper is pinned at
  [`src/api/robinhood.py`, lines 17–80](https://github.com/siropkin/robinhood-ai-trading-bot/blob/1a778749cfbe92c7ab9444b12e3cc73587533ade/src/api/robinhood.py#L17-L80),
  [121–188](https://github.com/siropkin/robinhood-ai-trading-bot/blob/1a778749cfbe92c7ab9444b12e3cc73587533ade/src/api/robinhood.py#L121-L188),
  and [221–294](https://github.com/siropkin/robinhood-ai-trading-bot/blob/1a778749cfbe92c7ab9444b12e3cc73587533ade/src/api/robinhood.py#L221-L294).
- The currently reviewed repository base for accepted P6/L43 and MCP contracts is
  [`ec0f33b7c15521c1901d749d5a933564360448c7`](https://github.com/callmedraken/ai-trading-bot/tree/ec0f33b7c15521c1901d749d5a933564360448c7).
  P6 authority and fake coverage are in [`robinhood_mcp/current_live_transport.py`](https://github.com/callmedraken/ai-trading-bot/blob/ec0f33b7c15521c1901d749d5a933564360448c7/src/trading_bot/robinhood_mcp/current_live_transport.py)
  and [`test_current_live_transport.py`](https://github.com/callmedraken/ai-trading-bot/blob/ec0f33b7c15521c1901d749d5a933564360448c7/tests/robinhood_mcp/test_current_live_transport.py).
  L43 lifecycle, ownership, state and recovery authority/test owners include
  [`l43_runtime.py`](https://github.com/callmedraken/ai-trading-bot/blob/ec0f33b7c15521c1901d749d5a933564360448c7/src/trading_bot/live_prototype/l43_runtime.py),
  [`l43_state.py`](https://github.com/callmedraken/ai-trading-bot/blob/ec0f33b7c15521c1901d749d5a933564360448c7/src/trading_bot/live_prototype/l43_state.py),
  [`l43_post_effect_reconciler.py`](https://github.com/callmedraken/ai-trading-bot/blob/ec0f33b7c15521c1901d749d5a933564360448c7/src/trading_bot/live_prototype/l43_post_effect_reconciler.py),
  [`test_l43_runtime.py`](https://github.com/callmedraken/ai-trading-bot/blob/ec0f33b7c15521c1901d749d5a933564360448c7/tests/live_prototype/test_l43_runtime.py),
  [`test_l43_state.py`](https://github.com/callmedraken/ai-trading-bot/blob/ec0f33b7c15521c1901d749d5a933564360448c7/tests/live_prototype/test_l43_state.py),
  and [`test_l43_post_effect_reconciler.py`](https://github.com/callmedraken/ai-trading-bot/blob/ec0f33b7c15521c1901d749d5a933564360448c7/tests/live_prototype/test_l43_post_effect_reconciler.py).
  Other owners include
  [`l43_production_owner.py`](https://github.com/callmedraken/ai-trading-bot/blob/ec0f33b7c15521c1901d749d5a933564360448c7/src/trading_bot/live_prototype/l43_production_owner.py),
  [`test_l43_production_owner.py`](https://github.com/callmedraken/ai-trading-bot/blob/ec0f33b7c15521c1901d749d5a933564360448c7/tests/live_prototype/test_l43_production_owner.py),
  [`l43_effect_operator.py`](https://github.com/callmedraken/ai-trading-bot/blob/ec0f33b7c15521c1901d749d5a933564360448c7/src/trading_bot/live_prototype/l43_effect_operator.py),
  [`test_l43_effect_operator.py`](https://github.com/callmedraken/ai-trading-bot/blob/ec0f33b7c15521c1901d749d5a933564360448c7/tests/live_prototype/test_l43_effect_operator.py),
  [`robinhood_mcp/models.py`](https://github.com/callmedraken/ai-trading-bot/blob/ec0f33b7c15521c1901d749d5a933564360448c7/src/trading_bot/robinhood_mcp/models.py),
  and [`robinhood_mcp/parsing.py`](https://github.com/callmedraken/ai-trading-bot/blob/ec0f33b7c15521c1901d749d5a933564360448c7/src/trading_bot/robinhood_mcp/parsing.py).

The pinned MIT loop is used as an application-shape reference only. Its main
routine owns login/refresh, waits for market open, reads account/history data,
calculates indicators and lets a model decide whether to buy/sell. Its wrapper
contains direct Robinhood login, account/history/order calls and write helpers.
148-A independently implements the deterministic decision layer and keeps all
provider acquisition and effects behind later injected adapters.

## Compact predecessor and MCP comparison

| Behavior | Pinned siropkin behavior | Accepted P6/L43 and current MCP evidence used for 148-A |
|---|---|---|
| Startup/session ownership | Main loop logs in/refreshes and polls market open; wrapper uses direct Robinhood login. | P6 binds a current session/plan to exact source identity; L43 has a serialized lifecycle and production owner. Current MCP requires account-specific OAuth session and fresh tool discovery. 148-A models the source/account/session binding but defers real composition. |
| Market data | Portfolio/watchlist history, indicators and model-directed selection are part of the loop. | MCP `get_equity_historicals` advertises regular-session five-minute bars with left-edge UTC timestamps, completed bars and interpolated-gap markers; quotes are a separate fact. 148-A requires complete contiguous completed QQQ bars and a separate fresh held-ETF price. |
| Account activity | Wrapper reads account and portfolio but does not reconcile exact local intent ownership. | MCP `get_accounts` supplies active/agentic eligibility; portfolio exposes cash and buying-power fields; paginated positions/orders carry ownership and status. L43 RHC2/RHC3 use exhaustive scoped reads. 148-A requires account identity and exhausted account-wide or exact two-ETF scope. |
| Buying power | Prompt-level budgets and direct account observations inform writes. | MCP portfolio headline buying power can include margin; 148-A feeds the shared `RiskManager` only the minimum cash, buying-power and unleveraged-buying-power amount, still capped at $10. |
| Tradability | Per-symbol PDT enrichment is part of the source loop. | MCP `get_equity_tradability` reports exact-symbol type/session eligibility, active/halt and fractional support. 148-A requires explicit QQQ/TQQQ/SQQQ facts and stop compatibility for fractional entry. |
| Approval | No durable exact pending-approval state is modeled by the loop. | MCP has `get_trade_approval_setting` and `get_trade_approvals`; a per-order request may exist even if the setting is off. An approval-originated order can carry an approval ID instead of `ref_id`. A review `approval_required` flag alone creates no provider request or receipt; 148-A requires an authenticated exact intent→approval→order link, otherwise stays blocked. |
| Broker review | The wrapper can write without a required exact preview. | MCP `review_equity_order` reviews exact order arguments and reports checks/warnings/approval requirement. P6 binds the reviewed order plan; 148-A binds fake review facts to exact account/source/session/revision/`ref_id`/digest. |
| `ref_id` | No stable logical-order identity survives from signal through market call. | Current placement accepts an idempotency key and normalized orders preserve optional `ref_id` (`robinhood_mcp/models.py` and `parsing.py`). P6 recovery requires an exact plan; L43 RHC3P settles facts by exact known identity. 148-A uses versioned UUID5 intent/ref IDs and never substitutes similar economics. |
| Placement/cancel | Direct market helpers, prompt/manual flow and generic retry are in the loop. | MCP placement may return an approval request; cancel acknowledgment is asynchronous. P6 consumes durable authority before one bounded write; L43 effect operator keeps effects behind an interlock. 148-A emits only a non-executable proposal. |
| Ambiguous writes | Generic retries do not distinguish a write that may have landed. | P6/L43 persist MAY_HAVE_OCCURRED/UNKNOWN and never auto-retry; idempotency does not prove landing. 148-A accepts only exhaustive, unique exact `ref_id` plus coherent terminal/position facts. |
| Position/order settlement | Holdings and process logs are observed, without exact local intent settlement. | MCP exposes paginated positions/orders with cumulative fills, remaining quantity and state. L43 RHC2/RHC3/RHC3P bind scope and settle exact pending facts. 148-A rejects foreign/conflicting holdings and unresolved orders; only a later fresh cycle can enter after FLAT. |
| Protective stop | The source loop has no owned-stop lifecycle. | MCP stop-market/stop-limit tools are regular-hours and whole-share only; cancellation is asynchronous and partial-trigger/cancel races remain possible. 148-A models exact stop intent, actual-fill threshold and coverage, but fractional stop incompatibility or unresolved stop lifecycle blocks. |
| Forced close | The loop waits for market open and has no reviewed forced-flat policy. | Regular-hours orders may queue for next open. 148-A uses published XNYS boundaries, reports mandatory EXIT after close, and never creates an after-close queue proposal. |
| GUI/AI authority | Console prompts and model recommendations are mixed into the trading loop. | L43's restricted application service exposes sanitized state; current MCP has broker facts but no 148 lifecycle owner. 148-A projects immutable status only; AI has no v1 order authority. |

## Behavior mapping

`REUSED` means an accepted contract or domain component remains authoritative.
`ADAPTED` means 148-A maps it into a narrower injected contract. `REPLACED`
means the old application behavior is not used by this runtime. `DEFERRED` means
a later integration milestone owns it. `NOT APPLICABLE` means it is outside v1
trading authority.

| Behavior | Disposition and 148-A owner | Focused fake regression | Deferred boundary |
|---|---|---|---|
| Startup and session ownership | **REUSED** exact `SourceIdentity`; **ADAPTED** one injected owner/source/session/account-bound `RuntimeState` and CAS protocol in `models.py` / `application.py`. | `test_state_revision_binding_failure_never_calls_cas`; `test_state_digest_and_account_drift_fail_closed_without_cas`. | Real session construction, single-run interlock and durable state provisioning/migration are owned by 148-C/D. Protected effects remain later work. |
| Market data and indicators | **REPLACED** portfolio-history/model choice with pure completed QQQ five-minute classification in `strategy.py`: typical-price session VWAP, SMA-seeded EMA20/50, Wilder RSI14 and two-bar confirmation. Explicit New York dates and Decimal context; only the current session contributes VWAP. | `test_completed_bar_regimes_warmup_vwap_and_confirmation`; `test_in_progress_bars_are_ignored_and_missing_completed_slot_blocks`; `test_history_closing_tail_and_current_vwap_open_are_required`; `test_indicator_and_stop_math_ignore_ambient_decimal_context`. | Qualified QQQ/TQQQ/SQQQ intraday data, acquisition, price-basis and provider freshness composition belong to 148-B/D. Interpolated or incomplete inputs are rejected. |
| Account activity and positions | **ADAPTED** `BrokerSnapshot`, explicit all-agent exhausted `ScopeFacts`, account fingerprint and position-owner facts. Position/order scope must be account-wide or exactly `(TQQQ, SQQQ)`. | `test_current_bounded_scope_is_exact_pair_or_account_wide`; `test_conflicting_etf_holdings_are_unknown_not_flat`; `test_scoped_entry_reconciliation_requires_unique_exact_terminal_facts`. | Real two-symbol reads, pagination and exhaustive-scope evidence belong to 148-D. Existing SPY evidence does not qualify these symbols. The normalized `Position` is long-only; a future adapter must reject short or omitted/unrepresentable positions as incomplete scope. |
| Portfolio and buying power | **REUSED** `RiskManager`; **ADAPTED** finite nonnegative cash, buying power and unleveraged buying power. Entry notional remains capped at the existing $10 ceiling and uses the minimum of those balances. | `test_entry_is_review_bound_risk_sized_and_effect_free`; `test_entry_blocks_on_review_tradability_and_power_facts`. | Real portfolio composition and any larger notional require a later reviewed milestone. |
| Tradability | **ADAPTED** typed QQQ/TQQQ/SQQQ active, halt, regular-session, fractional-entry and exact stop-compatibility facts. Unknown or false required facts deny admission. | `test_entry_blocks_on_review_tradability_and_power_facts`. | Current provider facts and exact whole-share/fractional stop feasibility are 148-D/E promotion blockers. |
| Trade approvals | **ADAPTED** fresh account/source/session/state-bound `ApprovalFacts`, request facts and durable `ApprovalRequiredReceipt`. A review flag alone only blocks; it does not create a receipt. | `test_provider_approval_receipt_requires_exact_read_fact`; `test_entry_blocks_on_review_tradability_and_power_facts`. | Provider-authenticated approval identity and approval-originated order linkage require the future adapter; unknown or incomplete approval reads remain blocked. |
| Exact broker review | **ADAPTED** review must be fresh and match account, source, session, state revision, `ref_id` and immutable terms digest. Rejection, warning, mismatch, staleness or approval requirement blocks admission. | `test_entry_is_review_bound_risk_sized_and_effect_free`; `test_review_rejection_warning_staleness_and_mismatch_block`. | 148-A accepts fake review facts only; no review endpoint is called. |
| Logical `ref_id` | **REUSED** the normalized MCP `ref_id` field; **ADAPTED** a versioned UUID5 identity binds owner, source HEAD/tree, durable sequence and immutable order economics, independent of time. | `test_stable_intent_identity_binds_sequence_owner_source_and_economics`. | A provider row with conflicting optional identity metadata is blocked; similar order arguments never substitute for the stable ID. |
| Placement and cancellation | **REPLACED** direct helper writes and retry loops with `EffectProposal`, a non-executable record whose `execution_attempted` value is always false. Typed intent kinds are ENTRY, EXIT and PROTECTIVE_STOP. | `test_entry_is_review_bound_risk_sized_and_effect_free`; `test_first_entry_then_stop_recovery_and_filled_stop_flatten`; `test_import_construction_and_help_have_no_provider_boundary`. | No executor, real review, place or cancel path exists in 148-A. Provider write normalization and separately armed effects belong to 148-E. |
| Ambiguous writes and restart | **REUSED** P6/L43 MAY_HAVE_OCCURRED / UNKNOWN and no-retry semantics; **ADAPTED** exact factual recovery under current state/source/account/session and exhausted scope. Only one unique matching `ref_id`, exact terms and coherent terminal/position facts can settle. | `test_scoped_entry_reconciliation_requires_unique_exact_terminal_facts`; `test_state_revision_binding_failure_never_calls_cas`; `test_state_digest_and_account_drift_fail_closed_without_cas`. | No-match, duplicate, partial, nonterminal, nonfill, malformed or mismatched facts remain blocked. Production persistence, migration and restart composition are deferred. Q1 remains consumed; no repair or retry is performed. |
| Position and order reconciliation | **ADAPTED** single-position TQQQ/SQQQ ownership, exhaustive scope, terminal fills and unresolved-order fencing. Two ETFs, shorts, foreign ownership, or unresolved relevant orders cannot become FLAT. An exit settlement blocks an inverse entry in the same cycle. | `test_scoped_entry_reconciliation_requires_unique_exact_terminal_facts`; `test_conflicting_etf_holdings_are_unknown_not_flat`; `test_confirmed_reversal_exits_then_reconciles_flat_before_inverse_entry`. | A fresh later cycle must reacquire facts before an inverse entry. |
| Protective stops | **REPLACED** unsupported stop handling with durable PROTECTIVE_STOP intent, threshold from reconciled average fill times exact `0.97`, no widening, and exact requested/fill/remaining coverage checks. A uniquely found OPEN stop binds by stable `ref_id` plus exact terms only after its durable intent is MAY_HAVE_OCCURRED/UNKNOWN or is already bound as RECONCILED; a PROPOSED intent cannot bind an unexpected provider row. Partial/triggered stops are not protection-ready and block competing sells. | `test_first_entry_then_stop_recovery_and_filled_stop_flatten`; `test_proposed_stop_cannot_bind_an_unexpected_open_provider_row`; `test_triggered_partial_stop_is_never_live_ready_or_competed_with`; `test_exact_terminal_cancel_releases_stop_before_replacement`; `test_missing_bound_stop_row_blocks_replacement_and_exit`; `test_quote_breach_reason_outranks_safety_regime_and_forced_flat`. | Exact broker stop precision/eligibility and cancel/replace lifecycle remain 148-E blockers. Full stop fill settles FLAT through read-only facts and cannot cause a same-cycle inverse entry. |
| Session boundaries and forced close | **REUSED** published XNYS session authority; **ADAPTED** entry starts at open+15m, ends at close-30m; forced-flat starts at close-5m, including early closes. After-close exits are reported but not queued. | `test_session_boundaries_and_published_early_close`; `test_after_close_keeps_forced_exit_reason_but_never_queues_exit`. | 148-C owns desktop cadence and fresh read-only reacquisition after a state advance. The runtime does not claim a forced close completed until broker facts reconcile it. |
| GUI status and AI authority | **ADAPTED** immutable `CycleStatus` contains regime, desired/actual position, action, blockers, mandatory-exit reasons and stop readiness without broker IDs or account secrets. AI is **NOT APPLICABLE** as v1 live authority. | Status projections are asserted in the cycle tests above; `test_import_construction_and_help_have_no_provider_boundary`. | Desktop Start/Stop, status wiring and research history are 148-C. AI cannot bypass a deterministic gate or create quantity/authority. |

## Focused proof and promotion limits

The mapped fake tests live in `tests/live_prototype/test_arch148_runtime.py` and
remain under the existing `arch147-live-prototype` FULL route. Import,
construction and help do not load a Robinhood session or expose an effect path.
The focused checks do not qualify real market data, provider schema, live stop
coverage, OAuth/session ownership, production storage or broker effects. Q63 was
not run and `FINAL_HOLDOUT` remains sealed.

## Exact-source acceptance

Accepted source identity: `df48cdd40bcd18f2bfdc65dda201cfe2b6f199bd` / tree `2e139bdd886ee6ce8f92da57cc11ea38f341114f`, parent `ec0f33b7c15521c1901d749d5a933564360448c7`.

Feature mapped FULL run `44411012023`, attempt 1, passed source-static, active tests, all seven canonical FULL lanes and source-gates. Develop run `44423510835`, attempt 1, passed with exact feature-certification reuse, stable identity and no duplicate FULL. Independent exact-source review accepted this parity mapping and its referenced implementation/tests. No provider or broker effect occurred.

The whole-share protective-stop constraint and approval-originated order identity/linkage remain explicit later promotion blockers. Acceptance of 148-A grants neither production persistence nor live broker authority.
