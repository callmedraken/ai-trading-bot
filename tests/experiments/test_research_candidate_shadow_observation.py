"""Synthetic, caller-supplied evidence only; no live observations."""

import ast
import inspect
import json
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, date, datetime, timedelta, timezone
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from tests.experiments.test_research_candidate_shadow_binding import binding as binding
from tests.experiments.test_research_candidate_shadow_binding import chain as chain
from tests.experiments.test_research_candidate_shadow_binding import (
    completed as completed,
)
from tests.experiments.test_research_candidate_shadow_binding import deepcopy

from trading_bot.experiments import research_candidate_shadow_observation as m

Error = m.ResearchCandidateShadowObservationError
Observation = m.ResearchCandidateShadowObservation
Batch = m.ResearchCandidateShadowObservationBatch
DEFAULT_BINDING_ID = UUID(int=1)
SOURCE = dict(observation_source_head="a" * 40, observation_source_tree="b" * 40)


def observation(
    binding_id=DEFAULT_BINDING_ID, ordinal=0, day=date(2026, 1, 2), **changes
):
    values = dict(
        binding_id=binding_id,
        session_date=day,
        observed_at_utc=datetime(2026, 1, 2, 15, tzinfo=UTC)
        + timedelta(minutes=ordinal),
        observation_ordinal=ordinal,
        input_fingerprint=UUID(int=2),
        decision_fingerprint=UUID(int=3),
        **dict.fromkeys(m.SHADOW_ZERO_EFFECT_FIELDS, 0),
    )
    values.update(changes)
    return Observation(**values)


def batch(binding_id=DEFAULT_BINDING_ID, **changes):
    values = dict(
        binding_id=binding_id, observations=(observation(binding_id),), **SOURCE
    )
    values.update(changes)
    return Batch(**values)


def test_deterministic_roundtrip_frozen_and_exact_identity():
    item = observation()
    evidence = batch()
    for value, model, namespace in (
        (item, Observation, m.OBSERVATION_NAMESPACE),
        (evidence, Batch, m.BATCH_NAMESPACE),
    ):
        assert model.from_json(value.to_json()) == value
        assert value.to_json() == json.dumps(
            json.loads(value.to_json()), sort_keys=True, separators=(",", ":")
        )
        assert not hasattr(value, "__dict__")
        with pytest.raises(FrozenInstanceError):
            value.binding_id = UUID(int=8)
        assert namespace == uuid5(NAMESPACE_URL, value.schema)
    values = (
        item.schema,
        str(item.binding_id),
        "2026-01-02",
        "2026-01-02T15:00:00.000000Z",
        "0",
        str(item.input_fingerprint),
        str(item.decision_fingerprint),
        *("0" for _ in m.SHADOW_ZERO_EFFECT_FIELDS),
    )
    material = ("research-candidate-shadow-observation-identity/v1", *values)
    assert item.observation_id == uuid5(
        m.OBSERVATION_NAMESPACE,
        "".join(f"{len(v.encode('utf-8'))}:{v}" for v in material),
    )
    values = (
        "research-candidate-shadow-observation-batch-identity/v1",
        evidence.schema,
        str(evidence.binding_id),
        SOURCE["observation_source_head"],
        SOURCE["observation_source_tree"],
        "1",
        str(item.observation_id),
        *("0" for _ in m.SHADOW_ZERO_EFFECT_FIELDS),
    )
    assert evidence.observation_batch_id == uuid5(
        m.BATCH_NAMESPACE, "".join(f"{len(v.encode('utf-8'))}:{v}" for v in values)
    )


@pytest.mark.parametrize(
    "name,value",
    [
        ("binding_id", UUID(int=4)),
        ("session_date", date(2026, 1, 3)),
        ("observed_at_utc", datetime(2026, 1, 2, 16, tzinfo=UTC)),
        ("observation_ordinal", 1),
        ("input_fingerprint", UUID(int=8)),
        ("decision_fingerprint", UUID(int=9)),
    ],
)
def test_every_variable_observation_semantic_field_changes_identity(name, value):
    assert (
        replace(observation(), **{name: value}).observation_id
        != observation().observation_id
    )


@pytest.mark.parametrize("name", m.SHADOW_ZERO_EFFECT_FIELDS)
@pytest.mark.parametrize("value", [True, False, 1, -1, 0.0, "0", None])
def test_every_effect_counter_is_structurally_zero(name, value):
    with pytest.raises(Error):
        observation(**{name: value})
    evidence = batch()
    object.__setattr__(evidence, name, value)
    with pytest.raises(Error):
        evidence.to_json()


