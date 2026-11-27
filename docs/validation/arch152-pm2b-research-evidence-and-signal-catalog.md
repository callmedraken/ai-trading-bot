# Architecture 152-PM2B — Research Evidence and Signal Catalog validation record

**Validation type:** design/documentation-only. This record verifies coverage
of the PM2B contract and its exclusions; it does not claim that synthetic or
real catalog calculations have run. No provider, account, credential, AI,
broker, or market-data read is authorized by this record.

## 1. Design acceptance checklist

| Requirement | Design evidence |
| --- | --- |
| Five-stage causal chain | Architecture §1 and §3 freeze source observation ingress -> point-in-time fact -> validated/derived feature -> research snapshot -> later policy. |
| Four-layer separation | Architecture §3 distinguishes source facts, derived features, snapshots, and interpretation/policy. |
| Point-in-time semantics | Architecture §4 defines period/effective time, available/observed/calculated timestamps, inclusive cutoff, operational versus historical reconstruction, and derived availability. |
| Provenance and identity | Architecture §5 binds provider/version, security/share class, field, units/currency, period, timestamps, record identity, quality/completeness, digest, ordered UUID5 inputs, and immutable revisions. |
| Availability | Architecture §6 preserves AVAILABLE, MISSING, STALE, UNSUPPORTED, NOT_YET_AVAILABLE, CONFLICTED, and INVALID with typed reasons and no numeric substitution. |
| Catalog schema | Architecture §7 requires version, key, family, raw/derived kind, formula, ordered roles/inputs, unit, scope, period/window/calendar, adjustment, status, and caveats. |
| V1 families | Architecture §8 covers valuation; growth/revisions; free cash flow; quality/profitability; leverage; momentum/trend; volatility/downside; relative context; and portfolio context. |
| Snapshot boundary | Architecture §9 binds catalog, mode/cutoff, calendar, membership, exact identities/statuses, portfolio observation, and acquisition witnesses when required. |
| AI firewall | Architecture §10 permits only typed traceable evidence and forbids invention, substitution, timestamp edits, numeric scoring, and market/allocation/risk/dispatch authority. |
| Allocation firewall | Architecture §10 reuses current optimizer contracts and forbids feature-to-forecast inference, covariance/objective/risk-aversion/weight choices, and PyPortfolioOpt dependency. |
| Qlib review | Architecture §11 records loading/processing/dataset/workflow/recorder/PIT as reference patterns while rejecting automatic provenance/PIT authority. |
| PyPortfolioOpt review | Architecture §11 records expected returns + covariance/general risk model and caller-supplied models as later allocation reference only. |
| PM2A/PM1/Arch149 boundaries | Architecture §1 preserves PM2A NOT YET AUTHORIZED, PM1 disarmed/preview-only, and sealed Arch149. |

## 2. Family contract matrix

Every row below is a required PM2C synthetic contract area. `Status` means the
fixture must preserve the named typed status/reason rather than inventing a
value.

| Family | Required provenance/timing contract | Required missing/invalid contract |
| --- | --- | --- |
| Valuation | PIT close, share class/shares, TTM/consensus version, fiscal availability, price and earnings basis. | Positive-denominator rules; negative EPS is not low P/E; conflicts and unavailable inputs propagate. |
| Growth/revisions | Same-fiscal-quarter TTM anchors; fixed source-declared forward interval/target; fixed provider/metric/horizon and 21-session prior consensus anchor. | No late consensus, horizon rolling, skipped quarter, or nonpositive prior-growth denominator. |
| Free cash flow | OCF and positive capex-outflow field identities; same-period revisions; explicit quarterization and four-quarter TTM. | No invented/aliased capex, skipped quarter, or hidden sign normalization. |
| Quality/profitability | Attributable-common net income, revenue, COGS, operating income, common-equity endpoints, and ordered quarterly operating margins; no leverage-owned EBITDA input. | Positive denominators where required; negative numerators remain signed; no silent after-tax ROIC claim. |
| Leverage | Last eligible fiscal balance plus same-period TTM operating income, qualifying operating D&A, and gross operating interest expense; this family owns the explicit EBITDA construction. | Invalid denominator is UNSUPPORTED; signed net debt and negative numerator retained; no D&A double count. |
| Momentum/trend | Named exchange calendar, month anchors, complete sessions, split-only versus total-return action basis, original-price/action identities. | No interpolation, previous-session fill for missing expected close, unsupported-action skipping, or cross-basis splice. |
| Volatility/downside | 64 ordered closes, 63 exact returns, named benchmark and paired sessions. | No shrinking windows or blind inner joins; zero-variance complete pair is UNSUPPORTED, absent coverage is MISSING. |
| Relative context | PIT classification/membership/version/effective window/publication and per-peer evidence. | No current membership projection, score, rank, or winner inference. |
| Portfolio context | Exact account observation/cutoff, `PortfolioObservation` coverage, supported positions/marks/costs, PIT group membership, exact fills/currency. | Missing coverage is not zero; no tax-lot, projected turnover, or optimizer inference. |

## 3. PM2C synthetic/adversarial fixture plan

The following are planned tests for PM2C, not tests run by this documentation
checkpoint:

1. Same semantic fact with different receipt/recalculation annotations retains
   its fact ID; a changed value/version changes identity. Paths and serialized
   bytes do not affect IDs.
