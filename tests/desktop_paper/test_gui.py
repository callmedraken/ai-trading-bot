"""Synthetic cached-controller tests for the desktop paper GUI slice."""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

from trading_bot.desktop_paper.models import (
    PaperAccountState,
    PaperControlState,
    PaperCycleInput,
    PaperCycleKind,
    PaperCycleResult,
    PaperStoreSnapshot,
)
from trading_bot.desktop_paper.presentation import DesktopPaperSnapshot
from trading_bot.desktop_runtime import (
    DesktopStatus,
    Diagnostic,
    Lifecycle,
    WorkerHealth,
)
from trading_bot.domain import Symbol
from trading_bot.gui.desktop_control import DesktopControl
from trading_bot.gui.desktop_paper_panel import DesktopPaperPanel
from trading_bot.gui.main_window import MainWindow
from trading_bot.gui.mock_service import MockGuiApplicationService

TEST_NAMESPACE = NAMESPACE_URL


def _application() -> QApplication:
    existing = QApplication.instance()
    return existing if existing is not None else QApplication([])


def _status(
    state: Lifecycle,
    *,
    can_start: bool,
    can_stop: bool,
    can_close: bool = True,
) -> DesktopStatus:
    return DesktopStatus(
        state=state,
        generation=0,
        trading=WorkerHealth(state=state),
        research=WorkerHealth(state=state),
        diagnostic=Diagnostic.NONE,
        can_start=can_start,
        can_stop=can_stop,
        can_close=can_close,
        transport="NOT_CONNECTED",
        mode="SIMULATED_PAPER",
        live_enabled=False,
    )


def _financial(config, *, kill_latched: bool = False, new_buys_enabled: bool = True):
    account = PaperAccountState(
        cash=Decimal("1000"),
        positions={},
        realized_profit_loss=Decimal("-12.50"),
        marked_equity=None,
        unrealized_profit_loss=None,
        fills=(),
    )
    control = PaperControlState(
        version=4,
        kill_latched=kill_latched,
        new_buys_enabled=new_buys_enabled,
    )
    return PaperStoreSnapshot(
        account_id=uuid5(TEST_NAMESPACE, "gui-account"),
        configuration_revision_id=config.configuration_revision_id,
        account=account,
        cursor_index=0,
        execution_session_id=None,
        control=control,
        latest_result=None,
    )


class FakePaperController:
    def __init__(
        self,
        snapshot: DesktopPaperSnapshot,
        status: DesktopStatus,
    ) -> None:
        self.current_snapshot = snapshot
        self.current_status = status
        self.calls: list[tuple[object, ...]] = []
        self.snapshot_calls = 0
        self.status_calls = 0

    def snapshot(self) -> DesktopPaperSnapshot:
        self.snapshot_calls += 1
        return self.current_snapshot

    def status(self) -> DesktopStatus:
        self.status_calls += 1
        return self.current_status

    def latch_kill(self) -> bool:
        self.calls.append(("latch_kill",))
        return True

    def set_new_buys_enabled(self, enabled: bool) -> bool:
        self.calls.append(("set_new_buys_enabled", enabled))
        return True

    def clear_kill(self) -> bool:
        self.calls.append(("clear_kill",))
        return True

    def start(self) -> bool:
        self.calls.append(("start",))
        return True

    def stop(self) -> None:
        self.calls.append(("stop",))

    def dispose(self) -> bool:
        self.calls.append(("dispose",))
        return True


def test_panel_reports_selection_required_without_inventing_account_values() -> None:
    _application()
    controller = FakePaperController(
        DesktopPaperSnapshot(),
        _status(Lifecycle.STOPPED, can_start=False, can_stop=False),
    )
    panel = DesktopPaperPanel(controller)

    assert panel.selection_label.text() == "Paper strategy: Selection required"
    assert panel.availability_label.text() == (
        "Trading unavailable until an accepted PAPER_EVALUATION binding is installed."
    )
    assert (
        panel.findChild(QLabel, "desktopPaperFieldFinancialAvailability").text()
        == "Unavailable"
    )
    assert panel.findChild(QLabel, "desktopPaperFieldAccount").text() == (
        "Unavailable (no financial snapshot)"
    )
    assert (
        "PAPER_EVALUATION_SELECTION_REQUIRED"
        in panel.findChild(QLabel, "desktopPaperFieldDiagnostic").text()
    )
    assert "100000" not in " ".join(
        label.text() for label in panel.findChildren(QLabel)
    )
    assert not panel.kill_button.isEnabled()
    assert not panel.new_buys_checkbox.isVisible()
    assert not panel.clear_kill_button.isEnabled()


