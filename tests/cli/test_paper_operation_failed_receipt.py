"""Milestone-5 deterministic FAILED receipt integration coverage."""

from __future__ import annotations

import os
from decimal import ROUND_FLOOR, localcontext
from pathlib import Path

import pytest
from tests.cli.test_paper_operation_inspection import _setup

from trading_bot.cli.checkpoint_transition import run_checkpointed_cycle
from trading_bot.cli.paper_operation import main
from trading_bot.cli.paper_operation_execution import (
    ELIGIBLE_FAILED_RECEIPT_DIAGNOSTICS,
    PaperOperationExecutionClassification,
    execute_paper_operation_once,
)
from trading_bot.runtime import (
    CheckpointedVerifiedSnapshotPaperCycleApplicationError,
    CheckpointedVerifiedSnapshotPaperCycleInsufficientCashError,
    CheckpointedVerifiedSnapshotPaperCycleReconciliationError,
    CheckpointedVerifiedSnapshotPaperCycleRestorationError,
    CheckpointedVerifiedSnapshotPaperCycleRuntimeExecutionError,
    PaperOperationDiagnosticCode,
    PaperOperationStatus,
    parse_paper_operation_receipt,
)

_ELIGIBLE = (
    (
        CheckpointedVerifiedSnapshotPaperCycleInsufficientCashError,
        PaperOperationDiagnosticCode.INSUFFICIENT_CASH,
    ),
    (
        CheckpointedVerifiedSnapshotPaperCycleApplicationError,
        PaperOperationDiagnosticCode.APPLICATION_FAILURE,
    ),
    (
        CheckpointedVerifiedSnapshotPaperCycleRestorationError,
        PaperOperationDiagnosticCode.RESTORATION_FAILURE,
    ),
    (
        CheckpointedVerifiedSnapshotPaperCycleReconciliationError,
        PaperOperationDiagnosticCode.RECONCILIATION_FAILURE,
    ),
    (
        CheckpointedVerifiedSnapshotPaperCycleRuntimeExecutionError,
        PaperOperationDiagnosticCode.RUNTIME_EXECUTION_FAILURE,
    ),
)


def _install_failure(
    monkeypatch: pytest.MonkeyPatch,
    exception_type: type[Exception],
) -> tuple[list[str], list[str]]:
    execution_calls: list[str] = []
    replay_calls: list[str] = []

    def fail_execution(*args, **kwargs):
        execution_calls.append("execution")
        raise exception_type("deterministic execution failure")

    def fail_replay(*args, **kwargs):
        replay_calls.append("replay")
        raise exception_type("deterministic replay failure")

    monkeypatch.setattr(
        "trading_bot.cli.paper_operation_execution."
        "execute_checkpointed_verified_snapshot_paper_cycle",
        fail_execution,
    )
    monkeypatch.setattr(
        "trading_bot.runtime.paper_operation."
        "execute_checkpointed_verified_snapshot_paper_cycle",
        fail_replay,
    )
    return execution_calls, replay_calls


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


def _filesystem_state(root: Path) -> tuple[tuple[str, str, int, bytes | None], ...]:
    retained: list[tuple[str, str, int, bytes | None]] = []
    for path in sorted(root.rglob("*"), key=lambda item: str(item.relative_to(root))):
        relative = path.relative_to(root).as_posix()
        stat_result = path.stat()
        retained.append(
            (
                relative,
                "file" if path.is_file() else "directory",
                stat_result.st_mtime_ns,
                path.read_bytes() if path.is_file() else None,
            )
        )
    return tuple(retained)


