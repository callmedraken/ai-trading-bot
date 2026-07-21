from decimal import Decimal
from uuid import uuid4

import pytest
from tests.multi_backtesting.test_engine import Provider, config, data

from trading_bot.domain import OrderSide, Symbol, TradeProposal
from trading_bot.multi_backtesting import (
    MultiSymbolBacktestEngine,
    MultiSymbolStrategyContractError,
)


def test_strategy_rejects_outside_symbol_and_mistimed_proposal() -> None:
    source = data()

    class Bad:
        def evaluate(self, context):  # type: ignore[no-untyped-def]
            return (
                TradeProposal.create(
                    proposal_id=uuid4(),
                    symbol=Symbol("DIA"),
                    side=OrderSide.BUY,
                    desired_quantity=Decimal("1"),
                    created_at=context.timestamp,
                    reason="bad",
                ),
            )

    with pytest.raises(MultiSymbolStrategyContractError, match="outside"):
        MultiSymbolBacktestEngine(Provider(source)).run(config(source), Bad())


def test_strategy_rejects_two_proposals_for_one_symbol() -> None:
    source = data()

    class Bad:
        def evaluate(self, context):  # type: ignore[no-untyped-def]
            if context.step_index:
                return ()
            return tuple(
                TradeProposal.create(
                    proposal_id=uuid4(),
                    symbol=Symbol("SPY"),
                    side=OrderSide.BUY,
                    desired_quantity=Decimal("1"),
                    created_at=context.timestamp,
                    reason="bad",
                )
                for _ in range(2)
            )

    with pytest.raises(MultiSymbolStrategyContractError, match="one proposal"):
        MultiSymbolBacktestEngine(Provider(source)).run(config(source), Bad())
