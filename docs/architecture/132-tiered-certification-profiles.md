# Architecture 132 — Tiered certification profiles

## Revision 132-R1: supported product versus legacy compatibility

Architecture 132-R1 revises this architecture rather than introducing
Architecture 133. It explicitly changes the meaning of FULL while preserving
the accepted Robinhood contract:

- FULL = all CURRENTLY SUPPORTED functionality.
- LEGACY = retained retired architecture.
- EXHAUSTIVE = every test still present in the repository, preserving the
  original Architecture 132 all-repository FULL behavior.
- ROBINHOOD = the accepted Architecture 131 product and direct shared-core
  subset of FULL.

The CLI accepts `--profile full`, `--profile robinhood`, `--profile legacy`,
and `--profile exhaustive`. The default remains FULL, including when the option
is omitted. Existing callers wanting the original all-repository scope must
now explicitly use `--profile exhaustive`; default invocations intentionally
adopt current-supported scope. Unknown profiles are rejected.

At startup HEAD `2577225dafcff2d616fcbf018d7045aebaab1ff5`, tree
`e0af9fb359872c77ab08248e9a101a281a357fa9`:

| Profile | Modules | Exact lanes |
| --- | ---: | --- |
| full | 113 | broad-1, broad-2 |
| robinhood | 40 | robinhood-1, robinhood-2 |
| legacy | 204 | legacy-1, legacy-2, serial |
| exhaustive | 317 | broad-1, broad-2, serial |

Counts describe this tree, not hard limits on future admitted additions.
The FULL 113-module and Robinhood 40-module required baselines below remain
frozen so deletion/renaming cannot silently reduce certification.

## Tier policy and handoff

```text
FOCUSED
-> SOURCE-GATE CI
-> ROBINHOOD when appropriate
-> FULL at coherent current-product boundaries
-> LEGACY/EXHAUSTIVE only when explicitly relevant
-> PROTECTED separately authorized
```

| Level | Trigger |
| --- | --- |
| FOCUSED | Every implementation/correction; Codex runs affected tests and focused checks. |
| SOURCE-GATE CI | Every pushed registered checkpoint; retain existing registered GitHub source-gate batching. |
| ROBINHOOD | When ChatGPT declares a coherent Architecture 131 integration boundary; before protected Robinhood qualification; after material changes to shared domain/execution/ledger/risk foundations used by Architecture 131. |
| FULL | After certification-topology changes; at coherent current-product boundaries; before major develop/release integration or consequential production/live-readiness transitions; after sufficiently broad supported shared-core changes; or when ChatGPT explicitly determines accumulated checkpoints warrant current-product regression. |
| LEGACY / EXHAUSTIVE | Only when explicitly justified by legacy architecture changes, interpreter/dependency migrations spanning both eras, broad repository restructuring, deliberate legacy removal, or backward compatibility investigation. |
| PROTECTED | Always separate fresh authorization. |

FULL is not mechanically tied to every accepted source checkpoint or
Architecture 131 letter. Normal current-product certification does not require
LEGACY or EXHAUSTIVE. ChatGPT owns exact source review, acceptance, and the
certification-tier decision. The normal handoff remains:

```text
implementation + focused checks
-> exact-file commit/push
-> ChatGPT exact GitHub code review
-> source acceptance
-> appropriate certification tier
-> docs closeout (PROJECT_STATUS + HANDOFF after certification acceptance)
```

Local patch-first review is fallback-only. This revision modifies neither
`scripts/checkpoint_runner.py` nor `.github/workflows/checkpoint-source-gates.yml`.
No actual certification profile is run during bounded implementation.

## Supported FULL ownership

Whole-directory families (including descendant test modules):

```text
tests/analytics/
tests/backtesting/
tests/domain/
tests/execution/
tests/experiments/
tests/integration/
tests/ledger/
tests/market_calendar/
tests/multi_backtesting/
tests/optimization/
tests/portfolio/
tests/portfolio_analytics/
tests/rebalancing/
tests/review_paper/
tests/risk/
tests/robinhood_mcp/
tests/simulation/
tests/strategies/
```

Reviewed exact supported tests in mixed directories and infrastructure/root:

