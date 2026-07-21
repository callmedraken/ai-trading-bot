from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from trading_bot.domain import OrderSide, Symbol, TradeProposal
from trading_bot.portfolio import (
    AllocationSource,
    MetadataEntry,
    PortfolioPositionState,
    PortfolioState,
    TargetAllocation,
    TargetPortfolio,
)
from trading_bot.rebalancing import (
    InconsistentRebalanceProposalResultError,
    InvalidRebalanceProposalRequestError,
    RebalanceAssumptions,
    RebalancePlan,
    RebalancePlanner,
    RebalancePlanNotEligibleError,
    RebalancePlanRequest,
    RebalanceProposalCreationError,
    RebalanceProposalDiagnostic,
    RebalanceProposalDiagnosticCode,
    RebalanceProposalFactory,
    RebalanceProposalPolicy,
    RebalanceProposalRequest,
    RebalanceProposalResult,
    RebalanceProposalStatus,
    RebalanceStatus,
)

NOW = datetime(2026, 7, 21, 20, tzinfo=UTC)
SPY = Symbol("SPY")
QQQ = Symbol("QQQ")
PROPOSAL_REQUEST_ID = UUID(int=100)


def make_plan(
    *,
    weights: tuple[str, str] = ("0.2", "0.2"),
    cash_weight: str = "0.6",
    assumptions: RebalanceAssumptions | None = None,
) -> RebalancePlan:
    state = PortfolioState(
        NOW,
        (
            PortfolioPositionState(SPY, Decimal("25"), Decimal("8"), Decimal("10")),
            PortfolioPositionState(QQQ, Decimal("0"), Decimal("0"), Decimal("10")),
        ),
        Decimal("750"),
        Decimal("1000"),
    )
    target = TargetPortfolio(
        UUID(int=2),
        NOW,
        (
            TargetAllocation(SPY, Decimal(weights[0])),
            TargetAllocation(QQQ, Decimal(weights[1])),
        ),
        Decimal(cash_weight),
        AllocationSource.MANUAL,
    )
    request = RebalancePlanRequest(
        UUID(int=1), state, target, assumptions or RebalanceAssumptions()
    )
    return RebalancePlanner().plan(request)


def proposal_request(
    plan: RebalancePlan | None = None,
    *,
    policy: RebalanceProposalPolicy | None = None,
    confidence: Decimal | None = None,
    request_id: UUID = PROPOSAL_REQUEST_ID,
    metadata: tuple[MetadataEntry, ...] = (),
) -> RebalanceProposalRequest:
    return RebalanceProposalRequest(
        request_id,
        plan or make_plan(),
        NOW,
        policy or RebalanceProposalPolicy(),
        confidence,
        metadata,
    )


def corrupt(plan: RebalancePlan, **changes: object) -> RebalancePlan:
    item = object.__new__(RebalancePlan)
    for field in fields(RebalancePlan):
        object.__setattr__(
            item, field.name, changes.get(field.name, getattr(plan, field.name))
        )
    return item


def corrupt_record(item, **changes: object):  # noqa: ANN001, ANN202
    changed = object.__new__(type(item))
    for field in fields(type(item)):
        object.__setattr__(
            changed, field.name, changes.get(field.name, getattr(item, field.name))
        )
    return changed


def test_complete_plan_maps_sells_then_buys_exactly() -> None:
    plan = make_plan()
    result = RebalanceProposalFactory().create(
        proposal_request(plan, confidence=Decimal("0.75"))
    )
    assert result.status is RebalanceProposalStatus.CREATED
    assert tuple(item.side for item in result.proposals) == (
        OrderSide.SELL,
        OrderSide.BUY,
    )
    assert tuple(item.symbol for item in result.proposals) == (SPY, QQQ)
    assert tuple(item.desired_quantity for item in result.proposals) == tuple(
        item.planned_quantity for item in plan.trades
    )
    assert all(item.created_at == NOW for item in result.proposals)
    assert all(item.confidence == Decimal("0.75") for item in result.proposals)
    assert result.diagnostics == ()


def test_reason_is_stable_and_uses_canonical_decimal() -> None:
    result = RebalanceProposalFactory().create(proposal_request())
    assert result.proposals[0].reason == (
        f"Rebalance plan {result.request.plan.plan_id}: SELL SPY "
        "toward target weight 0.2"
    )


def test_policy_request_and_result_are_frozen() -> None:
    request = proposal_request()
    result = RebalanceProposalFactory().create(request)
    with pytest.raises(FrozenInstanceError):
        request.confidence = Decimal("1")  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.status = RebalanceProposalStatus.NO_ACTION  # type: ignore[misc]
    with pytest.raises(InvalidRebalanceProposalRequestError, match="bool"):
        RebalanceProposalPolicy(1)  # type: ignore[arg-type]


