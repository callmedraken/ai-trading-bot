from __future__ import annotations

import hashlib
from uuid import UUID

import pytest

from trading_bot.runtime.capture_attempt_authority import (
    ProviderCallDisposition,
    SecretCleanupResult,
    SnapshotTerminalVerification,
)
from trading_bot.runtime.isolated_capture_artifacts import (
    ISOLATED_CAPTURE_CHILD_OPERATION_VERSION,
    ISOLATED_CAPTURE_ENVIRONMENT_POLICY_VERSION,
    HandleInheritancePosture,
    IsolatedCaptureChildClassification,
    JobObjectAssignmentResult,
    ProcessCreationResult,
    ProcessTreeTerminationResult,
    ResumeAuthorizationResult,
    create_child_process_creation_record,
    create_child_resume_authorization_record,
    create_child_termination_record,
    create_isolated_capture_child_result,
    evidence_for_payload,
    parse_child_process_creation_record,
    parse_child_resume_authorization_record,
    parse_child_termination_record,
    serialize_child_process_creation_record,
    serialize_child_resume_authorization_record,
    serialize_child_termination_record,
    serialize_isolated_capture_child_result,
)
from trading_bot.runtime.windows_isolated_capture_launcher import (
    ISOLATED_CAPTURE_RESUME_POLICY_VERSION,
    ISOLATED_CAPTURE_TERMINATION_POLICY_VERSION,
    IsolatedCaptureLauncherConfig,
    IsolatedCaptureLauncherError,
    NativeSuspendedProcess,
    build_isolated_child_environment,
    launch_isolated_capture_child,
)

from .isolated_capture_test_support import evidence, install_child_case


class FakeProcessApi:
    def __init__(
        self,
        *,
        waits: list[bool] | None = None,
        exit_code: int = 8,
        stdout: bytes = b"",
        stderr: bytes = b"",
    ) -> None:
        self.waits = [True] if waits is None else list(waits)
        self.child_exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.created = 0
        self.job_limits = 0
        self.assignments = 0
        self.resumes = 0
        self.terminations = 0
        self.closed: list[object] = []
        self.environment = None
        self.arguments = None
        self.inherit_handles = None

    def create_suspended(
        self,
        *,
        executable,
        arguments,
        environment,
        current_directory,
        inherit_handles,
    ):
        del executable, current_directory
        self.created += 1
        self.environment = dict(environment)
        self.arguments = arguments
        self.inherit_handles = inherit_handles
        return NativeSuspendedProcess(
            4242,
            "process-handle",
            "thread-handle",
            stdout=self.stdout,
            stderr=self.stderr,
        )

    def create_job_with_limits(self):
        self.job_limits += 1
        return "job-handle"

    def assign_to_job(self, job_handle, process):
        assert job_handle == "job-handle"
        assert process.process_id == 4242
        self.assignments += 1

    def resume(self, process):
        assert process.process_id == 4242
        self.resumes += 1

    def wait(self, process, timeout_milliseconds):
        assert process.process_id == 4242
        assert timeout_milliseconds > 0
        return self.waits.pop(0)

    def terminate_job(self, job_handle, exit_code):
        assert job_handle == "job-handle"
        assert exit_code == 9
        self.terminations += 1

    def terminate_process(self, process, exit_code):
        assert process.process_id == 4242
        assert exit_code == 9
        self.terminations += 1

    def exit_code(self, process):
        assert process.process_id == 4242
        return self.child_exit_code

    def close_handle(self, handle):
        self.closed.append(handle)


class ResumeFailureApi(FakeProcessApi):
    def resume(self, process):
        super().resume(process)
        raise RuntimeError("resume failed with secret-bearing detail")


