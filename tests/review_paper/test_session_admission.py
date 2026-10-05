"""Architecture 131-M deterministic explicit-session admission contract."""

import ast
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta, timezone, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import trading_bot.review_paper.session_admission as module
from trading_bot.review_paper.session_admission import (
    ReviewPaperSessionAdmission,
    ReviewPaperSessionSchedule,
    ReviewPaperSessionStatus,
    admit_review_paper_session,
)

DAY = date(2026, 1, 5)
OPEN = datetime(2026, 1, 5, 14, 30, tzinfo=UTC)
CLOSE = datetime(2026, 1, 5, 21, tzinfo=UTC)
BUFFER = timedelta(minutes=15)
SCHEDULE = ReviewPaperSessionSchedule(DAY, OPEN, CLOSE)


def _admit(as_of=OPEN + BUFFER, **kwargs):
    return admit_review_paper_session(
        **{
            "schedule": SCHEDULE,
            "as_of": as_of,
            "opening_buffer": BUFFER,
            "closing_buffer": BUFFER,
            **kwargs,
        }
    )


def test_status_enum_is_exact():
    assert [(status.name, status.value) for status in ReviewPaperSessionStatus] == [
        ("ADMITTED", "ADMITTED"),
        ("NON_SESSION_DATE", "NON_SESSION_DATE"),
        ("BEFORE_REGULAR_WINDOW", "BEFORE_REGULAR_WINDOW"),
        ("OPENING_BUFFER", "OPENING_BUFFER"),
        ("CLOSING_BUFFER", "CLOSING_BUFFER"),
        ("AFTER_REGULAR_WINDOW", "AFTER_REGULAR_WINDOW"),
    ]


@pytest.mark.parametrize("day,hour", [(DAY, 14), (date(2026, 7, 6), 13)])
def test_winter_and_daylight_saving_schedule_normalization(day, hour):
    ny = ZoneInfo("America/New_York")
    opens_at = datetime.combine(day, datetime.min.time()).replace(
        hour=9, minute=30, tzinfo=ny
    )
    closes_at = opens_at.replace(hour=16, minute=0)
    schedule = ReviewPaperSessionSchedule(day, opens_at, closes_at)
    assert schedule.session_date == day
    assert schedule.opens_at == opens_at.astimezone(UTC)
    assert schedule.opens_at.hour == hour
    assert schedule.closes_at == closes_at.astimezone(UTC)
    assert schedule.opens_at.tzinfo is UTC and schedule.closes_at.tzinfo is UTC
    result = _admit(opens_at + BUFFER, schedule=schedule)
    assert result.status is ReviewPaperSessionStatus.ADMITTED
    assert result.as_of.tzinfo is UTC
    # The UTC date is the next day; exchange-local date is still the session date.
    late = closes_at.replace(hour=23, minute=30)
    assert late.astimezone(UTC).date() != day
    assert _admit(late, schedule=schedule).status is (
        ReviewPaperSessionStatus.AFTER_REGULAR_WINDOW
    )
    assert _admit(opens_at - timedelta(days=1), schedule=schedule).status is (
        ReviewPaperSessionStatus.NON_SESSION_DATE
    )


@pytest.mark.parametrize("field", ["opens_at", "closes_at"])
@pytest.mark.parametrize(
    "value,error", [(OPEN.replace(tzinfo=None), ValueError), ("bad", TypeError)]
)
def test_invalid_schedule_datetimes(field, value, error):
    with pytest.raises(error, match=field):
        replace(SCHEDULE, **{field: value})


@pytest.mark.parametrize("value", [OPEN, "2026-01-05", None])
def test_session_date_requires_date_not_datetime(value):
    with pytest.raises(TypeError, match="session_date"):
        replace(SCHEDULE, session_date=value)


@pytest.mark.parametrize("close", [OPEN, OPEN - timedelta(seconds=1)])
def test_open_must_precede_close(close):
    with pytest.raises(ValueError, match="precede"):
        replace(SCHEDULE, closes_at=close)


@pytest.mark.parametrize(
    "changes,field",
    [
        ({"opens_at": OPEN - timedelta(days=1)}, "opens_at"),
        ({"closes_at": CLOSE + timedelta(days=1)}, "closes_at"),
    ],
)
def test_schedule_exchange_local_date_mismatch(changes, field):
    with pytest.raises(ValueError, match=field):
        replace(SCHEDULE, **changes)


class _NoOffset(tzinfo):
    def utcoffset(self, dt):
        return None


@pytest.mark.parametrize(
    "value,error",
    [
        (OPEN.replace(tzinfo=None), ValueError),
        (OPEN.replace(tzinfo=_NoOffset()), ValueError),
        (None, TypeError),
        (DAY, TypeError),
    ],
)
def test_invalid_as_of(value, error):
    with pytest.raises(error, match="as_of"):
        _admit(value)


class _ScheduleSubclass(ReviewPaperSessionSchedule):
    pass


