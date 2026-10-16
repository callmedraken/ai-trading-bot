"""Canonical offline history seeds for one deterministic paper strategy."""

from __future__ import annotations

import json
import re
from dataclasses import InitVar, dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from trading_bot.domain import Bar, Symbol
from trading_bot.market_calendar import MarketCalendarError, TradingSession
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    CalendarDescriptor,
    DailySnapshotBar,
    IdentifiedMarketCalendar,
    canonical_decimal,
)
from trading_bot.market_data.daily_snapshot_identity import canonical_timestamp
from trading_bot.strategies import MovingAverageCrossoverConfig

STRATEGY_HISTORY_SEED_SCHEMA = "strategy-history-seed/v1"
STRATEGY_HISTORY_SEED_IDENTITY_MATERIAL_VERSION = "strategy-history-seed-identity/v1"
STRATEGY_HISTORY_SEED_NAMESPACE = UUID("8a54eb24-cc17-5c15-9518-22b6f8af64e0")
MAX_STRATEGY_HISTORY_SEED_BYTES = 4 * 1024 * 1024
MAX_STRATEGY_HISTORY_SEED_BARS = 4096
MAX_STRATEGY_HISTORY_SEED_DECIMAL_CHARACTERS = 128

_SOURCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_TIMESTAMP_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{6})?Z$"
)
_DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_SEED_FIELDS = frozenset({"bars", "calendar", "schema", "seed_id", "source", "symbol"})
_CALENDAR_FIELDS = frozenset({"calendar_id", "exchange_timezone", "version"})
_SOURCE_FIELDS = frozenset({"authoritative", "classification", "source_id"})
_BAR_FIELDS = frozenset(
    {"close", "high", "low", "open", "session", "timestamp", "volume"}
)
_VERIFIED_SEED_AUTHORITY = object()


class StrategyHistorySeedError(Exception):
    """Base class for strict offline history-seed failures."""


class StrategyHistorySeedSerializationError(StrategyHistorySeedError, ValueError):
    """Raised when seed bytes are malformed, noncanonical, or out of bounds."""


class StrategyHistorySeedVerificationError(StrategyHistorySeedError, ValueError):
    """Raised when canonical seed evidence is invalid for one strategy target."""


class StrategyHistorySeedSourceClassification(StrEnum):
    """The only source authority classification supported by schema v1."""

    OFFLINE_SEED = "OFFLINE_SEED"


@dataclass(frozen=True, slots=True)
class StrategyHistorySeedSourceDescriptor:
    """One explicit non-authoritative offline source descriptor."""

    source_id: str
    classification: StrategyHistorySeedSourceClassification = (
        StrategyHistorySeedSourceClassification.OFFLINE_SEED
    )
    authoritative: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.source_id) is not str
            or _SOURCE_ID_PATTERN.fullmatch(self.source_id) is None
        ):
            raise StrategyHistorySeedVerificationError(
                "source_id must be bounded canonical ASCII identifier text"
            )
        if (
            type(self.classification) is not StrategyHistorySeedSourceClassification
            or self.classification
            is not StrategyHistorySeedSourceClassification.OFFLINE_SEED
        ):
            raise StrategyHistorySeedVerificationError(
                "source classification must be OFFLINE_SEED"
            )
        if type(self.authoritative) is not bool or self.authoritative:
            raise StrategyHistorySeedVerificationError(
                "offline history source must be explicitly non-authoritative"
            )


