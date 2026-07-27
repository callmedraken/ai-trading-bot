"""Strict caller-authored configuration for one verified snapshot paper cycle."""

# ruff: noqa: E501

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import UUID

from trading_bot.cli.exceptions import (
    VerifiedSnapshotPaperCycleConfigJsonError,
    VerifiedSnapshotPaperCycleConfigReadError,
    VerifiedSnapshotPaperCycleConfigValidationError,
)
from trading_bot.domain import Symbol
from trading_bot.execution import PaperFillPolicy
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data import canonical_decimal
from trading_bot.portfolio import MetadataEntry, PortfolioConstraints
from trading_bot.rebalancing import RebalanceAssumptions, RebalanceProposalPolicy
from trading_bot.risk import PortfolioRiskPolicy, RiskLimits
from trading_bot.runtime import (
    CallerAssertedNextSessionOpenReference,
    ExplicitQuantityTarget,
    ExplicitQuantityTargetPortfolio,
    VerifiedDailySnapshotReference,
    VerifiedSnapshotAccountPosition,
    VerifiedSnapshotAccountState,
    VerifiedSnapshotPaperCyclePolicies,
    VerifiedSnapshotPaperCyclePreparationRequest,
)

VERIFIED_SNAPSHOT_PAPER_CYCLE_CONFIG_SCHEMA_VERSION = 1
MAX_VERIFIED_SNAPSHOT_PAPER_CYCLE_CONFIG_BYTES = 256 * 1024

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{6})?Z$"
)
_DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

_ROOT_FIELDS = frozenset(
    {
        "account_state",
        "filled_at",
        "metadata",
        "open_references",
        "planning_at",
        "policies",
        "request_id",
        "schema_version",
        "snapshot_reference",
        "submitted_at",
        "target",
    }
)
_SNAPSHOT_FIELDS = frozenset({"artifact_byte_length", "artifact_sha256", "snapshot_id"})
_ACCOUNT_FIELDS = frozenset({"account_state_id", "as_of", "cash", "positions"})
_POSITION_FIELDS = frozenset({"average_cost", "quantity", "symbol"})
_TARGET_FIELDS = frozenset({"quantities", "target_cash", "target_id"})
_QUANTITY_FIELDS = frozenset({"quantity", "symbol"})
_OPEN_REFERENCE_FIELDS = frozenset(
    {"caller_asserted_open_reference_price", "session", "symbol"}
)
_POLICY_FIELDS = frozenset(
    {
        "fill_policy",
        "portfolio_constraints",
        "proposal_confidence",
        "proposal_policy",
        "rebalance_assumptions",
        "risk_limits",
        "risk_policy",
        "trading_enabled",
    }
)
_ASSUMPTION_FIELDS = frozenset(
    {
        "additional_execution_cash_buffer",
        "allow_fractional_quantities",
        "fixed_commission",
        "minimum_trade_notional",
        "minimum_trade_quantity",
        "quantity_increment",
        "target_weight_tolerance",
        "use_planned_sell_proceeds",
    }
)
_CONSTRAINT_FIELDS = frozenset(
    {
        "allow_leverage",
        "long_only",
        "maximum_cash_weight",
        "maximum_one_way_rebalance_turnover",
        "maximum_position_weight",
        "minimum_cash_weight",
        "minimum_position_weight",
    }
)
_PROPOSAL_POLICY_FIELDS = frozenset({"allow_partial_plans"})
_RISK_LIMIT_FIELDS = frozenset(
    {
        "allow_buying",
        "allow_fractional_shares",
        "allow_selling",
        "estimated_commission",
        "fractional_increment",
        "max_new_position_percent",
        "max_order_notional",
        "max_position_percent",
        "max_total_exposure_percent",
        "minimum_cash_reserve_percent",
    }
)
_RISK_POLICY_FIELDS = frozenset({"allow_sell_proceeds_for_later_buys"})
_FILL_POLICY_FIELDS = frozenset({"fixed_commission", "slippage_basis_points"})
_METADATA_FIELDS = frozenset({"key", "value"})


@dataclass(frozen=True, slots=True)
class VerifiedSnapshotPaperCycleConfig:
    """Complete nonsecret caller intent for one preparation request."""

    preparation_request: VerifiedSnapshotPaperCyclePreparationRequest
    schema_version: int = VERIFIED_SNAPSHOT_PAPER_CYCLE_CONFIG_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if (
            type(self.preparation_request)
            is not VerifiedSnapshotPaperCyclePreparationRequest
        ):
            raise VerifiedSnapshotPaperCycleConfigValidationError(
                "preparation_request must be an exact preparation request"
            )
        if (
            type(self.schema_version) is not int
            or self.schema_version
            != VERIFIED_SNAPSHOT_PAPER_CYCLE_CONFIG_SCHEMA_VERSION
        ):
            raise VerifiedSnapshotPaperCycleConfigValidationError(
                "schema_version must be 1"
            )


