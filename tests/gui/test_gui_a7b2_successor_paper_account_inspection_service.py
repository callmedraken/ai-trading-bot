"""Focused GUI-A7b2 successor-edge paper-account inspection adapter tests."""

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest
from tests.runtime.test_checkpointed_paper_cycle_successor import (
    _edge_artifacts,
    _later_cycle_request,
    _later_snapshot_verification,
)
from tests.runtime.test_checkpointed_verified_snapshot_execution import _target
from tests.runtime.test_verified_snapshot_preparation import calendar

from trading_bot.gui import (
    PaperAccountCheckpointKindView,
    PaperAccountPageStatus,
    VerifiedSuccessorPaperAccountInspectionService,
    unavailable_paper_account_state,
)
from trading_bot.gui import (
    verified_successor_paper_account_inspection_service as inspection_module,
)
from trading_bot.market_data import serialize_daily_snapshot
from trading_bot.runtime import (
    PaperAccountCheckpointEdgeVerificationCode,
    PaperAccountCheckpointEdgeVerificationDiagnostic,
    PaperAccountCheckpointEdgeVerificationResult,
    PaperAccountCheckpointEdgeVerificationStatus,
    checkpointed_paper_cycle_report_from_result,
    checkpointed_paper_cycle_report_reference,
    create_successor_paper_account_checkpoint,
    execute_checkpointed_verified_snapshot_paper_cycle,
    serialize_checkpointed_paper_cycle_report,
    serialize_successor_paper_account_checkpoint,
    verified_prior_from_successor_edge,
    verify_checkpointed_paper_cycle_successor_edge,
)


def _write_edge(
    tmp_path: Path,
    *,
    target=None,
    checkpoint=None,
) -> tuple[tuple[Path, Path, Path, Path], tuple[object, ...]]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    artifacts = _edge_artifacts(target=target, checkpoint=checkpoint)
    (
        result,
        report,
        report_payload,
        prior_payload,
        snapshot_payload,
        successor,
        payload,
    ) = artifacts
    paths = (
        tmp_path / "explicit-prior.json",
        tmp_path / "explicit-snapshot.json",
        tmp_path / "explicit-cycle-report.json",
        tmp_path / "explicit-successor.json",
    )
    for path, content in zip(
        paths,
        (prior_payload, snapshot_payload, report_payload, payload),
        strict=True,
    ):
        path.write_bytes(content)
    return paths, (
        result,
        report,
        report_payload,
        prior_payload,
        snapshot_payload,
        successor,
        payload,
    )


def _service(
    paths: tuple[Path, Path, Path, Path],
    **kwargs,
) -> VerifiedSuccessorPaperAccountInspectionService:
    prior, snapshot, report, successor = paths
    return VerifiedSuccessorPaperAccountInspectionService(
        prior,
        snapshot,
        report,
        successor,
        **kwargs,
    )


def _unchecked_result(result, **overrides):
    values = {
        "status": result.status,
        "successor_byte_length": result.successor_byte_length,
        "successor_sha256": result.successor_sha256,
        "cycle_result": result.cycle_result,
        "successor_checkpoint": result.successor_checkpoint,
        "restored_successor_ledger": result.restored_successor_ledger,
        "diagnostics": result.diagnostics,
    }
    values.update(overrides)
    malformed = object.__new__(PaperAccountCheckpointEdgeVerificationResult)
    for field, value in values.items():
        object.__setattr__(malformed, field, value)
    return malformed


def _unchecked_successor(successor, **overrides):
    values = {
        field: getattr(successor, field)
        for field in successor.__dataclass_fields__
        if field != "metadata"
    }
    values["metadata"] = successor.metadata
    values.update(overrides)
    malformed = object.__new__(type(successor))
    for field, value in values.items():
        object.__setattr__(malformed, field, value)
    return malformed


