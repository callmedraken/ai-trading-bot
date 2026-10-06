"""Independent provider-free, read-only Architecture-133 reconciliation.

Only the explicit state database is opened. Canonical 133-A readers validate
semantic facts; neither this module nor its imports can construct the writer.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from uuid import UUID

from trading_bot.review_paper.unattended_activation import (
    ReviewPaperActivation,
    ReviewPaperWake,
    ReviewPaperWakeState,
)
from trading_bot.review_paper.unattended_state_schema import (
    APPLICATION_ID,
    MAX_REVISION,
    METADATA,
    SNAPSHOT_SCHEMA,
    TABLES,
    USER_VERSION,
    PersistedReviewPaperWake,
    UnattendedStateConflict,
    UnattendedStateError,
)


@dataclass(frozen=True, slots=True)
class UnattendedStateSnapshot:
    """Complete exact rows, explicitly sorted, excluding file transport metadata."""

    metadata: tuple[tuple[str, str], ...]
    activations: tuple[tuple[str, str], ...]
    wakes: tuple[tuple[str, str, str, int], ...]

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema": SNAPSHOT_SCHEMA,
                "application_id": APPLICATION_ID,
                "user_version": USER_VERSION,
                "sqlite_schema": sorted(
                    ("table", name, name, sql) for name, sql in TABLES
                ),
                "metadata": sorted(self.metadata),
                "activations": sorted(self.activations),
                "wakes": sorted(self.wakes),
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()

    def current(self, activation: ReviewPaperActivation) -> PersistedReviewPaperWake:
        """Require exact activation bytes, including the inert paper-store path."""
        key = str(activation.activation_id)
        found = dict(self.activations).get(key)
        if found != activation.to_json():
            raise UnattendedStateConflict("activation material conflicts or is absent")
        for activation_id, _, wake_json, revision in self.wakes:
            if activation_id == key:
                return PersistedReviewPaperWake(
                    ReviewPaperWake.from_json(wake_json, activation=activation),
                    revision,
                )
        raise UnattendedStateError("wake row is absent")


@dataclass(frozen=True, slots=True)
class UnattendedStateVerification:
    """Bounded sanitized facts; contains no path, proposal, or raw SQLite/JSON text."""

    activation_id: UUID
    wake_id: UUID
    state: ReviewPaperWakeState
    revision: int
    activation_count: int
    fingerprint: str


def state_database_path(
    path: Path, *, activation: ReviewPaperActivation | None = None
) -> Path:
    """Validate explicit transport and reject reuse of the inert paper-store path."""
    if not isinstance(path, Path) or not path.is_absolute():
        raise UnattendedStateError("state database requires an explicit absolute Path")
    if activation is not None and type(activation) is not ReviewPaperActivation:
        raise UnattendedStateError("expected activation must be exact 133-A material")
    try:
        normalized = path.resolve()
    except (OSError, RuntimeError, ValueError):
        raise UnattendedStateError("state database path is unavailable") from None
    if activation is not None and PureWindowsPath(str(normalized)) == PureWindowsPath(
        activation.store_path
    ):
        raise UnattendedStateError("state database must be separate from paper storage")
    return normalized


def read_state_connection(connection: sqlite3.Connection) -> UnattendedStateSnapshot:
    """Read/validate the whole closed store in the caller's single read transaction.

    This function issues only SELECT and read-only PRAGMA queries. It is also
    used by the writer inside its transaction, without granting verifier writes.
    """
    try:
        if connection.execute("PRAGMA application_id").fetchone() != (APPLICATION_ID,):
            raise UnattendedStateError("state application identity is invalid")
        if connection.execute("PRAGMA user_version").fetchone() != (USER_VERSION,):
            raise UnattendedStateError("state version is invalid")
        schema = tuple(
            sorted(
                connection.execute(
                    "SELECT type, name, tbl_name, sql FROM sqlite_schema"
                ).fetchall()
            )
        )
        expected_schema = tuple(
            sorted(("table", name, name, sql) for name, sql in TABLES)
        )
        if schema != expected_schema:
            raise UnattendedStateError("state schema is not the exact closed v1 schema")
        metadata = tuple(
            sorted(connection.execute("SELECT key, value FROM metadata").fetchall())
        )
        if metadata != METADATA:
            raise UnattendedStateError("state metadata is invalid")
        activations = tuple(
            sorted(
                connection.execute(
                    "SELECT activation_id, activation_json FROM activations"
                ).fetchall()
            )
        )
        wakes = tuple(
            sorted(
                connection.execute(
                    "SELECT activation_id, wake_id, wake_json, revision FROM wakes"
                ).fetchall()
            )
        )
        if not activations or len(activations) != len(wakes):
            raise UnattendedStateError("state activation/wake rows are incomplete")
        parsed = {}
        for key, value in activations:
            activation = ReviewPaperActivation.from_json(value)
            if key != str(activation.activation_id) or key in parsed:
                raise UnattendedStateError("activation row identity is invalid")
            parsed[key] = activation
        seen = set()
        wake_ids = set()
        for key, wake_id, value, revision in wakes:
            if key not in parsed or key in seen or wake_id in wake_ids:
                raise UnattendedStateError("wake binding is invalid")
            if type(revision) is not int or not 0 <= revision <= MAX_REVISION:
                raise UnattendedStateError("wake revision is invalid")
            wake = ReviewPaperWake.from_json(value, activation=parsed[key])
            if wake_id != str(wake.wake_id):
                raise UnattendedStateError("wake row identity is invalid")
            seen.add(key)
            wake_ids.add(wake_id)
        return UnattendedStateSnapshot(metadata, activations, wakes)
    except (sqlite3.Error, ValueError, TypeError, KeyError, OverflowError):
        raise UnattendedStateError("state database failed closed validation") from None


def snapshot_unattended_state(path: Path) -> UnattendedStateSnapshot:
    """Open only existing SQLite through URI mode=ro and read one stable snapshot."""
    path = state_database_path(path)
    try:
        with closing(
            sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0)
        ) as connection:
            connection.execute("BEGIN")
            return read_state_connection(connection)
    except (sqlite3.Error, OSError):
        raise UnattendedStateError(
            "state database is unavailable for read-only verification"
        ) from None


def verify_unattended_state(
    path: Path,
    *,
    expected_activation: ReviewPaperActivation,
    expected_wake_id: UUID,
    expected_wake: ReviewPaperWake | None = None,
    expected_revision: int | None = None,
) -> UnattendedStateVerification:
    """Reconcile exact expected identities without writes, transition, or repair."""
    if type(expected_activation) is not ReviewPaperActivation:
        raise UnattendedStateError("expected activation must be exact 133-A material")
    path = state_database_path(path, activation=expected_activation)
    if type(expected_wake_id) is not UUID:
        raise UnattendedStateError("expected wake identity must be an exact UUID")
    if expected_revision is not None and (
        type(expected_revision) is not int or not 0 <= expected_revision <= MAX_REVISION
    ):
        raise UnattendedStateError("expected revision is invalid")
    if expected_wake is not None and type(expected_wake) is not ReviewPaperWake:
        raise UnattendedStateError("expected wake must be exact 133-A material")
    snapshot = snapshot_unattended_state(path)
    current = snapshot.current(expected_activation)
    if (
        current.wake.wake_id != expected_wake_id
        or (expected_revision is not None and current.revision != expected_revision)
        or (
            expected_wake is not None
            and current.wake.to_json() != expected_wake.to_json()
        )
        or (
            expected_wake is not None
            and current.wake.activation.to_json() != expected_wake.activation.to_json()
        )
    ):
        raise UnattendedStateConflict("expected wake identity or state conflicts")
    return UnattendedStateVerification(
        current.wake.activation.activation_id,
        current.wake.wake_id,
        current.wake.state,
        current.revision,
        len(snapshot.activations),
        snapshot.fingerprint,
    )
