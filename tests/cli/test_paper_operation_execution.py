"""Focused one-shot paper-operation completion and recovery coverage."""

from __future__ import annotations

import os
import socket
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from tests.cli.test_checkpoint_transition import _no_action_transition_bytes
from tests.cli.test_paper_operation_inspection import (
    _changed_request_cycle,
    _failed_fixture,
    _install_completed_receipt,
    _setup,
    _setup_from_lineage,
)
from tests.runtime.test_paper_account_lineage_verification import _two_edges

from trading_bot.cli.paper_operation import main
from trading_bot.cli.paper_operation_execution import (
    PaperOperationExecutionClassification,
    PaperOperationExecutionDiagnosticCode,
    execute_paper_operation_once,
)
from trading_bot.cli.paper_operation_output_capability import (
    PaperOperationOutputCapability,
)
from trading_bot.runtime import (
    CheckpointedVerifiedSnapshotPaperCycleInsufficientCashError,
    PaperOperationReceiptVerificationStatus,
    verify_paper_operation_receipt,
)


def _transition_paths(fixture) -> tuple[Path, Path]:
    final = (
        fixture.operation_root
        / f"paper-account-transition-{fixture.inputs.application_id}"
    )
    staging = (
        fixture.operation_root
        / f".paper-account-transition-{fixture.inputs.application_id}.staging"
    )
    return final, staging


class _RecordingOutputCapability(PaperOperationOutputCapability):
    def __init__(self, events: list[str]) -> None:
        self.events = events

    @staticmethod
    def _kind(path: Path) -> str:
        return "receipt" if "paper-operations" in str(path) else "transition"

    def verify_parent(self, path: Path) -> None:
        self.events.append(f"verify-parent:{path.name}")
        assert path.is_dir()

    def create_staging_directory(self, path: Path) -> None:
        self.events.append(f"{self._kind(path)}:create-staging")
        os.mkdir(path)

    def write_staged_file(self, path: Path, payload: bytes) -> None:
        self.events.append(f"{self._kind(path)}:write-file")
        with path.open("xb") as stream:
            assert stream.write(payload) == len(payload)
            stream.flush()
            os.fsync(stream.fileno())

    def verify_staged_directory(self, path: Path) -> None:
        self.events.append(f"{self._kind(path)}:verify-staged-directory")

    def verify_staged_file(self, path: Path) -> None:
        self.events.append(f"{self._kind(path)}:verify-staged-file")

    def finalize_directory(self, staging: Path, final: Path) -> None:
        self.events.append(f"{self._kind(staging)}:finalize")
        os.rename(staging, final)

    def verify_finalized_directory(self, path: Path) -> None:
        self.events.append(f"{self._kind(path)}:verify-final-directory")

    def verify_finalized_file(self, path: Path) -> None:
        self.events.append(f"{self._kind(path)}:verify-final-file")


def test_pending_execution_invokes_runtime_once_and_commits_exact_layout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _setup(tmp_path)
    final, staging = _transition_paths(fixture)
    from trading_bot.cli import paper_operation_execution as execution_module

    original = execution_module.execute_checkpointed_verified_snapshot_paper_cycle
    calls = 0

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        execution_module,
        "execute_checkpointed_verified_snapshot_paper_cycle",
        counted,
    )
    result = execute_paper_operation_once(
        fixture.operation_root,
        fixture.inputs,
    )

    assert calls == 1
    assert result.classification is PaperOperationExecutionClassification.COMPLETED
    assert result.outcome is not None
    assert result.outcome.value == "APPLIED"
    assert result.transition_path == final
    assert final.is_dir()
    assert not staging.exists()
    assert result.receipt_path is not None
    assert result.receipt_path.is_file()
    assert {item.name for item in result.receipt_path.parent.iterdir()} == {
        f"paper-operation-receipt-{result.operation_id}.json"
    }
    assert {item.name for item in final.iterdir()} == {
        f"checkpointed-paper-cycle-report-{result.cycle_result_id}.json",
        f"paper-account-checkpoint-{result.successor_checkpoint_id}.json",
    }

    repeated = execute_paper_operation_once(
        fixture.operation_root,
        fixture.inputs,
    )
    assert calls == 1
    assert (
        repeated.classification is PaperOperationExecutionClassification.ALREADY_APPLIED
    )
    assert repeated.diagnostic_code == "ALREADY_APPLIED"
    assert repeated.receipt_path == result.receipt_path


