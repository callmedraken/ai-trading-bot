# Architecture 142 / RCL-5 — Strategy-native research evaluation plan

Status: **142-A SOURCE ACCEPTED; 142-B IMPLEMENTATION PENDING**.

## 142-A source acceptance

Architecture 142-A / RCL-5 is SOURCE ACCEPTED on the isolated safe-side branch:

```text
branch  feature/research-strategy-native-evaluation-current
base    d9960c7480b2eebc2c6e4530b2bafaec47292036
HEAD    9ce66811aa37a47ee4f5d769cea1ff4c33b8dcae
TREE    447656468e1214b27028aff8516f80146d1cc398
```

Accepted lineage is
`d9960c7 -> 262adc5 -> 5027aff -> 9ce6681`.

The initial implementation commit
`262adc52b5c17644a05c1d4872f6d1454fa2917e` introduced the strategy-native
definition, evaluation policy, deterministic offline backtest evidence, exact
in-memory completed-result carrier, external replay verification, focused tests
and additive package exports. Checkpoint Source Gates #619 /
`39074231322` preserved its red result: static source authority rejected the
new `tests/scripts/certification_runner/test_profiles.py` blob because the
current successor overlay had not yet admitted it.

Corrective C1 `5027aff238c865041e1bb98274fc4aeadcc19395` added only the
mechanically required Architecture-142 current-inventory pin overlay and
successor composition. #620 / `39074576264` then passed static admission; its
FULL shards exposed only stale current FULL/EXHAUSTIVE inventory assertions and
one retained predecessor test that had not yet composed the new overlay.

Corrective C2 `9ce66811aa37a47ee4f5d769cea1ff4c33b8dcae` changed only
`scripts/checkpoint_runner.py` and the current inventory/pin tests required by
that mechanically exposed successor layer. Final Checkpoint Source Gates #621 /
`39075494778`, workflow_dispatch attempt 1, is terminal SUCCESS on exact final
HEAD/tree. Static diff/Ruff/format admission passed. All four FULL shards passed
with `PYTEST=0` in 75.282 / 98.325 / 90.395 / 85.452 seconds, all below the
300-second hygiene ceiling, and source-gates passed.

Final implementation blobs include:

```text
research_strategy_definition.py  f018076cc9adc17a06d3b335c7f297ecba6f2c38
research_strategy_backtest.py    44cdc57901b5b63b611ff8ad1a53b95f22b7837f
test_research_strategy_definition.py 5418ecb926bc73b1b91a8a9fad7c5a0d4debd0cf
test_research_strategy_backtest.py   d3a4e54edc182c95c2f54bd91ed665099bb7d440
checkpoint_runner.py              93d62b15519948b822181b161ebc30956e755ecc
```

The workflow blob remains exactly
`fe6aceac62721338eba4fcb40e2e7fde0d976e18`.

Accepted behavior:

- fixed production family/version are carried by construction;
- exact `Symbol` and exact `MovingAverageCrossoverConfig` are immutable
  definition semantics;
- every behavior-affecting BacktestConfig/RiskLimits value is bound explicitly;
- only caller-supplied exact RAW daily single-symbol `HistoricalDataResult`
  is accepted;
- no symbol or strategy mapping is inferred;
- run IDs, historical fingerprints, complete-result fingerprints and evidence
  IDs are deterministic UUID5 values over canonical semantic material;
- the supplied-data adapter is in-memory only and rejects any request other than
  the exact bound request;
- the unchanged `BacktestEngine`, `MovingAverageCrossoverStrategy`,
  `NYSEMarketCalendar` and `PerformanceAnalyzer` perform the offline
  computation;
- the result fingerprint covers the complete behaviorally material
  `BacktestResult` audit, including the complete `TradingSession` semantic
  model (currently exact session date);
- external verification reruns the engine/analyzer and requires exact result,
  report and evidence reconciliation;
- parser methods prove canonical self-consistency only.

Architecture 139 and Architecture 141 remain immutable; 141 remains
`NOT_ESTABLISHED`. 142-A creates no `ProductionStrategyContract`, positive
compatibility, PAPER_CANDIDATE, promotion, provider acquisition, credential
access, production/paper runtime mutation, broker effect, scheduler effect,
D1/D2 or live authority.

Final inventory is FULL 184 / ROBINHOOD 101 / LEGACY 222 / EXHAUSTIVE 406.
Required frozen baselines remain FULL 122 / ROBINHOOD 49. Architecture 142-A is
research-only and is not an ACTIVE production checkpoint.

The feature source is not merged by this acceptance closeout.

The next safe-side source checkpoint is **Architecture 142-B** on the same
isolated strategy-native research lineage. 142-B may consume accepted 142-A
definition/policy/backtest evidence to add strategy-native walk-forward evidence
and qualification only. It still cannot create positive compatibility,
ProductionStrategyContract, PAPER_CANDIDATE, promotion or any operational
authority.

## 142-B implementation boundary

142-B must be implemented only after this accepted 142-A source and must use the
same isolated branch/worktree unless exact clean-state admission requires a new
worktree.

Expected new module:

`src/trading_bot/experiments/research_strategy_walk_forward.py`

Expected focused test:

`tests/experiments/test_research_strategy_walk_forward.py`

Frozen 142-B schemas/namespaces remain those in the Architecture-142 document.
The implementation must own the strategy-native fold model rather than reuse
`HistoricalExperimentWalkForwardFold`.

