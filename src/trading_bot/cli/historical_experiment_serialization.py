"""Deterministic schema-two audit for offline historical experiments."""

from decimal import Decimal
from typing import Any

from trading_bot.cli._simulation_bootstrap import (
    InitializationMode,
    InitialLedgerConfig,
    InitialPositionConfig,
)
from trading_bot.cli.exceptions import HistoricalExperimentAuditError
from trading_bot.cli.historical_experiment_config import (
    LoadedHistoricalExperimentConfig,
)
from trading_bot.cli.rolling_historical_serialization import (
    build_historical_data_section,
    build_rolling_result_section,
)
from trading_bot.cli.serialization import (
    _datetime,
    _decimal,
    _metadata,
    _optional_decimal,
)
from trading_bot.execution.state_fingerprints import (
    engine_snapshot,
    engine_state_id,
    ledger_snapshot,
    ledger_state_id,
)
from trading_bot.experiments import (
    HistoricalExperimentComparisonResult,
    HistoricalExperimentMetrics,
    HistoricalExperimentRankingPolicy,
    HistoricalExperimentResult,
    HistoricalExperimentVariant,
)
from trading_bot.market_data import MultiSymbolHistoricalDataResult

HISTORICAL_EXPERIMENT_AUDIT_SCHEMA_VERSION = 2


def build_historical_experiment_audit(
    config: LoadedHistoricalExperimentConfig,
    historical: MultiSymbolHistoricalDataResult,
    result: HistoricalExperimentResult,
    comparison: HistoricalExperimentComparisonResult | None,
    factory_records: tuple,
) -> dict[str, Any]:
    """Build a complete raw and optional ranked historical experiment audit."""
    raw = _build_raw_experiment_sections(config, historical, result, factory_records)
    if config.ranking_policy is None:
        if comparison is not None:
            raise HistoricalExperimentAuditError(
                "comparison exists without a configured ranking policy"
            )
        comparison_section = None
    else:
        if comparison is None:
            raise HistoricalExperimentAuditError(
                "configured ranking policy has no comparison result"
            )
        comparison_section = _comparison(config.ranking_policy, result, comparison)
    return {
        "schema_version": HISTORICAL_EXPERIMENT_AUDIT_SCHEMA_VERSION,
        **raw,
        "comparison": comparison_section,
    }


def _build_raw_experiment_sections(
    config: LoadedHistoricalExperimentConfig,
    historical: MultiSymbolHistoricalDataResult,
    result: HistoricalExperimentResult,
    factory_records: tuple,
) -> dict[str, Any]:
    """Build the raw schema-one sections without their former root wrapper."""
    if result.request.historical_data is not historical:
        raise HistoricalExperimentAuditError(
            "experiment result does not retain the exact loaded history"
        )
    if len(factory_records) != len(result.runs):
        raise HistoricalExperimentAuditError(
            "factory record count does not match experiment runs"
        )
    initial_view = _initial_view(config)
    runs = []
    for run, record in zip(result.runs, factory_records, strict=True):
        if (
            record.variant_id != run.variant.variant_id
            or record.variant_ordinal != run.ordinal
            or record.initial_engine_state_id
            != run.rolling_result.initial_engine_state_id
            or record.initial_ledger_state_id
            != run.rolling_result.initial_ledger_state_id
        ):
            raise HistoricalExperimentAuditError(
                f"variant {run.ordinal} initialization record is inconsistent"
            )
        final_engine_id = engine_state_id(engine_snapshot(record.simulator.engine))
        final_ledger_id = ledger_state_id(ledger_snapshot(record.simulator.ledger))
        if (
            final_engine_id != run.rolling_result.final_engine_state_id
            or final_ledger_id != run.rolling_result.final_ledger_state_id
        ):
            raise HistoricalExperimentAuditError(
                f"variant {run.ordinal} final component state is inconsistent"
            )
        runs.append(
            {
                "run_id": str(run.run_id),
                "ordinal": run.ordinal,
                "variant": _variant(run.variant),
                "rolling_request_id": str(run.rolling_request_id),
                "initial_state_content_fingerprint": str(
                    run.initial_state_content_fingerprint
                ),
                "metrics": _metrics(run.metrics),
                "initialization": {
                    "initial_engine_state_id": str(record.initial_engine_state_id),
                    "initial_ledger_state_id": str(record.initial_ledger_state_id),
                    "final_engine_state_id": str(final_engine_id),
                    "final_ledger_state_id": str(final_ledger_id),
                    "bootstrap_fills": [
                        _bootstrap_fill(fill) for fill in record.bootstrap_fills
                    ],
                },
                "rolling": build_rolling_result_section(
                    initial_view,
                    run.rolling_result,
                    record.simulator.ledger,
                    record.bootstrap_fills,
                ),
            }
        )
    return {
        "configuration": _configuration(config),
        "historical_data": build_historical_data_section(
            config.historical_data.source_label, historical
        ),
        "initial_state": {
            "mode": config.initial_state.mode.value,
            "as_of": _datetime(config.initial_state.as_of),
            "available_cash": _decimal(config.initial_state.available_cash),
            "bootstrap_commission": _decimal(config.initial_state.bootstrap_commission),
            "bootstrap_positions": [
                {
                    "symbol": str(item.symbol),
                    "quantity": _decimal(item.quantity),
                    "unit_cost": _decimal(item.unit_cost),
                }
                for item in config.initial_state.bootstrap_positions
            ],
            "content_fingerprint": str(result.initial_state_fingerprint),
        },
        "experiment": {
            "request": {
                "request_id": str(result.request.request_id),
                "rebalance_schedule": [
                    _datetime(item) for item in result.request.rebalance_timestamps
                ],
                "variant_ids": [
                    str(item.variant_id) for item in result.request.variants
                ],
                "metadata": _metadata(result.request.metadata),
            },
            "result": {
                "result_id": str(result.result_id),
                "historical_fingerprint": str(result.historical_fingerprint),
                "schedule_fingerprint": str(result.schedule_fingerprint),
                "initial_state_fingerprint": str(result.initial_state_fingerprint),
                "runs": runs,
            },
        },
    }


