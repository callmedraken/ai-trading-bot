"""Architecture 151 frozen intraday walk-forward source contracts.

This module defines the immutable candidate population and pure causal feature
and execution-policy primitives. It does not read custody, replay strategies,
acquire data, access providers or credentials, or execute trading effects.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Context, Decimal, InvalidOperation, localcontext
from enum import IntEnum, StrEnum
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5
from zoneinfo import ZoneInfo

from trading_bot.experiments.arch148_intraday import (
    HistoricalIntradaySessionAuthority,
)

PROGRAM_SCHEMA = "arch151-intraday-walkforward-program/v1"
SLOT_SCHEMA = "arch151-intraday-walkforward-trial-slot/v1"
MANIFEST_SCHEMA = "arch151-intraday-walkforward-population/v1"
BAR_SCHEMA = "arch151-intraday-walkforward-bar/v1"
AGGREGATION_SCHEMA = "arch151-sparse-aggregate/v1"
CALIBRATION_SCHEMA = "arch151-family-a-calibration/v1"
EXECUTION_POLICY_SCHEMA = "arch151-causal-execution-policy/v1"
SEMANTIC_CONTRACT_VERSION = "arch151-frozen-design-2026-11-23/v1"
IDENTITY_NAMESPACE_SEED = (
    "urn:ai-trading-bot:arch151:intraday-walkforward-foundation:v1"
)

DEVELOPMENT_START = date(2016, 1, 1)
SCORED_YEARS = (2019, 2020, 2021, 2022, 2023)
DEVELOPMENT_END = date(2024, 1, 1)
INITIAL_UNIVERSE = ("SPY", "QQQ")
NEW_YORK = ZoneInfo("America/New_York")
_SESSION_AUTHORITY = HistoricalIntradaySessionAuthority()
_DECIMAL_CONTEXT = Context(prec=60)

_ROOT_NAMESPACE = uuid5(NAMESPACE_URL, IDENTITY_NAMESPACE_SEED)
_PROGRAM_NAMESPACE = uuid5(_ROOT_NAMESPACE, "program-identity/v1")
_SLOT_NAMESPACE = uuid5(_ROOT_NAMESPACE, "trial-slot-identity/v1")
_MANIFEST_NAMESPACE = uuid5(_ROOT_NAMESPACE, "population-identity/v1")
_AGGREGATION_NAMESPACE = uuid5(_ROOT_NAMESPACE, "sparse-aggregation/v1")
_CALIBRATION_NAMESPACE = uuid5(_ROOT_NAMESPACE, "family-a-calibration/v1")
_FOLD_NAMESPACE = uuid5(_ROOT_NAMESPACE, "walk-forward-fold/v1")
_EVALUATION_NAMESPACE = uuid5(_ROOT_NAMESPACE, "fold-evaluation/v1")
_LEDGER_NAMESPACE = uuid5(_ROOT_NAMESPACE, "prior-trial-ledger/v1")
_SELECTION_INPUT_NAMESPACE = uuid5(_ROOT_NAMESPACE, "selection-bias-input/v1")
_QUALIFICATION_NAMESPACE = uuid5(_ROOT_NAMESPACE, "development-qualification/v1")
_FINAL_FREEZE_NAMESPACE = uuid5(_ROOT_NAMESPACE, "final-candidate-freeze/v1")
_FAMILY_A_MEASURE_SEAL = object()
_FAMILY_A_CALIBRATION_SEAL = object()
_PRIOR_LEDGER_SEAL = object()
_SELECTION_INPUT_SEAL = object()
_FINAL_FREEZE_SEAL = object()
_AUTHENTICATED_DEVELOPMENT_EVIDENCE_SEAL = object()
_VERIFIED_SELECTION_BIAS_SEAL = object()
_AUTHENTICATED_HOLDOUT_PASS_SEAL = object()
_HOLDOUT_AUTHORIZATION_SEAL = object()
_EXTENSION_AUTHORIZATION_SEAL = object()


class Arch151Error(ValueError):
    """Base error for invalid Architecture 151 source contracts."""


class UnsupportedProgramError(Arch151Error):
    """Raised when a program is outside the one canonical frozen grammar."""


class IncompleteAggregationError(Arch151Error):
    """Raised when a strict aggregate is requested for an incomplete bucket."""


class UnavailableIndicatorError(Arch151Error):
    """Raised when a causal feature lacks valid contiguous warmup data."""


class AuthorizationUnavailableError(Arch151Error):
    """Raised when a source-owned evidence boundary is not available."""


class StrategyFamily(StrEnum):
    NOISE_VWAP_BREAKOUT = "NOISE_VWAP_BREAKOUT"
    OPENING_RANGE_RETEST = "OPENING_RANGE_RETEST"
    VWAP_MEAN_REVERSION = "VWAP_MEAN_REVERSION"
    CROSS_ETF_TREND_PULLBACK = "CROSS_ETF_TREND_PULLBACK"


class BarResolution(IntEnum):
    FIVE_MINUTE = 5
    FIFTEEN_MINUTE = 15


class ProgramKey(StrEnum):
    A5_01 = "A5-01"
    A5_02 = "A5-02"
    A15_01 = "A15-01"
    A15_02 = "A15-02"
    B5_01 = "B5-01"
    B5_02 = "B5-02"
    B15_01 = "B15-01"
    B15_02 = "B15-02"
    C5_01 = "C5-01"
    C5_02 = "C5-02"
    C15_01 = "C15-01"
    C15_02 = "C15-02"
    D5_01 = "D5-01"
    D5_02 = "D5-02"
    D15_01 = "D15-01"
    D15_02 = "D15-02"


@dataclass(frozen=True, slots=True)
class EntryWindow:
    """Inclusive local session-clock bounds for a completed-bar signal/open."""

    start: time
    end: time

    def __post_init__(self) -> None:
        if type(self.start) is not time or type(self.end) is not time:
            raise TypeError("entry window bounds must be time values")
        if self.start.tzinfo is not None or self.end.tzinfo is not None:
            raise ValueError("entry window times are New York wall-clock values")
        if (
            self.start.second
            or self.start.microsecond
            or self.end.second
            or self.end.microsecond
        ):
            raise ValueError("entry window bounds must be minute aligned")
        if self.start >= self.end:
            raise ValueError("entry window start must precede its end")

    def contains(self, value: datetime) -> bool:
        if value.tzinfo is None or value.utcoffset() is None:
            raise TypeError("entry timestamp must be timezone aware")
        local = value.astimezone(NEW_YORK)
        return self.start <= local.time().replace(tzinfo=None) <= self.end


@dataclass(frozen=True, slots=True)
class NoiseBreakoutParameters:
    noise_lookback_sessions: int
    breakout_multiplier: Decimal
    confirmation_bars: int
    regime_sessions: int
    regime_multiplier: Decimal
    stop_multiplier: Decimal
    trail_activation_r: Decimal
    trail_distance_r: Decimal
    max_hold_minutes: int
    entry_limit_per_session: int


@dataclass(frozen=True, slots=True)
class OpeningRangeRetestParameters:
    opening_range_minutes: int
    breakout_buffer_bps: Decimal
    breakout_confirmation_bars: int
    retest_deadline_bars: int
    retest_tolerance_bps: Decimal
    reclaim_confirmation_bars: int
    stop_buffer_bps: Decimal
    target_r: Decimal
    trail_activation_r: Decimal | None
    trail_reference: str | None
    max_hold_minutes: int
    entry_limit_per_session: int


@dataclass(frozen=True, slots=True)
class VwapMeanReversionParameters:
    deviation_lookback_bars: int
    entry_sigma_multiplier: Decimal
    efficiency_ratio_lookback: int
    efficiency_ratio_max: Decimal
    exit_sigma_multiplier: Decimal
    stop_sigma_multiplier: Decimal
    max_hold_minutes: int
    cooldown_minutes: int
    entry_limit_per_session: int


@dataclass(frozen=True, slots=True)
class CrossEtfPullbackParameters:
    ema_fast: int
    ema_slow: int
    cross_confirmation_bars: int
    atr_lookback: int
    swing_peak_window_bars: int
    pullback_min_atr: Decimal
    pullback_max_atr: Decimal
    reclaim_confirmation_bars: int
    reclaim_deadline_bars: int
    stop_buffer_atr: Decimal
    trail_activation_r: Decimal
    trail_distance_atr: Decimal
    max_hold_minutes: int
    entry_limit_per_session: int


type ProgramParameters = (
    NoiseBreakoutParameters
    | OpeningRangeRetestParameters
    | VwapMeanReversionParameters
    | CrossEtfPullbackParameters
)


@dataclass(frozen=True, slots=True)
class Arch151Program:
    """One closed-grammar structural program from the canonical population."""

    key: ProgramKey
    family: StrategyFamily
    resolution: BarResolution
    entry_window: EntryWindow
    parameters: ProgramParameters
    semantic_contract_version: str = SEMANTIC_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if type(self.key) is not ProgramKey:
            raise TypeError("key must be a ProgramKey")
        if type(self.family) is not StrategyFamily:
            raise TypeError("family must be a StrategyFamily")
        if type(self.resolution) is not BarResolution:
            raise TypeError("resolution must be a BarResolution")
        if type(self.entry_window) is not EntryWindow:
            raise TypeError("entry_window must be an EntryWindow")
        if type(self.semantic_contract_version) is not str:
            raise TypeError("semantic contract version must be text")


def _entry_window(start: str, end: str) -> EntryWindow:
    return EntryWindow(time.fromisoformat(start), time.fromisoformat(end))


def _a(
    key: ProgramKey,
    resolution: BarResolution,
    start: str,
    end: str,
    noise_sessions: int,
    breakout: str,
    confirmations: int,
    regime_cap: str,
    stop: str,
    activation: str,
    trail: str,
    hold: int,
) -> Arch151Program:
    return Arch151Program(
        key,
        StrategyFamily.NOISE_VWAP_BREAKOUT,
        resolution,
        _entry_window(start, end),
        NoiseBreakoutParameters(
            noise_sessions,
            Decimal(breakout),
            confirmations,
            60,
            Decimal(regime_cap),
            Decimal(stop),
            Decimal(activation),
            Decimal(trail),
            hold,
            1,
        ),
    )


def _b(
    key: ProgramKey,
    resolution: BarResolution,
    start: str,
    end: str,
    opening_range: int,
    buffer: str,
    break_confirm: int,
    retest_deadline: int,
    tolerance: str,
    reclaim: int,
    target: str,
    trail_activation: str | None,
    hold: int,
) -> Arch151Program:
    return Arch151Program(
        key,
        StrategyFamily.OPENING_RANGE_RETEST,
        resolution,
        _entry_window(start, end),
        OpeningRangeRetestParameters(
            opening_range,
            Decimal(buffer),
            break_confirm,
            retest_deadline,
            Decimal(tolerance),
            reclaim,
            Decimal("5"),
            Decimal(target),
            Decimal(trail_activation) if trail_activation is not None else None,
            "PRIOR_COMPLETE_BAR_LOW" if trail_activation is not None else None,
            hold,
            1,
        ),
    )


def _c(
    key: ProgramKey,
    resolution: BarResolution,
    start: str,
    end: str,
    deviation_lookback: int,
    entry_sigma: str,
    er_lookback: int,
    er_max: str,
    exit_sigma: str,
    stop_sigma: str,
    hold: int,
    cooldown: int,
) -> Arch151Program:
    return Arch151Program(
        key,
        StrategyFamily.VWAP_MEAN_REVERSION,
        resolution,
        _entry_window(start, end),
        VwapMeanReversionParameters(
            deviation_lookback,
            Decimal(entry_sigma),
            er_lookback,
            Decimal(er_max),
            Decimal(exit_sigma),
            Decimal(stop_sigma),
            hold,
            cooldown,
            2,
        ),
    )


def _d(
    key: ProgramKey,
    resolution: BarResolution,
    start: str,
    end: str,
    ema_fast: int,
    ema_slow: int,
    swing_window: int,
    pullback_min: str,
    pullback_max: str,
    reclaim: int,
    reclaim_deadline: int,
    stop_buffer: str,
    activation: str,
    trail: str,
    hold: int,
) -> Arch151Program:
    return Arch151Program(
        key,
        StrategyFamily.CROSS_ETF_TREND_PULLBACK,
        resolution,
        _entry_window(start, end),
        CrossEtfPullbackParameters(
            ema_fast,
            ema_slow,
            2,
            14
            if key not in (ProgramKey.D15_01, ProgramKey.D15_02)
            else (8 if key is ProgramKey.D15_01 else 10),
            swing_window,
            Decimal(pullback_min),
            Decimal(pullback_max),
            reclaim,
            reclaim_deadline,
            Decimal(stop_buffer),
            Decimal(activation),
            Decimal(trail),
            hold,
            1,
        ),
    )


CANONICAL_PROGRAMS: tuple[Arch151Program, ...] = (
    _a(
        ProgramKey.A5_01,
        BarResolution.FIVE_MINUTE,
        "10:00",
        "14:30",
        20,
        "0.75",
        2,
        "1.25",
        "1.25",
        "1",
        "1",
        60,
    ),
    _a(
        ProgramKey.A5_02,
        BarResolution.FIVE_MINUTE,
        "10:30",
        "13:30",
        40,
        "1.00",
        3,
        "1.10",
        "1.50",
        "1.5",
        "1",
        90,
    ),
    _a(
        ProgramKey.A15_01,
        BarResolution.FIFTEEN_MINUTE,
        "10:00",
        "14:00",
        20,
        "0.75",
        2,
        "1.25",
        "1.25",
        "1.5",
        "1",
        120,
    ),
    _a(
        ProgramKey.A15_02,
        BarResolution.FIFTEEN_MINUTE,
        "10:30",
        "13:00",
        40,
        "1.00",
        2,
        "1.10",
        "1.50",
        "2",
        "1.25",
        180,
    ),
    _b(
        ProgramKey.B5_01,
        BarResolution.FIVE_MINUTE,
        "10:00",
        "12:00",
        30,
        "5",
        1,
        6,
        "10",
        1,
        "2",
        None,
        90,
    ),
    _b(
        ProgramKey.B5_02,
        BarResolution.FIVE_MINUTE,
        "10:15",
        "13:00",
        45,
        "10",
        2,
        8,
        "5",
        2,
        "1.5",
        "1",
        120,
    ),
    _b(
        ProgramKey.B15_01,
        BarResolution.FIFTEEN_MINUTE,
        "10:00",
        "12:00",
        30,
        "5",
        1,
        4,
        "10",
        1,
        "2",
        None,
        120,
    ),
    _b(
        ProgramKey.B15_02,
        BarResolution.FIFTEEN_MINUTE,
        "10:30",
        "13:00",
        60,
        "10",
        2,
        3,
        "5",
        2,
        "1.5",
        "1",
        180,
    ),
    _c(
        ProgramKey.C5_01,
        BarResolution.FIVE_MINUTE,
        "10:00",
        "14:00",
        12,
        "2.00",
        24,
        "0.30",
        "0",
        "1.5",
        60,
        30,
    ),
    _c(
        ProgramKey.C5_02,
        BarResolution.FIVE_MINUTE,
        "10:30",
        "13:00",
        24,
        "2.50",
        30,
        "0.25",
        "0.25",
        "2.0",
        90,
        45,
    ),
    _c(
        ProgramKey.C15_01,
        BarResolution.FIFTEEN_MINUTE,
        "10:30",
        "14:00",
        8,
        "1.75",
        12,
        "0.30",
        "0",
        "1.5",
        120,
        45,
    ),
    _c(
        ProgramKey.C15_02,
        BarResolution.FIFTEEN_MINUTE,
        "11:00",
        "14:00",
        12,
        "2.25",
        10,
        "0.25",
        "0.25",
        "2.0",
        180,
        60,
    ),
    _d(
        ProgramKey.D5_01,
        BarResolution.FIVE_MINUTE,
        "11:30",
        "14:00",
        8,
        21,
        6,
        "0.25",
        "0.75",
        1,
        3,
        "0.25",
        "1.5",
        "1.0",
        90,
    ),
    _d(
        ProgramKey.D5_02,
        BarResolution.FIVE_MINUTE,
        "12:15",
        "14:00",
        12,
        26,
        8,
        "0.50",
        "1.00",
        2,
        4,
        "0.50",
        "2",
        "1.5",
        120,
    ),
    _d(
        ProgramKey.D15_01,
        BarResolution.FIFTEEN_MINUTE,
        "11:30",
        "14:00",
        3,
        8,
        4,
        "0.25",
        "0.75",
        1,
        2,
        "0.25",
        "1.5",
        "1.0",
        180,
    ),
    _d(
        ProgramKey.D15_02,
        BarResolution.FIFTEEN_MINUTE,
        "12:00",
        "14:00",
        4,
        10,
        6,
        "0.50",
        "1.00",
        2,
        3,
        "0.50",
        "2",
        "1.5",
        240,
    ),
)


def _program_by_key(key: ProgramKey) -> Arch151Program | None:
    return next((program for program in CANONICAL_PROGRAMS if program.key is key), None)


def _is_canonical_program(program: object) -> bool:
    return type(program) is Arch151Program and _program_by_key(program.key) == program


def _decimal(value: Decimal | str | int, name: str) -> Decimal:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be a Decimal-compatible value")
    try:
        result = value if type(value) is Decimal else Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as error:
        raise TypeError(f"{name} must be a Decimal-compatible value") from error
    if not result.is_finite():
        raise ValueError(f"{name} must be finite")
    return result


def _decimal_text(value: Decimal) -> str:
    result = _decimal(value, "value")
    if result == 0:
        return "0"
    rendered = format(result, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def _parameter_material(parameters: ProgramParameters) -> dict[str, object]:
    if type(parameters) is NoiseBreakoutParameters:
        return {
            "family": StrategyFamily.NOISE_VWAP_BREAKOUT.value,
            "noise_lookback_sessions": parameters.noise_lookback_sessions,
            "breakout_multiplier": _decimal_text(parameters.breakout_multiplier),
            "confirmation_bars": parameters.confirmation_bars,
            "regime_sessions": parameters.regime_sessions,
            "regime_multiplier": _decimal_text(parameters.regime_multiplier),
            "stop_multiplier": _decimal_text(parameters.stop_multiplier),
            "trail_activation_r": _decimal_text(parameters.trail_activation_r),
            "trail_distance_r": _decimal_text(parameters.trail_distance_r),
            "max_hold_minutes": parameters.max_hold_minutes,
            "entry_limit_per_session": parameters.entry_limit_per_session,
        }
    if type(parameters) is OpeningRangeRetestParameters:
        return {
            "family": StrategyFamily.OPENING_RANGE_RETEST.value,
            "opening_range_minutes": parameters.opening_range_minutes,
            "breakout_buffer_bps": _decimal_text(parameters.breakout_buffer_bps),
            "breakout_confirmation_bars": parameters.breakout_confirmation_bars,
            "retest_deadline_bars": parameters.retest_deadline_bars,
            "retest_tolerance_bps": _decimal_text(parameters.retest_tolerance_bps),
            "reclaim_confirmation_bars": parameters.reclaim_confirmation_bars,
            "stop_buffer_bps": _decimal_text(parameters.stop_buffer_bps),
            "target_r": _decimal_text(parameters.target_r),
            "trail_activation_r": (
                _decimal_text(parameters.trail_activation_r)
                if parameters.trail_activation_r is not None
                else None
            ),
            "trail_reference": parameters.trail_reference,
            "max_hold_minutes": parameters.max_hold_minutes,
            "entry_limit_per_session": parameters.entry_limit_per_session,
        }
    if type(parameters) is VwapMeanReversionParameters:
        return {
            "family": StrategyFamily.VWAP_MEAN_REVERSION.value,
            "deviation_lookback_bars": parameters.deviation_lookback_bars,
            "entry_sigma_multiplier": _decimal_text(parameters.entry_sigma_multiplier),
            "efficiency_ratio_lookback": parameters.efficiency_ratio_lookback,
            "efficiency_ratio_max": _decimal_text(parameters.efficiency_ratio_max),
            "exit_sigma_multiplier": _decimal_text(parameters.exit_sigma_multiplier),
            "stop_sigma_multiplier": _decimal_text(parameters.stop_sigma_multiplier),
            "max_hold_minutes": parameters.max_hold_minutes,
            "cooldown_minutes": parameters.cooldown_minutes,
            "entry_limit_per_session": parameters.entry_limit_per_session,
        }
    if type(parameters) is CrossEtfPullbackParameters:
        return {
            "family": StrategyFamily.CROSS_ETF_TREND_PULLBACK.value,
            "ema_fast": parameters.ema_fast,
            "ema_slow": parameters.ema_slow,
            "cross_confirmation_bars": parameters.cross_confirmation_bars,
            "atr_lookback": parameters.atr_lookback,
            "swing_peak_window_bars": parameters.swing_peak_window_bars,
            "pullback_min_atr": _decimal_text(parameters.pullback_min_atr),
            "pullback_max_atr": _decimal_text(parameters.pullback_max_atr),
            "reclaim_confirmation_bars": parameters.reclaim_confirmation_bars,
            "reclaim_deadline_bars": parameters.reclaim_deadline_bars,
            "stop_buffer_atr": _decimal_text(parameters.stop_buffer_atr),
            "trail_activation_r": _decimal_text(parameters.trail_activation_r),
            "trail_distance_atr": _decimal_text(parameters.trail_distance_atr),
            "max_hold_minutes": parameters.max_hold_minutes,
            "entry_limit_per_session": parameters.entry_limit_per_session,
        }
    raise UnsupportedProgramError("unknown Arch151 parameter record")


def _program_material(program: Arch151Program) -> dict[str, object]:
    if not _is_canonical_program(program):
        raise UnsupportedProgramError("program is not in the frozen Arch151 manifest")
    return {
        "schema": PROGRAM_SCHEMA,
        "semantic_contract_version": program.semantic_contract_version,
        "key": program.key.value,
        "family": program.family.value,
        "resolution_minutes": int(program.resolution),
        "entry_window": {
            "start_et": program.entry_window.start.isoformat(timespec="minutes"),
            "end_et": program.entry_window.end.isoformat(timespec="minutes"),
        },
        "parameters": _parameter_material(program.parameters),
    }


def program_to_bytes(program: Arch151Program) -> bytes:
    """Return the exact canonical representation of a frozen program."""

    return _canonical_json(_program_material(program))


def program_fingerprint(program: Arch151Program) -> str:
    """Return the SHA-256 fingerprint over every structural semantic field."""

    return sha256(program_to_bytes(program)).hexdigest()


def program_id(program: Arch151Program) -> UUID:
    """Return its deterministic version-5 identity from canonical material."""

    canonical = program_to_bytes(program)
    return uuid5(_PROGRAM_NAMESPACE, canonical.decode("utf-8"))


def program_from_bytes(payload: bytes) -> Arch151Program:
    """Decode only byte-for-byte canonical members of the frozen population."""

    if type(payload) is not bytes:
        raise TypeError("program payload must be bytes")
    try:
        raw = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise UnsupportedProgramError(
            "program payload is not valid canonical JSON"
        ) from None
    if type(raw) is not dict or raw.get("schema") != PROGRAM_SCHEMA:
        raise UnsupportedProgramError("unknown or incomplete program schema")
    key_value = raw.get("key")
    try:
        key = ProgramKey(key_value)
    except (TypeError, ValueError):
        raise UnsupportedProgramError("unknown program key") from None
    program = _program_by_key(key)
    if program is None or program_to_bytes(program) != payload:
        raise UnsupportedProgramError("program payload is altered or noncanonical")
    return program


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class TrialSlot:
    ordinal: int
    program_key: ProgramKey
    program_id: UUID
    program_fingerprint: str
    symbol: str
    resolution: BarResolution
    slot_id: UUID

    def __post_init__(self) -> None:
        if type(self.ordinal) is not int or self.ordinal < 1:
            raise ValueError("slot ordinal must be a positive integer")
        if type(self.program_key) is not ProgramKey:
            raise TypeError("slot program key must be canonical")
        if type(self.program_id) is not UUID or type(self.slot_id) is not UUID:
            raise TypeError("slot identities must be UUID values")
        if self.symbol not in INITIAL_UNIVERSE:
            raise ValueError("slot symbol is outside the frozen universe")
        if type(self.resolution) is not BarResolution:
            raise TypeError("slot resolution must be a BarResolution")


def _slot_material(slot: TrialSlot) -> dict[str, object]:
    return {
        "schema": SLOT_SCHEMA,
        "ordinal": slot.ordinal,
        "program_key": slot.program_key.value,
        "program_id": str(slot.program_id),
        "program_fingerprint": slot.program_fingerprint,
        "symbol": slot.symbol,
        "resolution_minutes": int(slot.resolution),
    }


def _slot_identity(program: Arch151Program, symbol: str) -> UUID:
    material = {
        "schema": SLOT_SCHEMA,
        "program_id": str(program_id(program)),
        "program_fingerprint": program_fingerprint(program),
        "symbol": symbol,
        "resolution_minutes": int(program.resolution),
        "semantic_contract_version": program.semantic_contract_version,
    }
    return uuid5(_SLOT_NAMESPACE, _canonical_json(material).decode("utf-8"))


CANONICAL_SLOTS: tuple[TrialSlot, ...] = tuple(
    TrialSlot(
        ordinal=(program_ordinal * 2) + symbol_ordinal + 1,
        program_key=program.key,
        program_id=program_id(program),
        program_fingerprint=program_fingerprint(program),
        symbol=symbol,
        resolution=program.resolution,
        slot_id=_slot_identity(program, symbol),
    )
    for program_ordinal, program in enumerate(CANONICAL_PROGRAMS)
    for symbol_ordinal, symbol in enumerate(INITIAL_UNIVERSE)
)


@dataclass(frozen=True, slots=True, init=False)
class CanonicalManifest:
    """Sealed, immutable, complete source-owned population and ordered slots."""

    schema: str
    semantic_contract_version: str
    programs: tuple[Arch151Program, ...]
    slots: tuple[TrialSlot, ...]
    manifest_id: UUID
    fingerprint: str
    canonical_bytes: bytes

    def __init__(self, *, _seal: object = None) -> None:
        if _seal is not _MANIFEST_SEAL:
            raise Arch151Error(
                "manifest must come from source-owned canonical population"
            )
        material = {
            "schema": MANIFEST_SCHEMA,
            "semantic_contract_version": SEMANTIC_CONTRACT_VERSION,
            "programs": [
                json.loads(program_to_bytes(item)) for item in CANONICAL_PROGRAMS
            ],
            "slots": [_slot_material(item) for item in CANONICAL_SLOTS],
        }
        canonical = _canonical_json(material)
        manifest_uuid = uuid5(_MANIFEST_NAMESPACE, canonical.decode("utf-8"))
        for name, value in (
            ("schema", MANIFEST_SCHEMA),
            ("semantic_contract_version", SEMANTIC_CONTRACT_VERSION),
            ("programs", CANONICAL_PROGRAMS),
            ("slots", CANONICAL_SLOTS),
            ("manifest_id", manifest_uuid),
            ("fingerprint", sha256(canonical).hexdigest()),
            ("canonical_bytes", canonical),
        ):
            object.__setattr__(self, name, value)


_MANIFEST_SEAL = object()
CANONICAL_MANIFEST = CanonicalManifest(_seal=_MANIFEST_SEAL)


def canonical_manifest() -> CanonicalManifest:
    """Return the one immutable 16-program / 32-slot manifest."""

    return CANONICAL_MANIFEST


def validate_slot(slot: TrialSlot) -> bool:
    """Return true only for an exact immutable slot in canonical order."""

    if type(slot) is not TrialSlot:
        return False
    return any(expected is slot or expected == slot for expected in CANONICAL_SLOTS)


@dataclass(frozen=True, slots=True)
class OneMinuteBar:
    """A single observed one-minute OHLCV bar supplied in memory."""

    symbol: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

    def __post_init__(self) -> None:
        if self.symbol not in INITIAL_UNIVERSE:
            raise Arch151Error("bar symbol is outside the frozen SPY/QQQ universe")
        if (
            type(self.timestamp) is not datetime
            or self.timestamp.tzinfo is None
            or self.timestamp.utcoffset() is None
        ):
            raise TypeError("bar timestamp must be timezone aware")
        normalized = self.timestamp.astimezone(UTC)
        if normalized.second or normalized.microsecond:
            raise ValueError("one-minute bar timestamp must be minute aligned")
        object.__setattr__(self, "timestamp", normalized)
        prices = {
            name: _decimal(getattr(self, name), name)
            for name in ("open", "high", "low", "close")
        }
        if any(value <= 0 for value in prices.values()):
            raise ValueError("OHLC values must be positive")
        if prices["high"] < max(prices.values()) or prices["low"] > min(
            prices.values()
        ):
            raise ValueError("OHLC high/low are inconsistent")
        for name, value in prices.items():
            object.__setattr__(self, name, value)
        if type(self.volume) is not int or self.volume < 0:
            raise ValueError("volume must be a nonnegative integer")

    @property
    def session_date(self) -> date:
        return self.timestamp.astimezone(NEW_YORK).date()

    @property
    def completed_at(self) -> datetime:
        return self.timestamp + timedelta(minutes=1)


@dataclass(frozen=True, slots=True)
class AggregateBar:
    """A complete XNYS-anchored aggregate derived from observed minutes."""

    symbol: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    resolution: BarResolution

    def __post_init__(self) -> None:
        if self.symbol not in INITIAL_UNIVERSE:
            raise Arch151Error("bar symbol is outside the frozen SPY/QQQ universe")
        if (
            type(self.timestamp) is not datetime
            or self.timestamp.tzinfo is None
            or self.timestamp.utcoffset() is None
        ):
            raise TypeError("aggregate timestamp must be timezone aware")
        object.__setattr__(self, "timestamp", self.timestamp.astimezone(UTC))
        if type(self.resolution) is not BarResolution:
            raise TypeError("aggregate resolution must be a BarResolution")
        prices = {
            name: _decimal(getattr(self, name), name)
            for name in ("open", "high", "low", "close")
        }
        if any(value <= 0 for value in prices.values()):
            raise ValueError("OHLC values must be positive")
        if prices["high"] < max(prices.values()) or prices["low"] > min(
            prices.values()
        ):
            raise ValueError("OHLC high/low are inconsistent")
        for name, value in prices.items():
            object.__setattr__(self, name, value)
        if type(self.volume) is not int or self.volume < 0:
            raise ValueError("volume must be a nonnegative integer")

    @property
    def session_date(self) -> date:
        return self.timestamp.astimezone(NEW_YORK).date()

    @property
    def completed_at(self) -> datetime:
        return self.timestamp + timedelta(minutes=int(self.resolution))


@dataclass(frozen=True, slots=True)
class VwapObservation:
    """Causal contemporaneous VWAP paired with one completed aggregate bar."""

    bar: AggregateBar
    vwap: Decimal

    def __post_init__(self) -> None:
        if type(self.bar) is not AggregateBar:
            raise TypeError("VWAP observation requires an AggregateBar")
        value = _decimal(self.vwap, "vwap")
        if value <= 0:
            raise ValueError("VWAP must be positive")
        object.__setattr__(self, "vwap", value)


@dataclass(frozen=True, slots=True)
class AggregateStream:
    """Immutable aggregate output and deterministic source commitments."""

    symbol: str
    resolution: BarResolution
    bars: tuple[AggregateBar, ...]
    input_digest: str
    output_digest: str
    source_digest: str


def _bar_material(bar: OneMinuteBar | AggregateBar) -> dict[str, object]:
    return {
        "schema": BAR_SCHEMA,
        "symbol": bar.symbol,
        "timestamp": bar.timestamp.isoformat(timespec="minutes").replace("+00:00", "Z"),
        "completed_at": bar.completed_at.isoformat(timespec="minutes").replace(
            "+00:00", "Z"
        ),
        "open": _decimal_text(bar.open),
        "high": _decimal_text(bar.high),
        "low": _decimal_text(bar.low),
        "close": _decimal_text(bar.close),
        "volume": bar.volume,
        "resolution_minutes": 1 if type(bar) is OneMinuteBar else int(bar.resolution),
    }


def _validated_minutes(bars: Iterable[OneMinuteBar]) -> tuple[OneMinuteBar, ...]:
    materialized = tuple(bars)
    if not materialized:
        raise Arch151Error("at least one observed one-minute bar is required")
    if any(type(bar) is not OneMinuteBar for bar in materialized):
        raise TypeError("aggregation accepts only OneMinuteBar values")
    symbol = materialized[0].symbol
    previous: datetime | None = None
    for bar in materialized:
        if bar.symbol != symbol:
            raise Arch151Error("one-minute stream must contain exactly one symbol")
        if previous is not None and bar.timestamp <= previous:
            raise Arch151Error("one-minute bars must be strictly chronological")
        previous = bar.timestamp
        schedule = _SESSION_AUTHORITY.schedule_for(bar.session_date)
        if schedule is None:
            raise Arch151Error("bar date is not a published regular XNYS session")
        opens_at = schedule.opens_at.astimezone(UTC)
        closes_at = schedule.closes_at.astimezone(UTC)
        if bar.timestamp < opens_at or bar.timestamp + timedelta(minutes=1) > closes_at:
            raise Arch151Error("one-minute bar falls outside the published session")
        if (bar.timestamp - opens_at).total_seconds() % 60 != 0:
            raise Arch151Error(
                "one-minute bar is not aligned to the published session open"
            )
    return materialized


def aggregate_sparse_bars(
    bars: Iterable[OneMinuteBar], resolution: BarResolution
) -> AggregateStream:
    """Aggregate complete 5m/15m buckets, dropping incomplete buckets only."""

    if type(resolution) is not BarResolution:
        raise TypeError("resolution must be a BarResolution")
    minutes = _validated_minutes(bars)
    grouped: dict[tuple[date, int], list[OneMinuteBar]] = defaultdict(list)
    schedules: dict[date, object] = {}
    span = int(resolution)
    for bar in minutes:
        schedule = _SESSION_AUTHORITY.schedule_for(bar.session_date)
        assert schedule is not None
        schedules[bar.session_date] = schedule
        elapsed = bar.timestamp - schedule.opens_at.astimezone(UTC)
        elapsed_minutes = int(elapsed.total_seconds() // 60)
        grouped[(bar.session_date, elapsed_minutes // span)].append(bar)

    output: list[AggregateBar] = []
    for (session, bucket), group in sorted(grouped.items()):
        schedule = schedules[session]
        bucket_open = schedule.opens_at.astimezone(UTC) + timedelta(
            minutes=bucket * span
        )
        if bucket_open + timedelta(minutes=span) > schedule.closes_at.astimezone(UTC):
            continue
        if len(group) != span or any(
            item.timestamp != bucket_open + timedelta(minutes=offset)
            for offset, item in enumerate(group)
        ):
            continue
        output.append(
            AggregateBar(
                group[0].symbol,
                bucket_open,
                group[0].open,
                max(item.high for item in group),
                min(item.low for item in group),
                group[-1].close,
                sum(item.volume for item in group),
                resolution,
            )
        )
    result = tuple(output)
    input_digest = sha256(
        _canonical_json([_bar_material(bar) for bar in minutes])
    ).hexdigest()
    output_digest = sha256(
        _canonical_json([_bar_material(bar) for bar in result])
    ).hexdigest()
    source_digest = sha256(
        _canonical_json(
            {
                "schema": AGGREGATION_SCHEMA,
                "resolution_minutes": span,
                "input_digest": input_digest,
                "output_digest": output_digest,
            }
        )
    ).hexdigest()
    return AggregateStream(
        minutes[0].symbol,
        resolution,
        result,
        input_digest,
        output_digest,
        source_digest,
    )


def aggregate_session_vwap(
    minute_bars: Iterable[OneMinuteBar], aggregate_stream: AggregateStream
) -> tuple[VwapObservation, ...]:
    """Derive bucket-end session VWAP from exact observed one-minute inputs.

    Every aggregate must match a complete sparse aggregate recomputed from the
    supplied minute bars. HLC3 is volume weighted using actual observed volume;
    accumulators reset at each published session boundary. No missing minute is
    synthesized, carried forward, or substituted.
    """

    if type(aggregate_stream) is not AggregateStream:
        raise TypeError("session VWAP requires an AggregateStream")
    minutes = _validated_minutes(minute_bars)
    recomputed = aggregate_sparse_bars(minutes, aggregate_stream.resolution)
    if recomputed != aggregate_stream:
        raise Arch151Error("VWAP aggregate stream does not match exact minute sources")
    if not aggregate_stream.bars:
        raise UnavailableIndicatorError(
            "session VWAP requires a complete aggregate bucket"
        )

    minutes_by_session: dict[date, list[OneMinuteBar]] = defaultdict(list)
    aggregates_by_session: dict[date, list[AggregateBar]] = defaultdict(list)
    for minute in minutes:
        minutes_by_session[minute.session_date].append(minute)
    for aggregate in aggregate_stream.bars:
        aggregates_by_session[aggregate.session_date].append(aggregate)
    for session, session_minutes in minutes_by_session.items():
        schedule = _SESSION_AUTHORITY.schedule_for(session)
        if schedule is None or session_minutes[0].timestamp != (
            schedule.opens_at.astimezone(UTC)
        ):
            raise UnavailableIndicatorError(
                "session VWAP source must begin at the published XNYS open"
            )

    observations: list[VwapObservation] = []
    for session, aggregate_bars in aggregates_by_session.items():
        session_minutes = minutes_by_session[session]
        cursor = 0
        cumulative_notional = Decimal(0)
        cumulative_volume = 0
        with localcontext(_DECIMAL_CONTEXT):
            for aggregate in aggregate_bars:
                final_constituent_open = aggregate.completed_at - timedelta(minutes=1)
                while (
                    cursor < len(session_minutes)
                    and session_minutes[cursor].timestamp <= final_constituent_open
                ):
                    minute = session_minutes[cursor]
                    h_l_c = minute.high + minute.low + minute.close
                    hlc3 = h_l_c / Decimal(3)
                    cumulative_notional += hlc3 * minute.volume
                    cumulative_volume += minute.volume
                    cursor += 1
                if cumulative_volume <= 0:
                    raise UnavailableIndicatorError(
                        "session VWAP has a zero observed-volume denominator"
                    )
                vwap = cumulative_notional / Decimal(cumulative_volume)
                if not vwap.is_finite() or vwap <= 0:
                    raise UnavailableIndicatorError("session VWAP is invalid")
                observations.append(VwapObservation(aggregate, vwap))
    return tuple(observations)


def contiguous_aggregate_bars(
    bars: Sequence[AggregateBar], *, count: int | None = None
) -> tuple[AggregateBar, ...]:
    """Validate one-session contiguous bars; gaps and session crossings fail."""

    materialized = tuple(bars)
    if not materialized:
        raise UnavailableIndicatorError("contiguous feature input is empty")
    if any(type(bar) is not AggregateBar for bar in materialized):
        raise TypeError("feature input must contain AggregateBar values")
    first = materialized[0]
    for previous, current in zip(materialized, materialized[1:], strict=False):
        if (
            current.symbol != first.symbol
            or current.resolution is not first.resolution
            or current.session_date != first.session_date
            or current.timestamp
            != previous.timestamp + timedelta(minutes=int(first.resolution))
        ):
            raise UnavailableIndicatorError(
                "aggregate feature input crosses a gap or session"
            )
    if count is not None and len(materialized) != count:
        raise UnavailableIndicatorError(
            f"feature requires exactly {count} contiguous bars"
        )
    return materialized


@dataclass(frozen=True, slots=True, init=False)
class FamilyASessionMeasure:
    """Dimensionless absolute first-30-minute return from a complete session."""

    session_date: date
    session_open: Decimal
    first_30m_close: Decimal
    absolute_return: Decimal
    source_digest: str

    def __init__(
        self,
        session_date: date,
        session_open: Decimal,
        first_30m_close: Decimal,
        absolute_return: Decimal,
        source_digest: str,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _FAMILY_A_MEASURE_SEAL:
            raise Arch151Error("Family A measures require 30 exact session minutes")
        opening = _decimal(session_open, "session_open")
        closing = _decimal(first_30m_close, "first_30m_close")
        measured = _decimal(absolute_return, "absolute_return")
        if opening <= 0 or closing <= 0 or measured < 0:
            raise ValueError("Family A measure prices/return are invalid")
        if (
            type(session_date) is not date
            or type(source_digest) is not str
            or len(source_digest) != 64
        ):
            raise TypeError("Family A measure identity fields are invalid")
        with localcontext(_DECIMAL_CONTEXT):
            expected = abs(closing / opening - Decimal(1))
        if measured != expected:
            raise Arch151Error("Family A measure return does not match its prices")
        for name, value in (
            ("session_date", session_date),
            ("session_open", opening),
            ("first_30m_close", closing),
            ("absolute_return", measured),
            ("source_digest", source_digest),
        ):
            object.__setattr__(self, name, value)


def family_a_session_measure(bars: Iterable[OneMinuteBar]) -> FamilyASessionMeasure:
    """Derive a complete first-30-minute absolute return from 30 exact minutes."""

    materialized = _validated_minutes(bars)
    if len(materialized) != 30:
        raise UnavailableIndicatorError(
            "Family A requires all 30 first-session minutes"
        )
    first = materialized[0]
    schedule = _SESSION_AUTHORITY.schedule_for(first.session_date)
    assert schedule is not None
    expected = tuple(
        schedule.opens_at.astimezone(UTC) + timedelta(minutes=offset)
        for offset in range(30)
    )
    if tuple(bar.timestamp for bar in materialized) != expected:
        raise UnavailableIndicatorError("Family A first-30-minute window is incomplete")
    with localcontext(_DECIMAL_CONTEXT):
        value = abs(materialized[-1].close / first.open - Decimal(1))
    digest = sha256(
        _canonical_json([_bar_material(bar) for bar in materialized])
    ).hexdigest()
    return FamilyASessionMeasure(
        first.session_date,
        first.open,
        materialized[-1].close,
        value,
        digest,
        _seal=_FAMILY_A_MEASURE_SEAL,
    )


@dataclass(frozen=True, slots=True, init=False)
class FamilyACalibration:
    """Frozen pre-score-year noise and regime statistics for one A program."""

    program_key: ProgramKey
    scored_year: int
    noise_return: Decimal
    regime_median_return: Decimal
    calibration_session_dates: tuple[date, ...]
    calibration_fingerprint: str
    calibration_id: UUID

    def __init__(
        self,
        program_key: ProgramKey,
        scored_year: int,
        noise_return: Decimal,
        regime_median_return: Decimal,
        calibration_session_dates: tuple[date, ...],
        calibration_fingerprint: str,
        calibration_id: UUID,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _FAMILY_A_CALIBRATION_SEAL:
            raise Arch151Error("Family A calibration must come from source calibration")
        noise = _decimal(noise_return, "noise_return")
        regime = _decimal(regime_median_return, "regime_median_return")
        if noise < 0 or regime < 0:
            raise ValueError("Family A calibrations must be nonnegative")
        if type(calibration_session_dates) is not tuple:
            raise TypeError("calibration session dates must be a tuple")
        if type(calibration_id) is not UUID or type(calibration_fingerprint) is not str:
            raise TypeError("calibration identity is invalid")
        for name, value in (
            ("program_key", program_key),
            ("scored_year", scored_year),
            ("noise_return", noise),
            ("regime_median_return", regime),
            ("calibration_session_dates", calibration_session_dates),
            ("calibration_fingerprint", calibration_fingerprint),
            ("calibration_id", calibration_id),
        ):
            object.__setattr__(self, name, value)


def calibrate_family_a(
    program: Arch151Program,
    observations: Iterable[FamilyASessionMeasure],
    scored_year: int,
) -> FamilyACalibration:
    """Freeze the last N and 60 eligible session returns before a scored year."""

    if (
        not _is_canonical_program(program)
        or type(program.parameters) is not NoiseBreakoutParameters
    ):
        raise UnsupportedProgramError(
            "Family A calibration requires a canonical A program"
        )
    if type(scored_year) is not int or scored_year not in SCORED_YEARS:
        raise ValueError("scored year is outside the five frozen Arch151 years")
    materialized = tuple(observations)
    if any(type(item) is not FamilyASessionMeasure for item in materialized):
        raise TypeError("calibration inputs must be complete Family A session measures")
    dates = tuple(item.session_date for item in materialized)
    if dates != tuple(sorted(set(dates))):
        raise Arch151Error("calibration sessions must be unique and chronological")
    cutoff = date(scored_year, 1, 1)
    if any(
        item.session_date < DEVELOPMENT_START or item.session_date >= cutoff
        for item in materialized
    ):
        raise Arch151Error(
            "calibration must use only development history before scored year"
        )
    parameters = program.parameters
    count = max(parameters.noise_lookback_sessions, parameters.regime_sessions)
    if len(materialized) < count:
        raise UnavailableIndicatorError(
            f"Family A calibration requires {count} eligible sessions"
        )
    selected = materialized[-count:]
    noise_items = selected[-parameters.noise_lookback_sessions :]
    regime_items = selected[-parameters.regime_sessions :]
    noise = _decimal_median(tuple(item.absolute_return for item in noise_items))
    regime = _decimal_median(tuple(item.absolute_return for item in regime_items))
    selected_dates = tuple(item.session_date for item in selected)
    material = {
        "schema": CALIBRATION_SCHEMA,
        "semantic_contract_version": SEMANTIC_CONTRACT_VERSION,
        "program_id": str(program_id(program)),
        "scored_year": scored_year,
        "cutoff": cutoff.isoformat(),
        "noise_return": _decimal_text(noise),
        "regime_median_return": _decimal_text(regime),
        "observations": [
            {
                "session_date": item.session_date.isoformat(),
                "source_digest": item.source_digest,
            }
            for item in selected
        ],
    }
    canonical = _canonical_json(material)
    return FamilyACalibration(
        program.key,
        scored_year,
        noise,
        regime,
        selected_dates,
        sha256(canonical).hexdigest(),
        uuid5(_CALIBRATION_NAMESPACE, canonical.decode("utf-8")),
        _seal=_FAMILY_A_CALIBRATION_SEAL,
    )


def _decimal_median(values: tuple[Decimal, ...]) -> Decimal:
    if not values:
        raise UnavailableIndicatorError("median requires at least one value")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    with localcontext(_DECIMAL_CONTEXT):
        return (ordered[middle - 1] + ordered[middle]) / Decimal(2)


def family_a_regime_passes(
    program: Arch151Program,
    calibration: FamilyACalibration,
    current_session: FamilyASessionMeasure,
) -> bool:
    """Apply the frozen calibration to a complete scored-session opening."""

    if (
        not _is_canonical_program(program)
        or type(program.parameters) is not NoiseBreakoutParameters
        or type(calibration) is not FamilyACalibration
        or calibration.program_key is not program.key
        or current_session.session_date.year != calibration.scored_year
    ):
        raise Arch151Error("Family A calibration/current session binding is invalid")
    limit = calibration.regime_median_return * program.parameters.regime_multiplier
    return current_session.absolute_return <= limit


def family_a_breakout_level(
    program: Arch151Program, calibration: FamilyACalibration, session_open: Decimal
) -> Decimal:
    """Compute the frozen dimensionless noise threshold in price units."""

    if (
        not _is_canonical_program(program)
        or type(program.parameters) is not NoiseBreakoutParameters
        or calibration.program_key is not program.key
    ):
        raise Arch151Error(
            "Family A breakout inputs are not bound to a canonical program"
        )
    open_price = _decimal(session_open, "session_open")
    with localcontext(_DECIMAL_CONTEXT):
        return open_price * (
            Decimal(1)
            + program.parameters.breakout_multiplier * calibration.noise_return
        )


def family_a_initial_risk(
    program: Arch151Program,
    calibration: FamilyACalibration,
    entry_reference_price: Decimal,
) -> tuple[Decimal, Decimal]:
    """Return stop and positive R using entry-price times dimensionless N."""

    if (
        not _is_canonical_program(program)
        or type(program.parameters) is not NoiseBreakoutParameters
        or calibration.program_key is not program.key
    ):
        raise Arch151Error("Family A risk inputs are not bound to a canonical program")
    entry = _decimal(entry_reference_price, "entry_reference_price")
    if entry <= 0:
        raise ValueError("entry reference price must be positive")
    with localcontext(_DECIMAL_CONTEXT):
        distance = entry * program.parameters.stop_multiplier * calibration.noise_return
        stop = entry - distance
    if distance <= 0 or stop <= 0 or not stop.is_finite():
        raise UnavailableIndicatorError("Family A initial risk distance is invalid")
    return stop, distance


@dataclass(frozen=True, slots=True)
class NoiseBreakoutSignal:
    program_key: ProgramKey
    session_date: date
    confirmation_timestamps: tuple[datetime, ...]
    breakout_level: Decimal
    final_close: Decimal
    calibration_id: UUID


def family_a_entry_signal(
    program: Arch151Program,
    calibration: FamilyACalibration,
    current_session: FamilyASessionMeasure,
    confirmation: Sequence[VwapObservation],
) -> NoiseBreakoutSignal | None:
    """Evaluate only the completed-bar Family A entry predicate."""

    if (
        not _is_canonical_program(program)
        or type(program.parameters) is not NoiseBreakoutParameters
        or type(calibration) is not FamilyACalibration
        or type(current_session) is not FamilyASessionMeasure
        or calibration.program_key is not program.key
        or current_session.session_date.year != calibration.scored_year
    ):
        raise Arch151Error("Family A signal inputs are not source-bound")
    observations = tuple(confirmation)
    required = program.parameters.confirmation_bars
    if len(observations) != required:
        raise UnavailableIndicatorError("Family A confirmation count is incomplete")
    if any(type(item) is not VwapObservation for item in observations):
        raise TypeError("Family A confirmation must contain VWAP observations")
    bars = _validated_session_aggregate_bars(
        program, tuple(item.bar for item in observations), from_open=False
    )
    if any(
        item.bar.session_date != current_session.session_date for item in observations
    ):
        raise Arch151Error("Family A confirmation crossed the current session")
    if current_session.session_open != _decimal(
        current_session.session_open, "session_open"
    ):
        raise Arch151Error("Family A session open is invalid")
    if not family_a_regime_passes(program, calibration, current_session):
        return None
    threshold = family_a_breakout_level(
        program, calibration, current_session.session_open
    )
    for observation in observations:
        if (
            observation.bar.close <= threshold
            or observation.bar.close <= observation.vwap
        ):
            return None
    if not program.entry_window.contains(bars[-1].completed_at):
        return None
    if any(
        current.vwap <= previous.vwap
        for previous, current in zip(observations, observations[1:], strict=False)
    ):
        return None
    return NoiseBreakoutSignal(
        program.key,
        current_session.session_date,
        tuple(bar.timestamp for bar in bars),
        threshold,
        bars[-1].close,
        calibration.calibration_id,
    )


@dataclass(frozen=True, slots=True)
class OpeningRangeRetestSignal:
    program_key: ProgramKey
    session_date: date
    breakout_level: Decimal
    breakout_confirmation_timestamps: tuple[datetime, ...]
    retest_timestamp: datetime
    reclaim_timestamps: tuple[datetime, ...]
    stop_reference_price: Decimal
    target_r: Decimal


def _validated_session_aggregate_bars(
    program: Arch151Program, bars: Sequence[AggregateBar], *, from_open: bool
) -> tuple[AggregateBar, ...]:
    materialized = contiguous_aggregate_bars(bars)
    if any(bar.resolution is not program.resolution for bar in materialized):
        raise Arch151Error("aggregate resolution does not match canonical program")
    schedule = _SESSION_AUTHORITY.schedule_for(materialized[0].session_date)
    if schedule is None:
        raise Arch151Error("signal date is not a published XNYS session")
    open_utc = schedule.opens_at.astimezone(UTC)
    close_utc = schedule.closes_at.astimezone(UTC)
    if from_open and materialized[0].timestamp != open_utc:
        raise UnavailableIndicatorError(
            "setup input must begin at the published session open"
        )
    for bar in materialized:
        if (
            bar.timestamp < open_utc
            or bar.completed_at > close_utc
            or (bar.timestamp - open_utc).total_seconds()
            % (int(program.resolution) * 60)
            != 0
        ):
            raise Arch151Error("aggregate bar is not complete and session aligned")
    return materialized


def family_b_entry_signal(
    program: Arch151Program, session_bars: Sequence[AggregateBar]
) -> OpeningRangeRetestSignal | None:
    """Evaluate one chronological breakout, later retest, later reclaim setup."""

    if (
        not _is_canonical_program(program)
        or type(program.parameters) is not OpeningRangeRetestParameters
    ):
        raise UnsupportedProgramError("Family B requires a canonical retest program")
    bars = _validated_session_aggregate_bars(program, session_bars, from_open=True)
    parameters = program.parameters
    resolution = int(program.resolution)
    if parameters.opening_range_minutes % resolution:
        raise Arch151Error("opening range is not aligned to program resolution")
    opening_count = parameters.opening_range_minutes // resolution
    if len(bars) <= opening_count:
        return None
    opening_range = bars[:opening_count]
    level = max(bar.high for bar in opening_range) * (
        Decimal(1) + parameters.breakout_buffer_bps / Decimal(10000)
    )

    confirmation_count = 0
    breakout_indexes: list[int] = []
    final_breakout_index: int | None = None
    for index in range(opening_count, len(bars)):
        if bars[index].close > level:
            confirmation_count += 1
            breakout_indexes.append(index)
            if confirmation_count == parameters.breakout_confirmation_bars:
                final_breakout_index = index
                break
        else:
            confirmation_count = 0
            breakout_indexes.clear()
    if final_breakout_index is None:
        return None

    lower = level * (Decimal(1) - parameters.retest_tolerance_bps / Decimal(10000))
    upper = level * (Decimal(1) + parameters.retest_tolerance_bps / Decimal(10000))
    retest_index: int | None = None
    deadline_end = min(
        len(bars) - 1, final_breakout_index + parameters.retest_deadline_bars
    )
    for index in range(final_breakout_index + 1, deadline_end + 1):
        if bars[index].low < lower:
            return None
        if lower <= bars[index].low <= upper:
            retest_index = index
            break
    if retest_index is None:
        return None

    reclaim_indexes: list[int] = []
    for index in range(retest_index + 1, len(bars)):
        if bars[index].close <= level:
            return None
        reclaim_indexes.append(index)
        if len(reclaim_indexes) == parameters.reclaim_confirmation_bars:
            final_bar = bars[index]
            if not program.entry_window.contains(final_bar.completed_at):
                return None
            swing_low = min(bar.low for bar in bars[retest_index : index + 1])
            stop = swing_low * (
                Decimal(1) - parameters.stop_buffer_bps / Decimal(10000)
            )
            return OpeningRangeRetestSignal(
                program.key,
                final_bar.session_date,
                level,
                tuple(bars[item].timestamp for item in breakout_indexes),
                bars[retest_index].timestamp,
                tuple(bars[item].timestamp for item in reclaim_indexes),
                stop,
                parameters.target_r,
            )
    return None


@dataclass(frozen=True, slots=True)
class VwapMeanReversionSignal:
    program_key: ProgramKey
    signal_timestamp: datetime
    normalized_deviation: Decimal
    frozen_entry_sigma: Decimal
    efficiency_ratio: Decimal


def family_c_entry_signal(
    program: Arch151Program,
    preceding: Sequence[VwapObservation],
    signal: VwapObservation,
) -> VwapMeanReversionSignal | None:
    """Evaluate the completed-bar downside sigma plus low-directionality gate."""

    if (
        not _is_canonical_program(program)
        or type(program.parameters) is not VwapMeanReversionParameters
        or type(signal) is not VwapObservation
    ):
        raise UnsupportedProgramError(
            "Family C requires a canonical mean-reversion program"
        )
    history = tuple(preceding)
    parameters = program.parameters
    required = max(
        parameters.deviation_lookback_bars, parameters.efficiency_ratio_lookback
    )
    if len(history) != required:
        raise UnavailableIndicatorError(
            "Family C requires its complete declared warmup"
        )
    if any(type(item) is not VwapObservation for item in history):
        raise TypeError("Family C history must contain VWAP observations")
    _validated_session_aggregate_bars(
        program, tuple(item.bar for item in (*history, signal)), from_open=False
    )
    if not program.entry_window.contains(signal.bar.completed_at):
        return None
    sigma_pairs = tuple(
        (item.bar.close, item.vwap)
        for item in history[-parameters.deviation_lookback_bars :]
    )
    sigma, deviation = vwap_deviation_sigma(
        sigma_pairs,
        signal.bar.close,
        signal.vwap,
        lookback=parameters.deviation_lookback_bars,
    )
    if sigma <= 0:
        raise UnavailableIndicatorError("Family C sigma must be positive")
    er_closes = tuple(
        item.bar.close for item in history[-parameters.efficiency_ratio_lookback :]
    ) + (signal.bar.close,)
    er = efficiency_ratio(er_closes, parameters.efficiency_ratio_lookback)
    with localcontext(_DECIMAL_CONTEXT):
        threshold = -parameters.entry_sigma_multiplier * sigma
    if deviation > threshold or er > parameters.efficiency_ratio_max:
        return None
    return VwapMeanReversionSignal(
        program.key, signal.bar.timestamp, deviation, sigma, er
    )


def family_c_reversion_exit(
    program: Arch151Program, signal: VwapMeanReversionSignal, current: VwapObservation
) -> bool:
    """Check the VWAP exit against current VWAP and frozen entry sigma."""

    if (
        not _is_canonical_program(program)
        or type(program.parameters) is not VwapMeanReversionParameters
        or type(signal) is not VwapMeanReversionSignal
        or signal.program_key is not program.key
        or type(current) is not VwapObservation
    ):
        raise Arch151Error("Family C exit is not bound to its canonical entry signal")
    if (
        type(signal.signal_timestamp) is not datetime
        or signal.signal_timestamp.tzinfo is None
        or signal.signal_timestamp.utcoffset() is None
    ):
        raise Arch151Error("Family C signal timestamp must be timezone aware")
    signal_timestamp = signal.signal_timestamp.astimezone(UTC)
    signal_session = signal_timestamp.astimezone(NEW_YORK).date()
    schedule = _SESSION_AUTHORITY.schedule_for(signal_session)
    if schedule is None:
        raise Arch151Error("Family C signal is outside the published XNYS schedule")
    signal_open = schedule.opens_at.astimezone(UTC)
    signal_close = schedule.closes_at.astimezone(UTC)
    if (
        signal_timestamp < signal_open
        or signal_timestamp + timedelta(minutes=int(program.resolution)) > signal_close
        or (signal_timestamp - signal_open).total_seconds()
        % (int(program.resolution) * 60)
        != 0
    ):
        raise Arch151Error("Family C signal is not aligned to the published schedule")
    current_bar = _validated_session_aggregate_bars(
        program, (current.bar,), from_open=False
    )[0]
    if (
        current_bar.session_date != signal_session
        or current_bar.timestamp <= signal_timestamp
    ):
        raise Arch151Error(
            "Family C exit must be strictly later and within the signal session"
        )
    with localcontext(_DECIMAL_CONTEXT):
        threshold = current.vwap * (
            Decimal(1)
            + program.parameters.exit_sigma_multiplier * signal.frozen_entry_sigma
        )
    return current.bar.close >= threshold


def normalized_vwap_deviation(close: Decimal, vwap: Decimal) -> Decimal:
    """Compute d_t = close_t / VWAP_t - 1 with fixed Decimal precision."""

    price = _decimal(close, "close")
    reference = _decimal(vwap, "vwap")
    if price <= 0 or reference <= 0:
        raise ValueError("close and VWAP must be positive")
    with localcontext(_DECIMAL_CONTEXT):
        return price / reference - Decimal(1)


def sample_standard_deviation(values: Sequence[Decimal]) -> Decimal:
    """Return sample standard deviation with context-independent precision."""

    points = tuple(_decimal(value, "deviation") for value in values)
    if len(points) < 2:
        raise UnavailableIndicatorError("sample standard deviation requires two values")
    with localcontext(_DECIMAL_CONTEXT):
        mean = sum(points, Decimal(0)) / Decimal(len(points))
        variance = sum(((point - mean) ** 2 for point in points), Decimal(0)) / Decimal(
            len(points) - 1
        )
        result = variance.sqrt()
    if not result.is_finite():
        raise UnavailableIndicatorError("sample standard deviation is not finite")
    return result


def vwap_deviation_sigma(
    preceding_close_vwap_pairs: Sequence[tuple[Decimal, Decimal]],
    signal_close: Decimal,
    signal_vwap: Decimal,
    *,
    lookback: int,
) -> tuple[Decimal, Decimal]:
    """Return frozen prior-bar sigma and current normalized deviation."""

    if type(lookback) is not int or lookback < 2:
        raise ValueError("lookback must be at least two")
    pairs = tuple(preceding_close_vwap_pairs)
    if len(pairs) != lookback:
        raise UnavailableIndicatorError("VWAP deviation warmup is incomplete")
    deviations = tuple(normalized_vwap_deviation(close, vwap) for close, vwap in pairs)
    sigma = sample_standard_deviation(deviations)
    current = normalized_vwap_deviation(signal_close, signal_vwap)
    return sigma, current


def vwap_sigma_stop_distance(
    entry_reference_price: Decimal, entry_sigma: Decimal, stop_sigma_multiplier: Decimal
) -> Decimal:
    """Convert normalized frozen entry sigma to a positive price distance."""

    entry = _decimal(entry_reference_price, "entry_reference_price")
    sigma = _decimal(entry_sigma, "entry_sigma")
    multiplier = _decimal(stop_sigma_multiplier, "stop_sigma_multiplier")
    if entry <= 0 or sigma <= 0 or multiplier <= 0:
        raise ValueError("entry, sigma and multiplier must be positive")
    with localcontext(_DECIMAL_CONTEXT):
        distance = entry * sigma * multiplier
    if distance <= 0 or not distance.is_finite():
        raise UnavailableIndicatorError("VWAP stop distance is invalid")
    return distance


def efficiency_ratio(closes: Sequence[Decimal], periods: int) -> Decimal:
    """Compute ER over L+1 contiguous closes, rejecting a zero denominator."""

    if type(periods) is not int or periods < 1:
        raise ValueError("periods must be a positive integer")
    values = tuple(_decimal(value, "close") for value in closes)
    if len(values) != periods + 1:
        raise UnavailableIndicatorError("efficiency ratio requires L+1 closes")
    if any(value <= 0 for value in values):
        raise ValueError("closes must be positive")
    with localcontext(_DECIMAL_CONTEXT):
        denominator = sum(
            (
                abs(right - left)
                for left, right in zip(values, values[1:], strict=False)
            ),
            Decimal(0),
        )
        if denominator == 0:
            raise UnavailableIndicatorError("efficiency ratio denominator is zero")
        result = abs(values[-1] - values[0]) / denominator
    if not result.is_finite():
        raise UnavailableIndicatorError("efficiency ratio is not finite")
    return result


def ema_series(bars: Sequence[AggregateBar], period: int) -> tuple[Decimal | None, ...]:
    """Compute session-local EMA with deterministic SMA seed and gap rejection."""

    if type(period) is not int or period < 1:
        raise ValueError("EMA period must be positive")
    materialized = contiguous_aggregate_bars(bars)
    schedule = _SESSION_AUTHORITY.schedule_for(materialized[0].session_date)
    if schedule is None or materialized[0].timestamp != schedule.opens_at.astimezone(
        UTC
    ):
        raise UnavailableIndicatorError(
            "session-local EMA must start at the published open"
        )
    if len(materialized) < period:
        raise UnavailableIndicatorError("EMA lacks its contiguous SMA seed")
    values: list[Decimal | None] = [None] * (period - 1)
    with localcontext(_DECIMAL_CONTEXT):
        seed = sum(
            (item.close for item in materialized[:period]), Decimal(0)
        ) / Decimal(period)
        values.append(seed)
        alpha = Decimal(2) / Decimal(period + 1)
        current = seed
        for item in materialized[period:]:
            current = alpha * item.close + (Decimal(1) - alpha) * current
            values.append(current)
    return tuple(values)


def average_true_range(
    preceding_bars: Sequence[AggregateBar], lookback: int
) -> Decimal:
    """Compute ATR from prior true ranges, excluding the decision bar.

    ``preceding_bars`` must contain ``lookback + 1`` contiguous bars so every
    true range has a genuine previous close. The final supplied bar is the last
    completed bar before the decision bar.
    """

    if type(lookback) is not int or lookback < 1:
        raise ValueError("ATR lookback must be positive")
    materialized = contiguous_aggregate_bars(preceding_bars, count=lookback + 1)
    ranges: list[Decimal] = []
    with localcontext(_DECIMAL_CONTEXT):
        for previous, current in zip(materialized, materialized[1:], strict=False):
            ranges.append(
                max(
                    current.high - current.low,
                    abs(current.high - previous.close),
                    abs(current.low - previous.close),
                )
            )
        result = sum(ranges, Decimal(0)) / Decimal(lookback)
    if not result.is_finite() or result <= 0:
        raise UnavailableIndicatorError("ATR is unavailable or nonpositive")
    return result


@dataclass(frozen=True, slots=True)
class AlignedCrossEtfBars:
    timestamp: datetime
    target_bar: AggregateBar
    confirming_bar: AggregateBar


def exact_cross_etf_confirmation(
    target_bars: Sequence[AggregateBar],
    confirming_bars: Sequence[AggregateBar],
    required_count: int,
) -> tuple[AlignedCrossEtfBars, ...]:
    """Require exactly aligned, contiguous, same-session SPY/QQQ bars."""

    if type(required_count) is not int or required_count < 1:
        raise ValueError("cross confirmation count must be positive")
    target = contiguous_aggregate_bars(target_bars, count=required_count)
    confirming = contiguous_aggregate_bars(confirming_bars, count=required_count)
    if target[0].symbol == confirming[0].symbol:
        raise Arch151Error("cross-ETF confirmation requires distinct symbols")
    if (
        target[0].symbol not in INITIAL_UNIVERSE
        or confirming[0].symbol not in INITIAL_UNIVERSE
    ):
        raise Arch151Error("cross-ETF confirmation is limited to SPY and QQQ")
    pairs: list[AlignedCrossEtfBars] = []
    for left, right in zip(target, confirming, strict=True):
        if (
            left.timestamp != right.timestamp
            or left.session_date != right.session_date
            or left.resolution is not right.resolution
        ):
            raise UnavailableIndicatorError(
                "cross-ETF bars are not exactly timestamp aligned"
            )
        pairs.append(AlignedCrossEtfBars(left.timestamp, left, right))
    return tuple(pairs)


@dataclass(frozen=True, slots=True)
class TrendPullbackSignal:
    program_key: ProgramKey
    session_date: date
    setup_timestamp: datetime
    signal_timestamp: datetime
    swing_peak: Decimal
    frozen_atr: Decimal
    pullback_low: Decimal
    stop_reference_price: Decimal
    local_ema_fast: Decimal
    local_ema_slow: Decimal
    confirming_symbol: str


def family_d_entry_signal(
    program: Arch151Program,
    target_bars: Sequence[AggregateBar],
    confirming_bars: Sequence[AggregateBar],
    confirming_vwaps: Sequence[VwapObservation],
) -> TrendPullbackSignal | None:
    """Evaluate a pure local-trend/cross-ETF pullback-reclaim entry predicate.

    This scans a bounded in-memory sequence for a completed-bar setup. It does
    not model positions, fills, exits, costs, or replay a strategy.
    """

    if (
        not _is_canonical_program(program)
        or type(program.parameters) is not CrossEtfPullbackParameters
    ):
        raise UnsupportedProgramError("Family D requires a canonical pullback program")
    local = _validated_session_aggregate_bars(program, target_bars, from_open=True)
    other = _validated_session_aggregate_bars(program, confirming_bars, from_open=True)
    parameters = program.parameters
    aligned = exact_cross_etf_confirmation(local, other, len(local))
    vwap_observations = tuple(confirming_vwaps)
    if len(vwap_observations) != len(aligned) or any(
        type(observation) is not VwapObservation for observation in vwap_observations
    ):
        raise UnavailableIndicatorError("cross-ETF VWAP observations are incomplete")
    if any(
        observation.bar != pair.confirming_bar
        for observation, pair in zip(vwap_observations, aligned, strict=True)
    ):
        raise UnavailableIndicatorError(
            "cross-ETF VWAP observations are not exactly bar aligned"
        )
    vwaps = tuple(observation.vwap for observation in vwap_observations)
    local_fast = ema_series(local, parameters.ema_fast)
    local_slow = ema_series(local, parameters.ema_slow)
    other_fast = ema_series(other, parameters.ema_fast)
    other_slow = ema_series(other, parameters.ema_slow)

    minimum_index = max(
        parameters.ema_slow + 2,
        parameters.atr_lookback + 1,
        parameters.swing_peak_window_bars,
    )
    for setup_index in range(minimum_index, len(local)):
        if local_fast[setup_index] is None or local_slow[setup_index] is None:
            continue
        peak_start = setup_index - parameters.swing_peak_window_bars
        if peak_start < 0:
            continue
        peak_bars = local[peak_start:setup_index]
        if len(peak_bars) != parameters.swing_peak_window_bars:
            continue
        swing_peak = max(bar.high for bar in peak_bars)
        atr_history = local[setup_index - parameters.atr_lookback - 1 : setup_index]
        try:
            frozen_atr = average_true_range(atr_history, parameters.atr_lookback)
        except UnavailableIndicatorError:
            continue
        setup_depth = swing_peak - local[setup_index].low
        with localcontext(_DECIMAL_CONTEXT):
            setup_depth_atr = setup_depth / frozen_atr
        if not (
            parameters.pullback_min_atr
            <= setup_depth_atr
            <= parameters.pullback_max_atr
        ):
            continue

        pullback_low = local[setup_index].low
        deadline_end = min(
            len(local) - 1,
            setup_index + parameters.reclaim_deadline_bars,
        )
        reclaim_count = 0
        reclaim_indexes: list[int] = []
        invalid_setup = False
        for index in range(setup_index + 1, deadline_end + 1):
            pullback_low = min(pullback_low, local[index].low)
            with localcontext(_DECIMAL_CONTEXT):
                depth_atr = (swing_peak - pullback_low) / frozen_atr
            if depth_atr > parameters.pullback_max_atr:
                invalid_setup = True
                break
            if (
                local_fast[index] is not None
                and local[index].close > local[index - 1].high
                and local[index].close > local_fast[index]
            ):
                reclaim_count += 1
                reclaim_indexes.append(index)
            else:
                reclaim_count = 0
                reclaim_indexes.clear()
            if reclaim_count < parameters.reclaim_confirmation_bars:
                continue

            if (
                local_slow[index] is None
                or local_slow[index - 1] is None
                or local_slow[index - 2] is None
            ):
                break
            local_trend = (
                local_fast[index] is not None
                and local_slow[index] is not None
                and local_fast[index] > local_slow[index]
                and local_slow[index] > local_slow[index - 1] > local_slow[index - 2]
            )
            cross_count = parameters.cross_confirmation_bars
            if index + 1 < cross_count:
                break
            cross_start = index - cross_count + 1
            confirmation = aligned[cross_start : index + 1]
            cross_trend = len(confirmation) == cross_count and all(
                other_fast[cross_start + offset] is not None
                and other_slow[cross_start + offset] is not None
                and other[cross_start + offset].close > vwaps[cross_start + offset]
                and other_fast[cross_start + offset] > other_slow[cross_start + offset]
                for offset in range(cross_count)
            )
            if not local_trend or not cross_trend:
                break
            signal_bar = local[index]
            if not program.entry_window.contains(signal_bar.completed_at):
                break
            stop = pullback_low - parameters.stop_buffer_atr * frozen_atr
            if stop <= 0 or signal_bar.close <= stop:
                break
            return TrendPullbackSignal(
                program.key,
                signal_bar.session_date,
                local[setup_index].timestamp,
                signal_bar.timestamp,
                swing_peak,
                frozen_atr,
                pullback_low,
                stop,
                local_fast[index],
                local_slow[index],
                other[0].symbol,
            )
        if invalid_setup:
            continue
    return None


@dataclass(frozen=True, slots=True)
class EntryOpportunity:
    """A structural schedule opportunity, not a strategy signal or replay."""

    completed_signal_bar: AggregateBar
    next_minute_open: OneMinuteBar


def structural_entry_opportunities(
    program: Arch151Program,
    aggregate_bars: Sequence[AggregateBar],
    minute_bars: Sequence[OneMinuteBar],
) -> tuple[EntryOpportunity, ...]:
    """Prove entry-window schedule reachability without evaluating a signal."""

    if not _is_canonical_program(program):
        raise UnsupportedProgramError("program is not in the frozen manifest")
    aggregates = tuple(aggregate_bars)
    minutes = tuple(minute_bars)
    if any(type(bar) is not AggregateBar for bar in aggregates):
        raise TypeError("aggregate bars required")
    if any(type(bar) is not OneMinuteBar for bar in minutes):
        raise TypeError("one-minute bars required")
    minute_by_time = {bar.timestamp: bar for bar in minutes}
    opportunities: list[EntryOpportunity] = []
    for bar in aggregates:
        if (
            bar.symbol not in INITIAL_UNIVERSE
            or bar.resolution is not program.resolution
        ):
            raise Arch151Error("structural schedule input mismatches the program")
        next_minute = minute_by_time.get(bar.completed_at)
        if (
            next_minute is not None
            and next_minute.symbol == bar.symbol
            and next_minute.session_date == bar.session_date
            and program.entry_window.contains(bar.completed_at)
            and program.entry_window.contains(next_minute.timestamp)
        ):
            opportunities.append(EntryOpportunity(bar, next_minute))
    return tuple(opportunities)


class FillCostCase(StrEnum):
    ZERO = "ZERO"
    BASE = "BASE"
    STRESS = "STRESS"


@dataclass(frozen=True, slots=True)
class FillCostPolicy:
    case: FillCostCase
    adverse_slippage_bps_per_fill: Decimal
    commission_per_fill: Decimal = Decimal("0")


FILL_COST_POLICIES = (
    FillCostPolicy(FillCostCase.ZERO, Decimal("0")),
    FillCostPolicy(FillCostCase.BASE, Decimal("2")),
    FillCostPolicy(FillCostCase.STRESS, Decimal("5")),
)


@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    """One exact expanding calibration interval and its scored calendar year."""

    name: str
    calibration_start: date
    calibration_end_exclusive: date
    scored_start: date
    scored_end_exclusive: date
    scored_year: int
    fold_id: UUID

    def __post_init__(self) -> None:
        if type(self.name) is not str or type(self.fold_id) is not UUID:
            raise TypeError("walk-forward fold identity is invalid")
        if type(self.scored_year) is not int:
            raise TypeError("walk-forward scored year must be an integer")
        dates = (
            self.calibration_start,
            self.calibration_end_exclusive,
            self.scored_start,
            self.scored_end_exclusive,
        )
        if any(type(value) is not date for value in dates):
            raise TypeError("fold boundaries must be dates")
        if not (
            self.calibration_start < self.calibration_end_exclusive
            and self.calibration_end_exclusive == self.scored_start
            and self.scored_start < self.scored_end_exclusive
            and self.scored_year == self.scored_start.year
            and self.scored_end_exclusive == date(self.scored_year + 1, 1, 1)
        ):
            raise Arch151Error("walk-forward fold chronology is invalid")


def _make_walk_forward_fold(index: int, scored_year: int) -> WalkForwardFold:
    calibration_start = DEVELOPMENT_START
    calibration_end = date(scored_year, 1, 1)
    material = {
        "schema": "arch151-expanding-walk-forward-fold/v1",
        "semantic_contract_version": SEMANTIC_CONTRACT_VERSION,
        "name": f"WF{index}",
        "calibration_start": calibration_start.isoformat(),
        "calibration_end_exclusive": calibration_end.isoformat(),
        "scored_start": calibration_end.isoformat(),
        "scored_end_exclusive": date(scored_year + 1, 1, 1).isoformat(),
        "scored_year": scored_year,
    }
    fold_id = uuid5(_FOLD_NAMESPACE, _canonical_json(material).decode("utf-8"))
    return WalkForwardFold(
        f"WF{index}",
        calibration_start,
        calibration_end,
        calibration_end,
        date(scored_year + 1, 1, 1),
        scored_year,
        fold_id,
    )


WALK_FORWARD_FOLDS = tuple(
    _make_walk_forward_fold(index, year)
    for index, year in enumerate(SCORED_YEARS, start=1)
)
EVALUATION_ECONOMICS_ORDER = (
    FillCostCase.BASE,
    FillCostCase.STRESS,
    FillCostCase.ZERO,
)


def _published_sessions_for_year(year: int) -> tuple[date, ...]:
    if type(year) is not int or year not in SCORED_YEARS:
        raise ValueError("scored year is outside the frozen walk-forward period")
    sessions = tuple(
        session
        for session in _SESSION_AUTHORITY.published.sessions
        if session.year == year
    )
    if not sessions:
        raise UnavailableIndicatorError("published XNYS scored-year calendar is empty")
    return sessions


@dataclass(frozen=True, slots=True)
class FoldMetrics:
    """Session returns/trades plus evaluator-owned annual turnover.

    The architecture does not yet define the underlying turnover calculation;
    the foundation validates its value and averages the five scored-year inputs
    for ranking without deriving turnover from trade frequency.
    """

    session_dates: tuple[date, ...]
    session_net_returns: tuple[Decimal, ...]
    round_trips_by_session: tuple[int, ...]
    gross_positive_trade_pnl: Decimal
    gross_negative_trade_pnl: Decimal
    annual_turnover: Decimal

    def __post_init__(self) -> None:
        session_dates = tuple(self.session_dates)
        returns = tuple(self.session_net_returns)
        round_trips = tuple(self.round_trips_by_session)
        if (
            not session_dates
            or len(session_dates) != len(returns)
            or len(returns) != len(round_trips)
            or any(type(value) is not date for value in session_dates)
            or session_dates != tuple(sorted(set(session_dates)))
        ):
            raise Arch151Error("fold metrics require aligned full-session vectors")
        if any(type(value) is not Decimal for value in returns):
            raise TypeError("session net returns must be Decimal values")
        normalized_returns = tuple(
            _decimal(value, "session net return") for value in returns
        )
        if any(value <= -1 for value in normalized_returns):
            raise ValueError("session return must leave positive equity")
        if any(type(value) is not int or value < 0 for value in round_trips):
            raise ValueError("session round trips must be nonnegative integers")
        if (
            type(self.gross_positive_trade_pnl) is not Decimal
            or type(self.gross_negative_trade_pnl) is not Decimal
            or type(self.annual_turnover) is not Decimal
        ):
            raise TypeError("fold P&L and turnover inputs must be Decimal values")
        gross_positive = _decimal(
            self.gross_positive_trade_pnl, "gross positive trade P&L"
        )
        gross_negative = _decimal(
            self.gross_negative_trade_pnl, "gross negative trade P&L"
        )
        annual_turnover = _decimal(self.annual_turnover, "annual turnover")
        if gross_positive < 0 or gross_negative <= 0:
            raise UnavailableIndicatorError(
                "gross trade P&L must have a positive loss denominator"
            )
        if annual_turnover < 0:
            raise ValueError("annual turnover cannot be negative")
        object.__setattr__(self, "session_net_returns", normalized_returns)
        object.__setattr__(self, "session_dates", session_dates)
        object.__setattr__(self, "round_trips_by_session", round_trips)
        object.__setattr__(self, "gross_positive_trade_pnl", gross_positive)
        object.__setattr__(self, "gross_negative_trade_pnl", gross_negative)
        object.__setattr__(self, "annual_turnover", annual_turnover)

    @property
    def net_return(self) -> Decimal:
        with localcontext(_DECIMAL_CONTEXT):
            equity = Decimal(1)
            for value in self.session_net_returns:
                equity *= Decimal(1) + value
            return equity - Decimal(1)

    @property
    def profit_factor(self) -> Decimal:
        with localcontext(_DECIMAL_CONTEXT):
            result = self.gross_positive_trade_pnl / self.gross_negative_trade_pnl
        if not result.is_finite():
            raise UnavailableIndicatorError("fold profit factor is not finite")
        return result

    @property
    def max_drawdown(self) -> Decimal:
        with localcontext(_DECIMAL_CONTEXT):
            equity = Decimal(1)
            peak = equity
            worst = Decimal(0)
            for value in self.session_net_returns:
                equity *= Decimal(1) + value
                peak = max(peak, equity)
                worst = max(worst, (peak - equity) / peak)
            return worst

    @property
    def completed_round_trips(self) -> int:
        return sum(self.round_trips_by_session)

    @property
    def active_sessions(self) -> int:
        return sum(value > 0 for value in self.round_trips_by_session)


def _fold_metrics_material(metrics: FoldMetrics) -> dict[str, object]:
    return {
        "session_dates": [value.isoformat() for value in metrics.session_dates],
        "session_net_returns": [
            _decimal_text(value) for value in metrics.session_net_returns
        ],
        "round_trips_by_session": list(metrics.round_trips_by_session),
        "gross_positive_trade_pnl": _decimal_text(metrics.gross_positive_trade_pnl),
        "gross_negative_trade_pnl": _decimal_text(metrics.gross_negative_trade_pnl),
        "annual_turnover": _decimal_text(metrics.annual_turnover),
    }


@dataclass(frozen=True, slots=True)
class FoldEvaluation:
    """One immutable canonical slot × fold × economics evidence record."""

    slot_id: UUID
    program_id: UUID
    symbol: str
    fold: WalkForwardFold
    economics_case: FillCostCase
    metrics: FoldMetrics

    def __post_init__(self) -> None:
        if type(self.slot_id) is not UUID or type(self.program_id) is not UUID:
            raise TypeError("fold evaluation identities must be UUID values")
        expected_fold = (
            next(
                (
                    fold
                    for fold in WALK_FORWARD_FOLDS
                    if fold.fold_id == self.fold.fold_id
                ),
                None,
            )
            if type(self.fold) is WalkForwardFold
            else None
        )
        if expected_fold is None or self.fold != expected_fold:
            raise Arch151Error("fold evaluation chronology is not canonical")
        if type(self.economics_case) is not FillCostCase:
            raise TypeError("fold economics case must be canonical")
        if type(self.metrics) is not FoldMetrics:
            raise TypeError("fold evaluation requires typed metrics")
        slot = next(
            (item for item in CANONICAL_SLOTS if item.slot_id == self.slot_id), None
        )
        if (
            slot is None
            or slot.program_id != self.program_id
            or slot.symbol != self.symbol
        ):
            raise UnsupportedProgramError(
                "fold evaluation identity does not match a canonical slot"
            )
        expected_sessions = _published_sessions_for_year(self.fold.scored_year)
        if self.metrics.session_dates != expected_sessions:
            raise Arch151Error(
                "fold metrics must cover the full published XNYS session population"
            )
        program = _program_by_key(slot.program_key)
        assert program is not None
        entry_limit = min(
            CAUSAL_EXECUTION_POLICY.maximum_completed_round_trips_per_session,
            program.parameters.entry_limit_per_session,
        )
        if any(value > entry_limit for value in self.metrics.round_trips_by_session):
            raise Arch151Error("fold metrics exceed the frozen per-session entry cap")

    @property
    def evaluation_id(self) -> UUID:
        material = {
            "schema": "arch151-fold-evaluation/v1",
            "semantic_contract_version": SEMANTIC_CONTRACT_VERSION,
            "slot_id": str(self.slot_id),
            "program_id": str(self.program_id),
            "symbol": self.symbol,
            "fold_id": str(self.fold.fold_id),
            "economics_case": self.economics_case.value,
            "metrics": _fold_metrics_material(self.metrics),
        }
        return uuid5(_EVALUATION_NAMESPACE, _canonical_json(material).decode("utf-8"))


@dataclass(frozen=True, slots=True)
class DevelopmentEvaluationBatch:
    """Exactly five expanding folds under BASE, STRESS and ZERO economics."""

    slot_id: UUID
    records: tuple[FoldEvaluation, ...]

    def __post_init__(self) -> None:
        records = tuple(self.records)
        if type(self.slot_id) is not UUID:
            raise TypeError("evaluation batch slot identity must be a UUID")
        slot = next(
            (item for item in CANONICAL_SLOTS if item.slot_id == self.slot_id), None
        )
        if slot is None:
            raise UnsupportedProgramError("evaluation batch is not a canonical slot")
        if any(type(record) is not FoldEvaluation for record in records):
            raise TypeError("evaluation batch must contain FoldEvaluation records")
        expected = tuple(
            (fold.fold_id, economics)
            for fold in WALK_FORWARD_FOLDS
            for economics in EVALUATION_ECONOMICS_ORDER
        )
        actual = tuple(
            (record.fold.fold_id, record.economics_case) for record in records
        )
        if (
            len(records) != len(expected)
            or actual != expected
            or any(record.slot_id != self.slot_id for record in records)
        ):
            raise Arch151Error(
                "evaluation batch must contain each fold once in all three economics"
            )
        object.__setattr__(self, "records", records)

    @property
    def program_id(self) -> UUID:
        return self.records[0].program_id

    @property
    def symbol(self) -> str:
        return self.records[0].symbol

    @property
    def batch_digest(self) -> str:
        return sha256(
            _canonical_json([str(record.evaluation_id) for record in self.records])
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class DevelopmentAggregate:
    """Derived five-year economics/frequency summary for one cost case.

    Turnover is the arithmetic mean of the five evaluator-owned annual values;
    it is descriptive/ranking-only and is not inferred from trade frequency.
    """

    slot_id: UUID
    economics_case: FillCostCase
    net_return: Decimal
    profit_factor: Decimal
    positive_scored_years: int
    profitable_scored_years: int
    worst_scored_year_return: Decimal
    max_drawdown: Decimal
    average_round_trips_per_year: Decimal
    active_session_fraction: Decimal
    median_round_trips_per_active_session: Decimal
    sharpe: Decimal | None
    turnover: Decimal

    def __post_init__(self) -> None:
        if (
            type(self.slot_id) is not UUID
            or type(self.economics_case) is not FillCostCase
        ):
            raise TypeError("development aggregate identity is invalid")
        names = (
            "net_return",
            "profit_factor",
            "worst_scored_year_return",
            "max_drawdown",
            "average_round_trips_per_year",
            "active_session_fraction",
            "median_round_trips_per_active_session",
            "turnover",
        )
        if any(type(getattr(self, name)) is not Decimal for name in names):
            raise TypeError("development aggregate metrics must be Decimal values")
        for name in names:
            object.__setattr__(self, name, _decimal(getattr(self, name), name))
        if self.sharpe is not None:
            if type(self.sharpe) is not Decimal:
                raise TypeError("development Sharpe must be a Decimal value")
            object.__setattr__(self, "sharpe", _decimal(self.sharpe, "sharpe"))
        if (
            type(self.positive_scored_years) is not int
            or not 0 <= self.positive_scored_years <= len(SCORED_YEARS)
            or type(self.profitable_scored_years) is not int
            or not 0 <= self.profitable_scored_years <= len(SCORED_YEARS)
        ):
            raise ValueError("scored-year counts are invalid")
        if (
            self.net_return <= -1
            or self.worst_scored_year_return <= -1
            or self.profit_factor < 0
            or not Decimal(0) <= self.max_drawdown <= Decimal(1)
            or not Decimal(0) <= self.active_session_fraction <= Decimal(1)
            or self.average_round_trips_per_year < 0
            or self.median_round_trips_per_active_session < 0
            or self.turnover < 0
        ):
            raise ValueError("development aggregate contains invalid metrics")


class QualificationRejection(StrEnum):
    STRESS_NET_RETURN_NOT_POSITIVE = "STRESS_NET_RETURN_NOT_POSITIVE"
    STRESS_PROFIT_FACTOR_NOT_ABOVE_ONE = "STRESS_PROFIT_FACTOR_NOT_ABOVE_ONE"
    FEWER_THAN_FOUR_POSITIVE_YEARS = "FEWER_THAN_FOUR_POSITIVE_YEARS"
    FEWER_THAN_FOUR_PROFITABLE_YEARS = "FEWER_THAN_FOUR_PROFITABLE_YEARS"
    WORST_YEAR_RETURN_AT_OR_BELOW_NEGATIVE_TEN_PERCENT = (
        "WORST_YEAR_RETURN_AT_OR_BELOW_NEGATIVE_TEN_PERCENT"
    )
    MAXIMUM_DRAWDOWN_ABOVE_TWENTY_PERCENT = "MAXIMUM_DRAWDOWN_ABOVE_TWENTY_PERCENT"
    AVERAGE_ROUND_TRIPS_PER_YEAR_BELOW_100 = "AVERAGE_ROUND_TRIPS_PER_YEAR_BELOW_100"
    ACTIVE_SESSION_FRACTION_BELOW_35_PERCENT = (
        "ACTIVE_SESSION_FRACTION_BELOW_35_PERCENT"
    )
    MEDIAN_TRADES_PER_ACTIVE_SESSION_ABOVE_TWO = (
        "MEDIAN_TRADES_PER_ACTIVE_SESSION_ABOVE_TWO"
    )
    SELECTION_BIAS_EVIDENCE_UNAVAILABLE = "SELECTION_BIAS_EVIDENCE_UNAVAILABLE"


class SelectionBiasStatus(StrEnum):
    DSR_COMPUTATION_DEFERRED = "DSR_COMPUTATION_DEFERRED"


def _qualification_rejections(
    aggregate: DevelopmentAggregate,
) -> tuple[QualificationRejection, ...]:
    rejected: list[QualificationRejection] = []
    if aggregate.net_return <= 0:
        rejected.append(QualificationRejection.STRESS_NET_RETURN_NOT_POSITIVE)
    if aggregate.profit_factor <= 1:
        rejected.append(QualificationRejection.STRESS_PROFIT_FACTOR_NOT_ABOVE_ONE)
    if aggregate.positive_scored_years < 4:
        rejected.append(QualificationRejection.FEWER_THAN_FOUR_POSITIVE_YEARS)
    if aggregate.profitable_scored_years < 4:
        rejected.append(QualificationRejection.FEWER_THAN_FOUR_PROFITABLE_YEARS)
    if aggregate.worst_scored_year_return <= Decimal("-0.10"):
        rejected.append(
            QualificationRejection.WORST_YEAR_RETURN_AT_OR_BELOW_NEGATIVE_TEN_PERCENT
        )
    if aggregate.max_drawdown > Decimal("0.20"):
        rejected.append(QualificationRejection.MAXIMUM_DRAWDOWN_ABOVE_TWENTY_PERCENT)
    if aggregate.average_round_trips_per_year < Decimal(100):
        rejected.append(QualificationRejection.AVERAGE_ROUND_TRIPS_PER_YEAR_BELOW_100)
    if aggregate.active_session_fraction < Decimal("0.35"):
        rejected.append(QualificationRejection.ACTIVE_SESSION_FRACTION_BELOW_35_PERCENT)
    if aggregate.median_round_trips_per_active_session > Decimal(2):
        rejected.append(
            QualificationRejection.MEDIAN_TRADES_PER_ACTIVE_SESSION_ABOVE_TWO
        )
    return tuple(rejected)


@dataclass(frozen=True, slots=True)
class DevelopmentQualification:
    """Economic qualification plus an explicit fail-closed DSR status."""

    slot_id: UUID
    batch_digest: str
    aggregate: DevelopmentAggregate
    economic_rejection_reasons: tuple[QualificationRejection, ...]
    rejection_reasons: tuple[QualificationRejection, ...]
    selection_bias_status: SelectionBiasStatus
    qualification_id: UUID

    @property
    def economically_qualified(self) -> bool:
        return not self.economic_rejection_reasons

    @property
    def qualified(self) -> bool:
        return not self.rejection_reasons


def _annualized_sharpe(returns: Sequence[Decimal]) -> Decimal | None:
    values = tuple(returns)
    if len(values) < 2:
        return None
    deviation = sample_standard_deviation(values)
    if deviation == 0:
        return None
    with localcontext(_DECIMAL_CONTEXT):
        mean = sum(values, Decimal(0)) / Decimal(len(values))
        return mean / deviation * Decimal(252).sqrt()


def aggregate_development_economics(
    batch: DevelopmentEvaluationBatch, economics_case: FillCostCase
) -> DevelopmentAggregate:
    """Derive five-year aggregates from the complete ordered fold evidence."""

    if type(batch) is not DevelopmentEvaluationBatch:
        raise TypeError("development aggregate requires a complete evaluation batch")
    if type(economics_case) is not FillCostCase:
        raise TypeError("economics case must be canonical")
    records = tuple(
        record for record in batch.records if record.economics_case is economics_case
    )
    if tuple(record.fold for record in records) != WALK_FORWARD_FOLDS:
        raise Arch151Error("aggregate requires every exact scored fold once")
    all_returns = tuple(
        value for record in records for value in record.metrics.session_net_returns
    )
    all_round_trips = tuple(
        value for record in records for value in record.metrics.round_trips_by_session
    )
    total_sessions = len(all_round_trips)
    active_counts = tuple(value for value in all_round_trips if value > 0)
    active_sessions = len(active_counts)
    total_round_trips = sum(all_round_trips)
    with localcontext(_DECIMAL_CONTEXT):
        net_return = Decimal(1)
        for value in all_returns:
            net_return *= Decimal(1) + value
        net_return -= Decimal(1)
        gross_positive = sum(
            (record.metrics.gross_positive_trade_pnl for record in records), Decimal(0)
        )
        gross_negative = sum(
            (record.metrics.gross_negative_trade_pnl for record in records), Decimal(0)
        )
        profit_factor = gross_positive / gross_negative
        average_round_trips = Decimal(total_round_trips) / Decimal(len(SCORED_YEARS))
        active_fraction = Decimal(active_sessions) / Decimal(total_sessions)
        turnover = sum(
            (record.metrics.annual_turnover for record in records), Decimal(0)
        ) / Decimal(len(SCORED_YEARS))
        ordered_active = sorted(active_counts)
        middle = len(ordered_active) // 2
        median_active = (
            Decimal(0)
            if not ordered_active
            else Decimal(ordered_active[middle])
            if len(ordered_active) % 2
            else Decimal(ordered_active[middle - 1] + ordered_active[middle]) / 2
        )
    annual_returns = tuple(record.metrics.net_return for record in records)
    annual_profit_factors = tuple(record.metrics.profit_factor for record in records)
    running_equity = Decimal(1)
    peak = Decimal(1)
    max_drawdown = Decimal(0)
    with localcontext(_DECIMAL_CONTEXT):
        for value in all_returns:
            running_equity *= Decimal(1) + value
            peak = max(peak, running_equity)
            max_drawdown = max(max_drawdown, (peak - running_equity) / peak)
    sharpe = _annualized_sharpe(all_returns)
    return DevelopmentAggregate(
        batch.slot_id,
        economics_case,
        net_return,
        profit_factor,
        sum(value > 0 for value in annual_returns),
        sum(value > 1 for value in annual_profit_factors),
        min(annual_returns),
        max_drawdown,
        average_round_trips,
        active_fraction,
        median_active,
        sharpe,
        turnover,
    )


def qualify_development(batch: DevelopmentEvaluationBatch) -> DevelopmentQualification:
    """Evaluate frozen STRESS thresholds; DSR absence always blocks selection."""

    aggregate = aggregate_development_economics(batch, FillCostCase.STRESS)
    economic_rejections = _qualification_rejections(aggregate)
    reasons = (
        *economic_rejections,
        QualificationRejection.SELECTION_BIAS_EVIDENCE_UNAVAILABLE,
    )
    material = {
        "schema": "arch151-development-qualification/v1",
        "batch_digest": batch.batch_digest,
        "economics_case": FillCostCase.STRESS.value,
        "economic_rejections": [item.value for item in economic_rejections],
        "selection_bias_status": SelectionBiasStatus.DSR_COMPUTATION_DEFERRED.value,
    }
    qualification_id = uuid5(
        _QUALIFICATION_NAMESPACE, _canonical_json(material).decode("utf-8")
    )
    return DevelopmentQualification(
        batch.slot_id,
        batch.batch_digest,
        aggregate,
        economic_rejections,
        reasons,
        SelectionBiasStatus.DSR_COMPUTATION_DEFERRED,
        qualification_id,
    )


class PriorTrialCampaignKey(StrEnum):
    ARCH148_CHURN = "ARCH148_CHURN"
    ARCH148_LATE_OPENING_DRIVE = "ARCH148_LATE_OPENING_DRIVE"
    ARCH150_G1 = "ARCH150_G1"


_ARCH150_G1_SLOT_IDS = tuple(
    UUID(value)
    for value in (
        "69e38e92-3748-53e4-a24f-a700c04386c3",
        "05b34c9f-4aa3-5b32-99ee-e76de7d30682",
        "612e820a-25c6-56eb-ac95-fbf943352842",
        "e771607a-3c78-5bb9-970a-7e0bb34da4bd",
        "fae4d0b5-348d-5ba4-a7ea-e2d75512a09d",
        "3e4b5053-b17e-582b-851e-c8c9927e524a",
        "4fdc7fe8-6845-5e1c-8aa8-a3d679f77aa3",
        "03532ff1-5c9a-5772-8d07-f905560c7800",
        "ad36a3fb-90ce-552a-81a6-a8791bba47d0",
        "5646b3cb-0bfb-54cf-8131-d3237cabfcd2",
        "59db62c4-3d17-5e73-9f94-20e516b25b5a",
        "11e66a27-c0a7-516e-b810-37ef5c4bcb78",
        "db72c3a0-3291-5eec-b6d3-0d8546b8cd75",
        "a5a4d9cb-c97f-5e71-b2b5-44137eb6e637",
        "30b0716b-4949-5bd6-8ab8-c582c8e5d3d6",
        "997cc95c-5e7c-5252-85bf-3a76d705ca4e",
        "5d19627f-25ec-5e76-961e-3d6ac86224df",
        "7aa841e8-0e9f-5eef-89e1-4f3f377a1fc6",
        "f55fc548-6597-5d23-a7f6-1152879f76d9",
        "63c665ab-8fc7-5feb-9b20-cdb25f702685",
        "1190874c-23af-503f-8b2f-4be6c8a1da85",
        "3d79db4f-f1a0-56da-a5fd-4438c6689fdc",
        "b80e9148-1620-5f47-9a8e-a2dc89468efd",
        "c0ea9f0b-8dc4-573b-932e-4777d1817dcb",
    )
)


@dataclass(frozen=True, slots=True)
class PriorTrialLedgerEntry:
    campaign: PriorTrialCampaignKey
    distinct_trial_count: int
    report_id: UUID
    report_sha256: str
    source_commit: str
    slot_ids: tuple[UUID, ...]
    manifest_id: UUID | None
    deduplication_rationale: str
    hypothesis_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.campaign) is not PriorTrialCampaignKey:
            raise TypeError("prior-trial campaign key is invalid")
        if type(self.distinct_trial_count) is not int or self.distinct_trial_count < 1:
            raise ValueError("prior-trial count must be positive")
        if type(self.report_id) is not UUID:
            raise TypeError("prior-trial report identity must be a UUID")
        if (
            type(self.report_sha256) is not str
            or len(self.report_sha256) != 64
            or any(char not in "0123456789abcdef" for char in self.report_sha256)
        ):
            raise ValueError("prior-trial report digest must be lowercase SHA-256")
        if (
            type(self.source_commit) is not str
            or len(self.source_commit) != 40
            or any(char not in "0123456789abcdef" for char in self.source_commit)
        ):
            raise ValueError("prior-trial source commit must be a full lowercase SHA")
        if type(self.slot_ids) is not tuple or any(
            type(slot_id) is not UUID for slot_id in self.slot_ids
        ):
            raise TypeError(
                "prior-trial slot identities must be an immutable UUID tuple"
            )
        if self.slot_ids and len(self.slot_ids) != self.distinct_trial_count:
            raise Arch151Error("prior-trial slot count does not match distinct trials")
        if len(set(self.slot_ids)) != len(self.slot_ids):
            raise Arch151Error("prior-trial slot ledger contains duplicates")
        if type(self.hypothesis_keys) is not tuple or any(
            type(key) is not str or not key for key in self.hypothesis_keys
        ):
            raise TypeError(
                "prior-trial hypothesis keys must be an immutable text tuple"
            )
        if len(set(self.hypothesis_keys)) != len(self.hypothesis_keys):
            raise Arch151Error("prior-trial hypothesis keys contain duplicates")
        if (
            self.hypothesis_keys
            and len(self.hypothesis_keys) != self.distinct_trial_count
        ):
            raise Arch151Error("prior-trial hypothesis count does not match its keys")
        if (
            type(self.deduplication_rationale) is not str
            or not self.deduplication_rationale
        ):
            raise ValueError("prior-trial ledger requires a deduplication rationale")


PRIOR_TRIAL_LEDGER_ENTRIES = (
    PriorTrialLedgerEntry(
        PriorTrialCampaignKey.ARCH148_CHURN,
        4,
        UUID("19dcca18-7080-541d-9864-d730c68471e0"),
        "5baa7ef9e035f72428c623c798fb9653aa43339027c03e8e417d16c52e08aca8",
        "be30617594e197f372438dba19d325fd8737b850",
        (),
        None,
        "Count four distinct variants; repeated CONTROL/baseline observations "
        "count once, and repeated observations or reporting slices are excluded.",
        (
            "CONTROL",
            "OPPOSITE_CONFIRMATION_EXIT",
            "OPPOSITE_EXIT_COOLDOWN_15M",
            "OPPOSITE_EXIT_COOLDOWN_30M",
        ),
    ),
    PriorTrialLedgerEntry(
        PriorTrialCampaignKey.ARCH148_LATE_OPENING_DRIVE,
        1,
        UUID("42355698-d57e-5f6b-8347-6a752e5b4572"),
        "e6349ea0c7f1e1b09f165bede8c93b68fb6bc6168940fda0ae2270bf9079f19b",
        "370ebccf52a61e91979bc61efaac0001dd563be6",
        (),
        None,
        "Count one distinct late-opening-drive hypothesis; observations, cost "
        "scenarios and reporting slices are not additional trials.",
        ("OPENING_DRIVE_LATE_CAPTURE_V1",),
    ),
    PriorTrialLedgerEntry(
        PriorTrialCampaignKey.ARCH150_G1,
        24,
        UUID("22f752aa-5dc1-5e42-af29-1c7e2f921175"),
        "d3b637f410b9e8bf05d352e50efea95721151543ec6308fc270c804b5aa372c7",
        "4df84db43833edc0d1b644e2116acdfdccc5897b",
        _ARCH150_G1_SLOT_IDS,
        UUID("7e179cbc-18cf-59ce-9116-899cc876ece0"),
        "Count each of the 24 canonical program-symbol slots once; repeated "
        "observations, cost scenarios and reporting slices are excluded.",
    ),
)


def _prior_trial_entry_material(entry: PriorTrialLedgerEntry) -> dict[str, object]:
    return {
        "campaign": entry.campaign.value,
        "distinct_trial_count": entry.distinct_trial_count,
        "report_id": str(entry.report_id),
        "report_sha256": entry.report_sha256,
        "source_commit": entry.source_commit,
        "slot_ids": [str(value) for value in entry.slot_ids],
        "hypothesis_keys": list(entry.hypothesis_keys),
        "manifest_id": str(entry.manifest_id) if entry.manifest_id else None,
        "deduplication_rationale": entry.deduplication_rationale,
    }


@dataclass(frozen=True, slots=True, init=False)
class PriorTrialLedger:
    """Sealed source-owned ledger; callers cannot choose or extend its entries."""

    entries: tuple[PriorTrialLedgerEntry, ...]
    documented_prior_intraday_trials: int
    ledger_id: UUID
    fingerprint: str

    def __init__(self, *, _seal: object = None) -> None:
        if _seal is not _PRIOR_LEDGER_SEAL:
            raise Arch151Error("prior-trial ledger must be source-owned")
        canonical_entries = PRIOR_TRIAL_LEDGER_ENTRIES
        total = sum(entry.distinct_trial_count for entry in canonical_entries)
        material = {
            "schema": "arch151-prior-intraday-trial-ledger/v1",
            "semantic_contract_version": SEMANTIC_CONTRACT_VERSION,
            "entries": [
                _prior_trial_entry_material(entry) for entry in canonical_entries
            ],
            "documented_prior_intraday_trials": total,
        }
        canonical = _canonical_json(material)
        for name, value in (
            ("entries", canonical_entries),
            ("documented_prior_intraday_trials", total),
            ("ledger_id", uuid5(_LEDGER_NAMESPACE, canonical.decode("utf-8"))),
            ("fingerprint", sha256(canonical).hexdigest()),
        ):
            object.__setattr__(self, name, value)


_PRIOR_LEDGER_SEAL = object()
PRIOR_INTRADAY_TRIAL_LEDGER = PriorTrialLedger(_seal=_PRIOR_LEDGER_SEAL)


@dataclass(frozen=True, slots=True, init=False)
class SelectionBiasInputContract:
    """Frozen source inputs; the evaluator-owned DSR probability is absent."""

    schema: str
    semantic_contract_version: str
    ledger_id: UUID
    ledger_fingerprint: str
    documented_prior_intraday_trials: int
    current_search_slots: int
    minimum_effective_trial_count: int
    effective_trial_count: int
    required_probability: Decimal
    status: SelectionBiasStatus
    probability: None
    input_id: UUID
    fingerprint: str

    def __init__(self, *, _seal: object = None) -> None:
        if _seal is not _SELECTION_INPUT_SEAL:
            raise Arch151Error("selection-bias inputs must be source-owned")
        prior = PRIOR_INTRADAY_TRIAL_LEDGER.documented_prior_intraday_trials
        effective = max(64, 32 + prior)
        values = (
            ("schema", "arch151-selection-bias-input/v1"),
            ("semantic_contract_version", SEMANTIC_CONTRACT_VERSION),
            ("ledger_id", PRIOR_INTRADAY_TRIAL_LEDGER.ledger_id),
            ("ledger_fingerprint", PRIOR_INTRADAY_TRIAL_LEDGER.fingerprint),
            ("documented_prior_intraday_trials", prior),
            ("current_search_slots", 32),
            ("minimum_effective_trial_count", 64),
            ("effective_trial_count", effective),
            ("required_probability", Decimal("0.95")),
            ("status", SelectionBiasStatus.DSR_COMPUTATION_DEFERRED),
            ("probability", None),
        )
        for name, value in values:
            object.__setattr__(self, name, value)
        material = {
            name: value.value
            if type(value) is SelectionBiasStatus
            else str(value)
            if type(value) is UUID
            else _decimal_text(value)
            if type(value) is Decimal
            else value
            for name, value in values
        }
        canonical = _canonical_json(material)
        object.__setattr__(
            self,
            "input_id",
            uuid5(_SELECTION_INPUT_NAMESPACE, canonical.decode("utf-8")),
        )
        object.__setattr__(self, "fingerprint", sha256(canonical).hexdigest())


_SELECTION_INPUT_SEAL = object()
SELECTION_BIAS_INPUT = SelectionBiasInputContract(_seal=_SELECTION_INPUT_SEAL)


def _selection_bias_probability_meets_threshold(probability: Decimal) -> bool:
    """Diagnostic predicate only; it cannot create evidence or qualify a slot."""

    if type(probability) is not Decimal:
        raise TypeError("selection-bias probability must be a Decimal")
    value = _decimal(probability, "selection-bias probability")
    if not Decimal(0) <= value <= Decimal(1):
        raise ValueError("selection-bias probability must be between zero and one")
    return value >= SELECTION_BIAS_INPUT.required_probability


def _ranking_key(
    probability: Decimal,
    worst_scored_year_return: Decimal,
    stress_profit_factor: Decimal,
    stress_sharpe: Decimal,
    max_drawdown: Decimal,
    turnover: Decimal,
    slot_id: UUID,
) -> tuple[Decimal | int, ...]:
    """Pure lexicographic key; synthetic calls never create qualification authority."""

    if type(slot_id) is not UUID:
        raise TypeError("ranking slot tie-break requires an immutable UUID")
    if any(
        type(value) is not Decimal
        for value in (
            probability,
            worst_scored_year_return,
            stress_profit_factor,
            stress_sharpe,
            max_drawdown,
            turnover,
        )
    ):
        raise TypeError("ranking metrics must be Decimal values")
    values = tuple(
        _decimal(value, name)
        for name, value in (
            ("probability", probability),
            ("worst-year return", worst_scored_year_return),
            ("STRESS profit factor", stress_profit_factor),
            ("STRESS Sharpe", stress_sharpe),
            ("maximum drawdown", max_drawdown),
            ("turnover", turnover),
        )
    )
    probability_value, worst_return, profit_factor, sharpe, drawdown, turnover_value = (
        values
    )
    if not Decimal(0) <= probability_value <= Decimal(1):
        raise ValueError("ranking probability must be between zero and one")
    if profit_factor < 0 or not Decimal(0) <= drawdown <= Decimal(1):
        raise ValueError("ranking metrics are invalid")
    if turnover_value < 0:
        raise ValueError("ranking turnover cannot be negative")
    return (
        -probability_value,
        -worst_return,
        -profit_factor,
        -sharpe,
        drawdown,
        turnover_value,
        slot_id.int,
    )


@dataclass(frozen=True, slots=True)
class SyntheticRankingMaterial:
    """Untrusted pure-ranking fixture; never selection-bias evidence."""

    slot_id: UUID
    unverified_probability: Decimal
    stress_aggregate: DevelopmentAggregate

    def __post_init__(self) -> None:
        if (
            type(self.slot_id) is not UUID
            or type(self.stress_aggregate) is not DevelopmentAggregate
        ):
            raise TypeError("synthetic ranking material is not typed")
        if self.stress_aggregate.slot_id != self.slot_id:
            raise Arch151Error("synthetic ranking summary does not bind its slot")
        if self.stress_aggregate.economics_case is not FillCostCase.STRESS:
            raise Arch151Error("candidate ranking requires STRESS aggregates")
        if self.stress_aggregate.sharpe is None:
            raise UnavailableIndicatorError("ranking requires a finite STRESS Sharpe")
        if type(self.unverified_probability) is not Decimal:
            raise TypeError("synthetic ranking probability must be a Decimal")
        probability = _decimal(
            self.unverified_probability, "synthetic ranking probability"
        )
        if not Decimal(0) <= probability <= Decimal(1):
            raise ValueError(
                "synthetic ranking probability must be between zero and one"
            )
        object.__setattr__(self, "unverified_probability", probability)


def rank_synthetic_candidate_population(
    materials: Sequence[SyntheticRankingMaterial],
) -> tuple[UUID, ...]:
    """Order all 32 slots for pure tests; this output cannot freeze a candidate."""

    population = tuple(materials)
    expected = tuple(slot.slot_id for slot in CANONICAL_SLOTS)
    if len(population) != len(expected) or any(
        type(item) is not SyntheticRankingMaterial for item in population
    ):
        raise Arch151Error("synthetic ranking requires the complete 32-slot population")
    if tuple(item.slot_id for item in population) != expected:
        raise Arch151Error("synthetic ranking must preserve canonical input population")
    ordered = sorted(
        population,
        key=lambda item: _ranking_key(
            item.unverified_probability,
            item.stress_aggregate.worst_scored_year_return,
            item.stress_aggregate.profit_factor,
            item.stress_aggregate.sharpe,
            item.stress_aggregate.max_drawdown,
            item.stress_aggregate.turnover,
            item.slot_id,
        ),
    )
    return tuple(item.slot_id for item in ordered)


class FinalFreezeStatus(StrEnum):
    ZERO_CANDIDATES_DSR_AUTHORITY_DEFERRED = "ZERO_CANDIDATES_DSR_AUTHORITY_DEFERRED"


class HoldoutConclusion(StrEnum):
    PASS = "PASS"


@dataclass(frozen=True, slots=True, init=False)
class VerifiedSelectionBiasEvidence:
    """Evaluator-owned DSR evidence type; no producer exists in this milestone."""

    candidate_slot_id: UUID
    development_batch_digest: str
    ledger_id: UUID
    effective_trial_count: int
    probability: Decimal
    evidence_digest: str
    _seal: object

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise AuthorizationUnavailableError(
            "verified DSR evidence is unavailable until the evaluator milestone"
        )


@dataclass(frozen=True, slots=True, init=False)
class AuthenticatedDevelopmentEvidence:
    """Authenticated evaluator output type; this source foundation cannot issue it."""

    freeze_id: UUID
    source_manifest_id: UUID
    batch_digests: tuple[str, ...]
    evidence_digest: str
    _seal: object

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise AuthorizationUnavailableError(
            "authenticated development evidence is unavailable in this foundation"
        )


@dataclass(frozen=True, slots=True, init=False)
class AuthenticatedHoldoutPass:
    """Evaluator-owned holdout result type; no holdout reader is present here."""

    freeze_id: UUID
    candidate_slot_id: UUID
    conclusion: HoldoutConclusion
    evidence_digest: str
    _seal: object

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise AuthorizationUnavailableError(
            "authenticated holdout PASS is unavailable in this foundation"
        )


@dataclass(frozen=True, slots=True, init=False)
class HoldoutAuthorization:
    """Sealed permission record bound to one exact source-owned freeze."""

    freeze_id: UUID
    candidate_slot_id: UUID
    development_evidence_digest: str
    selection_bias_evidence_digest: str
    _seal: object

    def __init__(
        self,
        *,
        _seal: object = None,
        freeze_id: UUID,
        candidate_slot_id: UUID,
        development_evidence_digest: str,
        selection_bias_evidence_digest: str,
    ) -> None:
        if _seal is not _HOLDOUT_AUTHORIZATION_SEAL:
            raise AuthorizationUnavailableError(
                "holdout authorization must come from the source gate"
            )
        for name, value in (
            ("freeze_id", freeze_id),
            ("candidate_slot_id", candidate_slot_id),
            ("development_evidence_digest", development_evidence_digest),
            ("selection_bias_evidence_digest", selection_bias_evidence_digest),
            ("_seal", _seal),
        ):
            object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True, init=False)
class ExtensionAuthorization:
    """Sealed extension permission bound to the same candidate and holdout PASS."""

    freeze_id: UUID
    candidate_slot_id: UUID
    holdout_pass_digest: str
    _seal: object

    def __init__(
        self,
        *,
        _seal: object = None,
        freeze_id: UUID,
        candidate_slot_id: UUID,
        holdout_pass_digest: str,
    ) -> None:
        if _seal is not _EXTENSION_AUTHORIZATION_SEAL:
            raise AuthorizationUnavailableError(
                "extension authorization must come from the source gate"
            )
        for name, value in (
            ("freeze_id", freeze_id),
            ("candidate_slot_id", candidate_slot_id),
            ("holdout_pass_digest", holdout_pass_digest),
            ("_seal", _seal),
        ):
            object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True, init=False)
class FinalCandidateFreeze:
    """Source-issued zero-or-one freeze; this version can issue zero only."""

    source_manifest_id: UUID
    batch_digests: tuple[str, ...]
    economically_qualified_slot_ids: tuple[UUID, ...]
    candidate_slot_id: UUID | None
    candidate_program_id: UUID | None
    selection_bias_status: SelectionBiasStatus
    status: FinalFreezeStatus
    freeze_id: UUID
    fingerprint: str
    _seal: object

    def __init__(
        self,
        *,
        _seal: object = None,
        batch_digests: tuple[str, ...],
        economically_qualified_slot_ids: tuple[UUID, ...],
    ) -> None:
        if _seal is not _FINAL_FREEZE_SEAL:
            raise Arch151Error("final candidate freeze must be source-owned")
        material = {
            "schema": "arch151-final-candidate-freeze/v1",
            "semantic_contract_version": SEMANTIC_CONTRACT_VERSION,
            "source_manifest_id": str(CANONICAL_MANIFEST.manifest_id),
            "batch_digests": list(batch_digests),
            "economically_qualified_slot_ids": [
                str(value) for value in economically_qualified_slot_ids
            ],
            "candidate_slot_id": None,
            "selection_bias_status": SelectionBiasStatus.DSR_COMPUTATION_DEFERRED.value,
        }
        canonical = _canonical_json(material)
        values = (
            ("source_manifest_id", CANONICAL_MANIFEST.manifest_id),
            ("batch_digests", batch_digests),
            ("economically_qualified_slot_ids", economically_qualified_slot_ids),
            ("candidate_slot_id", None),
            ("candidate_program_id", None),
            ("selection_bias_status", SelectionBiasStatus.DSR_COMPUTATION_DEFERRED),
            ("status", FinalFreezeStatus.ZERO_CANDIDATES_DSR_AUTHORITY_DEFERRED),
            ("freeze_id", uuid5(_FINAL_FREEZE_NAMESPACE, canonical.decode("utf-8"))),
            ("fingerprint", sha256(canonical).hexdigest()),
            ("_seal", _seal),
        )
        for name, value in values:
            object.__setattr__(self, name, value)


def freeze_final_candidate_set(
    batches: Sequence[DevelopmentEvaluationBatch],
) -> FinalCandidateFreeze:
    """Freeze the complete population; DSR deferral always yields zero candidates."""

    population = tuple(batches)
    expected_slot_ids = tuple(slot.slot_id for slot in CANONICAL_SLOTS)
    if len(population) != len(expected_slot_ids) or any(
        type(batch) is not DevelopmentEvaluationBatch for batch in population
    ):
        raise Arch151Error("final freeze requires all 32 canonical slot batches")
    actual_slot_ids = tuple(batch.slot_id for batch in population)
    if actual_slot_ids != expected_slot_ids:
        raise Arch151Error(
            "final freeze population must match canonical manifest order exactly"
        )
    qualifications = tuple(qualify_development(batch) for batch in population)
    economically_qualified = tuple(
        result.slot_id for result in qualifications if result.economically_qualified
    )
    batch_digests = tuple(batch.batch_digest for batch in population)
    return FinalCandidateFreeze(
        _seal=_FINAL_FREEZE_SEAL,
        batch_digests=batch_digests,
        economically_qualified_slot_ids=economically_qualified,
    )


def authorize_holdout(
    freeze: FinalCandidateFreeze,
    development_evidence: AuthenticatedDevelopmentEvidence | None = None,
    selection_bias_evidence: VerifiedSelectionBiasEvidence | None = None,
) -> HoldoutAuthorization:
    """Issue a bound authorization record only from verified source evidence."""

    if (
        type(freeze) is not FinalCandidateFreeze
        or getattr(freeze, "_seal", None) is not _FINAL_FREEZE_SEAL
    ):
        raise AuthorizationUnavailableError("source-owned final freeze is required")
    if freeze.candidate_slot_id is None:
        raise AuthorizationUnavailableError(
            "holdout is sealed because the source-owned freeze contains zero candidates"
        )
    if (
        type(development_evidence) is not AuthenticatedDevelopmentEvidence
        or getattr(development_evidence, "_seal", None)
        is not _AUTHENTICATED_DEVELOPMENT_EVIDENCE_SEAL
        or type(selection_bias_evidence) is not VerifiedSelectionBiasEvidence
        or getattr(selection_bias_evidence, "_seal", None)
        is not _VERIFIED_SELECTION_BIAS_SEAL
    ):
        raise AuthorizationUnavailableError(
            "complete authenticated development and verified DSR evidence are required"
        )
    if (
        development_evidence.freeze_id != freeze.freeze_id
        or development_evidence.source_manifest_id != freeze.source_manifest_id
        or development_evidence.batch_digests != freeze.batch_digests
        or selection_bias_evidence.candidate_slot_id != freeze.candidate_slot_id
        or selection_bias_evidence.ledger_id != SELECTION_BIAS_INPUT.ledger_id
        or selection_bias_evidence.effective_trial_count
        != SELECTION_BIAS_INPUT.effective_trial_count
        or not _selection_bias_probability_meets_threshold(
            selection_bias_evidence.probability
        )
    ):
        raise AuthorizationUnavailableError(
            "holdout evidence does not authenticate the exact frozen candidate"
        )
    return HoldoutAuthorization(
        _seal=_HOLDOUT_AUTHORIZATION_SEAL,
        freeze_id=freeze.freeze_id,
        candidate_slot_id=freeze.candidate_slot_id,
        development_evidence_digest=development_evidence.evidence_digest,
        selection_bias_evidence_digest=selection_bias_evidence.evidence_digest,
    )


def authorize_extension(
    freeze: FinalCandidateFreeze,
    holdout_authorization: HoldoutAuthorization,
    holdout_pass: AuthenticatedHoldoutPass,
) -> ExtensionAuthorization:
    """Issue an extension record only for the same frozen candidate's PASS."""

    if (
        type(freeze) is not FinalCandidateFreeze
        or getattr(freeze, "_seal", None) is not _FINAL_FREEZE_SEAL
        or freeze.candidate_slot_id is None
        or type(holdout_authorization) is not HoldoutAuthorization
        or getattr(holdout_authorization, "_seal", None)
        is not _HOLDOUT_AUTHORIZATION_SEAL
        or type(holdout_pass) is not AuthenticatedHoldoutPass
        or getattr(holdout_pass, "_seal", None) is not _AUTHENTICATED_HOLDOUT_PASS_SEAL
        or getattr(holdout_pass, "conclusion", None) is not HoldoutConclusion.PASS
    ):
        raise AuthorizationUnavailableError(
            "source-owned candidate, holdout authorization and authenticated PASS "
            "are required"
        )
    if (
        holdout_authorization.freeze_id != freeze.freeze_id
        or holdout_authorization.candidate_slot_id != freeze.candidate_slot_id
        or holdout_pass.freeze_id != freeze.freeze_id
        or holdout_pass.candidate_slot_id != freeze.candidate_slot_id
    ):
        raise AuthorizationUnavailableError(
            "extension evidence is not bound to the exact frozen candidate"
        )
    return ExtensionAuthorization(
        _seal=_EXTENSION_AUTHORIZATION_SEAL,
        freeze_id=freeze.freeze_id,
        candidate_slot_id=freeze.candidate_slot_id,
        holdout_pass_digest=holdout_pass.evidence_digest,
    )


