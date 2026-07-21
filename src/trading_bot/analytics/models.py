"""Immutable performance-analysis records and aggregate report."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from trading_bot.domain import Symbol
from trading_bot.domain._validation import normalize_utc, require_decimal


def _require_finite(value: Decimal, field_name: str) -> None:
    require_decimal(value, field_name)
    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite")


@dataclass(frozen=True, slots=True)
class TradeRealization:
    """Average-cost profit or loss realized by one sell fill."""

    symbol: Symbol
    quantity: Decimal
    average_entry_cost: Decimal
    entry_cost_basis: Decimal
    exit_price: Decimal
    gross_proceeds: Decimal
    exit_commission: Decimal
    net_profit_loss: Decimal
    entry_started_at: datetime
    closed_at: datetime
    exit_fill_id: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        for field_name in (
            "quantity",
            "average_entry_cost",
            "entry_cost_basis",
            "exit_price",
            "gross_proceeds",
            "exit_commission",
            "net_profit_loss",
        ):
            _require_finite(getattr(self, field_name), field_name)
        for field_name in (
            "quantity",
            "average_entry_cost",
            "entry_cost_basis",
            "exit_price",
            "gross_proceeds",
        ):
            if getattr(self, field_name) <= Decimal("0"):
                raise ValueError(f"{field_name} must be greater than zero")
        if self.exit_commission < Decimal("0"):
            raise ValueError("exit_commission must be nonnegative")
        started = normalize_utc(self.entry_started_at, "entry_started_at")
        closed = normalize_utc(self.closed_at, "closed_at")
        if started > closed:
            raise ValueError("entry_started_at cannot be later than closed_at")
        if not isinstance(self.exit_fill_id, UUID):
            raise TypeError("exit_fill_id must be a UUID")
        object.__setattr__(self, "entry_started_at", started)
        object.__setattr__(self, "closed_at", closed)


@dataclass(frozen=True, slots=True)
class DrawdownRecord:
    """One peak-to-trough equity decline."""

    peak_timestamp: datetime
    trough_timestamp: datetime
    peak_equity: Decimal
    trough_equity: Decimal
    amount: Decimal
    percentage: Decimal

    def __post_init__(self) -> None:
        peak_at = normalize_utc(self.peak_timestamp, "peak_timestamp")
        trough_at = normalize_utc(self.trough_timestamp, "trough_timestamp")
        if peak_at > trough_at:
            raise ValueError("peak_timestamp cannot be later than trough_timestamp")
        for field_name in (
            "peak_equity",
            "trough_equity",
            "amount",
            "percentage",
        ):
            _require_finite(getattr(self, field_name), field_name)
            if getattr(self, field_name) < Decimal("0"):
                raise ValueError(f"{field_name} must be nonnegative")
        if self.amount != self.peak_equity - self.trough_equity:
            raise ValueError("amount must equal peak_equity minus trough_equity")
        expected = (
            Decimal("0")
            if self.peak_equity == Decimal("0")
            else self.amount / self.peak_equity
        )
        if self.percentage != expected:
            raise ValueError("percentage must equal amount divided by peak_equity")
        object.__setattr__(self, "peak_timestamp", peak_at)
        object.__setattr__(self, "trough_timestamp", trough_at)


@dataclass(frozen=True, slots=True)
class DrawdownAnalysis:
    """Separate maxima for dollar and percentage drawdowns."""

    maximum_amount: DrawdownRecord
    maximum_percentage: DrawdownRecord

    def __post_init__(self) -> None:
        if not isinstance(self.maximum_amount, DrawdownRecord):
            raise TypeError("maximum_amount must be a DrawdownRecord")
        if not isinstance(self.maximum_percentage, DrawdownRecord):
            raise TypeError("maximum_percentage must be a DrawdownRecord")


@dataclass(frozen=True, slots=True)
class PerformanceReport:
    """Complete deterministic metrics derived from one backtest result."""

    total_return: Decimal
    absolute_profit_loss: Decimal
    drawdowns: DrawdownAnalysis
    trade_realizations: tuple[TradeRealization, ...]
    closed_trade_count: int
    winning_trade_count: int
    losing_trade_count: int
    breakeven_trade_count: int
    win_rate: Decimal
    gross_profit: Decimal
    gross_loss: Decimal
    average_winning_trade: Decimal
    average_losing_trade: Decimal
    profit_factor: Decimal | None
    turnover: Decimal
    average_gross_exposure: Decimal
    maximum_gross_exposure: Decimal
    time_in_market_percentage: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.drawdowns, DrawdownAnalysis):
            raise TypeError("drawdowns must be a DrawdownAnalysis")
        realizations = tuple(self.trade_realizations)
        if not all(isinstance(item, TradeRealization) for item in realizations):
            raise TypeError("trade_realizations must contain TradeRealization values")
        object.__setattr__(self, "trade_realizations", realizations)
        for field_name in (
            "total_return",
            "absolute_profit_loss",
            "win_rate",
            "gross_profit",
            "gross_loss",
            "average_winning_trade",
            "average_losing_trade",
            "turnover",
            "average_gross_exposure",
            "maximum_gross_exposure",
            "time_in_market_percentage",
        ):
            _require_finite(getattr(self, field_name), field_name)
        if self.profit_factor is not None:
            _require_finite(self.profit_factor, "profit_factor")
            if self.profit_factor < Decimal("0"):
                raise ValueError("profit_factor must be nonnegative")
        for field_name in (
            "closed_trade_count",
            "winning_trade_count",
            "losing_trade_count",
            "breakeven_trade_count",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a nonnegative integer")
        classified = (
            self.winning_trade_count
            + self.losing_trade_count
            + self.breakeven_trade_count
        )
        if self.closed_trade_count != len(realizations) or classified != len(
            realizations
        ):
            raise ValueError("trade counts must classify every realization exactly")
        for field_name in (
            "win_rate",
            "average_gross_exposure",
            "maximum_gross_exposure",
            "time_in_market_percentage",
        ):
            if getattr(self, field_name) < Decimal("0"):
                raise ValueError(f"{field_name} must be nonnegative")
        if self.win_rate > Decimal("1"):
            raise ValueError("win_rate must be no greater than 1")
        if self.time_in_market_percentage > Decimal("1"):
            raise ValueError("time_in_market_percentage must be no greater than 1")
        if self.gross_profit < Decimal("0") or self.gross_loss > Decimal("0"):
            raise ValueError(
                "gross profit must be nonnegative and gross loss nonpositive"
            )

    @property
    def maximum_drawdown_amount(self) -> Decimal:
        return self.drawdowns.maximum_amount.amount

    @property
    def maximum_drawdown_percentage(self) -> Decimal:
        return self.drawdowns.maximum_percentage.percentage
