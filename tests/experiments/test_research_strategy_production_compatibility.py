"""Architecture 143 transport, full-chain replay, and zero-effect boundaries."""

import ast
import inspect
import json
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from hashlib import sha256
from uuid import UUID, uuid5

import pytest

import trading_bot.experiments as exports
import trading_bot.experiments.research_strategy_production_compatibility as subject
import trading_bot.experiments.research_strategy_walk_forward as walk_forward
from scripts import checkpoint_runner
from trading_bot.domain import Bar, Symbol
from trading_bot.experiments.research_strategy_definition import (
    ResearchStrategyDefinition,
    ResearchStrategyEvaluationPolicy,
)
from trading_bot.experiments.research_strategy_production_compatibility import (
    ProductionStrategySemanticTarget as Target,
)
from trading_bot.experiments.research_strategy_production_compatibility import (
    ResearchStrategyProductionCompatibilityError as Error,
)
from trading_bot.experiments.research_strategy_production_compatibility import (
    ResearchStrategyProductionCompatibilityProof as Proof,
)
from trading_bot.experiments.research_strategy_production_compatibility import (
    build_research_strategy_production_compatibility_proof as build,
)
from trading_bot.experiments.research_strategy_production_compatibility import (
    verify_research_strategy_production_compatibility_proof as verify,
)
from trading_bot.market_data.models import HistoricalDataRequest, HistoricalDataResult
from trading_bot.strategies.moving_average import MovingAverageCrossoverConfig as Config

HEAD, TREE, QHEAD, QTREE, PHEAD, PTREE = (char * 40 for char in "abcdef")
PROVENANCE = dict(
    qualification_source_head=QHEAD,
    qualification_source_tree=QTREE,
    proof_source_head=PHEAD,
    proof_source_tree=PTREE,
)
TARGET_FIELDS = (
    "schema",
    "target_id",
    "production_source_head",
    "production_source_tree",
    "production_strategy_schema",
    "strategy_id",
    "strategy_version",
    "symbol",
    "strategy_config",
)
PROOF_FIELDS = (
    "schema",
    "proof_id",
    "definition_id",
    "evaluation_policy_id",
    "walk_forward_evidence_id",
    "qualification_id",
    "walk_forward_passed_id",
    "production_target_id",
    "research_strategy_source_head",
    "research_strategy_source_tree",
    "production_source_head",
    "production_source_tree",
    "production_strategy_schema",
    "strategy_id",
    "strategy_version",
    "symbol",
    "strategy_config",
    "proof_source_head",
    "proof_source_tree",
)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


@pytest.fixture
def chain():
    symbol = Symbol("SPY")
    definition = ResearchStrategyDefinition(
        HEAD, TREE, symbol, Config(2, 3, Decimal("1"))
    )
    policy = ResearchStrategyEvaluationPolicy(
        starting_cash=Decimal("10000"),
        fixed_commission=Decimal("0"),
        slippage_basis_points=Decimal("0"),
        trading_enabled=True,
        allow_missing_sessions=False,
        max_position_percent=Decimal("0.2"),
        max_total_exposure_percent=Decimal("0.8"),
        max_order_notional=None,
        max_new_position_percent=None,
        minimum_cash_reserve_percent=Decimal("0.1"),
        allow_fractional_shares=True,
        fractional_increment=Decimal("0.001"),
        allow_buying=True,
        allow_selling=True,
        estimated_commission=Decimal("0"),
    )
    timestamps = tuple(
        datetime(2024, 1, day, 20, tzinfo=UTC)
        for day in (2, 3, 4, 5, 8, 9, 10, 11, 12, 16, 17)
    )
    bars = tuple(
        Bar(
            symbol,
            time,
            Decimal(close),
            Decimal(close),
            Decimal(close),
            Decimal(close),
            1000,
        )
        for time, close in zip(
            timestamps,
            (100, 101, 99, 102, 103, 101, 104, 105, 103, 106, 107),
            strict=True,
        )
    )
    data = HistoricalDataResult(
        HistoricalDataRequest(
            symbol, datetime(2024, 1, 2, tzinfo=UTC), datetime(2024, 1, 19, tzinfo=UTC)
        ),
        bars,
        "test-memory",
    )
    folds = tuple(
        walk_forward.ResearchStrategyWalkForwardFold(
            datetime(2024, 1, start, 5, tzinfo=UTC),
            datetime(2024, 1, mid, 5, tzinfo=UTC),
            datetime(2024, 1, mid, 5, tzinfo=UTC),
            datetime(2024, 1, end, 5, tzinfo=UTC),
        )
        for start, mid, end in ((2, 5, 9), (9, 12, 17))
    )
    completed = walk_forward.run_research_strategy_walk_forward(
        definition,
        policy,
        data,
        folds,
        evaluation_source_head=QHEAD,
        evaluation_source_tree=QTREE,
    )
    qualification_policy = walk_forward.ResearchStrategyWalkForwardQualificationPolicy(
        minimum_fold_count=2,
        minimum_fold_return=Decimal("-1"),
        minimum_median_return=Decimal("-1"),
        maximum_fold_drawdown_percentage=Decimal("100"),
        require_equal_test_window_bar_count=True,
    )
    qualification = walk_forward.qualify_research_strategy_walk_forward(
        completed,
        qualification_policy,
        qualification_source_head=QHEAD,
        qualification_source_tree=QTREE,
    )
    passed = walk_forward.build_walk_forward_passed_research_strategy(
        qualification,
        completed,
        qualification_policy,
        qualification_source_head=QHEAD,
        qualification_source_tree=QTREE,
    )
    target = Target(HEAD, TREE, symbol, definition.strategy_config)
    return completed, qualification, qualification_policy, passed, target


