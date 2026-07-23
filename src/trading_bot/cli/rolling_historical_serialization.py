"""Deterministic schema-one audit for rolling historical simulations."""

from datetime import UTC
from typing import Any
from uuid import UUID, uuid5

from trading_bot.cli.rolling_historical_config import LoadedRollingHistoricalConfig
from trading_bot.cli.serialization import (
    _decimal,
    _fill,
    _initial_position,
    _metadata,
    _optional_decimal,
    build_optimized_performance_section,
    build_optimized_simulation_section,
    serialize_optimized_frame,
)
from trading_bot.domain import OrderFill
from trading_bot.execution.state_fingerprints import canonical_decimal
from trading_bot.ledger import PaperLedger
from trading_bot.market_data import MultiSymbolHistoricalDataResult
from trading_bot.simulation import RollingHistoricalSimulationResult

ROLLING_AUDIT_SCHEMA_VERSION = 1
_HISTORY_VERSION = "rolling-historical-cli-history-v1"
_HISTORY_NAMESPACE = UUID("5a747dd4-961a-5d96-9018-81e79d80db73")


def build_rolling_audit(
    config: LoadedRollingHistoricalConfig,
    historical: MultiSymbolHistoricalDataResult,
    result: RollingHistoricalSimulationResult,
    ledger: PaperLedger,
    bootstrap_fills: tuple[OrderFill, ...],
) -> dict[str, Any]:
    """Build one deliberate complete rolling audit without recalculating metrics."""
    return {
        "schema_version": ROLLING_AUDIT_SCHEMA_VERSION,
        "configuration": _configuration(config),
        "historical_data": build_historical_data_section(
            config.historical_data.source_label, historical
        ),
        "initial_state": {
            "initialization_mode": config.initial_state.initialization_mode.value,
            "as_of": _datetime(config.initial_state.as_of),
            "available_cash": _decimal(config.initial_state.available_cash),
            "engine_state_id": str(result.initial_engine_state_id),
            "ledger_state_id": str(result.initial_ledger_state_id),
            "positions": [
                _initial_position(item) for item in config.initial_state.positions
            ],
            "bootstrap_fills": [
                _fill(item, origin="INITIAL_POSITION_BOOTSTRAP")
                for item in bootstrap_fills
            ],
        },
        "rolling": build_rolling_result_section(
            config.initial_state,
            result,
            ledger,
            bootstrap_fills,
        ),
    }


def historical_content_fingerprint(
    historical: MultiSymbolHistoricalDataResult,
) -> UUID:
    """Fingerprint the actual loaded request and all ordered OHLCV content."""
    request = historical.request
    material = [
        _HISTORY_VERSION,
        request.start.isoformat(),
        request.end.isoformat(),
        request.timeframe.value,
        request.adjustment.value,
        request.missing_bar_policy.value,
        historical.provider_name,
        *(str(symbol) for symbol in request.symbols),
    ]
    for frame in historical.frames:
        material.extend(
            (
                frame.timestamp.isoformat(),
                *(str(symbol) for symbol in frame.missing_symbols),
            )
        )
        for symbol in frame.symbols:
            bar = frame.bars_by_symbol.get(symbol)
            if bar is None:
                material.extend(("missing", str(symbol)))
            else:
                material.extend(
                    (
                        str(bar.symbol),
                        bar.timestamp.isoformat(),
                        canonical_decimal(bar.open),
                        canonical_decimal(bar.high),
                        canonical_decimal(bar.low),
                        canonical_decimal(bar.close),
                        str(bar.volume),
                    )
                )
    return uuid5(_HISTORY_NAMESPACE, "|".join(material))


def _configuration(config: LoadedRollingHistoricalConfig) -> dict[str, Any]:
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
        "rolling_window": {"observation_count": config.window_policy.observation_count},
        "scenario": {
            "price_field": config.scenario_policy.price_field.value,
            "return_method": config.scenario_policy.return_method.value,
            "window_policy": config.scenario_policy.window_policy.value,
            "cash_return": _decimal(config.scenario_cash_return),
            "source_name": config.scenario_source_name,
            "forecast_horizon": {"periods": 1, "timeframe": "1D"},
        },
        "execution_prices": {
            "risk_price_field": config.execution_price_policy.risk_price_field.value,
            "fill_reference_price_field": (
                config.execution_price_policy.fill_reference_price_field.value
            ),
        },
        "timing": {
            "submission_offset_microseconds": _microseconds(
                config.timing_policy.submission_offset
            ),
            "fill_offset_microseconds": _microseconds(config.timing_policy.fill_offset),
        },
        "initial_state": {
            "initialization_mode": config.initial_state.initialization_mode.value,
            "as_of": _datetime(config.initial_state.as_of),
            "available_cash": _decimal(config.initial_state.available_cash),
            "positions": [
                _initial_position(item) for item in config.initial_state.positions
            ],
        },
        "optimization": _optimization(config),
        "portfolio_constraints": _constraints(config),
        "rebalance": _rebalance(config),
        "risk": _risk(config),
        "fills": {
            "slippage_basis_points": _decimal(config.fill_policy.slippage_basis_points),
            "fixed_commission": _decimal(config.fill_policy.fixed_commission),
        },
        "trading_enabled": config.trading_enabled,
        "metadata": _metadata(config.metadata),
    }