class StopGapRule(StrEnum):
    OBSERVED_OPEN_IF_THROUGH = "OBSERVED_OPEN_IF_THROUGH"
    OTHERWISE_STOP_REFERENCE = "OTHERWISE_STOP_REFERENCE"


class AmbiguousIntraminuteRule(StrEnum):
    STOP_PRECEDES_TARGET = "STOP_PRECEDES_TARGET"


class TrailingActivationRule(StrEnum):
    NEXT_OBSERVATION_ONLY = "NEXT_OBSERVATION_ONLY"


class TrailingMonotonicityRule(StrEnum):
    MONOTONIC_ONLY = "MONOTONIC_ONLY"


class MissingObservationRule(StrEnum):
    NO_SYNTHESIS_NO_CARRY_NO_SUBSTITUTION = "NO_SYNTHESIS_NO_CARRY_NO_SUBSTITUTION"
    PENDING_EXIT_REMAINS_PENDING = "PENDING_EXIT_REMAINS_PENDING"


class FillCostApplicationRule(StrEnum):
    ONCE_PER_ACTUAL_FILL = "ONCE_PER_ACTUAL_FILL"


class TargetReferenceRule(StrEnum):
    TARGET_REFERENCE_BEFORE_ADVERSE_COSTS = "TARGET_REFERENCE_BEFORE_ADVERSE_COSTS"


