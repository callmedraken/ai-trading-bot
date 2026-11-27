"""Account-namespaced durable synthetic decision history.

The store records decision and preview facts only.  It has no provider, broker,
credential, or order-dispatch dependency.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_SCHEMA = "portfolio-manager-history/v1"


class PortfolioManagerStoreError(RuntimeError):
    """Base class for sanitized durable-history failures."""


class PortfolioManagerStoreCorruption(PortfolioManagerStoreError):
    """The file is not a valid history store for the selected account."""


class PortfolioManagerStoreConflict(PortfolioManagerStoreError):
    """One semantic preview intent was reused for different outcome facts."""


@dataclass(frozen=True, slots=True)
class StoredOutcome:
    intent_key: str
    snapshot_id: UUID
    semantic_digest: str
    recorded_at: datetime
    payload_json: str

    def __post_init__(self) -> None:
        if _HEX64.fullmatch(self.intent_key) is None:
            raise ValueError("intent_key must be lowercase SHA-256 hex")
        if not isinstance(self.snapshot_id, UUID):
            raise TypeError("snapshot_id must be UUID")
        if _HEX64.fullmatch(self.semantic_digest) is None:
            raise ValueError("semantic_digest must be lowercase SHA-256 hex")
        if (
            not isinstance(self.recorded_at, datetime)
            or self.recorded_at.tzinfo is None
            or self.recorded_at.utcoffset() is None
        ):
            raise ValueError("recorded_at must be timezone-aware")
        try:
            payload = json.loads(self.payload_json)
        except (TypeError, json.JSONDecodeError):
            raise ValueError("payload_json must contain a JSON object") from None
        if not isinstance(payload, dict):
            raise ValueError("payload_json must contain a JSON object")


class PortfolioManagerStore:
    """Persist one account's restart-safe, idempotent decision history.

    Each instance is bound to one opaque account fingerprint.  SQLite's
    ``BEGIN IMMEDIATE`` transaction and the primary key on ``intent_key`` make
    duplicate reservations safe across simultaneous service instances.
    Construction is effect-free; files are opened only by a worker call to
    ``load_recent`` or ``record_outcome``.
    """

    def __init__(self, state_root: str | Path, account_fingerprint: str) -> None:
        if not isinstance(state_root, (str, Path)) or not str(state_root).strip():
            raise ValueError("state_root must be a nonblank path")
        if (
            not isinstance(account_fingerprint, str)
            or _HEX64.fullmatch(account_fingerprint) is None
        ):
            raise ValueError("account fingerprint must be lowercase SHA-256 hex")
        self._account_fingerprint = account_fingerprint
        self._path = (
            Path(state_root).expanduser()
            / "portfolio-manager"
            / account_fingerprint
            / "decision-history.sqlite3"
        )

    @property
    def path(self) -> Path:
        """Return the account-specific state path without opening it."""
        return self._path

    def load_recent(self, *, limit: int = 100) -> tuple[StoredOutcome, ...]:
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("limit must be an integer from 1 through 1000")
        with self._transaction() as connection:
            rows = connection.execute(
                "SELECT intent_key, snapshot_id, semantic_digest, recorded_at, "
                "payload_json FROM outcomes ORDER BY sequence DESC LIMIT ?",
                (limit,),
            ).fetchall()
        try:
            return tuple(_stored(row) for row in reversed(rows))
        except (TypeError, ValueError):
            raise PortfolioManagerStoreCorruption(
                "stored decision history is malformed"
            ) from None

    def record_outcome(
        self,
        *,
        intent_key: str,
        snapshot_id: UUID,
        semantic_digest: str,
        recorded_at: datetime,
        payload: dict[str, object],
    ) -> tuple[StoredOutcome, bool]:
        """Insert one immutable outcome or return the matching prior record.

        ``semantic_digest`` deliberately excludes wall-clock audit time and
        recommendation identifiers.  Callers bind it to the stable semantic
        inputs and the resulting action, risk, and preview facts.
        """
        if _HEX64.fullmatch(intent_key) is None:
            raise ValueError("intent_key must be lowercase SHA-256 hex")
        if not isinstance(snapshot_id, UUID):
            raise TypeError("snapshot_id must be UUID")
        if _HEX64.fullmatch(semantic_digest) is None:
            raise ValueError("semantic_digest must be lowercase SHA-256 hex")
        if (
            not isinstance(recorded_at, datetime)
            or recorded_at.tzinfo is None
            or recorded_at.utcoffset() is None
        ):
            raise ValueError("recorded_at must be timezone-aware")
        if not isinstance(payload, dict):
            raise TypeError("payload must be a JSON object")
        try:
            payload_json = json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            )
        except (TypeError, ValueError):
            raise ValueError("payload must contain canonical JSON values") from None
        timestamp = recorded_at.astimezone(UTC).isoformat()

        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT intent_key, snapshot_id, semantic_digest, recorded_at, "
                "payload_json FROM outcomes WHERE intent_key = ?",
                (intent_key,),
            ).fetchone()
            if existing is not None:
                outcome = _stored(existing)
                if outcome.semantic_digest != semantic_digest:
                    raise PortfolioManagerStoreConflict(
                        "stable preview intent produced different semantic facts"
                    )
                return outcome, False
            connection.execute(
                "INSERT INTO outcomes "
                "(intent_key, snapshot_id, semantic_digest, recorded_at, payload_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    intent_key,
                    str(snapshot_id),
                    semantic_digest,
                    timestamp,
                    payload_json,
                ),
            )
            return (
                StoredOutcome(
                    intent_key,
                    snapshot_id,
                    semantic_digest,
                    datetime.fromisoformat(timestamp),
                    payload_json,
                ),
                True,
            )

    def _transaction(self) -> _StoreTransaction:
        return _StoreTransaction(self._path, self._account_fingerprint)


class _StoreTransaction:
    def __init__(self, path: Path, account_fingerprint: str) -> None:
        self._path = path
        self._account_fingerprint = account_fingerprint
        self._connection: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Connection:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self._path, timeout=2.0)
            connection.execute("PRAGMA busy_timeout = 2000")
            connection.execute("PRAGMA synchronous = FULL")
            connection.execute("BEGIN IMMEDIATE")
            expected = {
                "schema": _SCHEMA,
                "account_fingerprint": self._account_fingerprint,
            }
            existing_tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
            }
            if not existing_tables:
                connection.execute(
                    "CREATE TABLE store_metadata "
                    "(name TEXT PRIMARY KEY, value TEXT NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE outcomes ("
                    "sequence INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "intent_key TEXT NOT NULL UNIQUE, "
                    "snapshot_id TEXT NOT NULL, "
                    "semantic_digest TEXT NOT NULL, "
                    "recorded_at TEXT NOT NULL, "
                    "payload_json TEXT NOT NULL)"
                )
                for name, value in expected.items():
                    connection.execute(
                        "INSERT INTO store_metadata (name, value) VALUES (?, ?)",
                        (name, value),
                    )
            elif existing_tables != {"store_metadata", "outcomes"}:
                raise PortfolioManagerStoreCorruption(
                    "history database schema is incomplete"
                )
            else:
                metadata = dict(
                    connection.execute(
                        "SELECT name, value FROM store_metadata"
                    ).fetchall()
                )
                if any(metadata.get(name) != value for name, value in expected.items()):
                    raise PortfolioManagerStoreCorruption(
                        "history database identity or schema mismatch"
                    )
                outcome_columns = {
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(outcomes)"
                    ).fetchall()
                }
                if outcome_columns != {
                    "sequence",
                    "intent_key",
                    "snapshot_id",
                    "semantic_digest",
                    "recorded_at",
                    "payload_json",
                }:
                    raise PortfolioManagerStoreCorruption(
                        "history database schema is incomplete"
                    )
        except PortfolioManagerStoreError:
            if "connection" in locals():
                connection.rollback()
                connection.close()
            raise
        except (OSError, sqlite3.Error):
            if "connection" in locals():
                connection.rollback()
                connection.close()
            raise PortfolioManagerStoreError(
                "decision history is unavailable"
            ) from None
        self._connection = connection
        return connection

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> bool:
        connection = self._connection
        if connection is not None:
            try:
                if exc_type is None:
                    connection.commit()
                else:
                    connection.rollback()
            except sqlite3.Error:
                connection.rollback()
                raise PortfolioManagerStoreError(
                    "decision history transaction failed"
                ) from None
            finally:
                connection.close()
        return False


def _stored(row: tuple[object, ...]) -> StoredOutcome:
    intent_key, snapshot_id, digest, timestamp, payload = row
    try:
        outcome = StoredOutcome(
            str(intent_key),
            UUID(str(snapshot_id)),
            str(digest),
            datetime.fromisoformat(str(timestamp)),
            str(payload),
        )
    except (TypeError, ValueError):
        raise PortfolioManagerStoreCorruption(
            "stored decision history is malformed"
        ) from None
    return outcome
