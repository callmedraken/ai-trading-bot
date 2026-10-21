"""Focused, disposable proof for Architecture 134-F1R1-A."""

import ast
import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from scripts import checkpoint_runner as runner
from trading_bot.strategies import MovingAverageCrossoverConfig
from trading_bot.supervised_release import (
    LAUNCHER_RELATIVE_PATH,
    STRATEGY_ID,
    STRATEGY_VERSION,
    ReleaseInventoryEntry,
    ReleaseManifest,
)
from trading_bot.supervised_release.runtime_isolation import (
    DiagnosticEvidence,
    DiagnosticReason,
    DurableStoreIdentity,
    EffectConsumedError,
    EffectOperation,
    EffectStage,
    EffectStatus,
    InstalledRuntimeMaterial,
    LifecycleEvent,
    LifecycleRecorder,
    LifecycleStatus,
    ProductionOperatorState,
    RuntimeAdmissionStatus,
    admit_installed_runtime,
    build_pin_successor_overlay,
    production_manual_start,
    production_state_after_boot_or_login,
    resolve_pin_successor,
    run_durable_effect,
)

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_SOURCE = ROOT / "src/trading_bot/supervised_release/runtime_isolation.py"


def _manifest(**changes: object) -> ReleaseManifest:
    material: dict[str, object] = {
        "source_head": "a" * 40,
        "source_tree": "b" * 40,
        "production_python_version": "3.14.3",
        "production_python_sha256": "c" * 64,
        "launcher_relative_path": LAUNCHER_RELATIVE_PATH,
        "launcher_sha256": "d" * 64,
        "source_inventory": (
            ReleaseInventoryEntry(LAUNCHER_RELATIVE_PATH, "d" * 64),
            ReleaseInventoryEntry(
                "src/trading_bot/strategies/moving_average.py", "e" * 64
            ),
            ReleaseInventoryEntry("pyproject.toml", "f" * 64),
        ),
        "strategy_id": STRATEGY_ID,
        "strategy_version": STRATEGY_VERSION,
        "strategy_config": MovingAverageCrossoverConfig(5, 20, Decimal("1.00")),
        "risk_policy_id": "long-only-reviewed-policy",
        "risk_policy_version": "1.0.0",
        "risk_policy_sha256": "1" * 64,
    }
    return ReleaseManifest(**(material | changes))


def _material() -> InstalledRuntimeMaterial:
    return InstalledRuntimeMaterial.from_manifest(
        _manifest(),
        binding_sha256="2" * 64,
        durable_store_identities=(DurableStoreIdentity("paper-state", "3" * 64),),
    )


class _Journal:
    def __init__(self) -> None:
        self._records = ()

    def records(self):
        return self._records

    def append(self, record):
        self._records = (*self._records, record)


def test_repeated_admission_uses_only_immutable_local_material(monkeypatch):
    material = _material()
    monkeypatch.chdir(ROOT)
    first = admit_installed_runtime(material)
    monkeypatch.chdir(ROOT / "tests")
    second = admit_installed_runtime(material)

    assert first.status is RuntimeAdmissionStatus.ADMITTED
    assert second == first
    assert first.proof is not None
    assert first.proof.runtime_id == material.runtime_id


def test_mutable_development_changes_do_not_change_admitted_material():
    material = _material()
    development_variant = replace(
        _manifest(), source_head="f" * 40, source_tree="e" * 40
    )

    assert material.runtime_id == _material().runtime_id
    assert (
        material.runtime_id
        != InstalledRuntimeMaterial.from_manifest(
            development_variant,
            binding_sha256="2" * 64,
            durable_store_identities=material.durable_store_identities,
        ).runtime_id
    )
    assert admit_installed_runtime(material).status is RuntimeAdmissionStatus.ADMITTED


def test_installed_runtime_has_no_live_git_or_development_helpers():
    tree = ast.parse(RUNTIME_SOURCE.read_text(encoding="utf-8"))
    imported = []
    called = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called.append(node.func.id.casefold())

    forbidden = ("git", "github", "subprocess", "credential", "provider", "broker")
    assert not any(
        any(word in module.casefold() for word in forbidden) for module in imported
    )
    assert not any(any(word in name for word in forbidden) for name in called)


def test_pre_entry_failure_persists_intent_without_entry_or_provider_call():
    journal = _Journal()
    calls = []
    result = run_durable_effect(
        journal=journal,
        operation=EffectOperation.QUOTE_REQUEST,
        pre_entry_guard=lambda: False,
        external_operation=lambda: calls.append("provider"),
    )

    assert result.status is EffectStatus.PRE_ENTRY_REJECTED
    assert [record.stage for record in result.records] == [
        EffectStage.INTENT,
        EffectStage.PRE_ENTRY_REJECTED,
    ]
    assert calls == []


