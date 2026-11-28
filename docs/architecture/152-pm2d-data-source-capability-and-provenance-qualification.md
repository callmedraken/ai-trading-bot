# Architecture 152-PM2D-A — Data-Source Capability and Provenance Qualification

**Status:** design and public-documentation review only. PM2D-A identifies
candidate source roles for the frozen [PM2B evidence catalog](152-pm2b-research-evidence-and-signal-catalog.md)
and [PM2C synthetic contracts](152-pm2c-synthetic-research-evidence-contracts.md).
It adds no adapter, provider dependency, configuration, source fact, or
production computation. It authorizes no provider call, login, credential,
subscription, bulk download, account read, AI call, or broker effect.

## 1. Purpose and authority

PM2D-A asks whether a source can establish the exact value, subject, economic
period, version, first defensible availability, revision lineage, units/basis,
coverage, and immutable provenance required by PM2C. A historical-period
endpoint, current value carrying an old period end, marketing description, or
content digest alone does not establish PIT availability.

The authority chain remains:

```text
provider observation (later, separately authorized)
  -> exact version and provenance witness
  -> PM2C typed source fact with availability and observation kept distinct
  -> deterministic PM2B feature and snapshot
  -> later policy outside PM2D
```

PM2D-A changes none of PM2C's identity, cutoff, witness, status, basis, or
authority rules. PM1 remains disarmed and preview-only; PM2A's real read-only
qualification remains separately gated; Arch149 sealed evidence remains
outside scope.

## 2. Qualification vocabulary

These labels describe what current public evidence establishes about a scoped
source claim. They are not PM2C `AvailabilityStatus` values and never mean
that a provider or production path has passed qualification as a whole.

| Label | Meaning |
| --- | --- |
| `DOC_SUPPORTED` | Current official documentation establishes this narrow capability or contract. It does not establish that an adapter, sample, complete history, or PM2C mapping has been accepted. |
| `SCHEMA_OBSERVATION_REQUIRED` | Documentation makes the capability plausible, but exact field meaning, record shape, version retention, or PIT behavior needs a later bounded schema/sample observation. |
| `PIT_UNQUALIFIED` | Data are exposed, but current evidence does not establish look-ahead-safe historical availability and version semantics for the proposed use. |
| `NOT_SUPPORTED` | The reviewed source contract does not provide the evidence needed for this family or claim. |
| `OUT_OF_SCOPE` | The capability belongs to another owner or is outside PM2B/PM2C V1. |

The label applies to the claim in its row, not every endpoint from that provider.
Official provider documentation outranks client-library behavior; public
repositories corroborate integration patterns only.

## 3. Frozen timing, version, and mapping rules

1. `period`/`effective_at`, source-channel `available_at`, local
   `observed_at`, and derived `calculated_at` remain separate. Period end,
   fiscal date, provider update time, and a signature change are not
   publication time by themselves.
2. Admit a historical fact only when the exact version is tied to a defensible
   availability witness in its declared source channel at or before the
   cutoff. Keep later observation time and witness identity. A digest proves
   byte identity, not when those bytes were available.
3. For a date-only source, the candidate conservative bound is the start of
   the next day in a proven source-local calendar, converted to UTC, only when
   the exact value/version is tied to that date and documentation or a source
   witness establishes availability by the end of that date. Otherwise
   `available_at` is not established. For SEC facts this means public filing
   availability; a commercial feed may instead use its declared channel. If
   source-channel delivery is later than filing or acceptance date, use the
   later defensible boundary. A typical processing interval is not a guarantee.
4. A later filing/version may not be backdated to an earlier 8-K. An earlier
   8-K is usable only if its accession/exhibit contains the same issuer,
   concept, context, dimensions, unit, currency, scale, value, and basis, and
   has its own public-availability witness. Otherwise use the later normalized
   version at its later boundary or leave it unavailable.
5. For compatible same-FY flow values, Q1 is direct; Q2/Q3 may be derived only
   as current YTD minus preceding same-FY YTD; Q4 may be annual minus same-FY
   Q3 YTD. Bind both exact component facts/revisions. TTM is four consecutive
   qualified discrete quarters. TTM EPS sums four discrete diluted EPS facts
   normalized to one admissible share/split basis; never subtract cumulative
   EPS or accept a current TTM field as substitute.
6. Corporate-action corrections, original/amendment filings, and consensus
   revisions are append-only versions. Do not overwrite a prior observation or
   infer completeness from an empty result.
7. Analyst revisions require the same provider, metric, target, fixed forecast
   interval, units, and aggregation/contributor policy at `T` and exactly
   `T-21` completed sessions on the named calendar. No calendar-day proxy,
   horizon roll, or later correction is eligible. No reviewed source currently
   establishes this full contract.
