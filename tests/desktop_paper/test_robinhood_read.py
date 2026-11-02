"""Synthetic observations only: broker context never supplies paper authority."""

import copy
import hashlib
import json
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext

import pytest

from trading_bot.desktop_paper.robinhood_read import (
    AgenticAccountIdentity,
    EquityPositionObservation,
    ObservationError,
    parse_portfolio,
    parse_position,
    parse_spy_quote,
    resolve_account,
)
from trading_bot.desktop_paper.robinhood_reconciliation import (
    MAX_ORDER_PAGES,
    MAX_ORDERS,
    observe_robinhood_baseline,
)

NOW = datetime(2026, 11, 1, 20, tzinfo=UTC)
ACCOUNT = "SYNTHETIC-ACCOUNT-123456"


def quote_payload():
    return {
        "data": {
            "results": [
                {
                    "quote": {
                        "symbol": "SPY",
                        "state": "active",
                        "has_traded": True,
                        "adjusted_previous_close": "500",
                        "previous_close": "500",
                        "ask_price": "502",
                        "bid_price": "501",
                        "last_trade_price": "501.5",
                        "last_non_reg_trade_price": "501.75",
                        "venue_ask_time": "2026-11-01T19:00:00Z",
                        "venue_bid_time": "2026-11-01T19:00:00Z",
                        "venue_last_trade_time": "2026-11-01T19:00:00Z",
                        "venue_last_non_reg_trade_time": "2026-11-01T19:01:00Z",
                    }
                }
            ]
        }
    }


def order(identifier="synthetic-order-1"):
    return {
        "id": identifier,
        "symbol": "SPY",
        "side": "buy",
        "state": "filled",
        "quantity": "5",
        "cumulative_quantity": "5",
        "created_at": "2026-10-31T20:00:00Z",
        "placed_agent": "agentic",
        "agent_initiated": True,
        "ref_id": "some-other-agent",
    }


class FakeReads:
    def __init__(self):
        self.accounts = {
            "data": {"accounts": [{"account_number": ACCOUNT, "agentic_allowed": True}]}
        }
        self.portfolio = {
            "data": {
                "total_value": "100000",
                "cash": "7000",
                "equity_value": "93000",
                "currency": "USD",
                "buying_power": {
                    "buying_power": "8000",
                    "unleveraged_buying_power": "7000",
                    "display_currency": "USD",
                },
            }
        }
        self.positions = [
            {
                "symbol": "SPY",
                "quantity": "5",
                "shares_available_for_sells": "4",
                "average_buy_price": "490",
                "type": "long",
            }
        ]
        self.quote = quote_payload()
        self.orders = [order()]
        self.calls = []
        self.order_pages = None
        self.position_pages = None

    def get_accounts(self):
        self.calls.append(("get_accounts", {}))
        return copy.deepcopy(self.accounts)

    def get_portfolio(self, arguments):
        self.calls.append(("get_portfolio", arguments))
        return copy.deepcopy(self.portfolio)

    def get_equity_positions(self, arguments):
        self.calls.append(("get_equity_positions", arguments))
        return (
            self.position_pages.pop(0)
            if self.position_pages is not None
            else {"data": {"positions": copy.deepcopy(self.positions)}}
        )

    def get_equity_quotes(self, arguments):
        self.calls.append(("get_equity_quotes", arguments))
        return copy.deepcopy(self.quote)

    def get_equity_orders(self, arguments):
        self.calls.append(("get_equity_orders", arguments))
        return (
            self.order_pages.pop(0)
            if self.order_pages is not None
            else {"data": {"orders": copy.deepcopy(self.orders)}}
        )


def snapshot():
    return observe_robinhood_baseline(FakeReads(), observed_at=NOW)


