# Architecture 152-PM2D-B1-R — Real Fundamental Observation Readiness Validation

**Readiness:** `SEC_OPERATIONAL_FIRST_OBSERVED_PATH_READY_PENDING_EXACT_SUBJECT_AND_REVIEW`;
`SEC_HISTORICAL_RECONSTRUCTION_BLOCKED`; and
`SHARADAR_VERSION_OR_ENTITLEMENT_UNQUALIFIED`.
**No real observation is authorized by this checkpoint.**

## 1. Parent and evidence boundary

Accepted PM2D-B1-C1 parent: HEAD
`3c9aa6c1dad6db5417bc3622a671906c13731afc` / tree
`82cd1c2a151ed332e0c898476ddd1686b7ef5729`. Feature mapped FULL run
`46114211575` and develop acceptance run `46115517155` are terminal success;
develop used `exact_feature_certification` reuse. The B1-R checkpoint is a
new source-only child on the persistent Portfolio Manager feature branch.

C1 preserves published B1-R HEAD
`91aa3119ed4f594f624b14e989982ec5cc496594` / tree
`1fb4cb0a917ee1c80b89b84c5278fde6dea27c4d`; its feature FULL run
`46123188954`, attempt 1, was terminal SUCCESS. C1 is a corrective descendant
and leaves the existing seven-lane mapped FULL route unchanged.

This validation did not purchase or access a subscription, log in, inspect
credentials, call a Sharadar API, fetch SEC filing data, read a brokerage
account, call an AI provider, place an order, mutate production state, or
access sealed Arch149 data. Test providers serve explicitly synthetic bytes.
No real request or observation attempt was made.

## 2. Documentation feasibility evidence

