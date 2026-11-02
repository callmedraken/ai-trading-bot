"""Bounded broker observations; no order intent, paper cursor, or account mutation."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Protocol

from trading_bot.desktop_paper.robinhood_read import (
    EquityOrderObservation,
    EquityPositionObservation,
    ObservationError,
    PortfolioObservation,
    commitment,
    data,
    parse_order,
    parse_portfolio,
    parse_position,
    parse_spy_quote,
    resolve_account,
    utc,
    validate_spy_quote,
)
from trading_bot.robinhood_mcp.models import RobinhoodQuoteData

MAX_POSITION_PAGES = 3
MAX_POSITIONS = 1000
MAX_ORDER_PAGES = 3
MAX_ORDERS = 300
ORDER_WINDOW_DAYS = 7


class ReadBoundary(Protocol):
    def get_accounts(self) -> Mapping[str, object]: ...
    def get_portfolio(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]: ...
    def get_equity_positions(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]: ...
    def get_equity_quotes(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]: ...
    def get_equity_orders(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]: ...


@dataclass(frozen=True, slots=True)
class RobinhoodReconciliationSnapshot:
    observed_at: datetime
    account_fingerprint: str
    observed_account_count: int
    eligible_account_count: int
    portfolio: PortfolioObservation
    positions: tuple[EquityPositionObservation, ...]
    spy_quote: RobinhoodQuoteData
    orders: tuple[EquityOrderObservation, ...]
    orders_since: datetime
    local_expected_broker_effect_count: int = field(default=0, init=False)
    status: str = field(default="READ_ONLY_CONNECTED", init=False)
    diagnostics: tuple[str, ...] = field(
        default=("PROVIDER_BASELINE_OBSERVED", "NO_BOT_ORDER_ATTRIBUTION"), init=False
    )

    def __post_init__(self) -> None:
        utc(self.observed_at)
        utc(self.orders_since)
        if len(self.account_fingerprint) != 64 or any(
            c not in "0123456789abcdef" for c in self.account_fingerprint
        ):
            raise ObservationError("ACCOUNT_FINGERPRINT_INVALID")
        if (
            type(self.observed_account_count) is not int
            or not 1 <= self.observed_account_count <= 100
            or type(self.eligible_account_count) is not int
            or self.eligible_account_count != 1
        ):
            raise ObservationError("ACCOUNT_COUNTS_INVALID")
        if (
            type(self.portfolio) is not PortfolioObservation
            or type(self.spy_quote) is not RobinhoodQuoteData
        ):
            raise ObservationError("SNAPSHOT_TYPES_INVALID")
        if (
            type(self.positions) is not tuple
            or len(self.positions) > MAX_POSITIONS
            or any(type(p) is not EquityPositionObservation for p in self.positions)
            or tuple(sorted(self.positions, key=lambda p: p.symbol)) != self.positions
            or len({p.symbol for p in self.positions}) != len(self.positions)
        ):
            raise ObservationError("SNAPSHOT_POSITIONS_INVALID")
        if (
            type(self.orders) is not tuple
            or len(self.orders) > MAX_ORDERS
            or any(type(o) is not EquityOrderObservation for o in self.orders)
            or tuple(sorted(self.orders, key=lambda o: (o.created_at, o.order_id)))
            != self.orders
            or len({o.order_id for o in self.orders}) != len(self.orders)
        ):
            raise ObservationError("SNAPSHOT_ORDERS_INVALID")
        if self.orders_since != self.observed_at - timedelta(
            days=ORDER_WINDOW_DAYS
        ) or any(
            not self.orders_since <= o.created_at <= self.observed_at
            for o in self.orders
        ):
            raise ObservationError("SNAPSHOT_ORDER_WINDOW_INVALID")
        validate_spy_quote(self.spy_quote)

    def sanitized(self) -> dict[str, object]:
        price, stamp = self.spy_quote.current_trade_candidate()
        return {
            "observed_at": self.observed_at.isoformat(),
            "account_fingerprint": self.account_fingerprint,
            "observed_account_count": self.observed_account_count,
            "eligible_agentic_account_count": self.eligible_account_count,
            "portfolio_material_sha256": self.portfolio.digest,
            "portfolio_currency": self.portfolio.currency,
            "position_count": len(self.positions),
            "canonical_symbols": [p.symbol for p in self.positions],
            "position_material_sha256": commitment([asdict(p) for p in self.positions]),
            "spy_quote": {
                "symbol": "SPY",
                "price": str(price),
                "timestamp": stamp.isoformat(),
                "ask": str(self.spy_quote.ask_price),
                "bid": str(self.spy_quote.bid_price),
            },
            "order_count": len(self.orders),
            "orders_since": self.orders_since.isoformat(),
            "order_material_sha256": commitment([asdict(o) for o in self.orders]),
            "order_history_baseline_observed": True,
            "local_expected_broker_effect_count": 0,
            "reconciliation_status": self.status,
            "diagnostics": list(self.diagnostics),
        }


def _pages(
    read: Callable[[Mapping[str, object]], Mapping[str, object]],
    arguments: dict[str, object],
    key: str,
    max_pages: int,
    max_items: int,
) -> list[object]:
    rows: list[object] = []
    seen = set()
    request = dict(arguments)
    for _ in range(max_pages):
        page = data(read(request))
        items = page.get(key)
        if not isinstance(items, list) or len(rows) + len(items) > max_items:
            raise ObservationError("COLLECTION_BOUND_OR_SHAPE_INVALID")
        rows.extend(items)
        cursor = page.get("next")
        if cursor is None or cursor == "":
            return rows
        if (
            not isinstance(cursor, str)
            or not cursor
            or len(cursor) > 4096
            or cursor in seen
        ):
            raise ObservationError("COLLECTION_CURSOR_INVALID")
        seen.add(cursor)
        request = {**arguments, "cursor": cursor}
    raise ObservationError("COLLECTION_PAGE_BOUND_EXCEEDED")


def observe_robinhood_baseline(
    read: ReadBoundary, *, observed_at: datetime
) -> RobinhoodReconciliationSnapshot:
    """One bounded observation sequence; failures stop, never retry or repair."""
    utc(observed_at)
    account = resolve_account(read.get_accounts())
    arguments = {"account_number": account.account_number}
    portfolio = parse_portfolio(read.get_portfolio(arguments))
    positions = tuple(
        sorted(
            (
                parse_position(p)
                for p in _pages(
                    read.get_equity_positions,
                    arguments,
                    "positions",
                    MAX_POSITION_PAGES,
                    MAX_POSITIONS,
                )
            ),
            key=lambda p: p.symbol,
        )
    )
    quote = parse_spy_quote(read.get_equity_quotes({"symbols": ["SPY"]}))
    since = observed_at - timedelta(days=ORDER_WINDOW_DAYS)
    orders = tuple(
        sorted(
            (
                parse_order(o)
                for o in _pages(
                    read.get_equity_orders,
                    {
                        **arguments,
                        "placed_agent": "agentic",
                        "created_at_gte": since.isoformat(),
                    },
                    "orders",
                    MAX_ORDER_PAGES,
                    MAX_ORDERS,
                )
            ),
            key=lambda o: (o.created_at, o.order_id),
        )
    )
    result = RobinhoodReconciliationSnapshot(
        observed_at,
        account.fingerprint,
        account.observed_account_count,
        account.eligible_account_count,
        portfolio,
        positions,
        quote,
        orders,
        since,
    )
    # Even a malformed provider echo in an otherwise valid symbol must not
    # disclose the resolved identifier in the evidence projection.
    if account.account_number in json.dumps(result.sanitized(), sort_keys=True):
        raise ObservationError("ACCOUNT_IDENTIFIER_ECHO_REJECTED")
    return result
