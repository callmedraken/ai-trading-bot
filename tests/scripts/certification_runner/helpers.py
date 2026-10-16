import argparse
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_test_certification as runner


def _inventory(tmp_path: Path) -> tuple[str, ...]:
    modules = (
        "tests/a/test_first.py",
        "tests/a/test_second.py",
        "tests/b/test_third.py",
        "tests/b/test_fourth.py",
        "tests/safety/test_serial.py",
    )
    for index, module in enumerate(modules):
        path = tmp_path / module
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * (index + 1))
    return modules


_SOURCE_HEAD = "1" * 40

_SOURCE_TREE = "2" * 40

_BASE_SHA = "3" * 40

_FEATURE_SHA = "4" * 40


def _source_args(
    root: Path,
    *,
    feature_ref: str | None = None,
    feature_head: str | None = None,
) -> argparse.Namespace:
    return argparse.Namespace(
        root=root,
        expected_head=_SOURCE_HEAD,
        expected_tree=_SOURCE_TREE,
        expected_base_head=_BASE_SHA,
        expected_branch="feature/certification",
        expected_feature_ref=feature_ref,
        expected_feature_head=feature_head,
    )


def _install_source_git_state(
    monkeypatch: pytest.MonkeyPatch, root: Path, args: argparse.Namespace
) -> None:
    state = {
        ("branch", "--show-current"): args.expected_branch,
        ("rev-parse", "HEAD"): args.expected_head,
        ("show", "-s", "--format=%T", "HEAD"): args.expected_tree,
        ("rev-parse", "origin/develop"): args.expected_base_head,
        ("status", "--porcelain=v1", "--untracked-files=all"): "",
    }
    if args.expected_feature_ref:
        state[("rev-parse", args.expected_feature_ref)] = args.expected_feature_head

    def fake_git(actual_root: Path, *arguments: str) -> str:
        if arguments == ("rev-parse", "--show-toplevel"):
            return str(root)
        return state[arguments]

    monkeypatch.setattr(runner, "_git", fake_git)


