# Architecture 152-PM2D-B1-R — Real Fundamental Observation Readiness

**Status:** C1 corrects the native SEC endpoint, evidence-store, authorization,
deadline, and embedded-document boundaries; the SEC operational first-observed
path is structurally ready pending a real subject and later review;
`SEC_HISTORICAL_RECONSTRUCTION_BLOCKED`;
`SHARADAR_VERSION_OR_ENTITLEMENT_UNQUALIFIED`. **No real observation is
authorized by this checkpoint.**

## 1. Parent checkpoint and boundary

This checkpoint starts from accepted PM2D-B1-C1 source HEAD
`3c9aa6c1dad6db5417bc3622a671906c13731afc` / tree
`82cd1c2a151ed332e0c898476ddd1686b7ef5729`. The feature mapped FULL run
`46114211575` and develop acceptance run `46115517155` are terminal success;
develop reused the exact feature certification. The persistent branch remains
`feature/robinhood-portfolio-manager-current`.

C1 preserves the published B1-R parent HEAD
`91aa3119ed4f594f624b14e989982ec5cc496594` / tree
`1fb4cb0a917ee1c80b89b84c5278fde6dea27c4d`; its feature FULL run
`46123188954`, attempt 1, was terminal SUCCESS. C1 adds no route and does not
change the seven-lane mapped FULL topology.

B1 remains the synthetic SEC/Sharadar comparison operator. Its fake-provider
type restriction is unchanged. B1-R separates the native SEC parser and
synthetic fake-transport harness in `sec_native_observation.py` from the
explicit real transport boundary in `sec_real_observation.py`. The real
boundary is not imported by application startup, source-admission code, pytest,
or CI. The routing authority check scans the application and scripts to reject
imports of the real boundary and calls to its entry or the parser's injected-
transport runner; it scans the entire test tree to reject reachability of the
real boundary. Synthetic tests call the parser only with fake transports. The
path creates no PM2C
`SourceFact`, research snapshot, recommendation, or portfolio authority.

PM1 remains disarmed and preview-only. PM2A real account reads remain
unauthorized. Arch149 remains sealed. No credential, account, AI, broker, or
production effect is added by this checkpoint.

## 2. Source feasibility decision

### Sharadar

Official Sharadar documentation describes SF1 ARY/ARQ as As Reported and
time-indexed to the Form 10 filing date. That makes annual revenue a plausible
candidate, but the public contract reviewed here does not establish an
immutable historical API for retrieving an exact prior SF1 version or the
first time that exact normalized row was available. `datekey`, `lastupdated`,
an API response, and a filing date do not close that gap. The subscription
terms reviewed also restrict direct plans to personal use, limit publication
of evaluations, and require retained data and derivable extracts to be deleted
after termination. The permitted entitlement and evidence-retention terms for
this project are therefore unresolved. No subscription, account, key, login,
provider endpoint, or provider response was used.

**Classification:** `SHARADAR_VERSION_OR_ENTITLEMENT_UNQUALIFIED`. Keep
Sharadar as a candidate. Do not build or call a commercial-provider route
until exact version retrieval, independent availability evidence, entitlement,
and retention rights are established in writing.

### Direct SEC

SEC EDGAR provides accession-addressed filing records and original filing
documents. The native parser accepts only the exact planned complete-submission
text and the named `EX-101.INS` member embedded in that response. It rejects
unsupported XML shapes, external entity declarations, context/period/issuer
mismatches, unsupported dimensions, and missing or duplicate target facts.
The raw response is retained separately from normalized filing/fact records.
Company Facts is not used as an immutable as-filed witness.

The SEC does not expose a dependable timestamp for when exact filing content
first became public. Acceptance time and filing date cannot establish the
historical public-availability boundary required by PM2C. CIK identifies an
issuer, not an exact share class or PM2C security. No independent historical
version witness or issuer-to-security mapping is currently selected.

