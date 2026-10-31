from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Event

import pytest

from trading_bot.desktop_paper.observations import (
    OpenReplayObservationSource,
    PaperObservation,
    PaperObservationExhausted,
    PaperObservationStatus,
)
from trading_bot.domain import Bar, Symbol
from trading_bot.experiments.historical_research_desktop import DesktopResearchStorage
from trading_bot.market_data.models import (
    HistoricalDataRequest,
    HistoricalDataResult,
)


def _bar(
    symbol: Symbol,
    day: int,
    *,
    open_value: str = "10",
    high_value: str = "12",
    low_value: str = "9",
    close_value: str = "11",
    volume: int = 100,
) -> Bar:
    return Bar(
        symbol=symbol,
        timestamp=datetime(2025, 1, day, tzinfo=UTC),
        open=Decimal(open_value),
        high=Decimal(high_value),
        low=Decimal(low_value),
        close=Decimal(close_value),
        volume=volume,
    )


def _bars(symbol: Symbol | None = None) -> tuple[Bar, ...]:
    symbol = Symbol("SYNTH") if symbol is None else symbol
    return tuple(
        _bar(
            symbol,
            day,
            open_value=str(10 + day),
            high_value=str(12 + day),
            low_value=str(9 + day),
            close_value=str(11 + day),
            volume=100 + day,
        )
        for day in range(1, 5)
    )


def _source(
    bars: tuple[Bar, ...] | list[Bar] | None = None,
    *,
    symbol: Symbol | None = None,
    minimum_history_bars: int = 2,
) -> OpenReplayObservationSource:
    symbol = Symbol("SYNTH") if symbol is None else symbol
    return OpenReplayObservationSource.from_bars(
        _bars(symbol) if bars is None else bars,
        symbol=symbol,
        minimum_history_bars=minimum_history_bars,
    )


def test_replay_exposes_prior_completed_history_and_current_open_only() -> None:
    bars = _bars()
    source = _source(bars, minimum_history_bars=2)

    first = source.next_observation()
    second = source.next_observation()
    third = source.next_observation()

    assert isinstance(first, PaperObservation)
    assert first.status is PaperObservationStatus.WARMUP
    assert first.warmup is True
    assert first.completed_history == ()
    assert first.completed_history_cutoff == ""
    assert first.observation_open == bars[0].open
    assert first.executed_at == bars[0].timestamp
    assert not hasattr(first, "execution_bar")
    assert not hasattr(first, "close")
    assert not hasattr(first, "high")
    assert not hasattr(first, "low")

    assert isinstance(second, PaperObservation)
    assert second.status is PaperObservationStatus.WARMUP
    assert second.completed_history == (bars[0],)
    assert second.completed_history_cutoff == bars[0].timestamp.isoformat()

    assert isinstance(third, PaperObservation)
    assert third.status is PaperObservationStatus.READY
    assert third.warmup is False
    assert third.completed_history == bars[:2]
    assert third.completed_history[-1].timestamp < third.executed_at
    assert third.completed_history_cutoff == bars[1].timestamp.isoformat()
    assert third.observation_open == bars[2].open


def test_observation_identity_uses_completed_history_and_current_open_only() -> None:
    symbol = Symbol("SYNTH")
    original = _bars(symbol)
    changed_execution_bar = _bar(
        symbol,
        1,
        open_value=str(original[0].open),
        high_value="99",
        low_value="8",
        close_value="90",
        volume=999,
    )

    original_first = _source(
        (original[0],), symbol=symbol, minimum_history_bars=1
    ).next_observation()
    changed_first = _source(
        (changed_execution_bar,), symbol=symbol, minimum_history_bars=1
    ).next_observation()

    assert isinstance(original_first, PaperObservation)
    assert isinstance(changed_first, PaperObservation)
    assert original_first.observation_id == changed_first.observation_id
    assert original_first.source_identity_digest == changed_first.source_identity_digest

    original_second = _source(original[:2], symbol=symbol, minimum_history_bars=1)
    changed_prior = replace(original[0], close=Decimal("11.5"))
    changed_second = _source(
        (changed_prior, original[1]), symbol=symbol, minimum_history_bars=1
    )
    original_second.next_observation()
    changed_second.next_observation()
    original_observation = original_second.next_observation()
    changed_observation = changed_second.next_observation()

    assert isinstance(original_observation, PaperObservation)
    assert isinstance(changed_observation, PaperObservation)
    assert original_observation.observation_id != changed_observation.observation_id
    assert (
        original_observation.execution_session_id
        != changed_observation.execution_session_id
    )


