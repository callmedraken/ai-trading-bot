"""Focused contract tests for the persistent certification runner."""

import argparse
import json
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


def test_inventory_partition_is_complete_disjoint_and_deterministic(
    tmp_path: Path,
) -> None:
    modules = _inventory(tmp_path)
    inventory = runner.discover_inventory(tmp_path)
    assert inventory == tuple(sorted(modules))
    broad, serial = runner.separate_serial(inventory, ("tests/safety/test_serial.py",))
    lanes = runner.balance_broad(tmp_path, broad)
    assert lanes == runner.balance_broad(tmp_path, broad)
    runner.validate_partitions(inventory, (*lanes, serial))
    assert set(lanes[0]).isdisjoint(lanes[1])
    assert set(lanes[0] + lanes[1] + serial) == set(modules)


def test_missing_serial_and_duplicate_or_overlap_fail(tmp_path: Path) -> None:
    inventory = runner.discover_inventory(tmp_path)
    with pytest.raises(runner.CertificationError, match="Missing serial"):
        runner.separate_serial(inventory, ("tests/missing/test_serial.py",))
    with pytest.raises(runner.CertificationError, match="Duplicate"):
        runner.validate_partitions(("a", "b"), (("a",), ("a", "b")))
    with pytest.raises(runner.CertificationError, match="Incomplete"):
        runner.validate_partitions(("a", "b"), (("a",), ()))


@pytest.mark.parametrize(
    "xml", ["", "<testsuites/>", "<testsuite><testcase name='x'>", "<other/>"]
)
def test_empty_or_malformed_junit_fails(tmp_path: Path, xml: str) -> None:
    path = tmp_path / "result.xml"
    path.write_text(xml, encoding="utf-8")
    with pytest.raises(runner.CertificationError):
        runner.parse_junit(path)


@pytest.mark.parametrize("outcome", ["failure", "error"])
def test_failed_or_error_testcase_fails(tmp_path: Path, outcome: str) -> None:
    path = tmp_path / "result.xml"
    path.write_text(
        f"<testsuite><testcase name='bad'><{outcome}/></testcase></testsuite>",
        encoding="utf-8",
    )
    with pytest.raises(runner.CertificationError, match="failed/error"):
        runner.parse_junit(path)


def test_skipped_is_counted_separately(tmp_path: Path) -> None:
    path = tmp_path / "result.xml"
    path.write_text(
        "<testsuites><testsuite tests='2' skipped='1' failures='0' errors='0'>"
        "<testcase name='ok'/><testcase name='skip'><skipped/></testcase>"
        "</testsuite></testsuites>",
        encoding="utf-8",
    )
    assert runner.parse_junit(path) == {
        "cases": 2,
        "passed": 1,
        "skipped": 1,
        "failed": 0,
        "errors": 0,
    }


def test_protected_opt_in_presence_fails_closed() -> None:
    for name in runner.PROTECTED_OPT_INS:
        with pytest.raises(runner.CertificationError, match=name):
            runner.reject_protected_opt_ins({name: "0"})


def test_subprocess_failure_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FailedProcess:
        returncode = 7

        def wait(self, timeout: int) -> int:
            return self.returncode

    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **k: FailedProcess())
    monkeypatch.setattr(
        runner,
        "parse_junit",
        lambda path, **kwargs: {
            "cases": 1,
            "passed": 1,
            "skipped": 0,
            "failed": 0,
            "errors": 0,
        },
    )
    args = SimpleNamespace(
        root=tmp_path, python=Path("python"), temp_root=tmp_path, timeout_seconds=1
    )
    result = runner.run_children(
        args, {"broad-1": ("tests/a/test_first.py",)}, tmp_path
    )
    assert result["broad-1"]["exit_code"] == 7
    assert "error" in result["broad-1"]


