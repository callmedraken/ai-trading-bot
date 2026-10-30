# Architecture 147 — Desktop product pivot validation

Status: CURRENT P3 SOURCE-ONLY validation; P2 source and real acquisition accepted.
P3 includes the explicitly authorized scoped lazy-export authority successor;
historical pins and security classification remain unchanged. The original
source and the exact reviewed transformation are separately validated.
Feature CI #809 is preserved green pre-correction source evidence,
but exact source review rejected its P2 candidate as
`ARCH147_P2_PREMATURE_COMPLETE_MARKER_DEFECT`. The #810 successor was accepted;
the separately reviewed real acquisition subsequently succeeded. No old
Architecture-146 preflight was restored.

## Scope

This checkpoint establishes the ordinary single-user desktop research profile,
the profile-owned acquisition persistence seam, the OPEN-only loader, and the
explicit Architecture-145 final-holdout admission boundary. It preserves the
deterministic Architecture 146-A dataset contracts and the accepted published
session authority. It does not perform real acquisition or create the fixed
production root.

The fixed source-owned root is
`F:\AI\ai-trading-bot\data\research\desktop-v1`. Tests must use a fresh
explicit temporary root seam under the external pytest temporary-root policy.
No ACL, SID, SDDL, token/elevation, ownership, privilege, credential, provider,
Robinhood, paper, broker, or live operation is in scope.

## Required source behavior

The desktop storage profile must use ordinary create-only filesystem behavior:
exact-byte hashing, readback verification, normal flush/fsync where practical,
manifest and size checks, visible incomplete state, and no automatic cleanup.
It must reject arbitrary production-root substitution, never overwrite an
existing completed file, and contain no rename/promotion or junction/symlink
publication path.

The OPEN loader must read only normalized OPEN bytes and required non-price
metadata, validate canonical CSV, hash/size/manifest membership, snapshot
bindings, and the accepted authority
`nyse-published-regular-sessions-2016-2026-v1` (2718 sessions and the frozen
published digest). It must not read FINAL_HOLDOUT bytes or require
`ACCEPTED_CUSTODY_ADMISSIONS`.

The final loader must require the exact existing
`ResearchStrategyFinalHoldoutAdmission`, reject missing/wrong admissions and
policy/dataset/partition mismatches, validate FINAL_HOLDOUT physical integrity,
and return only the explicitly admitted holdout. Optimizer, walk-forward, and
candidate-selection modules must not import or call that loader.

The acquisition kernel must retain the existing fake-transport normalization,
partition, raw-page, corporate-action, published-session, snapshot, and full
fingerprint semantics while delegating persistence to the injected profile.
The protected custody adapter remains isolated legacy behavior; it is not
constructed unconditionally by the current desktop path.

For the desktop profile, `open_files` and `materialize_open` must include and
readback-verify both `normalized/open/SPY.csv` and `evidence.json` before the
kernel records `COMPLETE`. If evidence materialization fails, the adapter must
report `PERSISTENCE_FAILURE`, leave a `STOPPED` terminal record and the
destination intact, and reject a second attempt as
`PREEXISTING_DESTINATION`. The wrapper then performs full integrity inspection,
the OPEN loader, and only then returns sanitized success metadata.

## Focused evidence

The focused P1 checks cover fixed-root/test-seam behavior, ordinary filesystem
invariants, create-only/readback and incomplete/corrupt/manifest mismatch
blocking, OPEN-only reads, final-holdout admission and integrity, optimizer
import ownership, fake acquisition composition, readiness classification, and
checkpoint/source authority. Retained compatibility coverage covers the
Architecture 146 acquisition/custody and dataset tests; affected Architecture
145 robustness and candidate/walk-forward tests remain required focused
coverage.

The checkpoint is registered as `arch147-desktop-research-profile` with
`preflight=None` and `execute=None`, mapped to GitHub-owned FULL. The consumed
Architecture 146 `HOST_UNKNOWN` observer report is historical evidence only
and must not be retried. P1 has no Robinhood MCP call, OAuth read, account
query, order review, order mutation, or live effect.

## Admission and handoff

Before publication, run focused tests, whole-root Ruff diagnostics, and
`git diff --check`. Then exact-file stage only the intended files, verify the
staged filename set and `git diff --cached --check`, create one atomic commit,
and run:

    .\ops.ps1 admit

