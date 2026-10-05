"""Two-phase supervised paper composition with a separate human proceed call."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from trading_bot.domain import TradeProposal
from trading_bot.execution.models import ExecutionInstruction
from trading_bot.review_paper.forward_preview import (
    ReviewPaperForwardPreview,
    build_review_paper_forward_preview,
)
from trading_bot.review_paper.models import ReviewPaperRecord
from trading_bot.review_paper.risk_price_acquisition import (
    acquire_review_paper_risk_price_snapshot,
)
from trading_bot.review_paper.risk_prices import ReviewPaperRiskPriceSnapshot
from trading_bot.review_paper.session_admission import (
    ReviewPaperSessionAdmission,
    ReviewPaperSessionSchedule,
    ReviewPaperSessionStatus,
    admit_review_paper_session,
)
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.risk.models import RiskLimits, RiskOutcome
from trading_bot.robinhood_forward_paper_cycle import run_robinhood_forward_paper_cycle
from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter
from trading_bot.robinhood_paper_pipeline import (
    RobinhoodDeterministicPaperPipelineResult,
)

_DATETIME_TYPE = datetime


class ReviewPaperSupervisedPreparationStatus(StrEnum):
    SESSION_NOT_ADMITTED = "SESSION_NOT_ADMITTED"
    SESSION_EXPIRED_DURING_ACQUISITION = "SESSION_EXPIRED_DURING_ACQUISITION"
    RISK_REJECTED = "RISK_REJECTED"
    READY_TO_PROCEED = "READY_TO_PROCEED"


def _require_inputs(
    store: ReviewPaperStore,
    proposal: TradeProposal,
    schedule: ReviewPaperSessionSchedule,
    opening_buffer: timedelta,
    closing_buffer: timedelta,
    max_quote_age: timedelta,
    risk_limits: RiskLimits,
    new_trading_enabled: bool,
) -> None:
    for name, value, expected in (
        ("store", store, ReviewPaperStore),
        ("proposal", proposal, TradeProposal),
        ("schedule", schedule, ReviewPaperSessionSchedule),
        ("opening_buffer", opening_buffer, timedelta),
        ("closing_buffer", closing_buffer, timedelta),
        ("max_quote_age", max_quote_age, timedelta),
        ("risk_limits", risk_limits, RiskLimits),
        ("new_trading_enabled", new_trading_enabled, bool),
    ):
        if type(value) is not expected:
            raise TypeError(f"{name} must be exactly {expected.__name__}")
    if max_quote_age <= timedelta(0):
        raise ValueError("max_quote_age must be strictly positive")
    if opening_buffer < timedelta(0) or closing_buffer < timedelta(0):
        raise ValueError("buffers must be nonnegative")
    duration = schedule.closes_at - schedule.opens_at
    if opening_buffer >= duration or closing_buffer >= duration - opening_buffer:
        raise ValueError("buffers must leave a nonempty admission interval")


def _require_admission(
    admission: ReviewPaperSessionAdmission,
    schedule: ReviewPaperSessionSchedule,
    opening_buffer: timedelta,
    closing_buffer: timedelta,
) -> None:
    if type(admission) is not ReviewPaperSessionAdmission:
        raise TypeError("admission must be exactly ReviewPaperSessionAdmission")
    if (
        admission.session_date != schedule.session_date
        or admission.opens_at != schedule.opens_at
        or admission.closes_at != schedule.closes_at
        or admission.admission_opens_at != schedule.opens_at + opening_buffer
        or admission.admission_closes_at != schedule.closes_at - closing_buffer
    ):
        raise ValueError("admission must match the prepared schedule and buffers")


def _require_preview(
    preview: ReviewPaperForwardPreview,
    preparation: ReviewPaperSupervisedPreparation,
) -> None:
    if type(preview) is not ReviewPaperForwardPreview:
        raise TypeError("preview must be exactly ReviewPaperForwardPreview")
    if (
        preview.proposal is not preparation.proposal
        or preview.price_snapshot is not preparation.price_snapshot
        or preview.risk_limits is not preparation.risk_limits
        or preview.risk_context.new_trading_enabled
        is not preparation.new_trading_enabled
    ):
        raise ValueError("preview must preserve the exact prepared inputs")


def _quote_deadline(
    snapshot: ReviewPaperRiskPriceSnapshot, max_quote_age: timedelta
) -> datetime:
    # Overflow propagates: never clamp or extend validity.
    deadline = min(mark.source_at + max_quote_age for mark in snapshot.marks)
    if deadline < snapshot.observed_at:
        raise ValueError("quote deadline must not precede snapshot observation")
    return deadline.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class ReviewPaperSupervisedPreparation:
    """Read-only review material, with execution state only for completed previews."""

    status: ReviewPaperSupervisedPreparationStatus
    store: ReviewPaperStore
    proposal: TradeProposal
    schedule: ReviewPaperSessionSchedule
    opening_buffer: timedelta
    closing_buffer: timedelta
    max_quote_age: timedelta
    risk_limits: RiskLimits
    new_trading_enabled: bool
    initial_admission: ReviewPaperSessionAdmission
    price_snapshot: ReviewPaperRiskPriceSnapshot | None = None
    quote_admission: ReviewPaperSessionAdmission | None = None
    preview: ReviewPaperForwardPreview | None = None
    durable_history: tuple[ReviewPaperRecord, ...] | None = None
    quote_valid_until: datetime | None = None

    def __post_init__(self) -> None:
        if type(self.status) is not ReviewPaperSupervisedPreparationStatus:
            raise TypeError(
                "status must be exactly ReviewPaperSupervisedPreparationStatus"
            )
        _require_inputs(
            self.store,
            self.proposal,
            self.schedule,
            self.opening_buffer,
            self.closing_buffer,
            self.max_quote_age,
            self.risk_limits,
            self.new_trading_enabled,
        )
        _require_admission(
            self.initial_admission,
            self.schedule,
            self.opening_buffer,
            self.closing_buffer,
        )
        if self.status is ReviewPaperSupervisedPreparationStatus.SESSION_NOT_ADMITTED:
            if (
                self.initial_admission.status is ReviewPaperSessionStatus.ADMITTED
                or any(
                    value is not None
                    for value in (
                        self.price_snapshot,
                        self.quote_admission,
                        self.preview,
                        self.durable_history,
                        self.quote_valid_until,
                    )
                )
            ):
                raise ValueError(
                    "blocked initial admission must have no acquired state"
                )
            return
        if self.initial_admission.status is not ReviewPaperSessionStatus.ADMITTED:
            raise ValueError("acquired state requires initial admission")
        if type(self.price_snapshot) is not ReviewPaperRiskPriceSnapshot:
            raise TypeError(
                "price_snapshot must be exactly ReviewPaperRiskPriceSnapshot"
            )
        _require_admission(
            self.quote_admission,
            self.schedule,
            self.opening_buffer,
            self.closing_buffer,
        )
        if self.quote_admission.as_of != self.price_snapshot.observed_at:
            raise ValueError("quote admission must use snapshot observation")
        if (
            self.status
            is ReviewPaperSupervisedPreparationStatus.SESSION_EXPIRED_DURING_ACQUISITION
        ):
            if (
                self.quote_admission.status is ReviewPaperSessionStatus.ADMITTED
                or self.preview is not None
                or self.durable_history is not None
                or self.quote_valid_until is not None
            ):
                raise ValueError(
                    "expired acquisition must have no execution-capable state"
                )
            return
        if self.quote_admission.status is not ReviewPaperSessionStatus.ADMITTED:
            raise ValueError("completed preview requires quote-time admission")
        _require_preview(self.preview, self)
        rejected = self.preview.risk_decision.outcome is RiskOutcome.REJECTED
        if rejected != (
            self.status is ReviewPaperSupervisedPreparationStatus.RISK_REJECTED
        ):
            raise ValueError("preparation status must match risk outcome")
        if type(self.durable_history) is not tuple or any(
            type(record) is not ReviewPaperRecord for record in self.durable_history
        ):
            raise TypeError(
                "durable_history must be exactly a tuple of ReviewPaperRecord"
            )
        if type(self.quote_valid_until) is not _DATETIME_TYPE:
            raise TypeError("quote_valid_until must be exactly datetime")
        if (
            self.quote_valid_until.tzinfo is None
            or self.quote_valid_until.utcoffset() is None
        ):
            raise ValueError("quote_valid_until must be timezone-aware")
        deadline = self.quote_valid_until.astimezone(UTC)
        if deadline != _quote_deadline(self.price_snapshot, self.max_quote_age):
            raise ValueError(
                "quote_valid_until must be the earliest exact mark deadline"
            )
        object.__setattr__(self, "quote_valid_until", deadline)


def prepare_review_paper_supervised_cycle(
    *,
    store: ReviewPaperStore,
    proposal: TradeProposal,
    schedule: ReviewPaperSessionSchedule,
    opening_buffer: timedelta,
    closing_buffer: timedelta,
    adapter: RobinhoodReviewReadAdapter,
    max_quote_age: timedelta,
    risk_limits: RiskLimits,
    new_trading_enabled: bool,
) -> ReviewPaperSupervisedPreparation:
    """Acquire and preview once; calling this function never grants execution."""
    _require_inputs(
        store,
        proposal,
        schedule,
        opening_buffer,
        closing_buffer,
        max_quote_age,
        risk_limits,
        new_trading_enabled,
    )
    if type(adapter) is not RobinhoodReviewReadAdapter:
        raise TypeError("adapter must be exactly RobinhoodReviewReadAdapter")
    prepare_started_at = datetime.now(UTC)
    initial_admission = admit_review_paper_session(
        schedule=schedule,
        as_of=prepare_started_at,
        opening_buffer=opening_buffer,
        closing_buffer=closing_buffer,
    )
    common = dict(
        store=store,
        proposal=proposal,
        schedule=schedule,
        opening_buffer=opening_buffer,
        closing_buffer=closing_buffer,
        max_quote_age=max_quote_age,
        risk_limits=risk_limits,
        new_trading_enabled=new_trading_enabled,
        initial_admission=initial_admission,
    )
    if initial_admission.status is not ReviewPaperSessionStatus.ADMITTED:
        return ReviewPaperSupervisedPreparation(
            status=ReviewPaperSupervisedPreparationStatus.SESSION_NOT_ADMITTED,
            **common,
        )
    durable_history_before = store.history()
    price_snapshot = acquire_review_paper_risk_price_snapshot(
        store=store,
        proposal=proposal,
        adapter=adapter,
        max_quote_age=max_quote_age,
    )
    quote_admission = admit_review_paper_session(
        schedule=schedule,
        as_of=price_snapshot.observed_at,
        opening_buffer=opening_buffer,
        closing_buffer=closing_buffer,
    )
    if quote_admission.status is not ReviewPaperSessionStatus.ADMITTED:
        return ReviewPaperSupervisedPreparation(
            status=ReviewPaperSupervisedPreparationStatus.SESSION_EXPIRED_DURING_ACQUISITION,
            price_snapshot=price_snapshot,
            quote_admission=quote_admission,
            **common,
        )
    preview = build_review_paper_forward_preview(
        store=store,
        proposal=proposal,
        price_snapshot=price_snapshot,
        risk_limits=risk_limits,
        new_trading_enabled=new_trading_enabled,
    )
    durable_history_after = store.history()
    if durable_history_before != durable_history_after:
        raise RuntimeError("durable history changed during preparation; prepare afresh")
    quote_valid_until = _quote_deadline(price_snapshot, max_quote_age)
    status = (
        ReviewPaperSupervisedPreparationStatus.RISK_REJECTED
        if preview.risk_decision.outcome is RiskOutcome.REJECTED
        else ReviewPaperSupervisedPreparationStatus.READY_TO_PROCEED
    )
    return ReviewPaperSupervisedPreparation(
        status=status,
        price_snapshot=price_snapshot,
        quote_admission=quote_admission,
        preview=preview,
        durable_history=durable_history_before,
        quote_valid_until=quote_valid_until,
        **common,
    )


@dataclass(frozen=True, slots=True)
class ReviewPaperSupervisedExecutionResult:
    """Preserve revalidation and the exact accepted pipeline/operator result."""

    preparation: ReviewPaperSupervisedPreparation
    execute_admission: ReviewPaperSessionAdmission
    revalidated_preview: ReviewPaperForwardPreview
    pipeline_result: RobinhoodDeterministicPaperPipelineResult

    def __post_init__(self) -> None:
        if type(self.preparation) is not ReviewPaperSupervisedPreparation:
            raise TypeError(
                "preparation must be exactly ReviewPaperSupervisedPreparation"
            )
        if (
            self.preparation.status
            is not ReviewPaperSupervisedPreparationStatus.READY_TO_PROCEED
        ):
            raise ValueError("execution requires READY_TO_PROCEED preparation")
        _require_admission(
            self.execute_admission,
            self.preparation.schedule,
            self.preparation.opening_buffer,
            self.preparation.closing_buffer,
        )
        if self.execute_admission.status is not ReviewPaperSessionStatus.ADMITTED:
            raise ValueError("execution requires current session admission")
        if self.execute_admission.as_of > self.preparation.quote_valid_until:
            raise ValueError("execution admission exceeds quote validity")
        _require_preview(self.revalidated_preview, self.preparation)
        if (
            self.revalidated_preview.risk_context
            != self.preparation.preview.risk_context
            or self.revalidated_preview.risk_decision
            != self.preparation.preview.risk_decision
        ):
            raise ValueError("revalidated risk context/decision must match preparation")
        if type(self.pipeline_result) is not RobinhoodDeterministicPaperPipelineResult:
            raise TypeError(
                "pipeline_result must be exactly "
                "RobinhoodDeterministicPaperPipelineResult"
            )
        if self.pipeline_result.risk_decision != self.revalidated_preview.risk_decision:
            raise ValueError("pipeline risk decision differs from revalidation")


def execute_review_paper_supervised_cycle(
    *,
    preparation: ReviewPaperSupervisedPreparation,
    instruction: ExecutionInstruction,
    order_id: UUID,
    expected_branch: str,
    expected_head: str,
    expected_tree: str,
    evidence_path: Path,
    redirect_uri: str,
    slippage_basis_points: Decimal,
    commission: Decimal,
) -> ReviewPaperSupervisedExecutionResult:
    """Explicit human proceed boundary; stop on expiry/drift and never retry."""
    if type(preparation) is not ReviewPaperSupervisedPreparation:
        raise TypeError("preparation must be exactly ReviewPaperSupervisedPreparation")
    if (
        preparation.status
        is not ReviewPaperSupervisedPreparationStatus.READY_TO_PROCEED
    ):
        raise ValueError("execution requires READY_TO_PROCEED preparation")
    if type(instruction) is not ExecutionInstruction:
        raise TypeError("instruction must be exactly ExecutionInstruction")
    if type(order_id) is not UUID:
        raise TypeError("order_id must be exactly UUID")
    execute_at = datetime.now(UTC)
    execute_admission = admit_review_paper_session(
        schedule=preparation.schedule,
        as_of=execute_at,
        opening_buffer=preparation.opening_buffer,
        closing_buffer=preparation.closing_buffer,
    )
    if execute_admission.status is not ReviewPaperSessionStatus.ADMITTED:
        raise RuntimeError("session no longer admitted; prepare afresh")
    if execute_at > preparation.quote_valid_until:
        raise RuntimeError("prepared quote expired; prepare afresh")
    revalidated_preview = build_review_paper_forward_preview(
        store=preparation.store,
        proposal=preparation.proposal,
        price_snapshot=preparation.price_snapshot,
        risk_limits=preparation.risk_limits,
        new_trading_enabled=preparation.new_trading_enabled,
    )
    _require_preview(revalidated_preview, preparation)
    if (
        revalidated_preview.risk_context != preparation.preview.risk_context
        or revalidated_preview.risk_decision != preparation.preview.risk_decision
    ):
        raise RuntimeError("prepared risk context/decision changed; prepare afresh")
    current_history = preparation.store.history()
    if current_history != preparation.durable_history:
        raise RuntimeError("prepared durable history changed; prepare afresh")
    if instruction.created_at < preparation.preview.risk_decision.evaluated_at:
        raise ValueError("instruction must not precede the prepared risk decision")
    pipeline_result = run_robinhood_forward_paper_cycle(
        store=preparation.store,
        proposal=preparation.proposal,
        prices=preparation.price_snapshot.prices,
        as_of=preparation.price_snapshot.observed_at,
        new_trading_enabled=preparation.new_trading_enabled,
        risk_limits=preparation.risk_limits,
        instruction=instruction,
        order_id=order_id,
        review_received_at=execute_at,
        expected_branch=expected_branch,
        expected_head=expected_head,
        expected_tree=expected_tree,
        evidence_path=evidence_path,
        redirect_uri=redirect_uri,
        slippage_basis_points=slippage_basis_points,
        commission=commission,
    )
    return ReviewPaperSupervisedExecutionResult(
        preparation,
        execute_admission,
        revalidated_preview,
        pipeline_result,
    )
