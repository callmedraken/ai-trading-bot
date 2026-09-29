from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from scripts import run_personal_desktop_d10_launch_guard as guard


def _deployment() -> guard.VerifiedDeploymentFacts:
    return guard.VerifiedDeploymentFacts(
        deployment_id="11111111-1111-5111-8111-111111111111",
        attestation_sha256="a" * 64,
        certified_source_head="b" * 40,
        certified_source_tree="c" * 40,
        executable_file_count=306,
        schema=guard.D10_ATTESTATION_SCHEMA,
        signing_key_id=guard.D10_SIGNING_KEY_ID,
        source_root=guard.D10_SOURCE_ROOT,
        launch_guard=guard.D10_LAUNCH_GUARD,
        launcher=guard.D10_SECOND_STAGE_LAUNCHER,
        scheduler_contract_schema=guard.D10_SCHEDULER_SCHEMA,
        approved_trading_sid=guard.TRADING_SID,
        production_python=guard.D10_PRODUCTION_PYTHON,
        production_python_version=guard.D10_PRODUCTION_PYTHON_VERSION,
    )


def _lease(
    deployment: guard.VerifiedDeploymentFacts,
) -> guard.VerifiedActivationLeaseFacts:
    return guard.VerifiedActivationLeaseFacts(
        state="ACTIVE",
        deployment_id=deployment.deployment_id,
        attestation_sha256=deployment.attestation_sha256,
        soak_id="22222222-2222-5222-8222-222222222222",
        accepted_activation_utc="2026-09-29T00:45:22.123456Z",
        end_utc="2026-10-06T00:45:22.123456Z",
        certified_source_head=deployment.certified_source_head,
        certified_source_tree=deployment.certified_source_tree,
        scheduler_contract_schema=guard.D10_SCHEDULER_SCHEMA,
        scheduler_contract_id=guard.D10_SCHEDULER_CONTRACT_ID,
        trading_sid=guard.TRADING_SID,
        production_python=guard.D10_PRODUCTION_PYTHON,
        production_python_version=guard.D10_PRODUCTION_PYTHON_VERSION,
    )