The admission must report `FEATURE PASS` and
`PROSPECTIVE_DEVELOP PASS` for the exact same final HEAD/tree and stable
identity. Publish one ordinary push and wait for the mapped GitHub FULL run to
reach a terminal result. Do not run canonical FULL locally. A deterministic
stale current assertion tied only to the retired protected-custody next action
must be corrected inside this checkpoint; unexpected security, authority,
credential, provider, or effect ambiguity is a STOP for ChatGPT review.

After terminal CI, ChatGPT independently reviews exact P3 source and decides
whether to fast-forward `develop`. After acceptance/integration and develop
certification/reuse, the automatic next action is the real offline OPEN campaign,
immediately followed by bundle review and existing Research GUI launch/inspection.
P3 source/CI never runs that production campaign. FINAL_HOLDOUT remains unopened
for strategy selection; no holdout admission is created or consumed.

## P2 additive focused coverage

P1 is accepted/integrated at `e8817e0214074b03d3d9ecd73232b7a2379276b9`,
tree `6937032602b9524ee9db0ddd2056463d418c3aef`. Feature #807 / run
41022636717 / attempt 1 succeeded with canonical FULL; develop #808 / run
41023791454 / attempt 1 succeeded with exact_feature_certification reuse,
stable identity and OVERALL PASS. Failed #806 remains immutable, not rerun.

P2 adds `test_historical_research_desktop_acquisition.py` and its source/CLI to
the existing `arch147-desktop-research-profile` test/Ruff inventory only.
No checkpoint, active CI entry, profile or dispatcher is added. Source-only
tests cover exact credential binding, accepted authority, one-use hidden input,
sanitized errors/repr, canonical source checks before storage/prompt/provider,
tracked/index-only cleanliness, fixed-root absent-first behavior, and synthetic
full acquisition composition through the existing kernel and frozen requests.

Completed synthetic stores must pass full physical integrity plus OPEN loading;
corruption of record, evidence, either manifest/partition, raw bars, corporate
raw or sidecar must fail. The immutable inspection summary exposes no prices
and grants no strategy holdout admission. Tests classify provider/pagination/
transport/shape/validation/persistence/input failures and prove no automatic
retry. New ordering regressions prove evidence and normalized OPEN are present
before `COMPLETE`, and that evidence-write failure remains `STOPPED` with no
success or retry. Static checks preserve historical credential/preflight
classes and exclude host-security, holdout-root, Robinhood and broker paths
from the bridge.

The #809 candidate remains green CI evidence but was source-review rejected for
`ARCH147_P2_PREMATURE_COMPLETE_MARKER_DEFECT`. This corrective child moves
evidence persistence before `COMPLETE`; real acquisition was `NOT_RUN` during
that source-only checkpoint. The accepted subsequent acquisition is below.

## Accepted P2 source and real-data freeze

Acquisition source HEAD `108ba9dee6ad593b3f4128ae44750d9f685ffa0d`, tree
`5652ec3e019766a66a05a9588e79e6cc8c46d70c`. Feature #810 / run 41031424114 /
attempt 1: SUCCESS / canonical FULL. Develop #811 / run 41033045646 / attempt 1:
SUCCESS, `DEVELOP_CERTIFICATION_REUSE=True REASON=exact_feature_certification`,
`IDENTITY_STABLE=True`, `OVERALL=PASS`.

Both real P2 attempts are preserved truthfully:

1. Earlier consumed attempt: `STOPPED`, stage `CREDENTIALS`, raw bars pages 0,
   raw corporate-action pages 0, provider requests 0. This was a credential-stage
   stop, not a provider/data failure. Recovery occurred only after exact read-only
   reconciliation proved that state; no automatic retry is implied.
2. Successful attempt: `a81baba7-7123-45eb-945d-9fb048e24607`.
   `FULL_DATASET_INTEGRITY=PASS`, `OPEN_LOADER=PASS`. Real desktop acquisition and
   these dataset identities are accepted.

