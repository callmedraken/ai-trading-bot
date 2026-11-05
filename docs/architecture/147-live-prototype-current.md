# Architecture 147 research-to-live prototype contract v1

## Current D34 accepted boundary and L40 transition

D30 is ACCEPTED with dataset semantic ID
`d5aa8ed7-b5cd-53a3-8671-5370f976e8e3`, dataset SHA-256
`ebe1839d510db0f24f58f9ebe02b7efb09221d4b8c06c23122f84912c3225214`, and
price basis `ALPACA_ALL_ADJUSTED_PRICE_V1`. D31's exact bundle is ACCEPTED:
campaign `9b2a000e-3adc-50f4-ab47-2aa90665e3c9`, bundle
`f01a39a7-0a65-55bb-9d38-608b1ce0bd21`, bundle SHA-256
`94870e0e0e10de16f7e98e7cfea2e2c84458a15e6f1d2665cd8a5dc7e404fc11`, result
`NONE_QUALIFIES`, retained control `BASE_MA35_50_V1`, and control candidate ID
`21158358-75be-5597-b940-5bccdda1429c`. NONE_QUALIFIES retains the control
because neither challenger qualified; it is not a winning challenger,
promotion, profitability proof, or live eligibility.

D32 is ACCEPTED / CLOSED: strategy math parity, research-binding integrity, and
live data-basis parity all passed; the 2,516 comparisons had zero mismatches.
The accepted D34 observation uses the same `ALPACA_ALL_ADJUSTED_PRICE_V1`
basis as D30/D31, so the former `DATA_BASIS_MISMATCH` blocker is closed. D33
was the additive current-signal predecessor and is now a consumed incident. Its
accepted/integrated source is
`fad65c9f4eab5bc1de4e154fdf0f59e397bc943a` / tree
`beab205abcc045fad38625ff73bb48affea9a0e9`; feature FULL
`41924058186`, attempt 1, and develop source-gate
`41936617801`, attempt 1, both succeeded, with exact feature certification
reuse on develop.

D33's one real read-only attempt is permanently CONSUMED / BLOCKED / NO RETRY.
The preserved evidence is
`F:\\AI\\temp\\arch147-d33-alpaca-observation-576b4b5c8f7b41548df7b822c44c74de\\evidence.json`,
SHA-256
`b767727712e4634950be8a6ba8f43522910d037987824ad33cb7c20c8eab95ec`,
1,999 bytes. It records `2026-11-04T23:59:08.218729Z`, credentials `1`,
provider requests `1`, selected sessions `60`, and zero production, broker,
runtime-binding, campaign, and FINAL_HOLDOUT mutations. The exact rejected
subtype is unavailable because D33 discarded it.

The consumed request was exactly:

`GET data.alpaca.markets/v2/stocks/bars?symbols=SPY&timeframe=1Day&start=2026-08-12T04%3A00%3A00.000000Z&end=2026-11-05T04%3A59%3A59.999999Z&limit=60&adjustment=all&asof=-&feed=sip&currency=USD&sort=asc`

Independent source review identifies a contract defect: its end extended past
the source-owned observation because it used end-of-calendar-day semantics.
This is not proof that the defect was the provider's exact rejection cause.

D34 is the additive recovery successor. `alpaca_signal_recovery_inputs.py`
selects exactly 60 completed published XNYS sessions, derives the final
published regular close once before credentials/provider construction, requires
that cutoff to be no later than the source-owned observation, and uses that same
value in the one Alpaca request and `CompletedSignalInputs`. It preserves
holiday, weekend, DST, and early-close authority. Its separately named operator
is `alpaca_signal_recovery_operator.py`; the consumed D33 CLI is retired before
credential/provider access and remains effect-free for `--help`.

