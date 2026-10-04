"""Independent, provider-free reconciliation of PREPARE qualification evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from collections.abc import Sequence
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import UUID

_SCHEMA = "arch131-q-prepare-qualification/v1"
_ADMISSION_FIELDS = {
    "status",
    "as_of",
    "session_date",
    "opens_at",
    "closes_at",
    "admission_opens_at",
    "admission_closes_at",
}
_DECIMAL_PREVIEW_FIELDS = {
    "requested_quantity",
    "approved_quantity",
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


class RobinhoodPrepareQualificationVerificationError(RuntimeError):
    """Evidence or current durable state fails the frozen qualification contract."""


@dataclass(frozen=True, slots=True)
class RobinhoodPrepareQualificationVerification:
    source_head: str
    source_tree: str
    proposal_id: UUID
    preparation_status: str
    record_count: int
    durable_sha256: str
    quote_observed_at: datetime | None
    quote_valid_until: datetime | None
    risk_outcome: str | None
    approved_quantity: Decimal | None


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RobinhoodPrepareQualificationVerificationError(message)


def _object(value: object, keys: set[str], name: str) -> dict:
    _require(type(value) is dict and set(value) == keys, f"{name} fields mismatch")
    return value


def _datetime(value: object) -> datetime:
    _require(type(value) is str, "timestamp must be a string")
    result = datetime.fromisoformat(value)
    _require(
        result.tzinfo is not None and result.utcoffset() is not None,
        "timestamp must be timezone-aware",
    )
    return result.astimezone(UTC)


def _decimal(value: object) -> Decimal:
    _require(type(value) is str, "Decimal must be a string")
    result = Decimal(value)
    _require(result.is_finite(), "Decimal must be finite")
    return result


def _duration(value: object) -> timedelta:
    _require(type(value) in (int, Decimal), "seconds must be a JSON number")
    seconds = Decimal(value)
    _require(seconds.is_finite(), "seconds must be finite")
    numerator, denominator = seconds.as_integer_ratio()
    microseconds, remainder = divmod(numerator * 1_000_000, denominator)
    _require(remainder == 0, "seconds must have exact microsecond precision")
    return timedelta(microseconds=microseconds)


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise RobinhoodPrepareQualificationVerificationError(
        f"invalid JSON constant: {value}"
    )


def _read_current(path: Path) -> dict[str, object]:
    # Independently canonicalize every column; no harness imports.
    with closing(
        sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    ) as connection:
        connection.execute("BEGIN")
        metadata = connection.execute(
            "SELECT key, value FROM metadata ORDER BY key"
        ).fetchall()
        cursor = connection.execute(
            "SELECT * FROM review_fills ORDER BY filled_at, paper_trade_id"
        )
        columns = [entry[0] for entry in cursor.description]
        rows = cursor.fetchall()
    material = json.dumps(
        {
            "metadata": metadata,
            "columns": columns,
            "rows": rows,
            "record_count": len(rows),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return {
        "metadata": [list(row) for row in metadata],
        "record_count": len(rows),
        "sha256": hashlib.sha256(material).hexdigest(),
    }


def _admission(
    value: object, schedule: dict, opening: timedelta, closing: timedelta
) -> dict:
    admission = _object(value, _ADMISSION_FIELDS, "admission")
    _require(
        admission["status"]
        in {
            "ADMITTED",
            "NON_SESSION_DATE",
            "BEFORE_REGULAR_WINDOW",
            "OPENING_BUFFER",
            "CLOSING_BUFFER",
            "AFTER_REGULAR_WINDOW",
        },
        "unknown admission status",
    )
    _datetime(admission["as_of"])
    _require(
        admission["session_date"] == schedule["session_date"],
        "admission session date mismatch",
    )
    for field in ("opens_at", "closes_at"):
        _require(
            _datetime(admission[field]) == _datetime(schedule[field]),
            "admission schedule mismatch",
        )
    _require(
        _datetime(admission["admission_opens_at"])
        == _datetime(schedule["opens_at"]) + opening,
        "admission opening mismatch",
    )
    _require(
        _datetime(admission["admission_closes_at"])
        == _datetime(schedule["closes_at"]) - closing,
        "admission closing mismatch",
    )
    return admission


def _verify(
    evidence: object, store_path: Path, head: str, tree: str, proposal_id: UUID
) -> RobinhoodPrepareQualificationVerification:
    evidence = _object(
        evidence,
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
        "evidence",
    )
    _require(evidence["schema"] == _SCHEMA, "evidence schema mismatch")
    _require(
        evidence["source_head"] == head and evidence["source_tree"] == tree,
        "source identity mismatch",
    )
    _require(
        type(evidence["store_path"]) is str
        and Path(evidence["store_path"]).is_absolute(),
        "evidence store must be absolute",
    )
    _require(
        Path(evidence["store_path"]).resolve() == store_path.resolve(),
        "store identity mismatch",
    )
    _require(
        evidence["execute_invoked"] is False, "execute_invoked must be exactly false"
    )
    _require(
        evidence["pipeline_result_present"] is False,
        "pipeline_result_present must be exactly false",
    )
    _require(
        type(evidence["new_trading_enabled"]) is bool,
        "new_trading_enabled must be bool",
    )
    proposal = _object(
        evidence["proposal"],
        {"proposal_id", "symbol", "side", "desired_quantity", "created_at"},
        "proposal",
    )
    _require(proposal["proposal_id"] == str(proposal_id), "proposal identity mismatch")
    _require(
        type(proposal["symbol"]) is str
        and re.fullmatch(r"[A-Z0-9.\-]{1,10}", proposal["symbol"]) is not None,
        "invalid proposal symbol",
    )
    _require(proposal["side"] in {"BUY", "SELL"}, "invalid proposal side")
    _require(
        _decimal(proposal["desired_quantity"]) > 0,
        "requested quantity must be positive",
    )
    _datetime(proposal["created_at"])
    schedule = _object(
        evidence["schedule"], {"session_date", "opens_at", "closes_at"}, "schedule"
    )
    _require(type(schedule["session_date"]) is str, "session_date must be a string")
    date.fromisoformat(schedule["session_date"])
    opening = _duration(evidence["opening_buffer_seconds"])
    closing_buffer = _duration(evidence["closing_buffer_seconds"])
    age = _duration(evidence["max_quote_age_seconds"])
    duration = _datetime(schedule["closes_at"]) - _datetime(schedule["opens_at"])
    _require(
        opening >= timedelta(0)
        and closing_buffer >= timedelta(0)
        and opening + closing_buffer < duration,
        "invalid session buffers",
    )
    _require(age > timedelta(0), "max quote age must be positive")
    current = _read_current(store_path)
    for key in ("durable_before", "durable_after"):
        durable = _object(evidence[key], {"metadata", "record_count", "sha256"}, key)
        _require(type(durable["record_count"]) is int, "record_count must be int")
        _require(durable == current, f"{key} differs from current durable state")
    metadata = dict(current["metadata"])
    _require(
        metadata.get("starting_cash") == evidence["starting_cash"],
        "starting cash mismatch",
    )
    _require(_decimal(evidence["starting_cash"]) > 0, "starting cash must be positive")
    preparation = _object(
        evidence["preparation"],
        {
            "status",
            "initial_admission",
            "price_snapshot",
            "quote_admission",
            "risk_preview",
            "quote_valid_until",
        },
        "preparation",
    )
    status = preparation["status"]
    _require(
        status
        in {
            "SESSION_NOT_ADMITTED",
            "SESSION_EXPIRED_DURING_ACQUISITION",
            "RISK_REJECTED",
            "READY_TO_PROCEED",
        },
        "unknown preparation status",
    )
    initial = _admission(
        preparation["initial_admission"], schedule, opening, closing_buffer
    )
    snapshot = preparation["price_snapshot"]
    quote = preparation["quote_admission"]
    preview = preparation["risk_preview"]
    deadline_value = preparation["quote_valid_until"]
    observed = deadline = outcome = approved = None
    if status == "SESSION_NOT_ADMITTED":
        _require(
            initial["status"] != "ADMITTED",
            "blocked initial admission must not be ADMITTED",
        )
        _require(
            snapshot is None
            and quote is None
            and preview is None
            and deadline_value is None,
            "blocked session must have no acquired/preview fields",
        )
    else:
        _require(
            initial["status"] == "ADMITTED", "acquired states require initial admission"
        )
        snapshot = _object(snapshot, {"observed_at", "marks"}, "snapshot")
        observed = _datetime(snapshot["observed_at"])
        marks = snapshot["marks"]
        _require(type(marks) is list and bool(marks), "marks must be a nonempty list")
        symbols = []
        source_times = []
        for mark in marks:
            mark = _object(mark, {"symbol", "price", "source_at"}, "mark")
            symbol = mark["symbol"]
            _require(
                type(symbol) is str
                and re.fullmatch(r"[A-Z0-9.\-]{1,10}", symbol) is not None,
                "invalid mark symbol",
            )
            _require(_decimal(mark["price"]) > 0, "mark price must be positive")
            source = _datetime(mark["source_at"])
            _require(source <= observed, "future source timestamp")
            symbols.append(symbol)
            source_times.append(source)
        _require(
            symbols == sorted(set(symbols)),
            "marks must be unique and canonically ordered",
        )
        _require(proposal["symbol"] in symbols, "proposal mark missing")
        quote = _admission(quote, schedule, opening, closing_buffer)
        _require(
            _datetime(quote["as_of"]) == observed,
            "quote admission must use observation time",
        )
        if status == "SESSION_EXPIRED_DURING_ACQUISITION":
            _require(
                quote["status"] != "ADMITTED"
                and preview is None
                and deadline_value is None,
                "expired acquisition must have no preview/deadline",
            )
        else:
            _require(
                quote["status"] == "ADMITTED",
                "completed preview requires quote admission",
            )
            preview = _object(
                preview,
                _DECIMAL_PREVIEW_FIELDS | {"risk_outcome", "reason_codes"},
                "risk preview",
            )
            values = {key: _decimal(preview[key]) for key in _DECIMAL_PREVIEW_FIELDS}
            approved = values["approved_quantity"]
            outcome = preview["risk_outcome"]
            _require(
                values["requested_quantity"] == _decimal(proposal["desired_quantity"]),
                "preview requested quantity mismatch",
            )
            reasons = preview["reason_codes"]
            _require(
                type(reasons) is list
                and all(type(reason) is str and bool(reason) for reason in reasons)
                and len(reasons) == len(set(reasons)),
                "invalid reason codes",
            )
            if status == "RISK_REJECTED":
                _require(
                    outcome == "REJECTED" and approved == 0,
                    "rejected preparation risk mismatch",
                )
            else:
                _require(
                    outcome in {"APPROVED", "RESIZED"} and approved > 0,
                    "ready preparation risk mismatch",
                )
            deadline = _datetime(deadline_value)
            expected_deadline = min(source + age for source in source_times)
            _require(deadline == expected_deadline, "quote deadline mismatch")
    return RobinhoodPrepareQualificationVerification(
        head,
        tree,
        proposal_id,
        status,
        current["record_count"],
        current["sha256"],
        observed,
        deadline,
        outcome,
        approved,
    )


def verify_robinhood_prepare_qualification(
    *,
    store_path: Path,
    evidence_path: Path,
    expected_source_head: str,
    expected_source_tree: str,
    expected_proposal_id: UUID,
) -> RobinhoodPrepareQualificationVerification:
    """Reconcile sanitized evidence against an independently read current store."""
    for name, value in (("store_path", store_path), ("evidence_path", evidence_path)):
        if type(value) is not type(Path()) or not value.is_absolute():
            raise TypeError(f"{name} must be an absolute exact Path")
    for name, value in (
        ("expected_source_head", expected_source_head),
        ("expected_source_tree", expected_source_tree),
    ):
        if type(value) is not str or re.fullmatch("[0-9a-f]{40}", value) is None:
            raise ValueError(f"{name} must be a lowercase 40-character Git SHA")
    if type(expected_proposal_id) is not UUID:
        raise TypeError("expected_proposal_id must be exactly UUID")
    try:
        evidence = json.loads(
            evidence_path.read_text(encoding="utf-8"),
            parse_float=Decimal,
            parse_constant=_invalid_constant,
            object_pairs_hook=_unique_object,
        )
        return _verify(
            evidence,
            store_path,
            expected_source_head,
            expected_source_tree,
            expected_proposal_id,
        )
    except (
        OSError,
        sqlite3.Error,
        ValueError,
        TypeError,
        KeyError,
        InvalidOperation,
        OverflowError,
    ) as error:
        raise RobinhoodPrepareQualificationVerificationError(
            "malformed or unavailable qualification evidence/store"
        ) from error


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify Architecture 131-R PREPARE qualification evidence"
    )
    parser.add_argument("--store", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-tree", required=True)
    parser.add_argument("--proposal-id", required=True, type=UUID)
    args = parser.parse_args(argv)
    result = verify_robinhood_prepare_qualification(
        store_path=args.store,
        evidence_path=args.evidence,
        expected_source_head=args.expected_head,
        expected_source_tree=args.expected_tree,
        expected_proposal_id=args.proposal_id,
    )
    payload = asdict(result)
    payload["proposal_id"] = str(result.proposal_id)
    for field in ("quote_observed_at", "quote_valid_until"):
        value = getattr(result, field)
        payload[field] = None if value is None else value.isoformat()
    payload["approved_quantity"] = (
        None if result.approved_quantity is None else str(result.approved_quantity)
    )
    payload["status"] = "PASS"
    print(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
