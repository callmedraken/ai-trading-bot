from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from trading_bot.domain import OrderSide, Position, Symbol, TradeProposal
from trading_bot.portfolio import MetadataEntry
from trading_bot.risk import (
    InconsistentPortfolioRiskBatchResultError,
    InvalidPortfolioRiskBatchRequestError,
    PortfolioRiskBatchRequest,
    PortfolioRiskBatchResult,
    PortfolioRiskBatchStatus,
    PortfolioRiskDecisionError,
    PortfolioRiskDiagnosticCode,
    PortfolioRiskOrchestrator,
    PortfolioRiskPolicy,
    PortfolioRiskPrice,
    PortfolioRiskReservationError,
    RiskContext,
    RiskDecision,
    RiskLimits,
    RiskOutcome,
)

NOW = datetime(2026, 7, 21, 20, tzinfo=UTC)
SPY = Symbol("SPY")
QQQ = Symbol("QQQ")


def limits(**changes: object) -> RiskLimits:
    values: dict[str, object] = {
        "max_position_percent": Decimal("1"),
        "max_total_exposure_percent": Decimal("1"),
        "minimum_cash_reserve_percent": Decimal("0"),
        "max_order_notional": None,
        "max_new_position_percent": None,
        "estimated_commission": Decimal("0"),
    }
    values.update(changes)
    return RiskLimits(**values)  # type: ignore[arg-type]


def proposal(
    identifier: int,
    symbol: Symbol,
    side: OrderSide,
    quantity: str,
    *,
    timestamp: datetime = NOW,
) -> TradeProposal:
    return TradeProposal(
        UUID(int=identifier),
        symbol,
        side,
        Decimal(quantity),
        timestamp,
        "portfolio risk fixture",
    )


def context(
    *,
    cash: str = "1000",
    positions: tuple[tuple[Symbol, str, str], ...] = (),
    prices: dict[Symbol, Decimal] | None = None,
) -> RiskContext:
    price_values = prices or {}
    mapped = {
        symbol: Position(symbol, Decimal(quantity), Decimal(cost))
        for symbol, quantity, cost in positions
    }
    exposure = sum(
        (item.quantity * price_values[symbol] for symbol, item in mapped.items()),
        start=Decimal("0"),
    )
    return RiskContext(
        Decimal(cash),
        Decimal(cash) + exposure,
        mapped,
        None,
        exposure,
        True,
        NOW,
    )


def request(
    proposals: tuple[TradeProposal, ...],
    *,
    base: RiskContext | None = None,
    prices: tuple[PortfolioRiskPrice, ...] | None = None,
    risk_limits: RiskLimits | None = None,
    policy: PortfolioRiskPolicy | None = None,
    metadata: tuple[MetadataEntry, ...] = (),
) -> PortfolioRiskBatchRequest:
    return PortfolioRiskBatchRequest(
        UUID(int=100),
        proposals,
        base or context(),
        prices
        if prices is not None
        else tuple(
            PortfolioRiskPrice(item.symbol, Decimal("100")) for item in proposals
        ),
        risk_limits or limits(),
        policy or PortfolioRiskPolicy(),
        metadata,
    )


def test_one_buy_is_approved_and_reconciles() -> None:
    result = PortfolioRiskOrchestrator().evaluate(
        request((proposal(1, SPY, OrderSide.BUY, "2"),))
    )
    assert result.status is PortfolioRiskBatchStatus.ALL_APPROVED
    assert result.final_risk_available_cash == Decimal("800")
    assert result.final_economic_cash == Decimal("800")
    assert result.final_exposure == Decimal("200")
    assert result.final_economic_equity == Decimal("1000")
    assert result.final_positions[0].quantity == Decimal("2")
    assert result.approved_count == 1


def test_one_sell_reduces_quantity_and_withholds_gross_proceeds() -> None:
    base = context(
        cash="0",
        positions=((SPY, "10", "80"),),
        prices={SPY: Decimal("100")},
    )
    result = PortfolioRiskOrchestrator().evaluate(
        request(
            (proposal(1, SPY, OrderSide.SELL, "4"),),
            base=base,
            prices=(PortfolioRiskPrice(SPY, Decimal("100")),),
        )
    )
    assert result.final_positions[0].quantity == Decimal("6")
    assert result.final_exposure == Decimal("600")
    assert result.final_economic_cash == Decimal("400")
    assert result.final_risk_available_cash == Decimal("0")
    assert result.withheld_sell_proceeds == Decimal("400")
    assert result.diagnostics[0].code is (
        PortfolioRiskDiagnosticCode.SELL_PROCEEDS_WITHHELD
    )


