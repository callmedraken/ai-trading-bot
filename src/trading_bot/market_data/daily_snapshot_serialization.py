"""Canonical UTF-8 JSON serialization for daily market-data snapshots."""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from trading_bot.domain import Bar, Symbol
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data.daily_snapshot_identity import (
    canonical_decimal,
    canonical_timestamp,
)
from trading_bot.market_data.daily_snapshot_models import (
    DAILY_SNAPSHOT_PROTOCOL_VERSION,
    DAILY_SNAPSHOT_SCHEMA_VERSION,
    CalendarDescriptor,
    CanonicalBarsEvidence,
    DailyMarketDataSnapshot,
    DailySnapshotBar,
    DailySnapshotCaptureRequest,
    DailySnapshotFreshness,
    ProviderDescriptor,
    SnapshotAuditEvidence,
    SourcePayloadEvidence,
)
from trading_bot.market_data.exceptions import DailySnapshotSerializationError
from trading_bot.market_data.models import AdjustmentType, Timeframe

MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES = 4 * 1024 * 1024

_TIMESTAMP_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{6})?Z$"
)
_DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

_ROOT_FIELDS = frozenset(
    {
        "adjustment",
        "audit",
        "bars",
        "calendar",
        "canonical_bars",
        "freshness",
        "protocol_version",
        "provider",
        "request_id",
        "requested_at",
        "schema_version",
        "snapshot_id",
        "symbols",
        "target_session",
        "timeframe",
    }
)
_CALENDAR_FIELDS = frozenset({"calendar_id", "exchange_timezone", "version"})
_PROVIDER_FIELDS = frozenset({"adapter_version", "feed", "operation", "provider_id"})
_BAR_FIELDS = frozenset(
    {
        "close",
        "high",
        "low",
        "open",
        "session",
        "symbol",
        "timestamp",
        "volume",
    }
)
_CANONICAL_BARS_FIELDS = frozenset(
    {"byte_length", "count", "material_version", "sha256"}
)
_AUDIT_FIELDS = frozenset(
    {
        "audit_sha256",
        "captured_at",
        "provider_as_of",
        "provider_request_id",
        "provider_response_symbols",
        "source_payload",
    }
)
_SOURCE_PAYLOAD_FIELDS = frozenset({"byte_length", "media_type", "sha256"})


def serialize_daily_snapshot(snapshot: DailyMarketDataSnapshot) -> bytes:
    """Serialize one exact immutable snapshot into canonical JSON bytes."""
    if type(snapshot) is not DailyMarketDataSnapshot:
        raise DailySnapshotSerializationError(
            "snapshot must be exactly DailyMarketDataSnapshot"
        )
    payload = _snapshot_tree(snapshot)
    try:
        rendered = json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        encoded = (rendered + "\n").encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as error:
        raise DailySnapshotSerializationError(
            "snapshot cannot be serialized as canonical JSON"
        ) from error
    if len(encoded) > MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES:
        raise DailySnapshotSerializationError(
            "serialized snapshot exceeds the 4 MiB limit"
        )
    return encoded


def parse_daily_snapshot(payload: bytes) -> DailyMarketDataSnapshot:
    """Strictly parse one bounded snapshot artifact without external access."""
    if type(payload) is not bytes:
        raise DailySnapshotSerializationError("payload must be exact bytes")
    if len(payload) > MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES:
        raise DailySnapshotSerializationError(
            "snapshot payload exceeds the 4 MiB limit"
        )
    if payload.startswith(b"\xef\xbb\xbf"):
        raise DailySnapshotSerializationError("UTF-8 BOM is not permitted")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise DailySnapshotSerializationError(
            "snapshot payload is not valid UTF-8"
        ) from error
    if not text.endswith("\n") or text.endswith("\n\n"):
        raise DailySnapshotSerializationError(
            "snapshot JSON must have exactly one final newline"
        )
    core = text[:-1]
    if not core or core != core.strip():
        raise DailySnapshotSerializationError(
            "snapshot JSON has leading or trailing whitespace"
        )
    try:
        value = json.loads(
            core,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, DailySnapshotSerializationError) as error:
        if isinstance(error, DailySnapshotSerializationError):
            raise
        raise DailySnapshotSerializationError(
            f"snapshot JSON is invalid at line {error.lineno} column {error.colno}"
        ) from error
    try:
        return _snapshot_from_tree(value)
    except DailySnapshotSerializationError:
        raise
    except (TypeError, ValueError) as error:
        raise DailySnapshotSerializationError(
            f"snapshot model is invalid: {error}"
        ) from error


