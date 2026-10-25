import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_test_certification as runner

from .helpers import (
    _fixture_profiles,
    _inventory,
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


def _ordered_lane_hash(modules: tuple[str, ...]) -> str:
    return hashlib.sha256(
        ("".join(f"{module}\n" for module in modules)).encode()
    ).hexdigest()


def test_robinhood_timing_model_is_exact_and_repeatable() -> None:
    root = Path(runner.__file__).resolve().parents[1]
    selected = runner.select_inventory(runner.discover_inventory(root), "robinhood")
    assert "tests/review_paper/test_successor_publication_recovery.py" in selected
    current = selected
    selected = tuple(
        m
        for m in selected
        if m
        not in {
            "tests/experiments/test_historical_research_dataset.py",
            "tests/review_paper/test_successor_publication_recovery.py",
            "tests/review_paper/test_arch134_f1r1_d1s4_rename_free_direct_installation.py",
            "tests/review_paper/test_arch134_f1r1_d1s4_r1_shared_namespace_acl_recovery.py",
        }
    )
    weights = runner.robinhood_module_weights(selected)
    assert len(selected) == len(runner.ROBINHOOD_MODULE_TIMINGS_MS) == 109
    assert set(weights) == set(selected)
    assert runner.ROBINHOOD_FALLBACK_MS == 1000
    assert (
        hashlib.sha256(
            json.dumps(weights, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == "0c0c79f710ab8b3a9ffc08de4720c026f257e2ffefc8dc6989c3a70fba2d2898"
    )
    lanes = runner.balance_robinhood(tuple(reversed(selected)))
    assert tuple(map(len, lanes)) == (27, 30, 26, 26)
    assert tuple(sum(weights[module] for module in lane) for lane in lanes) == (
        214237,
        214237,
        214240,
        214236,
    )
    assert tuple(_ordered_lane_hash(lane) for lane in lanes) == (
        "cc0a6556faf54386fe4e8c0a192ac0ad6543da814d5926e86f7c8bc867470a51",
        "904166863dfa5354fad29773877c70eb991ba240b3f117ccb163766f8fc71198",
        "a5620743bd21fbb59d16f0994290e2908bfeeba71bfc3a15bed0fb2cadb42aa3",
        "e51754fe142e84fac06f2a27184aa948f1a2de73f5868f6fef45f3d174a62b45",
    )
    assert "tests/domain/test_positions.py" in lanes[0]
    assert "tests/review_paper/test_d1_session_execution.py" in lanes[0]
    assert runner.build_lanes(root, selected, "robinhood") == {
        f"robinhood-{index}": lane for index, lane in enumerate(lanes, start=1)
    }
    runner.validate_partitions(selected, lanes)

    direct = (
        "tests/review_paper/test_arch134_f1r1_d1s4_rename_free_direct_installation.py"
    )
    assert direct in current
    assert (
        runner.robinhood_module_weights(current)[direct] == runner.ROBINHOOD_FALLBACK_MS
    )
    recovery = (
        "tests/review_paper/test_arch134_f1r1_d1s4_r1_shared_namespace_acl_recovery.py"
    )
    assert recovery in current
    assert (
        runner.robinhood_module_weights(current)[recovery]
        == runner.ROBINHOOD_FALLBACK_MS
    )
    current_lanes = runner.build_lanes(root, current, "robinhood")
    runner.validate_partitions(current, tuple(current_lanes.values()))
    assert (
        runner.robinhood_module_weights(current)[
            "tests/review_paper/test_successor_publication_recovery.py"
        ]
        == runner.ROBINHOOD_FALLBACK_MS
    )


def test_robinhood_r3k_normalizes_only_raw_zero_to_positive_minimum() -> None:
    raw = dict(runner.ROBINHOOD_MODULE_TIMINGS_MS)
    raw["tests/domain/test_positions.py"] = 0
    assert sum(raw.values()) == 856949
    assert [module for module, value in raw.items() if value == 0] == [
        "tests/domain/test_positions.py"
    ]
    normalized = {module: max(1, value) for module, value in raw.items()}
    assert normalized == dict(runner.ROBINHOOD_MODULE_TIMINGS_MS)
    assert sum(normalized.values()) == 856950
    assert all(value > 0 for value in normalized.values())


def test_robinhood_reversed_inventory_and_fixture_byte_size_cannot_change_lanes(
    tmp_path: Path,
) -> None:
    root = Path(runner.__file__).resolve().parents[1]
    selected = runner.select_inventory(runner.discover_inventory(root), "robinhood")
    fixture = (
        tmp_path
        / "tests/review_paper/test_arch134_f1r1_d1s3_successor_installation_operator.py"
    )
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_bytes(b"x")
    before = runner.build_lanes(tmp_path, selected, "robinhood")
    fixture.write_bytes(b"changed fixture bytes " * 10000)
    after = runner.build_lanes(tmp_path, tuple(reversed(selected)), "robinhood")
    assert before == after


def test_robinhood_future_module_uses_fallback_and_remains_covered() -> None:
    root = Path(runner.__file__).resolve().parents[1]
    current = runner.select_inventory(runner.discover_inventory(root), "robinhood")
    future = "tests/review_paper/test_future_supported.py"
    selected = tuple(sorted((*current, future)))
    weights = runner.robinhood_module_weights(selected)
    assert weights[future] == 1000
    lanes = runner.balance_robinhood(selected)
    runner.validate_partitions(selected, lanes)
    assert sum(future in lane for lane in lanes) == 1


@pytest.mark.parametrize("value", [True, False, -1, 1.0, "1", None, [], {}])
def test_robinhood_invalid_timing_values_fail_closed(monkeypatch, value) -> None:
    module = "tests/domain/test_market.py"
    monkeypatch.setattr(runner, "ROBINHOOD_MODULE_TIMINGS_MS", ((module, value),))
    with pytest.raises(runner.CertificationError, match="positive integers"):
        runner.balance_robinhood((module,))


def test_robinhood_zero_timing_value_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        runner,
        "ROBINHOOD_MODULE_TIMINGS_MS",
        (("tests/domain/test_market.py", 0),),
    )
    with pytest.raises(runner.CertificationError, match="positive integers"):
        runner.balance_robinhood(("tests/domain/test_market.py",))


@pytest.mark.parametrize(
    "table",
    [
        None,
        {},
        (("tests/domain/test_market.py",),),
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
def test_robinhood_malformed_duplicate_timing_tables_fail_closed(monkeypatch, table):
    monkeypatch.setattr(runner, "ROBINHOOD_MODULE_TIMINGS_MS", table)
    with pytest.raises(runner.CertificationError):
        runner.robinhood_module_weights(("tests/domain/test_market.py",))


def test_robinhood_stale_timing_module_fails_before_children(monkeypatch) -> None:
    monkeypatch.setattr(
        runner,
        "ROBINHOOD_MODULE_TIMINGS_MS",
        (("tests/domain/test_removed.py", 1),),
    )
    with pytest.raises(
        runner.CertificationError, match="Stale ROBINHOOD timing module"
    ):
        runner.build_lanes(Path("."), ("tests/domain/test_market.py",), "robinhood")


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


def test_full_six_lane_current_local_model_is_exact_and_repeatable() -> None:
    root = Path(runner.__file__).resolve().parents[1]
    inventory = runner.select_inventory(runner.discover_inventory(root), "full")
    assert "tests/review_paper/test_successor_publication_recovery.py" in inventory
    current = inventory
    inventory = tuple(
        m
        for m in inventory
        if m
        not in {
            "tests/review_paper/test_successor_publication_recovery.py",
            "tests/review_paper/test_arch134_f1r1_d1s4_rename_free_direct_installation.py",
            "tests/review_paper/test_arch134_f1r1_d1s4_r1_shared_namespace_acl_recovery.py",
        }
    )
    weights = runner.full_module_weights(inventory)
    assert len(inventory) == len(runner.FULL_MODULE_TIMINGS_MS) == 198
    assert set(weights) == {module for module, _ in runner.FULL_MODULE_TIMINGS_MS}
    assert runner.FULL_FALLBACK_MS == 1000
    assert sum(weights.values()) == 1231440
    assert (
        hashlib.sha256(
            json.dumps(weights, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == "65e9c1cc30d09d33db08f70c93be354ef5d3746ea45ef460467848f9f42998f9"
    )
    lanes = runner.build_lanes(root, inventory, "full")
    assert tuple(lanes) == tuple(f"broad-{index}" for index in range(1, 7))
    assert all(lanes.values()) and "serial" not in lanes
    assert lanes == runner.build_lanes(root, tuple(reversed(inventory)), "full")
    runner.validate_partitions(inventory, tuple(lanes.values()))
    assert tuple(map(len, lanes.values())) == (32, 32, 33, 33, 34, 34)
    totals = tuple(sum(weights[module] for module in lane) for lane in lanes.values())
    assert totals == (205240,) * 6
    assert tuple(_ordered_lane_hash(lane) for lane in lanes.values()) == (
        "b86fdc382015ef5845e761a6c671f8a9cd27c195ac37e900b2c709b41f68fd37",
        "40730d6b3d85600efdf972b84f5335e88d93b97915f6f6e9922bdf291176b64e",
        "a1da558ff6aee18e08a3e949f331e8743e0c02897d621107ad3d5f92237e454f",
        "3791a2a803e6a9c48cb41133a4f1568ed78a201a29aa536f547eb1d19edad0ef",
        "dc0fd920b76c118293b943065b4be59d804b7fc6da8bca8919b0725cc9aaeb57",
        "e5364bb6b084ae092926a3bc480b43a5c5c40ca0a9e5909b16d85e02fa0b4f6f",
    )
    assert max(totals) + 81674 == 286914 < 300000
    # Only this module measured zero in the preserved R4 FULL XML.
    assert weights["tests/domain/test_proposals.py"] == 1
    raw = dict(weights, **{"tests/domain/test_proposals.py": 0})
    assert sum(raw.values()) == 1231439
    assert [module for module, ms in raw.items() if ms == 0] == [
        "tests/domain/test_proposals.py"
    ]
    assert {module: max(1, ms) for module, ms in raw.items()} == weights

    current_lanes = runner.build_lanes(root, current, "full")
    runner.validate_partitions(current, tuple(current_lanes.values()))
    assert (
        runner.full_module_weights(current)[
            "tests/review_paper/test_successor_publication_recovery.py"
        ]
        == runner.FULL_FALLBACK_MS
    )


def test_full_fixture_byte_size_cannot_change_six_lane_placement(tmp_path) -> None:
    root = Path(runner.__file__).resolve().parents[1]
    selected = runner.select_inventory(runner.discover_inventory(root), "full")
    fixture = tmp_path / selected[0]
    fixture.parent.mkdir(parents=True)
    fixture.write_bytes(b"x")
    before = runner.build_lanes(tmp_path, selected, "full")
    fixture.write_bytes(b"changed fixture bytes " * 10000)
    assert before == runner.build_lanes(tmp_path, tuple(reversed(selected)), "full")


@pytest.mark.parametrize("value", [True, False, 0, -1, 1.0, "1", None])
def test_full_fallback_must_be_positive_integer(monkeypatch, value) -> None:
    monkeypatch.setattr(runner, "FULL_FALLBACK_MS", value)
    monkeypatch.setattr(runner, "FULL_MODULE_TIMINGS_MS", ())
    with pytest.raises(runner.CertificationError, match="fallback"):
        runner.full_module_weights(("tests/domain/test_future.py",))


def test_full_duplicate_inventory_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(runner, "FULL_MODULE_TIMINGS_MS", ())
    with pytest.raises(runner.CertificationError, match="Duplicate FULL"):
        runner.balance_full(("tests/domain/test_future.py",) * 2)


def test_full_fixture_matches_frozen_timing_membership() -> None:
    assert set(_fixture_profiles()["full"]) == {
        module for module, _ in runner.FULL_MODULE_TIMINGS_MS
    }


def test_full_path_and_lane_ties_and_future_supported_fallback(monkeypatch) -> None:
    original = runner.FULL_MODULE_TIMINGS_MS
    modules = tuple(f"tests/domain/test_{letter}.py" for letter in "abcdefgh")
    monkeypatch.setattr(runner, "FULL_MODULE_TIMINGS_MS", ((modules[1], 1000),))
    assert runner.full_module_weights(modules) == dict.fromkeys(modules, 1000)
    expected = (
        (modules[0], modules[6]),
        (modules[1], modules[7]),
        (modules[2],),
        (modules[3],),
        (modules[4],),
        (modules[5],),
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
    lanes = runner.balance_full(selected)
    runner.validate_partitions(selected, lanes)
    assert sum(future in lane for lane in lanes) == 1


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
        expected_current = checkpoint.ARCH134_D1S3_SHARED_SUCCESSOR_PINS.get(module)
        if expected_current is None:
            expected_current = checkpoint.ARCH134_D1S2_SUCCESSOR_PINS.get(module)
        if expected_current is None:
            expected_current = checkpoint._arch144_current_inventory_test_pin(
                module, pin
            )
        expected_current = checkpoint._arch132_r3j_current_shared_successor_pin(
            module, expected_current
        )
        expected_current = checkpoint._arch132_r3k_current_shared_successor_pin(
            module, expected_current
        )
        expected_current = checkpoint._arch132_r3l_current_shared_successor_pin(
            module, expected_current
        )
        assert checkpoint._git_blob_sha1(
            root / module
        ) == checkpoint._arch134_r5_blob_pin(module, expected_current)
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
        expected_current = checkpoint.ARCH134_D1S3_SHARED_SUCCESSOR_PINS.get(module)
        if expected_current is None:
            expected_current = checkpoint.ARCH134_D1S2_SUCCESSOR_PINS.get(module)
        if expected_current is None:
            expected_current = checkpoint._arch134_f1_current_inventory_test_pin(
                module, pin
            )
        expected_current = checkpoint._arch132_r3j_current_shared_successor_pin(
            module, expected_current
        )
        expected_current = checkpoint._arch132_r3k_current_shared_successor_pin(
            module, expected_current
        )
        expected_current = checkpoint._arch132_r3l_current_shared_successor_pin(
            module, expected_current
        )
        assert checkpoint._git_blob_sha1(
            root / module
        ) == checkpoint._arch134_r5_blob_pin(module, expected_current)
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


def test_r3j_successor_overlay_is_exact_and_intentionally_unmapped() -> None:
    from scripts import checkpoint_runner as checkpoint

    root = Path(checkpoint.__file__).resolve().parents[1]
    expected = {
        "scripts/run_test_certification.py": "7cff6bb635c0faf0eb30edfb298170490d8f523e",
        "tests/scripts/certification_runner/test_lanes.py": (
            "6de60ef0b897e1688d9245dcbc35e8696a9b6249"
        ),
        "tests/scripts/certification_runner/test_profiles.py": (
            "5c2cb07adca1b3fda437a77b2cf355b325006794"
        ),
    }
    assert checkpoint.ARCH132_R3J_CURRENT_SHARED_SUCCESSOR_PINS == expected
    assert (
        hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest()
        == checkpoint.ARCH132_R3J_CURRENT_SHARED_SUCCESSOR_PINS_SHA256
    )
    for relative, successor in expected.items():
        predecessor = checkpoint.ARCH134_D1S3_SHARED_SUCCESSOR_PINS[relative]
        assert (
            checkpoint._arch132_r3j_current_shared_successor_pin(relative, predecessor)
            == successor
        )
        with pytest.raises(ValueError, match="R3J"):
            checkpoint._arch132_r3j_current_shared_successor_pin(relative, "a" * 40)
    assert checkpoint.ARCH132_R3J_RUNNER_AST_PINS
    assert (
        checkpoint.resolve_ci_checkpoint(
            checkpoint._checkpoint_specs(),
            "feature/test-suite-arch132-r3j-robinhood-timing-hygiene-current",
            "push",
        )
        is None
    )
    assert (
        "feature/test-suite-arch132-r3j-robinhood-timing-hygiene-current"
        not in checkpoint.ACTIVE_CI_CHECKPOINTS
    )
    assert checkpoint.resolve_ci_certification_profile(None) is None
    assert checkpoint._arch134_d1s3_authority_check(root) == ()


def test_r3k_successor_overlay_is_exact_and_intentionally_unmapped() -> None:
    from scripts import checkpoint_runner as checkpoint

    root = Path(checkpoint.__file__).resolve().parents[1]
    expected = {
        "scripts/run_test_certification.py": (
            "a6b3857f832af47fccaf3c13203ecae1c813a22e"
        ),
        "tests/scripts/certification_runner/helpers.py": (
            "c3298836d98c1848c3603b8c8d952ea1cfb5e307"
        ),
        "tests/scripts/certification_runner/test_profiles.py": (
            "5259e9e39f7ba4a15431f51eb0e237a32bad4693"
        ),
    }
    predecessors = {
        "scripts/run_test_certification.py": (
            "7cff6bb635c0faf0eb30edfb298170490d8f523e"
        ),
        "tests/scripts/certification_runner/helpers.py": (
            "8936dedd1ba334558aff97724db8221a0fe3480e"
        ),
        "tests/scripts/certification_runner/test_profiles.py": (
            "5c2cb07adca1b3fda437a77b2cf355b325006794"
        ),
    }
    actual = checkpoint.ARCH132_R3K_CURRENT_SHARED_SUCCESSOR_PINS
    assert set(actual) == {
        *expected,
        "tests/scripts/certification_runner/test_lanes.py",
    }
    assert {key: value for key, value in actual.items() if key in expected} == expected
    assert len(actual["tests/scripts/certification_runner/test_lanes.py"]) == 40
    assert (
        hashlib.sha256(json.dumps(actual, sort_keys=True).encode()).hexdigest()
        == checkpoint.ARCH132_R3K_CURRENT_SHARED_SUCCESSOR_PINS_SHA256
    )
    for relative, successor in expected.items():
        assert (
            checkpoint._arch132_r3k_current_shared_successor_pin(
                relative, predecessors[relative]
            )
            == successor
        )
        with pytest.raises(ValueError, match="R3K"):
            checkpoint._arch132_r3k_current_shared_successor_pin(relative, "a" * 40)
    assert checkpoint.ARCH132_R3K_RUNNER_AST_PINS
    assert (
        checkpoint.resolve_ci_checkpoint(
            checkpoint._checkpoint_specs(),
            "feature/test-suite-arch132-r3k-robinhood-four-lane-hygiene-current",
            "push",
        )
        is None
    )
    assert (
        "feature/test-suite-arch132-r3k-robinhood-four-lane-hygiene-current"
        not in checkpoint.ACTIVE_CI_CHECKPOINTS
    )
    assert checkpoint.resolve_ci_certification_profile(None) is None
    assert checkpoint._arch134_d1s3_authority_check(root) == ()


def test_robinhood_historical_pin_constants_are_exact_but_inactive() -> None:
    root = Path(runner.__file__).resolve().parents[1]
    selected = runner.select_inventory(runner.discover_inventory(root), "robinhood")
    assert runner.ROBINHOOD_LANE_PINS == {
        "tests/runtime/checkpoint_runner/test_arch131.py": 0,
        "tests/runtime/checkpoint_runner/test_arch133_h_k.py": 0,
        "tests/runtime/checkpoint_runner/test_arch133_l_m.py": 1,
        "tests/review_paper/test_arch133_scheduler_installation.py": 1,
    }
    lanes = runner.build_lanes(root, selected, "robinhood")
    assert runner.ROBINHOOD_F1_LANE_PINS == {
        "tests/review_paper/test_five_session_soak.py": 0
    }
    assert runner.ROBINHOOD_F1R1_B_LANE_PINS == {
        "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py": 0
    }
    assert runner.ROBINHOOD_D1S3_LANE_PINS == {
        "tests/review_paper/test_d1_session_execution.py": 0
    }
    # These reviewed historical targets differ from the R3K timing model,
    # proving build_lanes no longer applies any byte-size-era overlay.
    assert (
        "tests/review_paper/test_arch133_scheduler_installation.py"
        in lanes["robinhood-4"]
    )
    assert "tests/review_paper/test_d1_session_execution.py" in lanes["robinhood-1"]


def test_r3l_successor_overlay_is_exact_and_intentionally_unmapped(monkeypatch):
    from scripts import checkpoint_runner as checkpoint

    root = Path(checkpoint.__file__).resolve().parents[1]
    pins = checkpoint.ARCH132_R3L_CURRENT_SHARED_SUCCESSOR_PINS
    assert set(pins) == {
        "scripts/run_test_certification.py",
        "tests/scripts/certification_runner/helpers.py",
        "tests/scripts/certification_runner/test_lanes.py",
    }
    assert (
        hashlib.sha256(json.dumps(pins, sort_keys=True).encode()).hexdigest()
        == checkpoint.ARCH132_R3L_CURRENT_SHARED_SUCCESSOR_PINS_SHA256
    )
    for relative, successor in pins.items():
        predecessor = checkpoint.ARCH132_R3K_CURRENT_SHARED_SUCCESSOR_PINS[relative]
        assert checkpoint._git_blob_sha1(
            root / relative
        ) == checkpoint._arch134_r5_blob_pin(relative, successor)
        assert (
            checkpoint._arch132_r3l_current_shared_successor_pin(relative, predecessor)
            == successor
        )
        with pytest.raises(ValueError, match="R3L"):
            checkpoint._arch132_r3l_current_shared_successor_pin(relative, "a" * 40)
    assert (
        checkpoint._arch132_r3l_current_shared_successor_pin("other", "unchanged")
        == "unchanged"
    )
    branch = "feature/test-suite-arch132-r3l-full-six-lane-hygiene-current"
    assert branch not in checkpoint.ACTIVE_CI_CHECKPOINTS
    assert (
        checkpoint.resolve_ci_checkpoint(checkpoint._checkpoint_specs(), branch, "push")
        is None
    )
    assert checkpoint.resolve_ci_certification_profile(None) is None
    assert checkpoint._arch134_d1s3_authority_check(root) == ()
    monkeypatch.setattr(checkpoint, "ARCH132_R3L_CURRENT_SHARED_SUCCESSOR_PINS", {})
    with pytest.raises(ValueError, match="R3L"):
        checkpoint._arch132_r3l_current_shared_successor_pin("other", "unchanged")
    assert checkpoint._arch134_d1s3_authority_check(root)


def test_r3l_preserves_r4_product_and_predecessor_topology_contracts() -> None:
    import ast
    import subprocess

    from scripts import checkpoint_runner as checkpoint

    root = Path(runner.__file__).resolve().parents[1]
    base = "e515f2d4b8f75ee04b95f7e89162e37c7890e0a4"

    def frozen_nodes(text):
        return {
            node.name
            if isinstance(node, ast.FunctionDef)
            else node.target.id: ast.dump(node, include_attributes=False)
            for node in ast.parse(text).body
            if isinstance(node, ast.FunctionDef)
            or (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name))
        }

    # The installation operator remains frozen from accepted R4.  The native
    # read adapter is the deliberately changed D1S3 source in this correction.
    for relative in (
        "src/trading_bot/supervised_release/successor_installation_operator.py",
    ):
        before = subprocess.run(
            ["git", "show", f"{base}:{relative}"],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
        assert (root / relative).read_bytes().replace(b"\r\n", b"\n") == before
    before_runner = subprocess.run(
        ["git", "show", f"{base}:scripts/run_test_certification.py"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    before_nodes = frozen_nodes(before_runner)
    after_nodes = frozen_nodes(Path(runner.__file__).read_text())
    for name in (
        "robinhood_module_weights",
        "balance_robinhood",
        "balance_broad",
        "separate_serial",
        "classify_inventory",
        "build_lanes",
    ):
        assert after_nodes[name] == before_nodes[name]
    before_checkpoint = subprocess.run(
        ["git", "show", f"{base}:scripts/checkpoint_runner.py"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    before_nodes = frozen_nodes(before_checkpoint)
    after_nodes = frozen_nodes(Path(checkpoint.__file__).read_text())
    intentionally_updated = {
        "ARCH132_R3L_CURRENT_SHARED_SUCCESSOR_PINS",
        "ARCH132_R3L_CURRENT_SHARED_SUCCESSOR_PINS_SHA256",
        "ARCH134_D1S3_SOURCE_PINS",
        "ARCH134_D1S3_SOURCE_PINS_SHA256",
    }
    for name, node in before_nodes.items():
        if (
            name.startswith(("ARCH132_R3J_", "ARCH132_R3K_", "ARCH134_D1S3_"))
            and name not in intentionally_updated
        ):
            assert after_nodes[name] == node
