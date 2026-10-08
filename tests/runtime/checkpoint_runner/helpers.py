from __future__ import annotations

import json
from pathlib import Path

from scripts import checkpoint_runner as runner


def _spec() -> runner.CheckpointSpec:
    return runner.CheckpointSpec(
        name="example",
        description="example",
        tests=("tests/runtime/checkpoint_runner/test_core.py",),
        ruff_paths=(
            "scripts/checkpoint_runner.py",
            "tests/runtime/checkpoint_runner/test_core.py",
        ),
        authority_check=lambda repo: (),
    )


def _outcome(name: str, exit_code: int) -> runner.CommandOutcome:
    return runner.CommandOutcome(
        name=name,
        argv=("tool", name),
        exit_code=exit_code,
        stdout_bytes=0,
        stderr_bytes=0,
        stdout_sha256="0" * 64,
        stderr_sha256="0" * 64,
        stdout_path="stdout",
        stderr_path="stderr",
    )


def _parent_preflight_result(status: str = "PASS") -> dict[str, object]:
    return {
        "status": status,
        "acl_mutation": "NOT_RUN",
        "recursive_acl_mutation": "NOT_RUN",
        "d10_child_mutation": "NOT_RUN",
        "scheduler_mutation": "NOT_RUN",
        "activation": "NOT_RUN",
        "source_launch": "NOT_RUN",
        "provider": "NOT_RUN",
        "Paper-v2": "NOT_RUN",
        "broker": "NOT_RUN",
        "live": "NOT_RUN",
    }


def _r4_preflight_result(
    *,
    status: str = "PASS",
    detail: str | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "status": status,
        "production_filesystem_mutation": "NOT_RUN",
        "rename_1": "NOT_RUN",
        "rename_2": "NOT_RUN",
        "scheduler_mutation": "NOT_RUN",
        "activation": "NOT_RUN",
        "source_launch": "NOT_RUN",
        "provider": "NOT_RUN",
        "Paper-v2": "NOT_RUN",
        "broker": "NOT_RUN",
        "live": "NOT_RUN",
    }
    if detail is not None:
        result["detail"] = detail
    return result


def _r7_result(status: str = "PASS") -> dict[str, object]:
    from scripts import d10_arch128_r7_protected as protected

    result = protected._base()
    if status == "PASS":
        result.update(
            status="PASS",
            stage="COMPLETE",
            authorization="ACCEPTED",
            evidence_provision="CALL_RETURNED",
            scheduler_mutation="CALL_RETURNED",
            lease_publication="PUBLISHED_VERIFIED",
        )
    return result


