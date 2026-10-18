# Architecture 142 / RCL-5 — Strategy-native research evaluation plan

Status: **142-A AND 142-B / RCL-5 SOURCE ACCEPTED; ARCHITECTURE 142 COMPLETE**.

## 142-B / RCL-5 source acceptance closeout

Architecture 142-A and 142-B / RCL-5 are SOURCE ACCEPTED. Architecture 142 is
complete as a research-only milestone; the feature source remains intentionally
unmerged.

```text
branch                 feature/research-strategy-native-evaluation-current
142-B initial HEAD     e77bccdafc065148c56fee17095a7cfee0e1711b
142-B initial TREE     bb02fd6e8c3b4d0c1bb5eca252a2fef1dff5ba69
142-B initial PARENT   9ce66811aa37a47ee4f5d769cea1ff4c33b8dcae
initial CI             #623 / 39095309178 SUCCESS

142-B-C1 final HEAD    e88f38f8deeb834ac3f162b6a82e328dc4708ad0
142-B-C1 final TREE    23f63ed62e67460edce5b9296893bdcfe49a25f7
142-B-C1 PARENT       e77bccdafc065148c56fee17095a7cfee0e1711b
final CI               #624 / 39096130260 SUCCESS
```

The accepted lineage is `9ce6681 -> e77bccd -> e88f38f`. Initial #623 SUCCESS
is preserved. ChatGPT review found the initial 142-B PASS external-verification
defect; C1 `e88f38f` corrected it. The #624 workflow_dispatch attempt 1 is
terminal SUCCESS, with shard timings `90.117 / 99.976 / 88.859 / 80.482`
seconds and JUnit `9,120 total / 9,119 passed / 1 skipped / 0 failed / 0
errors`.

Final source and focused-test identities are:

```text
research_strategy_walk_forward.py       6f8e69d023811f7763c67286cce0d44fab59a2c2
test_research_strategy_walk_forward.py  ce20cc57ddc89591606b5d1de6e541f4228011bd
workflow                                fe6aceac62721338eba4fcb40e2e7fde0d976e18
142-A overlay                           515392eb1213323ab2bc0a62a4bd848a21b9fe60b6afcdaeac14b44523c43366
142-B overlay                           8a7ddd8184e1beadecdce88207ed75b02dce75be870892957b9ae5ae5d7e33c6
```

The accepted certification inventories are FULL 185 / ROBINHOOD 101 / LEGACY
222 / EXHAUSTIVE 407. Parsing remains self-consistency-only. External PASS
verification now replays the full walk-forward/qualification chain.

No `ProductionStrategyContract`, positive compatibility,
`PAPER_CANDIDATE`, promotion or operational authority is created. All
production/provider/credential/broker/scheduler/paper/D1/D1R9/D2 effects are
zero:

```text
PRODUCTION_SQLITE_READS=0        PRODUCTION_SQLITE_WRITES=0
CREDENTIAL_READS=0               PROVIDER_CALLS=0
ROBINHOOD_READS=0                BROKER_CALLS=0
SCHEDULER_CALLS=0                ACL_MUTATIONS=0
PAPER_MUTATIONS=0                STRATEGY_PROMOTIONS=0
PRODUCTION_CONTRACTS_CREATED=0   PAPER_CANDIDATES_CREATED=0
D1_OPERATIONS=0                  D1R9_OPERATIONS=0
D2_SUPERVISOR_EXECUTIONS=0
```

The next safe-side milestone is **Architecture 143 / RCL-6**: a separate pure
compatibility-proof design/source checkpoint consuming the accepted
strategy-native definition plus verified 142-B walk-forward/PASS evidence and
comparing exact production family/version/symbol/config/source semantics.
Architecture 143 must not create `ProductionStrategyContract`,
`PAPER_CANDIDATE`, promotion, provider/runtime/broker/scheduler authority, or
any operational effect.

## 142-A predecessor source acceptance

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

The predecessor 142-A source remains accepted and immutable. Its successor
142-B is now accepted in the closeout above; no feature source was merged by
this documentation update.

## 142-B completion and evidence boundary

142-B was implemented only after the accepted 142-A source on the isolated
branch/worktree. The required behavior below is the frozen 142-B contract and
is now satisfied by the accepted final source recorded above.

Accepted final module:

`src/trading_bot/experiments/research_strategy_walk_forward.py`

Accepted focused test:

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

Publication followed the canonical single-attempt plus bounded mechanical C1/C2
continuation rule. Architecture 143 was not begun in the 142-B checkpoint.

## Completed 142-A and 142-B goal

The 142-A objective was implemented from
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

The final 142-B source was then reviewed and accepted as recorded above. The
next safe-side milestone is Architecture 143 / RCL-6; it is not implemented by
this closeout.
