# Architecture 152-PM2B — Research Evidence and Signal Catalog

**Status:** design-only checkpoint. PM2B freezes a typed evidence contract and
an initial descriptive signal catalog. It does not implement a factor engine,
provider, AI model, ranking system, strategy, optimizer, allocation policy, or
execution behavior. This document is a design authority for the bounded PM2C
synthetic implementation; it is not evidence that the catalog has been
computed on production or real market data.

## 1. Purpose and authority boundary

PM2B defines what future Portfolio Manager research must prove before a value
can be supplied to a later recommendation or allocation policy. The causal
chain is:

```text
source observation
  -> point-in-time source fact
  -> validated/derived feature
  -> research snapshot
  -> later decision policy
```

PM2B stops at the research snapshot. It defines representability, provenance,
point-in-time eligibility, deterministic derivation, and explicit unavailability;
it does not decide whether a security is attractive or what to do with it.

No PM2B operation may read a provider, account, credential, OAuth session, AI
service, broker, news feed, or sealed historical data. PM2A's prepared Robinhood
read-only operation remains **NOT YET AUTHORIZED**. PM1 remains disarmed and
preview-only. Arch149 confirmation remains sealed under its existing
calendar-2026 contract. PM2B grants no profitability, expected-return,
allocation, order, paper, live, or production authority.

The V1 catalog is descriptive. It deliberately excludes BUY/SELL thresholds,
composite scores, ranks, target weights, optimizer objectives, prompts, and
execution rules. A later architecture must review any policy that interprets
these values.

## 2. Reuse of current boundaries

PM2B reuses current concepts rather than creating a second research authority
stack:

- `PortfolioObservation.snapshot_id` is the account-observation identity. Its
  coverage and exact account/observation semantics remain authoritative only to
  their typed scope. `PositionObservation` retains the current known-price and
  known-cost distinctions; a missing price or cost is not zero. Portfolio
  context may refer to a future exact observation and its coverage evidence.
- PM1 `MarketQuote`, `MarketResearchInput`, `MarketSignal`, and
  `DecisionProvider` remain unchanged. `MarketSignal`'s score, rationale, and
  single `evidence_available` flag are not enough provenance for PM2B evidence
  and are not silently upgraded. A later, explicitly reviewed adapter may
  reference a PM2B snapshot without converting PM2B values automatically.
- Existing research comparison purpose/basis/dataset-digest and live-
  eligibility separation remains in force. `DiscoveryView`/`TrialLedger` and
  the research-candidate lifecycle show why binding/status is separate from
  effect authority. Candidate declarations remain inert; PM2B adds no ledger,
  lifecycle, or acceptance authority.
- Walk-forward research manifests illustrate versioned UUID5 identities from
  ordered semantic fields and result IDs. Artifact SHA-256/length validation is
  separate from artifact paths. PM2B semantic IDs remain separate from artifact
  integrity and do not use paths, fetch order, or serialized artifact bytes.
- Named exchange-calendar identity follows the repository's existing
  `BoundMarketCalendar` / `IdentifiedMarketCalendar` precedent; PM2B does not
  add a second schedule authority.
- The existing `PortfolioOptimizer`,
  `PortfolioOptimizationRequest`, `ExpectedReturn`, `ForecastHorizon`,
  `PortfolioConstraints`, and Mean-CVaR scenario boundary remain the only
  allocation interfaces. Current `ExpectedReturn` values are total arithmetic,
  non-annualized horizon forecasts, not evidence metrics. PM2B neither creates
  another optimizer nor turns arbitrary feature values into expected returns.

## 3. Evidence layers

Source observation is the ingress into the four evidence layers: it records what
an identified source channel supplied, when it was obtained, and the declared
source/version/coverage claim. It is not itself a semantic value and free-form
transport text is not authority.

