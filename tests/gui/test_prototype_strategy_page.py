"""Offscreen tests for the cached active-strategy binding page."""

import os
from dataclasses import replace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QScrollArea

from trading_bot.gui.prototype_strategy_page import StrategyPage
from trading_bot.live_prototype.contracts import PrototypeSnapshot, ResearchView


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_strategy_page_default_reports_no_active_binding():
    application = _application()
    snapshot = PrototypeSnapshot()
    page = StrategyPage(snapshot)
    application.processEvents()

    assert page.findChild(QLabel, "strategy_active_strategy").text() == (
        "Unavailable (UNSELECTED)"
    )
    assert page.findChild(QLabel, "strategy_binding_digest").text() == "Unavailable"
    assert page.findChild(QLabel, "strategy_source_head").text() == "Unavailable"
    assert page.findChild(QLabel, "strategy_research_selected").text() == "NOT_RUN"
    assert page.findChild(QLabel, "strategy_research_live_eligible").text() == "No"
    assert page.findChildren(QPushButton) == []
    page.close()


def test_strategy_page_keeps_active_binding_separate_from_research_result():
    application = _application()
    snapshot = PrototypeSnapshot(
        strategy="BASE_MA35_50_V1",
        binding_digest="sha256:active-binding",
        source_head="active-head",
        research=ResearchView(
            selected="PRICE_MOM_252_V1",
            bundle_digest="sha256:research",
            dataset_digest="sha256:data",
            live_eligible=False,
        ),
    )
    page = StrategyPage(snapshot)
    application.processEvents()

    assert page.findChild(QLabel, "strategy_active_strategy").text() == (
        "BASE_MA35_50_V1"
    )
    assert page.findChild(QLabel, "strategy_binding_digest").text() == (
        "sha256:active-binding"
    )
    assert page.findChild(QLabel, "strategy_source_head").text() == "active-head"
    assert page.findChild(QLabel, "strategy_research_selected").text() == (
        "PRICE_MOM_252_V1"
    )
    assert page.findChild(QLabel, "strategy_research_bundle_digest").text() == (
        "sha256:research"
    )
    assert page.findChild(QLabel, "strategy_research_dataset_digest").text() == (
        "sha256:data"
    )
    assert page.findChild(QLabel, "strategy_research_live_eligible").text() == "No"
    assert page.findChildren(QPushButton) == []
    assert page._snapshot.strategy == "BASE_MA35_50_V1"

    literal_snapshot = replace(snapshot, strategy="<b>active</b>")
    page.update_snapshot(literal_snapshot)
    active_strategy = page.findChild(QLabel, "strategy_active_strategy")
    assert active_strategy.text() == "<b>active</b>"
    assert active_strategy.textFormat() == Qt.TextFormat.PlainText
    page.resize(1366, 768)
    page.show()
    application.processEvents()
    scroll = page.findChild(QScrollArea, "prototypeStrategyScroll")
    assert scroll.horizontalScrollBar().maximum() == 0
    page.close()
