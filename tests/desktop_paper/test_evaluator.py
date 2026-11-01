"""Focused BASE_MA evaluator semantics and risk-boundary coverage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

import pytest

from trading_bot.desktop_paper.configuration import (
    PaperStrategyBinding,
    PaperStrategyEvaluationInput,
)
from trading_bot.desktop_paper.evaluator import FilteredTrendBaseMaEvaluator
from trading_bot.desktop_paper.models import PaperAccountState
from trading_bot.domain import Bar, OrderSide, Position, Symbol, TradeProposal

SYMBOL = Symbol("SPY")


def _binding(**changes) -> PaperStrategyBinding:
    values = {
        "strategy_family": "FILTERED_TREND_BASE_MA",
        "strategy_version": "filtered-trend-base-ma/v1",
        "symbol": SYMBOL,
        "parameter_set": (("fast", 35), ("slow", 50)),
        "research_campaign_id": uuid5(NAMESPACE_URL, "campaign"),
        "research_bundle_id": uuid5(NAMESPACE_URL, "bundle"),
        "research_candidate_id": uuid5(NAMESPACE_URL, "candidate"),
        "provenance_digest": "a" * 64,
    }
    values.update(changes)
    return PaperStrategyBinding(**values)


def _history(values: list[str]) -> tuple[Bar, ...]:
    return tuple(
        Bar(
            SYMBOL,
            datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=index),
            Decimal(price),
            Decimal(price) + 1,
            Decimal(price) - 1,
            Decimal(price),
            100,
        )
        for index, price in enumerate(values)
    )


def _input(history, account=None, *, execution_day=60):
    return PaperStrategyEvaluationInput(
        _binding(),
        history,
        datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=execution_day),
        account,
    )


def _account_with_position() -> PaperAccountState:
    return PaperAccountState(
        cash=Decimal("90000"),
        positions={SYMBOL: Position(SYMBOL, Decimal("7"), Decimal("100"))},
        realized_profit_loss=Decimal("0"),
        marked_equity=None,
        unrealized_profit_loss=None,
    )


def test_base_ma_35_50_uses_completed_data_and_no_filtered_family() -> None:
    history = _history(["100"] * 15 + ["110"] * 35)
    proposal = FilteredTrendBaseMaEvaluator().evaluate(_input(history))

    assert isinstance(proposal, TradeProposal)
    assert proposal.side is OrderSide.BUY
    assert proposal.symbol == SYMBOL
    assert proposal.desired_quantity == Decimal("1")
    assert proposal.created_at == datetime(2025, 3, 2, tzinfo=UTC)


def test_bearish_exit_is_reachable_and_liquidates_position() -> None:
    history = _history(["110"] * 15 + ["100"] * 35)
    proposal = FilteredTrendBaseMaEvaluator().evaluate(
        _input(history, _account_with_position())
    )

    assert proposal is not None
    assert proposal.side is OrderSide.SELL
    assert proposal.desired_quantity == Decimal("7")


def test_input_rejects_n_close_and_future_bar_lookahead() -> None:
    history = _history(["100"] * 15 + ["110"] * 35)
    execution = datetime(2025, 3, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="end before execution"):
        PaperStrategyEvaluationInput(
            _binding(),
            history
            + (
                Bar(
                    SYMBOL,
                    execution,
                    Decimal("999"),
                    Decimal("1000"),
                    Decimal("998"),
                    Decimal("999"),
                    100,
                ),
            ),
            execution,
        )


def test_wrong_candidate_or_family_cannot_change_evaluator_semantics() -> None:
    history = _history(["100"] * 15 + ["110"] * 35)
    evaluator = FilteredTrendBaseMaEvaluator()
    with pytest.raises(ValueError, match="BINDING_REJECTED"):
        evaluator.evaluate(
            PaperStrategyEvaluationInput(
                _binding(strategy_family="FILTERED_TREND_MA_ADX"),
                history,
                datetime(2025, 3, 1, tzinfo=UTC),
            )
        )


def test_evaluator_returns_intent_only_and_risk_remains_downstream() -> None:
    history = _history(["100"] * 15 + ["110"] * 35)
    proposal = FilteredTrendBaseMaEvaluator().evaluate(_input(history))

    assert isinstance(proposal, TradeProposal)
    assert not hasattr(proposal, "risk_decision")
    assert not hasattr(proposal, "fill")
