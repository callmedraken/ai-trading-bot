"""Real PySide6 offscreen Runtime presentation and minimum-size layout."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QScrollArea

from trading_bot.gui import (
    ProductionRuntimeEvidenceInspectionService,
    unavailable_runtime_state,
)
from trading_bot.gui.runtime_page import RuntimePage

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/gui/runtime"


def _application():
    return QApplication.instance() or QApplication([])


def test_runtime_page_read_only_selectable_and_scrollable_at_minimum_size():
    application = _application()
    state = ProductionRuntimeEvidenceInspectionService(
        acl=FIXTURES / "acl-provisioned.json",
        qualification=FIXTURES / "qualification-ready.json",
        session=FIXTURES / "session-executed.json",
    ).get_runtime_state()
    page = RuntimePage(state)
    page.resize(710, 620)  # 920 minus the existing navigation width.
    page.show()
    application.processEvents()
    scope = page.findChild(QLabel, "runtimeScope").text()
    assert all(
        text in scope
        for text in (
            "Read-only",
            "evidence-based",
            "current trading authority",
            "execution/control",
        )
    )
    assert page.findChildren(QPushButton) == []
    scroll = page.findChild(QScrollArea, "runtimeScroll")
    assert scroll.widgetResizable()
    assert scroll.verticalScrollBar().maximum() > 0
    assert scroll.horizontalScrollBar().maximum() == 0
    for field in (
        "source_head",
        "source_tree",
        "runtime_sid_digest",
        "contract_id",
        "operation_id",
        "proposal_id",
        "order_id",
        "fill_id",
    ):
        labels = page.findChildren(QLabel, f"runtime_{field}")
        assert labels
        assert all(
            label.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse
            for label in labels
        )
        for label in labels:
            caption = label.parentWidget().findChild(QLabel, f"runtimeCaption_{field}")
            assert caption.geometry().right() < label.geometry().left()
    page.close()


def test_default_runtime_page_truthful_unavailable():
    application = _application()
    page = RuntimePage(unavailable_runtime_state())
    application.processEvents()
    assert (
        "No production-runtime evidence is selected."
        in page.findChild(QLabel, "runtimeStatus").text()
    )
    assert page.findChildren(QPushButton) == []
    page.close()
