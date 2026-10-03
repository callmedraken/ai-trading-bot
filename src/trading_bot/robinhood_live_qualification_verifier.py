"""Read-only verification for the frozen Architecture 131-L live qualification."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from trading_bot.domain import OrderSide, Symbol
from trading_bot.risk import RiskOutcome, RiskReasonCode

_SCHEMA = "arch131-l-live-qualification/v1"
_STARTING_CASH = Decimal("100000")
_BEFORE_CASH = Decimal("99230.130000")
_SYMBOL = Symbol("SPY")
_PRIOR_QUANTITY = Decimal("1")
_DESIRED_QUANTITY = Decimal("2")
_APPROVED_QUANTITY = Decimal("1.000")
_FINAL_QUANTITY = Decimal("2.000")
_EXPECTED_REASONS = (
    RiskReasonCode.MAX_POSITION_PERCENT.value,
    RiskReasonCode.QUANTITY_INCREMENT.value,
)


class RobinhoodLiveQualificationVerificationError(RuntimeError):
    """Qualification evidence does not match the frozen accepted boundary."""


@dataclass(frozen=True, slots=True)
class Robinhood131LLiveQualificationVerification:
    source_head: str
    source_tree: str
    record_count: int
    cash: Decimal
    symbol: Symbol
    position_quantity: Decimal
    order_id: UUID
    fill_price: Decimal
    fill_time: datetime


def verify_robinhood_131l_live_qualification(
    *,
    store_path: Path,
    operator_evidence_path: Path,
    summary_path: Path,
    expected_source_head: str,
    expected_source_tree: str,
    expected_prior_order_id: UUID,
    expected_order_id: UUID,
) -> Robinhood131LLiveQualificationVerification:
    """Reconcile sanitized qualification evidence against the durable store."""
    for name, value in (
        ("store_path", store_path),
        ("operator_evidence_path", operator_evidence_path),
        ("summary_path", summary_path),
    ):
        if not isinstance(value, Path) or not value.is_absolute():
            raise TypeError(f"{name} must be an absolute Path")
    for name, value in (
        ("expected_source_head", expected_source_head),
        ("expected_source_tree", expected_source_tree),
    ):
        if not _is_git_sha(value):
            raise ValueError(f"{name} must be a lowercase 40-character Git SHA")
    if type(expected_prior_order_id) is not UUID or type(expected_order_id) is not UUID:
        raise TypeError("expected order IDs must be exact UUID values")
    if expected_prior_order_id == expected_order_id:
        raise ValueError("prior and qualification order IDs must differ")

    operator = _read_json_object(operator_evidence_path)
    summary = _read_json_object(summary_path)
    metadata, rows = _read_store(store_path)

    _require(
        metadata == {"schema_version": "2", "starting_cash": "100000"},
        "paper metadata mismatch",
    )
    _require(len(rows) == 2, "expected exactly two durable paper records")

    prior, qualified = rows
    _require(prior["order_id"] == str(expected_prior_order_id), "prior order mismatch")
    _require(qualified["order_id"] == str(expected_order_id), "new order mismatch")
    _require(prior["symbol"] == str(_SYMBOL), "prior symbol mismatch")
    _require(qualified["symbol"] == str(_SYMBOL), "new symbol mismatch")
    _require(prior["side"] == OrderSide.BUY.value, "prior side mismatch")
    _require(qualified["side"] == OrderSide.BUY.value, "new side mismatch")
    _require(
        Decimal(prior["approved_quantity"]) == _PRIOR_QUANTITY,
        "prior quantity mismatch",
    )
    _require(
        Decimal(qualified["desired_quantity"]) == _DESIRED_QUANTITY,
        "new desired quantity mismatch",
    )
    _require(
        Decimal(qualified["approved_quantity"]) == _APPROVED_QUANTITY,
        "new approved quantity mismatch",
    )
    _require(
        qualified["risk_outcome"] == RiskOutcome.RESIZED.value,
        "new risk outcome mismatch",
    )
    _require(
        tuple(item for item in qualified["risk_reason_codes"].split("|") if item)
        == _EXPECTED_REASONS,
        "new risk reasons mismatch",
    )

    cash, positions = _reconstruct(rows, _STARTING_CASH)
    _require(
        positions == {str(_SYMBOL): _FINAL_QUANTITY},
        "paper position mismatch",
    )

    expected_operator = {
        "source_head": expected_source_head,
        "source_tree": expected_source_tree,
        "status": "PASS",
        "phase": "complete",
        "symbol": str(_SYMBOL),
        "side": OrderSide.BUY.value,
        "quantity": format(_APPROVED_QUANTITY, "f"),
        "order_type": "MARKET",
        "get_accounts_calls": 1,
        "get_equity_orders_calls": 2,
        "review_equity_order_calls": 1,
        "get_equity_quotes_calls": 0,
        "baseline_order_pages": 1,
        "post_review_order_pages": 1,
        "paper_record_count": 2,
        "replay": False,
        "review_echo_validated": True,
        "quote_fill_validated": True,
        "disclosure_present": True,
        "interactive_reauth_count": 0,
    }
    _require(operator == expected_operator, "operator evidence mismatch")

    _require(summary.get("schema") == _SCHEMA, "summary schema mismatch")
    _require(summary.get("head") == expected_source_head, "summary head mismatch")
    _require(summary.get("tree") == expected_source_tree, "summary tree mismatch")
    _require(
        Path(str(summary.get("store"))).resolve() == store_path.resolve(),
        "summary store mismatch",
    )
    _require(
        summary.get("order_id") == str(expected_order_id), "summary order mismatch"
    )
    _require(summary.get("operator") == operator, "summary operator mismatch")

    before = summary.get("before")
    decision = summary.get("decision")
    after = summary.get("after")
    _require(type(before) is dict, "summary before section missing")
    _require(type(decision) is dict, "summary decision section missing")
    _require(type(after) is dict, "summary after section missing")

    _require(before.get("record_count") == 1, "summary prior record count mismatch")
    _require(
        Decimal(str(before.get("cash"))) == _BEFORE_CASH,
        "summary prior cash mismatch",
    )
    _require(
        Decimal(str(before.get("spy_quantity"))) == _PRIOR_QUANTITY,
        "summary prior position mismatch",
    )
    _require(
        Decimal(str(decision.get("desired_quantity"))) == _DESIRED_QUANTITY,
        "summary desired quantity mismatch",
    )
    _require(
        decision.get("outcome") == RiskOutcome.RESIZED.value,
        "summary risk outcome mismatch",
    )
    _require(
        Decimal(str(decision.get("approved_quantity"))) == _APPROVED_QUANTITY,
        "summary approved quantity mismatch",
    )
    _require(
        tuple(decision.get("reason_codes", ())) == _EXPECTED_REASONS,
        "summary risk reasons mismatch",
    )
    _require(after.get("record_count") == 2, "summary final record count mismatch")
    _require(Decimal(str(after.get("cash"))) == cash, "summary final cash mismatch")
    _require(
        Decimal(str(after.get("spy_quantity"))) == positions[str(_SYMBOL)],
        "summary final position mismatch",
    )
    _require(
        Decimal(str(after.get("new_fill_price"))) == Decimal(qualified["fill_price"]),
        "summary fill price mismatch",
    )
    _require(
        str(after.get("new_fill_time")) == qualified["filled_at"],
        "summary fill time mismatch",
    )
    _require(
        Path(str(summary.get("operator_evidence_file"))).resolve()
        == operator_evidence_path.resolve(),
        "summary operator evidence path mismatch",
    )

    return Robinhood131LLiveQualificationVerification(
        source_head=expected_source_head,
        source_tree=expected_source_tree,
        record_count=len(rows),
        cash=cash,
        symbol=_SYMBOL,
        position_quantity=positions[str(_SYMBOL)],
        order_id=expected_order_id,
        fill_price=Decimal(qualified["fill_price"]),
        fill_time=datetime.fromisoformat(qualified["filled_at"]),
    )


def _is_git_sha(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 40
        and value == value.lower()
        and all(character in "0123456789abcdef" for character in value)
    )


def _read_json_object(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RobinhoodLiveQualificationVerificationError(
            f"qualification JSON unavailable: {path.name}"
        ) from error
    if type(value) is not dict:
        raise RobinhoodLiveQualificationVerificationError(
            f"qualification JSON must be an object: {path.name}"
        )
    return value


def _read_store(path: Path) -> tuple[dict[str, str], tuple[dict[str, str], ...]]:
    try:
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        try:
            metadata = dict(
                connection.execute(
                    "SELECT key, value FROM metadata ORDER BY key"
                ).fetchall()
            )
            columns = (
                "order_id",
                "symbol",
                "side",
                "desired_quantity",
                "approved_quantity",
                "risk_outcome",
                "risk_reason_codes",
                "fill_price",
                "commission",
                "filled_at",
            )
            raw_rows = connection.execute(
                """
                SELECT
                    order_id, symbol, side, desired_quantity, approved_quantity,
                    risk_outcome, risk_reason_codes, fill_price, commission, filled_at
                FROM review_fills
                ORDER BY filled_at, paper_trade_id
                """
            ).fetchall()
        finally:
            connection.close()
    except (OSError, sqlite3.Error, ValueError) as error:
        raise RobinhoodLiveQualificationVerificationError(
            "durable paper store unavailable"
        ) from error
    rows = tuple(
        {column: str(value) for column, value in zip(columns, row, strict=True)}
        for row in raw_rows
    )
    return metadata, rows


def _reconstruct(
    rows: tuple[dict[str, str], ...],
    starting_cash: Decimal,
) -> tuple[Decimal, dict[str, Decimal]]:
    cash = starting_cash
    positions: dict[str, Decimal] = {}
    for row in rows:
        side = row["side"]
        symbol = row["symbol"]
        quantity = Decimal(row["approved_quantity"])
        price = Decimal(row["fill_price"])
        commission = Decimal(row["commission"])
        if side == OrderSide.BUY.value:
            cash -= quantity * price + commission
            positions[symbol] = positions.get(symbol, Decimal("0")) + quantity
        elif side == OrderSide.SELL.value:
            cash += quantity * price - commission
            positions[symbol] = positions.get(symbol, Decimal("0")) - quantity
        else:
            raise RobinhoodLiveQualificationVerificationError(
                f"unexpected durable order side: {side}"
            )
    return cash, {
        symbol: quantity for symbol, quantity in positions.items() if quantity != 0
    }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RobinhoodLiveQualificationVerificationError(message)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify one frozen Architecture 131-L live qualification"
    )
    parser.add_argument("--store", required=True, type=Path)
    parser.add_argument("--operator-evidence", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-tree", required=True)
    parser.add_argument("--prior-order-id", required=True, type=UUID)
    parser.add_argument("--order-id", required=True, type=UUID)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = verify_robinhood_131l_live_qualification(
        store_path=args.store.resolve(),
        operator_evidence_path=args.operator_evidence.resolve(),
        summary_path=args.summary.resolve(),
        expected_source_head=args.expected_head,
        expected_source_tree=args.expected_tree,
        expected_prior_order_id=args.prior_order_id,
        expected_order_id=args.order_id,
    )
    payload = {
        **asdict(result),
        "cash": str(result.cash),
        "symbol": str(result.symbol),
        "position_quantity": str(result.position_quantity),
        "order_id": str(result.order_id),
        "fill_price": str(result.fill_price),
        "fill_time": result.fill_time.isoformat(),
        "status": "PASS",
    }
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
