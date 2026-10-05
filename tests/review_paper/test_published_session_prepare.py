"""Published schedule composition uses only fake PREPARE boundaries."""

import ast
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest

from trading_bot.review_paper import published_session_prepare as module
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
    UnsupportedNYSEPublishedSessionYearError,
)


class DateSubclass(date):
    pass


class Untouchable:
    def __getattr__(self, name):
        pytest.fail(f"unexpected provider/store boundary: {name}")


@pytest.mark.parametrize(
    "session_date,open_hour,close_hour",
    [
        (date(2026, 1, 5), 14, 21),
        (date(2026, 7, 6), 13, 20),
        (date(2026, 11, 27), 14, 18),
    ],
)
def test_resolver_preserves_exact_published_schedule(
    monkeypatch, session_date, open_hour, close_hour
):
    schedule = NYSEPublishedRegularSessionAuthority().schedule_for(session_date)
    lookup = Mock(return_value=schedule)
    monkeypatch.setattr(NYSEPublishedRegularSessionAuthority, "schedule_for", lookup)
    assert (
        module.resolve_review_paper_published_session_schedule(session_date) is schedule
    )
    lookup.assert_called_once_with(session_date)
    assert schedule.opens_at == datetime.combine(
        session_date, datetime.min.time(), UTC
    ).replace(hour=open_hour, minute=30)
    assert schedule.closes_at == datetime.combine(
        session_date, datetime.min.time(), UTC
    ).replace(hour=close_hour)


_WRAPPERS = (
    (
        module.prepare_review_paper_supervised_published_session,
        "prepare_review_paper_supervised_cycle",
        False,
    ),
    (
        module.run_review_paper_published_session_prepare_qualification,
        "run_review_paper_prepare_qualification",
        True,
    ),
)


def _inputs(tmp_path, qualification):
    values = dict(
        store=Untouchable(),
        proposal=object(),
        opening_buffer=timedelta(minutes=5),
        closing_buffer=timedelta(minutes=7),
        adapter=Untouchable(),
        max_quote_age=timedelta(seconds=60),
        risk_limits=object(),
        new_trading_enabled=False,
    )
    if qualification:
        values.update(
            expected_source_head="a" * 40,
            expected_source_tree="b" * 40,
            evidence_path=tmp_path / "evidence.json",
        )
    return values


@pytest.mark.parametrize("wrapper,delegate,qualification", _WRAPPERS)
@pytest.mark.parametrize(
    "session_date", [date(2026, 1, 5), date(2026, 7, 6), date(2026, 11, 27)]
)
def test_wrappers_resolve_and_delegate_once_preserving_every_identity(
    tmp_path, monkeypatch, wrapper, delegate, qualification, session_date
):
    values = _inputs(tmp_path, qualification)
    schedule = NYSEPublishedRegularSessionAuthority().schedule_for(session_date)
    lookup = Mock(return_value=schedule)
    resolver = Mock(wraps=module.resolve_review_paper_published_session_schedule)
    result = object()
    prepare = Mock(return_value=result)
    qualify = Mock(return_value=result)
    monkeypatch.setattr(NYSEPublishedRegularSessionAuthority, "schedule_for", lookup)
    monkeypatch.setattr(
        module, "resolve_review_paper_published_session_schedule", resolver
    )
    monkeypatch.setattr(module, "prepare_review_paper_supervised_cycle", prepare)
    monkeypatch.setattr(module, "run_review_paper_prepare_qualification", qualify)
    assert wrapper(session_date=session_date, **values) is result
    resolver.assert_called_once_with(session_date)
    lookup.assert_called_once_with(session_date)
    called = qualify if qualification else prepare
    other = prepare if qualification else qualify
    other.assert_not_called()
    called.assert_called_once_with(schedule=schedule, **values)
    assert called.call_args.args == ()
    assert called.call_args.kwargs["schedule"] is schedule
    for key, value in values.items():
        assert called.call_args.kwargs[key] is value
    assert not (tmp_path / "evidence.json").exists()


_INVALID_DATES = (
    (date(2026, 10, 3), module.ReviewPaperPublishedNonSessionDateError),
    (date(2026, 12, 25), module.ReviewPaperPublishedNonSessionDateError),
    (date(2029, 1, 2), UnsupportedNYSEPublishedSessionYearError),
    (datetime(2026, 10, 2, tzinfo=UTC), TypeError),
    (DateSubclass(2026, 10, 2), TypeError),
    *(
        (value, TypeError)
        for value in ("2026-10-02", 20261002, True, False, None, 1.0, object())
    ),
)


@pytest.mark.parametrize("session_date,error", _INVALID_DATES)
def test_resolver_fails_closed(session_date, error):
    with pytest.raises(error) as caught:
        module.resolve_review_paper_published_session_schedule(session_date)
    assert type(caught.value) is error