| Layer | Meaning | Required boundary |
| --- | --- | --- |
| Point-in-time source fact | A typed value actually supplied by the source, with exact version, basis, timing, and provenance. | Never infer a missing fact, replace a version, or treat an economic period end as publication availability. |
| Validated/derived feature | A deterministic calculation over an acyclic, ordered set of admitted source facts and explicitly bound calendar/action artifacts. | Binds formula/version and every input identity; no fallback, interpolation, cross-basis splice, or hidden latest-value substitution. |
| Research snapshot | A coherent as-of set for a named symbol/universe and optional exact portfolio observation. | Binds catalog/version, mode, cutoff, membership, source/derived identities, statuses/reasons, and coverage. Prior snapshots are immutable. |
| Interpretation/policy | Ranking, scoring, thresholding, AI recommendation, forecasting, optimization, allocation, and execution. | Outside PM2B; may consume only typed admitted snapshots under a later review. |

No later layer repairs an unavailable earlier layer. A status is evidence about
availability, not a numeric substitute.

## 4. Point-in-time contract

All timestamps are UTC and use explicit ISO-8601 semantics. Each source fact or
derived feature distinguishes:

- `period` / `effective_at`: when the economic observation applies;
- `available_at`: the earliest instant the exact version was proven available in
  the declared source channel;
- `observed_at`: when this system obtained the observation;
- `calculated_at`: when a derived feature was computed;
- `decision_cutoff`: the inclusive latest information time admitted to a
  snapshot.

An operational snapshot admits a source fact only when its `available_at`,
actual acquisition/receipt, and any materialization needed for the admitted
decision input are no later than the cutoff. The snapshot binds the qualifying
receipt/calculation witnesses when actual system availability affects
eligibility. Historical reconstruction may acquire or calculate later only
when an immutable version-as-of witness proves the historical availability; it
must declare that reconstruction mode, preserve later calculation time as audit
metadata, must not rewrite receipt timestamps, and must not claim operational
receipt.

For a derived feature, semantic `available_at` is no earlier than the maximum
of every input's recorded availability and any separately bound source,
calendar, corporate-action, or membership artifact availability. The derivation
forms a validated DAG with typed roles and ordered immediate inputs: no cycles,
duplicate inputs unless the formula explicitly uses the same input twice, version
swaps, or fallback/last-observed-fresh claims. Dates-only evidence receives a
conservative qualified bound only through a reviewed future adapter; otherwise
it is unavailable.

Period end is never filing publication availability. Analyst estimates use the
version visible at the historical cutoff, not a later revised consensus. Price
features state unadjusted, split-only, or total-return basis and bind the
corporate-action reconstruction used. A point-in-time close is the latest
scheduled completed regular-session close on the named exchange calendar at or
before cutoff. If that expected close is unavailable, no previous-session fill
is permitted.

## 5. Provenance, identity, and arithmetic

Every source fact records, as applicable:

1. recognized source/provider identity and source version;
2. security/issuer/share-class identity and point-in-time symbol mapping;
3. field identity, typed value kind, units, and currency;
4. economic period or observation time and reporting basis;
5. `available_at`, `observed_at`, revision lineage and effective/recorded
   availability windows;
6. safe opaque provider record identity, when available;
7. source-quality and completeness state;
8. immutable content digest or evidence identity.

Free-form provider text, filesystem paths, object identity, locale, fetch order,
clock readings, and serialized artifact bytes are never semantic identity.

Derived features additionally record a versioned feature/formula identity,
ordered input identities and roles, calculation provenance, and any bound
calendar/action artifact identities. The typed dependency DAG also records the
ordered transitive source-evidence closure (for example, deterministic
first-encounter order while preserving explicit duplicate roles), so a feature
cannot hide an upstream source fact behind an intermediate ID. Snapshots bind
the exact selected fact and feature identities, not merely their keys.

Semantic IDs use stable UUID5 over explicit schema/domain/version and ordered
length-delimited canonical fields. Canonical Decimal text is finite and
ambient-context independent; UTC timestamps and symbols are normalized. Receipt
and recalculation clock annotations are separate from semantic fact IDs, so a
refetch/replay cannot change a fact identity. Append-only revisions preserve
prior versions.

