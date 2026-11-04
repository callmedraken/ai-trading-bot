# Architecture 147 prototype task ledger and acceptance matrix

Exact starting HEAD 04e02042f0bd34b2fb7c603b4dfb1b68c23cf57f; tree
7269c857f86e2b0bec352ff04ecca9788d571e2f. Branch
feature/robinhood-live-prototype-current, canonical F: worktree named in contract.
No real provider/order/credential/data/holdout effects, no paper soak.

| Task | Dependencies | Owner / exclusive surface | Interface | Status / next |
|---|---|---|---|---|
| P00 | exact P6/CI | independent ChatGPT acceptance; Sol reverification | P6 59+1 | ACCEPTED; provider observation separate |
| P01 | P00 | Sol contracts, docs, registry, composition | v1 | SOL_REVIEWED; publication gate next |
| R09 | P01 | Luna external primary-source evidence | 3 fixed arms | SOL_REVIEWED |
| R10 | P01 | Luna comparison_v2.py + exact tests | R10 v1 | SOL_REVIEWED; 14 focused tests |
| R11 | R10 | Luna comparison_campaign_v2.py + exact tests | R11 v1 | SOL_REVIEWED; 49 focused tests |
| R12 | P01/R11 | Luna comparison_bundle_v2.py, research_comparison_service.py + tests | R12 v1 | SOL_REVIEWED; 17 focused tests |
| G20 | P01 | Luna prototype_dashboard/session_page.py + tests | cached DTO v1 | SOL_REVIEWED; 4 focused tests |
| G21 | P01/R12 | Luna prototype_research/strategy_page.py + tests | cached DTO v1 | SOL_REVIEWED; 5 focused tests |
| G22 | P01 | Luna prototype_activity_page.py + tests | cached DTO v1 | SOL_REVIEWED; 3 focused tests |
| D30-D32 | selection/official data | Sol then Luna data/parity | not frozen | BLOCKED on reviewed actual input basis |
| L40-L43 | official exit/budgets | Sol contract then Luna | effect-disabled design | BLOCKED on actual fractional exit capabilities |
| I50-I53 | GUI/service convergence | Sol composition, Luna scenarios/docs | synthetic-only v1 | Synthetic I50/I51 and bounded I52 SOL_REVIEWED; full live scenarios/I53 deferred |
| Q60 | exact source | Sol admission/publication/FULL | registered source-only | RED PRESERVED; bounded registry/admission correction pending |
| Q61 | Q60 | Human native Windows UAT | isolated synthetic | NOT RUN |
| Q62 | accepted source/data/exit | Operator protected readiness | independent runner | NOT RUN |
| Q63 | all required evidence | Sol exact delivery | guarded test package | PENDING |

| Acceptance requirement | Status | Evidence / limitation |
|---|---|---|
| Usable launcher and GUI | SOURCE PASS / HOST NOT RUN | Actual five-page service/GUI tests; native UAT separate |
| Reproducible explicit selection | SYNTHETIC PASS / OFFLINE NOT RUN | 144-cell synthetic topology, frozen policy and strict bundle; real admitted data separate |
| Research/runtime parity | BLOCKED | no runtime binding/data-basis acceptance yet |
| Current valid inputs | BLOCKED | new official-close protected observation not run |
| Entry and exact owned exit | BLOCKED | official fractional exit capability unproven |
| Durable limits/no duplicate effects | PENDING | P6 remains untouched; successor not accepted |
| Stop/kill/restart/reconnect | SYNTHETIC STOP PASS / LIVE BLOCKED | Delayed-reader/worker shutdown proven; successor live recovery not implemented |
| Credential/state isolation | SOURCE PASS / HOST NOT RUN | No production transport dependency; isolated fresh state; no credential construction |
| Exact source certified | BLOCKED / CORRECTION PENDING | Rejected 01adf7f / run 41788777182; new certification required |
| Bounded live test ready | BLOCKED | no live effect authorization |

Readiness labels are NOT GRANTED. This ledger records progress, not acceptance.

## Focused verification and review record

All changes remain one source-only checkpoint. R10/R11/R12 and all five GUI
pages were reviewed at their actual source interfaces. Qualification has one
canonical owner; the GUI adapter imports it. The five qualification metrics are
the continuous-symbol count, minimum/median continuous return, worst continuous
drawdown and median turnover; annual-regime metrics remain evidence only.
Turnover is the stress annual median, return the continuous median and drawdown
the continuous worst case. Research data identity is not mislabeled as an
artifact SHA256. Complete campaigns still contain 144 cells; an explicit
bounded failed/incomplete challenger remains visible without fabricated cells
or metrics and carries only its fixed sanitized status code.

