# Architecture 147 — Desktop product pivot validation

Status: CURRENT P4 ACCEPTED/INTEGRATED validation; no-network runtime smoke pending; P2/P3 accepted and real-run complete.

## Accepted P3 closeout and real result

P3's public-helper correction is accepted/integrated at
`b9d52c4934517ea67b8c18f4d6f967bfd576ecf7`, tree
`755054f71489491f0214489e35827ba2bb51c74e`. Develop #814 / run
`41151276520` / attempt 1 is SUCCESS, with exact-feature certification reuse,
IDENTITY_STABLE=True and OVERALL=PASS. The accepted real campaign and GUI
inspection reported by the operator contain 255 candidates, 32 shortlisted
walk-forward results and LOADED / 255 GUI rows:

    campaign_id 11d55269-7e13-57aa-a3bf-1e20e486204b
    bundle_id b771cf92-a09f-5f18-86d3-e03b65e04fe9
    bundle SHA256 b883298824f346bca0cf41e83b214f35229f741aab784130602ed7eeea66f66d

Development rank 1 remains research-only candidate
`2e0eea52-0f36-5261-976b-c3e6ea299acf` (35/50): return `0.094971015`,
drawdown `0.027108157815096180365937479989239356275125079838597`,
walk-forward returns `0.066993175` and `-0.065377215`, median `0.000807980`,
maximum walk-forward drawdown `0.13670401`.

The descriptively strongest observed minimum/median-fold-return and maximum
fold-drawdown configuration is candidate
`cc8b7b1d-c480-5fb9-9836-d7230ea2690d` (55/100): Development return
`0.081506445`, drawdown
`0.028098358511127682090840288708938760639881545456235`, fold returns
`0.064235075` and `0.015644635`, minimum `0.015644635`, median `0.039939855`,
maximum walk-forward drawdown `0.03660648`. These are descriptive observations,
not a qualification policy. `qualification_policy` remains null. Neither
candidate is promoted or selected for P4 trading; no PAPER_CANDIDATE, production
strategy authority, trading eligibility or final-holdout admission exists.
FINAL_HOLDOUT remains sealed. P4 implementation never rereads production data.

## P4 source checkpoint and verification contract

P4 uses `feature/research-desktop-supervisor-current` in the verified main
checkout, with `arch147-desktop-supervisor`, no preflight/execute dispatcher,
and GitHub-owned FULL. The branch matches the existing reviewed
`feature/research-*` workflow trigger. One atomic candidate, both-context
admission, one ordinary push and one terminal CI result precede independent
ChatGPT exact-source review. No local canonical FULL, PR, merge, production
GUI/worker smoke or provider/broker effect occurs during this source checkpoint.

Focused tests cover separate concurrent RUNNING workers, one pair per Start,
duplicate Start, partial-start rollback, Stop during startup, idempotent Stop,
trading reconciliation before STOPPED, closure failures/timeouts, health failure
propagation, no restart, cached GUI health, responsive Qt controls, async
close/reconcile, refused close with unresolved workers, queue bounds, immutable
P3 artifact verification/display, malformed/conflicting journal replay, stale
ownership, clean reopen and sanitized diagnostics. Synthetic P3 fixtures prove
the existing Research page still loads its accepted campaign type. Historical
Supervisor presentation tests continue to require zero active controls and
unchanged recorded-only/promotion semantics on that historical page.

The literal whole-root Ruff commands were attempted. Lint passed, but formatter
discovery hit preserved historical `.pytest-*-temp` directories and generated
fixtures, producing access errors/a Ruff panic. Those artifacts were untouched.
Both combined non-mutating Ruff phases then passed on `src scripts tests`, with
a Git inventory proof that these roots cover every tracked Python file and all
new P4 Python files. Diff checks passed. No persistent exclusion or historical
artifact cleanup was added; GitHub certifies the clean checkout normally.

A fresh-process source-owned import probe proves the P4 composition loads no
Alpaca, Robinhood, credential, scheduler, host or native adapter. GUI historical
adapter exports retain the original owning objects and public `__all__`, but
load only when requested. The compact-report parser is deferred until explicit
legacy compact selection. Current `DesktopGuiService` selects P3 campaign
bundles only; the existing normal read-only GUI retains compact-report support.
The current worker imports only the public bounded bundle reader, never the
campaign runner, final-holdout loader, full integrity inspector or admission.
No trading-domain state or strategy configuration is supplied to research.

Source authority keeps P3 registered and Architecture 146 retired. P4 is the
new current route. Existing authority classifies both Architecture-134 workflow
projection functions as CURRENT_MUTABLE; historical AST pins reconstruct their
immutable Git objects. Two narrow current-owner projections remove the P4 row
before predecessor comparison. Historical pins/catalog/dispatch and function
bindings remain unchanged. These current-owner changes use the existing
classification and receive explicit reconstruction/topology regressions.