@dataclass(frozen=True, slots=True)
class StrategyHistorySeed:
    """One-symbol ordered history with deterministic semantic identity."""

    seed_id: UUID
    symbol: Symbol
    calendar: CalendarDescriptor
    source: StrategyHistorySeedSourceDescriptor
    bars: tuple[DailySnapshotBar, ...]
    schema: str = STRATEGY_HISTORY_SEED_SCHEMA

    def __post_init__(self) -> None:
        if type(self.seed_id) is not UUID:
            raise StrategyHistorySeedVerificationError("seed_id must be an exact UUID")
        if type(self.symbol) is not Symbol:
            raise StrategyHistorySeedVerificationError("symbol must be an exact Symbol")
        if self.calendar != XNYS_CALENDAR_DESCRIPTOR:
            raise StrategyHistorySeedVerificationError(
                "calendar must be the exact supported XNYS descriptor"
            )
        if type(self.source) is not StrategyHistorySeedSourceDescriptor:
            raise StrategyHistorySeedVerificationError(
                "source must be one exact offline source descriptor"
            )
        if type(self.schema) is not str or self.schema != STRATEGY_HISTORY_SEED_SCHEMA:
            raise StrategyHistorySeedVerificationError(
                "schema must be strategy-history-seed/v1"
            )
        try:
            bars = tuple(self.bars)
        except TypeError as error:
            raise StrategyHistorySeedVerificationError(
                "bars must be iterable"
            ) from error
        if not 1 <= len(bars) <= MAX_STRATEGY_HISTORY_SEED_BARS:
            raise StrategyHistorySeedVerificationError(
                "bars must contain between 1 and 4096 values"
            )
        previous: date | None = None
        for index, item in enumerate(bars):
            if type(item) is not DailySnapshotBar:
                raise StrategyHistorySeedVerificationError(
                    f"bars[{index}] must be an exact DailySnapshotBar"
                )
            if item.bar.symbol != self.symbol:
                raise StrategyHistorySeedVerificationError(
                    "every seed bar must match the one declared symbol"
                )
            session_date = item.session.session_date
            if previous is not None and session_date <= previous:
                raise StrategyHistorySeedVerificationError(
                    "seed sessions must be unique and strictly increasing"
                )
            if not _timestamp_matches_session(
                item.bar.timestamp, item.session, self.calendar
            ):
                raise StrategyHistorySeedVerificationError(
                    "seed bar timestamp must name its exchange session"
                )
            previous = session_date
        object.__setattr__(self, "bars", bars)
        if self.seed_id != _seed_id(self.symbol, self.calendar, self.source, bars):
            raise StrategyHistorySeedVerificationError(
                "seed_id does not match canonical semantic seed material"
            )


