"""Private canonical material shared by historical experiment identities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from trading_bot.execution.state_fingerprints import canonical_decimal

if TYPE_CHECKING:
    from trading_bot.experiments.historical import HistoricalExperimentVariant


def canonical_variant_material(
    variant: HistoricalExperimentVariant,
) -> tuple[str, ...]:
    """Return the complete namespace-free canonical variant material."""
    parameters = variant.optimization_parameters
    constraints = variant.portfolio_constraints
    assumptions = variant.rebalance_assumptions
    limits = variant.risk_limits
    return (
        str(variant.variant_id),
        variant.name,
        str(variant.window_policy.observation_count),
        variant.scenario_policy.price_field.value,
        variant.scenario_policy.return_method.value,
        variant.scenario_policy.window_policy.value,
        variant.execution_price_policy.risk_price_field.value,
        variant.execution_price_policy.fill_reference_price_field.value,
        str(_microseconds(variant.timing_policy.submission_offset)),
        str(_microseconds(variant.timing_policy.fill_offset)),
        canonical_decimal(variant.scenario_cash_return),
        variant.scenario_source_name,
        canonical_decimal(parameters.confidence_level),
        _optional(parameters.minimum_expected_return),
        canonical_decimal(parameters.solver_tolerance),
        str(parameters.maximum_iterations),
        canonical_decimal(parameters.output_quantum),
        canonical_decimal(variant.risk_aversion),
        canonical_decimal(constraints.minimum_cash_weight),
        canonical_decimal(constraints.maximum_cash_weight),
        canonical_decimal(constraints.maximum_position_weight),
        _optional(constraints.maximum_one_way_rebalance_turnover),
        _optional(constraints.minimum_position_weight),
        str(constraints.long_only),
        str(constraints.allow_leverage),
        canonical_decimal(assumptions.fixed_commission),
        str(assumptions.allow_fractional_quantities),
        canonical_decimal(assumptions.quantity_increment),
        canonical_decimal(assumptions.minimum_trade_notional),
        canonical_decimal(assumptions.minimum_trade_quantity),
        canonical_decimal(assumptions.target_weight_tolerance),
        canonical_decimal(assumptions.additional_execution_cash_buffer),
        str(assumptions.use_planned_sell_proceeds),
        str(variant.proposal_policy.allow_partial_plans),
        _optional(variant.proposal_confidence),
        canonical_decimal(limits.max_position_percent),
        canonical_decimal(limits.max_total_exposure_percent),
        _optional(limits.max_order_notional),
        _optional(limits.max_new_position_percent),
        canonical_decimal(limits.minimum_cash_reserve_percent),
        str(limits.allow_fractional_shares),
        canonical_decimal(limits.fractional_increment),
        str(limits.allow_buying),
        str(limits.allow_selling),
        canonical_decimal(limits.estimated_commission),
        str(variant.risk_policy.allow_sell_proceeds_for_later_buys),
        canonical_decimal(variant.fill_policy.slippage_basis_points),
        canonical_decimal(variant.fill_policy.fixed_commission),
        str(variant.trading_enabled),
        *(f"{item.key}={item.value}" for item in variant.metadata),
    )


def canonical_variant_semantic_material(
    variant: HistoricalExperimentVariant,
) -> tuple[str, ...]:
    """Return effective content excluding caller/generated ID and display name."""
    return canonical_variant_material(variant)[2:]


def _optional(value) -> str:  # type: ignore[no-untyped-def]
    return "none" if value is None else canonical_decimal(value)


def _microseconds(value) -> int:  # type: ignore[no-untyped-def]
    return value.days * 86_400_000_000 + value.seconds * 1_000_000 + value.microseconds
