"""Qt-free GUI-A13 targets for Evidence -> source-page navigation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from trading_bot.gui.evidence_timeline_models import (
    EvidenceTimelineEntry,
    EvidenceTimelineSource,
)


class EvidenceSourcePage(Enum):
    """Closed destination pages for already-presented Evidence sources."""

    RESEARCH = "research"
    PAPER_OPERATION = "paper"
    PAPER_ACCOUNT = "paper-account"
    MARKET_DATA = "market-data"
    OPERATIONS = "operations"


_SOURCE_TO_PAGE = {
    EvidenceTimelineSource.RESEARCH: EvidenceSourcePage.RESEARCH,
    EvidenceTimelineSource.PAPER_OPERATION: EvidenceSourcePage.PAPER_OPERATION,
    EvidenceTimelineSource.PAPER_ACCOUNT: EvidenceSourcePage.PAPER_ACCOUNT,
    EvidenceTimelineSource.MARKET_DATA: EvidenceSourcePage.MARKET_DATA,
    EvidenceTimelineSource.OPERATIONS: EvidenceSourcePage.OPERATIONS,
}


@dataclass(frozen=True, slots=True)
class EvidenceSourcePageTarget:
    """Presentation-only destination derived from one Evidence source."""

    source: EvidenceTimelineSource
    page_id: EvidenceSourcePage

    def __post_init__(self) -> None:
        if type(self.source) is not EvidenceTimelineSource:
            raise TypeError("source must be an exact EvidenceTimelineSource")
        if type(self.page_id) is not EvidenceSourcePage:
            raise TypeError("page_id must be an exact EvidenceSourcePage")
        if _SOURCE_TO_PAGE[self.source] is not self.page_id:
            raise ValueError("source and page_id do not match the closed mapping")


def build_evidence_source_page_target(
    entry: EvidenceTimelineEntry,
) -> EvidenceSourcePageTarget:
    """Map one already-presented Evidence entry to its existing source page."""
    if type(entry) is not EvidenceTimelineEntry:
        raise TypeError("entry must be an exact EvidenceTimelineEntry")
    return EvidenceSourcePageTarget(entry.source, _SOURCE_TO_PAGE[entry.source])
