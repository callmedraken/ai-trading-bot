"""Origin-bound, single-writer durable state for future L43 operations.

The production session can only open a pre-provisioned state journal. It never
creates state from provider observations, repairs an incomplete journal, or
opens the consumed Q62 journal for mutation. Tests may create a fresh journal
under their temporary root using ``DurableStateStore.create`` with a fake Q62
origin anchor.
"""

from __future__ import annotations

import os
import stat
from contextlib import AbstractContextManager
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import BinaryIO

from trading_bot.live_prototype.durable_state import (
    DurableState,
    DurableStateError,
    DurableStateStore,
    IntentStatus,
    L43OriginAnchor,
    ManualCloseRequired,
    ReconciliationSnapshot,
)
from trading_bot.live_prototype.live_controller import (
    LiveController,
    PreparedInvocation,
)
from trading_bot.live_prototype.tiny_live_policy import ManualCloseTrigger

L43_STATE_PATH = Path(r"F:\AI\arch147-l43-live-state-v1\durable-state.jsonl")
_REPARSE_POINT = 0x400


class L43StateUnavailable(DurableStateError):
    """Missing, malformed, mismatched, or concurrently owned L43 state."""


@dataclass(frozen=True, slots=True)
class L43StateSnapshot:
    """Detached immutable journal state and exact Q62 origin binding."""

    origin: L43OriginAnchor
    state: DurableState
    last_sequence: int
    journal_sha256: str
    sell_review_pending: bool
    review_active: bool
    manual_close_required: bool
    manual_follow_up_required: bool

    def __post_init__(self) -> None:
        if type(self.origin) is not L43OriginAnchor:
            raise TypeError("snapshot requires an L43 origin anchor")
        if type(self.state) is not DurableState:
            raise TypeError("snapshot requires immutable durable state")
        if self.state.l43_origin != self.origin:
            raise ValueError("snapshot origin differs from the journal genesis")
        if self.last_sequence != self.state.last_sequence:
            raise ValueError("snapshot sequence differs from durable state")
        if self.journal_sha256 != self.state.journal_hash:
            raise ValueError("snapshot digest differs from durable state")
        if self.sell_review_pending != self.state.sell_review_pending:
            raise ValueError("snapshot review status differs from durable state")
        if type(self.review_active) is not bool:
            raise TypeError("snapshot review activity must be boolean")
        if self.review_active and not self.sell_review_pending:
            raise ValueError("active review must have a durable pending attempt")
        if type(self.manual_close_required) is not bool:
            raise TypeError("snapshot manual-close status must be boolean")
        if type(self.manual_follow_up_required) is not bool:
            raise TypeError("snapshot manual-follow-up status must be boolean")
        expected_manual_close = self.state.manual_close_required or (
            self.sell_review_pending and not self.review_active
        )
        if self.manual_close_required != expected_manual_close:
            raise ValueError("snapshot manual-close state differs from replay facts")


def origin_anchor_from_q62(origin: object) -> L43OriginAnchor:
    """Bind only the exact accepted consumed-Q62 origin fields."""

    from trading_bot.live_prototype.l43_production_owner import Q62JournalOrigin

    if type(origin) is not Q62JournalOrigin:
        raise TypeError("the accepted typed Q62 journal origin is required")
    return L43OriginAnchor(
        runtime_identity=origin.runtime_identity,
        journal_sha256=origin.journal_sha256,
        initialization_event_sha256=origin.initialization_event_sha256,
        consumed_observation_sha256=origin.consumed_observation_sha256,
        journal_label=origin.journal_label,
    )


def read_canonical_l43_origin_anchor() -> L43OriginAnchor:
    """Read the source-pinned Q62 origin without creating any L43 state."""

    from trading_bot.live_prototype.l43_production_owner import (
        read_canonical_q62_origin,
    )

    return origin_anchor_from_q62(read_canonical_q62_origin())


def _file_identity(info: os.stat_result) -> tuple[int, int]:
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or not info.st_ino
        or getattr(info, "st_file_attributes", 0) & _REPARSE_POINT
    ):
        raise L43StateUnavailable("L43 state path is not a private regular file")
    return info.st_dev, info.st_ino


def _validate_state_path(path: Path) -> tuple[int, int]:
    if not path.is_absolute():
        raise L43StateUnavailable("L43 state path must be absolute")
    try:
        for candidate in (path, *path.parents):
            info = candidate.lstat()
            if (
                stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & _REPARSE_POINT
            ):
                raise L43StateUnavailable("L43 state path contains a link")
        return _file_identity(path.lstat())
    except FileNotFoundError:
        raise L43StateUnavailable("pre-provisioned L43 state is missing") from None
    except OSError:
        raise L43StateUnavailable("L43 state path is unavailable") from None


