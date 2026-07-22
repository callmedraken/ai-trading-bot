"""Explicit deterministic reporting and atomic output for the offline CLI."""

import json
import os
import tempfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from trading_bot.cli.config import _LoadedSimulationConfig
from trading_bot.cli.exceptions import AuditOutputError
from trading_bot.domain import Order, OrderFill, Position, Symbol
from trading_bot.execution import OrderEvent
from trading_bot.execution.state_fingerprints import canonical_decimal
from trading_bot.ledger import PaperLedger
from trading_bot.portfolio import MetadataEntry, TargetPortfolio
from trading_bot.simulation import OptimizedPaperSimulationResult

AUDIT_SCHEMA_VERSION = 1


def serialize_audit(audit: dict[str, Any], *, pretty: bool) -> str:
    """Serialize one complete audit with stable byte-level settings."""
    try:
        if pretty:
            rendered = json.dumps(audit, ensure_ascii=False, sort_keys=True, indent=2)
        else:
            rendered = json.dumps(
                audit,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
    except (TypeError, ValueError) as error:
        raise AuditOutputError(f"cannot serialize audit output: {error}") from error
    return rendered + "\n"


def write_atomic(destination: Path, content: str, *, overwrite: bool) -> None:
    """Write complete UTF-8 content and atomically replace the destination."""
    parent = destination.parent
    if not parent.is_dir():
        raise AuditOutputError(f"output parent directory does not exist: {parent}")
    if destination.exists() and not overwrite:
        raise AuditOutputError(f"output already exists: {destination}")
    temporary: Path | None = None
    try:
        descriptor, name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=parent
        )
        temporary = Path(name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if destination.exists() and not overwrite:
            raise AuditOutputError(f"output already exists: {destination}")
        os.replace(temporary, destination)
        temporary = None
    except AuditOutputError:
        raise
    except (OSError, UnicodeError) as error:
        raise AuditOutputError(f"cannot write output {destination}: {error}") from error
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def build_audit(
    config: _LoadedSimulationConfig,
    result: OptimizedPaperSimulationResult,
    ledger: PaperLedger,
    bootstrap_fills: tuple[OrderFill, ...],
) -> dict[str, Any]:
    """Build the deliberate version-one optimized-simulation audit tree."""
    initial = config.initial_ledger
    positions: dict[Symbol, Position] = {
        item.symbol: Position(item.symbol, item.quantity, item.average_cost)
        for item in initial.positions
    }
    running_cash = initial.available_cash
    running_realized = Decimal("0")
    frames = []
    for evaluation in result.evaluations:
        cycle = evaluation.cycle_result
        application_evaluations = cycle.application_result.evaluations
        for application in application_evaluations:
            if application.ledger_position_after is None:
                positions.pop(application.fill.symbol, None)
            else:
                positions[application.fill.symbol] = application.ledger_position_after
            running_cash = application.ledger_cash_after
            running_realized = application.ledger_realized_profit_loss_after
        frame_order = tuple(item.symbol for item in evaluation.frame.prices)
        frames.append(
            _frame_audit(
                evaluation,
                running_cash,
                running_realized,
                tuple(
                    positions[symbol] for symbol in frame_order if symbol in positions
                ),
            )
        )
    final_order = tuple(item.symbol for item in result.request.frames[-1].prices)
    bootstrap_ids = {fill.fill_id for fill in bootstrap_fills}
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "configuration": _configuration(config),
        "simulation_request_id": str(result.request.request_id),
        "simulation_result_id": str(result.result_id),
        "status": result.status.value,
        "counts": {
            "frame_count": len(result.evaluations),
            "applied_cycle_count": result.applied_cycle_count,
            "no_action_cycle_count": result.no_action_cycle_count,
        },
        "initial_state": {
            "initialization_mode": initial.initialization_mode.value,
            "as_of": _datetime(initial.as_of),
            "available_cash": _decimal(initial.available_cash),
            "engine_state_id": str(result.initial_engine_state_id),
            "ledger_state_id": str(result.initial_ledger_state_id),
            "positions": [_initial_position(item) for item in initial.positions],
            "bootstrap_fills": [
                _fill(fill, origin="INITIAL_POSITION_BOOTSTRAP")
                for fill in bootstrap_fills
            ],
        },
        "frames": frames,
        "final_state": {
            "engine_state_id": str(result.final_engine_state_id),
            "ledger_state_id": str(result.final_ledger_state_id),
            "cash": _decimal(ledger.cash),
            "realized_profit_loss": _decimal(ledger.realized_profit_loss),
            "positions": [
                _position(ledger.positions[symbol])
                for symbol in final_order
                if symbol in ledger.positions
            ],
            "ledger_fills": [
                _fill(
                    fill,
                    origin=(
                        "INITIAL_POSITION_BOOTSTRAP"
                        if fill.fill_id in bootstrap_ids
                        else "SIMULATION"
                    ),
                )
                for fill in ledger.fills
            ],
        },
    }


