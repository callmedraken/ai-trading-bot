from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from uuid import UUID, uuid5

import pytest

from trading_bot.desktop_paper.configuration import (
    PaperEvaluationSelectionRequired,
    PaperStrategyBinding,
    PaperStrategyEvaluationInput,
    create_paper_evaluation_config,
    derive_configuration_revision_id,
)
from trading_bot.desktop_paper.models import PaperRuntimePolicy
from trading_bot.domain import Bar, OrderSide, Symbol, TradeProposal

TEST_NAMESPACE = UUID("c8b840d4-8f91-5f95-81ef-4b83d1f1b077")


def _binding(symbol: str = "SYNTH") -> PaperStrategyBinding:
    return PaperStrategyBinding(
        strategy_family="synthetic-fixture",
        strategy_version="fixture-v1",
        symbol=Symbol(symbol),
        parameter_set=(
            ("desired_quantity", Decimal("1")),
            ("short_window", 2),
        ),
        research_campaign_id=uuid5(TEST_NAMESPACE, "campaign"),
        research_bundle_id=uuid5(TEST_NAMESPACE, "bundle"),
        research_candidate_id=uuid5(TEST_NAMESPACE, "candidate"),
        provenance_digest="a" * 64,
    )


def _bar(symbol: Symbol, day: int) -> Bar:
    return Bar(
        symbol=symbol,
        timestamp=datetime(2025, 1, day, tzinfo=UTC),
        open=Decimal("10"),
        high=Decimal("12"),
        low=Decimal("9"),
        close=Decimal("11"),
        volume=100,
    )


def test_config_requires_an_explicit_strategy_binding() -> None:
    with pytest.raises(
        PaperEvaluationSelectionRequired,
        match="PAPER_EVALUATION_SELECTION_REQUIRED",
    ):
        create_paper_evaluation_config(None, PaperRuntimePolicy())


def test_config_revision_is_deterministic_and_scale_canonical() -> None:
    binding = _binding("XYZ")
    first = create_paper_evaluation_config(
        binding, PaperRuntimePolicy(starting_cash=Decimal("100000.00"))
    )
    second = create_paper_evaluation_config(
        binding, PaperRuntimePolicy(starting_cash=Decimal("100000"))
    )

    assert first.configuration_revision_id == second.configuration_revision_id
    assert first == second
    with localcontext() as context:
        context.prec = 2
        assert (
            derive_configuration_revision_id(binding, first.policy)
            == first.configuration_revision_id
        )


def test_policy_change_changes_config_revision() -> None:
    binding = _binding()
    baseline = create_paper_evaluation_config(binding, PaperRuntimePolicy())
    changed = create_paper_evaluation_config(
        binding, PaperRuntimePolicy(replay_interval_seconds=Decimal("0.20"))
    )

    assert changed.configuration_revision_id != baseline.configuration_revision_id


def test_binding_is_generic_and_frozen_without_default_strategy_or_symbol() -> None:
    binding = _binding("AAPL")

    assert binding.symbol == Symbol("AAPL")
    assert binding.strategy_family == "synthetic-fixture"
    with pytest.raises(FrozenInstanceError):
        binding.symbol = Symbol("SPY")  # type: ignore[misc]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"qualification_policy": "qualified"}, "qualification_policy"),
        ({"live_eligible": True}, "live_eligible"),
        ({"purpose": "PAPER_CANDIDATE"}, "purpose"),
        ({"research_candidate_id": "not-a-uuid"}, "research_candidate_id"),
        ({"provenance_digest": "bad"}, "provenance_digest"),
    ],
)
def test_binding_rejects_qualification_live_and_invalid_provenance(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        replace(_binding(), **changes)


def test_binding_preserves_parameter_order_in_immutable_tuple() -> None:
    binding = _binding()
    parameter_set = (
        ("short_window", 2),
        ("desired_quantity", Decimal("1")),
    )

    ordered = replace(binding, parameter_set=parameter_set)

    assert ordered.parameter_set == parameter_set
    with pytest.raises(TypeError, match="tuple"):
        replace(binding, parameter_set=[("short_window", 2)])  # type: ignore[arg-type]


def test_revision_distinguishes_scalar_types_and_canonicalizes_decimal_scale() -> None:
    binding = _binding()
    decimal_one = replace(binding, parameter_set=(("value", Decimal("1")),))
    decimal_one_scaled = replace(binding, parameter_set=(("value", Decimal("1.00")),))
    string_one = replace(binding, parameter_set=(("value", "1"),))
    integer_one = replace(binding, parameter_set=(("value", 1),))

    decimal_revision = derive_configuration_revision_id(
        decimal_one, PaperRuntimePolicy()
    )

    assert decimal_revision == derive_configuration_revision_id(
        decimal_one_scaled, PaperRuntimePolicy()
    )
    assert decimal_revision != derive_configuration_revision_id(
        string_one, PaperRuntimePolicy()
    )
    assert decimal_revision != derive_configuration_revision_id(
        integer_one, PaperRuntimePolicy()
    )


def test_evaluation_input_contains_only_prior_completed_bars() -> None:
    binding = _binding("SYNTH")
    prior = _bar(binding.symbol, 1)
    execution_timestamp = datetime(2025, 1, 2, tzinfo=UTC)
    evaluation_input = PaperStrategyEvaluationInput(
        binding=binding,
        completed_history=[prior],  # type: ignore[arg-type]
        execution_timestamp=execution_timestamp,
    )

    assert evaluation_input.completed_history == (prior,)
    assert evaluation_input.execution_timestamp == execution_timestamp
    with pytest.raises(ValueError, match="end before execution"):
        PaperStrategyEvaluationInput(
            binding=binding,
            completed_history=(prior, _bar(binding.symbol, 2)),
            execution_timestamp=execution_timestamp,
        )
    with pytest.raises(ValueError, match="matching Bars"):
        PaperStrategyEvaluationInput(
            binding=binding,
            completed_history=(_bar(Symbol("OTHER"), 1),),
            execution_timestamp=execution_timestamp,
        )


def test_existing_trade_proposal_is_the_evaluator_output_type() -> None:
    binding = _binding()
    proposal = TradeProposal(
        proposal_id=uuid5(TEST_NAMESPACE, "proposal"),
        symbol=binding.symbol,
        side=OrderSide.BUY,
        desired_quantity=Decimal("1"),
        created_at=datetime(2025, 1, 2, tzinfo=UTC),
        reason="synthetic test signal",
    )

    assert isinstance(proposal, TradeProposal)
    assert proposal.symbol == binding.symbol