def test_valid_complete_edge_maps_exact_verified_successor_state(
    tmp_path: Path,
) -> None:
    paths, artifacts = _write_edge(tmp_path)
    result, _, _, _, _, successor, payload = artifacts

    state = _service(paths).get_paper_account_state()

    assert state.status is PaperAccountPageStatus.VERIFIED
    assert state.account is not None
    account = state.account
    source = successor.account_state
    compact = source.compact_state
    assert account.checkpoint_kind is PaperAccountCheckpointKindView.CYCLE_SUCCESSOR
    assert account.sequence == successor.sequence
    assert account.checkpoint_id == successor.checkpoint_id
    assert account.lineage_id == successor.lineage_id
    assert account.account_state_id == source.account_state_id
    assert account.compact_state_id == compact.compact_state_id
    assert account.as_of == source.as_of
    assert account.cash == source.cash == result.final_compact_state.cash
    assert account.realized_profit_loss == source.realized_profit_loss_after
    assert account.realized_profit_loss == result.final_realized_profit_loss
    assert account.realized_profit_loss != result.opening_realized_profit_loss
    assert tuple(
        (
            item.symbol,
            item.quantity,
            item.total_cost_basis,
            item.average_cost,
        )
        for item in account.positions
    ) == tuple(
        (
            str(item.symbol),
            item.quantity,
            item.total_cost_basis,
            item.average_cost,
        )
        for item in source.positions
    )
    assert account.artifact_sha256 == hashlib.sha256(payload).hexdigest()
    assert account.artifact_byte_length == len(payload)


def test_multiple_positions_preserve_verified_successor_order(tmp_path: Path) -> None:
    paths, artifacts = _write_edge(
        tmp_path,
        target=_target("4", "4", "777"),
    )
    successor = artifacts[5]

    state = _service(paths).get_paper_account_state()

    assert state.account is not None
    expected_order = tuple(
        str(item.symbol) for item in successor.account_state.positions
    )
    assert len(expected_order) == 2
    assert tuple(item.symbol for item in state.account.positions) == expected_order


def test_expected_successor_evidence_and_prior_are_forwarded_exactly_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, artifacts = _write_edge(tmp_path)
    payload = artifacts[6]
    expected_sha256 = hashlib.sha256(payload).hexdigest()
    expected_length = len(payload)
    real_verify = inspection_module.verify_checkpointed_paper_cycle_successor_edge
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def recording_verify(*args, **kwargs):
        calls.append((args, kwargs))
        return real_verify(*args, **kwargs)

    monkeypatch.setattr(
        inspection_module,
        "verify_checkpointed_paper_cycle_successor_edge",
        recording_verify,
    )

    state = _service(
        paths,
        expected_successor_sha256=expected_sha256,
        expected_successor_byte_length=expected_length,
    ).get_paper_account_state()

    assert state.status is PaperAccountPageStatus.VERIFIED
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[:4] == (artifacts[2], artifacts[3], artifacts[4], artifacts[6])
    assert kwargs == {
        "expected_successor_sha256": expected_sha256,
        "expected_successor_byte_length": expected_length,
        "verified_prior": None,
    }


def test_verifier_computed_successor_evidence_is_mapped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, artifacts = _write_edge(tmp_path)
    result = verify_checkpointed_paper_cycle_successor_edge(
        artifacts[2],
        artifacts[3],
        artifacts[4],
        artifacts[6],
        calendar(),
    )
    monkeypatch.setattr(
        inspection_module,
        "verify_checkpointed_paper_cycle_successor_edge",
        lambda *args, **kwargs: _unchecked_result(
            result,
            successor_sha256="b" * 64,
            successor_byte_length=777,
        ),
    )

    state = _service(paths).get_paper_account_state()

    assert state.account is not None
    assert state.account.artifact_sha256 == "b" * 64
    assert state.account.artifact_byte_length == 777


