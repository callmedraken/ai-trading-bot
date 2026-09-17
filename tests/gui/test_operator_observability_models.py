from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from trading_bot.gui.operator_observability_models import (
    OPERATOR_WARMUP_TARGET_COUNT,
    OperatorEffectGateState,
    OperatorObservabilityState,
    OperatorWarmupClassification,
    OperatorWarmupView,
    SelectedC3WarmupSessionView,
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