def test_baseline_can_contain_real_positions_and_other_agents_orders():
    read = FakeReads()
    result = observe_robinhood_baseline(read, observed_at=NOW)
    assert result.status == "READ_ONLY_CONNECTED"
    assert len(result.positions) == len(result.orders) == 1
    assert result.local_expected_broker_effect_count == 0
    assert result.orders[0].bot_attributable is False
    assert read.calls[-1] == (
        "get_equity_orders",
        {
            "account_number": ACCOUNT,
            "placed_agent": "agentic",
            "created_at_gte": (NOW - timedelta(days=7)).isoformat(),
        },
    )
    assert read.calls[3] == ("get_equity_quotes", {"symbols": ["SPY"]})


def test_empty_baseline_is_valid():
    read = FakeReads()
    read.positions = read.orders = []
    assert observe_robinhood_baseline(read, observed_at=NOW).positions == ()


def test_zero_portfolio_and_unfilled_order_are_valid_observations():
    read = FakeReads()
    for key in ("total_value", "cash", "equity_value"):
        read.portfolio["data"][key] = "0"
    read.portfolio["data"]["buying_power"]["buying_power"] = "0"
    read.portfolio["data"]["buying_power"]["unleveraged_buying_power"] = "0"
    read.orders[0]["cumulative_quantity"] = "0"
    read.orders[0]["state"] = "new"
    result = observe_robinhood_baseline(read, observed_at=NOW)
    assert result.portfolio.cash == 0
    assert result.orders[0].cumulative_quantity == 0


def test_direct_snapshot_quote_construction_cannot_bypass_strict_validation():
    first = snapshot()
    with pytest.raises(ObservationError):
        replace(first, spy_quote=replace(first.spy_quote, ask_price=Decimal("0")))


def test_even_account_identifier_echo_in_symbol_is_rejected():
    read = FakeReads()
    read.accounts["data"]["accounts"][0]["account_number"] = "A1234567"
    read.positions[0]["symbol"] = "A1234567"
    with pytest.raises(ObservationError, match="ACCOUNT_IDENTIFIER_ECHO_REJECTED"):
        observe_robinhood_baseline(read, observed_at=NOW)


def test_position_cursor_repetition_fails_before_later_reads():
    read = FakeReads()
    read.position_pages = [{"data": {"positions": [], "next": "a"}}] * 2
    with pytest.raises(ObservationError):
        observe_robinhood_baseline(read, observed_at=NOW)
    assert not any(name == "get_equity_quotes" for name, _ in read.calls)


def test_account_fingerprint_exact_deterministic_and_no_raw_evidence():
    identity = resolve_account(FakeReads().accounts)
    assert identity.fingerprint == hashlib.sha256(ACCOUNT.encode()).hexdigest()
    assert ACCOUNT not in repr(identity)
    sanitized = json.dumps(snapshot().sanitized(), sort_keys=True)
    assert ACCOUNT not in sanitized and "some-other-agent" not in sanitized
    assert "100000" not in sanitized and "synthetic-order-1" not in sanitized


@pytest.mark.parametrize(
    "accounts",
    [
        [],
        [{"account_number": ACCOUNT, "agentic_allowed": False}],
        [{"account_number": ACCOUNT, "agentic_allowed": 1}],
        [{"account_number": ACCOUNT, "agentic_allowed": True}] * 2,
        [
            {"account_number": ACCOUNT, "agentic_allowed": True},
            {"account_number": "other", "agentic_allowed": True},
        ],
    ],
)
def test_canonical_single_agentic_account_required(accounts):
    with pytest.raises(ObservationError):
        resolve_account({"data": {"accounts": accounts}})


@pytest.mark.parametrize(
    "field,value",
    [
        ("cash", None),
        ("total_value", "NaN"),
        ("equity_value", 1),
        ("currency", "EUR"),
        ("buying_power", None),
    ],
)
def test_malformed_missing_portfolio_fails_closed(field, value):
    payload = FakeReads().portfolio
    payload["data"][field] = value
    with pytest.raises(ObservationError):
        parse_portfolio(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("symbol", "spy"),
        ("quantity", "NaN"),
        ("quantity", "-1"),
        ("quantity", "0"),
        ("shares_available_for_sells", "-1"),
        ("quantity", None),
        ("type", "unknown"),
        ("average_buy_price", "Infinity"),
    ],
)
def test_malformed_positions_fail_closed(field, value):
    position = FakeReads().positions[0]
    position[field] = value
    with pytest.raises(ObservationError):
        parse_position(position)