@pytest.mark.parametrize(("exception_type", "diagnostic"), _ELIGIBLE)
def test_each_allowlisted_failure_finalizes_verified_failed_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exception_type: type[Exception],
    diagnostic: PaperOperationDiagnosticCode,
) -> None:
    fixture = _setup(tmp_path)
    execution_calls, replay_calls = _install_failure(monkeypatch, exception_type)

    result = execute_paper_operation_once(fixture.operation_root, fixture.inputs)

    assert ELIGIBLE_FAILED_RECEIPT_DIAGNOSTICS == {item[1] for item in _ELIGIBLE}
    assert execution_calls == ["execution"]
    assert replay_calls == ["replay", "replay", "replay"]
    assert (
        result.classification is PaperOperationExecutionClassification.EXECUTION_FAILED
    )
    assert result.diagnostic_code == diagnostic.value
    assert result.receipt_path is not None
    receipt = parse_paper_operation_receipt(result.receipt_path.read_bytes())
    assert receipt.receipt_id == fixture.inputs.intent.operation_id
    assert receipt.status is PaperOperationStatus.FAILED
    assert receipt.diagnostic_code is diagnostic
    assert receipt.outcome is None
    assert receipt.successor_lineage_evidence is None
    assert receipt.transition_report_artifact is None
    assert receipt.successor_checkpoint_artifact is None
    assert receipt.cycle_result_id is None
    assert result.cycle_result_id is None
    assert result.successor_checkpoint_id is None
    assert result.transition_path is None
    assert result.outcome is None
    final, staging = _transition_paths(fixture)
    assert not final.exists()
    assert not staging.exists()


def test_repeated_failed_receipt_is_terminal_without_execution_or_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _setup(tmp_path)
    execution_calls, replay_calls = _install_failure(
        monkeypatch,
        CheckpointedVerifiedSnapshotPaperCycleInsufficientCashError,
    )
    first = execute_paper_operation_once(fixture.operation_root, fixture.inputs)
    assert first.receipt_path is not None
    before = _filesystem_state(fixture.operation_root)
    execution_calls.clear()
    replay_calls.clear()

    repeated = execute_paper_operation_once(fixture.operation_root, fixture.inputs)

    assert execution_calls == []
    assert replay_calls == ["replay", "replay"]
    assert (
        repeated.classification
        is PaperOperationExecutionClassification.EXECUTION_FAILED
    )
    assert repeated.diagnostic_code == "INSUFFICIENT_CASH"
    assert repeated.receipt_path == first.receipt_path
    assert repeated.cycle_result_id is None
    assert repeated.transition_path is None
    assert repeated.outcome is None
    assert _filesystem_state(fixture.operation_root) == before


def test_failed_receipt_bytes_are_root_and_decimal_context_independent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _setup(tmp_path / "first")
    second = _setup(tmp_path / "second")
    _install_failure(
        monkeypatch,
        CheckpointedVerifiedSnapshotPaperCycleInsufficientCashError,
    )
    first_result = execute_paper_operation_once(first.operation_root, first.inputs)
    with localcontext() as context:
        context.prec = 2
        context.rounding = ROUND_FLOOR
        context.Emax = 3
        context.Emin = -3
        second_result = execute_paper_operation_once(
            second.operation_root,
            second.inputs,
        )

    assert first_result.receipt_path is not None
    assert second_result.receipt_path is not None
    assert (
        first_result.receipt_path.read_bytes()
        == second_result.receipt_path.read_bytes()
    )


def test_replay_mismatch_blocks_without_receipt_or_transition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _setup(tmp_path)

    def fail_execution(*args, **kwargs):
        raise CheckpointedVerifiedSnapshotPaperCycleInsufficientCashError(
            "execution-only failure"
        )

    monkeypatch.setattr(
        "trading_bot.cli.paper_operation_execution."
        "execute_checkpointed_verified_snapshot_paper_cycle",
        fail_execution,
    )
    result = execute_paper_operation_once(fixture.operation_root, fixture.inputs)

    assert result.classification is PaperOperationExecutionClassification.BLOCKED
    assert result.diagnostic_code == "FAILED_RECEIPT_REPLAY_VERIFICATION_FAILED"
    assert result.receipt_path is None
    assert not (fixture.operation_root / "paper-operations").exists()
    assert not any(
        "paper-account-transition" in item.name for item in tmp_path.rglob("*")
    )


