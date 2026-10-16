"""GUI-owned, immutable recorded runtime evidence. No execution authority."""

from __future__ import annotations

import re
from dataclasses import dataclass, fields
from datetime import date, datetime
from enum import Enum
from uuid import UUID

MAX_RUNTIME_EVIDENCE_BYTES = 32 * 1024
MAX_RUNTIME_COUNT = 1_000_000
MAX_RUNTIME_HISTORY = 253


class RuntimePageStatus(Enum):
    UNAVAILABLE = "UNAVAILABLE"
    AVAILABLE = "AVAILABLE"
    ATTENTION = "ATTENTION"


class RuntimeDiagnostic(Enum):
    NO_EVIDENCE = "No production-runtime evidence is selected."
    RECORDED = "Recorded runtime evidence is available."
    BLOCKED = "Recorded runtime evidence requires attention."
    INVALID = "Selected runtime evidence is unreadable or invalid."
    CONFLICTING = "Qualification and session source identities conflict."


class RuntimeAclStatus(Enum):
    BLOCKED = "BLOCKED"
    NEEDS_PROVISIONING = "NEEDS_PROVISIONING"
    PROVISIONED = "PROVISIONED"
    ALREADY_PROVISIONED = "ALREADY_PROVISIONED"
    STOPPED_AFTER_APPLY = "STOPPED_AFTER_APPLY"


class RuntimeResult(Enum):
    PASS = "PASS"
    FAIL = "FAIL"


class RuntimeQualificationStatus(Enum):
    BLOCKED = "BLOCKED"
    READY_FOR_MANUAL_PAPER_SESSION = "READY_FOR_MANUAL_PAPER_SESSION"


class RuntimeProvisionStatus(Enum):
    NOT_QUALIFIED = "NOT_QUALIFIED"
    PROVISIONED = "PROVISIONED"
    ALREADY_PROVISIONED = "ALREADY_PROVISIONED"


class RuntimeWriteReadiness(Enum):
    NOT_CHECKED = "NOT_CHECKED"
    BLOCKED = "BLOCKED"
    WRITE_READY = "WRITE_READY"


class RuntimeSessionStatus(Enum):
    ADMITTED = "ADMITTED"
    HISTORY_STARTED = "HISTORY_STARTED"
    HISTORY_READY = "HISTORY_READY"
    NO_SIGNAL = "NO_SIGNAL"
    WAITING_FOR_MARKET = "WAITING_FOR_MARKET"
    PREPARING = "PREPARING"
    READY_TO_PROCEED = "READY_TO_PROCEED"
    EXECUTE_STARTED = "EXECUTE_STARTED"
    PAPER_EXECUTED = "PAPER_EXECUTED"
    RISK_REJECTED = "RISK_REJECTED"
    SESSION_NOT_ADMITTED = "SESSION_NOT_ADMITTED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    BLOCKED = "BLOCKED"
    ALREADY_COMPLETED = "ALREADY_COMPLETED"


class RuntimeStrategyOutcome(Enum):
    NO_SIGNAL = "NO_SIGNAL"
    TRADE_PROPOSAL = "TRADE_PROPOSAL"


class RuntimePrepareResult(Enum):
    SESSION_NOT_ADMITTED = "SESSION_NOT_ADMITTED"
    SESSION_EXPIRED_DURING_ACQUISITION = "SESSION_EXPIRED_DURING_ACQUISITION"
    RISK_REJECTED = "RISK_REJECTED"
    READY_TO_PROCEED = "READY_TO_PROCEED"


def _enum(value: object, kind: type[Enum]) -> None:
    if type(value) is not kind:
        raise TypeError("Unsupported runtime classification")


def _hex(value: object, length: int) -> None:
    if type(value) is not str or re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is None:
        raise ValueError("Invalid runtime digest")


def _count(value: object, bound: int = MAX_RUNTIME_COUNT) -> None:
    if type(value) is not int or not 0 <= value <= bound:
        raise ValueError("Invalid bounded runtime count")


