from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_test_certification as runner

from .helpers import (
    _fixture_profiles,
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


def test_full_four_lane_evidence_model_is_exact_and_repeatable() -> None:
    import hashlib
    import json

    root = Path(runner.__file__).resolve().parents[1]
    inventory = runner.select_inventory(runner.discover_inventory(root), "full")
    weights = runner.full_module_weights(inventory)
    assert len(inventory) == len(runner.FULL_MODULE_TIMINGS_MS) == 189
    assert set(weights) == {module for module, _ in runner.FULL_MODULE_TIMINGS_MS}
    assert runner.FULL_FALLBACK_MS == 1000
    assert (
        hashlib.sha256(
            json.dumps(weights, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == "c478e893fa7cbfa86582f1b4ed1182cdd1a81ed25ff5359ea000879361d0c1ab"
    )
    lanes = runner.build_lanes(root, inventory, "full")
    assert tuple(lanes) == ("broad-1", "broad-2", "broad-3", "broad-4")
    assert all(lanes.values())
    assert lanes == runner.build_lanes(root, tuple(reversed(inventory)), "full")
    runner.validate_partitions(inventory, tuple(lanes.values()))
    assert tuple(map(len, lanes.values())) == (47, 48, 48, 46)
    assert tuple(
        sum(weights[module] for module in lane) for lane in lanes.values()
    ) == (278227, 278227, 278227, 278226)
    # The sole 0-ms measured module uses the reviewed positive 1-ms minimum.
    assert weights["tests/test_config.py"] == 1
    raw = dict(weights, **{"tests/test_config.py": 0})
    for count, expected in (
        (2, (556453, 556453)),
        (3, (370969, 370969, 370968)),
        (4, (278227, 278227, 278226, 278226)),
    ):
        totals = [0] * count
        for module in sorted(raw, key=lambda name: (-raw[name], name)):
            index = min(range(count), key=lambda lane: (totals[lane], lane))
            totals[index] += raw[module]
        assert tuple(totals) == expected


def test_full_fixture_matches_frozen_timing_membership() -> None:
    assert set(_fixture_profiles()["full"]) == {
        module for module, _ in runner.FULL_MODULE_TIMINGS_MS
    }


def test_full_path_and_lane_ties_and_future_supported_fallback(monkeypatch) -> None:
    original = runner.FULL_MODULE_TIMINGS_MS
    modules = tuple(f"tests/domain/test_{letter}.py" for letter in "abcdef")
    monkeypatch.setattr(runner, "FULL_MODULE_TIMINGS_MS", ((modules[1], 1000),))
    assert runner.full_module_weights(modules) == dict.fromkeys(modules, 1000)
    expected = (
        (modules[0], modules[4]),
        (modules[1], modules[5]),
        (modules[2],),
        (modules[3],),
    )
    assert runner.balance_full(tuple(reversed(modules))) == expected
    monkeypatch.setattr(runner, "FULL_MODULE_TIMINGS_MS", original)
    root = Path(runner.__file__).resolve().parents[1]
    current = runner.select_inventory(runner.discover_inventory(root), "full")
    future = "tests/domain/test_future_supported.py"
    selected = runner.select_inventory(
        tuple(sorted((*runner.discover_inventory(root), future))), "full"
    )
    assert set(selected) == {*current, future}
    assert runner.full_module_weights(selected)[future] == 1000
    runner.validate_partitions(selected, runner.balance_full(selected))


@pytest.mark.parametrize("value", [True, False, 0, -1, 1.0, "1", None, [], {}])
def test_full_invalid_timing_values_fail_closed(monkeypatch, value) -> None:
    module = "tests/domain/test_market.py"
    monkeypatch.setattr(runner, "FULL_MODULE_TIMINGS_MS", ((module, value),))
    with pytest.raises(runner.CertificationError, match="positive integers"):
        runner.balance_full((module,))


@pytest.mark.parametrize(
    "table",
    [
        None,
        {},
        (("tests/domain/test_market.py",),),
        (None,),
        (("tests/domain/test_market.py", 1, 2),),
        ((None, 1),),
        (("tests\\domain\\test_market.py", 1),),
        (("tests/domain/./test_market.py", 1),),
        (("tests//domain/test_market.py", 1),),
        (("tests/domain/../domain/test_market.py", 1),),
        (("Tests/domain/test_market.py", 1),),
        (("/tests/domain/test_market.py", 1),),
        (("tests/domain/test_market.py", 1), ("tests/domain/test_market.py", 2)),
        (("tests/domain/test_market.py", 1), ("tests/domain/./test_market.py", 2)),
    ],
)
def test_full_malformed_and_duplicate_timing_paths_fail_closed(monkeypatch, table):
    monkeypatch.setattr(runner, "FULL_MODULE_TIMINGS_MS", table)
    with pytest.raises(runner.CertificationError):
        runner.balance_full(("tests/domain/test_market.py",))


@pytest.mark.parametrize(
    "module",
    [
        "tests/domain/test_removed.py",
        "tests/gui/test_legacy.py",
    ],
)
def test_full_stale_or_nonfull_weight_fails_closed_before_children(monkeypatch, module):
    monkeypatch.setattr(runner, "FULL_MODULE_TIMINGS_MS", ((module, 1),))
    with pytest.raises(runner.CertificationError, match="Stale FULL timing module"):
        runner.build_lanes(Path("."), ("tests/domain/test_market.py",), "full")


def test_robinhood_r3h_pins_remain_exact() -> None:
    assert runner.ROBINHOOD_LANE_PINS == {
        "tests/runtime/checkpoint_runner/test_arch131.py": 0,
        "tests/runtime/checkpoint_runner/test_arch133_h_k.py": 0,
        "tests/runtime/checkpoint_runner/test_arch133_l_m.py": 1,
        "tests/review_paper/test_arch133_scheduler_installation.py": 1,
    }


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "extra",
        "wrong_blob",
        "malformed_blob",
        "malformed_table",
        "digest",
        "predecessor",
        "predecessor_material",
        "predecessor_digest",
    ],
)
def test_r3i_successor_overlay_fails_closed(monkeypatch, mutation):
    from scripts import checkpoint_runner as checkpoint

    pins = dict(checkpoint.ARCH132_R3I_CURRENT_TEST_PIN_OVERRIDES)
    path = "tests/scripts/certification_runner/test_profiles.py"
    predecessor = checkpoint.ARCH143_CURRENT_INVENTORY_TEST_PIN_OVERRIDES[path]
    if mutation == "missing":
        pins.pop(path)
    elif mutation == "extra":
        pins["tests/domain/test_market.py"] = "a" * 40
    elif mutation == "wrong_blob":
        pins[path] = "a" * 40
    elif mutation == "malformed_blob":
        pins[path] = None
    elif mutation == "malformed_table":
        pins = None
    elif mutation == "digest":
        monkeypatch.setattr(
            checkpoint, "ARCH132_R3I_CURRENT_TEST_PINS_SHA256", "a" * 64
        )
    elif mutation == "predecessor":
        predecessor = "a" * 40
    elif mutation == "predecessor_material":
        prior = dict(checkpoint.ARCH143_CURRENT_INVENTORY_TEST_PIN_OVERRIDES)
        prior[path] = "a" * 40
        monkeypatch.setattr(
            checkpoint, "ARCH143_CURRENT_INVENTORY_TEST_PIN_OVERRIDES", prior
        )
    else:
        monkeypatch.setattr(
            checkpoint, "ARCH143_CURRENT_INVENTORY_TEST_PINS_SHA256", "a" * 64
        )
    monkeypatch.setattr(checkpoint, "ARCH132_R3I_CURRENT_TEST_PIN_OVERRIDES", pins)
    with pytest.raises(ValueError, match="R3I"):
        checkpoint._arch132_r3i_current_inventory_test_pin(path, predecessor)
    root = Path(checkpoint.__file__).resolve().parents[1]
    if mutation != "predecessor":
        assert checkpoint._arch134_d1r8_authority_check(root)


def test_r3i_successor_is_limited_to_changed_previously_pinned_tests():
    from scripts import checkpoint_runner as checkpoint

    root = Path(checkpoint.__file__).resolve().parents[1]
    pins = checkpoint.ARCH132_R3I_CURRENT_TEST_PIN_OVERRIDES
    assert set(pins) == {
        "tests/scripts/certification_runner/test_lanes.py",
        "tests/scripts/certification_runner/test_profiles.py",
        "tests/review_paper/test_d1_session_execution.py",
        "tests/strategies/test_production_strategy_contract.py",
        "tests/gui/test_gui_a17_research_candidate_lifecycle_audit_qt.py",
        "tests/gui/test_gui_a18_research_candidate_lifecycle_boundary_map.py",
    }
    for module, pin in pins.items():
        predecessor = checkpoint.ARCH143_CURRENT_INVENTORY_TEST_PIN_OVERRIDES.get(
            module, checkpoint.ARCH134_D1R5_TEST_PIN_OVERRIDES.get(module)
        )
        assert predecessor != pin
        assert (
            checkpoint._arch132_r3i_current_inventory_test_pin(module, predecessor)
            == pin
        )
        assert checkpoint._git_blob_sha1(root / module) == (
            checkpoint._arch144_current_inventory_test_pin(module, pin)
        )
    assert (
        checkpoint._arch132_r3i_current_inventory_test_pin("other", "unchanged")
        == "unchanged"
    )
    for check in (
        checkpoint._arch134_production_paper_runtime_authority_check,
        checkpoint._arch134_authentication_authority_check,
        checkpoint._arch134_d1r5_authority_check,
        checkpoint._arch134_d1r6_authority_check,
        checkpoint._arch134_d1r7_authority_check,
        checkpoint._arch134_d1r8_authority_check,
    ):
        assert check(root) == ()


def test_arch144_current_inventory_successor_is_exact_and_current():
    import hashlib
    import json

    from scripts import checkpoint_runner as checkpoint

    root = Path(checkpoint.__file__).resolve().parents[1]
    pins = checkpoint.ARCH144_CURRENT_INVENTORY_TEST_PIN_OVERRIDES
    assert set(pins) == {
        *checkpoint.ARCH143_CURRENT_INVENTORY_TEST_PIN_OVERRIDES,
        "tests/scripts/certification_runner/test_lanes.py",
    }
    assert (
        hashlib.sha256(json.dumps(pins, sort_keys=True).encode()).hexdigest()
        == checkpoint.ARCH144_CURRENT_INVENTORY_TEST_PINS_SHA256
    )
    for module, pin in pins.items():
        predecessor = checkpoint.ARCH132_R3I_CURRENT_TEST_PIN_OVERRIDES.get(module)
        if predecessor is None:
            predecessor = checkpoint.ARCH143_CURRENT_INVENTORY_TEST_PIN_OVERRIDES[
                module
            ]
        assert predecessor != pin
        assert checkpoint._arch144_current_inventory_test_pin(
            module, predecessor
        ) == checkpoint._arch134_f1_current_inventory_test_pin(module, pin)
        assert checkpoint._git_blob_sha1(root / module) == (
            checkpoint._arch134_f1_current_inventory_test_pin(module, pin)
        )
    assert checkpoint._arch144_current_inventory_test_pin("other", "unchanged") == (
        "unchanged"
    )


def test_r3i_preserves_all_arch139_through_143_predecessor_constants_and_ci_route():
    import ast
    import hashlib

    from scripts import checkpoint_runner as checkpoint

    tree = ast.parse(Path(checkpoint.__file__).read_text(encoding="utf-8"))
    material = "\n".join(
        ast.dump(node, include_attributes=False)
        for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and node.target.id.startswith(
            ("ARCH139", "ARCH140", "ARCH141", "ARCH142", "ARCH143")
        )
    )
    assert (
        hashlib.sha256(material.encode()).hexdigest()
        == "d85308fc9fed15c9c435c2220402ee9a2e96ddddda145d0354eac8763d040aed"
    )
    assert (
        checkpoint.resolve_ci_checkpoint(
            checkpoint._checkpoint_specs(),
            "feature/test-suite-arch132-r3i-full-hygiene-current",
            "push",
        )
        is None
    )
    assert checkpoint.resolve_ci_certification_profile(None) is None


def test_f1_parent_outlier_placement_preserves_r3h_and_two_lane_coverage():
    root = Path(runner.__file__).resolve().parents[1]
    selected = runner.select_inventory(runner.discover_inventory(root), "robinhood")
    assert runner.ROBINHOOD_F1_LANE_PINS == {
        "tests/review_paper/test_five_session_soak.py": 0
    }
    assert set(runner.ROBINHOOD_F1_LANE_PINS).isdisjoint(runner.ROBINHOOD_LANE_PINS)
    lanes = runner.build_lanes(root, selected, "robinhood")
    assert tuple(lanes) == ("robinhood-1", "robinhood-2")
    runner.validate_partitions(selected, tuple(lanes.values()))
    for module, index in {
        **runner.ROBINHOOD_LANE_PINS,
        **runner.ROBINHOOD_F1_LANE_PINS,
    }.items():
        assert module in tuple(lanes.values())[index]
