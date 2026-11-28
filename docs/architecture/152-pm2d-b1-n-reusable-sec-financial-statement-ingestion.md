# Architecture 152-PM2D-B1-N — Reusable SEC Financial Statement Ingestion

This is a source-only, offline-document-validation checkpoint for reusable
extraction of supported financial statement facts. It does not
authorize a new SEC request, Sharadar observation, operational evidence
admission, historical reconstruction, recommendation, or portfolio action.

## 1. Parent and boundary

The accepted PM2D-B1-R-C2 parent is HEAD
`85d2cc1aec12d172d0225eac61bda770becdbbc7` / tree
`acf07f52d33f15fad7e391329076c015b844ce77`. Feature mapped FULL run
`46130743708`, attempt 1, completed SUCCESS across all seven lanes. Develop
acceptance run `46131689560`, attempt 1, completed SUCCESS with
`DEVELOP_CERTIFICATION_REUSE=True REASON=exact_feature_certification`; its
test and certification jobs were skipped. These identities supersede the
older C1 parent reference retained in the B1-R chronology below; that
historical evidence is not rewritten.

PM2D-B1-N extends the existing Architecture 152-PM2D-B1 source-only route. It
extracts reusable normalized financial statement facts from the exact
digest-verified local SEC instance identified in the validation record. The
implementation reuses the existing PM2C catalog, evidence, identity, and
snapshot contracts. It does not change the accepted B1 fake-provider contract,
the B1-R real transport, the canonical observation attempt, or PM2C cutoff and
historical-witness semantics. The existing B1 checkpoint slug and mapped
seven-lane FULL route remain in force; no new acquisition route is introduced.

The pipeline is limited to:

```text
already-held native instance bytes
  -> bounded offline parsing
  -> exact source fact and context preservation
  -> supported normalized field or typed unavailable result
  -> existing PM2C contracts, only when every admission prerequisite is met
```

Parsing does not fetch filings, discover or download taxonomies, make AI
requests, select investments, or create PM2C facts by itself. Financial
ingestion validation must have zero SEC or remote-taxonomy network access;
source CI may use its normal GitHub and toolchain network access.

## 2. Public-library review and reuse decision