@pytest.fixture
def proof(chain):
    return build(*chain, **PROVENANCE)


def _expected_identity(value):
    raw = json.loads(value.to_json())
    names = list(PROOF_FIELDS if type(value) is Proof else TARGET_FIELDS)
    names.remove("proof_id" if type(value) is Proof else "target_id")
    material = []
    for name in names:
        if name == "strategy_config":
            material.extend(
                str(raw[name][part])
                for part in ("short_window", "long_window", "desired_quantity")
            )
        else:
            material.append(str(raw[name]))
    version, namespace = (
        (
            "research-strategy-production-compatibility-proof-identity/v1",
            "f9f82ac4-219d-512d-bfe9-a1c07c9427a1",
        )
        if type(value) is Proof
        else (
            "production-strategy-semantic-target-identity/v1",
            "16be4a92-15d8-5db1-9f92-17a3dbd195f3",
        )
    )
    return uuid5(
        UUID(namespace),
        "".join(f"{len(part.encode('utf-8'))}:{part}" for part in (version, *material)),
    )


def test_exact_fields_identities_roundtrip_and_exports(chain, proof):
    assert tuple(item.name for item in fields(Target)) == TARGET_FIELDS
    assert tuple(item.name for item in fields(Proof)) == PROOF_FIELDS
    for value, identity in ((chain[-1], "target_id"), (proof, "proof_id")):
        assert getattr(value, identity) == _expected_identity(value)
        assert type(value).from_json(value.to_json()) == value
        assert value.to_json() == _json(json.loads(value.to_json()))
        assert getattr(replace(value), identity) == getattr(value, identity)
        with pytest.raises(FrozenInstanceError):
            value.symbol = Symbol("QQQ")
    for name in subject.__all__:
        assert getattr(exports, name) is getattr(subject, name)


@pytest.mark.parametrize("kind", ["target", "proof"])
@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "extra",
        "duplicate",
        "nested_duplicate",
        "nested_missing",
        "nested_extra",
        "whitespace",
    ],
)
def test_exact_json_transport(chain, proof, kind, mutation):
    value = chain[-1] if kind == "target" else proof
    raw = json.loads(value.to_json())
    if mutation == "missing":
        raw.pop("symbol")
    elif mutation == "extra":
        raw["verified"] = True
    elif mutation == "nested_missing":
        raw["strategy_config"].pop("desired_quantity")
    elif mutation == "nested_extra":
        raw["strategy_config"]["status"] = "PASS"
    text = _json(raw)
    if mutation == "duplicate":
        text = '{"symbol":"SPY",' + text[1:]
    elif mutation == "nested_duplicate":
        text = text.replace('"short_window":2', '"short_window":2,"short_window":2')
    elif mutation == "whitespace":
        text += "\n"
    with pytest.raises(Error):
        type(value).from_json(text)


