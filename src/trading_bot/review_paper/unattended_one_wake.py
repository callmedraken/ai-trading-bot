"""133-C: one durable wake, with typed fake quote/effect edges only.

This module binds no provider or paper writer. The supplied 131 store is used
only by the accepted read-only 131-O/K preview and predecessor checks. The
131-Q freshness and exact-material revalidation rules are preserved without
calling its clock-reading PREPARE/EXECUTE or production composition functions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from trading_bot.domain import Symbol
from trading_bot.review_paper.forward_preview import (
    ReviewPaperForwardPreview,
    build_review_paper_forward_preview,
)
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.review_paper.risk_prices import ReviewPaperRiskPriceSnapshot
from trading_bot.review_paper.session_admission import (
    ReviewPaperSessionAdmission,
    ReviewPaperSessionSchedule,
    ReviewPaperSessionStatus,
    admit_review_paper_session,
)
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.review_paper.unattended_activation import (
    ReviewPaperActivation,
    ReviewPaperWakeState,
)
from trading_bot.review_paper.unattended_state_schema import (
    PersistedReviewPaperWake,
    UnattendedStateConflict,
    UnattendedStateError,
)
from trading_bot.review_paper.unattended_state_store import UnattendedStateStore
from trading_bot.risk.models import RiskOutcome


def _utc(value: datetime) -> datetime:
    if type(value) is not datetime:
        raise TypeError("wake instants must be exact datetime values")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("wake instants must be timezone-aware")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class OneWakeInstants:
    started_at: datetime
    pre_effect_at: datetime
    finished_at: datetime

    def __post_init__(self) -> None:
        for name in ("started_at", "pre_effect_at", "finished_at"):
            object.__setattr__(self, name, _utc(getattr(self, name)))
        if not self.started_at <= self.pre_effect_at <= self.finished_at:
            raise ValueError("wake instants must not move backward")


class OneWakeQuoteSeam(Protocol):
    """Test-only one-acquisition edge, returning exact accepted 131-N material."""

    def prepare_quote(
        self,
        *,
        activation: ReviewPaperActivation,
        required_symbols: tuple[Symbol, ...],
        as_of: datetime,
    ) -> ReviewPaperRiskPriceSnapshot: ...


@dataclass(frozen=True, slots=True)
class OneWakeSyntheticEffectResult:
    """Closed fake acknowledgement; no provider payload or account identity."""

    activation_id: UUID
    wake_id: UUID
    local_order_id: UUID
    completed: bool

    def __post_init__(self) -> None:
        for name in ("activation_id", "wake_id", "local_order_id"):
            if type(getattr(self, name)) is not UUID:
                raise TypeError("synthetic result identities must be exact UUIDs")
        if type(self.completed) is not bool:
            raise TypeError("synthetic completion must be exactly bool")


class OneWakeEffectSeam(Protocol):
    """Test-only review/paper acknowledgement, never a production binding."""

    def simulate_review_paper(
        self,
        *,
        activation: ReviewPaperActivation,
        persisted: PersistedReviewPaperWake,
        preview: ReviewPaperForwardPreview,
        as_of: datetime,
    ) -> OneWakeSyntheticEffectResult: ...


class OneWakeClassification(StrEnum):
    COMPLETED = "COMPLETED"
    REPLAY = "REPLAY"
    RECONCILIATION_ONLY = "RECONCILIATION_ONLY"
    SESSION_NOT_ADMITTED = "SESSION_NOT_ADMITTED"
    QUOTE_NOT_VALID = "QUOTE_NOT_VALID"
    RISK_REJECTED = "RISK_REJECTED"
    MATERIAL_DRIFT = "MATERIAL_DRIFT"
    PRE_EFFECT_FAILURE = "PRE_EFFECT_FAILURE"
    EFFECT_INDETERMINATE = "EFFECT_INDETERMINATE"


@dataclass(frozen=True, slots=True)
class OneWakeResult:
    """Bounded immutable facts; attempt counts describe this invocation only."""

    activation_id: UUID
    wake_id: UUID
    revisions: tuple[int, ...]
    transitions: tuple[ReviewPaperWakeState, ...]
    schedule: ReviewPaperSessionSchedule | None
    admissions: tuple[ReviewPaperSessionAdmission, ...]
    quote_valid_until: datetime | None
    risk_outcome: RiskOutcome | None
    quote_attempts: int
    effect_attempts: int
    final_state: ReviewPaperWakeState
    classification: OneWakeClassification


class OneWakeStateError(UnattendedStateError):
    """A durability failure grants no further edge or compensation authority."""


def compose_one_review_paper_wake(
    *,
    activation: ReviewPaperActivation,
    expected: PersistedReviewPaperWake,
    state_store: UnattendedStateStore,
    paper_store: ReviewPaperStore,
    instants: OneWakeInstants,
    quote_seam: OneWakeQuoteSeam,
    effect_seam: OneWakeEffectSeam,
) -> OneWakeResult:
    """Run once from exact durable READY; replay never calls either seam.

    State-write failures propagate as sanitized reconciliation errors. No retry
    or compensating CAS follows a failed write, including a terminal write after
    an effect. A surviving REVIEW_STARTED remains ambiguous on every reopen.
    """
    for value, kind in (
        (activation, ReviewPaperActivation),
        (expected, PersistedReviewPaperWake),
        (state_store, UnattendedStateStore),
        (paper_store, ReviewPaperStore),
        (instants, OneWakeInstants),
    ):
        if type(value) is not kind:
            raise TypeError("one wake requires exact accepted boundary types")
    try:
        current = state_store.snapshot().current(activation)
    except Exception:
        raise OneWakeStateError("durable wake could not be verified") from None
    if (
        current != expected
        or expected.wake.activation.to_json() != activation.to_json()
    ):
        raise UnattendedStateConflict(
            "exact persisted activation/wake/revision required"
        )

    states = [current.wake.state]
    revisions = [current.revision]
    admissions: list[ReviewPaperSessionAdmission] = []
    schedule = None
    deadline = None
    outcome = None
    quote_attempts = 0
    effect_attempts = 0
    # The caller supplies lower-bound/fakeable instants. A real quote seam may
    # observe the response later; that later observation must advance every
    # remaining freshness/session/effect fence rather than be compared to an
    # already-stale pre-request timestamp.
    pre_effect_at = instants.pre_effect_at
    finished_at = instants.finished_at

    def result(classification: OneWakeClassification) -> OneWakeResult:
        return OneWakeResult(
            activation.activation_id,
            current.wake.wake_id,
            tuple(revisions),
            tuple(states),
            schedule,
            tuple(admissions),
            deadline,
            outcome,
            quote_attempts,
            effect_attempts,
            current.wake.state,
            classification,
        )

    def transition(state: ReviewPaperWakeState, at: datetime) -> None:
        nonlocal current
        try:
            current = state_store.transition(current, state=state, at=at)
        except BaseException:
            raise OneWakeStateError(
                "durable transition failed; reconciliation required"
            ) from None
        states.append(current.wake.state)
        revisions.append(current.revision)

    def stop(classification: OneWakeClassification, at: datetime) -> OneWakeResult:
        transition(ReviewPaperWakeState.STOPPED, at)
        return result(classification)

    def admit(at: datetime) -> ReviewPaperSessionAdmission:
        admission = admit_review_paper_session(
            schedule=schedule,
            as_of=at,
            opening_buffer=activation.opening_buffer,
            closing_buffer=activation.closing_buffer,
        )
        admissions.append(admission)
        return admission

    def preview(snapshot: ReviewPaperRiskPriceSnapshot) -> ReviewPaperForwardPreview:
        value = build_review_paper_forward_preview(
            store=paper_store,
            proposal=activation.proposal,
            price_snapshot=snapshot,
            risk_limits=activation.risk_limits,
            new_trading_enabled=activation.new_trading_enabled,
        )
        if (
            type(value) is not ReviewPaperForwardPreview
            or value.proposal is not activation.proposal
            or value.price_snapshot is not snapshot
            or value.risk_limits is not activation.risk_limits
            or value.risk_context.new_trading_enabled
            is not activation.new_trading_enabled
        ):
            raise ValueError("preview changed exact frozen inputs")
        return value

    if current.wake.state in (
        ReviewPaperWakeState.COMPLETED,
        ReviewPaperWakeState.STOPPED,
        ReviewPaperWakeState.INDETERMINATE,
    ):
        return result(OneWakeClassification.REPLAY)
    if current.wake.state is not ReviewPaperWakeState.READY:
        return result(OneWakeClassification.RECONCILIATION_ONLY)
    if instants.started_at < current.wake.updated_at:
        raise ValueError("wake must not precede durable state")

    # No external edge before exact session admission and the durable start fence.
    try:
        schedule = NYSEPublishedRegularSessionAuthority().schedule_for(
            activation.target_session_date
        )
        if (
            schedule is None
            or type(schedule) is not ReviewPaperSessionSchedule
            or schedule.session_date != activation.target_session_date
        ):
            classification = OneWakeClassification.SESSION_NOT_ADMITTED
        elif admit(instants.started_at).status is not ReviewPaperSessionStatus.ADMITTED:
            classification = OneWakeClassification.SESSION_NOT_ADMITTED
        elif (
            str(paper_store.path) != activation.store_path
            or paper_store.starting_cash != activation.starting_cash
        ):
            classification = OneWakeClassification.MATERIAL_DRIFT
        else:
            classification = None
    except BaseException:
        classification = OneWakeClassification.PRE_EFFECT_FAILURE
    if classification is not None:
        return stop(classification, instants.started_at)

    transition(ReviewPaperWakeState.PREPARE_STARTED, instants.started_at)
    try:
        history = paper_store.history()
        ledger = paper_store.reconstruct_ledger()
        symbols = tuple(
            sorted(set(ledger.positions) | {activation.proposal.symbol}, key=str)
        )
        quote_attempts = 1
        snapshot = quote_seam.prepare_quote(
            activation=activation,
            required_symbols=symbols,
            as_of=instants.started_at,
        )
        if type(snapshot) is not ReviewPaperRiskPriceSnapshot:
            raise TypeError("quote seam must return exact 131-N snapshot")
        pre_effect_at = max(pre_effect_at, snapshot.observed_at)
        finished_at = max(finished_at, pre_effect_at)
        deadline = min(
            mark.source_at + activation.max_quote_age for mark in snapshot.marks
        )
        if (
            snapshot.observed_at < instants.started_at
            or deadline < snapshot.observed_at
        ):
            classification = OneWakeClassification.QUOTE_NOT_VALID
        elif (
            admit(snapshot.observed_at).status is not ReviewPaperSessionStatus.ADMITTED
        ):
            classification = OneWakeClassification.SESSION_NOT_ADMITTED
        else:
            prepared = preview(snapshot)
            outcome = prepared.risk_decision.outcome
            if history != paper_store.history():
                classification = OneWakeClassification.MATERIAL_DRIFT
            elif outcome is RiskOutcome.REJECTED:
                classification = OneWakeClassification.RISK_REJECTED
            else:
                classification = None
    except BaseException:
        classification = OneWakeClassification.PRE_EFFECT_FAILURE
    if classification is not None:
        return stop(classification, pre_effect_at)

    transition(ReviewPaperWakeState.PREPARED, snapshot.observed_at)
    try:
        if admit(pre_effect_at).status is not ReviewPaperSessionStatus.ADMITTED:
            classification = OneWakeClassification.SESSION_NOT_ADMITTED
        elif pre_effect_at > deadline:
            classification = OneWakeClassification.QUOTE_NOT_VALID
        else:
            revalidated = preview(snapshot)
            if (
                revalidated.risk_context != prepared.risk_context
                or revalidated.risk_decision != prepared.risk_decision
                or paper_store.history() != history
                or str(paper_store.path) != activation.store_path
                or paper_store.starting_cash != activation.starting_cash
            ):
                classification = OneWakeClassification.MATERIAL_DRIFT
            else:
                classification = None
    except BaseException:
        classification = OneWakeClassification.PRE_EFFECT_FAILURE
    if classification is not None:
        return stop(classification, pre_effect_at)

    transition(ReviewPaperWakeState.REVIEW_STARTED, pre_effect_at)
    effect_attempts = 1
    try:
        acknowledgement = effect_seam.simulate_review_paper(
            activation=activation,
            persisted=current,
            preview=revalidated,
            as_of=pre_effect_at,
        )
        completed = (
            type(acknowledgement) is OneWakeSyntheticEffectResult
            and acknowledgement.completed is True
            and acknowledgement.activation_id == activation.activation_id
            and acknowledgement.wake_id == current.wake.wake_id
            and acknowledgement.local_order_id == activation.local_order_id
        )
    except BaseException:
        completed = False
    transition(
        ReviewPaperWakeState.COMPLETED
        if completed
        else ReviewPaperWakeState.INDETERMINATE,
        finished_at,
    )
    return result(
        OneWakeClassification.COMPLETED
        if completed
        else OneWakeClassification.EFFECT_INDETERMINATE
    )
