"""SQLite-backed durable history for manual-approval paper fills."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from trading_bot.approval_paper.models import (
    ApprovalDeclineState,
    ApprovalPaperIntent,
    ApprovalPaperQuote,
    ApprovalPaperRecord,
    approval_paper_fill_id,
    approval_paper_record_id,
    synthetic_market_fill_price,
)
from trading_bot.domain import OrderFill, OrderSide, OrderType, Symbol, TimeInForce
from trading_bot.domain._validation import (
    normalize_utc,
    require_decimal,
    require_positive_decimal,
)
from trading_bot.ledger import AccountSnapshot, PaperLedger
from trading_bot.risk import RiskOutcome

_SCHEMA_VERSION = "1"


class ApprovalPaperStoreError(RuntimeError):
    """Base error for durable approval-paper history."""


class ApprovalPaperConflictError(ApprovalPaperStoreError):
    """One Robinhood approval ID was observed with conflicting material."""


class UnsupportedApprovalPaperOrderError(ApprovalPaperStoreError):
    """The initial approval-paper adapter does not support this order type."""


class ApprovalPaperStore:
    """Durably retain synthetic fills and reconstruct the virtual paper account."""

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

    def record_market_approval(
        self,
        intent: ApprovalPaperIntent,
        quote: ApprovalPaperQuote,
        *,
        slippage_basis_points: Decimal = Decimal("0"),
        commission: Decimal = Decimal("0"),
    ) -> ApprovalPaperRecord:
        """Record one synthetic market fill before external approval decline."""

        if not isinstance(intent, ApprovalPaperIntent):
            raise TypeError("intent must be ApprovalPaperIntent")
        if not isinstance(quote, ApprovalPaperQuote):
            raise TypeError("quote must be ApprovalPaperQuote")
        if intent.order_type is not OrderType.MARKET:
            raise UnsupportedApprovalPaperOrderError(
                "Architecture 131 phase A supports MARKET approvals only"
            )
        if quote.symbol != intent.symbol:
            raise ValueError("quote symbol must match intent")
        if quote.observed_at < intent.proposed_at:
            raise ValueError("quote cannot precede Robinhood approval proposal")
        slippage = require_decimal(slippage_basis_points, "slippage_basis_points")
        commission_value = require_decimal(commission, "commission")
        if commission_value < Decimal("0"):
            raise ValueError("commission must be zero or greater")
        price = synthetic_market_fill_price(intent.side, quote, slippage)
        candidate = ApprovalPaperRecord(
            record_id=approval_paper_record_id(intent.approval_id),
            intent=intent,
            quote=quote,
            fill_id=approval_paper_fill_id(intent.approval_id),
            fill_price=price,
            commission=commission_value,
            slippage_basis_points=slippage,
            filled_at=quote.observed_at,
            decline_state=ApprovalDeclineState.PENDING_DECLINE,
        )

        existing = self.get(intent.approval_id)
        if existing is not None:
            if _same_trade_material(existing, candidate):
                return existing
            raise ApprovalPaperConflictError(
                f"approval {intent.approval_id} conflicts with durable paper history"
            )

        ledger = self.reconstruct_ledger()
        ledger.apply_fill(_record_fill(candidate))

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT approval_id FROM approval_fills WHERE approval_id = ?",
                    (intent.approval_id,),
                ).fetchone()
                if row is not None:
                    connection.rollback()
                    observed = self.get(intent.approval_id)
                    if observed is not None and _same_trade_material(
                        observed, candidate
                    ):
                        return observed
                    raise ApprovalPaperConflictError(
                        f"approval {intent.approval_id} raced with conflicting history"
                    )
                connection.execute(
                    """
                    INSERT INTO approval_fills (
                        approval_id, record_id, proposal_id, order_id, symbol, side,
                        desired_quantity, approved_quantity, risk_outcome,
                        risk_reason_codes_json, proposal_reason, proposal_confidence,
                        order_type, time_in_force, proposed_at, limit_price,
                        quote_bid, quote_ask, quote_observed_at,
                        fill_id, fill_price, commission, slippage_basis_points,
                        filled_at, decline_state, declined_at
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    _record_row(candidate),
                )
                connection.commit()
            except BaseException:
                if connection.in_transaction:
                    connection.rollback()
                raise
        return candidate

    def mark_declined(
        self,
        approval_id: str,
        *,
        declined_at: datetime,
    ) -> ApprovalPaperRecord:
        """Record externally verified decline confirmation exactly once."""

        existing = self.get(approval_id)
        if existing is None:
            raise ApprovalPaperStoreError(f"approval {approval_id} is not recorded")
        if existing.decline_state is ApprovalDeclineState.DECLINED:
            return existing
        normalized = normalize_utc(declined_at, "declined_at")
        if normalized < existing.filled_at:
            raise ValueError("declined_at cannot precede synthetic fill")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                result = connection.execute(
                    """
                    UPDATE approval_fills
                    SET decline_state = ?, declined_at = ?
                    WHERE approval_id = ? AND decline_state = ?
                    """,
                    (
                        ApprovalDeclineState.DECLINED.value,
                        normalized.isoformat(),
                        approval_id,
                        ApprovalDeclineState.PENDING_DECLINE.value,
                    ),
                )
                connection.commit()
            except BaseException:
                if connection.in_transaction:
                    connection.rollback()
                raise
        if result.rowcount not in {0, 1}:
            raise ApprovalPaperStoreError("unexpected decline update cardinality")
        observed = self.get(approval_id)
        if observed is None:
            raise ApprovalPaperStoreError("decline update lost durable paper record")
        if observed.decline_state is not ApprovalDeclineState.DECLINED:
            raise ApprovalPaperStoreError("decline confirmation was not persisted")
        return observed

    def get(self, approval_id: str) -> ApprovalPaperRecord | None:
        if not isinstance(approval_id, str) or not approval_id:
            raise ValueError("approval_id must be nonblank")
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    approval_id, record_id, proposal_id, order_id, symbol, side,
                    desired_quantity, approved_quantity, risk_outcome,
                    risk_reason_codes_json, proposal_reason, proposal_confidence,
                    order_type, time_in_force, proposed_at, limit_price,
                    quote_bid, quote_ask, quote_observed_at,
                    fill_id, fill_price, commission, slippage_basis_points,
                    filled_at, decline_state, declined_at
                FROM approval_fills
                WHERE approval_id = ?
                """,
                (approval_id,),
            ).fetchone()
        return None if row is None else _record_from_row(row)

    def history(self) -> tuple[ApprovalPaperRecord, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    approval_id, record_id, proposal_id, order_id, symbol, side,
                    desired_quantity, approved_quantity, risk_outcome,
                    risk_reason_codes_json, proposal_reason, proposal_confidence,
                    order_type, time_in_force, proposed_at, limit_price,
                    quote_bid, quote_ask, quote_observed_at,
                    fill_id, fill_price, commission, slippage_basis_points,
                    filled_at, decline_state, declined_at
                FROM approval_fills
                ORDER BY filled_at, approval_id
                """
            ).fetchall()
        return tuple(_record_from_row(row) for row in rows)

    def pending_declines(self) -> tuple[ApprovalPaperRecord, ...]:
        return tuple(
            record
            for record in self.history()
            if record.decline_state is ApprovalDeclineState.PENDING_DECLINE
        )

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
                    CREATE TABLE IF NOT EXISTS approval_fills (
                        approval_id TEXT PRIMARY KEY,
                        record_id TEXT NOT NULL UNIQUE,
                        proposal_id TEXT NOT NULL,
                        order_id TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        side TEXT NOT NULL,
                        desired_quantity TEXT NOT NULL,
                        approved_quantity TEXT NOT NULL,
                        risk_outcome TEXT NOT NULL,
                        risk_reason_codes_json TEXT NOT NULL,
                        proposal_reason TEXT NOT NULL,
                        proposal_confidence TEXT,
                        order_type TEXT NOT NULL,
                        time_in_force TEXT NOT NULL,
                        proposed_at TEXT NOT NULL,
                        limit_price TEXT,
                        quote_bid TEXT NOT NULL,
                        quote_ask TEXT NOT NULL,
                        quote_observed_at TEXT NOT NULL,
                        fill_id TEXT NOT NULL UNIQUE,
                        fill_price TEXT NOT NULL,
                        commission TEXT NOT NULL,
                        slippage_basis_points TEXT NOT NULL,
                        filled_at TEXT NOT NULL,
                        decline_state TEXT NOT NULL,
                        declined_at TEXT
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
                        raise ApprovalPaperStoreError(
                            "approval-paper schema version mismatch"
                        )
                    stored_cash = metadata.get("starting_cash")
                    if (
                        stored_cash is None
                        or Decimal(stored_cash) != self._starting_cash
                    ):
                        raise ApprovalPaperStoreError(
                            "approval-paper starting_cash mismatch"
                        )
                connection.commit()
            except BaseException:
                if connection.in_transaction:
                    connection.rollback()
                raise

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _record_fill(record: ApprovalPaperRecord) -> OrderFill:
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
    existing: ApprovalPaperRecord,
    candidate: ApprovalPaperRecord,
) -> bool:
    return (
        existing.intent == candidate.intent
        and existing.quote == candidate.quote
        and existing.fill_id == candidate.fill_id
        and existing.fill_price == candidate.fill_price
        and existing.commission == candidate.commission
        and existing.slippage_basis_points == candidate.slippage_basis_points
        and existing.filled_at == candidate.filled_at
    )


