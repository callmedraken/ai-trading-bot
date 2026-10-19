"""Pure strategy-native semantic compatibility evidence; no runtime authority.

Parsing checks canonical self-consistency only. Public build/verify operations
replay the independently supplied 142 PASS chain before comparing semantics.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, fields
from decimal import Decimal
from uuid import UUID, uuid5

from trading_bot.domain import Symbol
from trading_bot.experiments.research_strategy_walk_forward import (
    CompletedResearchStrategyWalkForward,
    ResearchStrategyWalkForwardQualification,
    ResearchStrategyWalkForwardQualificationPolicy,
    WalkForwardPassedResearchStrategy,
    verify_walk_forward_passed_research_strategy,
)
from trading_bot.strategies.moving_average import MovingAverageCrossoverConfig
from trading_bot.strategies.production import (
    MOVING_AVERAGE_STRATEGY_ID,
    MOVING_AVERAGE_STRATEGY_VERSION,
    PRODUCTION_STRATEGY_SCHEMA,
)

PRODUCTION_STRATEGY_SEMANTIC_TARGET_SCHEMA = "production-strategy-semantic-target/v1"
PRODUCTION_STRATEGY_SEMANTIC_TARGET_IDENTITY_VERSION = (
    "production-strategy-semantic-target-identity/v1"
)
PRODUCTION_STRATEGY_SEMANTIC_TARGET_NAMESPACE = UUID(
    "16be4a92-15d8-5db1-9f92-17a3dbd195f3"
)
RESEARCH_STRATEGY_PRODUCTION_COMPATIBILITY_PROOF_SCHEMA = (
    "research-strategy-production-compatibility-proof/v1"
)
RESEARCH_STRATEGY_PRODUCTION_COMPATIBILITY_PROOF_IDENTITY_VERSION = (
    "research-strategy-production-compatibility-proof-identity/v1"
)
RESEARCH_STRATEGY_PRODUCTION_COMPATIBILITY_PROOF_NAMESPACE = UUID(
    "f9f82ac4-219d-512d-bfe9-a1c07c9427a1"
)

_SHA40 = re.compile(r"[0-9a-f]{40}")
_CHAIN_IDS = (
    "definition_id",
    "evaluation_policy_id",
    "walk_forward_evidence_id",
    "qualification_id",
    "walk_forward_passed_id",
    "production_target_id",
)


class ResearchStrategyProductionCompatibilityError(ValueError):
    """Malformed or externally unreconciled compatibility evidence."""


def _decimal(value: object) -> str:
    if type(value) is not Decimal or not value.is_finite():
        raise ResearchStrategyProductionCompatibilityError("finite Decimal required")
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def _source(value: object) -> str:
    if type(value) is not str or _SHA40.fullmatch(value) is None:
        raise ResearchStrategyProductionCompatibilityError(
            "exact lowercase 40-hex source required"
        )
    return value


def _uuid(value: object) -> UUID:
    if type(value) is not UUID or value.version != 5:
        raise ResearchStrategyProductionCompatibilityError("exact UUID5 required")
    return value


def _parse_uuid(value: object) -> UUID:
    if type(value) is not str:
        raise ResearchStrategyProductionCompatibilityError(
            "canonical UUID text required"
        )
    result = UUID(value)
    if str(result) != value:
        raise ResearchStrategyProductionCompatibilityError(
            "canonical UUID text required"
        )
    return _uuid(result)


def _identity(value: Artifact) -> UUID:
    proof = type(value) is ResearchStrategyProductionCompatibilityProof
    version = (
        RESEARCH_STRATEGY_PRODUCTION_COMPATIBILITY_PROOF_IDENTITY_VERSION
        if proof
        else PRODUCTION_STRATEGY_SEMANTIC_TARGET_IDENTITY_VERSION
    )
    namespace = (
        RESEARCH_STRATEGY_PRODUCTION_COMPATIBILITY_PROOF_NAMESPACE
        if proof
        else PRODUCTION_STRATEGY_SEMANTIC_TARGET_NAMESPACE
    )
    config = value.strategy_config
    prefix = (
        (
            *(str(getattr(value, name)) for name in _CHAIN_IDS),
            value.research_strategy_source_head,
            value.research_strategy_source_tree,
        )
        if proof
        else ()
    )
    suffix = (value.proof_source_head, value.proof_source_tree) if proof else ()
    material = (
        version,
        value.schema,
        *prefix,
        value.production_source_head,
        value.production_source_tree,
        value.production_strategy_schema,
        value.strategy_id,
        value.strategy_version,
        str(value.symbol),
        str(config.short_window),
        str(config.long_window),
        _decimal(config.desired_quantity),
        *suffix,
    )
    return uuid5(
        namespace, "".join(f"{len(item.encode('utf-8'))}:{item}" for item in material)
    )


def _validate(value: Artifact, *, check_identity: bool = True) -> None:
    if type(value) not in (
        ProductionStrategySemanticTarget,
        ResearchStrategyProductionCompatibilityProof,
    ):
        raise ResearchStrategyProductionCompatibilityError(
            "exact artifact type required"
        )
    proof = type(value) is ResearchStrategyProductionCompatibilityProof
    schema = (
        RESEARCH_STRATEGY_PRODUCTION_COMPATIBILITY_PROOF_SCHEMA
        if proof
        else PRODUCTION_STRATEGY_SEMANTIC_TARGET_SCHEMA
    )
    for actual, expected in (
        (value.schema, schema),
        (value.production_strategy_schema, PRODUCTION_STRATEGY_SCHEMA),
        (value.strategy_id, MOVING_AVERAGE_STRATEGY_ID),
        (value.strategy_version, MOVING_AVERAGE_STRATEGY_VERSION),
    ):
        if type(actual) is not str or actual != expected:
            raise ResearchStrategyProductionCompatibilityError(
                "fixed schema/family/version"
            )
    for item in fields(value):
        if item.name.endswith(("_head", "_tree")):
            _source(getattr(value, item.name))
    if type(value.symbol) is not Symbol or Symbol(str(value.symbol)) != value.symbol:
        raise ResearchStrategyProductionCompatibilityError(
            "exact canonical Symbol required"
        )
    config = value.strategy_config
    if type(config) is not MovingAverageCrossoverConfig:
        raise ResearchStrategyProductionCompatibilityError(
            "exact strategy config required"
        )
    if type(config.short_window) is not int or type(config.long_window) is not int:
        raise ResearchStrategyProductionCompatibilityError(
            "exact integer windows required"
        )
    _decimal(config.desired_quantity)
    if (
        MovingAverageCrossoverConfig(
            config.short_window, config.long_window, config.desired_quantity
        )
        != config
    ):
        raise ResearchStrategyProductionCompatibilityError("inconsistent config")
    if proof:
        for name in _CHAIN_IDS:
            _uuid(getattr(value, name))
    if check_identity:
        identity = value.proof_id if proof else value.target_id
        if _uuid(identity) != _identity(value):
            raise ResearchStrategyProductionCompatibilityError(
                "inconsistent artifact identity"
            )


def _to_json(value: Artifact) -> str:
    _validate(value)
    config = value.strategy_config
    raw = {item.name: getattr(value, item.name) for item in fields(value)}
    for name in raw:
        if name.endswith("_id") and type(raw[name]) is UUID:
            raw[name] = str(raw[name])
    raw["symbol"] = str(value.symbol)
    raw["strategy_config"] = {
        "short_window": config.short_window,
        "long_window": config.long_window,
        "desired_quantity": _decimal(config.desired_quantity),
    }
    return json.dumps(raw, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, value in pairs:
        if name in result:
            raise ResearchStrategyProductionCompatibilityError("duplicate JSON field")
        result[name] = value
    return result


def _reject_constant(value: str) -> None:
    raise ResearchStrategyProductionCompatibilityError(f"non-JSON constant {value}")


def _from_json(cls: type[Artifact], value: str) -> Artifact:
    try:
        if cls not in (
            ProductionStrategySemanticTarget,
            ResearchStrategyProductionCompatibilityProof,
        ):
            raise ResearchStrategyProductionCompatibilityError(
                "exact artifact class required"
            )
        if type(value) is not str:
            raise ResearchStrategyProductionCompatibilityError(
                "exact JSON text required"
            )
        raw = json.loads(
            value, object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
        if type(raw) is not dict or set(raw) != {item.name for item in fields(cls)}:
            raise ResearchStrategyProductionCompatibilityError(
                "exact artifact fields required"
            )
        config = raw["strategy_config"]
        if type(config) is not dict or set(config) != {
            "short_window",
            "long_window",
            "desired_quantity",
        }:
            raise ResearchStrategyProductionCompatibilityError(
                "exact config fields required"
            )
        quantity = config["desired_quantity"]
        if type(quantity) is not str or _decimal(Decimal(quantity)) != quantity:
            raise ResearchStrategyProductionCompatibilityError(
                "canonical Decimal text required"
            )
        symbol = raw["symbol"]
        if type(symbol) is not str or str(Symbol(symbol)) != symbol:
            raise ResearchStrategyProductionCompatibilityError(
                "canonical Symbol text required"
            )
        values = {item.name: raw[item.name] for item in fields(cls) if item.init}
        values["symbol"] = Symbol(symbol)
        values["strategy_config"] = MovingAverageCrossoverConfig(
            config["short_window"], config["long_window"], Decimal(quantity)
        )
        for name in _CHAIN_IDS:
            if name in values:
                values[name] = _parse_uuid(values[name])
        result = cls(**values)
        identity_name = (
            "target_id" if cls is ProductionStrategySemanticTarget else "proof_id"
        )
        if (
            _parse_uuid(raw[identity_name]) != getattr(result, identity_name)
            or result.to_json() != value
        ):
            raise ResearchStrategyProductionCompatibilityError(
                "noncanonical or inconsistent JSON"
            )
        return result
    except (ArithmeticError, TypeError, UnicodeError, ValueError) as error:
        if isinstance(error, ResearchStrategyProductionCompatibilityError):
            raise
        raise ResearchStrategyProductionCompatibilityError(
            "invalid artifact JSON"
        ) from None


@dataclass(frozen=True, slots=True)
class ProductionStrategySemanticTarget:
    """Inert exact comparison material with no session or execution authority."""

    schema: str = field(default=PRODUCTION_STRATEGY_SEMANTIC_TARGET_SCHEMA, init=False)
    target_id: UUID = field(init=False)
    production_source_head: str
    production_source_tree: str
    production_strategy_schema: str = field(
        default=PRODUCTION_STRATEGY_SCHEMA, init=False
    )
    strategy_id: str = field(default=MOVING_AVERAGE_STRATEGY_ID, init=False)
    strategy_version: str = field(default=MOVING_AVERAGE_STRATEGY_VERSION, init=False)
    symbol: Symbol
    strategy_config: MovingAverageCrossoverConfig

    def __post_init__(self) -> None:
        _validate(self, check_identity=False)
        object.__setattr__(self, "target_id", _identity(self))

    def to_json(self) -> str:
        """Serialize canonical self-consistent target material."""
        return _to_json(self)

    @classmethod
    def from_json(cls, value: str) -> ProductionStrategySemanticTarget:
        """Parse self-consistency only, without replaying research."""
        return _from_json(cls, value)


@dataclass(frozen=True, slots=True)
class ResearchStrategyProductionCompatibilityProof:
    """Positive semantic assertion; external verification is always separate."""

    schema: str = field(
        default=RESEARCH_STRATEGY_PRODUCTION_COMPATIBILITY_PROOF_SCHEMA, init=False
    )
    proof_id: UUID = field(init=False)
    definition_id: UUID
    evaluation_policy_id: UUID
    walk_forward_evidence_id: UUID
    qualification_id: UUID
    walk_forward_passed_id: UUID
    production_target_id: UUID
    research_strategy_source_head: str
    research_strategy_source_tree: str
    production_source_head: str
    production_source_tree: str
    production_strategy_schema: str = field(
        default=PRODUCTION_STRATEGY_SCHEMA, init=False
    )
    strategy_id: str = field(default=MOVING_AVERAGE_STRATEGY_ID, init=False)
    strategy_version: str = field(default=MOVING_AVERAGE_STRATEGY_VERSION, init=False)
    symbol: Symbol
    strategy_config: MovingAverageCrossoverConfig
    proof_source_head: str
    proof_source_tree: str

    def __post_init__(self) -> None:
        _validate(self, check_identity=False)
        object.__setattr__(self, "proof_id", _identity(self))

    def to_json(self) -> str:
        """Serialize canonical self-consistent proof material."""
        return _to_json(self)

    @classmethod
    def from_json(cls, value: str) -> ResearchStrategyProductionCompatibilityProof:
        """Parse self-consistency only; this does not verify compatibility."""
        return _from_json(cls, value)


type Artifact = (
    ProductionStrategySemanticTarget | ResearchStrategyProductionCompatibilityProof
)


def build_research_strategy_production_compatibility_proof(
    completed: CompletedResearchStrategyWalkForward,
    qualification: ResearchStrategyWalkForwardQualification,
    qualification_policy: ResearchStrategyWalkForwardQualificationPolicy,
    passed: WalkForwardPassedResearchStrategy,
    target: ProductionStrategySemanticTarget,
    *,
    qualification_source_head: str,
    qualification_source_tree: str,
    proof_source_head: str,
    proof_source_tree: str,
) -> ResearchStrategyProductionCompatibilityProof:
    """Replay the complete independent PASS chain before positive projection."""
    verify_walk_forward_passed_research_strategy(
        passed,
        qualification,
        completed,
        qualification_policy,
        qualification_source_head=qualification_source_head,
        qualification_source_tree=qualification_source_tree,
    )
    if type(target) is not ProductionStrategySemanticTarget:
        raise ResearchStrategyProductionCompatibilityError("exact target required")
    _validate(target)
    definition = completed.definition
    for left, right in (
        (definition.production_strategy_schema, target.production_strategy_schema),
        (definition.strategy_id, target.strategy_id),
        (definition.strategy_version, target.strategy_version),
        (definition.symbol, target.symbol),
        (definition.strategy_config, target.strategy_config),
        (definition.strategy_source_head, target.production_source_head),
        (definition.strategy_source_tree, target.production_source_tree),
    ):
        if left != right:
            raise ResearchStrategyProductionCompatibilityError(
                "semantic target does not match"
            )
    _source(proof_source_head)
    _source(proof_source_tree)
    return ResearchStrategyProductionCompatibilityProof(
        definition_id=definition.definition_id,
        evaluation_policy_id=completed.evaluation_policy.policy_id,
        walk_forward_evidence_id=completed.evidence.evidence_id,
        qualification_id=qualification.qualification_id,
        walk_forward_passed_id=passed.passed_id,
        production_target_id=target.target_id,
        research_strategy_source_head=definition.strategy_source_head,
        research_strategy_source_tree=definition.strategy_source_tree,
        production_source_head=target.production_source_head,
        production_source_tree=target.production_source_tree,
        symbol=target.symbol,
        strategy_config=target.strategy_config,
        proof_source_head=proof_source_head,
        proof_source_tree=proof_source_tree,
    )


def verify_research_strategy_production_compatibility_proof(
    proof: ResearchStrategyProductionCompatibilityProof,
    completed: CompletedResearchStrategyWalkForward,
    qualification: ResearchStrategyWalkForwardQualification,
    qualification_policy: ResearchStrategyWalkForwardQualificationPolicy,
    passed: WalkForwardPassedResearchStrategy,
    target: ProductionStrategySemanticTarget,
    *,
    qualification_source_head: str,
    qualification_source_tree: str,
    proof_source_head: str,
    proof_source_tree: str,
) -> None:
    """Rebuild from independent full-chain inputs and require exact equality."""
    if type(proof) is not ResearchStrategyProductionCompatibilityProof:
        raise ResearchStrategyProductionCompatibilityError("exact proof required")
    _validate(proof)
    expected = build_research_strategy_production_compatibility_proof(
        completed,
        qualification,
        qualification_policy,
        passed,
        target,
        qualification_source_head=qualification_source_head,
        qualification_source_tree=qualification_source_tree,
        proof_source_head=proof_source_head,
        proof_source_tree=proof_source_tree,
    )
    if proof != expected:
        raise ResearchStrategyProductionCompatibilityError("proof does not reconcile")


__all__ = [
    "PRODUCTION_STRATEGY_SEMANTIC_TARGET_SCHEMA",
    "PRODUCTION_STRATEGY_SEMANTIC_TARGET_IDENTITY_VERSION",
    "PRODUCTION_STRATEGY_SEMANTIC_TARGET_NAMESPACE",
    "RESEARCH_STRATEGY_PRODUCTION_COMPATIBILITY_PROOF_SCHEMA",
    "RESEARCH_STRATEGY_PRODUCTION_COMPATIBILITY_PROOF_IDENTITY_VERSION",
    "RESEARCH_STRATEGY_PRODUCTION_COMPATIBILITY_PROOF_NAMESPACE",
    "ProductionStrategySemanticTarget",
    "ResearchStrategyProductionCompatibilityProof",
    "ResearchStrategyProductionCompatibilityError",
    "build_research_strategy_production_compatibility_proof",
    "verify_research_strategy_production_compatibility_proof",
]
