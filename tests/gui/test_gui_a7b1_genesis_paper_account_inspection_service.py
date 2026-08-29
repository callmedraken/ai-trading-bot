"""Focused GUI-A7b1 GENESIS paper-account inspection adapter tests."""

from __future__ import annotations

import hashlib
import inspect
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from trading_bot.domain import Symbol
from trading_bot.gui import (
    PaperAccountCheckpointKindView,
    PaperAccountPageStatus,
    PaperAccountPositionView,
    VerifiedGenesisPaperAccountInspectionService,
    unavailable_paper_account_state,
)
from trading_bot.gui import (
    verified_genesis_paper_account_inspection_service as inspection_module,
)
from trading_bot.portfolio import MetadataEntry
from trading_bot.runtime import (
    PaperAccountCheckpointPosition,
    PaperAccountCheckpointVerificationCode,
    PaperAccountCheckpointVerificationDiagnostic,
    PaperAccountCheckpointVerificationResult,
    PaperAccountCheckpointVerificationStatus,
    PaperAccountGenesisRequest,
    create_genesis_paper_account_checkpoint,
    serialize_paper_account_checkpoint,
    verify_genesis_paper_account_checkpoint,
)

_NOW = datetime(2026, 8, 27, 22, 0, tzinfo=UTC)
_METADATA = (MetadataEntry("source", "gui-a7b1-test"),)


def _checkpoint(
    positions: tuple[PaperAccountCheckpointPosition, ...] | None = None,
):
    if positions is None:
        positions = (
            PaperAccountCheckpointPosition.from_exact_basis(
                Symbol("SPY"), Decimal("2"), Decimal("20")
            ),
        )
    return create_genesis_paper_account_checkpoint(
        PaperAccountGenesisRequest(
            _NOW,
            Decimal("1000.00"),
            positions,
            Decimal("-12.50"),
            _METADATA,
        )
    )


def _artifact(
    tmp_path: Path,
    positions: tuple[PaperAccountCheckpointPosition, ...] | None = None,
) -> tuple[Path, bytes, object]:
    checkpoint = _checkpoint(positions)
    payload = serialize_paper_account_checkpoint(checkpoint)
    path = tmp_path / "explicit-genesis-checkpoint.json"
    path.write_bytes(payload)
    return path, payload, checkpoint


def _unchecked_pass(result, **overrides):
    values = {
        "status": result.status,
        "checkpoint_byte_length": result.checkpoint_byte_length,
        "checkpoint_sha256": result.checkpoint_sha256,
        "checkpoint": result.checkpoint,
        "restored_ledger": result.restored_ledger,
        "restoration_evidence": result.restoration_evidence,
        "diagnostics": result.diagnostics,
    }
    values.update(overrides)
    malformed = object.__new__(PaperAccountCheckpointVerificationResult)
    for field, value in values.items():
        object.__setattr__(malformed, field, value)
    return malformed


def test_valid_genesis_checkpoint_maps_exact_verified_state(tmp_path: Path) -> None:
    path, payload, checkpoint = _artifact(tmp_path)

    state = VerifiedGenesisPaperAccountInspectionService(path).get_paper_account_state()

    assert state.status is PaperAccountPageStatus.VERIFIED
    assert (
        state.message
        == "One local GENESIS paper-account checkpoint was verified offline."
    )
    assert state.account is not None
    account = state.account
    source = checkpoint.account_state
    assert account.checkpoint_kind is PaperAccountCheckpointKindView.GENESIS
    assert account.sequence == checkpoint.sequence == 0
    assert account.checkpoint_id == checkpoint.checkpoint_id
    assert account.lineage_id == checkpoint.lineage_id
    assert account.account_state_id == source.account_state_id
    assert account.compact_state_id == source.compact_ledger_state_id
    assert account.as_of == source.as_of
    assert account.cash == source.cash
    assert account.realized_profit_loss == source.realized_profit_loss
    assert tuple(item.symbol for item in account.positions) == ("SPY",)
    assert account.positions[0] == PaperAccountPositionView(
        symbol="SPY",
        quantity=Decimal("2"),
        total_cost_basis=Decimal("20"),
        average_cost=Decimal("10"),
    )
    assert account.artifact_sha256 == hashlib.sha256(payload).hexdigest()
    assert account.artifact_byte_length == len(payload)


def test_multiple_positions_preserve_verified_checkpoint_order(tmp_path: Path) -> None:
    positions = (
        PaperAccountCheckpointPosition.from_exact_basis(
            Symbol("QQQ"), Decimal("3"), Decimal("30")
        ),
        PaperAccountCheckpointPosition.from_exact_basis(
            Symbol("SPY"), Decimal("2"), Decimal("20")
        ),
        PaperAccountCheckpointPosition.from_exact_basis(
            Symbol("DIA"), Decimal("5"), Decimal("55")
        ),
    )
    path, _, _ = _artifact(tmp_path, positions)

    state = VerifiedGenesisPaperAccountInspectionService(path).get_paper_account_state()

    assert state.account is not None
    assert tuple(item.symbol for item in state.account.positions) == (
        "QQQ",
        "SPY",
        "DIA",
    )


