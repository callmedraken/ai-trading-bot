"""Deterministic offline backtest evidence for a strategy-native definition.

The runner accepts one already validated immutable ``HistoricalDataResult`` and
uses the existing pure single-symbol backtest engine unchanged.  Parsing and
fingerprinting are value-based; neither operation performs research or external
verification.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.analytics.analyzer import PerformanceAnalyzer
from trading_bot.analytics.models import PerformanceReport
from trading_bot.backtesting.engine import BacktestEngine
from trading_bot.backtesting.models import (
    BacktestConfig,
    BacktestResult,
    BacktestStep,
)
from trading_bot.domain import (
    Bar,
    Order,
    OrderFill,
    Position,
    Symbol,
    TradeProposal,
)
from trading_bot.execution.models import OrderEvent
from trading_bot.experiments.research_strategy_definition import (
    ResearchStrategyDefinition,
    ResearchStrategyDefinitionError,
    ResearchStrategyEvaluationPolicy,
)
from trading_bot.ledger.models import AccountSnapshot
from trading_bot.market_calendar.nyse import NYSEMarketCalendar
from trading_bot.market_data.models import (
    AdjustmentType,
    HistoricalDataRequest,
    HistoricalDataResult,
    Timeframe,
)
from trading_bot.risk.models import RiskDecision, RiskLimits, RiskReason
from trading_bot.strategies.moving_average import MovingAverageCrossoverStrategy

RESEARCH_STRATEGY_BACKTEST_EVIDENCE_SCHEMA = "research-strategy-backtest-evidence/v1"
RESEARCH_STRATEGY_BACKTEST_EVIDENCE_IDENTITY_VERSION = (
    "research-strategy-backtest-evidence-identity/v1"
)
RESEARCH_STRATEGY_BACKTEST_EVIDENCE_NAMESPACE = UUID(
    "b7e51d04-4d94-5b1c-b04d-6381c99dce27"
)
HISTORICAL_DATA_FINGERPRINT_VERSION = "research-strategy-historical-data-fingerprint/v1"
BACKTEST_RUN_IDENTITY_VERSION = "research-strategy-backtest-run-identity/v1"
BACKTEST_RESULT_FINGERPRINT_VERSION = "research-strategy-backtest-result-fingerprint/v1"
STANDALONE_FOLD_ROLE = "STANDALONE"

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_EVIDENCE_FIELDS = frozenset(
    {
        "schema",
        "evidence_id",
        "definition_id",
        "evaluation_policy_id",
        "evaluation_source_head",
        "evaluation_source_tree",
        "historical_data_fingerprint",
        "data_request_symbol",
        "data_request_start",
        "data_request_end",
        "data_request_timeframe",
        "data_request_adjustment",
        "provider_name",
        "backtest_run_id",
        "backtest_result_fingerprint",
        "bar_count",
        "start_timestamp",
        "end_timestamp",
        "total_return",
        "maximum_drawdown_percentage",
        "final_equity",
    }
)
_ZERO = Decimal("0")


class ResearchStrategyBacktestError(ValueError):
    """Raised for malformed or unreconcilable 142-A evidence."""


class _FoldRole(StrEnum):
    STANDALONE = STANDALONE_FOLD_ROLE
    TRAINING = "TRAINING"
    TEST = "TEST"


def _frame(value: str) -> str:
    try:
        return f"{len(value.encode('utf-8'))}:{value}"
    except UnicodeError:
        raise ResearchStrategyBacktestError("identity text must be UTF-8") from None


def _identity(namespace: UUID, version: str, values: tuple[str, ...]) -> UUID:
    return uuid5(namespace, "".join(_frame(value) for value in (version, *values)))


def _identity_material(namespace: UUID, values: tuple[str, ...]) -> UUID:
    return uuid5(namespace, "".join(_frame(value) for value in values))


def _decimal(value: object, name: str) -> str:
    if type(value) is not Decimal or not value.is_finite():
        raise ResearchStrategyBacktestError(f"{name} must be a finite Decimal")
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return "0" if rendered in {"", "-0"} else rendered


def _parse_decimal(value: object, name: str) -> Decimal:
    if type(value) is not str:
        raise ResearchStrategyBacktestError(f"{name} must be canonical Decimal text")
    try:
        parsed = Decimal(value)
    except ArithmeticError:
        raise ResearchStrategyBacktestError(f"{name} must be a Decimal") from None
    if _decimal(parsed, name) != value:
        raise ResearchStrategyBacktestError(f"{name} is not canonical Decimal text")
    return parsed


def _uuid_text(value: object, name: str) -> str:
    if type(value) is not UUID:
        raise ResearchStrategyBacktestError(f"{name} must be exactly UUID")
    return str(value)


def _parse_uuid(value: object, name: str) -> UUID:
    if type(value) is not str:
        raise ResearchStrategyBacktestError(f"{name} must be canonical UUID text")
    try:
        parsed = UUID(value)
    except ValueError:
        raise ResearchStrategyBacktestError(
            f"{name} must be canonical UUID text"
        ) from None
    if str(parsed) != value:
        raise ResearchStrategyBacktestError(f"{name} must be canonical UUID text")
    return parsed


def _source(value: object, name: str) -> str:
    if type(value) is not str or _SHA40.fullmatch(value) is None:
        raise ResearchStrategyBacktestError(
            f"{name} must be exact lowercase 40-hex text"
        )
    return value


def _timestamp(value: object, name: str) -> str:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ResearchStrategyBacktestError(f"{name} must be aware datetime")
    normalized = value.astimezone(UTC)
    return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_timestamp(value: object, name: str) -> datetime:
    if type(value) is not str:
        raise ResearchStrategyBacktestError(f"{name} must be canonical timestamp text")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ResearchStrategyBacktestError(
            f"{name} must be canonical timestamp text"
        ) from None
    if _timestamp(parsed, name) != value:
        raise ResearchStrategyBacktestError(f"{name} is not canonical timestamp text")
    return parsed.astimezone(UTC)


def _optional_decimal(value: Decimal | None, name: str) -> str:
    return "none" if value is None else _decimal(value, name)


def _optional_text(value: object, name: str) -> str:
    if value is None:
        return "none"
    if type(value) is not str:
        raise ResearchStrategyBacktestError(f"{name} must be text or None")
    return value


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ResearchStrategyBacktestError("duplicate JSON field")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ResearchStrategyBacktestError(f"non-JSON constant {value} is forbidden")


def _exact_fields(value: object, expected: frozenset[str]) -> dict[str, object]:
    if type(value) is not dict or set(value) != expected:
        raise ResearchStrategyBacktestError("exact canonical fields required")
    return value


def _validate_historical_data(data: HistoricalDataResult) -> None:
    if type(data) is not HistoricalDataResult:
        raise ResearchStrategyBacktestError(
            "historical_data must be exactly HistoricalDataResult"
        )
    if type(data.request) is not HistoricalDataRequest:
        raise ResearchStrategyBacktestError(
            "historical_data.request must be exactly HistoricalDataRequest"
        )
    request = data.request
    if type(request.symbol) is not Symbol:
        raise ResearchStrategyBacktestError(
            "historical_data.request.symbol must be exactly Symbol"
        )
    if type(data.provider_name) is not str or not data.provider_name.strip():
        raise ResearchStrategyBacktestError("historical provider_name must be nonblank")
    if request.timeframe is not Timeframe.DAY_1:
        raise ResearchStrategyBacktestError("only daily historical data is supported")
    if request.adjustment is not AdjustmentType.RAW:
        raise ResearchStrategyBacktestError("only RAW historical data is supported")
    if not data.bars:
        raise ResearchStrategyBacktestError("historical data must contain bars")
    previous: datetime | None = None
    for bar in data.bars:
        if type(bar) is not Bar:
            raise ResearchStrategyBacktestError(
                "historical bars must be exact Bar values"
            )
        if type(bar.symbol) is not Symbol:
            raise ResearchStrategyBacktestError("historical bar symbol must be exact")
        if bar.symbol != request.symbol:
            raise ResearchStrategyBacktestError("historical bar symbol mismatch")
        if previous is not None and bar.timestamp <= previous:
            raise ResearchStrategyBacktestError(
                "historical bars must be strictly chronological"
            )
        previous = bar.timestamp


def canonical_single_symbol_historical_material(
    data: HistoricalDataResult,
) -> tuple[str, ...]:
    """Return the frozen request/provider/ordered-OHLCV semantic material."""
    _validate_historical_data(data)
    request = data.request
    material: list[str] = [
        HISTORICAL_DATA_FINGERPRINT_VERSION,
        str(request.symbol),
        _timestamp(request.start, "request.start"),
        _timestamp(request.end, "request.end"),
        request.timeframe.value,
        request.adjustment.value,
        data.provider_name,
    ]
    for bar in data.bars:
        material.extend(
            (
                str(bar.symbol),
                _timestamp(bar.timestamp, "bar.timestamp"),
                _decimal(bar.open, "bar.open"),
                _decimal(bar.high, "bar.high"),
                _decimal(bar.low, "bar.low"),
                _decimal(bar.close, "bar.close"),
                str(bar.volume),
            )
        )
    return tuple(material)


def historical_data_fingerprint(data: HistoricalDataResult) -> UUID:
    """Return the deterministic UUID5 fingerprint of one supplied data result."""
    return _identity_material(
        RESEARCH_STRATEGY_BACKTEST_EVIDENCE_NAMESPACE,
        canonical_single_symbol_historical_material(data),
    )


def derive_backtest_run_id(
    definition_id: UUID,
    evaluation_policy_id: UUID,
    historical_data_fingerprint: UUID,
    *,
    fold_role: str = STANDALONE_FOLD_ROLE,
    fold_id: UUID | None = None,
) -> UUID:
    """Derive the 142-A standalone run ID and reserve explicit fold roles."""
    for value, name in (
        (definition_id, "definition_id"),
        (evaluation_policy_id, "evaluation_policy_id"),
        (historical_data_fingerprint, "historical_data_fingerprint"),
    ):
        if type(value) is not UUID:
            raise ResearchStrategyBacktestError(f"{name} must be exactly UUID")
    if type(fold_role) is not str or fold_role not in {
        item.value for item in _FoldRole
    }:
        raise ResearchStrategyBacktestError("fold_role is not supported")
    if fold_role == STANDALONE_FOLD_ROLE:
        if fold_id is not None:
            raise ResearchStrategyBacktestError("STANDALONE must not carry fold_id")
        values = (
            str(definition_id),
            str(evaluation_policy_id),
            str(historical_data_fingerprint),
            STANDALONE_FOLD_ROLE,
        )
    else:
        if type(fold_id) is not UUID:
            raise ResearchStrategyBacktestError(
                "TRAINING and TEST roles require an exact fold_id"
            )
        values = (
            str(definition_id),
            str(evaluation_policy_id),
            str(historical_data_fingerprint),
            str(fold_id),
            fold_role,
        )
    return _identity(
        RESEARCH_STRATEGY_BACKTEST_EVIDENCE_NAMESPACE,
        BACKTEST_RUN_IDENTITY_VERSION,
        values,
    )


class _SuppliedHistoricalDataProvider:
    """In-memory provider bound to one exact caller-supplied result."""

    def __init__(self, data: HistoricalDataResult) -> None:
        self._data = data

    def get_bars(self, request: HistoricalDataRequest) -> HistoricalDataResult:
        if type(request) is not HistoricalDataRequest or request != self._data.request:
            raise ResearchStrategyBacktestError(
                "provider request does not equal the supplied historical request"
            )
        return self._data


def build_backtest_config(
    evaluation_policy: ResearchStrategyEvaluationPolicy,
    run_id: UUID,
    data: HistoricalDataResult,
) -> BacktestConfig:
    """Build the unchanged engine config from every policy semantic."""
    if type(evaluation_policy) is not ResearchStrategyEvaluationPolicy:
        raise ResearchStrategyBacktestError("exact evaluation policy required")
    try:
        evaluation_policy.to_json()
    except ResearchStrategyDefinitionError as error:
        raise ResearchStrategyBacktestError(str(error)) from error
    if type(run_id) is not UUID:
        raise ResearchStrategyBacktestError("run_id must be exactly UUID")
    _validate_historical_data(data)
    return BacktestConfig(
        run_id=run_id,
        data_request=data.request,
        starting_cash=evaluation_policy.starting_cash,
        risk_limits=evaluation_policy.risk_limits,
        fixed_commission=evaluation_policy.fixed_commission,
        slippage_basis_points=evaluation_policy.slippage_basis_points,
        trading_enabled=evaluation_policy.trading_enabled,
        allow_missing_sessions=evaluation_policy.allow_missing_sessions,
    )


def _bar_material(bar: Bar) -> tuple[str, ...]:
    if type(bar) is not Bar:
        raise ResearchStrategyBacktestError("result contains a noncanonical Bar")
    return (
        str(bar.symbol),
        _timestamp(bar.timestamp, "bar.timestamp"),
        _decimal(bar.open, "bar.open"),
        _decimal(bar.high, "bar.high"),
        _decimal(bar.low, "bar.low"),
        _decimal(bar.close, "bar.close"),
        str(bar.volume),
    )


def _position_material(position: Position) -> tuple[str, ...]:
    if type(position) is not Position:
        raise ResearchStrategyBacktestError("result contains a noncanonical Position")
    return (
        str(position.symbol),
        _decimal(position.quantity, "position.quantity"),
        _decimal(position.average_cost, "position.average_cost"),
    )


def _proposal_material(proposal: TradeProposal) -> tuple[str, ...]:
    if type(proposal) is not TradeProposal:
        raise ResearchStrategyBacktestError("result contains a noncanonical proposal")
    return (
        str(proposal.proposal_id),
        str(proposal.symbol),
        proposal.side.value,
        _decimal(proposal.desired_quantity, "proposal.desired_quantity"),
        _timestamp(proposal.created_at, "proposal.created_at"),
        proposal.reason,
        _optional_decimal(proposal.confidence, "proposal.confidence"),
    )


def _risk_reason_material(reason: RiskReason) -> tuple[str, ...]:
    if type(reason) is not RiskReason:
        raise ResearchStrategyBacktestError(
            "result contains a noncanonical risk reason"
        )
    return (
        reason.code.value,
        reason.message,
        _optional_decimal(reason.observed, "risk_reason.observed"),
        _optional_decimal(reason.limit, "risk_reason.limit"),
    )


def _risk_decision_material(decision: RiskDecision) -> tuple[str, ...]:
    if type(decision) is not RiskDecision:
        raise ResearchStrategyBacktestError(
            "result contains a noncanonical risk decision"
        )
    material = [
        *_proposal_material(decision.proposal),
        decision.outcome.value,
        _decimal(decision.approved_quantity, "risk_decision.approved_quantity"),
        str(len(decision.reasons)),
    ]
    for reason in decision.reasons:
        material.extend(_risk_reason_material(reason))
    material.append(_timestamp(decision.evaluated_at, "risk_decision.evaluated_at"))
    return tuple(material)


def _order_request_material(request) -> tuple[str, ...]:  # type: ignore[no-untyped-def]
    return (
        str(request.order_id),
        str(request.symbol),
        request.side.value,
        request.order_type.value,
        _decimal(request.quantity, "order.quantity"),
        request.time_in_force.value,
        _timestamp(request.submitted_at, "order.submitted_at"),
        _optional_decimal(request.limit_price, "order.limit_price"),
    )


def _order_material(order: Order) -> tuple[str, ...]:
    if type(order) is not Order:
        raise ResearchStrategyBacktestError("result contains a noncanonical order")
    return (
        *_order_request_material(order.request),
        order.status.value,
        _decimal(order.filled_quantity, "order.filled_quantity"),
        _optional_decimal(order.average_fill_price, "order.average_fill_price"),
        _optional_text(order.rejection_reason, "order.rejection_reason"),
    )


def _fill_material(fill: OrderFill) -> tuple[str, ...]:
    if type(fill) is not OrderFill:
        raise ResearchStrategyBacktestError("result contains a noncanonical fill")
    return (
        str(fill.fill_id),
        str(fill.order_id),
        str(fill.symbol),
        fill.side.value,
        _decimal(fill.quantity, "fill.quantity"),
        _decimal(fill.price, "fill.price"),
        _decimal(fill.commission, "fill.commission"),
        _timestamp(fill.filled_at, "fill.filled_at"),
    )


def _event_material(event: OrderEvent) -> tuple[str, ...]:
    if type(event) is not OrderEvent:
        raise ResearchStrategyBacktestError(
            "result contains a noncanonical order event"
        )
    return (
        str(event.event_id),
        str(event.order_id),
        event.event_type.value,
        _timestamp(event.occurred_at, "order_event.occurred_at"),
        "none" if event.fill_id is None else str(event.fill_id),
        _optional_text(event.reason, "order_event.reason"),
    )


def _snapshot_material(snapshot: AccountSnapshot) -> tuple[str, ...]:
    if type(snapshot) is not AccountSnapshot:
        raise ResearchStrategyBacktestError(
            "result contains a noncanonical account snapshot"
        )
    return (
        _timestamp(snapshot.timestamp, "snapshot.timestamp"),
        _decimal(snapshot.cash, "snapshot.cash"),
        _decimal(snapshot.positions_market_value, "snapshot.positions_market_value"),
        _decimal(snapshot.equity, "snapshot.equity"),
        _decimal(snapshot.buying_power, "snapshot.buying_power"),
        _decimal(snapshot.realized_profit_loss, "snapshot.realized_profit_loss"),
        _decimal(snapshot.unrealized_profit_loss, "snapshot.unrealized_profit_loss"),
    )


def _step_material(step: BacktestStep) -> tuple[str, ...]:
    if type(step) is not BacktestStep:
        raise ResearchStrategyBacktestError("result contains a noncanonical step")
    material = [
        str(step.step_index),
        step.session.session_date.isoformat(),
        *_bar_material(step.bar),
        ("none",) if step.opening_fill is None else _fill_material(step.opening_fill),
        *_snapshot_material(step.account_snapshot),
        ("none",) if step.proposal is None else _proposal_material(step.proposal),
        (
            ("none",)
            if step.risk_decision is None
            else _risk_decision_material(step.risk_decision)
        ),
        (
            ("none",)
            if step.submitted_order is None
            else _order_material(step.submitted_order)
        ),
        "none" if step.unexecuted_reason is None else step.unexecuted_reason.value,
    ]
    flattened: list[str] = []
    for item in material:
        if isinstance(item, tuple):
            flattened.extend(item)
        else:
            flattened.append(item)
    return tuple(flattened)


def _request_material(request: HistoricalDataRequest) -> tuple[str, ...]:
    if type(request) is not HistoricalDataRequest:
        raise ResearchStrategyBacktestError("result request must be exact")
    return (
        str(request.symbol),
        _timestamp(request.start, "request.start"),
        _timestamp(request.end, "request.end"),
        request.timeframe.value,
        request.adjustment.value,
    )


def _risk_limits_material(limits: RiskLimits) -> tuple[str, ...]:
    if type(limits) is not RiskLimits:
        raise ResearchStrategyBacktestError("result risk limits must be exact")
    return (
        _decimal(limits.max_position_percent, "risk.max_position_percent"),
        _decimal(limits.max_total_exposure_percent, "risk.max_total_exposure_percent"),
        _optional_decimal(limits.max_order_notional, "risk.max_order_notional"),
        _optional_decimal(
            limits.max_new_position_percent, "risk.max_new_position_percent"
        ),
        _decimal(
            limits.minimum_cash_reserve_percent,
            "risk.minimum_cash_reserve_percent",
        ),
        "true" if limits.allow_fractional_shares else "false",
        _decimal(limits.fractional_increment, "risk.fractional_increment"),
        "true" if limits.allow_buying else "false",
        "true" if limits.allow_selling else "false",
        _decimal(limits.estimated_commission, "risk.estimated_commission"),
    )


def _config_material(config: BacktestConfig) -> tuple[str, ...]:
    if type(config) is not BacktestConfig:
        raise ResearchStrategyBacktestError("result config must be exact")
    return (
        str(config.run_id),
        *_request_material(config.data_request),
        _decimal(config.starting_cash, "config.starting_cash"),
        *_risk_limits_material(config.risk_limits),
        _decimal(config.fixed_commission, "config.fixed_commission"),
        _decimal(config.slippage_basis_points, "config.slippage_basis_points"),
        "true" if config.trading_enabled else "false",
        "true" if config.allow_missing_sessions else "false",
    )


def _validate_result_shape(result: BacktestResult) -> None:
    if type(result) is not BacktestResult:
        raise ResearchStrategyBacktestError("result must be exactly BacktestResult")
    if not isinstance(result.final_positions, Mapping):
        raise ResearchStrategyBacktestError("final_positions must be a mapping")
    for symbol, position in result.final_positions.items():
        if type(symbol) is not Symbol or type(position) is not Position:
            raise ResearchStrategyBacktestError("final positions must be exact values")
        if position.symbol != symbol:
            raise ResearchStrategyBacktestError("final position key mismatch")
    if not result.bars or len(result.bars) != len(result.steps):
        raise ResearchStrategyBacktestError("result bars and steps are inconsistent")


def _result_material(result: BacktestResult) -> tuple[str, ...]:
    _validate_result_shape(result)
    material: list[str] = [
        "result",
        *_config_material(result.config),
        result.provider_name,
    ]
    for name, values in (
        ("bars", result.bars),
        ("steps", result.steps),
        ("proposals", result.proposals),
        ("risk_decisions", result.risk_decisions),
        ("orders", result.orders),
        ("order_events", result.order_events),
        ("fills", result.fills),
        ("account_snapshots", result.account_snapshots),
        ("unexecuted_final_bar_proposals", result.unexecuted_final_bar_proposals),
    ):
        material.extend((name, str(len(values))))
        for value in values:
            if name == "bars":
                material.extend(_bar_material(value))
            elif name == "steps":
                material.extend(_step_material(value))
            elif name in {"proposals", "unexecuted_final_bar_proposals"}:
                material.extend(_proposal_material(value))
            elif name == "risk_decisions":
                material.extend(_risk_decision_material(value))
            elif name == "orders":
                material.extend(_order_material(value))
            elif name == "order_events":
                material.extend(_event_material(value))
            elif name == "fills":
                material.extend(_fill_material(value))
            else:
                material.extend(_snapshot_material(value))
    positions = sorted(result.final_positions.items(), key=lambda item: str(item[0]))
    material.extend(("final_positions", str(len(positions))))
    for symbol, position in positions:
        material.extend((str(symbol), *_position_material(position)))
    material.extend(
        (
            "final_equity",
            _decimal(result.final_equity, "result.final_equity"),
            "start_timestamp",
            _timestamp(result.start_timestamp, "result.start_timestamp"),
            "end_timestamp",
            _timestamp(result.end_timestamp, "result.end_timestamp"),
        )
    )
    return tuple(material)


def backtest_result_fingerprint(result: BacktestResult) -> UUID:
    """Return a deterministic UUID5 fingerprint of the complete result audit."""
    return _identity(
        RESEARCH_STRATEGY_BACKTEST_EVIDENCE_NAMESPACE,
        BACKTEST_RESULT_FINGERPRINT_VERSION,
        _result_material(result),
    )


@dataclass(frozen=True, slots=True)
class ResearchStrategyBacktestEvidence:
    """Canonical summary evidence for one completed standalone backtest."""

    schema: str = field(default=RESEARCH_STRATEGY_BACKTEST_EVIDENCE_SCHEMA, init=False)
    evidence_id: UUID = field(init=False)
    definition_id: UUID
    evaluation_policy_id: UUID
    evaluation_source_head: str
    evaluation_source_tree: str
    historical_data_fingerprint: UUID
    data_request_symbol: Symbol
    data_request_start: datetime
    data_request_end: datetime
    data_request_timeframe: Timeframe
    data_request_adjustment: AdjustmentType
    provider_name: str
    backtest_run_id: UUID
    backtest_result_fingerprint: UUID
    bar_count: int
    start_timestamp: datetime
    end_timestamp: datetime
    total_return: Decimal
    maximum_drawdown_percentage: Decimal
    final_equity: Decimal

    def __post_init__(self) -> None:
        _validate_evidence(self, check_identity=False)
        object.__setattr__(
            self,
            "evidence_id",
            _identity(
                RESEARCH_STRATEGY_BACKTEST_EVIDENCE_NAMESPACE,
                RESEARCH_STRATEGY_BACKTEST_EVIDENCE_IDENTITY_VERSION,
                _evidence_material(self),
            ),
        )

    def to_json(self) -> str:
        """Serialize compact sorted canonical evidence bytes."""
        _validate_evidence(self)
        return _json(
            {
                "schema": self.schema,
                "evidence_id": str(self.evidence_id),
                "definition_id": str(self.definition_id),
                "evaluation_policy_id": str(self.evaluation_policy_id),
                "evaluation_source_head": self.evaluation_source_head,
                "evaluation_source_tree": self.evaluation_source_tree,
                "historical_data_fingerprint": str(self.historical_data_fingerprint),
                "data_request_symbol": str(self.data_request_symbol),
                "data_request_start": _timestamp(
                    self.data_request_start, "data_request_start"
                ),
                "data_request_end": _timestamp(
                    self.data_request_end, "data_request_end"
                ),
                "data_request_timeframe": self.data_request_timeframe.value,
                "data_request_adjustment": self.data_request_adjustment.value,
                "provider_name": self.provider_name,
                "backtest_run_id": str(self.backtest_run_id),
                "backtest_result_fingerprint": str(self.backtest_result_fingerprint),
                "bar_count": self.bar_count,
                "start_timestamp": _timestamp(self.start_timestamp, "start_timestamp"),
                "end_timestamp": _timestamp(self.end_timestamp, "end_timestamp"),
                "total_return": _decimal(self.total_return, "total_return"),
                "maximum_drawdown_percentage": _decimal(
                    self.maximum_drawdown_percentage,
                    "maximum_drawdown_percentage",
                ),
                "final_equity": _decimal(self.final_equity, "final_equity"),
            }
        )

    @classmethod
    def from_json(cls, value: str) -> ResearchStrategyBacktestEvidence:
        """Parse self-consistent evidence only; never execute a backtest."""
        try:
            if cls is not ResearchStrategyBacktestEvidence or type(value) is not str:
                raise ResearchStrategyBacktestError("exact evidence JSON required")
            raw = json.loads(
                value,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
            root = _exact_fields(raw, _EVIDENCE_FIELDS)
            if root["schema"] != RESEARCH_STRATEGY_BACKTEST_EVIDENCE_SCHEMA:
                raise ResearchStrategyBacktestError("invalid evidence schema")
            symbol_text = root["data_request_symbol"]
            if type(symbol_text) is not str:
                raise ResearchStrategyBacktestError("data_request_symbol must be text")
            symbol = Symbol(symbol_text)
            if str(symbol) != symbol_text:
                raise ResearchStrategyBacktestError(
                    "data_request_symbol is not canonical"
                )
            timeframe = Timeframe(root["data_request_timeframe"])
            adjustment = AdjustmentType(root["data_request_adjustment"])
            result = cls(
                definition_id=_parse_uuid(root["definition_id"], "definition_id"),
                evaluation_policy_id=_parse_uuid(
                    root["evaluation_policy_id"], "evaluation_policy_id"
                ),
                evaluation_source_head=_source(
                    root["evaluation_source_head"], "evaluation_source_head"
                ),
                evaluation_source_tree=_source(
                    root["evaluation_source_tree"], "evaluation_source_tree"
                ),
                historical_data_fingerprint=_parse_uuid(
                    root["historical_data_fingerprint"],
                    "historical_data_fingerprint",
                ),
                data_request_symbol=symbol,
                data_request_start=_parse_timestamp(
                    root["data_request_start"], "data_request_start"
                ),
                data_request_end=_parse_timestamp(
                    root["data_request_end"], "data_request_end"
                ),
                data_request_timeframe=timeframe,
                data_request_adjustment=adjustment,
                provider_name=root["provider_name"],
                backtest_run_id=_parse_uuid(root["backtest_run_id"], "backtest_run_id"),
                backtest_result_fingerprint=_parse_uuid(
                    root["backtest_result_fingerprint"],
                    "backtest_result_fingerprint",
                ),
                bar_count=root["bar_count"],
                start_timestamp=_parse_timestamp(
                    root["start_timestamp"], "start_timestamp"
                ),
                end_timestamp=_parse_timestamp(root["end_timestamp"], "end_timestamp"),
                total_return=_parse_decimal(root["total_return"], "total_return"),
                maximum_drawdown_percentage=_parse_decimal(
                    root["maximum_drawdown_percentage"],
                    "maximum_drawdown_percentage",
                ),
                final_equity=_parse_decimal(root["final_equity"], "final_equity"),
            )
            if (
                _parse_uuid(root["evidence_id"], "evidence_id") != result.evidence_id
                or result.to_json() != value
            ):
                raise ResearchStrategyBacktestError(
                    "evidence identity or canonical bytes are inconsistent"
                )
            return result
        except (ArithmeticError, TypeError, UnicodeError, ValueError) as error:
            if isinstance(error, ResearchStrategyBacktestError):
                raise
            raise ResearchStrategyBacktestError(
                "invalid research backtest JSON"
            ) from None


def _evidence_material(evidence: ResearchStrategyBacktestEvidence) -> tuple[str, ...]:
    _validate_evidence(evidence, check_identity=False)
    return (
        evidence.schema,
        str(evidence.definition_id),
        str(evidence.evaluation_policy_id),
        evidence.evaluation_source_head,
        evidence.evaluation_source_tree,
        str(evidence.historical_data_fingerprint),
        str(evidence.data_request_symbol),
        _timestamp(evidence.data_request_start, "data_request_start"),
        _timestamp(evidence.data_request_end, "data_request_end"),
        evidence.data_request_timeframe.value,
        evidence.data_request_adjustment.value,
        evidence.provider_name,
        str(evidence.backtest_run_id),
        str(evidence.backtest_result_fingerprint),
        str(evidence.bar_count),
        _timestamp(evidence.start_timestamp, "start_timestamp"),
        _timestamp(evidence.end_timestamp, "end_timestamp"),
        _decimal(evidence.total_return, "total_return"),
        _decimal(
            evidence.maximum_drawdown_percentage,
            "maximum_drawdown_percentage",
        ),
        _decimal(evidence.final_equity, "final_equity"),
    )


def _validate_evidence(
    evidence: ResearchStrategyBacktestEvidence, *, check_identity: bool = True
) -> None:
    if type(evidence) is not ResearchStrategyBacktestEvidence:
        raise ResearchStrategyBacktestError(
            "evidence must be exactly ResearchStrategyBacktestEvidence"
        )
    if evidence.schema != RESEARCH_STRATEGY_BACKTEST_EVIDENCE_SCHEMA:
        raise ResearchStrategyBacktestError("evidence schema is fixed")
    for value, name in (
        (evidence.definition_id, "definition_id"),
        (evidence.evaluation_policy_id, "evaluation_policy_id"),
        (evidence.historical_data_fingerprint, "historical_data_fingerprint"),
        (evidence.backtest_run_id, "backtest_run_id"),
        (evidence.backtest_result_fingerprint, "backtest_result_fingerprint"),
    ):
        _uuid_text(value, name)
    _source(evidence.evaluation_source_head, "evaluation_source_head")
    _source(evidence.evaluation_source_tree, "evaluation_source_tree")
    if type(evidence.data_request_symbol) is not Symbol:
        raise ResearchStrategyBacktestError(
            "data_request_symbol must be exactly Symbol"
        )
    if type(evidence.data_request_timeframe) is not Timeframe:
        raise ResearchStrategyBacktestError("data_request_timeframe must be Timeframe")
    if type(evidence.data_request_adjustment) is not AdjustmentType:
        raise ResearchStrategyBacktestError(
            "data_request_adjustment must be AdjustmentType"
        )
    if evidence.data_request_timeframe is not Timeframe.DAY_1:
        raise ResearchStrategyBacktestError("only daily data is supported")
    if evidence.data_request_adjustment is not AdjustmentType.RAW:
        raise ResearchStrategyBacktestError("only RAW data is supported")
    if type(evidence.provider_name) is not str or not evidence.provider_name.strip():
        raise ResearchStrategyBacktestError("provider_name must be nonblank text")
    if (
        type(evidence.bar_count) is not int
        or isinstance(evidence.bar_count, bool)
        or evidence.bar_count <= 0
    ):
        raise ResearchStrategyBacktestError("bar_count must be a positive integer")
    for value, name in (
        (evidence.total_return, "total_return"),
        (evidence.maximum_drawdown_percentage, "maximum_drawdown_percentage"),
        (evidence.final_equity, "final_equity"),
    ):
        _decimal(value, name)
    for value, name in (
        (evidence.data_request_start, "data_request_start"),
        (evidence.data_request_end, "data_request_end"),
        (evidence.start_timestamp, "start_timestamp"),
        (evidence.end_timestamp, "end_timestamp"),
    ):
        _timestamp(value, name)
    if evidence.data_request_start >= evidence.data_request_end:
        raise ResearchStrategyBacktestError("data request interval is invalid")
    if evidence.start_timestamp > evidence.end_timestamp:
        raise ResearchStrategyBacktestError("backtest interval is invalid")
    if check_identity:
        expected = _identity(
            RESEARCH_STRATEGY_BACKTEST_EVIDENCE_NAMESPACE,
            RESEARCH_STRATEGY_BACKTEST_EVIDENCE_IDENTITY_VERSION,
            _evidence_material(evidence),
        )
        if type(evidence.evidence_id) is not UUID or evidence.evidence_id != expected:
            raise ResearchStrategyBacktestError("evidence_id is inconsistent")


@dataclass(frozen=True, slots=True)
class CompletedResearchStrategyBacktest:
    """Immutable in-memory carrier for exact completed engine/analyzer output."""

    definition: ResearchStrategyDefinition
    evaluation_policy: ResearchStrategyEvaluationPolicy
    historical_data: HistoricalDataResult
    result: BacktestResult
    performance_report: PerformanceReport
    evidence: ResearchStrategyBacktestEvidence

    def __post_init__(self) -> None:
        if type(self.definition) is not ResearchStrategyDefinition:
            raise ResearchStrategyBacktestError("exact research definition required")
        if type(self.evaluation_policy) is not ResearchStrategyEvaluationPolicy:
            raise ResearchStrategyBacktestError("exact evaluation policy required")
        if type(self.historical_data) is not HistoricalDataResult:
            raise ResearchStrategyBacktestError("exact historical data required")
        if type(self.result) is not BacktestResult:
            raise ResearchStrategyBacktestError("exact BacktestResult required")
        if type(self.performance_report) is not PerformanceReport:
            raise ResearchStrategyBacktestError("exact PerformanceReport required")
        if type(self.evidence) is not ResearchStrategyBacktestEvidence:
            raise ResearchStrategyBacktestError("exact evidence required")


def _new_evidence(
    definition: ResearchStrategyDefinition,
    evaluation_policy: ResearchStrategyEvaluationPolicy,
    data: HistoricalDataResult,
    result: BacktestResult,
    report: PerformanceReport,
    *,
    evaluation_source_head: str,
    evaluation_source_tree: str,
    fold_role: str = STANDALONE_FOLD_ROLE,
    fold_id: UUID | None = None,
) -> ResearchStrategyBacktestEvidence:
    if type(definition) is not ResearchStrategyDefinition:
        raise ResearchStrategyBacktestError("exact research definition required")
    if type(evaluation_policy) is not ResearchStrategyEvaluationPolicy:
        raise ResearchStrategyBacktestError("exact evaluation policy required")
    try:
        definition.to_json()
        evaluation_policy.to_json()
    except ResearchStrategyDefinitionError as error:
        raise ResearchStrategyBacktestError(str(error)) from error
    _validate_historical_data(data)
    _validate_result_shape(result)
    if type(report) is not PerformanceReport:
        raise ResearchStrategyBacktestError("report must be exactly PerformanceReport")
    _source(evaluation_source_head, "evaluation_source_head")
    _source(evaluation_source_tree, "evaluation_source_tree")
    if (
        result.config.data_request != data.request
        or result.provider_name != data.provider_name
    ):
        raise ResearchStrategyBacktestError("result does not match historical data")
    data_fp = historical_data_fingerprint(data)
    result_fp = backtest_result_fingerprint(result)
    expected_run_id = derive_backtest_run_id(
        definition.definition_id,
        evaluation_policy.policy_id,
        data_fp,
        fold_role=fold_role,
        fold_id=fold_id,
    )
    if result.config.run_id != expected_run_id:
        raise ResearchStrategyBacktestError("result run_id does not match evidence")
    return ResearchStrategyBacktestEvidence(
        definition_id=definition.definition_id,
        evaluation_policy_id=evaluation_policy.policy_id,
        evaluation_source_head=evaluation_source_head,
        evaluation_source_tree=evaluation_source_tree,
        historical_data_fingerprint=data_fp,
        data_request_symbol=data.request.symbol,
        data_request_start=data.request.start,
        data_request_end=data.request.end,
        data_request_timeframe=data.request.timeframe,
        data_request_adjustment=data.request.adjustment,
        provider_name=data.provider_name,
        backtest_run_id=expected_run_id,
        backtest_result_fingerprint=result_fp,
        bar_count=len(result.bars),
        start_timestamp=result.start_timestamp,
        end_timestamp=result.end_timestamp,
        total_return=report.total_return,
        maximum_drawdown_percentage=report.maximum_drawdown_percentage,
        final_equity=result.final_equity,
    )


def run_research_strategy_backtest(
    definition: ResearchStrategyDefinition,
    evaluation_policy: ResearchStrategyEvaluationPolicy,
    historical_data: HistoricalDataResult,
    *,
    evaluation_source_head: str,
    evaluation_source_tree: str,
    fold_role: str = STANDALONE_FOLD_ROLE,
    fold_id: UUID | None = None,
) -> CompletedResearchStrategyBacktest:
    """Run one deterministic offline evaluation.

    The default remains the accepted standalone 142-A behavior.  142-B uses
    the explicit fold role and fold identity to derive independent training
    and test run identities over the same offline machinery.
    """
    if type(definition) is not ResearchStrategyDefinition:
        raise ResearchStrategyBacktestError("exact research definition required")
    if type(evaluation_policy) is not ResearchStrategyEvaluationPolicy:
        raise ResearchStrategyBacktestError("exact evaluation policy required")
    try:
        definition.to_json()
        evaluation_policy.to_json()
    except ResearchStrategyDefinitionError as error:
        raise ResearchStrategyBacktestError(str(error)) from error
    _validate_historical_data(historical_data)
    if historical_data.request.symbol != definition.symbol:
        raise ResearchStrategyBacktestError(
            "historical request symbol must equal definition symbol"
        )
    data_fp = historical_data_fingerprint(historical_data)
    run_id = derive_backtest_run_id(
        definition.definition_id,
        evaluation_policy.policy_id,
        data_fp,
        fold_role=fold_role,
        fold_id=fold_id,
    )
    config = build_backtest_config(evaluation_policy, run_id, historical_data)
    provider = _SuppliedHistoricalDataProvider(historical_data)
    result = BacktestEngine(provider, NYSEMarketCalendar()).run(
        config, MovingAverageCrossoverStrategy(definition.strategy_config)
    )
    report = PerformanceAnalyzer().analyze(result)
    evidence = _new_evidence(
        definition,
        evaluation_policy,
        historical_data,
        result,
        report,
        evaluation_source_head=evaluation_source_head,
        evaluation_source_tree=evaluation_source_tree,
        fold_role=fold_role,
        fold_id=fold_id,
    )
    return CompletedResearchStrategyBacktest(
        definition=definition,
        evaluation_policy=evaluation_policy,
        historical_data=historical_data,
        result=result,
        performance_report=report,
        evidence=evidence,
    )


def verify_research_strategy_backtest(
    completed: CompletedResearchStrategyBacktest,
    historical_data: HistoricalDataResult | None = None,
    *,
    evaluation_source_head: str | None = None,
    evaluation_source_tree: str | None = None,
    fold_role: str = STANDALONE_FOLD_ROLE,
    fold_id: UUID | None = None,
) -> None:
    """Independently rerun and reconcile a completed evaluation exactly."""
    if type(completed) is not CompletedResearchStrategyBacktest:
        raise ResearchStrategyBacktestError("exact completed evaluation required")
    data = completed.historical_data if historical_data is None else historical_data
    head = (
        completed.evidence.evaluation_source_head
        if evaluation_source_head is None
        else evaluation_source_head
    )
    tree = (
        completed.evidence.evaluation_source_tree
        if evaluation_source_tree is None
        else evaluation_source_tree
    )
    recomputed = run_research_strategy_backtest(
        completed.definition,
        completed.evaluation_policy,
        data,
        evaluation_source_head=head,
        evaluation_source_tree=tree,
        fold_role=fold_role,
        fold_id=fold_id,
    )
    if (
        recomputed.result != completed.result
        or recomputed.performance_report != completed.performance_report
        or recomputed.evidence != completed.evidence
    ):
        raise ResearchStrategyBacktestError(
            "completed result, performance report, or evidence does not reconcile"
        )


def verify_research_strategy_backtest_evidence(
    evidence: ResearchStrategyBacktestEvidence,
    definition: ResearchStrategyDefinition,
    evaluation_policy: ResearchStrategyEvaluationPolicy,
    historical_data: HistoricalDataResult,
    result: BacktestResult,
    performance_report: PerformanceReport,
    *,
    evaluation_source_head: str,
    evaluation_source_tree: str,
    fold_role: str = STANDALONE_FOLD_ROLE,
    fold_id: UUID | None = None,
) -> None:
    """Verify independently supplied evidence and exact engine/analyzer output."""
    if type(evidence) is not ResearchStrategyBacktestEvidence:
        raise ResearchStrategyBacktestError("exact evidence required")
    expected = run_research_strategy_backtest(
        definition,
        evaluation_policy,
        historical_data,
        evaluation_source_head=evaluation_source_head,
        evaluation_source_tree=evaluation_source_tree,
        fold_role=fold_role,
        fold_id=fold_id,
    )
    if evidence != expected.evidence:
        raise ResearchStrategyBacktestError("evidence does not reconcile")
    if result != expected.result:
        raise ResearchStrategyBacktestError("BacktestResult does not reconcile")
    if performance_report != expected.performance_report:
        raise ResearchStrategyBacktestError("PerformanceReport does not reconcile")


build_research_strategy_backtest = run_research_strategy_backtest
verify_completed_research_strategy_backtest = verify_research_strategy_backtest


__all__ = [
    "BACKTEST_RESULT_FINGERPRINT_VERSION",
    "BACKTEST_RUN_IDENTITY_VERSION",
    "CompletedResearchStrategyBacktest",
    "HISTORICAL_DATA_FINGERPRINT_VERSION",
    "RESEARCH_STRATEGY_BACKTEST_EVIDENCE_IDENTITY_VERSION",
    "RESEARCH_STRATEGY_BACKTEST_EVIDENCE_NAMESPACE",
    "RESEARCH_STRATEGY_BACKTEST_EVIDENCE_SCHEMA",
    "STANDALONE_FOLD_ROLE",
    "ResearchStrategyBacktestError",
    "ResearchStrategyBacktestEvidence",
    "backtest_result_fingerprint",
    "build_backtest_config",
    "build_research_strategy_backtest",
    "canonical_single_symbol_historical_material",
    "derive_backtest_run_id",
    "historical_data_fingerprint",
    "run_research_strategy_backtest",
    "verify_completed_research_strategy_backtest",
    "verify_research_strategy_backtest",
    "verify_research_strategy_backtest_evidence",
]
