"""Certify supported, Robinhood, legacy, or exhaustive source test profiles."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import tomllib
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

# One current static-toolchain contract shared by local admission and certification.
RUFF_VERSION = "0.17.3"
CANONICAL_RUFF_ROOTS = (".",)


def canonical_ruff_commands(python: str) -> dict[str, list[str]]:
    """Return the complete non-mutating canonical Ruff file universe."""
    return {
        "ruff_check": [
            python,
            "-m",
            "ruff",
            "check",
            "--no-cache",
            *CANONICAL_RUFF_ROOTS,
        ],
        "ruff_format": [
            python,
            "-m",
            "ruff",
            "format",
            "--check",
            "--no-cache",
            *CANONICAL_RUFF_ROOTS,
        ],
    }


def static_toolchain_contract_failures(root: Path) -> tuple[str, ...]:
    """Own current Ruff dependency/install parity independently of historical pins."""
    failures = []
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    dev = project["project"]["optional-dependencies"]["dev"]
    if [item for item in dev if item.startswith("ruff")] != [f"ruff=={RUFF_VERSION}"]:
        failures.append("current development Ruff version drift")
    workflow = (root / ".github/workflows/checkpoint-source-gates.yml").read_text(
        encoding="utf-8"
    )
    if re.findall(r'"(ruff[^"]+)"', workflow) != [f"ruff=={RUFF_VERSION}"] * 5:
        failures.append("current CI Ruff version drift")
    return tuple(failures)


def check_ruff_version(python: str, root: Path) -> dict[str, Any]:
    """Fail closed on unavailable, malformed or mismatched Ruff, without installing."""
    command = [python, "-m", "ruff", "--version"]
    result: dict[str, Any] = {"command": command, "expected": f"ruff {RUFF_VERSION}"}
    try:
        completed = subprocess.run(
            command, cwd=root, text=True, capture_output=True, check=False, timeout=30
        )
        result.update(
            actual=completed.stdout.strip(),
            stdout=completed.stdout,
            stderr=completed.stderr,
            exit_code=(
                0
                if completed.returncode == 0
                and completed.stdout.strip() == result["expected"]
                else 1
            ),
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        result.update(actual="unavailable", error=str(error), exit_code=1)
    return result


SERIAL_MODULES = (
    "tests/runtime/test_windows_transactional_capture_authority.py",
    "tests/runtime/test_windows_authority_schema.py",
    "tests/runtime/test_windows_authority.py",
    "tests/runtime/test_windows_effectful_capture_native_acceptance.py",
    "tests/acceptance/test_windows_authority_provisioning_acceptance.py",
)
PROFILES = ("full", "robinhood", "legacy", "exhaustive")
ROBINHOOD_DIRECTORIES = (
    "tests/domain",
    "tests/execution",
    "tests/ledger",
    "tests/risk",
    "tests/review_paper",
    "tests/robinhood_mcp",
)
ROBINHOOD_LANE_PINS = {
    # Architecture 132-R3H: #553 JUnit timing evidence showed the byte-size
    # proxy co-locating the dominant runtime outliers. Keep exactly two lanes
    # and deterministically separate only these measured modules.
    "tests/runtime/checkpoint_runner/test_arch131.py": 0,
    "tests/runtime/checkpoint_runner/test_arch133_h_k.py": 0,
    "tests/runtime/checkpoint_runner/test_arch133_l_m.py": 1,
    "tests/review_paper/test_arch133_scheduler_installation.py": 1,
}

# F1 C1: canonical #648 measured 199.971/320.334-second lanes. Move only
# the new parent outlier (42.599 summed testcase seconds) to lane 0; retain
# every accepted R3H placement, the two-lane topology and the 300-second gate.
ROBINHOOD_F1_LANE_PINS = {"tests/review_paper/test_five_session_soak.py": 0}

# F1R1-B C2: the canonical C1 run measured the closed-descendant rename
# qualification at 14.399 s in lane 2. Move that reviewed outlier after the
# R3H and F1 placements; retain exact coverage and the 300-second gate.
ROBINHOOD_F1R1_B_LANE_PINS = {
    "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py": 0
}

# D1S3-R1: preserved C2 canonical ROBINHOOD timing measured 237.839/287.630
# summed testcase seconds in robinhood-1/robinhood-2.  Move only the reviewed
# 26.729-second D1 session execution module to lane 0, giving an estimated
# 264.568/260.901 split while retaining the two-lane topology and 300-second
# hygiene ceiling.
ROBINHOOD_D1S3_LANE_PINS = {"tests/review_paper/test_d1_session_execution.py": 0}

# Architecture 132-R3K: positive source-owned ROBINHOOD placement estimates
# normalized from the complete R3J-D1 isolated local diagnostic evidence. The
# raw evidence measured tests/domain/test_positions.py at 0 ms; Architecture
# 132 source timing weights use the reviewed positive 1-ms minimum for such a
# module. Raw evidence total: 856949 ms; canonical source-model total:
# 856950 ms. The sorted compact JSON timing-map SHA256 is
# 0c0c79f710ab8b3a9ffc08de4720c026f257e2ffefc8dc6989c3a70fba2d2898.
# Runtime certification never reads the JUnit artifact or prior CI evidence.
# Keep pairs rather than a dict so duplicate semantic paths fail closed during
# validation.
ROBINHOOD_FALLBACK_MS = 1000  # Placement estimate only; never ownership/exclusion.
ROBINHOOD_MODULE_TIMINGS_MS = (
    ("tests/domain/test_market.py", 2),
    ("tests/domain/test_orders.py", 1),
    ("tests/domain/test_positions.py", 1),
    ("tests/domain/test_proposals.py", 22),
    ("tests/execution/test_execution_models.py", 15),
    ("tests/execution/test_order_engine.py", 19),
    ("tests/execution/test_paper_fill_application.py", 22),
    ("tests/execution/test_paper_fills.py", 20),
    ("tests/execution/test_paper_submission.py", 20),
    ("tests/execution/test_portfolio_orders.py", 16),
    ("tests/ledger/test_checkpoint_state.py", 35),
    ("tests/ledger/test_initialization.py", 5),
    ("tests/ledger/test_ledger.py", 17),
    ("tests/ledger/test_models.py", 2),
    ("tests/review_paper/test_alpaca_authentication_qualification.py", 6950),
    ("tests/review_paper/test_alpaca_credential_generation.py", 6906),
    ("tests/review_paper/test_alpaca_credential_staging_cleanup.py", 4528),
    (
        "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py",
        21185,
    ),
    ("tests/review_paper/test_arch133_fresh_activation_reprovision.py", 14995),
    (
        "tests/review_paper/test_arch133_fresh_activation_reprovision_corrected.py",
        16480,
    ),
    ("tests/review_paper/test_arch133_parent_policy_diagnostic.py", 1515),
    ("tests/review_paper/test_arch133_parent_security_diagnostic.py", 1005),
    ("tests/review_paper/test_arch133_reprovision_admission_diagnostic.py", 468),
    ("tests/review_paper/test_arch133_reprovision_reconciliation.py", 9139),
    ("tests/review_paper/test_arch133_reprovision_recovery.py", 18957),
    ("tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py", 10470),
    ("tests/review_paper/test_arch133_scheduler_installation.py", 45619),
    ("tests/review_paper/test_arch133_windows_rename_qualification.py", 17002),
    ("tests/review_paper/test_arch134_f1r1_a_runtime_isolation.py", 28),
    ("tests/review_paper/test_arch134_f1r1_b_host_qualification.py", 263),
    ("tests/review_paper/test_arch134_f1r1_c1_qualification_operator.py", 22875),
    ("tests/review_paper/test_arch134_f1r1_d1s1_successor_soak.py", 18885),
    ("tests/review_paper/test_arch134_f1r1_d1s2_successor_readiness.py", 2801),
    (
        "tests/review_paper/test_arch134_f1r1_d1s3_successor_installation_operator.py",
        13477,
    ),
    ("tests/review_paper/test_armed_production_paper_session.py", 12529),
    ("tests/review_paper/test_current_production_strategy_decision.py", 1453),
    ("tests/review_paper/test_d1_session_authorization.py", 11007),
    ("tests/review_paper/test_d1_session_execution.py", 88506),
    ("tests/review_paper/test_five_session_soak.py", 86795),
    ("tests/review_paper/test_five_session_soak_child.py", 30761),
    ("tests/review_paper/test_forward_preview.py", 882),
    ("tests/review_paper/test_history_qualification.py", 1122),
    ("tests/review_paper/test_intent_bridge.py", 23),
    ("tests/review_paper/test_nyse_published_regular_sessions.py", 56),
    ("tests/review_paper/test_performance.py", 245),
    ("tests/review_paper/test_post_publication_stage_diagnostic.py", 4798),
    ("tests/review_paper/test_post_publication_verifier.py", 3011),
    ("tests/review_paper/test_pre_market_wake_overnight.py", 14644),
    ("tests/review_paper/test_pre_market_wake_qualification.py", 3418),
    ("tests/review_paper/test_prepare_qualification.py", 821),
    ("tests/review_paper/test_production_paper_runtime.py", 7842),
    ("tests/review_paper/test_production_paper_runtime_acl.py", 15572),
    ("tests/review_paper/test_production_strategy_cycle.py", 103),
    ("tests/review_paper/test_production_strategy_prepare_operator.py", 1687),
    ("tests/review_paper/test_publication_state_paper_corrected.py", 6641),
    ("tests/review_paper/test_publication_state_paper_diagnostic.py", 6010),
    ("tests/review_paper/test_published_session_prepare.py", 338),
    ("tests/review_paper/test_retained_root_acl_recovery.py", 353),
    ("tests/review_paper/test_retained_root_diagnostic.py", 265),
    ("tests/review_paper/test_risk_context.py", 592),
    ("tests/review_paper/test_risk_price_acquisition.py", 459),
    ("tests/review_paper/test_risk_prices.py", 117),
    ("tests/review_paper/test_scratch_root_acl.py", 366),
    ("tests/review_paper/test_session_admission.py", 102),
    ("tests/review_paper/test_store.py", 199),
    ("tests/review_paper/test_strategy_market_history.py", 507),
    ("tests/review_paper/test_supervised_deployment_qualification.py", 8813),
    ("tests/review_paper/test_supervised_forward_paper.py", 767),
    ("tests/review_paper/test_supervised_maintenance_rebind.py", 4484),
    ("tests/review_paper/test_supervised_release_bundle.py", 36842),
    ("tests/review_paper/test_supervised_release_foundation.py", 828),
    ("tests/review_paper/test_supervised_release_installation.py", 1885),
    ("tests/review_paper/test_supervised_release_installation_operator.py", 22280),
    ("tests/review_paper/test_supervised_release_installation_reconciliation.py", 472),
    ("tests/review_paper/test_supervised_release_publication_recovery.py", 4692),
    ("tests/review_paper/test_supervised_runtime_host_admission.py", 2173),
    ("tests/review_paper/test_unattended_activation.py", 233),
    ("tests/review_paper/test_unattended_execution.py", 3847),
    ("tests/review_paper/test_unattended_host.py", 2793),
    ("tests/review_paper/test_unattended_one_wake.py", 3029),
    ("tests/review_paper/test_unattended_publication.py", 2112),
    ("tests/review_paper/test_unattended_state_store.py", 2536),
    ("tests/risk/test_manager.py", 15),
    ("tests/risk/test_orchestration.py", 10),
    ("tests/risk/test_risk_models.py", 6),
    ("tests/robinhood_mcp/test_account_resolution.py", 20),
    ("tests/robinhood_mcp/test_adapter.py", 1),
    ("tests/robinhood_mcp/test_historical.py", 58),
    ("tests/robinhood_mcp/test_sdk_transport.py", 27),
    ("tests/robinhood_mcp/test_windows_oauth.py", 1726),
    ("tests/runtime/checkpoint_runner/test_arch131.py", 63486),
    ("tests/runtime/checkpoint_runner/test_arch133_a_g.py", 17002),
    ("tests/runtime/checkpoint_runner/test_arch133_h_k.py", 28739),
    ("tests/runtime/checkpoint_runner/test_arch133_l_m.py", 67781),
    ("tests/runtime/checkpoint_runner/test_ci.py", 14227),
    ("tests/runtime/checkpoint_runner/test_core.py", 2909),
    ("tests/scripts/certification_runner/test_children.py", 152),
    ("tests/scripts/certification_runner/test_lanes.py", 7310),
    ("tests/scripts/certification_runner/test_profiles.py", 2459),
    ("tests/scripts/certification_runner/test_results.py", 4175),
    ("tests/scripts/certification_runner/test_source.py", 452),
    ("tests/test_robinhood_forward_paper_cycle.py", 440),
    ("tests/test_robinhood_live_qualification_verifier.py", 1216),
    ("tests/test_robinhood_paper_cycle.py", 334),
    ("tests/test_robinhood_paper_operator.py", 723),
    ("tests/test_robinhood_paper_pipeline.py", 90),
    ("tests/test_robinhood_prepare_operator.py", 151),
    ("tests/test_robinhood_prepare_qualification_verifier.py", 3361),
    ("tests/test_robinhood_supervised_qualification.py", 7325),
)

# Architecture 146-B1-C4: canonical FULL #784 / run 40689830781, attempt 1.
# All 209 modules have positive raw JUnit testcase totals: 1749660 ms.
# Sorted compact JSON timing-map SHA256:
# a3b23aab842af7bb042c848b58d8aa0f17704d40937b89d85a3e11c524935710.
# The old R3L map is historical Git evidence, not a second current authority.
# Tuple pairs expose duplicate paths; runtime never reads prior evidence.
FULL_FALLBACK_MS = 1000  # Placement estimate only; never an ownership/exclusion rule.
FULL_MODULE_TIMINGS_MS = (
    ("tests/analytics/test_analyzer.py", 16),
    ("tests/backtesting/test_backtest_engine.py", 29),
    ("tests/backtesting/test_backtest_models.py", 5),
    ("tests/cli/test_create_research_session_bundle.py", 33),
    ("tests/cli/test_historical_experiment.py", 3391),
    ("tests/cli/test_historical_experiment_pairwise_config.py", 22),
    ("tests/cli/test_historical_experiment_pairwise_serialization.py", 81),
    ("tests/cli/test_historical_experiment_pareto_config.py", 7),
    ("tests/cli/test_historical_experiment_pareto_serialization.py", 52),
    ("tests/cli/test_historical_experiment_report_serialization.py", 72),
    ("tests/cli/test_optimized_simulation.py", 11571),
    ("tests/cli/test_research_session_archive.py", 350),
    ("tests/cli/test_research_session_archive_cli.py", 41),
    ("tests/cli/test_research_session_bundle.py", 181),
    ("tests/cli/test_research_session_manifest.py", 32),
    ("tests/cli/test_research_session_restore.py", 267),
    ("tests/cli/test_restore_research_session_archive.py", 72),
    ("tests/cli/test_rolling_historical.py", 211),
    ("tests/cli/test_verify_research_session_manifest.py", 104),
    ("tests/cli/test_walk_forward_aggregate_config.py", 11),
    ("tests/cli/test_walk_forward_aggregate_serialization.py", 262),
    ("tests/cli/test_walk_forward_experiment.py", 841),
    ("tests/cli/test_walk_forward_experiment_config.py", 9),
    ("tests/cli/test_walk_forward_experiment_serialization.py", 194),
    ("tests/cli/test_walk_forward_stability_config.py", 23),
    ("tests/cli/test_walk_forward_stability_serialization.py", 255),
    ("tests/domain/test_market.py", 28),
    ("tests/domain/test_orders.py", 11),
    ("tests/domain/test_positions.py", 8),
    ("tests/domain/test_proposals.py", 2),
    ("tests/execution/test_execution_models.py", 5),
    ("tests/execution/test_order_engine.py", 26),
    ("tests/execution/test_paper_fill_application.py", 42),
    ("tests/execution/test_paper_fills.py", 17),
    ("tests/execution/test_paper_submission.py", 17),
    ("tests/execution/test_portfolio_orders.py", 21),
    ("tests/experiments/test_comparison.py", 96),
    ("tests/experiments/test_grid.py", 83),
    ("tests/experiments/test_historical.py", 805),
    ("tests/experiments/test_historical_research_acquisition_custody.py", 8283),
    ("tests/experiments/test_historical_research_dataset.py", 2323),
    ("tests/experiments/test_pairwise.py", 1522),
    ("tests/experiments/test_pareto.py", 530),
    ("tests/experiments/test_report.py", 829),
    ("tests/experiments/test_research_candidate.py", 1255),
    ("tests/experiments/test_research_candidate_shadow_binding.py", 78694),
    ("tests/experiments/test_research_candidate_shadow_observation.py", 6458),
    ("tests/experiments/test_research_candidate_shadow_qualification.py", 85896),
    ("tests/experiments/test_research_candidate_walk_forward.py", 1993),
    ("tests/experiments/test_research_strategy_backtest.py", 55),
    ("tests/experiments/test_research_strategy_definition.py", 38),
    (
        "tests/experiments/test_research_strategy_f1_paper_evidence_verification.py",
        4065,
    ),
    ("tests/experiments/test_research_strategy_paper_candidate_eligibility.py", 5185),
    ("tests/experiments/test_research_strategy_paper_candidate_eligibility_v2.py", 94),
    ("tests/experiments/test_research_strategy_production_compatibility.py", 5888),
    ("tests/experiments/test_research_strategy_robustness.py", 173),
    ("tests/experiments/test_research_strategy_walk_forward.py", 626),
    ("tests/experiments/test_walk_forward.py", 1090),
    ("tests/experiments/test_walk_forward_analytics.py", 426),
    ("tests/experiments/test_walk_forward_stability.py", 660),
    ("tests/integration/test_walk_forward_e2e.py", 25934),
    ("tests/integration/test_walk_forward_research_archive_e2e.py", 26),
    ("tests/integration/test_walk_forward_research_bundle_e2e.py", 2422),
    ("tests/integration/test_walk_forward_research_restore_e2e.py", 30),
    ("tests/integration/test_walk_forward_research_transport_e2e.py", 298),
    ("tests/ledger/test_checkpoint_state.py", 71),
    ("tests/ledger/test_initialization.py", 35),
    ("tests/ledger/test_ledger.py", 22),
    ("tests/ledger/test_models.py", 6),
    ("tests/market_calendar/test_calendar_models.py", 22),
    ("tests/market_calendar/test_nyse_calendar.py", 25),
    ("tests/market_data/test_csv_historical_provider.py", 150),
    ("tests/market_data/test_historical_models.py", 8),
    ("tests/market_data/test_multi_symbol_models.py", 14),
    ("tests/market_data/test_multi_symbol_provider.py", 10),
    ("tests/multi_backtesting/test_engine.py", 14),
    ("tests/multi_backtesting/test_models.py", 2),
    ("tests/multi_backtesting/test_strategy_contract.py", 2),
    ("tests/optimization/test_cpu_mean_cvar.py", 22),
    ("tests/portfolio/test_historical_scenarios.py", 58),
    ("tests/portfolio/test_mean_cvar.py", 10),
    ("tests/portfolio/test_models.py", 14),
    ("tests/portfolio/test_optimized_targets.py", 41),
    ("tests/portfolio/test_optimizer_protocol.py", 6),
    ("tests/portfolio/test_scenarios.py", 17),
    ("tests/portfolio_analytics/test_analyzer.py", 22),
    ("tests/portfolio_analytics/test_models.py", 2),
    ("tests/portfolio_analytics/test_optimized_simulation.py", 9132),
    ("tests/rebalancing/test_models.py", 7),
    ("tests/rebalancing/test_planner.py", 13),
    ("tests/rebalancing/test_proposals.py", 33),
    ("tests/review_paper/test_alpaca_authentication_qualification.py", 15881),
    ("tests/review_paper/test_alpaca_credential_generation.py", 10399),
    ("tests/review_paper/test_alpaca_credential_staging_cleanup.py", 6140),
    (
        "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py",
        41100,
    ),
    ("tests/review_paper/test_arch133_fresh_activation_reprovision.py", 20028),
    (
        "tests/review_paper/test_arch133_fresh_activation_reprovision_corrected.py",
        24866,
    ),
    ("tests/review_paper/test_arch133_parent_policy_diagnostic.py", 1105),
    ("tests/review_paper/test_arch133_parent_security_diagnostic.py", 665),
    ("tests/review_paper/test_arch133_reprovision_admission_diagnostic.py", 379),
    ("tests/review_paper/test_arch133_reprovision_reconciliation.py", 14408),
    ("tests/review_paper/test_arch133_reprovision_recovery.py", 27066),
    ("tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py", 18279),
    ("tests/review_paper/test_arch133_scheduler_installation.py", 93322),
    ("tests/review_paper/test_arch133_windows_rename_qualification.py", 32375),
    ("tests/review_paper/test_arch134_f1r1_a_runtime_isolation.py", 49),
    ("tests/review_paper/test_arch134_f1r1_b_host_qualification.py", 259),
    ("tests/review_paper/test_arch134_f1r1_c1_qualification_operator.py", 40691),
    ("tests/review_paper/test_arch134_f1r1_d1s1_successor_soak.py", 36919),
    ("tests/review_paper/test_arch134_f1r1_d1s2_successor_readiness.py", 9310),
    (
        "tests/review_paper/test_arch134_f1r1_d1s3_successor_installation_operator.py",
        38573,
    ),
    (
        "tests/review_paper/test_arch134_f1r1_d1s4_r1_shared_namespace_acl_recovery.py",
        7073,
    ),
    (
        "tests/review_paper/test_arch134_f1r1_d1s4_rename_free_direct_installation.py",
        48731,
    ),
    (
        "tests/review_paper/test_arch134_readonly_deployment_admission_diagnostic.py",
        11589,
    ),
    (
        "tests/review_paper/test_arch134_readonly_deployment_admission_diagnostic_r1.py",
        5386,
    ),
    (
        "tests/review_paper/test_arch134_readonly_deployment_admission_diagnostic_r2.py",
        10750,
    ),
    (
        "tests/review_paper/test_arch134_readonly_deployment_admission_diagnostic_r3.py",
        4699,
    ),
    ("tests/review_paper/test_armed_production_paper_session.py", 8977),
    ("tests/review_paper/test_current_production_strategy_decision.py", 1170),
    ("tests/review_paper/test_d1_session_authorization.py", 11149),
    ("tests/review_paper/test_d1_session_execution.py", 54446),
    ("tests/review_paper/test_five_session_soak.py", 91439),
    ("tests/review_paper/test_five_session_soak_child.py", 21062),
    ("tests/review_paper/test_forward_preview.py", 439),
    ("tests/review_paper/test_history_qualification.py", 1108),
    ("tests/review_paper/test_intent_bridge.py", 38),
    ("tests/review_paper/test_nyse_published_regular_sessions.py", 229),
    ("tests/review_paper/test_performance.py", 177),
    ("tests/review_paper/test_post_publication_stage_diagnostic.py", 2913),
    ("tests/review_paper/test_post_publication_verifier.py", 2473),
    ("tests/review_paper/test_pre_market_wake_overnight.py", 24602),
    ("tests/review_paper/test_pre_market_wake_qualification.py", 2847),
    ("tests/review_paper/test_prepare_qualification.py", 480),
    ("tests/review_paper/test_production_paper_runtime.py", 4154),
    ("tests/review_paper/test_production_paper_runtime_acl.py", 6631),
    ("tests/review_paper/test_production_strategy_cycle.py", 93),
    ("tests/review_paper/test_production_strategy_prepare_operator.py", 3265),
    ("tests/review_paper/test_publication_state_paper_corrected.py", 2982),
    ("tests/review_paper/test_publication_state_paper_diagnostic.py", 3617),
    ("tests/review_paper/test_published_session_prepare.py", 264),
    ("tests/review_paper/test_retained_root_acl_recovery.py", 436),
    ("tests/review_paper/test_retained_root_diagnostic.py", 206),
    ("tests/review_paper/test_risk_context.py", 299),
    ("tests/review_paper/test_risk_price_acquisition.py", 424),
    ("tests/review_paper/test_risk_prices.py", 154),
    ("tests/review_paper/test_scratch_root_acl.py", 300),
    ("tests/review_paper/test_session_admission.py", 152),
    ("tests/review_paper/test_store.py", 144),
    ("tests/review_paper/test_strategy_market_history.py", 255),
    ("tests/review_paper/test_successor_publication_recovery.py", 4112),
    ("tests/review_paper/test_supervised_deployment_qualification.py", 21875),
    ("tests/review_paper/test_supervised_forward_paper.py", 530),
    ("tests/review_paper/test_supervised_maintenance_rebind.py", 7017),
    ("tests/review_paper/test_supervised_release_bundle.py", 133531),
    ("tests/review_paper/test_supervised_release_foundation.py", 868),
    ("tests/review_paper/test_supervised_release_installation.py", 4329),
    ("tests/review_paper/test_supervised_release_installation_operator.py", 41335),
    ("tests/review_paper/test_supervised_release_installation_reconciliation.py", 189),
    ("tests/review_paper/test_supervised_release_publication_recovery.py", 4329),
    ("tests/review_paper/test_supervised_runtime_host_admission.py", 4019),
    ("tests/review_paper/test_unattended_activation.py", 319),
    ("tests/review_paper/test_unattended_execution.py", 2862),
    ("tests/review_paper/test_unattended_host.py", 1235),
    ("tests/review_paper/test_unattended_one_wake.py", 3416),
    ("tests/review_paper/test_unattended_publication.py", 1130),
    ("tests/review_paper/test_unattended_state_store.py", 2057),
    ("tests/risk/test_manager.py", 12),
    ("tests/risk/test_orchestration.py", 20),
    ("tests/risk/test_risk_models.py", 16),
    ("tests/robinhood_mcp/test_account_resolution.py", 57),
    ("tests/robinhood_mcp/test_adapter.py", 9),
    ("tests/robinhood_mcp/test_historical.py", 66),
    ("tests/robinhood_mcp/test_sdk_transport.py", 81),
    ("tests/robinhood_mcp/test_windows_oauth.py", 3748),
    ("tests/runtime/checkpoint_runner/test_arch131.py", 105958),
    ("tests/runtime/checkpoint_runner/test_arch133_a_g.py", 20224),
    ("tests/runtime/checkpoint_runner/test_arch133_h_k.py", 41120),
    ("tests/runtime/checkpoint_runner/test_arch133_l_m.py", 120585),
    ("tests/runtime/checkpoint_runner/test_ci.py", 55338),
    ("tests/runtime/checkpoint_runner/test_core.py", 6426),
    ("tests/runtime/checkpoint_runner/test_r3m_c2.py", 1037),
    ("tests/runtime/checkpoint_runner/test_source_authority.py", 32277),
    ("tests/scripts/certification_runner/test_children.py", 86),
    ("tests/scripts/certification_runner/test_lanes.py", 19409),
    ("tests/scripts/certification_runner/test_profiles.py", 5209),
    ("tests/scripts/certification_runner/test_results.py", 5445),
    ("tests/scripts/certification_runner/test_source.py", 502),
    ("tests/scripts/test_archive_project_history.py", 19670),
    ("tests/scripts/test_create_walk_forward_research_bundle.py", 10),
    ("tests/scripts/test_research_session_archive_scripts.py", 7),
    ("tests/scripts/test_run_backtest.py", 1162),
    ("tests/scripts/test_run_historical_experiment.py", 11118),
    ("tests/scripts/test_run_rolling_historical_simulation.py", 2185),
    ("tests/scripts/test_run_walk_forward_experiment.py", 13),
    ("tests/simulation/test_optimized_paper_portfolio.py", 102),
    ("tests/simulation/test_paper_portfolio.py", 121),
    ("tests/simulation/test_rolling_historical.py", 193),
    ("tests/strategies/test_moving_average.py", 12),
    ("tests/strategies/test_production_strategy_contract.py", 23997),
    ("tests/strategies/test_production_strategy_decision.py", 57),
    ("tests/test_config.py", 21),
    ("tests/test_robinhood_forward_paper_cycle.py", 286),
    ("tests/test_robinhood_live_qualification_verifier.py", 547),
    ("tests/test_robinhood_paper_cycle.py", 199),
    ("tests/test_robinhood_paper_operator.py", 707),
    ("tests/test_robinhood_paper_pipeline.py", 105),
    ("tests/test_robinhood_prepare_operator.py", 102),
    ("tests/test_robinhood_prepare_qualification_verifier.py", 1686),
    ("tests/test_robinhood_supervised_qualification.py", 5771),
)

ROBINHOOD_INFRASTRUCTURE_MODULES = (
    "tests/runtime/checkpoint_runner/test_arch131.py",
    "tests/runtime/checkpoint_runner/test_arch133_a_g.py",
    "tests/runtime/checkpoint_runner/test_arch133_h_k.py",
    "tests/runtime/checkpoint_runner/test_arch133_l_m.py",
    "tests/runtime/checkpoint_runner/test_ci.py",
    "tests/runtime/checkpoint_runner/test_core.py",
    "tests/scripts/certification_runner/test_children.py",
    "tests/scripts/certification_runner/test_lanes.py",
    "tests/scripts/certification_runner/test_profiles.py",
    "tests/scripts/certification_runner/test_results.py",
    "tests/scripts/certification_runner/test_source.py",
    "tests/runtime/checkpoint_runner/test_source_authority.py",
)
# Frozen Architecture 132 baseline at accepted HEAD:
# 69327a7d5fbea7499329902ff96fd98e77a62591.
ROBINHOOD_REQUIRED_MODULES = (
    "tests/domain/test_market.py",
    "tests/domain/test_orders.py",
    "tests/domain/test_positions.py",
    "tests/domain/test_proposals.py",
    "tests/execution/test_execution_models.py",
    "tests/execution/test_order_engine.py",
    "tests/execution/test_paper_fill_application.py",
    "tests/execution/test_paper_fills.py",
    "tests/execution/test_paper_submission.py",
    "tests/execution/test_portfolio_orders.py",
    "tests/ledger/test_checkpoint_state.py",
    "tests/ledger/test_initialization.py",
    "tests/ledger/test_ledger.py",
    "tests/ledger/test_models.py",
    "tests/review_paper/test_forward_preview.py",
    "tests/review_paper/test_intent_bridge.py",
    "tests/review_paper/test_nyse_published_regular_sessions.py",
    "tests/review_paper/test_performance.py",
    "tests/review_paper/test_prepare_qualification.py",
    "tests/review_paper/test_risk_context.py",
    "tests/review_paper/test_risk_price_acquisition.py",
    "tests/review_paper/test_risk_prices.py",
    "tests/review_paper/test_session_admission.py",
    "tests/review_paper/test_store.py",
    "tests/review_paper/test_supervised_forward_paper.py",
    "tests/risk/test_manager.py",
    "tests/risk/test_orchestration.py",
    "tests/risk/test_risk_models.py",
    "tests/robinhood_mcp/test_account_resolution.py",
    "tests/robinhood_mcp/test_adapter.py",
    "tests/robinhood_mcp/test_sdk_transport.py",
    "tests/robinhood_mcp/test_windows_oauth.py",
    "tests/runtime/checkpoint_runner/test_arch131.py",
    "tests/runtime/checkpoint_runner/test_arch133_a_g.py",
    "tests/runtime/checkpoint_runner/test_arch133_h_k.py",
    "tests/runtime/checkpoint_runner/test_arch133_l_m.py",
    "tests/runtime/checkpoint_runner/test_ci.py",
    "tests/runtime/checkpoint_runner/test_core.py",
    "tests/scripts/certification_runner/test_children.py",
    "tests/scripts/certification_runner/test_lanes.py",
    "tests/scripts/certification_runner/test_profiles.py",
    "tests/scripts/certification_runner/test_results.py",
    "tests/scripts/certification_runner/test_source.py",
    "tests/test_robinhood_forward_paper_cycle.py",
    "tests/test_robinhood_live_qualification_verifier.py",
    "tests/test_robinhood_paper_cycle.py",
    "tests/test_robinhood_paper_operator.py",
    "tests/test_robinhood_paper_pipeline.py",
    "tests/test_robinhood_prepare_qualification_verifier.py",
)
FULL_DIRECTORIES = (
    "tests/analytics",
    "tests/backtesting",
    "tests/domain",
    "tests/execution",
    "tests/experiments",
    "tests/integration",
    "tests/ledger",
    "tests/market_calendar",
    "tests/multi_backtesting",
    "tests/optimization",
    "tests/portfolio",
    "tests/portfolio_analytics",
    "tests/rebalancing",
    "tests/review_paper",
    "tests/risk",
    "tests/robinhood_mcp",
    "tests/simulation",
    "tests/strategies",
)
FULL_EXACT_MODULES = (
    "tests/cli/test_create_research_session_bundle.py",
    "tests/cli/test_historical_experiment.py",
    "tests/cli/test_historical_experiment_pairwise_config.py",
    "tests/cli/test_historical_experiment_pairwise_serialization.py",
    "tests/cli/test_historical_experiment_pareto_config.py",
    "tests/cli/test_historical_experiment_pareto_serialization.py",
    "tests/cli/test_historical_experiment_report_serialization.py",
    "tests/cli/test_optimized_simulation.py",
    "tests/cli/test_research_session_archive.py",
    "tests/cli/test_research_session_archive_cli.py",
    "tests/cli/test_research_session_bundle.py",
    "tests/cli/test_research_session_manifest.py",
    "tests/cli/test_research_session_restore.py",
    "tests/cli/test_restore_research_session_archive.py",
    "tests/cli/test_rolling_historical.py",
    "tests/cli/test_verify_research_session_manifest.py",
    "tests/cli/test_walk_forward_aggregate_config.py",
    "tests/cli/test_walk_forward_aggregate_serialization.py",
    "tests/cli/test_walk_forward_experiment.py",
    "tests/cli/test_walk_forward_experiment_config.py",
    "tests/cli/test_walk_forward_experiment_serialization.py",
    "tests/cli/test_walk_forward_stability_config.py",
    "tests/cli/test_walk_forward_stability_serialization.py",
    "tests/market_data/test_csv_historical_provider.py",
    "tests/market_data/test_historical_models.py",
    "tests/market_data/test_multi_symbol_models.py",
    "tests/market_data/test_multi_symbol_provider.py",
    "tests/runtime/checkpoint_runner/test_arch131.py",
    "tests/runtime/checkpoint_runner/test_arch133_a_g.py",
    "tests/runtime/checkpoint_runner/test_arch133_h_k.py",
    "tests/runtime/checkpoint_runner/test_arch133_l_m.py",
    "tests/runtime/checkpoint_runner/test_ci.py",
    "tests/runtime/checkpoint_runner/test_core.py",
    "tests/runtime/checkpoint_runner/test_arch147.py",
    "tests/runtime/checkpoint_runner/test_r3m_c2.py",
    "tests/scripts/certification_runner/test_children.py",
    "tests/scripts/certification_runner/test_lanes.py",
    "tests/scripts/certification_runner/test_profiles.py",
    "tests/scripts/certification_runner/test_results.py",
    "tests/scripts/certification_runner/test_source.py",
    "tests/scripts/test_archive_project_history.py",
    "tests/scripts/test_create_walk_forward_research_bundle.py",
    "tests/scripts/test_research_session_archive_scripts.py",
    "tests/scripts/test_run_backtest.py",
    "tests/scripts/test_run_historical_experiment.py",
    "tests/scripts/test_run_rolling_historical_simulation.py",
    "tests/scripts/test_run_walk_forward_experiment.py",
    "tests/test_config.py",
    "tests/runtime/checkpoint_runner/test_source_authority.py",
)
# Frozen supported baseline at Architecture 132-R1 startup HEAD:
# 2577225dafcff2d616fcbf018d7045aebaab1ff5.
FULL_REQUIRED_MODULES = (
    "tests/analytics/test_analyzer.py",
    "tests/backtesting/test_backtest_engine.py",
    "tests/backtesting/test_backtest_models.py",
    "tests/cli/test_create_research_session_bundle.py",
    "tests/cli/test_historical_experiment.py",
    "tests/cli/test_historical_experiment_pairwise_config.py",
    "tests/cli/test_historical_experiment_pairwise_serialization.py",
    "tests/cli/test_historical_experiment_pareto_config.py",
    "tests/cli/test_historical_experiment_pareto_serialization.py",
    "tests/cli/test_historical_experiment_report_serialization.py",
    "tests/cli/test_optimized_simulation.py",
    "tests/cli/test_research_session_archive.py",
    "tests/cli/test_research_session_archive_cli.py",
    "tests/cli/test_research_session_bundle.py",
    "tests/cli/test_research_session_manifest.py",
    "tests/cli/test_research_session_restore.py",
    "tests/cli/test_restore_research_session_archive.py",
    "tests/cli/test_rolling_historical.py",
    "tests/cli/test_verify_research_session_manifest.py",
    "tests/cli/test_walk_forward_aggregate_config.py",
    "tests/cli/test_walk_forward_aggregate_serialization.py",
    "tests/cli/test_walk_forward_experiment.py",
    "tests/cli/test_walk_forward_experiment_config.py",
    "tests/cli/test_walk_forward_experiment_serialization.py",
    "tests/cli/test_walk_forward_stability_config.py",
    "tests/cli/test_walk_forward_stability_serialization.py",
    "tests/domain/test_market.py",
    "tests/domain/test_orders.py",
    "tests/domain/test_positions.py",
    "tests/domain/test_proposals.py",
    "tests/execution/test_execution_models.py",
    "tests/execution/test_order_engine.py",
    "tests/execution/test_paper_fill_application.py",
    "tests/execution/test_paper_fills.py",
    "tests/execution/test_paper_submission.py",
    "tests/execution/test_portfolio_orders.py",
    "tests/experiments/test_comparison.py",
    "tests/experiments/test_grid.py",
    "tests/experiments/test_historical.py",
    "tests/experiments/test_pairwise.py",
    "tests/experiments/test_pareto.py",
    "tests/experiments/test_report.py",
    "tests/experiments/test_walk_forward.py",
    "tests/experiments/test_walk_forward_analytics.py",
    "tests/experiments/test_walk_forward_stability.py",
    "tests/integration/test_walk_forward_e2e.py",
    "tests/integration/test_walk_forward_research_archive_e2e.py",
    "tests/integration/test_walk_forward_research_bundle_e2e.py",
    "tests/integration/test_walk_forward_research_restore_e2e.py",
    "tests/integration/test_walk_forward_research_transport_e2e.py",
    "tests/ledger/test_checkpoint_state.py",
    "tests/ledger/test_initialization.py",
    "tests/ledger/test_ledger.py",
    "tests/ledger/test_models.py",
    "tests/market_calendar/test_calendar_models.py",
    "tests/market_calendar/test_nyse_calendar.py",
    "tests/market_data/test_csv_historical_provider.py",
    "tests/market_data/test_historical_models.py",
    "tests/market_data/test_multi_symbol_models.py",
    "tests/market_data/test_multi_symbol_provider.py",
    "tests/multi_backtesting/test_engine.py",
    "tests/multi_backtesting/test_models.py",
    "tests/multi_backtesting/test_strategy_contract.py",
    "tests/optimization/test_cpu_mean_cvar.py",
    "tests/portfolio/test_historical_scenarios.py",
    "tests/portfolio/test_mean_cvar.py",
    "tests/portfolio/test_models.py",
    "tests/portfolio/test_optimized_targets.py",
    "tests/portfolio/test_optimizer_protocol.py",
    "tests/portfolio/test_scenarios.py",
    "tests/portfolio_analytics/test_analyzer.py",
    "tests/portfolio_analytics/test_models.py",
    "tests/portfolio_analytics/test_optimized_simulation.py",
    "tests/rebalancing/test_models.py",
    "tests/rebalancing/test_planner.py",
    "tests/rebalancing/test_proposals.py",
    "tests/review_paper/test_forward_preview.py",
    "tests/review_paper/test_intent_bridge.py",
    "tests/review_paper/test_nyse_published_regular_sessions.py",
    "tests/review_paper/test_performance.py",
    "tests/review_paper/test_prepare_qualification.py",
    "tests/review_paper/test_risk_context.py",
    "tests/review_paper/test_risk_price_acquisition.py",
    "tests/review_paper/test_risk_prices.py",
    "tests/review_paper/test_session_admission.py",
    "tests/review_paper/test_store.py",
    "tests/review_paper/test_supervised_forward_paper.py",
    "tests/risk/test_manager.py",
    "tests/risk/test_orchestration.py",
    "tests/risk/test_risk_models.py",
    "tests/robinhood_mcp/test_account_resolution.py",
    "tests/robinhood_mcp/test_adapter.py",
    "tests/robinhood_mcp/test_sdk_transport.py",
    "tests/robinhood_mcp/test_windows_oauth.py",
    "tests/runtime/checkpoint_runner/test_arch131.py",
    "tests/runtime/checkpoint_runner/test_arch133_a_g.py",
    "tests/runtime/checkpoint_runner/test_arch133_h_k.py",
    "tests/runtime/checkpoint_runner/test_arch133_l_m.py",
    "tests/runtime/checkpoint_runner/test_ci.py",
    "tests/runtime/checkpoint_runner/test_core.py",
    "tests/scripts/certification_runner/test_children.py",
    "tests/scripts/certification_runner/test_lanes.py",
    "tests/scripts/certification_runner/test_profiles.py",
    "tests/scripts/certification_runner/test_results.py",
    "tests/scripts/certification_runner/test_source.py",
    "tests/scripts/test_create_walk_forward_research_bundle.py",
    "tests/scripts/test_research_session_archive_scripts.py",
    "tests/scripts/test_run_backtest.py",
    "tests/scripts/test_run_historical_experiment.py",
    "tests/scripts/test_run_rolling_historical_simulation.py",
    "tests/scripts/test_run_walk_forward_experiment.py",
    "tests/simulation/test_optimized_paper_portfolio.py",
    "tests/simulation/test_paper_portfolio.py",
    "tests/simulation/test_rolling_historical.py",
    "tests/strategies/test_moving_average.py",
    "tests/test_config.py",
    "tests/test_robinhood_forward_paper_cycle.py",
    "tests/test_robinhood_live_qualification_verifier.py",
    "tests/test_robinhood_paper_cycle.py",
    "tests/test_robinhood_paper_operator.py",
    "tests/test_robinhood_paper_pipeline.py",
    "tests/test_robinhood_prepare_qualification_verifier.py",
)
LEGACY_DIRECTORIES = (
    "tests/acceptance",
    "tests/gui",
    "tests/runtime",
)
LEGACY_REQUIRED_MODULES = (
    "tests/runtime/checkpoint_runner/test_retained_arch128_130.py",
)
LEGACY_EXACT_MODULES = (
    *LEGACY_REQUIRED_MODULES,
    "tests/cli/test_checkpoint_lineage.py",
    "tests/cli/test_checkpoint_transition.py",
    "tests/cli/test_daily_snapshot_capture.py",
    "tests/cli/test_daily_snapshot_config.py",
    "tests/cli/test_paper_operation_config.py",
    "tests/cli/test_paper_operation_execution.py",
    "tests/cli/test_paper_operation_failed_receipt.py",
    "tests/cli/test_paper_operation_inspection.py",
    "tests/cli/test_paper_operation_receipt_output.py",
    "tests/cli/test_pd2d1_b1_readonly_diagnostic.py",
    "tests/cli/test_pd2d1_first_paper_qualification.py",
    "tests/cli/test_pd2d1_p1_readonly_diagnostic.py",
    "tests/cli/test_pd2d1_preparation_readonly_diagnostic.py",
    "tests/cli/test_pd2d2_first_paper_execution.py",
    "tests/cli/test_pd2d2_post_mutation_reconciliation.py",
    "tests/cli/test_pd3_read_only_recovery_launcher.py",
    "tests/cli/test_pd3_read_only_recovery_validation.py",
    "tests/cli/test_pd4_operator_observability_snapshot.py",
    "tests/cli/test_pd4_operator_observability_source_launcher.py",
    "tests/cli/test_pd4_read_only_decision_qualification.py",
    "tests/cli/test_pd4_read_only_decision_reconciliation.py",
    "tests/cli/test_pd4_read_only_settlement_qualification.py",
    "tests/cli/test_pd4_read_only_settlement_reconciliation.py",
    "tests/cli/test_pd4_read_only_single_deferred_settlement_qualification.py",
    "tests/cli/test_pd4_read_only_single_deferred_settlement_reconciliation.py",
    "tests/cli/test_pd4_read_only_unattended_validation.py",
    "tests/cli/test_pd4_single_deferred_settlement_execution.py",
    "tests/cli/test_pd4_unattended_settlement_execution.py",
    "tests/cli/test_personal_desktop_unattended_capture_warmup_launcher.py",
    "tests/cli/test_personal_desktop_unattended_decision_publication_launcher.py",
    "tests/cli/test_personal_desktop_unattended_paper_launcher.py",
    "tests/cli/test_production_daily_snapshot_capture.py",
    "tests/cli/test_verified_snapshot_paper_cycle.py",
    "tests/cli/test_windows_authority.py",
    "tests/market_data/test_alpaca_daily_snapshot.py",
    "tests/market_data/test_alpaca_http.py",
    "tests/market_data/test_daily_snapshot_acceptance.py",
    "tests/market_data/test_daily_snapshot_identity.py",
    "tests/market_data/test_daily_snapshot_models.py",
    "tests/market_data/test_daily_snapshot_provider.py",
    "tests/market_data/test_daily_snapshot_serialization.py",
    "tests/market_data/test_daily_snapshot_verification.py",
    "tests/scripts/test_capture_daily_market_snapshot.py",
)
PROTECTED_OPT_INS = (
    "AI_TRADING_BOT_RUN_WINDOWS_AUTHORITY_ACCEPTANCE",
    "AI_TRADING_BOT_RUN_WINDOWS_NATIVE_TESTS",
    "AI_TRADING_BOT_RUN_C3_E1_NATIVE_ACCEPTANCE",
    "AI_TRADING_BOT_RUN_C3_E37_PUBLICATION_ACCEPTANCE",
)
DEFAULT_TEMP_ROOT = Path(r"F:\AI\temp\pytest")


class CertificationError(RuntimeError):
    """A certification precondition or result failed."""


def reject_protected_opt_ins(environment: dict[str, str]) -> None:
    """Refuse any present protected opt-in, even if set to a false-looking value."""
    active = [name for name in PROTECTED_OPT_INS if name in environment]
    if active:
        raise CertificationError(f"Protected test opt-ins are set: {', '.join(active)}")


def discover_inventory(root: Path) -> tuple[str, ...]:
    """Discover every repository test module in stable relative-path order."""
    return tuple(
        sorted(
            path.relative_to(root).as_posix()
            for path in (root / "tests").rglob("test_*.py")
            if path.is_file()
        )
    )


def separate_serial(
    inventory: tuple[str, ...], serial: tuple[str, ...] = SERIAL_MODULES
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Separate the explicit safety allowlist from the broad inventory."""
    if len(inventory) != len(set(inventory)) or len(serial) != len(set(serial)):
        raise CertificationError(
            "Duplicate test module in inventory or serial allowlist"
        )
    missing = set(serial) - set(inventory)
    if missing:
        raise CertificationError(f"Missing serial safety modules: {sorted(missing)}")
    broad = tuple(module for module in inventory if module not in set(serial))
    validate_partitions(inventory, (broad, serial))
    return broad, serial


