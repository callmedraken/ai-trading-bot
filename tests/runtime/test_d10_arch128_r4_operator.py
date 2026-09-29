from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pytest
from scripts.d10_protected_deployment import DeploymentBlocked

from scripts import d10_arch128_r4_operator as operator
from scripts import d10_arch128_r4_replacement as r4


def _admission():
    from scripts import d10_arch128_r4_orchestration as r4c

    native = object()
    return r4c.AdmissionObservation(
        r4.NamespaceObservation(
            r4.RootObservation(r4.CANONICAL_PATH, True, r4.OLD_IDENTITY),
            r4.RootObservation(r4.STAGING_PATH, True, r4.NEW_IDENTITY),
            r4.RootObservation(r4.RETIRED_PATH, False),
            True,
            True,
        ),
        r4.AdmissionFacts(*([True] * len(fields(r4.AdmissionFacts)))),
        native,
        native,
        native,
        (("enabled", False), ("task_state", 1), ("xml_sha256", "x")),
    )


class _FakeAttestation:
    deployment_id = r4.NEW_DEPLOYMENT_ID


class _FakeManifest:
    digest = r4.NEW_IDENTITY.manifest_sha256


class _FakeMaterial:
    attestation = _FakeAttestation()
    manifest = _FakeManifest()


class _FakeSigned:
    material = _FakeMaterial()


