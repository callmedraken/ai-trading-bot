from __future__ import annotations

import ast
import json
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

import pytest

from scripts import checkpoint_runner as checkpoint_runner
from scripts import run_test_certification as certification
from trading_bot.domain import Symbol
from trading_bot.strategies import (
    MovingAverageCrossoverConfig,
    MovingAverageCrossoverStrategy,
)
from trading_bot.strategies import production as subject

NAME = "arch134-production-strategy-contract"


@pytest.mark.parametrize(
    "name,digest",
    [
        (
            "ARCH134_PRODUCTION_PAPER_RUNTIME_SOURCE_PINS",
            "8c957aa3d3b5707d644b2d086db08023a01ed35cd3ab3218bb27c19424f03235",
        ),
        (
            "ARCH134_D1R5_SOURCE_PINS",
            "3412b689a3c5b5d6ef4495fb62ce3611869e6e512d1055387b50276d188cd230",
        ),
        (
            "ARCH134_D1R5_TEST_PIN_OVERRIDES",
            "bcdb35cb77572df147ea12a9db54d22da2cbe8933140a6c1a7b448dba8be287b",
        ),
        (
            "ARCH134_HIST2_TEST_PIN_OVERRIDES",
            "1d005a7fa62d7172d58be3a9b61443e548f0c62c92ad8652bc883b8df302d950",
        ),
        (
            "ARCH134_D1R4_SOURCE_PINS",
            "9ed4ef533f4602b76382ce6e6841e790c1304de751684cd9a81cfb41a8f50ab2",
        ),
        (
            "ARCH134_D1R4R_SOURCE_PINS",
            "a6c6af6e231ea41074d2dd8b9fe26e36f9c8e70ef8d764626a22efd7217778c2",
        ),
        (
            "ARCH138_CURRENT_INVENTORY_TEST_PIN_OVERRIDES",
            "8a4021b92a5354cfbdb5394692eb50c14f6a13982b9a50aeb7d259553c7e5988",
        ),
    ],
)
def test_arch138_preserves_frozen_predecessor_pin_material(name, digest) -> None:
    # Exact accepted 7aa54bb predecessor material, independent of live inventory.
    material = json.dumps(getattr(checkpoint_runner, name), sort_keys=True).encode()
    assert sha256(material).hexdigest() == digest


@pytest.mark.parametrize("mutation", ["missing", "executable"])
def test_arch138_successor_test_overlay_fails_closed(monkeypatch, mutation) -> None:
    pins = dict(checkpoint_runner.ARCH138_CURRENT_INVENTORY_TEST_PIN_OVERRIDES)
    if mutation == "missing":
        pins.pop("tests/scripts/certification_runner/test_profiles.py")
    else:
        pins["src/trading_bot/review_paper/armed_session.py"] = "a" * 40
    monkeypatch.setattr(
        checkpoint_runner, "ARCH138_CURRENT_INVENTORY_TEST_PIN_OVERRIDES", pins
    )
    root = Path(checkpoint_runner.__file__).resolve().parents[1]
    for check in (
        checkpoint_runner._arch134_production_paper_runtime_authority_check,
        checkpoint_runner._arch134_authentication_authority_check,
        checkpoint_runner._arch134_d1r5_authority_check,
    ):
        assert check(root)


def test_arch138_successor_preserves_unmodified_d1r5_pins() -> None:
    root = Path(checkpoint_runner.__file__).resolve().parents[1]
    overrides = checkpoint_runner.ARCH138_CURRENT_INVENTORY_TEST_PIN_OVERRIDES
    for relative, pin in checkpoint_runner.ARCH134_D1R5_TEST_PIN_OVERRIDES.items():
        if relative not in overrides:
            expected = checkpoint_runner._arch134_d1r7_test_pin(
                relative, checkpoint_runner._arch134_d1r6_test_pin(relative, pin)
            )
            expected = checkpoint_runner._arch142_current_inventory_test_pin(
                relative, expected
            )
            expected = checkpoint_runner._arch142b_current_inventory_test_pin(
                relative, expected
            )
            expected = checkpoint_runner._arch143_current_inventory_test_pin(
                relative, expected
            )
            expected = checkpoint_runner._arch132_r3i_current_inventory_test_pin(
                relative, expected
            )
            expected = checkpoint_runner._arch144_current_inventory_test_pin(
                relative, expected
            )
            assert checkpoint_runner._git_blob_sha1(root / relative) == expected
    assert checkpoint_runner._arch134_d1r5_authority_check(root) == ()


