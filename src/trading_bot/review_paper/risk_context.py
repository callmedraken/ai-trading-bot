"""Derive paper-risk authority solely from durable virtual account history."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal

from trading_bot.domain import Symbol, TradeProposal
from trading_bot.domain._validation import normalize_utc
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.risk.models import RiskContext


def build_review_paper_risk_context(
    store: ReviewPaperStore,
    proposal: TradeProposal,
    prices: Mapping[Symbol, Decimal],
    *,
    as_of: datetime,
    new_trading_enabled: bool,
) -> RiskContext:
    """Mark the durable paper ledger using an explicit exact price snapshot."""
    if type(store) is not ReviewPaperStore:
        raise TypeError("store must be exactly a ReviewPaperStore")
    if type(proposal) is not TradeProposal:
        raise TypeError("proposal must be exactly a TradeProposal")
    if not isinstance(prices, Mapping):
        raise TypeError("prices must be a Mapping of Symbol to Decimal")
    if type(new_trading_enabled) is not bool:
        raise TypeError("new_trading_enabled must be exactly bool")
    as_of = normalize_utc(as_of, "as_of")
    if as_of < proposal.created_at:
        raise ValueError("as_of must not precede proposal created_at")
    for symbol, price in prices.items():
        if not isinstance(symbol, Symbol):
            raise TypeError("price keys must be Symbol values")
        if not isinstance(price, Decimal):
            raise TypeError("prices must be Decimal values")
        if not price.is_finite() or price <= Decimal("0"):
            raise ValueError("prices must be finite positive Decimal values")

    ledger = store.reconstruct_ledger()
    if set(prices) != set(ledger.positions) | {proposal.symbol}:
        raise ValueError(
            "prices must contain exactly open positions and proposal symbol"
        )
    account = ledger.create_account_snapshot(prices, as_of)
    return RiskContext(
        cash=account.cash,
        equity=account.equity,
        positions=ledger.positions,
        current_price=prices[proposal.symbol],
        total_market_exposure=account.positions_market_value,
        new_trading_enabled=new_trading_enabled,
        as_of=as_of,
    )
