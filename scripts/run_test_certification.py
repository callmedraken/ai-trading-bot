"""Certify supported, Robinhood, legacy, or exhaustive source test profiles."""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

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
    "tests/test_config.py",
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
    elif profile in {"full", "robinhood"}:
        first, second = balance_broad(root, inventory)
        prefix = "broad" if profile == "full" else "robinhood"
        lanes = {f"{prefix}-1": first, f"{prefix}-2": second}
    else:
        raise CertificationError(f"Unknown certification profile: {profile}")
    validate_partitions(inventory, tuple(lanes.values()))
    if any(not modules for modules in lanes.values()):
        raise CertificationError("Every certification lane must contain test modules")
    return lanes


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
        expected["branch"] = args.expected_branch
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
    commands = {
        "ruff_check": [str(args.python), "-m", "ruff", "check", "--no-cache", "."],
        "ruff_format": [
            str(args.python),
            "-m",
            "ruff",
            "format",
            "--check",
            "--no-cache",
            ".",
        ],
        "git_diff_check": ["git", "diff", "--check"],
    }
    results = {}
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
    if not args.plan and args.temp_root.resolve() != DEFAULT_TEMP_ROOT.resolve():
        raise CertificationError(f"Pytest basetemp root must be {DEFAULT_TEMP_ROOT}")
    profile = getattr(args, "profile", "full")
    repository_inventory = discover_inventory(args.root)
    if profile not in PROFILES:
        raise CertificationError(f"Unknown certification profile: {profile}")
    profiles = classify_inventory(repository_inventory)
    inventory = profiles[profile]
    _validate_legacy_required(inventory, profile)
    lanes = build_lanes(args.root, inventory, profile)
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
        summary["children"] = run_children(args, lanes, evidence_dir)
        try:
            summary["post_test_source"] = verify_source(args)
        except CertificationError as error:
            summary["source_error"] = str(error)
        children_passed = set(summary["children"]) == set(lanes) and all(
            "error" not in child and child.get("exit_code") == 0
            for child in summary["children"].values()
        )
        if not summary.get("source_error") and children_passed:
            summary["static_checks"] = run_static_checks(args, evidence_dir)
        else:
            summary["static_checks"] = {}
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
            if (
                not summary.get("source_error")
                and children_passed
                and len(summary["static_checks"]) == 3
                and all(
                    check.get("exit_code") == 0
                    for check in summary["static_checks"].values()
                )
            )
            else "failed"
        )
    finally:
        summary["wall_seconds"] = round(time.monotonic() - start, 3)
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
