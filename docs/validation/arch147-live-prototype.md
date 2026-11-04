# Architecture 147 prototype task ledger and acceptance matrix

Exact accepted D33 source HEAD `543dc6b45b4a20f53ae28646a0c82b9b1cd7b824`;
tree `9981cca7cc1f01fae778cbe9e5d189126d3a885c`. Branch
`feature/robinhood-live-prototype-current`, canonical F: worktree named in
contract. Feature FULL `41903739374`, attempt 1, and develop integration
`41905183980`, attempt 1, both succeeded. No real provider/order/credential/
data/holdout effects or paper soak; D33 provider observation remains NOT_RUN.

D30 ACCEPTED: dataset `d5aa8ed7-b5cd-53a3-8671-5370f976e8e3`, SHA
`ebe1839d510db0f24f58f9ebe02b7efb09221d4b8c06c23122f84912c3225214`, basis
`ALPACA_ALL_ADJUSTED_PRICE_V1`. D31 exact bundle ACCEPTED: campaign
`9b2a000e-3adc-50f4-ab47-2aa90665e3c9`, bundle
`f01a39a7-0a65-55bb-9d38-608b1ce0bd21`, SHA
`94870e0e0e10de16f7e98e7cfea2e2c84458a15e6f1d2665cd8a5dc7e404fc11`, result
`NONE_QUALIFIES`, retained control `BASE_MA35_50_V1`, ID
`21158358-75be-5597-b940-5bccdda1429c`. D32 PARTIAL_PASS: strategy math and
research binding PASS; live data-basis parity BLOCKED by
`DATA_BASIS_MISMATCH`; 2,516 comparisons had zero mismatches. D33 chooses
Alpaca all-adjusted current signal data and Robinhood execution/custody, with
no fallback and no provider observation yet.

Published D33 predecessor, preserved but rejected by exact-source review before
integration:

    HEAD 2fd6d764e56226d7ef54c458f6f40b14af3b5b20
    TREE f44c9e3455b712572f8c6c022883eadb3ebd9c56
    PARENT b7d42863d24958d1ce0fcf9f51eff67397f94240
    GitHub run 41822221848 / attempt 1 / terminal SUCCESS
    classification EXACT_SOURCE_REVIEW_REJECTED

Current corrective child scope: exact feature/develop admission before provider
authority, with live origin branch heads resolved read-only through the existing
source-owned `_remote_branch_head` helper rather than local remote-tracking
refs. The source-owned current clock, same-day completed-session cutoff,
invalid-clock sanitization, focused regressions, and coordination truth remain
unchanged.

Operational review found repeated pre-dispatch stale-tracking, `FETCH_HEAD`,
and ref-lock failures; none entered credentials or the provider, so none
consumed a D33 observation. Local stale develop/tracking-ref state is separate
host hygiene and is not provider authority. The cause of local Git write
failures remains unresolved; no ACL or sandbox-cause claim is made.

| Task | Dependencies | Owner / exclusive surface | Interface | Status / next |
|---|---|---|---|---|
| P00 | exact P6/CI | independent ChatGPT acceptance; Sol reverification | P6 59+1 | ACCEPTED; provider observation separate |
| P01 | P00 | Sol contracts, docs, registry, composition | v1 | IMPLEMENTATION/SOURCE ACCEPTED; integrated through 543dc6b4 |
| R09 | P01 | Luna external primary-source evidence | 3 fixed arms | SOL_REVIEWED |
| R10 | P01 | Luna comparison_v2.py + exact tests | R10 v1 | SOL_REVIEWED; 14 focused tests |
| R11 | R10 | Luna comparison_campaign_v2.py + exact tests | R11 v1 | SOL_REVIEWED; 49 focused tests |
| R12 | P01/R11 | Luna comparison_bundle_v2.py, research_comparison_service.py + tests | R12 v1 | SOL_REVIEWED; 17 focused tests |
| G20 | P01 | Luna prototype_dashboard/session_page.py + tests | cached DTO v1 | SOL_REVIEWED; 4 focused tests |
| G21 | P01/R12 | Luna prototype_research/strategy_page.py + tests | cached DTO v1 | SOL_REVIEWED; 5 focused tests |
| G22 | P01 | Luna prototype_activity_page.py + tests | cached DTO v1 | SOL_REVIEWED; 3 focused tests |
| D30 | selection/official data | Sol then Luna data/parity | accepted dataset identity | ACCEPTED; exact dataset and all-adjusted price basis frozen |
| D31 | selection/official data | Sol then Luna data/parity | exact research bundle | ACCEPTED; `NONE_QUALIFIES`, control retained, non-live |
| D32 | selection/official data | Sol then Luna data/parity | parity evidence | PARTIAL_PASS; math/binding PASS, live basis BLOCKED by `DATA_BASIS_MISMATCH` |
| D33 | current signal-data successor | Sol source/operator, exact review | Alpaca all-adjusted 60-session inputs | ACCEPTED SOURCE / CORRECTIVE CHILD IN PROGRESS; live-read-only authority correction; no provider observation |
| L40-L43 | official exit/budgets | Sol contract then Luna | effect-disabled design | BLOCKED on actual fractional exit capabilities |
| I50-I53 | GUI/service convergence | Sol composition, Luna scenarios/docs | synthetic-only v1 | Synthetic I50/I51 and bounded I52 SOL_REVIEWED; full live scenarios/I53 deferred |
| Q60 | exact source | Sol admission/publication/FULL | registered source-only | P01 implementation/corrections/docs integrated through 543dc6b4; corrective child pending |
| Q61 | Q60 | Human native Windows UAT | isolated synthetic | NOT RUN |
| Q62 | accepted source/data/exit | Operator protected readiness | independent runner | NOT RUN |
| Q63 | all required evidence | Sol exact delivery | guarded test package | PENDING |