def load_verified_snapshot_paper_cycle_config(
    path: Path,
) -> VerifiedSnapshotPaperCycleConfig:
    """Read one bounded strict JSON configuration without external access."""
    if not isinstance(path, Path):
        raise VerifiedSnapshotPaperCycleConfigReadError("configuration path is invalid")
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise VerifiedSnapshotPaperCycleConfigReadError(
            "cycle configuration cannot be read"
        ) from error
    return parse_verified_snapshot_paper_cycle_config(payload)


def parse_verified_snapshot_paper_cycle_config(
    payload: bytes,
) -> VerifiedSnapshotPaperCycleConfig:
    """Parse exact schema-1 configuration bytes into public immutable inputs."""
    if type(payload) is not bytes:
        raise VerifiedSnapshotPaperCycleConfigReadError(
            "cycle configuration must be exact bytes"
        )
    if len(payload) > MAX_VERIFIED_SNAPSHOT_PAPER_CYCLE_CONFIG_BYTES:
        raise VerifiedSnapshotPaperCycleConfigReadError(
            "cycle configuration exceeds the 256 KiB limit"
        )
    if payload.startswith(b"\xef\xbb\xbf"):
        raise VerifiedSnapshotPaperCycleConfigJsonError(
            "cycle configuration must not contain a UTF-8 BOM"
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise VerifiedSnapshotPaperCycleConfigJsonError(
            "cycle configuration is not valid UTF-8"
        ) from error
    try:
        root = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
            parse_float=_reject_float,
        )
    except VerifiedSnapshotPaperCycleConfigJsonError:
        raise
    except json.JSONDecodeError as error:
        raise VerifiedSnapshotPaperCycleConfigJsonError(
            "cycle configuration is not valid strict JSON"
        ) from error
    return _parse(root)


def _parse(root: object) -> VerifiedSnapshotPaperCycleConfig:
    value = _object(root, _ROOT_FIELDS, "configuration")
    if _integer(value["schema_version"], "schema_version") != 1:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            "schema_version must be 1"
        )
    try:
        request = VerifiedSnapshotPaperCyclePreparationRequest(
            request_id=_uuid(value["request_id"], "request_id"),
            snapshot_reference=_snapshot_reference(value["snapshot_reference"]),
            account_state=_account_state(value["account_state"]),
            target=_target(value["target"]),
            open_references=_open_references(value["open_references"]),
            policies=_policies(value["policies"]),
            planning_at=_timestamp(value["planning_at"], "planning_at"),
            submitted_at=_timestamp(value["submitted_at"], "submitted_at"),
            filled_at=_timestamp(value["filled_at"], "filled_at"),
            metadata=_metadata(value["metadata"]),
        )
        return VerifiedSnapshotPaperCycleConfig(request)
    except (TypeError, ValueError) as error:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            "configuration contains an invalid cycle value"
        ) from error


def _snapshot_reference(value: object) -> VerifiedDailySnapshotReference:
    item = _object(value, _SNAPSHOT_FIELDS, "snapshot_reference")
    sha256 = _string(item["artifact_sha256"], "snapshot_reference.artifact_sha256")
    if _SHA256_PATTERN.fullmatch(sha256) is None:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            "snapshot_reference.artifact_sha256 must be lowercase SHA-256 text"
        )
    try:
        return VerifiedDailySnapshotReference(
            _uuid(item["snapshot_id"], "snapshot_reference.snapshot_id"),
            sha256,
            _positive_integer(
                item["artifact_byte_length"],
                "snapshot_reference.artifact_byte_length",
            ),
        )
    except (TypeError, ValueError) as error:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            "snapshot_reference is invalid"
        ) from error


def _account_state(value: object) -> VerifiedSnapshotAccountState:
    item = _object(value, _ACCOUNT_FIELDS, "account_state")
    positions = _array(item["positions"], "account_state.positions")
    try:
        return VerifiedSnapshotAccountState(
            _uuid(item["account_state_id"], "account_state.account_state_id"),
            _timestamp(item["as_of"], "account_state.as_of"),
            _decimal(item["cash"], "account_state.cash"),
            tuple(
                VerifiedSnapshotAccountPosition(
                    _symbol(
                        _object(
                            entry, _POSITION_FIELDS, f"account_state.positions[{index}]"
                        )["symbol"],
                        f"account_state.positions[{index}].symbol",
                    ),
                    _decimal(
                        _object(
                            entry, _POSITION_FIELDS, f"account_state.positions[{index}]"
                        )["quantity"],
                        f"account_state.positions[{index}].quantity",
                    ),
                    _decimal(
                        _object(
                            entry, _POSITION_FIELDS, f"account_state.positions[{index}]"
                        )["average_cost"],
                        f"account_state.positions[{index}].average_cost",
                    ),
                )
                for index, entry in enumerate(positions)
            ),
        )
    except (TypeError, ValueError) as error:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            "account_state is invalid"
        ) from error


