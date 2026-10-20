"""Architecture-144 pure paper-eligibility artifact coverage."""

import ast
import json
from dataclasses import FrozenInstanceError, fields, replace
from datetime import date
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid5

import pytest

import trading_bot.experiments as exports
import trading_bot.experiments.research_strategy_paper_candidate_eligibility as subject
from trading_bot.domain import Symbol
from trading_bot.experiments.research_strategy_paper_candidate_eligibility import (
    OBSERVATION_TERMINAL_CLASSIFICATIONS,
    PAPER_TERMINAL_CLASSIFICATIONS,
    QUALIFYING_TERMINAL_CLASSIFICATIONS,
    REQUIRE_CONSECUTIVE_PUBLISHED_REGULAR_SESSIONS,
    REQUIRED_PAPER_EXECUTED_COUNT,
    REQUIRED_SESSION_COUNT,
    RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_IDENTITY_VERSION,
    RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_NAMESPACE,
    RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_SCHEMA,
    RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_IDENTITY_VERSION,
    RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_NAMESPACE,
    RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_SCHEMA,
    RESEARCH_STRATEGY_PAPER_SOAK_POLICY_IDENTITY_VERSION,
    RESEARCH_STRATEGY_PAPER_SOAK_POLICY_NAMESPACE,
    RESEARCH_STRATEGY_PAPER_SOAK_POLICY_SCHEMA,
    ResearchStrategyPaperCandidateEligibility,
    ResearchStrategyPaperSessionObservation,
    ResearchStrategyPaperSoakPolicy,
    canonical_decimal,
    validate_research_strategy_paper_eligibility_window,
)
from trading_bot.experiments.research_strategy_paper_candidate_eligibility import (
    ResearchStrategyPaperCandidateEligibilityError as Error,
)
from trading_bot.strategies.moving_average import MovingAverageCrossoverConfig as Config
from trading_bot.strategies.production import (
    MOVING_AVERAGE_STRATEGY_ID,
    MOVING_AVERAGE_STRATEGY_VERSION,
    PRODUCTION_STRATEGY_SCHEMA,
)

HEAD, TREE, PRODUCTION_HEAD, PRODUCTION_TREE = (char * 40 for char in "abcd")
JOURNAL_A = "1" * 64
JOURNAL_B = "2" * 64
_DATES = (
    date(2024, 1, 2),
    date(2024, 1, 3),
    date(2024, 1, 4),
    date(2024, 1, 5),
    date(2024, 1, 8),
)


def _uuid(name: str) -> UUID:
    return uuid5(UUID(int=0), name)


def _observation(
    session_date: date,
    *,
    classification: str = "NO_SIGNAL",
    ordinal: int = 0,
    quantity: Decimal = Decimal("1.00"),
) -> ResearchStrategyPaperSessionObservation:
    return ResearchStrategyPaperSessionObservation(
        compatibility_proof_id=_uuid("compatibility-proof"),
        production_target_id=_uuid("production-target"),
        target_session_date=session_date,
        production_contract_id=_uuid(f"production-contract-{session_date}"),
        d1r9_source_head=HEAD,
        d1r9_source_tree=TREE,
        d1r8_source_head=PRODUCTION_HEAD,
        d1r8_source_tree=PRODUCTION_TREE,
        d1r9_journal_sha256=f"{ordinal + 1:064x}",
        d1r8_journal_sha256=f"{ordinal + 11:064x}",
        terminal_classification=classification,
        symbol=Symbol("SPY"),
        strategy_config=Config(2, 3, quantity),
        production_source_head=HEAD,
        production_source_tree=TREE,
    )


def _window(
    *, executed: bool = True
) -> tuple[ResearchStrategyPaperSessionObservation, ...]:
    return tuple(
        _observation(
            session_date,
            classification=(
                "PAPER_EXECUTED"
                if executed and ordinal == len(_DATES) - 1
                else "NO_SIGNAL"
            ),
            ordinal=ordinal,
        )
        for ordinal, session_date in enumerate(_DATES)
    )


