"""GUI-A6b1 explicit verified-snapshot inspection adapter tests."""

import hashlib
from pathlib import Path

import pytest
from tests.market_data.daily_snapshot_test_support import accepted_snapshot

import trading_bot.gui.verified_snapshot_inspection_service as inspection_module
from trading_bot.gui import (
    MarketDataPageStatus,
    VerifiedSnapshotInspectionService,
)
from trading_bot.market_data import serialize_daily_snapshot


def _artifact(tmp_path: Path) -> tuple[Path, bytes]:
    payload = serialize_daily_snapshot(accepted_snapshot())
    path = tmp_path / "snapshot.json"
    path.write_bytes(payload)
    return path, payload


def test_verified_snapshot_adapter_maps_complete_pass_exactly(tmp_path: Path) -> None:
    path, payload = _artifact(tmp_path)

    state = VerifiedSnapshotInspectionService(path).get_market_data_state()

    assert state.status is MarketDataPageStatus.VERIFIED
    assert state.snapshot is not None
    snapshot = state.snapshot
    expected = accepted_snapshot()
    assert snapshot.snapshot_id == expected.snapshot_id
    assert snapshot.target_session_date == expected.target_session.session_date
    assert snapshot.symbols == tuple(str(symbol) for symbol in expected.request.symbols)
    assert snapshot.provider_id == expected.provider.provider_id
    assert snapshot.provider_operation == expected.provider.operation
    assert snapshot.provider_feed == expected.provider.feed
    assert snapshot.artifact_sha256 == hashlib.sha256(payload).hexdigest()
    assert snapshot.artifact_byte_length == len(payload)
    assert snapshot.captured_at == expected.audit.captured_at
    assert snapshot.provider_as_of == expected.audit.provider_as_of
    assert snapshot.source_payload_sha256 == expected.audit.source_payload.sha256
    assert (
        snapshot.source_payload_byte_length
        == expected.audit.source_payload.byte_length
    )
    assert (
        snapshot.source_payload_media_type == expected.audit.source_payload.media_type
    )


def test_verified_snapshot_adapter_accepts_matching_expected_evidence(
    tmp_path: Path,
) -> None:
    path, payload = _artifact(tmp_path)

    state = VerifiedSnapshotInspectionService(
        path,
        expected_sha256=hashlib.sha256(payload).hexdigest(),
        expected_byte_length=len(payload),
    ).get_market_data_state()

    assert state.status is MarketDataPageStatus.VERIFIED


def test_verified_snapshot_adapter_calls_verifier_once_per_state_acquisition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, _ = _artifact(tmp_path)
    real_verify = inspection_module.verify_daily_snapshot
    calls: list[tuple[bytes, object, dict[str, object]]] = []

    def recording_verify(payload, calendar, **kwargs):
        calls.append((payload, calendar, kwargs))
        return real_verify(payload, calendar, **kwargs)

    monkeypatch.setattr(inspection_module, "verify_daily_snapshot", recording_verify)

    state = VerifiedSnapshotInspectionService(path).get_market_data_state()

    assert state.status is MarketDataPageStatus.VERIFIED
    assert len(calls) == 1


def test_verified_snapshot_adapter_rejects_oversized_artifact_before_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "oversized.json"
    path.write_bytes(b"123456789")
    monkeypatch.setattr(inspection_module, "MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES", 8)

    def unexpected_verify(*args, **kwargs):
        raise AssertionError("oversized artifact must not reach the verifier")

    monkeypatch.setattr(inspection_module, "verify_daily_snapshot", unexpected_verify)

    state = VerifiedSnapshotInspectionService(path).get_market_data_state()

    assert state.status is MarketDataPageStatus.UNAVAILABLE
    assert state.snapshot is None


def test_verified_snapshot_adapter_sanitizes_read_and_verification_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = tmp_path / "private-secret-filename.json"
    missing_state = VerifiedSnapshotInspectionService(missing).get_market_data_state()

    assert missing_state.status is MarketDataPageStatus.UNAVAILABLE
    assert str(missing) not in missing_state.message

    path, _ = _artifact(tmp_path)

    def fail_verification(*args, **kwargs):
        raise RuntimeError("provider-native secret diagnostic")

    monkeypatch.setattr(inspection_module, "verify_daily_snapshot", fail_verification)
    failed_state = VerifiedSnapshotInspectionService(path).get_market_data_state()

    assert failed_state.status is MarketDataPageStatus.UNAVAILABLE
    assert "provider-native" not in failed_state.message
    assert "secret" not in failed_state.message


def test_verified_snapshot_adapter_treats_invalid_or_mismatched_evidence_as_unavailable(
    tmp_path: Path,
) -> None:
    path, payload = _artifact(tmp_path)

    invalid = VerifiedSnapshotInspectionService(
        path,
        expected_sha256="not-a-sha",
    ).get_market_data_state()
    mismatched_hash = VerifiedSnapshotInspectionService(
        path,
        expected_sha256="0" * 64,
    ).get_market_data_state()
    mismatched_length = VerifiedSnapshotInspectionService(
        path,
        expected_byte_length=len(payload) + 1,
    ).get_market_data_state()

    assert invalid.status is MarketDataPageStatus.UNAVAILABLE
    assert mismatched_hash.status is MarketDataPageStatus.UNAVAILABLE
    assert mismatched_length.status is MarketDataPageStatus.UNAVAILABLE


def test_verified_snapshot_adapter_does_not_discover_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, _ = _artifact(tmp_path)

    def forbidden_discovery(*args, **kwargs):
        raise AssertionError("snapshot adapter must not discover directory contents")

    monkeypatch.setattr(Path, "iterdir", forbidden_discovery)
    monkeypatch.setattr(Path, "glob", forbidden_discovery)
    monkeypatch.setattr(Path, "rglob", forbidden_discovery)

    state = VerifiedSnapshotInspectionService(path).get_market_data_state()

    assert state.status is MarketDataPageStatus.VERIFIED


def test_verified_snapshot_adapter_reads_only_the_explicit_file_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, _ = _artifact(tmp_path)
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

    state = VerifiedSnapshotInspectionService(path).get_market_data_state()

    assert state.status is MarketDataPageStatus.VERIFIED
    assert open_calls == [path]
    assert read_calls == [inspection_module.MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES + 1]