8. No fixed NTM consensus interval is qualified. Do not synthesize NTM from
   FY-next, calendar windows, or a vendor's latest forward-year ratio.
9. Current industry/sector metadata and current constituents cannot be
   projected backward. Membership needs effective windows and a public or
   otherwise reviewed publication witness.
10. Portfolio, broker, fill, and order facts remain owned by PM2A/runtime
    surfaces. Market-data vendors cannot establish account state; an order is
    not a fill and PM2D cannot infer fill completeness or order-to-fill links.

## 4. Evidence-family decision matrix

| PM2B/PM2C family | Candidate source and scoped status | PM2C mapping and material gap |
| --- | --- | --- |
| Price facts | Existing Alpaca historical route first; `SCHEMA_OBSERVATION_REQUIRED`. Sharadar SEP is an optional named-gap reference only. Tiingo is not a default fallback. | `raw.price.close.unadjusted` requires the PM2B regular-session unadjusted close. Alpaca daily bars are trade-condition aggregates; prove which observation matches the defined regular-session close. PM2B does not require an exchange official-auction close unless later policy explicitly chooses it. Also prove session boundary, source timestamp, correction/version behavior, subject mapping, completeness and missing semantics. |
| Corporate actions | Alpaca Corporate Actions REST + the separate Market Data SSE candidate; Sharadar ACTIONS reference; `SCHEMA_OBSERVATION_REQUIRED`. | `raw.price.action.split` and `raw.price.action.total_return`; prove effective/declaration/publication times, deletion/correction retention, replay continuity, entitlement and completeness. SSE emission time is not first-public time. |
| Security identity/ticker history and shares outstanding | Sharadar TICKERS + dated ACTIONS candidate; SEC CIK is issuer identity only; `SCHEMA_OBSERVATION_REQUIRED` for exact security mapping. SEC filing context is a per-fact candidate for eligible shares outstanding; no source is qualified for the exact share class/count/effective window. | `raw.security.issuer_share_class` and `raw.security.shares_outstanding`; prove persistent share-class identity, aliases, delistings, exact eligible share count and effective windows. TICKERS historical sector/industry metadata is `PIT_UNQUALIFIED`; no historical peer owner is qualified. |
| Fiscal statement facts | Sharadar SF1 As Reported ARQ/ARY normalized candidate; SEC accession and original filing bytes are raw per-fact witnesses. `SCHEMA_OBSERVATION_REQUIRED`. | `raw.fiscal.*`; exact field grain, XBRL context, dimensions, units, sign, YTD/Q4 construction and revision availability need a bounded sample. No guessed aliases. |
| Filing/revision lineage | SEC EDGAR accession, filing index and original filing are the primary official provenance reference; `DOC_SUPPORTED` for filing record/accession, with per-version public-availability proof still required. | Keep acceptance, filing date, period and public dissemination distinct. Company Facts/Frames alone are not immutable as-filed history. Amendments are separate versions. |
| Analyst consensus | No V1 source qualified; Intrinio Zacks and FMP current estimate schemas are `PIT_UNQUALIFIED`. | `raw.consensus.{metric}` requires arbitrary-cutoff vintages, fixed interval/target, metric, units, contributor policy, counts, publication time and immutable version. No qualified fixed NTM. |
| Analyst revisions | No V1 source qualified; Intrinio Zacks prior-period summaries and FMP estimates are `PIT_UNQUALIFIED`. | `growth.estimate_revision` requires same provider/metric/target/horizon at T and T-21 completed sessions, publication/revision time and immutable versions. No calendar-day proxy or later correction. |
| Peer/classification membership | Sharadar TICKERS current sector/industry fields are `PIT_UNQUALIFIED`; no qualified historical peer/sector owner identified. | `raw.classification.membership` requires role, member, effective/publication window, version and complete member evidence. Current metadata cannot be projected backward. |
| Benchmark/index membership | Sharadar SP500 effective additions/removals plus public S&P DJI announcement witnesses are a candidate; `SCHEMA_OBSERVATION_REQUIRED`. Benchmark return is separately a price-fact family. | Prove baseline, effective date, public publication time and archive completeness; effective time is not availability. Do not infer benchmark return from constituent membership. |
| Portfolio observations | PM2A/approved runtime brokerage observer only; `OUT_OF_SCOPE` for external vendors and PM2D-A. | `raw.portfolio.observation` needs exact account fingerprint, coverage, observation time and snapshot identity. No read is authorized here. |
| Fill/order observations | PM2A/runtime execution and ledger evidence only; `OUT_OF_SCOPE` for external vendors and PM2D-A. | `raw.portfolio.fill` needs execution identity, account/currency, deduplication and completeness witness. No order-to-fill inference/read is authorized. |

The detailed provider claim cards, field matrix, official sources, license
scope, rate/bandwidth evidence, repository patterns and next proofs are in the
[PM2D-A validation record](../validation/arch152-pm2d-data-source-capability-and-provenance-qualification.md).