def test_request_requires_uuid_plan_and_policy_types() -> None:
    plan = make_plan()
    with pytest.raises(InvalidRebalanceProposalRequestError, match="request_id"):
        RebalanceProposalRequest("bad", plan, NOW)  # type: ignore[arg-type]
    with pytest.raises(InvalidRebalanceProposalRequestError, match="plan"):
        RebalanceProposalRequest(UUID(int=100), object(), NOW)  # type: ignore[arg-type]
    with pytest.raises(InvalidRebalanceProposalRequestError, match="policy"):
        RebalanceProposalRequest(  # type: ignore[arg-type]
            UUID(int=100), plan, NOW, policy=True
        )


def test_request_normalizes_equal_instant_and_rejects_other_times() -> None:
    local = NOW.astimezone(timezone(timedelta(hours=-4)))
    request = RebalanceProposalRequest(UUID(int=100), make_plan(), local)
    assert request.proposal_created_at == NOW
    with pytest.raises(InvalidRebalanceProposalRequestError, match="aware"):
        RebalanceProposalRequest(UUID(int=100), make_plan(), NOW.replace(tzinfo=None))
    for moment in (NOW - timedelta(seconds=1), NOW + timedelta(seconds=1)):
        with pytest.raises(InvalidRebalanceProposalRequestError, match="equal"):
            RebalanceProposalRequest(UUID(int=100), make_plan(), moment)


@pytest.mark.parametrize(
    "confidence", (None, Decimal("0"), Decimal("0.4"), Decimal("1"))
)
def test_confidence_boundaries_are_preserved(confidence: Decimal | None) -> None:
    result = RebalanceProposalFactory().create(proposal_request(confidence=confidence))
    assert all(item.confidence == confidence for item in result.proposals)


@pytest.mark.parametrize(
    "confidence",
    (0.5, Decimal("NaN"), Decimal("Infinity"), Decimal("-0.1"), Decimal("1.1")),
)
def test_invalid_confidence_is_rejected(confidence: object) -> None:
    with pytest.raises(InvalidRebalanceProposalRequestError, match="confidence"):
        proposal_request(confidence=confidence)  # type: ignore[arg-type]


def test_metadata_is_copied_unique_and_affects_only_result_identity() -> None:
    source = [MetadataEntry("workflow", "one")]
    request = RebalanceProposalRequest(
        UUID(int=100),
        make_plan(),
        NOW,
        metadata=source,  # type: ignore[arg-type]
    )
    source.clear()
    assert request.metadata == (MetadataEntry("workflow", "one"),)
    first = RebalanceProposalFactory().create(request)
    second = RebalanceProposalFactory().create(
        proposal_request(metadata=(MetadataEntry("workflow", "two"),))
    )
    assert tuple(item.proposal_id for item in first.proposals) == tuple(
        item.proposal_id for item in second.proposals
    )
    assert first.result_id != second.result_id
    with pytest.raises(InvalidRebalanceProposalRequestError, match="unique"):
        proposal_request(metadata=(MetadataEntry("a", "1"), MetadataEntry("a", "2")))


def test_partial_is_rejected_by_default_and_allowed_explicitly() -> None:
    partial = make_plan(
        weights=("0.155", "0.345"),
        cash_weight="0.5",
        assumptions=RebalanceAssumptions(
            allow_fractional_quantities=False, quantity_increment=Decimal("1")
        ),
    )
    assert partial.status is RebalanceStatus.PARTIAL
    with pytest.raises(RebalancePlanNotEligibleError):
        RebalanceProposalFactory().create(proposal_request(partial))
    result = RebalanceProposalFactory().create(
        proposal_request(partial, policy=RebalanceProposalPolicy(True))
    )
    assert result.status is RebalanceProposalStatus.CREATED
    assert tuple(item.desired_quantity for item in result.proposals) == tuple(
        item.planned_quantity for item in partial.trades
    )
    assert tuple(item.code for item in result.diagnostics) == (
        RebalanceProposalDiagnosticCode.PARTIAL_PLAN_ACCEPTED,
    )
    assert all("(PARTIAL)" in item.reason for item in result.proposals)


def test_allowed_zero_trade_partial_remains_created() -> None:
    no_action = make_plan(weights=("0.25", "0"), cash_weight="0.75")
    partial = corrupt(no_action, status=RebalanceStatus.PARTIAL)
    result = RebalanceProposalFactory().create(
        proposal_request(partial, policy=RebalanceProposalPolicy(True))
    )
    assert result.status is RebalanceProposalStatus.CREATED
    assert result.proposals == ()


def test_no_action_returns_empty_result_and_infeasible_is_rejected() -> None:
    no_action = make_plan(weights=("0.25", "0"), cash_weight="0.75")
    result = RebalanceProposalFactory().create(proposal_request(no_action))
    assert result.status is RebalanceProposalStatus.NO_ACTION
    assert result.proposals == ()
    assert result.diagnostics[0].code is RebalanceProposalDiagnosticCode.NO_ACTION
    infeasible = corrupt(no_action, status=RebalanceStatus.INFEASIBLE)
    with pytest.raises(RebalancePlanNotEligibleError):
        RebalanceProposalFactory().create(proposal_request(infeasible))