| Commitment | Accepted value |
| --- | --- |
| Profile | `desktop-v1` |
| Dataset root | `F:\AI\ai-trading-bot\data\research\desktop-v1` |
| Acquisition HEAD | `108ba9dee6ad593b3f4128ae44750d9f685ffa0d` |
| Acquisition TREE | `5652ec3e019766a66a05a9588e79e6cc8c46d70c` |
| Session authority | `nyse-published-regular-sessions-2016-2026-v1` |
| Authority SHA256 | `7129170764896ad87c8110ec83523c234149393ae53739fed3764ed371ade6e1` |
| Snapshot | `cf9cb708-89ab-589f-a75c-add17dba25a4` |
| Full historical fingerprint | `5ebeb399-b97b-5c72-90c4-b1f764fd3109` |
| OPEN manifest | `19ac19ef-aeed-5fcd-a3ee-7e55cec15796` |
| OPEN normalized SHA256 | `45212bab5eab3c618c6c38d0ae00c8f06fecc4e6b025bc9ff3837920aa545421` |
| OPEN rows | `2012` |
| OPEN first | `2016-01-04T05:00:00+00:00` |
| OPEN last | `2023-12-29T05:00:00+00:00` |
| FINAL_HOLDOUT manifest | `4ec4783c-f419-5189-a9db-7293bf955410` |
| FINAL_HOLDOUT normalized SHA256 | `b0cfaf2177726b52482c4affce73fb391dc121deecbf4d5189a4f5a05bcc1a3b` |
| FINAL_HOLDOUT rows | `706` |
| FINAL_HOLDOUT first | `2024-01-02T05:00:00+00:00` |
| FINAL_HOLDOUT last | `2026-10-23T04:00:00+00:00` |
| Corporate-action SHA256 | `9b6a6dbc45f1c5f12e8576b3bf943dec44868ef43e4ec441f37f8ce7fd9a573b` |
| Acquisition evidence SHA256 | `5b90637cd434402962561a42d398cb925bc069420f5d322b55e40ad3cfaeb8f0` |

Holdout entries above are non-price commitments from accepted P2 integrity.
They confer no strategy-selection access. P3 does not repeat P2 integrity or
read `normalized/holdout/SPY.csv`.

## P3 synthetic source verification

New focused/current modules are `test_desktop_research_campaign.py` and
`test_desktop_research_campaign_gui.py` under `tests/experiments`. Both are
automatically supported FULL modules through existing whole-directory ownership.
They and retained Research GUI regressions join `ARCH147_TESTS`; no new
checkpoint/profile or historical routing is added. Optional Qt tests run locally
with the existing PySide6 GUI extra; pure artifact/model tests need no Qt.

Required tests cover the 255-point ordered grid and UUID5 candidate uniqueness;
every valid configuration exactly once in retained development output;
Development isolation; descending return/ascending drawdown/canonical-parameter
ties; exact deterministic top 32; shortlisted-only walk-forward; accepted
non-overlapping fold chronology; the New York request-boundary projection with
identical P2 bars; real public engine/verifier adapters on synthetic OPEN;
per-fold evidence and descriptive summaries; sensitivity without execution;
immutable bundle/CSV round-trips and identity; malformed/oversized/tampered
artifacts; candidate journal integrity, interruption/resume and conflicts.
Verification's public replay is distinct from a retained grid evaluation.

The source freeze test asserts every accepted P2 binding field without opening
the production dataset. Synthetic storage supplies equivalent structures, and
wrong OPEN hash/manifest, snapshot, evidence, source, session, count and
corporate-action commitments reject. The production binding/output roots cannot
be overridden through the test seam. Ordinary execution is instrumented at
both storage and filesystem opens: neither holdout CSV nor final loader nor
full integrity inspector may be accessed. A fresh-process module inventory
proves provider/credential/native/scheduler adapters are not imported.
Unchanged public exports remain available through lazy package resolution.

GUI coverage verifies campaign loading, all optional fields, truthful measured
turnover, absent metrics, compact-report compatibility, startup/Open Report
composition, filtering, rank sort, 2-to-4 comparison/chart and read-only details.
No GUI starts research, mutates output, opens holdout or grants trading authority.

Run P3 focused tests first with `-p no:cacheprovider` and fresh GUID basetemps
beneath `F:\AI\temp\pytest`. Then affected backtest/walk-forward/desktop,
historical/report/grid, Research GUI and Architecture-147/current-authority
regressions. Complete whole-root `ruff check --no-cache .`,
`ruff format --check --no-cache .`, both diff checks, exact-file atomic commit,
general `ops.ps1 admit` FEATURE/PROSPECTIVE_DEVELOP PASS on identical stable
HEAD/tree, one ordinary push and terminal mapped FULL. FULL is never run locally.
No production campaign or generated real results are part of these checks.