def _wake_record(
    deployment: guard.VerifiedDeploymentFacts,
    lease: guard.VerifiedActivationLeaseFacts,
    *,
    outcome: str = "NO_ACTION",
) -> bytes:
    stopped = outcome == "STOPPED"
    payload = {
        "schema": guard.D10_WAKE_EVIDENCE_SCHEMA,
        "outcome": outcome,
        "stop_reason": "BLOCKED" if stopped else None,
        "observed_at_utc": "2026-09-29T08:30:00Z",
        "deployment": {
            "id": deployment.deployment_id,
            "attestation_sha256": deployment.attestation_sha256,
            "source_head": deployment.certified_source_head,
            "source_tree": deployment.certified_source_tree,
            "executable_file_count": deployment.executable_file_count,
        },
        "soak": {
            "id": lease.soak_id,
            "activation_utc": lease.accepted_activation_utc,
            "end_utc": lease.end_utc,
        },
        "runtime": {
            "scheduler_contract_schema": guard.D10_SCHEDULER_SCHEMA,
            "scheduler_task_path": guard.D10_SCHEDULER_TASK_PATH,
            "trading_sid": guard.TRADING_SID,
            "production_python": guard.D10_PRODUCTION_PYTHON,
            "production_python_version": guard.D10_PRODUCTION_PYTHON_VERSION,
        },
        "session": {
            "completed": None,
            "next_execution": None,
            "preopen_deadline_utc": None,
        },
        "capture": {
            "classification": None,
            "selection_id": None,
            "snapshot_id": None,
            "attempt_id": None,
            "terminal_state": None,
            "provider_call_disposition": None,
        },
        "history": {
            "classification": None,
            "reconciled_count": 0,
            "current_decision_id": None,
            "unresolved_decision_id": None,
        },
        "settlement": {
            "decision_id": None,
            "classification": None,
            "reconciliation": None,
            "plan_id": None,
            "invocation_id": None,
            "operation_id": None,
            "application_id": None,
            "predecessor_checkpoint_id": None,
            "successor_checkpoint_id": None,
        },
        "decision": {
            "id": None,
            "publication": None,
            "reconciliation": None,
            "finalized_id": None,
        },
        "budgets": {
            "provider_attempts": 0,
            "settlement_attempts": 0,
            "publication_attempts": 0,
            "receipt_recovery_attempts": 0,
            "broker_live_calls": 0,
        },
        "effect_crossings": {
            "provider": False,
            "settlement": False,
            "publication": False,
        },
        "final_gates": {"all_closed": True, "closed_count": 8},
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


class EvidenceNative:
    def __init__(self, lease: guard.VerifiedActivationLeaseFacts) -> None:
        self.path = guard._wake_evidence_path(lease)
        self.data = b""
        self.paths: dict[int, str] = {}
        self.next_handle = 1
        self.closed: list[int] = []
        self.append_count = 0
        self.drift_after_append_count: int | None = None

    def open(self, path: str, *, directory: bool) -> int:
        assert directory
        assert path == guard.D10_EVIDENCE_ROOT
        handle = self.next_handle
        self.next_handle += 1
        self.paths[handle] = path
        return handle

    def open_evidence_file(self, path: str) -> int:
        assert path == self.path
        handle = self.next_handle
        self.next_handle += 1
        self.paths[handle] = path
        return handle

    def close(self, handle: int) -> None:
        self.closed.append(handle)

    def inspect(self, handle: int) -> guard.ObjectFacts:
        path = self.paths[handle]
        if path == guard.D10_EVIDENCE_ROOT:
            return guard.ObjectFacts(
                path,
                guard.FILE_ATTRIBUTE_DIRECTORY,
                guard.DRIVE_FIXED,
                "F:\\",
                "NTFS",
                41,
                100,
                1,
                0,
                guard.ADMINISTRATORS_SID,
                True,
                guard.DIRECTORY_POLICY.aces,
            )
        return guard.ObjectFacts(
            path,
            0,
            guard.DRIVE_FIXED,
            "F:\\",
            "NTFS",
            41,
            (
                201
                if self.drift_after_append_count is not None
                and self.append_count >= self.drift_after_append_count
                else 200
            ),
            1,
            len(self.data),
            guard.ADMINISTRATORS_SID,
            True,
            guard.EVIDENCE_FILE_POLICY.aces,
        )

    def read_bounded(self, handle: int, size: int, limit: int) -> bytes:
        assert self.paths[handle] == self.path
        assert len(self.data) == size
        assert size <= limit
        return self.data

    def append_exact(self, handle: int, payload: bytes, expected_size: int) -> None:
        assert self.paths[handle] == self.path
        assert len(self.data) == expected_size
        self.data += payload
        self.append_count += 1


def test_append_only_acl_and_path_are_frozen() -> None:
    deployment = _deployment()
    lease = _lease(deployment)
    assert guard._wake_evidence_path(lease) == (
        guard.D10_EVIDENCE_ROOT + rf"\wake-{lease.soak_id}.jsonl"
    )
    assert guard.EVIDENCE_FILE_POLICY.owner == guard.ADMINISTRATORS_SID
    assert guard.EVIDENCE_FILE_POLICY.protected
    mask = guard.EVIDENCE_FILE_POLICY.aces[2].mask
    assert mask == guard.TRADING_FILE_READ | guard.FILE_APPEND_DATA
    assert mask & guard.FILE_APPEND_DATA
    assert not mask & guard.FILE_WRITE_DATA
    assert not mask & (0x10000 | 0x40000 | 0x80000)


def test_guarded_no_action_wake_is_captured_and_appended(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deployment = _deployment()
    lease = _lease(deployment)
    native = EvidenceNative(lease)
    record = _wake_record(deployment, lease)
    calls: list[tuple[object, dict[str, object]]] = []

    def child(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=record + b"\n", stderr=b"")

    monkeypatch.setattr(
        guard,
        "_trusted_runtime_utc_now",
        lambda: datetime(2026, 9, 29, 8, 29, tzinfo=UTC),
    )
    monkeypatch.setattr(guard.subprocess, "run", child)
    assert (
        guard._run_second_stage_with_evidence(
            deployment,
            lease,
            {"SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows"},
            native,
        )
        == 0
    )
    lines = native.data.splitlines()
    assert len(lines) == 2
    assert guard.D10_GUARD_WAKE_START_EVIDENCE_SCHEMA.encode() in lines[0]
    assert lines[1] == record
    assert guard._parse_evidence_log(native.data, deployment, lease)[2] is False
    assert calls[0][1]["capture_output"] is True
    assert calls[0][1]["cwd"] == guard.D10_ROOT
    assert "evidence" not in " ".join(calls[0][0]).lower()


def test_stopped_record_latches_and_prevents_later_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deployment = _deployment()
    lease = _lease(deployment)
    native = EvidenceNative(lease)
    record = _wake_record(deployment, lease, outcome="STOPPED")
    calls = [0]

    def child(*args, **kwargs):
        del args, kwargs
        calls[0] += 1
        return SimpleNamespace(returncode=1, stdout=record + b"\n", stderr=b"")

    monkeypatch.setattr(
        guard,
        "_trusted_runtime_utc_now",
        lambda: datetime(2026, 9, 29, 8, 29, tzinfo=UTC),
    )
    monkeypatch.setattr(guard.subprocess, "run", child)
    environment = {"SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows"}
    assert (
        guard._run_second_stage_with_evidence(deployment, lease, environment, native)
        == 1
    )
    assert calls[0] == 1
    with pytest.raises(guard.GuardBlocked, match="stop latch"):
        guard._run_second_stage_with_evidence(deployment, lease, environment, native)
    assert calls[0] == 1


def test_invalid_child_output_persists_guard_terminal_latch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deployment = _deployment()
    lease = _lease(deployment)
    native = EvidenceNative(lease)
    monkeypatch.setattr(
        guard,
        "_trusted_runtime_utc_now",
        lambda: datetime(2026, 9, 29, 8, 31, tzinfo=UTC),
    )
    monkeypatch.setattr(
        guard.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=b"not-json\n", stderr=b""
        ),
    )
    assert (
        guard._run_second_stage_with_evidence(
            deployment,
            lease,
            {"SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows"},
            native,
        )
        == 1
    )
    assert guard.D10_GUARD_TERMINAL_EVIDENCE_SCHEMA.encode() in native.data
    assert b"CHILD_OUTPUT_INVALID" in native.data
    assert guard._parse_evidence_log(native.data, deployment, lease)[2] is True


def test_partial_existing_log_blocks_before_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deployment = _deployment()
    lease = _lease(deployment)
    native = EvidenceNative(lease)
    native.data = _wake_record(deployment, lease)
    calls = [0]
    monkeypatch.setattr(
        guard.subprocess,
        "run",
        lambda *args, **kwargs: calls.__setitem__(0, calls[0] + 1),
    )
    with pytest.raises(guard.GuardBlocked, match="partial"):
        guard._run_second_stage_with_evidence(
            deployment,
            lease,
            {"SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows"},
            native,
        )
    assert calls[0] == 0


def test_post_append_native_identity_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deployment = _deployment()
    lease = _lease(deployment)
    native = EvidenceNative(lease)
    native.drift_after_append_count = 2
    record = _wake_record(deployment, lease)
    monkeypatch.setattr(
        guard.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=record + b"\n", stderr=b""
        ),
    )
    with pytest.raises(guard.GuardBlocked, match="identity changed"):
        guard._run_second_stage_with_evidence(
            deployment,
            lease,
            {"SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows"},
            native,
        )