PM2C already separates operational receipt from historical reconstruction.
An operational `SourceFact` can use a trusted local response receipt as its
conservative `available_at` and `observed_at`, and an operational snapshot
admits it only at or after that receipt. Historical reconstruction still
requires an exact `VersionAsOfWitness`; acceptance time, filing date, a fixed
delay, and current receipt cannot be used to backdate it. The native SEC path
now preserves the local receipt timestamp with the original response, but this
checkpoint does not construct a PM2C `SourceFact` because no independently
established security mapping or real observation exists.

**Classification:** `SEC_OPERATIONAL_FIRST_OBSERVED_PATH_READY_PENDING_EXACT_SUBJECT_AND_REVIEW`;
`SEC_HISTORICAL_RECONSTRUCTION_BLOCKED`. The direct SEC route can support a
current operational fundamental snapshot after its bridge prerequisites are
met. It does not yet support historical replay or an SEC/Sharadar comparison.
The SEC daily Feed and Oldloads archives are a possible later historical
version-witness research route, not an admitted source.

## 3. Native SEC boundary

`src/trading_bot/portfolio_manager/sec_native_observation.py` freezes one
annual 10-K revenue hypothesis with exact plan fields for source HEAD/tree,
attempt ID, CIK, accession, filing document and sequence, context, fiscal
period, expanded concept namespace, dimensions, USD unit, endpoint, User-Agent,
evidence root, and bounded request/parser time and size limits. The current
narrow concept candidate is US-GAAP
`RevenueFromContractWithCustomerExcludingAssessedTax`; a selected filing must
actually contain that exact concept and grain. No alias is inferred.

The proposed acquisition uses one HTTPS GET to the exact SEC complete-submission
URL and parses only the named instance member inside those same response
bytes. The archive directory uses the accession without dashes; the complete-
submission filename uses the dashed accession, as shown in the SEC's official
[EDGAR path guidance](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data).
No fallback endpoint or retry is allowed. The plan has no query parameters,
allows one request, limits the response to 10,000,000 bytes, the filing to 200
document members, the XML to 100,000 elements and 10,000 candidate revenue
facts, each blocking socket operation to at most 10 seconds and the request
elapsed budget to 30 seconds. Standard-library DNS and connection setup do not
provide a hard end-to-end wall-clock guarantee; the implementation checks the
elapsed budget before and after transport and bounds response reads by the
remaining deadline.

The original response bytes and digest remain separate from the normalized
accession, exact document, context, period, namespace, dimensions, unit and
decimal value. The local UTC receipt time is captured when the response body
finishes, stored beside the raw bytes, and carried as the submission's
`observed_at`. It is explicitly first local receipt, not SEC publication time.
The embedded document range and digest are reverified against its parent
submission before parsing.

Production observation accepts paths to the actual prepublication admission
report and separate reviewed effect-authorization record. It verifies their
contents and exact source/plan/attempt bindings, hashes the bytes itself, and
copies the exact records into the attempt custody before request intent, and
rechecks the original records and time window after source admission and
durable intent.
The production entry constructs the exact reviewed `SECFileEvidenceStore`; it
does not accept injected stores, transports, clocks, or typed grants. A
UUIDv5 attempt identity is derived from the exact source and selected annual
fact, excluding the evidence path, and custody is fixed below
`F:\AI\temp\pm2d-b1-sec-observations`. This prevents a path change from
replaying a consumed attempt. Durable request intent precedes invocation;
failed intent, changed source, expired authorization, or consumed attempt
causes zero transport calls. Returned response digests are checked against
the actual bytes, and the file store reads back the preserved bytes before
reporting custody success.

The real HTTPS transport and manually invoked `observe_sec_once` entry are
isolated in `src/trading_bot/portfolio_manager/sec_real_observation.py`. No
application or admission code imports that module. Its injected-transport
counterpart remains private in the parser module and is exercised only with
synthetic fake transports. The checkpoint route checks those no-reachability
invariants.

