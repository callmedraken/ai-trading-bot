# Architecture 139 / RCL-3 — exact binding and future SHADOW validation

Status: **139-A SOURCE ACCEPTED** at HEAD `e730b3b05c0c78181a4b3ff6b8e257cb04f3ff15` / TREE `ea13572c565bcfe65959014bf1c98572c89cc3a7`; Checkpoint Source Gates #517 / 38387248166 SUCCESS. 139-B deferred while returning to the main production lane.
Architecture is split into 139-A exact variant binding and 139-B no-effect
observation + SHADOW qualification. This plan currently validates only 139-A.

## Acceptance evidence

Exact accepted executable/test source is HEAD
`e730b3b05c0c78181a4b3ff6b8e257cb04f3ff15`, TREE
`ea13572c565bcfe65959014bf1c98572c89cc3a7`, one commit after exact base
`1af8150c9985f5dc7ad1e143a16d90dcdc86be1a` /
`f0adb7a370c5ab1d41c4a6d62e2b9db012096952`.

Checkpoint Source Gates #517 / 38387248166 is terminal SUCCESS on that exact
source. source-static passed all 62 authorities with 83 test paths and 356 Ruff
paths. Broad shards passed 2,174 / 2,050 / 1,880 / 2,350 cases plus one optional
SDK skip: 8,454 passed, 1 skipped, 0 failed/errors. Hygiene timings were
96.994 / 47.760 / 72.335 / 95.456 seconds. Focused implementation evidence
records 966 distinct passing cases. Exactly three retained Architecture-134
test-file pins changed and match the committed Git blobs.

The lossy-Decimal historical-identity case is intentionally fail-closed. No
SHADOW stage, live observation, production compatibility, production contract,
promotion, D1/D1R2 or D2 authority is created. 139-B is deferred while work
returns to the protected production lane.

## Source admission

Exact base HEAD `1af8150c9985f5dc7ad1e143a16d90dcdc86be1a` / TREE
`f0adb7a370c5ab1d41c4a6d62e2b9db012096952` was verified against origin before
creating `feature/research-candidate-shadow-variant-binding` in
`F:\AI\worktrees\ai-trading-bot-research-candidate-shadow-variant-binding`.
Initial worktree/index were clean. Architecture-138 accepted executable/test
source remains `e0735af265894757ff9b90ab185bcbd77ee2dee9` /
`a29f51faaa81e866d0825ffbe082c5fcddb94584`, CI #516 / 38380502369 SUCCESS.
No D1/D1R1/D1R2 worktree or `F:\AITradingBot\Arch134D1` is inspected or changed.

## Focused coverage and verification

The new focused binding module covers explicit original rank 1/2/null,
repeatability, immutable exact resolver return, ordered UTF-8 UUID5 framing and
every semantic field, strict JSON representation/types/identity, full external
chain/type/source failures, FAILED qualification rejection, report/result/request/
fingerprint/run/rolling/metrics/name/ordinal disagreement, missing/duplicate
variants, retained-object drift, normalization drift and unchanged caller evidence
on failure. A different valid result using the same variant UUID is rejected.
Monkeypatch guards prove no runner or simulator use during binding operations.
AST tests freeze import/model allowlists and no promotion/execution/effect APIs.
Prior candidate/policy/qualification/successor canonical byte hashes are golden,
and prior parsers still reject SHADOW and later reserved stages.

Use the development interpreter with `-B -p no:cacheprovider` and a separate fresh
external `--basetemp=F:\AI\temp\pytest\arch139a-<unique>` for every invocation:

```text
tests/experiments/test_research_candidate_shadow_binding.py
tests/experiments/test_research_candidate_walk_forward.py
tests/experiments/test_research_candidate.py
tests/experiments/test_report.py
tests/experiments/test_historical.py
tests/experiments/test_walk_forward.py
tests/experiments/test_walk_forward_analytics.py
```

