from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

import pytest

from trading_bot.domain import OrderSide, OrderType, Symbol, TimeInForce
from trading_bot.review_paper import ReviewPaperIntent
from trading_bot.risk import RiskOutcome
from trading_bot.robinhood_mcp import (
    RobinhoodMcpSchemaError,
    RobinhoodReviewReadAdapter,
    RobinhoodReviewReadTransport,
    parse_equity_orders_response,
    parse_equity_quotes_response,
)


def _quote(symbol: str = "SPY") -> dict[str, object]:
    return {
        "adjusted_previous_close": "495.00",
        "ask_price": "500.10",
        "bid_price": "500.00",
        "has_traded": True,
        "last_non_reg_trade_price": None,
        "last_trade_price": "500.05",
        "previous_close": "495.00",
        "previous_close_date": "2026-10-01",
        "state": "active",
        "symbol": symbol,
        "venue_ask_time": "2026-10-02T15:00:01+00:00",
        "venue_bid_time": "2026-10-02T15:00:01+00:00",
        "venue_last_non_reg_trade_time": None,
        "venue_last_trade_time": "2026-10-02T15:00:00+00:00",
    }


def _review_payload() -> dict[str, object]:
    return {
        "data": {
            "market_data_disclosure": "verbatim disclosure",
            "order_checks": {},
            "quantity": "5",
            "quote_data": _quote(),
            "side": "buy",
            "symbol": "SPY",
            "type": "market",
        },
        "guide": "operator guidance",
    }


def _intent() -> ReviewPaperIntent:
    return ReviewPaperIntent(
        proposal_id=UUID("11111111-1111-1111-1111-111111111111"),
        order_id=UUID("22222222-2222-2222-2222-222222222222"),
        symbol=Symbol("SPY"),
        side=OrderSide.BUY,
        desired_quantity=Decimal("10"),
        approved_quantity=Decimal("5"),
        risk_outcome=RiskOutcome.RESIZED,
        risk_reason_codes=("MAX_POSITION_PERCENT",),
        proposal_reason="validated trend signal",
        proposal_confidence=Decimal("0.72"),
        order_type=OrderType.MARKET,
        time_in_force=TimeInForce.DAY,
        proposed_at=datetime(2026, 10, 2, 15, 0, tzinfo=UTC),
    )


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def review_equity_order(
        self,
        arguments: dict[str, object],
    ) -> dict[str, object]:
        self.calls.append(("review_equity_order", dict(arguments)))
        return _review_payload()

    def get_equity_quotes(
        self,
        arguments: dict[str, object],
    ) -> dict[str, object]:
        self.calls.append(("get_equity_quotes", dict(arguments)))
        return {
            "data": {
                "results": [
                    {
                        "quote": _quote(),
                        "close": {
                            "date": "2026-10-01",
                            "interpolated": False,
                            "price": "495.02",
                            "source": "sip-close",
                            "symbol": "SPY",
                        },
                    }
                ]
            },
            "guide": "quote guidance",
        }

    def get_equity_orders(
        self,
        arguments: dict[str, object],
    ) -> dict[str, object]:
        self.calls.append(("get_equity_orders", dict(arguments)))
        return {"data": {"next": "", "orders": []}, "guide": "orders guidance"}


def test_transport_protocol_has_only_review_and_read_methods() -> None:
    assert issubclass(RobinhoodReviewReadTransport, Protocol)
    public = {
        name
        for name in RobinhoodReviewReadTransport.__dict__
        if not name.startswith("_")
    }
    assert public == {
        "review_equity_order",
        "get_equity_quotes",
        "get_equity_orders",
    }


def test_review_adapter_builds_exact_phase_a_arguments() -> None:
    transport = FakeTransport()
    adapter = RobinhoodReviewReadAdapter(transport)

    review = adapter.review_market_order(
        account_number="agentic-account",
        intent=_intent(),
        received_at=datetime(2026, 10, 2, 15, 0, 2, tzinfo=UTC),
    )

    assert transport.calls == [
        (
            "review_equity_order",
            {
                "account_number": "agentic-account",
                "market_hours": "regular_hours",
                "quantity": "5",
                "side": "buy",
                "symbol": "SPY",
                "time_in_force": "gfd",
                "type": "market",
            },
        )
    ]
    assert review.quantity == Decimal("5")
    assert review.quote.ask_price == Decimal("500.10")
    assert review.market_data_disclosure == "verbatim disclosure"


def test_review_adapter_never_defaults_account_number() -> None:
    adapter = RobinhoodReviewReadAdapter(FakeTransport())

    with pytest.raises(ValueError, match="account_number"):
        adapter.review_market_order(
            account_number="",
            intent=_intent(),
            received_at=datetime(2026, 10, 2, 15, 0, 2, tzinfo=UTC),
        )


