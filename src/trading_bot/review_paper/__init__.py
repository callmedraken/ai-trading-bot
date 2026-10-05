"""Robinhood review-based paper-trading domain and persistence."""

from importlib import import_module
from typing import TYPE_CHECKING

from trading_bot.review_paper.intent_bridge import build_review_paper_intent
from trading_bot.review_paper.models import (
    ReviewPaperIntent,
    ReviewPaperRecord,
    RobinhoodEquityOrderReview,
    RobinhoodReviewQuote,
    canonical_order_checks,
)
from trading_bot.review_paper.risk_context import build_review_paper_risk_context
from trading_bot.review_paper.store import (
    ReviewPaperConflictError,
    ReviewPaperStore,
    ReviewPaperStoreError,
    UnsupportedReviewPaperOrderError,
)

__all__ = [
    "ReviewPaperConflictError",
    "ReviewPaperMark",
    "ReviewPaperPerformanceError",
    "ReviewPaperPerformanceHistoryEmptyError",
    "ReviewPaperPerformanceReport",
    "ReviewPaperPerformanceStore",
    "ReviewPaperQuoteError",
    "ReviewPaperRealization",
    "ReviewPaperIntent",
    "ReviewPaperRecord",
    "ReviewPaperStore",
    "ReviewPaperStoreError",
    "ReviewPaperValuation",
    "ReviewPaperValuationConflictError",
    "RobinhoodEquityOrderReview",
    "RobinhoodReviewQuote",
    "UnsupportedReviewPaperOrderError",
    "build_review_paper_intent",
    "build_review_paper_risk_context",
    "canonical_order_checks",
]


# Session/evidence imports must not eagerly load the performance provider boundary.
if TYPE_CHECKING:
    from trading_bot.review_paper.performance import (
        ReviewPaperMark,
        ReviewPaperPerformanceError,
        ReviewPaperPerformanceHistoryEmptyError,
        ReviewPaperPerformanceReport,
        ReviewPaperPerformanceStore,
        ReviewPaperQuoteError,
        ReviewPaperRealization,
        ReviewPaperValuation,
        ReviewPaperValuationConflictError,
    )

_PERFORMANCE_EXPORTS = frozenset(
    (
        "ReviewPaperMark",
        "ReviewPaperPerformanceError",
        "ReviewPaperPerformanceHistoryEmptyError",
        "ReviewPaperPerformanceReport",
        "ReviewPaperPerformanceStore",
        "ReviewPaperQuoteError",
        "ReviewPaperRealization",
        "ReviewPaperValuation",
        "ReviewPaperValuationConflictError",
    )
)


def __getattr__(name: str) -> object:
    if name in _PERFORMANCE_EXPORTS:
        return getattr(import_module("trading_bot.review_paper.performance"), name)
    raise AttributeError(name)
