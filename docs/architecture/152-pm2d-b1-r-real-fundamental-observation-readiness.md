# Architecture 152-PM2D-B1-R — Real Fundamental Observation Readiness

**Status:** readiness implemented; `SEC_OBSERVATION_BLOCKED`;
`SHARADAR_VERSION_OR_ENTITLEMENT_UNQUALIFIED`. **No real observation is
authorized by this checkpoint.**

## 1. Parent checkpoint and boundary

This checkpoint starts from accepted PM2D-B1-C1 source HEAD
`3c9aa6c1dad6db5417bc3622a671906c13731afc` / tree
`82cd1c2a151ed332e0c898476ddd1686b7ef5729`. The feature mapped FULL run
`46114211575` and develop acceptance run `46115517155` are terminal success;
develop reused the exact feature certification. The persistent branch remains
`feature/robinhood-portfolio-manager-current`.

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

The SEC states that filings often appear shortly after acceptance, but that
processing time is not guaranteed and that EDGAR does not expose a timestamp
for when filing content first became available on SEC.gov. Acceptance time,
filing date, and the local observation time therefore cannot establish the
historical public-availability boundary required by PM2C. CIK also identifies
an issuer, not an exact share class or PM2C security. No independent witness
for either requirement is currently selected.

**Classification:** `SEC_OBSERVATION_BLOCKED`. A direct SEC accession route is
an independent way to preserve and parse an as-filed revenue fact, but it
cannot independently qualify a PM2C point-in-time fact until public
availability and security-identity witnesses exist. It must not be reported
as a successful SEC/Sharadar comparison.

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
bytes. This avoids mixing two separately fetched copies of a filing. The plan
has no query parameters, allows one request, limits the response to 10,000,000
bytes, the filing to 200 document members, the XML to 100,000 elements and
10,000 candidate revenue facts, the request socket timeout to 10 seconds and
the total elapsed budget to 30 seconds, with no retry. Original bytes and their digest remain distinct from
the normalized accession, context, period, dimension, unit, and exact decimal
record, the SEC filing date, raw acceptance timestamp, and local observation
time. The filing date and acceptance time do not establish when the content
first became public. Durable intent precedes any transport call; it records the
plan/source/attempt-bound authorization ID, review-record digest, and validity
window. Attempt accounting is incremented first; the attempt ID is create-once
under an external `F:\AI\temp` evidence root.

The real HTTPS transport and manually invoked `observe_sec_once` entry are
isolated in `src/trading_bot/portfolio_manager/sec_real_observation.py`. No
application or admission code imports that module. Its injected-transport
counterpart remains private in the parser module and is exercised only with
synthetic fake transports. The checkpoint route checks those no-reachability
invariants.

Before a future request, the entry boundary requires a typed FEATURE and
PROSPECTIVE_DEVELOP pass bound to the plan source, rechecks the clean exact
feature worktree and both current source-authority contexts, and requires a
separate time-limited authorization bound to the plan, source and attempt.
This readiness checkpoint does not issue that authorization and does not run
the operator. The completed test path uses synthetic bytes and a fake
transport only. The successful parse outcome remains blocked and never creates
a PM2C `SourceFact` while availability and security-identity witnesses are
unproven.

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
| Evidence | One unique attempt directory under `F:\AI\temp`; write-once raw response, metadata, plan, request intent and terminal record |
| Required independent witnesses | Historical public-availability time and exact PM2C security/share-class mapping |
| Terminal result if either witness is absent | `SEC_OBSERVATION_BLOCKED`; no PM2C `SourceFact` |
| Sharadar comparison | None in this plan; candidate remains version/entitlement unqualified |
| Effect counters in this checkpoint | Zero real requests, bytes, records, credentials, accounts, AI, broker, or production mutations |

The exact CIK/accession/context are intentionally not fabricated or borrowed
from the synthetic PM2C candidate. A separate review must first select a real
security and original filing, bind its exact annual context and concept, and
establish a defensible availability witness. If that witness remains
unavailable, stop with `SEC_OBSERVATION_BLOCKED`; do not broaden to Q1,
Company Facts, amendments, other fields, or historical acquisition.

## 5. Q1 regression coverage

B1 supports the synthetic direct-Q1 comparison only when an independently
supplied exact grain witness matches the SEC and SF1 records. Focused tests now
cover a valid exact witness, an absent witness, and incompatible grain/period
witnesses. This does not expand the first real observation beyond annual ARY
revenue.

## 6. Next prerequisites

ChatGPT must review the exact published B1-R diff and terminal mapped CI before
source acceptance. A later observation proposal must then provide a real
issuer/security mapping, original annual accession, named document/context,
period, dimensions, and a distinct public-availability witness; successful
FEATURE and PROSPECTIVE_DEVELOP source admission; a fresh unique external
evidence root; and a separately reviewed plan-bound effect authorization.
Only that later review may decide whether one SEC request is allowed. Sharadar
remains excluded unless its historical-version and entitlement contract is
independently resolved. No develop integration or protected effect is part of
this checkpoint.
