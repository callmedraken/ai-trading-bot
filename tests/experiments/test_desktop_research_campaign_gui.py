"""Current P3 GUI integration; synthetic artifacts, no production storage."""

import json
import os
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from trading_bot.domain import Bar, Symbol
from trading_bot.experiments import desktop_research_campaign as campaign
from trading_bot.gui.desktop_campaign_service import (
    DesktopCampaignResearchService,
    ResearchArtifactService,
)
from trading_bot.gui.models import ResearchReportStatus
from trading_bot.gui.research_service import (
    CompactReportResearchService,
    filter_research_rows,
)
from trading_bot.gui.startup_composition import (
    GuiStartupConfiguration,
    ReadOnlyGuiApplicationService,
)
from trading_bot.market_data.models import HistoricalDataRequest, HistoricalDataResult

from .test_desktop_research_campaign import HEAD, TREE, fake_development, fake_walk


@pytest.fixture(scope="module")
def bundle():
    symbol = Symbol("SPY")
    bars = tuple(
        Bar(
            symbol,
            datetime(year, 1, 4, 20, tzinfo=UTC),
            Decimal("100"),
            Decimal("101"),
            Decimal("99"),
            Decimal("100"),
            10,
        )
        for year in range(2016, 2024)
    )
    data = HistoricalDataResult(
        HistoricalDataRequest(symbol, campaign._date(2016), campaign._date(2024)),
        bars,
        "synthetic-test",
    )
    binding = replace(
        campaign.ACCEPTED_DATASET_BINDING,
        open_row_count=len(bars),
        open_first_timestamp=bars[0].timestamp.isoformat(),
        open_last_timestamp=bars[-1].timestamp.isoformat(),
    )
    identity = campaign.campaign_identity(binding, HEAD, TREE)
    rows = tuple(
        fake_development(
            identity,
            campaign._definition(HEAD, TREE, *pair),
            campaign.development_data(data),
            HEAD,
            TREE,
        )
        for pair in campaign.GRID
    )
    walks = tuple(
        fake_walk(row, data, HEAD, TREE) for row in campaign.rank_development(rows)[:32]
    )
    return campaign.DesktopCampaignBundle(binding, HEAD, TREE, rows, walks)


@pytest.fixture
def artifact(tmp_path, bundle):
    path = tmp_path / "bundle.json"
    path.write_bytes(bundle.to_bytes())
    return path


def test_adapter_loads_all_candidates_and_truthful_optional_fields(artifact, bundle):
    state = DesktopCampaignResearchService(artifact).get_research_state()
    assert state.status is ResearchReportStatus.LOADED
    assert state == ResearchArtifactService(artifact).get_research_state()
    report = state.report
    assert report.report_id == bundle.bundle_id
    assert report.row_count == 255
    assert sum(row.shortlisted for row in report.rows) == 32
    assert sum(row.research_only_leader for row in report.rows) == 1
    assert all(row.aggregate_one_way_turnover is None for row in report.rows)
    assert all(row.performance_turnover == Decimal("0.5") for row in report.rows)
    leader = next(row for row in report.rows if row.research_only_leader)
    assert leader.rank == 1
    assert leader.walk_forward_fold_count == 2
    assert leader.minimum_walk_forward_return is not None
    assert leader.median_walk_forward_return is not None
    assert leader.maximum_walk_forward_drawdown is not None
    other = next(row for row in report.rows if not row.shortlisted)
    assert other.walk_forward_fold_count is None
    assert other.minimum_walk_forward_return is None
    assert other.median_walk_forward_return is None
    assert other.maximum_walk_forward_drawdown is None
    assert len(filter_research_rows(report.rows, "short_window=5,")) == 22
    assert "Research only" in state.message
    assert "FINAL_HOLDOUT sealed" in report.metadata_summary