class FinalObservedBarRule(StrEnum):
    NO_RETROSPECTIVE_FINAL_BAR_DESIGNATION = "NO_RETROSPECTIVE_FINAL_BAR_DESIGNATION"


@dataclass(frozen=True, slots=True)
class CausalExecutionPolicy:
    """Typed execution contract only; no replay or fill engine is supplied."""

    schema: str = field(default=EXECUTION_POLICY_SCHEMA, init=False)
    semantic_contract_version: str = field(
        default=SEMANTIC_CONTRACT_VERSION, init=False
    )
    decision_requires_completed_bar: bool = field(default=True, init=False)
    entry_requires_immediately_following_minute_open: bool = field(
        default=True, init=False
    )
    missing_entry_expires_without_chase: bool = field(default=True, init=False)
    per_slot_unleveraged_long_or_flat: bool = field(default=True, init=False)
    combined_multi_slot_allocation_allowed: bool = field(default=False, init=False)
    averaging_down_allowed: bool = field(default=False, init=False)
    pyramiding_allowed: bool = field(default=False, init=False)
    overnight_allowed: bool = field(default=False, init=False)
    stop_gap_rule: StopGapRule = field(
        default=StopGapRule.OBSERVED_OPEN_IF_THROUGH, init=False
    )
    non_gap_stop_touch_rule: StopGapRule = field(
        default=StopGapRule.OTHERWISE_STOP_REFERENCE, init=False
    )
    ambiguous_bar_rule: AmbiguousIntraminuteRule = field(
        default=AmbiguousIntraminuteRule.STOP_PRECEDES_TARGET, init=False
    )
    fill_cost_application_rule: FillCostApplicationRule = field(
        default=FillCostApplicationRule.ONCE_PER_ACTUAL_FILL, init=False
    )
    target_reference_rule: TargetReferenceRule = field(
        default=TargetReferenceRule.TARGET_REFERENCE_BEFORE_ADVERSE_COSTS,
        init=False,
    )
    final_observed_bar_rule: FinalObservedBarRule = field(
        default=FinalObservedBarRule.NO_RETROSPECTIVE_FINAL_BAR_DESIGNATION,
        init=False,
    )
    trailing_rule: TrailingActivationRule = field(
        default=TrailingActivationRule.NEXT_OBSERVATION_ONLY, init=False
    )
    trailing_monotonicity_rule: TrailingMonotonicityRule = field(
        default=TrailingMonotonicityRule.MONOTONIC_ONLY, init=False
    )
    missing_observation_rules: tuple[MissingObservationRule, ...] = field(
        default=(
            MissingObservationRule.NO_SYNTHESIS_NO_CARRY_NO_SUBSTITUTION,
            MissingObservationRule.PENDING_EXIT_REMAINS_PENDING,
        ),
        init=False,
    )
    max_hold_uses_elapsed_wall_clock: bool = field(default=True, init=False)
    cooldown_uses_elapsed_wall_clock: bool = field(default=True, init=False)
    maximum_hold_exit_uses_next_observed_open: bool = field(default=True, init=False)
    reversion_exit_uses_next_observed_open: bool = field(default=True, init=False)
    maximum_completed_round_trips_per_session: int = field(default=2, init=False)
    liquidation_minutes_before_close: int = field(default=5, init=False)
    liquidation_uses_first_observed_open_before_close: bool = field(
        default=True, init=False
    )
    no_entries_at_or_after_liquidation: bool = field(default=True, init=False)
    missing_liquidation_observation_fails_closed: bool = field(default=True, init=False)
    failed_liquidation_preserves_complete_evidence: bool = field(
        default=True, init=False
    )
    frequency_denominator_is_full_published_session_population: bool = field(
        default=True, init=False
    )