def _configuration(config: _LoadedSimulationConfig) -> dict[str, Any]:
    request = config.request
    return {
        "schema_version": config.schema_version,
        "simulation_request_id": str(request.request_id),
        "initial_ledger": {
            "initialization_mode": config.initial_ledger.initialization_mode.value,
            "as_of": _datetime(config.initial_ledger.as_of),
            "available_cash": _decimal(config.initial_ledger.available_cash),
            "positions": [
                _initial_position(item) for item in config.initial_ledger.positions
            ],
        },
        "frames": [_frame_configuration(frame) for frame in request.frames],
        "metadata": _metadata(request.metadata),
    }


def _frame_configuration(frame) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    parameters = frame.optimization_parameters
    constraints = frame.portfolio_constraints
    assumptions = frame.rebalance_assumptions
    limits = frame.risk_limits
    return {
        "as_of": _datetime(frame.as_of),
        "submitted_at": _datetime(frame.submitted_at),
        "filled_at": _datetime(frame.filled_at),
        "prices": [
            {
                "symbol": str(item.symbol),
                "risk_price": _decimal(item.risk_price),
                "fill_reference_price": _decimal(item.fill_reference_price),
            }
            for item in frame.prices
        ],
        "expected_returns": [
            {"symbol": str(item.symbol), "value": _decimal(item.value)}
            for item in frame.expected_returns
        ],
        "scenarios": {
            "scenario_set_id": str(frame.scenarios.scenario_set_id),
            "forecast_horizon": {
                "periods": frame.scenarios.forecast_horizon.periods,
                "timeframe": frame.scenarios.forecast_horizon.timeframe.value,
            },
            "symbols": [str(item) for item in frame.scenarios.symbols],
            "rows": [
                {
                    "scenario_id": str(row.scenario_id),
                    "returns": [_decimal(item) for item in row.returns],
                    "probability": _decimal(row.probability),
                    "metadata": _metadata(row.metadata),
                }
                for row in frame.scenarios.scenarios
            ],
            "cash_return": _decimal(frame.scenarios.cash_return),
            "source": frame.scenarios.source.value,
            "source_name": frame.scenarios.source_name,
            "metadata": _metadata(frame.scenarios.metadata),
        },
        "optimization": {
            "confidence_level": _decimal(parameters.confidence_level),
            "minimum_expected_return": _optional_decimal(
                parameters.minimum_expected_return
            ),
            "solver_tolerance": _decimal(parameters.solver_tolerance),
            "maximum_iterations": parameters.maximum_iterations,
            "output_quantum": _decimal(parameters.output_quantum),
            "risk_aversion": _decimal(frame.risk_aversion),
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
        "rebalance_assumptions": {
            "fixed_commission": _decimal(assumptions.fixed_commission),
            "allow_fractional_quantities": assumptions.allow_fractional_quantities,
            "quantity_increment": _decimal(assumptions.quantity_increment),
            "minimum_trade_notional": _decimal(assumptions.minimum_trade_notional),
            "minimum_trade_quantity": _decimal(assumptions.minimum_trade_quantity),
            "target_weight_tolerance": _decimal(assumptions.target_weight_tolerance),
            "additional_execution_cash_buffer": _decimal(
                assumptions.additional_execution_cash_buffer
            ),
            "use_planned_sell_proceeds": assumptions.use_planned_sell_proceeds,
        },
        "proposal_policy": {
            "allow_partial_plans": frame.proposal_policy.allow_partial_plans
        },
        "proposal_confidence": _optional_decimal(frame.proposal_confidence),
        "risk_limits": {
            "max_position_percent": _decimal(limits.max_position_percent),
            "max_total_exposure_percent": _decimal(limits.max_total_exposure_percent),
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
        "risk_policy": {
            "allow_sell_proceeds_for_later_buys": (
                frame.risk_policy.allow_sell_proceeds_for_later_buys
            )
        },
        "fill_policy": {
            "slippage_basis_points": _decimal(frame.fill_policy.slippage_basis_points),
            "fixed_commission": _decimal(frame.fill_policy.fixed_commission),
        },
        "trading_enabled": frame.trading_enabled,
        "metadata": _metadata(frame.metadata),
    }


def _frame_audit(evaluation, cash, realized, positions):  # type: ignore[no-untyped-def]
    optimization = evaluation.optimization_result
    portfolio = optimization.optimization_result
    certification = evaluation.optimized_target_result
    cycle = evaluation.cycle_result
    target = certification.target
    return {
        "ordinal": evaluation.frame_ordinal,
        "as_of": _datetime(evaluation.frame.as_of),
        "pre_engine_state_id": str(evaluation.pre_engine_state_id),
        "pre_ledger_state_id": str(evaluation.pre_ledger_state_id),
        "post_engine_state_id": str(evaluation.post_engine_state_id),
        "post_ledger_state_id": str(evaluation.post_ledger_state_id),
        "optimization": {
            "request_id": str(evaluation.optimization_request_id),
            "result_id": str(portfolio.result_id),
            "status": portfolio.status.value,
            "solver_name": portfolio.solver_name,
            "objective_value": _optional_decimal(portfolio.objective_value),
            "expected_portfolio_return": _optional_decimal(
                optimization.expected_portfolio_return
            ),
            "cvar": _optional_decimal(optimization.cvar),
            "diagnostics": [
                {
                    "code": item.code,
                    "message": item.message,
                    "level": item.level.value,
                    "value": _optional_decimal(item.value),
                }
                for item in portfolio.diagnostics
            ],
        },
        "certification": {
            "request_id": str(certification.request.request_id),
            "result_id": str(certification.result_id),
            "target": _target(target),
        },
        "runtime": {
            "request_id": str(evaluation.cycle_request_id),
            "result_id": str(cycle.result_id),
            "status": cycle.status.value,
        },
        "planning": {
            "result_id": str(cycle.plan.plan_id),
            "status": cycle.plan.status.value,
            "planned_trade_ids": [
                str(item.planned_trade_id) for item in cycle.plan.trades
            ],
        },
        "proposals": {
            "result_id": str(cycle.proposal_result.result_id),
            "status": cycle.proposal_result.status.value,
            "proposal_ids": [
                str(item.proposal_id) for item in cycle.proposal_result.proposals
            ],
        },
        "risk": {
            "result_id": str(cycle.risk_result.result_id),
            "status": cycle.risk_result.status.value,
            "approved_count": cycle.risk_result.approved_count,
            "resized_count": cycle.risk_result.resized_count,
            "rejected_count": cycle.risk_result.rejected_count,
            "evaluations": [
                {
                    "ordinal": item.ordinal,
                    "proposal_id": str(item.decision.proposal.proposal_id),
                    "outcome": item.decision.outcome.value,
                    "approved_quantity": _decimal(item.decision.approved_quantity),
                    "reasons": [
                        {
                            "code": reason.code.value,
                            "message": reason.message,
                            "observed": _optional_decimal(reason.observed),
                            "limit": _optional_decimal(reason.limit),
                        }
                        for reason in item.decision.reasons
                    ],
                }
                for item in cycle.risk_result.evaluations
            ],
        },
        "orders": [
            {
                **_order(order),
                "creation_event_id": str(event.event_id),
            }
            for order, event in zip(
                cycle.order_result.orders,
                cycle.order_result.created_events,
                strict=True,
            )
        ],
        "order_batch_result_id": str(cycle.order_result.result_id),
        "submissions": [
            {
                **_order(order),
                "submission_event_id": str(event.event_id),
            }
            for order, event in zip(
                cycle.submission_result.orders,
                cycle.submission_result.submitted_events,
                strict=True,
            )
        ],
        "submission_batch_result_id": str(cycle.submission_result.result_id),
        "fills": [
            {
                **_fill(item.fill, origin="SIMULATION"),
                "source_order_ordinal": item.source_order_ordinal,
                "reference_price": _decimal(item.reference_price),
                "slippage_amount": _decimal(item.slippage_amount),
            }
            for item in cycle.fill_result.evaluations
        ],
        "fill_batch_result_id": str(cycle.fill_result.result_id),
        "application": {
            "result_id": str(cycle.application_result.result_id),
            "status": cycle.application_result.status.value,
            "pre_engine_state_id": str(cycle.application_result.pre_engine_state_id),
            "pre_ledger_state_id": str(cycle.application_result.pre_ledger_state_id),
            "post_engine_state_id": str(cycle.application_result.post_engine_state_id),
            "post_ledger_state_id": str(cycle.application_result.post_ledger_state_id),
            "evaluations": [
                {
                    "source_fill_ordinal": item.source_fill_ordinal,
                    "fill_id": str(item.fill.fill_id),
                    "application_event": _event(item.fill_event),
                    "ledger_cash_after": _decimal(item.ledger_cash_after),
                    "ledger_realized_profit_loss_after": _decimal(
                        item.ledger_realized_profit_loss_after
                    ),
                    "ledger_position_after": (
                        None
                        if item.ledger_position_after is None
                        else _position(item.ledger_position_after)
                    ),
                }
                for item in cycle.application_result.evaluations
            ],
        },
        "ending_ledger": {
            "cash": _decimal(cash),
            "realized_profit_loss": _decimal(realized),
            "positions": [_position(item) for item in positions],
        },
    }


def _target(target: TargetPortfolio) -> dict[str, Any]:
    return {
        "target_id": str(target.target_id),
        "as_of": _datetime(target.as_of),
        "allocations": [
            {"symbol": str(item.symbol), "weight": _decimal(item.weight)}
            for item in target.allocations
        ],
        "cash_weight": _decimal(target.cash_weight),
        "source": target.source.value,
        "source_name": target.source_name,
        "metadata": _metadata(target.metadata),
    }


def _order(order: Order) -> dict[str, Any]:
    request = order.request
    return {
        "order_id": str(request.order_id),
        "symbol": str(request.symbol),
        "side": request.side.value,
        "order_type": request.order_type.value,
        "quantity": _decimal(request.quantity),
        "time_in_force": request.time_in_force.value,
        "request_created_at": _datetime(request.submitted_at),
        "status": order.status.value,
        "filled_quantity": _decimal(order.filled_quantity),
        "average_fill_price": _optional_decimal(order.average_fill_price),
    }


def _event(event: OrderEvent) -> dict[str, Any]:
    return {
        "event_id": str(event.event_id),
        "order_id": str(event.order_id),
        "event_type": event.event_type.value,
        "occurred_at": _datetime(event.occurred_at),
        "fill_id": None if event.fill_id is None else str(event.fill_id),
        "reason": event.reason,
    }


def _fill(fill: OrderFill, *, origin: str) -> dict[str, Any]:
    return {
        "origin": origin,
        "fill_id": str(fill.fill_id),
        "order_id": str(fill.order_id),
        "symbol": str(fill.symbol),
        "side": fill.side.value,
        "quantity": _decimal(fill.quantity),
        "price": _decimal(fill.price),
        "commission": _decimal(fill.commission),
        "filled_at": _datetime(fill.filled_at),
    }


def _initial_position(item) -> dict[str, str]:  # type: ignore[no-untyped-def]
    return {
        "symbol": str(item.symbol),
        "quantity": _decimal(item.quantity),
        "average_cost": _decimal(item.average_cost),
    }


def _position(item: Position) -> dict[str, str]:
    return {
        "symbol": str(item.symbol),
        "quantity": _decimal(item.quantity),
        "average_cost": _decimal(item.average_cost),
    }


def _metadata(items: tuple[MetadataEntry, ...]) -> list[dict[str, str]]:
    return [{"key": item.key, "value": item.value} for item in items]


def _decimal(value: Decimal) -> str:
    return canonical_decimal(value)


def _optional_decimal(value: Decimal | None) -> str | None:
    return None if value is None else _decimal(value)


def _datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()