## Scoped export authority successor

The original local preparation stopped at the historical market-data initializer
pin. The user explicitly authorized this bounded successor within the original
single unpublished P3 checkpoint. `READONLY_SOURCE_PINS` and all predecessor
source maps remain unchanged. No source is reclassified CURRENT_MUTABLE.

The original immutable market-data blob remains
`3b5237e5f7a6bbfa34213f48db9aa8dc3f52fe66`. Original exact bytes still pass
historical source acceptance. For the current lazy form only,
`scripts/arch147_source_authority.py` reconstructs the exact allowed AST from
that immutable Git object: only the original two Alpaca import groups are
replaced with a static owner/name map and an exact lazy resolver. Every retained
import and the complete public __all__ list remain exact. The experiments
initializer receives the analogous transformation of its accepted P2 export
surface, blob `9cae91a03fb02e3f2514f0ae8364960ad6021e8c`; no API or domain
implementation is duplicated or replaced.

Architecture-147 current authority requires both exact transformations. The
historical graph permits original bytes or the narrowly proven market-data
successor. Unknown predecessor pins, altered owners, missing names, changed
public exports/resolver, extra imports/statements, rebinding, duplicate resolvers
and eager calls fail closed. The checker parses source/Git objects only and
never imports package implementations or invokes host/provider work.

Focused successor evidence: 26 passed, including both previously blocked
retained regressions and 18 negative initializer mutations, under fresh root
`F:\AI\temp\pytest\arch147-export-authority-c03b838abfb8423992e45e0e4ad94017`.
Direct current authority, historical read-only candidate authority and current
Architecture-147 authority each returned no failures. Final P3 campaign/GUI
focused evidence remains 37 passed (66.89s), under
`F:\AI\temp\pytest\arch147-p3-final-focused-f9b6b8623a174b43b10634930e7252d3`.
The earlier retained run's five bounded root-assumption/GUI compatibility
failures were corrected and focused-verified; the successor resolved the other
two. Preserved local failed attempts were not hidden by source publication.

The complete affected authority/runner/coherence bundle then passed **759**
tests in 131.15s, including source authority, runner core/CI, the read-only
deployment diagnostic and research-strategy production compatibility, under
`F:\AI\temp\pytest\arch147-authority-coherence-2c93a1812bcf437da88a81786543f387`.
Six final CLI guard/verifier tests passed, including the added regression that
rejects price CSV paths before reading. Whole-root Ruff check and format check
(1425 Python files) and both diff checks passed before atomic staging. These
are focused/source gates, not a local canonical FULL attempt.

Starting source remains `108ba9dee6ad593b3f4128ae44750d9f685ffa0d`, tree
`5652ec3e019766a66a05a9588e79e6cc8c46d70c`. The first ordinary atomic child
is `307d73454dd68da8fc2d72e66dd66424ca3d3a79`, tree
`c868731984e80ee12559878bb40241d61efb5d6a`. It passed FEATURE but failed
PROSPECTIVE_DEVELOP admission, IDENTITY_STABLE=True. The one failure was the
Architecture-146-A experiments-initializer source pin: shared blob routing
omitted that initializer despite its strict checker being present and passing.
Preserve the failed admission without alteration at
`F:\AI\temp\arch147-p3-admit-20084df78dcf4bf7ab397605641166d1\arch132-r3n-prepublication-admission\source-gate-20261030T221542.779819Z\report.json`.

The user authorized preserving this unpublished commit and adding one ordinary
P3 export-routing corrective child before the original single push/CI. The
child routes both initializers through the already-reviewed exact checker and
adds an actual registered Architecture-146-A authority regression. No pin,
classification, export policy, registry, branch or effect boundary changes.
No amend, rebase, rewrite or CI rerun occurs. Final source/remote and
terminal CI identities belong to the exact post-publication handoff; this
source document does not self-pin its containing commit or claim acceptance.
Canonical FULL remains GitHub-owned and is not run locally. Production campaign,
FINAL_HOLDOUT price access/admission, credentials, provider, Robinhood, paper,
broker, scheduler, ACL and live effects remain zero throughout source work.