def test_malformed_status_trade_shapes_fail_closed() -> None:
    complete = make_plan()
    no_action = make_plan(weights=("0.25", "0"), cash_weight="0.75")
    with pytest.raises(InconsistentRebalanceProposalResultError, match="complete"):
        RebalanceProposalFactory().create(
            proposal_request(corrupt(no_action, status=RebalanceStatus.COMPLETE))
        )
    for status in (RebalanceStatus.NO_ACTION, RebalanceStatus.INFEASIBLE):
        malformed = corrupt(complete, status=status)
        with pytest.raises(InconsistentRebalanceProposalResultError):
            RebalanceProposalFactory().create(proposal_request(malformed))


def test_repeated_conversion_and_changed_confidence_have_deterministic_ids() -> None:
    factory = RebalanceProposalFactory()
    request = proposal_request(confidence=Decimal("0.5"))
    first = factory.create(request)
    assert first == factory.create(request)
    assert first.result_id.version == 5
    assert all(item.proposal_id.version == 5 for item in first.proposals)
    changed = factory.create(proposal_request(confidence=Decimal("0.6")))
    assert tuple(item.proposal_id for item in first.proposals) != tuple(
        item.proposal_id for item in changed.proposals
    )
    assert first.result_id != changed.result_id


def test_result_rejects_identity_and_mapping_tampering() -> None:
    result = RebalanceProposalFactory().create(proposal_request())
    with pytest.raises(InconsistentRebalanceProposalResultError, match="result_id"):
        RebalanceProposalResult(
            UUID(int=999),
            result.request,
            result.status,
            result.proposals,
            result.diagnostics,
        )
    changed = TradeProposal(
        result.proposals[0].proposal_id,
        result.proposals[0].symbol,
        result.proposals[0].side,
        result.proposals[0].desired_quantity + Decimal("1"),
        result.proposals[0].created_at,
        result.proposals[0].reason,
        result.proposals[0].confidence,
    )
    with pytest.raises(InconsistentRebalanceProposalResultError, match="planned trade"):
        RebalanceProposalResult(
            result.result_id,
            result.request,
            result.status,
            (changed, *result.proposals[1:]),
            result.diagnostics,
        )


def test_factory_defensively_rejects_duplicate_ids_symbols_and_bad_order() -> None:
    plan = make_plan()
    duplicate = corrupt(plan, trades=(plan.trades[0], plan.trades[0]))
    with pytest.raises(InconsistentRebalanceProposalResultError, match="unique"):
        RebalanceProposalFactory().create(proposal_request(duplicate))
    reversed_plan = corrupt(plan, trades=tuple(reversed(plan.trades)))
    with pytest.raises(InconsistentRebalanceProposalResultError, match="precede"):
        RebalanceProposalFactory().create(proposal_request(reversed_plan))


def test_factory_defensively_rejects_symbol_ordinal_and_quantity_corruption() -> None:
    plan = make_plan()
    wrong_symbol = corrupt_record(plan.trades[0], symbol=QQQ)
    with pytest.raises(InconsistentRebalanceProposalResultError, match="ordinal"):
        RebalanceProposalFactory().create(
            proposal_request(corrupt(plan, trades=(wrong_symbol, *plan.trades[1:])))
        )
    zero_quantity = corrupt_record(plan.trades[0], planned_quantity=Decimal("0"))
    with pytest.raises(InconsistentRebalanceProposalResultError, match="quantity"):
        RebalanceProposalFactory().create(
            proposal_request(corrupt(plan, trades=(zero_quantity, *plan.trades[1:])))
        )


def test_diagnostic_message_does_not_affect_result_identity_but_shape_is_checked() -> (
    None
):
    partial = make_plan(
        weights=("0.155", "0.345"),
        cash_weight="0.5",
        assumptions=RebalanceAssumptions(
            allow_fractional_quantities=False, quantity_increment=Decimal("1")
        ),
    )
    result = RebalanceProposalFactory().create(
        proposal_request(partial, policy=RebalanceProposalPolicy(True))
    )
    replacement = RebalanceProposalDiagnostic(
        RebalanceProposalDiagnosticCode.PARTIAL_PLAN_ACCEPTED, "different text"
    )
    rebuilt = RebalanceProposalResult(
        result.result_id,
        result.request,
        result.status,
        result.proposals,
        (replacement,),
    )
    assert rebuilt.result_id == result.result_id


def test_later_proposal_construction_failure_is_atomic() -> None:
    plan = make_plan()
    request = proposal_request(plan)
    created: list[TradeProposal] = []

    class FailingProposal:
        def __new__(cls, *args):  # noqa: ANN002, ANN204
            if created:
                raise ValueError("defensive failure")
            proposal = TradeProposal(*args)
            created.append(proposal)
            return proposal

    factory = RebalanceProposalFactory()
    factory._proposal_type = FailingProposal
    before = (request, plan)
    with pytest.raises(RebalanceProposalCreationError) as captured:
        factory.create(request)
    assert isinstance(captured.value.__cause__, ValueError)
    assert len(created) == 1
    assert (request, plan) == before


def test_factory_rejects_wrong_request_type() -> None:
    with pytest.raises(TypeError, match="RebalanceProposalRequest"):
        RebalanceProposalFactory().create(object())  # type: ignore[arg-type]
