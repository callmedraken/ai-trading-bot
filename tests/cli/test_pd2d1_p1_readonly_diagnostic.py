"""Focused source-only coverage for the temporary PD2D1 P1 diagnostic."""

from __future__ import annotations

import ast
import ctypes
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

import trading_bot.cli.pd2d1_p1_readonly_diagnostic as diagnostic
from trading_bot.runtime.exceptions import (
    CheckpointedVerifiedSnapshotPaperCycleReconciliationError,
)

_HOSTILE = r"token=private F:\secret handle=0xDEADBEEF dynamic-class"
_PLAN_ID = UUID("11111111-1111-4111-8111-111111111111")
_REQUEST_ID = UUID("22222222-2222-4222-8222-222222222222")
_SESSION_ID = UUID("33333333-3333-4333-8333-333333333333")
_TERMINAL_ID = UUID("44444444-4444-4444-8444-444444444444")
_PLAN_SHA = "a" * 64
_PLAN_LENGTH = 321


class _Cycle:
    def __init__(
        self,
        calls: dict[str, object],
        evidence: object,
        *,
        enter_error: BaseException | None = None,
        release_error: Exception | None = None,
        return_self: bool = True,
    ) -> None:
        self.calls = calls
        self._evidence = evidence
        self.enter_error = enter_error
        self.release_error = release_error
        self.return_self = return_self

    def __enter__(self) -> object:
        self.calls["b1_enter"] = int(self.calls["b1_enter"]) + 1
        if self.enter_error is not None:
            raise self.enter_error
        self.calls["active"] = True
        return self if self.return_self else object()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        self.calls["b1_exit"] = int(self.calls["b1_exit"]) + 1
        assert self.calls["active"] is True
        assert (exc_type, exc, traceback) == (None, None, None)
        self.calls["active"] = False
        if self.release_error is not None:
            raise self.release_error
        return False

    def _active(self) -> None:
        assert self.calls["active"] is True

    @property
    def acquisition(self) -> object:
        self._active()
        return self.calls["acquisition"]

    @property
    def evidence(self) -> object:
        self._active()
        return self._evidence

    @property
    def operation_root(self) -> str:
        self._active()
        return str(self.calls["operation_root"])


def _evidence() -> SimpleNamespace:
    prior = SimpleNamespace(
        kind=diagnostic.VerifiedPriorCheckpointKind.GENESIS,
        checkpoint_id=diagnostic._EXPECTED_TERMINAL_CHECKPOINT_ID,
        sequence=0,
    )
    return SimpleNamespace(
        anchor=SimpleNamespace(paper_account_id=diagnostic._EXPECTED_PAPER_ACCOUNT_ID),
        prior_checkpoint=prior,
        lineage=SimpleNamespace(
            terminal_checkpoint_id=diagnostic._EXPECTED_TERMINAL_CHECKPOINT_ID
        ),
        successors=(),
        reports=(),
        snapshots=(),
        receipts=(),
    )


def _selected() -> SimpleNamespace:
    return SimpleNamespace(
        audit=SimpleNamespace(
            selection_id=diagnostic._EXPECTED_SELECTION_ID,
            session_id=_SESSION_ID,
            terminal_id=_TERMINAL_ID,
            snapshot_id=diagnostic._EXPECTED_SELECTED_SNAPSHOT_ID,
            artifact_sha256="b" * 64,
            artifact_byte_length=1291,
        ),
        verification=object(),
    )


def _inputs() -> SimpleNamespace:
    return SimpleNamespace(
        history_seed=SimpleNamespace(
            seed=SimpleNamespace(seed_id=diagnostic._EXPECTED_SEED_ID)
        ),
        strategy_config=object(),
        caller_idempotency_key=UUID("c762ad22-8d10-43d7-a38b-7d95e730c5ea"),
        open_reference=object(),
        policies=object(),
        planning_at=object(),
        submitted_at=object(),
        filled_at=object(),
    )


