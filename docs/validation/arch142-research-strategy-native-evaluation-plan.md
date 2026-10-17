# Architecture 142 / RCL-5 — Strategy-native research evaluation plan

Status: **DESIGN FROZEN; 142-A IMPLEMENTATION PENDING**.

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
