"""Focused offscreen Qt tests for GUI-A6b2 Market Data rendering."""
# ruff: noqa: E402

import os
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from trading_bot.gui import (
    ApplicationOverview,
    MarketDataPageState,
    MarketDataPageStatus,
    PaperAccountPageState,
    PaperPageState,
    ResearchPageState,
    VerifiedMarketSnapshotView,
    unavailable_market_data_state,
    unavailable_paper_account_state,
    unavailable_paper_state,
)
from trading_bot.gui.main_window import MainWindow
from trading_bot.gui.market_data_page import MarketDataPage
from trading_bot.gui.mock_service import MockGuiApplicationService

_SNAPSHOT_ID = UUID("00000000-0000-0000-0000-000000000020")
_CAPTURED_AT = datetime(2026, 8, 27, 21, 30, tzinfo=UTC)
_PROVIDER_AS_OF = datetime(2026, 8, 27, 21, 29, tzinfo=UTC)


def _application() -> QApplication:
    existing = QApplication.instance()
    return existing if existing is not None else QApplication([])


def _verified_state(
    *,
    message: str = "One local market-data snapshot artifact was verified offline.",
    provider_id: str = "alpaca-market-data",
) -> MarketDataPageState:
    return MarketDataPageState(
        status=MarketDataPageStatus.VERIFIED,
        message=message,
        snapshot=VerifiedMarketSnapshotView(
            snapshot_id=_SNAPSHOT_ID,
            target_session_date=date(2026, 8, 27),
            symbols=("SPY", "QQQ"),
            provider_id=provider_id,
            provider_operation="historical-stock-bars-v2-raw-usd-no-asof",
            provider_feed="iex",
            artifact_sha256="a" * 64,
            artifact_byte_length=1234,
            captured_at=_CAPTURED_AT,
            provider_as_of=_PROVIDER_AS_OF,
            source_payload_sha256="b" * 64,
            source_payload_byte_length=900,
            source_payload_media_type="application/json",
        ),
    )


class _RecordingService:
    def __init__(self, market_data_state: MarketDataPageState) -> None:
        self.market_data_state = market_data_state
        self.market_data_calls = 0

    def get_overview(self) -> ApplicationOverview:
        return MockGuiApplicationService().get_overview()

    def get_research_state(self) -> ResearchPageState:
        return MockGuiApplicationService().get_research_state()

    def get_paper_state(self) -> PaperPageState:
        return unavailable_paper_state()

    def get_market_data_state(self) -> MarketDataPageState:
        self.market_data_calls += 1
        return self.market_data_state

    def get_paper_account_state(self) -> PaperAccountPageState:
        return unavailable_paper_account_state()

    def load_research_report(self, artifact_path: Path) -> ResearchPageState:
        return MockGuiApplicationService().load_research_report(artifact_path)


def test_unavailable_page_renders_only_bounded_message_and_status() -> None:
    _application()
    page = MarketDataPage(unavailable_market_data_state())

    texts = [label.text() for label in page.findChildren(QLabel)]

    assert "Unavailable" in texts
    assert any("No verified market-data snapshot" in text for text in texts)
    assert page.findChild(QLabel, "marketDataSnapshotId") is None
    assert page.findChildren(QPushButton) == []


def test_verified_page_renders_each_bounded_field() -> None:
    _application()
    page = MarketDataPage(_verified_state())
    texts = [label.text() for label in page.findChildren(QLabel)]

    assert "Verified Offline" in texts
    assert str(_SNAPSHOT_ID) in texts
    assert "2026-08-27" in texts
    assert "SPY, QQQ" in texts
    assert "alpaca-market-data" in texts
    assert "historical-stock-bars-v2-raw-usd-no-asof" in texts
    assert "iex" in texts
    assert "a" * 64 in texts
    assert "1234" in texts
    assert _CAPTURED_AT.isoformat() in texts
    assert _PROVIDER_AS_OF.isoformat() in texts
    assert "b" * 64 in texts
    assert "900" in texts
    assert "application/json" in texts
    assert page.findChildren(QPushButton) == []


def test_verified_page_handles_absent_provider_as_of_neutrally() -> None:
    _application()
    state = _verified_state()
    snapshot = state.snapshot
    assert snapshot is not None
    page = MarketDataPage(
        MarketDataPageState(
            status=MarketDataPageStatus.VERIFIED,
            message=state.message,
            snapshot=VerifiedMarketSnapshotView(
                snapshot_id=snapshot.snapshot_id,
                target_session_date=snapshot.target_session_date,
                symbols=snapshot.symbols,
                provider_id=snapshot.provider_id,
                provider_operation=snapshot.provider_operation,
                provider_feed=snapshot.provider_feed,
                artifact_sha256=snapshot.artifact_sha256,
                artifact_byte_length=snapshot.artifact_byte_length,
                captured_at=snapshot.captured_at,
                provider_as_of=None,
                source_payload_sha256=snapshot.source_payload_sha256,
                source_payload_byte_length=snapshot.source_payload_byte_length,
                source_payload_media_type=snapshot.source_payload_media_type,
            ),
        )
    )

    provider_as_of = page.findChild(QLabel, "marketDataProviderAsOf")

    assert provider_as_of is not None
    assert provider_as_of.text() == "Not retained"


def test_service_derived_text_is_rendered_as_literal_plain_text() -> None:
    _application()
    page = MarketDataPage(
        _verified_state(
            message="<b>literal message</b>",
            provider_id="<i>literal-provider</i>",
        )
    )

    message = page.findChild(QLabel, "summaryLabel")
    provider = page.findChild(QLabel, "marketDataProviderId")

    assert message is not None
    assert provider is not None
    assert message.text() == "<b>literal message</b>"
    assert provider.text() == "<i>literal-provider</i>"
    assert message.textFormat() is Qt.TextFormat.PlainText
    assert provider.textFormat() is Qt.TextFormat.PlainText
    assert all(
        label.textFormat() is Qt.TextFormat.PlainText
        for label in page.findChildren(QLabel)
    )


def test_navigation_does_not_reinspect_market_data_state() -> None:
    _application()
    service = _RecordingService(unavailable_market_data_state())
    window = MainWindow(service)

    assert service.market_data_calls == 1
    window.select_page("market-data")
    window.select_page("system")
    window.select_page("market-data")

    assert window.current_page_id == "market-data"
    assert service.market_data_calls == 1
    window.close()
