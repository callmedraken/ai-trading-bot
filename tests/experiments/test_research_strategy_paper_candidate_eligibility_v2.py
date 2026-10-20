"""V2 exact schema, identity, canonical representation and intrinsic policy."""

import json
from dataclasses import fields, replace
from datetime import date
from decimal import Decimal, localcontext
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest

from trading_bot.domain import Symbol
from trading_bot.experiments import (
    research_strategy_paper_candidate_eligibility_v2 as subject,
)
from trading_bot.experiments.research_strategy_paper_candidate_eligibility import (
    ResearchStrategyPaperCandidateEligibilityError as Error,
)
from trading_bot.experiments.research_strategy_paper_candidate_eligibility import (
    ResearchStrategyPaperSoakPolicy,
)
from trading_bot.strategies.moving_average import MovingAverageCrossoverConfig

OBS_FIELDS = """schema observation_id compatibility_proof_id production_target_id
target_session_date production_contract_id paper_authority_kind paper_authority_schema
paper_authority_source_head paper_authority_source_tree authority_parent_id
authority_parent_journal_sha256 authority_child_ordinal authority_child_id
authority_child_journal_sha256 d1r7_source_head d1r7_source_tree d1r7_evidence_sha256
d1r8_source_head d1r8_source_tree d1r8_evidence_sha256 terminal_classification
production_strategy_schema strategy_id strategy_version symbol strategy_config
production_source_head production_source_tree""".split()
ELIG_FIELDS = """schema eligibility_id compatibility_proof_id production_target_id
policy_id paper_authority_kind paper_authority_schema paper_authority_source_head
paper_authority_source_tree authority_parent_id authority_parent_journal_sha256
observation_ids first_session_date last_session_date paper_executed_count
production_strategy_schema strategy_id strategy_version symbol strategy_config
research_strategy_source_head research_strategy_source_tree production_source_head
production_source_tree eligibility_source_head eligibility_source_tree""".split()
DATES = tuple(date(2026, 10, day) for day in (20, 21, 22, 23, 26))


def uid(name):
    return uuid5(NAMESPACE_URL, name)


def observation(ordinal=1):
    return subject.ResearchStrategyPaperSessionObservationV2(
        compatibility_proof_id=uid("proof"),
        production_target_id=uid("target"),
        target_session_date=DATES[ordinal - 1],
        production_contract_id=uid(f"contract-{ordinal}"),
        paper_authority_kind="ARCH134_F1",
        paper_authority_schema="arch134-f1-five-session-soak/v1",
        paper_authority_source_head="b59ad3b44540a55a30f612d5c4e3e38e26a95b02",
        paper_authority_source_tree="e8a94e3512d7950f2fbc9c4d102a58b63e03244f",
        authority_parent_id=uid("parent"),
        authority_parent_journal_sha256="1" * 64,
        authority_child_ordinal=ordinal,
        authority_child_id=uid(f"child-{ordinal}"),
        authority_child_journal_sha256=str(ordinal) * 64,
        d1r7_source_head="30322c49b13b80af8d20acee4bdb1efd83d86260",
        d1r7_source_tree="b7dc7f054fca50c3ab784505f264b6f716a45dff",
        d1r7_evidence_sha256="2" * 64,
        d1r8_source_head="aa07c5ba94e0b55cbd8f920464fcc5bd9efcabd2",
        d1r8_source_tree="fcbfc348dab307fb9c456ce9e17aad0e53d7bd4f",
        d1r8_evidence_sha256="3" * 64,
        terminal_classification="PAPER_EXECUTED" if ordinal == 1 else "NO_SIGNAL",
        symbol=Symbol("SPY"),
        strategy_config=MovingAverageCrossoverConfig(2, 3, Decimal("1.00")),
        production_source_head="a" * 40,
        production_source_tree="b" * 40,
    )


def eligibility():
    observations = tuple(observation(n) for n in range(1, 6))
    reference = observations[0]
    names = (
        "compatibility_proof_id production_target_id paper_authority_kind "
        "paper_authority_schema paper_authority_source_head "
        "paper_authority_source_tree authority_parent_id "
        "authority_parent_journal_sha256 symbol strategy_config "
        "production_source_head production_source_tree"
    ).split()
    return subject.ResearchStrategyPaperCandidateEligibilityV2(
        **{name: getattr(reference, name) for name in names},
        policy_id=ResearchStrategyPaperSoakPolicy().policy_id,
        observation_ids=tuple(item.observation_id for item in observations),
        first_session_date=DATES[0],
        last_session_date=DATES[-1],
        paper_executed_count=1,
        research_strategy_source_head="a" * 40,
        research_strategy_source_tree="b" * 40,
        eligibility_source_head="c" * 40,
        eligibility_source_tree="d" * 40,
    )


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@pytest.mark.parametrize(
    "factory,names,namespace,version",
    [
        (
            observation,
            OBS_FIELDS,
            "8769f313-42dc-512f-91b2-e0299f6c9200",
            "research-strategy-paper-session-observation-identity/v2",
        ),
        (
            eligibility,
            ELIG_FIELDS,
            "98822733-db5a-5382-b362-a441861d56e1",
            "research-strategy-paper-candidate-eligibility-identity/v2",
        ),
    ],
)
def test_exact_fields_namespaces_and_independent_ordered_identity(
    factory, names, namespace, version
):
    artifact = factory()
    assert [item.name for item in fields(artifact)] == names
    raw = json.loads(artifact.to_json())
    material = [version]
    for name in names:
        if name in ("observation_id", "eligibility_id"):
            continue
        value = raw[name]
        if name == "strategy_config":
            material.extend(
                [
                    str(value["short_window"]),
                    str(value["long_window"]),
                    value["desired_quantity"],
                ]
            )
        elif name == "observation_ids":
            material.extend([str(len(value)), *value])
        else:
            material.append(str(value))
    expected = uuid5(
        UUID(namespace), "".join(f"{len(v.encode('utf-8'))}:{v}" for v in material)
    )
    assert expected == getattr(artifact, names[1])
    schema = raw["schema"]
    assert uuid5(
        NAMESPACE_URL, "https://github.com/callmedraken/ai-trading-bot/" + schema
    ) == UUID(namespace)
    assert artifact.to_json() == canonical(raw)
    assert type(artifact).from_json(artifact.to_json()) == artifact
    assert "eligible" not in raw


