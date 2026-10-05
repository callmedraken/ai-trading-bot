"""Provider-free reconciliation of the one-shot 131-V EXECUTE qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from decimal import Context, Decimal, localcontext
from pathlib import Path
from uuid import UUID, uuid5

from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)

SCHEMA = "arch131-q-execute-qualification/v1"
PROPOSAL_ID = UUID("11111111-131c-4000-8000-000000000002")
ORDER_ID = UUID("22222222-131c-4000-8000-000000000001")
BRANCH = "feature/robinhood-review-paper-side-foundation"
RISK_FIELDS = {
    "requested_quantity",
    "risk_outcome",
    "approved_quantity",
    "reason_codes",
    "cash",
    "equity",
    "current_price",
    "total_market_exposure",
    "current_position_quantity",
    "current_position_market_value",
    "projected_position_quantity",
    "projected_position_market_value",
    "projected_total_market_exposure",
}
ADMISSION_FIELDS = {
    "status",
    "as_of",
    "session_date",
    "opens_at",
    "closes_at",
    "admission_opens_at",
    "admission_closes_at",
}
CONFIG_FIELDS = {
    "branch",
    "head",
    "tree",
    "store_path",
    "operator_evidence_path",
    "order_type",
    "time_in_force",
    "slippage_basis_points",
    "commission",
    "redirect_uri_sha256",
    "risk_limits",
    "opening_buffer_seconds",
    "closing_buffer_seconds",
    "max_quote_age_seconds",
    "new_trading_enabled",
}
EVIDENCE_FIELDS = {
    "schema",
    "source_head",
    "source_tree",
    "proposal_id",
    "order_id",
    "prepare_evidence_path",
    "prepare_evidence_sha256",
    "authorization_challenge",
    "authorization_accepted",
    "authorization_accepted_at",
    "instruction_created_at",
    "quote_observed_at",
    "quote_valid_until",
    "execution_configuration",
    "execute_admission",
    "prepared_risk",
    "revalidated_risk",
    "durable_before",
    "durable_after",
    "operator_evidence_path",
    "operator_evidence_sha256",
    "operator_evidence",
    "placement_calls",
    "cancellation_calls",
    "options_mutation_calls",
    "crypto_mutation_calls",
    "interactive_reauth_count",
    "prepare_calls",
    "prepare_verifier_calls",
    "stdin_reads",
    "execute_calls",
    "execute_invoked",
    "forward_cycle_invoked",
    "retry_count",
    "status",
}
OPERATOR_FIELDS = {
    "source_head",
    "source_tree",
    "status",
    "phase",
    "symbol",
    "side",
    "quantity",
    "order_type",
    "get_accounts_calls",
    "get_equity_orders_calls",
    "review_equity_order_calls",
    "get_equity_quotes_calls",
    "baseline_order_pages",
    "post_review_order_pages",
    "paper_record_count",
    "replay",
    "review_echo_validated",
    "quote_fill_validated",
    "disclosure_present",
    "interactive_reauth_count",
    "placement_calls",
    "cancellation_calls",
    "options_mutation_calls",
    "crypto_mutation_calls",
}


class ExecuteQualificationVerificationError(RuntimeError):
    """Closed qualification evidence cannot be independently reconciled."""


def require_qualification(condition: bool) -> None:
    if not condition:
        raise ExecuteQualificationVerificationError(
            "qualification reconciliation failed"
        )


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def _exact(left: object, right: object) -> bool:
    return _canonical(left) == _canonical(right)


def _object(value: object, fields: set[str]) -> dict:
    require_qualification(type(value) is dict and set(value) == fields)
    return value


def _unique(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        require_qualification(key not in result)
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ExecuteQualificationVerificationError("invalid evidence JSON")


def read_qualification_json(path: Path) -> dict:
    """Read duplicate-free JSON; never access a provider or write a file."""
    result = json.loads(
        path.read_bytes(), object_pairs_hook=_unique, parse_constant=_constant
    )
    require_qualification(type(result) is dict)
    return result


def _time(value: object) -> datetime:
    require_qualification(type(value) is str)
    at = datetime.fromisoformat(value)
    require_qualification(
        at.tzinfo is not None
        and at.utcoffset() == timedelta(0)
        and at.isoformat() == value
    )
    return at.astimezone(UTC)


def _number(value: object) -> Decimal:
    require_qualification(type(value) is str)
    number = Decimal(value)
    require_qualification(number.is_finite())
    return number


def _sha(value: object, size: int = 64) -> None:
    require_qualification(
        type(value) is str and re.fullmatch(f"[0-9a-f]{{{size}}}", value) is not None
    )


def qualification_fingerprint(metadata: list, columns: list, rows: list) -> dict:
    """Canonical full-column SQLite fingerprint compatible with accepted 131-R."""
    material = {
        "metadata": metadata,
        "columns": columns,
        "rows": rows,
        "record_count": len(rows),
    }
    return {
        "metadata": metadata,
        "record_count": len(rows),
        "sha256": hashlib.sha256(_canonical(material)).hexdigest(),
    }


def read_qualification_store(path: Path) -> tuple[list, list, list]:
    """Open an existing database in URI read-only mode; return one stable snapshot."""
    require_qualification(path.is_absolute() and path.is_file())
    with closing(
        sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    ) as connection:
        connection.execute("BEGIN")
        metadata = [
            list(row)
            for row in connection.execute(
                "SELECT key, value FROM metadata ORDER BY key"
            )
        ]
        cursor = connection.execute(
            "SELECT * FROM review_fills ORDER BY filled_at, paper_trade_id"
        )
        columns = [column[0] for column in cursor.description]
        rows = [list(row) for row in cursor.fetchall()]
    return metadata, columns, rows


def validate_qualification_before(
    metadata: list, columns: list, rows: list, expected_sha256: str
) -> dict:
    """Require the caller-pinned two-record SPY state before provider access."""
    _sha(expected_sha256)
    require_qualification(
        metadata == [["schema_version", "2"], ["starting_cash", "100000"]]
        and len(rows) == 2
        and len(set(columns)) == len(columns)
    )
    require_qualification(
        qualification_fingerprint(metadata, columns, rows)["sha256"] == expected_sha256
    )
    records = [dict(zip(columns, row, strict=True)) for row in rows]
    # Pin historical bytes, then independently check the accepted balance.
    with localcontext(Context(prec=80)):
        cash = Decimal("100000")
        quantity = Decimal(0)
        for record in records:
            require_qualification(
                record["symbol"] == "SPY"
                and record["side"] == "BUY"
                and record["order_id"] != str(ORDER_ID)
                and record["proposal_id"] != str(PROPOSAL_ID)
            )
            q = _number(record["approved_quantity"])
            cash -= q * _number(record["fill_price"]) + _number(record["commission"])
            quantity += q
        require_qualification(
            cash == Decimal("98457.100000000") and quantity == Decimal("2.000")
        )
    return qualification_fingerprint(metadata, columns, rows)


def _admission(value: object, schedule: dict) -> datetime:
    value = _object(value, ADMISSION_FIELDS)
    at = _time(value["as_of"])
    require_qualification(
        value["status"] == "ADMITTED"
        and value["session_date"] == schedule["session_date"]
    )
    for field in ("opens_at", "closes_at"):
        require_qualification(value[field] == schedule[field])
    opening = _time(schedule["opens_at"]) + timedelta(minutes=5)
    closing = _time(schedule["closes_at"]) - timedelta(minutes=5)
    require_qualification(
        _time(value["admission_opens_at"]) == opening
        and _time(value["admission_closes_at"]) == closing
        and opening <= at < closing
    )
    return at


def _risk(value: object) -> dict:
    value = _object(value, RISK_FIELDS)
    require_qualification(
        value["risk_outcome"] == "APPROVED" and value["reason_codes"] == []
    )
    for field in RISK_FIELDS - {"risk_outcome", "reason_codes"}:
        _number(value[field])
    require_qualification(
        _number(value["requested_quantity"]) == Decimal("1.000")
        and _number(value["approved_quantity"]) == Decimal("1.000")
    )
    return value


def _configuration(
    value: object, head: str, tree: str, store: Path, operator: Path
) -> dict:
    config = _object(value, CONFIG_FIELDS)
    require_qualification(
        config["branch"] == BRANCH
        and config["head"] == head
        and config["tree"] == tree
        and config["store_path"] == str(store.resolve())
        and config["operator_evidence_path"] == str(operator.resolve())
        and config["order_type"] == "MARKET"
        and config["time_in_force"] == "DAY"
        and config["slippage_basis_points"] == "0"
        and config["commission"] == "0"
        and config["new_trading_enabled"] is True
    )
    for field in (
        "opening_buffer_seconds",
        "closing_buffer_seconds",
        "max_quote_age_seconds",
    ):
        require_qualification(type(config[field]) is int and config[field] == 300)
    require_qualification(
        config["redirect_uri_sha256"]
        == hashlib.sha256(b"http://127.0.0.1:8765/callback").hexdigest()
    )
    limits = _object(
        config["risk_limits"],
        {
            "max_position_percent",
            "max_total_exposure_percent",
            "max_order_notional",
            "max_new_position_percent",
            "minimum_cash_reserve_percent",
            "allow_fractional_shares",
            "fractional_increment",
            "allow_buying",
            "allow_selling",
            "estimated_commission",
        },
    )
    require_qualification(
        _exact(
            limits,
            {
                "max_position_percent": "0.20",
                "max_total_exposure_percent": "0.80",
                "max_order_notional": None,
                "max_new_position_percent": None,
                "minimum_cash_reserve_percent": "0.10",
                "allow_fractional_shares": True,
                "fractional_increment": "0.001",
                "allow_buying": True,
                "allow_selling": True,
                "estimated_commission": "0",
            },
        )
    )
    return config


def _verify(
    *,
    store_path: Path,
    evidence_path: Path,
    prepare_evidence_path: Path,
    operator_evidence_path: Path,
    expected_source_head: str,
    expected_source_tree: str,
    expected_before_sha256: str,
) -> dict:
    head, tree = expected_source_head, expected_source_tree
    _sha(head, 40)
    _sha(tree, 40)
    paths = (store_path, evidence_path, prepare_evidence_path, operator_evidence_path)
    require_qualification(
        all(path.is_absolute() for path in paths)
        and len({path.resolve() for path in paths}) == 4
    )
    evidence = _object(read_qualification_json(evidence_path), EVIDENCE_FIELDS)
    prepare = _object(
        read_qualification_json(prepare_evidence_path),
        {
            "schema",
            "source_head",
            "source_tree",
            "store_path",
            "starting_cash",
            "proposal",
            "schedule",
            "opening_buffer_seconds",
            "closing_buffer_seconds",
            "max_quote_age_seconds",
            "new_trading_enabled",
            "durable_before",
            "preparation",
            "durable_after",
            "execute_invoked",
            "pipeline_result_present",
        },
    )
    require_qualification(
        evidence["schema"] == SCHEMA
        and prepare["schema"] == "arch131-q-prepare-qualification/v1"
    )
    for payload in (evidence, prepare):
        require_qualification(
            payload["source_head"] == head and payload["source_tree"] == tree
        )
    require_qualification(
        prepare["store_path"] == str(store_path.resolve())
        and prepare["starting_cash"] == "100000"
        and prepare["new_trading_enabled"] is True
        and prepare["execute_invoked"] is False
        and prepare["pipeline_result_present"] is False
    )
    for field in (
        "opening_buffer_seconds",
        "closing_buffer_seconds",
        "max_quote_age_seconds",
    ):
        require_qualification(
            type(prepare[field]) in (int, float) and prepare[field] == 300
        )
    proposal = _object(
        prepare["proposal"],
        {"proposal_id", "symbol", "side", "desired_quantity", "created_at"},
    )
    require_qualification(
        proposal["proposal_id"] == evidence["proposal_id"] == str(PROPOSAL_ID)
        and evidence["order_id"] == str(ORDER_ID)
        and proposal["symbol"] == "SPY"
        and proposal["side"] == "SELL"
        and _number(proposal["desired_quantity"]) == Decimal("1.000")
    )
    proposed_at = _time(proposal["created_at"])
    schedule = _object(prepare["schedule"], {"session_date", "opens_at", "closes_at"})
    session = NYSEPublishedRegularSessionAuthority().schedule_for(
        datetime.fromisoformat(schedule["session_date"]).date()
    )
    require_qualification(
        session is not None
        and schedule
        == {
            "session_date": session.session_date.isoformat(),
            "opens_at": session.opens_at.isoformat(),
            "closes_at": session.closes_at.isoformat(),
        }
    )
    prepared = _object(
        prepare["preparation"],
        {
            "status",
            "initial_admission",
            "price_snapshot",
            "quote_admission",
            "risk_preview",
            "quote_valid_until",
        },
    )
    require_qualification(prepared["status"] == "READY_TO_PROCEED")
    initial = _admission(prepared["initial_admission"], schedule)
    observed = _admission(prepared["quote_admission"], schedule)
    snapshot = _object(prepared["price_snapshot"], {"observed_at", "marks"})
    require_qualification(
        snapshot["observed_at"] == evidence["quote_observed_at"] == observed.isoformat()
    )
    require_qualification(
        type(snapshot["marks"]) is list and len(snapshot["marks"]) == 1
    )
    mark = _object(snapshot["marks"][0], {"symbol", "price", "source_at"})
    require_qualification(mark["symbol"] == "SPY" and _number(mark["price"]) > 0)
    source = _time(mark["source_at"])
    deadline = _time(prepared["quote_valid_until"])
    require_qualification(
        source <= observed <= deadline == source + timedelta(minutes=5)
        and evidence["quote_valid_until"] == deadline.isoformat()
        and proposed_at <= initial <= observed
    )
    risk = _risk(prepared["risk_preview"])
    require_qualification(
        _exact(risk, _risk(evidence["prepared_risk"]))
        and _exact(risk, _risk(evidence["revalidated_risk"]))
        and _number(risk["cash"]) == Decimal("98457.100000000")
        and _number(risk["current_position_quantity"]) == Decimal("2.000")
        and _number(risk["current_price"]) == _number(mark["price"])
    )
    with localcontext(Context(prec=80)):
        price = _number(mark["price"])
        require_qualification(
            _number(risk["total_market_exposure"]) == price * 2
            and _number(risk["equity"]) == _number(risk["cash"]) + price * 2
            and _number(risk["current_position_market_value"]) == price * 2
            and _number(risk["projected_position_quantity"]) == 1
            and _number(risk["projected_position_market_value"]) == price
            and _number(risk["projected_total_market_exposure"]) == price
        )
    config = _configuration(
        evidence["execution_configuration"],
        head,
        tree,
        store_path,
        operator_evidence_path,
    )
    digest = hashlib.sha256(prepare_evidence_path.read_bytes()).hexdigest()
    require_qualification(
        evidence["prepare_evidence_path"] == str(prepare_evidence_path.resolve())
        and evidence["prepare_evidence_sha256"] == digest
    )
    # Independently construct challenge material; import no composition/gate helpers.
    material = {
        "schema": SCHEMA,
        "source_head": head,
        "source_tree": tree,
        "proposal_id": str(PROPOSAL_ID),
        "order_id": str(ORDER_ID),
        "prepare_evidence_sha256": digest,
        "prepare_evidence_path": str(prepare_evidence_path.resolve()),
        "quote_observed_at": observed.isoformat(),
        "quote_valid_until": deadline.isoformat(),
        "risk_outcome": risk["risk_outcome"],
        "approved_quantity": risk["approved_quantity"],
        "execution_configuration": config,
    }
    challenge = hashlib.sha256(_canonical(material)).hexdigest()
    require_qualification(
        evidence["authorization_challenge"] == challenge
        and evidence["authorization_accepted"] is True
    )
    authorized = _time(evidence["authorization_accepted_at"])
    instruction_at = _time(evidence["instruction_created_at"])
    execute_at = _admission(evidence["execute_admission"], schedule)
    require_qualification(
        observed <= authorized <= instruction_at <= execute_at <= deadline
    )
    require_qualification(
        evidence["status"] == "PASS"
        and evidence["execute_invoked"] is True
        and evidence["forward_cycle_invoked"] is True
    )
    for key in (
        "prepare_calls",
        "prepare_verifier_calls",
        "stdin_reads",
        "execute_calls",
    ):
        require_qualification(type(evidence[key]) is int and evidence[key] == 1)
    for key in (
        "retry_count",
        "interactive_reauth_count",
        "placement_calls",
        "cancellation_calls",
        "options_mutation_calls",
        "crypto_mutation_calls",
    ):
        require_qualification(type(evidence[key]) is int and evidence[key] == 0)
    metadata, columns, rows = read_qualification_store(store_path)
    require_qualification(len(rows) == 3)
    records = [dict(zip(columns, row, strict=True)) for row in rows]
    qualified = [record for record in records if record["order_id"] == str(ORDER_ID)]
    require_qualification(len(qualified) == 1)
    new = qualified[0]
    prior = [
        row
        for row, record in zip(rows, records, strict=True)
        if record["order_id"] != str(ORDER_ID)
    ]
    before = validate_qualification_before(
        metadata, columns, prior, expected_before_sha256
    )
    for value in (
        evidence["durable_before"],
        prepare["durable_before"],
        prepare["durable_after"],
    ):
        require_qualification(_exact(value, before))
    require_qualification(
        _exact(
            evidence["durable_after"],
            qualification_fingerprint(metadata, columns, rows),
        )
    )
    for key, expected in {
        "proposal_id": str(PROPOSAL_ID),
        "symbol": "SPY",
        "side": "SELL",
        "desired_quantity": proposal["desired_quantity"],
        "approved_quantity": risk["approved_quantity"],
        "risk_outcome": "APPROVED",
        "risk_reason_codes": "",
        "order_type": "MARKET",
        "time_in_force": "DAY",
        "limit_price": None,
        "proposed_at": proposal["created_at"],
        "reviewed_at": execute_at.isoformat(),
        "commission": "0",
        "slippage_basis_points": "0",
    }.items():
        require_qualification(new[key] == expected)
    require_qualification(
        new["paper_trade_id"]
        == str(uuid5(UUID("e68a2c7e-59fd-5679-935c-ab78814b5b45"), str(ORDER_ID)))
    )
    require_qualification(
        new["fill_id"]
        == str(uuid5(UUID("cde151e5-5a25-5aab-8ec6-9d39e58ba13e"), str(ORDER_ID)))
    )
    require_qualification(
        _number(new["fill_price"]) == _number(new["bid_price"]) > 0
        and new["filled_at"] == new["venue_bid_time"]
        and proposed_at <= _time(new["filled_at"]) <= execute_at
    )
    operator = _object(read_qualification_json(operator_evidence_path), OPERATOR_FIELDS)
    require_qualification(
        evidence["operator_evidence_path"] == str(operator_evidence_path.resolve())
        and evidence["operator_evidence_sha256"]
        == hashlib.sha256(operator_evidence_path.read_bytes()).hexdigest()
        and _exact(evidence["operator_evidence"], operator)
    )
    expected_operator = {
        "source_head": head,
        "source_tree": tree,
        "status": "PASS",
        "phase": "complete",
        "symbol": "SPY",
        "side": "SELL",
        "quantity": risk["approved_quantity"],
        "order_type": "MARKET",
        "get_accounts_calls": 1,
        "get_equity_orders_calls": 2,
        "review_equity_order_calls": 1,
        "get_equity_quotes_calls": 0,
        "baseline_order_pages": 1,
        "post_review_order_pages": 1,
        "paper_record_count": 3,
        "replay": False,
        "review_echo_validated": True,
        "quote_fill_validated": True,
        "disclosure_present": True,
        "interactive_reauth_count": 0,
        "placement_calls": 0,
        "cancellation_calls": 0,
        "options_mutation_calls": 0,
        "crypto_mutation_calls": 0,
    }
    require_qualification(_exact(operator, expected_operator))
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "source_head": head,
        "source_tree": tree,
        "record_count": 3,
        "order_id": str(ORDER_ID),
        "authorization_challenge": challenge,
    }


def verify_robinhood_execute_qualification(
    *,
    store_path: Path,
    evidence_path: Path,
    prepare_evidence_path: Path,
    operator_evidence_path: Path,
    expected_source_head: str,
    expected_source_tree: str,
    expected_before_sha256: str,
) -> dict:
    """Reconcile successful qualification; all other evidence fails closed."""
    try:
        return _verify(
            store_path=store_path,
            evidence_path=evidence_path,
            prepare_evidence_path=prepare_evidence_path,
            operator_evidence_path=operator_evidence_path,
            expected_source_head=expected_source_head,
            expected_source_tree=expected_source_tree,
            expected_before_sha256=expected_before_sha256,
        )
    except Exception:
        raise ExecuteQualificationVerificationError(
            "qualification reconciliation failed"
        ) from None


def main() -> int:
    parser = argparse.ArgumentParser(description="Provider-free 131-V EXECUTE verifier")
    for name in ("store", "evidence", "prepare-evidence", "operator-evidence"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("expected-head", "expected-tree", "expected-before-sha256"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    try:
        result = verify_robinhood_execute_qualification(
            store_path=args.store,
            evidence_path=args.evidence,
            prepare_evidence_path=args.prepare_evidence,
            operator_evidence_path=args.operator_evidence,
            expected_source_head=args.expected_head,
            expected_source_tree=args.expected_tree,
            expected_before_sha256=args.expected_before_sha256,
        )
    except ExecuteQualificationVerificationError:
        print('{"status":"STOP"}')
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