def _record_row(record: ApprovalPaperRecord) -> tuple[object, ...]:
    confidence = record.intent.proposal_confidence
    limit_price = record.intent.limit_price
    declined = record.declined_at
    return (
        record.intent.approval_id,
        str(record.record_id),
        str(record.intent.proposal_id),
        str(record.intent.order_id),
        str(record.intent.symbol),
        record.intent.side.value,
        str(record.intent.desired_quantity),
        str(record.intent.approved_quantity),
        record.intent.risk_outcome.value,
        json.dumps(record.intent.risk_reason_codes, separators=(",", ":")),
        record.intent.proposal_reason,
        None if confidence is None else str(confidence),
        record.intent.order_type.value,
        record.intent.time_in_force.value,
        record.intent.proposed_at.isoformat(),
        None if limit_price is None else str(limit_price),
        str(record.quote.bid),
        str(record.quote.ask),
        record.quote.observed_at.isoformat(),
        str(record.fill_id),
        str(record.fill_price),
        str(record.commission),
        str(record.slippage_basis_points),
        record.filled_at.isoformat(),
        record.decline_state.value,
        None if declined is None else declined.isoformat(),
    )


def _record_from_row(row: tuple[object, ...]) -> ApprovalPaperRecord:
    (
        approval_id,
        record_id,
        proposal_id,
        order_id,
        symbol,
        side,
        desired_quantity,
        approved_quantity,
        risk_outcome,
        risk_reason_codes_json,
        proposal_reason,
        proposal_confidence,
        order_type,
        time_in_force,
        proposed_at,
        limit_price,
        quote_bid,
        quote_ask,
        quote_observed_at,
        fill_id,
        fill_price,
        commission,
        slippage_basis_points,
        filled_at,
        decline_state,
        declined_at,
    ) = row
    reason_codes = json.loads(str(risk_reason_codes_json))
    if not isinstance(reason_codes, list) or not all(
        isinstance(item, str) for item in reason_codes
    ):
        raise ApprovalPaperStoreError("stored risk_reason_codes are invalid")
    intent = ApprovalPaperIntent(
        approval_id=str(approval_id),
        proposal_id=UUID(str(proposal_id)),
        order_id=UUID(str(order_id)),
        symbol=Symbol(str(symbol)),
        side=OrderSide(str(side)),
        desired_quantity=Decimal(str(desired_quantity)),
        approved_quantity=Decimal(str(approved_quantity)),
        risk_outcome=RiskOutcome(str(risk_outcome)),
        risk_reason_codes=tuple(reason_codes),
        proposal_reason=str(proposal_reason),
        proposal_confidence=(
            None if proposal_confidence is None else Decimal(str(proposal_confidence))
        ),
        order_type=OrderType(str(order_type)),
        time_in_force=TimeInForce(str(time_in_force)),
        proposed_at=datetime.fromisoformat(str(proposed_at)),
        limit_price=None if limit_price is None else Decimal(str(limit_price)),
    )
    quote = ApprovalPaperQuote(
        symbol=intent.symbol,
        bid=Decimal(str(quote_bid)),
        ask=Decimal(str(quote_ask)),
        observed_at=datetime.fromisoformat(str(quote_observed_at)),
    )
    return ApprovalPaperRecord(
        record_id=UUID(str(record_id)),
        intent=intent,
        quote=quote,
        fill_id=UUID(str(fill_id)),
        fill_price=Decimal(str(fill_price)),
        commission=Decimal(str(commission)),
        slippage_basis_points=Decimal(str(slippage_basis_points)),
        filled_at=datetime.fromisoformat(str(filled_at)),
        decline_state=ApprovalDeclineState(str(decline_state)),
        declined_at=(
            None if declined_at is None else datetime.fromisoformat(str(declined_at))
        ),
    )