@pytest.mark.parametrize("mutation", ["missing", "extra", "executable", "drift"])
@pytest.mark.parametrize(
    "check",
    [
        checkpoint_runner._arch134_production_paper_runtime_authority_check,
        checkpoint_runner._arch134_authentication_authority_check,
        checkpoint_runner._arch134_d1r5_authority_check,
    ],
)
def test_arch139a_successor_test_overlay_fails_closed(monkeypatch, mutation, check):
    pins = dict(checkpoint_runner.ARCH139A_CURRENT_INVENTORY_TEST_PIN_OVERRIDES)
    if mutation == "missing":
        pins.pop("tests/scripts/certification_runner/test_profiles.py")
    elif mutation == "extra":
        pins["tests/experiments/test_research_candidate_shadow_binding.py"] = "a" * 40
    elif mutation == "executable":
        pins["src/trading_bot/review_paper/armed_session.py"] = "a" * 40
    else:
        pins["tests/scripts/certification_runner/test_profiles.py"] = "0" * 40
    monkeypatch.setattr(
        checkpoint_runner, "ARCH139A_CURRENT_INVENTORY_TEST_PIN_OVERRIDES", pins
    )
    root = Path(checkpoint_runner.__file__).resolve().parents[1]
    assert check(root)


def test_arch140a18_successor_pins_match_and_preserve_unmodified_d1r5_pins():
    root = Path(checkpoint_runner.__file__).resolve().parents[1]
    predecessor = checkpoint_runner.ARCH140A17_CURRENT_INVENTORY_TEST_PIN_OVERRIDES
    overrides = checkpoint_runner.ARCH140A18_CURRENT_INVENTORY_TEST_PIN_OVERRIDES
    assert set(overrides) == set(predecessor)
    for relative, pin in overrides.items():
        current = checkpoint_runner._arch134_d1r7_test_pin(
            relative,
            checkpoint_runner._canonical_current_inventory_test_pin(relative, pin),
        )
        current = checkpoint_runner._arch142_current_inventory_test_pin(
            relative, current
        )
        current = checkpoint_runner._arch142b_current_inventory_test_pin(
            relative, current
        )
        current = checkpoint_runner._arch143_current_inventory_test_pin(
            relative, current
        )
        current = checkpoint_runner._arch132_r3i_current_inventory_test_pin(
            relative, current
        )
        current = checkpoint_runner._arch144_current_inventory_test_pin(
            relative, current
        )
        assert checkpoint_runner._git_blob_sha1(root / relative) == current
    for relative, pin in checkpoint_runner.ARCH134_D1R5_TEST_PIN_OVERRIDES.items():
        if relative not in predecessor:
            expected = checkpoint_runner._arch134_d1r7_test_pin(
                relative, checkpoint_runner._arch134_d1r6_test_pin(relative, pin)
            )
            expected = checkpoint_runner._arch132_r3i_current_inventory_test_pin(
                relative, expected
            )
            expected = checkpoint_runner._arch144_current_inventory_test_pin(
                relative, expected
            )
            assert checkpoint_runner._git_blob_sha1(root / relative) == expected
    for check in (
        checkpoint_runner._arch134_production_paper_runtime_authority_check,
        checkpoint_runner._arch134_authentication_authority_check,
        checkpoint_runner._arch134_d1r5_authority_check,
    ):
        assert check(root) == ()


def _contract(
    *,
    target_session_date: date = date(2026, 10, 13),
    source_head: str = "a" * 40,
    source_tree: str = "b" * 40,
    symbol: Symbol | None = None,
    config: MovingAverageCrossoverConfig | None = None,
) -> subject.ProductionStrategyContract:
    return subject.ProductionStrategyContract(
        target_session_date,
        source_head,
        source_tree,
        symbol if symbol is not None else Symbol("SPY"),
        config
        if config is not None
        else MovingAverageCrossoverConfig(5, 20, Decimal("1.000")),
    )


def test_contract_is_canonical_session_scoped_and_round_trips() -> None:
    contract = _contract()
    payload = contract.to_json()
    raw = json.loads(payload)

    assert raw == {
        "schema": "production-strategy-contract/v1",
        "contract_id": str(contract.contract_id),
        "target_session_date": "2026-10-13",
        "source_head": "a" * 40,
        "source_tree": "b" * 40,
        "strategy_id": "MovingAverageCrossoverStrategy",
        "strategy_version": "1.0.0",
        "symbol": "SPY",
        "strategy_config": {
            "short_window": 5,
            "long_window": 20,
            "desired_quantity": "1",
        },
    }
    assert subject.ProductionStrategyContract.from_json(payload) == contract
    assert subject.ProductionStrategyContract.from_json(payload).to_json() == payload


