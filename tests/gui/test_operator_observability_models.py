from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from trading_bot.gui.operator_observability_models import (
    OPERATOR_WARMUP_TARGET_COUNT,
    OperatorAccountSummaryView,
    OperatorEffectGateState,
    OperatorObservabilityState,
    OperatorOperationsPageState,
    OperatorOperationsPageStatus,
    OperatorStrategyExplanationStatus,
    OperatorStrategyExplanationView,
    OperatorWarmupClassification,
    OperatorWarmupView,
    SelectedC3WarmupSessionView,
    unavailable_operator_operations_state,
)


def _selected(day: int) -> SelectedC3WarmupSessionView:
    return SelectedC3WarmupSessionView(
        session_date=date(2026, 9, day),
        symbol="SPY",
        close=Decimal("760.25") + Decimal(day),
        snapshot_id=UUID(int=day),
        selection_id=UUID(int=100 + day),
    )


def _required() -> tuple[date, ...]:
    return tuple(date(2026, 9, day) for day in (8, 9, 10, 11, 14, 15))


def _closed_gates() -> OperatorEffectGateState:
    return OperatorEffectGateState(
        market_data_capture=False,
        decision_publication=False,
        production=False,
        recovery=False,
        supervised_execution=False,
        receipt_recovery=False,
        unattended_execution=False,
        unattended_storage_provisioning=False,
    )


def test_warming_up_view_reports_selected_and_missing_sessions() -> None:
    view = OperatorWarmupView(
        classification=OperatorWarmupClassification.WARMING_UP,
        required_sessions=_required(),
        selected_sessions=(_selected(11), _selected(14), _selected(15)),
    )

    assert view.target_count == OPERATOR_WARMUP_TARGET_COUNT == 6
    assert view.selected_count == 3
    assert view.missing_sessions == (
        date(2026, 9, 8),
        date(2026, 9, 9),
        date(2026, 9, 10),
    )


def test_ready_view_requires_all_six_selected_sessions() -> None:
    selected = tuple(
        SelectedC3WarmupSessionView(
            session_date=session,
            symbol="SPY",
            close=Decimal("700") + Decimal(index),
            snapshot_id=UUID(int=10 + index),
            selection_id=UUID(int=20 + index),
        )
        for index, session in enumerate(_required(), start=1)
    )

    view = OperatorWarmupView(
        classification=OperatorWarmupClassification.READY,
        required_sessions=_required(),
        selected_sessions=selected,
    )

    assert view.selected_count == 6
    assert view.missing_sessions == ()


@pytest.mark.parametrize(
    ("classification", "selected"),
    [
        (OperatorWarmupClassification.READY, (_selected(11),)),
        (
            OperatorWarmupClassification.WARMING_UP,
            tuple(
                SelectedC3WarmupSessionView(
                    session_date=session,
                    symbol="SPY",
                    close=Decimal("700") + Decimal(index),
                    snapshot_id=UUID(int=30 + index),
                    selection_id=UUID(int=40 + index),
                )
                for index, session in enumerate(_required(), start=1)
            ),
        ),
        (OperatorWarmupClassification.BLOCKED, (_selected(11),)),
    ],
)
def test_warmup_classification_rejects_inconsistent_selected_count(
    classification: OperatorWarmupClassification,
    selected: tuple[SelectedC3WarmupSessionView, ...],
) -> None:
    with pytest.raises(ValueError):
        OperatorWarmupView(
            classification=classification,
            required_sessions=_required(),
            selected_sessions=selected,
        )


def test_warmup_view_rejects_selected_session_outside_required_window() -> None:
    with pytest.raises(ValueError, match="belong"):
        OperatorWarmupView(
            classification=OperatorWarmupClassification.WARMING_UP,
            required_sessions=_required(),
            selected_sessions=(_selected(7),),
        )


def test_selected_session_rejects_non_ascii_uppercase_symbol() -> None:
    with pytest.raises(ValueError, match="canonical presentation text"):
        SelectedC3WarmupSessionView(
            session_date=date(2026, 9, 15),
            symbol="SPÅY",
            close=Decimal("757.39"),
            snapshot_id=UUID(int=1),
            selection_id=UUID(int=2),
        )


def test_effect_gate_view_is_closed_only_when_every_gate_is_false() -> None:
    closed = _closed_gates()
    opened = OperatorEffectGateState(
        market_data_capture=True,
        decision_publication=False,
        production=False,
        recovery=False,
        supervised_execution=False,
        receipt_recovery=False,
        unattended_execution=False,
        unattended_storage_provisioning=False,
    )

    assert closed.all_closed is True
    assert closed.as_tuple() == (False,) * 8
    assert opened.all_closed is False
    assert opened.as_tuple()[0] is True


def test_effect_gate_view_requires_exact_bools() -> None:
    with pytest.raises(TypeError, match="exact bools"):
        OperatorEffectGateState(
            market_data_capture=0,  # type: ignore[arg-type]
            decision_publication=False,
            production=False,
            recovery=False,
            supervised_execution=False,
            receipt_recovery=False,
            unattended_execution=False,
            unattended_storage_provisioning=False,
        )