@pytest.mark.parametrize("kind", ["target", "proof"])
@pytest.mark.parametrize(
    "bad",
    [
        "NaN",
        "sNaN",
        "Infinity",
        "-Infinity",
        "1.0",
        "1e0",
        "01",
        "-0",
        "",
        1.0,
        True,
        None,
    ],
)
def test_decimal_transport_rejects_noncanonical(chain, proof, kind, bad):
    value = chain[-1] if kind == "target" else proof
    raw = json.loads(value.to_json())
    raw["strategy_config"]["desired_quantity"] = bad
    with pytest.raises(Error):
        type(value).from_json(_json(raw))


@pytest.mark.parametrize("kind", ["target", "proof"])
@pytest.mark.parametrize("name", ["short_window", "long_window"])
@pytest.mark.parametrize("bad", [True, False, 2.0, "2", 0, -1])
def test_integer_transport_rejects_bool_float_invalid(chain, proof, kind, name, bad):
    value = chain[-1] if kind == "target" else proof
    raw = json.loads(value.to_json())
    raw["strategy_config"][name] = bad
    with pytest.raises(Error):
        type(value).from_json(_json(raw))


@pytest.mark.parametrize("kind", ["target", "proof"])
@pytest.mark.parametrize(
    "bad", ["bad", "A" * 40, "a" * 39, "a" * 41, "a" * 40 + "\n", 1, True, "F:/source"]
)
def test_all_source_fields_are_exact(chain, proof, kind, bad):
    value = chain[-1] if kind == "target" else proof
    for name in (
        item.name for item in fields(value) if item.name.endswith(("_head", "_tree"))
    ):
        raw = json.loads(value.to_json())
        raw[name] = bad
        with pytest.raises(Error):
            type(value).from_json(_json(raw))


@pytest.mark.parametrize(
    "bad",
    [
        "bad",
        "F9F82AC4-219D-512D-BFE9-A1C07C9427A1",
        "{f9f82ac4-219d-512d-bfe9-a1c07c9427a1}",
        "f9f82ac4219d512dbfe9a1c07c9427a1",
        "00000000-0000-4000-8000-000000000000",
        "00000000-0000-1000-8000-000000000000",
        1,
        True,
    ],
)
def test_uuid_transport_rejects_malformed_noncanonical_random_clock(chain, proof, bad):
    for value in (chain[-1], proof):
        raw = json.loads(value.to_json())
        for name, original in tuple(raw.items()):
            if name.endswith("_id") and name != "strategy_id":
                raw[name] = bad
                with pytest.raises(Error):
                    type(value).from_json(_json(raw))
                raw[name] = original


@pytest.mark.parametrize("bad", [None, b"pickle", 1, True, "NaN", "{}", "[]"])
def test_non_artifact_transport_rejected(bad):
    for cls in (Target, Proof):
        with pytest.raises(Error):
            cls.from_json(bad)


def test_decimal_context_independence(chain, proof):
    quantity = Decimal("12345678901234567890.1234567890123456789000")
    target = replace(chain[-1], strategy_config=Config(2, 3, quantity))
    projected = replace(proof, strategy_config=target.strategy_config)
    expected = target.to_json(), projected.to_json()
    with localcontext() as context:
        context.prec = 2
        context.Emax = 2
        context.Emin = -2
        for signal in context.traps:
            context.traps[signal] = True
        assert (target.to_json(), projected.to_json()) == expected
        assert Target.from_json(expected[0]) == target
        assert Proof.from_json(expected[1]) == projected


def test_builder_and_verifier_replay_all_folds_before_projection(chain, monkeypatch):
    events = []
    external = subject.verify_walk_forward_passed_research_strategy
    replay = walk_forward.verify_research_strategy_backtest
    constructor = Proof.__post_init__

    def external_spy(*args, **kwargs):
        events.append("external")
        return external(*args, **kwargs)

    def replay_spy(value, *args, **kwargs):
        events.append(value.evidence.backtest_run_id)
        return replay(value, *args, **kwargs)

    def constructor_spy(self):
        assert events[0] == "external"
        expected_runs = {
            getattr(fold, role).evidence.backtest_run_id
            for fold in chain[0].folds
            for role in ("training", "test")
        }
        assert expected_runs <= set(events)
        events.append("proof")
        constructor(self)

    monkeypatch.setattr(
        subject, "verify_walk_forward_passed_research_strategy", external_spy
    )
    monkeypatch.setattr(walk_forward, "verify_research_strategy_backtest", replay_spy)
    monkeypatch.setattr(Proof, "__post_init__", constructor_spy)
    value = build(*chain, **PROVENANCE)
    events.clear()
    verify(value, *chain, **PROVENANCE)
    assert events[-1] == "proof"