Before a future request, the entry requires an actual successful FEATURE and
PROSPECTIVE_DEVELOP prepublication report for the exact clean source and a
separate, time-limited authorization record bound to the plan, source,
admission-report digest and attempt. It rechecks source authority and
authorization immediately before invocation. This checkpoint does not create
an effect authorization or call the operator. The tests use only synthetic
bytes and private fake transports. Parsing a response still does not create a
PM2C `SourceFact`.

## 4. Finite plan proposed for review

This is a bounded plan template, not an executable observation authorization:

| Bound | Proposed value |
| --- | --- |
| Source | SEC EDGAR native complete-submission filing only |
| Fact | One annual revenue fact, USD, scale 0, exact US-GAAP concept above |
| Filing | One original 10-K, one exact `EX-101.INS` member name and sequence |
| Issuer, CIK, accession, fiscal period, context, dimensions | Unselected; must be independently chosen and frozen before plan approval |
| Request | One exact accession archive URL; no query parameters |
| Request / response | 1 attempt, 10,000,000 response bytes maximum, no retry |
| Filing / parse | 200 document members, 100,000 XML elements, 10,000 target-concept facts maximum |
| Time | 10-second request timeout; 30-second total limit |
| Evidence | One deterministic one-shot directory below `F:\AI\temp\pm2d-b1-sec-observations`; create-once raw response, receipt metadata, plan, durable request intent and terminal record |
| Operational bridge | Register one exact PM2C `RAW` decimal-USD annual-revenue `CatalogEntry`; independently establish issuer CIK to exact PM2C symbol, security ID and share class; bind response digest, accession/document/context, annual period, concept, exact decimal, USD unit, source record ID and local receipt; set conservative `available_at` and `observed_at` no earlier than receipt; supply a valid exact `MembershipBinding`; admit only `SnapshotMode.OPERATIONAL` snapshots with cutoff at or after receipt |
| Historical bridge | Separate exact immutable-version and public-availability witness at the historical cutoff; current receipt, acceptance time, filing date, and fixed delay do not qualify |
| Terminal result if a parser or identity check fails | Typed SEC failure; no PM2C `SourceFact` |
| Sharadar comparison | None in this plan; candidate remains version/entitlement unqualified |
| Effect counters in this checkpoint | Zero real requests, bytes, records, credentials, accounts, AI, broker, or production mutations |

The exact CIK/accession/context are intentionally not fabricated or borrowed
from the synthetic PM2C candidate. The next operational observation first
needs an independently sourced real issuer/security mapping and one original
annual filing whose named instance contains the frozen concept and exact
grain. Historical reconstruction separately remains blocked until an exact
historical version/availability witness is established. Do not broaden the
first observation to Q1, Company Facts, amendments, other fields, or bulk
historical acquisition.

## 5. Q1 regression coverage

B1 supports the synthetic direct-Q1 comparison only when an independently
supplied exact grain witness matches the SEC and SF1 records. Focused tests now
cover a valid exact witness, an absent witness, and incompatible grain/period
witnesses. This does not expand the first real observation beyond annual ARY
revenue.

## 6. Next prerequisites

Before one future operational request, ChatGPT must review: (1) a public,
independent issuer-to-security/share-class mapping; (2) one original annual
10-K accession, exact `EX-101.INS` document and sequence, context, period,
dimensions, and frozen revenue concept; (3) a final accepted source HEAD/tree,
its successful actual FEATURE/PROSPECTIVE_DEVELOP admission report, and a
separate exact-plan effect authorization record with a short validity window;
and (4) the deterministic attempt ID and canonical external custody root.
The finite request is one HTTPS GET to the dashed accession filename inside the
compact accession directory, with the limits above and no retry. It would
produce a first-observed operational fact only if parsing and independent
security mapping pass; it would not satisfy historical reconstruction. This
checkpoint does not authorize that request. Sharadar remains excluded unless
its historical-version and entitlement contract is independently resolved. No
develop integration or protected effect is part of this checkpoint.
