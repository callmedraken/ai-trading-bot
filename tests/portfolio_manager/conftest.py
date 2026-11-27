from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256

import pytest

from trading_bot.domain import Symbol
from trading_bot.portfolio_manager.decision import (
    MarketQuote,
    MarketResearchInput,
    MarketSignal,
)
from trading_bot.portfolio_manager.models import (
    ObservationCoverage,
    ObservationProvenance,
    OrderCoverage,
    OrderObservation,
    PortfolioObservation,
    PositionObservation,
    PositionType,
    decimal_sum,
)

NOW = datetime(2026, 11, 26, 20, 0, tzinfo=UTC)
ACCOUNT_FP = sha256(b"pm1 synthetic account").hexdigest()


def make_position(
    symbol: str,
    quantity: str = "1",
    *,
    price: str = "100",
    cost: str | None = "90",
    available: str | None = None,
    price_at: datetime = NOW,
    # Synthetic fixtures model a known supported equity unless a test opts out.
    supported: bool | None = True,
    position_type: PositionType | None = None,
) -> PositionObservation:
    quantity_value = Decimal(quantity)
    if available is None:
        available = quantity
    if position_type is None:
        position_type = (
            PositionType.SHORT
            if quantity_value < 0
            else PositionType.FLAT
            if quantity_value == 0
            else PositionType.LONG
        )
    return PositionObservation(
        symbol=Symbol(symbol),
        quantity=quantity_value,
        available_to_sell=Decimal(available),
        average_cost=None if cost is None else Decimal(cost),
        current_price=Decimal(price),
        price_observed_at=price_at,
        supported=supported,
        position_type=position_type,
    )


def make_observation(
    positions: tuple[PositionObservation, ...] = (),
    *,
    cash: str = "10000",
    buying_power: str | None = None,
    unleveraged_buying_power: str | None = None,
    broker_equity: str | None = None,
    orders: tuple[OrderObservation, ...] = (),
    account_fingerprint: str | None = ACCOUNT_FP,
    observed_account_fingerprint: str | None = None,
    observed_at: datetime = NOW,
    order_scope: OrderCoverage = OrderCoverage.SYNTHETIC_COMPLETE,
    provenance: ObservationProvenance = ObservationProvenance.SYNTHETIC,
    coverage_overrides: dict[str, bool] | None = None,
) -> PortfolioObservation:
    cash_value = Decimal(cash)
    computed_equity = decimal_sum(
        [
            cash_value,
            *(item.market_value for item in positions if item.market_value is not None),
        ]
    )
    coverage_values = {
        "account_bound": account_fingerprint is not None,
        "portfolio_complete": True,
        "positions_complete": True,
        "quotes_complete": all(item.current_price is not None for item in positions),
        "pagination_complete": True,
    }
    if coverage_overrides:
        coverage_values.update(coverage_overrides)
    return PortfolioObservation(
        observed_at=observed_at,
        account_fingerprint=account_fingerprint,
        observed_account_fingerprint=(
            observed_account_fingerprint
            if observed_account_fingerprint is not None
            else account_fingerprint
        ),
        broker_reported_equity=(
            computed_equity if broker_equity is None else Decimal(broker_equity)
        ),
        broker_reported_position_value=decimal_sum(
            [item.market_value for item in positions if item.market_value is not None]
        ),
        cash=cash_value,
        buying_power=Decimal(cash) if buying_power is None else Decimal(buying_power),
        unleveraged_buying_power=(
            Decimal(cash)
            if unleveraged_buying_power is None
            else Decimal(unleveraged_buying_power)
        ),
        positions=positions,
        orders=orders,
        coverage=ObservationCoverage(order_scope=order_scope, **coverage_values),
        provenance=provenance,
    )


def make_research(
    observation: PortfolioObservation,
    *,
    signals: tuple[tuple[str, str | None, str], ...] | None = None,
    opportunity_quotes: tuple[tuple[str, str], ...] = (),
    quote_overrides: tuple[MarketQuote, ...] = (),
    observed_at: datetime = NOW,
) -> MarketResearchInput:
    quotes = [
        MarketQuote(
            symbol=item.symbol,
            price=item.current_price,
            observed_at=item.price_observed_at,
            source_id="portfolio-observation",
        )
        for item in observation.positions
        if item.current_price is not None and item.price_observed_at is not None
    ]
    quotes.extend(
        MarketQuote(
            Symbol(symbol), Decimal(price), observed_at, "synthetic-market-input"
        )
        for symbol, price in opportunity_quotes
    )
    quote_positions = {quote.symbol: index for index, quote in enumerate(quotes)}
    for quote in quote_overrides:
        existing = quote_positions.get(quote.symbol)
        if existing is None:
            quote_positions[quote.symbol] = len(quotes)
            quotes.append(quote)
        else:
            quotes[existing] = quote
    if signals is None:
        symbols = [item.symbol for item in observation.positions]
        symbols.extend(
            Symbol(symbol)
            for symbol, _ in opportunity_quotes
            if Symbol(symbol) not in symbols
        )
        signal_values = tuple(
            MarketSignal(symbol, Decimal("0.01"), "Synthetic neutral signal.")
            for symbol in symbols
        )
    else:
        signal_values = tuple(
            MarketSignal(
                Symbol(symbol), None if score is None else Decimal(score), rationale
            )
            for symbol, score, rationale in signals
        )
    return MarketResearchInput(
        portfolio_snapshot_id=observation.snapshot_id,
        observed_at=observed_at,
        quotes=tuple(quotes),
        signals=signal_values,
        provider_id="SYNTHETIC_TEST_RESEARCH",
        provider_version="v1",
    )


@pytest.fixture
def now():
    return NOW
