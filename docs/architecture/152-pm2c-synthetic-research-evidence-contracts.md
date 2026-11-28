# Architecture 152-PM2C — Synthetic Research Evidence Contracts

**Status:** implementation draft; source publication, mapped CI, exact-source
acceptance, and integration identities are pending. PM2C is the bounded
synthetic implementation of the frozen [Architecture 152-PM2B research
evidence and catalog](152-pm2b-research-evidence-and-signal-catalog.md).
It does not claim that any provider, account, or real market data has been
read.

## 1. Purpose and boundary

PM2C makes the PM2B causal chain representable in immutable, typed in-memory
objects. Source observation is ingress only; it is not a later policy value:

```text
source observation
  -> point-in-time source fact
  -> validated/derived feature
  -> coherent research snapshot
  -> later policy (outside PM2C)
```

The implementation proves that unavailable or future information cannot become
a fabricated numeric value, that derived evidence cannot hide an input, and
that a snapshot cannot grant recommendation, allocation, or dispatch authority.
It remains synthetic-only. PM2A's real read-only qualification is **NOT YET
AUTHORIZED**, PM1 remains disarmed and preview-only, and Arch149 remains sealed.

PM2C does not decide whether a signal is useful, profitable, attractive, or
actionable.

| Evidence layer | PM2C contract | Boundary |
| --- | --- | --- |
| Point-in-time source fact | A typed source-channel value with exact catalog entry, subject, version, basis, timestamps, and provenance. | No missing-value inference, revision substitution, or period-end/publication conflation. |
| Validated/derived feature | A deterministic output over the exact ordered transitive evidence DAG. | No cycles, hidden late input, fallback, interpolation, cross-basis splice, or ambient-context arithmetic. |
| Research snapshot | An immutable as-of selection of ordered universe/membership and admitted or unavailable slots, with exact portfolio context when requested. | Binds catalog ID/version, mode, inclusive cutoff, membership, statuses/reasons, closure IDs, and qualifying witnesses. |
| Interpretation/policy | Later scoring, ranking, forecasting, AI interpretation, optimization, allocation, or execution. | Outside PM2C; no recommendation or effect authority is exposed. |

## 2. Three coordinated in-memory modules

The implementation is intentionally contained in the existing Portfolio
Manager namespace:

### 2.1 `research_catalog.py`

The catalog declares evidence without evaluating executable formula text.

- `ResearchCatalog` is an immutable versioned registry with a deterministic
  `catalog_id`, exact key/version lookup, and an immutable lookup index.
- `CatalogEntry` binds `catalog_version`, key, entry version, `entry_id`,
  family, `EntryKind.RAW` or `EntryKind.DERIVED`, a typed `FormulaRef` for
  derived entries, ordered `InputSpec` roles, `ValueSpec`, `ScopeSpec`,
  `PeriodSpec`, `WindowSpec`, `EvidenceBasis`, and availability/domain rule
  identifiers.
- `InputSpec` records exact dependency key/version, role and optional entry ID,
  value/basis requirements, repeat policy, and session/fiscal/target anchor
  information. Catalog construction proves key/version resolution and, when
  supplied, the actual registered entry ID, value specification, and basis.
- `ValueSpec` admits only finite `Decimal`, integer/count (with `bool`
  rejected), boolean, identifier, ordered identifier-vector, and ordered
  Decimal-vector values. Units, three-letter currencies, and canonical rule
  tokens are validated explicitly.
- `EvidenceBasis` separates named calendar, adjustment basis
  (`UNADJUSTED`, `SPLIT_ONLY`, `TOTAL_RETURN`), and optional data/reporting
  basis. Scope, period, and complete-window requirements remain declarations;
  no provider calendar or acquisition calculation occurs here.

The shared `research_identity` helper uses framed, versioned UUID5 material.
It does not use `repr`, filesystem paths, object identity, serialized bytes,
fetch order, or ambient Decimal context.

The only arithmetic helpers are context-independent Decimal operations:
`ratio` returns no value for a nonpositive denominator, preserves a signed
numerator for signed yield-like outputs, and rounds an exact quotient half-even
to twelve fractional places;
`simple_return` computes `new / old - 1`; and
`momentum_12m_minus_1m(old_12m, new_1m)` computes exactly
`T[-1m] / T[-12m] - 1` from its two named anchors. There is no generic formula
engine and no current-close or return-difference substitution.

### 2.2 `research_evidence.py`

This module owns immutable typed source and derived evidence.

- `AvailabilityStatus` preserves exactly `AVAILABLE`, `MISSING`, `STALE`,
  `UNSUPPORTED`, `NOT_YET_AVAILABLE`, `CONFLICTED`, and `INVALID`.
- `AvailabilityReason` is a closed typed reason vocabulary. `EvidenceOutcome`
  requires a value only for `AVAILABLE`; every unavailable state carries typed
  reason information and no numeric substitute. Genuine zero remains a value.
- `EvidenceSubject` binds a security or typed portfolio/account scope, and
  `EvidenceTimeframe` distinguishes instant, period, session, and window time
  from publication availability.
- `SourceFact` binds a RAW `CatalogEntry`, subject, source identity/version,
  typed outcome, timeframe, availability/observation/effective timestamps,
  revision lineage, safe source-record/content identifiers, and separate audit
  annotations. Its semantic identity includes the admitted semantic material,
  not receipt-path or incidental audit annotations.
