from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, localcontext

import pytest

from trading_bot.portfolio_manager.adapters import (
    PortfolioStateAdapterError,
    to_portfolio_state,
)
from trading_bot.portfolio_manager.models import ObservationCondition

from .conftest import make_observation, make_position


def test_complete_known_observation_converts_to_existing_strict_portfolio() -> None:
    observation = make_observation(
        (
            make_position("SPY", "1.5", price="101", cost="99"),
            make_position("TLT", "2", price="95", cost="100"),
        ),
        cash="10000",
    )

    converted = to_portfolio_state(observation)

    assert converted.as_of == observation.observed_at
    assert converted.symbols == tuple(item.symbol for item in observation.positions)
    assert tuple(item.quantity for item in converted.positions) == (
        Decimal("1.5"),
        Decimal("2"),
    )
    assert tuple(item.average_cost for item in converted.positions) == (
        Decimal("99"),
        Decimal("100"),
    )
    assert converted.cash == observation.cash
    assert converted.equity == observation.locally_computed_equity


def test_cash_only_and_unknown_cost_observations_remain_observation_only() -> None:
    cash_only = make_observation((), cash="2500")
    unknown_cost = make_observation(
        (make_position("SPY", "1.25", cost=None),), cash="2500"
    )

    assert cash_only.locally_computed_equity == Decimal("2500")
    with pytest.raises(PortfolioStateAdapterError, match="NONEMPTY_POSITIONS"):
        to_portfolio_state(cash_only)

    assert unknown_cost.positions[0].average_cost is None
    assert unknown_cost.positions[0].unrealized_pnl is None
    with pytest.raises(PortfolioStateAdapterError, match="COST_OR_CHRONOLOGY"):
        to_portfolio_state(unknown_cost)


def test_stale_and_reconciliation_conditions_block_strict_conversion() -> None:
    base = make_observation((make_position("SPY"),))
    stale = replace(base, conditions=(ObservationCondition.STALE_PRICE,))
    uncertain = replace(
        base, conditions=(ObservationCondition.RECONCILIATION_UNCERTAIN,)
    )
    mismatched_equity = make_observation((make_position("SPY"),), broker_equity="99999")

    for observation, condition in (
        (stale, ObservationCondition.STALE_PRICE),
        (uncertain, ObservationCondition.RECONCILIATION_UNCERTAIN),
        (
            mismatched_equity,
            ObservationCondition.BROKER_EQUITY_DIFFERS_FROM_LOCAL,
        ),
    ):
        assert condition in observation.conditions
        with pytest.raises(PortfolioStateAdapterError, match="NOT_STRICTLY_VALUED"):
            to_portfolio_state(observation)


def test_strict_conversion_is_independent_of_low_ambient_decimal_precision() -> None:
    position = make_position("SPY", "1.2345", price="1.2345", cost="1.1111")
    observation = make_observation((position,), cash="10000")

    with localcontext() as context:
        context.prec = 4
        converted = to_portfolio_state(observation)

    assert converted.positions[0].market_value == Decimal("1.52399025")
    assert converted.equity == Decimal("10001.52399025")