CAUSAL_EXECUTION_POLICY = CausalExecutionPolicy()


def __all_canonical_check() -> None:
    """Fail fast at import if the edited source population is internally invalid."""

    if len(CANONICAL_PROGRAMS) != 16 or len(CANONICAL_SLOTS) != 32:
        raise RuntimeError("Arch151 canonical population cardinality changed")
    if tuple(program.key for program in CANONICAL_PROGRAMS) != tuple(ProgramKey):
        raise RuntimeError("Arch151 program order changed")
    for family in StrategyFamily:
        family_programs = tuple(
            item for item in CANONICAL_PROGRAMS if item.family is family
        )
        if len(family_programs) != 4:
            raise RuntimeError("Arch151 family population must contain four programs")
        if (
            sum(
                item.resolution is BarResolution.FIVE_MINUTE for item in family_programs
            )
            != 2
        ):
            raise RuntimeError("Arch151 family must contain two 5m programs")
        if (
            sum(
                item.resolution is BarResolution.FIFTEEN_MINUTE
                for item in family_programs
            )
            != 2
        ):
            raise RuntimeError("Arch151 family must contain two 15m programs")
    if len({item.slot_id for item in CANONICAL_SLOTS}) != 32:
        raise RuntimeError("Arch151 slot identities must be unique")
    if any(not validate_slot(item) for item in CANONICAL_SLOTS):
        raise RuntimeError("Arch151 canonical slot validation failed")