D34 evidence uses `arch147-d34-alpaca-signal-observation/v1` and records only
closed transport/HTTP diagnostics, bounded provider codes/statuses, and a
digest-only request ID. Source admission precedes credentials/provider
construction, with exact live origin feature/develop identity and FEATURE /
PROSPECTIVE_DEVELOP authority. D34 source implementation and tests perform no
provider, credential, network, Robinhood, broker, order, runtime-binding,
campaign, paper, live, or FINAL_HOLDOUT effect.

The first D34 publication is preserved at
`9981bf47072d35381a2e5b6f187c9497e9dbed5a` / tree
`a8d2b4fb4a40039b74768b44fd0198dc87bc55f3`; mapped run `41950572892`, attempt
1, was terminal SUCCESS, but exact-source review rejected it before develop
integration. The rejected source did not perform a D34 real observation. The
bounded corrective child tightens blocked-result reason/phase/count invariants
and removes the operator fallback that could fabricate zero credential/provider
counts after an escaped failure; the published-close, source-admission,
diagnostic, and no-effect boundaries remain unchanged.

The corrective D34 source is accepted and integrated at
`b86defebf9ccbf1efb91397de8f2e66db24a6665` / tree
`9fa2360dfe7afdd902fd539e94f888063439785d`; feature mapped FULL
`41969407894`, attempt 1, and develop source-gate `41973853073`, attempt 1,
succeeded with exact feature-certification reuse. Its separately reviewed
read-only observation is consumed successfully and is not replayable:
`F:\\AI\\temp\\arch147-d34-alpaca-observation-84d32fb2af5045e7a661a77259b690fb\\evidence.json`,
2800 bytes, SHA-256
`7c6f2d391cbb3141405e3252efcfcd94db18b8e81083d947d778310bfe49464b`, schema
`arch147-d34-alpaca-signal-observation/v1`, observed at
`2026-11-05T05:28:41.664723Z`. It made one SPY daily request on the
`ALPACA_ALL_ADJUSTED_PRICE_V1` basis, ending at the exact published XNYS
regular close `2026-11-04T21:00:00.000000Z`, with response SHA-256
`296c9e89dd2f48d47b1ca3b071411d6e8509ca769fc92e433be19696bbf68c94` and
`CompletedSignalInputs` digest
`8b6d4f88012da820890cb5070de975c1d02504aeb432939a2e954d9bf9dfecb0`.

The current provider architecture is therefore Alpaca all-adjusted SIP/USD
daily data for signal inputs, with Robinhood remaining the separate
execution/custody/reconciliation provider. There is no provider fallback.
Corrected published-session cutoff semantics are part of the accepted D34
boundary. The observation validates current signal-input parity only; it does
not change D31's `NONE_QUALIFIES` result or authorize an order, live eligibility,
or L40-L43 effects. L40-L43 now own the remaining live-production path.

Q61 remains NOT RUN and no live-readiness label is granted. No paper soak is
inserted. FINAL_HOLDOUT remains sealed.

## Source and acceptance boundary

Baseline: P6 04e02042f0bd34b2fb7c603b4dfb1b68c23cf57f, tree
7269c857f86e2b0bec352ff04ecca9788d571e2f. GitHub feature run
41759329337 and develop run 41778371132, attempt 1, succeeded. Remote develop
already equals this source. This Codex implementation neither performs nor
retroactively supplies ChatGPT independent acceptance/integration authority.
Independent ChatGPT acceptance and user-run integration were recovered from the
connected chat "Review Workflow Handoff" (6aea90a7-8140-83ea-87d3-aeb667d40083).
Its latest transition closes P00 and confirms exact-feature certification reuse.
Current GitHub identities and terminal jobs were independently reverified here.
The deferred coordination closeout is incorporated into this source checkpoint;
no protected observation was performed by this implementation.

Worktree F:\AI\worktrees\ai-trading-bot-live-prototype-current; branch
feature/robinhood-live-prototype-current. Preserve P6/v1 modules and all four
consumed attempts. No fifth history-only request or quote workaround. One new
59+1 preflight may be prepared only against accepted integrated P6 source.
If the official close fails, STOP this path and design a dedicated source.