def test_each_artifact_is_read_once_with_its_bounded_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, _ = _write_edge(tmp_path)
    original_open = Path.open
    calls: list[tuple[Path, int]] = []

    class CountingStream:
        def __init__(self, path, stream) -> None:
            self._path = path
            self._stream = stream

        def __enter__(self):
            self._stream.__enter__()
            return self

        def __exit__(self, *args):
            return self._stream.__exit__(*args)

        def read(self, size=-1):
            calls.append((self._path, size))
            return self._stream.read(size)

    def counting_open(self, *args, **kwargs):
        return CountingStream(self, original_open(self, *args, **kwargs))

    monkeypatch.setattr(Path, "open", counting_open)

    state = _service(paths).get_paper_account_state()

    assert state.status is PaperAccountPageStatus.VERIFIED
    assert calls == [
        (paths[0], inspection_module.MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES + 1),
        (paths[1], inspection_module.MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES + 1),
        (paths[2], inspection_module.MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES + 1),
        (
            paths[3],
            inspection_module.MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES + 1,
        ),
    ]


@pytest.mark.parametrize(
    ("bound_name", "path_index"),
    (
        ("MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES", 0),
        ("MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES", 1),
        ("MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES", 2),
        ("MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES", 3),
    ),
)
def test_each_oversized_artifact_prevents_verifier_invocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bound_name: str,
    path_index: int,
) -> None:
    paths, _ = _write_edge(tmp_path)
    paths[path_index].write_bytes(b"123456789")
    monkeypatch.setattr(inspection_module, bound_name, 8)
    calls = 0

    def unexpected_verify(*args, **kwargs):
        nonlocal calls
        calls += 1
        return object()

    monkeypatch.setattr(
        inspection_module,
        "verify_checkpointed_paper_cycle_successor_edge",
        unexpected_verify,
    )

    state = _service(paths).get_paper_account_state()

    assert state == unavailable_paper_account_state()
    assert calls == 0


@pytest.mark.parametrize("missing_index", range(4))
def test_each_missing_proof_artifact_is_sanitized_unavailable(
    tmp_path: Path,
    missing_index: int,
) -> None:
    paths, _ = _write_edge(tmp_path)
    missing = tmp_path / f"private-missing-{missing_index}.json"
    supplied = list(paths)
    supplied[missing_index] = missing

    state = _service(tuple(supplied)).get_paper_account_state()

    assert state == unavailable_paper_account_state()
    assert str(missing) not in state.message


@pytest.mark.parametrize("unreadable_index", range(4))
def test_each_unreadable_proof_artifact_is_sanitized_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unreadable_index: int,
) -> None:
    paths, _ = _write_edge(tmp_path)
    unreadable = paths[unreadable_index]
    original_open = Path.open

    def selective_failure(self, *args, **kwargs):
        if self == unreadable:
            raise OSError(f"private proof path {unreadable}")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", selective_failure)

    state = _service(paths).get_paper_account_state()

    assert state == unavailable_paper_account_state()
    assert str(unreadable) not in state.message
    assert "private proof" not in state.message


@pytest.mark.parametrize(
    "kwargs",
    (
        {"expected_successor_sha256": "not-a-sha"},
        {"expected_successor_byte_length": True},
        {"expected_successor_byte_length": -1},
    ),
)
def test_malformed_expected_successor_evidence_is_unavailable(
    tmp_path: Path,
    kwargs: dict[str, object],
) -> None:
    paths, _ = _write_edge(tmp_path)

    assert _service(paths, **kwargs).get_paper_account_state() == (
        unavailable_paper_account_state()
    )


