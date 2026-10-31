"""Explicit synthetic fixtures; none selects a production paper strategy."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

import pytest

from trading_bot.desktop_paper.configuration import (
    PaperStrategyBinding,
    create_paper_evaluation_config,
)
from trading_bot.desktop_paper.models import PaperRuntimePolicy
from trading_bot.desktop_paper.observations import OpenReplayObservationSource
from trading_bot.domain import Bar, OrderSide, Symbol, TradeProposal


@pytest.fixture
def paper_config():
    binding = PaperStrategyBinding(
        "SYNTHETIC_FIXTURE",
        "test-v1",
        Symbol("QQQ"),
        (("fixture", True),),
        uuid5(NAMESPACE_URL, "p5-test-campaign"),
        uuid5(NAMESPACE_URL, "p5-test-bundle"),
        uuid5(NAMESPACE_URL, "p5-test-candidate"),
        "a" * 64,
    )
    return create_paper_evaluation_config(binding, PaperRuntimePolicy())


@pytest.fixture
def paper_source_factory(paper_config):
    symbol = paper_config.binding.symbol
    bars = tuple(
        Bar(
            symbol,
            datetime(2020, 1, 1, tzinfo=UTC) + timedelta(days=index),
            Decimal("100"),
            Decimal("102"),
            Decimal("99"),
            Decimal("101"),
            1000,
        )
        for index in range(4)
    )
    return lambda: OpenReplayObservationSource.from_bars(
        bars, symbol=symbol, minimum_history_bars=1
    )


class SyntheticBuyEvaluator:
    def evaluate(self, value):
        return TradeProposal(
            uuid5(
                NAMESPACE_URL,
                "synthetic-proposal:" + value.execution_timestamp.isoformat(),
            ),
            value.binding.symbol,
            OrderSide.BUY,
            Decimal("10"),
            value.execution_timestamp,
            "Synthetic infrastructure fixture only",
        )


@pytest.fixture
def paper_evaluator():
    return SyntheticBuyEvaluator()