Values carry typed units and currency. Conversions require an explicit,
versioned rule and evidence; unsupported FX or incompatible currency is
`UNSUPPORTED`, not an implicit conversion. Ratios and roots use exact arithmetic
where possible and an explicit versioned rounding rule (V1: correctly rounded
Decimal, half-even, 12 fractional places) independent of ambient context.

## 6. Availability vocabulary

V1 uses these seven statuses and typed reason codes:

| Status | Meaning |
| --- | --- |
| `AVAILABLE` | Required typed evidence and formula inputs are present, valid, temporally eligible, and complete for the declared scope. |
| `MISSING` | A required fact or scheduled observation is absent; no zero, carry, interpolation, or shrinking window is allowed. |
| `STALE` | Evidence exists but a named, explicitly applied freshness rule says it cannot support this slot. PM2B does not invent universal age durations. |
| `UNSUPPORTED` | The value is known non-applicable or its domain/denominator/basis/currency is unsupported. |
| `NOT_YET_AVAILABLE` | The exact fact is known to have become available only after the cutoff, distinguished by typed reason between later source-channel publication and later operational receipt/materialization. |
| `CONFLICTED` | Multiple genuinely like-for-like candidate facts (same subject, period, basis, units, and currency) remain conflicting; candidate identities are preserved and no value is admitted until a later policy resolves them. A duly superseded earlier revision is not a conflict with its later revision. |
| `INVALID` | Corrupt, impossible, nonfinite, malformed, identity-inconsistent, timing-inconsistent, or basis-inconsistent evidence. |

Reasons are typed, ordered, and reproducible; PM2B does not invent business
precedence between causes. An observed zero remains a zero; unavailable values
have no numeric output. Negative earnings do not become an attractive P/E, and
an absent P/E is not zero.

## 7. Catalog schema

Each catalog entry has:

`catalog_version`, stable `feature_key`, `family`, `kind` (`RAW` or `DERIVED`),
conceptual formula, ordered input keys and roles, value type/unit/currency,
security/universe scope, period basis, window and named calendar, adjustment
basis, availability/status rules, invalid-denominator/domain rules, and
point-in-time caveats. Parameterized keys include every parameter in the
semantic identity (for example symbol, horizon, benchmark, and adjustment
basis). Raw facts are never silently aliased to another provider field.

Common raw fact groups in V1 include:

- regular-session unadjusted close; PIT split-only and total-return corporate
  actions as separate bases;
- issuer/share class and shares outstanding with effective time;
- field-versioned fiscal series and reporting basis;
- filing OCF, capex, revenue, COGS, operating income, attributable-common net
  income, discrete diluted EPS, total stockholders' equity, attributable-common
  equity, cash/equivalents, interest-bearing total debt, EBIT basis, operating
  D&A, operating interest expense (gross recognized expense, separate from
  interest income);
- consensus EPS/revenue and as-of membership/classification;
- typed `PortfolioObservation` positions, cash, equity, quotes, cost, and future
  realized-fill/context evidence.

V1 raw facts have stable keys; the common provenance, timing, units, and status
fields above are inherited by every raw key:

