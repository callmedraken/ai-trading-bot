# Architecture 152-PM2D-A — Data-Source Capability and Provenance Qualification

**Validation type:** public-documentation and public-repository research only.
This record maps current source claims to the frozen [PM2B catalog](../architecture/152-pm2b-research-evidence-and-signal-catalog.md)
and [PM2C synthetic contract](../architecture/152-pm2c-synthetic-research-evidence-contracts.md).
It reports no real provider schema observation or API result. No credentials,
subscription, provider call, market data, account, AI, broker, or sealed-data
effect occurred.

## 1. Decision summary

The minimal candidate composition is SEC EDGAR as a per-fact raw filing and
provenance witness; the existing Alpaca data path as the first price candidate
and Alpaca Corporate Actions REST plus **Market Data** SSE as the first action
candidate; and Sharadar SF1 As Reported as a conditional normalized
fundamentals candidate. Sharadar SEP and Tiingo are optional named-gap price
references only. Sharadar ACTIONS and TICKERS can aid corporate-action and
identity cross-checks. Sharadar SP500 is a separate effective-membership
candidate, not a general peer-classification source.

No source is yet accepted for implementation. Exact Alpaca regular-session
close/correction semantics, action replay completeness, Sharadar field/grain
mapping and point-in-time availability need bounded later observation. There is
no qualified fixed NTM consensus, exact 21-session analyst revision history,
or historical sector/peer membership. Intrinio's reviewed Zacks schemas and
FMP's estimate API do not prove historical as-of vintages. FMP explicitly says
its internally retained estimate timestamps are not queryable by date on any
API plan.

Qualification vocabulary is owned by
[Architecture 152-PM2D-A](../architecture/152-pm2d-data-source-capability-and-provenance-qualification.md):
`DOC_SUPPORTED`, `SCHEMA_OBSERVATION_REQUIRED`, `PIT_UNQUALIFIED`,
`NOT_SUPPORTED`, and `OUT_OF_SCOPE`. These are scoped evidence judgments,
not PM2C runtime availability states and not blanket vendor passes/failures.

## 2. PM2B evidence-family crosswalk

| Evidence family | Source / dataset | Scoped status | Current decision and missing claim |
| --- | --- | --- | --- |
| Price facts | Alpaca historical stock bars; optional Sharadar SEP, Tiingo EOD | Alpaca: `SCHEMA_OBSERVATION_REQUIRED`; SEP/Tiingo: `PIT_UNQUALIFIED` for immutable historical versions | Existing Alpaca route stays first. Its daily bar is an eligible-trade aggregation; prove which observation maps to PM2B's regular-session close. PM2B does not require an exchange official-auction close unless a later policy selects one. Need exact session/early-close boundary, correction/version, identity, coverage and missing semantics. No automatic fallback. |
| Corporate actions | Alpaca Corporate Actions REST + Market Data SSE; Sharadar ACTIONS; Tiingo split/dividend endpoints; FMP dividend/split endpoints | `SCHEMA_OBSERVATION_REQUIRED` for event shapes; PIT version completeness unqualified | Alpaca Market Data SSE exposes insert/update/delete, event ID, emission time and replay bounds, not guaranteed first-public time or complete retained history. REST and other providers expose current records without immutable old-version proof. |
| Security identity / ticker history | Sharadar TICKERS + ACTIONS; SEC CIK; Tiingo permaTicker; FMP search/symbol changes | Sharadar: `SCHEMA_OBSERVATION_REQUIRED`; CIK issuer-only; other alias histories `PIT_UNQUALIFIED` | Need exact issuer/security/share-class mapping, alias effective windows, delisted/reused identifiers and event lineage. Current sector/industry is not historical membership. |
| Fiscal statements | Sharadar SF1 ARQ/ARY; SEC accession filing/XBRL; optional Intrinio fundamentals; FMP as-reported income statements | Sharadar/Intrinio exact field use: `SCHEMA_OBSERVATION_REQUIRED`; SEC filing witness: `DOC_SUPPORTED`; FMP historical revisions `PIT_UNQUALIFIED` | Validate exact concept, context, dimensions, unit, currency, sign, grain, revision, YTD/Q4 components and earliest defensible public availability. No statement field is interchangeable by name similarity. |
| Filing / revision lineage | SEC submissions, accession archive/index, SGML/iXBRL/XBRL; Sharadar datekey/lastupdated; Intrinio signatures; FMP filingDate/acceptedDate | SEC record/accession `DOC_SUPPORTED`; provider normalized-version retrieval remains `SCHEMA_OBSERVATION_REQUIRED` or `PIT_UNQUALIFIED` | Filing/acceptance date and content digest do not alone prove first public visibility. SEC amendments are separate accessions; Company Facts/Frames do not replace exact as-filed bytes. |
| Analyst consensus | Intrinio Zacks EPS/Sales; FMP Financial Estimates | Both `PIT_UNQUALIFIED` | Target-period aggregates are not arbitrary-cutoff vintages. No fixed NTM interval and full target/forecast-window definition are qualified. |
| Analyst revisions | Intrinio prior-estimate summaries; FMP estimate API | `PIT_UNQUALIFIED` | Neither current public schema establishes exact consensus at T and T-21 completed sessions with old versions retained. FMP explicitly says its internal timestamps are not queryable by date. |
| Peer / sector classification | Current Sharadar TICKERS, other reviewed provider surfaces | TICKERS historical labels `PIT_UNQUALIFIED`; no qualified V1 owner | No effective and source-availability history proves historical sector or industry. Do not project today's classification backward. |
| Benchmark membership | Sharadar SP500; public S&P DJI announcements; FMP historical S&P 500 | `SCHEMA_OBSERVATION_REQUIRED` for Sharadar effective changes; FMP not selected | Effective dates and changed-member records require a baseline, publication witness and archive completeness. Benchmark membership is separate from a benchmark-return price series and from general peer membership. |
| Portfolio observation | PM2A and approved runtime brokerage surfaces | `OUT_OF_SCOPE` for market-data/fundamental vendors and PM2D-A | Preserve PM2C exact account/snapshot/coverage identity. No account read is part of this milestone. |
| Fill / order observation | PM2A/runtime ledger and execution surfaces | `OUT_OF_SCOPE` for market-data/fundamental vendors and PM2D-A | Use exact execution/fill evidence and completeness witness; never infer fills from orders. No order read is part of this milestone. |

