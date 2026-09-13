from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from trading_bot.market_calendar import TradingSession
from trading_bot.runtime.personal_desktop_unattended_daily_cycle_timing import (
    PERSONAL_DESKTOP_UNATTENDED_DAILY_CYCLE_TIMING_POLICY_VERSION,
    PersonalDesktopPreOpenDecisionEligibility,
    PersonalDesktopUnattendedDailyCycleTimingError,
    classify_pre_open_decision_eligibility,
    next_xnys_execution_session,
    xnys_regular_open,
)


@pytest.mark.parametrize(
    ("session_date", "expected_open"),
    [
        (date(2026, 1, 15), datetime(2026, 1, 15, 14, 30, tzinfo=UTC)),
        (date(2026, 7, 15), datetime(2026, 7, 15, 13, 30, tzinfo=UTC)),
        (date(2026, 3, 6), datetime(2026, 3, 6, 14, 30, tzinfo=UTC)),
        (date(2026, 3, 9), datetime(2026, 3, 9, 13, 30, tzinfo=UTC)),
    ],
)
def test_regular_open_uses_exchange_timezone_and_dst(
    session_date: date,
    expected_open: datetime,
) -> None:
    assert xnys_regular_open(TradingSession(session_date)) == expected_open


def test_timing_policy_version_is_frozen() -> None:
    assert (
        PERSONAL_DESKTOP_UNATTENDED_DAILY_CYCLE_TIMING_POLICY_VERSION
        == "xnys-regular-session-timing-v1"
    )


def test_next_session_skips_weekend() -> None:
    assert next_xnys_execution_session(
        TradingSession(date(2026, 3, 13))
    ) == TradingSession(date(2026, 3, 16))


def test_next_session_skips_exchange_holiday() -> None:
    assert next_xnys_execution_session(
        TradingSession(date(2026, 4, 2))
    ) == TradingSession(date(2026, 4, 6))


def test_early_close_session_keeps_regular_open_rule() -> None:
    session = TradingSession(date(2026, 11, 27))

    assert xnys_regular_open(session) == datetime(2026, 11, 27, 14, 30, tzinfo=UTC)


def test_next_session_can_be_early_close_session() -> None:
    assert next_xnys_execution_session(
        TradingSession(date(2026, 11, 25))
    ) == TradingSession(date(2026, 11, 27))


@pytest.mark.parametrize(
    "session_date",
    [
        date(2026, 3, 14),
        date(2026, 11, 26),
    ],
)
def test_unmodeled_session_is_rejected(session_date: date) -> None:
    with pytest.raises(
        PersonalDesktopUnattendedDailyCycleTimingError,
        match="not a modeled XNYS trading session",
    ):
        xnys_regular_open(TradingSession(session_date))


def test_out_of_range_session_is_rejected() -> None:
    with pytest.raises(
        PersonalDesktopUnattendedDailyCycleTimingError,
        match="outside the supported XNYS calendar",
    ):
        xnys_regular_open(TradingSession(date(2101, 1, 3)))


def test_pre_open_eligibility_is_strictly_before_regular_open() -> None:
    session = TradingSession(date(2026, 7, 15))

    assert classify_pre_open_decision_eligibility(
        session,
        datetime(2026, 7, 15, 13, 29, 59, 999999, tzinfo=UTC),
    ) is PersonalDesktopPreOpenDecisionEligibility.ELIGIBLE
    assert classify_pre_open_decision_eligibility(
        session,
        datetime(2026, 7, 15, 13, 30, tzinfo=UTC),
    ) is PersonalDesktopPreOpenDecisionEligibility.MISSED_DEADLINE
    assert classify_pre_open_decision_eligibility(
        session,
        datetime(2026, 7, 15, 13, 30, 0, 1, tzinfo=UTC),
    ) is PersonalDesktopPreOpenDecisionEligibility.MISSED_DEADLINE


def test_pre_open_eligibility_normalizes_aware_timestamp_to_utc() -> None:
    session = TradingSession(date(2026, 7, 15))
    los_angeles = ZoneInfo("America/Los_Angeles")
    local_observation = datetime(2026, 7, 15, 6, 29, tzinfo=los_angeles)
    utc_observation = datetime(2026, 7, 15, 13, 29, tzinfo=UTC)

    assert classify_pre_open_decision_eligibility(
        session, local_observation
    ) is classify_pre_open_decision_eligibility(session, utc_observation)


def test_naive_observed_timestamp_is_rejected() -> None:
    with pytest.raises(
        PersonalDesktopUnattendedDailyCycleTimingError,
        match="timezone-aware",
    ):
        classify_pre_open_decision_eligibility(
            TradingSession(date(2026, 7, 15)),
            datetime(2026, 7, 15, 13, 0),
        )


def test_non_session_type_is_rejected() -> None:
    with pytest.raises(
        PersonalDesktopUnattendedDailyCycleTimingError,
        match="exact TradingSession",
    ):
        xnys_regular_open(date(2026, 7, 15))  # type: ignore[arg-type]