@pytest.mark.parametrize("profile", runner.PROFILES)
def test_plan_never_launches_pytest_and_saves_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    modules = _profile_inventory(tmp_path, profile)
    monkeypatch.setattr(
        runner, "verify_source", lambda args: {"head": "h", "tree": "t"}
    )
    monkeypatch.setattr(
        runner, "run_children", lambda *a: pytest.fail("pytest launched")
    )
    monkeypatch.setattr(
        runner, "run_static_checks", lambda *a: pytest.fail("static checks launched")
    )
    args = argparse.Namespace(
        root=tmp_path,
        python=Path("python"),
        expected_feature_ref=None,
        expected_feature_head=None,
        timeout_seconds=1,
        evidence_dir=tmp_path.parent / f"{tmp_path.name}-plan-evidence",
        temp_root=tmp_path,
        profile=profile,
        plan=True,
    )
    result = runner.run(args)
    assert result["status"] == "planned"
    assert result["profile"] == profile
    assert result["repository_inventory"] == list(runner.discover_inventory(tmp_path))
    assert result["selected_inventory"] == result["inventory"] == sorted(modules)
    evidence = json.loads((args.evidence_dir / "inventory.json").read_text())
    assert evidence["profile"] == profile
    assert evidence["all"] == evidence["repository"] == result["repository_inventory"]
    assert evidence["selected"] == result["selected_inventory"]
    assert evidence["excluded"] == result["excluded_inventory"]
    assert set(evidence["selected"]) | set(evidence["excluded"]) == set(evidence["all"])
    assert set(evidence["selected"]).isdisjoint(evidence["excluded"])
    assert set(result["lanes"]) == set(_lane_names(profile))
    expected = _fixture_profiles()
    assert evidence["excluded"] == sorted(set(expected["exhaustive"]) - set(modules))
    assert evidence["classification"] == result["classification"]
    classification = evidence["classification"]
    assert classification["policy"] == "architecture-132-r1"
    assert classification["supported_inventory"] == list(_EXPECTED_FULL)
    assert classification["legacy_inventory"] == list(_FIXTURE_LEGACY)
    assert classification["profile_counts"] == {
        name: len(value) for name, value in expected.items()
    }
    assert (
        classification["ownership"]["supported_root_pattern"]
        == "tests/test_robinhood_*.py"
    )
    if profile == "exhaustive":
        assert evidence["selected"] == evidence["all"]
        assert evidence["excluded"] == []
    if profile in {"legacy", "exhaustive"}:
        assert evidence["serial"] == list(_EXPECTED_SERIAL)
        assert result["lanes"]["serial"]["module_count"] == 5
    else:
        assert evidence["serial"] == []
    assert (args.evidence_dir / "results.json").is_file()
    assert (args.evidence_dir / "inventory.json").is_file()


def test_source_identity_mismatch_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_git(root: Path, *arguments: str) -> str:
        if arguments == ("rev-parse", "--show-toplevel"):
            return str(tmp_path)
        return {
            ("branch", "--show-current"): "feature/actual",
            ("rev-parse", "HEAD"): "head",
            ("show", "-s", "--format=%T", "HEAD"): "tree",
            ("rev-parse", "origin/develop"): "base",
        }[arguments]

    monkeypatch.setattr(runner, "_git", fake_git)
    monkeypatch.setattr(runner, "_resolve_live_origin_branch_sha", lambda *a: "base")
    args = argparse.Namespace(
        root=tmp_path,
        expected_head="head",
        expected_tree="tree",
        expected_base_head="base",
        expected_branch="feature/expected",
        expected_feature_ref=None,
    )
    with pytest.raises(runner.CertificationError, match="branch"):
        runner.verify_source(args)


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


def test_live_develop_matching_expected_head_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = _source_args(tmp_path)
    _install_source_git_state(monkeypatch, tmp_path, args)
    queried = _install_live_git(
        monkeypatch,
        {
            "refs/heads/develop": (
                0,
                _ls_remote_line(_BASE_SHA, "refs/heads/develop"),
                "",
            )
        },
    )

    identity = runner.verify_source(args)

    assert identity["base_head"] == _BASE_SHA
    assert identity["live_base_head"] == _BASE_SHA
    assert queried == ["refs/heads/develop"]