def _target(value: object) -> ExplicitQuantityTargetPortfolio:
    item = _object(value, _TARGET_FIELDS, "target")
    quantities = _array(item["quantities"], "target.quantities")
    try:
        return ExplicitQuantityTargetPortfolio(
            _uuid(item["target_id"], "target.target_id"),
            tuple(
                ExplicitQuantityTarget(
                    _symbol(
                        _object(entry, _QUANTITY_FIELDS, f"target.quantities[{index}]")[
                            "symbol"
                        ],
                        f"target.quantities[{index}].symbol",
                    ),
                    _decimal(
                        _object(entry, _QUANTITY_FIELDS, f"target.quantities[{index}]")[
                            "quantity"
                        ],
                        f"target.quantities[{index}].quantity",
                    ),
                )
                for index, entry in enumerate(quantities)
            ),
            _decimal(item["target_cash"], "target.target_cash"),
        )
    except (TypeError, ValueError) as error:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            "target is invalid"
        ) from error


def _open_references(
    value: object,
) -> tuple[CallerAssertedNextSessionOpenReference, ...]:
    items = _array(value, "open_references")
    try:
        return tuple(
            CallerAssertedNextSessionOpenReference(
                _symbol(
                    _object(item, _OPEN_REFERENCE_FIELDS, f"open_references[{index}]")[
                        "symbol"
                    ],
                    f"open_references[{index}].symbol",
                ),
                TradingSession(
                    _date(
                        _object(
                            item, _OPEN_REFERENCE_FIELDS, f"open_references[{index}]"
                        )["session"],
                        f"open_references[{index}].session",
                    )
                ),
                _decimal(
                    _object(item, _OPEN_REFERENCE_FIELDS, f"open_references[{index}]")[
                        "caller_asserted_open_reference_price"
                    ],
                    f"open_references[{index}].caller_asserted_open_reference_price",
                ),
            )
            for index, item in enumerate(items)
        )
    except (TypeError, ValueError) as error:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            "open_references are invalid"
        ) from error


def _policies(value: object) -> VerifiedSnapshotPaperCyclePolicies:
    item = _object(value, _POLICY_FIELDS, "policies")
    assumptions = _assumptions(item["rebalance_assumptions"])
    constraints = _constraints(item["portfolio_constraints"])
    proposal = _proposal_policy(item["proposal_policy"])
    confidence = (
        None
        if item["proposal_confidence"] is None
        else _decimal(item["proposal_confidence"], "policies.proposal_confidence")
    )
    limits = _risk_limits(item["risk_limits"])
    risk_policy = _risk_policy(item["risk_policy"])
    fill_policy = _fill_policy(item["fill_policy"])
    try:
        return VerifiedSnapshotPaperCyclePolicies(
            assumptions,
            constraints,
            proposal,
            confidence,
            limits,
            risk_policy,
            fill_policy,
            _boolean(item["trading_enabled"], "policies.trading_enabled"),
        )
    except (TypeError, ValueError) as error:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            "policies are invalid"
        ) from error


def _assumptions(value: object) -> RebalanceAssumptions:
    item = _object(value, _ASSUMPTION_FIELDS, "policies.rebalance_assumptions")
    try:
        return RebalanceAssumptions(
            fixed_commission=_decimal(
                item["fixed_commission"],
                "policies.rebalance_assumptions.fixed_commission",
            ),
            allow_fractional_quantities=_boolean(
                item["allow_fractional_quantities"],
                "policies.rebalance_assumptions.allow_fractional_quantities",
            ),
            quantity_increment=_decimal(
                item["quantity_increment"],
                "policies.rebalance_assumptions.quantity_increment",
            ),
            minimum_trade_notional=_decimal(
                item["minimum_trade_notional"],
                "policies.rebalance_assumptions.minimum_trade_notional",
            ),
            minimum_trade_quantity=_decimal(
                item["minimum_trade_quantity"],
                "policies.rebalance_assumptions.minimum_trade_quantity",
            ),
            target_weight_tolerance=_decimal(
                item["target_weight_tolerance"],
                "policies.rebalance_assumptions.target_weight_tolerance",
            ),
            additional_execution_cash_buffer=_decimal(
                item["additional_execution_cash_buffer"],
                "policies.rebalance_assumptions.additional_execution_cash_buffer",
            ),
            use_planned_sell_proceeds=_boolean(
                item["use_planned_sell_proceeds"],
                "policies.rebalance_assumptions.use_planned_sell_proceeds",
            ),
        )
    except (TypeError, ValueError) as error:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            "rebalance_assumptions are invalid"
        ) from error


