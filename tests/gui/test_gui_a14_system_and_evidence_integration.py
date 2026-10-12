"""Seven acquisition calls, pure integration, zero Runtime/System/Evidence rereads."""

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QFrame, QPushButton

from trading_bot.gui import (
    EvidenceTimelineFilter,
    EvidenceTimelineSource,
    GuiStartupConfiguration,
    ProductionRuntimeEvidenceInspectionService,
    ReadOnlyGuiApplicationService,
    SystemComponentStatus,
    SystemHealthStatus,
    build_evidence_source_page_target,
    build_evidence_timeline_state,
    build_system_health_state,
    filter_evidence_timeline_entries,
    unavailable_runtime_state,
)
from trading_bot.gui.main_window import MainWindow
from trading_bot.gui.mock_service import MockGuiApplicationService

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/gui/runtime"


def _adapters(runtime):
    service = MockGuiApplicationService()
    states = (
        service.get_research_state(),
        service.get_paper_state(),
        service.get_paper_account_state(),
        service.get_market_data_state(),
        service.get_operator_observability_state(),
        runtime,
    )
    return build_system_health_state(
        service.get_overview(), *states
    ), build_evidence_timeline_state(*states)


@pytest.mark.parametrize(
    "filename,status",
    [
        (None, SystemComponentStatus.UNAVAILABLE),
        ("acl-provisioned.json", SystemComponentStatus.AVAILABLE),
        ("acl-blocked.json", SystemComponentStatus.BLOCKED),
    ],
)
def test_runtime_health_unavailable_neutral_attention_and_safe_identity(
    filename, status
):
    runtime = (
        unavailable_runtime_state()
        if filename is None
        else ProductionRuntimeEvidenceInspectionService(
            acl=FIXTURES / filename
        ).get_runtime_state()
    )
    system, timeline = _adapters(runtime)
    assert system.components[-1].status is status
    assert (system.status is SystemHealthStatus.ATTENTION) == (
        status is SystemComponentStatus.BLOCKED
    )
    assert str(FIXTURES) not in repr(system) + repr(timeline)
    if filename is not None:
        assert system.audit_entries[0].identifier == "a" * 64
        assert timeline.entries[0].occurred_at is None


def test_runtime_timeline_uses_only_explicit_timestamps_and_filter_mapping():
    runtime = ProductionRuntimeEvidenceInspectionService(
        acl=FIXTURES / "acl-provisioned.json",
        qualification=FIXTURES / "qualification-ready.json",
        session=FIXTURES / "session-executed.json",
    ).get_runtime_state()
    system, timeline = _adapters(runtime)
    assert len(timeline.entries) == 3
    assert timeline.entries[0].occurred_at == runtime.session.admitted_at
    assert all(entry.occurred_at is None for entry in timeline.entries[1:])
    assert all(
        build_evidence_source_page_target(entry).page_id.value == "runtime"
        for entry in timeline.entries
    )
    assert (
        len(
            filter_evidence_timeline_entries(
                timeline, EvidenceTimelineFilter(source=EvidenceTimelineSource.RUNTIME)
            )
        )
        == 3
    )
    assert (
        len(
            filter_evidence_timeline_entries(
                timeline,
                EvidenceTimelineFilter(query=str(runtime.session.operation_id)),
            )
        )
        == 1
    )
    assert {item.identifier for item in system.audit_entries} >= {
        runtime.qualification.source_head,
        runtime.qualification.source_tree,
        str(runtime.session.contract_id),
    }


def test_main_window_exactly_seven_reads_and_runtime_evidence_source_navigation(
    monkeypatch,
):
    application = QApplication.instance() or QApplication([])
    service = ReadOnlyGuiApplicationService(
        GuiStartupConfiguration(
            runtime_acl_evidence=FIXTURES / "acl-provisioned.json",
            runtime_qualification_evidence=FIXTURES / "qualification-ready.json",
            runtime_session_evidence=FIXTURES / "session-waiting.json",
        )
    )
    reads = []
    for name in (
        "get_overview",
        "get_research_state",
        "get_paper_state",
        "get_paper_account_state",
        "get_market_data_state",
        "get_operator_observability_state",
        "get_runtime_state",
    ):
        original = getattr(service, name)

        def record(*args, _name=name, _original=original, **kwargs):
            reads.append(_name)
            return _original(*args, **kwargs)

        monkeypatch.setattr(service, name, record)
    original_open = Path.open
    opens = []

    def open_record(path, *args, **kwargs):
        opens.append(path)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_record)
    window = MainWindow(service)
    window.resize(920, 620)
    window.show()
    application.processEvents()
    assert len(reads) == 7 and len(set(reads)) == 7
    assert len(opens) == 3 and len(set(opens)) == 3
    assert window.page_ids == (
        "home",
        "research",
        "paper",
        "paper-account",
        "market-data",
        "operations",
        "runtime",
        "evidence",
        "system",
    )
    for page in ("runtime", "system", "evidence", "runtime", "evidence"):
        window.select_page(page)
    cards = window._evidence_timeline_page.findChildren(QFrame, "evidenceTimelineCard")
    assert cards
    button = next(
        button
        for card in cards
        for button in card.findChildren(QPushButton)
        if button.text() == "View source page"
    )
    button.click()
    assert window.current_page_id == "runtime"
    assert len(reads) == 7 and len(opens) == 3
    window.close()
