"""Deterministic strategy-native walk-forward research evidence.

This module is the pure Architecture-142-B continuation of the accepted
strategy-native single-symbol backtest runner.  It slices only one caller-
supplied immutable historical result, evaluates every fold independently, and
records qualification as research evidence.  It has no provider, filesystem,
clock, runtime, promotion, or production authority.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.experiments.research_strategy_backtest import (
    CompletedResearchStrategyBacktest,
    ResearchStrategyBacktestError,
    canonical_single_symbol_historical_material,
    derive_backtest_run_id,
    historical_data_fingerprint,
    run_research_strategy_backtest,
    verify_research_strategy_backtest,
)
from trading_bot.experiments.research_strategy_definition import (
    ResearchStrategyDefinition,
    ResearchStrategyDefinitionError,
    ResearchStrategyEvaluationPolicy,
)
from trading_bot.market_data.models import (
    HistoricalDataRequest,
    HistoricalDataResult,
)

RESEARCH_STRATEGY_WALK_FORWARD_EVIDENCE_SCHEMA = (
    "research-strategy-walk-forward-evidence/v1"
)
RESEARCH_STRATEGY_WALK_FORWARD_EVIDENCE_NAMESPACE = UUID(
    "18a84b75-90fe-546a-8444-0bb6bfd495dd"
)
RESEARCH_STRATEGY_WALK_FORWARD_EVIDENCE_IDENTITY_VERSION = (
    "research-strategy-walk-forward-evidence-identity/v1"
)
RESEARCH_STRATEGY_WALK_FORWARD_FOLD_IDENTITY_VERSION = (
    "research-strategy-walk-forward-fold-identity/v1"
)
RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_POLICY_SCHEMA = (
    "research-strategy-walk-forward-qualification-policy/v1"
)
RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_POLICY_NAMESPACE = UUID(
    "e865a7f0-abad-5352-b2f8-8ff500ebebc9"
)
RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_POLICY_IDENTITY_VERSION = (
    "research-strategy-walk-forward-qualification-policy-identity/v1"
)
RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_SCHEMA = (
    "research-strategy-walk-forward-qualification/v1"
)
RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_NAMESPACE = UUID(
    "44710283-8780-58d4-b34b-dce20d66447f"
)
RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_IDENTITY_VERSION = (
    "research-strategy-walk-forward-qualification-identity/v1"
)
RESEARCH_STRATEGY_WALK_FORWARD_PASSED_SCHEMA = (
    "research-strategy-walk-forward-passed/v1"
)
RESEARCH_STRATEGY_WALK_FORWARD_PASSED_NAMESPACE = UUID(
    "f3e48591-0eb4-5c26-a15b-2f8863ada223"
)
RESEARCH_STRATEGY_WALK_FORWARD_PASSED_IDENTITY_VERSION = (
    "research-strategy-walk-forward-passed-identity/v1"
)

TRAINING_FOLD_ROLE = "TRAINING"
TEST_FOLD_ROLE = "TEST"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_ZERO = Decimal("0")


class ResearchStrategyWalkForwardError(ValueError):
    """Raised for malformed, unreconcilable, or unverifiable 142-B evidence."""


class ResearchStrategyWalkForwardQualificationStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"


class ResearchStrategyWalkForwardFailureReason(StrEnum):
    INSUFFICIENT_FOLDS = "INSUFFICIENT_FOLDS"
    NONCOMPARABLE_TEST_WINDOWS = "NONCOMPARABLE_TEST_WINDOWS"
    MINIMUM_FOLD_RETURN_BELOW_THRESHOLD = "MINIMUM_FOLD_RETURN_BELOW_THRESHOLD"
    MEDIAN_FOLD_RETURN_BELOW_THRESHOLD = "MEDIAN_FOLD_RETURN_BELOW_THRESHOLD"
    MAXIMUM_FOLD_DRAWDOWN_PERCENTAGE_ABOVE_THRESHOLD = (
        "MAXIMUM_FOLD_DRAWDOWN_PERCENTAGE_ABOVE_THRESHOLD"
    )

    # Retained descriptive aliases make the threshold vocabulary explicit
    # without changing the canonical serialized reason values.
    MINIMUM_SIMULATION_RETURN_BELOW_THRESHOLD = "MINIMUM_FOLD_RETURN_BELOW_THRESHOLD"
    MEDIAN_SIMULATION_RETURN_BELOW_THRESHOLD = "MEDIAN_FOLD_RETURN_BELOW_THRESHOLD"


_FOLD_FIELDS = frozenset(
    {"fold_id", "training_start", "training_end", "test_start", "test_end"}
)
_FOLD_EVIDENCE_FIELDS = frozenset(
    {
        "fold_id",
        "training_backtest_evidence_id",
        "test_backtest_evidence_id",
        "training_start",
        "training_end",
        "test_start",
        "test_end",
        "training_historical_fingerprint",
        "test_historical_fingerprint",
        "training_bar_count",
        "test_bar_count",
    }
)
_WALK_FORWARD_EVIDENCE_FIELDS = frozenset(
    {
        "schema",
        "evidence_id",
        "definition_id",
        "evaluation_policy_id",
        "evaluation_source_head",
        "evaluation_source_tree",
        "source_historical_fingerprint",
        "folds",
    }
)
_POLICY_FIELDS = frozenset(
    {
        "schema",
        "policy_id",
        "minimum_fold_count",
        "minimum_fold_return",
        "minimum_median_return",
        "maximum_fold_drawdown_percentage",
        "require_equal_test_window_bar_count",
    }
)
_QUALIFICATION_FIELDS = frozenset(
    {
        "schema",
        "qualification_id",
        "definition_id",
        "evaluation_policy_id",
        "qualification_source_head",
        "qualification_source_tree",
        "source_historical_fingerprint",
        "walk_forward_evidence_id",
        "policy",
        "policy_id",
        "fold_count",
        "test_window_bar_counts",
        "test_windows_comparable",
        "minimum_observed_fold_return",
        "median_fold_return",
        "maximum_observed_fold_drawdown_percentage",
        "status",
        "failure_reasons",
    }
)
_PASSED_FIELDS = frozenset(
    {
        "schema",
        "passed_id",
        "definition_id",
        "evaluation_policy_id",
        "qualification_id",
        "walk_forward_evidence_id",
        "source_head",
        "source_tree",
    }
)


def _frame(value: str) -> str:
    try:
        return f"{len(value.encode('utf-8'))}:{value}"
    except UnicodeError:
        raise ResearchStrategyWalkForwardError("identity text must be UTF-8") from None


def _identity(namespace: UUID, version: str, values: tuple[str, ...]) -> UUID:
    return uuid5(namespace, "".join(_frame(value) for value in (version, *values)))


def _decimal(value: object, name: str) -> str:
    if type(value) is not Decimal or not value.is_finite():
        raise ResearchStrategyWalkForwardError(f"{name} must be a finite Decimal")
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return "0" if rendered in {"", "-0"} else rendered


def _parse_decimal(value: object, name: str) -> Decimal:
    if type(value) is not str:
        raise ResearchStrategyWalkForwardError(f"{name} must be canonical Decimal text")
    try:
        parsed = Decimal(value)
    except ArithmeticError:
        raise ResearchStrategyWalkForwardError(f"{name} must be a Decimal") from None
    if _decimal(parsed, name) != value:
        raise ResearchStrategyWalkForwardError(f"{name} is not canonical Decimal text")
    return parsed


def _uuid(value: object, name: str) -> UUID:
    if type(value) is not UUID:
        raise ResearchStrategyWalkForwardError(f"{name} must be exactly UUID")
    return value


def _parse_uuid(value: object, name: str) -> UUID:
    if type(value) is not str:
        raise ResearchStrategyWalkForwardError(f"{name} must be canonical UUID text")
    try:
        parsed = UUID(value)
    except ValueError:
        raise ResearchStrategyWalkForwardError(
            f"{name} must be canonical UUID text"
        ) from None
    if str(parsed) != value:
        raise ResearchStrategyWalkForwardError(f"{name} must be canonical UUID text")
    return parsed


def _source(value: object, name: str) -> str:
    if type(value) is not str or _SHA40.fullmatch(value) is None:
        raise ResearchStrategyWalkForwardError(
            f"{name} must be exact lowercase 40-hex text"
        )
    return value


def _timestamp(value: object, name: str) -> str:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ResearchStrategyWalkForwardError(f"{name} must be aware datetime")
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _normalized_timestamp(value: object, name: str) -> datetime:
    text = _timestamp(value, name)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ResearchStrategyWalkForwardError(f"{name} is invalid") from None


def _parse_timestamp(value: object, name: str) -> datetime:
    if type(value) is not str:
        raise ResearchStrategyWalkForwardError(
            f"{name} must be canonical timestamp text"
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ResearchStrategyWalkForwardError(
            f"{name} must be canonical timestamp text"
        ) from None
    if _timestamp(parsed, name) != value:
        raise ResearchStrategyWalkForwardError(
            f"{name} is not canonical timestamp text"
        )
    return parsed.astimezone(UTC)


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ResearchStrategyWalkForwardError("duplicate JSON field")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ResearchStrategyWalkForwardError(f"non-JSON constant {value} is forbidden")


def _exact_fields(value: object, expected: frozenset[str]) -> dict[str, object]:
    if type(value) is not dict or set(value) != expected:
        raise ResearchStrategyWalkForwardError("exact canonical fields required")
    return value


def _integer(value: object, name: str, *, positive: bool = False) -> int:
    if type(value) is not int or isinstance(value, bool):
        raise ResearchStrategyWalkForwardError(f"{name} must be an integer")
    if positive and value <= 0:
        raise ResearchStrategyWalkForwardError(f"{name} must be positive")
    return value


def _fold_material(fold: ResearchStrategyWalkForwardFold) -> tuple[str, ...]:
    return (
        RESEARCH_STRATEGY_WALK_FORWARD_EVIDENCE_SCHEMA,
        _timestamp(fold.training_start, "training_start"),
        _timestamp(fold.training_end, "training_end"),
        _timestamp(fold.test_start, "test_start"),
        _timestamp(fold.test_end, "test_end"),
    )


@dataclass(frozen=True, slots=True)
class ResearchStrategyWalkForwardFold:
    """One immutable strategy-native training/test interval pair."""

    training_start: datetime
    training_end: datetime
    test_start: datetime
    test_end: datetime
    fold_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        starts = tuple(
            _normalized_timestamp(value, name)
            for value, name in (
                (self.training_start, "training_start"),
                (self.training_end, "training_end"),
                (self.test_start, "test_start"),
                (self.test_end, "test_end"),
            )
        )
        if not starts[0] < starts[1] == starts[2] < starts[3]:
            raise ResearchStrategyWalkForwardError(
                "fold chronology must be training_start < training_end == "
                "test_start < test_end"
            )
        for name, value in zip(
            ("training_start", "training_end", "test_start", "test_end"),
            starts,
            strict=True,
        ):
            object.__setattr__(self, name, value)
        object.__setattr__(
            self,
            "fold_id",
            _identity(
                RESEARCH_STRATEGY_WALK_FORWARD_EVIDENCE_NAMESPACE,
                RESEARCH_STRATEGY_WALK_FORWARD_FOLD_IDENTITY_VERSION,
                _fold_material(self),
            ),
        )

    def to_json(self) -> str:
        _validate_fold(self)
        return _json(
            {
                "fold_id": str(self.fold_id),
                "training_start": _timestamp(self.training_start, "training_start"),
                "training_end": _timestamp(self.training_end, "training_end"),
                "test_start": _timestamp(self.test_start, "test_start"),
                "test_end": _timestamp(self.test_end, "test_end"),
            }
        )

    @classmethod
    def from_json(cls, value: str) -> ResearchStrategyWalkForwardFold:
        try:
            if cls is not ResearchStrategyWalkForwardFold or type(value) is not str:
                raise ResearchStrategyWalkForwardError("exact fold JSON required")
            raw = json.loads(
                value,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
            root = _exact_fields(raw, _FOLD_FIELDS)
            result = cls(
                _parse_timestamp(root["training_start"], "training_start"),
                _parse_timestamp(root["training_end"], "training_end"),
                _parse_timestamp(root["test_start"], "test_start"),
                _parse_timestamp(root["test_end"], "test_end"),
            )
            if (
                _parse_uuid(root["fold_id"], "fold_id") != result.fold_id
                or result.to_json() != value
            ):
                raise ResearchStrategyWalkForwardError(
                    "fold identity or canonical bytes are inconsistent"
                )
            return result
        except (ArithmeticError, TypeError, UnicodeError, ValueError) as error:
            if isinstance(error, ResearchStrategyWalkForwardError):
                raise
            raise ResearchStrategyWalkForwardError("invalid fold JSON") from None


def _validate_fold(fold: ResearchStrategyWalkForwardFold) -> None:
    if type(fold) is not ResearchStrategyWalkForwardFold:
        raise ResearchStrategyWalkForwardError("exact fold required")
    if not fold.training_start < fold.training_end == fold.test_start < fold.test_end:
        raise ResearchStrategyWalkForwardError("invalid fold chronology")
    expected = _identity(
        RESEARCH_STRATEGY_WALK_FORWARD_EVIDENCE_NAMESPACE,
        RESEARCH_STRATEGY_WALK_FORWARD_FOLD_IDENTITY_VERSION,
        _fold_material(fold),
    )
    if type(fold.fold_id) is not UUID or fold.fold_id != expected:
        raise ResearchStrategyWalkForwardError("fold_id is inconsistent")


def _validate_ordered_folds(
    folds: tuple[ResearchStrategyWalkForwardFold, ...],
) -> None:
    if not folds:
        raise ResearchStrategyWalkForwardError("at least one fold is required")
    previous: ResearchStrategyWalkForwardFold | None = None
    for fold in folds:
        _validate_fold(fold)
        if previous is not None and fold.training_start != previous.test_end:
            raise ResearchStrategyWalkForwardError(
                "folds must be ordered, contiguous, and non-overlapping"
            )
        previous = fold


@dataclass(frozen=True, slots=True)
class ResearchStrategyWalkForwardFoldEvidence:
    """The exact per-fold references retained by aggregate evidence."""

    fold_id: UUID
    training_backtest_evidence_id: UUID
    test_backtest_evidence_id: UUID
    training_start: datetime
    training_end: datetime
    test_start: datetime
    test_end: datetime
    training_historical_fingerprint: UUID
    test_historical_fingerprint: UUID
    training_bar_count: int
    test_bar_count: int

    def __post_init__(self) -> None:
        _validate_fold_evidence(self)

    def to_dict(self) -> dict[str, object]:
        _validate_fold_evidence(self)
        return {
            "fold_id": str(self.fold_id),
            "training_backtest_evidence_id": str(self.training_backtest_evidence_id),
            "test_backtest_evidence_id": str(self.test_backtest_evidence_id),
            "training_start": _timestamp(self.training_start, "training_start"),
            "training_end": _timestamp(self.training_end, "training_end"),
            "test_start": _timestamp(self.test_start, "test_start"),
            "test_end": _timestamp(self.test_end, "test_end"),
            "training_historical_fingerprint": str(
                self.training_historical_fingerprint
            ),
            "test_historical_fingerprint": str(self.test_historical_fingerprint),
            "training_bar_count": self.training_bar_count,
            "test_bar_count": self.test_bar_count,
        }

    @classmethod
    def from_dict(cls, value: object) -> ResearchStrategyWalkForwardFoldEvidence:
        root = _exact_fields(value, _FOLD_EVIDENCE_FIELDS)
        try:
            return cls(
                _parse_uuid(root["fold_id"], "fold_id"),
                _parse_uuid(
                    root["training_backtest_evidence_id"],
                    "training_backtest_evidence_id",
                ),
                _parse_uuid(
                    root["test_backtest_evidence_id"], "test_backtest_evidence_id"
                ),
                _parse_timestamp(root["training_start"], "training_start"),
                _parse_timestamp(root["training_end"], "training_end"),
                _parse_timestamp(root["test_start"], "test_start"),
                _parse_timestamp(root["test_end"], "test_end"),
                _parse_uuid(
                    root["training_historical_fingerprint"],
                    "training_historical_fingerprint",
                ),
                _parse_uuid(
                    root["test_historical_fingerprint"],
                    "test_historical_fingerprint",
                ),
                _integer(
                    root["training_bar_count"], "training_bar_count", positive=True
                ),
                _integer(root["test_bar_count"], "test_bar_count", positive=True),
            )
        except (ArithmeticError, TypeError, UnicodeError, ValueError) as error:
            if isinstance(error, ResearchStrategyWalkForwardError):
                raise
            raise ResearchStrategyWalkForwardError("invalid fold evidence") from None


def _validate_fold_evidence(
    evidence: ResearchStrategyWalkForwardFoldEvidence,
) -> None:
    if type(evidence) is not ResearchStrategyWalkForwardFoldEvidence:
        raise ResearchStrategyWalkForwardError("exact fold evidence required")
    for value, name in (
        (evidence.fold_id, "fold_id"),
        (evidence.training_backtest_evidence_id, "training_backtest_evidence_id"),
        (evidence.test_backtest_evidence_id, "test_backtest_evidence_id"),
        (evidence.training_historical_fingerprint, "training_historical_fingerprint"),
        (evidence.test_historical_fingerprint, "test_historical_fingerprint"),
    ):
        _uuid(value, name)
    fold = ResearchStrategyWalkForwardFold(
        evidence.training_start,
        evidence.training_end,
        evidence.test_start,
        evidence.test_end,
    )
    if fold.fold_id != evidence.fold_id:
        raise ResearchStrategyWalkForwardError("fold evidence identity mismatch")
    _integer(evidence.training_bar_count, "training_bar_count", positive=True)
    _integer(evidence.test_bar_count, "test_bar_count", positive=True)


def _walk_forward_evidence_material(
    evidence: ResearchStrategyWalkForwardEvidence,
) -> tuple[str, ...]:
    _validate_walk_forward_evidence(evidence, check_identity=False)
    material: list[str] = [
        evidence.schema,
        str(evidence.definition_id),
        str(evidence.evaluation_policy_id),
        evidence.evaluation_source_head,
        evidence.evaluation_source_tree,
        str(evidence.source_historical_fingerprint),
        str(len(evidence.folds)),
    ]
    for fold in evidence.folds:
        material.extend(
            (
                str(fold.fold_id),
                str(fold.training_backtest_evidence_id),
                str(fold.test_backtest_evidence_id),
                _timestamp(fold.training_start, "training_start"),
                _timestamp(fold.training_end, "training_end"),
                _timestamp(fold.test_start, "test_start"),
                _timestamp(fold.test_end, "test_end"),
                str(fold.training_historical_fingerprint),
                str(fold.test_historical_fingerprint),
                str(fold.training_bar_count),
                str(fold.test_bar_count),
            )
        )
    return tuple(material)


@dataclass(frozen=True, slots=True)
class ResearchStrategyWalkForwardEvidence:
    """Canonical aggregate evidence for all strategy-native folds."""

    definition_id: UUID
    evaluation_policy_id: UUID
    evaluation_source_head: str
    evaluation_source_tree: str
    source_historical_fingerprint: UUID
    folds: tuple[ResearchStrategyWalkForwardFoldEvidence, ...]
    schema: str = field(
        default=RESEARCH_STRATEGY_WALK_FORWARD_EVIDENCE_SCHEMA, init=False
    )
    evidence_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        _validate_walk_forward_evidence(self, check_identity=False)
        object.__setattr__(
            self,
            "evidence_id",
            _identity(
                RESEARCH_STRATEGY_WALK_FORWARD_EVIDENCE_NAMESPACE,
                RESEARCH_STRATEGY_WALK_FORWARD_EVIDENCE_IDENTITY_VERSION,
                _walk_forward_evidence_material(self),
            ),
        )

    @property
    def fold_count(self) -> int:
        return len(self.folds)

    def to_json(self) -> str:
        _validate_walk_forward_evidence(self)
        return _json(
            {
                "schema": self.schema,
                "evidence_id": str(self.evidence_id),
                "definition_id": str(self.definition_id),
                "evaluation_policy_id": str(self.evaluation_policy_id),
                "evaluation_source_head": self.evaluation_source_head,
                "evaluation_source_tree": self.evaluation_source_tree,
                "source_historical_fingerprint": str(
                    self.source_historical_fingerprint
                ),
                "folds": [fold.to_dict() for fold in self.folds],
            }
        )

    @classmethod
    def from_json(cls, value: str) -> ResearchStrategyWalkForwardEvidence:
        try:
            if cls is not ResearchStrategyWalkForwardEvidence or type(value) is not str:
                raise ResearchStrategyWalkForwardError(
                    "exact walk-forward JSON required"
                )
            raw = json.loads(
                value,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
            root = _exact_fields(raw, _WALK_FORWARD_EVIDENCE_FIELDS)
            if root["schema"] != RESEARCH_STRATEGY_WALK_FORWARD_EVIDENCE_SCHEMA:
                raise ResearchStrategyWalkForwardError("invalid walk-forward schema")
            if type(root["folds"]) is not list:
                raise ResearchStrategyWalkForwardError("folds must be a list")
            result = cls(
                _parse_uuid(root["definition_id"], "definition_id"),
                _parse_uuid(root["evaluation_policy_id"], "evaluation_policy_id"),
                _source(root["evaluation_source_head"], "evaluation_source_head"),
                _source(root["evaluation_source_tree"], "evaluation_source_tree"),
                _parse_uuid(
                    root["source_historical_fingerprint"],
                    "source_historical_fingerprint",
                ),
                tuple(
                    ResearchStrategyWalkForwardFoldEvidence.from_dict(item)
                    for item in root["folds"]
                ),
            )
            if (
                _parse_uuid(root["evidence_id"], "evidence_id") != result.evidence_id
                or result.to_json() != value
            ):
                raise ResearchStrategyWalkForwardError(
                    "walk-forward evidence identity or canonical bytes are inconsistent"
                )
            return result
        except (ArithmeticError, TypeError, UnicodeError, ValueError) as error:
            if isinstance(error, ResearchStrategyWalkForwardError):
                raise
            raise ResearchStrategyWalkForwardError(
                "invalid walk-forward JSON"
            ) from None


def _validate_walk_forward_evidence(
    evidence: ResearchStrategyWalkForwardEvidence,
    *,
    check_identity: bool = True,
) -> None:
    if type(evidence) is not ResearchStrategyWalkForwardEvidence:
        raise ResearchStrategyWalkForwardError("exact walk-forward evidence required")
    if evidence.schema != RESEARCH_STRATEGY_WALK_FORWARD_EVIDENCE_SCHEMA:
        raise ResearchStrategyWalkForwardError("walk-forward schema is fixed")
    _uuid(evidence.definition_id, "definition_id")
    _uuid(evidence.evaluation_policy_id, "evaluation_policy_id")
    _uuid(evidence.source_historical_fingerprint, "source_historical_fingerprint")
    _source(evidence.evaluation_source_head, "evaluation_source_head")
    _source(evidence.evaluation_source_tree, "evaluation_source_tree")
    if type(evidence.folds) is not tuple or not evidence.folds:
        raise ResearchStrategyWalkForwardError("walk-forward folds must be nonempty")
    folds = []
    for fold in evidence.folds:
        _validate_fold_evidence(fold)
        folds.append(
            ResearchStrategyWalkForwardFold(
                fold.training_start,
                fold.training_end,
                fold.test_start,
                fold.test_end,
            )
        )
    _validate_ordered_folds(tuple(folds))
    if check_identity:
        expected = _identity(
            RESEARCH_STRATEGY_WALK_FORWARD_EVIDENCE_NAMESPACE,
            RESEARCH_STRATEGY_WALK_FORWARD_EVIDENCE_IDENTITY_VERSION,
            _walk_forward_evidence_material(evidence),
        )
        if type(evidence.evidence_id) is not UUID or evidence.evidence_id != expected:
            raise ResearchStrategyWalkForwardError("evidence_id is inconsistent")


def _policy_material(
    policy: ResearchStrategyWalkForwardQualificationPolicy,
) -> tuple[str, ...]:
    _validate_policy(policy, check_identity=False)
    return (
        policy.schema,
        str(policy.minimum_fold_count),
        _decimal(policy.minimum_fold_return, "minimum_fold_return"),
        _decimal(policy.minimum_median_return, "minimum_median_return"),
        _decimal(
            policy.maximum_fold_drawdown_percentage,
            "maximum_fold_drawdown_percentage",
        ),
        "true" if policy.require_equal_test_window_bar_count else "false",
    )


@dataclass(frozen=True, slots=True)
class ResearchStrategyWalkForwardQualificationPolicy:
    """Explicit deterministic thresholds for strategy-native qualification."""

    minimum_fold_count: int
    minimum_fold_return: Decimal
    minimum_median_return: Decimal
    maximum_fold_drawdown_percentage: Decimal
    require_equal_test_window_bar_count: bool
    schema: str = field(
        default=RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_POLICY_SCHEMA,
        init=False,
    )
    policy_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        _validate_policy(self, check_identity=False)
        object.__setattr__(
            self,
            "policy_id",
            _identity(
                RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_POLICY_NAMESPACE,
                RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_POLICY_IDENTITY_VERSION,
                _policy_material(self),
            ),
        )

    def to_json(self) -> str:
        _validate_policy(self)
        return _json(
            {
                "schema": self.schema,
                "policy_id": str(self.policy_id),
                "minimum_fold_count": self.minimum_fold_count,
                "minimum_fold_return": _decimal(
                    self.minimum_fold_return, "minimum_fold_return"
                ),
                "minimum_median_return": _decimal(
                    self.minimum_median_return, "minimum_median_return"
                ),
                "maximum_fold_drawdown_percentage": _decimal(
                    self.maximum_fold_drawdown_percentage,
                    "maximum_fold_drawdown_percentage",
                ),
                "require_equal_test_window_bar_count": (
                    self.require_equal_test_window_bar_count
                ),
            }
        )

    @classmethod
    def from_json(cls, value: str) -> ResearchStrategyWalkForwardQualificationPolicy:
        try:
            if (
                cls is not ResearchStrategyWalkForwardQualificationPolicy
                or type(value) is not str
            ):
                raise ResearchStrategyWalkForwardError(
                    "exact qualification policy JSON required"
                )
            raw = json.loads(
                value,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
            root = _exact_fields(raw, _POLICY_FIELDS)
            if (
                root["schema"]
                != RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_POLICY_SCHEMA
            ):
                raise ResearchStrategyWalkForwardError(
                    "invalid qualification policy schema"
                )
            if type(root["require_equal_test_window_bar_count"]) is not bool:
                raise ResearchStrategyWalkForwardError(
                    "require_equal_test_window_bar_count must be a bool"
                )
            result = cls(
                _integer(
                    root["minimum_fold_count"], "minimum_fold_count", positive=True
                ),
                _parse_decimal(root["minimum_fold_return"], "minimum_fold_return"),
                _parse_decimal(root["minimum_median_return"], "minimum_median_return"),
                _parse_decimal(
                    root["maximum_fold_drawdown_percentage"],
                    "maximum_fold_drawdown_percentage",
                ),
                root["require_equal_test_window_bar_count"],
            )
            if (
                _parse_uuid(root["policy_id"], "policy_id") != result.policy_id
                or result.to_json() != value
            ):
                raise ResearchStrategyWalkForwardError(
                    "qualification policy identity or canonical bytes are inconsistent"
                )
            return result
        except (ArithmeticError, TypeError, UnicodeError, ValueError) as error:
            if isinstance(error, ResearchStrategyWalkForwardError):
                raise
            raise ResearchStrategyWalkForwardError(
                "invalid qualification policy JSON"
            ) from None


def _validate_policy(
    policy: ResearchStrategyWalkForwardQualificationPolicy,
    *,
    check_identity: bool = True,
) -> None:
    if type(policy) is not ResearchStrategyWalkForwardQualificationPolicy:
        raise ResearchStrategyWalkForwardError("exact qualification policy required")
    if policy.schema != RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_POLICY_SCHEMA:
        raise ResearchStrategyWalkForwardError("qualification policy schema is fixed")
    _integer(policy.minimum_fold_count, "minimum_fold_count", positive=True)
    for value, name in (
        (policy.minimum_fold_return, "minimum_fold_return"),
        (policy.minimum_median_return, "minimum_median_return"),
        (
            policy.maximum_fold_drawdown_percentage,
            "maximum_fold_drawdown_percentage",
        ),
    ):
        _decimal(value, name)
    if type(policy.require_equal_test_window_bar_count) is not bool:
        raise ResearchStrategyWalkForwardError(
            "require_equal_test_window_bar_count must be a bool"
        )
    if policy.minimum_median_return < policy.minimum_fold_return:
        raise ResearchStrategyWalkForwardError(
            "minimum_median_return must be at least minimum_fold_return"
        )
    if policy.maximum_fold_drawdown_percentage < _ZERO:
        raise ResearchStrategyWalkForwardError(
            "maximum_fold_drawdown_percentage must be nonnegative"
        )
    if check_identity:
        expected = _identity(
            RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_POLICY_NAMESPACE,
            RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_POLICY_IDENTITY_VERSION,
            _policy_material(policy),
        )
        if type(policy.policy_id) is not UUID or policy.policy_id != expected:
            raise ResearchStrategyWalkForwardError("policy_id is inconsistent")


def _qualification_material(
    qualification: ResearchStrategyWalkForwardQualification,
) -> tuple[str, ...]:
    _validate_qualification(qualification, check_identity=False)
    return (
        qualification.schema,
        str(qualification.definition_id),
        str(qualification.evaluation_policy_id),
        qualification.qualification_source_head,
        qualification.qualification_source_tree,
        str(qualification.source_historical_fingerprint),
        str(qualification.walk_forward_evidence_id),
        *(_policy_material(qualification.policy)),
        str(qualification.fold_count),
        str(len(qualification.test_window_bar_counts)),
        *(str(value) for value in qualification.test_window_bar_counts),
        "true" if qualification.test_windows_comparable else "false",
        _decimal(
            qualification.minimum_observed_fold_return,
            "minimum_observed_fold_return",
        ),
        _decimal(qualification.median_fold_return, "median_fold_return"),
        _decimal(
            qualification.maximum_observed_fold_drawdown_percentage,
            "maximum_observed_fold_drawdown_percentage",
        ),
        qualification.status.value,
        str(len(qualification.failure_reasons)),
        *(reason.value for reason in qualification.failure_reasons),
    )


@dataclass(frozen=True, slots=True)
class ResearchStrategyWalkForwardQualification:
    """Deterministic PASS/FAILED threshold evidence over verified folds."""

    definition_id: UUID
    evaluation_policy_id: UUID
    qualification_source_head: str
    qualification_source_tree: str
    source_historical_fingerprint: UUID
    walk_forward_evidence_id: UUID
    policy: ResearchStrategyWalkForwardQualificationPolicy
    fold_count: int
    test_window_bar_counts: tuple[int, ...]
    minimum_observed_fold_return: Decimal
    median_fold_return: Decimal
    maximum_observed_fold_drawdown_percentage: Decimal
    schema: str = field(
        default=RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_SCHEMA, init=False
    )
    policy_id: UUID = field(init=False)
    test_windows_comparable: bool = field(init=False)
    status: ResearchStrategyWalkForwardQualificationStatus = field(init=False)
    failure_reasons: tuple[ResearchStrategyWalkForwardFailureReason, ...] = field(
        init=False
    )
    qualification_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        _validate_policy(self.policy)
        for value, name in (
            (self.definition_id, "definition_id"),
            (self.evaluation_policy_id, "evaluation_policy_id"),
            (self.source_historical_fingerprint, "source_historical_fingerprint"),
            (self.walk_forward_evidence_id, "walk_forward_evidence_id"),
        ):
            _uuid(value, name)
        _source(self.qualification_source_head, "qualification_source_head")
        _source(self.qualification_source_tree, "qualification_source_tree")
        _integer(self.fold_count, "fold_count", positive=True)
        if (
            type(self.test_window_bar_counts) is not tuple
            or not self.test_window_bar_counts
        ):
            raise ResearchStrategyWalkForwardError(
                "test_window_bar_counts must be a nonempty tuple"
            )
        if len(self.test_window_bar_counts) != self.fold_count:
            raise ResearchStrategyWalkForwardError(
                "test_window_bar_counts must match fold_count"
            )
        for value in self.test_window_bar_counts:
            _integer(value, "test_window_bar_count", positive=True)
        for value, name in (
            (self.minimum_observed_fold_return, "minimum_observed_fold_return"),
            (self.median_fold_return, "median_fold_return"),
            (
                self.maximum_observed_fold_drawdown_percentage,
                "maximum_observed_fold_drawdown_percentage",
            ),
        ):
            _decimal(value, name)
        if self.minimum_observed_fold_return > self.median_fold_return:
            raise ResearchStrategyWalkForwardError(
                "minimum observed return exceeds median return"
            )
        if self.maximum_observed_fold_drawdown_percentage < _ZERO:
            raise ResearchStrategyWalkForwardError(
                "maximum observed drawdown must be nonnegative"
            )
        comparable = all(
            value == self.test_window_bar_counts[0]
            for value in self.test_window_bar_counts
        )
        conditions = (
            self.fold_count < self.policy.minimum_fold_count,
            self.policy.require_equal_test_window_bar_count and not comparable,
            self.minimum_observed_fold_return < self.policy.minimum_fold_return,
            self.median_fold_return < self.policy.minimum_median_return,
            self.maximum_observed_fold_drawdown_percentage
            > self.policy.maximum_fold_drawdown_percentage,
        )
        reasons = tuple(
            reason
            for reason, failed in zip(
                ResearchStrategyWalkForwardFailureReason,
                conditions,
                strict=True,
            )
            if failed
        )
        object.__setattr__(self, "policy_id", self.policy.policy_id)
        object.__setattr__(self, "test_windows_comparable", comparable)
        object.__setattr__(
            self,
            "status",
            ResearchStrategyWalkForwardQualificationStatus.FAILED
            if reasons
            else ResearchStrategyWalkForwardQualificationStatus.PASSED,
        )
        object.__setattr__(self, "failure_reasons", reasons)
        object.__setattr__(
            self,
            "qualification_id",
            _identity(
                RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_NAMESPACE,
                RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_IDENTITY_VERSION,
                _qualification_material(self),
            ),
        )

    def to_json(self) -> str:
        _validate_qualification(self)
        policy = json.loads(self.policy.to_json())
        return _json(
            {
                "schema": self.schema,
                "qualification_id": str(self.qualification_id),
                "definition_id": str(self.definition_id),
                "evaluation_policy_id": str(self.evaluation_policy_id),
                "qualification_source_head": self.qualification_source_head,
                "qualification_source_tree": self.qualification_source_tree,
                "source_historical_fingerprint": str(
                    self.source_historical_fingerprint
                ),
                "walk_forward_evidence_id": str(self.walk_forward_evidence_id),
                "policy": policy,
                "policy_id": str(self.policy_id),
                "fold_count": self.fold_count,
                "test_window_bar_counts": list(self.test_window_bar_counts),
                "test_windows_comparable": self.test_windows_comparable,
                "minimum_observed_fold_return": _decimal(
                    self.minimum_observed_fold_return,
                    "minimum_observed_fold_return",
                ),
                "median_fold_return": _decimal(
                    self.median_fold_return, "median_fold_return"
                ),
                "maximum_observed_fold_drawdown_percentage": _decimal(
                    self.maximum_observed_fold_drawdown_percentage,
                    "maximum_observed_fold_drawdown_percentage",
                ),
                "status": self.status.value,
                "failure_reasons": [reason.value for reason in self.failure_reasons],
            }
        )

    @classmethod
    def from_json(cls, value: str) -> ResearchStrategyWalkForwardQualification:
        try:
            if (
                cls is not ResearchStrategyWalkForwardQualification
                or type(value) is not str
            ):
                raise ResearchStrategyWalkForwardError(
                    "exact qualification JSON required"
                )
            raw = json.loads(
                value,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
            root = _exact_fields(raw, _QUALIFICATION_FIELDS)
            if root["schema"] != RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_SCHEMA:
                raise ResearchStrategyWalkForwardError("invalid qualification schema")
            if type(root["test_window_bar_counts"]) is not list:
                raise ResearchStrategyWalkForwardError(
                    "test_window_bar_counts must be a list"
                )
            if type(root["failure_reasons"]) is not list:
                raise ResearchStrategyWalkForwardError("failure_reasons must be a list")
            policy = ResearchStrategyWalkForwardQualificationPolicy.from_json(
                _json(root["policy"])
            )
            result = cls(
                _parse_uuid(root["definition_id"], "definition_id"),
                _parse_uuid(root["evaluation_policy_id"], "evaluation_policy_id"),
                _source(root["qualification_source_head"], "qualification_source_head"),
                _source(root["qualification_source_tree"], "qualification_source_tree"),
                _parse_uuid(
                    root["source_historical_fingerprint"],
                    "source_historical_fingerprint",
                ),
                _parse_uuid(
                    root["walk_forward_evidence_id"], "walk_forward_evidence_id"
                ),
                policy,
                _integer(root["fold_count"], "fold_count", positive=True),
                tuple(
                    _integer(item, "test_window_bar_count", positive=True)
                    for item in root["test_window_bar_counts"]
                ),
                _parse_decimal(
                    root["minimum_observed_fold_return"],
                    "minimum_observed_fold_return",
                ),
                _parse_decimal(root["median_fold_return"], "median_fold_return"),
                _parse_decimal(
                    root["maximum_observed_fold_drawdown_percentage"],
                    "maximum_observed_fold_drawdown_percentage",
                ),
            )
            if type(root["test_windows_comparable"]) is not bool:
                raise ResearchStrategyWalkForwardError(
                    "test_windows_comparable must be a bool"
                )
            if root["test_windows_comparable"] != result.test_windows_comparable:
                raise ResearchStrategyWalkForwardError("derived comparability mismatch")
            if root["status"] != result.status.value:
                raise ResearchStrategyWalkForwardError("derived status mismatch")
            expected_reasons = [reason.value for reason in result.failure_reasons]
            if root["failure_reasons"] != expected_reasons:
                raise ResearchStrategyWalkForwardError(
                    "derived failure reasons mismatch"
                )
            if _parse_uuid(root["policy_id"], "policy_id") != result.policy_id:
                raise ResearchStrategyWalkForwardError("policy_id is inconsistent")
            if (
                _parse_uuid(root["qualification_id"], "qualification_id")
                != result.qualification_id
                or result.to_json() != value
            ):
                raise ResearchStrategyWalkForwardError(
                    "qualification identity or canonical bytes are inconsistent"
                )
            return result
        except (ArithmeticError, TypeError, UnicodeError, ValueError) as error:
            if isinstance(error, ResearchStrategyWalkForwardError):
                raise
            raise ResearchStrategyWalkForwardError(
                "invalid qualification JSON"
            ) from None


def _validate_qualification(
    qualification: ResearchStrategyWalkForwardQualification,
    *,
    check_identity: bool = True,
) -> None:
    if type(qualification) is not ResearchStrategyWalkForwardQualification:
        raise ResearchStrategyWalkForwardError("exact qualification required")
    if (
        type(qualification.schema) is not str
        or qualification.schema != RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_SCHEMA
    ):
        raise ResearchStrategyWalkForwardError("qualification schema is fixed")
    _validate_policy(qualification.policy)
    for value, name in (
        (qualification.definition_id, "definition_id"),
        (qualification.evaluation_policy_id, "evaluation_policy_id"),
        (qualification.source_historical_fingerprint, "source_historical_fingerprint"),
        (qualification.walk_forward_evidence_id, "walk_forward_evidence_id"),
        (qualification.policy_id, "policy_id"),
    ):
        _uuid(value, name)
    _source(qualification.qualification_source_head, "qualification_source_head")
    _source(qualification.qualification_source_tree, "qualification_source_tree")
    _integer(qualification.fold_count, "fold_count", positive=True)
    if (
        type(qualification.test_window_bar_counts) is not tuple
        or not qualification.test_window_bar_counts
    ):
        raise ResearchStrategyWalkForwardError(
            "test_window_bar_counts must be a nonempty tuple"
        )
    if len(qualification.test_window_bar_counts) != qualification.fold_count:
        raise ResearchStrategyWalkForwardError(
            "test_window_bar_counts must match fold_count"
        )
    for value in qualification.test_window_bar_counts:
        _integer(value, "test_window_bar_count", positive=True)
    for value, name in (
        (qualification.minimum_observed_fold_return, "minimum_observed_fold_return"),
        (qualification.median_fold_return, "median_fold_return"),
        (
            qualification.maximum_observed_fold_drawdown_percentage,
            "maximum_observed_fold_drawdown_percentage",
        ),
    ):
        _decimal(value, name)
    if qualification.minimum_observed_fold_return > qualification.median_fold_return:
        raise ResearchStrategyWalkForwardError(
            "minimum observed return exceeds median return"
        )
    if qualification.maximum_observed_fold_drawdown_percentage < _ZERO:
        raise ResearchStrategyWalkForwardError(
            "maximum observed drawdown must be nonnegative"
        )
    if type(qualification.test_windows_comparable) is not bool:
        raise ResearchStrategyWalkForwardError("comparability must be a bool")
    if type(qualification.status) is not ResearchStrategyWalkForwardQualificationStatus:
        raise ResearchStrategyWalkForwardError("status must be exact enum")
    if type(qualification.failure_reasons) is not tuple or any(
        type(reason) is not ResearchStrategyWalkForwardFailureReason
        for reason in qualification.failure_reasons
    ):
        raise ResearchStrategyWalkForwardError(
            "failure reasons must be exact enum values"
        )
    comparable = all(
        value == qualification.test_window_bar_counts[0]
        for value in qualification.test_window_bar_counts
    )
    conditions = (
        qualification.fold_count < qualification.policy.minimum_fold_count,
        qualification.policy.require_equal_test_window_bar_count and not comparable,
        qualification.minimum_observed_fold_return
        < qualification.policy.minimum_fold_return,
        qualification.median_fold_return < qualification.policy.minimum_median_return,
        qualification.maximum_observed_fold_drawdown_percentage
        > qualification.policy.maximum_fold_drawdown_percentage,
    )
    reasons = tuple(
        reason
        for reason, failed in zip(
            ResearchStrategyWalkForwardFailureReason, conditions, strict=True
        )
        if failed
    )
    expected_status = (
        ResearchStrategyWalkForwardQualificationStatus.FAILED
        if reasons
        else ResearchStrategyWalkForwardQualificationStatus.PASSED
    )
    expected_policy_id = qualification.policy.policy_id
    if (
        qualification.policy_id != expected_policy_id
        or qualification.test_windows_comparable != comparable
        or qualification.status != expected_status
        or qualification.failure_reasons != reasons
    ):
        raise ResearchStrategyWalkForwardError(
            "qualification derived fields inconsistent"
        )
    if check_identity:
        _uuid(
            getattr(qualification, "qualification_id", None),
            "qualification_id",
        )
        expected_id = _identity(
            RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_NAMESPACE,
            RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_IDENTITY_VERSION,
            _qualification_material(qualification),
        )
        if qualification.qualification_id != expected_id:
            raise ResearchStrategyWalkForwardError("qualification_id is inconsistent")


@dataclass(frozen=True, slots=True)
class CompletedResearchStrategyWalkForwardFold:
    """Immutable in-memory results for one independently evaluated fold."""

    fold: ResearchStrategyWalkForwardFold
    training: CompletedResearchStrategyBacktest
    test: CompletedResearchStrategyBacktest
    evidence: ResearchStrategyWalkForwardFoldEvidence

    def __post_init__(self) -> None:
        _validate_fold(self.fold)
        if type(self.training) is not CompletedResearchStrategyBacktest:
            raise ResearchStrategyWalkForwardError("exact training backtest required")
        if type(self.test) is not CompletedResearchStrategyBacktest:
            raise ResearchStrategyWalkForwardError("exact test backtest required")
        if type(self.evidence) is not ResearchStrategyWalkForwardFoldEvidence:
            raise ResearchStrategyWalkForwardError("exact fold evidence required")
        _validate_fold_evidence(self.evidence)
        for completed, role, name in (
            (self.training, TRAINING_FOLD_ROLE, "training"),
            (self.test, TEST_FOLD_ROLE, "test"),
        ):
            if (
                completed.definition.definition_id
                != self.training.definition.definition_id
            ):
                raise ResearchStrategyWalkForwardError(
                    f"{name} definition provenance mismatch"
                )
            if (
                completed.evaluation_policy.policy_id
                != self.training.evaluation_policy.policy_id
            ):
                raise ResearchStrategyWalkForwardError(
                    f"{name} policy provenance mismatch"
                )
            expected_run = completed.result.config.run_id
            if completed.evidence.backtest_run_id != expected_run:
                raise ResearchStrategyWalkForwardError(f"{name} run identity mismatch")
            expected_run = derive_backtest_run_id(
                completed.definition.definition_id,
                completed.evaluation_policy.policy_id,
                completed.evidence.historical_data_fingerprint,
                fold_role=role,
                fold_id=self.fold.fold_id,
            )
            if completed.evidence.backtest_run_id != expected_run:
                raise ResearchStrategyWalkForwardError(
                    f"{name} fold-role identity mismatch"
                )
            if role == TRAINING_FOLD_ROLE:
                if (
                    completed.evidence.evidence_id
                    != self.evidence.training_backtest_evidence_id
                ):
                    raise ResearchStrategyWalkForwardError("training evidence mismatch")
                if (
                    completed.evidence.historical_data_fingerprint
                    != self.evidence.training_historical_fingerprint
                ):
                    raise ResearchStrategyWalkForwardError(
                        "training fingerprint mismatch"
                    )
                if completed.evidence.bar_count != self.evidence.training_bar_count:
                    raise ResearchStrategyWalkForwardError(
                        "training bar count mismatch"
                    )
                if (
                    completed.historical_data.request.start != self.fold.training_start
                    or completed.historical_data.request.end != self.fold.training_end
                ):
                    raise ResearchStrategyWalkForwardError("training slice mismatch")
            else:
                if (
                    completed.evidence.evidence_id
                    != self.evidence.test_backtest_evidence_id
                ):
                    raise ResearchStrategyWalkForwardError("test evidence mismatch")
                if (
                    completed.evidence.historical_data_fingerprint
                    != self.evidence.test_historical_fingerprint
                ):
                    raise ResearchStrategyWalkForwardError("test fingerprint mismatch")
                if completed.evidence.bar_count != self.evidence.test_bar_count:
                    raise ResearchStrategyWalkForwardError("test bar count mismatch")
                if (
                    completed.historical_data.request.start != self.fold.test_start
                    or completed.historical_data.request.end != self.fold.test_end
                ):
                    raise ResearchStrategyWalkForwardError("test slice mismatch")


@dataclass(frozen=True, slots=True)
class CompletedResearchStrategyWalkForward:
    """Immutable carrier retaining exact fold results for later verification."""

    definition: ResearchStrategyDefinition
    evaluation_policy: ResearchStrategyEvaluationPolicy
    historical_data: HistoricalDataResult
    folds: tuple[CompletedResearchStrategyWalkForwardFold, ...]
    evidence: ResearchStrategyWalkForwardEvidence

    def __post_init__(self) -> None:
        _validate_walk_forward_definition_inputs(
            self.definition, self.evaluation_policy, self.historical_data
        )
        if type(self.folds) is not tuple or not self.folds:
            raise ResearchStrategyWalkForwardError("completed folds must be nonempty")
        for item in self.folds:
            if type(item) is not CompletedResearchStrategyWalkForwardFold:
                raise ResearchStrategyWalkForwardError("exact completed fold required")
        if type(self.evidence) is not ResearchStrategyWalkForwardEvidence:
            raise ResearchStrategyWalkForwardError(
                "exact walk-forward evidence required"
            )
        _validate_walk_forward_evidence(self.evidence)
        fold_models = tuple(item.fold for item in self.folds)
        _validate_ordered_folds(fold_models)
        if self.evidence.definition_id != self.definition.definition_id:
            raise ResearchStrategyWalkForwardError("definition provenance mismatch")
        if self.evidence.evaluation_policy_id != self.evaluation_policy.policy_id:
            raise ResearchStrategyWalkForwardError("policy provenance mismatch")
        if self.evidence.source_historical_fingerprint != historical_data_fingerprint(
            self.historical_data
        ):
            raise ResearchStrategyWalkForwardError(
                "source historical fingerprint mismatch"
            )
        if tuple(item.evidence for item in self.folds) != tuple(
            _fold_evidence_from_completed(item) for item in self.folds
        ):
            raise ResearchStrategyWalkForwardError("fold evidence is inconsistent")


def _validate_walk_forward_definition_inputs(
    definition: ResearchStrategyDefinition,
    evaluation_policy: ResearchStrategyEvaluationPolicy,
    historical_data: HistoricalDataResult,
) -> None:
    if type(definition) is not ResearchStrategyDefinition:
        raise ResearchStrategyWalkForwardError("exact research definition required")
    if type(evaluation_policy) is not ResearchStrategyEvaluationPolicy:
        raise ResearchStrategyWalkForwardError("exact evaluation policy required")
    try:
        definition.to_json()
        evaluation_policy.to_json()
    except ResearchStrategyDefinitionError as error:
        raise ResearchStrategyWalkForwardError(str(error)) from error
    try:
        canonical_single_symbol_historical_material(historical_data)
    except (ResearchStrategyBacktestError, TypeError, ValueError) as error:
        raise ResearchStrategyWalkForwardError(str(error)) from error
    if historical_data.request.symbol != definition.symbol:
        raise ResearchStrategyWalkForwardError(
            "historical request symbol must equal definition symbol"
        )


def _slice_historical_data(
    historical_data: HistoricalDataResult,
    start: datetime,
    end: datetime,
) -> HistoricalDataResult:
    request = historical_data.request
    if start < request.start or end > request.end:
        raise ResearchStrategyWalkForwardError(
            "fold is outside supplied historical interval"
        )
    bars = tuple(bar for bar in historical_data.bars if start <= bar.timestamp < end)
    if not bars:
        raise ResearchStrategyWalkForwardError("fold slice contains no historical bars")
    try:
        return HistoricalDataResult(
            HistoricalDataRequest(
                request.symbol,
                start,
                end,
                request.timeframe,
                request.adjustment,
            ),
            bars,
            historical_data.provider_name,
        )
    except (TypeError, ValueError) as error:
        raise ResearchStrategyWalkForwardError(
            "invalid fold historical slice"
        ) from error


def _fold_evidence_from_completed(
    completed: CompletedResearchStrategyWalkForwardFold,
) -> ResearchStrategyWalkForwardFoldEvidence:
    return ResearchStrategyWalkForwardFoldEvidence(
        completed.fold.fold_id,
        completed.training.evidence.evidence_id,
        completed.test.evidence.evidence_id,
        completed.fold.training_start,
        completed.fold.training_end,
        completed.fold.test_start,
        completed.fold.test_end,
        completed.training.evidence.historical_data_fingerprint,
        completed.test.evidence.historical_data_fingerprint,
        completed.training.evidence.bar_count,
        completed.test.evidence.bar_count,
    )


def _build_completed_walk_forward(
    definition: ResearchStrategyDefinition,
    evaluation_policy: ResearchStrategyEvaluationPolicy,
    historical_data: HistoricalDataResult,
    folds: tuple[ResearchStrategyWalkForwardFold, ...],
    *,
    evaluation_source_head: str,
    evaluation_source_tree: str,
) -> CompletedResearchStrategyWalkForward:
    _source(evaluation_source_head, "evaluation_source_head")
    _source(evaluation_source_tree, "evaluation_source_tree")
    _validate_walk_forward_definition_inputs(
        definition, evaluation_policy, historical_data
    )
    _validate_ordered_folds(folds)
    completed_folds: list[CompletedResearchStrategyWalkForwardFold] = []
    for fold in folds:
        training_data = _slice_historical_data(
            historical_data, fold.training_start, fold.training_end
        )
        test_data = _slice_historical_data(
            historical_data, fold.test_start, fold.test_end
        )
        try:
            training = run_research_strategy_backtest(
                definition,
                evaluation_policy,
                training_data,
                evaluation_source_head=evaluation_source_head,
                evaluation_source_tree=evaluation_source_tree,
                fold_role=TRAINING_FOLD_ROLE,
                fold_id=fold.fold_id,
            )
            test = run_research_strategy_backtest(
                definition,
                evaluation_policy,
                test_data,
                evaluation_source_head=evaluation_source_head,
                evaluation_source_tree=evaluation_source_tree,
                fold_role=TEST_FOLD_ROLE,
                fold_id=fold.fold_id,
            )
        except (ResearchStrategyBacktestError, TypeError, ValueError) as error:
            raise ResearchStrategyWalkForwardError(str(error)) from error
        evidence = ResearchStrategyWalkForwardFoldEvidence(
            fold.fold_id,
            training.evidence.evidence_id,
            test.evidence.evidence_id,
            fold.training_start,
            fold.training_end,
            fold.test_start,
            fold.test_end,
            training.evidence.historical_data_fingerprint,
            test.evidence.historical_data_fingerprint,
            training.evidence.bar_count,
            test.evidence.bar_count,
        )
        completed_folds.append(
            CompletedResearchStrategyWalkForwardFold(fold, training, test, evidence)
        )
    evidence = ResearchStrategyWalkForwardEvidence(
        definition.definition_id,
        evaluation_policy.policy_id,
        evaluation_source_head,
        evaluation_source_tree,
        historical_data_fingerprint(historical_data),
        tuple(item.evidence for item in completed_folds),
    )
    return CompletedResearchStrategyWalkForward(
        definition,
        evaluation_policy,
        historical_data,
        tuple(completed_folds),
        evidence,
    )


def run_research_strategy_walk_forward(
    definition: ResearchStrategyDefinition,
    evaluation_policy: ResearchStrategyEvaluationPolicy,
    historical_data: HistoricalDataResult,
    folds: tuple[ResearchStrategyWalkForwardFold, ...],
    *,
    evaluation_source_head: str,
    evaluation_source_tree: str,
) -> CompletedResearchStrategyWalkForward:
    """Evaluate every frozen fold with independent TRAINING and TEST state."""
    if type(folds) is not tuple:
        raise ResearchStrategyWalkForwardError("folds must be an exact tuple")
    return _build_completed_walk_forward(
        definition,
        evaluation_policy,
        historical_data,
        folds,
        evaluation_source_head=evaluation_source_head,
        evaluation_source_tree=evaluation_source_tree,
    )


def verify_research_strategy_walk_forward(
    completed: CompletedResearchStrategyWalkForward,
    *,
    evaluation_source_head: str | None = None,
    evaluation_source_tree: str | None = None,
) -> None:
    """Independently replay all fold sides and reconcile the complete chain."""
    if type(completed) is not CompletedResearchStrategyWalkForward:
        raise ResearchStrategyWalkForwardError("exact completed walk-forward required")
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
    try:
        expected = _build_completed_walk_forward(
            completed.definition,
            completed.evaluation_policy,
            completed.historical_data,
            tuple(item.fold for item in completed.folds),
            evaluation_source_head=head,
            evaluation_source_tree=tree,
        )
    except ResearchStrategyWalkForwardError:
        raise
    if expected != completed:
        raise ResearchStrategyWalkForwardError(
            "walk-forward result, fold results, or evidence does not reconcile"
        )
    for item in completed.folds:
        try:
            verify_research_strategy_backtest(
                item.training,
                item.training.historical_data,
                evaluation_source_head=head,
                evaluation_source_tree=tree,
                fold_role=TRAINING_FOLD_ROLE,
                fold_id=item.fold.fold_id,
            )
            verify_research_strategy_backtest(
                item.test,
                item.test.historical_data,
                evaluation_source_head=head,
                evaluation_source_tree=tree,
                fold_role=TEST_FOLD_ROLE,
                fold_id=item.fold.fold_id,
            )
        except (ResearchStrategyBacktestError, TypeError, ValueError) as error:
            raise ResearchStrategyWalkForwardError(str(error)) from error


def verify_research_strategy_walk_forward_evidence(
    evidence: ResearchStrategyWalkForwardEvidence,
    definition: ResearchStrategyDefinition,
    evaluation_policy: ResearchStrategyEvaluationPolicy,
    historical_data: HistoricalDataResult,
    folds: tuple[ResearchStrategyWalkForwardFold, ...],
    *,
    evaluation_source_head: str,
    evaluation_source_tree: str,
) -> None:
    """Rebuild and verify aggregate evidence from independently supplied inputs."""
    if type(evidence) is not ResearchStrategyWalkForwardEvidence:
        raise ResearchStrategyWalkForwardError("exact walk-forward evidence required")
    expected = run_research_strategy_walk_forward(
        definition,
        evaluation_policy,
        historical_data,
        folds,
        evaluation_source_head=evaluation_source_head,
        evaluation_source_tree=evaluation_source_tree,
    )
    verify_research_strategy_walk_forward(expected)
    if evidence != expected.evidence:
        raise ResearchStrategyWalkForwardError(
            "walk-forward evidence does not reconcile"
        )


def _median(values: tuple[Decimal, ...]) -> Decimal:
    if not values:
        raise ResearchStrategyWalkForwardError("median requires observations")
    ordered = tuple(sorted(values))
    if len(ordered) % 2:
        return ordered[len(ordered) // 2]
    left = ordered[len(ordered) // 2 - 1]
    right = ordered[len(ordered) // 2]
    precision = (
        max(
            len(left.as_tuple().digits),
            len(right.as_tuple().digits),
        )
        + abs(left.as_tuple().exponent - right.as_tuple().exponent)
        + 2
    )
    with localcontext() as context:
        context.prec = precision
        return (left + right) / Decimal("2")


def qualify_research_strategy_walk_forward(
    completed: CompletedResearchStrategyWalkForward,
    policy: ResearchStrategyWalkForwardQualificationPolicy,
    *,
    qualification_source_head: str,
    qualification_source_tree: str,
) -> ResearchStrategyWalkForwardQualification:
    """Replay every fold, then apply only the explicit threshold policy."""
    if type(policy) is not ResearchStrategyWalkForwardQualificationPolicy:
        raise ResearchStrategyWalkForwardError("exact qualification policy required")
    _validate_policy(policy)
    verify_research_strategy_walk_forward(completed)
    _source(qualification_source_head, "qualification_source_head")
    _source(qualification_source_tree, "qualification_source_tree")
    returns = tuple(
        item.test.performance_report.total_return for item in completed.folds
    )
    drawdowns = tuple(
        item.test.performance_report.maximum_drawdown_percentage
        for item in completed.folds
    )
    counts = tuple(item.evidence.test_bar_count for item in completed.folds)
    return ResearchStrategyWalkForwardQualification(
        completed.definition.definition_id,
        completed.evaluation_policy.policy_id,
        qualification_source_head,
        qualification_source_tree,
        completed.evidence.source_historical_fingerprint,
        completed.evidence.evidence_id,
        policy,
        len(completed.folds),
        counts,
        min(returns),
        _median(returns),
        max(drawdowns),
    )


def verify_research_strategy_walk_forward_qualification(
    qualification: ResearchStrategyWalkForwardQualification,
    completed: CompletedResearchStrategyWalkForward,
    policy: ResearchStrategyWalkForwardQualificationPolicy,
    *,
    qualification_source_head: str,
    qualification_source_tree: str,
) -> None:
    """Reconcile qualification only after replaying its complete evidence chain."""
    _validate_qualification(qualification)
    if qualification.policy != policy:
        raise ResearchStrategyWalkForwardError(
            "qualification policy does not reconcile"
        )
    expected = qualify_research_strategy_walk_forward(
        completed,
        policy,
        qualification_source_head=qualification_source_head,
        qualification_source_tree=qualification_source_tree,
    )
    if qualification != expected:
        raise ResearchStrategyWalkForwardError("qualification does not reconcile")


@dataclass(frozen=True, slots=True)
class WalkForwardPassedResearchStrategy:
    """Separate research-only artifact available only for exact PASS."""

    definition_id: UUID
    evaluation_policy_id: UUID
    qualification_id: UUID
    walk_forward_evidence_id: UUID
    source_head: str
    source_tree: str
    schema: str = field(
        default=RESEARCH_STRATEGY_WALK_FORWARD_PASSED_SCHEMA, init=False
    )
    passed_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        for value, name in (
            (self.definition_id, "definition_id"),
            (self.evaluation_policy_id, "evaluation_policy_id"),
            (self.qualification_id, "qualification_id"),
            (self.walk_forward_evidence_id, "walk_forward_evidence_id"),
        ):
            _uuid(value, name)
        _source(self.source_head, "source_head")
        _source(self.source_tree, "source_tree")
        if self.schema != RESEARCH_STRATEGY_WALK_FORWARD_PASSED_SCHEMA:
            raise ResearchStrategyWalkForwardError("passed schema is fixed")
        object.__setattr__(
            self,
            "passed_id",
            _identity(
                RESEARCH_STRATEGY_WALK_FORWARD_PASSED_NAMESPACE,
                RESEARCH_STRATEGY_WALK_FORWARD_PASSED_IDENTITY_VERSION,
                (
                    self.schema,
                    str(self.definition_id),
                    str(self.evaluation_policy_id),
                    str(self.qualification_id),
                    str(self.walk_forward_evidence_id),
                    self.source_head,
                    self.source_tree,
                ),
            ),
        )

    def to_json(self) -> str:
        _validate_passed(self)
        return _json(
            {
                "schema": self.schema,
                "passed_id": str(self.passed_id),
                "definition_id": str(self.definition_id),
                "evaluation_policy_id": str(self.evaluation_policy_id),
                "qualification_id": str(self.qualification_id),
                "walk_forward_evidence_id": str(self.walk_forward_evidence_id),
                "source_head": self.source_head,
                "source_tree": self.source_tree,
            }
        )

    @classmethod
    def from_json(cls, value: str) -> WalkForwardPassedResearchStrategy:
        try:
            if cls is not WalkForwardPassedResearchStrategy or type(value) is not str:
                raise ResearchStrategyWalkForwardError("exact passed JSON required")
            raw = json.loads(
                value,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
            root = _exact_fields(raw, _PASSED_FIELDS)
            if root["schema"] != RESEARCH_STRATEGY_WALK_FORWARD_PASSED_SCHEMA:
                raise ResearchStrategyWalkForwardError("invalid passed schema")
            result = cls(
                _parse_uuid(root["definition_id"], "definition_id"),
                _parse_uuid(root["evaluation_policy_id"], "evaluation_policy_id"),
                _parse_uuid(root["qualification_id"], "qualification_id"),
                _parse_uuid(
                    root["walk_forward_evidence_id"], "walk_forward_evidence_id"
                ),
                _source(root["source_head"], "source_head"),
                _source(root["source_tree"], "source_tree"),
            )
            if (
                _parse_uuid(root["passed_id"], "passed_id") != result.passed_id
                or result.to_json() != value
            ):
                raise ResearchStrategyWalkForwardError(
                    "passed identity or canonical bytes are inconsistent"
                )
            return result
        except (ArithmeticError, TypeError, UnicodeError, ValueError) as error:
            if isinstance(error, ResearchStrategyWalkForwardError):
                raise
            raise ResearchStrategyWalkForwardError("invalid passed JSON") from None


def _validate_passed(passed: WalkForwardPassedResearchStrategy) -> None:
    if type(passed) is not WalkForwardPassedResearchStrategy:
        raise ResearchStrategyWalkForwardError("exact passed artifact required")
    if passed.schema != RESEARCH_STRATEGY_WALK_FORWARD_PASSED_SCHEMA:
        raise ResearchStrategyWalkForwardError("passed schema is fixed")
    expected = WalkForwardPassedResearchStrategy(
        passed.definition_id,
        passed.evaluation_policy_id,
        passed.qualification_id,
        passed.walk_forward_evidence_id,
        passed.source_head,
        passed.source_tree,
    )
    if type(passed.passed_id) is not UUID or passed.passed_id != expected.passed_id:
        raise ResearchStrategyWalkForwardError("passed_id is inconsistent")


def _project_walk_forward_passed_research_strategy(
    qualification: ResearchStrategyWalkForwardQualification,
) -> WalkForwardPassedResearchStrategy:
    """Project a qualification after its external chain was verified."""
    _validate_qualification(qualification)
    if (
        qualification.status
        is not ResearchStrategyWalkForwardQualificationStatus.PASSED
        or qualification.failure_reasons
    ):
        raise ResearchStrategyWalkForwardError(
            "only exact PASS qualification may create passed evidence"
        )
    return WalkForwardPassedResearchStrategy(
        qualification.definition_id,
        qualification.evaluation_policy_id,
        qualification.qualification_id,
        qualification.walk_forward_evidence_id,
        qualification.qualification_source_head,
        qualification.qualification_source_tree,
    )


def build_walk_forward_passed_research_strategy(
    qualification: ResearchStrategyWalkForwardQualification,
    completed: CompletedResearchStrategyWalkForward,
    policy: ResearchStrategyWalkForwardQualificationPolicy,
    *,
    qualification_source_head: str,
    qualification_source_tree: str,
) -> WalkForwardPassedResearchStrategy:
    """Externally verify the complete chain before projecting PASS evidence."""
    verify_research_strategy_walk_forward_qualification(
        qualification,
        completed,
        policy,
        qualification_source_head=qualification_source_head,
        qualification_source_tree=qualification_source_tree,
    )
    return _project_walk_forward_passed_research_strategy(qualification)


def verify_walk_forward_passed_research_strategy(
    passed: WalkForwardPassedResearchStrategy,
    qualification: ResearchStrategyWalkForwardQualification,
    completed: CompletedResearchStrategyWalkForward,
    policy: ResearchStrategyWalkForwardQualificationPolicy,
    *,
    qualification_source_head: str,
    qualification_source_tree: str,
) -> None:
    """Replay qualification evidence before accepting a PASS artifact."""
    _validate_passed(passed)
    verify_research_strategy_walk_forward_qualification(
        qualification,
        completed,
        policy,
        qualification_source_head=qualification_source_head,
        qualification_source_tree=qualification_source_tree,
    )
    expected = _project_walk_forward_passed_research_strategy(qualification)
    if passed != expected:
        raise ResearchStrategyWalkForwardError("passed artifact does not reconcile")


# Descriptive aliases keep the public family easy to discover while retaining
# one canonical implementation and one canonical serialized vocabulary.
ResearchStrategyWalkForwardPassed = WalkForwardPassedResearchStrategy
build_research_strategy_walk_forward = run_research_strategy_walk_forward
build_research_strategy_walk_forward_passed = (
    build_walk_forward_passed_research_strategy
)
verify_completed_research_strategy_walk_forward = verify_research_strategy_walk_forward


__all__ = [
    "RESEARCH_STRATEGY_WALK_FORWARD_EVIDENCE_IDENTITY_VERSION",
    "RESEARCH_STRATEGY_WALK_FORWARD_EVIDENCE_NAMESPACE",
    "RESEARCH_STRATEGY_WALK_FORWARD_EVIDENCE_SCHEMA",
    "RESEARCH_STRATEGY_WALK_FORWARD_FOLD_IDENTITY_VERSION",
    "RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_IDENTITY_VERSION",
    "RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_NAMESPACE",
    "RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_POLICY_IDENTITY_VERSION",
    "RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_POLICY_NAMESPACE",
    "RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_POLICY_SCHEMA",
    "RESEARCH_STRATEGY_WALK_FORWARD_QUALIFICATION_SCHEMA",
    "RESEARCH_STRATEGY_WALK_FORWARD_PASSED_IDENTITY_VERSION",
    "RESEARCH_STRATEGY_WALK_FORWARD_PASSED_NAMESPACE",
    "RESEARCH_STRATEGY_WALK_FORWARD_PASSED_SCHEMA",
    "TRAINING_FOLD_ROLE",
    "TEST_FOLD_ROLE",
    "CompletedResearchStrategyWalkForward",
    "CompletedResearchStrategyWalkForwardFold",
    "ResearchStrategyWalkForwardError",
    "ResearchStrategyWalkForwardFailureReason",
    "ResearchStrategyWalkForwardFold",
    "ResearchStrategyWalkForwardFoldEvidence",
    "ResearchStrategyWalkForwardEvidence",
    "ResearchStrategyWalkForwardQualification",
    "ResearchStrategyWalkForwardQualificationPolicy",
    "ResearchStrategyWalkForwardQualificationStatus",
    "ResearchStrategyWalkForwardPassed",
    "WalkForwardPassedResearchStrategy",
    "build_research_strategy_walk_forward",
    "build_research_strategy_walk_forward_passed",
    "build_walk_forward_passed_research_strategy",
    "qualify_research_strategy_walk_forward",
    "run_research_strategy_walk_forward",
    "verify_completed_research_strategy_walk_forward",
    "verify_research_strategy_walk_forward",
    "verify_research_strategy_walk_forward_evidence",
    "verify_research_strategy_walk_forward_qualification",
    "verify_walk_forward_passed_research_strategy",
]
