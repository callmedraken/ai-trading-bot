"""Focused source-only tests for the temporary PD2D1 B1 diagnostic."""

from __future__ import annotations

import ast
import ctypes
import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

import trading_bot.cli.pd2d1_b1_readonly_diagnostic as diagnostic

_HOSTILE = (
    r"token=private F:\private\root handle=0xDEADBEEF "
    r"Global\hostile-mutex arbitrary-native-message"
)


class _Admission:
    def __init__(
        self,
        calls: dict[str, object],
        *,
        state: object = diagnostic.PaperAccountMutexState.OWNED,
        enter_error: Exception | None = None,
        release_error: Exception | None = None,
        return_self: bool = True,
        acquisition_account_id: str = diagnostic._EXPECTED_PAPER_ACCOUNT_ID,
    ) -> None:
        self.calls = calls
        self.enter_error = enter_error
        self.release_error = release_error
        self.return_self = return_self
        self.acquisition = SimpleNamespace(
            paper_account_id=acquisition_account_id,
            state=state,
        )

    def __enter__(self) -> object:
        self.calls["enter"] = int(self.calls["enter"]) + 1
        if self.enter_error is not None:
            raise self.enter_error
        self.calls["active"] = True
        return (
            self if self.return_self else SimpleNamespace(acquisition=self.acquisition)
        )

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.calls["exit"] = int(self.calls["exit"]) + 1
        assert self.calls["active"] is True
        assert (exc_type, exc, traceback) == (None, None, None)
        self.calls["active"] = False
        if self.release_error is not None:
            raise self.release_error


def _account_evidence(
    *,
    account_id: str = diagnostic._EXPECTED_PAPER_ACCOUNT_ID,
    terminal: object = diagnostic._EXPECTED_TERMINAL_CHECKPOINT_ID,
    successors: object = (),
    reports: object = (),
    snapshots: object = (),
    receipts: object = (),
) -> SimpleNamespace:
    return SimpleNamespace(
        anchor=SimpleNamespace(paper_account_id=account_id),
        lineage=SimpleNamespace(terminal_checkpoint_id=terminal),
        successors=successors,
        reports=reports,
        snapshots=snapshots,
        receipts=receipts,
    )


def _install_happy_path(
    monkeypatch: pytest.MonkeyPatch,
    *,
    admission_factory: Callable[[dict[str, object]], _Admission] | None = None,
    post_evidence: object | None = None,
) -> tuple[dict[str, object], SimpleNamespace, _Admission]:
    monkeypatch.setattr(diagnostic, "_require_all_effect_gates_false", lambda: None)
    monkeypatch.setattr(diagnostic, "_require_frozen_publication", lambda: None)
    authority = SimpleNamespace(
        machine_authority_id=diagnostic._EXPECTED_MACHINE_AUTHORITY_ID,
        authority_epoch_id=diagnostic._EXPECTED_AUTHORITY_EPOCH_ID,
        approved_account_sid=diagnostic._EXPECTED_TRADING_SID,
    )
    pre_account = SimpleNamespace(operation_root=diagnostic._EXPECTED_OPERATION_ROOT)
    post_account = SimpleNamespace(operation_root=diagnostic._EXPECTED_OPERATION_ROOT)
    pre_evidence = _account_evidence()
    post_evidence = _account_evidence() if post_evidence is None else post_evidence
    calls: dict[str, object] = {
        "acquire": 0,
        "active": False,
        "admit": [],
        "enter": 0,
        "exit": 0,
        "reads": [],
        "requires": [],
    }
    admission = (
        _Admission(calls) if admission_factory is None else admission_factory(calls)
    )

    def acquire() -> object:
        calls["acquire"] = int(calls["acquire"]) + 1
        return authority

    def read(candidate: object, **kwargs: object) -> object:
        reads = calls["reads"]
        assert isinstance(reads, list)
        reads.append((candidate, kwargs, calls["active"]))
        return pre_account if len(reads) == 1 else post_account

    def require(account: object) -> object:
        requires = calls["requires"]
        assert isinstance(requires, list)
        requires.append(account)
        return pre_evidence if account is pre_account else post_evidence

    def admit(account: object) -> object:
        admitted = calls["admit"]
        assert isinstance(admitted, list)
        admitted.append(account)
        return admission

    monkeypatch.setattr(diagnostic, "acquire_validated_production_authority", acquire)
    monkeypatch.setattr(diagnostic, "read_personal_desktop_paper_account", read)
    monkeypatch.setattr(
        diagnostic, "require_validated_personal_desktop_paper_account", require
    )
    monkeypatch.setattr(diagnostic, "supervised_paper_cycle_admission", admit)
    return calls, authority, admission