## Finish line and current effect ceiling

Five pages: Dashboard, Research, Strategy, Live Session, Activity/Health.
READY_FOR_HOST_UAT requires integrated composition, actual-service synthetic
scenarios and terminal mapped FULL; READY_FOR_BOUNDED_LIVE_TEST additionally
requires distinct native host and fresh protected provider/data evidence.
Neither label is currently granted. No paper soak. FINAL_HOLDOUT stays sealed.
No real order, credential access or provider observation is authorized by
implementation. Synthetic mode has no production transport constructor.
Default stopped/disarmed; Start never arms. Live controls remain external
reviewed operator commands. No enabled placeholder Place/Cancel/Exit buttons.

## Stable presentation interface v1

src/trading_bot/live_prototype/contracts.py owns frozen DTOs and enums.
PrototypeSnapshot is an immutable sanitized cached view. None means unavailable,
not zero. connected does not imply ready_to_trade. Activity is bounded to the
last 200 fixed-reason events; refresh renders only cached data, never I/O.
PrototypeApplicationService.snapshot returns cache; submit enqueues START/STOP
and returns command acceptance, fixed reason, disposition and evidence identity.
Acceptance is not completion. Widgets contain no financial/authority policy.
ResearchView contains all candidates, base/stress metrics, failures, assumptions,
policy, report/data provenance and explicit NOT_RUN/NONE_QUALIFIES/selection.
Viewing research never changes strategy. Selection is separate, stopped-only,
source/data/binding validated, never implied by ranking or opening an artifact.

ResearchCampaignSpec freezes candidates, formulas, dataset/price basis, periods,
costs, policy/version and total trials before data inspection. A strict immutable
ResearchComparisonBundle binds canonical semantic identities and every result;
it grants no runtime authority. SelectedStrategyBinding separately binds purpose,
research digest, strategy/config, data requirements and live eligibility.
CompletedSignalInputs must contain genuine exact completed sessions and closes
or OHLCV as required, source/adjustment identity, cutoff/as-of and digest. An
official close never supplies synthetic OHLCV. A data-basis mismatch blocks.
PrototypeSessionConfiguration binds explicit mode, selected binding, exact
executable source, external state root, read policy and reviewed risk policy.
These latter contracts are design requirements until their owning packages land.

## Lifecycle and successor live contract (design, effect-disabled)

DISARMED -> VALIDATING -> READY -> RUNNING requires source/binding/data/account,
reconciliation, exit capability and budgets all admitted. START is explicit,
never arming. READY means every applicable prerequisite passed, not connected.
A missing fact yields BLOCKED. An uncertain mutation yields UNKNOWN and consumes
its durable attempt; observation only, no retry or fresh identity workaround.
Order states are INTENT_RECORDED, INVOKED_UNKNOWN, WORKING, PARTIAL, FILLED,
CANCEL_PENDING, CANCELLED, REJECTED. Cancel acknowledgement is not terminal.
Persist intent/consumption before invocation. Recheck source/account/session/risk
immediately before every effect. Serialize intents, one working order maximum.

STOP disables new intents, enters STOPPING, joins/reconciles workers and reports
STOPPED only after confirmed shutdown. STOP does not cancel or liquidate. Close
uses the same service and stays open while shutdown is unconfirmed. KILL disables
new intents and may cancel only the exact durable owned working order under its
separate reviewed arm; it never liquidates. EXIT is a distinct reviewed sell
of reconciled owned quantity only; never unrelated holdings. These effectful
commands remain rejected by the prototype until successor capability acceptance.
Disconnect blocks new effects; reconnect can observe, never replay mutation.
Restart reconciles durable intent/order/fill/ownership/budget state before READY.
No marker/database deletion, reset or uncertain partial-state repair.

