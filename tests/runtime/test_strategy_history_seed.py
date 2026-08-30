"""Focused Architecture-94 P1 history-seed coverage."""

import json
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from tests.market_data.daily_snapshot_test_support import SPY, calendar

from trading_bot.domain import Bar, Symbol
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    CalendarDescriptor,
    DailySnapshotBar,
)
from trading_bot.runtime import (
    MAX_STRATEGY_HISTORY_SEED_BYTES,
    StrategyHistorySeed,
    StrategyHistorySeedSerializationError,
    StrategyHistorySeedSourceDescriptor,
    StrategyHistorySeedVerificationError,
    create_strategy_history_seed,
    parse_strategy_history_seed,
    serialize_strategy_history_seed,
    verify_strategy_history_seed,
)
from trading_bot.strategies import MovingAverageCrossoverConfig

_SOURCE = StrategyHistorySeedSourceDescriptor("focused-offline-seed")
_CONFIG = MovingAverageCrossoverConfig(2, 3, Decimal("2"))
_TARGET = TradingSession(date(2025, 1, 6))
_SESSIONS = (date(2024, 12, 31), date(2025, 1, 2), date(2025, 1, 3))


def _bar(session_date: date, close: str = "10", *, symbol=SPY) -> DailySnapshotBar:
    price = Decimal(close)
    return DailySnapshotBar(
        TradingSession(session_date),
        Bar(
            symbol,
            datetime.combine(session_date, time(), tzinfo=UTC) + timedelta(hours=5),
            price,
            price + Decimal("1"),
            price - Decimal("1"),
            price,
            100,
        ),
    )


def _seed(
    sessions: tuple[date, ...] = _SESSIONS,
    closes: tuple[str, ...] = ("10", "10", "9"),
) -> StrategyHistorySeed:
    return create_strategy_history_seed(
        symbol=SPY,
        source=_SOURCE,
        bars=tuple(
            _bar(day, close) for day, close in zip(sessions, closes, strict=True)
        ),
    )


def _payload(**kwargs) -> bytes:
    return serialize_strategy_history_seed(_seed(**kwargs))


def test_canonical_round_trip_deterministic_uuid_and_detached_evidence() -> None:
    first = _seed()
    equivalent = _seed()
    payload = serialize_strategy_history_seed(first)

    assert first.seed_id == equivalent.seed_id
    assert parse_strategy_history_seed(payload) == first
    verified = verify_strategy_history_seed(
        payload,
        expected_symbol=SPY,
        target_session=_TARGET,
        strategy_config=_CONFIG,
        calendar=calendar(),
    )
    assert verified.seed == first
    assert verified.artifact_byte_length == len(payload) > 0
    assert len(verified.artifact_sha256) == 64
    assert str(first.seed_id).encode() in payload
    assert verified.artifact_sha256.encode() not in payload


def test_seed_identity_changes_with_semantic_history() -> None:
    assert _seed().seed_id != _seed(closes=("10", "10", "8")).seed_id


def test_enforces_one_symbol_and_exact_xnys_calendar() -> None:
    qqq = Symbol("QQQ")
    with pytest.raises(StrategyHistorySeedVerificationError, match="one declared"):
        create_strategy_history_seed(
            symbol=SPY,
            source=_SOURCE,
            bars=(_bar(_SESSIONS[0]), _bar(_SESSIONS[1], symbol=qqq)),
        )

    seed = _seed()
    with pytest.raises(StrategyHistorySeedVerificationError, match="exact supported"):
        replace(
            seed,
            calendar=CalendarDescriptor("XNYS", "wrong", "America/New_York"),
        )
    assert seed.calendar == XNYS_CALENDAR_DESCRIPTOR


@pytest.mark.parametrize(
    "sessions",
    (
        (date(2025, 1, 2), date(2024, 12, 31), date(2025, 1, 3)),
        (date(2024, 12, 31), date(2025, 1, 2), date(2025, 1, 2)),
    ),
)
def test_rejects_unordered_or_duplicate_sessions(sessions: tuple[date, ...]) -> None:
    with pytest.raises(
        StrategyHistorySeedVerificationError, match="strictly increasing"
    ):
        _seed(sessions=sessions)


def test_requires_immediate_predecessor() -> None:
    payload = _payload(
        sessions=(date(2024, 12, 30), date(2024, 12, 31), date(2025, 1, 2))
    )
    with pytest.raises(StrategyHistorySeedVerificationError, match="immediately"):
        verify_strategy_history_seed(
            payload,
            expected_symbol=SPY,
            target_session=_TARGET,
            strategy_config=_CONFIG,
            calendar=calendar(),
        )