```text
tests/cli/test_create_research_session_bundle.py
tests/cli/test_historical_experiment.py
tests/cli/test_historical_experiment_pairwise_config.py
tests/cli/test_historical_experiment_pairwise_serialization.py
tests/cli/test_historical_experiment_pareto_config.py
tests/cli/test_historical_experiment_pareto_serialization.py
tests/cli/test_historical_experiment_report_serialization.py
tests/cli/test_optimized_simulation.py
tests/cli/test_research_session_archive.py
tests/cli/test_research_session_archive_cli.py
tests/cli/test_research_session_bundle.py
tests/cli/test_research_session_manifest.py
tests/cli/test_research_session_restore.py
tests/cli/test_restore_research_session_archive.py
tests/cli/test_rolling_historical.py
tests/cli/test_verify_research_session_manifest.py
tests/cli/test_walk_forward_aggregate_config.py
tests/cli/test_walk_forward_aggregate_serialization.py
tests/cli/test_walk_forward_experiment.py
tests/cli/test_walk_forward_experiment_config.py
tests/cli/test_walk_forward_experiment_serialization.py
tests/cli/test_walk_forward_stability_config.py
tests/cli/test_walk_forward_stability_serialization.py
tests/market_data/test_csv_historical_provider.py
tests/market_data/test_historical_models.py
tests/market_data/test_multi_symbol_models.py
tests/market_data/test_multi_symbol_provider.py
tests/runtime/test_checkpoint_runner.py
tests/scripts/test_create_walk_forward_research_bundle.py
tests/scripts/test_research_session_archive_scripts.py
tests/scripts/test_run_backtest.py
tests/scripts/test_run_historical_experiment.py
tests/scripts/test_run_rolling_historical_simulation.py
tests/scripts/test_run_test_certification.py
tests/scripts/test_run_walk_forward_experiment.py
tests/test_config.py
```

Root `tests/test_robinhood_*.py` is also supported. New tests in supported
whole-directory families and matching root Robinhood tests enter FULL
automatically. The mixed research CLI, market-data, and scripts namespaces
use exact ownership; new files there require an explicit reviewed support
classification, even when their names suggest research. Unrelated root test
names are likewise unclassified.

The frozen current FULL required baseline is exactly 113 modules:

```text
tests/analytics/test_analyzer.py
tests/backtesting/test_backtest_engine.py
tests/backtesting/test_backtest_models.py
tests/cli/test_create_research_session_bundle.py
tests/cli/test_historical_experiment.py
tests/cli/test_historical_experiment_pairwise_config.py
tests/cli/test_historical_experiment_pairwise_serialization.py
tests/cli/test_historical_experiment_pareto_config.py
tests/cli/test_historical_experiment_pareto_serialization.py
tests/cli/test_historical_experiment_report_serialization.py
tests/cli/test_optimized_simulation.py
tests/cli/test_research_session_archive.py
tests/cli/test_research_session_archive_cli.py
tests/cli/test_research_session_bundle.py
tests/cli/test_research_session_manifest.py
tests/cli/test_research_session_restore.py
tests/cli/test_restore_research_session_archive.py
tests/cli/test_rolling_historical.py
tests/cli/test_verify_research_session_manifest.py
tests/cli/test_walk_forward_aggregate_config.py
tests/cli/test_walk_forward_aggregate_serialization.py
tests/cli/test_walk_forward_experiment.py
tests/cli/test_walk_forward_experiment_config.py
tests/cli/test_walk_forward_experiment_serialization.py
tests/cli/test_walk_forward_stability_config.py
tests/cli/test_walk_forward_stability_serialization.py
tests/domain/test_market.py
tests/domain/test_orders.py
tests/domain/test_positions.py
tests/domain/test_proposals.py
tests/execution/test_execution_models.py
tests/execution/test_order_engine.py
tests/execution/test_paper_fill_application.py
tests/execution/test_paper_fills.py
tests/execution/test_paper_submission.py
tests/execution/test_portfolio_orders.py
tests/experiments/test_comparison.py
tests/experiments/test_grid.py
tests/experiments/test_historical.py
tests/experiments/test_pairwise.py
tests/experiments/test_pareto.py
tests/experiments/test_report.py
tests/experiments/test_walk_forward.py
tests/experiments/test_walk_forward_analytics.py
tests/experiments/test_walk_forward_stability.py
tests/integration/test_walk_forward_e2e.py
tests/integration/test_walk_forward_research_archive_e2e.py
tests/integration/test_walk_forward_research_bundle_e2e.py
tests/integration/test_walk_forward_research_restore_e2e.py
tests/integration/test_walk_forward_research_transport_e2e.py
tests/ledger/test_checkpoint_state.py
tests/ledger/test_initialization.py
tests/ledger/test_ledger.py
tests/ledger/test_models.py
tests/market_calendar/test_calendar_models.py
tests/market_calendar/test_nyse_calendar.py
tests/market_data/test_csv_historical_provider.py
tests/market_data/test_historical_models.py
tests/market_data/test_multi_symbol_models.py
tests/market_data/test_multi_symbol_provider.py
tests/multi_backtesting/test_engine.py
tests/multi_backtesting/test_models.py
tests/multi_backtesting/test_strategy_contract.py
tests/optimization/test_cpu_mean_cvar.py
tests/portfolio/test_historical_scenarios.py
tests/portfolio/test_mean_cvar.py
tests/portfolio/test_models.py
tests/portfolio/test_optimized_targets.py
tests/portfolio/test_optimizer_protocol.py
tests/portfolio/test_scenarios.py
tests/portfolio_analytics/test_analyzer.py
tests/portfolio_analytics/test_models.py
tests/portfolio_analytics/test_optimized_simulation.py
tests/rebalancing/test_models.py
tests/rebalancing/test_planner.py
tests/rebalancing/test_proposals.py
tests/review_paper/test_forward_preview.py
tests/review_paper/test_intent_bridge.py
tests/review_paper/test_nyse_published_regular_sessions.py
tests/review_paper/test_performance.py
tests/review_paper/test_prepare_qualification.py
tests/review_paper/test_risk_context.py
tests/review_paper/test_risk_price_acquisition.py
tests/review_paper/test_risk_prices.py
tests/review_paper/test_session_admission.py
tests/review_paper/test_store.py
tests/review_paper/test_supervised_forward_paper.py
tests/risk/test_manager.py
tests/risk/test_orchestration.py
tests/risk/test_risk_models.py
tests/robinhood_mcp/test_account_resolution.py
tests/robinhood_mcp/test_adapter.py
tests/robinhood_mcp/test_sdk_transport.py
tests/robinhood_mcp/test_windows_oauth.py
tests/runtime/test_checkpoint_runner.py
tests/scripts/test_create_walk_forward_research_bundle.py
tests/scripts/test_research_session_archive_scripts.py
tests/scripts/test_run_backtest.py
tests/scripts/test_run_historical_experiment.py
tests/scripts/test_run_rolling_historical_simulation.py
tests/scripts/test_run_test_certification.py
tests/scripts/test_run_walk_forward_experiment.py
tests/simulation/test_optimized_paper_portfolio.py
tests/simulation/test_paper_portfolio.py
tests/simulation/test_rolling_historical.py
tests/strategies/test_moving_average.py
tests/test_config.py
tests/test_robinhood_forward_paper_cycle.py
tests/test_robinhood_live_qualification_verifier.py
tests/test_robinhood_paper_cycle.py
tests/test_robinhood_paper_operator.py
tests/test_robinhood_paper_pipeline.py
tests/test_robinhood_prepare_qualification_verifier.py
```

## Preserved Robinhood ownership

Robinhood ownership remains exactly the accepted direct-file patterns:

```text
tests/domain/test_*.py
tests/execution/test_*.py
tests/ledger/test_*.py
tests/risk/test_*.py
tests/review_paper/test_*.py
tests/robinhood_mcp/test_*.py
tests/test_robinhood_*.py
tests/runtime/test_checkpoint_runner.py
tests/scripts/test_run_test_certification.py
```

New matching direct-directory or root files are admitted automatically. FULL
owns descendant modules recursively, but this revision does not expand
Robinhood's direct-directory contract. All current Architecture 131 registered
test modules remain in Robinhood and therefore in FULL. Tests inspect
registrations to prove coverage; production certification code does not depend
on private checkpoint-runner helpers.

The preserved 40-module required baseline is:

```text
tests/domain/test_market.py
tests/domain/test_orders.py
tests/domain/test_positions.py
tests/domain/test_proposals.py
tests/execution/test_execution_models.py
tests/execution/test_order_engine.py
tests/execution/test_paper_fill_application.py
tests/execution/test_paper_fills.py
tests/execution/test_paper_submission.py
tests/execution/test_portfolio_orders.py
tests/ledger/test_checkpoint_state.py
tests/ledger/test_initialization.py
tests/ledger/test_ledger.py
tests/ledger/test_models.py
tests/review_paper/test_forward_preview.py
tests/review_paper/test_intent_bridge.py
tests/review_paper/test_nyse_published_regular_sessions.py
tests/review_paper/test_performance.py
tests/review_paper/test_prepare_qualification.py
tests/review_paper/test_risk_context.py
tests/review_paper/test_risk_price_acquisition.py
tests/review_paper/test_risk_prices.py
tests/review_paper/test_session_admission.py
tests/review_paper/test_store.py
tests/review_paper/test_supervised_forward_paper.py
tests/risk/test_manager.py
tests/risk/test_orchestration.py
tests/risk/test_risk_models.py
tests/robinhood_mcp/test_account_resolution.py
tests/robinhood_mcp/test_adapter.py
tests/robinhood_mcp/test_sdk_transport.py
tests/robinhood_mcp/test_windows_oauth.py
tests/runtime/test_checkpoint_runner.py
tests/scripts/test_run_test_certification.py
tests/test_robinhood_forward_paper_cycle.py
tests/test_robinhood_live_qualification_verifier.py
tests/test_robinhood_paper_cycle.py
tests/test_robinhood_paper_operator.py
tests/test_robinhood_paper_pipeline.py
tests/test_robinhood_prepare_qualification_verifier.py
```

## Reviewed legacy ownership and EXHAUSTIVE

At the current tree:

| Legacy population | Modules |
| --- | ---: |
| tests/acceptance/ | 1 |
| tests/cli/ | 34 |
| tests/gui/ | 34 |
| tests/market_data/ | 8 |
| tests/runtime/ | 126 |
| tests/scripts/ | 1 |
| Total | 204 |

Reviewed whole legacy namespaces are `tests/acceptance/`, `tests/gui/`, and
`tests/runtime/`, including descendants, with the exact supported
`tests/runtime/test_checkpoint_runner.py` exception. New tests in these
namespaces remain legacy by ownership until explicitly reclassified.

Mixed CLI/market-data/scripts legacy ownership is frozen to these exact files:

```text
tests/cli/test_checkpoint_lineage.py
tests/cli/test_checkpoint_transition.py
tests/cli/test_daily_snapshot_capture.py
tests/cli/test_daily_snapshot_config.py
tests/cli/test_paper_operation_config.py
tests/cli/test_paper_operation_execution.py
tests/cli/test_paper_operation_failed_receipt.py
tests/cli/test_paper_operation_inspection.py
tests/cli/test_paper_operation_receipt_output.py
tests/cli/test_pd2d1_b1_readonly_diagnostic.py
tests/cli/test_pd2d1_first_paper_qualification.py
tests/cli/test_pd2d1_p1_readonly_diagnostic.py
tests/cli/test_pd2d1_preparation_readonly_diagnostic.py
tests/cli/test_pd2d2_first_paper_execution.py
tests/cli/test_pd2d2_post_mutation_reconciliation.py
tests/cli/test_pd3_read_only_recovery_launcher.py
tests/cli/test_pd3_read_only_recovery_validation.py
tests/cli/test_pd4_operator_observability_snapshot.py
tests/cli/test_pd4_operator_observability_source_launcher.py
tests/cli/test_pd4_read_only_decision_qualification.py
tests/cli/test_pd4_read_only_decision_reconciliation.py
tests/cli/test_pd4_read_only_settlement_qualification.py
tests/cli/test_pd4_read_only_settlement_reconciliation.py
tests/cli/test_pd4_read_only_single_deferred_settlement_qualification.py
tests/cli/test_pd4_read_only_single_deferred_settlement_reconciliation.py
tests/cli/test_pd4_read_only_unattended_validation.py
tests/cli/test_pd4_single_deferred_settlement_execution.py
tests/cli/test_pd4_unattended_settlement_execution.py
tests/cli/test_personal_desktop_unattended_capture_warmup_launcher.py
tests/cli/test_personal_desktop_unattended_decision_publication_launcher.py
tests/cli/test_personal_desktop_unattended_paper_launcher.py
tests/cli/test_production_daily_snapshot_capture.py
tests/cli/test_verified_snapshot_paper_cycle.py
tests/cli/test_windows_authority.py
tests/market_data/test_alpaca_daily_snapshot.py
tests/market_data/test_alpaca_http.py
tests/market_data/test_daily_snapshot_acceptance.py
tests/market_data/test_daily_snapshot_identity.py
tests/market_data/test_daily_snapshot_models.py
tests/market_data/test_daily_snapshot_provider.py
tests/market_data/test_daily_snapshot_serialization.py
tests/market_data/test_daily_snapshot_verification.py
tests/scripts/test_capture_daily_market_snapshot.py
```

