"""SQLite-backed durable history for Robinhood review-based paper fills."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from trading_bot.domain import OrderFill, OrderSide, OrderType, Symbol, TimeInForce
from trading_bot.domain._validation import (
    require_decimal,
    require_positive_decimal,
)
from trading_bot.ledger import AccountSnapshot, PaperLedger
from trading_bot.review_paper.models import (
    ReviewPaperIntent,
    ReviewPaperRecord,
    RobinhoodEquityOrderReview,
    RobinhoodReviewQuote,
    review_paper_fill_id,
    review_paper_trade_id,
    synthetic_review_fill,
)
from trading_bot.risk import RiskOutcome

_SCHEMA_VERSION = "2"


class ReviewPaperStoreError(RuntimeError):
    """Base error for durable review-paper history."""


class ReviewPaperConflictError(ReviewPaperStoreError):
    """One local order ID was observed with conflicting review material."""


class UnsupportedReviewPaperOrderError(ReviewPaperStoreError):
    """The initial review-paper adapter does not support this order type."""


class ReviewPaperStore:
    """Durably retain review-derived fills and reconstruct the virtual account."""

    def __init__(self, path: str | Path, *, starting_cash: Decimal) -> None:
        self._path = Path(path)
        self._starting_cash = require_positive_decimal(starting_cash, "starting_cash")
        self._initialize()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def starting_cash(self) -> Decimal:
        return self._starting_cash

    def record_market_review(
        self,
        intent: ReviewPaperIntent,
        review: RobinhoodEquityOrderReview,
        *,
        slippage_basis_points: Decimal = Decimal("0"),
        commission: Decimal = Decimal("0"),
    ) -> ReviewPaperRecord:
        """Record one synthetic MARKET fill from one exact Robinhood review."""

        if not isinstance(intent, ReviewPaperIntent):
            raise TypeError("intent must be ReviewPaperIntent")
        if not isinstance(review, RobinhoodEquityOrderReview):
            raise TypeError("review must be RobinhoodEquityOrderReview")
        if intent.order_type is not OrderType.MARKET:
            raise UnsupportedReviewPaperOrderError(
                "Architecture 131 phase A2 supports MARKET orders only"
            )
        if review.order_type is not OrderType.MARKET:
            raise ReviewPaperConflictError("review order type differs from intent")
        if (
            review.symbol != intent.symbol
            or review.side is not intent.side
            or review.quantity != intent.approved_quantity
        ):
            raise ReviewPaperConflictError(
                "Robinhood review does not echo exact risk-approved order"
            )
        slippage = require_decimal(slippage_basis_points, "slippage_basis_points")
        commission_value = require_decimal(commission, "commission")
        if commission_value < Decimal("0"):
            raise ValueError("commission must be zero or greater")
        price, filled_at = synthetic_review_fill(
            intent.side,
            review.quote,
            slippage,
        )
        if filled_at < intent.proposed_at:
            raise ValueError("review quote timestamp cannot precede proposal")
        candidate = ReviewPaperRecord(
            paper_trade_id=review_paper_trade_id(intent.order_id),
            intent=intent,
            review=review,
            fill_id=review_paper_fill_id(intent.order_id),
            fill_price=price,
            commission=commission_value,
            slippage_basis_points=slippage,
            filled_at=filled_at,
        )

        existing = self.get_by_order_id(intent.order_id)
        if existing is not None:
            if _same_trade_material(existing, candidate):
                return existing
            raise ReviewPaperConflictError(
                f"order {intent.order_id} conflicts with durable paper history"
            )

        ledger = self.reconstruct_ledger()
        ledger.apply_fill(_record_fill(candidate))

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """
                    INSERT INTO review_fills (
                        paper_trade_id, proposal_id, order_id, symbol, side,
                        desired_quantity, approved_quantity, risk_outcome,
                        risk_reason_codes, proposal_reason, proposal_confidence,
                        order_type, time_in_force, proposed_at, limit_price,
                        reviewed_at, market_data_disclosure, order_checks_json,
                        adjusted_previous_close, ask_price, bid_price, has_traded,
                        last_non_reg_trade_price, last_trade_price, previous_close,
                        previous_close_date, quote_state, venue_ask_time,
                        venue_bid_time, venue_last_non_reg_trade_time,
                        venue_last_trade_time, fill_id, fill_price, commission,
                        slippage_basis_points, filled_at
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    _record_row(candidate),
                )
                connection.commit()
            except sqlite3.IntegrityError as error:
                connection.rollback()
                observed = self.get_by_order_id(intent.order_id)
                if observed is not None and _same_trade_material(observed, candidate):
                    return observed
                raise ReviewPaperConflictError(
                    f"order {intent.order_id} raced with conflicting history"
                ) from error
        return candidate

    def get_by_order_id(self, order_id: UUID) -> ReviewPaperRecord | None:
        if not isinstance(order_id, UUID):
            raise TypeError("order_id must be a UUID")
        with self._connect() as connection:
            row = connection.execute(
                _SELECT + " WHERE order_id = ?",
                (str(order_id),),
            ).fetchone()
        return None if row is None else _record_from_row(row)

    def history(self) -> tuple[ReviewPaperRecord, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                _SELECT + " ORDER BY filled_at, paper_trade_id"
            ).fetchall()
        return tuple(_record_from_row(row) for row in rows)

    def reconstruct_ledger(self) -> PaperLedger:
        ledger = PaperLedger(self._starting_cash)
        for record in self.history():
            ledger.apply_fill(_record_fill(record))
        return ledger

    def create_account_snapshot(
        self,
        prices: Mapping[Symbol, Decimal],
        *,
        timestamp: datetime,
    ) -> AccountSnapshot:
        return self.reconstruct_ledger().create_account_snapshot(prices, timestamp)

    def _initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS review_fills (
                        paper_trade_id TEXT PRIMARY KEY,
                        proposal_id TEXT NOT NULL,
                        order_id TEXT NOT NULL UNIQUE,
                        symbol TEXT NOT NULL,
                        side TEXT NOT NULL,
                        desired_quantity TEXT NOT NULL,
                        approved_quantity TEXT NOT NULL,
                        risk_outcome TEXT NOT NULL,
                        risk_reason_codes TEXT NOT NULL,
                        proposal_reason TEXT NOT NULL,
                        proposal_confidence TEXT,
                        order_type TEXT NOT NULL,
                        time_in_force TEXT NOT NULL,
                        proposed_at TEXT NOT NULL,
                        limit_price TEXT,
                        reviewed_at TEXT NOT NULL,
                        market_data_disclosure TEXT,
                        order_checks_json TEXT NOT NULL,
                        adjusted_previous_close TEXT NOT NULL,
                        ask_price TEXT NOT NULL,
                        bid_price TEXT NOT NULL,
                        has_traded INTEGER NOT NULL,
                        last_non_reg_trade_price TEXT,
                        last_trade_price TEXT NOT NULL,
                        previous_close TEXT NOT NULL,
                        previous_close_date TEXT,
                        quote_state TEXT NOT NULL,
                        venue_ask_time TEXT NOT NULL,
                        venue_bid_time TEXT NOT NULL,
                        venue_last_non_reg_trade_time TEXT,
                        venue_last_trade_time TEXT NOT NULL,
                        fill_id TEXT NOT NULL UNIQUE,
                        fill_price TEXT NOT NULL,
                        commission TEXT NOT NULL,
                        slippage_basis_points TEXT NOT NULL,
                        filled_at TEXT NOT NULL
                    )
                    """
                )
                metadata = dict(
                    connection.execute("SELECT key, value FROM metadata").fetchall()
                )
                if not metadata:
                    connection.executemany(
                        "INSERT INTO metadata(key, value) VALUES (?, ?)",
                        (
                            ("schema_version", _SCHEMA_VERSION),
                            ("starting_cash", str(self._starting_cash)),
                        ),
                    )
                else:
                    if metadata.get("schema_version") != _SCHEMA_VERSION:
                        raise ReviewPaperStoreError(
                            "review-paper schema version mismatch"
                        )
                    stored_cash = metadata.get("starting_cash")
                    if (
                        stored_cash is None
                        or Decimal(stored_cash) != self._starting_cash
                    ):
                        raise ReviewPaperStoreError(
                            "review-paper starting_cash mismatch"
                        )
                connection.commit()
            except BaseException:
                if connection.in_transaction:
                    connection.rollback()
                raise

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)


_SELECT = """
SELECT
    paper_trade_id, proposal_id, order_id, symbol, side,
    desired_quantity, approved_quantity, risk_outcome, risk_reason_codes,
    proposal_reason, proposal_confidence, order_type, time_in_force, proposed_at,
    limit_price, reviewed_at, market_data_disclosure, order_checks_json,
    adjusted_previous_close, ask_price, bid_price, has_traded,
    last_non_reg_trade_price, last_trade_price, previous_close,
    previous_close_date, quote_state, venue_ask_time, venue_bid_time,
    venue_last_non_reg_trade_time, venue_last_trade_time, fill_id, fill_price,
    commission, slippage_basis_points, filled_at
