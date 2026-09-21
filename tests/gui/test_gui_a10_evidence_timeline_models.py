"""GUI-A10 Evidence Timeline presentation-model tests."""

from datetime import UTC, datetime

import pytest

from trading_bot.gui import (
    EvidenceTimelineEntry,
    EvidenceTimelinePageState,
    EvidenceTimelineSource,
)


def _entry(
    *,
    identifier: str = "id-1",
    occurred_at: datetime | None = None,
    sha256: str | None = None,
) -> EvidenceTimelineEntry:
    return EvidenceTimelineEntry(
        EvidenceTimelineSource.MARKET_DATA,
        "Snapshot",
        identifier,
        occurred_at,
        sha256,
        "Bounded evidence detail.",
    )


def test_timeline_state_accepts_bounded_entries() -> None:
    timestamp = datetime(2026, 9, 20, 20, 0, tzinfo=UTC)
    state = EvidenceTimelinePageState(
        "One bounded entry.",
        (_entry(occurred_at=timestamp, sha256="a" * 64),),
    )

    assert state.entries[0].occurred_at == timestamp
    assert state.entries[0].sha256 == "a" * 64


@pytest.mark.parametrize("value", ("A" * 64, "short", ""))
def test_timeline_entry_rejects_invalid_sha256(value: str) -> None:
    with pytest.raises(ValueError):
        _entry(sha256=value)


def test_timeline_entry_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError):
        _entry(occurred_at=datetime(2026, 9, 20, 20, 0))


def test_timeline_state_rejects_duplicate_evidence_identity() -> None:
    entry = _entry()
    with pytest.raises(ValueError):
        EvidenceTimelinePageState("Duplicate evidence.", (entry, entry))