def test_output_capability_hooks_preserve_transition_then_receipt_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _setup(tmp_path)
    (fixture.operation_root / "paper-operations").mkdir()
    events: list[str] = []
    capability = _RecordingOutputCapability(events)
    from trading_bot.cli import paper_operation_execution as execution_module

    original_successor = execution_module._verify_successor
    original_receipt = execution_module._verify_completed_receipt

    def verify_successor(*args, **kwargs):  # type: ignore[no-untyped-def]
        phase = args[6]
        events.append(f"transition:semantic-{phase.value.lower()}")
        return original_successor(*args, **kwargs)

    def verify_receipt(*args, **kwargs):  # type: ignore[no-untyped-def]
        events.append("receipt:semantic")
        return original_receipt(*args, **kwargs)

    monkeypatch.setattr(execution_module, "_verify_successor", verify_successor)
    monkeypatch.setattr(execution_module, "_verify_completed_receipt", verify_receipt)
    result = execute_paper_operation_once(
        fixture.operation_root,
        fixture.inputs,
        output_capability=capability,
    )
    assert result.classification is PaperOperationExecutionClassification.COMPLETED

    assert events.index("transition:create-staging") < events.index(
        "transition:verify-staged-directory"
    )
    assert events.index("transition:verify-staged-directory") < events.index(
        "transition:write-file"
    )
    assert events.index("transition:verify-staged-file") < events.index(
        "transition:semantic-staged"
    )
    assert events.index("transition:semantic-staged") < events.index(
        "transition:finalize"
    )
    assert events.index("transition:finalize") < events.index(
        "transition:verify-final-directory"
    )
    assert events.index("transition:verify-final-file") < events.index(
        "transition:semantic-finalized"
    )

    receipt_create = events.index("receipt:create-staging")
    receipt_staged_security = events.index("receipt:verify-staged-file")
    receipt_finalize = events.index("receipt:finalize")
    receipt_final_security = events.index("receipt:verify-final-file")
    staged_receipt_semantic = events.index("receipt:semantic", receipt_create)
    finalized_receipt_semantic = events.index("receipt:semantic", receipt_finalize)
    assert receipt_create < receipt_staged_security < staged_receipt_semantic
    assert staged_receipt_semantic < receipt_finalize < receipt_final_security
    assert receipt_final_security < finalized_receipt_semantic


def test_output_capability_commits_eligible_failed_receipt_after_runtime_attempt(
    tmp_path: Path,
) -> None:
    fixture = _failed_fixture(tmp_path)
    (fixture.operation_root / "paper-operations").mkdir()
    events: list[str] = []
    result = execute_paper_operation_once(
        fixture.operation_root,
        fixture.inputs,
        output_capability=_RecordingOutputCapability(events),
    )
    assert (
        result.classification is PaperOperationExecutionClassification.EXECUTION_FAILED
    )
    assert result.diagnostic_code == "INSUFFICIENT_CASH"
    assert "receipt:create-staging" in events
    assert "receipt:finalize" in events
    assert not any(event.startswith("transition:create") for event in events)


def test_no_action_still_commits_successor_checkpoint(tmp_path: Path) -> None:
    fixture = _setup(
        tmp_path,
        cycle_payload=_no_action_transition_bytes(),
    )

    result = execute_paper_operation_once(
        fixture.operation_root,
        fixture.inputs,
    )

    assert result.classification is PaperOperationExecutionClassification.COMPLETED
    assert result.outcome is not None
    assert result.outcome.value == "NO_ACTION"
    assert result.successor_checkpoint_id is not None
    assert result.transition_path is not None


