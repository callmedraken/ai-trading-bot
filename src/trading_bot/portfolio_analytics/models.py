"""Immutable portfolio performance-analysis records."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from trading_bot.analytics import DrawdownAnalysis, TradeRealization
from trading_bot.domain import Symbol
from trading_bot.domain._validation import normalize_utc, require_decimal


def _finite(value: Decimal, name: str) -> None:
    require_decimal(value, name)
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")


def _count(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")


@dataclass(frozen=True, slots=True)
class PortfolioExposureRecord:
    """One close-valued portfolio exposure observation."""

    timestamp: datetime
    positions_market_value: Decimal
    equity: Decimal
    gross_exposure_ratio: Decimal
    in_market: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "timestamp", normalize_utc(self.timestamp, "timestamp")
        )
        for name in ("positions_market_value", "equity", "gross_exposure_ratio"):
            _finite(getattr(self, name), name)
        if self.positions_market_value < 0 or self.equity < 0:
            raise ValueError("market value and equity must be nonnegative")
        if self.gross_exposure_ratio < 0:
            raise ValueError("gross_exposure_ratio must be nonnegative")
        expected = (
            Decimal("0")
            if self.equity == 0
            else self.positions_market_value / self.equity
        )
        if self.gross_exposure_ratio != expected:
            raise ValueError("gross_exposure_ratio does not match market value/equity")
        if not isinstance(self.in_market, bool):
            raise TypeError("in_market must be bool")
        if self.in_market is not (self.positions_market_value > 0):
            raise ValueError("in_market must reflect positive positions market value")


@dataclass(frozen=True, slots=True)
class SymbolPerformanceSummary:
    """Exact fill, realization, and final-valuation metrics for one symbol."""

    symbol: Symbol
    buy_fill_count: int
    sell_fill_count: int
    buy_notional: Decimal
    sell_notional: Decimal
    total_executed_notional: Decimal
    realization_count: int
    winning_realization_count: int
    losing_realization_count: int
    breakeven_realization_count: int
    realized_profit_loss: Decimal
    gross_profit: Decimal
    gross_loss: Decimal
    average_winning_realization: Decimal
    average_losing_realization: Decimal
    profit_factor: Decimal | None
    final_quantity: Decimal
    final_average_cost: Decimal
    final_market_value: Decimal
    final_unrealized_profit_loss: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        count_names = (
            "buy_fill_count",
            "sell_fill_count",
            "realization_count",
            "winning_realization_count",
            "losing_realization_count",
            "breakeven_realization_count",
        )
        for name in count_names:
            _count(getattr(self, name), name)
        if self.sell_fill_count != self.realization_count:
            raise ValueError("each sell fill must produce one realization")
        classified = (
            self.winning_realization_count
            + self.losing_realization_count
            + self.breakeven_realization_count
        )
        if classified != self.realization_count:
            raise ValueError("realization counts must classify every realization")
        decimal_names = (
            "buy_notional",
            "sell_notional",
            "total_executed_notional",
            "realized_profit_loss",
            "gross_profit",
            "gross_loss",
            "average_winning_realization",
            "average_losing_realization",
            "final_quantity",
            "final_average_cost",
            "final_market_value",
            "final_unrealized_profit_loss",
        )
        for name in decimal_names:
            _finite(getattr(self, name), name)
        if self.profit_factor is not None:
            _finite(self.profit_factor, "profit_factor")
            if self.profit_factor < 0:
                raise ValueError("profit_factor must be nonnegative")
        for name in (
            "buy_notional",
            "sell_notional",
            "total_executed_notional",
            "gross_profit",
            "final_quantity",
            "final_average_cost",
            "final_market_value",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be nonnegative")
        if self.gross_loss > 0:
            raise ValueError("gross_loss must be nonpositive")
        if self.total_executed_notional != self.buy_notional + self.sell_notional:
            raise ValueError(
                "total executed notional must equal buy plus sell notional"
            )
        if self.final_quantity == 0 and (
            self.final_average_cost != 0
            or self.final_market_value != 0
            or self.final_unrealized_profit_loss != 0
        ):
            raise ValueError("flat symbols must have zero final position values")
        if self.final_quantity > 0 and self.final_average_cost <= 0:
            raise ValueError("open symbols require a positive final average cost")


@dataclass(frozen=True, slots=True)
class PortfolioPerformanceReport:
    """Complete deterministic metrics for one multi-symbol backtest result."""

    absolute_profit_loss: Decimal
    total_return: Decimal
    drawdowns: DrawdownAnalysis
    trade_realizations: tuple[TradeRealization, ...]
    realization_count: int
    winning_realization_count: int
    losing_realization_count: int
    breakeven_realization_count: int
    win_rate: Decimal
    gross_profit: Decimal
    gross_loss: Decimal
    average_winning_realization: Decimal
    average_losing_realization: Decimal
    profit_factor: Decimal | None
    executed_notional: Decimal
    turnover: Decimal
    exposure_history: tuple[PortfolioExposureRecord, ...]
    average_gross_exposure: Decimal
    maximum_gross_exposure: Decimal
    time_in_market_percentage: Decimal
    symbol_summaries: tuple[SymbolPerformanceSummary, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.drawdowns, DrawdownAnalysis):
            raise TypeError("drawdowns must be a DrawdownAnalysis")
        realizations = tuple(self.trade_realizations)
        exposures = tuple(self.exposure_history)
        summaries = tuple(self.symbol_summaries)
        if not all(isinstance(item, TradeRealization) for item in realizations):
            raise TypeError("trade_realizations must contain TradeRealization values")
        if not exposures or not all(
            isinstance(item, PortfolioExposureRecord) for item in exposures
        ):
            raise TypeError("exposure_history must contain exposure records")
        if not summaries or not all(
            isinstance(item, SymbolPerformanceSummary) for item in summaries
        ):
            raise TypeError("symbol_summaries must contain symbol summaries")
        object.__setattr__(self, "trade_realizations", realizations)
        object.__setattr__(self, "exposure_history", exposures)
        object.__setattr__(self, "symbol_summaries", summaries)
        for name in (
            "realization_count",
            "winning_realization_count",
            "losing_realization_count",
            "breakeven_realization_count",
        ):
            _count(getattr(self, name), name)
        classified = (
            self.winning_realization_count
            + self.losing_realization_count
            + self.breakeven_realization_count
        )
        if self.realization_count != len(realizations) or classified != len(
            realizations
        ):
            raise ValueError("realization counts must classify every realization")
        for name in (
            "absolute_profit_loss",
            "total_return",
            "win_rate",
            "gross_profit",
            "gross_loss",
            "average_winning_realization",
            "average_losing_realization",
            "executed_notional",
            "turnover",
            "average_gross_exposure",
            "maximum_gross_exposure",
            "time_in_market_percentage",
        ):
            _finite(getattr(self, name), name)
        if self.profit_factor is not None:
            _finite(self.profit_factor, "profit_factor")
            if self.profit_factor < 0:
                raise ValueError("profit_factor must be nonnegative")
        if self.gross_profit < 0 or self.gross_loss > 0:
            raise ValueError("gross profit/loss signs are inconsistent")
        for name in (
            "win_rate",
            "executed_notional",
            "turnover",
            "average_gross_exposure",
            "maximum_gross_exposure",
            "time_in_market_percentage",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be nonnegative")
        if self.win_rate > 1 or self.time_in_market_percentage > 1:
            raise ValueError("rate values must be no greater than one")