def _result(capsys: pytest.CaptureFixture[str]) -> tuple[str, str]:
    captured = capsys.readouterr()
    assert _HOSTILE not in captured.out
    assert _HOSTILE not in captured.err
    return captured.out, captured.err


def test_unexpected_arguments_stop_before_c1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        diagnostic,
        "_require_all_effect_gates_false",
        lambda: pytest.fail("arguments reached preflight"),
    )
    monkeypatch.setattr(
        diagnostic,
        "acquire_validated_production_authority",
        lambda: pytest.fail("arguments reached C1"),
    )

    assert diagnostic.main(["--account", _HOSTILE]) == diagnostic._EXIT_USAGE
    out, err = _result(capsys)
    assert out == ""
    assert json.loads(err) == {
        "reason": "INVALID_ARGUMENTS",
        "schema": diagnostic._SCHEMA,
    }


@pytest.mark.parametrize(
    ("module", "name", "value"),
    (
        (
            diagnostic.paper_security,
            "PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED",
            True,
        ),
        (
            diagnostic.paper_security,
            "PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED",
            None,
        ),
        (
            diagnostic.pd2c,
            "PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED",
            0,
        ),
    ),
)
def test_any_gate_mismatch_stops_before_c1(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    module: object,
    name: str,
    value: object,
) -> None:
    monkeypatch.setattr(module, name, value)
    monkeypatch.setattr(diagnostic, "_require_frozen_publication", lambda: None)
    monkeypatch.setattr(
        diagnostic,
        "acquire_validated_production_authority",
        lambda: pytest.fail("gate mismatch reached C1"),
    )

    assert diagnostic.main([]) == diagnostic._EXIT_PREFLIGHT
    out, err = _result(capsys)
    assert out == ""
    assert json.loads(err)["reason"] == "PREFLIGHT_BLOCKED"


def test_publication_mismatch_stops_before_c1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    freeze = diagnostic.publication_freeze.PERSONAL_DESKTOP_PAPER_V2_PUBLICATION_FREEZE
    assert freeze is not None
    mismatched = SimpleNamespace(
        **{
            name: getattr(freeze, name)
            for name in (
                "machine_authority_id",
                "approved_trading_sid",
                "paper_account_id",
                "starting_cash",
                "genesis_as_of",
                "genesis_sha256",
                "genesis_byte_length",
                "anchor_sha256",
                "anchor_byte_length",
                "manifest_sha256",
                "manifest_byte_length",
            )
        }
    )
    mismatched.manifest_byte_length += 1
    monkeypatch.setattr(
        diagnostic.publication_freeze,
        "require_production_paper_publication_freeze",
        lambda: mismatched,
    )
    monkeypatch.setattr(
        diagnostic,
        "acquire_validated_production_authority",
        lambda: pytest.fail("publication mismatch reached C1"),
    )

    assert diagnostic.main([]) == diagnostic._EXIT_PREFLIGHT
    out, err = _result(capsys)
    assert out == ""
    assert json.loads(err)["reason"] == "PREFLIGHT_BLOCKED"


