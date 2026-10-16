# GUI-A16 — Read-only Research Candidate Lifecycle validation

Architecture 140 freezes the normative contract before source implementation.
Status: **SOURCE ACCEPTED** after terminal publication gates and independent
ChatGPT GitHub review of exact source `6d092b8e05372d241dc4183b7b392f0eb83b4500` / tree
`fd17ccfd338266c04d24dd03e303ee36dd72b0ca`.

## Required local gates

Use existing `F:\AI\ai-trading-bot\.venv\Scripts\python.exe`, real PySide6,
`QT_QPA_PLATFORM=offscreen`, `-B -p no:cacheprovider -q --tb=short`, and a fresh
external basetemp under `F:\AI\temp\pytest\` for each pytest invocation.

1. Five focused A16 modules: models, service, page Qt, composition, startup.
2. Affected existing MainWindow, A8 startup, A9 System, A10 timeline, A11 explorer,
   A12/A13 navigation and all A15 tests.
3. Complete tests/gui once with real PySide6.
4. Seven affected inventory/authority modules plus directly relevant source
   authority regressions; D1Q/D1R3/D1R4/D1R4R/D1R5 PASS.
5. Both non-mutating Ruff check/format checks on all touched Python paths;
   capture both exits and emit non-mutating --diff for each failed phase before
   deciding failure. `git diff --check` PASS.

No local FULL/ROBINHOOD/LEGACY/EXHAUSTIVE profile. Preserve failed evidence and
rerun only affected tests after bounded corrections.

## Coverage obligations

Exact enums/types, frozen/slotted models, complete AVAILABLE evidence, empty
UNAVAILABLE/ATTENTION, exact UUID/source/int/rank/bounded text, fixed governance.
All 30 partial sets reject before Qt; no default/discovery, all five explicit
CLI flags consumed; no selection means no instance/opens. Validate local path
syntax, strict UTF-8, 8 MiB+1 bounded reads, exact canonical parser text, all five
parsers and public successor verifier calls, cached success/failure, at-most-once
opens. Fail closed for malformed/noncanonical/duplicate/forged/stage/lineage/mixed
chain artifacts, wrong binding/batch/qualification/predecessor and oversized data.
No raw paths, JSON, exceptions or domain artifacts retained in view.

Prove local self-consistency/linkage scope visibly and explicitly excludes full
historical external qualification, source acceptance, promotion eligibility,
production compatibility and trading readiness. Exact B1 ranges/counts/nine
zeros, B2 policy/counts/PASSED/empty ordered reasons, non-authoritative rank.
Qt uses real PySide6, selectable identities/hashes, both requested resolutions,
vertical scrolling/no horizontal overflow/no action buttons, all three states.
Nine exact ordered MainWindow acquisitions, stable page order, zero navigation
service/file reads, pure Supervisor/System/Evidence, A11/A12/A13 lifecycle routes,
existing pages intact. AST capability gate covers imports/calls/discovery/I/O.

Recompute actual module inventories. Freeze all predecessor dictionary digests,
including 139-B2 overlay, and test missing/extra/executable/wrong-blob/drift
rejection through the existing authority chain. Preserve domain/parser/workflow
bytes and production executable/native/AST authority.

## Publication and stop

Exactly one normal implementation commit/push after local PASS. Existing
feature/gui-* push pattern must produce one real GUI Source Gates run: exact
HEAD, attempt 1, real PySide6, full tests/gui/Ruff/format/diff terminal SUCCESS.
Only then dispatch exactly one Checkpoint Source Gates on the exact branch/HEAD.
Require source-static, four broad shards each under 300 s, terminal source-gates,
attempt 1/SUCCESS/no retry; keep existing unmapped branch route. Any CI failure
stops and preserves evidence. No workflow byte edits or manual GUI dispatch.

Post-CI refetch/review exact parent/tree/changed paths/new GUI blobs/seven 140
successor blobs/B2 hash/all frozen dictionaries/inventories/CI/clean worktree and
index. Return exact evidence and zero-effect accounting. Canonical ChatGPT
SOURCE ACCEPTED is not claimed. PROJECT_STATUS and AI_TRADING_BOT_HANDOFF remain
unchanged for post-acceptance closeout. Stop before integration, acquisition,
post-SHADOW stages, promotion or Architecture 141.

## Local verification evidence

Existing interpreter: Python 3.14, real PySide6 6.10.3, offscreen. Complete GUI
suite: **880 passed, 0 skipped** in 17.97 s, including **349 A16 cases** and
531 retained GUI cases. Eleven directly affected inventory/authority modules:
**1,358 passed** in 63.11 s. These sets are disjoint: **2,238 distinct cases**.
The initial A16 run passed 324 and exposed a too-broad Qt signal static check;
the affected existing run passed 145 and exposed the report-only service's
missing ninth getter. Both were corrected before the full GUI run. Later static
hardening distinguished QApplication.exec from Python exec; its focused rerun
passed. Final Ruff check/format and diff checks are required before staging.
No broad certification profile was run.

Canonical inventory: ACTIVE 64 / FULL 179 / ROBINHOOD 98 / LEGACY 220 /
EXHAUSTIVE 399 / GUI 49. D1Q, D1R3, D1R4, D1R4R and D1R5 source authority
checks independently PASS. All 34 predecessor dictionaries, B2 overlay, accepted
domain source and both workflow blobs remain frozen. Only the seven current
inventory test blobs gain the additive Architecture-140 successor authority.

| Current inventory test | Architecture-140 successor blob |
| --- | --- |
| tests/scripts/certification_runner/test_profiles.py | cfa0ad5b217b6493c6eab748efeff09b17e6a7d3 |
| tests/strategies/test_production_strategy_contract.py | 4e694f9e8ac110b422f1ae2b1eafc401ce6bbf7f |
| tests/strategies/test_production_strategy_decision.py | 57d1053f46b4a86a80cdc8d575dc6ec8e8d9ddb1 |
| tests/review_paper/test_production_strategy_cycle.py | bf9afe45f42a8d8cd6334ff295f7a76ca07697d3 |
| tests/review_paper/test_supervised_deployment_qualification.py | c98d6252257ace3d8b876dc0c36fab474e089e92 |
| tests/review_paper/test_supervised_runtime_host_admission.py | 544e0b9ac6d0276467872ce2ae0481504cd31a79 |
| tests/review_paper/test_supervised_maintenance_rebind.py | 36e9c0802f19cec5fe0ed771be5a599fa584e84c |

All eighteen requested operational/production effect counters are zero,
including real production evidence reads during tests. A16 fixtures consist only
of explicit synthetic temporary canonical files; retained GUI/authority tests
use their accepted synthetic/fake boundaries. No real observation, provider,
credential, broker, paper, production store, scheduler/ACL, research/walk-forward,
promotion, production contract, D1/D1R5/D2 operation occurred. Filesystem and
latest-artifact discovery remain false. The GUI verifies local canonical parser
self-consistency and exact SHADOW successor linkage only; full external-chain
qualification remains false.


## Terminal publication and acceptance evidence

Exact accepted source:

```text
HEAD  6d092b8e05372d241dc4183b7b392f0eb83b4500
TREE  fd17ccfd338266c04d24dd03e303ee36dd72b0ca
parent 5889f83ea5a4baefc154283266d645a555ed2d5c
```

GUI Source Gates #8 / `38684121623` was the single automatic push run, attempt 1,
terminal SUCCESS on the exact HEAD. Windows CI installed PySide6 6.10.3 and ran
**880 passed** with Ruff check, Ruff format and diff checks PASS.

Checkpoint Source Gates #565 / `38684312270` was the single subsequent
workflow_dispatch, attempt 1, terminal SUCCESS on the same HEAD. Source-static
reported CHECKPOINTS=64 / TEST_PATHS=88 / RUFF_PATHS=372,
GIT_DIFF_CHECK=0 / RUFF_CHECK=0 / RUFF_FORMAT=0 / PYTEST=SKIP and all current
authorities PASS. Broad shards passed with PYTEST=0 and wall times:

- shard 0: 99.178 s
- shard 1: 94.690 s
- shard 2: 85.018 s
- shard 3: 109.033 s

All remain below 300 seconds. Active and certification jobs skipped as expected
for the unmapped GUI dispatch; terminal source-gates passed. No retry occurred.

Independent GitHub review confirmed all 42 changed paths, the exact new GUI and
test blobs, the seven Architecture-140 successor blobs, five resolver sites,
34 frozen predecessor dictionaries, frozen 139-B2 overlay digest, final inventory
ACTIVE 64 / FULL 179 / ROBINHOOD 98 / LEGACY 220 / EXHAUSTIVE 399 / GUI 49,
unchanged 137–139 domain bytes, unchanged workflow bytes, and unchanged
product/history refs. The visible verification-scope statement is accurate:
canonical local artifacts and SHADOW successor linkage are verified; full
historical external-chain qualification is not re-run by this GUI.

All eighteen requested A16 effect counters remain zero, including real production
evidence reads during tests. Only explicit synthetic temporary artifacts were
read by A16 tests. No protected effect, product/history integration, acquisition,
promotion, production conversion, post-SHADOW materialization or Architecture 141
work is part of this acceptance.
