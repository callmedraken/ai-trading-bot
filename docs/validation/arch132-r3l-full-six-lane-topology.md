# Architecture 132-R3L — FULL six-lane current-local validation

## Exact source and preserved evidence

R3L starts from ChatGPT SOURCE ACCEPTED D1S3-R4:

    HEAD e515f2d4b8f75ee04b95f7e89162e37c7890e0a4
    TREE ee326a61a87f543e85a00ec162bbf990bf17e507
    parent / accepted R3K 5c57d49e31b1f0e5174bdc826b933118494e2456
    develop HEAD 2b697b79e6bdbc964d2b0414ced057628e6c2da7
    develop TREE e510210070874ade43a240457645939650e457d8

The sole timing evidence is the immutable preserved four-lane FULL directory:

    F:\AI\temp\certification\arch134-d1s3-r4-full-86ff71accd8f4c468c9807361333c795

Interpreter: F:\AI\ai-trading-bot\.venv\Scripts\python.exe, Python 3.14.3.
The runner returned exit 0 / status passed, but certification acceptance failed
timing: 356.885 seconds wall, 56.885 seconds over the unchanged strict
300-second ceiling. No rerun occurred.

| Original lane | Modules | Cases | Passed | Skipped | Failed | Errors | JUnit ms | Child elapsed s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| broad-1 | 49 | 3548 | 3548 | 0 | 0 | 0 | 278943 | 288.262 |
| broad-2 | 50 | 2991 | 2991 | 0 | 0 | 0 | 335691 | 344.513 |
| broad-3 | 50 | 2453 | 2452 | 1 | 0 | 0 | 345073 | 353.395 |
| broad-4 | 49 | 4142 | 4140 | 2 | 0 | 0 | 271732 | 353.406 |
| total | 198 | 13134 | 13131 | 3 | 0 | 0 | 1231439 | 1339.576 |

Every lane XML, stdout/stderr log and static result was read. All lane stderr
logs were empty; Ruff check, Ruff format (1062 files), and Git diff check
passed. Exact source/live feature/develop admission, post-test and final
identity checks passed; worktree/index stayed clean.

The three explicit skips were capability-bound, permitted symlink cases:

- tests.cli.test_research_session_restore::test_symlink_destination_parent_and_dangling_staging_are_rejected — directory symlinks unavailable.
- tests.cli.test_research_session_bundle::test_existing_destination_entries_are_never_replaced[dangling] — symlink creation unavailable.
- tests.cli.test_verify_research_session_manifest::test_verification_rejects_final_symlink_when_supported — symlink creation unavailable.

## Deterministic derivation and normalization

Before edits, independently match every JUnit classname to its unique canonical
selected module prefix (including class suffixes), multiply each decimal
testcase duration by 1000 exactly, reject negative/fractional milliseconds,
and sum integers by module. Each original lane reconciles to its exact
inventory and total above; no module overlaps lanes, and the union equals
all 198 selected FULL modules exactly.

Raw total is 1231439 ms. The complete raw zero list is exactly
tests/domain/test_proposals.py (0 ms). Normalize that exact zero to 1 ms
before freezing source; all other module values remain exact measured values.
Canonical positive total is 1231440 ms across 198 duplicate-detectable tuple
pairs. The old active FULL table total was 1149907 ms; R3L replaces it.

Sorted compact JSON object SHA256 (UTF-8, sorted keys, separators comma/colon,
no trailing newline):

    65e9c1cc30d09d33db08f70c93be354ef5d3746ea45ef460467848f9f42998f9

Strict source validation rejects malformed pair/table shape, noncanonical
paths, duplicate semantic paths, stale modules, zero/negative/bool/noninteger
weights, duplicate selected inventory, and invalid fallback values. A future
admitted FULL module receives exactly FULL_FALLBACK_MS = 1000 and stays covered
once. The runtime never reads this document, JUnit, or prior evidence.

The pre-edit machine-readable derivation, raw/canonical maps, ordered five/six
models and preserved-evidence hashes are also stored externally at:

    F:\AI\temp\certification\arch132-r3l-derivation-477063d1cfcb450daa502711c3d6e2ea\derivation.json

## Four/five rejection and six-lane admission

Four lanes are mathematically insufficient: 1231.439 / 4 = 307.85975 seconds,
even before process/static overhead. Five has testcase lower bound 246.2878 s;
the reported child-work total gives 1339.576 / 5 = 267.9152 s, only 32.0848 s
below the ceiling before additional concurrency uncertainty. Observed reported
child-minus-JUnit gaps were 9.319 / 8.822 / 8.322 / 81.674 s. Five was modeled
only and rejected without a publication or execution attempt.

Six is selected directly: raw testcase lower bound 205.239833 s and reported
child-work lower bound 223.262667 s. The exact normalized model below has
maximum = minimum = 205240 ms. Both pre-edit conditions pass:

    M = 205240 < 300000
    M + 81674 = 286914 < 300000
    conservative stress headroom = 13086 ms

This stress check is a design admission bound, not a changed runtime rule.
Actual canonical FULL must still finish strictly below 300 seconds; no retries,
automatic seventh lane, runtime alternatives, or raised ceiling are introduced.
CPU/disk/antivirus contention remains an uncertainty requiring the real run.

Both models use descending frozen milliseconds, ascending canonical path,
lowest lane total then lowest index ties, and preserve whole-module assignment
order. Ordered membership hashes use UTF-8 concatenation of each canonical
module path followed by one LF, including the last path.

## Five-lane analysis only (never implemented)

| Lane | Modules | Modeled ms | Ordered SHA256 | Largest module (ms) |
| --- | ---: | ---: | --- | --- |
| broad-1 | 38 | 246288 | fe2ffcb63a9b4e04a33bb8b7d1a3979fdfbdd803d4892f7c9b4810e25bfb66c6 | tests/review_paper/test_d1_session_execution.py (106074) |
| broad-2 | 40 | 246288 | ab16cb242f14f7c48953d284975c049b797bac90ea67862b819e55cf325cf829 | tests/review_paper/test_five_session_soak.py (104261) |
| broad-3 | 41 | 246288 | a4d39d0e9a50ed47c769e12f112d659da6ef6f8ca5fba084ec98911ffc75db1a | tests/runtime/checkpoint_runner/test_arch133_l_m.py (82834) |
| broad-4 | 39 | 246288 | 430c8f0fcceb161e57ffa5e0c6d187bd3d1766987bca7555ede6c2709140fced | tests/runtime/checkpoint_runner/test_arch131.py (78936) |
| broad-5 | 40 | 246288 | 3d3f7d6a52886e30299a3f869d6f4b81c9c0cb4a37b8ecc8701bfd60549dbc64 | tests/review_paper/test_arch133_scheduler_installation.py (54693) |

