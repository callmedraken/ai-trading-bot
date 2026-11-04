"""P6 production decision composition over Robinhood completed daily bars."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import (
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    localcontext,
)
from enum import StrEnum

from trading_bot.desktop_live.configuration import TinyLivePolicy
from trading_bot.desktop_paper.robinhood_read import EquityPositionObservation
from trading_bot.experiments.filtered_trend_strategies import StrategyConfig, signal
from trading_bot.robinhood_mcp.historical import RobinhoodDailyHistory

MIN_COMPLETED_BARS = 60
_ARITHMETIC_CONTEXT = Context(prec=50, rounding=ROUND_HALF_EVEN)
_CLOSE_SERIES_ARITHMETIC_CONTEXT = Context(
    prec=50,
    rounding=ROUND_HALF_EVEN,
    Emin=-999999,
    Emax=999999,
    capitals=1,
    clamp=0,
    traps=[InvalidOperation, DivisionByZero, Overflow],
)
P6_CLOSE_SERIES_INPUT_BASIS = "ROBINHOOD_HISTORY59_PLUS_OFFICIAL_CLOSE_V1"


class LiveStrategyDecision(StrEnum):
    BUY = "BUY"
    NO_ACTION = "NO_ACTION"


class P6CloseSource(StrEnum):
    """Source class for one completed P6 close observation."""

    HISTORICAL_DAILY = "HISTORICAL_DAILY"
    ROBINHOOD_OFFICIAL_CLOSE = "ROBINHOOD_OFFICIAL_CLOSE"


@dataclass(frozen=True, slots=True)
class P6CompletedClose:
    """One immutable session close with its bounded source classification."""

    session_date: date
    close: Decimal
    source: P6CloseSource

    def __post_init__(self) -> None:
        if isinstance(self.session_date, datetime) or not isinstance(
            self.session_date, date
        ):
            raise TypeError("session_date must be a date")
        if not isinstance(self.close, Decimal):
            raise TypeError("close must be a Decimal")
        if not self.close.is_finite() or self.close <= 0:
            raise ValueError("close must be a positive finite Decimal")
        if not isinstance(self.source, P6CloseSource):
            raise TypeError("source must be a P6CloseSource")


@dataclass(frozen=True, slots=True)
class LiveStrategyResult:
    decision: LiveStrategyDecision
    raw_signal: str
    completed_bar_count: int
    previous_completed_session: str
    fast_average: str
    slow_average: str
    values_digest: str


def decide_live_strategy(
    history: RobinhoodDailyHistory,
    position: EquityPositionObservation | None,
    policy: TinyLivePolicy,
) -> LiveStrategyResult:
    """Apply exactly the accepted BASE_MA 35/50 signal to completed bars only."""
    if not isinstance(history, RobinhoodDailyHistory):
        raise TypeError("history must be RobinhoodDailyHistory")
    if not isinstance(policy, TinyLivePolicy):
        raise TypeError("policy must be TinyLivePolicy")
    if position is not None and str(position.symbol) != str(policy.symbol):
        raise ValueError("position symbol does not match the P6 policy")
    bars = tuple(item.bar for item in history.bars)
    if len(bars) < MIN_COMPLETED_BARS:
        raise ValueError("P6 requires at least 60 completed daily bars")
    if not bars:
        raise ValueError("P6 history cannot be empty")
    config = StrategyConfig("BASE_MA", 35, 50, "none")
    invested = position is not None and position.quantity > 0
    raw = signal(config, bars, invested=invested)
    decision = (
        LiveStrategyDecision.BUY
        if raw == "BUY" and not invested
        else LiveStrategyDecision.NO_ACTION
    )
    closes = tuple(bar.close for bar in bars)
    with localcontext(_ARITHMETIC_CONTEXT):
        fast = sum(closes[-35:], start=Decimal("0")) / 35
        slow = sum(closes[-50:], start=Decimal("0")) / 50
    material = {
        "schema": "arch147-p6-live-signal/v1",
        "bars": len(bars),
        "previous_session": history.bars[-1].session.session_date.isoformat(),
        "fast": format(fast, "f"),
        "slow": format(slow, "f"),
        "raw_signal": raw,
        "invested": invested,
    }
    digest = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()
    return LiveStrategyResult(
        decision,
        raw,
        len(bars),
        history.bars[-1].session.session_date.isoformat(),
        format(fast, "f"),
        format(slow, "f"),
        digest,
    )


def decide_live_strategy_from_closes(
    completed_closes: Sequence[P6CompletedClose],
    position: EquityPositionObservation | None,
    policy: TinyLivePolicy,
    *,
    selected_sessions: Sequence[date],
) -> LiveStrategyResult:
    """Apply the accepted BASE_MA 35/50 signal to a 59+1 close composition."""
    if not isinstance(policy, TinyLivePolicy):
        raise TypeError("policy must be TinyLivePolicy")
    if position is not None and str(position.symbol) != str(policy.symbol):
        raise ValueError("position symbol does not match the P6 policy")
    if isinstance(completed_closes, (str, bytes)) or not isinstance(
        completed_closes, Sequence
    ):
        raise TypeError("completed_closes must be a sequence")
    if isinstance(selected_sessions, (str, bytes)) or not isinstance(
        selected_sessions, Sequence
    ):
        raise TypeError("selected_sessions must be a sequence")

    closes = tuple(completed_closes)
    sessions = tuple(selected_sessions)
    if len(closes) != MIN_COMPLETED_BARS:
        raise ValueError("P6 requires exactly 60 completed closes")
    if len(sessions) != MIN_COMPLETED_BARS:
        raise ValueError("P6 requires exactly 60 selected sessions")
    if any(not isinstance(item, P6CompletedClose) for item in closes):
        raise TypeError("completed_closes must contain P6CompletedClose values")
    if any(
        isinstance(session, datetime) or not isinstance(session, date)
        for session in sessions
    ):
        raise TypeError("selected_sessions must contain dates")
    if any(left >= right for left, right in zip(sessions, sessions[1:], strict=False)):
        raise ValueError("selected_sessions must be strictly increasing")
    if tuple(item.session_date for item in closes) != sessions:
        raise ValueError("completed close sessions must match selected sessions")
    expected_sources = (P6CloseSource.HISTORICAL_DAILY,) * 59 + (
        P6CloseSource.ROBINHOOD_OFFICIAL_CLOSE,
    )
    if tuple(item.source for item in closes) != expected_sources:
        raise ValueError("P6 close sources must be 59 historical and one official")

    close_values = tuple(item.close for item in closes)
    with localcontext(_CLOSE_SERIES_ARITHMETIC_CONTEXT):
        fast_total = Decimal("0")
        slow_total = Decimal("0")
        for index, value in enumerate(close_values):
            fast_total += value
            slow_total += value
            if index >= 35:
                fast_total -= close_values[index - 35]
            if index >= 50:
                slow_total -= close_values[index - 50]
        fast = fast_total / Decimal(35)
        slow = slow_total / Decimal(50)

    invested = position is not None and position.quantity > 0
    if fast > slow:
        raw = "BUY" if not invested else "HOLD"
    elif fast < slow:
        raw = "SELL" if invested else "HOLD"
    else:
        raw = "HOLD"
    decision = (
        LiveStrategyDecision.BUY
        if raw == "BUY" and not invested
        else LiveStrategyDecision.NO_ACTION
    )
    latest_session = sessions[-1].isoformat()
    material = {
        "schema": "arch147-p6-live-signal/v2",
        "completed_count": MIN_COMPLETED_BARS,
        "latest_session": latest_session,
        "fast": format(fast, "f"),
        "slow": format(slow, "f"),
        "raw_signal": raw,
        "invested": invested,
        "input_basis": P6_CLOSE_SERIES_INPUT_BASIS,
    }
    digest = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()
    return LiveStrategyResult(
        decision,
        raw,
        MIN_COMPLETED_BARS,
        latest_session,
        format(fast, "f"),
        format(slow, "f"),
        digest,
    )
