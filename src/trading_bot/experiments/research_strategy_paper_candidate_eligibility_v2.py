"""Pure deterministic Architecture-144-C V2 F1 paper-eligibility artifacts.

The artifacts in this module are inert evidence containers.  Parsing proves
only canonical self-consistency; it does not verify external evidence,
acquire files, or grant paper, promotion, or production authority.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, fields
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID, uuid5

from trading_bot.domain import Symbol
from trading_bot.experiments.research_strategy_paper_candidate_eligibility import (
    OBSERVATION_TERMINAL_CLASSIFICATIONS,
    REQUIRED_PAPER_EXECUTED_COUNT,
    REQUIRED_SESSION_COUNT,
    ResearchStrategyPaperCandidateEligibilityError,
    ResearchStrategyPaperSoakPolicy,
    canonical_decimal,
)
from trading_bot.market_calendar import MarketCalendarError, NYSEMarketCalendar
from trading_bot.strategies.moving_average import MovingAverageCrossoverConfig
from trading_bot.strategies.production import (
    MOVING_AVERAGE_STRATEGY_ID,
    MOVING_AVERAGE_STRATEGY_VERSION,
    PRODUCTION_STRATEGY_SCHEMA,
)

RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_V2_SCHEMA = (
    "research-strategy-paper-session-observation/v2"
)
RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_V2_IDENTITY_VERSION = (
    "research-strategy-paper-session-observation-identity/v2"
)
RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_V2_NAMESPACE = UUID(
    "8769f313-42dc-512f-91b2-e0299f6c9200"
)
RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_V2_SCHEMA = (
    "research-strategy-paper-candidate-eligibility/v2"
)
RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_V2_IDENTITY_VERSION = (
    "research-strategy-paper-candidate-eligibility-identity/v2"
)
RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_V2_NAMESPACE = UUID(
    "98822733-db5a-5382-b362-a441861d56e1"
)
PAPER_AUTHORITY_KIND = "ARCH134_F1"
PAPER_AUTHORITY_SCHEMA = "arch134-f1-five-session-soak/v1"
PAPER_AUTHORITY_SOURCE_HEAD = "b59ad3b44540a55a30f612d5c4e3e38e26a95b02"
PAPER_AUTHORITY_SOURCE_TREE = "e8a94e3512d7950f2fbc9c4d102a58b63e03244f"
D1R7_SOURCE_HEAD = "30322c49b13b80af8d20acee4bdb1efd83d86260"
D1R7_SOURCE_TREE = "b7dc7f054fca50c3ab784505f264b6f716a45dff"
D1R8_SOURCE_HEAD = "aa07c5ba94e0b55cbd8f920464fcc5bd9efcabd2"
D1R8_SOURCE_TREE = "fcbfc348dab307fb9c456ce9e17aad0e53d7bd4f"
_SHA40 = re.compile(r"[0-9a-f]{40}")
_SHA64 = re.compile(r"[0-9a-f]{64}")
_OBSERVATION_FIELDS = frozenset(
    (
        "schema",
        "observation_id",
        "compatibility_proof_id",
        "production_target_id",
        "target_session_date",
        "production_contract_id",
        "paper_authority_kind",
        "paper_authority_schema",
        "paper_authority_source_head",
        "paper_authority_source_tree",
        "authority_parent_id",
        "authority_parent_journal_sha256",
        "authority_child_ordinal",
        "authority_child_id",
        "authority_child_journal_sha256",
        "d1r7_source_head",
        "d1r7_source_tree",
        "d1r7_evidence_sha256",
        "d1r8_source_head",
        "d1r8_source_tree",
        "d1r8_evidence_sha256",
        "terminal_classification",
        "production_strategy_schema",
        "strategy_id",
        "strategy_version",
        "symbol",
        "strategy_config",
        "production_source_head",
        "production_source_tree",
    )
)
_ELIGIBILITY_FIELDS = frozenset(
    (
        "schema",
        "eligibility_id",
        "compatibility_proof_id",
        "production_target_id",
        "policy_id",
        "paper_authority_kind",
        "paper_authority_schema",
        "paper_authority_source_head",
        "paper_authority_source_tree",
        "authority_parent_id",
        "authority_parent_journal_sha256",
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
    )
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
    "paper_authority_kind",
    "paper_authority_schema",
    "paper_authority_source_head",
    "paper_authority_source_tree",
    "authority_parent_id",
    "authority_parent_journal_sha256",
)


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
        ResearchStrategyPaperSessionObservationV2,
        ResearchStrategyPaperCandidateEligibilityV2,
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


def _validate_authority(value: object) -> None:
    if type(value) not in (
        ResearchStrategyPaperSessionObservationV2,
        ResearchStrategyPaperCandidateEligibilityV2,
    ):
        raise ResearchStrategyPaperCandidateEligibilityError(
            "exact V2 artifact required"
        )
    for name, expected in (
        ("paper_authority_kind", PAPER_AUTHORITY_KIND),
        ("paper_authority_schema", PAPER_AUTHORITY_SCHEMA),
        ("paper_authority_source_head", PAPER_AUTHORITY_SOURCE_HEAD),
        ("paper_authority_source_tree", PAPER_AUTHORITY_SOURCE_TREE),
    ):
        if type(getattr(value, name)) is not str or getattr(value, name) != expected:
            raise ResearchStrategyPaperCandidateEligibilityError(
                "fixed accepted F1 authority required"
            )
    _uuid(value.authority_parent_id, "authority_parent_id")
    _journal_hash(
        value.authority_parent_journal_sha256, "authority_parent_journal_sha256"
    )


def _wire(value: object) -> object:
    if type(value) is UUID or type(value) is Symbol:
        return str(value)
    if type(value) is date:
        return value.isoformat()
    if type(value) is MovingAverageCrossoverConfig:
        return _wire_config(value)
    if type(value) is tuple:
        return [_wire(item) for item in value]
    return value


def _to_json(value: object) -> str:
    return _json(
        {item.name: _wire(getattr(value, item.name)) for item in fields(value)}
    )


def _from_json(cls: type, value: str, expected: frozenset[str], identity: str):
    try:
        raw = _exact_fields(_parse_json(value), expected)
        kwargs = {}
        for item in fields(cls):
            if not item.init:
                continue
            name = item.name
            entry = raw[name]
            if name == "observation_ids":
                if type(entry) is not list:
                    raise ResearchStrategyPaperCandidateEligibilityError(
                        "ordered observation array required"
                    )
                entry = tuple(_parse_uuid(i, "observation_id") for i in entry)
            elif name.endswith("_id") and name != "strategy_id":
                entry = _parse_uuid(entry, name)
            elif name.endswith("_date"):
                entry = _parse_date(entry, name)
            elif name == "symbol":
                if type(entry) is not str or str(Symbol(entry)) != entry:
                    raise ResearchStrategyPaperCandidateEligibilityError(
                        "canonical symbol required"
                    )
                entry = Symbol(entry)
            elif name == "strategy_config":
                entry = _parse_config(entry)
            kwargs[name] = entry
        result = cls(**kwargs)
        if (
            _parse_uuid(raw[identity], identity) != getattr(result, identity)
            or result.to_json() != value
        ):
            raise ResearchStrategyPaperCandidateEligibilityError(
                "identity or canonical bytes inconsistent"
            )
        return result
    except ResearchStrategyPaperCandidateEligibilityError:
        raise
    except (
        ArithmeticError,
        TypeError,
        UnicodeError,
        ValueError,
        RecursionError,
    ) as error:
        raise ResearchStrategyPaperCandidateEligibilityError(
            "invalid V2 artifact JSON"
        ) from error


def _validate_observation(
    observation: ResearchStrategyPaperSessionObservationV2,
    *,
    check_identity: bool = True,
) -> None:
    _validate_authority(observation)
    _fixed_strategy(
        observation, schema=RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_V2_SCHEMA
    )
    for name in (
        "compatibility_proof_id",
        "production_target_id",
        "production_contract_id",
    ):
        _uuid(getattr(observation, name), name)
    _date(observation.target_session_date, "target_session_date")
    for name in (
        "d1r7_source_head",
        "d1r7_source_tree",
        "d1r8_source_head",
        "d1r8_source_tree",
        "production_source_head",
        "production_source_tree",
    ):
        _source(getattr(observation, name), name)
    for name in (
        "authority_child_journal_sha256",
        "d1r7_evidence_sha256",
        "d1r8_evidence_sha256",
    ):
        _journal_hash(getattr(observation, name), name)
    if (
        type(observation.terminal_classification) is not str
        or observation.terminal_classification
        not in OBSERVATION_TERMINAL_CLASSIFICATIONS
    ):
        raise ResearchStrategyPaperCandidateEligibilityError(
            "terminal classification is not recognized"
        )
    _uuid(observation.authority_child_id, "authority_child_id")
    if (
        type(observation.authority_child_ordinal) is not int
        or not 1 <= observation.authority_child_ordinal <= 5
    ):
        raise ResearchStrategyPaperCandidateEligibilityError(
            "exact child ordinal 1 through 5 required"
        )
    for name in (
        "d1r7_source_head",
        "d1r7_source_tree",
        "d1r8_source_head",
        "d1r8_source_tree",
    ):
        if getattr(observation, name) != globals()[name.upper()]:
            raise ResearchStrategyPaperCandidateEligibilityError(
                "fixed child source required"
            )
    if check_identity:
        expected = _identity(
            RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_V2_NAMESPACE,
            RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_V2_IDENTITY_VERSION,
            _observation_material(observation),
        )
        if _uuid(observation.observation_id, "observation_id") != expected:
            raise ResearchStrategyPaperCandidateEligibilityError(
                "observation_id is inconsistent"
            )


def _validate_eligibility(
    eligibility: ResearchStrategyPaperCandidateEligibilityV2,
    *,
    check_identity: bool = True,
) -> None:
    _validate_authority(eligibility)
    _fixed_strategy(
        eligibility, schema=RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_V2_SCHEMA
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
            RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_V2_NAMESPACE,
            RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_V2_IDENTITY_VERSION,
            _eligibility_material(eligibility),
        )
        if _uuid(eligibility.eligibility_id, "eligibility_id") != expected:
            raise ResearchStrategyPaperCandidateEligibilityError(
                "eligibility_id is inconsistent"
            )


def _observation_material(value) -> tuple[str, ...]:
    _validate_observation(value, check_identity=False)
    return (
        str(value.schema),
        str(value.compatibility_proof_id),
        str(value.production_target_id),
        value.target_session_date.isoformat(),
        str(value.production_contract_id),
        str(value.paper_authority_kind),
        str(value.paper_authority_schema),
        str(value.paper_authority_source_head),
        str(value.paper_authority_source_tree),
        str(value.authority_parent_id),
        str(value.authority_parent_journal_sha256),
        str(value.authority_child_ordinal),
        str(value.authority_child_id),
        str(value.authority_child_journal_sha256),
        str(value.d1r7_source_head),
        str(value.d1r7_source_tree),
        str(value.d1r7_evidence_sha256),
        str(value.d1r8_source_head),
        str(value.d1r8_source_tree),
        str(value.d1r8_evidence_sha256),
        str(value.terminal_classification),
        str(value.production_strategy_schema),
        str(value.strategy_id),
        str(value.strategy_version),
        str(value.symbol),
        str(value.strategy_config.short_window),
        str(value.strategy_config.long_window),
        canonical_decimal(value.strategy_config.desired_quantity),
        str(value.production_source_head),
        str(value.production_source_tree),
    )


def _eligibility_material(value) -> tuple[str, ...]:
    _validate_eligibility(value, check_identity=False)
    return (
        str(value.schema),
        str(value.compatibility_proof_id),
        str(value.production_target_id),
        str(value.policy_id),
        str(value.paper_authority_kind),
        str(value.paper_authority_schema),
        str(value.paper_authority_source_head),
        str(value.paper_authority_source_tree),
        str(value.authority_parent_id),
        str(value.authority_parent_journal_sha256),
        str(len(value.observation_ids)),
        *(str(item) for item in value.observation_ids),
        value.first_session_date.isoformat(),
        value.last_session_date.isoformat(),
        str(value.paper_executed_count),
        str(value.production_strategy_schema),
        str(value.strategy_id),
        str(value.strategy_version),
        str(value.symbol),
        str(value.strategy_config.short_window),
        str(value.strategy_config.long_window),
        canonical_decimal(value.strategy_config.desired_quantity),
        str(value.research_strategy_source_head),
        str(value.research_strategy_source_tree),
        str(value.production_source_head),
        str(value.production_source_tree),
        str(value.eligibility_source_head),
        str(value.eligibility_source_tree),
    )


@dataclass(frozen=True, slots=True)
class ResearchStrategyPaperSessionObservationV2:
    """Inert canonical V2 evidence; external verification is separate."""

    schema: str = field(
        default=RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_V2_SCHEMA, init=False
    )
    observation_id: UUID = field(init=False)
    compatibility_proof_id: UUID
    production_target_id: UUID
    target_session_date: date
    production_contract_id: UUID
    paper_authority_kind: str
    paper_authority_schema: str
    paper_authority_source_head: str
    paper_authority_source_tree: str
    authority_parent_id: UUID
    authority_parent_journal_sha256: str
    authority_child_ordinal: int
    authority_child_id: UUID
    authority_child_journal_sha256: str
    d1r7_source_head: str
    d1r7_source_tree: str
    d1r7_evidence_sha256: str
    d1r8_source_head: str
    d1r8_source_tree: str
    d1r8_evidence_sha256: str
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
                RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_V2_NAMESPACE,
                RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_V2_IDENTITY_VERSION,
                _observation_material(self),
            ),
        )

    def to_json(self) -> str:
        """Serialize exact canonical self-consistency, without external authority."""
        _validate_observation(self)
        return _to_json(self)

    @classmethod
    def from_json(cls, value: str) -> ResearchStrategyPaperSessionObservationV2:
        """Parse only canonical self-consistency; never verify supplied evidence."""
        if cls is not ResearchStrategyPaperSessionObservationV2:
            raise ResearchStrategyPaperCandidateEligibilityError(
                "exact artifact class required"
            )
        return _from_json(cls, value, _OBSERVATION_FIELDS, "observation_id")


@dataclass(frozen=True, slots=True)
class ResearchStrategyPaperCandidateEligibilityV2:
    """Inert canonical V2 evidence; external verification is separate."""

    schema: str = field(
        default=RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_V2_SCHEMA, init=False
    )
    eligibility_id: UUID = field(init=False)
    compatibility_proof_id: UUID
    production_target_id: UUID
    policy_id: UUID
    paper_authority_kind: str
    paper_authority_schema: str
    paper_authority_source_head: str
    paper_authority_source_tree: str
    authority_parent_id: UUID
    authority_parent_journal_sha256: str
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
                RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_V2_NAMESPACE,
                RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_V2_IDENTITY_VERSION,
                _eligibility_material(self),
            ),
        )

    def to_json(self) -> str:
        """Serialize exact canonical self-consistency, without external authority."""
        _validate_eligibility(self)
        return _to_json(self)

    @classmethod
    def from_json(cls, value: str) -> ResearchStrategyPaperCandidateEligibilityV2:
        """Parse only canonical self-consistency; never verify supplied evidence."""
        if cls is not ResearchStrategyPaperCandidateEligibilityV2:
            raise ResearchStrategyPaperCandidateEligibilityError(
                "exact artifact class required"
            )
        return _from_json(cls, value, _ELIGIBILITY_FIELDS, "eligibility_id")


def validate_research_strategy_paper_eligibility_window_v2(
    observations: tuple[ResearchStrategyPaperSessionObservationV2, ...],
    policy: ResearchStrategyPaperSoakPolicy | None = None,
) -> int:
    """Validate a complete five-session window and return its execution count.

    This is a pure intrinsic check.  It does not verify the external evidence
    referenced by an observation and does not construct an eligibility artifact.
    """
    selected_policy = ResearchStrategyPaperSoakPolicy() if policy is None else policy
    if type(selected_policy) is not ResearchStrategyPaperSoakPolicy:
        raise ResearchStrategyPaperCandidateEligibilityError(
            "exact unchanged v1 policy required"
        )
    ResearchStrategyPaperSoakPolicy.from_json(selected_policy.to_json())
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
    if tuple(item.authority_child_ordinal for item in observations) != (1, 2, 3, 4, 5):
        raise ResearchStrategyPaperCandidateEligibilityError(
            "exact ordered child ordinals required"
        )
    if len({item.observation_id for item in observations}) != 5:
        raise ResearchStrategyPaperCandidateEligibilityError(
            "five unique observations required"
        )
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
