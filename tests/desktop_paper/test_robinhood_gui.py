"""Qt renders cached baseline only, with mutation disabled in every state."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton

from trading_bot.gui.broker_read_panel import RobinhoodReadPanel
from trading_bot.gui.main_window import MainWindow
from trading_bot.gui.mock_service import MockGuiApplicationService

from .test_robinhood_read import ACCOUNT, snapshot


def test_all_read_only_states_and_no_order_controls():
    app = QApplication.instance() or QApplication([])
    panel = RobinhoodReadPanel()
    assert panel.status_label.text() == "Robinhood: NOT_CONNECTED"
    panel.set_observation(snapshot())
    assert panel.status_label.text() == "Robinhood: READ_ONLY_CONNECTED"
    observations = panel.observations_label.text()
    assert "positions observed = 1" in observations
    assert "account resolved = yes" in observations
    assert "SPY quote observed = yes" in observations
    assert "order-history baseline observed = yes" in observations
    assert "broker mutation enabled = false" in observations
    assert ACCOUNT not in observations
    assert not panel.findChildren(QPushButton)
    panel.set_observation(None, failed=True)
    assert panel.status_label.text() == "Robinhood: RECONCILIATION_FAILED"
    assert "broker mutation enabled = false" in panel.observations_label.text()
    panel.close()
    app.processEvents()


def test_main_window_contains_disconnected_cached_broker_panel():
    app = QApplication.instance() or QApplication([])
    window = MainWindow(MockGuiApplicationService())
    assert window.robinhood_read_panel.status_label.text() == "Robinhood: NOT_CONNECTED"
    window.close()
    app.processEvents()
