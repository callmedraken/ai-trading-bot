"""Nine acquisitions, pure System/Evidence and zero navigation rereads/effects."""

import ast
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QComboBox, QPushButton, QScrollArea

from trading_bot.domain import Symbol
from trading_bot.gui import (
    EvidenceTimelineFilter,
    EvidenceTimelineSource,
    GuiStartupConfiguration,
    ReadOnlyGuiApplicationService,
    SupervisorConsistency,
    SystemComponentStatus,
    SystemHealthStatus,
    build_evidence_navigation_target,
    build_evidence_source_page_target,
    build_evidence_timeline_state,
    build_supervisor_state,
    build_system_health_state,
    filter_evidence_timeline_entries,
)
from trading_bot.gui.main_window import MainWindow
from trading_bot.gui.models import PresentationStatus
from trading_bot.strategies.moving_average import MovingAverageCrossoverConfig
from trading_bot.strategies.production import ProductionStrategyContract


def test_nine_acquisitions_one_file_and_source_navigation(tmp_path, monkeypatch):
    application = QApplication.instance() or QApplication([])
    path = tmp_path / "selected.json"
    contract = ProductionStrategyContract(
        date(2026, 10, 12),
        "a" * 40,
        "b" * 40,
        Symbol("SPY"),
        MovingAverageCrossoverConfig(5, 20, Decimal("1")),
    )
    path.write_text(contract.to_json(), encoding="utf-8")
    service = ReadOnlyGuiApplicationService(
        GuiStartupConfiguration(production_strategy_contract=path)
    )
    calls = []
    names = (
        "get_overview",
        "get_research_state",
        "get_paper_state",
        "get_paper_account_state",
        "get_market_data_state",
        "get_operator_observability_state",
        "get_runtime_state",
        "get_production_strategy_state",
        "get_research_candidate_lifecycle_state",
    )
    for name in names:
        original = getattr(service, name)

        def acquire(_name=name, _original=original):
            calls.append(_name)
            return _original()

        monkeypatch.setattr(service, name, acquire)
    original_open = Path.open
    opens = []

    def opened(selected, *args, **kwargs):
        opens.append(selected)
        return original_open(selected, *args, **kwargs)

    monkeypatch.setattr(Path, "open", opened)
    window = MainWindow(service)
    window.resize(920, 620)
    window.show()
    application.processEvents()
    assert calls == list(names) and opens == [path]
    assert window.page_ids == (
        "home",
        "research",
        "research-lifecycle",
        "paper",
        "paper-account",
        "market-data",
        "operations",
        "runtime",
        "supervisor",
        "evidence",
        "system",
    )
    assert window._navigation.item(8).text() == "Supervisor"
    for page in window.page_ids:
        window.select_page(page)
        application.processEvents()
    timeline = window._evidence_timeline_page._state
    assert len(timeline.entries) == 1
    entry = timeline.entries[0]
    assert entry.source is EvidenceTimelineSource.SUPERVISOR
    assert entry.title == "Production strategy contract"
    assert entry.identifier == str(contract.contract_id) and entry.occurred_at is None
    assert build_evidence_source_page_target(entry).page_id.value == "supervisor"
    assert filter_evidence_timeline_entries(
        timeline, EvidenceTimelineFilter(source=EvidenceTimelineSource.SUPERVISOR)
    ) == (entry,)
    audit = window._system_health_page._state.audit_entries
    assert len(audit) == 3
    assert (
        build_evidence_navigation_target(audit[0]).source
        is EvidenceTimelineSource.SUPERVISOR
    )
    window.select_page("evidence")
    selector = window._evidence_timeline_page.findChild(QComboBox)
    selector.setCurrentText("Supervisor")
    button = next(
        b
        for b in window._evidence_timeline_page.findChildren(QPushButton)
        if b.text() == "View source page"
    )
    button.click()
    assert window.current_page_id == "supervisor"
    application.processEvents()
    scroll = window._supervisor_page.findChild(QScrollArea)
    assert scroll.horizontalScrollBar().maximum() == 0
    assert calls == list(names) and opens == [path]
    window.close()


