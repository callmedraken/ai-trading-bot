"""Pure deterministic preparation for one verified-snapshot paper cycle."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, time
from decimal import Context, Decimal, localcontext
from enum import StrEnum
from fractions import Fraction
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from trading_bot.domain import Symbol
from trading_bot.execution import PaperFillPolicy
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data import (
    CalendarDescriptor,
    DailySnapshotReplayError,
    DailySnapshotVerificationResult,
    DailySnapshotVerificationStatus,
    IdentifiedMarketCalendar,
    InvalidDailySnapshotCalendarError,
    ProviderDescriptor,
    replay_verified_daily_snapshot,
    require_matching_calendar,
)
from trading_bot.portfolio import (
    AllocationSource,
    MetadataEntry,
    PortfolioConstraints,
    PortfolioPositionState,
    PortfolioState,
    TargetAllocation,
    TargetPortfolio,
)
from trading_bot.rebalancing import (
    RebalanceAssumptions,
    RebalanceError,
    RebalancePlanner,
    RebalancePlanRequest,
    RebalanceProposalPolicy,
)
from trading_bot.risk import PortfolioRiskPolicy, RiskLimits
from trading_bot.runtime.exceptions import (
    InconsistentPreparedVerifiedSnapshotPaperCycleError,
    InvalidVerifiedSnapshotPaperCyclePreparationRequestError,
    VerifiedSnapshotPaperCyclePolicyError,
    VerifiedSnapshotPaperCyclePreparationError,
    VerifiedSnapshotPaperCycleSnapshotError,
    VerifiedSnapshotPaperCycleTargetError,
    VerifiedSnapshotPaperCycleTemporalError,
    VerifiedSnapshotPaperCycleUniverseError,
)

VERIFIED_SNAPSHOT_PAPER_CYCLE_PREPARATION_MATERIAL_VERSION = (
    "verified-snapshot-paper-cycle-preparation-v1"
)
VERIFIED_SNAPSHOT_PAPER_CYCLE_PREPARATION_NAMESPACE = UUID(
    "0aaf4d26-665b-5d2d-b823-83062d5d36e9"
)

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_ZERO = Decimal("0")
_ONE = Decimal("1")
_MAX_INPUT_SCALE = 18
_MAX_INPUT_SIGNIFICANT_DIGITS = 38
_MAX_INPUT_ADJUSTED_EXPONENT = 18
_ARITHMETIC_CONTEXT = Context(prec=1024, Emax=999_999, Emin=-999_999)


class VerifiedSnapshotPaperCyclePreparationDiagnosticCode(StrEnum):
    """Stable machine-readable preparation failure classifications."""

    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_DECIMAL = "INVALID_DECIMAL"
    SNAPSHOT_VERIFICATION_REQUIRED = "SNAPSHOT_VERIFICATION_REQUIRED"
    SNAPSHOT_REFERENCE_MISMATCH = "SNAPSHOT_REFERENCE_MISMATCH"
    SNAPSHOT_REPLAY_FAILED = "SNAPSHOT_REPLAY_FAILED"
    CALENDAR_MISMATCH = "CALENDAR_MISMATCH"
    ACCOUNT_UNIVERSE_MISMATCH = "ACCOUNT_UNIVERSE_MISMATCH"
    TARGET_UNIVERSE_MISMATCH = "TARGET_UNIVERSE_MISMATCH"
    OPEN_REFERENCE_UNIVERSE_MISMATCH = "OPEN_REFERENCE_UNIVERSE_MISMATCH"
    INVALID_ACCOUNT_STATE = "INVALID_ACCOUNT_STATE"
    TARGET_CASH_MISMATCH = "TARGET_CASH_MISMATCH"
    QUANTITY_TARGET_NOT_EXACTLY_REPRESENTABLE = (
        "QUANTITY_TARGET_NOT_EXACTLY_REPRESENTABLE"
    )
    PLANNER_VALIDATION_FAILED = "PLANNER_VALIDATION_FAILED"
    NEXT_SESSION_DERIVATION_FAILED = "NEXT_SESSION_DERIVATION_FAILED"
    OPEN_REFERENCE_SESSION_MISMATCH = "OPEN_REFERENCE_SESSION_MISMATCH"
    INVALID_CHRONOLOGY = "INVALID_CHRONOLOGY"
    FILL_SESSION_MISMATCH = "FILL_SESSION_MISMATCH"
    POLICY_MISMATCH = "POLICY_MISMATCH"
    INCONSISTENT_PREPARED_RESULT = "INCONSISTENT_PREPARED_RESULT"


@dataclass(frozen=True, slots=True)
class VerifiedSnapshotPaperCyclePreparationDiagnostic:
    """One stable failure code with non-identity explanatory text."""

    code: VerifiedSnapshotPaperCyclePreparationDiagnosticCode
    detail: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.code, VerifiedSnapshotPaperCyclePreparationDiagnosticCode
        ):
            raise TypeError(
                "code must be VerifiedSnapshotPaperCyclePreparationDiagnosticCode"
            )
        if type(self.detail) is not str or not self.detail.strip():
            raise ValueError("detail must be nonblank")


def _raise(
    error_type: type[VerifiedSnapshotPaperCyclePreparationError],
    code: VerifiedSnapshotPaperCyclePreparationDiagnosticCode,
    detail: str,
) -> None:
    raise error_type(VerifiedSnapshotPaperCyclePreparationDiagnostic(code, detail))


def _request_error(
    code: VerifiedSnapshotPaperCyclePreparationDiagnosticCode,
    detail: str,
) -> InvalidVerifiedSnapshotPaperCyclePreparationRequestError:
    return InvalidVerifiedSnapshotPaperCyclePreparationRequestError(
        VerifiedSnapshotPaperCyclePreparationDiagnostic(code, detail)
    )


def _decimal(
    value: object,
    name: str,
    *,
    positive: bool = False,
) -> Decimal:
    if type(value) is not Decimal:
        raise _request_error(
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_DECIMAL,
            f"{name} must be an exact Decimal",
        )
    if not value.is_finite():
        raise _request_error(
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_DECIMAL,
            f"{name} must be finite",
        )
    normalized = _ZERO if value == _ZERO else value
    decimal_tuple = normalized.as_tuple()
    if (
        len(decimal_tuple.digits) > _MAX_INPUT_SIGNIFICANT_DIGITS
        or decimal_tuple.exponent < -_MAX_INPUT_SCALE
        or (
            normalized != _ZERO and normalized.adjusted() > _MAX_INPUT_ADJUSTED_EXPONENT
        )
    ):
        raise _request_error(
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_DECIMAL,
            f"{name} exceeds the supported Decimal scale or magnitude",
        )
    if normalized < _ZERO or (positive and normalized == _ZERO):
        qualifier = "positive" if positive else "nonnegative"
        raise _request_error(
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_DECIMAL,
            f"{name} must be {qualifier}",
        )
    return normalized


def _utc(value: object, name: str) -> datetime:
    if type(value) is not datetime:
        raise _request_error(
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_REQUEST,
            f"{name} must be a datetime",
        )
    if value.tzinfo is None or value.utcoffset() is None:
        raise _request_error(
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_REQUEST,
            f"{name} must be timezone-aware",
        )
    return value.astimezone(UTC)


def _tuple(
    value: object,
    item_type: type[object],
    name: str,
) -> tuple[object, ...]:
    try:
        items = tuple(value)  # type: ignore[arg-type]
    except TypeError as error:
        raise _request_error(
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_REQUEST,
            f"{name} must be iterable",
        ) from error
    if any(type(item) is not item_type for item in items):
        raise _request_error(
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_REQUEST,
            f"{name} must contain exact {item_type.__name__} values",
        )
    return items


@dataclass(frozen=True, slots=True)
class VerifiedDailySnapshotReference:
    """Caller-expected identity and artifact evidence for one verified snapshot."""

    snapshot_id: UUID
    artifact_sha256: str
    artifact_byte_length: int

    def __post_init__(self) -> None:
        if type(self.snapshot_id) is not UUID:
            raise _request_error(
                VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_REQUEST,
                "snapshot_id must be a UUID",
            )
        if (
            type(self.artifact_sha256) is not str
            or _SHA256_PATTERN.fullmatch(self.artifact_sha256) is None
        ):
            raise _request_error(
                VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_REQUEST,
                "artifact_sha256 must be lowercase SHA-256 text",
            )
        if type(self.artifact_byte_length) is not int or self.artifact_byte_length <= 0:
            raise _request_error(
                VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_REQUEST,
                "artifact_byte_length must be a positive integer",
            )


VerifiedSnapshotReference = VerifiedDailySnapshotReference


@dataclass(frozen=True, slots=True)
class VerifiedSnapshotAccountPosition:
    """One caller-supplied current paper-account position."""

    symbol: Symbol
    quantity: Decimal
    average_cost: Decimal

    def __post_init__(self) -> None:
        if type(self.symbol) is not Symbol:
            raise _request_error(
                VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_REQUEST,
                "account position symbol must be a Symbol",
            )
        quantity = _decimal(self.quantity, "account position quantity")
        average_cost = _decimal(self.average_cost, "account position average_cost")
        if quantity == _ZERO and average_cost != _ZERO:
            raise _request_error(
                VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_REQUEST,
                "flat account positions require zero average_cost",
            )
        if quantity > _ZERO and average_cost <= _ZERO:
            raise _request_error(
                VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_REQUEST,
                "held account positions require positive average_cost",
            )
        object.__setattr__(self, "quantity", quantity)
        object.__setattr__(self, "average_cost", average_cost)


@dataclass(frozen=True, slots=True)
class VerifiedSnapshotAccountState:
    """Explicit caller-authored paper account state before planning marks."""

    account_state_id: UUID
    as_of: datetime
    cash: Decimal
    positions: tuple[VerifiedSnapshotAccountPosition, ...] = ()

    def __post_init__(self) -> None:
        if type(self.account_state_id) is not UUID:
            raise _request_error(
                VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_REQUEST,
                "account_state_id must be a UUID",
            )
        as_of = _utc(self.as_of, "account_state.as_of")
        cash = _decimal(self.cash, "account_state.cash")
        positions = _tuple(
            self.positions,
            VerifiedSnapshotAccountPosition,
            "account_state.positions",
        )
        symbols = tuple(item.symbol for item in positions)
        if len(set(symbols)) != len(symbols):
            raise _request_error(
                VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_REQUEST,
                "account position symbols must be unique",
            )
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "cash", cash)
        object.__setattr__(self, "positions", positions)


@dataclass(frozen=True, slots=True)
class ExplicitQuantityTarget:
    """One explicit nonnegative end-of-cycle quantity target."""

    symbol: Symbol
    quantity: Decimal

    def __post_init__(self) -> None:
        if type(self.symbol) is not Symbol:
            raise _request_error(
                VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_REQUEST,
                "target symbol must be a Symbol",
            )
        object.__setattr__(
            self,
            "quantity",
            _decimal(self.quantity, "target quantity"),
        )


@dataclass(frozen=True, slots=True)
class ExplicitQuantityTargetPortfolio:
    """Complete caller-authored quantity and uninvested-cash target."""

    target_id: UUID
    quantities: tuple[ExplicitQuantityTarget, ...]
    target_cash: Decimal

    def __post_init__(self) -> None:
        if type(self.target_id) is not UUID:
            raise _request_error(
                VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_REQUEST,
                "target_id must be a UUID",
            )
        quantities = _tuple(
            self.quantities,
            ExplicitQuantityTarget,
            "target quantities",
        )
        if not quantities:
            raise _request_error(
                VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_REQUEST,
                "target quantities must not be empty",
            )
        symbols = tuple(item.symbol for item in quantities)
        if len(set(symbols)) != len(symbols):
            raise _request_error(
                VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_REQUEST,
                "target quantity symbols must be unique",
            )
        object.__setattr__(self, "quantities", quantities)
        object.__setattr__(
            self,
            "target_cash",
            _decimal(self.target_cash, "target_cash"),
        )


@dataclass(frozen=True, slots=True)
class CallerAssertedNextSessionOpenReference:
    """A caller assertion, not independently verified opening-print provenance."""

    symbol: Symbol
    session: TradingSession
    caller_asserted_open_reference_price: Decimal

    def __post_init__(self) -> None:
        if type(self.symbol) is not Symbol:
            raise _request_error(
                VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_REQUEST,
                "open reference symbol must be a Symbol",
            )
        if type(self.session) is not TradingSession:
            raise _request_error(
                VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_REQUEST,
                "open reference session must be a TradingSession",
            )
        object.__setattr__(
            self,
            "caller_asserted_open_reference_price",
            _decimal(
                self.caller_asserted_open_reference_price,
                "caller_asserted_open_reference_price",
                positive=True,
            ),
        )


@dataclass(frozen=True, slots=True)
class VerifiedSnapshotPaperCyclePolicies:
    """All explicit reusable policies needed by a later paper-runtime cycle."""

    rebalance_assumptions: RebalanceAssumptions
    portfolio_constraints: PortfolioConstraints | None
    proposal_policy: RebalanceProposalPolicy
    proposal_confidence: Decimal | None
    risk_limits: RiskLimits
    risk_policy: PortfolioRiskPolicy
    fill_policy: PaperFillPolicy
    trading_enabled: bool

    def __post_init__(self) -> None:
        for name, expected in (
            ("rebalance_assumptions", RebalanceAssumptions),
            ("proposal_policy", RebalanceProposalPolicy),
            ("risk_limits", RiskLimits),
            ("risk_policy", PortfolioRiskPolicy),
            ("fill_policy", PaperFillPolicy),
        ):
            if type(getattr(self, name)) is not expected:
                _raise(
                    VerifiedSnapshotPaperCyclePolicyError,
                    VerifiedSnapshotPaperCyclePreparationDiagnosticCode.POLICY_MISMATCH,
                    f"{name} must be an exact {expected.__name__}",
                )
        if (
            self.portfolio_constraints is not None
            and type(self.portfolio_constraints) is not PortfolioConstraints
        ):
            _raise(
                VerifiedSnapshotPaperCyclePolicyError,
                VerifiedSnapshotPaperCyclePreparationDiagnosticCode.POLICY_MISMATCH,
                "portfolio_constraints must be PortfolioConstraints or None",
            )
        if type(self.trading_enabled) is not bool:
            _raise(
                VerifiedSnapshotPaperCyclePolicyError,
                VerifiedSnapshotPaperCyclePreparationDiagnosticCode.POLICY_MISMATCH,
                "trading_enabled must be a bool",
            )
        confidence = self.proposal_confidence
        if confidence is not None:
            try:
                confidence = _decimal(confidence, "proposal_confidence")
            except InvalidVerifiedSnapshotPaperCyclePreparationRequestError as error:
                raise VerifiedSnapshotPaperCyclePolicyError(error.diagnostic) from error
            if confidence > _ONE:
                _raise(
                    VerifiedSnapshotPaperCyclePolicyError,
                    VerifiedSnapshotPaperCyclePreparationDiagnosticCode.POLICY_MISMATCH,
                    "proposal_confidence must be between zero and one",
                )
            object.__setattr__(self, "proposal_confidence", confidence)
        _validate_policy_decimals(self)
        assumptions = self.rebalance_assumptions
        limits = self.risk_limits
        if not (
            assumptions.fixed_commission
            == limits.estimated_commission
            == self.fill_policy.fixed_commission
        ):
            _raise(
                VerifiedSnapshotPaperCyclePolicyError,
                VerifiedSnapshotPaperCyclePreparationDiagnosticCode.POLICY_MISMATCH,
                "planner, risk, and fill fixed commissions must match",
            )
        if (
            assumptions.allow_fractional_quantities != limits.allow_fractional_shares
            or assumptions.quantity_increment != limits.fractional_increment
        ):
            _raise(
                VerifiedSnapshotPaperCyclePolicyError,
                VerifiedSnapshotPaperCyclePreparationDiagnosticCode.POLICY_MISMATCH,
                "planner and risk quantity precision policies must match",
            )
        if (
            assumptions.use_planned_sell_proceeds
            != self.risk_policy.allow_sell_proceeds_for_later_buys
        ):
            _raise(
                VerifiedSnapshotPaperCyclePolicyError,
                VerifiedSnapshotPaperCyclePreparationDiagnosticCode.POLICY_MISMATCH,
                "planner and risk sell-proceeds policies must match",
            )


@dataclass(frozen=True, slots=True)
class VerifiedSnapshotPaperCyclePreparationRequest:
    """Complete explicit input for pure verified-snapshot preparation."""

    request_id: UUID
    snapshot_reference: VerifiedDailySnapshotReference
    account_state: VerifiedSnapshotAccountState
    target: ExplicitQuantityTargetPortfolio
    open_references: tuple[CallerAssertedNextSessionOpenReference, ...]
    policies: VerifiedSnapshotPaperCyclePolicies
    planning_at: datetime
    submitted_at: datetime
    filled_at: datetime
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        if type(self.request_id) is not UUID:
            raise _request_error(
                VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_REQUEST,
                "request_id must be a UUID",
            )
        for name, expected in (
            ("snapshot_reference", VerifiedDailySnapshotReference),
            ("account_state", VerifiedSnapshotAccountState),
            ("target", ExplicitQuantityTargetPortfolio),
            ("policies", VerifiedSnapshotPaperCyclePolicies),
        ):
            if type(getattr(self, name)) is not expected:
                raise _request_error(
                    VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_REQUEST,
                    f"{name} must be an exact {expected.__name__}",
                )
        open_references = _tuple(
            self.open_references,
            CallerAssertedNextSessionOpenReference,
            "open_references",
        )
        metadata = _tuple(self.metadata, MetadataEntry, "metadata")
        if len({item.key for item in metadata}) != len(metadata):
            raise _request_error(
                VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_REQUEST,
                "metadata keys must be unique",
            )
        planning_at = _utc(self.planning_at, "planning_at")
        submitted_at = _utc(self.submitted_at, "submitted_at")
        filled_at = _utc(self.filled_at, "filled_at")
        object.__setattr__(self, "open_references", open_references)
        object.__setattr__(self, "metadata", metadata)
        object.__setattr__(self, "planning_at", planning_at)
        object.__setattr__(self, "submitted_at", submitted_at)
        object.__setattr__(self, "filled_at", filled_at)


@dataclass(frozen=True, slots=True)
class VerifiedSnapshotCloseMark:
    """One replayed completed-session close used only as a planning/risk mark."""

    symbol: Symbol
    session: TradingSession
    planning_close: Decimal

    def __post_init__(self) -> None:
        if type(self.symbol) is not Symbol or type(self.session) is not TradingSession:
            raise _request_error(
                VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_REQUEST,
                "close mark requires a Symbol and TradingSession",
            )
        object.__setattr__(
            self,
            "planning_close",
            _decimal(self.planning_close, "planning_close", positive=True),
        )


@dataclass(frozen=True, slots=True)
class _PreparedIdentityValues:
    request_id: UUID
    snapshot_reference: VerifiedDailySnapshotReference
    snapshot_audit_sha256: str
    snapshot_canonical_bars_sha256: str
    snapshot_captured_at: datetime
    provider: ProviderDescriptor
    calendar: CalendarDescriptor
    target_session: TradingSession
    next_session: TradingSession
    close_marks: tuple[VerifiedSnapshotCloseMark, ...]
    account_state: VerifiedSnapshotAccountState
    target: ExplicitQuantityTargetPortfolio
    open_references: tuple[CallerAssertedNextSessionOpenReference, ...]
    policies: VerifiedSnapshotPaperCyclePolicies
    planning_at: datetime
    submitted_at: datetime
    filled_at: datetime
    metadata: tuple[MetadataEntry, ...]
    planner_request: RebalancePlanRequest


@dataclass(frozen=True, slots=True)
class PreparedVerifiedSnapshotPaperCycle:
    """Immutable, replayable inputs prepared for one later paper-runtime cycle.

    Open-reference session consistency is enforced, but preparation cannot prove
    when the caller learned any asserted open-reference price.
    """

    preparation_id: UUID
    request_id: UUID
    snapshot_reference: VerifiedDailySnapshotReference
    snapshot_audit_sha256: str
    snapshot_canonical_bars_sha256: str
    snapshot_captured_at: datetime
    provider: ProviderDescriptor
    calendar: CalendarDescriptor
    target_session: TradingSession
    next_session: TradingSession
    close_marks: tuple[VerifiedSnapshotCloseMark, ...]
    account_state: VerifiedSnapshotAccountState
    target: ExplicitQuantityTargetPortfolio
    open_references: tuple[CallerAssertedNextSessionOpenReference, ...]
    policies: VerifiedSnapshotPaperCyclePolicies
    planning_at: datetime
    submitted_at: datetime
    filled_at: datetime
    metadata: tuple[MetadataEntry, ...]
    planner_request: RebalancePlanRequest

    def __post_init__(self) -> None:
        if type(self.preparation_id) is not UUID or type(self.request_id) is not UUID:
            _inconsistent("prepared identities must be UUIDs")
        for name, expected in (
            ("snapshot_reference", VerifiedDailySnapshotReference),
            ("provider", ProviderDescriptor),
            ("calendar", CalendarDescriptor),
            ("target_session", TradingSession),
            ("next_session", TradingSession),
            ("account_state", VerifiedSnapshotAccountState),
            ("target", ExplicitQuantityTargetPortfolio),
            ("policies", VerifiedSnapshotPaperCyclePolicies),
            ("planner_request", RebalancePlanRequest),
        ):
            if type(getattr(self, name)) is not expected:
                _inconsistent(f"{name} must be exact {expected.__name__}")
        for name in ("snapshot_audit_sha256", "snapshot_canonical_bars_sha256"):
            value = getattr(self, name)
            if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
                _inconsistent(f"{name} must be lowercase SHA-256 text")
        close_marks = _prepared_tuple(
            self.close_marks, VerifiedSnapshotCloseMark, "close_marks"
        )
        open_references = _prepared_tuple(
            self.open_references,
            CallerAssertedNextSessionOpenReference,
            "open_references",
        )
        metadata = _prepared_tuple(self.metadata, MetadataEntry, "metadata")
        snapshot_captured_at = _prepared_utc(
            self.snapshot_captured_at, "snapshot_captured_at"
        )
        planning_at = _prepared_utc(self.planning_at, "planning_at")
        submitted_at = _prepared_utc(self.submitted_at, "submitted_at")
        filled_at = _prepared_utc(self.filled_at, "filled_at")
        symbols = tuple(item.symbol for item in close_marks)
        if (
            not symbols
            or tuple(item.symbol for item in self.account_state.positions) != symbols
            or tuple(item.symbol for item in self.target.quantities) != symbols
            or tuple(item.symbol for item in open_references) != symbols
            or self.planner_request.state.symbols != symbols
            or self.planner_request.target.symbols != symbols
        ):
            _inconsistent("prepared ordered universes must match exactly")
        if any(item.session != self.target_session for item in close_marks):
            _inconsistent("close marks must name the snapshot target session")
        if any(item.session != self.next_session for item in open_references):
            _inconsistent("open references must name the derived next session")
        if (
            self.planner_request.state.as_of != planning_at
            or self.planner_request.target.as_of != planning_at
            or self.planner_request.target.target_id != self.target.target_id
            or self.planner_request.assumptions != self.policies.rebalance_assumptions
            or self.planner_request.constraints != self.policies.portfolio_constraints
            or self.planner_request.metadata != metadata
            or self.planner_request.request_id
            != _planner_validation_request_id(
                self.request_id,
                self.snapshot_reference.snapshot_id,
                self.target.target_id,
            )
        ):
            _inconsistent("prepared planner inputs do not match retained inputs")
        if self.next_session <= self.target_session:
            _inconsistent("next_session must be later than target_session")
        if not (
            self.account_state.as_of
            <= snapshot_captured_at
            <= planning_at
            <= submitted_at
            <= filled_at
        ):
            _inconsistent("prepared chronology does not reconcile")
        try:
            fill_date = filled_at.astimezone(
                ZoneInfo(self.calendar.exchange_timezone)
            ).date()
        except ZoneInfoNotFoundError:
            _inconsistent("prepared calendar timezone is unavailable")
        if fill_date != self.next_session.session_date:
            _inconsistent("prepared fill date does not match next_session")
        with localcontext(_ARITHMETIC_CONTEXT):
            for close_mark, account_position, state_position, target_quantity, (
                allocation
            ) in zip(
                close_marks,
                self.account_state.positions,
                self.planner_request.state.positions,
                self.target.quantities,
                self.planner_request.target.allocations,
                strict=True,
            ):
                if (
                    state_position.symbol != close_mark.symbol
                    or state_position.quantity != account_position.quantity
                    or state_position.average_cost != account_position.average_cost
                    or state_position.current_price != close_mark.planning_close
                    or allocation.symbol != target_quantity.symbol
                    or (
                        allocation.weight
                        * self.planner_request.state.equity
                        / close_mark.planning_close
                        != target_quantity.quantity
                    )
                ):
                    _inconsistent(
                        "prepared account, close, target, and planner values disagree"
                    )
            if (
                self.planner_request.target.cash_weight
                * self.planner_request.state.equity
                != self.target.target_cash
            ):
                _inconsistent("prepared target cash does not match planner target")
        object.__setattr__(self, "close_marks", close_marks)
        object.__setattr__(self, "open_references", open_references)
        object.__setattr__(self, "metadata", metadata)
        object.__setattr__(self, "snapshot_captured_at", snapshot_captured_at)
        object.__setattr__(self, "planning_at", planning_at)
        object.__setattr__(self, "submitted_at", submitted_at)
        object.__setattr__(self, "filled_at", filled_at)
        expected_id = _prepared_id(self)
        if self.preparation_id != expected_id:
            _inconsistent("preparation_id does not match canonical prepared material")

    @property
    def portfolio_state(self) -> PortfolioState:
        """Return the exact derived planning state."""
        return self.planner_request.state

    @property
    def target_portfolio(self) -> TargetPortfolio:
        """Return the exact quantity-derived planner target."""
        return self.planner_request.target


def prepare_verified_snapshot_paper_cycle(
    request: VerifiedSnapshotPaperCyclePreparationRequest,
    verification: DailySnapshotVerificationResult,
    calendar: IdentifiedMarketCalendar,
) -> PreparedVerifiedSnapshotPaperCycle:
    """Prepare exact immutable inputs without executing or performing I/O."""
    if type(request) is not VerifiedSnapshotPaperCyclePreparationRequest:
        raise _request_error(
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_REQUEST,
            "request must be VerifiedSnapshotPaperCyclePreparationRequest",
        )
    if (
        type(verification) is not DailySnapshotVerificationResult
        or verification.status is not DailySnapshotVerificationStatus.PASS
        or verification.snapshot is None
        or verification.diagnostics
    ):
        _raise(
            VerifiedSnapshotPaperCycleSnapshotError,
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.SNAPSHOT_VERIFICATION_REQUIRED,
            "preparation requires one complete PASS verification result",
        )

    try:
        replay = replay_verified_daily_snapshot(verification)
    except DailySnapshotReplayError as error:
        _raise(
            VerifiedSnapshotPaperCycleSnapshotError,
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.SNAPSHOT_REPLAY_FAILED,
            str(error),
        )

    snapshot = verification.snapshot
    reference = request.snapshot_reference
    if (
        reference.snapshot_id != replay.snapshot_id
        or reference.artifact_sha256 != verification.sha256
        or reference.artifact_byte_length != verification.byte_length
    ):
        _raise(
            VerifiedSnapshotPaperCycleSnapshotError,
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.SNAPSHOT_REFERENCE_MISMATCH,
            "expected snapshot UUID, artifact SHA-256, and byte length must match",
        )
    try:
        require_matching_calendar(snapshot.request, calendar)
    except InvalidDailySnapshotCalendarError as error:
        _raise(
            VerifiedSnapshotPaperCycleSnapshotError,
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.CALENDAR_MISMATCH,
            str(error),
        )

    close_marks = tuple(
        VerifiedSnapshotCloseMark(
            symbol,
            replay.target_session,
            replay_bar.bar.close,
        )
        for symbol, replay_bar in zip(replay.symbols, replay.bars, strict=True)
    )
    symbols = tuple(item.symbol for item in close_marks)
    normalized_account = _normalize_account(request.account_state, symbols)
    _require_target_universe(request.target, symbols)
    _require_open_reference_universe(request.open_references, symbols)
    next_session = _next_session(
        replay.target_session,
        snapshot.request.calendar,
        calendar,
    )
    if any(item.session != next_session for item in request.open_references):
        _raise(
            VerifiedSnapshotPaperCycleTemporalError,
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.OPEN_REFERENCE_SESSION_MISMATCH,
            "every caller-asserted open reference must name the first next session",
        )
    _validate_chronology(
        normalized_account.as_of,
        snapshot.audit.captured_at,
        request.planning_at,
        request.submitted_at,
        request.filled_at,
        next_session,
        snapshot.request.calendar,
    )

    with localcontext(_ARITHMETIC_CONTEXT):
        state = _portfolio_state(
            normalized_account,
            close_marks,
            request.planning_at,
        )
        target_portfolio = _target_portfolio(request.target, close_marks, state)
        validation_request_id = _planner_validation_request_id(
            request.request_id,
            reference.snapshot_id,
            request.target.target_id,
        )
        try:
            planner_request = RebalancePlanRequest(
                validation_request_id,
                state,
                target_portfolio,
                request.policies.rebalance_assumptions,
                request.policies.portfolio_constraints,
                request.metadata,
            )
            validation_plan = RebalancePlanner().plan(planner_request)
        except (RebalanceError, TypeError, ValueError, ArithmeticError) as error:
            _raise(
                VerifiedSnapshotPaperCycleTargetError,
                VerifiedSnapshotPaperCyclePreparationDiagnosticCode.PLANNER_VALIDATION_FAILED,
                f"existing planner rejected derived quantity-target inputs: {error}",
            )
        if any(
            deviation.target_quantity != quantity.quantity
            for deviation, quantity in zip(
                validation_plan.deviations,
                request.target.quantities,
                strict=True,
            )
        ):
            _raise(
                VerifiedSnapshotPaperCycleTargetError,
                VerifiedSnapshotPaperCyclePreparationDiagnosticCode.QUANTITY_TARGET_NOT_EXACTLY_REPRESENTABLE,
                "quantity target does not round-trip exactly through RebalancePlanner",
            )

        identity_values = _PreparedIdentityValues(
            request.request_id,
            reference,
            snapshot.audit.audit_sha256,
            snapshot.canonical_bars.sha256,
            snapshot.audit.captured_at,
            replay.provider,
            snapshot.request.calendar,
            replay.target_session,
            next_session,
            close_marks,
            normalized_account,
            request.target,
            request.open_references,
            request.policies,
            request.planning_at,
            request.submitted_at,
            request.filled_at,
            request.metadata,
            planner_request,
        )
    return PreparedVerifiedSnapshotPaperCycle(
        _prepared_id(identity_values),
        identity_values.request_id,
        identity_values.snapshot_reference,
        identity_values.snapshot_audit_sha256,
        identity_values.snapshot_canonical_bars_sha256,
        identity_values.snapshot_captured_at,
        identity_values.provider,
        identity_values.calendar,
        identity_values.target_session,
        identity_values.next_session,
        identity_values.close_marks,
        identity_values.account_state,
        identity_values.target,
        identity_values.open_references,
        identity_values.policies,
        identity_values.planning_at,
        identity_values.submitted_at,
        identity_values.filled_at,
        identity_values.metadata,
        identity_values.planner_request,
    )


def _validate_policy_decimals(policies: VerifiedSnapshotPaperCyclePolicies) -> None:
    values: list[tuple[str, Decimal | None]] = [
        (
            "rebalance.fixed_commission",
            policies.rebalance_assumptions.fixed_commission,
        ),
        (
            "rebalance.quantity_increment",
            policies.rebalance_assumptions.quantity_increment,
        ),
        (
            "rebalance.minimum_trade_notional",
            policies.rebalance_assumptions.minimum_trade_notional,
        ),
        (
            "rebalance.minimum_trade_quantity",
            policies.rebalance_assumptions.minimum_trade_quantity,
        ),
        (
            "rebalance.target_weight_tolerance",
            policies.rebalance_assumptions.target_weight_tolerance,
        ),
        (
            "rebalance.additional_execution_cash_buffer",
            policies.rebalance_assumptions.additional_execution_cash_buffer,
        ),
        ("risk.max_position_percent", policies.risk_limits.max_position_percent),
        (
            "risk.max_total_exposure_percent",
            policies.risk_limits.max_total_exposure_percent,
        ),
        ("risk.max_order_notional", policies.risk_limits.max_order_notional),
        (
            "risk.max_new_position_percent",
            policies.risk_limits.max_new_position_percent,
        ),
        (
            "risk.minimum_cash_reserve_percent",
            policies.risk_limits.minimum_cash_reserve_percent,
        ),
        ("risk.fractional_increment", policies.risk_limits.fractional_increment),
        ("risk.estimated_commission", policies.risk_limits.estimated_commission),
        (
            "fill.slippage_basis_points",
            policies.fill_policy.slippage_basis_points,
        ),
        ("fill.fixed_commission", policies.fill_policy.fixed_commission),
    ]
    constraints = policies.portfolio_constraints
    if constraints is not None:
        values.extend(
            (
                ("constraints.minimum_cash_weight", constraints.minimum_cash_weight),
                ("constraints.maximum_cash_weight", constraints.maximum_cash_weight),
                (
                    "constraints.maximum_position_weight",
                    constraints.maximum_position_weight,
                ),
                (
                    "constraints.maximum_one_way_rebalance_turnover",
                    constraints.maximum_one_way_rebalance_turnover,
                ),
                (
                    "constraints.minimum_position_weight",
                    constraints.minimum_position_weight,
                ),
            )
        )
    for name, value in values:
        if value is None:
            continue
        try:
            _decimal(value, name)
        except InvalidVerifiedSnapshotPaperCyclePreparationRequestError as error:
            raise VerifiedSnapshotPaperCyclePolicyError(error.diagnostic) from error


def _normalize_account(
    account: VerifiedSnapshotAccountState,
    symbols: tuple[Symbol, ...],
) -> VerifiedSnapshotAccountState:
    supplied = {item.symbol: item for item in account.positions}
    unsupported = tuple(symbol for symbol in supplied if symbol not in set(symbols))
    if unsupported:
        _raise(
            VerifiedSnapshotPaperCycleUniverseError,
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.ACCOUNT_UNIVERSE_MISMATCH,
            "account positions contain symbols absent from the verified snapshot",
        )
    return VerifiedSnapshotAccountState(
        account.account_state_id,
        account.as_of,
        account.cash,
        tuple(
            supplied.get(
                symbol,
                VerifiedSnapshotAccountPosition(symbol, _ZERO, _ZERO),
            )
            for symbol in symbols
        ),
    )


def _require_target_universe(
    target: ExplicitQuantityTargetPortfolio,
    symbols: tuple[Symbol, ...],
) -> None:
    if tuple(item.symbol for item in target.quantities) != symbols:
        _raise(
            VerifiedSnapshotPaperCycleUniverseError,
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.TARGET_UNIVERSE_MISMATCH,
            "target quantities must contain every snapshot symbol in exact order",
        )


def _require_open_reference_universe(
    references: tuple[CallerAssertedNextSessionOpenReference, ...],
    symbols: tuple[Symbol, ...],
) -> None:
    if tuple(item.symbol for item in references) != symbols:
        _raise(
            VerifiedSnapshotPaperCycleUniverseError,
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.OPEN_REFERENCE_UNIVERSE_MISMATCH,
            "open references must contain every snapshot symbol in exact order",
        )


def _next_session(
    target: TradingSession,
    descriptor: CalendarDescriptor,
    calendar: IdentifiedMarketCalendar,
) -> TradingSession:
    try:
        timezone = ZoneInfo(descriptor.exchange_timezone)
        anchor = datetime.combine(target.session_date, time(12), timezone)
        next_session = calendar.next_session(anchor)
    except (AttributeError, TypeError, ValueError, ZoneInfoNotFoundError) as error:
        _raise(
            VerifiedSnapshotPaperCycleTemporalError,
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.NEXT_SESSION_DERIVATION_FAILED,
            f"next session cannot be derived: {error}",
        )
    if type(next_session) is not TradingSession or next_session <= target:
        _raise(
            VerifiedSnapshotPaperCycleTemporalError,
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.NEXT_SESSION_DERIVATION_FAILED,
            "calendar next_session must return the first later TradingSession",
        )
    return next_session


def _validate_chronology(
    account_as_of: datetime,
    captured_at: datetime,
    planning_at: datetime,
    submitted_at: datetime,
    filled_at: datetime,
    next_session: TradingSession,
    descriptor: CalendarDescriptor,
) -> None:
    if not (account_as_of <= captured_at <= planning_at <= submitted_at <= filled_at):
        _raise(
            VerifiedSnapshotPaperCycleTemporalError,
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_CHRONOLOGY,
            "timestamps must satisfy account <= capture <= plan <= submit <= fill",
        )
    try:
        filled_session_date = filled_at.astimezone(
            ZoneInfo(descriptor.exchange_timezone)
        ).date()
    except ZoneInfoNotFoundError as error:
        _raise(
            VerifiedSnapshotPaperCycleTemporalError,
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.NEXT_SESSION_DERIVATION_FAILED,
            str(error),
        )
    if filled_session_date != next_session.session_date:
        _raise(
            VerifiedSnapshotPaperCycleTemporalError,
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.FILL_SESSION_MISMATCH,
            "the New York fill date must equal the derived next session",
        )


def _portfolio_state(
    account: VerifiedSnapshotAccountState,
    close_marks: tuple[VerifiedSnapshotCloseMark, ...],
    planning_at: datetime,
) -> PortfolioState:
    positions = tuple(
        PortfolioPositionState(
            account_position.symbol,
            account_position.quantity,
            account_position.average_cost,
            close_mark.planning_close,
        )
        for account_position, close_mark in zip(
            account.positions, close_marks, strict=True
        )
    )
    equity = account.cash + sum(
        (
            item.quantity * close_mark.planning_close
            for item, close_mark in zip(account.positions, close_marks, strict=True)
        ),
        start=_ZERO,
    )
    if equity <= _ZERO:
        _raise(
            VerifiedSnapshotPaperCycleTargetError,
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_ACCOUNT_STATE,
            "planning equity must be positive",
        )
    try:
        return PortfolioState(planning_at, positions, account.cash, equity)
    except (TypeError, ValueError, ArithmeticError) as error:
        _raise(
            VerifiedSnapshotPaperCycleTargetError,
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_ACCOUNT_STATE,
            f"derived planning state is invalid: {error}",
        )


def _target_portfolio(
    target: ExplicitQuantityTargetPortfolio,
    close_marks: tuple[VerifiedSnapshotCloseMark, ...],
    state: PortfolioState,
) -> TargetPortfolio:
    target_notionals = tuple(
        quantity.quantity * close_mark.planning_close
        for quantity, close_mark in zip(target.quantities, close_marks, strict=True)
    )
    if target.target_cash + sum(target_notionals, start=_ZERO) != state.equity:
        _raise(
            VerifiedSnapshotPaperCycleTargetError,
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.TARGET_CASH_MISMATCH,
            "target cash plus close-marked target notionals must equal planning equity",
        )
    equity_fraction = Fraction(state.equity)
    try:
        weights = tuple(
            _fraction_to_decimal(Fraction(notional) / equity_fraction)
            for notional in target_notionals
        )
        cash_weight = _fraction_to_decimal(
            Fraction(target.target_cash) / equity_fraction
        )
    except ValueError as error:
        _raise(
            VerifiedSnapshotPaperCycleTargetError,
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.QUANTITY_TARGET_NOT_EXACTLY_REPRESENTABLE,
            f"quantity target cannot be represented by exact Decimal weights: {error}",
        )
    try:
        result = TargetPortfolio(
            target.target_id,
            state.as_of,
            tuple(
                TargetAllocation(quantity.symbol, weight)
                for quantity, weight in zip(target.quantities, weights, strict=True)
            ),
            cash_weight,
            AllocationSource.MANUAL,
        )
    except (TypeError, ValueError, ArithmeticError) as error:
        _raise(
            VerifiedSnapshotPaperCycleTargetError,
            VerifiedSnapshotPaperCyclePreparationDiagnosticCode.QUANTITY_TARGET_NOT_EXACTLY_REPRESENTABLE,
            f"exact quantity-derived target is invalid: {error}",
        )
    for allocation, quantity, close_mark in zip(
        result.allocations,
        target.quantities,
        close_marks,
        strict=True,
    ):
        if (
            allocation.weight * state.equity / close_mark.planning_close
            != quantity.quantity
        ):
            _raise(
                VerifiedSnapshotPaperCycleTargetError,
                VerifiedSnapshotPaperCyclePreparationDiagnosticCode.QUANTITY_TARGET_NOT_EXACTLY_REPRESENTABLE,
                "quantity target does not round-trip through TargetPortfolio",
            )
    return result


def _fraction_to_decimal(value: Fraction) -> Decimal:
    if value < 0:
        raise ValueError("negative fractions are unsupported")
    denominator = value.denominator
    twos = 0
    fives = 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        raise ValueError("ratio has a non-terminating Decimal expansion")
    scale = max(twos, fives)
    coefficient = value.numerator * (2 ** (scale - twos)) * (5 ** (scale - fives))
    if coefficient == 0:
        return _ZERO
    digits = tuple(int(character) for character in str(coefficient))
    return Decimal((0, digits, -scale))


def _planner_validation_request_id(
    request_id: UUID,
    snapshot_id: UUID,
    target_id: UUID,
) -> UUID:
    material = _framed_material(
        (
            "planner-validation-request-v1",
            str(request_id),
            str(snapshot_id),
            str(target_id),
        )
    )
    return uuid5(VERIFIED_SNAPSHOT_PAPER_CYCLE_PREPARATION_NAMESPACE, material)


def _prepared_id(
    value: PreparedVerifiedSnapshotPaperCycle | _PreparedIdentityValues,
) -> UUID:
    return uuid5(
        VERIFIED_SNAPSHOT_PAPER_CYCLE_PREPARATION_NAMESPACE,
        _framed_material(_prepared_identity_parts(value)),
    )


def _prepared_identity_parts(
    value: PreparedVerifiedSnapshotPaperCycle | _PreparedIdentityValues,
) -> tuple[str, ...]:
    policies = value.policies
    assumptions = policies.rebalance_assumptions
    limits = policies.risk_limits
    constraints = policies.portfolio_constraints
    parts = [
        VERIFIED_SNAPSHOT_PAPER_CYCLE_PREPARATION_MATERIAL_VERSION,
        str(value.request_id),
        str(value.snapshot_reference.snapshot_id),
        value.snapshot_reference.artifact_sha256,
        str(value.snapshot_reference.artifact_byte_length),
        value.snapshot_audit_sha256,
        value.snapshot_canonical_bars_sha256,
        value.snapshot_captured_at.isoformat(),
        value.provider.provider_id,
        str(value.provider.adapter_version),
        value.provider.operation,
        value.provider.feed,
        value.calendar.calendar_id,
        value.calendar.version,
        value.calendar.exchange_timezone,
        value.target_session.session_date.isoformat(),
        value.next_session.session_date.isoformat(),
        str(value.account_state.account_state_id),
        value.account_state.as_of.isoformat(),
        _canonical_decimal(value.account_state.cash),
        str(value.target.target_id),
        _canonical_decimal(value.target.target_cash),
        value.planning_at.isoformat(),
        value.submitted_at.isoformat(),
        value.filled_at.isoformat(),
        str(value.planner_request.request_id),
        _canonical_decimal(assumptions.fixed_commission),
        _canonical_bool(assumptions.allow_fractional_quantities),
        _canonical_decimal(assumptions.quantity_increment),
        _canonical_decimal(assumptions.minimum_trade_notional),
        _canonical_decimal(assumptions.minimum_trade_quantity),
        _canonical_decimal(assumptions.target_weight_tolerance),
        _canonical_decimal(assumptions.additional_execution_cash_buffer),
        _canonical_bool(assumptions.use_planned_sell_proceeds),
        _canonical_bool(policies.proposal_policy.allow_partial_plans),
        _canonical_optional_decimal(policies.proposal_confidence),
        _canonical_decimal(limits.max_position_percent),
        _canonical_decimal(limits.max_total_exposure_percent),
        _canonical_optional_decimal(limits.max_order_notional),
        _canonical_optional_decimal(limits.max_new_position_percent),
        _canonical_decimal(limits.minimum_cash_reserve_percent),
        _canonical_bool(limits.allow_fractional_shares),
        _canonical_decimal(limits.fractional_increment),
        _canonical_bool(limits.allow_buying),
        _canonical_bool(limits.allow_selling),
        _canonical_decimal(limits.estimated_commission),
        _canonical_bool(policies.risk_policy.allow_sell_proceeds_for_later_buys),
        _canonical_decimal(policies.fill_policy.slippage_basis_points),
        _canonical_decimal(policies.fill_policy.fixed_commission),
        _canonical_bool(policies.trading_enabled),
        str(len(value.close_marks)),
    ]
    if constraints is None:
        parts.append("constraints:none")
    else:
        parts.extend(
            (
                "constraints:present",
                _canonical_decimal(constraints.minimum_cash_weight),
                _canonical_decimal(constraints.maximum_cash_weight),
                _canonical_decimal(constraints.maximum_position_weight),
                _canonical_optional_decimal(
                    constraints.maximum_one_way_rebalance_turnover
                ),
                _canonical_optional_decimal(constraints.minimum_position_weight),
                _canonical_bool(constraints.long_only),
                _canonical_bool(constraints.allow_leverage),
            )
        )
    for close_mark, account_position, target, open_reference in zip(
        value.close_marks,
        value.account_state.positions,
        value.target.quantities,
        value.open_references,
        strict=True,
    ):
        parts.extend(
            (
                str(close_mark.symbol),
                close_mark.session.session_date.isoformat(),
                _canonical_decimal(close_mark.planning_close),
                _canonical_decimal(account_position.quantity),
                _canonical_decimal(account_position.average_cost),
                _canonical_decimal(target.quantity),
                open_reference.session.session_date.isoformat(),
                _canonical_decimal(open_reference.caller_asserted_open_reference_price),
            )
        )
    parts.append(str(len(value.metadata)))
    for item in value.metadata:
        parts.extend((item.key, item.value))
    return tuple(parts)


def _framed_material(parts: tuple[str, ...]) -> str:
    return "".join(f"{len(part.encode('utf-8'))}:{part}" for part in parts)


def _canonical_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("identity Decimal must be finite")
    if value == _ZERO:
        return "0"
    sign, digits, exponent = value.as_tuple()
    coefficient = "".join(str(digit) for digit in digits)
    if exponent >= 0:
        text = coefficient + ("0" * exponent)
    else:
        point = len(coefficient) + exponent
        text = (
            ("0." + ("0" * (-point)) + coefficient)
            if point <= 0
            else coefficient[:point] + "." + coefficient[point:]
        )
        text = text.rstrip("0").rstrip(".")
    return f"-{text}" if sign else text


def _canonical_optional_decimal(value: Decimal | None) -> str:
    return "none" if value is None else f"decimal:{_canonical_decimal(value)}"


def _canonical_bool(value: bool) -> str:
    return "true" if value else "false"


def _inconsistent(detail: str) -> None:
    _raise(
        InconsistentPreparedVerifiedSnapshotPaperCycleError,
        VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INCONSISTENT_PREPARED_RESULT,
        detail,
    )


def _prepared_tuple(
    value: object,
    item_type: type[object],
    name: str,
) -> tuple[object, ...]:
    try:
        items = tuple(value)  # type: ignore[arg-type]
    except TypeError:
        _inconsistent(f"{name} must be iterable")
    if any(type(item) is not item_type for item in items):
        _inconsistent(f"{name} contains invalid values")
    return items


def _prepared_utc(value: object, name: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        _inconsistent(f"{name} must be timezone-aware datetime")
    return value.astimezone(UTC)
