"""Cached, factual Architecture 148 projection for the existing desktop window."""

from __future__ import annotations

import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from trading_bot.live_prototype.contracts import (
    ActivityItem,
    Command,
    Lifecycle,
    PrototypeCommandResult,
    PrototypeSnapshot,
    Reason,
    RestrictedLiveStatus,
)

from .worker import Arch148RuntimeWorker, WorkerLifecycle


@dataclass(frozen=True, slots=True)
class Arch148RuntimeDisplayFacts:
    """Already-cached, sanitized facts for one GUI refresh.

    The adapter does not query providers, inspect runtime state, or derive a
    position/stop/status.  The runtime service supplies this immutable snapshot
    from the same observations used by its planner and reconciler.
    """

    session: str = "UNAVAILABLE"
    strategy: str = "UNAVAILABLE"
    source_head: str | None = None
    source_tree: str | None = None
    binding_digest: str | None = None
    signal_as_of: datetime | None = None
    quote_as_of: datetime | None = None
    signal_fresh: bool = False
    quote_fresh: bool = False
    connected: bool = False
    current_regime: str | None = None
    entry_confirmation: str | None = None
    desired_position: str | None = None
    actual_position: str | None = None
    owned_quantity: Decimal | None = None
    working_orders: int | None = None
    fills: int | None = None
    entries_used: int = 0
    exits_used: int = 0
    latest_reconciled_fill: str | None = None
    hard_stop_price: Decimal | None = None
    protection_status: str = "UNAVAILABLE"
    pending_intent: str | None = None
    effect_status: str | None = None
    latest_result: str | None = None
    blockers: tuple[str, ...] = ()
    health: str = "UNKNOWN"
    reasons: tuple[Reason, ...] = (Reason.RECONCILIATION_REQUIRED,)
    restricted_live_status: RestrictedLiveStatus = RestrictedLiveStatus.STOPPED
    runtime_enabled: bool = False

    def __post_init__(self) -> None:
        for name in ("session", "strategy", "protection_status", "health"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a nonblank sanitized string")
        for name in ("signal_as_of", "quote_as_of"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, datetime) or value.tzinfo is None
            ):
                raise ValueError(f"{name} must be timezone-aware or None")
        for name in ("signal_fresh", "quote_fresh", "connected", "runtime_enabled"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be a bool")
        if self.owned_quantity is not None and not isinstance(
            self.owned_quantity, Decimal
        ):
            raise TypeError("owned_quantity must be Decimal or None")
        if self.owned_quantity is not None and not self.owned_quantity.is_finite():
            raise ValueError("owned_quantity must be finite")
        if self.hard_stop_price is not None and (
            not isinstance(self.hard_stop_price, Decimal)
            or not self.hard_stop_price.is_finite()
        ):
            raise ValueError("hard_stop_price must be finite Decimal or None")
        for name in ("working_orders", "fills", "entries_used", "exits_used"):
            value = getattr(self, name)
            if value is None and name in ("working_orders", "fills"):
                continue
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if re.fullmatch(r"[A-Z0-9_]{1,96}", self.health) is None:
            raise ValueError("health must be a sanitized reason code")
        if not isinstance(self.blockers, tuple) or not all(
            isinstance(value, str) and value.strip() for value in self.blockers
        ):
            raise TypeError("blockers must be a tuple of nonblank strings")
        if not isinstance(self.reasons, tuple) or not all(
            type(value) is Reason for value in self.reasons
        ):
            raise TypeError("reasons must be a tuple of Reason values")
        if type(self.restricted_live_status) is not RestrictedLiveStatus:
            raise TypeError("restricted_live_status must be a closed status value")

    def detail_lines(self) -> tuple[str, ...]:
        """Render each display value directly from its cached fact."""

        return (
            f"Session: {self.session}",
            f"Signal: {self.current_regime or 'Unavailable'}; confirmation: "
            f"{self.entry_confirmation or 'Unavailable'}",
            f"Desired position: {self.desired_position or 'Unavailable'}; actual: "
            f"{self.actual_position or 'Unavailable'}",
            f"Owned quantity: {_decimal_text(self.owned_quantity)}",
            f"Latest reconciled fill: {self.latest_reconciled_fill or 'Unavailable'}",
            f"Hard stop: {_decimal_text(self.hard_stop_price)}; protection: "
            f"{self.protection_status}",
            f"Pending intent: {self.pending_intent or 'None reported'}; effect: "
            f"{self.effect_status or 'None reported'}",
            f"Latest result: {self.latest_result or 'Unavailable'}",
            f"Blockers: {', '.join(self.blockers) or 'None reported'}",
            f"Source head/tree: {self.source_head or 'Unavailable'} / "
            f"{self.source_tree or 'Unavailable'}",
            f"Health: {self.health}",
        )


DisplayFactsReader = Callable[[], Arch148RuntimeDisplayFacts]


class Arch148RuntimeDisplayCache:
    """Small thread-safe cache shared by the worker and desktop projection."""

    def __init__(self, initial: Arch148RuntimeDisplayFacts | None = None) -> None:
        self._lock = threading.Lock()
        self._facts = initial or Arch148RuntimeDisplayFacts()

    def read(self) -> Arch148RuntimeDisplayFacts:
        with self._lock:
            return self._facts

    def publish(self, facts: Arch148RuntimeDisplayFacts) -> None:
        if type(facts) is not Arch148RuntimeDisplayFacts:
            raise TypeError("facts must be Arch148RuntimeDisplayFacts")
        with self._lock:
            self._facts = facts


class Arch148GuiAdapter:
    """Implement the existing PrototypeWindow service without GUI-side I/O."""

    def __init__(
        self,
        worker: Arch148RuntimeWorker,
        cached_facts: DisplayFactsReader,
    ) -> None:
        if not isinstance(worker, Arch148RuntimeWorker):
            raise TypeError("worker must be Arch148RuntimeWorker")
        if not callable(cached_facts):
            raise TypeError("cached_facts must read a cached runtime projection")
        self._worker = worker
        self._cached_facts = cached_facts
        self._activity_sequence = 0
        self._last_activity: tuple[ActivityItem, ...] = ()

    def snapshot(self) -> PrototypeSnapshot:
        facts = self._cached_facts()
        if type(facts) is not Arch148RuntimeDisplayFacts:
            raise TypeError("cached_facts must return Arch148RuntimeDisplayFacts")
        worker = self._worker.snapshot()
        lifecycle = _prototype_lifecycle(worker.lifecycle)
        reasons = facts.reasons
        if worker.error_code is not None:
            reasons = (Reason.RECONCILIATION_REQUIRED,)
        return PrototypeSnapshot(
            lifecycle=lifecycle,
            mode="RESTRICTED_LIVE",
            connected=facts.connected,
            ready_to_trade=False,
            workers_running=worker.lifecycle
            in (
                WorkerLifecycle.STARTING,
                WorkerLifecycle.RECONCILING,
                WorkerLifecycle.RUNNING,
                WorkerLifecycle.STOPPING,
            ),
            strategy=facts.strategy,
            binding_digest=facts.binding_digest,
            source_head=facts.source_head,
            signal_as_of=_iso(facts.signal_as_of),
            quote_as_of=_iso(facts.quote_as_of),
            signal_fresh=facts.signal_fresh,
            quote_fresh=facts.quote_fresh,
            exposure=facts.actual_position,
            owned_quantity=_decimal_text(facts.owned_quantity),
            working_orders=facts.working_orders,
            fills=facts.fills,
            entries_used=facts.entries_used,
            exits_used=facts.exits_used,
            reasons=reasons,
            activity=self._last_activity,
            restricted_live_status=facts.restricted_live_status,
            restricted_live_enabled=facts.runtime_enabled,
            effect_authority_granted=False,
            source_tree=facts.source_tree,
            restricted_live_reason_code=(worker.error_code or facts.health),
        )

    def display_details(self) -> tuple[str, ...]:
        facts = self._cached_facts()
        if type(facts) is not Arch148RuntimeDisplayFacts:
            raise TypeError("cached_facts must return Arch148RuntimeDisplayFacts")
        worker = self._worker.snapshot()
        worker_health = worker.error_code or worker.lifecycle.value
        return facts.detail_lines() + (f"Worker health: {worker_health}",)

    def submit(self, command: Command) -> PrototypeCommandResult:
        if type(command) is not Command:
            raise TypeError("command must be a Command")
        if command is Command.START:
            accepted = self._worker.start()
            reason = Reason.NO_ACTION if accepted else Reason.COMMAND_REJECTED
        elif command is Command.STOP:
            accepted = self._worker.stop()
            reason = Reason.STOP_PENDING if accepted else Reason.WORKERS_STOPPED
        elif command is Command.KILL:
            accepted = self._worker.kill()
            reason = (
                Reason.RECONCILIATION_REQUIRED if accepted else Reason.COMMAND_REJECTED
            )
        else:
            accepted = False
            reason = Reason.COMMAND_REJECTED
        if accepted:
            self._activity_sequence += 1
            lifecycle = _prototype_lifecycle(self._worker.snapshot().lifecycle)
            self._last_activity = (
                ActivityItem(self._activity_sequence, reason, lifecycle),
            )
        return PrototypeCommandResult(command=command, accepted=accepted, reason=reason)

    def request_report(self, path: Path) -> bool:
        del path
        return False

    def shutdown_complete(self) -> bool:
        return self._worker.shutdown_complete()


def create_arch148_window(service: object) -> object:
    """Lazily compose a window around an explicitly injected service.

    Importing this module or creating the service performs no provider, session,
    credential, thread, or Qt work.  The window is created only when this
    factory is explicitly called by desktop composition code.
    """

    if not all(
        callable(getattr(service, method, None))
        for method in ("snapshot", "submit", "request_report", "shutdown_complete")
    ):
        raise TypeError("service must implement the PrototypeWindow service protocol")
    snapshot = service.snapshot()
    if (
        not isinstance(snapshot, PrototypeSnapshot)
        or snapshot.mode != "RESTRICTED_LIVE"
    ):
        raise ValueError("Architecture 148 window requires a restricted-live snapshot")
    from trading_bot.live_prototype.window import PrototypeWindow

    return PrototypeWindow(service, mode="RESTRICTED_LIVE")


def _prototype_lifecycle(lifecycle: WorkerLifecycle) -> Lifecycle:
    return {
        WorkerLifecycle.STOPPED: Lifecycle.STOPPED,
        WorkerLifecycle.STARTING: Lifecycle.VALIDATING,
        WorkerLifecycle.RECONCILING: Lifecycle.RECONCILING,
        WorkerLifecycle.RUNNING: Lifecycle.RUNNING,
        WorkerLifecycle.STOPPING: Lifecycle.STOPPING,
        WorkerLifecycle.BLOCKED: Lifecycle.BLOCKED,
    }[lifecycle]


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _decimal_text(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None