def _launcher_case(tmp_path, *, native_exit_code: int = 8):
    case = install_child_case(tmp_path)
    python_path = tmp_path / "approved-python.exe"
    python_path.write_bytes(b"approved-python")
    script_path = tmp_path / "approved-child.py"
    script_path.write_bytes(b"approved-child-script")
    process_evidence = tmp_path / "process-evidence"
    process_evidence.mkdir()
    controlled_temp = tmp_path / "controlled-temp"
    controlled_temp.mkdir()
    request_evidence = evidence_for_payload(
        case["request"].child_request_id,
        case["request_payload"],
    )
    result = create_isolated_capture_child_result(
        child_request=request_evidence,
        allocation=case["request"].allocation,
        attempt_id=case["request"].attempt_id,
        provider_call_disposition=ProviderCallDisposition.NOT_STARTED,
        classification=IsolatedCaptureChildClassification.INTERNAL_FAILED,
        diagnostics=("CHILD_INTERNAL_FAILED",),
        http_status=None,
        provider_code=None,
        provider_request_id=None,
        native_exit_code=native_exit_code,
        snapshot=None,
        snapshot_verification=SnapshotTerminalVerification.NOT_APPLICABLE,
        secret_cleanup=SecretCleanupResult.NOT_APPLICABLE,
        child_operation_version=ISOLATED_CAPTURE_CHILD_OPERATION_VERSION,
    )
    case["request"].child_result_path.write_bytes(
        serialize_isolated_capture_child_result(result)
    )
    config = IsolatedCaptureLauncherConfig(
        schema_version=1,
        child_request=request_evidence,
        child_request_path=case["request_path"],
        approved_python_executable=python_path,
        approved_python_executable_evidence=evidence_for_payload(
            UUID("77777777-7777-5777-8777-777777777777"),
            python_path.read_bytes(),
        ),
        approved_child_script=script_path,
        approved_child_script_evidence=evidence_for_payload(
            UUID("88888888-8888-5888-8888-888888888888"),
            script_path.read_bytes(),
        ),
        process_evidence_directory=process_evidence,
        controlled_temp_directory=controlled_temp,
        environment_policy_version=ISOLATED_CAPTURE_ENVIRONMENT_POLICY_VERSION,
        termination_grace_seconds=5,
    )
    return case, config


def test_process_evidence_golden_vectors() -> None:
    allocation = evidence("allocation-golden")
    request = evidence("request-golden")
    creation = create_child_process_creation_record(
        allocation=allocation,
        child_request=request,
        scheduled_launch_id=UUID("22222222-2222-5222-8222-222222222222"),
        approved_executable=evidence("python-golden"),
        software_release=evidence("release-golden"),
        process_id=4242,
        creation_result=ProcessCreationResult.CREATED_SUSPENDED,
        job_object_assignment=JobObjectAssignmentResult.ASSIGNED,
        handle_inheritance=HandleInheritancePosture.DISABLED,
        environment_policy_version=ISOLATED_CAPTURE_ENVIRONMENT_POLICY_VERSION,
        diagnostics=("CHILD_CREATED_SUSPENDED", "JOB_LIMITS_ASSIGNED"),
    )
    creation_payload = serialize_child_process_creation_record(creation)
    creation_evidence = evidence_for_payload(
        creation.process_creation_record_id, creation_payload
    )
    resume = create_child_resume_authorization_record(
        allocation=allocation,
        child_request=request,
        process_creation=creation_evidence,
        scheduled_launch_id=UUID("22222222-2222-5222-8222-222222222222"),
        process_id=4242,
        evidence_verified=True,
        result=ResumeAuthorizationResult.AUTHORIZED,
        diagnostics=("RESUME_AUTHORIZED",),
        resume_policy_version=ISOLATED_CAPTURE_RESUME_POLICY_VERSION,
    )
    resume_payload = serialize_child_resume_authorization_record(resume)
    termination = create_child_termination_record(
        allocation=allocation,
        child_request=request,
        process_creation=creation_evidence,
        resume_authorization=evidence_for_payload(
            resume.resume_authorization_record_id, resume_payload
        ),
        scheduled_launch_id=UUID("22222222-2222-5222-8222-222222222222"),
        process_id=4242,
        timed_out=False,
        job_termination_requested=False,
        process_tree_result=ProcessTreeTerminationResult.EXITED,
        native_exit_code=8,
        diagnostics=("CHILD_EXITED",),
        termination_policy_version=ISOLATED_CAPTURE_TERMINATION_POLICY_VERSION,
    )
    termination_payload = serialize_child_termination_record(termination)

    assert str(creation.process_creation_record_id) == (
        "1e32841c-b00e-5a92-83f7-a36009f6b220"
    )
    assert len(creation_payload) == 1061
    assert hashlib.sha256(creation_payload).hexdigest() == (
        "53a82f1a2f528a941bbbb1273774582cb3b2e1d9f462608d8f4c0f17ccf8eeb7"
    )
    assert str(resume.resume_authorization_record_id) == (
        "d70f2c8d-79f8-5231-b429-5d8d97e51daa"
    )
    assert len(resume_payload) == 800
    assert hashlib.sha256(resume_payload).hexdigest() == (
        "6da75aae77126fbf901dbdfbc3bde9e8e32b078aecab90048f45bbd7e35422f4"
    )
    assert str(termination.termination_record_id) == (
        "dec05d87-7be5-502e-842d-622c4ee7ead1"
    )
    assert len(termination_payload) == 1025
    assert hashlib.sha256(termination_payload).hexdigest() == (
        "7d6e17cdfb59a91a974889b8c6d7bd792158e07e07e14dad4912c68e93bdf054"
    )
    assert parse_child_process_creation_record(creation_payload) == creation
    assert parse_child_resume_authorization_record(resume_payload) == resume
    assert parse_child_termination_record(termination_payload) == termination