def _snapshot_tree(snapshot: DailyMarketDataSnapshot) -> dict[str, Any]:
    request = snapshot.request
    return {
        "adjustment": request.adjustment.value,
        "audit": {
            "audit_sha256": snapshot.audit.audit_sha256,
            "captured_at": canonical_timestamp(snapshot.audit.captured_at),
            "provider_as_of": (
                None
                if snapshot.audit.provider_as_of is None
                else canonical_timestamp(snapshot.audit.provider_as_of)
            ),
            "provider_request_id": snapshot.audit.provider_request_id,
            "provider_response_symbols": [
                str(symbol) for symbol in snapshot.audit.provider_response_symbols
            ],
            "source_payload": {
                "byte_length": snapshot.audit.source_payload.byte_length,
                "media_type": snapshot.audit.source_payload.media_type,
                "sha256": snapshot.audit.source_payload.sha256,
            },
        },
        "bars": [
            {
                "close": canonical_decimal(item.bar.close),
                "high": canonical_decimal(item.bar.high),
                "low": canonical_decimal(item.bar.low),
                "open": canonical_decimal(item.bar.open),
                "session": item.session.session_date.isoformat(),
                "symbol": str(item.bar.symbol),
                "timestamp": canonical_timestamp(item.bar.timestamp),
                "volume": item.bar.volume,
            }
            for item in snapshot.bars
        ],
        "calendar": {
            "calendar_id": request.calendar.calendar_id,
            "exchange_timezone": request.calendar.exchange_timezone,
            "version": request.calendar.version,
        },
        "canonical_bars": {
            "byte_length": snapshot.canonical_bars.byte_length,
            "count": snapshot.canonical_bars.count,
            "material_version": snapshot.canonical_bars.material_version,
            "sha256": snapshot.canonical_bars.sha256,
        },
        "freshness": snapshot.freshness.value,
        "protocol_version": snapshot.protocol_version,
        "provider": {
            "adapter_version": snapshot.provider.adapter_version,
            "feed": snapshot.provider.feed,
            "operation": snapshot.provider.operation,
            "provider_id": snapshot.provider.provider_id,
        },
        "request_id": str(request.request_id),
        "requested_at": canonical_timestamp(request.requested_at),
        "schema_version": snapshot.schema_version,
        "snapshot_id": str(snapshot.snapshot_id),
        "symbols": [str(symbol) for symbol in request.symbols],
        "target_session": snapshot.target_session.session_date.isoformat(),
        "timeframe": request.timeframe.value,
    }