def _constraints(value: object) -> PortfolioConstraints | None:
    if value is None:
        return None
    item = _object(value, _CONSTRAINT_FIELDS, "policies.portfolio_constraints")
    try:
        return PortfolioConstraints(
            minimum_cash_weight=_decimal(
                item["minimum_cash_weight"],
                "policies.portfolio_constraints.minimum_cash_weight",
            ),
            maximum_cash_weight=_decimal(
                item["maximum_cash_weight"],
                "policies.portfolio_constraints.maximum_cash_weight",
            ),
            maximum_position_weight=_decimal(
                item["maximum_position_weight"],
                "policies.portfolio_constraints.maximum_position_weight",
            ),
            maximum_one_way_rebalance_turnover=_optional_decimal(
                item["maximum_one_way_rebalance_turnover"],
                "policies.portfolio_constraints.maximum_one_way_rebalance_turnover",
            ),
            minimum_position_weight=_optional_decimal(
                item["minimum_position_weight"],
                "policies.portfolio_constraints.minimum_position_weight",
            ),
            long_only=_boolean(
                item["long_only"], "policies.portfolio_constraints.long_only"
            ),
            allow_leverage=_boolean(
                item["allow_leverage"], "policies.portfolio_constraints.allow_leverage"
            ),
        )
    except (TypeError, ValueError) as error:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            "portfolio_constraints are invalid"
        ) from error


def _proposal_policy(value: object) -> RebalanceProposalPolicy:
    item = _object(value, _PROPOSAL_POLICY_FIELDS, "policies.proposal_policy")
    try:
        return RebalanceProposalPolicy(
            _boolean(
                item["allow_partial_plans"],
                "policies.proposal_policy.allow_partial_plans",
            )
        )
    except (TypeError, ValueError) as error:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            "proposal_policy is invalid"
        ) from error


def _risk_limits(value: object) -> RiskLimits:
    item = _object(value, _RISK_LIMIT_FIELDS, "policies.risk_limits")
    try:
        return RiskLimits(
            max_position_percent=_decimal(
                item["max_position_percent"],
                "policies.risk_limits.max_position_percent",
            ),
            max_total_exposure_percent=_decimal(
                item["max_total_exposure_percent"],
                "policies.risk_limits.max_total_exposure_percent",
            ),
            max_order_notional=_optional_decimal(
                item["max_order_notional"], "policies.risk_limits.max_order_notional"
            ),
            max_new_position_percent=_optional_decimal(
                item["max_new_position_percent"],
                "policies.risk_limits.max_new_position_percent",
            ),
            minimum_cash_reserve_percent=_decimal(
                item["minimum_cash_reserve_percent"],
                "policies.risk_limits.minimum_cash_reserve_percent",
            ),
            allow_fractional_shares=_boolean(
                item["allow_fractional_shares"],
                "policies.risk_limits.allow_fractional_shares",
            ),
            fractional_increment=_decimal(
                item["fractional_increment"],
                "policies.risk_limits.fractional_increment",
            ),
            allow_buying=_boolean(
                item["allow_buying"], "policies.risk_limits.allow_buying"
            ),
            allow_selling=_boolean(
                item["allow_selling"], "policies.risk_limits.allow_selling"
            ),
            estimated_commission=_decimal(
                item["estimated_commission"],
                "policies.risk_limits.estimated_commission",
            ),
        )
    except (TypeError, ValueError) as error:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            "risk_limits are invalid"
        ) from error


def _risk_policy(value: object) -> PortfolioRiskPolicy:
    item = _object(value, _RISK_POLICY_FIELDS, "policies.risk_policy")
    try:
        return PortfolioRiskPolicy(
            _boolean(
                item["allow_sell_proceeds_for_later_buys"],
                "policies.risk_policy.allow_sell_proceeds_for_later_buys",
            )
        )
    except (TypeError, ValueError) as error:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            "risk_policy is invalid"
        ) from error


