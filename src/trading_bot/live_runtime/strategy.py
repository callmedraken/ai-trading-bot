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
    TargetPosition,
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
    at every published regular-session open. Indicator state advances over real
    observations only; current-session gaps fail closed.
    """

    if not isinstance(market, MarketSnapshot):
        raise TypeError("market must be MarketSnapshot")
    if not market.completed_bars:
        return _unavailable(MarketQuality.NO_CURRENT_SESSION_DATA, "NO_COMPLETED_BARS")

    ordered = tuple(sorted(market.completed_bars, key=lambda bar: bar.timestamp))
    if len({bar.timestamp for bar in ordered}) != len(ordered):
        return _unavailable(MarketQuality.GAP, "DUPLICATE_BAR_TIMESTAMP")
    if ordered != market.completed_bars:
        return _unavailable(MarketQuality.INVALID, "BARS_NOT_CHRONOLOGICAL")

    stream = _CompletedBarSignalStream(
        authority or NYSEPublishedRegularSessionAuthority()
    )
    for bar in ordered:
        stream.append(bar)
    return stream.analyze(market.as_of)


class _CompletedBarSignalStream:
    """Incremental equivalent of ``analyze_market`` for ordered real bars."""

    def __init__(self, authority: NYSEPublishedRegularSessionAuthority) -> None:
        self._authority = authority
        self._last_bar: CompletedBar | None = None
        self._last_session_date: date | None = None
        self._session_schedule: ReviewPaperSessionSchedule | None = None
        self._session_first_timestamp: datetime | None = None
        self._session_gap = False
        self._session_weighted_total = Decimal("0")
        self._session_volume_total = 0
        self._session_latest_point: SignalPoint | None = None
        self._session_previous_point: SignalPoint | None = None
        self._history_gap = False
        self._invalid: tuple[MarketQuality, str] | None = None
        self._count = 0
        self._last_close: Decimal | None = None
        self._ema20_seed = Decimal("0")
        self._ema50_seed = Decimal("0")
        self._ema20: Decimal | None = None
        self._ema50: Decimal | None = None
        self._rsi_gain_seed = Decimal("0")
        self._rsi_loss_seed = Decimal("0")
        self._rsi_average_gain: Decimal | None = None
        self._rsi_average_loss: Decimal | None = None
        self._rsi: Decimal | None = None

    def append(self, bar: CompletedBar) -> None:
        """Consume one new, real completed observation in chronological order."""

        if self._invalid is not None:
            return
        if not isinstance(bar, CompletedBar):
            self._invalid = (MarketQuality.INVALID, "BAR_TYPE_INVALID")
            return
        previous = self._last_bar
        if previous is not None and bar.timestamp <= previous.timestamp:
            if bar.timestamp == previous.timestamp:
                self._invalid = (MarketQuality.GAP, "DUPLICATE_BAR_TIMESTAMP")
            else:
                self._invalid = (MarketQuality.INVALID, "BARS_NOT_CHRONOLOGICAL")
            return
        if bar.interpolated:
            self._invalid = (MarketQuality.INTERPOLATED, "INTERPOLATED_BAR")
            return

        session_date = bar.timestamp.astimezone(_NEW_YORK).date()
        try:
            schedule = self._authority.schedule_for(session_date)
        except UnsupportedNYSEPublishedSessionYearError:
            self._invalid = (MarketQuality.INVALID, "UNSUPPORTED_SESSION_YEAR")
            return
        if schedule is None:
            self._invalid = (MarketQuality.INVALID, "BAR_OUTSIDE_PUBLISHED_SESSION")
            return
        if not (schedule.opens_at <= bar.timestamp < schedule.closes_at):
            self._invalid = (MarketQuality.INVALID, "BAR_OUTSIDE_REGULAR_HOURS")
            return
        if bar.ends_at > schedule.closes_at:
            self._invalid = (MarketQuality.INVALID, "BAR_CROSSES_SESSION_CLOSE")
            return
        if (bar.timestamp - schedule.opens_at) % _BAR_WIDTH:
            self._invalid = (MarketQuality.GAP, "BAR_NOT_ALIGNED_TO_FIVE_MINUTES")
            return

        if self._last_session_date != session_date:
            if self._last_session_date is not None:
                cursor = self._last_session_date + timedelta(days=1)
                while cursor < session_date:
                    try:
                        intermediate = self._authority.schedule_for(cursor)
                    except UnsupportedNYSEPublishedSessionYearError:
                        self._invalid = (
                            MarketQuality.INVALID,
                            "UNSUPPORTED_SESSION_YEAR",
                        )
                        return
                    if intermediate is not None:
                        self._history_gap = True
                    cursor += timedelta(days=1)
            self._last_session_date = session_date
            self._session_schedule = schedule
            self._session_first_timestamp = bar.timestamp
            self._session_gap = False
            self._session_weighted_total = Decimal("0")
            self._session_volume_total = 0
            self._session_latest_point = None
            self._session_previous_point = None
        elif previous is not None and bar.timestamp - previous.timestamp != _BAR_WIDTH:
            self._session_gap = True

        with localcontext(_calculation_context(_PRECISION)):
            typical_price = (bar.high + bar.low + bar.close) / Decimal("3")
            self._session_weighted_total += typical_price * bar.volume
            self._session_volume_total += bar.volume
            vwap = (
                self._session_weighted_total / Decimal(self._session_volume_total)
                if self._session_volume_total > 0
                else None
            )
            ema20, ema50, rsi = self._append_indicators(bar.close)

        if (
            vwap is not None
            and ema20 is not None
            and ema50 is not None
            and rsi is not None
        ):
            if bar.close > vwap and ema20 > ema50 and rsi >= Decimal("55"):
                candidate = MarketRegime.BULLISH
            elif bar.close < vwap and ema20 < ema50 and rsi <= Decimal("45"):
                candidate = MarketRegime.BEARISH
            else:
                candidate = MarketRegime.NEUTRAL
            self._session_previous_point = self._session_latest_point
            self._session_latest_point = SignalPoint(
                bar.ends_at,
                bar.close,
                vwap,
                ema20,
                ema50,
                rsi,
                candidate,
            )

        self._last_bar = bar

    def analyze(self, as_of: datetime) -> SignalAnalysis:
        """Return the same latest-signal result as the batch analyzer."""

        if self._invalid is not None:
            return _unavailable(*self._invalid)
        if self._last_bar is None:
            return _unavailable(
                MarketQuality.NO_CURRENT_SESSION_DATA, "NO_COMPLETED_BARS"
            )
        if not isinstance(as_of, datetime) or as_of.tzinfo is None:
            return _unavailable(MarketQuality.INVALID, "AS_OF_INVALID")
        if self._last_bar.ends_at > as_of:
            return _unavailable(MarketQuality.INVALID, "UNCOMPLETED_BAR_IN_INPUT")

        current_session_date = as_of.astimezone(_NEW_YORK).date()
        if self._history_gap:
            return _unavailable(MarketQuality.GAP, "MISSING_PUBLISHED_SESSION")
        has_current = self._last_session_date == current_session_date
        if not has_current:
            try:
                current_schedule = self._authority.schedule_for(current_session_date)
            except UnsupportedNYSEPublishedSessionYearError:
                return _unavailable(MarketQuality.INVALID, "UNSUPPORTED_SESSION_YEAR")
            if current_schedule is not None:
                latest_expected_end = _latest_completed_end(as_of, current_schedule)
                if latest_expected_end > current_schedule.opens_at:
                    return _unavailable(
                        MarketQuality.GAP, "MISSING_LATEST_COMPLETED_BAR"
                    )
            return _unavailable(
                MarketQuality.NO_CURRENT_SESSION_DATA, "NO_CURRENT_SESSION_BARS"
            )

        schedule = self._session_schedule
        if schedule is None:
            return _unavailable(MarketQuality.INVALID, "SESSION_AUTHORITY_UNAVAILABLE")
        if self._session_first_timestamp != schedule.opens_at:
            return _unavailable(MarketQuality.GAP, "SESSION_VWAP_START_MISSING")
        if self._session_gap:
            return _unavailable(MarketQuality.GAP, "NONCONTIGUOUS_CURRENT_SESSION_BARS")
        if self._last_bar.ends_at != _latest_completed_end(as_of, schedule):
            return _unavailable(MarketQuality.GAP, "MISSING_LATEST_COMPLETED_BAR")
        if as_of - self._last_bar.ends_at > _MAX_BAR_AGE:
            return _unavailable(MarketQuality.STALE, "LATEST_COMPLETED_BAR_STALE")
        latest = self._session_latest_point
        if latest is None:
            return _unavailable(MarketQuality.INSUFFICIENT_WARMUP, "INDICATOR_WARMUP")
        previous = self._session_previous_point
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

    def _append_indicators(
        self, close: Decimal
    ) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
        index = self._count
        with localcontext(_calculation_context(_PRECISION)):
            if index < 20:
                self._ema20_seed += close
                if index == 19:
                    self._ema20 = self._ema20_seed / Decimal("20")
            else:
                assert self._ema20 is not None
                multiplier = Decimal("2") / Decimal("21")
                self._ema20 = (close - self._ema20) * multiplier + self._ema20

            if index < 50:
                self._ema50_seed += close
                if index == 49:
                    self._ema50 = self._ema50_seed / Decimal("50")
            else:
                assert self._ema50 is not None
                multiplier = Decimal("2") / Decimal("51")
                self._ema50 = (close - self._ema50) * multiplier + self._ema50

            if self._last_close is not None:
                change = close - self._last_close
                gain = max(change, Decimal("0"))
                loss = max(-change, Decimal("0"))
                if index <= 14:
                    self._rsi_gain_seed += gain
                    self._rsi_loss_seed += loss
                    if index == 14:
                        self._rsi_average_gain = self._rsi_gain_seed / Decimal("14")
                        self._rsi_average_loss = self._rsi_loss_seed / Decimal("14")
                        self._rsi = _rsi_value(
                            self._rsi_average_gain, self._rsi_average_loss
                        )
                else:
                    assert self._rsi_average_gain is not None
                    assert self._rsi_average_loss is not None
                    self._rsi_average_gain = (
                        self._rsi_average_gain * Decimal("13") + gain
                    ) / Decimal("14")
                    self._rsi_average_loss = (
                        self._rsi_average_loss * Decimal("13") + loss
                    ) / Decimal("14")
                    self._rsi = _rsi_value(
                        self._rsi_average_gain, self._rsi_average_loss
                    )
            self._last_close = close
            self._count += 1
        return self._ema20, self._ema50, self._rsi


def confirmed_regime_exit(signal: SignalAnalysis, held: TargetPosition) -> bool:
    """Return whether two completed bars no longer support the held ETF."""

    if (
        signal.quality is not MarketQuality.READY
        or signal.latest is None
        or signal.previous is None
        or held not in (TargetPosition.TQQQ, TargetPosition.SQQQ)
    ):
        return False
    held_regime = (
        MarketRegime.BULLISH if held is TargetPosition.TQQQ else MarketRegime.BEARISH
    )
    return (
        signal.latest.candidate is not held_regime
        and signal.previous.candidate is not held_regime
    )


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
