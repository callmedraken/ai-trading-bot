"""One-shot 134-D1 session reservation and bounded sanitized durable evidence."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from datetime import UTC, date, datetime
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid5

from trading_bot.review_paper.armed_history_failure import parse_history_failure
from trading_bot.strategies.production import ProductionStrategyContract


class ArmedSessionStatus(StrEnum):
    ADMITTED = "ADMITTED"
    HISTORY_STARTED = "HISTORY_STARTED"
    HISTORY_READY = "HISTORY_READY"
    RECOVERY_STARTED = "RECOVERY_STARTED"
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

_V2_FIELDS = frozenset(
    {
        "strategy_contract",
        "history_failure",
        "recovery_count",
        "recovery_reason",
        "predecessor_evidence",
        "predecessor_sha256",
    }
)
_ZERO_EFFECTS = (
    "strategy_evaluations",
    "prepare_attempts",
    "execute_attempts",
    "robinhood_get_equity_quotes",
    "robinhood_get_accounts",
    "robinhood_get_equity_orders",
    "robinhood_review_equity_order",
    "paper_mutations",
    "broker_placement_count",
)
_NO_RESULTS = (
    "strategy_outcome",
    "prepare_result",
    "execute_result",
    "proposal_id",
    "order_id",
    "fill_id",
    "wait_started_at",
    "admitted_at",
)
_LEGACY_FACTS = {
    "target_session": "2026-10-13",
    "source_head": "6bf8753b0cc8950ae27b32b6858b64d454c512f0",
    "source_tree": "ce3feb2ac48e7aebc23970142aafed5059c447e7",
    "contract_id": "d490a15f-2c6e-5a1c-af36-e5f233760a7b",
    "operation_id": "8e8c5102-8b52-5534-8288-b3261f65b2d4",
    "historical_sessions": ["2026-10-07", "2026-10-08", "2026-10-09", "2026-10-12"],
    "alpaca_reads": 1,
    "effect_counts_complete": False,
    "admission_opens_at": "2026-10-13T13:35:00+00:00",
    "admission_closes_at": "2026-10-13T19:55:00+00:00",
}


def armed_operation_id(contract_id: UUID) -> UUID:
    """Preserve the accepted D1 operation identity material and namespace."""
    material = ("armed-paper-result/v1", str(contract_id))
    return uuid5(
        UUID("b719fe73-bc50-565d-9b77-c39da34008bd"),
        "".join(f"{len(x)}:{x}" for x in material),
    )


def recovery_reason_for(value: dict[str, object]) -> str:
    """Closed pre-effect policy; caller must first validate canonical evidence."""
    if (
        value["status"] != "BLOCKED"
        or any(type(value[k]) is not int or value[k] != 0 for k in _ZERO_EFFECTS)
        or any(value[k] is not None for k in _NO_RESULTS)
        or value["snapshot_sha256"] != []
        or value["history_seed_sha256"] is not None
    ):
        raise ValueError("pre-effect history recovery not proven")
    if value["schema"] == "armed-paper-session/v1":
        if any(value[k] != v for k, v in _LEGACY_FACTS.items()):
            raise ValueError("legacy recovery tuple differs")
        return "FROZEN_OCTOBER_13_PRE_D1R1"
    if value["recovery_count"] != 0 or value["history_failure"] is None:
        raise ValueError("recovery unavailable or already consumed")
    failure = value["history_failure"]
    if (
        failure["classification"] == "TRANSPORT_FAILED"
        and failure["transport_stage"] != "RESPONSE_METADATA"
    ):
        return "TRANSIENT_HISTORY_TRANSPORT"
    status = failure["http_status"]
    if (
        failure["classification"] == "HTTP_FAILED"
        and type(status) is int
        and (status == 429 or 500 <= status <= 599)
    ):
        return "TRANSIENT_HISTORY_HTTP"
    raise ValueError("history failure is not recovery eligible")


def validate_session_evidence(value: dict[str, object]) -> None:
    """Reject unknown/free-form data, including tampered restart evidence."""
    if type(value) is dict and value.get("schema") == "armed-paper-session/v2":
        _validate_v2(value)
        return
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
    if value["status"] == ArmedSessionStatus.RECOVERY_STARTED.value:
        raise ValueError("v1 has no recovery authority")
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


def _validate_v2(value: dict[str, object]) -> None:
    if set(value) != _EVIDENCE_FIELDS | _V2_FIELDS:
        raise ValueError("invalid v2 evidence fields")
    base = {k: value[k] for k in _EVIDENCE_FIELDS}
    base["schema"] = "armed-paper-session/v1"
    if base["status"] == ArmedSessionStatus.RECOVERY_STARTED.value:
        base["status"] = ArmedSessionStatus.HISTORY_STARTED.value
    validate_session_evidence(base)
    contract = ProductionStrategyContract.from_json(value["strategy_contract"])
    if str(contract.symbol) != "SPY" or any(
        value[k] != v
        for k, v in {
            "source_head": contract.source_head,
            "source_tree": contract.source_tree,
            "contract_id": str(contract.contract_id),
            "target_session": contract.target_session_date.isoformat(),
        }.items()
    ):
        raise ValueError("v2 contract binding differs")
    count = value["recovery_count"]
    if type(count) is not int or count not in (0, 1):
        raise ValueError("invalid recovery count")
    if value["status"] == "RECOVERY_STARTED" and (
        any(value[k] != 0 for k in _ZERO_EFFECTS)
        or any(value[k] is not None for k in _NO_RESULTS)
        or value["alpaca_reads"] != 0
        or value["snapshot_sha256"] != []
        or value["history_seed_sha256"] is not None
        or value["history_failure"] is not None
        or not value["effect_counts_complete"]
    ):
        raise ValueError("recovery consumption must precede all effects")
    failure = value["history_failure"]
    if failure is not None:
        raw = (
            json.dumps(failure, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        parsed = parse_history_failure(raw)
        if (
            value["status"] != "BLOCKED"
            or any(
                failure[k] != value[k]
                for k in (
                    "source_head",
                    "source_tree",
                    "contract_id",
                    "target_session",
                    "operation_id",
                    "alpaca_reads",
                )
            )
            or (
                parsed.history_session is not None
                and (
                    parsed.read_ordinal > len(value["historical_sessions"])
                    or value["historical_sessions"][parsed.read_ordinal - 1]
                    != parsed.history_session.isoformat()
                )
            )
        ):
            raise ValueError("history failure binding differs")
    if count == 0:
        if (
            any(
                value[k] is not None
                for k in (
                    "predecessor_evidence",
                    "predecessor_sha256",
                    "recovery_reason",
                )
            )
            or value["status"] == "RECOVERY_STARTED"
        ):
            raise ValueError("unexpected recovery lineage")
        if value["operation_id"] != str(armed_operation_id(contract.contract_id)):
            raise ValueError("original operation differs")
        return
    prior = value["predecessor_evidence"]
    if (
        type(prior) is not dict
        or prior.get("schema")
        not in {"armed-paper-session/v1", "armed-paper-session/v2"}
        or prior.get("recovery_count", 0) != 0
    ):
        raise ValueError("invalid predecessor lineage")
    raw = evidence_bytes(prior)
    if (
        sha256(raw).hexdigest() != value["predecessor_sha256"]
        or recovery_reason_for(prior) != value["recovery_reason"]
    ):
        raise ValueError("predecessor digest or reason differs")
    if any(
        prior[k] != value[k]
        for k in ("target_session", "operation_id", "historical_sessions")
    ):
        raise ValueError("recovery session identity differs")
    previous = ProductionStrategyContract(
        contract.target_session_date,
        prior["source_head"],
        prior["source_tree"],
        contract.symbol,
        contract.strategy_config,
    )
    if (
        str(previous.contract_id) != prior["contract_id"]
        or str(armed_operation_id(previous.contract_id)) != prior["operation_id"]
    ):
        raise ValueError("recovery predecessor contract differs")
    if (
        prior["schema"] == "armed-paper-session/v2"
        and previous.to_json() != prior["strategy_contract"]
    ):
        raise ValueError("recovery strategy differs")


def evidence_bytes(value: dict[str, object]) -> bytes:
    validate_session_evidence(value)
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(payload) > MAX_SESSION_EVIDENCE_BYTES:
        raise ValueError("session evidence exceeds bound")
    return payload


class ArmedSessionStore:
    """Unique session fence; one explicit pre-effect CAS recovery, no reclamation."""

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

    def read(self, key: str) -> tuple[dict[str, object], bytes]:
        """Read existing canonical bytes without reservation or schema creation."""
        with closing(
            sqlite3.connect(
                self.path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0
            )
        ) as connection:
            row = connection.execute(
                "SELECT evidence FROM armed_session_v1 WHERE session_key=?", (key,)
            ).fetchone()
        if (
            row is None
            or type(row[0]) is not bytes
            or len(row[0]) > MAX_SESSION_EVIDENCE_BYTES
        ):
            raise ValueError("missing or invalid recovery predecessor")
        raw = row[0]
        value = json.loads(raw)
        if evidence_bytes(value) != raw:
            raise ValueError("noncanonical recovery predecessor")
        return value, raw


def write_session_evidence(path: Path, payload: bytes) -> None:
    """Exclusive terminal export; the database remains the pre-effect fence."""
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
