from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from trading_bot.cli.windows_launch_guard import (
    LaunchGuardAclPolicy,
    LaunchGuardAcquireRequest,
    LaunchLeaseReleaseInput,
    ReleaseOperationalClassification,
    acquire_windows_launch_guard,
)
from trading_bot.cli.windows_launch_guard_smoke import main as smoke_main
from trading_bot.runtime.launch_guard import (
    LaunchGuardAcquisitionClassification,
    LaunchLeaseReleaseClassification,
    LaunchResultClassification,
    windows_mutex_name,
)
from trading_bot.runtime.scheduled_readiness import ArtifactEvidence, ScheduledPhase

pytestmark = pytest.mark.skipif(os.name != "nt", reason="requires Windows mutexes")


def _release_input(diagnostic: str) -> LaunchLeaseReleaseInput:
    return LaunchLeaseReleaseInput(
        release_classification=LaunchLeaseReleaseClassification.NORMAL,
        release_timestamp_utc="2026-07-30T19:00:02Z",
        monotonic_duration_nanoseconds=2_000_000,
        result_classification=LaunchResultClassification.NOT_RUN,
        result_diagnostic=diagnostic,
        process_exit_code=0,
        release_policy="windows-local-single-writer-v1",
    )


def _request(root: Path, epoch: UUID, diagnostic: str) -> LaunchGuardAcquireRequest:
    return LaunchGuardAcquireRequest(
        audit_root=root,
        scheduled_launch_id=UUID("397e22f6-b236-50a5-89fb-cb9a9b130167"),
        authority_epoch_id=epoch,
        scheduled_phase=ScheduledPhase.OPERATION,
        machine_authority_id=UUID("61f74efb-272c-5898-a8fb-2903d59dca3f"),
        boot_evidence="windows-integration-boot",
        process_id=os.getpid(),
        process_creation_timestamp_utc="2026-07-30T19:00:00Z",
        user_sid="S-1-5-21-1-2-3-1001",
        executable_release=ArtifactEvidence(
            artifact_id=UUID("04e1ac53-90db-5f7b-a32a-76b8e3c42102"),
            sha256="9" * 64,
            byte_length=99,
        ),
        acquisition_timestamp_utc="2026-07-30T19:00:01Z",
        max_runtime_seconds=30,
        launch_policy="windows-local-single-writer-v1",
        timeout_seconds=2,
        acl_policy=LaunchGuardAclPolicy.ALLOW_DEFAULT_DACL,
        context_release_input=_release_input(diagnostic),
    )


def test_real_windows_acquisition_release_and_thread_contention(
    tmp_path: Path,
) -> None:
    request = _request(
        tmp_path,
        UUID("b2e980e5-0280-5285-8738-c56f365c9390"),
        "THREAD_OWNER_RELEASE",
    )
    owner_ready = threading.Event()
    owner_may_release = threading.Event()
    outcomes: list[Any] = []

    def own_mutex() -> None:
        acquired = acquire_windows_launch_guard(request)
        outcomes.append(acquired)
        if acquired.ownership is None:
            owner_ready.set()
            return
        owner_ready.set()
        owner_may_release.wait(5)
        outcomes.append(
            acquired.ownership.release(request.context_release_input)  # type: ignore[arg-type]
        )

    thread = threading.Thread(target=own_mutex)
    thread.start()
    assert owner_ready.wait(5)
    first = outcomes[0]
    assert first.classification is (LaunchGuardAcquisitionClassification.ACQUIRED)

    contender = acquire_windows_launch_guard(
        replace(request, timeout_seconds=0),
    )

    assert contender.classification is LaunchGuardAcquisitionClassification.ALREADY_HELD
    assert contender.ownership is None
    owner_may_release.set()
    thread.join(5)
    assert not thread.is_alive()
    assert outcomes[-1].classification is ReleaseOperationalClassification.RELEASED


def test_real_windows_abandoned_owner_is_acquired_but_unsafe(
    tmp_path: Path,
) -> None:
    epoch = UUID("f6538bbf-5443-51f4-8dc5-c33587897abd")
    mutex_name = windows_mutex_name(epoch)
    child_code = (
        "import ctypes,os,sys,time;"
        "k=ctypes.WinDLL('kernel32',use_last_error=True);"
        "k.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_wchar_p];"
        "k.CreateMutexW.restype=ctypes.c_void_p;"
        "h=k.CreateMutexW(None,True,sys.argv[1]);"
        "print('READY' if h else f'ERROR:{ctypes.get_last_error()}',flush=True);"
        "time.sleep(0.5);"
        "os._exit(0)"
    )
    child = subprocess.Popen(
        [sys.executable, "-c", child_code, mutex_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert child.stdout is not None
    ready = child.stdout.readline().strip()
    assert ready == "READY"

    acquired = acquire_windows_launch_guard(
        _request(tmp_path, epoch, "ABANDONED_OWNER_RELEASE"),
    )

    child.wait(timeout=5)
    assert (
        acquired.classification
        is LaunchGuardAcquisitionClassification.ABANDONED_ACQUIRED
    )
    assert acquired.ownership is not None
    released = acquired.ownership.release(_release_input("ABANDONED_OWNER_RELEASE"))
    assert released.classification is ReleaseOperationalClassification.RELEASED


def test_real_windows_cli_smoke_acquires_publishes_and_releases(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    release_input = tmp_path / "release-input.json"
    release_input.write_text(
        json.dumps(
            {
                "monotonic_duration_nanoseconds": 10,
                "process_exit_code": 0,
                "release_classification": "NORMAL",
                "release_policy": "windows-local-single-writer-v1",
                "release_timestamp_utc": "2026-07-30T20:00:02Z",
                "result_classification": "NOT_RUN",
                "result_diagnostic": "CLI_SMOKE_RELEASE",
            }
        ),
        encoding="utf-8",
    )

    result = smoke_main(
        [
            "--authority-epoch-id",
            "8a39e78a-47d8-50b9-a427-c102abc91e1e",
            "--scheduled-launch-id",
            "89a3184a-05ef-5228-8664-d26f31ed03c9",
            "--phase",
            "OPERATION",
            "--machine-authority-id",
            "71abfbb7-ae72-54fc-b049-3ea87879dd32",
            "--boot-evidence",
            "windows-cli-smoke-boot",
            "--process-id",
            str(os.getpid()),
            "--process-creation-timestamp",
            "2026-07-30T20:00:00Z",
            "--user-sid",
            "S-1-5-21-1-2-3-1001",
            "--executable-release-id",
            "918a8cd2-b8fd-5334-8df3-b62eab72e311",
            "--executable-release-sha256",
            "7" * 64,
            "--executable-release-byte-length",
            "1200",
            "--acquisition-timestamp",
            "2026-07-30T20:00:01Z",
            "--max-runtime-seconds",
            "900",
            "--timeout-seconds",
            "2",
            "--policy",
            "windows-local-single-writer-v1",
            "--output-root",
            str(tmp_path),
            "--release-evidence-input",
            str(release_input),
            "--acl-policy",
            "ALLOW_DEFAULT_DACL",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output["acquisition_classification"] == "ACQUIRED"
    assert output["release_classification"] == "RELEASED"
    assert len(list((tmp_path / "lock-events").glob("*.json"))) == 2
