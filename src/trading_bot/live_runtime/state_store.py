"""Opt-in durable SQLite CAS store for Architecture 148 runtime state.

The store is create-once and never provisions itself during worker startup.
State is canonical typed JSON inside SQLite transactions; pickle is not used.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from trading_bot.domain import OrderSide, Symbol

from .identity import canonical_decimal
from .models import (
    AdmissionBlocker,
    ApprovalRequiredReceipt,
    BrokerOrderFact,
    BrokerReviewFacts,
    IntentKind,
    IntentLifecycle,
    LogicalOrderIntent,
    OrderState,
    OwnedPositionRecord,
    PendingExit,
    ReviewStatus,
    RuntimeState,
    RuntimeStateStore,
    SourceIdentity,
)
from .order_tracker import (
    OrderWriteAction,
    OrderWriteReservation,
    OrderWriteStatus,
    TrackedOrder,
    _fact_progresses,
)

_SCHEMA = "arch148-runtime-state/sqlite-v3"
_STATE_COLUMNS = (
    "singleton",
    "owner_id",
    "source_head",
    "source_tree",
    "account_fingerprint",
    "session_fingerprint",
    "revision",
    "state_json",
    "state_sha256",
)


class RuntimeStateStoreError(RuntimeError):
    """Durable state could not be safely loaded or advanced."""


class RuntimeStateStoreUnavailable(RuntimeStateStoreError):
    """The durable state backend is unavailable."""


class RuntimeStateStoreCorrupt(RuntimeStateStoreError):
    """The durable state is missing, malformed, or inconsistent."""


class RuntimeStateStoreIdentityError(RuntimeStateStoreError):
    """The durable state belongs to another owner or runtime identity."""


class SQLiteRuntimeStateStore(RuntimeStateStore):
    """Single-row SQLite state with cross-instance transactional revision CAS."""

    def __init__(
        self,
        path: Path,
        *,
        owner_id: UUID,
        source_identity: SourceIdentity,
        account_fingerprint: str,
        session_fingerprint: str,
    ) -> None:
        self.path = path
        self.owner_id = owner_id
        self.source_identity = source_identity
        self.account_fingerprint = account_fingerprint
        self.session_fingerprint = session_fingerprint

    @classmethod
    def create(cls, path: Path, initial_state: RuntimeState) -> SQLiteRuntimeStateStore:
        """Create one new file and persist an explicitly supplied initial state."""

        _validate_path(path, must_exist=False)
        if not isinstance(initial_state, RuntimeState):
            raise TypeError("initial_state must be RuntimeState")
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        except FileExistsError:
            raise RuntimeStateStoreIdentityError(
                "runtime state already exists"
            ) from None
        except OSError:
            raise RuntimeStateStoreUnavailable(
                "runtime state file could not be created"
            ) from None
        else:
            os.close(descriptor)
        store = cls(
            path,
            owner_id=initial_state.owner_id,
            source_identity=initial_state.source_identity,
            account_fingerprint=initial_state.account_fingerprint,
            session_fingerprint=initial_state.session_fingerprint,
        )
        try:
            connection = sqlite3.connect(path, timeout=5.0, isolation_level=None)
            try:
                connection.execute("PRAGMA synchronous = FULL")
                connection.execute("PRAGMA foreign_keys = ON")
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "CREATE TABLE state_meta ("
                    "singleton INTEGER PRIMARY KEY CHECK(singleton = 1), "
                    "schema TEXT NOT NULL)"
                )
                connection.execute(
                    "INSERT INTO state_meta(singleton, schema) VALUES(1, ?)",
                    (_SCHEMA,),
                )
                connection.execute(
                    "CREATE TABLE runtime_state ("
                    "singleton INTEGER PRIMARY KEY CHECK(singleton = 1), "
                    "owner_id TEXT NOT NULL, source_head TEXT NOT NULL, "
                    "source_tree TEXT NOT NULL, account_fingerprint TEXT NOT NULL, "
                    "session_fingerprint TEXT NOT NULL, revision INTEGER NOT NULL, "
                    "state_json TEXT NOT NULL, state_sha256 TEXT NOT NULL)"
                )
                state_json = _canonical_json(_encode_state(initial_state))
                connection.execute(
                    "INSERT INTO runtime_state VALUES(1, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(initial_state.owner_id),
                        initial_state.source_identity.head,
                        initial_state.source_identity.tree,
                        initial_state.account_fingerprint,
                        initial_state.session_fingerprint,
                        initial_state.revision,
                        state_json,
                        _sha256(state_json),
                    ),
                )
                connection.execute("COMMIT")
            except Exception:
                _rollback(connection)
                raise
            finally:
                connection.close()
        except RuntimeStateStoreError:
            raise
        except Exception:
            raise RuntimeStateStoreUnavailable(
                "runtime state initialization failed; partial file is preserved"
            ) from None
        return store

    @classmethod
    def open(
        cls,
        path: Path,
        *,
        owner_id: UUID,
        source_identity: SourceIdentity,
        account_fingerprint: str,
        session_fingerprint: str,
    ) -> SQLiteRuntimeStateStore:
        """Open existing state under explicit expected owner/source/account/session."""

        _validate_path(path, must_exist=True)
        store = cls(
            path,
            owner_id=owner_id,
            source_identity=source_identity,
            account_fingerprint=account_fingerprint,
            session_fingerprint=session_fingerprint,
        )
        initial = store._read_state()
        _assert_pinned(
            initial,
            owner_id,
            source_identity,
            account_fingerprint,
            session_fingerprint,
        )
        return store

    def load(self, owner_id: UUID, source_identity: SourceIdentity) -> RuntimeState:
        if owner_id != self.owner_id or source_identity != self.source_identity:
            raise RuntimeStateStoreIdentityError("runtime state owner/source mismatch")
        state = self._read_state()
        _assert_pinned(
            state,
            self.owner_id,
            self.source_identity,
            self.account_fingerprint,
            self.session_fingerprint,
        )
        return state

    def compare_and_swap(
        self, expected_revision: int, next_state: RuntimeState
    ) -> bool:
        """Commit exactly one state revision, or return False on a stale revision."""

        if not isinstance(next_state, RuntimeState):
            return False
        if (
            not isinstance(expected_revision, int)
            or isinstance(expected_revision, bool)
            or expected_revision < 0
            or next_state.revision != expected_revision + 1
        ):
            return False
        try:
            _assert_pinned(
                next_state,
                self.owner_id,
                self.source_identity,
                self.account_fingerprint,
                self.session_fingerprint,
            )
            connection = self._connect()
        except RuntimeStateStoreError:
            raise
        except Exception:
            raise RuntimeStateStoreUnavailable(
                "runtime state database is unavailable"
            ) from None
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = _read_from_connection(connection)
            if current.revision != expected_revision:
                connection.execute("ROLLBACK")
                return False
            if not _transition_is_monotone(current, next_state):
                connection.execute("ROLLBACK")
                return False
            state_json = _canonical_json(_encode_state(next_state))
            cursor = connection.execute(
                "UPDATE runtime_state SET revision = ?, "
                "state_json = ?, state_sha256 = ? "
                "WHERE singleton = 1 AND revision = ?",
                (
                    next_state.revision,
                    state_json,
                    _sha256(state_json),
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                connection.execute("ROLLBACK")
                return False
            connection.execute("COMMIT")
            return True
        except RuntimeStateStoreError:
            _rollback(connection)
            raise
        except Exception:
            _rollback(connection)
            raise RuntimeStateStoreUnavailable("runtime state CAS failed") from None
        finally:
            connection.close()

    def _read_state(self) -> RuntimeState:
        try:
            connection = self._connect()
        except RuntimeStateStoreError:
            raise
        except Exception:
            raise RuntimeStateStoreUnavailable(
                "runtime state database is unavailable"
            ) from None
        try:
            return _read_from_connection(connection)
        except RuntimeStateStoreError:
            raise
        except Exception:
            raise RuntimeStateStoreCorrupt(
                "runtime state could not be decoded"
            ) from None
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        _validate_path(self.path, must_exist=True)
        try:
            uri = self.path.resolve().as_uri() + "?mode=rw"
            connection = sqlite3.connect(
                uri,
                uri=True,
                timeout=5.0,
                isolation_level=None,
            )
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA synchronous = FULL")
            return connection
        except Exception:
            raise RuntimeStateStoreUnavailable(
                "runtime state database is unavailable"
            ) from None


def _validate_path(path: Path, *, must_exist: bool) -> None:
    if not isinstance(path, Path):
        raise TypeError("path must be pathlib.Path")
    if must_exist:
        if not path.is_file():
            raise RuntimeStateStoreUnavailable("runtime state file is unavailable")
    elif path.exists():
        raise RuntimeStateStoreIdentityError("runtime state already exists")
    if not must_exist and not path.parent.is_dir():
        raise RuntimeStateStoreUnavailable(
            "runtime state parent directory is unavailable"
        )


def _read_from_connection(connection: sqlite3.Connection) -> RuntimeState:
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity != ("ok",):
            raise RuntimeStateStoreCorrupt("runtime state database integrity failed")
        meta = connection.execute("SELECT singleton, schema FROM state_meta").fetchall()
        if meta != [(1, _SCHEMA)]:
            raise RuntimeStateStoreCorrupt("runtime state schema is unsupported")
        columns = tuple(
            row[1] for row in connection.execute("PRAGMA table_info(runtime_state)")
        )
        if columns != _STATE_COLUMNS:
            raise RuntimeStateStoreCorrupt("runtime state table shape differs")
        rows = connection.execute(
            "SELECT singleton, owner_id, source_head, source_tree, "
            "account_fingerprint, session_fingerprint, revision, state_json, "
            "state_sha256 "
            "FROM runtime_state"
        ).fetchall()
        if len(rows) != 1 or rows[0][0] != 1:
            raise RuntimeStateStoreCorrupt("runtime state row is missing or duplicated")
        (
            _,
            owner_id,
            source_head,
            source_tree,
            account,
            session,
            revision,
            payload,
            digest,
        ) = rows[0]
        if not all(
            isinstance(value, str)
            for value in (
                owner_id,
                source_head,
                source_tree,
                account,
                session,
                payload,
                digest,
            )
        ):
            raise RuntimeStateStoreCorrupt("runtime state row has invalid column types")
        if type(revision) is not int or digest != _sha256(payload):
            raise RuntimeStateStoreCorrupt("runtime state digest or revision differs")
        raw = json.loads(payload, object_pairs_hook=_reject_duplicate_keys)
        state = _decode_state(raw)
        if _canonical_json(_encode_state(state)) != payload:
            raise RuntimeStateStoreCorrupt("runtime state JSON is not canonical")
        if (
            str(state.owner_id) != owner_id
            or state.source_identity.head != source_head
            or state.source_identity.tree != source_tree
            or state.account_fingerprint != account
            or state.session_fingerprint != session
            or state.revision != revision
        ):
            raise RuntimeStateStoreCorrupt("runtime state columns differ from payload")
        return state
    except RuntimeStateStoreError:
        raise
    except Exception:
        raise RuntimeStateStoreCorrupt("runtime state database is malformed") from None


def _assert_pinned(
    state: RuntimeState,
    owner_id: UUID,
    source_identity: SourceIdentity,
    account_fingerprint: str,
    session_fingerprint: str,
) -> None:
    if (
        state.owner_id != owner_id
        or state.source_identity != source_identity
        or state.account_fingerprint != account_fingerprint
        or state.session_fingerprint != session_fingerprint
    ):
        raise RuntimeStateStoreIdentityError("runtime state identity differs")


def _transition_is_monotone(current: RuntimeState, next_state: RuntimeState) -> bool:
    if (
        current.owner_id != next_state.owner_id
        or current.source_identity != next_state.source_identity
        or current.account_fingerprint != next_state.account_fingerprint
        or current.session_fingerprint != next_state.session_fingerprint
        or current.revision + 1 != next_state.revision
        or current.next_sequence > next_state.next_sequence
    ):
        return False
    next_intents = {item.intent_id: item for item in next_state.intents}
    current_intent_ids = {item.intent_id for item in current.intents}
    if any(item.intent_id not in next_intents for item in current.intents):
        return False
    intent_transitions = {
        IntentLifecycle.PROPOSED: {
            IntentLifecycle.PROPOSED,
            IntentLifecycle.SUPERSEDED,
            IntentLifecycle.APPROVAL_REQUIRED,
            IntentLifecycle.MAY_HAVE_OCCURRED,
        },
        IntentLifecycle.APPROVAL_REQUIRED: {
            IntentLifecycle.APPROVAL_REQUIRED,
            IntentLifecycle.MAY_HAVE_OCCURRED,
            IntentLifecycle.UNKNOWN,
            IntentLifecycle.REJECTED,
        },
        IntentLifecycle.MAY_HAVE_OCCURRED: {
            IntentLifecycle.MAY_HAVE_OCCURRED,
            IntentLifecycle.APPROVAL_REQUIRED,
            IntentLifecycle.UNKNOWN,
            IntentLifecycle.RECONCILED,
            IntentLifecycle.REJECTED,
        },
        IntentLifecycle.UNKNOWN: {
            IntentLifecycle.UNKNOWN,
            IntentLifecycle.APPROVAL_REQUIRED,
            IntentLifecycle.RECONCILED,
            IntentLifecycle.REJECTED,
        },
        IntentLifecycle.RECONCILED: {IntentLifecycle.RECONCILED},
        IntentLifecycle.REJECTED: {IntentLifecycle.REJECTED},
        IntentLifecycle.SUPERSEDED: {IntentLifecycle.SUPERSEDED},
    }
    for old in current.intents:
        new = next_intents[old.intent_id]
        if (
            old.ref_id != new.ref_id
            or old.terms_digest != new.terms_digest
            or old.owner_id != new.owner_id
            or old.source_identity != new.source_identity
            or old.kind is not new.kind
            or old.symbol != new.symbol
            or old.side is not new.side
            or old.quantity != new.quantity
            or old.stop_price != new.stop_price
            or old.created_at != new.created_at
            or new.lifecycle not in intent_transitions[old.lifecycle]
        ):
            return False
    old_reservations = {item.operation_id: item for item in current.write_reservations}
    next_reservations = {
        item.operation_id: item for item in next_state.write_reservations
    }
    if not old_reservations.keys() <= next_reservations.keys():
        return False
    status_transitions = {
        OrderWriteStatus.MAY_HAVE_OCCURRED: {
            OrderWriteStatus.MAY_HAVE_OCCURRED,
            OrderWriteStatus.UNKNOWN,
            OrderWriteStatus.OBSERVED,
            OrderWriteStatus.TERMINAL,
        },
        OrderWriteStatus.UNKNOWN: {
            OrderWriteStatus.UNKNOWN,
            OrderWriteStatus.OBSERVED,
            OrderWriteStatus.TERMINAL,
        },
        OrderWriteStatus.OBSERVED: {
            OrderWriteStatus.OBSERVED,
            OrderWriteStatus.TERMINAL,
        },
        OrderWriteStatus.TERMINAL: {OrderWriteStatus.TERMINAL},
    }
    for operation_id, old in old_reservations.items():
        new = next_reservations[operation_id]
        if (
            replace(old, status=new.status) != new
            or new.status not in status_transitions[old.status]
        ):
            return False
    next_receipts = {
        (item.intent_id, item.approval_id): item
        for item in next_state.approval_receipts
    }
    next_tracked = {item.intent_id: item for item in next_state.tracked_orders}
    for old_receipt in current.approval_receipts:
        if (old_receipt.intent_id, old_receipt.approval_id) not in next_receipts:
            tracked = next_tracked.get(old_receipt.intent_id)
            if tracked is None or tracked.approval_id != old_receipt.approval_id:
                return False
    old_tracked = {item.intent_id: item for item in current.tracked_orders}
    if not old_tracked.keys() <= next_tracked.keys():
        return False
    for intent_id, old in old_tracked.items():
        new = next_tracked[intent_id]
        if (
            old.ref_id != new.ref_id
            or (old.approval_id is not None and new.approval_id != old.approval_id)
            or (
                old.provider_order_id is not None
                and new.provider_order_id != old.provider_order_id
            )
            or (
                old.last_fact is not None
                and (
                    new.last_fact is None
                    or not _fact_progresses(old.last_fact, new.last_fact)
                )
            )
        ):
            return False
    if current.pending_exit is None:
        if next_state.pending_exit is not None:
            pending = next_state.pending_exit
            new_cancel = any(
                item.action is OrderWriteAction.CANCEL
                and item.intent_id == pending.stop_intent_id
                and item.target_provider_order_id == pending.stop_provider_order_id
                and item.reserved_revision == next_state.revision
                for item in next_state.write_reservations
                if item.operation_id not in old_reservations
            )
            if not new_cancel:
                return False
    elif next_state.pending_exit != current.pending_exit:
        old_pending = current.pending_exit
        old_track = old_tracked.get(old_pending.stop_intent_id)
        new_track = next_tracked.get(old_pending.stop_intent_id)
        if next_state.pending_exit is not None:
            bound_exit = next_state.pending_exit
            new_exit_intent = next(
                (
                    item
                    for item in next_state.intents
                    if item.intent_id == bound_exit.exit_intent_id
                    and item.intent_id not in current_intent_ids
                ),
                None,
            )
            if (
                old_pending.exit_intent_id is not None
                or replace(old_pending, exit_intent_id=bound_exit.exit_intent_id)
                != bound_exit
                or old_pending.symbol not in current.positions
                or new_exit_intent is None
                or new_exit_intent.kind is not IntentKind.EXIT
                or new_exit_intent.symbol != old_pending.symbol
                or new_exit_intent.side is not OrderSide.SELL
                or new_exit_intent.quantity
                != current.positions[old_pending.symbol].quantity
                or new_exit_intent.lifecycle is not IntentLifecycle.PROPOSED
                or current.positions[old_pending.symbol].stop_intent_id is not None
                or old_track is None
                or old_track.last_fact is None
                or old_track.last_fact.state
                not in (OrderState.CANCELED, OrderState.REJECTED)
            ):
                return False
        else:
            stop_intent = next(
                (
                    item
                    for item in next_state.intents
                    if item.intent_id == old_pending.stop_intent_id
                ),
                None,
            )
            stop_fact = None if new_track is None else new_track.last_fact
            stop_filled = (
                not next_state.positions
                and stop_intent is not None
                and stop_intent.lifecycle is IntentLifecycle.RECONCILED
                and new_track is not None
                and new_track.provider_order_id == old_pending.stop_provider_order_id
                and stop_fact is not None
                and stop_fact.provider_order_id == old_pending.stop_provider_order_id
                and stop_fact.account_fingerprint == current.account_fingerprint
                and stop_fact.source_identity in (None, current.source_identity)
                and stop_fact.intent_id in (None, old_pending.stop_intent_id)
                and stop_fact.ref_id in (None, stop_intent.ref_id)
                and stop_fact.kind is IntentKind.PROTECTIVE_STOP
                and stop_fact.symbol == old_pending.symbol
                and stop_fact.side is OrderSide.SELL
                and stop_fact.state is OrderState.FILLED
                and stop_fact.requested_quantity == stop_intent.quantity
                and stop_fact.filled_quantity == stop_intent.quantity
                and stop_fact.remaining_quantity == 0
                and stop_fact.stop_price == stop_intent.stop_price
            )
            exit_intent = (
                None
                if old_pending.exit_intent_id is None
                else next_intents.get(old_pending.exit_intent_id)
            )
            exit_track = (
                None
                if old_pending.exit_intent_id is None
                else next_tracked.get(old_pending.exit_intent_id)
            )
            exit_fact = None if exit_track is None else exit_track.last_fact
            exit_reservation = next(
                (
                    item
                    for item in next_state.write_reservations
                    if item.action is OrderWriteAction.PLACE
                    and item.intent_id == old_pending.exit_intent_id
                ),
                None,
            )
            canceled_stop = (
                old_track is not None
                and old_track.last_fact is not None
                and old_track.last_fact.state
                in (OrderState.CANCELED, OrderState.REJECTED)
                and old_track.provider_order_id == old_pending.stop_provider_order_id
                and old_pending.symbol in current.positions
                and current.positions[old_pending.symbol].stop_intent_id is None
            )
            exit_filled = (
                old_pending.exit_intent_id is not None
                and canceled_stop
                and not next_state.positions
                and exit_intent is not None
                and exit_intent.kind is IntentKind.EXIT
                and exit_intent.symbol == old_pending.symbol
                and exit_intent.side is OrderSide.SELL
                and exit_intent.lifecycle is IntentLifecycle.RECONCILED
                and exit_track is not None
                and exit_track.provider_order_id is not None
                and exit_fact is not None
                and exit_fact.provider_order_id == exit_track.provider_order_id
                and exit_fact.account_fingerprint == current.account_fingerprint
                and exit_fact.source_identity in (None, current.source_identity)
                and exit_fact.intent_id in (None, exit_intent.intent_id)
                and exit_fact.ref_id in (None, exit_intent.ref_id)
                and exit_fact.kind is IntentKind.EXIT
                and exit_fact.symbol == old_pending.symbol
                and exit_fact.side is OrderSide.SELL
                and exit_fact.state is OrderState.FILLED
                and exit_fact.requested_quantity == exit_intent.quantity
                and exit_fact.filled_quantity == exit_intent.quantity
                and exit_fact.remaining_quantity == 0
                and exit_fact.stop_price is None
                and exit_reservation is not None
                and exit_reservation.status is OrderWriteStatus.TERMINAL
            )
            if not (stop_filled or exit_filled):
                return False
    return True


def _encode_state(state: RuntimeState) -> dict[str, Any]:
    return {
        "schema": _SCHEMA,
        "owner_id": str(state.owner_id),
        "source_identity": _encode_source(state.source_identity),
        "session_fingerprint": state.session_fingerprint,
        "account_fingerprint": state.account_fingerprint,
        "revision": state.revision,
        "next_sequence": state.next_sequence,
        "intents": [_encode_intent(item) for item in state.intents],
        "positions": [_encode_position(item) for item in state.positions.values()],
        "approval_receipts": [
            _encode_receipt(item) for item in state.approval_receipts
        ],
        "proposal_reviews": [_encode_review(item) for item in state.proposal_reviews],
        "tracked_orders": [
            _encode_tracked_order(item) for item in state.tracked_orders
        ],
        "write_reservations": [
            _encode_reservation(item) for item in state.write_reservations
        ],
        "pending_exit": None
        if state.pending_exit is None
        else _encode_pending_exit(state.pending_exit),
    }


def _decode_state(value: object) -> RuntimeState:
    data = _object(
        value,
        {
            "schema",
            "owner_id",
            "source_identity",
            "session_fingerprint",
            "account_fingerprint",
            "revision",
            "next_sequence",
            "intents",
            "positions",
            "approval_receipts",
            "proposal_reviews",
            "tracked_orders",
            "write_reservations",
            "pending_exit",
        },
    )
    if data["schema"] != _SCHEMA:
        raise RuntimeStateStoreCorrupt("runtime state schema is unsupported")
    intents = tuple(_decode_intent(item) for item in _array(data["intents"]))
    positions = tuple(_decode_position(item) for item in _array(data["positions"]))
    return RuntimeState(
        owner_id=_uuid(data["owner_id"]),
        source_identity=_decode_source(data["source_identity"]),
        session_fingerprint=_string(data["session_fingerprint"]),
        account_fingerprint=_string(data["account_fingerprint"]),
        revision=_integer(data["revision"]),
        next_sequence=_integer(data["next_sequence"]),
        intents=intents,
        positions={item.symbol: item for item in positions},
        approval_receipts=tuple(
            _decode_receipt(item) for item in _array(data["approval_receipts"])
        ),
        proposal_reviews=tuple(
            _decode_review(item) for item in _array(data["proposal_reviews"])
        ),
        tracked_orders=tuple(
            _decode_tracked_order(item) for item in _array(data["tracked_orders"])
        ),
        write_reservations=tuple(
            _decode_reservation(item) for item in _array(data["write_reservations"])
        ),
        pending_exit=None
        if data["pending_exit"] is None
        else _decode_pending_exit(data["pending_exit"]),
    )


def _encode_pending_exit(value: PendingExit) -> dict[str, object]:
    return {
        "stop_intent_id": str(value.stop_intent_id),
        "stop_provider_order_id": value.stop_provider_order_id,
        "symbol": value.symbol.value,
        "exit_reasons": [reason.value for reason in value.exit_reasons],
        "exit_intent_id": None
        if value.exit_intent_id is None
        else str(value.exit_intent_id),
    }


def _decode_pending_exit(value: object) -> PendingExit:
    data = _object(
        value,
        {
            "stop_intent_id",
            "stop_provider_order_id",
            "symbol",
            "exit_reasons",
            "exit_intent_id",
        },
    )
    return PendingExit(
        stop_intent_id=_uuid(data["stop_intent_id"]),
        stop_provider_order_id=_string(data["stop_provider_order_id"]),
        symbol=Symbol(_string(data["symbol"])),
        exit_reasons=tuple(
            AdmissionBlocker(_string(item)) for item in _array(data["exit_reasons"])
        ),
        exit_intent_id=None
        if data["exit_intent_id"] is None
        else _uuid(data["exit_intent_id"]),
    )


def _encode_source(value: SourceIdentity) -> dict[str, str]:
    return {"head": value.head, "tree": value.tree}


def _decode_source(value: object) -> SourceIdentity:
    data = _object(value, {"head", "tree"})
    return SourceIdentity(_string(data["head"]), _string(data["tree"]))


def _encode_intent(value: LogicalOrderIntent) -> dict[str, object]:
    return {
        "intent_id": str(value.intent_id),
        "ref_id": value.ref_id,
        "logical_sequence": value.logical_sequence,
        "kind": value.kind.value,
        "symbol": value.symbol.value,
        "side": value.side.value,
        "quantity": canonical_decimal(value.quantity),
        "stop_price": None
        if value.stop_price is None
        else canonical_decimal(value.stop_price),
        "source_identity": _encode_source(value.source_identity),
        "owner_id": str(value.owner_id),
        "lifecycle": value.lifecycle.value,
        "terms_digest": value.terms_digest,
        "created_at": value.created_at.isoformat(),
    }


def _decode_intent(value: object) -> LogicalOrderIntent:
    data = _object(
        value,
        {
            "intent_id",
            "ref_id",
            "logical_sequence",
            "kind",
            "symbol",
            "side",
            "quantity",
            "stop_price",
            "source_identity",
            "owner_id",
            "lifecycle",
            "terms_digest",
            "created_at",
        },
    )
    return LogicalOrderIntent(
        intent_id=_uuid(data["intent_id"]),
        ref_id=_string(data["ref_id"]),
        logical_sequence=_integer(data["logical_sequence"]),
        kind=IntentKind(_string(data["kind"])),
        symbol=Symbol(_string(data["symbol"])),
        side=OrderSide(_string(data["side"])),
        quantity=_decimal(data["quantity"]),
        stop_price=None if data["stop_price"] is None else _decimal(data["stop_price"]),
        source_identity=_decode_source(data["source_identity"]),
        owner_id=_uuid(data["owner_id"]),
        lifecycle=IntentLifecycle(_string(data["lifecycle"])),
        terms_digest=_string(data["terms_digest"]),
        created_at=_datetime(data["created_at"]),
    )


def _encode_position(value: OwnedPositionRecord) -> dict[str, object]:
    return {
        "symbol": value.symbol.value,
        "entry_intent_id": str(value.entry_intent_id),
        "quantity": canonical_decimal(value.quantity),
        "average_entry_fill": canonical_decimal(value.average_entry_fill),
        "hard_stop_price": canonical_decimal(value.hard_stop_price),
        "stop_intent_id": None
        if value.stop_intent_id is None
        else str(value.stop_intent_id),
    }


def _decode_position(value: object) -> OwnedPositionRecord:
    data = _object(
        value,
        {
            "symbol",
            "entry_intent_id",
            "quantity",
            "average_entry_fill",
            "hard_stop_price",
            "stop_intent_id",
        },
    )
    return OwnedPositionRecord(
        symbol=Symbol(_string(data["symbol"])),
        entry_intent_id=_uuid(data["entry_intent_id"]),
        quantity=_decimal(data["quantity"]),
        average_entry_fill=_decimal(data["average_entry_fill"]),
        hard_stop_price=_decimal(data["hard_stop_price"]),
        stop_intent_id=None
        if data["stop_intent_id"] is None
        else _uuid(data["stop_intent_id"]),
    )


def _encode_receipt(value: ApprovalRequiredReceipt) -> dict[str, object]:
    return {
        "approval_id": value.approval_id,
        "intent_id": str(value.intent_id),
        "ref_id": value.ref_id,
        "terms_digest": value.terms_digest,
        "account_fingerprint": value.account_fingerprint,
        "source_identity": _encode_source(value.source_identity),
        "session_fingerprint": value.session_fingerprint,
        "state_revision": value.state_revision,
        "observed_at": value.observed_at.isoformat(),
    }


def _decode_receipt(value: object) -> ApprovalRequiredReceipt:
    data = _object(
        value,
        {
            "approval_id",
            "intent_id",
            "ref_id",
            "terms_digest",
            "account_fingerprint",
            "source_identity",
            "session_fingerprint",
            "state_revision",
            "observed_at",
        },
    )
    return ApprovalRequiredReceipt(
        approval_id=_string(data["approval_id"]),
        intent_id=_uuid(data["intent_id"]),
        ref_id=_string(data["ref_id"]),
        terms_digest=_string(data["terms_digest"]),
        account_fingerprint=_string(data["account_fingerprint"]),
        source_identity=_decode_source(data["source_identity"]),
        session_fingerprint=_string(data["session_fingerprint"]),
        state_revision=_integer(data["state_revision"]),
        observed_at=_datetime(data["observed_at"]),
    )


def _encode_review(value: BrokerReviewFacts) -> dict[str, object]:
    return {
        "account_fingerprint": value.account_fingerprint,
        "source_identity": _encode_source(value.source_identity),
        "session_fingerprint": value.session_fingerprint,
        "state_revision": value.state_revision,
        "ref_id": value.ref_id,
        "terms_digest": value.terms_digest,
        "status": value.status.value,
        "warnings": list(value.warnings),
        "approval_required": value.approval_required,
        "observed_at": value.observed_at.isoformat(),
    }


def _decode_review(value: object) -> BrokerReviewFacts:
    data = _object(
        value,
        {
            "account_fingerprint",
            "source_identity",
            "session_fingerprint",
            "state_revision",
            "ref_id",
            "terms_digest",
            "status",
            "warnings",
            "approval_required",
            "observed_at",
        },
    )
    warnings = _array(data["warnings"])
    return BrokerReviewFacts(
        account_fingerprint=_string(data["account_fingerprint"]),
        source_identity=_decode_source(data["source_identity"]),
        session_fingerprint=_string(data["session_fingerprint"]),
        state_revision=_integer(data["state_revision"]),
        ref_id=_string(data["ref_id"]),
        terms_digest=_string(data["terms_digest"]),
        status=ReviewStatus(_string(data["status"])),
        warnings=tuple(_string(item) for item in warnings),
        approval_required=_boolean(data["approval_required"]),
        observed_at=_datetime(data["observed_at"]),
    )


def _encode_broker_order(value: BrokerOrderFact) -> dict[str, object]:
    return {
        "provider_order_id": value.provider_order_id,
        "account_fingerprint": value.account_fingerprint,
        "source_identity": None
        if value.source_identity is None
        else _encode_source(value.source_identity),
        "intent_id": None if value.intent_id is None else str(value.intent_id),
        "ref_id": value.ref_id,
        "kind": value.kind.value,
        "symbol": value.symbol.value,
        "side": value.side.value,
        "state": value.state.value,
        "requested_quantity": canonical_decimal(value.requested_quantity),
        "filled_quantity": canonical_decimal(value.filled_quantity),
        "remaining_quantity": canonical_decimal(value.remaining_quantity),
        "stop_price": None
        if value.stop_price is None
        else canonical_decimal(value.stop_price),
        "observed_at": value.observed_at.isoformat(),
        "average_fill_price": None
        if value.average_fill_price is None
        else canonical_decimal(value.average_fill_price),
    }


def _decode_broker_order(value: object) -> BrokerOrderFact:
    data = _object(
        value,
        {
            "provider_order_id",
            "account_fingerprint",
            "source_identity",
            "intent_id",
            "ref_id",
            "kind",
            "symbol",
            "side",
            "state",
            "requested_quantity",
            "filled_quantity",
            "remaining_quantity",
            "stop_price",
            "observed_at",
            "average_fill_price",
        },
    )
    return BrokerOrderFact(
        provider_order_id=_string(data["provider_order_id"]),
        account_fingerprint=_string(data["account_fingerprint"]),
        source_identity=None
        if data["source_identity"] is None
        else _decode_source(data["source_identity"]),
        intent_id=None if data["intent_id"] is None else _uuid(data["intent_id"]),
        ref_id=None if data["ref_id"] is None else _string(data["ref_id"]),
        kind=IntentKind(_string(data["kind"])),
        symbol=Symbol(_string(data["symbol"])),
        side=OrderSide(_string(data["side"])),
        state=OrderState(_string(data["state"])),
        requested_quantity=_decimal(data["requested_quantity"]),
        filled_quantity=_decimal(data["filled_quantity"]),
        remaining_quantity=_decimal(data["remaining_quantity"]),
        stop_price=None if data["stop_price"] is None else _decimal(data["stop_price"]),
        observed_at=_datetime(data["observed_at"]),
        average_fill_price=None
        if data["average_fill_price"] is None
        else _decimal(data["average_fill_price"]),
    )


def _encode_tracked_order(value: TrackedOrder) -> dict[str, object]:
    return {
        "intent_id": str(value.intent_id),
        "ref_id": value.ref_id,
        "approval_id": value.approval_id,
        "provider_order_id": value.provider_order_id,
        "last_fact": None
        if value.last_fact is None
        else _encode_broker_order(value.last_fact),
    }


def _decode_tracked_order(value: object) -> TrackedOrder:
    data = _object(
        value, {"intent_id", "ref_id", "approval_id", "provider_order_id", "last_fact"}
    )
    return TrackedOrder(
        intent_id=_uuid(data["intent_id"]),
        ref_id=_string(data["ref_id"]),
        approval_id=None
        if data["approval_id"] is None
        else _string(data["approval_id"]),
        provider_order_id=None
        if data["provider_order_id"] is None
        else _string(data["provider_order_id"]),
        last_fact=None
        if data["last_fact"] is None
        else _decode_broker_order(data["last_fact"]),
    )


def _encode_reservation(value: OrderWriteReservation) -> dict[str, object]:
    return {
        "operation_id": str(value.operation_id),
        "action": value.action.value,
        "intent_id": str(value.intent_id),
        "ref_id": value.ref_id,
        "terms_digest": value.terms_digest,
        "owner_id": str(value.owner_id),
        "source_identity": _encode_source(value.source_identity),
        "account_fingerprint": value.account_fingerprint,
        "session_fingerprint": value.session_fingerprint,
        "expected_revision": value.expected_revision,
        "reserved_revision": value.reserved_revision,
        "review_revision": value.review_revision,
        "review": None if value.review is None else _encode_review(value.review),
        "approval_id": value.approval_id,
        "target_provider_order_id": value.target_provider_order_id,
        "status": value.status.value,
    }


def _decode_reservation(value: object) -> OrderWriteReservation:
    data = _object(
        value,
        {
            "operation_id",
            "action",
            "intent_id",
            "ref_id",
            "terms_digest",
            "owner_id",
            "source_identity",
            "account_fingerprint",
            "session_fingerprint",
            "expected_revision",
            "reserved_revision",
            "review_revision",
            "review",
            "approval_id",
            "target_provider_order_id",
            "status",
        },
    )
    return OrderWriteReservation(
        operation_id=_uuid(data["operation_id"]),
        action=OrderWriteAction(_string(data["action"])),
        intent_id=_uuid(data["intent_id"]),
        ref_id=_string(data["ref_id"]),
        terms_digest=_string(data["terms_digest"]),
        owner_id=_uuid(data["owner_id"]),
        source_identity=_decode_source(data["source_identity"]),
        account_fingerprint=_string(data["account_fingerprint"]),
        session_fingerprint=_string(data["session_fingerprint"]),
        expected_revision=_integer(data["expected_revision"]),
        reserved_revision=_integer(data["reserved_revision"]),
        review_revision=None
        if data["review_revision"] is None
        else _integer(data["review_revision"]),
        review=None if data["review"] is None else _decode_review(data["review"]),
        approval_id=None
        if data["approval_id"] is None
        else _string(data["approval_id"]),
        target_provider_order_id=None
        if data["target_provider_order_id"] is None
        else _string(data["target_provider_order_id"]),
        status=OrderWriteStatus(_string(data["status"])),
    )


def _object(value: object, expected_keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise RuntimeStateStoreCorrupt("runtime state object has invalid fields")
    return value


def _array(value: object) -> list[object]:
    if not isinstance(value, list):
        raise RuntimeStateStoreCorrupt("runtime state array is malformed")
    return value


def _string(value: object) -> str:
    if not isinstance(value, str):
        raise RuntimeStateStoreCorrupt("runtime state text field is malformed")
    return value


def _boolean(value: object) -> bool:
    if not isinstance(value, bool):
        raise RuntimeStateStoreCorrupt("runtime state boolean field is malformed")
    return value


def _integer(value: object) -> int:
    if type(value) is not int:
        raise RuntimeStateStoreCorrupt("runtime state integer field is malformed")
    return value


def _uuid(value: object) -> UUID:
    raw = _string(value)
    try:
        parsed = UUID(raw)
    except ValueError:
        raise RuntimeStateStoreCorrupt(
            "runtime state UUID field is malformed"
        ) from None
    if str(parsed) != raw:
        raise RuntimeStateStoreCorrupt("runtime state UUID is not canonical")
    return parsed


def _decimal(value: object) -> Decimal:
    raw = _string(value)
    try:
        parsed = Decimal(raw)
    except Exception:
        raise RuntimeStateStoreCorrupt(
            "runtime state Decimal field is malformed"
        ) from None
    if not parsed.is_finite() or canonical_decimal(parsed) != raw:
        raise RuntimeStateStoreCorrupt("runtime state Decimal is not canonical")
    return parsed


def _datetime(value: object) -> datetime:
    raw = _string(value)
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        raise RuntimeStateStoreCorrupt("runtime state timestamp is malformed") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RuntimeStateStoreCorrupt("runtime state timestamp has no timezone")
    return parsed


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeStateStoreCorrupt("runtime state JSON has duplicate fields")
        result[key] = value
    return result


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _rollback(connection: sqlite3.Connection) -> None:
    try:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
    except sqlite3.Error:
        pass
