"""Deterministic completed-bar regime, stop and published-session policies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
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
from zoneinfo import ZoneInfo

from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
    UnsupportedNYSEPublishedSessionYearError,
)
from trading_bot.review_paper.session_admission import ReviewPaperSessionSchedule

from .models import (
    CompletedBar,
    MarketQuality,
    MarketRegime,
    MarketSnapshot,
    SignalAnalysis,
    SignalPoint,
)

_PRECISION = 48
_BAR_WIDTH = timedelta(minutes=5)
_MAX_BAR_AGE = timedelta(minutes=5)
_NEW_YORK = ZoneInfo("America/New_York")
HARD_STOP_LOSS_PCT = Decimal("0.03")


class SessionReason(StrEnum):
    ENTRY_OPEN = "ENTRY_OPEN"
    BEFORE_SESSION = "BEFORE_SESSION"
    OPENING_EXCLUSION = "OPENING_EXCLUSION"
    CLOSING_EXCLUSION = "CLOSING_EXCLUSION"
    FORCED_FLAT = "FORCED_FLAT"
    AFTER_SESSION = "AFTER_SESSION"
    NON_SESSION_DATE = "NON_SESSION_DATE"
    SESSION_AUTHORITY_UNAVAILABLE = "SESSION_AUTHORITY_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class SessionDecision:
    schedule: ReviewPaperSessionSchedule | None
    can_enter: bool
    force_flat: bool
    reason: SessionReason


@dataclass(frozen=True, slots=True)
class HardStopPolicy:
    """The fixed 3% hard stop derived from reconciled average fill only."""

    loss_pct: Decimal = HARD_STOP_LOSS_PCT

    def __post_init__(self) -> None:
        if self.loss_pct != HARD_STOP_LOSS_PCT:
            raise ValueError("v1 hard stop is frozen at 3.00 percent")

    def threshold(
        self,
        reconciled_average_fill: Decimal,
        previous_threshold: Decimal | None = None,
    ) -> Decimal:
        if not isinstance(reconciled_average_fill, Decimal):
            raise TypeError("reconciled_average_fill must be Decimal")
        if not reconciled_average_fill.is_finite() or reconciled_average_fill <= 0:
            raise ValueError("reconciled_average_fill must be finite and positive")
        if previous_threshold is not None and (
            not isinstance(previous_threshold, Decimal)
            or not previous_threshold.is_finite()
            or previous_threshold <= 0
        ):
            raise ValueError("previous_threshold must be finite and positive")
        precision = len(reconciled_average_fill.as_tuple().digits) + 2
        if previous_threshold is not None:
            precision = max(precision, len(previous_threshold.as_tuple().digits))
        with localcontext(_calculation_context(precision)):
            computed = reconciled_average_fill * (Decimal("1") - HARD_STOP_LOSS_PCT)
            if previous_threshold is None:
                return computed
            return max(computed, previous_threshold)

    @staticmethod
    def is_breached(price: Decimal, threshold: Decimal) -> bool:
        for name, value in (("price", price), ("threshold", threshold)):
            if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        return price <= threshold


def session_decision(
    as_of: datetime,
    *,
    authority: NYSEPublishedRegularSessionAuthority | None = None,
) -> SessionDecision:
    """Apply the 15/30-minute entry windows and five-minute force-flat rule."""

    if not isinstance(as_of, datetime) or as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    authority = authority or NYSEPublishedRegularSessionAuthority()
    local_date = as_of.astimezone(_NEW_YORK).date()
    try:
        schedule = authority.schedule_for(local_date)
    except UnsupportedNYSEPublishedSessionYearError:
        return SessionDecision(
            None, False, False, SessionReason.SESSION_AUTHORITY_UNAVAILABLE
        )
    if schedule is None:
        return SessionDecision(None, False, False, SessionReason.NON_SESSION_DATE)
    # The calendar object normalizes these instants to UTC. Use them directly so
    # DST and the published early-close date remain authoritative.
    open_entry = schedule.opens_at + timedelta(minutes=15)
    close_entry = schedule.closes_at - timedelta(minutes=30)
    force_flat_at = schedule.closes_at - timedelta(minutes=5)
    as_of_utc = as_of.astimezone(schedule.opens_at.tzinfo)
    if as_of_utc < schedule.opens_at:
        return SessionDecision(schedule, False, False, SessionReason.BEFORE_SESSION)
    if as_of_utc >= schedule.closes_at:
        return SessionDecision(schedule, False, True, SessionReason.AFTER_SESSION)
    if as_of_utc >= force_flat_at:
        return SessionDecision(schedule, False, True, SessionReason.FORCED_FLAT)
    if as_of_utc < open_entry:
        return SessionDecision(schedule, False, False, SessionReason.OPENING_EXCLUSION)
    if as_of_utc >= close_entry:
        return SessionDecision(schedule, False, False, SessionReason.CLOSING_EXCLUSION)
    return SessionDecision(schedule, True, False, SessionReason.ENTRY_OPEN)


def analyze_market(
    market: MarketSnapshot,
    *,
    authority: NYSEPublishedRegularSessionAuthority | None = None,
) -> SignalAnalysis:
    """Classify the latest completed QQQ bars using frozen Decimal arithmetic.

    EMA20/50 seed with a simple average of their first full period. RSI14 seeds
    with the first 14 close changes, then uses Wilder smoothing. Session VWAP
    uses typical price `(high + low + close) / 3` weighted by volume and resets
    at every published regular-session open. Flat RSI is 50; equal comparisons
    are NEUTRAL. A source-marked interpolated bar is never used.
    """

    if not isinstance(market, MarketSnapshot):
        raise TypeError("market must be MarketSnapshot")
    authority = authority or NYSEPublishedRegularSessionAuthority()
    as_of = market.as_of
    if not market.completed_bars:
        return _unavailable(MarketQuality.NO_CURRENT_SESSION_DATA, "NO_COMPLETED_BARS")

    ordered = tuple(sorted(market.completed_bars, key=lambda bar: bar.timestamp))
    if len({bar.timestamp for bar in ordered}) != len(ordered):
        return _unavailable(MarketQuality.GAP, "DUPLICATE_BAR_TIMESTAMP")
    if ordered != market.completed_bars:
        return _unavailable(MarketQuality.INVALID, "BARS_NOT_CHRONOLOGICAL")

    schedules: dict[date, ReviewPaperSessionSchedule] = {}
    grouped: dict[date, list[CompletedBar]] = {}
    for bar in ordered:
        if bar.interpolated:
            return _unavailable(MarketQuality.INTERPOLATED, "INTERPOLATED_BAR")
        if bar.ends_at > as_of:
            return _unavailable(MarketQuality.INVALID, "UNCOMPLETED_BAR_IN_INPUT")
        session_date = bar.timestamp.astimezone(_NEW_YORK).date()
        try:
            schedule = authority.schedule_for(session_date)
        except UnsupportedNYSEPublishedSessionYearError:
            return _unavailable(MarketQuality.INVALID, "UNSUPPORTED_SESSION_YEAR")
        if schedule is None:
            return _unavailable(MarketQuality.INVALID, "BAR_OUTSIDE_PUBLISHED_SESSION")
        if not (schedule.opens_at <= bar.timestamp < schedule.closes_at):
            return _unavailable(MarketQuality.INVALID, "BAR_OUTSIDE_REGULAR_HOURS")
        if bar.ends_at > schedule.closes_at:
            return _unavailable(MarketQuality.INVALID, "BAR_CROSSES_SESSION_CLOSE")
        offset = bar.timestamp - schedule.opens_at
        if offset % _BAR_WIDTH:
            return _unavailable(MarketQuality.GAP, "BAR_NOT_ALIGNED_TO_FIVE_MINUTES")
        schedules[session_date] = schedule
        grouped.setdefault(session_date, []).append(bar)

    # A missing entire published session between observed sessions is data loss.
    observed_days = sorted(grouped)
    for previous_day, current_day in zip(
        observed_days, observed_days[1:], strict=False
    ):
        cursor = previous_day + timedelta(days=1)
        while cursor < current_day:
            try:
                intermediate = authority.schedule_for(cursor)
            except UnsupportedNYSEPublishedSessionYearError:
                return _unavailable(MarketQuality.INVALID, "UNSUPPORTED_SESSION_YEAR")
            if intermediate is not None and cursor not in grouped:
                return _unavailable(MarketQuality.GAP, "MISSING_PUBLISHED_SESSION")
            cursor += timedelta(days=1)
    current_session_date = as_of.astimezone(_NEW_YORK).date()
    for day, bars in grouped.items():
        schedule = schedules[day]
        if day != current_session_date:
            if day != observed_days[0] and bars[0].timestamp != schedule.opens_at:
                return _unavailable(MarketQuality.GAP, "OBSERVED_SESSION_START_MISSING")
            if bars[-1].ends_at != schedule.closes_at:
                return _unavailable(MarketQuality.GAP, "OBSERVED_SESSION_CLOSE_MISSING")
        for left, right in zip(bars, bars[1:], strict=False):
            if right.timestamp - left.timestamp != _BAR_WIDTH:
                return _unavailable(MarketQuality.GAP, "NONCONTIGUOUS_SESSION_BARS")

    current_bars = grouped.get(current_session_date, [])
    if not current_bars:
        try:
            current_schedule = authority.schedule_for(current_session_date)
        except UnsupportedNYSEPublishedSessionYearError:
            return _unavailable(MarketQuality.INVALID, "UNSUPPORTED_SESSION_YEAR")
        if current_schedule is not None:
            latest_expected_end = _latest_completed_end(as_of, current_schedule)
            if latest_expected_end > current_schedule.opens_at:
                return _unavailable(MarketQuality.GAP, "MISSING_LATEST_COMPLETED_BAR")
        return _unavailable(
            MarketQuality.NO_CURRENT_SESSION_DATA, "NO_CURRENT_SESSION_BARS"
        )
    current_schedule = schedules[current_session_date]
    if current_bars[0].timestamp != current_schedule.opens_at:
        return _unavailable(MarketQuality.GAP, "SESSION_VWAP_START_MISSING")
    if current_bars[-1].ends_at != _latest_completed_end(as_of, current_schedule):
        return _unavailable(MarketQuality.GAP, "MISSING_LATEST_COMPLETED_BAR")
    if as_of - current_bars[-1].ends_at > _MAX_BAR_AGE:
        return _unavailable(MarketQuality.STALE, "LATEST_COMPLETED_BAR_STALE")

    with localcontext(_calculation_context(_PRECISION)):
        closes = [bar.close for bar in ordered]
        ema20 = _ema(closes, 20)
        ema50 = _ema(closes, 50)
        rsi14 = _rsi_wilder(closes, 14)
        vwaps = _session_vwaps(ordered)
        points: list[SignalPoint | None] = []
        for index, bar in enumerate(ordered):
            vwap = vwaps[index]
            fast = ema20[index]
            slow = ema50[index]
            rsi = rsi14[index]
            if vwap is None or fast is None or slow is None or rsi is None:
                points.append(None)
                continue
            if bar.close > vwap and fast > slow and rsi >= Decimal("55"):
                candidate = MarketRegime.BULLISH
            elif bar.close < vwap and fast < slow and rsi <= Decimal("45"):
                candidate = MarketRegime.BEARISH
            else:
                candidate = MarketRegime.NEUTRAL
            points.append(
                SignalPoint(
                    bar_end=bar.ends_at,
                    close=bar.close,
                    session_vwap=vwap,
                    ema20=fast,
                    ema50=slow,
                    rsi14=rsi,
                    candidate=candidate,
                )
            )

    index_by_timestamp = {bar.timestamp: i for i, bar in enumerate(ordered)}
    current_points = [
        point
        for bar in current_bars
        if (point := points[index_by_timestamp[bar.timestamp]]) is not None
    ]
    if not current_points:
        return _unavailable(MarketQuality.INSUFFICIENT_WARMUP, "INDICATOR_WARMUP")
    latest = current_points[-1]
    previous = current_points[-2] if len(current_points) >= 2 else None
    if previous is not None and latest.bar_end - previous.bar_end != _BAR_WIDTH:
        return _unavailable(MarketQuality.GAP, "CONFIRMATION_BARS_NOT_ADJACENT")
    confirmation = None
    if (
        previous is not None
        and latest.candidate is previous.candidate
        and latest.candidate in (MarketRegime.BULLISH, MarketRegime.BEARISH)
    ):
        confirmation = latest.candidate
    return SignalAnalysis(
        MarketQuality.READY,
        latest.candidate,
        confirmation,
        latest,
        previous,
        "COMPLETED_BAR_CLASSIFICATION",
    )


def _ema(values: list[Decimal], period: int) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(values)
    if len(values) < period:
        return result
    with localcontext(_calculation_context(_PRECISION)):
        average = sum(values[:period], Decimal("0")) / Decimal(period)
        result[period - 1] = average
        multiplier = Decimal("2") / Decimal(period + 1)
        for index in range(period, len(values)):
            average = (values[index] - average) * multiplier + average
            result[index] = average
    return result


def _rsi_wilder(values: list[Decimal], period: int) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(values)
    if len(values) <= period:
        return result
    with localcontext(_calculation_context(_PRECISION)):
        changes = [values[index] - values[index - 1] for index in range(1, len(values))]
        gains = [max(change, Decimal("0")) for change in changes]
        losses = [max(-change, Decimal("0")) for change in changes]
        average_gain = sum(gains[:period], Decimal("0")) / Decimal(period)
        average_loss = sum(losses[:period], Decimal("0")) / Decimal(period)
        result[period] = _rsi_value(average_gain, average_loss)
        for index in range(period + 1, len(values)):
            gain = gains[index - 1]
            loss = losses[index - 1]
            average_gain = (average_gain * Decimal(period - 1) + gain) / Decimal(period)
            average_loss = (average_loss * Decimal(period - 1) + loss) / Decimal(period)
            result[index] = _rsi_value(average_gain, average_loss)
    return result


def _rsi_value(average_gain: Decimal, average_loss: Decimal) -> Decimal:
    if average_gain == 0 and average_loss == 0:
        return Decimal("50")
    if average_loss == 0:
        return Decimal("100")
    if average_gain == 0:
        return Decimal("0")
    return Decimal("100") - (
        Decimal("100") / (Decimal("1") + average_gain / average_loss)
    )


def _session_vwaps(bars: tuple[CompletedBar, ...]) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(bars)
    with localcontext(_calculation_context(_PRECISION)):
        current_date: date | None = None
        weighted_total = Decimal("0")
        volume_total = 0
        for index, bar in enumerate(bars):
            session_date = bar.timestamp.astimezone(_NEW_YORK).date()
            if session_date != current_date:
                current_date = session_date
                weighted_total = Decimal("0")
                volume_total = 0
            typical_price = (bar.high + bar.low + bar.close) / Decimal("3")
            weighted_total += typical_price * bar.volume
            volume_total += bar.volume
            if volume_total > 0:
                result[index] = weighted_total / Decimal(volume_total)
    return result


def _unavailable(quality: MarketQuality, reason: str) -> SignalAnalysis:
    return SignalAnalysis(quality, None, None, None, None, reason)


def _latest_completed_end(
    as_of: datetime, schedule: ReviewPaperSessionSchedule
) -> datetime:
    bounded_as_of = min(as_of, schedule.closes_at)
    elapsed = bounded_as_of - schedule.opens_at
    completed_slots = elapsed // _BAR_WIDTH
    return schedule.opens_at + completed_slots * _BAR_WIDTH


def _calculation_context(precision: int) -> Context:
    context = Context(
        prec=precision,
        rounding=ROUND_HALF_EVEN,
        Emin=-999999,
        Emax=999999,
        capitals=1,
        clamp=0,
    )
    for signal in context.traps:
        context.traps[signal] = False
    context.traps[InvalidOperation] = True
    context.traps[DivisionByZero] = True
    context.traps[Overflow] = True
    return context
