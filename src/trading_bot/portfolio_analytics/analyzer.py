"""Read-only deterministic analysis of multi-symbol backtest results."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from trading_bot.analytics import DrawdownAnalysis, DrawdownRecord, TradeRealization
from trading_bot.domain import OrderSide, OrderStatus, Symbol
from trading_bot.execution import OrderEventType
from trading_bot.multi_backtesting import MultiSymbolBacktestResult
from trading_bot.portfolio_analytics.exceptions import (
    InconsistentPortfolioBacktestAuditError,
    PortfolioAnalyticsInputError,
)
from trading_bot.portfolio_analytics.models import (
    PortfolioExposureRecord,
    PortfolioPerformanceReport,
    SymbolPerformanceSummary,
)


@dataclass(slots=True)
class _PositionState:
    quantity: Decimal = Decimal("0")
    basis: Decimal = Decimal("0")
    entry_started_at: datetime | None = None


class PortfolioPerformanceAnalyzer:
    """Derive immutable portfolio metrics without changing backtest state."""

    def analyze(self, result: MultiSymbolBacktestResult) -> PortfolioPerformanceReport:
        if not isinstance(result, MultiSymbolBacktestResult):
            raise PortfolioAnalyticsInputError(
                "result must be a MultiSymbolBacktestResult"
            )
        symbols = self._validate_structure(result)
        self._validate_orders_and_fills(result)
        states, realizations, notionals = self._reconstruct(result, symbols)
        self._validate_final_accounting(result, symbols, states, realizations)

        winners = tuple(item for item in realizations if item.net_profit_loss > 0)
        losers = tuple(item for item in realizations if item.net_profit_loss < 0)
        breakeven_count = len(realizations) - len(winners) - len(losers)
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
        profit_factor = gross_profit / abs(gross_loss) if gross_loss else None

        executed_notional = sum(notionals.values(), start=Decimal("0"))
        average_equity = sum(
            (item.equity for item in result.account_snapshots), start=Decimal("0")
        ) / Decimal(len(result.account_snapshots))
        if average_equity > 0:
            turnover = executed_notional / average_equity
        elif average_equity == 0 and executed_notional == 0:
            turnover = Decimal("0")
        else:
            raise InconsistentPortfolioBacktestAuditError(
                "average equity is incompatible with executed notional"
            )

        exposures = self._exposures(result)
        average_exposure = sum(
            (item.gross_exposure_ratio for item in exposures), start=Decimal("0")
        ) / Decimal(len(exposures))
        time_in_market = Decimal(sum(item.in_market for item in exposures)) / Decimal(
            len(exposures)
        )
        summaries = self._symbol_summaries(
            result, symbols, states, realizations, notionals
        )
        final = result.account_snapshots[-1]
        absolute_profit_loss = final.equity - result.config.starting_cash
        return PortfolioPerformanceReport(
            absolute_profit_loss=absolute_profit_loss,
            total_return=absolute_profit_loss / result.config.starting_cash,
            drawdowns=self._drawdowns(result),
            trade_realizations=realizations,
            realization_count=count,
            winning_realization_count=len(winners),
            losing_realization_count=len(losers),
            breakeven_realization_count=breakeven_count,
            win_rate=win_rate,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            average_winning_realization=average_winner,
            average_losing_realization=average_loser,
            profit_factor=profit_factor,
            executed_notional=executed_notional,
            turnover=turnover,
            exposure_history=exposures,
            average_gross_exposure=average_exposure,
            maximum_gross_exposure=max(item.gross_exposure_ratio for item in exposures),
            time_in_market_percentage=time_in_market,
            symbol_summaries=summaries,
        )

    @classmethod
    def _validate_structure(
        cls, result: MultiSymbolBacktestResult
    ) -> tuple[Symbol, ...]:
        symbols = tuple(result.config.data_request.symbols)
        if not symbols or len(set(symbols)) != len(symbols):
            raise InconsistentPortfolioBacktestAuditError(
                "configured universe must be nonempty and duplicate-free"
            )
        frames = result.frames
        steps = result.steps
        snapshots = result.account_snapshots
        if not frames or len(frames) != len(steps) or len(frames) != len(snapshots):
            raise InconsistentPortfolioBacktestAuditError(
                "frames, steps, and snapshots must have equal nonzero counts"
            )
        previous_frame_at = None
        for index, (frame, step, snapshot) in enumerate(
            zip(frames, steps, snapshots, strict=True)
        ):
            if frame.symbols != symbols or tuple(frame.bars_by_symbol) != symbols:
                raise InconsistentPortfolioBacktestAuditError(
                    "every frame must contain the configured universe in order"
                )
            if previous_frame_at is not None and frame.timestamp <= previous_frame_at:
                raise InconsistentPortfolioBacktestAuditError(
                    "frame timestamps must be strictly increasing"
                )
            previous_frame_at = frame.timestamp
            if step.step_index != index:
                raise InconsistentPortfolioBacktestAuditError(
                    "step indexes must be zero-based and contiguous"
                )
            if step.frame != frame or step.account_snapshot != snapshot:
                raise InconsistentPortfolioBacktestAuditError(
                    "step, frame, and snapshot tuples are not aligned"
                )
            if snapshot.timestamp != frame.timestamp:
                raise InconsistentPortfolioBacktestAuditError(
                    "snapshot timestamp must equal its frame timestamp"
                )
            if any(fill.filled_at != frame.timestamp for fill in step.opening_fills):
                raise InconsistentPortfolioBacktestAuditError(
                    "opening fill timestamp must equal its frame timestamp"
                )
            cls._validate_snapshot(snapshot)
        if result.start_timestamp != frames[0].timestamp:
            raise InconsistentPortfolioBacktestAuditError(
                "start timestamp must equal the first frame timestamp"
            )
        if result.end_timestamp != frames[-1].timestamp:
            raise InconsistentPortfolioBacktestAuditError(
                "end timestamp must equal the final frame timestamp"
            )
        step_fills = tuple(fill for step in steps for fill in step.opening_fills)
        if step_fills != result.fills:
            raise InconsistentPortfolioBacktestAuditError(
                "step opening fills must equal result fills in application order"
            )
        return symbols

    @staticmethod
    def _validate_snapshot(snapshot) -> None:  # type: ignore[no-untyped-def]
        for name in (
            "cash",
            "positions_market_value",
            "equity",
            "buying_power",
            "realized_profit_loss",
            "unrealized_profit_loss",
        ):
            value = getattr(snapshot, name)
            if not isinstance(value, Decimal) or not value.is_finite():
                raise InconsistentPortfolioBacktestAuditError(
                    f"snapshot {name} must be a finite Decimal"
                )
        if (
            snapshot.cash < 0
            or snapshot.positions_market_value < 0
            or snapshot.equity < 0
        ):
            raise InconsistentPortfolioBacktestAuditError(
                "snapshot cash, market value, and equity must be nonnegative"
            )
        if snapshot.equity != snapshot.cash + snapshot.positions_market_value:
            raise InconsistentPortfolioBacktestAuditError(
                "snapshot equity must equal cash plus positions market value"
            )

    @staticmethod
    def _validate_orders_and_fills(result: MultiSymbolBacktestResult) -> None:
        orders = {}
        for order in result.final_orders:
            order_id = order.request.order_id
            if order_id in orders:
                raise InconsistentPortfolioBacktestAuditError(
                    "duplicate final order ID"
                )
            orders[order_id] = order
        events_by_order = {order_id: [] for order_id in orders}
        for event in result.order_events:
            if event.order_id not in orders:
                raise InconsistentPortfolioBacktestAuditError(
                    "order event references an unknown final order"
                )
            events_by_order[event.order_id].append(event)
        fill_ids = set()
        fills_by_order = {order_id: [] for order_id in orders}
        previous_fill_at = None
        frame_timestamps = {frame.timestamp for frame in result.frames}
        universe = set(result.config.data_request.symbols)
        for fill in result.fills:
            if fill.fill_id in fill_ids:
                raise InconsistentPortfolioBacktestAuditError("duplicate fill ID")
            fill_ids.add(fill.fill_id)
            if previous_fill_at is not None and fill.filled_at < previous_fill_at:
                raise InconsistentPortfolioBacktestAuditError(
                    "fill timestamps must be nondecreasing"
                )
            previous_fill_at = fill.filled_at
            if fill.filled_at not in frame_timestamps:
                raise InconsistentPortfolioBacktestAuditError(
                    "fill timestamp is not represented by a market frame"
                )
            if fill.symbol not in universe:
                raise InconsistentPortfolioBacktestAuditError(
                    "fill symbol is outside the configured universe"
                )
            for name in ("quantity", "price", "commission"):
                value = getattr(fill, name)
                if not isinstance(value, Decimal) or not value.is_finite():
                    raise InconsistentPortfolioBacktestAuditError(
                        f"fill {name} must be a finite Decimal"
                    )
            if fill.quantity <= 0 or fill.price <= 0 or fill.commission < 0:
                raise InconsistentPortfolioBacktestAuditError(
                    "fill quantity/price must be positive and commission nonnegative"
                )
            order = orders.get(fill.order_id)
            if order is None:
                raise InconsistentPortfolioBacktestAuditError(
                    "fill references an unknown final order"
                )
            if (
                fill.symbol != order.request.symbol
                or fill.side is not order.request.side
            ):
                raise InconsistentPortfolioBacktestAuditError(
                    "fill symbol or side does not match its order"
                )
            if fill.quantity != order.request.quantity:
                raise InconsistentPortfolioBacktestAuditError(
                    "fill quantity must equal full order quantity"
                )
            fills_by_order[fill.order_id].append(fill)
            if len(fills_by_order[fill.order_id]) > 1:
                raise InconsistentPortfolioBacktestAuditError(
                    "full-fill orders cannot have multiple fills"
                )
            submitted = [
                event
                for event in events_by_order[fill.order_id]
                if event.event_type is OrderEventType.SUBMITTED
            ]
            if len(submitted) != 1 or fill.filled_at < submitted[0].occurred_at:
                raise InconsistentPortfolioBacktestAuditError(
                    "fill must occur after exactly one submission event"
                )
            fill_events = [
                event
                for event in events_by_order[fill.order_id]
                if event.event_type is OrderEventType.FILLED
                and event.fill_id == fill.fill_id
                and event.occurred_at == fill.filled_at
            ]
            if len(fill_events) != 1:
                raise InconsistentPortfolioBacktestAuditError(
                    "fill must have one matching filled lifecycle event"
                )
        for order_id, order in orders.items():
            order_fills = fills_by_order[order_id]
            if order.status is OrderStatus.FILLED:
                if len(order_fills) != 1:
                    raise InconsistentPortfolioBacktestAuditError(
                        "filled order must have exactly one fill"
                    )
                fill = order_fills[0]
                if (
                    order.filled_quantity != order.request.quantity
                    or order.average_fill_price != fill.price
                ):
                    raise InconsistentPortfolioBacktestAuditError(
                        "filled order snapshot does not reconcile with its fill"
                    )
            elif order_fills or order.filled_quantity != 0:
                raise InconsistentPortfolioBacktestAuditError(
                    "non-filled order cannot have a fill in the full-fill engine"
                )

    @staticmethod
    def _reconstruct(result, symbols):  # type: ignore[no-untyped-def]
        states = {symbol: _PositionState() for symbol in symbols}
        records = []
        notionals = {symbol: Decimal("0") for symbol in symbols}
        sell_fill_ids = []
        for fill in result.fills:
            state = states[fill.symbol]
            notionals[fill.symbol] += fill.gross_amount
            if fill.side is OrderSide.BUY:
                if state.quantity == 0:
                    state.entry_started_at = fill.filled_at
                state.quantity += fill.quantity
                state.basis += fill.gross_amount + fill.commission
                continue
            sell_fill_ids.append(fill.fill_id)
            if state.quantity == 0 or fill.quantity > state.quantity:
                raise InconsistentPortfolioBacktestAuditError(
                    "sell fill exceeds reconstructed symbol position"
                )
            average_cost = state.basis / state.quantity
            removed_basis = average_cost * fill.quantity
            profit_loss = fill.gross_amount - fill.commission - removed_basis
            if state.entry_started_at is None:
                raise InconsistentPortfolioBacktestAuditError(
                    "open position is missing its entry timestamp"
                )
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
                    entry_started_at=state.entry_started_at,
                    closed_at=fill.filled_at,
                    exit_fill_id=fill.fill_id,
                )
            )
            state.quantity -= fill.quantity
            state.basis -= removed_basis
            if state.quantity == 0:
                state.quantity = Decimal("0")
                state.basis = Decimal("0")
                state.entry_started_at = None
        if [record.exit_fill_id for record in records] != sell_fill_ids:
            raise InconsistentPortfolioBacktestAuditError(
                "realization order must equal global sell-fill order"
            )
        return states, tuple(records), notionals

    @staticmethod
    def _validate_final_accounting(result, symbols, states, realizations):  # type: ignore[no-untyped-def]
        final_positions = result.final_positions
        if any(symbol not in symbols for symbol in final_positions):
            raise InconsistentPortfolioBacktestAuditError(
                "final position is outside the configured universe"
            )
        for symbol in symbols:
            state = states[symbol]
            position = final_positions.get(symbol)
            if state.quantity == 0:
                if position is not None:
                    raise InconsistentPortfolioBacktestAuditError(
                        "flat symbols must be absent from final positions"
                    )
            elif position is None or (
                position.quantity != state.quantity
                or position.average_cost != state.basis / state.quantity
            ):
                raise InconsistentPortfolioBacktestAuditError(
                    "reconstructed position does not match final positions"
                )
        final_frame = result.frames[-1]
        market_value = Decimal("0")
        unrealized = Decimal("0")
        for symbol in symbols:
            bar = final_frame.bars_by_symbol.get(symbol)
            if bar is None:
                raise InconsistentPortfolioBacktestAuditError(
                    "final frame must contain every configured symbol"
                )
            for name in ("open", "high", "low", "close"):
                value = getattr(bar, name)
                if not isinstance(value, Decimal) or not value.is_finite():
                    raise InconsistentPortfolioBacktestAuditError(
                        "final bar prices must be finite Decimals"
                    )
            state = states[symbol]
            value = state.quantity * bar.close
            market_value += value
            unrealized += value - state.basis
        final = result.account_snapshots[-1]
        realized = sum(
            (item.net_profit_loss for item in realizations), start=Decimal("0")
        )
        if realized != final.realized_profit_loss:
            raise InconsistentPortfolioBacktestAuditError(
                "reconstructed realized P&L does not match final snapshot"
            )
        if market_value != final.positions_market_value:
            raise InconsistentPortfolioBacktestAuditError(
                "reconstructed market value does not match final snapshot"
            )
        if unrealized != final.unrealized_profit_loss:
            raise InconsistentPortfolioBacktestAuditError(
                "reconstructed unrealized P&L does not match final snapshot"
            )
        if result.final_equity != final.equity or result.final_cash != final.cash:
            raise InconsistentPortfolioBacktestAuditError(
                "result final values do not match the final snapshot"
            )
        if final.equity != final.cash + final.positions_market_value:
            raise InconsistentPortfolioBacktestAuditError(
                "final equity does not equal cash plus positions market value"
            )
        absolute = final.equity - result.config.starting_cash
        if absolute != final.realized_profit_loss + final.unrealized_profit_loss:
            raise InconsistentPortfolioBacktestAuditError(
                "final profit/loss identity does not reconcile"
            )

    @staticmethod
    def _exposures(result):  # type: ignore[no-untyped-def]
        records = []
        for frame, snapshot in zip(
            result.frames, result.account_snapshots, strict=True
        ):
            if snapshot.equity == 0:
                if snapshot.positions_market_value > 0:
                    raise InconsistentPortfolioBacktestAuditError(
                        "positive exposure cannot have zero equity"
                    )
                ratio = Decimal("0")
            elif snapshot.equity < 0:
                raise InconsistentPortfolioBacktestAuditError(
                    "snapshot equity cannot be negative"
                )
            else:
                ratio = snapshot.positions_market_value / snapshot.equity
            records.append(
                PortfolioExposureRecord(
                    timestamp=snapshot.timestamp,
                    positions_market_value=snapshot.positions_market_value,
                    equity=snapshot.equity,
                    gross_exposure_ratio=ratio,
                    in_market=snapshot.positions_market_value > 0,
                )
            )
            if records[-1].timestamp != frame.timestamp:
                raise InconsistentPortfolioBacktestAuditError(
                    "exposure timestamp must come from aligned audit data"
                )
        return tuple(records)

    @staticmethod
    def _symbol_summaries(result, symbols, states, realizations, notionals):  # type: ignore[no-untyped-def]
        summaries = []
        final_frame = result.frames[-1]
        for symbol in symbols:
            symbol_fills = tuple(fill for fill in result.fills if fill.symbol == symbol)
            symbol_realizations = tuple(
                item for item in realizations if item.symbol == symbol
            )
            winners = tuple(
                item for item in symbol_realizations if item.net_profit_loss > 0
            )
            losers = tuple(
                item for item in symbol_realizations if item.net_profit_loss < 0
            )
            gross_profit = sum(
                (item.net_profit_loss for item in winners), start=Decimal("0")
            )
            gross_loss = sum(
                (item.net_profit_loss for item in losers), start=Decimal("0")
            )
            state = states[symbol]
            market_value = state.quantity * final_frame.bars_by_symbol[symbol].close
            summaries.append(
                SymbolPerformanceSummary(
                    symbol=symbol,
                    buy_fill_count=sum(
                        fill.side is OrderSide.BUY for fill in symbol_fills
                    ),
                    sell_fill_count=sum(
                        fill.side is OrderSide.SELL for fill in symbol_fills
                    ),
                    buy_notional=sum(
                        (
                            fill.gross_amount
                            for fill in symbol_fills
                            if fill.side is OrderSide.BUY
                        ),
                        start=Decimal("0"),
                    ),
                    sell_notional=sum(
                        (
                            fill.gross_amount
                            for fill in symbol_fills
                            if fill.side is OrderSide.SELL
                        ),
                        start=Decimal("0"),
                    ),
                    total_executed_notional=notionals[symbol],
                    realization_count=len(symbol_realizations),
                    winning_realization_count=len(winners),
                    losing_realization_count=len(losers),
                    breakeven_realization_count=(
                        len(symbol_realizations) - len(winners) - len(losers)
                    ),
                    realized_profit_loss=sum(
                        (item.net_profit_loss for item in symbol_realizations),
                        start=Decimal("0"),
                    ),
                    gross_profit=gross_profit,
                    gross_loss=gross_loss,
                    average_winning_realization=(
                        gross_profit / Decimal(len(winners))
                        if winners
                        else Decimal("0")
                    ),
                    average_losing_realization=(
                        gross_loss / Decimal(len(losers)) if losers else Decimal("0")
                    ),
                    profit_factor=(
                        gross_profit / abs(gross_loss) if gross_loss else None
                    ),
                    final_quantity=state.quantity,
                    final_average_cost=(
                        state.basis / state.quantity if state.quantity else Decimal("0")
                    ),
                    final_market_value=market_value,
                    final_unrealized_profit_loss=market_value - state.basis,
                )
            )
        return tuple(summaries)

    @staticmethod
    def _drawdowns(result):  # type: ignore[no-untyped-def]
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