@pytest.mark.parametrize(
    "name,value",
    [
        ("binding_id", "00000000-0000-0000-0000-000000000001"),
        ("session_date", "2026-01-02"),
        ("session_date", datetime(2026, 1, 2)),
        ("observation_ordinal", True),
        ("observation_ordinal", -1),
        ("observation_ordinal", 1_000_001),
        ("observation_ordinal", 1.0),
        ("observed_at_utc", datetime(2026, 1, 2)),
        ("observed_at_utc", datetime(2026, 1, 2, tzinfo=timezone(timedelta(hours=1)))),
        ("observed_at_utc", datetime(2026, 1, 2, tzinfo=UTC, fold=1)),
        ("input_fingerprint", "hash"),
        ("decision_fingerprint", None),
    ],
)
def test_exact_observation_types(name, value):
    with pytest.raises(Error):
        observation(**{name: value})


@pytest.mark.parametrize(
    "mutation",
    ["empty", "list", "duplicate", "ordinal", "time", "session", "binding", "subclass"],
)
def test_batch_rejects_noncanonical_order_and_shape(mutation):
    first, second = observation(), observation(ordinal=1)
    observations = (first, second)
    if mutation == "empty":
        observations = ()
    elif mutation == "list":
        observations = [first]
    elif mutation == "duplicate":
        observations = (first, first)
    elif mutation == "ordinal":
        observations = (second, first)
    elif mutation == "time":
        observations = (
            first,
            replace(
                second, observed_at_utc=first.observed_at_utc - timedelta(seconds=1)
            ),
        )
    elif mutation == "session":
        observations = (replace(first, session_date=date(2026, 1, 3)), second)
    elif mutation == "binding":
        observations = (replace(first, binding_id=UUID(int=8)),)
    else:

        class Subclass(Observation):
            pass

        observations = (
            Subclass(
                **{f.name: getattr(first, f.name) for f in fields(first) if f.init}
            ),
        )
    with pytest.raises(Error):
        batch(observations=observations)


def test_batch_source_count_order_identity_and_caller_input_retention():
    first = observation()
    items = (first, observation(ordinal=1))
    assert batch(observations=items).observations is items
    assert batch(observations=items).observation_count == 2
    assert (
        batch(observations=items).observation_batch_id != batch().observation_batch_id
    )
    for name in SOURCE:
        assert (
            replace(batch(), **{name: "c" * 40}).observation_batch_id
            != batch().observation_batch_id
        )
        for bad in (True, "A" * 40, "a" * 39, "g" * 40, None):
            with pytest.raises(Error):
                replace(batch(), **{name: bad})
    assert batch(UUID(int=9)).observation_batch_id != batch().observation_batch_id
    assert (
        batch(
            observations=(replace(first, decision_fingerprint=UUID(int=8)),)
        ).observation_batch_id
        != batch().observation_batch_id
    )
    # Supplied session dates are evidence, including weekends, not exchange claims.
    assert observation(day=date(2026, 1, 3)).session_date.weekday() == 5


@pytest.mark.parametrize("model,make", [(Observation, observation), (Batch, batch)])
@pytest.mark.parametrize(
    "mutation",
    [
        "space",
        "newline",
        "duplicate",
        "missing",
        "extra",
        "id",
        "uuid",
        "source",
        "bool",
        "constant",
        "schema",
    ],
)
def test_strict_canonical_parser(model, make, mutation):
    value = make().to_json()
    raw = json.loads(value)
    if mutation == "space":
        value = json.dumps(raw)
    elif mutation == "newline":
        value += "\n"
    elif mutation == "duplicate":
        value = '{"binding_id":"' + str(UUID(int=1)) + '",' + value[1:]
    else:
        if mutation == "missing":
            raw.pop("binding_id")
        elif mutation == "extra":
            raw["verified"] = True
        elif mutation == "id":
            raw[
                "observation_id" if model is Observation else "observation_batch_id"
            ] = str(UUID(int=8))
        elif mutation == "uuid":
            raw["binding_id"] = UUID(int=1).hex
        elif mutation == "source":
            raw[
                "observed_at_utc" if model is Observation else "observation_source_head"
            ] = "bad"
        elif mutation == "bool":
            raw["credential_reads"] = False
        elif mutation == "constant":
            raw["credential_reads"] = float("nan")
        elif mutation == "schema":
            raw["schema"] = "wrong/v1"
        value = json.dumps(raw, sort_keys=True, separators=(",", ":"))
    with pytest.raises(Error):
        model.from_json(value)


@pytest.mark.parametrize(
    "text",
    [
        "2026-01-02T15:00:00Z",
        "2026-01-02T15:00:00.000000+00:00",
        "2026-01-02T16:00:00.000000+01:00",
        "20260102T150000Z",
    ],
)
def test_timestamp_representation_is_unique(text):
    raw = json.loads(observation().to_json())
    raw["observed_at_utc"] = text
    with pytest.raises(Error):
        Observation.from_json(json.dumps(raw, sort_keys=True, separators=(",", ":")))