Exact ordered lane membership:

broad-1:

    tests/review_paper/test_d1_session_execution.py
    tests/review_paper/test_supervised_release_installation_operator.py
    tests/review_paper/test_arch133_reprovision_recovery.py
    tests/review_paper/test_arch133_fresh_activation_reprovision_corrected.py
    tests/review_paper/test_pre_market_wake_overnight.py
    tests/review_paper/test_supervised_deployment_qualification.py
    tests/review_paper/test_publication_state_paper_corrected.py
    tests/review_paper/test_alpaca_credential_generation.py
    tests/review_paper/test_supervised_release_publication_recovery.py
    tests/review_paper/test_post_publication_verifier.py
    tests/review_paper/test_unattended_one_wake.py
    tests/scripts/test_run_rolling_historical_simulation.py
    tests/review_paper/test_supervised_runtime_host_admission.py
    tests/review_paper/test_prepare_qualification.py
    tests/experiments/test_pairwise.py
    tests/review_paper/test_supervised_release_foundation.py
    tests/review_paper/test_strategy_market_history.py
    tests/review_paper/test_supervised_release_installation_reconciliation.py
    tests/review_paper/test_retained_root_acl_recovery.py
    tests/cli/test_research_session_restore.py
    tests/experiments/test_walk_forward_analytics.py
    tests/review_paper/test_store.py
    tests/scripts/certification_runner/test_children.py
    tests/review_paper/test_production_strategy_cycle.py
    tests/cli/test_walk_forward_experiment_serialization.py
    tests/cli/test_research_session_archive_cli.py
    tests/experiments/test_research_strategy_backtest.py
    tests/integration/test_walk_forward_research_archive_e2e.py
    tests/experiments/test_research_strategy_definition.py
    tests/portfolio/test_optimized_targets.py
    tests/strategies/test_moving_average.py
    tests/portfolio_analytics/test_analyzer.py
    tests/analytics/test_analyzer.py
    tests/ledger/test_initialization.py
    tests/portfolio/test_models.py
    tests/scripts/test_research_session_archive_scripts.py
    tests/market_calendar/test_nyse_calendar.py
    tests/scripts/test_create_walk_forward_research_bundle.py

broad-2:

    tests/review_paper/test_five_session_soak.py
    tests/runtime/checkpoint_runner/test_arch133_h_k.py
    tests/review_paper/test_arch134_f1r1_d1s1_successor_soak.py
    tests/runtime/checkpoint_runner/test_arch133_a_g.py
    tests/review_paper/test_arch134_f1r1_d1s3_successor_installation_operator.py
    tests/scripts/test_archive_project_history.py
    tests/review_paper/test_arch133_reprovision_reconciliation.py
    tests/review_paper/test_alpaca_authentication_qualification.py
    tests/scripts/certification_runner/test_results.py
    tests/test_robinhood_prepare_qualification_verifier.py
    tests/review_paper/test_unattended_host.py
    tests/integration/test_walk_forward_research_bundle_e2e.py
    tests/robinhood_mcp/test_windows_oauth.py
    tests/scripts/test_run_backtest.py
    tests/experiments/test_research_candidate_walk_forward.py
    tests/test_robinhood_forward_paper_cycle.py
    tests/experiments/test_research_strategy_walk_forward.py
    tests/scripts/certification_runner/test_source.py
    tests/review_paper/test_scratch_root_acl.py
    tests/review_paper/test_arch133_reprovision_admission_diagnostic.py
    tests/review_paper/test_published_session_prepare.py
    tests/cli/test_walk_forward_stability_serialization.py
    tests/test_robinhood_prepare_operator.py
    tests/cli/test_restore_research_session_archive.py
    tests/cli/test_historical_experiment_report_serialization.py
    tests/experiments/test_research_strategy_paper_candidate_eligibility_v2.py
    tests/robinhood_mcp/test_historical.py
    tests/robinhood_mcp/test_account_resolution.py
    tests/cli/test_research_session_manifest.py
    tests/optimization/test_cpu_mean_cvar.py
    tests/cli/test_walk_forward_stability_config.py
    tests/execution/test_portfolio_orders.py
    tests/risk/test_manager.py
    tests/multi_backtesting/test_engine.py
    tests/scripts/test_run_walk_forward_experiment.py
    tests/cli/test_historical_experiment_pareto_config.py
    tests/rebalancing/test_models.py
    tests/execution/test_execution_models.py
    tests/domain/test_positions.py
    tests/market_calendar/test_calendar_models.py

broad-3:

    tests/runtime/checkpoint_runner/test_arch133_l_m.py
    tests/experiments/test_research_candidate_shadow_binding.py
    tests/review_paper/test_arch134_f1r1_c1_qualification_operator.py
    tests/review_paper/test_arch133_windows_rename_qualification.py
    tests/runtime/checkpoint_runner/test_ci.py
    tests/scripts/test_run_historical_experiment.py
    tests/scripts/certification_runner/test_lanes.py
    tests/cli/test_optimized_simulation.py
    tests/review_paper/test_publication_state_paper_diagnostic.py
    tests/portfolio_analytics/test_optimized_simulation.py
    tests/experiments/test_research_strategy_f1_paper_evidence_verification.py
    tests/review_paper/test_arch134_f1r1_d1s2_successor_readiness.py
    tests/review_paper/test_unattended_publication.py
    tests/review_paper/test_supervised_release_installation.py
    tests/test_robinhood_live_qualification_verifier.py
    tests/review_paper/test_arch133_parent_policy_diagnostic.py
    tests/test_robinhood_paper_operator.py
    tests/cli/test_walk_forward_experiment.py
    tests/cli/test_research_session_archive.py
    tests/experiments/test_pareto.py
    tests/review_paper/test_arch134_f1r1_b_host_qualification.py
    tests/market_data/test_csv_historical_provider.py
    tests/cli/test_verify_research_session_manifest.py
    tests/review_paper/test_session_admission.py
    tests/review_paper/test_risk_prices.py
    tests/simulation/test_optimized_paper_portfolio.py
    tests/cli/test_historical_experiment_pairwise_serialization.py
    tests/simulation/test_paper_portfolio.py
    tests/market_data/test_multi_symbol_provider.py
    tests/portfolio/test_historical_scenarios.py
    tests/execution/test_paper_fill_application.py
    tests/cli/test_historical_experiment_pairwise_config.py
    tests/backtesting/test_backtest_engine.py
    tests/domain/test_market.py
    tests/execution/test_paper_fills.py
    tests/domain/test_orders.py
    tests/rebalancing/test_planner.py
    tests/market_data/test_multi_symbol_models.py
    tests/multi_backtesting/test_strategy_contract.py
    tests/domain/test_proposals.py
    tests/market_data/test_historical_models.py