def _snapshot_from_tree(value: object) -> DailyMarketDataSnapshot:
    root = _object(value, "$", _ROOT_FIELDS)
    schema_version = _exact_int(root["schema_version"], "$.schema_version")
    if schema_version != DAILY_SNAPSHOT_SCHEMA_VERSION:
        raise DailySnapshotSerializationError("$.schema_version: expected 1")
    protocol_version = _exact_int(root["protocol_version"], "$.protocol_version")
    if protocol_version != DAILY_SNAPSHOT_PROTOCOL_VERSION:
        raise DailySnapshotSerializationError("$.protocol_version: expected 1")

    calendar_value = _object(root["calendar"], "$.calendar", _CALENDAR_FIELDS)
    calendar = CalendarDescriptor(
        calendar_id=_string(calendar_value["calendar_id"], "$.calendar.calendar_id"),
        version=_string(calendar_value["version"], "$.calendar.version"),
        exchange_timezone=_string(
            calendar_value["exchange_timezone"],
            "$.calendar.exchange_timezone",
        ),
    )
    symbols_value = _array(root["symbols"], "$.symbols")
    symbols = tuple(
        _canonical_symbol(item, f"$.symbols[{index}]")
        for index, item in enumerate(symbols_value)
    )
    request = DailySnapshotCaptureRequest(
        request_id=_canonical_uuid(root["request_id"], "$.request_id"),
        symbols=symbols,
        requested_at=_canonical_timestamp(root["requested_at"], "$.requested_at"),
        calendar=calendar,
        timeframe=_enum_value(Timeframe, root["timeframe"], "$.timeframe"),
        adjustment=_enum_value(AdjustmentType, root["adjustment"], "$.adjustment"),
    )

    provider_value = _object(root["provider"], "$.provider", _PROVIDER_FIELDS)
    provider = ProviderDescriptor(
        provider_id=_string(provider_value["provider_id"], "$.provider.provider_id"),
        adapter_version=_exact_int(
            provider_value["adapter_version"], "$.provider.adapter_version"
        ),
        operation=_string(provider_value["operation"], "$.provider.operation"),
        feed=_string(provider_value["feed"], "$.provider.feed"),
    )

    bars_value = _array(root["bars"], "$.bars")
    bars = tuple(
        _snapshot_bar_from_tree(item, index) for index, item in enumerate(bars_value)
    )
    canonical_value = _object(
        root["canonical_bars"],
        "$.canonical_bars",
        _CANONICAL_BARS_FIELDS,
    )
    canonical_bars = CanonicalBarsEvidence(
        material_version=_string(
            canonical_value["material_version"],
            "$.canonical_bars.material_version",
        ),
        count=_exact_int(canonical_value["count"], "$.canonical_bars.count"),
        sha256=_canonical_sha256(canonical_value["sha256"], "$.canonical_bars.sha256"),
        byte_length=_exact_nonnegative_int(
            canonical_value["byte_length"],
            "$.canonical_bars.byte_length",
        ),
    )

    audit_value = _object(root["audit"], "$.audit", _AUDIT_FIELDS)
    source_value = _object(
        audit_value["source_payload"],
        "$.audit.source_payload",
        _SOURCE_PAYLOAD_FIELDS,
    )
    provider_request_id = audit_value["provider_request_id"]
    if provider_request_id is not None:
        provider_request_id = _string(
            provider_request_id, "$.audit.provider_request_id"
        )
    provider_as_of = audit_value["provider_as_of"]
    if provider_as_of is not None:
        provider_as_of = _canonical_timestamp(provider_as_of, "$.audit.provider_as_of")
    response_symbols_value = _array(
        audit_value["provider_response_symbols"],
        "$.audit.provider_response_symbols",
    )
    audit = SnapshotAuditEvidence(
        captured_at=_canonical_timestamp(
            audit_value["captured_at"], "$.audit.captured_at"
        ),
        provider_as_of=provider_as_of,
        provider_request_id=provider_request_id,
        provider_response_symbols=tuple(
            _canonical_symbol(item, f"$.audit.provider_response_symbols[{index}]")
            for index, item in enumerate(response_symbols_value)
        ),
        source_payload=SourcePayloadEvidence(
            sha256=_canonical_sha256(
                source_value["sha256"], "$.audit.source_payload.sha256"
            ),
            byte_length=_exact_nonnegative_int(
                source_value["byte_length"],
                "$.audit.source_payload.byte_length",
            ),
            media_type=_string(
                source_value["media_type"], "$.audit.source_payload.media_type"
            ),
        ),
        audit_sha256=_canonical_sha256(
            audit_value["audit_sha256"], "$.audit.audit_sha256"
        ),
    )
    freshness = _enum_value(DailySnapshotFreshness, root["freshness"], "$.freshness")
    return DailyMarketDataSnapshot(
        snapshot_id=_canonical_uuid(root["snapshot_id"], "$.snapshot_id"),
        request=request,
        target_session=TradingSession(
            _canonical_date(root["target_session"], "$.target_session")
        ),
        provider=provider,
        bars=bars,
        canonical_bars=canonical_bars,
        audit=audit,
        freshness=freshness,
        schema_version=schema_version,
        protocol_version=protocol_version,
    )


def _snapshot_bar_from_tree(value: object, index: int) -> DailySnapshotBar:
    path = f"$.bars[{index}]"
    item = _object(value, path, _BAR_FIELDS)
    symbol = _canonical_symbol(item["symbol"], f"{path}.symbol")
    session = TradingSession(_canonical_date(item["session"], f"{path}.session"))
    return DailySnapshotBar(
        session=session,
        bar=Bar(
            symbol=symbol,
            timestamp=_canonical_timestamp(item["timestamp"], f"{path}.timestamp"),
            open=_canonical_positive_decimal(item["open"], f"{path}.open"),
            high=_canonical_positive_decimal(item["high"], f"{path}.high"),
            low=_canonical_positive_decimal(item["low"], f"{path}.low"),
            close=_canonical_positive_decimal(item["close"], f"{path}.close"),
            volume=_exact_nonnegative_int(item["volume"], f"{path}.volume"),
        ),
    )