| Raw key | Value/unit and temporal basis |
| --- | --- |
| `raw.price.close.unadjusted` | Positive currency/share regular-session close, exchange date/session and source timestamp. |
| `raw.price.action.split` / `raw.price.action.total_return` | Typed corporate-action record, effective/ex-date, announced/available version, and reconstruction basis; split-only and total-return are separate keys. |
| `raw.security.issuer_share_class` / `raw.security.shares_outstanding` | Issuer, security/share class, point-in-time mapping; shares are count with effective window. |
| `raw.fiscal.quarter.{field}.discrete` | One exact recognized field (`ocf`, `capex_ppe`, `revenue`, `cogs`, `operating_income`, `net_income_attributable_common`, `diluted_eps`, `operating_da`, or `operating_interest_expense_gross`) for one discrete fiscal quarter, with reporting basis and period end. |
| `raw.fiscal.annual.{field}` | One exact annual fiscal actual for a recognized flow field, with fiscal-year identity, reporting basis, period end, and revision. Annual values are not quarterized without the explicit same-FY rule. |
| `raw.fiscal.ytd.{field}` | One exact same-fiscal-year cumulative YTD flow field for quarterization, with YTD start/end and revision; it cannot stand in for a discrete quarter without the explicit subtraction rule. |
| `raw.fiscal.balance_sheet.{field}.pit` | Point-in-time fiscal balance field (`total_stockholders_equity`, `equity_attributable_common`, `cash_equivalents`, or `total_debt_interest_bearing`) with as-of period/effective timestamp and revision; balance-sheet facts are never quarterized as flows. |
| `raw.consensus.{metric}` | Provider/versioned EPS or revenue consensus for fixed source-declared forecast start/end interval, target fiscal period, units, and as-of membership; metric is not a free-form alias. |
| `raw.classification.membership` | Point-in-time peer/sector/benchmark membership with classification version, effective/publication window and typed role (`subject`, `peer_panel`, `sector`, or `benchmark`) plus source evidence. |
| `raw.portfolio.observation` | Exact named RAW selection from `PortfolioObservation`: account, cash/equity, position quantity/mark/cost, coverage, snapshot ID, and observation time. It proves only its typed scope, not PM2B `available_at` or historical provider version without a reviewed adapter. |
| `raw.portfolio.fill` | Future named RAW executed-fill selection with account, currency, execution time, notional, deduplication identity, and completeness witness. |

Parameterized raw keys include the security/share class, field/metric, fiscal
period or target, provider/version, named calendar, and basis as semantic
parameters where applicable; unrecognized provider fields cannot satisfy a raw
key by name similarity.

Rows such as `fcf.ocf`, `fcf.capex`, valuation inputs, leverage inputs, and
portfolio cost are transparent DERIVED selections only when they point to the
exact named RAW fact ID and apply no undocumented alias or normalization.

### Period and TTM construction

TTM is the latest effective eligible fiscal-period anchor plus four consecutive
discrete fiscal quarters of the same issuer, calendar/accounting basis, with a
revision availability timestamp for every quarter. Missing or stale required
quarters are not skipped. Prior growth uses the same fiscal-quarter anchor four
quarters earlier, with its own TTM.

Quarterization is allowed only for a common-basis cumulative statement and an
explicit same-fiscal-year identity: Q1 is direct; Q2/Q3 are current YTD minus
preceding YTD; Q4 is annual minus nine-month YTD. Both component evidence IDs
and their revisions are stored. TTM EPS is the sum of four discrete diluted
attributable-common EPS values normalized to one admissible share/split basis;
it is never a difference of cumulative EPS.

## 8. V1 catalog

The following entries freeze the V1 conceptual formulas. A future implementation
must preserve the named inputs, ordering, units, basis, and unavailable behavior.
Unless a row explicitly names a raw fact, every entry in §8 is `DERIVED`. Ratio,
margin, yield, return, volatility, correlation, and weight outputs are stored as
dimensionless fractions; amount outputs use the stated source currency; price
outputs are currency/share; share counts and holding counts are counts; vectors
retain the ordered element unit. Every derived row carries its ordered source
keys, formula version, period/window, and status even when a compact table row
does not repeat those common fields.

### 8.1 Valuation

