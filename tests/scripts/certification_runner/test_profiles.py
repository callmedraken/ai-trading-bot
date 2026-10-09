from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_test_certification as runner

from .helpers import (
    _EXPECTED_FULL,
    _EXPECTED_ROBINHOOD,
    _EXPECTED_SERIAL,
    _PREPARE_OPERATOR_TEST,
    _PUBLISHED_PREPARE_TEST,
    _SUPERVISED_QUALIFICATION_TEST,
    _UNATTENDED_ACTIVATION_TEST,
    _UNATTENDED_EXECUTION_TEST,
    _UNATTENDED_HOST_TEST,
    _UNATTENDED_ONE_WAKE_TEST,
    _UNATTENDED_STATE_TEST,
    _fixture_profiles,
    _lane_names,
    _profile_inventory,
)


def test_current_robinhood_baseline_and_arch131_registration_coverage() -> None:
    from scripts import checkpoint_runner

    root = Path(runner.__file__).resolve().parents[1]
    repository = runner.discover_inventory(root)
    selected = runner.select_inventory(repository, "robinhood")
    assert runner.ROBINHOOD_REQUIRED_MODULES == _EXPECTED_ROBINHOOD
    assert len(runner.ROBINHOOD_REQUIRED_MODULES) == 49
    assert selected == tuple(
        sorted(
            (
                *_EXPECTED_ROBINHOOD,
                _PUBLISHED_PREPARE_TEST,
                _PREPARE_OPERATOR_TEST,
                _SUPERVISED_QUALIFICATION_TEST,
                _UNATTENDED_ACTIVATION_TEST,
                _UNATTENDED_STATE_TEST,
                _UNATTENDED_ONE_WAKE_TEST,
                _UNATTENDED_EXECUTION_TEST,
                _UNATTENDED_HOST_TEST,
                "tests/review_paper/test_unattended_publication.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_retained_root_acl_recovery.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/review_paper/test_post_publication_stage_diagnostic.py",
                "tests/review_paper/test_publication_state_paper_diagnostic.py",
                "tests/review_paper/test_publication_state_paper_corrected.py",
                "tests/review_paper/test_arch133_scheduler_installation.py",
                "tests/review_paper/test_arch133_fresh_activation_reprovision.py",
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/review_paper/test_arch133_parent_security_diagnostic.py",
                "tests/review_paper/test_arch133_parent_policy_diagnostic.py",
                "tests/review_paper/test_arch133_fresh_activation_reprovision_corrected.py",
                "tests/review_paper/test_arch133_reprovision_reconciliation.py",
                "tests/review_paper/test_arch133_reprovision_recovery.py",
            )
        )
    )
    assert len(selected) == 73
    registered = {
        module
        for name, spec in checkpoint_runner._checkpoint_specs().items()
        if name.startswith(("arch131-", "arch133-"))
        for module in spec.tests
    }
    assert registered <= set(selected)
    assert not set(runner.SERIAL_MODULES) & set(selected)


def test_current_profile_counts_support_partition_and_serial_allowlist() -> None:
    root = Path(runner.__file__).resolve().parents[1]
    inventory = runner.discover_inventory(root)
    profiles = {
        name: runner.select_inventory(inventory, name)
        for name in ("full", "robinhood", "legacy", "exhaustive")
    }
    assert runner.PROFILES == ("full", "robinhood", "legacy", "exhaustive")
    assert _EXPECTED_FULL == runner.FULL_REQUIRED_MODULES
    assert len(runner.FULL_REQUIRED_MODULES) == 122
    assert profiles["full"] == tuple(
        sorted(
            (
                *_EXPECTED_FULL,
                _PUBLISHED_PREPARE_TEST,
                _PREPARE_OPERATOR_TEST,
                _SUPERVISED_QUALIFICATION_TEST,
                _UNATTENDED_ACTIVATION_TEST,
                _UNATTENDED_STATE_TEST,
                _UNATTENDED_ONE_WAKE_TEST,
                _UNATTENDED_EXECUTION_TEST,
                _UNATTENDED_HOST_TEST,
                "tests/review_paper/test_unattended_publication.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_retained_root_acl_recovery.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/review_paper/test_post_publication_stage_diagnostic.py",
                "tests/review_paper/test_publication_state_paper_diagnostic.py",
                "tests/review_paper/test_publication_state_paper_corrected.py",
                "tests/review_paper/test_arch133_scheduler_installation.py",
                "tests/review_paper/test_arch133_fresh_activation_reprovision.py",
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/review_paper/test_arch133_parent_security_diagnostic.py",
                "tests/review_paper/test_arch133_parent_policy_diagnostic.py",
                "tests/review_paper/test_arch133_fresh_activation_reprovision_corrected.py",
                "tests/review_paper/test_arch133_reprovision_reconciliation.py",
                "tests/review_paper/test_arch133_reprovision_recovery.py",
            )
        )
    )
    assert _PUBLISHED_PREPARE_TEST in profiles["robinhood"]
    assert _PREPARE_OPERATOR_TEST in profiles["robinhood"]
    assert _PREPARE_OPERATOR_TEST in profiles["full"]
    assert _SUPERVISED_QUALIFICATION_TEST in profiles["robinhood"]
    assert _SUPERVISED_QUALIFICATION_TEST in profiles["full"]
    assert _UNATTENDED_ACTIVATION_TEST in profiles["robinhood"]
    assert _UNATTENDED_ACTIVATION_TEST in profiles["full"]
    assert _UNATTENDED_EXECUTION_TEST in profiles["robinhood"]
    assert _UNATTENDED_EXECUTION_TEST in profiles["full"]
    assert {name: len(value) for name, value in profiles.items()} == {
        "full": 146,
        "robinhood": 73,
        "legacy": 205,
        "exhaustive": 351,
    }
    assert profiles["exhaustive"] == inventory
    assert set(profiles["robinhood"]) <= set(profiles["full"])
    assert set(profiles["full"]).isdisjoint(profiles["legacy"])
    assert set(profiles["full"]) | set(profiles["legacy"]) == set(inventory)
    assert runner.SERIAL_MODULES == _EXPECTED_SERIAL
    for name, selected in profiles.items():
        lanes = runner.build_lanes(root, selected, name)
        assert tuple(lanes) == _lane_names(name)
        assert all(lanes.values())
        runner.validate_partitions(selected, tuple(lanes.values()))
        if name in {"legacy", "exhaustive"}:
            broad, serial = runner.separate_serial(selected)
            assert lanes["serial"] == serial == _EXPECTED_SERIAL
            assert tuple(lanes.values())[:2] == runner.balance_broad(root, broad)
        else:
            assert not set(selected) & set(_EXPECTED_SERIAL)
            assert tuple(lanes.values()) == runner.balance_broad(root, selected)


