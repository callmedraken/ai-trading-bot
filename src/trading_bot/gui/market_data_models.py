"""Immutable Qt-free presentation records for verified market-data snapshots."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from uuid import UUID

MAX_MARKET_DATA_MESSAGE_CHARACTERS = 512
MAX_MARKET_DATA_PRESENTATION_TEXT_CHARACTERS = 256
MAX_MARKET_DATA_SYMBOL_CHARACTERS = 64
MAX_MARKET_DATA_SYMBOLS = 100

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class MarketDataPageStatus(Enum):
    """Bounded availability state for the read-only Market Data page."""

    VERIFIED = "verified"
    UNAVAILABLE = "unavailable"


def _require_message(value: str) -> None:
    if type(value) is not str or not value.strip():
        raise ValueError("market-data page message must be non-empty text")
    if len(value) > MAX_MARKET_DATA_MESSAGE_CHARACTERS:
        raise ValueError("market-data page message exceeds the presentation bound")


def _require_presentation_text(value: str, field_name: str) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{field_name} must be non-empty canonical text")
    if len(value) > MAX_MARKET_DATA_PRESENTATION_TEXT_CHARACTERS:
        raise ValueError(f"{field_name} exceeds the presentation bound")
    if any(ord(character) < 0x20 or ord(character) > 0x7E for character in value):
        raise ValueError(f"{field_name} must be printable ASCII text")


def _require_sha256(value: str, field_name: str) -> None:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be lowercase SHA-256 text")


def _require_byte_length(value: int, field_name: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field_name} must be a nonnegative exact integer")


def _require_aware_datetime(value: datetime, field_name: str) -> None:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be an exact timezone-aware datetime")


@dataclass(frozen=True, slots=True)
class VerifiedMarketSnapshotView:
    """Bounded nonsecret facts from one completely verified snapshot artifact."""

    snapshot_id: UUID
    target_session_date: date
    symbols: tuple[str, ...]
    provider_id: str
    provider_operation: str
    provider_feed: str
    artifact_sha256: str
    artifact_byte_length: int
    captured_at: datetime
    provider_as_of: datetime | None
    source_payload_sha256: str
    source_payload_byte_length: int
    source_payload_media_type: str

    def __post_init__(self) -> None:
        if type(self.snapshot_id) is not UUID:
            raise TypeError("snapshot_id must be a UUID")
        if type(self.target_session_date) is not date:
            raise TypeError("target_session_date must be an exact date")

        try:
            symbols = tuple(self.symbols)
        except TypeError as error:
            raise TypeError("symbols must be iterable") from error
        if not 1 <= len(symbols) <= MAX_MARKET_DATA_SYMBOLS:
            raise ValueError("symbols must contain between 1 and 100 values")
        if any(type(symbol) is not str for symbol in symbols):
            raise TypeError("symbols must contain exact strings")
        if any(
            not symbol
            or symbol != symbol.strip()
            or len(symbol) > MAX_MARKET_DATA_SYMBOL_CHARACTERS
            or any(ord(character) < 0x21 or ord(character) > 0x7E for character in symbol)
            for symbol in symbols
        ):
            raise ValueError("symbols contain invalid presentation text")
        if len(set(symbols)) != len(symbols):
            raise ValueError("symbols must be unique")

        _require_presentation_text(self.provider_id, "provider_id")
        _require_presentation_text(self.provider_operation, "provider_operation")
        _require_presentation_text(self.provider_feed, "provider_feed")
        _require_sha256(self.artifact_sha256, "artifact_sha256")
        _require_byte_length(self.artifact_byte_length, "artifact_byte_length")
        _require_aware_datetime(self.captured_at, "captured_at")
        if self.provider_as_of is not None:
            _require_aware_datetime(self.provider_as_of, "provider_as_of")
            if self.provider_as_of > self.captured_at:
                raise ValueError("provider_as_of must not follow captured_at")
        _require_sha256(self.source_payload_sha256, "source_payload_sha256")
        _require_byte_length(
            self.source_payload_byte_length,
            "source_payload_byte_length",
        )
        _require_presentation_text(
            self.source_payload_media_type,
            "source_payload_media_type",
        )
        object.__setattr__(self, "symbols", symbols)


@dataclass(frozen=True, slots=True)
class MarketDataPageState:
    """One verified local snapshot artifact or a bounded unavailable state."""

    status: MarketDataPageStatus
    message: str
    snapshot: VerifiedMarketSnapshotView | None

    def __post_init__(self) -> None:
        if type(self.status) is not MarketDataPageStatus:
            raise TypeError("status must be a MarketDataPageStatus")
        _require_message(self.message)
        if self.status is MarketDataPageStatus.VERIFIED:
            if type(self.snapshot) is not VerifiedMarketSnapshotView:
                raise ValueError("verified market-data state requires one snapshot")
        elif self.snapshot is not None:
            raise ValueError("unavailable market-data state must not contain a snapshot")


def unavailable_market_data_state() -> MarketDataPageState:
    """Return the deterministic default state with no verified artifact connected."""
    return MarketDataPageState(
        status=MarketDataPageStatus.UNAVAILABLE,
        message=(
            "No verified market-data snapshot artifact is connected to this "
            "read-only GUI."
        ),
        snapshot=None,
    )
