"""Immutable presentation-only models for GUI-A10 Evidence Timeline."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

MAX_EVIDENCE_TIMELINE_ENTRIES = 32
MAX_EVIDENCE_TIMELINE_TEXT_CHARACTERS = 512
MAX_EVIDENCE_TIMELINE_IDENTIFIER_CHARACTERS = 256

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class EvidenceTimelineSource(Enum):
    """Closed source vocabulary for already-acquired GUI evidence."""

    RESEARCH = "Research"
    PAPER_OPERATION = "Paper Operation"
    PAPER_ACCOUNT = "Paper Account"
    MARKET_DATA = "Market Data"
    OPERATIONS = "Operations"


def _require_text(value: str, field_name: str, maximum: int) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{field_name} must be non-empty canonical text")
    if len(value) > maximum:
        raise ValueError(f"{field_name} exceeds the presentation bound")
    if any(ord(character) < 0x20 and character not in "\t" for character in value):
        raise ValueError(f"{field_name} contains unsupported control characters")


@dataclass(frozen=True, slots=True)
class EvidenceTimelineEntry:
    """One bounded evidence identity derived from an existing GUI page state."""

    source: EvidenceTimelineSource
    title: str
    identifier: str
    occurred_at: datetime | None
    sha256: str | None
    detail: str

    def __post_init__(self) -> None:
        if type(self.source) is not EvidenceTimelineSource:
            raise TypeError("source must be an exact EvidenceTimelineSource")
        _require_text(self.title, "title", 128)
        _require_text(
            self.identifier,
            "identifier",
            MAX_EVIDENCE_TIMELINE_IDENTIFIER_CHARACTERS,
        )
        if self.occurred_at is not None and (
            type(self.occurred_at) is not datetime
            or self.occurred_at.tzinfo is None
            or self.occurred_at.utcoffset() is None
        ):
            raise ValueError("occurred_at must be timezone-aware or None")
        if self.sha256 is not None and (
            type(self.sha256) is not str
            or _SHA256_PATTERN.fullmatch(self.sha256) is None
        ):
            raise ValueError("sha256 must be lowercase SHA-256 text or None")
        _require_text(
            self.detail,
            "detail",
            MAX_EVIDENCE_TIMELINE_TEXT_CHARACTERS,
        )


@dataclass(frozen=True, slots=True)
class EvidenceTimelinePageState:
    """Read-only timeline state derived entirely from GUI presentation values."""

    message: str
    entries: tuple[EvidenceTimelineEntry, ...]

    def __post_init__(self) -> None:
        _require_text(
            self.message,
            "message",
            MAX_EVIDENCE_TIMELINE_TEXT_CHARACTERS,
        )
        try:
            entries = tuple(self.entries)
        except TypeError as error:
            raise TypeError("entries must be iterable") from error
        if len(entries) > MAX_EVIDENCE_TIMELINE_ENTRIES:
            raise ValueError("entries exceed the presentation count bound")
        if any(type(item) is not EvidenceTimelineEntry for item in entries):
            raise TypeError("entries must contain exact EvidenceTimelineEntry values")
        identities = tuple(
            (item.source, item.title, item.identifier) for item in entries
        )
        if len(identities) != len(set(identities)):
            raise ValueError("timeline evidence identities must be unique")
        object.__setattr__(self, "entries", entries)
