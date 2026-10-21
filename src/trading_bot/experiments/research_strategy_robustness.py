"""Pure Architecture-145 historical robustness and execution-stress evidence.

The models in this module are additive research evidence.  They do not acquire
data, execute a strategy, open a holdout, call a provider/broker, or create any
paper/live authority.  Callers supply completed predecessor evidence and the
explicit thresholds that were frozen before final-holdout evaluation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Context, Decimal, localcontext
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.domain import Symbol
from trading_bot.domain.enums import OrderSide
from trading_bot.strategies.moving_average import MovingAverageCrossoverConfig

RESEARCH_STRATEGY_ROBUSTNESS_POLICY_SCHEMA = (
    "research-strategy-robustness-qualification-policy/v1"
)
RESEARCH_STRATEGY_ROBUSTNESS_POLICY_NAMESPACE = UUID(
    "76bd7d2c-f0b5-5a42-97dc-8fc95d493f4a"
)
RESEARCH_STRATEGY_ROBUSTNESS_POLICY_IDENTITY_VERSION = (
    "research-strategy-robustness-qualification-policy-identity/v1"
)
RESEARCH_STRATEGY_ROBUSTNESS_PARTITION_SCHEMA = (
    "research-strategy-robustness-partition/v1"
)
RESEARCH_STRATEGY_ROBUSTNESS_PARTITION_NAMESPACE = UUID(
    "3a9857ae-9715-51a8-93d2-6b85fc2b90c2"
)
RESEARCH_STRATEGY_ROBUSTNESS_PARTITION_IDENTITY_VERSION = (
    "research-strategy-robustness-partition-identity/v1"
)
RESEARCH_EXECUTION_STRESS_SCENARIO_SCHEMA = "research-execution-stress-scenario/v1"
RESEARCH_EXECUTION_STRESS_SCENARIO_NAMESPACE = UUID(
    "db6d2c14-8dd8-5f07-9a25-84c8a6f8d9ae"
)
RESEARCH_EXECUTION_STRESS_SCENARIO_IDENTITY_VERSION = (
    "research-execution-stress-scenario-identity/v1"
)
RESEARCH_EXECUTION_STRESS_RESULT_SCHEMA = "research-execution-stress-result/v1"
RESEARCH_EXECUTION_STRESS_RESULT_NAMESPACE = UUID(
    "d6f5d0dc-f1de-58ec-9343-a69f24d9b00c"
)
RESEARCH_EXECUTION_STRESS_RESULT_IDENTITY_VERSION = (
    "research-execution-stress-result-identity/v1"
)
RESEARCH_STRATEGY_FINAL_HOLDOUT_ADMISSION_SCHEMA = (
    "research-strategy-final-holdout-admission/v1"
)
RESEARCH_STRATEGY_FINAL_HOLDOUT_ADMISSION_NAMESPACE = UUID(
    "23cb2f45-2ae3-5c69-a4c1-37e91961b10a"
)
RESEARCH_STRATEGY_FINAL_HOLDOUT_ADMISSION_IDENTITY_VERSION = (
    "research-strategy-final-holdout-admission-identity/v1"
)
RESEARCH_STRATEGY_ROBUSTNESS_EVIDENCE_SCHEMA = (
    "research-strategy-robustness-evidence/v1"
)
RESEARCH_STRATEGY_ROBUSTNESS_EVIDENCE_NAMESPACE = UUID(
    "18c0a5d8-0edb-59f2-9881-5b66d8bafc40"
)
RESEARCH_STRATEGY_ROBUSTNESS_EVIDENCE_IDENTITY_VERSION = (
    "research-strategy-robustness-evidence-identity/v1"
)
RESEARCH_STRATEGY_LIVE_CANARY_ELIGIBILITY_SCHEMA = (
    "research-strategy-live-canary-eligibility/v1"
)
RESEARCH_STRATEGY_LIVE_CANARY_ELIGIBILITY_NAMESPACE = UUID(
    "b3994b46-8cf8-5ea6-8b19-5665f04a0d32"
)
RESEARCH_STRATEGY_LIVE_CANARY_ELIGIBILITY_IDENTITY_VERSION = (
    "research-strategy-live-canary-eligibility-identity/v1"
)

# Descriptive aliases keep the long policy name available to callers without
# introducing a second identity vocabulary.
RESEARCH_STRATEGY_ROBUSTNESS_QUALIFICATION_POLICY_SCHEMA = (
    RESEARCH_STRATEGY_ROBUSTNESS_POLICY_SCHEMA
)
RESEARCH_STRATEGY_ROBUSTNESS_QUALIFICATION_POLICY_NAMESPACE = (
    RESEARCH_STRATEGY_ROBUSTNESS_POLICY_NAMESPACE
)
RESEARCH_STRATEGY_ROBUSTNESS_QUALIFICATION_POLICY_IDENTITY_VERSION = (
    RESEARCH_STRATEGY_ROBUSTNESS_POLICY_IDENTITY_VERSION
)

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_ZERO = Decimal("0")
_ONE = Decimal("1")
_SCENARIO_ORDER = (
    "HIGHER_COST",
    "DELAYED_FILL",
    "MISSED_FILL",
    "REJECTED_FILL",
    "PARTIAL_FILL",
)


class ResearchStrategyRobustnessError(ValueError):
    """Raised for malformed, unreconciled, or failing robustness evidence."""


class ResearchRobustnessPartitionRole(StrEnum):
    DEVELOPMENT = "DEVELOPMENT"
    WALK_FORWARD = "WALK_FORWARD"
    FINAL_HOLDOUT = "FINAL_HOLDOUT"


class ResearchExecutionStressKind(StrEnum):
    HIGHER_COST = "HIGHER_COST"
    DELAYED_FILL = "DELAYED_FILL"
    MISSED_FILL = "MISSED_FILL"
    REJECTED_FILL = "REJECTED_FILL"
    PARTIAL_FILL = "PARTIAL_FILL"


class ResearchExecutionStressDisposition(StrEnum):
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    MISSED = "MISSED"
    REJECTED = "REJECTED"


class ResearchStrategyLiveCanaryEligibilityStatus(StrEnum):
    LIVE_CANARY_ELIGIBLE = "LIVE_CANARY_ELIGIBLE"


def _frame(value: str) -> str:
    if type(value) is not str:
        raise ResearchStrategyRobustnessError("identity material must be text")
    try:
        return f"{len(value.encode('utf-8'))}:{value}"
    except UnicodeError:
        raise ResearchStrategyRobustnessError("identity text must be UTF-8") from None


def _identity(namespace: UUID, version: str, values: tuple[str, ...]) -> UUID:
    return uuid5(namespace, "".join(_frame(value) for value in (version, *values)))


def _uuid(value: object, name: str) -> UUID:
    if type(value) is not UUID:
        raise ResearchStrategyRobustnessError(f"{name} must be exactly UUID")
    return value


def _source(value: object, name: str) -> str:
    if type(value) is not str or _SHA40.fullmatch(value) is None:
        raise ResearchStrategyRobustnessError(
            f"{name} must be exact lowercase 40-hex text"
        )
    return value


def _text(value: object, name: str, *, allow_none: bool = False) -> str | None:
    if allow_none and value is None:
        return None
    if type(value) is not str or not value.strip():
        raise ResearchStrategyRobustnessError(f"{name} must be nonblank text")
    if value != value.strip() or len(value) > 256:
        raise ResearchStrategyRobustnessError(f"{name} has invalid canonical text")
    return value


def _decimal(value: object, name: str, *, nonnegative: bool = False) -> str:
    if type(value) is not Decimal or not value.is_finite():
        raise ResearchStrategyRobustnessError(f"{name} must be a finite Decimal")
    if nonnegative and value < _ZERO:
        raise ResearchStrategyRobustnessError(f"{name} must be nonnegative")
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return "0" if rendered in {"", "-0"} else rendered


def _parse_decimal(value: object, name: str, *, nonnegative: bool = False) -> Decimal:
    if type(value) is not str:
        raise ResearchStrategyRobustnessError(f"{name} must be canonical Decimal text")
    try:
        parsed = Decimal(value)
    except ArithmeticError:
        raise ResearchStrategyRobustnessError(f"{name} must be Decimal text") from None
    if _decimal(parsed, name, nonnegative=nonnegative) != value:
        raise ResearchStrategyRobustnessError(f"{name} is not canonical Decimal text")
    return parsed


def _exact_int(value: object, name: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ResearchStrategyRobustnessError(
            f"{name} must be an exact integer >= {minimum}"
        )
    return value


def _timestamp(value: object, name: str) -> str:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ResearchStrategyRobustnessError(f"{name} must be an aware datetime")
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _parse_timestamp(value: object, name: str) -> datetime:
    if type(value) is not str:
        raise ResearchStrategyRobustnessError(f"{name} must be canonical timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ResearchStrategyRobustnessError(
            f"{name} must be canonical timestamp"
        ) from None
    if _timestamp(parsed, name) != value:
        raise ResearchStrategyRobustnessError(f"{name} is not canonical timestamp")
    return parsed.astimezone(UTC)


def _parse_uuid(value: object, name: str) -> UUID:
    if type(value) is not str:
        raise ResearchStrategyRobustnessError(f"{name} must be canonical UUID text")
    try:
        parsed = UUID(value)
    except ValueError:
        raise ResearchStrategyRobustnessError(
            f"{name} must be canonical UUID text"
        ) from None
    if str(parsed) != value:
        raise ResearchStrategyRobustnessError(f"{name} must be canonical UUID text")
    return parsed


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _loads(value: object) -> object:
    if type(value) is not str:
        raise ResearchStrategyRobustnessError("canonical JSON text required")
    try:
        return json.loads(
            value,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (TypeError, ValueError, UnicodeError):
        raise ResearchStrategyRobustnessError("invalid canonical JSON") from None


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, item in pairs:
        if key in result:
            raise ResearchStrategyRobustnessError("duplicate JSON field")
        result[key] = item
    return result


def _reject_constant(value: str) -> None:
    raise ResearchStrategyRobustnessError(
        f"nonfinite JSON constant {value} is forbidden"
    )


def _fields(raw: object, expected: frozenset[str]) -> dict[str, object]:
    if type(raw) is not dict or set(raw) != expected:
        raise ResearchStrategyRobustnessError("exact canonical fields required")
    return raw


def _wire_config(config: MovingAverageCrossoverConfig) -> dict[str, object]:
    if type(config) is not MovingAverageCrossoverConfig:
        raise ResearchStrategyRobustnessError("strategy_config has an invalid type")
    return {
        "short_window": config.short_window,
        "long_window": config.long_window,
        "desired_quantity": _decimal(config.desired_quantity, "desired_quantity"),
    }


def _parse_config(raw: object) -> MovingAverageCrossoverConfig:
    values = _fields(
        raw, frozenset({"short_window", "long_window", "desired_quantity"})
    )
    try:
        short_window = _exact_int(values["short_window"], "short_window", minimum=1)
        long_window = _exact_int(values["long_window"], "long_window", minimum=2)
        quantity = _parse_decimal(values["desired_quantity"], "desired_quantity")
        return MovingAverageCrossoverConfig(short_window, long_window, quantity)
    except (TypeError, ValueError, ArithmeticError) as error:
        raise ResearchStrategyRobustnessError("invalid strategy_config") from error


def _wire_partition(
    partition: ResearchStrategyRobustnessPartition,
) -> dict[str, object]:
    return {
        "schema": partition.schema,
        "partition_id": str(partition.partition_id),
        "role": partition.role.value,
        "start": _timestamp(partition.start, "partition.start"),
        "end": _timestamp(partition.end, "partition.end"),
        "historical_data_fingerprint": str(partition.historical_data_fingerprint),
        "evidence_id": str(partition.evidence_id),
    }


@dataclass(frozen=True, slots=True)
class ResearchStrategyRobustnessPartition:
    role: ResearchRobustnessPartitionRole
    start: datetime
    end: datetime
    historical_data_fingerprint: UUID
    evidence_id: UUID
    schema: str = field(
        default=RESEARCH_STRATEGY_ROBUSTNESS_PARTITION_SCHEMA, init=False
    )
    partition_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        if type(self.role) is not ResearchRobustnessPartitionRole:
            raise ResearchStrategyRobustnessError("partition role has an invalid type")
        start = _parse_timestamp(
            _timestamp(self.start, "partition.start"), "partition.start"
        )
        end = _parse_timestamp(_timestamp(self.end, "partition.end"), "partition.end")
        if start >= end:
            raise ResearchStrategyRobustnessError(
                "partition interval must be increasing"
            )
        _uuid(self.historical_data_fingerprint, "historical_data_fingerprint")
        _uuid(self.evidence_id, "evidence_id")
        if self.schema != RESEARCH_STRATEGY_ROBUSTNESS_PARTITION_SCHEMA:
            raise ResearchStrategyRobustnessError("partition schema is fixed")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        object.__setattr__(
            self,
            "partition_id",
            _identity(
                RESEARCH_STRATEGY_ROBUSTNESS_PARTITION_NAMESPACE,
                RESEARCH_STRATEGY_ROBUSTNESS_PARTITION_IDENTITY_VERSION,
                (
                    self.schema,
                    self.role.value,
                    _timestamp(start, "partition.start"),
                    _timestamp(end, "partition.end"),
                    str(self.historical_data_fingerprint),
                    str(self.evidence_id),
                ),
            ),
        )

    def to_json(self) -> str:
        _validate_partition(self)
        return _json(_wire_partition(self))

    @classmethod
    def from_json(cls, value: str) -> ResearchStrategyRobustnessPartition:
        raw = _fields(_loads(value), frozenset(_wire_partition_fields()))
        try:
            result = cls(
                ResearchRobustnessPartitionRole(raw["role"]),
                _parse_timestamp(raw["start"], "partition.start"),
                _parse_timestamp(raw["end"], "partition.end"),
                _parse_uuid(
                    raw["historical_data_fingerprint"], "historical_data_fingerprint"
                ),
                _parse_uuid(raw["evidence_id"], "evidence_id"),
            )
            if _parse_uuid(raw["partition_id"], "partition_id") != result.partition_id:
                raise ResearchStrategyRobustnessError("partition identity mismatch")
            if result.to_json() != value:
                raise ResearchStrategyRobustnessError("noncanonical partition JSON")
            return result
        except (TypeError, ValueError, ArithmeticError, KeyError):
            raise ResearchStrategyRobustnessError("invalid partition JSON") from None


def _wire_partition_fields() -> tuple[str, ...]:
    return (
        "schema",
        "partition_id",
        "role",
        "start",
        "end",
        "historical_data_fingerprint",
        "evidence_id",
    )


def _validate_partition(value: ResearchStrategyRobustnessPartition) -> None:
    if type(value) is not ResearchStrategyRobustnessPartition:
        raise ResearchStrategyRobustnessError("exact robustness partition required")
    if value.schema != RESEARCH_STRATEGY_ROBUSTNESS_PARTITION_SCHEMA:
        raise ResearchStrategyRobustnessError("partition schema is fixed")
    expected = ResearchStrategyRobustnessPartition(
        value.role,
        value.start,
        value.end,
        value.historical_data_fingerprint,
        value.evidence_id,
    )
    if expected.partition_id != value.partition_id:
        raise ResearchStrategyRobustnessError("partition identity is inconsistent")


@dataclass(frozen=True, slots=True)
class ResearchExecutionStressScenario:
    scenario_name: str
    kind: ResearchExecutionStressKind
    slippage_basis_points: Decimal
    fixed_cost_per_fill: Decimal
    delay_bars: int
    fill_ratio: Decimal | None
    schema: str = field(default=RESEARCH_EXECUTION_STRESS_SCENARIO_SCHEMA, init=False)
    scenario_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        name = _text(self.scenario_name, "scenario_name")
        if type(self.kind) is not ResearchExecutionStressKind:
            raise ResearchStrategyRobustnessError("stress kind has an invalid type")
        _decimal(self.slippage_basis_points, "slippage_basis_points", nonnegative=True)
        if self.slippage_basis_points >= Decimal("10000"):
            raise ResearchStrategyRobustnessError("slippage_basis_points is too large")
        _decimal(self.fixed_cost_per_fill, "fixed_cost_per_fill", nonnegative=True)
        _exact_int(self.delay_bars, "delay_bars")
        if self.schema != RESEARCH_EXECUTION_STRESS_SCENARIO_SCHEMA:
            raise ResearchStrategyRobustnessError("stress scenario schema is fixed")
        if self.kind is ResearchExecutionStressKind.HIGHER_COST and not (
            self.slippage_basis_points > _ZERO or self.fixed_cost_per_fill > _ZERO
        ):
            raise ResearchStrategyRobustnessError(
                "higher-cost stress must degrade cost"
            )
        if (
            self.kind is ResearchExecutionStressKind.DELAYED_FILL
            and self.delay_bars < 1
        ):
            raise ResearchStrategyRobustnessError("delayed-fill stress requires delay")
        if (
            self.kind is not ResearchExecutionStressKind.DELAYED_FILL
            and self.delay_bars
        ):
            raise ResearchStrategyRobustnessError("only delayed-fill stress may delay")
        if self.kind is ResearchExecutionStressKind.PARTIAL_FILL:
            if type(self.fill_ratio) is not Decimal or not (
                _ZERO < self.fill_ratio < _ONE
            ):
                raise ResearchStrategyRobustnessError(
                    "partial-fill stress requires a ratio between zero and one"
                )
        elif self.fill_ratio is not None:
            raise ResearchStrategyRobustnessError(
                "only partial-fill stress may specify a fill ratio"
            )
        object.__setattr__(self, "scenario_name", name)
        object.__setattr__(
            self,
            "scenario_id",
            _identity(
                RESEARCH_EXECUTION_STRESS_SCENARIO_NAMESPACE,
                RESEARCH_EXECUTION_STRESS_SCENARIO_IDENTITY_VERSION,
                (
                    self.schema,
                    name,
                    self.kind.value,
                    _decimal(self.slippage_basis_points, "slippage_basis_points"),
                    _decimal(self.fixed_cost_per_fill, "fixed_cost_per_fill"),
                    str(self.delay_bars),
                    "none"
                    if self.fill_ratio is None
                    else _decimal(self.fill_ratio, "fill_ratio"),
                ),
            ),
        )

    def to_json(self) -> str:
        _validate_scenario(self)
        return _json(
            {
                "schema": self.schema,
                "scenario_id": str(self.scenario_id),
                "scenario_name": self.scenario_name,
                "kind": self.kind.value,
                "slippage_basis_points": _decimal(
                    self.slippage_basis_points, "slippage_basis_points"
                ),
                "fixed_cost_per_fill": _decimal(
                    self.fixed_cost_per_fill, "fixed_cost_per_fill"
                ),
                "delay_bars": self.delay_bars,
                "fill_ratio": None
                if self.fill_ratio is None
                else _decimal(self.fill_ratio, "fill_ratio"),
            }
        )

    @classmethod
    def from_json(cls, value: str) -> ResearchExecutionStressScenario:
        raw = _fields(_loads(value), frozenset(_SCENARIO_FIELDS))
        try:
            ratio = (
                None
                if raw["fill_ratio"] is None
                else _parse_decimal(raw["fill_ratio"], "fill_ratio")
            )
            result = cls(
                raw["scenario_name"],
                ResearchExecutionStressKind(raw["kind"]),
                _parse_decimal(
                    raw["slippage_basis_points"],
                    "slippage_basis_points",
                    nonnegative=True,
                ),
                _parse_decimal(
                    raw["fixed_cost_per_fill"], "fixed_cost_per_fill", nonnegative=True
                ),
                raw["delay_bars"],
                ratio,
            )
            if _parse_uuid(raw["scenario_id"], "scenario_id") != result.scenario_id:
                raise ResearchStrategyRobustnessError(
                    "stress scenario identity mismatch"
                )
            if result.to_json() != value:
                raise ResearchStrategyRobustnessError(
                    "noncanonical stress scenario JSON"
                )
            return result
        except (TypeError, ValueError, ArithmeticError, KeyError):
            raise ResearchStrategyRobustnessError(
                "invalid stress scenario JSON"
            ) from None


_SCENARIO_FIELDS = (
    "schema",
    "scenario_id",
    "scenario_name",
    "kind",
    "slippage_basis_points",
    "fixed_cost_per_fill",
    "delay_bars",
    "fill_ratio",
)


def _validate_scenario(value: ResearchExecutionStressScenario) -> None:
    if type(value) is not ResearchExecutionStressScenario:
        raise ResearchStrategyRobustnessError("exact stress scenario required")
    expected = ResearchExecutionStressScenario(
        value.scenario_name,
        value.kind,
        value.slippage_basis_points,
        value.fixed_cost_per_fill,
        value.delay_bars,
        value.fill_ratio,
    )
    if expected.scenario_id != value.scenario_id:
        raise ResearchStrategyRobustnessError(
            "stress scenario identity is inconsistent"
        )


@dataclass(frozen=True, slots=True)
class ResearchExecutionStressOrder:
    order_id: UUID
    symbol: Symbol
    side: OrderSide
    quantity: Decimal
    requested_price: Decimal
    delayed_execution_price: Decimal
    mark_price: Decimal

    def __post_init__(self) -> None:
        _uuid(self.order_id, "order_id")
        if type(self.symbol) is not Symbol:
            raise ResearchStrategyRobustnessError("order symbol has an invalid type")
        if type(self.side) is not OrderSide:
            raise ResearchStrategyRobustnessError("order side has an invalid type")
        _decimal(self.quantity, "quantity", nonnegative=True)
        _decimal(self.requested_price, "requested_price", nonnegative=True)
        _decimal(
            self.delayed_execution_price, "delayed_execution_price", nonnegative=True
        )
        _decimal(self.mark_price, "mark_price", nonnegative=True)
        if self.quantity <= _ZERO or self.requested_price <= _ZERO:
            raise ResearchStrategyRobustnessError(
                "stress orders require positive size/price"
            )
        if self.delayed_execution_price <= _ZERO or self.mark_price <= _ZERO:
            raise ResearchStrategyRobustnessError(
                "stress orders require positive marks"
            )


@dataclass(frozen=True, slots=True)
class ResearchExecutionStressOrderResult:
    order_id: UUID
    disposition: ResearchExecutionStressDisposition
    requested_quantity: Decimal
    filled_quantity: Decimal
    execution_price: Decimal | None
    commission: Decimal
    cash_effect: Decimal
    reason: str | None = None

    def __post_init__(self) -> None:
        _uuid(self.order_id, "order_id")
        if type(self.disposition) is not ResearchExecutionStressDisposition:
            raise ResearchStrategyRobustnessError(
                "stress disposition has an invalid type"
            )
        _decimal(self.requested_quantity, "requested_quantity", nonnegative=True)
        _decimal(self.filled_quantity, "filled_quantity", nonnegative=True)
        if (
            self.filled_quantity < _ZERO
            or self.filled_quantity > self.requested_quantity
        ):
            raise ResearchStrategyRobustnessError("filled quantity is outside request")
        if self.disposition is ResearchExecutionStressDisposition.FILLED and (
            self.filled_quantity != self.requested_quantity
        ):
            raise ResearchStrategyRobustnessError(
                "filled disposition has partial quantity"
            )
        if (
            self.disposition is ResearchExecutionStressDisposition.PARTIALLY_FILLED
            and not (_ZERO < self.filled_quantity < self.requested_quantity)
        ):
            raise ResearchStrategyRobustnessError(
                "partial disposition has invalid quantity"
            )
        if (
            self.disposition
            in {
                ResearchExecutionStressDisposition.MISSED,
                ResearchExecutionStressDisposition.REJECTED,
            }
            and self.filled_quantity != _ZERO
        ):
            raise ResearchStrategyRobustnessError("unfilled disposition has a fill")
        if self.execution_price is not None:
            _decimal(self.execution_price, "execution_price", nonnegative=True)
            if self.execution_price <= _ZERO:
                raise ResearchStrategyRobustnessError(
                    "execution price must be positive"
                )
        elif self.filled_quantity:
            raise ResearchStrategyRobustnessError(
                "filled result requires execution price"
            )
        _decimal(self.commission, "commission", nonnegative=True)
        _decimal(self.cash_effect, "cash_effect")
        if self.reason is not None:
            _text(self.reason, "reason")


@dataclass(frozen=True, slots=True)
class ResearchExecutionStressPosition:
    symbol: Symbol
    quantity: Decimal
    average_cost: Decimal
    mark_price: Decimal

    def __post_init__(self) -> None:
        if type(self.symbol) is not Symbol:
            raise ResearchStrategyRobustnessError("position symbol has an invalid type")
        _decimal(self.quantity, "position.quantity", nonnegative=True)
        _decimal(self.average_cost, "position.average_cost", nonnegative=True)
        _decimal(self.mark_price, "position.mark_price", nonnegative=True)
        if (
            self.quantity <= _ZERO
            or self.average_cost <= _ZERO
            or self.mark_price <= _ZERO
        ):
            raise ResearchStrategyRobustnessError("positions require positive values")


@dataclass(frozen=True, slots=True)
class ResearchExecutionStressReconciliation:
    starting_cash: Decimal
    ending_cash: Decimal
    positions: tuple[ResearchExecutionStressPosition, ...]
    ending_equity: Decimal
    filled_order_count: int
    partial_fill_order_count: int
    missed_order_count: int
    rejected_order_count: int
    total_filled_quantity: Decimal
    total_transaction_cost: Decimal

    def __post_init__(self) -> None:
        _decimal(self.starting_cash, "starting_cash", nonnegative=True)
        _decimal(self.ending_cash, "ending_cash")
        _decimal(self.ending_equity, "ending_equity")
        if self.starting_cash <= _ZERO:
            raise ResearchStrategyRobustnessError("starting_cash must be positive")
        if type(self.positions) is not tuple or not all(
            type(item) is ResearchExecutionStressPosition for item in self.positions
        ):
            raise ResearchStrategyRobustnessError("positions must be an exact tuple")
        symbols = tuple(item.symbol for item in self.positions)
        if len(set(symbols)) != len(symbols):
            raise ResearchStrategyRobustnessError("positions must have unique symbols")
        for name in (
            "filled_order_count",
            "partial_fill_order_count",
            "missed_order_count",
            "rejected_order_count",
        ):
            _exact_int(getattr(self, name), name)
        _decimal(self.total_filled_quantity, "total_filled_quantity", nonnegative=True)
        _decimal(
            self.total_transaction_cost, "total_transaction_cost", nonnegative=True
        )
        if self.ending_cash < _ZERO:
            raise ResearchStrategyRobustnessError("ending cash cannot be negative")


@dataclass(frozen=True, slots=True)
class ResearchExecutionStressResult:
    scenario: ResearchExecutionStressScenario
    starting_cash: Decimal
    orders: tuple[ResearchExecutionStressOrder, ...]
    order_results: tuple[ResearchExecutionStressOrderResult, ...]
    reconciliation: ResearchExecutionStressReconciliation
    schema: str = field(default=RESEARCH_EXECUTION_STRESS_RESULT_SCHEMA, init=False)
    result_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        _validate_scenario(self.scenario)
        _decimal(self.starting_cash, "starting_cash", nonnegative=True)
        if self.starting_cash <= _ZERO:
            raise ResearchStrategyRobustnessError("starting_cash must be positive")
        if type(self.orders) is not tuple or not self.orders:
            raise ResearchStrategyRobustnessError(
                "stress orders must be nonempty tuple"
            )
        if not all(type(item) is ResearchExecutionStressOrder for item in self.orders):
            raise ResearchStrategyRobustnessError("stress orders have invalid types")
        if type(self.order_results) is not tuple or len(self.order_results) != len(
            self.orders
        ):
            raise ResearchStrategyRobustnessError(
                "stress results must cover every order"
            )
        if not all(
            type(item) is ResearchExecutionStressOrderResult
            for item in self.order_results
        ):
            raise ResearchStrategyRobustnessError(
                "stress order results have invalid types"
            )
        if tuple(item.order_id for item in self.orders) != tuple(
            item.order_id for item in self.order_results
        ):
            raise ResearchStrategyRobustnessError(
                "stress order result order is not preserved"
            )
        if len({item.order_id for item in self.orders}) != len(self.orders):
            raise ResearchStrategyRobustnessError("stress order IDs must be unique")
        if type(self.reconciliation) is not ResearchExecutionStressReconciliation:
            raise ResearchStrategyRobustnessError(
                "exact stress reconciliation required"
            )
        if self.schema != RESEARCH_EXECUTION_STRESS_RESULT_SCHEMA:
            raise ResearchStrategyRobustnessError("stress result schema is fixed")
        object.__setattr__(
            self,
            "result_id",
            _identity(
                RESEARCH_EXECUTION_STRESS_RESULT_NAMESPACE,
                RESEARCH_EXECUTION_STRESS_RESULT_IDENTITY_VERSION,
                _stress_result_material(self),
            ),
        )

    def to_json(self) -> str:
        verify_research_execution_stress_result(self)
        return _json(_wire_stress_result(self))

    @classmethod
    def from_json(cls, value: str) -> ResearchExecutionStressResult:
        raw = _fields(_loads(value), _STRESS_RESULT_FIELDS)
        try:
            result = _parse_stress_result(raw)
            if _parse_uuid(raw["result_id"], "result_id") != result.result_id:
                raise ResearchStrategyRobustnessError("stress result identity mismatch")
            if result.to_json() != value:
                raise ResearchStrategyRobustnessError("noncanonical stress result JSON")
            return result
        except (TypeError, ValueError, ArithmeticError, KeyError):
            raise ResearchStrategyRobustnessError(
                "invalid stress result JSON"
            ) from None


_STRESS_ORDER_FIELDS = frozenset(
    {
        "order_id",
        "symbol",
        "side",
        "quantity",
        "requested_price",
        "delayed_execution_price",
        "mark_price",
    }
)
_STRESS_ORDER_RESULT_FIELDS = frozenset(
    {
        "order_id",
        "disposition",
        "requested_quantity",
        "filled_quantity",
        "execution_price",
        "commission",
        "cash_effect",
        "reason",
    }
)
_STRESS_POSITION_FIELDS = frozenset(
    {"symbol", "quantity", "average_cost", "mark_price"}
)
_STRESS_RECONCILIATION_FIELDS = frozenset(
    {
        "starting_cash",
        "ending_cash",
        "positions",
        "ending_equity",
        "filled_order_count",
        "partial_fill_order_count",
        "missed_order_count",
        "rejected_order_count",
        "total_filled_quantity",
        "total_transaction_cost",
    }
)
_STRESS_RESULT_FIELDS = frozenset(
    {
        "schema",
        "result_id",
        "scenario",
        "starting_cash",
        "orders",
        "order_results",
        "reconciliation",
    }
)


def _parse_stress_order(raw: object) -> ResearchExecutionStressOrder:
    values = _fields(raw, _STRESS_ORDER_FIELDS)
    return ResearchExecutionStressOrder(
        _parse_uuid(values["order_id"], "order_id"),
        Symbol(values["symbol"]),
        OrderSide(values["side"]),
        _parse_decimal(values["quantity"], "quantity", nonnegative=True),
        _parse_decimal(values["requested_price"], "requested_price", nonnegative=True),
        _parse_decimal(
            values["delayed_execution_price"],
            "delayed_execution_price",
            nonnegative=True,
        ),
        _parse_decimal(values["mark_price"], "mark_price", nonnegative=True),
    )


def _parse_stress_order_result(raw: object) -> ResearchExecutionStressOrderResult:
    values = _fields(raw, _STRESS_ORDER_RESULT_FIELDS)
    return ResearchExecutionStressOrderResult(
        _parse_uuid(values["order_id"], "order_id"),
        ResearchExecutionStressDisposition(values["disposition"]),
        _parse_decimal(
            values["requested_quantity"], "requested_quantity", nonnegative=True
        ),
        _parse_decimal(values["filled_quantity"], "filled_quantity", nonnegative=True),
        None
        if values["execution_price"] is None
        else _parse_decimal(
            values["execution_price"], "execution_price", nonnegative=True
        ),
        _parse_decimal(values["commission"], "commission", nonnegative=True),
        _parse_decimal(values["cash_effect"], "cash_effect"),
        _text(values["reason"], "reason", allow_none=True),
    )


def _parse_stress_reconciliation(raw: object) -> ResearchExecutionStressReconciliation:
    values = _fields(raw, _STRESS_RECONCILIATION_FIELDS)
    positions = tuple(
        ResearchExecutionStressPosition(
            Symbol(item["symbol"]),
            _parse_decimal(item["quantity"], "position.quantity", nonnegative=True),
            _parse_decimal(
                item["average_cost"], "position.average_cost", nonnegative=True
            ),
            _parse_decimal(item["mark_price"], "position.mark_price", nonnegative=True),
        )
        for item in (
            _fields(item, _STRESS_POSITION_FIELDS) for item in values["positions"]
        )
    )
    return ResearchExecutionStressReconciliation(
        _parse_decimal(values["starting_cash"], "starting_cash", nonnegative=True),
        _parse_decimal(values["ending_cash"], "ending_cash"),
        positions,
        _parse_decimal(values["ending_equity"], "ending_equity"),
        _exact_int(values["filled_order_count"], "filled_order_count"),
        _exact_int(values["partial_fill_order_count"], "partial_fill_order_count"),
        _exact_int(values["missed_order_count"], "missed_order_count"),
        _exact_int(values["rejected_order_count"], "rejected_order_count"),
        _parse_decimal(
            values["total_filled_quantity"], "total_filled_quantity", nonnegative=True
        ),
        _parse_decimal(
            values["total_transaction_cost"], "total_transaction_cost", nonnegative=True
        ),
    )


def _parse_stress_result(raw: dict[str, object]) -> ResearchExecutionStressResult:
    if raw["schema"] != RESEARCH_EXECUTION_STRESS_RESULT_SCHEMA:
        raise ResearchStrategyRobustnessError("stress result schema is fixed")
    return ResearchExecutionStressResult(
        ResearchExecutionStressScenario.from_json(_json(raw["scenario"])),
        _parse_decimal(raw["starting_cash"], "starting_cash", nonnegative=True),
        tuple(_parse_stress_order(item) for item in raw["orders"]),
        tuple(_parse_stress_order_result(item) for item in raw["order_results"]),
        _parse_stress_reconciliation(raw["reconciliation"]),
    )


def _stress_result_material(value: ResearchExecutionStressResult) -> tuple[str, ...]:
    material = [
        value.schema,
        str(value.scenario.scenario_id),
        _decimal(value.starting_cash, "starting_cash"),
    ]
    for order, result in zip(value.orders, value.order_results, strict=True):
        material.extend(
            (
                str(order.order_id),
                str(order.symbol),
                order.side.value,
                _decimal(order.quantity, "quantity"),
                _decimal(order.requested_price, "requested_price"),
                _decimal(order.delayed_execution_price, "delayed_execution_price"),
                _decimal(order.mark_price, "mark_price"),
                result.disposition.value,
                _decimal(result.filled_quantity, "filled_quantity"),
                "none"
                if result.execution_price is None
                else _decimal(result.execution_price, "execution_price"),
                _decimal(result.commission, "commission"),
                _decimal(result.cash_effect, "cash_effect"),
                "none" if result.reason is None else result.reason,
            )
        )
    reconciliation = value.reconciliation
    material.extend(
        (
            _decimal(reconciliation.ending_cash, "ending_cash"),
            _decimal(reconciliation.ending_equity, "ending_equity"),
            str(reconciliation.filled_order_count),
            str(reconciliation.partial_fill_order_count),
            str(reconciliation.missed_order_count),
            str(reconciliation.rejected_order_count),
            _decimal(reconciliation.total_filled_quantity, "total_filled_quantity"),
            _decimal(reconciliation.total_transaction_cost, "total_transaction_cost"),
        )
    )
    for position in reconciliation.positions:
        material.extend(
            (
                str(position.symbol),
                _decimal(position.quantity, "position.quantity"),
                _decimal(position.average_cost, "position.average_cost"),
                _decimal(position.mark_price, "position.mark_price"),
            )
        )
    return tuple(material)


def _stress_precision(values: tuple[Decimal, ...]) -> int:
    return max(100, sum(len(item.as_tuple().digits) for item in values) + 32)


def _stress_price(price: Decimal, side: OrderSide, basis_points: Decimal) -> Decimal:
    with localcontext(Context(prec=_stress_precision((price, basis_points)))):
        adjustment = basis_points / Decimal("10000")
        return price * (
            (_ONE + adjustment) if side is OrderSide.BUY else (_ONE - adjustment)
        )


def simulate_research_execution_stress(
    scenario: ResearchExecutionStressScenario,
    orders: tuple[ResearchExecutionStressOrder, ...],
    *,
    starting_cash: Decimal,
) -> ResearchExecutionStressResult:
    """Run one deterministic in-memory stress scenario with no external effects."""
    _validate_scenario(scenario)
    if type(orders) is not tuple or not orders:
        raise ResearchStrategyRobustnessError("orders must be a nonempty exact tuple")
    if len({item.order_id for item in orders}) != len(orders):
        raise ResearchStrategyRobustnessError("stress order IDs must be unique")
    for item in orders:
        if type(item) is not ResearchExecutionStressOrder:
            raise ResearchStrategyRobustnessError("exact stress orders required")
    _decimal(starting_cash, "starting_cash", nonnegative=True)
    if starting_cash <= _ZERO:
        raise ResearchStrategyRobustnessError("starting_cash must be positive")

    cash = starting_cash
    positions: dict[Symbol, list[Decimal]] = {}
    marks: dict[Symbol, Decimal] = {}
    results: list[ResearchExecutionStressOrderResult] = []
    for order in orders:
        existing_mark = marks.setdefault(order.symbol, order.mark_price)
        if existing_mark != order.mark_price:
            raise ResearchStrategyRobustnessError(
                "symbol mark price changed in scenario"
            )
        disposition = ResearchExecutionStressDisposition.FILLED
        reason: str | None = None
        quantity = order.quantity
        if scenario.kind is ResearchExecutionStressKind.MISSED_FILL:
            disposition = ResearchExecutionStressDisposition.MISSED
            quantity = _ZERO
            reason = "MISSED_BY_SCENARIO"
        elif scenario.kind is ResearchExecutionStressKind.REJECTED_FILL:
            disposition = ResearchExecutionStressDisposition.REJECTED
            quantity = _ZERO
            reason = "REJECTED_BY_SCENARIO"
        elif scenario.kind is ResearchExecutionStressKind.PARTIAL_FILL:
            with localcontext(
                Context(
                    prec=_stress_precision(
                        (order.quantity, scenario.fill_ratio or _ZERO)
                    )
                )
            ):
                quantity = order.quantity * (scenario.fill_ratio or _ZERO)
            disposition = ResearchExecutionStressDisposition.PARTIALLY_FILLED
        price = (
            order.delayed_execution_price
            if scenario.delay_bars
            else order.requested_price
        )
        price = _stress_price(price, order.side, scenario.slippage_basis_points)
        commission = _ZERO
        cash_effect = _ZERO
        if quantity:
            with localcontext(
                Context(
                    prec=_stress_precision(
                        (quantity, price, scenario.fixed_cost_per_fill)
                    )
                )
            ):
                gross = quantity * price
                commission = scenario.fixed_cost_per_fill
                cash_effect = (
                    -(gross + commission)
                    if order.side is OrderSide.BUY
                    else gross - commission
                )
            held = positions.get(order.symbol, [_ZERO, price])[0]
            if order.side is OrderSide.BUY and cash + cash_effect < _ZERO:
                disposition = ResearchExecutionStressDisposition.REJECTED
                reason = "INSUFFICIENT_CASH"
                quantity = _ZERO
                commission = _ZERO
                cash_effect = _ZERO
            elif order.side is OrderSide.SELL and held < quantity:
                disposition = ResearchExecutionStressDisposition.REJECTED
                reason = "INSUFFICIENT_POSITION"
                quantity = _ZERO
                commission = _ZERO
                cash_effect = _ZERO
        if quantity:
            cash += cash_effect
            if order.side is OrderSide.BUY:
                old_quantity, old_cost = positions.get(order.symbol, [_ZERO, price])
                with localcontext(
                    Context(
                        prec=_stress_precision(
                            (old_quantity, old_cost, quantity, price)
                        )
                    )
                ):
                    total_quantity = old_quantity + quantity
                    average_cost = (
                        (old_quantity * old_cost) + (quantity * price)
                    ) / total_quantity
                positions[order.symbol] = [total_quantity, average_cost]
            else:
                old_quantity, old_cost = positions[order.symbol]
                remaining = old_quantity - quantity
                if remaining:
                    positions[order.symbol] = [remaining, old_cost]
                else:
                    del positions[order.symbol]
        elif disposition is ResearchExecutionStressDisposition.PARTIALLY_FILLED:
            raise ResearchStrategyRobustnessError("partial scenario produced no fill")
        results.append(
            ResearchExecutionStressOrderResult(
                order.order_id,
                disposition,
                order.quantity,
                quantity,
                price if quantity else None,
                commission,
                cash_effect,
                reason,
            )
        )
    position_models = tuple(
        ResearchExecutionStressPosition(symbol, values[0], values[1], marks[symbol])
        for symbol, values in positions.items()
    )
    with localcontext(
        Context(
            prec=_stress_precision(
                (cash, *(item.mark_price for item in position_models))
            )
        )
    ):
        equity = cash + sum(
            (item.quantity * item.mark_price for item in position_models), _ZERO
        )
    reconciliation = ResearchExecutionStressReconciliation(
        starting_cash,
        cash,
        position_models,
        equity,
        sum(
            item.disposition is ResearchExecutionStressDisposition.FILLED
            for item in results
        ),
        sum(
            item.disposition is ResearchExecutionStressDisposition.PARTIALLY_FILLED
            for item in results
        ),
        sum(
            item.disposition is ResearchExecutionStressDisposition.MISSED
            for item in results
        ),
        sum(
            item.disposition is ResearchExecutionStressDisposition.REJECTED
            for item in results
        ),
        sum((item.filled_quantity for item in results), _ZERO),
        sum((item.commission for item in results), _ZERO),
    )
    return ResearchExecutionStressResult(
        scenario, starting_cash, orders, tuple(results), reconciliation
    )


def verify_research_execution_stress_result(
    result: ResearchExecutionStressResult,
) -> None:
    if type(result) is not ResearchExecutionStressResult:
        raise ResearchStrategyRobustnessError("exact stress result required")
    expected = simulate_research_execution_stress(
        result.scenario, result.orders, starting_cash=result.starting_cash
    )
    if expected != result:
        raise ResearchStrategyRobustnessError(
            "stress result reconciliation does not match"
        )


@dataclass(frozen=True, slots=True)
class ResearchStrategyRobustnessQualificationPolicy:
    candidate_id: UUID
    strategy_definition_id: UUID
    strategy_source_head: str
    strategy_source_tree: str
    strategy_id: str
    strategy_version: str
    symbol: Symbol
    strategy_config: MovingAverageCrossoverConfig
    historical_data_fingerprint: UUID
    development_partition: ResearchStrategyRobustnessPartition
    walk_forward_partition: ResearchStrategyRobustnessPartition
    final_holdout_partition: ResearchStrategyRobustnessPartition
    minimum_completed_trade_count: int
    maximum_drawdown_percentage: Decimal
    minimum_net_return: Decimal
    minimum_walk_forward_fold_count: int
    minimum_walk_forward_pass_rate: Decimal
    minimum_stability_pass_rate: Decimal
    maximum_stability_range: Decimal
    maximum_stability_adjacent_change: Decimal
    minimum_sensitivity_neighborhood_count: int
    minimum_sensitivity_pass_count: int
    maximum_sensitivity_return_spread: Decimal
    execution_stress_suite: tuple[ResearchExecutionStressScenario, ...]
    benchmark_rule: str | None
    policy_source_head: str
    policy_source_tree: str
    schema: str = field(default=RESEARCH_STRATEGY_ROBUSTNESS_POLICY_SCHEMA, init=False)
    policy_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        _uuid(self.candidate_id, "candidate_id")
        _uuid(self.strategy_definition_id, "strategy_definition_id")
        _source(self.strategy_source_head, "strategy_source_head")
        _source(self.strategy_source_tree, "strategy_source_tree")
        _text(self.strategy_id, "strategy_id")
        _text(self.strategy_version, "strategy_version")
        if type(self.symbol) is not Symbol:
            raise ResearchStrategyRobustnessError("symbol has an invalid type")
        _wire_config(self.strategy_config)
        _uuid(self.historical_data_fingerprint, "historical_data_fingerprint")
        partitions = (
            self.development_partition,
            self.walk_forward_partition,
            self.final_holdout_partition,
        )
        if not all(
            type(item) is ResearchStrategyRobustnessPartition for item in partitions
        ):
            raise ResearchStrategyRobustnessError("all policy partitions are required")
        expected_roles = (
            ResearchRobustnessPartitionRole.DEVELOPMENT,
            ResearchRobustnessPartitionRole.WALK_FORWARD,
            ResearchRobustnessPartitionRole.FINAL_HOLDOUT,
        )
        for item, role in zip(partitions, expected_roles, strict=True):
            _validate_partition(item)
            if (
                item.role is not role
                or item.historical_data_fingerprint != self.historical_data_fingerprint
            ):
                raise ResearchStrategyRobustnessError(
                    "policy partition lineage is inconsistent"
                )
        if not (
            self.development_partition.end <= self.walk_forward_partition.start
            and self.walk_forward_partition.end <= self.final_holdout_partition.start
        ):
            raise ResearchStrategyRobustnessError(
                "policy partitions must be chronological and non-overlapping"
            )
        _exact_int(
            self.minimum_completed_trade_count,
            "minimum_completed_trade_count",
            minimum=1,
        )
        _decimal(
            self.maximum_drawdown_percentage,
            "maximum_drawdown_percentage",
            nonnegative=True,
        )
        _decimal(self.minimum_net_return, "minimum_net_return")
        _exact_int(
            self.minimum_walk_forward_fold_count,
            "minimum_walk_forward_fold_count",
            minimum=1,
        )
        _rate(self.minimum_walk_forward_pass_rate, "minimum_walk_forward_pass_rate")
        _rate(self.minimum_stability_pass_rate, "minimum_stability_pass_rate")
        _decimal(
            self.maximum_stability_range, "maximum_stability_range", nonnegative=True
        )
        _decimal(
            self.maximum_stability_adjacent_change,
            "maximum_stability_adjacent_change",
            nonnegative=True,
        )
        _exact_int(
            self.minimum_sensitivity_neighborhood_count,
            "minimum_sensitivity_neighborhood_count",
            minimum=1,
        )
        _exact_int(
            self.minimum_sensitivity_pass_count,
            "minimum_sensitivity_pass_count",
            minimum=0,
        )
        if (
            self.minimum_sensitivity_pass_count
            > self.minimum_sensitivity_neighborhood_count
        ):
            raise ResearchStrategyRobustnessError(
                "sensitivity pass minimum exceeds neighborhood minimum"
            )
        _decimal(
            self.maximum_sensitivity_return_spread,
            "maximum_sensitivity_return_spread",
            nonnegative=True,
        )
        if type(self.execution_stress_suite) is not tuple or len(
            self.execution_stress_suite
        ) != len(_SCENARIO_ORDER):
            raise ResearchStrategyRobustnessError(
                "the complete execution-stress suite is required"
            )
        if not all(
            type(item) is ResearchExecutionStressScenario
            for item in self.execution_stress_suite
        ):
            raise ResearchStrategyRobustnessError("invalid execution-stress scenario")
        if (
            tuple(item.kind.value for item in self.execution_stress_suite)
            != _SCENARIO_ORDER
        ):
            raise ResearchStrategyRobustnessError(
                "execution-stress scenario order is frozen"
            )
        if len({item.scenario_id for item in self.execution_stress_suite}) != len(
            self.execution_stress_suite
        ):
            raise ResearchStrategyRobustnessError(
                "execution-stress scenario IDs must be unique"
            )
        if (
            self.benchmark_rule is not None
            and self.benchmark_rule != "CANDIDATE_NET_RETURN_AT_LEAST_BENCHMARK"
        ):
            raise ResearchStrategyRobustnessError("unknown benchmark rule")
        _source(self.policy_source_head, "policy_source_head")
        _source(self.policy_source_tree, "policy_source_tree")
        if self.schema != RESEARCH_STRATEGY_ROBUSTNESS_POLICY_SCHEMA:
            raise ResearchStrategyRobustnessError("policy schema is fixed")
        object.__setattr__(
            self,
            "policy_id",
            _identity(
                RESEARCH_STRATEGY_ROBUSTNESS_POLICY_NAMESPACE,
                RESEARCH_STRATEGY_ROBUSTNESS_POLICY_IDENTITY_VERSION,
                _policy_material(self),
            ),
        )

    def to_json(self) -> str:
        _validate_policy(self)
        return _json(_wire_policy(self))

    @classmethod
    def from_json(cls, value: str) -> ResearchStrategyRobustnessQualificationPolicy:
        raw = _fields(_loads(value), frozenset(_POLICY_FIELDS))
        try:
            result = cls(
                _parse_uuid(raw["candidate_id"], "candidate_id"),
                _parse_uuid(raw["strategy_definition_id"], "strategy_definition_id"),
                raw["strategy_source_head"],
                raw["strategy_source_tree"],
                raw["strategy_id"],
                raw["strategy_version"],
                Symbol(raw["symbol"]),
                _parse_config(raw["strategy_config"]),
                _parse_uuid(
                    raw["historical_data_fingerprint"], "historical_data_fingerprint"
                ),
                ResearchStrategyRobustnessPartition.from_json(
                    _json(raw["development_partition"])
                ),
                ResearchStrategyRobustnessPartition.from_json(
                    _json(raw["walk_forward_partition"])
                ),
                ResearchStrategyRobustnessPartition.from_json(
                    _json(raw["final_holdout_partition"])
                ),
                raw["minimum_completed_trade_count"],
                _parse_decimal(
                    raw["maximum_drawdown_percentage"],
                    "maximum_drawdown_percentage",
                    nonnegative=True,
                ),
                _parse_decimal(raw["minimum_net_return"], "minimum_net_return"),
                raw["minimum_walk_forward_fold_count"],
                _parse_decimal(
                    raw["minimum_walk_forward_pass_rate"],
                    "minimum_walk_forward_pass_rate",
                ),
                _parse_decimal(
                    raw["minimum_stability_pass_rate"], "minimum_stability_pass_rate"
                ),
                _parse_decimal(
                    raw["maximum_stability_range"],
                    "maximum_stability_range",
                    nonnegative=True,
                ),
                _parse_decimal(
                    raw["maximum_stability_adjacent_change"],
                    "maximum_stability_adjacent_change",
                    nonnegative=True,
                ),
                raw["minimum_sensitivity_neighborhood_count"],
                raw["minimum_sensitivity_pass_count"],
                _parse_decimal(
                    raw["maximum_sensitivity_return_spread"],
                    "maximum_sensitivity_return_spread",
                    nonnegative=True,
                ),
                tuple(
                    ResearchExecutionStressScenario.from_json(_json(item))
                    for item in raw["execution_stress_suite"]
                ),
                raw["benchmark_rule"],
                raw["policy_source_head"],
                raw["policy_source_tree"],
            )
            if (
                _parse_uuid(raw["policy_id"], "policy_id") != result.policy_id
                or result.to_json() != value
            ):
                raise ResearchStrategyRobustnessError(
                    "policy identity or bytes are inconsistent"
                )
            return result
        except (TypeError, ValueError, ArithmeticError, KeyError):
            raise ResearchStrategyRobustnessError("invalid policy JSON") from None


def _rate(value: Decimal, name: str) -> None:
    _decimal(value, name)
    if not _ZERO <= value <= _ONE:
        raise ResearchStrategyRobustnessError(f"{name} must be between zero and one")


def _policy_material(
    value: ResearchStrategyRobustnessQualificationPolicy,
) -> tuple[str, ...]:
    material = [
        value.schema,
        str(value.candidate_id),
        str(value.strategy_definition_id),
        value.strategy_source_head,
        value.strategy_source_tree,
        value.strategy_id,
        value.strategy_version,
        str(value.symbol),
        _wire_config(value.strategy_config)["short_window"].__str__(),
        str(value.strategy_config.long_window),
        _decimal(value.strategy_config.desired_quantity, "desired_quantity"),
        str(value.historical_data_fingerprint),
        *(
            str(item.partition_id)
            for item in (
                value.development_partition,
                value.walk_forward_partition,
                value.final_holdout_partition,
            )
        ),
        str(value.minimum_completed_trade_count),
        _decimal(value.maximum_drawdown_percentage, "maximum_drawdown_percentage"),
        _decimal(value.minimum_net_return, "minimum_net_return"),
        str(value.minimum_walk_forward_fold_count),
        _decimal(
            value.minimum_walk_forward_pass_rate, "minimum_walk_forward_pass_rate"
        ),
        _decimal(value.minimum_stability_pass_rate, "minimum_stability_pass_rate"),
        _decimal(value.maximum_stability_range, "maximum_stability_range"),
        _decimal(
            value.maximum_stability_adjacent_change, "maximum_stability_adjacent_change"
        ),
        str(value.minimum_sensitivity_neighborhood_count),
        str(value.minimum_sensitivity_pass_count),
        _decimal(
            value.maximum_sensitivity_return_spread, "maximum_sensitivity_return_spread"
        ),
        "none" if value.benchmark_rule is None else value.benchmark_rule,
        value.policy_source_head,
        value.policy_source_tree,
    ]
    material.extend(str(item.scenario_id) for item in value.execution_stress_suite)
    return tuple(material)


def _wire_policy(
    value: ResearchStrategyRobustnessQualificationPolicy,
) -> dict[str, object]:
    return {
        "schema": value.schema,
        "policy_id": str(value.policy_id),
        "candidate_id": str(value.candidate_id),
        "strategy_definition_id": str(value.strategy_definition_id),
        "strategy_source_head": value.strategy_source_head,
        "strategy_source_tree": value.strategy_source_tree,
        "strategy_id": value.strategy_id,
        "strategy_version": value.strategy_version,
        "symbol": str(value.symbol),
        "strategy_config": _wire_config(value.strategy_config),
        "historical_data_fingerprint": str(value.historical_data_fingerprint),
        "development_partition": _loads(value.development_partition.to_json()),
        "walk_forward_partition": _loads(value.walk_forward_partition.to_json()),
        "final_holdout_partition": _loads(value.final_holdout_partition.to_json()),
        "minimum_completed_trade_count": value.minimum_completed_trade_count,
        "maximum_drawdown_percentage": _decimal(
            value.maximum_drawdown_percentage, "maximum_drawdown_percentage"
        ),
        "minimum_net_return": _decimal(value.minimum_net_return, "minimum_net_return"),
        "minimum_walk_forward_fold_count": value.minimum_walk_forward_fold_count,
        "minimum_walk_forward_pass_rate": _decimal(
            value.minimum_walk_forward_pass_rate, "minimum_walk_forward_pass_rate"
        ),
        "minimum_stability_pass_rate": _decimal(
            value.minimum_stability_pass_rate, "minimum_stability_pass_rate"
        ),
        "maximum_stability_range": _decimal(
            value.maximum_stability_range, "maximum_stability_range"
        ),
        "maximum_stability_adjacent_change": _decimal(
            value.maximum_stability_adjacent_change, "maximum_stability_adjacent_change"
        ),
        "minimum_sensitivity_neighborhood_count": (
            value.minimum_sensitivity_neighborhood_count
        ),
        "minimum_sensitivity_pass_count": value.minimum_sensitivity_pass_count,
        "maximum_sensitivity_return_spread": _decimal(
            value.maximum_sensitivity_return_spread, "maximum_sensitivity_return_spread"
        ),
        "execution_stress_suite": [
            _loads(item.to_json()) for item in value.execution_stress_suite
        ],
        "benchmark_rule": value.benchmark_rule,
        "policy_source_head": value.policy_source_head,
        "policy_source_tree": value.policy_source_tree,
    }


_POLICY_FIELDS = frozenset(
    {
        "schema",
        "policy_id",
        "candidate_id",
        "strategy_definition_id",
        "strategy_source_head",
        "strategy_source_tree",
        "strategy_id",
        "strategy_version",
        "symbol",
        "strategy_config",
        "historical_data_fingerprint",
        "development_partition",
        "walk_forward_partition",
        "final_holdout_partition",
        "minimum_completed_trade_count",
        "maximum_drawdown_percentage",
        "minimum_net_return",
        "minimum_walk_forward_fold_count",
        "minimum_walk_forward_pass_rate",
        "minimum_stability_pass_rate",
        "maximum_stability_range",
        "maximum_stability_adjacent_change",
        "minimum_sensitivity_neighborhood_count",
        "minimum_sensitivity_pass_count",
        "maximum_sensitivity_return_spread",
        "execution_stress_suite",
        "benchmark_rule",
        "policy_source_head",
        "policy_source_tree",
    }
)


def _validate_policy(value: ResearchStrategyRobustnessQualificationPolicy) -> None:
    if type(value) is not ResearchStrategyRobustnessQualificationPolicy:
        raise ResearchStrategyRobustnessError("exact robustness policy required")
    expected = ResearchStrategyRobustnessQualificationPolicy(
        value.candidate_id,
        value.strategy_definition_id,
        value.strategy_source_head,
        value.strategy_source_tree,
        value.strategy_id,
        value.strategy_version,
        value.symbol,
        value.strategy_config,
        value.historical_data_fingerprint,
        value.development_partition,
        value.walk_forward_partition,
        value.final_holdout_partition,
        value.minimum_completed_trade_count,
        value.maximum_drawdown_percentage,
        value.minimum_net_return,
        value.minimum_walk_forward_fold_count,
        value.minimum_walk_forward_pass_rate,
        value.minimum_stability_pass_rate,
        value.maximum_stability_range,
        value.maximum_stability_adjacent_change,
        value.minimum_sensitivity_neighborhood_count,
        value.minimum_sensitivity_pass_count,
        value.maximum_sensitivity_return_spread,
        value.execution_stress_suite,
        value.benchmark_rule,
        value.policy_source_head,
        value.policy_source_tree,
    )
    if expected.policy_id != value.policy_id:
        raise ResearchStrategyRobustnessError("policy identity is inconsistent")


@dataclass(frozen=True, slots=True)
class ResearchStrategyFinalHoldoutAdmission:
    policy: ResearchStrategyRobustnessQualificationPolicy
    admission_source_head: str
    admission_source_tree: str
    schema: str = field(
        default=RESEARCH_STRATEGY_FINAL_HOLDOUT_ADMISSION_SCHEMA, init=False
    )
    admission_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        _validate_policy(self.policy)
        _source(self.admission_source_head, "admission_source_head")
        _source(self.admission_source_tree, "admission_source_tree")
        if self.schema != RESEARCH_STRATEGY_FINAL_HOLDOUT_ADMISSION_SCHEMA:
            raise ResearchStrategyRobustnessError("holdout admission schema is fixed")
        object.__setattr__(
            self,
            "admission_id",
            _identity(
                RESEARCH_STRATEGY_FINAL_HOLDOUT_ADMISSION_NAMESPACE,
                RESEARCH_STRATEGY_FINAL_HOLDOUT_ADMISSION_IDENTITY_VERSION,
                (
                    self.schema,
                    str(self.policy.policy_id),
                    str(self.policy.final_holdout_partition.partition_id),
                    self.admission_source_head,
                    self.admission_source_tree,
                ),
            ),
        )

    def to_json(self) -> str:
        _validate_admission(self)
        return _json(_wire_admission(self))

    @classmethod
    def from_json(cls, value: str) -> ResearchStrategyFinalHoldoutAdmission:
        raw = _fields(_loads(value), _ADMISSION_FIELDS)
        try:
            result = _parse_admission(raw)
            if _parse_uuid(raw["admission_id"], "admission_id") != result.admission_id:
                raise ResearchStrategyRobustnessError(
                    "holdout admission identity mismatch"
                )
            if result.to_json() != value:
                raise ResearchStrategyRobustnessError(
                    "noncanonical holdout admission JSON"
                )
            return result
        except (TypeError, ValueError, ArithmeticError, KeyError):
            raise ResearchStrategyRobustnessError(
                "invalid holdout admission JSON"
            ) from None


def admit_research_strategy_final_holdout(
    policy: ResearchStrategyRobustnessQualificationPolicy,
    *,
    admission_source_head: str,
    admission_source_tree: str,
) -> ResearchStrategyFinalHoldoutAdmission:
    """Freeze policy identity before a caller evaluates its sealed holdout."""
    return ResearchStrategyFinalHoldoutAdmission(
        policy, admission_source_head, admission_source_tree
    )


_ADMISSION_FIELDS = frozenset(
    {
        "schema",
        "admission_id",
        "policy",
        "admission_source_head",
        "admission_source_tree",
    }
)


def _wire_admission(value: ResearchStrategyFinalHoldoutAdmission) -> dict[str, object]:
    return {
        "schema": value.schema,
        "admission_id": str(value.admission_id),
        "policy": _loads(value.policy.to_json()),
        "admission_source_head": value.admission_source_head,
        "admission_source_tree": value.admission_source_tree,
    }


def _parse_admission(raw: dict[str, object]) -> ResearchStrategyFinalHoldoutAdmission:
    if raw["schema"] != RESEARCH_STRATEGY_FINAL_HOLDOUT_ADMISSION_SCHEMA:
        raise ResearchStrategyRobustnessError("holdout admission schema is fixed")
    return ResearchStrategyFinalHoldoutAdmission(
        ResearchStrategyRobustnessQualificationPolicy.from_json(_json(raw["policy"])),
        raw["admission_source_head"],
        raw["admission_source_tree"],
    )


def _validate_admission(value: ResearchStrategyFinalHoldoutAdmission) -> None:
    if type(value) is not ResearchStrategyFinalHoldoutAdmission:
        raise ResearchStrategyRobustnessError("exact holdout admission required")
    expected = ResearchStrategyFinalHoldoutAdmission(
        value.policy, value.admission_source_head, value.admission_source_tree
    )
    if expected.admission_id != value.admission_id:
        raise ResearchStrategyRobustnessError(
            "holdout admission identity is inconsistent"
        )


@dataclass(frozen=True, slots=True)
class ResearchStrategyRobustnessEvidence:
    policy_id: UUID
    candidate_id: UUID
    strategy_definition_id: UUID
    evidence_source_head: str
    evidence_source_tree: str
    historical_data_fingerprint: UUID
    development_partition_id: UUID
    development_completed_trade_count: int
    development_net_return: Decimal
    development_maximum_drawdown_percentage: Decimal
    walk_forward_partition_id: UUID
    walk_forward_evidence_id: UUID
    walk_forward_fold_count: int
    walk_forward_pass_count: int
    walk_forward_stability_result_id: UUID
    stability_observation_count: int
    stability_pass_count: int
    stability_maximum_range: Decimal
    stability_maximum_adjacent_change: Decimal
    sensitivity_result_id: UUID
    sensitivity_neighborhood_count: int
    sensitivity_pass_count: int
    sensitivity_return_spread: Decimal
    execution_stress_results: tuple[ResearchExecutionStressResult, ...]
    final_holdout_partition_id: UUID
    holdout_admission_id: UUID
    holdout_evaluation_id: UUID
    final_holdout_completed_trade_count: int
    final_holdout_net_return: Decimal
    final_holdout_maximum_drawdown_percentage: Decimal
    benchmark_return: Decimal | None
    schema: str = field(
        default=RESEARCH_STRATEGY_ROBUSTNESS_EVIDENCE_SCHEMA, init=False
    )
    evidence_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        for value, name in (
            (self.policy_id, "policy_id"),
            (self.candidate_id, "candidate_id"),
            (self.strategy_definition_id, "strategy_definition_id"),
            (self.historical_data_fingerprint, "historical_data_fingerprint"),
            (self.development_partition_id, "development_partition_id"),
            (self.walk_forward_partition_id, "walk_forward_partition_id"),
            (self.walk_forward_evidence_id, "walk_forward_evidence_id"),
            (self.walk_forward_stability_result_id, "walk_forward_stability_result_id"),
            (self.sensitivity_result_id, "sensitivity_result_id"),
            (self.final_holdout_partition_id, "final_holdout_partition_id"),
            (self.holdout_admission_id, "holdout_admission_id"),
            (self.holdout_evaluation_id, "holdout_evaluation_id"),
        ):
            _uuid(value, name)
        _source(self.evidence_source_head, "evidence_source_head")
        _source(self.evidence_source_tree, "evidence_source_tree")
        for name, value in (
            (
                "development_completed_trade_count",
                self.development_completed_trade_count,
            ),
            ("walk_forward_fold_count", self.walk_forward_fold_count),
            ("walk_forward_pass_count", self.walk_forward_pass_count),
            ("stability_observation_count", self.stability_observation_count),
            ("stability_pass_count", self.stability_pass_count),
            ("sensitivity_neighborhood_count", self.sensitivity_neighborhood_count),
            ("sensitivity_pass_count", self.sensitivity_pass_count),
            (
                "final_holdout_completed_trade_count",
                self.final_holdout_completed_trade_count,
            ),
        ):
            _exact_int(value, name)
        if (
            self.walk_forward_fold_count < 1
            or self.walk_forward_pass_count > self.walk_forward_fold_count
            or self.stability_observation_count < 1
            or self.stability_pass_count > self.stability_observation_count
            or self.sensitivity_neighborhood_count < 1
            or self.sensitivity_pass_count > self.sensitivity_neighborhood_count
        ):
            raise ResearchStrategyRobustnessError("evidence counts are inconsistent")
        for name, value, nonnegative in (
            ("development_net_return", self.development_net_return, False),
            (
                "development_maximum_drawdown_percentage",
                self.development_maximum_drawdown_percentage,
                True,
            ),
            ("stability_maximum_range", self.stability_maximum_range, True),
            (
                "stability_maximum_adjacent_change",
                self.stability_maximum_adjacent_change,
                True,
            ),
            ("sensitivity_return_spread", self.sensitivity_return_spread, True),
            ("final_holdout_net_return", self.final_holdout_net_return, False),
            (
                "final_holdout_maximum_drawdown_percentage",
                self.final_holdout_maximum_drawdown_percentage,
                True,
            ),
        ):
            _decimal(value, name, nonnegative=nonnegative)
        if self.benchmark_return is not None:
            _decimal(self.benchmark_return, "benchmark_return")
        if (
            type(self.execution_stress_results) is not tuple
            or len(self.execution_stress_results) != len(_SCENARIO_ORDER)
            or not all(
                type(item) is ResearchExecutionStressResult
                for item in self.execution_stress_results
            )
        ):
            raise ResearchStrategyRobustnessError(
                "evidence must retain all stress results"
            )
        if (
            tuple(item.scenario.kind.value for item in self.execution_stress_results)
            != _SCENARIO_ORDER
        ):
            raise ResearchStrategyRobustnessError(
                "evidence stress scenario order is frozen"
            )
        if self.schema != RESEARCH_STRATEGY_ROBUSTNESS_EVIDENCE_SCHEMA:
            raise ResearchStrategyRobustnessError("robustness evidence schema is fixed")
        object.__setattr__(
            self,
            "evidence_id",
            _identity(
                RESEARCH_STRATEGY_ROBUSTNESS_EVIDENCE_NAMESPACE,
                RESEARCH_STRATEGY_ROBUSTNESS_EVIDENCE_IDENTITY_VERSION,
                _evidence_material(self),
            ),
        )

    def to_json(self) -> str:
        _validate_evidence(self)
        return _json(_wire_evidence(self))

    @classmethod
    def from_json(cls, value: str) -> ResearchStrategyRobustnessEvidence:
        raw = _fields(_loads(value), _EVIDENCE_FIELDS)
        try:
            result = _parse_evidence(raw)
            if _parse_uuid(raw["evidence_id"], "evidence_id") != result.evidence_id:
                raise ResearchStrategyRobustnessError("evidence identity mismatch")
            if result.to_json() != value:
                raise ResearchStrategyRobustnessError("noncanonical evidence JSON")
            return result
        except (TypeError, ValueError, ArithmeticError, KeyError):
            raise ResearchStrategyRobustnessError("invalid evidence JSON") from None


_EVIDENCE_FIELDS = frozenset(
    {
        "schema",
        "evidence_id",
        "policy_id",
        "candidate_id",
        "strategy_definition_id",
        "evidence_source_head",
        "evidence_source_tree",
        "historical_data_fingerprint",
        "development_partition_id",
        "development_completed_trade_count",
        "development_net_return",
        "development_maximum_drawdown_percentage",
        "walk_forward_partition_id",
        "walk_forward_evidence_id",
        "walk_forward_fold_count",
        "walk_forward_pass_count",
        "walk_forward_stability_result_id",
        "stability_observation_count",
        "stability_pass_count",
        "stability_maximum_range",
        "stability_maximum_adjacent_change",
        "sensitivity_result_id",
        "sensitivity_neighborhood_count",
        "sensitivity_pass_count",
        "sensitivity_return_spread",
        "execution_stress_results",
        "final_holdout_partition_id",
        "holdout_admission_id",
        "holdout_evaluation_id",
        "final_holdout_completed_trade_count",
        "final_holdout_net_return",
        "final_holdout_maximum_drawdown_percentage",
        "benchmark_return",
    }
)


def _parse_evidence(raw: dict[str, object]) -> ResearchStrategyRobustnessEvidence:
    if raw["schema"] != RESEARCH_STRATEGY_ROBUSTNESS_EVIDENCE_SCHEMA:
        raise ResearchStrategyRobustnessError("robustness evidence schema is fixed")
    return ResearchStrategyRobustnessEvidence(
        _parse_uuid(raw["policy_id"], "policy_id"),
        _parse_uuid(raw["candidate_id"], "candidate_id"),
        _parse_uuid(raw["strategy_definition_id"], "strategy_definition_id"),
        _source(raw["evidence_source_head"], "evidence_source_head"),
        _source(raw["evidence_source_tree"], "evidence_source_tree"),
        _parse_uuid(raw["historical_data_fingerprint"], "historical_data_fingerprint"),
        _parse_uuid(raw["development_partition_id"], "development_partition_id"),
        _exact_int(
            raw["development_completed_trade_count"],
            "development_completed_trade_count",
        ),
        _parse_decimal(raw["development_net_return"], "development_net_return"),
        _parse_decimal(
            raw["development_maximum_drawdown_percentage"],
            "development_maximum_drawdown_percentage",
            nonnegative=True,
        ),
        _parse_uuid(raw["walk_forward_partition_id"], "walk_forward_partition_id"),
        _parse_uuid(raw["walk_forward_evidence_id"], "walk_forward_evidence_id"),
        _exact_int(raw["walk_forward_fold_count"], "walk_forward_fold_count"),
        _exact_int(raw["walk_forward_pass_count"], "walk_forward_pass_count"),
        _parse_uuid(
            raw["walk_forward_stability_result_id"],
            "walk_forward_stability_result_id",
        ),
        _exact_int(raw["stability_observation_count"], "stability_observation_count"),
        _exact_int(raw["stability_pass_count"], "stability_pass_count"),
        _parse_decimal(
            raw["stability_maximum_range"],
            "stability_maximum_range",
            nonnegative=True,
        ),
        _parse_decimal(
            raw["stability_maximum_adjacent_change"],
            "stability_maximum_adjacent_change",
            nonnegative=True,
        ),
        _parse_uuid(raw["sensitivity_result_id"], "sensitivity_result_id"),
        _exact_int(
            raw["sensitivity_neighborhood_count"], "sensitivity_neighborhood_count"
        ),
        _exact_int(raw["sensitivity_pass_count"], "sensitivity_pass_count"),
        _parse_decimal(
            raw["sensitivity_return_spread"],
            "sensitivity_return_spread",
            nonnegative=True,
        ),
        tuple(
            ResearchExecutionStressResult.from_json(_json(item))
            for item in raw["execution_stress_results"]
        ),
        _parse_uuid(raw["final_holdout_partition_id"], "final_holdout_partition_id"),
        _parse_uuid(raw["holdout_admission_id"], "holdout_admission_id"),
        _parse_uuid(raw["holdout_evaluation_id"], "holdout_evaluation_id"),
        _exact_int(
            raw["final_holdout_completed_trade_count"],
            "final_holdout_completed_trade_count",
        ),
        _parse_decimal(raw["final_holdout_net_return"], "final_holdout_net_return"),
        _parse_decimal(
            raw["final_holdout_maximum_drawdown_percentage"],
            "final_holdout_maximum_drawdown_percentage",
            nonnegative=True,
        ),
        None
        if raw["benchmark_return"] is None
        else _parse_decimal(raw["benchmark_return"], "benchmark_return"),
    )


def _validate_evidence(value: ResearchStrategyRobustnessEvidence) -> None:
    if type(value) is not ResearchStrategyRobustnessEvidence:
        raise ResearchStrategyRobustnessError("exact robustness evidence required")
    expected = ResearchStrategyRobustnessEvidence(
        value.policy_id,
        value.candidate_id,
        value.strategy_definition_id,
        value.evidence_source_head,
        value.evidence_source_tree,
        value.historical_data_fingerprint,
        value.development_partition_id,
        value.development_completed_trade_count,
        value.development_net_return,
        value.development_maximum_drawdown_percentage,
        value.walk_forward_partition_id,
        value.walk_forward_evidence_id,
        value.walk_forward_fold_count,
        value.walk_forward_pass_count,
        value.walk_forward_stability_result_id,
        value.stability_observation_count,
        value.stability_pass_count,
        value.stability_maximum_range,
        value.stability_maximum_adjacent_change,
        value.sensitivity_result_id,
        value.sensitivity_neighborhood_count,
        value.sensitivity_pass_count,
        value.sensitivity_return_spread,
        value.execution_stress_results,
        value.final_holdout_partition_id,
        value.holdout_admission_id,
        value.holdout_evaluation_id,
        value.final_holdout_completed_trade_count,
        value.final_holdout_net_return,
        value.final_holdout_maximum_drawdown_percentage,
        value.benchmark_return,
    )
    if expected.evidence_id != value.evidence_id:
        raise ResearchStrategyRobustnessError("evidence identity is inconsistent")


def _evidence_material(value: ResearchStrategyRobustnessEvidence) -> tuple[str, ...]:
    return (
        value.schema,
        str(value.policy_id),
        str(value.candidate_id),
        str(value.strategy_definition_id),
        value.evidence_source_head,
        value.evidence_source_tree,
        str(value.historical_data_fingerprint),
        str(value.development_partition_id),
        str(value.development_completed_trade_count),
        _decimal(value.development_net_return, "development_net_return"),
        _decimal(
            value.development_maximum_drawdown_percentage,
            "development_maximum_drawdown_percentage",
        ),
        str(value.walk_forward_partition_id),
        str(value.walk_forward_evidence_id),
        str(value.walk_forward_fold_count),
        str(value.walk_forward_pass_count),
        str(value.walk_forward_stability_result_id),
        str(value.stability_observation_count),
        str(value.stability_pass_count),
        _decimal(value.stability_maximum_range, "stability_maximum_range"),
        _decimal(
            value.stability_maximum_adjacent_change, "stability_maximum_adjacent_change"
        ),
        str(value.sensitivity_result_id),
        str(value.sensitivity_neighborhood_count),
        str(value.sensitivity_pass_count),
        _decimal(value.sensitivity_return_spread, "sensitivity_return_spread"),
        *(str(item.result_id) for item in value.execution_stress_results),
        str(value.final_holdout_partition_id),
        str(value.holdout_admission_id),
        str(value.holdout_evaluation_id),
        str(value.final_holdout_completed_trade_count),
        _decimal(value.final_holdout_net_return, "final_holdout_net_return"),
        _decimal(
            value.final_holdout_maximum_drawdown_percentage,
            "final_holdout_maximum_drawdown_percentage",
        ),
        "none"
        if value.benchmark_return is None
        else _decimal(value.benchmark_return, "benchmark_return"),
    )


@dataclass(frozen=True, slots=True)
class ResearchStrategyLiveCanaryEligibility:
    policy: ResearchStrategyRobustnessQualificationPolicy
    holdout_admission: ResearchStrategyFinalHoldoutAdmission
    evidence: ResearchStrategyRobustnessEvidence
    schema: str = field(
        default=RESEARCH_STRATEGY_LIVE_CANARY_ELIGIBILITY_SCHEMA, init=False
    )
    status: ResearchStrategyLiveCanaryEligibilityStatus = field(
        default=ResearchStrategyLiveCanaryEligibilityStatus.LIVE_CANARY_ELIGIBLE,
        init=False,
    )
    eligibility_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        _validate_policy(self.policy)
        if (
            type(self.holdout_admission) is not ResearchStrategyFinalHoldoutAdmission
            or self.holdout_admission.policy != self.policy
        ):
            raise ResearchStrategyRobustnessError(
                "holdout admission does not bind policy"
            )
        if type(self.evidence) is not ResearchStrategyRobustnessEvidence:
            raise ResearchStrategyRobustnessError("exact robustness evidence required")
        _validate_lineage(self.policy, self.holdout_admission, self.evidence)
        _validate_positive_criteria(self.policy, self.evidence)
        if self.schema != RESEARCH_STRATEGY_LIVE_CANARY_ELIGIBILITY_SCHEMA:
            raise ResearchStrategyRobustnessError("eligibility schema is fixed")
        object.__setattr__(
            self,
            "eligibility_id",
            _identity(
                RESEARCH_STRATEGY_LIVE_CANARY_ELIGIBILITY_NAMESPACE,
                RESEARCH_STRATEGY_LIVE_CANARY_ELIGIBILITY_IDENTITY_VERSION,
                (
                    self.schema,
                    self.status.value,
                    str(self.policy.policy_id),
                    str(self.holdout_admission.admission_id),
                    str(self.evidence.evidence_id),
                ),
            ),
        )

    def to_json(self) -> str:
        _validate_eligibility(self)
        return _json(
            {
                "schema": self.schema,
                "eligibility_id": str(self.eligibility_id),
                "status": self.status.value,
                "policy": _loads(self.policy.to_json()),
                "holdout_admission_id": str(self.holdout_admission.admission_id),
                "holdout_admission": _loads(self.holdout_admission.to_json()),
                "evidence": _wire_evidence(self.evidence),
            }
        )

    @classmethod
    def from_json(cls, value: str) -> ResearchStrategyLiveCanaryEligibility:
        raw = _fields(_loads(value), _ELIGIBILITY_FIELDS)
        try:
            policy = ResearchStrategyRobustnessQualificationPolicy.from_json(
                _json(raw["policy"])
            )
            admission = ResearchStrategyFinalHoldoutAdmission.from_json(
                _json(raw["holdout_admission"])
            )
            evidence = ResearchStrategyRobustnessEvidence.from_json(
                _json(raw["evidence"])
            )
            expected_status = (
                ResearchStrategyLiveCanaryEligibilityStatus.LIVE_CANARY_ELIGIBLE.value
            )
            if raw["status"] != expected_status:
                raise ResearchStrategyRobustnessError("eligibility status is fixed")
            if (
                _parse_uuid(raw["holdout_admission_id"], "holdout_admission_id")
                != admission.admission_id
            ):
                raise ResearchStrategyRobustnessError(
                    "holdout admission identity mismatch"
                )
            result = cls(policy, admission, evidence)
            if (
                _parse_uuid(raw["eligibility_id"], "eligibility_id")
                != result.eligibility_id
            ):
                raise ResearchStrategyRobustnessError("eligibility identity mismatch")
            if result.to_json() != value:
                raise ResearchStrategyRobustnessError("noncanonical eligibility JSON")
            return result
        except (TypeError, ValueError, ArithmeticError, KeyError):
            raise ResearchStrategyRobustnessError("invalid eligibility JSON") from None


_ELIGIBILITY_FIELDS = frozenset(
    {
        "schema",
        "eligibility_id",
        "status",
        "policy",
        "holdout_admission_id",
        "holdout_admission",
        "evidence",
    }
)


def _validate_policy_lineage(
    policy: ResearchStrategyRobustnessQualificationPolicy,
    admission: ResearchStrategyFinalHoldoutAdmission,
    evidence: ResearchStrategyRobustnessEvidence,
) -> None:
    if admission.policy != policy or evidence.policy_id != policy.policy_id:
        raise ResearchStrategyRobustnessError("policy changed after holdout admission")
    if (
        admission.admission_source_head != policy.policy_source_head
        or admission.admission_source_tree != policy.policy_source_tree
        or evidence.evidence_source_head != policy.policy_source_head
        or evidence.evidence_source_tree != policy.policy_source_tree
    ):
        raise ResearchStrategyRobustnessError("research provenance does not reconcile")
    expected = (
        ("candidate_id", evidence.candidate_id, policy.candidate_id),
        (
            "strategy_definition_id",
            evidence.strategy_definition_id,
            policy.strategy_definition_id,
        ),
        (
            "historical_data_fingerprint",
            evidence.historical_data_fingerprint,
            policy.historical_data_fingerprint,
        ),
        (
            "development_partition_id",
            evidence.development_partition_id,
            policy.development_partition.partition_id,
        ),
        (
            "walk_forward_partition_id",
            evidence.walk_forward_partition_id,
            policy.walk_forward_partition.partition_id,
        ),
        (
            "final_holdout_partition_id",
            evidence.final_holdout_partition_id,
            policy.final_holdout_partition.partition_id,
        ),
        ("holdout_admission_id", evidence.holdout_admission_id, admission.admission_id),
    )
    for name, actual, bound in expected:
        if actual != bound:
            raise ResearchStrategyRobustnessError(f"{name} does not reconcile")
    for result, scenario in zip(
        evidence.execution_stress_results, policy.execution_stress_suite, strict=True
    ):
        verify_research_execution_stress_result(result)
        if result.scenario != scenario:
            raise ResearchStrategyRobustnessError("stress scenario does not reconcile")


def build_research_strategy_live_canary_eligibility(
    policy: ResearchStrategyRobustnessQualificationPolicy,
    holdout_admission: ResearchStrategyFinalHoldoutAdmission,
    evidence: ResearchStrategyRobustnessEvidence,
) -> ResearchStrategyLiveCanaryEligibility:
    """Create positive-only evidence after every frozen requirement passes."""
    _validate_policy(policy)
    _validate_lineage(policy, holdout_admission, evidence)
    _validate_positive_criteria(policy, evidence)
    return ResearchStrategyLiveCanaryEligibility(policy, holdout_admission, evidence)


def _validate_positive_criteria(
    policy: ResearchStrategyRobustnessQualificationPolicy,
    evidence: ResearchStrategyRobustnessEvidence,
) -> None:
    if (
        evidence.development_completed_trade_count
        < policy.minimum_completed_trade_count
        or evidence.development_net_return < policy.minimum_net_return
        or evidence.development_maximum_drawdown_percentage
        > policy.maximum_drawdown_percentage
    ):
        raise ResearchStrategyRobustnessError("development evidence fails policy")
    if (
        evidence.walk_forward_fold_count < policy.minimum_walk_forward_fold_count
        or _ratio(evidence.walk_forward_pass_count, evidence.walk_forward_fold_count)
        < policy.minimum_walk_forward_pass_rate
        or evidence.final_holdout_net_return < policy.minimum_net_return
        or evidence.final_holdout_maximum_drawdown_percentage
        > policy.maximum_drawdown_percentage
        or evidence.final_holdout_completed_trade_count
        < policy.minimum_completed_trade_count
    ):
        raise ResearchStrategyRobustnessError(
            "walk-forward or holdout evidence fails policy"
        )
    if (
        _ratio(evidence.stability_pass_count, evidence.stability_observation_count)
        < policy.minimum_stability_pass_rate
        or evidence.stability_maximum_range > policy.maximum_stability_range
        or evidence.stability_maximum_adjacent_change
        > policy.maximum_stability_adjacent_change
    ):
        raise ResearchStrategyRobustnessError("stability evidence fails policy")
    if (
        evidence.sensitivity_neighborhood_count
        < policy.minimum_sensitivity_neighborhood_count
        or evidence.sensitivity_pass_count < policy.minimum_sensitivity_pass_count
        or evidence.sensitivity_return_spread > policy.maximum_sensitivity_return_spread
    ):
        raise ResearchStrategyRobustnessError("sensitivity evidence fails policy")
    for result in evidence.execution_stress_results:
        if _stress_net_return(result) < policy.minimum_net_return:
            raise ResearchStrategyRobustnessError(
                "execution stress evidence fails policy"
            )
    if policy.benchmark_rule is not None and (
        evidence.benchmark_return is None
        or evidence.final_holdout_net_return < evidence.benchmark_return
    ):
        raise ResearchStrategyRobustnessError("benchmark evidence fails policy")


def _ratio(numerator: int, denominator: int) -> Decimal:
    with localcontext(Context(prec=80)):
        return Decimal(numerator) / Decimal(denominator)


def _stress_net_return(result: ResearchExecutionStressResult) -> Decimal:
    reconciliation = result.reconciliation
    with localcontext(Context(prec=100)):
        return (
            reconciliation.ending_equity - reconciliation.starting_cash
        ) / reconciliation.starting_cash


def _validate_lineage(
    policy: ResearchStrategyRobustnessQualificationPolicy,
    admission: ResearchStrategyFinalHoldoutAdmission,
    evidence: ResearchStrategyRobustnessEvidence,
) -> None:
    if (
        type(admission) is not ResearchStrategyFinalHoldoutAdmission
        or type(evidence) is not ResearchStrategyRobustnessEvidence
    ):
        raise ResearchStrategyRobustnessError(
            "exact admission and evidence are required"
        )
    _validate_policy_lineage(policy, admission, evidence)


def _validate_eligibility(value: ResearchStrategyLiveCanaryEligibility) -> None:
    if (
        type(value) is not ResearchStrategyLiveCanaryEligibility
        or value.status
        is not ResearchStrategyLiveCanaryEligibilityStatus.LIVE_CANARY_ELIGIBLE
    ):
        raise ResearchStrategyRobustnessError("positive-only eligibility is invalid")
    expected = ResearchStrategyLiveCanaryEligibility(
        value.policy, value.holdout_admission, value.evidence
    )
    if expected.eligibility_id != value.eligibility_id:
        raise ResearchStrategyRobustnessError("eligibility identity is inconsistent")


def verify_research_strategy_live_canary_eligibility(
    eligibility: ResearchStrategyLiveCanaryEligibility,
    policy: ResearchStrategyRobustnessQualificationPolicy,
    holdout_admission: ResearchStrategyFinalHoldoutAdmission,
    evidence: ResearchStrategyRobustnessEvidence,
) -> None:
    expected = build_research_strategy_live_canary_eligibility(
        policy, holdout_admission, evidence
    )
    _validate_eligibility(eligibility)
    if expected != eligibility:
        raise ResearchStrategyRobustnessError(
            "eligibility does not independently reconcile"
        )


def _wire_stress_order(order: ResearchExecutionStressOrder) -> dict[str, object]:
    return {
        "order_id": str(order.order_id),
        "symbol": str(order.symbol),
        "side": order.side.value,
        "quantity": _decimal(order.quantity, "quantity"),
        "requested_price": _decimal(order.requested_price, "requested_price"),
        "delayed_execution_price": _decimal(
            order.delayed_execution_price, "delayed_execution_price"
        ),
        "mark_price": _decimal(order.mark_price, "mark_price"),
    }


def _wire_stress_result(result: ResearchExecutionStressResult) -> dict[str, object]:
    return {
        "schema": result.schema,
        "result_id": str(result.result_id),
        "scenario": _loads(result.scenario.to_json()),
        "starting_cash": _decimal(result.starting_cash, "starting_cash"),
        "orders": [_wire_stress_order(item) for item in result.orders],
        "order_results": [
            {
                "order_id": str(item.order_id),
                "disposition": item.disposition.value,
                "requested_quantity": _decimal(
                    item.requested_quantity, "requested_quantity"
                ),
                "filled_quantity": _decimal(item.filled_quantity, "filled_quantity"),
                "execution_price": None
                if item.execution_price is None
                else _decimal(item.execution_price, "execution_price"),
                "commission": _decimal(item.commission, "commission"),
                "cash_effect": _decimal(item.cash_effect, "cash_effect"),
                "reason": item.reason,
            }
            for item in result.order_results
        ],
        "reconciliation": {
            "starting_cash": _decimal(
                result.reconciliation.starting_cash, "starting_cash"
            ),
            "ending_cash": _decimal(result.reconciliation.ending_cash, "ending_cash"),
            "positions": [
                {
                    "symbol": str(item.symbol),
                    "quantity": _decimal(item.quantity, "position.quantity"),
                    "average_cost": _decimal(
                        item.average_cost, "position.average_cost"
                    ),
                    "mark_price": _decimal(item.mark_price, "position.mark_price"),
                }
                for item in result.reconciliation.positions
            ],
            "ending_equity": _decimal(
                result.reconciliation.ending_equity, "ending_equity"
            ),
            "filled_order_count": result.reconciliation.filled_order_count,
            "partial_fill_order_count": result.reconciliation.partial_fill_order_count,
            "missed_order_count": result.reconciliation.missed_order_count,
            "rejected_order_count": result.reconciliation.rejected_order_count,
            "total_filled_quantity": _decimal(
                result.reconciliation.total_filled_quantity, "total_filled_quantity"
            ),
            "total_transaction_cost": _decimal(
                result.reconciliation.total_transaction_cost, "total_transaction_cost"
            ),
        },
    }


def _wire_evidence(value: ResearchStrategyRobustnessEvidence) -> dict[str, object]:
    return {
        "schema": value.schema,
        "evidence_id": str(value.evidence_id),
        "policy_id": str(value.policy_id),
        "candidate_id": str(value.candidate_id),
        "strategy_definition_id": str(value.strategy_definition_id),
        "evidence_source_head": value.evidence_source_head,
        "evidence_source_tree": value.evidence_source_tree,
        "historical_data_fingerprint": str(value.historical_data_fingerprint),
        "development_partition_id": str(value.development_partition_id),
        "development_completed_trade_count": value.development_completed_trade_count,
        "development_net_return": _decimal(
            value.development_net_return, "development_net_return"
        ),
        "development_maximum_drawdown_percentage": _decimal(
            value.development_maximum_drawdown_percentage,
            "development_maximum_drawdown_percentage",
        ),
        "walk_forward_partition_id": str(value.walk_forward_partition_id),
        "walk_forward_evidence_id": str(value.walk_forward_evidence_id),
        "walk_forward_fold_count": value.walk_forward_fold_count,
        "walk_forward_pass_count": value.walk_forward_pass_count,
        "walk_forward_stability_result_id": str(value.walk_forward_stability_result_id),
        "stability_observation_count": value.stability_observation_count,
        "stability_pass_count": value.stability_pass_count,
        "stability_maximum_range": _decimal(
            value.stability_maximum_range, "stability_maximum_range"
        ),
        "stability_maximum_adjacent_change": _decimal(
            value.stability_maximum_adjacent_change, "stability_maximum_adjacent_change"
        ),
        "sensitivity_result_id": str(value.sensitivity_result_id),
        "sensitivity_neighborhood_count": value.sensitivity_neighborhood_count,
        "sensitivity_pass_count": value.sensitivity_pass_count,
        "sensitivity_return_spread": _decimal(
            value.sensitivity_return_spread, "sensitivity_return_spread"
        ),
        "execution_stress_results": [
            _wire_stress_result(item) for item in value.execution_stress_results
        ],
        "final_holdout_partition_id": str(value.final_holdout_partition_id),
        "holdout_admission_id": str(value.holdout_admission_id),
        "holdout_evaluation_id": str(value.holdout_evaluation_id),
        "final_holdout_completed_trade_count": (
            value.final_holdout_completed_trade_count
        ),
        "final_holdout_net_return": _decimal(
            value.final_holdout_net_return, "final_holdout_net_return"
        ),
        "final_holdout_maximum_drawdown_percentage": _decimal(
            value.final_holdout_maximum_drawdown_percentage,
            "final_holdout_maximum_drawdown_percentage",
        ),
        "benchmark_return": None
        if value.benchmark_return is None
        else _decimal(value.benchmark_return, "benchmark_return"),
    }


__all__ = [
    "RESEARCH_EXECUTION_STRESS_RESULT_IDENTITY_VERSION",
    "RESEARCH_EXECUTION_STRESS_RESULT_NAMESPACE",
    "RESEARCH_EXECUTION_STRESS_RESULT_SCHEMA",
    "RESEARCH_EXECUTION_STRESS_SCENARIO_IDENTITY_VERSION",
    "RESEARCH_EXECUTION_STRESS_SCENARIO_NAMESPACE",
    "RESEARCH_EXECUTION_STRESS_SCENARIO_SCHEMA",
    "RESEARCH_STRATEGY_FINAL_HOLDOUT_ADMISSION_IDENTITY_VERSION",
    "RESEARCH_STRATEGY_FINAL_HOLDOUT_ADMISSION_NAMESPACE",
    "RESEARCH_STRATEGY_FINAL_HOLDOUT_ADMISSION_SCHEMA",
    "RESEARCH_STRATEGY_LIVE_CANARY_ELIGIBILITY_IDENTITY_VERSION",
    "RESEARCH_STRATEGY_LIVE_CANARY_ELIGIBILITY_NAMESPACE",
    "RESEARCH_STRATEGY_LIVE_CANARY_ELIGIBILITY_SCHEMA",
    "RESEARCH_STRATEGY_ROBUSTNESS_EVIDENCE_IDENTITY_VERSION",
    "RESEARCH_STRATEGY_ROBUSTNESS_EVIDENCE_NAMESPACE",
    "RESEARCH_STRATEGY_ROBUSTNESS_EVIDENCE_SCHEMA",
    "RESEARCH_STRATEGY_ROBUSTNESS_POLICY_IDENTITY_VERSION",
    "RESEARCH_STRATEGY_ROBUSTNESS_POLICY_NAMESPACE",
    "RESEARCH_STRATEGY_ROBUSTNESS_POLICY_SCHEMA",
    "RESEARCH_STRATEGY_ROBUSTNESS_QUALIFICATION_POLICY_IDENTITY_VERSION",
    "RESEARCH_STRATEGY_ROBUSTNESS_QUALIFICATION_POLICY_NAMESPACE",
    "RESEARCH_STRATEGY_ROBUSTNESS_QUALIFICATION_POLICY_SCHEMA",
    "ResearchExecutionStressDisposition",
    "ResearchExecutionStressKind",
    "ResearchExecutionStressOrder",
    "ResearchExecutionStressOrderResult",
    "ResearchExecutionStressPosition",
    "ResearchExecutionStressReconciliation",
    "ResearchExecutionStressResult",
    "ResearchExecutionStressScenario",
    "ResearchRobustnessPartitionRole",
    "ResearchStrategyFinalHoldoutAdmission",
    "ResearchStrategyLiveCanaryEligibility",
    "ResearchStrategyLiveCanaryEligibilityStatus",
    "ResearchStrategyRobustnessError",
    "ResearchStrategyRobustnessPartition",
    "ResearchStrategyRobustnessQualificationPolicy",
    "ResearchStrategyRobustnessEvidence",
    "admit_research_strategy_final_holdout",
    "build_research_strategy_live_canary_eligibility",
    "simulate_research_execution_stress",
    "verify_research_execution_stress_result",
    "verify_research_strategy_live_canary_eligibility",
]
