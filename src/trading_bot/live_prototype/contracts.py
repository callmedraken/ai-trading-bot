"""Frozen v1 cached presentation/service contracts. Construction performs no I/O."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class Lifecycle(StrEnum):
    DISARMED = "DISARMED"
    VALIDATING = "VALIDATING"
    READY = "READY"
    RUNNING = "RUNNING"
    RECONCILING = "RECONCILING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class Reason(StrEnum):
    SYNTHETIC_ONLY = "SYNTHETIC_ONLY"
    SOURCE_ACCEPTANCE_REQUIRED = "SOURCE_ACCEPTANCE_REQUIRED"
    DATA_NOT_READY = "DATA_NOT_READY"
    LIVE_STRATEGY_SELECTION_BLOCKED = "LIVE_STRATEGY_SELECTION_BLOCKED"
    EXIT_CAPABILITY_UNPROVEN = "EXIT_CAPABILITY_UNPROVEN"
    EXTERNAL_OPERATOR_REQUIRED = "EXTERNAL_OPERATOR_REQUIRED"
    WORKERS_STOPPED = "WORKERS_STOPPED"
    STOP_PENDING = "STOP_PENDING"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    COMMAND_REJECTED = "COMMAND_REJECTED"
    STALE_QUOTE = "STALE_QUOTE"
    MISSING_OFFICIAL_CLOSE = "MISSING_OFFICIAL_CLOSE"
    NO_ACTION = "NO_ACTION"
    AMBIGUOUS_EFFECT = "AMBIGUOUS_EFFECT"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"


class Command(StrEnum):
    START = "START"
    STOP = "STOP"
    KILL = "KILL"
    EXIT = "EXIT"


class EffectDisposition(StrEnum):
    NO_EFFECT = "NO_EFFECT"
    CONFIRMED = "CONFIRMED"
    MAY_HAVE_OCCURRED = "MAY_HAVE_OCCURRED"


@dataclass(frozen=True, slots=True)
class ActivityItem:
    sequence: int
    reason: Reason
    lifecycle: Lifecycle


@dataclass(frozen=True, slots=True)
class CandidateView:
    candidate: str
    base_return: str | None = None
    stress_return: str | None = None
    stress_drawdown: str | None = None
    turnover: str | None = None
    qualified: bool = False
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ResearchView:
    candidates: tuple[CandidateView, ...] = ()
    selected: str = "NOT_RUN"
    policy: str = "comparison-v2/qualification-v1"
    bundle_digest: str | None = None
    dataset_digest: str | None = None
    assumptions: tuple[str, ...] = ()
    prior_trials: int = 30
    new_trials: int = 3
    live_eligible: bool = False


@dataclass(frozen=True, slots=True)
class PrototypeSnapshot:
    lifecycle: Lifecycle = Lifecycle.DISARMED
    mode: str = "SYNTHETIC"
    connected: bool = False
    ready_to_trade: bool = False
    workers_running: bool = False
    strategy: str = "UNSELECTED"
    binding_digest: str | None = None
    source_head: str | None = None
    signal_as_of: str | None = None
    quote_as_of: str | None = None
    signal_fresh: bool = False
    quote_fresh: bool = False
    exposure: str | None = None
    owned_quantity: str | None = None
    working_orders: int | None = None
    fills: int | None = None
    entries_used: int = 0
    exits_used: int = 0
    reasons: tuple[Reason, ...] = (Reason.SYNTHETIC_ONLY,)
    activity: tuple[ActivityItem, ...] = ()
    research: ResearchView = ResearchView()


@dataclass(frozen=True, slots=True)
class PrototypeCommandResult:
    command: Command
    accepted: bool
    reason: Reason
    disposition: EffectDisposition = EffectDisposition.NO_EFFECT
    attempt_id: str | None = None
    evidence_id: str | None = None


class PrototypeApplicationService(Protocol):
    """All methods return cached facts or enqueue work; never block the Qt thread."""

    def snapshot(self) -> PrototypeSnapshot: ...
    def submit(self, command: Command) -> PrototypeCommandResult: ...
