"""Sparse-observation Architecture 148 backtest replay.

The exchange schedule supplies event times, while only received provider bars
may value or execute a position. Missing ETF observations never become prices.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, localcontext
from zoneinfo import ZoneInfo

from trading_bot.domain import Bar, OrderSide
from trading_bot.experiments.arch148_churn_policy import ChurnPolicy
from trading_bot.experiments.arch148_intraday import (
    _DECIMAL_CONTEXT,
    SQQQ_SYMBOL,
    TQQQ_SYMBOL,
    ZERO_COST,
    Arch148IntradayError,
    BacktestCostModel,
    BacktestResult,
    BacktestTrade,
    HistoricalIntradaySessionAuthority,
    SparseIntradayDataset,
    _execution_price,
    _OpenBacktestPosition,
    _return,
    _settle_backtest_exit,
    expected_open_slots,
)
from trading_bot.live_runtime.models import (
    CompletedBar,
    MarketQuality,
    MarketRegime,
    MarketSnapshot,
    SignalAnalysis,
    TargetPosition,
)
from trading_bot.live_runtime.strategy import (
    HardStopPolicy,
    SessionDecision,
    _CompletedBarSignalStream,
    analyze_market,
    session_decision,
)

_BAR_WIDTH = timedelta(minutes=5)
_NEW_YORK = ZoneInfo("America/New_York")


@dataclass(frozen=True, slots=True)
class _PendingExit:
    reason: str
    reversal_source: MarketRegime | None = None


def _completed_bar(bar: Bar) -> CompletedBar:
    return CompletedBar(
        bar.timestamp,
        bar.open,
        bar.high,
        bar.low,
        bar.close,
        bar.volume,
    )


def _stop_exit_price(position: _OpenBacktestPosition, bar: Bar) -> Decimal | None:
    if bar.open <= position.stop_price:
        return bar.open
    if bar.low <= position.stop_price:
        return position.stop_price
    return None


def _settle(
    position: _OpenBacktestPosition,
    at: datetime,
    raw_price: Decimal,
    reason: str,
    cost_model: BacktestCostModel,
) -> tuple[Decimal, BacktestTrade, Decimal]:
    with localcontext(_DECIMAL_CONTEXT):
        return _settle_backtest_exit(position, at, raw_price, reason, cost_model)


def _add(left: Decimal, right: Decimal) -> Decimal:
    with localcontext(_DECIMAL_CONTEXT):
        return left + right


def run_sparse_backtest(
    dataset: SparseIntradayDataset,
    *,
    cost_model: BacktestCostModel = ZERO_COST,
    initial_capital: Decimal = Decimal("10000"),
    analyzer: Callable[..., SignalAnalysis] = analyze_market,
    session_policy: Callable[[datetime], SessionDecision] | None = None,
    churn_policy: ChurnPolicy = ChurnPolicy.CONTROL,
    on_equity_mark: Callable[[datetime, Decimal], None] | None = None,
    on_trade_close: (
        Callable[[BacktestTrade, Decimal, MarketRegime | None], None] | None
    ) = None,
) -> BacktestResult:
    """Replay a sparse dataset without fabricating execution or valuation bars.

    A signal uses only QQQ bars completed by the event time. Entry is permitted
    only on a real target ETF bar at that immediate event time; a missing entry
    bar skips the signal. Missing held-ETF bars leave exits pending until the
    first later real bar, where the hard stop has priority. The final published
    session slot must flatten any open position or the simulation fails. The
    equity curve emits no mark while a position lacks a real ETF close; it does
    not carry forward a stale valuation. ``churn_policy`` adds a research-only
    exit/entry gate; CONTROL preserves the existing strategy behavior. Optional
    observers receive only emitted equity marks and settled trade facts, without
    changing the returned result.
    """

    if type(dataset) is not SparseIntradayDataset:
        raise Arch148IntradayError("exact sparse dataset is required")
    if type(cost_model) is not BacktestCostModel:
        raise Arch148IntradayError("exact cost model is required")
    if (
        type(initial_capital) is not Decimal
        or not initial_capital.is_finite()
        or initial_capital <= 0
    ):
        raise Arch148IntradayError("initial capital must be finite and positive")
    if not callable(analyzer):
        raise Arch148IntradayError("analyzer must be callable")
    if session_policy is not None and not callable(session_policy):
        raise Arch148IntradayError("session_policy must be callable")
    if type(churn_policy) is not ChurnPolicy:
        raise Arch148IntradayError("exact churn policy is required")
    if on_equity_mark is not None and not callable(on_equity_mark):
        raise Arch148IntradayError("equity observer must be callable")
    if on_trade_close is not None and not callable(on_trade_close):
        raise Arch148IntradayError("trade observer must be callable")

    authority = HistoricalIntradaySessionAuthority()
    session_policy = session_policy or (
        lambda as_of: session_decision(as_of, authority=authority)
    )
    bars_by_symbol = dataset.bars_by_symbol
    qqq_bars = bars_by_symbol["QQQ"]
    bar_pointers = dict.fromkeys(dataset.symbols, 0)
    qqq_pointer = 0
    completed_history: list[CompletedBar] = []
    has_completed_qqq = False
    signal_stream = (
        _CompletedBarSignalStream(authority) if analyzer is analyze_market else None
    )
    cash = initial_capital
    position: _OpenBacktestPosition | None = None
    pending_exit: _PendingExit | None = None
    trades: list[BacktestTrade] = []
    equity_curve: list[Decimal] = []
    turnover = Decimal("0")
    stop_hits = 0
    reversal_exits = 0
    forced_flat_count = 0
    hard_stop = HardStopPolicy()
    active_session_date: date | None = None
    cooldown_until: datetime | None = None

    def append_equity_mark(at: datetime, value: Decimal) -> None:
        equity_curve.append(value)
        if on_equity_mark is not None:
            on_equity_mark(at, value)

    def observe_closed_trade(
        trade: BacktestTrade,
        added_turnover: Decimal,
        reversal_source: MarketRegime | None,
    ) -> None:
        if on_trade_close is not None:
            on_trade_close(trade, added_turnover, reversal_source)

    for as_of in expected_open_slots(dataset.start, dataset.end_exclusive, authority):
        session_date = as_of.astimezone(_NEW_YORK).date()
        if session_date != active_session_date:
            active_session_date = session_date
            cooldown_until = None
        elif cooldown_until is not None and as_of >= cooldown_until:
            cooldown_until = None

        while (
            qqq_pointer < len(qqq_bars)
            and qqq_bars[qqq_pointer].timestamp + _BAR_WIDTH <= as_of
        ):
            completed = _completed_bar(qqq_bars[qqq_pointer])
            if signal_stream is not None:
                signal_stream.append(completed)
            else:
                completed_history.append(completed)
            has_completed_qqq = True
            qqq_pointer += 1

        current_bars: dict[str, Bar] = {}
        for symbol, bars in bars_by_symbol.items():
            pointer = bar_pointers[symbol]
            while pointer < len(bars) and bars[pointer].timestamp < as_of:
                pointer += 1
            if pointer < len(bars) and bars[pointer].timestamp == as_of:
                current_bars[symbol] = bars[pointer]
            bar_pointers[symbol] = pointer

        signal: SignalAnalysis | None = None
        if has_completed_qqq:
            if signal_stream is not None:
                signal = signal_stream.analyze(as_of)
            else:
                signal = analyzer(
                    MarketSnapshot(as_of, tuple(completed_history), (), {}),
                    authority=authority,
                )
        decision = session_policy(as_of)
        acted = False
        valuation_bar: Bar | None = None
        current_bar = (
            current_bars.get(position.symbol) if position is not None else None
        )

        if position is not None and current_bar is not None:
            valuation_bar = current_bar
            stop_price = _stop_exit_price(position, current_bar)
            if stop_price is not None:
                stop_hits += 1
                proceeds, trade, added_turnover = _settle(
                    position, as_of, stop_price, "STOP", cost_model
                )
                cash = _add(cash, proceeds)
                trades.append(trade)
                turnover = _add(turnover, added_turnover)
                observe_closed_trade(trade, added_turnover, None)
                position = None
                pending_exit = None
                acted = True
                valuation_bar = None

        if (
            position is not None
            and pending_exit is not None
            and current_bar is not None
        ):
            proceeds, trade, added_turnover = _settle(
                position,
                as_of,
                current_bar.open,
                pending_exit.reason,
                cost_model,
            )
            cash = _add(cash, proceeds)
            trades.append(trade)
            turnover = _add(turnover, added_turnover)
            reversal_exits += int(pending_exit.reversal_source is not None)
            forced_flat_count += int(pending_exit.reason == "FORCED_FLAT")
            observe_closed_trade(trade, added_turnover, pending_exit.reversal_source)
            if trade.exit_reason == "REGIME_EXIT" and churn_policy.cooldown_duration:
                cooldown_until = trade.exit_at + churn_policy.cooldown_duration
            position = None
            pending_exit = None
            acted = True
            valuation_bar = None

        if position is not None and pending_exit is None:
            exit_reason: str | None = None
            reversal_source: MarketRegime | None = None
            if decision.force_flat:
                exit_reason = "FORCED_FLAT"
            elif signal is None or signal.quality is not MarketQuality.READY:
                exit_reason = "SAFETY"
            elif churn_policy.should_exit_regime(
                signal, TargetPosition(position.symbol)
            ):
                exit_reason = "REGIME_EXIT"
                reversal_source = churn_policy.reversal_source(signal)
            if exit_reason is not None:
                pending_exit = _PendingExit(exit_reason, reversal_source)
                if current_bar is not None:
                    proceeds, trade, added_turnover = _settle(
                        position,
                        as_of,
                        current_bar.open,
                        exit_reason,
                        cost_model,
                    )
                    cash = _add(cash, proceeds)
                    trades.append(trade)
                    turnover = _add(turnover, added_turnover)
                    reversal_exits += int(reversal_source is not None)
                    forced_flat_count += int(exit_reason == "FORCED_FLAT")
                    observe_closed_trade(trade, added_turnover, reversal_source)
                    if (
                        trade.exit_reason == "REGIME_EXIT"
                        and churn_policy.cooldown_duration
                    ):
                        cooldown_until = trade.exit_at + churn_policy.cooldown_duration
                    position = None
                    pending_exit = None
                    acted = True
                    valuation_bar = None

        if (
            position is None
            and pending_exit is None
            and not acted
            and signal is not None
            and signal.quality is MarketQuality.READY
            and decision.can_enter
            and not decision.force_flat
            and signal.entry_confirmation
            in (MarketRegime.BULLISH, MarketRegime.BEARISH)
            and cooldown_until is None
        ):
            target = (
                TQQQ_SYMBOL
                if signal.entry_confirmation is MarketRegime.BULLISH
                else SQQQ_SYMBOL
            )
            target_bar = current_bars.get(target)
            if target_bar is not None:
                raw_entry = target_bar.open
                fill = _execution_price(raw_entry, OrderSide.BUY, cost_model)
                commission = cost_model.commission_per_side
                with localcontext(_DECIMAL_CONTEXT):
                    quantity = (cash - commission) / fill
                if quantity > 0:
                    cash = Decimal("0")
                    stop_price = hard_stop.threshold(fill)
                    position = _OpenBacktestPosition(
                        target,
                        quantity,
                        as_of,
                        raw_entry,
                        fill,
                        stop_price,
                        commission,
                    )
                    acted = True
                    valuation_bar = target_bar
                    entry_stop = _stop_exit_price(position, target_bar)
                    if entry_stop is not None:
                        stop_hits += 1
                        proceeds, trade, added_turnover = _settle(
                            position,
                            as_of,
                            entry_stop,
                            "STOP",
                            cost_model,
                        )
                        cash = _add(cash, proceeds)
                        trades.append(trade)
                        turnover = _add(turnover, added_turnover)
                        observe_closed_trade(trade, added_turnover, None)
                        position = None
                        valuation_bar = None

        if position is None:
            append_equity_mark(as_of, cash)
        elif valuation_bar is not None:
            with localcontext(_DECIMAL_CONTEXT):
                equity_value = cash + position.quantity * valuation_bar.close
            append_equity_mark(as_of, equity_value)

        session = authority.schedule_for(as_of.astimezone(_NEW_YORK).date())
        if session is not None and as_of == session.closes_at - _BAR_WIDTH:
            if position is not None:
                raise Arch148IntradayError(
                    "forced-flat requirement was unexecutable before session close"
                )

    if position is not None:
        raise Arch148IntradayError("backtest ended with an open position")
    if not qqq_bars:
        raise Arch148IntradayError("sparse dataset contains no QQQ observations")

    with localcontext(_DECIMAL_CONTEXT):
        gross_pnl = sum((item.gross_pnl for item in trades), Decimal("0"))
        cost_pnl = sum((item.cost_adjusted_pnl for item in trades), Decimal("0"))
        qqq_control = _return(qqq_bars[-1].close - qqq_bars[0].open, qqq_bars[0].open)
    peak = initial_capital
    maximum_drawdown = Decimal("0")
    with localcontext(_DECIMAL_CONTEXT):
        for value in equity_curve:
            peak = max(peak, value)
            if peak:
                maximum_drawdown = max(maximum_drawdown, _return(peak - value, peak))
    wins = [item.return_pct for item in trades if item.cost_adjusted_pnl > 0]
    losses = [item.return_pct for item in trades if item.cost_adjusted_pnl < 0]
    average_duration = (
        sum((item.holding_duration for item in trades), timedelta()) / len(trades)
        if trades
        else timedelta()
    )
    with localcontext(_DECIMAL_CONTEXT):
        return BacktestResult(
            dataset.identity,
            cost_model.name,
            _return(gross_pnl, initial_capital),
            _return(cost_pnl, initial_capital),
            qqq_control,
            Decimal("0"),
            maximum_drawdown,
            len(trades),
            stop_hits,
            reversal_exits,
            forced_flat_count,
            turnover,
            average_duration,
            _return(Decimal(len(wins)), Decimal(len(trades)))
            if trades
            else Decimal("0"),
            sum(wins, Decimal("0")) / Decimal(len(wins)) if wins else Decimal("0"),
            sum(losses, Decimal("0")) / Decimal(len(losses))
            if losses
            else Decimal("0"),
            tuple(trades),
            tuple(equity_curve),
        )


__all__ = ["run_sparse_backtest"]
