"""Pure canonical risk prices from an already acquired Robinhood quote response."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import MappingProxyType

from trading_bot.domain import Symbol
from trading_bot.robinhood_mcp.models import (
    RobinhoodEquityQuotesResponse,
    RobinhoodQuoteData,
)


def _normalize_utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{field} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(UTC)


def _require_symbols(symbols: tuple[Symbol, ...]) -> None:
    if type(symbols) is not tuple:
        raise TypeError("required_symbols must be exactly tuple")
    if not symbols:
        raise ValueError("required_symbols must be nonempty")
    if not all(isinstance(symbol, Symbol) for symbol in symbols):
        raise TypeError("required_symbols must contain Symbol values")
    if len(set(symbols)) != len(symbols):
        raise ValueError("required_symbols must be unique")
    if symbols != tuple(sorted(symbols, key=str)):
        raise ValueError("required_symbols must be in canonical symbol order")


@dataclass(frozen=True, slots=True)
class ReviewPaperRiskPriceMark:
    """One exact positive trade price and its explicit source timestamp."""

    symbol: Symbol
    price: Decimal
    source_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        if type(self.price) is not Decimal:
            raise TypeError("price must be exactly Decimal")
        if not self.price.is_finite() or self.price <= Decimal("0"):
            raise ValueError("price must be finite and positive")
        object.__setattr__(
            self, "source_at", _normalize_utc(self.source_at, "source_at")
        )


@dataclass(frozen=True, slots=True)
class ReviewPaperRiskPriceSnapshot:
    """Immutable canonical marks at one explicit observation instant."""

    observed_at: datetime
    marks: tuple[ReviewPaperRiskPriceMark, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "observed_at", _normalize_utc(self.observed_at, "observed_at")
        )
        if type(self.marks) is not tuple:
            raise TypeError("marks must be exactly tuple")
        if not all(type(mark) is ReviewPaperRiskPriceMark for mark in self.marks):
            raise TypeError("marks must contain ReviewPaperRiskPriceMark values")
        _require_symbols(tuple(mark.symbol for mark in self.marks))
        if any(mark.source_at > self.observed_at for mark in self.marks):
            raise ValueError("mark source_at must not be later than observed_at")

    @property
    def prices(self) -> Mapping[Symbol, Decimal]:
        """Derive a read-only exact price mapping in canonical mark order."""
        return MappingProxyType({mark.symbol: mark.price for mark in self.marks})


def build_review_paper_risk_price_snapshot(
    *,
    response: RobinhoodEquityQuotesResponse,
    required_symbols: tuple[Symbol, ...],
    observed_at: datetime,
    max_quote_age: timedelta,
) -> ReviewPaperRiskPriceSnapshot:
    """Validate complete quote coverage and select each current trade once."""
    if type(response) is not RobinhoodEquityQuotesResponse:
        raise TypeError("response must be exactly RobinhoodEquityQuotesResponse")
    _require_symbols(required_symbols)
    observed_at = _normalize_utc(observed_at, "observed_at")
    if type(max_quote_age) is not timedelta:
        raise TypeError("max_quote_age must be exactly timedelta")
    if max_quote_age <= timedelta(0):
        raise ValueError("max_quote_age must be strictly positive")

    quotes: dict[Symbol, RobinhoodQuoteData] = {}
    for result in response.results:
        if result is None or result.quote is None:
            continue
        quote = result.quote
        if quote.symbol in quotes:
            raise ValueError(f"duplicate quote for {quote.symbol}")
        quotes[quote.symbol] = quote
    if set(quotes) != set(required_symbols):
        raise ValueError("quote symbols must exactly match required_symbols")

    marks: list[ReviewPaperRiskPriceMark] = []
    for symbol in required_symbols:
        quote = quotes[symbol]
        if quote.has_traded is not True:
            raise ValueError(f"{symbol} has never traded")
        if quote.state != "active":
            raise ValueError(f"{symbol} is not active")
        price, source_at = quote.current_trade_candidate()
        mark = ReviewPaperRiskPriceMark(symbol, price, source_at)
        if mark.source_at > observed_at:
            raise ValueError(f"{symbol} quote timestamp is in the future")
        if observed_at - mark.source_at > max_quote_age:
            raise ValueError(f"{symbol} quote is stale")
        marks.append(mark)
    return ReviewPaperRiskPriceSnapshot(observed_at, tuple(marks))
