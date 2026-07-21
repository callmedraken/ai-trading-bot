"""Deterministic adapter from rebalance plans to trade proposals."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.domain import OrderSide, TradeProposal
from trading_bot.domain._validation import normalize_utc
from trading_bot.portfolio import MetadataEntry
from trading_bot.rebalancing.exceptions import (
    InconsistentRebalanceProposalResultError,
    InvalidRebalanceProposalRequestError,
    RebalancePlanNotEligibleError,
    RebalanceProposalCreationError,
)
from trading_bot.rebalancing.models import (
    PlannedTrade,
    PlannedTradeSide,
    RebalancePlan,
    RebalanceStatus,
)

_ZERO = Decimal("0")
_REASON_VERSION = "rebalance-proposal-v1"
_PROPOSAL_NAMESPACE = UUID("4e51b959-c086-5d85-9077-f9cb9296e6f1")
_SIDE_MAPPING = {
    PlannedTradeSide.BUY: OrderSide.BUY,
    PlannedTradeSide.SELL: OrderSide.SELL,
}


@dataclass(frozen=True, slots=True)
class RebalanceProposalPolicy:
    """Explicit eligibility policy for partial rebalance plans."""

    allow_partial_plans: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.allow_partial_plans, bool):
            raise InvalidRebalanceProposalRequestError(
                "allow_partial_plans must be a bool"
            )


@dataclass(frozen=True, slots=True)
class RebalanceProposalRequest:
    """Immutable inputs for one plan-to-proposal conversion."""

    request_id: UUID
    plan: RebalancePlan
    proposal_created_at: datetime
    policy: RebalanceProposalPolicy = RebalanceProposalPolicy()
    confidence: Decimal | None = None
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, UUID):
            raise InvalidRebalanceProposalRequestError("request_id must be a UUID")
        if not isinstance(self.plan, RebalancePlan):
            raise InvalidRebalanceProposalRequestError("plan must be a RebalancePlan")
        if not isinstance(self.policy, RebalanceProposalPolicy):
            raise InvalidRebalanceProposalRequestError(
                "policy must be a RebalanceProposalPolicy"
            )
        try:
            created_at = normalize_utc(self.proposal_created_at, "proposal_created_at")
        except (TypeError, ValueError) as error:
            raise InvalidRebalanceProposalRequestError(str(error)) from error
        if created_at != self.plan.request.as_of:
            raise InvalidRebalanceProposalRequestError(
                "proposal_created_at must equal the plan request as_of"
            )
        confidence = self.confidence
        if confidence is not None:
            if not isinstance(confidence, Decimal):
                raise InvalidRebalanceProposalRequestError(
                    "confidence must be a Decimal or None"
                )
            if not confidence.is_finite():
                raise InvalidRebalanceProposalRequestError("confidence must be finite")
            if not _ZERO <= confidence <= Decimal("1"):
                raise InvalidRebalanceProposalRequestError(
                    "confidence must be between zero and one"
                )
            confidence = _ZERO if confidence == _ZERO else confidence
        try:
            metadata = tuple(self.metadata)
        except TypeError as error:
            raise InvalidRebalanceProposalRequestError(
                "metadata must be iterable"
            ) from error
        if not all(isinstance(item, MetadataEntry) for item in metadata):
            raise InvalidRebalanceProposalRequestError(
                "metadata must contain MetadataEntry values"
            )
        if len({item.key for item in metadata}) != len(metadata):
            raise InvalidRebalanceProposalRequestError("metadata keys must be unique")
        object.__setattr__(self, "proposal_created_at", created_at)
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "metadata", metadata)


class RebalanceProposalStatus(StrEnum):
    CREATED = "CREATED"
    NO_ACTION = "NO_ACTION"


class RebalanceProposalDiagnosticCode(StrEnum):
    PARTIAL_PLAN_ACCEPTED = "PARTIAL_PLAN_ACCEPTED"
    NO_ACTION = "NO_ACTION"


@dataclass(frozen=True, slots=True)
class RebalanceProposalDiagnostic:
    code: RebalanceProposalDiagnosticCode
    message: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, RebalanceProposalDiagnosticCode):
            raise InconsistentRebalanceProposalResultError(
                "diagnostic code must be RebalanceProposalDiagnosticCode"
            )
        if not isinstance(self.message, str) or not self.message.strip():
            raise InconsistentRebalanceProposalResultError(
                "diagnostic message must be nonblank"
            )


@dataclass(frozen=True, slots=True)
class RebalanceProposalResult:
    """Immutable all-or-nothing proposal conversion result."""

    result_id: UUID
    request: RebalanceProposalRequest
    status: RebalanceProposalStatus
    proposals: tuple[TradeProposal, ...]
    diagnostics: tuple[RebalanceProposalDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.result_id, UUID):
            raise InconsistentRebalanceProposalResultError("result_id must be a UUID")
        if not isinstance(self.request, RebalanceProposalRequest):
            raise InconsistentRebalanceProposalResultError(
                "request must be a RebalanceProposalRequest"
            )
        if not isinstance(self.status, RebalanceProposalStatus):
            raise InconsistentRebalanceProposalResultError(
                "status must be a RebalanceProposalStatus"
            )
        try:
            proposals = tuple(self.proposals)
            diagnostics = tuple(self.diagnostics)
        except TypeError as error:
            raise InconsistentRebalanceProposalResultError(
                "proposals and diagnostics must be iterable"
            ) from error
        if not all(isinstance(item, TradeProposal) for item in proposals):
            raise InconsistentRebalanceProposalResultError(
                "proposals must contain TradeProposal values"
            )
        if not all(
            isinstance(item, RebalanceProposalDiagnostic) for item in diagnostics
        ):
            raise InconsistentRebalanceProposalResultError(
                "diagnostics must contain RebalanceProposalDiagnostic values"
            )
        plan = self.request.plan
        if self.status is RebalanceProposalStatus.NO_ACTION:
            if plan.status is not RebalanceStatus.NO_ACTION or proposals:
                raise InconsistentRebalanceProposalResultError(
                    "NO_ACTION requires a no-action plan and no proposals"
                )
            expected_codes = (RebalanceProposalDiagnosticCode.NO_ACTION,)
        else:
            if plan.status not in {RebalanceStatus.COMPLETE, RebalanceStatus.PARTIAL}:
                raise InconsistentRebalanceProposalResultError(
                    "CREATED requires a complete or partial plan"
                )
            if len(proposals) != len(plan.trades):
                raise InconsistentRebalanceProposalResultError(
                    "proposal count must equal plan trade count"
                )
            for ordinal, (proposal, trade) in enumerate(
                zip(proposals, plan.trades, strict=True)
            ):
                _validate_proposal_mapping(self.request, proposal, trade, ordinal)
            expected_codes = (
                (RebalanceProposalDiagnosticCode.PARTIAL_PLAN_ACCEPTED,)
                if plan.status is RebalanceStatus.PARTIAL
                else ()
            )
        codes = tuple(item.code for item in diagnostics)
        if codes != expected_codes:
            raise InconsistentRebalanceProposalResultError(
                "diagnostic codes do not match result status"
            )
        expected_id = _result_id(self.request, self.status, proposals, codes)
        if self.result_id != expected_id:
            raise InconsistentRebalanceProposalResultError(
                "result_id does not match deterministic result identity"
            )
        object.__setattr__(self, "proposals", proposals)
        object.__setattr__(self, "diagnostics", diagnostics)


class RebalanceProposalFactory:
    """Convert one eligible plan to ordered high-level trade intent."""

    _proposal_type = TradeProposal

    def create(self, request: RebalanceProposalRequest) -> RebalanceProposalResult:
        if not isinstance(request, RebalanceProposalRequest):
            raise TypeError("request must be a RebalanceProposalRequest")
        plan = request.plan
        self._validate_eligibility(request)
        self._validate_trades(plan)
        diagnostics = self._diagnostics(plan)
        candidates: list[TradeProposal] = []
        for ordinal, trade in enumerate(plan.trades):
            side = _SIDE_MAPPING[trade.side]
            try:
                proposal = self._proposal_type(
                    _proposal_id(request, trade, ordinal, side),
                    trade.symbol,
                    side,
                    trade.planned_quantity,
                    request.proposal_created_at,
                    _reason(plan, trade, side),
                    request.confidence,
                )
            except (TypeError, ValueError) as error:
                raise RebalanceProposalCreationError(
                    "could not create proposal for planned trade "
                    f"{trade.planned_trade_id}"
                ) from error
            candidates.append(proposal)
        proposals = tuple(candidates)
        status = (
            RebalanceProposalStatus.NO_ACTION
            if plan.status is RebalanceStatus.NO_ACTION
            else RebalanceProposalStatus.CREATED
        )
        result_id = _result_id(
            request,
            status,
            proposals,
            tuple(item.code for item in diagnostics),
        )
        return RebalanceProposalResult(
            result_id, request, status, proposals, diagnostics
        )

    @staticmethod
    def _validate_eligibility(request: RebalanceProposalRequest) -> None:
        plan = request.plan
        if plan.status is RebalanceStatus.COMPLETE:
            if not plan.trades:
                raise InconsistentRebalanceProposalResultError(
                    "a complete plan must contain at least one trade"
                )
            return
        if plan.status is RebalanceStatus.PARTIAL:
            if not request.policy.allow_partial_plans:
                raise RebalancePlanNotEligibleError(
                    "partial plans require allow_partial_plans=True"
                )
            return
        if plan.status is RebalanceStatus.NO_ACTION:
            if plan.trades:
                raise InconsistentRebalanceProposalResultError(
                    "a no-action plan cannot contain trades"
                )
            return
        if plan.status is RebalanceStatus.INFEASIBLE:
            if plan.trades:
                raise InconsistentRebalanceProposalResultError(
                    "an infeasible plan cannot contain trades"
                )
            raise RebalancePlanNotEligibleError(
                "infeasible plans cannot produce trade proposals"
            )
        raise RebalancePlanNotEligibleError("unsupported rebalance plan status")

    @staticmethod
    def _validate_trades(plan: RebalancePlan) -> None:
        ids: set[UUID] = set()
        symbols = set()
        seen_buy = False
        last_ordinal = -1
        for trade in plan.trades:
            if not isinstance(trade, PlannedTrade):
                raise InconsistentRebalanceProposalResultError(
                    "plan trades must be PlannedTrade values"
                )
            if trade.planned_trade_id in ids or trade.symbol in symbols:
                raise InconsistentRebalanceProposalResultError(
                    "planned trade IDs and symbols must be unique"
                )
            ids.add(trade.planned_trade_id)
            symbols.add(trade.symbol)
            if trade.side not in _SIDE_MAPPING:
                raise InconsistentRebalanceProposalResultError(
                    "planned trade side is unsupported"
                )
            if trade.side is PlannedTradeSide.BUY:
                if not seen_buy:
                    seen_buy = True
                    last_ordinal = -1
            elif seen_buy:
                raise InconsistentRebalanceProposalResultError(
                    "planned sells must precede planned buys"
                )
            if trade.symbol_ordinal <= last_ordinal:
                raise InconsistentRebalanceProposalResultError(
                    "symbol ordinals must increase within each side"
                )
            last_ordinal = trade.symbol_ordinal
            if not 0 <= trade.symbol_ordinal < len(plan.request.state.positions):
                raise InconsistentRebalanceProposalResultError(
                    "symbol ordinal is outside the configured universe"
                )
            if (
                plan.request.state.positions[trade.symbol_ordinal].symbol
                != trade.symbol
            ):
                raise InconsistentRebalanceProposalResultError(
                    "planned trade symbol does not match its ordinal"
                )
            if (
                not isinstance(trade.planned_quantity, Decimal)
                or not trade.planned_quantity.is_finite()
                or trade.planned_quantity <= _ZERO
            ):
                raise InconsistentRebalanceProposalResultError(
                    "planned quantity must be a positive finite Decimal"
                )

    @staticmethod
    def _diagnostics(
        plan: RebalancePlan,
    ) -> tuple[RebalanceProposalDiagnostic, ...]:
        if plan.status is RebalanceStatus.PARTIAL:
            return (
                RebalanceProposalDiagnostic(
                    RebalanceProposalDiagnosticCode.PARTIAL_PLAN_ACCEPTED,
                    "partial plan accepted; estimated_constraints_satisfied="
                    f"{plan.estimated_constraints_satisfied}",
                ),
            )
        if plan.status is RebalanceStatus.NO_ACTION:
            return (
                RebalanceProposalDiagnostic(
                    RebalanceProposalDiagnosticCode.NO_ACTION,
                    "rebalance plan requires no trade proposals",
                ),
            )
        return ()


def _canonical_decimal(value: Decimal) -> str:
    normalized = _ZERO if value == _ZERO else value.normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _canonical_timestamp(value: datetime) -> str:
    return normalize_utc(value, "timestamp").isoformat()


def _reason(plan: RebalancePlan, trade: PlannedTrade, side: OrderSide) -> str:
    partial = " (PARTIAL)" if plan.status is RebalanceStatus.PARTIAL else ""
    return (
        f"Rebalance plan {plan.plan_id}{partial}: {side.value} {trade.symbol} "
        f"toward target weight {_canonical_decimal(trade.target_weight)}"
    )


def _proposal_id(
    request: RebalanceProposalRequest,
    trade: PlannedTrade,
    ordinal: int,
    side: OrderSide,
) -> UUID:
    confidence = (
        "none" if request.confidence is None else _canonical_decimal(request.confidence)
    )
    identity = "|".join(
        (
            _REASON_VERSION,
            str(request.request_id),
            str(request.plan.plan_id),
            str(trade.planned_trade_id),
            str(ordinal),
            str(trade.symbol_ordinal),
            str(trade.symbol),
            side.value,
            _canonical_decimal(trade.planned_quantity),
            _canonical_timestamp(request.proposal_created_at),
            confidence,
            request.plan.status.value,
            _canonical_decimal(trade.target_weight),
        )
    )
    return uuid5(_PROPOSAL_NAMESPACE, identity)


def _request_fingerprint(request: RebalanceProposalRequest) -> str:
    metadata = "|".join(f"{item.key}={item.value}" for item in request.metadata)
    confidence = (
        "none" if request.confidence is None else _canonical_decimal(request.confidence)
    )
    return "|".join(
        (
            _REASON_VERSION,
            str(request.request_id),
            str(request.plan.plan_id),
            _canonical_timestamp(request.proposal_created_at),
            str(request.policy.allow_partial_plans),
            confidence,
            metadata,
        )
    )


def _result_id(
    request: RebalanceProposalRequest,
    status: RebalanceProposalStatus,
    proposals: tuple[TradeProposal, ...],
    diagnostic_codes: tuple[RebalanceProposalDiagnosticCode, ...],
) -> UUID:
    identity = "|".join(
        (
            _request_fingerprint(request),
            status.value,
            ",".join(str(item.proposal_id) for item in proposals),
            ",".join(item.value for item in diagnostic_codes),
        )
    )
    return uuid5(_PROPOSAL_NAMESPACE, f"result|{identity}")


def _validate_proposal_mapping(
    request: RebalanceProposalRequest,
    proposal: TradeProposal,
    trade: PlannedTrade,
    ordinal: int,
) -> None:
    side = _SIDE_MAPPING.get(trade.side)
    if side is None:
        raise InconsistentRebalanceProposalResultError(
            "planned trade side is unsupported"
        )
    if (
        proposal.proposal_id != _proposal_id(request, trade, ordinal, side)
        or proposal.symbol != trade.symbol
        or proposal.side is not side
        or proposal.desired_quantity != trade.planned_quantity
        or proposal.created_at != request.proposal_created_at
        or proposal.reason != _reason(request.plan, trade, side)
        or proposal.confidence != request.confidence
    ):
        raise InconsistentRebalanceProposalResultError(
            "proposal does not match its planned trade"
        )