def test_native_evidence_open_is_existing_append_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deployment = _deployment()
    lease = _lease(deployment)
    path = guard._wake_evidence_path(lease)
    calls: list[tuple[object, ...]] = []

    class Function:
        argtypes = None
        restype = None

        def __call__(self, *args: object) -> int:
            calls.append(args)
            return 7

    class Kernel:
        CreateFileW = Function()

    monkeypatch.setattr(guard, "_win_dll", lambda _: Kernel())
    assert guard._Native().open_evidence_file(path) == 7
    assert len(calls) == 1
    args = calls[0]
    assert args[0] == path
    assert args[1] == guard.TRADING_EVIDENCE_FILE_ACCESS
    assert args[1] & guard.FILE_APPEND_DATA
    assert not args[1] & guard.FILE_WRITE_DATA
    assert args[2] == 1
    assert args[4] == 3
    assert args[5] == guard.FILE_FLAG_OPEN_REPARSE_POINT


def test_scheduler_command_remains_zero_semantic_argument_guard_target() -> None:
    source = (
        guard.D10_PRODUCTION_PYTHON,
        "-I",
        "-S",
        "-B",
        "-X",
        f"pycache_prefix={guard.D10_CACHE_PREFIX}",
        guard.D10_SECOND_STAGE_LAUNCHER,
    )
    assert guard.D10_SCHEDULER_TASK_PATH == r"\AITradingBot-PD4-UnattendedPaper-v1"
    assert guard.D10_EVIDENCE_ROOT not in " ".join(source)
    assert guard.D10_EVIDENCE_ROOT not in guard.D10_SECOND_STAGE_LAUNCHER