def test_nested_duplicate_forgery_and_bounds():
    value = batch().to_json()
    with pytest.raises(Error):
        Batch.from_json(
            value.replace(
                '"input_fingerprint":', '"credential_reads":0,"input_fingerprint":'
            )
        )
    raw = json.loads(value)
    raw["observations"][0]["observation_ordinal"] = True
    with pytest.raises(Error):
        Batch.from_json(json.dumps(raw, sort_keys=True, separators=(",", ":")))
    with pytest.raises(Error):
        batch(observations=(observation(),) * (m.MAX_SHADOW_OBSERVATIONS + 1))
    item = observation(ordinal=m.MAX_SHADOW_OBSERVATION_ORDINAL)
    assert item.observation_ordinal == m.MAX_SHADOW_OBSERVATION_ORDINAL


def test_complete_external_chain_builder_and_independent_verifier(
    binding, chain, monkeypatch
):
    before = deepcopy(chain)
    items = (observation(binding.binding_id),)
    result = m.build_research_candidate_shadow_observation_batch(
        binding, **chain, observations=items, **SOURCE
    )
    m.verify_research_candidate_shadow_observation_batch(
        result, binding, **chain, observations=items, **SOURCE
    )
    assert result == batch(binding.binding_id)
    assert chain == before
    # Parser self-consistency does not establish independently supplied source.
    with pytest.raises(Error):
        m.verify_research_candidate_shadow_observation_batch(
            result,
            binding,
            **chain,
            observations=items,
            **{**SOURCE, "observation_source_head": "c" * 40},
        )
    calls = []
    verify = m.verify_research_candidate_shadow_variant_binding
    resolve = m.resolve_bound_research_candidate_variant

    def checking(*args, **kwargs):
        calls.append("verify")
        return verify(*args, **kwargs)

    def resolving(*args, **kwargs):
        calls.append("resolve")
        return resolve(*args, **kwargs)

    monkeypatch.setattr(m, "verify_research_candidate_shadow_variant_binding", checking)
    monkeypatch.setattr(m, "resolve_bound_research_candidate_variant", resolving)
    m.build_research_candidate_shadow_observation_batch(
        binding, **chain, observations=items, **SOURCE
    )
    assert calls == ["verify", "resolve"]


@pytest.mark.parametrize(
    "name",
    [
        "qualification_source_head",
        "qualification_source_tree",
        "binding_source_head",
        "binding_source_tree",
    ],
)
def test_external_source_drift_rejected_and_evidence_unchanged(binding, chain, name):
    before = deepcopy(chain)
    with pytest.raises(ValueError):
        m.build_research_candidate_shadow_observation_batch(
            binding,
            **{**chain, name: "f" * 40},
            observations=(observation(binding.binding_id),),
            **SOURCE,
        )
    assert chain == before


def test_wrong_binding_and_malformed_predecessor_rejected(binding, chain):
    before = deepcopy(chain)
    with pytest.raises(Error):
        m.build_research_candidate_shadow_observation_batch(
            binding, **chain, observations=(observation(),), **SOURCE
        )
    broken = deepcopy(chain)
    object.__setattr__(broken["predecessor"], "rank", True)
    with pytest.raises(ValueError):
        m.build_research_candidate_shadow_observation_batch(
            binding, **broken, observations=(observation(binding.binding_id),), **SOURCE
        )
    assert chain == before


def test_no_acquisition_execution_or_private_import_capability():
    tree = ast.parse(inspect.getsource(m))
    imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    }
    assert imports == {
        "__future__",
        "json",
        "re",
        "dataclasses",
        "datetime",
        "uuid",
        "trading_bot.experiments.historical",
        "trading_bot.experiments.report",
        "trading_bot.experiments.research_candidate",
        "trading_bot.experiments.research_candidate_shadow_binding",
        "trading_bot.experiments.research_candidate_walk_forward",
        "trading_bot.experiments.walk_forward",
    }
    assert all(
        not a.name.startswith("_")
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom)
        for a in n.names
    )
    forbidden = {
        "open",
        "Path",
        "eval",
        "exec",
        "__import__",
        "now",
        "utcnow",
        "today",
        "sleep",
        "uuid4",
        "hash",
        "id",
        "run",
        "evaluate",
        "simulate",
        "Popen",
        "connect",
        "request",
        "execute",
        "place_order",
        "review_equity_order",
        "promote",
        "advance",
        "set_stage",
    }
    calls = {
        n.func.id if isinstance(n.func, ast.Name) else n.func.attr
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))
    }
    assert not calls & forbidden
    assert (
        not {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} & forbidden
    )
