"""Fail-closed Robinhood review-only forward paper-trading cycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from trading_bot.review_paper import (
    ReviewPaperConflictError,
    ReviewPaperIntent,
    ReviewPaperRecord,
    ReviewPaperStore,
)
from trading_bot.robinhood_mcp import (
    RobinhoodEquityOrder,
    RobinhoodEquityOrdersPage,
    RobinhoodReviewReadAdapter,
)

_MAX_ORDER_HISTORY_PAGES = 100


class RobinhoodPaperCycleSafetyError(RuntimeError):
    """Paper mode cannot prove that the review window stayed order-free."""


@dataclass(frozen=True, slots=True)
class RobinhoodPaperCycleResult:
    """Durable result of one review-only paper cycle."""

    record: ReviewPaperRecord
    reused_durable_record: bool
    baseline_order_pages: int
    post_review_order_pages: int

    def __post_init__(self) -> None:
        if not isinstance(self.record, ReviewPaperRecord):
            raise TypeError("record must be a ReviewPaperRecord")
        if not isinstance(self.reused_durable_record, bool):
            raise TypeError("reused_durable_record must be a bool")
        if self.baseline_order_pages < 0 or self.post_review_order_pages < 0:
            raise ValueError("order page counts cannot be negative")


class RobinhoodReviewPaperCycle:
    """Compose typed review/read calls with the durable virtual paper ledger."""

    def __init__(
        self,
        adapter: RobinhoodReviewReadAdapter,
        store: ReviewPaperStore,
        *,
        slippage_basis_points: Decimal = Decimal("0"),
        commission: Decimal = Decimal("0"),
    ) -> None:
        self._adapter = adapter
        self._store = store
        self._slippage_basis_points = slippage_basis_points
        self._commission = commission

    def run(
        self,
        *,
        account_number: str,
        intent: ReviewPaperIntent,
        review_received_at: datetime,
    ) -> RobinhoodPaperCycleResult:
        """Run one paper review only when the real-order window stays empty."""

        if not isinstance(intent, ReviewPaperIntent):
            raise TypeError("intent must be ReviewPaperIntent")

        existing = self._store.get_by_order_id(intent.order_id)
        if existing is not None:
            if existing.intent != intent:
                raise ReviewPaperConflictError(
                    f"order {intent.order_id} conflicts with durable paper history"
                )
            return RobinhoodPaperCycleResult(
                record=existing,
                reused_durable_record=True,
                baseline_order_pages=0,
                post_review_order_pages=0,
            )

        baseline, baseline_pages = _collect_agentic_orders(
            self._adapter,
            account_number=account_number,
            intent=intent,
        )
        _require_empty_order_window(baseline, stage="before_review")

        review = self._adapter.review_market_order(
            account_number=account_number,
            intent=intent,
            received_at=review_received_at,
        )

        post_review, post_review_pages = _collect_agentic_orders(
            self._adapter,
            account_number=account_number,
            intent=intent,
        )
        _require_empty_order_window(post_review, stage="after_review")

        record = self._store.record_market_review(
            intent,
            review,
            slippage_basis_points=self._slippage_basis_points,
            commission=self._commission,
        )
        return RobinhoodPaperCycleResult(
            record=record,
            reused_durable_record=False,
            baseline_order_pages=baseline_pages,
            post_review_order_pages=post_review_pages,
        )


def _collect_agentic_orders(
    adapter: RobinhoodReviewReadAdapter,
    *,
    account_number: str,
    intent: ReviewPaperIntent,
) -> tuple[dict[str, RobinhoodEquityOrder], int]:
    observed: dict[str, RobinhoodEquityOrder] = {}
    cursor: str | None = None
    seen_cursors: set[str] = set()
    pages = 0

    while True:
        page = adapter.agentic_equity_orders(
            account_number=account_number,
            created_at_gte=intent.proposed_at,
            cursor=cursor,
            symbol=intent.symbol,
        )
        if not isinstance(page, RobinhoodEquityOrdersPage):
            raise TypeError("agentic_equity_orders returned unexpected type")
        pages += 1
        if pages > _MAX_ORDER_HISTORY_PAGES:
            raise RobinhoodPaperCycleSafetyError(
                "agentic order history exceeded safety pagination limit"
            )

        for order in page.orders:
            if order is None:
                continue
            if order.placed_agent != "agentic":
                raise RobinhoodPaperCycleSafetyError(
                    "Robinhood returned a non-agentic order through agentic filter"
                )
            prior = observed.get(order.order_id)
            if prior is not None and prior != order:
                raise RobinhoodPaperCycleSafetyError(
                    "Robinhood repeated one order ID with conflicting material"
                )
            observed[order.order_id] = order

        next_cursor = page.next_cursor
        if not next_cursor:
            return observed, pages
        if next_cursor in seen_cursors:
            raise RobinhoodPaperCycleSafetyError(
                "Robinhood order pagination cursor repeated"
            )
        seen_cursors.add(next_cursor)
        cursor = next_cursor


def _require_empty_order_window(
    orders: dict[str, RobinhoodEquityOrder],
    *,
    stage: str,
) -> None:
    if orders:
        raise RobinhoodPaperCycleSafetyError(
            f"agentic real-order window is not empty {stage}; "
            f"observed_count={len(orders)}"
        )
