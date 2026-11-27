from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from trading_bot.domain import Bar, Symbol
from trading_bot.experiments.arch149_monthly_defensive_rotation import (
    STRATEGY_ID,
    replay_monthly_defensive_rotation,
    verify_rotation_replay_identity,
)
from trading_bot.experiments.filtered_trend_campaign import BASE_COSTS
from trading_bot.experiments.filtered_trend_data import (
    UNIVERSE,
    MultiAssetDataset,
    ProviderProvenance,
    SymbolDataset,
)
from trading_bot.experiments.historical_research_sessions import (
    published_historical_session_authority,
)
from trading_bot.portfolio_manager.arch149_adapter import (
    Arch149AuthorityStatus,
    Arch149EvidenceStatus,
    adapt_arch149_replay,
)

_NEW_YORK = ZoneInfo("America/New_York")


def _synthetic_arch149_dataset() -> MultiAssetDataset:
    """Construct fake in-memory prices on the frozen 2016–2023 session calendar."""
    sessions = tuple(
        session
        for session in published_historical_session_authority().sessions
        if date(2016, 1, 1) <= session < date(2024, 1, 1)
    )
    provenance = ProviderProvenance()
    datasets = []
    for symbol_index, symbol in enumerate(UNIVERSE):
        slope = Decimal(symbol_index) / Decimal(1000)
        bars = []
        for index, session in enumerate(sessions):
            close = Decimal(100) + slope * index
            timestamp = datetime.combine(session, time.min, _NEW_YORK).astimezone(UTC)
            bars.append(
                Bar(
                    Symbol(symbol),
                    timestamp,
                    close,
                    close + Decimal(1),
                    close - Decimal(1),
                    close,
                    1000,
                )
            )
        datasets.append(SymbolDataset(symbol, tuple(bars), provenance))
    return MultiAssetDataset(tuple(datasets))


def test_synthetic_arch149_targets_adapt_as_unadmitted_research_only_signals() -> None:
    replay = replay_monthly_defensive_rotation(
        _synthetic_arch149_dataset(), costs=BASE_COSTS
    )
    batch = adapt_arch149_replay(replay)
    repeated = adapt_arch149_replay(replay)

    assert verify_rotation_replay_identity(replay)
    assert batch.strategy_id == STRATEGY_ID
    assert batch.source_replay_id == replay.identity
    assert batch.target_sequence_identity == replay.target_sequence_identity
    assert batch.targets == replay.targets
    assert batch.identity == repeated.identity
    assert batch.evidence_status is Arch149EvidenceStatus.UNADMITTED
    assert (
        batch.authority_status
        is Arch149AuthorityStatus.RESEARCH_SIGNAL_ONLY_NO_ORDER_AUTHORITY
    )
    assert batch.performance_evidence_available is False
    assert batch.order_authority is False
    assert not hasattr(batch, "fills")
    assert not hasattr(batch, "daily_marks")

    first = batch.targets[0]
    assert first.target == "PDBC"
    assert batch.target_for(first.signal_date) == first
    signals = batch.market_signals_for(first.signal_date)
    assert tuple(signal.symbol.value for signal in signals) == UNIVERSE
    expected_scores = dict(first.ranked_scores)
    assert tuple((signal.symbol.value, signal.score) for signal in signals) == tuple(
        (symbol, expected_scores[symbol]) for symbol in UNIVERSE
    )
    assert all(signal.evidence_available is False for signal in signals)
    assert all("cannot authorize an order" in signal.rationale for signal in signals)


def test_arch149_adapter_rejects_untyped_replay_input() -> None:
    with pytest.raises(TypeError, match="exact RotationReplay"):
        adapt_arch149_replay(object())  # type: ignore[arg-type]