def _r8_authority_copy(
    tmp_path: Path,
    *,
    addition: str = "",
    old: str = "",
    new: str = "",
    runner_old: str = "",
    runner_new: str = "",
) -> Path:
    root = Path(runner.__file__).resolve().parent.parent
    target = tmp_path / "scripts"
    target.mkdir()
    source = (root / "scripts/d10_arch128_r8_readonly.py").read_text(encoding="utf-8")
    if old:
        assert old in source
        source = source.replace(old, new, 1)
    if addition:
        source = source.replace(
            "    result = _base()", f"    {addition}\n    result = _base()", 1
        )
    (target / "d10_arch128_r8_readonly.py").write_text(source, encoding="utf-8")
    runner_source = (root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
    if runner_old:
        assert runner_old in runner_source
        runner_source = runner_source.replace(runner_old, runner_new, 1)
    (target / "checkpoint_runner.py").write_text(runner_source, encoding="utf-8")
    return tmp_path


def _131i_authority_copy(tmp_path: Path) -> Path:
    repo = Path(runner.__file__).resolve().parent.parent
    for relative in (
        "src/trading_bot/review_paper/intent_bridge.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    return tmp_path


def _131j_authority_copy(tmp_path: Path) -> Path:
    repo = Path(runner.__file__).resolve().parent.parent
    for relative in (
        "src/trading_bot/robinhood_paper_pipeline.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    return tmp_path


_EXPECTED_RETAINED_CHECKPOINTS = (
    "arch128-parent-acl-repair",
    "arch128-r4",
    "arch128-r5-substrate",
    "arch128-r5-trading",
    "arch128-r6",
    "arch128-r7",
    "arch128-r8-terminal-halt",
    "arch130-r8i-d1",
)

_EXPECTED_ACTIVE_CI_CHECKPOINTS = (
    "arch131-robinhood-review-paper",
    "arch131-robinhood-mcp-schema",
    "arch131-robinhood-paper-cycle",
    "arch131-robinhood-performance",
    "arch131-robinhood-direct-mcp",
    "arch131-robinhood-oauth-windows",
    "arch131-robinhood-agentic-account",
    "arch131-robinhood-paper-operator",
    "arch131-robinhood-paper-intent-bridge",
    "arch131-robinhood-deterministic-paper-pipeline",
    "arch131-robinhood-virtual-risk-context",
    "arch131-robinhood-forward-paper-cycle",
    "arch131-robinhood-live-qualification-verifier",
    "arch131-robinhood-session-admission",
    "arch131-robinhood-risk-price-snapshot",
    "arch131-robinhood-forward-paper-preview",
    "arch131-robinhood-risk-price-acquisition",
    "arch131-robinhood-supervised-forward-paper",
    "arch131-robinhood-supervised-prepare-qualification",
    "arch131-robinhood-supervised-prepare-verifier",
    "arch131-nyse-published-regular-session-authority",
    "arch131-robinhood-published-session-prepare",
    "arch131-robinhood-published-prepare-operator",
    "arch131-robinhood-supervised-qualification",
    "arch133-robinhood-unattended-activation-core",
    "arch133-robinhood-unattended-state-store",
    "arch133-robinhood-unattended-one-wake-composition",
    "arch133-robinhood-unattended-review-paper-execution",
    "arch133-robinhood-unattended-host-scheduler-surface",
    "arch133-robinhood-unattended-host-bootstrap",
    "arch133-robinhood-unattended-host-publication",
    "arch133-robinhood-scratch-root-acl-qualification",
    "arch133-robinhood-retained-root-diagnostic",
    "arch133-robinhood-retained-root-acl-recovery",
    "arch133-robinhood-post-publication-verifier",
    "arch133-robinhood-post-publication-stage-diagnostic",
    "arch133-robinhood-publication-state-paper-diagnostic",
    "arch133-robinhood-publication-state-paper-corrected",
    "arch133-robinhood-single-session-scheduler-installation",
)


def _clean_source():
    return {"head": "a" * 40, "tree": "b" * 40, "branch": "example", "porcelain": ""}


def _batch_specs(calls, *, authority_failure=False, authority_exception=False):
    def forbidden():
        raise AssertionError("host/effect capability called")

    def authority(name):
        def check(repo):
            calls.append(name)
            if name == "second" and authority_exception:
                raise RuntimeError("authority unavailable")
            return ("boundary drift",) if name == "second" and authority_failure else ()

        return check

    return tuple(
        runner.CheckpointSpec(
            name=name,
            description=name,
            tests=tests,
            ruff_paths=ruff,
            authority_check=authority(name),
            preflight=forbidden,
            execute=forbidden,
        )
        for name, tests, ruff in (
            ("first", ("tests/shared.py", "tests/first.py"), ("shared.py", "first.py")),
            (
                "second",
                ("tests/second.py", "tests/shared.py"),
                ("second.py", "shared.py"),
            ),
            ("third", ("tests/first.py",), ("third.py", "first.py")),
        )
    )


def _event(monkeypatch, tmp_path, base, name="push"):
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps(
            {"before": base}
            if name == "push"
            else {"pull_request": {"base": {"sha": base}}}
        )
    )
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("GITHUB_EVENT_NAME", name)
    return event


def _131k_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parent.parent
    for relative in (
        "src/trading_bot/review_paper/risk_context.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    return tmp_path


def _131l_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parent.parent
    for relative in (
        "src/trading_bot/robinhood_forward_paper_cycle.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    return tmp_path


def _131lq_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parent.parent
    for relative in (
        "src/trading_bot/robinhood_live_qualification_verifier.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    return tmp_path


def _131m_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parent.parent
    for relative in (
        "src/trading_bot/review_paper/session_admission.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    return tmp_path


def _131n_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parent.parent
    for relative in (
        "src/trading_bot/review_paper/risk_prices.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    return tmp_path


def _131o_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parent.parent
    for relative in (
        "src/trading_bot/review_paper/forward_preview.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    return tmp_path


def _131p_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parent.parent
    for relative in (
        "src/trading_bot/review_paper/risk_price_acquisition.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    return tmp_path


def _131q_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parent.parent
    for relative in (
        "src/trading_bot/review_paper/supervised_forward_paper.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    return tmp_path


_R_PREPARE_BOUNDARIES = (
    (
        "arch131-robinhood-supervised-prepare-qualification",
        "Architecture 131-R supervised PREPARE qualification harness",
        "src/trading_bot/review_paper/prepare_qualification.py",
        "tests/review_paper/test_prepare_qualification.py",
        runner._arch131_prepare_qualification_authority_check,
        "arch131-robinhood-supervised-forward-paper",
    ),
    (
        "arch131-robinhood-supervised-prepare-verifier",
        "Architecture 131-R read-only PREPARE qualification verifier",
        "src/trading_bot/robinhood_prepare_qualification_verifier.py",
        "tests/test_robinhood_prepare_qualification_verifier.py",
        runner._arch131_prepare_verifier_authority_check,
        "arch131-robinhood-supervised-prepare-qualification",
    ),
)


def _131r_copy(tmp_path, boundary):
    repo = Path(runner.__file__).resolve().parent.parent
    for relative in (
        boundary[2],
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    return tmp_path


def _131s_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parent.parent
    for relative in (
        "src/trading_bot/review_paper/nyse_published_regular_sessions.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    return tmp_path


_T_NAME = "arch131-robinhood-published-session-prepare"

_T_SOURCE = "src/trading_bot/review_paper/published_session_prepare.py"

_T_VERIFIER = "src/trading_bot/robinhood_prepare_qualification_verifier.py"

_T_AUTHORITY = runner._arch131_published_session_prepare_authority_check


def _131t_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parents[1]
    for relative in (
        _T_SOURCE,
        _T_VERIFIER,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    return tmp_path


_U_NAME = "arch131-robinhood-published-prepare-operator"

_U_SOURCE = "src/trading_bot/robinhood_prepare_operator.py"

_U_AUTHORITY = runner._arch131_published_prepare_operator_authority_check


def _131u_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parents[1]
    for relative in (
        _U_SOURCE,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    return tmp_path


_A133_NAME = "arch133-robinhood-unattended-activation-core"

_A133_SOURCE = "src/trading_bot/review_paper/unattended_activation.py"

_A133_TEST = "tests/review_paper/test_unattended_activation.py"


def _133a_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parents[1]
    for relative in (
        _A133_SOURCE,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    return tmp_path


_B133_NAME = "arch133-robinhood-unattended-state-store"

_B133_SOURCES = (
    "src/trading_bot/review_paper/unattended_state_schema.py",
    "src/trading_bot/review_paper/unattended_state_store.py",
    "src/trading_bot/review_paper/unattended_state_verifier.py",
)

_B133_TEST = "tests/review_paper/test_unattended_state_store.py"


def _133b_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parents[1]
    for relative in (
        *_B133_SOURCES,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    return tmp_path


_C133_NAME = "arch133-robinhood-unattended-one-wake-composition"

_C133_SOURCE = "src/trading_bot/review_paper/unattended_one_wake.py"

_C133_TEST = "tests/review_paper/test_unattended_one_wake.py"


def _133c_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parents[1]
    for relative in (
        _C133_SOURCE,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    return tmp_path


_D133_NAME = "arch133-robinhood-unattended-review-paper-execution"

_D133_SOURCE = "src/trading_bot/review_paper/unattended_execution.py"

_D133_TEST = "tests/review_paper/test_unattended_execution.py"


def _133d_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parents[1]
    for relative in (
        _D133_SOURCE,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    return tmp_path


_E133_NAME = "arch133-robinhood-unattended-host-scheduler-surface"

_E133_SOURCES = (
    "src/trading_bot/review_paper/unattended_host_identity.py",
    "src/trading_bot/review_paper/unattended_scheduler.py",
    "src/trading_bot/review_paper/unattended_host.py",
    "scripts/run_arch133_unattended_review_paper.py",
)

_E133_TEST = "tests/review_paper/test_unattended_host.py"


def _133e_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parents[1]
    for relative in (
        *_E133_SOURCES,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((repo / relative).read_text(), encoding="utf-8")
    return tmp_path


_G133_NAME = "arch133-robinhood-unattended-host-bootstrap"

_H133_NAME = "arch133-robinhood-unattended-host-publication"


def _133h_copy(tmp_path):
    # The accepted-source test proves PASS; mutation cases need only one local check.
    return _copy_local_authority(tmp_path, runner.ARCH133_PUBLICATION_PINS)


_G133_SOURCES = (
    "src/trading_bot/review_paper/unattended_host_identity.py",
    "src/trading_bot/review_paper/unattended_scheduler.py",
    "src/trading_bot/review_paper/unattended_host.py",
    "src/trading_bot/review_paper/unattended_host_bootstrap.py",
    "scripts/run_arch133_unattended_review_paper.py",
    "scripts/run_arch133_unattended_host_preflight.py",
)


def _133g_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parents[1]
    for relative in (
        *_G133_SOURCES,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((repo / relative).read_text(), encoding="utf-8")
    return tmp_path


_I133_NAME = "arch133-robinhood-scratch-root-acl-qualification"


def _133i_copy(tmp_path, monkeypatch, *, isolate_predecessor=True):
    # Only the predecessor is isolated. The local authority and all local pins,
    # registration, workflow/order and runtime capability checks remain real.
    if isolate_predecessor:
        monkeypatch.setattr(
            runner, "_arch133_host_publication_authority_check", lambda repo: ()
        )
        root = _copy_local_authority(tmp_path, runner.ARCH133_SCRATCH_PINS)
    else:
        root = _copy_chain_authority(tmp_path, runner.ARCH133_SCRATCH_PINS)
    assert runner._arch133_scratch_root_acl_authority_check(root) == ()
    return root


_J133_NAME = "arch133-robinhood-retained-root-diagnostic"


def _133j_copy(tmp_path, monkeypatch, *, isolate_predecessor=True):
    # Only the predecessor is isolated. The local authority and all local pins,
    # registration, workflow/order and runtime capability checks remain real.
    if isolate_predecessor:
        monkeypatch.setattr(
            runner, "_arch133_scratch_root_acl_authority_check", lambda repo: ()
        )
        root = _copy_local_authority(tmp_path, runner.ARCH133_RETAINED_PINS)
    else:
        root = _copy_chain_authority(tmp_path, runner.ARCH133_RETAINED_PINS)
    assert runner._arch133_retained_root_authority_check(root) == ()
    return root


_K133_NAME = "arch133-robinhood-retained-root-acl-recovery"


def _133k_copy(tmp_path, monkeypatch, *, isolate_predecessor=True):
    # Only the predecessor is isolated. The local authority and all local pins,
    # registration, workflow/order and runtime capability checks remain real.
    if isolate_predecessor:
        monkeypatch.setattr(
            runner, "_arch133_retained_root_authority_check", lambda repo: ()
        )
        root = _copy_local_authority(tmp_path, runner.ARCH133_RECOVERY_PINS)
    else:
        root = _copy_chain_authority(tmp_path, runner.ARCH133_RECOVERY_PINS)
    assert runner._arch133_recovery_authority_check(root) == ()
    return root


_L133_NAME = "arch133-robinhood-post-publication-verifier"


def _133l_copy(tmp_path, monkeypatch, *, isolate_predecessor=True):
    # Only the predecessor is isolated. The local authority and all local pins,
    # registration, workflow/order and runtime capability checks remain real.
    if isolate_predecessor:
        monkeypatch.setattr(
            runner, "_arch133_recovery_authority_check", lambda repo: ()
        )
        root = _copy_local_authority(tmp_path, runner.ARCH133_VERIFIER_PINS)
    else:
        root = _copy_chain_authority(tmp_path, runner.ARCH133_VERIFIER_PINS)
    assert runner._arch133_verifier_authority_check(root) == ()
    return root


_M133_NAME = "arch133-robinhood-post-publication-stage-diagnostic"


def _133m_copy(tmp_path, monkeypatch, *, isolate_predecessor=True):
    # Only the predecessor is isolated. The local authority and all local pins,
    # registration, workflow/order and runtime capability checks remain real.
    if isolate_predecessor:
        monkeypatch.setattr(
            runner, "_arch133_verifier_authority_check", lambda repo: ()
        )
        root = _copy_local_authority(tmp_path, runner.ARCH133_DIAGNOSTIC_PINS)
    else:
        root = _copy_chain_authority(tmp_path, runner.ARCH133_DIAGNOSTIC_PINS)
    assert runner._arch133_diagnostic_authority_check(root) == ()
    return root


def _copy_local_authority(tmp_path, pins):
    repo = Path(runner.__file__).resolve().parents[1]
    for relative in (
        *pins,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((repo / relative).read_bytes())
    return tmp_path


def _copy_chain_authority(tmp_path, local_pins):
    # Workflow/order mutations are predecessor integration cases, so retain the
    # complete real chain and copy every predecessor closure without recursive
    # helper assertions. Only local pin/runtime matrices isolate predecessors.
    paths = []
    for pins in (
        runner.ARCH133_PUBLICATION_PINS,
        runner.ARCH133_SCRATCH_PINS,
        runner.ARCH133_RETAINED_PINS,
        runner.ARCH133_RECOVERY_PINS,
        runner.ARCH133_VERIFIER_PINS,
        runner.ARCH133_DIAGNOSTIC_PINS,
        runner.ARCH133_PUBLICATION_DIAGNOSTIC_PINS,
        runner.ARCH133_PUBLICATION_CORRECTED_PINS,
    ):
        paths.extend(pins)
        if pins is local_pins:
            break
    return _copy_local_authority(tmp_path, dict.fromkeys(paths))