def test_sell_proceeds_policy_changes_later_buy_capacity() -> None:
    base = context(
        cash="0",
        positions=((SPY, "10", "80"),),
        prices={SPY: Decimal("100")},
    )
    proposals = (
        proposal(1, SPY, OrderSide.SELL, "5"),
        proposal(2, QQQ, OrderSide.BUY, "5"),
    )
    prices = (
        PortfolioRiskPrice(SPY, Decimal("100")),
        PortfolioRiskPrice(QQQ, Decimal("100")),
    )
    disabled = PortfolioRiskOrchestrator().evaluate(
        request(proposals, base=base, prices=prices)
    )
    enabled = PortfolioRiskOrchestrator().evaluate(
        request(
            proposals,
            base=base,
            prices=prices,
            policy=PortfolioRiskPolicy(True),
        )
    )
    assert disabled.evaluations[1].decision.outcome is RiskOutcome.REJECTED
    assert enabled.evaluations[1].decision.outcome is RiskOutcome.APPROVED
    assert enabled.final_risk_available_cash == Decimal("0")
    assert enabled.withheld_sell_proceeds == Decimal("0")


def test_two_buys_compete_for_collective_cash() -> None:
    result = PortfolioRiskOrchestrator().evaluate(
        request(
            (
                proposal(1, SPY, OrderSide.BUY, "8"),
                proposal(2, QQQ, OrderSide.BUY, "8"),
            ),
            base=context(cash="1000"),
        )
    )
    assert result.evaluations[0].decision.outcome is RiskOutcome.APPROVED
    assert result.evaluations[1].decision.outcome is RiskOutcome.RESIZED
    assert result.evaluations[1].decision.approved_quantity == Decimal("2")
    assert result.status is PortfolioRiskBatchStatus.PARTIALLY_APPROVED
    assert result.resized_count == 1


def test_rejected_decision_reserves_nothing_and_caller_order_is_preserved() -> None:
    result = PortfolioRiskOrchestrator().evaluate(
        request(
            (
                proposal(1, SPY, OrderSide.BUY, "2"),
                proposal(2, QQQ, OrderSide.BUY, "2"),
            ),
            risk_limits=limits(allow_buying=False),
        )
    )
    assert result.status is PortfolioRiskBatchStatus.ALL_REJECTED
    assert result.total_reserved_commissions == Decimal("0")
    assert result.final_risk_available_cash == Decimal("1000")
    assert tuple(item.decision.proposal.symbol for item in result.evaluations) == (
        SPY,
        QQQ,
    )


def test_commissions_are_reserved_once_and_reduce_economic_equity() -> None:
    result = PortfolioRiskOrchestrator().evaluate(
        request(
            (proposal(1, SPY, OrderSide.BUY, "1"),),
            risk_limits=limits(estimated_commission=Decimal("2")),
        )
    )
    assert result.total_reserved_commissions == Decimal("2")
    assert result.final_economic_equity == Decimal("998")
    assert result.final_economic_cash == Decimal("898")


def test_exact_liquidation_omits_final_position_and_net_sell_can_fund_buy() -> None:
    base = context(
        cash="10",
        positions=((SPY, "1", "90"),),
        prices={SPY: Decimal("100")},
    )
    result = PortfolioRiskOrchestrator().evaluate(
        request(
            (proposal(1, SPY, OrderSide.SELL, "1"),),
            base=base,
            prices=(PortfolioRiskPrice(SPY, Decimal("100")),),
            risk_limits=limits(estimated_commission=Decimal("1")),
            policy=PortfolioRiskPolicy(True),
        )
    )
    assert result.final_positions == ()
    assert result.final_risk_available_cash == Decimal("109")
    assert result.final_economic_equity == Decimal("109")


def test_sell_notional_below_commission_fails_closed() -> None:
    base = context(
        cash="10",
        positions=((SPY, "1", "1"),),
        prices={SPY: Decimal("1")},
    )
    with pytest.raises(PortfolioRiskReservationError, match="cover commission"):
        PortfolioRiskOrchestrator().evaluate(
            request(
                (proposal(1, SPY, OrderSide.SELL, "1"),),
                base=base,
                prices=(PortfolioRiskPrice(SPY, Decimal("1")),),
                risk_limits=limits(estimated_commission=Decimal("2")),
            )
        )