def _eligibility(
    observations: tuple[ResearchStrategyPaperSessionObservation, ...],
    *,
    paper_executed_count: int = 1,
) -> ResearchStrategyPaperCandidateEligibility:
    return ResearchStrategyPaperCandidateEligibility(
        compatibility_proof_id=observations[0].compatibility_proof_id,
        production_target_id=observations[0].production_target_id,
        policy_id=ResearchStrategyPaperSoakPolicy().policy_id,
        observation_ids=tuple(item.observation_id for item in observations),
        first_session_date=observations[0].target_session_date,
        last_session_date=observations[-1].target_session_date,
        paper_executed_count=paper_executed_count,
        symbol=observations[0].symbol,
        strategy_config=observations[0].strategy_config,
        research_strategy_source_head=HEAD,
        research_strategy_source_tree=TREE,
        production_source_head=PRODUCTION_HEAD,
        production_source_tree=PRODUCTION_TREE,
        eligibility_source_head="e" * 40,
        eligibility_source_tree="f" * 40,
    )


def test_exact_fields_fixed_values_and_package_exports() -> None:
    assert tuple(
        item.name for item in fields(ResearchStrategyPaperSessionObservation)
    ) == (
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
    )
    assert tuple(item.name for item in fields(ResearchStrategyPaperSoakPolicy)) == (
        "schema",
        "policy_id",
        "required_session_count",
        "required_paper_executed_count",
        "require_consecutive_published_regular_sessions",
        "qualifying_terminal_classifications",
    )
    assert tuple(
        item.name for item in fields(ResearchStrategyPaperCandidateEligibility)
    ) == (
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
    )
    policy = ResearchStrategyPaperSoakPolicy()
    assert (
        policy.required_session_count,
        policy.required_paper_executed_count,
        policy.require_consecutive_published_regular_sessions,
        policy.qualifying_terminal_classifications,
    ) == (5, 1, True, ("NO_SIGNAL", "PAPER_EXECUTED"))
    for name in subject.__all__:
        assert getattr(exports, name) is getattr(subject, name)


def test_identity_material_is_exact_and_semantic_fields_are_significant() -> None:
    observation = _observation(_DATES[0])
    material = (
        RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_IDENTITY_VERSION,
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
        str(observation.strategy_config.short_window),
        str(observation.strategy_config.long_window),
        "1",
        observation.production_source_head,
        observation.production_source_tree,
    )
    expected = uuid5(
        RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_NAMESPACE,
        "".join(f"{len(item.encode('utf-8'))}:{item}" for item in material),
    )
    assert observation.observation_id == expected
    assert (
        replace(observation, terminal_classification="PAPER_EXECUTED").observation_id
        != observation.observation_id
    )
    assert (
        replace(observation, strategy_config=Config(3, 4, Decimal("1"))).observation_id
        != observation.observation_id
    )
    assert (
        replace(observation, production_source_head="e" * 40).observation_id
        != observation.observation_id
    )


def test_uuid5_framing_uses_utf8_byte_lengths() -> None:
    expected = uuid5(UUID(int=0), "2:é3:abc")
    assert subject._identity(UUID(int=0), "é", ("abc",)) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (Decimal("0"), "0"),
        (Decimal("-0"), "0"),
        (Decimal("1.2300"), "1.23"),
        (Decimal("1000.000"), "1000"),
    ],
)
def test_canonical_decimal(value: Decimal, expected: str) -> None:
    assert canonical_decimal(value) == expected


@pytest.mark.parametrize(
    "value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")]
)
def test_nonfinite_decimal_is_rejected(value: Decimal) -> None:
    with pytest.raises(Error):
        canonical_decimal(value)


def test_policy_identity_order_and_immutability() -> None:
    policy = ResearchStrategyPaperSoakPolicy()
    material = (
        RESEARCH_STRATEGY_PAPER_SOAK_POLICY_IDENTITY_VERSION,
        policy.schema,
        "5",
        "1",
        "true",
        "2",
        "NO_SIGNAL",
        "PAPER_EXECUTED",
    )
    expected = uuid5(
        RESEARCH_STRATEGY_PAPER_SOAK_POLICY_NAMESPACE,
        "".join(f"{len(item.encode('utf-8'))}:{item}" for item in material),
    )
    assert policy.policy_id == expected
    assert (
        policy.qualifying_terminal_classifications
        == QUALIFYING_TERMINAL_CLASSIFICATIONS
    )
    assert ResearchStrategyPaperSoakPolicy.from_json(policy.to_json()) == policy
    with pytest.raises(FrozenInstanceError):
        policy.required_session_count = 6  # type: ignore[misc]
    object.__setattr__(policy, "required_session_count", 6)
    with pytest.raises(Error):
        policy.to_json()