Initial successor scope is SPY long cash equities, no leverage/options/shorts/
crypto, <=$10 entry/order/gross exposure, <=$10 cumulative entry dollars, maximum
one entry and one owned exit; no automatic repeated session or budget reset.
Fees/slippage do not confer a market-fill price guarantee. Exit may cover only
verified owned fractional quantity if official broker size/minimum/order rules
support it. Missing exit capability is EXIT_CAPABILITY_UNPROVEN, never permission
to enlarge/emulate an order. A hard loss/fill-price promise cannot be implemented
with an unbounded market order: live readiness remains blocked until the effect
contract and official capabilities are independently accepted. Synthetic fixtures
are not capability evidence. Repeated operation needs a separately accepted
persistent-budget contract; P6 consumption cannot be bypassed.

## Frozen launcher interface

python scripts/run_live_prototype.py --help is effect-free.
--synthetic --state-root <fresh absolute external F: directory> launches isolated
fakes only; no default state creation on import/construction or help. Start and
Stop manage synthetic workers; no production provider exists in this route.
No live CLI flag until accepted real composition exists. Credentials/state stay
outside source. Updates are manual while stopped; no updater/scheduler machinery.

## Synthetic examples and host checklist

Initial: DISARMED/SYNTHETIC, connected=False, ready_to_trade=False, all financial
facts None, SYNTHETIC_ONLY. Cached connected=True with STALE_QUOTE still blocks.
A stopped service returns NO_EFFECT for EXIT/KILL with EXTERNAL_OPERATOR_REQUIRED.
Partial-fill/cancel acknowledgement remains nonterminal until exact observation.
Unknown/persistence failure consumes effect authority and cannot retry.

Host checklist on exact certified source: launch/help, five-page navigation,
1366x768 and 1920x1080/DPI, keyboard access, unavailable facts, responsive refresh,
Start/Stop, close during work, no orphan worker, repeated launch with isolated
state and stopped manual update. Human evidence is distinct from offscreen Qt.
All acceptance rows need evidence; source-only progress never grants readiness.

## Research comparison v2 frozen contract

This incorporates the newer independent ChatGPT P01 freeze from the connected
review chat, superseding the older companion shortlist before observing results.
Exactly BASE_MA35_50_V1 (control), PRICE_SMA200_V1, PRICE_MOM_252_V1. No skipped
month or risk-free-return ambiguity; no volatility sizing in this campaign.
All eight existing ETF symbols in UNIVERSE, five 2019-2023 annual regimes plus
continuous 2019-2023: 3 x 8 x 6 = 144 cells, each with base/stress and buy-hold
context. Prior campaign had 30 configurations/1440 cells; total configurations
considered 33 (control is intentionally rerun), not three independent trials.
Reused 2016-2023 adjusted history is robustness evidence, never fresh holdout.
No real campaign/data acquisition/FINAL_HOLDOUT access during implementation.

R10 API in experiments/filtered_trend_comparison_v2.py:
Candidate StrEnum with members BASE_MA35_50_V1, PRICE_SMA200_V1,
PRICE_MOM_252_V1. CANDIDATES tuple in that order. signal(candidate, bars,
*, invested: bool) -> str (BUY/SELL/HOLD); signal_series(candidate, bars) ->
tuple[str, ...] (HOLD before warmup); required_closes(candidate) -> int.
Bars are same-symbol, strictly increasing genuine completed bars; no imputation.
The caller passes only completed data through information session i. BASE_MA
uses accepted signal semantics and warmup 50; > bullish, < bearish, = HOLD.
SMA: at i, close[i] > mean(close[i-199:i+1]) gives bullish, < gives bearish,
and equality is HOLD; warmup 200. Momentum: at i, close[i] > close[i-252]
gives bullish, < gives bearish, and equality is HOLD; warmup 253.
Bullish yields BUY if flat, HOLD if invested; bearish SELL if invested, HOLD if
flat. Series uses BUY/SELL/HOLD as state intentions regardless of investment;
signal and series return HOLD before sufficient warmup. Fixed Decimal
Context(prec=50), no ambient dependency.

