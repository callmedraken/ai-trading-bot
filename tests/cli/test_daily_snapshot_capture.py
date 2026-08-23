from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_bot.cli import daily_snapshot_output
from trading_bot.cli.daily_snapshot_capture import (
    capture_daily_snapshot_artifact,
    main,
)
from trading_bot.cli.exceptions import (
    DailySnapshotArtifactOutputError,
    DailySnapshotCaptureRejectedError,
)
from trading_bot.market_data import (
    AlpacaHttpResponse,
    AlpacaTransportError,
)

KEY = "capture-test-key"
SECRET = "capture-test-secret"
REQUEST_ID = "98dbdaca-e14b-5f10-8ca9-3650e18aa1d8"


def _write_config(path: Path) -> Path:
    value = {
        "schema_version": 1,
        "request_id": REQUEST_ID,
        "symbols": ["SPY", "QQQ"],
        "calendar": {
            "calendar_id": "XNYS",
            "version": "nyse-regular-sessions-1998-2100-v1",
            "exchange_timezone": "America/New_York",
        },
        "timeframe": "1D",
        "adjustment": "RAW",
        "provider": {
            "provider_id": "alpaca-market-data",
            "adapter_version": 1,
            "operation": "historical-stock-bars-v2-raw-usd-no-asof",
            "feed": "sip",
        },
    }
    path.write_text(json.dumps(value), encoding="utf-8", newline="")
    return path


def _body(*, token=None) -> bytes:
    return json.dumps(
        {
            "bars": {
                "QQQ": [
                    {
                        "t": "2025-01-06T05:00:00Z",
                        "o": 200,
                        "h": 205,
                        "l": 198,
                        "c": 203,
                        "v": 2000,
                        "n": 50,
                        "vw": 202.5,
                    }
                ],
                "SPY": [
                    {
                        "t": "2025-01-06T05:00:00Z",
                        "o": 100,
                        "h": 103.5,
                        "l": 99.25,
                        "c": 102.75,
                        "v": 1000,
                    }
                ],
            },
            "next_page_token": token,
        },
        separators=(",", ":"),
    ).encode()


class FakeTransport:
    def __init__(self, body: bytes | None = None) -> None:
        self.body = _body() if body is None else body
        self.calls = []

    def execute(self, request, *, api_key_id, api_secret_key):
        self.calls.append((request, api_key_id, api_secret_key))
        return AlpacaHttpResponse(
            status=200,
            headers=(
                ("Content-Type", "application/json"),
                ("X-Request-ID", "capture-request-1"),
            ),
            body=self.body,
            body_sha256=hashlib.sha256(self.body).hexdigest(),
            body_byte_length=len(self.body),
            request_id="capture-request-1",
            media_type="application/json",
        )


class FixedClock:
    def __init__(self) -> None:
        self.values = iter(
            (
                datetime(2025, 1, 7, 18, tzinfo=UTC),
                datetime(2025, 1, 7, 18, 0, 1, tzinfo=UTC),
            )
        )
        self.calls = 0

    def __call__(self) -> datetime:
        self.calls += 1
        return next(self.values)


def _capture(
    config: Path,
    destination: Path,
    *,
    transport: FakeTransport | None = None,
    clock: FixedClock | None = None,
):
    return capture_daily_snapshot_artifact(
        config_path=config,
        destination_directory=destination,
        transport=FakeTransport() if transport is None else transport,
        clock=FixedClock() if clock is None else clock,
        environment={
            "APCA_API_KEY_ID": KEY,
            "APCA_API_SECRET_KEY": SECRET,
        },
    )


def test_capture_calls_transport_once_and_clock_exactly_twice(
    tmp_path: Path,
) -> None:
    config = _write_config(tmp_path / "capture.json")
    destination = tmp_path / "snapshots"
    destination.mkdir()
    transport = FakeTransport()
    clock = FixedClock()

    result = _capture(
        config,
        destination,
        transport=transport,
        clock=clock,
    )

    assert len(transport.calls) == 1
    assert clock.calls == 2
    assert transport.calls[0][1:] == (KEY, SECRET)
    assert result.artifact_path.name == (
        f"daily-market-data-snapshot-{result.snapshot.snapshot_id}.json"
    )
    assert result.artifact_path.read_bytes()
    assert (
        result.artifact_sha256
        == hashlib.sha256(result.artifact_path.read_bytes()).hexdigest()
    )
    assert result.artifact_byte_length == result.artifact_path.stat().st_size
    assert result.staged_verification.passed
    assert result.staged_verification.snapshot == result.snapshot
    assert not (destination / f".{result.artifact_path.name}.staging").exists()
    combined = (
        repr(result)
        + str(result.artifact_path)
        + result.artifact_path.read_text(encoding="utf-8")
        + repr(transport.calls[0][0])
    )
    assert KEY not in combined
    assert SECRET not in combined