def test_resume_starts_after_durable_cursor_and_never_rewinds() -> None:
    source = _source(minimum_history_bars=2)
    source.seek_after(2)

    observation = source.next_observation()

    assert isinstance(observation, PaperObservation)
    assert observation.execution_index == 3
    assert observation.completed_history == _bars()[:2]
    assert observation.status is PaperObservationStatus.READY
    assert source.cursor == 3
    with pytest.raises(ValueError, match="cannot rewind"):
        source.seek_after(2)
    assert source.cursor == 3


def test_exhaustion_is_visible_stable_and_does_not_advance_cursor() -> None:
    source = _source(minimum_history_bars=1)
    for _ in range(4):
        source.next_observation()

    exhausted = source.next_observation()
    repeated = source.next_observation()

    assert isinstance(exhausted, PaperObservationExhausted)
    assert exhausted.status is PaperObservationStatus.EXHAUSTED
    assert exhausted.total_sessions == 4
    assert exhausted.consumed_execution_index == 4
    assert repeated == exhausted
    assert source.status is PaperObservationStatus.EXHAUSTED
    assert source.cursor == 4


def test_empty_source_is_immediately_exhausted() -> None:
    source = _source([], minimum_history_bars=1)

    result = source.next_observation()

    assert isinstance(result, PaperObservationExhausted)
    assert source.status is PaperObservationStatus.EXHAUSTED


def test_invalid_execution_open_is_rejected() -> None:
    invalid = _bar(Symbol("SYNTH"), 1)
    object.__setattr__(invalid, "open", Decimal("0"))

    with pytest.raises(ValueError, match="greater than zero"):
        _source((invalid,), minimum_history_bars=1)


@pytest.mark.parametrize("minimum_history_bars", [0, -1, True])
def test_warmup_requirement_must_be_positive_integer(
    minimum_history_bars: int,
) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        _source(minimum_history_bars=minimum_history_bars)


def test_wait_is_interruptible() -> None:
    stop_event = Event()
    stop_event.set()

    assert _source().wait_interruptibly(stop_event, Decimal("10")) is False
    assert _source().wait_interruptibly(Event(), 0) is True


def test_storage_adapter_calls_only_the_public_open_loader(
    tmp_path, monkeypatch
) -> None:
    from trading_bot.experiments import historical_research_desktop

    symbol = Symbol("SPY")
    bars = _bars(symbol)
    data = HistoricalDataResult(
        request=HistoricalDataRequest(
            symbol=symbol,
            start=bars[0].timestamp,
            end=bars[-1].timestamp + timedelta(days=1),
        ),
        bars=bars,
        provider_name="offline-open-fixture",
    )
    storage = DesktopResearchStorage.for_test(tmp_path / "research")
    calls: list[DesktopResearchStorage] = []

    def load_open(value: DesktopResearchStorage) -> HistoricalDataResult:
        calls.append(value)
        return data

    monkeypatch.setattr(
        historical_research_desktop, "load_desktop_open_research", load_open
    )

    source = OpenReplayObservationSource.from_storage(
        storage, symbol=symbol, minimum_history_bars=2
    )

    assert calls == [storage]
    observation = source.next_observation()
    assert isinstance(observation, PaperObservation)
    assert observation.symbol == symbol


def test_storage_adapter_rejects_symbol_different_from_open_projection(
    tmp_path, monkeypatch
) -> None:
    from trading_bot.experiments import historical_research_desktop

    loaded_symbol = Symbol("SPY")
    bars = _bars(loaded_symbol)
    data = HistoricalDataResult(
        request=HistoricalDataRequest(
            symbol=loaded_symbol,
            start=bars[0].timestamp,
            end=bars[-1].timestamp + timedelta(days=1),
        ),
        bars=bars,
        provider_name="offline-open-fixture",
    )
    storage = DesktopResearchStorage.for_test(tmp_path / "research")
    monkeypatch.setattr(
        historical_research_desktop, "load_desktop_open_research", lambda _: data
    )

    with pytest.raises(ValueError, match="requested symbol"):
        OpenReplayObservationSource.from_storage(
            storage, symbol=Symbol("QQQ"), minimum_history_bars=2
        )


def test_source_accepts_generic_symbols_without_a_spy_default() -> None:
    symbol = Symbol("QQQ")
    source = _source(_bars(symbol), symbol=symbol, minimum_history_bars=1)

    observation = source.next_observation()

    assert isinstance(observation, PaperObservation)
    assert observation.symbol == symbol
