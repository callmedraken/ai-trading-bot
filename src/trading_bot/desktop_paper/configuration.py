"""Explicit, immutable strategy configuration for desktop paper evaluation."""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID, uuid5

from trading_bot.desktop_paper.models import PaperAccountState, PaperRuntimePolicy
from trading_bot.domain import Bar, Symbol, TradeProposal
from trading_bot.domain._validation import normalize_utc

PAPER_EVALUATION_CONFIG_SCHEMA = "desktop-paper-evaluation-config/v1"
PAPER_RUNTIME_POLICY_SCHEMA = "simulated-paper-runtime-policy/v1"
PAPER_EVALUATION_REVISION_NAMESPACE = UUID("f2fa8f73-8d90-5c32-974c-609f4e4bb88f")


class PaperEvaluationSelectionRequired(RuntimeError):
    """Raised when a production paper config has no explicit strategy binding."""


@dataclass(frozen=True, slots=True)
class PaperStrategyBinding:
    """Immutable, explicit identity and provenance for one paper strategy."""

    strategy_family: str
    strategy_version: str
    symbol: Symbol
    parameter_set: tuple[tuple[str, str | int | Decimal | bool], ...]
    research_campaign_id: UUID
    research_bundle_id: UUID
    research_candidate_id: UUID
    provenance_digest: str
    purpose: Literal["PAPER_EVALUATION"] = "PAPER_EVALUATION"
    qualification_policy: None = None
    live_eligible: Literal[False] = False

    def __post_init__(self) -> None:
        for name in ("strategy_family", "strategy_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonblank")
        if type(self.symbol) is not Symbol:
            raise TypeError("symbol must be an exact Symbol")
        if type(self.parameter_set) is not tuple:
            raise TypeError("parameter_set must be a tuple")
        parameters: list[tuple[str, str | int | Decimal | bool]] = []
        names: set[str] = set()
        for parameter in self.parameter_set:
            if type(parameter) is not tuple or len(parameter) != 2:
                raise TypeError("parameter_set entries must be key/value pairs")
            name, value = parameter
            if not isinstance(name, str) or not name.strip() or name in names:
                raise ValueError("parameter names must be unique and nonblank")
            if type(value) not in (str, int, Decimal, bool):
                raise TypeError("parameter values must be scalar semantic values")
            if isinstance(value, str) and not value.strip():
                raise ValueError("string parameters must be nonblank")
            if isinstance(value, Decimal) and not value.is_finite():
                raise ValueError("Decimal parameters must be finite")
            names.add(name)
            parameters.append((name, value))

        for name in (
            "research_campaign_id",
            "research_bundle_id",
            "research_candidate_id",
        ):
            if type(getattr(self, name)) is not UUID:
                raise TypeError(f"{name} must be a UUID")
        if (
            not isinstance(self.provenance_digest, str)
            or len(self.provenance_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.provenance_digest
            )
        ):
            raise ValueError("provenance_digest must be lowercase SHA256 hex")
        if self.purpose != "PAPER_EVALUATION":
            raise ValueError("purpose must be PAPER_EVALUATION")
        if self.qualification_policy is not None:
            raise ValueError("qualification_policy must remain None")
        if type(self.live_eligible) is not bool or self.live_eligible:
            raise ValueError("live_eligible must remain False")


@dataclass(frozen=True, slots=True)
class PaperEvaluationConfig:
    """One immutable, revisioned selection and its independent paper policy."""

    binding: PaperStrategyBinding
    policy: PaperRuntimePolicy
    configuration_revision_id: UUID
    schema: Literal["desktop-paper-evaluation-config/v1"] = (
        PAPER_EVALUATION_CONFIG_SCHEMA
    )

    def __post_init__(self) -> None:
        if type(self.binding) is not PaperStrategyBinding:
            raise TypeError("binding must be an exact PaperStrategyBinding")
        if type(self.policy) is not PaperRuntimePolicy:
            raise TypeError("policy must be an exact PaperRuntimePolicy")
        if type(self.configuration_revision_id) is not UUID:
            raise TypeError("configuration_revision_id must be a UUID")
        if self.schema != PAPER_EVALUATION_CONFIG_SCHEMA:
            raise ValueError("unsupported paper evaluation config schema")
        expected = derive_configuration_revision_id(self.binding, self.policy)
        if self.configuration_revision_id != expected:
            raise ValueError("configuration_revision_id does not match config")


