# Architecture 147 research-to-live prototype contract v1

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
tuple[str | None, ...] (None before warmup); required_closes(candidate) -> int.
Bars are same-symbol, strictly increasing genuine completed bars; no imputation.
The caller passes only completed data through information session i. BASE_MA
uses accepted signal semantics and warmup 50; > bullish, < bearish, = HOLD.
SMA: at i, close[i] > mean(close[i-199:i+1]) gives bullish; <= bearish, warmup 200.
Momentum: at i, close[i] > close[i-252] bullish; <= bearish, warmup 253.
Bullish yields BUY if flat, HOLD if invested; bearish SELL if invested, HOLD if
flat. Series uses BUY/SELL as state intentions regardless of investment.
signal raises ValueError on insufficient warmup; series None cannot reach a
trading regime. Fixed Decimal Context(prec=50), no ambient dependency.

R11 API in experiments/filtered_trend_comparison_campaign_v2.py:
ComparisonSummary(candidate: Candidate, candidate_id: str, base: AggregateSummary,
stress: AggregateSummary); select_candidate(summaries) -> str (challenger value
or NONE_QUALIFIES); frozen_context(source_head,source_tree,dataset_id,
price_basis,dataset_provenance) -> dict; run_campaign(dataset,source_head,
source_tree) -> (context dict, tuple[CellEvidence,...], tuple[ComparisonSummary,...]).
UUID5 semantic identities include explicit comparison-v2 namespace/version;
semantic_identity(kind,value) -> str. No artifact bytes/path/clocks in identity.
Use immutable v1 Regime/Costs/CellEvidence/Metrics/AggregateSummary and accounting
helpers where compatible. _evaluate_cell may be adapted with the accepted
BASE_MA StrategyConfig as its validation carrier and explicit prepared_states;
financial replay is unchanged and v2 context/candidate identities distinguish
signals. No monkeypatching globals, no alteration to v1. Every candidate/symbol/
regime has evidence even if it fails qualification. Invalid input fails the
whole campaign; do not drop cells. Fixed $100000 virtual cash, 95% allocation,
whole shares, 5% reserve; $1+5bps base/$2+10bps stress are research assumptions,
not broker fee claims. Prior-completed signals fill next open, no forced end
liquidation. Existing market/session/provenance validation must apply.

Qualification policy comparison-v2/qualification-v1 compares every field of
AggregateSummary against control for BOTH base and stress. Higher is better for
positive_regime_cells, minimum_regime_return, median_regime_return,
positive_continuous_symbols, minimum_continuous_return, median_continuous_return.
Lower is better for negative_regime_cells, worst_regime_drawdown,
median_regime_drawdown, median_turnover, worst_continuous_drawdown. All weakly
better in both cases AND strictly better in >=1 stress field qualifies.
Stable fixed challenger order SMA200 then MOM252 breaks multiple qualifiers.
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
qualified-fixed-order-sma200-mom252/v1; neighbor_policy null. Add
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
bundle_id uses R11 semantic_identity('bundle',(context,asdict cells,asdict summaries,
selected_candidate)); identity aliases bundle_id; digest is SHA256 of canonical
report bytes, separate from semantic UUID5 identity. All typed metrics/provenance/
calendar/economic validation remains required. Re-serialization must match bytes.
Unavailable view is ResearchView(selected='UNAVAILABLE',candidates=(),
assumptions=('Comparison report unavailable',),live_eligible=False); no raw error
or provider text. Display base/stress median continuous return, stress worst
continuous drawdown and stress median turnover, clearly labeled aggregate metrics.

Launcher also permits --comparison-report <explicit path>; loading is optional
on a tracked background worker, never import/construction/Qt refresh. Opening
an artifact cannot change runtime binding. Close joins all report/worker threads
before confirmation; malformed reports yield fixed unavailable text.

### L40 unresolved capability/budget boundary

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
