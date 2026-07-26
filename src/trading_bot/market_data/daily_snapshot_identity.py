"""Versioned canonical material for deterministic daily snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid5

from trading_bot.domain import Symbol
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data.daily_snapshot_models import (
    CanonicalBarsEvidence,
    DailySnapshotBar,
    DailySnapshotCaptureRequest,
    ProviderDescriptor,
    SourcePayloadEvidence,
)
from trading_bot.market_data.exceptions import InvalidDailySnapshotModelError

CANONICAL_BARS_MATERIAL_VERSION = "daily-market-snapshot-bars-v1"
SNAPSHOT_IDENTITY_MATERIAL_VERSION = "daily-market-snapshot-identity-v1"
SNAPSHOT_AUDIT_MATERIAL_VERSION = "daily-market-snapshot-audit-v1"
DAILY_SNAPSHOT_IDENTITY_NAMESPACE = UUID("3ca3c3db-658d-58b0-a7fb-0d560cc15968")

_ZERO = Decimal("0")


def canonical_scalar(value: str) -> str:
    """Frame one ASCII scalar without ambiguous delimiters."""
    if type(value) is not str:
        raise InvalidDailySnapshotModelError("canonical scalar must be a string")
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError as error:
        raise InvalidDailySnapshotModelError(
            "canonical scalar must contain only ASCII"
        ) from error
    return f"{len(encoded)}:{value}"


def canonical_decimal(value: Decimal) -> str:
    """Render an exact finite Decimal without exponent or ambient context."""
    if type(value) is not Decimal or not value.is_finite():
        raise InvalidDailySnapshotModelError(
            "canonical Decimal values must be exact and finite"
        )
    if value == _ZERO:
        return "0"
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def canonical_timestamp(value: datetime) -> str:
    """Render one exact aware timestamp in canonical UTC text."""
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise InvalidDailySnapshotModelError(
            "canonical timestamps must be timezone-aware datetimes"
        )
    normalized = value.astimezone(UTC)
    if normalized.microsecond:
        return normalized.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical_session(value: TradingSession) -> str:
    if type(value) is not TradingSession:
        raise InvalidDailySnapshotModelError(
            "canonical sessions must be TradingSession values"
        )
    return value.session_date.isoformat()


def canonical_bar_material(bars: tuple[DailySnapshotBar, ...]) -> str:
    """Return complete ordered canonical material for accepted bars."""
    try:
        retained = tuple(bars)
    except TypeError as error:
        raise InvalidDailySnapshotModelError("bars must be iterable") from error
    if not retained:
        raise InvalidDailySnapshotModelError("canonical bars must not be empty")
    values = [CANONICAL_BARS_MATERIAL_VERSION]
    for position, snapshot_bar in enumerate(retained):
        if type(snapshot_bar) is not DailySnapshotBar:
            raise InvalidDailySnapshotModelError(
                "bars must contain DailySnapshotBar values"
            )
        bar = snapshot_bar.bar
        values.extend(
            (
                str(position),
                str(bar.symbol),
                canonical_session(snapshot_bar.session),
                canonical_timestamp(bar.timestamp),
                canonical_decimal(bar.open),
                canonical_decimal(bar.high),
                canonical_decimal(bar.low),
                canonical_decimal(bar.close),
                str(bar.volume),
            )
        )
    return "".join(canonical_scalar(value) for value in values)


def canonical_bars_evidence(
    bars: tuple[DailySnapshotBar, ...],
) -> CanonicalBarsEvidence:
    """Hash the exact canonical accepted-bar material."""
    material = canonical_bar_material(bars).encode("ascii")
    return CanonicalBarsEvidence(
        material_version=CANONICAL_BARS_MATERIAL_VERSION,
        count=len(bars),
        sha256=sha256(material).hexdigest(),
        byte_length=len(material),
    )


def snapshot_identity_material(
    request: DailySnapshotCaptureRequest,
    target_session: TradingSession,
    provider: ProviderDescriptor,
    bars: tuple[DailySnapshotBar, ...],
) -> str:
    """Return versioned UUID5 material excluding clocks and source evidence."""
    if type(request) is not DailySnapshotCaptureRequest:
        raise InvalidDailySnapshotModelError(
            "request must be DailySnapshotCaptureRequest"
        )
    if type(target_session) is not TradingSession:
        raise InvalidDailySnapshotModelError("target_session must be TradingSession")
    if type(provider) is not ProviderDescriptor:
        raise InvalidDailySnapshotModelError("provider must be ProviderDescriptor")
    values = [
        SNAPSHOT_IDENTITY_MATERIAL_VERSION,
        str(request.request_id),
        request.calendar.calendar_id,
        request.calendar.version,
        request.calendar.exchange_timezone,
        canonical_session(target_session),
        request.timeframe.value,
        request.adjustment.value,
        provider.provider_id,
        str(provider.adapter_version),
        provider.operation,
        provider.feed,
        str(len(request.symbols)),
        *(str(symbol) for symbol in request.symbols),
        canonical_bar_material(bars),
    ]
    return "".join(canonical_scalar(value) for value in values)


def daily_snapshot_id(
    request: DailySnapshotCaptureRequest,
    target_session: TradingSession,
    provider: ProviderDescriptor,
    bars: tuple[DailySnapshotBar, ...],
) -> UUID:
    """Derive the deterministic snapshot UUID5."""
    return uuid5(
        DAILY_SNAPSHOT_IDENTITY_NAMESPACE,
        snapshot_identity_material(request, target_session, provider, bars),
    )


def snapshot_audit_material(
    *,
    snapshot_id: UUID,
    requested_at: datetime,
    captured_at: datetime,
    provider_as_of: datetime | None,
    provider_request_id: str | None,
    provider_response_symbols: tuple[Symbol, ...],
    source_payload: SourcePayloadEvidence,
) -> str:
    """Return separately versioned material for excluded audit evidence."""
    if type(snapshot_id) is not UUID:
        raise InvalidDailySnapshotModelError("snapshot_id must be UUID")
    if type(source_payload) is not SourcePayloadEvidence:
        raise InvalidDailySnapshotModelError(
            "source_payload must be SourcePayloadEvidence"
        )
    try:
        response_symbols = tuple(provider_response_symbols)
    except TypeError as error:
        raise InvalidDailySnapshotModelError(
            "provider_response_symbols must be iterable"
        ) from error
    if any(type(symbol) is not Symbol for symbol in response_symbols):
        raise InvalidDailySnapshotModelError(
            "provider_response_symbols must contain Symbol values"
        )
    values = [
        SNAPSHOT_AUDIT_MATERIAL_VERSION,
        str(snapshot_id),
        canonical_timestamp(requested_at),
        canonical_timestamp(captured_at),
        ("<none>" if provider_as_of is None else canonical_timestamp(provider_as_of)),
        "<none>" if provider_request_id is None else provider_request_id,
        source_payload.sha256,
        str(source_payload.byte_length),
        source_payload.media_type,
        str(len(response_symbols)),
    ]
    for position, symbol in enumerate(response_symbols):
        values.extend((str(position), str(symbol)))
    return "".join(canonical_scalar(value) for value in values)


def daily_snapshot_audit_hash(
    *,
    snapshot_id: UUID,
    requested_at: datetime,
    captured_at: datetime,
    provider_as_of: datetime | None,
    provider_request_id: str | None,
    provider_response_symbols: tuple[Symbol, ...],
    source_payload: SourcePayloadEvidence,
) -> str:
    """Hash retained non-identity evidence."""
    material = snapshot_audit_material(
        snapshot_id=snapshot_id,
        requested_at=requested_at,
        captured_at=captured_at,
        provider_as_of=provider_as_of,
        provider_request_id=provider_request_id,
        provider_response_symbols=provider_response_symbols,
        source_payload=source_payload,
    ).encode("ascii")
    return sha256(material).hexdigest()
