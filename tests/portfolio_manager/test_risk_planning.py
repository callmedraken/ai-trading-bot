from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from trading_bot.domain import Symbol
from trading_bot.portfolio_manager import (
    Action,
    AIRecommendationSuggestion,
    DecisionBatch,
    FakeAIRecommendationProvider,
    InvestmentHorizon,
    MarketQuote,
    OrderCoverage,
    OrderObservation,
    OrderOwnership,
    PreviewSide,
    Recommendation,
    RiskCode,
    RiskDisposition,
    RiskPolicy,
    evaluate_recommendations,
    plan_preview,
)
from trading_bot.portfolio_manager.models import ObservationProvenance

from .conftest import NOW, make_observation, make_position, make_research


def _batch(observation, research, *specs):  # type: ignore[no-untyped-def]
    recommendations = tuple(
        Recommendation(
            symbol=Symbol(symbol),
            action=action,
            portfolio_snapshot_id=observation.snapshot_id,
            account_fingerprint=observation.account_fingerprint,
            research_input_id=research.research_input_id,
            strategy_id="SYNTHETIC_TEST_PROVIDER",
            strategy_version="v1",
            decision_at=NOW,
            investment_horizon=InvestmentHorizon("TEST_90D", 90),
            target_quantity=target,
            rationale="Bounded synthetic test recommendation.",
            evidence_available=True,
        )
        for symbol, action, target in specs
    )
    return DecisionBatch(
        portfolio_snapshot_id=observation.snapshot_id,
        account_fingerprint=observation.account_fingerprint,
        research_input_id=research.research_input_id,
        strategy_id="SYNTHETIC_TEST_PROVIDER",
        strategy_version="v1",
        decision_at=NOW,
        recommendations=recommendations,
        unavailable=(),
    )


def _risk(observation, research, batch, policy=None):  # type: ignore[no-untyped-def]
    return evaluate_recommendations(
        observation,
        research,
        batch,
        policy or RiskPolicy(),
        decision_at=NOW,
    )


def _order(
    symbol: str,
    *,
    state="open",
    ownership=OrderOwnership.BOT,
    identifier="order-1",
    filled_quantity=Decimal("0"),
):
    return OrderObservation(
        order_id=identifier,
        symbol=Symbol(symbol),
        side="buy",
        state=state,
        quantity=Decimal("10"),
        filled_quantity=filled_quantity,
        created_at=NOW - timedelta(minutes=1),
        ownership=ownership,
    )


def test_cash_and_concentration_are_evaluated_after_price_lookup():
    observation = make_observation()
    research = make_research(observation, opportunity_quotes=(("GLD", "100"),))
    batch = _batch(observation, research, ("GLD", Action.BUY, Decimal("30")))
    result = _risk(observation, research, batch)[0]
    assert result.disposition is RiskDisposition.BLOCKED
    assert RiskCode.MAX_POSITION_WEIGHT in result.codes
    assert result.price == Decimal("100")
    assert result.preview_only is True and result.dispatch_authorized is False


def test_pending_order_conflicts_cover_unheld_opportunity_symbols():
    observation = make_observation(orders=(_order("GLD"),))
    research = make_research(observation, opportunity_quotes=(("GLD", "100"),))
    batch = _batch(observation, research, ("GLD", Action.BUY, Decimal("1")))
    result = _risk(observation, research, batch)[0]
    assert result.disposition is RiskDisposition.BLOCKED
    assert RiskCode.PENDING_ORDER_CONFLICT in result.codes


@pytest.mark.parametrize(
    "state,filled_quantity",
    [
        ("queued", Decimal("0")),
        ("pending", Decimal("0")),
        ("confirmed", Decimal("0")),
        ("partially_filled", Decimal("2")),
    ],
)
def test_open_order_states_and_partial_fills_remain_pending(state, filled_quantity):
    partial = _order(
        "GLD",
        state=state,
        ownership=OrderOwnership.UNKNOWN,
        identifier=f"pending-{state}",
        filled_quantity=filled_quantity,
    )
    assert partial.pending
    if state == "partially_filled":
        assert partial.filled_quantity == Decimal("2")

    observation = make_observation(orders=(partial,))
    research = make_research(observation, opportunity_quotes=(("GLD", "100"),))
    batch = _batch(observation, research, ("GLD", Action.BUY, Decimal("1")))
    result = _risk(observation, research, batch)[0]

    assert result.disposition is RiskDisposition.BLOCKED
    assert RiskCode.PENDING_ORDER_CONFLICT in result.codes


def test_pending_external_order_unknown_ownership_and_duplicate_ids_block_actions():
    external = _order("GLD", ownership=OrderOwnership.EXTERNAL, identifier="external-1")
    observation = make_observation(orders=(external,))
    research = make_research(observation, opportunity_quotes=(("GLD", "100"),))
    batch = _batch(observation, research, ("GLD", Action.BUY, Decimal("1")))
    result = _risk(observation, research, batch)[0]
    assert result.disposition is RiskDisposition.BLOCKED
    assert RiskCode.PENDING_ORDER_CONFLICT in result.codes

    duplicated = make_observation(orders=(external, external))
    research = make_research(duplicated, opportunity_quotes=(("GLD", "100"),))
    batch = _batch(duplicated, research, ("GLD", Action.BUY, Decimal("1")))
    result = _risk(duplicated, research, batch)[0]
    assert result.disposition is RiskDisposition.BLOCKED
    assert RiskCode.DUPLICATE_ORDER_ID in result.codes