@pytest.mark.parametrize(
    "payload",
    [
        b"{",
        b"[]",
        b'{"schema":"desktop-research-campaign/v1"}',
        b"[" * 2000,
        b"x" * 10_000_001,
    ],
    ids=("truncated", "array", "incomplete", "deep", "oversized"),
)
def test_invalid_or_oversized_is_bounded_unavailable(tmp_path, payload):
    path = tmp_path / "bad.json"
    path.write_bytes(payload)
    state = DesktopCampaignResearchService(path).get_research_state()
    assert state.status is ResearchReportStatus.UNAVAILABLE
    assert state.report is None
    assert len(state.message) < 100
    assert ResearchArtifactService(path).get_research_state().report is None


def test_compact_service_and_existing_startup_remain_compatible(artifact):
    fixture = (
        Path(__file__).resolve().parents[1]
        / "fixtures/cli/historical-experiment-compact-report-v1-compact.json"
    )
    old = CompactReportResearchService(fixture).get_research_state()
    assert old.status is ResearchReportStatus.LOADED
    assert ResearchArtifactService(fixture).get_research_state() == old
    assert old.report.rows[0].walk_forward_fold_count is None
    assert old.report.rows[0].performance_turnover is None
    service = ReadOnlyGuiApplicationService(
        GuiStartupConfiguration(research_report=artifact)
    )
    assert service.get_research_state().report.variant_source == "DESKTOP_OPEN_CAMPAIGN"
    assert service.load_research_report(fixture) == old
    assert service.load_research_report(artifact).report.row_count == 255


def test_canonical_schema_and_read_only_service_source(artifact, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("GUI attempted campaign or storage operation")

    monkeypatch.setattr(campaign, "run_desktop_campaign", forbidden)
    raw = json.loads(artifact.read_bytes())
    raw["walk_forward"][0]["fold_count"] = 100
    artifact.write_bytes(campaign._json(raw))
    assert DesktopCampaignResearchService(artifact).get_research_state().report is None


def test_page_sort_filter_comparison_and_campaign_details(artifact):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QTableWidget

    from trading_bot.gui.research_page import ResearchPage

    app = QApplication.instance() or QApplication([])
    service = ReadOnlyGuiApplicationService(
        GuiStartupConfiguration(research_report=artifact)
    )
    page = ResearchPage(service.get_research_state(), service)
    table = page.findChild(QTableWidget, "researchResultsTable")
    assert table.rowCount() == 255
    page._sort_table(0)
    table.selectRow(0)
    leader = next(
        row for row in page.research_state.report.rows if row.research_only_leader
    )
    assert table.item(0, 0).text() == "1"
    for name, value in {
        "researchDetailWfFolds": "2",
        "researchDetailPerformanceTurnover": "0.5",
        "researchDetailClosedTrades": "2",
        "researchDetailShortlisted": "Yes",
        "researchDetailResearchLeader": "Yes",
    }.items():
        assert page.findChild(QLabel, name).text() == value
    assert page.findChild(QLabel, "researchDetailWfMinimum").text() != "Not evaluated"
    assert not table.item(0, 0).flags() & Qt.ItemFlag.ItemIsEditable
    page.add_selected_to_comparison()
    table.selectRow(1)
    page.add_selected_to_comparison()
    assert page.comparison_state.is_ready
    chart = page._comparison_chart
    assert len(chart.rows) == 2
    assert {bar.metric for bar in chart.bar_layout(800)} == {
        "total_return",
        "maximum_drawdown_percentage",
        "performance_turnover",
        "total_fills",
    }
    page.findChild(QLineEdit, "researchFilter").setText(leader.parameter_label)
    assert sum(not table.isRowHidden(row) for row in range(table.rowCount())) == 1
    assert page.comparison_state.count == 2
    page.findChild(QLineEdit, "researchFilter").clear()
    nonshortlisted = next(
        row for row in page.research_state.report.rows if not row.shortlisted
    )
    table_row = next(
        i
        for i in range(table.rowCount())
        if table.item(i, 0).data(Qt.ItemDataRole.UserRole)
        == nonshortlisted.caller_ordinal
    )
    table.selectRow(table_row)
    assert page.findChild(QLabel, "researchDetailWfFolds").text() == "Not evaluated"
    assert page.findChild(QLabel, "researchDetailResearchLeader").text() == "No"
    page.close()
    app.processEvents()