Official Sharadar documentation identifies SF1 ARY/ARQ as As Reported and
describes the Form 10 filing-date time index, but does not establish immutable
prior-version retrieval or first availability of an exact normalized value.
The official [Fundamentals documentation](https://sharadar.com/docs/fundamentals)
and [terms](https://sharadar.com/terms) were reviewed. Direct-plan use and
retention/publication limits leave this project’s entitlement and evidence
retention rights unresolved. No provider API sample was requested.

SEC official [EDGAR API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
and [data access guidance](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
support a narrow accession-addressed native filing path. The official path
example uses the accession without dashes for the archive directory and the
dashed accession for the complete-submission filename. The SEC
[Webmaster FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions)
says posting delay is not guaranteed and that it does not provide a timestamp
for when filing content first became available on SEC.gov. Therefore neither
acceptance time nor filing date can serve as the PM2C public-availability
witness. SEC CIK is issuer identity, not a security/share-class key. The
independent SEC route can support a current operational PM2C fact at first
local receipt after exact issuer/security mapping, but it cannot establish
historical public availability and it is not a successful SEC/Sharadar
comparison. SEC daily [Feed](https://www.sec.gov/Archives/edgar/Feed/) and
[Oldloads](https://www.sec.gov/Archives/edgar/Oldloads/) archives remain a
potential later version-witness research route, not an admitted source.

PM2C already supports this distinction without a contract change:
`SnapshotMode.OPERATIONAL` requires both conservative `available_at` and
`observed_at` to be at or before the decision cutoff; historical reconstruction
requires an exact `VersionAsOfWitness` for a fact first received after its
historical cutoff. The bridge may therefore set both time fields no earlier
than the trusted local receipt and admit only operational snapshots at or
after receipt. It must register one exact RAW decimal-USD annual-revenue
catalog entry, bind the exact response digest, accession/document/context,
period, concept, decimal value, USD unit, source record and local receipt,
supply a valid `MembershipBinding`, and independently establish the
CIK-to-symbol/security/share-class mapping. The generic PM2C contracts support
these bindings; the current catalog has no built-in annual-revenue entry, so
that exact field registration is a bridge prerequisite. A receipt cannot be
projected backward into a historical snapshot.

## 3. Implementation and focused adversarial coverage

The native parser and synthetic fake-transport harness are isolated in
`src/trading_bot/portfolio_manager/sec_native_observation.py`; the explicit
real SEC transport and manual entrypoint are separate in
`src/trading_bot/portfolio_manager/sec_real_observation.py`. Application
startup, source admission, pytest, and CI do not import or call the real
entrypoint. The route authority check scans application, scripts and admission
code for imports of the real boundary and calls to its entry or the parser's
injected-transport runner. It scans every test module to keep the real
entrypoint out of pytest and CI. Synthetic tests use only fake transports. It
binds one
annual 10-K, one exact `EX-101.INS` member name and sequence, and one USD
revenue concept. The single SEC complete-submission response contains both the
accession header and embedded XBRL member, avoiding separate fetches that
could observe different same-accession bytes. The parser preserves exact
decimal values, issuer/context/period/dimensions/unit/currency/scale identity,
the SEC filing date, raw acceptance timestamp, original-response digest, and
local observation time. Neither SEC timestamp establishes first public
availability.
Bounded XML parsing rejects DTD/entities and external inclusion; no external
resource loader is configured. Unsupported native shapes fail closed.

The one-shot contract allows one request, at most 10,000,000 response bytes,
200 filing members, 100,000 XML elements, 10,000 candidate revenue facts, a
10-second per-blocking-socket-operation timeout, a 30-second elapsed budget,
and no automatic retry. It does not claim a hard end-to-end wall-clock bound:
standard-library DNS and connection setup are not governed by the response
read deadline. The source is checked against the clean feature worktree,
current remote feature tip, and FEATURE/PROSPECTIVE_DEVELOP authority before
attempt reservation and again immediately before the request. Production
accepts actual report paths, validates their contents and exact bindings, and
computes each evidence digest from the bytes. A separate short-lived
plan/source/attempt authorization must bind the exact admission report digest.
The authorization file and admission report are re-read and rechecked after
source admission and durable intent. The real boundary constructs the exact
`SECFileEvidenceStore`; structural store substitution, clock injection, and
typed-grant injection are excluded. A canonical UUIDv5 attempt and fixed
external `F:\AI\temp\pm2d-b1-sec-observations` root make attempts create-once
across evidence-path changes. Request intent is durable before invocation.
The exact source-admission and effect-authorization JSON bytes are copied into
attempt custody and their paths and digests are recorded in the intent and
terminal result. Raw filing bytes, receipt metadata, and normalized terminal
records are separate; the body receipt time is recorded locally and cannot
claim availability earlier than receipt. Response digests are checked against
preserved bytes.

Synthetic tests verify the SEC URL, exact member filename and embedded-byte
identity, exact decimal preservation, namespace/context/issuer/period/dimension/
unit mismatches, missing versus true zero, duplicate/conflicting facts,
DTD/entity rejection, XML and response bounds, per-read deadline behavior,
elapsed-limit accounting, provider timeout accounting, no retry, consumed
attempt rejection, evidence-path/store substitution rejection, actual
admission and authorization record binding, expiry/evidence change before the
provider call, request-intent failure, response digest/custody failure, and
receipt-time custody. Tests use only explicitly synthetic fixtures and private
fake transports; the real entry is unreachable from pytest and CI. A successful
synthetic parse still creates no PM2C `SourceFact`. Existing PM2C operational
and historical cutoff tests plus B1 direct-Q1 exact-grain witness tests remain
in the focused verification set; Q1 is not permitted in the first real
observation.

The B1-C1 checkpoint routing remains shared and source-only, maps to the
existing seven-lane canonical FULL workflow, keeps the B1 fake operator
restricted to fake provider types, and has no preflight or execute hook. The
parser, separately isolated manual-entry module, and synthetic tests are
included in that route. No local FULL is run for this checkpoint.

## 4. Pending publication evidence

The exact C1 candidate HEAD/tree, FEATURE and PROSPECTIVE_DEVELOP admission
output, mapped feature FULL run and all seven lane results, and zero real-effect
counters are reported with this source handoff after the single ordinary push.
Preserve any failed run; do not retry unchanged CI or integrate `develop` from
this checkpoint.

## 5. Exact next observation gate

The plan remains non-executable because no real issuer/security, CIK,
accession, fiscal context, or independent CIK-to-security mapping has been
selected. The proposed next minimal operation is one SEC native accession GET
for one original annual 10-K revenue fact, captured as a first-observed
operational fact. Before any request, ChatGPT must review the exact subject and
share-class mapping, original accession/document/context, annual period,
concept, dimensions and unit; final accepted HEAD/tree; actual FEATURE and
PROSPECTIVE_DEVELOP admission report; canonical attempt ID/root; one-request
byte/time contract; and a separate short-lived effect authorization bound to
the exact report digest and plan. The request remains one GET with no retries
or endpoint fallback. It will not establish historical PIT qualification.
Sharadar remains out of scope until its exact immutable-version witness and
project-use entitlement/retention terms are resolved.

PM1 remains disarmed and preview-only. PM2A real account reads remain
unauthorized. Arch149 remains sealed. No production research, recommendation,
or trading authority is granted.