def test_unexpected_runtime_exception_never_creates_failed_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _setup(tmp_path)

    def fail(*args, **kwargs):
        raise RuntimeError("environmental failure")

    monkeypatch.setattr(
        "trading_bot.cli.paper_operation_execution."
        "execute_checkpointed_verified_snapshot_paper_cycle",
        fail,
    )
    result = execute_paper_operation_once(fixture.operation_root, fixture.inputs)

    assert result.classification is PaperOperationExecutionClassification.BLOCKED
    assert result.diagnostic_code == "RUNTIME_EXCEPTION"
    assert not (fixture.operation_root / "paper-operations").exists()
    final, staging = _transition_paths(fixture)
    assert not final.exists()
    assert not staging.exists()


def test_runtime_created_transition_staging_blocks_failed_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _setup(tmp_path)
    _, staging = _transition_paths(fixture)

    def fail_with_side_effect(*args, **kwargs):
        staging.mkdir()
        raise CheckpointedVerifiedSnapshotPaperCycleInsufficientCashError(
            "invalid side-effecting failure"
        )

    monkeypatch.setattr(
        "trading_bot.cli.paper_operation_execution."
        "execute_checkpointed_verified_snapshot_paper_cycle",
        fail_with_side_effect,
    )
    result = execute_paper_operation_once(fixture.operation_root, fixture.inputs)

    assert result.classification is PaperOperationExecutionClassification.BLOCKED
    assert result.diagnostic_code == "OUTPUT_SAFETY_FAILURE"
    assert staging.is_dir()
    assert not (fixture.operation_root / "paper-operations").exists()


def test_failed_receipt_output_failure_preserves_staging_without_transition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _setup(tmp_path)
    _install_failure(
        monkeypatch,
        CheckpointedVerifiedSnapshotPaperCycleInsufficientCashError,
    )
    original_rename = os.rename

    def fail_receipt_rename(source, destination, *args, **kwargs):
        if Path(source).parent.name == "paper-operations":
            raise OSError("receipt rename failed")
        return original_rename(source, destination, *args, **kwargs)

    monkeypatch.setattr(
        "trading_bot.cli.paper_operation_receipt_output.os.rename",
        fail_receipt_rename,
    )
    result = execute_paper_operation_once(fixture.operation_root, fixture.inputs)
    operations = fixture.operation_root / "paper-operations"
    final_receipt = operations / f"paper-operation-{fixture.inputs.intent.operation_id}"
    staged_receipt = (
        operations / f".paper-operation-{fixture.inputs.intent.operation_id}.staging"
    )

    assert result.classification is PaperOperationExecutionClassification.BLOCKED
    assert result.diagnostic_code == "RECEIPT_OUTPUT_SAFETY_FAILURE"
    assert not final_receipt.exists()
    assert staged_receipt.is_dir()
    final, staging = _transition_paths(fixture)
    assert not final.exists()
    assert not staging.exists()


def test_failed_receipt_serialization_failure_creates_no_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _setup(tmp_path)
    _install_failure(
        monkeypatch,
        CheckpointedVerifiedSnapshotPaperCycleInsufficientCashError,
    )

    def fail_serialization(*args, **kwargs):
        raise ValueError("serialization failed")

    monkeypatch.setattr(
        "trading_bot.cli.paper_operation_execution.serialize_paper_operation_receipt",
        fail_serialization,
    )
    result = execute_paper_operation_once(fixture.operation_root, fixture.inputs)

    assert result.classification is PaperOperationExecutionClassification.BLOCKED
    assert result.diagnostic_code == "RECEIPT_SERIALIZATION_FAILURE"
    assert not (fixture.operation_root / "paper-operations").exists()
    final, staging = _transition_paths(fixture)
    assert not final.exists()
    assert not staging.exists()