@pytest.mark.parametrize(
    ("failure_target", "diagnostic"),
    (
        (
            "verify_checkpointed_paper_cycle_successor_edge",
            PaperOperationExecutionDiagnosticCode.PROSPECTIVE_EDGE_VERIFICATION_FAILED,
        ),
        (
            "verify_paper_account_lineage",
            PaperOperationExecutionDiagnosticCode.PROSPECTIVE_LINEAGE_VERIFICATION_FAILED,
        ),
    ),
)
def test_prospective_verification_failure_prevents_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_target: str,
    diagnostic: PaperOperationExecutionDiagnosticCode,
) -> None:
    fixture = _setup(tmp_path)
    final, staging = _transition_paths(fixture)
    monkeypatch.setattr(
        f"trading_bot.cli.paper_operation_execution.{failure_target}",
        lambda *args, **kwargs: SimpleNamespace(status=None, cycle_result=None),
    )

    result = execute_paper_operation_once(
        fixture.operation_root,
        fixture.inputs,
    )

    assert result.classification is PaperOperationExecutionClassification.BLOCKED
    assert result.diagnostic_code == diagnostic.value
    assert not staging.exists()
    assert not final.exists()


@pytest.mark.parametrize(
    (
        "failure_target",
        "failed_phase",
        "diagnostic",
        "final_exists",
        "staging_exists",
    ),
    (
        (
            "verify_checkpointed_paper_cycle_successor_edge",
            "STAGED",
            PaperOperationExecutionDiagnosticCode.STAGED_EDGE_VERIFICATION_FAILED,
            False,
            True,
        ),
        (
            "verify_paper_account_lineage",
            "STAGED",
            PaperOperationExecutionDiagnosticCode.STAGED_LINEAGE_VERIFICATION_FAILED,
            False,
            True,
        ),
        (
            "verify_checkpointed_paper_cycle_successor_edge",
            "FINALIZED",
            PaperOperationExecutionDiagnosticCode.FINALIZED_EDGE_VERIFICATION_FAILED,
            True,
            False,
        ),
        (
            "verify_paper_account_lineage",
            "FINALIZED",
            PaperOperationExecutionDiagnosticCode.FINALIZED_LINEAGE_VERIFICATION_FAILED,
            True,
            False,
        ),
    ),
)
def test_reread_verification_failure_fails_closed_at_durable_phase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_target: str,
    failed_phase: str,
    diagnostic: PaperOperationExecutionDiagnosticCode,
    final_exists: bool,
    staging_exists: bool,
) -> None:
    fixture = _setup(tmp_path)
    final, staging = _transition_paths(fixture)
    from trading_bot.cli import paper_operation_execution as execution_module

    original = getattr(execution_module, failure_target)
    calls = 0

    def fail_selected(*args, **kwargs):
        nonlocal calls
        calls += 1
        if (failed_phase == "STAGED" and calls == 2) or (
            failed_phase == "FINALIZED" and calls == 3
        ):
            return SimpleNamespace(status=None, cycle_result=None)
        return original(*args, **kwargs)

    monkeypatch.setattr(
        execution_module,
        failure_target,
        fail_selected,
    )

    result = execute_paper_operation_once(
        fixture.operation_root,
        fixture.inputs,
    )

    assert result.classification is PaperOperationExecutionClassification.BLOCKED
    assert result.diagnostic_code == diagnostic.value
    assert final.exists() is final_exists
    assert staging.exists() is staging_exists


def test_deterministic_runtime_failure_and_exception_are_not_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deterministic = _failed_fixture(tmp_path / "deterministic")
    first = execute_paper_operation_once(
        deterministic.operation_root,
        deterministic.inputs,
    )
    final, staging = _transition_paths(deterministic)
    assert (
        first.classification is PaperOperationExecutionClassification.EXECUTION_FAILED
    )
    assert first.diagnostic_code == "INSUFFICIENT_CASH"
    assert not final.exists()
    assert not staging.exists()

    exceptional = _setup(tmp_path / "exception")
    calls = 0

    def fail_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise RuntimeError("environmental failure")

    monkeypatch.setattr(
        "trading_bot.cli.paper_operation_execution."
        "execute_checkpointed_verified_snapshot_paper_cycle",
        fail_once,
    )
    second = execute_paper_operation_once(
        exceptional.operation_root,
        exceptional.inputs,
    )
    final, staging = _transition_paths(exceptional)
    assert calls == 1
    assert second.classification is PaperOperationExecutionClassification.BLOCKED
    assert second.diagnostic_code == "RUNTIME_EXCEPTION"
    assert not final.exists()
    assert not staging.exists()