@dataclass(frozen=True, slots=True)
class RuntimeAclEvidenceView:
    status: RuntimeAclStatus
    result: RuntimeResult
    runtime_sid_digest: str | None
    acl_apply_attempts: int
    acl_applies_verified: int
    parent_mutations: int
    recursive_mutations: int
    credential_mutations: int
    scheduler_mutations: int
    provider_calls: int
    paper_mutations: int
    session_mutations: int
    broker_mutations: int

    def __post_init__(self) -> None:
        _enum(self.status, RuntimeAclStatus)
        _enum(self.result, RuntimeResult)
        if self.runtime_sid_digest is not None:
            _hex(self.runtime_sid_digest, 64)
        for field in fields(self)[3:]:
            _count(getattr(self, field.name))


@dataclass(frozen=True, slots=True)
class RuntimeQualificationEvidenceView:
    source_head: str
    source_tree: str
    status: RuntimeQualificationStatus
    runtime_status: RuntimeProvisionStatus
    paper_records: int | None
    session_reservations: int | None
    paper_store_write_readiness: RuntimeWriteReadiness
    session_store_write_readiness: RuntimeWriteReadiness
    alpaca_credential_reads: int | None
    robinhood_credential_reads: int | None
    persisted_oauth_available: bool
    alpaca_http_calls: int
    robinhood_application_calls: int
    paper_trade_mutations: int
    scheduler_mutations: int
    broker_mutations: int
    effect_counts_complete: bool

    def __post_init__(self) -> None:
        _hex(self.source_head, 40)
        _hex(self.source_tree, 40)
        _enum(self.status, RuntimeQualificationStatus)
        _enum(self.runtime_status, RuntimeProvisionStatus)
        _enum(self.paper_store_write_readiness, RuntimeWriteReadiness)
        _enum(self.session_store_write_readiness, RuntimeWriteReadiness)
        for name in ("persisted_oauth_available", "effect_counts_complete"):
            if type(getattr(self, name)) is not bool:
                raise TypeError("Exact runtime boolean required")
        for name in (
            "paper_records",
            "session_reservations",
            "alpaca_credential_reads",
            "robinhood_credential_reads",
        ):
            value = getattr(self, name)
            if value is not None:
                _count(value)
        for field in fields(self)[11:16]:
            _count(getattr(self, field.name))