@dataclass(frozen=True, slots=True)
class VerifiedStrategyHistorySeed:
    """Immutable evidence issued only after target-specific offline verification."""

    seed: StrategyHistorySeed
    artifact_sha256: str
    artifact_byte_length: int
    target_session: TradingSession
    strategy_config: MovingAverageCrossoverConfig
    _authority: InitVar[object]

    def __post_init__(self, _authority: object) -> None:
        if _authority is not _VERIFIED_SEED_AUTHORITY:
            raise StrategyHistorySeedVerificationError(
                "verified seed evidence must come from strict byte verification"
            )
        if type(self.seed) is not StrategyHistorySeed:
            raise StrategyHistorySeedVerificationError("seed evidence is invalid")
        if (
            type(self.artifact_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", self.artifact_sha256) is None
            or type(self.artifact_byte_length) is not int
            or self.artifact_byte_length <= 0
        ):
            raise StrategyHistorySeedVerificationError(
                "seed artifact SHA-256 or byte length is invalid"
            )
        if type(self.target_session) is not TradingSession:
            raise StrategyHistorySeedVerificationError("target_session is invalid")
        if type(self.strategy_config) is not MovingAverageCrossoverConfig:
            raise StrategyHistorySeedVerificationError("strategy_config is invalid")


def create_strategy_history_seed(
    *,
    symbol: Symbol,
    source: StrategyHistorySeedSourceDescriptor,
    bars: tuple[DailySnapshotBar, ...],
) -> StrategyHistorySeed:
    """Create one canonical semantic seed without reading files or clocks."""
    retained = tuple(bars)
    return StrategyHistorySeed(
        _seed_id(symbol, XNYS_CALENDAR_DESCRIPTOR, source, retained),
        symbol,
        XNYS_CALENDAR_DESCRIPTOR,
        source,
        retained,
    )


def serialize_strategy_history_seed(seed: StrategyHistorySeed) -> bytes:
    """Serialize one seed into strict canonical UTF-8 JSON bytes."""
    if type(seed) is not StrategyHistorySeed:
        raise StrategyHistorySeedSerializationError(
            "seed must be an exact StrategyHistorySeed"
        )
    payload = _canonical_json_bytes(_seed_tree(seed))
    if len(payload) > MAX_STRATEGY_HISTORY_SEED_BYTES:
        raise StrategyHistorySeedSerializationError(
            "serialized seed exceeds the 4 MiB limit"
        )
    return payload


def parse_strategy_history_seed(payload: bytes) -> StrategyHistorySeed:
    """Strictly parse one bounded canonical history-seed artifact."""
    value = _load_json(payload)
    root = _object(value, _SEED_FIELDS, "root")
    calendar_raw = _object(root["calendar"], _CALENDAR_FIELDS, "calendar")
    source_raw = _object(root["source"], _SOURCE_FIELDS, "source")
    bars_raw = _array(root["bars"], "bars", MAX_STRATEGY_HISTORY_SEED_BARS)
    try:
        calendar = CalendarDescriptor(
            _string(calendar_raw["calendar_id"], "calendar.calendar_id"),
            _string(calendar_raw["version"], "calendar.version"),
            _string(calendar_raw["exchange_timezone"], "calendar.exchange_timezone"),
        )
        source = StrategyHistorySeedSourceDescriptor(
            _string(source_raw["source_id"], "source.source_id"),
            _enum(
                source_raw["classification"],
                StrategyHistorySeedSourceClassification,
                "source.classification",
            ),
            _bool(source_raw["authoritative"], "source.authoritative"),
        )
        symbol = _symbol(root["symbol"], "symbol")
        seed = StrategyHistorySeed(
            _uuid(root["seed_id"], "seed_id"),
            symbol,
            calendar,
            source,
            tuple(_bar(item, index, symbol) for index, item in enumerate(bars_raw)),
            _string(root["schema"], "schema"),
        )
    except StrategyHistorySeedError:
        raise
    except (TypeError, ValueError) as error:
        raise StrategyHistorySeedSerializationError(
            "seed model does not reconcile"
        ) from error
    if serialize_strategy_history_seed(seed) != payload:
        raise StrategyHistorySeedSerializationError(
            "seed bytes are not the canonical representation"
        )
    return seed


def verify_strategy_history_seed(
    payload: bytes,
    *,
    expected_symbol: Symbol,
    target_session: TradingSession,
    strategy_config: MovingAverageCrossoverConfig,
    calendar: IdentifiedMarketCalendar,
) -> VerifiedStrategyHistorySeed:
    """Verify canonical bytes and target-specific XNYS history sufficiency."""
    if type(expected_symbol) is not Symbol:
        raise StrategyHistorySeedVerificationError(
            "expected_symbol must be an exact Symbol"
        )
    if type(target_session) is not TradingSession:
        raise StrategyHistorySeedVerificationError(
            "target_session must be an exact TradingSession"
        )
    if type(strategy_config) is not MovingAverageCrossoverConfig:
        raise StrategyHistorySeedVerificationError(
            "strategy_config must be an exact MovingAverageCrossoverConfig"
        )
    if getattr(calendar, "descriptor", None) != XNYS_CALENDAR_DESCRIPTOR:
        raise StrategyHistorySeedVerificationError(
            "calendar must expose the exact XNYS descriptor"
        )
    seed = parse_strategy_history_seed(payload)
    if seed.symbol != expected_symbol:
        raise StrategyHistorySeedVerificationError(
            "seed symbol does not match the selected snapshot symbol"
        )
    bars = seed.bars
    if len(bars) < strategy_config.long_window:
        raise StrategyHistorySeedVerificationError(
            "seed does not provide the configured long-window history"
        )
    try:
        for item in bars:
            moment = _session_moment(item.session, seed.calendar)
            if not calendar.is_trading_session(moment):
                raise StrategyHistorySeedVerificationError(
                    "seed contains a non-modeled XNYS session"
                )
            if item.session >= target_session:
                raise StrategyHistorySeedVerificationError(
                    "seed sessions must strictly precede the selected target session"
                )
        target_moment = _session_moment(target_session, seed.calendar)
        if not calendar.is_trading_session(target_moment):
            raise StrategyHistorySeedVerificationError(
                "selected target session is not a modeled XNYS session"
            )
        expected_predecessor = calendar.previous_session(target_moment)
        if bars[-1].session != expected_predecessor:
            raise StrategyHistorySeedVerificationError(
                "final seed session must immediately precede the selected target"
            )
        suffix = bars[-strategy_config.long_window :]
        for previous, current in zip(suffix, suffix[1:], strict=False):
            expected_next = calendar.next_session(
                _session_moment(previous.session, seed.calendar)
            )
            if current.session != expected_next:
                raise StrategyHistorySeedVerificationError(
                    "configured long-window suffix must contain consecutive "
                    "XNYS sessions"
                )
    except (MarketCalendarError, TypeError, ValueError) as error:
        if isinstance(error, StrategyHistorySeedVerificationError):
            raise
        raise StrategyHistorySeedVerificationError(
            "seed temporal validation failed"
        ) from error
    if len(bars) + 1 < strategy_config.long_window + 1:
        raise StrategyHistorySeedVerificationError(
            "strategy history remains insufficient after appending the target bar"
        )
    return VerifiedStrategyHistorySeed(
        seed,
        sha256(payload).hexdigest(),
        len(payload),
        target_session,
        strategy_config,
        _VERIFIED_SEED_AUTHORITY,
    )


def _seed_id(
    symbol: Symbol,
    calendar: CalendarDescriptor,
    source: StrategyHistorySeedSourceDescriptor,
    bars: tuple[DailySnapshotBar, ...],
) -> UUID:
    parts = [
        STRATEGY_HISTORY_SEED_IDENTITY_MATERIAL_VERSION,
        STRATEGY_HISTORY_SEED_SCHEMA,
        str(symbol),
        calendar.calendar_id,
        calendar.version,
        calendar.exchange_timezone,
        source.source_id,
        source.classification.value,
        "false",
        str(len(bars)),
    ]
    for item in bars:
        bar = item.bar
        parts.extend(
            (
                item.session.session_date.isoformat(),
                canonical_timestamp(bar.timestamp),
                canonical_decimal(bar.open),
                canonical_decimal(bar.high),
                canonical_decimal(bar.low),
                canonical_decimal(bar.close),
                str(bar.volume),
            )
        )
    return uuid5(STRATEGY_HISTORY_SEED_NAMESPACE, _framed_material(tuple(parts)))


def _seed_tree(seed: StrategyHistorySeed) -> dict[str, Any]:
    return {
        "bars": [
            {
                "close": canonical_decimal(item.bar.close),
                "high": canonical_decimal(item.bar.high),
                "low": canonical_decimal(item.bar.low),
                "open": canonical_decimal(item.bar.open),
                "session": item.session.session_date.isoformat(),
                "timestamp": canonical_timestamp(item.bar.timestamp),
                "volume": item.bar.volume,
            }
            for item in seed.bars
        ],
        "calendar": {
            "calendar_id": seed.calendar.calendar_id,
            "exchange_timezone": seed.calendar.exchange_timezone,
            "version": seed.calendar.version,
        },
        "schema": seed.schema,
        "seed_id": str(seed.seed_id),
        "source": {
            "authoritative": seed.source.authoritative,
            "classification": seed.source.classification.value,
            "source_id": seed.source.source_id,
        },
        "symbol": str(seed.symbol),
    }


def _bar(value: object, index: int, symbol: Symbol) -> DailySnapshotBar:
    path = f"bars[{index}]"
    raw = _object(value, _BAR_FIELDS, path)
    session = TradingSession(_date(raw["session"], f"{path}.session"))
    return DailySnapshotBar(
        session,
        Bar(
            symbol,
            _timestamp(raw["timestamp"], f"{path}.timestamp"),
            _positive_decimal(raw["open"], f"{path}.open"),
            _positive_decimal(raw["high"], f"{path}.high"),
            _positive_decimal(raw["low"], f"{path}.low"),
            _positive_decimal(raw["close"], f"{path}.close"),
            _nonnegative_int(raw["volume"], f"{path}.volume"),
        ),
    )


def _canonical_json_bytes(tree: object) -> bytes:
    try:
        rendered = json.dumps(
            tree,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return (rendered + "\n").encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as error:
        raise StrategyHistorySeedSerializationError(
            "seed cannot be serialized as canonical JSON"
        ) from error


def _load_json(payload: bytes) -> object:
    if type(payload) is not bytes:
        raise StrategyHistorySeedSerializationError("payload must be exact bytes")
    if len(payload) > MAX_STRATEGY_HISTORY_SEED_BYTES:
        raise StrategyHistorySeedSerializationError("seed payload exceeds byte bound")
    if payload.startswith(b"\xef\xbb\xbf"):
        raise StrategyHistorySeedSerializationError("UTF-8 BOM is not permitted")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise StrategyHistorySeedSerializationError(
            "seed payload is not valid UTF-8"
        ) from error
    if not text.endswith("\n") or text.endswith("\n\n"):
        raise StrategyHistorySeedSerializationError(
            "seed JSON must have exactly one final newline"
        )
    core = text[:-1]
    if not core or core != core.strip():
        raise StrategyHistorySeedSerializationError(
            "seed JSON has leading or trailing whitespace"
        )
    try:
        return json.loads(
            core,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as error:
        raise StrategyHistorySeedSerializationError(
            f"seed JSON is invalid at line {error.lineno} column {error.colno}"
        ) from error


def _object(value: object, fields: frozenset[str], path: str) -> dict[str, object]:
    if type(value) is not dict:
        raise StrategyHistorySeedSerializationError(f"{path}: expected object")
    actual = frozenset(value)
    if actual != fields:
        missing = sorted(fields - actual)
        unknown = sorted(actual - fields)
        detail = []
        if missing:
            detail.append(f"missing fields: {', '.join(missing)}")
        if unknown:
            detail.append(f"unknown fields: {', '.join(unknown)}")
        raise StrategyHistorySeedSerializationError(f"{path}: {'; '.join(detail)}")
    return value


def _array(value: object, path: str, maximum: int) -> list[object]:
    if type(value) is not list:
        raise StrategyHistorySeedSerializationError(f"{path}: expected array")
    if not 1 <= len(value) <= maximum:
        raise StrategyHistorySeedSerializationError(f"{path}: array exceeds bound")
    return value


def _string(value: object, path: str) -> str:
    if type(value) is not str:
        raise StrategyHistorySeedSerializationError(f"{path}: expected string")
    return value


def _bool(value: object, path: str) -> bool:
    if type(value) is not bool:
        raise StrategyHistorySeedSerializationError(f"{path}: expected bool")
    return value


def _uuid(value: object, path: str) -> UUID:
    text = _string(value, path)
    try:
        parsed = UUID(text)
    except ValueError as error:
        raise StrategyHistorySeedSerializationError(
            f"{path}: expected canonical UUID"
        ) from error
    if str(parsed) != text:
        raise StrategyHistorySeedSerializationError(f"{path}: UUID is not canonical")
    return parsed


def _symbol(value: object, path: str) -> Symbol:
    text = _string(value, path)
    try:
        parsed = Symbol(text)
    except (TypeError, ValueError) as error:
        raise StrategyHistorySeedSerializationError(
            f"{path}: invalid symbol"
        ) from error
    if str(parsed) != text:
        raise StrategyHistorySeedSerializationError(f"{path}: symbol is not canonical")
    return parsed


def _date(value: object, path: str) -> date:
    text = _string(value, path)
    if _DATE_PATTERN.fullmatch(text) is None:
        raise StrategyHistorySeedSerializationError(f"{path}: invalid date")
    try:
        parsed = date.fromisoformat(text)
    except ValueError as error:
        raise StrategyHistorySeedSerializationError(f"{path}: invalid date") from error
    if parsed.isoformat() != text:
        raise StrategyHistorySeedSerializationError(f"{path}: date is not canonical")
    return parsed


def _timestamp(value: object, path: str) -> datetime:
    text = _string(value, path)
    if _TIMESTAMP_PATTERN.fullmatch(text) is None:
        raise StrategyHistorySeedSerializationError(f"{path}: invalid timestamp")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00").astimezone(UTC)
    except ValueError as error:
        raise StrategyHistorySeedSerializationError(
            f"{path}: invalid timestamp"
        ) from error
    if canonical_timestamp(parsed) != text:
        raise StrategyHistorySeedSerializationError(
            f"{path}: timestamp is not canonical"
        )
    return parsed


def _positive_decimal(value: object, path: str) -> Decimal:
    text = _string(value, path)
    if not 1 <= len(text) <= MAX_STRATEGY_HISTORY_SEED_DECIMAL_CHARACTERS:
        raise StrategyHistorySeedSerializationError(f"{path}: Decimal exceeds bound")
    try:
        parsed = Decimal(text)
    except InvalidOperation as error:
        raise StrategyHistorySeedSerializationError(
            f"{path}: invalid Decimal"
        ) from error
    if not parsed.is_finite() or parsed <= 0 or canonical_decimal(parsed) != text:
        raise StrategyHistorySeedSerializationError(
            f"{path}: expected canonical positive Decimal"
        )
    return parsed


def _nonnegative_int(value: object, path: str) -> int:
    if type(value) is not int or not 0 <= value <= 2**63 - 1:
        raise StrategyHistorySeedSerializationError(
            f"{path}: expected bounded nonnegative integer"
        )
    return value


def _enum(value: object, enum_type: type[StrEnum], path: str) -> Any:
    text = _string(value, path)
    try:
        return enum_type(text)
    except ValueError as error:
        raise StrategyHistorySeedSerializationError(
            f"{path}: unsupported value"
        ) from error


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise StrategyHistorySeedSerializationError(
                f"duplicate JSON object key: {key}"
            )
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise StrategyHistorySeedSerializationError(
        f"nonstandard JSON constant is not permitted: {value}"
    )


def _timestamp_matches_session(
    value: datetime,
    session: TradingSession,
    descriptor: CalendarDescriptor,
) -> bool:
    try:
        return value.astimezone(ZoneInfo(descriptor.exchange_timezone)).date() == (
            session.session_date
        )
    except ZoneInfoNotFoundError as error:
        raise StrategyHistorySeedVerificationError(
            "calendar exchange timezone is unavailable"
        ) from error


def _session_moment(
    session: TradingSession,
    descriptor: CalendarDescriptor,
) -> datetime:
    try:
        zone = ZoneInfo(descriptor.exchange_timezone)
    except ZoneInfoNotFoundError as error:
        raise StrategyHistorySeedVerificationError(
            "calendar exchange timezone is unavailable"
        ) from error
    return datetime.combine(session.session_date, time(12), zone)


def _framed_material(parts: tuple[str, ...]) -> str:
    return "".join(f"{len(part.encode('utf-8'))}:{part}" for part in parts)
