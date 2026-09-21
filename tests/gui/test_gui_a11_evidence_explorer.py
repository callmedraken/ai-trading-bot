"""GUI-A11 pure Evidence Explorer filter tests."""

from datetime import UTC, datetime

import pytest

from trading_bot.gui import (
    EvidenceTimelineEntry,
    EvidenceTimelineFilter,
    EvidenceTimelinePageState,
    EvidenceTimelineSource,
    filter_evidence_timeline_entries,
)


def _state() -> EvidenceTimelinePageState:
    return EvidenceTimelinePageState(
        "Three entries.",
        (
            EvidenceTimelineEntry(
                EvidenceTimelineSource.MARKET_DATA,
                "Verified snapshot",
                "snapshot-one",
                datetime(2026, 9, 20, 20, 0, tzinfo=UTC),
                "a" * 64,
                "XNYS session 2026-09-20.",
            ),
            EvidenceTimelineEntry(
                EvidenceTimelineSource.RESEARCH,
                "Research report",
                "report-one",
                None,
                None,
                "Loaded compact report.",
            ),
            EvidenceTimelineEntry(
                EvidenceTimelineSource.MARKET_DATA,
                "Older snapshot",
                "snapshot-two",
                datetime(2026, 9, 19, 20, 0, tzinfo=UTC),
                "b" * 64,
                "XNYS session 2026-09-19.",
            ),
        ),
    )


def test_filter_model_enforces_exact_bounded_inputs() -> None:
    assert EvidenceTimelineFilter() == EvidenceTimelineFilter("", None)

    with pytest.raises(TypeError):
        EvidenceTimelineFilter(query=object())  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        EvidenceTimelineFilter(query="x" * 201)
    with pytest.raises(ValueError):
        EvidenceTimelineFilter(query="bad\nquery")
    with pytest.raises(TypeError):
        EvidenceTimelineFilter(source="Research")  # type: ignore[arg-type]


def test_source_filter_preserves_original_timeline_order() -> None:
    state = _state()

    entries = filter_evidence_timeline_entries(
        state,
        EvidenceTimelineFilter(source=EvidenceTimelineSource.MARKET_DATA),
    )

    assert tuple(entry.identifier for entry in entries) == (
        "snapshot-one",
        "snapshot-two",
    )


@pytest.mark.parametrize(
    ("query", "expected"),
    (
        ("REPORT", ("report-one",)),
        ("xnys session 2026-09-19", ("snapshot-two",)),
        ("B" * 64, ("snapshot-two",)),
        ("2026-09-20T20:00", ("snapshot-one",)),
        ("", ("snapshot-one", "report-one", "snapshot-two")),
        ("   ", ("snapshot-one", "report-one", "snapshot-two")),
    ),
)
def test_text_filter_is_case_insensitive_and_uses_visible_fields(
    query: str,
    expected: tuple[str, ...],
) -> None:
    state = _state()

    entries = filter_evidence_timeline_entries(
        state,
        EvidenceTimelineFilter(query=query),
    )

    assert tuple(entry.identifier for entry in entries) == expected


def test_source_and_text_filters_compose_without_reordering() -> None:
    state = _state()

    entries = filter_evidence_timeline_entries(
        state,
        EvidenceTimelineFilter(
            query="snapshot",
            source=EvidenceTimelineSource.MARKET_DATA,
        ),
    )

    assert tuple(entry.identifier for entry in entries) == (
        "snapshot-one",
        "snapshot-two",
    )