def test_canonical_but_malformed_child_record_becomes_terminal_guard_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deployment = _deployment()
    lease = _lease(deployment)
    native = EvidenceNative(lease)
    value = json.loads(_wake_record(deployment, lease))
    value["history"]["reconciled_count"] = -1
    malformed = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    monkeypatch.setattr(
        guard,
        "_trusted_runtime_utc_now",
        lambda: datetime(2026, 9, 29, 8, 32, tzinfo=UTC),
    )
    monkeypatch.setattr(
        guard.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=malformed + b"\n", stderr=b""
        ),
    )
    assert (
        guard._run_second_stage_with_evidence(
            deployment,
            lease,
            {"SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows"},
            native,
        )
        == 1
    )
    assert b"CHILD_OUTPUT_INVALID" in native.data
    assert guard._parse_evidence_log(native.data, deployment, lease)[2] is True



def test_post_child_append_failure_leaves_start_latch_and_blocks_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deployment = _deployment()
    lease = _lease(deployment)

    class FailingSecondAppend(EvidenceNative):
        def append_exact(
            self, handle: int, payload: bytes, expected_size: int
        ) -> None:
            if self.append_count == 1:
                raise guard.GuardBlocked("simulated result append failure")
            super().append_exact(handle, payload, expected_size)

    native = FailingSecondAppend(lease)
    record = _wake_record(deployment, lease)
    calls = [0]

    def child(*args, **kwargs):
        del args, kwargs
        calls[0] += 1
        return SimpleNamespace(returncode=0, stdout=record + b"\n", stderr=b"")

    monkeypatch.setattr(guard.subprocess, "run", child)
    environment = {"SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows"}

    with pytest.raises(guard.GuardBlocked, match="simulated result append failure"):
        guard._run_second_stage_with_evidence(
            deployment, lease, environment, native
        )
    assert calls[0] == 1
    assert native.append_count == 1
    assert guard.D10_GUARD_WAKE_START_EVIDENCE_SCHEMA.encode() in native.data
    assert guard._parse_evidence_log(native.data, deployment, lease)[2] is True

    with pytest.raises(guard.GuardBlocked, match="stop latch"):
        guard._run_second_stage_with_evidence(
            deployment, lease, environment, native
        )
    assert calls[0] == 1


