# Architecture 152-PM2C — Synthetic Research Evidence Contracts validation record

**Validation type:** implementation-validation draft. The contract map below
is grounded in the current PM2C catalog and evidence source modules, while
publication SHA, mapped CI, exact-source acceptance, and integration remain
pending. This record authorizes no provider, account, credential, AI, broker,
market-data, or production operation.

## 1. Contract coverage map

| Requirement group | Current implementation surface | Focused coverage known in the worktree |
| --- | --- | --- |
| Catalog identity and definitions | `research_catalog.py`: `ResearchCatalog`, `CatalogEntry`, `InputSpec`, `ValueSpec`, `EvidenceBasis`, typed scope/period/window/formula declarations, exact lookup and immutable registry. | `tests/portfolio_manager/test_research_catalog.py`: exact registration/identity/version/value/basis checks, ordered roles, cycle/raw-formula rejection, typed values and token validation. |
| Availability and values | `research_evidence.py`: `AvailabilityStatus`, `AvailabilityReason`, `EvidenceOutcome`, finite immutable typed values, genuine zero preservation, no unavailable numeric substitute. | `tests/portfolio_manager/test_research_evidence.py`: all seven statuses, typed reasons, zero, nonfinite and timing rejection. |
| Point-in-time source facts | `SourceFact`, `EvidenceTimeframe`, `VersionAsOfWitness`, operational and historical cutoff validation, semantic source-fact identity. | Evidence tests cover semantic identity, impossible timing, late operational receipt, and exact historical witness behavior. |
| Derived provenance DAG | `DerivedFeature`, `EvidenceDependency`, `EvidenceGraph`, exact catalog entry IDs, role/order, subject, anchor, basis/currency and availability checks, ordered transitive closure, cycle rejection. | Evidence tests cover exact catalog inputs, closure order, late/unavailable dependency behavior, and the PM1 firewall. |
| Deterministic arithmetic | Catalog-owned `ratio`, `simple_return`, and two-anchor `momentum_12m_minus_1m`; no generic engine. | Catalog tests cover ambient-context-independent ratio, signed numerator, unsupported denominator, simple return, and golden momentum non-equivalence. Evidence tests cover the shared denominator/momentum boundary. |
| Immutable snapshot boundary | `research_snapshot.py`: `SnapshotSlotRequest`, `MembershipBinding`, `ResearchSnapshotSlot`, `ResearchSnapshot.admit`, exact graph/catalog/cutoff/mode/membership/portfolio/witness binding, recursive cutoff closure, hidden future IDs, and nonsemantic audit clock. | `tests/portfolio_manager/test_research_snapshot.py`: 15 focused tests cover unavailable slots, publication/receipt witnesses, membership window, immutable identity, exact synthetic portfolio binding, zero/missing, invalid price, and mark timing. |
| PM1/optimizer/authority firewall | Snapshot and evidence modules expose no recommendation, expected-return, optimizer, target, order, or dispatch conversion. | Evidence test includes the structural PM1 firewall; the combined focused run passed the affected PM and Arch152 ownership selectors. |

The current catalog/evidence test inventory is descriptive and does not
substitute for the combined focused run or mapped certification.

## 2. Synthetic and adversarial validation matrix

The final focused validation must preserve the PM2B cases below without
silently broadening into a provider or production test:

1. Semantic identity is stable under nonsemantic receipt/path/recalculation
   annotations and changes when value, source version, formula, role/order, or
   basis semantics change.
2. All seven availability states remain distinct; an observed zero remains a
   value and unavailable outcomes carry no numeric substitute.
3. Source timing distinguishes economic period, publication availability,
   operational receipt/materialization, calculation time, and snapshot cutoff.
   Operational late receipt fails; historical reconstruction requires an exact
   immutable version-as-of witness.
4. Derived evidence binds exact catalog key/version/entry ID, ordered roles,
   units, currency, anchors, subjects, and transitive source closure. Unknown,
   cyclic, duplicated-when-not-permitted, version-swapped, basis-mismatched,
   or late dependencies fail closed.
5. Positive-denominator ratio succeeds, nonpositive denominator is unsupported,
   signed numerators survive, and simple return uses no float. The golden
   momentum helper uses only old 12-month and new 1-month anchors, not current
   close or a difference of returns.
