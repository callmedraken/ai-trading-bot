# Architecture 139-A / RCL-3A — current-lineage forward-port validation

Status: **SOURCE ACCEPTED** at HEAD `bf500ffecefe0a8be8117e315228e3bc07ffdf54`, TREE `69d4ee1d6e7b3c2ca095b3ddf3cf05fdb7e3babd`; Checkpoint Source Gates #562 / `38640090298` SUCCESS. That accepted identity covers 139-A. B1 implementation is pending exact-source review; B2 is gated below.

## Terminal acceptance evidence

Fresh Checkpoint Source Gates #562 / `38640090298` completed SUCCESS on the
exact pushed source in one dispatch/attempt. source-static passed all 64 current
authorities with 88 test paths and 372 Ruff paths; git diff, Ruff check and Ruff
format passed. The four broad shards completed in 90.389 / 98.647 / 104.755 /
121.06 seconds, all below the 300-second hygiene ceiling. active-tests and
certification-tests skipped as expected for this unmapped research dispatch.

Focused verification records 1,808 distinct passing cases. The three required
historically accepted 139-A blobs match exactly, all seven current successor
blobs match the committed Git blobs, and D1Q/D1R3/D1R4/D1R4R/D1R5 authority
checks pass with predecessor dictionaries frozen. No protected or operational
effect occurred.

## Admission and unchanged accepted semantics

Current isolated worktree:
`F:\AI\worktrees\ai-trading-bot-research-candidate-shadow-variant-binding-current`.
Branch: `feature/research-candidate-shadow-variant-binding-current`.
Initial index/worktree were clean; origin was exactly
`https://github.com/callmedraken/ai-trading-bot.git`. Exact base:

```text
HEAD 69bf101556a62788b9dd9a1ce82c706c9c977c44
TREE a1b566d8642a06553caa3bb029c81d7ece5541d2
138 executable HEAD a9c3682231f8540be6e9dc6f2bfecd06ecf1a8b1
138 executable TREE 55841f5119228dbf302747256326d43ff7d32e23
138 CI #561 / 38634855492 SUCCESS
```

Ancestry and the live accepted research ref were verified before edits. The
historical accepted reference is HEAD `e730b3b05c0c78181a4b3ff6b8e257cb04f3ff15`,
TREE `ea13572c565bcfe65959014bf1c98572c89cc3a7`, CI #517 / `38387248166`
SUCCESS, parent `1af8150c9985f5dc7ad1e143a16d90dcdc86be1a`. No stale-branch
merge/rebase/cherry-pick is used. The [architecture contract](../architecture/139-research-candidate-shadow.md)
records all three mandatory accepted blobs. Any mismatch is a STOP.

No production store/artifact, operational qualification, D1R5 execution,
credential, provider, broker or scheduler surface is accessed.

## Focused verification

Use the existing development interpreter, `-B -p no:cacheprovider`, and a fresh
external basetemp for each invocation. No dependencies are installed.

```powershell
& {
    $Arch139Temp = Join-Path 'F:\AI\temp\pytest' ('arch139a-current-domain-' + [guid]::NewGuid().ToString('N'))
    & F:\AI\ai-trading-bot\.venv\Scripts\python.exe -B -m pytest -q --tb=short -p no:cacheprovider --basetemp $Arch139Temp tests/experiments/test_research_candidate_shadow_binding.py tests/experiments/test_research_candidate_walk_forward.py tests/experiments/test_research_candidate.py tests/experiments/test_report.py tests/experiments/test_historical.py tests/experiments/test_walk_forward.py tests/experiments/test_walk_forward_analytics.py
    if ($LASTEXITCODE -ne 0) { throw '139-A focused domain verification failed' }
}
```