@pytest.mark.parametrize(
    "schedule",
    [
        None,
        {"session_date": DAY, "opens_at": OPEN, "closes_at": CLOSE},
        _ScheduleSubclass(DAY, OPEN, CLOSE),
    ],
)
def test_schedule_requires_exact_type(schedule):
    with pytest.raises(TypeError, match="exactly ReviewPaperSessionSchedule"):
        _admit(schedule=schedule)


class _BufferSubclass(timedelta):
    pass


@pytest.mark.parametrize("field", ["opening_buffer", "closing_buffer"])
@pytest.mark.parametrize("value", [None, 0, False, "15", _BufferSubclass(minutes=15)])
def test_buffers_require_exact_timedelta(field, value):
    with pytest.raises(TypeError, match=field):
        _admit(**{field: value})


@pytest.mark.parametrize("field", ["opening_buffer", "closing_buffer"])
def test_negative_buffer_rejected(field):
    with pytest.raises(ValueError, match=field):
        _admit(**{field: -timedelta(microseconds=1)})


@pytest.mark.parametrize(
    "opening,closing",
    [
        (CLOSE - OPEN, timedelta(0)),
        (timedelta(0), CLOSE - OPEN),
        (timedelta(hours=3), timedelta(hours=3, minutes=30)),
        (timedelta(hours=4), timedelta(hours=3)),
        (timedelta.max, BUFFER),
        (BUFFER, timedelta.max),
    ],
)
def test_buffers_must_leave_nonempty_interval(opening, closing):
    with pytest.raises(ValueError, match="nonempty"):
        _admit(opening_buffer=opening, closing_buffer=closing)


@pytest.mark.parametrize(
    "as_of,status",
    [
        (OPEN - timedelta(days=1), "NON_SESSION_DATE"),
        (CLOSE + timedelta(days=1), "NON_SESSION_DATE"),
        (OPEN - timedelta(microseconds=1), "BEFORE_REGULAR_WINDOW"),
        (OPEN, "OPENING_BUFFER"),
        (OPEN + BUFFER / 2, "OPENING_BUFFER"),
        (OPEN + BUFFER - timedelta(microseconds=1), "OPENING_BUFFER"),
        (OPEN + BUFFER, "ADMITTED"),
        (OPEN + timedelta(hours=2), "ADMITTED"),
        (CLOSE - BUFFER - timedelta(microseconds=1), "ADMITTED"),
        (CLOSE - BUFFER, "CLOSING_BUFFER"),
        (CLOSE - BUFFER / 2, "CLOSING_BUFFER"),
        (CLOSE - timedelta(microseconds=1), "CLOSING_BUFFER"),
        (CLOSE, "AFTER_REGULAR_WINDOW"),
        (CLOSE + timedelta(microseconds=1), "AFTER_REGULAR_WINDOW"),
    ],
)
def test_exact_status_boundaries(as_of, status):
    assert _admit(as_of).status is ReviewPaperSessionStatus[status]


@pytest.mark.parametrize(
    "as_of,status",
    [
        (OPEN - timedelta(microseconds=1), "BEFORE_REGULAR_WINDOW"),
        (OPEN, "ADMITTED"),
        (CLOSE - timedelta(microseconds=1), "ADMITTED"),
        (CLOSE, "AFTER_REGULAR_WINDOW"),
    ],
)
def test_zero_buffers(as_of, status):
    result = _admit(as_of, opening_buffer=timedelta(0), closing_buffer=timedelta(0))
    assert result.status is ReviewPaperSessionStatus[status]
    assert result.admission_opens_at == OPEN
    assert result.admission_closes_at == CLOSE


@pytest.mark.parametrize("field", ["opening_buffer", "closing_buffer"])
def test_one_zero_buffer_accepted(field):
    assert _admit(**{field: timedelta(0)}).status is ReviewPaperSessionStatus.ADMITTED


def test_exact_result_windows_and_determinism():
    instant = (OPEN + BUFFER).astimezone(timezone(timedelta(hours=9)))
    result = _admit(instant)
    assert type(result) is ReviewPaperSessionAdmission
    assert result == ReviewPaperSessionAdmission(
        ReviewPaperSessionStatus.ADMITTED,
        OPEN + BUFFER,
        DAY,
        OPEN,
        CLOSE,
        OPEN + BUFFER,
        CLOSE - BUFFER,
    )
    assert _admit(instant) == result
    assert SCHEDULE == ReviewPaperSessionSchedule(DAY, OPEN, CLOSE)
    assert all(
        getattr(result, field).tzinfo is UTC
        for field in (
            "as_of",
            "opens_at",
            "closes_at",
            "admission_opens_at",
            "admission_closes_at",
        )
    )


