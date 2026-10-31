"""Append-only, crash-consistent SQLite authority for simulated paper state."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Callable, Mapping
from contextlib import closing
from dataclasses import fields, replace
from datetime import UTC, datetime
from decimal import Context, Decimal, localcontext
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID

from trading_bot.desktop_paper.configuration import PaperEvaluationConfig
from trading_bot.desktop_paper.engine import (
    PaperCycleEngine,
    cycle_identity,
    financial_identity,
)
from trading_bot.desktop_paper.models import (
    PaperAccountState,
    PaperControlState,
    PaperCycleInput,
    PaperCycleKind,
    PaperCycleResult,
    PaperRuntimePolicy,
    PaperStoreSnapshot,
)
from trading_bot.domain import (
    Order,
    OrderFill,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Symbol,
    TimeInForce,
    TradeProposal,
)
from trading_bot.execution import OrderEvent, OrderEventType
from trading_bot.execution.exceptions import (
    DuplicateEventError,
    DuplicateOrderError,
)
from trading_bot.execution.exceptions import (
    DuplicateFillError as DuplicateEngineFillError,
)
from trading_bot.ledger import DuplicateFillError as DuplicateLedgerFillError
from trading_bot.ledger import PaperLedger
from trading_bot.risk import (
    RiskContext,
    RiskDecision,
    RiskOutcome,
    RiskReason,
    RiskReasonCode,
)

_APPLICATION_ID = 0x44505035  # DPP5
_SCHEMA_VERSION = 1
_ZERO_HASH = "0" * 64
_STORE_MARKER = "desktop-paper-store/v1"
_ARITHMETIC_CONTEXT = Context(prec=1024, Emax=999_999, Emin=-999_999)
_STORE_SCHEMA = {
    "chain_events": """CREATE TABLE chain_events (
        seq INTEGER PRIMARY KEY,
        event_id TEXT NOT NULL UNIQUE,
        event_type TEXT NOT NULL,
        payload TEXT NOT NULL,
        previous_hash TEXT NOT NULL,
        event_hash TEXT NOT NULL
    )""",
    "cycle_slots": """CREATE TABLE cycle_slots (
        account_id TEXT NOT NULL,
        source_lane TEXT NOT NULL,
        symbol TEXT NOT NULL,
        session_id TEXT NOT NULL,
        cycle_id TEXT NOT NULL UNIQUE,
        event_id TEXT NOT NULL UNIQUE REFERENCES chain_events(event_id),
        PRIMARY KEY (account_id, source_lane, symbol, session_id)
    )""",
    "effect_identities": """CREATE TABLE effect_identities (
        identity TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        cycle_id TEXT NOT NULL,
        event_id TEXT NOT NULL REFERENCES chain_events(event_id)
    )""",
    "store_metadata": """CREATE TABLE store_metadata (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""",
}


class PaperEvaluationStoreError(RuntimeError):
    """Base error for durable paper-store failures."""


class PaperEvaluationStoreCorruptionError(PaperEvaluationStoreError):
    """Raised when SQLite schema or the financial event chain is invalid."""


class PaperEvaluationStoreConflictError(PaperEvaluationStoreError):
    """Raised after a conflict diagnostic is durably recorded."""


class PaperEvaluationStore:
    """Persist complete ordered financial cycles in a single SQLite database."""

    def __init__(
        self,
        path: str | Path,
        *,
        account_id: UUID,
        config: PaperEvaluationConfig,
        fault_hook: Callable[[str], None] | None = None,
    ) -> None:
        if not isinstance(path, (str, Path)) or not str(path):
            raise ValueError("path must be nonblank")
        if not isinstance(account_id, UUID):
            raise TypeError("account_id must be a UUID")
        if type(config) is not PaperEvaluationConfig:
            raise TypeError("config must be an exact PaperEvaluationConfig")
        if fault_hook is not None and not callable(fault_hook):
            raise TypeError("fault_hook must be callable or None")
        self._path = Path(path)
        self._database_was_missing = not self._path.exists()
        self._fresh_schema_created = False
        self._account_id = account_id
        self._config = config
        self._source_lane = config.policy.source_lane
        self._fault_hook = fault_hook
        self._initialize_and_validate()

    @property
    def path(self) -> Path:
        """The selected database path, without exposing a connection handle."""
        return self._path

    def close(self) -> None:
        """Close seam retained for the worker; each operation owns its connection."""

    def load_state(self) -> PaperStoreSnapshot:
        with closing(self._connection()) as connection:
            self._begin(connection)
            self._ensure_base_events(connection)
            state = self._reconstruct(connection)
            connection.commit()
        return self._snapshot(state)

    def latest_cycle(self) -> PaperCycleResult | None:
        """Return the exact validated last cycle, including after a clean reopen."""
        return self.load_state().latest_result

    def commit_cycle(
        self,
        cycle: PaperCycleInput,
        *,
        stop_requested: Callable[[], bool] | None = None,
    ) -> PaperCycleResult:
        """Atomically evaluate, append, and read back one financial session.

        A stop observed after BEGIN IMMEDIATE and before slot admission prevents
        the cycle. Once the transaction is admitted, it is allowed to commit or
        roll back as a whole.
        """
        if not isinstance(cycle, PaperCycleInput):
            raise TypeError("cycle must be a PaperCycleInput")
        if stop_requested is not None and not callable(stop_requested):
            raise TypeError("stop_requested must be callable or None")
        conflict: str | None = None
        committed_result: PaperCycleResult | None = None
        with closing(self._connection()) as connection:
            self._begin(connection)
            self._ensure_base_events(connection)
            if stop_requested is not None and stop_requested():
                connection.rollback()
                raise InterruptedError("paper cycle stopped before admission")
            self._call_hook("admitted")
            state = self._reconstruct(connection)
            slot_id = cycle_identity(
                self._account_id,
                self._source_lane,
                cycle.symbol.value,
                cycle.execution_session_id,
            )
            existing = self._find_slot(connection, cycle, state)
            if existing is not None:
                stored_result, stored_input_material = existing
                input_material = self._cycle_input_material(cycle)
                requested_material = _canonical_json(
                    {
                        "configuration_revision_id": str(
                            self._config.configuration_revision_id
                        ),
                        "input": input_material,
                    }
                )
                if requested_material == stored_input_material:
                    connection.commit()
                    return stored_result
                conflict = "SLOT_MATERIAL_CONFLICT"
                self._append_diagnostic(
                    connection,
                    conflict,
                    {
                        "cycle_id": str(slot_id),
                        "existing_material_sha256": hashlib.sha256(
                            stored_input_material.encode("utf-8")
                        ).hexdigest(),
                        "requested_material_sha256": hashlib.sha256(
                            requested_material.encode("utf-8")
                        ).hexdigest(),
                    },
                )
                connection.commit()
            elif state.control.kill_latched:
                committed_result = PaperCycleResult(
                    cycle_id=slot_id,
                    kind=PaperCycleKind.KILL_LATCHED,
                    input=cycle,
                    configuration_revision_id=self._config.configuration_revision_id,
                    risk_context=None,
                    risk_decision=None,
                    order=None,
                    fill=None,
                    order_events=(),
                    account=state.account,
                    cursor_index=state.cursor_index,
                    control=state.control,
                    diagnostic="KILL_LATCHED",
                )
                connection.commit()
            else:
                cursor_index = state.cursor_by_symbol.get(cycle.symbol, 0)
                if cycle.execution_index != cursor_index + 1:
                    raise PaperEvaluationStoreConflictError(
                        "EXECUTION_CURSOR_OUT_OF_ORDER"
                    )
                expected_symbol = self._config.binding.symbol
                if cycle.symbol != expected_symbol:
                    raise PaperEvaluationStoreConflictError(
                        "OBSERVATION_SYMBOL_DOES_NOT_MATCH_BINDING"
                    )
                engine = PaperCycleEngine(
                    account_id=self._account_id,
                    source_lane=self._source_lane,
                    policy=self._config.policy,
                    configuration_revision_id=self._config.configuration_revision_id,
                )
                try:
                    result = engine.process(cycle, state.ledger, state.control)
                except (
                    DuplicateEventError,
                    DuplicateEngineFillError,
                    DuplicateLedgerFillError,
                    DuplicateOrderError,
                ) as error:
                    conflict = "DUPLICATE_FINANCIAL_IDENTITY"
                    self._append_diagnostic(
                        connection,
                        conflict,
                        {
                            "cycle_id": str(slot_id),
                            "failure_class": type(error).__name__,
                        },
                    )
                    connection.commit()
                    result = None
                if result is None:
                    # The diagnostic itself is the only durable result.
                    pass
                else:
                    requested_material = _canonical_json(
                        {
                            "configuration_revision_id": str(
                                self._config.configuration_revision_id
                            ),
                            "input": self._cycle_input_material(cycle),
                        }
                    )
                    payload = _canonical_json(
                        {
                            "input_material": requested_material,
                            "result": _encode_result(result, omit_account_fills=True),
                        }
                    )
                    event_id = str(result.cycle_id)
                    self._append_event(
                        connection,
                        event_id=event_id,
                        event_type="CYCLE",
                        payload=payload,
                    )
                    connection.execute(
                        """INSERT INTO cycle_slots
                           (account_id, source_lane, symbol, session_id,
                            cycle_id, event_id)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            str(self._account_id),
                            self._source_lane,
                            cycle.symbol.value,
                            cycle.execution_session_id,
                            str(result.cycle_id),
                            event_id,
                        ),
                    )
                    try:
                        self._record_effect_identities(connection, result)
                    except sqlite3.IntegrityError as error:
                        connection.rollback()
                        # A durable diagnostic is recorded in its own transaction;
                        # no order, fill, event, cursor, or account result survived.
                        self._record_conflict_after_rollback(
                            "DUPLICATE_FINANCIAL_IDENTITY",
                            {"cycle_id": str(result.cycle_id)},
                        )
                        raise PaperEvaluationStoreConflictError(
                            "DUPLICATE_FINANCIAL_IDENTITY"
                        ) from error
                    self._call_hook("before_commit")
                    connection.commit()
                    self._call_hook("after_commit")
                    committed_result = result
        if conflict is not None:
            raise PaperEvaluationStoreConflictError(conflict)
        if committed_result is None:
            raise PaperEvaluationStoreCorruptionError(
                "cycle transaction completed without a result"
            )
        return committed_result

    def latch_kill(self) -> PaperControlState:
        """Durably latch the all-side kill gate."""
        return self._write_control(
            lambda current: PaperControlState(
                current.version + 1, True, current.new_buys_enabled
            )
        )

    def set_new_buys_enabled(self, enabled: bool) -> PaperControlState:
        """Persist the RiskManager new-trading switch; sells remain risk-managed."""
        if not isinstance(enabled, bool):
            raise TypeError("enabled must be a bool")
        return self._write_control(
            lambda current: PaperControlState(
                current.version + 1, current.kill_latched, enabled
            )
        )

    def clear_kill_when_stopped(
        self, *, active_worker: bool = False
    ) -> PaperControlState:
        """Clear kill only through the bounded stopped-worker seam."""
        if not isinstance(active_worker, bool):
            raise TypeError("active_worker must be a bool")
        if active_worker:
            raise PaperEvaluationStoreConflictError(
                "KILL_CLEAR_REFUSED_WHILE_WORKER_ACTIVE"
            )
        return self._write_control(
            lambda current: PaperControlState(
                current.version + 1, False, current.new_buys_enabled
            )
        )

    def _write_control(
        self, update: Callable[[PaperControlState], PaperControlState]
    ) -> PaperControlState:
        with closing(self._connection()) as connection:
            self._begin(connection)
            self._ensure_base_events(connection)
            state = self._reconstruct(connection)
            updated = update(state.control)
            if updated == state.control:
                connection.commit()
                return updated
            event_id = str(
                financial_identity(
                    "control",
                    f"{self._account_id}|{self._source_lane}|{updated.version}",
                )
            )
            self._append_event(
                connection,
                event_id=event_id,
                event_type="CONTROL",
                payload=_canonical_json(_encode(updated)),
            )
            self._call_hook("before_commit")
            connection.commit()
        return updated

    def _initialize_and_validate(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connection()) as connection:
            self._ensure_schema(connection)
            self._begin(connection)
            self._ensure_base_events(connection)
            self._reconstruct(connection)
            connection.commit()
            self._fresh_schema_created = False

    def _connection(self) -> sqlite3.Connection:
        try:
            connection = sqlite3.connect(
                self._path,
                timeout=30,
                isolation_level=None,
            )
        except sqlite3.DatabaseError as error:
            raise PaperEvaluationStoreCorruptionError(
                "PAPER_SQLITE_OPEN_FAILED"
            ) from error
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA busy_timeout=30000")
            if connection.execute("PRAGMA foreign_keys").fetchone() != (1,):
                raise PaperEvaluationStoreCorruptionError(
                    "PAPER_SQLITE_FOREIGN_KEYS_UNAVAILABLE"
                )
            if connection.execute("PRAGMA synchronous").fetchone() != (2,):
                raise PaperEvaluationStoreCorruptionError(
                    "PAPER_SQLITE_SYNCHRONOUS_NOT_FULL"
                )
            return connection
        except (sqlite3.DatabaseError, PaperEvaluationStoreError) as error:
            connection.close()
            if isinstance(error, PaperEvaluationStoreError):
                raise
            raise PaperEvaluationStoreCorruptionError(
                "PAPER_SQLITE_PRAGMA_FAILED"
            ) from error

    def _ensure_schema(self, connection: sqlite3.Connection) -> None:
        try:
            objects = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            if not objects:
                if not self._database_was_missing:
                    raise PaperEvaluationStoreCorruptionError(
                        "PAPER_SQLITE_PREEXISTING_EMPTY_SCHEMA"
                    )
                connection.executescript(
                    """
                    BEGIN IMMEDIATE;
                    CREATE TABLE chain_events (
                        seq INTEGER PRIMARY KEY,
                        event_id TEXT NOT NULL UNIQUE,
                        event_type TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        previous_hash TEXT NOT NULL,
                        event_hash TEXT NOT NULL
                    );
                    CREATE TABLE store_metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    );
                    CREATE TABLE cycle_slots (
                        account_id TEXT NOT NULL,
                        source_lane TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        session_id TEXT NOT NULL,
                        cycle_id TEXT NOT NULL UNIQUE,
                        event_id TEXT NOT NULL UNIQUE REFERENCES chain_events(event_id),
                        PRIMARY KEY (account_id, source_lane, symbol, session_id)
                    );
                    CREATE TABLE effect_identities (
                        identity TEXT PRIMARY KEY,
                        kind TEXT NOT NULL,
                        cycle_id TEXT NOT NULL,
                        event_id TEXT NOT NULL REFERENCES chain_events(event_id)
                    );
                    INSERT INTO store_metadata(key,value)
                        VALUES('schema_marker','desktop-paper-store/v1');
                    PRAGMA application_id=1146114101;
                    PRAGMA user_version=1;
                    COMMIT;
                    """
                )
                connection.execute("PRAGMA journal_mode=WAL")
                self._fresh_schema_created = True
                return
            application_id = connection.execute("PRAGMA application_id").fetchone()[0]
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if application_id != _APPLICATION_ID or version != _SCHEMA_VERSION:
                raise PaperEvaluationStoreCorruptionError(
                    "PAPER_SQLITE_SCHEMA_INCOMPATIBLE"
                )
            table_names = {name for (name,) in objects}
            if table_names != set(_STORE_SCHEMA):
                raise PaperEvaluationStoreCorruptionError(
                    "PAPER_SQLITE_SCHEMA_TABLE_SET_INVALID"
                )
            for table, expected_sql in _STORE_SCHEMA.items():
                actual = connection.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                if actual is None or _normalized_sql(actual[0]) != _normalized_sql(
                    expected_sql
                ):
                    raise PaperEvaluationStoreCorruptionError(
                        "PAPER_SQLITE_SCHEMA_CONSTRAINTS_INVALID"
                    )
            marker = connection.execute(
                "SELECT value FROM store_metadata WHERE key='schema_marker'"
            ).fetchone()
            if marker != (_STORE_MARKER,):
                raise PaperEvaluationStoreCorruptionError(
                    "PAPER_SQLITE_SCHEMA_MARKER_INVALID"
                )
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()
            if journal_mode != ("wal",):
                raise PaperEvaluationStoreCorruptionError(
                    "PAPER_SQLITE_JOURNAL_MODE_INVALID"
                )
            integrity = connection.execute("PRAGMA quick_check").fetchone()
            if integrity != ("ok",):
                raise PaperEvaluationStoreCorruptionError(
                    "PAPER_SQLITE_INTEGRITY_CHECK_FAILED"
                )
            foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
            if foreign_keys:
                raise PaperEvaluationStoreCorruptionError(
                    "PAPER_SQLITE_FOREIGN_KEY_FAILURE"
                )
        except PaperEvaluationStoreError:
            raise
        except sqlite3.DatabaseError as error:
            raise PaperEvaluationStoreCorruptionError(
                "PAPER_SQLITE_SCHEMA_INVALID"
            ) from error

    @staticmethod
    def _begin(connection: sqlite3.Connection) -> None:
        try:
            connection.execute("BEGIN IMMEDIATE")
        except sqlite3.DatabaseError as error:
            raise PaperEvaluationStoreError(
                "PAPER_SQLITE_TRANSACTION_FAILED"
            ) from error

    def _ensure_base_events(self, connection: sqlite3.Connection) -> None:
        events = connection.execute(
            "SELECT seq, event_type, payload FROM chain_events ORDER BY seq"
        ).fetchall()
        if not events:
            if not self._fresh_schema_created:
                raise PaperEvaluationStoreCorruptionError(
                    "PAPER_FINANCIAL_CHAIN_MISSING"
                )
            account_payload = _canonical_json(
                {
                    "account_id": str(self._account_id),
                    "source_lane": self._source_lane,
                    "starting_cash": _encode(self._config.policy.starting_cash),
                }
            )
            self._append_event(
                connection,
                event_id=str(
                    financial_identity(
                        "account-opened", f"{self._account_id}|{self._source_lane}"
                    )
                ),
                event_type="ACCOUNT_OPENED",
                payload=account_payload,
            )
            self._append_config_event(connection, self._config)
            initial_control = PaperControlState(0, False, True)
            self._append_event(
                connection,
                event_id=str(
                    financial_identity(
                        "control",
                        f"{self._account_id}|{self._source_lane}|0",
                    )
                ),
                event_type="CONTROL",
                payload=_canonical_json(_encode(initial_control)),
            )
            connection.execute(
                "INSERT INTO store_metadata(key,value) VALUES('store_seeded',?)",
                (_STORE_MARKER,),
            )
            return
        seeded = connection.execute(
            "SELECT value FROM store_metadata WHERE key='store_seeded'"
        ).fetchone()
        if seeded != (_STORE_MARKER,):
            raise PaperEvaluationStoreCorruptionError(
                "PAPER_FINANCIAL_CHAIN_SEED_MARKER_MISSING"
            )
        try:
            stored_configs = tuple(
                _decode(json.loads(payload))
                for (payload,) in connection.execute(
                    "SELECT payload FROM chain_events WHERE event_type='CONFIGURATION'"
                ).fetchall()
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise PaperEvaluationStoreCorruptionError(
                "PAPER_CONFIGURATION_EVENT_INVALID"
            ) from error
        current_revision_present = any(
            type(stored) is PaperEvaluationConfig
            and stored.configuration_revision_id
            == self._config.configuration_revision_id
            for stored in stored_configs
        )
        if not current_revision_present:
            raise PaperEvaluationStoreCorruptionError(
                "PAPER_CONFIGURATION_REVISION_MISMATCH"
            )
        state = self._reconstruct(connection)
        if (
            state.account_id != self._account_id
            or state.source_lane != self._source_lane
        ):
            raise PaperEvaluationStoreCorruptionError(
                "PAPER_ACCOUNT_OR_SOURCE_MISMATCH"
            )
        existing_config = state.configs.get(self._config.configuration_revision_id)
        encoded = _canonical_json(_encode(self._config))
        if existing_config is not None:
            if existing_config != encoded:
                raise PaperEvaluationStoreCorruptionError(
                    "PAPER_CONFIGURATION_REVISION_CONFLICT"
                )
        else:
            raise PaperEvaluationStoreCorruptionError(
                "PAPER_CONFIGURATION_REVISION_MISMATCH"
            )

    def _append_config_event(
        self, connection: sqlite3.Connection, config: PaperEvaluationConfig
    ) -> None:
        event_id = str(
            financial_identity("configuration", str(config.configuration_revision_id))
        )
        self._append_event(
            connection,
            event_id=event_id,
            event_type="CONFIGURATION",
            payload=_canonical_json(_encode(config)),
        )

    def _reconstruct(self, connection: sqlite3.Connection) -> _ReconstructedState:
        with localcontext(_ARITHMETIC_CONTEXT):
            return self._reconstruct_under_context(connection)

    def _reconstruct_under_context(
        self, connection: sqlite3.Connection
    ) -> _ReconstructedState:
        try:
            rows = connection.execute(
                "SELECT seq,event_id,event_type,payload,previous_hash,event_hash "
                "FROM chain_events ORDER BY seq"
            ).fetchall()
            if not rows:
                return _ReconstructedState.empty(
                    self._account_id,
                    self._source_lane,
                    self._config.policy.starting_cash,
                )
            previous = _ZERO_HASH
            configs: dict[UUID, str] = {}
            config_objects: dict[UUID, PaperEvaluationConfig] = {}
            cycle_results: dict[UUID, PaperCycleResult] = {}
            account_id: UUID | None = None
            source_lane: str | None = None
            starting_cash: Decimal | None = None
            control: PaperControlState | None = None
            ledger: PaperLedger | None = None
            latest_result: PaperCycleResult | None = None
            cursor_by_symbol: dict[Symbol, int] = {}
            sessions_by_symbol: dict[Symbol, set[str]] = {}
            seen_effects: dict[str, tuple[str, str, str]] = {}
            expected_slots: set[tuple[str, str, str, str, str, str]] = set()
            last_cycle_sequence = 0
            for expected_seq, row in enumerate(rows, start=1):
                seq, event_id, event_type, payload_text, previous_hash, event_hash = row
                if seq != expected_seq or previous_hash != previous:
                    raise PaperEvaluationStoreCorruptionError(
                        "PAPER_FINANCIAL_CHAIN_ORDER_INVALID"
                    )
                expected_hash = _event_hash(
                    seq, event_id, event_type, payload_text, previous_hash
                )
                if expected_hash != event_hash:
                    raise PaperEvaluationStoreCorruptionError(
                        "PAPER_FINANCIAL_CHAIN_HASH_INVALID"
                    )
                payload = json.loads(payload_text)
                if not isinstance(payload, dict):
                    raise PaperEvaluationStoreCorruptionError(
                        "PAPER_FINANCIAL_EVENT_PAYLOAD_INVALID"
                    )
                previous = event_hash
                if event_type == "ACCOUNT_OPENED":
                    if account_id is not None or seq != 1:
                        raise PaperEvaluationStoreCorruptionError(
                            "PAPER_ACCOUNT_OPEN_EVENT_INVALID"
                        )
                    account_id = UUID(payload["account_id"])
                    source_lane = payload["source_lane"]
                    if event_id != str(
                        financial_identity(
                            "account-opened", f"{account_id}|{source_lane}"
                        )
                    ):
                        raise PaperEvaluationStoreCorruptionError(
                            "PAPER_ACCOUNT_OPEN_ID_INVALID"
                        )
                    starting_cash = _decode(payload["starting_cash"])
                    if not isinstance(starting_cash, Decimal) or starting_cash <= 0:
                        raise PaperEvaluationStoreCorruptionError(
                            "PAPER_STARTING_CASH_INVALID"
                        )
                    ledger = PaperLedger(starting_cash)
                elif event_type == "CONFIGURATION":
                    if account_id is None:
                        raise PaperEvaluationStoreCorruptionError(
                            "PAPER_CONFIG_BEFORE_ACCOUNT"
                        )
                    if not configs and seq != 2:
                        raise PaperEvaluationStoreCorruptionError(
                            "PAPER_INITIAL_CONFIGURATION_ORDER_INVALID"
                        )
                    config = _decode(payload)
                    if type(config) is not PaperEvaluationConfig:
                        raise PaperEvaluationStoreCorruptionError(
                            "PAPER_CONFIGURATION_EVENT_INVALID"
                        )
                    revision = config.configuration_revision_id
                    if event_id != str(
                        financial_identity("configuration", str(revision))
                    ):
                        raise PaperEvaluationStoreCorruptionError(
                            "PAPER_CONFIGURATION_EVENT_ID_INVALID"
                        )
                    serialized = _canonical_json(_encode(config))
                    if revision in configs:
                        raise PaperEvaluationStoreCorruptionError(
                            "PAPER_CONFIGURATION_REVISION_DUPLICATED"
                        )
                    configs[revision] = serialized
                    config_objects[revision] = config
                elif event_type == "CONTROL":
                    decoded_control = _decode(payload)
                    if type(decoded_control) is not PaperControlState:
                        raise PaperEvaluationStoreCorruptionError(
                            "PAPER_CONTROL_EVENT_INVALID"
                        )
                    if control is None:
                        if seq != 3 or decoded_control != PaperControlState(
                            0, False, True
                        ):
                            raise PaperEvaluationStoreCorruptionError(
                                "PAPER_INITIAL_CONTROL_INVALID"
                            )
                    elif decoded_control.version != control.version + 1:
                        raise PaperEvaluationStoreCorruptionError(
                            "PAPER_CONTROL_VERSION_INVALID"
                        )
                    if event_id != str(
                        financial_identity(
                            "control",
                            f"{self._account_id}|{self._source_lane}|{decoded_control.version}",
                        )
                    ):
                        raise PaperEvaluationStoreCorruptionError(
                            "PAPER_CONTROL_EVENT_ID_INVALID"
                        )
                    control = decoded_control
                elif event_type == "CYCLE":
                    if (
                        ledger is None
                        or control is None
                        or account_id is None
                        or not configs
                    ):
                        raise PaperEvaluationStoreCorruptionError(
                            "PAPER_CYCLE_BEFORE_INITIAL_STATE"
                        )
                    input_material = payload.get("input_material")
                    result_data = payload.get("result")
                    result = _decode(result_data)
                    if type(result) is not PaperCycleResult:
                        raise PaperEvaluationStoreCorruptionError(
                            "PAPER_CYCLE_RESULT_INVALID"
                        )
                    if result.cycle_id != UUID(event_id):
                        raise PaperEvaluationStoreCorruptionError(
                            "PAPER_CYCLE_ID_INVALID"
                        )
                    revision = result.configuration_revision_id
                    config = config_objects.get(revision)
                    if config is None or result.control != control:
                        raise PaperEvaluationStoreCorruptionError(
                            "PAPER_CYCLE_CONFIGURATION_OR_CONTROL_INVALID"
                        )
                    if result.input.symbol != config.binding.symbol:
                        raise PaperEvaluationStoreCorruptionError(
                            "PAPER_CYCLE_SYMBOL_BINDING_INVALID"
                        )
                    expected_cycle_id = cycle_identity(
                        account_id,
                        source_lane or "",
                        result.input.symbol.value,
                        result.input.execution_session_id,
                    )
                    if result.cycle_id != expected_cycle_id:
                        raise PaperEvaluationStoreCorruptionError(
                            "PAPER_CYCLE_SLOT_ID_INVALID"
                        )
                    if event_id != str(expected_cycle_id):
                        raise PaperEvaluationStoreCorruptionError(
                            "PAPER_CYCLE_EVENT_ID_INVALID"
                        )
                    symbol = result.input.symbol
                    previous_index = cursor_by_symbol.get(symbol, 0)
                    if result.input.execution_index != previous_index + 1:
                        raise PaperEvaluationStoreCorruptionError(
                            "PAPER_CYCLE_CURSOR_INVALID"
                        )
                    sessions = sessions_by_symbol.setdefault(symbol, set())
                    if result.input.execution_session_id in sessions:
                        raise PaperEvaluationStoreCorruptionError(
                            "PAPER_CYCLE_SESSION_DUPLICATED"
                        )
                    if control.kill_latched:
                        raise PaperEvaluationStoreCorruptionError(
                            "PAPER_CYCLE_COMMITTED_WHILE_KILL_LATCHED"
                        )
                    engine = PaperCycleEngine(
                        account_id=account_id,
                        source_lane=source_lane or "",
                        policy=config.policy,
                        configuration_revision_id=revision,
                    )
                    expected_result = engine.process(result.input, ledger, control)
                    if _canonical_json(
                        _encode_result(expected_result, omit_account_fills=True)
                    ) != _canonical_json(
                        _encode_result(result, omit_account_fills=True)
                    ):
                        raise PaperEvaluationStoreCorruptionError(
                            "PAPER_FINANCIAL_CYCLE_REPLAY_MISMATCH"
                        )
                    expected_input_material = _canonical_json(
                        {
                            "configuration_revision_id": str(revision),
                            "input": self._cycle_input_material(result.input),
                        }
                    )
                    if input_material != expected_input_material:
                        raise PaperEvaluationStoreCorruptionError(
                            "PAPER_CYCLE_INPUT_COMMITMENT_INVALID"
                        )
                    slot = connection.execute(
                        "SELECT account_id,source_lane,symbol,session_id,"
                        "cycle_id,event_id "
                        "FROM cycle_slots WHERE event_id=?",
                        (event_id,),
                    ).fetchone()
                    expected_slot = (
                        str(account_id),
                        source_lane,
                        symbol.value,
                        result.input.execution_session_id,
                        str(result.cycle_id),
                        event_id,
                    )
                    if slot != expected_slot:
                        raise PaperEvaluationStoreCorruptionError(
                            "PAPER_CYCLE_SLOT_INDEX_INVALID"
                        )
                    for kind, identity in _effect_identities(result):
                        if identity in seen_effects:
                            raise PaperEvaluationStoreCorruptionError(
                                "PAPER_DUPLICATE_FINANCIAL_IDENTITY"
                            )
                        seen_effects[identity] = (
                            kind,
                            str(result.cycle_id),
                            event_id,
                        )
                    expected_slots.add(expected_slot)
                    sessions.add(result.input.execution_session_id)
                    cursor_by_symbol[symbol] = result.input.execution_index
                    latest_result = expected_result
                    cycle_results[result.cycle_id] = expected_result
                    last_cycle_sequence = seq
                elif event_type == "CONFLICT":
                    pass
                else:
                    raise PaperEvaluationStoreCorruptionError(
                        "PAPER_FINANCIAL_EVENT_TYPE_UNKNOWN"
                    )
            if (
                account_id is None
                or source_lane is None
                or ledger is None
                or control is None
            ):
                raise PaperEvaluationStoreCorruptionError(
                    "PAPER_FINANCIAL_CHAIN_INCOMPLETE"
                )
            if (
                account_id != self._account_id
                or source_lane != self._source_lane
                or self._config.configuration_revision_id not in configs
                or not configs
            ):
                raise PaperEvaluationStoreCorruptionError(
                    "PAPER_ACCOUNT_OR_CONFIGURATION_MISMATCH"
                )
            self._verify_effect_identity_index(connection, seen_effects)
            actual_slots = set(
                connection.execute(
                    "SELECT account_id,source_lane,symbol,session_id,cycle_id,event_id "
                    "FROM cycle_slots"
                ).fetchall()
            )
            if actual_slots != expected_slots:
                raise PaperEvaluationStoreCorruptionError(
                    "PAPER_CYCLE_SLOT_INDEX_INVALID"
                )
            for symbol, index in cursor_by_symbol.items():
                if latest_result is not None and symbol == latest_result.input.symbol:
                    continue
                if index < 0:
                    raise PaperEvaluationStoreCorruptionError(
                        "PAPER_CYCLE_CURSOR_INVALID"
                    )
            account = _state_from_ledger(
                ledger,
                latest_result.input if latest_result else None,
            )
            return _ReconstructedState(
                account_id=account_id,
                source_lane=source_lane,
                starting_cash=starting_cash or Decimal("0"),
                ledger=ledger,
                account=account,
                control=control,
                configs=configs,
                config_objects=config_objects,
                cursor_index=(latest_result.cursor_index if latest_result else 0),
                execution_session_id=(
                    latest_result.input.execution_session_id if latest_result else None
                ),
                latest_result=latest_result,
                cursor_by_symbol=cursor_by_symbol,
                last_cycle_sequence=last_cycle_sequence,
                cycle_results=cycle_results,
            )
        except PaperEvaluationStoreError:
            raise
        except (
            sqlite3.DatabaseError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            raise PaperEvaluationStoreCorruptionError(
                "PAPER_FINANCIAL_RECONSTRUCTION_FAILED"
            ) from error

    def _verify_effect_identity_index(
        self,
        connection: sqlite3.Connection,
        expected: Mapping[str, tuple[str, str, str]],
    ) -> None:
        rows = connection.execute(
            "SELECT identity,kind,cycle_id,event_id "
            "FROM effect_identities ORDER BY identity"
        ).fetchall()
        actual = {
            identity: (kind, cycle_id, event_id)
            for identity, kind, cycle_id, event_id in rows
        }
        if actual != dict(expected):
            raise PaperEvaluationStoreCorruptionError(
                "PAPER_FINANCIAL_IDENTITY_INDEX_INVALID"
            )

    def _snapshot(self, state: _ReconstructedState) -> PaperStoreSnapshot:
        return PaperStoreSnapshot(
            account_id=state.account_id,
            configuration_revision_id=self._config.configuration_revision_id,
            account=state.account,
            cursor_index=state.cursor_index,
            execution_session_id=state.execution_session_id,
            control=state.control,
            latest_result=state.latest_result,
        )

    def _find_slot(
        self,
        connection: sqlite3.Connection,
        cycle: PaperCycleInput,
        state: _ReconstructedState,
    ) -> tuple[PaperCycleResult, str] | None:
        row = connection.execute(
            "SELECT event_id FROM cycle_slots WHERE account_id=? AND source_lane=? "
            "AND symbol=? AND session_id=?",
            (
                str(self._account_id),
                self._source_lane,
                cycle.symbol.value,
                cycle.execution_session_id,
            ),
        ).fetchone()
        if row is None:
            return None
        event = connection.execute(
            "SELECT payload FROM chain_events WHERE event_id=? AND event_type='CYCLE'",
            (row[0],),
        ).fetchone()
        if event is None:
            raise PaperEvaluationStoreCorruptionError("PAPER_SLOT_EVENT_MISSING")
        payload = json.loads(event[0])
        result = _decode(payload["result"])
        if type(result) is not PaperCycleResult:
            raise PaperEvaluationStoreCorruptionError("PAPER_CYCLE_RESULT_INVALID")
        result = state.cycle_results.get(result.cycle_id, result)
        return result, payload["input_material"]

    def _cycle_input_material(self, cycle: PaperCycleInput) -> dict[str, object]:
        proposal = cycle.proposal
        proposal_material: object = None
        if proposal is not None:
            proposal_material = {
                "symbol": proposal.symbol.value,
                "side": proposal.side.value,
                "desired_quantity": _encode(proposal.desired_quantity),
                "created_at": _encode(proposal.created_at),
                "reason": proposal.reason,
                "confidence": _encode(proposal.confidence),
            }
        return {
            "execution_session_id": cycle.execution_session_id,
            "execution_index": cycle.execution_index,
            "symbol": cycle.symbol.value,
            "observation_id": str(cycle.observation_id),
            "completed_history_cutoff": cycle.completed_history_cutoff,
            "observation_open": _encode(cycle.observation_open),
            "executed_at": _encode(cycle.executed_at),
            "proposal": proposal_material,
            "no_signal_reason": cycle.no_signal_reason,
            "warmup": cycle.warmup,
            "current_marks": [
                [symbol.value, _encode(price)]
                for symbol, price in (cycle.current_marks or {}).items()
            ],
        }

    def _record_effect_identities(
        self, connection: sqlite3.Connection, result: PaperCycleResult
    ) -> None:
        for kind, identity in _effect_identities(result):
            connection.execute(
                "INSERT INTO effect_identities(identity,kind,cycle_id,event_id) "
                "VALUES(?,?,?,?)",
                (identity, kind, str(result.cycle_id), str(result.cycle_id)),
            )

    def _append_diagnostic(
        self, connection: sqlite3.Connection, code: str, payload: dict[str, object]
    ) -> None:
        serialized = _canonical_json({"code": code, "details": payload})
        next_seq = self._last_sequence(connection) + 1
        event_id = str(
            financial_identity(
                "diagnostic",
                f"{next_seq}|{code}|{hashlib.sha256(serialized.encode()).hexdigest()}",
            )
        )
        self._append_event(
            connection,
            event_id=event_id,
            event_type="CONFLICT",
            payload=serialized,
        )

    def _record_conflict_after_rollback(
        self, code: str, payload: dict[str, object]
    ) -> None:
        with closing(self._connection()) as connection:
            self._begin(connection)
            self._append_diagnostic(connection, code, payload)
            connection.commit()

    def _append_event(
        self,
        connection: sqlite3.Connection,
        *,
        event_id: str,
        event_type: str,
        payload: str,
    ) -> None:
        previous_row = connection.execute(
            "SELECT seq,event_hash FROM chain_events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        seq = 1 if previous_row is None else previous_row[0] + 1
        previous_hash = _ZERO_HASH if previous_row is None else previous_row[1]
        event_hash = _event_hash(seq, event_id, event_type, payload, previous_hash)
        try:
            connection.execute(
                "INSERT INTO chain_events"
                "(seq,event_id,event_type,payload,previous_hash,event_hash) "
                "VALUES(?,?,?,?,?,?)",
                (seq, event_id, event_type, payload, previous_hash, event_hash),
            )
        except sqlite3.IntegrityError as error:
            raise PaperEvaluationStoreConflictError(
                "DUPLICATE_EVENT_IDENTITY"
            ) from error

    @staticmethod
    def _last_sequence(connection: sqlite3.Connection) -> int:
        row = connection.execute(
            "SELECT seq FROM chain_events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return 0 if row is None else int(row[0])

    def _call_hook(self, stage: str) -> None:
        if self._fault_hook is not None:
            self._fault_hook(stage)


class _ReconstructedState:
    __slots__ = (
        "account_id",
        "source_lane",
        "starting_cash",
        "ledger",
        "account",
        "control",
        "configs",
        "config_objects",
        "cursor_index",
        "execution_session_id",
        "latest_result",
        "cursor_by_symbol",
        "last_cycle_sequence",
        "cycle_results",
    )

    def __init__(
        self,
        *,
        account_id: UUID,
        source_lane: str,
        starting_cash: Decimal,
        ledger: PaperLedger,
        account: PaperAccountState,
        control: PaperControlState,
        configs: dict[UUID, str],
        config_objects: dict[UUID, PaperEvaluationConfig],
        cursor_index: int,
        execution_session_id: str | None,
        latest_result: PaperCycleResult | None,
        cursor_by_symbol: dict[Symbol, int],
        last_cycle_sequence: int,
        cycle_results: dict[UUID, PaperCycleResult],
    ) -> None:
        self.account_id = account_id
        self.source_lane = source_lane
        self.starting_cash = starting_cash
        self.ledger = ledger
        self.account = account
        self.control = control
        self.configs = configs
        self.config_objects = config_objects
        self.cursor_index = cursor_index
        self.execution_session_id = execution_session_id
        self.latest_result = latest_result
        self.cursor_by_symbol = cursor_by_symbol
        self.last_cycle_sequence = last_cycle_sequence
        self.cycle_results = cycle_results

    @classmethod
    def empty(
        cls, account_id: UUID, source_lane: str, starting_cash: Decimal
    ) -> _ReconstructedState:
        ledger = PaperLedger(starting_cash)
        account = PaperAccountState(
            cash=ledger.cash,
            positions=ledger.positions,
            realized_profit_loss=ledger.realized_profit_loss,
            marked_equity=ledger.cash,
            unrealized_profit_loss=Decimal("0"),
        )
        return cls(
            account_id=account_id,
            source_lane=source_lane,
            starting_cash=starting_cash,
            ledger=ledger,
            account=account,
            control=PaperControlState(0, False, True),
            configs={},
            config_objects={},
            cursor_index=0,
            execution_session_id=None,
            latest_result=None,
            cursor_by_symbol={},
            last_cycle_sequence=0,
            cycle_results={},
        )


def _state_from_ledger(
    ledger: PaperLedger, latest_input: PaperCycleInput | None
) -> PaperAccountState:
    positions = ledger.positions
    marks = dict(latest_input.current_marks or {}) if latest_input is not None else {}
    if latest_input is None and positions:
        marked_equity = unrealized = None
    elif all(symbol in marks for symbol in positions):
        as_of = (
            latest_input.executed_at
            if latest_input is not None
            else datetime.min.replace(tzinfo=UTC)
        )
        snapshot = ledger.create_account_snapshot(marks, as_of)
        marked_equity = snapshot.equity
        unrealized = snapshot.unrealized_profit_loss
    else:
        marked_equity = unrealized = None
    return PaperAccountState(
        cash=ledger.cash,
        positions=positions,
        realized_profit_loss=ledger.realized_profit_loss,
        marked_equity=marked_equity,
        unrealized_profit_loss=unrealized,
        fills=ledger.fills,
    )


def _event_hash(
    seq: int, event_id: str, event_type: str, payload: str, previous_hash: str
) -> str:
    material = (
        f"desktop-paper-chain/v1|{seq}|{event_id}|{event_type}|"
        f"{previous_hash}|{payload}"
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _normalized_sql(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().rstrip(";").upper()


def _encode(value: object) -> object:
    if value is None or type(value) in (str, bool, int):
        return value
    if isinstance(value, Decimal):
        return {"$decimal": _canonical_decimal(value)}
    if isinstance(value, UUID):
        return {"$uuid": str(value)}
    if isinstance(value, datetime):
        return {"$datetime": value.isoformat()}
    if isinstance(value, Enum):
        return {"$enum": type(value).__name__, "value": value.value}
    if isinstance(value, Symbol):
        return {"$symbol": value.value}
    if isinstance(value, Mapping):
        return {
            "$mapping": [[_encode(key), _encode(item)] for key, item in value.items()]
        }
    if isinstance(value, (tuple, list)):
        return [_encode(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return {
            "$type": type(value).__name__,
            "fields": {
                field.name: _encode(getattr(value, field.name))
                for field in fields(value)
            },
        }
    raise TypeError(f"unsupported paper-store value: {type(value).__name__}")


def _decode(value: object) -> object:
    if isinstance(value, list):
        return tuple(_decode(item) for item in value)
    if not isinstance(value, dict):
        return value
    if "$decimal" in value:
        return Decimal(value["$decimal"])
    if "$uuid" in value:
        return UUID(value["$uuid"])
    if "$datetime" in value:
        return datetime.fromisoformat(value["$datetime"])
    if "$symbol" in value:
        return Symbol(value["$symbol"])
    if "$mapping" in value:
        return {_decode(key): _decode(item) for key, item in value["$mapping"]}
    if "$enum" in value:
        enum_type = _enum_type(value["$enum"])
        return enum_type(value["value"])
    if "$type" in value:
        cls = _model_type(value["$type"])
        decoded = {name: _decode(item) for name, item in value["fields"].items()}
        return cls(**decoded)
    return {name: _decode(item) for name, item in value.items()}


def _enum_type(name: str) -> type[Enum]:
    enums: dict[str, type[Enum]] = {
        type_.__name__: type_
        for type_ in (
            OrderSide,
            OrderStatus,
            OrderType,
            TimeInForce,
            OrderEventType,
            RiskOutcome,
            RiskReasonCode,
            PaperCycleKind,
        )
    }
    try:
        return enums[name]
    except KeyError as error:
        raise ValueError("unknown paper-store enum") from error


def _model_type(name: str) -> type[Any]:
    from trading_bot.desktop_paper.configuration import (
        PaperStrategyBinding,
    )

    models: dict[str, type[Any]] = {
        type_.__name__: type_
        for type_ in (
            PaperRuntimePolicy,
            PaperEvaluationConfig,
            PaperStrategyBinding,
            PaperAccountState,
            PaperControlState,
            PaperCycleInput,
            PaperCycleResult,
            PaperStoreSnapshot,
            Position,
            TradeProposal,
            RiskContext,
            RiskDecision,
            RiskReason,
            Order,
            OrderRequest,
            OrderFill,
            OrderEvent,
        )
    }
    try:
        return models[name]
    except KeyError as error:
        raise ValueError("unknown paper-store model") from error


def _encode_result(result: PaperCycleResult, *, omit_account_fills: bool) -> object:
    if not omit_account_fills:
        return _encode(result)
    return _encode(replace(result, account=replace(result.account, fills=())))


def _effect_identities(result: PaperCycleResult) -> tuple[tuple[str, str], ...]:
    identities: list[tuple[str, str]] = [("cycle", str(result.cycle_id))]
    if result.risk_decision is not None:
        identities.append(("proposal", str(result.risk_decision.proposal.proposal_id)))
    if result.order is not None:
        identities.append(("order", str(result.order.request.order_id)))
    if result.fill is not None:
        identities.append(("fill", str(result.fill.fill_id)))
    identities.extend(("event", str(event.event_id)) for event in result.order_events)
    return tuple(identities)


def _canonical_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("financial decimals must be finite")
    sign, digits, exponent = value.as_tuple()
    digits = list(digits)
    if not any(digits):
        return "0"
    while digits and digits[-1] == 0:
        digits.pop()
        exponent += 1
    raw = "".join(str(digit) for digit in digits)
    if exponent >= 0:
        rendered = raw + ("0" * exponent)
    else:
        decimal_point = len(raw) + exponent
        rendered = (
            f"{raw[:decimal_point]}.{raw[decimal_point:]}"
            if decimal_point > 0
            else f"0.{('0' * -decimal_point)}{raw}"
        )
    return f"-{rendered}" if sign else rendered
