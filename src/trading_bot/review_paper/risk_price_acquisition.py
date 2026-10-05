"""Bounded read-only Robinhood risk-price acquisition for review-paper mode."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from trading_bot.domain import TradeProposal
from trading_bot.review_paper.risk_prices import (
    ReviewPaperRiskPriceSnapshot,
    build_review_paper_risk_price_snapshot,
)
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter


def acquire_review_paper_risk_price_snapshot(
    *,
    store: ReviewPaperStore,
    proposal: TradeProposal,
    adapter: RobinhoodReviewReadAdapter,
    max_quote_age: timedelta,
) -> ReviewPaperRiskPriceSnapshot:
    """Discover symbols, read quotes once, observe UTC, and delegate to 131-N."""
    if type(store) is not ReviewPaperStore:
        raise TypeError("store must be exactly ReviewPaperStore")
    if type(proposal) is not TradeProposal:
        raise TypeError("proposal must be exactly TradeProposal")
    if type(adapter) is not RobinhoodReviewReadAdapter:
        raise TypeError("adapter must be exactly RobinhoodReviewReadAdapter")
    if type(max_quote_age) is not timedelta:
        raise TypeError("max_quote_age must be exactly timedelta")
    if max_quote_age <= timedelta(0):
        raise ValueError("max_quote_age must be strictly positive")

    ledger = store.reconstruct_ledger()
    required_symbols = tuple(sorted(set(ledger.positions) | {proposal.symbol}, key=str))
    if not required_symbols or len(required_symbols) > 20:
        raise ValueError("required_symbols must contain between 1 and 20 symbols")

    response = adapter.equity_quotes(required_symbols)
    observed_at = datetime.now(UTC)
    return build_review_paper_risk_price_snapshot(
        response=response,
        required_symbols=required_symbols,
        observed_at=observed_at,
        max_quote_age=max_quote_age,
    )