The review was pinned to EdgarTools commit
[`31371d457ee4c95d9f397a07fa3fc60a3b7b4492`](https://github.com/dgunning/edgartools/tree/31371d457ee4c95d9f397a07fa3fc60a3b7b4492)
and Arelle commit
[`1a82e9731e70bdb3cb9721a5e6ad812507f470e4`](https://github.com/Arelle/Arelle/tree/1a82e9731e70bdb3cb9721a5e6ad812507f470e4).

### EdgarTools

EdgarTools is MIT-licensed and requires Python 3.11 or newer at the reviewed
revision. Its local `XBRL.from_files` and directory paths are useful for
broader XBRL workflows and do not by themselves imply a network request. The
higher-level `from_filing` path can use attachment retrieval; for older inline
filings whose extracted instance is missing, it can fall back to retrieving an
SEC homepage instance when local-storage/network settings permit. That
filing-oriented fallback is outside this checkpoint's one-existing-document
boundary. Sources: [EdgarTools XBRL paths](https://github.com/dgunning/edgartools/blob/31371d457ee4c95d9f397a07fa3fc60a3b7b4492/edgar/xbrl/xbrl.py),
[pinned project metadata](https://github.com/dgunning/edgartools/blob/31371d457ee4c95d9f397a07fa3fc60a3b7b4492/pyproject.toml).

The instance parser retains contexts, units, dimensions, source concepts, and
duplicate fact records, and exposes a lexical `raw_value` string. Its common typed numeric
representation uses `float(value)` and can infer decimals from precision
metadata, so using its convenience numeric value would not preserve this
checkpoint's exact decimal contract. Its statement resolver uses presentation
roles and trees; its standardization layer includes label similarity and
contextual mapping. Those conveniences do not establish the exact accounting
basis, concept equivalence, or decimal evidence required here. The reviewed
dependency closure also includes a broad data/HTTP stack, including pandas,
pyarrow, lxml, and networking packages. Sources: [instance parser](https://github.com/dgunning/edgartools/blob/31371d457ee4c95d9f397a07fa3fc60a3b7b4492/edgar/xbrl/parsers/instance.py),
[statement resolver](https://github.com/dgunning/edgartools/blob/31371d457ee4c95d9f397a07fa3fc60a3b7b4492/edgar/xbrl/statement_resolver.py),
[standardization](https://github.com/dgunning/edgartools/blob/31371d457ee4c95d9f397a07fa3fc60a3b7b4492/edgar/standardization/core.py),
[pinned project metadata](https://github.com/dgunning/edgartools/blob/31371d457ee4c95d9f397a07fa3fc60a3b7b4492/pyproject.toml).

### Arelle

Arelle is Apache-2.0-licensed and requires Python 3.11 or newer at the reviewed
revision. Its document loader supports native XBRL and Inline XBRL / IXDS
discovery; local file sources and package remapping can resolve taxonomies from
local packages or catalogs; and relationship sets expose presentation roles
and networks. Instance objects retain context dimensions, units,
decimals/precision and Inline XBRL scale/sign. Duplicate validation classifies
complete, consistent, and inconsistent duplicate fact sets with accuracy
ranges. Sources: [document loader](https://github.com/Arelle/Arelle/blob/1a82e9731e70bdb3cb9721a5e6ad812507f470e4/arelle/ModelDocument.py),
[file sources](https://github.com/Arelle/Arelle/blob/1a82e9731e70bdb3cb9721a5e6ad812507f470e4/arelle/FileSource.py),
[relationship sets](https://github.com/Arelle/Arelle/blob/1a82e9731e70bdb3cb9721a5e6ad812507f470e4/arelle/ModelXbrl.py),
[instance objects](https://github.com/Arelle/Arelle/blob/1a82e9731e70bdb3cb9721a5e6ad812507f470e4/arelle/ModelInstanceObject.py),
[duplicate validation](https://github.com/Arelle/Arelle/blob/1a82e9731e70bdb3cb9721a5e6ad812507f470e4/arelle/ValidateDuplicateFacts.py),
[pinned project metadata](https://github.com/Arelle/Arelle/blob/1a82e9731e70bdb3cb9721a5e6ad812507f470e4/pyproject.toml).

Arelle's command-line documentation and web cache implementation show that
offline operation is an explicit configuration concern. `--workOffline` uses
only locally available resources, while `--skipDTS` bypasses taxonomy
discovery/validation and is not a substitute for a complete local taxonomy
bundle. A future Arelle adapter would require an approved filing/taxonomy
package set, an isolated cache, explicit no-egress verification, and negative
tests for missing schema/linkbase inputs. Its dependencies include lxml,
NumPy, jsonschema, and other packages, which would be a material dependency
increase for a single native instance. Sources: [command-line documentation](https://github.com/Arelle/Arelle/blob/1a82e9731e70bdb3cb9721a5e6ad812507f470e4/docs/source/command_line.md),
[web cache](https://github.com/Arelle/Arelle/blob/1a82e9731e70bdb3cb9721a5e6ad812507f470e4/arelle/WebCache.py),
[pinned project metadata](https://github.com/Arelle/Arelle/blob/1a82e9731e70bdb3cb9721a5e6ad812507f470e4/pyproject.toml).

### Decision

Do not install, vendor, or add either library as a dependency for this narrow
checkpoint. Use a small explicit standard-library XML path for the
already-held native instance, preserve the exact PM2C provenance, and fail
closed on unsupported shapes. EdgarTools remains a possible helper for broader
local workflows when its numeric/basis limitations are addressed. Arelle is a
candidate for a later Inline XBRL, extension-taxonomy, or presentation-role
milestone when complete local filing and taxonomy bundles are available and
the offline boundary is tested. Neither library may silently acquire SEC
content or resolve remote taxonomies in validation or CI.

## 3. Normalized fact contract

The initial research field set is annual revenue, operating income, net income,
diluted EPS, operating cash flow, capital expenditure, cash and equivalents,
total assets, total liabilities, equity, and debt only where its exact
accounting basis can be established. This list is a bounded research target,
not a claim that each field has a supported mapping in every filing.

V1 recognizes the exact US GAAP namespace
`http://fasb.org/us-gaap/2018-01-31`. Facts in other dated namespaces remain
typed unsupported until a separately reviewed mapping supports them. The
generic `NetIncomeLoss` fact is preserved as source evidence, but it does not
by itself establish the PM2B attributable-to-common net-income basis.

Every available result preserves the original expanded namespace and concept,
context identifier, period, unit, dimensions, signed exact decimal value,
accession, and source-document digest alongside its normalized field. The
normalized mapping must identify the concept and accounting basis it supports.
Unsupported or conflicting concepts remain typed unavailable; no fuzzy label,
alias, missing-value, or period fallback is inferred. Values are not converted
through binary floating point.

`RevenueFromContractWithCustomerIncludingAssessedTax` and
`RevenueFromContractWithCustomerExcludingAssessedTax` remain distinct concepts
and accounting bases unless an independently justified, reviewed mapping
establishes equivalence. Consolidated revenue is not added to dimensional
segment revenue. Nonmonetary facts and text-block/policy facts are not accepted
as financial statement values. Annual and quarterly contexts remain distinct;
quarterly values are not inferred from annual or year-to-date facts.

`PaymentsToAcquireProductiveAssets` remains a separately named productive-
asset payment mapping and is not promoted to a PPE-specific capital expenditure
value. Debt concepts retain their exact names and bases; no aggregate, current/
noncurrent residual, or total is synthesized from other facts.

The extractor does not decide which issuer, share class, catalog field, peer,
period, or source version should be selected for an investment. PM2C remains
responsible for exact catalog-entry compatibility, typed availability,
point-in-time cutoff, subject, and historical witness validation.

## 4. ODFL discovery evidence and limits

The preserved Old Dominion Freight Line instance is an owner-held discovery
artifact: 1,350,303 bytes, SHA-256
`96437a6d33f26d4f559afcd7e7b14ebafd9f84fcee909520c16f11467f0a06b0`.
It is the `odfl-20181231.xml` instance, sequence 11, from original 10-K
accession `0001564590-19-004755`, with annual context
`C_0000878927_20180101_20181231` and namespace
`http://fasb.org/us-gaap/2018-01-31`.

The discovery hypothesis sought
`RevenueFromContractWithCustomerExcludingAssessedTax` and found zero such
facts. The consolidated revenue fact is instead
`RevenueFromContractWithCustomerIncludingAssessedTax`, value `4043695000`
USD in unit `U_iso4217USD`, with no dimensions. Separate dimensional LTL and
other-service revenue facts are `3982658000` USD and `61037000` USD. The
discovery establishes why single-concept extraction is insufficient; it does
not establish a general normalization between the assessed-tax concepts.

The accepted B1-R `SECObservationPlan` requires its frozen
`RevenueFromContractWithCustomerExcludingAssessedTax` concept. The ODFL
`IncludingAssessedTax` fact cannot be observed through that exact plan. B1-N
does not retarget or weaken B1-R. A future request must either select a filing
whose exact supported fact matches the frozen B1-R plan, or use a separately
reviewed successor plan/source. Other mapped values can enter the operational
bridge only after their own independent catalog, subject, membership,
provenance, and receipt checks pass.

This document is not a production observation, source receipt record,
point-in-time witness, or current investment signal. The canonical B1-O real
observation attempt remains unconsumed. No additional SEC request is
authorized by B1-N.

## 5. Operational bridge and acquisition prerequisites

An extracted record becomes a PM2C operational source fact only after an exact
catalog registration and all existing PM2C checks pass. Its source version,
filing period, publication/acceptance metadata, and local receipt remain
separate fields. The security subject must be independently mapped from issuer
and CIK to the exact security/share class, then bound to exact ordered
membership. A real local receipt timestamp cannot be fabricated from the file
modification time, execution time, filing date, or acceptance timestamp.
Operational `available_at` and `observed_at` cannot precede trusted receipt,
and the snapshot cutoff must be at or after receipt.

The bridge accepts only the complete B1-R response body and its request intent,
acquisition, response-provenance, document, accession, issuer, and target-fact
verification references, with the exact terminal classification and receipt.
It re-parses the B1-R submission header and named embedded member from those
same bytes, independently re-extracts the frozen
`RevenueFromContractWithCustomerExcludingAssessedTax` plan anchor, and selects
the separately requested normalized fact. It accepts the exact B1-R terminal
`SEC_OBSERVATION_BLOCKED` reason
`SEC_HISTORICAL_VERSION_WITNESS_AND_SECURITY_MAPPING_UNPROVEN`, or the typed
`NATIVE_DOCUMENT_UNSUPPORTED` / `XBRL_DURATION_CONTEXT_REQUIRED` result for a
filing with instant contexts. The latter remains unsupported; the bridge does
not convert it into a B1-R success. Supplied verification-reference strings
are trust inputs whose referenced records must be independently checked by the
caller; the adapter does not authenticate signatures. Historical version
witnesses are never minted by this bridge. Terminal counters must show exactly
one provider invocation, request intent, and response document; the response
byte counts must equal the full preserved body, with credentials, accounts,
AI, broker, and production effects all zero. Request intent cannot follow
receipt, verification cannot precede receipt, and any supplied publication
time cannot be later than receipt. The bridged PM2C fact uses trusted receipt
as `available_at`; `observed_at` is no earlier than receipt, independent
verification completion, and issuer/security mapping verification.

Historical reconstruction remains separately blocked until a witness proves
that the exact immutable fact/version was publicly available by the requested
historical cutoff. SEC acceptance time, filing date, a fixed delay, and current
receipt are not that witness. B1-N does not create PIT evidence, change
historical admission, or promote the 2018 ODFL record into current research.

Any later live acquisition requires a separately reviewed exact issuer,
security/share-class mapping, accession, document/context, concept and
accounting basis; current source admission; canonical one-shot attempt and
custody; and a short-lived plan-bound effect authorization. B1-N adds no
request and no authorization.

PM1 remains disarmed and preview-only. PM2A real account reads remain
unauthorized. Sharadar remains unqualified for exact historical version and
entitlement/retention. PM2D-B2 price/action qualification is separate. Arch149
remains sealed.