def test_review_schema_rejects_numeric_quantity_instead_of_decimal_text() -> None:
    payload = _review_payload()
    data = payload["data"]
    assert isinstance(data, dict)
    data["quantity"] = 5
    adapter = RobinhoodReviewReadAdapter(FakeTransport())
    adapter._transport.review_equity_order = lambda arguments: payload

    with pytest.raises(RobinhoodMcpSchemaError, match="decimal string"):
        adapter.review_market_order(
            account_number="agentic-account",
            intent=_intent(),
            received_at=datetime(2026, 10, 2, 15, 0, 2, tzinfo=UTC),
        )


def test_equity_quotes_parser_preserves_official_close_and_quote() -> None:
    payload = {
        "data": {
            "results": [
                {
                    "quote": _quote(),
                    "close": {
                        "date": "2026-10-01",
                        "interpolated": False,
                        "price": "495.02",
                        "source": "sip-close",
                        "symbol": "SPY",
                    },
                },
                None,
            ]
        }
    }

    parsed = parse_equity_quotes_response(payload)

    assert len(parsed.results) == 2
    first = parsed.results[0]
    assert first is not None
    assert first.quote is not None
    assert first.close is not None
    assert first.quote.current_trade_candidate() == (
        Decimal("500.05"),
        datetime(2026, 10, 2, 15, 0, tzinfo=UTC),
    )
    assert first.close.price == Decimal("495.02")
    assert parsed.results[1] is None


def test_quotes_adapter_caps_batch_at_twenty_symbols() -> None:
    adapter = RobinhoodReviewReadAdapter(FakeTransport())
    symbols = tuple(Symbol(f"S{i}") for i in range(21))

    with pytest.raises(ValueError, match="at most 20"):
        adapter.equity_quotes(symbols)


def test_agentic_orders_adapter_forces_agentic_filter() -> None:
    transport = FakeTransport()
    adapter = RobinhoodReviewReadAdapter(transport)

    page = adapter.agentic_equity_orders(
        account_number="agentic-account",
        created_at_gte=datetime(2026, 10, 2, 14, 59, tzinfo=UTC),
        symbol=Symbol("SPY"),
    )

    assert page.orders == ()
    assert transport.calls[-1] == (
        "get_equity_orders",
        {
            "account_number": "agentic-account",
            "created_at_gte": "2026-10-02T14:59:00+00:00",
            "placed_agent": "agentic",
            "symbol": "SPY",
        },
    )


def test_equity_orders_parser_preserves_agentic_ref_and_executions() -> None:
    payload = {
        "data": {
            "next": "cursor-2",
            "orders": [
                {
                    "average_price": "500.12",
                    "created_at": "2026-10-02T15:00:03+00:00",
                    "cumulative_quantity": "5",
                    "dollar_based_amount": None,
                    "executions": [
                        {
                            "fees": "0.01",
                            "id": "execution-1",
                            "price": "500.12",
                            "quantity": "5",
                            "timestamp": "2026-10-02T15:00:04+00:00",
                        }
                    ],
                    "fees": "0.01",
                    "id": "order-1",
                    "instrument_id": "instrument-1",
                    "last_transaction_at": "2026-10-02T15:00:04+00:00",
                    "market_hours": "regular_hours",
                    "placed_agent": "agentic",
                    "price": None,
                    "quantity": "5",
                    "ref_id": "paper-safety-check",
                    "reject_reason": None,
                    "side": "buy",
                    "state": "filled",
                    "stop_price": None,
                    "symbol": "SPY",
                    "time_in_force": "gfd",
                    "trigger": "immediate",
                    "type": "market",
                }
            ],
        }
    }

    page = parse_equity_orders_response(payload)

    assert page.next_cursor == "cursor-2"
    order = page.orders[0]
    assert order is not None
    assert order.placed_agent == "agentic"
    assert order.ref_id == "paper-safety-check"
    assert order.side is OrderSide.BUY
    assert order.average_price == Decimal("500.12")
    assert order.executions[0].execution_id == "execution-1"


def test_quote_and_close_symbol_conflict_is_rejected() -> None:
    payload = {
        "data": {
            "results": [
                {
                    "quote": _quote("SPY"),
                    "close": {
                        "date": "2026-10-01",
                        "interpolated": False,
                        "price": "495.02",
                        "source": "sip-close",
                        "symbol": "QQQ",
                    },
                }
            ]
        }
    }

    with pytest.raises(RobinhoodMcpSchemaError, match="symbols must match"):
        parse_equity_quotes_response(payload)
