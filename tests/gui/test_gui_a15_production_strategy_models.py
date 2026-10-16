"""Strict immutable strategy models and pure cross-evidence composition."""

from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime
from decimal import Decimal, localcontext
from pathlib import Path
from uuid import UUID

import pytest

from trading_bot.domain import Symbol
from trading_bot.gui import (
    ProductionRuntimeEvidenceInspectionService,
    ProductionStrategyContractView,
    ProductionStrategyDiagnostic,
    ProductionStrategyPageState,
    ProductionStrategyPageStatus,
    SupervisorConsistency,
    SupervisorPageStatus,
    build_supervisor_state,
    unavailable_production_strategy_state,
    unavailable_runtime_state,
)
from trading_bot.gui.research_service import (
    CompactReportResearchService,
    unavailable_research_state,
)
from trading_bot.strategies.moving_average import MovingAverageCrossoverConfig
from trading_bot.strategies.production import ProductionStrategyContract


def strategy_view() -> ProductionStrategyContractView:
    contract = ProductionStrategyContract(
        date(2026, 10, 12),
        "b" * 40,
        "c" * 40,
        Symbol("SPY"),
        MovingAverageCrossoverConfig(5, 20, Decimal("1.123456789012345678901")),
    )
    return ProductionStrategyContractView(
        contract.contract_id,
        contract.target_session_date,
        contract.source_head,
        contract.source_tree,
        contract.strategy_id,
        contract.strategy_version,
        str(contract.symbol),
        5,
        20,
        contract.strategy_config.desired_quantity,
    )


def strategy_state() -> ProductionStrategyPageState:
    return ProductionStrategyPageState(
        ProductionStrategyPageStatus.AVAILABLE,
        ProductionStrategyDiagnostic.RECORDED,
        strategy_view(),
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"contract_id": "id"},
        {"contract_id": UUID(int=0)},
        {"target_session_date": datetime(2026, 10, 12)},
        {"source_head": "A" * 40},
        {"source_tree": "a" * 39},
        {"strategy_id": "<b>secret</b>"},
        {"strategy_version": "2"},
        {"symbol": "C:/private"},
        {"short_window": True},
        {"long_window": 5},
        {"long_window": 1_000_001},
        {"desired_quantity": "1"},
        {"desired_quantity": Decimal("NaN")},
        {"desired_quantity": Decimal("0")},
        {"desired_quantity": Decimal("1E+1000")},
    ],
)
def test_strict_strategy_view(changes):
    with pytest.raises((TypeError, ValueError)):
        replace(strategy_view(), **changes)


def test_state_bounds_immutability_and_exact_quantity():
    view = strategy_view()
    with pytest.raises(FrozenInstanceError):
        view.symbol = "QQQ"
    with localcontext() as context:
        context.prec = 3
        assert format(view.desired_quantity, "f") == "1.123456789012345678901"
    for status, diagnostic, contract in (
        ("AVAILABLE", ProductionStrategyDiagnostic.RECORDED, view),
        (
            ProductionStrategyPageStatus.AVAILABLE,
            ProductionStrategyDiagnostic.RECORDED,
            None,
        ),
        (
            ProductionStrategyPageStatus.UNAVAILABLE,
            ProductionStrategyDiagnostic.NO_CONTRACT,
            view,
        ),
        (
            ProductionStrategyPageStatus.ATTENTION,
            ProductionStrategyDiagnostic.RECORDED,
            view,
        ),
    ):
        with pytest.raises((TypeError, ValueError)):
            ProductionStrategyPageState(status, diagnostic, contract)


def test_contract_only_and_fixed_promotion_policy():
    state = build_supervisor_state(
        unavailable_research_state(), unavailable_runtime_state(), strategy_state()
    )
    assert state.status is SupervisorPageStatus.AVAILABLE
    assert state.consistency is SupervisorConsistency.NOT_CHECKED
    assert state.automatic_promotion_enabled is False
    assert state.human_promotion_required is True
    assert state.promotion_authority_connected is False
    assert state.can_research_replace_production is False
    assert state.supervisor_connected is False
    with pytest.raises((TypeError, ValueError)):
        replace(state, automatic_promotion_enabled=True)


@pytest.mark.parametrize(
    "field,value",
    [
        (None, None),
        ("contract_id", UUID("11111111-1111-5111-8111-111111111111")),
        ("source_head", "d" * 40),
        ("source_tree", "e" * 40),
        ("target_session", date(2026, 10, 13)),
    ],
)
def test_exact_semantic_session_comparison(field, value):
    fixtures = Path(__file__).resolve().parents[1] / "fixtures/gui/runtime"
    runtime = ProductionRuntimeEvidenceInspectionService(
        session=fixtures / "session-waiting.json"
    ).get_runtime_state()
    view = strategy_view()
    session = replace(
        runtime.session,
        contract_id=view.contract_id,
        source_head=view.source_head,
        source_tree=view.source_tree,
        target_session=view.target_session_date,
    )
    if field is not None:
        session = replace(session, **{field: value})
    state = build_supervisor_state(
        unavailable_research_state(),
        replace(runtime, session=session),
        strategy_state(),
    )
    assert state.consistency is (
        SupervisorConsistency.CONSISTENT
        if field is None
        else SupervisorConsistency.CONFLICTING
    )
    assert state.status is (
        SupervisorPageStatus.AVAILABLE
        if field is None
        else SupervisorPageStatus.ATTENTION
    )


def test_research_is_evidence_and_paths_never_propagate():
    path = (
        Path(__file__).resolve().parents[1]
        / "fixtures/cli/historical-experiment-compact-report-v1-compact.json"
    )
    research = CompactReportResearchService(path).get_research_state()
    assert research.report is not None
    state = build_supervisor_state(
        research, unavailable_runtime_state(), unavailable_production_strategy_state()
    )
    assert state.research_report_id == UUID(research.report.report_id)
    assert state.research_experiment_result_id == UUID(
        research.report.experiment_result_id
    )
    assert "Research evidence available" in state.research_message
    assert str(path) not in repr(state)
    assert "active" not in state.research_message.lower()
    assert "running" not in state.research_message.lower()


def test_no_evidence_invalid_strategy_and_exact_builder_types():
    absent = unavailable_production_strategy_state()
    default = build_supervisor_state(
        unavailable_research_state(), unavailable_runtime_state(), absent
    )
    assert default.status is SupervisorPageStatus.UNAVAILABLE
    assert default.research_message == "Research evidence not connected."
    invalid = ProductionStrategyPageState(
        ProductionStrategyPageStatus.ATTENTION, ProductionStrategyDiagnostic.INVALID
    )
    assert (
        build_supervisor_state(
            unavailable_research_state(), unavailable_runtime_state(), invalid
        ).status
        is SupervisorPageStatus.ATTENTION
    )
    with pytest.raises(TypeError):
        build_supervisor_state(None, unavailable_runtime_state(), absent)