def test_entry_admitted_is_durable_before_external_seam_and_failure_is_consumed():
    journal = _Journal()
    seen = []

    def external_operation():
        seen.append(tuple(record.stage for record in journal.records()))
        raise RuntimeError("raw provider failure must not be persisted")

    result = run_durable_effect(
        journal=journal,
        operation=EffectOperation.QUOTE_REQUEST,
        pre_entry_guard=lambda: True,
        external_operation=external_operation,
    )

    assert seen == [(EffectStage.INTENT, EffectStage.ENTRY_ADMITTED)]
    assert result.status is EffectStatus.AMBIGUOUS
    assert result.records[-1].stage is EffectStage.DIAGNOSTIC
    with pytest.raises(EffectConsumedError):
        run_durable_effect(
            journal=journal,
            operation=EffectOperation.QUOTE_REQUEST,
            pre_entry_guard=lambda: True,
            external_operation=lambda: None,
        )


def test_successful_external_operation_persists_acknowledgement():
    journal = _Journal()
    result = run_durable_effect(
        journal=journal,
        operation=EffectOperation.PAPER_MUTATION,
        pre_entry_guard=lambda: True,
        external_operation=lambda: None,
    )

    assert result.status is EffectStatus.ACKNOWLEDGED
    assert [record.stage for record in result.records] == [
        EffectStage.INTENT,
        EffectStage.ENTRY_ADMITTED,
        EffectStage.ACK,
    ]


def test_unknown_diagnostic_reason_and_raw_material_are_rejected():
    runtime_id = _material().runtime_id
    evidence = DiagnosticEvidence(
        runtime_id,
        1,
        DiagnosticReason.PROVIDER_ENTRY_FAILED,
        EffectOperation.QUOTE_REQUEST,
    )
    text = evidence.to_json()
    assert "secret-token" not in text
    assert "provider-payload" not in text
    assert "raw exception" not in text
    raw = json.loads(text)
    raw["reason"] = "UNKNOWN_REASON"
    with pytest.raises(ValueError):
        DiagnosticEvidence.from_json(
            json.dumps(raw, separators=(",", ":"), sort_keys=True)
        )
    raw = json.loads(text)
    raw["secret"] = "secret-token"
    with pytest.raises(ValueError):
        DiagnosticEvidence.from_json(
            json.dumps(raw, separators=(",", ":"), sort_keys=True)
        )


def test_lifecycle_evidence_is_bounded_replay_valid_and_marks_abrupt_exit():
    recorder = LifecycleRecorder(_material().runtime_id)
    for event in (
        LifecycleEvent.HOST_ENTERED,
        LifecycleEvent.SUPERVISOR_LOCK_ACQUIRED,
        LifecycleEvent.SUPERVISOR_LOOP_ENTERED,
        LifecycleEvent.SAFE_WAITING,
    ):
        recorder.append(event)
    evidence = recorder.snapshot()

    assert evidence.status is LifecycleStatus.ABRUPT_PROCESS_DISAPPEARANCE
    assert type(evidence.from_json(evidence.to_json())) is type(evidence)
    with pytest.raises(ValueError):
        recorder.append(LifecycleEvent.HOST_ENTERED)

    completed = LifecycleRecorder(_material().runtime_id)
    for event in (
        LifecycleEvent.HOST_ENTERED,
        LifecycleEvent.SUPERVISOR_LOCK_ACQUIRED,
        LifecycleEvent.SUPERVISOR_LOOP_ENTERED,
        LifecycleEvent.NORMAL_RETURN,
    ):
        completed.append(event)
    assert completed.snapshot().status is LifecycleStatus.NORMAL_RETURN


def test_runtime_isolation_exposes_no_effect_or_host_capability_imports():
    tree = ast.parse(RUNTIME_SOURCE.read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    )
    assert imported <= {
        "__future__",
        "hashlib",
        "json",
        "re",
        "collections.abc",
        "dataclasses",
        "enum",
        "typing",
        "trading_bot.supervised_release.model",
    }