def test_live_develop_move_is_rejected_when_local_tracking_ref_is_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = _source_args(tmp_path)
    _install_source_git_state(monkeypatch, tmp_path, args)
    moved = "5" * 40
    _install_live_git(
        monkeypatch,
        {"refs/heads/develop": (0, _ls_remote_line(moved, "refs/heads/develop"), "")},
    )

    with pytest.raises(runner.CertificationError, match="live_base_head"):
        runner.verify_source(args)


def test_live_feature_move_is_rejected_when_local_tracking_ref_is_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    feature_ref = "origin/feature/certification"
    args = _source_args(tmp_path, feature_ref=feature_ref, feature_head=_FEATURE_SHA)
    _install_source_git_state(monkeypatch, tmp_path, args)
    moved = "6" * 40
    _install_live_git(
        monkeypatch,
        {
            "refs/heads/develop": (
                0,
                _ls_remote_line(_BASE_SHA, "refs/heads/develop"),
                "",
            ),
            "refs/heads/feature/certification": (
                0,
                _ls_remote_line(moved, "refs/heads/feature/certification"),
                "",
            ),
        },
    )

    with pytest.raises(runner.CertificationError, match="live_feature_head"):
        runner.verify_source(args)


def test_live_feature_query_maps_tracking_ref_to_exact_remote_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    feature_ref = "refs/heads/feature/certification/performance"
    sha = "7" * 40
    queried = _install_live_git(
        monkeypatch, {feature_ref: (0, _ls_remote_line(sha, feature_ref), "")}
    )

    assert (
        runner._resolve_live_origin_branch_sha(
            tmp_path, "origin/feature/certification/performance"
        )
        == sha
    )
    assert queried == [feature_ref]


def test_live_origin_resolver_rejects_nontracking_ref_form(tmp_path: Path) -> None:
    with pytest.raises(runner.CertificationError, match="origin tracking ref"):
        runner._resolve_live_origin_branch_sha(
            tmp_path, "refs/remotes/origin/feature/certification"
        )


def test_missing_live_feature_ref_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queried = _install_live_git(monkeypatch, {})

    with pytest.raises(runner.CertificationError, match="missing"):
        runner._resolve_live_origin_branch_sha(tmp_path, "origin/feature/certification")
    assert queried == ["refs/heads/feature/certification"]


@pytest.mark.parametrize(
    "stdout",
    [
        "not-a-sha\trefs/heads/develop\n",
        _ls_remote_line(_BASE_SHA, "refs/heads/develop")
        + _ls_remote_line(_FEATURE_SHA, "refs/heads/develop"),
    ],
)
def test_malformed_or_multiple_live_origin_response_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stdout: str
) -> None:
    _install_live_git(monkeypatch, {"refs/heads/develop": (0, stdout, "")})

    with pytest.raises(runner.CertificationError, match="Malformed live origin"):
        runner._resolve_live_origin_branch_sha(tmp_path, "origin/develop")


def test_live_origin_query_failure_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_live_git(
        monkeypatch,
        {"refs/heads/develop": (128, "", "Could not resolve host")},
    )

    with pytest.raises(runner.CertificationError, match="ls-remote failed"):
        runner._resolve_live_origin_branch_sha(tmp_path, "origin/develop")