def test_matching_expected_evidence_is_forwarded_to_verifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, payload, _ = _artifact(tmp_path)
    expected_sha256 = hashlib.sha256(payload).hexdigest()
    expected_byte_length = len(payload)
    real_verify = inspection_module.verify_genesis_paper_account_checkpoint
    calls: list[tuple[bytes, dict[str, object]]] = []

    def recording_verify(payload, **kwargs):
        calls.append((payload, kwargs))
        return real_verify(payload, **kwargs)

    monkeypatch.setattr(
        inspection_module,
        "verify_genesis_paper_account_checkpoint",
        recording_verify,
    )

    state = VerifiedGenesisPaperAccountInspectionService(
        path,
        expected_sha256=expected_sha256,
        expected_byte_length=expected_byte_length,
    ).get_paper_account_state()

    assert state.status is PaperAccountPageStatus.VERIFIED
    assert calls == [
        (
            payload,
            {
                "expected_checkpoint_sha256": expected_sha256,
                "expected_checkpoint_byte_length": expected_byte_length,
            },
        )
    ]


def test_verifier_computed_evidence_is_mapped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, payload, _ = _artifact(tmp_path)
    result = verify_genesis_paper_account_checkpoint(payload)
    verifier_sha256 = "b" * 64
    verifier_byte_length = 777
    monkeypatch.setattr(
        inspection_module,
        "verify_genesis_paper_account_checkpoint",
        lambda *args, **kwargs: _unchecked_pass(
            result,
            checkpoint_sha256=verifier_sha256,
            checkpoint_byte_length=verifier_byte_length,
        ),
    )

    state = VerifiedGenesisPaperAccountInspectionService(path).get_paper_account_state()

    assert state.status is PaperAccountPageStatus.VERIFIED
    assert state.account is not None
    assert state.account.artifact_sha256 == verifier_sha256
    assert state.account.artifact_byte_length == verifier_byte_length


def test_verifier_is_called_once_per_state_acquisition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _, _ = _artifact(tmp_path)
    real_verify = inspection_module.verify_genesis_paper_account_checkpoint
    calls = 0

    def recording_verify(payload, **kwargs):
        nonlocal calls
        calls += 1
        return real_verify(payload, **kwargs)

    monkeypatch.setattr(
        inspection_module,
        "verify_genesis_paper_account_checkpoint",
        recording_verify,
    )
    service = VerifiedGenesisPaperAccountInspectionService(path)

    assert service.get_paper_account_state().status is PaperAccountPageStatus.VERIFIED
    assert service.get_paper_account_state().status is PaperAccountPageStatus.VERIFIED
    assert calls == 2


def test_explicit_artifact_is_read_once_with_bounded_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _, _ = _artifact(tmp_path)
    original_open = Path.open
    open_calls: list[Path] = []
    read_calls: list[int] = []

    class CountingStream:
        def __init__(self, stream) -> None:
            self._stream = stream

        def __enter__(self):
            self._stream.__enter__()
            return self

        def __exit__(self, *args):
            return self._stream.__exit__(*args)

        def read(self, size=-1):
            read_calls.append(size)
            return self._stream.read(size)

    def counting_open(self, *args, **kwargs):
        open_calls.append(self)
        return CountingStream(original_open(self, *args, **kwargs))

    monkeypatch.setattr(Path, "open", counting_open)

    state = VerifiedGenesisPaperAccountInspectionService(path).get_paper_account_state()

    assert state.status is PaperAccountPageStatus.VERIFIED
    assert open_calls == [path]
    assert read_calls == [inspection_module.MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES + 1]


def test_missing_artifact_is_unavailable_without_path_text(tmp_path: Path) -> None:
    path = tmp_path / "private-secret-checkpoint.json"

    state = VerifiedGenesisPaperAccountInspectionService(path).get_paper_account_state()

    assert state == unavailable_paper_account_state()
    assert str(path) not in state.message


def test_unreadable_artifact_is_unavailable_without_raw_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _, _ = _artifact(tmp_path)

    def fail_open(*args, **kwargs):
        raise OSError(f"private path {path} cannot be read")

    monkeypatch.setattr(Path, "open", fail_open)

    state = VerifiedGenesisPaperAccountInspectionService(path).get_paper_account_state()

    assert state == unavailable_paper_account_state()
    assert str(path) not in state.message
    assert "private path" not in state.message


def test_oversized_artifact_is_rejected_before_verifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "oversized.json"
    path.write_bytes(b"123456789")
    monkeypatch.setattr(inspection_module, "MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES", 8)

    def unexpected_verify(*args, **kwargs):
        raise AssertionError("oversized artifact reached verifier")

    monkeypatch.setattr(
        inspection_module,
        "verify_genesis_paper_account_checkpoint",
        unexpected_verify,
    )

    state = VerifiedGenesisPaperAccountInspectionService(path).get_paper_account_state()

    assert state == unavailable_paper_account_state()


