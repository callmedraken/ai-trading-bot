from __future__ import annotations

import ast
import json
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
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
    assert len(checkpoint_runner.ACTIVE_CI_CHECKPOINTS) == 62

    root = Path(certification.__file__).resolve().parents[1]
    inventory = certification.discover_inventory(root)
    profiles = {
        name: certification.select_inventory(inventory, name)
        for name in ("full", "robinhood", "legacy", "exhaustive")
    }
    assert {name: len(value) for name, value in profiles.items()} == {
        "full": 168,
        "robinhood": 93,
        "legacy": 205,
        "exhaustive": 373,
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
