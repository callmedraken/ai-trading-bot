from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from trading_bot.desktop_paper.robinhood_reconciliation import MAX_POSITION_PAGES
from trading_bot.portfolio_manager import (
    AccountBindingStatus,
    ObservationCondition,
    ObservationProvenance,
    OrderCoverage,
    PortfolioObservationError,
    account_candidates,
    bind_account,
    observe_robinhood_portfolio,
)

from .conftest import NOW, make_observation, make_position

ACCOUNT = "SYNTHETIC-ACCOUNT-123456"


def _quote(symbol: str, price: str, at: datetime = NOW):
    stamp = at.isoformat().replace("+00:00", "Z")
    return {
        "data": {
            "results": [
                {
                    "quote": {
                        "symbol": symbol,
                        "state": "active",
                        "has_traded": True,
                        "adjusted_previous_close": price,
                        "previous_close": price,
                        "ask_price": price,
                        "bid_price": price,
                        "last_trade_price": price,
                        "last_non_reg_trade_price": None,
                        "venue_ask_time": stamp,
                        "venue_bid_time": stamp,
                        "venue_last_trade_time": stamp,
                        "venue_last_non_reg_trade_time": None,
                    }
                }
            ]
        }
    }


class FakeRead:
    def __init__(self) -> None:
        self.account_number = ACCOUNT
        self.accounts = {
            "data": {"accounts": [{"account_number": ACCOUNT, "agentic_allowed": True}]}
        }
        self.portfolio = {
            "data": {
                "total_value": "10000",
                "cash": "8850",
                "equity_value": "1150",
                "currency": "USD",
                "buying_power": {
                    "buying_power": "8850",
                    "unleveraged_buying_power": "8850",
                    "display_currency": "USD",
                },
            }
        }
        self.positions = [
            {
                "symbol": "SPY",
                "quantity": "1.5",
                "shares_available_for_sells": "1.0",
                "average_buy_price": None,
                "type": "long",
            },
            {
                "symbol": "GLD",
                "quantity": "2",
                "shares_available_for_sells": "2",
                "average_buy_price": "190",
                "type": "long",
            },
        ]
        self.quotes = {"SPY": _quote("SPY", "500"), "GLD": _quote("GLD", "200")}
        self.orders = []
        self.calls = []
        self.position_pages = None
        self.order_pages = None
        self.echo_account_number = None
        self.account_records = None

    def get_accounts(self):
        self.calls.append(("accounts", {}))
        if self.account_records is not None:
            return {"data": {"accounts": self.account_records}}
        return self.accounts

    def get_portfolio(self, arguments):
        self.calls.append(("portfolio", dict(arguments)))
        result = dict(self.portfolio)
        if self.echo_account_number is not None:
            result["data"] = dict(
                result["data"], account_number=self.echo_account_number
            )
        return result

    def get_equity_positions(self, arguments):
        self.calls.append(("positions", dict(arguments)))
        if self.position_pages is not None:
            return self.position_pages.pop(0)
        rows = self.positions
        result = {"data": {"positions": rows}}
        if self.echo_account_number is not None:
            result["data"]["account_number"] = self.echo_account_number
        return result

    def get_equity_quotes(self, arguments):
        self.calls.append(("quotes", dict(arguments)))
        result = self.quotes.get(arguments["symbols"][0], {"data": {"results": []}})
        if self.echo_account_number is not None:
            result = dict(result)
            result["data"] = dict(
                result["data"], account_number=self.echo_account_number
            )
        return result

    def get_equity_orders(self, arguments):
        self.calls.append(("orders", dict(arguments)))
        if self.order_pages is not None:
            return self.order_pages.pop(0)
        return {"data": {"orders": self.orders}}