R11 API in experiments/filtered_trend_comparison_campaign_v2.py:
ComparisonSummary(candidate, candidate_id, base, stress, status, failure_code)
is the minimal typed candidate evidence representation. COMPLETE candidates own
exactly their 48 ordered cells and validated BASE/STRESS aggregates. A
FAILED_INCOMPLETE challenger owns no cells or aggregates and carries only the
fixed sanitized code CANDIDATE_EVALUATION_INCOMPLETE; it remains visible but is
ineligible. select_candidate(summaries) -> str (challenger value or
NONE_QUALIFIES); frozen_context(source_head,source_tree,dataset_id,
price_basis,dataset_provenance) -> dict; run_campaign(dataset,source_head,
source_tree) -> (context dict, complete cells, three typed candidate evidences).
UUID5 semantic identities include explicit comparison-v2 namespace/version;
semantic_identity(kind,value) -> str. No artifact bytes/path/clocks in identity.
Use immutable v1 Regime/Costs/CellEvidence/Metrics/AggregateSummary and accounting
helpers where compatible. _evaluate_cell may be adapted with the accepted
BASE_MA StrategyConfig as its validation carrier and explicit prepared_states;
financial replay is unchanged and v2 context/candidate identities distinguish
signals. No monkeypatching globals, no alteration to v1. Every candidate/symbol/
regime has evidence when complete; a bounded explicit candidate-evaluation
incompleteness records the typed failed state without dropping other candidates.
Invalid global input and unexpected programming errors fail the whole campaign;
do not fabricate cells or metrics. Fixed $100000 virtual cash, 95% allocation,
whole shares, 5% reserve; $1+5bps base/$2+10bps stress are research assumptions,
not broker fee claims. Prior-completed signals fill next open, no forced end
liquidation. Existing market/session/provenance validation must apply.

Qualification policy comparison-v2/qualification-v1 compares challengers to the
control in BOTH base and stress using only higher-is-better
positive_continuous_symbols, minimum_continuous_return,
median_continuous_return and lower-is-better worst_continuous_drawdown,
median_turnover. All five must be weakly no worse in both contexts and at least
one must be strictly better in STRESS. Annual-regime metrics remain evidence but
do not qualify or disqualify. Multiple qualifiers are ordered by STRESS
positive_continuous_symbols descending, minimum_continuous_return descending,
worst_continuous_drawdown ascending, median_continuous_return descending,
median_turnover ascending, then the same five BASE metrics in that order, then
canonical candidate ID ascending.
No threshold/variant expansion after results. NONE_QUALIFIES retains control
for research selection only; neither control nor challenger becomes live eligible.

R12 API in experiments/filtered_trend_comparison_bundle_v2.py:
ResearchComparisonBundle(context_bytes: bytes, cells: tuple[CellEvidence,...],
summaries: tuple[ComparisonSummary,...]); build_bundle(context,cells,summaries),
.to_bytes(), .from_bytes(body), .identity UUID5, .digest SHA256, .selected_candidate.
Strict bounded canonical JSON; reject unknown/duplicate fields, wrong types,
nonfinite/noncanonical numbers, missing/reordered/duplicate cells, source/policy/
data/economics/selection tampering. Recompute summaries/qualification/identities
and validate all fill/accounting evidence. Can reuse v1 decode/validation helpers
without modifying v1 or accepting v1's strategy-grid policy. No file reading in
widget: gui/research_comparison_service.py to_research_view(bundle)->ResearchView
is pure; read_comparison_report(path) reads only explicit bounded report path
on a worker, returns fixed unavailable state on malformed reports; never selects
runtime binding or launches research. R12 may start against this API before R11
lands, using fabricated typed evidence fixtures, but must complete tests after
R11 review. No permissive fallback or speculative live_eligible field.

