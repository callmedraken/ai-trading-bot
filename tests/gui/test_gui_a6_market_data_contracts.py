"""Pure-Python GUI-A6a verified market-data presentation contract tests."""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest

from trading_bot.gui import (
    MAX_MARKET_DATA_MESSAGE_CHARACTERS,
    MAX_MARKET_DATA_PRESENTATION_TEXT_CHARACTERS,
    MAX_MARKET_DATA_SYMBOL_CHARACTERS,
    MAX_MARKET_DATA_SYMBOLS,
    MarketDataPageState,
    MarketDataPageStatus,
    VerifiedMarketSnapshotView,
    unavailable_market_data_state,
)
from trading_bot.gui.mock_service import (
    MockGuiApplicationService,
    ResearchReportGuiApplicationService,
)

_SNAPSHOT_ID = UUID("00000000-0000-0000-0000-000000000010")
_ARTIFACT_SHA256 = "a" * 64
_SOURCE_SHA256 = "b" * 64
_CAPTURED_AT = datetime(2026, 8, 27, 21, 30, tzinfo=UTC)
_PROVIDER_AS_OF = _CAPTURED_AT - timedelta(minutes=1)


def _snapshot(**overrides: object) -> VerifiedMarketSnapshotView:
    values: dict[str, object] = {
        "snapshot_id": _SNAPSHOT_ID,
        "target_session_date": date(2026, 8, 27),
        "symbols": ("SPY",),
        "provider_id": "alpaca-market-data",
        "provider_operation": "historical-stock-bars-v2-raw-usd-no-asof",
        "provider_feed": "iex",
        "artifact_sha256": _ARTIFACT_SHA256,
        "artifact_byte_length": 1234,
        "captured_at": _CAPTURED_AT,
        "provider_as_of": _PROVIDER_AS_OF,
        "source_payload_sha256": _SOURCE_SHA256,
        "source_payload_byte_length": 900,
        "source_payload_media_type": "application/json",
    }
    values.update(overrides)
    return VerifiedMarketSnapshotView(**values)  # type: ignore[arg-type]


def test_market_data_page_state_requires_exact_payload_for_status() -> None:
    snapshot = _snapshot()

    assert (
        MarketDataPageState(
            status=MarketDataPageStatus.VERIFIED,
            message="One verified snapshot artifact is connected.",
            snapshot=snapshot,
        ).snapshot
        is snapshot
    )

    with pytest.raises(ValueError, match="requires one snapshot"):
        MarketDataPageState(
            status=MarketDataPageStatus.VERIFIED,
            message="Missing snapshot.",
            snapshot=None,
        )

    with pytest.raises(ValueError, match="must not contain"):
        MarketDataPageState(
            status=MarketDataPageStatus.UNAVAILABLE,
            message="Unavailable.",
            snapshot=snapshot,
        )


def test_market_data_page_message_is_bounded() -> None:
    MarketDataPageState(
        status=MarketDataPageStatus.UNAVAILABLE,
        message="x" * MAX_MARKET_DATA_MESSAGE_CHARACTERS,
        snapshot=None,
    )

    with pytest.raises(ValueError, match="exceeds the presentation bound"):
        MarketDataPageState(
            status=MarketDataPageStatus.UNAVAILABLE,
            message="x" * (MAX_MARKET_DATA_MESSAGE_CHARACTERS + 1),
            snapshot=None,
        )


def test_verified_snapshot_preserves_exact_bounded_identity_and_order() -> None:
    symbols = ("SPY", "QQQ", "IWM")
    snapshot = _snapshot(symbols=symbols)

    assert snapshot.snapshot_id == _SNAPSHOT_ID
    assert snapshot.target_session_date == date(2026, 8, 27)
    assert snapshot.symbols is symbols
    assert snapshot.provider_id == "alpaca-market-data"
    assert snapshot.provider_operation == "historical-stock-bars-v2-raw-usd-no-asof"
    assert snapshot.provider_feed == "iex"
    assert snapshot.artifact_sha256 == _ARTIFACT_SHA256
    assert snapshot.artifact_byte_length == 1234
    assert snapshot.captured_at == _CAPTURED_AT
    assert snapshot.provider_as_of == _PROVIDER_AS_OF
    assert snapshot.source_payload_sha256 == _SOURCE_SHA256
    assert snapshot.source_payload_byte_length == 900
    assert snapshot.source_payload_media_type == "application/json"


def test_verified_snapshot_rejects_invalid_symbols_and_bounds() -> None:
    with pytest.raises(ValueError, match="between 1 and 100"):
        _snapshot(symbols=())

    with pytest.raises(ValueError, match="between 1 and 100"):
        _snapshot(
            symbols=tuple(f"S{index}" for index in range(MAX_MARKET_DATA_SYMBOLS + 1))
        )

    with pytest.raises(ValueError, match="must be unique"):
        _snapshot(symbols=("SPY", "SPY"))

    with pytest.raises(ValueError, match="invalid presentation text"):
        _snapshot(symbols=("X" * (MAX_MARKET_DATA_SYMBOL_CHARACTERS + 1),))


def test_verified_snapshot_rejects_invalid_evidence() -> None:
    with pytest.raises(ValueError, match="artifact_sha256"):
        _snapshot(artifact_sha256="A" * 64)

    with pytest.raises(ValueError, match="artifact_byte_length"):
        _snapshot(artifact_byte_length=-1)

    with pytest.raises(ValueError, match="source_payload_sha256"):
        _snapshot(source_payload_sha256="not-a-sha")

    with pytest.raises(ValueError, match="source_payload_byte_length"):
        _snapshot(source_payload_byte_length=-1)


def test_verified_snapshot_rejects_invalid_timestamps_and_text() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _snapshot(captured_at=datetime(2026, 8, 27, 21, 30))

    with pytest.raises(ValueError, match="must not follow"):
        _snapshot(provider_as_of=_CAPTURED_AT + timedelta(seconds=1))

    with pytest.raises(ValueError, match="provider_id"):
        _snapshot(provider_id="x" * (MAX_MARKET_DATA_PRESENTATION_TEXT_CHARACTERS + 1))

    with pytest.raises(ValueError, match="source_payload_media_type"):
        _snapshot(source_payload_media_type="application/json\nunsafe")


def test_default_services_return_deterministic_unavailable_market_data_state(
    tmp_path,
) -> None:
    mock = MockGuiApplicationService()
    research = ResearchReportGuiApplicationService(tmp_path / "missing-report.json")

    assert mock.get_market_data_state() == unavailable_market_data_state()
    assert research.get_market_data_state() == unavailable_market_data_state()
    assert mock.get_market_data_state().status is MarketDataPageStatus.UNAVAILABLE


def test_public_market_data_contract_is_qt_free() -> None:
    state = unavailable_market_data_state()

    assert state.status is MarketDataPageStatus.UNAVAILABLE
    assert state.snapshot is None