def test_account_selection_requires_explicit_fingerprint_and_blocks_ambiguity():
    single = account_candidates(FakeRead().accounts)
    assert single[0].fingerprint == hashlib.sha256(ACCOUNT.encode()).hexdigest()
    assert bind_account(single, None).status is AccountBindingStatus.SELECTION_REQUIRED
    assert (
        bind_account(single, single[0].fingerprint).status is AccountBindingStatus.BOUND
    )

    other = hashlib.sha256(b"other synthetic account").hexdigest()
    multiple = (single[0], type(single[0])(other, True))
    assert (
        bind_account(multiple, None).status
        is AccountBindingStatus.MULTIPLE_ELIGIBLE_ACCOUNTS
    )
    assert bind_account(multiple, other).status is AccountBindingStatus.BOUND
    reads = FakeRead()
    reads.account_records = [
        {"account_number": ACCOUNT, "agentic_allowed": True},
        {"account_number": "OTHER-SYNTHETIC", "agentic_allowed": True},
    ]
    with pytest.raises(PortfolioObservationError) as caught:
        observe_robinhood_portfolio(
            reads, observed_at=NOW, selected_account_fingerprint=single[0].fingerprint
        )
    assert (
        caught.value.binding_result.status
        is AccountBindingStatus.MULTIPLE_ELIGIBLE_ACCOUNTS
    )
    assert [name for name, _ in reads.calls] == ["accounts"]
    assert ACCOUNT not in str(caught.value)


def test_fake_robinhood_transport_adopts_fractional_holdings_without_filling_history():
    reads = FakeRead()
    fingerprint = hashlib.sha256(ACCOUNT.encode()).hexdigest()
    result = observe_robinhood_portfolio(
        reads, observed_at=NOW, selected_account_fingerprint=fingerprint
    )
    assert result.provenance is ObservationProvenance.ROBINHOOD_READ_ONLY
    assert result.positions[0].quantity == Decimal("1.5")
    assert result.positions[0].available_to_sell == Decimal("1.0")
    assert result.positions[0].average_cost is None
    assert result.positions[0].supported is None
    assert ObservationCondition.ASSET_TYPE_UNKNOWN in result.conditions
    assert result.positions[0].unrealized_pnl is None
    assert result.positions[1].average_cost == Decimal("190")
    assert result.positions[1].price_observed_at == NOW
    assert result.broker_reported_equity == Decimal("10000")
    assert result.locally_computed_equity == Decimal("10000.0")
    assert result.broker_reported_position_value == Decimal("1150")
    assert result.coverage.order_scope is OrderCoverage.ROBINHOOD_AGENTIC_BOUNDED
    assert ObservationCondition.ORDER_SCOPE_INCOMPLETE in result.conditions
    assert not result.preview_eligible
    assert ACCOUNT not in repr(result)
    assert [name for name, _ in reads.calls].count("quotes") == 2


def test_unknown_position_classification_and_explicit_unsupported_hint_stay_visible():
    fingerprint = hashlib.sha256(ACCOUNT.encode()).hexdigest()
    reads = FakeRead()
    reads.positions[0]["type"] = "unclassified"
    result = observe_robinhood_portfolio(
        reads, observed_at=NOW, selected_account_fingerprint=fingerprint
    )
    assert result.positions[0].position_type.value == "UNKNOWN"
    assert ObservationCondition.POSITION_TYPE_UNKNOWN in result.conditions
    assert not result.preview_eligible

    reads = FakeRead()
    reads.positions[0]["asset_type"] = "crypto"
    result = observe_robinhood_portfolio(
        reads, observed_at=NOW, selected_account_fingerprint=fingerprint
    )
    assert result.positions[0].supported is False
    assert ObservationCondition.UNSUPPORTED_ASSET in result.conditions
    assert not result.preview_eligible


@pytest.mark.parametrize("page_kind", ["positions", "orders"])
def test_row_account_echo_mismatch_blocks_before_adopting_rows(page_kind: str):
    reads = FakeRead()
    raw_account = "MISMATCHED-ROW-ACCOUNT"
    if page_kind == "positions":
        reads.position_pages = [
            {"data": {"positions": [{"account_number": raw_account}]}}
        ]
    else:
        reads.order_pages = [{"data": {"orders": [{"account_number": raw_account}]}}]

    with pytest.raises(PortfolioObservationError) as caught:
        observe_robinhood_portfolio(
            reads,
            observed_at=NOW,
            selected_account_fingerprint=hashlib.sha256(ACCOUNT.encode()).hexdigest(),
        )

    assert caught.value.code == "ACCOUNT_ECHO_MISMATCH"
    assert caught.value.condition is ObservationCondition.ACCOUNT_MISMATCH
    assert raw_account not in str(caught.value)


