from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, localcontext

from trading_bot.domain import Symbol
from trading_bot.portfolio_manager import (
    Action,
    AIRecommendationSuggestion,
    FakeAIRecommendationProvider,
    InvestmentHorizon,
    RecommendationDiagnosticKind,
    SyntheticReferenceDecisionProvider,
)

from .conftest import ACCOUNT_FP, NOW, make_observation, make_position, make_research


def _portfolio():
    positions = (
        make_position("SPY", "10", price="100", cost=None, available="10"),
        make_position("QQQ", "5", price="50", cost="55", available="5"),
        make_position("IWM", "2", price="60", cost="65", available="2"),
    )
    return make_observation(positions, cash="98830")


def test_synthetic_reference_decides_per_holding_and_opportunity_without_cost_bias():
    observation = _portfolio()
    research = make_research(
        observation,
        signals=(
            ("SPY", "-0.25", "Synthetic risk score is below exit threshold."),
            ("QQQ", "0.01", "Synthetic score is neutral."),
            ("IWM", "-0.15", "Synthetic score is below reduction threshold."),
            ("GLD", "0.15", "Synthetic opportunity score is positive."),
        ),
        opportunity_quotes=(("GLD", "120"),),
    )
    decision = SyntheticReferenceDecisionProvider().evaluate(
        observation, research, decision_at=NOW
    )
    by_symbol = {str(item.symbol): item for item in decision.recommendations}
    assert [str(item.symbol) for item in decision.recommendations] == [
        "SPY",
        "QQQ",
        "IWM",
        "GLD",
    ]
    assert by_symbol["SPY"].action is Action.SELL
    assert by_symbol["SPY"].target_quantity == 0
    assert by_symbol["QQQ"].action is Action.HOLD
    assert by_symbol["IWM"].action is Action.REDUCE
    assert by_symbol["IWM"].target_quantity == Decimal("1.0")
    assert by_symbol["GLD"].action is Action.BUY
    assert by_symbol["GLD"].target_quantity == Decimal("1")
    assert any(
        item.code == "COST_BASIS_UNKNOWN" for item in by_symbol["SPY"].diagnostics
    )
    assert any(
        item.kind is RecommendationDiagnosticKind.PROVIDER_LIMITATION
        for item in by_symbol["QQQ"].diagnostics
    )
    assert not decision.unavailable
    assert "profitable" not in by_symbol["SPY"].rationale.casefold()


def test_missing_research_is_explicit_and_snapshot_binding_is_exact():
    observation = _portfolio()
    research = make_research(
        observation,
        signals=(("SPY", None, "Research was not available."),),
        opportunity_quotes=(("GLD", "120"),),
    )
    result = SyntheticReferenceDecisionProvider().evaluate(
        observation, research, decision_at=NOW
    )
    unavailable = {str(item.symbol): item.code for item in result.unavailable}
    assert unavailable["SPY"] == "RESEARCH_UNAVAILABLE"
    assert unavailable["QQQ"] == "RESEARCH_UNAVAILABLE"
    assert unavailable["IWM"] == "RESEARCH_UNAVAILABLE"
    assert all(item.symbol != Symbol("GLD") for item in result.recommendations)


def test_decision_and_recommendation_ids_are_stable_and_context_bound():
    observation = _portfolio()
    research = make_research(observation, opportunity_quotes=(("GLD", "120"),))
    provider = SyntheticReferenceDecisionProvider()
    first = provider.evaluate(observation, research, decision_at=NOW)
    second = provider.evaluate(observation, research, decision_at=NOW)
    assert first.decision_batch_id == second.decision_batch_id
    assert tuple(item.recommendation_id for item in first.recommendations) == tuple(
        item.recommendation_id for item in second.recommendations
    )
    later = provider.evaluate(
        observation, research, decision_at=NOW + timedelta(seconds=1)
    )
    assert later.decision_batch_id != first.decision_batch_id
    assert first.recommendations[0].portfolio_snapshot_id == observation.snapshot_id
    assert first.recommendations[0].account_fingerprint == ACCOUNT_FP
    assert first.recommendations[0].research_input_id == research.research_input_id


def test_fake_ai_provider_binds_prices_and_reports_missing_holdings():
    observation = _portfolio()
    research = make_research(observation, opportunity_quotes=(("GLD", "120"),))
    provider = FakeAIRecommendationProvider(
        (
            AIRecommendationSuggestion(
                Symbol("GLD"),
                Action.BUY,
                Decimal("1000"),
                "Fake model requests an oversized buy.",
            ),
        ),
        investment_horizon=InvestmentHorizon("FAKE_1Y", 252),
    )
    result = provider.evaluate(observation, research, decision_at=NOW)
    assert not hasattr(result.recommendations[0], "price")
    missing = {str(item.symbol) for item in result.unavailable}
    assert missing == {"SPY", "QQQ", "IWM"}
    assert result.recommendations[0].action is Action.BUY
    assert result.recommendations[0].diagnostics[0].code == "FAKE_AI_OUTPUT_UNVALIDATED"


def test_decimal_identity_and_valuation_do_not_depend_on_ambient_context():
    position = make_position(
        "SPY", "123456789.123456789", price="1.23456789123456789", cost="1"
    )
    observation = make_observation((position,), cash="0")
    with localcontext() as context:
        context.prec = 3
        first_id = observation.snapshot_id
        market_value = position.market_value
        equity = observation.locally_computed_equity
        pnl = position.unrealized_pnl
    with localcontext() as context:
        context.prec = 80
        assert observation.snapshot_id == first_id
        assert position.market_value == market_value
        assert observation.locally_computed_equity == equity
        assert position.unrealized_pnl == pnl
    assert market_value == Decimal("152415787.80673678515622620750190521")
