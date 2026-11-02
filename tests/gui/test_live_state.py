import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton

from trading_bot.gui.live_state import LiveStatePanel, unavailable_live_state


def test_live_panel_is_sanitized_and_has_no_placement_button():
    application = QApplication.instance() or QApplication([])
    panel = LiveStatePanel(unavailable_live_state())
    assert application is not None
    assert panel.findChildren(QPushButton) == []
    assert panel.findChild(QPushButton) is None
    panel.close()