def test_operator_observability_state_is_frozen() -> None:
    state = OperatorObservabilityState(
        warmup=OperatorWarmupView(
            classification=OperatorWarmupClassification.WARMING_UP,
            required_sessions=_required(),
            selected_sessions=(_selected(11),),
        ),
        gates=_closed_gates(),
    )

    with pytest.raises(FrozenInstanceError):
        state.gates = _closed_gates()  # type: ignore[misc]


def _account() -> OperatorAccountSummaryView:
    return OperatorAccountSummaryView(
        paper_account_id="paper-account",
        checkpoint_id=UUID(int=500),
        sequence=1,
        as_of=datetime(2026, 8, 31, 13, 30, tzinfo=UTC),
        cash=Decimal("25000"),
        realized_profit_loss=Decimal("0"),
        positions=(),
        lineage_edge_count=1,
        receipt_count=1,
    )


def test_operations_available_state_reports_strategy_readiness() -> None:
    selected = tuple(
        SelectedC3WarmupSessionView(
            session_date=session,
            symbol="SPY",
            close=Decimal("700") + Decimal(index),
            snapshot_id=UUID(int=600 + index),
            selection_id=UUID(int=700 + index),
        )
        for index, session in enumerate(_required(), start=1)
    )
    warmup = OperatorWarmupView(
        classification=OperatorWarmupClassification.READY,
        required_sessions=_required(),
        selected_sessions=selected,
    )
    state = OperatorOperationsPageState(
        status=OperatorOperationsPageStatus.AVAILABLE,
        message="Read-only.",
        cycle_classification="BLOCKED",
        completed_session=date(2026, 9, 15),
        market_data_classification="NO_NEW_COMPLETED_SESSION",
        selected_snapshot_id=UUID(int=606),
        warmup=warmup,
        gates=_closed_gates(),
        account=_account(),
    )

    assert state.strategy_ready is True
    assert state.account is not None and state.account.cash == Decimal("25000")


def test_unavailable_operations_state_exposes_no_runtime_details() -> None:
    state = unavailable_operator_operations_state()

    assert state.status is OperatorOperationsPageStatus.UNAVAILABLE
    assert state.warmup is None
    assert state.gates is None
    assert state.account is None
    assert state.strategy_ready is False


def test_unavailable_operations_state_rejects_attached_authority_details() -> None:
    with pytest.raises(ValueError, match="cannot expose details"):
        OperatorOperationsPageState(
            status=OperatorOperationsPageStatus.UNAVAILABLE,
            message="Unavailable.",
            gates=_closed_gates(),
        )



def test_strategy_explanation_requires_exact_complete_window_for_buy() -> None:
    explanation = OperatorStrategyExplanationView(
        status=OperatorStrategyExplanationStatus.BUY,
        short_window=3,
        long_window=5,
        desired_quantity=Decimal("1"),
        symbol="SPY",
        sessions=_required(),
        closes=(
            Decimal("764.29"),
            Decimal("760.88"),
            Decimal("757.39"),
            Decimal("754.05"),
            Decimal("762.6"),
            Decimal("761.69"),
        ),
        previous_short=Decimal("758.0133333333333333333333333"),
        previous_long=Decimal("759.842"),
        current_short=Decimal("759.4466666666666666666666667"),
        current_long=Decimal("759.322"),
        crossover_side="BUY",
        actionable_side="BUY",
        invested=False,
    )

    assert explanation.status is OperatorStrategyExplanationStatus.BUY
    assert explanation.actionable_side == "BUY"


def test_strategy_explanation_incomplete_history_has_no_derived_values() -> None:
    explanation = OperatorStrategyExplanationView(
        status=OperatorStrategyExplanationStatus.INSUFFICIENT_HISTORY,
        short_window=3,
        long_window=5,
        desired_quantity=Decimal("1"),
        symbol="SPY",
        sessions=(_required()[-1],),
        closes=(Decimal("761.69"),),
        previous_short=None,
        previous_long=None,
        current_short=None,
        current_long=None,
        crossover_side=None,
        actionable_side=None,
        invested=False,
    )

    assert explanation.previous_short is None
    assert explanation.actionable_side is None


def test_strategy_explanation_rejects_complete_status_without_six_closes() -> None:
    with pytest.raises(ValueError, match="long_window \+ 1 closes"):
        OperatorStrategyExplanationView(
            status=OperatorStrategyExplanationStatus.NO_CROSSOVER,
            short_window=3,
            long_window=5,
            desired_quantity=Decimal("1"),
            symbol="SPY",
            sessions=(_required()[-1],),
            closes=(Decimal("761.69"),),
            previous_short=Decimal("1"),
            previous_long=Decimal("1"),
            current_short=Decimal("1"),
            current_long=Decimal("1"),
            crossover_side=None,
            actionable_side=None,
            invested=False,
        )
