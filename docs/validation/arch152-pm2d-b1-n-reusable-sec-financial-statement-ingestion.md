# Architecture 152-PM2D-B1-N — Reusable SEC Financial Statement Ingestion Validation

**Validation boundary** This record covers source-only offline extraction and
synthetic PM2C bridge qualification. It does not authorize a new SEC or
Sharadar request, provider access, credentials, account reads, AI calls,
brokerage effects, production mutation, recommendations, or sealed Arch149
access.

## 1. Parent, route, and evidence identity

The accepted parent is PM2D-B1-R-C2 HEAD
`85d2cc1aec12d172d0225eac61bda770becdbbc7` / tree
`acf07f52d33f15fad7e391329076c015b844ce77`. Feature mapped FULL run
`46130743708`, attempt 1, completed SUCCESS across all seven lanes. Develop
acceptance run `46131689560`, attempt 1, completed SUCCESS with
`DEVELOP_CERTIFICATION_REUSE=True REASON=exact_feature_certification`;
source-static and source-gates passed, and test/certification jobs were
skipped. These identities correct the older C1 parent still recorded in the
B1-R historical chronology.

B1-N extends the existing `arch152-pm2d-b1-sec-sharadar-bounded-qualification-source`
checkpoint. The source and test paths are included in the same exact
`ARCH152_PM2D_B1_*` ownership tuples and in the same seven-lane FULL mapping.
The existing B1 fake-provider behavior and B1-R transport/parser remain
unchanged.

## 2. Public-library decision

The pinned EdgarTools and Arelle reviews, source references, license/dependency
costs, exact-decimal limitations, and offline boundary are recorded in the
[B1-N architecture record](../architecture/152-pm2d-b1-n-reusable-sec-financial-statement-ingestion.md).
Neither package was installed or added to project dependencies. A bounded
standard-library parser uses the exact local native instance and retains its
fact/context provenance. Ingestion validation has zero SEC and remote-taxonomy
network access; ordinary GitHub/toolchain CI networking remains permitted.

## 3. Preserved ODFL document

Offline validation used only the existing owner-held file:

`F:\AI\temp\arch152-pm2d-b1-o-p-cc5aa89283824251a2c34c5b71b9ec06\instance.xml`

- Length: `1,350,303` bytes.
- SHA-256: `96437a6d33f26d4f559afcd7e7b14ebafd9f84fcee909520c16f11467f0a06b0`.
- Issuer: Old Dominion Freight Line, CIK `0000878927`.
- Filing: original 10-K accession `0001564590-19-004755`.
- Instance: `odfl-20181231.xml`, sequence `11`.
- Namespace: `http://fasb.org/us-gaap/2018-01-31`.
- Annual context: `C_0000878927_20180101_20181231`.
- Closing context: `C_0000878927_20181231`.

The exact digest and length were verified before parsing. This local
file-processing result is discovery evidence only and does not create a
trusted response-receipt record.

## 4. Extracted facts and supported mappings

Every reported fact retains its source concept, namespace, context, period,
unit, dimensions, decimals, accession, and document digest. Money values below
use USD. `decimals=-3` records the source precision declaration; values remain
exact decimal facts, not inferred precision.

