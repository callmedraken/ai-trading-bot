"""Focused Architecture 142-A definition and evaluation-policy coverage."""

import json
from dataclasses import fields, replace
from decimal import Decimal, localcontext
from uuid import uuid5

import pytest

from trading_bot.domain import Symbol
from trading_bot.experiments.research_strategy_definition import (
    MOVING_AVERAGE_STRATEGY_ID,
    MOVING_AVERAGE_STRATEGY_VERSION,
    PRODUCTION_STRATEGY_SCHEMA,
    RESEARCH_STRATEGY_DEFINITION_IDENTITY_VERSION,
    RESEARCH_STRATEGY_DEFINITION_NAMESPACE,
    RESEARCH_STRATEGY_DEFINITION_SCHEMA,
    RESEARCH_STRATEGY_EVALUATION_POLICY_IDENTITY_VERSION,
    RESEARCH_STRATEGY_EVALUATION_POLICY_NAMESPACE,
    RESEARCH_STRATEGY_EVALUATION_POLICY_SCHEMA,
    ResearchStrategyDefinition,
    ResearchStrategyDefinitionError,
    ResearchStrategyEvaluationPolicy,
)
from trading_bot.strategies import MovingAverageCrossoverConfig

HEAD = "a" * 40
TREE = "b" * 40


@pytest.fixture
def definition() -> ResearchStrategyDefinition:
    return ResearchStrategyDefinition(
        HEAD,
        TREE,
        Symbol("SPY"),
        MovingAverageCrossoverConfig(2, 3, Decimal("1.00")),
    )


@pytest.fixture
def policy() -> ResearchStrategyEvaluationPolicy:
    return ResearchStrategyEvaluationPolicy(
        starting_cash=Decimal("10000.00"),
        fixed_commission=Decimal("1.00"),
        slippage_basis_points=Decimal("5.00"),
        trading_enabled=True,
        allow_missing_sessions=False,
        max_position_percent=Decimal("0.20"),
        max_total_exposure_percent=Decimal("0.80"),
        max_order_notional=Decimal("5000"),
        max_new_position_percent=Decimal("0.30"),
        minimum_cash_reserve_percent=Decimal("0.10"),
        allow_fractional_shares=True,
        fractional_increment=Decimal("0.001"),
        allow_buying=True,
        allow_selling=True,
        estimated_commission=Decimal("1.00"),
    )


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def test_definition_has_exact_frozen_fields_and_fixed_family(definition) -> None:
    assert tuple(item.name for item in fields(definition)) == (
        "schema",
        "definition_id",
        "strategy_source_head",
        "strategy_source_tree",
        "production_strategy_schema",
        "strategy_id",
        "strategy_version",
        "symbol",
        "strategy_config",
    )
    assert definition.schema == RESEARCH_STRATEGY_DEFINITION_SCHEMA
    assert definition.production_strategy_schema == PRODUCTION_STRATEGY_SCHEMA
    assert definition.strategy_id == MOVING_AVERAGE_STRATEGY_ID
    assert definition.strategy_version == MOVING_AVERAGE_STRATEGY_VERSION
    assert not {
        "target_session",
        "rank",
        "variant_name",
        "metadata",
        "compatibility",
        "verified",
        "lifecycle_stage",
        "promotion_state",
    } & {item.name for item in fields(definition)}


def test_definition_identity_uses_framed_frozen_material(definition) -> None:
    values = (
        RESEARCH_STRATEGY_DEFINITION_IDENTITY_VERSION,
        definition.schema,
        HEAD,
        TREE,
        PRODUCTION_STRATEGY_SCHEMA,
        MOVING_AVERAGE_STRATEGY_ID,
        MOVING_AVERAGE_STRATEGY_VERSION,
        "SPY",
        "2",
        "3",
        "1",
    )
    material = "".join(f"{len(item.encode('utf-8'))}:{item}" for item in values)
    assert definition.definition_id == uuid5(
        RESEARCH_STRATEGY_DEFINITION_NAMESPACE, material
    )
    assert definition.definition_id.version == 5


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("strategy_source_head", "c" * 40),
        ("strategy_source_tree", "d" * 40),
        ("symbol", Symbol("QQQ")),
        (
            "strategy_config",
            MovingAverageCrossoverConfig(4, 5, Decimal("1")),
        ),
    ],
)
def test_definition_semantics_change_identity(definition, field_name, value) -> None:
    assert (
        replace(definition, **{field_name: value}).definition_id
        != definition.definition_id
    )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("strategy_source_head", None),
        ("strategy_source_tree", "A" * 40),
        ("strategy_source_tree", "g" * 40),
        ("symbol", "SPY"),
        ("strategy_config", object()),
    ],
)
def test_definition_rejects_noncanonical_types(definition, field_name, value) -> None:
    with pytest.raises((TypeError, ValueError, ResearchStrategyDefinitionError)):
        replace(definition, **{field_name: value})


def test_definition_canonical_json_roundtrip_and_rejects_noncanonical_decimal(
    definition,
) -> None:
    encoded = definition.to_json()
    assert encoded == _canonical(json.loads(encoded))
    assert ResearchStrategyDefinition.from_json(encoded) == definition
    raw = json.loads(encoded)
    raw["strategy_config"]["desired_quantity"] = "1.00"
    with pytest.raises(ResearchStrategyDefinitionError):
        ResearchStrategyDefinition.from_json(_canonical(raw))
    raw["strategy_config"]["desired_quantity"] = 1.0
    with pytest.raises(ResearchStrategyDefinitionError):
        ResearchStrategyDefinition.from_json(_canonical(raw))