def test_equivalent_captures_in_different_directories_are_byte_identical(
    tmp_path: Path,
) -> None:
    config = _write_config(tmp_path / "capture.json")
    first_directory = tmp_path / "first"
    second_directory = tmp_path / "second"
    first_directory.mkdir()
    second_directory.mkdir()

    first = _capture(config, first_directory)
    second = _capture(config, second_directory)

    assert first.snapshot.snapshot_id == second.snapshot.snapshot_id
    assert first.artifact_path.read_bytes() == second.artifact_path.read_bytes()
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.artifact_byte_length == second.artifact_byte_length


def test_destination_is_validated_before_credentials_are_loaded(
    tmp_path: Path,
) -> None:
    config = _write_config(tmp_path / "capture.json")

    class ExplodingEnvironment(Mapping[str, str]):
        def __getitem__(self, key):
            raise AssertionError("credentials must not be accessed")

        def __iter__(self):
            return iter(())

        def __len__(self):
            return 0

        def get(self, key, default=None):
            raise AssertionError("credentials must not be accessed")

    with pytest.raises(DailySnapshotArtifactOutputError):
        capture_daily_snapshot_artifact(
            config_path=config,
            destination_directory=tmp_path / "missing",
            transport=FakeTransport(),
            clock=FixedClock(),
            environment=ExplodingEnvironment(),
        )


def test_rejected_pagination_creates_no_staging(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "capture.json")
    destination = tmp_path / "snapshots"
    destination.mkdir()
    transport = FakeTransport(_body(token="next-page"))

    with pytest.raises(DailySnapshotCaptureRejectedError):
        _capture(config, destination, transport=transport)

    assert len(transport.calls) == 1
    assert tuple(destination.iterdir()) == ()


def test_existing_final_and_casefold_collision_are_not_replaced(
    tmp_path: Path,
) -> None:
    config = _write_config(tmp_path / "capture.json")
    destination = tmp_path / "snapshots"
    destination.mkdir()
    first = _capture(config, destination)
    original = first.artifact_path.read_bytes()

    with pytest.raises(DailySnapshotArtifactOutputError, match="already exists"):
        _capture(config, destination)

    assert first.artifact_path.read_bytes() == original
    first.artifact_path.unlink()
    collision = destination / first.artifact_path.name.upper()
    collision.write_bytes(b"keep")
    with pytest.raises(DailySnapshotArtifactOutputError, match="already exists"):
        _capture(config, destination)
    assert collision.read_bytes() == b"keep"


def test_preexisting_staging_is_preserved(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "capture.json")
    reference_directory = tmp_path / "reference"
    destination = tmp_path / "snapshots"
    reference_directory.mkdir()
    destination.mkdir()
    reference = _capture(config, reference_directory)
    staging = destination / f".{reference.artifact_path.name}.staging"
    staging.write_bytes(b"keep")

    with pytest.raises(DailySnapshotArtifactOutputError, match="already exists"):
        _capture(config, destination)

    assert staging.read_bytes() == b"keep"