def _install_happy_path(
    monkeypatch: pytest.MonkeyPatch,
    *,
    cycle_factory: object | None = None,
) -> tuple[dict[str, object], object, object, object, _Cycle]:
    authority = SimpleNamespace(
        machine_authority_id=diagnostic._EXPECTED_MACHINE_AUTHORITY_ID,
        authority_epoch_id=diagnostic._EXPECTED_AUTHORITY_EPOCH_ID,
        approved_account_sid=diagnostic._EXPECTED_TRADING_SID,
    )
    selected = _selected()
    inputs = _inputs()
    evidence = _evidence()
    calls: dict[str, object] = {
        "acquire": 0,
        "active": False,
        "assertions": [],
        "b1_construct": [],
        "b1_enter": 0,
        "b1_exit": 0,
        "build": [],
        "calendar": [],
        "p2_construct": [],
        "p2_read": [],
        "prior": [],
        "requests": [],
        "verify": [],
        "operation_root": diagnostic._EXPECTED_OPERATION_ROOT,
        "acquisition": SimpleNamespace(
            state=diagnostic.PaperAccountMutexState.OWNED,
            paper_account_id=diagnostic._EXPECTED_PAPER_ACCOUNT_ID,
        ),
    }
    if cycle_factory is None:
        cycle = _Cycle(calls, evidence)
    else:
        assert callable(cycle_factory)
        cycle = cycle_factory(calls, evidence)

    monkeypatch.setattr(
        diagnostic.frozen, "_require_all_effect_gates_false", lambda: None
    )
    monkeypatch.setattr(diagnostic.frozen, "_require_frozen_publication", lambda: None)
    monkeypatch.setattr(
        diagnostic.frozen, "_load_frozen_history_seed", lambda: inputs.history_seed
    )
    monkeypatch.setattr(diagnostic.frozen, "_frozen_inputs", lambda seed: inputs)
    monkeypatch.setattr(diagnostic.frozen, "_reconcile_authority", lambda item: None)
    monkeypatch.setattr(
        diagnostic.frozen, "_reconcile_selected_snapshot", lambda item: None
    )

    def acquire() -> object:
        calls["acquire"] = int(calls["acquire"]) + 1
        return authority

    class Reader:
        def __init__(self, candidate: object) -> None:
            values = calls["p2_construct"]
            assert isinstance(values, list)
            values.append(candidate)

        def read_selected_snapshot(self, *args: object, **kwargs: object) -> object:
            values = calls["p2_read"]
            assert isinstance(values, list)
            values.append((args, kwargs))
            return selected

    def construct_cycle(*args: object, **kwargs: object) -> object:
        values = calls["b1_construct"]
        assert isinstance(values, list)
        values.append((args, kwargs))
        return cycle

    def assertion(*args: object) -> object:
        values = calls["assertions"]
        assert isinstance(values, list)
        values.append((args, calls["active"]))
        result = SimpleNamespace(values=args)
        calls["assertion_object"] = result
        return result

    def request(*args: object) -> object:
        values = calls["requests"]
        assert isinstance(values, list)
        values.append((args, calls["active"]))
        return SimpleNamespace(values=args)

    calendar_engine = object()

    def market_calendar() -> object:
        return calendar_engine

    def bound_calendar(*args: object) -> object:
        values = calls["calendar"]
        assert isinstance(values, list)
        values.append((args, calls["active"]))
        return SimpleNamespace(descriptor=args[0], engine=args[1])

    target = object()
    snapshot_reference = SimpleNamespace(
        snapshot_id=selected.audit.snapshot_id,
        artifact_sha256=selected.audit.artifact_sha256,
        artifact_byte_length=selected.audit.artifact_byte_length,
    )
    checkpointed_request = SimpleNamespace(
        request_id=_REQUEST_ID,
        snapshot_reference=snapshot_reference,
        target=target,
    )
    plan = SimpleNamespace(
        plan_id=_PLAN_ID,
        paper_account_id=diagnostic._EXPECTED_PAPER_ACCOUNT_ID,
        selected_c3_assertion=None,
        prior_checkpoint=("prior", evidence.prior_checkpoint),
        caller_idempotency_key=str(inputs.caller_idempotency_key),
        target=target,
    )
    binding = SimpleNamespace(
        plan=plan,
        artifact_bytes=b"plan",
        artifact_sha256=_PLAN_SHA,
        artifact_byte_length=_PLAN_LENGTH,
        checkpointed_request=checkpointed_request,
    )
    calls["checkpointed_request"] = checkpointed_request

    def build(candidate: object, calendar: object) -> object:
        values = calls["build"]
        assert isinstance(values, list)
        values.append((candidate, calendar, calls["active"]))
        request_values = calls["requests"]
        assert isinstance(request_values, list)
        plan.selected_c3_assertion = request_values[0][0][2]
        assert plan.selected_c3_assertion is calls["assertion_object"]
        return binding

    def verify(*args: object, **kwargs: object) -> object:
        values = calls["verify"]
        assert isinstance(values, list)
        values.append((args, kwargs, calls["active"]))
        return binding

    class PriorEvidence:
        @staticmethod
        def from_verified(prior: object) -> object:
            values = calls["prior"]
            assert isinstance(values, list)
            values.append((prior, calls["active"]))
            return ("prior", prior)

    monkeypatch.setattr(diagnostic, "acquire_validated_production_authority", acquire)
    monkeypatch.setattr(diagnostic, "WindowsSelectedC3SnapshotReadAuthority", Reader)
    monkeypatch.setattr(
        diagnostic, "supervised_personal_desktop_paper_cycle", construct_cycle
    )
    monkeypatch.setattr(diagnostic, "ManualPaperSelectedC3Assertion", assertion)
    monkeypatch.setattr(diagnostic, "ManualPaperStrategyPlanRequest", request)
    monkeypatch.setattr(diagnostic, "NYSEMarketCalendar", market_calendar)
    monkeypatch.setattr(diagnostic, "BoundMarketCalendar", bound_calendar)
    monkeypatch.setattr(diagnostic, "build_manual_paper_strategy_plan", build)
    monkeypatch.setattr(diagnostic, "verify_manual_paper_strategy_plan", verify)
    monkeypatch.setattr(diagnostic, "ManualPaperPriorCheckpointEvidence", PriorEvidence)
    return calls, authority, selected, inputs, cycle