def test_panel_shows_binding_provenance_and_incomplete_marks_truthfully(
    paper_config,
) -> None:
    _application()
    snapshot = DesktopPaperSnapshot(
        binding=paper_config.binding,
        state=Lifecycle.STOPPED,
        activity="WAITING",
        diagnostic="",
        financial=_financial(paper_config),
        latest=None,
        stale=True,
    )
    controller = FakePaperController(
        snapshot, _status(Lifecycle.STOPPED, can_start=True, can_stop=False)
    )
    panel = DesktopPaperPanel(controller)

    assert panel.selection_label.text() == (
        "Paper strategy: SYNTHETIC_FIXTURE test-v1 · QQQ"
    )
    expected_fields = {
        "Family": "SYNTHETIC_FIXTURE",
        "Version": "test-v1",
        "Symbol": "QQQ",
        "Parameters": "fixture=True",
        "CampaignId": str(paper_config.binding.research_campaign_id),
        "BundleId": str(paper_config.binding.research_bundle_id),
        "CandidateId": str(paper_config.binding.research_candidate_id),
        "ProvenanceDigest": "a" * 64,
        "QualificationPolicy": "None",
        "LiveEligible": "False",
        "Mode": "SIMULATED_PAPER",
        "Purpose": "PAPER_EVALUATION",
        "SourceLane": "OPEN_REPLAY",
        "Control": "version=4; kill_latched=False; new_buys_enabled=True",
    }
    for field_name, expected in expected_fields.items():
        label = panel.findChild(QLabel, f"desktopPaperField{field_name}")
        assert label is not None
        assert label.text() == expected
    account = panel.findChild(QLabel, "desktopPaperFieldAccount").text()
    assert "cash=1000" in account
    assert "realized_profit_loss=-12.50" in account
    assert "marked_equity=Unavailable (incomplete marks)" in account
    assert "unrealized_profit_loss=Unavailable (incomplete marks)" in account
    assert (
        "cached financial values, marks, and session may be stale"
        in panel.findChild(QLabel, "desktopPaperFieldStale").text()
    )
    assert all(
        label.textFormat() is Qt.TextFormat.PlainText
        for label in panel.findChildren(QLabel)
    )


def test_panel_displays_complete_latest_cycle_snapshot(paper_config) -> None:
    _application()
    account = PaperAccountState(
        cash=Decimal("987.50"),
        positions={},
        realized_profit_loss=Decimal("0"),
        marked_equity=None,
        unrealized_profit_loss=None,
        fills=(),
    )
    control = PaperControlState(
        version=8,
        kill_latched=False,
        new_buys_enabled=True,
    )
    cycle_input = PaperCycleInput(
        execution_session_id="OPEN_REPLAY:QQQ:2025-01-02:prefix",
        execution_index=1,
        symbol=Symbol("QQQ"),
        observation_id=uuid5(TEST_NAMESPACE, "gui-observation"),
        completed_history_cutoff="2025-01-01T00:00:00+00:00",
        observation_open=Decimal("100"),
        executed_at=datetime(2025, 1, 2, tzinfo=UTC),
        proposal=None,
        no_signal_reason="NO_SIGNAL",
        warmup=False,
    )
    cycle = PaperCycleResult(
        cycle_id=uuid5(TEST_NAMESPACE, "gui-cycle"),
        kind=PaperCycleKind.NO_SIGNAL,
        input=cycle_input,
        configuration_revision_id=paper_config.configuration_revision_id,
        risk_context=None,
        risk_decision=None,
        order=None,
        fill=None,
        order_events=(),
        account=account,
        cursor_index=1,
        control=control,
    )
    financial = PaperStoreSnapshot(
        account_id=uuid5(TEST_NAMESPACE, "gui-account"),
        configuration_revision_id=paper_config.configuration_revision_id,
        account=account,
        cursor_index=1,
        execution_session_id=cycle_input.execution_session_id,
        control=control,
        latest_result=cycle,
    )
    snapshot = DesktopPaperSnapshot(
        binding=paper_config.binding,
        state=Lifecycle.RUNNING,
        activity="NO_SIGNAL",
        diagnostic="",
        financial=financial,
        latest=cycle,
        stale=False,
    )
    panel = DesktopPaperPanel(
        FakePaperController(
            snapshot, _status(Lifecycle.RUNNING, can_start=False, can_stop=True)
        )
    )

    latest = panel.findChild(QLabel, "desktopPaperFieldLatestCycle").text()

    assert "kind=NO_SIGNAL" in latest
    assert "execution_index=1" in latest
    assert "no_signal_reason=NO_SIGNAL" in latest
    assert "current_marks=[QQQ=100] (cached cycle marks)" in latest
    assert "Unavailable (no risk context for this cycle)" in latest
    assert "Unavailable (no risk decision for this cycle)" in latest
    assert "Unavailable (no order for this cycle)" in latest
    assert "marked_equity=Unavailable (incomplete marks)" in latest
    assert "False — cached financial values, marks, and session are current" in (
        panel.findChild(QLabel, "desktopPaperFieldStale").text()
    )
    assert all(
        label.textFormat() is Qt.TextFormat.PlainText
        for label in panel.findChildren(QLabel)
    )