@pytest.mark.parametrize(
    "name,value",
    [
        ("symbol", Symbol("QQQ")),
        ("strategy_config", Config(1, 3, Decimal("1"))),
        ("strategy_config", Config(2, 4, Decimal("1"))),
        ("strategy_config", Config(2, 3, Decimal("2"))),
        ("production_source_head", "1" * 40),
        ("production_source_tree", "2" * 40),
        ("production_strategy_schema", "different/v1"),
        ("strategy_id", "other"),
        ("strategy_version", "2.0.0"),
    ],
)
def test_every_semantic_mismatch_rejects_before_projection(
    chain, proof, monkeypatch, name, value
):
    target = deepcopy(chain[-1])
    if name in {"production_strategy_schema", "strategy_id", "strategy_version"}:
        object.__setattr__(target, name, value)
    else:
        target = replace(target, **{name: value})
    inputs = (*chain[:-1], target)
    monkeypatch.setattr(
        Proof,
        "__post_init__",
        lambda self: pytest.fail("constructed proof on mismatch"),
    )
    with pytest.raises(ValueError):
        build(*inputs, **PROVENANCE)
    with pytest.raises(ValueError):
        verify(proof, *inputs, **PROVENANCE)


@pytest.mark.parametrize("position", range(4))
def test_wrong_independent_chain_member_rejected(chain, proof, position):
    inputs = list(chain)
    if position == 0:
        inputs[0] = replace(inputs[0])
        object.__setattr__(
            inputs[0],
            "evaluation_policy",
            replace(inputs[0].evaluation_policy, starting_cash=Decimal("9999")),
        )
    elif position == 1:
        inputs[1] = replace(inputs[1], qualification_source_head="1" * 40)
    elif position == 2:
        inputs[2] = replace(inputs[2], minimum_fold_count=3)
    else:
        inputs[3] = replace(inputs[3], definition_id=uuid5(UUID(int=0), "wrong"))
        inputs[3] = type(inputs[3]).from_json(inputs[3].to_json())
    with pytest.raises(ValueError):
        build(*inputs, **PROVENANCE)
    with pytest.raises(ValueError):
        verify(proof, *inputs, **PROVENANCE)


@pytest.mark.parametrize("name", PROVENANCE)
def test_independent_provenance_reconciles(chain, proof, name):
    provenance = {**PROVENANCE, name: "1" * 40}
    if name.startswith("qualification"):
        with pytest.raises(ValueError):
            build(*chain, **provenance)
    else:
        assert build(*chain, **provenance).proof_id != proof.proof_id
    with pytest.raises(ValueError):
        verify(proof, *chain, **provenance)


@pytest.mark.parametrize("role", ["training", "test"])
def test_tampered_fold_rejected_even_with_parsed_forged_material(chain, proof, role):
    inputs = list(chain)
    inputs[0] = replace(inputs[0])
    fold = replace(inputs[0].folds[0])
    backtest = replace(getattr(fold, role))
    object.__setattr__(
        backtest,
        "evidence",
        replace(backtest.evidence, bar_count=backtest.evidence.bar_count + 1),
    )
    object.__setattr__(fold, role, backtest)
    object.__setattr__(inputs[0], "folds", (fold, *inputs[0].folds[1:]))
    parsed = Proof.from_json(proof.to_json())
    with pytest.raises(ValueError):
        build(*inputs, **PROVENANCE)
    with pytest.raises(ValueError):
        verify(parsed, *inputs, **PROVENANCE)


def test_forged_self_consistent_proof_cannot_verify(chain, proof):
    forged = replace(proof, definition_id=uuid5(UUID(int=0), "forged"))
    parsed = Proof.from_json(forged.to_json())
    with pytest.raises(Error, match="reconcile"):
        verify(parsed, *chain, **PROVENANCE)