def _object(value: object, path: str, fields: frozenset[str]) -> dict[str, object]:
    if type(value) is not dict:
        raise DailySnapshotSerializationError(f"{path}: expected object")
    actual = frozenset(value)
    missing = sorted(fields - actual)
    unknown = sorted(actual - fields)
    if missing:
        raise DailySnapshotSerializationError(
            f"{path}: missing fields: {', '.join(missing)}"
        )
    if unknown:
        raise DailySnapshotSerializationError(
            f"{path}: unknown fields: {', '.join(unknown)}"
        )
    return value


def _array(value: object, path: str) -> list[object]:
    if type(value) is not list:
        raise DailySnapshotSerializationError(f"{path}: expected array")
    return value


def _string(value: object, path: str) -> str:
    if type(value) is not str:
        raise DailySnapshotSerializationError(f"{path}: expected string")
    return value


def _exact_int(value: object, path: str) -> int:
    if type(value) is not int:
        raise DailySnapshotSerializationError(f"{path}: expected integer")
    return value


def _exact_nonnegative_int(value: object, path: str) -> int:
    retained = _exact_int(value, path)
    if retained < 0:
        raise DailySnapshotSerializationError(f"{path}: expected nonnegative integer")
    return retained


def _canonical_uuid(value: object, path: str) -> UUID:
    text = _string(value, path)
    try:
        parsed = UUID(text)
    except ValueError as error:
        raise DailySnapshotSerializationError(
            f"{path}: expected canonical UUID"
        ) from error
    if str(parsed) != text:
        raise DailySnapshotSerializationError(f"{path}: UUID is not canonical")
    return parsed


def _canonical_sha256(value: object, path: str) -> str:
    text = _string(value, path)
    if _SHA256_PATTERN.fullmatch(text) is None:
        raise DailySnapshotSerializationError(
            f"{path}: expected lowercase SHA-256 text"
        )
    return text


def _canonical_timestamp(value: object, path: str) -> datetime:
    text = _string(value, path)
    if _TIMESTAMP_PATTERN.fullmatch(text) is None:
        raise DailySnapshotSerializationError(
            f"{path}: expected canonical UTC timestamp"
        )
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as error:
        raise DailySnapshotSerializationError(
            f"{path}: invalid UTC timestamp"
        ) from error
    parsed = parsed.astimezone(UTC)
    if canonical_timestamp(parsed) != text:
        raise DailySnapshotSerializationError(f"{path}: timestamp is not canonical")
    return parsed


def _canonical_date(value: object, path: str) -> date:
    text = _string(value, path)
    if _DATE_PATTERN.fullmatch(text) is None:
        raise DailySnapshotSerializationError(f"{path}: expected ISO date")
    try:
        parsed = date.fromisoformat(text)
    except ValueError as error:
        raise DailySnapshotSerializationError(f"{path}: invalid date") from error
    if parsed.isoformat() != text:
        raise DailySnapshotSerializationError(f"{path}: date is not canonical")
    return parsed


def _canonical_symbol(value: object, path: str) -> Symbol:
    text = _string(value, path)
    try:
        symbol = Symbol(text)
    except (TypeError, ValueError) as error:
        raise DailySnapshotSerializationError(f"{path}: invalid symbol") from error
    if str(symbol) != text:
        raise DailySnapshotSerializationError(f"{path}: symbol is not canonical")
    return symbol


def _canonical_positive_decimal(value: object, path: str) -> Decimal:
    text = _string(value, path)
    try:
        parsed = Decimal(text)
    except InvalidOperation as error:
        raise DailySnapshotSerializationError(f"{path}: invalid Decimal") from error
    if not parsed.is_finite() or parsed <= 0 or canonical_decimal(parsed) != text:
        raise DailySnapshotSerializationError(
            f"{path}: expected canonical positive Decimal string"
        )
    return parsed


def _enum_value(enum_type, value: object, path: str):  # type: ignore[no-untyped-def]
    text = _string(value, path)
    try:
        return enum_type(text)
    except ValueError as error:
        raise DailySnapshotSerializationError(
            f"{path}: unsupported enum value"
        ) from error


def _reject_duplicate_keys(pairs):  # type: ignore[no-untyped-def]
    result = {}
    for key, value in pairs:
        if key in result:
            raise DailySnapshotSerializationError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise DailySnapshotSerializationError(
        f"nonstandard JSON constant is not permitted: {value}"
    )