@pytest.mark.parametrize("profile", runner.PROFILES)
def test_final_source_verification_repeats_live_origin_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    _profile_inventory(tmp_path, profile)
    monkeypatch.setattr(runner, "DEFAULT_TEMP_ROOT", tmp_path / "temp")
    args = _source_args(
        tmp_path,
        feature_ref="origin/feature/certification",
        feature_head=_FEATURE_SHA,
    )
    _install_source_git_state(monkeypatch, tmp_path, args)
    live_proofs: list[str] = []

    def resolve_live(root: Path, tracking_ref: str) -> str:
        live_proofs.append(tracking_ref)
        return _BASE_SHA if tracking_ref == "origin/develop" else _FEATURE_SHA

    monkeypatch.setattr(runner, "_resolve_live_origin_branch_sha", resolve_live)
    monkeypatch.setattr(
        runner,
        "run_children",
        lambda *args: {name: {"exit_code": 0} for name in _lane_names(profile)},
    )
    monkeypatch.setattr(
        runner,
        "run_static_checks",
        lambda *args: {
            name: {"exit_code": 0}
            for name in ("ruff_check", "ruff_format", "git_diff_check")
        },
    )
    args.python = Path("python")
    args.expected_feature_ref = "origin/feature/certification"
    args.temp_root = tmp_path / "temp"
    args.timeout_seconds = 1
    args.evidence_dir = tmp_path.parent / f"{tmp_path.name}-final-proof"
    args.plan = False
    args.profile = profile

    summary = runner.run(args)

    assert summary["status"] == "passed"
    assert (
        live_proofs
        == [
            "origin/develop",
            "origin/feature/certification",
        ]
        * 3
    )
    assert summary["final_source"]["live_base_head"] == _BASE_SHA
    assert summary["final_source"]["live_feature_head"] == _FEATURE_SHA


def test_failed_child_sets_failed_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _profile_inventory(tmp_path, "full")
    monkeypatch.setattr(
        runner, "verify_source", lambda args: {"head": "h", "tree": "t"}
    )
    monkeypatch.setattr(runner, "DEFAULT_TEMP_ROOT", tmp_path)
    monkeypatch.setattr(
        runner,
        "run_children",
        lambda *args: {
            "broad-1": {"error": "Child exited with 1", "exit_code": 1},
            "broad-2": {"exit_code": 0},
        },
    )
    monkeypatch.setattr(
        runner, "run_static_checks", lambda *args: pytest.fail("static checks ran")
    )
    args = argparse.Namespace(
        root=tmp_path,
        python=Path("python"),
        expected_feature_ref=None,
        expected_feature_head=None,
        timeout_seconds=1,
        evidence_dir=tmp_path.parent / "evidence",
        temp_root=tmp_path,
        plan=False,
    )
    assert runner.run(args)["status"] == "failed"


def test_feature_ref_must_name_origin(tmp_path: Path) -> None:
    args = argparse.Namespace(
        expected_feature_ref="HEAD",
        expected_feature_head="abc",
        timeout_seconds=1,
    )
    with pytest.raises(runner.CertificationError, match="origin tracking ref"):
        runner.run(args)


# Independent frozen baseline, so editing the production allowlist cannot silently
# reduce accepted Architecture 131 coverage.
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
    "runtime": "checkpoint_runner",
    "scripts": "run_test_certification",
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


def test_parser_defaults_to_full_and_rejects_unknown_profile() -> None:
    parser = runner.build_parser()
    assert parser.parse_args(_parser_arguments()).profile == "full"
    for profile in runner.PROFILES:
        assert (
            parser.parse_args(_parser_arguments() + ["--profile", profile]).profile
            == profile
        )
    with pytest.raises(SystemExit) as error:
        parser.parse_args(_parser_arguments() + ["--profile", "unknown"])
    assert error.value.code == 2
    with pytest.raises(runner.CertificationError, match="Unknown"):
        runner.select_inventory((), "unknown")


_PUBLISHED_PREPARE_TEST = "tests/review_paper/test_published_session_prepare.py"
_PREPARE_OPERATOR_TEST = "tests/test_robinhood_prepare_operator.py"
_SUPERVISED_QUALIFICATION_TEST = "tests/test_robinhood_supervised_qualification.py"