@pytest.mark.parametrize("factory", [observation, eligibility])
@pytest.mark.parametrize(
    "mutation",
    [
        "unknown",
        "missing",
        "duplicate",
        "space",
        "newline",
        "reorder",
        "id",
        "float",
        "bool",
        "quantity",
        "config",
        "uuid",
        "date",
        "hash",
        "source",
        "authority",
    ],
)
def test_noncanonical_transport_rejected(factory, mutation):
    artifact = factory()
    raw = json.loads(artifact.to_json())
    text = None
    if mutation == "unknown":
        raw["extra"] = 1
    elif mutation == "missing":
        del raw["schema"]
    elif mutation == "duplicate":
        text = artifact.to_json().replace("{", '{"schema":"wrong",', 1)
    elif mutation == "space":
        text = " " + artifact.to_json()
    elif mutation == "newline":
        text = artifact.to_json() + "\n"
    elif mutation == "reorder":
        text = json.dumps(dict(reversed(list(raw.items()))), separators=(",", ":"))
    elif mutation == "id":
        raw[list(raw.keys())[0]] = str(uid("wrong"))
    elif mutation == "float":
        raw["strategy_config"]["short_window"] = 2.0
    elif mutation == "bool":
        raw["strategy_config"]["short_window"] = True
    elif mutation == "quantity":
        raw["strategy_config"]["desired_quantity"] = "1.00"
    elif mutation == "config":
        raw["strategy_config"]["other"] = 1
    elif mutation == "uuid":
        raw["compatibility_proof_id"] = raw["compatibility_proof_id"].upper()
    elif mutation == "date":
        raw[
            "target_session_date" if factory == observation else "first_session_date"
        ] = "20261020"
    elif mutation == "hash":
        raw["authority_parent_journal_sha256"] = "G" * 64
    elif mutation == "source":
        raw["production_source_head"] = "A" * 40
    elif mutation == "authority":
        raw["paper_authority_kind"] = "D1R9"
    with pytest.raises(ValueError):
        type(artifact).from_json(canonical(raw) if text is None else text)


@pytest.mark.parametrize(
    "name,value",
    [
        ("authority_child_ordinal", True),
        ("authority_child_ordinal", 0),
        ("authority_child_ordinal", 6),
        ("paper_authority_source_head", "a" * 40),
        ("d1r7_source_head", "a" * 40),
        ("d1r8_source_tree", "a" * 40),
        ("terminal_classification", "SESSION_MISSED"),
        ("terminal_classification", "BLOCKED"),
        ("terminal_classification", "INDETERMINATE"),
    ],
)
def test_observation_intrinsic_rejections(name, value):
    with pytest.raises(Error):
        replace(observation(), **{name: value})


def test_window_policy_and_provenance_stability():
    window = tuple(observation(n) for n in range(1, 6))
    assert subject.validate_research_strategy_paper_eligibility_window_v2(window) == 1
    assert eligibility().policy_id == ResearchStrategyPaperSoakPolicy().policy_id
    for name, value in [
        ("authority_parent_id", uid("other")),
        ("authority_parent_journal_sha256", "0" * 64),
        ("production_source_head", "e" * 40),
        ("symbol", Symbol("QQQ")),
        ("authority_child_ordinal", 4),
        ("terminal_classification", "RISK_REJECTED"),
    ]:
        bad = window[:2] + (replace(window[2], **{name: value}),) + window[3:]
        with pytest.raises(Error):
            subject.validate_research_strategy_paper_eligibility_window_v2(bad)
    for bad in (
        window[:4],
        window[::-1],
        tuple([window[0]] * 5),
        tuple(replace(i, terminal_classification="NO_SIGNAL") for i in window),
        window[:4] + (replace(window[-1], target_session_date=date(2026, 10, 27)),),
    ):
        with pytest.raises(Error):
            subject.validate_research_strategy_paper_eligibility_window_v2(bad)


@pytest.mark.parametrize(
    "name,value",
    [
        ("paper_executed_count", True),
        ("paper_executed_count", 0),
        ("paper_executed_count", 6),
        ("policy_id", uid("other")),
        ("observation_ids", (uid("same"),) * 5),
        ("last_session_date", date(2026, 10, 27)),
    ],
)
def test_eligibility_is_positive_only(name, value):
    with pytest.raises(Error):
        replace(eligibility(), **{name: value})


def test_decimal_identity_is_ambient_context_independent():
    before = observation()
    with localcontext() as context:
        context.prec = 1
        after = replace(
            before,
            strategy_config=MovingAverageCrossoverConfig(
                2, 3, Decimal("1.000000000000")
            ),
        )
    assert before.observation_id == after.observation_id
    assert before.to_json() == after.to_json()
    assert subject._frame("é") == "2:é"