def _configuration(config: LoadedHistoricalExperimentConfig) -> dict[str, Any]:
    historical = config.historical_data
    return {
        "schema_version": config.schema_version,
        "request_id": str(config.request_id),
        "historical_data": {
            "symbols": [str(item) for item in historical.symbols],
            "sources": [
                {"symbol": str(item.symbol), "path": item.configured_path}
                for item in historical.sources
            ],
            "start": _datetime(historical.start),
            "end": _datetime(historical.end),
            "timeframe": historical.timeframe.value,
            "adjustment": historical.adjustment.value,
            "missing_bar_policy": historical.missing_bar_policy.value,
            "source_label": historical.source_label,
        },
        "rebalance_schedule": [_datetime(item) for item in config.rebalance_schedule],
        "initial_state": {
            "mode": config.initial_state.mode.value,
            "as_of": _datetime(config.initial_state.as_of),
            "available_cash": _decimal(config.initial_state.available_cash),
            "bootstrap_commission": _decimal(config.initial_state.bootstrap_commission),
            "bootstrap_positions": [
                {
                    "symbol": str(item.symbol),
                    "quantity": _decimal(item.quantity),
                    "unit_cost": _decimal(item.unit_cost),
                }
                for item in config.initial_state.bootstrap_positions
            ],
        },
        "variants": [_variant(item) for item in config.variants],
        "metadata": _metadata(config.metadata),
        "ranking": (
            None
            if config.ranking_policy is None
            else _ranking_policy(config.ranking_policy)
        ),
    }


def _ranking_policy(
    policy: HistoricalExperimentRankingPolicy,
) -> dict[str, Any]:
    return {
        "policy_id": str(policy.policy_id),
        "criteria": [
            {
                "metric": item.metric.value,
                "direction": item.direction.value,
            }
            for item in policy.criteria
        ],
        "tie_breaker": policy.tie_breaker.value,
        "metadata": _metadata(policy.metadata),
    }


