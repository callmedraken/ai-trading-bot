"""Real PySide6 minimum-size, recorded-only Supervisor rendering."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QScrollArea

from trading_bot.domain import Symbol
from trading_bot.gui import (
    ProductionRuntimeEvidenceInspectionService,
    ProductionStrategyContractInspectionService,
    build_supervisor_state,
)
from trading_bot.gui.research_service import unavailable_research_state
from trading_bot.gui.supervisor_page import SupervisorPage
from trading_bot.strategies.moving_average import MovingAverageCrossoverConfig
from trading_bot.strategies.production import ProductionStrategyContract


def test_supervisor_plain_selectable_recorded_text_and_minimum_layout(tmp_path):
    application = QApplication.instance() or QApplication([])
    path = tmp_path / "selected.json"
    contract = ProductionStrategyContract(
        date(2026, 10, 12),
        "a" * 40,
        "b" * 40,
        Symbol("SPY"),
        MovingAverageCrossoverConfig(5, 20, Decimal("1.123456789012345678901")),
    )
    path.write_text(contract.to_json(), encoding="utf-8")
    fixtures = Path(__file__).resolve().parents[1] / "fixtures/gui/runtime"
    runtime = ProductionRuntimeEvidenceInspectionService(
        session=fixtures / "session-waiting.json"
    ).get_runtime_state()
    strategy = ProductionStrategyContractInspectionService(
        path
    ).get_production_strategy_state()
    page = SupervisorPage(
        build_supervisor_state(unavailable_research_state(), runtime, strategy)
    )
    page.resize(710, 620)
    page.show()
    application.processEvents()
    labels = page.findChildren(QLabel)
    text = "\n".join(label.text() for label in labels)
    assert "D2 supervisor runtime: Not connected" in text
    assert "Recorded D1 status: WAITING_FOR_MARKET" in text
    assert "TARGET D2 DESIGN ONLY" in text
    assert "Automatic promotion: Disabled" in text
    assert "Human promotion: Required" in text
    assert "Promotion authority: Not connected" in text
    assert "1.123456789012345678901" in text
    assert str(path) not in text
    assert not page.findChildren(QPushButton)
    for label in labels:
        assert label.textFormat() is Qt.TextFormat.PlainText
        assert (
            label.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse
        )
    scroll = page.findChild(QScrollArea, "supervisorScroll")
    assert scroll.horizontalScrollBar().maximum() == 0
    assert scroll.widget().width() <= scroll.viewport().width()
    assert scroll.verticalScrollBar().maximum() > 0
    page.close()
