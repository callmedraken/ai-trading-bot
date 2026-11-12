"""Injected-only L43 effect ordering for a later separately reviewed boundary.

This module has no production composition.  Every provider-facing operation,
authorization, state session, fresh observation, and post-effect reconciliation
must be explicitly injected.  Its positive paths are intended for fakes only.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from trading_bot.live_prototype.durable_state import (
    IntentKind,
    IntentStatus,
    ReconciliationSnapshot,
)
from trading_bot.live_prototype.l43_pre_effect_observation import (
    L43PlanKind,
    L43PreEffectBlocker,
    L43PreEffectOutcome,
    L43PreEffectPlan,
    L43PreEffectResult,
)
from trading_bot.live_prototype.l43_provider_contracts import (
    L43EffectTransport,
    L43PlacementReceipt,
    L43ReviewNormalization,
    L43TransportError,
)
from trading_bot.live_prototype.l43_state import L43StateSession
from trading_bot.live_prototype.live_controller import PreparedInvocation
from trading_bot.live_prototype.tiny_live_policy import (
    ExactOwnedSellProposal,
    ManualCloseTrigger,
    NormalizedSellReview,
    SellOrderArguments,
    SellReviewValidationStatus,
    evaluate_exact_owned_sell_proposal,
    validate_normalized_sell_review,
)

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SAFE_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
_ACCOUNT_NUMBER = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
_ZERO = Decimal("0")


class L43EffectStage(StrEnum):
    ENTRY_PLACEMENT = "ENTRY_PLACEMENT"
    SELL_REVIEW = "SELL_REVIEW"
    SELL_PLACEMENT = "SELL_PLACEMENT"


class L43EffectOutcome(StrEnum):
    BLOCKED = "BLOCKED"
    NO_ACTION_SIGNAL = "NO_ACTION_SIGNAL"
    ENTRY_RECONCILED = "ENTRY_RECONCILED"
    ENTRY_PENDING = "ENTRY_PENDING"
    REVIEW_ACCEPTED = "REVIEW_ACCEPTED"
    MANUAL_CLOSE_REQUIRED = "MANUAL_CLOSE_REQUIRED"
    SELL_RECONCILED = "SELL_RECONCILED"
    EFFECT_UNKNOWN = "EFFECT_UNKNOWN"


@dataclass(frozen=True, slots=True)
class L43AuthorizationRequest:
    """Exact fresh facts presented to one independently injected grant seam."""

    stage: L43EffectStage
    plan_binding_sha256: str
    state_last_sequence: int
    state_tail_sha256: str
    source_head: str
    source_tree: str
    config_digest: str
    binding_digest: str
    account_fingerprint: str
    target_session: str
    signal_inputs_digest: str
    proposal_sha256: str | None = None
    arguments_sha256: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.stage, L43EffectStage):
            raise TypeError("authorization stage must be closed")
        for digest, label in (
            (self.plan_binding_sha256, "plan binding"),
            (self.state_tail_sha256, "state tail"),
            (self.config_digest, "configuration"),
            (self.binding_digest, "runtime binding"),
            (self.account_fingerprint, "account fingerprint"),
            (self.signal_inputs_digest, "signal inputs"),
        ):
            _require_sha256(digest, label)
        for value, label in (
            (self.source_head, "source HEAD"),
            (self.source_tree, "source tree"),
        ):
            if type(value) is not str or re.fullmatch(r"[0-9a-f]{40}", value) is None:
                raise ValueError(f"{label} must be a Git SHA-1")
        if type(self.state_last_sequence) is not int or self.state_last_sequence < 0:
            raise ValueError("authorization state sequence must be nonnegative")
        if (
            type(self.target_session) is not str
            or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", self.target_session) is None
        ):
            raise ValueError("authorization target session must be an ISO date")
        if self.stage is L43EffectStage.ENTRY_PLACEMENT:
            if self.proposal_sha256 is not None or self.arguments_sha256 is not None:
                raise ValueError("entry authorization cannot bind sell facts")
        else:
            _require_sha256(self.proposal_sha256, "sell proposal")
            _require_sha256(self.arguments_sha256, "sell arguments")

    @property
    def request_sha256(self) -> str:
        return _digest(
            (
                "ARCH147_L43_EXACT_STAGE_AUTHORIZATION_REQUEST_V1",
                self.stage.value,
                self.plan_binding_sha256,
                self.state_last_sequence,
                self.state_tail_sha256,
                self.source_head,
                self.source_tree,
                self.config_digest,
                self.binding_digest,
                self.account_fingerprint,
                self.target_session,
                self.signal_inputs_digest,
                self.proposal_sha256,
                self.arguments_sha256,
            )
        )


@dataclass(frozen=True, slots=True)
class L43StageAuthorization:
    """Explicit injected grant for exactly one request and stage."""

    request: L43AuthorizationRequest
    authority_sha256: str

    def __post_init__(self) -> None:
        if type(self.request) is not L43AuthorizationRequest:
            raise TypeError("authorization requires its exact typed request")
        _require_sha256(self.authority_sha256, "stage authority")


class L43ExactPlanAuthorizer(Protocol):
    """A future separately reviewed gate; this checkpoint supplies no grant."""

    def authorize(
        self, request: L43AuthorizationRequest
    ) -> L43StageAuthorization | None: ...


class L43EffectReobserver(Protocol):
    """Re-run the source-owned observer while the durable state lock is held."""

    def __call__(
        self,
        session: L43StateSession,
        *,
        requested_entry_risk: Decimal | None = None,
    ) -> L43PreEffectResult: ...


@dataclass(frozen=True, slots=True)
class L43PostEffectFacts:
    """Bounded, already normalized facts returned by an injected fake seam."""

    account_fingerprint: str
    snapshot: ReconciliationSnapshot
    positions_digest: str
    orders_digest: str
    order_scope_digest: str
    evidence_sha256: str
    all_relevant_orders_proven: bool

    def __post_init__(self) -> None:
        _require_sha256(self.account_fingerprint, "post-effect account fingerprint")
        if type(self.snapshot) is not ReconciliationSnapshot:
            raise TypeError("post-effect facts require a reconciliation snapshot")
        for digest, label in (
            (self.positions_digest, "post-effect positions"),
            (self.orders_digest, "post-effect orders"),
            (self.order_scope_digest, "post-effect order scope"),
            (self.evidence_sha256, "post-effect evidence"),
        ):
            _require_sha256(digest, label)
        if type(self.all_relevant_orders_proven) is not bool:
            raise TypeError("post-effect order coverage must be explicit")


class L43PostEffectReconciler(Protocol):
    """One bounded factual read after a placement; never a retry/cancel path."""

    async def reconcile(
        self,
        *,
        stage: L43EffectStage,
        plan: L43PreEffectPlan,
        intent_id: str,
        provider_order_id: str,
        known_state: object,
    ) -> L43PostEffectFacts: ...


class L43NormalizedReviewCaller(Protocol):
    """Return only the accepted normalized review DTO or transport normalization."""

    async def __call__(
        self, *, account_number: str, proposal: ExactOwnedSellProposal
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class L43AcceptedReviewReceipt:
    """Durable accepted review facts; never placement authority by itself."""

    authorization_sha256: str
    review_plan_binding_sha256: str
    proposal_sha256: str
    arguments_sha256: str
    review_evidence_sha256: str
    reviewed_arguments: SellOrderArguments
    accepted_state_sequence: int
    accepted_state_tail_sha256: str

    def __post_init__(self) -> None:
        for digest, label in (
            (self.authorization_sha256, "review stage authorization"),
            (self.review_plan_binding_sha256, "review plan"),
            (self.proposal_sha256, "review proposal"),
            (self.arguments_sha256, "review arguments"),
            (self.review_evidence_sha256, "review evidence"),
            (self.accepted_state_tail_sha256, "accepted review state tail"),
        ):
            _require_sha256(digest, label)
        if type(self.reviewed_arguments) is not SellOrderArguments:
            raise TypeError("accepted review requires exact normalized arguments")
        if (
            type(self.accepted_state_sequence) is not int
            or self.accepted_state_sequence < 0
        ):
            raise ValueError("accepted review sequence must be nonnegative")


@dataclass(frozen=True, slots=True)
class L43EffectResult:
    """Sanitized stage result; contains no provider payload or account number."""

    stage: L43EffectStage
    outcome: L43EffectOutcome
    reason_code: str
    evidence_sha256: str
    plan_binding_sha256: str | None
    authorization_sha256: str | None
    state_last_sequence: int | None
    state_tail_sha256: str | None
    confirmed_filled_quantity: Decimal | None = None
    accepted_review: L43AcceptedReviewReceipt | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.stage, L43EffectStage) or not isinstance(
            self.outcome, L43EffectOutcome
        ):
            raise TypeError("effect result uses closed stage and outcome")
        if (
            type(self.reason_code) is not str
            or _SAFE_CODE.fullmatch(self.reason_code) is None
        ):
            raise ValueError("effect result reason must be sanitized")
        _require_sha256(self.evidence_sha256, "effect evidence")
        for digest, label in (
            (self.plan_binding_sha256, "effect plan"),
            (self.authorization_sha256, "effect authorization"),
            (self.state_tail_sha256, "effect state tail"),
        ):
            if digest is not None:
                _require_sha256(digest, label)
        if self.state_last_sequence is not None and (
            type(self.state_last_sequence) is not int or self.state_last_sequence < 0
        ):
            raise ValueError("effect result state sequence is invalid")
        if self.confirmed_filled_quantity is not None and (
            type(self.confirmed_filled_quantity) is not Decimal
            or not self.confirmed_filled_quantity.is_finite()
            or self.confirmed_filled_quantity < _ZERO
        ):
            raise ValueError("confirmed fill quantity must be nonnegative")
        if (
            self.accepted_review is not None
            and type(self.accepted_review) is not L43AcceptedReviewReceipt
        ):
            raise TypeError("accepted review receipt must be typed")


class L43EffectOperator:
    """Fake-injectable three-stage operator with durable-before-effect order."""

    __slots__ = (
        "_session_factory",
        "_transport",
        "_authorizer",
        "_reobserver",
        "_reconciler",
        "_review_caller",
    )

    def __init__(
        self,
        *,
        session_factory: Callable[[], L43StateSession],
        transport: L43EffectTransport,
        authorizer: L43ExactPlanAuthorizer,
        reobserver: L43EffectReobserver,
        reconciler: L43PostEffectReconciler,
        review_caller: L43NormalizedReviewCaller | None = None,
    ) -> None:
        if not callable(session_factory):
            raise TypeError("state session factory must be injected")
        if not all(
            callable(getattr(transport, name, None))
            for name in (
                "prepare_entry_order",
                "prepare_sell_order",
                "review_sell_order",
            )
        ):
            raise TypeError("L43 transport must provide the neutral effect contract")
        if not callable(getattr(authorizer, "authorize", None)):
            raise TypeError("exact-plan authorizer must be injected")
        if not callable(reobserver):
            raise TypeError("locked reobserver must be injected")
        if not callable(getattr(reconciler, "reconcile", None)):
            raise TypeError("post-effect reconciler must be injected")
        if review_caller is None:
            review_caller = transport.review_sell_order
        if not callable(review_caller):
            raise TypeError("normalized review caller must be callable")
        self._session_factory = session_factory
        self._transport = transport
        self._authorizer = authorizer
        self._reobserver = reobserver
        self._reconciler = reconciler
        self._review_caller = review_caller

    async def place_entry(
        self, pre_effect: L43PreEffectResult, *, account_number: str
    ) -> L43EffectResult:
        """Stage, authorize, reserve, MAY, place once, and reconcile entry."""

        plan = _ready_plan(
            pre_effect,
            outcome=L43PreEffectOutcome.READY_FOR_L43_ENTRY_EFFECT_REVIEW,
            kind=L43PlanKind.ENTRY,
        )
        if plan is None:
            return self._result(
                L43EffectStage.ENTRY_PLACEMENT,
                L43EffectOutcome.NO_ACTION_SIGNAL
                if pre_effect.outcome is L43PreEffectOutcome.NO_ACTION_SIGNAL
                else L43EffectOutcome.BLOCKED,
                "ENTRY_PLAN_UNAVAILABLE",
                pre_effect.plan,
                None,
                None,
            )
        if not _account_matches(plan, account_number):
            return self._result(
                L43EffectStage.ENTRY_PLACEMENT,
                L43EffectOutcome.BLOCKED,
                "ACCOUNT_FINGERPRINT_MISMATCH",
                plan,
                None,
                None,
            )
        risk = plan.requested_entry_risk
        assert risk is not None
        completed_result: L43EffectResult | None = None
        try:
            async with self._transport.prepare_entry_order(
                account_number=account_number,
                requested_dollars=risk,
            ) as prepared:
                with self._session_factory() as session:
                    initial = self._fresh_result(session, requested_entry_risk=risk)
                    fresh = self._matching_plan(
                        pre_effect,
                        initial,
                        expected_kind=L43PlanKind.ENTRY,
                        requested_entry_risk=risk,
                        snapshot=session.snapshot(),
                    )
                    if fresh is None:
                        return self._result(
                            L43EffectStage.ENTRY_PLACEMENT,
                            L43EffectOutcome.BLOCKED,
                            "ENTRY_REVALIDATION_CHANGED",
                            initial.plan,
                            None,
                            session.snapshot(),
                        )
                    if not session.state.reconciled:
                        if not self._persist_clean_reconciliation(session, fresh):
                            return self._result(
                                L43EffectStage.ENTRY_PLACEMENT,
                                L43EffectOutcome.BLOCKED,
                                "INITIAL_RECONCILIATION_FAILED",
                                fresh,
                                None,
                                session.snapshot(),
                            )
                        after_reconcile = self._fresh_result(
                            session, requested_entry_risk=risk
                        )
                        reconciled_plan = _ready_plan(
                            after_reconcile,
                            outcome=L43PreEffectOutcome.READY_FOR_L43_ENTRY_EFFECT_REVIEW,
                            kind=L43PlanKind.ENTRY,
                        )
                        if reconciled_plan is None or not _same_plan_facts_except_tail(
                            fresh, reconciled_plan
                        ):
                            return self._result(
                                L43EffectStage.ENTRY_PLACEMENT,
                                L43EffectOutcome.BLOCKED,
                                "ENTRY_FACTS_CHANGED_AFTER_RECONCILIATION",
                                reconciled_plan,
                                None,
                                session.snapshot(),
                            )
                        fresh = reconciled_plan
                    snapshot = session.snapshot()
                    if not self._state_ready(
                        snapshot, stage=L43EffectStage.ENTRY_PLACEMENT
                    ):
                        return self._result(
                            L43EffectStage.ENTRY_PLACEMENT,
                            L43EffectOutcome.BLOCKED,
                            "L43_STATE_NOT_READY",
                            fresh,
                            None,
                            snapshot,
                        )
                    authorization = self._authorize(
                        _authorization_request(
                            L43EffectStage.ENTRY_PLACEMENT, fresh, snapshot
                        )
                    )
                    if authorization is None:
                        return self._result(
                            L43EffectStage.ENTRY_PLACEMENT,
                            L43EffectOutcome.BLOCKED,
                            "ENTRY_AUTHORIZATION_MISSING",
                            fresh,
                            None,
                            snapshot,
                        )
                    intent_id = session.reserve_entry(risk)
                    invoke = prepared.resolve_callable()
                    try:
                        permit = session.prepare_invocation(intent_id)
                    except Exception:
                        return self._result(
                            L43EffectStage.ENTRY_PLACEMENT,
                            L43EffectOutcome.BLOCKED,
                            "ENTRY_MAY_PERSIST_FAILED",
                            fresh,
                            authorization,
                            session.snapshot(),
                        )
                    if not _permit_matches(
                        permit,
                        kind=IntentKind.ENTRY,
                        dollars=risk,
                        quantity=None,
                        authority_sha256=None,
                    ):
                        completed_result = self._after_may_failure(
                            session,
                            intent_id,
                            L43EffectStage.ENTRY_PLACEMENT,
                            fresh,
                            authorization,
                            trigger=None,
                        )
                        return completed_result
                    try:
                        receipt = await invoke(permit)
                        if type(receipt) is not L43PlacementReceipt:
                            raise L43TransportError("L43_PLACEMENT_RESULT_UNKNOWN")
                        session.bind_provider_order(
                            intent_id, receipt.provider_order_id
                        )
                        facts = await self._reconcile_after_placement(
                            stage=L43EffectStage.ENTRY_PLACEMENT,
                            plan=fresh,
                            intent_id=intent_id,
                            receipt=receipt,
                            known_state=session.state,
                        )
                        if not self._valid_post_effect_facts(
                            facts,
                            plan=fresh,
                            state=session.state,
                            intent_id=intent_id,
                            provider_order_id=receipt.provider_order_id,
                            expected_stage=L43EffectStage.ENTRY_PLACEMENT,
                        ):
                            raise L43TransportError("L43_POST_EFFECT_FACTS_INVALID")
                        updated = session.reconcile(facts.snapshot)
                        entry = updated.entry
                        if (
                            entry is None
                            or updated.blocked_reason is not None
                            or not updated.reconciled
                        ):
                            raise L43TransportError("L43_RECONCILIATION_UNKNOWN")
                        if (
                            entry.status
                            in {
                                IntentStatus.MAY_HAVE_OCCURRED,
                                IntentStatus.UNKNOWN,
                            }
                            or not updated.reconciled
                        ):
                            raise L43TransportError("L43_RECONCILIATION_UNKNOWN")
                        outcome = (
                            L43EffectOutcome.ENTRY_RECONCILED
                            if entry.status
                            in {
                                IntentStatus.FILLED,
                                IntentStatus.CANCELED,
                                IntentStatus.REJECTED,
                            }
                            else L43EffectOutcome.ENTRY_PENDING
                        )
                        completed_result = self._result(
                            L43EffectStage.ENTRY_PLACEMENT,
                            outcome,
                            "ENTRY_FACTUALLY_RECONCILED",
                            fresh,
                            authorization,
                            session.snapshot(),
                            confirmed_filled_quantity=entry.cumulative_quantity,
                            supplemental_digest=facts.evidence_sha256,
                        )
                        return completed_result
                    except asyncio.CancelledError:
                        completed_result = self._after_may_failure(
                            session,
                            intent_id,
                            L43EffectStage.ENTRY_PLACEMENT,
                            fresh,
                            authorization,
                            trigger=None,
                        )
                        raise
                    except Exception:
                        completed_result = self._after_may_failure(
                            session,
                            intent_id,
                            L43EffectStage.ENTRY_PLACEMENT,
                            fresh,
                            authorization,
                            trigger=None,
                        )
                        return completed_result
        except Exception:
            if completed_result is not None:
                return completed_result
            return self._result(
                L43EffectStage.ENTRY_PLACEMENT,
                L43EffectOutcome.BLOCKED,
                "ENTRY_PREPARATION_OR_STATE_FAILED",
                plan,
                None,
                None,
            )

    async def review_sell(
        self, pre_effect: L43PreEffectResult, *, account_number: str
    ) -> L43EffectResult:
        """Persist review-start, call nonplacing review, then validate/record it."""

        if pre_effect.outcome is L43PreEffectOutcome.MANUAL_CLOSE_REQUIRED:
            return self.persist_observed_manual_close(pre_effect)
        plan = _ready_plan(
            pre_effect,
            outcome=L43PreEffectOutcome.READY_FOR_L43_EXACT_OWNED_REVIEW,
            kind=L43PlanKind.EXACT_OWNED_SELL_REVIEW,
        )
        if plan is None or plan.sell_proposal is None:
            return self._result(
                L43EffectStage.SELL_REVIEW,
                L43EffectOutcome.NO_ACTION_SIGNAL
                if pre_effect.outcome is L43PreEffectOutcome.NO_ACTION_SIGNAL
                else L43EffectOutcome.BLOCKED,
                "SELL_REVIEW_PLAN_UNAVAILABLE",
                pre_effect.plan,
                None,
                None,
            )
        if not _account_matches(plan, account_number):
            return self._result(
                L43EffectStage.SELL_REVIEW,
                L43EffectOutcome.BLOCKED,
                "ACCOUNT_FINGERPRINT_MISMATCH",
                plan,
                None,
                None,
            )
        proposal = plan.sell_proposal
        eligibility = evaluate_exact_owned_sell_proposal(proposal)
        if not eligibility.eligible_for_nonplacing_review:
            return self._result(
                L43EffectStage.SELL_REVIEW,
                L43EffectOutcome.BLOCKED,
                "SELL_PROPOSAL_INVALID",
                plan,
                None,
                None,
            )
        proposal_sha256 = eligibility.proposal_sha256
        arguments_sha256 = _sell_arguments_sha256(proposal.review_arguments)
        completed_result: L43EffectResult | None = None
        try:
            with self._session_factory() as session:
                fresh_result = self._fresh_result(session)
                fresh = self._matching_plan(
                    pre_effect,
                    fresh_result,
                    expected_kind=L43PlanKind.EXACT_OWNED_SELL_REVIEW,
                    requested_entry_risk=None,
                    snapshot=session.snapshot(),
                )
                if (
                    fresh is None
                    or fresh.sell_proposal is None
                    or fresh.sell_proposal != proposal
                    or not _account_matches(fresh, account_number)
                ):
                    return self._result(
                        L43EffectStage.SELL_REVIEW,
                        L43EffectOutcome.BLOCKED,
                        "SELL_REVIEW_REVALIDATION_CHANGED",
                        fresh_result.plan,
                        None,
                        session.snapshot(),
                    )
                snapshot = session.snapshot()
                if not self._state_ready(snapshot, stage=L43EffectStage.SELL_REVIEW):
                    return self._result(
                        L43EffectStage.SELL_REVIEW,
                        L43EffectOutcome.BLOCKED,
                        "L43_STATE_NOT_READY",
                        fresh,
                        None,
                        snapshot,
                    )
                authorization = self._authorize(
                    _authorization_request(
                        L43EffectStage.SELL_REVIEW,
                        fresh,
                        snapshot,
                        proposal_sha256=proposal_sha256,
                        arguments_sha256=arguments_sha256,
                    )
                )
                if authorization is None:
                    return self._result(
                        L43EffectStage.SELL_REVIEW,
                        L43EffectOutcome.BLOCKED,
                        "SELL_REVIEW_AUTHORIZATION_MISSING",
                        fresh,
                        None,
                        snapshot,
                    )
                session.begin_sell_review(
                    proposal_sha256=proposal_sha256,
                    arguments_sha256=arguments_sha256,
                )
                try:
                    raw_normalized = await self._review_caller(
                        account_number=account_number,
                        proposal=proposal,
                    )
                    normalized, fallback_trigger, reason = _review_facts(raw_normalized)
                    validation = validate_normalized_sell_review(proposal, normalized)
                    if (
                        validation.status
                        is SellReviewValidationStatus.ACCEPTED_FOR_PROSPECTIVE_CONTRACT
                    ):
                        assert normalized is not None
                        session.accept_sell_review(
                            proposal_sha256=proposal_sha256,
                            arguments_sha256=arguments_sha256,
                            review_evidence_sha256=normalized.evidence_sha256,
                        )
                        accepted_snapshot = session.snapshot()
                        accepted = L43AcceptedReviewReceipt(
                            authorization_sha256=authorization.authority_sha256,
                            review_plan_binding_sha256=fresh.binding_sha256,
                            proposal_sha256=proposal_sha256,
                            arguments_sha256=arguments_sha256,
                            review_evidence_sha256=normalized.evidence_sha256,
                            reviewed_arguments=proposal.review_arguments,
                            accepted_state_sequence=accepted_snapshot.last_sequence,
                            accepted_state_tail_sha256=accepted_snapshot.journal_sha256,
                        )
                        completed_result = self._result(
                            L43EffectStage.SELL_REVIEW,
                            L43EffectOutcome.REVIEW_ACCEPTED,
                            "SELL_REVIEW_ACCEPTED",
                            fresh,
                            authorization,
                            accepted_snapshot,
                            accepted_review=accepted,
                            supplemental_digest=normalized.evidence_sha256,
                        )
                        return completed_result
                    trigger = (
                        fallback_trigger
                        or validation.manual_close_trigger
                        or ManualCloseTrigger.SELL_REVIEW_MALFORMED
                    )
                    effect_digest = _effect_evidence_digest(
                        stage=L43EffectStage.SELL_REVIEW,
                        plan=fresh,
                        authorization=authorization,
                        reason=reason,
                        supplemental_digest=(
                            None if normalized is None else normalized.evidence_sha256
                        ),
                    )
                    session.require_manual_close(
                        trigger=trigger,
                        effect_evidence_sha256=effect_digest,
                    )
                    completed_result = self._result(
                        L43EffectStage.SELL_REVIEW,
                        L43EffectOutcome.MANUAL_CLOSE_REQUIRED,
                        trigger.value,
                        fresh,
                        authorization,
                        session.snapshot(),
                        supplemental_digest=effect_digest,
                    )
                    return completed_result
                except asyncio.CancelledError:
                    trigger = ManualCloseTrigger.SELL_REVIEW_UNKNOWN
                    effect_digest = _effect_evidence_digest(
                        stage=L43EffectStage.SELL_REVIEW,
                        plan=fresh,
                        authorization=authorization,
                        reason="SELL_REVIEW_CANCELLED",
                        supplemental_digest=None,
                    )
                    try:
                        session.require_manual_close(
                            trigger=trigger,
                            effect_evidence_sha256=effect_digest,
                        )
                    except Exception:
                        pass
                    raise
                except Exception:
                    trigger = ManualCloseTrigger.SELL_REVIEW_UNKNOWN
                    effect_digest = _effect_evidence_digest(
                        stage=L43EffectStage.SELL_REVIEW,
                        plan=fresh,
                        authorization=authorization,
                        reason="SELL_REVIEW_RESULT_UNKNOWN",
                        supplemental_digest=None,
                    )
                    try:
                        session.require_manual_close(
                            trigger=trigger,
                            effect_evidence_sha256=effect_digest,
                        )
                    except Exception:
                        pass
                    completed_result = self._result(
                        L43EffectStage.SELL_REVIEW,
                        L43EffectOutcome.MANUAL_CLOSE_REQUIRED,
                        "SELL_REVIEW_RESULT_UNKNOWN",
                        fresh,
                        authorization,
                        _snapshot_best_effort(session),
                        supplemental_digest=effect_digest,
                    )
                    return completed_result
        except Exception:
            if completed_result is not None:
                return completed_result
            return self._result(
                L43EffectStage.SELL_REVIEW,
                L43EffectOutcome.BLOCKED,
                "SELL_REVIEW_PREPARATION_OR_STATE_FAILED",
                plan,
                None,
                None,
            )

    def persist_observed_manual_close(
        self, candidate: L43PreEffectResult
    ) -> L43EffectResult:
        """Persist only a fresh typed unsupported-residual observation."""

        if (
            type(candidate) is not L43PreEffectResult
            or candidate.outcome is not L43PreEffectOutcome.MANUAL_CLOSE_REQUIRED
            or candidate.manual_close_trigger is None
            or candidate.blockers != (L43PreEffectBlocker.EXACT_RESIDUAL_UNSUPPORTED,)
            or candidate.manual_close_residual_quantity is None
            or candidate.manual_close_basis_sha256 is None
        ):
            return self._result(
                L43EffectStage.SELL_REVIEW,
                L43EffectOutcome.BLOCKED,
                "MANUAL_CLOSE_CANDIDATE_INVALID",
                None,
                None,
                None,
            )
        try:
            with self._session_factory() as session:
                snapshot = session.snapshot()
                fresh = self._fresh_result(session)
                if (
                    fresh.outcome is not L43PreEffectOutcome.MANUAL_CLOSE_REQUIRED
                    or fresh.manual_close_trigger != candidate.manual_close_trigger
                    or fresh.manual_close_residual_quantity
                    != candidate.manual_close_residual_quantity
                    or fresh.manual_close_state_sequence != snapshot.last_sequence
                    or fresh.manual_close_state_tail_sha256 != snapshot.journal_sha256
                    or fresh.manual_close_state_sequence
                    != candidate.manual_close_state_sequence
                    or fresh.manual_close_state_tail_sha256
                    != candidate.manual_close_state_tail_sha256
                    or fresh.manual_close_basis_sha256
                    != candidate.manual_close_basis_sha256
                    or snapshot.state.owned_quantity
                    != candidate.manual_close_residual_quantity
                    or snapshot.manual_close_required
                    or snapshot.manual_follow_up_required
                ):
                    return self._result(
                        L43EffectStage.SELL_REVIEW,
                        L43EffectOutcome.BLOCKED,
                        "MANUAL_CLOSE_REVALIDATION_CHANGED",
                        None,
                        None,
                        snapshot,
                    )
                session.require_manual_close(
                    trigger=candidate.manual_close_trigger,
                    effect_evidence_sha256=candidate.manual_close_basis_sha256,
                )
                persisted = session.snapshot()
                manual = persisted.state.manual_close
                if (
                    manual is None
                    or manual.trigger is not candidate.manual_close_trigger
                    or manual.exact_residual_quantity
                    != candidate.manual_close_residual_quantity
                ):
                    return self._result(
                        L43EffectStage.SELL_REVIEW,
                        L43EffectOutcome.BLOCKED,
                        "MANUAL_CLOSE_PERSISTENCE_UNKNOWN",
                        None,
                        None,
                        persisted,
                    )
                return self._result(
                    L43EffectStage.SELL_REVIEW,
                    L43EffectOutcome.MANUAL_CLOSE_REQUIRED,
                    candidate.manual_close_trigger.value,
                    None,
                    None,
                    persisted,
                    supplemental_digest=candidate.manual_close_basis_sha256,
                )
        except Exception:
            return self._result(
                L43EffectStage.SELL_REVIEW,
                L43EffectOutcome.BLOCKED,
                "MANUAL_CLOSE_PERSISTENCE_UNKNOWN",
                None,
                None,
                None,
                supplemental_digest=candidate.evidence_sha256,
            )

    async def place_sell(
        self,
        pre_effect: L43PreEffectResult,
        accepted_review: L43AcceptedReviewReceipt,
        *,
        account_number: str,
    ) -> L43EffectResult:
        """Require a distinct exact-plan grant and consume the sole exit attempt."""

        plan = _ready_plan(
            pre_effect,
            outcome=L43PreEffectOutcome.READY_FOR_L43_EXACT_OWNED_REVIEW,
            kind=L43PlanKind.EXACT_OWNED_SELL_REVIEW,
        )
        if (
            plan is None
            or plan.sell_proposal is None
            or type(accepted_review) is not L43AcceptedReviewReceipt
        ):
            return self._result(
                L43EffectStage.SELL_PLACEMENT,
                L43EffectOutcome.BLOCKED,
                "ACCEPTED_REVIEW_RECEIPT_REQUIRED",
                pre_effect.plan,
                None,
                None,
            )
        if not _account_matches(plan, account_number):
            return self._result(
                L43EffectStage.SELL_PLACEMENT,
                L43EffectOutcome.BLOCKED,
                "ACCOUNT_FINGERPRINT_MISMATCH",
                plan,
                None,
                None,
            )
        proposal = plan.sell_proposal
        arguments = proposal.placement_arguments
        completed_result: L43EffectResult | None = None
        try:
            async with self._transport.prepare_sell_order(
                account_number=account_number,
                arguments=accepted_review.reviewed_arguments,
            ) as prepared:
                with self._session_factory() as session:
                    fresh_result = self._fresh_result(session)
                    fresh = self._matching_plan(
                        pre_effect,
                        fresh_result,
                        expected_kind=L43PlanKind.EXACT_OWNED_SELL_REVIEW,
                        requested_entry_risk=None,
                        snapshot=session.snapshot(),
                    )
                    if (
                        fresh is None
                        or fresh.sell_proposal is None
                        or not _receipt_matches_plan(accepted_review, fresh)
                        or not _account_matches(fresh, account_number)
                    ):
                        return self._result(
                            L43EffectStage.SELL_PLACEMENT,
                            L43EffectOutcome.BLOCKED,
                            "SELL_PLACEMENT_REVALIDATION_CHANGED",
                            fresh_result.plan,
                            None,
                            session.snapshot(),
                        )
                    snapshot = session.snapshot()
                    if not self._state_ready(
                        snapshot, stage=L43EffectStage.SELL_PLACEMENT
                    ):
                        return self._result(
                            L43EffectStage.SELL_PLACEMENT,
                            L43EffectOutcome.BLOCKED,
                            "L43_STATE_NOT_READY",
                            fresh,
                            None,
                            snapshot,
                        )
                    review_state = snapshot.state.sell_review
                    if (
                        review_state is None
                        or review_state.status.value != "ACCEPTED"
                        or review_state.proposal_sha256
                        != accepted_review.proposal_sha256
                        or review_state.arguments_sha256
                        != accepted_review.arguments_sha256
                        or review_state.review_evidence_sha256
                        != accepted_review.review_evidence_sha256
                        or snapshot.last_sequence
                        != accepted_review.accepted_state_sequence
                        or snapshot.journal_sha256
                        != accepted_review.accepted_state_tail_sha256
                        or arguments != accepted_review.reviewed_arguments
                        or arguments != proposal.review_arguments
                    ):
                        return self._result(
                            L43EffectStage.SELL_PLACEMENT,
                            L43EffectOutcome.BLOCKED,
                            "DURABLE_REVIEW_BINDING_MISMATCH",
                            fresh,
                            None,
                            snapshot,
                        )
                    proposal_sha256 = proposal.proposal_sha256()
                    arguments_sha256 = _sell_arguments_sha256(arguments)
                    authorization = self._authorize(
                        _authorization_request(
                            L43EffectStage.SELL_PLACEMENT,
                            fresh,
                            snapshot,
                            proposal_sha256=proposal_sha256,
                            arguments_sha256=arguments_sha256,
                        )
                    )
                    if authorization is None:
                        return self._result(
                            L43EffectStage.SELL_PLACEMENT,
                            L43EffectOutcome.BLOCKED,
                            "SELL_PLACEMENT_AUTHORIZATION_MISSING",
                            fresh,
                            None,
                            snapshot,
                        )
                    intent_id = session.reserve_exit(
                        arguments.quantity,
                        authority_sha256=authorization.authority_sha256,
                    )
                    invoke = prepared.resolve_callable(
                        authority_sha256=authorization.authority_sha256
                    )
                    try:
                        permit = session.prepare_invocation(intent_id)
                    except Exception:
                        return self._result(
                            L43EffectStage.SELL_PLACEMENT,
                            L43EffectOutcome.BLOCKED,
                            "SELL_MAY_PERSIST_FAILED",
                            fresh,
                            authorization,
                            session.snapshot(),
                        )
                    if not _permit_matches(
                        permit,
                        kind=IntentKind.EXIT,
                        dollars=None,
                        quantity=arguments.quantity,
                        authority_sha256=authorization.authority_sha256,
                    ):
                        completed_result = self._after_may_failure(
                            session,
                            intent_id,
                            L43EffectStage.SELL_PLACEMENT,
                            fresh,
                            authorization,
                            trigger=ManualCloseTrigger.SELL_UNKNOWN,
                        )
                        return completed_result
                    try:
                        receipt = await invoke(permit)
                        if type(receipt) is not L43PlacementReceipt:
                            raise L43TransportError("L43_PLACEMENT_RESULT_UNKNOWN")
                        session.bind_provider_order(
                            intent_id, receipt.provider_order_id
                        )
                        facts = await self._reconcile_after_placement(
                            stage=L43EffectStage.SELL_PLACEMENT,
                            plan=fresh,
                            intent_id=intent_id,
                            receipt=receipt,
                            known_state=session.state,
                        )
                        if not self._valid_post_effect_facts(
                            facts,
                            plan=fresh,
                            state=session.state,
                            intent_id=intent_id,
                            provider_order_id=receipt.provider_order_id,
                            expected_stage=L43EffectStage.SELL_PLACEMENT,
                        ):
                            raise L43TransportError("L43_POST_EFFECT_FACTS_INVALID")
                        updated = session.reconcile(facts.snapshot)
                        exit_order = updated.exit
                        if exit_order is None:
                            raise L43TransportError("L43_RECONCILIATION_UNKNOWN")
                        if updated.blocked_reason is not None:
                            if (
                                exit_order.status
                                in {
                                    IntentStatus.REJECTED,
                                    IntentStatus.CANCELED,
                                    IntentStatus.PARTIAL,
                                    IntentStatus.MAY_HAVE_OCCURRED,
                                    IntentStatus.UNKNOWN,
                                }
                                and updated.owned_quantity > _ZERO
                            ):
                                trigger = {
                                    IntentStatus.REJECTED: (
                                        ManualCloseTrigger.SELL_REJECTED
                                    ),
                                    IntentStatus.CANCELED: (
                                        ManualCloseTrigger.SELL_CANCELED
                                    ),
                                    IntentStatus.PARTIAL: (
                                        ManualCloseTrigger.SELL_PARTIAL
                                    ),
                                }.get(
                                    exit_order.status, ManualCloseTrigger.SELL_UNKNOWN
                                )
                                completed_result = self._manual_close_after_sell(
                                    session,
                                    fresh,
                                    authorization,
                                    trigger,
                                    "SELL_RECONCILIATION_BLOCKED",
                                    facts.evidence_sha256,
                                )
                                return completed_result
                            completed_result = self._result(
                                L43EffectStage.SELL_PLACEMENT,
                                L43EffectOutcome.BLOCKED,
                                "SELL_POSITION_OR_ORDER_MISMATCH",
                                fresh,
                                authorization,
                                session.snapshot(),
                                supplemental_digest=facts.evidence_sha256,
                            )
                            return completed_result
                        if exit_order.status is IntentStatus.FILLED:
                            if (
                                not updated.reconciled
                                or updated.owned_quantity != _ZERO
                            ):
                                completed_result = self._result(
                                    L43EffectStage.SELL_PLACEMENT,
                                    L43EffectOutcome.BLOCKED,
                                    "SELL_RESIDUAL_AFTER_FILL",
                                    fresh,
                                    authorization,
                                    session.snapshot(),
                                    supplemental_digest=facts.evidence_sha256,
                                )
                                return completed_result
                            completed_result = self._result(
                                L43EffectStage.SELL_PLACEMENT,
                                L43EffectOutcome.SELL_RECONCILED,
                                "SELL_FACTUALLY_RECONCILED",
                                fresh,
                                authorization,
                                session.snapshot(),
                                confirmed_filled_quantity=exit_order.cumulative_quantity,
                                supplemental_digest=facts.evidence_sha256,
                            )
                            return completed_result
                        trigger = {
                            IntentStatus.REJECTED: ManualCloseTrigger.SELL_REJECTED,
                            IntentStatus.CANCELED: ManualCloseTrigger.SELL_CANCELED,
                            IntentStatus.PARTIAL: ManualCloseTrigger.SELL_PARTIAL,
                        }.get(exit_order.status)
                        if trigger is None:
                            try:
                                session.mark_unknown(intent_id)
                            except Exception:
                                pass
                            trigger = ManualCloseTrigger.SELL_UNKNOWN
                        completed_result = self._manual_close_after_sell(
                            session,
                            fresh,
                            authorization,
                            trigger,
                            "SELL_TERMINAL_REQUIRES_MANUAL_CLOSE",
                            facts.evidence_sha256,
                        )
                        return completed_result
                    except asyncio.CancelledError:
                        completed_result = self._after_may_failure(
                            session,
                            intent_id,
                            L43EffectStage.SELL_PLACEMENT,
                            fresh,
                            authorization,
                            trigger=ManualCloseTrigger.SELL_UNKNOWN,
                        )
                        raise
                    except Exception:
                        completed_result = self._after_may_failure(
                            session,
                            intent_id,
                            L43EffectStage.SELL_PLACEMENT,
                            fresh,
                            authorization,
                            trigger=ManualCloseTrigger.SELL_UNKNOWN,
                        )
                        return completed_result
        except Exception:
            if completed_result is not None:
                return completed_result
            return self._result(
                L43EffectStage.SELL_PLACEMENT,
                L43EffectOutcome.BLOCKED,
                "SELL_PREPARATION_OR_STATE_FAILED",
                plan,
                None,
                None,
            )

    def _fresh_result(
        self,
        session: L43StateSession,
        *,
        requested_entry_risk: Decimal | None = None,
    ) -> L43PreEffectResult:
        result = self._reobserver(session, requested_entry_risk=requested_entry_risk)
        if type(result) is not L43PreEffectResult:
            raise TypeError("locked reobserver returned an unsupported result")
        return result

    def _matching_plan(
        self,
        submitted: L43PreEffectResult,
        fresh_result: L43PreEffectResult,
        *,
        expected_kind: L43PlanKind,
        requested_entry_risk: Decimal | None,
        snapshot: object,
    ) -> L43PreEffectPlan | None:
        submitted_plan = _ready_plan(
            submitted,
            outcome=(
                L43PreEffectOutcome.READY_FOR_L43_ENTRY_EFFECT_REVIEW
                if expected_kind is L43PlanKind.ENTRY
                else L43PreEffectOutcome.READY_FOR_L43_EXACT_OWNED_REVIEW
            ),
            kind=expected_kind,
        )
        fresh = _ready_plan(
            fresh_result,
            outcome=(
                L43PreEffectOutcome.READY_FOR_L43_ENTRY_EFFECT_REVIEW
                if expected_kind is L43PlanKind.ENTRY
                else L43PreEffectOutcome.READY_FOR_L43_EXACT_OWNED_REVIEW
            ),
            kind=expected_kind,
        )
        if submitted_plan is None or fresh is None:
            return None
        try:
            _check_plan_state_binding(fresh, snapshot)
        except (TypeError, ValueError):
            return None
        if submitted_plan.binding_sha256 != fresh.binding_sha256:
            return None
        if expected_kind is L43PlanKind.ENTRY:
            if fresh.requested_entry_risk != requested_entry_risk:
                return None
        elif fresh.sell_proposal is None or submitted_plan.sell_proposal != (
            fresh.sell_proposal
        ):
            return None
        return fresh

    def _state_ready(self, snapshot: object, *, stage: L43EffectStage) -> bool:
        try:
            state = snapshot.state
            if (
                snapshot.manual_close_required
                or snapshot.manual_follow_up_required
                or snapshot.sell_review_pending
                or not state.reconciled
                or state.blocked_reason is not None
                or state.manual_close_required
                or state.exit is not None
            ):
                return False
            entry = state.entry
            terminal = entry is not None and entry.status in {
                IntentStatus.FILLED,
                IntentStatus.CANCELED,
                IntentStatus.REJECTED,
            }
            if stage is L43EffectStage.ENTRY_PLACEMENT:
                return entry is None and state.owned_quantity == _ZERO
            if not terminal or state.owned_quantity <= _ZERO:
                return False
            if stage is L43EffectStage.SELL_REVIEW:
                return state.sell_review is None
            return (
                state.sell_review is not None
                and state.sell_review.status.value == "ACCEPTED"
            )
        except Exception:
            return False

    def _authorize(
        self, request: L43AuthorizationRequest
    ) -> L43StageAuthorization | None:
        try:
            grant = self._authorizer.authorize(request)
        except Exception:
            return None
        if type(grant) is not L43StageAuthorization or grant.request != request:
            return None
        return grant

    def _persist_clean_reconciliation(
        self, session: L43StateSession, plan: L43PreEffectPlan
    ) -> bool:
        try:
            if plan.reconciliation_snapshot.identity != session.state.identity:
                return False
            state = session.reconcile(plan.reconciliation_snapshot)
            return (
                state.reconciled
                and state.blocked_reason is None
                and not state.manual_close_required
                and state.owned_quantity == _ZERO
            )
        except Exception:
            return False

    async def _reconcile_after_placement(
        self,
        *,
        stage: L43EffectStage,
        plan: L43PreEffectPlan,
        intent_id: str,
        receipt: L43PlacementReceipt,
        known_state: object,
    ) -> L43PostEffectFacts:
        facts = await self._reconciler.reconcile(
            stage=stage,
            plan=plan,
            intent_id=intent_id,
            provider_order_id=receipt.provider_order_id,
            known_state=known_state,
        )
        if type(facts) is not L43PostEffectFacts:
            raise TypeError("post-effect reader returned unsupported facts")
        return facts

    def _valid_post_effect_facts(
        self,
        facts: L43PostEffectFacts,
        *,
        plan: L43PreEffectPlan,
        state: object,
        intent_id: str,
        provider_order_id: str,
        expected_stage: L43EffectStage,
    ) -> bool:
        if (
            facts.account_fingerprint != plan.account_fingerprint
            or facts.snapshot.identity != state.identity
            or facts.snapshot.identity != plan.reconciliation_snapshot.identity
            or not facts.all_relevant_orders_proven
        ):
            return False
        expected_orders = {
            order.intent_id: order.provider_order_id
            for order in (state.entry, state.exit)
            if order is not None and order.provider_order_id is not None
        }
        if expected_orders.get(intent_id) != provider_order_id:
            return False
        seen: dict[str, str] = {}
        for observation in facts.snapshot.orders:
            if observation.local_intent_id in seen:
                return False
            seen[observation.local_intent_id] = observation.provider_order_id
        if seen != expected_orders:
            return False
        placed = next(
            (
                observation
                for observation in facts.snapshot.orders
                if observation.local_intent_id == intent_id
            ),
            None,
        )
        if placed is None or placed.provider_order_id != provider_order_id:
            return False
        if expected_stage is L43EffectStage.ENTRY_PLACEMENT:
            return state.entry is not None and state.entry.kind is IntentKind.ENTRY
        return state.exit is not None and state.exit.kind is IntentKind.EXIT

    def _after_may_failure(
        self,
        session: L43StateSession,
        intent_id: str,
        stage: L43EffectStage,
        plan: L43PreEffectPlan,
        authorization: L43StageAuthorization,
        *,
        trigger: ManualCloseTrigger | None,
    ) -> L43EffectResult:
        try:
            session.mark_unknown(intent_id)
        except Exception:
            pass
        if stage is L43EffectStage.SELL_PLACEMENT:
            current = _snapshot_best_effort(session)
            if current is not None and current.state.owned_quantity <= _ZERO:
                return self._result(
                    stage,
                    L43EffectOutcome.BLOCKED,
                    "SELL_OWNED_RESIDUAL_UNAVAILABLE",
                    plan,
                    authorization,
                    current,
                )
            return self._manual_close_after_sell(
                session,
                plan,
                authorization,
                trigger or ManualCloseTrigger.SELL_UNKNOWN,
                "SELL_EFFECT_UNKNOWN",
                None,
            )
        return self._result(
            stage,
            L43EffectOutcome.EFFECT_UNKNOWN,
            "ENTRY_EFFECT_UNKNOWN",
            plan,
            authorization,
            _snapshot_best_effort(session),
        )

    def _manual_close_after_sell(
        self,
        session: L43StateSession,
        plan: L43PreEffectPlan,
        authorization: L43StageAuthorization,
        trigger: ManualCloseTrigger,
        reason: str,
        supplemental_digest: str | None,
    ) -> L43EffectResult:
        current = _snapshot_best_effort(session)
        if current is not None and current.state.owned_quantity <= _ZERO:
            return self._result(
                L43EffectStage.SELL_PLACEMENT,
                L43EffectOutcome.BLOCKED,
                "SELL_OWNED_RESIDUAL_UNAVAILABLE",
                plan,
                authorization,
                current,
            )
        digest = _effect_evidence_digest(
            stage=L43EffectStage.SELL_PLACEMENT,
            plan=plan,
            authorization=authorization,
            reason=reason,
            supplemental_digest=supplemental_digest,
        )
        try:
            session.require_manual_close(
                trigger=trigger,
                effect_evidence_sha256=digest,
            )
        except Exception:
            pass
        return self._result(
            L43EffectStage.SELL_PLACEMENT,
            L43EffectOutcome.MANUAL_CLOSE_REQUIRED,
            reason,
            plan,
            authorization,
            _snapshot_best_effort(session),
            supplemental_digest=digest,
        )

    def _result(
        self,
        stage: L43EffectStage,
        outcome: L43EffectOutcome,
        reason: str,
        plan: L43PreEffectPlan | None,
        authorization: L43StageAuthorization | None,
        snapshot: object | None,
        *,
        confirmed_filled_quantity: Decimal | None = None,
        accepted_review: L43AcceptedReviewReceipt | None = None,
        supplemental_digest: str | None = None,
    ) -> L43EffectResult:
        safe_reason = reason if _SAFE_CODE.fullmatch(reason) else "L43_EFFECT_FAILED"
        tail = None if snapshot is None else snapshot.journal_sha256
        sequence = None if snapshot is None else snapshot.last_sequence
        evidence = _digest(
            (
                "ARCH147_L43_EFFECT_RESULT_V1",
                stage.value,
                outcome.value,
                safe_reason,
                None if plan is None else plan.binding_sha256,
                None if authorization is None else authorization.authority_sha256,
                sequence,
                tail,
                None
                if confirmed_filled_quantity is None
                else _decimal_text(confirmed_filled_quantity),
                supplemental_digest,
            )
        )
        return L43EffectResult(
            stage=stage,
            outcome=outcome,
            reason_code=safe_reason,
            evidence_sha256=evidence,
            plan_binding_sha256=None if plan is None else plan.binding_sha256,
            authorization_sha256=(
                None if authorization is None else authorization.authority_sha256
            ),
            state_last_sequence=sequence,
            state_tail_sha256=tail,
            confirmed_filled_quantity=confirmed_filled_quantity,
            accepted_review=accepted_review,
        )


def _ready_plan(
    result: L43PreEffectResult,
    *,
    outcome: L43PreEffectOutcome,
    kind: L43PlanKind,
) -> L43PreEffectPlan | None:
    if type(result) is not L43PreEffectResult or result.outcome is not outcome:
        return None
    plan = result.plan
    if type(plan) is not L43PreEffectPlan or plan.kind is not kind:
        return None
    return plan


def _check_plan_state_binding(plan: L43PreEffectPlan, snapshot: object) -> None:
    state = snapshot.state
    if (
        plan.state_last_sequence != snapshot.last_sequence
        or plan.state_tail_sha256 != snapshot.journal_sha256
        or plan.state_journal_sha256 != snapshot.journal_sha256
        or plan.reconciliation_snapshot.identity != state.identity
        or plan.continuity.origin.runtime_identity != state.identity
        or plan.current_source != plan.continuity.current
        or not plan.provenance.matches(state.identity)
        or plan.account_fingerprint != state.identity.account_fingerprint
    ):
        raise ValueError("fresh plan does not bind current L43 state")


def _same_plan_facts_except_tail(old: L43PreEffectPlan, new: L43PreEffectPlan) -> bool:
    return (
        old.kind is new.kind
        and old.current_source == new.current_source
        and old.provenance == new.provenance
        and old.continuity == new.continuity
        and old.reconciliation_snapshot == new.reconciliation_snapshot
        and old.account_fingerprint == new.account_fingerprint
        and old.positions_digest == new.positions_digest
        and old.relevant_orders_digest == new.relevant_orders_digest
        and old.order_scope_digest == new.order_scope_digest
        and old.session == new.session
        and old.signal == new.signal
        and old.requested_entry_risk == new.requested_entry_risk
        and old.sell_proposal == new.sell_proposal
        and old.recovery.reconciled == new.recovery.reconciled
        and old.recovery.unresolved_effects == new.recovery.unresolved_effects
        and old.recovery.terminal_entry == new.recovery.terminal_entry
        and old.recovery.exact_owned_remainder == new.recovery.exact_owned_remainder
    )


def _authorization_request(
    stage: L43EffectStage,
    plan: L43PreEffectPlan,
    snapshot: object,
    *,
    proposal_sha256: str | None = None,
    arguments_sha256: str | None = None,
) -> L43AuthorizationRequest:
    _check_plan_state_binding(plan, snapshot)
    return L43AuthorizationRequest(
        stage=stage,
        plan_binding_sha256=plan.binding_sha256,
        state_last_sequence=snapshot.last_sequence,
        state_tail_sha256=snapshot.journal_sha256,
        source_head=plan.current_source.source_head,
        source_tree=plan.current_source.source_tree,
        config_digest=plan.provenance.config_digest,
        binding_digest=plan.provenance.binding_digest,
        account_fingerprint=plan.account_fingerprint,
        target_session=plan.session.target_session,
        signal_inputs_digest=plan.signal.inputs_digest,
        proposal_sha256=proposal_sha256,
        arguments_sha256=arguments_sha256,
    )


def _permit_matches(
    permit: PreparedInvocation,
    *,
    kind: IntentKind,
    dollars: Decimal | None,
    quantity: Decimal | None,
    authority_sha256: str | None,
) -> bool:
    return (
        type(permit) is PreparedInvocation
        and permit.kind is kind
        and permit.requested_dollars == dollars
        and permit.requested_quantity == quantity
        and permit.authority_sha256 == authority_sha256
    )


def _review_facts(
    value: object,
) -> tuple[NormalizedSellReview | None, ManualCloseTrigger | None, str]:
    if type(value) is NormalizedSellReview:
        return value, None, "NORMALIZED_REVIEW_SEAM"
    if type(value) is L43ReviewNormalization:
        return value.review, value.manual_close_trigger, value.reason_code
    return None, ManualCloseTrigger.SELL_REVIEW_MALFORMED, "REVIEW_RESULT_UNSUPPORTED"


def _receipt_matches_plan(
    receipt: L43AcceptedReviewReceipt, plan: L43PreEffectPlan
) -> bool:
    proposal = plan.sell_proposal
    return (
        proposal is not None
        and proposal.proposal_sha256() == receipt.proposal_sha256
        and proposal.review_arguments == receipt.reviewed_arguments
        and proposal.placement_arguments == receipt.reviewed_arguments
        and _sell_arguments_sha256(proposal.review_arguments)
        == receipt.arguments_sha256
    )


def _sell_arguments_sha256(arguments: SellOrderArguments) -> str:
    context = arguments.context
    return _digest(
        (
            "ARCH147_L43_SELL_ARGUMENTS_V1",
            arguments.side.value,
            arguments.symbol,
            arguments.order_type.value,
            arguments.session.value,
            arguments.time_in_force.value,
            _decimal_text(arguments.quantity),
            None
            if arguments.dollar_amount is None
            else _decimal_text(arguments.dollar_amount),
            context.identity.source_head,
            context.identity.source_tree,
            context.identity.config_digest,
            context.identity.account_fingerprint,
            context.identity.target_session,
            context.binding_digest,
            context.lifecycle_id,
            context.entry_local_intent_id,
            context.entry_provider_order_id,
            _decimal_text(context.exact_owned_remainder),
            _decimal_text(context.broker_position_quantity),
            _decimal_text(context.broker_sellable_quantity),
            context.terminal_entry_outcome.value,
            context.reserved_usd_cents,
            _decimal_text(context.confirmed_entry_filled_quantity),
            _decimal_text(context.confirmed_entry_filled_notional),
        )
    )


def _effect_evidence_digest(
    *,
    stage: L43EffectStage,
    plan: L43PreEffectPlan,
    authorization: L43StageAuthorization,
    reason: str,
    supplemental_digest: str | None,
) -> str:
    if not _SAFE_CODE.fullmatch(reason):
        reason = "L43_EFFECT_FAILED"
    if supplemental_digest is not None:
        _require_sha256(supplemental_digest, "supplemental effect evidence")
    return _digest(
        (
            "ARCH147_L43_DURABLE_EFFECT_EVIDENCE_V1",
            stage.value,
            plan.binding_sha256,
            authorization.authority_sha256,
            reason,
            supplemental_digest,
        )
    )


def _snapshot_best_effort(session: L43StateSession) -> object | None:
    try:
        return session.snapshot()
    except Exception:
        return None


def _require_account_number(value: object) -> None:
    if type(value) is not str or _ACCOUNT_NUMBER.fullmatch(value) is None:
        raise ValueError("account number is outside the bounded private request")


def _account_matches(plan: L43PreEffectPlan, value: object) -> bool:
    try:
        _require_account_number(value)
    except (TypeError, ValueError):
        return False
    return hashlib.sha256(value.encode("utf-8")).hexdigest() == (
        plan.account_fingerprint
    )


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be lowercase SHA-256")


def _decimal_text(value: Decimal) -> str:
    if type(value) is not Decimal or not value.is_finite():
        raise TypeError("canonical value must be a finite Decimal")
    if value == 0:
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _digest(material: tuple[object, ...]) -> str:
    document = json.dumps(
        material,
        sort_keys=False,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(document).hexdigest()


__all__ = [
    "L43AcceptedReviewReceipt",
    "L43AuthorizationRequest",
    "L43EffectOperator",
    "L43EffectOutcome",
    "L43EffectResult",
    "L43EffectStage",
    "L43ExactPlanAuthorizer",
    "L43PostEffectFacts",
    "L43PostEffectReconciler",
    "L43StageAuthorization",
]