@pytest.mark.parametrize(
    ("stdout", "stderr", "returncode", "reason"),
    [
        (b"", b"", 0, b"CHILD_OUTPUT_MISSING"),
        (b"{}\n{}\n", b"", 0, b"CHILD_OUTPUT_INVALID"),
        (b"not-json\n", b"", 0, b"CHILD_OUTPUT_INVALID"),
        (b"", b"unexpected", 0, b"CHILD_OUTPUT_INVALID"),
    ],
)
def test_child_output_ambiguity_is_durably_terminal(
    monkeypatch: pytest.MonkeyPatch,
    stdout: bytes,
    stderr: bytes,
    returncode: int,
    reason: bytes,
) -> None:
    deployment = _deployment()
    lease = _lease(deployment)
    native = EvidenceNative(lease)
    monkeypatch.setattr(
        guard,
        "_trusted_runtime_utc_now",
        lambda: datetime(2026, 9, 29, 8, 33, tzinfo=UTC),
    )
    monkeypatch.setattr(
        guard.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=returncode, stdout=stdout, stderr=stderr
        ),
    )
    assert (
        guard._run_second_stage_with_evidence(
            deployment,
            lease,
            {"SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows"},
            native,
        )
        == 1
    )
    assert reason in native.data
    assert guard._parse_evidence_log(native.data, deployment, lease)[2] is True


def test_exit_mismatch_is_durably_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deployment = _deployment()
    lease = _lease(deployment)
    native = EvidenceNative(lease)
    record = _wake_record(deployment, lease)
    monkeypatch.setattr(
        guard,
        "_trusted_runtime_utc_now",
        lambda: datetime(2026, 9, 29, 8, 34, tzinfo=UTC),
    )
    monkeypatch.setattr(
        guard.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1, stdout=record + b"\n", stderr=b""
        ),
    )
    assert (
        guard._run_second_stage_with_evidence(
            deployment,
            lease,
            {"SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows"},
            native,
        )
        == 1
    )
    assert b"CHILD_EXIT_MISMATCH" in native.data
    assert guard._parse_evidence_log(native.data, deployment, lease)[2] is True


def test_missing_or_wrong_security_evidence_file_blocks_before_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deployment = _deployment()
    lease = _lease(deployment)
    calls = [0]

    class MissingEvidence(EvidenceNative):
        def open_evidence_file(self, path: str) -> int:
            del path
            raise guard.GuardBlocked("evidence file missing")

    missing = MissingEvidence(lease)
    monkeypatch.setattr(
        guard.subprocess,
        "run",
        lambda *args, **kwargs: calls.__setitem__(0, calls[0] + 1),
    )
    with pytest.raises(guard.GuardBlocked, match="missing"):
        guard._run_second_stage_with_evidence(
            deployment,
            lease,
            {"SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows"},
            missing,
        )
    assert calls[0] == 0

    wrong = EvidenceNative(lease)
    original = wrong.inspect

    def inspect(handle: int) -> guard.ObjectFacts:
        facts = original(handle)
        if wrong.paths[handle] == wrong.path:
            return guard.ObjectFacts(
                facts.final_path,
                facts.attributes,
                facts.drive_type,
                facts.volume_root,
                facts.filesystem,
                facts.volume_serial,
                facts.file_index,
                2,
                facts.size,
                facts.owner,
                facts.protected,
                facts.aces,
            )
        return facts

    wrong.inspect = inspect
    with pytest.raises(guard.GuardBlocked, match="hard-linked"):
        guard._run_second_stage_with_evidence(
            deployment,
            lease,
            {"SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows"},
            wrong,
        )
    assert calls[0] == 0



def test_native_evidence_observer_open_is_shared_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deployment = _deployment()
    lease = _lease(deployment)
    path = guard._wake_evidence_path(lease)
    calls: list[tuple[object, ...]] = []

    class Function:
        argtypes = None
        restype = None

        def __call__(self, *args: object) -> int:
            calls.append(args)
            return 7

    class Kernel:
        CreateFileW = Function()

    monkeypatch.setattr(guard, "_win_dll", lambda _: Kernel())
    assert guard._Native().open_evidence_observer(path) == 7
    assert len(calls) == 1
    args = calls[0]
    assert args[0] == path
    assert args[1] == guard.TRADING_FILE_READ
    assert not args[1] & guard.FILE_APPEND_DATA
    assert not args[1] & guard.FILE_WRITE_DATA
    assert args[2] == 3
    assert args[4] == 3
    assert args[5] == guard.FILE_FLAG_OPEN_REPARSE_POINT
