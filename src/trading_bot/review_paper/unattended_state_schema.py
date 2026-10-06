"""Passive, closed Architecture-133 state-store v1 contract."""

from dataclasses import dataclass

from trading_bot.review_paper.unattended_activation import ReviewPaperWake

STATE_SCHEMA = "arch133-review-paper-state/v1"
SNAPSHOT_SCHEMA = "arch133-review-paper-state-snapshot/v1"
APPLICATION_ID = 133066
USER_VERSION = 1
MAX_REVISION = 9223372036854775807
METADATA = (("schema", STATE_SCHEMA), ("version", "1"))
TABLES = (
    (
        "metadata",
        "CREATE TABLE metadata (key TEXT PRIMARY KEY, "
        "value TEXT NOT NULL) WITHOUT ROWID",
    ),
    (
        "activations",
        "CREATE TABLE activations (activation_id TEXT PRIMARY KEY, "
        "activation_json TEXT NOT NULL) WITHOUT ROWID",
    ),
    (
        "wakes",
        "CREATE TABLE wakes (activation_id TEXT PRIMARY KEY "
        "REFERENCES activations(activation_id), wake_id TEXT NOT NULL, "
        "wake_json TEXT NOT NULL, revision INTEGER NOT NULL "
        "CHECK(revision >= 0)) WITHOUT ROWID",
    ),
)


class UnattendedStateError(ValueError):
    """Invalid or unavailable closed state; error text contains no stored material."""


class UnattendedStateConflict(UnattendedStateError):
    """Exact activation or optimistic expected state disagrees with persistence."""


@dataclass(frozen=True, slots=True)
class PersistedReviewPaperWake:
    wake: ReviewPaperWake
    revision: int
