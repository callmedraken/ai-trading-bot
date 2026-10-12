"""One-shot 134-D1 session reservation and bounded sanitized durable evidence."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID


class ArmedSessionStatus(StrEnum):
    ADMITTED = "ADMITTED"
    HISTORY_STARTED = "HISTORY_STARTED"
    HISTORY_READY = "HISTORY_READY"
    NO_SIGNAL = "NO_SIGNAL"
    WAITING_FOR_MARKET = "WAITING_FOR_MARKET"
    PREPARING = "PREPARING"
    READY_TO_PROCEED = "READY_TO_PROCEED"
    EXECUTE_STARTED = "EXECUTE_STARTED"
    PAPER_EXECUTED = "PAPER_EXECUTED"
    RISK_REJECTED = "RISK_REJECTED"
    SESSION_NOT_ADMITTED = "SESSION_NOT_ADMITTED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    BLOCKED = "BLOCKED"
    ALREADY_COMPLETED = "ALREADY_COMPLETED"


MAX_SESSION_EVIDENCE_BYTES = 32 * 1024


_EVIDENCE_FIELDS = frozenset(
    {
        "schema",
        "source_head",
        "source_tree",
        "contract_id",
        "target_session",
        "historical_provider",
        "historical_sessions",
        "snapshot_sha256",
        "history_seed_sha256",
        "operation_id",
        "order_id",
        "fill_id",
        "strategy_outcome",
        "proposal_id",
        "wait_started_at",
        "admitted_at",
        "admission_opens_at",
        "admission_closes_at",
        "prepare_result",
        "execute_result",
        "alpaca_reads",
        "strategy_evaluations",
        "prepare_attempts",
        "execute_attempts",
        "robinhood_get_equity_quotes",
        "robinhood_get_accounts",
        "robinhood_get_equity_orders",
        "robinhood_review_equity_order",
        "paper_mutations",
        "broker_placement_count",
        "effect_counts_complete",
        "status",
    }
)


def validate_session_evidence(value: dict[str, object]) -> None:
    """Reject unknown/free-form data, including tampered restart evidence."""
    if (
        type(value) is not dict
        or set(value) != _EVIDENCE_FIELDS
        or value["schema"] != "armed-paper-session/v1"
        or value["historical_provider"] != "alpaca"
        or type(value["effect_counts_complete"]) is not bool
    ):
        raise ValueError("invalid evidence schema")
    for name in ("source_head", "source_tree"):
        text = value[name]
        if (
            type(text) is not str
            or len(text) != 40
            or any(c not in "0123456789abcdef" for c in text)
        ):
            raise ValueError("invalid source identity")
    ArmedSessionStatus(value["status"])
    if (
        date.fromisoformat(value["target_session"]).isoformat()
        != value["target_session"]
    ):
        raise ValueError("invalid target date")
    sessions = value["historical_sessions"]
    if type(sessions) is not list or len(sessions) > 253:
        raise ValueError("invalid history session list")
    for item in sessions:
        if date.fromisoformat(item).isoformat() != item:
            raise ValueError("invalid history date")
    digests = value["snapshot_sha256"]
    if type(digests) is not list or len(digests) > 253:
        raise ValueError("invalid snapshot digests")
    for text in digests + (
        [value["history_seed_sha256"]] if value["history_seed_sha256"] else []
    ):
        if (
            type(text) is not str
            or len(text) != 64
            or any(c not in "0123456789abcdef" for c in text)
        ):
            raise ValueError("invalid canonical evidence digest")
    for name in ("contract_id", "operation_id", "order_id", "fill_id", "proposal_id"):
        text = value[name]
        if text is None and name in {"order_id", "fill_id", "proposal_id"}:
            continue
        if type(text) is not str or str(UUID(text)) != text:
            raise ValueError("invalid bounded identity")
    for name in (
        "wait_started_at",
        "admitted_at",
        "admission_opens_at",
        "admission_closes_at",
    ):
        text = value[name]
        if text is not None:
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None or parsed.astimezone(UTC).isoformat() != text:
                raise ValueError("invalid evidence timestamp")
    for name, bound in (
        ("alpaca_reads", 253),
        ("strategy_evaluations", 1),
        ("prepare_attempts", 1),
        ("execute_attempts", 1),
        ("robinhood_get_equity_quotes", 1),
        ("robinhood_get_accounts", 1),
        ("robinhood_get_equity_orders", 202),
        ("robinhood_review_equity_order", 1),
        ("paper_mutations", 1),
        ("broker_placement_count", 0),
    ):
        count = value[name]
        if (
            count is None
            and name == "paper_mutations"
            and not value["effect_counts_complete"]
        ):
            continue
        if type(count) is not int or not 0 <= count <= bound:
            raise ValueError("invalid effect count")
    for name, allowed in (
        ("strategy_outcome", {None, "NO_SIGNAL", "TRADE_PROPOSAL"}),
        (
            "prepare_result",
            {
                None,
                "SESSION_NOT_ADMITTED",
                "SESSION_EXPIRED_DURING_ACQUISITION",
                "RISK_REJECTED",
                "READY_TO_PROCEED",
            },
        ),
        ("execute_result", {None, "PASS"}),
    ):
        if value[name] not in allowed:
            raise ValueError("invalid result classification")


def evidence_bytes(value: dict[str, object]) -> bytes:
    validate_session_evidence(value)
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(payload) > MAX_SESSION_EVIDENCE_BYTES:
        raise ValueError("session evidence exceeds bound")
    return payload


class ArmedSessionStore:
    """Atomic unique (symbol, session) fence; no reclaim, lease expiry or retry."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=0, isolation_level=None)
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS armed_session_v1 "
            "(session_key TEXT PRIMARY KEY, evidence BLOB NOT NULL)"
        )
        return connection

    def initialize(self) -> None:
        """Create the reviewed table without manufacturing a reservation."""
        if self.path.exists():
            self.qualify()
            return
        with self.path.open("xb"):
            pass
        with closing(self._connect()):
            pass
        self.qualify()

    def qualify(self) -> int:
        """Read-only exact table/evidence validation; return reservation count."""
        with closing(
            sqlite3.connect(
                self.path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True
            )
        ) as connection:
            schema = connection.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY name"
            ).fetchall()
            if schema != [
                (
                    "table",
                    "armed_session_v1",
                    "armed_session_v1",
                    "CREATE TABLE armed_session_v1 "
                    "(session_key TEXT PRIMARY KEY, evidence BLOB NOT NULL)",
                ),
                (
                    "index",
                    "sqlite_autoindex_armed_session_v1_1",
                    "armed_session_v1",
                    None,
                ),
            ] or connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError("invalid session schema")
            count = 0
            for key, raw in connection.execute(
                "SELECT session_key,evidence FROM armed_session_v1"
            ):
                if type(raw) is not bytes or len(raw) > MAX_SESSION_EVIDENCE_BYTES:
                    raise ValueError("invalid session evidence")
                value = json.loads(raw)
                if evidence_bytes(value) != raw or key != (
                    "armed-paper-session/v1:SPY:" + value["target_session"]
                ):
                    raise ValueError("invalid session reservation")
                count += 1
            return count

    def reserve(self, key: str, evidence: dict[str, object]) -> dict | None:
        payload = evidence_bytes(evidence)
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                prior = connection.execute(
                    "SELECT evidence FROM armed_session_v1 WHERE session_key=?", (key,)
                ).fetchone()
                if prior is not None:
                    raw = prior[0]
                    if type(raw) is not bytes or len(raw) > MAX_SESSION_EVIDENCE_BYTES:
                        raise ValueError("invalid prior evidence")
                    value = json.loads(raw)
                    if evidence_bytes(value) != raw:
                        raise ValueError("noncanonical prior evidence")
                    connection.execute("COMMIT")
                    return value
                connection.execute(
                    "INSERT INTO armed_session_v1 VALUES (?,?)", (key, payload)
                )
                connection.execute("COMMIT")
                return None
            except BaseException:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise

    def publish(self, key: str, before: bytes, evidence: dict[str, object]) -> bytes:
        payload = evidence_bytes(evidence)
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "UPDATE armed_session_v1 SET evidence=? "
                "WHERE session_key=? AND evidence=?",
                (payload, key, before),
            )
            if cursor.rowcount != 1:
                raise ValueError("session fence changed; reconciliation required")
        return payload


def write_session_evidence(path: Path, payload: bytes) -> None:
    """Exclusive terminal export; the database remains the pre-effect fence."""
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