def test_canonical_json_roundtrip_and_no_eligibility_boolean() -> None:
    observations = _window()
    observation = observations[0]
    eligibility = _eligibility(observations)
    assert (
        ResearchStrategyPaperSessionObservation.from_json(observation.to_json())
        == observation
    )
    assert ResearchStrategyPaperSoakPolicy.from_json(
        ResearchStrategyPaperSoakPolicy().to_json()
    )
    assert (
        ResearchStrategyPaperCandidateEligibility.from_json(eligibility.to_json())
        == eligibility
    )
    assert "eligibility" not in {item.name for item in fields(eligibility)}
    assert not hasattr(observation, "externally_verified")


@pytest.mark.parametrize("artifact", ["observation", "eligibility", "policy"])
@pytest.mark.parametrize("mutation", ["missing", "unknown", "duplicate", "whitespace"])
def test_strict_json_field_and_byte_rejection(artifact: str, mutation: str) -> None:
    observations = _window()
    value = {
        "observation": observations[0].to_json(),
        "eligibility": _eligibility(observations).to_json(),
        "policy": ResearchStrategyPaperSoakPolicy().to_json(),
    }[artifact]
    parser = {
        "observation": ResearchStrategyPaperSessionObservation.from_json,
        "eligibility": ResearchStrategyPaperCandidateEligibility.from_json,
        "policy": ResearchStrategyPaperSoakPolicy.from_json,
    }[artifact]
    raw = json.loads(value)
    if mutation == "missing":
        raw.pop(next(iter(raw)))
        mutated = json.dumps(raw, sort_keys=True, separators=(",", ":"))
    elif mutation == "unknown":
        raw["unknown"] = 1
        mutated = json.dumps(raw, sort_keys=True, separators=(",", ":"))
    elif mutation == "whitespace":
        mutated = " " + value
    else:
        if artifact == "observation":
            mutated = value.replace(
                '"strategy_config":{"desired_quantity":"1","long_window":3,"short_window":2}',
                '"strategy_config":{"short_window":2,"short_window":2,"long_window":3,"desired_quantity":"1"}',
            )
        elif artifact == "policy":
            mutated = value.replace(
                '"schema":"research-strategy-paper-soak-policy/v1"',
                '"schema":"research-strategy-paper-soak-policy/v1","schema":"research-strategy-paper-soak-policy/v1"',
            )
        else:
            mutated = value.replace('"symbol":"SPY"', '"symbol":"SPY","symbol":"SPY"')
    with pytest.raises(Error):
        parser(mutated)


@pytest.mark.parametrize(
    "path,value",
    [
        (("strategy_config", "desired_quantity"), 1.0),
        (("strategy_config", "short_window"), True),
        (("target_session_date",), "20240102"),
        (("observation_id",), str(_uuid("wrong"))),
    ],
)
def test_noncanonical_scalar_rejection(path: tuple[str, ...], value: object) -> None:
    raw = json.loads(_observation(_DATES[0]).to_json())
    cursor = raw
    for name in path[:-1]:
        cursor = cursor[name]
    cursor[path[-1]] = value
    with pytest.raises(Error):
        ResearchStrategyPaperSessionObservation.from_json(
            json.dumps(raw, sort_keys=True, separators=(",", ":"))
        )


def test_eligibility_identity_preserves_observation_order_and_policy_binding() -> None:
    observations = _window()
    eligibility = _eligibility(observations)
    config = eligibility.strategy_config
    material = (
        RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_IDENTITY_VERSION,
        eligibility.schema,
        str(eligibility.compatibility_proof_id),
        str(eligibility.production_target_id),
        str(eligibility.policy_id),
        str(REQUIRED_SESSION_COUNT),
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
        "1",
        eligibility.research_strategy_source_head,
        eligibility.research_strategy_source_tree,
        eligibility.production_source_head,
        eligibility.production_source_tree,
        eligibility.eligibility_source_head,
        eligibility.eligibility_source_tree,
    )
    expected = uuid5(
        RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_NAMESPACE,
        "".join(f"{len(item.encode('utf-8'))}:{item}" for item in material),
    )
    assert eligibility.eligibility_id == expected
    reordered = replace(
        eligibility,
        observation_ids=(
            observations[1].observation_id,
            observations[0].observation_id,
            *(item.observation_id for item in observations[2:]),
        ),
    )
    assert reordered.eligibility_id != eligibility.eligibility_id
    assert eligibility.paper_executed_count == REQUIRED_PAPER_EXECUTED_COUNT
    with pytest.raises(Error):
        _eligibility(observations, paper_executed_count=0)
    object.__setattr__(eligibility, "policy_id", _uuid("different-policy"))
    with pytest.raises(Error):
        eligibility.to_json()