def test_parsers_do_no_research_or_grant_authority(chain, proof, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("parser replayed research")

    monkeypatch.setattr(
        subject, "verify_walk_forward_passed_research_strategy", forbidden
    )
    monkeypatch.setattr(
        walk_forward, "verify_research_strategy_walk_forward", forbidden
    )
    monkeypatch.setattr(walk_forward, "run_research_strategy_walk_forward", forbidden)
    assert Target.from_json(chain[-1].to_json()) == chain[-1]
    assert Proof.from_json(proof.to_json()) == proof
    for cls in (Target, Proof):
        assert not {
            "verified",
            "compatible",
            "status",
            "stage",
            "target_session_date",
            "blockers",
        } & {item.name for item in fields(cls)}


def test_every_bound_proof_input_changes_identity(proof):
    for item in fields(proof):
        if not item.init:
            continue
        value = getattr(proof, item.name)
        if type(value) is UUID:
            changed = uuid5(UUID(int=0), item.name)
        elif item.name.endswith(("_head", "_tree")):
            changed = "1" * 40
        elif item.name == "symbol":
            changed = Symbol("QQQ")
        else:
            for config in (
                Config(1, 3, Decimal("1")),
                Config(2, 4, Decimal("1")),
                Config(2, 3, Decimal("2")),
            ):
                assert replace(proof, strategy_config=config).proof_id != proof.proof_id
            continue
        assert replace(proof, **{item.name: changed}).proof_id != proof.proof_id


def test_capability_allowlist_and_no_141_bridge():
    source = inspect.getsource(subject)
    tree = ast.parse(source)
    imports = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imports == {
        "__future__",
        "json",
        "re",
        "dataclasses",
        "decimal",
        "uuid",
        "trading_bot.domain",
        "trading_bot.experiments.research_strategy_walk_forward",
        "trading_bot.strategies.moving_average",
        "trading_bot.strategies.production",
    }
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "trading_bot.strategies.production"
        ):
            assert {alias.name for alias in node.names} == {
                "MOVING_AVERAGE_STRATEGY_ID",
                "MOVING_AVERAGE_STRATEGY_VERSION",
                "PRODUCTION_STRATEGY_SCHEMA",
            }
        if isinstance(node, ast.Call):
            name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else getattr(node.func, "attr", "")
            )
            assert name not in {
                "open",
                "exec",
                "eval",
                "__import__",
                "hash",
                "id",
                "repr",
                "float",
                "uuid4",
                "now",
                "today",
                "utcnow",
                "connect",
                "request",
                "send",
                "promote",
                "advance",
                "set_stage",
            }
    for forbidden in (
        "ProductionStrategyContract",
        "build_production_strategy",
        "PAPER_CANDIDATE",
        "AWAITING_HUMAN_PROMOTION",
        "ResearchCandidateProductionCompatibilityAssessment",
        "HistoricalExperimentVariant",
        "variant_name",
    ):
        assert forbidden not in source