@pytest.mark.parametrize(
    "change",
    [
        {"target_session_date": date(2026, 10, 14)},
        {"source_head": "c" * 40},
        {"source_tree": "d" * 40},
        {"symbol": Symbol("QQQ")},
        {"config": MovingAverageCrossoverConfig(6, 20, Decimal("1"))},
        {"config": MovingAverageCrossoverConfig(5, 21, Decimal("1"))},
        {"config": MovingAverageCrossoverConfig(5, 20, Decimal("2"))},
    ],
)
def test_contract_id_is_stable_and_binds_every_semantic_field(change) -> None:
    first = _contract()
    assert _contract().contract_id == first.contract_id
    assert _contract(**change).contract_id != first.contract_id


@pytest.mark.parametrize("name", ["source_head", "source_tree"])
@pytest.mark.parametrize(
    "value",
    [
        "A" * 40,
        "a" * 39,
        "a" * 41,
        "g" * 40,
        7,
        None,
    ],
)
def test_source_identity_is_exact_lowercase_sha(name, value) -> None:
    kwargs = {name: value}
    with pytest.raises(ValueError):
        _contract(**kwargs)


def test_target_session_date_is_exact_date_not_datetime_or_text() -> None:
    with pytest.raises(TypeError):
        _contract(target_session_date=datetime(2026, 10, 13))
    with pytest.raises(TypeError):
        _contract(target_session_date="2026-10-13")


def test_symbol_and_config_are_exact_existing_domain_types() -> None:
    with pytest.raises(TypeError):
        _contract(symbol="SPY")
    with pytest.raises(TypeError):
        subject.ProductionStrategyContract(
            date(2026, 10, 13),
            "a" * 40,
            "b" * 40,
            Symbol("SPY"),
            object(),
        )


def test_build_strategy_reuses_exact_existing_pure_strategy_and_config() -> None:
    contract = _contract()
    strategy = subject.build_production_strategy(contract)
    assert type(strategy) is MovingAverageCrossoverStrategy
    assert strategy.config is contract.strategy_config
    with pytest.raises(TypeError):
        subject.build_production_strategy(object())


@pytest.mark.parametrize(
    "mutate",
    [
        lambda raw: {**raw, "extra": True},
        lambda raw: {key: value for key, value in raw.items() if key != "symbol"},
        lambda raw: {**raw, "schema": "production-strategy-contract/v2"},
        lambda raw: {**raw, "strategy_id": "ResearchStrategy"},
        lambda raw: {**raw, "strategy_version": "2.0.0"},
        lambda raw: {**raw, "symbol": "spy"},
        lambda raw: {**raw, "target_session_date": "2026-10-13T00:00:00"},
        lambda raw: {**raw, "source_head": "A" * 40},
        lambda raw: {
            **raw,
            "strategy_config": {
                **raw["strategy_config"],
                "desired_quantity": "1.0",
            },
        },
        lambda raw: {
            **raw,
            "strategy_config": {
                **raw["strategy_config"],
                "unexpected": 1,
            },
        },
    ],
)
def test_parser_rejects_noncanonical_or_wrong_semantics(mutate) -> None:
    raw = json.loads(_contract().to_json())
    altered = mutate(raw)
    value = json.dumps(altered, sort_keys=True, separators=(",", ":"))
    with pytest.raises(ValueError, match="invalid production strategy contract"):
        subject.ProductionStrategyContract.from_json(value)


def test_parser_rejects_noncanonical_json_and_duplicate_fields() -> None:
    canonical = _contract().to_json()
    with pytest.raises(ValueError):
        subject.ProductionStrategyContract.from_json(" " + canonical)
    duplicate = canonical.replace(
        '"schema":"production-strategy-contract/v1"',
        '"schema":"production-strategy-contract/v1","schema":"production-strategy-contract/v1"',
        1,
    )
    with pytest.raises(ValueError):
        subject.ProductionStrategyContract.from_json(duplicate)