def test_requires_consecutive_configured_long_window_suffix() -> None:
    payload = _payload(
        sessions=(date(2024, 12, 30), date(2025, 1, 2), date(2025, 1, 3))
    )
    with pytest.raises(StrategyHistorySeedVerificationError, match="consecutive"):
        verify_strategy_history_seed(
            payload,
            expected_symbol=SPY,
            target_session=_TARGET,
            strategy_config=_CONFIG,
            calendar=calendar(),
        )


@pytest.mark.parametrize(
    "sessions",
    (
        (date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)),
        (date(2025, 1, 3), date(2025, 1, 6), date(2025, 1, 7)),
    ),
)
def test_rejects_equal_or_future_target_sessions(sessions: tuple[date, ...]) -> None:
    with pytest.raises(StrategyHistorySeedVerificationError, match="strictly precede"):
        verify_strategy_history_seed(
            _payload(sessions=sessions),
            expected_symbol=SPY,
            target_session=_TARGET,
            strategy_config=_CONFIG,
            calendar=calendar(),
        )


def test_rejects_wrong_expected_symbol_and_insufficient_history() -> None:
    with pytest.raises(StrategyHistorySeedVerificationError, match="symbol"):
        verify_strategy_history_seed(
            _payload(),
            expected_symbol=Symbol("QQQ"),
            target_session=_TARGET,
            strategy_config=_CONFIG,
            calendar=calendar(),
        )
    with pytest.raises(StrategyHistorySeedVerificationError, match="long-window"):
        verify_strategy_history_seed(
            serialize_strategy_history_seed(
                create_strategy_history_seed(
                    symbol=SPY,
                    source=_SOURCE,
                    bars=(_bar(date(2025, 1, 3)),),
                )
            ),
            expected_symbol=SPY,
            target_session=_TARGET,
            strategy_config=_CONFIG,
            calendar=calendar(),
        )


def test_rejects_temporally_invalid_bar() -> None:
    wrong_timestamp = DailySnapshotBar(
        TradingSession(date(2025, 1, 3)),
        Bar(
            SPY,
            datetime(2025, 1, 2, 5, tzinfo=UTC),
            Decimal("10"),
            Decimal("11"),
            Decimal("9"),
            Decimal("10"),
            100,
        ),
    )
    with pytest.raises(StrategyHistorySeedVerificationError, match="timestamp"):
        create_strategy_history_seed(
            symbol=SPY,
            source=_SOURCE,
            bars=(_bar(_SESSIONS[0]), _bar(_SESSIONS[1]), wrong_timestamp),
        )


def test_strict_parser_rejects_malformed_extra_duplicate_and_noncanonical() -> None:
    payload = _payload()
    tree = json.loads(payload)
    tree["extra"] = True
    extra = (json.dumps(tree, sort_keys=True, separators=(",", ":")) + "\n").encode()
    duplicate = payload.replace(
        b'"schema":"strategy-history-seed/v1"',
        b'"schema":"strategy-history-seed/v1","schema":"strategy-history-seed/v1"',
    )
    noncanonical = json.dumps(json.loads(payload), indent=2).encode() + b"\n"

    for candidate in (b"{}", extra, duplicate, noncanonical, payload[:-1]):
        with pytest.raises(StrategyHistorySeedSerializationError):
            parse_strategy_history_seed(candidate)


def test_strict_parser_rejects_invalid_bar_and_over_bound_payload() -> None:
    tree = json.loads(_payload())
    tree["bars"][0]["high"] = "1"
    invalid = (json.dumps(tree, sort_keys=True, separators=(",", ":")) + "\n").encode()
    with pytest.raises(StrategyHistorySeedSerializationError):
        parse_strategy_history_seed(invalid)
    with pytest.raises(StrategyHistorySeedSerializationError, match="byte bound"):
        parse_strategy_history_seed(b"x" * (MAX_STRATEGY_HISTORY_SEED_BYTES + 1))


def test_rejects_tampered_seed_id() -> None:
    payload = _payload()
    tampered = payload.replace(str(_seed().seed_id).encode(), str(UUID(int=1)).encode())
    with pytest.raises(StrategyHistorySeedVerificationError, match="seed_id"):
        parse_strategy_history_seed(tampered)