Also run `tests/scripts/certification_runner/test_profiles.py`, the seven exact
current inventory assertions in strategy/cycle/supervised tests, and the exact
R1/R2 source-only authority cases whose retained test blobs change. Run focused
Ruff check and format check on every changed Python file, both phases before
stopping and non-mutating diff diagnostics on failures, then `git diff --check`.
The registered repository CI owns the broad source-gate checks; do not substitute
local FULL/ROBINHOOD/LEGACY/EXHAUSTIVE certification.

Focused research-chain regression passed **542 cases in 35.51 s**, including
216 binding cases plus unchanged 137/138, report, historical and directly relevant
walk-forward/aggregate modules. After final defensive-copy/Decimal checks, the
final binding module passed **222 cases in 30.10 s**. Across these overlapping
runs, 548 distinct research cases and 418 distinct authority/profile cases
passed: **966 distinct cases** total. Profile/inventory and exact R1/R2 source-only authority verification
passed **418 cases in 6.39 s**. Three targeted copy/context checks additionally
passed in 3.37 s before the final binding run. No local broad certification ran. Final focused Ruff check PASS, Ruff format
check PASS (11 changed Python files), and git diff check PASS. Initial development
found standard deepcopy cannot copy retained immutable mapping proxies; the
bounded copy fix retains original alias topology and tests pass without mutating
caller evidence. This changes no historical artifact model or serializer. Additional low-precision
validation exposed inherited context-sensitive Decimal.normalize calls. Historical
boundary revalidation now uses a fresh precision context sufficient for every
retained coefficient, preserving exact canonical identities independently of
ambient precision/traps. A precise variant change that aliases under legacy
precision-28 normalization must fail closed, rather than weakening the full
configuration commitment. This conservatively rejects evidence whose original
historical identity depended on lossy Decimal normalization.

## Canonical inventory and retained pins

Discovery through `scripts.run_test_certification.discover_inventory` and
`select_inventory` yields ACTIVE 62 / FULL 172 / ROBINHOOD 94 / LEGACY 215 /
EXHAUSTIVE 387 / GUI 44. Only FULL/EXHAUSTIVE increase by one. No supported
ownership, baseline, ACTIVE checkpoint or workflow route changes.

Only `ARCH134_PRODUCTION_PAPER_RUNTIME_SOURCE_PINS` entries for
`tests/scripts/certification_runner/test_profiles.py`,
`tests/strategies/test_production_strategy_contract.py`, and
`tests/strategies/test_production_strategy_decision.py` are repinned to their
LF-normalized Git blobs. Production executable/native/AST, historical recovery
and ACTIVE tuple/digest remain unchanged.

## Publication and required CI evidence

One ordinary exact-file commit, subject
`feat: bind research candidates to exact shadow variants`, and one ordinary
push; no amend/rebase/force/merge or PR mutation. Branch remains outside the
production push allowlist. Dispatch exactly one fresh Checkpoint Source Gates
run on the exact resulting branch/HEAD and wait for terminal evidence:
source-static and all 62 authorities PASS; four broad shards PASS below 300 s;
active-tests/certification-tests SKIPPED; terminal source-gates PASS.
Record run/jobs, test/path counts and hygiene timings in the handoff. Exact
GitHub review and acceptance belong to ChatGPT, followed by 139-B design.

## Operational effect accounting

Pure synthetic in-memory fixture generation/validation is not an operational
research execution. All implementation effects remain:

```text
PRODUCTION_SQLITE_READS=0
PRODUCTION_SQLITE_WRITES=0
CREDENTIAL_READS=0
PROVIDER_CALLS=0
ALPACA_HTTP_CALLS=0
ROBINHOOD_APPLICATION_CALLS=0
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
D1R2_RECOVERY_OPERATIONS=0
D2_SUPERVISOR_EXECUTIONS=0
```

A green 139-A grants no SHADOW, live observation, production compatibility,
production contract, promotion or D1/D2 authority. 139-B separately owns minimum
observation/session policy, evidence provenance, failures, no-effect enforcement,
SHADOW qualification and any later immutable SHADOW successor. No execution or
live/provider data is authorized here. Real-money broker placement remains NO-GO.
