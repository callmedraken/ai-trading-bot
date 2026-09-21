"""Pure presentation-only filtering for GUI-A11 Evidence Explorer."""

from __future__ import annotations

from dataclasses import dataclass

from trading_bot.gui.evidence_timeline_models import (
    EvidenceTimelineEntry,
    EvidenceTimelinePageState,
    EvidenceTimelineSource,
)

MAX_EVIDENCE_TIMELINE_FILTER_CHARACTERS = 200


@dataclass(frozen=True, slots=True)
class EvidenceTimelineFilter:
    """Bounded local-only filter state for already-built A10 timeline entries."""

    query: str = ""
    source: EvidenceTimelineSource | None = None

    def __post_init__(self) -> None:
        if type(self.query) is not str:
            raise TypeError("query must be an exact string")
        if len(self.query) > MAX_EVIDENCE_TIMELINE_FILTER_CHARACTERS:
            raise ValueError("query exceeds the presentation bound")
        if any(
            ord(character) < 0x20 or ord(character) == 0x7F for character in self.query
        ):
            raise ValueError("query contains unsupported control characters")
        if self.source is not None and type(self.source) is not EvidenceTimelineSource:
            raise TypeError("source must be an exact EvidenceTimelineSource or None")


def filter_evidence_timeline_entries(
    state: EvidenceTimelinePageState,
    filter_state: EvidenceTimelineFilter,
) -> tuple[EvidenceTimelineEntry, ...]:
    """Filter bounded evidence locally while preserving accepted A10 ordering."""
    if type(state) is not EvidenceTimelinePageState:
        raise TypeError("state must be an exact EvidenceTimelinePageState")
    if type(filter_state) is not EvidenceTimelineFilter:
        raise TypeError("filter_state must be an exact EvidenceTimelineFilter")

    query = filter_state.query.strip().casefold()
    matches: list[EvidenceTimelineEntry] = []
    for entry in state.entries:
        if filter_state.source is not None and entry.source is not filter_state.source:
            continue
        if query and query not in _searchable_text(entry):
            continue
        matches.append(entry)
    return tuple(matches)


def _searchable_text(entry: EvidenceTimelineEntry) -> str:
    timestamp = (
        entry.occurred_at.isoformat()
        if entry.occurred_at is not None
        else "Untimed presentation evidence"
    )
    return "\n".join(
        (
            entry.source.value,
            entry.title,
            entry.identifier,
            entry.sha256 or "",
            entry.detail,
            timestamp,
        )
    ).casefold()