## 5. Minimal candidate composition

1. **SEC EDGAR — raw filing/provenance reference.** Use exact accession and
   filing bytes to support only facts present in the filing. SEC does not
   supply prices, consensus, corporate-action completeness, or peer membership.
   Company Facts/Frames are discovery/corroboration, not stand-alone as-filed
   reconstruction.
2. **Existing Alpaca route — first price candidate; Alpaca Corporate Actions
   REST plus Market Data SSE — first action candidate.** This reuses the
   existing path and avoids adding a price vendor by default. Alpaca daily SIP
   bars aggregate eligible trades by New York calendar date: documentation
   excludes condition M, includes condition 6, and says condition 9 corrected
   consolidated close can change daily OHLC; T/U do not set daily open/close.
   These distinctions do not define PM2B as an exchange official-auction close.
   Prove which observation matches PM2B's regular-session close, including
   early closes, exact historical correction versions, entitlement and
   selected-symbol coverage. Market Data SSE insert/update/delete and replay
   are useful observation candidates; its `at` is channel emission time, not
   first availability. Sharadar SEP is an optional independent reference for
   an explicitly named gap, never an automatic fallback or basis splice.
3. **Sharadar SF1 As Reported — conditional normalized fundamentals
   candidate.** ARQ/ARY are PIT-oriented; ART can reflect restated component
   quarters and is descriptive parity only. MRQ/MRY/MRT are Most Recent
   restated dimensions and are rejected for historical PM2C facts. Exact
   selected fields and quarterization remain unqualified until sampled.
4. **Sharadar identity and membership references.** TICKERS+ACTIONS are
   candidates for security identity and dated ticker history. SP500 effective
   changes plus S&P DJI public announcements are a separate benchmark-
   membership candidate. These do not qualify historical peer classification,
   shares outstanding, or a benchmark-return price series.
5. **Intrinio — optional fundamentals gap challenger; no estimate authority in
   V1.** Filing/signature fields may help a future comparison, but update or
   signature changes do not prove retrieval of a prior version. Zacks EPS/Sales
   aggregates do not establish arbitrary-cutoff vintages. A distinct dated-
   vintage contract and commercial license would be required before an
   estimate observation.
6. **No qualified analyst-estimate, fixed-NTM, or historical peer source.**
   FMP is rejected for historical PIT estimates because the vendor says its
   internal timestamps are not queryable by date on an API plan. Tiingo is an
   optional cost challenger only for a documented price/action coverage or
   rights gap; it is not a primary or automatic fallback because its EOD
   timestamps and correction history do not establish immutable vintages.

The PM2B families still unavailable or unqualified are fixed-interval NTM
consensus, exact 21-session estimate revisions, historical peer/sector
membership, a proven PM2B regular-session close mapping and immutable price
corrections, complete PIT corporate-action history, and fully qualified SF1
field/YTD/Q4 mappings. An unavailable PM2B slot remains typed unavailable; a
gap does not authorize substitution.

## 6. Later bounded observation boundary

PM2D-B may observe only exact schema/sample claims named by an accepted
PM2D-A review, using separately reviewed source/effect bounds. For an initial
SEC/Sharadar mapping candidate, the minimum proof is one issuer's original
10-Q/10-K, a separately accessioned amendment, selected annual and quarterly
facts with narrow YTD/discrete/Q4 cases, one custom-dimension context, and an
early 8-K fact only where exact same-value lineage is needed. Compare exact
tags/contexts/units/scale and all candidate versions to the official filing;
include null, zero and conflict cases. A single sample cannot qualify all
fields, issuer coverage, first-public timing, or broad historical completeness.

For estimates, first prove a licensed dated-vintage contract with retrievable
old versions. Only then consider same-issuer/metric/fixed-target snapshots
including T-21 completed sessions and a later correction, retaining the
original version and proving the actual fixed NTM interval if one exists.
FMP is not a PM2D-B probe candidate. No bulk acquisition belongs to PM2D-B.

## 7. Explicit non-goals and next milestone

PM2D-A creates no HTTP/API call, key, credential, login, trial, paid plan,
subscription, market-data or filing acquisition, Robinhood/Alpaca/Intrinio/
Nasdaq/Tiingo/FMP read, AI-provider request, broker effect, order, or access to
Arch149 sealed data. No source adapter or production field mapping is accepted.

The next milestone is **PM2D-B — bounded schema/sample qualification**. It may
proceed only after independent acceptance/integration of PM2D-A and only for
the explicit proof claims above. Each observation must be separately reviewed,
bound to exact source/schema/attempt identity, and fail closed on missing
version retention, timing, completeness, or license evidence. A first adapter
is a later milestone after those observations are accepted.