def _comparison(
    configured_policy: HistoricalExperimentRankingPolicy,
    experiment_result: HistoricalExperimentResult,
    comparison: HistoricalExperimentComparisonResult,
) -> dict[str, Any]:
    if comparison.experiment_result is not experiment_result:
        raise HistoricalExperimentAuditError(
            "comparison does not retain the exact experiment result"
        )
    if comparison.policy is not configured_policy:
        raise HistoricalExperimentAuditError(
            "comparison does not retain the exact configured ranking policy"
        )
    source_runs = experiment_result.runs
    ranked = comparison.ranked_runs
    if len(ranked) != len(source_runs):
        raise HistoricalExperimentAuditError(
            "comparison ranked-run count differs from raw runs"
        )
    if len({id(item.run) for item in ranked}) != len(ranked) or {
        id(item.run) for item in ranked
    } != {id(item) for item in source_runs}:
        raise HistoricalExperimentAuditError(
            "comparison ranked runs do not exactly cover raw runs"
        )
    rows = []
    for item in ranked:
        if len(item.comparison_values) != len(configured_policy.criteria):
            raise HistoricalExperimentAuditError(
                "comparison value count differs from ranking criteria"
            )
        rows.append(
            {
                "rank": item.rank,
                "caller_ordinal": item.caller_ordinal,
                "source_run_id": str(item.run.run_id),
                "source_variant_id": str(item.run.variant.variant_id),
                "comparison_values": [
                    {
                        "metric": criterion.metric.value,
                        "value": _ranked_value(value),
                    }
                    for criterion, value in zip(
                        configured_policy.criteria,
                        item.comparison_values,
                        strict=True,
                    )
                ],
            }
        )
    return {
        "policy": _ranking_policy(configured_policy),
        "policy_fingerprint": str(comparison.policy_fingerprint),
        "result_id": str(comparison.result_id),
        "source_experiment_result_id": str(experiment_result.result_id),
        "ranked_runs": rows,
    }


def _ranked_value(value: Decimal | int) -> str | int:
    return _decimal(value) if isinstance(value, Decimal) else value


def _variant(item: HistoricalExperimentVariant) -> dict[str, Any]:
    parameters = item.optimization_parameters
    constraints = item.portfolio_constraints
    assumptions = item.rebalance_assumptions
    limits = item.risk_limits
    return {
        "variant_id": str(item.variant_id),
        "name": item.name,
        "rolling_window": {"observation_count": item.window_policy.observation_count},
        "scenario": {
            "price_field": item.scenario_policy.price_field.value,
            "return_method": item.scenario_policy.return_method.value,
            "window_policy": item.scenario_policy.window_policy.value,
            "cash_return": _decimal(item.scenario_cash_return),
            "source_name": item.scenario_source_name,
        },
        "execution_prices": {
            "risk_price_field": item.execution_price_policy.risk_price_field.value,
            "fill_reference_price_field": (
                item.execution_price_policy.fill_reference_price_field.value
            ),
        },
        "timing": {
            "submission_offset_microseconds": _microseconds(
                item.timing_policy.submission_offset
            ),
            "fill_offset_microseconds": _microseconds(item.timing_policy.fill_offset),
        },
        "optimization": {
            "confidence_level": _decimal(parameters.confidence_level),
            "minimum_expected_return": _optional_decimal(
                parameters.minimum_expected_return
            ),
            "solver_tolerance": _decimal(parameters.solver_tolerance),
            "maximum_iterations": parameters.maximum_iterations,
            "output_quantum": _decimal(parameters.output_quantum),
            "risk_aversion": _decimal(item.risk_aversion),
        },
        "portfolio_constraints": {
            "minimum_cash_weight": _decimal(constraints.minimum_cash_weight),
            "maximum_cash_weight": _decimal(constraints.maximum_cash_weight),
            "maximum_position_weight": _decimal(constraints.maximum_position_weight),
            "maximum_one_way_rebalance_turnover": _optional_decimal(
                constraints.maximum_one_way_rebalance_turnover
            ),
            "minimum_position_weight": _optional_decimal(
                constraints.minimum_position_weight
            ),
            "long_only": constraints.long_only,
            "allow_leverage": constraints.allow_leverage,
        },
        "rebalance": {
            "assumptions": {
                "fixed_commission": _decimal(assumptions.fixed_commission),
                "allow_fractional_quantities": (
                    assumptions.allow_fractional_quantities
                ),
                "quantity_increment": _decimal(assumptions.quantity_increment),
                "minimum_trade_notional": _decimal(assumptions.minimum_trade_notional),
                "minimum_trade_quantity": _decimal(assumptions.minimum_trade_quantity),
                "target_weight_tolerance": _decimal(
                    assumptions.target_weight_tolerance
                ),
                "additional_execution_cash_buffer": _decimal(
                    assumptions.additional_execution_cash_buffer
                ),
                "use_planned_sell_proceeds": assumptions.use_planned_sell_proceeds,
            },
            "proposal_policy": {
                "allow_partial_plans": item.proposal_policy.allow_partial_plans
            },
            "proposal_confidence": _optional_decimal(item.proposal_confidence),
        },
        "risk": {
            "limits": {
                "max_position_percent": _decimal(limits.max_position_percent),
                "max_total_exposure_percent": _decimal(
                    limits.max_total_exposure_percent
                ),
                "max_order_notional": _optional_decimal(limits.max_order_notional),
                "max_new_position_percent": _optional_decimal(
                    limits.max_new_position_percent
                ),
                "minimum_cash_reserve_percent": _decimal(
                    limits.minimum_cash_reserve_percent
                ),
                "allow_fractional_shares": limits.allow_fractional_shares,
                "fractional_increment": _decimal(limits.fractional_increment),
                "allow_buying": limits.allow_buying,
                "allow_selling": limits.allow_selling,
                "estimated_commission": _decimal(limits.estimated_commission),
            },
            "policy": {
                "allow_sell_proceeds_for_later_buys": (
                    item.risk_policy.allow_sell_proceeds_for_later_buys
                )
            },
        },
        "fills": {
            "slippage_basis_points": _decimal(item.fill_policy.slippage_basis_points),
            "fixed_commission": _decimal(item.fill_policy.fixed_commission),
        },
        "trading_enabled": item.trading_enabled,
        "metadata": _metadata(item.metadata),
    }