def test_edge_fail_and_mismatched_references_are_unavailable(tmp_path: Path) -> None:
    paths, artifacts = _write_edge(tmp_path / "first")
    second_root = tmp_path / "second"
    second_root.mkdir()
    _, second = _write_edge(second_root, target=_target("10", "0", "972.50"))
    paths[3].write_bytes(second[6])

    state = _service(paths).get_paper_account_state()

    assert state == unavailable_paper_account_state()
    direct = verify_checkpointed_paper_cycle_successor_edge(
        artifacts[2],
        artifacts[3],
        artifacts[4],
        second[6],
        calendar(),
    )
    assert direct.status is PaperAccountCheckpointEdgeVerificationStatus.FAIL


@pytest.mark.parametrize(
    "missing_field",
    ("cycle_result", "successor_checkpoint", "restored_successor_ledger"),
)
def test_incomplete_pass_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    missing_field: str,
) -> None:
    paths, artifacts = _write_edge(tmp_path)
    result = verify_checkpointed_paper_cycle_successor_edge(
        artifacts[2], artifacts[3], artifacts[4], artifacts[6], calendar()
    )
    monkeypatch.setattr(
        inspection_module,
        "verify_checkpointed_paper_cycle_successor_edge",
        lambda *args, **kwargs: _unchecked_result(
            result,
            **{missing_field: None},
        ),
    )

    assert (
        _service(paths).get_paper_account_state() == unavailable_paper_account_state()
    )


def test_pass_with_diagnostics_and_raw_details_is_sanitized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, artifacts = _write_edge(tmp_path)
    result = verify_checkpointed_paper_cycle_successor_edge(
        artifacts[2], artifacts[3], artifacts[4], artifacts[6], calendar()
    )
    diagnostic = PaperAccountCheckpointEdgeVerificationDiagnostic(
        PaperAccountCheckpointEdgeVerificationCode.REPORT_REPLAY_FAILURE,
        "raw secret diagnostic path",
    )
    monkeypatch.setattr(
        inspection_module,
        "verify_checkpointed_paper_cycle_successor_edge",
        lambda *args, **kwargs: _unchecked_result(
            result,
            diagnostics=(diagnostic,),
        ),
    )

    state = _service(paths).get_paper_account_state()

    assert state == unavailable_paper_account_state()
    assert "raw secret" not in state.message
    assert "diagnostic path" not in state.message


def test_unexpected_result_wrong_kind_and_model_failure_are_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, artifacts = _write_edge(tmp_path)
    result = verify_checkpointed_paper_cycle_successor_edge(
        artifacts[2], artifacts[3], artifacts[4], artifacts[6], calendar()
    )
    monkeypatch.setattr(
        inspection_module,
        "verify_checkpointed_paper_cycle_successor_edge",
        lambda *args, **kwargs: object(),
    )
    assert (
        _service(paths).get_paper_account_state() == unavailable_paper_account_state()
    )

    malformed_successor = _unchecked_successor(
        result.successor_checkpoint,
        kind=object(),
    )
    monkeypatch.setattr(
        inspection_module,
        "verify_checkpointed_paper_cycle_successor_edge",
        lambda *args, **kwargs: _unchecked_result(
            result,
            successor_checkpoint=malformed_successor,
        ),
    )
    assert (
        _service(paths).get_paper_account_state() == unavailable_paper_account_state()
    )

    monkeypatch.setattr(
        inspection_module,
        "verify_checkpointed_paper_cycle_successor_edge",
        lambda *args, **kwargs: result,
    )

    def fail_model(*args, **kwargs):
        raise ValueError("private adaptation exception")

    monkeypatch.setattr(inspection_module, "VerifiedPaperAccountView", fail_model)
    state = _service(paths).get_paper_account_state()
    assert state == unavailable_paper_account_state()
    assert "private adaptation" not in state.message