broad-4:

    tests/runtime/checkpoint_runner/test_arch131.py
    tests/review_paper/test_supervised_release_bundle.py
    tests/strategies/test_production_strategy_contract.py
    tests/integration/test_walk_forward_e2e.py
    tests/review_paper/test_production_paper_runtime_acl.py
    tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py
    tests/review_paper/test_alpaca_credential_staging_cleanup.py
    tests/review_paper/test_production_paper_runtime.py
    tests/experiments/test_research_strategy_production_compatibility.py
    tests/review_paper/test_post_publication_stage_diagnostic.py
    tests/review_paper/test_pre_market_wake_qualification.py
    tests/runtime/checkpoint_runner/test_core.py
    tests/scripts/certification_runner/test_profiles.py
    tests/experiments/test_research_candidate_shadow_observation.py
    tests/experiments/test_report.py
    tests/review_paper/test_risk_context.py
    tests/review_paper/test_arch133_parent_security_diagnostic.py
    tests/experiments/test_research_candidate.py
    tests/integration/test_walk_forward_research_transport_e2e.py
    tests/review_paper/test_risk_price_acquisition.py
    tests/experiments/test_historical.py
    tests/review_paper/test_performance.py
    tests/cli/test_research_session_bundle.py
    tests/experiments/test_walk_forward.py
    tests/experiments/test_research_strategy_robustness.py
    tests/review_paper/test_nyse_published_regular_sessions.py
    tests/test_robinhood_paper_pipeline.py
    tests/cli/test_create_research_session_bundle.py
    tests/experiments/test_comparison.py
    tests/review_paper/test_arch134_f1r1_a_runtime_isolation.py
    tests/robinhood_mcp/test_sdk_transport.py
    tests/execution/test_order_engine.py
    tests/execution/test_paper_submission.py
    tests/risk/test_orchestration.py
    tests/cli/test_walk_forward_experiment_config.py
    tests/portfolio_analytics/test_models.py
    tests/ledger/test_ledger.py
    tests/backtesting/test_backtest_models.py
    tests/test_config.py

broad-5:

    tests/review_paper/test_arch133_scheduler_installation.py
    tests/experiments/test_research_candidate_shadow_qualification.py
    tests/review_paper/test_five_session_soak_child.py
    tests/review_paper/test_arch133_closed_descendant_rename_qualification.py
    tests/review_paper/test_arch133_fresh_activation_reprovision.py
    tests/review_paper/test_armed_production_paper_session.py
    tests/review_paper/test_d1_session_authorization.py
    tests/review_paper/test_unattended_execution.py
    tests/test_robinhood_supervised_qualification.py
    tests/review_paper/test_supervised_maintenance_rebind.py
    tests/review_paper/test_unattended_state_store.py
    tests/experiments/test_research_strategy_paper_candidate_eligibility.py
    tests/cli/test_historical_experiment.py
    tests/review_paper/test_production_strategy_prepare_operator.py
    tests/review_paper/test_current_production_strategy_decision.py
    tests/review_paper/test_history_qualification.py
    tests/review_paper/test_forward_preview.py
    tests/review_paper/test_supervised_forward_paper.py
    tests/test_robinhood_paper_cycle.py
    tests/experiments/test_walk_forward_stability.py
    tests/review_paper/test_retained_root_diagnostic.py
    tests/review_paper/test_unattended_activation.py
    tests/cli/test_rolling_historical.py
    tests/cli/test_walk_forward_aggregate_serialization.py
    tests/strategies/test_production_strategy_decision.py
    tests/simulation/test_rolling_historical.py
    tests/integration/test_walk_forward_research_restore_e2e.py
    tests/cli/test_historical_experiment_pareto_serialization.py
    tests/experiments/test_grid.py
    tests/ledger/test_checkpoint_state.py
    tests/rebalancing/test_proposals.py
    tests/review_paper/test_intent_bridge.py
    tests/multi_backtesting/test_models.py
    tests/robinhood_mcp/test_adapter.py
    tests/portfolio/test_scenarios.py
    tests/risk/test_risk_models.py
    tests/cli/test_walk_forward_aggregate_config.py
    tests/ledger/test_models.py
    tests/portfolio/test_mean_cvar.py
    tests/portfolio/test_optimizer_protocol.py

## Six-lane exact implemented model

| Lane | Modules | Modeled ms | Ordered SHA256 | Largest module (ms) |
| --- | ---: | ---: | --- | --- |
| broad-1 | 32 | 205240 | b86fdc382015ef5845e761a6c671f8a9cd27c195ac37e900b2c709b41f68fd37 | tests/review_paper/test_d1_session_execution.py (106074) |
| broad-2 | 32 | 205240 | 40730d6b3d85600efdf972b84f5335e88d93b97915f6f6e9922bdf291176b64e | tests/review_paper/test_five_session_soak.py (104261) |
| broad-3 | 33 | 205240 | a1da558ff6aee18e08a3e949f331e8743e0c02897d621107ad3d5f92237e454f | tests/runtime/checkpoint_runner/test_arch133_l_m.py (82834) |
| broad-4 | 33 | 205240 | 3791a2a803e6a9c48cb41133a4f1568ed78a201a29aa536f547eb1d19edad0ef | tests/runtime/checkpoint_runner/test_arch131.py (78936) |
| broad-5 | 34 | 205240 | dc0fd920b76c118293b943065b4be59d804b7fc6da8bca8919b0725cc9aaeb57 | tests/review_paper/test_arch133_scheduler_installation.py (54693) |
| broad-6 | 34 | 205240 | e5364bb6b084ae092926a3bc480b43a5c5c40ca0a9e5909b16d85e02fa0b4f6f | tests/experiments/test_research_candidate_shadow_qualification.py (44293) |

