from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

import pytest

from trading_bot.desktop_paper.configuration import create_paper_evaluation_config
from trading_bot.desktop_paper.engine import PaperCycleEngine, cycle_identity
from trading_bot.desktop_paper.models import (
    PaperControlState,
    PaperCycleInput,
    PaperCycleKind,
)
from trading_bot.domain import OrderFill, OrderSide, Symbol, TradeProposal
from trading_bot.ledger import PaperLedger
from trading_bot.risk import RiskReasonCode

T0 = datetime(2026, 10, 1, 13, 30, tzinfo=UTC)
QQQ = Symbol("QQQ")


def _proposal(symbol: Symbol, side: OrderSide, at: datetime, quantity: str = "1"):
    return TradeProposal(
        proposal_id=uuid5(NAMESPACE_URL, f"proposal:{symbol}:{at.isoformat()}"),
        symbol=symbol,
        side=side,
        desired_quantity=Decimal(quantity),
        created_at=at,
        reason="deterministic engine test",
    )


def _cycle(
    *,
    symbol: Symbol = QQQ,
    side: OrderSide = OrderSide.BUY,
    index: int = 1,
    quantity: str = "1",
    marks: dict[Symbol, Decimal] | None = None,
) -> PaperCycleInput:
    at = T0 + timedelta(days=index)
    session = at.date().isoformat()
    return PaperCycleInput(
        execution_session_id=session,
        execution_index=index,
        symbol=symbol,
        observation_id=uuid5(NAMESPACE_URL, f"observation:{session}"),
        completed_history_cutoff=(at - timedelta(days=1)).isoformat(),
        observation_open=Decimal("100"),
        executed_at=at,
        proposal=_proposal(symbol, side, at, quantity),
        current_marks=marks,
    )


def _engine(paper_config) -> PaperCycleEngine:
    return PaperCycleEngine(
        account_id=uuid5(NAMESPACE_URL, "paper-account"),
        source_lane=paper_config.policy.source_lane,
        policy=paper_config.policy,
        configuration_revision_id=paper_config.configuration_revision_id,
    )


def test_buy_and_sell_slippage_prices_are_the_risk_and_fill_prices(
    paper_config,
) -> None:
    symbol = paper_config.binding.symbol
    engine = _engine(paper_config)
    buy = engine.process(
        _cycle(symbol=symbol, side=OrderSide.BUY),
        PaperLedger(paper_config.policy.starting_cash),
        PaperControlState(0, False, True),
    )
    assert buy.risk_context is not None
    assert buy.risk_context.current_price == Decimal("100.05")
    assert buy.fill is not None and buy.fill.price == Decimal("100.05")

    ledger = PaperLedger(paper_config.policy.starting_cash)
    seed_fill = OrderFill(
        fill_id=uuid5(NAMESPACE_URL, "seed-fill"),
        order_id=uuid5(NAMESPACE_URL, "seed-order"),
        symbol=symbol,
        side=OrderSide.BUY,
        quantity=Decimal("2"),
        price=Decimal("100"),
        commission=Decimal("1"),
        filled_at=T0,
    )
    ledger.apply_fill(seed_fill)
    sell = engine.process(
        _cycle(symbol=symbol, side=OrderSide.SELL, index=1, quantity="1"),
        ledger,
        PaperControlState(0, False, False),
    )
    assert sell.kind is PaperCycleKind.FILLED
    assert sell.risk_context is not None
    assert sell.risk_context.current_price == Decimal("99.95")
    assert sell.fill is not None and sell.fill.price == Decimal("99.95")


def test_incomplete_multi_symbol_marks_keep_valuation_unavailable_and_block_buy(
    paper_config,
) -> None:
    symbol = paper_config.binding.symbol
    other = Symbol("IWM")
    ledger = PaperLedger(paper_config.policy.starting_cash)
    for name, held_symbol in (("qqq", symbol), ("iwm", other)):
        ledger.apply_fill(
            OrderFill(
                fill_id=uuid5(NAMESPACE_URL, f"seed-fill:{name}"),
                order_id=uuid5(NAMESPACE_URL, f"seed-order:{name}"),
                symbol=held_symbol,
                side=OrderSide.BUY,
                quantity=Decimal("1"),
                price=Decimal("100"),
                commission=Decimal("1"),
                filled_at=T0,
            )
        )

    result = _engine(paper_config).process(
        _cycle(symbol=symbol, side=OrderSide.BUY, marks={symbol: Decimal("100")}),
        ledger,
        PaperControlState(0, False, True),
    )

    assert result.kind is PaperCycleKind.RISK_REJECTED
    assert result.risk_decision is not None
    assert result.risk_decision.reasons[0].code is RiskReasonCode.PRICE_NOT_AVAILABLE
    assert result.order is None and result.fill is None
    assert result.account.marked_equity is None
    assert result.account.unrealized_profit_loss is None
    assert set(result.account.positions) == {symbol, other}


@pytest.mark.parametrize("price", [Decimal("0"), Decimal("-1"), None])
def test_invalid_execution_prices_are_rejected_before_financial_evaluation(
    paper_config, price
) -> None:
    at = T0 + timedelta(days=1)
    with pytest.raises((TypeError, ValueError)):
        PaperCycleInput(
            execution_session_id="invalid-price-session",
            execution_index=1,
            symbol=paper_config.binding.symbol,
            observation_id=uuid5(NAMESPACE_URL, "invalid-price-observation"),
            completed_history_cutoff=None,
            observation_open=price,
            executed_at=at,
            proposal=_proposal(paper_config.binding.symbol, OrderSide.BUY, at),
        )


def test_warmup_and_no_signal_are_explicit_non_effect_cycles(paper_config) -> None:
    engine = _engine(paper_config)
    warmup = replace(
        _cycle(symbol=paper_config.binding.symbol),
        proposal=None,
        warmup=True,
        no_signal_reason="INSUFFICIENT_HISTORY",
    )
    no_signal = replace(
        _cycle(symbol=paper_config.binding.symbol, index=2),
        proposal=None,
        no_signal_reason="STRATEGY_HOLD",
    )
    ledger = PaperLedger(paper_config.policy.starting_cash)
    control = PaperControlState(0, False, True)

    first = engine.process(warmup, ledger, control)
    second = engine.process(no_signal, ledger, control)

    assert first.kind is PaperCycleKind.WARMUP
    assert second.kind is PaperCycleKind.NO_SIGNAL
    assert first.risk_decision is None and first.order is None and first.fill is None
    assert second.risk_decision is None and second.order is None and second.fill is None
    assert (
        first.account.cash == second.account.cash == paper_config.policy.starting_cash
    )


def test_slot_identity_does_not_include_configuration_revision(paper_config) -> None:
    cycle = _cycle(symbol=paper_config.binding.symbol)
    first = cycle_identity(
        uuid5(NAMESPACE_URL, "account"),
        paper_config.policy.source_lane,
        cycle.symbol.value,
        cycle.execution_session_id,
    )
    changed_policy = replace(
        paper_config.policy, replay_interval_seconds=Decimal("0.20")
    )
    changed_config = create_paper_evaluation_config(
        paper_config.binding, changed_policy
    )
    second = cycle_identity(
        uuid5(NAMESPACE_URL, "account"),
        changed_config.policy.source_lane,
        cycle.symbol.value,
        cycle.execution_session_id,
    )

    assert first == second