def test_successor_prior_form_is_preserved_without_type_discovery(
    tmp_path: Path,
) -> None:
    first = _edge_artifacts()
    first_edge = verify_checkpointed_paper_cycle_successor_edge(
        first[2], first[3], first[4], first[6], calendar()
    )
    verified_prior = verified_prior_from_successor_edge(first_edge)
    snapshot_verification = _later_snapshot_verification()
    result = execute_checkpointed_verified_snapshot_paper_cycle(
        _later_cycle_request(snapshot_verification),
        verified_prior,
        snapshot_verification,
        calendar(),
    )
    report = checkpointed_paper_cycle_report_from_result(result)
    report_payload = serialize_checkpointed_paper_cycle_report(report)
    successor = create_successor_paper_account_checkpoint(
        report.evidence.prior_checkpoint,
        report.evidence.prior_lineage_id,
        result,
        checkpointed_paper_cycle_report_reference(report_payload),
    )
    successor_payload = serialize_successor_paper_account_checkpoint(successor)
    snapshot = snapshot_verification.snapshot
    assert snapshot is not None
    payloads = (
        first[6],
        serialize_daily_snapshot(snapshot),
        report_payload,
        successor_payload,
    )
    paths = tuple(tmp_path / f"edge-{index}.json" for index in range(4))
    for path, payload in zip(paths, payloads, strict=True):
        path.write_bytes(payload)

    state = _service(paths, verified_prior=verified_prior).get_paper_account_state()

    assert state.status is PaperAccountPageStatus.VERIFIED
    assert state.account is not None
    assert state.account.sequence == 2
    assert state.account.checkpoint_id == successor.checkpoint_id


def test_invalid_verified_prior_authority_fails_before_verifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, _ = _write_edge(tmp_path)
    calls = 0

    def unexpected_verify(*args, **kwargs):
        nonlocal calls
        calls += 1
        return object()

    monkeypatch.setattr(
        inspection_module,
        "verify_checkpointed_paper_cycle_successor_edge",
        unexpected_verify,
    )

    state = _service(paths, verified_prior=object()).get_paper_account_state()

    assert state == unavailable_paper_account_state()
    assert calls == 0


def test_successor_artifact_alone_cannot_produce_verified(tmp_path: Path) -> None:
    _, artifacts = _write_edge(tmp_path)
    successor_path = tmp_path / "successor-alone.json"
    successor_path.write_bytes(artifacts[6])
    missing_paths = (
        tmp_path / "missing-prior.json",
        tmp_path / "missing-snapshot.json",
        tmp_path / "missing-report.json",
        successor_path,
    )

    assert _service(missing_paths).get_paper_account_state() == (
        unavailable_paper_account_state()
    )


def test_no_directory_discovery_or_effectful_dependency_is_introduced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, _ = _write_edge(tmp_path)

    def forbidden_discovery(*args, **kwargs):
        raise AssertionError("directory discovery is forbidden")

    monkeypatch.setattr(Path, "iterdir", forbidden_discovery)
    monkeypatch.setattr(Path, "glob", forbidden_discovery)
    monkeypatch.setattr(Path, "rglob", forbidden_discovery)

    assert _service(paths).get_paper_account_state().status is (
        PaperAccountPageStatus.VERIFIED
    )
    source = inspect.getsource(inspection_module).casefold()
    assert all(
        forbidden not in source
        for forbidden in (
            "sqlite",
            "credential",
            "alpaca",
            "brokerage",
            "network",
            "execute_checkpointed_verified_snapshot_paper_cycle(",
            "verify_paper_account_lineage(",
            "recover",
            "resume",
            "retry",
            "write_bytes",
            "unlink",
            "rename",
            ".iterdir(",
            ".glob(",
            ".rglob(",
        )
    )


@pytest.mark.parametrize("wrong_index", range(4))
def test_wrong_path_types_are_unavailable(wrong_index: int) -> None:
    paths: list[object] = [
        Path("prior"),
        Path("snapshot"),
        Path("report"),
        Path("successor"),
    ]
    paths[wrong_index] = "private-path.json"

    state = VerifiedSuccessorPaperAccountInspectionService(
        *paths  # type: ignore[arg-type]
    ).get_paper_account_state()

    assert state == unavailable_paper_account_state()