| Key | Formula and required inputs | Availability and timing |
| --- | --- | --- |
| `valuation.pe_ttm` | Point-in-time unadjusted close / TTM diluted EPS on the same admissible share basis. | `AVAILABLE` only when EPS > 0; EPS <= 0 is `UNSUPPORTED`/not meaningful, never a signed P/E or zero. |
| `valuation.pe_ntm` | Point-in-time unadjusted close / exact provider NTM diluted EPS consensus for the source-declared fixed forecast interval `[forecast_start, forecast_end]` visible at cutoff. | The interval, target/horizon, publication/revision provenance, and point-in-time membership are bound; denominator <= 0 is `UNSUPPORTED`; PM2B never synthesizes NTM from FY-next. |
| `valuation.earnings_yield_ttm` | TTM diluted EPS / same-basis unadjusted close. | Signed result permits genuine negative earnings; missing EPS/close preserves its status. |
| `valuation.market_cap_common` | Same point-in-time positive unadjusted close × positive supported eligible common shares outstanding, same class/basis. | V1 supports one comparable common class only; invalid/nonpositive price or shares and class/basis ambiguity are `INVALID`/`UNSUPPORTED` as applicable. |
| `valuation.price_sales_ttm` | Common market cap / TTM revenue. | Positive revenue denominator required; currency and period basis must match. |
| `valuation.price_book` | Common market cap / latest eligible common book equity. | Positive common-equity denominator and same class/basis required. |

FCF yield is owned by the canonical `fcf.yield_ttm` key in §8.3; valuation
views reference that identity rather than define a competing key.

### 8.2 Growth and revisions

| Key | Formula and required inputs | Availability and timing |
| --- | --- | --- |
| `growth.revenue_ttm_yoy` | `(current TTM revenue - prior same-fiscal-quarter TTM revenue) / prior TTM revenue`. | Prior denominator must be > 0; otherwise `UNSUPPORTED`; both TTM sets are PIT eligible. |
| `growth.diluted_eps_ttm_yoy` | Same formula using normalized diluted attributable-common EPS TTM. | Prior EPS must be > 0; negative current EPS remains a genuine signed numerator, not a fabricated ratio. |
| `growth.eps_forward` | FY-next consensus EPS minus latest completed FY reported diluted EPS, divided by the reported EPS. | Positive reported actual required; consensus has a fixed source-declared forecast interval and target fiscal period following anchor FY; no NTM/FY-next synthesis; visible by cutoff. |
| `growth.revenue_forward` | FY-next consensus revenue minus latest completed FY reported revenue, divided by reported revenue. | Same fixed source-declared interval, target/basis/cutoff rules; do not equate this with NTM. |
| `growth.estimate_revision` | Latest as-of consensus minus prior same-provider consensus, for fixed metric/target/horizon; optional normalized change is a separately keyed feature. | Prior anchor is exactly 21 completed sessions before the as-of last close on the named calendar. Contributor/aggregation policy, basis, units (currency/share or amount), publication/revision timestamps, and both consensus identities are required; no horizon rolls or late consensus. |

### 8.3 Free cash flow

| Key | Formula and required inputs | Availability and timing |
| --- | --- | --- |
| `fcf.ocf` | Typed RAW selection `raw.fiscal.quarter.ocf.discrete` (or the explicitly bound annual/YTD source at its declared grain), in source currency. | Exact filing field, fiscal period, reporting basis, revision, and available timestamp are retained; no unsupported alias. |
| `fcf.capex` | Qualifying PPE purchases selected from `raw.fiscal.quarter.capex_ppe.discrete`, normalized to a positive cash-outflow magnitude. | Sign normalization is a versioned DERIVED step over the exact RAW fact; no invented value or sign guess. |
| `fcf.free_cash_flow` | OCF - capex. | Both inputs share the fiscal period/basis and revisions. |
| `fcf.ttm` | Sum of four eligible discrete quarterly FCF values. | Same-issuer TTM construction; no skipped quarter. |
| `fcf.margin_ttm` | TTM FCF / TTM revenue. | Positive TTM revenue required; otherwise `UNSUPPORTED`. |
| `fcf.growth_ttm_yoy` | `(current TTM FCF - prior same-fiscal-quarter TTM FCF) / prior TTM FCF`. | Positive prior FCF denominator required; signed current FCF is retained. |
| `fcf.yield_ttm` | TTM FCF / common market cap. | Canonical FCF yield identity; signed yield allowed and basis/currency must align. Valuation references this key. |

### 8.4 Quality and profitability