@dataclass(frozen=True, slots=True)
class RuntimeSessionEvidenceView:
    source_head: str
    source_tree: str
    contract_id: UUID
    target_session: date
    historical_provider: str
    historical_sessions: tuple[date, ...]
    operation_id: UUID
    order_id: UUID | None
    fill_id: UUID | None
    strategy_outcome: RuntimeStrategyOutcome | None
    proposal_id: UUID | None
    wait_started_at: datetime | None
    admitted_at: datetime | None
    admission_opens_at: datetime | None
    admission_closes_at: datetime | None
    prepare_result: RuntimePrepareResult | None
    execute_result: RuntimeResult | None
    alpaca_reads: int
    strategy_evaluations: int
    prepare_attempts: int
    execute_attempts: int
    robinhood_get_equity_quotes: int
    robinhood_get_accounts: int
    robinhood_get_equity_orders: int
    robinhood_review_equity_order: int
    paper_mutations: int | None
    broker_placement_count: int
    effect_counts_complete: bool
    status: RuntimeSessionStatus

    def __post_init__(self) -> None:
        _hex(self.source_head, 40)
        _hex(self.source_tree, 40)
        _enum(self.status, RuntimeSessionStatus)
        if (
            type(self.historical_provider) is not str
            or self.historical_provider != "alpaca"
        ):
            raise ValueError("Unsupported historical provider")
        if type(self.target_session) is not date:
            raise TypeError("Exact session date required")
        if (
            type(self.historical_sessions) is not tuple
            or len(self.historical_sessions) > MAX_RUNTIME_HISTORY
        ):
            raise ValueError("Invalid bounded history sequence")
        if any(type(item) is not date for item in self.historical_sessions):
            raise TypeError("Exact historical dates required")
        for name in (
            "contract_id",
            "operation_id",
            "order_id",
            "fill_id",
            "proposal_id",
        ):
            value = getattr(self, name)
            if value is None and name in {"order_id", "fill_id", "proposal_id"}:
                continue
            if type(value) is not UUID:
                raise TypeError("Exact runtime UUID required")
        for name in (
            "wait_started_at",
            "admitted_at",
            "admission_opens_at",
            "admission_closes_at",
        ):
            value = getattr(self, name)
            if value is not None and (
                type(value) is not datetime
                or value.tzinfo is None
                or value.utcoffset() is None
            ):
                raise ValueError("Timezone-aware runtime timestamp required")
        for name, kind in (
            ("strategy_outcome", RuntimeStrategyOutcome),
            ("prepare_result", RuntimePrepareResult),
            ("execute_result", RuntimeResult),
        ):
            value = getattr(self, name)
            if value is not None:
                _enum(value, kind)
        if self.execute_result is RuntimeResult.FAIL:
            raise ValueError("Unsupported session execute result")
        if type(self.effect_counts_complete) is not bool:
            raise TypeError("Exact runtime boolean required")
        for name, bound in (
            ("alpaca_reads", 253),
            ("strategy_evaluations", 1),
            ("prepare_attempts", 1),
            ("execute_attempts", 1),
            ("robinhood_get_equity_quotes", 1),
            ("robinhood_get_accounts", 1),
            ("robinhood_get_equity_orders", 202),
            ("robinhood_review_equity_order", 1),
            ("paper_mutations", 1),
            ("broker_placement_count", 0),
        ):
            value = getattr(self, name)
            if (
                name == "paper_mutations"
                and value is None
                and not self.effect_counts_complete
            ):
                continue
            _count(value, bound)


@dataclass(frozen=True, slots=True)
class RuntimePageState:
    status: RuntimePageStatus
    diagnostic: RuntimeDiagnostic
    acl: RuntimeAclEvidenceView | None = None
    qualification: RuntimeQualificationEvidenceView | None = None
    session: RuntimeSessionEvidenceView | None = None

    def __post_init__(self) -> None:
        _enum(self.status, RuntimePageStatus)
        _enum(self.diagnostic, RuntimeDiagnostic)
        for value, kind in (
            (self.acl, RuntimeAclEvidenceView),
            (self.qualification, RuntimeQualificationEvidenceView),
            (self.session, RuntimeSessionEvidenceView),
        ):
            if value is not None and type(value) is not kind:
                raise TypeError("Exact runtime evidence view required")
        expected = {
            RuntimeDiagnostic.NO_EVIDENCE: RuntimePageStatus.UNAVAILABLE,
            RuntimeDiagnostic.RECORDED: RuntimePageStatus.AVAILABLE,
            RuntimeDiagnostic.BLOCKED: RuntimePageStatus.ATTENTION,
            RuntimeDiagnostic.INVALID: RuntimePageStatus.ATTENTION,
            RuntimeDiagnostic.CONFLICTING: RuntimePageStatus.ATTENTION,
        }[self.diagnostic]
        if self.status is not expected:
            raise ValueError("Runtime status and diagnostic conflict")
        if self.status is RuntimePageStatus.UNAVAILABLE and any(
            (self.acl, self.qualification, self.session)
        ):
            raise ValueError("Unavailable runtime cannot contain evidence")
        if self.status is RuntimePageStatus.AVAILABLE and not any(
            (self.acl, self.qualification, self.session)
        ):
            raise ValueError("Available runtime requires evidence")

    @property
    def message(self) -> str:
        return self.diagnostic.value


def unavailable_runtime_state() -> RuntimePageState:
    """Deterministic default with no paths or runtime I/O."""
    return RuntimePageState(
        RuntimePageStatus.UNAVAILABLE, RuntimeDiagnostic.NO_EVIDENCE
    )
