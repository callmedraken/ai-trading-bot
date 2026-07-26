"""Strict local configuration for one audited daily-snapshot capture."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

from trading_bot.cli.exceptions import (
    DailySnapshotConfigJsonError,
    DailySnapshotConfigReadError,
    DailySnapshotConfigValidationError,
)
from trading_bot.domain import Symbol
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    AdjustmentType,
    CalendarDescriptor,
    DailySnapshotCaptureRequest,
    ProviderDescriptor,
    Timeframe,
)
from trading_bot.market_data.alpaca_daily_snapshot import (
    ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
)

DAILY_SNAPSHOT_CAPTURE_CONFIG_SCHEMA_VERSION = 1
MAX_DAILY_SNAPSHOT_CONFIG_BYTES = 64 * 1024

_ROOT_FIELDS = frozenset(
    {
        "adjustment",
        "calendar",
        "provider",
        "request_id",
        "schema_version",
        "symbols",
        "timeframe",
    }
)
_CALENDAR_FIELDS = frozenset({"calendar_id", "exchange_timezone", "version"})
_PROVIDER_FIELDS = frozenset({"adapter_version", "feed", "operation", "provider_id"})


@dataclass(frozen=True, slots=True)
class DailySnapshotCaptureConfig:
    """Validated nonsecret configuration for the fixed capture contract."""

    request_id: UUID
    symbols: tuple[Symbol, ...]
    calendar: CalendarDescriptor
    timeframe: Timeframe
    adjustment: AdjustmentType
    provider: ProviderDescriptor
    schema_version: int = DAILY_SNAPSHOT_CAPTURE_CONFIG_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.request_id) is not UUID:
            raise DailySnapshotConfigValidationError("request_id must be a UUID")
        symbols = tuple(self.symbols)
        if not symbols or any(type(symbol) is not Symbol for symbol in symbols):
            raise DailySnapshotConfigValidationError(
                "symbols must contain Symbol values"
            )
        if len(symbols) > 100 or len(set(symbols)) != len(symbols):
            raise DailySnapshotConfigValidationError(
                "symbols must contain 1-100 unique values"
            )
        if self.calendar != XNYS_CALENDAR_DESCRIPTOR:
            raise DailySnapshotConfigValidationError(
                "calendar must be the exact supported XNYS descriptor"
            )
        if self.timeframe is not Timeframe.DAY_1:
            raise DailySnapshotConfigValidationError("timeframe must be 1D")
        if self.adjustment is not AdjustmentType.RAW:
            raise DailySnapshotConfigValidationError("adjustment must be RAW")
        if self.provider != ALPACA_DAILY_SNAPSHOT_DESCRIPTOR:
            raise DailySnapshotConfigValidationError(
                "provider must be the exact supported Alpaca descriptor"
            )
        if (
            type(self.schema_version) is not int
            or self.schema_version != DAILY_SNAPSHOT_CAPTURE_CONFIG_SCHEMA_VERSION
        ):
            raise DailySnapshotConfigValidationError("schema_version must be 1")
        object.__setattr__(self, "symbols", symbols)

    def capture_request(self, requested_at: datetime) -> DailySnapshotCaptureRequest:
        """Bind one runtime request timestamp to this deterministic intent."""
        return DailySnapshotCaptureRequest(
            request_id=self.request_id,
            symbols=self.symbols,
            requested_at=requested_at,
            calendar=self.calendar,
            timeframe=self.timeframe,
            adjustment=self.adjustment,
        )


def load_daily_snapshot_capture_config(path: Path) -> DailySnapshotCaptureConfig:
    """Read and strictly validate one bounded version-one JSON configuration."""
    if not isinstance(path, Path):
        raise DailySnapshotConfigReadError("config path must be a Path")
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise DailySnapshotConfigReadError(
            "daily snapshot configuration cannot be read"
        ) from error
    if len(payload) > MAX_DAILY_SNAPSHOT_CONFIG_BYTES:
        raise DailySnapshotConfigReadError(
            "daily snapshot configuration exceeds 65536 bytes"
        )
    if payload.startswith(b"\xef\xbb\xbf"):
        raise DailySnapshotConfigJsonError(
            "daily snapshot configuration must not contain a UTF-8 BOM"
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise DailySnapshotConfigJsonError(
            "daily snapshot configuration is not valid UTF-8"
        ) from error
    try:
        root = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, DailySnapshotConfigJsonError) as error:
        raise DailySnapshotConfigJsonError(
            "daily snapshot configuration is not valid strict JSON"
        ) from error
    return _parse_config(root)


def _parse_config(root: object) -> DailySnapshotCaptureConfig:
    value = _exact_object(root, _ROOT_FIELDS, "configuration")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise DailySnapshotConfigValidationError("schema_version must be 1")
    request_id = _canonical_uuid(value["request_id"])
    raw_symbols = value["symbols"]
    if type(raw_symbols) is not list:
        raise DailySnapshotConfigValidationError("symbols must be an array")
    symbols: list[Symbol] = []
    for raw_symbol in raw_symbols:
        if type(raw_symbol) is not str:
            raise DailySnapshotConfigValidationError("symbols must contain strings")
        try:
            symbol = Symbol(raw_symbol)
        except (TypeError, ValueError) as error:
            raise DailySnapshotConfigValidationError(
                "symbols contain an invalid value"
            ) from error
        if str(symbol) != raw_symbol:
            raise DailySnapshotConfigValidationError("symbols must use canonical text")
        symbols.append(symbol)

    calendar_value = _exact_object(
        value["calendar"],
        _CALENDAR_FIELDS,
        "calendar",
    )
    provider_value = _exact_object(
        value["provider"],
        _PROVIDER_FIELDS,
        "provider",
    )
    try:
        calendar = CalendarDescriptor(
            calendar_id=_exact_string(
                calendar_value["calendar_id"],
                "calendar.calendar_id",
            ),
            version=_exact_string(
                calendar_value["version"],
                "calendar.version",
            ),
            exchange_timezone=_exact_string(
                calendar_value["exchange_timezone"],
                "calendar.exchange_timezone",
            ),
        )
        provider = ProviderDescriptor(
            provider_id=_exact_string(
                provider_value["provider_id"],
                "provider.provider_id",
            ),
            adapter_version=_exact_int(
                provider_value["adapter_version"],
                "provider.adapter_version",
            ),
            operation=_exact_string(
                provider_value["operation"],
                "provider.operation",
            ),
            feed=_exact_string(provider_value["feed"], "provider.feed"),
        )
        timeframe = Timeframe(_exact_string(value["timeframe"], "timeframe"))
        adjustment = AdjustmentType(_exact_string(value["adjustment"], "adjustment"))
        return DailySnapshotCaptureConfig(
            request_id=request_id,
            symbols=tuple(symbols),
            calendar=calendar,
            timeframe=timeframe,
            adjustment=adjustment,
            provider=provider,
        )
    except DailySnapshotConfigValidationError:
        raise
    except (TypeError, ValueError) as error:
        raise DailySnapshotConfigValidationError(
            "configuration contains an unsupported domain value"
        ) from error


def _exact_object(
    value: object,
    fields: frozenset[str],
    path: str,
) -> dict[str, object]:
    if type(value) is not dict or frozenset(value) != fields:
        raise DailySnapshotConfigValidationError(
            f"{path} must contain exactly the supported fields"
        )
    return value


def _exact_string(value: object, path: str) -> str:
    if type(value) is not str:
        raise DailySnapshotConfigValidationError(f"{path} must be a string")
    return value


def _exact_int(value: object, path: str) -> int:
    if type(value) is not int:
        raise DailySnapshotConfigValidationError(f"{path} must be an integer")
    return value


def _canonical_uuid(value: object) -> UUID:
    if type(value) is not str:
        raise DailySnapshotConfigValidationError("request_id must be a string")
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise DailySnapshotConfigValidationError(
            "request_id must be a canonical UUID"
        ) from error
    if str(parsed) != value:
        raise DailySnapshotConfigValidationError("request_id must be a canonical UUID")
    return parsed


def _reject_duplicate_keys(pairs):  # type: ignore[no-untyped-def]
    result = {}
    for key, value in pairs:
        if key in result:
            raise DailySnapshotConfigJsonError(
                "daily snapshot configuration contains a duplicate key"
            )
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise DailySnapshotConfigJsonError(
        f"nonstandard JSON constant is not permitted: {value}"
    )