@pytest.mark.parametrize(
    "module",
    [
        *(f"{directory}/test_new.py" for directory in runner.ROBINHOOD_DIRECTORIES),
        "tests/test_robinhood_new.py",
    ],
)
def test_new_owned_modules_are_automatically_admitted(module: str) -> None:
    inventory = tuple(
        sorted((*_EXPECTED_FULL, *runner.LEGACY_REQUIRED_MODULES, module))
    )
    assert runner.select_inventory(inventory, "robinhood") == tuple(
        sorted((*_EXPECTED_ROBINHOOD, module))
    )
    assert module in runner.select_inventory(inventory, "full")


@pytest.mark.parametrize("missing", _EXPECTED_ROBINHOOD)
@pytest.mark.parametrize("rename", [False, True])
def test_missing_or_renamed_required_module_fails_closed(
    missing: str, rename: bool
) -> None:
    inventory = tuple(module for module in _EXPECTED_FULL if module != missing)
    if rename:
        inventory += (missing.replace(".py", "_renamed.py"),)
    with pytest.raises(runner.CertificationError, match="Missing required Robinhood"):
        runner.select_inventory(inventory, "robinhood")


def test_retired_families_are_legacy_and_research_is_supported() -> None:
    root = Path(runner.__file__).resolve().parents[1]
    profiles = runner.classify_inventory(runner.discover_inventory(root))
    expected_counts = {
        "tests/acceptance": 1,
        "tests/cli": 34,
        "tests/gui": 34,
        "tests/market_data": 8,
        "tests/runtime": 126,
        "tests/scripts": 1,
    }
    assert {
        directory: sum(
            Path(module).parent.as_posix() == directory for module in profiles["legacy"]
        )
        for directory in expected_counts
    } == expected_counts
    for module in (
        "tests/runtime/test_d10_arch128_r4_windows.py",
        "tests/runtime/test_personal_desktop_paper_account_authority.py",
        "tests/market_data/test_alpaca_daily_snapshot.py",
        "tests/cli/test_daily_snapshot_capture.py",
        "tests/scripts/test_capture_daily_market_snapshot.py",
        *_EXPECTED_SERIAL,
    ):
        assert module in profiles["legacy"]
    for module in (
        "tests/analytics/test_analyzer.py",
        "tests/backtesting/test_backtest_engine.py",
        "tests/strategies/test_moving_average.py",
        "tests/portfolio/test_mean_cvar.py",
        "tests/cli/test_walk_forward_experiment.py",
        "tests/scripts/test_run_backtest.py",
        "tests/test_config.py",
    ):
        assert module in profiles["full"]
        assert module not in profiles["robinhood"]


@pytest.mark.parametrize("missing", _EXPECTED_FULL)
@pytest.mark.parametrize("rename", [False, True])
def test_full_missing_or_renamed_frozen_baseline_fails_closed(
    missing: str, rename: bool
) -> None:
    inventory = tuple(module for module in _EXPECTED_FULL if module != missing)
    if rename:
        inventory += (missing.replace(".py", "_renamed.py"),)
    with pytest.raises(runner.CertificationError, match="Missing required"):
        runner.select_inventory(inventory, "full")