def test_failed_receipt_staging_crash_is_preserved_and_blocks_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _setup(tmp_path)
    execution_calls, _ = _install_failure(
        monkeypatch,
        CheckpointedVerifiedSnapshotPaperCycleInsufficientCashError,
    )

    def crash_write(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(
        "trading_bot.cli.paper_operation_receipt_output._write_file",
        crash_write,
    )
    with pytest.raises(KeyboardInterrupt):
        execute_paper_operation_once(fixture.operation_root, fixture.inputs)
    staged_receipt = (
        fixture.operation_root
        / "paper-operations"
        / f".paper-operation-{fixture.inputs.intent.operation_id}.staging"
    )
    assert staged_receipt.is_dir()
    execution_calls.clear()
    monkeypatch.undo()

    def forbidden(*args, **kwargs):
        raise AssertionError("crash-left failed receipt must not retry")

    monkeypatch.setattr(
        "trading_bot.cli.paper_operation_execution."
        "execute_checkpointed_verified_snapshot_paper_cycle",
        forbidden,
    )
    result = execute_paper_operation_once(fixture.operation_root, fixture.inputs)

    assert execution_calls == []
    assert result.classification is PaperOperationExecutionClassification.BLOCKED
    assert result.diagnostic_code == "OPERATION_STAGING_EXISTS"
    assert staged_receipt.is_dir()


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
def test_failed_receipt_reverification_failure_never_reports_recorded_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failed_call: int,
    final_exists: bool,
    staging_exists: bool,
    diagnostic: str,
) -> None:
    fixture = _setup(tmp_path)
    _install_failure(
        monkeypatch,
        CheckpointedVerifiedSnapshotPaperCycleInsufficientCashError,
    )
    from trading_bot.cli import paper_operation_execution as execution_module

    original = execution_module._verify_failed_receipt
    calls = 0

    def fail_selected(*args, **kwargs):
        nonlocal calls
        calls += 1
        return None if calls == failed_call else original(*args, **kwargs)

    monkeypatch.setattr(
        execution_module,
        "_verify_failed_receipt",
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
    transition, transition_staging = _transition_paths(fixture)
    assert not transition.exists()
    assert not transition_staging.exists()


def test_failed_receipt_plus_transition_is_invalid_operation_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _setup(tmp_path)
    _install_failure(
        monkeypatch,
        CheckpointedVerifiedSnapshotPaperCycleInsufficientCashError,
    )
    failed = execute_paper_operation_once(fixture.operation_root, fixture.inputs)
    assert failed.receipt_path is not None
    monkeypatch.undo()
    transition = run_checkpointed_cycle(
        checkpoint_path=fixture.checkpoint_path,
        snapshot_path=fixture.snapshot_path,
        config_path=fixture.cycle_path,
        output_directory=fixture.operation_root,
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("invalid state must not execute")

    monkeypatch.setattr(
        "trading_bot.cli.paper_operation_execution."
        "execute_checkpointed_verified_snapshot_paper_cycle",
        forbidden,
    )
    result = execute_paper_operation_once(fixture.operation_root, fixture.inputs)

    assert result.classification is PaperOperationExecutionClassification.BLOCKED
    assert result.diagnostic_code == "BLOCKED_INVALID_OPERATION_STATE"
    assert result.receipt_path == failed.receipt_path
    assert transition.directory.is_dir()


def test_cli_new_and_recorded_failed_receipt_exit_six_without_fabricated_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = _setup(tmp_path)
    execution_calls, _ = _install_failure(
        monkeypatch,
        CheckpointedVerifiedSnapshotPaperCycleInsufficientCashError,
    )
    arguments = [
        "--config",
        str(fixture.config_path),
        "--operation-root",
        str(fixture.operation_root),
        "--execute-once",
    ]

    assert main(arguments) == 6
    first = capsys.readouterr().out
    assert "classification: EXECUTION_FAILED" in first
    assert "diagnostic: INSUFFICIENT_CASH" in first
    assert "receipt path:" in first
    assert "cycle-result ID:" not in first
    assert "successor checkpoint ID:" not in first
    assert "transition path:" not in first
    assert "outcome:" not in first

    execution_calls.clear()
    assert main(arguments) == 6
    repeated = capsys.readouterr().out
    assert execution_calls == []
    assert "classification: EXECUTION_FAILED" in repeated
    assert "receipt path:" in repeated