def _fill_policy(value: object) -> PaperFillPolicy:
    item = _object(value, _FILL_POLICY_FIELDS, "policies.fill_policy")
    try:
        return PaperFillPolicy(
            slippage_basis_points=_decimal(
                item["slippage_basis_points"],
                "policies.fill_policy.slippage_basis_points",
            ),
            fixed_commission=_decimal(
                item["fixed_commission"], "policies.fill_policy.fixed_commission"
            ),
        )
    except (TypeError, ValueError) as error:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            "fill_policy is invalid"
        ) from error


def _metadata(value: object) -> tuple[MetadataEntry, ...]:
    items = _array(value, "metadata")
    try:
        return tuple(
            MetadataEntry(
                _string(
                    _object(item, _METADATA_FIELDS, f"metadata[{index}]")["key"],
                    f"metadata[{index}].key",
                ),
                _string(
                    _object(item, _METADATA_FIELDS, f"metadata[{index}]")["value"],
                    f"metadata[{index}].value",
                ),
            )
            for index, item in enumerate(items)
        )
    except (TypeError, ValueError) as error:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            "metadata is invalid"
        ) from error


def _object(value: object, fields: frozenset[str], path: str) -> dict[str, object]:
    if type(value) is not dict or frozenset(value) != fields:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            f"{path} must contain exactly the required fields"
        )
    return value


def _array(value: object, path: str) -> list[object]:
    if type(value) is not list:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            f"{path} must be an array"
        )
    return value


def _string(value: object, path: str) -> str:
    if type(value) is not str:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            f"{path} must be a string"
        )
    return value


def _integer(value: object, path: str) -> int:
    if type(value) is not int:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            f"{path} must be an integer"
        )
    return value


def _positive_integer(value: object, path: str) -> int:
    result = _integer(value, path)
    if result <= 0:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            f"{path} must be positive"
        )
    return result


def _boolean(value: object, path: str) -> bool:
    if type(value) is not bool:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            f"{path} must be a boolean"
        )
    return value


def _uuid(value: object, path: str) -> UUID:
    text = _string(value, path)
    try:
        parsed = UUID(text)
    except ValueError as error:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            f"{path} must be a canonical UUID"
        ) from error
    if str(parsed) != text:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            f"{path} must be a canonical UUID"
        )
    return parsed


def _symbol(value: object, path: str) -> Symbol:
    text = _string(value, path)
    try:
        parsed = Symbol(text)
    except (TypeError, ValueError) as error:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            f"{path} is not a canonical symbol"
        ) from error
    if str(parsed) != text:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            f"{path} is not a canonical symbol"
        )
    return parsed


def _decimal(value: object, path: str) -> Decimal:
    text = _string(value, path)
    try:
        parsed = Decimal(text)
    except InvalidOperation as error:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            f"{path} must be a Decimal string"
        ) from error
    if not parsed.is_finite() or canonical_decimal(parsed) != text:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            f"{path} must be an exponent-free canonical Decimal string"
        )
    return parsed


def _optional_decimal(value: object, path: str) -> Decimal | None:
    return None if value is None else _decimal(value, path)


def _timestamp(value: object, path: str) -> datetime:
    text = _string(value, path)
    if _TIMESTAMP_PATTERN.fullmatch(text) is None:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            f"{path} must be a canonical UTC timestamp"
        )
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00").astimezone(UTC)
    except ValueError as error:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            f"{path} is not a valid UTC timestamp"
        ) from error
    if _canonical_timestamp(parsed) != text:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            f"{path} must be a canonical UTC timestamp"
        )
    return parsed


def _canonical_timestamp(value: datetime) -> str:
    normalized = value.astimezone(UTC)
    timespec = "seconds" if normalized.microsecond == 0 else "microseconds"
    return normalized.isoformat(timespec=timespec).replace("+00:00", "Z")


def _date(value: object, path: str) -> date:
    text = _string(value, path)
    if _DATE_PATTERN.fullmatch(text) is None:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            f"{path} must be a canonical ISO date"
        )
    try:
        parsed = date.fromisoformat(text)
    except ValueError as error:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            f"{path} is not a valid date"
        ) from error
    if parsed.isoformat() != text:
        raise VerifiedSnapshotPaperCycleConfigValidationError(
            f"{path} must be a canonical ISO date"
        )
    return parsed


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise VerifiedSnapshotPaperCycleConfigJsonError(
                "cycle configuration contains a duplicate key"
            )
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise VerifiedSnapshotPaperCycleConfigJsonError(
        f"nonstandard JSON constant is not permitted: {value}"
    )


def _reject_float(value: str) -> None:
    raise VerifiedSnapshotPaperCycleConfigJsonError(
        f"JSON floating-point number is not permitted: {value}"
    )