def test_duplicate_positions_even_across_pages_fail_closed():
    read = FakeReads()
    read.position_pages = [
        {"data": {"positions": read.positions, "next": "a"}},
        {"data": {"positions": read.positions}},
    ]
    with pytest.raises(ObservationError):
        observe_robinhood_baseline(read, observed_at=NOW)


@pytest.mark.parametrize(
    "field,value",
    [
        ("symbol", "QQQ"),
        ("state", "inactive"),
        ("has_traded", False),
        ("ask_price", "0"),
        ("bid_price", "NaN"),
        ("last_trade_price", "-1"),
        ("venue_last_trade_time", "2026-11-01T19:00:00"),
        ("venue_ask_time", "garbage"),
    ],
)
def test_strict_spy_quote(field, value):
    payload = quote_payload()
    payload["data"]["results"][0]["quote"][field] = value
    with pytest.raises((ValueError, TypeError)):
        parse_spy_quote(payload)


def test_public_current_trade_semantics_reused_without_fill():
    result = snapshot()
    assert result.spy_quote.current_trade_candidate() == (
        Decimal("501.75"),
        datetime(2026, 11, 1, 19, 1, tzinfo=UTC),
    )
    assert not hasattr(result, "fills") and not hasattr(result, "cursor_index")


@pytest.mark.parametrize(
    "mode", ["repeated", "pages", "rows", "duplicate", "window", "filter"]
)
def test_order_history_bounds_and_filters_fail_closed(mode):
    read = FakeReads()
    if mode == "repeated":
        read.order_pages = [{"data": {"orders": [], "next": "a"}}] * 2
    elif mode == "pages":
        read.order_pages = [
            {"data": {"orders": [], "next": str(i)}} for i in range(MAX_ORDER_PAGES)
        ]
    elif mode == "rows":
        read.orders = [order(str(i)) for i in range(MAX_ORDERS + 1)]
    elif mode == "duplicate":
        read.orders *= 2
    elif mode == "window":
        read.orders[0]["created_at"] = "2020-01-01T00:00:00Z"
    else:
        read.orders[0]["placed_agent"] = "user"
    with pytest.raises(ObservationError):
        observe_robinhood_baseline(read, observed_at=NOW)
    assert sum(name == "get_equity_orders" for name, _ in read.calls) <= MAX_ORDER_PAGES


def test_pagination_preserves_filters_and_canonical_order():
    read = FakeReads()
    read.order_pages = [
        {"data": {"orders": [order("z")], "next": "opaque"}},
        {"data": {"orders": [order("a")], "next": ""}},
    ]
    result = observe_robinhood_baseline(read, observed_at=NOW)
    assert [o.order_id for o in result.orders] == ["a", "z"]
    first, second = [args for name, args in read.calls if name == "get_equity_orders"]
    assert second == {**first, "cursor": "opaque"}


def test_snapshot_immutable_deterministic_and_not_paper_authority():
    first = snapshot()
    assert first == snapshot()
    with localcontext() as context:
        context.prec = 2
        assert first.sanitized() == snapshot().sanitized()
    with pytest.raises(FrozenInstanceError):
        first.local_expected_broker_effect_count = 1
    with pytest.raises((ValueError, TypeError)):
        replace(first, local_expected_broker_effect_count=1)
    assert not hasattr(first, "risk_context") and not hasattr(first, "paper_policy")
    assert not hasattr(first.portfolio, "to_paper_account")
    with pytest.raises(ObservationError):
        EquityPositionObservation("SPY", Decimal("-1"), Decimal("0"), None, "long")
    with pytest.raises(ObservationError):
        AgenticAccountIdentity(ACCOUNT, 1, 2)