def balance_broad(
    root: Path, broad: tuple[str, ...]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Assign whole files by descending size, with stable path and lane ties."""
    lanes: list[list[str]] = [[], []]
    weights = [0, 0]
    for module in sorted(broad, key=lambda name: (-(root / name).stat().st_size, name)):
        lane = 0 if weights[0] <= weights[1] else 1
        lanes[lane].append(module)
        weights[lane] += (root / module).stat().st_size
    return tuple(lanes[0]), tuple(lanes[1])


def full_module_weights(inventory: tuple[str, ...]) -> dict[str, int]:
    """Validate frozen timings against selected FULL, then admit fallback weights."""
    if type(FULL_MODULE_TIMINGS_MS) is not tuple:
        raise CertificationError("Malformed FULL timing table")
    if len(inventory) != len(set(inventory)):
        raise CertificationError("Duplicate FULL module")
    if type(FULL_FALLBACK_MS) is not int or FULL_FALLBACK_MS <= 0:
        raise CertificationError("FULL fallback must be a positive integer")
    timings: dict[str, int] = {}
    for entry in FULL_MODULE_TIMINGS_MS:
        if type(entry) is not tuple or len(entry) != 2:
            raise CertificationError("Malformed FULL timing entry")
        module, weight = entry
        if type(module) is not str or not re.fullmatch(
            r"tests/(?:[a-z0-9_]+/)*test_[a-z0-9_]+\.py", module
        ):
            raise CertificationError("Noncanonical FULL timing module path")
        if module in timings:
            raise CertificationError("Duplicate FULL timing module path")
        if type(weight) is not int or weight <= 0:
            raise CertificationError("FULL timing weights must be positive integers")
        if module not in inventory:
            raise CertificationError(f"Stale FULL timing module: {module}")
        timings[module] = weight
    return {module: timings.get(module, FULL_FALLBACK_MS) for module in inventory}


def robinhood_module_weights(inventory: tuple[str, ...]) -> dict[str, int]:
    """Validate frozen ROBINHOOD timings, admitting future modules by fallback."""
    if type(ROBINHOOD_MODULE_TIMINGS_MS) is not tuple:
        raise CertificationError("Malformed ROBINHOOD timing table")
    if len(inventory) != len(set(inventory)):
        raise CertificationError("Duplicate Robinhood module")
    timings: dict[str, int] = {}
    for entry in ROBINHOOD_MODULE_TIMINGS_MS:
        if type(entry) is not tuple or len(entry) != 2:
            raise CertificationError("Malformed ROBINHOOD timing entry")
        module, weight = entry
        if type(module) is not str or not re.fullmatch(
            r"tests/(?:[a-z0-9_]+/)*test_[a-z0-9_]+\.py", module
        ):
            raise CertificationError("Noncanonical ROBINHOOD timing module path")
        if module in timings:
            raise CertificationError("Duplicate ROBINHOOD timing module path")
        if type(weight) is not int or weight <= 0:
            raise CertificationError(
                "ROBINHOOD timing weights must be positive integers"
            )
        if module not in inventory:
            raise CertificationError(f"Stale ROBINHOOD timing module: {module}")
        timings[module] = weight
    if type(ROBINHOOD_FALLBACK_MS) is not int or ROBINHOOD_FALLBACK_MS <= 0:
        raise CertificationError("ROBINHOOD fallback must be a positive integer")
    return {module: timings.get(module, ROBINHOOD_FALLBACK_MS) for module in inventory}


def balance_robinhood(
    inventory: tuple[str, ...],
) -> tuple[tuple[str, ...], ...]:
    """Place whole ROBINHOOD modules into four timing-aware lanes."""
    weights = robinhood_module_weights(inventory)
    lanes: list[list[str]] = [[], [], [], []]
    totals = [0, 0, 0, 0]
    for module in sorted(inventory, key=lambda name: (-weights[name], name)):
        index = min(range(4), key=lambda lane: (totals[lane], lane))
        lanes[index].append(module)
        totals[index] += weights[module]
    return tuple(tuple(lane) for lane in lanes)


def balance_full(inventory: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    """Place whole FULL modules into seven frozen timing-aware lanes."""
    weights = full_module_weights(inventory)
    lanes: list[list[str]] = [[] for _ in range(7)]
    totals = [0] * 7
    for module in sorted(inventory, key=lambda name: (-weights[name], name)):
        index = min(range(7), key=lambda lane: (totals[lane], lane))
        lanes[index].append(module)
        totals[index] += weights[module]
    return tuple(tuple(lane) for lane in lanes)


def apply_lane_pins(
    lanes: tuple[tuple[str, ...], tuple[str, ...]],
    pins: dict[str, int],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Apply deterministic reviewed lane placement without changing coverage."""
    if any(type(lane) is not int or lane not in {0, 1} for lane in pins.values()):
        raise CertificationError("Lane pins must select lane 0 or 1")
    mutable = [list(lanes[0]), list(lanes[1])]
    assigned = {module for lane in lanes for module in lane}
    for module, target in sorted(pins.items()):
        if module not in assigned:
            continue
        for lane in mutable:
            if module in lane:
                lane.remove(module)
        mutable[target].append(module)
    return tuple(mutable[0]), tuple(mutable[1])


def validate_partitions(
    inventory: tuple[str, ...], lanes: tuple[tuple[str, ...], ...]
) -> None:
    """Require an exact, disjoint assignment of all discovered modules."""
    assigned = [module for lane in lanes for module in lane]
    if len(inventory) != len(set(inventory)) or len(assigned) != len(set(assigned)):
        raise CertificationError("Duplicate or overlapping test modules")
    if set(assigned) != set(inventory):
        missing = sorted(set(inventory) - set(assigned))
        extra = sorted(set(assigned) - set(inventory))
        raise CertificationError(
            f"Incomplete partition: missing={missing}, extra={extra}"
        )


def validate_classification(
    repository: tuple[str, ...], profiles: dict[str, tuple[str, ...]]
) -> None:
    """Fail closed unless all reviewed support-status invariants hold."""
    if set(profiles) != set(PROFILES):
        raise CertificationError("Incomplete certification profile classification")
    if profiles["exhaustive"] != repository:
        raise CertificationError("Exhaustive inventory must equal repository inventory")
    validate_partitions(repository, (profiles["full"], profiles["legacy"]))
    robinhood = profiles["robinhood"]
    if len(robinhood) != len(set(robinhood)):
        raise CertificationError("Duplicate Robinhood module")
    if not set(robinhood) <= set(profiles["full"]):
        raise CertificationError("Robinhood inventory must be a subset of FULL")
    for label, required, selected in (
        ("Robinhood", ROBINHOOD_REQUIRED_MODULES, robinhood),
        ("supported FULL", FULL_REQUIRED_MODULES, profiles["full"]),
    ):
        missing = set(required) - set(selected)
        if missing:
            raise CertificationError(
                f"Missing required {label} modules: {sorted(missing)}"
            )


def classify_inventory(inventory: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    """Admit only reviewed supported or legacy ownership for every profile."""
    for label, required in (
        ("Robinhood", ROBINHOOD_REQUIRED_MODULES),
        ("supported FULL", FULL_REQUIRED_MODULES),
    ):
        missing = set(required) - set(inventory)
        if missing:
            raise CertificationError(
                f"Missing required {label} modules: {sorted(missing)}"
            )
    full: list[str] = []
    legacy: list[str] = []
    robinhood: list[str] = []
    for module in inventory:
        supported = (
            any(module.startswith(f"{directory}/") for directory in FULL_DIRECTORIES)
            or module in FULL_EXACT_MODULES
            or (
                Path(module).parent.as_posix() == "tests"
                and Path(module).match("test_robinhood_*.py")
            )
        )
        historical = module in LEGACY_EXACT_MODULES or (
            any(module.startswith(f"{directory}/") for directory in LEGACY_DIRECTORIES)
            and not module.startswith("tests/runtime/checkpoint_runner/")
            and module not in FULL_EXACT_MODULES
        )
        if supported and historical:
            raise CertificationError(
                f"Overlapping supported/legacy ownership: {module}"
            )
        if not supported and not historical:
            raise CertificationError(f"Unclassified test module: {module}")
        (full if supported else legacy).append(module)
        if (
            Path(module).parent.as_posix() in ROBINHOOD_DIRECTORIES
            or (
                Path(module).parent.as_posix() == "tests"
                and Path(module).match("test_robinhood_*.py")
            )
            or module in ROBINHOOD_INFRASTRUCTURE_MODULES
        ):
            robinhood.append(module)
    profiles = {
        "full": tuple(full),
        "robinhood": tuple(robinhood),
        "legacy": tuple(legacy),
        "exhaustive": inventory,
    }
    validate_classification(inventory, profiles)
    return profiles


def select_inventory(inventory: tuple[str, ...], profile: str) -> tuple[str, ...]:
    """Select one profile from the fully admitted repository inventory."""
    if profile not in PROFILES:
        raise CertificationError(f"Unknown certification profile: {profile}")
    selected = classify_inventory(inventory)[profile]
    _validate_legacy_required(selected, profile)
    return selected


def _validate_legacy_required(selected: tuple[str, ...], profile: str) -> None:
    """Preserve the relocated retained baseline at every profile admission path."""
    if profile in {"legacy", "exhaustive"}:
        missing = set(LEGACY_REQUIRED_MODULES) - set(selected)
        if missing:
            raise CertificationError(
                f"Missing required LEGACY modules: {sorted(missing)}"
            )


def build_lanes(
    root: Path, inventory: tuple[str, ...], profile: str
) -> dict[str, tuple[str, ...]]:
    """Partition the selected inventory into the profile's exact nonempty lanes."""
    if profile in {"legacy", "exhaustive"}:
        broad, serial = separate_serial(inventory, SERIAL_MODULES)
        first, second = balance_broad(root, broad)
        prefix = "legacy" if profile == "legacy" else "broad"
        lanes = {f"{prefix}-1": first, f"{prefix}-2": second, "serial": serial}
    elif profile == "full":
        lanes = {
            f"broad-{index}": modules
            for index, modules in enumerate(balance_full(inventory), start=1)
        }
    elif profile == "robinhood":
        lanes = {
            f"robinhood-{index}": modules
            for index, modules in enumerate(balance_robinhood(inventory), start=1)
        }
    else:
        raise CertificationError(f"Unknown certification profile: {profile}")
    validate_partitions(inventory, tuple(lanes.values()))
    if any(not modules for modules in lanes.values()):
        raise CertificationError("Every certification lane must contain test modules")
    return lanes


def select_full_lane(
    inventory: tuple[str, ...],
    lanes: dict[str, tuple[str, ...]],
    profile: str,
    selection: list[str] | None,
) -> dict[str, tuple[str, ...]]:
    "Select one stable one-based FULL identity from a verified complete plan."
    if selection is None:
        return lanes
    if (
        profile != "full"
        or len(selection) != 1
        or selection[0] not in {str(index) for index in range(1, 8)}
    ):
        raise CertificationError(
            "Single-lane selection requires exactly one FULL lane 1..7"
        )
    if tuple(lanes) != tuple(f"broad-{index}" for index in range(1, 8)):
        raise CertificationError("Incomplete FULL lane plan")
    validate_partitions(inventory, tuple(lanes.values()))
    if any(not modules for modules in lanes.values()):
        raise CertificationError("Empty FULL lane")
    name = f"broad-{selection[0]}"
    return {name: lanes[name]}


def inherited_ci_static_checks(
    args: argparse.Namespace, identity: dict[str, str], evidence_dir: Path
) -> dict[str, dict[str, Any]]:
    "Accept only the exact workflow's successful same-SHA static dependency."
    if not (
        getattr(args, "lane", None) in ([str(index)] for index in range(1, 8))
        and args.profile == "full"
        and os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("GITHUB_JOB") == "certification-full"
        and os.environ.get("SOURCE_STATIC_RESULT") == "success"
        and os.environ.get("SOURCE_STATIC_HEAD") == identity["head"]
        and identity["head"] == args.expected_head
        and os.environ.get("GITHUB_SHA") == identity["head"]
        and os.environ.get("GITHUB_RUN_ATTEMPT") in {"1", "2"}
        and re.fullmatch(r"[1-9][0-9]*", os.environ.get("GITHUB_RUN_ID", ""))
        and os.environ.get("GITHUB_REF", "").startswith("refs/heads/")
        and os.environ.get("GITHUB_WORKFLOW_REF")
        == (
            "callmedraken/ai-trading-bot/.github/workflows/checkpoint-source-gates.yml@"
            + os.environ.get("GITHUB_REF", "")
        )
    ):
        raise CertificationError(
            "Exact successful CI source-static dependency required"
        )
    version = check_ruff_version(str(args.python), args.root)
    checks = {"ruff_version": version}
    for name, command in {
        **canonical_ruff_commands(str(args.python)),
        "git_diff_check": ["git", "diff", "--check"],
    }.items():
        checks[name] = {
            "command": command,
            "exit_code": 0,
            "inherited_from": "source-static",
            "head": identity["head"],
            "tree": identity["tree"],
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        }
    _save(evidence_dir / "inherited-static.json", checks)
    return checks


def _git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=root, text=True, capture_output=True, check=False
    )
    if result.returncode:
        raise CertificationError(
            f"git {' '.join(arguments)} failed: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def _resolve_live_origin_branch_sha(root: Path, tracking_ref: str) -> str:
    """Resolve one exact origin branch without updating local refs."""
    if not isinstance(tracking_ref, str) or not tracking_ref.startswith("origin/"):
        raise CertificationError("Feature ref must be an origin tracking ref")
    branch = tracking_ref.removeprefix("origin/")
    if not branch:
        raise CertificationError("Origin tracking ref must name a branch")
    remote_ref = f"refs/heads/{branch}"
    try:
        validated = subprocess.run(
            ["git", "check-ref-format", remote_ref],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as error:
        raise CertificationError(
            f"Could not validate origin tracking ref {tracking_ref}: {error}"
        ) from error
    if validated.returncode:
        raise CertificationError(f"Malformed origin tracking ref: {tracking_ref}")

    try:
        result = subprocess.run(
            ["git", "ls-remote", "--exit-code", "origin", remote_ref],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as error:
        raise CertificationError(
            f"Live origin query failed for {remote_ref}: {error}"
        ) from error
    if result.returncode:
        if result.returncode == 2 and not result.stdout:
            raise CertificationError(f"Live origin branch is missing: {remote_ref}")
        raise CertificationError(
            f"git ls-remote failed for {remote_ref}: {result.stderr.strip()}"
        )

    lines = result.stdout.splitlines()
    if len(lines) != 1 or result.stdout not in {lines[0], f"{lines[0]}\n"}:
        raise CertificationError(
            f"Malformed live origin response for {remote_ref}: expected one ref"
        )
    fields = lines[0].split("\t")
    if (
        len(fields) != 2
        or fields[1] != remote_ref
        or re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", fields[0]) is None
    ):
        raise CertificationError(f"Malformed live origin response for {remote_ref}")
    return fields[0]


def verify_source(args: argparse.Namespace) -> dict[str, str]:
    """Prove the requested checkout and its clean source identity."""
    root = args.root.resolve(strict=True)
    if Path(_git(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise CertificationError("Worktree root mismatch")
    actual = {
        "root": str(root),
        "branch": _git(root, "branch", "--show-current"),
        "head": _git(root, "rev-parse", "HEAD"),
        "tree": _git(root, "show", "-s", "--format=%T", "HEAD"),
        "base_head": _git(root, "rev-parse", "origin/develop"),
        "live_base_head": _resolve_live_origin_branch_sha(root, "origin/develop"),
    }
    expected = {
        "head": args.expected_head,
        "tree": args.expected_tree,
        "base_head": args.expected_base_head,
    }
    if args.expected_branch:
        detached_full = (
            getattr(args, "lane", None)
            and getattr(args, "profile", None) == "full"
            and os.environ.get("GITHUB_ACTIONS") == "true"
            and os.environ.get("GITHUB_JOB") == "certification-full"
            and os.environ.get("GITHUB_REF_NAME") == args.expected_branch
            and actual["branch"] == ""
        )
        expected["branch"] = "" if detached_full else args.expected_branch
    if args.expected_feature_ref:
        actual["feature_ref"] = args.expected_feature_ref
        actual["feature_head"] = _git(root, "rev-parse", args.expected_feature_ref)
        actual["live_feature_head"] = _resolve_live_origin_branch_sha(
            root, args.expected_feature_ref
        )
        expected["feature_head"] = args.expected_feature_head
        expected["live_feature_head"] = args.expected_feature_head
    expected["live_base_head"] = args.expected_base_head
    for key, value in expected.items():
        if actual[key] != value:
            raise CertificationError(
                f"Source identity mismatch for {key}: "
                f"expected {value}, got {actual[key]}"
            )
    status = _git(root, "status", "--porcelain=v1", "--untracked-files=all")
    if status:
        raise CertificationError(f"Worktree/index is not clean:\n{status}")
    return actual


def parse_junit(path: Path, *, reject_failures: bool = True) -> dict[str, int]:
    """Count actual testcases, and reject empty, inconsistent, or failing XML."""
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as error:
        raise CertificationError(
            f"Missing or malformed JUnit report: {path}"
        ) from error
    if root.tag not in {"testsuite", "testsuites"}:
        raise CertificationError(f"Invalid JUnit root: {path}")
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if not suites:
        raise CertificationError(f"Empty JUnit report: {path}")
    counts = {"cases": 0, "passed": 0, "skipped": 0, "failed": 0, "errors": 0}
    for suite in suites:
        local = {"cases": 0, "skipped": 0, "failed": 0, "errors": 0}
        for case in suite.iter("testcase"):
            if not case.get("name"):
                raise CertificationError(f"Unnamed JUnit testcase: {path}")
            outcomes = [
                kind
                for kind in ("skipped", "failure", "error")
                if case.find(kind) is not None
            ]
            if len(outcomes) > 1:
                raise CertificationError(f"Conflicting JUnit testcase outcomes: {path}")
            local["cases"] += 1
            counts["cases"] += 1
            kind = (
                {"skipped": "skipped", "failure": "failed", "error": "errors"}.get(
                    outcomes[0]
                )
                if outcomes
                else "passed"
            )
            counts[kind] += 1
            if kind != "passed":
                local[kind] += 1
        for key in ("cases", "skipped", "failed", "errors"):
            attribute = (
                "tests" if key == "cases" else "failures" if key == "failed" else key
            )
            if suite.get(attribute) is not None:
                try:
                    declared = int(suite.attrib[attribute])
                except ValueError as error:
                    raise CertificationError(f"Invalid JUnit count: {path}") from error
                if declared != local[key]:
                    raise CertificationError(f"JUnit {key} count mismatch: {path}")
    if not counts["cases"]:
        raise CertificationError(f"Empty JUnit report: {path}")
    if reject_failures and (counts["failed"] or counts["errors"]):
        raise CertificationError(f"JUnit contains failed/error cases: {path}: {counts}")
    return counts


def make_summary(
    identity: dict[str, str],
    lanes: dict[str, tuple[str, ...]],
    *,
    dry_run: bool,
    evidence_dir: Path,
) -> dict[str, Any]:
    """Create the persisted, machine-readable topology and result skeleton."""
    return {
        "schema_version": 1,
        "status": "planned" if dry_run else "running",
        "dry_run": dry_run,
        "source": identity,
        "evidence_dir": str(evidence_dir),
        "inventory": sorted(module for modules in lanes.values() for module in modules),
        "lanes": {
            name: {"modules": list(modules), "module_count": len(modules)}
            for name, modules in lanes.items()
        },
    }


def _save(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def run_children(
    args: argparse.Namespace, lanes: dict[str, tuple[str, ...]], evidence_dir: Path
) -> dict[str, dict[str, Any]]:
    """Start all selected pytest lanes before waiting for any of them."""
    if not lanes or any(not modules for modules in lanes.values()):
        raise CertificationError("Every certification lane must contain test modules")
    started: dict[str, tuple[subprocess.Popen[bytes], float]] = {}
    streams: list[Any] = []
    results: dict[str, dict[str, Any]] = {}
    try:
        for name, modules in lanes.items():
            stdout = (evidence_dir / f"{name}.stdout.log").open("wb")
            stderr = (evidence_dir / f"{name}.stderr.log").open("wb")
            streams.extend((stdout, stderr))
            basetemp = args.temp_root / f"certification-{uuid.uuid4().hex}-{name}"
            junit = evidence_dir / f"{name}.xml"
            command = [
                str(args.python),
                "-m",
                "pytest",
                *modules,
                "--basetemp",
                str(basetemp),
                "-p",
                "no:cacheprovider",
                "-q",
                "-ra",
                "--durations=0",
                "--junitxml",
                str(junit),
            ]
            try:
                process = subprocess.Popen(
                    command, cwd=args.root, stdout=stdout, stderr=stderr
                )
            except OSError as error:
                results[name] = {
                    "error": f"Child could not start: {error}",
                    "command": command,
                }
                continue
            started[name] = (process, time.monotonic())
            results[name] = {
                "command": command,
                "basetemp": str(basetemp),
                "junit": str(junit),
                "stdout": str(evidence_dir / f"{name}.stdout.log"),
                "stderr": str(evidence_dir / f"{name}.stderr.log"),
            }
        for name, (process, start) in started.items():
            try:
                code = process.wait(timeout=args.timeout_seconds)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                results[name]["error"] = "Child timed out and was killed"
                code = process.returncode
            results[name].update(
                exit_code=code, elapsed_seconds=round(time.monotonic() - start, 3)
            )
            if code != 0:
                results[name]["error"] = results[name].get(
                    "error", f"Child exited with {code}"
                )
            try:
                counts = parse_junit(
                    Path(results[name]["junit"]), reject_failures=False
                )
                results[name]["counts"] = counts
                if counts["failed"] or counts["errors"]:
                    results[name]["error"] = "JUnit contains failed/error cases"
            except CertificationError as error:
                results[name]["error"] = (
                    f"{results[name].get('error', '')} {error}".strip()
                )
    finally:
        for stream in streams:
            stream.close()
    return results


def run_static_checks(
    args: argparse.Namespace, evidence_dir: Path
) -> dict[str, dict[str, Any]]:
    """Run the accepted source checks without Ruff caches."""
    version = check_ruff_version(str(args.python), args.root)
    results = {"ruff_version": version}
    for stream in ("stdout", "stderr"):
        (evidence_dir / f"ruff_version.{stream}.log").write_text(
            version.get(stream, version.get("error", "")), encoding="utf-8"
        )
    if version["exit_code"]:
        return results
    commands = {
        **canonical_ruff_commands(str(args.python)),
        "git_diff_check": ["git", "diff", "--check"],
    }
    for name, command in commands.items():
        try:
            completed = subprocess.run(
                command, cwd=args.root, text=True, capture_output=True, check=False
            )
            result = {"command": command, "exit_code": completed.returncode}
            (evidence_dir / f"{name}.stdout.log").write_text(
                completed.stdout, encoding="utf-8"
            )
            (evidence_dir / f"{name}.stderr.log").write_text(
                completed.stderr, encoding="utf-8"
            )
        except OSError as error:
            result = {"command": command, "error": str(error)}
        results[name] = result
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILES, default="full")
    parser.add_argument(
        "--lane", action="append", help="Execute exactly one FULL lane (1..7)"
    )
    parser.add_argument(
        "--ci-source-static",
        action="store_true",
        help="Use the exact CI static dependency in distributed FULL mode",
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-tree", required=True)
    parser.add_argument("--expected-base-head", required=True)
    parser.add_argument("--expected-branch")
    parser.add_argument("--expected-feature-ref")
    parser.add_argument("--expected-feature-head")
    parser.add_argument("--temp-root", type=Path, default=DEFAULT_TEMP_ROOT)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=7200)
    parser.add_argument(
        "--plan", action="store_true", help="Verify and save topology without pytest"
    )
    return parser


def _validate_pytest_temp_root(args: argparse.Namespace) -> None:
    """Keep local certification on the frozen root; admit hosted CI runner temp."""
    if args.plan:
        return
    requested = args.temp_root.resolve()
    if requested == DEFAULT_TEMP_ROOT.resolve():
        return
    if os.environ.get("GITHUB_ACTIONS") == "true":
        runner_temp_raw = os.environ.get("RUNNER_TEMP")
        if runner_temp_raw:
            runner_temp = Path(runner_temp_raw).resolve()
            if requested == runner_temp or runner_temp in requested.parents:
                return
    raise CertificationError(
        f"Pytest basetemp root must be {DEFAULT_TEMP_ROOT} locally or "
        "a GitHub Actions RUNNER_TEMP descendant"
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    """Admit source, save exact topology, and optionally execute certification."""
    if bool(args.expected_feature_ref) != bool(args.expected_feature_head):
        raise CertificationError(
            "Feature ref and expected feature HEAD must be supplied together"
        )
    if args.expected_feature_ref and not args.expected_feature_ref.startswith(
        "origin/"
    ):
        raise CertificationError("Feature ref must be an origin tracking ref")
    if args.timeout_seconds <= 0:
        raise CertificationError("Timeout must be positive")
    reject_protected_opt_ins(dict(os.environ))
    identity = verify_source(args)
    _validate_pytest_temp_root(args)
    if not args.plan:
        args.temp_root.mkdir(parents=True, exist_ok=True)
    profile = getattr(args, "profile", "full")
    repository_inventory = discover_inventory(args.root)
    if profile not in PROFILES:
        raise CertificationError(f"Unknown certification profile: {profile}")
    profiles = classify_inventory(repository_inventory)
    inventory = profiles[profile]
    _validate_legacy_required(inventory, profile)
    lanes = build_lanes(args.root, inventory, profile)
    execution_lanes = select_full_lane(
        inventory, lanes, profile, getattr(args, "lane", None)
    )
    if getattr(args, "ci_source_static", False) and not getattr(args, "lane", None):
        raise CertificationError("CI static dependency requires single-lane FULL mode")
    serial = lanes.get("serial", ())
    broad = tuple(module for module in inventory if module not in set(serial))
    excluded = tuple(
        module for module in repository_inventory if module not in set(inventory)
    )
    evidence_dir = (
        args.evidence_dir
        or args.temp_root / f"certification-evidence-{uuid.uuid4().hex}"
    )
    if (
        args.root.resolve() == evidence_dir.resolve()
        or args.root.resolve() in evidence_dir.resolve().parents
    ):
        raise CertificationError("Evidence directory must be outside the worktree")
    evidence_dir.mkdir(parents=True, exist_ok=False)
    summary = make_summary(
        identity, lanes, dry_run=args.plan, evidence_dir=evidence_dir
    )
    classification = {
        "policy": "architecture-132-r1",
        "supported_inventory": list(profiles["full"]),
        "legacy_inventory": list(profiles["legacy"]),
        "profile_counts": {name: len(modules) for name, modules in profiles.items()},
        "ownership": {
            "supported_directories": list(FULL_DIRECTORIES),
            "supported_exact_modules": list(FULL_EXACT_MODULES),
            "supported_root_pattern": "tests/test_robinhood_*.py",
            "legacy_directories": list(LEGACY_DIRECTORIES),
            "legacy_exact_modules": list(LEGACY_EXACT_MODULES),
            "robinhood_directories": list(ROBINHOOD_DIRECTORIES),
            "robinhood_infrastructure": list(ROBINHOOD_INFRASTRUCTURE_MODULES),
        },
    }
    summary.update(
        classification=classification,
        profile=profile,
        repository_inventory=list(repository_inventory),
        selected_inventory=list(inventory),
        inventory_sha256=hashlib.sha256(
            json.dumps(sorted(inventory), separators=(",", ":")).encode()
        ).hexdigest(),
        executed_lanes=list(execution_lanes),
        executed_modules=[
            module for modules in execution_lanes.values() for module in modules
        ],
        excluded_inventory=list(excluded),
    )
    _save(
        evidence_dir / "inventory.json",
        {
            "profile": profile,
            "classification": classification,
            "all": list(repository_inventory),
            "repository": list(repository_inventory),
            "selected": list(inventory),
            "excluded": list(excluded),
            "broad": list(broad),
            "serial": list(serial),
            "lanes": {name: list(modules) for name, modules in lanes.items()},
        },
    )
    _save(evidence_dir / "results.json", summary)
    if args.plan:
        return summary
    start = time.monotonic()
    try:
        summary["static_checks"] = (
            inherited_ci_static_checks(args, identity, evidence_dir)
            if getattr(args, "ci_source_static", False)
            else run_static_checks(args, evidence_dir)
        )
        static_passed = set(summary["static_checks"]) == {
            "ruff_version",
            "ruff_check",
            "ruff_format",
            "git_diff_check",
        } and all(
            check.get("exit_code") == 0 for check in summary["static_checks"].values()
        )
        summary["children"] = {}
        if static_passed:
            summary["children"] = run_children(args, execution_lanes, evidence_dir)
            try:
                summary["post_test_source"] = verify_source(args)
            except CertificationError as error:
                summary["source_error"] = str(error)
        children_passed = set(summary["children"]) == set(execution_lanes) and all(
            "error" not in child and child.get("exit_code") == 0
            for child in summary["children"].values()
        )
        try:
            summary["final_source"] = verify_source(args)
        except CertificationError as error:
            summary["source_error"] = str(error)
        counts = {key: 0 for key in ("cases", "passed", "skipped", "failed", "errors")}
        for child in summary["children"].values():
            for key, count in child.get("counts", {}).items():
                counts[key] += count
        summary["totals"] = counts
        summary["status"] = (
            "passed"
            if (not summary.get("source_error") and children_passed and static_passed)
            else "failed"
        )
    finally:
        summary["wall_seconds"] = round(time.monotonic() - start, 3)
        if getattr(args, "lane", None):
            summary["hygiene_passed"] = summary["wall_seconds"] < 300
            if not summary["hygiene_passed"]:
                summary["status"] = "failed"
        _save(evidence_dir / "results.json", summary)
    return summary


def main() -> int:
    try:
        summary = run(build_parser().parse_args())
    except (CertificationError, OSError) as error:
        print(f"Certification STOP: {error}", file=sys.stderr)
        return 1
    print(f"Status: {summary['status']}; profile: {summary['profile']}")
    print(f"HEAD: {summary['source']['head']}; tree: {summary['source']['tree']}")
    for name, lane in summary["lanes"].items():
        child = summary.get("children", {}).get(name, {})
        print(f"{name}: {lane['module_count']} modules; {child.get('counts', {})}")
        print(
            f"  elapsed {child.get('elapsed_seconds', 'planned')} s; "
            f"exit {child.get('exit_code', 'planned')}"
        )
    if "totals" in summary:
        print(f"Totals: {summary['totals']}; wall: {summary['wall_seconds']} s")
    print(f"Evidence: {summary['evidence_dir']}")
    return 0 if summary["status"] in {"planned", "passed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