def test_environment_allowlist_excludes_parent_secrets_and_proxy_state(
    tmp_path,
) -> None:
    controlled = tmp_path / "controlled"
    controlled.mkdir()
    parent = {
        "SystemRoot": r"C:\Windows",
        "WINDIR": r"C:\Windows",
        "PATH": "secret-path",
        "PYTHONPATH": "developer-path",
        "HTTPS_PROXY": "proxy-secret",
        "SSL_CERT_FILE": "certificate-override",
        "CODEX_HOME": "developer-secret",
        "HOME": "profile-secret",
        "UNRELATED_SECRET": "do-not-pass",
    }

    child = build_isolated_child_environment(parent, controlled)

    assert child == {
        "SystemRoot": r"C:\Windows",
        "WINDIR": r"C:\Windows",
        "TEMP": str(controlled),
        "TMP": str(controlled),
        "PYTHONUTF8": "1",
    }


@pytest.mark.parametrize("name", ["APCA_API_KEY_ID", "apca_api_secret_key"])
def test_parent_rejects_ambient_alpaca_variables(tmp_path, name) -> None:
    controlled = tmp_path / "controlled"
    controlled.mkdir()
    parent = {"SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows", name: "x"}

    with pytest.raises(IsolatedCaptureLauncherError):
        build_isolated_child_environment(parent, controlled)


def test_launcher_creates_suspended_assigns_before_resume_and_closes_handles(
    tmp_path,
) -> None:
    _, config = _launcher_case(tmp_path)
    api = FakeProcessApi(exit_code=8)
    parent = {"SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows"}

    execution = launch_isolated_capture_child(
        config,
        parent_environment=parent,
        native_api=api,
    )

    assert api.created == 1
    assert api.job_limits == 1
    assert api.assignments == 1
    assert api.resumes == 1
    assert api.inherit_handles is False
    assert api.environment == build_isolated_child_environment(
        parent, config.controlled_temp_directory
    )
    assert api.arguments == (
        str(config.approved_child_script),
        "--request",
        str(config.child_request_path),
    )
    assert set(api.closed) == {"thread-handle", "process-handle", "job-handle"}
    assert execution.child_classification is (
        IsolatedCaptureChildClassification.INTERNAL_FAILED
    )
    assert len(list(config.process_evidence_directory.glob("*.json"))) == 3


def test_timeout_terminates_job_and_surfaces_stream_overflow(tmp_path) -> None:
    _, config = _launcher_case(tmp_path)
    api = FakeProcessApi(
        waits=[False, True],
        exit_code=9,
        stdout=b"x" * (64 * 1024 + 1),
        stderr=b"y" * (64 * 1024 + 1),
    )

    execution = launch_isolated_capture_child(
        config,
        parent_environment={
            "SystemRoot": r"C:\Windows",
            "WINDIR": r"C:\Windows",
        },
        native_api=api,
    )

    assert api.terminations == 1
    assert execution.child_classification is None
    assert execution.termination_record.timed_out
    assert execution.termination_record.process_tree_result is (
        ProcessTreeTerminationResult.TERMINATED_AND_CONFIRMED
    )
    assert execution.termination_record.diagnostics == (
        "WALL_TIMEOUT",
        "PROCESS_TREE_TERMINATED",
        "STDOUT_LIMIT_EXCEEDED",
        "STDERR_LIMIT_EXCEEDED",
    )


def test_resume_failure_terminates_job_and_closes_every_handle(tmp_path) -> None:
    _, config = _launcher_case(tmp_path)
    api = ResumeFailureApi(waits=[True])

    execution = launch_isolated_capture_child(
        config,
        parent_environment={
            "SystemRoot": r"C:\Windows",
            "WINDIR": r"C:\Windows",
        },
        native_api=api,
    )

    assert api.resumes == 1
    assert api.terminations == 1
    assert set(api.closed) == {"thread-handle", "process-handle", "job-handle"}
    assert execution.child_classification is None
    assert execution.termination_record.process_tree_result is (
        ProcessTreeTerminationResult.TERMINATED_AND_CONFIRMED
    )
    assert execution.termination_record.diagnostics == (
        "LAUNCH_OPERATION_FAILED",
        "PROCESS_TREE_TERMINATED",
    )