Exact ordered lane membership:

broad-1:

    tests/review_paper/test_d1_session_execution.py
    tests/review_paper/test_arch133_closed_descendant_rename_qualification.py
    tests/runtime/checkpoint_runner/test_arch133_a_g.py
    tests/review_paper/test_arch134_f1r1_d1s3_successor_installation_operator.py
    tests/review_paper/test_alpaca_credential_staging_cleanup.py
    tests/test_robinhood_supervised_qualification.py
    tests/review_paper/test_supervised_release_publication_recovery.py
    tests/review_paper/test_unattended_state_store.py
    tests/scripts/certification_runner/test_profiles.py
    tests/review_paper/test_supervised_release_installation.py
    tests/experiments/test_research_candidate_shadow_observation.py
    tests/review_paper/test_history_qualification.py
    tests/review_paper/test_forward_preview.py
    tests/experiments/test_research_strategy_walk_forward.py
    tests/cli/test_research_session_archive.py
    tests/review_paper/test_retained_root_diagnostic.py
    tests/review_paper/test_published_session_prepare.py
    tests/cli/test_verify_research_session_manifest.py
    tests/experiments/test_walk_forward.py
    tests/cli/test_restore_research_session_archive.py
    tests/cli/test_walk_forward_experiment_serialization.py
    tests/cli/test_create_research_session_bundle.py
    tests/experiments/test_comparison.py
    tests/execution/test_paper_fill_application.py
    tests/cli/test_historical_experiment_pairwise_config.py
    tests/execution/test_order_engine.py
    tests/robinhood_mcp/test_adapter.py
    tests/portfolio/test_scenarios.py
    tests/scripts/test_run_walk_forward_experiment.py
    tests/rebalancing/test_models.py
    tests/portfolio/test_mean_cvar.py
    tests/domain/test_positions.py

broad-2:

    tests/review_paper/test_five_session_soak.py
    tests/strategies/test_production_strategy_contract.py
    tests/review_paper/test_arch133_fresh_activation_reprovision_corrected.py
    tests/review_paper/test_armed_production_paper_session.py
    tests/review_paper/test_supervised_deployment_qualification.py
    tests/review_paper/test_alpaca_authentication_qualification.py
    tests/review_paper/test_post_publication_stage_diagnostic.py
    tests/test_robinhood_prepare_qualification_verifier.py
    tests/review_paper/test_arch134_f1r1_d1s2_successor_readiness.py
    tests/review_paper/test_production_strategy_prepare_operator.py
    tests/robinhood_mcp/test_windows_oauth.py
    tests/review_paper/test_prepare_qualification.py
    tests/test_robinhood_paper_operator.py
    tests/test_robinhood_paper_cycle.py
    tests/review_paper/test_retained_root_acl_recovery.py
    tests/review_paper/test_arch133_reprovision_admission_diagnostic.py
    tests/review_paper/test_unattended_activation.py
    tests/review_paper/test_session_admission.py
    tests/review_paper/test_production_strategy_cycle.py
    tests/simulation/test_optimized_paper_portfolio.py
    tests/cli/test_historical_experiment_pairwise_serialization.py
    tests/robinhood_mcp/test_historical.py
    tests/portfolio/test_historical_scenarios.py
    tests/rebalancing/test_proposals.py
    tests/strategies/test_moving_average.py
    tests/portfolio_analytics/test_analyzer.py
    tests/analytics/test_analyzer.py
    tests/portfolio_analytics/test_models.py
    tests/cli/test_walk_forward_aggregate_config.py
    tests/ledger/test_models.py
    tests/execution/test_execution_models.py
    tests/multi_backtesting/test_strategy_contract.py

broad-3:

    tests/runtime/checkpoint_runner/test_arch133_l_m.py
    tests/runtime/checkpoint_runner/test_arch133_h_k.py
    tests/review_paper/test_arch133_windows_rename_qualification.py
    tests/review_paper/test_arch133_fresh_activation_reprovision.py
    tests/scripts/test_archive_project_history.py
    tests/scripts/certification_runner/test_lanes.py
    tests/cli/test_optimized_simulation.py
    tests/review_paper/test_supervised_maintenance_rebind.py
    tests/review_paper/test_pre_market_wake_qualification.py
    tests/experiments/test_research_strategy_paper_candidate_eligibility.py
    tests/cli/test_historical_experiment.py
    tests/test_robinhood_live_qualification_verifier.py
    tests/experiments/test_pairwise.py
    tests/review_paper/test_arch133_parent_security_diagnostic.py
    tests/experiments/test_research_candidate.py
    tests/scripts/certification_runner/test_source.py
    tests/experiments/test_pareto.py
    tests/experiments/test_walk_forward_analytics.py
    tests/cli/test_walk_forward_stability_serialization.py
    tests/test_robinhood_prepare_operator.py
    tests/review_paper/test_risk_prices.py
    tests/review_paper/test_nyse_published_regular_sessions.py
    tests/cli/test_historical_experiment_pareto_serialization.py
    tests/robinhood_mcp/test_account_resolution.py
    tests/review_paper/test_arch134_f1r1_a_runtime_isolation.py
    tests/optimization/test_cpu_mean_cvar.py
    tests/execution/test_portfolio_orders.py
    tests/domain/test_market.py
    tests/ledger/test_initialization.py
    tests/rebalancing/test_planner.py
    tests/backtesting/test_backtest_models.py
    tests/market_calendar/test_nyse_calendar.py
    tests/domain/test_proposals.py