def test_intrinsic_window_validation_accepts_exact_policy_semantics() -> None:
    observations = _window()
    assert validate_research_strategy_paper_eligibility_window(observations) == 1
    assert OBSERVATION_TERMINAL_CLASSIFICATIONS == (
        "NO_SIGNAL",
        "RISK_REJECTED",
        "PAPER_EXECUTED",
    )
    assert PAPER_TERMINAL_CLASSIFICATIONS == OBSERVATION_TERMINAL_CLASSIFICATIONS
    assert REQUIRE_CONSECUTIVE_PUBLISHED_REGULAR_SESSIONS is True


@pytest.mark.parametrize(
    "mutator",
    [
        lambda values: (
            tuple(
                replace(values[0], terminal_classification="RISK_REJECTED") for _ in [0]
            )
            + values[1:]
        ),
        lambda values: (
            tuple(replace(values[-1], terminal_classification="NO_SIGNAL") for _ in [0])
            + values[1:-1]
        ),
        lambda values: (values[0], values[1], values[2], values[4], values[3]),
        lambda values: tuple(
            replace(item, strategy_config=Config(3, 4, Decimal("1")))
            if item is values[-1]
            else item
            for item in values
        ),
    ],
)
def test_intrinsic_window_validation_rejects_nonqualifying_or_inconsistent_windows(
    mutator,
) -> None:
    with pytest.raises(Error):
        validate_research_strategy_paper_eligibility_window(mutator(_window()))
    with pytest.raises(Error):
        validate_research_strategy_paper_eligibility_window(_window(executed=False))


@pytest.mark.parametrize(
    "classification", ["SESSION_MISSED", "BLOCKED", "INDETERMINATE"]
)
def test_incomplete_terminal_classifications_cannot_form_observations(
    classification: str,
) -> None:
    with pytest.raises(Error):
        _observation(_DATES[0], classification=classification)


def test_source_has_no_operational_or_external_evidence_capability() -> None:
    source_path = Path(subject.__file__).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    forbidden = {
        "D1R9",
        "D1R8",
        "ProductionStrategyContract",
        "build_production_strategy",
        "PAPER_CANDIDATE",
        "AWAITING_HUMAN_PROMOTION",
        "sqlite3",
        "subprocess",
        "socket",
        "requests",
        "uuid4",
        "now",
        "utcnow",
        "today",
        "open",
        "read_text",
        "write_text",
        "scheduler",
        "provider",
        "credential",
        "broker",
    }
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attributes = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    strings = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert not forbidden & (names | attributes | strings)
    assert not any(
        isinstance(node, (ast.Import, ast.ImportFrom))
        and any(
            alias.name.split(".")[0]
            in {"pathlib", "os", "sqlite3", "subprocess", "socket", "requests"}
            for alias in node.names
        )
        for node in ast.walk(tree)
    )


def test_schema_constants_are_exact() -> None:
    assert RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_SCHEMA == (
        "research-strategy-paper-session-observation/v1"
    )
    assert (
        RESEARCH_STRATEGY_PAPER_SOAK_POLICY_SCHEMA
        == "research-strategy-paper-soak-policy/v1"
    )
    assert RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_SCHEMA == (
        "research-strategy-paper-candidate-eligibility/v1"
    )
    assert PRODUCTION_STRATEGY_SCHEMA
    assert MOVING_AVERAGE_STRATEGY_ID
    assert MOVING_AVERAGE_STRATEGY_VERSION
    assert sha256(_eligibility(_window()).to_json().encode()).hexdigest()