@pytest.mark.parametrize(
    "module",
    [
        "tests/analytics/test_new.py",
        "tests/backtesting/nested/test_new.py",
        "tests/domain/nested/test_new.py",
        "tests/execution/test_new.py",
        "tests/experiments/test_new.py",
        "tests/integration/test_new.py",
        "tests/ledger/test_new.py",
        "tests/market_calendar/test_new.py",
        "tests/multi_backtesting/test_new.py",
        "tests/optimization/test_new.py",
        "tests/portfolio/test_new.py",
        "tests/portfolio_analytics/test_new.py",
        "tests/rebalancing/test_new.py",
        "tests/review_paper/test_new.py",
        "tests/risk/test_new.py",
        "tests/robinhood_mcp/test_new.py",
        "tests/simulation/test_new.py",
        "tests/strategies/test_new.py",
        "tests/test_robinhood_new.py",
    ],
)
def test_new_supported_files_are_discovered_and_admitted(
    tmp_path: Path, module: str
) -> None:
    _profile_inventory(tmp_path, "full")
    path = tmp_path / module
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    inventory = runner.discover_inventory(tmp_path)
    assert runner.select_inventory(inventory, "full") == tuple(
        sorted((*_EXPECTED_FULL, module))
    )
    assert module not in runner.select_inventory(inventory, "legacy")


@pytest.mark.parametrize("profile", ("full", "robinhood", "legacy", "exhaustive"))
@pytest.mark.parametrize(
    "module",
    [
        "tests/new_product/test_new.py",
        "tests/test_unknown.py",
        "tests/cli/test_unknown.py",
        "tests/market_data/test_unknown.py",
        "tests/scripts/test_unknown.py",
        "tests/scripts/certification_runner/test_unknown.py",
        "tests/runtime/checkpoint_runner/test_unknown.py",
    ],
)
def test_unclassified_namespace_fails_every_profile(profile: str, module: str) -> None:
    inventory = tuple(
        sorted((*_EXPECTED_FULL, *runner.LEGACY_REQUIRED_MODULES, module))
    )
    with pytest.raises(runner.CertificationError, match="Unclassified"):
        runner.select_inventory(inventory, profile)


@pytest.mark.parametrize(
    "mutation",
    ["exhaustive", "overlap", "missing", "robinhood", "duplicate", "profile_set"],
)
def test_classification_invariants_fail_closed(mutation: str) -> None:
    profiles = _fixture_profiles()
    repository = profiles["exhaustive"]
    if mutation == "exhaustive":
        profiles["exhaustive"] = repository[:-1]
    elif mutation == "overlap":
        profiles["legacy"] += (profiles["full"][0],)
    elif mutation == "missing":
        profiles["legacy"] = profiles["legacy"][:-1]
    elif mutation == "robinhood":
        profiles["robinhood"] += (profiles["legacy"][0],)
    elif mutation == "duplicate":
        profiles["robinhood"] += (profiles["robinhood"][0],)
    else:
        profiles.pop("legacy")
    with pytest.raises(runner.CertificationError):
        runner.validate_classification(repository, profiles)


def test_ownership_overlap_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        runner,
        "LEGACY_EXACT_MODULES",
        (*runner.LEGACY_EXACT_MODULES, "tests/test_config.py"),
    )
    with pytest.raises(runner.CertificationError, match="Overlapping"):
        runner.classify_inventory(_EXPECTED_FULL)


@pytest.mark.parametrize("profile", ["legacy", "exhaustive"])
@pytest.mark.parametrize("renamed", [False, True])
def test_retained_replacement_required_baseline_fails_closed(
    profile, renamed, tmp_path, monkeypatch
):
    inventory = list(_fixture_profiles()["exhaustive"])
    missing = "tests/runtime/checkpoint_runner/test_retained_arch128_130.py"
    inventory.remove(missing)
    if renamed:
        inventory.append(missing.replace(".py", "_renamed.py"))
    with pytest.raises(
        runner.CertificationError, match="Unclassified|Missing required LEGACY"
    ):
        runner.select_inventory(tuple(sorted(inventory)), profile)
    _profile_inventory(tmp_path, profile)
    original = tmp_path / missing
    if renamed:
        original.rename(original.with_name(original.stem + "_renamed.py"))
    else:
        original.unlink()
    monkeypatch.setattr(
        runner, "verify_source", lambda args: {"head": "h", "tree": "t"}
    )
    monkeypatch.setattr(
        runner, "run_children", lambda *args: pytest.fail("child launched")
    )
    args = SimpleNamespace(
        root=tmp_path,
        expected_feature_ref=None,
        expected_feature_head=None,
        timeout_seconds=1,
        temp_root=tmp_path,
        plan=True,
        profile=profile,
    )
    with pytest.raises(
        runner.CertificationError, match="Unclassified|Missing required LEGACY"
    ):
        runner.run(args)
