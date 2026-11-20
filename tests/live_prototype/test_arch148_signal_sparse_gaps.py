"""Focused fake-only checks for sparse Architecture 148 signal history."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from trading_bot.live_runtime.models import (
    CompletedBar,
    MarketQuality,
    MarketSnapshot,
)
from trading_bot.live_runtime.strategy import (
    _CompletedBarSignalStream,
    analyze_market,
)
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)

_NEW_YORK = ZoneInfo("America/New_York")
_PRIOR_DAY = datetime(2026, 11, 17, 9, 30, tzinfo=_NEW_YORK)
_CURRENT_DAY = datetime(2026, 11, 18, 9, 30, tzinfo=_NEW_YORK)


def _bar(timestamp: datetime, ordinal: int) -> CompletedBar:
    close = Decimal("100") + Decimal(ordinal) / Decimal("10")
    return CompletedBar(
        timestamp,
        close,
        close + Decimal("1"),
        close - Decimal("1"),
        close,
        100,
    )


def _market(
    *,
    prior_indices: range | tuple[int, ...] = range(78),
    current_indices: range | tuple[int, ...] = range(55),
    current_as_of_index: int = 55,
) -> MarketSnapshot:
    bars: list[CompletedBar] = []
    ordinal = 0
    for index in prior_indices:
        bars.append(_bar(_PRIOR_DAY + timedelta(minutes=5 * index), ordinal))
        ordinal += 1
    for index in current_indices:
        bars.append(_bar(_CURRENT_DAY + timedelta(minutes=5 * index), ordinal))
        ordinal += 1
    as_of = _CURRENT_DAY + timedelta(minutes=5 * current_as_of_index)
    return MarketSnapshot(as_of, tuple(bars), (), {})


def test_prior_session_sparse_gap_and_missing_tail_do_not_block_current_signal() -> (
    None
):
    prior_indices = tuple(index for index in range(78) if index not in (12, 77))
    result = analyze_market(_market(prior_indices=prior_indices))

    assert result.quality is MarketQuality.READY
    assert result.latest is not None
    assert result.previous is not None
    assert result.latest.bar_end - result.previous.bar_end == timedelta(minutes=5)


def test_current_session_internal_gap_blocks_even_an_adjacent_latest_pair() -> None:
    current_indices = tuple(index for index in range(56) if index != 20)
    result = analyze_market(
        _market(current_indices=current_indices, current_as_of_index=56)
    )

    assert result.quality is MarketQuality.GAP
    assert result.reason == "NONCONTIGUOUS_CURRENT_SESSION_BARS"


def test_missing_latest_completed_current_bar_is_gap_not_entry_ready() -> None:
    current_indices = tuple(index for index in range(55) if index != 54)
    result = analyze_market(
        _market(current_indices=current_indices, current_as_of_index=55)
    )

    assert result.quality is MarketQuality.GAP
    assert result.reason == "MISSING_LATEST_COMPLETED_BAR"


def test_entirely_missing_prior_session_remains_a_history_gap() -> None:
    monday = datetime(2026, 11, 16, 9, 30, tzinfo=_NEW_YORK)
    bars = tuple(
        _bar(monday + timedelta(minutes=5 * index), index) for index in range(78)
    ) + tuple(
        _bar(_CURRENT_DAY + timedelta(minutes=5 * index), 78 + index)
        for index in range(55)
    )
    as_of = _CURRENT_DAY + timedelta(minutes=275)

    result = analyze_market(MarketSnapshot(as_of, bars, (), {}))

    assert result.quality is MarketQuality.GAP
    assert result.reason == "MISSING_PUBLISHED_SESSION"


def test_incremental_signal_stream_matches_batch_analysis_for_sparse_history() -> None:
    history = [
        _bar(_PRIOR_DAY + timedelta(minutes=5 * index), ordinal)
        for ordinal, index in enumerate(
            index for index in range(78) if index not in (12, 77)
        )
    ]
    current_ordinal = len(history)
    history.extend(
        _bar(_CURRENT_DAY + timedelta(minutes=5 * index), current_ordinal + index)
        for index in range(55)
    )
    stream = _CompletedBarSignalStream(NYSEPublishedRegularSessionAuthority())
    prefix: list[CompletedBar] = []

    for bar in history:
        stream.append(bar)
        prefix.append(bar)
        as_of = bar.ends_at
        batch = analyze_market(MarketSnapshot(as_of, tuple(prefix), (), {}))
        assert stream.analyze(as_of) == batch