@pytest.mark.parametrize(
    "service_kwargs",
    (
        {"expected_sha256": "not-a-sha"},
        {"expected_byte_length": True},
    ),
)
def test_malformed_expected_evidence_is_unavailable(
    tmp_path: Path, service_kwargs: dict[str, object]
) -> None:
    path, _, _ = _artifact(tmp_path)

    state = VerifiedGenesisPaperAccountInspectionService(
        path, **service_kwargs
    ).get_paper_account_state()

    assert state == unavailable_paper_account_state()


def test_verifier_fail_is_unavailable(tmp_path: Path) -> None:
    path = tmp_path / "malformed.json"
    path.write_bytes(b"not a canonical checkpoint")

    state = VerifiedGenesisPaperAccountInspectionService(path).get_paper_account_state()

    assert state == unavailable_paper_account_state()


@pytest.mark.parametrize(
    "missing_field", ("checkpoint", "restored_ledger", "restoration_evidence")
)
def test_incomplete_pass_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    missing_field: str,
) -> None:
    path, payload, _ = _artifact(tmp_path)
    result = verify_genesis_paper_account_checkpoint(payload)
    monkeypatch.setattr(
        inspection_module,
        "verify_genesis_paper_account_checkpoint",
        lambda *args, **kwargs: _unchecked_pass(result, **{missing_field: None}),
    )

    state = VerifiedGenesisPaperAccountInspectionService(path).get_paper_account_state()

    assert state == unavailable_paper_account_state()


def test_pass_with_diagnostics_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, payload, _ = _artifact(tmp_path)
    result = verify_genesis_paper_account_checkpoint(payload)
    diagnostic = PaperAccountCheckpointVerificationDiagnostic(
        PaperAccountCheckpointVerificationCode.CHECKPOINT_SYNTAX_FAILURE,
        "raw diagnostic secret path",
    )
    monkeypatch.setattr(
        inspection_module,
        "verify_genesis_paper_account_checkpoint",
        lambda *args, **kwargs: _unchecked_pass(result, diagnostics=(diagnostic,)),
    )

    state = VerifiedGenesisPaperAccountInspectionService(path).get_paper_account_state()

    assert state == unavailable_paper_account_state()
    assert "raw diagnostic" not in state.message
    assert "secret path" not in state.message


def test_unexpected_verifier_result_type_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _, _ = _artifact(tmp_path)
    monkeypatch.setattr(
        inspection_module,
        "verify_genesis_paper_account_checkpoint",
        lambda *args, **kwargs: object(),
    )

    state = VerifiedGenesisPaperAccountInspectionService(path).get_paper_account_state()

    assert state == unavailable_paper_account_state()


def test_model_adaptation_failure_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _, _ = _artifact(tmp_path)

    def fail_model(*args, **kwargs):
        raise ValueError("model failure reveals private path")

    monkeypatch.setattr(inspection_module, "VerifiedPaperAccountView", fail_model)

    state = VerifiedGenesisPaperAccountInspectionService(path).get_paper_account_state()

    assert state == unavailable_paper_account_state()
    assert "private path" not in state.message


def test_adapter_does_not_discover_latest_or_other_directory_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _, _ = _artifact(tmp_path)
    (tmp_path / "latest-checkpoint.json").write_bytes(b"not selected")

    def forbidden_discovery(*args, **kwargs):
        raise AssertionError("directory discovery is forbidden")

    monkeypatch.setattr(Path, "iterdir", forbidden_discovery)
    monkeypatch.setattr(Path, "glob", forbidden_discovery)
    monkeypatch.setattr(Path, "rglob", forbidden_discovery)

    state = VerifiedGenesisPaperAccountInspectionService(path).get_paper_account_state()

    assert state.status is PaperAccountPageStatus.VERIFIED


@pytest.mark.parametrize("path_value", (None, "checkpoint.json", 42))
def test_wrong_path_type_is_unavailable(path_value: object) -> None:
    state = VerifiedGenesisPaperAccountInspectionService(
        path_value  # type: ignore[arg-type]
    ).get_paper_account_state()

    assert state == unavailable_paper_account_state()


def test_no_effectful_or_operational_dependency_is_introduced() -> None:
    source = inspect.getsource(inspection_module).casefold()

    assert all(
        forbidden not in source
        for forbidden in (
            "sqlite",
            "credential",
            "alpaca",
            "brokerage",
            "network",
            "execute",
            "recover",
            "resume",
            "retry",
            "write_bytes",
            "unlink",
            "rename",
            "iterdir",
            "glob",
            "rglob",
        )
    )


def test_incomplete_verifier_status_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, payload, _ = _artifact(tmp_path)
    result = verify_genesis_paper_account_checkpoint(payload)
    incomplete = _unchecked_pass(
        result,
        status=PaperAccountCheckpointVerificationStatus.FAIL,
        diagnostics=(),
    )
    monkeypatch.setattr(
        inspection_module,
        "verify_genesis_paper_account_checkpoint",
        lambda *args, **kwargs: incomplete,
    )

    state = VerifiedGenesisPaperAccountInspectionService(path).get_paper_account_state()

    assert state == unavailable_paper_account_state()
