"""Pure, in-memory replay for the frozen Architecture 148 late-capture rule."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal, localcontext
from enum import StrEnum
from zoneinfo import ZoneInfo

from trading_bot.domain import Bar
from trading_bot.experiments.arch148_intraday import (
    CONSERVATIVE_COSTS,
    SQQQ_SYMBOL,
    TQQQ_SYMBOL,
    ZERO_COST,
    BacktestCostModel,
    BacktestResult,
    BacktestTrade,
    HistoricalIntradaySessionAuthority,
    SparseIntradayDataset,
)
from trading_bot.experiments.arch148_sparse_backtest import (
    run_sparse_backtest,
    sparse_backtest_decimal_context,
)
from trading_bot.live_runtime.models import MarketQuality, MarketRegime

OPENING_DRIVE_POLICY_ID = "OPENING_DRIVE_LATE_CAPTURE_V1"
OPENING_DRIVE_REPLAY_SCHEMA = "arch148-intraday-momentum-replay/v1"
OPENING_DRIVE_SIMULATOR_VERSION = "arch148-sparse-scheduled-replay/v1"
_BAR_WIDTH = timedelta(minutes=5)
_OPENING_BAR_COUNT = 6
_OPENING_CAPITAL = Decimal("10000")
_NEW_YORK = ZoneInfo("America/New_York")


class OpeningDriveNoTradeReason(StrEnum):
    MISSING_PREVIOUS_QQQ_CLOSE = "MISSING_PREVIOUS_QQQ_CLOSE"
    INCOMPLETE_FIRST_HALF_HOUR_QQQ = "INCOMPLETE_FIRST_HALF_HOUR_QQQ"
    ZERO_OPENING_DRIVE = "ZERO_OPENING_DRIVE"
    MISSING_SCHEDULED_ENTRY_BAR = "MISSING_SCHEDULED_ENTRY_BAR"
    QQQ_DATA_SAFETY_AT_ENTRY = "QQQ_DATA_SAFETY_AT_ENTRY"


@dataclass(frozen=True, slots=True)
class OpeningDriveSessionCapture:
    session_date: date
    previous_session_date: date | None
    entry_at: datetime
    force_flat_at: datetime
    opening_drive_return: Decimal | None
    target_symbol: str | None
    policy_entry_eligible: bool
    no_trade_reason: OpeningDriveNoTradeReason | None
    early_close: bool
    qqq_late_window_return: Decimal | None
    entry_data_quality: MarketQuality | None = None

    def __post_init__(self) -> None:
        if type(self.session_date) is not date:
            raise TypeError("session_date must be exactly date")
        if (
            self.previous_session_date is not None
            and type(self.previous_session_date) is not date
        ):
            raise TypeError("previous_session_date must be date or None")
        for name in ("entry_at", "force_flat_at"):
            value = getattr(self, name)
            if type(value) is not datetime or value.tzinfo is None:
                raise TypeError(f"{name} must be timezone-aware")
        if self.entry_at >= self.force_flat_at:
            raise ValueError("entry_at must precede force_flat_at")
        for name in ("opening_drive_return", "qqq_late_window_return"):
            value = getattr(self, name)
            if value is not None and (
                type(value) is not Decimal or not value.is_finite()
            ):
                raise TypeError(f"{name} must be a finite Decimal or None")
        if self.target_symbol not in (None, TQQQ_SYMBOL, SQQQ_SYMBOL):
            raise ValueError("target_symbol must be TQQQ, SQQQ, or None")
        if type(self.policy_entry_eligible) is not bool:
            raise TypeError("policy_entry_eligible must be a bool")
        if (
            self.no_trade_reason is not None
            and type(self.no_trade_reason) is not OpeningDriveNoTradeReason
        ):
            raise TypeError("no_trade_reason must be an OpeningDriveNoTradeReason")
        if type(self.early_close) is not bool:
            raise TypeError("early_close must be a bool")
        if (
            self.entry_data_quality is not None
            and type(self.entry_data_quality) is not MarketQuality
        ):
            raise TypeError("entry_data_quality must be a MarketQuality or None")

        if self.no_trade_reason is OpeningDriveNoTradeReason.MISSING_PREVIOUS_QQQ_CLOSE:
            if self.opening_drive_return is not None or self.target_symbol is not None:
                raise ValueError("missing previous close cannot produce a direction")
        elif (
            self.no_trade_reason
            is OpeningDriveNoTradeReason.INCOMPLETE_FIRST_HALF_HOUR_QQQ
        ):
            if self.opening_drive_return is not None or self.target_symbol is not None:
                raise ValueError("incomplete opening data cannot produce a direction")
        elif self.no_trade_reason is OpeningDriveNoTradeReason.ZERO_OPENING_DRIVE:
            if (
                self.opening_drive_return != Decimal("0")
                or self.target_symbol is not None
            ):
                raise ValueError("zero opening drive must remain flat")
        elif self.opening_drive_return is None or self.opening_drive_return == 0:
            raise ValueError("a selected target requires a nonzero opening drive")
        elif self.target_symbol is None:
            raise ValueError("a nonzero opening drive requires a target symbol")

        if self.no_trade_reason in (
            OpeningDriveNoTradeReason.MISSING_PREVIOUS_QQQ_CLOSE,
            OpeningDriveNoTradeReason.INCOMPLETE_FIRST_HALF_HOUR_QQQ,
            OpeningDriveNoTradeReason.ZERO_OPENING_DRIVE,
            OpeningDriveNoTradeReason.MISSING_SCHEDULED_ENTRY_BAR,
        ):
            if self.policy_entry_eligible:
                raise ValueError("frozen policy skips cannot be entry eligible")
        elif not self.policy_entry_eligible:
            raise ValueError("safety/no-skip captures must be policy eligible")

        if self.no_trade_reason is OpeningDriveNoTradeReason.QQQ_DATA_SAFETY_AT_ENTRY:
            if (
                self.entry_data_quality is None
                or self.entry_data_quality is MarketQuality.READY
            ):
                raise ValueError("entry safety skip requires non-ready QQQ quality")
        elif self.policy_entry_eligible and self.entry_data_quality is not None:
            if self.entry_data_quality is not MarketQuality.READY:
                raise ValueError(
                    "only failed entry quality may block an eligible session"
                )


@dataclass(frozen=True, slots=True)
class OpeningDriveEquityMark:
    at: datetime
    equity: Decimal

    def __post_init__(self) -> None:
        if type(self.at) is not datetime or self.at.tzinfo is None:
            raise TypeError("equity mark timestamp must be timezone-aware")
        if type(self.equity) is not Decimal or not self.equity.is_finite():
            raise TypeError("equity must be a finite Decimal")


@dataclass(frozen=True, slots=True)
class OpeningDriveReplayCapture:
    session_captures: tuple[OpeningDriveSessionCapture, ...]
    backtest_result: BacktestResult
    equity_marks: tuple[OpeningDriveEquityMark, ...]
    trade_turnovers: tuple[Decimal, ...]
    missing_held_session_dates: tuple[date, ...]

    def __post_init__(self) -> None:
        if type(self.session_captures) is not tuple or any(
            type(item) is not OpeningDriveSessionCapture
            for item in self.session_captures
        ):
            raise TypeError("session_captures must be a tuple of capture facts")
        if type(self.backtest_result) is not BacktestResult:
            raise TypeError("backtest_result must be an exact BacktestResult")
        if type(self.equity_marks) is not tuple or any(
            type(item) is not OpeningDriveEquityMark for item in self.equity_marks
        ):
            raise TypeError("equity_marks must be a tuple of timestamped marks")
        if type(self.trade_turnovers) is not tuple or any(
            type(value) is not Decimal or not value.is_finite() or value < 0
            for value in self.trade_turnovers
        ):
            raise TypeError("trade_turnovers must be finite nonnegative Decimals")
        if type(self.missing_held_session_dates) is not tuple or any(
            type(value) is not date for value in self.missing_held_session_dates
        ):
            raise TypeError("missing-held dates must be a tuple of dates")
        if self.missing_held_session_dates != tuple(
            sorted(set(self.missing_held_session_dates))
        ):
            raise ValueError("missing-held dates must be sorted and unique")
        if len(self.trade_turnovers) != len(self.backtest_result.trades):
            raise ValueError("trade turnovers must align with completed trades")
        if (
            tuple(mark.equity for mark in self.equity_marks)
            != self.backtest_result.equity_curve
        ):
            raise ValueError("timestamped marks must align with the simulator curve")
        with localcontext(sparse_backtest_decimal_context()):
            total_turnover = sum(self.trade_turnovers, Decimal("0"))
        if total_turnover != self.backtest_result.turnover:
            raise ValueError("trade turnovers must sum to simulator turnover")


def _ratio_return(end: Decimal, start: Decimal) -> Decimal:
    with localcontext(sparse_backtest_decimal_context()):
        return end / start - Decimal("1")


def _expected_session_dates(
    dataset: SparseIntradayDataset,
    authority: HistoricalIntradaySessionAuthority,
) -> tuple[date, ...]:
    return tuple(
        item
        for item in authority.published.sessions
        if dataset.start.date() <= item < dataset.end_exclusive.date()
    )


def _session_capture(
    session_date: date,
    previous_session_date: date | None,
    schedule_opens_at: datetime,
    schedule_closes_at: datetime,
    qqq_by_time: dict[datetime, Bar],
    tqqq_by_time: dict[datetime, Bar],
    sqqq_by_time: dict[datetime, Bar],
    previous_close: Decimal | None,
) -> tuple[OpeningDriveSessionCapture, str | None]:
    entry_at = schedule_closes_at - timedelta(minutes=35)
    force_flat_at = schedule_closes_at - timedelta(minutes=5)
    early_close = schedule_closes_at - schedule_opens_at < timedelta(
        hours=6, minutes=30
    )

    def capture(
        opening_return: Decimal | None,
        target: str | None,
        policy_eligible: bool,
        reason: OpeningDriveNoTradeReason,
    ) -> OpeningDriveSessionCapture:
        return OpeningDriveSessionCapture(
            session_date,
            previous_session_date,
            entry_at,
            force_flat_at,
            opening_return,
            target,
            policy_eligible,
            reason,
            early_close,
            None,
        )

    if previous_close is None:
        return (
            capture(
                None,
                None,
                False,
                OpeningDriveNoTradeReason.MISSING_PREVIOUS_QQQ_CLOSE,
            ),
            None,
        )

    qqq_first_half = tuple(
        qqq_by_time.get(schedule_opens_at + index * _BAR_WIDTH)
        for index in range(_OPENING_BAR_COUNT)
    )
    if any(bar is None for bar in qqq_first_half):
        return (
            capture(
                None,
                None,
                False,
                OpeningDriveNoTradeReason.INCOMPLETE_FIRST_HALF_HOUR_QQQ,
            ),
            None,
        )

    first_half_hour_close = qqq_first_half[-1].close
    opening_return = _ratio_return(first_half_hour_close, previous_close)
    if opening_return == 0:
        return (
            capture(
                opening_return,
                None,
                False,
                OpeningDriveNoTradeReason.ZERO_OPENING_DRIVE,
            ),
            None,
        )

    target_symbol = TQQQ_SYMBOL if opening_return > 0 else SQQQ_SYMBOL
    target_bars = tqqq_by_time if target_symbol == TQQQ_SYMBOL else sqqq_by_time
    if entry_at not in target_bars:
        return (
            capture(
                opening_return,
                target_symbol,
                False,
                OpeningDriveNoTradeReason.MISSING_SCHEDULED_ENTRY_BAR,
            ),
            None,
        )

    return (
        OpeningDriveSessionCapture(
            session_date,
            previous_session_date,
            entry_at,
            force_flat_at,
            opening_return,
            target_symbol,
            True,
            None,
            early_close,
            None,
        ),
        target_symbol,
    )


def run_opening_drive_replay(
    dataset: SparseIntradayDataset,
    *,
    authority: HistoricalIntradaySessionAuthority,
    cost_model: BacktestCostModel,
) -> OpeningDriveReplayCapture:
    """Replay the one frozen opening-drive rule over supplied in-memory bars."""

    if type(dataset) is not SparseIntradayDataset:
        raise TypeError("exact SparseIntradayDataset is required")
    if type(authority) is not HistoricalIntradaySessionAuthority:
        raise TypeError("exact preconstructed session authority is required")
    if type(cost_model) is not BacktestCostModel or cost_model not in (
        ZERO_COST,
        CONSERVATIVE_COSTS,
    ):
        raise ValueError("only the two frozen Architecture 148 cost cases are allowed")

    all_sessions = tuple(authority.published.sessions)
    session_indexes = {item: index for index, item in enumerate(all_sessions)}
    session_dates = _expected_session_dates(dataset, authority)
    bars = dataset.bars_by_symbol
    qqq_by_time = {bar.timestamp: bar for bar in bars["QQQ"]}
    tqqq_by_time = {bar.timestamp: bar for bar in bars[TQQQ_SYMBOL]}
    sqqq_by_time = {bar.timestamp: bar for bar in bars[SQQQ_SYMBOL]}

    entry_symbols: dict[datetime, str] = {}
    session_captures: list[OpeningDriveSessionCapture] = []
    capture_by_entry: dict[datetime, int] = {}
    for current_date in session_dates:
        index = session_indexes[current_date]
        previous_date = all_sessions[index - 1] if index else None
        schedule = authority.schedule_for(current_date)
        if schedule is None:
            raise ValueError("expected session lacks an accepted schedule")
        previous_close: Decimal | None = None
        if previous_date is not None:
            previous_schedule = authority.schedule_for(previous_date)
            if previous_schedule is None:
                raise ValueError("previous expected session lacks an accepted schedule")
            previous_close_bar = qqq_by_time.get(
                previous_schedule.closes_at - _BAR_WIDTH
            )
            if previous_close_bar is not None:
                previous_close = previous_close_bar.close
        capture, target_symbol = _session_capture(
            current_date,
            previous_date,
            schedule.opens_at,
            schedule.closes_at,
            qqq_by_time,
            tqqq_by_time,
            sqqq_by_time,
            previous_close,
        )
        capture_index = len(session_captures)
        session_captures.append(capture)
        if target_symbol is not None:
            entry_symbols[capture.entry_at] = target_symbol
            capture_by_entry[capture.entry_at] = capture_index

    equity_marks: list[OpeningDriveEquityMark] = []
    observed_trades: list[BacktestTrade] = []
    trade_turnovers: list[Decimal] = []
    missing_held_dates: set[date] = set()
    entry_qualities: dict[datetime, MarketQuality] = {}

    def on_equity_mark(at: datetime, equity: Decimal) -> None:
        equity_marks.append(OpeningDriveEquityMark(at, equity))

    def on_trade_close(
        trade: BacktestTrade,
        turnover: Decimal,
        _reversal_source: MarketRegime | None,
    ) -> None:
        observed_trades.append(trade)
        trade_turnovers.append(turnover)

    def on_entry_quality(at: datetime, quality: MarketQuality) -> None:
        entry_qualities[at] = quality

    def on_missing_held_bar(at: datetime, _symbol: str) -> None:
        missing_held_dates.add(at.astimezone(_NEW_YORK).date())

    result = run_sparse_backtest(
        dataset,
        cost_model=cost_model,
        initial_capital=_OPENING_CAPITAL,
        scheduled_entries=entry_symbols,
        scheduled_authority=authority,
        on_equity_mark=on_equity_mark,
        on_trade_close=on_trade_close,
        on_scheduled_entry_quality=on_entry_quality,
        on_missing_held_bar=on_missing_held_bar,
    )

    for entry_at, capture_index in capture_by_entry.items():
        quality = entry_qualities.get(entry_at)
        if quality is None:
            raise ValueError("scheduled entry did not produce a QQQ quality fact")
        capture = session_captures[capture_index]
        if quality is MarketQuality.READY:
            session_captures[capture_index] = replace(
                capture, entry_data_quality=quality
            )
        else:
            session_captures[capture_index] = replace(
                capture,
                no_trade_reason=OpeningDriveNoTradeReason.QQQ_DATA_SAFETY_AT_ENTRY,
                entry_data_quality=quality,
            )

    if tuple(observed_trades) != result.trades:
        raise ValueError("settled-trade observer differs from sparse replay result")
    if len(entry_qualities) != len(entry_symbols):
        raise ValueError("scheduled entry quality facts are incomplete")

    capture_by_date = {item.session_date: item for item in session_captures}
    traded_dates: set[date] = set()
    for trade in result.trades:
        session_date = trade.entry_at.date()
        capture = capture_by_date.get(session_date)
        if capture is None or session_date in traded_dates:
            raise ValueError("simulator trade lacks a unique session capture")
        if (
            not capture.policy_entry_eligible
            or capture.no_trade_reason is not None
            or trade.entry_at != capture.entry_at
            or trade.symbol != capture.target_symbol
        ):
            raise ValueError("simulator trade conflicts with captured policy facts")
        if trade.exit_at > capture.force_flat_at:
            raise ValueError("simulator trade extends beyond the forced-flat boundary")
        if (
            trade.exit_reason == "FORCED_FLAT"
            and trade.exit_at != capture.force_flat_at
        ):
            raise ValueError("forced-flat trade did not exit at the scheduled boundary")
        if trade.exit_reason not in ("STOP", "SAFETY", "FORCED_FLAT"):
            raise ValueError("scheduled policy produced a non-frozen exit reason")
        traded_dates.add(session_date)

    for capture in session_captures:
        if capture.no_trade_reason is None and capture.session_date not in traded_dates:
            raise ValueError("eligible capture did not produce its scheduled trade")
        if capture.no_trade_reason is not None and capture.session_date in traded_dates:
            raise ValueError("no-trade capture unexpectedly produced a trade")

    # The fixed late-window diagnostic is derived only after execution facts
    # have been settled; it never participates in entry authorization.
    for index, capture in enumerate(session_captures):
        qqq_entry_bar = qqq_by_time.get(capture.entry_at)
        qqq_force_flat_bar = qqq_by_time.get(capture.force_flat_at)
        late_return = (
            _ratio_return(qqq_force_flat_bar.open, qqq_entry_bar.open)
            if qqq_entry_bar is not None and qqq_force_flat_bar is not None
            else None
        )
        session_captures[index] = replace(capture, qqq_late_window_return=late_return)

    return OpeningDriveReplayCapture(
        tuple(session_captures),
        result,
        tuple(equity_marks),
        tuple(trade_turnovers),
        tuple(sorted(missing_held_dates)),
    )


__all__ = [
    "OPENING_DRIVE_POLICY_ID",
    "OPENING_DRIVE_REPLAY_SCHEMA",
    "OPENING_DRIVE_SIMULATOR_VERSION",
    "OpeningDriveEquityMark",
    "OpeningDriveNoTradeReason",
    "OpeningDriveReplayCapture",
    "OpeningDriveSessionCapture",
    "run_opening_drive_replay",
]
