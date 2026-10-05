"""Architecture 131-S frozen published-session authority contract."""

import ast
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import trading_bot.review_paper.nyse_published_regular_sessions as module
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
    UnsupportedNYSEPublishedSessionYearError,
)
from trading_bot.review_paper.session_admission import (
    ReviewPaperSessionSchedule,
    ReviewPaperSessionStatus,
    admit_review_paper_session,
)

AUTHORITY = NYSEPublishedRegularSessionAuthority()
NY = ZoneInfo("America/New_York")
CLOSURES = tuple(
    date.fromisoformat(value)
    for value in (
        "2026-01-01",
        "2026-01-19",
        "2026-02-16",
        "2026-04-03",
        "2026-05-25",
        "2026-06-19",
        "2026-07-03",
        "2026-09-07",
        "2026-11-26",
        "2026-12-25",
        "2027-01-01",
        "2027-01-18",
        "2027-02-15",
        "2027-03-26",
        "2027-05-31",
        "2027-06-18",
        "2027-07-05",
        "2027-09-06",
        "2027-11-25",
        "2027-12-24",
        "2028-01-17",
        "2028-02-21",
        "2028-04-14",
        "2028-05-29",
        "2028-06-19",
        "2028-07-04",
        "2028-09-04",
        "2028-11-23",
        "2028-12-25",
    )
)
EARLY_CLOSES = tuple(
    date.fromisoformat(value)
    for value in (
        "2026-11-27",
        "2026-12-24",
        "2027-11-26",
        "2028-07-03",
        "2028-11-24",
    )
)


def _assert_schedule(day, close_hour, utc_open_hour, utc_close_hour):
    schedule = AUTHORITY.schedule_for(day)
    assert type(schedule) is ReviewPaperSessionSchedule
    assert schedule.session_date == day
    assert schedule.opens_at == datetime.combine(day, time(utc_open_hour, 30), UTC)
    assert schedule.closes_at == datetime.combine(day, time(utc_close_hour), UTC)
    assert schedule.opens_at.tzinfo is UTC and schedule.closes_at.tzinfo is UTC
    assert schedule.opens_at.astimezone(NY) == datetime.combine(day, time(9, 30), NY)
    assert schedule.closes_at.astimezone(NY) == datetime.combine(
        day, time(close_hour), NY
    )
    assert schedule == AUTHORITY.schedule_for(day)
    # The returned accepted 131-M model is directly consumable by admission.
    admitted = admit_review_paper_session(
        schedule=schedule,
        as_of=schedule.opens_at + timedelta(minutes=15),
        opening_buffer=timedelta(minutes=15),
        closing_buffer=timedelta(minutes=15),
    )
    assert admitted.status is ReviewPaperSessionStatus.ADMITTED
    return schedule


@pytest.mark.parametrize("day", CLOSURES, ids=str)
def test_every_frozen_full_market_closure(day):
    assert AUTHORITY.schedule_for(day) is None


@pytest.mark.parametrize("day", EARLY_CLOSES, ids=str)
def test_every_frozen_early_close(day):
    utc_open_hour, utc_close_hour = (13, 17) if day == date(2028, 7, 3) else (14, 18)
    _assert_schedule(day, 13, utc_open_hour, utc_close_hour)


@pytest.mark.parametrize(
    "day,utc_open_hour,utc_close_hour",
    [
        (date(2026, 1, 5), 14, 21),
        (date(2026, 7, 6), 13, 20),
        (date(2027, 1, 4), 14, 21),
        (date(2027, 7, 6), 13, 20),
        (date(2028, 1, 3), 14, 21),
        (date(2028, 7, 5), 13, 20),
        (date(2026, 3, 6), 14, 21),
        (date(2026, 3, 9), 13, 20),
        (date(2026, 10, 30), 13, 20),
        (date(2026, 11, 2), 14, 21),
    ],
)
def test_ordinary_sessions_and_dst_transitions(day, utc_open_hour, utc_close_hour):
    _assert_schedule(day, 16, utc_open_hour, utc_close_hour)


@pytest.mark.parametrize(
    "day",
    [
        date(2026, 1, 3),
        date(2026, 1, 4),
        date(2027, 7, 3),
        date(2027, 7, 4),
        date(2028, 1, 1),
        date(2028, 1, 2),
    ],
)
def test_weekends(day):
    assert AUTHORITY.schedule_for(day) is None


def test_2028_new_year_does_not_invent_an_observed_closure():
    assert AUTHORITY.schedule_for(date(2028, 1, 1)) is None
    _assert_schedule(date(2027, 12, 31), 16, 14, 21)
    _assert_schedule(date(2028, 1, 3), 16, 14, 21)


@pytest.mark.parametrize(
    "day,closed",
    [
        (date(2026, 1, 1), True),
        (date(2026, 12, 31), False),
        (date(2027, 1, 1), True),
        (date(2027, 12, 31), False),
        (date(2028, 1, 1), True),
        (date(2028, 12, 31), True),
    ],
)
def test_supported_year_boundaries(day, closed):
    assert (AUTHORITY.schedule_for(day) is None) is closed


@pytest.mark.parametrize(
    "day",
    [
        date(1, 1, 1),
        date(2025, 12, 31),
        date(2025, 12, 27),
        date(2029, 1, 1),
        date(2029, 1, 6),
        date(9999, 12, 31),
    ],
)
def test_unsupported_years_fail_before_weekend_or_holiday_classification(day):
    with pytest.raises(UnsupportedNYSEPublishedSessionYearError, match=str(day.year)):
        AUTHORITY.schedule_for(day)


