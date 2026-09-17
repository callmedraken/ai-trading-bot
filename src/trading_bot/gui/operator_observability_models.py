"""Immutable Qt-free presentation records for PD4 operator observability."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from uuid import UUID

OPERATOR_WARMUP_TARGET_COUNT = 6
MAX_OPERATOR_SYMBOL_CHARACTERS = 10


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
        if type(self.symbol) is not str:
            raise TypeError("symbol must be an exact string")
        if (
            not self.symbol
            or self.symbol != self.symbol.strip()
            or len(self.symbol) > MAX_OPERATOR_SYMBOL_CHARACTERS
            or any(
                not (
                    "A" <= character <= "Z"
                    or "0" <= character <= "9"
                    or character in ".-"
                )
                for character in self.symbol
            )
        ):
            raise ValueError("symbol must be canonical presentation text")
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
            session for session in self.required_sessions if session not in selected_dates
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