class _ExclusiveFileLock(AbstractContextManager[None]):
    """Small OS-backed, nonblocking single-writer lifetime lock."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._stream: BinaryIO | None = None
        self._identity: tuple[int, int] | None = None

    def __enter__(self) -> None:
        if not self.path.is_absolute():
            raise L43StateUnavailable("L43 lock path must be absolute")
        descriptor: int | None = None
        stream: BinaryIO | None = None
        try:
            for candidate in (self.path.parent, *self.path.parent.parents):
                info = candidate.lstat()
                if (
                    stat.S_ISLNK(info.st_mode)
                    or getattr(info, "st_file_attributes", 0) & _REPARSE_POINT
                ):
                    raise L43StateUnavailable("L43 lock path contains a link")
            lock_identity = _file_identity(self.path.lstat())
            flags = os.O_RDWR | getattr(os, "O_BINARY", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(self.path, flags, 0o600)
            stream = os.fdopen(descriptor, "r+b")
            descriptor = None
            identity = _file_identity(os.fstat(stream.fileno()))
            if (
                identity != lock_identity
                or _file_identity(self.path.lstat()) != identity
            ):
                stream.close()
                raise L43StateUnavailable("L43 lock identity changed")
            if os.name == "nt":
                import msvcrt

                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._stream = stream
            self._identity = identity
            return None
        except L43StateUnavailable:
            if stream is not None:
                stream.close()
            elif descriptor is not None:
                os.close(descriptor)
            raise
        except FileNotFoundError:
            if stream is not None:
                stream.close()
            elif descriptor is not None:
                os.close(descriptor)
            raise L43StateUnavailable("L43 state lock is not provisioned") from None
        except OSError:
            if stream is not None:
                stream.close()
            elif descriptor is not None:
                os.close(descriptor)
            raise L43StateUnavailable(
                "another L43 state owner holds the lock"
            ) from None

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        stream = self._stream
        identity = self._identity
        self._stream = None
        self._identity = None
        if stream is None or identity is None:
            return None
        try:
            if _file_identity(self.path.lstat()) != identity:
                raise L43StateUnavailable("L43 lock identity changed")
        finally:
            stream.close()
        return None


class L43StateSession:
    """Guarded controller facade held under one OS lock for the full session."""

    __slots__ = (
        "path",
        "origin",
        "_lock_context",
        "_controller",
        "_active",
        "_review_binding_started_here",
        "_review_session_token",
        "_reserved_here",
    )

    def __init__(self, path: Path, expected_origin: L43OriginAnchor) -> None:
        if not isinstance(path, Path):
            raise TypeError("L43 state path must be a concrete Path")
        if type(expected_origin) is not L43OriginAnchor:
            raise TypeError("L43 session requires the accepted typed Q62 origin")
        self.path = path
        self.origin = expected_origin
        self._lock_context: _ExclusiveFileLock | None = None
        self._controller: LiveController | None = None
        self._active = False
        self._review_binding_started_here: tuple[str, str] | None = None
        self._review_session_token: object | None = None
        self._reserved_here: set[str] = set()

    @classmethod
    def open_existing(
        cls, path: Path, expected_origin: L43OriginAnchor
    ) -> L43StateSession:
        """Open only an existing exact-origin state journal; never initialize."""

        return cls(path, expected_origin)

    @classmethod
    def for_production(cls) -> L43StateSession:
        """Use the fixed path and canonical Q62 origin; require provisioning."""

        return cls(L43_STATE_PATH, read_canonical_l43_origin_anchor())

    def __enter__(self) -> L43StateSession:
        if self._active:
            raise L43StateUnavailable("L43 state session is already active")
        state_identity = _validate_state_path(self.path)
        lock_context = _ExclusiveFileLock(
            self.path.with_suffix(self.path.suffix + ".lock")
        )
        lock_context.__enter__()
        try:
            if _validate_state_path(self.path) != state_identity:
                raise L43StateUnavailable("L43 state identity changed during lock")
            try:
                store = DurableStateStore.open(self.path, self.origin.runtime_identity)
            except Exception:
                raise L43StateUnavailable("L43 state journal is invalid") from None
            if store.state.l43_origin != self.origin:
                raise L43StateUnavailable("L43 state has a different Q62 origin")
            self._controller = LiveController(store)
            self._lock_context = lock_context
            self._active = True
            self._review_binding_started_here = None
            self._review_session_token = object()
            self._reserved_here = set()
            return self
        except Exception:
            lock_context.__exit__(None, None, None)
            raise

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self._active = False
        self._controller = None
        self._review_binding_started_here = None
        self._review_session_token = None
        self._reserved_here.clear()
        lock_context = self._lock_context
        self._lock_context = None
        if lock_context is not None:
            lock_context.__exit__(exc_type, exc, traceback)
        return None

    def _require_active(self) -> LiveController:
        if not self._active or self._controller is None:
            raise L43StateUnavailable("L43 state session is not active")
        return self._controller

    @property
    def state(self) -> DurableState:
        return self._require_active().state

    @property
    def manual_close_required(self) -> bool:
        controller = self._require_active()
        return controller.state.manual_close_required or (
            controller.state.sell_review_pending
            and self._review_binding_started_here is None
        )

    @property
    def manual_follow_up_required(self) -> bool:
        state = self._require_active().state
        reserved_exit_is_active = (
            state.exit is not None and state.exit.intent_id in self._reserved_here
        )
        return state.manual_follow_up_required and not (
            reserved_exit_is_active
            and state.exit is not None
            and state.exit.status is IntentStatus.RESERVED
            and not state.manual_close_required
        )

    def snapshot(self) -> L43StateSnapshot:
        """Return a detached view while retaining the caller's session lock."""

        state = self._require_active().state
        if state.l43_origin != self.origin:
            raise L43StateUnavailable("L43 state origin changed during session")
        return L43StateSnapshot(
            origin=self.origin,
            state=state,
            last_sequence=state.last_sequence,
            journal_sha256=state.journal_hash,
            sell_review_pending=state.sell_review_pending,
            review_active=self._review_binding_started_here is not None,
            manual_close_required=self.manual_close_required,
            manual_follow_up_required=self.manual_follow_up_required,
        )

    def reserve_entry(self, requested_dollars: Decimal) -> str:
        intent_id = self._require_active().reserve_entry(requested_dollars)
        self._reserved_here.add(intent_id)
        return intent_id

    def reserve_exit(
        self, requested_quantity: Decimal, *, authority_sha256: str | None = None
    ) -> str:
        intent_id = self._require_active().reserve_exit(
            requested_quantity,
            authority_sha256=authority_sha256,
        )
        self._reserved_here.add(intent_id)
        return intent_id

    def prepare_invocation(self, intent_id: str) -> PreparedInvocation:
        if intent_id not in self._reserved_here:
            raise L43StateUnavailable(
                "intent was not reserved in the active L43 session"
            )
        self._reserved_here.remove(intent_id)
        return self._require_active().prepare_invocation(intent_id)

    def bind_provider_order(self, intent_id: str, provider_order_id: str) -> None:
        self._require_active().bind_provider_order(intent_id, provider_order_id)

    def mark_unknown(self, intent_id: str) -> None:
        self._require_active().mark_unknown(intent_id)

    def reconcile(self, snapshot: ReconciliationSnapshot) -> DurableState:
        return self._require_active().reconcile(snapshot)

    def begin_sell_review(self, *, proposal_sha256: str, arguments_sha256: str) -> None:
        self._require_active().begin_sell_review(
            proposal_sha256=proposal_sha256,
            arguments_sha256=arguments_sha256,
            session_token=self._review_session_token,
        )
        self._review_binding_started_here = (proposal_sha256, arguments_sha256)

    def accept_sell_review(
        self,
        *,
        proposal_sha256: str,
        arguments_sha256: str,
        review_evidence_sha256: str,
    ) -> None:
        if self._review_binding_started_here != (
            proposal_sha256,
            arguments_sha256,
        ):
            raise L43StateUnavailable(
                "sell review cannot be accepted outside its active session"
            )
        self._require_active().accept_sell_review(
            proposal_sha256=proposal_sha256,
            arguments_sha256=arguments_sha256,
            review_evidence_sha256=review_evidence_sha256,
            session_token=self._review_session_token,
        )
        self._review_binding_started_here = None

    def require_manual_close(
        self,
        *,
        trigger: ManualCloseTrigger,
        effect_evidence_sha256: str,
    ) -> ManualCloseRequired:
        result = self._require_active().require_manual_close(
            trigger=trigger,
            effect_evidence_sha256=effect_evidence_sha256,
        )
        self._review_binding_started_here = None
        return result


def read_l43_state_snapshot(
    path: Path, expected_origin: L43OriginAnchor
) -> L43StateSnapshot:
    """Read immutable L43 state under the single-writer lock and release it."""

    with L43StateSession.open_existing(path, expected_origin) as session:
        return session.snapshot()


def read_production_l43_state_snapshot() -> L43StateSnapshot:
    return read_l43_state_snapshot(L43_STATE_PATH, read_canonical_l43_origin_anchor())


__all__ = [
    "L43_STATE_PATH",
    "L43StateSession",
    "L43StateSnapshot",
    "L43StateUnavailable",
    "origin_anchor_from_q62",
    "read_canonical_l43_origin_anchor",
    "read_l43_state_snapshot",
    "read_production_l43_state_snapshot",
]
