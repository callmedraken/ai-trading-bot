import argparse
from pathlib import Path

import pytest

from scripts import run_test_certification as runner

from .helpers import (
    _BASE_SHA,
    _FEATURE_SHA,
    _install_live_git,
    _install_source_git_state,
    _lane_names,
    _ls_remote_line,
    _profile_inventory,
    _source_args,
)


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


def test_feature_ref_must_name_origin(tmp_path: Path) -> None:
    args = argparse.Namespace(
        expected_feature_ref="HEAD",
        expected_feature_head="abc",
        timeout_seconds=1,
    )
    with pytest.raises(runner.CertificationError, match="origin tracking ref"):
        runner.run(args)
