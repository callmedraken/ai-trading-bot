"""Immutable provider-neutral daily market-data snapshot models."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from trading_bot.domain import Bar, Symbol
from trading_bot.domain._validation import normalize_utc
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data.exceptions import (
    InvalidDailySnapshotCalendarError,
    InvalidDailySnapshotModelError,
    InvalidDailySnapshotProviderError,
    InvalidDailySnapshotRequestError,
    InvalidDailySnapshotResponseError,
)
from trading_bot.market_data.models import AdjustmentType, Timeframe

DAILY_SNAPSHOT_SCHEMA_VERSION = 1
DAILY_SNAPSHOT_PROTOCOL_VERSION = 1
MAX_DAILY_SNAPSHOT_SYMBOLS = 100

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_CALENDAR_TEXT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+-]*$")
_MEDIA_TYPE_PATTERN = re.compile(r"^[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+$")


@dataclass(frozen=True, slots=True)
class CalendarDescriptor:
    """Stable identity for one exact exchange-calendar implementation."""

    calendar_id: str
    version: str
    exchange_timezone: str

    def __post_init__(self) -> None:
        for field_name in ("calendar_id", "version", "exchange_timezone"):
            value = getattr(self, field_name)
            if (
                type(value) is not str
                or len(value) > 128
                or _CALENDAR_TEXT_PATTERN.fullmatch(value) is None
            ):
                raise InvalidDailySnapshotCalendarError(
                    f"{field_name} must be canonical ASCII text"
                )


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    """Provider-neutral, nonsecret identity for one adapter contract."""

    provider_id: str
    adapter_version: int
    operation: str
    feed: str

    def __post_init__(self) -> None:
        _require_identifier(self.provider_id, "provider_id")
        _require_exact_positive_int(self.adapter_version, "adapter_version")
        _require_identifier(self.operation, "operation")
        _require_identifier(self.feed, "feed")


@dataclass(frozen=True, slots=True)
class DailySnapshotCaptureRequest:
    """Caller-owned request for one complete prior-session snapshot."""

    request_id: UUID
    symbols: tuple[Symbol, ...]
    requested_at: datetime
    calendar: CalendarDescriptor
    timeframe: Timeframe = Timeframe.DAY_1
    adjustment: AdjustmentType = AdjustmentType.RAW

    def __post_init__(self) -> None:
        if type(self.request_id) is not UUID:
            raise InvalidDailySnapshotRequestError("request_id must be a UUID")
        try:
            symbols = tuple(self.symbols)
        except TypeError as error:
            raise InvalidDailySnapshotRequestError(
                "symbols must be iterable"
            ) from error
        if not 1 <= len(symbols) <= MAX_DAILY_SNAPSHOT_SYMBOLS:
            raise InvalidDailySnapshotRequestError(
                "symbols must contain between 1 and 100 values"
            )
        if any(type(symbol) is not Symbol for symbol in symbols):
            raise InvalidDailySnapshotRequestError(
                "symbols must contain only Symbol values"
            )
        if len(set(symbols)) != len(symbols):
            raise InvalidDailySnapshotRequestError("symbols must be unique")
        try:
            requested_at = normalize_utc(self.requested_at, "requested_at")
        except (TypeError, ValueError) as error:
            raise InvalidDailySnapshotRequestError(str(error)) from error
        if self.calendar != XNYS_CALENDAR_DESCRIPTOR:
            raise InvalidDailySnapshotRequestError(
                "calendar must be the exact supported XNYS descriptor"
            )
        if self.timeframe is not Timeframe.DAY_1:
            raise InvalidDailySnapshotRequestError("timeframe must be DAY_1")
        if self.adjustment is not AdjustmentType.RAW:
            raise InvalidDailySnapshotRequestError("adjustment must be RAW")
        object.__setattr__(self, "symbols", symbols)
        object.__setattr__(self, "requested_at", requested_at)


@dataclass(frozen=True, slots=True)
class DailyProviderRequest:
    """Exact semantic request supplied to one provider attempt."""

    capture_request: DailySnapshotCaptureRequest
    target_session: TradingSession
    provider: ProviderDescriptor

    def __post_init__(self) -> None:
        if type(self.capture_request) is not DailySnapshotCaptureRequest:
            raise InvalidDailySnapshotRequestError(
                "capture_request must be a DailySnapshotCaptureRequest"
            )
        if type(self.target_session) is not TradingSession:
            raise InvalidDailySnapshotRequestError(
                "target_session must be a TradingSession"
            )
        if type(self.provider) is not ProviderDescriptor:
            raise InvalidDailySnapshotRequestError(
                "provider must be a ProviderDescriptor"
            )


@dataclass(frozen=True, slots=True)
class DailyBarCandidate:
    """Untrusted parsed provider values awaiting canonical acceptance."""

    response_ordinal: int
    symbol: Symbol
    session: TradingSession
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


@dataclass(frozen=True, slots=True)
class SourcePayloadEvidence:
    """Hash and size evidence for an external response entity body."""

    sha256: str
    byte_length: int
    media_type: str

    def __post_init__(self) -> None:
        _require_sha256(self.sha256, "sha256", InvalidDailySnapshotResponseError)
        _require_exact_nonnegative_int(
            self.byte_length,
            "byte_length",
            InvalidDailySnapshotResponseError,
        )
        if (
            type(self.media_type) is not str
            or _MEDIA_TYPE_PATTERN.fullmatch(self.media_type) is None
        ):
            raise InvalidDailySnapshotResponseError(
                "media_type must be a canonical ASCII media type"
            )


@dataclass(frozen=True, slots=True)
class DailyProviderResponse:
    """One complete provider response envelope and ordered candidates."""

    request: DailyProviderRequest
    candidates: tuple[DailyBarCandidate, ...]
    captured_at: datetime
    provider_as_of: datetime | None
    provider_request_id: str | None
    source_payload: SourcePayloadEvidence
    pagination_complete: bool

    def __post_init__(self) -> None:
        if type(self.request) is not DailyProviderRequest:
            raise InvalidDailySnapshotResponseError(
                "request must be a DailyProviderRequest"
            )
        try:
            candidates = tuple(self.candidates)
        except TypeError as error:
            raise InvalidDailySnapshotResponseError(
                "candidates must be iterable"
            ) from error
        try:
            captured_at = normalize_utc(self.captured_at, "captured_at")
        except (TypeError, ValueError) as error:
            raise InvalidDailySnapshotResponseError(str(error)) from error
        if captured_at < self.request.capture_request.requested_at:
            raise InvalidDailySnapshotResponseError(
                "captured_at must not precede requested_at"
            )
        provider_as_of = self.provider_as_of
        if provider_as_of is not None:
            try:
                provider_as_of = normalize_utc(provider_as_of, "provider_as_of")
            except (TypeError, ValueError) as error:
                raise InvalidDailySnapshotResponseError(str(error)) from error
            if provider_as_of > captured_at:
                raise InvalidDailySnapshotResponseError(
                    "provider_as_of must not follow captured_at"
                )
        _require_optional_request_id(self.provider_request_id)
        if type(self.source_payload) is not SourcePayloadEvidence:
            raise InvalidDailySnapshotResponseError(
                "source_payload must be SourcePayloadEvidence"
            )
        if type(self.pagination_complete) is not bool:
            raise InvalidDailySnapshotResponseError(
                "pagination_complete must be a bool"
            )
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "captured_at", captured_at)
        object.__setattr__(self, "provider_as_of", provider_as_of)


@dataclass(frozen=True, slots=True)
class DailySnapshotBar:
    """One accepted daily bar bound to an exact exchange session."""

    session: TradingSession
    bar: Bar

    def __post_init__(self) -> None:
        if type(self.session) is not TradingSession:
            raise InvalidDailySnapshotModelError("session must be a TradingSession")
        if type(self.bar) is not Bar:
            raise InvalidDailySnapshotModelError("bar must be a Bar")


@dataclass(frozen=True, slots=True)
class CanonicalBarsEvidence:
    """Hash evidence for versioned canonical accepted-bar material."""

    material_version: str
    count: int
    sha256: str
    byte_length: int

    def __post_init__(self) -> None:
        _require_identifier(self.material_version, "material_version")
        _require_exact_positive_int(self.count, "count", InvalidDailySnapshotModelError)
        _require_sha256(self.sha256, "sha256", InvalidDailySnapshotModelError)
        _require_exact_nonnegative_int(
            self.byte_length,
            "byte_length",
            InvalidDailySnapshotModelError,
        )


@dataclass(frozen=True, slots=True)
class SnapshotAuditEvidence:
    """Retained non-identity response evidence and its own hash."""

    captured_at: datetime
    provider_as_of: datetime | None
    provider_request_id: str | None
    provider_response_symbols: tuple[Symbol, ...]
    source_payload: SourcePayloadEvidence
    audit_sha256: str

    def __post_init__(self) -> None:
        try:
            captured_at = normalize_utc(self.captured_at, "captured_at")
        except (TypeError, ValueError) as error:
            raise InvalidDailySnapshotModelError(str(error)) from error
        provider_as_of = self.provider_as_of
        if provider_as_of is not None:
            try:
                provider_as_of = normalize_utc(provider_as_of, "provider_as_of")
            except (TypeError, ValueError) as error:
                raise InvalidDailySnapshotModelError(str(error)) from error
            if provider_as_of > captured_at:
                raise InvalidDailySnapshotModelError(
                    "provider_as_of must not follow captured_at"
                )
        _require_optional_request_id(
            self.provider_request_id, InvalidDailySnapshotModelError
        )
        try:
            provider_response_symbols = tuple(self.provider_response_symbols)
        except TypeError as error:
            raise InvalidDailySnapshotModelError(
                "provider_response_symbols must be iterable"
            ) from error
        if not provider_response_symbols or any(
            type(symbol) is not Symbol for symbol in provider_response_symbols
        ):
            raise InvalidDailySnapshotModelError(
                "provider_response_symbols must contain Symbol values"
            )
        if type(self.source_payload) is not SourcePayloadEvidence:
            raise InvalidDailySnapshotModelError(
                "source_payload must be SourcePayloadEvidence"
            )
        _require_sha256(
            self.audit_sha256, "audit_sha256", InvalidDailySnapshotModelError
        )
        object.__setattr__(self, "captured_at", captured_at)
        object.__setattr__(self, "provider_as_of", provider_as_of)
        object.__setattr__(self, "provider_response_symbols", provider_response_symbols)


class DailySnapshotFreshness(StrEnum):
    """Top-level temporal classification for one provider response."""

    CURRENT = "CURRENT"
    INVALID = "INVALID"
    INCOMPLETE = "INCOMPLETE"
    MISSING = "MISSING"
    NON_SESSION = "NON_SESSION"
    INCONSISTENT = "INCONSISTENT"
    FUTURE = "FUTURE"
    STALE = "STALE"


class DailySnapshotAcceptanceStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class DailySnapshotRejectionClassification(StrEnum):
    """Ordered top-level rejection categories."""

    REQUEST_RESPONSE_MISMATCH = "REQUEST_RESPONSE_MISMATCH"
    INCOMPLETE_RESPONSE = "INCOMPLETE_RESPONSE"
    MALFORMED_CANDIDATE = "MALFORMED_CANDIDATE"
    UNEXPECTED_SYMBOL = "UNEXPECTED_SYMBOL"
    DUPLICATE_SYMBOL = "DUPLICATE_SYMBOL"
    MISSING_SYMBOL = "MISSING_SYMBOL"
    NON_SESSION = "NON_SESSION"
    MIXED_SESSION = "MIXED_SESSION"
    FUTURE = "FUTURE"
    STALE = "STALE"


class DailySnapshotDiagnosticCode(StrEnum):
    REQUEST_RESPONSE_MISMATCH = "REQUEST_RESPONSE_MISMATCH"
    PAGINATION_INCOMPLETE = "PAGINATION_INCOMPLETE"
    INVALID_RESPONSE_ORDINAL = "INVALID_RESPONSE_ORDINAL"
    MALFORMED_CANDIDATE = "MALFORMED_CANDIDATE"
    SESSION_TIMESTAMP_MISMATCH = "SESSION_TIMESTAMP_MISMATCH"
    UNEXPECTED_SYMBOL = "UNEXPECTED_SYMBOL"
    DUPLICATE_SYMBOL = "DUPLICATE_SYMBOL"
    MISSING_SYMBOL = "MISSING_SYMBOL"
    NON_SESSION = "NON_SESSION"
    MIXED_SESSION = "MIXED_SESSION"
    FUTURE_SESSION = "FUTURE_SESSION"
    STALE_SESSION = "STALE_SESSION"


@dataclass(frozen=True, slots=True)
class DailySnapshotDiagnostic:
    """One deterministic acceptance diagnostic."""

    code: DailySnapshotDiagnosticCode
    symbol: Symbol | None = None
    response_ordinal: int | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.code, DailySnapshotDiagnosticCode):
            raise InvalidDailySnapshotModelError(
                "code must be a DailySnapshotDiagnosticCode"
            )
        if self.symbol is not None and type(self.symbol) is not Symbol:
            raise InvalidDailySnapshotModelError("symbol must be Symbol or None")
        if self.response_ordinal is not None:
            _require_exact_nonnegative_int(
                self.response_ordinal,
                "response_ordinal",
                InvalidDailySnapshotModelError,
            )
        if type(self.detail) is not str:
            raise InvalidDailySnapshotModelError("detail must be a string")


@dataclass(frozen=True, slots=True)
class DailyMarketDataSnapshot:
    """Complete immutable accepted daily market-data snapshot."""

    snapshot_id: UUID
    request: DailySnapshotCaptureRequest
    target_session: TradingSession
    provider: ProviderDescriptor
    bars: tuple[DailySnapshotBar, ...]
    canonical_bars: CanonicalBarsEvidence
    audit: SnapshotAuditEvidence
    freshness: DailySnapshotFreshness = DailySnapshotFreshness.CURRENT
    schema_version: int = DAILY_SNAPSHOT_SCHEMA_VERSION
    protocol_version: int = DAILY_SNAPSHOT_PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if type(self.snapshot_id) is not UUID:
            raise InvalidDailySnapshotModelError("snapshot_id must be a UUID")
        if type(self.request) is not DailySnapshotCaptureRequest:
            raise InvalidDailySnapshotModelError(
                "request must be DailySnapshotCaptureRequest"
            )
        if type(self.target_session) is not TradingSession:
            raise InvalidDailySnapshotModelError(
                "target_session must be TradingSession"
            )
        if type(self.provider) is not ProviderDescriptor:
            raise InvalidDailySnapshotModelError("provider must be ProviderDescriptor")
        try:
            bars = tuple(self.bars)
        except TypeError as error:
            raise InvalidDailySnapshotModelError("bars must be iterable") from error
        if len(bars) != len(self.request.symbols):
            raise InvalidDailySnapshotModelError(
                "bars must contain exactly one value per requested symbol"
            )
        for position, (symbol, snapshot_bar) in enumerate(
            zip(self.request.symbols, bars, strict=True)
        ):
            if type(snapshot_bar) is not DailySnapshotBar:
                raise InvalidDailySnapshotModelError(
                    f"bars[{position}] must be DailySnapshotBar"
                )
            if snapshot_bar.bar.symbol != symbol:
                raise InvalidDailySnapshotModelError(
                    "bars must follow exact requested symbol order"
                )
            if snapshot_bar.session != self.target_session:
                raise InvalidDailySnapshotModelError(
                    "every bar must match target_session"
                )
        if type(self.canonical_bars) is not CanonicalBarsEvidence:
            raise InvalidDailySnapshotModelError(
                "canonical_bars must be CanonicalBarsEvidence"
            )
        if self.canonical_bars.count != len(bars):
            raise InvalidDailySnapshotModelError("canonical bar count must match bars")
        if type(self.audit) is not SnapshotAuditEvidence:
            raise InvalidDailySnapshotModelError("audit must be SnapshotAuditEvidence")
        if self.audit.captured_at < self.request.requested_at:
            raise InvalidDailySnapshotModelError(
                "captured_at must not precede requested_at"
            )
        if len(self.audit.provider_response_symbols) != len(bars):
            raise InvalidDailySnapshotModelError(
                "provider response order must contain every accepted bar"
            )
        if set(self.audit.provider_response_symbols) != set(self.request.symbols):
            raise InvalidDailySnapshotModelError(
                "provider response symbols must equal requested symbols"
            )
        if self.freshness is not DailySnapshotFreshness.CURRENT:
            raise InvalidDailySnapshotModelError(
                "accepted snapshot freshness must be CURRENT"
            )
        if (
            type(self.schema_version) is not int
            or self.schema_version != DAILY_SNAPSHOT_SCHEMA_VERSION
        ):
            raise InvalidDailySnapshotModelError("schema_version must be 1")
        if (
            type(self.protocol_version) is not int
            or self.protocol_version != DAILY_SNAPSHOT_PROTOCOL_VERSION
        ):
            raise InvalidDailySnapshotModelError("protocol_version must be 1")
        object.__setattr__(self, "bars", bars)


@dataclass(frozen=True, slots=True)
class DailySnapshotAcceptanceResult:
    """Accepted complete snapshot or rejected diagnostics, never both."""

    status: DailySnapshotAcceptanceStatus
    freshness: DailySnapshotFreshness
    snapshot: DailyMarketDataSnapshot | None
    classification: DailySnapshotRejectionClassification | None
    diagnostics: tuple[DailySnapshotDiagnostic, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, DailySnapshotAcceptanceStatus):
            raise InvalidDailySnapshotModelError(
                "status must be DailySnapshotAcceptanceStatus"
            )
        if not isinstance(self.freshness, DailySnapshotFreshness):
            raise InvalidDailySnapshotModelError(
                "freshness must be DailySnapshotFreshness"
            )
        diagnostics = tuple(self.diagnostics)
        if any(type(item) is not DailySnapshotDiagnostic for item in diagnostics):
            raise InvalidDailySnapshotModelError(
                "diagnostics must contain DailySnapshotDiagnostic values"
            )
        if self.status is DailySnapshotAcceptanceStatus.ACCEPTED:
            if type(self.snapshot) is not DailyMarketDataSnapshot:
                raise InvalidDailySnapshotModelError(
                    "ACCEPTED requires a complete snapshot"
                )
            if (
                self.freshness is not DailySnapshotFreshness.CURRENT
                or self.classification is not None
                or diagnostics
            ):
                raise InvalidDailySnapshotModelError(
                    "ACCEPTED requires CURRENT with no rejection diagnostics"
                )
        else:
            if self.snapshot is not None:
                raise InvalidDailySnapshotModelError(
                    "REJECTED must not contain a snapshot"
                )
            if not isinstance(
                self.classification, DailySnapshotRejectionClassification
            ):
                raise InvalidDailySnapshotModelError(
                    "REJECTED requires a rejection classification"
                )
            if self.freshness is DailySnapshotFreshness.CURRENT or not diagnostics:
                raise InvalidDailySnapshotModelError(
                    "REJECTED requires non-CURRENT freshness and diagnostics"
                )
        object.__setattr__(self, "diagnostics", diagnostics)


@dataclass(frozen=True, slots=True)
class DailySnapshotReplayView:
    """Exact immutable bars exposed after complete offline verification."""

    snapshot_id: UUID
    target_session: TradingSession
    provider: ProviderDescriptor
    symbols: tuple[Symbol, ...]
    bars: tuple[DailySnapshotBar, ...]

    def __post_init__(self) -> None:
        if type(self.snapshot_id) is not UUID:
            raise InvalidDailySnapshotModelError("snapshot_id must be UUID")
        if type(self.target_session) is not TradingSession:
            raise InvalidDailySnapshotModelError(
                "target_session must be TradingSession"
            )
        if type(self.provider) is not ProviderDescriptor:
            raise InvalidDailySnapshotModelError("provider must be ProviderDescriptor")
        symbols = tuple(self.symbols)
        bars = tuple(self.bars)
        if len(symbols) != len(bars) or not symbols:
            raise InvalidDailySnapshotModelError(
                "replay symbols and bars must be complete"
            )
        if any(type(symbol) is not Symbol for symbol in symbols):
            raise InvalidDailySnapshotModelError(
                "replay symbols must contain Symbol values"
            )
        for symbol, snapshot_bar in zip(symbols, bars, strict=True):
            if (
                type(snapshot_bar) is not DailySnapshotBar
                or snapshot_bar.bar.symbol != symbol
                or snapshot_bar.session != self.target_session
            ):
                raise InvalidDailySnapshotModelError(
                    "replay bars must match symbols and target session"
                )
        object.__setattr__(self, "symbols", symbols)
        object.__setattr__(self, "bars", bars)


def _require_identifier(value: object, field_name: str) -> None:
    if (
        type(value) is not str
        or len(value) > 128
        or _IDENTIFIER_PATTERN.fullmatch(value) is None
    ):
        raise InvalidDailySnapshotProviderError(
            f"{field_name} must be a canonical ASCII identifier"
        )


def _require_optional_request_id(
    value: object,
    error_type: type[Exception] = InvalidDailySnapshotResponseError,
) -> None:
    if value is None:
        return
    if (
        type(value) is not str
        or not value
        or len(value) > 256
        or any(ord(character) < 33 or ord(character) > 126 for character in value)
    ):
        raise error_type("provider_request_id must be nonblank printable ASCII or None")


def _require_sha256(
    value: object, field_name: str, error_type: type[Exception]
) -> None:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise error_type(f"{field_name} must be lowercase SHA-256 text")


def _require_exact_positive_int(
    value: object,
    field_name: str,
    error_type: type[Exception] = InvalidDailySnapshotProviderError,
) -> None:
    if type(value) is not int or value <= 0:
        raise error_type(f"{field_name} must be a positive integer")


def _require_exact_nonnegative_int(
    value: object, field_name: str, error_type: type[Exception]
) -> None:
    if type(value) is not int or value < 0:
        raise error_type(f"{field_name} must be a nonnegative integer")


XNYS_CALENDAR_DESCRIPTOR = CalendarDescriptor(
    calendar_id="XNYS",
    version="nyse-regular-sessions-1998-2100-v1",
    exchange_timezone="America/New_York",
)