def test_missing_cash_and_buying_power_remain_unknown():
    reads = FakeRead()
    reads.portfolio["data"].pop("cash")
    reads.portfolio["data"].pop("buying_power")

    result = observe_robinhood_portfolio(
        reads,
        observed_at=NOW,
        selected_account_fingerprint=hashlib.sha256(ACCOUNT.encode()).hexdigest(),
    )

    assert result.cash is None
    assert result.buying_power is None
    assert result.unleveraged_buying_power is None
    assert ObservationCondition.MISSING_CASH in result.conditions
    assert ObservationCondition.MISSING_BUYING_POWER in result.conditions
    assert ObservationCondition.MISSING_UNLEVERAGED_BUYING_POWER in result.conditions
    assert not result.preview_eligible


def test_missing_unleveraged_buying_power_stays_unknown():
    reads = FakeRead()
    reads.portfolio["data"]["buying_power"].pop("unleveraged_buying_power")

    result = observe_robinhood_portfolio(
        reads,
        observed_at=NOW,
        selected_account_fingerprint=hashlib.sha256(ACCOUNT.encode()).hexdigest(),
    )

    assert result.buying_power == Decimal("8850")
    assert result.unleveraged_buying_power is None
    assert ObservationCondition.MISSING_UNLEVERAGED_BUYING_POWER in result.conditions
    assert not result.preview_eligible


def test_empty_next_cursor_retains_current_terminal_sentinel():
    reads = FakeRead()
    reads.position_pages = [{"data": {"positions": [], "next": ""}}]

    result = observe_robinhood_portfolio(
        reads,
        observed_at=NOW,
        selected_account_fingerprint=hashlib.sha256(ACCOUNT.encode()).hexdigest(),
    )

    assert result.positions == ()
    assert result.coverage.pagination_complete


def test_cash_only_account_is_valid_and_stable_account_namespace_isolated():
    cash_only = make_observation()
    other_account = hashlib.sha256(b"intraday account").hexdigest()
    other = make_observation(account_fingerprint=other_account)
    assert cash_only.positions == ()
    assert cash_only.locally_computed_equity == Decimal("10000")
    assert cash_only.snapshot_id != other.snapshot_id
    assert cash_only.account_fingerprint != other.account_fingerprint


def test_missing_stale_and_echo_mismatch_remain_explicit():
    reads = FakeRead()
    reads.quotes["GLD"] = {"data": {"results": []}}
    result = observe_robinhood_portfolio(
        reads,
        observed_at=NOW,
        selected_account_fingerprint=hashlib.sha256(ACCOUNT.encode()).hexdigest(),
    )
    assert result.positions[1].current_price is None
    assert ObservationCondition.MISSING_PRICE in result.conditions
    assert not result.coverage.quotes_complete
    assert not result.preview_eligible

    stale_at = NOW - timedelta(minutes=10)
    reads = FakeRead()
    reads.quotes["SPY"] = _quote("SPY", "500", stale_at)
    stale = observe_robinhood_portfolio(
        reads,
        observed_at=NOW,
        selected_account_fingerprint=hashlib.sha256(ACCOUNT.encode()).hexdigest(),
    )
    assert ObservationCondition.STALE_PRICE in stale.conditions
    assert not stale.preview_eligible

    reads = FakeRead()
    reads.echo_account_number = "MISMATCHED-SECRET-ACCOUNT"
    with pytest.raises(PortfolioObservationError) as caught:
        observe_robinhood_portfolio(
            reads,
            observed_at=NOW,
            selected_account_fingerprint=hashlib.sha256(ACCOUNT.encode()).hexdigest(),
        )
    assert caught.value.code == "ACCOUNT_ECHO_MISMATCH"
    assert "MISMATCHED-SECRET-ACCOUNT" not in str(caught.value)


