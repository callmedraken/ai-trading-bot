# Architecture 132-R2 — Test Suite Rationalization Validation Plan

## 2026-10-07 — Architecture 132-R2 COMPLETE; FULL CERTIFIED

Architecture 132-R2 test-suite rationalization is **ACCEPTED and CLOSED**.

Final certified checkout:

```text
BRANCH  feature/test-suite-rationalization-132r2
HEAD    9d6e1b1c376c5f366e2dbac43d430b5683b7ad28
TREE    792bbc7b5010cdcbfa833ef548a672f8f23ec910

R2-B2 implementation
HEAD    ff21c05b93d862d2299dd1574c2f931b9ea5acb5
TREE    3e714d054516dfd156def89c2a21e51b85e8861e
CI      #294 / 37731218114 SUCCESS

R2-B2 acceptance/policy source gate
CI      #296 / 37732562660 SUCCESS
```

Fresh FULL current-product certification on the exact final checkout:

```text
profile     full
broad-1     67 modules / 3,259 cases / 3,257 passed / 2 skipped
broad-2     69 modules / 2,632 cases / 2,631 passed / 1 skipped

TOTAL       136 modules
cases       5,891
passed      5,888
skipped     3
failed      0
errors      0
wall        259.314 s
evidence    F:\AI\temp\certification\arch132-r2b2-full-9d6e1b1
```

The certification runner admitted and re-admitted the exact clean source,
current live feature ref and current live develop ref, then completed whole-
repository Ruff check, Ruff format check and git-diff check through the accepted
FULL profile. No protected opt-in was enabled.

### Final R2 outcome

Routine current-product source CI is restored to its historical operating
envelope without reducing logical authority coverage:

```text
                         pre-R2 / regression     final R2-B2
routine checkpoints              44                  36
active TEST_PATHS                68                  47
active RUFF_PATHS               150                 127
source-CI pytest              696-790 s          198.14 s
source-CI workflow             >13 min              250 s
```

Historical successful non-docs source-gate medians were 188.41 s pytest and
242 s workflow. Final R2-B2 is +5.16% and +3.31% respectively, inside the
historical operating range.

All accepted R2-B logical test identities remain, with additional proof cases.
Production authority code/pins/chaining were not weakened. The final
certification topology is:

```text
FULL        136 modules
ROBINHOOD    63 modules
LEGACY      205 modules
EXHAUSTIVE  341 modules

required FULL       122 modules
required ROBINHOOD   49 modules

ACTIVE_CI_CHECKPOINTS   36
RETAINED_CHECKPOINTS     8
```

### R2-C / R2-D disposition

R2-C retained-source/test provenance cleanup and R2-D source-gate
parallelization are **deferred maintenance**, not blockers for current product
work.

- R2-C remains useful before any deliberate historical source deletion, but
  routine current-product CI no longer executes the retained Architecture
  128/130 checkpoints or retained runner contracts.
- R2-D is not justified as an immediate prerequisite now that serial routine CI
  is back to the historical ~4-minute end-to-end regime. Parallelization may be
  revisited if current-product growth again makes the measured serial gate
  materially expensive.

Do not delete retained production/security primitives merely because R2 is
closed. Any future R2-C removal still requires provenance classification
`KEEP_COMPAT`, `DISTILL_INVARIANTS`, or `DELETE_WITH_SOURCE`.

### Project resumes Architecture 133

The test-suite interlude no longer blocks Architecture 133. Resume from the
already source-accepted Architecture 133-M credential-free stage diagnostic.
Q133-2V remains consumed and non-retryable. Q133-3 scheduler installation and
Q133-4 unattended wake remain unauthorized. The real 133-M diagnostic remains a
separately protected one-attempt read-only boundary and requires fresh explicit
authorization before invocation.

Production/live real-money placement remains **NO-GO**.

## 2026-10-07 — Architecture 132-R2-B2 SOURCE ACCEPTED; FULL certification next

Architecture 132-R2-B2 is **SOURCE/TOPOLOGY ACCEPTED**.

Accepted executable/test implementation:

```text
BRANCH  feature/test-suite-rationalization-132r2
HEAD    ff21c05b93d862d2299dd1574c2f931b9ea5acb5
TREE    3e714d054516dfd156def89c2a21e51b85e8861e
CI      #294 / 37731218114 SUCCESS
```

Implementation-evidence docs descendant before this closeout:

```text
HEAD    ad43c9c45b3ff10e33833c49823fc74cd6b2ba91
TREE    e1e7485d9a607194ac8d142af87c57f4d2c6f15e
CI      #295 / 37731687297 SUCCESS
```

ChatGPT exact-source review found no correction required. The implementation
diff changes only:

```text
tests/runtime/checkpoint_runner/helpers.py
tests/runtime/checkpoint_runner/test_arch131.py
tests/runtime/checkpoint_runner/test_arch133_a_g.py
```

No production `src/`, source-gate workflow, checkpoint registration,
production authority function, certification runner, profile ownership, source
pin or protected capability changed.

Independent JUnit identity comparison against accepted R2-B source gate #291
proves all **4,612** prior testcase identities remain in R2-B2, with **zero**
missing and exactly **32** new proof cases. Those additions are 21 copied-closure
baseline PASS cases, ten predecessor PASS/rejection cases for five real G/H
edges, and one complete transparent real-chain PASS trace.

The only newly isolated predecessor edges are:

```text
131-G agentic account -> direct MCP
131-G agentic account -> MCP schema
131-G agentic account -> paper cycle
131-H paper operator  -> 131-G agentic account
131-H paper operator  -> Windows OAuth
```

Isolation is confined to wholly local G/H source mutations. The real local
authority body still executes. Separate tests prove each predecessor is invoked
exactly once, predecessor rejection propagates fail-closed, and the complete
real H -> G -> direct MCP -> schema -> paper-cycle plus Windows-OAuth chain
passes on accepted source. G transport/adapter/registration mutations, H
predecessor-source/registration/workflow mutations, and all 30 H-M
workflow/order cases retain real chaining.

Terminal source evidence was independently checked from artifact
`checkpoint-source-gate-evidence`:

```text
CHECKPOINTS       36
TEST_PATHS        47
RUFF_PATHS       127
pytest            4,643 passed / 1 skipped / 0 failed / 0 errors
pytest wall       198.14 s
command elapsed   199.42576060000002 s
workflow elapsed  250 s
identity stable   true
all source/static commands exit 0
```

R2-B2 therefore restores routine source CI to the historical operating envelope
without reducing logical coverage. Pytest is 5.16% above the historical median
188.41 s and end-to-end workflow time is 3.31% above the historical median
242 s; timing remains diagnostic only.

Certification topology is unchanged from accepted R2-B:

```text
FULL / ROBINHOOD modules      136 / 63
LEGACY / EXHAUSTIVE modules   205 / 341
required FULL / ROBINHOOD     122 / 49
active / retained checkpoints 36 / 8
```

The deferred R2-B certification obligation is now due. The immediate next gate
is exactly one fresh **FULL current-product certification** on the clean current
R2 branch checkout. R2-C, R2-D and real Architecture-133 protected work remain
paused until FULL is reviewed.

Q133-2V remains consumed/non-retryable. Q133-3 and Q133-4 remain unauthorized.
Production/live real-money placement remains **NO-GO**.

## 2026-10-07 — Architecture 132-R2-B2 terminal source CI green; review/FULL pending

R2-B2 is implemented and its source gate is terminal **SUCCESS**. This is
implementation evidence only; ChatGPT exact-source acceptance and the deferred
FULL current-product certification remain pending.

```text
BRANCH  feature/test-suite-rationalization-132r2
HEAD    ff21c05b93d862d2299dd1574c2f931b9ea5acb5
TREE    3e714d054516dfd156def89c2a21e51b85e8861e
CI      #294 / 37731218114 SUCCESS
```

The change is confined to three checkpoint-runner test/helper files. Twenty
copy helpers now defer accepted-source PASS checks to 21 dedicated cases rather
than repeating them before every mutation. Five Architecture-131 G/H predecessor
edges are isolated only for wholly local source mutations; separate invocation,
rejection-propagation and complete real-chain PASS proofs remain. All original
mutation matrices and all 4,612 prior CI case identities remain; 32 proof cases
are added. No production source, authority implementation/chaining, pin,
registration, workflow, certification ownership or module topology changed.
The 30 H-M workflow/order cases retain real chaining.

```text
active / retained checkpoints   36 / 8 (exact order unchanged)
TEST_PATHS / RUFF_PATHS          47 / 127
FULL / ROBINHOOD modules         136 / 63
LEGACY / EXHAUSTIVE modules      205 / 341
required FULL / ROBINHOOD        122 / 49 (accepted R2-B migrated baselines)
focused tests                   1,627 passed / 0 failed
source CI                       4,643 passed / 1 skipped / 0 failed / 0 errors
pytest wall                     198.14 s
pytest command elapsed_seconds  199.42576060000002
workflow end-to-end             250 s
```

Observed pytest time decreased 43.72% from R2-B's 352.07 s;
workflow time decreased 38.42% from 406 s. Relative to historical
medians (188.41 s / 242 s), pytest is +5.16% and workflow is
+3.31%. Timing is diagnostic and has no PASS/FAIL threshold.
Recorded testcase time totals 192.039 s; checkpoint-runner
infrastructure contributes 175.592 s / 1325 cases /
91.44%, and other tests contribute 16.447 s.

