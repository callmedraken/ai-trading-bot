"""Pure session-scoped production strategy selection.

This module is inert contract material only. It owns no market-data, provider,
paper-store, risk, scheduler, clock, filesystem, research, AI, or execution
capability.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid5

from trading_bot.domain import Symbol
from trading_bot.strategies.moving_average import (
    MovingAverageCrossoverConfig,
    MovingAverageCrossoverStrategy,
)

PRODUCTION_STRATEGY_SCHEMA = "production-strategy-contract/v1"
PRODUCTION_STRATEGY_IDENTITY_VERSION = "production-strategy-contract-identity/v1"
MOVING_AVERAGE_STRATEGY_ID = "MovingAverageCrossoverStrategy"
MOVING_AVERAGE_STRATEGY_VERSION = "1.0.0"
_PRODUCTION_STRATEGY_NAMESPACE = UUID("c0867c3b-548e-5512-a135-3c4f1225e6fc")
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_ROOT_FIELDS = frozenset(
    {
        "schema",
        "contract_id",
        "target_session_date",
        "source_head",
        "source_tree",
        "strategy_id",
        "strategy_version",
        "symbol",
        "strategy_config",
    }
)
_CONFIG_FIELDS = frozenset({"short_window", "long_window", "desired_quantity"})


def _canonical_decimal(value: Decimal) -> str:
    if type(value) is not Decimal or not value.is_finite() or value <= 0:
        raise ValueError("positive finite Decimal required")
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _exact_fields(value: object, expected: frozenset[str]) -> dict[str, object]:
    if type(value) is not dict or set(value) != expected:
        raise ValueError("exact contract fields required")
    return value


def _source_digest(value: object, name: str) -> str:
    if type(value) is not str or _SHA40.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase 40-character digest")
    return value


def _target_date(value: object) -> date:
    if type(value) is not date:
        raise TypeError("target_session_date must be exactly date")
    return value


def _frame(value: str) -> str:
    return f"{len(value.encode('utf-8'))}:{value}"


def _semantic_material(
    target_session_date: date,
    source_head: str,
    source_tree: str,
    symbol: Symbol,
    config: MovingAverageCrossoverConfig,
) -> str:
    values = (
        PRODUCTION_STRATEGY_IDENTITY_VERSION,
        target_session_date.isoformat(),
        source_head,
        source_tree,
        MOVING_AVERAGE_STRATEGY_ID,
        MOVING_AVERAGE_STRATEGY_VERSION,
        str(symbol),
        str(config.short_window),
        str(config.long_window),
        _canonical_decimal(config.desired_quantity),
    )
    return "".join(_frame(value) for value in values)


@dataclass(frozen=True, slots=True)
class ProductionStrategyContract:
    """One inert production strategy selection for one explicit session date."""

    target_session_date: date
    source_head: str
    source_tree: str
    symbol: Symbol
    strategy_config: MovingAverageCrossoverConfig
    schema: str = field(default=PRODUCTION_STRATEGY_SCHEMA, init=False)
    strategy_id: str = field(default=MOVING_AVERAGE_STRATEGY_ID, init=False)
    strategy_version: str = field(default=MOVING_AVERAGE_STRATEGY_VERSION, init=False)
    contract_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        target = _target_date(self.target_session_date)
        head = _source_digest(self.source_head, "source_head")
        tree = _source_digest(self.source_tree, "source_tree")
        if type(self.symbol) is not Symbol:
            raise TypeError("symbol must be exactly Symbol")
        if type(self.strategy_config) is not MovingAverageCrossoverConfig:
            raise TypeError(
                "strategy_config must be exactly MovingAverageCrossoverConfig"
            )
        object.__setattr__(
            self,
            "contract_id",
            uuid5(
                _PRODUCTION_STRATEGY_NAMESPACE,
                _semantic_material(
                    target,
                    head,
                    tree,
                    self.symbol,
                    self.strategy_config,
                ),
            ),
        )

    def to_json(self) -> str:
        config = self.strategy_config
        return _canonical_json(
            {
                "schema": self.schema,
                "contract_id": str(self.contract_id),
                "target_session_date": self.target_session_date.isoformat(),
                "source_head": self.source_head,
                "source_tree": self.source_tree,
                "strategy_id": self.strategy_id,
                "strategy_version": self.strategy_version,
                "symbol": str(self.symbol),
                "strategy_config": {
                    "short_window": config.short_window,
                    "long_window": config.long_window,
                    "desired_quantity": _canonical_decimal(config.desired_quantity),
                },
            }
        )

    @classmethod
    def from_json(cls, value: str) -> ProductionStrategyContract:
        """Parse only the exact canonical v1 representation."""
        try:
            if type(value) is not str or not value:
                raise ValueError
            raw = json.loads(value, object_pairs_hook=_unique_object)
            root = _exact_fields(raw, _ROOT_FIELDS)
            if (
                root["schema"] != PRODUCTION_STRATEGY_SCHEMA
                or root["strategy_id"] != MOVING_AVERAGE_STRATEGY_ID
                or root["strategy_version"] != MOVING_AVERAGE_STRATEGY_VERSION
            ):
                raise ValueError
            target_text = root["target_session_date"]
            if type(target_text) is not str:
                raise ValueError
            target = date.fromisoformat(target_text)
            if target.isoformat() != target_text:
                raise ValueError
            symbol_text = root["symbol"]
            if type(symbol_text) is not str:
                raise ValueError
            symbol = Symbol(symbol_text)
            if str(symbol) != symbol_text:
                raise ValueError
            config_raw = _exact_fields(root["strategy_config"], _CONFIG_FIELDS)
            quantity_text = config_raw["desired_quantity"]
            if type(quantity_text) is not str:
                raise ValueError
            quantity = Decimal(quantity_text)
            if _canonical_decimal(quantity) != quantity_text:
                raise ValueError
            config = MovingAverageCrossoverConfig(
                config_raw["short_window"],
                config_raw["long_window"],
                quantity,
            )
            result = cls(
                target,
                _source_digest(root["source_head"], "source_head"),
                _source_digest(root["source_tree"], "source_tree"),
                symbol,
                config,
            )
            contract_id = root["contract_id"]
            if (
                type(contract_id) is not str
                or str(UUID(contract_id)) != contract_id
                or contract_id != str(result.contract_id)
                or result.to_json() != value
            ):
                raise ValueError
            return result
        except (ArithmeticError, KeyError, TypeError, ValueError):
            raise ValueError("invalid production strategy contract") from None


def build_production_strategy(
    contract: ProductionStrategyContract,
) -> MovingAverageCrossoverStrategy:
    """Construct only the existing pure strategy selected by the exact contract."""
    if type(contract) is not ProductionStrategyContract:
        raise TypeError("contract must be exactly ProductionStrategyContract")
    return MovingAverageCrossoverStrategy(contract.strategy_config)


__all__ = [
    "MOVING_AVERAGE_STRATEGY_ID",
    "MOVING_AVERAGE_STRATEGY_VERSION",
    "PRODUCTION_STRATEGY_IDENTITY_VERSION",
    "PRODUCTION_STRATEGY_SCHEMA",
    "ProductionStrategyContract",
    "build_production_strategy",
]