def test_arch143_inventory_overlay_exact_predecessor_and_blobs():
    pins = checkpoint_runner.ARCH143_CURRENT_INVENTORY_TEST_PIN_OVERRIDES
    predecessor = checkpoint_runner.ARCH142B_CURRENT_INVENTORY_TEST_PIN_OVERRIDES
    assert set(pins) == set(predecessor)
    assert all(pins[path] != predecessor[path] for path in pins)
    assert (
        sha256(json.dumps(pins, sort_keys=True).encode()).hexdigest()
        == checkpoint_runner.ARCH143_CURRENT_INVENTORY_TEST_PINS_SHA256
    )
    from pathlib import Path

    root = Path(checkpoint_runner.__file__).resolve().parents[1]
    for path, pin in pins.items():
        assert (
            checkpoint_runner._arch143_current_inventory_test_pin(
                path, predecessor[path]
            )
            == pin
        )
        expected_current = checkpoint_runner._arch132_r3i_current_inventory_test_pin(
            path, pin
        )
        expected_current = checkpoint_runner._arch144_current_inventory_test_pin(
            path, expected_current
        )
        assert (
            checkpoint_runner._arch144_current_inventory_test_pin(
                path,
                checkpoint_runner._arch132_r3i_current_inventory_test_pin(path, pin),
            )
            == expected_current
        )
        assert checkpoint_runner._git_blob_sha1(root / path) == expected_current
    assert (
        checkpoint_runner._arch143_current_inventory_test_pin(
            "tests/unrelated.py", "a" * 40
        )
        == "a" * 40
    )
    assert (
        checkpoint_runner.ARCH142_CURRENT_INVENTORY_TEST_PINS_SHA256
        == "515392eb1213323ab2bc0a62a4bd848a21b9fe60b6afcdaeac14b44523c43366"
    )
    assert (
        checkpoint_runner.ARCH142B_CURRENT_INVENTORY_TEST_PINS_SHA256
        == "8a7ddd8184e1beadecdce88207ed75b02dce75be870892957b9ae5ae5d7e33c6"
    )
    for name in ("ARCH142", "ARCH142B"):
        material = json.dumps(
            getattr(checkpoint_runner, name + "_CURRENT_INVENTORY_TEST_PIN_OVERRIDES"),
            sort_keys=True,
        ).encode()
        assert sha256(material).hexdigest() == getattr(
            checkpoint_runner, name + "_CURRENT_INVENTORY_TEST_PINS_SHA256"
        )


@pytest.mark.parametrize(
    "mutation", ["missing", "extra", "source", "drift", "predecessor"]
)
def test_arch143_overlay_fails_closed(monkeypatch, mutation):
    pins = dict(checkpoint_runner.ARCH143_CURRENT_INVENTORY_TEST_PIN_OVERRIDES)
    path = next(iter(pins))
    before = checkpoint_runner.ARCH142B_CURRENT_INVENTORY_TEST_PIN_OVERRIDES[path]
    if mutation == "missing":
        pins.pop(path)
    elif mutation == "extra":
        pins["tests/unreviewed.py"] = "a" * 40
    elif mutation == "source":
        pins["src/trading_bot/strategies/production.py"] = "a" * 40
    elif mutation == "drift":
        pins[path] = "0" * 40
    else:
        before = "0" * 40
    monkeypatch.setattr(
        checkpoint_runner, "ARCH143_CURRENT_INVENTORY_TEST_PIN_OVERRIDES", pins
    )
    with pytest.raises(ValueError):
        checkpoint_runner._arch143_current_inventory_test_pin(path, before)


@pytest.mark.parametrize(
    "name,digest",
    [
        [
            "trading_bot.experiments.research_strategy_definition",
            "9fe041a38dfcc3c10e2b40d5183e67b134cf7991affb04251270b331c05b8c9a",
        ],
        [
            "trading_bot.experiments.research_strategy_backtest",
            "8a396ed571cd234fea961b8ba3401b6d3ef84a4e7cfb93f04e7afc18367d87a6",
        ],
        [
            "trading_bot.experiments.research_strategy_walk_forward",
            "e7bbfb09762ecd91dc40ded68bd43fea35d50fc058737527837013f569c834c8",
        ],
    ],
)
def test_arch142_source_schema_namespace_and_behavior_remain_frozen(name, digest):
    import sys

    assert sha256(inspect.getsource(sys.modules[name]).encode()).hexdigest() == digest


@pytest.mark.parametrize(
    "name,bad",
    [
        ("symbol", "SPY"),
        ("strategy_config", {"short_window": 2}),
        ("schema", "other/v1"),
        ("target_id", UUID(int=0)),
    ],
)
def test_target_defensive_validation(chain, name, bad):
    target = replace(chain[-1])
    object.__setattr__(target, name, bad)
    with pytest.raises(ValueError):
        target.to_json()
    with pytest.raises(ValueError):
        build(*chain[:-1], target, **PROVENANCE)


@pytest.mark.parametrize(
    "name",
    [
        "schema",
        "production_strategy_schema",
        "strategy_id",
        "strategy_version",
        "symbol",
    ],
)
def test_fixed_or_noncanonical_transport(chain, proof, name):
    for value in (chain[-1], proof):
        raw = json.loads(value.to_json())
        raw[name] = "spy" if name == "symbol" else "other"
        with pytest.raises(Error):
            type(value).from_json(_json(raw))