@pytest.mark.parametrize("wrapper,delegate,qualification", _WRAPPERS)
@pytest.mark.parametrize("session_date,error", _INVALID_DATES)
@pytest.mark.parametrize("existing_evidence", [False, True])
def test_invalid_resolution_precedes_all_delegates_and_effects(
    tmp_path,
    monkeypatch,
    wrapper,
    delegate,
    qualification,
    session_date,
    error,
    existing_evidence,
):
    values = _inputs(tmp_path, qualification)
    evidence = tmp_path / "evidence.json"
    if existing_evidence:
        evidence.write_bytes(b"preserve existing evidence")
    prepare = Mock(side_effect=AssertionError("PREPARE must not run"))
    qualify = Mock(side_effect=AssertionError("qualification must not run"))
    lookup = Mock(wraps=NYSEPublishedRegularSessionAuthority().schedule_for)
    monkeypatch.setattr(NYSEPublishedRegularSessionAuthority, "schedule_for", lookup)
    monkeypatch.setattr(module, "prepare_review_paper_supervised_cycle", prepare)
    monkeypatch.setattr(module, "run_review_paper_prepare_qualification", qualify)
    with pytest.raises(error) as caught:
        wrapper(session_date=session_date, **values)
    assert type(caught.value) is error
    lookup.assert_called_once_with(session_date)
    prepare.assert_not_called()
    qualify.assert_not_called()
    if existing_evidence:
        assert evidence.read_bytes() == b"preserve existing evidence"
    else:
        assert not evidence.exists()


def test_unsupported_year_error_propagates_by_identity(monkeypatch):
    error = UnsupportedNYSEPublishedSessionYearError("outside manifest")
    monkeypatch.setattr(
        NYSEPublishedRegularSessionAuthority, "schedule_for", Mock(side_effect=error)
    )
    with pytest.raises(UnsupportedNYSEPublishedSessionYearError) as caught:
        module.resolve_review_paper_published_session_schedule(date(2029, 1, 2))
    assert caught.value is error


@pytest.mark.parametrize("wrapper,delegate,qualification", _WRAPPERS)
def test_delegate_failure_propagates_without_retry_or_evidence_creation(
    tmp_path, monkeypatch, wrapper, delegate, qualification
):
    session_date = date(2026, 10, 2)
    values = _inputs(tmp_path, qualification)
    error = RuntimeError("delegate failed")
    called = Mock(side_effect=error)
    lookup = Mock(wraps=NYSEPublishedRegularSessionAuthority().schedule_for)
    monkeypatch.setattr(NYSEPublishedRegularSessionAuthority, "schedule_for", lookup)
    monkeypatch.setattr(module, delegate, called)
    with pytest.raises(RuntimeError) as caught:
        wrapper(session_date=session_date, **values)
    assert caught.value is error
    lookup.assert_called_once_with(session_date)
    called.assert_called_once()
    assert not (tmp_path / "evidence.json").exists()


def _assert_prepare_only_source(source):
    tree = ast.parse(source)
    imports = {
        "__future__": {"annotations"},
        "datetime": {"date", "timedelta"},
        "pathlib": {"Path"},
        "trading_bot.domain": {"TradeProposal"},
        "trading_bot.review_paper.nyse_published_regular_sessions": {
            "NYSEPublishedRegularSessionAuthority"
        },
        "trading_bot.review_paper.prepare_qualification": {
            "run_review_paper_prepare_qualification"
        },
        "trading_bot.review_paper.session_admission": {"ReviewPaperSessionSchedule"},
        "trading_bot.review_paper.store": {"ReviewPaperStore"},
        "trading_bot.review_paper.supervised_forward_paper": {
            "ReviewPaperSupervisedPreparation",
            "prepare_review_paper_supervised_cycle",
        },
        "trading_bot.risk.models": {"RiskLimits"},
        "trading_bot.robinhood_mcp.adapter": {"RobinhoodReviewReadAdapter"},
    }
    for node in ast.walk(tree):
        assert not isinstance(
            node, (ast.Import, ast.For, ast.While, ast.AsyncFunctionDef, ast.With)
        )
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0 and node.module in imports
            assert {alias.name for alias in node.names} <= imports[node.module]
            assert all(alias.asname is None for alias in node.names)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                assert node.func.id in {
                    "NYSEPublishedRegularSessionAuthority",
                    "ReviewPaperPublishedNonSessionDateError",
                    "resolve_review_paper_published_session_schedule",
                    "prepare_review_paper_supervised_cycle",
                    "run_review_paper_prepare_qualification",
                }
            else:
                assert isinstance(node.func, ast.Attribute)
                assert node.func.attr == "schedule_for"
                assert isinstance(node.func.value, ast.Call)
                assert node.func.value.func.id == "NYSEPublishedRegularSessionAuthority"
    assert {node.name for node in tree.body if isinstance(node, ast.FunctionDef)} == {
        "resolve_review_paper_published_session_schedule",
        "prepare_review_paper_supervised_published_session",
        "run_review_paper_published_session_prepare_qualification",
    }


def test_source_has_only_published_resolution_and_prepare_delegation():
    _assert_prepare_only_source(Path(module.__file__).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "addition",
    [
        "from datetime import datetime",
        "date.today()",
        "datetime.now()",
        "import os",
        "import socket",
        "import httpx",
        "import subprocess",
        "import time",
        "from pathlib import PurePath",
        "open('schedule.json')",
        "adapter.acquire_quotes()",
        "store.read_records()",
        "risk_limits.evaluate()",
        "execute_review_paper_supervised_cycle()",
        "run_robinhood_paper_pipeline()",
        "sleep(1)",
        "while True:\n    pass",
        "retry()",
        "poll()",
        "scheduler.run()",
        "config.read()",
        "environ.get('SESSION_DATE')",
    ],
)
def test_source_guard_rejects_added_clock_discovery_or_effect(addition):
    source = Path(module.__file__).read_text(encoding="utf-8")
    with pytest.raises(AssertionError):
        _assert_prepare_only_source(source + "\n" + addition + "\n")