broad-4:

    tests/runtime/checkpoint_runner/test_arch131.py
    tests/review_paper/test_five_session_soak_child.py
    tests/review_paper/test_arch133_reprovision_recovery.py
    tests/review_paper/test_pre_market_wake_overnight.py
    tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py
    tests/review_paper/test_arch133_reprovision_reconciliation.py
    tests/review_paper/test_alpaca_credential_generation.py
    tests/portfolio_analytics/test_optimized_simulation.py
    tests/review_paper/test_post_publication_verifier.py
    tests/runtime/checkpoint_runner/test_core.py
    tests/review_paper/test_supervised_runtime_host_admission.py
    tests/review_paper/test_current_production_strategy_decision.py
    tests/experiments/test_research_candidate_walk_forward.py
    tests/test_robinhood_forward_paper_cycle.py
    tests/cli/test_walk_forward_experiment.py
    tests/review_paper/test_risk_price_acquisition.py
    tests/experiments/test_historical.py
    tests/market_data/test_csv_historical_provider.py
    tests/cli/test_rolling_historical.py
    tests/scripts/certification_runner/test_children.py
    tests/strategies/test_production_strategy_decision.py
    tests/experiments/test_research_strategy_paper_candidate_eligibility_v2.py
    tests/experiments/test_research_strategy_backtest.py
    tests/integration/test_walk_forward_research_archive_e2e.py
    tests/cli/test_research_session_manifest.py
    tests/robinhood_mcp/test_sdk_transport.py
    tests/execution/test_paper_submission.py
    tests/risk/test_manager.py
    tests/multi_backtesting/test_engine.py
    tests/domain/test_orders.py
    tests/scripts/test_research_session_archive_scripts.py
    tests/scripts/test_create_walk_forward_research_bundle.py
    tests/market_calendar/test_calendar_models.py

broad-5:

    tests/review_paper/test_arch133_scheduler_installation.py
    tests/experiments/test_research_candidate_shadow_binding.py
    tests/review_paper/test_arch134_f1r1_c1_qualification_operator.py
    tests/integration/test_walk_forward_e2e.py
    tests/runtime/checkpoint_runner/test_ci.py
    tests/review_paper/test_d1_session_authorization.py
    tests/review_paper/test_unattended_execution.py
    tests/review_paper/test_production_paper_runtime.py
    tests/scripts/certification_runner/test_results.py
    tests/review_paper/test_unattended_one_wake.py
    tests/review_paper/test_unattended_host.py
    tests/scripts/test_run_rolling_historical_simulation.py
    tests/experiments/test_report.py
    tests/review_paper/test_risk_context.py
    tests/review_paper/test_supervised_release_foundation.py
    tests/review_paper/test_supervised_forward_paper.py
    tests/review_paper/test_supervised_release_installation_reconciliation.py
    tests/review_paper/test_scratch_root_acl.py
    tests/review_paper/test_arch134_f1r1_b_host_qualification.py
    tests/cli/test_research_session_bundle.py
    tests/cli/test_walk_forward_aggregate_serialization.py
    tests/simulation/test_rolling_historical.py
    tests/cli/test_research_session_archive_cli.py
    tests/integration/test_walk_forward_research_restore_e2e.py
    tests/market_data/test_multi_symbol_provider.py
    tests/ledger/test_checkpoint_state.py
    tests/portfolio/test_optimized_targets.py
    tests/multi_backtesting/test_models.py
    tests/risk/test_orchestration.py
    tests/cli/test_walk_forward_experiment_config.py
    tests/risk/test_risk_models.py
    tests/cli/test_historical_experiment_pareto_config.py
    tests/market_data/test_multi_symbol_models.py
    tests/market_data/test_historical_models.py

broad-6:

    tests/experiments/test_research_candidate_shadow_qualification.py
    tests/review_paper/test_supervised_release_bundle.py
    tests/review_paper/test_supervised_release_installation_operator.py
    tests/review_paper/test_arch134_f1r1_d1s1_successor_soak.py
    tests/review_paper/test_production_paper_runtime_acl.py
    tests/scripts/test_run_historical_experiment.py
    tests/review_paper/test_publication_state_paper_corrected.py
    tests/review_paper/test_publication_state_paper_diagnostic.py
    tests/experiments/test_research_strategy_production_compatibility.py
    tests/experiments/test_research_strategy_f1_paper_evidence_verification.py
    tests/integration/test_walk_forward_research_bundle_e2e.py
    tests/review_paper/test_unattended_publication.py
    tests/scripts/test_run_backtest.py
    tests/review_paper/test_arch133_parent_policy_diagnostic.py
    tests/review_paper/test_strategy_market_history.py
    tests/integration/test_walk_forward_research_transport_e2e.py
    tests/experiments/test_walk_forward_stability.py
    tests/cli/test_research_session_restore.py
    tests/review_paper/test_performance.py
    tests/review_paper/test_store.py
    tests/experiments/test_research_strategy_robustness.py
    tests/cli/test_historical_experiment_report_serialization.py
    tests/test_robinhood_paper_pipeline.py
    tests/simulation/test_paper_portfolio.py
    tests/experiments/test_grid.py
    tests/experiments/test_research_strategy_definition.py
    tests/review_paper/test_intent_bridge.py
    tests/cli/test_walk_forward_stability_config.py
    tests/backtesting/test_backtest_engine.py
    tests/execution/test_paper_fills.py
    tests/portfolio/test_models.py
    tests/ledger/test_ledger.py
    tests/test_config.py
    tests/portfolio/test_optimizer_protocol.py

## Complete measured and normalized module material