def build_historical_data_section(
    source_label: str, historical: MultiSymbolHistoricalDataResult
) -> dict[str, Any]:
    """Serialize shared loaded history without CLI configuration or paths."""
    request = historical.request
    return {
        "provider_name": historical.provider_name,
        "source_label": source_label,
        "request": {
            "start": _datetime(request.start),
            "end": _datetime(request.end),
            "timeframe": request.timeframe.value,
            "adjustment": request.adjustment.value,
            "missing_bar_policy": request.missing_bar_policy.value,
            "symbols": [str(item) for item in request.symbols],
        },
        "frame_count": len(historical.frames),
        "first_timestamp": _datetime(historical.frames[0].timestamp),
        "last_timestamp": _datetime(historical.frames[-1].timestamp),
        "is_complete": historical.is_complete,
        "content_fingerprint": str(historical_content_fingerprint(historical)),
        "frames": [
            {
                "timestamp": _datetime(frame.timestamp),
                "symbols": [str(item) for item in frame.symbols],
                "missing_symbols": [str(item) for item in frame.missing_symbols],
                "bars": [
                    {
                        "symbol": str(symbol),
                        "timestamp": _datetime(frame.bars_by_symbol[symbol].timestamp),
                        "open": _decimal(frame.bars_by_symbol[symbol].open),
                        "high": _decimal(frame.bars_by_symbol[symbol].high),
                        "low": _decimal(frame.bars_by_symbol[symbol].low),
                        "close": _decimal(frame.bars_by_symbol[symbol].close),
                        "volume": frame.bars_by_symbol[symbol].volume,
                    }
                    for symbol in frame.symbols
                    if symbol in frame.bars_by_symbol
                ],
            }
            for frame in historical.frames
        ],
    }


def build_rolling_result_section(
    initial_state,
    result: RollingHistoricalSimulationResult,
    ledger: PaperLedger,
    bootstrap_fills: tuple[OrderFill, ...],
) -> dict[str, Any]:
    """Serialize one rolling domain request/result without its CLI root wrapper."""
    return {
        "request": _rolling_request(result),
        "result": {
            "result_id": str(result.result_id),
            "frame_generations": [
                _frame_generation(item) for item in result.frame_generations
            ],
            "optimized_simulation": build_optimized_simulation_section(
                initial_state,
                result.optimized_result,
                ledger,
                bootstrap_fills,
            ),
            "performance": build_optimized_performance_section(
                result.performance_result
            ),
            "state_ids": {
                "initial_engine": str(result.initial_engine_state_id),
                "initial_ledger": str(result.initial_ledger_state_id),
                "final_engine": str(result.final_engine_state_id),
                "final_ledger": str(result.final_ledger_state_id),
            },
        },
    }


def _rolling_request(result: RollingHistoricalSimulationResult) -> dict[str, Any]:
    request = result.request
    return {
        "request_id": str(request.request_id),
        "rebalance_schedule": [
            _datetime(item) for item in request.rebalance_timestamps
        ],
        "observation_count": request.window_policy.observation_count,
        "scenario_cash_return": _decimal(request.scenario_cash_return),
        "scenario_source_name": request.scenario_source_name,
        "trading_enabled": request.trading_enabled,
        "metadata": _metadata(request.metadata),
    }


def _frame_generation(item) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    return {
        "frame_ordinal": item.frame_ordinal,
        "rebalance_timestamp": _datetime(item.rebalance_timestamp),
        "historical_frame_index": item.historical_frame_index,
        "window_start_index": item.window_start_index,
        "window_end_index_inclusive": item.window_end_index_inclusive,
        "window_start_timestamp": _datetime(item.window_start_timestamp),
        "window_end_timestamp": _datetime(item.window_end_timestamp),
        "source_frame_id": str(item.source_frame_id),
        "scenario_request_id": str(item.scenario_request_id),
        "scenario_result": _scenario_result(item.scenario_result),
        "optimized_frame_fingerprint": str(item.optimized_frame_fingerprint),
        "optimized_frame": serialize_optimized_frame(item.optimized_frame),
    }


