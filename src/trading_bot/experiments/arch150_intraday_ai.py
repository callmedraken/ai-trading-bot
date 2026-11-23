"""Architecture 150 offline intraday AI research contracts.

The module owns deterministic research contracts and synthetic test seams. It
does not read custody files, acquire data, access credentials, contact a
provider, or execute broker effects. Accepted sparse custody can be bound only
from an already materialized in-memory stream at a separately reviewed step.
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
TRIAL_LEDGER_SCHEMA = "arch150-consumed-trial-ledger/v3"
G1_POPULATION_SCHEMA = "arch150-g1-pre-evaluation-population/v2"
G1_RESULT_SCHEMA = "arch150-g1-trial-result/v2"
DISCOVERY_RESULT_SCHEMA = "arch150-discovery-result-freeze/v2"
SELECTION_BIAS_SCHEMA = "arch150-selection-bias-input/v3"
CANDIDATE_FREEZE_SCHEMA = "arch150-candidate-freeze/v2"
REPLAY_SCHEMA = "arch150-deterministic-replay/v2"
SPARSE_FIVE_MINUTE_SCHEMA = "arch150-sparse-five-minute-view/v1"
SPARSE_CUSTODY_AUTHORITY_SCHEMA = "arch150-sparse-custody-authority/v1"

DISCOVERY_START = date(2016, 1, 1)
DISCOVERY_END = date(2021, 1, 1)
VALIDATION_START = date(2021, 1, 1)
VALIDATION_END = date(2024, 1, 1)
SPARSE_CUSTODY_START = date(2016, 1, 1)
SPARSE_CUSTODY_END = date(2024, 1, 1)
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
_DISCOVERY_DATASET_NAMESPACE = UUID("ab09fd8e-480d-5937-a238-b4fb9720437e")
_SPARSE_TEST_DATASET_NAMESPACE = UUID("1a7395d3-a494-5b5c-940d-b0a7699302ad")
_CANDIDATE_FREEZE_NAMESPACE = UUID("d463e47c-c8f8-5843-a059-7520dab589ea")
_G1_MANIFEST_NAMESPACE = UUID("795ace21-a597-5bbd-9c4d-4daeffcf3028")
_DISCOVERY_RESULT_NAMESPACE = UUID("2db93faf-c704-5612-9747-96a9bde00c65")
_G1_SLOT_NAMESPACE = UUID("e5307e4c-77a1-5d38-9d4c-3b94cfa5379f")
_G1_RESULT_NAMESPACE = UUID("8a04eb07-0a78-5a06-8a1a-62e572ecaf1b")
_G1_SLOT_SEAL = object()
_G1_MANIFEST_SEAL = object()
_G1_RESULT_SEAL = object()
_DISCOVERY_RESULT_SEAL = object()
_CANDIDATE_FREEZE_SEAL = object()
_DATASET_SEAL = object()
_FIVE_MINUTE_SEAL = object()
_SPARSE_FIVE_MINUTE_SEAL = object()
_SPARSE_CUSTODY_AUTHORITY_SEAL = object()

_ACCEPTED_SPARSE_DATASET_ID = UUID("ff5a3847-09c2-5902-b174-9e77eebf7d53")
_ACCEPTED_SPARSE_DATASET_SHA256 = (
    "0070a5c0cfa5cd7878253d93bc0895b46da28d8b5e2a71395e66ce904b3f85dd"
)
_ACCEPTED_SPARSE_CUSTODY_ID = UUID("21e121dc-a9da-538f-bc88-c15fe7ea7f50")
_ACCEPTED_SPARSE_CUSTODY_SHA256 = (
    "5b6ac554eda73b588f2f6d664c14e5c7fca3c151966cb546c17621d0c7e6ad83"
)
_ACCEPTED_NORMALIZED_CSV_SHA256 = (
    ("SPY", "f7c1a708db72f9f73bd0d05c45dfffed26f5b5fa36c9428c8069af28d897c8ed"),
    ("QQQ", "c9c95664f1a0112d410cdc01273be8146f0136ca57591b18ddb6a7f1fbd3c471"),
)
_ACCEPTED_SCHEDULED_SLOTS = 781980
_ACCEPTED_OBSERVED_COUNTS = (("SPY", 781876), ("QQQ", 781865))
_ACCEPTED_MISSING_COUNTS = (("SPY", 104), ("QQQ", 115))
_ACCEPTED_MISSING_SHA256 = (
    ("SPY", "d6da92e26196d00a25355ebb83e58d16ef767d9a4c476ee848070727a9780eba"),
    ("QQQ", "7f4eab086290576208f1d47887b32413de5015634da9e551aa9f8eecc385a0d4"),
)
_ACCEPTED_COMMON_MISSING_COUNT = 64
_ACCEPTED_UNION_MISSING_COUNT = 155
_ACCEPTED_FULLY_MISSING_SESSION_COUNTS = (("SPY", 0), ("QQQ", 0))


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


@dataclass(frozen=True, slots=True, init=False)
class SparseCustodyAuthority:
    """Immutable accepted custody facts, without exposing missing timestamps."""

    schema: str
    dataset_id: UUID
    dataset_semantic_sha256: str
    custody_id: UUID
    custody_semantic_sha256: str
    normalized_file_sha256_by_symbol: tuple[tuple[str, str], ...]
    scheduled_slots_per_symbol: int
    observed_counts_by_symbol: tuple[tuple[str, int], ...]
    missing_counts_by_symbol: tuple[tuple[str, int], ...]
    missing_timestamp_sha256_by_symbol: tuple[tuple[str, str], ...]
    common_missing_count: int
    union_missing_count: int
    fully_missing_session_counts_by_symbol: tuple[tuple[str, int], ...]
    authority_kind: str
    _source_input_digest: str | None = field(repr=False, compare=False)
    _authority_seal: object = field(repr=False, compare=False)

    def __init__(
        self,
        dataset_id: UUID,
        dataset_semantic_sha256: str,
        custody_id: UUID,
        custody_semantic_sha256: str,
        normalized_file_sha256_by_symbol: tuple[tuple[str, str], ...],
        scheduled_slots_per_symbol: int,
        observed_counts_by_symbol: tuple[tuple[str, int], ...],
        missing_counts_by_symbol: tuple[tuple[str, int], ...],
        missing_timestamp_sha256_by_symbol: tuple[tuple[str, str], ...],
        common_missing_count: int,
        union_missing_count: int,
        fully_missing_session_counts_by_symbol: tuple[tuple[str, int], ...],
        authority_kind: str,
        source_input_digest: str | None = None,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _SPARSE_CUSTODY_AUTHORITY_SEAL:
            raise InformationFirewallError(
                "sparse custody authorities require source-owned binding"
            )
        for name, value in (
            ("schema", SPARSE_CUSTODY_AUTHORITY_SCHEMA),
            ("dataset_id", dataset_id),
            ("dataset_semantic_sha256", dataset_semantic_sha256),
            ("custody_id", custody_id),
            ("custody_semantic_sha256", custody_semantic_sha256),
            ("normalized_file_sha256_by_symbol", normalized_file_sha256_by_symbol),
            ("scheduled_slots_per_symbol", scheduled_slots_per_symbol),
            ("observed_counts_by_symbol", observed_counts_by_symbol),
            ("missing_counts_by_symbol", missing_counts_by_symbol),
            ("missing_timestamp_sha256_by_symbol", missing_timestamp_sha256_by_symbol),
            ("common_missing_count", common_missing_count),
            ("union_missing_count", union_missing_count),
            (
                "fully_missing_session_counts_by_symbol",
                fully_missing_session_counts_by_symbol,
            ),
            ("authority_kind", authority_kind),
            ("_source_input_digest", source_input_digest),
        ):
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_authority_seal", _seal)


def _new_sparse_custody_authority(
    *,
    dataset_id: UUID,
    dataset_semantic_sha256: str,
    custody_id: UUID,
    custody_semantic_sha256: str,
    normalized_file_sha256_by_symbol: tuple[tuple[str, str], ...],
    scheduled_slots_per_symbol: int,
    observed_counts_by_symbol: tuple[tuple[str, int], ...],
    missing_counts_by_symbol: tuple[tuple[str, int], ...],
    missing_timestamp_sha256_by_symbol: tuple[tuple[str, str], ...],
    common_missing_count: int,
    union_missing_count: int,
    fully_missing_session_counts_by_symbol: tuple[tuple[str, int], ...],
    authority_kind: str,
    source_input_digest: str | None = None,
) -> SparseCustodyAuthority:
    return SparseCustodyAuthority(
        dataset_id,
        dataset_semantic_sha256,
        custody_id,
        custody_semantic_sha256,
        normalized_file_sha256_by_symbol,
        scheduled_slots_per_symbol,
        observed_counts_by_symbol,
        missing_counts_by_symbol,
        missing_timestamp_sha256_by_symbol,
        common_missing_count,
        union_missing_count,
        fully_missing_session_counts_by_symbol,
        authority_kind,
        source_input_digest,
        _seal=_SPARSE_CUSTODY_AUTHORITY_SEAL,
    )


_ACCEPTED_SPARSE_CUSTODY_AUTHORITY = _new_sparse_custody_authority(
    dataset_id=_ACCEPTED_SPARSE_DATASET_ID,
    dataset_semantic_sha256=_ACCEPTED_SPARSE_DATASET_SHA256,
    custody_id=_ACCEPTED_SPARSE_CUSTODY_ID,
    custody_semantic_sha256=_ACCEPTED_SPARSE_CUSTODY_SHA256,
    normalized_file_sha256_by_symbol=_ACCEPTED_NORMALIZED_CSV_SHA256,
    scheduled_slots_per_symbol=_ACCEPTED_SCHEDULED_SLOTS,
    observed_counts_by_symbol=_ACCEPTED_OBSERVED_COUNTS,
    missing_counts_by_symbol=_ACCEPTED_MISSING_COUNTS,
    missing_timestamp_sha256_by_symbol=_ACCEPTED_MISSING_SHA256,
    common_missing_count=_ACCEPTED_COMMON_MISSING_COUNT,
    union_missing_count=_ACCEPTED_UNION_MISSING_COUNT,
    fully_missing_session_counts_by_symbol=_ACCEPTED_FULLY_MISSING_SESSION_COUNTS,
    authority_kind="ACCEPTED_D1R_SPARSE_CUSTODY",
)


def _sparse_custody_authority_is_valid(value: object) -> bool:
    return (
        type(value) is SparseCustodyAuthority
        and value._authority_seal is _SPARSE_CUSTODY_AUTHORITY_SEAL
        and (
            value is _ACCEPTED_SPARSE_CUSTODY_AUTHORITY
            or (
                value.authority_kind == "SYNTHETIC_TEST"
                and value._source_input_digest is not None
            )
        )
    )


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


def _custody_timestamp_text(value: datetime) -> str:
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _normalized_custody_csv_row(bar: IntradayBar) -> bytes:
    return (
        ",".join(
            (
                _custody_timestamp_text(bar.timestamp),
                bar.symbol,
                "1Min",
                _decimal_text(bar.open),
                _decimal_text(bar.high),
                _decimal_text(bar.low),
                _decimal_text(bar.close),
                str(bar.volume),
            )
        ).encode("utf-8")
        + b"\n"
    )


def _validate_accepted_sparse_custody(
    bars: Iterable[IntradayBar],
) -> ValidatedUniverseBars:
    materialized = tuple(bars)
    if not materialized or any(
        type(bar) is not IntradayBar
        or not SPARSE_CUSTODY_START <= bar.session_date < SPARSE_CUSTODY_END
        for bar in materialized
    ):
        raise Arch150Error(
            "sparse custody input is outside its accepted 2016-2023 window"
        )
    validated = validate_universe_minute_bars(materialized)
    csv_hashes: dict[str, str] = {}
    bar_indexes = {symbol: 0 for symbol in INITIAL_UNIVERSE}
    observed = {symbol: 0 for symbol in INITIAL_UNIVERSE}
    missing = {symbol: 0 for symbol in INITIAL_UNIVERSE}
    missing_hashes = {symbol: sha256() for symbol in INITIAL_UNIVERSE}
    fully_missing_sessions = {symbol: 0 for symbol in INITIAL_UNIVERSE}
    common_missing = 0
    union_missing = 0
    scheduled_count = 0

    for symbol in INITIAL_UNIVERSE:
        csv_hash = sha256()
        csv_hash.update(b"timestamp,symbol,resolution,open,high,low,close,volume\n")
        for bar in validated.by_symbol[symbol].bars:
            csv_hash.update(_normalized_custody_csv_row(bar))
        csv_hashes[symbol] = csv_hash.hexdigest()

    for session in _SESSION_AUTHORITY.published.sessions:
        if not SPARSE_CUSTODY_START <= session < SPARSE_CUSTODY_END:
            continue
        schedule = _SESSION_AUTHORITY.schedule_for(session)
        if schedule is None:
            raise Arch150Error("published sparse-custody session has no schedule")
        slot = schedule.opens_at.astimezone(UTC)
        close = schedule.closes_at.astimezone(UTC)
        per_session_scheduled = 0
        per_session_missing = {symbol: 0 for symbol in INITIAL_UNIVERSE}
        while slot < close:
            scheduled_count += 1
            per_session_scheduled += 1
            is_missing: dict[str, bool] = {}
            for symbol in INITIAL_UNIVERSE:
                stream = validated.by_symbol[symbol].bars
                index = bar_indexes[symbol]
                if index < len(stream) and stream[index].timestamp == slot:
                    observed[symbol] += 1
                    bar_indexes[symbol] = index + 1
                    is_missing[symbol] = False
                else:
                    if index < len(stream) and stream[index].timestamp < slot:
                        raise Arch150Error("sparse custody input is not slot ordered")
                    missing[symbol] += 1
                    per_session_missing[symbol] += 1
                    missing_hashes[symbol].update(
                        _custody_timestamp_text(slot).encode("ascii") + b"\n"
                    )
                    is_missing[symbol] = True
            if all(is_missing.values()):
                common_missing += 1
            if any(is_missing.values()):
                union_missing += 1
            slot += timedelta(minutes=1)
        for symbol in INITIAL_UNIVERSE:
            if per_session_missing[symbol] == per_session_scheduled:
                fully_missing_sessions[symbol] += 1

    if any(
        bar_indexes[symbol] != len(validated.by_symbol[symbol].bars)
        for symbol in INITIAL_UNIVERSE
    ):
        raise Arch150Error("sparse custody input contains an unaccounted observation")
    actual = (
        scheduled_count,
        tuple((symbol, observed[symbol]) for symbol in INITIAL_UNIVERSE),
        tuple((symbol, missing[symbol]) for symbol in INITIAL_UNIVERSE),
        tuple(
            (symbol, missing_hashes[symbol].hexdigest()) for symbol in INITIAL_UNIVERSE
        ),
        tuple((symbol, csv_hashes[symbol]) for symbol in INITIAL_UNIVERSE),
        common_missing,
        union_missing,
        tuple((symbol, fully_missing_sessions[symbol]) for symbol in INITIAL_UNIVERSE),
    )
    expected = (
        _ACCEPTED_SCHEDULED_SLOTS,
        _ACCEPTED_OBSERVED_COUNTS,
        _ACCEPTED_MISSING_COUNTS,
        _ACCEPTED_MISSING_SHA256,
        _ACCEPTED_NORMALIZED_CSV_SHA256,
        _ACCEPTED_COMMON_MISSING_COUNT,
        _ACCEPTED_UNION_MISSING_COUNT,
        _ACCEPTED_FULLY_MISSING_SESSION_COUNTS,
    )
    if actual != expected:
        raise Arch150Error("sparse custody stream differs from accepted commitments")
    return validated


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
class SparseDerivedFiveMinuteBars:
    """Sealed complete buckets derived independently from a sparse minute stream."""

    symbol: str
    bars: tuple[IntradayBar, ...]
    sessions: tuple[date, ...]
    input_digest: str
    output_digest: str
    source_digest: str
    _authority_seal: object = field(repr=False, compare=False)

    def __init__(
        self,
        symbol: str,
        bars: tuple[IntradayBar, ...],
        sessions: tuple[date, ...],
        input_digest: str,
        output_digest: str,
        source_digest: str,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _SPARSE_FIVE_MINUTE_SEAL:
            raise Arch150Error("sparse five-minute streams require exact aggregation")
        for name, value in (
            ("symbol", symbol),
            ("bars", bars),
            ("sessions", sessions),
            ("input_digest", input_digest),
            ("output_digest", output_digest),
            ("source_digest", source_digest),
        ):
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_authority_seal", _seal)

    def __len__(self) -> int:
        return len(self.bars)

    def __iter__(self):
        return iter(self.bars)

    def __getitem__(self, index):
        return self.bars[index]


def _sparse_five_minute_source_digest(input_digest: str, output_digest: str) -> str:
    material = {
        "schema": SPARSE_FIVE_MINUTE_SCHEMA,
        "input_digest": input_digest,
        "output_digest": output_digest,
    }
    return sha256(_canonical_json(material)).hexdigest()


def aggregate_sparse_five_minute_bars(
    bars: ValidatedMinuteBars | Iterable[IntradayBar],
) -> SparseDerivedFiveMinuteBars:
    """Aggregate only complete XNYS-aligned buckets in a sparse stream."""

    validated = validate_1_minute_bars(
        bars.bars if type(bars) is ValidatedMinuteBars else bars,
        symbol=bars.symbol if type(bars) is ValidatedMinuteBars else None,
    )
    groups: dict[tuple[date, int], list[IntradayBar]] = defaultdict(list)
    schedules = {}
    for bar in validated.bars:
        schedule = _SESSION_AUTHORITY.schedule_for(bar.session_date)
        if schedule is None:
            raise Arch150Error("bar date is not a published regular XNYS session")
        schedules[bar.session_date] = schedule
        elapsed = bar.timestamp - schedule.opens_at
        elapsed_minutes = int(elapsed.total_seconds() // 60)
        if elapsed.total_seconds() != elapsed_minutes * 60:
            raise Arch150Error("one-minute bars must align to XNYS session minutes")
        bucket = elapsed_minutes // int(BarResolution.FIVE_MINUTE)
        groups[(bar.session_date, bucket)].append(bar)

    derived: list[IntradayBar] = []
    for (session, bucket), group in sorted(groups.items()):
        bucket_open = schedules[session].opens_at + timedelta(
            minutes=bucket * int(BarResolution.FIVE_MINUTE)
        )
        if len(group) != int(BarResolution.FIVE_MINUTE) or any(
            bar.timestamp != bucket_open + timedelta(minutes=offset)
            for offset, bar in enumerate(group)
        ):
            continue
        derived.append(
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
    result = tuple(derived)
    output_digest = sha256(
        _canonical_json([_bar_material(bar) for bar in result])
    ).hexdigest()
    source_digest = _sparse_five_minute_source_digest(
        validated.input_digest, output_digest
    )
    return SparseDerivedFiveMinuteBars(
        validated.symbol,
        result,
        tuple(dict.fromkeys(bar.session_date for bar in result)),
        validated.input_digest,
        output_digest,
        source_digest,
        _seal=_SPARSE_FIVE_MINUTE_SEAL,
    )


def _validate_sparse_derived_five_minute_bars(
    bars: SparseDerivedFiveMinuteBars,
) -> tuple[IntradayBar, ...]:
    if (
        type(bars) is not SparseDerivedFiveMinuteBars
        or bars._authority_seal is not _SPARSE_FIVE_MINUTE_SEAL
    ):
        raise Arch150Error("sparse five-minute input must come from exact aggregation")
    previous: datetime | None = None
    for bar in bars.bars:
        if (
            type(bar) is not IntradayBar
            or bar.resolution is not BarResolution.FIVE_MINUTE
        ):
            raise Arch150Error(
                "sparse derived input must retain five-minute resolution"
            )
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
    sessions = tuple(dict.fromkeys(bar.session_date for bar in bars.bars))
    output_digest = sha256(
        _canonical_json([_bar_material(bar) for bar in bars.bars])
    ).hexdigest()
    source_digest = _sparse_five_minute_source_digest(bars.input_digest, output_digest)
    if (
        sessions != bars.sessions
        or output_digest != bars.output_digest
        or source_digest != bars.source_digest
    ):
        raise Arch150Error("sparse five-minute commitment does not match its bars")
    return bars.bars


@dataclass(frozen=True, slots=True, init=False)
class FrozenTrialSlot:
    """One ordered hypothesis committed before official evaluation."""

    manifest_id: UUID
    slot_id: UUID
    ordinal: int
    family: StrategyFamily
    source_symbol: str
    bar_resolution: BarResolution
    semantic_fingerprint: str
    program_id: UUID | None
    invalid_reference: InvalidTrialReference | None
    _program: IntradayProgram | None = field(repr=False, compare=False)
    _authority_seal: object = field(repr=False, compare=False)

    def __init__(
        self,
        manifest_id: UUID,
        slot_id: UUID,
        ordinal: int,
        family: StrategyFamily,
        source_symbol: str,
        bar_resolution: BarResolution,
        semantic_fingerprint: str,
        program_id: UUID | None,
        invalid_reference: InvalidTrialReference | None,
        program: IntradayProgram | None,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _G1_SLOT_SEAL:
            raise InformationFirewallError(
                "G1 trial slots must come from the frozen population authority"
            )
        for name, value in (
            ("manifest_id", manifest_id),
            ("slot_id", slot_id),
            ("ordinal", ordinal),
            ("family", family),
            ("source_symbol", source_symbol),
            ("bar_resolution", bar_resolution),
            ("semantic_fingerprint", semantic_fingerprint),
            ("program_id", program_id),
            ("invalid_reference", invalid_reference),
            ("_program", program),
        ):
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_authority_seal", _seal)


@dataclass(frozen=True, slots=True, init=False)
class G1PopulationManifest:
    """The ordered, immutable G1 proposal population frozen before results."""

    manifest_id: UUID
    slots: tuple[FrozenTrialSlot, ...]
    _authority_seal: object = field(repr=False, compare=False)

    def __init__(
        self,
        manifest_id: UUID,
        slots: tuple[FrozenTrialSlot, ...],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _G1_MANIFEST_SEAL:
            raise InformationFirewallError(
                "G1 manifests must come from the pre-evaluation freeze authority"
            )
        object.__setattr__(self, "manifest_id", manifest_id)
        object.__setattr__(self, "slots", slots)
        object.__setattr__(self, "_authority_seal", _seal)

    def to_bytes(self) -> bytes:
        return _canonical_json(
            {
                "schema": G1_POPULATION_SCHEMA,
                "manifest_id": str(self.manifest_id),
                "slots": [
                    {
                        "ordinal": slot.ordinal,
                        "slot_id": str(slot.slot_id),
                        "family": slot.family.value,
                        "source_symbol": slot.source_symbol,
                        "bar_resolution": slot.bar_resolution.name,
                        "semantic_fingerprint": slot.semantic_fingerprint,
                        "program_id": str(slot.program_id) if slot.program_id else None,
                        "proposal": _slot_material(slot),
                    }
                    for slot in self.slots
                ],
            }
        )


@dataclass(frozen=True, slots=True, init=False)
class DiscoveryResultFreeze:
    """Post-evaluation authority bound to a complete manifest and ledger."""

    freeze_id: UUID
    population_manifest_id: UUID
    discovery_dataset_id: UUID
    ledger_id: UUID
    slot_ids: tuple[UUID, ...]
    result_ids: tuple[UUID, ...]
    _authority_seal: object = field(repr=False, compare=False)

    def __init__(
        self,
        freeze_id: UUID,
        population_manifest_id: UUID,
        discovery_dataset_id: UUID,
        ledger_id: UUID,
        slot_ids: tuple[UUID, ...],
        result_ids: tuple[UUID, ...],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _DISCOVERY_RESULT_SEAL:
            raise InformationFirewallError(
                "discovery result freezes require completed G1 evaluation"
            )
        for name, value in (
            ("freeze_id", freeze_id),
            ("population_manifest_id", population_manifest_id),
            ("discovery_dataset_id", discovery_dataset_id),
            ("ledger_id", ledger_id),
            ("slot_ids", slot_ids),
            ("result_ids", result_ids),
        ):
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_authority_seal", _seal)


@dataclass(frozen=True, slots=True, init=False)
class CandidateFreeze:
    """Immutable validation authorization bound to completed discovery results."""

    freeze_id: UUID
    population_manifest_id: UUID
    discovery_result_freeze_id: UUID
    discovery_dataset_id: UUID
    ledger_id: UUID
    candidate_slot_ids: tuple[UUID, ...]
    candidate_program_ids: tuple[UUID, ...]
    candidate_fingerprints: tuple[str, ...]
    candidate_source_symbols: tuple[str, ...]
    candidate_bar_resolutions: tuple[BarResolution, ...]
    _authority_seal: object = field(repr=False, compare=False)

    def __init__(
        self,
        freeze_id: UUID,
        population_manifest_id: UUID,
        discovery_result_freeze_id: UUID,
        discovery_dataset_id: UUID,
        ledger_id: UUID,
        candidate_slot_ids: tuple[UUID, ...],
        candidate_program_ids: tuple[UUID, ...],
        candidate_fingerprints: tuple[str, ...],
        candidate_source_symbols: tuple[str, ...],
        candidate_bar_resolutions: tuple[BarResolution, ...],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _CANDIDATE_FREEZE_SEAL:
            raise InformationFirewallError(
                "candidate freezes must come from the frozen discovery population"
            )
        for name, value in (
            ("freeze_id", freeze_id),
            ("population_manifest_id", population_manifest_id),
            ("discovery_result_freeze_id", discovery_result_freeze_id),
            ("discovery_dataset_id", discovery_dataset_id),
            ("ledger_id", ledger_id),
            ("candidate_slot_ids", candidate_slot_ids),
            ("candidate_program_ids", candidate_program_ids),
            ("candidate_fingerprints", candidate_fingerprints),
            ("candidate_source_symbols", candidate_source_symbols),
            ("candidate_bar_resolutions", candidate_bar_resolutions),
        ):
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_authority_seal", _seal)

    def to_bytes(self) -> bytes:
        return _canonical_json(
            {
                "schema": CANDIDATE_FREEZE_SCHEMA,
                "freeze_id": str(self.freeze_id),
                "population_manifest_id": str(self.population_manifest_id),
                "discovery_result_freeze_id": str(self.discovery_result_freeze_id),
                "discovery_dataset_id": str(self.discovery_dataset_id),
                "ledger_id": str(self.ledger_id),
                "candidate_slot_ids": [str(item) for item in self.candidate_slot_ids],
                "candidate_program_ids": [
                    str(item) for item in self.candidate_program_ids
                ],
                "candidate_fingerprints": list(self.candidate_fingerprints),
                "candidate_source_symbols": list(self.candidate_source_symbols),
                "candidate_bar_resolutions": [
                    item.name for item in self.candidate_bar_resolutions
                ],
            }
        )


@dataclass(frozen=True, slots=True, init=False)
class ResearchDataset:
    stage: ResearchStage
    bars: ValidatedUniverseBars
    start: date
    end_exclusive: date
    candidate_freeze: CandidateFreeze | None
    _sparse_custody_authority: SparseCustodyAuthority | None = field(repr=False)
    _authority_seal: object = field(repr=False, compare=False)

    def __init__(
        self,
        stage: ResearchStage,
        bars: ValidatedUniverseBars,
        start: date,
        end_exclusive: date,
        candidate_freeze: CandidateFreeze | None = None,
        sparse_custody_authority: SparseCustodyAuthority | None = None,
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
        if sparse_custody_authority is not None:
            if (
                stage is not ResearchStage.DISCOVERY
                or not _sparse_custody_authority_is_valid(sparse_custody_authority)
            ):
                raise InformationFirewallError(
                    "sparse custody authority is invalid for this dataset stage"
                )
            if (
                sparse_custody_authority.authority_kind == "SYNTHETIC_TEST"
                and sparse_custody_authority._source_input_digest != bars.input_digest
            ):
                raise InformationFirewallError(
                    "synthetic sparse authority does not bind this input stream"
                )
        for name, value in (
            ("stage", stage),
            ("bars", bars),
            ("start", start),
            ("end_exclusive", end_exclusive),
            ("candidate_freeze", candidate_freeze),
            ("_sparse_custody_authority", sparse_custody_authority),
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
        and len(value.candidate_slot_ids)
        == len(value.candidate_program_ids)
        == len(value.candidate_fingerprints)
        == len(value.candidate_source_symbols)
        == len(value.candidate_bar_resolutions)
        and len(set(value.candidate_slot_ids)) == len(value.candidate_slot_ids)
        and all(symbol in INITIAL_UNIVERSE for symbol in value.candidate_source_symbols)
        and all(type(item) is BarResolution for item in value.candidate_bar_resolutions)
    ):
        return False
    material = {
        "schema": CANDIDATE_FREEZE_SCHEMA,
        "population_manifest_id": str(value.population_manifest_id),
        "discovery_result_freeze_id": str(value.discovery_result_freeze_id),
        "discovery_dataset_id": str(value.discovery_dataset_id),
        "ledger_id": str(value.ledger_id),
        "candidate_slot_ids": [str(item) for item in value.candidate_slot_ids],
        "candidate_program_ids": [str(item) for item in value.candidate_program_ids],
        "candidate_fingerprints": list(value.candidate_fingerprints),
        "candidate_source_symbols": list(value.candidate_source_symbols),
        "candidate_bar_resolutions": [
            item.name for item in value.candidate_bar_resolutions
        ],
    }
    expected = uuid5(_CANDIDATE_FREEZE_NAMESPACE, _canonical_json(material).decode())
    return value.freeze_id == expected


def _open_dataset(
    stage: ResearchStage,
    bars: Iterable[IntradayBar],
    candidate_freeze: CandidateFreeze | None = None,
    sparse_custody_authority: SparseCustodyAuthority | None = None,
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
        sparse_custody_authority,
        _seal=_DATASET_SEAL,
    )


def open_discovery_dataset(bars: Iterable[IntradayBar]) -> ResearchDataset:
    return _open_dataset(ResearchStage.DISCOVERY, bars)


def _synthetic_sparse_custody_authority_for_test(
    validated: ValidatedUniverseBars,
) -> SparseCustodyAuthority:
    """Create deterministic test-only custody binding for synthetic bars."""

    input_digest = validated.input_digest
    semantic = sha256(
        _canonical_json(
            {
                "schema": SPARSE_CUSTODY_AUTHORITY_SCHEMA,
                "authority_kind": "SYNTHETIC_TEST",
                "input_digest": input_digest,
            }
        )
    ).hexdigest()
    normalized_hashes = []
    observed_counts = []
    observed_times = {}
    for symbol in INITIAL_UNIVERSE:
        csv_hash = sha256()
        csv_hash.update(b"timestamp,symbol,resolution,open,high,low,close,volume\n")
        stream = validated.by_symbol[symbol].bars
        for bar in stream:
            csv_hash.update(_normalized_custody_csv_row(bar))
        normalized_hashes.append((symbol, csv_hash.hexdigest()))
        observed_counts.append((symbol, len(stream)))
        observed_times[symbol] = frozenset(bar.timestamp for bar in stream)

    sessions = tuple(
        sorted(
            {
                session
                for symbol in INITIAL_UNIVERSE
                for session in validated.by_symbol[symbol].sessions
            }
        )
    )
    scheduled_slots = 0
    missing_counts = {symbol: 0 for symbol in INITIAL_UNIVERSE}
    missing_hashes = {symbol: sha256() for symbol in INITIAL_UNIVERSE}
    fully_missing_sessions = {symbol: 0 for symbol in INITIAL_UNIVERSE}
    common_missing = 0
    union_missing = 0
    for session in sessions:
        schedule = _SESSION_AUTHORITY.schedule_for(session)
        if schedule is None:
            raise Arch150Error("synthetic sparse session has no XNYS schedule")
        slot = schedule.opens_at.astimezone(UTC)
        close = schedule.closes_at.astimezone(UTC)
        per_session_scheduled = 0
        per_session_missing = {symbol: 0 for symbol in INITIAL_UNIVERSE}
        while slot < close:
            scheduled_slots += 1
            per_session_scheduled += 1
            absent = {
                symbol: slot not in observed_times[symbol]
                for symbol in INITIAL_UNIVERSE
            }
            if all(absent.values()):
                common_missing += 1
            if any(absent.values()):
                union_missing += 1
            for symbol in INITIAL_UNIVERSE:
                if absent[symbol]:
                    missing_counts[symbol] += 1
                    per_session_missing[symbol] += 1
                    missing_hashes[symbol].update(
                        _custody_timestamp_text(slot).encode("ascii") + b"\n"
                    )
            slot += timedelta(minutes=1)
        for symbol in INITIAL_UNIVERSE:
            if per_session_missing[symbol] == per_session_scheduled:
                fully_missing_sessions[symbol] += 1
    return _new_sparse_custody_authority(
        dataset_id=uuid5(_SPARSE_TEST_DATASET_NAMESPACE, input_digest),
        dataset_semantic_sha256=semantic,
        custody_id=uuid5(_SPARSE_TEST_DATASET_NAMESPACE, f"custody:{input_digest}"),
        custody_semantic_sha256=semantic,
        normalized_file_sha256_by_symbol=tuple(normalized_hashes),
        scheduled_slots_per_symbol=scheduled_slots,
        observed_counts_by_symbol=tuple(observed_counts),
        missing_counts_by_symbol=tuple(
            (symbol, missing_counts[symbol]) for symbol in INITIAL_UNIVERSE
        ),
        missing_timestamp_sha256_by_symbol=tuple(
            (symbol, missing_hashes[symbol].hexdigest()) for symbol in INITIAL_UNIVERSE
        ),
        common_missing_count=common_missing,
        union_missing_count=union_missing,
        fully_missing_session_counts_by_symbol=tuple(
            (symbol, fully_missing_sessions[symbol]) for symbol in INITIAL_UNIVERSE
        ),
        authority_kind="SYNTHETIC_TEST",
        source_input_digest=input_digest,
    )


def _open_sparse_discovery_dataset_for_test(
    bars: Iterable[IntradayBar],
) -> ResearchDataset:
    """Private fake-only seam; not used by an official G1 evaluation."""

    materialized = tuple(bars)
    if any(
        type(bar) is not IntradayBar
        or not DISCOVERY_START <= bar.session_date < DISCOVERY_END
        for bar in materialized
    ):
        raise InformationFirewallError("synthetic sparse input must be discovery-only")
    validated = validate_universe_minute_bars(materialized)
    authority = _synthetic_sparse_custody_authority_for_test(validated)
    return ResearchDataset(
        ResearchStage.DISCOVERY,
        validated,
        DISCOVERY_START,
        DISCOVERY_END,
        sparse_custody_authority=authority,
        _seal=_DATASET_SEAL,
    )


def open_sparse_discovery_dataset(
    bars: Iterable[IntradayBar],
) -> ResearchDataset:
    """Bind a materialized 2016-2023 stream to the accepted D1R commitments."""

    validated = _validate_accepted_sparse_custody(bars)
    discovery_bars = tuple(
        bar
        for symbol in INITIAL_UNIVERSE
        for bar in validated.by_symbol[symbol].bars
        if DISCOVERY_START <= bar.session_date < DISCOVERY_END
    )
    discovery = validate_universe_minute_bars(discovery_bars)
    return ResearchDataset(
        ResearchStage.DISCOVERY,
        discovery,
        DISCOVERY_START,
        DISCOVERY_END,
        sparse_custody_authority=_ACCEPTED_SPARSE_CUSTODY_AUTHORITY,
        _seal=_DATASET_SEAL,
    )


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
    reference_bar_timestamp: datetime
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


def _vwap_through(bars: Sequence[IntradayBar], index: int) -> Decimal | None:
    """Compute VWAP from observed positive-volume bars through this index."""

    with localcontext(_DECIMAL_CONTEXT):
        visible = tuple(bar for bar in bars[: index + 1] if bar.volume > 0)
        volume = sum(bar.volume for bar in visible)
        if volume == 0:
            return None
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
            if prior_bars[matching].volume == 0:
                return None
            prior_close = prior_bars[matching].close
            prior_vwap = _vwap_through(prior_bars, matching)
            if prior_vwap is None:
                return None
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
    if vwap is None:
        return None
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
    if vwap is None:
        return None
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
    if bars[index].volume == 0:
        return None
    if type(program) is OpeningRangeBreakoutReversalProgram:
        return _opening_range_signal(program, bars, index, resolution)
    confirmation = program.confirmation_bars
    if index + 1 < confirmation:
        return None
    first_index = index - confirmation + 1
    if any(
        bars[right].timestamp - bars[left].timestamp
        != timedelta(minutes=int(resolution))
        or bars[right].volume == 0
        or bars[left].volume == 0
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
        f"{REPLAY_SCHEMA}:{trade_material}:{side.value}:{filled_at.isoformat()}:"
        f"{bar.timestamp.isoformat()}",
    )
    return Fill(
        fill_id=fill_id,
        side=side,
        timestamp=filled_at,
        reference_bar_timestamp=bar.timestamp,
        reference_price=reference,
        execution_price=execution,
        quantity=quantity,
        slippage_bps=model.adverse_slippage_bps,
    )


def replay_program(
    program: IntradayProgram,
    bars: (
        ValidatedMinuteBars
        | DerivedFiveMinuteBars
        | SparseDerivedFiveMinuteBars
        | Iterable[IntradayBar]
    ),
    *,
    cost_case: CostCase | CostModel = CostCase.STRESS,
    initial_equity: Decimal = Decimal("1"),
) -> ReplayResult:
    """Low-level deterministic replay helper, not G1 campaign authority.

    Official G1 results must use ``evaluate_frozen_trial`` with the exact next
    slot from its pre-evaluation manifest-bound ledger.
    """

    if type(program) not in (
        NoiseAreaVwapMomentumProgram,
        VwapTrendReversalProgram,
        OpeningRangeBreakoutReversalProgram,
    ):
        raise UnsupportedProgramError("replay accepts only the closed typed grammar")
    if type(bars) is SparseDerivedFiveMinuteBars:
        validated_bars = _validate_sparse_derived_five_minute_bars(bars)
        symbol = bars.symbol
        input_digest = bars.source_digest
        resolution = BarResolution.FIVE_MINUTE
    elif type(bars) is DerivedFiveMinuteBars:
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
                if signal is not None and any(
                    candidate.volume > 0 for candidate in session_bars[index + 1 :]
                ):
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
            exit_index = max(
                index
                for index in range(entry_index + 1, len(session_bars))
                if session_bars[index].volume > 0
            )
            for candidate_index in range(entry_index + 1, len(session_bars)):
                candidate = session_bars[candidate_index]
                if candidate.volume == 0:
                    continue
                candidate_vwap = _vwap_through(session_bars, candidate_index)
                should_exit = False
                if (
                    type(program) is VwapTrendReversalProgram
                    and candidate_vwap is not None
                ):
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


def _compute_published_stage_frequency_diagnostics(
    trades: Iterable[Trade],
    *,
    stage: ResearchStage,
    cost_case: CostCase = CostCase.STRESS,
) -> FrequencyDiagnostics:
    if stage not in (
        ResearchStage.VALIDATION,
        ResearchStage.HOLDOUT,
        ResearchStage.RECENT_EXTENSION,
    ):
        raise InformationFirewallError(
            "frequency diagnostics require an authorized stage"
        )
    start, end = _stage_window(stage)
    sessions = tuple(
        session
        for session in _SESSION_AUTHORITY.published.sessions
        if start <= session < end
    )
    if not sessions:
        raise Arch150Error("published stage has no regular XNYS sessions")
    session_set = frozenset(sessions)
    materialized = tuple(trades)
    if any(
        type(trade) is not Trade or trade.session not in session_set
        for trade in materialized
    ):
        raise InformationFirewallError("trade falls outside the frozen stage sessions")
    years = tuple(sorted({session.year for session in sessions}))
    return compute_frequency_diagnostics(
        materialized,
        validation_years=years,
        regular_sessions=len(sessions),
        cost_case=cost_case,
    )


def compute_validation_frequency_diagnostics(
    trades: Iterable[Trade],
    *,
    cost_case: CostCase = CostCase.STRESS,
) -> FrequencyDiagnostics:
    """Use all published 2021-2023 sessions as the official denominator."""

    return _compute_published_stage_frequency_diagnostics(
        trades,
        stage=ResearchStage.VALIDATION,
        cost_case=cost_case,
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

    def __post_init__(self) -> None:
        if type(self.family) is not StrategyFamily:
            raise TypeError("invalid trial family must be a StrategyFamily")
        if (
            type(self.caller_semantic_fingerprint) is not str
            or not self.caller_semantic_fingerprint.strip()
        ):
            raise ValueError("invalid trial semantic fingerprint must be nonempty")
        if type(self.diagnostic_code) is not str or not self.diagnostic_code.strip():
            raise ValueError("invalid trial diagnostic code must be nonempty")

    @property
    def program_id(self) -> None:
        return None

    @property
    def semantic_fingerprint(self) -> str:
        return self.caller_semantic_fingerprint


type TrialProgram = IntradayProgram | InvalidTrialReference


@dataclass(frozen=True, slots=True)
class G1TrialSpecification:
    """A typed proposal and the source identity frozen before evaluation."""

    program: TrialProgram
    source_symbol: str
    bar_resolution: BarResolution

    def __post_init__(self) -> None:
        if not (
            _is_intraday_program(self.program)
            or type(self.program) is InvalidTrialReference
        ):
            raise UnsupportedProgramError(
                "G1 trial specifications require the closed typed grammar"
            )
        if (
            type(self.source_symbol) is not str
            or self.source_symbol not in INITIAL_UNIVERSE
        ):
            raise ValueError("G1 source symbol must be SPY or QQQ")
        if type(self.bar_resolution) is not BarResolution:
            raise TypeError("G1 bar resolution must be a BarResolution")


@dataclass(frozen=True, slots=True)
class TrialRecord:
    trial_ordinal: int
    trial_id: UUID
    slot_id: UUID
    discovery_dataset_id: UUID
    source_symbol: str
    bar_resolution: BarResolution
    family: StrategyFamily
    program_id: UUID | None
    semantic_fingerprint: str
    result_id: UUID
    evaluation_id: UUID
    replay_id: UUID | None
    disposition: TrialDisposition
    diagnostic_code: str | None


def _is_intraday_program(value: object) -> bool:
    return type(value) in (
        NoiseAreaVwapMomentumProgram,
        VwapTrendReversalProgram,
        OpeningRangeBreakoutReversalProgram,
    )


def _proposal_material(
    proposal: TrialProgram,
    source_symbol: str,
    bar_resolution: BarResolution,
) -> dict[str, object]:
    material: dict[str, object] = {
        "source_symbol": source_symbol,
        "bar_resolution": bar_resolution.name,
    }
    if _is_intraday_program(proposal):
        program = proposal
        material.update(
            {
                "kind": "TYPED_PROGRAM",
                "family": program.family.value,
                "semantic_fingerprint": program_fingerprint(program),
                "program_id": str(program_id(program)),
            }
        )
    elif type(proposal) is InvalidTrialReference:
        material.update(
            {
                "kind": "INVALID_ATTEMPT",
                "family": proposal.family.value,
                "semantic_fingerprint": proposal.semantic_fingerprint,
                "program_id": None,
                "diagnostic_code": proposal.diagnostic_code,
            }
        )
    else:
        raise UnsupportedProgramError(
            "G1 proposals must be typed programs or explicit invalid references"
        )
    return material


def _slot_material(slot: FrozenTrialSlot) -> dict[str, object]:
    if slot.invalid_reference is not None:
        proposal: TrialProgram = slot.invalid_reference
    elif slot._program is not None:
        proposal = slot._program
    else:
        raise InformationFirewallError("frozen G1 slot lost its proposal binding")
    return _proposal_material(proposal, slot.source_symbol, slot.bar_resolution)


def _manifest_is_valid(manifest: G1PopulationManifest | None) -> bool:
    if not (
        type(manifest) is G1PopulationManifest
        and manifest._authority_seal is _G1_MANIFEST_SEAL
        and isinstance(manifest.slots, tuple)
        and 1 <= len(manifest.slots) <= G1_TOTAL_TRIAL_LIMIT
    ):
        return False
    proposal_material: list[dict[str, object]] = []
    counts = {family: 0 for family in StrategyFamily}
    for ordinal, slot in enumerate(manifest.slots, 1):
        if not (
            type(slot) is FrozenTrialSlot
            and slot._authority_seal is _G1_SLOT_SEAL
            and slot.manifest_id == manifest.manifest_id
            and slot.ordinal == ordinal
            and type(slot.source_symbol) is str
            and slot.source_symbol in INITIAL_UNIVERSE
            and type(slot.bar_resolution) is BarResolution
        ):
            return False
        try:
            material = _slot_material(slot)
        except (Arch150Error, TypeError, ValueError):
            return False
        if (
            slot.family.value != material["family"]
            or slot.source_symbol != material["source_symbol"]
            or slot.bar_resolution.name != material["bar_resolution"]
            or slot.semantic_fingerprint != material["semantic_fingerprint"]
            or (str(slot.program_id) if slot.program_id else None)
            != material["program_id"]
        ):
            return False
        expected_slot_id = uuid5(
            _G1_SLOT_NAMESPACE,
            _canonical_json(
                {
                    "schema": G1_POPULATION_SCHEMA,
                    "manifest_id": str(manifest.manifest_id),
                    "ordinal": ordinal,
                    "proposal": material,
                }
            ).decode(),
        )
        if slot.slot_id != expected_slot_id:
            return False
        counts[slot.family] += 1
        proposal_material.append(material)
    if any(count > G1_FAMILY_TRIAL_LIMIT for count in counts.values()):
        return False
    expected_manifest_id = uuid5(
        _G1_MANIFEST_NAMESPACE,
        _canonical_json(
            {"schema": G1_POPULATION_SCHEMA, "proposals": proposal_material}
        ).decode(),
    )
    return manifest.manifest_id == expected_manifest_id


def _freeze_g1_population(
    specifications: tuple[G1TrialSpecification, ...],
) -> G1PopulationManifest:
    materialized = specifications
    if not materialized:
        raise TrialBudgetExceeded("G1 population must contain at least one proposal")
    if len(materialized) > G1_TOTAL_TRIAL_LIMIT:
        raise TrialBudgetExceeded("G1 total trial budget is 24")
    counts = {family: 0 for family in StrategyFamily}
    proposal_material: list[dict[str, object]] = []
    for specification in materialized:
        if type(specification) is not G1TrialSpecification:
            raise UnsupportedProgramError("G1 population requires trial specifications")
        item = _proposal_material(
            specification.program,
            specification.source_symbol,
            specification.bar_resolution,
        )
        family = StrategyFamily(item["family"])
        counts[family] += 1
        if counts[family] > G1_FAMILY_TRIAL_LIMIT:
            raise TrialBudgetExceeded("G1 family trial budget is 8")
        proposal_material.append(item)
    manifest_id = uuid5(
        _G1_MANIFEST_NAMESPACE,
        _canonical_json(
            {"schema": G1_POPULATION_SCHEMA, "proposals": proposal_material}
        ).decode(),
    )
    slots: list[FrozenTrialSlot] = []
    for ordinal, (proposal, material) in enumerate(
        zip(materialized, proposal_material, strict=True), 1
    ):
        slot_id = uuid5(
            _G1_SLOT_NAMESPACE,
            _canonical_json(
                {
                    "schema": G1_POPULATION_SCHEMA,
                    "manifest_id": str(manifest_id),
                    "ordinal": ordinal,
                    "proposal": material,
                }
            ).decode(),
        )
        if type(proposal.program) is InvalidTrialReference:
            family = proposal.program.family
            fingerprint = proposal.program.semantic_fingerprint
            identifier = None
            invalid_reference = proposal.program
            program = None
        else:
            program = proposal.program
            family = program.family
            fingerprint = program_fingerprint(program)
            identifier = program_id(program)
            invalid_reference = None
        slots.append(
            FrozenTrialSlot(
                manifest_id,
                slot_id,
                ordinal,
                family,
                proposal.source_symbol,
                proposal.bar_resolution,
                fingerprint,
                identifier,
                invalid_reference,
                program,
                _seal=_G1_SLOT_SEAL,
            )
        )
    manifest = G1PopulationManifest(manifest_id, tuple(slots), _seal=_G1_MANIFEST_SEAL)
    if not _manifest_is_valid(manifest):
        raise InformationFirewallError("G1 population manifest failed validation")
    return manifest


def _freeze_g1_population_for_test(
    specifications: Iterable[G1TrialSpecification],
) -> G1PopulationManifest:
    """Private synthetic seam for bounded noncanonical populations."""

    return _freeze_g1_population(tuple(specifications))


def _canonical_g1_trial_specifications() -> tuple[G1TrialSpecification, ...]:
    programs: tuple[IntradayProgram, ...] = (
        NoiseAreaVwapMomentumProgram(3, Decimal("10"), 1, 15),
        NoiseAreaVwapMomentumProgram(5, Decimal("20"), 2, 30),
        NoiseAreaVwapMomentumProgram(10, Decimal("35"), 2, 45),
        NoiseAreaVwapMomentumProgram(20, Decimal("50"), 3, 60),
        VwapTrendReversalProgram(
            Decimal("10"),
            VwapStrategyMode.CONTINUATION,
            VwapReferenceSide.ABOVE,
            1,
            15,
            5,
        ),
        VwapTrendReversalProgram(
            Decimal("10"),
            VwapStrategyMode.CONTINUATION,
            VwapReferenceSide.BELOW,
            1,
            15,
            5,
        ),
        VwapTrendReversalProgram(
            Decimal("35"),
            VwapStrategyMode.BOUNDED_REVERSAL,
            VwapReferenceSide.ABOVE,
            2,
            20,
            10,
        ),
        VwapTrendReversalProgram(
            Decimal("35"),
            VwapStrategyMode.BOUNDED_REVERSAL,
            VwapReferenceSide.BELOW,
            2,
            20,
            10,
        ),
        OpeningRangeBreakoutReversalProgram(
            5, OpeningRangeDirection.CONTINUATION, 0, 10
        ),
        OpeningRangeBreakoutReversalProgram(
            15, OpeningRangeDirection.CONTINUATION, 1, 20
        ),
        OpeningRangeBreakoutReversalProgram(15, OpeningRangeDirection.REVERSAL, 1, 20),
        OpeningRangeBreakoutReversalProgram(30, OpeningRangeDirection.REVERSAL, 2, 30),
    )
    return tuple(
        G1TrialSpecification(program, symbol, BarResolution.ONE_MINUTE)
        for program in programs
        for symbol in INITIAL_UNIVERSE
    )


def freeze_g1_population() -> G1PopulationManifest:
    """Return the source-owned canonical 24-slot Architecture-150 G1 manifest."""

    manifest = _freeze_g1_population(_canonical_g1_trial_specifications())
    if (
        len(manifest.slots) != G1_TOTAL_TRIAL_LIMIT
        or any(
            slot.bar_resolution is not BarResolution.ONE_MINUTE
            for slot in manifest.slots
        )
        or {slot.source_symbol for slot in manifest.slots} != set(INITIAL_UNIVERSE)
        or sum(slot.source_symbol == "SPY" for slot in manifest.slots) != 12
        or sum(slot.source_symbol == "QQQ" for slot in manifest.slots) != 12
        or any(
            sum(slot.family is family for slot in manifest.slots)
            != G1_FAMILY_TRIAL_LIMIT
            for family in StrategyFamily
        )
    ):
        raise InformationFirewallError("canonical G1 population contract drift")
    return manifest


def _evaluation_identity_material(
    manifest_id: UUID,
    slot_id: UUID,
    discovery_dataset_id: UUID,
    source_symbol: str,
    bar_resolution: BarResolution,
    replay_id: UUID | None,
    fixed_disposition: TrialDisposition | None,
    diagnostic_code: str | None,
) -> dict[str, object]:
    return {
        "schema": G1_RESULT_SCHEMA,
        "manifest_id": str(manifest_id),
        "slot_id": str(slot_id),
        "discovery_dataset_id": str(discovery_dataset_id),
        "source_symbol": source_symbol,
        "bar_resolution": bar_resolution.name,
        "qualification_cost_case": CostCase.STRESS.value,
        "replay_id": str(replay_id) if replay_id else None,
        "fixed_disposition": (
            fixed_disposition.value if fixed_disposition is not None else None
        ),
        "diagnostic_code": diagnostic_code,
    }


@dataclass(frozen=True, slots=True, init=False)
class G1TrialEvaluation:
    """Official result for exactly one currently authorized frozen slot."""

    manifest_id: UUID
    slot_id: UUID
    discovery_dataset_id: UUID
    source_symbol: str
    bar_resolution: BarResolution
    evaluation_id: UUID
    replay_result: ReplayResult | None
    fixed_disposition: TrialDisposition | None
    diagnostic_code: str | None
    _authority_seal: object = field(repr=False, compare=False)

    def __init__(
        self,
        manifest_id: UUID,
        slot_id: UUID,
        discovery_dataset_id: UUID,
        source_symbol: str,
        bar_resolution: BarResolution,
        evaluation_id: UUID,
        replay_result: ReplayResult | None,
        fixed_disposition: TrialDisposition | None,
        diagnostic_code: str | None,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _G1_RESULT_SEAL:
            raise InformationFirewallError(
                "G1 evaluations must come from the frozen-slot evaluator"
            )
        for name, value in (
            ("manifest_id", manifest_id),
            ("slot_id", slot_id),
            ("discovery_dataset_id", discovery_dataset_id),
            ("source_symbol", source_symbol),
            ("bar_resolution", bar_resolution),
            ("evaluation_id", evaluation_id),
            ("replay_result", replay_result),
            ("fixed_disposition", fixed_disposition),
            ("diagnostic_code", diagnostic_code),
        ):
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_authority_seal", _seal)


def _evaluation_is_valid(evaluation: G1TrialEvaluation, slot: FrozenTrialSlot) -> bool:
    if not (
        type(evaluation) is G1TrialEvaluation
        and evaluation._authority_seal is _G1_RESULT_SEAL
        and evaluation.manifest_id == slot.manifest_id
        and evaluation.slot_id == slot.slot_id
        and evaluation.source_symbol == slot.source_symbol
        and evaluation.bar_resolution is slot.bar_resolution
    ):
        return False
    replay = evaluation.replay_result
    if replay is not None and (
        type(replay) is not ReplayResult
        or slot.program_id is None
        or replay.program_id != slot.program_id
    ):
        return False
    if evaluation.fixed_disposition is None:
        if replay is None or not replay.trades:
            return False
        if evaluation.diagnostic_code is not None:
            return False
    elif evaluation.fixed_disposition is TrialDisposition.INVALID:
        if (
            slot.invalid_reference is None
            or evaluation.replay_result is not None
            or evaluation.diagnostic_code != slot.invalid_reference.diagnostic_code
        ):
            return False
    elif evaluation.fixed_disposition is TrialDisposition.DUPLICATE:
        if (
            slot.program_id is None
            or evaluation.diagnostic_code != "DUPLICATE_SEMANTIC_PROGRAM"
        ):
            return False
    elif evaluation.fixed_disposition is TrialDisposition.ZERO_TRADE:
        if replay is None or replay.trades or evaluation.diagnostic_code is not None:
            return False
    elif evaluation.fixed_disposition is TrialDisposition.FAILED:
        if replay is not None or evaluation.diagnostic_code is None:
            return False
    else:
        return False
    expected = uuid5(
        _G1_RESULT_NAMESPACE,
        _canonical_json(
            _evaluation_identity_material(
                evaluation.manifest_id,
                evaluation.slot_id,
                evaluation.discovery_dataset_id,
                evaluation.source_symbol,
                evaluation.bar_resolution,
                replay.replay_id if replay is not None else None,
                evaluation.fixed_disposition,
                evaluation.diagnostic_code,
            )
        ).decode(),
    )
    return evaluation.evaluation_id == expected


def _make_g1_evaluation(
    slot: FrozenTrialSlot,
    discovery_dataset_id: UUID,
    replay_result: ReplayResult | None,
    fixed_disposition: TrialDisposition | None,
    diagnostic_code: str | None,
) -> G1TrialEvaluation:
    material = _evaluation_identity_material(
        slot.manifest_id,
        slot.slot_id,
        discovery_dataset_id,
        slot.source_symbol,
        slot.bar_resolution,
        replay_result.replay_id if replay_result is not None else None,
        fixed_disposition,
        diagnostic_code,
    )
    return G1TrialEvaluation(
        slot.manifest_id,
        slot.slot_id,
        discovery_dataset_id,
        slot.source_symbol,
        slot.bar_resolution,
        uuid5(_G1_RESULT_NAMESPACE, _canonical_json(material).decode()),
        replay_result,
        fixed_disposition,
        diagnostic_code,
        _seal=_G1_RESULT_SEAL,
    )


class TrialLedger:
    """Immutable terminal results for one exact pre-evaluation G1 manifest."""

    __slots__ = ("_manifest", "_records")

    def __init__(
        self,
        manifest: G1PopulationManifest,
        records: Iterable[TrialRecord] = (),
        *,
        _seal: object = None,
    ) -> None:
        materialized = tuple(records)
        if not _manifest_is_valid(manifest):
            raise InformationFirewallError("trial ledger needs a frozen G1 manifest")
        if materialized and _seal is not _TRIAL_LEDGER_SEAL:
            raise InformationFirewallError(
                "nonempty trial ledgers must come from frozen-slot consumption"
            )
        if len(materialized) > len(manifest.slots):
            raise TrialBudgetExceeded("ledger cannot exceed its frozen G1 slots")
        for ordinal, record in enumerate(materialized, 1):
            slot = manifest.slots[ordinal - 1]
            if (
                type(record) is not TrialRecord
                or record.trial_ordinal != ordinal
                or record.slot_id != slot.slot_id
                or record.family is not slot.family
                or record.source_symbol != slot.source_symbol
                or record.bar_resolution is not slot.bar_resolution
                or record.program_id != slot.program_id
                or record.semantic_fingerprint != slot.semantic_fingerprint
            ):
                raise InformationFirewallError(
                    "trial ledger records must consume manifest slots in order"
                )
            if (
                materialized
                and record.discovery_dataset_id != materialized[0].discovery_dataset_id
            ):
                raise InformationFirewallError(
                    "all G1 results must use one discovery dataset"
                )
        object.__setattr__(self, "_manifest", manifest)
        object.__setattr__(self, "_records", materialized)

    def __setattr__(self, name: str, value: object) -> None:
        if hasattr(self, name):
            raise AttributeError("trial ledger records are immutable")
        object.__setattr__(self, name, value)

    @property
    def manifest(self) -> G1PopulationManifest:
        return self._manifest

    @property
    def records(self) -> tuple[TrialRecord, ...]:
        return self._records

    @property
    def consumed_trial_count(self) -> int:
        return len(self._records)

    @property
    def is_complete(self) -> bool:
        return self.consumed_trial_count == len(self._manifest.slots)

    @property
    def discovery_dataset_id(self) -> UUID | None:
        if not self._records:
            return None
        return self._records[0].discovery_dataset_id

    @property
    def next_slot(self) -> FrozenTrialSlot | None:
        if self.is_complete:
            return None
        return self._manifest.slots[self.consumed_trial_count]

    @property
    def family_counts(self) -> Mapping[StrategyFamily, int]:
        counts = {family: 0 for family in StrategyFamily}
        for record in self._records:
            counts[record.family] += 1
        return counts

    @property
    def ledger_id(self) -> UUID:
        material = {
            "schema": TRIAL_LEDGER_SCHEMA,
            "population_manifest_id": str(self._manifest.manifest_id),
            "slot_ids": [str(slot.slot_id) for slot in self._manifest.slots],
            "records": [
                {
                    "ordinal": record.trial_ordinal,
                    "trial_id": str(record.trial_id),
                    "slot_id": str(record.slot_id),
                    "discovery_dataset_id": str(record.discovery_dataset_id),
                    "source_symbol": record.source_symbol,
                    "bar_resolution": record.bar_resolution.name,
                    "result_id": str(record.result_id),
                    "evaluation_id": str(record.evaluation_id),
                    "replay_id": str(record.replay_id) if record.replay_id else None,
                    "disposition": record.disposition.value,
                    "diagnostic_code": record.diagnostic_code,
                }
                for record in self._records
            ],
        }
        return uuid5(_TRIAL_NAMESPACE, _canonical_json(material).decode())

    def consume(
        self,
        evaluation: G1TrialEvaluation,
    ) -> TrialLedger:
        slot = self.next_slot
        if slot is None:
            raise TrialBudgetExceeded("all frozen G1 proposal slots are consumed")
        if not _evaluation_is_valid(evaluation, slot):
            raise InformationFirewallError(
                "trial result is not authorized for the next frozen population slot"
            )
        if (
            evaluation.discovery_dataset_id != self.discovery_dataset_id
            and self.discovery_dataset_id is not None
        ):
            raise InformationFirewallError(
                "all G1 results must use one discovery dataset"
            )
        fixed = evaluation.fixed_disposition
        if fixed is not None:
            terminal_disposition = fixed
        else:
            if evaluation.replay_result is None or not evaluation.replay_result.trades:
                raise InformationFirewallError(
                    "G1 advancement requires a nonzero STRESS discovery replay"
                )
            terminal_disposition = TrialDisposition.SHORTLISTED
        diagnostic_code = evaluation.diagnostic_code
        replay_id = (
            evaluation.replay_result.replay_id
            if evaluation.replay_result is not None
            else None
        )
        result_material = {
            "schema": G1_RESULT_SCHEMA,
            "manifest_id": str(self._manifest.manifest_id),
            "slot_id": str(slot.slot_id),
            "discovery_dataset_id": str(evaluation.discovery_dataset_id),
            "source_symbol": evaluation.source_symbol,
            "bar_resolution": evaluation.bar_resolution.name,
            "evaluation_id": str(evaluation.evaluation_id),
            "replay_id": str(replay_id) if replay_id else None,
            "disposition": terminal_disposition.value,
            "diagnostic_code": diagnostic_code,
        }
        result_id = uuid5(
            _G1_RESULT_NAMESPACE, _canonical_json(result_material).decode()
        )
        trial_id = uuid5(
            _TRIAL_NAMESPACE,
            _canonical_json(
                {
                    "schema": TRIAL_LEDGER_SCHEMA,
                    "manifest_id": str(self._manifest.manifest_id),
                    "ordinal": slot.ordinal,
                    "slot_id": str(slot.slot_id),
                    "result_id": str(result_id),
                }
            ).decode(),
        )
        record = TrialRecord(
            slot.ordinal,
            trial_id,
            slot.slot_id,
            evaluation.discovery_dataset_id,
            evaluation.source_symbol,
            evaluation.bar_resolution,
            slot.family,
            slot.program_id,
            slot.semantic_fingerprint,
            result_id,
            evaluation.evaluation_id,
            replay_id,
            terminal_disposition,
            diagnostic_code,
        )
        return TrialLedger(
            self._manifest,
            (*self._records, record),
            _seal=_TRIAL_LEDGER_SEAL,
        )

    def to_bytes(self) -> bytes:
        return _canonical_json(
            {
                "schema": TRIAL_LEDGER_SCHEMA,
                "population_manifest_id": str(self._manifest.manifest_id),
                "slot_ids": [str(slot.slot_id) for slot in self._manifest.slots],
                "ledger_id": str(self.ledger_id),
                "is_complete": self.is_complete,
                "records": [
                    {
                        "trial_ordinal": record.trial_ordinal,
                        "trial_id": str(record.trial_id),
                        "slot_id": str(record.slot_id),
                        "discovery_dataset_id": str(record.discovery_dataset_id),
                        "source_symbol": record.source_symbol,
                        "bar_resolution": record.bar_resolution.name,
                        "family": record.family.value,
                        "program_id": (
                            str(record.program_id) if record.program_id else None
                        ),
                        "semantic_fingerprint": record.semantic_fingerprint,
                        "result_id": str(record.result_id),
                        "evaluation_id": str(record.evaluation_id),
                        "replay_id": (
                            str(record.replay_id) if record.replay_id else None
                        ),
                        "disposition": record.disposition.value,
                        "diagnostic_code": record.diagnostic_code,
                    }
                    for record in self._records
                ],
            }
        )


def _evaluate_frozen_trial_common(
    ledger: TrialLedger,
    slot: FrozenTrialSlot,
    discovery_dataset: ResearchDataset,
    *,
    require_accepted_sparse_custody: bool,
    initial_equity: Decimal = Decimal("1"),
) -> G1TrialEvaluation:
    """Evaluate only the next manifest slot through official G1 campaign authority."""

    if type(ledger) is not TrialLedger or not _manifest_is_valid(ledger.manifest):
        raise InformationFirewallError("G1 evaluation requires a bound trial ledger")
    if (
        type(discovery_dataset) is not ResearchDataset
        or discovery_dataset._authority_seal is not _DATASET_SEAL
        or discovery_dataset.stage is not ResearchStage.DISCOVERY
    ):
        raise InformationFirewallError(
            "official G1 evaluation requires an opened discovery dataset"
        )
    if (
        require_accepted_sparse_custody
        and discovery_dataset._sparse_custody_authority
        is not _ACCEPTED_SPARSE_CUSTODY_AUTHORITY
    ):
        raise InformationFirewallError(
            "official G1 evaluation requires accepted sparse custody binding"
        )
    if require_accepted_sparse_custody and (
        ledger.manifest.manifest_id != freeze_g1_population().manifest_id
    ):
        raise InformationFirewallError(
            "official G1 evaluation requires the canonical source-owned population"
        )
    discovery_dataset_id = _discovery_dataset_id(discovery_dataset)
    if (
        ledger.discovery_dataset_id is not None
        and ledger.discovery_dataset_id != discovery_dataset_id
    ):
        raise InformationFirewallError("all G1 results must use one discovery dataset")
    next_slot = ledger.next_slot
    if next_slot is None:
        raise TrialBudgetExceeded("all frozen G1 proposal slots are consumed")
    if (
        type(slot) is not FrozenTrialSlot
        or slot._authority_seal is not _G1_SLOT_SEAL
        or slot.manifest_id != ledger.manifest.manifest_id
        or slot.slot_id != next_slot.slot_id
    ):
        raise InformationFirewallError(
            "G1 evaluation requires the exact next frozen population slot"
        )
    if slot.invalid_reference is not None:
        return _make_g1_evaluation(
            slot,
            discovery_dataset_id,
            None,
            TrialDisposition.INVALID,
            slot.invalid_reference.diagnostic_code,
        )
    if slot._program is None or slot.program_id is None:
        raise InformationFirewallError("frozen typed program binding is incomplete")
    if any(
        record.semantic_fingerprint == slot.semantic_fingerprint
        and record.source_symbol == slot.source_symbol
        and record.bar_resolution is slot.bar_resolution
        and record.program_id is not None
        for record in ledger.records
    ):
        return _make_g1_evaluation(
            slot,
            discovery_dataset_id,
            None,
            TrialDisposition.DUPLICATE,
            "DUPLICATE_SEMANTIC_PROGRAM",
        )
    bars = discovery_dataset.bars.by_symbol[slot.source_symbol]
    if any(bar.resolution is not slot.bar_resolution for bar in bars.bars):
        raise InformationFirewallError(
            "G1 trial resolution does not match its discovery source bars"
        )
    try:
        replay = replay_program(
            slot._program,
            bars,
            cost_case=CostCase.STRESS,
            initial_equity=initial_equity,
        )
    except (Arch150Error, ValueError) as exc:
        return _make_g1_evaluation(
            slot,
            discovery_dataset_id,
            None,
            TrialDisposition.FAILED,
            f"REPLAY_{type(exc).__name__.upper()}",
        )
    if not replay.trades:
        return _make_g1_evaluation(
            slot,
            discovery_dataset_id,
            replay,
            TrialDisposition.ZERO_TRADE,
            None,
        )
    return _make_g1_evaluation(slot, discovery_dataset_id, replay, None, None)


def evaluate_frozen_trial(
    ledger: TrialLedger,
    slot: FrozenTrialSlot,
    discovery_dataset: ResearchDataset,
    *,
    initial_equity: Decimal = Decimal("1"),
) -> G1TrialEvaluation:
    """Official G1 evaluation requires the accepted D1R sparse custody bind."""

    return _evaluate_frozen_trial_common(
        ledger,
        slot,
        discovery_dataset,
        require_accepted_sparse_custody=True,
        initial_equity=initial_equity,
    )


def _evaluate_frozen_trial_for_test(
    ledger: TrialLedger,
    slot: FrozenTrialSlot,
    discovery_dataset: ResearchDataset,
    *,
    initial_equity: Decimal = Decimal("1"),
) -> G1TrialEvaluation:
    """Private synthetic-only G1 seam for deterministic contract tests."""

    return _evaluate_frozen_trial_common(
        ledger,
        slot,
        discovery_dataset,
        require_accepted_sparse_custody=False,
        initial_equity=initial_equity,
    )


def _discovery_dataset_id(discovery_dataset: ResearchDataset) -> UUID:
    custody = discovery_dataset._sparse_custody_authority
    discovery_material = {
        "stage": discovery_dataset.stage.value,
        "start": discovery_dataset.start.isoformat(),
        "end_exclusive": discovery_dataset.end_exclusive.isoformat(),
        "input_digest": discovery_dataset.bars.input_digest,
        "sparse_custody": (
            None
            if custody is None
            else {
                "dataset_id": str(custody.dataset_id),
                "dataset_semantic_sha256": custody.dataset_semantic_sha256,
                "custody_id": str(custody.custody_id),
                "custody_semantic_sha256": custody.custody_semantic_sha256,
                "authority_kind": custody.authority_kind,
                "source_input_digest": custody._source_input_digest,
            }
        ),
    }
    return uuid5(
        _DISCOVERY_DATASET_NAMESPACE,
        _canonical_json(discovery_material).decode(),
    )


def _discovery_result_material(
    population_manifest_id: UUID,
    discovery_dataset_id: UUID,
    ledger_id: UUID,
    slot_ids: tuple[UUID, ...],
    result_ids: tuple[UUID, ...],
) -> dict[str, object]:
    return {
        "schema": DISCOVERY_RESULT_SCHEMA,
        "population_manifest_id": str(population_manifest_id),
        "discovery_dataset_id": str(discovery_dataset_id),
        "ledger_id": str(ledger_id),
        "slot_ids": [str(item) for item in slot_ids],
        "result_ids": [str(item) for item in result_ids],
    }


def _discovery_result_freeze_is_valid(
    value: DiscoveryResultFreeze, ledger: TrialLedger
) -> bool:
    if not (
        type(value) is DiscoveryResultFreeze
        and value._authority_seal is _DISCOVERY_RESULT_SEAL
        and type(ledger) is TrialLedger
        and ledger.is_complete
        and value.population_manifest_id == ledger.manifest.manifest_id
        and value.discovery_dataset_id == ledger.discovery_dataset_id
        and value.ledger_id == ledger.ledger_id
        and value.slot_ids == tuple(slot.slot_id for slot in ledger.manifest.slots)
        and value.result_ids == tuple(record.result_id for record in ledger.records)
        and len(value.slot_ids) == len(value.result_ids)
    ):
        return False
    expected = uuid5(
        _DISCOVERY_RESULT_NAMESPACE,
        _canonical_json(
            _discovery_result_material(
                value.population_manifest_id,
                value.discovery_dataset_id,
                value.ledger_id,
                value.slot_ids,
                value.result_ids,
            )
        ).decode(),
    )
    return value.freeze_id == expected


def finalize_discovery_population(
    discovery_dataset: ResearchDataset,
    ledger: TrialLedger,
) -> DiscoveryResultFreeze:
    """Bind completed G1 results to their frozen manifest and discovery input."""

    if (
        type(discovery_dataset) is not ResearchDataset
        or discovery_dataset._authority_seal is not _DATASET_SEAL
        or discovery_dataset.stage is not ResearchStage.DISCOVERY
        or type(ledger) is not TrialLedger
        or not ledger.is_complete
    ):
        raise InformationFirewallError(
            "discovery finalization requires an opened discovery dataset and one "
            "terminal result for every frozen G1 proposal"
        )
    discovery_dataset_id = _discovery_dataset_id(discovery_dataset)
    if ledger.discovery_dataset_id != discovery_dataset_id:
        raise InformationFirewallError(
            "completed G1 results are bound to a different discovery dataset"
        )
    slot_ids = tuple(slot.slot_id for slot in ledger.manifest.slots)
    result_ids = tuple(record.result_id for record in ledger.records)
    material = _discovery_result_material(
        ledger.manifest.manifest_id,
        discovery_dataset_id,
        ledger.ledger_id,
        slot_ids,
        result_ids,
    )
    freeze_id = uuid5(_DISCOVERY_RESULT_NAMESPACE, _canonical_json(material).decode())
    return DiscoveryResultFreeze(
        freeze_id,
        ledger.manifest.manifest_id,
        discovery_dataset_id,
        ledger.ledger_id,
        slot_ids,
        result_ids,
        _seal=_DISCOVERY_RESULT_SEAL,
    )


def freeze_candidate_population(
    discovery_result_freeze: DiscoveryResultFreeze,
    ledger: TrialLedger,
    candidate_slot_ids: Iterable[UUID],
) -> CandidateFreeze:
    """Freeze shortlisted slots without erasing their source or resolution."""

    if not _discovery_result_freeze_is_valid(discovery_result_freeze, ledger):
        raise InformationFirewallError(
            "candidate freeze requires the completed exact G1 result ledger"
        )
    records_by_slot = {record.slot_id: record for record in ledger.records}
    slots_by_id = {slot.slot_id: slot for slot in ledger.manifest.slots}
    materialized = tuple(candidate_slot_ids)
    candidate_slots: list[FrozenTrialSlot] = []
    for slot_id in materialized:
        if type(slot_id) is not UUID:
            raise InformationFirewallError(
                "candidate freeze requires originating frozen slot identities"
            )
        slot = slots_by_id.get(slot_id)
        record = records_by_slot.get(slot_id)
        if (
            slot is None
            or record is None
            or record.disposition is not TrialDisposition.SHORTLISTED
            or record.program_id is None
        ):
            raise InformationFirewallError(
                "candidate slot was not shortlisted in the completed discovery ledger"
            )
        candidate_slots.append(slot)
    slot_ids = tuple(slot.slot_id for slot in candidate_slots)
    if not candidate_slots or len(set(slot_ids)) != len(slot_ids):
        raise InformationFirewallError(
            "candidate freeze requires a nonempty unique frozen population subset"
        )
    candidate_ids = tuple(slot.program_id for slot in candidate_slots)
    fingerprints = tuple(slot.semantic_fingerprint for slot in candidate_slots)
    source_symbols = tuple(slot.source_symbol for slot in candidate_slots)
    resolutions = tuple(slot.bar_resolution for slot in candidate_slots)
    identity_material = {
        "schema": CANDIDATE_FREEZE_SCHEMA,
        "population_manifest_id": str(discovery_result_freeze.population_manifest_id),
        "discovery_result_freeze_id": str(discovery_result_freeze.freeze_id),
        "discovery_dataset_id": str(discovery_result_freeze.discovery_dataset_id),
        "ledger_id": str(ledger.ledger_id),
        "candidate_slot_ids": [str(item) for item in slot_ids],
        "candidate_program_ids": [str(item) for item in candidate_ids],
        "candidate_fingerprints": list(fingerprints),
        "candidate_source_symbols": list(source_symbols),
        "candidate_bar_resolutions": [item.name for item in resolutions],
    }
    freeze_id = uuid5(
        _CANDIDATE_FREEZE_NAMESPACE, _canonical_json(identity_material).decode()
    )
    return CandidateFreeze(
        freeze_id,
        discovery_result_freeze.population_manifest_id,
        discovery_result_freeze.freeze_id,
        discovery_result_freeze.discovery_dataset_id,
        ledger.ledger_id,
        slot_ids,
        candidate_ids,
        fingerprints,
        source_symbols,
        resolutions,
        _seal=_CANDIDATE_FREEZE_SEAL,
    )


@dataclass(frozen=True, slots=True)
class SelectionBiasInput:
    population_manifest_id: UUID
    discovery_result_freeze_id: UUID
    discovery_dataset_id: UUID
    ledger_id: UUID
    consumed_trial_count: int
    slot_ids: tuple[UUID, ...]
    trial_ids: tuple[UUID, ...]
    result_ids: tuple[UUID, ...]
    program_ids: tuple[UUID | None, ...]
    semantic_fingerprints: tuple[str, ...]
    source_symbols: tuple[str, ...]
    bar_resolutions: tuple[BarResolution, ...]
    dispositions: tuple[TrialDisposition, ...]
    diagnostic_codes: tuple[str | None, ...]
    metric_schema: str

    def to_bytes(self) -> bytes:
        return _canonical_json(
            {
                "schema": SELECTION_BIAS_SCHEMA,
                "population_manifest_id": str(self.population_manifest_id),
                "discovery_result_freeze_id": str(self.discovery_result_freeze_id),
                "discovery_dataset_id": str(self.discovery_dataset_id),
                "ledger_id": str(self.ledger_id),
                "consumed_trial_count": self.consumed_trial_count,
                "slot_ids": [str(item) for item in self.slot_ids],
                "trial_ids": [str(item) for item in self.trial_ids],
                "result_ids": [str(item) for item in self.result_ids],
                "program_ids": [
                    str(item) if item else None for item in self.program_ids
                ],
                "semantic_fingerprints": list(self.semantic_fingerprints),
                "source_symbols": list(self.source_symbols),
                "bar_resolutions": [item.name for item in self.bar_resolutions],
                "dispositions": [item.value for item in self.dispositions],
                "diagnostic_codes": list(self.diagnostic_codes),
                "metric_schema": self.metric_schema,
            }
        )


def selection_bias_input(
    discovery_result_freeze: DiscoveryResultFreeze,
    ledger: TrialLedger,
) -> SelectionBiasInput:
    if not _discovery_result_freeze_is_valid(discovery_result_freeze, ledger):
        raise InformationFirewallError(
            "selection-bias input requires the completed bound G1 result ledger"
        )
    return SelectionBiasInput(
        ledger.manifest.manifest_id,
        discovery_result_freeze.freeze_id,
        discovery_result_freeze.discovery_dataset_id,
        ledger.ledger_id,
        ledger.consumed_trial_count,
        tuple(slot.slot_id for slot in ledger.manifest.slots),
        tuple(record.trial_id for record in ledger.records),
        tuple(record.result_id for record in ledger.records),
        tuple(record.program_id for record in ledger.records),
        tuple(record.semantic_fingerprint for record in ledger.records),
        tuple(record.source_symbol for record in ledger.records),
        tuple(record.bar_resolution for record in ledger.records),
        tuple(record.disposition for record in ledger.records),
        tuple(record.diagnostic_code for record in ledger.records),
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
