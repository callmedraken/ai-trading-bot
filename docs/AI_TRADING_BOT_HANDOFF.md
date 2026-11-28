# AI Trading Bot - Current Handoff

## Current milestone — PM2D-B1-N reusable SEC financial statement ingestion

The exact accepted base is PM2D-B1-R-C2 HEAD
`85d2cc1aec12d172d0225eac61bda770becdbbc7` / tree
`acf07f52d33f15fad7e391329076c015b844ce77`. Feature mapped FULL run
`46130743708`, attempt 1, passed all seven lanes. Develop acceptance run
`46131689560`, attempt 1, passed source-static and source-gates with
`DEVELOP_CERTIFICATION_REUSE=True REASON=exact_feature_certification`; all
test/certification jobs were skipped. The canonical develop worktree retains
its 17 pre-existing untracked artifacts. This newer exact source/CI evidence
corrects the older C1 parent still recorded in the B1-R history below.

B1-N adds a reusable offline financial statement extractor for the
already-held, digest-verified SEC native instance. The existing B1 checkpoint
slug, source routing, and seven-lane mapped FULL remain in use. B1's fake
provider contract and B1-R's one-shot real transport are unchanged. No filing
request, new provider access, or taxonomy download is authorized.

The pinned library review found no adoption appropriate for this bounded task.
EdgarTools at
[`31371d4`](https://github.com/dgunning/edgartools/tree/31371d457ee4c95d9f397a07fa3fc60a3b7b4492)
offers local-file XBRL parsing, presentation roles, and standardization, but
the reviewed fact parser uses floating-point numeric values and its mapping
helpers do not prove the exact accounting basis. Its high-level filing path can
retrieve attachments and may use a network fallback for older missing
instances; this does not imply its explicit local-file parser itself makes a
request. Arelle at
[`1a82e97`](https://github.com/Arelle/Arelle/tree/1a82e9731e70bdb3cb9721a5e6ad812507f470e4)
provides fuller native/inline XBRL, taxonomy package, presentation, and
duplicate-fact support, but requires broader dependencies and an explicit
offline package/cache configuration. The one-document boundary uses the
standard-library XML path and existing PM2C models; no dependency is added.
See the [B1-N architecture](architecture/152-pm2d-b1-n-reusable-sec-financial-statement-ingestion.md)
and [validation record](validation/arch152-pm2d-b1-n-reusable-sec-financial-statement-ingestion.md)
for source links and value-level results.

The owner-held ODFL instance is 1,350,303 bytes, SHA-256
`96437a6d33f26d4f559afcd7e7b14ebafd9f84fcee909520c16f11467f0a06b0`, from
original 10-K accession `0001564590-19-004755`, instance
`odfl-20181231.xml`, sequence 11. It has annual context
`C_0000878927_20180101_20181231` and namespace
`http://fasb.org/us-gaap/2018-01-31`. The original ExcludingAssessedTax
hypothesis has zero facts; consolidated revenue is the separate
IncludingAssessedTax concept at `4043695000` USD, with no dimensions. LTL and
other-service dimensional facts are `3982658000` USD and `61037000` USD.
These are discovery facts from existing bytes, not a real production
observation or current investment signal. The canonical B1-O attempt remains
unconsumed; do not obtain another SEC copy.

The frozen B1-R `SECObservationPlan` requires
`RevenueFromContractWithCustomerExcludingAssessedTax`; the ODFL
IncludingAssessedTax fact cannot use that plan. Do not retarget B1-R. A future
request must use a filing matching the frozen plan or a separately reviewed
successor plan/source.

Offline extraction also produced exact operating income, diluted EPS,
operating cash flow, cash, assets, liabilities, stockholders' equity, and
separately named productive-asset-payment and long-term-debt facts. The generic
`NetIncomeLoss` fact is not a PM2B attributable-to-common net-income mapping.
The PPE-specific acquisition concept is missing, and `PaymentsToAcquireProductiveAssets`
remains a separate field. Debt facts are not aggregated. The validation record
contains each value, original context, unit, decimals, dimension, and typed
unsupported concept.

Operational admission for this ODFL discovery remains blocked. The file is not
a consumed B1-R response with trusted response receipt; an independent
issuer-to-security/share-class mapping, exact membership binding, and exact
catalog entry are also required. Filing date, acceptance metadata, file
modification time, or current execution time cannot stand in for receipt or
historical public availability. No PM2C SourceFact or operational snapshot is
emitted from these discovery bytes.

PM1 remains disarmed and preview-only; PM2A real account reads remain
unauthorized; Sharadar remains unqualified for exact version/entitlement and
retention; Arch149 remains sealed. Next, finish the narrow custody-bridge
correction and focused verification, then complete combined Ruff and diff
checks. The source-publication owner then completes FEATURE and
PROSPECTIVE_DEVELOP admission and the single mapped CI run under the reviewed
scope. Do not run local FULL, integrate `develop`, or make a real SEC request.

### Historical predecessor — PM2D-B1-R-C1-C2 SEC response accounting

The accepted PM2D-B1-C1 parent is HEAD
`3c9aa6c1dad6db5417bc3622a671906c13731afc` / tree
`82cd1c2a151ed332e0c898476ddd1686b7ef5729`. Feature mapped FULL run
`46114211575` and develop acceptance run `46115517155` are terminal SUCCESS;
develop used `exact_feature_certification`. The persistent feature branch is
`feature/robinhood-portfolio-manager-current`, worktree
`F:\AI\worktrees\ai-trading-bot-portfolio-manager-current`, origin
`https://github.com/callmedraken/ai-trading-bot.git`. Canonical develop remains
at the parent identity and retains all 17 pre-existing untracked artifacts.

B1-R was published at HEAD `91aa3119ed4f594f624b14e989982ec5cc496594` / tree
`1fb4cb0a917ee1c80b89b84c5278fde6dea27c4d`; feature FULL run `46123188954`,
attempt 1, was terminal SUCCESS. C1 preserves that parent and corrects the SEC
complete-submission filename, exact embedded-document identity, production
store and attempt boundary, evidence-backed authorization rechecks, and
bounded-time claims. The seven-lane FULL topology is unchanged.

C1 HEAD `edbf2df90791d735de6a3f409f7ce0d2de7cd056` / tree
`757e6383c73f4757d319f3f861a5af2b793149b2` passed feature FULL run
`46128814136`, attempt 1, including all seven broad lanes. C2 adds partial
socket-read byte accounting on timeout. It records yielded bytes in
`response_bytes_received`, leaves `response_bytes` at zero until complete raw
response custody succeeds, and performs no retry.

The SEC operational path is classified
`SEC_OPERATIONAL_FIRST_OBSERVED_PATH_READY_PENDING_EXACT_SUBJECT_AND_REVIEW`.
It can supply a first-observed operational fact only after an independent
issuer-to-security/share-class mapping and exact annual accession/document
are selected. Its `available_at` and `observed_at` must be no earlier than
trusted local receipt; an operational snapshot cutoff must be at or after
receipt. Historical reconstruction remains
`SEC_HISTORICAL_RECONSTRUCTION_BLOCKED`: SEC does not prove first-public
availability of an exact filing version, and CIK does not prove PM2C security
identity. Feed and Oldloads are potential later historical witness research,
not admitted sources. Sharadar remains
`SHARADAR_VERSION_OR_ENTITLEMENT_UNQUALIFIED`: public SF1 ARY/ARQ documentation
does not establish immutable prior-version retrieval or exact vendor
availability, and project entitlement/retention rights remain unresolved. No
SEC filing or Sharadar fact was requested; no provider subscription, login,
credential, endpoint, or account was accessed.

The parser and synthetic transport harness are in a module separate from the
real HTTPS transport and manual observation entrypoint. Production accepts
actual prepublication admission and separate effect-authorization record
paths, preserves their exact bytes, enforces the fixed create-once SEC file
store and canonical attempt, and rechecks source and authorization immediately
before one request. The request targets one original annual 10-K's named
`EX-101.INS` member: one GET, 10 MB response, 200 filing members, 100,000 XML
elements, 10,000 target-concept facts, 10-second blocking socket operations,
30-second elapsed budget, and no retry. The real issuer/security, CIK,
accession, fiscal context, and concept are not yet selected, so the plan is
not executable. A successful synthetic parse creates no PM2C `SourceFact`.
B1's existing fake-provider type restriction remains unchanged.

See [Architecture 152-PM2D-B1-R](architecture/152-pm2d-b1-r-real-fundamental-observation-readiness.md),
its [validation record](validation/arch152-pm2d-b1-r-real-fundamental-observation-readiness.md),
the accepted [B1 source contract](architecture/152-pm2d-b1-sec-sharadar-bounded-qualification-source.md),
and the [PM2D-A source assessment](architecture/152-pm2d-data-source-capability-and-provenance-qualification.md).

PM1 remains disarmed and preview-only; PM2A real account reads remain
unauthorized; Arch149 remains sealed. **Next step:** ChatGPT independently
reviews the exact C1 corrective diff, successful FEATURE and
PROSPECTIVE_DEVELOP admission, terminal mapped feature FULL evidence, and
zero-effect ledger. No develop integration or real observation is part of
this transition. The future operational observation gate requires exact real
subject and annual accession selection, independent issuer-to-security
mapping, final accepted source and current admission, and separate
short-lived effect authorization. Return the published HEAD/tree, exact
staged/published paths, admission evidence root, terminal workflow run
ID/attempt and seven lane results, focused checks, and all effect counters. No
local FULL should be run for this mapped checkpoint.

### Historical PM2B design checkpoint

PM2B remains the design authority for catalog families, point-in-time
semantics, provenance, availability, and AI/optimizer firewalls. It was
design-only and introduced no Python, tests, dependencies, provider, real
data, AI request, or execution path. Its records are retained as historical
predecessor design evidence rather than PM2C publication or acceptance.

### Historical PM1/PM2A checkpoint chronology

Architecture 152-PM1 is **SOURCE/CERTIFICATION ACCEPTED and FAST-FORWARD
INTEGRATED** at HEAD `0fc38b187169ce2322bca108751b4c05fe4078c0` / tree
`17426689d0eb381491654bb03caa28e0b29899ea`, direct parent
`e578a7ff0e128a1f9895a9df82296f73f550e9c5`. Feature source-gate run
`45954491120`, attempt 1, is terminal SUCCESS with source-static,
active-tests and all seven canonical FULL lanes green: 18,614 passed, 10
skipped, zero failures/errors, slowest lane broad-1 at 292.368 seconds under the
unchanged 300-second ceiling. No local FULL was run.

Develop source-gate run `45956617137`, attempt 1, is terminal SUCCESS at the
same source and reports
`DEVELOP_CERTIFICATION_REUSE=True REASON=exact_feature_certification`.
Active-tests, full-tests, certification-tests and certification-full were
skipped, so no duplicate FULL ran. PM1's source, certification and integration
gates are closed.

The implementation remains synthetic/disarmed. Account fingerprint and durable
history are isolated from the intraday product; deterministic risk evaluation
is independent of recommendations; plans are preview-only and cannot dispatch.
A narrow Arch149 adapter exposes only identity-verified, unadmitted research
signals and grants no performance or order authority. No real Robinhood
transport, OAuth, credential, broker/order effect, real AI-provider request,
production mutation or sealed 2024+ confirmation access was used or authorized.

The synthetic desktop remains runnable with:

```powershell
Set-Location 'F:\AI\worktrees\ai-trading-bot-portfolio-manager-current'
& 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe' -B 'src\trading_bot\portfolio_manager\application.py'
```

It binds synthetic PM state under `F:\AI\portfolio-manager-state\pm1`,
starts disarmed, and waits for the owner to click Start. It has no live
placement method.

PM2A is **SOURCE/CERTIFICATION ACCEPTED** at C3 HEAD
`834ac5b942eb436ab7d06809953f21f7a0f8fcc5` / tree
`0051affa15e94253a15a47c7d51e6f5b9ca625ec`, on
`feature/robinhood-portfolio-manager-current`. C3 mapped run `45984464000`,
attempt 1, passed source-static, active-tests, all seven canonical FULL lanes,
and source-gates. No local FULL was run. C4 feature docs-only run `45987424791`,
attempt 1, passed source-static and source-gates; other profiles were skipped.
C4 develop run `45988604704` was terminal FAILURE: `full-tests (3)` and
`full-tests (1)` passed shard verification but failed the 300-second hygiene
budget at 331.893s and 419.295s. `source-static` passed; `source-gates` failed
because FULL_RESULT was failure; active and certification profiles were
skipped. ChatGPT classified this as `DEVELOP_FULL_HYGIENE_BUDGET_FAILURE`, not
`PREPUBLICATION_COVERAGE_DEFECT`. The run was preserved and not retried.

C5 docs-only closeout HEAD `5235187cd2e2470dca7d20bd2c1e9fe6acdd4185` / tree
`59b065160a33005932fa0c27725b0bd17bd007cb` is a historical PM2A documentation
integration. Its feature run `45990380031` and develop run `45990688069` passed
source-static and source-gates; active, full, and certification jobs were
skipped. C6 and C6-C1 are historical docs-only corrections. C6 feature run
`45993792476` on HEAD `ea2522cbe1e4d8c12acd1d686ae9ad33fdfb812f` / tree
`f0a01f7b3f4db4e070efa986093c67e6be505873`, C6-C1 feature run
`45994722624`, and C6-C1 develop run `45995025872` all passed their
docs-only source gates with test/certification jobs skipped.

Historical PM2A documentation integration was C6-C2 HEAD
`e7f485be4ce2032586a97bbd5d689a516a7271be` / tree
`518c6de6cda4e85f1945a486ad43662e5e4bb9a8`. C6-C2 feature run
`45997466949` and develop run `45997969288`, both attempt 1, are terminal
SUCCESS with source-static/source-gates passed and active, full, and
certification jobs skipped. C6-C2 was integrated by local fast-forward plus
ordinary push; an initial merge invocation could not write `.git/ORIG_HEAD`,
then the same fast-forward succeeded with elevated filesystem access. No
update-ref integration was used for C6-C2. These documentation checkpoints
changed no PM2A implementation source; C3 remains the accepted implementation
source. No local FULL was run.

The public-reference review and complete source capability matrix are in
[Architecture 152-PM2A](architecture/152-pm2a-brokerage-observation-and-reconciliation.md).
Focused synthetic verification and all mapped CI outcomes are recorded in the
[PM2A validation plan](validation/arch152-pm2a-brokerage-observation-validation.md).
The current source query remains `ROBINHOOD_AGENTIC_BOUNDED` (selected account,
`placed_agent=agentic`, seven-day window, bounded pages/rows); account-wide open
orders and manual/external visibility are not proven. Actual provider schemas
remain unobserved, so order scope is
`CURRENT_PROVIDER_ORDER_SCOPE_UNQUALIFIED`. The prepared schema qualifier and
one-shot PM2A attempt API have not contacted the provider. The API requires the
literal accepted HEAD/tree and explicit account fingerprint, reserves immutable
attempt metadata before OAuth, and refuses repeated IDs, including
crash-reserved slots. If separately reviewed schemas cannot prove exhaustive
selected-account open equity orders, the stop classification is
`CURRENT_PROVIDER_ORDER_SCOPE_INSUFFICIENT`.

The observer rejects discovery with more than one eligible account even if the
supplied fingerprint matches one of them. The prepared attempt records counts
and the selected fingerprint, then stops without portfolio, position, quote,
or order reads. PM1 selection behavior is unchanged. No attempt/evidence
directory was created. No provider, OAuth, credential, account, or order read,
review, placement, cancellation, transfer, broker action, or production effect
occurred. Real read-only qualification remains **NOT YET AUTHORIZED**; PM1
remains disarmed, preview-only, and unable to dispatch.

At that historical PM2A checkpoint, PM2B was the next design milestone; the
current PM2B checkpoint is recorded above. Arch149 confirmation remains frozen
under its existing calendar-2026 contract.

### Prior terminal Arch151 evidence

Architecture 150 remains terminal and must not be rerun or mutated. Accepted
validation evidence remains at
`F:\AI\temp\arch150-g1-validation-cb197d11-9779-46e1-8179-81bab0c8806a\validation.json`;
report `22f752aa-5dc1-5e42-af29-1c7e2f921175`, SHA-256
`d3b637f410b9e8bf05d352e50efea95721151543ec6308fc270c804b5aa372c7`,
24 evaluated / 0 qualified / `NO_HOLDOUT_CANDIDATES`.

Arch151 foundation was accepted and integrated at
`39ce9cfe095acfef44e41ff4aa12ae371abd14ac` /
`b8216809237ce2c0826644d9534f82fd77ac763c`; feature FULL `45492979313` and
develop reuse `45495638481` are terminal SUCCESS, attempt 1. Foundation
predecessors `b6b398014ade93b13a4abda90634247dca822ada`,
`f442cf958dad07a740650a2d274894f0a0411633` and
`0a5b978a2f2f2a493a85257fda048910eb7d229d` remain immutable. Foundation
integration evidence: `F:\AI\temp\arch151-c3-integration-ac70162d6e8c4859a85e4474bf34ec8a`.
The prior coordination closeout was `5da3b755e4ce05e091c3dea2d9cae8f715fc8281` /
`b0bb3671595095e82505a5590637ff255ba06d47`.

The complete E1 evaluator is independently SOURCE/CERTIFICATION ACCEPTED and
FAST-FORWARD INTEGRATED at `60b5016d960eac6d916080ad298d98945d40358c` /
`b18af8f7bef3bc2a97900544ae82e6e034926932`. The four-commit chain is:
E1 `d3a42a4d763a3912e8601b19d6f240bae77cd952` (FULL `45557311951` SUCCESS),
E1-C1 `ecbb9e37d58572f49192992ece0a0b609d181d73` (preserved FULL
`45715017377` FAILURE: hosted fixture portability and hygiene), E1-C2
`f4aa349efb18f33bfc2fe034b19262d2e9778a8f` (FULL `45721239698` SUCCESS),
and E1-C3 (FULL `45739318873` SUCCESS, 18,526 passed / 10 skipped,
slowest lane 274.462 s; all seven hygiene gates passed). Each run was attempt 1.
Develop `45753356448`, attempt 1, is terminal SUCCESS with
`DEVELOP_CERTIFICATION_REUSE=True REASON=exact_feature_certification`,
`IDENTITY_STABLE=True`, `OVERALL=PASS`; duplicate FULL did not run.
Integration evidence:
`F:\AI\temp\arch151-e1-integration-accfe9527ef4433ba2ff585fd9363a23`.
Both local worktrees were reported synchronized and develop's untracked
inventory preserved. No accepted-custody read, real replay, trading credential,
provider, broker/order, or 2024+ access was performed during E1 implementation.

E1 docs closeout `3bb821aa77fbad7f3177e880d64234eb66b68ec4` /
`5e559e406d66f5a3bcbbab5155db0688b1c4c1d2` was accepted and integrated;
feature `45758271427` and develop `45758933931` were terminal DOCS_ONLY
SUCCESS, attempt 1. On that source, the first real observation consumed
attempt `0c0db97e-034c-4b59-97de-137d6e95359c`, invocation
`7fa05c82-d0e5-508f-8e77-b508071236d0`, at
`F:\AI\temp\arch151-intraday-development-evidence`.
Terminal FAILED / SOURCE_LOAD_FAILED / AuthorizationUnavailableError;
no years, source binding, report or candidate evaluation. Exact four artifact
hashes and lengths are preserved in the owning validation plan. Terminal
artifact SHA-256 `0e0e5d5bfe3e8f0c6d04159c6615bccaa92a067f7e54dde42ce3b2d254a088e2`.
No retry, rename, deletion or relocation. The failure does not establish a
negative strategy result. Its exact raising statement is not recorded.

E2 is independently SOURCE/CERTIFICATION ACCEPTED and FAST-FORWARD INTEGRATED
at `7c9c398cd82f917b51ce4ddba5488df937ea46ac` /
`d2e3067a285cc309fea6989f145203b08e86eabd`, direct parent E1 docs closeout.
Feature FULL `45769306690`, attempt 1, terminal SUCCESS: 18,538 passed,
10 skipped; seven lane hygiene gates passed, slowest lane 272.724 s.
Develop `45772034607`, attempt 1, terminal SUCCESS with
`DEVELOP_CERTIFICATION_REUSE=True REASON=exact_feature_certification`,
`IDENTITY_STABLE=True`, `OVERALL=PASS`; no duplicate FULL.
Integration evidence:
`F:\AI\temp\arch151-e2-integration-aa1b6fc58d784b9683b4883f45507c41`.
Both local worktrees were reported synchronized; develop inventory preserved.
E2 replaces the stage-filtered Arch150 discovery opener with full accepted
custody validation and Arch151-owned development authority. Source-history
identity is v2; frozen program/manifest/ledger/economics/thresholds unchanged.
Positive synthetic adaptation, projection and B5 replay passed; synthetic
history cannot issue real authority. The consumed E2 observation did execute
the corrected loader and returned source digest
`69537a0b180bf995f1e645bda5e7b25fc32f66d2f5c6104a407d57e764a7b40b`, then
failed before producing an annual artifact. Its evidence does not distinguish
an annual replay failure from annual-evidence construction failure, so it is
not an annual result or a negative strategy result. The consumed attempt is
`8721f462-ebeb-4f77-b5b7-4455e30cb599`, invocation
`89f2b597-3032-5502-bfd4-33608c3f234b`, at
`F:\AI\temp\arch151-intraday-development-evidence-e2-successor`; its exact
artifact hashes and terminal binding are preserved in the validation plan.
Typed sanitized source-load reasons and the exact published session population
check improve failure attribution. See owning architecture and validation for
the complete contract.

Continuation checkout: `F:\AI\worktrees\ai-trading-bot-arch151-intraday-walkforward-current`,
branch `feature/research-arch151-intraday-walkforward-current`; canonical develop
checkout `F:\AI\ai-trading-bot`. E3 mapped FULL run `45797405811`, attempt 1,
is terminal FAILURE only for broad-1 exceeding the 300-second budget (408.168
seconds); all cases passed or skipped without failures/errors. Preserve this
published red result. Failed job `139831883414` has timing artifact
`15106217058`. E3-C1 removes redundant fixture work while retaining representative annual
and campaign coverage; executable source is unchanged from E3. E3/E3-C1
are independently SOURCE/CERTIFICATION ACCEPTED and FAST-FORWARD INTEGRATED at
`5525013ffcfe3b28276651e0f4a1719265db0369` /
`a65232cbc1bcc341de1732a48066c24dbc98f8c6`. Direct parent E3 is
`cd3188ad5752f8437573be126a6a8564ffce0116` /
`3c95fc51f63302b898c90dd1756b3e07df1bde3e`. Feature FULL `45813360271`,
attempt 1, terminal SUCCESS: 18,549 passed / 10 skipped, zero failures or
errors, broad-1 248.642 s, slowest lane 262.682 s. Develop `45895966764`,
attempt 1, terminal SUCCESS: `DEVELOP_CERTIFICATION_REUSE=True`,
`REASON=exact_feature_certification`, `IDENTITY_STABLE=True`, `OVERALL=PASS`.
No duplicate FULL. Integration evidence:
`F:\AI\temp\arch151-e3-c1-integration-9e900aee67714f34ac1cbe44f7eab15b`.
Both local checkouts reported synchronized; develop inventory preserved.
Reprove live refs and exact source identities before any later transition.

[Architecture 151](architecture/151-intraday-walk-forward-campaign.md) and its
[validation plan](validation/arch151-intraday-walk-forward-campaign.md) own the
frozen manifest `4fdce706-4322-59e1-95d1-590a39e67978` / SHA-256
`8a5c89c55388e8ec5d0c6384a8f69ab99587a538bd0d868cb29a108717084083`.
Prior ledger `f7ce28f9-56b2-570b-8c83-62fbac38edbf` / SHA-256
`20dd765979f389504ccdf187589268a0d9d10a5d6479f1111738fc441a5a4269`:
29 prior trials, 32 current slots, effective count 64. E1 implements DSR,
realized-net PF, ZERO/BASE/STRESS diagnostics and adjusted-price benchmark,
canonical 480-record report, durable one-shot operator and authenticated
one-candidate development evidence. E1-C3 checks the exact chronological
fill-cash chain and frozen family entry caps. DSR unavailability remains
fail-closed for the full population, with per-slot reasons and descriptive
non-authorizing economic order. The completed E4 campaign verified DSR for
all 32 slots but froze no candidate.

The E1 and E2 public execution routes are permanently retired. E2
`--preflight-successor` and `--run-successor` now fail closed with
`SUCCESSOR_ATTEMPT_CONSUMED`, whether the old evidence root exists or not; they
do not check source identity, inspect either consumed observation, read
custody, or create a new attempt. The private execution engine remains
available only to synthetic tests. Do not retry, resume, relocate, or replace
either consumed observation. The exact E1/E2 evidence inventory, hashes,
terminal classifications, and preserved partial artifacts are in the owning
validation plan.

Accepted D1R source (do not reacquire):
`F:\AI\temp\arch150-d1r-offline-requalification-a46c4ad1-4287-4e51-8741-0316f784f1de`.
Dataset `ff5a3847-09c2-5902-b174-9e77eebf7d53` / SHA-256
`0070a5c0cfa5cd7878253d93bc0895b46da28d8b5e2a71395e66ce904b3f85dd`;
custody `21e121dc-a9da-538f-bc88-c15fe7ea7f50` / SHA-256
`5b6ac554eda73b588f2f6d664c14e5c7fca3c151966cb546c17621d0c7e6ad83`;
evidence `c31bb29d-3d53-5e2f-a01f-55a42ec96295` / SHA-256
`e58a6e5d95c44b33eb34311f705e6cc26982120689f98ddb207768dc304b4ecd`.
E2 accessed the accepted development source path and did not produce an annual
artifact; E3 did not access custody content. No later-period or holdout source
was read or replayed. The E3 work adds deterministic Decimal behavior and
sanitized attribution to the annual evaluator/operator, with synthetic-only
focused verification. It did not perform an offline diagnostic replay or issue
qualification evidence. E4 implements a fixed exact-source read-only preflight
and reusable development-only runner with separate smoke-only and full-campaign
modes. Preflight checks current local/live source refs, the consumed E1/E2
bindings, custody metadata and frozen manifest/ledger without reading custody
content or creating an attempt. Execution authenticates accepted 2016–2023
history once, binds a canonical attempt UUID, and records bounded progress and
sanitized failure evidence. Smoke replays the fixed 1,056-record 2019 diagnostic
population and cannot compose, report, qualify, or attest. Campaign requires a
complete smoke, then evaluates the full five-year 480-record population through
the existing simulator, composer, report serializer, attestation issuer and
authenticated evidence gate. Incomplete data never composes; catchable
interrupts preserve available partial rows, while a hard kill can leave a
consumed attempt unterminated. The exact terminal freeze status preserves
statistical unavailability versus a valid no-survivor result.

E4 candidate `1ca21d8e9af513198d442fb0b620de1c41dbc49b` / tree
`f44799ffe0ac43ee9a6b014fd1852e12c2cbb645` was evaluated by mapped FULL run
`45916194897`, attempt 1. It is preserved as terminal FAILURE only because
broad-1 exceeded the unchanged 300-second hygiene ceiling: 301.670 seconds,
with 2,449 passed, one skipped, and zero failures or errors. Failed job
`140236126413` retains timing artifact `15162936229`; source-static,
active-tests, and broad-2 through broad-7 passed. This red result is not
source acceptance.

E4-C1 shares the existing generated five-year history between the 480-record
annual regression and smoke/interruption/partial-year tests. The paired local
selection passed five tests in 69.90 seconds after fixture sharing versus
93.17 seconds before; all smoke population, trade, and equity assertions remain
active. No production source, authority, deterministic identity, timing weight,
lane membership, or budget changes. E4/E4-C1 are independently SOURCE/
CERTIFICATION ACCEPTED and FAST-FORWARD INTEGRATED at
`2a78c986855b6ccdcc13cf7b263977116ad13be7` /
`dcd3e0d06ebc1ae8cde3d8261163f08fc642e095`. Feature FULL `45919230088`,
attempt 1, terminal SUCCESS: 18,566 passed, 10 skipped, zero failures/errors;
broad-1 258.979 s, slowest lane 282.020 s. Develop `45925568595`, attempt 1,
terminal SUCCESS: `DEVELOP_CERTIFICATION_REUSE=True`,
`REASON=exact_feature_certification`, `IDENTITY_STABLE=True`, `OVERALL=PASS`.
No duplicate FULL. Initial local integration stopped before fetch, merge or
push on Git ls-remote exit 128; exact transport cause unknown. Preserve
`F:\AI\temp\arch151-e4-c1-integration-6419d7dfd16743e2b8bcfe52f2d7ba6f`.
Reconciled integration succeeded at
`F:\AI\temp\arch151-e4-c1-reconciled-integration-b443dc1cb77d47bb890760f06f5fcf92`.
Both local checkouts reported synchronized; develop inventory preserved.

No E4 CLI operation, accepted-custody content read, or real replay occurred
during implementation. Synthetic tests called `main` to verify argument
sanitization and a stubbed preflight display, and exercised the real attestation
issuer's synthetic-source rejection; none dispatched current-source preflight,
loaded accepted history, or evaluated a real candidate.
The E1 and E2 routes remain permanently retired, and E4 does not resume or alter
either consumed root. Annual summary artifacts still cannot reconstitute
qualification authority; no separate persisted replay reader is added. The
reviewed real preflight and combined campaign are now completed. The
terminal result is recorded in the owning validation plan; no further
Arch151 execution is authorized. All later-period, provider/credential,
broker, paper/live and production boundaries remain unchanged.
2024-2025 remains sealed until a single authenticated qualifying development
candidate and separate reviewed later-period authority; Jan-Oct 2026 remains
sealed until that same candidate's authenticated holdout PASS. Actual later-
period readers and result issuers are unavailable. A pure synthetic PASS is
not an authorization. Distinguish valid no-survivor, statistical unavailable,
incomplete and failed observation. No automatic trading authority follows.

Product priority is defined in [Project Status](PROJECT_STATUS.md): Arch151
valid qualification failure has triggered the separate Arch149-based AI
Portfolio Manager priority before further intraday strategy discovery. Preserve the Arch149 frozen confirmation boundary, account isolation
and all broker/live readiness gates. Portfolio framework preparation is not
authority to open partial 2026 confirmation or trade.

### Accepted real E4 development observation — terminal economic rejection

The exact integrated execution source was `6d420d20b7eab6689d84432ecfe38a68e5dbb367` / tree
`1cd21a0cb26b5f7781e84be2f7a2ea8b07eb8df2`. Coordination feature `45929687618` and develop
`45931754827` both passed DOCS_ONLY on attempt 1. The read-only preflight was
READY with no custody-content read or attempt creation; its SHA-256 was
`29d090873195d9648b602181aaa31da739e797672071ae70e3cde17cac4d1c68`.
The separately reviewed combined campaign consumed attempt
`9ac36178-906b-416b-ba5a-9df687595a3f`, invocation `7aa001a7-5a11-5cf6-9834-a5803b6e7f58`,
at `F:\AI\temp\arch151-offline-development\attempts\9ac36178-906b-416b-ba5a-9df687595a3f`. Terminal COMPLETED, no failure, exit 0,
elapsed 1597.9507193 seconds. Preserve the attempt; no retry or resume.

The source digest `69537a0b180bf995f1e645bda5e7b25fc32f66d2f5c6104a407d57e764a7b40b`
matches the earlier E2 loaded history. Validated-input digest
`01c4af0cfa114d4dd6cbe96a08c7e3832d23f25ed2def696b87f6bd4bc89dfed`;
source binding `bccf6de5-3721-5513-aae3-e759e2280616`. Smoke completed 1,056/1,056;
all five 2019–2023 years completed 96/96 each; 480/480 annual fold-cost records,
32/32 slots, 16 programs, all four families, no partial or failed replays.
DSR_VERIFIED (64 effective trials; 1,258 daily observations per slot).
Zero economically qualified slots and zero statistically qualified slots;
freeze `2d83bd02-a89a-5820-9f60-f81686f7ff1b` / fingerprint
`abdac525fb76414cee81dddc29b68145db39d966d39ffc5e77cb4e616bd3033a`:
`ZERO_CANDIDATES_NO_QUALIFIED_SURVIVOR`. No candidate or authenticated
candidate-evidence handoff exists. This is a valid completed negative strategy
result, distinct from consumed E1/E2 operational failures.

Run `217024eb-4904-51b8-b53e-f6100cad7a18`; report `3bf56887-7647-545d-8547-910d841f638a`;
selection-bias calculation `c5bffe91-b7ef-5c1a-9aa9-8be7bcc5ea23`;
population digest `a400a2d83c116c61fd4d52dff084621503d0c0e03821e8abe7ea9e9047c4fbc3`.
Source attestation `64374e05-38a8-5fb4-a068-54b99b04b999` is not candidate authority.

See the owning validation plan for exact artifact commitments and performance diagnostics.

Current implemented intraday runtime authority is [Architecture 148](architecture/148-tqqq-sqqq-runtime-pivot.md). It replaces further L43 checkpoint accretion as the application architecture while retaining accepted Architecture-147 safety components as reusable infrastructure and historical evidence.

V1 scope is fixed: intraday-only, long-only, at most one of TQQQ/SQQQ, QQQ as the primary direction reference, two completed-bar confirmation, no same-cycle inverse flip, and forced flat beginning five minutes before official regular-session close. The source-owned hard stop is 3.00% below the reconciled average entry fill and may never be widened. Live readiness requires proving exact full-position stop protection; a broker stop-market order is preferred and software independently treats threshold breach as mandatory EXIT.

Whole-share sizing uses a fresh price with cash, unleveraged buying power and
existing risk controls while retaining the <=$10 acquisition ceiling. A
quantity-denominated market order does not cap its fill price, so that ceiling
does not guarantee a <=$10 live fill. Exact whole-share risk authority and
provider stop capability remain live-promotion blockers.

The canonical full-pin source/runtime/public-reference adoption matrix is
`docs/validation/arch148-runtime-parity.md`. It records source functions,
licenses, local source/tests, adopted and declined behavior, and current
provider/backtest gaps. Its rule
`REFERENCE_FIRST_IMPLEMENTATION_REQUIRED_FOR_PROVIDER_OR_BACKTEST_SEMANTIC_GAPS`
requires source inspection and an explicit local rule before implementing a
provider or backtest semantic gap.

The Architecture 148 public-reference completion wave is independently
SOURCE/CERTIFICATION ACCEPTED and FAST-FORWARD INTEGRATED at
`6fb78af8c2e07d906629fd95277343eb6d54fde3` / tree
`01091cea96aa3aba6e5de8b88b64d8f722f116ba`, parent
`e11840c2ec7054c79183b3e33aee032f427d1a69`. Feature mapped FULL
`44673337558`, attempt 1, and develop `44679168920`, attempt 1, are terminal
SUCCESS.

The immutable `bb1a...` acquisition was requalified offline under the accepted
sparse v3 contract and independently accepted. Evidence:
`F:\AI\temp\arch148-b2-offline-requalification-b9a8babd-4869-466d-a81f-fae08fe2aae5\evidence.json`;
byte length 65688; SHA-256
`bdad3ab1f387617e2cef35644680e397c94d113f77f48cc242857151b352788d`.
Dataset: `0308b694-c718-5b1a-a51c-9fcc4516bb81` /
`0ba8b2437ef27a98fc48855aa8bb8d27ca3cdc0f2888e214305dde760686dbe0`.
Custody: `dbcced6a-b4cc-5d36-a33b-5e6df3d82baa` /
`93db9a9163cf445fdfd61abe68559196d240b09c1c9b70cdc0f7f452e3e8708b`.
It records 430 exhausted pages, observed counts 156379/156376/156376, missing
counts 17/20/20, 17 common missing slots, 23 union missing slots, zero fully
missing sessions, and zero new credential/network/provider/Robinhood/broker/
order/production/FINAL_HOLDOUT/baseline effects. The original acquisition
remains CONSUMED / NO RETRY.

Primary application reference: `siropkin/robinhood-ai-trading-bot@1a778749cfbe92c7ab9444b12e3cc73587533ade` (MIT). 148-A used its simple cycle shape as a reference while retaining the repository's stronger deterministic risk, MCP boundary and durable reconciliation contracts; its direct `robin_stocks` credential path, generic write retry, prompt-only risk limits and non-durable order handling were not adopted.

148-A is accepted/integrated at `df48cdd40bcd18f2bfdc65dda201cfe2b6f199bd` / tree `2e139bdd886ee6ce8f92da57cc11ea38f341114f`, parent `ec0f33b7c15521c1901d749d5a933564360448c7`. Feature mapped FULL `44411012023`, attempt 1, is SUCCESS. Develop `44423510835`, attempt 1, is SUCCESS with exact feature-certification reuse, stable identity and no duplicate FULL. Real provider calls and broker effects were zero.

### Architecture 148-B2-A-C1 accepted/integrated identity

B2-A-C1 is independently SOURCE/CERTIFICATION ACCEPTED and FAST-FORWARD
INTEGRATED at HEAD `0ebeaef7ea8ee83677d775fe66d037efa76c8cf1` / tree
`e16fe3aeec6a862c0d7ad7dd35e4171c1d3385e7`, direct parent
`298bba38cf61d506fec68cb7034fc66a58218078`. Feature mapped FULL run
`44507842755`, attempt 1, is terminal SUCCESS with source-static, active-tests,
source-gates and all seven canonical FULL lanes passing. Develop run
`44616906540`, attempt 1, is terminal SUCCESS with
`DEVELOP_CERTIFICATION_REUSE=True / exact_feature_certification` and
`IDENTITY_STABLE=True`; active tests and all broad/certification execution were
skipped on develop, so `DEVELOP_DUPLICATE_FULL=NO`.

The [Architecture 148 churn study](validation/arch148-churn-research.md) is
independently SOURCE/CERTIFICATION/EVIDENCE ACCEPTED and FAST-FORWARD
INTEGRATED at `be30617594e197f372438dba19d325fd8737b850` / tree
`57d5e80bd1933d59faf5da07f0ea293eac34b323`, parent
`0e82457d71e584dc526b5e377d7f90867e515879`. Feature mapped FULL
`44695628477`, attempt 1, passed all seven canonical lanes. Develop
`44698088183`, attempt 1, is terminal SUCCESS with no duplicate FULL.

Accepted report:
`F:\AI\temp\arch148-churn-research-731f1ee4-53a1-4bdf-8979-5eef493d9f4a\research.json`;
299,259 bytes; identity `19dcca18-7080-541d-9864-d730c68471e0`; SHA-256
`5baa7ef9e035f72428c623c798fb9653aa43339027c03e8e417d16c52e08aca8`.
It contains the fixed four variants × two cost models with OPEN_FULL plus
2016-2023 partitions, reproduces CONTROL baseline facts, records zero protected
effects and zero `FINAL_HOLDOUT` accesses, and selects no variant. Opposite
confirmation cut trade count substantially, but every variant lost money in
every calendar year at 10 bps; the descriptive first-place 30-minute cooldown
still lost about 99.4027% over OPEN. Preserve the acquisition,
requalification, baseline and churn evidence unchanged; `FINAL_HOLDOUT`
remains sealed.

The accepted OPEN sparse baseline is preserved at
`F:\AI\temp\arch148-open-sparse-baseline-e3e27c29-8a9d-41c5-9ac0-d89a1d4cb5d1\baseline.json`,
SHA-256 `38cbba9beae664c675670af1ad96e86a56df2a9060c6cb924c1ad51ea4f9b85f`.
It records 6,233 `ZERO_COST` and 6,235 `CONSERVATIVE_10_BPS` trades, 5,446 and
5,439 regime exits respectively, and `-99.998648%` conservative return. Those
baseline economics are rejected and must not be presented as churn results.

The separately reviewed predecessor B2-B attempt
`fd8aa437-c748-4d5b-a52f-1e58b2ca5953` remains CONSUMED / BLOCKED /
PAGE_LIMIT_REACHED / NO RETRY at
`F:\AI\temp\arch148-b2-fd8aa437-c748-4d5b-a52f-1e58b2ca5953`. It read
credentials once, made 64 provider attempts and received 64 successful QQQ
pages; TQQQ and SQQQ were not requested. QQQ raw/regular-slot/off-slot counts
were 162426 / 78057 / 84369 and unresolved intent was NONE. It remains immutable
incident evidence and cannot be resumed or retried.

Later attempt `bb1a784b-98d1-41fd-8d95-aa9fa463d5c9` at
`F:\AI\temp\arch148-b2-bb1a784b-98d1-41fd-8d95-aa9fa463d5c9` completed
acquisition with one credential read, 430/430 pages, zero unresolved
pagination intents and null end cursors for all three symbols. The original
dense B1 downstream qualification rejected the preserved data:

| Symbol | Pages | Raw bars | Observed B1 slots | Missing expected slots |
|---|---:|---:|---:|---:|
| QQQ | 148 | 349805 | 156379 | 17 |
| TQQQ | 141 | 331112 | 156376 | 20 |
| SQQQ | 141 | 328679 | 156376 | 20 |

The missing-slot sets share 17 timestamps and have a 23-timestamp union. This
attempt is CONSUMED / BLOCKED / `QUALIFICATION_BAR_COUNT_MISMATCH` / NO RETRY.
It remains separate from the fd8aa page-limit incident above.

The accepted C1 operator validates all raw bars before projecting only exact B1
regular-session slots into the normalized dataset, binds reconciled
raw/qualified/excluded counts in v2 evidence, enforces 192 pages per symbol /
576 total attempts, and spaces provider-request starts by at least 0.5 seconds.
Pacing grants no retry.

The first integration wrapper terminated after the successful push because it
combined `$ErrorActionPreference='Stop'` with redirected native Git stderr;
GitHub independently proved both remote refs at the accepted SHA and the
develop reuse run completed successfully. The subsequent read-only local proof
confirmed the clean accepted integration identity. Do not repeat that
stderr-unsafe wrapper pattern.

The offline requalification source at
`src/trading_bot/experiments/arch148_b2_requalify.py` and sparse simulator at
`src/trading_bot/experiments/arch148_sparse_backtest.py` are accepted in
`6fb78af8...`. The exact offline output above is independently accepted. No
provider retry is authorized. The fixed Architecture 148 churn comparison in
[`arch148-churn-research.md`](validation/arch148-churn-research.md) is now
accepted/integrated with the exact evidence recorded above. It rejects all four
tested variants economically and selects none. The active research boundary is
[`ai-strategy-discovery-campaign-v1.md`](validation/ai-strategy-discovery-campaign-v1.md).

Generation 1 is consumed and must not be rerun automatically. Accepted G1
identities are proposal set `b2b3cadc-c11d-5a7a-be0b-5a2e16b9b39b`, batch
`fd53330e-82ff-58a3-99b8-1818b9a0bbc0`, analysis
`d5ca081e-7490-5590-921d-10cee373d012` and terminal ledger
`68418f44-7db0-5080-a6bd-a956a928bd4a`. G1 consumed exactly 22 trials:
12 SHORTLISTED and 10 ECONOMICALLY_REJECTED.

Generation 2 is consumed and its confirmation evidence is visible. Accepted G2
identities are proposal set `c958130d-7594-535b-aa46-065525a10c46`, batch
`8c85731c-75dd-5a60-9456-10f237a6b0dd`, analysis
`821697c8-9917-5b76-b519-f81a2452d7f6` and terminal ledger
`e86be80c-562c-5243-bc56-9e4a9e4c9f6d`. It consumed six trials:
0 CONFIRMATION_PASSED and 6 CONFIRMATION_REJECTED. Do not rerun, mutate or
design another G2 candidate from the visible 2022-2023 results. Total campaign
trial count is 28. `FINAL_HOLDOUT` remains sealed.

The G1 selection-bias source is accepted/integrated at
`c26315b37c9b5fce355f323484f639368ce95749` / tree
`b3c678459062d24ae67f901b40cf7bc496ea6b87`. Feature run
`44881687514`, attempt 1, is SUCCESS with all seven mapped FULL lanes.
Develop run `44882606523`, attempt 1, is SUCCESS with exact feature
certification reuse and no duplicate FULL.

The real selection-bias observation is CONSUMED. Report
`854a1c95-f236-5dd7-9706-41035dd7fdf7`, SHA-256
`99e407ea3f646ecdd3ce17d9652356b1d0ee40bc0504d639841d2fcffd8bd708`,
is preserved at
`F:\AI\temp\ai-strategy-discovery-selection-bias-854a1c95-f236-5dd7-9706-41035dd7fdf7\selection-bias.json`.
All 12 G1 shortlists were SELECTION_BIAS_REJECTED and zero passed. The best
shortlisted DSR was about 0.918051 against the frozen 0.95 threshold; its
campaign PSR p-value was about 0.0139583 against alpha
`0.001785714...`. No G1 candidate may proceed to walk-forward. The observation
added zero strategy trials, replayed no G1/G2 strategy, read no G2 artifact,
performed zero provider/broker/production effects, and kept `FINAL_HOLDOUT`
sealed. Do not retry, tune or mutate the daily branch from these visible
results.

The frozen late-session intraday-momentum candidate
`OPENING_DRIVE_LATE_CAPTURE_V1` now has accepted/integrated source at
`370ebccf52a61e91979bc61efaac0001dd563be6` / tree
`49dbdc10401203422d5f8af7d4a936d9cd92a7f3`. Feature mapped FULL
`44888198054`, attempt 1, is SUCCESS. Develop run `44889299328`, attempt 1,
is SUCCESS with exact feature-certification reuse and no duplicate FULL.

The implementation kept the candidate single-shot and parameter-free, used the
explicit accepted XNYS schedule, preserved the existing 3% stop/safety/forced
flat semantics, and separated the inherited QQQ data-readiness veto from the
strategy's four frozen no-trade reasons.

The single real sparse OPEN observation is now CONSUMED and
`ECONOMICALLY_REJECTED`. Report
`42355698-d57e-5f6b-8347-6a752e5b4572`, SHA-256
`e6349ea0c7f1e1b09f165bede8c93b68fb6bc6168940fda0ae2270bf9079f19b`,
is preserved at
`F:\AI\temp\arch148-intraday-momentum-research-42355698-d57e-5f6b-8347-6a752e5b4572\research.json`.
ZERO_COST OPEN_FULL was about +24.96%, while CONSERVATIVE_10_BPS was about
-97.65%; median conservative annual return was about -39.86%. Seven of eight
calendar years were negative at conservative cost, opening-drive hit rate was
about 49.48%, and both leveraged target directions had negative realized mean
returns after cost. No confirmation or holdout action is permitted.

Do not retry, retime, threshold, filter, or mutate this Architecture-148
hypothesis from its visible result. The observation performed no provider/
broker/production effect, baseline replay, or `FINAL_HOLDOUT` access.
`FINAL_HOLDOUT` remains sealed. No earlier frozen unevaluated trading hypothesis remained after that closeout.
At that historical closeout, Architecture 150 became the primary intraday
research campaign and Architecture 149 was preserved as a secondary benchmark.
Current conditional portfolio-manager priority is recorded above and in Project Status.

Architecture 150 freezes a same-day, session-flat SPY/QQQ research campaign with
three typed families (noise-area/VWAP momentum, VWAP trend/reversal, and
opening-range/early-session breakout-reversal), a 24-program G1 budget,
frequency requirements, explicit ETF costs, complete trial-ledger
selection-bias correction, 2024-2025 untouched historical holdout, and a fixed
Jan-Oct 2026 recent-regime extension. No end-of-2026 wait is required. See
[Architecture 150](architecture/150-intraday-ai-day-trading-campaign.md) and
its [validation plan](validation/arch150-intraday-ai-day-trading-campaign.md).

The Architecture-150 foundation is SOURCE/CERTIFICATION ACCEPTED and
FAST-FORWARD INTEGRATED at HEAD `df504d166690ed7e6d2b67b5376565926b76baed` /
tree `9431111706710406baf336a7fd6a16f00a8db36a`. D1 data-custody source is now
SOURCE/CERTIFICATION ACCEPTED and FAST-FORWARD INTEGRATED at HEAD
`55f3bd8ae91c73c15e073c5a13e848f24c919bb9` / tree
`23daa9536fbf73f9c706e5e2661f6b3623dba1d3`. The original D1 publication
`a5bc7ec6bde787490ced14457d7b9bc83ed6e9f4` is preserved with terminal failed
run `44990894674` / `PREPUBLICATION_COVERAGE_DEFECT` for test-output-root
portability. Corrective feature FULL `44995353037`, attempt 1, is terminal
SUCCESS with all seven FULL lanes, active-tests and source-gates passing.
Develop run `44997145175`, attempt 1, is terminal SUCCESS with
`DEVELOP_CERTIFICATION_REUSE=True / exact_feature_certification`; no duplicate
FULL ran. The later docs reconciliation is
`50c5ed6204e909534778b07534fee7217117e47e` / tree
`f53588f74266b3ef054ca49f9ea5c8a29e24d630`; feature synchronization run
`45001962063`, attempt 1, is terminal SUCCESS.

The one real D1 acquisition is now CONSUMED / BLOCKED /
`MISSING_EXPECTED_SLOT` / NO RETRY. Attempt
`a8d5975b-a3e9-4917-a8a8-2809e191fa20` is preserved under
`F:\AI\research-data\arch150-intraday-data-custody\arch150-d1-a8d5975b-a3e9-4917-a8a8-2809e191fa20`.
It consumed one credential read and 306 provider requests. SPY exhausted 158
pages with 781,876 regular bars and 104 missing scheduled minutes; QQQ exhausted
148 pages with 781,865 regular bars and 115 missing scheduled minutes.
Duplicates/malformed bars were zero. Dataset
`6085afed-b870-59d7-9c0d-407db940777b` /
`70bf65d5b5c8726285215ed8337ae06bfaac8371cdb07b5dfd625ed800a96e23`
remains the blocked dense identity. Custody evidence identity is
`c0276e43-7533-5af4-9dbe-bb7e9095e693`; the retained evidence file SHA-256 is
`b83ced21f58cc1aa4731b2e72c1cf8cba4fb7d24378b0f206b303583bc658267`.
No normalized file was produced. 2024+, strategy P&L, holdout/extension,
Robinhood, broker, order and production effects were zero.

Do not retry or resume provider acquisition. D1R offline sparse-custody source
is SOURCE/CERTIFICATION ACCEPTED and FAST-FORWARD INTEGRATED at HEAD
`fd0eb9073d55cbb5b1dba2f0fb35ce00317855c1` / tree
`bec66738a1796a0300b1dd5bbd503675203eb506`, direct parent
`f376f10840ab40723af6393b9918fab67702a073`. Feature mapped FULL
`45012246733`, attempt 1, is terminal SUCCESS with all seven canonical FULL
lanes passing. Develop run `45015293875`, attempt 1, is terminal SUCCESS with
`DEVELOP_CERTIFICATION_REUSE=True / exact_feature_certification`,
`IDENTITY_STABLE=True`, `OVERALL=PASS`, and no duplicate FULL.

The first real **offline** D1R invocation is now CONSUMED / BLOCKED /
`OUTPUT_CREATE_FAILED` / NO AUTOMATIC RETRY. Requested output was
`F:\AI\temp\arch150-d1r-offline-requalification-e8040deb-1fb6-4a4d-9ac6-05f5c4f6349d`;
the process exited 21, the directory was not created, and there is no partial
output. The retained D1 artifact hashes and SPY/QQQ raw filename counts remained
unchanged. New credential/network/provider/Robinhood/broker/order/strategy-P&L/
holdout/extension effects were all zero.

Do not invoke the original D1R observation unchanged. D1R-C1
output-boundary correction is SOURCE/CERTIFICATION ACCEPTED and FAST-FORWARD
INTEGRATED at HEAD `3afcc5b24845c6ed4e50dd4bbfe34d9deb076d5d` /
tree `f393498786060a6e55eed545f6fdd44ecea49f4d`, direct parent
`b769a3a5565bdbda18b0fd2ff76eadbd7b1f6071`. Feature mapped FULL
`45087988867`, attempt 1, is terminal SUCCESS with all seven canonical FULL
lanes passing. Develop run `45100486575`, attempt 1, is terminal SUCCESS with
`DEVELOP_CERTIFICATION_REUSE=True / exact_feature_certification`,
`IDENTITY_STABLE=True`, `OVERALL=PASS`, and no duplicate FULL.

The correction canonicalizes/returns the validated production output Path,
rejects control characters before any create attempt, and adds the CLI:
`python -B -m trading_bot.experiments.arch150_d1_requalify --output-directory <output-directory>`.

The corrected real offline D1R observation is now CONSUMED and sparse custody
is ACCEPTED. Output:
`F:\AI\temp\arch150-d1r-offline-requalification-a46c4ad1-4287-4e51-8741-0316f784f1de`.
Dataset identity `ff5a3847-09c2-5902-b174-9e77eebf7d53`, semantic SHA-256
`0070a5c0cfa5cd7878253d93bc0895b46da28d8b5e2a71395e66ce904b3f85dd`.
SPY has 781,876 observed / 104 missing scheduled slots; QQQ has 781,865 /
115. Common missing is 64, union 155, across 9 affected sessions, with no fully
missing sessions. The original consumed D1 attempt remains unchanged and every
new protected-effect counter is zero.

Architecture-150 D2 sparse-replay semantics are SOURCE/CERTIFICATION ACCEPTED
and integrated at HEAD `6fb7b128d83b4846b384bb1709f0ee4e724d173d` / tree
`7fd5ea4c516a7f97ce2f5227befd4dbef4e3a802`. Feature FULL run `45113622952`,
attempt 1, is terminal SUCCESS. Develop run `45122666587`, attempt 1, is
terminal SUCCESS with exact feature-certification reuse; no duplicate FULL ran.

The source-owned G1 population is frozen under schema
`arch150-g1-pre-evaluation-population/v2`, manifest
`7e179cbc-18cf-59ce-9116-899cc876ece0`: exactly 24 ordered one-minute trials,
eight per family, with 12 SPY and 12 QQQ. Each slot binds program, symbol and
resolution; identical programs on different symbols are separate trials. A
valid unique STRESS discovery trial with any trade is shortlisted; discovery
economic metrics and BASE/ZERO diagnostics do not decide advancement.

All 24 real G1 discovery trials are consumed and all advanced under the
frozen mechanical rule. Subsequent V1 validation was accepted and consumed with
zero qualifiers as recorded above. 2024+ remained unopened.

Architecture 149 defined the frozen independent research family:
`MONTHLY_CROSS_ASSET_DEFENSIVE_ROTATION_V1`. It has exactly one candidate,
uses the accepted SPY/QQQ/IWM/EFA/EEM/TLT/GLD/PDBC daily universe, ranks fixed
21/252-session momentum only at month end, holds the top ETF only when its score
is strictly positive, otherwise holds CASH, and executes at the next session
OPEN under the accepted A147 BASE/STRESS costs. 2016 is warmup and 2017-2023 is
exploratory. 2024-2026 data remains forbidden until a separately frozen
confirmation step.

Source is accepted/integrated at
`57087af056767c59ee48e3edb86063ac4f20c10d` / tree
`da80c3f560d54d959822f7716a50fc45c3ead716`. Feature FULL
`44914956812`, attempt 1, is SUCCESS. Develop run `44935678418`, attempt 1,
is SUCCESS with exact feature-certification reuse and no duplicate FULL.

The one authorized exploratory replay is CONSUMED / `EXPLORATORY_CANDIDATE_ONLY`.
Report `8a3d7c3a-d2f9-5f10-91e6-ba06c3935d84`, SHA-256
`69f941721aaba736cef45b80543f7a238a30dcdb74f03c046c3fc01aabb5dbcf`,
records STRESS full return about +82.59%, 8.98% CAGR, 28.15% maximum drawdown,
0.5183 Sharpe, 10.86% median annual return and 6/7 positive years. It consumed
one strategy trial and performed zero protected effects.

The separately frozen confirmation contract is
[Architecture 149 2024-2026 confirmation](validation/arch149-monthly-defensive-rotation-confirmation.md).
It preserves the exact strategy, starts a fresh $100,000 confirmation portfolio,
uses pre-2024 A147 history only as signal warmup, and evaluates exactly calendar
2024-2026. No partial-2026 peek is allowed. Source-only confirmation support is
deferred to the portfolio roadmap; real acquisition/replay waits for completed
2026 data.

The prior single-candidate research design remains in
[`arch148-intraday-momentum-research.md`](validation/arch148-intraday-momentum-research.md).
It tests one OPEN-only late-session intraday-momentum architecture: QQQ's
first-half-hour return from the previous regular-session close fixes the
session direction; at most one TQQQ/SQQQ position may enter at official
close minus 35 minutes and then remains held until the 3% hard stop, a safety
exit, or forced flat at close minus 5 minutes. There are no EMA/VWAP/RSI
regime exits, cooldown variants or same-session re-entry. Source is now
accepted/integrated; the single real OPEN evidence observation remains pending.
Preserve `FINAL_HOLDOUT` and all provider/broker boundaries.

Architecture 148-B1 is accepted/integrated at `68b9526f022458cbcdd4f25ff268e0de7c56e562` / tree `85e4830e71cb3b0ab5e85c5da9131f90f7ce575b`. The initial B1 commit `70b0a8de5cb3b2cf4fb826352b6ada3650c57614` remains preserved with green run `44432367772` but was exact-source rejected; corrective C1 closed the reviewed defects. Feature mapped FULL `44438409583`, attempt 1, is SUCCESS. Develop `44465681331`, attempt 1, is SUCCESS with exact feature-certification reuse, stable identity and no duplicate FULL. The operator integration report records both canonical F: worktrees and both live refs at the exact accepted HEAD/tree and clean; the feature checkout required no catch-up.

The earlier B2-B attempt is CONSUMED / BLOCKED / PAGE_LIMIT_REACHED / NO
RETRY. The later acquisition remains CONSUMED / BLOCKED /
`QUALIFICATION_BAR_COUNT_MISMATCH` / NO RETRY under dense B1, while its
immutable raw observations are independently accepted through sparse offline
requalification. B2-A-C1, the public-reference completion source, and the churn
research checkpoint are accepted/integrated. Churn evidence rejects CONTROL and
all three fixed churn-reduction candidates at conservative costs; no strategy
variant is selected. No new provider or credential read, Robinhood/broker,
production, Q63 or `FINAL_HOLDOUT` action is authorized here.


### Architecture 148-B1 accepted intraday identity

- HEAD: `68b9526f022458cbcdd4f25ff268e0de7c56e562`
- tree: `85e4830e71cb3b0ab5e85c5da9131f90f7ce575b`
- direct parent / initial B1: `70b0a8de5cb3b2cf4fb826352b6ada3650c57614`
- integrated develop predecessor: `9237cfe5fe3b617e00f7b2885ab171eb06542334`
- original B1 mapped FULL: `44432367772`, attempt 1, terminal SUCCESS, preserved but exact-source rejected
- C1 mapped feature FULL: `44438409583`, attempt 1, terminal SUCCESS
- develop source gate: `44465681331`, attempt 1, terminal SUCCESS
- develop reuse: `DEVELOP_CERTIFICATION_REUSE=True / exact_feature_certification`
- develop identity: `IDENTITY_STABLE=True`
- duplicate develop FULL: NO
- OPEN interval: `[2016-01-01, 2024-01-01)` UTC
- symbols: `QQQ`, `TQQQ`, `SQQQ`
- timeframe / basis: `5Min` / `ALPACA_ALL_ADJUSTED_INTRADAY_PRICE_V1`
- schedule identity: `4fe981d0-34ef-57be-a7d1-ffd017460bf5`
- schedule SHA-256: `a33be70499cdafbfa21f45a04c854ab834425807b6c0314814b7442749aa2bad`
- source/provider/credential/broker/production/FINAL_HOLDOUT effects during B1: zero
- Earlier B2-B attempt `fd8aa...`: CONSUMED / BLOCKED / PAGE_LIMIT_REACHED / NO RETRY.
- Later attempt `bb1a...`: acquisition complete; original downstream qualification CONSUMED / BLOCKED / `QUALIFICATION_BAR_COUNT_MISMATCH` / NO RETRY. Its immutable raw observations are independently accepted through sparse offline requalification evidence `bdad3ab1f387617e2cef35644680e397c94d113f77f48cc242857151b352788d`; no provider retry is authorized.

The accepted B1 simulator executes signals no earlier than the next bar open, then activates the 3% hard stop immediately for the entry bar. Entry-bar gap-through exits use the bar OPEN; otherwise a LOW breach exits at the stop threshold. The shared `live_runtime.strategy.confirmed_regime_exit` rule is used by both runtime and research paths. Dataset and custody schemas are v2 and bind the Architecture-148 schedule commitment separately from the Architecture-146 session-date authority.

### Architecture 148-A accepted runtime identity

- HEAD: `df48cdd40bcd18f2bfdc65dda201cfe2b6f199bd`
- tree: `2e139bdd886ee6ce8f92da57cc11ea38f341114f`
- direct parent: `ec0f33b7c15521c1901d749d5a933564360448c7`
- feature mapped FULL: `44411012023`, attempt 1, terminal SUCCESS
- develop source gate: `44423510835`, attempt 1, terminal SUCCESS
- develop reuse: `DEVELOP_CERTIFICATION_REUSE=True / exact_feature_certification`
- develop identity: `IDENTITY_STABLE=True`
- duplicate develop FULL: NO
- provider/broker effects during source work/review/integration: zero
- live-promotion blockers retained: whole-share protective-stop compatibility under the <=$10 canary; approval-ID linkage for approval-originated provider orders

`ARCH148_A_CONNECTOR_INTEGRATION_MECHANISM_DEVIATION` is preserved: ChatGPT used a leased non-force GitHub ref fast-forward for develop in the connector-only review turn instead of the preferred admitted local `merge --ff-only` + ordinary push. Exact accepted history/tree and develop reuse were preserved; do not treat this as the normal integration method.

Canonical feature worktree: `F:\AI\worktrees\ai-trading-bot-live-prototype-current`.
Branch: `feature/robinhood-live-prototype-current`.

Preserved accepted/integrated L43-Q1 predecessor identity:
- L43-Q1 HEAD: `05f4c4700f82c3d40c83f474c3cf614573d48091`
- tree: `70aec1c51e63705a68d6710cc3448ac994227e46`
- direct parent: `f38c3079d83f5e9773280fe36e43a4d9d9d3c76d`
- feature mapped FULL: `44260469616`, attempt 1, terminal SUCCESS
- develop exact-source run: `44264566809`, attempt 1, terminal SUCCESS
- develop reuse: exact feature certification
- develop identity stability: `IDENTITY_STABLE=True`
- duplicate develop FULL: NO
- accepted RHC4-C2 ancestor: `4f560a74b04ecba85c7b312364a9e4e7b30e57b6` / `b422ef66d88b184bdbe12788546e6b2ffd083846`

Preserved predecessor evidence:
- original RHC4 `2f4f50a1df44c261d172f55bc540b635d637cbd9` / tree `558e2f8c1f930d3f15810dea3f01a92ca20fdc24`; mapped run `44181143712` terminal SUCCESS but exact-source rejected;
- RHC4-C1 `f3f44e00ec17279ea74445df2b7a680875745f7b` / tree `8dac42fa7039bde8fdb6f6bdd63eeaf432cb049a`; run `44192574584` terminal FAILURE / `PREPUBLICATION_COVERAGE_DEFECT`;
- first clean C2 admission `F:\\AI\\temp\\ai-trading-bot-checkpoints\\arch132-r3n-prepublication-admission\\source-gate-20261118T012223.701722Z\\report.json` remains `PREPUBLICATION_ADMISSION_PORTABILITY_DEFECT`;
- final C2 admission `F:\\AI\\temp\\ai-trading-bot-checkpoints\\arch132-r3n-prepublication-admission\\source-gate-20261118T013037.569843Z\\report.json` passed FEATURE and PROSPECTIVE_DEVELOP with stable identity, `2692 passed, 1 skipped`, Ruff PASS and diff PASS.

RHC4-C2 is production composition source, not real-order evidence. Its default production exact-plan authorizer denies. Start/Stop does not grant trading authority. Pending bound orders settle through accepted RHC3P factual reads first. The serialized lifecycle interlock orders Stop against the transition into ENTRY placement, SELL nonplacing review and SELL placement. Import, construction and help remain effect-free. No RHC4 real Robinhood/OAuth/browser/MCP/Alpaca/review/place/cancel action occurred during source implementation, certification or integration.

### Q62 retained state and consumed observation

Q62 source was accepted/integrated before RHC4. Its create-once local state is consumed and must never be reinitialized:

- journal: `F:\AI\arch147-q62-live-state-v1\durable-state.jsonl`
- bytes: `806`
- SHA-256: `21F6C07273226D467F85CC8B86DED104B58A94C456E81C67521F94D8CC7CA7D1`

The separately reviewed protected read-only Q62 observation was consumed successfully:

- status: `READY_FOR_L43_PROTOTYPE_READ_ONLY`
- reason: `Q62_READ_ONLY_PREREQUISITES_PROVEN`
- evidence: `F:\AI\temp\arch147-q62-tiny-live-readiness-ecd813dcb93f4f66bb7f9adce592ed42\evidence.json`
- bytes: `11,663`
- SHA-256: `4D08EB505651CEB551BF6D94BB87960F14940925263D3E682B62610A063FC9C9`
- PROVEN: SOURCE, CONFIGURATION, ACCOUNT, CAPABILITY, OWNERSHIP, BUDGET, SESSION, SIGNAL_INPUTS, RECOVERY
- Robinhood reads: get_accounts=1, get_equity_positions=1, get_equity_orders=1
- Alpaca snapshot/provider call: 1
- review/place/cancel/other Robinhood calls: 0
- provider mutations: 0
- live readiness: false
- trade authority: false
- disposition: `CONSUMED / NO AUTOMATIC RETRY`

RHC2 remains `CONSUMED / PASS / NO RETRY`. RHC3 retained account-wide-all-agents order-scope evidence remains immutable and operationally required. Q62 evidence is an anchor, not current effect authorization.

### Workflow deviations preserved

`RHC4_C2_PREPUBLICATION_ATOMICITY_DEVIATION` records that C2 was published as two unpublished commits (`7dfd693b...` then `4f560a74...`) in one push rather than one atomic checkpoint commit. Do not rewrite published history.

`RHC4_C2_TRANSITION_WORKFLOW_REGRESSION` records that the first ChatGPT integration guard Boolean-tested `git diff --quiet` stdout and falsely stopped a clean worktree. The broader transition also failed to follow existing procedure in several places: remembered-path use instead of same-block worktree discovery/reproof, incomplete first cleanliness proof, unsafe native stderr handling, output parsing before native-exit classification, missing canonical-origin/final-cleanliness proof, oversized generated PowerShell, incorrect delegation of the tiny docs closeout, delayed automatic continuation, failure to batch the known L43-Q1 design freeze with the closeout, and an initially missed stale current Q62 summary. The diagnostic re-established exact clean state before successful integration. These are workflow/procedure regressions, not source defects.

`RHC4_C2_CLOSEOUT_C1_DOCS_HYGIENE_DEFECT` preserves direct docs run `44239165344`, attempt 1, terminal FAILURE. Its only source-static defect was one new blank line at EOF in each newly added L43-Q1 document; canonical FULL/active tests were skipped. The run is immutable evidence and is not rerun unchanged.

`ARCH150_D1_INTEGRATION_GIT_FUNCTION_RECURSION` records a later ChatGPT-generated integration wrapper that defined `function Git` and then invoked `git` inside it. PowerShell command resolution is case-insensitive, so the wrapper recursively resolved to itself and stopped with `CallDepthOverflow` before integration. No source/protected effect or partial integration occurred in that failed wrapper. The subsequent Codex-owned transition followed the established simple Git procedure and integrated D1 successfully. Do not use case-colliding native-command wrapper names.

For future Windows/Git operator commands, follow the normative sections of `docs/AI_DEVELOPMENT_WORKFLOW.md` rather than reconstructing the rules from memory. The checkpoint owner follows mapped CI to terminal: ChatGPT for ChatGPT-direct publications and the same implementing Codex session for delegated publications. Codex may correct fully reproduced bounded/mechanical failures as separately named descendants with affected focused verification and fresh admission. Do not hand back merely because CI is queued/in progress, and do not use a separate waiting/polling agent.

- discover or re-prove the exact worktree; never derive it from a branch name;
- normalize filesystem identity with `Resolve-Path`;
- use porcelain/status arrays for tracked/index cleanliness and explicitly account for untracked state when the contract requires it;
- check `$LASTEXITCODE` before parsing potentially absent native output;
- never Boolean-test stdout from an exit-code-only native command;
- use the reviewed wrapper or stderr-safe `Start-Process -Wait -PassThru` pattern when native stderr is expected;
- verify the canonical origin before network/ref mutation;
- re-prove final branch/HEAD/tree/tracked/index/untracked state;
- after any STOP, re-establish the complete gate before continuation.

### L43-Q1 consumed observation and next boundary

`ARCH147-L43-Q1_QUALIFICATION_PREFLIGHT_SOURCE` is accepted/integrated at `05f4c4700f82c3d40c83f474c3cf614573d48091` / tree `70aec1c51e63705a68d6710cc3448ac994227e46`. Feature run `44260469616` is terminal SUCCESS with mapped FULL; develop run `44264566809` is terminal SUCCESS with exact feature-certification reuse and no duplicate FULL. The registered slug remains `arch147-l43-qualification-preflight`, with protected read-only `preflight` and `execute=None`.

The separately reviewed Q1 preflight was invoked once after exact local/remote reconciliation and is now CONSUMED / BLOCKED / NO AUTOMATIC RETRY:
- evidence: `F:\AI\temp\ai-trading-bot-checkpoints\arch147-l43-qualification-preflight\preflight-20261118T091033.372793Z\report.json`
- source admission: PASS before/after
- identity: stable at the accepted Q1 HEAD/tree
- qualification: `BLOCKED / QUALIFICATION_INDETERMINATE`
- accepted source/config/binding/Q62 journal digests: present
- L43 durable-state snapshot/fresh pre-effect facts/challenge: absent
- review/place/cancel/broker mutation/L43 state mutation/Q62 mutation: all 0
- provider/credential call counts: `null` (unknown, not proof of zero)
- retry: `NOT_AUTHORIZED`

Source review narrows the failure to the interval after accepted source identity and before a durable-state snapshot was bound. The production snapshot path is fixed at `F:\AI\arch147-l43-live-state-v1\durable-state.jsonl`; the reader requires an already provisioned journal plus lock and never initializes them. The repository currently has no production L43 provisioning command; only test/fake fixtures create L43 state. The sanitized observation does not expose the underlying exception, so do not claim a specific host cause such as a missing journal or lock without separate evidence.

The former standalone L43 state-provisioning/diagnostic successor is superseded as the immediate milestone by Architecture 148. If the new application reuses L43 durable-state machinery, provisioning/migration must be owned by the new complete runtime dependency closure. No second Q1 preflight, Robinhood/Alpaca protected observation, review/place/cancel, Q63, or `FINAL_HOLDOUT` access is authorized by this handoff.

## RHC3 production order-scope admission

RHC3 consumes, but never mutates or retries, the exact retained A2/RHC2 chain:

- A2 semantic evidence: `F:\AI\temp\arch147-agent-initiated-runtime-proof-eligible-0d1c18123732442c9d3f4a14ba0f43e6\evidence.json`, SHA-256 `34483478bbf6430ff0e9a139cd33cdc8837be22eff100e53e0f6b2fdde46c3f1`
- RHC2 registered report: `F:\AI\temp\ai-trading-bot-checkpoints\arch147-rhc2-robinhood-order-scope-successor-observation\preflight-20261117T064253.945488Z\report.json`, SHA-256 `25873f5cdbb509b7a93b80a0644affb01e784c1bf0145a1aca20222ac71f56e9`
- RHC2 observer evidence: `F:\AI\temp\arch147-agent-initiated-runtime-partition-3f05ea6fed42440293ea3d58a1af5074\evidence.json`, SHA-256 `99bca426cba77589055be6dc826cf0d72884c51e40f493c19b55625ac2bf2189`
- reconstructed inner B2 evidence SHA-256: `7016e9c9f5a8b52e996a56e5eab4ee89ce993b967513109c09af23aa5e693fc3`

A2 authenticates the hosted `agent_initiated` filter semantics. RHC2 remains CONSUMED / PASS / NO RETRY and supplies four exhaustive runtime-consistency reads (`ALL_BEFORE`, `TRUE`, `FALSE`, `ALL_AFTER`), all zero-row. The zero-row observation is not treated as a non-empty semantic witness.

The RHC3 loader reads only those fixed paths, validates exact file hashes before parsing, rejects symlink/reparse/path/object drift, duplicate or unexpected JSON structure, wrong counters/status/source identity, and any write/other-tool attempt. It reconstructs and verifies the inner B2 digest and requires the retained RHC2 account fingerprint to equal canonical Q62.

At each current L43 proof request, the production verifier reauthenticates the evidence chain rather than caching authority. It accepts only the exact current unfiltered `{"account_number": ..., "symbol": "SPY"}` query, proves the account-number hash matches the Q62-bound fingerprint, requires bounded positive page count, bounded nonnegative row count and exhausted pagination, and returns an `ACCOUNT_WIDE_ALL_AGENTS` scope proof whose evidence digest binds all four retained evidence hashes plus current account/query/page/row/exhaustion facts. Any failure returns no proof and preserves `ORDER_SCOPE_UNPROVEN`.

The historical RHC2 field `production_order_scope_authority=NOT_GRANTED` remains unchanged; RHC3 is the separately source-reviewed consumer that grants only this narrow pre-effect order-scope prerequisite. It does not grant review/place/cancel authority or any generic live-effect permission.

The three pinned evidence files are now operational runtime dependencies. Do not clean, move, rewrite, regenerate, or replace them. Q63 must include their exact custody, backup/restore and hash verification in the final delivery package. Loss or mutation is fail-closed availability loss, not authority to recreate evidence.

## L41R1 consumed observation and L41R2 source successor

The consumed predecessor is recorded exactly as
`L41R1_REAL_OBSERVATION=CONSUMED_BLOCKED_NO_RETRY`. Its preserved evidence is
`F:\\AI\\temp\\arch147-l41r1-schema-observation-f5b81e5f60dc40c280f53007d1db2b52\\evidence.json`,
SHA-256
`2b62f54076fdfd34aa3eb799ed563701f8eadafe8877b25590f88fe72147160f`,
length `1130` bytes. It recorded source admission PASS, OAuth scope entry `1`,
MCP session-open `1`, `tools/list=0`, empty schemas, reason
`L41R1_MCP_SESSION_OPEN_FAILED`, and zero MCP tool, account, tradability,
position, order, portfolio, quote, review, placement, cancellation and
other-tool attempts.

The exact cause was `_create_windows_oauth_factory()` installing
`_forbid_interactive_oauth`; the MCP OAuth SDK required an authorization-code
flow and invoked that blocker. The classification is
`L41R1_INTERACTIVE_OAUTH_FORBIDDEN`, not a generic browser/environment failure.
The attempt also exposed an upstream OAuth/MCP traceback-output defect because
provider/OAuth traceback text reached the terminal despite sanitized evidence.

`L41R2_INTERACTIVE_SCHEMA_DISCOVERY` is the separately named additive successor
with evidence schema `arch147-l41r2-interactive-interface-observation/v1`. It
preserves the corrected schema facts, permits one reviewed interactive OAuth
authorization when persisted state is insufficient, suppresses upstream
provider/OAuth output, and invokes only bounded `tools/list`. Evidence records
browser launches as `0` or `1`, native credential read/write counts as `null`,
and `SDK_MANAGED_NOT_INDIVIDUALLY_COUNTED`; raw URLs, callback values, tokens
and provider text are never persisted. A successful result is
`CAPTURED_FOR_REVIEW` only and grants no live readiness, broker authority, Q62
acceptance or order authority. At that historical checkpoint, Q62 remained NOT
RUN and blocked pending L41R3 classification.

The L41R2 observation is CONSUMED / BLOCKED / NO RETRY. Its immutable evidence
is
`F:\\AI\\temp\\arch147-l41r2-schema-observation-9a504f5e26b9414998cea287ee13936a\\evidence.json`,
SHA-256
`66C3E5C32A0FD575490B3219AEA7DE2ECCEE65C4E5FDEFF6EB339B9B963FA751`, length
`1386` bytes, reason `L41R2_SCHEMA_MALFORMED`. Source HEAD/tree were
`d421562703d6bae92b14afdcc1b3defcc595dbc8` /
`b0ca242360b1cfe17222c4b56e95198219eee4be`; FEATURE and
PROSPECTIVE_DEVELOP admission both passed. It recorded one OAuth scope-entry
attempt, one MCP session-open attempt, one browser launch, and one `tools/list`
attempt. All prohibited MCP tool/account/tradability/position/order/portfolio/
quote/review/place/cancel/other-tool counters were zero. Native credential
read/write fields are `null` with accounting
`SDK_MANAGED_NOT_INDIVIDUALLY_COUNTED`; automatic retry is FORBIDDEN.

The failure is classified from source/client-model comparison: the source
extracts the wire spelling `inputSchema`, while MCP SDK v2 Tool objects expose
the Python attribute `input_schema`. The consumed evidence does not record the
raw provider object type. L41R3 is the additive successor with evidence schema
`arch147-l41r3-mcp-v2-interface-observation/v1`; it normalizes only name,
description, schema and pagination cursor before using the existing fail-closed
sanitized parser. Its success remains `CAPTURED_FOR_REVIEW` only, with zero
tool calls and no Q62, live, broker, order, numeric-rule or `FINAL_HOLDOUT`
authority. At the L41R2 source-acceptance checkpoint, real L41R3 had not yet
run; a later consumed observation followed that checkpoint.

The first unpublished L41R2 prepublication admission is preserved at
`F:\\AI\\temp\\arch147-l41r2-source-admission-2804bb15b8ec49eab4f0ac8ac0fe0a0f` and is classified
`PREPUBLICATION_ADMISSION_TOPOLOGY_DEFECT` / `FULL_LANE_DUPLICATE_BASENAME`.
The enlarged FULL inventory placed `tests/portfolio/test_models.py` and
`tests/rebalancing/test_models.py` together in broad-5, producing the required
`40 != 39` basename invariant failure under the current pytest topology. No
authority failure occurred, `IDENTITY_STABLE=True`, and `PROTECTED_EFFECTS=0`.
This was not a product-source failure, published red source, coverage defect,
or GitHub CI failure. The corrected admission subsequently passed, the amended
candidate was published as
`235118f70b7c7039055e9fea45ccf27df46671a0` / tree
`972004101036afe52642ed93c38fed21ea479956`, mapped FULL
`42358983502` attempt 1 was terminal SUCCESS, and independent exact-source
review accepted the L41R2 implementation. At that source-acceptance checkpoint
the real observation had not yet run; it was subsequently consumed as
BLOCKED / NO RETRY in the L41R2 record above. It does not advance Q62.

## L40 accepted/integrated checkpoint

Canonical worktree: `F:\AI\worktrees\ai-trading-bot-live-prototype-current`;
branch: `feature/robinhood-live-prototype-current`.

Accepted L40 source HEAD:
`14e1b628c0c51c27b23deabee56eb91859818529`

Accepted L40 source tree:
`48b588cbb37818b0d1edfcbb895cfb715a2bf2d3`

Direct parent:
`f7f13f805ad6a0eea7041cb6d13c561149a13f6e`

Feature mapped FULL `41995282653`, attempt 1, was SUCCESS with all seven
canonical broad lanes, active tests, hygiene/evidence and aggregate source gate
green. The exact source was independently accepted. Ordinary fast-forward
integration then moved `develop` to the accepted L40 source; develop gate
`41997418576`, attempt 1, was SUCCESS and reused feature certification
`41995282653` without another FULL. Remote feature and develop were both
verified at the accepted L40 HEAD/tree before this coordination closeout.

The accepted [L40 contract](architecture/147-restricted-live-contract.md) is an
effect-disabled pure policy owner. It freezes exact-owned full-remainder exits,
the <=$10 requested/cumulative new-acquisition budget, reducing exits without a
universal $10 exit-notional ceiling, partial-fill ownership, residual
preservation, exact identity matching and UNKNOWN/MAY_HAVE_OCCURRED no-retry
semantics. Evidence-reference flags are necessary-only prerequisites and
authenticate nothing by themselves. L40 does not establish actual Robinhood
account fractional-sell eligibility, numeric quantity/minimum/notional rules,
durable controller persistence or live-order authority.

The next source step described at L40 was superseded by the current source
preparation milestone above. D33 and D34 remain consumed/no-retry and
`FINAL_HOLDOUT` remains sealed. No paper soak is inserted.

## D34 accepted/integrated closeout identity

Worktree: `F:\AI\worktrees\ai-trading-bot-live-prototype-current`

Branch: `feature/robinhood-live-prototype-current`

Integrated source HEAD: `b86defebf9ccbf1efb91397de8f2e66db24a6665`

Integrated source tree: `9fa2360dfe7afdd902fd539e94f888063439785d`

Feature mapped FULL `41969407894`, attempt 1, and develop source-gate
`41973853073`, attempt 1, both succeeded; develop reused the exact feature
certification. That is the accepted D34 implementation identity; the later
canonical closeout and current L40 base are recorded above. The accepted/integrated
D33 source remains the D34 lineage ancestor
`fad65c9f4eab5bc1de4e154fdf0f59e397bc943a` / tree
`beab205abcc045fad38625ff73bb48affea9a0e9`. The first D34 publication
`9981bf47072d35381a2e5b6f187c9497e9dbed5a` is its direct child, and accepted
D34 corrective source `b86defebf9ccbf1efb91397de8f2e66db24a6665` is the direct
child of `9981bf47072d35381a2e5b6f187c9497e9dbed5a`. D33 is a consumed
predecessor incident, not an available observation boundary.

The preserved D34 predecessor is
`9981bf47072d35381a2e5b6f187c9497e9dbed5a` / tree
`a8d2b4fb4a40039b74768b44fd0198dc87bc55f3`. Its mapped run `41950572892`,
attempt 1, was terminal SUCCESS, but exact-source review rejected it before
develop integration because blocked-result attempt counts were not bound to
their failure phase and the operator fallback could write false `0/0`
credential/provider counts after an escaped failure. No D34 real observation
occurred; the candidate remains immutable evidence.

D30 is ACCEPTED with dataset ID
`d5aa8ed7-b5cd-53a3-8671-5370f976e8e3`, dataset SHA
`ebe1839d510db0f24f58f9ebe02b7efb09221d4b8c06c23122f84912c3225214`, and
`ALPACA_ALL_ADJUSTED_PRICE_V1`. D31's exact bundle is ACCEPTED with campaign
`9b2a000e-3adc-50f4-ab47-2aa90665e3c9`, bundle
`f01a39a7-0a65-55bb-9d38-608b1ce0bd21`, bundle SHA
`94870e0e0e10de16f7e98e7cfea2e2c84458a15e6f1d2665cd8a5dc7e404fc11`, result
`NONE_QUALIFIES`, and retained control `BASE_MA35_50_V1` / candidate
`21158358-75be-5597-b940-5bccdda1429c`. D32 is ACCEPTED / CLOSED: strategy
math parity, research-binding integrity, and live data-basis parity passed;
the 2,516 comparisons had zero mismatches. The former
`DATA_BASIS_MISMATCH` blocker is closed.

## Consumed D33 incident

D33's one real read-only attempt is CONSUMED / BLOCKED / NO RETRY. Preserved
evidence:
`F:\\AI\\temp\\arch147-d33-alpaca-observation-576b4b5c8f7b41548df7b822c44c74de\\evidence.json`;
SHA-256 `b767727712e4634950be8a6ba8f43522910d037987824ad33cb7c20c8eab95ec`,
1,999 bytes; observation `2026-11-04T23:59:08.218729Z`; credentials `1`;
provider requests `1`; selected sessions `60`; production, broker,
runtime-binding, campaign, and FINAL_HOLDOUT mutation counts are all `0`.
The exact provider rejection subtype is unavailable because D33 discarded it.
The request end exceeded observation through end-of-calendar-day semantics;
this is a source-contract defect, not proof of the provider's exact rejection
cause. D33's exact request target is preserved in the validation ledger.

## Accepted D34 observation and stop conditions

The corrective D34 child changes only attempt-accounting/evidence truthfulness
and focused tests/docs. The additive D34 source derives one exact published
regular close after selecting the 60 completed XNYS sessions and before
credential/provider construction. That same cutoff is used for the request and
`CompletedSignalInputs`; it never uses next midnight, end-of-calendar-day,
observation-as-substitute, silent subtraction, provider fallback, or a changed
session set. D34's separately named entry point is
`trading_bot.live_prototype.alpaca_signal_recovery_operator`, with evidence
schema `arch147-d34-alpaca-signal-observation/v1`. The old D33 CLI is retired
before credentials/provider access; `--help` remains effect-free.

D34 source admission and the mapped feature FULL completed before the
separately labeled read-only observation. The accepted evidence is
`F:\\AI\\temp\\arch147-d34-alpaca-observation-84d32fb2af5045e7a661a77259b690fb\\evidence.json`,
2800 bytes, SHA-256
`7c6f2d391cbb3141405e3252efcfcd94db18b8e81083d947d778310bfe49464b`.
Schema: `arch147-d34-alpaca-signal-observation/v1`; status READY; reason
`D34_ALPACA_SIGNAL_INPUTS_READY`; observation timestamp
`2026-11-05T05:28:41.664723Z`.

The observation consumed exactly one credential read and one provider call, with
automatic retry FORBIDDEN. The exact one-request target is
`GET /v2/stocks/bars?symbols=SPY&timeframe=1Day&start=2026-08-12T04%3A00%3A00.000000Z&end=2026-11-04T21%3A00%3A00.000000Z&limit=60&adjustment=all&asof=-&feed=sip&currency=USD&sort=asc`.
It selected 60 sessions from 2026-08-12 through 2026-11-04. Response-body
bytes were 6702 with SHA-256
`296c9e89dd2f48d47b1ca3b071411d6e8509ca769fc92e433be19696bbf68c94`;
provider request-ID digest was
`6384000426f7d007ed9391b81bef6beb2ba40a5193cf94dd30a2a58fb63ae15f`; and
the `CompletedSignalInputs` digest was
`8b6d4f88012da820890cb5070de975c1d02504aeb432939a2e954d9bf9dfecb0`.
No raw request ID or credential material is retained.

The D34 attempt is CONSUMED SUCCESSFULLY / NO RETRY. Production, broker,
runtime-binding, campaign, order, paper, live, and `FINAL_HOLDOUT` effects are
all zero. The observed BASE_MA35_50_V1 BUY/HOLD outputs are signal outputs only;
they do not authorize an order or grant live eligibility.

At the L40 closeout, its original L41-L43 dependency plan was the accepted
baseline and Q61 had not yet run. Q61 was accepted later; this passage records
the earlier L40 state. No live-readiness label or paper-soak milestone is
granted and `FINAL_HOLDOUT` remains sealed.

The old P6 preflight is historical predecessor context, not the current next
operator action and not the D33/D34 signal-data path. It grants no retry.