| Acceptance requirement | Status | Evidence / limitation |
|---|---|---|
| Usable launcher and GUI | SOURCE PASS / HOST NOT RUN | Actual five-page service/GUI tests; native UAT separate |
| Reproducible explicit selection | SYNTHETIC PASS / OFFLINE NOT RUN | 144-cell synthetic topology, frozen policy and strict bundle; real admitted data separate |
| Research/runtime parity | D32 PARTIAL_PASS | strategy math and research binding PASS; current data-basis observation remains pending |
| Current valid inputs | BLOCKED | D33 source exists; no Alpaca provider observation has been performed |
| Entry and exact owned exit | BLOCKED | official fractional exit capability unproven |
| Durable limits/no duplicate effects | PENDING | P6 remains untouched; P01 source is accepted but durable runtime/reconciliation evidence remains unaccepted |
| Stop/kill/restart/reconnect | SYNTHETIC STOP PASS / LIVE BLOCKED | Delayed-reader/worker shutdown proven; successor live recovery not implemented |
| Credential/state isolation | SOURCE PASS / HOST NOT RUN | No production transport dependency; isolated fresh state; no credential construction |
| Exact source certified | CORRECTIVE CHILD PENDING | D33 predecessor run 41822221848 was terminal green but exact-source rejected; child requires fresh admission and mapped FULL |
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
| D33 source-admission correction focused tests/checks | PASS locally | D33 45 passed/2 host-evidence skipped; `_remote_branch_head` helper 2 passed; current source-authority 59 passed; no P6 source changed |

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

Complete exact-source review of this bounded corrective child, stage only the
intended files, create one normal atomic commit, push once, and wait for its
single mapped `arch147-live-prototype` FULL run. Do not integrate the child
before independent acceptance. The accepted integrated source is
`543dc6b4`; no local tracking-ref refresh is a D33 prerequisite.

After acceptance, exact ff-only integrate with certification reuse, verify
feature/develop identities, and run one fresh source-admitted D33 read-only
observation using the source-owned current UTC clock. That observation uses one
Alpaca request, no Robinhood call, no runtime binding, no campaign, no
FINAL_HOLDOUT access, and no paper/broker/live effect. It can close the
data-basis blocker but cannot authorize a live order. Q61 remains NOT RUN;
L40-L43 remain unresolved. Do not insert a paper soak between D33 and L40-L43.
The old P6 guarded 59+1 path remains preserved predecessor evidence.

## Preserved rejected publication and accepted corrections

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

The prepublication plan required the affected runner/authority/certification and
coherence coverage, whole-repository Ruff/diff checks, clean-candidate FEATURE and
PROSPECTIVE_DEVELOP admission, one ordinary correction push and one mapped FULL;
it prohibited a local canonical FULL and unchanged reruns.

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

The registry/admission correction completed at `1f2f42b` / tree
`87a4eb9e27ee1b5a209eda93ad198f650abbfed3`, with GitHub run `41792913721`,
attempt 1, terminal SUCCESS. The frozen-P01 semantic correction then completed
at `3218931` / tree `96784106879285736ee412e887319b48f2c64281`, with GitHub run
`41799106223`, attempt 1, terminal SUCCESS across source-static, active-tests and
broad-1 through broad-7. Independent review accepted the implementation/source
semantics, and those P01 corrections/docs were later integrated through
`b7d42863d24958d1ce0fcf9f51eff67397f94240`. The D33 predecessor above remains
historical terminal-green evidence and must never be mistaken for the current
corrective child.
