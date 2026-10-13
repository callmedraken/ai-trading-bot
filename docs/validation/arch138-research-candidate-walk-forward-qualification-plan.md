# Architecture 138 / RCL-2 — Focused qualification validation plan

Status: SOURCE ACCEPTED at HEAD `e0735af265894757ff9b90ab185bcbd77ee2dee9`, TREE `a29f51faaa81e866d0825ffbe082c5fcddb94584`; Checkpoint Source Gates #516 / 38380502369 SUCCESS.

## Acceptance evidence

Exact accepted executable/test source is HEAD
`e0735af265894757ff9b90ab185bcbd77ee2dee9`, TREE
`a29f51faaa81e866d0825ffbe082c5fcddb94584`, one commit after exact parent
`6e2081a1278f579ca0cee5a00e2bd83632bc2856` /
`5858cc644d78eab9bbe58d1332f02c1b56aa5c65`.

Checkpoint Source Gates #516 / 38380502369 is terminal SUCCESS on that exact
source. source-static verified 62/62 authorities, 83 test paths and 356 Ruff
paths with git diff/Ruff check/Ruff format PASS and stable source identity.
Broad shards passed 2,174 / 2,050 / 1,880 / 2,350 cases plus one optional SDK
skip: 8,454 passed, 1 skipped, 0 failed/errors. Hygiene times were
98.041 / 91.323 / 92.354 / 106.281 seconds. active-tests and
certification-tests were skipped as expected; terminal source-gates PASSed.

Focused implementation evidence records 723 distinct passing cases. Exactly
three retained Architecture-134 test-file Git-blob pins changed and were
independently matched to the committed blobs. No operational effect occurred.

Architecture 139 / RCL-3 owns the next lifecycle boundary: deterministic
no-effect SHADOW observation/qualification evidence. RCL-2 itself grants no
SHADOW, compatibility, approval, promotion, D1 or D2 authority.

Exact parent HEAD `6e2081a1278f579ca0cee5a00e2bd83632bc2856`, TREE
`5858cc644d78eab9bbe58d1332f02c1b56aa5c65`. Branch
`feature/research-candidate-walk-forward-qualification`; worktree
`F:\AI\worktrees\ai-trading-bot-research-candidate-walk-forward-qualification`.
The Architecture-138 authority document freezes policy/result/successor schemas,
UUID5 namespaces and every ordered length-framed identity field.

## Focused evidence and test contract

The new test module covers exact frozen models, no-default policy constraints,
complete semantic identity sensitivity and independent UUID5 framing; exact
Decimal context independence; strict types/finite/bounds/threshold validation;
compact sorted canonical JSON with duplicates/missing/unknown fields, identity,
status/reason/stage/schema and representation forgery rejection; and separate
external reconciliation of candidate/report/walk-forward/policy/source evidence.

Rank-one, rank-two and unranked original BACKTESTED evidence can qualify when the
candidate wins every training fold. Original rank remains evidence and is copied
unchanged. Losing one/all folds and differing winners are valid FAILED evidence.
Missing candidate and ordinal/name disagreement are malformed. Revalidation uses
defensive copies and preserves caller evidence on both valid and failed paths,
including noncanonical sequences and selected-rank bool forgery with a recomputed
upstream identity. Minimum folds, both comparability dimensions, exact inclusive
threshold equality and all six simultaneous failures are covered.

The analyzer spy proves one invocation, exact derived policy UUID, the fixed two
metrics and three operations, empty metadata and retained aggregate identity.
No caller aggregate injection or runner invocation is available. Completed
fixtures are produced only through accepted in-memory fake simulators; neither
new qualification nor successor builders execute research/provider work.
Existing immutable tracked fixtures are unchanged. Static tests freeze the exact
pure import allowlist, public upstream model names, absence of private imports,
runner/production imports, current time/random UUID, filesystem/network methods,
generic lifecycle mutation and promotion APIs.

Local evidence (Python in the existing repository virtual environment):

- Initial new-module run: 109 passed / 5.62 s.
- Candidate/report/walk-forward/aggregate plus then-current new tests:
  302 passed, one new identity-test assertion failed / 5.67 s. The test had an
  off-by-one slice in independently assembling framed material; domain source did
  not change. The affected identity test then passed / 2.96 s.
- Final new module after additional semantic defenses: 128 passed / 3.45 s.
- Profile/current-inventory and exact R1/R2 authority checks: 418 passed / 6.98 s.
- Distinct final coverage: 128 new + 177 retained domain + 418 inventory/authority
  cases = 723 passed. Intermediate duplicate runs are not added to this total.

Fresh external temporary roots were used under `F:\AI\temp\pytest\arch138-*`,
with `-B -p no:cacheprovider`; no local broad profile ran.
The system Python had no pytest/Ruff installed, so focused checks used the existing
`F:\AI\ai-trading-bot\.venv\Scripts\python.exe`. No dependencies were installed.

Reproducible focused commands from this worktree (use a fresh unique basetemp):

