"""Strategy-native research definitions and deterministic evaluation policies.

These models are inert research inputs.  They do not select production
strategies, acquire market data, or grant any runtime or promotion authority.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID, uuid5

from trading_bot.domain import Symbol
from trading_bot.risk.models import RiskLimits
from trading_bot.strategies.moving_average import MovingAverageCrossoverConfig
from trading_bot.strategies.production import (
    MOVING_AVERAGE_STRATEGY_ID,
    MOVING_AVERAGE_STRATEGY_VERSION,
    PRODUCTION_STRATEGY_SCHEMA,
)

RESEARCH_STRATEGY_DEFINITION_SCHEMA = "research-strategy-definition/v1"
RESEARCH_STRATEGY_DEFINITION_IDENTITY_VERSION = (
    "research-strategy-definition-identity/v1"
)
RESEARCH_STRATEGY_DEFINITION_NAMESPACE = UUID("0b64cd96-bc4a-569e-aaa6-8cee8a0c037d")

RESEARCH_STRATEGY_EVALUATION_POLICY_SCHEMA = "research-strategy-evaluation-policy/v1"
RESEARCH_STRATEGY_EVALUATION_POLICY_IDENTITY_VERSION = (
    "research-strategy-evaluation-policy-identity/v1"
)
RESEARCH_STRATEGY_EVALUATION_POLICY_NAMESPACE = UUID(
    "26c58998-5378-5140-928c-fa3db4488b77"
)

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_DEFINITION_FIELDS = frozenset(
    {
        "schema",
        "definition_id",
        "strategy_source_head",
        "strategy_source_tree",
        "production_strategy_schema",
        "strategy_id",
        "strategy_version",
        "symbol",
        "strategy_config",
    }
)
_CONFIG_FIELDS = frozenset({"short_window", "long_window", "desired_quantity"})
_POLICY_FIELDS = frozenset(
    {
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
    }
)
_POLICY_DECIMAL_FIELDS = (
    "starting_cash",
    "fixed_commission",
    "slippage_basis_points",
    "max_position_percent",
    "max_total_exposure_percent",
    "max_order_notional",
    "max_new_position_percent",
    "minimum_cash_reserve_percent",
    "fractional_increment",
    "estimated_commission",
)
_POLICY_BOOLEAN_FIELDS = (
    "trading_enabled",
    "allow_missing_sessions",
    "allow_fractional_shares",
    "allow_buying",
    "allow_selling",
)


class ResearchStrategyDefinitionError(ValueError):
    """Raised when strategy-native research input is malformed."""


def _frame(value: str) -> str:
    try:
        return f"{len(value.encode('utf-8'))}:{value}"
    except UnicodeError:
        raise ResearchStrategyDefinitionError("identity text must be UTF-8") from None


def _identity(namespace: UUID, version: str, values: tuple[str, ...]) -> UUID:
    return uuid5(namespace, "".join(_frame(value) for value in (version, *values)))


def _canonical_decimal(value: Decimal, name: str = "Decimal") -> str:
    if type(value) is not Decimal or not value.is_finite():
        raise ResearchStrategyDefinitionError(f"{name} must be a finite Decimal")
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return "0" if rendered in {"", "-0"} else rendered


def _parse_decimal(
    value: object, name: str, *, optional: bool = False
) -> Decimal | None:
    if optional and value is None:
        return None
    if type(value) is not str:
        raise ResearchStrategyDefinitionError(f"{name} must be canonical Decimal text")
    try:
        parsed = Decimal(value)
    except ArithmeticError:
        raise ResearchStrategyDefinitionError(f"{name} must be a Decimal") from None
    if _canonical_decimal(parsed, name) != value:
        raise ResearchStrategyDefinitionError(f"{name} is not canonical Decimal text")
    return parsed


def _source(value: object, name: str) -> str:
    if type(value) is not str or _SHA40.fullmatch(value) is None:
        raise ResearchStrategyDefinitionError(
            f"{name} must be exact lowercase 40-hex text"
        )
    return value


def _uuid(value: object, name: str) -> UUID:
    if type(value) is not str:
        raise ResearchStrategyDefinitionError(f"{name} must be a canonical UUID")
    try:
        parsed = UUID(value)
    except ValueError:
        raise ResearchStrategyDefinitionError(
            f"{name} must be a canonical UUID"
        ) from None
    if str(parsed) != value:
        raise ResearchStrategyDefinitionError(f"{name} must be a canonical UUID")
    return parsed


def _exact_fields(value: object, expected: frozenset[str]) -> dict[str, object]:
    if type(value) is not dict or set(value) != expected:
        raise ResearchStrategyDefinitionError("exact canonical fields required")
    return value


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ResearchStrategyDefinitionError("duplicate JSON field")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ResearchStrategyDefinitionError(f"non-JSON constant {value} is forbidden")


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _definition_material(definition: ResearchStrategyDefinition) -> tuple[str, ...]:
    _validate_definition(definition, check_identity=False)
    config = definition.strategy_config
    return (
        definition.schema,
        definition.strategy_source_head,
        definition.strategy_source_tree,
        definition.production_strategy_schema,
        definition.strategy_id,
        definition.strategy_version,
        str(definition.symbol),
        str(config.short_window),
        str(config.long_window),
        _canonical_decimal(config.desired_quantity, "desired_quantity"),
    )


@dataclass(frozen=True, slots=True)
class ResearchStrategyDefinition:
    """One immutable v1 strategy-native research definition."""

    schema: str = field(default=RESEARCH_STRATEGY_DEFINITION_SCHEMA, init=False)
    definition_id: UUID = field(init=False)
    strategy_source_head: str
    strategy_source_tree: str
    production_strategy_schema: str = field(
        default=PRODUCTION_STRATEGY_SCHEMA, init=False
    )
    strategy_id: str = field(default=MOVING_AVERAGE_STRATEGY_ID, init=False)
    strategy_version: str = field(default=MOVING_AVERAGE_STRATEGY_VERSION, init=False)
    symbol: Symbol
    strategy_config: MovingAverageCrossoverConfig

    def __post_init__(self) -> None:
        _validate_definition(self, check_identity=False)
        object.__setattr__(
            self,
            "definition_id",
            _identity(
                RESEARCH_STRATEGY_DEFINITION_NAMESPACE,
                RESEARCH_STRATEGY_DEFINITION_IDENTITY_VERSION,
                _definition_material(self),
            ),
        )

    def to_json(self) -> str:
        """Serialize the exact compact canonical definition representation."""
        _validate_definition(self)
        config = self.strategy_config
        return _json(
            {
                "schema": self.schema,
                "definition_id": str(self.definition_id),
                "strategy_source_head": self.strategy_source_head,
                "strategy_source_tree": self.strategy_source_tree,
                "production_strategy_schema": self.production_strategy_schema,
                "strategy_id": self.strategy_id,
                "strategy_version": self.strategy_version,
                "symbol": str(self.symbol),
                "strategy_config": {
                    "short_window": config.short_window,
                    "long_window": config.long_window,
                    "desired_quantity": _canonical_decimal(
                        config.desired_quantity, "desired_quantity"
                    ),
                },
            }
        )

    @classmethod
    def from_json(cls, value: str) -> ResearchStrategyDefinition:
        """Parse canonical self-consistent bytes without executing research."""
        try:
            if cls is not ResearchStrategyDefinition or type(value) is not str:
                raise ResearchStrategyDefinitionError("exact definition JSON required")
            raw = json.loads(
                value,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
            root = _exact_fields(raw, _DEFINITION_FIELDS)
            if root["schema"] != RESEARCH_STRATEGY_DEFINITION_SCHEMA:
                raise ResearchStrategyDefinitionError("invalid definition schema")
            symbol_text = root["symbol"]
            if type(symbol_text) is not str:
                raise ResearchStrategyDefinitionError("symbol must be canonical text")
            symbol = Symbol(symbol_text)
            if str(symbol) != symbol_text:
                raise ResearchStrategyDefinitionError("symbol is not canonical")
            config_raw = _exact_fields(root["strategy_config"], _CONFIG_FIELDS)
            quantity = _parse_decimal(
                config_raw["desired_quantity"], "desired_quantity"
            )
            assert quantity is not None
            config = MovingAverageCrossoverConfig(
                config_raw["short_window"], config_raw["long_window"], quantity
            )
            result = cls(
                strategy_source_head=_source(
                    root["strategy_source_head"], "strategy_source_head"
                ),
                strategy_source_tree=_source(
                    root["strategy_source_tree"], "strategy_source_tree"
                ),
                symbol=symbol,
                strategy_config=config,
            )
            if (
                _uuid(root["definition_id"], "definition_id") != result.definition_id
                or result.to_json() != value
            ):
                raise ResearchStrategyDefinitionError(
                    "definition identity or canonical bytes are inconsistent"
                )
            return result
        except (ArithmeticError, TypeError, UnicodeError, ValueError) as error:
            if isinstance(error, ResearchStrategyDefinitionError):
                raise
            raise ResearchStrategyDefinitionError(
                "invalid research definition JSON"
            ) from None


def _validate_definition(
    definition: ResearchStrategyDefinition, *, check_identity: bool = True
) -> None:
    if type(definition) is not ResearchStrategyDefinition:
        raise ResearchStrategyDefinitionError(
            "definition must be exactly ResearchStrategyDefinition"
        )
    _source(definition.strategy_source_head, "strategy_source_head")
    _source(definition.strategy_source_tree, "strategy_source_tree")
    if type(definition.symbol) is not Symbol:
        raise ResearchStrategyDefinitionError("symbol must be exactly Symbol")
    if type(definition.strategy_config) is not MovingAverageCrossoverConfig:
        raise ResearchStrategyDefinitionError(
            "strategy_config must be exactly MovingAverageCrossoverConfig"
        )
    try:
        canonical_config = MovingAverageCrossoverConfig(
            definition.strategy_config.short_window,
            definition.strategy_config.long_window,
            definition.strategy_config.desired_quantity,
        )
    except (TypeError, ValueError) as error:
        raise ResearchStrategyDefinitionError(str(error)) from error
    if canonical_config != definition.strategy_config:
        raise ResearchStrategyDefinitionError("strategy_config is inconsistent")
    if definition.schema != RESEARCH_STRATEGY_DEFINITION_SCHEMA:
        raise ResearchStrategyDefinitionError("definition schema is fixed")
    if definition.production_strategy_schema != PRODUCTION_STRATEGY_SCHEMA:
        raise ResearchStrategyDefinitionError("production schema is fixed")
    if definition.strategy_id != MOVING_AVERAGE_STRATEGY_ID:
        raise ResearchStrategyDefinitionError("strategy id is fixed")
    if definition.strategy_version != MOVING_AVERAGE_STRATEGY_VERSION:
        raise ResearchStrategyDefinitionError("strategy version is fixed")
    if check_identity:
        expected = _identity(
            RESEARCH_STRATEGY_DEFINITION_NAMESPACE,
            RESEARCH_STRATEGY_DEFINITION_IDENTITY_VERSION,
            _definition_material(definition),
        )
        if (
            type(definition.definition_id) is not UUID
            or definition.definition_id != expected
        ):
            raise ResearchStrategyDefinitionError("definition_id is inconsistent")


@dataclass(frozen=True, slots=True)
class ResearchStrategyEvaluationPolicy:
    """Complete behavior-affecting BacktestConfig and RiskLimits semantics."""

    schema: str = field(default=RESEARCH_STRATEGY_EVALUATION_POLICY_SCHEMA, init=False)
    policy_id: UUID = field(init=False)
    starting_cash: Decimal
    fixed_commission: Decimal
    slippage_basis_points: Decimal
    trading_enabled: bool
    allow_missing_sessions: bool
    max_position_percent: Decimal
    max_total_exposure_percent: Decimal
    max_order_notional: Decimal | None
    max_new_position_percent: Decimal | None
    minimum_cash_reserve_percent: Decimal
    allow_fractional_shares: bool
    fractional_increment: Decimal
    allow_buying: bool
    allow_selling: bool
    estimated_commission: Decimal

    def __post_init__(self) -> None:
        _validate_policy(self, check_identity=False)
        object.__setattr__(
            self,
            "policy_id",
            _identity(
                RESEARCH_STRATEGY_EVALUATION_POLICY_NAMESPACE,
                RESEARCH_STRATEGY_EVALUATION_POLICY_IDENTITY_VERSION,
                _policy_material(self),
            ),
        )

    @property
    def risk_limits(self) -> RiskLimits:
        """Build the exact deterministic risk limits bound by this policy."""
        _validate_policy(self)
        return RiskLimits(
            max_position_percent=self.max_position_percent,
            max_total_exposure_percent=self.max_total_exposure_percent,
            max_order_notional=self.max_order_notional,
            max_new_position_percent=self.max_new_position_percent,
            minimum_cash_reserve_percent=self.minimum_cash_reserve_percent,
            allow_fractional_shares=self.allow_fractional_shares,
            fractional_increment=self.fractional_increment,
            allow_buying=self.allow_buying,
            allow_selling=self.allow_selling,
            estimated_commission=self.estimated_commission,
        )

    def to_json(self) -> str:
        """Serialize the exact compact canonical policy representation."""
        _validate_policy(self)
        return _json(
            {
                "schema": self.schema,
                "policy_id": str(self.policy_id),
                **{
                    name: (
                        _canonical_decimal(getattr(self, name), name)
                        if name in _POLICY_DECIMAL_FIELDS
                        and getattr(self, name) is not None
                        else getattr(self, name)
                    )
                    for name in (
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
                },
            }
        )

    @classmethod
    def from_json(cls, value: str) -> ResearchStrategyEvaluationPolicy:
        """Parse canonical self-consistent bytes without executing research."""
        try:
            if cls is not ResearchStrategyEvaluationPolicy or type(value) is not str:
                raise ResearchStrategyDefinitionError("exact policy JSON required")
            raw = json.loads(
                value,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
            root = _exact_fields(raw, _POLICY_FIELDS)
            if root["schema"] != RESEARCH_STRATEGY_EVALUATION_POLICY_SCHEMA:
                raise ResearchStrategyDefinitionError("invalid policy schema")
            values: dict[str, object] = {}
            for name in _POLICY_DECIMAL_FIELDS:
                values[name] = _parse_decimal(
                    root[name],
                    name,
                    optional=name in {"max_order_notional", "max_new_position_percent"},
                )
            for name in _POLICY_BOOLEAN_FIELDS:
                if type(root[name]) is not bool:
                    raise ResearchStrategyDefinitionError(f"{name} must be a bool")
                values[name] = root[name]
            result = cls(**values)  # type: ignore[arg-type]
            if (
                _uuid(root["policy_id"], "policy_id") != result.policy_id
                or result.to_json() != value
            ):
                raise ResearchStrategyDefinitionError(
                    "policy identity or canonical bytes are inconsistent"
                )
            return result
        except (ArithmeticError, TypeError, UnicodeError, ValueError) as error:
            if isinstance(error, ResearchStrategyDefinitionError):
                raise
            raise ResearchStrategyDefinitionError(
                "invalid evaluation policy JSON"
            ) from None


def _policy_material(policy: ResearchStrategyEvaluationPolicy) -> tuple[str, ...]:
    _validate_policy(policy, check_identity=False)
    values: list[str] = [policy.schema]
    for name in (
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
    ):
        value = getattr(policy, name)
        if name in _POLICY_DECIMAL_FIELDS:
            values.append("none" if value is None else _canonical_decimal(value, name))
        else:
            values.append("true" if value else "false")
    return tuple(values)


def _validate_policy(
    policy: ResearchStrategyEvaluationPolicy, *, check_identity: bool = True
) -> None:
    if type(policy) is not ResearchStrategyEvaluationPolicy:
        raise ResearchStrategyDefinitionError(
            "policy must be exactly ResearchStrategyEvaluationPolicy"
        )
    if policy.schema != RESEARCH_STRATEGY_EVALUATION_POLICY_SCHEMA:
        raise ResearchStrategyDefinitionError("policy schema is fixed")
    for name in _POLICY_DECIMAL_FIELDS:
        value = getattr(policy, name)
        if value is None and name in {"max_order_notional", "max_new_position_percent"}:
            continue
        _canonical_decimal(value, name)
    for name in _POLICY_BOOLEAN_FIELDS:
        if type(getattr(policy, name)) is not bool:
            raise ResearchStrategyDefinitionError(f"{name} must be a bool")
    if policy.starting_cash <= Decimal("0"):
        raise ResearchStrategyDefinitionError("starting_cash must be positive")
    if policy.fixed_commission < Decimal("0"):
        raise ResearchStrategyDefinitionError("fixed_commission must be nonnegative")
    if not Decimal("0") <= policy.slippage_basis_points < Decimal("10000"):
        raise ResearchStrategyDefinitionError("slippage_basis_points is out of range")
    if policy.max_order_notional is not None and policy.max_order_notional <= 0:
        raise ResearchStrategyDefinitionError("max_order_notional must be positive")
    if (
        policy.max_new_position_percent is not None
        and policy.max_new_position_percent <= 0
    ):
        raise ResearchStrategyDefinitionError(
            "max_new_position_percent must be positive"
        )
    if policy.estimated_commission != policy.fixed_commission:
        raise ResearchStrategyDefinitionError(
            "estimated_commission must equal fixed_commission"
        )
    try:
        RiskLimits(
            max_position_percent=policy.max_position_percent,
            max_total_exposure_percent=policy.max_total_exposure_percent,
            max_order_notional=policy.max_order_notional,
            max_new_position_percent=policy.max_new_position_percent,
            minimum_cash_reserve_percent=policy.minimum_cash_reserve_percent,
            allow_fractional_shares=policy.allow_fractional_shares,
            fractional_increment=policy.fractional_increment,
            allow_buying=policy.allow_buying,
            allow_selling=policy.allow_selling,
            estimated_commission=policy.estimated_commission,
        )
    except (TypeError, ValueError) as error:
        raise ResearchStrategyDefinitionError(str(error)) from error
    if check_identity:
        expected = _identity(
            RESEARCH_STRATEGY_EVALUATION_POLICY_NAMESPACE,
            RESEARCH_STRATEGY_EVALUATION_POLICY_IDENTITY_VERSION,
            _policy_material(policy),
        )
        if type(policy.policy_id) is not UUID or policy.policy_id != expected:
            raise ResearchStrategyDefinitionError("policy_id is inconsistent")


def build_research_strategy_definition(
    *,
    strategy_source_head: str,
    strategy_source_tree: str,
    symbol: Symbol,
    strategy_config: MovingAverageCrossoverConfig,
) -> ResearchStrategyDefinition:
    """Construct one fixed-family strategy-native definition."""
    return ResearchStrategyDefinition(
        strategy_source_head=strategy_source_head,
        strategy_source_tree=strategy_source_tree,
        symbol=symbol,
        strategy_config=strategy_config,
    )


def build_research_strategy_evaluation_policy(
    **values: object,
) -> ResearchStrategyEvaluationPolicy:
    """Construct a policy only when every behavior-affecting value is supplied."""
    return ResearchStrategyEvaluationPolicy(**values)  # type: ignore[arg-type]


__all__ = [
    "MOVING_AVERAGE_STRATEGY_ID",
    "MOVING_AVERAGE_STRATEGY_VERSION",
    "PRODUCTION_STRATEGY_SCHEMA",
    "RESEARCH_STRATEGY_DEFINITION_IDENTITY_VERSION",
    "RESEARCH_STRATEGY_DEFINITION_NAMESPACE",
    "RESEARCH_STRATEGY_DEFINITION_SCHEMA",
    "RESEARCH_STRATEGY_EVALUATION_POLICY_IDENTITY_VERSION",
    "RESEARCH_STRATEGY_EVALUATION_POLICY_NAMESPACE",
    "RESEARCH_STRATEGY_EVALUATION_POLICY_SCHEMA",
    "ResearchStrategyDefinition",
    "ResearchStrategyDefinitionError",
    "ResearchStrategyEvaluationPolicy",
    "build_research_strategy_definition",
    "build_research_strategy_evaluation_policy",
]