See the R2-B2 terminal implementation report in
`docs/validation/arch132-r2-test-suite-rationalization-plan.md` for the exact
isolated edges, coverage accounting, active path unions, JUnit module timings,
commands, deviations and all top-100 durations. Source evidence is retained in
[CI #294](https://github.com/callmedraken/ai-trading-bot/actions/runs/37731218114) as `checkpoint-source-gate-evidence`, including
`pytest-results.xml`, `report.json`, and command output.

Next owner: **ChatGPT** for exact GitHub source review against frozen parent
`bd9729e2dc8ca728908fc75ad906d78ddfa833b5`. If accepted, supply one fresh FULL
certification command against this final executable/test source. FULL remains
deferred, not waived. Do not begin R2-C/R2-D, run real 133-M, retry Q133-2V,
perform Q133-3/Q133-4, or cross credential/scheduler/provider/broker/live
boundaries. Production/live real-money placement remains **NO-GO**.

## R2-B2 terminal implementation report

### Admission, implementation and publication

The designated worktree is
`F:\AI\worktrees\ai-trading-bot-test-suite-rationalization-132r2` on
`feature/test-suite-rationalization-132r2`, origin
`https://github.com/callmedraken/ai-trading-bot.git`. It was initially clean at
known docs-lag HEAD `4c89d5b968da5a26a0967766c164b49349c158f0`, tree
`f795a236fb7d220e6dbc5a806c3d1ce81ddc2710`. The exact live remote was
`bd9729e2dc8ca728908fc75ad906d78ddfa833b5`, tree
`7e38840a609eee3fbd07cdda1f3adb88ecb42005`. Ancestry and the four-file docs-only
diff were proved before the expressly authorized `git merge --ff-only` against
the exact local origin tracking ref. Final identity and clean index/worktree
were reverified before edits. No other worktree was changed.

Implementation changes exactly:

```text
tests/runtime/checkpoint_runner/helpers.py
tests/runtime/checkpoint_runner/test_arch131.py
tests/runtime/checkpoint_runner/test_arch133_a_g.py
```

A distinct docs-only evidence checkpoint updates exactly:

```text
docs/AI_TRADING_BOT_HANDOFF.md
docs/PROJECT_STATUS.md
docs/architecture/132-tiered-certification-profiles.md
docs/validation/arch132-r2-test-suite-rationalization-plan.md
```

These are independently useful source and evidence checkpoints: terminal CI
measurements only exist after the implementation push. Each checkpoint uses
one normal atomic commit and one ordinary push, exact staging, clean-index
admission, staged filename verification and `git diff --cached --check`.
No amend, rebase, force-push, PR metadata/review-thread change or integration
merge is authorized or performed.

### Authority-edge isolation and integration proof

The actual frozen production graph has five G/H edges:

| Real local layer | Isolated immediate predecessor | Local mutation scope |
| --- | --- | --- |
| 131-G agentic account | `_arch131_direct_mcp_authority_check` | resolver/package only |
| 131-G agentic account | `_arch131_mcp_schema_authority_check` | resolver/package only |
| 131-G agentic account | `_arch131_paper_cycle_authority_check` | resolver/package only |
| 131-H paper operator | `_arch131_agentic_account_authority_check` | operator source only |
| 131-H paper operator | `_arch131_windows_oauth_authority_check` | operator source only |

G isolates five of its 13 mutation cases (four resolver, one package). H isolates
13 of its 21 cases (operator source). Both execute the real local production
body. G's eight transport/adapter/registration cases and H's eight
predecessor-source/registration/workflow cases retain complete real chaining.
No local layer under test is mocked, and no registration/workflow mutation is
newly isolated.

`test_predecessor_called_once_and_failure_propagates` runs two outcomes for each
of these five edges: predecessor PASS and a unique rejection marker. It invokes
the real local body, verifies exactly one predecessor call with the exact root,
and requires exact fail-closed marker propagation. The new
`test_full_real_authority_chain_passes_and_visits_every_predecessor` transparently
traces H -> G -> direct MCP -> schema -> paper cycle -> Windows OAuth, executes
every real body, and requires accepted-source PASS and exact call order. Existing
G/H accepted-source registration tests remain unpatched real-chain PASS checks.

Source inspection found no predecessor calls in 131 I-U or 133 A-G. In
particular, Q does not call P, and A-G are locally pinned independent authority
functions in this source. No hypothetical chain was added or altered. Their
redundant work was the accepted-copy PASS assertion before each local mutation.
Twenty copy helpers no longer run those repetitive assertions. The actual local
authority remains real in every mutation; 21 explicit baseline cases prove each
exact copied closure once (15 Architecture-131 cases including both R closures,
six A-G cases). Existing real-repository PASS tests also remain. This discovery
refines the test-harness optimization without changing the frozen production
authority graph.

No H-K/L-M source/test/helper implementation was rewritten. All 30 I-M
runner/workflow missing/duplicate/order cases retain `isolate_predecessor=False`
and complete real-chain rejection, alongside the existing five-edge
invocation/failure and M-to-H transparent full-chain PASS proofs.

### Function and logical-dimension accounting

| Module | R2-B functions | R2-B2 functions | Original functions missing |
| --- | ---: | ---: | ---: |
| Architecture 131 | 99 | 103 | 0 |
| Architecture 133 A-G | 29 | 30 | 0 |
| Architecture 133 H-K | 19 | 19 | 0 |
| Architecture 133 L-M | 10 | 10 | 0 |
| CI | 12 | 12 | 0 |
| core | 30 | 30 | 0 |
| retained 128/130 | 37 | 37 | 0 |
| runner total | 236 | 241 | 0 |
| certification infrastructure | 38 | 38 | 0 |

No function was renamed, deleted or replaced. Every original function's
parameter decorators/matrices were mechanically compared against the frozen
parent AST and remain identical. JUnit `(classname, name)` identity comparison
also proves all 4,612 R2-B CI cases remain, with exactly 32 additions: 21 copied
closure PASS cases, ten G/H predecessor outcome cases, and one full-chain trace.

Source missing/changed, effect/capability drift, registration drift, checkpoint
order, workflow mutation, callback injection, predecessor rejection propagation
and accepted complete-chain PASS dimensions remain. All 182 H-M source-pin
mutations remain unchanged. Production source/registration pins and capability
checks are unchanged; there is no diff in `src/`, `scripts/`, or `.github/`.

### Focused verification

The requested `F:\AI\ai-trading-bot.venv\Scripts\python.exe` was absent.
As in R2-B, verification used the existing development interpreter
`F:\AI\ai-trading-bot\.venv\Scripts\python.exe`.
From the designated worktree, the exact focused test command was:

```powershell
& F:\AI\ai-trading-bot\.venv\Scripts\python.exe -m pytest tests/runtime/checkpoint_runner/test_arch131.py tests/runtime/checkpoint_runner/test_arch133_a_g.py tests/runtime/checkpoint_runner/test_arch133_h_k.py tests/runtime/checkpoint_runner/test_arch133_l_m.py tests/scripts/certification_runner/test_profiles.py -q --tb=short --maxfail=5 --basetemp=F:/AI/temp/pytest-r2b2-focused-20261007-a -p no:cacheprovider --junitxml=F:/AI/temp/r2b2-evidence/focused-a.xml
```

Result: **1,627 passed / zero failed, errors or skips in 277.44 s**.
Per-module counts: 131 = 724, A-G = 211, H-K = 153, L-M = 129, profiles = 410.
The profile tests prove exact inventory, support partition, required baselines,
unknown-ownership rejection and missing/renamed-module fail-closed behavior.

Focused non-mutating checks, all PASS:

```powershell
& F:\AI\ai-trading-bot\.venv\Scripts\python.exe -m ruff check --no-cache tests/runtime/checkpoint_runner/helpers.py tests/runtime/checkpoint_runner/test_arch131.py tests/runtime/checkpoint_runner/test_arch133_a_g.py
& F:\AI\ai-trading-bot\.venv\Scripts\python.exe -m ruff format --check --no-cache tests/runtime/checkpoint_runner/helpers.py tests/runtime/checkpoint_runner/test_arch131.py tests/runtime/checkpoint_runner/test_arch133_a_g.py
git diff --check
git diff --cached --check
```

Both Ruff phases ran before the combined result was assessed. Formatting was
explicitly applied as a source-edit step before these checks. No broad local
FULL, ROBINHOOD, LEGACY or EXHAUSTIVE certification ran.

### Unchanged selectability and certification topology

36 ACTIVE_CI_CHECKPOINTS and eight RETAINED_CHECKPOINTS retain their exact R2-B
ordering. Retained explicit verification behavior is unchanged and retained
runner tests are not selected by routine active CI. FULL/ROBINHOOD/LEGACY/
EXHAUSTIVE remain 136/63/205/341 modules. Required FULL/ROBINHOOD baselines
remain exactly the accepted R2-B migrated tuples (122/49); no membership changed.

`COMMON_TESTS` remains exactly:

```text
tests/runtime/checkpoint_runner/test_core.py
tests/runtime/checkpoint_runner/test_ci.py
```

The terminal artifact's path unions were compared exactly, in first-seen order,
against the admitted R2-B2 inventory. They remain 47 TEST_PATHS / 127 RUFF_PATHS.

<details>
<summary>Exact active TEST_PATHS</summary>

```text
tests/runtime/checkpoint_runner/test_core.py
tests/runtime/checkpoint_runner/test_ci.py
tests/runtime/checkpoint_runner/test_arch131.py
tests/review_paper/test_store.py
tests/robinhood_mcp/test_adapter.py
tests/test_robinhood_paper_cycle.py
tests/review_paper/test_performance.py
tests/robinhood_mcp/test_sdk_transport.py
tests/robinhood_mcp/test_windows_oauth.py
tests/robinhood_mcp/test_account_resolution.py
tests/test_robinhood_paper_operator.py
tests/review_paper/test_intent_bridge.py
tests/risk/test_risk_models.py
tests/risk/test_manager.py
tests/execution/test_execution_models.py
tests/execution/test_order_engine.py
tests/test_robinhood_paper_pipeline.py
tests/review_paper/test_risk_context.py
tests/ledger/test_ledger.py
tests/test_robinhood_forward_paper_cycle.py
tests/test_robinhood_live_qualification_verifier.py
tests/review_paper/test_session_admission.py
tests/review_paper/test_risk_prices.py
tests/review_paper/test_forward_preview.py
tests/review_paper/test_risk_price_acquisition.py
tests/review_paper/test_supervised_forward_paper.py
tests/review_paper/test_prepare_qualification.py
tests/test_robinhood_prepare_qualification_verifier.py
tests/review_paper/test_nyse_published_regular_sessions.py
tests/review_paper/test_published_session_prepare.py
tests/scripts/certification_runner/test_profiles.py
tests/test_robinhood_prepare_operator.py
tests/test_robinhood_supervised_qualification.py
tests/runtime/checkpoint_runner/test_arch133_a_g.py
tests/review_paper/test_unattended_activation.py
tests/review_paper/test_unattended_state_store.py
tests/review_paper/test_unattended_one_wake.py
tests/review_paper/test_unattended_execution.py
tests/review_paper/test_unattended_host.py
tests/runtime/checkpoint_runner/test_arch133_h_k.py
tests/review_paper/test_unattended_publication.py
tests/review_paper/test_scratch_root_acl.py
tests/review_paper/test_retained_root_diagnostic.py
tests/review_paper/test_retained_root_acl_recovery.py
tests/runtime/checkpoint_runner/test_arch133_l_m.py
tests/review_paper/test_post_publication_verifier.py
tests/review_paper/test_post_publication_stage_diagnostic.py
```

</details>

<details>
<summary>Exact active RUFF_PATHS</summary>

```text
scripts/checkpoint_runner.py
tests/runtime/checkpoint_runner/test_core.py
tests/runtime/checkpoint_runner/test_ci.py
tests/runtime/checkpoint_runner/helpers.py
tests/runtime/checkpoint_runner/__init__.py
tests/runtime/checkpoint_runner/test_arch131.py
src/trading_bot/review_paper/__init__.py
src/trading_bot/review_paper/models.py
src/trading_bot/review_paper/store.py
tests/review_paper/test_store.py
src/trading_bot/robinhood_mcp/__init__.py
src/trading_bot/robinhood_mcp/models.py
src/trading_bot/robinhood_mcp/parsing.py
src/trading_bot/robinhood_mcp/adapter.py
tests/robinhood_mcp/test_adapter.py
src/trading_bot/robinhood_paper_cycle.py
tests/test_robinhood_paper_cycle.py
src/trading_bot/review_paper/performance.py
tests/review_paper/test_performance.py
src/trading_bot/robinhood_mcp/sdk_transport.py
tests/robinhood_mcp/test_sdk_transport.py
src/trading_bot/robinhood_mcp/windows_oauth.py
tests/robinhood_mcp/test_windows_oauth.py
src/trading_bot/robinhood_mcp/account_resolution.py
tests/robinhood_mcp/test_account_resolution.py
src/trading_bot/robinhood_paper_operator.py
tests/test_robinhood_paper_operator.py
src/trading_bot/review_paper/intent_bridge.py
tests/review_paper/test_intent_bridge.py
src/trading_bot/robinhood_paper_pipeline.py
tests/test_robinhood_paper_pipeline.py
src/trading_bot/review_paper/risk_context.py
tests/review_paper/test_risk_context.py
src/trading_bot/robinhood_forward_paper_cycle.py
tests/test_robinhood_forward_paper_cycle.py
src/trading_bot/robinhood_live_qualification_verifier.py
tests/test_robinhood_live_qualification_verifier.py
src/trading_bot/review_paper/session_admission.py
tests/review_paper/test_session_admission.py
src/trading_bot/review_paper/risk_prices.py
tests/review_paper/test_risk_prices.py
src/trading_bot/review_paper/forward_preview.py
tests/review_paper/test_forward_preview.py
src/trading_bot/review_paper/risk_price_acquisition.py
tests/review_paper/test_risk_price_acquisition.py
src/trading_bot/review_paper/supervised_forward_paper.py
tests/review_paper/test_supervised_forward_paper.py
src/trading_bot/review_paper/prepare_qualification.py
tests/review_paper/test_prepare_qualification.py
src/trading_bot/robinhood_prepare_qualification_verifier.py
tests/test_robinhood_prepare_qualification_verifier.py
src/trading_bot/review_paper/nyse_published_regular_sessions.py
tests/review_paper/test_nyse_published_regular_sessions.py
src/trading_bot/review_paper/published_session_prepare.py
tests/review_paper/test_published_session_prepare.py
tests/scripts/certification_runner/test_profiles.py
src/trading_bot/robinhood_prepare_operator.py
tests/test_robinhood_prepare_operator.py
src/trading_bot/robinhood_supervised_qualification.py
src/trading_bot/robinhood_execute_qualification_verifier.py
scripts/robinhood_supervised_qualification.py
tests/test_robinhood_supervised_qualification.py
tests/runtime/checkpoint_runner/test_arch133_a_g.py
src/trading_bot/review_paper/unattended_activation.py
tests/review_paper/test_unattended_activation.py
src/trading_bot/review_paper/unattended_state_schema.py
src/trading_bot/review_paper/unattended_state_store.py
src/trading_bot/review_paper/unattended_state_verifier.py
tests/review_paper/test_unattended_state_store.py
src/trading_bot/review_paper/unattended_one_wake.py
tests/review_paper/test_unattended_one_wake.py
src/trading_bot/review_paper/unattended_execution.py
tests/review_paper/test_unattended_execution.py
src/trading_bot/review_paper/unattended_host_identity.py
src/trading_bot/review_paper/unattended_scheduler.py
src/trading_bot/review_paper/unattended_host.py
scripts/run_arch133_unattended_review_paper.py
tests/review_paper/test_unattended_host.py
src/trading_bot/review_paper/unattended_host_bootstrap.py
scripts/run_arch133_unattended_host_preflight.py
tests/runtime/checkpoint_runner/test_arch133_h_k.py
src/trading_bot/review_paper/unattended_publication.py
src/trading_bot/review_paper/unattended_publication_windows.py
scripts/run_arch133_host_publication.py
src/trading_bot/arch133_acl/__init__.py
src/trading_bot/arch133_acl/primitive.py
src/trading_bot/arch133_acl/read_only.py
src/trading_bot/arch133_acl/root_policy_apply.py
src/trading_bot/arch133_acl/administrator.py
tests/review_paper/test_unattended_publication.py
src/trading_bot/arch133_acl/qualification.py
scripts/run_arch133_scratch_root_acl.py
tests/review_paper/test_scratch_root_acl.py
src/trading_bot/arch133_acl/retained_reads.py
src/trading_bot/arch133_acl/retained_diagnostic.py
scripts/run_arch133_retained_root_diagnostic.py
tests/review_paper/test_retained_root_diagnostic.py
src/trading_bot/arch133_acl/recovery.py
scripts/run_arch133_retained_root_acl_recovery.py
tests/review_paper/test_retained_root_acl_recovery.py
tests/runtime/checkpoint_runner/test_arch133_l_m.py
src/trading_bot/__init__.py
src/trading_bot/config.py
src/trading_bot/arch133_verifier/__init__.py
src/trading_bot/arch133_verifier/activation.py
src/trading_bot/arch133_verifier/binding.py
src/trading_bot/arch133_verifier/credentials.py
src/trading_bot/arch133_verifier/file_policy.py
src/trading_bot/arch133_verifier/operator.py
src/trading_bot/arch133_verifier/scheduler.py
src/trading_bot/arch133_verifier/sessions.py
src/trading_bot/arch133_verifier/state.py
src/trading_bot/arch133_verifier/state_schema.py
src/trading_bot/arch133_verifier/token.py
src/trading_bot/domain/__init__.py
src/trading_bot/domain/_validation.py
src/trading_bot/domain/enums.py
src/trading_bot/domain/market.py
src/trading_bot/domain/orders.py
src/trading_bot/domain/positions.py
src/trading_bot/domain/proposals.py
scripts/run_arch133_post_publication_verifier.py
tests/review_paper/test_post_publication_verifier.py
src/trading_bot/arch133_diagnostic/__init__.py
src/trading_bot/arch133_diagnostic/operator.py
scripts/run_arch133_post_publication_stage_diagnostic.py
tests/review_paper/test_post_publication_stage_diagnostic.py
```

</details>

### Terminal CI, JUnit and performance evidence

[Source gate #294 / 37731218114](https://github.com/callmedraken/ai-trading-bot/actions/runs/37731218114) reached terminal
**SUCCESS** on HEAD `ff21c05b93d862d2299dd1574c2f931b9ea5acb5`, tree `3e714d054516dfd156def89c2a21e51b85e8861e`.
All 36 authority results passed, identity remained stable and all four command
exit codes were zero. The downloaded command bytes/SHA-256 values were verified
against `report.json`. The sole skip is the unchanged optional MCP OAuth import
(`mcp.shared.auth` unavailable in source CI).

Artifact `checkpoint-source-gate-evidence` retains:

```text
source-gate-batch-20261008T051306.659003Z/report.json
source-gate-batch-20261008T051306.659003Z/pytest-results.xml
source-gate-batch-20261008T051306.659003Z/commands/01-pytest.stdout.txt
```

| Measurement | R2-B | R2-B2 | Historical median |
| --- | ---: | ---: | ---: |
| Passed / skipped | 4,611 / 1 | 4,643 / 1 | varies |
| Total cases | 4,612 | 4,644 | varies |
| Pytest wall seconds | 352.07 | 198.14 | 188.41 |
| Pytest command elapsed_seconds | 353.5722111 | 199.42576060000002 | unavailable |
| Workflow end-to-end seconds | 406 | 250 | 242 |
| Recorded testcase seconds | 344.615 | 192.039 | unavailable |

Workflow elapsed is terminal `updated_at` minus `created_at`, using the same
convention as the historical comparison. Historical pytest/workflow ranges are
150.67-234.87 s / 195-288 s. Pytest changes by -43.72% against R2-B
and +5.16% against its historical median; workflow changes by
-38.42% and +3.31% respectively. Timing is
observational, never a correctness criterion or threshold.

| JUnit module | R2-B cases | R2-B seconds | R2-B2 cases | R2-B2 seconds |
| --- | ---: | ---: | ---: | ---: |
| `test_arch131.py` | 698 | 172.955 | 724 | 71.088 |
| `test_arch133_a_g.py` | 205 | 44.751 | 211 | 18.983 |
| `test_arch133_h_k.py` | 153 | 43.902 | 153 | 35.826 |
| `test_arch133_l_m.py` | 129 | 55.094 | 129 | 44.269 |
| `test_ci.py` | 58 | 6.433 | 58 | 5.345 |
| `test_core.py` | 50 | 0.112 | 50 | 0.081 |

Checkpoint-runner aggregate: **175.592 s / 1325 cases /
91.44%** of 192.039 s recorded testcase
time, versus R2-B's 323.247 s / 1,293 cases / 93.8%. Non-runner tests total
**16.447 s**, versus approximately 21.368 s in R2-B.

| CI command | Exit | elapsed_seconds |
| --- | ---: | ---: |
| `pytest` | 0 | 199.42576060000002 |
| `ruff_check` | 0 | 0.10405910000002905 |
| `ruff_format` | 0 | 0.08929960000000392 |
| `git_diff_check` | 0 | 0.024824200000011842 |

### Top-100 slowest durations

The retained stdout contains all 100 durations; their rounded sum is
54.95 s. Counts by module:

- `tests/runtime/checkpoint_runner/test_arch133_l_m.py`: 56.
- `tests/runtime/checkpoint_runner/test_arch133_h_k.py`: 25.
- `tests/runtime/checkpoint_runner/test_ci.py`: 8.
- `tests/runtime/checkpoint_runner/test_arch131.py`: 11.

<details>
<summary>All 100 recorded slowest durations (seconds / phase / test)</summary>

```text
1.58s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133m_ci_registration_drift_fails_closed[order-runner]
1.57s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133m_ci_registration_drift_fails_closed[order-workflow]
1.50s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133m_ci_registration_drift_fails_closed[duplicate-runner]
1.46s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_ci_registration_drift_fails_closed[missing-workflow]
1.43s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133m_ci_registration_drift_fails_closed[missing-runner]
1.38s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_ci_registration_drift_fails_closed[order-runner]
1.36s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133m_ci_registration_drift_fails_closed[missing-workflow]
1.36s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_ci_registration_drift_fails_closed[duplicate-workflow]
1.35s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133m_ci_registration_drift_fails_closed[duplicate-workflow]
1.28s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_ci_registration_drift_fails_closed[missing-runner]
1.27s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_ci_registration_drift_fails_closed[order-workflow]
1.14s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_ci_registration_drift_fails_closed[duplicate-runner]
1.13s call tests/runtime/checkpoint_runner/test_arch133_h_k.py::test_133k_ci_registration_drift_fails_closed[duplicate-runner]
1.00s call tests/runtime/checkpoint_runner/test_arch133_h_k.py::test_133k_ci_registration_drift_fails_closed[order-runner]
1.00s call tests/runtime/checkpoint_runner/test_arch133_h_k.py::test_133k_ci_registration_drift_fails_closed[missing-workflow]
0.98s call tests/runtime/checkpoint_runner/test_arch133_h_k.py::test_133k_ci_registration_drift_fails_closed[duplicate-workflow]
0.94s call tests/runtime/checkpoint_runner/test_arch133_h_k.py::test_133k_ci_registration_drift_fails_closed[order-workflow]
0.93s call tests/runtime/checkpoint_runner/test_arch133_h_k.py::test_133j_ci_registration_drift_fails_closed[missing-runner]
0.86s call tests/runtime/checkpoint_runner/test_arch133_h_k.py::test_133k_ci_registration_drift_fails_closed[missing-runner]
0.83s call tests/runtime/checkpoint_runner/test_arch133_h_k.py::test_133j_ci_registration_drift_fails_closed[missing-workflow]
0.82s call tests/runtime/checkpoint_runner/test_arch133_h_k.py::test_133j_ci_registration_drift_fails_closed[duplicate-runner]
0.76s call tests/runtime/checkpoint_runner/test_arch133_h_k.py::test_133j_ci_registration_drift_fails_closed[order-workflow]
0.75s call tests/runtime/checkpoint_runner/test_ci.py::test_ci_change_gate_against_real_git_range[whitespace-pull_request]
0.75s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_full_real_authority_chain_passes_and_visits_every_predecessor
0.73s call tests/runtime/checkpoint_runner/test_ci.py::test_ci_change_gate_against_real_git_range[docs-push]
0.69s call tests/runtime/checkpoint_runner/test_arch133_h_k.py::test_133j_ci_registration_drift_fails_closed[order-runner]
0.68s call tests/runtime/checkpoint_runner/test_ci.py::test_ci_change_gate_against_real_git_range[whitespace-push]
0.68s call tests/runtime/checkpoint_runner/test_arch131.py::test_131v_source_only_registration_and_boundaries
0.68s call tests/runtime/checkpoint_runner/test_arch133_h_k.py::test_133j_ci_registration_drift_fails_closed[duplicate-workflow]
0.67s call tests/runtime/checkpoint_runner/test_ci.py::test_ci_change_gate_against_real_git_range[docs-pull_request]
0.67s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133m_source_only_registration_no_host_callbacks
0.67s call tests/runtime/checkpoint_runner/test_ci.py::test_ci_change_gate_against_real_git_range[moved_source-pull_request]
0.66s call tests/runtime/checkpoint_runner/test_ci.py::test_ci_change_gate_against_real_git_range[moved_source-push]
0.66s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_source_only_registration_no_host_callbacks
0.61s call tests/runtime/checkpoint_runner/test_arch133_h_k.py::test_133i_ci_registration_drift_fails_closed[order-workflow]
0.58s call tests/runtime/checkpoint_runner/test_ci.py::test_ci_change_gate_against_real_git_range[unavailable-pull_request]
0.56s call tests/runtime/checkpoint_runner/test_arch133_h_k.py::test_133i_ci_registration_drift_fails_closed[duplicate-runner]
0.54s call tests/runtime/checkpoint_runner/test_ci.py::test_ci_change_gate_against_real_git_range[unavailable-push]
0.53s call tests/runtime/checkpoint_runner/test_arch133_h_k.py::test_133i_ci_registration_drift_fails_closed[duplicate-workflow]
0.53s call tests/runtime/checkpoint_runner/test_arch133_h_k.py::test_133i_ci_registration_drift_fails_closed[missing-runner]
0.51s call tests/runtime/checkpoint_runner/test_arch133_h_k.py::test_133i_ci_registration_drift_fails_closed[missing-workflow]
0.51s call tests/runtime/checkpoint_runner/test_arch133_h_k.py::test_133i_ci_registration_drift_fails_closed[order-runner]
0.43s call tests/runtime/checkpoint_runner/test_arch133_h_k.py::test_133k_source_only_registration_no_host_callbacks
0.36s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_complete_import_closure_pins_fail_closed[changed-src/trading_bot/__init__.py]
0.35s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_runtime_callback_injection_fails_closed[change2]
0.35s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_complete_import_closure_pins_fail_closed[changed-src/trading_bot/arch133_verifier/credentials.py]
0.34s call tests/runtime/checkpoint_runner/test_arch133_h_k.py::test_133j_source_only_registration_no_host_callbacks
0.34s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133m_complete_import_closure_pins_fail_closed[changed-src/trading_bot/domain/__init__.py]
0.33s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133m_complete_import_closure_pins_fail_closed[changed-src/trading_bot/arch133_acl/retained_reads.py]
0.32s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133m_complete_import_closure_pins_fail_closed[changed-scripts/run_arch133_post_publication_stage_diagnostic.py]
0.30s call tests/runtime/checkpoint_runner/test_arch131.py::test_131h_authority_rejects_boundary_drift[src/trading_bot/robinhood_paper_cycle.py-        post_review, post_review_pages = _collect_agentic_orders(-        if review_failure is not None:\n            raise review_failure\n        post_review, post_review_pages = _collect_agentic_orders(]
0.30s call tests/runtime/checkpoint_runner/test_arch131.py::test_full_real_authority_chain_passes_and_visits_every_predecessor
0.30s call tests/runtime/checkpoint_runner/test_arch131.py::test_131h_authority_rejects_boundary_drift[.github/workflows/checkpoint-source-gates.yml-arch131-robinhood-paper-operator-missing-checkpoint]
0.30s call tests/runtime/checkpoint_runner/test_arch131.py::test_131h_authority_rejects_boundary_drift[scripts/checkpoint_runner.py-execute=None,-execute=host_effect,]
0.30s call tests/runtime/checkpoint_runner/test_arch131.py::test_131h_source_registration_and_workflow
0.30s call tests/runtime/checkpoint_runner/test_arch133_h_k.py::test_133i_runtime_callback_injection_fails_closed[change6]
0.30s call tests/runtime/checkpoint_runner/test_arch131.py::test_131h_authority_rejects_boundary_drift[scripts/checkpoint_runner.py-preflight=None,-preflight=host_effect,]
0.30s call tests/runtime/checkpoint_runner/test_arch131.py::test_131h_authority_rejects_boundary_drift[src/trading_bot/robinhood_paper_cycle.py-except Exception as error:-except BaseException as error:]
0.30s call tests/runtime/checkpoint_runner/test_arch131.py::test_131h_authority_rejects_boundary_drift[src/trading_bot/robinhood_mcp/sdk_transport.py-    def get_equity_orders(-    def call_tool(]
0.29s call tests/runtime/checkpoint_runner/test_arch131.py::test_131h_authority_rejects_boundary_drift[src/trading_bot/robinhood_mcp/sdk_transport.py-    "get_equity_orders",-    "get_accounts",\n    "get_equity_orders",]
0.29s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133m_complete_import_closure_pins_fail_closed[missing-src/trading_bot/domain/orders.py]
0.29s call tests/runtime/checkpoint_runner/test_arch131.py::test_131h_authority_rejects_boundary_drift[src/trading_bot/robinhood_mcp/sdk_transport.py-    def _get_accounts(-    def get_accounts(]
0.29s call tests/runtime/checkpoint_runner/test_arch133_h_k.py::test_133h_complete_authority_pins_fail_closed[changed-src/trading_bot/review_paper/unattended_activation.py]
0.29s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_runtime_callback_injection_fails_closed[change6]
0.28s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_runtime_callback_injection_fails_closed[change5]
0.28s call tests/runtime/checkpoint_runner/test_arch133_h_k.py::test_133k_read_only_import_closure_pins_fail_closed[changed-src/trading_bot/config.py]
0.28s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_complete_import_closure_pins_fail_closed[changed-src/trading_bot/config.py]
0.27s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133m_complete_import_closure_pins_fail_closed[changed-src/trading_bot/arch133_verifier/activation.py]
0.27s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_runtime_callback_injection_fails_closed[change0]
0.27s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_runtime_callback_injection_fails_closed[change4]
0.27s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_complete_import_closure_pins_fail_closed[missing-src/trading_bot/arch133_verifier/state_schema.py]
0.27s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_complete_import_closure_pins_fail_closed[changed-src/trading_bot/arch133_verifier/token.py]
0.27s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133m_complete_import_closure_pins_fail_closed[changed-src/trading_bot/domain/enums.py]
0.27s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_complete_import_closure_pins_fail_closed[changed-src/trading_bot/arch133_verifier/sessions.py]
0.27s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_complete_import_closure_pins_fail_closed[changed-src/trading_bot/domain/enums.py]
0.27s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_complete_import_closure_pins_fail_closed[changed-src/trading_bot/arch133_acl/__init__.py]
0.27s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_complete_import_closure_pins_fail_closed[changed-src/trading_bot/domain/__init__.py]
0.27s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_complete_import_closure_pins_fail_closed[changed-src/trading_bot/arch133_verifier/binding.py]
0.26s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_complete_import_closure_pins_fail_closed[changed-scripts/run_arch133_post_publication_verifier.py]
0.26s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_complete_import_closure_pins_fail_closed[changed-src/trading_bot/domain/_validation.py]
0.26s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_complete_import_closure_pins_fail_closed[changed-src/trading_bot/arch133_acl/retained_reads.py]
0.26s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_complete_import_closure_pins_fail_closed[changed-src/trading_bot/arch133_verifier/file_policy.py]
0.26s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_complete_import_closure_pins_fail_closed[changed-src/trading_bot/arch133_verifier/operator.py]
0.26s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_runtime_callback_injection_fails_closed[change3]
0.26s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_complete_import_closure_pins_fail_closed[changed-src/trading_bot/domain/orders.py]
0.26s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_runtime_callback_injection_fails_closed[change1]
0.25s call tests/runtime/checkpoint_runner/test_arch133_h_k.py::test_133i_source_only_registration_and_inert_callbacks
0.25s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133m_runtime_callback_injection_fails_closed[change0]
0.25s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133m_runtime_callback_injection_fails_closed[change4]
0.25s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133m_complete_import_closure_pins_fail_closed[changed-src/trading_bot/domain/positions.py]
0.25s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_complete_import_closure_pins_fail_closed[changed-src/trading_bot/domain/positions.py]
0.25s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133m_complete_import_closure_pins_fail_closed[changed-src/trading_bot/domain/market.py]
0.25s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_complete_import_closure_pins_fail_closed[changed-src/trading_bot/arch133_verifier/activation.py]
0.25s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_complete_import_closure_pins_fail_closed[changed-src/trading_bot/arch133_verifier/state.py]
0.25s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_complete_import_closure_pins_fail_closed[changed-src/trading_bot/arch133_verifier/state_schema.py]
0.25s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133m_runtime_callback_injection_fails_closed[change3]
0.25s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_complete_import_closure_pins_fail_closed[changed-src/trading_bot/arch133_acl/read_only.py]
0.25s call tests/runtime/checkpoint_runner/test_arch133_h_k.py::test_133k_read_only_import_closure_pins_fail_closed[changed-src/trading_bot/arch133_acl/retained_reads.py]
0.25s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133l_complete_import_closure_pins_fail_closed[changed-src/trading_bot/domain/proposals.py]
0.25s call tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133m_complete_import_closure_pins_fail_closed[changed-src/trading_bot/arch133_diagnostic/__init__.py]
```

</details>

### Deviations, limitations and next owner

The requested interpreter path was absent; the existing development `.venv`
was used. The Windows sandbox helper failed before commands could start, so
approved commands ran outside that broken sandbox while remaining confined to
the expressly named source worktree and external test/evidence roots. The first
push approval attempt hit a reviewer usage limit and executed no push; after
the user's Continue instruction, the ordinary push succeeded through the same
approval mechanism.

The main 131/A-G optimization moves repeated setup PASS checks into dedicated
cases because those real local authority functions have no predecessor calls.
Only the five actually present G/H edges are isolated, for 18 wholly local
mutation cases. Production chaining and all logical rejection dimensions remain
unchanged. This is a single observational CI sample; timing variability is not a
correctness failure. No unresolved focused/source-CI failure remains.

ChatGPT exact-source acceptance and FULL certification are pending. No protected
operation, real 133-M, Q133-2V retry, Q133-3/Q133-4, R2-C or R2-D was performed.
Production/live placement remains NO-GO.

Ready-to-paste next action for ChatGPT:

> Review Architecture 132-R2-B2 implementation HEAD
> `ff21c05b93d862d2299dd1574c2f931b9ea5acb5`, TREE `3e714d054516dfd156def89c2a21e51b85e8861e`, against
> frozen parent `bd9729e2dc8ca728908fc75ad906d78ddfa833b5`, using terminal
> source gate #294 / 37731218114 SUCCESS and this evidence report.
> Check all original function/mutation/case identities, copied-closure PASS
> proofs, five G/H invocation/failure/full-real-chain proofs, unchanged H-M
> workflow/order integration, unchanged active unions and profile baselines.
> Decide exact-source acceptance. If accepted, supply one fresh FULL certification
> command on this final executable/test source to close R2-B's deferred obligation.
> Do not begin R2-C/R2-D or resume protected Architecture-133 operations.

## 2026-10-07 — Architecture 132-R2-B SOURCE ACCEPTED; historical CI gap localizes R2-B2

Architecture 132-R2-B is **SOURCE/TOPOLOGY ACCEPTED**.

Accepted implementation source:

```text
BRANCH  feature/test-suite-rationalization-132r2
HEAD    40aa7ef55a528fe7b7d9482d083ef1dcfed4dfb1
TREE    0781d9ecb3dcaf87888506e2b833fb8106f35990
CI      #291 / 37726690416 SUCCESS
```

Evidence/docs descendant:

```text
HEAD    4c89d5b968da5a26a0967766c164b49349c158f0
TREE    f795a236fb7d220e6dbc5a806c3d1ce81ddc2710
CI      #292 / 37727527551 SUCCESS
```

ChatGPT exact-source review found no correction required. No production
`src/` file changed. The checkpoint-runner authority-function edits are
coverage/registration/test-path migrations required by the split, while
production source pins and production authority chaining remain intact.
Certification ownership remains fail-closed: current split runner/certification
infrastructure is supported FULL/ROBINHOOD, the retained Architecture 128/130
runner replacement is LEGACY-required, FULL and LEGACY remain disjoint, and
unknown ownership remains rejected.

Independent relocation verification found all original test functions preserved:

```text
old checkpoint-runner functions       230
new checkpoint-runner functions       236
missing original runner functions       0

old certification-runner functions     37
new certification-runner functions     38
missing original certification funcs    0

original functions total              267
missing originals                       0
```

The six additional proof functions cover R2-B selectability, external JUnit
evidence, predecessor invocation/failure propagation, full real-chain PASS, and
retained individual verification. The repeated predecessor propagation test name
exists in two different split modules and is intentional.

R2-B terminal active source CI:

```text
CHECKPOINTS        36
TEST_PATHS         47
RUFF_PATHS        127
pytest             4,611 passed / 1 skipped / 0 failed / 0 errors
pytest wall        352.07 s
command elapsed    353.5722111 s
```

This is a 55.44% pytest-time reduction from R2-A's 790.08 s, but historical
same-workflow evidence proves the suite is still materially slower than its
pre-regression baseline.

### Historical same-workflow baseline

The comparison below uses successful non-docs **Checkpoint Source Gates** runs
whose `Verify batch source checkpoints` step actually executed; docs-only
20-40 second fast paths are excluded.

```text
run   checkpoints paths  passed  pytest_s  workflow_s
#224      32       57    4,508    215.40      266
#227      33       58    4,770    198.08      250
#229      34       59    4,926    178.74      234
#239      37       62    5,251    159.04      195
#247      37       62    5,255    150.67      200
#252      37       62    5,255    223.56      266
#256      38       62    5,291    234.87      288
#259      39       63    5,436    161.31      212
#260      39       63    5,466    220.10      265
#265      40       64    5,671    174.69      212
```

For those ten successful full gates:

```text
historical pytest median    188.41 s
historical pytest range     150.67 - 234.87 s
historical workflow median  242 s
historical workflow range   195 - 288 s

R2-B pytest               352.07 s   (+86.86% vs historical median)
R2-B workflow             406 s      (+67.77% vs historical median)
```

R2-B therefore recovered most of the R2-A/L-M explosion but is **not yet back
to the original sub-300-second CI regime**. It has fewer active cases and paths
than many historical gates, so raw test count is not the explanation.

The regression becomes visible around Architecture 133-I/J and compounds through
L/M:

```text
#265  40 checkpoints / 64 paths / 5,671 passed -> 174.69 s
#269  40 checkpoints / 64 paths / 5,680 passed -> 307.58 s
#274  41 / 65 / 5,805                         -> 324.17 s
#276  42 / 66 / 5,963                         -> 300.17 s
#279  43 / 67 / 6,154                         -> 378.51 s
#282  43 / 67 / 6,169                         -> 522.90 s
#286  44 / 68 / 6,393                         -> 696.12 s
#288  36 / 42 / 4,849                         -> 790.08 s
#291  36 / 47 / 4,611                         -> 352.07 s
```

### R2-B JUnit localization

R2-B's newly retained JUnit artifact makes the remaining cost explicit:

```text
all recorded testcase time                    344.615 s

checkpoint-runner infrastructure              323.247 s / 1,293 cases
                                               93.8% of testcase time

  Architecture 131 runner                     172.955 s / 698
  Architecture 133 L-M                         55.094 s / 129
  Architecture 133 A-G                         44.751 s / 205
  Architecture 133 H-K                         43.902 s / 153
  CI contracts                                  6.433 s / 58
  core runner                                   0.112 s / 50

all non-checkpoint-runner tests combined       ~21.368 s
```

The top 100 slowest tests account for only 77.04 s, so optimizing only the
headline L/M cases cannot recover the historical baseline. The dominant next
target is the broad Architecture-131 source-authority mutation matrix, followed
by Architecture-133 chained authority tests.

### Certification decision

R2-B deliberately changed certification inventory topology, so a **FULL
current-product certification remains required before Architecture 132-R2 is
closed**. It is intentionally deferred until R2-B2 because R2-B2 will modify the
test source again; certifying 40aa7ef now would create knowingly stale evidence
and force a duplicate broad certification. This is a selected/deferred
certification, not a waiver.

### R2-B2 frozen checkpoint — recover active authority-test efficiency

R2-B2 is the final source-only performance checkpoint before FULL certification.
It does not change product behavior, production authority, certification
ownership, or profile module topology.

1. Preserve all R2-B split files and ownership.
2. Do not delete logical test dimensions.
3. Keep production authority functions and predecessor chaining real and
   fail-closed.
4. Apply the immediate-predecessor isolation pattern already accepted for
   Architecture 133 I-M to expensive **Architecture 131 local mutation/unit
   tests** and, where independently justified by JUnit evidence, Architecture
   133 A-G local mutation/unit tests.
5. A local authority mutation test may stub only the already-separately-proven
   predecessor authority call. It must execute the real local authority layer
   under test.
6. For every isolated production chain edge preserve separate tests proving:
   - the real predecessor is invoked;
   - predecessor rejection propagates fail-closed;
   - the accepted full real chain passes.
7. Registration/workflow/order tests may be isolated only when equivalent
   dedicated real-chain integration proves the same edge. Do not silently
   convert all workflow/order coverage to mocked predecessors.
8. Do not change source/registration pins merely for performance.
9. Keep R2-A timing and R2-B JUnit evidence. Report per-module testcase time
   from the terminal JUnit artifact.
10. Timing remains diagnostic. The historical envelope is a comparison target,
    not a PASS/FAIL threshold. The desired outcome is to return routine pytest
    close to the historical 150-235 second range and end-to-end CI below roughly
    300 seconds without dropping logical coverage.
11. Do not begin R2-C legacy deletion/provenance work or R2-D parallelization.
12. After terminal-green R2-B2 exact-source review, run one fresh FULL
    certification on that final source identity; do not run FULL during
    implementation.

Real Architecture 133-M remains paused. Q133-2V is consumed/non-retryable.
Q133-3 and Q133-4 remain unauthorized.

## 2026-10-07 — Architecture 132-R2-B terminal source CI green; review pending

R2-B is implemented and ordinary-pushed on
`feature/test-suite-rationalization-132r2`.

```text
IMPLEMENTATION HEAD 40aa7ef55a528fe7b7d9482d083ef1dcfed4dfb1
IMPLEMENTATION TREE 0781d9ecb3dcaf87888506e2b833fb8106f35990
SOURCE CI           #291 / 37726690416 SUCCESS
PYTEST              4,611 passed / 1 skipped / 0 failed / 0 errors
PYTEST WALL         352.07 s
COMMAND ELAPSED     353.5722111 s
ACTIVE CHECKPOINTS  36 (reviewed sequence unchanged)
TEST_PATHS          42 -> 47
RUFF_PATHS          120 -> 127
```

All 36 authority results passed, source identity stayed stable, and production,
scheduler, provider and broker/live fields remained `NOT_RUN`. The single skip
is the existing optional `mcp.shared.auth` import in the Windows OAuth test;
the source-gate environment does not install `mcp`.

Against accepted R2-A's 790.08 s, this run's pytest wall time is 438.01 s
(55.44%) lower. Command elapsed decreased from 792.1711838 s to 353.5722111 s.
This is observed cross-run evidence, with no timing threshold or performance
claim beyond the measured runs. Splitting increases path counts while reducing
routine collection from 4,850 to 4,612 outcomes and redundant predecessor work.

The [terminal source run](https://github.com/callmedraken/ai-trading-bot/actions/runs/37726690416)
uploaded [evidence artifact 11528162705](https://github.com/callmedraken/ai-trading-bot/actions/runs/37726690416/artifacts/11528162705).
Its batch prefix is `source-gate-batch-20261008T041656.870000Z/`:
`report.json` contains command timings and authority/effect evidence;
`commands/01-pytest.stdout.txt` contains all top-100 durations; and
`pytest-results.xml` contains exact total/per-module case counts.

All 100 slowest entries are calls in supported runner infrastructure: 41 in
133-L–M, 20 in 133-H–K, 29 in Architecture 131, eight in CI, and two in 133-A–G.
The slowest three are real-chain 133-M runner ordering/registration mutations:
1.94 s duplicate, 1.93 s missing, and 1.91 s order. The validation plan records
every split module's CI and focused counts, all original test mappings, exact
unions and required-baseline migration.

All 2,003 distinct focused infrastructure cases passed; focused Ruff
check/format and diff checks passed. No FULL/ROBINHOOD/LEGACY/EXHAUSTIVE
certification was run locally. This separate docs-only checkpoint records
terminal implementation evidence and grants no source/topology or certification
acceptance. ChatGPT owns exact GitHub diff review and final certification
selection; FULL is expected after source acceptance unless exact review
establishes stronger equivalent evidence.

R2-C/R2-D have not started. No historical production source was deleted.
Real 133-M remains paused. Q133-2V remains consumed/non-retryable;
Q133-3/Q133-4 and all protected/provider/credential/scheduler/broker operations
remain unauthorized and were not run.


## 2026-10-07 — Architecture 132-R2-B implementation (source review pending)

R2-B splits test infrastructure by responsibility and isolates redundant
predecessor work in local authority mutation tests. R2-C/R2-D have not started.
The implementation does not claim ChatGPT source/topology or certification
acceptance. Terminal source CI evidence is recorded above in the separate
docs-only evidence checkpoint after implementation source CI completed.

The exact 36 active and eight retained checkpoint sequences are unchanged.
All product test/Ruff requirements retain first-seen order. All eight production
source-pin dictionaries are unchanged. All 46 authority-function ASTs preserve
their logic after accounting only for family test selection and migrated source
registration hashes. Production chaining M → L → K → J → I → H remains real.
Local I–M pin/runtime tests replace only the immediate predecessor with PASS;
workflow/order mutation tests retain the complete real predecessor chain;
separate tests prove predecessor calls, rejection propagation, and complete real
chain PASS. H mutations use the real H layer with no predecessor stub.

`COMMON_TESTS` is exactly:

```text
tests/runtime/checkpoint_runner/test_core.py
tests/runtime/checkpoint_runner/test_ci.py
```

Architecture 131, 133-A–G, 133-H–K, 133-L–M, and retained 128/130 checkpoints
select only their own runner family module in addition to that common pair.
Inventory-dependent checkpoints select only
`tests/scripts/certification_runner/test_profiles.py`; the other four
certification modules remain independently runnable FULL/ROBINHOOD contracts.
The workflow preserves `feature/test-suite-*`, its docs-only fast path, and one
serial source-gate job. Existing R2-A monotonic timing and top-100 flags are
unchanged; an external `pytest-results.xml` is additionally uploaded for exact
per-module case accounting.

| Inventory / union | Before | R2-B |
| --- | ---: | ---: |
| FULL modules | 127 | 136 |
| ROBINHOOD modules | 54 | 63 |
| LEGACY modules | 204 | 205 |
| EXHAUSTIVE modules | 331 | 341 |
| FULL required baseline | 113 | 122 |
| ROBINHOOD required baseline | 40 | 49 |
| Active TEST_PATHS | 42 | 47 |
| Active RUFF_PATHS | 120 | 127 |
| Retained TEST_PATHS | 27 | 29 |
| Retained RUFF_PATHS | 32 | 36 |

Path counts rise because files are split; no speedup is inferred from path
counts. The required legacy replacement is explicitly pinned in
`LEGACY_REQUIRED_MODULES` for LEGACY/EXHAUSTIVE selection. Unknown files in the
new runner infrastructure namespace fail closed instead of inheriting the broad
historical runtime family. FULL/LEGACY remain disjoint, their union equals
EXHAUSTIVE, and ROBINHOOD remains a subset of FULL.

The original 1,941 collected cases are accounted for in the split inventory
below. The 36 additional required-baseline mutation cases exercise the expanded
replacement baselines. Original missing/changed pins, registration, workflow,
ordering, callback/capability, wrong source/authority configuration, and
predecessor rejection dimensions remain covered.

The requested `F:\AI\ai-trading-bot.venv\Scripts\python.exe` is absent.
Focused checks use the existing `F:\AI\ai-trading-bot\.venv\Scripts\python.exe`
and fresh external `F:\AI\temp\pytest-r2b-*` basetemps. No certification
profile run or protected host/provider/credential/scheduler/broker operation
was performed. Real 133-M remains paused; Q133-2V is consumed/non-retryable;
Q133-3/Q133-4 remain unauthorized.

Next owner: ChatGPT for exact GitHub diff review and source acceptance, then
final certification selection. FULL current-product certification is expected
because inventory topology changed, unless exact review establishes stronger
equivalent evidence. Do not begin R2-C/R2-D or resume real 133-M here.


## 2026-10-07 — Architecture 132-R2-A ACCEPTED; R2-B split/selection frozen

Architecture 132-R2-A is **SOURCE/TOPOLOGY ACCEPTED**.

Accepted executable/test source:

```text
BRANCH  feature/test-suite-rationalization-132r2
HEAD    d86c13c00b72f8800bddb15a57c582dbd790b774
TREE    8c06d080fb936c40bccf74c523572e5152c6d12d
CI      #288 / 37713529571 SUCCESS
```

Evidence/docs descendant:

```text
HEAD    8129bac92ce84628048ccafc76815f6511c0990d
TREE    3ee934821ace692e74bebe201445300062487d17
CI      #289 / 37714920814 SUCCESS
```

ChatGPT exact-source review found no correction required. The retained eight
Architecture 128/130 checkpoints remain registered, individually runnable and
available to explicit retained-only or mixed `verify-batch` calls. The routine
workflow invokes exactly the 36 active Architecture 131/133 checkpoints in
reviewed order. First-seen batch de-duplication, active source/registration
pins, authority checks, docs-only classification, clean identity requirements,
and protected `NOT_RUN` semantics remain fail-closed.

R2-A adds only observational timing evidence. `elapsed_seconds` is measured
with a monotonic timer and does not participate in PASS/FAIL. Pytest top-100
durations remain in uploaded stdout evidence.

No additional FULL or ROBINHOOD certification is required for R2-A.
`scripts/run_test_certification.py`, certification ownership, frozen FULL and
ROBINHOOD required baselines, lane semantics and protected-opt-in rejection are
unchanged. Source gate #288 already exercised the changed runner together with
the complete active checkpoint requirement union and every active authority
check. A product certification would not add material evidence for this
source-gate topology-only change.

R2-A measurement outcome:

```text
routine checkpoints   44 -> 36
test paths            68 -> 42
ruff paths           150 -> 120
cases              6,393 -> 4,850 collected outcomes
R2-A pytest         4,849 passed / 1 skipped
R2-A pytest time    790.08 s
command elapsed     792.1711838 s
```

The smaller routine union did not reduce wall time in this single comparison.
The diagnostic evidence localizes the next bottleneck: **all 100 slowest R2-A
tests are in the checkpoint-runner infrastructure suite**, led by repeated
133-L/133-M/H authority mutation tests. Therefore R2-B must improve
selectability and repeated-test cost before R2-D parallelization.

### R2-B frozen contract — split infrastructure without losing logical coverage

R2-B remains test/workflow infrastructure only. It grants no production,
provider, credential, scheduler, wake, broker or live authority. Real
Architecture 133-M remains paused.

#### 1. Split checkpoint-runner tests by responsibility

Replace the monolithic
`tests/runtime/test_checkpoint_runner.py` with independently collectible
modules under a dedicated runtime subpackage. The target responsibility split
is:

```text
tests/runtime/checkpoint_runner/test_core.py
tests/runtime/checkpoint_runner/test_ci.py
tests/runtime/checkpoint_runner/test_arch131.py
tests/runtime/checkpoint_runner/test_arch133_a_g.py
tests/runtime/checkpoint_runner/test_arch133_h_k.py
tests/runtime/checkpoint_runner/test_arch133_l_m.py
tests/runtime/checkpoint_runner/test_retained_arch128_130.py
```

A `conftest.py` and/or non-test helper module may hold inert shared fixtures.
Do not leave duplicate collected copies of moved tests in the old monolith.

The first six modules are current supported test infrastructure. The retained
Architecture 128/130 module is LEGACY compatibility. Routine active source CI
must not collect the retained module merely because every checkpoint shares a
common test path.

`COMMON_TESTS` must become a genuinely small core/CI contract, not a new alias
for every historical/current runner test. Architecture-specific runner contract
modules must be attached only to the checkpoints whose source/authority
contracts they protect. Explicit retained checkpoint verification must still
select the retained runner contract.

#### 2. Split certification-runner tests by responsibility

Replace the monolithic
`tests/scripts/test_run_test_certification.py` with independently collectible
supported modules covering at least:

```text
profile / inventory classification
lane construction
source identity / admission
child execution + JUnit aggregation
protected opt-in + result/evidence semantics
```

Shared inert fixtures/helpers may live in non-collected support files. Routine
Architecture 131/133 source checkpoints should include only the certification
test module(s) actually needed by their source/inventory authority contract;
they must no longer pull the entire certification-runner regression suite merely
because one inventory assertion is relevant.

#### 3. Deliberately update Architecture-132 ownership

Because the two old supported monoliths are being replaced by multiple test
modules, R2-B is an explicit certification-topology change.

Update `run_test_certification.py` ownership and required baselines
deliberately:

- current/core/Architecture-131/Architecture-133 runner split modules are FULL
  and ROBINHOOD infrastructure;
- retained Architecture-128/130 runner tests are LEGACY, not ROBINHOOD/FULL;
- all certification-runner split modules remain supported infrastructure and
  retain their appropriate FULL/ROBINHOOD ownership;
- FULL ∩ LEGACY remains empty;
- FULL ∪ LEGACY remains EXHAUSTIVE;
- unknown ownership remains fail-closed;
- no required baseline may silently disappear because a monolith was renamed.

Record the exact old-to-new baseline mapping and new profile module counts.
Module counts may rise because one file becomes several; that is expected and
must not be mistaken for broader product scope.

#### 4. Preserve logical tests while removing recursive test-harness waste

R2-B does **not** weaken production authority functions or their source pins.

For expensive chained authority mutation tests (especially 133-H/L/M), retain
the full missing/changed pin matrix and runtime/workflow/callback rejection
coverage, but unit tests for a checkpoint's *local* authority layer need not
re-execute every already-proven predecessor authority layer for every
parameterized mutation.

It is acceptable and preferred to isolate local-layer tests by replacing only
the predecessor authority function with a deterministic PASS stub in the test
process, provided separate integration tests prove:

- each production authority function invokes its real predecessor;
- predecessor failures propagate fail-closed;
- the complete real chain passes on the accepted repository;
- workflow/order/registration checks remain real where they are the subject of
  the test.

Do not mock the local layer under test. Do not weaken the production chain.
Do not remove any missing/changed source-pin dimension merely for speed.

The goal is to preserve logical coverage while eliminating thousands of
redundant predecessor source reads/copies/AST checks caused by parameterization.

#### 5. Measure R2-B rather than guessing

Keep R2-A timing instrumentation. Terminal R2-B CI must report:

- active TEST_PATHS/RUFF_PATHS before vs after;
- total pytest cases/passed/skipped;
- pytest wall time and command elapsed time;
- top-100 durations;
- case counts by each new infrastructure test module;
- confirmation retained-only explicit verification still selects its retained
  runner tests;
- profile module counts and old-to-new required baseline mapping.

No timing threshold is a correctness gate.

#### 6. No deletion/provenance audit or parallelization yet

R2-B may remove the two old monolith files only as a test relocation after all
logical coverage is accounted for. It may not delete historical production
source or retire legacy behavioral suites. That belongs to R2-C.

Do not implement parallel source-gate lanes in R2-B. R2-D remains after accepted
R2-B measurements.

### R2-B verification/acceptance

Implementation uses Astra. Run focused split-module, checkpoint registration,
inventory/classification and source-authority tests with fresh external
basetemps. No FULL/ROBINHOOD/LEGACY/EXHAUSTIVE certification during
implementation. After exact source review, because R2-B deliberately changes
certification inventory topology, ChatGPT will select the final certification
tier; a FULL current-product certification is expected unless the reviewed
evidence establishes a stronger equivalent.

R2-B does not authorize the real 133-M diagnostic. Q133-2V remains consumed;
Q133-3 and Q133-4 remain unauthorized.

## 2026-10-07 — Architecture 132-R2-A terminal CI green (source review pending)

R2-A separates the routine source batch from retained compatibility without
changing the checkpoint registry or certification ownership. The exact 36 active
Architecture 131/133 checkpoints retain their previous relative order and all
registered tests, Ruff paths, source pins and authority boundaries. The eight
Architecture 128/130 checkpoints listed in the frozen R2-A contract remain
registered, individually verifiable and selectable in retained-only or mixed
explicit batches. First-seen requirement deduplication is unchanged.

Measured requirement unions against the admitted frozen design parent:

| Routine source gate | Before | R2-A |
| --- | ---: | ---: |
| Checkpoints | 44 | 36 |
| Test paths | 68 | 42 |
| Ruff paths | 150 | 120 |

Accepted baseline CI #286 / 37708975995 recorded 6,393 passed / 3 skipped
in 696.12 seconds. Implementation CI **#288 / 37713529571 SUCCESS** recorded
**4,849 passed / 1 skipped / 0 failed / 0 errors in 790.08 seconds**.
All 36 authority results passed, identity remained stable, and protected
production/scheduler/provider/broker evidence remained `NOT_RUN`.

```text
IMPLEMENTATION HEAD d86c13c00b72f8800bddb15a57c582dbd790b774
IMPLEMENTATION TREE 8c06d080fb936c40bccf74c523572e5152c6d12d
PYTEST             0 / elapsed_seconds 792.1711838
RUFF_CHECK         0 / elapsed_seconds 0.130218000000013
RUFF_FORMAT        0 / elapsed_seconds 0.120859800000062
GIT_DIFF           0 / elapsed_seconds 0.038282099999833
```

The pytest-reported duration was 93.96 seconds higher than the accepted
baseline despite the smaller file union. This single cross-run comparison does
not establish a speedup or explain the timing difference. No timing threshold
was applied.

The [source workflow](https://github.com/callmedraken/ai-trading-bot/actions/runs/37713529571)
uploaded [checkpoint-source-gate-evidence](https://github.com/callmedraken/ai-trading-bot/actions/runs/37713529571/artifacts/11522378514).
Within that artifact, machine-readable command timings are in
`source-gate-batch-20261008T013401.428982Z/report.json`, and the complete top-100
pytest output is in the adjacent `commands/01-pytest.stdout.txt`. All 100 slowest
entries came from `tests/runtime/test_checkpoint_runner.py`. The slowest three
were 133-L import-closure pin drift (5.79s), 133-H complete-authority pin drift
(4.72s), and 133-M import-closure pin drift (3.70s). These are source tests;
the real protected 133-M diagnostic was not run.

Command reports add observational `elapsed_seconds` from a monotonic timer.
Pytest stdout preserves `--durations=100 --durations-min=0.0` output in the
existing uploaded command evidence. Timing has no PASS/FAIL threshold. Report
schema, authority results, source identity and protected `NOT_RUN` fields remain
unchanged. Active tuple AST pins now freeze
`8aaf63458ec12dea75e130e257577c0d00ba3bba5a4bb7a4db4059c7a8ab8b2a`;
production source and registration pins are unchanged.

The workflow adds only the explicitly requested `feature/test-suite-*` push
family. Its active invocation and docs-only classification remain source-pinned.
Terminal implementation measurements are recorded above in this separate
docs-only evidence checkpoint. This records implementation evidence and does
not claim source/topology or certification acceptance.
ChatGPT owns exact GitHub source review, topology acceptance and certification
choice. R2-B has not started. Real 133-M remains paused; Q133-2V is consumed and
Q133-3/Q133-4 remain unauthorized. No protected operation was invoked.

The requested development interpreter path `F:\AI\ai-trading-bot.venv` was
absent; implementation uses the existing `F:\AI\ai-trading-bot\.venv` instead,
with fresh explicit external basetemp directories under `F:\AI\temp\pytest...`.

Focused verification exercised all 1,491 runner cases: the first pass reported
1,488 passed / 3 failed in 725.29 seconds. Those three existing workflow-mutation
cases still targeted retained names; they were corrected to mutate active names.
The affected five-case group then passed (5 passed / 1,486 deselected).
Focused Ruff check/format and `git diff --check` passed. No certification profile
suite was run locally; `run_test_certification.py` and its tests are unchanged.


## 2026-10-07 — Architecture 132-R2 test-suite rationalization interlude

Architecture 133-M is source-accepted and docs-closed, but the real protected
133-M diagnostic is intentionally paused while routine CI/test topology is
rationalized.

Current accepted source baseline for this infrastructure interlude:

```text
PARENT  0e856691c2d1ce350d1846720182bba2bea64f0a
TREE    1536e7a45a67d214ee97454290e2781b3b7001d9
BRANCH  feature/test-suite-rationalization-132r2
```

Current certification ownership at that parent is FULL 127, ROBINHOOD 54,
LEGACY 204, EXHAUSTIVE 331. Architecture 132-R1 already defines LEGACY and
EXHAUSTIVE as explicit, non-routine gates, but routine source-gate CI still
batches eight retained Architecture 128/130 checkpoints ahead of the active
Architecture 131/133 checkpoints.

The latest accepted source gate #286 / 37708975995 ran one deduplicated batch:

```text
CHECKPOINTS 44
TEST_PATHS  68
RUFF_PATHS  150
pytest      6,393 passed / 3 skipped / 0 failed / 0 errors
PYTEST      0
RUFF_CHECK  0
RUFF_FORMAT 0
GIT_DIFF    0
```

This routine source gate therefore overlaps substantially with broad current-
product certification and also reintroduces retained compatibility coverage
that Architecture 132-R1 intentionally removed from routine FULL/ROBINHOOD
certification.

Architecture 132-R2 fixes test topology before any additional protected
Architecture 133 operation. It is a test/workflow-infrastructure change only and
grants no new production, provider, scheduler, credential, wake, broker or live
authority.

### 132-R2 phased plan

**R2-A — measure and correct routine CI scope**

1. Persist source-gate timing evidence: pytest elapsed time, top-100 pytest
   durations, and existing command/lane elapsed data. Timing is diagnostic only
   and cannot affect PASS/FAIL.
2. Replace the single routine checkpoint sequence with explicit
   `ACTIVE_CI_CHECKPOINTS` and `RETAINED_CHECKPOINTS`.
3. The retained set is exactly:
   - `arch128-parent-acl-repair`
   - `arch128-r4`
   - `arch128-r5-substrate`
   - `arch128-r5-trading`
   - `arch128-r6`
   - `arch128-r7`
   - `arch128-r8-terminal-halt`
   - `arch130-r8i-d1`
4. Every retained checkpoint remains registered, authority-pinned, individually
   runnable, and available to explicit batch verification. No retained source
   or test is deleted in R2-A.
5. Routine current-product GitHub source-gate batching executes only the active
   Architecture 131/133 sequence. All active checkpoint tests, Ruff paths,
   authority checks, order pins and source-identity invariants remain enforced.
6. R2-A does not change FULL/ROBINHOOD/LEGACY/EXHAUSTIVE ownership or the frozen
   Architecture 132-R1 required baselines.

**R2-B — split monolithic test infrastructure without deleting coverage**

Split `tests/runtime/test_checkpoint_runner.py` by responsibility so core
runner/batch/CI classification and active Architecture 131/133 contracts are
independently selectable from retained Architecture 128/130 compatibility
contracts. Split `tests/scripts/test_run_test_certification.py` into independently
selectable profile/inventory, lane construction, source admission, child/JUnit,
and protected-opt-in/result areas. Preserve all tests initially; this phase is
structural/selectability work.

**R2-C — retained source+test provenance audit**

Audit all 204 LEGACY modules and their exercised production/source surfaces.
Classify each cohort `KEEP_COMPAT`, `DISTILL_INVARIANTS`, or
`DELETE_WITH_SOURCE`. No deletion is allowed merely because a test is old.
Any retained Windows/security primitive used or source-pinned by current
Architecture 133 stays until its current invariant is migrated and independently
proved.

**R2-D — parallelize only after scope/selectability cleanup**

After R2-A/R2-B measurements are accepted, create deterministic parallel active
source-gate lanes. Do not parallelize today's oversized routine workload first.

### Immediate checkpoint

The next implementation checkpoint is **132-R2-A** only: timing evidence plus
active/retained source-gate separation. Use Astra because the change crosses
checkpoint registration, workflow topology, authority pins, and tests, but does
not change production authority. Focused verification only during implementation;
ChatGPT performs exact-source review and decides whether any broader
certification is necessary afterward.

The real Architecture 133-M diagnostic remains ready but paused. Q133-2V remains
consumed/non-retryable. Q133-3 and Q133-4 remain unauthorized.



## R2-A acceptance contract

R2-A is accepted only if all of the following are true:

- routine source-gate CI has an explicit active checkpoint sequence containing
  all current Architecture 131 and 133 registered source checkpoints in their
  reviewed order;
- the exact eight Architecture 128/130 retained checkpoints are excluded from
  routine current-product batching but remain registered and explicitly
  runnable;
- explicit verification of a retained checkpoint still runs its complete
  existing test/Ruff/authority contract;
- batch verification still accepts an explicit caller-provided mix of active and
  retained checkpoints, so LEGACY/recovery investigation remains possible;
- workflow source pins prove the executable routine batch contains exactly the
  active sequence once, with exit propagation intact;
- no Architecture 131/133 checkpoint loses any test path, Ruff path, authority
  check, or source pin as a side effect of the separation;
- `run_test_certification.py` profile ownership and frozen required baselines
  are byte-for-byte unchanged in R2-A unless a review-proven test relocation
  requires a later R2-B change;
- source-gate reports record pytest elapsed time and retain top-100 pytest
  duration output as evidence, but timing never affects gate status;
- source-gate test collection remains deterministic, de-duplicated and
  first-seen ordered;
- docs-only classification remains unchanged;
- no protected/native/provider/scheduler/credential/wake/broker action is
  introduced.

## Focused verification for R2-A

Implementation should run only the affected runner/workflow/certification tests
and non-mutating static checks. Use fresh `--basetemp` under
`F:\AI\temp\pytest`. Do not run FULL, LEGACY, EXHAUSTIVE, real Architecture
133 diagnostics, or protected operations during implementation.

After ordinary push, follow the source gate to terminal and report:

- exact active and retained checkpoint lists;
- deduplicated routine test/Ruff path counts before vs after;
- pytest case count and elapsed time from terminal CI;
- top-duration evidence location/output;
- exact commit/tree and terminal workflow run;
- confirmation retained checkpoints remain explicitly runnable;
- any changed source-authority hashes/order pins.

ChatGPT then reviews the exact GitHub diff and decides the next R2-B split
checkpoint.

## R2-B exact relocation and requirement inventory

### Required-baseline migration

`tests/runtime/test_checkpoint_runner.py` →

- `tests/runtime/checkpoint_runner/test_arch131.py` — FULL + ROBINHOOD required
- `tests/runtime/checkpoint_runner/test_arch133_a_g.py` — FULL + ROBINHOOD required
- `tests/runtime/checkpoint_runner/test_arch133_h_k.py` — FULL + ROBINHOOD required
- `tests/runtime/checkpoint_runner/test_arch133_l_m.py` — FULL + ROBINHOOD required
- `tests/runtime/checkpoint_runner/test_ci.py` — FULL + ROBINHOOD required
- `tests/runtime/checkpoint_runner/test_core.py` — FULL + ROBINHOOD required
- `tests/runtime/checkpoint_runner/test_retained_arch128_130.py` — LEGACY required (LEGACY/EXHAUSTIVE)

`tests/scripts/test_run_test_certification.py` →

- `tests/scripts/certification_runner/test_children.py` — FULL + ROBINHOOD required
- `tests/scripts/certification_runner/test_lanes.py` — FULL + ROBINHOOD required
- `tests/scripts/certification_runner/test_profiles.py` — FULL + ROBINHOOD required
- `tests/scripts/certification_runner/test_results.py` — FULL + ROBINHOOD required
- `tests/scripts/certification_runner/test_source.py` — FULL + ROBINHOOD required

### Exact active checkpoint test union (first-seen order)

```text
tests/runtime/checkpoint_runner/test_core.py
tests/runtime/checkpoint_runner/test_ci.py
tests/runtime/checkpoint_runner/test_arch131.py
tests/review_paper/test_store.py
tests/robinhood_mcp/test_adapter.py
tests/test_robinhood_paper_cycle.py
tests/review_paper/test_performance.py
tests/robinhood_mcp/test_sdk_transport.py
tests/robinhood_mcp/test_windows_oauth.py
tests/robinhood_mcp/test_account_resolution.py
tests/test_robinhood_paper_operator.py
tests/review_paper/test_intent_bridge.py
tests/risk/test_risk_models.py
tests/risk/test_manager.py
tests/execution/test_execution_models.py
tests/execution/test_order_engine.py
tests/test_robinhood_paper_pipeline.py
tests/review_paper/test_risk_context.py
tests/ledger/test_ledger.py
tests/test_robinhood_forward_paper_cycle.py
tests/test_robinhood_live_qualification_verifier.py
tests/review_paper/test_session_admission.py
tests/review_paper/test_risk_prices.py
tests/review_paper/test_forward_preview.py
tests/review_paper/test_risk_price_acquisition.py
tests/review_paper/test_supervised_forward_paper.py
tests/review_paper/test_prepare_qualification.py
tests/test_robinhood_prepare_qualification_verifier.py
tests/review_paper/test_nyse_published_regular_sessions.py
tests/review_paper/test_published_session_prepare.py
tests/scripts/certification_runner/test_profiles.py
tests/test_robinhood_prepare_operator.py
tests/test_robinhood_supervised_qualification.py
tests/runtime/checkpoint_runner/test_arch133_a_g.py
tests/review_paper/test_unattended_activation.py
tests/review_paper/test_unattended_state_store.py
tests/review_paper/test_unattended_one_wake.py
tests/review_paper/test_unattended_execution.py
tests/review_paper/test_unattended_host.py
tests/runtime/checkpoint_runner/test_arch133_h_k.py
tests/review_paper/test_unattended_publication.py
tests/review_paper/test_scratch_root_acl.py
tests/review_paper/test_retained_root_diagnostic.py
tests/review_paper/test_retained_root_acl_recovery.py
tests/runtime/checkpoint_runner/test_arch133_l_m.py
tests/review_paper/test_post_publication_verifier.py
tests/review_paper/test_post_publication_stage_diagnostic.py
```

### Exact retained checkpoint test union (first-seen order)

```text
tests/runtime/checkpoint_runner/test_core.py
tests/runtime/checkpoint_runner/test_ci.py
tests/runtime/checkpoint_runner/test_retained_arch128_130.py
tests/runtime/test_d10_arch128_parent_acl_repair.py
tests/runtime/test_d10_arch128_r4_operator.py
tests/runtime/test_d10_arch128_r4_orchestration.py
tests/runtime/test_d10_arch128_r4_replacement.py
tests/runtime/test_d10_arch128_r4_windows.py
tests/runtime/test_d10_protected_deployment.py
tests/runtime/test_d10_protected_replacement.py
tests/runtime/test_d10_protected_replacement_windows.py
tests/runtime/test_windows_authority.py
tests/runtime/test_d10_arch128_r3_preflight.py
tests/runtime/test_d10_activation_scheduler_operator.py
tests/runtime/test_d10_arch128_r5_trading_child.py
tests/runtime/test_d10_python_substrate_harness.py
tests/runtime/test_d10_python_substrate_windows.py
tests/runtime/test_personal_desktop_d10_python_substrate.py
tests/runtime/test_d10_arch128_r6_reactivation.py
tests/runtime/test_personal_desktop_d10_activation_lease.py
tests/runtime/test_personal_desktop_d10_wake_evidence_log.py
tests/runtime/test_personal_desktop_unattended_scheduler_contract.py
tests/runtime/test_d10_arch128_r7_readonly.py
tests/runtime/test_d10_arch128_r7_protected.py
tests/runtime/test_d10_arch128_r7_windows.py
tests/runtime/test_d10_arch128_r8_terminal_halt.py
tests/runtime/test_d10_arch128_r8_readonly.py
tests/runtime/test_d10_durable_wake_evidence_observe.py
tests/runtime/test_d10_arch130_r8i_d1.py
```

### Every original logical test accounted for

All rows refer to the admitted parent `4b81a822d55fa5e79460294f46239d133170a157`.
Each original function appears exactly once. Parameter matrices retain their
original dimensions; path/registration literals are deliberately relocated.

#### `tests/runtime/checkpoint_runner/test_arch131.py`

Original module: `tests/runtime/test_checkpoint_runner.py`.

| Original test function | Parent line | Original cases |
| --- | ---: | ---: |
| `test_131f_authority_detects_boundary_drift` | 1684 | 7 |
| `test_131f_authority_rejects_new_effects` | 1711 | 8 |
| `test_131f_authority_rejects_host_registration` | 1727 | 2 |
| `test_131f_source_registration_and_workflow` | 1743 | 1 |
| `test_131g_source_registration` | 1756 | 1 |
| `test_131g_authority_rejects_boundary_drift` | 1841 | 13 |
| `test_131h_source_registration_and_workflow` | 1862 | 1 |
| `test_131h_authority_rejects_boundary_drift` | 1987 | 21 |
| `test_131i_source_registration_and_workflow` | 2013 | 1 |
| `test_131i_authority_freezes_each_mapping` | 2074 | 14 |
| `test_131i_authority_freezes_validation_and_identity` | 2108 | 13 |
| `test_131i_authority_rejects_imports_calls_and_module_effects` | 2150 | 27 |
| `test_131i_authority_freezes_source_only_registration_and_ci` | 2204 | 9 |
| `test_131i_authority_rejects_reversed_workflow_order` | 2218 | 1 |
| `test_131j_source_registration_and_workflow` | 2230 | 1 |
| `test_131j_authority_freezes_each_forwarded_argument` | 2288 | 11 |
| `test_131j_authority_freezes_composition_and_result` | 2345 | 15 |
| `test_131j_authority_rejects_unreviewed_effects` | 2383 | 22 |
| `test_131j_authority_freezes_source_only_registration` | 2404 | 6 |
| `test_131j_authority_freezes_workflow_invocations` | 2443 | 3 |
| `test_131j_authority_rejects_reversed_workflow_order` | 2452 | 1 |
| `test_131k_source_only_registration_and_batch` | 3096 | 1 |
| `test_131k_authority_freezes_builder` | 3182 | 20 |
| `test_131k_authority_rejects_expanded_effect_surface` | 3216 | 19 |
| `test_131k_authority_freezes_registration` | 3238 | 7 |
| `test_131k_authority_freezes_batch_workflow` | 3261 | 4 |
| `test_131l_source_only_registration_and_batch` | 3284 | 1 |
| `test_131l_authority_freezes_composition_and_every_input` | 3388 | 27 |
| `test_131l_authority_rejects_expanded_effect_or_retry_surface` | 3428 | 26 |
| `test_131l_authority_freezes_source_only_registration` | 3452 | 7 |
| `test_131l_authority_rejects_runtime_effect_registration` | 3475 | 2 |
| `test_131l_authority_freezes_batch_workflow` | 3496 | 5 |
| `test_131l_authority_fails_closed_when_source_is_unavailable` | 3528 | 3 |
| `test_131lq_source_only_registration_and_batch` | 3535 | 1 |
| `test_131lq_authority_rejects_effect_surface_drift` | 3589 | 8 |
| `test_131lq_authority_rejects_runtime_effect_registration` | 3600 | 2 |
| `test_131m_source_only_registration_and_batch` | 3619 | 1 |
| `test_131m_authority_rejects_effect_surface_drift` | 3673 | 8 |
| `test_131m_authority_rejects_runtime_effect_registration` | 3684 | 2 |
| `test_131m_authority_rejects_registration_drift` | 3720 | 7 |
| `test_131m_authority_rejects_source_authority_drift` | 3740 | 4 |
| `test_131m_authority_rejects_runtime_remote_drift` | 3766 | 1 |
| `test_131n_source_only_registration_and_batch` | 3780 | 1 |
| `test_131n_authority_rejects_effect_surface_drift` | 3831 | 8 |
| `test_131n_authority_rejects_runtime_effect_registration` | 3842 | 2 |
| `test_131n_authority_rejects_registration_drift` | 3878 | 7 |
| `test_131n_authority_rejects_source_authority_drift` | 3898 | 4 |
| `test_131n_authority_rejects_runtime_remote_drift` | 3924 | 1 |
| `test_131o_source_only_registration_and_batch` | 3938 | 1 |
| `test_131o_authority_rejects_effect_surface_drift` | 3989 | 8 |
| `test_131o_authority_rejects_runtime_effect_registration` | 4000 | 2 |
| `test_131o_authority_rejects_registration_drift` | 4036 | 7 |
| `test_131o_authority_rejects_source_authority_drift` | 4056 | 4 |
| `test_131o_authority_rejects_runtime_remote_drift` | 4082 | 1 |
| `test_131o_authority_pins_composition_validation_and_projection` | 4116 | 8 |
| `test_131p_source_only_registration_and_batch` | 4131 | 1 |
| `test_131p_authority_rejects_effect_surface_drift` | 4185 | 8 |
| `test_131p_authority_rejects_runtime_effect_registration` | 4196 | 2 |
| `test_131p_authority_rejects_registration_drift` | 4232 | 7 |
| `test_131p_authority_rejects_source_authority_drift` | 4252 | 4 |
| `test_131p_authority_rejects_runtime_remote_drift` | 4278 | 1 |
| `test_131p_authority_pins_complete_acquisition` | 4312 | 9 |
| `test_131q_source_only_registration_and_batch` | 4324 | 1 |
| `test_131q_authority_rejects_effect_surface_drift` | 4378 | 8 |
| `test_131q_authority_rejects_runtime_effect_registration` | 4389 | 2 |
| `test_131q_authority_rejects_registration_drift` | 4425 | 7 |
| `test_131q_authority_rejects_source_authority_drift` | 4445 | 4 |
| `test_131q_authority_rejects_runtime_remote_drift` | 4471 | 1 |
| `test_131q_authority_pins_complete_composition` | 4541 | 18 |
| `test_131r_source_only_registration_and_batch` | 4573 | 2 |
| `test_131r_complete_module_pinned` | 4640 | 20 |
| `test_131r_exact_registration_pinned` | 4659 | 12 |
| `test_131r_source_authority_drift` | 4677 | 8 |
| `test_131r_runtime_registration_drift` | 4712 | 6 |
| `test_131r_critical_guards_pinned` | 4742 | 11 |
| `test_131s_source_only_registration_and_batch` | 4753 | 1 |
| `test_131s_authority_rejects_effect_surface_drift` | 4812 | 8 |
| `test_131s_authority_rejects_runtime_effect_registration` | 4823 | 2 |
| `test_131s_authority_rejects_registration_drift` | 4859 | 7 |
| `test_131s_authority_rejects_source_authority_drift` | 4879 | 4 |
| `test_131s_authority_rejects_runtime_remote_drift` | 4907 | 1 |
| `test_131s_authority_pins_manifest_and_schedule` | 4945 | 17 |
| `test_131s_authority_rejects_ci_invocation_drift` | 4957 | 4 |
| `test_131t_source_only_registration_and_batch` | 4988 | 1 |
| `test_131t_complete_boundaries_pinned` | 5063 | 36 |
| `test_131t_resolution_delegation_and_verifier_guards_pinned` | 5095 | 12 |
| `test_131t_registration_drift` | 5121 | 7 |
| `test_131t_runtime_capability_drift` | 5138 | 3 |
| `test_131t_authority_drift` | 5157 | 4 |
| `test_131t_ci_invocation_drift` | 5179 | 4 |
| `test_131u_source_only_registration_and_batch` | 5206 | 1 |
| `test_131u_complete_boundaries_pinned` | 5296 | 35 |
| `test_131u_composition_and_blocker_pinned` | 5327 | 10 |
| `test_131u_registration_drift` | 5351 | 7 |
| `test_131u_runtime_capability_drift` | 5368 | 3 |
| `test_131u_authority_drift` | 5387 | 4 |
| `test_131u_ci_invocation_drift` | 5414 | 4 |
| `test_131u_source_gate_participant_drift` | 5437 | 2 |
| `test_131v_source_only_registration_and_boundaries` | 5448 | 1 |

#### `tests/runtime/checkpoint_runner/test_arch133_a_g.py`

Original module: `tests/runtime/test_checkpoint_runner.py`.

| Original test function | Parent line | Original cases |
| --- | ---: | ---: |
| `test_133a_source_only_registration_and_single_ordered_batch` | 5486 | 1 |
| `test_133a_authority_pins_every_import_and_call` | 5542 | 14 |
| `test_133a_authority_fails_closed_on_missing_or_drifting_material` | 5565 | 9 |
| `test_133a_runtime_registration_drift_is_rejected` | 5610 | 5 |
| `test_133b_source_only_registration_exact_order_and_coverage` | 5629 | 1 |
| `test_133b_authority_pins_every_import_and_call` | 5682 | 30 |
| `test_133b_authority_missing_files_fail_closed` | 5699 | 5 |
| `test_133b_authority_registration_batch_and_workflow_drift` | 5716 | 6 |
| `test_133b_runtime_registration_drift_fails_closed` | 5768 | 7 |
| `test_133c_source_only_registration_exact_order_and_coverage` | 5783 | 1 |
| `test_133c_authority_pins_every_import_call_and_edge` | 5855 | 11 |
| `test_133c_authority_missing_files_fail_closed` | 5872 | 3 |
| `test_133c_authority_registration_batch_and_workflow_drift` | 5889 | 6 |
| `test_133d_source_only_registration_exact_order_and_coverage` | 5932 | 1 |
| `test_133d_authority_pins_every_import_call_and_edge` | 6005 | 11 |
| `test_133d_authority_missing_files_fail_closed` | 6022 | 3 |
| `test_133d_authority_registration_batch_and_workflow_drift` | 6039 | 6 |
| `test_133d_runtime_registration_drift_fails_closed` | 6089 | 7 |
| `test_133c_runtime_registration_drift_fails_closed` | 6111 | 7 |
| `test_133e_source_only_registration_exact_order_and_coverage` | 6131 | 1 |
| `test_133e_authority_pins_all_host_runtime_scheduler_and_launcher_edges` | 6190 | 24 |
| `test_133e_authority_missing_files_fail_closed` | 6210 | 6 |
| `test_133e_runtime_registration_drift_rejected` | 6228 | 7 |
| `test_133e_registration_batch_and_workflow_fail_closed` | 6249 | 6 |
| `test_133g_source_only_registration_exact_order_and_coverage` | 6407 | 1 |
| `test_133g_authority_pins_bootstrap_runtime_and_launcher_edges` | 6451 | 6 |
| `test_133g_authority_missing_files_fail_closed` | 6469 | 8 |
| `test_133g_runtime_registration_drift_rejected` | 6487 | 7 |
| `test_133g_registration_batch_and_workflow_fail_closed` | 6507 | 5 |

#### `tests/runtime/checkpoint_runner/test_arch133_h_k.py`

Original module: `tests/runtime/test_checkpoint_runner.py`.

| Original test function | Parent line | Original cases |
| --- | ---: | ---: |
| `test_133h_checkpoint_is_source_only_and_ci_registered` | 6290 | 1 |
| `test_133h_complete_authority_pins_fail_closed` | 6319 | 36 |
| `test_133h_runtime_capability_drift_rejected` | 6343 | 7 |
| `test_133h_batch_workflow_registration_drift` | 6355 | 6 |
| `test_133h_verify_preflight_execute_callbacks_unreachable` | 6382 | 1 |
| `test_133i_source_only_registration_and_inert_callbacks` | 6535 | 1 |
| `test_133i_source_import_closure_pins_fail_closed` | 6577 | 18 |
| `test_133i_runtime_callback_injection_fails_closed` | 6601 | 7 |
| `test_133i_ci_registration_drift_fails_closed` | 6613 | 6 |
| `test_133i_relocated_namespace_pin_rejects_drift` | 6661 | 4 |
| `test_133j_source_only_registration_no_host_callbacks` | 6691 | 1 |
| `test_133j_read_only_import_closure_pins_fail_closed` | 6716 | 14 |
| `test_133j_runtime_callback_injection_fails_closed` | 6740 | 7 |
| `test_133j_ci_registration_drift_fails_closed` | 6752 | 6 |
| `test_133k_source_only_registration_no_host_callbacks` | 6801 | 1 |
| `test_133k_read_only_import_closure_pins_fail_closed` | 6826 | 18 |
| `test_133k_runtime_callback_injection_fails_closed` | 6850 | 7 |
| `test_133k_ci_registration_drift_fails_closed` | 6862 | 6 |

#### `tests/runtime/checkpoint_runner/test_arch133_l_m.py`

Original module: `tests/runtime/test_checkpoint_runner.py`.

| Original test function | Parent line | Original cases |
| --- | ---: | ---: |
| `test_133l_source_only_registration_no_host_callbacks` | 6905 | 1 |
| `test_133l_complete_import_closure_pins_fail_closed` | 6929 | 48 |
| `test_133l_runtime_callback_injection_fails_closed` | 6953 | 7 |
| `test_133l_ci_registration_drift_fails_closed` | 6965 | 6 |
| `test_133m_source_only_registration_no_host_callbacks` | 7008 | 1 |
| `test_133m_complete_import_closure_pins_fail_closed` | 7032 | 48 |
| `test_133m_runtime_callback_injection_fails_closed` | 7056 | 7 |
| `test_133m_ci_registration_drift_fails_closed` | 7068 | 6 |

#### `tests/runtime/checkpoint_runner/test_ci.py`

Original module: `tests/runtime/test_checkpoint_runner.py`.

| Original test function | Parent line | Original cases |
| --- | ---: | ---: |
| `test_docs_changed_path_classification` | 2780 | 14 |
| `test_ci_classification_uses_exact_event_base_and_nul_paths` | 2799 | 2 |
| `test_ci_invalid_base_falls_back_without_git` | 2832 | 7 |
| `test_ci_missing_or_malformed_event_falls_back` | 2843 | 5 |
| `test_ci_unavailable_base_or_nonancestor_falls_back` | 2852 | 2 |
| `test_ci_unknown_diff_and_moved_source_fall_back` | 2874 | 5 |
| `test_ci_docs_gate_evidence_range_check_and_output` | 2897 | 7 |
| `test_docs_gate_rejects_dirty_source` | 2942 | 1 |
| `test_ci_workflow_batch_order_conditions_and_slim_artifacts` | 2957 | 1 |
| `test_batch_workflow_authority_rejects_incomplete_or_ambiguous_invocation` | 3011 | 5 |
| `test_ci_change_gate_against_real_git_range` | 3040 | 8 |
| `test_r2a_workflow_scope_and_narrow_branch_trigger` | 7175 | 1 |

#### `tests/runtime/checkpoint_runner/test_core.py`

Original module: `tests/runtime/test_checkpoint_runner.py`.

| Original test function | Parent line | Original cases |
| --- | ---: | ---: |
| `test_build_verification_steps_runs_both_nonmutating_ruff_gates` | 41 | 1 |
| `test_run_verification_steps_continues_after_lint_failure` | 78 | 1 |
| `test_run_verification_steps_collects_both_ruff_diagnostics` | 116 | 1 |
| `test_registered_profiles_include_current_arch128_gates` | 148 | 1 |
| `test_default_evidence_root_is_outside_repo` | 318 | 1 |
| `test_read_only_effect_guard_rejects_unexpected_mutation` | 537 | 1 |
| `test_remote_branch_head_is_bounded_and_noninteractive` | 549 | 1 |
| `test_remote_branch_head_timeout_fails_closed` | 577 | 1 |
| `test_trusted_remote_head_handoff_requires_exact_lower_hex` | 594 | 1 |
| `test_preflight_checkpoint_accepts_bound_trusted_remote_head` | 612 | 1 |
| `test_preflight_checkpoint_rejects_mismatched_trusted_remote_head` | 659 | 1 |
| `test_preflight_checkpoint_requires_live_remote_head` | 704 | 1 |
| `test_preflight_checkpoint_writes_external_evidence` | 755 | 1 |
| `test_preflight_checkpoint_allows_detached_with_pinned_remote` | 799 | 1 |
| `test_execute_checkpoint_requires_live_remote_head` | 844 | 1 |
| `test_execute_checkpoint_writes_attempt_and_final_evidence` | 896 | 1 |
| `test_execute_checkpoint_preserves_attempt_on_runner_exception` | 945 | 1 |
| `test_batch_first_seen_requirements_and_all_current_coverage` | 2558 | 1 |
| `test_batch_shares_commands_preserves_order_and_collects_authorities` | 2578 | 5 |
| `test_batch_authority_failure_attribution_and_continuation` | 2643 | 2 |
| `test_batch_source_drift_fails` | 2669 | 3 |
| `test_batch_dirty_source_rejected_before_commands_or_authority` | 2684 | 1 |
| `test_batch_cli_rejects_invalid_selection` | 2708 | 4 |
| `test_batch_cli_preserves_order_and_single_verify_dispatch` | 2717 | 1 |
| `test_single_verify_report_and_command_selection_unchanged` | 2735 | 1 |
| `test_r2a_command_elapsed_uses_monotonic_and_preserves_stdout` | 7202 | 4 |
| `test_r2a_elapsed_is_additive_report_evidence_without_status_threshold` | 7238 | 8 |
| `test_r2a_pytest_top_100_duration_flags_are_exact_and_diagnostic_only` | 7265 | 1 |

#### `tests/runtime/checkpoint_runner/test_retained_arch128_130.py`

Original module: `tests/runtime/test_checkpoint_runner.py`.

| Original test function | Parent line | Original cases |
| --- | ---: | ---: |
| `test_current_arch128_authority_profiles_pass` | 299 | 1 |
| `test_parent_preflight_uses_read_only_operator` | 365 | 1 |
| `test_parent_execute_delegates_through_existing_interlock` | 379 | 1 |
| `test_parent_execute_rejects_forbidden_side_effect_evidence` | 398 | 1 |
| `test_r4_execute_delegates_through_existing_interlock` | 417 | 1 |
| `test_r4_execute_accepts_exact_complete_result` | 436 | 1 |
| `test_r4_execute_marks_indeterminate_effect_conservatively` | 458 | 1 |
| `test_r4_execute_rejects_forbidden_side_effect_evidence` | 479 | 1 |
| `test_r4_preflight_attaches_parent_acl_diagnostic` | 504 | 1 |
| `test_r5_substrate_preflight_requires_exact_pid_interlock` | 991 | 1 |
| `test_r5_trading_preflight_uses_fixed_production_command` | 1003 | 1 |
| `test_r7_preflight_delegates_to_read_only_admission` | 1046 | 1 |
| `test_r7_preflight_rejects_effect_evidence` | 1065 | 1 |
| `test_r7_registration_preserves_source_and_preflight_profiles` | 1080 | 1 |
| `test_r7_execute_missing_exact_authorization_never_constructs_host` | 1125 | 4 |
| `test_r7_execute_exact_dispatch_composition_and_pass` | 1149 | 1 |
| `test_r7_execute_possible_mutation_is_conservative` | 1196 | 15 |
| `test_r7_execute_unproven_pre_effect_result_is_conservative` | 1222 | 8 |
| `test_r7_execute_rejects_forbidden_effects` | 1247 | 14 |
| `test_r7_execute_rejects_malformed_pass_recovery_evidence` | 1267 | 16 |
| `test_r7_execute_rejects_incomplete_pass` | 1291 | 5 |
| `test_r7_execute_rejects_malformed_dispatch_result` | 1302 | 4 |
| `test_r7_runner_records_dispatch_failures_as_possible_effect` | 1311 | 3 |
| `test_r7d_authority_rejects_direct_host_and_recovery_calls` | 1371 | 12 |
| `test_r7d_authority_rejects_composition_or_contract_drift` | 1414 | 9 |
| `test_r7d_wrapper_has_no_direct_host_authority` | 1433 | 1 |
| `test_r8_registration_is_read_only` | 1447 | 1 |
| `test_r8_preflight_delegates_once_and_preserves_runner_shape` | 1474 | 2 |
| `test_r8_runner_independently_rejects_effect_drift` | 1509 | 40 |
| `test_r8_runner_rejects_malformed_result` | 1526 | 3 |
| `test_r8_authority_rejects_direct_host_or_effect_calls` | 1591 | 23 |
| `test_r8_authority_freezes_boundary_identity_and_first_wake_policy` | 1643 | 21 |
| `test_r8_authority_rejects_execute_registration_and_wrapper_effects` | 1662 | 3 |
| `test_r2a_active_retained_partition_and_retained_authorities` | 7095 | 1 |
| `test_r2a_explicit_retained_and_mixed_batches_preserve_all_requirements` | 7123 | 3 |
| `test_r2a_retained_individual_cli_dispatch` | 7164 | 8 |

#### `tests/scripts/certification_runner/test_children.py`

Original module: `tests/scripts/test_run_test_certification.py`.

| Original test function | Parent line | Original cases |
| --- | ---: | ---: |
| `test_empty_or_malformed_junit_fails` | 55 | 4 |
| `test_failed_or_error_testcase_fails` | 63 | 2 |
| `test_skipped_is_counted_separately` | 73 | 1 |
| `test_subprocess_failure_propagates` | 96 | 1 |

#### `tests/scripts/certification_runner/test_lanes.py`

Original module: `tests/scripts/test_run_test_certification.py`.

| Original test function | Parent line | Original cases |
| --- | ---: | ---: |
| `test_inventory_partition_is_complete_disjoint_and_deterministic` | 28 | 1 |
| `test_missing_serial_and_duplicate_or_overlap_fail` | 42 | 1 |
| `test_robinhood_has_two_deterministic_balanced_nonempty_lanes` | 871 | 1 |
| `test_empty_lane_never_launches_pytest` | 893 | 3 |

#### `tests/scripts/certification_runner/test_profiles.py`

Original module: `tests/scripts/test_run_test_certification.py`.

| Original test function | Parent line | Original cases |
| --- | ---: | ---: |
| `test_current_robinhood_baseline_and_arch131_registration_coverage` | 700 | 1 |
| `test_current_profile_counts_support_partition_and_serial_allowlist` | 740 | 1 |
| `test_new_owned_modules_are_automatically_admitted` | 812 | 7 |
| `test_missing_or_renamed_required_module_fails_closed` | 822 | 80 |
| `test_retired_families_are_legacy_and_research_is_supported` | 832 | 1 |
| `test_full_missing_or_renamed_frozen_baseline_fails_closed` | 1016 | 226 |
| `test_new_supported_files_are_discovered_and_admitted` | 1050 | 19 |
| `test_unclassified_namespace_fails_every_profile` | 1075 | 20 |
| `test_classification_invariants_fail_closed` | 1085 | 6 |
| `test_ownership_overlap_fails_closed` | 1104 | 1 |

#### `tests/scripts/certification_runner/test_results.py`

Original module: `tests/scripts/test_run_test_certification.py`.

| Original test function | Parent line | Original cases |
| --- | ---: | ---: |
| `test_protected_opt_in_presence_fails_closed` | 90 | 1 |
| `test_plan_never_launches_pytest_and_saves_summary` | 128 | 4 |
| `test_failed_child_sets_failed_summary` | 470 | 1 |
| `test_parser_defaults_to_full_and_rejects_unknown_profile` | 675 | 1 |
| `test_exact_profile_lane_success_accounting` | 907 | 28 |
| `test_all_profiles_reject_protected_opt_ins_before_source` | 956 | 16 |
| `test_static_checks_remain_whole_repository` | 974 | 4 |
| `test_all_profiles_retain_temp_root_requirement` | 995 | 4 |

#### `tests/scripts/certification_runner/test_source.py`

Original module: `tests/scripts/test_run_test_certification.py`.

| Original test function | Parent line | Original cases |
| --- | ---: | ---: |
| `test_source_identity_mismatch_fails` | 191 | 1 |
| `test_live_develop_matching_expected_head_is_accepted` | 286 | 1 |
| `test_live_develop_move_is_rejected_when_local_tracking_ref_is_stale` | 309 | 1 |
| `test_live_feature_move_is_rejected_when_local_tracking_ref_is_stale` | 324 | 1 |
| `test_live_feature_query_maps_tracking_ref_to_exact_remote_branch` | 351 | 1 |
| `test_live_origin_resolver_rejects_nontracking_ref_form` | 369 | 1 |
| `test_missing_live_feature_ref_is_rejected` | 376 | 1 |
| `test_malformed_or_multiple_live_origin_response_is_rejected` | 394 | 2 |
| `test_live_origin_query_failure_is_rejected` | 403 | 1 |
| `test_final_source_verification_repeats_live_origin_proof` | 416 | 4 |
| `test_feature_ref_must_name_origin` | 502 | 1 |

### Focused verification commands

From the named R2-B worktree, with the existing development interpreter:

```powershell
& F:\AI\ai-trading-bot\.venv\Scripts\python.exe -m pytest tests/runtime/checkpoint_runner/test_core.py tests/runtime/checkpoint_runner/test_ci.py tests/runtime/checkpoint_runner/test_retained_arch128_130.py tests/scripts/certification_runner -q --tb=short --basetemp=F:/AI/temp/pytest-r2b-focused-20261008-b -p no:cacheprovider --junitxml=F:/AI/temp/r2b-evidence/focused-b.xml
& F:\AI\ai-trading-bot\.venv\Scripts\python.exe -m pytest tests/runtime/checkpoint_runner/test_arch131.py tests/runtime/checkpoint_runner/test_arch133_a_g.py tests/runtime/checkpoint_runner/test_arch133_h_k.py tests/runtime/checkpoint_runner/test_arch133_l_m.py -q --tb=short --maxfail=8 --basetemp=F:/AI/temp/pytest-r2b-focused-20261008-c -p no:cacheprovider --junitxml=F:/AI/temp/r2b-evidence/focused-c.xml
& F:\AI\ai-trading-bot\.venv\Scripts\python.exe -m pytest tests/runtime/checkpoint_runner/test_retained_arch128_130.py -k retained_individual_verification -q --tb=short --basetemp=F:/AI/temp/pytest-r2b-focused-20261008-e -p no:cacheprovider --junitxml=F:/AI/temp/r2b-evidence/focused-e.xml
& F:\AI\ai-trading-bot\.venv\Scripts\python.exe -m ruff check --no-cache scripts/checkpoint_runner.py scripts/run_test_certification.py tests/runtime/checkpoint_runner tests/scripts/certification_runner
& F:\AI\ai-trading-bot\.venv\Scripts\python.exe -m ruff format --check --no-cache scripts/checkpoint_runner.py scripts/run_test_certification.py tests/runtime/checkpoint_runner tests/scripts/certification_runner
git diff --check
```

Group B: 817 passed / 0 skipped / 0 failed/errors in 28.59 s.
The additional retained individual source-contract proof: 1 passed / 211
deselected in 0.29 s. The first combined attempt stopped at 12 relocation-only
failures after 478 passes; registration-mutation literals and one expected
module set were corrected. Its duration was 128.61 s. The new retained proof's
first attempt asserted a nonexistent report field; the assertion was corrected
to inspect the existing recorded command requirements without changing schema.
Ruff check/format and diff checks pass; terminal remaining group and CI results
will be recorded separately. Reusing these exact basetemps is not permitted;
choose fresh names for any future rerun.

### R2-B focused completion before implementation publication

All **2,003 distinct final cases passed**, with no skipped, failed or error
outcomes remaining. This comprises group B's 817, Architecture 131/A–G's 903
passes from group C, the corrected H–M group's 282, and the extra retained
individual verification proof's one pass. Group C stopped at eight expected
workflow/order isolation failures after 1,006 passes in 270.15 s; those cases
were restored to real-chain execution and only H–M was rerun. Group F passed
282 in 116.88 s. A final certification-admission follow-up (group G) passed
469 in 3.94 s after ensuring real `run()` admission and direct `select_inventory()`
both enforce the deliberately required retained replacement. Group G repeats
already counted cases and does not increase the 2,003 distinct count.

Additional exact focused commands:

```powershell
& F:\AI\ai-trading-bot\.venv\Scripts\python.exe -m pytest tests/runtime/checkpoint_runner/test_arch133_h_k.py tests/runtime/checkpoint_runner/test_arch133_l_m.py -q --tb=short --maxfail=5 --basetemp=F:/AI/temp/pytest-r2b-focused-20261008-f -p no:cacheprovider --junitxml=F:/AI/temp/r2b-evidence/focused-f.xml
& F:\AI\ai-trading-bot\.venv\Scripts\python.exe -m pytest tests/scripts/certification_runner/test_profiles.py tests/scripts/certification_runner/test_results.py -q --tb=short --basetemp=F:/AI/temp/pytest-r2b-focused-20261008-g -p no:cacheprovider --junitxml=F:/AI/temp/r2b-evidence/focused-g.xml
```

| Split module | Final focused cases |
| --- | ---: |
| `tests/runtime/checkpoint_runner/test_arch131.py` | 698 |
| `tests/runtime/checkpoint_runner/test_arch133_a_g.py` | 205 |
| `tests/runtime/checkpoint_runner/test_arch133_h_k.py` | 153 |
| `tests/runtime/checkpoint_runner/test_arch133_l_m.py` | 129 |
| `tests/runtime/checkpoint_runner/test_ci.py` | 58 |
| `tests/runtime/checkpoint_runner/test_core.py` | 50 |
| `tests/runtime/checkpoint_runner/test_retained_arch128_130.py` | 212 |
| `tests/scripts/certification_runner/test_children.py` | 8 |
| `tests/scripts/certification_runner/test_lanes.py` | 6 |
| `tests/scripts/certification_runner/test_profiles.py` | 410 |
| `tests/scripts/certification_runner/test_results.py` | 59 |
| `tests/scripts/certification_runner/test_source.py` | 15 |

## R2-B terminal implementation report

### Startup admission

The exact existing worktree was clean at the documented lag parent
`8129bac92ce84628048ccafc76815f6511c0990d` / tree
`3ee934821ace692e74bebe201445300062487d17`. Branch and origin matched exactly.
Only the named remote feature branch was fetched; live origin was proved at
`4b81a822d55fa5e79460294f46239d133170a157` / tree
`5725e64ac35be890f3e6ab00793d1a11c0b7b5f0`. Ancestry was proved before the
expressly authorized `git merge --ff-only` to that exact admitted HEAD.
Final HEAD/tree and clean worktree/index were reverified before editing.

### Exact implementation file set

Against the admitted parent (A = added, D = deleted, M = modified):

```text
M	.github/workflows/checkpoint-source-gates.yml
M	docs/AI_TRADING_BOT_HANDOFF.md
M	docs/PROJECT_STATUS.md
M	docs/architecture/132-tiered-certification-profiles.md
M	docs/validation/arch132-r2-test-suite-rationalization-plan.md
M	scripts/checkpoint_runner.py
M	scripts/run_test_certification.py
A	tests/runtime/checkpoint_runner/__init__.py
A	tests/runtime/checkpoint_runner/helpers.py
A	tests/runtime/checkpoint_runner/test_arch131.py
A	tests/runtime/checkpoint_runner/test_arch133_a_g.py
A	tests/runtime/checkpoint_runner/test_arch133_h_k.py
A	tests/runtime/checkpoint_runner/test_arch133_l_m.py
A	tests/runtime/checkpoint_runner/test_ci.py
A	tests/runtime/checkpoint_runner/test_core.py
A	tests/runtime/checkpoint_runner/test_retained_arch128_130.py
D	tests/runtime/test_checkpoint_runner.py
A	tests/scripts/certification_runner/__init__.py
A	tests/scripts/certification_runner/helpers.py
A	tests/scripts/certification_runner/test_children.py
A	tests/scripts/certification_runner/test_lanes.py
A	tests/scripts/certification_runner/test_profiles.py
A	tests/scripts/certification_runner/test_results.py
A	tests/scripts/certification_runner/test_source.py
D	tests/scripts/test_run_test_certification.py
```

The two removed monoliths are test relocations only. Their complete 267-function,
1,941-original-case mapping appears above. Inert shared `helpers.py` and
`__init__.py` files contain no collected tests. All production source pins,
product test/Ruff path order, active/retained sequences and production authority
chaining remain unchanged. Thirty-eight registration AST hashes were deliberately
migrated for infrastructure tuple references; no production source pin was
relaxed.

### Terminal module accounting

Zero CI cases below means deliberately unselected by routine active CI; those
contracts were independently exercised in focused verification.

| Split module | Focused cases | Terminal source CI cases |
| --- | ---: | ---: |
| `tests/runtime/checkpoint_runner/test_arch131.py` | 698 | 698 |
| `tests/runtime/checkpoint_runner/test_arch133_a_g.py` | 205 | 205 |
| `tests/runtime/checkpoint_runner/test_arch133_h_k.py` | 153 | 153 |
| `tests/runtime/checkpoint_runner/test_arch133_l_m.py` | 129 | 129 |
| `tests/runtime/checkpoint_runner/test_ci.py` | 58 | 58 |
| `tests/runtime/checkpoint_runner/test_core.py` | 50 | 50 |
| `tests/runtime/checkpoint_runner/test_retained_arch128_130.py` | 212 | 0 |
| `tests/scripts/certification_runner/test_children.py` | 8 | 0 |
| `tests/scripts/certification_runner/test_lanes.py` | 6 | 0 |
| `tests/scripts/certification_runner/test_profiles.py` | 410 | 410 |
| `tests/scripts/certification_runner/test_results.py` | 59 | 0 |
| `tests/scripts/certification_runner/test_source.py` | 15 | 0 |

### Missing/changed source-pin proof

| Layer | Pinned sources | Missing cases | Changed cases |
| --- | ---: | ---: | ---: |
| 133-H | 18 | 18 | 18 |
| 133-I | 9 | 9 | 9 |
| 133-J | 7 | 7 | 7 |
| 133-K | 9 | 9 | 9 |
| 133-L | 24 | 24 | 24 |
| 133-M | 24 | 24 | 24 |

All 182 H–M pin mutations remain. Every original runtime test decorator/matrix
was compared against the admitted parent's AST; only deliberate registration
literal/path relocations differ. Original 131/A–G matrices and retained rejection
contracts remain accounted for in the inventory. Runtime injection matrices
retain preflight, execute, wrong branch, wrong remote-authority environment,
missing tests, missing Ruff coverage and wrong authority callbacks.

Local I–M pin/runtime tests patch only the immediate predecessor. They copy only
the local pinned closure plus runner/workflow and exercise the actual local
function both on valid input and the mutation. H pin tests exercise real H.
All 30 I–M runner/workflow missing/duplicate/order cases explicitly use
`isolate_predecessor=False`, copying the complete predecessor closure and
retaining real-chain rejection. Recursive copy-helper assertions are eliminated.
Separate parameterized tests prove each I–M function calls its predecessor once
and propagates a rejection marker. The transparent trace test executes every
real M→L→K→J→I→H body and verifies call order/PASS; the original accepted-source
registration tests also retain unpatched real-chain PASS checks.

Retained source-only verification is proved by the individual `arch128-r4`
verification test with fake child commands and real authority, eight individual
CLI dispatch cases, real retained authority PASS checks, and retained-only/mixed
batch cases with fake child commands. No retained protected execution ran.

### Command evidence

| CI command | Exit | elapsed_seconds |
| --- | ---: | ---: |
| `pytest` | 0 | 353.5722111 |
| `ruff_check` | 0 | 0.12955919999996013 |
| `ruff_format` | 0 | 0.11001320000002579 |
| `git_diff_check` | 0 | 0.03126209999999219 |

### Top-100 slowest summary

All 100 entries are call durations. Exact unabridged output is in the artifact
stdout path cited above. Counts by module: 133-L–M 41, Architecture 131 29,
133-H–K 20, CI eight, 133-A–G two. The five slowest are:

| Seconds | Test |
| ---: | --- |
| 1.94 | `tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133m_ci_registration_drift_fails_closed[duplicate-runner]` |
| 1.93 | `tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133m_ci_registration_drift_fails_closed[missing-runner]` |
| 1.91 | `tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133m_ci_registration_drift_fails_closed[order-runner]` |
| 1.82 | `tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133m_ci_registration_drift_fails_closed[duplicate-workflow]` |
| 1.82 | `tests/runtime/checkpoint_runner/test_arch133_l_m.py::test_133m_ci_registration_drift_fails_closed[order-workflow]` |

### Deviations and next owner

The requested interpreter path was absent; the existing development `.venv`
interpreter was used. Path counts increase due to deliberate selectability;
measured case count and wall time decrease. Source CI adds JUnit artifact
output solely for module-count evidence; R2-A timing, execution order, branch
triggers, docs-only fast path and single-job topology remain unchanged.

No unresolved focused/source-CI failure remains. Source acceptance and final
certification are pending. No protected operation or broad local certification
was run. The one optional MCP OAuth import skip is recorded above.

Ready-to-paste next action for ChatGPT:

> Review Architecture 132-R2-B's exact GitHub implementation commit
> `40aa7ef55a528fe7b7d9482d083ef1dcfed4dfb1`, tree
> `0781d9ecb3dcaf87888506e2b833fb8106f35990`, against admitted parent
> `4b81a822d55fa5e79460294f46239d133170a157`, with source CI
> #291 / 37726690416 SUCCESS and this terminal evidence descendant. Check
> complete logical relocation, frozen baseline migration, active/retained
> selectivity, real workflow/order rejection and predecessor/full-chain coverage.
> Decide source acceptance and final certification selection; FULL is expected
> after acceptance because topology changed unless exact review establishes
> stronger equivalent evidence. Supply the exact admitted local certification
> command. Do not begin R2-C/R2-D or resume real 133-M/protected operations.
