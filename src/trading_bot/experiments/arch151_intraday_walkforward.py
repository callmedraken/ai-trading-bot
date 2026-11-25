"""Architecture 151 frozen intraday walk-forward source contracts.

This module defines the immutable candidate population and pure causal feature
and execution-policy primitives. Import and pure feature operations do not read
custody. The fixed-root accepted-custody loader is reserved for a separately
authorized future operation and is never invoked by import or synthetic tests.
This module does not replay strategies, acquire data, access providers or
credentials, or execute trading effects.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Context, Decimal, InvalidOperation, localcontext
from enum import IntEnum, StrEnum
from hashlib import sha256
from types import MappingProxyType
from uuid import NAMESPACE_URL, UUID, uuid5
from zoneinfo import ZoneInfo

from trading_bot.experiments import arch150_g1_discovery as arch150_d1r
from trading_bot.experiments import arch150_intraday_ai as arch150
from trading_bot.experiments.arch148_intraday import (
    HistoricalIntradaySessionAuthority,
)

PROGRAM_SCHEMA = "arch151-intraday-walkforward-program/v1"
SLOT_SCHEMA = "arch151-intraday-walkforward-trial-slot/v1"
MANIFEST_SCHEMA = "arch151-intraday-walkforward-population/v1"
BAR_SCHEMA = "arch151-intraday-walkforward-bar/v1"
AGGREGATION_SCHEMA = "arch151-sparse-aggregate/v1"
CALIBRATION_SCHEMA = "arch151-family-a-calibration/v2"
EXECUTION_POLICY_SCHEMA = "arch151-causal-execution-policy/v1"
_FOLD_EVALUATION_SCHEMA = "arch151-fold-evaluation/v3"
_QUALIFICATION_SCHEMA = "arch151-development-qualification/v3"
SEMANTIC_CONTRACT_VERSION = "arch151-frozen-design-2026-11-23/v1"
IDENTITY_NAMESPACE_SEED = (
    "urn:ai-trading-bot:arch151:intraday-walkforward-foundation:v1"
)

DEVELOPMENT_START = date(2016, 1, 1)
SCORED_YEARS = (2019, 2020, 2021, 2022, 2023)
DEVELOPMENT_END = date(2024, 1, 1)
DSR_OBSERVATION_COUNT = 1_258
DSR_DECIMAL_PRECISION = 60
INITIAL_UNIVERSE = ("SPY", "QQQ")
ARCH150_D1R_DATASET_ID = UUID("ff5a3847-09c2-5902-b174-9e77eebf7d53")
ARCH150_D1R_DATASET_SHA256 = (
    "0070a5c0cfa5cd7878253d93bc0895b46da28d8b5e2a71395e66ce904b3f85dd"
)
ARCH150_D1R_CUSTODY_ID = UUID("21e121dc-a9da-538f-bc88-c15fe7ea7f50")
ARCH150_D1R_CUSTODY_SHA256 = (
    "5b6ac554eda73b588f2f6d664c14e5c7fca3c151966cb546c17621d0c7e6ad83"
)
ARCH150_D1R_EVIDENCE_ID = UUID("c31bb29d-3d53-5e2f-a01f-55a42ec96295")
ARCH150_D1R_EVIDENCE_SHA256 = (
    "e58a6e5d95c44b33eb34311f705e6cc26982120689f98ddb207768dc304b4ecd"
)
ARCH150_D1R_SCHEDULED_SLOTS_PER_SYMBOL = 781_980
ARCH150_D1R_OBSERVED_COUNTS = (("SPY", 781_876), ("QQQ", 781_865))
ARCH150_D1R_MISSING_COUNTS = (("SPY", 104), ("QQQ", 115))
ARCH150_D1R_COMMON_MISSING_COUNT = 64
ARCH150_D1R_UNION_MISSING_COUNT = 155
ARCH150_D1R_AFFECTED_SESSION_COUNT = 9
ARCH150_D1R_FULLY_MISSING_SESSION_COUNTS = (("SPY", 0), ("QQQ", 0))
NEW_YORK = ZoneInfo("America/New_York")
_SESSION_AUTHORITY = HistoricalIntradaySessionAuthority()
_DECIMAL_CONTEXT = Context(prec=60)

_ROOT_NAMESPACE = uuid5(NAMESPACE_URL, IDENTITY_NAMESPACE_SEED)
_PROGRAM_NAMESPACE = uuid5(_ROOT_NAMESPACE, "program-identity/v1")
_SLOT_NAMESPACE = uuid5(_ROOT_NAMESPACE, "trial-slot-identity/v1")
_MANIFEST_NAMESPACE = uuid5(_ROOT_NAMESPACE, "population-identity/v1")
_AGGREGATION_NAMESPACE = uuid5(_ROOT_NAMESPACE, "sparse-aggregation/v1")
_CALIBRATION_NAMESPACE = uuid5(_ROOT_NAMESPACE, "family-a-calibration/v2")
_D1R_HISTORY_NAMESPACE = uuid5(_ROOT_NAMESPACE, "arch150-d1r-source-history/v1")
_FEATURE_CACHE_NAMESPACE = uuid5(_ROOT_NAMESPACE, "session-feature-cache-key/v1")
_FOLD_NAMESPACE = uuid5(_ROOT_NAMESPACE, "walk-forward-fold/v1")
_EVALUATION_NAMESPACE = uuid5(_ROOT_NAMESPACE, "fold-evaluation/v3")
_LEDGER_NAMESPACE = uuid5(_ROOT_NAMESPACE, "prior-trial-ledger/v1")
_SELECTION_INPUT_NAMESPACE = uuid5(_ROOT_NAMESPACE, "selection-bias-input/v2")
_DSR_EVIDENCE_NAMESPACE = uuid5(_ROOT_NAMESPACE, "verified-dsr-evidence/v1")
_DSR_CALCULATION_NAMESPACE = uuid5(_ROOT_NAMESPACE, "dsr-population-calculation/v2")
_QUALIFICATION_NAMESPACE = uuid5(_ROOT_NAMESPACE, "development-qualification/v3")
_FINAL_FREEZE_NAMESPACE = uuid5(_ROOT_NAMESPACE, "final-candidate-freeze/v2")
_AUTHENTICATED_DEVELOPMENT_EVIDENCE_NAMESPACE = uuid5(
    _ROOT_NAMESPACE, "authenticated-development-evidence/v1"
)
_LATER_PERIOD_QUALIFICATION_NAMESPACE = uuid5(
    _ROOT_NAMESPACE, "later-period-qualification/v1"
)
_HOLDOUT_AUTHORIZATION_NAMESPACE = uuid5(_ROOT_NAMESPACE, "holdout-authorization/v1")
_EXTENSION_AUTHORIZATION_NAMESPACE = uuid5(
    _ROOT_NAMESPACE, "extension-authorization/v1"
)
_RESEARCH_SURVIVOR_NAMESPACE = uuid5(
    _ROOT_NAMESPACE, "research-survivor-classification/v1"
)
_FAMILY_A_MEASURE_SEAL = object()
_FAMILY_A_CALIBRATION_SEAL = object()
_VERIFIED_SPARSE_SESSION_SEAL = object()
_SYNTHETIC_SPARSE_SESSION_SEAL = object()
_D1R_HISTORY_SEAL = object()
_SYNTHETIC_HISTORY_SEAL = object()
_PRIOR_LEDGER_SEAL = object()
_SELECTION_INPUT_SEAL = object()
_FINAL_FREEZE_SEAL = object()
_AUTHENTICATED_DEVELOPMENT_EVIDENCE_SEAL = object()
_VERIFIED_SELECTION_BIAS_SEAL = object()
_AUTHENTICATED_HOLDOUT_PASS_SEAL = object()
_AUTHENTICATED_EXTENSION_PASS_SEAL = object()
_HOLDOUT_AUTHORIZATION_SEAL = object()
_EXTENSION_AUTHORIZATION_SEAL = object()
_LATER_PERIOD_QUALIFICATION_SEAL = object()
_RESEARCH_SURVIVOR_CLASSIFICATION_SEAL = object()


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


def _is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


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


@dataclass(frozen=True, slots=True, init=False)
class VerifiedSparseSession:
    """Production-issued seal binding one projection to accepted D1R history."""

    symbol: str
    resolution: BarResolution
    session_date: date
    bars: tuple[AggregateBar, ...]
    history_source_digest: str
    minute_source_digest: str | None
    source_digest: str
    _seal: object

    def __init__(
        self,
        *,
        symbol: str,
        resolution: BarResolution,
        session_date: date,
        bars: tuple[AggregateBar, ...],
        history_source_digest: str | None = None,
        source_digest: str,
        minute_source_digest: str | None = None,
        _seal: object = None,
    ) -> None:
        if _seal is not _VERIFIED_SPARSE_SESSION_SEAL:
            raise AuthorizationUnavailableError(
                "verified sparse-session evidence is evaluator-owned and unavailable"
            )
        for name, value in (
            ("symbol", symbol),
            ("resolution", resolution),
            ("session_date", session_date),
            ("bars", bars),
            ("history_source_digest", history_source_digest),
            ("minute_source_digest", minute_source_digest),
            ("source_digest", source_digest),
            ("_seal", _seal),
        ):
            object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True, init=False)
class _SyntheticSparseSessionEvidence:
    """Test-only projection evidence, deliberately distinct from production."""

    symbol: str
    resolution: BarResolution
    session_date: date
    bars: tuple[AggregateBar, ...]
    history_source_digest: str
    minute_source_digest: str | None
    source_digest: str
    _seal: object

    def __init__(
        self,
        *,
        symbol: str,
        resolution: BarResolution,
        session_date: date,
        bars: tuple[AggregateBar, ...],
        history_source_digest: str,
        source_digest: str,
        minute_source_digest: str | None,
        _seal: object = None,
    ) -> None:
        if _seal is not _SYNTHETIC_SPARSE_SESSION_SEAL:
            raise AuthorizationUnavailableError(
                "synthetic projection evidence is test-only"
            )
        for name, value in (
            ("symbol", symbol),
            ("resolution", resolution),
            ("session_date", session_date),
            ("bars", bars),
            ("history_source_digest", history_source_digest),
            ("minute_source_digest", minute_source_digest),
            ("source_digest", source_digest),
            ("_seal", _seal),
        ):
            object.__setattr__(self, name, value)


type _SparseSessionEvidence = VerifiedSparseSession | _SyntheticSparseSessionEvidence


@dataclass(frozen=True, slots=True)
class _SessionSourceProjection:
    symbol: str
    session_date: date
    minutes: tuple[OneMinuteBar, ...]
    aggregate_streams: tuple[AggregateStream, ...]
    verified_sessions: tuple[_SparseSessionEvidence, ...]
    vwap_by_resolution: tuple[tuple[BarResolution, tuple[VwapObservation, ...]], ...]


@dataclass(frozen=True, slots=True, init=False)
class Arch150D1RSourceHistory:
    """Source-owned projection of the accepted Arch150 D1R sparse custody."""

    source_id: UUID
    dataset_id: UUID
    dataset_sha256: str
    custody_id: UUID
    custody_sha256: str
    evidence_id: UUID
    evidence_sha256: str
    artifact_commitments: tuple[tuple[str, int, str], ...]
    source_digest: str
    _session_projections: tuple[_SessionSourceProjection, ...] = field(
        repr=False, compare=False
    )
    _projection_index: Mapping[
        tuple[str, date, BarResolution], _SessionSourceProjection
    ] = field(repr=False, compare=False)
    _seal: object = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        source_id: UUID,
        dataset_id: UUID,
        dataset_sha256: str,
        custody_id: UUID,
        custody_sha256: str,
        evidence_id: UUID,
        evidence_sha256: str,
        artifact_commitments: tuple[tuple[str, int, str], ...],
        source_digest: str,
        session_projections: tuple[_SessionSourceProjection, ...],
        _seal: object = None,
    ) -> None:
        if _seal is not _D1R_HISTORY_SEAL:
            raise AuthorizationUnavailableError(
                "Arch150 D1R history requires the fixed accepted-source adapter"
            )
        for name, value in (
            ("source_id", source_id),
            ("dataset_id", dataset_id),
            ("dataset_sha256", dataset_sha256),
            ("custody_id", custody_id),
            ("custody_sha256", custody_sha256),
            ("evidence_id", evidence_id),
            ("evidence_sha256", evidence_sha256),
            ("artifact_commitments", artifact_commitments),
            ("source_digest", source_digest),
            ("_session_projections", session_projections),
            (
                "_projection_index",
                MappingProxyType(
                    {
                        (item.symbol, item.session_date, stream.resolution): item
                        for item in session_projections
                        for stream in item.aggregate_streams
                    }
                ),
            ),
            ("_seal", _seal),
        ):
            object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True, init=False)
class _SyntheticSourceHistory:
    """Private synthetic source fixture; never accepted as D1R authority."""

    source_digest: str
    _session_projections: tuple[_SessionSourceProjection, ...] = field(
        repr=False, compare=False
    )
    _projection_index: Mapping[
        tuple[str, date, BarResolution], _SessionSourceProjection
    ] = field(repr=False, compare=False)
    _seal: object = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        source_digest: str,
        session_projections: tuple[_SessionSourceProjection, ...],
        _seal: object = None,
    ) -> None:
        if _seal is not _SYNTHETIC_HISTORY_SEAL:
            raise AuthorizationUnavailableError(
                "synthetic source history is available only to focused tests"
            )
        object.__setattr__(self, "source_digest", source_digest)
        object.__setattr__(self, "_session_projections", session_projections)
        object.__setattr__(
            self,
            "_projection_index",
            MappingProxyType(
                {
                    (item.symbol, item.session_date, stream.resolution): item
                    for item in session_projections
                    for stream in item.aggregate_streams
                }
            ),
        )
        object.__setattr__(self, "_seal", _seal)


@dataclass(frozen=True, slots=True)
class SessionFeatureCacheKey:
    """Immutable cache identity for one causal family/symbol/session prefix."""

    source_digest: str
    symbol: str
    resolution: BarResolution
    session_date: date
    program_id: UUID
    program_fingerprint: str
    cutoff_completed_at: datetime
    cache_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        if not _is_sha256(self.source_digest) or not _is_sha256(
            self.program_fingerprint
        ):
            raise ValueError("feature cache source/config fingerprints are invalid")
        if self.symbol not in INITIAL_UNIVERSE:
            raise Arch151Error("feature cache symbol is outside frozen SPY/QQQ")
        if type(self.resolution) is not BarResolution:
            raise TypeError("feature cache resolution must be canonical")
        if type(self.session_date) is not date or type(self.program_id) is not UUID:
            raise TypeError("feature cache session/program identity is invalid")
        if (
            type(self.cutoff_completed_at) is not datetime
            or self.cutoff_completed_at.tzinfo is None
            or self.cutoff_completed_at.utcoffset() is None
        ):
            raise TypeError("feature cutoff must be timezone aware")
        cutoff = self.cutoff_completed_at.astimezone(UTC)
        object.__setattr__(self, "cutoff_completed_at", cutoff)
        material = {
            "schema": "arch151-session-feature-cache-key/v1",
            "source_digest": self.source_digest,
            "symbol": self.symbol,
            "resolution_minutes": int(self.resolution),
            "session_date": self.session_date.isoformat(),
            "program_id": str(self.program_id),
            "program_fingerprint": self.program_fingerprint,
            "cutoff_completed_at": cutoff.isoformat(timespec="minutes").replace(
                "+00:00", "Z"
            ),
        }
        object.__setattr__(
            self,
            "cache_id",
            uuid5(_FEATURE_CACHE_NAMESPACE, _canonical_json(material).decode()),
        )


@dataclass(frozen=True, slots=True)
class CausalIndicatorPoint:
    bar: AggregateBar
    vwap: Decimal
    normalized_deviation: Decimal | None
    sigma: Decimal | None
    efficiency_ratio: Decimal | None
    ema_fast: Decimal | None
    ema_slow: Decimal | None
    preceding_atr: Decimal | None


@dataclass(frozen=True, slots=True)
class PreparedSessionFeatures:
    """Immutable signal-time prefix; no future aggregate/VWAP values are exposed."""

    key: SessionFeatureCacheKey
    bars: tuple[AggregateBar, ...]
    vwap_observations: tuple[VwapObservation, ...]
    indicators: tuple[CausalIndicatorPoint, ...]
    decision_bar: AggregateBar | None
    decision_vwap: VwapObservation | None
    opening_range_high: Decimal | None
    family_a_measure: FamilyASessionMeasure | None


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
    minute_bars: Iterable[OneMinuteBar],
    aggregate_stream: AggregateStream,
    *,
    verified_sessions: Sequence[_SparseSessionEvidence] = (),
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
    evidence_by_session: dict[date, _SparseSessionEvidence] = {}
    for evidence in tuple(verified_sessions):
        if not _sparse_session_evidence_is_valid(evidence):
            raise AuthorizationUnavailableError(
                "post-open VWAP requires evaluator-owned verified session evidence"
            )
        if evidence.session_date in evidence_by_session:
            raise Arch151Error("verified sparse-session evidence is duplicated")
        evidence_by_session[evidence.session_date] = evidence
    if not set(evidence_by_session).issubset(minutes_by_session):
        raise AuthorizationUnavailableError(
            "verified VWAP evidence does not match a supplied source session"
        )
    for session, session_minutes in minutes_by_session.items():
        schedule = _SESSION_AUTHORITY.schedule_for(session)
        if schedule is None:
            raise Arch151Error("VWAP source session is outside the published calendar")
        starts_at_open = session_minutes[0].timestamp == schedule.opens_at.astimezone(
            UTC
        )
        evidence = evidence_by_session.get(session)
        if not starts_at_open and evidence is None:
            raise UnavailableIndicatorError(
                "session VWAP source must begin at the published XNYS open"
            )
        if evidence is not None:
            source_digest = sha256(
                _canonical_json([_bar_material(bar) for bar in session_minutes])
            ).hexdigest()
            session_aggregates = tuple(aggregates_by_session.get(session, ()))
            if (
                evidence.symbol != session_minutes[0].symbol
                or evidence.resolution is not aggregate_stream.resolution
                or evidence.minute_source_digest != source_digest
                or evidence.bars != session_aggregates
                or evidence.source_digest
                != _verified_sparse_session_digest(
                    evidence.symbol,
                    evidence.resolution,
                    evidence.session_date,
                    evidence.bars,
                    evidence.minute_source_digest,
                    evidence.history_source_digest,
                )
            ):
                raise AuthorizationUnavailableError(
                    "VWAP source is not bound to the exact verified sparse projection"
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


def _d1r_semantic_pins_match() -> bool:
    expected = {
        "dataset.json": (str(ARCH150_D1R_DATASET_ID), ARCH150_D1R_DATASET_SHA256),
        "custody-evidence.json": (
            str(ARCH150_D1R_CUSTODY_ID),
            ARCH150_D1R_CUSTODY_SHA256,
        ),
        "evidence.json": (str(ARCH150_D1R_EVIDENCE_ID), ARCH150_D1R_EVIDENCE_SHA256),
    }
    return (
        type(arch150_d1r._SEMANTIC_PINS) is dict
        and arch150_d1r._SEMANTIC_PINS == expected
    )


def _accepted_arch150_dataset_is_valid(dataset: object) -> bool:
    if (
        type(dataset) is not arch150.ResearchDataset
        or dataset._authority_seal is not arch150._DATASET_SEAL
        or dataset.stage is not arch150.ResearchStage.DISCOVERY
        or dataset.start != date(2016, 1, 1)
        or dataset.end_exclusive != date(2024, 1, 1)
        or dataset.candidate_freeze is not None
        or dataset._sparse_custody_authority
        is not arch150._ACCEPTED_SPARSE_CUSTODY_AUTHORITY
        or not arch150._sparse_custody_authority_is_valid(
            dataset._sparse_custody_authority
        )
    ):
        return False
    authority = dataset._sparse_custody_authority
    return (
        authority.dataset_id == ARCH150_D1R_DATASET_ID
        and authority.dataset_semantic_sha256 == ARCH150_D1R_DATASET_SHA256
        and authority.custody_id == ARCH150_D1R_CUSTODY_ID
        and authority.custody_semantic_sha256 == ARCH150_D1R_CUSTODY_SHA256
        and authority.scheduled_slots_per_symbol
        == ARCH150_D1R_SCHEDULED_SLOTS_PER_SYMBOL
        and authority.observed_counts_by_symbol == ARCH150_D1R_OBSERVED_COUNTS
        and authority.missing_counts_by_symbol == ARCH150_D1R_MISSING_COUNTS
        and authority.common_missing_count == ARCH150_D1R_COMMON_MISSING_COUNT
        and authority.union_missing_count == ARCH150_D1R_UNION_MISSING_COUNT
        and authority.fully_missing_session_counts_by_symbol
        == ARCH150_D1R_FULLY_MISSING_SESSION_COUNTS
    )


def _source_session_projections(
    minutes_by_symbol: tuple[tuple[str, tuple[OneMinuteBar, ...]], ...],
    source_digest: str,
    *,
    accepted_dataset: arch150.ResearchDataset | None,
) -> tuple[_SessionSourceProjection, ...]:
    if accepted_dataset is not None:
        if not _accepted_arch150_dataset_is_valid(accepted_dataset):
            raise AuthorizationUnavailableError(
                "production projections require accepted Arch150 D1R authority"
            )
        if len(minutes_by_symbol) != len(INITIAL_UNIVERSE):
            raise AuthorizationUnavailableError(
                "production projection minutes differ from accepted Arch150 source"
            )
        for symbol, (actual_symbol, actual_minutes) in zip(
            INITIAL_UNIVERSE, minutes_by_symbol, strict=True
        ):
            source_bars = accepted_dataset.bars.by_symbol[symbol].bars
            if (
                actual_symbol != symbol
                or len(actual_minutes) != len(source_bars)
                or any(
                    actual.symbol != source.symbol
                    or actual.timestamp != source.timestamp
                    or actual.open != source.open
                    or actual.high != source.high
                    or actual.low != source.low
                    or actual.close != source.close
                    or actual.volume != source.volume
                    for actual, source in zip(actual_minutes, source_bars, strict=True)
                )
            ):
                raise AuthorizationUnavailableError(
                    "production projection minutes differ from accepted Arch150 source"
                )
    projections: list[_SessionSourceProjection] = []
    for symbol, symbol_minutes in minutes_by_symbol:
        grouped: dict[date, list[OneMinuteBar]] = defaultdict(list)
        for minute in symbol_minutes:
            grouped[minute.session_date].append(minute)
        for session in sorted(grouped):
            minutes = _validated_minutes(grouped[session])
            if any(
                minute.symbol != symbol or minute.session_date != session
                for minute in minutes
            ):
                raise Arch151Error("source projection mixes symbol or session")
            streams: list[AggregateStream] = []
            verified: list[_SparseSessionEvidence] = []
            vwap_values: list[tuple[BarResolution, tuple[VwapObservation, ...]]] = []
            for resolution in BarResolution:
                stream = aggregate_sparse_bars(minutes, resolution)
                if not stream.bars:
                    raise UnavailableIndicatorError(
                        "verified source session contains no complete aggregate bucket"
                    )
                minute_digest = sha256(
                    _canonical_json([_bar_material(bar) for bar in minutes])
                ).hexdigest()
                evidence_digest = _verified_sparse_session_digest(
                    symbol,
                    resolution,
                    session,
                    stream.bars,
                    minute_digest,
                    source_digest,
                )
                if accepted_dataset is not None:
                    session_evidence: _SparseSessionEvidence = VerifiedSparseSession(
                        symbol=symbol,
                        resolution=resolution,
                        session_date=session,
                        bars=stream.bars,
                        history_source_digest=source_digest,
                        source_digest=evidence_digest,
                        minute_source_digest=minute_digest,
                        _seal=_VERIFIED_SPARSE_SESSION_SEAL,
                    )
                else:
                    session_evidence = _SyntheticSparseSessionEvidence(
                        symbol=symbol,
                        resolution=resolution,
                        session_date=session,
                        bars=stream.bars,
                        history_source_digest=source_digest,
                        source_digest=evidence_digest,
                        minute_source_digest=minute_digest,
                        _seal=_SYNTHETIC_SPARSE_SESSION_SEAL,
                    )
                observations = aggregate_session_vwap(
                    minutes, stream, verified_sessions=(session_evidence,)
                )
                streams.append(stream)
                verified.append(session_evidence)
                vwap_values.append((resolution, observations))
            projections.append(
                _SessionSourceProjection(
                    symbol,
                    session,
                    minutes,
                    tuple(streams),
                    tuple(verified),
                    tuple(vwap_values),
                )
            )
    return tuple(projections)


def _adapt_arch150_d1r_snapshot() -> Arch150D1RSourceHistory:
    """Read the fixed Arch150 source and bind it through accepted custody."""

    if not _d1r_semantic_pins_match():
        raise AuthorizationUnavailableError("accepted Arch150 D1R pins drifted")
    snapshot = arch150_d1r._read_pinned_input(arch150_d1r.ACCEPTED_INPUT_ROOT)
    if type(snapshot) is not arch150_d1r.InputSnapshot:
        raise AuthorizationUnavailableError("Arch150 D1R input is not reader-owned")
    expected_artifact_names = tuple(arch150_d1r._ARTIFACT_LENGTHS)
    artifacts = snapshot.artifacts
    expected_normalized_sha256 = {
        f"normalized/{symbol}.csv": digest
        for symbol, digest in arch150._ACCEPTED_NORMALIZED_CSV_SHA256
    }
    if (
        type(artifacts) is not tuple
        or tuple(item.name for item in artifacts) != expected_artifact_names
        or any(
            type(item) is not arch150_d1r.ArtifactCommitment
            or type(item.byte_length) is not int
            or item.byte_length != arch150_d1r._ARTIFACT_LENGTHS[item.name]
            or not _is_sha256(item.sha256)
            or (
                item.name in expected_normalized_sha256
                and item.sha256 != expected_normalized_sha256[item.name]
            )
            for item in artifacts
        )
    ):
        raise AuthorizationUnavailableError(
            "Arch150 D1R artifact commitments are incomplete or reordered"
        )
    # The fixed reader validates each JSON artifact's inner semantic identity
    # against _SEMANTIC_PINS and returns its raw-byte commitment here. For the
    # normalized CSV artifacts, Arch150 also owns the accepted raw-file hashes.
    if type(snapshot.bars) is not tuple or any(
        type(bar) is not arch150.IntradayBar for bar in snapshot.bars
    ):
        raise AuthorizationUnavailableError("Arch150 D1R bars are not normalized")

    # This is Arch150's accepted identity/count/schedule validator. The adapter
    # does not duplicate its custody scan or invoke the G1 strategy evaluator.
    dataset = arch150.open_sparse_discovery_dataset(snapshot.bars)
    if not _accepted_arch150_dataset_is_valid(dataset):
        raise AuthorizationUnavailableError(
            "Arch150 D1R dataset lacks the accepted sparse-custody authority"
        )

    authority = _SESSION_AUTHORITY.published
    source_material = {
        "schema": "arch151-arch150-d1r-source-history/v1",
        "semantic_contract_version": SEMANTIC_CONTRACT_VERSION,
        "arch150_dataset_id": str(ARCH150_D1R_DATASET_ID),
        "arch150_dataset_sha256": ARCH150_D1R_DATASET_SHA256,
        "arch150_custody_id": str(ARCH150_D1R_CUSTODY_ID),
        "arch150_custody_sha256": ARCH150_D1R_CUSTODY_SHA256,
        "arch150_evidence_id": str(ARCH150_D1R_EVIDENCE_ID),
        "arch150_evidence_sha256": ARCH150_D1R_EVIDENCE_SHA256,
        "scheduled_slots_per_symbol": ARCH150_D1R_SCHEDULED_SLOTS_PER_SYMBOL,
        "observed_counts_by_symbol": [
            list(item) for item in ARCH150_D1R_OBSERVED_COUNTS
        ],
        "missing_counts_by_symbol": [list(item) for item in ARCH150_D1R_MISSING_COUNTS],
        "common_missing_count": ARCH150_D1R_COMMON_MISSING_COUNT,
        "union_missing_count": ARCH150_D1R_UNION_MISSING_COUNT,
        "affected_session_count": ARCH150_D1R_AFFECTED_SESSION_COUNT,
        "fully_missing_session_counts_by_symbol": [
            list(item) for item in ARCH150_D1R_FULLY_MISSING_SESSION_COUNTS
        ],
        "artifact_commitments": [
            {"name": item.name, "length": item.byte_length, "sha256": item.sha256}
            for item in artifacts
        ],
        "validated_input_digest": dataset.bars.input_digest,
        "published_xnys_identity": str(authority.identity),
        "published_xnys_digest": authority.digest,
    }
    canonical = _canonical_json(source_material)
    source_digest = sha256(canonical).hexdigest()
    source_id = uuid5(_D1R_HISTORY_NAMESPACE, canonical.decode("utf-8"))
    minutes_by_symbol = tuple(
        (
            symbol,
            tuple(
                OneMinuteBar(
                    symbol,
                    bar.timestamp,
                    bar.open,
                    bar.high,
                    bar.low,
                    bar.close,
                    bar.volume,
                )
                for bar in dataset.bars.by_symbol[symbol].bars
            ),
        )
        for symbol in INITIAL_UNIVERSE
    )
    projections = _source_session_projections(
        minutes_by_symbol, source_digest, accepted_dataset=dataset
    )
    return Arch150D1RSourceHistory(
        source_id=source_id,
        dataset_id=ARCH150_D1R_DATASET_ID,
        dataset_sha256=ARCH150_D1R_DATASET_SHA256,
        custody_id=ARCH150_D1R_CUSTODY_ID,
        custody_sha256=ARCH150_D1R_CUSTODY_SHA256,
        evidence_id=ARCH150_D1R_EVIDENCE_ID,
        evidence_sha256=ARCH150_D1R_EVIDENCE_SHA256,
        artifact_commitments=tuple(
            (item.name, item.byte_length, item.sha256) for item in artifacts
        ),
        source_digest=source_digest,
        session_projections=projections,
        _seal=_D1R_HISTORY_SEAL,
    )


def load_arch150_d1r_source_history() -> Arch150D1RSourceHistory:
    """Load and bind accepted Arch150 D1R history without strategy evaluation.

    This future evaluator entry point uses the existing fixed-root Arch150
    artifact reader and accepted sparse-custody validator. It does not acquire
    data, invoke the Arch150 G1 evaluator, or open holdout/extension history.
    """

    return _adapt_arch150_d1r_snapshot()


def _test_only_synthetic_source_history(
    minute_bars: Iterable[OneMinuteBar],
) -> _SyntheticSourceHistory:
    """Create a separate synthetic source path for foundation tests only."""

    materialized = tuple(minute_bars)
    if not materialized or any(type(item) is not OneMinuteBar for item in materialized):
        raise TypeError("synthetic history requires exact OneMinuteBar values")
    if any(
        not DEVELOPMENT_START <= item.session_date < DEVELOPMENT_END
        for item in materialized
    ):
        raise Arch151Error("synthetic development history cannot include 2024+")
    grouped: dict[str, list[OneMinuteBar]] = {symbol: [] for symbol in INITIAL_UNIVERSE}
    for item in materialized:
        grouped[item.symbol].append(item)
    minutes_by_symbol = tuple(
        (symbol, tuple(sorted(grouped[symbol], key=lambda item: item.timestamp)))
        for symbol in INITIAL_UNIVERSE
        if grouped[symbol]
    )
    canonical = _canonical_json(
        {
            "schema": "arch151-synthetic-source-history/v1",
            "bars": [
                _bar_material(item)
                for symbol, items in minutes_by_symbol
                for item in items
            ],
        }
    )
    source_digest = sha256(canonical).hexdigest()
    projections = _source_session_projections(
        minutes_by_symbol, source_digest, accepted_dataset=None
    )
    return _SyntheticSourceHistory(
        source_digest=source_digest,
        session_projections=projections,
        _seal=_SYNTHETIC_HISTORY_SEAL,
    )


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


class FamilyAMeasureScope(StrEnum):
    CURRENT_OPENING_WINDOW = "CURRENT_OPENING_WINDOW"
    COMPLETE_HISTORICAL_SESSION = "COMPLETE_HISTORICAL_SESSION"


@dataclass(frozen=True, slots=True, init=False)
class FamilyASessionMeasure:
    """Dimensionless first-30-minute return with symbol and completeness proof."""

    symbol: str
    measure_scope: FamilyAMeasureScope
    session_date: date
    session_open: Decimal
    first_30m_close: Decimal
    absolute_return: Decimal
    source_digest: str

    def __init__(
        self,
        symbol: str,
        measure_scope: FamilyAMeasureScope,
        session_date: date,
        session_open: Decimal,
        first_30m_close: Decimal,
        absolute_return: Decimal,
        source_digest: str,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _FAMILY_A_MEASURE_SEAL:
            raise Arch151Error("Family A measures must come from validated bars")
        if symbol not in INITIAL_UNIVERSE:
            raise Arch151Error("Family A measure symbol is outside frozen SPY/QQQ")
        if type(measure_scope) is not FamilyAMeasureScope:
            raise TypeError("Family A measure scope must be a closed enum")
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
            ("symbol", symbol),
            ("measure_scope", measure_scope),
            ("session_date", session_date),
            ("session_open", opening),
            ("first_30m_close", closing),
            ("absolute_return", measured),
            ("source_digest", source_digest),
        ):
            object.__setattr__(self, name, value)


def _family_a_measure_from_exact_session(
    materialized: tuple[OneMinuteBar, ...],
    scope: FamilyAMeasureScope,
) -> FamilyASessionMeasure:
    first = materialized[0]
    first_30m = materialized[:30]
    with localcontext(_DECIMAL_CONTEXT):
        value = abs(first_30m[-1].close / first.open - Decimal(1))
    digest = sha256(
        _canonical_json([_bar_material(bar) for bar in materialized])
    ).hexdigest()
    return FamilyASessionMeasure(
        first.symbol,
        scope,
        first.session_date,
        first.open,
        first_30m[-1].close,
        value,
        digest,
        _seal=_FAMILY_A_MEASURE_SEAL,
    )


def family_a_session_measure(bars: Iterable[OneMinuteBar]) -> FamilyASessionMeasure:
    """Measure only the exact opening 30 minutes available at decision time."""

    materialized = _validated_minutes(bars)
    if len(materialized) != 30:
        raise UnavailableIndicatorError(
            "current Family A measure requires exactly 30 opening minutes"
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
    return _family_a_measure_from_exact_session(
        materialized, FamilyAMeasureScope.CURRENT_OPENING_WINDOW
    )


def family_a_historical_session_measure(
    bars: Iterable[OneMinuteBar],
) -> FamilyASessionMeasure:
    """Measure first-30 return only after an exact full XNYS session is observed."""

    materialized = _validated_minutes(bars)
    first = materialized[0]
    schedule = _SESSION_AUTHORITY.schedule_for(first.session_date)
    assert schedule is not None
    open_utc = schedule.opens_at.astimezone(UTC)
    close_utc = schedule.closes_at.astimezone(UTC)
    session_minutes = int((close_utc - open_utc).total_seconds() // 60)
    expected = tuple(
        open_utc + timedelta(minutes=offset) for offset in range(session_minutes)
    )
    if (
        len(materialized) != session_minutes
        or tuple(bar.timestamp for bar in materialized) != expected
    ):
        raise UnavailableIndicatorError(
            "historical Family A measure requires the complete published session"
        )
    return _family_a_measure_from_exact_session(
        materialized, FamilyAMeasureScope.COMPLETE_HISTORICAL_SESSION
    )


@dataclass(frozen=True, slots=True, init=False)
class FamilyACalibration:
    """Frozen pre-score-year noise and regime statistics for one A program."""

    program_key: ProgramKey
    symbol: str
    scored_year: int
    noise_return: Decimal
    regime_median_return: Decimal
    calibration_session_dates: tuple[date, ...]
    calibration_fingerprint: str
    calibration_id: UUID

    def __init__(
        self,
        program_key: ProgramKey,
        symbol: str,
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
        if symbol not in INITIAL_UNIVERSE:
            raise Arch151Error("Family A calibration symbol is outside frozen SPY/QQQ")
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
            ("symbol", symbol),
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
    if not materialized:
        raise UnavailableIndicatorError("Family A calibration history is empty")
    if any(
        item.measure_scope is not FamilyAMeasureScope.COMPLETE_HISTORICAL_SESSION
        for item in materialized
    ):
        raise Arch151Error(
            "calibration accepts only complete published historical sessions"
        )
    symbols = {item.symbol for item in materialized}
    if len(symbols) != 1:
        raise Arch151Error("Family A calibration history mixes instruments")
    symbol = next(iter(symbols))
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
        "symbol": symbol,
        "scored_year": scored_year,
        "cutoff": cutoff.isoformat(),
        "noise_return": _decimal_text(noise),
        "regime_median_return": _decimal_text(regime),
        "observations": [
            {
                "symbol": item.symbol,
                "measure_scope": item.measure_scope.value,
                "session_date": item.session_date.isoformat(),
                "source_digest": item.source_digest,
            }
            for item in selected
        ],
    }
    canonical = _canonical_json(material)
    return FamilyACalibration(
        program.key,
        symbol,
        scored_year,
        noise,
        regime,
        selected_dates,
        sha256(canonical).hexdigest(),
        uuid5(_CALIBRATION_NAMESPACE, canonical.decode("utf-8")),
        _seal=_FAMILY_A_CALIBRATION_SEAL,
    )


def _source_history_digest(history: object) -> str:
    if type(history) is Arch150D1RSourceHistory:
        if (
            getattr(history, "_seal", None) is not _D1R_HISTORY_SEAL
            or history.dataset_id != ARCH150_D1R_DATASET_ID
            or history.dataset_sha256 != ARCH150_D1R_DATASET_SHA256
            or history.custody_id != ARCH150_D1R_CUSTODY_ID
            or history.custody_sha256 != ARCH150_D1R_CUSTODY_SHA256
            or history.evidence_id != ARCH150_D1R_EVIDENCE_ID
            or history.evidence_sha256 != ARCH150_D1R_EVIDENCE_SHA256
            or not _is_sha256(history.source_digest)
        ):
            raise AuthorizationUnavailableError(
                "Arch150 D1R source-history seal is invalid"
            )
        return history.source_digest
    if type(history) is _SyntheticSourceHistory:
        if getattr(
            history, "_seal", None
        ) is not _SYNTHETIC_HISTORY_SEAL or not _is_sha256(history.source_digest):
            raise AuthorizationUnavailableError(
                "synthetic source-history evidence is invalid"
            )
        return history.source_digest
    raise AuthorizationUnavailableError(
        "feature preparation requires source-owned accepted or synthetic history"
    )


def _bind_family_a_measure_to_source(
    measure: FamilyASessionMeasure, source_identity_digest: str
) -> FamilyASessionMeasure:
    bound_digest = sha256(
        _canonical_json(
            {
                "schema": "arch151-family-a-source-measure/v1",
                "source_identity_digest": source_identity_digest,
                "measure_digest": measure.source_digest,
                "symbol": measure.symbol,
                "scope": measure.measure_scope.value,
                "session_date": measure.session_date.isoformat(),
            }
        )
    ).hexdigest()
    return FamilyASessionMeasure(
        measure.symbol,
        measure.measure_scope,
        measure.session_date,
        measure.session_open,
        measure.first_30m_close,
        measure.absolute_return,
        bound_digest,
        _seal=_FAMILY_A_MEASURE_SEAL,
    )


def _source_calibration_provenance(history: object) -> str:
    if type(history) is Arch150D1RSourceHistory:
        _source_history_digest(history)
        material: object = {
            "schema": "arch151-family-a-source-provenance/v1",
            "dataset_id": str(history.dataset_id),
            "dataset_sha256": history.dataset_sha256,
            "custody_id": str(history.custody_id),
            "custody_sha256": history.custody_sha256,
            "evidence_id": str(history.evidence_id),
            "evidence_sha256": history.evidence_sha256,
        }
    elif type(history) is _SyntheticSourceHistory:
        _source_history_digest(history)
        material = {"schema": "arch151-synthetic-family-a-provenance/v1"}
    else:
        raise AuthorizationUnavailableError(
            "Family A calibration provenance is not source-owned"
        )
    return sha256(_canonical_json(material)).hexdigest()


def _family_a_historical_measures_from_source_history(
    history: Arch150D1RSourceHistory | _SyntheticSourceHistory,
    symbol: str,
    scored_year: int,
) -> tuple[FamilyASessionMeasure, ...]:
    """Return the source-bound complete-session prefix for one symbol/year."""
    _source_history_digest(history)
    provenance_digest = _source_calibration_provenance(history)
    if symbol not in INITIAL_UNIVERSE:
        raise Arch151Error("Family A calibration symbol is outside frozen SPY/QQQ")
    if type(scored_year) is not int or scored_year not in SCORED_YEARS:
        raise ValueError("scored year is outside the five frozen Arch151 years")
    a_parameters = tuple(
        program.parameters
        for program in CANONICAL_PROGRAMS
        if program.family is StrategyFamily.NOISE_VWAP_BREAKOUT
        and type(program.parameters) is NoiseBreakoutParameters
    )
    required_sessions = max(
        max(item.noise_lookback_sessions, item.regime_sessions) for item in a_parameters
    )
    prior_projections = sorted(
        (
            projection
            for projection in history._session_projections
            if projection.symbol == symbol
            and projection.session_date < date(scored_year, 1, 1)
            and projection.aggregate_streams
            and projection.aggregate_streams[0].resolution is BarResolution.FIVE_MINUTE
        ),
        key=lambda item: item.session_date,
        reverse=True,
    )
    reverse_measures: list[FamilyASessionMeasure] = []
    for projection in prior_projections:
        try:
            reverse_measures.append(
                _bind_family_a_measure_to_source(
                    family_a_historical_session_measure(projection.minutes),
                    provenance_digest,
                )
            )
        except UnavailableIndicatorError:
            # Sparse historical sessions are omitted from the complete-session
            # calibration population, never repaired or treated as zero.
            continue
        if len(reverse_measures) == required_sessions:
            break
    return tuple(reversed(reverse_measures))


def calibrate_family_a_from_source_history(
    history: Arch150D1RSourceHistory | _SyntheticSourceHistory,
    program: Arch151Program,
    symbol: str,
    scored_year: int,
) -> FamilyACalibration:
    """Calibrate A from complete source sessions strictly before scored year."""

    if (
        not _is_canonical_program(program)
        or program.family is not StrategyFamily.NOISE_VWAP_BREAKOUT
    ):
        raise UnsupportedProgramError("Family A history needs a canonical A program")
    return calibrate_family_a(
        program,
        _family_a_historical_measures_from_source_history(history, symbol, scored_year),
        scored_year,
    )


def family_a_current_measure_from_source_history(
    history: Arch150D1RSourceHistory | _SyntheticSourceHistory,
    symbol: str,
    session: date,
) -> FamilyASessionMeasure:
    """Prepare only the exact observed first 30 minutes for one scored session."""

    _source_history_digest(history)
    provenance_digest = _source_calibration_provenance(history)
    if symbol not in INITIAL_UNIVERSE:
        raise Arch151Error("Family A current symbol is outside frozen SPY/QQQ")
    if type(session) is not date or session.year not in SCORED_YEARS:
        raise Arch151Error("Family A current measure is outside scored years")
    projection = history._projection_index.get(
        (symbol, session, BarResolution.FIVE_MINUTE)
    )
    if projection is None:
        raise UnavailableIndicatorError("Family A scored-session source is unavailable")
    return _bind_family_a_measure_to_source(
        family_a_session_measure(projection.minutes[:30]), provenance_digest
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
        or type(current_session) is not FamilyASessionMeasure
        or calibration.program_key is not program.key
        or calibration.symbol != current_session.symbol
        or current_session.measure_scope
        is not FamilyAMeasureScope.CURRENT_OPENING_WINDOW
        or current_session.session_date.year != calibration.scored_year
    ):
        raise Arch151Error("Family A calibration/current session binding is invalid")
    limit = calibration.regime_median_return * program.parameters.regime_multiplier
    return current_session.absolute_return <= limit


@dataclass(frozen=True, slots=True)
class FamilyABreakoutLevel:
    program_key: ProgramKey
    symbol: str
    session_date: date
    calibration_id: UUID
    level: Decimal

    def __post_init__(self) -> None:
        if type(self.program_key) is not ProgramKey:
            raise TypeError("Family A breakout program key is invalid")
        if self.symbol not in INITIAL_UNIVERSE:
            raise Arch151Error("Family A breakout symbol is outside frozen SPY/QQQ")
        if type(self.session_date) is not date or type(self.calibration_id) is not UUID:
            raise TypeError("Family A breakout identity is invalid")
        level = _decimal(self.level, "breakout level")
        if level <= 0:
            raise ValueError("Family A breakout level must be positive")
        object.__setattr__(self, "level", level)


def family_a_breakout_level(
    program: Arch151Program,
    calibration: FamilyACalibration,
    current_session: FamilyASessionMeasure,
) -> FamilyABreakoutLevel:
    """Return a symbol-bound frozen noise threshold for the current session."""

    if (
        not _is_canonical_program(program)
        or type(program.parameters) is not NoiseBreakoutParameters
        or type(calibration) is not FamilyACalibration
        or type(current_session) is not FamilyASessionMeasure
        or calibration.program_key is not program.key
        or calibration.symbol != current_session.symbol
        or current_session.measure_scope
        is not FamilyAMeasureScope.CURRENT_OPENING_WINDOW
        or current_session.session_date.year != calibration.scored_year
    ):
        raise Arch151Error(
            "Family A breakout inputs are not bound to a canonical program"
        )
    with localcontext(_DECIMAL_CONTEXT):
        level = current_session.session_open * (
            Decimal(1)
            + program.parameters.breakout_multiplier * calibration.noise_return
        )
    return FamilyABreakoutLevel(
        program.key,
        current_session.symbol,
        current_session.session_date,
        calibration.calibration_id,
        level,
    )


@dataclass(frozen=True, slots=True)
class FamilyAInitialRisk:
    program_key: ProgramKey
    symbol: str
    session_date: date
    calibration_id: UUID
    entry_reference_price: Decimal
    stop_reference_price: Decimal
    risk_distance: Decimal

    def __post_init__(self) -> None:
        if type(self.program_key) is not ProgramKey:
            raise TypeError("Family A risk program key is invalid")
        if self.symbol not in INITIAL_UNIVERSE:
            raise Arch151Error("Family A risk symbol is outside frozen SPY/QQQ")
        if type(self.session_date) is not date or type(self.calibration_id) is not UUID:
            raise TypeError("Family A risk identity is invalid")
        entry = _decimal(self.entry_reference_price, "entry_reference_price")
        stop = _decimal(self.stop_reference_price, "stop_reference_price")
        distance = _decimal(self.risk_distance, "risk_distance")
        if entry <= 0 or stop <= 0 or distance <= 0 or entry - stop != distance:
            raise ValueError("Family A initial risk prices are inconsistent")
        object.__setattr__(self, "entry_reference_price", entry)
        object.__setattr__(self, "stop_reference_price", stop)
        object.__setattr__(self, "risk_distance", distance)


def family_a_initial_risk(
    program: Arch151Program,
    calibration: FamilyACalibration,
    current_session: FamilyASessionMeasure,
    entry_reference_price: Decimal,
) -> FamilyAInitialRisk:
    """Return symbol-bound positive R using entry-price times dimensionless N."""

    if (
        not _is_canonical_program(program)
        or type(program.parameters) is not NoiseBreakoutParameters
        or type(calibration) is not FamilyACalibration
        or type(current_session) is not FamilyASessionMeasure
        or calibration.program_key is not program.key
        or calibration.symbol != current_session.symbol
        or current_session.measure_scope
        is not FamilyAMeasureScope.CURRENT_OPENING_WINDOW
        or current_session.session_date.year != calibration.scored_year
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
    return FamilyAInitialRisk(
        program.key,
        current_session.symbol,
        current_session.session_date,
        calibration.calibration_id,
        entry,
        stop,
        distance,
    )


@dataclass(frozen=True, slots=True)
class NoiseBreakoutSignal:
    program_key: ProgramKey
    symbol: str
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
        or calibration.symbol != current_session.symbol
        or current_session.measure_scope
        is not FamilyAMeasureScope.CURRENT_OPENING_WINDOW
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
    if any(item.bar.symbol != calibration.symbol for item in observations):
        raise Arch151Error(
            "Family A confirmation instrument does not match calibration"
        )
    if current_session.session_open != _decimal(
        current_session.session_open, "session_open"
    ):
        raise Arch151Error("Family A session open is invalid")
    if not family_a_regime_passes(program, calibration, current_session):
        return None
    threshold = family_a_breakout_level(program, calibration, current_session)
    for observation in observations:
        if (
            observation.bar.close <= threshold.level
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
        current_session.symbol,
        current_session.session_date,
        tuple(bar.timestamp for bar in bars),
        threshold.level,
        bars[-1].close,
        calibration.calibration_id,
    )


@dataclass(frozen=True, slots=True)
class OpeningRangeRetestSignal:
    program_key: ProgramKey
    symbol: str
    session_date: date
    signal_timestamp: datetime
    breakout_level: Decimal
    breakout_confirmation_timestamps: tuple[datetime, ...]
    retest_timestamp: datetime
    reclaim_timestamps: tuple[datetime, ...]
    stop_reference_price: Decimal
    target_r: Decimal


def _validated_sparse_session_aggregate_bars(
    session_bars: Sequence[AggregateBar],
    resolution: BarResolution | None = None,
    *,
    require_open: bool = False,
) -> tuple[AggregateBar, ...]:
    materialized = tuple(session_bars)
    if not materialized:
        raise UnavailableIndicatorError("sparse session aggregate input is empty")
    if any(type(bar) is not AggregateBar for bar in materialized):
        raise TypeError("sparse session input must contain AggregateBar values")
    first = materialized[0]
    expected_resolution = resolution or first.resolution
    if type(expected_resolution) is not BarResolution:
        raise TypeError("sparse session resolution must be a BarResolution")
    schedule = _SESSION_AUTHORITY.schedule_for(first.session_date)
    if schedule is None:
        raise Arch151Error("aggregate date is not a published XNYS session")
    open_utc = schedule.opens_at.astimezone(UTC)
    close_utc = schedule.closes_at.astimezone(UTC)
    if require_open and first.timestamp != open_utc:
        raise UnavailableIndicatorError(
            "sparse session input must begin at the published open"
        )
    previous_timestamp: datetime | None = None
    for bar in materialized:
        if (
            bar.symbol != first.symbol
            or bar.session_date != first.session_date
            or bar.resolution is not expected_resolution
        ):
            raise Arch151Error(
                "aggregate stream crosses symbol, resolution, or session"
            )
        if (
            bar.timestamp < open_utc
            or bar.completed_at > close_utc
            or (bar.timestamp - open_utc).total_seconds()
            % (int(expected_resolution) * 60)
            != 0
        ):
            raise Arch151Error("aggregate bar is incomplete or off the published grid")
        if previous_timestamp is not None and bar.timestamp <= previous_timestamp:
            raise Arch151Error("sparse session bars must be strictly chronological")
        previous_timestamp = bar.timestamp
    return materialized


def _validated_family_b_session_bars(
    program: Arch151Program,
    session_bars: Sequence[AggregateBar],
    opening_count: int,
) -> tuple[AggregateBar, ...]:
    materialized = _validated_sparse_session_aggregate_bars(
        session_bars, program.resolution, require_open=True
    )
    first = materialized[0]
    schedule = _SESSION_AUTHORITY.schedule_for(first.session_date)
    assert schedule is not None
    open_utc = schedule.opens_at.astimezone(UTC)

    if len(materialized) < opening_count:
        raise UnavailableIndicatorError("Family B opening range is incomplete")
    expected_opening = tuple(
        open_utc + timedelta(minutes=index * int(program.resolution))
        for index in range(opening_count)
    )
    if tuple(bar.timestamp for bar in materialized[:opening_count]) != expected_opening:
        raise UnavailableIndicatorError(
            "Family B opening range must be complete and session aligned"
        )
    return materialized


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


def _verified_sparse_session_digest(
    symbol: str,
    resolution: BarResolution,
    session: date,
    bars: tuple[AggregateBar, ...],
    minute_source_digest: str | None,
    history_source_digest: str,
) -> str:
    return sha256(
        _canonical_json(
            {
                "schema": "arch151-verified-sparse-session/v2",
                "symbol": symbol,
                "resolution_minutes": int(resolution),
                "session_date": session.isoformat(),
                "bars": [_bar_material(bar) for bar in bars],
                "minute_source_digest": minute_source_digest,
                "history_source_digest": history_source_digest,
            }
        )
    ).hexdigest()


def _sparse_session_evidence_is_valid(value: object) -> bool:
    if type(value) is VerifiedSparseSession:
        return (
            getattr(value, "_seal", None) is _VERIFIED_SPARSE_SESSION_SEAL
            and _is_sha256(value.history_source_digest)
            and _is_sha256(value.source_digest)
        )
    if type(value) is _SyntheticSparseSessionEvidence:
        return (
            getattr(value, "_seal", None) is _SYNTHETIC_SPARSE_SESSION_SEAL
            and _is_sha256(value.history_source_digest)
            and _is_sha256(value.source_digest)
        )
    return False


def _test_only_verified_sparse_session(
    bars: Sequence[AggregateBar],
    *,
    minute_bars: Sequence[OneMinuteBar] | None = None,
) -> _SyntheticSparseSessionEvidence:
    """Private test seam that cannot construct production verification evidence."""

    materialized = tuple(bars)
    if any(type(bar) is not AggregateBar for bar in materialized):
        raise TypeError("synthetic sparse-session input must contain aggregate bars")
    validated = _validated_sparse_session_aggregate_bars(
        materialized, require_open=False
    )
    first = validated[0]
    minute_source_digest: str | None = None
    if minute_bars is not None:
        minutes = _validated_minutes(minute_bars)
        if any(
            bar.symbol != first.symbol or bar.session_date != first.session_date
            for bar in minutes
        ):
            raise Arch151Error("synthetic minute evidence must bind one sparse session")
        recomputed = aggregate_sparse_bars(minutes, first.resolution)
        if recomputed.bars != validated:
            raise Arch151Error("synthetic minute and aggregate evidence do not match")
        minute_source_digest = sha256(
            _canonical_json([_bar_material(bar) for bar in minutes])
        ).hexdigest()
    synthetic_history_digest = sha256(
        _canonical_json(
            {
                "schema": "arch151-synthetic-session-source/v1",
                "symbol": first.symbol,
                "session_date": first.session_date.isoformat(),
                "minute_source_digest": minute_source_digest,
                "aggregate_bars": [_bar_material(bar) for bar in validated],
            }
        )
    ).hexdigest()
    digest = _verified_sparse_session_digest(
        first.symbol,
        first.resolution,
        first.session_date,
        validated,
        minute_source_digest,
        synthetic_history_digest,
    )
    return _SyntheticSparseSessionEvidence(
        symbol=first.symbol,
        resolution=first.resolution,
        session_date=first.session_date,
        bars=validated,
        history_source_digest=synthetic_history_digest,
        source_digest=digest,
        minute_source_digest=minute_source_digest,
        _seal=_SYNTHETIC_SPARSE_SESSION_SEAL,
    )


def _require_verified_sparse_projection(
    evidence: _SparseSessionEvidence | None,
    requested_bars: tuple[AggregateBar, ...],
    program: Arch151Program,
    *,
    allow_prefix: bool,
) -> tuple[AggregateBar, ...]:
    if not _sparse_session_evidence_is_valid(evidence):
        raise AuthorizationUnavailableError(
            "Family C/D require evaluator-owned verified sparse-session evidence"
        )
    if (
        type(evidence.bars) is not tuple
        or not evidence.bars
        or evidence.symbol not in INITIAL_UNIVERSE
        or evidence.symbol != evidence.bars[0].symbol
        or evidence.session_date != evidence.bars[0].session_date
        or evidence.resolution is not program.resolution
        or evidence.minute_source_digest is None
    ):
        raise AuthorizationUnavailableError("sparse-session evidence seal is invalid")
    verified = evidence.bars
    if any(type(bar) is not AggregateBar for bar in requested_bars):
        raise TypeError("sparse-session projection requires AggregateBar values")
    if allow_prefix:
        bound = verified[: len(requested_bars)] == requested_bars
    else:
        starts = tuple(
            index
            for index in range(len(verified))
            if verified[index : index + len(requested_bars)] == requested_bars
        )
        bound = bool(starts)
    if not bound:
        raise AuthorizationUnavailableError(
            "requested bars are not a source-bound sparse-session projection"
        )
    return verified


def family_b_entry_signal(
    program: Arch151Program, session_bars: Sequence[AggregateBar]
) -> OpeningRangeRetestSignal | None:
    """Evaluate a causal retest predicate at the final supplied completed bar."""

    if (
        not _is_canonical_program(program)
        or type(program.parameters) is not OpeningRangeRetestParameters
    ):
        raise UnsupportedProgramError("Family B requires a canonical retest program")
    parameters = program.parameters
    resolution = int(program.resolution)
    if parameters.opening_range_minutes % resolution:
        raise Arch151Error("opening range is not aligned to program resolution")
    opening_count = parameters.opening_range_minutes // resolution
    bars = _validated_family_b_session_bars(program, session_bars, opening_count)
    opening_range = bars[:opening_count]
    level = max(bar.high for bar in opening_range) * (
        Decimal(1) + parameters.breakout_buffer_bps / Decimal(10000)
    )

    lower = level * (Decimal(1) - parameters.retest_tolerance_bps / Decimal(10000))
    upper = level * (Decimal(1) + parameters.retest_tolerance_bps / Decimal(10000))
    resolution_delta = timedelta(minutes=resolution)
    breakout_indexes: list[int] = []
    final_breakout_index: int | None = None
    retest_index: int | None = None
    reclaim_indexes: list[int] = []
    for index in range(opening_count, len(bars)):
        current = bars[index]
        if current.timestamp != bars[index - 1].timestamp + resolution_delta:
            breakout_indexes.clear()
            final_breakout_index = None
            retest_index = None
            reclaim_indexes.clear()

        if (
            final_breakout_index is not None
            and retest_index is None
            and index > final_breakout_index + parameters.retest_deadline_bars
        ):
            breakout_indexes.clear()
            final_breakout_index = None
            reclaim_indexes.clear()

        if final_breakout_index is None:
            if current.close > level:
                breakout_indexes.append(index)
                if len(breakout_indexes) == parameters.breakout_confirmation_bars:
                    final_breakout_index = index
            else:
                breakout_indexes.clear()
            continue

        if retest_index is None:
            if current.low < lower:
                breakout_indexes.clear()
                final_breakout_index = None
                reclaim_indexes.clear()
                continue
            if lower <= current.low <= upper:
                retest_index = index
            continue

        if current.close <= level:
            breakout_indexes.clear()
            final_breakout_index = None
            retest_index = None
            reclaim_indexes.clear()
            continue
        reclaim_indexes.append(index)
        if len(reclaim_indexes) != parameters.reclaim_confirmation_bars:
            continue
        final_bar = bars[index]
        if index != len(bars) - 1 or not program.entry_window.contains(
            final_bar.completed_at
        ):
            breakout_indexes.clear()
            final_breakout_index = None
            retest_index = None
            reclaim_indexes.clear()
            continue
        assert retest_index is not None
        swing_low = min(bar.low for bar in bars[retest_index : index + 1])
        stop = swing_low * (Decimal(1) - parameters.stop_buffer_bps / Decimal(10000))
        return OpeningRangeRetestSignal(
            program.key,
            final_bar.symbol,
            final_bar.session_date,
            final_bar.completed_at,
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
    program_id: UUID
    symbol: str
    resolution: BarResolution
    session_date: date
    signal_timestamp: datetime
    normalized_deviation: Decimal
    frozen_entry_sigma: Decimal
    efficiency_ratio: Decimal


def family_c_entry_signal(
    program: Arch151Program,
    preceding: Sequence[VwapObservation],
    signal: VwapObservation,
    *,
    verified_session: _SparseSessionEvidence | None = None,
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
    if signal.bar.symbol not in INITIAL_UNIVERSE:
        raise Arch151Error("Family C signal symbol is outside frozen SPY/QQQ")
    _require_verified_sparse_projection(
        verified_session,
        tuple(item.bar for item in (*history, signal)),
        program,
        allow_prefix=False,
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
        program.key,
        program_id(program),
        signal.bar.symbol,
        signal.bar.resolution,
        signal.bar.session_date,
        signal.bar.timestamp,
        deviation,
        sigma,
        er,
    )


def family_c_reversion_exit(
    program: Arch151Program,
    signal: VwapMeanReversionSignal,
    current: VwapObservation,
    *,
    verified_session: _SparseSessionEvidence | None = None,
) -> bool:
    """Check the VWAP exit against current VWAP and frozen entry sigma."""

    if (
        not _is_canonical_program(program)
        or type(program.parameters) is not VwapMeanReversionParameters
        or type(signal) is not VwapMeanReversionSignal
        or signal.program_key is not program.key
        or signal.program_id != program_id(program)
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
    sigma = _decimal(signal.frozen_entry_sigma, "frozen entry sigma")
    if sigma <= 0:
        raise Arch151Error("Family C frozen entry sigma must be positive and finite")
    if (
        signal.symbol not in INITIAL_UNIVERSE
        or signal.resolution is not program.resolution
        or signal.session_date != signal_session
        or current.bar.symbol != signal.symbol
        or current.bar.resolution is not signal.resolution
    ):
        raise Arch151Error("Family C exit instrument or resolution differs from entry")
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
    _require_verified_sparse_projection(
        verified_session,
        (current_bar,),
        program,
        allow_prefix=False,
    )
    with localcontext(_DECIMAL_CONTEXT):
        threshold = current.vwap * (
            Decimal(1) + program.parameters.exit_sigma_multiplier * sigma
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


def ema_series(
    bars: Sequence[AggregateBar],
    period: int,
    *,
    verified_session: _SparseSessionEvidence | None = None,
) -> tuple[Decimal | None, ...]:
    """Compute session-local EMA, reseeding after each sparse gap."""

    if type(period) is not int or period < 1:
        raise ValueError("EMA period must be positive")
    materialized = _validated_sparse_session_aggregate_bars(
        bars, require_open=verified_session is None
    )
    if verified_session is not None:
        if not _sparse_session_evidence_is_valid(verified_session):
            raise AuthorizationUnavailableError(
                "EMA recovery after a missing open requires verified session evidence"
            )
        if (
            type(verified_session.bars) is not tuple
            or not verified_session.bars
            or verified_session.symbol != materialized[0].symbol
            or verified_session.session_date != materialized[0].session_date
            or verified_session.resolution is not materialized[0].resolution
            or verified_session.minute_source_digest is None
            or verified_session.bars[: len(materialized)] != materialized
        ):
            raise AuthorizationUnavailableError(
                "EMA bars are not a source-bound sparse-session prefix"
            )
    values: list[Decimal | None] = [None] * len(materialized)
    segment_start = 0
    current: Decimal | None = None
    with localcontext(_DECIMAL_CONTEXT):
        alpha = Decimal(2) / Decimal(period + 1)
        for index, item in enumerate(materialized):
            if index > 0 and item.timestamp != materialized[
                index - 1
            ].timestamp + timedelta(minutes=int(item.resolution)):
                segment_start = index
                current = None
            contiguous_count = index - segment_start + 1
            if contiguous_count < period:
                continue
            if contiguous_count == period:
                current = sum(
                    (bar.close for bar in materialized[segment_start : index + 1]),
                    Decimal(0),
                ) / Decimal(period)
            else:
                assert current is not None
                current = alpha * item.close + (Decimal(1) - alpha) * current
            values[index] = current
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


def prepare_session_features(
    history: Arch150D1RSourceHistory | _SyntheticSourceHistory,
    program: Arch151Program,
    symbol: str,
    session: date,
    cutoff_completed_at: datetime,
) -> PreparedSessionFeatures:
    """Return an immutable feature prefix through one completed decision cutoff.

    The accepted source reader computes the full history identity and each
    source-session projection once. This function selects that projection and
    never hashes or returns later session observations.
    """

    source_digest = _source_history_digest(history)
    if not _is_canonical_program(program):
        raise UnsupportedProgramError(
            "feature preparation requires a canonical program"
        )
    if symbol not in INITIAL_UNIVERSE:
        raise Arch151Error("feature preparation symbol is outside frozen SPY/QQQ")
    if type(session) is not date or not DEVELOPMENT_START <= session < DEVELOPMENT_END:
        raise Arch151Error("feature preparation session is outside 2016-2023")
    if (
        type(cutoff_completed_at) is not datetime
        or cutoff_completed_at.tzinfo is None
        or cutoff_completed_at.utcoffset() is None
    ):
        raise TypeError("feature cutoff must be timezone aware")
    cutoff = cutoff_completed_at.astimezone(UTC)
    schedule = _SESSION_AUTHORITY.schedule_for(session)
    if schedule is None:
        raise Arch151Error("feature session is not published by XNYS")
    open_utc = schedule.opens_at.astimezone(UTC)
    close_utc = schedule.closes_at.astimezone(UTC)
    span_seconds = int(program.resolution) * 60
    elapsed_seconds = (cutoff - open_utc).total_seconds()
    if (
        elapsed_seconds < span_seconds
        or cutoff > close_utc
        or elapsed_seconds % span_seconds != 0
    ):
        raise UnavailableIndicatorError(
            "feature cutoff must be a scheduled completed aggregate boundary"
        )
    projection = history._projection_index.get((symbol, session, program.resolution))
    if projection is None:
        raise UnavailableIndicatorError("source session projection is unavailable")
    stream = next(
        item
        for item in projection.aggregate_streams
        if item.resolution is program.resolution
    )
    all_vwaps = dict(projection.vwap_by_resolution)[program.resolution]
    evidence = next(
        item
        for item in projection.verified_sessions
        if item.resolution is program.resolution
    )
    bars = tuple(bar for bar in stream.bars if bar.completed_at <= cutoff)
    vwap_observations = tuple(
        observation
        for observation in all_vwaps
        if observation.bar.completed_at <= cutoff
    )
    if tuple(item.bar for item in vwap_observations) != bars:
        raise Arch151Error("prepared VWAP and aggregate prefixes do not match")

    cache_key = SessionFeatureCacheKey(
        source_digest,
        symbol,
        program.resolution,
        session,
        program_id(program),
        program_fingerprint(program),
        cutoff,
    )
    decision_bar = bars[-1] if bars and bars[-1].completed_at == cutoff else None
    decision_vwap = (
        vwap_observations[-1]
        if decision_bar is not None
        and vwap_observations
        and vwap_observations[-1].bar == decision_bar
        else None
    )

    fast_values: tuple[Decimal | None, ...] = ()
    slow_values: tuple[Decimal | None, ...] = ()
    if program.family is StrategyFamily.CROSS_ETF_TREND_PULLBACK and bars:
        parameters = program.parameters
        assert type(parameters) is CrossEtfPullbackParameters
        fast_values = ema_series(bars, parameters.ema_fast, verified_session=evidence)
        slow_values = ema_series(bars, parameters.ema_slow, verified_session=evidence)

    points: list[CausalIndicatorPoint] = []
    vwap_by_timestamp = {item.bar.timestamp: item for item in vwap_observations}
    for index, bar in enumerate(bars):
        observation = vwap_by_timestamp[bar.timestamp]
        deviation = normalized_vwap_deviation(bar.close, observation.vwap)
        sigma: Decimal | None = None
        efficiency: Decimal | None = None
        ema_fast = fast_values[index] if fast_values else None
        ema_slow = slow_values[index] if slow_values else None
        preceding_atr: Decimal | None = None

        if program.family is StrategyFamily.VWAP_MEAN_REVERSION:
            parameters = program.parameters
            assert type(parameters) is VwapMeanReversionParameters
            deviation_count = parameters.deviation_lookback_bars
            if index >= deviation_count:
                prior = vwap_observations[index - deviation_count : index]
                try:
                    contiguous_aggregate_bars(
                        tuple(item.bar for item in (*prior, observation))
                    )
                    sigma, deviation = vwap_deviation_sigma(
                        tuple((item.bar.close, item.vwap) for item in prior),
                        bar.close,
                        observation.vwap,
                        lookback=deviation_count,
                    )
                except UnavailableIndicatorError:
                    sigma = None
            er_count = parameters.efficiency_ratio_lookback
            if index >= er_count:
                er_bars = bars[index - er_count : index + 1]
                try:
                    contiguous_aggregate_bars(er_bars)
                    efficiency = efficiency_ratio(
                        tuple(item.close for item in er_bars), er_count
                    )
                except UnavailableIndicatorError:
                    efficiency = None

        if program.family is StrategyFamily.CROSS_ETF_TREND_PULLBACK:
            parameters = program.parameters
            assert type(parameters) is CrossEtfPullbackParameters
            prior_count = parameters.atr_lookback + 1
            if index >= prior_count:
                try:
                    preceding_atr = average_true_range(
                        bars[index - prior_count : index], parameters.atr_lookback
                    )
                except UnavailableIndicatorError:
                    preceding_atr = None
        points.append(
            CausalIndicatorPoint(
                bar,
                observation.vwap,
                deviation,
                sigma,
                efficiency,
                ema_fast,
                ema_slow,
                preceding_atr,
            )
        )

    opening_range_high: Decimal | None = None
    if program.family is StrategyFamily.OPENING_RANGE_RETEST:
        parameters = program.parameters
        assert type(parameters) is OpeningRangeRetestParameters
        opening_count = parameters.opening_range_minutes // int(program.resolution)
        if len(bars) >= opening_count and bars[0].timestamp == open_utc:
            expected = tuple(
                open_utc + timedelta(minutes=index * int(program.resolution))
                for index in range(opening_count)
            )
            if tuple(item.timestamp for item in bars[:opening_count]) == expected:
                opening_range_high = max(item.high for item in bars[:opening_count])

    family_a_measure: FamilyASessionMeasure | None = None
    if (
        program.family is StrategyFamily.NOISE_VWAP_BREAKOUT
        and cutoff >= open_utc + timedelta(minutes=30)
        and len(projection.minutes) >= 30
    ):
        try:
            family_a_measure = _bind_family_a_measure_to_source(
                family_a_session_measure(projection.minutes[:30]),
                _source_calibration_provenance(history),
            )
        except UnavailableIndicatorError:
            pass

    return PreparedSessionFeatures(
        cache_key,
        bars,
        vwap_observations,
        tuple(points),
        decision_bar,
        decision_vwap,
        opening_range_high,
        family_a_measure,
    )


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
class PreparedCrossEtfFeatures:
    target: PreparedSessionFeatures
    confirming: PreparedSessionFeatures
    aligned_bars: tuple[AlignedCrossEtfBars, ...]
    decision_aligned: bool


def prepare_cross_etf_session_features(
    history: Arch150D1RSourceHistory | _SyntheticSourceHistory,
    program: Arch151Program,
    target_symbol: str,
    session: date,
    cutoff_completed_at: datetime,
) -> PreparedCrossEtfFeatures:
    """Prepare both source-bound symbol prefixes at the same causal cutoff."""

    if (
        not _is_canonical_program(program)
        or program.family is not StrategyFamily.CROSS_ETF_TREND_PULLBACK
    ):
        raise UnsupportedProgramError("cross-ETF preparation requires Family D")
    if target_symbol not in INITIAL_UNIVERSE:
        raise Arch151Error("target symbol is outside frozen SPY/QQQ")
    confirming_symbol = next(item for item in INITIAL_UNIVERSE if item != target_symbol)
    target = prepare_session_features(
        history, program, target_symbol, session, cutoff_completed_at
    )
    confirming = prepare_session_features(
        history, program, confirming_symbol, session, cutoff_completed_at
    )
    confirming_by_timestamp = {bar.timestamp: bar for bar in confirming.bars}
    pairs = tuple(
        AlignedCrossEtfBars(bar.timestamp, bar, confirming_by_timestamp[bar.timestamp])
        for bar in target.bars
        if bar.timestamp in confirming_by_timestamp
    )
    segment_start = len(pairs)
    if pairs:
        segment_start = len(pairs) - 1
        while segment_start > 0 and pairs[segment_start].timestamp == pairs[
            segment_start - 1
        ].timestamp + timedelta(minutes=int(program.resolution)):
            segment_start -= 1
    aligned = pairs[segment_start:]
    decision_aligned = (
        target.decision_bar is not None
        and confirming.decision_bar is not None
        and target.decision_bar.completed_at == cutoff_completed_at.astimezone(UTC)
        and confirming.decision_bar.completed_at == cutoff_completed_at.astimezone(UTC)
        and target.decision_bar.timestamp == confirming.decision_bar.timestamp
    )
    return PreparedCrossEtfFeatures(target, confirming, aligned, decision_aligned)


@dataclass(frozen=True, slots=True)
class TrendPullbackSignal:
    program_key: ProgramKey
    program_id: UUID
    symbol: str
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


def _family_d_same_bar_tie_key(
    signal: TrendPullbackSignal,
) -> tuple[datetime, Decimal, Decimal, Decimal]:
    return (
        signal.setup_timestamp,
        -signal.swing_peak,
        signal.pullback_low,
        signal.stop_reference_price,
    )


def _family_d_contiguous_segment_signal(
    program: Arch151Program,
    local: tuple[AggregateBar, ...],
    other: tuple[AggregateBar, ...],
    other_vwaps: tuple[Decimal, ...],
    local_fast: tuple[Decimal | None, ...],
    local_slow: tuple[Decimal | None, ...],
    other_fast: tuple[Decimal | None, ...],
    other_slow: tuple[Decimal | None, ...],
) -> TrendPullbackSignal | None:
    """Evaluate one gap-free, exactly aligned local/cross-ETF segment."""

    parameters = program.parameters
    assert type(parameters) is CrossEtfPullbackParameters
    aligned = exact_cross_etf_confirmation(local, other, len(local))
    if not (
        len(local_fast)
        == len(local_slow)
        == len(other_fast)
        == len(other_slow)
        == len(local)
    ):
        raise UnavailableIndicatorError("cross-ETF EMA values are incomplete")

    minimum_index = max(
        parameters.ema_slow + 2,
        parameters.atr_lookback + 1,
        parameters.swing_peak_window_bars,
    )
    candidates: list[TrendPullbackSignal] = []
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
        for index in range(setup_index + 1, deadline_end + 1):
            pullback_low = min(pullback_low, local[index].low)
            with localcontext(_DECIMAL_CONTEXT):
                depth_atr = (swing_peak - pullback_low) / frozen_atr
            if depth_atr > parameters.pullback_max_atr:
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
                and other[cross_start + offset].close
                > other_vwaps[cross_start + offset]
                and other_fast[cross_start + offset] > other_slow[cross_start + offset]
                for offset in range(cross_count)
            )
            if not local_trend or not cross_trend:
                break
            signal_bar = local[index]
            if index != len(local) - 1 or not program.entry_window.contains(
                signal_bar.completed_at
            ):
                break
            stop = pullback_low - parameters.stop_buffer_atr * frozen_atr
            if stop <= 0 or signal_bar.close <= stop:
                break
            candidates.append(
                TrendPullbackSignal(
                    program.key,
                    program_id(program),
                    local[0].symbol,
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
            )
            break
    if not candidates:
        return None
    return min(candidates, key=_family_d_same_bar_tie_key)


def family_d_entry_signal(
    program: Arch151Program,
    target_bars: Sequence[AggregateBar],
    confirming_bars: Sequence[AggregateBar],
    confirming_vwaps: Sequence[VwapObservation],
    *,
    target_session: _SparseSessionEvidence | None = None,
    confirming_session: _SparseSessionEvidence | None = None,
) -> TrendPullbackSignal | None:
    """Evaluate only a qualifying reclaim on the current completed decision bar.

    A missing bucket resets both the local setup state and the cross-ETF
    confirmation segment. EMA and ATR warmup must be re-established within a
    fresh contiguous segment; no stale cross-symbol value is substituted.
    Multiple setups completing on the same bar are resolved by earliest setup
    timestamp, then highest swing peak, then lowest pullback low, then lowest
    stop reference. This predicate does not consume entries or synthesize fills.
    """

    if (
        not _is_canonical_program(program)
        or type(program.parameters) is not CrossEtfPullbackParameters
    ):
        raise UnsupportedProgramError("Family D requires a canonical pullback program")
    local = _validated_sparse_session_aggregate_bars(
        target_bars, program.resolution, require_open=False
    )
    other = _validated_sparse_session_aggregate_bars(
        confirming_bars, program.resolution, require_open=False
    )
    _require_verified_sparse_projection(
        target_session, local, program, allow_prefix=True
    )
    _require_verified_sparse_projection(
        confirming_session, other, program, allow_prefix=True
    )
    if local[0].symbol == other[0].symbol:
        raise Arch151Error("cross-ETF confirmation requires distinct symbols")
    if (
        local[0].symbol not in INITIAL_UNIVERSE
        or other[0].symbol not in INITIAL_UNIVERSE
    ):
        raise Arch151Error("cross-ETF symbols are limited to SPY and QQQ")
    if local[0].session_date != other[0].session_date:
        raise Arch151Error("cross-ETF streams must belong to the same session")
    vwap_observations = tuple(confirming_vwaps)
    if len(vwap_observations) != len(other) or any(
        type(observation) is not VwapObservation for observation in vwap_observations
    ):
        raise UnavailableIndicatorError("cross-ETF VWAP observations are incomplete")
    if any(
        observation.bar != bar
        for observation, bar in zip(vwap_observations, other, strict=True)
    ):
        raise UnavailableIndicatorError(
            "cross-ETF VWAP observations are not exactly bar aligned"
        )

    local_fast_all = ema_series(
        local, program.parameters.ema_fast, verified_session=target_session
    )
    local_slow_all = ema_series(
        local, program.parameters.ema_slow, verified_session=target_session
    )
    other_fast_all = ema_series(
        other, program.parameters.ema_fast, verified_session=confirming_session
    )
    other_slow_all = ema_series(
        other, program.parameters.ema_slow, verified_session=confirming_session
    )

    other_indexes = {bar.timestamp: index for index, bar in enumerate(other)}
    vwap_by_timestamp = {
        observation.bar.timestamp: observation.vwap for observation in vwap_observations
    }
    pairs = tuple(
        (local_index, other_indexes[bar.timestamp])
        for local_index, bar in enumerate(local)
        if bar.timestamp in other_indexes
    )
    if not pairs:
        raise UnavailableIndicatorError("cross-ETF streams have no exact overlap")
    if pairs[-1] != (len(local) - 1, len(other) - 1):
        return None

    segments: list[list[tuple[int, int]]] = []
    current_segment: list[tuple[int, int]] = []
    resolution_delta = timedelta(minutes=int(program.resolution))
    for pair in pairs:
        local_index, other_index = pair
        if current_segment:
            previous_local, previous_other = current_segment[-1]
            contiguous = (
                local_index == previous_local + 1
                and other_index == previous_other + 1
                and local[local_index].timestamp
                == local[previous_local].timestamp + resolution_delta
                and other[other_index].timestamp
                == other[previous_other].timestamp + resolution_delta
            )
            if not contiguous:
                segments.append(current_segment)
                current_segment = []
        current_segment.append(pair)
    if current_segment:
        segments.append(current_segment)

    final_segment = segments[-1]
    local_segment = tuple(local[left] for left, _ in final_segment)
    other_segment = tuple(other[right] for _, right in final_segment)
    segment_vwaps = tuple(vwap_by_timestamp[bar.timestamp] for bar in other_segment)
    segment_local_fast = tuple(local_fast_all[left] for left, _ in final_segment)
    segment_local_slow = tuple(local_slow_all[left] for left, _ in final_segment)
    segment_other_fast = tuple(other_fast_all[right] for _, right in final_segment)
    segment_other_slow = tuple(other_slow_all[right] for _, right in final_segment)
    signal = _family_d_contiguous_segment_signal(
        program,
        local_segment,
        other_segment,
        segment_vwaps,
        segment_local_fast,
        segment_local_slow,
        segment_other_fast,
        segment_other_slow,
    )
    if signal is None or signal.signal_timestamp != local[-1].timestamp:
        return None
    if signal.signal_timestamp != other[-1].timestamp:
        return None
    return signal


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


class ProfitFactorState(StrEnum):
    FINITE = "FINITE"
    POSITIVE_INFINITY = "POSITIVE_INFINITY"
    UNDEFINED = "UNDEFINED"
    INVALID = "INVALID"


@dataclass(frozen=True, slots=True)
class ProfitFactor:
    """Explicit finite, positive-infinity, or undefined PF evidence."""

    state: ProfitFactorState
    finite_value: Decimal | None

    def __post_init__(self) -> None:
        if type(self.state) is not ProfitFactorState:
            raise TypeError("profit-factor state must be a closed enum")
        if self.state is ProfitFactorState.INVALID:
            raise Arch151Error("invalid profit-factor evidence is rejected")
        if self.state is ProfitFactorState.FINITE:
            if type(self.finite_value) is not Decimal:
                raise TypeError("finite profit factor requires a Decimal value")
            value = _decimal(self.finite_value, "finite profit factor")
            if value < 0:
                raise ValueError("finite profit factor cannot be negative")
            object.__setattr__(self, "finite_value", value)
        elif self.finite_value is not None:
            raise Arch151Error(
                "infinite and undefined profit factors cannot have numeric sentinels"
            )

    @classmethod
    def from_totals(
        cls, positive_total: Decimal, negative_total: Decimal
    ) -> ProfitFactor:
        if type(positive_total) is not Decimal or type(negative_total) is not Decimal:
            raise TypeError("trade P&L totals must be Decimal values")
        positive = _decimal(positive_total, "positive trade P&L")
        negative = _decimal(negative_total, "negative trade P&L")
        if positive < 0 or negative < 0:
            raise Arch151Error("invalid trade P&L evidence cannot produce a PF metric")
        if positive == 0 and negative == 0:
            return cls(ProfitFactorState.UNDEFINED, None)
        if positive > 0 and negative == 0:
            return cls(ProfitFactorState.POSITIVE_INFINITY, None)
        with localcontext(_DECIMAL_CONTEXT):
            return cls(ProfitFactorState.FINITE, positive / negative)

    @classmethod
    def finite(cls, value: Decimal) -> ProfitFactor:
        return cls(ProfitFactorState.FINITE, value)

    @property
    def exceeds_one(self) -> bool:
        return self.state is ProfitFactorState.POSITIVE_INFINITY or (
            self.state is ProfitFactorState.FINITE
            and self.finite_value is not None
            and self.finite_value > 1
        )

    @property
    def ranking_key(self) -> tuple[int, Decimal]:
        if self.state is ProfitFactorState.POSITIVE_INFINITY:
            return (0, Decimal(0))
        if self.state is ProfitFactorState.FINITE:
            assert self.finite_value is not None
            return (1, -self.finite_value)
        return (2, Decimal(0))

    def canonical_material(self) -> dict[str, str | None]:
        return {
            "state": self.state.value,
            "value": (
                _decimal_text(self.finite_value)
                if self.finite_value is not None
                else None
            ),
        }

    def arch150_report_value(self) -> str | None:
        if self.state is ProfitFactorState.POSITIVE_INFINITY:
            return "Infinity"
        if self.state is ProfitFactorState.UNDEFINED:
            return None
        assert self.finite_value is not None
        return _decimal_text(self.finite_value)


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
    net_positive_trade_pnl: Decimal
    net_negative_trade_pnl: Decimal
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
            or type(self.net_positive_trade_pnl) is not Decimal
            or type(self.net_negative_trade_pnl) is not Decimal
            or type(self.annual_turnover) is not Decimal
        ):
            raise TypeError("fold P&L and turnover inputs must be Decimal values")
        gross_positive = _decimal(
            self.gross_positive_trade_pnl, "gross positive trade P&L"
        )
        gross_negative = _decimal(
            self.gross_negative_trade_pnl, "gross negative trade P&L"
        )
        net_positive = _decimal(self.net_positive_trade_pnl, "net positive trade P&L")
        net_negative = _decimal(self.net_negative_trade_pnl, "net negative trade P&L")
        annual_turnover = _decimal(self.annual_turnover, "annual turnover")
        if min(gross_positive, gross_negative, net_positive, net_negative) < 0:
            raise Arch151Error("invalid gross or realized net trade P&L evidence")
        if annual_turnover < 0:
            raise ValueError("annual turnover cannot be negative")
        if not any(round_trips) and (
            gross_positive != 0
            or gross_negative != 0
            or net_positive != 0
            or net_negative != 0
            or any(normalized_returns)
            or annual_turnover != 0
        ):
            raise Arch151Error(
                "zero-trade fold requires zero returns, gross/net economics, "
                "and turnover"
            )
        object.__setattr__(self, "session_net_returns", normalized_returns)
        object.__setattr__(self, "session_dates", session_dates)
        object.__setattr__(self, "round_trips_by_session", round_trips)
        object.__setattr__(self, "gross_positive_trade_pnl", gross_positive)
        object.__setattr__(self, "gross_negative_trade_pnl", gross_negative)
        object.__setattr__(self, "net_positive_trade_pnl", net_positive)
        object.__setattr__(self, "net_negative_trade_pnl", net_negative)
        object.__setattr__(self, "annual_turnover", annual_turnover)

    @property
    def net_return(self) -> Decimal:
        with localcontext(_DECIMAL_CONTEXT):
            equity = Decimal(1)
            for value in self.session_net_returns:
                equity *= Decimal(1) + value
            return equity - Decimal(1)

    @property
    def profit_factor(self) -> ProfitFactor:
        return ProfitFactor.from_totals(
            self.net_positive_trade_pnl, self.net_negative_trade_pnl
        )

    @property
    def pre_cost_profit_factor(self) -> ProfitFactor:
        return ProfitFactor.from_totals(
            self.gross_positive_trade_pnl, self.gross_negative_trade_pnl
        )

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
        "net_positive_trade_pnl": _decimal_text(metrics.net_positive_trade_pnl),
        "net_negative_trade_pnl": _decimal_text(metrics.net_negative_trade_pnl),
        "profit_factor": metrics.profit_factor.canonical_material(),
        "pre_cost_profit_factor": metrics.pre_cost_profit_factor.canonical_material(),
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
            "schema": _FOLD_EVALUATION_SCHEMA,
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
    """Complete, internally consistent folds under BASE, STRESS and ZERO.

    Integrity-invalid records are rejected before economic qualification can
    classify a candidate. Real replay-integrity failure evidence is evaluator-
    owned and is not issued by this foundation.
    """

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
    profit_factor: ProfitFactor | Decimal
    pre_cost_profit_factor: ProfitFactor | Decimal
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
        if type(self.profit_factor) is Decimal:
            object.__setattr__(
                self, "profit_factor", ProfitFactor.finite(self.profit_factor)
            )
        elif type(self.profit_factor) is not ProfitFactor:
            raise TypeError("development profit factor must have an explicit state")
        if type(self.pre_cost_profit_factor) is Decimal:
            object.__setattr__(
                self,
                "pre_cost_profit_factor",
                ProfitFactor.finite(self.pre_cost_profit_factor),
            )
        elif type(self.pre_cost_profit_factor) is not ProfitFactor:
            raise TypeError(
                "development pre-cost profit factor must have an explicit state"
            )
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
    SELECTION_BIAS_PROBABILITY_BELOW_THRESHOLD = (
        "SELECTION_BIAS_PROBABILITY_BELOW_THRESHOLD"
    )


class SelectionBiasStatus(StrEnum):
    DSR_COMPUTATION_REQUIRED = "DSR_COMPUTATION_REQUIRED"
    DSR_VERIFIED = "DSR_VERIFIED"
    STATISTICAL_EVIDENCE_UNAVAILABLE = "STATISTICAL_EVIDENCE_UNAVAILABLE"


class DsrTrialStatus(StrEnum):
    SHARPE_AVAILABLE = "SHARPE_AVAILABLE"
    SHARPE_UNAVAILABLE = "SHARPE_UNAVAILABLE"


class DsrUnavailableReason(StrEnum):
    UNDEFINED_TRIAL_SHARPE = "UNDEFINED_TRIAL_SHARPE"
    ZERO_TRIAL_SHARPE_VARIANCE = "ZERO_TRIAL_SHARPE_VARIANCE"
    INVALID_CANDIDATE_MOMENTS = "INVALID_CANDIDATE_MOMENTS"
    DEGENERATE_DSR_VARIANCE = "DEGENERATE_DSR_VARIANCE"


@dataclass(frozen=True, slots=True)
class DsrTrialDiagnostic:
    """Candidate-level DSR input status retained for every canonical slot."""

    candidate_slot_id: UUID
    status: DsrTrialStatus
    daily_sharpe: Decimal | None
    unavailable_reason: DsrUnavailableReason | None

    def __post_init__(self) -> None:
        if type(self.candidate_slot_id) is not UUID:
            raise TypeError("DSR diagnostic requires a canonical slot UUID")
        if type(self.status) is not DsrTrialStatus:
            raise TypeError("DSR trial status must be a closed enum")
        if (
            self.unavailable_reason is not None
            and type(self.unavailable_reason) is not DsrUnavailableReason
        ):
            raise TypeError("DSR trial reason must be a closed enum")
        if self.status is DsrTrialStatus.SHARPE_AVAILABLE:
            if (
                type(self.daily_sharpe) is not Decimal
                or not self.daily_sharpe.is_finite()
                or self.unavailable_reason
                is DsrUnavailableReason.UNDEFINED_TRIAL_SHARPE
            ):
                raise Arch151Error(
                    "available Sharpe diagnostic requires a finite value"
                )
        else:
            if not isinstance(self.unavailable_reason, DsrUnavailableReason):
                raise Arch151Error("unavailable DSR diagnostic requires a reason")
            if self.daily_sharpe is not None:
                raise Arch151Error("unavailable Sharpe diagnostic cannot carry a value")

    def canonical_material(self) -> dict[str, str | None]:
        return {
            "candidate_slot_id": str(self.candidate_slot_id),
            "status": self.status.value,
            "daily_sharpe": (
                _decimal_text(self.daily_sharpe)
                if self.daily_sharpe is not None
                else None
            ),
            "unavailable_reason": (
                self.unavailable_reason.value
                if self.unavailable_reason is not None
                else None
            ),
        }


def _qualification_rejections(
    aggregate: DevelopmentAggregate,
) -> tuple[QualificationRejection, ...]:
    rejected: list[QualificationRejection] = []
    if aggregate.net_return <= 0:
        rejected.append(QualificationRejection.STRESS_NET_RETURN_NOT_POSITIVE)
    if not aggregate.profit_factor.exceeds_one:
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
        net_positive = sum(
            (record.metrics.net_positive_trade_pnl for record in records), Decimal(0)
        )
        net_negative = sum(
            (record.metrics.net_negative_trade_pnl for record in records), Decimal(0)
        )
        gross_positive = sum(
            (record.metrics.gross_positive_trade_pnl for record in records), Decimal(0)
        )
        gross_negative = sum(
            (record.metrics.gross_negative_trade_pnl for record in records), Decimal(0)
        )
        profit_factor = ProfitFactor.from_totals(net_positive, net_negative)
        pre_cost_profit_factor = ProfitFactor.from_totals(
            gross_positive, gross_negative
        )
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
        pre_cost_profit_factor,
        sum(value > 0 for value in annual_returns),
        sum(value.exceeds_one for value in annual_profit_factors),
        min(annual_returns),
        max_drawdown,
        average_round_trips,
        active_fraction,
        median_active,
        sharpe,
        turnover,
    )


def qualify_development(
    batch: DevelopmentEvaluationBatch,
    selection_bias_evidence: VerifiedSelectionBiasEvidence | None = None,
) -> DevelopmentQualification:
    """Qualify one complete batch against its source-issued DSR evidence.

    Returned economic rejection reasons apply only to valid complete records.
    Malformed evidence fails at its typed construction boundary instead.
    """

    aggregate = aggregate_development_economics(batch, FillCostCase.STRESS)
    economic_rejections = _qualification_rejections(aggregate)
    verified_evidence = (
        type(selection_bias_evidence) is VerifiedSelectionBiasEvidence
        and getattr(selection_bias_evidence, "_seal", None)
        is _VERIFIED_SELECTION_BIAS_SEAL
        and selection_bias_evidence.candidate_slot_id == batch.slot_id
        and selection_bias_evidence.development_batch_digest == batch.batch_digest
        and selection_bias_evidence.ledger_id == SELECTION_BIAS_INPUT.ledger_id
        and selection_bias_evidence.effective_trial_count
        == SELECTION_BIAS_INPUT.effective_trial_count
    )
    selection_bias_status = (
        SelectionBiasStatus.DSR_VERIFIED
        if verified_evidence
        else SelectionBiasStatus.STATISTICAL_EVIDENCE_UNAVAILABLE
    )
    reasons = list(economic_rejections)
    if not verified_evidence:
        reasons.append(QualificationRejection.SELECTION_BIAS_EVIDENCE_UNAVAILABLE)
    elif not _selection_bias_probability_meets_threshold(
        selection_bias_evidence.probability
    ):
        reasons.append(
            QualificationRejection.SELECTION_BIAS_PROBABILITY_BELOW_THRESHOLD
        )
    material = {
        "schema": _QUALIFICATION_SCHEMA,
        "batch_digest": batch.batch_digest,
        "economics_case": FillCostCase.STRESS.value,
        "economic_rejections": [item.value for item in economic_rejections],
        "selection_bias_status": selection_bias_status.value,
        "selection_bias_evidence_digest": (
            selection_bias_evidence.evidence_digest if verified_evidence else None
        ),
        "selection_bias_rejections": [
            item.value for item in reasons[len(economic_rejections) :]
        ],
    }
    qualification_id = uuid5(
        _QUALIFICATION_NAMESPACE, _canonical_json(material).decode("utf-8")
    )
    return DevelopmentQualification(
        batch.slot_id,
        batch.batch_digest,
        aggregate,
        economic_rejections,
        tuple(reasons),
        selection_bias_status,
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
            ("schema", "arch151-selection-bias-input/v2"),
            ("semantic_contract_version", SEMANTIC_CONTRACT_VERSION),
            ("ledger_id", PRIOR_INTRADAY_TRIAL_LEDGER.ledger_id),
            ("ledger_fingerprint", PRIOR_INTRADAY_TRIAL_LEDGER.fingerprint),
            ("documented_prior_intraday_trials", prior),
            ("current_search_slots", 32),
            ("minimum_effective_trial_count", 64),
            ("effective_trial_count", effective),
            ("required_probability", Decimal("0.95")),
            ("status", SelectionBiasStatus.DSR_COMPUTATION_REQUIRED),
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
    stress_profit_factor: Decimal | ProfitFactor,
    stress_sharpe: Decimal,
    max_drawdown: Decimal,
    turnover: Decimal,
    slot_id: UUID,
) -> tuple[Decimal | int, ...]:
    """Pure lexicographic key; synthetic calls never create qualification authority."""

    if type(slot_id) is not UUID:
        raise TypeError("ranking slot tie-break requires an immutable UUID")
    decimal_values = (
        type(value) is not Decimal
        for value in (
            probability,
            worst_scored_year_return,
            stress_sharpe,
            max_drawdown,
            turnover,
        )
    )
    if any(decimal_values) or type(stress_profit_factor) not in (Decimal, ProfitFactor):
        raise TypeError("ranking metrics must be Decimal values")
    values = tuple(
        _decimal(value, name)
        for name, value in (
            ("probability", probability),
            ("worst-year return", worst_scored_year_return),
            ("STRESS Sharpe", stress_sharpe),
            ("maximum drawdown", max_drawdown),
            ("turnover", turnover),
        )
    )
    probability_value, worst_return, sharpe, drawdown, turnover_value = values
    profit_factor = (
        ProfitFactor.finite(_decimal(stress_profit_factor, "STRESS profit factor"))
        if type(stress_profit_factor) is Decimal
        else stress_profit_factor
    )
    if not Decimal(0) <= probability_value <= Decimal(1):
        raise ValueError("ranking probability must be between zero and one")
    if (
        profit_factor.state is ProfitFactorState.INVALID
        or (
            profit_factor.state is ProfitFactorState.FINITE
            and (profit_factor.finite_value is None or profit_factor.finite_value < 0)
        )
        or not Decimal(0) <= drawdown <= Decimal(1)
    ):
        raise ValueError("ranking metrics are invalid")
    if turnover_value < 0:
        raise ValueError("ranking turnover cannot be negative")
    return (
        -probability_value,
        -worst_return,
        *profit_factor.ranking_key,
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
    ZERO_CANDIDATES_STATISTICAL_EVIDENCE_UNAVAILABLE = (
        "ZERO_CANDIDATES_STATISTICAL_EVIDENCE_UNAVAILABLE"
    )
    ZERO_CANDIDATES_NO_QUALIFIED_SURVIVOR = "ZERO_CANDIDATES_NO_QUALIFIED_SURVIVOR"
    ONE_CANDIDATE_FROZEN = "ONE_CANDIDATE_FROZEN"


class HoldoutConclusion(StrEnum):
    PASS = "PASS"


@dataclass(frozen=True, slots=True, init=False)
class VerifiedSelectionBiasEvidence:
    """Source-issued DSR result bound to one batch and the full population."""

    candidate_slot_id: UUID
    development_batch_digest: str
    population_digest: str
    ledger_id: UUID
    effective_trial_count: int
    observation_count: int
    daily_sharpe: Decimal
    expected_max_daily_sharpe: Decimal
    skew: Decimal
    non_excess_kurtosis: Decimal
    probability: Decimal
    evidence_id: UUID
    evidence_digest: str
    _seal: object

    def __init__(
        self,
        *,
        _seal: object = None,
        candidate_slot_id: UUID | None = None,
        development_batch_digest: str | None = None,
        population_digest: str | None = None,
        daily_sharpe: Decimal | None = None,
        expected_max_daily_sharpe: Decimal | None = None,
        skew: Decimal | None = None,
        non_excess_kurtosis: Decimal | None = None,
        probability: Decimal | None = None,
    ) -> None:
        if _seal is not _VERIFIED_SELECTION_BIAS_SEAL:
            raise AuthorizationUnavailableError(
                "verified DSR evidence must come from the complete source population"
            )
        if type(candidate_slot_id) is not UUID:
            raise TypeError("DSR evidence candidate identity must be a UUID")
        for name, digest in (
            ("development batch", development_batch_digest),
            ("population", population_digest),
        ):
            if (
                type(digest) is not str
                or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)
            ):
                raise ValueError(f"DSR {name} digest must be lowercase SHA-256")
        decimal_fields = (
            ("daily_sharpe", daily_sharpe),
            ("expected_max_daily_sharpe", expected_max_daily_sharpe),
            ("skew", skew),
            ("non_excess_kurtosis", non_excess_kurtosis),
            ("probability", probability),
        )
        normalized: dict[str, Decimal] = {}
        for name, value in decimal_fields:
            if type(value) is not Decimal:
                raise TypeError(f"DSR {name} must be Decimal")
            normalized[name] = _decimal(value, f"DSR {name}")
        probability_value = normalized["probability"]
        if not Decimal(0) <= probability_value <= Decimal(1):
            raise ValueError("DSR probability must be between zero and one")
        if normalized[
            "non_excess_kurtosis"
        ] < 0 or SELECTION_BIAS_INPUT.effective_trial_count != max(
            SELECTION_BIAS_INPUT.minimum_effective_trial_count,
            SELECTION_BIAS_INPUT.current_search_slots
            + SELECTION_BIAS_INPUT.documented_prior_intraday_trials,
        ):
            raise Arch151Error("DSR evidence statistical inputs are invalid")
        material = {
            "schema": "arch151-verified-selection-bias-evidence/v1",
            "candidate_slot_id": str(candidate_slot_id),
            "development_batch_digest": development_batch_digest,
            "population_digest": population_digest,
            "ledger_id": str(SELECTION_BIAS_INPUT.ledger_id),
            "effective_trial_count": SELECTION_BIAS_INPUT.effective_trial_count,
            "observation_count": DSR_OBSERVATION_COUNT,
            **{name: _decimal_text(value) for name, value in normalized.items()},
        }
        canonical = _canonical_json(material)
        values: tuple[tuple[str, object], ...] = (
            ("candidate_slot_id", candidate_slot_id),
            ("development_batch_digest", development_batch_digest),
            ("population_digest", population_digest),
            ("ledger_id", SELECTION_BIAS_INPUT.ledger_id),
            ("effective_trial_count", SELECTION_BIAS_INPUT.effective_trial_count),
            ("observation_count", DSR_OBSERVATION_COUNT),
            *tuple(normalized.items()),
            ("evidence_id", uuid5(_DSR_EVIDENCE_NAMESPACE, canonical.decode("utf-8"))),
            ("evidence_digest", sha256(canonical).hexdigest()),
            ("_seal", _seal),
        )
        for name, value in values:
            object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True)
class SelectionBiasCalculation:
    """Complete DSR status, candidate diagnostics, and non-authorizing order."""

    status: SelectionBiasStatus
    population_digest: str
    effective_trial_count: int
    evidence: tuple[VerifiedSelectionBiasEvidence, ...]
    trial_diagnostics: tuple[DsrTrialDiagnostic, ...]
    affected_trial_slot_ids: tuple[UUID, ...]
    descriptive_economic_order: tuple[UUID, ...]
    unavailable_reason: DsrUnavailableReason | None
    calculation_id: UUID

    def __post_init__(self) -> None:
        if type(self.status) is not SelectionBiasStatus:
            raise TypeError("selection-bias calculation status is invalid")
        if (
            type(self.population_digest) is not str
            or len(self.population_digest) != 64
            or any(char not in "0123456789abcdef" for char in self.population_digest)
        ):
            raise ValueError("selection-bias population digest is invalid")
        if self.effective_trial_count != SELECTION_BIAS_INPUT.effective_trial_count:
            raise Arch151Error("selection-bias effective count differs from ledger")
        if type(self.calculation_id) is not UUID:
            raise TypeError("selection-bias calculation identity must be a UUID")
        if type(self.evidence) is not tuple:
            raise TypeError("selection-bias evidence must be an immutable tuple")
        expected_slot_ids = tuple(item.slot_id for item in CANONICAL_SLOTS)
        if (
            type(self.trial_diagnostics) is not tuple
            or len(self.trial_diagnostics) != len(expected_slot_ids)
            or any(
                type(item) is not DsrTrialDiagnostic for item in self.trial_diagnostics
            )
            or tuple(item.candidate_slot_id for item in self.trial_diagnostics)
            != expected_slot_ids
        ):
            raise Arch151Error("DSR diagnostics must preserve all 32 canonical slots")
        if type(self.affected_trial_slot_ids) is not tuple:
            raise TypeError("affected DSR slot IDs must be an immutable tuple")
        if type(self.descriptive_economic_order) is not tuple:
            raise TypeError("descriptive economic order must be an immutable tuple")
        unavailable_ids = tuple(
            item.candidate_slot_id
            for item in self.trial_diagnostics
            if item.unavailable_reason is not None
        )
        if self.affected_trial_slot_ids != unavailable_ids:
            raise Arch151Error("affected DSR slots must match candidate diagnostics")
        if len(self.descriptive_economic_order) != len(expected_slot_ids) or set(
            self.descriptive_economic_order
        ) != set(expected_slot_ids):
            raise Arch151Error("descriptive economic order must preserve all 32 slots")
        if self.status is SelectionBiasStatus.DSR_VERIFIED:
            if (
                len(self.evidence) != len(CANONICAL_SLOTS)
                or any(
                    type(item) is not VerifiedSelectionBiasEvidence
                    or getattr(item, "_seal", None) is not _VERIFIED_SELECTION_BIAS_SEAL
                    or item.population_digest != self.population_digest
                    or item.ledger_id != SELECTION_BIAS_INPUT.ledger_id
                    or item.effective_trial_count
                    != SELECTION_BIAS_INPUT.effective_trial_count
                    or item.observation_count != DSR_OBSERVATION_COUNT
                    for item in self.evidence
                )
                or tuple(item.candidate_slot_id for item in self.evidence)
                != tuple(item.slot_id for item in CANONICAL_SLOTS)
                or self.unavailable_reason is not None
                or self.affected_trial_slot_ids
                or any(
                    item.status is not DsrTrialStatus.SHARPE_AVAILABLE
                    or item.unavailable_reason is not None
                    for item in self.trial_diagnostics
                )
            ):
                raise Arch151Error(
                    "verified DSR requires the complete ordered population"
                )
        elif (
            self.evidence
            or not isinstance(self.unavailable_reason, DsrUnavailableReason)
            or not self.affected_trial_slot_ids
            or self.unavailable_reason
            != next(
                item.unavailable_reason
                for item in self.trial_diagnostics
                if item.unavailable_reason is not None
            )
        ):
            raise Arch151Error(
                "unavailable DSR requires reasons and no partial evidence"
            )
        if self.calculation_id != _selection_bias_calculation_id(
            self.status,
            self.population_digest,
            self.evidence,
            self.trial_diagnostics,
            self.affected_trial_slot_ids,
            self.descriptive_economic_order,
            self.unavailable_reason,
        ):
            raise Arch151Error(
                "selection-bias calculation identity does not match canonical inputs"
            )


def _selection_bias_calculation_id(
    status: SelectionBiasStatus,
    population_digest: str,
    evidence: tuple[VerifiedSelectionBiasEvidence, ...],
    trial_diagnostics: tuple[DsrTrialDiagnostic, ...],
    affected_trial_slot_ids: tuple[UUID, ...],
    descriptive_economic_order: tuple[UUID, ...],
    unavailable_reason: DsrUnavailableReason | None,
) -> UUID:
    common_material = {
        "schema": "arch151-dsr-population-calculation/v2",
        "population_digest": population_digest,
        "status": status.value,
        "trial_diagnostics": [item.canonical_material() for item in trial_diagnostics],
        "affected_trial_slot_ids": [str(item) for item in affected_trial_slot_ids],
        "descriptive_economic_order": [
            str(item) for item in descriptive_economic_order
        ],
    }
    if status is SelectionBiasStatus.DSR_VERIFIED:
        material = {
            **common_material,
            "evidence_ids": [str(item.evidence_id) for item in evidence],
        }
    else:
        if not isinstance(unavailable_reason, DsrUnavailableReason):
            raise Arch151Error("unavailable DSR calculation requires a reason")
        material = {
            **common_material,
            "reason": unavailable_reason.value,
        }
    canonical = _canonical_json(material)
    return uuid5(_DSR_CALCULATION_NAMESPACE, canonical.decode("utf-8"))


_DSR_PI = Decimal(
    "3.141592653589793238462643383279502884197169399375105820974944592307816406286"
)
_EULER_MASCHERONI = Decimal(
    "0.577215664901532860606512090082402431042159335939923598805767234884867726"
)


def _normal_cdf(value: Decimal) -> Decimal:
    """High-precision standard-normal CDF using a Decimal erf series."""

    if type(value) is not Decimal or not value.is_finite():
        raise TypeError("normal CDF input must be a finite Decimal")
    if value == 0:
        return Decimal("0.5")
    if value >= Decimal(20):
        return Decimal(1)
    if value <= Decimal(-20):
        return Decimal(0)
    if value < 0:
        with localcontext(_DECIMAL_CONTEXT):
            return Decimal(1) - _normal_cdf(-value)
    guard_context = _DECIMAL_CONTEXT.copy()
    guard_context.prec = 140
    with localcontext(guard_context):
        scaled = value / Decimal(2).sqrt()
        term = scaled
        series = term
        scaled_squared = scaled * scaled
        for index in range(1, 1200):
            term *= (
                -scaled_squared
                * Decimal(2 * index - 1)
                / (Decimal(index) * Decimal(2 * index + 1))
            )
            series += term
            if abs(term) < Decimal("1e-130"):
                break
        erf = Decimal(2) * series / _DSR_PI.sqrt()
        result = (Decimal(1) + erf) / Decimal(2)
    with localcontext(_DECIMAL_CONTEXT):
        return +result


def _normal_quantile(probability: Decimal) -> Decimal:
    if type(probability) is not Decimal or not Decimal(0) < probability < Decimal(1):
        raise ValueError(
            "normal quantile requires a probability strictly between zero and one"
        )
    low = Decimal(0)
    high = Decimal(5)
    with localcontext(_DECIMAL_CONTEXT):
        for _ in range(240):
            midpoint = (low + high) / Decimal(2)
            if midpoint == low or midpoint == high:
                break
            if _normal_cdf(midpoint) < probability:
                low = midpoint
            else:
                high = midpoint
        return +(low + high) / Decimal(2)


def _expected_maximum_standard_normal_quantiles() -> Decimal:
    with localcontext(_DECIMAL_CONTEXT):
        effective = Decimal(SELECTION_BIAS_INPUT.effective_trial_count)
        first_probability = Decimal(1) - Decimal(1) / effective
        e_value = Decimal(1).exp()
        second_probability = Decimal(1) - Decimal(1) / (effective * e_value)
        first = _normal_quantile(first_probability)
        second = _normal_quantile(second_probability)
        gamma = _EULER_MASCHERONI
        return +((Decimal(1) - gamma) * first + gamma * second)


def _trial_return_statistics(
    returns: tuple[Decimal, ...],
) -> tuple[Decimal, Decimal, Decimal, Decimal] | DsrUnavailableReason | None:
    if len(returns) != DSR_OBSERVATION_COUNT:
        return None
    if any(type(value) is not Decimal or not value.is_finite() for value in returns):
        return DsrUnavailableReason.INVALID_CANDIDATE_MOMENTS
    try:
        standard_deviation = _sample_standard_deviation_centered(returns)
    except ArithmeticError:
        return DsrUnavailableReason.INVALID_CANDIDATE_MOMENTS
    if standard_deviation <= 0:
        return None
    try:
        with localcontext(_DECIMAL_CONTEXT):
            count = Decimal(len(returns))
            mean = sum(returns, Decimal(0)) / count
            centered = tuple(value - mean for value in returns)
            second = sum((value**2 for value in centered), Decimal(0)) / count
            if second <= 0:
                return DsrUnavailableReason.INVALID_CANDIDATE_MOMENTS
            third = sum((value**3 for value in centered), Decimal(0)) / count
            fourth = sum((value**4 for value in centered), Decimal(0)) / count
            skew = third / second.sqrt() ** 3
            kurtosis = fourth / second**2
            sharpe = mean / standard_deviation
    except ArithmeticError:
        return DsrUnavailableReason.INVALID_CANDIDATE_MOMENTS
    values = (sharpe, skew, kurtosis, standard_deviation)
    if any(not value.is_finite() for value in values):
        return DsrUnavailableReason.INVALID_CANDIDATE_MOMENTS
    return values


def _sample_standard_deviation_centered(values: Sequence[Decimal]) -> Decimal:
    """Stable ddof=1 deviation centered around the first value."""

    points = tuple(values)
    if len(points) < 2:
        raise UnavailableIndicatorError("sample deviation requires two observations")
    if any(type(value) is not Decimal or not value.is_finite() for value in points):
        raise TypeError("sample deviation values must be finite Decimals")
    with localcontext(_DECIMAL_CONTEXT):
        origin = points[0]
        offsets = tuple(value - origin for value in points)
        mean_offset = sum(offsets, Decimal(0)) / Decimal(len(offsets))
        variance = sum(
            ((value - mean_offset) ** 2 for value in offsets), Decimal(0)
        ) / Decimal(len(offsets) - 1)
        if variance == 0:
            return Decimal(0)
        return variance.sqrt()


def _selection_bias_population_digest(
    batches: tuple[DevelopmentEvaluationBatch, ...],
) -> str:
    material = {
        "schema": "arch151-selection-bias-population/v1",
        "semantic_contract_version": SEMANTIC_CONTRACT_VERSION,
        "manifest_id": str(CANONICAL_MANIFEST.manifest_id),
        "ledger_id": str(SELECTION_BIAS_INPUT.ledger_id),
        "effective_trial_count": SELECTION_BIAS_INPUT.effective_trial_count,
        "batch_digests": [item.batch_digest for item in batches],
    }
    return sha256(_canonical_json(material)).hexdigest()


def rank_descriptive_economic_population(
    batches: Sequence[DevelopmentEvaluationBatch],
) -> tuple[UUID, ...]:
    """Order all canonical slots descriptively without DSR or freeze authority.

    Undefined Sharpe values sort after finite Sharpe values at that tie-break;
    they do not remove a slot from this complete descriptive order.
    """

    population = tuple(batches)
    expected = tuple(item.slot_id for item in CANONICAL_SLOTS)
    if (
        len(population) != len(expected)
        or any(type(item) is not DevelopmentEvaluationBatch for item in population)
        or tuple(item.slot_id for item in population) != expected
    ):
        raise Arch151Error(
            "descriptive economic order requires all 32 canonical slot batches"
        )
    ordered: list[tuple[tuple[Decimal | int, ...], UUID]] = []
    for batch in population:
        aggregate = aggregate_development_economics(batch, FillCostCase.STRESS)
        if type(aggregate.profit_factor) is not ProfitFactor:
            raise Arch151Error("descriptive order requires typed STRESS profit factor")
        sharpe_unavailable = aggregate.sharpe is None
        sharpe_key = (
            Decimal(0) if sharpe_unavailable else -aggregate.sharpe  # type: ignore[operator]
        )
        key: tuple[Decimal | int, ...] = (
            -aggregate.worst_scored_year_return,
            *aggregate.profit_factor.ranking_key,
            int(sharpe_unavailable),
            sharpe_key,
            aggregate.max_drawdown,
            aggregate.turnover,
            batch.slot_id.int,
        )
        ordered.append((key, batch.slot_id))
    return tuple(slot_id for _key, slot_id in sorted(ordered))


def _unavailable_selection_bias_calculation(
    population_digest: str,
    reason: DsrUnavailableReason,
    trial_diagnostics: tuple[DsrTrialDiagnostic, ...],
    descriptive_economic_order: tuple[UUID, ...],
) -> SelectionBiasCalculation:
    affected = tuple(
        item.candidate_slot_id
        for item in trial_diagnostics
        if item.unavailable_reason is not None
    )
    status = SelectionBiasStatus.STATISTICAL_EVIDENCE_UNAVAILABLE
    calculation_id = _selection_bias_calculation_id(
        status,
        population_digest,
        (),
        trial_diagnostics,
        affected,
        descriptive_economic_order,
        reason,
    )
    return SelectionBiasCalculation(
        status,
        population_digest,
        SELECTION_BIAS_INPUT.effective_trial_count,
        (),
        trial_diagnostics,
        affected,
        descriptive_economic_order,
        reason,
        calculation_id,
    )


def _mark_population_dsr_unavailable(
    diagnostics: tuple[DsrTrialDiagnostic, ...], reason: DsrUnavailableReason
) -> tuple[DsrTrialDiagnostic, ...]:
    return tuple(
        DsrTrialDiagnostic(
            diagnostic.candidate_slot_id,
            (
                DsrTrialStatus.SHARPE_AVAILABLE
                if diagnostic.daily_sharpe is not None
                else DsrTrialStatus.SHARPE_UNAVAILABLE
            ),
            diagnostic.daily_sharpe,
            reason,
        )
        for diagnostic in diagnostics
    )


def compute_selection_bias_evidence(
    batches: Sequence[DevelopmentEvaluationBatch],
) -> SelectionBiasCalculation:
    """Compute Bailey DSR for the complete canonical 32-slot STRESS population."""

    population = tuple(batches)
    expected_slots = tuple(item.slot_id for item in CANONICAL_SLOTS)
    if len(population) != len(expected_slots) or any(
        type(item) is not DevelopmentEvaluationBatch for item in population
    ):
        raise Arch151Error("DSR requires all 32 complete canonical slot batches")
    if tuple(item.slot_id for item in population) != expected_slots:
        raise Arch151Error("DSR population must preserve canonical manifest order")
    population_digest = _selection_bias_population_digest(population)
    descriptive_order = rank_descriptive_economic_population(population)
    trial_statistics: list[tuple[Decimal, Decimal, Decimal, Decimal] | None] = []
    trial_diagnostics: list[DsrTrialDiagnostic] = []
    for batch in population:
        stress_records = tuple(
            record
            for record in batch.records
            if record.economics_case is FillCostCase.STRESS
        )
        if tuple(record.fold for record in stress_records) != WALK_FORWARD_FOLDS:
            raise Arch151Error("DSR requires all five exact STRESS folds per slot")
        returns = tuple(
            value
            for record in stress_records
            for value in record.metrics.session_net_returns
        )
        statistics = _trial_return_statistics(returns)
        if statistics is None or isinstance(statistics, DsrUnavailableReason):
            reason = (
                statistics
                if isinstance(statistics, DsrUnavailableReason)
                else DsrUnavailableReason.UNDEFINED_TRIAL_SHARPE
            )
            trial_statistics.append(None)
            trial_diagnostics.append(
                DsrTrialDiagnostic(
                    batch.slot_id,
                    DsrTrialStatus.SHARPE_UNAVAILABLE,
                    None,
                    reason,
                )
            )
            continue
        if (
            type(statistics) is not tuple
            or len(statistics) != 4
            or any(
                type(value) is not Decimal or not value.is_finite()
                for value in statistics
            )
            or statistics[3] <= 0
        ):
            trial_statistics.append(None)
            trial_diagnostics.append(
                DsrTrialDiagnostic(
                    batch.slot_id,
                    DsrTrialStatus.SHARPE_UNAVAILABLE,
                    None,
                    DsrUnavailableReason.INVALID_CANDIDATE_MOMENTS,
                )
            )
            continue
        trial_statistics.append(statistics)
        trial_diagnostics.append(
            DsrTrialDiagnostic(
                batch.slot_id,
                DsrTrialStatus.SHARPE_AVAILABLE,
                statistics[0],
                None,
            )
        )
    diagnostics = tuple(trial_diagnostics)
    candidate_unavailable = tuple(
        item for item in diagnostics if item.unavailable_reason is not None
    )
    if candidate_unavailable:
        reason = candidate_unavailable[0].unavailable_reason
        assert reason is not None
        return _unavailable_selection_bias_calculation(
            population_digest, reason, diagnostics, descriptive_order
        )

    concrete_statistics = tuple(item for item in trial_statistics if item is not None)
    sharpes = tuple(item[0] for item in concrete_statistics)
    try:
        sharpe_dispersion = _sample_standard_deviation_centered(sharpes)
    except ArithmeticError:
        reason = DsrUnavailableReason.INVALID_CANDIDATE_MOMENTS
        diagnostics = _mark_population_dsr_unavailable(diagnostics, reason)
        return _unavailable_selection_bias_calculation(
            population_digest, reason, diagnostics, descriptive_order
        )
    if sharpe_dispersion == 0:
        reason = DsrUnavailableReason.ZERO_TRIAL_SHARPE_VARIANCE
        diagnostics = _mark_population_dsr_unavailable(diagnostics, reason)
        return _unavailable_selection_bias_calculation(
            population_digest, reason, diagnostics, descriptive_order
        )
    try:
        with localcontext(_DECIMAL_CONTEXT):
            expected_maximum = (
                sharpe_dispersion * _expected_maximum_standard_normal_quantiles()
            )
            time_scale = Decimal(DSR_OBSERVATION_COUNT - 1).sqrt()
    except ArithmeticError:
        reason = DsrUnavailableReason.INVALID_CANDIDATE_MOMENTS
        diagnostics = _mark_population_dsr_unavailable(diagnostics, reason)
        return _unavailable_selection_bias_calculation(
            population_digest, reason, diagnostics, descriptive_order
        )
    evidence_records: list[VerifiedSelectionBiasEvidence] = []
    failures: dict[UUID, DsrUnavailableReason] = {}
    for batch, (sharpe, skew, kurtosis, _std) in zip(
        population, concrete_statistics, strict=True
    ):
        with localcontext(_DECIMAL_CONTEXT):
            dsr_variance = (
                Decimal(1)
                - skew * sharpe
                + ((kurtosis - Decimal(1)) / Decimal(4)) * sharpe**2
            )
        if not dsr_variance.is_finite() or dsr_variance <= 0:
            failures[batch.slot_id] = DsrUnavailableReason.DEGENERATE_DSR_VARIANCE
            continue
        try:
            with localcontext(_DECIMAL_CONTEXT):
                probability = _normal_cdf(
                    (sharpe - expected_maximum) * time_scale / dsr_variance.sqrt()
                )
        except ArithmeticError:
            failures[batch.slot_id] = DsrUnavailableReason.INVALID_CANDIDATE_MOMENTS
            continue
        if (
            type(probability) is not Decimal
            or not probability.is_finite()
            or not (Decimal(0) <= probability <= Decimal(1))
        ):
            failures[batch.slot_id] = DsrUnavailableReason.INVALID_CANDIDATE_MOMENTS
            continue
        evidence_records.append(
            VerifiedSelectionBiasEvidence(
                _seal=_VERIFIED_SELECTION_BIAS_SEAL,
                candidate_slot_id=batch.slot_id,
                development_batch_digest=batch.batch_digest,
                population_digest=population_digest,
                daily_sharpe=sharpe,
                expected_max_daily_sharpe=expected_maximum,
                skew=skew,
                non_excess_kurtosis=kurtosis,
                probability=probability,
            )
        )
    if failures:
        diagnostics = tuple(
            DsrTrialDiagnostic(
                item.candidate_slot_id,
                DsrTrialStatus.SHARPE_AVAILABLE
                if item.candidate_slot_id in failures
                else item.status,
                item.daily_sharpe,
                failures.get(item.candidate_slot_id, item.unavailable_reason),
            )
            for item in diagnostics
        )
        reason = next(iter(failures.values()))
        return _unavailable_selection_bias_calculation(
            population_digest, reason, diagnostics, descriptive_order
        )
    evidence = tuple(evidence_records)
    status = SelectionBiasStatus.DSR_VERIFIED
    calculation_id = _selection_bias_calculation_id(
        status,
        population_digest,
        evidence,
        diagnostics,
        (),
        descriptive_order,
        None,
    )
    return SelectionBiasCalculation(
        status,
        population_digest,
        SELECTION_BIAS_INPUT.effective_trial_count,
        evidence,
        diagnostics,
        (),
        descriptive_order,
        None,
        calculation_id,
    )


def rank_verified_candidate_population(
    batches: Sequence[DevelopmentEvaluationBatch],
    selection: SelectionBiasCalculation,
) -> tuple[UUID, ...]:
    """Rank the complete population using source-issued DSR evidence."""

    population = tuple(batches)
    expected = tuple(slot.slot_id for slot in CANONICAL_SLOTS)
    if (
        len(population) != len(expected)
        or tuple(item.slot_id for item in population) != expected
    ):
        raise Arch151Error("verified ranking requires all 32 canonical slot batches")
    if (
        type(selection) is not SelectionBiasCalculation
        or selection.status is not SelectionBiasStatus.DSR_VERIFIED
        or selection.population_digest != _selection_bias_population_digest(population)
        or len(selection.evidence) != len(expected)
    ):
        raise AuthorizationUnavailableError(
            "complete source-issued DSR population evidence is required for ranking"
        )
    ordered_material: list[tuple[tuple[Decimal | int, ...], UUID]] = []
    for batch, evidence in zip(population, selection.evidence, strict=True):
        if (
            getattr(evidence, "_seal", None) is not _VERIFIED_SELECTION_BIAS_SEAL
            or evidence.candidate_slot_id != batch.slot_id
            or evidence.development_batch_digest != batch.batch_digest
            or evidence.population_digest != selection.population_digest
        ):
            raise AuthorizationUnavailableError(
                "ranking DSR evidence does not bind the complete canonical population"
            )
        aggregate = aggregate_development_economics(batch, FillCostCase.STRESS)
        if aggregate.sharpe is None:
            raise AuthorizationUnavailableError(
                "verified DSR candidate has no finite STRESS Sharpe"
            )
        key = _ranking_key(
            evidence.probability,
            aggregate.worst_scored_year_return,
            aggregate.profit_factor,
            aggregate.sharpe,
            aggregate.max_drawdown,
            aggregate.turnover,
            batch.slot_id,
        )
        ordered_material.append((key, batch.slot_id))
    return tuple(slot_id for _key, slot_id in sorted(ordered_material))


@dataclass(frozen=True, slots=True, init=False)
class AuthenticatedDevelopmentEvidence:
    """Sealed binding of the complete accepted-source development result."""

    freeze_id: UUID
    freeze_fingerprint: str
    candidate_slot_id: UUID
    source_manifest_id: UUID
    manifest_fingerprint: str
    batch_digests: tuple[str, ...]
    year_batch_ids: tuple[UUID, ...]
    run_id: UUID
    report_id: UUID
    report_sha256: str
    record_count: int
    source_kind: str
    source_binding_id: UUID
    source_digest: str
    source_branch: str
    source_origin: str
    source_head: str
    source_tree: str
    invocation_id: UUID
    source_revision_digest: str
    selection_bias_calculation_id: UUID
    selection_bias_population_digest: str
    selection_bias_ledger_id: UUID
    selection_bias_effective_trial_count: int
    selection_bias_evidence_ids: tuple[UUID, ...]
    selection_bias_evidence_digests: tuple[str, ...]
    evidence_id: UUID
    evidence_digest: str
    _seal: object

    def __init__(
        self,
        *,
        _seal: object = None,
        freeze_id: UUID,
        freeze_fingerprint: str,
        candidate_slot_id: UUID,
        source_manifest_id: UUID,
        manifest_fingerprint: str,
        batch_digests: tuple[str, ...],
        year_batch_ids: tuple[UUID, ...],
        run_id: UUID,
        report_id: UUID,
        report_sha256: str,
        record_count: int,
        source_kind: str,
        source_binding_id: UUID,
        source_digest: str,
        source_branch: str,
        source_origin: str,
        source_head: str,
        source_tree: str,
        invocation_id: UUID,
        source_revision_digest: str,
        selection_bias_calculation_id: UUID,
        selection_bias_population_digest: str,
        selection_bias_ledger_id: UUID,
        selection_bias_effective_trial_count: int,
        selection_bias_evidence_ids: tuple[UUID, ...],
        selection_bias_evidence_digests: tuple[str, ...],
    ) -> None:
        if _seal is not _AUTHENTICATED_DEVELOPMENT_EVIDENCE_SEAL:
            raise AuthorizationUnavailableError(
                "authenticated development evidence requires the sealed "
                "accepted-source evaluator"
            )
        if (
            type(freeze_id) is not UUID
            or type(candidate_slot_id) is not UUID
            or candidate_slot_id not in {item.slot_id for item in CANONICAL_SLOTS}
            or source_manifest_id != CANONICAL_MANIFEST.manifest_id
            or manifest_fingerprint != CANONICAL_MANIFEST.fingerprint
            or type(run_id) is not UUID
            or type(report_id) is not UUID
            or type(source_binding_id) is not UUID
            or type(invocation_id) is not UUID
            or type(selection_bias_calculation_id) is not UUID
            or selection_bias_ledger_id != SELECTION_BIAS_INPUT.ledger_id
            or selection_bias_effective_trial_count
            != SELECTION_BIAS_INPUT.effective_trial_count
            or type(record_count) is not int
            or record_count != 480
            or source_kind != "ARCH150_D1R_ACCEPTED"
        ):
            raise AuthorizationUnavailableError(
                "development evidence does not bind one complete "
                "accepted-source candidate"
            )
        for name, digest in (
            ("freeze fingerprint", freeze_fingerprint),
            ("report SHA-256", report_sha256),
            ("source digest", source_digest),
            ("source revision digest", source_revision_digest),
            ("selection-bias population digest", selection_bias_population_digest),
        ):
            if not _is_sha256(digest):
                raise ValueError(f"{name} must be lowercase SHA-256")
        if (
            type(batch_digests) is not tuple
            or len(batch_digests) != len(CANONICAL_SLOTS)
            or any(not _is_sha256(item) for item in batch_digests)
            or type(year_batch_ids) is not tuple
            or len(year_batch_ids) != len(SCORED_YEARS)
            or any(type(item) is not UUID for item in year_batch_ids)
            or len(set(year_batch_ids)) != len(year_batch_ids)
        ):
            raise AuthorizationUnavailableError(
                "development evidence must bind the exact 32 slots and "
                "five year batches"
            )
        if (
            type(selection_bias_evidence_ids) is not tuple
            or len(selection_bias_evidence_ids) != len(CANONICAL_SLOTS)
            or any(type(item) is not UUID for item in selection_bias_evidence_ids)
            or len(set(selection_bias_evidence_ids)) != len(selection_bias_evidence_ids)
            or type(selection_bias_evidence_digests) is not tuple
            or len(selection_bias_evidence_digests) != len(CANONICAL_SLOTS)
            or any(not _is_sha256(item) for item in selection_bias_evidence_digests)
        ):
            raise AuthorizationUnavailableError(
                "development evidence must bind all 32 verified DSR records"
            )
        if (
            type(source_branch) is not str
            or not source_branch
            or type(source_origin) is not str
            or not source_origin
            or type(source_head) is not str
            or len(source_head) not in (40, 64)
            or any(char not in "0123456789abcdef" for char in source_head)
            or type(source_tree) is not str
            or len(source_tree) not in (40, 64)
            or any(char not in "0123456789abcdef" for char in source_tree)
        ):
            raise ValueError("development source revision identity is invalid")
        material = {
            "schema": "arch151-authenticated-development-evidence/v1",
            "freeze_id": str(freeze_id),
            "freeze_fingerprint": freeze_fingerprint,
            "candidate_slot_id": str(candidate_slot_id),
            "source_manifest_id": str(source_manifest_id),
            "manifest_fingerprint": manifest_fingerprint,
            "batch_digests": list(batch_digests),
            "year_batch_ids": [str(item) for item in year_batch_ids],
            "run_id": str(run_id),
            "report_id": str(report_id),
            "report_sha256": report_sha256,
            "record_count": record_count,
            "source_kind": source_kind,
            "source_binding_id": str(source_binding_id),
            "source_digest": source_digest,
            "source_branch": source_branch,
            "source_origin": source_origin,
            "source_head": source_head,
            "source_tree": source_tree,
            "invocation_id": str(invocation_id),
            "source_revision_digest": source_revision_digest,
            "selection_bias_calculation_id": str(selection_bias_calculation_id),
            "selection_bias_population_digest": selection_bias_population_digest,
            "selection_bias_ledger_id": str(selection_bias_ledger_id),
            "selection_bias_effective_trial_count": (
                selection_bias_effective_trial_count
            ),
            "selection_bias_evidence_ids": [
                str(item) for item in selection_bias_evidence_ids
            ],
            "selection_bias_evidence_digests": list(selection_bias_evidence_digests),
        }
        canonical = _canonical_json(material)
        values: tuple[tuple[str, object], ...] = (
            ("freeze_id", freeze_id),
            ("freeze_fingerprint", freeze_fingerprint),
            ("candidate_slot_id", candidate_slot_id),
            ("source_manifest_id", source_manifest_id),
            ("manifest_fingerprint", manifest_fingerprint),
            ("batch_digests", batch_digests),
            ("year_batch_ids", year_batch_ids),
            ("run_id", run_id),
            ("report_id", report_id),
            ("report_sha256", report_sha256),
            ("record_count", record_count),
            ("source_kind", source_kind),
            ("source_binding_id", source_binding_id),
            ("source_digest", source_digest),
            ("source_branch", source_branch),
            ("source_origin", source_origin),
            ("source_head", source_head),
            ("source_tree", source_tree),
            ("invocation_id", invocation_id),
            ("source_revision_digest", source_revision_digest),
            ("selection_bias_calculation_id", selection_bias_calculation_id),
            ("selection_bias_population_digest", selection_bias_population_digest),
            ("selection_bias_ledger_id", selection_bias_ledger_id),
            (
                "selection_bias_effective_trial_count",
                selection_bias_effective_trial_count,
            ),
            ("selection_bias_evidence_ids", selection_bias_evidence_ids),
            ("selection_bias_evidence_digests", selection_bias_evidence_digests),
            (
                "evidence_id",
                uuid5(
                    _AUTHENTICATED_DEVELOPMENT_EVIDENCE_NAMESPACE,
                    canonical.decode("utf-8"),
                ),
            ),
            ("evidence_digest", sha256(canonical).hexdigest()),
            ("_seal", _seal),
        )
        for name, value in values:
            object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True, init=False)
class AuthenticatedHoldoutPass:
    """Evaluator-owned holdout result type; no holdout reader is present here."""

    freeze_id: UUID
    freeze_fingerprint: str
    candidate_slot_id: UUID
    conclusion: HoldoutConclusion
    qualification_id: UUID
    source_revision_digest: str
    evidence_digest: str
    _seal: object

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise AuthorizationUnavailableError(
            "authenticated holdout PASS is unavailable in this foundation"
        )


@dataclass(frozen=True, slots=True, init=False)
class HoldoutAuthorization:
    """Sealed permission record bound to one exact source-owned freeze."""

    authorization_id: UUID
    freeze_id: UUID
    freeze_fingerprint: str
    candidate_slot_id: UUID
    development_evidence_digest: str
    development_report_id: UUID
    development_report_sha256: str
    source_revision_digest: str
    selection_bias_evidence_id: UUID
    selection_bias_evidence_digest: str
    mutation_policy: MutationAfterHoldoutVisibilityPolicy
    authorization_digest: str
    _seal: object

    def __init__(
        self,
        *,
        _seal: object = None,
        freeze_id: UUID,
        freeze_fingerprint: str,
        candidate_slot_id: UUID,
        development_evidence_digest: str,
        development_report_id: UUID,
        development_report_sha256: str,
        source_revision_digest: str,
        selection_bias_evidence_id: UUID,
        selection_bias_evidence_digest: str,
    ) -> None:
        if _seal is not _HOLDOUT_AUTHORIZATION_SEAL:
            raise AuthorizationUnavailableError(
                "holdout authorization must come from the source gate"
            )
        if (
            type(freeze_id) is not UUID
            or not _is_sha256(freeze_fingerprint)
            or type(candidate_slot_id) is not UUID
            or type(development_report_id) is not UUID
            or type(selection_bias_evidence_id) is not UUID
            or any(
                not _is_sha256(item)
                for item in (
                    development_evidence_digest,
                    development_report_sha256,
                    source_revision_digest,
                    selection_bias_evidence_digest,
                )
            )
        ):
            raise Arch151Error("holdout authorization binding is invalid")
        mutation_policy = MutationAfterHoldoutVisibilityPolicy.PROHIBITED
        material = {
            "schema": "arch151-holdout-authorization/v1",
            "freeze_id": str(freeze_id),
            "freeze_fingerprint": freeze_fingerprint,
            "candidate_slot_id": str(candidate_slot_id),
            "development_evidence_digest": development_evidence_digest,
            "development_report_id": str(development_report_id),
            "development_report_sha256": development_report_sha256,
            "source_revision_digest": source_revision_digest,
            "selection_bias_evidence_id": str(selection_bias_evidence_id),
            "selection_bias_evidence_digest": selection_bias_evidence_digest,
            "mutation_policy": mutation_policy.value,
        }
        canonical = _canonical_json(material)
        for name, value in (
            (
                "authorization_id",
                uuid5(_HOLDOUT_AUTHORIZATION_NAMESPACE, canonical.decode("utf-8")),
            ),
            ("freeze_id", freeze_id),
            ("freeze_fingerprint", freeze_fingerprint),
            ("candidate_slot_id", candidate_slot_id),
            ("development_evidence_digest", development_evidence_digest),
            ("development_report_id", development_report_id),
            ("development_report_sha256", development_report_sha256),
            ("source_revision_digest", source_revision_digest),
            ("selection_bias_evidence_id", selection_bias_evidence_id),
            ("selection_bias_evidence_digest", selection_bias_evidence_digest),
            ("mutation_policy", mutation_policy),
            ("authorization_digest", sha256(canonical).hexdigest()),
            ("_seal", _seal),
        ):
            object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True, init=False)
class ExtensionAuthorization:
    """Sealed extension permission bound to the same candidate and holdout PASS."""

    authorization_id: UUID
    freeze_id: UUID
    freeze_fingerprint: str
    candidate_slot_id: UUID
    source_revision_digest: str
    holdout_authorization_id: UUID
    holdout_pass_digest: str
    authorization_digest: str
    _seal: object

    def __init__(
        self,
        *,
        _seal: object = None,
        freeze_id: UUID,
        freeze_fingerprint: str,
        candidate_slot_id: UUID,
        source_revision_digest: str,
        holdout_authorization_id: UUID,
        holdout_pass_digest: str,
    ) -> None:
        if _seal is not _EXTENSION_AUTHORIZATION_SEAL:
            raise AuthorizationUnavailableError(
                "extension authorization must come from the source gate"
            )
        if (
            type(freeze_id) is not UUID
            or not _is_sha256(freeze_fingerprint)
            or type(candidate_slot_id) is not UUID
            or type(holdout_authorization_id) is not UUID
            or not _is_sha256(source_revision_digest)
            or not _is_sha256(holdout_pass_digest)
        ):
            raise Arch151Error("extension authorization binding is invalid")
        material = {
            "schema": "arch151-extension-authorization/v1",
            "freeze_id": str(freeze_id),
            "freeze_fingerprint": freeze_fingerprint,
            "candidate_slot_id": str(candidate_slot_id),
            "source_revision_digest": source_revision_digest,
            "holdout_authorization_id": str(holdout_authorization_id),
            "holdout_pass_digest": holdout_pass_digest,
        }
        canonical = _canonical_json(material)
        for name, value in (
            (
                "authorization_id",
                uuid5(_EXTENSION_AUTHORIZATION_NAMESPACE, canonical.decode("utf-8")),
            ),
            ("freeze_id", freeze_id),
            ("freeze_fingerprint", freeze_fingerprint),
            ("candidate_slot_id", candidate_slot_id),
            ("source_revision_digest", source_revision_digest),
            ("holdout_authorization_id", holdout_authorization_id),
            ("holdout_pass_digest", holdout_pass_digest),
            ("authorization_digest", sha256(canonical).hexdigest()),
            ("_seal", _seal),
        ):
            object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True, init=False)
class AuthenticatedExtensionPass:
    """Evaluator-owned extension PASS; no extension reader exists here."""

    freeze_id: UUID
    freeze_fingerprint: str
    candidate_slot_id: UUID
    extension_authorization_id: UUID
    holdout_pass_digest: str
    qualification_id: UUID
    source_revision_digest: str
    evidence_digest: str
    _seal: object

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise AuthorizationUnavailableError(
            "authenticated extension PASS is unavailable without the "
            "future extension evaluator"
        )


class ResearchSurvivorClass(StrEnum):
    ARCH151_INTRADAY_RESEARCH_SURVIVOR = "ARCH151_INTRADAY_RESEARCH_SURVIVOR"


@dataclass(frozen=True, slots=True, init=False)
class ResearchSurvivorClassification:
    """Research classification only; it grants no runtime or order authority."""

    classification: ResearchSurvivorClass
    freeze_id: UUID
    freeze_fingerprint: str
    candidate_slot_id: UUID
    source_revision_digest: str
    holdout_pass_digest: str
    extension_pass_digest: str
    classification_id: UUID
    _seal: object

    def __init__(
        self,
        *,
        _seal: object = None,
        classification: ResearchSurvivorClass,
        freeze_id: UUID,
        freeze_fingerprint: str,
        candidate_slot_id: UUID,
        source_revision_digest: str,
        holdout_pass_digest: str,
        extension_pass_digest: str,
        classification_id: UUID,
    ) -> None:
        if _seal is not _RESEARCH_SURVIVOR_CLASSIFICATION_SEAL:
            raise AuthorizationUnavailableError(
                "research survivor classification must follow "
                "authenticated PASS evidence"
            )
        material = {
            "schema": "arch151-research-survivor-classification/v1",
            "classification": classification.value,
            "freeze_id": str(freeze_id),
            "freeze_fingerprint": freeze_fingerprint,
            "candidate_slot_id": str(candidate_slot_id),
            "source_revision_digest": source_revision_digest,
            "holdout_pass_digest": holdout_pass_digest,
            "extension_pass_digest": extension_pass_digest,
            "runtime_authority": False,
            "order_authority": False,
        }
        expected_id = uuid5(
            _RESEARCH_SURVIVOR_NAMESPACE,
            _canonical_json(material).decode("utf-8"),
        )
        if (
            classification
            is not ResearchSurvivorClass.ARCH151_INTRADAY_RESEARCH_SURVIVOR
            or type(freeze_id) is not UUID
            or not _is_sha256(freeze_fingerprint)
            or type(candidate_slot_id) is not UUID
            or not _is_sha256(source_revision_digest)
            or not _is_sha256(holdout_pass_digest)
            or not _is_sha256(extension_pass_digest)
            or classification_id != expected_id
        ):
            raise Arch151Error("research survivor classification is not canonical")
        for name, value in (
            ("classification", classification),
            ("freeze_id", freeze_id),
            ("freeze_fingerprint", freeze_fingerprint),
            ("candidate_slot_id", candidate_slot_id),
            ("source_revision_digest", source_revision_digest),
            ("holdout_pass_digest", holdout_pass_digest),
            ("extension_pass_digest", extension_pass_digest),
            ("classification_id", classification_id),
            ("_seal", _seal),
        ):
            object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True, init=False)
class FinalCandidateFreeze:
    """Source-issued deterministic zero-or-one development candidate freeze."""

    source_manifest_id: UUID
    batch_digests: tuple[str, ...]
    economically_qualified_slot_ids: tuple[UUID, ...]
    ranking_order: tuple[UUID, ...]
    selection_bias_calculation_id: UUID | None
    selection_bias_evidence_digests: tuple[str, ...]
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
        ranking_order: tuple[UUID, ...],
        selection_bias_status: SelectionBiasStatus,
        selection_bias_calculation_id: UUID | None,
        selection_bias_evidence_digests: tuple[str, ...],
        candidate_slot_id: UUID | None,
        status: FinalFreezeStatus,
    ) -> None:
        if _seal is not _FINAL_FREEZE_SEAL:
            raise Arch151Error("final candidate freeze must be source-owned")
        expected_slot_ids = tuple(slot.slot_id for slot in CANONICAL_SLOTS)
        if type(batch_digests) is not tuple or len(batch_digests) != len(
            expected_slot_ids
        ):
            raise Arch151Error("final freeze must bind all 32 batch digests")
        if type(economically_qualified_slot_ids) is not tuple or any(
            item not in expected_slot_ids for item in economically_qualified_slot_ids
        ):
            raise Arch151Error("final freeze economic survivor identities are invalid")
        if type(selection_bias_status) is not SelectionBiasStatus:
            raise TypeError("final freeze DSR status is invalid")
        if type(status) is not FinalFreezeStatus:
            raise TypeError("final freeze status is invalid")
        if type(selection_bias_evidence_digests) is not tuple:
            raise TypeError("final freeze DSR evidence digests must be immutable")
        if selection_bias_status is SelectionBiasStatus.DSR_VERIFIED:
            if (
                type(selection_bias_calculation_id) is not UUID
                or len(selection_bias_evidence_digests) != len(expected_slot_ids)
                or len(ranking_order) != len(expected_slot_ids)
                or set(ranking_order) != set(expected_slot_ids)
            ):
                raise Arch151Error(
                    "verified final freeze requires complete DSR ranking"
                )
        elif (
            type(selection_bias_calculation_id) is not UUID
            or selection_bias_evidence_digests
            or ranking_order
        ):
            raise Arch151Error("unavailable DSR cannot authorize a candidate ranking")
        if status is FinalFreezeStatus.ONE_CANDIDATE_FROZEN:
            if candidate_slot_id not in expected_slot_ids:
                raise Arch151Error("one-candidate freeze requires a canonical slot")
        elif candidate_slot_id is not None:
            raise Arch151Error("zero-candidate freeze cannot name a candidate")
        if (
            status is FinalFreezeStatus.ZERO_CANDIDATES_STATISTICAL_EVIDENCE_UNAVAILABLE
        ) != (
            selection_bias_status
            is SelectionBiasStatus.STATISTICAL_EVIDENCE_UNAVAILABLE
        ):
            raise Arch151Error("final freeze status disagrees with DSR evidence status")
        material = {
            "schema": "arch151-final-candidate-freeze/v2",
            "semantic_contract_version": SEMANTIC_CONTRACT_VERSION,
            "source_manifest_id": str(CANONICAL_MANIFEST.manifest_id),
            "batch_digests": list(batch_digests),
            "economically_qualified_slot_ids": [
                str(value) for value in economically_qualified_slot_ids
            ],
            "ranking_order": [str(value) for value in ranking_order],
            "selection_bias_status": selection_bias_status.value,
            "selection_bias_calculation_id": (
                str(selection_bias_calculation_id)
                if selection_bias_calculation_id is not None
                else None
            ),
            "selection_bias_evidence_digests": list(selection_bias_evidence_digests),
            "candidate_slot_id": (
                str(candidate_slot_id) if candidate_slot_id is not None else None
            ),
            "status": status.value,
        }
        canonical = _canonical_json(material)
        values = (
            ("source_manifest_id", CANONICAL_MANIFEST.manifest_id),
            ("batch_digests", batch_digests),
            ("economically_qualified_slot_ids", economically_qualified_slot_ids),
            ("ranking_order", ranking_order),
            ("selection_bias_calculation_id", selection_bias_calculation_id),
            ("selection_bias_evidence_digests", selection_bias_evidence_digests),
            ("candidate_slot_id", candidate_slot_id),
            (
                "candidate_program_id",
                next(
                    (
                        slot.program_id
                        for slot in CANONICAL_SLOTS
                        if slot.slot_id == candidate_slot_id
                    ),
                    None,
                ),
            ),
            ("selection_bias_status", selection_bias_status),
            ("status", status),
            ("freeze_id", uuid5(_FINAL_FREEZE_NAMESPACE, canonical.decode("utf-8"))),
            ("fingerprint", sha256(canonical).hexdigest()),
            ("_seal", _seal),
        )
        for name, value in values:
            object.__setattr__(self, name, value)


def freeze_final_candidate_set(
    batches: Sequence[DevelopmentEvaluationBatch],
    *,
    _selection_bias_calculation: SelectionBiasCalculation | None = None,
) -> FinalCandidateFreeze:
    """Rank and freeze zero or one survivor from the complete verified population."""

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
    selection = (
        compute_selection_bias_evidence(population)
        if _selection_bias_calculation is None
        else _selection_bias_calculation
    )
    if (
        type(selection) is not SelectionBiasCalculation
        or selection.population_digest != _selection_bias_population_digest(population)
    ):
        raise AuthorizationUnavailableError(
            "final freeze requires DSR evidence bound to the complete batch population"
        )
    evidence_by_slot = {item.candidate_slot_id: item for item in selection.evidence}
    qualifications = tuple(
        qualify_development(batch, evidence_by_slot.get(batch.slot_id))
        for batch in population
    )
    economically_qualified = tuple(
        result.slot_id for result in qualifications if result.economically_qualified
    )
    ranking_order: tuple[UUID, ...] = ()
    if selection.status is SelectionBiasStatus.DSR_VERIFIED:
        ranking_order = rank_verified_candidate_population(population, selection)
        qualified_slot_ids = {
            result.slot_id for result in qualifications if result.qualified
        }
        candidate_slot_id = next(
            (slot_id for slot_id in ranking_order if slot_id in qualified_slot_ids),
            None,
        )
        status = (
            FinalFreezeStatus.ONE_CANDIDATE_FROZEN
            if candidate_slot_id is not None
            else FinalFreezeStatus.ZERO_CANDIDATES_NO_QUALIFIED_SURVIVOR
        )
    else:
        candidate_slot_id = None
        status = FinalFreezeStatus.ZERO_CANDIDATES_STATISTICAL_EVIDENCE_UNAVAILABLE
    batch_digests = tuple(batch.batch_digest for batch in population)
    return FinalCandidateFreeze(
        _seal=_FINAL_FREEZE_SEAL,
        batch_digests=batch_digests,
        economically_qualified_slot_ids=economically_qualified,
        ranking_order=ranking_order,
        selection_bias_status=selection.status,
        selection_bias_calculation_id=selection.calculation_id,
        selection_bias_evidence_digests=tuple(
            item.evidence_digest for item in selection.evidence
        ),
        candidate_slot_id=candidate_slot_id,
        status=status,
    )


class LaterPeriodKind(StrEnum):
    HOLDOUT_2024_2025 = "HOLDOUT_2024_2025"
    EXTENSION_2026_JAN_OCT = "EXTENSION_2026_JAN_OCT"


class LaterPeriodStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCOMPLETE = "INCOMPLETE"
    INVALID = "INVALID"


class LaterPeriodRejection(StrEnum):
    SESSION_POPULATION_INCOMPLETE = "SESSION_POPULATION_INCOMPLETE"
    CALENDAR_MONTH_POPULATION_INCOMPLETE = "CALENDAR_MONTH_POPULATION_INCOMPLETE"
    SESSION_TRADE_RECONCILIATION_INVALID = "SESSION_TRADE_RECONCILIATION_INVALID"
    HOLDOUT_NET_RETURN_NOT_POSITIVE = "HOLDOUT_NET_RETURN_NOT_POSITIVE"
    HOLDOUT_YEAR_RETURN_NOT_POSITIVE = "HOLDOUT_YEAR_RETURN_NOT_POSITIVE"
    HOLDOUT_PROFIT_FACTOR_NOT_ABOVE_1_10 = "HOLDOUT_PROFIT_FACTOR_NOT_ABOVE_1_10"
    HOLDOUT_MAX_DRAWDOWN_ABOVE_15_PERCENT = "HOLDOUT_MAX_DRAWDOWN_ABOVE_15_PERCENT"
    HOLDOUT_ACTIVE_SESSION_FRACTION_BELOW_30_PERCENT = (
        "HOLDOUT_ACTIVE_SESSION_FRACTION_BELOW_30_PERCENT"
    )
    HOLDOUT_AVERAGE_ROUND_TRIPS_BELOW_80 = "HOLDOUT_AVERAGE_ROUND_TRIPS_BELOW_80"
    HOLDOUT_POSITIVE_PNL_CONCENTRATION_ABOVE_40_PERCENT = (
        "HOLDOUT_POSITIVE_PNL_CONCENTRATION_ABOVE_40_PERCENT"
    )
    HOLDOUT_POSITIVE_PNL_UNAVAILABLE = "HOLDOUT_POSITIVE_PNL_UNAVAILABLE"
    EXTENSION_NET_RETURN_NOT_POSITIVE = "EXTENSION_NET_RETURN_NOT_POSITIVE"
    EXTENSION_PROFIT_FACTOR_NOT_ABOVE_1_05 = "EXTENSION_PROFIT_FACTOR_NOT_ABOVE_1_05"
    EXTENSION_MAX_DRAWDOWN_ABOVE_15_PERCENT = "EXTENSION_MAX_DRAWDOWN_ABOVE_15_PERCENT"
    EXTENSION_POSITIVE_MONTHS_BELOW_6 = "EXTENSION_POSITIVE_MONTHS_BELOW_6"
    EXTENSION_ACTIVE_SESSION_FRACTION_BELOW_30_PERCENT = (
        "EXTENSION_ACTIVE_SESSION_FRACTION_BELOW_30_PERCENT"
    )


class MutationAfterHoldoutVisibilityPolicy(StrEnum):
    PROHIBITED = "PROHIBITED"


@dataclass(frozen=True, slots=True)
class LaterPeriodSessionEvidence:
    """Pure one-session STRESS summary; it carries no source/authentication seal."""

    session_date: date
    net_return: Decimal
    net_trade_pnl: Decimal
    completed_round_trips: int

    def __post_init__(self) -> None:
        if type(self.session_date) is not date:
            raise TypeError("later-period session date must be date")
        if (
            type(self.net_return) is not Decimal
            or type(self.net_trade_pnl) is not Decimal
        ):
            raise TypeError("later-period returns and P&L must be Decimal")
        net_return = _decimal(self.net_return, "later-period net return")
        net_trade_pnl = _decimal(self.net_trade_pnl, "later-period session net P&L")
        if net_return <= Decimal(-1):
            raise ValueError("later-period session return must exceed -100%")
        if (
            type(self.completed_round_trips) is not int
            or not 0 <= self.completed_round_trips <= 2
        ):
            raise ValueError(
                "later-period session must have zero through two round trips"
            )
        object.__setattr__(self, "net_return", net_return)
        object.__setattr__(self, "net_trade_pnl", net_trade_pnl)


@dataclass(frozen=True, slots=True)
class LaterPeriodTradeEvidence:
    """Pure completed-trade net P&L used to recompute STRESS profit factor."""

    exit_session_date: date
    net_pnl: Decimal

    def __post_init__(self) -> None:
        if type(self.exit_session_date) is not date:
            raise TypeError("later-period trade exit date must be date")
        if type(self.net_pnl) is not Decimal:
            raise TypeError("later-period trade net P&L must be Decimal")
        object.__setattr__(
            self, "net_pnl", _decimal(self.net_pnl, "later-period trade net P&L")
        )


@dataclass(frozen=True, slots=True)
class LaterPeriodEvaluationEvidence:
    """Non-authorizing synthetic/pure input to sealed-period threshold contracts."""

    period: LaterPeriodKind
    freeze_id: UUID
    freeze_fingerprint: str
    candidate_slot_id: UUID
    economics_case: FillCostCase
    sessions: tuple[LaterPeriodSessionEvidence, ...]
    trades: tuple[LaterPeriodTradeEvidence, ...]

    def __post_init__(self) -> None:
        if type(self.period) is not LaterPeriodKind:
            raise TypeError("later-period kind is invalid")
        if type(self.freeze_id) is not UUID or type(self.candidate_slot_id) is not UUID:
            raise TypeError("later-period freeze and candidate identities must be UUID")
        if not _is_sha256(self.freeze_fingerprint):
            raise ValueError("later-period freeze fingerprint must be SHA-256")
        if type(self.economics_case) is not FillCostCase:
            raise TypeError("later-period economics case is invalid")
        if type(self.sessions) is not tuple or any(
            type(item) is not LaterPeriodSessionEvidence for item in self.sessions
        ):
            raise TypeError("later-period sessions must be immutable typed records")
        if type(self.trades) is not tuple or any(
            type(item) is not LaterPeriodTradeEvidence for item in self.trades
        ):
            raise TypeError("later-period trades must be immutable typed records")


@dataclass(frozen=True, slots=True, init=False)
class LaterPeriodQualification:
    """Pure threshold result; it is not an authenticated holdout or extension pass."""

    period: LaterPeriodKind
    status: LaterPeriodStatus
    rejection_reasons: tuple[LaterPeriodRejection, ...]
    freeze_id: UUID
    freeze_fingerprint: str
    candidate_slot_id: UUID
    expected_session_count: int
    observed_session_count: int
    expected_month_count: int
    observed_month_count: int
    calendar_partition_net_returns: tuple[tuple[int, Decimal], ...]
    aggregate_net_return: Decimal | None
    profit_factor: ProfitFactor | None
    max_drawdown: Decimal | None
    active_session_fraction: Decimal | None
    average_completed_round_trips_per_year: Decimal | None
    positive_month_count: int | None
    maximum_positive_month_pnl_share: Decimal | None
    input_digest: str
    qualification_id: UUID
    _seal: object

    def __init__(
        self,
        *,
        _seal: object = None,
        period: LaterPeriodKind,
        status: LaterPeriodStatus,
        rejection_reasons: tuple[LaterPeriodRejection, ...],
        freeze_id: UUID,
        freeze_fingerprint: str,
        candidate_slot_id: UUID,
        expected_session_count: int,
        observed_session_count: int,
        expected_month_count: int,
        observed_month_count: int,
        calendar_partition_net_returns: tuple[tuple[int, Decimal], ...],
        aggregate_net_return: Decimal | None,
        profit_factor: ProfitFactor | None,
        max_drawdown: Decimal | None,
        active_session_fraction: Decimal | None,
        average_completed_round_trips_per_year: Decimal | None,
        positive_month_count: int | None,
        maximum_positive_month_pnl_share: Decimal | None,
        input_digest: str,
    ) -> None:
        if _seal is not _LATER_PERIOD_QUALIFICATION_SEAL:
            raise AuthorizationUnavailableError(
                "later-period qualification must be computed by the "
                "pure policy function"
            )
        material = {
            "schema": "arch151-later-period-qualification/v1",
            "period": period.value,
            "status": status.value,
            "rejection_reasons": [item.value for item in rejection_reasons],
            "freeze_id": str(freeze_id),
            "freeze_fingerprint": freeze_fingerprint,
            "candidate_slot_id": str(candidate_slot_id),
            "expected_session_count": expected_session_count,
            "observed_session_count": observed_session_count,
            "expected_month_count": expected_month_count,
            "observed_month_count": observed_month_count,
            "calendar_partition_net_returns": [
                [year, _decimal_text(value)]
                for year, value in calendar_partition_net_returns
            ],
            "aggregate_net_return": (
                _decimal_text(aggregate_net_return)
                if aggregate_net_return is not None
                else None
            ),
            "profit_factor": (
                profit_factor.canonical_material()
                if profit_factor is not None
                else None
            ),
            "max_drawdown": (
                _decimal_text(max_drawdown) if max_drawdown is not None else None
            ),
            "active_session_fraction": (
                _decimal_text(active_session_fraction)
                if active_session_fraction is not None
                else None
            ),
            "average_completed_round_trips_per_year": (
                _decimal_text(average_completed_round_trips_per_year)
                if average_completed_round_trips_per_year is not None
                else None
            ),
            "positive_month_count": positive_month_count,
            "maximum_positive_month_pnl_share": (
                _decimal_text(maximum_positive_month_pnl_share)
                if maximum_positive_month_pnl_share is not None
                else None
            ),
            "input_digest": input_digest,
        }
        canonical = _canonical_json(material)
        if (
            type(period) is not LaterPeriodKind
            or type(status) is not LaterPeriodStatus
            or type(rejection_reasons) is not tuple
            or any(type(item) is not LaterPeriodRejection for item in rejection_reasons)
            or not _is_sha256(freeze_fingerprint)
            or not _is_sha256(input_digest)
            or (status is LaterPeriodStatus.PASS and rejection_reasons)
            or (status is not LaterPeriodStatus.PASS and not rejection_reasons)
        ):
            raise Arch151Error(
                "later-period qualification identity or status is invalid"
            )
        for name, value in (
            ("period", period),
            ("status", status),
            ("rejection_reasons", rejection_reasons),
            ("freeze_id", freeze_id),
            ("freeze_fingerprint", freeze_fingerprint),
            ("candidate_slot_id", candidate_slot_id),
            ("expected_session_count", expected_session_count),
            ("observed_session_count", observed_session_count),
            ("expected_month_count", expected_month_count),
            ("observed_month_count", observed_month_count),
            ("calendar_partition_net_returns", calendar_partition_net_returns),
            ("aggregate_net_return", aggregate_net_return),
            ("profit_factor", profit_factor),
            ("max_drawdown", max_drawdown),
            ("active_session_fraction", active_session_fraction),
            (
                "average_completed_round_trips_per_year",
                average_completed_round_trips_per_year,
            ),
            ("positive_month_count", positive_month_count),
            ("maximum_positive_month_pnl_share", maximum_positive_month_pnl_share),
            ("input_digest", input_digest),
            (
                "qualification_id",
                uuid5(
                    _LATER_PERIOD_QUALIFICATION_NAMESPACE,
                    canonical.decode("utf-8"),
                ),
            ),
            ("_seal", _seal),
        ):
            object.__setattr__(self, name, value)

    @property
    def passed(self) -> bool:
        return self.status is LaterPeriodStatus.PASS


def _later_period_bounds(period: LaterPeriodKind) -> tuple[date, date]:
    if period is LaterPeriodKind.HOLDOUT_2024_2025:
        return date(2024, 1, 1), date(2026, 1, 1)
    if period is LaterPeriodKind.EXTENSION_2026_JAN_OCT:
        return date(2026, 1, 1), date(2026, 11, 1)
    raise TypeError("later-period kind is invalid")


def _later_period_calendar(
    period: LaterPeriodKind,
) -> tuple[tuple[date, ...], tuple[tuple[int, int], ...]]:
    start, end_exclusive = _later_period_bounds(period)
    sessions: list[date] = []
    day = start
    while day < end_exclusive:
        schedule = _SESSION_AUTHORITY.schedule_for(day)
        if schedule is not None:
            if schedule.session_date != day or schedule.closes_at <= schedule.opens_at:
                raise AuthorizationUnavailableError(
                    "published later-period session schedule is inconsistent"
                )
            sessions.append(day)
        day += timedelta(days=1)
    months: list[tuple[int, int]] = []
    year, month = start.year, start.month
    while date(year, month, 1) < end_exclusive:
        months.append((year, month))
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    if not sessions or len(months) != (
        24 if period is LaterPeriodKind.HOLDOUT_2024_2025 else 10
    ):
        raise AuthorizationUnavailableError(
            "published XNYS later-period calendar is incomplete"
        )
    return tuple(sessions), tuple(months)


def _later_period_input_material(
    evidence: LaterPeriodEvaluationEvidence,
) -> dict[str, object]:
    return {
        "schema": "arch151-later-period-input/v1",
        "period": evidence.period.value,
        "freeze_id": str(evidence.freeze_id),
        "freeze_fingerprint": evidence.freeze_fingerprint,
        "candidate_slot_id": str(evidence.candidate_slot_id),
        "economics_case": evidence.economics_case.value,
        "sessions": [
            {
                "session_date": item.session_date.isoformat(),
                "net_return": _decimal_text(item.net_return),
                "net_trade_pnl": _decimal_text(item.net_trade_pnl),
                "completed_round_trips": item.completed_round_trips,
            }
            for item in evidence.sessions
        ],
        "trades": [
            {
                "exit_session_date": item.exit_session_date.isoformat(),
                "net_pnl": _decimal_text(item.net_pnl),
            }
            for item in evidence.trades
        ],
    }


def _new_later_period_qualification(
    *,
    evidence: LaterPeriodEvaluationEvidence,
    status: LaterPeriodStatus,
    rejection_reasons: tuple[LaterPeriodRejection, ...],
    expected_session_count: int,
    expected_month_count: int,
    calendar_partition_net_returns: tuple[tuple[int, Decimal], ...] = (),
    aggregate_net_return: Decimal | None = None,
    profit_factor: ProfitFactor | None = None,
    max_drawdown: Decimal | None = None,
    active_session_fraction: Decimal | None = None,
    average_completed_round_trips_per_year: Decimal | None = None,
    positive_month_count: int | None = None,
    maximum_positive_month_pnl_share: Decimal | None = None,
) -> LaterPeriodQualification:
    return LaterPeriodQualification(
        _seal=_LATER_PERIOD_QUALIFICATION_SEAL,
        period=evidence.period,
        status=status,
        rejection_reasons=rejection_reasons,
        freeze_id=evidence.freeze_id,
        freeze_fingerprint=evidence.freeze_fingerprint,
        candidate_slot_id=evidence.candidate_slot_id,
        expected_session_count=expected_session_count,
        observed_session_count=len(evidence.sessions),
        expected_month_count=expected_month_count,
        observed_month_count=len(
            {
                (item.session_date.year, item.session_date.month)
                for item in evidence.sessions
            }
        ),
        calendar_partition_net_returns=calendar_partition_net_returns,
        aggregate_net_return=aggregate_net_return,
        profit_factor=profit_factor,
        max_drawdown=max_drawdown,
        active_session_fraction=active_session_fraction,
        average_completed_round_trips_per_year=average_completed_round_trips_per_year,
        positive_month_count=positive_month_count,
        maximum_positive_month_pnl_share=maximum_positive_month_pnl_share,
        input_digest=sha256(
            _canonical_json(_later_period_input_material(evidence))
        ).hexdigest(),
    )


def _later_period_compound(returns: Sequence[Decimal]) -> Decimal:
    with localcontext(_DECIMAL_CONTEXT):
        equity = Decimal(1)
        for item in returns:
            equity *= Decimal(1) + item
        return equity - Decimal(1)


def _later_period_max_drawdown(returns: Sequence[Decimal]) -> Decimal:
    with localcontext(_DECIMAL_CONTEXT):
        equity = Decimal(1)
        peak = Decimal(1)
        worst = Decimal(0)
        for item in returns:
            equity *= Decimal(1) + item
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak
            if drawdown > worst:
                worst = drawdown
        return worst


def _profit_factor_exceeds(profit_factor: ProfitFactor, threshold: Decimal) -> bool:
    if profit_factor.state is ProfitFactorState.POSITIVE_INFINITY:
        return True
    return (
        profit_factor.state is ProfitFactorState.FINITE
        and profit_factor.finite_value is not None
        and profit_factor.finite_value > threshold
    )


def qualify_later_period(
    freeze: FinalCandidateFreeze,
    evidence: LaterPeriodEvaluationEvidence,
) -> LaterPeriodQualification:
    """Apply frozen holdout or extension thresholds to pure STRESS summaries.

    The returned PASS is diagnostic/qualifying data only. It is deliberately
    not an authenticated holdout result and cannot authorize later-period data.
    """

    if (
        type(freeze) is not FinalCandidateFreeze
        or getattr(freeze, "_seal", None) is not _FINAL_FREEZE_SEAL
        or freeze.status is not FinalFreezeStatus.ONE_CANDIDATE_FROZEN
        or freeze.candidate_slot_id is None
    ):
        raise AuthorizationUnavailableError(
            "later-period qualification requires the source-owned one-candidate freeze"
        )
    if type(evidence) is not LaterPeriodEvaluationEvidence:
        raise TypeError("later-period qualification evidence is invalid")
    if (
        evidence.freeze_id != freeze.freeze_id
        or evidence.freeze_fingerprint != freeze.fingerprint
        or evidence.candidate_slot_id != freeze.candidate_slot_id
    ):
        raise AuthorizationUnavailableError(
            "later-period evidence differs from the exact frozen candidate"
        )
    if evidence.economics_case is not FillCostCase.STRESS:
        raise Arch151Error("later-period qualification requires STRESS economics")
    expected_sessions, expected_months = _later_period_calendar(evidence.period)
    actual_sessions = tuple(item.session_date for item in evidence.sessions)
    actual_months = tuple(
        sorted(
            {
                (item.session_date.year, item.session_date.month)
                for item in evidence.sessions
            }
        )
    )
    incomplete_reasons: list[LaterPeriodRejection] = []
    if actual_sessions != expected_sessions:
        incomplete_reasons.append(LaterPeriodRejection.SESSION_POPULATION_INCOMPLETE)
    if actual_months != expected_months:
        incomplete_reasons.append(
            LaterPeriodRejection.CALENDAR_MONTH_POPULATION_INCOMPLETE
        )
    if incomplete_reasons:
        return _new_later_period_qualification(
            evidence=evidence,
            status=LaterPeriodStatus.INCOMPLETE,
            rejection_reasons=tuple(incomplete_reasons),
            expected_session_count=len(expected_sessions),
            expected_month_count=len(expected_months),
        )

    slot = next(
        item for item in CANONICAL_SLOTS if item.slot_id == freeze.candidate_slot_id
    )
    program = next(item for item in CANONICAL_PROGRAMS if item.key is slot.program_key)
    session_limit = 1 if program.family is StrategyFamily.OPENING_RANGE_RETEST else 2
    if any(item.completed_round_trips > session_limit for item in evidence.sessions):
        raise Arch151Error("later-period session exceeds the frozen entry limit")
    if any(
        left.exit_session_date > right.exit_session_date
        for left, right in zip(evidence.trades, evidence.trades[1:], strict=False)
    ):
        raise Arch151Error("later-period trades are not chronologically ordered")
    trades_by_date: dict[date, list[Decimal]] = defaultdict(list)
    for trade in evidence.trades:
        if trade.exit_session_date not in expected_sessions:
            raise Arch151Error(
                "later-period trade exit is outside the published calendar"
            )
        trades_by_date[trade.exit_session_date].append(trade.net_pnl)
    for session in evidence.sessions:
        values = trades_by_date.get(session.session_date, [])
        with localcontext(_DECIMAL_CONTEXT):
            session_pnl = sum(values, Decimal(0))
        if (
            len(values) != session.completed_round_trips
            or session_pnl != session.net_trade_pnl
        ):
            return _new_later_period_qualification(
                evidence=evidence,
                status=LaterPeriodStatus.INVALID,
                rejection_reasons=(
                    LaterPeriodRejection.SESSION_TRADE_RECONCILIATION_INVALID,
                ),
                expected_session_count=len(expected_sessions),
                expected_month_count=len(expected_months),
            )

    year_returns = tuple(
        (
            year,
            _later_period_compound(
                tuple(
                    item.net_return
                    for item in evidence.sessions
                    if item.session_date.year == year
                )
            ),
        )
        for year in sorted({item.session_date.year for item in evidence.sessions})
    )
    aggregate_return = _later_period_compound(
        tuple(item.net_return for item in evidence.sessions)
    )
    drawdown = _later_period_max_drawdown(
        tuple(item.net_return for item in evidence.sessions)
    )
    with localcontext(_DECIMAL_CONTEXT):
        positive_pnl = sum(
            (max(item.net_pnl, Decimal(0)) for item in evidence.trades), Decimal(0)
        )
        negative_pnl = sum(
            (max(-item.net_pnl, Decimal(0)) for item in evidence.trades), Decimal(0)
        )
    profit_factor = ProfitFactor.from_totals(positive_pnl, negative_pnl)
    active_count = sum(item.completed_round_trips > 0 for item in evidence.sessions)
    with localcontext(_DECIMAL_CONTEXT):
        active_fraction = Decimal(active_count) / Decimal(len(expected_sessions))
        average_round_trips_per_year = (
            Decimal(sum(item.completed_round_trips for item in evidence.sessions))
            / Decimal(2)
            if evidence.period is LaterPeriodKind.HOLDOUT_2024_2025
            else None
        )
    monthly_returns: dict[tuple[int, int], list[Decimal]] = {
        month: [] for month in expected_months
    }
    monthly_pnl: dict[tuple[int, int], Decimal] = {
        month: Decimal(0) for month in expected_months
    }
    for session in evidence.sessions:
        month = (session.session_date.year, session.session_date.month)
        monthly_returns[month].append(session.net_return)
    with localcontext(_DECIMAL_CONTEXT):
        for session in evidence.sessions:
            month = (session.session_date.year, session.session_date.month)
            monthly_pnl[month] += session.net_trade_pnl
    monthly_return_values = {
        month: _later_period_compound(values)
        for month, values in monthly_returns.items()
    }
    positive_month_count = sum(value > 0 for value in monthly_return_values.values())
    positive_month_pnl = {
        month: value for month, value in monthly_pnl.items() if value > 0
    }
    with localcontext(_DECIMAL_CONTEXT):
        total_positive_month_pnl = sum(positive_month_pnl.values(), Decimal(0))
        maximum_month_share = (
            max(positive_month_pnl.values()) / total_positive_month_pnl
            if total_positive_month_pnl > 0
            else None
        )
    reasons: list[LaterPeriodRejection] = []
    if evidence.period is LaterPeriodKind.HOLDOUT_2024_2025:
        if aggregate_return <= 0:
            reasons.append(LaterPeriodRejection.HOLDOUT_NET_RETURN_NOT_POSITIVE)
        if any(value <= 0 for _year, value in year_returns):
            reasons.append(LaterPeriodRejection.HOLDOUT_YEAR_RETURN_NOT_POSITIVE)
        if not _profit_factor_exceeds(profit_factor, Decimal("1.10")):
            reasons.append(LaterPeriodRejection.HOLDOUT_PROFIT_FACTOR_NOT_ABOVE_1_10)
        if drawdown > Decimal("0.15"):
            reasons.append(LaterPeriodRejection.HOLDOUT_MAX_DRAWDOWN_ABOVE_15_PERCENT)
        if active_fraction < Decimal("0.30"):
            reasons.append(
                LaterPeriodRejection.HOLDOUT_ACTIVE_SESSION_FRACTION_BELOW_30_PERCENT
            )
        if average_round_trips_per_year is None or average_round_trips_per_year < 80:
            reasons.append(LaterPeriodRejection.HOLDOUT_AVERAGE_ROUND_TRIPS_BELOW_80)
        if maximum_month_share is None:
            reasons.append(LaterPeriodRejection.HOLDOUT_POSITIVE_PNL_UNAVAILABLE)
        elif maximum_month_share > Decimal("0.40"):
            reasons.append(
                LaterPeriodRejection.HOLDOUT_POSITIVE_PNL_CONCENTRATION_ABOVE_40_PERCENT
            )
    else:
        if aggregate_return <= 0:
            reasons.append(LaterPeriodRejection.EXTENSION_NET_RETURN_NOT_POSITIVE)
        if not _profit_factor_exceeds(profit_factor, Decimal("1.05")):
            reasons.append(LaterPeriodRejection.EXTENSION_PROFIT_FACTOR_NOT_ABOVE_1_05)
        if drawdown > Decimal("0.15"):
            reasons.append(LaterPeriodRejection.EXTENSION_MAX_DRAWDOWN_ABOVE_15_PERCENT)
        if positive_month_count < 6:
            reasons.append(LaterPeriodRejection.EXTENSION_POSITIVE_MONTHS_BELOW_6)
        if active_fraction < Decimal("0.30"):
            reasons.append(
                LaterPeriodRejection.EXTENSION_ACTIVE_SESSION_FRACTION_BELOW_30_PERCENT
            )
    return _new_later_period_qualification(
        evidence=evidence,
        status=LaterPeriodStatus.FAIL if reasons else LaterPeriodStatus.PASS,
        rejection_reasons=tuple(reasons),
        expected_session_count=len(expected_sessions),
        expected_month_count=len(expected_months),
        calendar_partition_net_returns=year_returns,
        aggregate_net_return=aggregate_return,
        profit_factor=profit_factor,
        max_drawdown=drawdown,
        active_session_fraction=active_fraction,
        average_completed_round_trips_per_year=average_round_trips_per_year,
        positive_month_count=positive_month_count,
        maximum_positive_month_pnl_share=maximum_month_share,
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
        or development_evidence.freeze_fingerprint != freeze.fingerprint
        or development_evidence.source_manifest_id != freeze.source_manifest_id
        or development_evidence.batch_digests != freeze.batch_digests
        or development_evidence.record_count != 480
        or development_evidence.source_kind != "ARCH150_D1R_ACCEPTED"
        or development_evidence.selection_bias_calculation_id
        != freeze.selection_bias_calculation_id
        or development_evidence.selection_bias_evidence_digests
        != freeze.selection_bias_evidence_digests
        or development_evidence.selection_bias_ledger_id
        != SELECTION_BIAS_INPUT.ledger_id
        or development_evidence.selection_bias_effective_trial_count
        != SELECTION_BIAS_INPUT.effective_trial_count
        or selection_bias_evidence.candidate_slot_id != freeze.candidate_slot_id
        or selection_bias_evidence.population_digest
        != development_evidence.selection_bias_population_digest
        or selection_bias_evidence.ledger_id != SELECTION_BIAS_INPUT.ledger_id
        or selection_bias_evidence.effective_trial_count
        != SELECTION_BIAS_INPUT.effective_trial_count
        or selection_bias_evidence.evidence_id
        not in development_evidence.selection_bias_evidence_ids
        or selection_bias_evidence.evidence_digest
        not in development_evidence.selection_bias_evidence_digests
        or not _selection_bias_probability_meets_threshold(
            selection_bias_evidence.probability
        )
    ):
        raise AuthorizationUnavailableError(
            "holdout evidence does not authenticate the exact frozen candidate"
        )
    candidate_index = next(
        index
        for index, slot in enumerate(CANONICAL_SLOTS)
        if slot.slot_id == freeze.candidate_slot_id
    )
    if (
        development_evidence.selection_bias_evidence_ids[candidate_index]
        != selection_bias_evidence.evidence_id
        or development_evidence.selection_bias_evidence_digests[candidate_index]
        != selection_bias_evidence.evidence_digest
        or selection_bias_evidence.development_batch_digest
        != development_evidence.batch_digests[candidate_index]
    ):
        raise AuthorizationUnavailableError(
            "holdout DSR evidence is not bound to the frozen candidate batch"
        )
    return HoldoutAuthorization(
        _seal=_HOLDOUT_AUTHORIZATION_SEAL,
        freeze_id=freeze.freeze_id,
        freeze_fingerprint=freeze.fingerprint,
        candidate_slot_id=freeze.candidate_slot_id,
        development_evidence_digest=development_evidence.evidence_digest,
        development_report_id=development_evidence.report_id,
        development_report_sha256=development_evidence.report_sha256,
        source_revision_digest=development_evidence.source_revision_digest,
        selection_bias_evidence_id=selection_bias_evidence.evidence_id,
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
        or holdout_authorization.freeze_fingerprint != freeze.fingerprint
        or holdout_authorization.candidate_slot_id != freeze.candidate_slot_id
        or holdout_pass.freeze_id != freeze.freeze_id
        or holdout_pass.freeze_fingerprint != freeze.fingerprint
        or holdout_pass.candidate_slot_id != freeze.candidate_slot_id
        or holdout_pass.source_revision_digest
        != holdout_authorization.source_revision_digest
        or holdout_pass.conclusion is not HoldoutConclusion.PASS
    ):
        raise AuthorizationUnavailableError(
            "extension evidence is not bound to the exact frozen candidate"
        )
    return ExtensionAuthorization(
        _seal=_EXTENSION_AUTHORIZATION_SEAL,
        freeze_id=freeze.freeze_id,
        freeze_fingerprint=freeze.fingerprint,
        candidate_slot_id=freeze.candidate_slot_id,
        source_revision_digest=holdout_authorization.source_revision_digest,
        holdout_authorization_id=holdout_authorization.authorization_id,
        holdout_pass_digest=holdout_pass.evidence_digest,
    )


def classify_research_survivor(
    freeze: FinalCandidateFreeze,
    holdout_authorization: HoldoutAuthorization,
    holdout_pass: AuthenticatedHoldoutPass,
    extension_authorization: ExtensionAuthorization,
    extension_pass: AuthenticatedExtensionPass,
) -> ResearchSurvivorClassification:
    """Classify a full survivor after same-candidate holdout and extension PASS.

    The result is a research label only. It grants no runtime, order, Robinhood,
    or live authority.
    """

    if (
        type(freeze) is not FinalCandidateFreeze
        or getattr(freeze, "_seal", None) is not _FINAL_FREEZE_SEAL
        or freeze.status is not FinalFreezeStatus.ONE_CANDIDATE_FROZEN
        or freeze.candidate_slot_id is None
        or type(holdout_authorization) is not HoldoutAuthorization
        or getattr(holdout_authorization, "_seal", None)
        is not _HOLDOUT_AUTHORIZATION_SEAL
        or type(holdout_pass) is not AuthenticatedHoldoutPass
        or getattr(holdout_pass, "_seal", None) is not _AUTHENTICATED_HOLDOUT_PASS_SEAL
        or type(extension_authorization) is not ExtensionAuthorization
        or getattr(extension_authorization, "_seal", None)
        is not _EXTENSION_AUTHORIZATION_SEAL
        or type(extension_pass) is not AuthenticatedExtensionPass
        or getattr(extension_pass, "_seal", None)
        is not _AUTHENTICATED_EXTENSION_PASS_SEAL
    ):
        raise AuthorizationUnavailableError(
            "source-owned freeze and ordered authenticated "
            "holdout/extension evidence are required"
        )
    same_candidate = (
        holdout_authorization.freeze_id
        == holdout_pass.freeze_id
        == extension_authorization.freeze_id
        == extension_pass.freeze_id
        == freeze.freeze_id
        and holdout_authorization.freeze_fingerprint
        == holdout_pass.freeze_fingerprint
        == extension_authorization.freeze_fingerprint
        == extension_pass.freeze_fingerprint
        == freeze.fingerprint
        and holdout_authorization.candidate_slot_id
        == holdout_pass.candidate_slot_id
        == extension_authorization.candidate_slot_id
        == extension_pass.candidate_slot_id
        == freeze.candidate_slot_id
        and holdout_authorization.source_revision_digest
        == holdout_pass.source_revision_digest
        == extension_authorization.source_revision_digest
        == extension_pass.source_revision_digest
        and extension_authorization.holdout_pass_digest == holdout_pass.evidence_digest
        and extension_pass.extension_authorization_id
        == extension_authorization.authorization_id
        and extension_pass.holdout_pass_digest == holdout_pass.evidence_digest
        and holdout_pass.conclusion is HoldoutConclusion.PASS
    )
    if not same_candidate:
        raise AuthorizationUnavailableError(
            "survivor evidence differs from the exact frozen candidate or "
            "source revision"
        )
    material = {
        "schema": "arch151-research-survivor-classification/v1",
        "classification": (
            ResearchSurvivorClass.ARCH151_INTRADAY_RESEARCH_SURVIVOR.value
        ),
        "freeze_id": str(freeze.freeze_id),
        "freeze_fingerprint": freeze.fingerprint,
        "candidate_slot_id": str(freeze.candidate_slot_id),
        "source_revision_digest": holdout_authorization.source_revision_digest,
        "holdout_pass_digest": holdout_pass.evidence_digest,
        "extension_pass_digest": extension_pass.evidence_digest,
        "runtime_authority": False,
        "order_authority": False,
    }
    canonical = _canonical_json(material)
    return ResearchSurvivorClassification(
        _seal=_RESEARCH_SURVIVOR_CLASSIFICATION_SEAL,
        classification=ResearchSurvivorClass.ARCH151_INTRADAY_RESEARCH_SURVIVOR,
        freeze_id=freeze.freeze_id,
        freeze_fingerprint=freeze.fingerprint,
        candidate_slot_id=freeze.candidate_slot_id,
        source_revision_digest=holdout_authorization.source_revision_digest,
        holdout_pass_digest=holdout_pass.evidence_digest,
        extension_pass_digest=extension_pass.evidence_digest,
        classification_id=uuid5(
            _RESEARCH_SURVIVOR_NAMESPACE, canonical.decode("utf-8")
        ),
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
    "ARCH150_D1R_AFFECTED_SESSION_COUNT",
    "ARCH150_D1R_COMMON_MISSING_COUNT",
    "ARCH150_D1R_CUSTODY_ID",
    "ARCH150_D1R_CUSTODY_SHA256",
    "ARCH150_D1R_DATASET_ID",
    "ARCH150_D1R_DATASET_SHA256",
    "ARCH150_D1R_EVIDENCE_ID",
    "ARCH150_D1R_EVIDENCE_SHA256",
    "ARCH150_D1R_FULLY_MISSING_SESSION_COUNTS",
    "ARCH150_D1R_MISSING_COUNTS",
    "ARCH150_D1R_OBSERVED_COUNTS",
    "ARCH150_D1R_SCHEDULED_SLOTS_PER_SYMBOL",
    "ARCH150_D1R_UNION_MISSING_COUNT",
    "AGGREGATION_SCHEMA",
    "AuthenticatedDevelopmentEvidence",
    "AuthenticatedExtensionPass",
    "AuthenticatedHoldoutPass",
    "Arch150D1RSourceHistory",
    "Arch151Error",
    "Arch151Program",
    "AlignedCrossEtfBars",
    "AggregateBar",
    "AggregateStream",
    "AmbiguousIntraminuteRule",
    "AuthorizationUnavailableError",
    "BarResolution",
    "CAUSAL_EXECUTION_POLICY",
    "CausalIndicatorPoint",
    "CANONICAL_MANIFEST",
    "CANONICAL_PROGRAMS",
    "CANONICAL_SLOTS",
    "CausalExecutionPolicy",
    "CrossEtfPullbackParameters",
    "DevelopmentAggregate",
    "DevelopmentEvaluationBatch",
    "DevelopmentQualification",
    "DSR_OBSERVATION_COUNT",
    "DsrUnavailableReason",
    "DsrTrialDiagnostic",
    "DsrTrialStatus",
    "DEVELOPMENT_END",
    "DEVELOPMENT_START",
    "EVALUATION_ECONOMICS_ORDER",
    "EntryOpportunity",
    "EntryWindow",
    "ExtensionAuthorization",
    "FILL_COST_POLICIES",
    "FamilyABreakoutLevel",
    "FamilyAInitialRisk",
    "FamilyAMeasureScope",
    "FamilyACalibration",
    "FamilyASessionMeasure",
    "ProfitFactor",
    "ProfitFactorState",
    "PreparedCrossEtfFeatures",
    "PreparedSessionFeatures",
    "SessionFeatureCacheKey",
    "VerifiedSparseSession",
    "VwapMeanReversionSignal",
    "TrendPullbackSignal",
    "OpeningRangeRetestSignal",
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
    "LaterPeriodEvaluationEvidence",
    "LaterPeriodKind",
    "LaterPeriodQualification",
    "LaterPeriodRejection",
    "LaterPeriodSessionEvidence",
    "LaterPeriodStatus",
    "LaterPeriodTradeEvidence",
    "MutationAfterHoldoutVisibilityPolicy",
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
    "ResearchSurvivorClass",
    "ResearchSurvivorClassification",
    "SCORED_YEARS",
    "SELECTION_BIAS_INPUT",
    "SelectionBiasCalculation",
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
    "classify_research_survivor",
    "average_true_range",
    "calibrate_family_a",
    "calibrate_family_a_from_source_history",
    "canonical_manifest",
    "compute_selection_bias_evidence",
    "contiguous_aggregate_bars",
    "efficiency_ratio",
    "ema_series",
    "exact_cross_etf_confirmation",
    "family_a_breakout_level",
    "family_a_entry_signal",
    "family_a_current_measure_from_source_history",
    "family_a_historical_session_measure",
    "family_a_initial_risk",
    "family_a_regime_passes",
    "family_a_session_measure",
    "family_b_entry_signal",
    "family_c_entry_signal",
    "family_c_reversion_exit",
    "family_d_entry_signal",
    "freeze_final_candidate_set",
    "load_arch150_d1r_source_history",
    "normalized_vwap_deviation",
    "program_fingerprint",
    "program_from_bytes",
    "program_id",
    "program_to_bytes",
    "qualify_later_period",
    "prepare_cross_etf_session_features",
    "prepare_session_features",
    "qualify_development",
    "rank_verified_candidate_population",
    "rank_descriptive_economic_population",
    "rank_synthetic_candidate_population",
    "sample_standard_deviation",
    "structural_entry_opportunities",
    "vwap_deviation_sigma",
    "vwap_sigma_stop_distance",
)