@pytest.mark.parametrize("state", ("staging", "stale", "hostile-final"))
def test_non_pending_state_never_invokes_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    state: str,
) -> None:
    fixture = _setup(tmp_path)
    final, staging = _transition_paths(fixture)
    if state == "staging":
        staging.mkdir()
    elif state == "stale":
        changed = _changed_request_cycle(fixture)
        from trading_bot.cli.checkpoint_transition import run_checkpointed_cycle

        run_checkpointed_cycle(
            checkpoint_path=fixture.checkpoint_path,
            snapshot_path=fixture.snapshot_path,
            config_path=changed,
            output_directory=fixture.operation_root,
        )
    else:
        final.mkdir()
        (final / "hostile.txt").write_bytes(b"x")

    def forbidden(*args, **kwargs):
        raise AssertionError("runtime must not execute")

    monkeypatch.setattr(
        "trading_bot.cli.paper_operation_execution."
        "execute_checkpointed_verified_snapshot_paper_cycle",
        forbidden,
    )
    result = execute_paper_operation_once(
        fixture.operation_root,
        fixture.inputs,
    )

    assert result.classification in (
        PaperOperationExecutionClassification.BLOCKED,
        PaperOperationExecutionClassification.CONFLICTING,
    )
    if state == "staging":
        assert staging.is_dir()
    if state == "hostile-final":
        assert (final / "hostile.txt").read_bytes() == b"x"