@pytest.mark.parametrize("identity_mismatch", (False, True))
def test_c1_failure_or_identity_mismatch_stops_before_account_read(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    identity_mismatch: bool,
) -> None:
    monkeypatch.setattr(diagnostic, "_require_all_effect_gates_false", lambda: None)
    monkeypatch.setattr(diagnostic, "_require_frozen_publication", lambda: None)
    if identity_mismatch:
        acquire = lambda: SimpleNamespace(  # noqa: E731
            machine_authority_id="00000000-0000-0000-0000-000000000000",
            authority_epoch_id=diagnostic._EXPECTED_AUTHORITY_EPOCH_ID,
            approved_account_sid=diagnostic._EXPECTED_TRADING_SID,
        )
    else:
        acquire = lambda: (_ for _ in ()).throw(RuntimeError(_HOSTILE))  # noqa: E731
    monkeypatch.setattr(diagnostic, "acquire_validated_production_authority", acquire)
    monkeypatch.setattr(
        diagnostic,
        "read_personal_desktop_paper_account",
        lambda *args, **kwargs: pytest.fail("C1 failure reached account read"),
    )

    assert diagnostic.main([]) == diagnostic._EXIT_C1
    out, err = _result(capsys)
    assert out == ""
    record = json.loads(err)
    assert record["reason"] == "C1_BLOCKED"
    assert record["exception_family"] in {"RUNTIME_ERROR", "VALUE_ERROR"}


@pytest.mark.parametrize("reconciliation_failure", (False, True))
def test_pre_lock_failure_stops_before_admission_construction(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    reconciliation_failure: bool,
) -> None:
    calls, _, _ = _install_happy_path(monkeypatch)
    if reconciliation_failure:
        monkeypatch.setattr(
            diagnostic,
            "_reconcile_account",
            lambda *args: (_ for _ in ()).throw(
                diagnostic._HarnessReconciliationError(_HOSTILE)
            ),
        )
    else:
        monkeypatch.setattr(
            diagnostic,
            "read_personal_desktop_paper_account",
            lambda *args, **kwargs: (_ for _ in ()).throw(OSError(_HOSTILE)),
        )

    assert diagnostic.main([]) == diagnostic._EXIT_PRE_LOCK_READ
    out, err = _result(capsys)
    assert out == ""
    assert json.loads(err)["reason"] == "PRE_LOCK_ACCOUNT_READ_BLOCKED"
    assert calls["admit"] == []
    assert calls["enter"] == 0


def test_admission_construction_failure_stops_before_native_entry(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls, _, _ = _install_happy_path(monkeypatch)
    monkeypatch.setattr(
        diagnostic,
        "supervised_paper_cycle_admission",
        lambda account: (_ for _ in ()).throw(TypeError(_HOSTILE)),
    )

    assert diagnostic.main([]) == diagnostic._EXIT_ADMISSION_CONSTRUCTION
    out, err = _result(capsys)
    assert out == ""
    assert json.loads(err) == {
        "exception_family": "TYPE_ERROR",
        "reason": "MUTEX_ADMISSION_CONSTRUCTION_BLOCKED",
        "schema": diagnostic._SCHEMA,
    }
    assert calls["enter"] == 0


@pytest.mark.parametrize(
    ("error", "family"),
    (
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
            diagnostic.PaperAccountMutexPoisonedError(_HOSTILE),
            "PAPER_MUTEX_POISONED_ERROR",
        ),
        (diagnostic.PaperAccountMutexError(_HOSTILE), "PAPER_MUTEX_ERROR"),
        (ctypes.ArgumentError(_HOSTILE), "CTYPES_ARGUMENT_ERROR"),
        (TypeError(_HOSTILE), "TYPE_ERROR"),
    ),
)
def test_mutex_enter_failure_is_safe_typed_and_never_retried(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: Exception,
    family: str,
) -> None:
    calls, _, _ = _install_happy_path(
        monkeypatch,
        admission_factory=lambda state: _Admission(state, enter_error=error),
    )

    assert diagnostic.main([]) == diagnostic._EXIT_MUTEX_ACQUIRE
    out, err = _result(capsys)
    assert out == ""
    assert json.loads(err) == {
        "exception_family": family,
        "reason": "MUTEX_ACQUIRE_BLOCKED",
        "schema": diagnostic._SCHEMA,
    }
    assert calls["enter"] == 1
    assert calls["exit"] == 0