def _captured(capsys: pytest.CaptureFixture[str]) -> tuple[str, str]:
    captured = capsys.readouterr()
    assert _HOSTILE not in captured.out
    assert _HOSTILE not in captured.err
    return captured.out, captured.err


def test_invalid_arguments_stop_before_preflight_and_c1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    parser = diagnostic.build_parser()
    assert {
        option for action in parser._actions for option in action.option_strings
    } == {"-h", "--help"}
    monkeypatch.setattr(
        diagnostic.frozen,
        "_require_all_effect_gates_false",
        lambda: pytest.fail("arguments reached preflight"),
    )
    monkeypatch.setattr(
        diagnostic,
        "acquire_validated_production_authority",
        lambda: pytest.fail("arguments reached C1"),
    )

    assert diagnostic.main(["--account", _HOSTILE]) == diagnostic._EXIT_USAGE
    out, err = _captured(capsys)
    assert out == ""
    assert json.loads(err) == {
        "reason": "INVALID_ARGUMENTS",
        "schema": diagnostic._SCHEMA,
    }


def test_preflight_failure_stops_before_c1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        diagnostic.frozen,
        "_require_all_effect_gates_false",
        lambda: (_ for _ in ()).throw(ValueError(_HOSTILE)),
    )
    monkeypatch.setattr(
        diagnostic,
        "acquire_validated_production_authority",
        lambda: pytest.fail("preflight reached C1"),
    )

    assert diagnostic.main([]) == diagnostic._EXIT_PREFLIGHT
    out, err = _captured(capsys)
    assert out == ""
    assert json.loads(err)["reason"] == "PREFLIGHT_BLOCKED"