def _install_live_git(
    monkeypatch: pytest.MonkeyPatch,
    responses: dict[str, tuple[int, str, str]],
) -> list[str]:
    queried_refs: list[str] = []

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        if command[1] == "check-ref-format":
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        assert command[:4] == ["git", "ls-remote", "--exit-code", "origin"]
        assert len(command) == 5
        remote_ref = command[4]
        queried_refs.append(remote_ref)
        return_code, stdout, stderr = responses.get(remote_ref, (2, "", ""))
        return SimpleNamespace(returncode=return_code, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    return queried_refs


def _ls_remote_line(sha: str, remote_ref: str) -> str:
    return f"{sha}\t{remote_ref}\n"


_BASELINE_FAMILIES = {
    "domain": "market orders positions proposals",
    "execution": (
        "execution_models order_engine paper_fill_application paper_fills "
        "paper_submission portfolio_orders"
    ),
    "ledger": "checkpoint_state initialization ledger models",
    "risk": "manager orchestration risk_models",
    "review_paper": (
        "forward_preview intent_bridge nyse_published_regular_sessions performance "
        "prepare_qualification risk_context risk_price_acquisition risk_prices "
        "session_admission store supervised_forward_paper"
    ),
    "robinhood_mcp": "account_resolution adapter sdk_transport windows_oauth",
}

_BASELINE_ROOT = (
    "forward_paper_cycle live_qualification_verifier paper_cycle paper_operator "
    "paper_pipeline prepare_qualification_verifier"
)

_EXPECTED_ROBINHOOD = tuple(
    sorted(
        [
            f"tests/{family}/test_{name}.py"
            for family, names in _BASELINE_FAMILIES.items()
            for name in names.split()
        ]
        + [f"tests/test_robinhood_{name}.py" for name in _BASELINE_ROOT.split()]
        + [
            "tests/runtime/checkpoint_runner/test_core.py",
            "tests/runtime/checkpoint_runner/test_ci.py",
            "tests/runtime/checkpoint_runner/test_arch131.py",
            "tests/runtime/checkpoint_runner/test_arch133_a_g.py",
            "tests/runtime/checkpoint_runner/test_arch133_h_k.py",
            "tests/runtime/checkpoint_runner/test_arch133_l_m.py",
            "tests/scripts/certification_runner/test_profiles.py",
            "tests/scripts/certification_runner/test_lanes.py",
            "tests/scripts/certification_runner/test_source.py",
            "tests/scripts/certification_runner/test_children.py",
            "tests/scripts/certification_runner/test_results.py",
        ]
    )
)

_SUPPORTED_ADDITIONAL_FAMILIES = {
    "analytics": ("analyzer"),
    "backtesting": ("backtest_engine backtest_models"),
    "cli": (
        "create_research_session_bundle historical_experiment "
        "historical_experiment_pairwise_config "
        "historical_experiment_pairwise_serialization "
        "historical_experiment_pareto_config "
        "historical_experiment_pareto_serialization "
        "historical_experiment_report_serialization optimized_simulation "
        "research_session_archive research_session_archive_cli "
        "research_session_bundle research_session_manifest "
        "research_session_restore restore_research_session_archive "
        "rolling_historical verify_research_session_manifest "
        "walk_forward_aggregate_config "
        "walk_forward_aggregate_serialization walk_forward_experiment "
        "walk_forward_experiment_config "
        "walk_forward_experiment_serialization "
        "walk_forward_stability_config "
        "walk_forward_stability_serialization"
    ),
    "experiments": (
        "comparison grid historical pairwise pareto report walk_forward "
        "walk_forward_analytics walk_forward_stability"
    ),
    "integration": (
        "walk_forward_e2e walk_forward_research_archive_e2e "
        "walk_forward_research_bundle_e2e "
        "walk_forward_research_restore_e2e "
        "walk_forward_research_transport_e2e"
    ),
    "market_calendar": ("calendar_models nyse_calendar"),
    "market_data": (
        "csv_historical_provider historical_models multi_symbol_models "
        "multi_symbol_provider"
    ),
    "multi_backtesting": ("engine models strategy_contract"),
    "optimization": ("cpu_mean_cvar"),
    "portfolio": (
        "historical_scenarios mean_cvar models optimized_targets "
        "optimizer_protocol scenarios"
    ),
    "portfolio_analytics": ("analyzer models optimized_simulation"),
    "rebalancing": ("models planner proposals"),
    "scripts": (
        "create_walk_forward_research_bundle "
        "research_session_archive_scripts run_backtest "
        "run_historical_experiment run_rolling_historical_simulation "
        "run_walk_forward_experiment"
    ),
    "simulation": ("optimized_paper_portfolio paper_portfolio rolling_historical"),
    "strategies": ("moving_average"),
}

_EXPECTED_FULL = tuple(
    sorted(
        (
            *_EXPECTED_ROBINHOOD,
            *(
                f"tests/{family}/test_{name}.py"
                for family, names in _SUPPORTED_ADDITIONAL_FAMILIES.items()
                for name in names.split()
            ),
            "tests/test_config.py",
        )
    )
)

_EXPECTED_SERIAL = (
    "tests/runtime/test_windows_transactional_capture_authority.py",
    "tests/runtime/test_windows_authority_schema.py",
    "tests/runtime/test_windows_authority.py",
    "tests/runtime/test_windows_effectful_capture_native_acceptance.py",
    "tests/acceptance/test_windows_authority_provisioning_acceptance.py",
)

_FIXTURE_LEGACY = tuple(
    sorted(
        (
            *_EXPECTED_SERIAL,
            "tests/runtime/checkpoint_runner/test_retained_arch128_130.py",
            "tests/gui/test_unrelated.py",
            "tests/runtime/test_d10_future.py",
            "tests/cli/test_daily_snapshot_capture.py",
            "tests/market_data/test_alpaca_http.py",
            "tests/scripts/test_capture_daily_market_snapshot.py",
        )
    )
)


def _fixture_profiles() -> dict[str, tuple[str, ...]]:
    return {
        "full": _EXPECTED_FULL,
        "robinhood": _EXPECTED_ROBINHOOD,
        "legacy": _FIXTURE_LEGACY,
        "exhaustive": tuple(sorted((*_EXPECTED_FULL, *_FIXTURE_LEGACY))),
    }


def _lane_names(profile: str) -> tuple[str, ...]:
    return {
        "full": ("broad-1", "broad-2"),
        "robinhood": ("robinhood-1", "robinhood-2"),
        "legacy": ("legacy-1", "legacy-2", "serial"),
        "exhaustive": ("broad-1", "broad-2", "serial"),
    }[profile]


def _profile_inventory(root: Path, profile: str) -> tuple[str, ...]:
    for index, module in enumerate(_fixture_profiles()["exhaustive"]):
        path = root / module
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * (index + 1))
    return _fixture_profiles()[profile]


def _parser_arguments() -> list[str]:
    return [
        "--root",
        ".",
        "--python",
        "python",
        "--expected-head",
        "h",
        "--expected-tree",
        "t",
        "--expected-base-head",
        "b",
    ]


_PUBLISHED_PREPARE_TEST = "tests/review_paper/test_published_session_prepare.py"

_PREPARE_OPERATOR_TEST = "tests/test_robinhood_prepare_operator.py"

_SUPERVISED_QUALIFICATION_TEST = "tests/test_robinhood_supervised_qualification.py"

_UNATTENDED_ACTIVATION_TEST = "tests/review_paper/test_unattended_activation.py"

_UNATTENDED_STATE_TEST = "tests/review_paper/test_unattended_state_store.py"

_UNATTENDED_ONE_WAKE_TEST = "tests/review_paper/test_unattended_one_wake.py"

_UNATTENDED_EXECUTION_TEST = "tests/review_paper/test_unattended_execution.py"

_UNATTENDED_HOST_TEST = "tests/review_paper/test_unattended_host.py"