def _metrics(item: HistoricalExperimentMetrics) -> dict[str, Any]:
    return {
        "initial_equity": _decimal(item.initial_equity),
        "final_equity": _decimal(item.final_equity),
        "absolute_simulation_profit_loss": _decimal(
            item.absolute_simulation_profit_loss
        ),
        "simulation_return": _decimal(item.simulation_return),
        "maximum_drawdown_amount": _decimal(item.maximum_drawdown_amount),
        "maximum_drawdown_percentage": _decimal(item.maximum_drawdown_percentage),
        "simulation_realized_profit_loss": _decimal(
            item.simulation_realized_profit_loss
        ),
        "total_commissions": _decimal(item.total_commissions),
        "adverse_slippage_cost": _decimal(item.adverse_slippage_cost),
        "total_execution_cost": _decimal(item.total_execution_cost),
        "aggregate_one_way_turnover": _decimal(item.aggregate_one_way_turnover),
        "aggregate_two_way_turnover": _decimal(item.aggregate_two_way_turnover),
        "maximum_allocation_drift": _decimal(item.maximum_allocation_drift),
        "total_orders": item.total_orders,
        "total_fills": item.total_fills,
        "approved_decisions": item.approved_decisions,
        "resized_decisions": item.resized_decisions,
        "rejected_decisions": item.rejected_decisions,
        "rejected_notional": _decimal(item.rejected_notional),
        "reduced_notional": _decimal(item.reduced_notional),
        "mean_expected_portfolio_return": _decimal(item.mean_expected_portfolio_return),
        "worst_cvar": _decimal(item.worst_cvar),
        "minimum_target_cash_weight": _decimal(item.minimum_target_cash_weight),
        "maximum_target_cash_weight": _decimal(item.maximum_target_cash_weight),
        "applied_cycle_count": item.applied_cycle_count,
        "no_action_cycle_count": item.no_action_cycle_count,
    }


def _initial_view(config: LoadedHistoricalExperimentConfig) -> InitialLedgerConfig:
    initial = config.initial_state
    return InitialLedgerConfig(
        InitializationMode(initial.mode.value),
        initial.as_of,
        initial.available_cash,
        tuple(
            InitialPositionConfig(item.symbol, item.quantity, item.unit_cost)
            for item in initial.bootstrap_positions
        ),
    )


def _bootstrap_fill(fill) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    return {
        "fill_id": str(fill.fill_id),
        "order_id": str(fill.order_id),
        "symbol": str(fill.symbol),
        "side": fill.side.value,
        "quantity": _decimal(fill.quantity),
        "price": _decimal(fill.price),
        "commission": _decimal(fill.commission),
        "filled_at": _datetime(fill.filled_at),
        "origin": "INITIAL_POSITION_BOOTSTRAP",
    }


def _microseconds(value) -> int:  # type: ignore[no-untyped-def]
    return value.days * 86_400_000_000 + value.seconds * 1_000_000 + value.microseconds