The accepted 222-case binding module freezes exact types, UUID5 framing and
all retained semantic fields; caller ordinal/name/rank; independent complete
report/result/request/run/variant reconciliation; strict JSON; frozen/slotted
artifacts; exact original variant object resolution; defensive validation and
caller immutability even on failure; Decimal precision/trap independence;
lossy historical identity rejection; prior bytes; and no runner/simulator/effect
capability. Prior 137/138, report, historical, walk-forward and aggregate
coverage runs alongside it using synthetic fixtures/fake execution edges only.

Directly affected current inventory/authority coverage includes all seven
successor files plus production paper runtime/ACL, Alpaca authentication and
pre-market wake qualification tests. The new successor tests reject missing,
extra-test, executable/source and wrong-blob overrides at each affected authority
entry point. Frozen digest cases cover all required predecessor dictionaries,
including D1R4/D1R4R and Architecture 138. Untouched D1R5 pins and exact successor
blobs are independently compared to the actual worktree Git blobs.

AST comparison against the exact base must show all existing Architecture-134,
Architecture-138, ACTIVE and profile constant definitions unchanged. Verify
Architecture-138 domain source/test blobs and workflow bytes independently.
D1Q/D1R3/D1R4/D1R4R/D1R5 authority checks must all PASS before publication.

Run both non-mutating Ruff phases over the 11 touched Python files:
`ruff check --no-cache` and `ruff format --check --no-cache`. On failure, emit
the corresponding `--diff --no-cache` diagnostics before deciding failure after
both phases. Run `git diff --check`. No local certification profile runs.
Focused research coverage passed **548 cases in 32.84 seconds**, including the
222 unchanged accepted binding cases. The 11 directly affected inventory/authority
modules passed **1,260 cases in 56.54 seconds**. These sets are disjoint:
**1,808 distinct cases passed**, with zero failures/errors/skips. Focused Ruff
lint and format checks passed on all 11 touched Python files; diff check passed.
Independent checks confirmed all three accepted 139-A blobs, unchanged 138
domain/test/workflow blobs, all seven successor blobs and all five authority
checks. All 72 existing Architecture-134/138/ACTIVE/profile constant definitions
match the exact base AST. No local broad certification ran.

## Canonical inventory and seven-path successor overlay

Canonical discovery verified before/after:

| Inventory | Before | After |
| --- | ---: | ---: |
| ACTIVE | 64 | 64 |
| FULL | 176 | 177 |
| ROBINHOOD | 98 | 98 |
| LEGACY | 215 | 215 |
| EXHAUSTIVE | 391 | 392 |
| tests/gui | 44 | 44 |

No ownership, required baseline, checkpoint membership, ACTIVE digest, D1R5
registration, executable/native/AST pin or workflow change is permitted.
`ARCH139A_CURRENT_INVENTORY_TEST_PIN_OVERRIDES` follows the existing 138 resolver
at all five sites. Historical -> HIST2 -> D1R5 -> 138 -> 139-A -> actual blob
comparison is test-only. Every predecessor dictionary stays exact/frozen.

| Test path | Successor Git blob |
| --- | --- |
| tests/scripts/certification_runner/test_profiles.py | cacc61cc25e1b6ba9db866767758b13c91f92aff |
| tests/strategies/test_production_strategy_contract.py | 2f72359ba9338ea0969469de216ee602be6df4d4 |
| tests/strategies/test_production_strategy_decision.py | 411d18876f33ac456c5fd5efa4d73bf6294bb3ea |
| tests/review_paper/test_production_strategy_cycle.py | ca217d4214141bcdac7e2e7ecd1b8f7b5d058853 |
| tests/review_paper/test_supervised_deployment_qualification.py | 11471897d25ae60cb8bf893b2f8ce39217f2082d |
| tests/review_paper/test_supervised_runtime_host_admission.py | e623a7eb9483e540f13f8e97d4b4b6c1e4a285d7 |
| tests/review_paper/test_supervised_maintenance_rebind.py | 0d71948f511aa7cf2c2313e78cda6c9326bd6f65 |

## Publication and acceptance boundary