def test_read_only_preflight_never_constructs_writer_or_rename(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admission = _admission()

    monkeypatch.setattr(operator, "WindowsCngVerifier", lambda: object())
    monkeypatch.setattr(
        operator.r4c,
        "load_fixed_signed_material",
        lambda verifier: _FakeSigned(),
    )
    monkeypatch.setattr(
        operator.r4w,
        "WindowsArch128ReadOnlyReader",
        lambda: object(),
    )
    monkeypatch.setattr(
        operator.r4c,
        "observe_pre_stage",
        lambda *args: type(
            "Pre",
            (),
            {"scheduler": admission.scheduler},
        )(),
    )
    monkeypatch.setattr(
        operator.r4w,
        "WindowsArch128StagingBackend",
        lambda: (_ for _ in ()).throw(AssertionError("writer constructed")),
    )
    monkeypatch.setattr(
        operator.r4w,
        "rename_fixed_step",
        lambda *args: (_ for _ in ()).throw(AssertionError("rename called")),
    )

    result = operator._dispatch((operator.READ_ONLY_FLAG,), {})
    assert result["status"] == "PASS"
    assert result["production_filesystem_mutation"] == "NOT_RUN"
    assert result["rename_1"] == "NOT_RUN"
    assert result["rename_2"] == "NOT_RUN"


def test_execute_interlock_blocks_before_components(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        operator,
        "WindowsCngVerifier",
        lambda: (_ for _ in ()).throw(AssertionError("component constructed")),
    )

    result = operator._dispatch((operator.EXECUTE_FLAG,), {})
    assert result["status"] == "BLOCKED"
    assert result["production_filesystem_mutation"] == "NOT_RUN"


def test_unknown_arguments_are_non_mutating() -> None:
    result = operator._dispatch(("--wrong",), {})
    assert result["status"] == "BLOCKED"
    assert result["mode"] == "INTERLOCK"
    assert result["production_filesystem_mutation"] == "NOT_RUN"


def test_execute_happy_path_binds_fixed_components(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admission = _admission()
    calls: list[str] = []

    monkeypatch.setattr(operator, "WindowsCngVerifier", lambda: object())
    monkeypatch.setattr(
        operator.r4c,
        "load_fixed_signed_material",
        lambda verifier: _FakeSigned(),
    )
    monkeypatch.setattr(
        operator.r4w,
        "WindowsArch128ReadOnlyReader",
        lambda: object(),
    )
    monkeypatch.setattr(
        operator.r4w,
        "WindowsArch128StagingBackend",
        lambda: object(),
    )

    def construct(*args):
        calls.append("staging")
        return admission

    monkeypatch.setattr(operator.r4c, "_construct_staging", construct)

    class Session:
        def __init__(self, *args) -> None:
            calls.append("session")

        def retire_old(self):
            calls.append("retire")
            return r4.ReplacementResult(
                r4.Phase.READY_TO_PUBLISH_NEW,
                r4.MutationOutcome.SUCCESS,
                r4.MutationOutcome.NOT_CALLED,
            )

        def publish_new(self):
            calls.append("publish")
            return r4.ReplacementResult(
                r4.Phase.COMPLETE,
                r4.MutationOutcome.SUCCESS,
                r4.MutationOutcome.SUCCESS,
            )

    monkeypatch.setattr(operator.r4c, "_ReplacementSession", Session)

    result = operator._dispatch(
        (operator.EXECUTE_FLAG,),
        {operator.AUTH_ENV: operator.AUTH_VALUE},
    )
    assert result["status"] == "PASS"
    assert result["production_filesystem_mutation"] == (
        "REPLACEMENT_COMPLETE_AND_VERIFIED"
    )
    assert calls == ["staging", "session", "retire", "publish"]


def test_staging_failure_is_single_attempt_without_cleanup_or_rename(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    monkeypatch.setattr(operator, "WindowsCngVerifier", lambda: object())
    monkeypatch.setattr(
        operator.r4c,
        "load_fixed_signed_material",
        lambda verifier: _FakeSigned(),
    )
    monkeypatch.setattr(
        operator.r4w,
        "WindowsArch128ReadOnlyReader",
        lambda: object(),
    )
    monkeypatch.setattr(
        operator.r4w,
        "WindowsArch128StagingBackend",
        lambda: object(),
    )

    def fail_staging(*args):
        calls.append("staging")
        raise DeploymentBlocked("partial")

    monkeypatch.setattr(operator.r4c, "_construct_staging", fail_staging)
    monkeypatch.setattr(
        operator.r4c,
        "_ReplacementSession",
        lambda *args: (_ for _ in ()).throw(AssertionError("session constructed")),
    )

    result = operator._dispatch(
        (operator.EXECUTE_FLAG,),
        {operator.AUTH_ENV: operator.AUTH_VALUE},
    )
    assert result["status"] == "STOPPED"
    assert result["production_filesystem_mutation"] == "POSSIBLE_PARTIAL_STAGING"
    assert calls == ["staging"]


def test_first_rename_stop_never_attempts_second(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admission = _admission()
    calls: list[str] = []

    monkeypatch.setattr(operator, "WindowsCngVerifier", lambda: object())
    monkeypatch.setattr(
        operator.r4c,
        "load_fixed_signed_material",
        lambda verifier: _FakeSigned(),
    )
    monkeypatch.setattr(
        operator.r4w,
        "WindowsArch128ReadOnlyReader",
        lambda: object(),
    )
    monkeypatch.setattr(
        operator.r4w,
        "WindowsArch128StagingBackend",
        lambda: object(),
    )
    monkeypatch.setattr(operator.r4c, "_construct_staging", lambda *args: admission)

    class Session:
        def __init__(self, *args) -> None:
            pass

        def retire_old(self):
            calls.append("retire")
            return r4.ReplacementResult(
                r4.Phase.STOPPED_INDETERMINATE,
                r4.MutationOutcome.INDETERMINATE,
                r4.MutationOutcome.NOT_CALLED,
            )

        def publish_new(self):
            calls.append("publish")
            raise AssertionError("second rename attempted")

    monkeypatch.setattr(operator.r4c, "_ReplacementSession", Session)

    result = operator._dispatch(
        (operator.EXECUTE_FLAG,),
        {operator.AUTH_ENV: operator.AUTH_VALUE},
    )
    assert result["status"] == "STOPPED_INDETERMINATE"
    assert calls == ["retire"]
    assert result["rename_2"] == r4.MutationOutcome.NOT_CALLED.value


def test_operator_has_no_scheduler_activation_or_trading_mutator() -> None:
    source = Path(operator.__file__).read_text(encoding="utf-8")

    for forbidden in (
        "RegisterTask",
        "RegisterTaskDefinition",
        "DeleteTask",
        ".Run(",
        "Start-ScheduledTask",
        "Enable-ScheduledTask",
        "WindowsActivationLeaseBackend",
        "publish_activation",
        "provider.",
        "paper_v2",
        "broker.",
        "live_order",
        "delete(",
        "rmtree",
        "unlink(",
        "os.rename",
    ):
        assert forbidden not in source

    assert "WindowsArch128StagingBackend()" in source
    assert "WindowsArch128ReadOnlyReader()" in source
    assert "r4w.rename_fixed_step" in source
    assert "r3._observe_scheduler" in source
    assert operator.AUTH_VALUE in source