def test_frozen_predecessor_digests_and_source_identity_remain_exact():
    assert runner.ARCH134_D1R7_PREDECESSOR_DIGESTS == {
        "ARCH134_D1R5_TEST_PIN_OVERRIDES": (
            "6a95f4afc8640dfa0c672f5d77cda06ae57171c0199128a3ddd1d8b0debaac4a"
        ),
        "ARCH134_D1R5_SOURCE_PINS": (
            "370e14ff9a9453b4e001278921c3d1084c6ff94c8e34be76d430cb2b2adae575"
        ),
        "ARCH134_D1R5_IMPORTS": (
            "1e00ebdb9916d624591ecf41818a458dabf545cb8654c5e93f1e4e6e35402f03"
        ),
        "ARCH140A18_CURRENT_INVENTORY_TEST_PIN_OVERRIDES": (
            "00a2195aca3ca844209f27437ebce3e179cc2060aaa8c334999180c7b5b4094f"
        ),
        "ARCH134_D1R6_TEST_PIN_OVERRIDES": (
            "dfe1999400e0a6fdea245ccdd7d77a62e49aa1a169dbd42c0f89e2e88868ef4b"
        ),
        "ARCH134_D1R6_PREDECESSOR_DIGESTS": (
            "f17583c1a1e519c001acb9d3751ec3c0cdcbe1974589580c1836e75c3ac2e3bf"
        ),
        "ARCH134_D1R6_ADDITIONAL_PREDECESSOR_PINS": (
            "572d83c4a3938678894c0cb9072c182373fbce4f596c4b66c26b51f07e2089ab"
        ),
        "ARCH134_D1R6_SOURCE_PINS": (
            "bbf14101519464b7cd4495e32b5b402a845befd89e2ef1e9a1597efb0e236425"
        ),
        "CANONICAL_CURRENT_INVENTORY_TEST_PIN_OVERRIDES": (
            "1e00670b28dfbad915c34ec4657143deb40a0b7932207c302f9ea87ab12c7d51"
        ),
    }
    assert runner.ARCH134_D1R8_PREDECESSOR_DIGESTS == {
        "ARCH134_ARMED_PAPER_RECOVERY_PIN_OVERRIDES": (
            "883a60d81edf1b71aa7daa376e6b8067e2833484254ba7bc1967c03b8fa587ba"
        ),
        "ARCH134_D1R5_SOURCE_PINS": (
            "370e14ff9a9453b4e001278921c3d1084c6ff94c8e34be76d430cb2b2adae575"
        ),
        "ARCH134_D1R6_SOURCE_PINS": (
            "bbf14101519464b7cd4495e32b5b402a845befd89e2ef1e9a1597efb0e236425"
        ),
        "ARCH134_D1R7_PREDECESSOR_DIGESTS": (
            "f65852b2a75e45d4637c2452b15ff8f2833c4a7f6ae1a1cea847b148dc50819f"
        ),
        "ARCH134_D1R7_PREDECESSOR_TEST_PINS": (
            "a07ac0ce7dbb1ae2ddab299f3839a778bd469b5e7aa3ff65f044942a7f895aaa"
        ),
        "ARCH134_D1R7_SOURCE_PINS": (
            "e194e364fb2278a8dfcaf789f5cc8c7d07b1785f4e68fa182f0982c93fa1274d"
        ),
        "ARCH134_D1R7_TEST_PIN_OVERRIDES": (
            "15925f6d9c6e3e9407ac8893b36be95a1eb53b5704430ac94ac5471c5bfabb37"
        ),
    }
    assert runner.ARCH145A_PREDECESSOR_SOURCE_PINS_SHA256 == (
        "d948d14649c0ae5a64ec4497e410ae59305fa6bd917ed1a907b9b8e91ccc2016"
    )
    assert runner.ARCH145A_PREDECESSOR_TEST_PINS_SHA256 == (
        "20216754a6bc04916e57a54b64236af5dd259cc539a6721462535d7b1ff32347"
    )


def test_successor_overlay_is_exact_and_fails_closed():
    predecessor = (("a.py", "a" * 40), ("b.py", "b" * 40))
    successor = (("a.py", "c" * 40), ("b.py", "d" * 40))
    overlay = build_pin_successor_overlay(predecessor, successor)

    assert resolve_pin_successor("a.py", predecessor, overlay, successor) == "c" * 40
    assert resolve_pin_successor("a.py", predecessor, None, None) == "a" * 40
    with pytest.raises(ValueError):
        build_pin_successor_overlay(predecessor, (("a.py", "c" * 40),))
    with pytest.raises(ValueError):
        build_pin_successor_overlay(
            predecessor, (("a.py", "c" * 40), ("c.py", "d" * 40))
        )
    with pytest.raises(ValueError):
        resolve_pin_successor(
            "a.py",
            (("a.py", "e" * 40), ("b.py", "b" * 40)),
            overlay,
            successor,
        )
    with pytest.raises(ValueError):
        resolve_pin_successor(
            "a.py",
            predecessor,
            overlay,
            (("a.py", "e" * 40), ("b.py", "d" * 40)),
        )


def test_production_reboot_stops_and_manual_start_requires_fresh_admission():
    material = _material()
    admitted = admit_installed_runtime(material)
    blocked = admit_installed_runtime(
        material, expected_runtime_id="runtime-" + "0" * 64
    )

    assert (
        production_state_after_boot_or_login(ProductionOperatorState.RUNNING)
        is ProductionOperatorState.STOPPED
    )
    assert (
        production_manual_start(ProductionOperatorState.STOPPED, admitted)
        is ProductionOperatorState.RUNNING
    )
    with pytest.raises(ValueError):
        production_manual_start(ProductionOperatorState.STOPPED, blocked)
    with pytest.raises(ValueError):
        production_manual_start(ProductionOperatorState.RUNNING, admitted)