After focused PASS: verify the initially clean index; stage exactly the 13
intended paths; compare the staged filename set; run cached diff check; make one
normal checkpoint commit; ordinary-push only the fresh research branch; verify
exact remote HEAD/tree. Dispatch exactly one fresh Checkpoint Source Gates run
and wait for terminal evidence. This research branch remains outside the
production push allowlist; explicit workflow_dispatch is the reviewed route.
Do not treat an absent push-triggered run as PASS or modify workflow bytes.

Require source-static/all 64 authorities and four broad shards PASS, each
shard below 300 seconds; active-tests/certification-tests skip as expected for
the unmapped research dispatch; terminal source-gates PASS. Preserve failures;
no blind retry, amend, rebase, force-push, merge or PR mutation.

The implementation stop boundary is complete: terminal CI and exact GitHub
source review both passed. Architecture 139-A is SOURCE ACCEPTED on the identity
recorded above. The bounded status/handoff closeout records it as a parallel
safe-side checkpoint without changing the active D1R5 protected boundary or
moving the canonical handoff branch onto research executable source. 139-B1 implementation and the guarded B2 continuation are recorded below.

## Zero-effect accounting

```text
PRODUCTION_SQLITE_READS=0
PRODUCTION_SQLITE_WRITES=0
CREDENTIAL_READS=0
PROVIDER_CALLS=0
ROBINHOOD_READS=0
BROKER_CALLS=0
SCHEDULER_CALLS=0
ACL_MUTATIONS=0
PAPER_MUTATIONS=0
REAL_RESEARCH_EXECUTIONS=0
REAL_WALK_FORWARD_EXECUTIONS=0
SHADOW_LIVE_OBSERVATIONS=0
STRATEGY_PROMOTIONS=0
PRODUCTION_CONTRACTS_CREATED=0
D1_OPERATIONS=0
D1R5_OPERATIONS=0
D2_SUPERVISOR_EXECUTIONS=0
```

Synthetic fixtures/in-memory validation grant no operational authority. No
SHADOW stage, live observation, production compatibility/conversion, promotion,
D1/D2 or live-money capability is added. Real-money placement remains **NO-GO**.

## 139-B1 / 139-B2 guarded validation contract

The [architecture contract](../architecture/139-research-candidate-shadow.md)
freezes both pure in-memory stages before B1 implementation. Actual observation
acquisition is excluded. B1 is implemented, pending ChatGPT source acceptance.
Its inventory is ACTIVE 64 / FULL 178 / ROBINHOOD 98 / LEGACY 215 /
EXHAUSTIVE 393 / GUI 44. B2 must add exactly one FULL/EXHAUSTIVE test.

Focused B1 domain verification: 673 cases passed, including 125 new B1 cases
and 548 accepted predecessor cases. Coverage includes all semantic identities,
nine mandatory zero counters, exact types/bounds, canonical timestamps/JSON,
ordering/duplicates, complete external-chain builder/verifier, immutability and
no acquisition/execution/private-import capability. Existing synthetic fixture
factories produce only in-memory completed evidence; no real research executes.

Affected inventory/authority tests additionally cover all seven successor paths,
missing/extra/source/wrong successor blobs, every frozen predecessor dictionary,
and D1Q/D1R3/D1R4/D1R4R/D1R5 authority. All prior 137/138/139-A domain/test
blobs, B1 package exports, predecessor dictionary values, executable/native/AST
pins, ACTIVE definition, workflow bytes and bounded status/handoff stay frozen.

Use fresh purpose/GUID basetemp under F:\AI\temp\pytest, -B,
-p no:cacheprovider, -q --tb=short. Cheap static/Ruff/diff checks precede pytest;
both Ruff phases and final checks are mandatory. No local broad profile runs.

Publish B1 as one exact-file normal commit/ordinary push, then dispatch exactly
one fresh Checkpoint Source Gates run. Require exact HEAD/tree, attempt 1,
source-static and four broad shards SUCCESS, each under 300 seconds, and
terminal source-gates SUCCESS. Active/certification tests skip as expected for
an unmapped research dispatch. No second dispatch or blind retry.

