from copy import deepcopy
from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest
from tests.multi_backtesting.test_engine import RUN_ID, data, limits

from trading_bot.execution import OrderEngine
from trading_bot.ledger import PaperLedger
from trading_bot.multi_backtesting import (
    InvalidMultiSymbolBacktestConfigError,
    MultiSymbolBacktestConfig,
)


def test_config_is_immutable_and_validates_commission_consistency() -> None:
    source = data()
    item = MultiSymbolBacktestConfig(RUN_ID, source.request, risk_limits=limits())
    with pytest.raises(FrozenInstanceError):
        item.starting_cash = Decimal("1")  # type: ignore[misc]
    with pytest.raises(InvalidMultiSymbolBacktestConfigError, match="commission"):
        MultiSymbolBacktestConfig(
            RUN_ID,
            source.request,
            fixed_commission=Decimal("1"),
            risk_limits=limits(),
        )


def test_order_engine_and_ledger_are_safely_deepcopyable() -> None:
    orders = OrderEngine()
    ledger = PaperLedger(Decimal("1000"))
    copied_orders = deepcopy(orders)
    copied_ledger = deepcopy(ledger)
    assert copied_orders.orders == orders.orders
    assert copied_orders.get_events() == orders.get_events()
    assert copied_ledger.cash == ledger.cash
    assert copied_ledger.positions == ledger.positions
    assert copied_ledger.fills == ledger.fills
