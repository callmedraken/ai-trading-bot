"""Explicit-file canonical parsing, bounded reads and cached failures."""

import io
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from trading_bot.domain import Symbol
from trading_bot.gui import (
    MAX_PRODUCTION_STRATEGY_BYTES,
    ProductionStrategyContractInspectionService,
    ProductionStrategyPageStatus,
)
from trading_bot.strategies.moving_average import MovingAverageCrossoverConfig
from trading_bot.strategies.production import ProductionStrategyContract


def contract_text() -> str:
    return ProductionStrategyContract(
        date(2026, 10, 12),
        "a" * 40,
        "b" * 40,
        Symbol("SPY"),
        MovingAverageCrossoverConfig(5, 20, Decimal("1.25")),
    ).to_json()


def test_one_explicit_bounded_binary_read_and_exact_parser_input(monkeypatch):
    selected = Path("selected.json")
    opens = []
    bounds = []
    text = contract_text()

    class Reader(io.BytesIO):
        def read(self, size=-1):
            bounds.append(size)
            return super().read(size)

    def opened(path, mode):
        opens.append((path, mode))
        return Reader(text.encode())

    monkeypatch.setattr(Path, "open", opened)
    parser = ProductionStrategyContract.from_json
    inputs = []

    def parse(value):
        inputs.append(value)
        return parser(value)

    monkeypatch.setattr(ProductionStrategyContract, "from_json", parse)
    service = ProductionStrategyContractInspectionService(selected)
    state = service.get_production_strategy_state()
    assert state is service.get_production_strategy_state()
    assert state.status is ProductionStrategyPageStatus.AVAILABLE
    assert opens == [(selected, "rb")]
    assert bounds == [MAX_PRODUCTION_STRATEGY_BYTES + 1]
    assert inputs == [text]


@pytest.mark.parametrize(
    "kind",
    [
        "oversize",
        "utf8",
        "json",
        "duplicate",
        "unknown",
        "noncanonical",
        "id",
        "head",
        "tree",
        "quantity",
        "windows",
        "bool",
        "schema",
    ],
)
def test_invalid_contract_is_cached_and_bounded(tmp_path, monkeypatch, kind):
    text = contract_text()
    raw = json.loads(text)
    payload = text.encode()
    if kind == "oversize":
        payload = b"x" * (MAX_PRODUCTION_STRATEGY_BYTES + 1)
    elif kind == "utf8":
        payload = b"\xff"
    elif kind == "json":
        payload = b"{"
    elif kind == "duplicate":
        payload = text.replace(
            "{", '{"schema":"production-strategy-contract/v1",', 1
        ).encode()
    elif kind == "noncanonical":
        payload = (text + "\n").encode()
    else:
        if kind == "unknown":
            raw["SECRET_PATH"] = "C:/private"
        elif kind == "id":
            raw["contract_id"] = "11111111-1111-5111-8111-111111111111"
        elif kind in ("head", "tree"):
            raw["source_" + kind] = "A" * 40
        elif kind == "quantity":
            raw["strategy_config"]["desired_quantity"] = "1.250"
        elif kind == "windows":
            raw["strategy_config"]["short_window"] = 20
        elif kind == "bool":
            raw["strategy_config"]["short_window"] = True
        elif kind == "schema":
            raw["schema"] = "research-candidate/v1"
        payload = json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
    path = tmp_path / "secret-selected.json"
    path.write_bytes(payload)
    original = Path.open
    opens = []

    def opened(selected, *args, **kwargs):
        opens.append(selected)
        return original(selected, *args, **kwargs)

    monkeypatch.setattr(Path, "open", opened)
    service = ProductionStrategyContractInspectionService(path)
    state = service.get_production_strategy_state()
    assert state is service.get_production_strategy_state()
    assert state.status is ProductionStrategyPageStatus.ATTENTION
    assert state.contract is None
    assert str(path) not in repr(state) and "SECRET_PATH" not in repr(state)
    assert opens == [path]


@pytest.mark.parametrize(
    "path",
    [
        r"\\server\share\contract.json",
        "//server/share/contract.json",
        r"\\?\C:\contract.json",
        "https://host/contract.json",
        "C:contract.json",
        "contract.json:stream",
        "contract.txt",
    ],
)
def test_unsupported_local_paths_do_not_open(monkeypatch, path):
    def forbidden(*args, **kwargs):
        pytest.fail("Unsupported path opened")

    monkeypatch.setattr(Path, "open", forbidden)
    state = ProductionStrategyContractInspectionService(
        Path(path)
    ).get_production_strategy_state()
    assert state.status is ProductionStrategyPageStatus.ATTENTION


def test_cached_os_failure_never_exposes_exception_or_path(monkeypatch):
    calls = []

    def fail(*args, **kwargs):
        calls.append(1)
        raise OSError("SECRET C:/private/credential")

    monkeypatch.setattr(Path, "open", fail)
    service = ProductionStrategyContractInspectionService(Path("selected.json"))
    state = service.get_production_strategy_state()
    assert state is service.get_production_strategy_state()
    assert len(calls) == 1 and "SECRET" not in repr(state)
    with pytest.raises(TypeError):
        ProductionStrategyContractInspectionService("selected.json")