def test_direct_result_normalizes_all_datetimes():
    result = _admit()
    offset = timezone(timedelta(hours=-5))
    changed = replace(
        result,
        **{
            field: getattr(result, field).astimezone(offset)
            for field in (
                "as_of",
                "opens_at",
                "closes_at",
                "admission_opens_at",
                "admission_closes_at",
            )
        },
    )
    assert changed == result
    assert all(
        getattr(changed, field).tzinfo is UTC
        for field in (
            "as_of",
            "opens_at",
            "closes_at",
            "admission_opens_at",
            "admission_closes_at",
        )
    )


@pytest.mark.parametrize(
    "field",
    ["as_of", "opens_at", "closes_at", "admission_opens_at", "admission_closes_at"],
)
@pytest.mark.parametrize(
    "value,error", [(OPEN.replace(tzinfo=None), ValueError), (None, TypeError)]
)
def test_direct_result_rejects_invalid_datetimes(field, value, error):
    with pytest.raises(error, match=field):
        replace(_admit(), **{field: value})


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "ADMITTED"},
        {"status": ReviewPaperSessionStatus.NON_SESSION_DATE},
        {"status": ReviewPaperSessionStatus.OPENING_BUFFER},
        {"as_of": CLOSE},
        {"session_date": DAY + timedelta(days=1)},
        {"session_date": OPEN},
        {"opens_at": CLOSE},
        {"closes_at": CLOSE + timedelta(days=1)},
        {"admission_opens_at": OPEN - timedelta(microseconds=1)},
        {"admission_closes_at": CLOSE + timedelta(microseconds=1)},
        {"admission_opens_at": CLOSE - BUFFER},
        {"admission_opens_at": CLOSE},
        {"admission_closes_at": OPEN},
    ],
)
def test_direct_result_rejects_contradictions(changes):
    with pytest.raises((ValueError, TypeError)):
        replace(_admit(), **changes)


@pytest.mark.parametrize("value", [SCHEDULE, _admit()])
def test_objects_are_frozen_and_slotted(value):
    assert not hasattr(value, "__dict__")
    with pytest.raises(FrozenInstanceError):
        value.session_date = DAY + timedelta(days=1)


def _assert_closed_temporal_surface(source):
    tree = ast.parse(source)
    imports = {}
    for node in ast.walk(tree):
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
            imports[node.module] = {alias.name for alias in node.names}
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                assert node.func.id in {
                    "ZoneInfo",
                    "dataclass",
                    "isinstance",
                    "type",
                    "TypeError",
                    "ValueError",
                    "_normalize_utc",
                    "_session_status",
                    "timedelta",
                    "ReviewPaperSessionSchedule",
                    "ReviewPaperSessionAdmission",
                }
            else:
                assert isinstance(node.func, ast.Attribute)
                assert node.func.attr in {
                    "utcoffset",
                    "astimezone",
                    "date",
                    "__setattr__",
                }
                if node.func.attr == "__setattr__":
                    assert ast.unparse(node.func) == "object.__setattr__"
                    assert ast.unparse(node.args[0]) == "self"
                    assert isinstance(node.args[1], ast.Constant)
                    assert node.args[1].value in {
                        "as_of",
                        "opens_at",
                        "closes_at",
                        "admission_opens_at",
                        "admission_closes_at",
                    }
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            assert all(isinstance(target, ast.Name) for target in targets)
    assert imports == {
        "__future__": {"annotations"},
        "dataclasses": {"dataclass"},
        "datetime": {"UTC", "date", "datetime", "timedelta"},
        "enum": {"StrEnum"},
        "zoneinfo": {"ZoneInfo"},
    }


def test_source_has_only_deterministic_temporal_capabilities():
    _assert_closed_temporal_surface(Path(module.__file__).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "addition",
    [
        "from trading_bot.robinhood_mcp import RobinhoodMcpStreamableHttpTransport",
        "from trading_bot.robinhood_oauth import RobinhoodOAuth",
        "from trading_bot.review_paper.store import ReviewPaperStore",
        "from trading_bot.risk.models import RiskContext",
        "from trading_bot.domain import TradeProposal",
        "from trading_bot.review_paper.models import ReviewPaperIntent",
        "run_robinhood_paper_pipeline()",
        "run_robinhood_forward_paper_cycle()",
        "get_equity_quotes()",
        "review_equity_order()",
        "place_order()",
        "cancel_order()",
        "open('state', 'w')",
        "from pathlib import Path",
        "import os",
        "import socket",
        "import httpx",
        "import subprocess",
        "import uuid",
        "datetime.now()",
        "datetime.today()",
        "datetime.utcnow()",
        "time.time()",
        "sleep(1)",
        "retry()",
        "poll()",
        "schedule_work()",
        "while True: pass",
        "for item in (): pass",
        "store.record_market_review()",
        "self.status = 'ADMITTED'",
    ],
)
def test_structural_guard_rejects_forbidden_capability(addition):
    source = Path(module.__file__).read_text(encoding="utf-8")
    with pytest.raises(AssertionError):
        _assert_closed_temporal_surface(source + "\n" + addition + "\n")