## 3. Detailed provider and field matrix

Each provider card carries the requested fields: dataset/API; coverage/history
and active/delisted scope; subject identifier and economic period; availability,
observation/update and revision witness; units/currency and adjustment basis;
missing-value behavior; pagination/bulk and rate/bandwidth; licensing; PIT
hazard; PM2C mapping; qualification; and the smallest next proof. A provider
claim may qualify only the named field or behavior in that row.

### 3.1 SEC EDGAR — raw filing and provenance witness

| Dataset/API and official evidence | Coverage, subject and economic period | Availability, observation and version | Units, missing, pagination and limits | License, PM2C mapping, status and next proof |
| --- | --- | --- | --- | --- |
| [Submissions API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces); [EDGAR data access](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data); official [filing-data FAQ](https://www.sec.gov/files/about/webmaster-faq.htm), [filing-status guide](https://www.sec.gov/submit-filings/filer-support-resources/how-do-i-guides/determine-status-my-filing), [dissemination notice](https://www.sec.gov/info/edgar/ednews/dissemin.htm). Raw filing index, SGML, inline XBRL and filing documents use exact accession path. | Issuer identity is CIK; CIK is unique/not recycled but is not a share-class security key. EDGAR filing archive begins in 1994–95 (form-dependent); submissions includes recent filings plus archive manifests; ticker/exchange map is current and has no accuracy/scope guarantee. Filing form, report period and XBRL context must be read from the exact filing. No statement that every historical/active/delisted subject has complete PM2B coverage. | Accession, form, filing date, period and acceptance timestamp are distinct. SEC describes 1–3 minute processing as typical, not a guarantee; filings accepted after roughly 5:30 p.m. ET are generally disseminated next business day with exceptions. Public SEC website precedes separate paid PDS. Neither acceptance nor filing date alone proves the first public instant. Amendment `/A` has separate accession. PAC can change bytes under same accession/date; preserve corrected/deleted content or leave version unqualified. | XBRL value requires exact tag, context/instant or duration, dimensions, unit, currency and scale. Company Facts covers non-custom taxonomy facts at entity level; custom facts/dimensional contexts and complete as-filed history are not represented by Company Facts alone. Frames is an approximate last-filed calendar slice, not exact historical issuer fact. Missing tag/context is unknown, not zero. | API is free; declare User-Agent; maximum 10 requests/second total. Public filings may contain third-party content. No bulk pull in PM2D-A. PM2C: raw fiscal fact + accession/byte provenance. `DOC_SUPPORTED` for filing/accession records; per-version `available_at` still needs public-availability witness. A date-only filing date maps to next local midnight only if that exact version is proven public by source-date end; otherwise availability is unqualified/later. Next proof: narrow 10-Q/10-K, amendment, custom context and exact earlier 8-K fact with a public-availability witness. |

The [SEC privacy statement](https://www.sec.gov/about/privacy-information)
allows reuse of public filings subject to applicable third-party content. SEC
is not a price, consensus, corporate-action-completeness or peer-membership
source.

### 3.2 Sharadar / Nasdaq Data Link — SF1, SEP, ACTIONS, TICKERS, SP500

| Dataset/API and official evidence | Coverage, subject and economic period | Availability, observation and version | Units, missing, pagination and limits | License, PM2C mapping, status and next proof |
| --- | --- | --- | --- | --- |
| [SF1 docs](https://data.nasdaq.com/databases/SF1/documentation?anchor=see-also), [Sharadar fundamentals](https://sharadar.com/docs/fundamentals), [EVENTS](https://sharadar.com/docs/events), [NDL legal terms](https://assets.ctfassets.net/mx0rke14e5yt/1d9opC78Sc76FsxoFedmF9/003ce415c4b85f12b4e43dcc0e506043/Data_Link_Terms_and_Conditions_-_effective_11.1.26.pdf). Datasets: `SHARADAR/SF1` and `SHARADAR/EVENTS`; dimensions ARQ/ARY/ART/MRQ/MRY/MRT. | ARQ is domestic quarterly; ARY annual; ART is twelve-month measured quarterly. Vendor-published coverage and Nasdaq-table route figures differ (Sharadar describes nearly 18k and history from 1998; Nasdaq catalogue describes over 16k and history from Dec. 1997). Preserve the route-specific claim; prove sample/coverage rather than reconciling by assumption. Active/delisted coverage is advertised, but completeness for a selected symbol/cohort is not established by one row. `permaTicker` is a candidate security/share-class key; `reportperiod` is fiscal period end; `calendardate` is a normalized calendar bucket. | AR is PIT-oriented and excludes recasting older periods to latest filings; ART may reflect restatements to component quarters and is not the sum of four historical ARQ values. MRQ/MRY/MRT are most-recent/restated views and are rejected for historical PM2C facts. On AR, `datekey` is Form 10 filing date; MR uses report-period date (publisher table route exposes `date`). `lastupdated` is date-level change time, not an intraday publication clock or immutable version history. Same-day catch-up filings may omit earlier periods. EVENTS has dated Form 8 event codes, but not exact accession/version/fact lineage. Early Form 8-K values require exact same fact and public witness. | SF1 supplies normalized fields, not a universal exact PM2B basis. `capex` combines physical/intangible/acquisition/disposal categories and may impute zero; `debt` includes operating leases and may impute; `cashneq` may impute; `equity` parent vs common/total is unresolved; `depamor` includes accretion; `intexp` may be net of interest income and is unsuitable as gross operating interest. Narrow candidates `ncfo`, `revenue`, `cor`, `opinc`, `netinccmn`, `epsdil` still require exact sample mapping. No documented YTD dimension for safe Q2/Q3/Q4 reconstruction. NDL Table API supports projection/filters/cursor and 10,000-row limits; bulk export exists but is out of scope. Exact paid-plan rate/bandwidth not verified. | Direct Sharadar annual personal prices published: Fundamentals $199/$299/$399, Prices $99/$199/$299, Bundle $299/$399/$499 for 5/10/full plans. Direct individual license excludes organizational/commercial/pro use and redistribution, and requires deletion of retained data/reproducible extracts at termination; see [terms](https://sharadar.com/terms) and [plans](https://sharadar.com/subscribe). Nasdaq Data Link commercial terms/service order are distinct; legal terms indicate scoped internal use and retention, while exact rights/quote need login/contact. PM2C: raw fiscal facts, actions, security, shares and benchmark membership. ARQ/ARY candidate only: `SCHEMA_OBSERVATION_REQUIRED`; ART/MR rejected for PIT; SP500 effective changes need publication/completeness proof. Next proof: exact field/context/grain, datekey-to-accession witness, same-FY YTD/annual arithmetic, null/zero/conflict and cohort checks. |
| [SEP documentation](https://data.nasdaq.com/databases/SEP/documentation). Dataset `SHARADAR/SEP`; [ACTIONS](https://sharadar.com/docs/actions), [TICKERS](https://sharadar.com/docs/tickers), [SP500](https://sharadar.com/docs/sp500). | SEP advertises 21k active/delisted securities from Jan. 1998. `permaTicker` is the stable instrument key; date is trading day. ACTIONS contains action/date/value/ticker/contra but not declaration/revision fields. TICKERS carries current identifiers/sector; dated alias history is inferred only with ACTIONS plus identity proof. SP500 reports quarterly baseline and additions/deletions from 1998, but event-publication time is absent. | SEP documents 17:30 and 23:30 ET update cadence; `lastupdated` is mutable and not an immutable historical version. `closeunadj` is raw; OHLCV are split/stock-dividend adjusted; `closeadj` also applies cash/spinoff backward adjustment. No official exchange-close equivalence or exact first-public time proven. ACTIONS dates/effective values are not announcement/version history. S&P [methodology](https://www.spglobal.com/spdji/en/documents/methodologies/methodology-sp-equity-indices-policies-practices.pdf) and [news/announcements](https://www.spglobal.com/spdji/en/media-center/news-announcements/) are reference witnesses, with no guarantee of a complete archived publication timeline. | Raw/split/total-return values are different basis keys. Missing values, imputed zeros and corporate-action adjustment semantics need row-level observation; never coerce NaN/Inf to zero. Same Data Link projection/filter/cursor and 10k-row table cap; bulk export not authorized. Exact subscription throughput unknown. | Same licensing split as SF1; do not infer rights from endpoint availability. PM2C: optional named-gap price reference, action/security cross-check, benchmark membership. `PIT_UNQUALIFIED` for direct price facts due mutable endpoint and close/availability gaps; ACTIONS/TICKERS/SP500 `SCHEMA_OBSERVATION_REQUIRED` for named sample. Next proof: compare an exact action/identity/membership sample to official witnesses and prove route cohort completeness before use. |

For field selection, examples of the
[Nasdaq Data Link Python client](https://github.com/Nasdaq/data-link-python)
show projection/filter/pagination request patterns, not immutable evidence
custody. The public
[Sharadar ingestion example](https://github.com/alphaville76/sharadar_db_bundle/blob/master/sharadar/loaders/ingest_sharadar.py)
replaces NaN/Inf with zero, drops `lastupdated`, and assigns one timestamp to
dividend events; those patterns are explicitly rejected.

### 3.3 Alpaca — existing prices and candidate corporate actions

| Dataset/API and official evidence | Coverage, subject and economic period | Availability, observation and version | Units, missing, pagination and limits | License, PM2C mapping, status and next proof |
| --- | --- | --- | --- | --- |
| [Historical stock bars](https://docs.alpaca.markets/us/reference/stockbars), [market-data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq), [real-time stock pricing/corrections](https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data). Existing [Alpaca transport](../../src/trading_bot/market_data/alpaca_http.py) retains exact response bytes, SHA-256, length and safe request ID while excluding auth metadata. Existing daily snapshot uses raw SIP/USD and `asof=-`; its `provider_as_of` remains null. | Historical US stock/ETF bars advertised since 2016; complete delisted/inactive coverage is not claimed. Bar subject is a symbol resolved by `asof`; that controls symbol mapping and is not a historical data-version selector. Daily bars aggregate eligible trades by New York calendar date, not necessarily PM2B's regular-session close. | Daily close conditions: M market-center official close excluded; 6 closing trade included; 9 corrected consolidated close can change daily OHLC; T/U do not set daily open/close. These conditions do not impose an official-auction requirement; prove the daily observation's mapping to PM2B's regular-session close. Early-close/session boundary and exact correction-version retrieval remain unresolved. Live minute `updatedBars`, `corrections`, and `cancelErrors` can support prospective correction observation; they do not guarantee historical V2 bar vintages. REST corporate-action endpoints expose type/IDs, symbol/CUSIP/ISIN/date/ratio/cash and data-quality `complete/all`, but current state is not an old-version witness. | Explicit feed/currency/adjustment and `asof=-` are needed to avoid silent aliases; adjustments include raw, split, dividend, spin-off and all. Bar pagination uses a cross-symbol row cap and opaque `next_page_token`, which must be followed even after a short page. A missing scheduled close remains missing. PM2C units/currency are explicit; no default adjustment splice. | Basic published $0: IEX real time, SIP delayed 15 minutes, 200 requests/min; Plus published $99/month: all exchanges and 10,000/min (checked 2026-11-27). Entitlement/data rights require separate confirmation; standard account agreement restricts commercial exploitation/distribution absent written consent. PM2C: `raw.price.close.unadjusted`, split/total-return action records. `SCHEMA_OBSERVATION_REQUIRED`; next proof: predeclared normal/early close sample, known correction and replay/history behavior, complete pagination, explicit feed/adjustment and selected-symbol cohort. No plan change. |
| [Corporate Actions REST](https://docs.alpaca.markets/us/reference/corporateactions-1), separate [Market Data Corporate Actions SSE](https://docs.alpaca.markets/us/reference/subscribetocorporateactionseventssse); deprecated [Trading announcements](https://docs.alpaca.markets/us/reference/getcorporateannouncements) and account-scoped [Broker Activity SSE](https://docs.alpaca.markets/us/docs/activity-sse). | REST/SSE Market Data describe market-wide corporate action records; fields include action type, symbol and identifiers, dates, ratio/cash. Corporate announcements are a different channel with declared/ex/record/payable dates. Broker Activity is account-posting/fill/corporate-action scope, not a market-wide action feed. | Market Data SSE carries `action=insert/update/delete`, RFC3339 `at` channel-emission time, unique ordered `event_id` ULID and persistent `ca.id`; replay accepts inclusive `since`/`since_id`/`Last-Event-Id`, with bounded `until`/`until_id`. Redelivery is possible. An `at` timestamp is not action effective time or first source-channel availability. Retention, entitlement and contiguous replay completeness are not established. Broker Activity can backfill with earlier business `at` and does not expose non-fill order states; never treat it as market-wide. | Split ratio and cash distributions need exact action type, dates, currency/unit, cancellation/update lineage and event identity. REST current projection alone cannot reconstruct overwritten/deleted versions. Market Data SSE replay is a future observation candidate, not complete as-of history. | Same account agreement/data-rights limit; no live connection or subscription in PM2D-A. PM2C: action raw facts; `SCHEMA_OBSERVATION_REQUIRED`. Next proof: one bounded selected action chain with REST/event comparison, insert/update/delete ordering, duplicate replay, durable event capture, source-channel cutoff witness, retention and entitlement before deriving prices. |

The market-data pricing and rights summary uses Alpaca's
[published plans](https://alpaca.markets/data) and
[account agreement](https://files.alpaca.markets/disclosures/library/AcctAppMarginAndCustAgmt.pdf);
verify current account-specific entitlements before any future approved use.
Neither pricing nor a public endpoint grants access authorization.

### 3.4 Intrinio — fundamentals challenger, estimates not PIT-qualified

| Dataset/API and official evidence | Coverage, subject and economic period | Availability, observation and version | Units, missing, pagination and limits | License, PM2C mapping, status and next proof |
| --- | --- | --- | --- | --- |
| [Fundamental by ID](https://docs.intrinio.com/documentation/web_api/get_fundamental_by_id_v2), [lookup](https://docs.intrinio.com/documentation/web_api/lookup_fundamental_v2), [filter](https://docs.intrinio.com/documentation/web_api/filter_fundamental_v2), [reported financials](https://docs.intrinio.com/documentation/web_api/get_fundamental_reported_financials_v2), [standardized financials](https://docs.intrinio.com/documentation/web_api/get_fundamental_standardized_financials_v2), [company fundamentals](https://docs.intrinio.com/documentation/web_api/get_company_fundamentals_v2), [filing by ID](https://docs.intrinio.com/documentation/web_api/get_filing_by_id_v2), [terminology](https://help.intrinio.com/fundamentals-terminology), [product timing](https://intrinio.com/products/us-fundamentals), and [API limits](https://docs.intrinio.com/documentation/api_v2/limits). SEC-derived US fundamentals from 2006 are described in product material. | Company/fundamental IDs identify an issuer and statement/fiscal period; prove permanent security/share-class mapping, active/delisted depth and selected-cohort completeness separately. Reported values are tag-based; standardized values are vendor-normalized. Flows expose FY/Q/TTM/YTD and balances FY/Q; Q4 is calculated FY minus Q1-Q3 and needs component lineage. | `filing_date` is SEC filing date/time, but filing/acceptance is not source visibility. `updated_date` is vendor last-change time. `first_calculable` means when a value can first be calculated, not exact publication. `earnings_disclosed_at` points to an earnings 8-K, not proof that it contains the exact same normalized fact/version. `reported_signature` and `standardized_signature` are distinct change-detection signatures. Product material gives typical ~10/~30-minute timing for reported/standardized metrics, not guarantee. Lookup is explicitly latest; by-ID identifies a record but does not prove old-version retention; filter bounds filing/update time but has no version-as-of selector. Docs label both `start_date` and `end_date` as period start in some places; exact shape/timezone needs observation. | Exact reported XBRL tag/value/unit/dimensions must be distinguished from standardized normalization. Currency, scale, null/zero and component lineage need per-field proof. Do not assume an empty series or absent field means zero. For paid plans, requests with `page_size > 100` and bulk each have a 1/second limit; the free plan is 1/minute. Requests time out at 25 seconds; other feed limits depend on account. No real call or bulk access here. | Personal fundamentals plan is published at $150/month with personal-use restrictions; Startup schedule is published as $333 -> $666 -> $999/month; Enterprise starts at $1,250/month with custom/feed-specific quote. EPS and Sales estimate history is separately listed at +$150/month for each year of history per feed over a 12-month term with the current feed; a blog calls historical estimate access one-time, so resolve billing/rights by written quote. PM2C: optional raw statement challenger only for an explicitly identified gap. `SCHEMA_OBSERVATION_REQUIRED`; no historical-as-of lookup qualification. |
| [Zacks EPS estimates](https://docs.intrinio.com/documentation/web_api/get_zacks_eps_estimates_v2), [Zacks sales estimates](https://docs.intrinio.com/documentation/web_api/get_zacks_sales_estimates_v2), [forward P/E](https://docs.intrinio.com/documentation/web_api/get_zacks_forward_pe_v2), [EPS product](https://intrinio.com/products/eps-estimates), [sales product](https://intrinio.com/products/sales-estimates). | Company IDs map ticker, Intrinio ID, LEI, CIK; target `date` is fiscal/calendar period end. Product material advertises 5k+ US/Canada names and 20+ years for some feeds; delisted coverage and timestamp-version retention are not established by the schemas. | EPS has 7/30/60/90-day prior mean fields; Sales has 1w/1m/3m aggregates, percent changes, ups/downs and cursors. No observation date per contributor, historical-vintage identifier, publication/revision timestamp, or arbitrary-cutoff API is documented. Forward P/E is FY1-5/latest TTM EPS, not a fixed NTM interval. | EPS mean/median/high/low/stdev/count; Sales equivalent aggregates. These do not supply the prior exact consensus snapshot required by PM2B. Next-page cursors do not establish historical versions. Rates/bandwidth depend on account/feed. | Estimate feed history is distinct from current API fields; +$150/month per year/feed, current feed and 12-month term on published product FAQ; personal plan is not redistribution. `PIT_UNQUALIFIED` for consensus/revisions and fixed NTM. No schema probe until an allowed licensed dated-vintage contract is demonstrated. |

Intrinio's [analyst-ratings vs analyst-estimates article](https://intrinio.com/blog/analyst-ratings-vs-analyst-estimates)
describes a separate analyst-level feed/one-time history offer; ratings snapshots
are not EPS/Sales consensus history. The [official limits page](https://docs.intrinio.com/documentation/api_v2/limits)
and [Python SDK](https://github.com/intrinio/python-sdk) document API paging,
but the SDK uses typed float fields in some fundamental models and does not add
as-of version retrieval. Preserve exact response/raw numeric text before any
future Decimal normalization.

### 3.5 Tiingo — optional price/action cost challenger only

| Dataset/API and official evidence | Coverage, subject and economic period | Availability, observation and version | Units, missing, pagination and limits | License, PM2C mapping, status and next proof |
| --- | --- | --- | --- | --- |
| [EOD documentation](https://www.tiingo.com/documentation/end-of-day), [equity EOD product](https://www.tiingo.com/products/end-of-day-stock-price-data), [fundamentals/permaTicker](https://www.tiingo.com/documentation/fundamentals). | `permaTicker` is a candidate stable security identifier. EOD rows use ticker/date; exact historical alias, active/delisted cohort completeness and security/share-class mapping are not proved by a current security master. | Documentation describes typical US equity EOD delivery around 5:30 p.m. ET and corrections/updates around 8 p.m.; these are typical timing statements, not immutable per-version timestamps. Raw close is `close`; `adjClose` is CRSP split/cash adjusted; `divCash` and `splitFactor` are separate fields. Historical endpoint exposes current values, not an as-of version selector. | Currency is instrument/feed scoped; raw vs adjusted basis must be named. Do not infer publication time from trade date or `startDate/endDate`. Exact missing/correction behavior, delisted completeness and per-row values need bounded observation. | Free $0: 50 requests/hour, 1k/day, 1 GB/month; Power $30/month: 10k/hour, 100k/day, 40 GB; Commercial internal $50/month: 20k/hour, 150k/day, 100 GB. Redistribution tiers are separately published at $250 startup/$500 enterprise; rights/feature depth need exact quote. Terms restrict raw/derived retention for free/trial and specify active-paid/termination deletion obligations. PM2C: optional named-gap price cross-check only; `PIT_UNQUALIFIED` as a historical fact source until corrections and close semantics are observed. |
| [Corporate-action split docs](https://www.tiingo.com/documentation/corporate-actions/splits), [dividend docs](https://www.tiingo.com/documentation/corporate-actions/dividends), [corporate-action product](https://www.tiingo.com/products/corporate-actions/stock-etf-mutual-fund-split-api), [pricing](https://www.tiingo.com/pricing), [terms](https://www.tiingo.com/tos/). | Split/dividend records can include permaTicker, ex/declared/record/payable dates, ratios/cash and current cancellation/status. A stable permaTicker alone does not establish historical alias timing. | No immutable prior event version or complete revision lineage is documented. Declaration/effective/payment dates remain distinct; current cancellation status may not reconstruct when a correction became public. | Split and dividend units/ratios/cash amounts need action-specific currency and adjustment basis. Exact historical endpoint completeness and pagination/rates depend on plan. | Same plan/retention restrictions. Optional only for a selected coverage/rights gap after exact sample. No purchase or activation. `SCHEMA_OBSERVATION_REQUIRED` for event shape; PIT historical correction use remains unqualified. |

The maintained community
[tiingo-python client](https://github.com/hydrosquall/tiingo-python) v0.16.1
shows date filters, JSON/CSV parsing and optional session reuse. It returns
parsed data and logs raw error bodies; it does not establish immutable custody,
PIT semantics or action completeness.

### 3.6 Financial Modeling Prep — lower-cost challenger, historical estimates rejected

| Dataset/API and official evidence | Coverage, subject and economic period | Availability, observation and version | Units, missing, pagination and limits | License, PM2C mapping, status and next proof |
| --- | --- | --- | --- | --- |
| [Financial estimates](https://site.financialmodelingprep.com/developer/docs/stable/financial-estimates), direct [PIT FAQ](https://site.financialmodelingprep.com/faqs?code=analyst), [freshness explanation](https://site.financialmodelingprep.com/insights/enterprise/data-infrastructure/how-to-check-financial-data-coverage-against-your-target-equity), [freshness/update timing](https://site.financialmodelingprep.com/insights/platform/api-access/how-fresh-is-fmp-data-understanding-update-timing-across-prices). | Estimate `date` denotes target fiscal period; EPS/revenue records expose averages, high/low and analyst counts. No estimate-observation date or version identity appears in the reviewed schema. | The FAQ says private timestamped revisions are retained internally but cannot be queried by date on any API plan. Thus historical consensus at an arbitrary cutoff cannot be reconstructed. Filing metadata does not prove which value version was served. Coverage/timing article reports correction risks and date mappings; some filingDate/acceptedDate values can equal report period end, so inspect exact field lineage rather than assuming semantics. | Aggregates are target-period values, not a contributor revision trail. Pagination and rate/bandwidth follow plan. | Personal published plans show $0/$19/$49/$99 monthly equivalent with annual billing; limits 250/day and 300/750/3,000 per minute, bandwidth 500 MB Basic and 20/50/150 GB Starter/Premium/Ultimate, 1 TB+ Enterprise. Terms distinguish personal individual use from commercial display/redistribution Enterprise/custom contact. `PIT_UNQUALIFIED`; rejected as PM2B consensus/revisions. No PM2D-B probe. |
| [As-reported income](https://site.financialmodelingprep.com/developer/docs/stable/as-reported-income-statements), [EOD](https://site.financialmodelingprep.com/developer/docs/stable/historical-price-eod-full), unadjusted/dividend-adjusted price routes, [dividends](https://site.financialmodelingprep.com/developer/docs/stable/dividends-company), [splits](https://site.financialmodelingprep.com/developer/docs/stable/splits-company), [delisted companies](https://site.financialmodelingprep.com/developer/docs/stable/delisted-companies), [historical S&P 500](https://site.financialmodelingprep.com/developer/docs/stable/historical-sp-500), [changelog](https://site.financialmodelingprep.com/developer/docs/changelog). | As-reported rows include date, fiscal year/period, reported currency, CIK, filingDate and acceptedDate. Symbol/CIK/CUSIP/ISIN search and symbol changes do not prove permanent historical share-class mapping. Delisted endpoint is selective/page-limited (100/page). Historical S&P endpoint has changed (Oct. 6 date corrections; Oct. 12 changeType/addedTicker); coverage/baseline completeness remains unresolved. | FilingDate/acceptedDate identify filing metadata, not first public visibility or old served statement versions/accessions. Some date fields can align with period end; do not accept without a filing witness. EOD offers full split-adjusted plus unadjusted/dividend-adjusted routes, but no proven PM2B regular-session-close mapping or immutable correction witness. Dividend/split records supply dates/amounts/ratios with no old correction lineage. | Statement units/currency/taxonomy context and null/zero behavior need exact samples; no assumption that as-reported means historical PIT version retrieval. | Same personal vs commercial distinction above. Estimates remain `PIT_UNQUALIFIED`; statement, price, action and index endpoints are not selected because exact provenance/version claims are unresolved and would duplicate the minimal candidate set. FMP public [income statement repo](https://github.com/FinancialModelingPrep/income-statement-api) and [stocks repo](https://github.com/FinancialModelingPrep/stocks-api) are legacy v3 examples, not authority. Next proof only if later a named gap justifies source selection; no PM2D-A/B probe. |

FMP's published [terms](https://site.financialmodelingprep.com/terms-of-service)
are effective Nov. 17, 2026; verify plan-specific display, redistribution,
retention and commercial rights before any future use.

## 4. Sharadar field and time decision details

SF1's dimensions have deliberately different meanings:

| Dimension | Documented interpretation | PM2D-A use |
| --- | --- | --- |
| `ARQ` | As Reported quarterly, PIT-oriented; does not recast older periods to current restatements. | Candidate only after selected fields, quarter/YTD grain, exact Form 10 date and version evidence are observed. |
| `ARY` | As Reported annual, PIT-oriented. | Annual flow candidate only with exact filing/version and same-FY reconciliation. |
| `ART` | As Reported trailing twelve months measured quarterly; may reflect restated component quarters. | Descriptive parity only. Do not use as four original/as-reported ARQ facts. |
| `MRQ` / `MRY` / `MRT` | Most Recent/restated quarter, year, trailing period. | Rejected for historical PM2C PIT facts. Current restatements cannot replace old versions. |

SF1 uses `datekey` for Form 10 filing date on As Reported dimensions; Most
Recent dimensions use the report-period date (the Nasdaq publisher table route
exposes `date`). `reportperiod` is fiscal period end, `calendardate` is a
normalized calendar bucket, and `lastupdated` is provider change date only,
not an intraday timestamp. These fields are not interchangeable. Same-day
catch-up filings may omit earlier periods. The provider warns
that a Form 8-K may disclose a value before the later Form 10 filing used by
SF1. Using that later Form 10 date as a conservative candidate is valid only
when the exact same fact, value, version, basis, and visibility boundary are
tied to it. A Form 8-K can establish an earlier boundary only with the exact
accession/exhibit fact and separate public-availability witness.

Candidate fields for narrow future evaluation are `ncfo`, `revenue`,
`cor`, `opinc`, `netinccmn`, and `epsdil`. None is accepted yet. Do not
select `capex`, `debt`, `cashneq`, `equity`, `depamor`, or `intexp`
as exact PM2B defaults absent a field-level contract: their documented
aggregation, lease, zero-imputation, parent/common, accretion, or net-interest
semantics do not match the frozen PM2B fields exactly.

For Q2/Q3 use only same-FY compatible YTD flow components; Q4 is annual minus
same-FY Q3 YTD. The current SF1 docs do not establish an exact YTD dimension,
ARQ normalization grain, Q4 component witness, or immutable prior version.
Do not infer discrete quarters from adjacent ARQ rows until the bounded
PM2D-B sample proves it.

## 5. Date-only filing and estimate availability policy

For any date-only source, the candidate conservative bound is the next local
midnight converted to UTC only if that exact value/version is tied to the
source-local date and a documented source-channel witness establishes
availability by date end. Otherwise its historical `available_at` is
unqualified or bounded at a later proven time. The commercial channel may be
private; for SEC facts, the required witness is public filing availability.

The SEC makes official filing pages and raw submissions publicly accessible;
the SEC FAQ describes a typical 1–3 minute post-acceptance processing window,
but it is not a guaranteed first-public timestamp. Official guidance says most
filings after 5:30 p.m. Eastern are disseminated the next business day, with
exceptions. Therefore do not translate `acceptedDate`, a date-only filing
date, or the typical interval directly into `available_at`. A date-only
candidate can be bounded to next local midnight only if the exact version and
public visibility by that source date are established; otherwise leave
availability unqualified or use the later proven boundary.

For vendor-normalized facts, record actual SEC filing/public visibility and
vendor version visibility as separate claims. A later standardized value tied
to a filing does not prove when the vendor made that exact normalization
available. An amendment is append-only and never rewrites the original
observation. PAC updates may change a same-accession filing; if prior bytes or
version lineage cannot be retained, the fact is unqualified for historical
reconstruction.

## 6. Analyst-estimate qualification decision

PM2B revision evidence is stronger than “historical estimates” by target
period. It requires:

- a source-declared fixed forecast interval and target fiscal period;
- mean/median/high/low, analyst count and explicit contributor/aggregation
  policy;
- an immutable observation/revision identity and publication time for each
  value;
- exact same-provider/metric/target/horizon consensus at T and 21 completed
  sessions earlier on the named calendar;
- corrections retained as later versions while the prior observation remains
  retrievable; and
- exact units/currency/basis plus a true fixed NTM interval if used for P/E.

Intrinio's 7/30/60/90-day EPS prior summaries and 1-week/1-month/3-month Sales
aggregates are not 21-session history. Its Lookup endpoint is explicitly
latest; a by-ID record lookup does not prove old-version retention; filter
filing/update bounds do not provide a version-as-of selector. FMP explicitly
states internally timestamped revisions cannot be queried by date on any API
plan. Neither vendor is qualified for PM2B revisions; FY-next, forward P/E,
calendar buckets or later local captures cannot substitute.

## 7. Public repository/reference review

| Repository/reference | Reusable pattern | Explicit limit |
| --- | --- | --- |
| [edgartools filing model](https://github.com/dgunning/edgartools/blob/main/edgar/entity/filings.py) and [Filing guide](https://github.com/dgunning/edgartools/blob/main/edgar/docs/Filing.md) | Accession/index/SGML/XBRL navigation and filing metadata cross-check. | Its submissions timestamps can be unreliable UTC for some filing dates; use SEC header/index as acceptance cross-check, never as public-dissemination proof. |
| [Nasdaq Data Link Python](https://github.com/Nasdaq/data-link-python), especially [get_table.py](https://raw.githubusercontent.com/Nasdaq/data-link-python/main/nasdaqdatalink/get_table.py) | Explicit table projection, filters, and cursor traversal. It follows `next_cursor_id` with `paginate=True`; without pagination it may warn and return a partial result. | It is not raw-response custody or a historical version API. Its page-limit exception can interpolate authentication material; never emit raw SDK errors. See [message.py](https://raw.githubusercontent.com/Nasdaq/data-link-python/main/nasdaqdatalink/message.py). |
| [Intrinio Python SDK](https://github.com/intrinio/python-sdk) | Typed request models and explicit cursor flow. | No as-of version retrieval; float-bound model fields do not retain exact original decimal text. |
| [tiingo-python API client](https://github.com/hydrosquall/tiingo-python/blob/master/tiingo/api.py) | Date filters, JSON/CSV parsing and reusable session. | Parsed responses and raw error logging do not prove immutable response custody, PIT history or corporate-action completeness. |
| [sharadar_db_bundle loader](https://github.com/alphaville76/sharadar_db_bundle/blob/master/sharadar/loaders/ingest_sharadar.py) | Illustrates dataset joins only. | Reject its NaN/Inf-to-zero coercion, dropped `lastupdated`, and same timestamp assigned to dividend events. |
| [FMP income-statement API](https://github.com/FinancialModelingPrep/income-statement-api) and [stocks API](https://github.com/FinancialModelingPrep/stocks-api) | Legacy examples only. | Old v3 examples do not override current official schema or establish historical estimate snapshots. |
| [QuantRocket fundamental-factors example](https://www.quantrocket.com/codeload/fundamental-factors/fundamental_factors/Lesson03-Basic-Usage.ipynb.html), [QuantRocket API docs](https://www.quantrocket.com/docs/api/), and [Sharadar dataset guide](https://github.com/zacharyfrederick/regime/blob/main/sharadar_dataset_guide.md) | AR-oriented examples and documentation can inform a later AR allowlist. | No verified public code-level refusal of MRQ/MRY/MRT was found: a QuantRocket helper permits MR, while the regime guide refuses MR in prose but has a conflicting datekey assertion. Official provider semantics control; future routing must explicitly allow only selected AR dimensions. |

Reusable future adapter patterns are explicit pagination/cursor traversal,
exact raw response byte custody, safe request metadata without credentials,
stable provider record IDs, append-only revisions and separate source vs local
observation clocks. These patterns are candidates only; no adapter was
implemented.

## 8. Published pricing, licensing and operational constraints

Pricing was reviewed on 2026-11-27; it is a public-page snapshot, not an offer,
subscription, entitlement determination, or legal opinion.

| Provider | Published price/limits relevant to this review | Scope limitation or unresolved condition |
| --- | --- | --- |
| SEC | Public filing/API access free; maximum 10 requests/second total and declared User-Agent. | Public reuse is subject to third-party content; no bulk request in PM2D-A. |
| Sharadar direct | Annual personal plans: Fundamentals $199/$299/$399; Prices $99/$199/$299; Bundle $299/$399/$499 (5/10/full plans). | Direct individual license excludes organization/commercial/pro use and redistribution; retained data/reproducible extracts must be deleted at termination. Nasdaq Data Link commercial service order and rights are separate; exact quote/login required. Exact subscribed bandwidth is unconfirmed. |
| Alpaca | Basic $0 (IEX real-time; SIP 15-minute delay; 200/min); Plus $99/month (all exchanges; 10,000/min). | No plan upgrade. Exact rights/entitlement are account-specific; standard account agreement restricts commercial exploitation/distribution without written consent. |
| Intrinio | Personal fundamentals $150/month; Startup published $333 -> $666 -> $999/month; Enterprise starts at $1,250/month/custom. EPS/Sales history add-on $150/month per year/feed for 12-month term with current feed. | Personal use is not redistribution/display. One Intrinio blog describes estimate history as one-time while current product FAQ prices each history year monthly; request a written feed-specific quote before future use. |
| Tiingo | Free $0 (50/hr, 1k/day, 1 GB/month); Power $30/month (10k/hr, 100k/day, 40 GB); Commercial internal $50/month (20k/hr, 150k/day, 100 GB); redistribution tiers $250 startup/$500 enterprise. | Exact product depth and rights depend on plan; free/trial raw/derived retention limits and paid termination/deletion terms apply; exact quote required. Enterprise terms mention financial/AI benchmarking and certain AI/commercial uses; this is scoped contract language, not a blanket ban on owner backtests. |
| FMP | Personal published $0/$19/$49/$99 monthly equivalent on annual billing; 250/day and 300/750/3,000 requests/min; bandwidth 500 MB Basic, 20/50/150 GB paid tiers, 1 TB+ Enterprise. | Personal terms are individual-use only; commercial display/redistribution requires Enterprise/custom contact. Terms effective 2026-11-17. No plan provides queryable historical estimate snapshots. |

Nasdaq generic Data Link API error documentation cites broad daily/10-minute
limits, but exact subscribed Sharadar service throughput was not verified.
Product pricing does not establish the rights required for a commercial
internal trading application, durable raw/derived storage, display, or
redistribution. No purchase or subscription occurred.

## 9. PM2D-B smallest bounded proof plan

Only after PM2D-A is independently accepted and integrated:

Before each bounded observation, freeze a finite attempt budget, exact provider
product/endpoint and schema version, issuer/security set, query window,
maximum requests/pages/rows, and whether/how exact response bytes or permitted
derived evidence may be retained. The numeric limits belong to that reviewed
PM2D-B authorization, not this design. Bind safe request parameters and
provider/request/event IDs without credentials; record attempt identity,
observation time, response content type/length/digest, page/result counts and
terminal outcome. No automatic retry or unbounded “look farther back” search.
If the contract, data, rights or retention proof is absent at the frozen bound,
stop and record the family unavailable/unqualified.

1. **SEC/Sharadar fundamentals:** preselect one issuer and one original 10-Q or
   10-K, a separately accessioned amendment, narrow annual/discrete/YTD/Q4
   facts, one custom dimension, and an early 8-K fact only if testing exact
   same-value lineage. Compare SF1 keys/values/units/grain and candidate
   datekey to exact SEC accession/context/bytes. Include true zero, absent/null,
   conflict, amendment and later-correction cases. This does not qualify all
fields, all issuers, or first public availability.
2. **Security identity and eligible shares:** if required, separately preselect
   one issuer/security with a ticker rename, one possible reused symbol or
   delisting case, and the exact eligible share-class/count context. Compare
   Sharadar TICKERS/ACTIONS and any selected SEC fact to source records with
   effective windows. No current TICKERS sector/industry projection and no
   unbounded peer-history probe. If no historical classification source is
   documented, record peer membership as unavailable rather than probing
   providers by curiosity.
3. **Alpaca price/actions:** if a separate reviewed observation is selected,
   predeclare normal and early-close sessions, trade-condition cases and a
   known correction. Check explicit raw SIP/USD, pagination across symbols,
   missing scheduled sessions, adjustment selectors and exact historical
   correction retrieval. For actions, bound one event chain through REST and
   Market Data SSE, including insert/update/delete, replay duplication,
   retention, entitlement and public/effective times. No live subscription in
   PM2D-A.
4. **Analyst estimates:** no sample until a distinct licensed dated-vintage
   contract proves arbitrary-cutoff retrieval and old-version retention. Only
   then consider same issuer/metric/fixed target snapshots at T-21, T and after
   a later correction, plus a genuine fixed NTM interval if documented. FMP is
   not a probe candidate.
5. **Membership:** sample Sharadar SP500 only if selected, with a baseline,
   one addition/removal, effective date, exact S&P announcement witness and
   coverage bound. This cannot qualify historical peer/sector labels.

Each provider observation remains separately authorized, exact-source-bound
and attempt-counted. No bulk-data acquisition is a PM2D-B goal.

## 10. Verification and next milestone

This is a documentation-only record. PM2D-A made no provider schema/sample
observation and ran no pytest, FULL, subscription check, credential flow,
account read, market-data request, AI call, or broker operation. The repository
candidate is limited to its architecture/validation documents plus bounded
status and handoff updates. Docs/static hygiene and `git diff --check` are
the appropriate local checks; mapped publication must remain DOCS_ONLY.

Next milestone: **PM2D-B — bounded schema/sample qualification**, limited to
the accepted proof cases in §9. A real source adapter remains a later
milestone, after each required observation, source license and exact PM2C
mapping have been reviewed and accepted.
