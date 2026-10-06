"""Dedicated local wake durability, separate from the 131 paper ledger (133-B).

No provider/paper effect is reachable. Every write uses a single transaction,
zero busy timeout and no retry; 133-A is the sole transition semantic authority.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from trading_bot.review_paper.unattended_activation import (
    ReviewPaperActivation,
    ReviewPaperWake,
    ReviewPaperWakeState,
    transition_review_paper_wake,
)
from trading_bot.review_paper.unattended_state_schema import (
    APPLICATION_ID,
    MAX_REVISION,
    METADATA,
    TABLES,
    USER_VERSION,
    PersistedReviewPaperWake,
    UnattendedStateConflict,
    UnattendedStateError,
)
from trading_bot.review_paper.unattended_state_verifier import (
    UnattendedStateSnapshot,
    read_state_connection,
    snapshot_unattended_state,
    state_database_path,
)


class UnattendedStateStore:
    """Explicit-path writer; construction never opens/initializes any database.

    Operations own and close their connections. An existing empty/partial store
    is rejected, never guessed to be a new schema or repaired.
    """

    def __init__(self, path: Path) -> None:
        self.path = state_database_path(path)

    def snapshot(self) -> UnattendedStateSnapshot:
        return snapshot_unattended_state(self.path)

    def admit(self, activation: ReviewPaperActivation) -> PersistedReviewPaperWake:
        """Atomically admit activation + READY wake, or read exact existing state."""
        if type(activation) is not ReviewPaperActivation:
            raise UnattendedStateError("activation must be exact 133-A material")
        path = state_database_path(self.path, activation=activation)
        exists = path.exists()
        if exists:
            snapshot = self.snapshot()
            if str(activation.activation_id) in dict(snapshot.activations):
                return snapshot.current(activation)
        try:
            with (
                closing(
                    sqlite3.connect(
                        path.as_uri() + ("?mode=rw" if exists else "?mode=rwc"),
                        uri=True,
                        timeout=0,
                    )
                ) as connection,
                connection,
            ):
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("BEGIN IMMEDIATE")
                if (
                    not exists
                    and not connection.execute(
                        "SELECT name FROM sqlite_schema"
                    ).fetchall()
                ):
                    if connection.execute("PRAGMA user_version").fetchone() != (
                        0,
                    ) or connection.execute("PRAGMA application_id").fetchone() != (0,):
                        raise UnattendedStateError(
                            "uninitialized state metadata conflicts"
                        )
                    for _, sql in TABLES:
                        connection.execute(sql)
                    connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
                    connection.execute(f"PRAGMA user_version={USER_VERSION}")
                    connection.executemany(
                        "INSERT INTO metadata VALUES (?, ?)", METADATA
                    )
                else:
                    snapshot = read_state_connection(connection)
                    if str(activation.activation_id) in dict(snapshot.activations):
                        return snapshot.current(activation)
                wake = ReviewPaperWake(
                    activation=activation, updated_at=activation.created_at
                )
                connection.execute(
                    "INSERT INTO activations VALUES (?, ?)",
                    (str(activation.activation_id), activation.to_json()),
                )
                connection.execute(
                    "INSERT INTO wakes VALUES (?, ?, ?, ?)",
                    (
                        str(activation.activation_id),
                        str(wake.wake_id),
                        wake.to_json(),
                        0,
                    ),
                )
                read_state_connection(connection)
                return PersistedReviewPaperWake(wake, 0)
        except sqlite3.Error:
            raise UnattendedStateError("state admission failed without retry") from None

    def transition(
        self,
        expected: PersistedReviewPaperWake,
        *,
        state: ReviewPaperWakeState,
        at: datetime,
    ) -> PersistedReviewPaperWake:
        """One exact optimistic CAS; stale/conflicting state has no retry authority."""
        if (
            type(expected) is not PersistedReviewPaperWake
            or type(expected.wake) is not ReviewPaperWake
            or type(expected.revision) is not int
            or not 0 <= expected.revision < MAX_REVISION
        ):
            raise UnattendedStateError("expected persisted state is invalid")
        path = state_database_path(self.path, activation=expected.wake.activation)
        try:
            with (
                closing(
                    sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=0)
                ) as connection,
                connection,
            ):
                connection.execute("BEGIN IMMEDIATE")
                current = read_state_connection(connection).current(
                    expected.wake.activation
                )
                if current != expected:
                    raise UnattendedStateConflict(
                        "expected persisted wake/revision is stale"
                    )
                wake = transition_review_paper_wake(current.wake, state=state, at=at)
                changed = connection.execute(
                    "UPDATE wakes SET wake_json=?, revision=? WHERE activation_id=? "
                    "AND wake_id=? AND wake_json=? AND revision=?",
                    (
                        wake.to_json(),
                        current.revision + 1,
                        str(wake.activation.activation_id),
                        str(wake.wake_id),
                        current.wake.to_json(),
                        current.revision,
                    ),
                ).rowcount
                if changed != 1:
                    raise UnattendedStateConflict("state compare-and-swap failed")
                read_state_connection(connection)
                return PersistedReviewPaperWake(wake, current.revision + 1)
        except sqlite3.Error:
            raise UnattendedStateError(
                "state transition failed without retry"
            ) from None