### Canonical R11/R12 encoding freeze

Context is the v1 frozen_context output with schema changed to
filtered-trend-comparison-campaign/v2; grid is the three Candidate values;
qualification_policy comparison-v2/qualification-v1; shortlist_policy
qualified-metric-order-v2/v1; neighbor_policy null. Add
prior_configurations=30, comparison_configurations=3,
prior_campaign_id=48ae05d5-ede1-5461-9da9-b5d7744cefad, reused_history=true.
All other v1 context fields unchanged, including paper_binding=null and
live_eligible=false. Compare canonical semantic context, never tuple/list
serialization artifacts. R11 semantic_identity(kind,value) delegates v1's typed
length-framing with kind prefixed comparison-v2/. campaign_id uses kind campaign
and context; candidate_id uses kind candidate and (campaign_id,candidate.value).
Compatible v1 replay/cell-result identities are retained because their material
already includes the v2 candidate ID; unchanged replay validator reconstructs them.

The strict report envelope has exactly schema=filtered-trend-comparison-bundle/v2,
campaign_id,bundle_id,context,cells,summaries,selected_candidate,live_eligible=false.
Each summary has exactly candidate, candidate_id, status, base, stress and
failure_code. Cells contain only complete candidate evidence in frozen candidate
order; every complete candidate owns exactly 48 ordered cells, so a successful
three-candidate campaign still contains 144 cells while a failed challenger is
represented without synthetic cells or aggregate metrics.
bundle_id uses R11 semantic_identity('bundle',(context,asdict cells,asdict summaries,
selected_candidate)); identity aliases bundle_id; digest is SHA256 of canonical
report bytes, separate from semantic UUID5 identity. All typed metrics/provenance/
calendar/economic validation remains required, including all AggregateSummary
fields for type/range/canonical correctness. Re-serialization must match bytes.
Unavailable view is ResearchView(selected='UNAVAILABLE',candidates=(),
assumptions=('Comparison report unavailable',),live_eligible=False); no raw error
or provider text. Display base/stress median continuous return, stress worst
continuous drawdown and stress median turnover, clearly labeled aggregate metrics.

Launcher also permits --comparison-report <explicit path>; loading is optional
on a tracked background worker, never import/construction/Qt refresh. Opening
an artifact cannot change runtime binding. Close joins all report/worker threads
before confirmation; malformed reports yield fixed unavailable text.

### L40 immediate next milestone: unresolved capability/budget boundary

L40 is the immediate next milestone. L40 must freeze official Robinhood
fractional-position exit capability, exact owned-position exit semantics,
the distinction between entry/gross budget and safety-exit notional, honest
market-order fill/loss semantics, and no-retry / `MAY_HAVE_OCCURRED` /
`UNKNOWN` recovery. L40 remains effect-disabled and does not grant live-order
authority; L41-L43 depend on its accepted contract.

The above successor lifecycle is an effect-disabled design constraint, not an
accepted live implementation contract. Tool metadata advertises fractional
quantity market orders in regular hours with at most six decimal places, but
account eligibility, minimum sizes, exact residual exits and the source-owned
adapter still require distinct admission. Metadata is not a provider observation.
No tool/provider was invoked to inspect those descriptions.

The $10 initial order/admission ceiling does not guarantee post-fill mark-to-market
exposure under price movement. A full owned exit after appreciation could exceed
an unqualified $10 order ceiling. Exit-notional admission, loss-budget semantics
and any price constraint must therefore be frozen by the independent successor
live-contract owner before L41/L42. No exception or broader sell authority is
implemented here. This ambiguity blocks live readiness; it is not resolved by
rounding up, selling unrelated holdings, guaranteeing a market fill, or silently
increasing a budget. P6 remains untouched.
