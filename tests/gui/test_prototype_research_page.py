"""Offscreen tests for the cached prototype research page."""

import os
from dataclasses import replace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QScrollArea

from trading_bot.gui.prototype_research_page import ResearchPage
from trading_bot.live_prototype.contracts import (
    CandidateView,
    PrototypeSnapshot,
    ResearchView,
)


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_research_page_default_is_unavailable_and_not_an_active_binding():
    application = _application()
    snapshot = PrototypeSnapshot()
    page = ResearchPage(snapshot)
    application.processEvents()

    assert page.findChild(QLabel, "research_selected").text() == "NOT_RUN"
    assert page.findChild(QLabel, "research_bundle_digest").text() == "Unavailable"
    assert page.findChild(QLabel, "research_dataset_digest").text() == "Unavailable"
    assert page.findChild(QLabel, "research_prior_trials").text() == "30"
    assert page.findChild(QLabel, "research_new_trials").text() == "3"
    assert page.findChild(QLabel, "research_live_eligible").text() == "No"
    assert (
        page.findChild(QLabel, "research_active_strategy").text()
        == "Unavailable (UNSELECTED)"
    )
    assert page.findChild(QLabel, "research_active_binding_digest").text() == (
        "Unavailable"
    )
    assert page.findChild(QLabel, "researchNoCandidates").text() == (
        "No candidate results recorded."
    )
    assert page.findChildren(QPushButton) == []
    page.close()


def test_research_page_shows_every_candidate_and_keeps_selection_descriptive():
    application = _application()
    snapshot = PrototypeSnapshot()
    research = ResearchView(
        candidates=(
            CandidateView(
                candidate="BASE_MA35_50_V1",
                base_return="5.1%",
                stress_return="1.2%",
                stress_drawdown="-8.0%",
                turnover="1.4x",
                qualified=True,
            ),
            CandidateView(
                candidate="<img src=x>",
                base_return=None,
                stress_return="-2.1%",
                stress_drawdown=None,
                turnover=None,
                qualified=False,
                reasons=("STRESS_RETURN_WORSE", "<b>literal reason</b>"),
            ),
            CandidateView(
                candidate="PRICE_MOM_252_V1",
                base_return="4.0%",
                stress_return="-4.0%",
                stress_drawdown="-12.0%",
                turnover="2.3x",
                qualified=False,
                reasons=("STRESS_DRAWDOWN_WORSE",),
            ),
        ),
        selected="PRICE_SMA200_V1",
        policy="comparison-v2/qualification-v1",
        bundle_digest="sha256:bundle",
        dataset_digest="sha256:dataset",
        assumptions=("5bps base slippage", "10bps stress slippage"),
        prior_trials=30,
        new_trials=3,
        live_eligible=False,
    )
    snapshot = replace(snapshot, research=research)
    page = ResearchPage(PrototypeSnapshot())
    page.update_snapshot(snapshot)
    application.processEvents()

    assert page.findChild(QLabel, "research_selected").text() == "PRICE_SMA200_V1"
    assert page.findChild(QLabel, "research_bundle_digest").text() == "sha256:bundle"
    assert page.findChild(QLabel, "research_dataset_digest").text() == "sha256:dataset"
    assert page.findChild(QLabel, "research_assumptions").text() == (
        "5bps base slippage\n10bps stress slippage"
    )
    assert page.findChild(QLabel, "researchCandidate_0_base_return").text() == "5.1%"
    assert page.findChild(QLabel, "researchCandidate_1_base_return").text() == (
        "Unavailable"
    )
    assert page.findChild(QLabel, "researchCandidate_1_stress_return").text() == (
        "-2.1%"
    )
    assert page.findChild(QLabel, "researchCandidate_1_stress_drawdown").text() == (
        "Unavailable"
    )
    assert page.findChild(QLabel, "researchCandidate_1_turnover").text() == (
        "Unavailable"
    )
    assert page.findChild(QLabel, "researchCandidate_1_reasons").text() == (
        "STRESS_RETURN_WORSE; <b>literal reason</b>"
    )
    literal = page.findChild(QLabel, "researchCandidate_1_name")
    assert literal.text() == "<img src=x>"
    assert literal.textFormat() == Qt.TextFormat.PlainText
    assert page.findChild(QLabel, "researchCandidate_2_reasons").text() == (
        "STRESS_DRAWDOWN_WORSE"
    )
    assert page.findChild(QLabel, "researchCandidate_0_qualified").text() == "Yes"
    assert page.findChild(QLabel, "researchCandidate_1_qualified").text() == "No"
    assert (
        page.findChild(QLabel, "research_active_strategy").text()
        == "Unavailable (UNSELECTED)"
    )
    assert page.findChildren(QPushButton) == []
    assert snapshot.strategy == "UNSELECTED"
    assert snapshot.binding_digest is None

    page.resize(1366, 768)
    page.show()
    application.processEvents()
    scroll = page.findChild(QScrollArea, "prototypeResearchScroll")
    assert scroll.horizontalScrollBar().maximum() == 0
    page.close()


def test_none_qualifies_remains_a_research_result_not_an_active_strategy():
    application = _application()
    snapshot = PrototypeSnapshot(
        research=ResearchView(selected="NONE_QUALIFIES", live_eligible=False)
    )
    page = ResearchPage(snapshot)
    application.processEvents()

    assert page.findChild(QLabel, "research_selected").text() == "NONE_QUALIFIES"
    assert page.findChild(QLabel, "research_active_strategy").text() == (
        "Unavailable (UNSELECTED)"
    )
    assert page.findChild(QLabel, "research_active_binding_digest").text() == (
        "Unavailable"
    )
    assert page.findChildren(QPushButton) == []
    page.close()
