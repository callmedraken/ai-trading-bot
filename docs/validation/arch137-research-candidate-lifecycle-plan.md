# Architecture 137 / RCL-1 — Research candidate validation

Status: SOURCE ACCEPTED at HEAD `2ade3899e2ec97aa53f9cc7af3bfdbe5bab786a6`, TREE `9d33c980510f841f6dd254b3ff9f587ac2f43203`.

## Terminal acceptance evidence

Fresh repository Checkpoint Source Gates #510 /
[38346016265](https://github.com/callmedraken/ai-trading-bot/actions/runs/38346016265)
completed SUCCESS on the exact accepted HEAD.

- source-static: 62/62 current authorities PASS, 83 test paths, 356 Ruff paths,
  PYTEST=SKIP, identity stable
- shard 0: 17 paths / 88.439 s
- shard 1: 21 paths / 84.138 s
- shard 2: 23 paths / 91.002 s
- shard 3: 22 paths / 59.167 s
- active-tests: SKIPPED as expected
- certification-tests: SKIPPED as expected
- terminal source-gates: PASS

All shard runtimes are below 300 seconds. Combined with the focused 162-case
candidate/report verification and 418-case inventory/R1/R2 authority verification
below, this closes the source evidence without a local broad certification run.

## Scope and prior accepted evidence

The research implementation starts at HEAD
`778151fe8f91632a1af66384a3ab0a85d8d65069`, TREE
`03c50482427b04ebfc6ed061d048bb95e86edeae`. GUI-A15 remains accepted at
HEAD `1dd46169deb69d7a381687b6ba835af9d6c12e5a`, TREE
`383b237aebfc553b10c7a5ef121a0191559c3f11`, with dedicated GUI CI
[38343026765](https://github.com/callmedraken/ai-trading-bot/actions/runs/38343026765)
and repository CI
[38343142780](https://github.com/callmedraken/ai-trading-bot/actions/runs/38343142780)
terminal SUCCESS. Those are prior accepted evidence, not new RCL-1 acceptance.

R1 `6bf8753b0cc8950ae27b32b6858b64d454c512f0` and R2
`2f122958366d1db282fea51abbd461b83fa893d9` remain frozen. D1 proving
remains independent and protected; D2 remains disconnected. No production effect,
compatibility bridge, promotion or qualification policy is introduced.

## Focused checks

`tests/experiments/test_research_candidate.py` uses the existing completed
compact-report fixture and its deterministically identified unranked projection.
It does not execute an experiment to create candidate evidence. Coverage checks:

- the exact six-stage order EXPERIMENTAL, BACKTESTED, WALK_FORWARD_PASSED, SHADOW,
  PAPER_CANDIDATE, AWAITING_HUMAN_PROMOTION and package exports;
- immutable fixed BACKTESTED materialization and rejection of forged stages;
- UUID5 framing, retained semantic sensitivity, repeatability and Decimal-context
  independence;
- exact UUID/type/HEAD/TREE, ordinal/name/rank bounds and invalid bools;
- explicit rank-1/rank-2/unranked selection, missing/duplicate variant rejection
  and absence of automatic selection;
- candidate/report revalidation and independent report_id, result_id, variant_id,
  ordinal, name and rank reconciliation;
- strict JSON roundtrip, exact field set, duplicates, unknown/missing fields,
  constants, representation drift and forged identity;
- exact AST import allowlist, absence of filesystem/network/provider/credential/
  storage/scheduler/runtime/production-conversion capability.

Candidate + directly affected report tests: **162 passed**.
Profile tests plus the seven affected current-inventory assertions and exact
source-only R1/R2 authority checks: **418 passed**.
Both runs used quiet pytest and disabled cache output. An initial test expected
the wrong exception for dataclasses.replace on a fixed field under Python 3.14;
the corrected cross-version test accepts TypeError/ValueError. No domain
behavior changed in that correction.

Reproducible commands from the requested worktree:

```powershell
python -m pytest -q --tb=short -p no:cacheprovider tests/experiments/test_research_candidate.py tests/experiments/test_report.py
python -m pytest -q --tb=short -p no:cacheprovider tests/scripts/certification_runner/test_profiles.py tests/strategies/test_production_strategy_contract.py::test_checkpoint_is_source_only_and_profile_inventory_is_exact tests/strategies/test_production_strategy_decision.py::test_checkpoint_registration_and_inventory_are_exact tests/review_paper/test_production_strategy_cycle.py::test_checkpoint_and_certification_inventory_are_exact tests/review_paper/test_supervised_deployment_qualification.py::test_registration_workflow_profiles_and_authority_chain tests/review_paper/test_supervised_maintenance_rebind.py::test_source_registration_inventory_and_pins tests/review_paper/test_supervised_runtime_host_admission.py::test_source_registration_profiles_and_authority tests/review_paper/test_production_paper_runtime.py::test_registration_source_only_and_authority tests/review_paper/test_production_paper_runtime_acl.py::test_registered_source_only_authority_and_canonical_mapping
```

Final non-mutating focused Ruff check **PASS**, Ruff format check **PASS**
(11 Python files already formatted) and git diff check **PASS** before exact-file
staging. Both Ruff phases ran before deciding failure, with non-mutating diff
diagnostics required for any failed phase.

## Inventory and pin reconciliation

Use `scripts.run_test_certification.discover_inventory` and `select_inventory`
for final inventory, and the canonical `ACTIVE_CI_CHECKPOINTS` for ACTIVE:

```text
ACTIVE 62
FULL 170
ROBINHOOD 94
LEGACY 215
EXHAUSTIVE 385
tests/gui 44
```

Only FULL/EXHAUSTIVE increase. No ACTIVE checkpoint is added. Current count
assertions in profile/production-strategy/supervised tests change accordingly;
the full-profile exact expectation includes the new module. Three R1-retained
test-file blob pins change: profile, production strategy contract and production
strategy decision tests. Production executables/native/AST pins, the ACTIVE
tuple digest and historical publication-recovery pins remain unchanged. Exact
R1 and R2 source-only authority tests pass on the resulting tree.

## Repository CI closeout

The requested exact-source repository dispatch is complete and accepted as
recorded above. No further broad rerun is required for Architecture 137.
Architecture 138 must separately define the deterministic
ResearchCandidateWalkForwardQualificationPolicy; existing walk-forward evidence
alone still cannot materialize WALK_FORWARD_PASSED. Research-to-production
compatibility remains a separate future review boundary.


## Operational effect freeze

All counts describe this implementation's operational effects; test fixture
validation and historical focused simulated-report checks grant no operation.

```text
PRODUCTION_SQLITE_READS=0
PRODUCTION_SQLITE_WRITES=0
CREDENTIAL_READS=0
PROVIDER_CALLS=0
BROKER_CALLS=0
SCHEDULER_CALLS=0
ACL_MUTATIONS=0
PAPER_MUTATIONS=0
RESEARCH_EXECUTIONS=0
WALK_FORWARD_EXECUTIONS=0
STRATEGY_PROMOTIONS=0
PRODUCTION_CONTRACTS_CREATED=0
D1_OPERATIONS=0
D2_SUPERVISOR_EXECUTIONS=0
```