def _canonical_decimal(value: Decimal) -> str:
    """Render a finite Decimal without ambient context or exponent notation."""
    if not value.is_finite():
        raise ValueError("identity Decimal values must be finite")
    sign, digits_tuple, exponent = value.as_tuple()
    digits = list(digits_tuple)
    if not any(digits):
        return "0"
    while digits and digits[-1] == 0:
        digits.pop()
        exponent += 1
    digits_text = "".join(str(digit) for digit in digits)
    if exponent >= 0:
        rendered = digits_text + ("0" * exponent)
    else:
        point = len(digits_text) + exponent
        if point > 0:
            rendered = f"{digits_text[:point]}.{digits_text[point:]}"
        else:
            rendered = f"0.{('0' * -point)}{digits_text}"
    return f"-{rendered}" if sign else rendered


def _semantic_value(value: object) -> list[str]:
    if type(value) is Decimal:
        return ["decimal", _canonical_decimal(value)]
    if type(value) is UUID:
        return ["uuid", str(value)]
    if value is None:
        return ["none", ""]
    if type(value) is bool:
        return ["bool", "true" if value else "false"]
    if type(value) is int:
        return ["int", str(value)]
    if type(value) is str:
        return ["str", value]
    raise TypeError(f"unsupported config identity value: {type(value).__name__}")


def _binding_material(binding: PaperStrategyBinding) -> list[object]:
    return [
        binding.strategy_family,
        binding.strategy_version,
        binding.symbol.value,
        [[name, _semantic_value(value)] for name, value in binding.parameter_set],
        str(binding.research_campaign_id),
        str(binding.research_bundle_id),
        str(binding.research_candidate_id),
        binding.provenance_digest,
        binding.purpose,
        binding.qualification_policy,
        binding.live_eligible,
    ]


def _policy_material(policy: PaperRuntimePolicy) -> list[list[object]]:
    return [
        [field.name, _semantic_value(getattr(policy, field.name))]
        for field in fields(policy)
    ]


def derive_configuration_revision_id(
    binding: PaperStrategyBinding,
    policy: PaperRuntimePolicy,
) -> UUID:
    """Derive an immutable revision from versioned semantic config material."""
    if type(binding) is not PaperStrategyBinding:
        raise TypeError("binding must be an exact PaperStrategyBinding")
    if type(policy) is not PaperRuntimePolicy:
        raise TypeError("policy must be an exact PaperRuntimePolicy")
    material = [
        PAPER_EVALUATION_CONFIG_SCHEMA,
        PAPER_RUNTIME_POLICY_SCHEMA,
        _binding_material(binding),
        _policy_material(policy),
    ]
    canonical = json.dumps(material, ensure_ascii=True, separators=(",", ":"))
    return uuid5(PAPER_EVALUATION_REVISION_NAMESPACE, canonical)


def create_paper_evaluation_config(
    binding: PaperStrategyBinding | None,
    policy: PaperRuntimePolicy,
) -> PaperEvaluationConfig:
    """Create a config only from an explicit binding; no strategy is selected here."""
    if binding is None:
        raise PaperEvaluationSelectionRequired("PAPER_EVALUATION_SELECTION_REQUIRED")
    revision = derive_configuration_revision_id(binding, policy)
    return PaperEvaluationConfig(binding, policy, revision)


@dataclass(frozen=True, slots=True)
class PaperStrategyEvaluationInput:
    """Prior history/account for an evaluator; prior marked values may be stale."""

    binding: PaperStrategyBinding
    completed_history: tuple[Bar, ...]
    execution_timestamp: datetime
    prior_account: PaperAccountState | None = None

    def __post_init__(self) -> None:
        if type(self.binding) is not PaperStrategyBinding:
            raise TypeError("binding must be an exact PaperStrategyBinding")
        if (
            self.prior_account is not None
            and type(self.prior_account) is not PaperAccountState
        ):
            raise TypeError(
                "prior_account must be an exact immutable PaperAccountState"
            )
        history = tuple(self.completed_history)
        previous = None
        for bar in history:
            if type(bar) is not Bar or bar.symbol != self.binding.symbol:
                raise ValueError("completed history must contain matching Bars")
            if previous is not None and bar.timestamp <= previous:
                raise ValueError("completed history must be strictly chronological")
            previous = bar.timestamp
        try:
            execution_timestamp = normalize_utc(
                self.execution_timestamp, "execution_timestamp"
            )
        except (TypeError, ValueError) as error:
            raise ValueError("execution_timestamp must be a UTC datetime") from error
        if previous is not None and previous >= execution_timestamp:
            raise ValueError("strategy history must end before execution")
        object.__setattr__(self, "completed_history", history)
        object.__setattr__(self, "execution_timestamp", execution_timestamp)


class PaperStrategyEvaluator(Protocol):
    """Narrow injection point; no plugins, expressions or default strategy."""

    def evaluate(
        self, evaluation_input: PaperStrategyEvaluationInput
    ) -> TradeProposal | None: ...