6. Catalog declarations retain complete windows, fiscal/session/target anchors,
   and split-only versus total-return basis as typed metadata. No provider
   calendar, quarterization, consensus, corporate-action, or peer calculation
   is invented by PM2C.
7. Snapshot admission preserves ordered universe/membership, every available
   and unavailable slot, exact catalog ID/version, cutoff/mode, effective
   membership window, dependency closure, selected witness identities,
   operational receipt/materialization identities, and exact portfolio
   observation binding. It rejects newer-fact/older-cutoff mixing, future-ID
   exposure, and mutation after construction.
8. PM2C evidence cannot become a PM1 `MarketSignal`, recommendation,
   expected-return estimate, optimizer input, target, plan, or order.
9. Planned synthetic adversarial fixtures retain an after-cutoff restatement as
   typed unavailable, exercise the 12-minus-1 golden anchor without a current
   close or return-difference substitution, and distinguish true zero from
   missing currency/quantity. These remain test-plan cases only; no provider
   feed or production computation is claimed.

## 3. Verification state

The owned snapshot-focused command completed in the implementation checkout:

```powershell
& 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe' -B -u -m pytest -p no:cacheprovider `
  tests/portfolio_manager/test_research_snapshot.py `
  --basetemp 'F:\AI\temp\pytest\<fresh-guid>' -q
```

Observed result: **15 passed in 0.12s**, exit 0, basetemp
`F:\AI\temp\pytest\pm2c-snapshot-6ca7d243060646b19974896f3d0cc345`.

The combined focused regression command included the three PM2C modules, the
affected PM1/PM2A decision, observation, risk-planning, vertical-slice, and
certification-ownership modules, plus the Arch152 ownership selector:

```powershell
& 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe' -B -u -m pytest -p no:cacheprovider `
  tests/portfolio_manager/test_research_catalog.py `
  tests/portfolio_manager/test_research_evidence.py `
  tests/portfolio_manager/test_research_snapshot.py `
  tests/portfolio_manager/test_decision.py `
  tests/portfolio_manager/test_observation.py `
  tests/portfolio_manager/test_risk_planning.py `
  tests/portfolio_manager/test_vertical_slice.py `
  tests/portfolio_manager/test_certification_ownership.py `
  tests/runtime/checkpoint_runner/test_core.py::test_arch152_pm1_is_source_only_and_mapped_to_full `
  --basetemp 'F:\AI\temp\pytest\<fresh-guid>' -q
```

Observed result: **86 passed in 0.79s**, exit 0, basetemp
`F:\AI\temp\pytest\pm2c-combined-b96ba9af2af34213a03dca90319e0602`.

Whole-repository `ruff check .` and `ruff format --check .` both completed
with exit 0 after scoped formatting of the owned snapshot files; `git diff
--check` also completed with exit 0. These are source hygiene results, not
local FULL, mapped FULL, source-gate, admission, publication, acceptance, or
integration evidence.

The checked documentation scope is exactly these four Markdown paths: this
validation record, its owning [Architecture 152-PM2C](../architecture/152-pm2c-synthetic-research-evidence-contracts.md),
`docs/PROJECT_STATUS.md`, and `docs/AI_TRADING_BOT_HANDOFF.md`. Together they
record the synthetic contract/test evidence, the implementation boundary, the
high-level milestone status, and the active continuation boundary. They do not
grant provider, account, AI, broker, publication, acceptance, or integration
authority.

## 4. Exclusions and next milestone

This validation record does not add or authorize providers, credentials,
OAuth, real account reads, Robinhood sessions, AI calls, broker/order effects,
sealed Arch149 access, market-data acquisition, database storage, scoring,
ranking, forecasting, covariance, optimizer objectives, allocation, or live
trading. Qlib and PyPortfolioOpt remain non-dependencies and non-authorities.

After PM2C is source-accepted, certified, reviewed, and integrated, PM2D is
the next separately designed milestone: qualify public/commercial data-source
capabilities and provenance methodology against the PM2B catalog. PM2D must
retain PM2C's fail-closed timing, identity, basis, availability, and authority
boundaries and does not inherit provider authorization from this draft.