def test_unknown_scope_and_incomplete_coverage_never_approve_a_preview():
    position = make_position("SPY", "1")
    observation = make_observation(
        (position,),
        cash="9900",
        order_scope=OrderCoverage.ROBINHOOD_AGENTIC_BOUNDED,
        provenance=ObservationProvenance.ROBINHOOD_READ_ONLY,
    )
    research = make_research(observation, opportunity_quotes=(("GLD", "100"),))
    batch = _batch(observation, research, ("GLD", Action.BUY, Decimal("1")))
    result = _risk(observation, research, batch)[0]
    assert result.disposition is RiskDisposition.BLOCKED
    assert RiskCode.ORDER_SCOPE_INCOMPLETE in result.codes
    assert RiskCode.INCOMPLETE_OBSERVATION in result.codes

    incomplete = make_observation(
        (position,),
        cash="9900",
        coverage_overrides={"pagination_complete": False},
    )
    research = make_research(incomplete, opportunity_quotes=(("GLD", "100"),))
    batch = _batch(incomplete, research, ("GLD", Action.BUY, Decimal("1")))
    result = _risk(incomplete, research, batch)[0]
    assert result.disposition is RiskDisposition.BLOCKED
    assert RiskCode.PAGINATION_INCOMPLETE in result.codes
    assert RiskCode.INCOMPLETE_OBSERVATION in result.codes


def test_stale_observation_or_any_held_quote_blocks_unrelated_buy():
    stale_position = make_position("SPY", "1", price_at=NOW - timedelta(minutes=10))
    observation = make_observation(
        (stale_position,), cash="9900", observed_at=NOW - timedelta(minutes=1)
    )
    research = make_research(observation, opportunity_quotes=(("GLD", "100"),))
    batch = _batch(observation, research, ("GLD", Action.BUY, Decimal("1")))
    result = _risk(observation, research, batch)[0]
    assert result.disposition is RiskDisposition.BLOCKED
    assert RiskCode.STALE_PRICE in result.codes


def test_risk_rejects_market_quote_conflict_instead_of_trusting_recommendation():
    position = make_position("SPY", "1", price="100")
    observation = make_observation((position,), cash="9900")
    research = make_research(
        observation,
        quote_overrides=(
            MarketQuote(Symbol("SPY"), Decimal("101"), NOW, "fake-model-price"),
        ),
    )
    batch = _batch(observation, research, ("SPY", Action.BUY, Decimal("2")))
    result = _risk(observation, research, batch)[0]
    assert result.disposition is RiskDisposition.BLOCKED
    assert RiskCode.PRICE_SOURCE_CONFLICT in result.codes


def test_sellable_quantity_and_adverse_cost_floor_block_sells():
    position = make_position("SPY", "10", price="100", available="1")
    observation = make_observation((position,), cash="0")
    research = make_research(observation)
    batch = _batch(observation, research, ("SPY", Action.SELL, Decimal("0")))
    result = _risk(observation, research, batch)[0]
    assert result.disposition is RiskDisposition.BLOCKED
    assert RiskCode.AVAILABLE_TO_SELL in result.codes

    tiny = make_position("SPY", "0.001", price="10", available="0.001")
    observation = make_observation((tiny,), cash="0")
    research = make_research(observation)
    batch = _batch(observation, research, ("SPY", Action.SELL, Decimal("0")))
    result = _risk(observation, research, batch)[0]
    assert result.disposition is RiskDisposition.BLOCKED
    assert RiskCode.SELL_COST_FLOOR in result.codes


def test_sell_from_flat_position_is_invalid_and_never_falls_through_to_approval():
    flat = make_position("SPY", "0", price="100", cost="0", available="0")
    observation = make_observation((flat,), cash="10000")
    research = make_research(observation)
    batch = _batch(observation, research, ("SPY", Action.SELL, Decimal("0")))
    result = _risk(observation, research, batch)[0]
    assert result.disposition is RiskDisposition.BLOCKED
    assert result.codes == (RiskCode.INVALID_TARGET_QUANTITY,)
    assert result.order_quantity == 0


def test_cash_only_buy_reservations_are_aggregate_and_input_ordered():
    observation = make_observation(cash="10000")
    research = make_research(
        observation,
        opportunity_quotes=(("GLD", "100"), ("TLT", "100")),
        signals=(
            ("GLD", "0.2", "First synthetic opportunity."),
            ("TLT", "0.2", "Second synthetic opportunity."),
        ),
    )
    batch = _batch(
        observation,
        research,
        ("GLD", Action.BUY, Decimal("48")),
        ("TLT", Action.BUY, Decimal("48")),
    )
    policy = RiskPolicy(
        maximum_position_weight=Decimal("0.95"),
        maximum_total_exposure_weight=Decimal("0.95"),
        minimum_cash_reserve_weight=Decimal("0.05"),
    )
    first = _risk(observation, research, batch, policy)
    repeated = _risk(observation, research, batch, policy)
    assert tuple(item.disposition for item in first) == (
        RiskDisposition.PREVIEW_APPROVED,
        RiskDisposition.BLOCKED,
    )
    assert RiskCode.INSUFFICIENT_CASH in first[1].codes
    assert tuple(item.disposition for item in first) == tuple(
        item.disposition for item in repeated
    )