| Canonical module | Raw ms | Source ms |
| --- | ---: | ---: |
| tests/analytics/test_analyzer.py | 12 | 12 |
| tests/backtesting/test_backtest_engine.py | 13 | 13 |
| tests/backtesting/test_backtest_models.py | 5 | 5 |
| tests/cli/test_create_research_session_bundle.py | 66 | 66 |
| tests/cli/test_historical_experiment.py | 2652 | 2652 |
| tests/cli/test_historical_experiment_pairwise_config.py | 21 | 21 |
| tests/cli/test_historical_experiment_pairwise_serialization.py | 77 | 77 |
| tests/cli/test_historical_experiment_pareto_config.py | 6 | 6 |
| tests/cli/test_historical_experiment_pareto_serialization.py | 66 | 66 |
| tests/cli/test_historical_experiment_report_serialization.py | 98 | 98 |
| tests/cli/test_optimized_simulation.py | 8695 | 8695 |
| tests/cli/test_research_session_archive.py | 452 | 452 |
| tests/cli/test_research_session_archive_cli.py | 85 | 85 |
| tests/cli/test_research_session_bundle.py | 223 | 223 |
| tests/cli/test_research_session_manifest.py | 33 | 33 |
| tests/cli/test_research_session_restore.py | 350 | 350 |
| tests/cli/test_restore_research_session_archive.py | 114 | 114 |
| tests/cli/test_rolling_historical.py | 235 | 235 |
| tests/cli/test_verify_research_session_manifest.py | 200 | 200 |
| tests/cli/test_walk_forward_aggregate_config.py | 7 | 7 |
| tests/cli/test_walk_forward_aggregate_serialization.py | 137 | 137 |
| tests/cli/test_walk_forward_experiment.py | 529 | 529 |
| tests/cli/test_walk_forward_experiment_config.py | 10 | 10 |
| tests/cli/test_walk_forward_experiment_serialization.py | 93 | 93 |
| tests/cli/test_walk_forward_stability_config.py | 17 | 17 |
| tests/cli/test_walk_forward_stability_serialization.py | 199 | 199 |
| tests/domain/test_market.py | 13 | 13 |
| tests/domain/test_orders.py | 8 | 8 |
| tests/domain/test_positions.py | 1 | 1 |
| tests/domain/test_proposals.py | 0 | 1 |
| tests/execution/test_execution_models.py | 2 | 2 |
| tests/execution/test_order_engine.py | 17 | 17 |
| tests/execution/test_paper_fill_application.py | 25 | 25 |
| tests/execution/test_paper_fills.py | 12 | 12 |
| tests/execution/test_paper_submission.py | 15 | 15 |
| tests/execution/test_portfolio_orders.py | 16 | 16 |
| tests/experiments/test_comparison.py | 58 | 58 |
| tests/experiments/test_grid.py | 44 | 44 |
| tests/experiments/test_historical.py | 370 | 370 |
| tests/experiments/test_pairwise.py | 1020 | 1020 |
| tests/experiments/test_pareto.py | 411 | 411 |
| tests/experiments/test_report.py | 1757 | 1757 |
| tests/experiments/test_research_candidate.py | 644 | 644 |
| tests/experiments/test_research_candidate_shadow_binding.py | 34867 | 34867 |
| tests/experiments/test_research_candidate_shadow_observation.py | 2102 | 2102 |
| tests/experiments/test_research_candidate_shadow_qualification.py | 44293 | 44293 |
| tests/experiments/test_research_candidate_walk_forward.py | 1412 | 1412 |
| tests/experiments/test_research_strategy_backtest.py | 63 | 63 |
| tests/experiments/test_research_strategy_definition.py | 33 | 33 |
| tests/experiments/test_research_strategy_f1_paper_evidence_verification.py | 4501 | 4501 |
| tests/experiments/test_research_strategy_paper_candidate_eligibility.py | 3200 | 3200 |
| tests/experiments/test_research_strategy_paper_candidate_eligibility_v2.py | 85 | 85 |
| tests/experiments/test_research_strategy_production_compatibility.py | 6175 | 6175 |
| tests/experiments/test_research_strategy_robustness.py | 122 | 122 |
| tests/experiments/test_research_strategy_walk_forward.py | 604 | 604 |
| tests/experiments/test_walk_forward.py | 142 | 142 |
| tests/experiments/test_walk_forward_analytics.py | 321 | 321 |
| tests/experiments/test_walk_forward_stability.py | 428 | 428 |
| tests/integration/test_walk_forward_e2e.py | 19838 | 19838 |
| tests/integration/test_walk_forward_research_archive_e2e.py | 49 | 49 |
| tests/integration/test_walk_forward_research_bundle_e2e.py | 3177 | 3177 |
| tests/integration/test_walk_forward_research_restore_e2e.py | 77 | 77 |
| tests/integration/test_walk_forward_research_transport_e2e.py | 517 | 517 |
| tests/ledger/test_checkpoint_state.py | 34 | 34 |
| tests/ledger/test_initialization.py | 12 | 12 |
| tests/ledger/test_ledger.py | 6 | 6 |
| tests/ledger/test_models.py | 5 | 5 |
| tests/market_calendar/test_calendar_models.py | 1 | 1 |
| tests/market_calendar/test_nyse_calendar.py | 5 | 5 |
| tests/market_data/test_csv_historical_provider.py | 275 | 275 |
| tests/market_data/test_historical_models.py | 1 | 1 |
| tests/market_data/test_multi_symbol_models.py | 5 | 5 |
| tests/market_data/test_multi_symbol_provider.py | 39 | 39 |
| tests/multi_backtesting/test_engine.py | 11 | 11 |
| tests/multi_backtesting/test_models.py | 16 | 16 |
| tests/multi_backtesting/test_strategy_contract.py | 2 | 2 |
| tests/optimization/test_cpu_mean_cvar.py | 24 | 24 |
| tests/portfolio/test_historical_scenarios.py | 35 | 35 |
| tests/portfolio/test_mean_cvar.py | 4 | 4 |
| tests/portfolio/test_models.py | 8 | 8 |
| tests/portfolio/test_optimized_targets.py | 23 | 23 |
| tests/portfolio/test_optimizer_protocol.py | 1 | 1 |
| tests/portfolio/test_scenarios.py | 10 | 10 |
| tests/portfolio_analytics/test_analyzer.py | 15 | 15 |
| tests/portfolio_analytics/test_models.py | 10 | 10 |
| tests/portfolio_analytics/test_optimized_simulation.py | 5703 | 5703 |
| tests/rebalancing/test_models.py | 6 | 6 |
| tests/rebalancing/test_planner.py | 8 | 8 |
| tests/rebalancing/test_proposals.py | 25 | 25 |
| tests/review_paper/test_alpaca_authentication_qualification.py | 7556 | 7556 |
| tests/review_paper/test_alpaca_credential_generation.py | 7568 | 7568 |
| tests/review_paper/test_alpaca_credential_staging_cleanup.py | 9954 | 9954 |
| tests/review_paper/test_arch133_closed_descendant_rename_qualification.py | 25107 | 25107 |
| tests/review_paper/test_arch133_fresh_activation_reprovision.py | 18353 | 18353 |
| tests/review_paper/test_arch133_fresh_activation_reprovision_corrected.py | 19268 | 19268 |
| tests/review_paper/test_arch133_parent_policy_diagnostic.py | 1661 | 1661 |
| tests/review_paper/test_arch133_parent_security_diagnostic.py | 966 | 966 |
| tests/review_paper/test_arch133_reprovision_admission_diagnostic.py | 347 | 347 |
| tests/review_paper/test_arch133_reprovision_reconciliation.py | 9842 | 9842 |
| tests/review_paper/test_arch133_reprovision_recovery.py | 23032 | 23032 |
| tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py | 12430 | 12430 |
| tests/review_paper/test_arch133_scheduler_installation.py | 54693 | 54693 |
| tests/review_paper/test_arch133_windows_rename_qualification.py | 20356 | 20356 |
| tests/review_paper/test_arch134_f1r1_a_runtime_isolation.py | 29 | 29 |
| tests/review_paper/test_arch134_f1r1_b_host_qualification.py | 326 | 326 |
| tests/review_paper/test_arch134_f1r1_c1_qualification_operator.py | 26299 | 26299 |
| tests/review_paper/test_arch134_f1r1_d1s1_successor_soak.py | 21660 | 21660 |
| tests/review_paper/test_arch134_f1r1_d1s2_successor_readiness.py | 3357 | 3357 |
| tests/review_paper/test_arch134_f1r1_d1s3_successor_installation_operator.py | 15305 | 15305 |
| tests/review_paper/test_armed_production_paper_session.py | 15402 | 15402 |
| tests/review_paper/test_current_production_strategy_decision.py | 1816 | 1816 |
| tests/review_paper/test_d1_session_authorization.py | 12276 | 12276 |
| tests/review_paper/test_d1_session_execution.py | 106074 | 106074 |
| tests/review_paper/test_five_session_soak.py | 104261 | 104261 |
| tests/review_paper/test_five_session_soak_child.py | 34276 | 34276 |
| tests/review_paper/test_forward_preview.py | 869 | 869 |
| tests/review_paper/test_history_qualification.py | 1283 | 1283 |
| tests/review_paper/test_intent_bridge.py | 19 | 19 |
| tests/review_paper/test_nyse_published_regular_sessions.py | 92 | 92 |
| tests/review_paper/test_performance.py | 256 | 256 |
| tests/review_paper/test_post_publication_stage_diagnostic.py | 5570 | 5570 |
| tests/review_paper/test_post_publication_verifier.py | 3709 | 3709 |
| tests/review_paper/test_pre_market_wake_overnight.py | 17205 | 17205 |
| tests/review_paper/test_pre_market_wake_qualification.py | 3997 | 3997 |
| tests/review_paper/test_prepare_qualification.py | 1727 | 1727 |
| tests/review_paper/test_production_paper_runtime.py | 8485 | 8485 |
| tests/review_paper/test_production_paper_runtime_acl.py | 17312 | 17312 |
| tests/review_paper/test_production_strategy_cycle.py | 120 | 120 |
| tests/review_paper/test_production_strategy_prepare_operator.py | 2284 | 2284 |
| tests/review_paper/test_publication_state_paper_corrected.py | 9317 | 9317 |
| tests/review_paper/test_publication_state_paper_diagnostic.py | 6364 | 6364 |
| tests/review_paper/test_published_session_prepare.py | 286 | 286 |
| tests/review_paper/test_retained_root_acl_recovery.py | 424 | 424 |
| tests/review_paper/test_retained_root_diagnostic.py | 388 | 388 |
| tests/review_paper/test_risk_context.py | 1141 | 1141 |
| tests/review_paper/test_risk_price_acquisition.py | 444 | 444 |
| tests/review_paper/test_risk_prices.py | 113 | 113 |
| tests/review_paper/test_scratch_root_acl.py | 414 | 414 |
| tests/review_paper/test_session_admission.py | 151 | 151 |
| tests/review_paper/test_store.py | 179 | 179 |
| tests/review_paper/test_strategy_market_history.py | 742 | 742 |
| tests/review_paper/test_supervised_deployment_qualification.py | 10831 | 10831 |
| tests/review_paper/test_supervised_forward_paper.py | 619 | 619 |
| tests/review_paper/test_supervised_maintenance_rebind.py | 4767 | 4767 |
| tests/review_paper/test_supervised_release_bundle.py | 41902 | 41902 |
| tests/review_paper/test_supervised_release_foundation.py | 875 | 875 |
| tests/review_paper/test_supervised_release_installation.py | 2105 | 2105 |
| tests/review_paper/test_supervised_release_installation_operator.py | 28205 | 28205 |
| tests/review_paper/test_supervised_release_installation_reconciliation.py | 493 | 493 |
| tests/review_paper/test_supervised_release_publication_recovery.py | 5410 | 5410 |
| tests/review_paper/test_supervised_runtime_host_admission.py | 2590 | 2590 |
| tests/review_paper/test_unattended_activation.py | 249 | 249 |
| tests/review_paper/test_unattended_execution.py | 9517 | 9517 |
| tests/review_paper/test_unattended_host.py | 3358 | 3358 |
| tests/review_paper/test_unattended_one_wake.py | 3498 | 3498 |
| tests/review_paper/test_unattended_publication.py | 2647 | 2647 |
| tests/review_paper/test_unattended_state_store.py | 4474 | 4474 |
| tests/risk/test_manager.py | 13 | 13 |
| tests/risk/test_orchestration.py | 13 | 13 |
| tests/risk/test_risk_models.py | 9 | 9 |
| tests/robinhood_mcp/test_account_resolution.py | 51 | 51 |
| tests/robinhood_mcp/test_adapter.py | 13 | 13 |
| tests/robinhood_mcp/test_historical.py | 60 | 60 |
| tests/robinhood_mcp/test_sdk_transport.py | 23 | 23 |
| tests/robinhood_mcp/test_windows_oauth.py | 1973 | 1973 |
| tests/runtime/checkpoint_runner/test_arch131.py | 78936 | 78936 |
| tests/runtime/checkpoint_runner/test_arch133_a_g.py | 19065 | 19065 |
| tests/runtime/checkpoint_runner/test_arch133_h_k.py | 32425 | 32425 |
| tests/runtime/checkpoint_runner/test_arch133_l_m.py | 82834 | 82834 |
| tests/runtime/checkpoint_runner/test_ci.py | 18008 | 18008 |
| tests/runtime/checkpoint_runner/test_core.py | 3471 | 3471 |
| tests/scripts/certification_runner/test_children.py | 131 | 131 |
| tests/scripts/certification_runner/test_lanes.py | 10075 | 10075 |
| tests/scripts/certification_runner/test_profiles.py | 3074 | 3074 |
| tests/scripts/certification_runner/test_results.py | 5223 | 5223 |
| tests/scripts/certification_runner/test_source.py | 484 | 484 |
| tests/scripts/test_archive_project_history.py | 11407 | 11407 |
| tests/scripts/test_create_walk_forward_research_bundle.py | 4 | 4 |
| tests/scripts/test_research_session_archive_scripts.py | 7 | 7 |
| tests/scripts/test_run_backtest.py | 1785 | 1785 |
| tests/scripts/test_run_historical_experiment.py | 13239 | 13239 |
| tests/scripts/test_run_rolling_historical_simulation.py | 2771 | 2771 |
| tests/scripts/test_run_walk_forward_experiment.py | 9 | 9 |
| tests/simulation/test_optimized_paper_portfolio.py | 98 | 98 |
| tests/simulation/test_paper_portfolio.py | 74 | 74 |
| tests/simulation/test_rolling_historical.py | 104 | 104 |
| tests/strategies/test_moving_average.py | 19 | 19 |
| tests/strategies/test_production_strategy_contract.py | 26033 | 26033 |
| tests/strategies/test_production_strategy_decision.py | 110 | 110 |
| tests/test_config.py | 5 | 5 |
| tests/test_robinhood_forward_paper_cycle.py | 844 | 844 |
| tests/test_robinhood_live_qualification_verifier.py | 1859 | 1859 |
| tests/test_robinhood_paper_cycle.py | 517 | 517 |
| tests/test_robinhood_paper_operator.py | 829 | 829 |
| tests/test_robinhood_paper_pipeline.py | 78 | 78 |
| tests/test_robinhood_prepare_operator.py | 140 | 140 |
| tests/test_robinhood_prepare_qualification_verifier.py | 3974 | 3974 |
| tests/test_robinhood_supervised_qualification.py | 7909 | 7909 |

