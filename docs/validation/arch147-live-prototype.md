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
| Q60 | exact source | Sol admission/publication/FULL | registered source-only | PENDING |
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
| Exact source certified | PENDING | prototype not published/certified |
| Bounded live test ready | BLOCKED | no live effect authorization |

Readiness labels are NOT GRANTED. This ledger records progress, not acceptance.

## Focused verification and review record

All changes remain one source-only checkpoint. R10/R11/R12 and all five GUI
pages were reviewed at their actual source interfaces. Qualification has one
canonical owner; the GUI adapter imports it. Turnover is the stress annual
median, return the continuous median and drawdown the continuous worst case.
Research data identity is not mislabeled as an artifact SHA256.

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