__all_canonical_check()


__all__ = (
    "AGGREGATION_SCHEMA",
    "AuthenticatedDevelopmentEvidence",
    "AuthenticatedHoldoutPass",
    "Arch151Error",
    "Arch151Program",
    "AlignedCrossEtfBars",
    "AggregateBar",
    "AggregateStream",
    "AmbiguousIntraminuteRule",
    "AuthorizationUnavailableError",
    "BarResolution",
    "CAUSAL_EXECUTION_POLICY",
    "CANONICAL_MANIFEST",
    "CANONICAL_PROGRAMS",
    "CANONICAL_SLOTS",
    "CausalExecutionPolicy",
    "CrossEtfPullbackParameters",
    "DevelopmentAggregate",
    "DevelopmentEvaluationBatch",
    "DevelopmentQualification",
    "DEVELOPMENT_END",
    "DEVELOPMENT_START",
    "EVALUATION_ECONOMICS_ORDER",
    "EntryOpportunity",
    "EntryWindow",
    "ExtensionAuthorization",
    "FILL_COST_POLICIES",
    "FamilyACalibration",
    "FamilyASessionMeasure",
    "FinalObservedBarRule",
    "FinalCandidateFreeze",
    "FinalFreezeStatus",
    "FillCostApplicationRule",
    "FillCostCase",
    "FillCostPolicy",
    "FoldEvaluation",
    "FoldMetrics",
    "HoldoutAuthorization",
    "HoldoutConclusion",
    "IncompleteAggregationError",
    "MissingObservationRule",
    "NoiseBreakoutParameters",
    "NoiseBreakoutSignal",
    "OneMinuteBar",
    "OpeningRangeRetestParameters",
    "OpeningRangeRetestSignal",
    "PRIOR_INTRADAY_TRIAL_LEDGER",
    "PRIOR_TRIAL_LEDGER_ENTRIES",
    "PriorTrialCampaignKey",
    "PriorTrialLedger",
    "PriorTrialLedgerEntry",
    "ProgramKey",
    "QualificationRejection",
    "SCORED_YEARS",
    "SELECTION_BIAS_INPUT",
    "SelectionBiasInputContract",
    "SelectionBiasStatus",
    "StrategyFamily",
    "StopGapRule",
    "SyntheticRankingMaterial",
    "TrialSlot",
    "TargetReferenceRule",
    "TrailingActivationRule",
    "TrailingMonotonicityRule",
    "UnavailableIndicatorError",
    "UnsupportedProgramError",
    "VwapMeanReversionParameters",
    "VwapMeanReversionSignal",
    "VwapObservation",
    "VerifiedSelectionBiasEvidence",
    "WALK_FORWARD_FOLDS",
    "WalkForwardFold",
    "TrendPullbackSignal",
    "aggregate_session_vwap",
    "aggregate_sparse_bars",
    "aggregate_development_economics",
    "authorize_extension",
    "authorize_holdout",
    "average_true_range",
    "calibrate_family_a",
    "canonical_manifest",
    "contiguous_aggregate_bars",
    "efficiency_ratio",
    "ema_series",
    "exact_cross_etf_confirmation",
    "family_a_breakout_level",
    "family_a_entry_signal",
    "family_a_initial_risk",
    "family_a_regime_passes",
    "family_a_session_measure",
    "family_b_entry_signal",
    "family_c_entry_signal",
    "family_c_reversion_exit",
    "family_d_entry_signal",
    "freeze_final_candidate_set",
    "normalized_vwap_deviation",
    "program_fingerprint",
    "program_from_bytes",
    "program_id",
    "program_to_bytes",
    "qualify_development",
    "rank_synthetic_candidate_population",
    "sample_standard_deviation",
    "structural_entry_opportunities",
    "vwap_deviation_sigma",
    "vwap_sigma_stop_distance",
)
