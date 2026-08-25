"""Immutable presentation-only records for the desktop GUI."""

from dataclasses import dataclass
from enum import Enum


class OperatingMode(Enum):
    """Operator-visible mode label; this enum grants no operating authority."""

    RESEARCH = "research"
    SIMULATED_PAPER = "simulated-paper"
    BROKER_PAPER = "broker-paper"
    LIVE = "live"


class PresentationStatus(Enum):
    """Bounded status vocabulary for read-only GUI presentation."""

    INFO = "info"
    HEALTHY = "healthy"
    UNAVAILABLE = "unavailable"
    BLOCKED = "blocked"


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


@dataclass(frozen=True, slots=True)
class ComponentStatus:
    """One bounded, presentation-only component status card."""

    key: str
    title: str
    status: PresentationStatus
    detail: str

    def __post_init__(self) -> None:
        _require_text(self.key, "key")
        _require_text(self.title, "title")
        _require_text(self.detail, "detail")
        if not isinstance(self.status, PresentationStatus):
            raise TypeError("status must be a PresentationStatus")


@dataclass(frozen=True, slots=True)
class ApplicationOverview:
    """Read-only application overview consumed by the GUI shell."""

    mode: OperatingMode
    environment: str
    summary: str
    components: tuple[ComponentStatus, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.mode, OperatingMode):
            raise TypeError("mode must be an OperatingMode")
        _require_text(self.environment, "environment")
        _require_text(self.summary, "summary")

        components = tuple(self.components)
        if not components:
            raise ValueError("components must not be empty")
        if not all(isinstance(item, ComponentStatus) for item in components):
            raise TypeError("components must contain ComponentStatus values")

        keys = tuple(item.key for item in components)
        if len(keys) != len(set(keys)):
            raise ValueError("component keys must be unique")

        object.__setattr__(self, "components", components)