Required behavior:

1. accept one exact 142-A definition and one exact 142-A evaluation policy;
2. accept one caller-supplied exact immutable single-symbol historical result;
3. define ordered non-overlapping strategy-native folds with contiguous
   train/test boundaries;
4. deterministically slice exact train/test historical results without
   acquisition or filesystem access;
5. derive TRAINING/TEST run IDs using exact fold ID plus role;
6. call the accepted 142-A offline runner independently for every fold side;
7. retain exact per-fold training/test backtest evidence IDs and fingerprints;
8. independently verify every fold by replay before qualification;
9. apply only the frozen explicit walk-forward threshold policy;
10. derive PASS/FAIL and ordered failure reasons;
11. malformed provenance/reconciliation must raise, never become FAILED;
12. emit the separate passed artifact only for exact PASS.

142-B must preserve the same definition/config/policy across every fold. There
is no variant ranking, winner selection, metadata mapping or strategy mutation.

Required focused coverage includes fold identity/canonical transport, chronology,
overlap/gap rejection as frozen, deterministic slicing, TRAINING/TEST run-ID
separation, independent fold state, no look-ahead, same definition/policy across
all folds, equal-test-window policy, median/return/drawdown qualification,
ordered failure reasons, malformed-evidence fail-closed behavior, parser
self-consistency only, external full replay verification, caller-input
immutability, AST/capability restrictions, Architecture-139/141 immutability,
zero effects and successor-overlay/inventory fail-closed behavior.

Publication follows the canonical single-attempt plus bounded mechanical C1/C2
continuation rule. Do not begin Architecture 143 in the 142-B checkpoint.

## Goal

Implement 142-A from
[142-research-strategy-native-evaluation.md](../architecture/142-research-strategy-native-evaluation.md).

The checkpoint creates a new strategy-native research definition and deterministic
offline backtest evidence for the exact production MovingAverageCrossover
semantics. It does not retrofit Architecture 139/141 and does not create
positive compatibility or a paper candidate.

## Frozen 142-A artifacts

Implement:

- `research-strategy-definition/v1`;
- `research-strategy-evaluation-policy/v1`;
- `research-strategy-backtest-evidence/v1`.

Frozen UUID5 namespaces:

```text
definition  0b64cd96-bc4a-569e-aaa6-8cee8a0c037d
policy      26c58998-5378-5140-928c-fa3db4488b77
backtest    b7e51d04-4d94-5b1c-b04d-6381c99dce27
```

Use exact `Symbol`, exact `MovingAverageCrossoverConfig`, exact
`RiskLimits`, exact caller-supplied `HistoricalDataResult`, existing
`BacktestEngine`, `NYSEMarketCalendar` and `PerformanceAnalyzer`.

Do not use the portfolio experiment or walk-forward runners.

## Expected paths

New:

- `src/trading_bot/experiments/research_strategy_definition.py`;
- `src/trading_bot/experiments/research_strategy_backtest.py`;
- `tests/experiments/test_research_strategy_definition.py`;
- `tests/experiments/test_research_strategy_backtest.py`.

Additive/mechanical only if required:

- `src/trading_bot/experiments/__init__.py`;
- single-symbol historical canonical material helper/export/test;
- `scripts/run_test_certification.py`;
- `scripts/checkpoint_runner.py`;
- current inventory/pin assertions;
- this validation record.

Do not modify production strategy/backtest behavior, 139/141 behavior, D1R9,
workflow YAML, runtime/provider/broker source or GUI.

## Required verification

Focused tests must prove the complete 142-A architecture contract, especially:

- fixed family/version/source/config/symbol identity;
- full policy binding with no defaults;
- exact historical symbol/request/fingerprint;
- no multi-symbol inference;
- deterministic run/result fingerprints;
- exact equivalence with direct BacktestEngine execution;
- no look-ahead/next-open regression;
- complete external rerun verification;
- canonical parser self-consistency only;
- no ProductionStrategyContract, paper-candidate or production authority;
- no historical portfolio runner reuse;
- zero external/provider/credential/runtime/broker/scheduler/D1/D2 effects;
- immutable separation from Architecture 139/141;
- successor-overlay and inventory fail-closed behavior.

Run focused tests first, then affected pure backtest/strategy/market-data tests,
retained Architecture-139/141 separation tests, affected authority tests, Ruff
check/format and diff checks.

GitHub CI owns broad FULL/ROBINHOOD when mapped.

## Corrective-CI rule

The initial source publication is one atomic commit/push and one planned CI
admission. A red run ends that attempt but not automatically the delegated
Codex task. If the failure is fully classified and purely mechanical, preserve
it, declare C1 (and at most one further bounded C2 if necessary), locally verify
the corrective scope, make one atomic corrective commit/push and poll to
terminal. Hand back on green or on any semantic/authority/protected-effect/
remote-state ambiguity.

## Final report

Return exact:

- base/final HEAD/TREE/direct parent;
- branch/worktree;
- changed paths/blobs;
- schema/namespaces;
- focused/retained/authority test counts;
- final inventories;
- predecessor/overlay preservation;
- workflow-byte preservation;
- zero-effect accounting;
- all CI attempts including preserved failures/corrections;
- terminal green run/job/shard details;
- clean worktree/index.

Then stop for ChatGPT source acceptance. Do not begin 142-B in the same source
checkpoint.
