"""GUI-A8 real-adapter multi-source startup integration tests."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from tests.market_data.daily_snapshot_test_support import accepted_snapshot
from tests.runtime.test_checkpointed_paper_cycle_successor import _edge_artifacts

from trading_bot.domain import Symbol
from trading_bot.gui import (
    GuiStartupConfiguration,
    MarketDataPageStatus,
    OperatorOperationsPageStatus,
    PaperAccountCheckpointKindView,
    PaperAccountPageStatus,
    PaperPageStatus,
    ResearchReportStatus,
    app,
)
from trading_bot.market_data import serialize_daily_snapshot
from trading_bot.portfolio import MetadataEntry
from trading_bot.runtime import (
    PaperAccountCheckpointPosition,
    PaperAccountGenesisRequest,
    create_genesis_paper_account_checkpoint,
    serialize_paper_account_checkpoint,
)

ROOT = Path(__file__).resolve().parents[2]
RESEARCH_FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "cli"
    / "historical-experiment-compact-report-v1-compact.json"
)
_NOW = datetime(2026, 8, 27, 22, 0, tzinfo=UTC)


def _write_market_snapshot(tmp_path: Path) -> tuple[Path, bytes]:
    payload = serialize_daily_snapshot(accepted_snapshot())
    path = tmp_path / "explicit-market-snapshot.json"
    path.write_bytes(payload)
    return path, payload


def _write_genesis(tmp_path: Path) -> tuple[Path, bytes]:
    checkpoint = create_genesis_paper_account_checkpoint(
        PaperAccountGenesisRequest(
            _NOW,
            Decimal("1000.00"),
            (
                PaperAccountCheckpointPosition.from_exact_basis(
                    Symbol("SPY"),
                    Decimal("2"),
                    Decimal("20"),
                ),
            ),
            Decimal("-12.50"),
            (MetadataEntry("source", "gui-a8-integration"),),
        )
    )
    payload = serialize_paper_account_checkpoint(checkpoint)
    path = tmp_path / "explicit-genesis.json"
    path.write_bytes(payload)
    return path, payload


def _write_successor_edge(
    tmp_path: Path,
) -> tuple[tuple[Path, Path, Path, Path], bytes]:
    (
        _result,
        _report,
        report_payload,
        prior_payload,
        snapshot_payload,
        _successor,
        successor_payload,
    ) = _edge_artifacts()
    paths = (
        tmp_path / "explicit-prior.json",
        tmp_path / "explicit-snapshot.json",
        tmp_path / "explicit-cycle-report.json",
        tmp_path / "explicit-successor.json",
    )
    for path, payload in zip(
        paths,
        (prior_payload, snapshot_payload, report_payload, successor_payload),
        strict=True,
    ):
        path.write_bytes(payload)
    return paths, successor_payload


def test_combined_research_market_data_and_genesis_startup_uses_real_adapters(
    tmp_path: Path,
) -> None:
    snapshot_path, snapshot_payload = _write_market_snapshot(tmp_path)
    genesis_path, genesis_payload = _write_genesis(tmp_path)

    service = app.build_startup_service(
        GuiStartupConfiguration(
            research_report=RESEARCH_FIXTURE,
            market_data_snapshot=snapshot_path,
            market_data_expected_sha256=hashlib.sha256(
                snapshot_payload
            ).hexdigest(),
            market_data_expected_byte_length=len(snapshot_payload),
            paper_account_genesis=genesis_path,
            paper_account_expected_sha256=hashlib.sha256(
                genesis_payload
            ).hexdigest(),
            paper_account_expected_byte_length=len(genesis_payload),
        )
    )

    research = service.get_research_state()
    market_data = service.get_market_data_state()
    paper_account = service.get_paper_account_state()

    assert research.status is ResearchReportStatus.LOADED
    assert research.report is not None
    assert research.report.row_count == 4
    assert market_data.status is MarketDataPageStatus.VERIFIED
    assert market_data.snapshot is not None
    assert paper_account.status is PaperAccountPageStatus.VERIFIED
    assert paper_account.account is not None
    assert (
        paper_account.account.checkpoint_kind
        is PaperAccountCheckpointKindView.GENESIS
    )
    assert service.get_paper_state().status is PaperPageStatus.UNAVAILABLE
    assert (
        service.get_operator_observability_state().status
        is OperatorOperationsPageStatus.UNAVAILABLE
    )


def test_successor_startup_uses_complete_real_edge_verifier(
    tmp_path: Path,
) -> None:
    paths, successor_payload = _write_successor_edge(tmp_path)

    service = app.build_startup_service(
        GuiStartupConfiguration(
            paper_account_prior=paths[0],
            paper_account_snapshot=paths[1],
            paper_account_cycle_report=paths[2],
            paper_account_successor=paths[3],
            paper_account_successor_expected_sha256=hashlib.sha256(
                successor_payload
            ).hexdigest(),
            paper_account_successor_expected_byte_length=len(successor_payload),
        )
    )

    state = service.get_paper_account_state()

    assert state.status is PaperAccountPageStatus.VERIFIED
    assert state.account is not None
    assert (
        state.account.checkpoint_kind
        is PaperAccountCheckpointKindView.CYCLE_SUCCESSOR
    )
    assert state.account.sequence == 1
    assert service.get_market_data_state().status is MarketDataPageStatus.UNAVAILABLE
    assert service.get_research_state().status is ResearchReportStatus.UNAVAILABLE


def test_one_invalid_artifact_does_not_replace_other_valid_sources(
    tmp_path: Path,
) -> None:
    genesis_path, _ = _write_genesis(tmp_path)
    missing_snapshot = tmp_path / "private-missing-market-snapshot.json"

    service = app.build_startup_service(
        GuiStartupConfiguration(
            research_report=RESEARCH_FIXTURE,
            market_data_snapshot=missing_snapshot,
            paper_account_genesis=genesis_path,
        )
    )

    research = service.get_research_state()
    market_data = service.get_market_data_state()
    paper_account = service.get_paper_account_state()

    assert research.status is ResearchReportStatus.LOADED
    assert market_data.status is MarketDataPageStatus.UNAVAILABLE
    assert str(missing_snapshot) not in market_data.message
    assert paper_account.status is PaperAccountPageStatus.VERIFIED


def test_multi_source_composition_never_discovers_latest_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot_path, _ = _write_market_snapshot(tmp_path)
    genesis_path, _ = _write_genesis(tmp_path)

    def forbidden_discovery(*args, **kwargs):
        raise AssertionError("GUI-A8 must not discover latest artifacts")

    monkeypatch.setattr(Path, "iterdir", forbidden_discovery)
    monkeypatch.setattr(Path, "glob", forbidden_discovery)
    monkeypatch.setattr(Path, "rglob", forbidden_discovery)

    service = app.build_startup_service(
        GuiStartupConfiguration(
            research_report=RESEARCH_FIXTURE,
            market_data_snapshot=snapshot_path,
            paper_account_genesis=genesis_path,
        )
    )

    assert service.get_research_state().status is ResearchReportStatus.LOADED
    assert service.get_market_data_state().status is MarketDataPageStatus.VERIFIED
    assert (
        service.get_paper_account_state().status
        is PaperAccountPageStatus.VERIFIED
    )