def test_no_caller_flags_or_target_only_proof(chain, proof):
    for name in ("compatible", "verified", "status", "stage", "blockers"):
        with pytest.raises(TypeError):
            replace(chain[-1], **{name: True})
        with pytest.raises(TypeError):
            replace(proof, **{name: True})
    parsed = Target.from_json(chain[-1].to_json())
    with pytest.raises(TypeError):
        build(parsed)
    with pytest.raises(TypeError):
        verify(Proof.from_json(proof.to_json()))


@pytest.mark.parametrize("kind", ["symbol", "config"])
def test_target_requires_exact_value_object_types(chain, kind):
    class DerivedSymbol(Symbol):
        pass

    class DerivedConfig(Config):
        pass

    changes = (
        {"symbol": DerivedSymbol("SPY")}
        if kind == "symbol"
        else {"strategy_config": DerivedConfig(2, 3, Decimal("1"))}
    )
    with pytest.raises(Error):
        replace(chain[-1], **changes)


@pytest.mark.parametrize("quantity", [1.0, True, Decimal("NaN"), Decimal("Infinity")])
def test_mutated_config_decimal_is_rejected(chain, quantity):
    config = replace(chain[-1].strategy_config)
    object.__setattr__(config, "desired_quantity", quantity)
    with pytest.raises(ValueError):
        replace(chain[-1], strategy_config=config)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_non_json_constants_rejected(chain, proof, constant):
    for value in (chain[-1], proof):
        text = value.to_json().replace(
            '"desired_quantity":"1"', '"desired_quantity":' + constant
        )
        with pytest.raises(Error):
            type(value).from_json(text)


def test_external_failure_prevents_projection(chain, monkeypatch):
    def reject(*args, **kwargs):
        raise ValueError("external chain rejected")

    monkeypatch.setattr(subject, "verify_walk_forward_passed_research_strategy", reject)
    monkeypatch.setattr(
        Proof,
        "__post_init__",
        lambda self: pytest.fail("projected before external acceptance"),
    )
    with pytest.raises(ValueError, match="external chain rejected"):
        build(*chain, **PROVENANCE)


def test_proof_structural_failure_precedes_research(chain, proof, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("replayed malformed proof")

    monkeypatch.setattr(
        subject, "verify_walk_forward_passed_research_strategy", forbidden
    )
    malformed = replace(proof)
    object.__setattr__(malformed, "proof_id", UUID(int=0))
    with pytest.raises(Error):
        verify(malformed, *chain, **PROVENANCE)


def test_zero_effect_accounting(chain, monkeypatch):
    import socket
    import sqlite3

    import trading_bot.strategies.production as production

    names = (
        "PRODUCTION_SQLITE_READS",
        "PRODUCTION_SQLITE_WRITES",
        "CREDENTIAL_READS",
        "PROVIDER_CALLS",
        "ROBINHOOD_READS",
        "BROKER_CALLS",
        "SCHEDULER_CALLS",
        "ACL_MUTATIONS",
        "PAPER_MUTATIONS",
        "STRATEGY_PROMOTIONS",
        "PRODUCTION_CONTRACTS_CREATED",
        "PAPER_CANDIDATES_CREATED",
        "D1_OPERATIONS",
        "D1R9_OPERATIONS",
        "D2_SUPERVISOR_EXECUTIONS",
    )
    counters = dict.fromkeys(names, 0)

    def trap(name):
        def forbidden(*args, **kwargs):
            counters[name] += 1
            pytest.fail(f"forbidden effect: {name}")

        return forbidden

    monkeypatch.setattr(sqlite3, "connect", trap("PRODUCTION_SQLITE_READS"))
    monkeypatch.setattr(socket, "socket", trap("PROVIDER_CALLS"))
    monkeypatch.setattr(
        production.ProductionStrategyContract,
        "__post_init__",
        trap("PRODUCTION_CONTRACTS_CREATED"),
    )
    monkeypatch.setattr(
        production, "build_production_strategy", trap("STRATEGY_PROMOTIONS")
    )
    value = build(*chain, **PROVENANCE)
    verify(Proof.from_json(value.to_json()), *chain, **PROVENANCE)
    assert counters == dict.fromkeys(names, 0)