2. A source fact available after cutoff is `NOT_YET_AVAILABLE`; missing,
   conflicted, stale, invalid, unsupported, and genuine zero remain distinct.
3. A derived feature with one later input cannot claim earlier availability;
   cycles, duplicate edges, version swaps, mismatched units/currency, and
   nonfinite values fail closed.
4. Operational mode rejects a later receipt even when the source period is old;
   historical mode accepts only a verifiable immutable version-as-of witness and
   retains the distinction from operational receipt.
5. TTM rejects a missing/stale quarter; cumulative quarterization binds both
   component IDs; TTM EPS uses four discrete EPS values, not cumulative EPS
   subtraction.
6. P/E with zero/negative EPS becomes `UNSUPPORTED`; signed earnings yield and
   signed FCF/net debt remain valid where their formulas allow them.
7. Consensus revisions use the fixed 21-session prior anchor and exact target;
   a late or rolled consensus is not admitted.
8. Price windows reject a missing expected anchor, incomplete sessions,
   unsupported actions, and split/total-return cross-splicing; they do not carry
   a previous close. Split-only and total-return chains use their distinct
   versioned formulas.
9. Volatility/downside/drawdown/tracking error require all 64 closes, exact
   paired dates, and the sample conventions; no inner-join shrink is accepted.
   A complete zero-variance Pearson leg is `UNSUPPORTED`, while absent dates are
   `MISSING`.
10. Relative context rejects current membership projected backward and preserves
    peer-level unavailable states without producing a rank.
11. Portfolio context distinguishes missing cash/equity/price/cost from zero,
    requires account/coverage identity, and rejects unsupported tax-lot claims,
    duplicate/incomplete fills, cash-flow contamination, and cross-currency P&L.
12. Snapshot construction preserves every slot status/reason, ordered universe,
    membership, catalog version, cutoff/mode, and exact portfolio observation;
    mutation or newer-fact/older-timestamp mixing fails closed.
13. An adapter to PM1 can reference a snapshot only through a later reviewed
    seam; no automatic conversion to `MarketSignal`, score, recommendation,
    expected return, target, or order is allowed.

## 4. Explicit exclusion checklist

The PM2B candidate must be rejected as out of scope if it introduces any of the
following:

- Python source, tests, checkpoint registration, workflow, dependencies,
  lockfiles, production configuration, or runtime provider code;
- real market/fundamental/news/provider/AI/broker/account reads, credentials,
  OAuth, or sealed 2024+ access;
- a factor engine, feed, data acquisition, live-data qualification, or
  production computation;
- BUY/SELL thresholds, composite scores, rankings, relative winners, model
  prompts, expected-return forecasts, covariance/risk estimation, optimizer
  objectives, target weights, allocation policy, or execution behavior;
- a second research provenance authority, ledger, candidate lifecycle, or
  artifact authority;
- numeric imputation for missing/stale/unsupported/not-yet-available/conflicted
  evidence, hidden fallback, carry, interpolation, shrinking windows, or
  cross-basis splicing;
- PyPortfolioOpt or Qlib as a project dependency or authoritative evidence
  source.

## 5. Verification and next milestone

The owning design is [Architecture 152-PM2B — Research Evidence and Signal
Catalog](../architecture/152-pm2b-research-evidence-and-signal-catalog.md).

This record is intended for focused documentation checks only: Markdown/static
checks required by the repository, `git diff --check`, and the repository's
docs-only admission path. No pytest, broad certification, local FULL, provider,
or real-data operation belongs to PM2B.

The checked candidate scope is four Markdown paths only:

1. `docs/architecture/152-pm2b-research-evidence-and-signal-catalog.md` owns
   the frozen architecture, formulas, provenance, timing, catalog, and
   boundaries.
2. `docs/validation/arch152-pm2b-research-evidence-and-signal-catalog.md` owns
   this design checklist, family coverage, synthetic fixture plan, and scope
   exclusions.
3. `docs/PROJECT_STATUS.md` updates only the bounded current milestone and
   links these PM2B records while preserving historical PM1/PM2A and Arch151
   sections.
4. `docs/AI_TRADING_BOT_HANDOFF.md` updates only the bounded handoff,
   continuation identities/bounds, and links these PM2B records while
   preserving historical sections.

No other repository path is part of the PM2B candidate. The candidate must
remain docs-only and the mapped CI route must keep active tests, FULL, and
certification jobs skipped.

The next milestone is PM2C, synthetic typed evidence/catalog/snapshot
implementation. PM2C must first add focused tests for the planned fixtures and
then implement only the frozen contracts. Its planned synthetic fixtures must
also cover: (a) an after-cutoff source publication or operational receipt/
materialization, preserving the typed reason rather than restating it as a
period timestamp; (b) the golden 12-minus-1 anchor
`(T[-1m] / T[-12m]) - 1`, explicitly proving it does not use the current close
or a difference of returns; and (c) true versus zero currency/quantity/price
states, proving a genuine zero is retained while absent or invalid values stay
typed unavailable. These are test-plan cases only in PM2B, not executed here.
Real data-provider qualification,
signal-policy calibration, AI-provider qualification, portfolio optimization
policy, and execution authority remain later separately reviewed milestones.
