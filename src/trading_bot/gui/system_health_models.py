"""Immutable presentation-only models for GUI-A9 System Health & Audit."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

MAX_SYSTEM_COMPONENTS = 16
MAX_SYSTEM_AUDIT_ENTRIES = 32
MAX_SYSTEM_TEXT_CHARACTERS = 512
MAX_SYSTEM_IDENTIFIER_CHARACTERS = 256

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class SystemHealthStatus(Enum):
    """Overall status of already-presented local read-only GUI state."""

    READ_ONLY_READY = "read_only_ready"
    ATTENTION = "attention"


class SystemComponentStatus(Enum):
    """Bounded health classification for one already-presented GUI component."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    BLOCKED = "blocked"


def _require_text(value: str, field_name: str, maximum: int) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{field_name} must be non-empty canonical text")
    if len(value) > maximum:
        raise ValueError(f"{field_name} exceeds the presentation bound")
    if any(ord(character) < 0x20 and character not in "\t" for character in value):
        raise ValueError(f"{field_name} contains unsupported control characters")


@dataclass(frozen=True, slots=True)
class SystemComponentHealthView:
    """One component status derived from an already-acquired GUI page state."""

    key: str
    title: str
    status: SystemComponentStatus
    detail: str

    def __post_init__(self) -> None:
        _require_text(self.key, "key", 64)
        _require_text(self.title, "title", 128)
        if type(self.status) is not SystemComponentStatus:
            raise TypeError("status must be an exact SystemComponentStatus")
        _require_text(self.detail, "detail", MAX_SYSTEM_TEXT_CHARACTERS)


@dataclass(frozen=True, slots=True)
class SystemAuditEntryView:
    """One bounded identifier/hash already exposed by another GUI page."""

    source: str
    evidence_kind: str
    identifier: str
    sha256: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.source, "source", 128)
        _require_text(self.evidence_kind, "evidence_kind", 128)
        _require_text(
            self.identifier,
            "identifier",
            MAX_SYSTEM_IDENTIFIER_CHARACTERS,
        )
        if self.sha256 is not None and (
            type(self.sha256) is not str
            or _SHA256_PATTERN.fullmatch(self.sha256) is None
        ):
            raise ValueError("sha256 must be lowercase SHA-256 text or None")


@dataclass(frozen=True, slots=True)
class SystemHealthPageState:
    """Pure read-only System Health & Audit state."""

    status: SystemHealthStatus
    message: str
    environment: str
    displayed_mode: str
    components: tuple[SystemComponentHealthView, ...]
    audit_entries: tuple[SystemAuditEntryView, ...]

    def __post_init__(self) -> None:
        if type(self.status) is not SystemHealthStatus:
            raise TypeError("status must be an exact SystemHealthStatus")
        _require_text(self.message, "message", MAX_SYSTEM_TEXT_CHARACTERS)
        _require_text(self.environment, "environment", 256)
        _require_text(self.displayed_mode, "displayed_mode", 128)

        try:
            components = tuple(self.components)
            audit_entries = tuple(self.audit_entries)
        except TypeError as error:
            raise TypeError("components and audit_entries must be iterable") from error

        if not 1 <= len(components) <= MAX_SYSTEM_COMPONENTS:
            raise ValueError("components must contain between 1 and 16 values")
        if any(type(item) is not SystemComponentHealthView for item in components):
            raise TypeError(
                "components must contain exact SystemComponentHealthView values"
            )
        keys = tuple(item.key for item in components)
        if len(keys) != len(set(keys)):
            raise ValueError("component keys must be unique")

        if len(audit_entries) > MAX_SYSTEM_AUDIT_ENTRIES:
            raise ValueError("audit_entries exceed the presentation count bound")
        if any(type(item) is not SystemAuditEntryView for item in audit_entries):
            raise TypeError(
                "audit_entries must contain exact SystemAuditEntryView values"
            )
        identities = tuple(
            (item.source, item.evidence_kind, item.identifier) for item in audit_entries
        )
        if len(identities) != len(set(identities)):
            raise ValueError("audit entries must be unique")

        object.__setattr__(self, "components", components)
        object.__setattr__(self, "audit_entries", audit_entries)