def test_decimal_spelling_is_canonical_but_semantic_identity_ignores_scale() -> None:
    a = _contract(config=MovingAverageCrossoverConfig(5, 20, Decimal("1.0")))
    b = _contract(config=MovingAverageCrossoverConfig(5, 20, Decimal("1.000")))
    assert a.contract_id == b.contract_id
    assert a.to_json() == b.to_json()
    assert '"desired_quantity":"1"' in a.to_json()


def test_source_import_and_call_surface_is_inert() -> None:
    path = Path(subject.__file__)
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert imported <= {
        "__future__",
        "json",
        "re",
        "dataclasses",
        "datetime",
        "decimal",
        "uuid",
        "trading_bot.domain",
        "trading_bot.strategies.moving_average",
    }
    forbidden_import_fragments = {
        "robinhood",
        "oauth",
        "sqlite",
        "scheduler",
        "subprocess",
        "socket",
        "pathlib",
        "experiments",
        "optimization",
        "backtesting",
        "review_paper",
        "risk",
        "execution",
        "runtime",
        "provider",
        "openai",
    }
    assert not any(
        fragment in module.lower()
        for module in imported
        for fragment in forbidden_import_fragments
    )

    calls = {
        getattr(node.func, "attr", getattr(node.func, "id", ""))
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert not calls & {
        "open",
        "eval",
        "exec",
        "__import__",
        "sleep",
        "now",
        "utcnow",
        "run",
        "Popen",
        "connect",
        "request",
        "execute",
        "place_order",
        "review_equity_order",
    }
    assert "candidate" not in source.lower()
    assert "promotion" not in source.lower()


def test_checkpoint_is_source_only_and_profile_inventory_is_exact() -> None:
    spec = checkpoint_runner._checkpoint_specs()[NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-production-strategy-contract"
    assert (
        spec.authority_check
        is checkpoint_runner._arch134_production_strategy_authority_check
    )
    a = checkpoint_runner.ACTIVE_CI_CHECKPOINTS.index(NAME)
    assert checkpoint_runner.ACTIVE_CI_CHECKPOINTS[a : a + 2] == (
        NAME,
        "arch134-production-strategy-decision",
    )
    assert len(checkpoint_runner.ACTIVE_CI_CHECKPOINTS) == 68

    root = Path(certification.__file__).resolve().parents[1]
    inventory = certification.discover_inventory(root)
    profiles = {
        name: certification.select_inventory(inventory, name)
        for name in ("full", "robinhood", "legacy", "exhaustive")
    }
    assert {name: len(value) for name, value in profiles.items()} == {
        "full": 189,
        "robinhood": 103,
        "legacy": 222,
        "exhaustive": 411,
    }
    assert "tests/strategies/test_production_strategy_contract.py" in profiles["full"]
    assert "tests/strategies/test_production_strategy_decision.py" in profiles["full"]
    assert (
        "tests/strategies/test_production_strategy_contract.py"
        not in profiles["robinhood"]
    )


def test_contract_cannot_be_reconfigured_with_dataclass_replace_constants() -> None:
    contract = _contract()
    with pytest.raises(TypeError):
        replace(contract, schema="other")
    with pytest.raises(TypeError):
        replace(contract, strategy_id="other")
    with pytest.raises(TypeError):
        replace(contract, strategy_version="other")
    with pytest.raises(TypeError):
        replace(contract, contract_id=contract.contract_id)


@pytest.mark.parametrize("mutation", ["missing", "extra", "executable", "drift"])
@pytest.mark.parametrize(
    "check",
    [
        checkpoint_runner._arch134_production_paper_runtime_authority_check,
        checkpoint_runner._arch134_authentication_authority_check,
        checkpoint_runner._arch134_d1r5_authority_check,
    ],
)
def test_arch139b1_successor_test_overlay_fails_closed(monkeypatch, mutation, check):
    pins = dict(checkpoint_runner.ARCH139B1_CURRENT_INVENTORY_TEST_PIN_OVERRIDES)
    if mutation == "missing":
        pins.pop("tests/scripts/certification_runner/test_profiles.py")
    elif mutation == "extra":
        pins["tests/experiments/test_research_candidate_shadow_binding.py"] = "a" * 40
    elif mutation == "executable":
        pins["src/trading_bot/review_paper/armed_session.py"] = "a" * 40
    else:
        pins["tests/scripts/certification_runner/test_profiles.py"] = "0" * 40
    monkeypatch.setattr(
        checkpoint_runner, "ARCH139B1_CURRENT_INVENTORY_TEST_PIN_OVERRIDES", pins
    )
    root = Path(checkpoint_runner.__file__).resolve().parents[1]
    assert check(root)


@pytest.mark.parametrize(
    "name,digest",
    [
        (
            "ARCH134_CURRENT_DECISION_SOURCE_PINS",
            "432cd2b8efeb65f651d332acd499c2efeebe5180e16bb5aa224c19d64152bb12",
        ),
        (
            "ARCH134_MARKET_HISTORY_SOURCE_PINS",
            "e12072bc7da6398eed4c81274b38bffa89a280b7ff9bd4b919a5a5c6e904c9db",
        ),
        (
            "ARCH134_HISTORY_QUALIFICATION_SOURCE_PINS",
            "52b622392c5b32c4c13425aa0a39fca46bae89a915af66edfe6551376ba8d3fa",
        ),
        (
            "ARCH134_ARMED_PAPER_SOURCE_PINS",
            "10188ed4933e8874c145c07bfc7fb47c5ccc78cb74fb4d0ddc671f21c4cd3828",
        ),
        (
            "ARCH134_ARMED_PAPER_IMPORTS",
            "56ec5eb2ae4d0d457e44bfebbe43f23ad609839f90b0695e73d760d8b831ecbf",
        ),
        (
            "ARCH134_ARMED_PAPER_SUCCESSOR_PIN_OVERRIDES",
            "3976d983a2019193eddae89c89ce1fff87cc563e27327e176b67efbadbd9cb3d",
        ),
        (
            "ARCH134_ARMED_PAPER_SUCCESSOR_IMPORT_OVERRIDES",
            "b397d74fba50bfc157b6a7e6c8fd55c1d713fd0b0fa212dd7cdcc5e607fa59ad",
        ),
        (
            "ARCH134_ARMED_PAPER_RECOVERY_PIN_OVERRIDES",
            "0d4fe9f3a0e1ce1af7a01116c26cc8ef64bb9272630f165dcbb5c6863b0ec21b",
        ),
        (
            "ARCH134_ARMED_PAPER_RECOVERY_IMPORT_OVERRIDES",
            "d020b022b3bf3950173b11d5067fee3ad3e04178017ee4e39bf64f5d404980b3",
        ),
        (
            "ARCH134_PRODUCTION_PAPER_RUNTIME_SOURCE_PINS",
            "8c957aa3d3b5707d644b2d086db08023a01ed35cd3ab3218bb27c19424f03235",
        ),
        (
            "ARCH134_PRODUCTION_PAPER_RUNTIME_IMPORTS",
            "d784128948fb9cc31c6f9794e8347b449e0116d2efd1583ec617c88fa0cc536a",
        ),
        (
            "ARCH134_PRODUCTION_PAPER_RUNTIME_SUCCESSOR_SOURCE_PINS",
            "403181d4169a5a6537716bd12c1400884fcb959a93867544358ed70889d19de8",
        ),
        (
            "ARCH134_PRODUCTION_PAPER_RUNTIME_SUCCESSOR_IMPORTS",
            "5a07daffa9aad877de8607b4b147c4dd9c2662eaade00bc3d25cb990e641a42d",
        ),
        (
            "ARCH134_PRODUCTION_PAPER_RUNTIME_RECOVERY_SOURCE_PINS",
            "dca04885add2cc74ea2b21383dca60f0c6636fd7d1e12cfc6d8100f8a813d390",
        ),
        (
            "ARCH134_PRODUCTION_PAPER_RUNTIME_RECOVERY_IMPORTS",
            "e6e3a127f70224e978504d57c280de796d3a93c4274c8ff7e62ab0ad3d37f1ba",
        ),
        (
            "ARCH134_AUTH_SOURCE_PINS",
            "92799d3ff0a74258bc12540d55303b509fcae90c6fbed6e18c4cda1e0bfe7903",
        ),
        (
            "ARCH134_AUTH_TEST_PIN_OVERRIDES",
            "a240ad6e800ff29a6720ef416f30f99243f486eeb1b1a7e1f41b097cdd6ce6a6",
        ),
        (
            "ARCH134_AUTH_CORRECTION_TEST_PINS",
            "cc25401816f1fcb59c7ee7bdccd26d390089a19744508cbda64c74ebcdb1dd90",
        ),
        (
            "ARCH134_AUTH_IMPORTS",
            "f4303daae96be4c0d1d62f79e03ee35e3f6b3605e1553550ef8a305a743738eb",
        ),
        (
            "ARCH134_D1R4_SOURCE_PINS",
            "9ed4ef533f4602b76382ce6e6841e790c1304de751684cd9a81cfb41a8f50ab2",
        ),
        (
            "ARCH134_D1R4_IMPORTS",
            "1d88dac76eecb29dbaedd2cc4e117242be1bd1a027824e27a8c122b02de82ec4",
        ),
        (
            "ARCH134_D1R4R_SOURCE_PINS",
            "a6c6af6e231ea41074d2dd8b9fe26e36f9c8e70ef8d764626a22efd7217778c2",
        ),
        (
            "ARCH134_D1R4R_IMPORTS",
            "2fb70bdf88ca899d1ffe27a61a5fe51707b16779161d35bfd11ae3f6f3305456",
        ),
        (
            "ARCH134_HIST2_TEST_PIN_OVERRIDES",
            "1d005a7fa62d7172d58be3a9b61443e548f0c62c92ad8652bc883b8df302d950",
        ),
        (
            "ARCH134_D1R5_TEST_PIN_OVERRIDES",
            "bcdb35cb77572df147ea12a9db54d22da2cbe8933140a6c1a7b448dba8be287b",
        ),
        (
            "ARCH134_D1R5_SOURCE_PINS",
            "3412b689a3c5b5d6ef4495fb62ce3611869e6e512d1055387b50276d188cd230",
        ),
        (
            "ARCH134_D1R5_IMPORTS",
            "7402233d1d0d9ec921399a57cc8d3a3dda4ee82497d7ac608a4b8d88b2c9b38f",
        ),
        (
            "ARCH138_CURRENT_INVENTORY_TEST_PIN_OVERRIDES",
            "8a4021b92a5354cfbdb5394692eb50c14f6a13982b9a50aeb7d259553c7e5988",
        ),
        (
            "ARCH139A_CURRENT_INVENTORY_TEST_PIN_OVERRIDES",
            "9ec72c131a25b962a7d3e49124f99aa712dc2a8e0182d297f4a78507b6e0fb69",
        ),
        (
            "ARCH134_RUNTIME_ACL_SOURCE_PINS",
            "93760d287a535297a29f1e4acb53c98450613ae6196df064f8697906bfcd00ad",
        ),
        (
            "ARCH134_RUNTIME_ACL_IMPORTS",
            "cf5604482cf46f2e7c0823585526f140e9c2b13f415f726861e735c0f2cda14d",
        ),
        (
            "ARCH134_RUNTIME_ACL_AST_PINS",
            "a8f319cc3f413eacca83e5effab7521394cc3190eafe403e95fb2dd33b7e0acc",
        ),
    ],
)
def test_arch139b1_frozen_predecessor_dictionaries(name, digest):
    assert (
        sha256(
            json.dumps(getattr(checkpoint_runner, name), sort_keys=True).encode()
        ).hexdigest()
        == digest
    )


@pytest.mark.parametrize(
    "name",
    (
        "ARCH134_HIST2_TEST_PIN_OVERRIDES",
        "ARCH134_D1R5_TEST_PIN_OVERRIDES",
        "ARCH138_CURRENT_INVENTORY_TEST_PIN_OVERRIDES",
        "ARCH139A_CURRENT_INVENTORY_TEST_PIN_OVERRIDES",
    ),
)
def test_arch139b1_predecessor_drift_cannot_be_hidden(monkeypatch, name):
    pins = dict(getattr(checkpoint_runner, name))
    key = next(iter(pins))
    pins[key] = "0" * 40
    monkeypatch.setattr(checkpoint_runner, name, pins)
    root = Path(checkpoint_runner.__file__).resolve().parents[1]
    assert checkpoint_runner._arch134_d1r5_authority_check(root)


@pytest.mark.parametrize("mutation", ["missing", "extra", "executable", "drift"])
@pytest.mark.parametrize(
    "check",
    [
        checkpoint_runner._arch134_production_paper_runtime_authority_check,
        checkpoint_runner._arch134_authentication_authority_check,
        checkpoint_runner._arch134_d1r5_authority_check,
    ],
)
def test_arch139b2_successor_test_overlay_fails_closed(monkeypatch, mutation, check):
    pins = dict(checkpoint_runner.ARCH139B2_CURRENT_INVENTORY_TEST_PIN_OVERRIDES)
    if mutation == "missing":
        pins.pop("tests/scripts/certification_runner/test_profiles.py")
    elif mutation == "extra":
        pins["tests/experiments/test_research_candidate_shadow_binding.py"] = "a" * 40
    elif mutation == "executable":
        pins["src/trading_bot/review_paper/armed_session.py"] = "a" * 40
    else:
        pins["tests/scripts/certification_runner/test_profiles.py"] = "0" * 40
    monkeypatch.setattr(
        checkpoint_runner, "ARCH139B2_CURRENT_INVENTORY_TEST_PIN_OVERRIDES", pins
    )
    root = Path(checkpoint_runner.__file__).resolve().parents[1]
    assert check(root)


@pytest.mark.parametrize(
    "name,digest",
    [
        (
            "ARCH134_CURRENT_DECISION_SOURCE_PINS",
            "432cd2b8efeb65f651d332acd499c2efeebe5180e16bb5aa224c19d64152bb12",
        ),
        (
            "ARCH134_MARKET_HISTORY_SOURCE_PINS",
            "e12072bc7da6398eed4c81274b38bffa89a280b7ff9bd4b919a5a5c6e904c9db",
        ),
        (
            "ARCH134_HISTORY_QUALIFICATION_SOURCE_PINS",
            "52b622392c5b32c4c13425aa0a39fca46bae89a915af66edfe6551376ba8d3fa",
        ),
        (
            "ARCH134_ARMED_PAPER_SOURCE_PINS",
            "10188ed4933e8874c145c07bfc7fb47c5ccc78cb74fb4d0ddc671f21c4cd3828",
        ),
        (
            "ARCH134_ARMED_PAPER_IMPORTS",
            "56ec5eb2ae4d0d457e44bfebbe43f23ad609839f90b0695e73d760d8b831ecbf",
        ),
        (
            "ARCH134_ARMED_PAPER_SUCCESSOR_PIN_OVERRIDES",
            "3976d983a2019193eddae89c89ce1fff87cc563e27327e176b67efbadbd9cb3d",
        ),
        (
            "ARCH134_ARMED_PAPER_SUCCESSOR_IMPORT_OVERRIDES",
            "b397d74fba50bfc157b6a7e6c8fd55c1d713fd0b0fa212dd7cdcc5e607fa59ad",
        ),
        (
            "ARCH134_ARMED_PAPER_RECOVERY_PIN_OVERRIDES",
            "0d4fe9f3a0e1ce1af7a01116c26cc8ef64bb9272630f165dcbb5c6863b0ec21b",
        ),
        (
            "ARCH134_ARMED_PAPER_RECOVERY_IMPORT_OVERRIDES",
            "d020b022b3bf3950173b11d5067fee3ad3e04178017ee4e39bf64f5d404980b3",
        ),
        (
            "ARCH134_PRODUCTION_PAPER_RUNTIME_SOURCE_PINS",
            "8c957aa3d3b5707d644b2d086db08023a01ed35cd3ab3218bb27c19424f03235",
        ),
        (
            "ARCH134_PRODUCTION_PAPER_RUNTIME_IMPORTS",
            "d784128948fb9cc31c6f9794e8347b449e0116d2efd1583ec617c88fa0cc536a",
        ),
        (
            "ARCH134_PRODUCTION_PAPER_RUNTIME_SUCCESSOR_SOURCE_PINS",
            "403181d4169a5a6537716bd12c1400884fcb959a93867544358ed70889d19de8",
        ),
        (
            "ARCH134_PRODUCTION_PAPER_RUNTIME_SUCCESSOR_IMPORTS",
            "5a07daffa9aad877de8607b4b147c4dd9c2662eaade00bc3d25cb990e641a42d",
        ),
        (
            "ARCH134_PRODUCTION_PAPER_RUNTIME_RECOVERY_SOURCE_PINS",
            "dca04885add2cc74ea2b21383dca60f0c6636fd7d1e12cfc6d8100f8a813d390",
        ),
        (
            "ARCH134_PRODUCTION_PAPER_RUNTIME_RECOVERY_IMPORTS",
            "e6e3a127f70224e978504d57c280de796d3a93c4274c8ff7e62ab0ad3d37f1ba",
        ),
        (
            "ARCH134_AUTH_SOURCE_PINS",
            "92799d3ff0a74258bc12540d55303b509fcae90c6fbed6e18c4cda1e0bfe7903",
        ),
        (
            "ARCH134_AUTH_TEST_PIN_OVERRIDES",
            "a240ad6e800ff29a6720ef416f30f99243f486eeb1b1a7e1f41b097cdd6ce6a6",
        ),
        (
            "ARCH134_AUTH_CORRECTION_TEST_PINS",
            "cc25401816f1fcb59c7ee7bdccd26d390089a19744508cbda64c74ebcdb1dd90",
        ),
        (
            "ARCH134_AUTH_IMPORTS",
            "f4303daae96be4c0d1d62f79e03ee35e3f6b3605e1553550ef8a305a743738eb",
        ),
        (
            "ARCH134_D1R4_SOURCE_PINS",
            "9ed4ef533f4602b76382ce6e6841e790c1304de751684cd9a81cfb41a8f50ab2",
        ),
        (
            "ARCH134_D1R4_IMPORTS",
            "1d88dac76eecb29dbaedd2cc4e117242be1bd1a027824e27a8c122b02de82ec4",
        ),
        (
            "ARCH134_D1R4R_SOURCE_PINS",
            "a6c6af6e231ea41074d2dd8b9fe26e36f9c8e70ef8d764626a22efd7217778c2",
        ),
        (
            "ARCH134_D1R4R_IMPORTS",
            "2fb70bdf88ca899d1ffe27a61a5fe51707b16779161d35bfd11ae3f6f3305456",
        ),
        (
            "ARCH134_HIST2_TEST_PIN_OVERRIDES",
            "1d005a7fa62d7172d58be3a9b61443e548f0c62c92ad8652bc883b8df302d950",
        ),
        (
            "ARCH134_D1R5_TEST_PIN_OVERRIDES",
            "bcdb35cb77572df147ea12a9db54d22da2cbe8933140a6c1a7b448dba8be287b",
        ),
        (
            "ARCH134_D1R5_SOURCE_PINS",
            "3412b689a3c5b5d6ef4495fb62ce3611869e6e512d1055387b50276d188cd230",
        ),
        (
            "ARCH134_D1R5_IMPORTS",
            "7402233d1d0d9ec921399a57cc8d3a3dda4ee82497d7ac608a4b8d88b2c9b38f",
        ),
        (
            "ARCH138_CURRENT_INVENTORY_TEST_PIN_OVERRIDES",
            "8a4021b92a5354cfbdb5394692eb50c14f6a13982b9a50aeb7d259553c7e5988",
        ),
        (
            "ARCH139A_CURRENT_INVENTORY_TEST_PIN_OVERRIDES",
            "9ec72c131a25b962a7d3e49124f99aa712dc2a8e0182d297f4a78507b6e0fb69",
        ),
        (
            "ARCH139B1_CURRENT_INVENTORY_TEST_PIN_OVERRIDES",
            "d66e134a5491e1e2966728e27558f05c51946c5e89930707e1471f339324634c",
        ),
        (
            "ARCH134_RUNTIME_ACL_SOURCE_PINS",
            "93760d287a535297a29f1e4acb53c98450613ae6196df064f8697906bfcd00ad",
        ),
        (
            "ARCH134_RUNTIME_ACL_IMPORTS",
            "cf5604482cf46f2e7c0823585526f140e9c2b13f415f726861e735c0f2cda14d",
        ),
        (
            "ARCH134_RUNTIME_ACL_AST_PINS",
            "a8f319cc3f413eacca83e5effab7521394cc3190eafe403e95fb2dd33b7e0acc",
        ),
    ],
)
def test_arch139b2_frozen_predecessor_dictionaries(name, digest):
    assert (
        sha256(
            json.dumps(getattr(checkpoint_runner, name), sort_keys=True).encode()
        ).hexdigest()
        == digest
    )


@pytest.mark.parametrize(
    "name",
    [
        "ARCH134_HIST2_TEST_PIN_OVERRIDES",
        "ARCH134_D1R5_TEST_PIN_OVERRIDES",
        "ARCH138_CURRENT_INVENTORY_TEST_PIN_OVERRIDES",
        "ARCH139A_CURRENT_INVENTORY_TEST_PIN_OVERRIDES",
        "ARCH139B1_CURRENT_INVENTORY_TEST_PIN_OVERRIDES",
    ],
)
def test_arch139b2_predecessor_drift_cannot_be_hidden(monkeypatch, name):
    pins = dict(getattr(checkpoint_runner, name))
    key = next(iter(pins))
    pins[key] = "0" * 40
    monkeypatch.setattr(checkpoint_runner, name, pins)
    root = Path(checkpoint_runner.__file__).resolve().parents[1]
    assert checkpoint_runner._arch134_d1r5_authority_check(root)
