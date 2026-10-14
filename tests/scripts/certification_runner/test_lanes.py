from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_test_certification as runner

from .helpers import (
    _inventory,
    _lane_names,
    _profile_inventory,
)


def test_inventory_partition_is_complete_disjoint_and_deterministic(
    tmp_path: Path,
) -> None:
    modules = _inventory(tmp_path)
    inventory = runner.discover_inventory(tmp_path)
    assert inventory == tuple(sorted(modules))
    broad, serial = runner.separate_serial(inventory, ("tests/safety/test_serial.py",))
    lanes = runner.balance_broad(tmp_path, broad)
    assert lanes == runner.balance_broad(tmp_path, broad)
    runner.validate_partitions(inventory, (*lanes, serial))
    assert set(lanes[0]).isdisjoint(lanes[1])
    assert set(lanes[0] + lanes[1] + serial) == set(modules)


def test_missing_serial_and_duplicate_or_overlap_fail(tmp_path: Path) -> None:
    inventory = runner.discover_inventory(tmp_path)
    with pytest.raises(runner.CertificationError, match="Missing serial"):
        runner.separate_serial(inventory, ("tests/missing/test_serial.py",))
    with pytest.raises(runner.CertificationError, match="Duplicate"):
        runner.validate_partitions(("a", "b"), (("a",), ("a", "b")))
    with pytest.raises(runner.CertificationError, match="Incomplete"):
        runner.validate_partitions(("a", "b"), (("a",), ()))


def test_robinhood_has_two_deterministic_balanced_nonempty_lanes(
    tmp_path: Path,
) -> None:
    inventory = _profile_inventory(tmp_path, "robinhood")
    raw = runner.balance_broad(tmp_path, inventory)
    weights = [
        sum((tmp_path / module).stat().st_size for module in lane) for lane in raw
    ]
    assert abs(weights[0] - weights[1]) <= max(
        (tmp_path / module).stat().st_size for module in inventory
    )

    lanes = runner.build_lanes(tmp_path, inventory, "robinhood")
    assert tuple(lanes) == _lane_names("robinhood")
    assert all(lanes.values())
    assert lanes == runner.build_lanes(tmp_path, inventory, "robinhood")
    runner.validate_partitions(inventory, tuple(lanes.values()))
    for module, target in runner.ROBINHOOD_LANE_PINS.items():
        if module in inventory:
            assert module in tuple(lanes.values())[target]


def test_reviewed_lane_pins_override_size_proxy_without_changing_partition(
    tmp_path: Path,
) -> None:
    modules = tuple(runner.ROBINHOOD_LANE_PINS)
    for index, module in enumerate(modules):
        path = tmp_path / module
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * (100 - index))

    lanes = runner.build_lanes(tmp_path, modules, "robinhood")
    runner.validate_partitions(modules, tuple(lanes.values()))
    for module, target in runner.ROBINHOOD_LANE_PINS.items():
        assert module in tuple(lanes.values())[target]


def test_lane_pins_reject_invalid_lane_number() -> None:
    with pytest.raises(runner.CertificationError, match="lane 0 or 1"):
        runner.apply_lane_pins((("a.py",), ("b.py",)), {"a.py": 2})


@pytest.mark.parametrize(
    "lanes", [{}, {"empty": ()}, {"valid": ("test.py",), "empty": ()}]
)
def test_empty_lane_never_launches_pytest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, lanes: dict[str, tuple[str, ...]]
) -> None:
    monkeypatch.setattr(
        runner.subprocess, "Popen", lambda *a, **k: pytest.fail("pytest launched")
    )
    with pytest.raises(runner.CertificationError, match="contain test modules"):
        runner.run_children(SimpleNamespace(), lanes, tmp_path)