FROM review_fills
"""


def _record_fill(record: ReviewPaperRecord) -> OrderFill:
    return OrderFill(
        fill_id=record.fill_id,
        order_id=record.intent.order_id,
        symbol=record.intent.symbol,
        side=record.intent.side,
        quantity=record.intent.approved_quantity,
        price=record.fill_price,
        commission=record.commission,
        filled_at=record.filled_at,
    )


def _same_trade_material(
    existing: ReviewPaperRecord,
    candidate: ReviewPaperRecord,
) -> bool:
    return (
        existing.intent == candidate.intent
        and existing.review == candidate.review
        and existing.fill_id == candidate.fill_id
        and existing.fill_price == candidate.fill_price
        and existing.commission == candidate.commission
        and existing.slippage_basis_points == candidate.slippage_basis_points
        and existing.filled_at == candidate.filled_at
    )


def _record_row(record: ReviewPaperRecord) -> tuple[object, ...]:
    intent = record.intent
    review = record.review
    quote = review.quote
    return (
        str(record.paper_trade_id),
        str(intent.proposal_id),
        str(intent.order_id),
        str(intent.symbol),
        intent.side.value,
        str(intent.desired_quantity),
        str(intent.approved_quantity),
        intent.risk_outcome.value,
        "|".join(intent.risk_reason_codes),
        intent.proposal_reason,
        None
        if intent.proposal_confidence is None
        else str(intent.proposal_confidence),
        intent.order_type.value,
        intent.time_in_force.value,
        intent.proposed_at.isoformat(),
        None if intent.limit_price is None else str(intent.limit_price),
        review.reviewed_at.isoformat(),
        review.market_data_disclosure,
        review.order_checks_json,
        str(quote.adjusted_previous_close),
        str(quote.ask_price),
        str(quote.bid_price),
        1 if quote.has_traded else 0,
        None
        if quote.last_non_reg_trade_price is None
        else str(quote.last_non_reg_trade_price),
        str(quote.last_trade_price),
        str(quote.previous_close),
        quote.previous_close_date,
        quote.state,
        quote.venue_ask_time.isoformat(),
        quote.venue_bid_time.isoformat(),
        None
        if quote.venue_last_non_reg_trade_time is None
        else quote.venue_last_non_reg_trade_time.isoformat(),
        quote.venue_last_trade_time.isoformat(),
        str(record.fill_id),
        str(record.fill_price),
        str(record.commission),
        str(record.slippage_basis_points),
        record.filled_at.isoformat(),
    )


def _record_from_row(row: tuple[object, ...]) -> ReviewPaperRecord:
    (
        paper_trade_id,
        proposal_id,
        order_id,
        symbol,
        side,
        desired_quantity,
        approved_quantity,
        risk_outcome,
        risk_reason_codes,
        proposal_reason,
        proposal_confidence,
        order_type,
        time_in_force,
        proposed_at,
        limit_price,
        reviewed_at,
        market_data_disclosure,
        order_checks_json,
        adjusted_previous_close,
        ask_price,
        bid_price,
        has_traded,
        last_non_reg_trade_price,
        last_trade_price,
        previous_close,
        previous_close_date,
        quote_state,
        venue_ask_time,
        venue_bid_time,
        venue_last_non_reg_trade_time,
        venue_last_trade_time,
        fill_id,
        fill_price,
        commission,
        slippage_basis_points,
        filled_at,
    ) = row
    intent = ReviewPaperIntent(
        proposal_id=UUID(str(proposal_id)),
        order_id=UUID(str(order_id)),
        symbol=Symbol(str(symbol)),
        side=OrderSide(str(side)),
        desired_quantity=Decimal(str(desired_quantity)),
        approved_quantity=Decimal(str(approved_quantity)),
        risk_outcome=RiskOutcome(str(risk_outcome)),
        risk_reason_codes=tuple(
            item for item in str(risk_reason_codes).split("|") if item
        ),
        proposal_reason=str(proposal_reason),
        proposal_confidence=(
            None
            if proposal_confidence is None
            else Decimal(str(proposal_confidence))
        ),
        order_type=OrderType(str(order_type)),
        time_in_force=TimeInForce(str(time_in_force)),
        proposed_at=datetime.fromisoformat(str(proposed_at)),
        limit_price=None if limit_price is None else Decimal(str(limit_price)),
    )
    quote = RobinhoodReviewQuote(
        symbol=intent.symbol,
        adjusted_previous_close=Decimal(str(adjusted_previous_close)),
        ask_price=Decimal(str(ask_price)),
        bid_price=Decimal(str(bid_price)),
        has_traded=bool(has_traded),
        last_non_reg_trade_price=(
            None
            if last_non_reg_trade_price is None
            else Decimal(str(last_non_reg_trade_price))
        ),
        last_trade_price=Decimal(str(last_trade_price)),
        previous_close=Decimal(str(previous_close)),
        previous_close_date=(
            None if previous_close_date is None else str(previous_close_date)
        ),
        state=str(quote_state),
        venue_ask_time=datetime.fromisoformat(str(venue_ask_time)),
        venue_bid_time=datetime.fromisoformat(str(venue_bid_time)),
        venue_last_non_reg_trade_time=(
            None
            if venue_last_non_reg_trade_time is None
            else datetime.fromisoformat(str(venue_last_non_reg_trade_time))
        ),
        venue_last_trade_time=datetime.fromisoformat(str(venue_last_trade_time)),
    )
    review = RobinhoodEquityOrderReview(
        symbol=intent.symbol,
        side=intent.side,
        order_type=intent.order_type,
        quantity=intent.approved_quantity,
        quote=quote,
        order_checks_json=str(order_checks_json),
        reviewed_at=datetime.fromisoformat(str(reviewed_at)),
        market_data_disclosure=(
            None
            if market_data_disclosure is None
            else str(market_data_disclosure)
        ),
    )
    return ReviewPaperRecord(
        paper_trade_id=UUID(str(paper_trade_id)),
        intent=intent,
        review=review,
        fill_id=UUID(str(fill_id)),
        fill_price=Decimal(str(fill_price)),
        commission=Decimal(str(commission)),
        slippage_basis_points=Decimal(str(slippage_basis_points)),
        filled_at=datetime.fromisoformat(str(filled_at)),
    )
