"""Architecture 150 synthetic-only intraday AI research foundation.

The module deliberately owns only typed, deterministic, offline research
contracts.  It has no data acquisition, filesystem, credential, provider,
broker, or execution imports.  Real campaign data is a later, separately
reviewed custody boundary.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Context, Decimal, InvalidOperation, localcontext
from enum import IntEnum, StrEnum
from hashlib import sha256
from statistics import median
from types import MappingProxyType
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from trading_bot.experiments.arch148_intraday import (
    HistoricalIntradaySessionAuthority,
)

ARCH150_SCHEMA = "arch150-intraday-ai-research-foundation/v1"
PROGRAM_SCHEMA = "arch150-typed-intraday-program/v1"
TRIAL_LEDGER_SCHEMA = "arch150-consumed-trial-ledger/v1"
SELECTION_BIAS_SCHEMA = "arch150-selection-bias-input/v1"
REPLAY_SCHEMA = "arch150-deterministic-replay/v1"

DISCOVERY_START = date(2016, 1, 1)
DISCOVERY_END = date(2021, 1, 1)
VALIDATION_START = date(2021, 1, 1)
VALIDATION_END = date(2024, 1, 1)
HOLDOUT_START = date(2024, 1, 1)
HOLDOUT_END = date(2026, 1, 1)
RECENT_EXTENSION_START = date(2026, 1, 1)
RECENT_EXTENSION_END = date(2026, 11, 1)

INITIAL_UNIVERSE: tuple[str, ...] = ("SPY", "QQQ")
NEW_YORK = ZoneInfo("America/New_York")
_SESSION_AUTHORITY = HistoricalIntradaySessionAuthority()

G1_TOTAL_TRIAL_LIMIT = 24
G1_FAMILY_TRIAL_LIMIT = 8
VALIDATION_MIN_AVERAGE_ROUND_TRIPS = Decimal("100")
VALIDATION_MIN_ACTIVE_SESSION_FRACTION = Decimal("0.35")
VALIDATION_MAX_MEDIAN_TRADES_PER_ACTIVE_SESSION = Decimal("3")
HOLDOUT_MIN_ACTIVE_SESSION_FRACTION = Decimal("0.30")
EXTENSION_MIN_ACTIVE_SESSION_FRACTION = Decimal("0.30")
MAX_GROSS_EXPOSURE_FRACTION = Decimal("1")

ZERO_FRICTION_BPS = Decimal("0")
BASE_SLIPPAGE_BPS = Decimal("2")
STRESS_SLIPPAGE_BPS = Decimal("5")

_DECIMAL_CONTEXT = Context(prec=60)
_PROGRAM_NAMESPACE = UUID("b8eeb5f2-51ac-5c8a-9bd1-13c8f1d72f28")
_TRIAL_NAMESPACE = UUID("19ad72dd-3a0b-5dd1-b4d5-5b0af30a8df4")
_TRIAL_LEDGER_SEAL = object()
_TRADE_NAMESPACE = UUID("d1b8463f-349d-5d1d-9d1c-88a1f235122e")
_REPLAY_NAMESPACE = UUID("e22c9066-4b42-5d7f-bdb8-a0b3d62e0c13")
_FILL_NAMESPACE = UUID("0d76dd95-78fb-5fb5-93f1-0718fd6a7b9b")
_POPULATION_FREEZE_NAMESPACE = UUID("ab09fd8e-480d-5937-a238-b4fb9720437e")
_CANDIDATE_FREEZE_NAMESPACE = UUID("d463e47c-c8f8-5843-a059-7520dab589ea")
_POPULATION_FREEZE_SEAL = object()
_CANDIDATE_FREEZE_SEAL = object()
_DATASET_SEAL = object()
_FIVE_MINUTE_SEAL = object()


class Arch150Error(ValueError):
    """Base error for the closed Architecture 150 foundation contracts."""


class InformationFirewallError(Arch150Error):
    """Raised when a stage attempts to see data outside its frozen window."""


class UnsupportedProgramError(Arch150Error):
    """Raised for a program outside the closed typed grammar."""


class TrialBudgetExceeded(Arch150Error):
    """Raised when a consumed trial would exceed a frozen G1 budget."""


class StrategyFamily(StrEnum):
    NOISE_AREA_VWAP_MOMENTUM = "NOISE_AREA_VWAP_MOMENTUM"
    VWAP_TREND_REVERSAL = "VWAP_TREND_REVERSAL"
    OPENING_RANGE_BREAKOUT_REVERSAL = "OPENING_RANGE_BREAKOUT_REVERSAL"


class OpeningRangeDirection(StrEnum):
    CONTINUATION = "CONTINUATION"
    REVERSAL = "REVERSAL"


class VwapStrategyMode(StrEnum):
    CONTINUATION = "CONTINUATION"
    BOUNDED_REVERSAL = "BOUNDED_REVERSAL"


class VwapReferenceSide(StrEnum):
    ABOVE = "ABOVE"
    BELOW = "BELOW"


class BarResolution(IntEnum):
    ONE_MINUTE = 1
    FIVE_MINUTE = 5


class ResearchStage(StrEnum):
    DISCOVERY = "DISCOVERY"
    VALIDATION = "VALIDATION"
    HOLDOUT = "HOLDOUT"
    RECENT_EXTENSION = "RECENT_EXTENSION"


class CostCase(StrEnum):
    ZERO = "ZERO"
    BASE = "BASE"
    STRESS = "STRESS"


class TrialDisposition(StrEnum):
    INVALID = "INVALID"
    DUPLICATE = "DUPLICATE"
    ZERO_TRADE = "ZERO_TRADE"
    FAILED = "FAILED"
    ECONOMICALLY_REJECTED = "ECONOMICALLY_REJECTED"
    SHORTLISTED = "SHORTLISTED"


class FillSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class TradeDirection(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def _decimal(value: Decimal | str | int, field_name: str) -> Decimal:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be a Decimal-compatible number")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise TypeError(f"{field_name} must be a Decimal-compatible number") from exc
    if not result.is_finite():
        raise ValueError(f"{field_name} must be finite")
    return result


def _decimal_text(value: Decimal) -> str:
    value = _decimal(value, "value")
    if value == 0:
        return "0"
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _positive_decimal(value: Decimal | str | int, field_name: str) -> Decimal:
    result = _decimal(value, field_name)
    if result <= 0:
        raise ValueError(f"{field_name} must be positive")
    return result


def _bounded_int(value: int, field_name: str, lower: int, upper: int) -> int:
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError(f"{field_name} must be an integer in [{lower}, {upper}]")
    return value


def _payload_int(raw: Mapping[str, object], field_name: str) -> int:
    value = raw.get(field_name)
    if type(value) is not int:
        raise UnsupportedProgramError(f"{field_name} must be an integer")
    return value


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate program field")
        result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class NoiseAreaVwapMomentumProgram:
    """Closed typed representation of family A."""

    lookback_sessions: int = 5
    noise_band_bps: Decimal = Decimal("10")
    confirmation_bars: int = 2
    max_hold_minutes: int = 30

    @property
    def family(self) -> StrategyFamily:
        return StrategyFamily.NOISE_AREA_VWAP_MOMENTUM

    def __post_init__(self) -> None:
        _bounded_int(self.lookback_sessions, "lookback_sessions", 1, 20)
        _bounded_int(self.confirmation_bars, "confirmation_bars", 1, 10)
        _bounded_int(self.max_hold_minutes, "max_hold_minutes", 1, 60)
        band = _positive_decimal(self.noise_band_bps, "noise_band_bps")
        if band > Decimal("250"):
            raise ValueError("noise_band_bps must be at most 250")
        object.__setattr__(self, "noise_band_bps", band)


@dataclass(frozen=True, slots=True)
class VwapTrendReversalProgram:
    """Closed typed representation of family B."""

    displacement_bps: Decimal = Decimal("25")
    mode: VwapStrategyMode = VwapStrategyMode.CONTINUATION
    reference_side: VwapReferenceSide = VwapReferenceSide.ABOVE
    confirmation_bars: int = 2
    max_hold_minutes: int = 30
    cooldown_bars: int = 5

    @property
    def family(self) -> StrategyFamily:
        return StrategyFamily.VWAP_TREND_REVERSAL

    def __post_init__(self) -> None:
        displacement = _positive_decimal(self.displacement_bps, "displacement_bps")
        if displacement > Decimal("500"):
            raise ValueError("displacement_bps must be at most 500")
        object.__setattr__(self, "displacement_bps", displacement)
        _bounded_int(self.confirmation_bars, "confirmation_bars", 1, 10)
        if type(self.mode) is not VwapStrategyMode:
            raise TypeError("mode must be a VwapStrategyMode")
        if type(self.reference_side) is not VwapReferenceSide:
            raise TypeError("reference_side must be a VwapReferenceSide")
        _bounded_int(self.max_hold_minutes, "max_hold_minutes", 1, 60)
        _bounded_int(self.cooldown_bars, "cooldown_bars", 0, 30)


@dataclass(frozen=True, slots=True)
class OpeningRangeBreakoutReversalProgram:
    """Closed early-session breakout/reversal grammar for family C.

    The grammar has a bounded hold and no late-session exit selector.  This is
    intentional: Architecture-148's first-half-hour-to-last-half-hour rule is
    not expressible by this type.
    """

    opening_range_minutes: int = 30
    direction: OpeningRangeDirection = OpeningRangeDirection.CONTINUATION
    entry_delay_bars: int = 1
    max_hold_minutes: int = 30

    @property
    def family(self) -> StrategyFamily:
        return StrategyFamily.OPENING_RANGE_BREAKOUT_REVERSAL

    def __post_init__(self) -> None:
        if self.opening_range_minutes not in (5, 15, 30):
            raise ValueError("opening_range_minutes must be 5, 15, or 30")
        if type(self.direction) is not OpeningRangeDirection:
            raise TypeError("direction must be an OpeningRangeDirection")
        _bounded_int(self.entry_delay_bars, "entry_delay_bars", 0, 30)
        _bounded_int(self.max_hold_minutes, "max_hold_minutes", 1, 60)


type IntradayProgram = (
    NoiseAreaVwapMomentumProgram
    | VwapTrendReversalProgram
    | OpeningRangeBreakoutReversalProgram
)


def _program_dict(program: IntradayProgram) -> dict[str, object]:
    if type(program) is NoiseAreaVwapMomentumProgram:
        return {
            "schema": PROGRAM_SCHEMA,
            "family": program.family.value,
            "lookback_sessions": program.lookback_sessions,
            "noise_band_bps": _decimal_text(program.noise_band_bps),
            "confirmation_bars": program.confirmation_bars,
            "max_hold_minutes": program.max_hold_minutes,
        }
    if type(program) is VwapTrendReversalProgram:
        return {
            "schema": PROGRAM_SCHEMA,
            "family": program.family.value,
            "displacement_bps": _decimal_text(program.displacement_bps),
            "mode": program.mode.value,
            "reference_side": program.reference_side.value,
            "confirmation_bars": program.confirmation_bars,
            "max_hold_minutes": program.max_hold_minutes,
            "cooldown_bars": program.cooldown_bars,
        }
    if type(program) is OpeningRangeBreakoutReversalProgram:
        return {
            "schema": PROGRAM_SCHEMA,
            "family": program.family.value,
            "opening_range_minutes": program.opening_range_minutes,
            "direction": program.direction.value,
            "entry_delay_bars": program.entry_delay_bars,
            "max_hold_minutes": program.max_hold_minutes,
        }
    raise UnsupportedProgramError(
        "program must use the closed Architecture 150 grammar"
    )


def program_fingerprint(program: IntradayProgram) -> str:
    """Return the stable semantic fingerprint of a typed program."""

    return sha256(_canonical_json(_program_dict(program))).hexdigest()


def program_id(program: IntradayProgram) -> UUID:
    return uuid5(_PROGRAM_NAMESPACE, f"{PROGRAM_SCHEMA}:{program_fingerprint(program)}")


def program_to_bytes(program: IntradayProgram) -> bytes:
    return _canonical_json(_program_dict(program))


def program_from_bytes(payload: bytes) -> IntradayProgram:
    try:
        raw = json.loads(
            payload.decode("utf-8"), object_pairs_hook=_reject_duplicate_pairs
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise UnsupportedProgramError("program payload is not canonical JSON") from exc
    if not isinstance(raw, dict):
        raise UnsupportedProgramError("program payload must be an object")
    allowed = {
        "schema",
        "family",
        "lookback_sessions",
        "noise_band_bps",
        "confirmation_bars",
        "max_hold_minutes",
        "displacement_bps",
        "mode",
        "reference_side",
        "cooldown_bars",
        "opening_range_minutes",
        "direction",
        "entry_delay_bars",
    }
    if set(raw) - allowed or raw.get("schema") != PROGRAM_SCHEMA:
        raise UnsupportedProgramError("unknown or missing typed program fields")
    family = raw.get("family")
    try:
        if family == StrategyFamily.NOISE_AREA_VWAP_MOMENTUM.value:
            expected = {
                "schema",
                "family",
                "lookback_sessions",
                "noise_band_bps",
                "confirmation_bars",
                "max_hold_minutes",
            }
            if set(raw) != expected:
                raise UnsupportedProgramError(
                    "noise-area program fields are incomplete"
                )
            return NoiseAreaVwapMomentumProgram(
                _payload_int(raw, "lookback_sessions"),
                Decimal(str(raw["noise_band_bps"])),
                _payload_int(raw, "confirmation_bars"),
                _payload_int(raw, "max_hold_minutes"),
            )
        if family == StrategyFamily.VWAP_TREND_REVERSAL.value:
            expected = {
                "schema",
                "family",
                "displacement_bps",
                "mode",
                "reference_side",
                "confirmation_bars",
                "max_hold_minutes",
                "cooldown_bars",
            }
            if set(raw) != expected:
                raise UnsupportedProgramError("VWAP program fields are incomplete")
            return VwapTrendReversalProgram(
                Decimal(str(raw["displacement_bps"])),
                VwapStrategyMode(str(raw["mode"])),
                VwapReferenceSide(str(raw["reference_side"])),
                _payload_int(raw, "confirmation_bars"),
                _payload_int(raw, "max_hold_minutes"),
                _payload_int(raw, "cooldown_bars"),
            )
        if family == StrategyFamily.OPENING_RANGE_BREAKOUT_REVERSAL.value:
            expected = {
                "schema",
                "family",
                "opening_range_minutes",
                "direction",
                "entry_delay_bars",
                "max_hold_minutes",
            }
            if set(raw) != expected:
                raise UnsupportedProgramError(
                    "opening-range program fields are incomplete"
                )
            return OpeningRangeBreakoutReversalProgram(
                _payload_int(raw, "opening_range_minutes"),
                OpeningRangeDirection(str(raw["direction"])),
                _payload_int(raw, "entry_delay_bars"),
                _payload_int(raw, "max_hold_minutes"),
            )
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        raise UnsupportedProgramError("invalid typed program") from exc
    raise UnsupportedProgramError("strategy family is not in the closed grammar")


@dataclass(frozen=True, slots=True)
class IntradayBar:
    """One explicitly resolved synthetic-or-custodied OHLCV bar."""

    symbol: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    resolution: BarResolution = BarResolution.ONE_MINUTE

    def __post_init__(self) -> None:
        if self.symbol not in INITIAL_UNIVERSE:
            raise Arch150Error("symbol is outside the frozen SPY/QQQ universe")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise TypeError("timestamp must be timezone-aware")
        if type(self.resolution) is not BarResolution:
            raise TypeError("resolution must be a BarResolution")
        object.__setattr__(self, "timestamp", self.timestamp.astimezone(UTC))
        values = {
            field_name: _positive_decimal(getattr(self, field_name), field_name)
            for field_name in ("open", "high", "low", "close")
        }
        if values["high"] < max(values["open"], values["low"], values["close"]):
            raise ValueError("high must be the greatest OHLC value")
        if values["low"] > min(values["open"], values["high"], values["close"]):
            raise ValueError("low must be the least OHLC value")
        for field_name, value in values.items():
            object.__setattr__(self, field_name, value)
        if type(self.volume) is not int or self.volume < 0:
            raise ValueError("volume must be a nonnegative integer")

    @property
    def local_timestamp(self) -> datetime:
        return self.timestamp.astimezone(NEW_YORK)

    @property
    def session_date(self) -> date:
        return self.local_timestamp.date()


@dataclass(frozen=True, slots=True)
class ValidatedMinuteBars:
    symbol: str
    bars: tuple[IntradayBar, ...]
    sessions: tuple[date, ...]
    input_digest: str


class IncompleteFiveMinuteAggregation(Arch150Error):
    """A source range contains a missing or partial five-minute bucket."""


@dataclass(frozen=True, slots=True, init=False)
class DerivedFiveMinuteBars:
    """An explicitly derived five-minute view that cannot masquerade as 1m input."""

    symbol: str
    bars: tuple[IntradayBar, ...]
    sessions: tuple[date, ...]
    source_digest: str
    input_digest: str
    _authority_seal: object = field(repr=False, compare=False)

    def __init__(
        self,
        symbol: str,
        bars: tuple[IntradayBar, ...],
        sessions: tuple[date, ...],
        source_digest: str,
        input_digest: str,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _FIVE_MINUTE_SEAL:
            raise Arch150Error("five-minute streams must come from exact aggregation")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "bars", bars)
        object.__setattr__(self, "sessions", sessions)
        object.__setattr__(self, "source_digest", source_digest)
        object.__setattr__(self, "input_digest", input_digest)
        object.__setattr__(self, "_authority_seal", _seal)

    def __len__(self) -> int:
        return len(self.bars)

    def __iter__(self):
        return iter(self.bars)

    def __getitem__(self, index):
        return self.bars[index]


def _validate_bar_chronology(bars: Sequence[IntradayBar], symbol: str) -> None:
    previous: datetime | None = None
    for bar in bars:
        if type(bar) is not IntradayBar or bar.symbol != symbol:
            raise Arch150Error("all bars must be exact typed bars for one symbol")
        if bar.resolution is not BarResolution.ONE_MINUTE:
            raise Arch150Error("validated minute input must have 1-minute resolution")
        local = bar.local_timestamp
        if local.second or local.microsecond:
            raise Arch150Error("one-minute bars must start on an exact minute")
        try:
            schedule = _SESSION_AUTHORITY.schedule_for(bar.session_date)
        except (TypeError, ValueError) as exc:
            raise Arch150Error(
                "bar date is outside the accepted XNYS authority"
            ) from exc
        if schedule is None:
            raise Arch150Error("bar date is not a published regular XNYS session")
        bar_end = bar.timestamp + timedelta(minutes=BarResolution.ONE_MINUTE)
        if not schedule.opens_at <= bar.timestamp or bar_end > schedule.closes_at:
            raise Arch150Error("bar is outside the published regular XNYS session")
        if previous is not None and bar.timestamp <= previous:
            raise Arch150Error("bars must be strictly chronological and unique")
        previous = bar.timestamp


def _bar_material(bar: IntradayBar) -> dict[str, object]:
    return {
        "symbol": bar.symbol,
        "timestamp": bar.timestamp.isoformat().replace("+00:00", "Z"),
        "open": _decimal_text(bar.open),
        "high": _decimal_text(bar.high),
        "low": _decimal_text(bar.low),
        "close": _decimal_text(bar.close),
        "volume": bar.volume,
        "resolution_minutes": int(bar.resolution),
    }


def validate_1_minute_bars(
    bars: Iterable[IntradayBar], *, symbol: str | None = None
) -> ValidatedMinuteBars:
    materialized = tuple(bars)
    if not materialized:
        raise Arch150Error("at least one one-minute bar is required")
    actual_symbol = materialized[0].symbol
    if symbol is not None and symbol != actual_symbol:
        raise Arch150Error("requested symbol does not match the bars")
    _validate_bar_chronology(materialized, actual_symbol)
    sessions = tuple(dict.fromkeys(bar.session_date for bar in materialized))
    digest = sha256(
        _canonical_json([_bar_material(bar) for bar in materialized])
    ).hexdigest()
    return ValidatedMinuteBars(actual_symbol, materialized, sessions, digest)


@dataclass(frozen=True, slots=True)
class ValidatedUniverseBars:
    by_symbol: Mapping[str, ValidatedMinuteBars]
    input_digest: str


def validate_universe_minute_bars(bars: Iterable[IntradayBar]) -> ValidatedUniverseBars:
    grouped: dict[str, list[IntradayBar]] = defaultdict(list)
    for bar in bars:
        if type(bar) is not IntradayBar:
            raise Arch150Error("universe input must contain exact typed bars")
        grouped[bar.symbol].append(bar)
    if tuple(grouped) != INITIAL_UNIVERSE:
        raise Arch150Error("the initial universe is exactly SPY then QQQ")
    validated = {
        symbol: validate_1_minute_bars(grouped[symbol], symbol=symbol)
        for symbol in INITIAL_UNIVERSE
    }
    digest = sha256(
        _canonical_json(
            {
                symbol: [_bar_material(bar) for bar in validated[symbol].bars]
                for symbol in INITIAL_UNIVERSE
            }
        )
    ).hexdigest()
    return ValidatedUniverseBars(MappingProxyType(validated), digest)


def aggregate_five_minute_bars(
    bars: ValidatedMinuteBars | Iterable[IntradayBar],
) -> DerivedFiveMinuteBars:
    validated = validate_1_minute_bars(
        bars.bars if type(bars) is ValidatedMinuteBars else bars,
        symbol=bars.symbol if type(bars) is ValidatedMinuteBars else None,
    )
    groups: dict[tuple[date, int], list[IntradayBar]] = defaultdict(list)
    session_open: dict[date, datetime] = {}
    for bar in validated.bars:
        schedule = _SESSION_AUTHORITY.schedule_for(bar.session_date)
        if schedule is None:
            raise Arch150Error("bar date is not a published regular XNYS session")
        session_open[bar.session_date] = schedule.opens_at
        elapsed = bar.timestamp - schedule.opens_at
        elapsed_minutes = int(elapsed.total_seconds() // 60)
        if elapsed.total_seconds() != elapsed_minutes * 60:
            raise Arch150Error("one-minute bars must align to XNYS session minutes")
        slot = elapsed_minutes // int(BarResolution.FIVE_MINUTE)
        groups[(bar.session_date, slot)].append(bar)
    for session in session_open:
        session_values = [bar for bar in validated.bars if bar.session_date == session]
        if any(
            right.timestamp - left.timestamp != timedelta(minutes=1)
            for left, right in zip(session_values, session_values[1:], strict=False)
        ):
            raise IncompleteFiveMinuteAggregation(
                "source minutes are not consecutive within a session range"
            )
    result: list[IntradayBar] = []
    for key in sorted(groups):
        group = groups[key]
        expected_open = session_open[key[0]] + timedelta(
            minutes=key[1] * int(BarResolution.FIVE_MINUTE)
        )
        if len(group) != int(BarResolution.FIVE_MINUTE) or any(
            bar.timestamp != expected_open + timedelta(minutes=offset)
            for offset, bar in enumerate(group)
        ):
            raise IncompleteFiveMinuteAggregation(
                "a derived five-minute bucket requires all five aligned source minutes"
            )
        result.append(
            IntradayBar(
                validated.symbol,
                group[0].timestamp,
                group[0].open,
                max(bar.high for bar in group),
                min(bar.low for bar in group),
                group[-1].close,
                sum(bar.volume for bar in group),
                BarResolution.FIVE_MINUTE,
            )
        )
    aggregated = tuple(result)
    digest = sha256(
        _canonical_json([_bar_material(bar) for bar in aggregated])
    ).hexdigest()
    return DerivedFiveMinuteBars(
        validated.symbol,
        aggregated,
        tuple(dict.fromkeys(bar.session_date for bar in aggregated)),
        validated.input_digest,
        digest,
        _seal=_FIVE_MINUTE_SEAL,
    )


def _validate_derived_five_minute_bars(
    bars: DerivedFiveMinuteBars,
) -> tuple[IntradayBar, ...]:
    if (
        type(bars) is not DerivedFiveMinuteBars
        or bars._authority_seal is not _FIVE_MINUTE_SEAL
    ):
        raise Arch150Error("five-minute input must come from the exact aggregator")
    if not bars.bars or len(bars.source_digest) != 64:
        raise Arch150Error("derived five-minute stream commitment is incomplete")
    previous: datetime | None = None
    for bar in bars.bars:
        if (
            type(bar) is not IntradayBar
            or bar.resolution is not BarResolution.FIVE_MINUTE
        ):
            raise Arch150Error("derived input must retain five-minute resolution")
        schedule = _SESSION_AUTHORITY.schedule_for(bar.session_date)
        if schedule is None:
            raise Arch150Error("derived bar date is not a published XNYS session")
        elapsed = bar.timestamp - schedule.opens_at
        if (
            elapsed.total_seconds() < 0
            or elapsed.total_seconds() % (5 * 60) != 0
            or bar.timestamp + timedelta(minutes=5) > schedule.closes_at
        ):
            raise Arch150Error("derived bar is not aligned inside its XNYS session")
        if previous is not None and bar.timestamp <= previous:
            raise Arch150Error("derived bars must be strictly chronological")
        previous = bar.timestamp
    digest = sha256(
        _canonical_json([_bar_material(bar) for bar in bars.bars])
    ).hexdigest()
    if digest != bars.input_digest:
        raise Arch150Error("derived five-minute digest does not match its bars")
    sessions = tuple(dict.fromkeys(bar.session_date for bar in bars.bars))
    if sessions != bars.sessions:
        raise Arch150Error("derived five-minute session index does not match its bars")
    return bars.bars


@dataclass(frozen=True, slots=True, init=False)
class DiscoveryPopulationFreeze:
    """Immutable proof that the complete discovery trial population was frozen."""

    freeze_id: UUID
    discovery_dataset_id: UUID
    ledger_id: UUID
    trial_ids: tuple[UUID, ...]
    semantic_fingerprints: tuple[str, ...]
    program_ids: tuple[UUID, ...]
    _authority_seal: object = field(repr=False, compare=False)

    def __init__(
        self,
        freeze_id: UUID,
        discovery_dataset_id: UUID,
        ledger_id: UUID,
        trial_ids: tuple[UUID, ...],
        semantic_fingerprints: tuple[str, ...],
        program_ids: tuple[UUID, ...],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _POPULATION_FREEZE_SEAL:
            raise InformationFirewallError(
                "discovery population freezes must come from the freeze authority"
            )
        for name, value in (
            ("freeze_id", freeze_id),
            ("discovery_dataset_id", discovery_dataset_id),
            ("ledger_id", ledger_id),
            ("trial_ids", trial_ids),
            ("semantic_fingerprints", semantic_fingerprints),
            ("program_ids", program_ids),
        ):
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_authority_seal", _seal)


@dataclass(frozen=True, slots=True, init=False)
class CandidateFreeze:
    """Immutable validation authorization bound to one frozen G1 population."""

    freeze_id: UUID
    population_freeze_id: UUID
    discovery_dataset_id: UUID
    ledger_id: UUID
    candidate_program_ids: tuple[UUID, ...]
    candidate_fingerprints: tuple[str, ...]
    _authority_seal: object = field(repr=False, compare=False)

    def __init__(
        self,
        freeze_id: UUID,
        population_freeze_id: UUID,
        discovery_dataset_id: UUID,
        ledger_id: UUID,
        candidate_program_ids: tuple[UUID, ...],
        candidate_fingerprints: tuple[str, ...],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _CANDIDATE_FREEZE_SEAL:
            raise InformationFirewallError(
                "candidate freezes must come from the frozen discovery population"
            )
        for name, value in (
            ("freeze_id", freeze_id),
            ("population_freeze_id", population_freeze_id),
            ("discovery_dataset_id", discovery_dataset_id),
            ("ledger_id", ledger_id),
            ("candidate_program_ids", candidate_program_ids),
            ("candidate_fingerprints", candidate_fingerprints),
        ):
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_authority_seal", _seal)


@dataclass(frozen=True, slots=True, init=False)
class ResearchDataset:
    stage: ResearchStage
    bars: ValidatedUniverseBars
    start: date
    end_exclusive: date
    candidate_freeze: CandidateFreeze | None
    _authority_seal: object = field(repr=False, compare=False)

    def __init__(
        self,
        stage: ResearchStage,
        bars: ValidatedUniverseBars,
        start: date,
        end_exclusive: date,
        candidate_freeze: CandidateFreeze | None = None,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _DATASET_SEAL:
            raise InformationFirewallError(
                "research datasets must be opened through stage authority"
            )
        if stage not in (ResearchStage.DISCOVERY, ResearchStage.VALIDATION):
            raise InformationFirewallError(f"{stage.value} remains sealed")
        expected_window = _stage_window(stage)
        if (start, end_exclusive) != expected_window:
            raise InformationFirewallError("dataset window differs from frozen stage")
        if stage is ResearchStage.VALIDATION and not _candidate_freeze_is_valid(
            candidate_freeze
        ):
            raise InformationFirewallError(
                "validation requires an immutable candidate-freeze authorization"
            )
        if stage is ResearchStage.DISCOVERY and candidate_freeze is not None:
            raise InformationFirewallError(
                "discovery cannot be opened with a validation candidate freeze"
            )
        for name, value in (
            ("stage", stage),
            ("bars", bars),
            ("start", start),
            ("end_exclusive", end_exclusive),
            ("candidate_freeze", candidate_freeze),
        ):
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_authority_seal", _seal)

    @property
    def candidate_program_ids(self) -> tuple[UUID, ...]:
        if self.candidate_freeze is None:
            return ()
        return self.candidate_freeze.candidate_program_ids


def _stage_window(stage: ResearchStage) -> tuple[date, date]:
    if stage is ResearchStage.DISCOVERY:
        return DISCOVERY_START, DISCOVERY_END
    if stage is ResearchStage.VALIDATION:
        return VALIDATION_START, VALIDATION_END
    if stage is ResearchStage.HOLDOUT:
        return HOLDOUT_START, HOLDOUT_END
    return RECENT_EXTENSION_START, RECENT_EXTENSION_END


def _candidate_freeze_is_valid(value: CandidateFreeze | None) -> bool:
    if not (
        type(value) is CandidateFreeze
        and value._authority_seal is _CANDIDATE_FREEZE_SEAL
        and bool(value.candidate_program_ids)
        and len(value.candidate_program_ids) == len(value.candidate_fingerprints)
    ):
        return False
    material = {
        "population_freeze_id": str(value.population_freeze_id),
        "discovery_dataset_id": str(value.discovery_dataset_id),
        "ledger_id": str(value.ledger_id),
        "candidate_program_ids": [str(item) for item in value.candidate_program_ids],
        "candidate_fingerprints": list(value.candidate_fingerprints),
    }
    expected = uuid5(_CANDIDATE_FREEZE_NAMESPACE, _canonical_json(material).decode())
    return value.freeze_id == expected


def _open_dataset(
    stage: ResearchStage,
    bars: Iterable[IntradayBar],
    candidate_freeze: CandidateFreeze | None = None,
) -> ResearchDataset:
    if stage in (ResearchStage.HOLDOUT, ResearchStage.RECENT_EXTENSION):
        raise InformationFirewallError(
            f"{stage.value} is sealed until a later authorized campaign stage"
        )
    if stage not in (ResearchStage.DISCOVERY, ResearchStage.VALIDATION):
        raise InformationFirewallError("unknown research stage")
    if stage is ResearchStage.VALIDATION and not _candidate_freeze_is_valid(
        candidate_freeze
    ):
        raise InformationFirewallError(
            "validation requires an immutable candidate-freeze authorization"
        )
    if stage is ResearchStage.DISCOVERY and candidate_freeze is not None:
        raise InformationFirewallError("discovery cannot use a candidate freeze")
    start, end = _stage_window(stage)
    materialized = tuple(bars)
    if not materialized:
        raise Arch150Error("at least one one-minute bar is required")
    if any(
        type(bar) is not IntradayBar or not (start <= bar.session_date < end)
        for bar in materialized
    ):
        raise InformationFirewallError(f"bars fall outside the {stage.value} window")
    dataset = validate_universe_minute_bars(materialized)
    return ResearchDataset(
        stage,
        dataset,
        start,
        end,
        candidate_freeze,
        _seal=_DATASET_SEAL,
    )


def open_discovery_dataset(bars: Iterable[IntradayBar]) -> ResearchDataset:
    return _open_dataset(ResearchStage.DISCOVERY, bars)


def open_validation_dataset(
    bars: Iterable[IntradayBar],
    candidate_freeze: CandidateFreeze | None = None,
) -> ResearchDataset:
    return _open_dataset(ResearchStage.VALIDATION, bars, candidate_freeze)


def open_holdout_dataset(bars: Iterable[IntradayBar]) -> ResearchDataset:
    del bars
    raise InformationFirewallError("2024-2025 holdout access is sealed")


def open_recent_extension_dataset(bars: Iterable[IntradayBar]) -> ResearchDataset:
    del bars
    raise InformationFirewallError("Jan-Oct 2026 extension access is sealed")


@dataclass(frozen=True, slots=True)
class CostModel:
    case: CostCase
    adverse_slippage_bps: Decimal
    commission_per_fill: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if self.commission_per_fill != 0:
            raise ValueError("Architecture 150 commission is frozen at zero")
        expected = {
            CostCase.ZERO: ZERO_FRICTION_BPS,
            CostCase.BASE: BASE_SLIPPAGE_BPS,
            CostCase.STRESS: STRESS_SLIPPAGE_BPS,
        }[self.case]
        if self.adverse_slippage_bps != expected:
            raise ValueError("cost case has the wrong frozen slippage")


ZERO_COST = CostModel(CostCase.ZERO, ZERO_FRICTION_BPS)
BASE_COST = CostModel(CostCase.BASE, BASE_SLIPPAGE_BPS)
STRESS_COST = CostModel(CostCase.STRESS, STRESS_SLIPPAGE_BPS)


def cost_model(case: CostCase) -> CostModel:
    return {
        CostCase.ZERO: ZERO_COST,
        CostCase.BASE: BASE_COST,
        CostCase.STRESS: STRESS_COST,
    }[case]


def _coerce_cost_model(case: CostCase | CostModel) -> CostModel:
    return case if isinstance(case, CostModel) else cost_model(case)


@dataclass(frozen=True, slots=True)
class Fill:
    fill_id: UUID
    side: FillSide
    timestamp: datetime
    reference_price: Decimal
    execution_price: Decimal
    quantity: Decimal
    slippage_bps: Decimal


@dataclass(frozen=True, slots=True)
class Trade:
    trade_id: UUID
    symbol: str
    session: date
    entry: Fill
    exit: Fill
    direction: TradeDirection
    net_pnl: Decimal
    equity_before: Decimal
    equity_after: Decimal
    gross_exposure_fraction: Decimal


@dataclass(frozen=True, slots=True)
class ReplayResult:
    replay_id: UUID
    program_id: UUID
    cost_case: CostCase
    trades: tuple[Trade, ...]
    net_pnl: Decimal
    initial_equity: Decimal
    final_equity: Decimal
    maximum_gross_exposure: Decimal
    input_digest: str
    equity_digest: str

    @property
    def completed_round_trips(self) -> int:
        return len(self.trades)

    @property
    def zero_friction_can_qualify(self) -> bool:
        return self.cost_case is not CostCase.ZERO


def _vwap_through(bars: Sequence[IntradayBar], index: int) -> Decimal:
    """Compute VWAP through the current completed bar, never using a future bar."""

    with localcontext(_DECIMAL_CONTEXT):
        visible = bars[: index + 1]
        volume = sum(bar.volume for bar in visible)
        if volume == 0:
            return bars[index].close
        return sum(
            ((bar.high + bar.low + bar.close) / Decimal("3")) * bar.volume
            for bar in visible
        ) / Decimal(volume)


def _bar_offset_minutes(bar: IntradayBar) -> int:
    schedule = _SESSION_AUTHORITY.schedule_for(bar.session_date)
    if schedule is None:
        raise Arch150Error("bar date is not a published regular XNYS session")
    return int((bar.timestamp - schedule.opens_at).total_seconds() // 60)


def _lagged_noise_band_bps(
    program: NoiseAreaVwapMomentumProgram,
    current_session: date,
    offset_minutes: int,
    prior_sessions: Mapping[date, Sequence[IntradayBar]],
) -> Decimal | None:
    published_sessions = _SESSION_AUTHORITY.published.sessions
    earlier_dates = tuple(day for day in published_sessions if day < current_session)
    if len(earlier_dates) < program.lookback_sessions:
        return None
    selected = earlier_dates[-program.lookback_sessions :]
    if any(day not in prior_sessions for day in selected):
        return None
    deviations: list[Decimal] = []
    with localcontext(_DECIMAL_CONTEXT):
        for day in selected:
            prior_bars = prior_sessions[day]
            matching = next(
                (
                    index
                    for index, bar in enumerate(prior_bars)
                    if _bar_offset_minutes(bar) == offset_minutes
                ),
                None,
            )
            if matching is None:
                return None
            prior_close = prior_bars[matching].close
            prior_vwap = _vwap_through(prior_bars, matching)
            deviations.append(
                abs(prior_close - prior_vwap) / prior_vwap * Decimal("10000")
            )
        # noise_band_bps is a minimum width; the realized width comes only from
        # the immediately preceding sessions at this exact session offset.
        historical_width = sum(deviations, Decimal("0")) / Decimal(len(deviations))
        return max(program.noise_band_bps, historical_width)


def _a_signal_at(
    program: NoiseAreaVwapMomentumProgram,
    bars: Sequence[IntradayBar],
    index: int,
    current_session: date,
    prior_sessions: Mapping[date, Sequence[IntradayBar]],
) -> TradeDirection | None:
    noise_band = _lagged_noise_band_bps(
        program, current_session, _bar_offset_minutes(bars[index]), prior_sessions
    )
    if noise_band is None:
        return None
    vwap = _vwap_through(bars, index)
    with localcontext(_DECIMAL_CONTEXT):
        scale = noise_band / Decimal("10000")
        if bars[index].close > vwap * (Decimal("1") + scale):
            return TradeDirection.LONG
        if bars[index].close < vwap * (Decimal("1") - scale):
            return TradeDirection.SHORT
    return None


def _b_signal_at(
    program: VwapTrendReversalProgram,
    bars: Sequence[IntradayBar],
    index: int,
) -> TradeDirection | None:
    vwap = _vwap_through(bars, index)
    with localcontext(_DECIMAL_CONTEXT):
        displacement = program.displacement_bps / Decimal("10000")
        current = bars[index].close
        if program.reference_side is VwapReferenceSide.ABOVE:
            if current < vwap * (Decimal("1") + displacement):
                return None
            return (
                TradeDirection.LONG
                if program.mode is VwapStrategyMode.CONTINUATION
                else TradeDirection.SHORT
            )
        if current > vwap * (Decimal("1") - displacement):
            return None
        return (
            TradeDirection.SHORT
            if program.mode is VwapStrategyMode.CONTINUATION
            else TradeDirection.LONG
        )


def _opening_range_signal(
    program: OpeningRangeBreakoutReversalProgram,
    bars: Sequence[IntradayBar],
    index: int,
    resolution: BarResolution,
) -> TradeDirection | None:
    if program.opening_range_minutes % int(resolution):
        raise Arch150Error("opening range must align to the selected bar resolution")
    if not bars or _bar_offset_minutes(bars[0]) != 0:
        return None
    entry_offset = program.opening_range_minutes + program.entry_delay_bars * int(
        resolution
    )
    if _bar_offset_minutes(bars[index]) < entry_offset:
        return None
    range_count = program.opening_range_minutes // int(resolution)
    opening = bars[:range_count]
    if len(opening) != range_count or any(
        _bar_offset_minutes(value) != offset * int(resolution)
        for offset, value in enumerate(opening)
    ):
        return None
    high = max(value.high for value in opening)
    low = min(value.low for value in opening)
    if bars[index].close > high:
        return (
            TradeDirection.LONG
            if program.direction is OpeningRangeDirection.CONTINUATION
            else TradeDirection.SHORT
        )
    if bars[index].close < low:
        return (
            TradeDirection.SHORT
            if program.direction is OpeningRangeDirection.CONTINUATION
            else TradeDirection.LONG
        )
    return None


def _entry_signal(
    program: IntradayProgram,
    bars: Sequence[IntradayBar],
    index: int,
    current_session: date,
    prior_sessions: Mapping[date, Sequence[IntradayBar]],
    resolution: BarResolution,
) -> TradeDirection | None:
    if type(program) is OpeningRangeBreakoutReversalProgram:
        return _opening_range_signal(program, bars, index, resolution)
    confirmation = program.confirmation_bars
    if index + 1 < confirmation:
        return None
    first_index = index - confirmation + 1
    if any(
        bars[right].timestamp - bars[left].timestamp
        != timedelta(minutes=int(resolution))
        for left, right in zip(
            range(first_index, index),
            range(first_index + 1, index + 1),
            strict=True,
        )
    ):
        return None
    observed: list[TradeDirection | None] = []
    for current_index in range(first_index, index + 1):
        if type(program) is NoiseAreaVwapMomentumProgram:
            observed.append(
                _a_signal_at(
                    program,
                    bars,
                    current_index,
                    current_session,
                    prior_sessions,
                )
            )
        elif type(program) is VwapTrendReversalProgram:
            observed.append(_b_signal_at(program, bars, current_index))
        else:
            raise UnsupportedProgramError("program is outside the closed grammar")
    signal = observed[-1]
    return (
        signal
        if signal is not None and all(item is signal for item in observed)
        else None
    )


def _max_hold_minutes(program: IntradayProgram) -> int:
    if type(program) in (
        NoiseAreaVwapMomentumProgram,
        VwapTrendReversalProgram,
        OpeningRangeBreakoutReversalProgram,
    ):
        return program.max_hold_minutes
    raise UnsupportedProgramError("program is outside the closed grammar")


def _execution_price(reference: Decimal, side: FillSide, model: CostModel) -> Decimal:
    with localcontext(_DECIMAL_CONTEXT):
        friction = model.adverse_slippage_bps / Decimal("10000")
        if side is FillSide.BUY:
            return reference * (Decimal("1") + friction)
        return reference * (Decimal("1") - friction)


def _fill(
    trade_material: str,
    side: FillSide,
    bar: IntradayBar,
    reference: Decimal,
    quantity: Decimal,
    model: CostModel,
) -> Fill:
    execution = _execution_price(reference, side, model)
    filled_at = bar.timestamp + timedelta(minutes=int(bar.resolution))
    fill_id = uuid5(
        _FILL_NAMESPACE,
        f"{REPLAY_SCHEMA}:{trade_material}:{side.value}:{filled_at.isoformat()}",
    )
    return Fill(
        fill_id,
        side,
        filled_at,
        reference,
        execution,
        quantity,
        model.adverse_slippage_bps,
    )


def replay_program(
    program: IntradayProgram,
    bars: ValidatedMinuteBars | DerivedFiveMinuteBars | Iterable[IntradayBar],
    *,
    cost_case: CostCase | CostModel = CostCase.STRESS,
    initial_equity: Decimal = Decimal("1"),
) -> ReplayResult:
    """Replay a typed program over supplied offline bars with session-flat rules."""

    if type(program) not in (
        NoiseAreaVwapMomentumProgram,
        VwapTrendReversalProgram,
        OpeningRangeBreakoutReversalProgram,
    ):
        raise UnsupportedProgramError("replay accepts only the closed typed grammar")
    if type(bars) is DerivedFiveMinuteBars:
        validated_bars = _validate_derived_five_minute_bars(bars)
        symbol = bars.symbol
        input_digest = bars.input_digest
        resolution = BarResolution.FIVE_MINUTE
    else:
        validated = validate_1_minute_bars(
            bars.bars if type(bars) is ValidatedMinuteBars else bars,
            symbol=bars.symbol if type(bars) is ValidatedMinuteBars else None,
        )
        validated_bars = validated.bars
        symbol = validated.symbol
        input_digest = validated.input_digest
        resolution = BarResolution.ONE_MINUTE
    starting_equity = _positive_decimal(initial_equity, "initial_equity")
    hold_minutes = _max_hold_minutes(program)
    if hold_minutes % int(resolution):
        raise Arch150Error("hold duration must align to the selected bar resolution")
    if type(
        program
    ) is OpeningRangeBreakoutReversalProgram and program.opening_range_minutes % int(
        resolution
    ):
        raise Arch150Error("opening range must align to the selected bar resolution")
    equity = starting_equity
    model = _coerce_cost_model(cost_case)
    result_cost_case = model.case
    grouped: dict[date, list[IntradayBar]] = defaultdict(list)
    for bar in validated_bars:
        grouped[bar.session_date].append(bar)
    prior_sessions: dict[date, Sequence[IntradayBar]] = {}
    trades: list[Trade] = []
    maximum_gross_exposure = Decimal("0")
    for session in sorted(grouped):
        session_bars = grouped[session]
        earliest_entry = 0
        trade_ordinal = 0
        while earliest_entry < len(session_bars) and equity > 0:
            entry_index: int | None = None
            direction: TradeDirection | None = None
            for index in range(earliest_entry, len(session_bars) - 1):
                signal = _entry_signal(
                    program,
                    session_bars,
                    index,
                    session,
                    prior_sessions,
                    resolution,
                )
                if signal is not None:
                    entry_index = index
                    direction = signal
                    break
            if entry_index is None or direction is None:
                break

            entry_bar = session_bars[entry_index]
            entry_side = (
                FillSide.BUY if direction is TradeDirection.LONG else FillSide.SELL
            )
            exit_side = (
                FillSide.SELL if direction is TradeDirection.LONG else FillSide.BUY
            )
            equity_before = equity
            with localcontext(_DECIMAL_CONTEXT):
                entry_price = _execution_price(entry_bar.close, entry_side, model)
                quantity = equity_before / entry_price
                with localcontext(Context(prec=120)):
                    if entry_price * quantity > equity_before:
                        quantity = quantity.next_minus(_DECIMAL_CONTEXT)
                gross_exposure = abs(entry_price * quantity) / equity_before
            if gross_exposure > MAX_GROSS_EXPOSURE_FRACTION:
                raise Arch150Error(
                    "entry gross exposure exceeds current portfolio equity"
                )
            entry_material = (
                f"{program_id(program)}:{symbol}:{session.isoformat()}:{trade_ordinal}:"
                f"{direction.value}:{entry_index}"
            )
            entry = _fill(
                entry_material,
                entry_side,
                entry_bar,
                entry_bar.close,
                quantity,
                model,
            )
            target_exit_at = entry.timestamp + timedelta(minutes=hold_minutes)
            exit_index = len(session_bars) - 1
            for candidate_index in range(entry_index + 1, len(session_bars)):
                candidate = session_bars[candidate_index]
                candidate_vwap = _vwap_through(session_bars, candidate_index)
                should_exit = False
                if type(program) is VwapTrendReversalProgram:
                    if program.mode is VwapStrategyMode.BOUNDED_REVERSAL:
                        should_exit = (
                            candidate.close >= candidate_vwap
                            if direction is TradeDirection.LONG
                            else candidate.close <= candidate_vwap
                        )
                    else:
                        should_exit = (
                            candidate.close <= candidate_vwap
                            if direction is TradeDirection.LONG
                            else candidate.close >= candidate_vwap
                        )
                elif type(program) is NoiseAreaVwapMomentumProgram:
                    opposite = _entry_signal(
                        program,
                        session_bars,
                        candidate_index,
                        session,
                        prior_sessions,
                        resolution,
                    )
                    should_exit = opposite is not None and opposite is not direction
                if should_exit or (
                    candidate.timestamp + timedelta(minutes=int(resolution))
                    >= target_exit_at
                ):
                    exit_index = candidate_index
                    break

            exit_bar = session_bars[exit_index]
            exit = _fill(
                entry_material,
                exit_side,
                exit_bar,
                exit_bar.close,
                quantity,
                model,
            )
            with localcontext(_DECIMAL_CONTEXT):
                pnl = (
                    quantity * (exit.execution_price - entry.execution_price)
                    if direction is TradeDirection.LONG
                    else quantity * (entry.execution_price - exit.execution_price)
                )
                equity = equity_before + pnl
            maximum_gross_exposure = max(maximum_gross_exposure, gross_exposure)
            trade_id = uuid5(
                _TRADE_NAMESPACE,
                f"{entry_material}:{exit_index}:{exit.timestamp.isoformat()}",
            )
            trades.append(
                Trade(
                    trade_id,
                    symbol,
                    session,
                    entry,
                    exit,
                    direction,
                    pnl,
                    equity_before,
                    equity,
                    gross_exposure,
                )
            )
            trade_ordinal += 1
            cooldown = (
                program.cooldown_bars
                if type(program) is VwapTrendReversalProgram
                else 0
            )
            earliest_entry = exit_index + 1 + cooldown
        # Later sessions may use only prior-session data for Family A's noise area.
        prior_sessions[session] = session_bars
    with localcontext(_DECIMAL_CONTEXT):
        net_pnl = equity - starting_equity
    equity_material = {
        "initial_equity": _decimal_text(starting_equity),
        "final_equity": _decimal_text(equity),
        "net_pnl": _decimal_text(net_pnl),
        "trades": [
            {
                "trade_id": str(trade.trade_id),
                "equity_before": _decimal_text(trade.equity_before),
                "equity_after": _decimal_text(trade.equity_after),
            }
            for trade in trades
        ],
    }
    equity_digest = sha256(_canonical_json(equity_material)).hexdigest()
    replay_material = {
        "program_id": str(program_id(program)),
        "input_digest": input_digest,
        "cost_case": result_cost_case.value,
        "equity_digest": equity_digest,
    }
    replay_id = uuid5(_REPLAY_NAMESPACE, _canonical_json(replay_material).decode())
    return ReplayResult(
        replay_id,
        program_id(program),
        result_cost_case,
        tuple(trades),
        net_pnl,
        starting_equity,
        equity,
        maximum_gross_exposure,
        input_digest,
        equity_digest,
    )


@dataclass(frozen=True, slots=True)
class FrequencyDiagnostics:
    cost_case: CostCase
    validation_years: tuple[int, ...]
    annual_completed_round_trips: tuple[tuple[int, int], ...]
    regular_sessions: int
    active_sessions: int
    trades_per_active_session_values: tuple[int, ...]
    average_completed_round_trips_per_validation_year: Decimal
    active_session_fraction: Decimal
    trades_per_active_session: Decimal
    median_trades_per_active_session: Decimal


def compute_frequency_diagnostics(
    trades: Iterable[Trade],
    *,
    validation_years: Sequence[int] = (2021, 2022, 2023),
    regular_sessions: int,
    cost_case: CostCase = CostCase.STRESS,
) -> FrequencyDiagnostics:
    years = tuple(validation_years)
    if not years or len(set(years)) != len(years):
        raise ValueError("validation_years must be a nonempty unique sequence")
    if type(regular_sessions) is not int or regular_sessions < 0:
        raise ValueError("regular_sessions must be a nonnegative integer")
    materialized = tuple(trades)
    annual = {year: 0 for year in years}
    session_counts: dict[date, int] = defaultdict(int)
    for trade in materialized:
        if trade.session.year in annual:
            annual[trade.session.year] += 1
            session_counts[trade.session] += 1
    active_values = tuple(sorted(session_counts.values()))
    active = len(active_values)
    with localcontext(_DECIMAL_CONTEXT):
        average = Decimal(sum(annual.values())) / Decimal(len(years))
        fraction = (
            Decimal(active) / Decimal(regular_sessions)
            if regular_sessions
            else Decimal("0")
        )
        per_active = (
            Decimal(sum(active_values)) / Decimal(active) if active else Decimal("0")
        )
        median_value = Decimal(str(median(active_values))) if active else Decimal("0")
    return FrequencyDiagnostics(
        cost_case,
        years,
        tuple(annual.items()),
        regular_sessions,
        active,
        active_values,
        average,
        fraction,
        per_active,
        median_value,
    )


@dataclass(frozen=True, slots=True)
class FrequencyPolicy:
    name: str
    minimum_average_round_trips_per_year: Decimal | None
    minimum_active_session_fraction: Decimal
    maximum_median_trades_per_active_session: Decimal | None


VALIDATION_FREQUENCY_POLICY = FrequencyPolicy(
    "VALIDATION",
    VALIDATION_MIN_AVERAGE_ROUND_TRIPS,
    VALIDATION_MIN_ACTIVE_SESSION_FRACTION,
    VALIDATION_MAX_MEDIAN_TRADES_PER_ACTIVE_SESSION,
)
HOLDOUT_FREQUENCY_POLICY = FrequencyPolicy(
    "HOLDOUT", None, HOLDOUT_MIN_ACTIVE_SESSION_FRACTION, None
)
EXTENSION_FREQUENCY_POLICY = FrequencyPolicy(
    "RECENT_EXTENSION", None, EXTENSION_MIN_ACTIVE_SESSION_FRACTION, None
)


def passes_frequency_gate(
    diagnostics: FrequencyDiagnostics,
    policy: FrequencyPolicy = VALIDATION_FREQUENCY_POLICY,
) -> bool:
    # Advancement, holdout, and extension frequency rules are explicitly STRESS-only.
    if diagnostics.cost_case is not CostCase.STRESS:
        return False
    if (
        policy.minimum_average_round_trips_per_year is not None
        and diagnostics.average_completed_round_trips_per_validation_year
        < policy.minimum_average_round_trips_per_year
    ):
        return False
    if diagnostics.active_session_fraction < policy.minimum_active_session_fraction:
        return False
    return not (
        policy.maximum_median_trades_per_active_session is not None
        and diagnostics.median_trades_per_active_session
        > policy.maximum_median_trades_per_active_session
    )


@dataclass(frozen=True, slots=True)
class ValidationRankingMetrics:
    net_return: Decimal
    sharpe: Decimal
    maximum_drawdown: Decimal
    profit_factor: Decimal
    median_trade_expectancy: Decimal
    positive_month_breadth: Decimal
    active_session_fraction: Decimal
    turnover: Decimal
    worst_calendar_year_return: Decimal
    cost_case: CostCase = CostCase.STRESS


@dataclass(frozen=True, slots=True)
class ValidationRankingRecord:
    program_id: UUID
    metrics: ValidationRankingMetrics


def validation_rank_key(record: ValidationRankingRecord) -> tuple[object, ...]:
    """The reviewed descriptive ordering; it does not grant promotion."""

    metrics = record.metrics
    if metrics.cost_case is CostCase.ZERO:
        raise Arch150Error("zero-friction metrics are diagnostic only")
    return (
        -metrics.net_return,
        -metrics.sharpe,
        metrics.maximum_drawdown,
        -metrics.profit_factor,
        -metrics.median_trade_expectancy,
        -metrics.positive_month_breadth,
        -metrics.active_session_fraction,
        metrics.turnover,
        -metrics.worst_calendar_year_return,
        str(record.program_id),
    )


def rank_validation_records(
    records: Iterable[ValidationRankingRecord],
) -> tuple[ValidationRankingRecord, ...]:
    return tuple(sorted(tuple(records), key=validation_rank_key))


@dataclass(frozen=True, slots=True)
class InvalidTrialReference:
    family: StrategyFamily
    caller_semantic_fingerprint: str
    diagnostic_code: str

    @property
    def program_id(self) -> None:
        return None

    @property
    def semantic_fingerprint(self) -> str:
        return self.caller_semantic_fingerprint


type TrialProgram = IntradayProgram | InvalidTrialReference


@dataclass(frozen=True, slots=True)
class TrialRecord:
    trial_ordinal: int
    trial_id: UUID
    family: StrategyFamily
    program_id: UUID | None
    semantic_fingerprint: str
    disposition: TrialDisposition
    diagnostic_code: str | None


class TrialLedger:
    """Append-only complete G1 trial history, including every rejected trial."""

    __slots__ = ("_records",)

    def __init__(
        self,
        records: Iterable[TrialRecord] = (),
        *,
        _seal: object = None,
    ) -> None:
        materialized = tuple(records)
        if materialized and _seal is not _TRIAL_LEDGER_SEAL:
            raise InformationFirewallError(
                "nonempty trial ledgers must be produced by append-only consumption"
            )
        if len(materialized) > G1_TOTAL_TRIAL_LIMIT:
            raise TrialBudgetExceeded("G1 total trial budget is 24")
        seen_ids: set[UUID] = set()
        family_counts: dict[StrategyFamily, int] = defaultdict(int)
        for expected, record in enumerate(materialized, 1):
            if record.trial_ordinal != expected or record.trial_id in seen_ids:
                raise Arch150Error(
                    "trial ledger ordinals and identities must be unique"
                )
            seen_ids.add(record.trial_id)
            family_counts[record.family] += 1
            if family_counts[record.family] > G1_FAMILY_TRIAL_LIMIT:
                raise TrialBudgetExceeded("G1 family trial budget is 8")
        self._records = materialized

    def __setattr__(self, name: str, value: object) -> None:
        if hasattr(self, name):
            raise AttributeError("trial ledger records are immutable")
        object.__setattr__(self, name, value)

    @property
    def records(self) -> tuple[TrialRecord, ...]:
        return self._records

    @property
    def consumed_trial_count(self) -> int:
        return len(self._records)

    @property
    def family_counts(self) -> Mapping[StrategyFamily, int]:
        counts = {family: 0 for family in StrategyFamily}
        for record in self._records:
            counts[record.family] += 1
        return counts

    @property
    def ledger_id(self) -> UUID:
        material = [
            {
                "ordinal": record.trial_ordinal,
                "trial_id": str(record.trial_id),
                "family": record.family.value,
                "program_id": str(record.program_id) if record.program_id else None,
                "semantic_fingerprint": record.semantic_fingerprint,
                "disposition": record.disposition.value,
                "diagnostic_code": record.diagnostic_code,
            }
            for record in self._records
        ]
        return uuid5(_TRIAL_NAMESPACE, _canonical_json(material).decode())

    def consume(
        self,
        program: TrialProgram,
        disposition: TrialDisposition,
        *,
        diagnostic_code: str | None = None,
    ) -> TrialLedger:
        if self.consumed_trial_count >= G1_TOTAL_TRIAL_LIMIT:
            raise TrialBudgetExceeded("G1 total trial budget is 24")
        if type(program) is InvalidTrialReference:
            family = program.family
            semantic = program.semantic_fingerprint
            identifier = None
        elif type(program) in (
            NoiseAreaVwapMomentumProgram,
            VwapTrendReversalProgram,
            OpeningRangeBreakoutReversalProgram,
        ):
            family = program.family
            semantic = program_fingerprint(program)
            identifier = program_id(program)
        else:
            raise UnsupportedProgramError(
                "invalid trials need a typed family reference"
            )
        if any(record.semantic_fingerprint == semantic for record in self._records):
            disposition = TrialDisposition.DUPLICATE
            diagnostic_code = diagnostic_code or "DUPLICATE_SEMANTIC_PROGRAM"
        family_count = self.family_counts[family]
        if family_count >= G1_FAMILY_TRIAL_LIMIT:
            raise TrialBudgetExceeded("family trial budget is 8")
        ordinal = self.consumed_trial_count + 1
        trial_id = uuid5(
            _TRIAL_NAMESPACE,
            f"{TRIAL_LEDGER_SCHEMA}:{ordinal}:{family.value}:{semantic}:{disposition.value}",
        )
        record = TrialRecord(
            ordinal,
            trial_id,
            family,
            identifier,
            semantic,
            disposition,
            diagnostic_code,
        )
        return TrialLedger((*self._records, record), _seal=_TRIAL_LEDGER_SEAL)

    def to_bytes(self) -> bytes:
        return _canonical_json(
            {
                "schema": TRIAL_LEDGER_SCHEMA,
                "ledger_id": str(self.ledger_id),
                "records": [
                    {
                        "trial_ordinal": record.trial_ordinal,
                        "trial_id": str(record.trial_id),
                        "family": record.family.value,
                        "program_id": (
                            str(record.program_id) if record.program_id else None
                        ),
                        "semantic_fingerprint": record.semantic_fingerprint,
                        "disposition": record.disposition.value,
                        "diagnostic_code": record.diagnostic_code,
                    }
                    for record in self._records
                ],
            }
        )


def _population_freeze_material(
    discovery_dataset: ResearchDataset, ledger: TrialLedger
) -> dict[str, object]:
    discovery_material = {
        "stage": discovery_dataset.stage.value,
        "start": discovery_dataset.start.isoformat(),
        "end_exclusive": discovery_dataset.end_exclusive.isoformat(),
        "input_digest": discovery_dataset.bars.input_digest,
    }
    discovery_dataset_id = uuid5(
        _POPULATION_FREEZE_NAMESPACE, _canonical_json(discovery_material).decode()
    )
    return {
        "discovery_dataset_id": str(discovery_dataset_id),
        "ledger_id": str(ledger.ledger_id),
        "trial_ids": [str(record.trial_id) for record in ledger.records],
        "semantic_fingerprints": [
            record.semantic_fingerprint for record in ledger.records
        ],
        "program_ids": [
            str(record.program_id) for record in ledger.records if record.program_id
        ],
    }


def freeze_discovery_population(
    discovery_dataset: ResearchDataset, ledger: TrialLedger
) -> DiscoveryPopulationFreeze:
    """Freeze the complete 24-trial G1 discovery population immutably."""

    if (
        type(discovery_dataset) is not ResearchDataset
        or discovery_dataset._authority_seal is not _DATASET_SEAL
        or discovery_dataset.stage is not ResearchStage.DISCOVERY
        or type(ledger) is not TrialLedger
        or ledger.consumed_trial_count != G1_TOTAL_TRIAL_LIMIT
    ):
        raise InformationFirewallError(
            "discovery population freeze requires an opened discovery dataset "
            "and all 24 G1 trials"
        )
    if any(count != G1_FAMILY_TRIAL_LIMIT for count in ledger.family_counts.values()):
        raise InformationFirewallError(
            "discovery population freeze requires eight trials per family"
        )
    material = _population_freeze_material(discovery_dataset, ledger)
    freeze_id = uuid5(_POPULATION_FREEZE_NAMESPACE, _canonical_json(material).decode())
    discovery_dataset_id = UUID(material["discovery_dataset_id"])
    return DiscoveryPopulationFreeze(
        freeze_id,
        discovery_dataset_id,
        ledger.ledger_id,
        tuple(record.trial_id for record in ledger.records),
        tuple(record.semantic_fingerprint for record in ledger.records),
        tuple(record.program_id for record in ledger.records if record.program_id),
        _seal=_POPULATION_FREEZE_SEAL,
    )


def freeze_candidate_population(
    population_freeze: DiscoveryPopulationFreeze,
    ledger: TrialLedger,
    candidates: Iterable[IntradayProgram],
) -> CandidateFreeze:
    """Freeze shortlisted typed candidates against the exact frozen G1 ledger."""

    if (
        type(population_freeze) is not DiscoveryPopulationFreeze
        or population_freeze._authority_seal is not _POPULATION_FREEZE_SEAL
        or type(ledger) is not TrialLedger
    ):
        raise InformationFirewallError("candidate freeze needs frozen G1 authority")
    if (
        population_freeze.ledger_id != ledger.ledger_id
        or population_freeze.trial_ids
        != tuple(record.trial_id for record in ledger.records)
        or population_freeze.semantic_fingerprints
        != tuple(record.semantic_fingerprint for record in ledger.records)
        or population_freeze.program_ids
        != tuple(record.program_id for record in ledger.records if record.program_id)
    ):
        raise InformationFirewallError(
            "population freeze does not bind the supplied trial ledger"
        )
    shortlisted = {
        (record.program_id, record.semantic_fingerprint)
        for record in ledger.records
        if record.disposition is TrialDisposition.SHORTLISTED
        and record.program_id is not None
    }
    materialized = tuple(candidates)
    candidate_material: list[tuple[UUID, str]] = []
    for program in materialized:
        if type(program) not in (
            NoiseAreaVwapMomentumProgram,
            VwapTrendReversalProgram,
            OpeningRangeBreakoutReversalProgram,
        ):
            raise InformationFirewallError(
                "candidate freeze accepts only the closed typed grammar"
            )
        identity = (program_id(program), program_fingerprint(program))
        if identity not in shortlisted:
            raise InformationFirewallError(
                "candidate was not shortlisted in the frozen discovery ledger"
            )
        candidate_material.append(identity)
    if not candidate_material or len(set(candidate_material)) != len(
        candidate_material
    ):
        raise InformationFirewallError(
            "candidate freeze requires a nonempty unique frozen population subset"
        )
    candidate_ids = tuple(item[0] for item in candidate_material)
    fingerprints = tuple(item[1] for item in candidate_material)
    identity_material = {
        "population_freeze_id": str(population_freeze.freeze_id),
        "discovery_dataset_id": str(population_freeze.discovery_dataset_id),
        "ledger_id": str(ledger.ledger_id),
        "candidate_program_ids": [str(item) for item in candidate_ids],
        "candidate_fingerprints": list(fingerprints),
    }
    freeze_id = uuid5(
        _CANDIDATE_FREEZE_NAMESPACE, _canonical_json(identity_material).decode()
    )
    return CandidateFreeze(
        freeze_id,
        population_freeze.freeze_id,
        population_freeze.discovery_dataset_id,
        ledger.ledger_id,
        candidate_ids,
        fingerprints,
        _seal=_CANDIDATE_FREEZE_SEAL,
    )


@dataclass(frozen=True, slots=True)
class SelectionBiasInput:
    ledger_id: UUID
    consumed_trial_count: int
    trial_ids: tuple[UUID, ...]
    program_ids: tuple[UUID, ...]
    metric_schema: str

    def to_bytes(self) -> bytes:
        return _canonical_json(
            {
                "schema": SELECTION_BIAS_SCHEMA,
                "ledger_id": str(self.ledger_id),
                "consumed_trial_count": self.consumed_trial_count,
                "trial_ids": [str(item) for item in self.trial_ids],
                "program_ids": [str(item) for item in self.program_ids],
                "metric_schema": self.metric_schema,
            }
        )


def selection_bias_input(ledger: TrialLedger) -> SelectionBiasInput:
    return SelectionBiasInput(
        ledger.ledger_id,
        ledger.consumed_trial_count,
        tuple(record.trial_id for record in ledger.records),
        tuple(record.program_id for record in ledger.records if record.program_id),
        "arch150-validation-ranking-metrics/v1",
    )


@dataclass(frozen=True, slots=True)
class FoundationEffectCounters:
    provider_calls: int = 0
    credential_reads: int = 0
    robinhood_calls: int = 0
    broker_effects: int = 0
    order_effects: int = 0
    production_mutations: int = 0
    final_holdout_opens: int = 0


FOUNDATION_EFFECT_COUNTERS = FoundationEffectCounters()


def foundation_help() -> str:
    """Return effect-free help text for the source-only foundation."""

    return (
        "Architecture 150 foundation: typed synthetic-only research contracts; "
        "no provider, credential, broker, order, production, or holdout access."
    )
