import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

import trading_bot.desktop_live.preflight as preflight
from trading_bot.desktop_live.models import LivePlanState
from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import XNYS_CALENDAR_DESCRIPTOR, BoundMarketCalendar
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.robinhood_mcp.current_live_transport import (
    LIVE_TOOL_SURFACE,
    CurrentLiveTransportError,
    RobinhoodCurrentLiveTransport,
)
from trading_bot.robinhood_mcp.historical import RobinhoodDailyHistoryRequest

HEAD = "7ff86d06a99bcdf349d5e20846d139a554d8be46"
TREE = "095c51cedc1c656616123c3acf88148b16b71aa2"


def _write_report(
    root: Path,
    name: str,
    *,
    status: str = "PASS",
    source_head: str = HEAD,
    source_tree: str = TREE,
    mutation_call_count: int = 0,
    order_review_count: int = 0,
    order_preview_count: int = 0,
    order_placement_count: int = 0,
    order_cancel_count: int = 0,
    p5_financial_state_mutation_count: int = 0,
    production_state_unchanged: bool = True,
) -> Path:
    report = root / name / "report.json"
    report.parent.mkdir(parents=True)
    report.write_text(
        json.dumps(
            {
                "status": status,
                "source_head": source_head,
                "source_tree": source_tree,
                "result": {
                    "mutation_call_count": mutation_call_count,
                    "order_review_count": order_review_count,
                    "order_preview_count": order_preview_count,
                    "order_placement_count": order_placement_count,
                    "order_cancel_count": order_cancel_count,
                    "p5_financial_state_mutation_count": (
                        p5_financial_state_mutation_count
                    ),
                    "production_state_unchanged": production_state_unchanged,
                    "observation": {
                        "account_fingerprint": "a" * 64,
                        "position_count": 0,
                        "order_count": 0,
                        "local_expected_broker_effect_count": 0,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return report


def test_p5b_evidence_discovery_blocks_zero_matches(tmp_path):
    with pytest.raises(preflight.LivePreflightError, match="MATCH_COUNT"):
        preflight.load_p5b_baseline_evidence(
            tmp_path, expected_source_head=HEAD, expected_source_tree=TREE
        )


def test_p5b_evidence_discovery_accepts_one_exact_match(tmp_path):
    report = _write_report(tmp_path, "preflight-one")

    evidence = preflight.load_p5b_baseline_evidence(
        tmp_path, expected_source_head=HEAD, expected_source_tree=TREE
    )

    assert evidence.source_head == HEAD
    assert evidence.source_tree == TREE
    assert evidence.account_fingerprint == "a" * 64
    assert report.is_file()


def test_p5b_evidence_discovery_blocks_multiple_exact_matches(tmp_path):
    _write_report(tmp_path, "preflight-one")
    _write_report(tmp_path, "preflight-two")

    with pytest.raises(preflight.LivePreflightError, match="MATCH_COUNT"):
        preflight.load_p5b_baseline_evidence(
            tmp_path, expected_source_head=HEAD, expected_source_tree=TREE
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "BLOCKED"},
        {"source_head": "b" * 40},
        {"source_tree": "c" * 40},
        {"mutation_call_count": 1},
        {"order_review_count": 1},
        {"order_preview_count": 1},
        {"order_placement_count": 1},
        {"order_cancel_count": 1},
        {"p5_financial_state_mutation_count": 1},
        {"production_state_unchanged": False},
    ],
)
def test_p5b_evidence_discovery_filters_nonmatching_reports(tmp_path, changes):
    _write_report(tmp_path, "preflight-rejected", **changes)
    _write_report(tmp_path, "preflight-accepted")

    evidence = preflight.load_p5b_baseline_evidence(
        tmp_path, expected_source_head=HEAD, expected_source_tree=TREE
    )

    assert evidence.account_fingerprint == "a" * 64


# Fixed UTC instants exercise New York dates, DST and published early closes.
SESSION_CASES = (
    ("premarket", "2026-11-02T12:00:00+00:00", "2026-11-02", False),
    ("open", "2026-11-02T14:30:00+00:00", "2026-11-02", True),
    ("former-cutoff", "2026-11-02T14:35:00+00:00", "2026-11-02", True),
    ("noon", "2026-11-02T17:00:00+00:00", "2026-11-02", True),
    ("late", "2026-11-02T20:59:59+00:00", "2026-11-02", True),
    ("close", "2026-11-02T21:00:00+00:00", "2026-11-03", False),
    ("after-close", "2026-11-02T23:00:00+00:00", "2026-11-03", False),
    ("utc-next-date", "2026-11-03T01:00:00+00:00", "2026-11-03", False),
    ("weekend", "2026-11-07T17:00:00+00:00", "2026-11-09", False),
    ("holiday", "2026-11-26T17:00:00+00:00", "2026-11-27", False),
    ("early-close-noon", "2026-11-27T17:00:00+00:00", "2026-11-27", True),
    ("early-close-end", "2026-11-27T18:00:00+00:00", "2026-11-30", False),
    ("dst-noon", "2026-10-30T16:00:00+00:00", "2026-10-30", True),
)


@pytest.mark.parametrize(
    "label,instant,target,is_open", SESSION_CASES, ids=[row[0] for row in SESSION_CASES]
)
def test_target_session_uses_published_regular_hours(label, instant, target, is_open):
    assert preflight.resolve_target_session(datetime.fromisoformat(instant)) == (
        target,
        is_open,
    )


class _PlanTransport:
    """Synthetic bounded reads/review only; any mutation fails the test."""

    def __init__(self, now, *, rising=True):
        self.now = now
        self.rising = rising
        self.reviews = 0
        self.placed = 0
        self.canceled = 0
        self._counts = dict.fromkeys(LIVE_TOOL_SURFACE, 0)
        self.review_changes = {}
        self.setting_approval = False
        self.review_arguments = []

    @property
    def call_counts(self):
        return tuple(self._counts.items())

    def discover_required_capabilities(self):
        pass

    def get_accounts(self):
        self._counts["get_accounts"] += 1
        return {
            "data": {
                "accounts": [{"account_number": "SYNTHETIC", "agentic_allowed": True}]
            }
        }

    def get_portfolio(self, arguments):
        raise AssertionError("use the synthetic baseline observation seam")

    get_equity_positions = get_portfolio
    get_equity_quotes = get_portfolio
    get_equity_orders = get_portfolio

    def get_equity_historicals(self, arguments):
        self._counts["get_equity_historicals"] += 1
        request = RobinhoodDailyHistoryRequest(
            preflight.LIVE_SYMBOL,
            self.now,
            60,
            BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar()),
        )
        assert arguments == request.arguments()
        authority = NYSEPublishedRegularSessionAuthority()
        bars = []
        for index, session in enumerate(request.sessions()):
            schedule = authority.schedule_for(session.session_date)
            price = str(100 + index if self.rising else 200 - index)
            bars.append(
                {
                    "begins_at": schedule.opens_at.astimezone(UTC).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    "open_price": price,
                    "high_price": price,
                    "low_price": price,
                    "close_price": price,
                    "volume": 100,
                    "session": "reg",
                    "interpolated": False,
                }
            )
        return {
            "data": {
                "results": [
                    {
                        "symbol": "SPY",
                        "interval": "day",
                        "bounds": "regular",
                        "adjustment_type": "none",
                        "bars": bars,
                    }
                ]
            },
            "guide": "synthetic",
        }

    def get_equity_tradability(self, arguments):
        self._counts["get_equity_tradability"] += 1
        return {
            "data": {
                "symbol": "SPY",
                "tradable": True,
                "fractional_trading": True,
                "dollar_orders": True,
            }
        }

    def get_trade_approval_setting(self, arguments):
        self._counts["get_trade_approval_setting"] += 1
        return {"data": {"enabled": self.setting_approval}}

    def review_equity_order(self, arguments):
        self.reviews += 1
        self._counts["review_equity_order"] += 1
        self.review_arguments.append(dict(arguments))
        return {
            "data": {
                **{
                    key: arguments[key]
                    for key in ("symbol", "side", "type", "dollar_amount")
                },
                "order_checks": {},
                **self.review_changes,
            }
        }

    def place_equity_order(self, arguments):
        self.placed += 1
        raise AssertionError("preflight cannot place")

    def cancel_equity_order(self, arguments):
        self.canceled += 1
        raise AssertionError("preflight cannot cancel")


@pytest.fixture
def plan_builder(monkeypatch):
    observation = SimpleNamespace(
        account_fingerprint="a" * 64,
        positions=(),
        orders=(),
        portfolio=SimpleNamespace(cash=Decimal("100"), equity_value=Decimal("100")),
        spy_quote=SimpleNamespace(
            symbol=preflight.LIVE_SYMBOL,
            current_trade_candidate=lambda: (Decimal("500"), None),
        ),
    )
    monkeypatch.setattr(
        preflight, "observe_robinhood_baseline", lambda *args, **kwargs: observation
    )

    def build(
        instant,
        *,
        rising=True,
        through_preflight=False,
        review_changes=None,
        setting_approval=False,
    ):
        now = datetime.fromisoformat(instant)
        transport = _PlanTransport(now, rising=rising)
        transport.review_changes = review_changes or {}
        transport.setting_approval = setting_approval
        if through_preflight:
            monkeypatch.setattr(preflight, "_transport", lambda: transport)
            monkeypatch.setattr(
                preflight, "datetime", SimpleNamespace(now=lambda _: now)
            )
            return preflight.preflight(), transport
        plan = preflight.build_live_plan(
            transport=transport,
            p5b=preflight.P5BBaselineEvidence(HEAD, TREE, "a" * 64, 0, 0),
            source_head="b" * 40,
            source_tree="c" * 40,
            now=now,
        )
        assert transport.placed == transport.canceled == 0
        return plan, transport

    return build


@pytest.mark.parametrize(
    "label,instant,target,is_open", SESSION_CASES, ids=[row[0] for row in SESSION_CASES]
)
def test_buy_preflight_can_prepare_anytime_for_next_executable_session(
    plan_builder, label, instant, target, is_open
):
    plan, transport = plan_builder(instant)
    assert plan.state is LivePlanState.READY
    assert plan.decision == "BUY"
    assert plan.target_session == target
    assert plan.provider_warning_summary == ()
    assert plan.review.clean
    assert Decimal("0") < plan.requested_dollars <= Decimal("10")
    assert transport.reviews == 1


@pytest.mark.parametrize(
    "label,instant,target,is_open", SESSION_CASES, ids=[row[0] for row in SESSION_CASES]
)
def test_no_action_preflight_has_no_market_time_gate(
    plan_builder, label, instant, target, is_open
):
    plan, transport = plan_builder(instant, rising=False)
    assert plan.state is LivePlanState.NO_ACTION
    assert plan.decision == "NO_ACTION"
    assert plan.target_session == target
    assert plan.requested_dollars == 0
    assert transport.reviews == 0


SECRET = "SECRET_OAUTH_ACCOUNT_PROVIDER_PAYLOAD"


@pytest.fixture
def preflight_environment(monkeypatch):
    before = {"live.sqlite": {"exists": False, "sha256": None}}
    monkeypatch.setattr(preflight, "_production_identities", lambda: before)
    monkeypatch.setattr(preflight, "_source_identity", lambda: (HEAD, TREE))
    monkeypatch.setattr(
        preflight,
        "load_p5b_baseline_evidence",
        lambda **_: preflight.P5BBaselineEvidence(HEAD, TREE, "a" * 64, 0, 0),
    )

    def forbidden():
        raise AssertionError("real transport construction is forbidden")

    monkeypatch.setattr(preflight, "_transport", forbidden)
    return before


def _assert_blocked(result, diagnostic, counts, before, *, code="NONE"):
    assert result["status"] == "BLOCKED"
    assert result["diagnostic"] == diagnostic
    assert result["failure_code"] == code
    assert result["plan"] is None
    assert result["provider_call_counts"] == counts
    assert result["order_review_count"] == counts.get("review_equity_order", 0)
    assert result["order_placement_count"] == result["order_cancel_count"] == 0
    assert (
        result["production_state_before"] == result["production_state_after"] == before
    )
    assert result["production_state_unchanged"] is True
    assert SECRET not in json.dumps(result)


@pytest.mark.parametrize(
    "seam,diagnostic,code",
    (
        ("_source_identity", "P6_SOURCE_IDENTITY_BLOCKED", "NONE"),
        (
            "load_p5b_baseline_evidence",
            "P5B_EVIDENCE_BLOCKED",
            "P5B_EVIDENCE_MATCH_COUNT",
        ),
        ("_transport", "P6_TRANSPORT_CONSTRUCTION_BLOCKED", "NONE"),
    ),
)
def test_failure_before_transport_is_sanitized(
    monkeypatch, preflight_environment, seam, diagnostic, code
):
    def fail(*args, **kwargs):
        if code != "NONE":
            raise preflight.LivePreflightError(code)
        raise RuntimeError(SECRET)

    monkeypatch.setattr(preflight, seam, fail)
    result = preflight.preflight()
    _assert_blocked(result, diagnostic, {}, preflight_environment, code=code)
    expected = (None, None) if seam == "_source_identity" else (HEAD, TREE)
    assert (result["source_head"], result["source_tree"]) == expected


class _PreflightSession:
    """Fake SDK boundary for blocked preflight invocation accounting."""

    def __init__(self, *, fail_review=False):
        self.fail_review = fail_review
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def list_tools(self, cursor=None):
        fields = (
            "account_number",
            "symbol",
            "side",
            "type",
            "market_hours",
            "time_in_force",
            "dollar_amount",
            "order_id",
            "ref_id",
            "quantity",
        )
        return SimpleNamespace(
            next_cursor=None,
            tools=[
                SimpleNamespace(
                    name=name,
                    inputSchema={
                        "properties": dict.fromkeys(fields, {}),
                        "required": (
                            ["account_number", "order_id"]
                            if name == "cancel_equity_order"
                            else ["account_number", "symbol", "side", "type"]
                        ),
                    },
                )
                for name in LIVE_TOOL_SURFACE
            ],
        )

    async def call_tool(self, name, arguments):
        assert name not in {"place_equity_order", "cancel_equity_order"}
        self.calls.append(name)
        if name == "review_equity_order" and self.fail_review:
            raise RuntimeError(SECRET)
        return SimpleNamespace(is_error=False, structured_content={"data": {}})


@pytest.mark.parametrize("progress", ("constructed", "read", "review"))
def test_downstream_failure_retains_transport_and_invocations(
    monkeypatch, preflight_environment, progress
):
    session = _PreflightSession(fail_review=True)
    transport = RobinhoodCurrentLiveTransport.for_test(lambda: session)
    monkeypatch.setattr(preflight, "_transport", lambda: transport)

    def fail_plan(**kwargs):
        assert kwargs["transport"] is transport
        if progress in {"read", "review"}:
            transport.get_accounts()
        if progress == "review":
            transport.review_equity_order({})
        raise RuntimeError(SECRET)

    monkeypatch.setattr(preflight, "build_live_plan", fail_plan)
    result = preflight.preflight()
    expected = dict.fromkeys(LIVE_TOOL_SURFACE, 0)
    expected["get_accounts"] = int(progress in {"read", "review"})
    expected["review_equity_order"] = int(progress == "review")
    _assert_blocked(
        result,
        "P6_PLAN_BUILD_BLOCKED",
        expected,
        preflight_environment,
        code="LIVE_REQUEST_FAILED" if progress == "review" else "NONE",
    )
    assert result["source_head"] == HEAD
    assert result["source_tree"] == TREE
    assert result["provider_call_counts"] == dict(transport.call_counts)
    assert session.calls == [name for name, count in expected.items() if count]


@pytest.mark.parametrize(
    "error,code",
    (
        (RuntimeError("LIVE_REQUEST_FAILED"), "NONE"),
        (CurrentLiveTransportError(SECRET), "NONE"),
        (preflight.LivePreflightError(SECRET), "NONE"),
        (CurrentLiveTransportError("LIVE_DISCOVERY_FAILED"), "LIVE_DISCOVERY_FAILED"),
        (
            preflight.LivePreflightError("P5B_EVIDENCE_UNAVAILABLE"),
            "P5B_EVIDENCE_UNAVAILABLE",
        ),
    ),
)
def test_failure_detail_requires_allowlisted_type_and_exact_code(
    monkeypatch, preflight_environment, error, code
):
    def fail(**kwargs):
        raise error

    monkeypatch.setattr(preflight, "load_p5b_baseline_evidence", fail)
    _assert_blocked(
        preflight.preflight(),
        "P5B_EVIDENCE_BLOCKED",
        {},
        preflight_environment,
        code=code,
    )


@pytest.mark.parametrize("rising", (True, False), ids=("READY", "NO_ACTION"))
def test_successful_preflight_retains_complete_counts(
    preflight_environment, plan_builder, rising
):
    result, transport = plan_builder(
        "2026-11-02T17:00:00+00:00", rising=rising, through_preflight=True
    )
    assert result["status"] == "PASS"
    assert result["diagnostic"] == result["failure_code"] == "NONE"
    assert result["plan"]["plan_state"] == ("READY" if rising else "NO_ACTION")
    expected = dict.fromkeys(LIVE_TOOL_SURFACE, 0)
    expected["get_accounts"] = expected["get_equity_historicals"] = 1
    for name in (
        "get_equity_tradability",
        "get_trade_approval_setting",
        "review_equity_order",
    ):
        expected[name] = int(rising)
    assert result["provider_call_counts"] == expected == dict(transport.call_counts)
    assert result["order_review_count"] == int(rising)
    assert result["order_placement_count"] == result["order_cancel_count"] == 0
    assert transport.placed == transport.canceled == 0
    assert result["production_state_unchanged"] is True


@pytest.mark.parametrize("unavailable", (False, True))
def test_changed_or_unavailable_state_blocks_without_erasing_completed_plan(
    monkeypatch, preflight_environment, plan_builder, unavailable
):
    before = preflight_environment
    after = {"live.sqlite": {"exists": None if unavailable else True, "sha256": None}}
    snapshots = iter((after, after) if unavailable else (before, after))
    monkeypatch.setattr(preflight, "_production_identities", lambda: next(snapshots))
    result, _ = plan_builder("2026-11-02T17:00:00+00:00", through_preflight=True)
    assert result["status"] == "BLOCKED"
    assert result["diagnostic"] == "P6_STATE_CHANGED_OR_UNAVAILABLE"
    assert result["production_state_unchanged"] is False
    assert result["production_state_before"] == (after if unavailable else before)
    assert result["production_state_after"] == after
    assert result["plan"]["plan_state"] == "READY"
    assert result["order_review_count"] == 1


def test_state_read_failure_is_unavailable_rather_than_absent(monkeypatch, tmp_path):
    state = tmp_path / "synthetic-state"
    state.write_bytes(b"synthetic")
    monkeypatch.setattr(preflight, "P6_STATE_FILES", (state,))

    def fail_read(self):
        raise OSError(SECRET)

    monkeypatch.setattr(Path, "read_bytes", fail_read)
    assert preflight._production_identities() == {
        state.name: {"exists": None, "sha256": None}
    }


def test_preflight_sends_only_exact_dollar_review_contract(plan_builder):
    plan, transport = plan_builder("2026-11-02T17:00:00+00:00")
    assert transport.review_arguments == [
        {
            "account_number": "SYNTHETIC",
            "symbol": "SPY",
            "side": "buy",
            "type": "market",
            "market_hours": "regular_hours",
            "time_in_force": "gfd",
            "dollar_amount": format(plan.requested_dollars, "f"),
        }
    ]


@pytest.mark.parametrize("setting_approval", [False, True])
@pytest.mark.parametrize("condition", ["checks", "approval"])
def test_review_conditions_block_ready_and_sanitize_plan(
    plan_builder, condition, setting_approval
):
    changes = (
        {"order_checks": {"alert": SECRET}}
        if condition == "checks"
        else {
            "customer_approval_required": True,
            "customer_approval_required_reason": SECRET,
        }
    )
    plan, transport = plan_builder(
        "2026-11-02T17:00:00+00:00",
        review_changes=changes,
        setting_approval=setting_approval,
    )
    assert plan.state is not LivePlanState.READY
    assert not plan.review.clean
    assert plan.provider_warning_summary == (
        (
            "ROBINHOOD_ORDER_CHECKS_PRESENT"
            if condition == "checks"
            else "ROBINHOOD_CUSTOMER_APPROVAL_REQUIRED"
        ),
    )
    assert SECRET not in json.dumps(plan.sanitized())
    assert "SYNTHETIC" not in repr(plan)
    assert transport.placed == transport.canceled == 0


def test_separate_approval_setting_blocks_even_when_review_reports_false(plan_builder):
    plan, _ = plan_builder(
        "2026-11-02T17:00:00+00:00",
        setting_approval=True,
        review_changes={"customer_approval_required": False},
    )
    assert plan.state is LivePlanState.OPERATOR_ACTION_REQUIRED
    assert plan.trade_approval_enabled


@pytest.mark.parametrize(
    "changes",
    [
        {"dollar_amount": "9.99"},
        {"symbol": "QQQ"},
        {"side": "sell"},
        {"type": "limit"},
        {"order_checks": None},
        {"order_checks": []},
        {"customer_approval_required": "false"},
    ],
)
def test_review_drift_and_malformed_conditions_block_sanitized_preflight(
    preflight_environment, plan_builder, changes
):
    result, transport = plan_builder(
        "2026-11-02T17:00:00+00:00", through_preflight=True, review_changes=changes
    )
    assert result["status"] == "BLOCKED"
    assert result["diagnostic"] == "P6_PLAN_BUILD_BLOCKED"
    assert result["order_review_count"] == 1
    assert result["order_placement_count"] == result["order_cancel_count"] == 0
    assert transport.placed == transport.canceled == 0
    assert result["production_state_unchanged"]