def test_malformed_pagination_is_explicit_and_prevents_quote_reads():
    reads = FakeRead()
    reads.position_pages = [
        {"data": {"positions": [], "next": "same"}},
        {"data": {"positions": [], "next": "same"}},
    ]
    with pytest.raises(PortfolioObservationError) as caught:
        observe_robinhood_portfolio(
            reads,
            observed_at=NOW,
            selected_account_fingerprint=hashlib.sha256(ACCOUNT.encode()).hexdigest(),
        )
    assert caught.value.condition is ObservationCondition.PAGINATION_INCOMPLETE
    assert not any(name == "quotes" for name, _ in reads.calls)


@pytest.mark.parametrize(
    "position_page",
    [
        {"data": {"positions": [], "next": []}},
        {"data": {"positions": [], "next": "x" * 4097}},
    ],
)
def test_invalid_position_cursor_is_incomplete(position_page):
    reads = FakeRead()
    reads.position_pages = [position_page]

    with pytest.raises(PortfolioObservationError) as caught:
        observe_robinhood_portfolio(
            reads,
            observed_at=NOW,
            selected_account_fingerprint=hashlib.sha256(ACCOUNT.encode()).hexdigest(),
        )

    assert caught.value.code == "POSITIONS_CURSOR_INVALID"
    assert caught.value.condition is ObservationCondition.PAGINATION_INCOMPLETE
    assert not any(name == "quotes" for name, _ in reads.calls)


def test_position_page_limit_is_incomplete_without_partial_observation():
    reads = FakeRead()
    reads.position_pages = [
        {"data": {"positions": [], "next": f"page-{index}"}}
        for index in range(MAX_POSITION_PAGES)
    ]

    with pytest.raises(PortfolioObservationError) as caught:
        observe_robinhood_portfolio(
            reads,
            observed_at=NOW,
            selected_account_fingerprint=hashlib.sha256(ACCOUNT.encode()).hexdigest(),
        )

    assert caught.value.code == "POSITIONS_PAGE_BOUND_EXCEEDED"
    assert caught.value.condition is ObservationCondition.PAGINATION_INCOMPLETE
    assert not any(name == "quotes" for name, _ in reads.calls)


def test_later_position_page_failure_does_not_return_partial_success():
    class LaterPageFailure(FakeRead):
        def get_equity_positions(self, arguments):
            self.calls.append(("positions", dict(arguments)))
            if "cursor" in arguments:
                raise RuntimeError("raw provider response and token")
            return {"data": {"positions": [], "next": "page-2"}}

    reads = LaterPageFailure()

    with pytest.raises(PortfolioObservationError) as caught:
        observe_robinhood_portfolio(
            reads,
            observed_at=NOW,
            selected_account_fingerprint=hashlib.sha256(ACCOUNT.encode()).hexdigest(),
        )

    assert caught.value.code == "POSITIONS_READ_FAILED"
    assert caught.value.condition is ObservationCondition.PAGINATION_INCOMPLETE
    assert "token" not in str(caught.value)
    assert not any(name == "quotes" for name, _ in reads.calls)


def test_duplicate_position_rows_are_rejected_before_quote_reads():
    reads = FakeRead()
    reads.positions = [reads.positions[0], reads.positions[0]]

    with pytest.raises(PortfolioObservationError) as caught:
        observe_robinhood_portfolio(
            reads,
            observed_at=NOW,
            selected_account_fingerprint=hashlib.sha256(ACCOUNT.encode()).hexdigest(),
        )

    assert caught.value.code == "POSITION_SYMBOL_DUPLICATE"
    assert not any(name == "quotes" for name, _ in reads.calls)


def test_account_mismatch_and_external_holding_changes_are_not_normalized_away():
    position = make_position("SPY", "1", cost=None)
    mismatched = make_observation(
        (position,),
        cash="9900",
        observed_account_fingerprint=hashlib.sha256(b"different account").hexdigest(),
    )
    assert ObservationCondition.ACCOUNT_MISMATCH in mismatched.conditions
    assert not mismatched.preview_eligible
    before = make_observation((position,), cash="9900")
    after = make_observation((make_position("SPY", "1.25", cost=None),), cash="9875")
    assert before.snapshot_id != after.snapshot_id
    assert before.positions[0].average_cost is None