def test_unleveraged_buying_power_is_an_independent_limit():
    observation = make_observation(
        cash="10000", buying_power="10000", unleveraged_buying_power="500"
    )
    research = make_research(observation, opportunity_quotes=(("GLD", "100"),))
    batch = _batch(observation, research, ("GLD", Action.BUY, Decimal("10")))
    result = _risk(observation, research, batch)[0]
    assert result.disposition is RiskDisposition.BLOCKED
    assert RiskCode.INSUFFICIENT_UNLEVERAGED_BUYING_POWER in result.codes


def test_rebalance_buys_wait_for_approved_sell_and_plan_contains_dependency_ids():
    positions = (
        make_position("SPY", "10", price="100", available="10"),
        make_position("IWM", "1", price="30", available="1"),
    )
    observation = make_observation(positions, cash="89970")
    research = make_research(observation, opportunity_quotes=(("GLD", "100"),))
    batch = _batch(
        observation,
        research,
        ("SPY", Action.SELL, Decimal("0")),
        ("GLD", Action.BUY, Decimal("10")),
        ("IWM", Action.REBALANCE, Decimal("1")),
    )
    evaluated = _risk(observation, research, batch)
    assert [item.disposition for item in evaluated] == [
        RiskDisposition.PREVIEW_APPROVED,
        RiskDisposition.PREVIEW_APPROVED,
        RiskDisposition.NO_ORDER,
    ]
    plan = plan_preview(observation, batch, evaluated)
    assert [item.side for item in plan.legs] == [PreviewSide.SELL, PreviewSide.BUY]
    assert plan.legs[1].depends_on == (plan.legs[0].leg_id,)
    assert plan.sell_before_buy_dependency is True
    assert plan.sell_proceeds_assumed_available == 0
    assert plan.dispatch_authorized is False

    blocked_sell = make_observation(
        (
            make_position("SPY", "10", price="100", available="0"),
            make_position("IWM", "1", price="30", available="1"),
        ),
        cash="89970",
    )
    blocked_research = make_research(blocked_sell, opportunity_quotes=(("GLD", "100"),))
    blocked_batch = _batch(
        blocked_sell,
        blocked_research,
        ("SPY", Action.SELL, Decimal("0")),
        ("GLD", Action.BUY, Decimal("1")),
        ("IWM", Action.REBALANCE, Decimal("1")),
    )
    blocked = _risk(blocked_sell, blocked_research, blocked_batch)
    assert blocked[0].disposition is RiskDisposition.BLOCKED
    assert blocked[1].disposition is RiskDisposition.BLOCKED
    assert RiskCode.REBALANCE_DEPENDENCY_BLOCKED in blocked[1].codes
    blocked_plan = plan_preview(blocked_sell, blocked_batch, blocked)
    assert blocked_plan.legs == ()


def test_proposed_sale_proceeds_never_fund_a_later_rebalance_buy():
    observation = make_observation(
        (
            make_position("SPY", "50", price="100", available="50"),
            make_position("IWM", "1", price="20", available="1"),
        ),
        cash="100",
    )
    research = make_research(
        observation,
        opportunity_quotes=(("GLD", "100"),),
    )
    batch = _batch(
        observation,
        research,
        ("SPY", Action.SELL, Decimal("0")),
        ("GLD", Action.BUY, Decimal("1")),
        ("IWM", Action.REBALANCE, Decimal("1")),
    )
    evaluated = _risk(observation, research, batch)
    assert evaluated[0].disposition is RiskDisposition.PREVIEW_APPROVED
    assert evaluated[1].disposition is RiskDisposition.BLOCKED
    assert RiskCode.INSUFFICIENT_CASH in evaluated[1].codes
    plan = plan_preview(observation, batch, evaluated)
    assert [item.side for item in plan.legs] == [PreviewSide.SELL]
    assert plan.sell_proceeds_assumed_available == 0


def test_fake_ai_buy_still_fails_independent_concentration_risk():
    observation = make_observation()
    research = make_research(observation, opportunity_quotes=(("GLD", "100"),))
    provider = FakeAIRecommendationProvider(
        (
            AIRecommendationSuggestion(
                Symbol("GLD"),
                Action.BUY,
                Decimal("1000"),
                "Fake model requests a large buy.",
            ),
        )
    )
    batch = provider.evaluate(observation, research, decision_at=NOW)
    result = _risk(observation, research, batch)[0]
    assert result.disposition is RiskDisposition.BLOCKED
    assert RiskCode.MAX_POSITION_WEIGHT in result.codes