def test_panel_refresh_uses_only_controller_cached_accessors(paper_config) -> None:
    _application()
    controller = FakePaperController(
        DesktopPaperSnapshot(
            binding=paper_config.binding,
            financial=_financial(paper_config),
        ),
        _status(Lifecycle.RUNNING, can_start=False, can_stop=True),
    )
    panel = DesktopPaperPanel(controller)
    before = (controller.snapshot_calls, controller.status_calls)

    panel.refresh()

    assert controller.snapshot_calls == before[0] + 1
    assert controller.status_calls == before[1] + 1
    assert controller.calls == []


def test_kill_and_new_buy_controls_route_only_while_running(paper_config) -> None:
    _application()
    controller = FakePaperController(
        DesktopPaperSnapshot(
            binding=paper_config.binding,
            financial=_financial(paper_config, new_buys_enabled=True),
        ),
        _status(Lifecycle.RUNNING, can_start=False, can_stop=True),
    )
    panel = DesktopPaperPanel(controller)

    assert panel.kill_button.isEnabled()
    assert panel.new_buys_checkbox.isEnabled()
    assert panel.new_buys_checkbox.isChecked()

    panel.kill_button.click()
    panel.new_buys_checkbox.click()

    assert controller.calls == [
        ("latch_kill",),
        ("set_new_buys_enabled", False),
    ]

    controller.current_status = _status(
        Lifecycle.STOPPED, can_start=True, can_stop=False
    )
    controller.current_snapshot = replace(
        controller.current_snapshot,
        financial=_financial(paper_config, kill_latched=True),
    )
    panel.refresh()

    assert not panel.kill_button.isEnabled()
    assert not panel.new_buys_checkbox.isEnabled()
    assert panel.clear_kill_button.isEnabled()
    panel.clear_kill_button.click()
    assert controller.calls[-1] == ("clear_kill",)


def test_main_window_integrates_panel_and_preserves_historical_paper_content(
    paper_config,
) -> None:
    _application()
    controller = FakePaperController(
        DesktopPaperSnapshot(),
        _status(Lifecycle.STOPPED, can_start=False, can_stop=False),
    )
    window = MainWindow(
        MockGuiApplicationService(),
        paper_controller=controller,  # type: ignore[arg-type]
    )
    try:
        home = window._stack.widget(0)
        home_text = " ".join(label.text() for label in home.findChildren(QLabel))
        assert "P4 inert" not in home_text
        assert "inert trading worker" not in home_text
        assert "simulated-paper evaluation" in home_text
        assert "Selection required" in home_text
        assert (
            "Trading unavailable until an accepted "
            "PAPER_EVALUATION binding is installed." in home_text
        )
        assert isinstance(window._desktop_control, DesktopControl)
        assert "deferred to P5" not in window._desktop_control.status_label.text()
        assert window._desktop_control.start_button.isEnabled() is False
        assert window._desktop_control.stop_button.isEnabled() is False

        panel = window.findChild(DesktopPaperPanel, "desktopPaperPanel")
        assert panel is window._desktop_paper_panel
        assert window._paper_page.layout().itemAt(0).widget() is panel
        historical_message = window._paper_page.paper_state.message
        assert (
            window._paper_page.findChild(QLabel, "summaryLabel").text()
            == historical_message
        )
    finally:
        window.close()


def test_main_window_reuses_start_stop_control_for_paper_controller(
    paper_config,
) -> None:
    _application()
    controller = FakePaperController(
        DesktopPaperSnapshot(binding=paper_config.binding),
        _status(Lifecycle.STOPPED, can_start=True, can_stop=False),
    )
    window = MainWindow(
        MockGuiApplicationService(),
        paper_controller=controller,  # type: ignore[arg-type]
    )
    try:
        assert isinstance(window._desktop_control, DesktopControl)
        assert window._desktop_control.start_button.isEnabled()
        window._desktop_control.start_button.click()
        assert controller.calls == [("start",)]

        controller.current_status = _status(
            Lifecycle.RUNNING, can_start=False, can_stop=True
        )
        window._desktop_control.refresh()
        assert window._desktop_control.stop_button.isEnabled()
        window._desktop_control.stop_button.click()
        assert controller.calls[-1] == ("stop",)
    finally:
        window.close()


def test_main_window_without_paper_controller_keeps_historical_page() -> None:
    _application()
    window = MainWindow(MockGuiApplicationService())
    try:
        assert not hasattr(window, "_desktop_paper_panel")
        assert not hasattr(window, "_desktop_control")
        assert window._paper_page.paper_state is not None
    finally:
        window.close()