## Preserved input hashes

These identify the exact evidence read before edits; none is rewritten.

| File | SHA256 |
| --- | --- |
| broad-1.stderr.log | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| broad-1.stdout.log | 172016550a834eb5593648e45e9a5c08ba80ce8cf18824b0ba2b0d9f26861b38 |
| broad-1.xml | 6f1c4eb1580390b3cddb4f59766b27d6e21add76eadffed7bf2f9e9690361c19 |
| broad-2.stderr.log | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| broad-2.stdout.log | a51458551509b72d9cd93b06e42caf6596db8a24b03bc42eecfd57ad1340c377 |
| broad-2.xml | bcce3b287baa9473089a6fa94ff40fb554d965e84dd14aad32e8a11f5ae4ae80 |
| broad-3.stderr.log | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| broad-3.stdout.log | db0322da0bd03746c96fbf1252b3c0e6ea1bbe8e6776c8c320e4c2d933bab5aa |
| broad-3.xml | 410b89892864ac335a27e21e99ab8fe1df44adc163a1ae6c90b7d97ddf28770c |
| broad-4.stderr.log | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| broad-4.stdout.log | 601573e7d1e50d565ca347f4540a010f842f4b633964e71951d4d0a03135c2b6 |
| broad-4.xml | 79f21691de8ae12a6760851586c5f9ac3b457ca7dcdaf7712d04cbb6910ab051 |
| git_diff_check.stderr.log | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| git_diff_check.stdout.log | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| inventory.json | b50acd0eb8c10d382b9662f42bcfc9aec38ae82420d7aa9bf73bc0d00017ceeb |
| results.json | 61cd8f3c53dc7897b8f7836573c9ece22b15733cd3134383b4e7f89bf186027e |
| ruff_check.stderr.log | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| ruff_check.stdout.log | a4443afdcfb6d7363adb285762515ccf7cf50473b1a05c20c1a50f6bed4d26b0 |
| ruff_format.stderr.log | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| ruff_format.stdout.log | 8f0493dbbc55e013dfe720e85947ee81fe18e5aa7012f52579ba69c46de0a110 |

