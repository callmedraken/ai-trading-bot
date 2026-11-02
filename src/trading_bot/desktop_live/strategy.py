"""P6 production decision composition over Robinhood completed daily bars."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from enum import StrEnum

from trading_bot.desktop_live.configuration import TinyLivePolicy
from trading_bot.desktop_paper.robinhood_read import EquityPositionObservation
from trading_bot.experiments.filtered_trend_strategies import StrategyConfig, signal
from trading_bot.robinhood_mcp.historical import RobinhoodDailyHistory

MIN_COMPLETED_BARS = 60
_ARITHMETIC_CONTEXT = Context(prec=50, rounding=ROUND_HALF_EVEN)


class LiveStrategyDecision(StrEnum):
    BUY = "BUY"
    NO_ACTION = "NO_ACTION"


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