def test_definition_parser_is_self_consistency_only(definition, monkeypatch) -> None:
    import trading_bot.experiments.research_strategy_backtest as backtest

    monkeypatch.setattr(
        backtest.BacktestEngine,
        "run",
        lambda *args, **kwargs: pytest.fail("definition parser executed research"),
    )
    assert ResearchStrategyDefinition.from_json(definition.to_json()) == definition


def test_decimal_identity_is_independent_of_ambient_context(definition, policy) -> None:
    with localcontext() as context:
        context.prec = 2
        assert replace(definition).to_json() == definition.to_json()
        assert replace(policy).to_json() == policy.to_json()
    assert (
        replace(
            definition,
            strategy_config=MovingAverageCrossoverConfig(2, 3, Decimal("1.0")),
        ).definition_id
        == definition.definition_id
    )


def test_policy_binds_every_behavior_affecting_value(policy) -> None:
    assert tuple(item.name for item in fields(policy)) == (
        "schema",
        "policy_id",
        "starting_cash",
        "fixed_commission",
        "slippage_basis_points",
        "trading_enabled",
        "allow_missing_sessions",
        "max_position_percent",
        "max_total_exposure_percent",
        "max_order_notional",
        "max_new_position_percent",
        "minimum_cash_reserve_percent",
        "allow_fractional_shares",
        "fractional_increment",
        "allow_buying",
        "allow_selling",
        "estimated_commission",
    )
    assert policy.schema == RESEARCH_STRATEGY_EVALUATION_POLICY_SCHEMA
    assert policy.risk_limits.estimated_commission == policy.fixed_commission
    assert policy.risk_limits.max_order_notional == policy.max_order_notional
    assert (
        policy.risk_limits.max_new_position_percent == policy.max_new_position_percent
    )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("starting_cash", Decimal("10001")),
        ("fixed_commission", Decimal("2")),
        ("slippage_basis_points", Decimal("6")),
        ("trading_enabled", False),
        ("allow_missing_sessions", True),
        ("max_position_percent", Decimal("0.21")),
        ("max_total_exposure_percent", Decimal("0.81")),
        ("max_order_notional", None),
        ("max_new_position_percent", None),
        ("minimum_cash_reserve_percent", Decimal("0.11")),
        ("allow_fractional_shares", False),
        ("fractional_increment", Decimal("0.002")),
        ("allow_buying", False),
        ("allow_selling", False),
    ],
)
def test_policy_semantics_change_identity(policy, field_name, value) -> None:
    if field_name == "estimated_commission":
        pytest.skip("commission invariant is covered separately")
    if field_name == "fixed_commission":
        changed = replace(
            policy,
            fixed_commission=value,
            estimated_commission=value,
        )
    else:
        changed = replace(policy, **{field_name: value})
    assert changed.policy_id != policy.policy_id


def test_policy_requires_commission_invariant_and_no_hidden_defaults(policy) -> None:
    with pytest.raises(ResearchStrategyDefinitionError):
        replace(policy, estimated_commission=Decimal("2"))
    with pytest.raises(TypeError):
        ResearchStrategyEvaluationPolicy()  # type: ignore[call-arg]
    raw = json.loads(policy.to_json())
    raw["fixed_commission"] = 1.0
    with pytest.raises(ResearchStrategyDefinitionError):
        ResearchStrategyEvaluationPolicy.from_json(_canonical(raw))
    raw = json.loads(policy.to_json())
    raw["trading_enabled"] = 1
    with pytest.raises(ResearchStrategyDefinitionError):
        ResearchStrategyEvaluationPolicy.from_json(_canonical(raw))


def test_policy_identity_and_canonical_json(policy) -> None:
    values = (
        RESEARCH_STRATEGY_EVALUATION_POLICY_IDENTITY_VERSION,
        policy.schema,
        "10000",
        "1",
        "5",
        "true",
        "false",
        "0.2",
        "0.8",
        "5000",
        "0.3",
        "0.1",
        "true",
        "0.001",
        "true",
        "true",
        "1",
    )
    material = "".join(f"{len(item.encode('utf-8'))}:{item}" for item in values)
    assert policy.policy_id == uuid5(
        RESEARCH_STRATEGY_EVALUATION_POLICY_NAMESPACE, material
    )
    assert ResearchStrategyEvaluationPolicy.from_json(policy.to_json()) == policy


@pytest.mark.parametrize(
    "field_name",
    [
        "starting_cash",
        "fixed_commission",
        "slippage_basis_points",
        "max_position_percent",
        "max_total_exposure_percent",
        "minimum_cash_reserve_percent",
        "fractional_increment",
    ],
)
def test_policy_rejects_float_and_nonfinite_decimal(policy, field_name) -> None:
    with pytest.raises((TypeError, ValueError, ResearchStrategyDefinitionError)):
        replace(policy, **{field_name: 1.0})
    with pytest.raises((TypeError, ValueError, ResearchStrategyDefinitionError)):
        replace(policy, **{field_name: Decimal("NaN")})
