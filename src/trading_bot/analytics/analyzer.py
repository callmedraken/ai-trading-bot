"""Read-only deterministic performance analysis of completed backtests."""

from datetime import datetime
from decimal import Decimal

from trading_bot.analytics.exceptions import (
    AnalyticsInputError,
    InconsistentBacktestAuditError,
)
from trading_bot.analytics.models import (
    DrawdownAnalysis,
    DrawdownRecord,
    PerformanceReport,
    TradeRealization,
)
from trading_bot.backtesting import BacktestResult
from trading_bot.domain import OrderSide
from trading_bot.ledger import AccountSnapshot


class PerformanceAnalyzer:
    """Derive immutable metrics without changing backtest behavior or state."""

    def analyze(self, result: BacktestResult) -> PerformanceReport:
        if not isinstance(result, BacktestResult):
            raise AnalyticsInputError("result must be a BacktestResult")
        self._validate_snapshots(result)
        realizations, executed_notional = self._reconstruct_trades(result)
        snapshots = result.account_snapshots
        final = snapshots[-1]
        absolute_profit_loss = final.equity - result.config.starting_cash
        total_return = absolute_profit_loss / result.config.starting_cash
        drawdowns = self._drawdowns(result)

        winners = tuple(item for item in realizations if item.net_profit_loss > 0)
        losers = tuple(item for item in realizations if item.net_profit_loss < 0)
        breakeven = len(realizations) - len(winners) - len(losers)
        gross_profit = sum(
            (item.net_profit_loss for item in winners), start=Decimal("0")
        )
        gross_loss = sum((item.net_profit_loss for item in losers), start=Decimal("0"))
        count = len(realizations)
        win_rate = Decimal(len(winners)) / Decimal(count) if count else Decimal("0")
        average_winner = (
            gross_profit / Decimal(len(winners)) if winners else Decimal("0")
        )
        average_loser = gross_loss / Decimal(len(losers)) if losers else Decimal("0")
        profit_factor = gross_profit / abs(gross_loss) if gross_loss != 0 else None

        average_equity = sum(
            (item.equity for item in snapshots), start=Decimal("0")
        ) / Decimal(len(snapshots))
        if average_equity == 0:
            if executed_notional != 0:
                raise InconsistentBacktestAuditError(
                    "executed notional cannot have zero average equity"
                )
            turnover = Decimal("0")
        else:
            turnover = executed_notional / average_equity

        exposures = tuple(self._exposure_ratio(item) for item in snapshots)
        average_exposure = sum(exposures, start=Decimal("0")) / Decimal(len(exposures))
        time_in_market = Decimal(
            sum(item.positions_market_value > 0 for item in snapshots)
        ) / Decimal(len(snapshots))
        return PerformanceReport(
            total_return=total_return,
            absolute_profit_loss=absolute_profit_loss,
            drawdowns=drawdowns,
            trade_realizations=realizations,
            closed_trade_count=count,
            winning_trade_count=len(winners),
            losing_trade_count=len(losers),
            breakeven_trade_count=breakeven,
            win_rate=win_rate,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            average_winning_trade=average_winner,
            average_losing_trade=average_loser,
            profit_factor=profit_factor,
            turnover=turnover,
            average_gross_exposure=average_exposure,
            maximum_gross_exposure=max(exposures),
            time_in_market_percentage=time_in_market,
        )

    @staticmethod
    def _validate_snapshots(result: BacktestResult) -> None:
        snapshots = result.account_snapshots
        if not snapshots:
            raise InconsistentBacktestAuditError("at least one snapshot is required")
        if len(snapshots) != len(result.bars) or len(result.steps) != len(result.bars):
            raise InconsistentBacktestAuditError(
                "bars, steps, and snapshots must have equal counts"
            )
        previous: datetime | None = None
        for snapshot in snapshots:
            if previous is not None and snapshot.timestamp < previous:
                raise InconsistentBacktestAuditError(
                    "snapshot timestamps must be nondecreasing"
                )
            previous = snapshot.timestamp
            for field_name in ("equity", "positions_market_value"):
                value = getattr(snapshot, field_name)
                if not value.is_finite() or value < 0:
                    raise InconsistentBacktestAuditError(
                        f"snapshot {field_name} must be finite and nonnegative"
                    )
        if snapshots[-1].equity != result.final_equity:
            raise InconsistentBacktestAuditError(
                "final snapshot equity must equal result final_equity"
            )

    @staticmethod
    def _reconstruct_trades(
        result: BacktestResult,
    ) -> tuple[tuple[TradeRealization, ...], Decimal]:
        symbol = result.config.data_request.symbol
        quantity = Decimal("0")
        total_basis = Decimal("0")
        entry_started_at = None
        previous_fill_at = None
        fill_ids = set()
        realized = Decimal("0")
        executed_notional = Decimal("0")
        records = []
        for fill in result.fills:
            if fill.fill_id in fill_ids:
                raise InconsistentBacktestAuditError("duplicate fill ID")
            fill_ids.add(fill.fill_id)
            if fill.symbol != symbol:
                raise InconsistentBacktestAuditError(
                    "fill symbol does not match backtest symbol"
                )
            if previous_fill_at is not None and fill.filled_at < previous_fill_at:
                raise InconsistentBacktestAuditError(
                    "fill timestamps must be nondecreasing"
                )
            if not result.start_timestamp <= fill.filled_at <= result.end_timestamp:
                raise InconsistentBacktestAuditError(
                    "fill timestamp is outside the backtest interval"
                )
            previous_fill_at = fill.filled_at
            executed_notional += fill.gross_amount
            if fill.side is OrderSide.BUY:
                if quantity == 0:
                    entry_started_at = fill.filled_at
                quantity += fill.quantity
                total_basis += fill.gross_amount + fill.commission
                continue
            if fill.quantity > quantity or quantity == 0:
                raise InconsistentBacktestAuditError(
                    "sell fill exceeds reconstructed position"
                )
            average_cost = total_basis / quantity
            removed_basis = average_cost * fill.quantity
            proceeds = fill.gross_amount - fill.commission
            profit_loss = proceeds - removed_basis
            assert entry_started_at is not None
            records.append(
                TradeRealization(
                    symbol=fill.symbol,
                    quantity=fill.quantity,
                    average_entry_cost=average_cost,
                    entry_cost_basis=removed_basis,
                    exit_price=fill.price,
                    gross_proceeds=fill.gross_amount,
                    exit_commission=fill.commission,
                    net_profit_loss=profit_loss,
                    entry_started_at=entry_started_at,
                    closed_at=fill.filled_at,
                    exit_fill_id=fill.fill_id,
                )
            )
            realized += profit_loss
            quantity -= fill.quantity
            total_basis -= removed_basis
            if quantity == 0:
                total_basis = Decimal("0")
                entry_started_at = None

        final_position = result.final_positions.get(symbol)
        if final_position is None:
            consistent_position = quantity == 0 and total_basis == 0
        else:
            consistent_position = (
                final_position.quantity == quantity
                and final_position.average_cost == total_basis / quantity
            )
        if not consistent_position:
            raise InconsistentBacktestAuditError(
                "reconstructed position does not match final positions"
            )
        if realized != result.account_snapshots[-1].realized_profit_loss:
            raise InconsistentBacktestAuditError(
                "reconstructed realized P&L does not match final snapshot"
            )
        return tuple(records), executed_notional

    @staticmethod
    def _exposure_ratio(snapshot: AccountSnapshot) -> Decimal:
        equity = snapshot.equity
        exposure = snapshot.positions_market_value
        if equity == 0:
            if exposure > 0:
                raise InconsistentBacktestAuditError(
                    "positive exposure cannot have zero equity"
                )
            return Decimal("0")
        return exposure / equity

    @staticmethod
    def _drawdowns(result: BacktestResult) -> DrawdownAnalysis:
        first = result.account_snapshots[0]
        peak_equity = first.equity
        peak_at = first.timestamp
        zero = DrawdownRecord(
            peak_at, peak_at, peak_equity, peak_equity, Decimal("0"), Decimal("0")
        )
        maximum_amount = zero
        maximum_percentage = zero
        for snapshot in result.account_snapshots:
            if snapshot.equity > peak_equity:
                peak_equity = snapshot.equity
                peak_at = snapshot.timestamp
            amount = peak_equity - snapshot.equity
            percentage = amount / peak_equity if peak_equity else Decimal("0")
            record = DrawdownRecord(
                peak_at,
                snapshot.timestamp,
                peak_equity,
                snapshot.equity,
                amount,
                percentage,
            )
            if amount > maximum_amount.amount:
                maximum_amount = record
            if percentage > maximum_percentage.percentage:
                maximum_percentage = record
        return DrawdownAnalysis(maximum_amount, maximum_percentage)