def test_empty_batch_is_explicit_no_action() -> None:
    result = PortfolioRiskOrchestrator().evaluate(
        request((), prices=(), base=context())
    )
    assert result.status is PortfolioRiskBatchStatus.NO_ACTION
    assert result.evaluations == ()
    assert result.diagnostics[0].code is PortfolioRiskDiagnosticCode.NO_ACTION


def test_request_validates_duplicates_prices_timestamps_and_reconciliation() -> None:
    item = proposal(1, SPY, OrderSide.BUY, "1")
    with pytest.raises(InvalidPortfolioRiskBatchRequestError, match="IDs"):
        request((item, item), prices=(PortfolioRiskPrice(SPY, Decimal("100")),))
    with pytest.raises(InvalidPortfolioRiskBatchRequestError, match="symbols"):
        request(
            (item,),
            prices=(
                PortfolioRiskPrice(SPY, Decimal("100")),
                PortfolioRiskPrice(QQQ, Decimal("100")),
            ),
        )
    with pytest.raises(InvalidPortfolioRiskBatchRequestError, match="timestamps"):
        request((proposal(1, SPY, OrderSide.BUY, "1", timestamp=NOW + timedelta(1)),))
    bad = RiskContext(Decimal("100"), Decimal("200"), {}, None, Decimal("0"), True, NOW)
    with pytest.raises(InvalidPortfolioRiskBatchRequestError, match="equity"):
        request((item,), base=bad)


@pytest.mark.parametrize("value", (Decimal("0"), Decimal("NaN"), Decimal("Infinity")))
def test_price_must_be_positive_and_finite(value: Decimal) -> None:
    with pytest.raises(InvalidPortfolioRiskBatchRequestError, match="price"):
        PortfolioRiskPrice(SPY, value)


def test_request_defensively_copies_metadata_and_is_frozen() -> None:
    proposals = [proposal(1, SPY, OrderSide.BUY, "1")]
    metadata = [MetadataEntry("source", "fixture")]
    item = PortfolioRiskBatchRequest(  # type: ignore[arg-type]
        UUID(int=100),
        proposals,
        context(),
        [PortfolioRiskPrice(SPY, Decimal("100"))],
        limits(),
        metadata=metadata,
    )
    proposals.clear()
    metadata.clear()
    assert len(item.proposals) == 1
    with pytest.raises(FrozenInstanceError):
        item.proposals = ()  # type: ignore[misc]
    with pytest.raises(InvalidPortfolioRiskBatchRequestError, match="unique"):
        request(
            (),
            prices=(),
            metadata=(MetadataEntry("a", "1"), MetadataEntry("a", "2")),
        )
    with pytest.raises(InvalidPortfolioRiskBatchRequestError, match="bool"):
        PortfolioRiskPolicy(1)  # type: ignore[arg-type]


def test_invalid_manager_decision_is_atomic_and_wrapped() -> None:
    proposals = (
        proposal(1, SPY, OrderSide.BUY, "1"),
        proposal(2, QQQ, OrderSide.BUY, "1"),
    )
    batch = request(proposals)

    class BadManager:
        def __init__(self, unused: RiskLimits) -> None:
            self.calls = 0

        def evaluate(self, item: TradeProposal, risk_context: RiskContext):
            self.calls += 1
            selected = item if self.calls == 1 else proposals[0]
            return RiskDecision(
                selected,
                RiskOutcome.APPROVED,
                selected.desired_quantity,
                (),
                risk_context.as_of,
            )

    before = batch
    with pytest.raises(PortfolioRiskDecisionError):
        PortfolioRiskOrchestrator(_manager_factory=BadManager).evaluate(batch)
    assert batch == before


def test_result_id_is_deterministic_and_tampering_is_rejected() -> None:
    batch = request((proposal(1, SPY, OrderSide.BUY, "1"),))
    first = PortfolioRiskOrchestrator().evaluate(batch)
    assert first == PortfolioRiskOrchestrator().evaluate(batch)
    assert first.result_id.version == 5
    with pytest.raises(InconsistentPortfolioRiskBatchResultError, match="result_id"):
        PortfolioRiskBatchResult(
            UUID(int=999),
            first.request,
            first.status,
            first.evaluations,
            first.final_positions,
            first.final_risk_available_cash,
            first.final_economic_cash,
            first.final_exposure,
            first.final_economic_equity,
            first.withheld_sell_proceeds,
            first.total_reserved_commissions,
            first.total_approved_buy_notional,
            first.total_approved_sell_notional,
            first.approved_count,
            first.resized_count,
            first.rejected_count,
            first.diagnostics,
        )