def test_c1_failure_stops_before_p2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls, _, _, _, _ = _install_happy_path(monkeypatch)
    monkeypatch.setattr(
        diagnostic,
        "acquire_validated_production_authority",
        lambda: (_ for _ in ()).throw(RuntimeError(_HOSTILE)),
    )

    assert diagnostic.main([]) == diagnostic._EXIT_C1
    assert calls["p2_construct"] == []
    assert calls["b1_construct"] == []
    assert json.loads(_captured(capsys)[1])["reason"] == "C1_BLOCKED"


def test_p2_failure_stops_before_b1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls, authority, _, _, _ = _install_happy_path(monkeypatch)

    class Reader:
        def __init__(self, candidate: object) -> None:
            assert candidate is authority

        def read_selected_snapshot(self, selection_id: str) -> object:
            assert selection_id == str(diagnostic._EXPECTED_SELECTION_ID)
            raise ValueError(_HOSTILE)

    monkeypatch.setattr(diagnostic, "WindowsSelectedC3SnapshotReadAuthority", Reader)

    assert diagnostic.main([]) == diagnostic._EXIT_P2
    assert calls["b1_construct"] == []
    assert json.loads(_captured(capsys)[1])["reason"] == "P2_BLOCKED"


def test_exact_same_c1_and_selection_feed_p2_and_b1_once(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls, authority, _, _, _ = _install_happy_path(monkeypatch)

    assert diagnostic.main([]) == 0
    _captured(capsys)
    assert calls["acquire"] == 1
    assert calls["p2_construct"] == [authority]
    assert calls["p2_read"] == [((str(diagnostic._EXPECTED_SELECTION_ID),), {})]
    assert calls["b1_construct"] == [
        ((authority,), {"historical_cycle_configuration_payloads": ()})
    ]
    assert calls["b1_enter"] == 1
    assert calls["b1_exit"] == 1


def test_exact_post_lock_evidence_and_frozen_fields_build_request_while_active(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls, _, selected, inputs, _ = _install_happy_path(monkeypatch)

    assert diagnostic.main([]) == 0
    _captured(capsys)
    assertions = calls["assertions"]
    requests = calls["requests"]
    assert isinstance(assertions, list) and isinstance(requests, list)
    assert assertions == [
        (
            (
                selected.audit.selection_id,
                selected.audit.session_id,
                selected.audit.terminal_id,
                selected.audit.snapshot_id,
                selected.audit.artifact_sha256,
                selected.audit.artifact_byte_length,
            ),
            True,
        )
    ]
    assertion = calls["assertion_object"]
    request_args, active = requests[0]
    assert active is True
    assert request_args == (
        selected.verification,
        diagnostic._EXPECTED_PAPER_ACCOUNT_ID,
        assertion,
        _evidence().prior_checkpoint,
        inputs.history_seed,
        inputs.strategy_config,
        str(inputs.caller_idempotency_key),
        inputs.open_reference,
        inputs.policies,
        inputs.planning_at,
        inputs.submitted_at,
        inputs.filled_at,
        (),
    )


def test_build_and_verify_once_with_same_exact_calendar(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls, _, _, _, _ = _install_happy_path(monkeypatch)

    assert diagnostic.main([]) == 0
    _captured(capsys)
    calendars = calls["calendar"]
    builds = calls["build"]
    verifies = calls["verify"]
    assert isinstance(calendars, list)
    assert len(calendars) == 1
    assert calendars[0][0][0] is diagnostic.XNYS_CALENDAR_DESCRIPTOR
    assert calendars[0][1] is True
    assert isinstance(builds, list) and len(builds) == 1 and builds[0][2] is True
    calendar = builds[0][1]
    assert isinstance(verifies, list) and len(verifies) == 1
    args, kwargs, active = verifies[0]
    assert args == (b"plan", calendar)
    assert kwargs == {
        "expected_sha256": _PLAN_SHA,
        "expected_byte_length": _PLAN_LENGTH,
        "expected_checkpointed_request": calls["checkpointed_request"],
    }
    assert active is True


def test_b1_enter_failure_is_once_and_has_no_release(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls, _, _, _, _ = _install_happy_path(
        monkeypatch,
        cycle_factory=lambda values, evidence: _Cycle(
            values, evidence, enter_error=ValueError(_HOSTILE)
        ),
    )

    assert diagnostic.main([]) == diagnostic._EXIT_B1_ENTER
    assert calls["b1_enter"] == 1
    assert calls["b1_exit"] == 0
    assert calls["requests"] == []
    assert json.loads(_captured(capsys)[1])["reason"] == "B1_ENTER_BLOCKED"


@pytest.mark.parametrize(
    ("stage", "reason", "exit_code"),
    (
        ("request", "P1_REQUEST_BLOCKED", diagnostic._EXIT_P1_REQUEST),
        ("build", "P1_BUILD_BLOCKED", diagnostic._EXIT_P1_BUILD),
        ("verify", "P1_REPLAY_BLOCKED", diagnostic._EXIT_P1_REPLAY),
    ),
)
def test_p1_stage_failure_is_typed_released_once_and_not_retried(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stage: str,
    reason: str,
    exit_code: int,
) -> None:
    calls, _, _, _, _ = _install_happy_path(monkeypatch)
    name = {
        "request": "ManualPaperStrategyPlanRequest",
        "build": "build_manual_paper_strategy_plan",
        "verify": "verify_manual_paper_strategy_plan",
    }[stage]
    monkeypatch.setattr(
        diagnostic,
        name,
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError(_HOSTILE)),
    )

    assert diagnostic.main([]) == exit_code
    out, err = _captured(capsys)
    assert out == ""
    assert json.loads(err) == {
        "exception_family": "VALUE_ERROR",
        "reason": reason,
        "schema": diagnostic._SCHEMA,
    }
    assert calls["b1_enter"] == 1
    assert calls["b1_exit"] == 1
    assert calls["active"] is False
    assert len(calls["requests"]) <= 1
    assert len(calls["build"]) <= 1
    assert len(calls["verify"]) <= 1


def test_checkpointed_value_error_family_is_not_collapsed() -> None:
    error = CheckpointedVerifiedSnapshotPaperCycleReconciliationError(_HOSTILE)
    assert diagnostic._exception_record("P1_BUILD_BLOCKED", error) == {
        "exception_family": "CHECKPOINTED_VERIFIED_SNAPSHOT_CYCLE_ERROR",
        "reason": "P1_BUILD_BLOCKED",
        "schema": diagnostic._SCHEMA,
    }


@pytest.mark.parametrize(
    ("error", "family"),
    (
        (
            diagnostic.ManualPaperStrategyPlanError(_HOSTILE),
            "MANUAL_PAPER_STRATEGY_PLAN_ERROR",
        ),
        (
            diagnostic.VerifiedSnapshotPaperCyclePreparationError(_HOSTILE),
            "VERIFIED_SNAPSHOT_PREPARATION_ERROR",
        ),
        (
            diagnostic.SupervisedPersonalDesktopPaperCycleError(_HOSTILE),
            "SUPERVISED_CYCLE_ERROR",
        ),
        (
            diagnostic.PersonalDesktopPaperAccountError(_HOSTILE),
            "PAPER_ACCOUNT_ERROR",
        ),
        (
            diagnostic.PaperAccountMutexSecurityError(_HOSTILE),
            "PAPER_MUTEX_SECURITY_ERROR",
        ),
        (diagnostic.PaperAccountMutexBusyError(_HOSTILE), "PAPER_MUTEX_BUSY_ERROR"),
        (diagnostic.PaperAccountMutexWaitError(_HOSTILE), "PAPER_MUTEX_WAIT_ERROR"),
        (
            diagnostic.PaperAccountMutexReentrantError(_HOSTILE),
            "PAPER_MUTEX_REENTRANT_ERROR",
        ),
        (
            diagnostic.PaperAccountMutexReleaseError(_HOSTILE),
            "PAPER_MUTEX_RELEASE_ERROR",
        ),
        (
            diagnostic.PaperAccountMutexPoisonedError(_HOSTILE),
            "PAPER_MUTEX_POISONED_ERROR",
        ),
        (diagnostic.PaperAccountMutexError(_HOSTILE), "PAPER_MUTEX_ERROR"),
        (diagnostic.WindowsAuthorityError(_HOSTILE), "WINDOWS_AUTHORITY_ERROR"),
        (ctypes.ArgumentError(_HOSTILE), "CTYPES_ARGUMENT_ERROR"),
        (TypeError(_HOSTILE), "TYPE_ERROR"),
        (ValueError(_HOSTILE), "VALUE_ERROR"),
        (OSError(_HOSTILE), "OS_ERROR"),
        (AttributeError(_HOSTILE), "ATTRIBUTE_ERROR"),
        (KeyError(_HOSTILE), "KEY_ERROR"),
        (IndexError(_HOSTILE), "INDEX_ERROR"),
        (RuntimeError(_HOSTILE), "RUNTIME_ERROR"),
        (Exception(_HOSTILE), "UNKNOWN_EXCEPTION"),
    ),
)
def test_fixed_exception_families_hide_messages(error: Exception, family: str) -> None:
    record = diagnostic._exception_record("P1_BUILD_BLOCKED", error)
    assert record["exception_family"] == family
    assert record["reason"] == "P1_BUILD_BLOCKED"
    assert _HOSTILE not in json.dumps(record)


def test_windows_native_fields_are_allowlisted_only() -> None:
    allowed = diagnostic.WindowsNativeError("GetSecurityInfo", 5)
    hostile = diagnostic.WindowsNativeError(_HOSTILE, 6)
    assert diagnostic._exception_record("B1_ENTER_BLOCKED", allowed) == {
        "exception_family": "WINDOWS_NATIVE_ERROR",
        "native_error_code": 5,
        "native_operation": "GetSecurityInfo",
        "reason": "B1_ENTER_BLOCKED",
        "schema": diagnostic._SCHEMA,
    }
    record = diagnostic._exception_record("B1_ENTER_BLOCKED", hostile)
    assert "native_operation" not in record
    assert _HOSTILE not in json.dumps(record)


def test_replay_mismatch_blocks_reconciliation_and_releases(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls, _, _, _, _ = _install_happy_path(monkeypatch)
    monkeypatch.setattr(
        diagnostic,
        "verify_manual_paper_strategy_plan",
        lambda *args, **kwargs: SimpleNamespace(),
    )

    assert diagnostic.main([]) == diagnostic._EXIT_P1_RECONCILIATION
    assert calls["b1_exit"] == 1
    assert json.loads(_captured(capsys)[1])["reason"] == ("P1_RECONCILIATION_BLOCKED")


@pytest.mark.parametrize("error", (KeyboardInterrupt(), SystemExit(17)))
def test_base_exception_releases_then_reraises(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: BaseException,
) -> None:
    calls, _, _, _, _ = _install_happy_path(monkeypatch)

    def interrupt(*args: object, **kwargs: object) -> object:
        assert calls["active"] is True
        raise error

    monkeypatch.setattr(diagnostic, "build_manual_paper_strategy_plan", interrupt)
    with pytest.raises(type(error)) as raised:
        diagnostic.main([])
    assert raised.value is error
    if isinstance(error, SystemExit):
        assert raised.value.code == 17
    assert calls["b1_exit"] == 1
    assert calls["active"] is False
    assert _captured(capsys) == ("", "")


def test_release_failure_overrides_ordinary_body_result_and_is_not_retried(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls, _, _, _, _ = _install_happy_path(
        monkeypatch,
        cycle_factory=lambda values, evidence: _Cycle(
            values,
            evidence,
            release_error=diagnostic.PaperAccountMutexReleaseError(_HOSTILE),
        ),
    )
    monkeypatch.setattr(
        diagnostic,
        "build_manual_paper_strategy_plan",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError(_HOSTILE)),
    )

    assert diagnostic.main([]) == diagnostic._EXIT_B1_RELEASE
    assert calls["b1_exit"] == 1
    assert json.loads(_captured(capsys)[1]) == {
        "exception_family": "PAPER_MUTEX_RELEASE_ERROR",
        "reason": "B1_RELEASE_BLOCKED",
        "schema": diagnostic._SCHEMA,
    }


def test_success_json_is_exact_and_safe(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls, authority, selected, inputs, _ = _install_happy_path(monkeypatch)

    assert diagnostic.main([]) == 0
    out, err = _captured(capsys)
    assert err == ""
    assert out.count("\n") == 1
    assert json.loads(out) == {
        "all_effect_gates_false": True,
        "authority_epoch_id": authority.authority_epoch_id,
        "machine_authority_id": authority.machine_authority_id,
        "mutex_acquisition_state": "OWNED",
        "paper_account_id": diagnostic._EXPECTED_PAPER_ACCOUNT_ID,
        "plan_artifact_byte_length": _PLAN_LENGTH,
        "plan_artifact_sha256": _PLAN_SHA,
        "plan_id": str(_PLAN_ID),
        "request_id": str(_REQUEST_ID),
        "result": "P1_READY",
        "schema": diagnostic._SCHEMA,
        "seed_id": str(inputs.history_seed.seed.seed_id),
        "selected_snapshot_id": str(selected.audit.snapshot_id),
        "selection_id": str(selected.audit.selection_id),
        "terminal_checkpoint_id": str(diagnostic._EXPECTED_TERMINAL_CHECKPOINT_ID),
    }
    assert calls["b1_enter"] == 1
    assert calls["b1_exit"] == 1
    assert calls["active"] is False
    for prohibited in (
        "F:\\",
        "artifact_bytes",
        "request_payload",
        "operation_root",
        "intent",
        "execution_inputs",
        "binding",
        "credential",
    ):
        assert prohibited not in out


def test_source_stops_at_p1_and_has_no_effect_or_write_boundary() -> None:
    source = Path(diagnostic.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    imported_modules = {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    forbidden = {
        "PaperOperationIntent",
        "VerifiedPaperOperationExecutionInputs",
        "_require_active_prepared_paper_operation_binding",
        "inspect_paper_operation_root",
        "qualify_supervised_personal_desktop_paper_operation",
        "execute_supervised_personal_desktop_paper_operation",
        "execute_paper_operation_once",
        "commit_transition_directory",
        "commit_paper_operation_receipt",
    }
    assert imported_names.isdisjoint(forbidden)
    assert called.isdisjoint(forbidden)
    assert not any(
        boundary in module
        for module in imported_modules
        for boundary in (
            "paper_operation_inspection",
            "paper_operation_execution_inputs",
            "personal_desktop_supervised_paper_operation_preparation",
            "personal_desktop_supervised_paper_operation_qualification",
            "provider",
            "broker",
            "scheduler",
            "recovery",
            "requests",
            "socket",
            "subprocess",
        )
    )
    assert source.count("supervised_personal_desktop_paper_cycle(") == 1
    assert source.count("read_selected_snapshot(") == 1
    assert source.count("ManualPaperSelectedC3Assertion(") == 1
    assert source.count("ManualPaperStrategyPlanRequest(") == 1
    assert source.count("build_manual_paper_strategy_plan(") == 1
    assert source.count("verify_manual_paper_strategy_plan(") == 1
    assert "artifact_path" not in source
    assert not ({"write_text", "write_bytes", "unlink", "replace"} & called)
    assert "RebalanceAssumptions(" not in source
    assert "PortfolioConstraints(" not in source


def test_thin_script_imports_without_running() -> None:
    module = importlib.import_module("scripts.diagnose_pd2d1_p1_readonly")
    assert module.main is diagnostic.main