| Field or source fact | Concept and context | Value and source unit | Dimensions and result |
| --- | --- | --- | --- |
| Revenue including assessed tax | `RevenueFromContractWithCustomerIncludingAssessedTax`; annual context | `4043695000`, USD, decimals `-3` | Consolidated, no dimensions; separate from ExcludingAssessedTax. |
| Revenue excluding assessed tax | `RevenueFromContractWithCustomerExcludingAssessedTax`; expected annual concept | Missing | No fact in this filing; the frozen B1-R plan requires this concept. |
| LTL service revenue | `RevenueFromContractWithCustomerIncludingAssessedTax`; `C_0000878927_srtProductOrServiceAxis_odflLTLServiceRevenueMember_20180101_20181231` | `3982658000`, USD, decimals `-3` | `{http://fasb.org/srt/2018-01-31}ProductOrServiceAxis = {http://www.odfl.com/20181231}LTLServiceRevenueMember`; kept separate. |
| Other service revenue | `RevenueFromContractWithCustomerIncludingAssessedTax`; `C_0000878927_srtProductOrServiceAxis_odflOtherServiceRevenueMember_20180101_20181231` | `61037000`, USD, decimals `-3` | `{http://fasb.org/srt/2018-01-31}ProductOrServiceAxis = {http://www.odfl.com/20181231}OtherServiceRevenueMember`; kept separate. |
| Operating income | `OperatingIncomeLoss`; annual context | `817051000`, USD, decimals `-3` | One consolidated duration fact. |
| Generic net income | `NetIncomeLoss`; annual context | `605668000`, USD, decimals `-3` | Preserved as a source fact; it does not establish PM2B attributable-to-common income. A same-value RetainedEarnings-dimensional fact is separate evidence. |
| Diluted EPS | `EarningsPerShareDiluted`; annual context | `7.38`, USD per share, decimals `2` | Exact quotient unit retained. |
| Operating cash flow | `NetCashProvidedByUsedInOperatingActivities`; annual context | `900116000`, USD, decimals `-3` | One consolidated duration fact. |
| PPE-specific acquisition payments | `PaymentsToAcquirePropertyPlantAndEquipment`; annual | Missing | Typed unavailable; no PPE-specific capex mapping is emitted. |
| Productive-asset payments | `PaymentsToAcquireProductiveAssets`; annual context | `588292000`, USD, decimals `-3` | Separate supported field; not renamed or promoted to PPE capex. |
| Cash and equivalents | `CashAndCashEquivalentsAtCarryingValue`; closing context | `190282000`, USD, decimals `-3` | One consolidated instant fact. |
| Total assets | `Assets`; closing context | `3545283000`, USD, decimals `-3` | One consolidated instant fact. |
| Total liabilities | `Liabilities`; closing context | `864800000`, USD, decimals `-3` | One consolidated instant fact. |
| Stockholders' equity | `StockholdersEquity`; closing context | `2680483000`, USD, decimals `-3` | Consolidated fact; common stock, APIC, and retained-earnings dimensions remain separate facts. |
| Long-term debt | `LongTermDebt`; closing context | `45000000`, USD, decimals `-6` | Separately mapped source basis. |
| Long-term debt and capital lease obligations | `LongTermDebtAndCapitalLeaseObligations`; closing context | `45000000`, USD, decimals `-3` | Separate source basis; not combined with `LongTermDebt`. |
| Current long-term debt and capital lease obligations | `LongTermDebtAndCapitalLeaseObligationsCurrent`; closing context | `0`, USD, decimals `-3` | Separate current basis; the exact zero is retained. |

The three adjacent concepts below remain typed
`CONCEPT_BASIS_NOT_MAPPED`; their values are preserved for diagnostics and do
not create debt totals or operating-lease estimates:

- `DebtAndCapitalLeaseObligations`: `45000000` USD, decimals `-3`.
- `LongTermDebtFairValue`: `45600000` USD, decimals `-5`.
- `OperatingLeaseLiability`: range `65000000`–`70000000` USD on
  `{http://fasb.org/srt/2018-01-31}RangeAxis` contexts whose members are
  `{http://fasb.org/srt/2018-01-31}MinimumMember` and
  `{http://fasb.org/srt/2018-01-31}MaximumMember`.

No long-term-debt current/noncurrent value is inferred from other concepts.
The separate CommonStock (`8123000`), AdditionalPaidInCapital (`142176000`),
and RetainedEarnings (`2530184000`) facts are not summed in place of the
consolidated equity fact. Consolidated revenue is not added to dimensional
segment facts. No duplicate/conflicting fact was observed in the selected
annual or closing grains; no unknown mapped-unit observation was reported.

## 5. Operational bridge and historical reconstruction