Legacy includes retired Alpaca/daily-snapshot capture, checkpointed
verified-snapshot/old PaperAccount operation, PD2/PD3/PD4 operational CLIs,
personal-desktop Paper-v2, D10 scheduler/deployment/recovery, Windows
transactional/effectful capture authority, Architecture-77/78 native acceptance,
and the current pre-Robinhood GUI implementation.

GUI remains a future product goal. Its existing implementation is legacy
because it is tied to the retired operational artifact/runtime model; a future
Robinhood-integrated GUI milestone must explicitly reclassify or replace it.
D10/Windows/Paper-v2/Alpaca operational paths are historical compatibility,
not current product certification requirements.

LEGACY is the complement of FULL only after every discovered module has
reviewed supported or legacy ownership. Unknown ownership never defaults to
legacy. EXHAUSTIVE equals complete `tests/**/test_*.py` discovery over that
admitted repository and is the backward compatibility/repository archaeology
gate. It is not routine current-product certification.

## Fail-closed invariants and lanes

Every profile first admits the full repository classification and both required
baselines. Missing/renamed required FULL or Robinhood modules stop all profiles.
A wholly unknown namespace, an unknown test in a mixed namespace, overlapping
ownership, duplicate modules, or an invalid support partition fails closed and
requires an explicit support-status decision.

Require:

```text
robinhood subset of full
full intersection legacy == empty
full union legacy == exhaustive
exhaustive == complete discovered repository inventory
```

All profiles use the existing deterministic descending-file-size balancing,
with stable path/lane ties and whole-file allocation. FULL and Robinhood have
exactly two nonempty balanced lanes and no historical serial lane. LEGACY and
EXHAUSTIVE retain the exact historical five-module serial allowlist:

```text
tests/runtime/test_windows_transactional_capture_authority.py
tests/runtime/test_windows_authority_schema.py
tests/runtime/test_windows_authority.py
tests/runtime/test_windows_effectful_capture_native_acceptance.py
tests/acceptance/test_windows_authority_provisioning_acceptance.py
```

Architecture-77 remains serial; unrestricted parallel safety is not established.
Both non-serial compatibility lanes must be nonempty. All lanes are checked
before any pytest starts; an empty module list must never trigger accidental
repository-wide collection. Partitions must be complete/disjoint for the
selection, and success requires the exact expected profile-specific lane names,
successful exits/JUnit validation, unchanged source identity, and successful
whole-repository static checks.

## Source checks and evidence compatibility

All profiles preserve exact worktree/branch/HEAD/tree verification, local
tracking-ref and live-origin proof, clean admission and post-test/final source
verification, protected-opt-in rejection, unique external basetemp, timeouts,
JUnit validation, and evidence outside the worktree. Actual runs require
`F:\AI\temp\pytest`. `--plan` verifies admission and records topology without
launching pytest or static checks.

Every profile retains whole-repository post-test static checks:

```text
ruff check --no-cache .
ruff format --check --no-cache .
git diff --check
```

`results.json` preserves `profile`, `repository_inventory`, `selected_inventory`,
`excluded_inventory`, `lanes`, source and result fields. Existing `inventory`
remains the flattened selected lane inventory.

`inventory.json` preserves `all` and `repository` as complete repository
inventory, with `profile`, `selected`, `excluded`, `broad`, `serial`, and `lanes`.
Only EXHAUSTIVE has `selected == all`. FULL selects supported modules,
Robinhood selects its supported subset, and LEGACY selects the admitted
supported complement. FULL/Robinhood retain empty `serial` metadata without
an empty process.

Both evidence files add `classification` with policy `architecture-132-r1`,
`supported_inventory`, `legacy_inventory`, all four `profile_counts`, and
reviewed `ownership` (whole directories, exact module lists, root pattern,
and Robinhood infrastructure). This makes retained support status auditable
independently of the selected profile.

## Protected boundary and focused verification

All profiles reject the same `PROTECTED_OPT_INS`, even false-looking values.
No profile grants or invokes native Windows acceptance opt-ins, provider access,
Robinhood calls, OAuth interaction, broker effects, or production effects.
PROTECTED always requires separate fresh authorization.

Implementation verifies only `tests/scripts/test_run_test_certification.py`,
Ruff check/format on changed Python files, and Git diff checks. Tests construct
independent baseline expectations and prove counts, support invariants, new
owned-file admission, missing/renamed baselines, unknown ownership rejection,
all lane sets, protected rejection, static commands, source identity, plan-only
behavior, and evidence semantics. Actual certification awaits exact GitHub
review and ChatGPT's authorization. Status/handoff closeout waits for accepted
certification.