Re-prove exact remote parent/tree/diff/blobs, predecessor digests, inventory,
CI and clean worktree/index; review B1 against the frozen contract. Only an
unqualified `139_B1_CONTINUATION_GATE=PASS` permits B2 immediately within this
task. It is internal continuation, not canonical ChatGPT acceptance. Any concern
stops before B2. B2 has a separate normal commit/push and one fresh terminal CI
gate, then STOP for ChatGPT to review both exact sources and close bounded docs.
Neither stage may update PROJECT_STATUS or AI_TRADING_BOT_HANDOFF. All 17 effect
counters recorded above remain zero. No real SHADOW observation or later stage.

## 139-B1 / 139-B2 guarded validation contract

The [architecture contract](../architecture/139-research-candidate-shadow.md)
freezes both pure in-memory stages before B1 implementation. Actual observation
acquisition is excluded. B1 is implemented, pending ChatGPT source acceptance.
Its inventory is ACTIVE 64 / FULL 178 / ROBINHOOD 98 / LEGACY 215 /
EXHAUSTIVE 393 / GUI 44. B2 must add exactly one FULL/EXHAUSTIVE test.

Focused B1 domain verification: 673 cases passed, including 125 new B1 cases
and 548 accepted predecessor cases. Coverage includes all semantic identities,
nine mandatory zero counters, exact types/bounds, canonical timestamps/JSON,
ordering/duplicates, complete external-chain builder/verifier, immutability and
no acquisition/execution/private-import capability. Existing synthetic fixture
factories produce only in-memory completed evidence; no real research executes.

Affected inventory/authority tests additionally cover all seven successor paths,
missing/extra/source/wrong successor blobs, every frozen predecessor dictionary,
and D1Q/D1R3/D1R4/D1R4R/D1R5 authority. All prior 137/138/139-A domain/test
blobs, B1 package exports, predecessor dictionary values, executable/native/AST
pins, ACTIVE definition, workflow bytes and bounded status/handoff stay frozen.

Use fresh purpose/GUID basetemp under F:\AI\temp\pytest, -B,
-p no:cacheprovider, -q --tb=short. Cheap static/Ruff/diff checks precede pytest;
both Ruff phases and final checks are mandatory. No local broad profile runs.

Publish B1 as one exact-file normal commit/ordinary push, then dispatch exactly
one fresh Checkpoint Source Gates run. Require exact HEAD/tree, attempt 1,
source-static and four broad shards SUCCESS, each under 300 seconds, and
terminal source-gates SUCCESS. Active/certification tests skip as expected for
an unmapped research dispatch. No second dispatch or blind retry.

Re-prove exact remote parent/tree/diff/blobs, predecessor digests, inventory,
CI and clean worktree/index; review B1 against the frozen contract. Only an
unqualified `139_B1_CONTINUATION_GATE=PASS` permits B2 immediately within this
task. It is internal continuation, not canonical ChatGPT acceptance. Any concern
stops before B2. B2 has a separate normal commit/push and one fresh terminal CI
gate, then STOP for ChatGPT to review both exact sources and close bounded docs.
Neither stage may update PROJECT_STATUS or AI_TRADING_BOT_HANDOFF. All 17 effect
counters recorded above remain zero. No real SHADOW observation or later stage.

### B1 focused result

Final distinct focused coverage is 1,981 passing cases: 673 domain and 1,308
inventory/authority cases. The first authority run exposed 13 diagnostic
regressions from over-freezing runtime dictionaries; narrowing the runtime
guard to the four masked inventory overlays retained all 32 frozen-dictionary
tests and restored original diagnostic behavior. The affected three-module
rerun passed 323 cases in 26.15 seconds. Failed evidence is preserved; no broad
certification or CI retry occurred. Both Ruff phases pass on all ten touched
Python paths; diff check, all five authority boundaries and predecessor/blob/
workflow/ACTIVE checks pass. Exact source acceptance remains pending.