| Key | Formula and required inputs | Availability and timing |
| --- | --- | --- |
| `quality.gross_margin_ttm` | `(revenue - COGS) / revenue`. | TTM common basis; positive revenue required. |
| `quality.operating_margin_ttm` | Operating income / revenue. | Positive revenue required; negative operating income is retained. |
| `quality.net_margin_ttm` | Attributable-common net income / revenue. | Positive revenue required; attributable-common field is explicit. |
| `quality.roe_ttm` | TTM attributable-common net income / arithmetic mean of common equity at TTM end and four quarters earlier. | Both positive equity endpoints required; endpoint identities and timing are bound. |
| `quality.pre_tax_operating_roic_ttm` | Operating income TTM / average(total debt + common equity - cash/equivalents) at matching endpoints. | Both positive invested-capital endpoints required. This is a named pre-tax operating return substitute, not silently equivalent to after-tax ROIC. |
| `quality.operating_margin_persistence` | Ordered four quarterly operating-margin values for the TTM quarters. | Descriptive vector only; same issuer/basis and explicit per-quarter statuses; no persistence threshold or composite. |

### 8.5 Leverage and balance sheet

| Key | Formula and required inputs | Availability and timing |
| --- | --- | --- |
| `leverage.cash` / `leverage.total_debt` | Typed RAW selections `raw.fiscal.balance_sheet.cash_equivalents.pit` and `raw.fiscal.balance_sheet.total_debt_interest_bearing.pit`, in source currency. | Exact balance-sheet period/effective timestamp and revision; no current-period substitution or quarterization. |
| `leverage.net_debt` | Total debt - cash/equivalents. | Signed result allowed when cash exceeds debt. |
| `leverage.debt_equity` | Total debt / common equity. | Positive common-equity denominator required. |
| `leverage.net_debt_ebitda` | Net debt / TTM EBITDA. | EBITDA = TTM operating income + qualifying operating D&A, with compatible accounting and no double count; positive EBITDA required. |
| `leverage.interest_coverage` | TTM operating income / positive gross recognized operating interest expense for the same period. | Interest expense excludes interest income and uses the explicit gross expense field; positive denominator required; negative numerator is retained. |

### 8.6 Momentum and trend

Price features use exchange-date calendar-month anchors relative to the last
completed regular-session close. For 1/3/6/12 month horizons, subtract the
calendar interval, clip to month end, and choose the on-or-before session close;
there is no previous-session substitution for a missing expected close. Every
used interval must contain all scheduled sessions, with no interpolation or
cross-basis splice.

Split-only adjustment restates historical prices to the latest share basis using
only eligible split actions. Total-return adjustment additionally chains a
compatible cash distribution at its ex-date close: for adjacent adjusted prices
`A_prev` and `A_t` and ex-date cash distribution `D_t`, the one-step factor is
`(A_t + D_t) / A_prev`. The reconstruction binds original unadjusted prices,
action identities, effective/ex dates, and version. An unsupported action or
incompatible distribution blocks the feature; it is not silently skipped.

| Key | Formula and required inputs | Availability and timing |
| --- | --- | --- |
| `momentum.return_1m`, `return_3m`, `return_6m`, `return_12m` | `(current total-return close / anchored prior total-return close) - 1`. | Total-return series is PIT: only corporate actions effective/known by cutoff; bind original unadjusted prices, action records, reconstruction basis, calendar, and complete sessions. |
| `momentum.return_12m_minus_1m` | `(T[-1m] / T[-12m]) - 1` on the total-return series, using only the -12 and -1 month anchors. | Same complete total-return basis; neither the current close nor a difference of returns is substituted; missing anchors are `MISSING`. |
| `trend.sma_20`, `sma_50`, `sma_200` | Arithmetic mean of the last N completed closes on a split-only series restated to the latest close share basis. | Requires N complete sessions and explicit split-action reconstruction; dividends are not silently mixed into this basis. |
| `trend.distance_to_sma_N` | Latest split-only close / corresponding SMA - 1. | Same coverage and basis as the SMA; N is part of the key. |

### 8.7 Volatility and downside