- `VersionAsOfWitness` proves an exact source version and publication witness
  for historical reconstruction. `SourceFact.validate_cutoff` rejects a
  source publication after the cutoff; operational mode also requires receipt
  by the cutoff, while historical reconstruction requires the exact immutable
  witness and does not rewrite receipt time.
- `DerivedFeature` binds a DERIVED catalog entry, ordered role-labelled
  `EvidenceDependency` values, output outcome, calculation/availability time,
  and optional timeframe. `EvidenceGraph` proves exact catalog entry identity,
  dependency role/order, value/basis/currency compatibility, subject match,
  anchor match, availability ordering, unavailable propagation, and acyclicity.
  Its closure methods expose transitive source evidence.

No provider, filesystem, network, database, AI, or broker lookup occurs during
these validations.

### 2.3 `research_snapshot.py`

`ResearchSnapshot` is the immutable as-of boundary. `SnapshotSlotRequest`
selects an exact catalog entry and subject with either a graph evidence ID or
an explicitly unavailable `EvidenceOutcome`; `MembershipBinding` retains
ordered point-in-time membership evidence and its effective window; and
`ResearchSnapshot.admit` validates an `EvidenceGraph`, decision cutoff,
canonical `SnapshotMode`, universe, optional exact `PortfolioObservation`, and
historical version witnesses.

The resulting slots retain entry identity/version, evidence identity or typed
unavailability, outcome, and source-fact closure. The value-only portfolio
reference retains exact observation/account/coverage distinctions without
inventing tax lots, fills, entry dates, or historical marks. Snapshot identity
includes the immutable `ResearchCatalog.catalog_id` and version, semantic
cutoff, mode, named membership basis/calendar, universe, slots, closure IDs,
selected historical `VersionAsOfWitness.witness_id` values, operational
receipt/materialization IDs, and portfolio context; historical recalculation
audit time is nonsemantic. The graph and slot requests are admission inputs,
not public snapshot state. A late publication/receipt/materialization slot
retains its typed reason but hides future evidence identity and value.

## 3. Point-in-time and availability firewall

Economic period/effective time, source `available_at`, `observed_at`, derived
`calculated_at`, and snapshot `decision_cutoff` remain distinct. Period end is
not publication availability. An operational snapshot cannot admit evidence
received or materialized after its cutoff. Historical reconstruction can admit
later acquisition only when `VersionAsOfWitness` proves that the exact source
version was visible by the historical cutoff; it preserves the later audit
fact and never relabels it as an operational receipt.
Snapshot admission recursively checks every ancestor, so a late raw leaf cannot
be laundered by a derived output.

Derived availability is no earlier than every required input. Missing,
stale, unsupported, future, conflicted, or invalid evidence remains typed and
cannot be replaced by zero, carry, interpolation, a shrinking window, a newer
revision, or an implicit basis/currency conversion.

## 4. Portfolio, peer, and policy boundaries

PM2C can retain synthetic references to an exact portfolio observation and
point-in-time membership. A real Robinhood read remains outside the milestone.
Cash, quantity, price, cost, coverage, account, and observation identity keep
genuine zero distinct from missing or unavailable state. The synthetic adapter
allowlist is explicit (`portfolio.cash`, `portfolio.broker_equity`,
`portfolio.quantity`, `portfolio.mark`, and `portfolio.average_cost`); each
admitted fact binds both the exact observation snapshot and account fingerprint,
relevant coverage, and—when it is a mark—the original position quote timestamp
at or before the cutoff. Peer membership is bound as evidence and is not
projected backward from current classification; an unavailable peer remains
represented rather than silently pruned.

There is no automatic conversion from `ResearchSnapshot` to `MarketSignal`,
recommendation, expected return, covariance, optimizer request, target
allocation, plan, order, or dispatch authority. PM1's existing preview-only,
`dispatch_authorized=False` boundary is unchanged. PM2C adds no score, rank,
threshold, factor weight, forecast, risk model, optimizer objective, AI
provider, or execution path.

## 5. Explicit non-goals and next milestone

PM2C does not implement provider mappings, public/commercial acquisition,
point-in-time storage, SEC/fundamental/consensus/news/macro feeds, corporate
action reconstruction, peer-provider selection, freshness policy, conflict
arbitration, scoring, calibration, allocation, AI qualification, or live
readiness. Qlib and PyPortfolioOpt remain documented architectural references
only and are not dependencies or evidence authorities.

The PM2C synthetic validation plan also keeps three adversarial cases explicit
for focused tests and later PM2D qualification: an after-cutoff source
revision/receipt must remain typed unavailable; the 12-minus-1-month golden
momentum anchor must be `(T[-1m] / T[-12m]) - 1` and must not use the current
close or a difference of returns; and true zero currency/quantity must remain
distinct from missing currency/quantity. These are test-contract cases only,
not production feed or computation claims.

After PM2C source, focused verification, mapped certification, exact review,
and integration are accepted, the next separately designed milestone is
**PM2D — data-source capability and provenance qualification**. PM2D must
determine which public or commercial sources can supply the PM2B catalog with
trustworthy point-in-time versions, timing, basis, coverage, and evidence
identities. PM2D does not receive provider authorization from this document.