@pytest.mark.parametrize(
    ("state", "reason"),
    (
        (
            diagnostic.PaperAccountMutexState.ABANDONED_OWNER,
            "ABANDONED_OWNER_RECONCILIATION_REQUIRED",
        ),
        ("UNEXPECTED", "MUTEX_ACQUIRE_RECONCILIATION_BLOCKED"),
    ),
)
def test_non_owned_state_stops_before_post_lock_and_releases_once(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    state: object,
    reason: str,
) -> None:
    calls, _, _ = _install_happy_path(
        monkeypatch,
        admission_factory=lambda values: _Admission(values, state=state),
    )

    assert diagnostic.main([]) == diagnostic._EXIT_MUTEX_ACQUIRE
    out, err = _result(capsys)
    assert out == ""
    assert json.loads(err) == {"reason": reason, "schema": diagnostic._SCHEMA}
    assert len(calls["reads"]) == 1
    assert calls["enter"] == 1
    assert calls["exit"] == 1
    assert calls["active"] is False


@pytest.mark.parametrize("failure", ("held", "missing", "account"))
def test_mutex_acquisition_evidence_mismatch_releases_once(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    calls, _, admission = _install_happy_path(
        monkeypatch,
        admission_factory=lambda values: _Admission(
            values,
            return_self=failure != "held",
            acquisition_account_id=(
                "00000000-0000-0000-0000-000000000000"
                if failure == "account"
                else diagnostic._EXPECTED_PAPER_ACCOUNT_ID
            ),
        ),
    )
    if failure == "missing":
        admission.acquisition = None

    assert diagnostic.main([]) == diagnostic._EXIT_MUTEX_ACQUIRE
    out, err = _result(capsys)
    assert out == ""
    assert json.loads(err) == {
        "reason": "MUTEX_ACQUIRE_RECONCILIATION_BLOCKED",
        "schema": diagnostic._SCHEMA,
    }
    assert len(calls["reads"]) == 1
    assert calls["enter"] == 1
    assert calls["exit"] == 1


def test_post_lock_read_uses_same_c1_empty_history_and_active_mutex(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls, authority, _ = _install_happy_path(monkeypatch)

    assert diagnostic.main([]) == 0
    out, err = _result(capsys)
    assert err == ""
    assert json.loads(out)["result"] == "B1_READY"
    assert calls["reads"] == [
        (authority, {"historical_cycle_configuration_payloads": ()}, False),
        (authority, {"historical_cycle_configuration_payloads": ()}, True),
    ]
    assert calls["enter"] == 1
    assert calls["exit"] == 1
    assert calls["active"] is False
    assert calls["admit"] == [calls["requires"][0]]


@pytest.mark.parametrize("reconciliation_failure", (False, True))
def test_post_lock_failure_preserves_stage_and_releases_once(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    reconciliation_failure: bool,
) -> None:
    bad_post = (
        _account_evidence(receipts=(object(),))
        if reconciliation_failure
        else _account_evidence()
    )
    calls, _, _ = _install_happy_path(monkeypatch, post_evidence=bad_post)
    if not reconciliation_failure:
        original = diagnostic.read_personal_desktop_paper_account

        def read(*args: object, **kwargs: object) -> object:
            if len(calls["reads"]) == 1:
                raise KeyError(_HOSTILE)
            return original(*args, **kwargs)

        monkeypatch.setattr(diagnostic, "read_personal_desktop_paper_account", read)

    assert diagnostic.main([]) == diagnostic._EXIT_POST_LOCK_READ
    out, err = _result(capsys)
    assert out == ""
    assert json.loads(err)["reason"] == (
        "POST_LOCK_ACCOUNT_RECONCILIATION_BLOCKED"
        if reconciliation_failure
        else "POST_LOCK_ACCOUNT_READ_BLOCKED"
    )
    assert calls["enter"] == 1
    assert calls["exit"] == 1
    assert calls["active"] is False


def test_release_failure_overrides_earlier_post_lock_failure_without_retry(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls, _, _ = _install_happy_path(
        monkeypatch,
        admission_factory=lambda values: _Admission(
            values,
            release_error=diagnostic.PaperAccountMutexReleaseError(_HOSTILE),
        ),
        post_evidence=_account_evidence(receipts=(object(),)),
    )

    assert diagnostic.main([]) == diagnostic._EXIT_MUTEX_RELEASE
    out, err = _result(capsys)
    assert out == ""
    assert json.loads(err) == {
        "exception_family": "PAPER_MUTEX_RELEASE_ERROR",
        "reason": "MUTEX_RELEASE_BLOCKED",
        "schema": diagnostic._SCHEMA,
    }
    assert calls["enter"] == 1
    assert calls["exit"] == 1


def test_windows_native_fields_are_allowlisted_and_message_is_never_emitted(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls, _, _ = _install_happy_path(
        monkeypatch,
        admission_factory=lambda values: _Admission(
            values,
            enter_error=diagnostic.WindowsNativeError("GetSecurityInfo", 5),
        ),
    )
    error = diagnostic.WindowsNativeError(_HOSTILE, 6)
    error.args = (_HOSTILE,)
    # The allowlisted instance is exercised through main; the hostile operation
    # is classified directly to prove it is omitted.
    assert diagnostic.main([]) == diagnostic._EXIT_MUTEX_ACQUIRE
    out, err = _result(capsys)
    assert out == ""
    assert json.loads(err) == {
        "exception_family": "WINDOWS_NATIVE_ERROR",
        "native_error_code": 5,
        "native_operation": "GetSecurityInfo",
        "reason": "MUTEX_ACQUIRE_BLOCKED",
        "schema": diagnostic._SCHEMA,
    }
    hostile_record = diagnostic._exception_record("MUTEX_ACQUIRE_BLOCKED", error)
    assert "native_operation" not in hostile_record
    assert _HOSTILE not in json.dumps(hostile_record)
    assert calls["enter"] == 1


def test_full_success_emits_exact_safe_json_and_exit_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls, _, _ = _install_happy_path(monkeypatch)

    assert diagnostic.main([]) == 0
    out, err = _result(capsys)
    assert err == ""
    assert out.count("\n") == 1
    assert json.loads(out) == {
        "all_effect_gates_false": True,
        "authority_epoch_id": diagnostic._EXPECTED_AUTHORITY_EPOCH_ID,
        "machine_authority_id": diagnostic._EXPECTED_MACHINE_AUTHORITY_ID,
        "mutex_acquisition_state": "OWNED",
        "operation_root_matches": True,
        "paper_account_id": diagnostic._EXPECTED_PAPER_ACCOUNT_ID,
        "post_lock_genesis_only": True,
        "pre_lock_genesis_only": True,
        "result": "B1_READY",
        "schema": diagnostic._SCHEMA,
        "terminal_checkpoint_id": str(diagnostic._EXPECTED_TERMINAL_CHECKPOINT_ID),
    }
    assert calls["acquire"] == 1
    assert len(calls["admit"]) == 1
    assert calls["enter"] == 1
    assert calls["exit"] == 1


def test_source_surface_stops_at_b1_and_effect_gates_are_false() -> None:
    source_path = Path(diagnostic.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported.update(alias.name for alias in node.names)
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    forbidden_import_fragments = (
        "manual_paper_selected_c3_snapshot",
        "strategy_history_seed",
        "verified_snapshot_preparation",
        "paper_operation_execution_inputs",
        "paper_operation_inspection",
        "provider",
        "broker",
        "scheduler",
    )
    forbidden_calls = {
        "supervised_personal_desktop_paper_cycle",
        "qualify_supervised_personal_desktop_paper_operation",
        "execute_paper_operation_once",
        "inspect_paper_operation_root",
        "PaperOperationIntent",
        "VerifiedPaperOperationExecutionInputs",
    }
    assert not any(
        fragment in name for fragment in forbidden_import_fragments for name in imported
    )
    assert called.isdisjoint(forbidden_calls)
    assert "subprocess" not in imported
    assert not ({"open", "write_text", "write_bytes", "unlink", "replace"} & called)
    assert (
        diagnostic.paper_security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED
        is False
    )
    assert (
        diagnostic.paper_security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED
        is False
    )
    assert (
        diagnostic.pd2c.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED
        is False
    )
