"""CLI-only smoke path for the Windows launch guard."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

from trading_bot.cli.checkpoint_lineage_config import read_safe_regular_file
from trading_bot.cli.windows_launch_guard import (
    LaunchGuardAclPolicy,
    LaunchGuardAcquireRequest,
    LaunchLeaseReleaseInput,
    ReleaseOperationalClassification,
    acquire_windows_launch_guard,
)
from trading_bot.runtime.launch_guard import (
    LaunchGuardAcquisitionClassification,
    LaunchLeaseReleaseClassification,
    LaunchResultClassification,
)
from trading_bot.runtime.scheduled_readiness import ArtifactEvidence, ScheduledPhase


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Acquire the Windows paper-authority mutex, publish lease-start "
            "evidence, then immediately publish release evidence and release it."
        )
    )
    parser.add_argument("--authority-epoch-id", type=UUID, required=True)
    parser.add_argument("--scheduled-launch-id", type=UUID, required=True)
    parser.add_argument(
        "--phase",
        choices=[phase.value for phase in ScheduledPhase],
        required=True,
    )
    parser.add_argument("--machine-authority-id", type=UUID, required=True)
    parser.add_argument("--boot-evidence", required=True)
    parser.add_argument("--process-id", type=int, required=True)
    parser.add_argument("--process-creation-timestamp", required=True)
    parser.add_argument("--user-sid", required=True)
    parser.add_argument("--executable-release-id", type=UUID, required=True)
    parser.add_argument("--executable-release-sha256", required=True)
    parser.add_argument("--executable-release-byte-length", type=int, required=True)
    parser.add_argument("--acquisition-timestamp", required=True)
    parser.add_argument("--max-runtime-seconds", type=int, required=True)
    parser.add_argument("--timeout-seconds", type=int, required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--release-evidence-input", type=Path, required=True)
    parser.add_argument(
        "--acl-policy",
        choices=[policy.value for policy in LaunchGuardAclPolicy],
        required=True,
    )
    return parser


def _reject_duplicate_key(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate release-evidence member: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"unsupported JSON constant: {value}")


def _load_release_input(path: Path) -> LaunchLeaseReleaseInput:
    payload = read_safe_regular_file(path, 16_384, "release-evidence input")
    document = json.loads(
        payload.decode("utf-8"),
        object_pairs_hook=_reject_duplicate_key,
        parse_constant=_reject_constant,
    )
    if not isinstance(document, dict):
        raise ValueError("release-evidence input must be an object")
    expected = {
        "monotonic_duration_nanoseconds",
        "process_exit_code",
        "release_classification",
        "release_policy",
        "release_timestamp_utc",
        "result_classification",
        "result_diagnostic",
    }
    if set(document) != expected:
        raise ValueError("release-evidence input members are not exact")
    release_input = LaunchLeaseReleaseInput(
        release_classification=LaunchLeaseReleaseClassification(
            document["release_classification"]
        ),
        release_timestamp_utc=str(document["release_timestamp_utc"]),
        monotonic_duration_nanoseconds=document["monotonic_duration_nanoseconds"],  # type: ignore[arg-type]
        result_classification=LaunchResultClassification(
            document["result_classification"]
        ),
        result_diagnostic=str(document["result_diagnostic"]),
        process_exit_code=document["process_exit_code"],  # type: ignore[arg-type]
        release_policy=str(document["release_policy"]),
    )
    if release_input.result_classification is not LaunchResultClassification.NOT_RUN:
        raise ValueError("smoke release result_classification must be NOT_RUN")
    return release_input


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    release_input = _load_release_input(args.release_evidence_input)
    request = LaunchGuardAcquireRequest(
        audit_root=args.output_root,
        scheduled_launch_id=args.scheduled_launch_id,
        authority_epoch_id=args.authority_epoch_id,
        scheduled_phase=ScheduledPhase(args.phase),
        machine_authority_id=args.machine_authority_id,
        boot_evidence=args.boot_evidence,
        process_id=args.process_id,
        process_creation_timestamp_utc=args.process_creation_timestamp,
        user_sid=args.user_sid,
        executable_release=ArtifactEvidence(
            artifact_id=args.executable_release_id,
            sha256=args.executable_release_sha256,
            byte_length=args.executable_release_byte_length,
        ),
        acquisition_timestamp_utc=args.acquisition_timestamp,
        max_runtime_seconds=args.max_runtime_seconds,
        launch_policy=args.policy,
        timeout_seconds=args.timeout_seconds,
        acl_policy=LaunchGuardAclPolicy(args.acl_policy),
        context_release_input=release_input,
    )
    acquired = acquire_windows_launch_guard(request)
    output: dict[str, object] = {
        "acl_enforcement": acquired.acl_enforcement.value,
        "acquisition_classification": acquired.classification.value,
        "diagnostic": acquired.diagnostic,
        "mutex_name": acquired.mutex_name,
        "native_error_code": acquired.native_error_code,
    }
    if acquired.ownership is None:
        print(json.dumps(output, sort_keys=True, separators=(",", ":")))
        return (
            2
            if acquired.classification
            is LaunchGuardAcquisitionClassification.ALREADY_HELD
            else 1
        )
    output["lease_start_id"] = str(acquired.ownership.start_record.record_id)
    released = acquired.ownership.release(release_input)
    output.update(
        {
            "lease_release_id": str(released.release_record.release_id),
            "manual_review_required": released.manual_review_required,
            "release_classification": released.classification.value,
        }
    )
    print(json.dumps(output, sort_keys=True, separators=(",", ":")))
    if (
        acquired.classification
        is LaunchGuardAcquisitionClassification.ABANDONED_ACQUIRED
    ):
        return 3
    return (
        0 if released.classification is ReleaseOperationalClassification.RELEASED else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