Production journal/lock lives outside source at
`F:\AI\desktop-bot-state\p4\lifecycle.jsonl`. Runtime generation is an ordinary
local chronology counter; UTC records contain only bounded enums and facts.
Unresolved state never becomes a clean Stop. Recovery is visible and manual;
P4 never deletes prior evidence, force kills, auto-restarts or updates itself.
See the architecture document for full lifecycle and close policy.

P4 source is accepted/integrated at
`e5e800ad99da8dd1c09fa36202d5ff8b648c1daf`, tree
`1d2f57afb1d5cddc9487352519f92cced5554f9d`. Original P4 source
`5fb96f758b6f2bb2af302f5725fdf7ad03bfc138` produced feature CI #815 /
run `41172155619`, which is preserved terminal red because Qt-backed tests
were collected without PySide6 in source-gate test jobs. That was a CI
dependency-coverage defect, not a P4 runtime semantic failure.

Corrective child `e5e800ad...` changed only the source-gate workflow dependency
coverage and its deterministic runner regression. Its focused verification
reported 1161 passing focused cases plus the targeted CI regression, whole-root
Ruff/diff PASS, FEATURE PASS, PROSPECTIVE_DEVELOP PASS and stable identity.
Feature CI #816 / run `41175037719` / attempt 1 is terminal SUCCESS with
canonical FULL. After exact fast-forward integration, develop CI #817 / run
`41177055270` / attempt 1 is terminal SUCCESS with
`DEVELOP_CERTIFICATION_REUSE=True` for `exact_feature_certification`.
Source-static and source-gates passed; active-tests, fallback full-tests,
Robinhood certification and all seven canonical FULL lanes were skipped.
No duplicate canonical broad run was performed.

Prepublication P4 local evidence also includes application/GUI batches of 87 and
38 tests, a 634-test shared checkpoint/source-authority and retained Supervisor
integration batch, and the earlier 255-case overlapping registry/profile batch.
All 79 develop-routed static checkpoint authorities plus current authority
returned no failures. These are focused/static checks, not another local
canonical FULL.

No production GUI/worker runtime, journal, credentials, network, provider,
broker, account, scheduler, ACL or holdout effect occurred during source
implementation, admission, CI or integration. The source-owned launcher now
supports exactly one reviewed no-network Start/Stop smoke. That smoke remains
NOT_RUN; P5 architecture work follows a successful smoke. LIVE remains disabled.

## Preserved P1–P3 source implementation chronology

The following records describe their original source-only boundaries, before
the subsequently accepted P3 integration and real run above.

P3 includes the explicitly authorized scoped lazy-export authority successor;
historical pins and security classification remain unchanged. The original
source and the exact reviewed transformation are separately validated.
Feature CI #809 is preserved green pre-correction source evidence,
but exact source review rejected its P2 candidate as
`ARCH147_P2_PREMATURE_COMPLETE_MARKER_DEFECT`. The #810 successor was accepted;
the separately reviewed real acquisition subsequently succeeded. No old
Architecture-146 preflight was restored.

The preserved P3 initializer-routing candidate is exact source
`06f6e2181863ac000c2f94a56c2d342a895211c7`, tree
`f899294eb96f4a397302721ae94307dcda26d938`; GitHub #812 / run `41138345080` /
attempt 1 is terminal SUCCESS and remains unchanged. ChatGPT exact-source
review found `P3_PRIVATE_HELPER_BOUNDARY_DEFECT`: production CLI/GUI modules
imported private helpers from other project modules. The current corrective
child exposes one public bounded campaign-bundle loader and owns the tiny GUI
path validation/presentation operations locally. `develop` remains the
accepted P2 `108ba9dee6ad593b3f4128ae44750d9f685ffa0d`; #812 is not rerun and
no real campaign ran. The initializer authority proof, P3 grid/ranking/
shortlist/fold/identity/canonical-byte semantics, OPEN-only behavior, GUI
result fields and FINAL_HOLDOUT seal are unchanged.

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

That first child remains preserved as immutable source/admission history. The
new ordinary child is a source-review correction only: it removes production
cross-module underscore dependencies without changing checkpoint registration,
profile, initializer authority, accepted P3 research semantics, GUI result
fields or effect boundaries. No amend, rebase, rewrite or #812 rerun occurs.
The child performs no production campaign, FINAL_HOLDOUT access/admission,
credential/provider/Robinhood/paper/broker/scheduler/ACL/live effect. Its
terminal CI result and exact final identity are recorded only after publication
and independent ChatGPT review.
Canonical FULL remains GitHub-owned and is not run locally. Production campaign,
FINAL_HOLDOUT price access/admission, credentials, provider, Robinhood, paper,
broker, scheduler, ACL and live effects remain zero throughout source work.