@pytest.mark.parametrize(
    "selected,expected",
    [(False, SystemComponentStatus.UNAVAILABLE), (True, SystemComponentStatus.BLOCKED)],
)
def test_system_default_neutral_and_malformed_blocked(tmp_path, selected, expected):
    path = tmp_path / "selected.json"
    path.write_text("invalid")
    service = ReadOnlyGuiApplicationService(
        GuiStartupConfiguration(production_strategy_contract=path if selected else None)
    )
    research = service.get_research_state()
    runtime = service.get_runtime_state()
    supervisor = build_supervisor_state(
        research, runtime, service.get_production_strategy_state()
    )
    states = (
        research,
        service.get_paper_state(),
        service.get_paper_account_state(),
        service.get_market_data_state(),
        service.get_operator_observability_state(),
        runtime,
        supervisor,
    )
    system = build_system_health_state(service.get_overview(), *states)
    assert system.components[-1].status is expected
    assert (system.status is SystemHealthStatus.ATTENTION) is selected
    assert not build_evidence_timeline_state(*states).entries
    assert str(path) not in repr(system)


@pytest.mark.parametrize(
    "mismatch", [None, "contract_id", "source_head", "source_tree", "target_session"]
)
def test_overview_and_system_propagate_exact_session_conflicts(tmp_path, mismatch):
    contract = ProductionStrategyContract(
        date(2026, 10, 12),
        "a" * 40,
        "b" * 40,
        Symbol("SPY"),
        MovingAverageCrossoverConfig(5, 20, Decimal("1")),
    )
    strategy_path = tmp_path / "strategy.json"
    strategy_path.write_text(contract.to_json(), encoding="utf-8")
    fixtures = Path(__file__).resolve().parents[1] / "fixtures/gui/runtime"
    session = json.loads((fixtures / "session-waiting.json").read_text())
    session.update(
        contract_id=str(contract.contract_id),
        source_head=contract.source_head,
        source_tree=contract.source_tree,
        target_session=contract.target_session_date.isoformat(),
    )
    if mismatch is not None:
        session[mismatch] = {
            "contract_id": "11111111-1111-5111-8111-111111111111",
            "source_head": "c" * 40,
            "source_tree": "d" * 40,
            "target_session": "2026-10-13",
        }[mismatch]
    session_path = tmp_path / "session.json"
    session_path.write_text(json.dumps(session), encoding="utf-8")
    service = ReadOnlyGuiApplicationService(
        GuiStartupConfiguration(
            production_strategy_contract=strategy_path,
            runtime_session_evidence=session_path,
        )
    )
    overview = service.get_overview()
    component = next(c for c in overview.components if c.key == "supervisor")
    assert component.status is (
        PresentationStatus.INFO if mismatch is None else PresentationStatus.BLOCKED
    )
    research = service.get_research_state()
    runtime = service.get_runtime_state()
    supervisor = build_supervisor_state(
        research, runtime, service.get_production_strategy_state()
    )
    assert supervisor.consistency is (
        SupervisorConsistency.CONSISTENT
        if mismatch is None
        else SupervisorConsistency.CONFLICTING
    )
    system = build_system_health_state(
        overview,
        research,
        service.get_paper_state(),
        service.get_paper_account_state(),
        service.get_market_data_state(),
        service.get_operator_observability_state(),
        runtime,
        supervisor,
    )
    assert system.components[-1].status is (
        SystemComponentStatus.AVAILABLE
        if mismatch is None
        else SystemComponentStatus.BLOCKED
    )
    assert (system.status is SystemHealthStatus.ATTENTION) == (mismatch is not None)


def test_a15_capability_freeze_has_no_effectful_imports_or_calls():
    root = Path(__file__).resolve().parents[2] / "src/trading_bot/gui"
    names = (
        "production_strategy_models.py",
        "production_strategy_service.py",
        "supervisor_models.py",
        "supervisor_adapter.py",
        "supervisor_page.py",
    )
    forbidden = (
        "trading_bot.review_paper",
        "sqlite3",
        "subprocess",
        "socket",
        "requests",
        "trading_bot.runtime",
        "trading_bot.risk",
        "trading_bot.execution",
        "trading_bot.brokers",
        "trading_bot.robinhood",
    )
    for name in names:
        tree = ast.parse((root / name).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(forbidden)
            elif isinstance(node, ast.Import):
                assert all(not alias.name.startswith(forbidden) for alias in node.names)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {
                    "glob",
                    "rglob",
                    "walk",
                    "write_text",
                    "write_bytes",
                    "getenv",
                    "execute",
                    "arm",
                    "promote",
                }
                if name in (
                    "supervisor_models.py",
                    "supervisor_adapter.py",
                    "supervisor_page.py",
                ):
                    assert node.func.attr not in {
                        "open",
                        "read",
                        "get_production_strategy_state",
                        "get_runtime_state",
                        "get_research_state",
                    }