def test_current_robinhood_baseline_and_arch131_registration_coverage() -> None:
    from scripts import checkpoint_runner

    root = Path(__file__).resolve().parents[2]
    repository = runner.discover_inventory(root)
    selected = runner.select_inventory(repository, "robinhood")
    assert runner.ROBINHOOD_REQUIRED_MODULES == _EXPECTED_ROBINHOOD
    assert len(runner.ROBINHOOD_REQUIRED_MODULES) == 40
    assert selected == tuple(
        sorted(
            (
                *_EXPECTED_ROBINHOOD,
                _PUBLISHED_PREPARE_TEST,
                _PREPARE_OPERATOR_TEST,
                _SUPERVISED_QUALIFICATION_TEST,
            )
        )
    )
    assert len(selected) == 43
    registered = {
        module
        for name, spec in checkpoint_runner._checkpoint_specs().items()
        if name.startswith("arch131-")
        for module in spec.tests
    }
    assert registered <= set(selected)
    assert not set(runner.SERIAL_MODULES) & set(selected)


def test_current_profile_counts_support_partition_and_serial_allowlist() -> None:
    root = Path(__file__).resolve().parents[2]
    inventory = runner.discover_inventory(root)
    profiles = {
        name: runner.select_inventory(inventory, name)
        for name in ("full", "robinhood", "legacy", "exhaustive")
    }
    assert runner.PROFILES == ("full", "robinhood", "legacy", "exhaustive")
    assert _EXPECTED_FULL == runner.FULL_REQUIRED_MODULES
    assert len(runner.FULL_REQUIRED_MODULES) == 113
    assert profiles["full"] == tuple(
        sorted(
            (
                *_EXPECTED_FULL,
                _PUBLISHED_PREPARE_TEST,
                _PREPARE_OPERATOR_TEST,
                _SUPERVISED_QUALIFICATION_TEST,
            )
        )
    )
    assert _PUBLISHED_PREPARE_TEST in profiles["robinhood"]
    assert _PREPARE_OPERATOR_TEST in profiles["robinhood"]
    assert _PREPARE_OPERATOR_TEST in profiles["full"]
    assert _SUPERVISED_QUALIFICATION_TEST in profiles["robinhood"]
    assert _SUPERVISED_QUALIFICATION_TEST in profiles["full"]
    assert {name: len(value) for name, value in profiles.items()} == {
        "full": 116,
        "robinhood": 43,
        "legacy": 204,
        "exhaustive": 320,
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
    inventory = tuple(sorted((*_EXPECTED_FULL, module)))
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
    root = Path(__file__).resolve().parents[2]
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


def test_robinhood_has_two_deterministic_balanced_nonempty_lanes(
    tmp_path: Path,
) -> None:
    inventory = _profile_inventory(tmp_path, "robinhood")
    lanes = runner.build_lanes(tmp_path, inventory, "robinhood")
    assert tuple(lanes) == _lane_names("robinhood")
    assert all(lanes.values())
    assert lanes == runner.build_lanes(tmp_path, inventory, "robinhood")
    assert tuple(lanes.values()) == runner.balance_broad(tmp_path, inventory)
    runner.validate_partitions(inventory, tuple(lanes.values()))
    weights = [
        sum((tmp_path / module).stat().st_size for module in lane)
        for lane in lanes.values()
    ]
    assert abs(weights[0] - weights[1]) <= max(
        (tmp_path / module).stat().st_size for module in inventory
    )


@pytest.mark.parametrize(
    "lanes", [{}, {"empty": ()}, {"valid": ("test.py",), "empty": ()}]
)
def test_empty_lane_never_launches_pytest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, lanes: dict[str, tuple[str, ...]]
) -> None:
    monkeypatch.setattr(
        runner.subprocess, "Popen", lambda *a, **k: pytest.fail("pytest launched")
    )
    with pytest.raises(runner.CertificationError, match="contain test modules"):
        runner.run_children(SimpleNamespace(), lanes, tmp_path)