def test_nonregular_and_link_destination_parents_are_rejected(
    tmp_path: Path,
) -> None:
    config = _write_config(tmp_path / "capture.json")
    regular_file = tmp_path / "not-a-directory"
    regular_file.write_bytes(b"x")
    with pytest.raises(DailySnapshotArtifactOutputError):
        _capture(config, regular_file)

    real = tmp_path / "real"
    link = tmp_path / "link"
    real.mkdir()
    try:
        os.symlink(real, link, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable")
    with pytest.raises(DailySnapshotArtifactOutputError):
        _capture(config, link)


def test_detectable_destination_reparse_point_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _write_config(tmp_path / "capture.json")
    destination = tmp_path / "snapshots"
    destination.mkdir()
    retained = os.lstat(destination)
    original_lstat = daily_snapshot_output.os.lstat

    def fake_lstat(path):
        if Path(path) == destination:
            return SimpleNamespace(
                st_mode=retained.st_mode,
                st_dev=retained.st_dev,
                st_ino=retained.st_ino,
                st_file_attributes=0x400,
            )
        return original_lstat(path)

    monkeypatch.setattr(daily_snapshot_output.os, "lstat", fake_lstat)
    with pytest.raises(DailySnapshotArtifactOutputError, match="real directory"):
        _capture(config, destination)


def test_hard_link_failure_has_no_copy_or_rename_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _write_config(tmp_path / "capture.json")
    destination = tmp_path / "snapshots"
    destination.mkdir()
    calls = 0

    def fail_link(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise OSError("hard links unsupported")

    monkeypatch.setattr(os, "link", fail_link)
    with pytest.raises(DailySnapshotArtifactOutputError, match="hard link"):
        _capture(config, destination)

    assert calls == 1
    assert tuple(destination.iterdir()) == ()


def test_concurrent_no_clobber_winner_is_never_removed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _write_config(tmp_path / "capture.json")
    destination = tmp_path / "snapshots"
    destination.mkdir()
    sentinel = b"other writer"

    def race_link(source, target, **kwargs):
        Path(target).write_bytes(sentinel)
        raise FileExistsError("lost final-name race")

    monkeypatch.setattr(os, "link", race_link)
    with pytest.raises(DailySnapshotArtifactOutputError, match="hard link"):
        _capture(config, destination)

    entries = tuple(destination.iterdir())
    assert len(entries) == 1
    assert entries[0].read_bytes() == sentinel


def test_cleanup_refuses_to_remove_replaced_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _write_config(tmp_path / "capture.json")
    destination = tmp_path / "snapshots"
    destination.mkdir()

    def replace_staging(path, expected_identity):
        path.unlink()
        path.mkdir()
        raise DailySnapshotArtifactOutputError("injected staged read failure")

    monkeypatch.setattr(
        daily_snapshot_output,
        "_secure_read_staging",
        replace_staging,
    )
    with pytest.raises(DailySnapshotArtifactOutputError) as caught:
        _capture(config, destination)

    assert caught.value.cleanup_message == (
        "snapshot staging identity changed; cleanup was not attempted"
    )
    entries = tuple(destination.iterdir())
    assert len(entries) == 1
    assert entries[0].is_dir()


def test_staging_unlink_failure_returns_success_with_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _write_config(tmp_path / "capture.json")
    destination = tmp_path / "snapshots"
    destination.mkdir()
    original_unlink = Path.unlink

    def fail_staging_unlink(self, *args, **kwargs):
        if self.name.endswith(".json.staging"):
            raise OSError("cannot unlink")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_staging_unlink)
    result = _capture(config, destination)

    assert result.artifact_path.exists()
    assert result.cleanup_warning == (
        "final artifact installed but staging unlink failed"
    )
    assert (destination / f".{result.artifact_path.name}.staging").exists()


def test_post_install_durability_failure_is_only_a_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _write_config(tmp_path / "capture.json")
    destination = tmp_path / "snapshots"
    destination.mkdir()

    def fsync_directory(path, *, post_install):
        if post_install:
            return "final artifact installed but directory durability flush failed"
        return None

    monkeypatch.setattr(
        daily_snapshot_output,
        "_fsync_directory",
        fsync_directory,
    )
    result = _capture(config, destination)

    assert result.artifact_path.exists()
    assert result.cleanup_warning == (
        "final artifact installed but directory durability flush failed"
    )


def test_staged_verification_failure_cleans_owned_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _write_config(tmp_path / "capture.json")
    destination = tmp_path / "snapshots"
    destination.mkdir()
    original_verify = daily_snapshot_output.verify_daily_snapshot

    def changed_verification(payload, calendar, **kwargs):
        return original_verify(payload + b" ", calendar, **kwargs)

    monkeypatch.setattr(
        daily_snapshot_output,
        "verify_daily_snapshot",
        changed_verification,
    )
    with pytest.raises(DailySnapshotArtifactOutputError, match="verification"):
        _capture(config, destination)

    assert tuple(destination.iterdir()) == ()


def test_cli_provider_failure_is_sanitized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _write_config(tmp_path / "capture.json")
    destination = tmp_path / "snapshots"
    destination.mkdir()

    def fail_capture(**kwargs):
        raise AlpacaTransportError("sanitized provider failure")

    monkeypatch.setattr(
        "trading_bot.cli.daily_snapshot_capture.capture_daily_snapshot_artifact",
        fail_capture,
    )
    exit_code = main(
        [
            "--config",
            str(config),
            "--destination-directory",
            str(destination),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 5
    assert "sanitized provider failure" not in captured.err
    assert "stage UNKNOWN" in captured.err
    assert KEY not in captured.out + captured.err
    assert SECRET not in captured.out + captured.err