Risk features use 64 consecutive completed closes and 63 same-basis daily
returns on the named calendar. They are daily and unannualized unless a later
version explicitly adds an annualized key.

| Key | Formula and required inputs | Availability and timing |
| --- | --- | --- |
| `risk.realized_volatility_63d` | Sample standard deviation of 63 total-return daily returns (`n - 1` denominator). | All 64 closes and paired sessions required; no shrinking window. |
| `risk.downside_deviation_63d` | `sqrt(mean(min(return, 0)^2))` over all 63 returns, including non-downside zero terms. | Same complete window; no omission of nonnegative days. |
| `risk.maximum_drawdown_64close` | `max(1 - close_t / running_peak_t)` over ordered 64 total-return closes, with deterministic earliest peak/trough dates when values tie. | No interpolation or unordered reduction; a complete no-loss path is the genuine value 0; insufficient history is `MISSING`. |
| `risk.tracking_error_63d` | Sample standard deviation of 63 paired daily excess returns versus an identified benchmark on the exact same sessions. | Benchmark identity, calendar, basis, and pair coverage required; no blind inner join. |

### 8.8 Relative attractiveness context

Peer/sector/benchmark context binds point-in-time classification, membership
version/effective window/publication, coverage, data basis, and each eligible
peer's evidence identity. Membership cannot be inferred from today's sector.
The stable `raw.classification.membership` key supplies a typed role for
`subject`, `peer_panel`, `sector`, or `benchmark`, and the derived peer panel
key `relative.peer_panel` binds the ordered eligible peer IDs, same-time
membership window, coverage, data basis, and per-peer evidence IDs. Required
membership or panel coverage that is absent is `MISSING` (or another evidenced
typed state); known incomplete numeric data remains attached to the affected
peer's status. Peers are never pruned or substituted to make the panel
complete. Its output unit is an ordered typed-ID vector, not a score. The optional descriptive
`relative.active_return_3m` is symbol total return minus benchmark total return
over the same 3-month anchors, calendar, currency, and complete sessions. PM2B
produces no relative score, rank, or winner.

### 8.9 Portfolio context

Portfolio features bind one exact account observation/cutoff and its coverage.
Cash and broker-reported equity remain distinct typed RAW selections. Position
quantity, known current mark, and account identity are used only when supported
by the observation; exact portfolio snapshot identity and point-in-time group
membership are required. A mark is admissible only when the PM2B adapter proves
its source, version, currency, timestamp, and PIT eligibility; a positive
quantity with no source-proven mark is unavailable, and an invalid/nonpositive
price rejects the derived exposure rather than becoming zero.

| Key | Formula and required inputs | Availability and timing |
| --- | --- | --- |
| `portfolio.cash` / `portfolio.broker_equity` | Typed RAW selections from the exact `PortfolioObservation` scope. | A zero is emitted only when the observation proves zero; missing coverage is not zero. |
| `portfolio.exposure` | Supported position quantity × known current mark. | Same currency, supported long scope, and complete typed coverage required. |
| `portfolio.symbol_weight` | Symbol exposure / positive broker-reported equity. | Positive equity and exact observation/cutoff required. |
| `portfolio.group_weight` | Sum of eligible exposures in a point-in-time group / positive broker-reported equity. | PIT group membership and complete member coverage required. |
| `portfolio.concentration_context` | Reproducible descriptive tuple: active nonzero holding count plus the ordered per-symbol and per-point-in-time-group exposure/weight vectors (with membership IDs). | No target or constraint is inferred; incomplete coverage preserves `MISSING`. |
| `portfolio.cost_basis` | Typed RAW selection of known average cost from a supported position observation, in currency/share. | No tax-lot or entry-date claim; missing cost is not zero. |
| `portfolio.unrealized_pnl` | Quantity × (known current price - known average cost). | Both prices/costs, same currency, and supported long scope required. |
| `portfolio.gross_realized_turnover_21d` | Sum of absolute valid executed-fill notionals over 21 completed calendar sessions / mean of positive beginning and ending account equity. | Exact account/currency, deduplicated fills, completeness, and cash-flow/order separation required; no projected or optimizer turnover. |
| `portfolio.pair_correlation_63d` | Pearson correlation of two symbols' total-return daily returns on 63 exact common session dates. | Missing dates/coverage are `MISSING`; after complete coverage, zero sample variance in either leg is `UNSUPPORTED`; same basis/calendar and exact ordered dates are required. |

