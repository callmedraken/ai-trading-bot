"""Qt-free GUI-A12 navigation targets derived from System audit evidence."""

from __future__ import annotations

from dataclasses import dataclass

from trading_bot.gui.evidence_explorer import (
    MAX_EVIDENCE_TIMELINE_FILTER_CHARACTERS,
)
from trading_bot.gui.evidence_timeline_models import EvidenceTimelineSource
from trading_bot.gui.system_health_models import SystemAuditEntryView

_SYSTEM_SOURCE_TO_EVIDENCE = {
    "Research": EvidenceTimelineSource.RESEARCH,
    "Paper Operation": EvidenceTimelineSource.PAPER_OPERATION,
    "Paper Account": EvidenceTimelineSource.PAPER_ACCOUNT,
    "Market Data": EvidenceTimelineSource.MARKET_DATA,
    "Operations": EvidenceTimelineSource.OPERATIONS,
}


@dataclass(frozen=True, slots=True)
class EvidenceNavigationTarget:
    """One exact presentation-only target for the accepted Evidence Explorer."""

    source: EvidenceTimelineSource
    identifier: str

    def __post_init__(self) -> None:
        if type(self.source) is not EvidenceTimelineSource:
            raise TypeError("source must be an exact EvidenceTimelineSource")
        if type(self.identifier) is not str:
            raise TypeError("identifier must be an exact string")
        if not self.identifier or self.identifier != self.identifier.strip():
            raise ValueError("identifier must be non-empty canonical text")
        if len(self.identifier) > MAX_EVIDENCE_TIMELINE_FILTER_CHARACTERS:
            raise ValueError("identifier exceeds the Evidence search bound")
        if any(
            ord(character) < 0x20 or ord(character) == 0x7F
            for character in self.identifier
        ):
            raise ValueError("identifier contains unsupported control characters")


def build_evidence_navigation_target(
    entry: SystemAuditEntryView,
) -> EvidenceNavigationTarget | None:
    """Map one bounded System audit entry through the closed A12 source map."""
    if type(entry) is not SystemAuditEntryView:
        raise TypeError("entry must be an exact SystemAuditEntryView")

    source = _SYSTEM_SOURCE_TO_EVIDENCE.get(entry.source)
    if source is None or not _identifier_is_navigable(entry.identifier):
        return None
    return EvidenceNavigationTarget(source, entry.identifier)


def _identifier_is_navigable(identifier: str) -> bool:
    return (
        len(identifier) <= MAX_EVIDENCE_TIMELINE_FILTER_CHARACTERS
        and not any(
            ord(character) < 0x20 or ord(character) == 0x7F
            for character in identifier
        )
    )