def test_already_applied_and_verified_caller_conflict_never_execute(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    already = _setup(tmp_path / "already")
    _install_completed_receipt(already)

    conflicting = _setup(tmp_path / "conflicting")
    changed_cycle = _changed_request_cycle(conflicting)
    _install_completed_receipt(
        conflicting,
        transition_cycle_path=changed_cycle,
        configuration_evidence=(conflicting.inputs.intent.cycle_configuration_artifact),
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("runtime must not execute")

    monkeypatch.setattr(
        "trading_bot.cli.paper_operation_execution."
        "execute_checkpointed_verified_snapshot_paper_cycle",
        forbidden,
    )

    already_result = execute_paper_operation_once(
        already.operation_root,
        already.inputs,
    )
    conflict_result = execute_paper_operation_once(
        conflicting.operation_root,
        conflicting.inputs,
    )

    assert (
        already_result.classification
        is PaperOperationExecutionClassification.ALREADY_APPLIED
    )
    assert (
        conflict_result.classification
        is PaperOperationExecutionClassification.CONFLICTING
    )


def test_parent_identity_change_before_runtime_blocks_without_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _setup(tmp_path)
    from trading_bot.cli import paper_operation_execution as execution_module

    original = execution_module.validate_output_parent
    validations = 0

    def changed_on_second(path):
        nonlocal validations
        validations += 1
        parent = original(path)
        return replace(parent, inode=parent.inode + 1) if validations == 2 else parent

    def forbidden(*args, **kwargs):
        raise AssertionError("runtime must not execute")

    monkeypatch.setattr(
        execution_module,
        "validate_output_parent",
        changed_on_second,
    )
    monkeypatch.setattr(
        execution_module,
        "execute_checkpointed_verified_snapshot_paper_cycle",
        forbidden,
    )

    result = execute_paper_operation_once(
        fixture.operation_root,
        fixture.inputs,
    )

    assert result.classification is PaperOperationExecutionClassification.BLOCKED
    assert result.diagnostic_code == "OPERATION_ROOT_CHANGED"


def test_multi_edge_terminal_predecessor_reaches_runtime_with_verified_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lineage = _two_edges()
    fixture = _setup_from_lineage(
        tmp_path,
        genesis=lineage.genesis,
        terminal_id=lineage.terminal_id,
        successors=lineage.successors,
        reports=lineage.reports,
        lineage_snapshots=lineage.snapshots,
    )

    calls = 0

    def accepted(request, verified_prior, snapshot, calendar):
        nonlocal calls
        calls += 1
        assert verified_prior.sequence == 2
        assert verified_prior.checkpoint_id == lineage.terminal_id
        raise CheckpointedVerifiedSnapshotPaperCycleInsufficientCashError(
            "deterministic test rejection"
        )

    monkeypatch.setattr(
        "trading_bot.cli.paper_operation_execution."
        "execute_checkpointed_verified_snapshot_paper_cycle",
        accepted,
    )

    def replay_failure(*args, **kwargs):
        raise CheckpointedVerifiedSnapshotPaperCycleInsufficientCashError(
            "deterministic replay rejection"
        )

    monkeypatch.setattr(
        "trading_bot.runtime.paper_operation."
        "execute_checkpointed_verified_snapshot_paper_cycle",
        replay_failure,
    )
    result = execute_paper_operation_once(
        fixture.operation_root,
        fixture.inputs,
    )

    assert calls == 1
    assert (
        result.classification is PaperOperationExecutionClassification.EXECUTION_FAILED
    )
    assert result.diagnostic_code == "INSUFFICIENT_CASH"


@pytest.mark.parametrize(
    ("crash_target", "staging_exists"),
    (
        ("execute_checkpointed_verified_snapshot_paper_cycle", False),
        ("serialize_checkpointed_paper_cycle_report", False),
        ("verify_checkpointed_paper_cycle_successor_edge", False),
        ("commit_transition_directory", False),
    ),
)
def test_crash_before_or_at_staging_boundary_never_finalizes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    crash_target: str,
    staging_exists: bool,
) -> None:
    fixture = _setup(tmp_path)
    final, staging = _transition_paths(fixture)

    def crash(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(
        f"trading_bot.cli.paper_operation_execution.{crash_target}",
        crash,
    )
    with pytest.raises(KeyboardInterrupt):
        execute_paper_operation_once(fixture.operation_root, fixture.inputs)

    assert not final.exists()
    assert staging.exists() is staging_exists


def test_crash_after_staging_creation_is_preserved_without_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _setup(tmp_path)
    final, staging = _transition_paths(fixture)

    def crash_write(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(
        "trading_bot.cli.checkpoint_transition_output._write_file",
        crash_write,
    )
    with pytest.raises(KeyboardInterrupt):
        execute_paper_operation_once(fixture.operation_root, fixture.inputs)

    assert staging.is_dir()
    assert not final.exists()


@pytest.mark.parametrize(
    ("boundary", "final_exists", "staging_exists"),
    (
        ("staged-verification", False, True),
        ("rename", False, True),
        ("finalized-verification", True, False),
    ),
)
def test_crash_at_durable_commit_boundaries_preserves_observable_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
    final_exists: bool,
    staging_exists: bool,
) -> None:
    fixture = _setup(tmp_path)
    final, staging = _transition_paths(fixture)
    if boundary == "rename":
        monkeypatch.setattr(
            "trading_bot.cli.checkpoint_transition_output.os.rename",
            lambda *args, **kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
        )
    else:
        from trading_bot.cli import paper_operation_execution as execution_module

        original = execution_module.verify_checkpointed_paper_cycle_successor_edge
        calls = 0
        selected = 2 if boundary == "staged-verification" else 3

        def crash_selected(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == selected:
                raise KeyboardInterrupt
            return original(*args, **kwargs)

        monkeypatch.setattr(
            execution_module,
            "verify_checkpointed_paper_cycle_successor_edge",
            crash_selected,
        )

    with pytest.raises(KeyboardInterrupt):
        execute_paper_operation_once(fixture.operation_root, fixture.inputs)

    assert final.exists() is final_exists
    assert staging.exists() is staging_exists


def test_success_path_never_deletes_or_repairs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _setup(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("delete or repair is forbidden")

    monkeypatch.setattr(Path, "unlink", forbidden)
    monkeypatch.setattr(Path, "rmdir", forbidden)
    monkeypatch.setattr(os, "remove", forbidden)
    monkeypatch.setattr(os, "unlink", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(
        "trading_bot.market_data.AlpacaDailySnapshotProvider.fetch",
        forbidden,
    )

    result = execute_paper_operation_once(
        fixture.operation_root,
        fixture.inputs,
    )

    assert result.classification is PaperOperationExecutionClassification.COMPLETED
    assert result.receipt_path is not None


def test_cli_requires_one_mode_and_execute_once_reports_commit(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = _setup(tmp_path)
    missing = main(
        [
            "--config",
            str(fixture.config_path),
            "--operation-root",
            str(fixture.operation_root),
        ]
    )
    assert missing == 2
    capsys.readouterr()
    both = main(
        [
            "--config",
            str(fixture.config_path),
            "--operation-root",
            str(fixture.operation_root),
            "--inspect-only",
            "--execute-once",
        ]
    )
    assert both == 2
    capsys.readouterr()

    exit_code = main(
        [
            "--config",
            str(fixture.config_path),
            "--operation-root",
            str(fixture.operation_root),
            "--execute-once",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "initial inspection classification: PENDING" in captured.out
    assert "classification: COMPLETED" in captured.out
    assert "outcome: APPLIED" in captured.out
    assert "transition path:" in captured.out
    assert "receipt path:" in captured.out


def test_cli_execution_failure_exit_codes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def invoke(fixture) -> int:
        return main(
            [
                "--config",
                str(fixture.config_path),
                "--operation-root",
                str(fixture.operation_root),
                "--execute-once",
            ]
        )

    deterministic = _failed_fixture(tmp_path / "deterministic")
    assert invoke(deterministic) == 6
    capsys.readouterr()

    staged = _setup(tmp_path / "staged")
    _, staging_path = _transition_paths(staged)
    staging_path.mkdir()
    assert invoke(staged) == 8
    capsys.readouterr()

    stale = _setup(tmp_path / "stale")
    changed = _changed_request_cycle(stale)
    from trading_bot.cli.checkpoint_transition import run_checkpointed_cycle

    run_checkpointed_cycle(
        checkpoint_path=stale.checkpoint_path,
        snapshot_path=stale.snapshot_path,
        config_path=changed,
        output_directory=stale.operation_root,
    )
    assert invoke(stale) == 5
    capsys.readouterr()

    verification = _setup(tmp_path / "verification")
    monkeypatch.setattr(
        "trading_bot.cli.paper_operation_execution."
        "verify_checkpointed_paper_cycle_successor_edge",
        lambda *args, **kwargs: SimpleNamespace(status=None, cycle_result=None),
    )
    assert invoke(verification) == 4
    capsys.readouterr()
    monkeypatch.undo()

    environmental = _setup(tmp_path / "environmental")

    def fail(*args, **kwargs):
        raise RuntimeError("environmental")

    monkeypatch.setattr(
        "trading_bot.cli.paper_operation_execution."
        "execute_checkpointed_verified_snapshot_paper_cycle",
        fail,
    )
    assert invoke(environmental) == 7


def test_cli_reports_recovery_and_repeated_already_applied(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = _setup(tmp_path)
    from trading_bot.cli import paper_operation_execution as execution_module

    original_commit = execution_module.commit_paper_operation_receipt

    def crash_before_receipt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(
        execution_module,
        "commit_paper_operation_receipt",
        crash_before_receipt,
    )
    with pytest.raises(KeyboardInterrupt):
        execute_paper_operation_once(fixture.operation_root, fixture.inputs)
    monkeypatch.setattr(
        execution_module,
        "commit_paper_operation_receipt",
        original_commit,
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("recovery and repeat must not execute")

    monkeypatch.setattr(
        execution_module,
        "execute_checkpointed_verified_snapshot_paper_cycle",
        forbidden,
    )
    arguments = [
        "--config",
        str(fixture.config_path),
        "--operation-root",
        str(fixture.operation_root),
        "--execute-once",
    ]
    assert main(arguments) == 0
    recovered = capsys.readouterr().out
    assert "classification: RECEIPT_RECOVERED" in recovered
    assert "receipt path:" in recovered

    assert main(arguments) == 0
    repeated = capsys.readouterr().out
    assert "classification: ALREADY_APPLIED" in repeated
    assert "receipt path:" in repeated


def test_completed_receipt_passes_full_offline_verification(tmp_path: Path) -> None:
    fixture = _setup(tmp_path)
    result = execute_paper_operation_once(fixture.operation_root, fixture.inputs)

    assert result.classification is PaperOperationExecutionClassification.COMPLETED
    assert result.receipt_path is not None
    assert result.transition_path is not None
    report_path = next(
        result.transition_path.glob("checkpointed-paper-cycle-report-*.json")
    )
    checkpoint_path = next(
        result.transition_path.glob("paper-account-checkpoint-*.json")
    )
    verification = verify_paper_operation_receipt(
        result.receipt_path.read_bytes(),
        cycle_configuration_payload=fixture.inputs.cycle_configuration_payload,
        prior_genesis_checkpoint=fixture.inputs.prior_genesis_checkpoint,
        prior_successor_checkpoints=fixture.inputs.prior_successor_checkpoints,
        prior_cycle_reports=fixture.inputs.prior_cycle_reports,
        prior_snapshots=fixture.inputs.prior_snapshots,
        completed_snapshot_payload=fixture.inputs.completed_snapshot_payload,
        calendar=fixture.inputs.calendar,
        transition_report_payload=report_path.read_bytes(),
        successor_checkpoint_payload=checkpoint_path.read_bytes(),
    )

    assert verification.status is PaperOperationReceiptVerificationStatus.PASS
    assert verification.receipt is not None
    assert verification.receipt.receipt_id == result.operation_id
    assert verification.receipt.application_id == result.application_id
    assert verification.receipt.cycle_result_id == result.cycle_result_id
    assert (
        verification.receipt.successor_checkpoint_artifact is not None
        and verification.receipt.successor_checkpoint_artifact.artifact_id
        == result.successor_checkpoint_id
    )


def test_crash_after_transition_commit_recovers_byte_identical_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    crashed = _setup(tmp_path / "crashed")
    normal = _setup(tmp_path / "normal")
    from trading_bot.cli import paper_operation_execution as execution_module

    original_commit = execution_module.commit_paper_operation_receipt

    def crash_before_receipt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(
        execution_module,
        "commit_paper_operation_receipt",
        crash_before_receipt,
    )
    with pytest.raises(KeyboardInterrupt):
        execute_paper_operation_once(crashed.operation_root, crashed.inputs)

    transition, _ = _transition_paths(crashed)
    before = {
        item.name: (item.read_bytes(), item.stat().st_mtime_ns)
        for item in transition.iterdir()
    }
    assert not (crashed.operation_root / "paper-operations").exists()

    monkeypatch.setattr(
        execution_module,
        "commit_paper_operation_receipt",
        original_commit,
    )
    normal_result = execute_paper_operation_once(normal.operation_root, normal.inputs)

    def forbidden(*args, **kwargs):
        raise AssertionError("recovery must not execute the runtime")

    monkeypatch.setattr(
        execution_module,
        "execute_checkpointed_verified_snapshot_paper_cycle",
        forbidden,
    )
    recovered = execute_paper_operation_once(crashed.operation_root, crashed.inputs)

    assert (
        recovered.classification
        is PaperOperationExecutionClassification.RECEIPT_RECOVERED
    )
    assert recovered.receipt_path is not None
    assert normal_result.receipt_path is not None
    assert (
        recovered.receipt_path.read_bytes() == normal_result.receipt_path.read_bytes()
    )
    assert before == {
        item.name: (item.read_bytes(), item.stat().st_mtime_ns)
        for item in transition.iterdir()
    }


def test_receipt_staging_crash_blocks_recovery_without_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _setup(tmp_path)

    def crash_write(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(
        "trading_bot.cli.paper_operation_receipt_output._write_file",
        crash_write,
    )
    with pytest.raises(KeyboardInterrupt):
        execute_paper_operation_once(fixture.operation_root, fixture.inputs)

    staging = (
        fixture.operation_root
        / "paper-operations"
        / f".paper-operation-{fixture.inputs.intent.operation_id}.staging"
    )
    assert staging.is_dir()
    monkeypatch.undo()

    def forbidden(*args, **kwargs):
        raise AssertionError("blocked recovery must not execute the runtime")

    monkeypatch.setattr(
        "trading_bot.cli.paper_operation_execution."
        "execute_checkpointed_verified_snapshot_paper_cycle",
        forbidden,
    )
    result = execute_paper_operation_once(fixture.operation_root, fixture.inputs)

    assert result.classification is PaperOperationExecutionClassification.BLOCKED
    assert result.diagnostic_code == "OPERATION_STAGING_EXISTS"
    assert staging.is_dir()


def test_receipt_without_transition_is_invalid_state_and_never_executes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _setup(tmp_path)
    completed = execute_paper_operation_once(
        fixture.operation_root,
        fixture.inputs,
    )
    assert completed.transition_path is not None
    moved_transition = tmp_path / "detached-transition"
    completed.transition_path.rename(moved_transition)

    def forbidden(*args, **kwargs):
        raise AssertionError("invalid operation state must not execute")

    monkeypatch.setattr(
        "trading_bot.cli.paper_operation_execution."
        "execute_checkpointed_verified_snapshot_paper_cycle",
        forbidden,
    )
    result = execute_paper_operation_once(fixture.operation_root, fixture.inputs)

    assert result.classification is PaperOperationExecutionClassification.BLOCKED
    assert result.diagnostic_code == "BLOCKED_INVALID_OPERATION_STATE"
    assert result.receipt_path == completed.receipt_path
    assert moved_transition.is_dir()


@pytest.mark.parametrize(
    ("failed_call", "final_exists", "staging_exists", "diagnostic"),
    (
        (
            2,
            False,
            True,
            "STAGED_RECEIPT_VERIFICATION_FAILED",
        ),
        (
            3,
            True,
            False,
            "FINALIZED_RECEIPT_VERIFICATION_FAILED",
        ),
    ),
)
def test_receipt_reread_verification_failure_preserves_observable_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failed_call: int,
    final_exists: bool,
    staging_exists: bool,
    diagnostic: str,
) -> None:
    fixture = _setup(tmp_path)
    from trading_bot.cli import paper_operation_execution as execution_module

    original = execution_module._verify_completed_receipt
    calls = 0

    def fail_selected(*args, **kwargs):
        nonlocal calls
        calls += 1
        return None if calls == failed_call else original(*args, **kwargs)

    monkeypatch.setattr(
        execution_module,
        "_verify_completed_receipt",
        fail_selected,
    )
    result = execute_paper_operation_once(fixture.operation_root, fixture.inputs)

    operations = fixture.operation_root / "paper-operations"
    final = operations / f"paper-operation-{fixture.inputs.intent.operation_id}"
    staging = (
        operations / f".paper-operation-{fixture.inputs.intent.operation_id}.staging"
    )
    assert result.classification is PaperOperationExecutionClassification.BLOCKED
    assert result.diagnostic_code == diagnostic
    assert final.exists() is final_exists
    assert staging.exists() is staging_exists


def test_receipt_rename_failure_preserves_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _setup(tmp_path)
    original_rename = os.rename

    def fail_receipt_rename(source, destination, *args, **kwargs):
        if Path(source).parent.name == "paper-operations":
            raise OSError("rename failed")
        return original_rename(source, destination, *args, **kwargs)

    monkeypatch.setattr(
        "trading_bot.cli.paper_operation_receipt_output.os.rename",
        fail_receipt_rename,
    )
    result = execute_paper_operation_once(fixture.operation_root, fixture.inputs)
    operations = fixture.operation_root / "paper-operations"
    final = operations / f"paper-operation-{fixture.inputs.intent.operation_id}"
    staging = (
        operations / f".paper-operation-{fixture.inputs.intent.operation_id}.staging"
    )

    assert result.classification is PaperOperationExecutionClassification.BLOCKED
    assert result.diagnostic_code == "RECEIPT_OUTPUT_SAFETY_FAILURE"
    assert not final.exists()
    assert staging.is_dir()