```powershell
& F:\AI\ai-trading-bot\.venv\Scripts\python.exe -B -m pytest -q --tb=short -p no:cacheprovider --basetemp F:/AI/temp/pytest/arch138-domain-<unique> tests/experiments/test_research_candidate_walk_forward.py tests/experiments/test_research_candidate.py tests/experiments/test_report.py tests/experiments/test_walk_forward.py tests/experiments/test_walk_forward_analytics.py
& F:\AI\ai-trading-bot\.venv\Scripts\python.exe -B -m pytest -q --tb=short -p no:cacheprovider --basetemp F:/AI/temp/pytest/arch138-authority-<unique> tests/scripts/certification_runner/test_profiles.py tests/strategies/test_production_strategy_contract.py::test_checkpoint_is_source_only_and_profile_inventory_is_exact tests/strategies/test_production_strategy_decision.py::test_checkpoint_registration_and_inventory_are_exact tests/review_paper/test_production_strategy_cycle.py::test_checkpoint_and_certification_inventory_are_exact tests/review_paper/test_supervised_deployment_qualification.py::test_registration_workflow_profiles_and_authority_chain tests/review_paper/test_supervised_maintenance_rebind.py::test_source_registration_inventory_and_pins tests/review_paper/test_supervised_runtime_host_admission.py::test_source_registration_profiles_and_authority tests/review_paper/test_production_paper_runtime.py::test_registration_source_only_and_authority tests/review_paper/test_production_paper_runtime_acl.py::test_registered_source_only_authority_and_canonical_mapping
```

Run both non-mutating Ruff phases on the 11 changed Python paths before deciding
PASS/FAIL: `ruff check --no-cache` and `ruff format --check --no-cache`; emit
`ruff check --diff --no-cache` / `ruff format --diff --no-cache` for failed phases,
then stop if either exit code is nonzero. Run `git diff --check`.
Final Ruff check PASS; Ruff format check PASS (11 files already formatted);
git diff --check PASS.
Formatting/import ordering of new files was an explicit implementation edit,
not a mutating operator verification gate.

## Discovery and retained pins

Canonical discover_inventory/select_inventory functions yield ACTIVE 62,
FULL 171, ROBINHOOD 94, LEGACY 215, EXHAUSTIVE 386 and tests/gui 44.
Seven current exact count maps and the FULL exact test list are reconciled.
Only these LF-normalized Git-blob test pins change in
ARCH134_PRODUCTION_PAPER_RUNTIME_SOURCE_PINS:

| Test path | Previous blob | New blob |
| --- | --- | --- |
| tests/scripts/certification_runner/test_profiles.py | 71903964f3bc13039d49451740f16a14470673ac | 46e93ca65eedf6fb72712806c297873a8593af37 |
| tests/strategies/test_production_strategy_contract.py | 5dbb515c077e000fa56bb0aebc2ec2681a2e1074 | ba9af47714203bb6a63499a261861ebcd53baff7 |
| tests/strategies/test_production_strategy_decision.py | 5a124f1d02d3809a18d31b95ba1e8d52cc11baef | 603902f41c9c65209b6fcac504286de7a9094912 |

All executable/native/AST pins, ACTIVE_CI_CHECKPOINTS/digest, historical recovery
pins, Architecture-137 artifact/fixture bytes and workflow bytes remain frozen.
No ACTIVE/production checkpoint is introduced.

## Exact CI and handoff

The branch is deliberately outside the production push allowlist. After exact
staging, staged path-set/diff checks, one normal commit and ordinary push, verify
remote HEAD/TREE then dispatch exactly one fresh Checkpoint Source Gates workflow
against that exact branch/HEAD. Wait for terminal evidence. Expected routing:
source-static and every current authority PASS; four broad shards PASS; active-tests
and certification-tests SKIPPED; terminal source-gates PASS. Each shard must stay
below 300 seconds. No missing run, queued run, failure or incomplete evidence is
acceptance. If CI fails, inspect complete failing evidence, correct only that
bounded defect, run focused checks, ordinary-push a correction and dispatch once
on the new exact HEAD. No amend/rebase/force-push/PR operation is authorized.

Do not substitute local FULL/ROBINHOOD/LEGACY/EXHAUSTIVE certification or real
research/provider/operator execution. Once terminal CI is green, STOP and return
exact HEAD/TREE/path set plus tests/static/pins/inventory/CI/effect accounting.
ChatGPT owns exact GitHub review, source acceptance and the next architecture.
Canonical status/handoff entries remain implementation-pending until that review.

## Operational zero effects

```text
PRODUCTION_SQLITE_READS=0
PRODUCTION_SQLITE_WRITES=0
CREDENTIAL_READS=0
PROVIDER_CALLS=0
BROKER_CALLS=0
SCHEDULER_CALLS=0
ACL_MUTATIONS=0
PAPER_MUTATIONS=0
REAL_RESEARCH_EXECUTIONS=0
REAL_WALK_FORWARD_EXECUTIONS=0
STRATEGY_PROMOTIONS=0
PRODUCTION_CONTRACTS_CREATED=0
D1_OPERATIONS=0
D1R2_RECOVERY_OPERATIONS=0
D2_SUPERVISOR_EXECUTIONS=0
```

Pure in-memory test fixture/analytics work is not an operational effect.
No production D1/D1R1/D1R2 worktree, branch or `F:\AITradingBot\Arch134D1`
artifact is read or modified. SHADOW or production authority is never inferred.
Real-money placement remains NO-GO.