## 9. Snapshot contract

A snapshot binds:

- catalog and entry versions;
- named calendar, as-of mode, inclusive decision cutoff, and a calculation-time
  audit witness (wall-clock calculation time is not semantic snapshot identity);
- ordered security/universe identities and PIT membership evidence;
- every admitted source-fact and derived-feature identity, ordered dependency
  roles, value/basis/unit metadata, and status/reason (including unavailable);
- the exact portfolio observation and coverage when portfolio context is used;
- acquisition witnesses when operational receipt governs eligibility.

It must not combine a newer fundamental with an older timestamp that makes the
value appear historically available. A replay may record a different
calculation-time audit annotation without changing semantic fact or snapshot
identity. Snapshots are immutable and informational;
existence grants no optimizer or order authority.

## 10. AI and allocation firewalls

Future AI recommendations may consume only typed, admitted research evidence and
must trace to the exact snapshot and evidence IDs. AI must not invent missing
values, substitute a source or formula, alter timestamps, turn unavailable
evidence into a numeric score, or own market price, quantity, allocation, risk,
or dispatch authority. PM2B selects no AI provider and sends no prompt/request.

PM2B does not infer an `ExpectedReturn` from a factor, choose a covariance or
risk model, set risk aversion, choose a Mean-CVaR objective, set thresholds,
weights, views, or portfolio targets. A later policy may explicitly adapt
validated snapshot evidence into the existing optimizer request, preserving the
existing long-only/no-leverage/risk boundaries.

## 11. Qlib and PyPortfolioOpt review

Qlib is an architectural reference, not a project dependency. Its documented
pattern separates data loading, expression/feature processing, dataset
construction, workflow configuration, recorder artifact tracking, and a
point-in-time guide that distinguishes publication date from report period:
[Qlib data](https://qlib.readthedocs.io/en/latest/component/data.html),
[Qlib PIT](https://qlib.readthedocs.io/en/latest/advanced/PIT.html),
[Qlib workflow](https://qlib.readthedocs.io/en/latest/component/workflow.html),
and [Qlib recorder](https://qlib.readthedocs.io/en/latest/component/recorder.html).
PM2B adopts that separation conceptually. Qlib's downloadable US/CN data or
loadability does not attest this project's revision lineage, publication
cutoff, point-in-time availability, eligible universe, or evidence identity;
Qlib does not become the authority for those contracts.

The canonical PyPortfolioOpt repository is
[`PyPortfolio/PyPortfolioOpt`](https://github.com/PyPortfolio/PyPortfolioOpt/blob/main/docs/UserGuide.rst).
Its guide treats optimization as consuming expected-return estimates and a
covariance/general risk model and supports caller-supplied models. PM2B treats
it only as a possible later allocation reference. It is not an evidence source,
not a provenance authority, and is not added as a dependency.

## 12. Deferred decisions and next milestone

Deferred to later separately reviewed milestones: events/news, macro/regime
data, vendor selection, FX conversion, freshness-age policy, conflict
arbitration, ranking/scoring/threshold policy, forecast calibration, covariance
or other risk-model estimation, optimizer/objective/target selection, AI
provider qualification, real-data qualification, and live selection.

**PM2C — synthetic typed evidence/catalog/snapshot implementation** is the next
bounded milestone. It may implement only the contracts frozen here, with
synthetic fixtures and adversarial tests first: identity stability, dependency
DAGs, PIT modes, status/reason preservation, denominator behavior, basis/unit
normalization, complete windows, snapshot immutability, and portfolio coverage.
It must not add a production feed, provider request, factor engine, model,
policy, optimizer, or execution path.
