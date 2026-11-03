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

    def discover_required_capabilities(self):
        pass

    def get_accounts(self):
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
        return {
            "data": {
                "symbol": "SPY",
                "tradable": True,
                "fractional_trading": True,
                "dollar_orders": True,
            }
        }

    def get_trade_approval_setting(self, arguments):
        return {"data": {"enabled": False}}

    def review_equity_order(self, arguments):
        self.reviews += 1
        return {"data": {**arguments, "warnings": []}}

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

    def build(instant, *, rising=True):
        now = datetime.fromisoformat(instant)
        transport = _PlanTransport(now, rising=rising)
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