The offline parser does not by itself admit a PM2C `SourceFact`. The bridge
accepts only a complete B1-R request/response custody record, full received
body, exact terminal qualification and receipt, independent verification
references, exact catalog entry, issuer-to-security/share-class mapping, and
PM2C membership binding. It re-parses the submission header and named embedded
member from the preserved bytes and independently reproduces the B1-R frozen
revenue anchor before selecting the requested target fact. It accepts only the
exact B1-R terminal `SEC_OBSERVATION_BLOCKED` reason
`SEC_HISTORICAL_VERSION_WITNESS_AND_SECURITY_MAPPING_UNPROVEN`, or the exact
`NATIVE_DOCUMENT_UNSUPPORTED` / `XBRL_DURATION_CONTEXT_REQUIRED` parser limit.
That parser limit remains unsupported; it does not count as a B1-R success.
Verification-reference strings are trust inputs whose referenced records
require independent validation; the bridge does not authenticate signatures.

The terminal record must show one provider invocation, one request intent, and
one response document; both response-byte counters must equal the full body
length. Credential, account, AI, broker, and production counters must be zero.
Request intent must be no later than receipt, verification must be no earlier
than receipt, and independently supplied publication time cannot follow
receipt. The new PM2C fact uses trusted local receipt as `available_at` and
places `observed_at` no earlier than receipt, verification completion, and
issuer/security mapping verification. No historical version witness is
created.

The ODFL discovery file has no B1-R consumed response/custody, trusted response
receipt record, independent verification references, approved
issuer-to-security/share-class mapping, exact PM2C membership binding, or
admitted catalog entry. Its consolidated IncludingAssessedTax fact also cannot
use the frozen B1-R `SECObservationPlan`, which requires the
ExcludingAssessedTax concept. B1-N does not retarget B1-R. A future acquisition
must match the frozen B1-R concept or use a separately reviewed successor
plan/source, then pass exact catalog, custody, receipt, subject, membership,
and availability checks.

Operational admission for this ODFL discovery remains **BLOCKED**. No PM2C
source fact or operational snapshot is emitted. Historical reconstruction
remains **BLOCKED** until a witness proves public availability of the exact
immutable source version by the requested cutoff. Filing date, acceptance
metadata, present receipt, a digest, or a fixed delay is not that witness.

## 6. Local validation and publication checks

Exact owner-local offline command:

```powershell
$env:PYTHONPATH='src'; py -m trading_bot.portfolio_manager.sec_financial_statements `
  'F:\AI\temp\arch152-pm2d-b1-o-p-cc5aa89283824251a2c34c5b71b9ec06\instance.xml' `
  --sha256 96437a6d33f26d4f559afcd7e7b14ebafd9f84fcee909520c16f11467f0a06b0 `
  --length 1350303 --accession 0001564590-19-004755 `
  --document-name odfl-20181231.xml --cik 0000878927 `
  --period-start 2018-01-01 --period-end 2018-12-31
```

The CLI emits source IDs, concepts, contexts, units, dimensions, decimals, and
typed missing/unsupported outcomes. It reports zero HTTP, taxonomy, credential,
account, AI, broker, or repository-write effects. The invocation verifies the
existing bytes and does not retrieve another filing.

Focused verification after the bridge correction completed in separate
groups:

- New B1-N statement-extraction and PM2C bridge modules:
  `test_sec_financial_statements.py` plus `test_sec_financial_evidence.py`,
  **34 passed**.
- Existing B1/B1-R compatibility:
  `test_source_qualification.py`, `test_sec_sharadar_qualification.py`, and
  `test_sec_native_observation.py`, **95 passed**.
- Existing PM2C contracts:
  `test_research_catalog.py`, `test_research_evidence.py`, and
  `test_research_snapshot.py`, **44 passed**.
- Shared checkpoint authority/profile/lane group:
  checkpoint-runner `test_core.py`, `test_source_authority.py`, and `test_ci.py`,
  plus certification-runner `test_profiles.py` and `test_lanes.py`,
  **1,147 passed in 130.86s**. After adding the new validation-record route,
  the direct B1 route and four singleton owned-path cases passed again
  (**5 passed**).
- Ruff check and format check passed on the seven changed Python files. The
  working diff check passed; the exact staged diff is checked again before
  commit.

The exact FEATURE and PROSPECTIVE_DEVELOP admission evidence and terminal
mapped GitHub FULL identity are generated after this source commit and are
reported in the publication handoff. The mapped GitHub FULL is the canonical
certification; do not run a duplicate local FULL.

No feature publication, integration, provider request, credential, account,
AI, broker, order, production, or sealed-data effect is authorized by this
validation record.
