"""Durable forward-performance tracking for Robinhood review paper trading."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid5

from trading_bot.domain import OrderSide, Symbol
from trading_bot.domain._validation import normalize_utc, require_decimal
from trading_bot.ledger import AccountSnapshot
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.robinhood_mcp import (
    RobinhoodEquityQuotesResponse,
    RobinhoodQuoteData,
)

_VALUATION_NAMESPACE = UUID("50fe4fb6-9680-568f-baae-e9766d896428")


class ReviewPaperPerformanceError(RuntimeError):
    """Base error for durable forward-performance history."""


class ReviewPaperValuationConflictError(ReviewPaperPerformanceError):
    """One valuation timestamp was reused with different material."""


class ReviewPaperQuoteError(ReviewPaperPerformanceError):
    """Quote data cannot safely value the virtual paper portfolio."""


class ReviewPaperPerformanceHistoryEmptyError(ReviewPaperPerformanceError):
    """No durable valuation exists yet."""


@dataclass(frozen=True, slots=True)
class ReviewPaperMark:
    symbol: Symbol
    price: Decimal
    source_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        require_decimal(self.price, "price")
        if not self.price.is_finite() or self.price <= Decimal("0"):
            raise ValueError("price must be a finite positive Decimal")
        object.__setattr__(
            self,
            "source_at",
            normalize_utc(self.source_at, "source_at"),
        )


@dataclass(frozen=True, slots=True)
class ReviewPaperValuation:
    valuation_id: UUID
    timestamp: datetime
    marks: tuple[ReviewPaperMark, ...]
    account: AccountSnapshot

    def __post_init__(self) -> None:
        if not isinstance(self.valuation_id, UUID):
            raise TypeError("valuation_id must be a UUID")
        timestamp = normalize_utc(self.timestamp, "timestamp")
        object.__setattr__(self, "timestamp", timestamp)
        if not isinstance(self.marks, tuple) or not all(
            isinstance(item, ReviewPaperMark) for item in self.marks
        ):
            raise TypeError("marks must contain ReviewPaperMark values")
        symbols = tuple(item.symbol for item in self.marks)
        if len(set(symbols)) != len(symbols):
            raise ValueError("marks must contain each symbol at most once")
        if tuple(sorted(symbols, key=str)) != symbols:
            raise ValueError("marks must use canonical symbol order")
        if not isinstance(self.account, AccountSnapshot):
            raise TypeError("account must be an AccountSnapshot")
        if self.account.timestamp != timestamp:
            raise ValueError("account timestamp must equal valuation timestamp")
        if self.valuation_id != review_paper_valuation_id(timestamp):
            raise ValueError("valuation_id does not match timestamp")


@dataclass(frozen=True, slots=True)
class ReviewPaperRealization:
    symbol: Symbol
    quantity: Decimal
    net_profit_loss: Decimal
    entry_started_at: datetime
    closed_at: datetime
    exit_paper_trade_id: UUID
    exit_proposal_id: UUID
    exit_reason: str
    exit_confidence: Decimal | None

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        require_decimal(self.quantity, "quantity")
        require_decimal(self.net_profit_loss, "net_profit_loss")
        if self.quantity <= Decimal("0"):
            raise ValueError("quantity must be positive")
        started = normalize_utc(self.entry_started_at, "entry_started_at")
        closed = normalize_utc(self.closed_at, "closed_at")
        if started > closed:
            raise ValueError("entry_started_at cannot follow closed_at")
        object.__setattr__(self, "entry_started_at", started)
        object.__setattr__(self, "closed_at", closed)
        if not isinstance(self.exit_paper_trade_id, UUID) or not isinstance(
            self.exit_proposal_id, UUID
        ):
            raise TypeError("exit identities must be UUIDs")
        if not isinstance(self.exit_reason, str) or not self.exit_reason.strip():
            raise ValueError("exit_reason must be nonblank")
        if self.exit_confidence is not None:
            require_decimal(self.exit_confidence, "exit_confidence")


@dataclass(frozen=True, slots=True)
class ReviewPaperPerformanceReport:
    starting_cash: Decimal
    latest: ReviewPaperValuation
    total_return: Decimal
    absolute_profit_loss: Decimal
    maximum_drawdown_amount: Decimal
    maximum_drawdown_percentage: Decimal
    valuation_count: int
    paper_trade_count: int
    closed_trade_count: int
    winning_trade_count: int
    losing_trade_count: int
    breakeven_trade_count: int
    win_rate: Decimal
    realizations: tuple[ReviewPaperRealization, ...]

    def __post_init__(self) -> None:
        for name in (
            "starting_cash",
            "total_return",
            "absolute_profit_loss",
            "maximum_drawdown_amount",
            "maximum_drawdown_percentage",
            "win_rate",
        ):
            require_decimal(getattr(self, name), name)
        if self.starting_cash <= Decimal("0"):
            raise ValueError("starting_cash must be positive")
        if not isinstance(self.latest, ReviewPaperValuation):
            raise TypeError("latest must be ReviewPaperValuation")
        for name in (
            "valuation_count",
            "paper_trade_count",
            "closed_trade_count",
            "winning_trade_count",
            "losing_trade_count",
            "breakeven_trade_count",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if self.valuation_count < 1:
            raise ValueError("valuation_count must be at least one")
        if not Decimal("0") <= self.win_rate <= Decimal("1"):
            raise ValueError("win_rate must be between zero and one")
        if self.maximum_drawdown_amount < Decimal("0"):
            raise ValueError("maximum_drawdown_amount cannot be negative")
        if self.maximum_drawdown_percentage < Decimal("0"):
            raise ValueError("maximum_drawdown_percentage cannot be negative")
        if not isinstance(self.realizations, tuple) or not all(
            isinstance(item, ReviewPaperRealization) for item in self.realizations
        ):
            raise TypeError("realizations must contain ReviewPaperRealization values")


class ReviewPaperPerformanceStore:
    """Persist paper-account valuations beside the durable review-fill ledger."""

    def __init__(self, review_store: ReviewPaperStore) -> None:
        if not isinstance(review_store, ReviewPaperStore):
            raise TypeError("review_store must be ReviewPaperStore")
        self._review_store = review_store
        self._initialize()

    def record_quotes(
        self,
        response: RobinhoodEquityQuotesResponse,
        *,
        observed_at: datetime,
        max_quote_age: timedelta,
    ) -> ReviewPaperValuation:
        if not isinstance(response, RobinhoodEquityQuotesResponse):
            raise TypeError("response must be RobinhoodEquityQuotesResponse")
        timestamp = normalize_utc(observed_at, "observed_at")
        if not isinstance(max_quote_age, timedelta) or max_quote_age <= timedelta(0):
            raise ValueError("max_quote_age must be a positive timedelta")

        ledger = self._review_store.reconstruct_ledger()
        open_symbols = tuple(sorted(ledger.positions, key=str))
        quotes = _quote_map(response)
        if set(quotes) != set(open_symbols):
            raise ReviewPaperQuoteError(
                "quote symbols must exactly match current open paper positions"
            )

        marks = tuple(
            _mark_from_quote(
                quotes[symbol],
                observed_at=timestamp,
                max_quote_age=max_quote_age,
            )
            for symbol in open_symbols
        )
        prices = {mark.symbol: mark.price for mark in marks}
        account = ledger.create_account_snapshot(prices, timestamp)
        candidate = ReviewPaperValuation(
            valuation_id=review_paper_valuation_id(timestamp),
            timestamp=timestamp,
            marks=marks,
            account=account,
        )

        existing = self.get(timestamp)
        if existing is not None:
            if existing == candidate:
                return existing
            raise ReviewPaperValuationConflictError(
                "valuation timestamp conflicts with durable performance history"
            )

        latest = self.latest()
        if latest is not None and timestamp < latest.timestamp:
            raise ReviewPaperValuationConflictError(
                "valuation timestamps must be nondecreasing"
            )

        with sqlite3.connect(self._review_store.path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """
                    INSERT INTO review_valuations (
                        valuation_id, timestamp, marks_json,
                        cash, positions_market_value, equity, buying_power,
                        realized_profit_loss, unrealized_profit_loss
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    _valuation_row(candidate),
                )
                connection.commit()
            except sqlite3.IntegrityError as error:
                connection.rollback()
                observed = self.get(timestamp)
                if observed == candidate:
                    return candidate
                raise ReviewPaperValuationConflictError(
                    "valuation raced with conflicting durable history"
                ) from error
        return candidate

    def get(self, timestamp: datetime) -> ReviewPaperValuation | None:
        normalized = normalize_utc(timestamp, "timestamp")
        with sqlite3.connect(self._review_store.path) as connection:
            row = connection.execute(
                _VALUATION_SELECT + " WHERE timestamp = ?",
                (normalized.isoformat(),),
            ).fetchone()
        return None if row is None else _valuation_from_row(row)

    def history(self) -> tuple[ReviewPaperValuation, ...]:
        with sqlite3.connect(self._review_store.path) as connection:
            rows = connection.execute(
                _VALUATION_SELECT + " ORDER BY timestamp"
            ).fetchall()
        return tuple(_valuation_from_row(row) for row in rows)

    def latest(self) -> ReviewPaperValuation | None:
        with sqlite3.connect(self._review_store.path) as connection:
            row = connection.execute(
                _VALUATION_SELECT + " ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
        return None if row is None else _valuation_from_row(row)

    def report(self) -> ReviewPaperPerformanceReport:
        valuations = self.history()
        if not valuations:
            raise ReviewPaperPerformanceHistoryEmptyError(
                "at least one durable valuation is required"
            )

        realizations = _realizations(self._review_store)
        winners = tuple(item for item in realizations if item.net_profit_loss > 0)
        losers = tuple(item for item in realizations if item.net_profit_loss < 0)
        breakeven = len(realizations) - len(winners) - len(losers)
        count = len(realizations)
        win_rate = Decimal(len(winners)) / Decimal(count) if count else Decimal("0")

        latest = valuations[-1]
        starting_cash = self._review_store.starting_cash
        absolute_profit_loss = latest.account.equity - starting_cash
        total_return = absolute_profit_loss / starting_cash
        drawdown_amount, drawdown_percentage = _maximum_drawdown(
            starting_cash,
            valuations,
        )
        return ReviewPaperPerformanceReport(
            starting_cash=starting_cash,
            latest=latest,
            total_return=total_return,
            absolute_profit_loss=absolute_profit_loss,
            maximum_drawdown_amount=drawdown_amount,
            maximum_drawdown_percentage=drawdown_percentage,
            valuation_count=len(valuations),
            paper_trade_count=len(self._review_store.history()),
            closed_trade_count=count,
            winning_trade_count=len(winners),
            losing_trade_count=len(losers),
            breakeven_trade_count=breakeven,
            win_rate=win_rate,
            realizations=realizations,
        )

    def _initialize(self) -> None:
        with sqlite3.connect(self._review_store.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS review_valuations (
                    valuation_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL UNIQUE,
                    marks_json TEXT NOT NULL,
                    cash TEXT NOT NULL,
                    positions_market_value TEXT NOT NULL,
                    equity TEXT NOT NULL,
                    buying_power TEXT NOT NULL,
                    realized_profit_loss TEXT NOT NULL,
                    unrealized_profit_loss TEXT NOT NULL
                )
                """
            )


def review_paper_valuation_id(timestamp: datetime) -> UUID:
    normalized = normalize_utc(timestamp, "timestamp")
    return uuid5(_VALUATION_NAMESPACE, normalized.isoformat())


def _quote_map(
    response: RobinhoodEquityQuotesResponse,
) -> dict[Symbol, RobinhoodQuoteData]:
    result: dict[Symbol, RobinhoodQuoteData] = {}
    for item in response.results:
        if item is None or item.quote is None:
            continue
        symbol = item.quote.symbol
        if symbol in result:
            raise ReviewPaperQuoteError(f"duplicate quote for {symbol}")
        result[symbol] = item.quote
    return result


def _mark_from_quote(
    quote: RobinhoodQuoteData,
    *,
    observed_at: datetime,
    max_quote_age: timedelta,
) -> ReviewPaperMark:
    if not quote.has_traded:
        raise ReviewPaperQuoteError(f"{quote.symbol} has never traded")
    if quote.state != "active":
        raise ReviewPaperQuoteError(f"{quote.symbol} is not active")
    price, source_at = quote.current_trade_candidate()
    if price <= Decimal("0") or not price.is_finite():
        raise ReviewPaperQuoteError(f"{quote.symbol} mark price is not positive")
    if source_at > observed_at:
        raise ReviewPaperQuoteError(f"{quote.symbol} quote timestamp is in the future")
    if observed_at - source_at > max_quote_age:
        raise ReviewPaperQuoteError(f"{quote.symbol} quote is stale")
    return ReviewPaperMark(quote.symbol, price, source_at)


def _maximum_drawdown(
    starting_cash: Decimal,
    valuations: tuple[ReviewPaperValuation, ...],
) -> tuple[Decimal, Decimal]:
    peak = starting_cash
    maximum_amount = Decimal("0")
    maximum_percentage = Decimal("0")
    for valuation in valuations:
        equity = valuation.account.equity
        if equity > peak:
            peak = equity
        amount = peak - equity
        percentage = amount / peak if peak else Decimal("0")
        maximum_amount = max(maximum_amount, amount)
        maximum_percentage = max(maximum_percentage, percentage)
    return maximum_amount, maximum_percentage


def _realizations(
    store: ReviewPaperStore,
) -> tuple[ReviewPaperRealization, ...]:
    positions: dict[Symbol, tuple[Decimal, Decimal, datetime]] = {}
    result: list[ReviewPaperRealization] = []
    for record in store.history():
        symbol = record.intent.symbol
        if record.intent.side is OrderSide.BUY:
            current = positions.get(symbol)
            quantity = Decimal("0") if current is None else current[0]
            basis = Decimal("0") if current is None else current[1]
            started = record.filled_at if current is None else current[2]
            positions[symbol] = (
                quantity + record.intent.approved_quantity,
                basis
                + record.intent.approved_quantity * record.fill_price
                + record.commission,
                started,
            )
            continue

        current = positions.get(symbol)
        if current is None or record.intent.approved_quantity > current[0]:
            raise ReviewPaperPerformanceError(
                "durable paper history cannot reconstruct sell realization"
            )
        quantity, basis, started = current
        average_cost = basis / quantity
        sold = record.intent.approved_quantity
        removed_basis = average_cost * sold
        proceeds = sold * record.fill_price - record.commission
        profit_loss = proceeds - removed_basis
        result.append(
            ReviewPaperRealization(
                symbol=symbol,
                quantity=sold,
                net_profit_loss=profit_loss,
                entry_started_at=started,
                closed_at=record.filled_at,
                exit_paper_trade_id=record.paper_trade_id,
                exit_proposal_id=record.intent.proposal_id,
                exit_reason=record.intent.proposal_reason,
                exit_confidence=record.intent.proposal_confidence,
            )
        )
        remaining = quantity - sold
        if remaining == Decimal("0"):
            del positions[symbol]
        else:
            positions[symbol] = (
                remaining,
                basis - removed_basis,
                started,
            )
    return tuple(result)


def _valuation_row(value: ReviewPaperValuation) -> tuple[str, ...]:
    marks_json = json.dumps(
        [
            {
                "symbol": str(mark.symbol),
                "price": str(mark.price),
                "source_at": mark.source_at.isoformat(),
            }
            for mark in value.marks
        ],
        separators=(",", ":"),
    )
    account = value.account
    return (
        str(value.valuation_id),
        value.timestamp.isoformat(),
        marks_json,
        str(account.cash),
        str(account.positions_market_value),
        str(account.equity),
        str(account.buying_power),
        str(account.realized_profit_loss),
        str(account.unrealized_profit_loss),
    )


_VALUATION_SELECT = """
SELECT valuation_id, timestamp, marks_json, cash, positions_market_value, equity,
       buying_power, realized_profit_loss, unrealized_profit_loss
FROM review_valuations
"""


def _valuation_from_row(row: tuple[object, ...]) -> ReviewPaperValuation:
    (
        valuation_id,
        timestamp,
        marks_json,
        cash,
        positions_market_value,
        equity,
        buying_power,
        realized_profit_loss,
        unrealized_profit_loss,
    ) = row
    try:
        decoded = json.loads(str(marks_json))
    except json.JSONDecodeError as error:
        raise ReviewPaperPerformanceError(
            "stored valuation marks are invalid"
        ) from error
    if not isinstance(decoded, list):
        raise ReviewPaperPerformanceError("stored valuation marks must be a list")
    marks: list[ReviewPaperMark] = []
    for item in decoded:
        if not isinstance(item, dict):
            raise ReviewPaperPerformanceError("stored mark must be an object")
        try:
            marks.append(
                ReviewPaperMark(
                    symbol=Symbol(str(item["symbol"])),
                    price=Decimal(str(item["price"])),
                    source_at=datetime.fromisoformat(str(item["source_at"])),
                )
            )
        except (KeyError, ValueError, TypeError) as error:
            raise ReviewPaperPerformanceError("stored mark is invalid") from error
    observed_at = datetime.fromisoformat(str(timestamp))
    account = AccountSnapshot(
        timestamp=observed_at,
        cash=Decimal(str(cash)),
        positions_market_value=Decimal(str(positions_market_value)),
        equity=Decimal(str(equity)),
        buying_power=Decimal(str(buying_power)),
        realized_profit_loss=Decimal(str(realized_profit_loss)),
        unrealized_profit_loss=Decimal(str(unrealized_profit_loss)),
    )
    return ReviewPaperValuation(
        valuation_id=UUID(str(valuation_id)),
        timestamp=observed_at,
        marks=tuple(marks),
        account=account,
    )