@pytest.mark.parametrize("profile", runner.PROFILES)
@pytest.mark.parametrize(
    "outcome", ["pass", "missing", "extra", "wrong", "error", "nonzero", "no_exit_code"]
)
def test_exact_profile_lane_success_accounting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str, outcome: str
) -> None:
    _profile_inventory(tmp_path, profile)
    monkeypatch.setattr(runner, "DEFAULT_TEMP_ROOT", tmp_path)
    monkeypatch.setattr(
        runner, "verify_source", lambda args: {"head": "h", "tree": "t"}
    )
    children = {name: {"exit_code": 0} for name in _lane_names(profile)}
    first = _lane_names(profile)[0]
    if outcome in {"missing", "wrong"}:
        children.pop(first)
    if outcome in {"extra", "wrong"}:
        children["unexpected"] = {"exit_code": 0}
    if outcome == "error":
        children[first]["error"] = "bad evidence"
    if outcome == "nonzero":
        children[first]["exit_code"] = 1
    if outcome == "no_exit_code":
        children[first] = {}
    monkeypatch.setattr(runner, "run_children", lambda *args: children)
    static_calls = []

    def static(*args):
        static_calls.append(True)
        return {
            name: {"exit_code": 0}
            for name in ("ruff_check", "ruff_format", "git_diff_check")
        }

    monkeypatch.setattr(runner, "run_static_checks", static)
    args = argparse.Namespace(
        root=tmp_path,
        python=Path("python"),
        expected_feature_ref=None,
        expected_feature_head=None,
        timeout_seconds=1,
        evidence_dir=tmp_path.parent / f"{tmp_path.name}-accounting",
        temp_root=tmp_path,
        profile=profile,
        plan=False,
    )
    result = runner.run(args)
    assert result["status"] == ("passed" if outcome == "pass" else "failed")
    assert bool(static_calls) == (outcome == "pass")


@pytest.mark.parametrize("profile", runner.PROFILES)
@pytest.mark.parametrize("name", runner.PROTECTED_OPT_INS)
def test_all_profiles_reject_protected_opt_ins_before_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str, name: str
) -> None:
    monkeypatch.setenv(name, "0")
    monkeypatch.setattr(
        runner, "verify_source", lambda *a: pytest.fail("source verification ran")
    )
    args = argparse.Namespace(
        expected_feature_ref=None,
        expected_feature_head=None,
        timeout_seconds=1,
        profile=profile,
    )
    with pytest.raises(runner.CertificationError, match=name):
        runner.run(args)


@pytest.mark.parametrize("profile", runner.PROFILES)
def test_static_checks_remain_whole_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    commands = []

    def fake_run(command, **kwargs):
        assert kwargs["cwd"] == tmp_path
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    args = argparse.Namespace(root=tmp_path, python=Path("python"), profile=profile)
    runner.run_static_checks(args, tmp_path)
    assert commands == [
        ["python", "-m", "ruff", "check", "--no-cache", "."],
        ["python", "-m", "ruff", "format", "--check", "--no-cache", "."],
        ["git", "diff", "--check"],
    ]


@pytest.mark.parametrize("profile", runner.PROFILES)
def test_all_profiles_retain_temp_root_requirement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    monkeypatch.setattr(
        runner, "verify_source", lambda args: {"head": "h", "tree": "t"}
    )
    args = argparse.Namespace(
        root=tmp_path,
        expected_feature_ref=None,
        expected_feature_head=None,
        timeout_seconds=1,
        profile=profile,
        plan=False,
        temp_root=tmp_path,
    )
    with pytest.raises(runner.CertificationError, match="basetemp root"):
        runner.run(args)


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
    ],
)
def test_unclassified_namespace_fails_every_profile(profile: str, module: str) -> None:
    inventory = tuple(sorted((*_EXPECTED_FULL, module)))
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
