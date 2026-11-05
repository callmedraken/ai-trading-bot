# Architecture 147 prototype task ledger and acceptance matrix

Current D34 source-only successor starts from accepted/integrated D33 source
HEAD `fad65c9f4eab5bc1de4e154fdf0f59e397bc943a`; tree
`beab205abcc045fad38625ff73bb48affea9a0e9`. Branch
`feature/robinhood-live-prototype-current`, canonical worktree
`F:\\AI\\worktrees\\ai-trading-bot-live-prototype-current`. Feature FULL
`41924058186`, attempt 1, and develop source-gate `41936617801`, attempt 1,
succeeded; develop reused the exact feature certification.

D30 ACCEPTED: dataset `d5aa8ed7-b5cd-53a3-8671-5370f976e8e3`, SHA
`ebe1839d510db0f24f58f9ebe02b7efb09221d4b8c06c23122f84912c3225214`, basis
`ALPACA_ALL_ADJUSTED_PRICE_V1`. D31 exact bundle ACCEPTED: campaign
`9b2a000e-3adc-50f4-ab47-2aa90665e3c9`, bundle
`f01a39a7-0a65-55bb-9d38-608b1ce0bd21`, SHA
`94870e0e0e10de16f7e98e7cfea2e2c84458a15e6f1d2665cd8a5dc7e404fc11`, result
`NONE_QUALIFIES`, retained control `BASE_MA35_50_V1`, ID
`21158358-75be-5597-b940-5bccdda1429c`. D32 PARTIAL_PASS: strategy math and
research binding PASS; live data-basis parity remains BLOCKED by
`DATA_BASIS_MISMATCH`; 2,516 comparisons had zero mismatches. Alpaca
all-adjusted current signal data and Robinhood execution/custody remain
separate providers with no fallback.

D33's real read-only attempt is CONSUMED / BLOCKED / NO RETRY. Evidence is
`F:\\AI\\temp\\arch147-d33-alpaca-observation-576b4b5c8f7b41548df7b822c44c74de\\evidence.json`,
SHA-256 `b767727712e4634950be8a6ba8f43522910d037987824ad33cb7c20c8eab95ec`,
1,999 bytes, observation `2026-11-04T23:59:08.218729Z`, credentials `1`,
provider requests `1`, selected sessions `60`, and zero prohibited-effect
counters. The exact provider rejection subtype is unavailable because D33
discarded it. The request end exceeded observation through end-of-calendar-day
semantics; this is a source-contract defect, not proof of the provider's exact
rejection cause.

D34 is an additive successor, not a D33 retry. It derives one exact published
regular close before credential/provider construction and uses that same cutoff
for the request and `CompletedSignalInputs`. The D33 CLI is retired; D34 uses
`trading_bot.live_prototype.alpaca_signal_recovery_operator` and evidence schema
`arch147-d34-alpaca-signal-observation/v1`. Implementation and tests are
source-only and perform no credentials, network, Alpaca, Robinhood, broker,
paper, live, campaign, runtime-binding, or FINAL_HOLDOUT effect.

The preserved D34 predecessor is
`9981bf47072d35381a2e5b6f187c9497e9dbed5a` / tree
`a8d2b4fb4a40039b74768b44fd0198dc87bc55f3`; mapped run `41950572892`, attempt
1, was terminal SUCCESS, but exact-source review rejected it before develop
integration. Review found incomplete blocked-result attempt-count invariants
and an operator-level fallback that could fabricate zero credential/provider
counts after an escaped failure. No D34 real observation occurred. The current
corrective child changes only those accounting/evidence semantics and focused
tests/docs; the consumed D33 incident remains unchanged.

Published D33 predecessor, preserved but rejected by exact-source review before
integration:

    HEAD 2fd6d764e56226d7ef54c458f6f40b14af3b5b20
    TREE f44c9e3455b712572f8c6c022883eadb3ebd9c56
    PARENT b7d42863d24958d1ce0fcf9f51eff67397f94240
    GitHub run 41822221848 / attempt 1 / terminal SUCCESS
    classification EXACT_SOURCE_REVIEW_REJECTED

Current D34 corrective-child scope: attempt-accounting and evidence truthfulness
at the existing additive recovery source, with exact feature/develop admission
before provider authority, live origin branch heads resolved read-only through
the existing source-owned `_remote_branch_head` helper, one source-owned UTC
clock, exact published-close cutoff, and sanitized failure diagnostics. The
consumed D33 evidence and preserved D34 predecessor remain immutable and are
not replayed or relabeled.

The D34 implementation uses no credential, provider, network, Robinhood, broker,
paper, live, campaign, runtime-binding, or FINAL_HOLDOUT effect. Any future
provider observation is a separate reviewed boundary after publication,
integration, mapped FULL, and exact-source acceptance.

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
| D33 | consumed predecessor incident | preserved immutable evidence | one Alpaca all-adjusted observation | CONSUMED / BLOCKED / NO RETRY |
| D34 | consumed-D33 recovery successor | Sol source/operator, exact review | Alpaca all-adjusted 60-session inputs with published-close cutoff | CORRECTIVE CHILD IN PROGRESS; future observation separately reviewed |
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
| Current valid inputs | BLOCKED | D33 is consumed/blocked; D34 source correction is not yet observed |
| Entry and exact owned exit | BLOCKED | official fractional exit capability unproven |
| Durable limits/no duplicate effects | PENDING | P6 remains untouched; P01 source is accepted but durable runtime/reconciliation evidence remains unaccepted |
| Stop/kill/restart/reconnect | SYNTHETIC STOP PASS / LIVE BLOCKED | Delayed-reader/worker shutdown proven; successor live recovery not implemented |
| Credential/state isolation | SOURCE PASS / HOST NOT RUN | No production transport dependency; isolated fresh state; no credential construction |
| Exact source certified | D34 CANDIDATE PENDING | D33 source is accepted/integrated; D34 requires exact-source review, admission, and mapped FULL |
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
| D34 corrective-child focused tests/checks | PASS locally | 62 D34 input/operator tests; no real observation; no P6 source changed |

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

Complete exact-source review of the D34 candidate, stage only intended files,
create one normal atomic commit, push once, and wait for its single mapped
`arch147-live-prototype` FULL run. Do not invoke D33 or D34 during this source
checkpoint. After acceptance, exact ff-only integration and certification reuse
come before one separately labeled, source-admitted D34 successor observation.
That future observation has one Alpaca request, no Robinhood call, no runtime
binding, no campaign, no FINAL_HOLDOUT access, and no paper/broker/live effect.
It may close the D32 data-basis blocker but cannot authorize a live order.
Q61 remains NOT RUN; L40-L43 remain pending. Do not insert a paper soak.

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