## Authority, verification and publication contract

R4 Administrator-before-latch semantics and both native/product source files
remain byte-identical. R3J/R3K predecessor maps/digests/AST data are frozen.
The minimal R3L overlay replaces current pins only for run_test_certification,
certification helpers and test_lanes; D1S2 None rollback, R3 native pins,
mutable PROJECT_STATUS/HANDOFF, D1S3 registration and mapped ROBINHOOD persist.
Accepted R3K retains its 109-module timing map (856950 ms), four lane counts
27/30/26/26, and all four ordered hashes. FULL ownership remains 198 modules;
LEGACY/EXHAUSTIVE and serial safety do not change. No tests are removed.

Focused verification covers certification test_lanes, test_profiles,
test_results, test_source, changed six-child concurrency tests and affected
checkpoint authority. Fresh external basetemps are required, followed by Ruff
lint/format and diff checks. Final unpublished exact-commit FULL/ROBINHOOD
plan-only runs must match the six-lane model and unchanged accepted R3K model.

R3L is intentionally absent from ACTIVE_CI_CHECKPOINTS and
CI_CERTIFICATION_PROFILES; its one push resolves to no active checkpoint and
uses normal broad fallback source CI. No CI workflow edits or canonical
ROBINHOOD rerun are made. Only terminal-green source CI permits exactly one
canonical local FULL against the exact pushed R3L HEAD/tree, with six children
started before any waits, fresh external evidence and basetemps, exact
pre/post/final source, all 198 modules once, zero failures/errors, static PASS
and wall strictly below 300 seconds. On red or failed FULL, preserve and STOP;
no correction publication, unchanged rerun or automatic seventh lane.

This pre-publication record does not claim R3L source/certification acceptance.
The terminal run identity and canonical FULL evidence belong in the external
implementation handoff for ChatGPT review, without a second publication merely
to record results. If accepted, ChatGPT owns the later D1S3 fast-forward,
mapped ROBINHOOD CI, exact-tree develop integration and docs closeout.
No merge occurs in this task.

Production preflight/execute, installation/publication, successor provisioning,
scheduler access, real credential access, provider requests, paper/broker/D1/D2/
live effects and original-F1/C2 evidence mutations all remain zero. Original F1
is FINAL / INDETERMINATE / CONSUMED; C2 is consumed and immutable; live is NO-GO.

Also remove or update any tests and docs that referenced the old behavior.
