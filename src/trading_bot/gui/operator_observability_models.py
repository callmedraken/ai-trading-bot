"""Immutable Qt-free presentation records for PD4 operator observability."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

OPERATOR_WARMUP_TARGET_COUNT = 6
MAX_OPERATOR_SYMBOL_CHARACTERS = 10


def _require_operator_symbol(symbol: str) -> None:
    if type(symbol) is not str:
        raise TypeError("symbol must be an exact string")
    if (
        not symbol
        or symbol != symbol.strip()
        or len(symbol) > MAX_OPERATOR_SYMBOL_CHARACTERS
        or any(
            not (
                "A" <= character <= "Z" or "0" <= character <= "9" or character in ".-"
            )
            for character in symbol
        )
    ):
        raise ValueError("symbol must be canonical presentation text")


class OperatorWarmupClassification(Enum):
    """Bounded presentation classification for the selected-C3 warm-up window."""

    WARMING_UP = "warming_up"
    READY = "ready"
    SESSION_GAP = "session_gap"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class SelectedC3WarmupSessionView:
    """Bounded nonsecret facts for one selected session in the warm-up window."""

    session_date: date
    symbol: str
    close: Decimal
    snapshot_id: UUID
    selection_id: UUID

    def __post_init__(self) -> None:
        if type(self.session_date) is not date:
            raise TypeError("session_date must be an exact date")
        _require_operator_symbol(self.symbol)
        if (
            type(self.close) is not Decimal
            or not self.close.is_finite()
            or self.close <= 0
        ):
            raise ValueError("close must be a positive finite Decimal")
        if type(self.snapshot_id) is not UUID:
            raise TypeError("snapshot_id must be a UUID")
        if type(self.selection_id) is not UUID:
            raise TypeError("selection_id must be a UUID")


@dataclass(frozen=True, slots=True)
class OperatorEffectGateState:
    """Read-only presentation of the eight committed/process-local effect gates."""

    market_data_capture: bool
    decision_publication: bool
    production: bool
    recovery: bool
    supervised_execution: bool
    receipt_recovery: bool
    unattended_execution: bool
    unattended_storage_provisioning: bool

    def __post_init__(self) -> None:
        if any(
            type(value) is not bool
            for value in (
                self.market_data_capture,
                self.decision_publication,
                self.production,
                self.recovery,
                self.supervised_execution,
                self.receipt_recovery,
                self.unattended_execution,
                self.unattended_storage_provisioning,
            )
        ):
            raise TypeError("effect-gate values must be exact bools")

    @property
    def all_closed(self) -> bool:
        """Return whether every displayed effect gate is closed."""
        return not any(
            (
                self.market_data_capture,
                self.decision_publication,
                self.production,
                self.recovery,
                self.supervised_execution,
                self.receipt_recovery,
                self.unattended_execution,
                self.unattended_storage_provisioning,
            )
        )

    def as_tuple(self) -> tuple[bool, bool, bool, bool, bool, bool, bool, bool]:
        """Return the stable display ordering used by the current PD4 gate set."""
        return (
            self.market_data_capture,
            self.decision_publication,
            self.production,
            self.recovery,
            self.supervised_execution,
            self.receipt_recovery,
            self.unattended_execution,
            self.unattended_storage_provisioning,
        )


@dataclass(frozen=True, slots=True)
class OperatorWarmupView:
    """One bounded read-only view of the six-session selected-C3 window."""

    classification: OperatorWarmupClassification
    required_sessions: tuple[date, ...]
    selected_sessions: tuple[SelectedC3WarmupSessionView, ...]
    target_count: int = OPERATOR_WARMUP_TARGET_COUNT

    def __post_init__(self) -> None:
        if type(self.classification) is not OperatorWarmupClassification:
            raise TypeError("classification must be an OperatorWarmupClassification")
        if (
            type(self.target_count) is not int
            or self.target_count != OPERATOR_WARMUP_TARGET_COUNT
        ):
            raise ValueError("target_count must equal the frozen six-session target")

        try:
            required = tuple(self.required_sessions)
        except TypeError as error:
            raise TypeError("required_sessions must be iterable") from error
        if len(required) != OPERATOR_WARMUP_TARGET_COUNT:
            raise ValueError("required_sessions must contain exactly six dates")
        if any(type(item) is not date for item in required):
            raise TypeError("required_sessions must contain exact dates")
        if len(set(required)) != len(required) or tuple(sorted(required)) != required:
            raise ValueError("required_sessions must be unique and increasing")

        try:
            selected = tuple(self.selected_sessions)
        except TypeError as error:
            raise TypeError("selected_sessions must be iterable") from error
        if any(type(item) is not SelectedC3WarmupSessionView for item in selected):
            raise TypeError(
                "selected_sessions must contain SelectedC3WarmupSessionView values"
            )
        selected_dates = tuple(item.session_date for item in selected)
        if len(set(selected_dates)) != len(selected_dates):
            raise ValueError("selected session dates must be unique")
        if any(item not in required for item in selected_dates):
            raise ValueError("selected session dates must belong to required_sessions")
        if tuple(sorted(selected_dates)) != selected_dates:
            raise ValueError("selected session dates must be increasing")

        if (
            self.classification is OperatorWarmupClassification.READY
            and len(selected) != self.target_count
        ):
            raise ValueError("READY warm-up state requires six selected sessions")
        if (
            self.classification is OperatorWarmupClassification.WARMING_UP
            and len(selected) >= self.target_count
        ):
            raise ValueError("WARMING_UP must contain fewer than six selected sessions")
        if self.classification is OperatorWarmupClassification.BLOCKED and selected:
            raise ValueError("BLOCKED warm-up state must not expose selected sessions")

        object.__setattr__(self, "required_sessions", required)
        object.__setattr__(self, "selected_sessions", selected)

    @property
    def selected_count(self) -> int:
        """Return the number of selected sessions in the displayed window."""
        return len(self.selected_sessions)

    @property
    def missing_sessions(self) -> tuple[date, ...]:
        """Return required sessions not represented by selected-C3 evidence."""
        selected_dates = {item.session_date for item in self.selected_sessions}
        return tuple(
            session
            for session in self.required_sessions
            if session not in selected_dates
        )


@dataclass(frozen=True, slots=True)
class OperatorObservabilityState:
    """Pure presentation state for the first operator-observability slice."""

    warmup: OperatorWarmupView
    gates: OperatorEffectGateState

    def __post_init__(self) -> None:
        if type(self.warmup) is not OperatorWarmupView:
            raise TypeError("warmup must be an OperatorWarmupView")
        if type(self.gates) is not OperatorEffectGateState:
            raise TypeError("gates must be an OperatorEffectGateState")


MAX_OPERATOR_MESSAGE_CHARACTERS = 1000
MAX_OPERATOR_ACCOUNT_ID_CHARACTERS = 128
MAX_OPERATOR_CLASSIFICATION_CHARACTERS = 64
MAX_OPERATOR_POSITIONS = 128


class OperatorOperationsPageStatus(Enum):
    """Availability of one bounded Operations-page snapshot."""

    UNAVAILABLE = "unavailable"
    AVAILABLE = "available"


@dataclass(frozen=True, slots=True)
class OperatorAccountPositionView:
    """Bounded current Paper-v2 position facts for Operations presentation."""

    symbol: str
    quantity: Decimal
    total_cost_basis: Decimal
    average_cost: Decimal

    def __post_init__(self) -> None:
        _require_operator_symbol(self.symbol)
        for name in ("quantity", "total_cost_basis", "average_cost"):
            value = getattr(self, name)
            if type(value) is not Decimal or not value.is_finite() or value <= 0:
                raise ValueError(f"{name} must be a positive finite Decimal")


@dataclass(frozen=True, slots=True)
class OperatorAccountSummaryView:
    """Bounded current Paper-v2 account summary for operator display."""

    paper_account_id: str
    checkpoint_id: UUID
    sequence: int
    as_of: datetime
    cash: Decimal
    realized_profit_loss: Decimal
    positions: tuple[OperatorAccountPositionView, ...]
    lineage_edge_count: int
    receipt_count: int

    def __post_init__(self) -> None:
        if (
            type(self.paper_account_id) is not str
            or not self.paper_account_id
            or self.paper_account_id != self.paper_account_id.strip()
            or len(self.paper_account_id) > MAX_OPERATOR_ACCOUNT_ID_CHARACTERS
        ):
            raise ValueError("paper_account_id is invalid")
        if type(self.checkpoint_id) is not UUID:
            raise TypeError("checkpoint_id must be a UUID")
        if type(self.sequence) is not int or self.sequence < 0:
            raise ValueError("sequence must be a nonnegative int")
        if (
            type(self.as_of) is not datetime
            or self.as_of.tzinfo is None
            or self.as_of.utcoffset() is None
        ):
            raise ValueError("as_of must be timezone-aware")
        if type(self.cash) is not Decimal or not self.cash.is_finite() or self.cash < 0:
            raise ValueError("cash must be a nonnegative finite Decimal")
        if (
            type(self.realized_profit_loss) is not Decimal
            or not self.realized_profit_loss.is_finite()
        ):
            raise ValueError("realized_profit_loss must be a finite Decimal")
        positions = tuple(self.positions)
        if len(positions) > MAX_OPERATOR_POSITIONS or any(
            type(item) is not OperatorAccountPositionView for item in positions
        ):
            raise ValueError("positions are invalid")
        if len({item.symbol for item in positions}) != len(positions):
            raise ValueError("position symbols must be unique")
        for name in ("lineage_edge_count", "receipt_count"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative int")
        object.__setattr__(self, "positions", positions)


class OperatorStrategyExplanationStatus(Enum):
    """Presentation classification from the source-owned crossover evaluator."""

    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    NO_CROSSOVER = "NO_CROSSOVER"
    POSITION_FILTERED = "POSITION_FILTERED"
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True, slots=True)
class OperatorStrategyExplanationView:
    """Exact deterministic MA inputs and result, carrying no publication authority."""

    status: OperatorStrategyExplanationStatus
    short_window: int
    long_window: int
    desired_quantity: Decimal
    symbol: str | None
    sessions: tuple[date, ...]
    closes: tuple[Decimal, ...]
    previous_short: Decimal | None
    previous_long: Decimal | None
    current_short: Decimal | None
    current_long: Decimal | None
    crossover_side: str | None
    actionable_side: str | None
    invested: bool

    def __post_init__(self) -> None:
        if type(self.status) is not OperatorStrategyExplanationStatus:
            raise TypeError("status must be an OperatorStrategyExplanationStatus")
        if (
            type(self.short_window) is not int
            or self.short_window <= 0
            or type(self.long_window) is not int
            or self.long_window <= self.short_window
        ):
            raise ValueError("strategy windows are invalid")
        if (
            type(self.desired_quantity) is not Decimal
            or not self.desired_quantity.is_finite()
            or self.desired_quantity <= 0
        ):
            raise ValueError("desired_quantity must be a positive finite Decimal")
        if self.symbol is not None:
            _require_operator_symbol(self.symbol)
        sessions = tuple(self.sessions)
        closes = tuple(self.closes)
        if len(sessions) != len(closes):
            raise ValueError("strategy sessions and closes must align")
        if any(type(value) is not date for value in sessions):
            raise TypeError("strategy sessions must contain exact dates")
        if tuple(sorted(sessions)) != sessions or len(set(sessions)) != len(sessions):
            raise ValueError("strategy sessions must be unique and increasing")
        if any(
            type(value) is not Decimal or not value.is_finite() or value <= 0
            for value in closes
        ):
            raise ValueError("strategy closes must be positive finite Decimals")
        if type(self.invested) is not bool:
            raise TypeError("invested must be an exact bool")
        if self.crossover_side not in (None, "BUY", "SELL"):
            raise ValueError("crossover_side is invalid")
        if self.actionable_side not in (None, "BUY", "SELL"):
            raise ValueError("actionable_side is invalid")

        averages = (
            self.previous_short,
            self.previous_long,
            self.current_short,
            self.current_long,
        )
        if self.status is OperatorStrategyExplanationStatus.INSUFFICIENT_HISTORY:
            if any(value is not None for value in averages) or any(
                value is not None
                for value in (self.crossover_side, self.actionable_side)
            ):
                raise ValueError(
                    "insufficient-history explanation cannot expose averages or sides"
                )
        else:
            if any(
                type(value) is not Decimal or not value.is_finite()
                for value in averages
            ):
                raise ValueError(
                    "complete strategy explanation requires finite Decimal averages"
                )
            if len(closes) != self.long_window + 1:
                raise ValueError(
                    "complete strategy explanation requires long_window + 1 closes"
                )

        object.__setattr__(self, "sessions", sessions)
        object.__setattr__(self, "closes", closes)


@dataclass(frozen=True, slots=True)
class OperatorOperationsPageState:
    """Immutable state rendered by the native read-only Operations page."""

    status: OperatorOperationsPageStatus
    message: str
    cycle_classification: str | None = None
    completed_session: date | None = None
    market_data_classification: str | None = None
    selected_snapshot_id: UUID | None = None
    warmup: OperatorWarmupView | None = None
    gates: OperatorEffectGateState | None = None
    account: OperatorAccountSummaryView | None = None
    strategy_explanation: OperatorStrategyExplanationView | None = None

    def __post_init__(self) -> None:
        if type(self.status) is not OperatorOperationsPageStatus:
            raise TypeError("status must be an OperatorOperationsPageStatus")
        if (
            type(self.message) is not str
            or not self.message.strip()
            or len(self.message) > MAX_OPERATOR_MESSAGE_CHARACTERS
        ):
            raise ValueError("message is invalid")

        for name in ("cycle_classification", "market_data_classification"):
            value = getattr(self, name)
            if value is not None and (
                type(value) is not str
                or not value
                or value != value.strip()
                or len(value) > MAX_OPERATOR_CLASSIFICATION_CHARACTERS
            ):
                raise ValueError(f"{name} is invalid")
        if (
            self.completed_session is not None
            and type(self.completed_session) is not date
        ):
            raise TypeError("completed_session must be an exact date or None")
        if (
            self.selected_snapshot_id is not None
            and type(self.selected_snapshot_id) is not UUID
        ):
            raise TypeError("selected_snapshot_id must be a UUID or None")

        details = (
            self.warmup,
            self.gates,
            self.account,
            self.strategy_explanation,
        )
        if self.status is OperatorOperationsPageStatus.UNAVAILABLE:
            if any(value is not None for value in details) or any(
                value is not None
                for value in (
                    self.cycle_classification,
                    self.completed_session,
                    self.market_data_classification,
                    self.selected_snapshot_id,
                )
            ):
                raise ValueError("unavailable Operations state cannot expose details")
            return

        if (
            type(self.gates) is not OperatorEffectGateState
            or type(self.account) is not OperatorAccountSummaryView
        ):
            raise ValueError("available Operations state requires gates and account")
        if (self.warmup is None) != (self.selected_snapshot_id is None):
            raise ValueError(
                "warmup and selected_snapshot_id must appear together or be absent"
            )
        if self.warmup is not None and type(self.warmup) is not OperatorWarmupView:
            raise TypeError("warmup must be an OperatorWarmupView or None")
        if (
            self.strategy_explanation is not None
            and type(self.strategy_explanation) is not OperatorStrategyExplanationView
        ):
            raise TypeError(
                "strategy_explanation must be an OperatorStrategyExplanationView or None"
            )

    @property
    def strategy_ready(self) -> bool:
        """Return whether the displayed selected-C3 window is strategy-ready."""
        return (
            self.warmup is not None
            and self.warmup.classification is OperatorWarmupClassification.READY
        )


def unavailable_operator_operations_state() -> OperatorOperationsPageState:
    """Return the deterministic safe default for an unconnected Operations page."""

    return OperatorOperationsPageState(
        status=OperatorOperationsPageStatus.UNAVAILABLE,
        message=(
            "Production operator observability is not connected to this GUI service."
        ),
    )