def _scenario_result(result) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    request = result.request
    scenario_set = result.scenario_set
    return {
        "result_id": str(result.result_id),
        "request": {
            "request_id": str(request.request_id),
            "as_of": _datetime(request.as_of),
            "historical_request": {
                "start": _datetime(request.historical_data.request.start),
                "end": _datetime(request.historical_data.request.end),
                "symbols": [
                    str(item) for item in request.historical_data.request.symbols
                ],
                "timeframe": request.historical_data.request.timeframe.value,
                "adjustment": request.historical_data.request.adjustment.value,
                "missing_bar_policy": (
                    request.historical_data.request.missing_bar_policy.value
                ),
                "provider_name": request.historical_data.provider_name,
                "frame_count": len(request.historical_data.frames),
            },
            "policy": {
                "price_field": request.policy.price_field.value,
                "return_method": request.policy.return_method.value,
                "window_policy": request.policy.window_policy.value,
            },
            "forecast_horizon": {
                "periods": request.forecast_horizon.periods,
                "timeframe": request.forecast_horizon.timeframe.value,
            },
            "cash_return": _decimal(request.cash_return),
            "source_name": request.source_name,
            "metadata": _metadata(request.metadata),
        },
        "scenario_set": {
            "scenario_set_id": str(scenario_set.scenario_set_id),
            "as_of": _datetime(scenario_set.as_of),
            "forecast_horizon": {
                "periods": scenario_set.forecast_horizon.periods,
                "timeframe": scenario_set.forecast_horizon.timeframe.value,
            },
            "symbols": [str(item) for item in scenario_set.symbols],
            "rows": [
                {
                    "scenario_id": str(row.scenario_id),
                    "returns": [_decimal(value) for value in row.returns],
                    "probability": _decimal(row.probability),
                    "metadata": _metadata(row.metadata),
                }
                for row in scenario_set.scenarios
            ],
            "cash_return": _decimal(scenario_set.cash_return),
            "source": scenario_set.source.value,
            "source_name": scenario_set.source_name,
            "metadata": _metadata(scenario_set.metadata),
        },
        "expected_returns": [
            {"symbol": str(item.symbol), "value": _decimal(item.value)}
            for item in result.expected_returns
        ],
        "diagnostics": [
            {
                "code": item.code.value,
                "message": item.message,
                "symbol": None if item.symbol is None else str(item.symbol),
            }
            for item in result.diagnostics
        ],
    }


def _optimization(config: LoadedRollingHistoricalConfig) -> dict[str, Any]:
    item = config.optimization_parameters
    return {
        "confidence_level": _decimal(item.confidence_level),
        "minimum_expected_return": _optional_decimal(item.minimum_expected_return),
        "solver_tolerance": _decimal(item.solver_tolerance),
        "maximum_iterations": item.maximum_iterations,
        "output_quantum": _decimal(item.output_quantum),
        "risk_aversion": _decimal(config.risk_aversion),
    }


def _constraints(config: LoadedRollingHistoricalConfig) -> dict[str, Any]:
    item = config.portfolio_constraints
    return {
        "minimum_cash_weight": _decimal(item.minimum_cash_weight),
        "maximum_cash_weight": _decimal(item.maximum_cash_weight),
        "maximum_position_weight": _decimal(item.maximum_position_weight),
        "maximum_one_way_rebalance_turnover": _optional_decimal(
            item.maximum_one_way_rebalance_turnover
        ),
        "minimum_position_weight": _optional_decimal(item.minimum_position_weight),
        "long_only": item.long_only,
        "allow_leverage": item.allow_leverage,
    }


def _rebalance(config: LoadedRollingHistoricalConfig) -> dict[str, Any]:
    item = config.rebalance_assumptions
    return {
        "assumptions": {
            "fixed_commission": _decimal(item.fixed_commission),
            "allow_fractional_quantities": item.allow_fractional_quantities,
            "quantity_increment": _decimal(item.quantity_increment),
            "minimum_trade_notional": _decimal(item.minimum_trade_notional),
            "minimum_trade_quantity": _decimal(item.minimum_trade_quantity),
            "target_weight_tolerance": _decimal(item.target_weight_tolerance),
            "additional_execution_cash_buffer": _decimal(
                item.additional_execution_cash_buffer
            ),
            "use_planned_sell_proceeds": item.use_planned_sell_proceeds,
        },
        "proposal_policy": {
            "allow_partial_plans": config.proposal_policy.allow_partial_plans
        },
        "proposal_confidence": _optional_decimal(config.proposal_confidence),
    }


def _risk(config: LoadedRollingHistoricalConfig) -> dict[str, Any]:
    item = config.risk_limits
    return {
        "limits": {
            "max_position_percent": _decimal(item.max_position_percent),
            "max_total_exposure_percent": _decimal(item.max_total_exposure_percent),
            "max_order_notional": _optional_decimal(item.max_order_notional),
            "max_new_position_percent": _optional_decimal(
                item.max_new_position_percent
            ),
            "minimum_cash_reserve_percent": _decimal(item.minimum_cash_reserve_percent),
            "allow_fractional_shares": item.allow_fractional_shares,
            "fractional_increment": _decimal(item.fractional_increment),
            "allow_buying": item.allow_buying,
            "allow_selling": item.allow_selling,
            "estimated_commission": _decimal(item.estimated_commission),
        },
        "policy": {
            "allow_sell_proceeds_for_later_buys": (
                config.risk_policy.allow_sell_proceeds_for_later_buys
            )
        },
    }


def _datetime(value) -> str:  # type: ignore[no-untyped-def]
    return value.astimezone(UTC).isoformat()


def _microseconds(value) -> int:  # type: ignore[no-untyped-def]
    return value.days * 86_400_000_000 + value.seconds * 1_000_000 + value.microseconds
