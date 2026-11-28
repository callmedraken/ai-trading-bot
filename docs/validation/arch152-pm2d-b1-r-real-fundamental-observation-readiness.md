# Architecture 152-PM2D-B1-R — Real Fundamental Observation Readiness Validation

**Result:** `SEC_OBSERVATION_BLOCKED` and
`SHARADAR_VERSION_OR_ENTITLEMENT_UNQUALIFIED`.
**No real observation is authorized by this checkpoint.**

## 1. Parent and evidence boundary

Accepted PM2D-B1-C1 parent: HEAD
`3c9aa6c1dad6db5417bc3622a671906c13731afc` / tree
`82cd1c2a151ed332e0c898476ddd1686b7ef5729`. Feature mapped FULL run
`46114211575` and develop acceptance run `46115517155` are terminal success;
develop used `exact_feature_certification` reuse. The B1-R checkpoint is a
new source-only child on the persistent Portfolio Manager feature branch.

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
support a narrow accession-addressed native filing path. The SEC
[Webmaster FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions)
says posting delay is not guaranteed and that it does not provide a timestamp
for when filing content first became available on SEC.gov. Therefore neither
acceptance time nor filing date can serve as the PM2C public-availability
witness. SEC CIK is issuer identity, not a security/share-class key. The
independent SEC route is useful for preserving and parsing a filing but is not
currently sufficient to admit a point-in-time PM2C fact or a provider
comparison.

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
10-second socket timeout, 30-second elapsed budget, and no automatic retry.
The exact
source is checked against the clean feature worktree, current remote feature
tip, and FEATURE/PROSPECTIVE_DEVELOP authority before attempt reservation. A
separate plan/source/attempt-bound, time-limited effect authorization is
required. Durable attempt reservation and request intent precede any
transport invocation. The intent persists the authorization ID, review-record
digest and validity window alongside its exact plan/source/attempt binding.
Raw bytes and normalized terminal records are stored separately under a unique
external `F:\AI\temp` attempt directory.

Synthetic tests verify native submission/document binding, exact decimal
preservation, namespace/context/issuer/period/dimension/unit mismatches,
missing versus true zero, duplicate/conflicting facts, DTD/entity rejection,
XML and response bounds, provider timeout accounting, no retry, consumed
attempt rejection, request-intent ordering, evidence-write failure, source and
effect gates before transport, and raw/normalized custody separation. The
successful synthetic parse remains `SEC_OBSERVATION_BLOCKED` while independent
availability and security-identity witnesses are unproven; no PM2C `SourceFact`
is created. B1 direct-Q1 tests cover a valid exact-grain witness, missing
witness, and incompatible witness grain/period. These do not permit Q1 in the
first real observation.

The B1-C1 checkpoint routing remains shared and source-only, maps to the
existing seven-lane canonical FULL workflow, keeps the B1 fake operator
restricted to fake provider types, and has no preflight or execute hook. The
parser, separately isolated manual-entry module, and synthetic tests are
included in that route. No local FULL is run for this checkpoint.

## 4. Pending publication evidence

This file records the expected scope and feasibility decision. The exact
published B1-R HEAD/tree, FEATURE and PROSPECTIVE_DEVELOP admission output,
terminal feature CI run, and zero real-effect counters belong in the final
source handoff after one exact-path commit, one ordinary push, and completion
of the mapped workflow. A failed run remains immutable; do not retry unchanged
CI or integrate `develop` from this checkpoint.

## 5. Exact next observation gate

The current plan template is non-executable because no real issuer/security,
CIK, accession, fiscal context, or independent public-availability witness
has been selected. Before any future request, ChatGPT must review a finite
plan binding the accepted source HEAD/tree, unique attempt ID, real subject and
security mapping, original annual 10-K accession, exact document/context,
annual period, concept namespace, dimensions, unit, one endpoint, byte/time
limits, and a fresh external evidence directory. FEATURE and
PROSPECTIVE_DEVELOP admission and a separate plan-bound effect authorization
are required immediately before that one request. If a defensible historical
public-availability witness or security mapping is unavailable, stop with
`SEC_OBSERVATION_BLOCKED`. Sharadar remains out of scope until both its exact
immutable-version witness and project-use entitlement/retention terms are
resolved.

PM1 remains disarmed and preview-only. PM2A real account reads remain
unauthorized. Arch149 remains sealed. No production research, recommendation,
or trading authority is granted.
