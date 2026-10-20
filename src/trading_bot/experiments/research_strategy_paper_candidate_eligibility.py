"""Pure deterministic Architecture-144 paper-eligibility artifacts.

The artifacts in this module are inert evidence containers.  Parsing proves
only canonical self-consistency; it does not verify external evidence,
acquire files, or grant paper, promotion, or production authority.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID, uuid5

from trading_bot.domain import Symbol
from trading_bot.market_calendar import MarketCalendarError, NYSEMarketCalendar
from trading_bot.strategies.moving_average import MovingAverageCrossoverConfig
from trading_bot.strategies.production import (
    MOVING_AVERAGE_STRATEGY_ID,
    MOVING_AVERAGE_STRATEGY_VERSION,
    PRODUCTION_STRATEGY_SCHEMA,
)

RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_SCHEMA = (
    "research-strategy-paper-session-observation/v1"
)
RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_IDENTITY_VERSION = (
    "research-strategy-paper-session-observation-identity/v1"
)
RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_NAMESPACE = UUID(
    "b39bc4f6-4de1-5dd3-b9ec-286702cd744b"
)

RESEARCH_STRATEGY_PAPER_SOAK_POLICY_SCHEMA = "research-strategy-paper-soak-policy/v1"
RESEARCH_STRATEGY_PAPER_SOAK_POLICY_IDENTITY_VERSION = (
    "research-strategy-paper-soak-policy-identity/v1"
)
RESEARCH_STRATEGY_PAPER_SOAK_POLICY_NAMESPACE = UUID(
    "d0124aa1-3a8e-577f-9848-977fa0adb83a"
)

RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_SCHEMA = (
    "research-strategy-paper-candidate-eligibility/v1"
)
RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_IDENTITY_VERSION = (
    "research-strategy-paper-candidate-eligibility-identity/v1"
)
RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_NAMESPACE = UUID(
    "28ed63ec-8f37-59ce-aad8-57741a645832"
)

REQUIRED_SESSION_COUNT = 5
REQUIRED_PAPER_EXECUTED_COUNT = 1
REQUIRE_CONSECUTIVE_PUBLISHED_REGULAR_SESSIONS = True
QUALIFYING_TERMINAL_CLASSIFICATIONS = ("NO_SIGNAL", "PAPER_EXECUTED")
OBSERVATION_TERMINAL_CLASSIFICATIONS = (
    "NO_SIGNAL",
    "RISK_REJECTED",
    "PAPER_EXECUTED",
)
PAPER_TERMINAL_CLASSIFICATIONS = (
    "NO_SIGNAL",
    "RISK_REJECTED",
    "PAPER_EXECUTED",
)

_SHA40 = re.compile(r"[0-9a-f]{40}")
_SHA64 = re.compile(r"[0-9a-f]{64}")
_OBSERVATION_FIELDS = frozenset(
    {
        "schema",
        "observation_id",
        "compatibility_proof_id",
        "production_target_id",
        "target_session_date",
        "production_contract_id",
        "d1r9_source_head",
        "d1r9_source_tree",
        "d1r8_source_head",
        "d1r8_source_tree",
        "d1r9_journal_sha256",
        "d1r8_journal_sha256",
        "terminal_classification",
        "production_strategy_schema",
        "strategy_id",
        "strategy_version",
        "symbol",
        "strategy_config",
        "production_source_head",
        "production_source_tree",
    }
)
_POLICY_FIELDS = frozenset(
    {
        "schema",
        "policy_id",
        "required_session_count",
        "required_paper_executed_count",
        "require_consecutive_published_regular_sessions",
        "qualifying_terminal_classifications",
    }
)
_ELIGIBILITY_FIELDS = frozenset(
    {
        "schema",
        "eligibility_id",
        "compatibility_proof_id",
        "production_target_id",
        "policy_id",
        "observation_ids",
        "first_session_date",
        "last_session_date",
        "paper_executed_count",
        "production_strategy_schema",
        "strategy_id",
        "strategy_version",
        "symbol",
        "strategy_config",
        "research_strategy_source_head",
        "research_strategy_source_tree",
        "production_source_head",
        "production_source_tree",
        "eligibility_source_head",
        "eligibility_source_tree",
    }
)
_SHARED_OBSERVATION_FIELDS = (
    "compatibility_proof_id",
    "production_target_id",
    "production_strategy_schema",
    "strategy_id",
    "strategy_version",
    "symbol",
    "strategy_config",
    "production_source_head",
    "production_source_tree",
)


class ResearchStrategyPaperCandidateEligibilityError(ValueError):
    """Raised when a paper-eligibility artifact is malformed or inconsistent."""


ResearchStrategyPaperEligibilityError = ResearchStrategyPaperCandidateEligibilityError


def canonical_decimal(value: Decimal) -> str:
    """Return the fixed, context-independent spelling of one finite Decimal."""
    if type(value) is not Decimal or not value.is_finite():
        raise ResearchStrategyPaperCandidateEligibilityError(
            "value must be a finite Decimal"
        )
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return "0" if rendered in {"", "-0"} else rendered


def _frame(value: str) -> str:
    if type(value) is not str:
        raise ResearchStrategyPaperCandidateEligibilityError(
            "identity material must be text"
        )
    try:
        return f"{len(value.encode('utf-8'))}:{value}"
    except UnicodeError:
        raise ResearchStrategyPaperCandidateEligibilityError(
            "identity text must be UTF-8"
        ) from None


def _identity(namespace: UUID, version: str, values: tuple[str, ...]) -> UUID:
    return uuid5(namespace, "".join(_frame(value) for value in (version, *values)))


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, value in pairs:
        if name in result:
            raise ResearchStrategyPaperCandidateEligibilityError("duplicate JSON field")
        result[name] = value
    return result


def _reject_constant(value: str) -> None:
    raise ResearchStrategyPaperCandidateEligibilityError(
        f"non-JSON constant {value} is forbidden"
    )


def _parse_json(value: object) -> object:
    if type(value) is not str:
        raise ResearchStrategyPaperCandidateEligibilityError("JSON text is required")
    try:
        return json.loads(
            value,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError:
        raise ResearchStrategyPaperCandidateEligibilityError("invalid JSON") from None


def _exact_fields(value: object, expected: frozenset[str]) -> dict[str, object]:
    if type(value) is not dict or set(value) != expected:
        raise ResearchStrategyPaperCandidateEligibilityError(
            "exact canonical fields required"
        )
    return value


def _uuid(value: object, name: str) -> UUID:
    if type(value) is not UUID or value.version != 5:
        raise ResearchStrategyPaperCandidateEligibilityError(f"{name} must be a UUID5")
    return value


def _parse_uuid(value: object, name: str) -> UUID:
    if type(value) is not str:
        raise ResearchStrategyPaperCandidateEligibilityError(
            f"{name} must be canonical UUID text"
        )
    try:
        parsed = UUID(value)
    except ValueError:
        raise ResearchStrategyPaperCandidateEligibilityError(
            f"{name} must be canonical UUID text"
        ) from None
    if str(parsed) != value:
        raise ResearchStrategyPaperCandidateEligibilityError(
            f"{name} must be canonical UUID text"
        )
    return _uuid(parsed, name)


def _date(value: object, name: str) -> date:
    if type(value) is not date:
        raise ResearchStrategyPaperCandidateEligibilityError(
            f"{name} must be an exact date"
        )
    return value


def _parse_date(value: object, name: str) -> date:
    if type(value) is not str:
        raise ResearchStrategyPaperCandidateEligibilityError(
            f"{name} must be canonical date text"
        )
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ResearchStrategyPaperCandidateEligibilityError(
            f"{name} must be canonical date text"
        ) from None
    if parsed.isoformat() != value:
        raise ResearchStrategyPaperCandidateEligibilityError(
            f"{name} must be canonical date text"
        )
    return parsed


def _source(value: object, name: str) -> str:
    if type(value) is not str or _SHA40.fullmatch(value) is None:
        raise ResearchStrategyPaperCandidateEligibilityError(
            f"{name} must be exact lowercase 40-hex text"
        )
    return value


def _journal_hash(value: object, name: str) -> str:
    if type(value) is not str or _SHA64.fullmatch(value) is None:
        raise ResearchStrategyPaperCandidateEligibilityError(
            f"{name} must be exact lowercase 64-hex text"
        )
    return value


def _symbol(value: object, name: str) -> Symbol:
    if type(value) is not Symbol or Symbol(str(value)) != value:
        raise ResearchStrategyPaperCandidateEligibilityError(
            f"{name} must be an exact canonical Symbol"
        )
    return value


def _config(value: object) -> MovingAverageCrossoverConfig:
    if type(value) is not MovingAverageCrossoverConfig:
        raise ResearchStrategyPaperCandidateEligibilityError(
            "strategy_config must be an exact MovingAverageCrossoverConfig"
        )
    if type(value.short_window) is not int or type(value.long_window) is not int:
        raise ResearchStrategyPaperCandidateEligibilityError(
            "strategy windows must be exact integers"
        )
    if type(value.desired_quantity) is not Decimal:
        raise ResearchStrategyPaperCandidateEligibilityError(
            "desired_quantity must be an exact Decimal"
        )
    canonical_decimal(value.desired_quantity)
    try:
        canonical = MovingAverageCrossoverConfig(
            value.short_window, value.long_window, value.desired_quantity
        )
    except (TypeError, ValueError) as error:
        raise ResearchStrategyPaperCandidateEligibilityError(str(error)) from error
    if canonical != value:
        raise ResearchStrategyPaperCandidateEligibilityError(
            "strategy_config is inconsistent"
        )
    return value


def _parse_config(value: object) -> MovingAverageCrossoverConfig:
    raw = _exact_fields(
        value, frozenset({"short_window", "long_window", "desired_quantity"})
    )
    if type(raw["short_window"]) is not int or type(raw["long_window"]) is not int:
        raise ResearchStrategyPaperCandidateEligibilityError(
            "strategy windows must be exact JSON integers"
        )
    quantity = raw["desired_quantity"]
    if type(quantity) is not str:
        raise ResearchStrategyPaperCandidateEligibilityError(
            "desired_quantity must be canonical Decimal text"
        )
    try:
        parsed_quantity = Decimal(quantity)
    except ArithmeticError:
        raise ResearchStrategyPaperCandidateEligibilityError(
            "desired_quantity must be a Decimal"
        ) from None
    if canonical_decimal(parsed_quantity) != quantity:
        raise ResearchStrategyPaperCandidateEligibilityError(
            "desired_quantity is not canonical Decimal text"
        )
    try:
        return MovingAverageCrossoverConfig(
            raw["short_window"], raw["long_window"], parsed_quantity
        )
    except (TypeError, ValueError) as error:
        raise ResearchStrategyPaperCandidateEligibilityError(str(error)) from error


def _wire_config(config: MovingAverageCrossoverConfig) -> dict[str, object]:
    _config(config)
    return {
        "short_window": config.short_window,
        "long_window": config.long_window,
        "desired_quantity": canonical_decimal(config.desired_quantity),
    }


def _fixed_strategy(value: object, *, schema: str) -> None:
    if type(value) not in (
        ResearchStrategyPaperSessionObservation,
        ResearchStrategyPaperCandidateEligibility,
    ):
        raise ResearchStrategyPaperCandidateEligibilityError(
            "exact paper artifact type required"
        )
    if value.schema != schema:
        raise ResearchStrategyPaperCandidateEligibilityError("fixed schema required")
    if value.production_strategy_schema != PRODUCTION_STRATEGY_SCHEMA:
        raise ResearchStrategyPaperCandidateEligibilityError(
            "production strategy schema is fixed"
        )
    if value.strategy_id != MOVING_AVERAGE_STRATEGY_ID:
        raise ResearchStrategyPaperCandidateEligibilityError("strategy id is fixed")
    if value.strategy_version != MOVING_AVERAGE_STRATEGY_VERSION:
        raise ResearchStrategyPaperCandidateEligibilityError(
            "strategy version is fixed"
        )
    _symbol(value.symbol, "symbol")
    _config(value.strategy_config)


def _regular_session_dates(start: date, end: date) -> tuple[date, ...]:
    if start > end:
        raise ResearchStrategyPaperCandidateEligibilityError(
            "session dates must be ordered"
        )
    calendar = NYSEMarketCalendar()
    result: list[date] = []
    current = start
    try:
        while current <= end:
            if calendar.is_trading_session(
                datetime.combine(current, time(12), tzinfo=UTC)
            ):
                result.append(current)
            current += timedelta(days=1)
    except MarketCalendarError as error:
        raise ResearchStrategyPaperCandidateEligibilityError(
            "session dates must be supported NYSE regular sessions"
        ) from error
    return tuple(result)


def _observation_material(
    observation: ResearchStrategyPaperSessionObservation,
) -> tuple[str, ...]:
    _validate_observation(observation, check_identity=False)
    config = observation.strategy_config
    return (
        observation.schema,
        str(observation.compatibility_proof_id),
        str(observation.production_target_id),
        observation.target_session_date.isoformat(),
        str(observation.production_contract_id),
        observation.d1r9_source_head,
        observation.d1r9_source_tree,
        observation.d1r8_source_head,
        observation.d1r8_source_tree,
        observation.d1r9_journal_sha256,
        observation.d1r8_journal_sha256,
        observation.terminal_classification,
        observation.production_strategy_schema,
        observation.strategy_id,
        observation.strategy_version,
        str(observation.symbol),
        str(config.short_window),
        str(config.long_window),
        canonical_decimal(config.desired_quantity),
        observation.production_source_head,
        observation.production_source_tree,
    )


def _validate_observation(
    observation: ResearchStrategyPaperSessionObservation, *, check_identity: bool = True
) -> None:
    _fixed_strategy(
        observation, schema=RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_SCHEMA
    )
    for name in (
        "compatibility_proof_id",
        "production_target_id",
        "production_contract_id",
    ):
        _uuid(getattr(observation, name), name)
    _date(observation.target_session_date, "target_session_date")
    for name in (
        "d1r9_source_head",
        "d1r9_source_tree",
        "d1r8_source_head",
        "d1r8_source_tree",
        "production_source_head",
        "production_source_tree",
    ):
        _source(getattr(observation, name), name)
    for name in ("d1r9_journal_sha256", "d1r8_journal_sha256"):
        _journal_hash(getattr(observation, name), name)
    if (
        type(observation.terminal_classification) is not str
        or observation.terminal_classification
        not in OBSERVATION_TERMINAL_CLASSIFICATIONS
    ):
        raise ResearchStrategyPaperCandidateEligibilityError(
            "terminal classification is not recognized"
        )
    if check_identity:
        expected = _identity(
            RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_NAMESPACE,
            RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_IDENTITY_VERSION,
            _observation_material(observation),
        )
        if _uuid(observation.observation_id, "observation_id") != expected:
            raise ResearchStrategyPaperCandidateEligibilityError(
                "observation_id is inconsistent"
            )


@dataclass(frozen=True, slots=True)
class ResearchStrategyPaperSessionObservation:
    """One inert, self-consistent paper-session observation container."""

    schema: str = field(
        default=RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_SCHEMA, init=False
    )
    observation_id: UUID = field(init=False)
    compatibility_proof_id: UUID
    production_target_id: UUID
    target_session_date: date
    production_contract_id: UUID
    d1r9_source_head: str
    d1r9_source_tree: str
    d1r8_source_head: str
    d1r8_source_tree: str
    d1r9_journal_sha256: str
    d1r8_journal_sha256: str
    terminal_classification: str
    production_strategy_schema: str = field(
        default=PRODUCTION_STRATEGY_SCHEMA, init=False
    )
    strategy_id: str = field(default=MOVING_AVERAGE_STRATEGY_ID, init=False)
    strategy_version: str = field(default=MOVING_AVERAGE_STRATEGY_VERSION, init=False)
    symbol: Symbol
    strategy_config: MovingAverageCrossoverConfig
    production_source_head: str
    production_source_tree: str

    def __post_init__(self) -> None:
        _validate_observation(self, check_identity=False)
        object.__setattr__(
            self,
            "observation_id",
            _identity(
                RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_NAMESPACE,
                RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_IDENTITY_VERSION,
                _observation_material(self),
            ),
        )

    def to_json(self) -> str:
        """Serialize the exact compact canonical observation representation."""
        _validate_observation(self)
        return _json(
            {
                "schema": self.schema,
                "observation_id": str(self.observation_id),
                "compatibility_proof_id": str(self.compatibility_proof_id),
                "production_target_id": str(self.production_target_id),
                "target_session_date": self.target_session_date.isoformat(),
                "production_contract_id": str(self.production_contract_id),
                "d1r9_source_head": self.d1r9_source_head,
                "d1r9_source_tree": self.d1r9_source_tree,
                "d1r8_source_head": self.d1r8_source_head,
                "d1r8_source_tree": self.d1r8_source_tree,
                "d1r9_journal_sha256": self.d1r9_journal_sha256,
                "d1r8_journal_sha256": self.d1r8_journal_sha256,
                "terminal_classification": self.terminal_classification,
                "production_strategy_schema": self.production_strategy_schema,
                "strategy_id": self.strategy_id,
                "strategy_version": self.strategy_version,
                "symbol": str(self.symbol),
                "strategy_config": _wire_config(self.strategy_config),
                "production_source_head": self.production_source_head,
                "production_source_tree": self.production_source_tree,
            }
        )

    @classmethod
    def from_json(cls, value: str) -> ResearchStrategyPaperSessionObservation:
        """Parse canonical self-consistency without external verification."""
        if cls is not ResearchStrategyPaperSessionObservation:
            raise ResearchStrategyPaperCandidateEligibilityError(
                "exact observation class required"
            )
        try:
            raw = _exact_fields(_parse_json(value), _OBSERVATION_FIELDS)
            if raw["schema"] != RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_SCHEMA:
                raise ResearchStrategyPaperCandidateEligibilityError(
                    "invalid observation schema"
                )
            symbol_text = raw["symbol"]
            if type(symbol_text) is not str or str(Symbol(symbol_text)) != symbol_text:
                raise ResearchStrategyPaperCandidateEligibilityError(
                    "symbol must be canonical text"
                )
            result = cls(
                compatibility_proof_id=_parse_uuid(
                    raw["compatibility_proof_id"], "compatibility_proof_id"
                ),
                production_target_id=_parse_uuid(
                    raw["production_target_id"], "production_target_id"
                ),
                target_session_date=_parse_date(
                    raw["target_session_date"], "target_session_date"
                ),
                production_contract_id=_parse_uuid(
                    raw["production_contract_id"], "production_contract_id"
                ),
                d1r9_source_head=_source(raw["d1r9_source_head"], "d1r9_source_head"),
                d1r9_source_tree=_source(raw["d1r9_source_tree"], "d1r9_source_tree"),
                d1r8_source_head=_source(raw["d1r8_source_head"], "d1r8_source_head"),
                d1r8_source_tree=_source(raw["d1r8_source_tree"], "d1r8_source_tree"),
                d1r9_journal_sha256=_journal_hash(
                    raw["d1r9_journal_sha256"], "d1r9_journal_sha256"
                ),
                d1r8_journal_sha256=_journal_hash(
                    raw["d1r8_journal_sha256"], "d1r8_journal_sha256"
                ),
                terminal_classification=raw["terminal_classification"],
                symbol=Symbol(symbol_text),
                strategy_config=_parse_config(raw["strategy_config"]),
                production_source_head=_source(
                    raw["production_source_head"], "production_source_head"
                ),
                production_source_tree=_source(
                    raw["production_source_tree"], "production_source_tree"
                ),
            )
            if (
                _parse_uuid(raw["observation_id"], "observation_id")
                != result.observation_id
                or result.to_json() != value
            ):
                raise ResearchStrategyPaperCandidateEligibilityError(
                    "observation identity or canonical bytes are inconsistent"
                )
            return result
        except ResearchStrategyPaperCandidateEligibilityError:
            raise
        except (ArithmeticError, TypeError, UnicodeError, ValueError) as error:
            raise ResearchStrategyPaperCandidateEligibilityError(
                "invalid observation JSON"
            ) from error


def _policy_material(policy: ResearchStrategyPaperSoakPolicy) -> tuple[str, ...]:
    _validate_policy(policy, check_identity=False)
    return (
        policy.schema,
        str(policy.required_session_count),
        str(policy.required_paper_executed_count),
        "true",
        str(len(policy.qualifying_terminal_classifications)),
        *policy.qualifying_terminal_classifications,
    )


def _validate_policy(
    policy: ResearchStrategyPaperSoakPolicy, *, check_identity: bool = True
) -> None:
    if type(policy) is not ResearchStrategyPaperSoakPolicy:
        raise ResearchStrategyPaperCandidateEligibilityError(
            "exact soak policy type required"
        )
    if policy.schema != RESEARCH_STRATEGY_PAPER_SOAK_POLICY_SCHEMA:
        raise ResearchStrategyPaperCandidateEligibilityError("fixed policy schema")
    if type(policy.required_session_count) is not int or (
        policy.required_session_count != REQUIRED_SESSION_COUNT
    ):
        raise ResearchStrategyPaperCandidateEligibilityError(
            "required session count is fixed"
        )
    if type(policy.required_paper_executed_count) is not int or (
        policy.required_paper_executed_count != REQUIRED_PAPER_EXECUTED_COUNT
    ):
        raise ResearchStrategyPaperCandidateEligibilityError(
            "required execution count is fixed"
        )
    if policy.require_consecutive_published_regular_sessions is not True:
        raise ResearchStrategyPaperCandidateEligibilityError(
            "consecutive-session policy is fixed"
        )
    if policy.qualifying_terminal_classifications != (
        QUALIFYING_TERMINAL_CLASSIFICATIONS
    ):
        raise ResearchStrategyPaperCandidateEligibilityError(
            "qualifying classification order is fixed"
        )
    if check_identity:
        expected = _identity(
            RESEARCH_STRATEGY_PAPER_SOAK_POLICY_NAMESPACE,
            RESEARCH_STRATEGY_PAPER_SOAK_POLICY_IDENTITY_VERSION,
            _policy_material(policy),
        )
        if _uuid(policy.policy_id, "policy_id") != expected:
            raise ResearchStrategyPaperCandidateEligibilityError(
                "policy_id is inconsistent"
            )


@dataclass(frozen=True, slots=True)
class ResearchStrategyPaperSoakPolicy:
    """The immutable Architecture-144 paper-soak v1 policy."""

    schema: str = field(default=RESEARCH_STRATEGY_PAPER_SOAK_POLICY_SCHEMA, init=False)
    policy_id: UUID = field(init=False)
    required_session_count: int = field(default=REQUIRED_SESSION_COUNT, init=False)
    required_paper_executed_count: int = field(
        default=REQUIRED_PAPER_EXECUTED_COUNT, init=False
    )
    require_consecutive_published_regular_sessions: bool = field(
        default=REQUIRE_CONSECUTIVE_PUBLISHED_REGULAR_SESSIONS, init=False
    )
    qualifying_terminal_classifications: tuple[str, ...] = field(
        default=QUALIFYING_TERMINAL_CLASSIFICATIONS, init=False
    )

    def __post_init__(self) -> None:
        _validate_policy(self, check_identity=False)
        object.__setattr__(
            self,
            "policy_id",
            _identity(
                RESEARCH_STRATEGY_PAPER_SOAK_POLICY_NAMESPACE,
                RESEARCH_STRATEGY_PAPER_SOAK_POLICY_IDENTITY_VERSION,
                _policy_material(self),
            ),
        )

    def to_json(self) -> str:
        """Serialize the exact compact canonical policy representation."""
        _validate_policy(self)
        return _json(
            {
                "schema": self.schema,
                "policy_id": str(self.policy_id),
                "required_session_count": self.required_session_count,
                "required_paper_executed_count": self.required_paper_executed_count,
                "require_consecutive_published_regular_sessions": (
                    self.require_consecutive_published_regular_sessions
                ),
                "qualifying_terminal_classifications": list(
                    self.qualifying_terminal_classifications
                ),
            }
        )

    @classmethod
    def from_json(cls, value: str) -> ResearchStrategyPaperSoakPolicy:
        """Parse the fixed policy without accepting caller-selected policy values."""
        if cls is not ResearchStrategyPaperSoakPolicy:
            raise ResearchStrategyPaperCandidateEligibilityError(
                "exact policy class required"
            )
        try:
            raw = _exact_fields(_parse_json(value), _POLICY_FIELDS)
            if (
                type(raw["required_session_count"]) is not int
                or type(raw["required_paper_executed_count"]) is not int
                or type(raw["require_consecutive_published_regular_sessions"])
                is not bool
                or type(raw["qualifying_terminal_classifications"]) is not list
                or any(
                    type(item) is not str
                    for item in raw["qualifying_terminal_classifications"]
                )
            ):
                raise ResearchStrategyPaperCandidateEligibilityError(
                    "invalid policy value types"
                )
            result = cls()
            if (
                raw["schema"] != result.schema
                or raw["required_session_count"] != result.required_session_count
                or raw["required_paper_executed_count"]
                != result.required_paper_executed_count
                or raw["require_consecutive_published_regular_sessions"]
                != result.require_consecutive_published_regular_sessions
                or tuple(raw["qualifying_terminal_classifications"])
                != result.qualifying_terminal_classifications
                or _parse_uuid(raw["policy_id"], "policy_id") != result.policy_id
                or result.to_json() != value
            ):
                raise ResearchStrategyPaperCandidateEligibilityError(
                    "policy identity or canonical bytes are inconsistent"
                )
            return result
        except ResearchStrategyPaperCandidateEligibilityError:
            raise
        except (ArithmeticError, TypeError, UnicodeError, ValueError) as error:
            raise ResearchStrategyPaperCandidateEligibilityError(
                "invalid policy JSON"
            ) from error


def _eligibility_material(
    eligibility: ResearchStrategyPaperCandidateEligibility,
) -> tuple[str, ...]:
    _validate_eligibility(eligibility, check_identity=False)
    config = eligibility.strategy_config
    return (
        eligibility.schema,
        str(eligibility.compatibility_proof_id),
        str(eligibility.production_target_id),
        str(eligibility.policy_id),
        str(len(eligibility.observation_ids)),
        *(str(item) for item in eligibility.observation_ids),
        eligibility.first_session_date.isoformat(),
        eligibility.last_session_date.isoformat(),
        str(eligibility.paper_executed_count),
        eligibility.production_strategy_schema,
        eligibility.strategy_id,
        eligibility.strategy_version,
        str(eligibility.symbol),
        str(config.short_window),
        str(config.long_window),
        canonical_decimal(config.desired_quantity),
        eligibility.research_strategy_source_head,
        eligibility.research_strategy_source_tree,
        eligibility.production_source_head,
        eligibility.production_source_tree,
        eligibility.eligibility_source_head,
        eligibility.eligibility_source_tree,
    )


def _validate_eligibility(
    eligibility: ResearchStrategyPaperCandidateEligibility,
    *,
    check_identity: bool = True,
) -> None:
    _fixed_strategy(
        eligibility, schema=RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_SCHEMA
    )
    for name in ("compatibility_proof_id", "production_target_id", "policy_id"):
        _uuid(getattr(eligibility, name), name)
    expected_policy = ResearchStrategyPaperSoakPolicy().policy_id
    if eligibility.policy_id != expected_policy:
        raise ResearchStrategyPaperCandidateEligibilityError(
            "eligibility must use the fixed v1 policy"
        )
    if (
        type(eligibility.observation_ids) is not tuple
        or len(eligibility.observation_ids) != REQUIRED_SESSION_COUNT
    ):
        raise ResearchStrategyPaperCandidateEligibilityError(
            "eligibility requires five unique observation IDs"
        )
    for item in eligibility.observation_ids:
        _uuid(item, "observation_id")
    if len(set(eligibility.observation_ids)) != len(eligibility.observation_ids):
        raise ResearchStrategyPaperCandidateEligibilityError(
            "eligibility requires five unique observation IDs"
        )
    _date(eligibility.first_session_date, "first_session_date")
    _date(eligibility.last_session_date, "last_session_date")
    regular_dates = _regular_session_dates(
        eligibility.first_session_date, eligibility.last_session_date
    )
    if (
        len(regular_dates) != REQUIRED_SESSION_COUNT
        or regular_dates[0] != eligibility.first_session_date
        or regular_dates[-1] != eligibility.last_session_date
    ):
        raise ResearchStrategyPaperCandidateEligibilityError(
            "eligibility dates must bound five consecutive regular sessions"
        )
    if type(eligibility.paper_executed_count) is not int or not (
        REQUIRED_PAPER_EXECUTED_COUNT
        <= eligibility.paper_executed_count
        <= REQUIRED_SESSION_COUNT
    ):
        raise ResearchStrategyPaperCandidateEligibilityError(
            "eligibility requires execution evidence count of at least one"
        )
    for name in (
        "research_strategy_source_head",
        "research_strategy_source_tree",
        "production_source_head",
        "production_source_tree",
        "eligibility_source_head",
        "eligibility_source_tree",
    ):
        _source(getattr(eligibility, name), name)
    if check_identity:
        expected = _identity(
            RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_NAMESPACE,
            RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_IDENTITY_VERSION,
            _eligibility_material(eligibility),
        )
        if _uuid(eligibility.eligibility_id, "eligibility_id") != expected:
            raise ResearchStrategyPaperCandidateEligibilityError(
                "eligibility_id is inconsistent"
            )


@dataclass(frozen=True, slots=True)
class ResearchStrategyPaperCandidateEligibility:
    """Positive-only, inert eligibility evidence with no boolean status field."""

    schema: str = field(
        default=RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_SCHEMA, init=False
    )
    eligibility_id: UUID = field(init=False)
    compatibility_proof_id: UUID
    production_target_id: UUID
    policy_id: UUID
    observation_ids: tuple[UUID, ...]
    first_session_date: date
    last_session_date: date
    paper_executed_count: int
    production_strategy_schema: str = field(
        default=PRODUCTION_STRATEGY_SCHEMA, init=False
    )
    strategy_id: str = field(default=MOVING_AVERAGE_STRATEGY_ID, init=False)
    strategy_version: str = field(default=MOVING_AVERAGE_STRATEGY_VERSION, init=False)
    symbol: Symbol
    strategy_config: MovingAverageCrossoverConfig
    research_strategy_source_head: str
    research_strategy_source_tree: str
    production_source_head: str
    production_source_tree: str
    eligibility_source_head: str
    eligibility_source_tree: str

    def __post_init__(self) -> None:
        _validate_eligibility(self, check_identity=False)
        object.__setattr__(
            self,
            "eligibility_id",
            _identity(
                RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_NAMESPACE,
                RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_IDENTITY_VERSION,
                _eligibility_material(self),
            ),
        )

    def to_json(self) -> str:
        """Serialize the exact compact canonical eligibility representation."""
        _validate_eligibility(self)
        return _json(
            {
                "schema": self.schema,
                "eligibility_id": str(self.eligibility_id),
                "compatibility_proof_id": str(self.compatibility_proof_id),
                "production_target_id": str(self.production_target_id),
                "policy_id": str(self.policy_id),
                "observation_ids": [str(item) for item in self.observation_ids],
                "first_session_date": self.first_session_date.isoformat(),
                "last_session_date": self.last_session_date.isoformat(),
                "paper_executed_count": self.paper_executed_count,
                "production_strategy_schema": self.production_strategy_schema,
                "strategy_id": self.strategy_id,
                "strategy_version": self.strategy_version,
                "symbol": str(self.symbol),
                "strategy_config": _wire_config(self.strategy_config),
                "research_strategy_source_head": self.research_strategy_source_head,
                "research_strategy_source_tree": self.research_strategy_source_tree,
                "production_source_head": self.production_source_head,
                "production_source_tree": self.production_source_tree,
                "eligibility_source_head": self.eligibility_source_head,
                "eligibility_source_tree": self.eligibility_source_tree,
            }
        )

    @classmethod
    def from_json(cls, value: str) -> ResearchStrategyPaperCandidateEligibility:
        """Parse canonical self-consistency without external verification."""
        if cls is not ResearchStrategyPaperCandidateEligibility:
            raise ResearchStrategyPaperCandidateEligibilityError(
                "exact eligibility class required"
            )
        try:
            raw = _exact_fields(_parse_json(value), _ELIGIBILITY_FIELDS)
            if raw["schema"] != RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_SCHEMA:
                raise ResearchStrategyPaperCandidateEligibilityError(
                    "invalid eligibility schema"
                )
            observation_ids = raw["observation_ids"]
            if type(observation_ids) is not list:
                raise ResearchStrategyPaperCandidateEligibilityError(
                    "observation_ids must be an array"
                )
            parsed_observation_ids = tuple(
                _parse_uuid(item, "observation_id") for item in observation_ids
            )
            symbol_text = raw["symbol"]
            if type(symbol_text) is not str or str(Symbol(symbol_text)) != symbol_text:
                raise ResearchStrategyPaperCandidateEligibilityError(
                    "symbol must be canonical text"
                )
            result = cls(
                compatibility_proof_id=_parse_uuid(
                    raw["compatibility_proof_id"], "compatibility_proof_id"
                ),
                production_target_id=_parse_uuid(
                    raw["production_target_id"], "production_target_id"
                ),
                policy_id=_parse_uuid(raw["policy_id"], "policy_id"),
                observation_ids=parsed_observation_ids,
                first_session_date=_parse_date(
                    raw["first_session_date"], "first_session_date"
                ),
                last_session_date=_parse_date(
                    raw["last_session_date"], "last_session_date"
                ),
                paper_executed_count=raw["paper_executed_count"],
                symbol=Symbol(symbol_text),
                strategy_config=_parse_config(raw["strategy_config"]),
                research_strategy_source_head=_source(
                    raw["research_strategy_source_head"],
                    "research_strategy_source_head",
                ),
                research_strategy_source_tree=_source(
                    raw["research_strategy_source_tree"],
                    "research_strategy_source_tree",
                ),
                production_source_head=_source(
                    raw["production_source_head"], "production_source_head"
                ),
                production_source_tree=_source(
                    raw["production_source_tree"], "production_source_tree"
                ),
                eligibility_source_head=_source(
                    raw["eligibility_source_head"], "eligibility_source_head"
                ),
                eligibility_source_tree=_source(
                    raw["eligibility_source_tree"], "eligibility_source_tree"
                ),
            )
            if (
                _parse_uuid(raw["eligibility_id"], "eligibility_id")
                != result.eligibility_id
                or result.to_json() != value
            ):
                raise ResearchStrategyPaperCandidateEligibilityError(
                    "eligibility identity or canonical bytes are inconsistent"
                )
            return result
        except ResearchStrategyPaperCandidateEligibilityError:
            raise
        except (ArithmeticError, TypeError, UnicodeError, ValueError) as error:
            raise ResearchStrategyPaperCandidateEligibilityError(
                "invalid eligibility JSON"
            ) from error


def validate_research_strategy_paper_eligibility_window(
    observations: tuple[ResearchStrategyPaperSessionObservation, ...],
    policy: ResearchStrategyPaperSoakPolicy | None = None,
) -> int:
    """Validate a complete five-session window and return its execution count.

    This is a pure intrinsic check.  It does not verify the external evidence
    referenced by an observation and does not construct an eligibility artifact.
    """
    selected_policy = ResearchStrategyPaperSoakPolicy() if policy is None else policy
    _validate_policy(selected_policy)
    if type(observations) is not tuple:
        raise ResearchStrategyPaperCandidateEligibilityError(
            "observations must be an ordered tuple"
        )
    if len(observations) != selected_policy.required_session_count:
        raise ResearchStrategyPaperCandidateEligibilityError(
            "exactly five observations are required"
        )
    for observation in observations:
        _validate_observation(observation)
    dates = tuple(observation.target_session_date for observation in observations)
    expected_dates = _regular_session_dates(dates[0], dates[-1])
    if dates != expected_dates:
        raise ResearchStrategyPaperCandidateEligibilityError(
            "observations must be exactly consecutive regular sessions"
        )
    reference = observations[0]
    for observation in observations[1:]:
        if any(
            getattr(observation, name) != getattr(reference, name)
            for name in _SHARED_OBSERVATION_FIELDS
        ):
            raise ResearchStrategyPaperCandidateEligibilityError(
                "observation semantic fields must remain stable across the window"
            )
    if any(
        observation.terminal_classification
        not in selected_policy.qualifying_terminal_classifications
        for observation in observations
    ):
        raise ResearchStrategyPaperCandidateEligibilityError(
            "window contains a nonqualifying terminal classification"
        )
    paper_executed_count = sum(
        observation.terminal_classification == "PAPER_EXECUTED"
        for observation in observations
    )
    if paper_executed_count < selected_policy.required_paper_executed_count:
        raise ResearchStrategyPaperCandidateEligibilityError(
            "window lacks required paper execution evidence"
        )
    return paper_executed_count


__all__ = [
    "OBSERVATION_TERMINAL_CLASSIFICATIONS",
    "PAPER_TERMINAL_CLASSIFICATIONS",
    "QUALIFYING_TERMINAL_CLASSIFICATIONS",
    "REQUIRED_PAPER_EXECUTED_COUNT",
    "REQUIRED_SESSION_COUNT",
    "REQUIRE_CONSECUTIVE_PUBLISHED_REGULAR_SESSIONS",
    "RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_IDENTITY_VERSION",
    "RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_NAMESPACE",
    "RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_SCHEMA",
    "RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_IDENTITY_VERSION",
    "RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_NAMESPACE",
    "RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_SCHEMA",
    "RESEARCH_STRATEGY_PAPER_SOAK_POLICY_IDENTITY_VERSION",
    "RESEARCH_STRATEGY_PAPER_SOAK_POLICY_NAMESPACE",
    "RESEARCH_STRATEGY_PAPER_SOAK_POLICY_SCHEMA",
    "ResearchStrategyPaperCandidateEligibility",
    "ResearchStrategyPaperCandidateEligibilityError",
    "ResearchStrategyPaperEligibilityError",
    "ResearchStrategyPaperSessionObservation",
    "ResearchStrategyPaperSoakPolicy",
    "canonical_decimal",
    "validate_research_strategy_paper_eligibility_window",
]