| Focused set | Result |
|---|---|
| CI routing + certification profile tests | 848 passed |
| R10 candidate primitives | 14 passed |
| R11 replay/selection | 49 passed |
| R12 bundle/presentation | 17 passed |
| Final GUI/service/registration convergence | 56 passed; one label assertion fixed and its exact test passed |
| Whole-repository Ruff check and format check | PASS; 1535 files formatted |
| Current authority and source-only prototype authority | PASS, zero failures |
| Git diff whitespace | PASS |

Precommit current/historical batch evaluation reported only task files that were
still being written; all now exist. Clean-candidate admission must independently
prove FEATURE and PROSPECTIVE_DEVELOP after the one candidate commit. Publication
is not complete until one terminal mapped GitHub FULL result; independent source
acceptance remains outside Codex. No local FULL/LEGACY/EXHAUSTIVE was run.

Offscreen layouts were rendered at 1366x768 and 1920x1080 under the external F:
prototype-ui artifact directory. Headless Qt exposes no fonts by default, so
visual QA explicitly loaded the existing Windows Segoe UI font. This is source
layout evidence, not native DPI/keyboard/operational acceptance.

Both bounded current coordination documents and README were reviewed and updated.
Historical/P6 source and consumed evidence were not changed. Automatic review
initially rejected shared registration; the user explicitly approved the exact
review patch and focused fixes before it was applied. No gate bypass occurred.
The L40 exit-notional/price-movement ambiguity is recorded in the contract; no
live implementation is delegated across it.

## Concrete next boundary

Independent ChatGPT exact-source review after terminal mapped FULL, then the
next selected source/data/host step. A real offline comparison needs separate
admission of the existing dataset; it must not reacquire data, rerun the old
30-arm campaign, expand variants or access FINAL_HOLDOUT. Native host commands
are in docs/LIVE_PROTOTYPE_UAT.md and are used only after exact source acceptance.
P00's prepared guarded read-only 59+1 command is an external review artifact;
it has not been executed here. No placement, cancellation or live order is
included in this checkpoint.

## Preserved rejected publication and bounded coverage correction

The first prototype publication is permanently preserved:

    HEAD 01adf7f0808970576b263f158d2dd121b216d733
    TREE bd0fb74dacbd22aa832d991c0876fd14ad478789
    GitHub run 41788777182 / attempt 1 / terminal FAILURE

Source-static and active-tests passed. FULL broad-1/2/4/5/6/7 passed; broad-3
failed 2 of 2560 tests, with 2558 passed and no skips/errors. Both failures
reproduced on that unchanged source in 0.44 seconds:

- `test_core.py::test_registered_profiles_include_current_arch128_gates` omitted
  `arch147-live-prototype` from the exact current registry inventory.
- `test_core.py::test_r2b_common_and_family_requirements_are_independently_selectable`
  lacked a prototype family expectation; the prototype selection omitted the
  established `COMMON_TESTS` contract.

The recorded general admission executed source-authority, CI, profile/lane,
readonly-diagnostic, strategy-compatibility and certification result/source tests,
but not `test_core.py`. Classification: `PREPUBLICATION_COVERAGE_DEFECT`. Work
stopped for independent review; the user then explicitly authorized this bounded
current runner/admission/test-topology correction. The red run is not retried and
its commit is not amended, rebased or rewritten.

Corrective scope is limited to prototype COMMON_TESTS membership, mandatory
infrastructure coherence coverage of `test_core.py`, exact current inventory and
family expectations, an independent literal coverage regression, and current
workflow/coordination documentation. Product/research/GUI/P6/provider/credential/
execution/ownership/kill/data/holdout semantics remain unchanged. No protected
or operational action, paper soak, or further prototype delegation is included.

Before publication, run the requested affected runner/authority/certification and
two existing coherence modules, plus the prototype checkpoint test selection.
Run whole-repository Ruff check/format and diff checks. On one new clean ordinary
correction commit, `ops.ps1 admit` must prove FEATURE and PROSPECTIVE_DEVELOP PASS,
stable identity, and recorded `executed_tests` containing `test_core.py`. Absence
is STOP before push. One ordinary push owns one new terminal mapped GitHub FULL;
no local canonical FULL or unchanged rerun. Independent exact-source review still
precedes any integration or next prototype work.

The correction's initial ten-module focused run passed 1435 tests and exposed
one further assertion in the formerly short-circuited inventory test: the
prototype Ruff tuple must contain `scripts/checkpoint_runner.py`. That same
current inventory test also needs the explicit prototype branch expectation.
Both were corrected within the runner/test contract; the exact failing test
then passed (1 passed). No product source changed. The newly added regression
also rejected a process-local removal of `test_core.py` from the coherence tuple.
The restored tuple was verified afterward; no source mutation was used for that
probe. Final current authority, whole-repository Ruff check/format (1535 files)
and whitespace checks passed before the ordinary correction candidate.

The registered prototype verification and exact clean-candidate admission remain
required after the candidate commit. The implementation handoff supplies that
candidate's exact HEAD/tree/parent, report identities/selection and terminal CI;
the rejected predecessor above must never be mistaken for the corrective source.