class _DateSubclass(date):
    pass


@pytest.mark.parametrize(
    "value",
    [
        None,
        "2026-01-05",
        20260105,
        True,
        object(),
        datetime(2026, 1, 5),
        datetime(2026, 1, 5, tzinfo=UTC),
        datetime(2025, 12, 31),
        _DateSubclass(2026, 1, 5),
    ],
)
def test_input_is_exact_date_and_rejects_datetime_and_subclasses(value):
    with pytest.raises(TypeError, match="session_date must be exactly date"):
        AUTHORITY.schedule_for(value)


def test_exact_frozen_manifest_and_identity():
    assert AUTHORITY.source_name == "NYSE"
    assert AUTHORITY.source_scope == "NYSE core equity regular session"
    assert AUTHORITY.manifest_version == "nyse-published-regular-sessions-2026-2028/v1"
    assert AUTHORITY.supported_years == (2026, 2027, 2028)
    assert AUTHORITY.source_as_of == date(2026, 10, 4)
    assert module._FULL_MARKET_CLOSURES == frozenset(CLOSURES)
    assert module._EARLY_CLOSES == frozenset(EARLY_CLOSES)
    assert type(module._FULL_MARKET_CLOSURES) is frozenset
    assert type(module._EARLY_CLOSES) is frozenset
    assert module._NEW_YORK.key == "America/New_York"
    assert not hasattr(AUTHORITY, "__dict__")
    for name in (
        "source_name",
        "source_scope",
        "manifest_version",
        "supported_years",
        "source_as_of",
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(AUTHORITY, name, None)
        with pytest.raises(FrozenInstanceError):
            delattr(AUTHORITY, name)
        with pytest.raises(TypeError):
            NYSEPublishedRegularSessionAuthority(**{name: None})
        with pytest.raises((TypeError, ValueError), match="init=False"):
            replace(AUTHORITY, **{name: None})


def test_entire_supported_range_has_no_inferred_closures_or_early_closes():
    day = date(2026, 1, 1)
    while day.year <= 2028:
        schedule = AUTHORITY.schedule_for(day)
        if day.weekday() >= 5 or day in CLOSURES:
            assert schedule is None
        else:
            assert type(schedule) is ReviewPaperSessionSchedule
            assert schedule.opens_at.astimezone(NY).time() == time(9, 30)
            assert schedule.closes_at.astimezone(NY).time() == (
                time(13) if day in EARLY_CLOSES else time(16)
            )
        day += timedelta(days=1)


def _assert_closed_published_session_surface(source):
    imports = {}
    for node in ast.walk(ast.parse(source)):
        assert not isinstance(
            node,
            (
                ast.Import,
                ast.For,
                ast.While,
                ast.AsyncFor,
                ast.With,
                ast.AsyncWith,
                ast.Try,
                ast.Await,
                ast.AsyncFunctionDef,
                ast.Lambda,
                ast.Global,
                ast.Nonlocal,
                ast.Delete,
                ast.ListComp,
                ast.SetComp,
                ast.DictComp,
                ast.GeneratorExp,
                ast.Yield,
                ast.YieldFrom,
            ),
        )
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0
            assert all(alias.asname is None for alias in node.names)
            assert node.module not in imports
            imports[node.module] = {alias.name for alias in node.names}
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                assert node.func.id in {
                    "ZoneInfo",
                    "frozenset",
                    "date",
                    "time",
                    "dataclass",
                    "field",
                    "type",
                    "TypeError",
                    "UnsupportedNYSEPublishedSessionYearError",
                    "ReviewPaperSessionSchedule",
                }
            else:
                assert isinstance(node.func, ast.Attribute)
                assert isinstance(node.func.value, ast.Name)
                assert (node.func.value.id, node.func.attr) in {
                    ("session_date", "weekday"),
                    ("datetime", "combine"),
                }
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            assert all(isinstance(target, ast.Name) for target in targets)
    assert imports == {
        "__future__": {"annotations"},
        "dataclasses": {"dataclass", "field"},
        "datetime": {"date", "datetime", "time"},
        "zoneinfo": {"ZoneInfo"},
        "trading_bot.review_paper.session_admission": {"ReviewPaperSessionSchedule"},
    }


def test_source_has_only_published_session_lookup_capabilities():
    _assert_closed_published_session_surface(
        Path(module.__file__).read_text(encoding="utf-8")
    )


@pytest.mark.parametrize(
    "addition",
    [
        "import os",
        "import socket",
        "import httpx",
        "import subprocess",
        "from pathlib import Path",
        "from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter",
        "from trading_bot.robinhood_oauth import RobinhoodOAuth",
        "from trading_bot.review_paper.store import ReviewPaperStore",
        "from trading_bot.review_paper.risk_price_acquisition import "
        "acquire_robinhood_risk_prices",
        "from trading_bot.risk.manager import RiskManager",
        "from trading_bot.execution.models import ExecutionInstruction",
        "datetime.now()",
        "date.today()",
        "open('state', 'w')",
        "get_equity_quotes()",
        "place_order()",
        "sleep(1)",
        "retry()",
        "poll()",
        "schedule_work()",
        "while True: pass",
        "for item in (): pass",
        "self.source_name = 'other'",
    ],
)
def test_structural_guard_rejects_prohibited_authority(addition):
    source = Path(module.__file__).read_text(encoding="utf-8")
    with pytest.raises(AssertionError):
        _assert_closed_published_session_surface(source + "\n" + addition + "\n")
