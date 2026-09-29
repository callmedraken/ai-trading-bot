"""Architecture-128 final fixed protected replacement operator.

The read-only preflight mode never constructs a production writer or invokes the
native rename transport. The protected execution mode requires two exact
interlocks and remains filesystem-only: no scheduler mutation, activation,
source launch, provider, Paper-v2, broker, or live-trading authority exists here.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from typing import Final

from scripts import d10_arch128_r3_preflight as r3
from scripts import d10_arch128_r4_orchestration as r4c
from scripts import d10_arch128_r4_replacement as r4
from scripts import d10_arch128_r4_windows as r4w
from scripts.d10_protected_deployment_windows import WindowsCngVerifier

SCHEMA: Final = "arch128-r4-protected-replacement/v1"
READ_ONLY_FLAG: Final = "--read-only-preflight"
EXECUTE_FLAG: Final = "--execute-reviewed-r4-protected-replacement"
AUTH_ENV: Final = "AI_TRADING_BOT_ARCH128_R4_AUTHORIZATION"
AUTH_VALUE: Final = "ARCH128_R4_PROTECTED_REPLACEMENT_AUTHORIZED"


def _base(mode: str) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "mode": mode,
        "status": "BLOCKED",
        "old_deployment_id": r4.OLD_DEPLOYMENT_ID,
        "new_deployment_id": r4.NEW_DEPLOYMENT_ID,
        "new_source_head": r4.NEW_IDENTITY.certified_source_head,
        "new_source_tree": r4.NEW_IDENTITY.certified_source_tree,
        "new_manifest_sha256": r4.NEW_IDENTITY.manifest_sha256,
        "new_signature_sha256": r4.NEW_IDENTITY.detached_signature_sha256,
        "scheduler_mutation": "NOT_RUN",
        "activation": "NOT_RUN",
        "source_launch": "NOT_RUN",
        "provider": "NOT_RUN",
        "Paper-v2": "NOT_RUN",
        "broker": "NOT_RUN",
        "live": "NOT_RUN",
    }


def _read_only_preflight() -> dict[str, object]:
    result = _base("READ_ONLY_PREFLIGHT")
    result["production_filesystem_mutation"] = "NOT_RUN"
    result["rename_1"] = "NOT_RUN"
    result["rename_2"] = "NOT_RUN"
    try:
        verifier = WindowsCngVerifier()
        signed = r4c.load_fixed_signed_material(verifier)
        reader = r4w.WindowsArch128ReadOnlyReader()
        observation = r4c.observe_pre_stage(
            reader,
            verifier,
            r3._observe_scheduler,
        )
        scheduler = dict(observation.scheduler)
        if (
            signed.material.attestation.deployment_id != r4.NEW_DEPLOYMENT_ID
            or signed.material.manifest.digest != r4.NEW_IDENTITY.manifest_sha256
            or scheduler.get("enabled") is not False
            or scheduler.get("task_state") != 1
        ):
            raise RuntimeError("arch128_operator_preflight_identity_drift")
    except Exception as exc:
        result["reason"] = type(exc).__name__
        result["detail"] = str(exc)
        return result

    result.update(
        {
            "status": "PASS",
            "halted_canonical": "EXACT_AND_VERIFIED",
            "old_final_lease": "EXACT_AND_VERIFIED",
            "historical_s5r8_retired": "ABSENT_AND_VERIFIED",
            "new_s5r10_retired_destination": "ABSENT_AND_VERIFIED",
            "new_arch128_staging_destination": "ABSENT_AND_VERIFIED",
            "scheduler_enabled": False,
            "scheduler_task_state": 1,
            "scheduler_xml_sha256": scheduler["xml_sha256"],
            "material_lineage": "E6_R1_R2_EXACT_AND_VERIFIED",
        }
    )
    return result


def _session_evidence(result: r4.ReplacementResult) -> dict[str, object]:
    return {
        "phase": result.phase.value,
        "rename_1": result.old_to_retired.value,
        "rename_2": result.staging_to_canonical.value,
    }


def _execute_once() -> dict[str, object]:
    result = _base("PROTECTED_REPLACEMENT")
    result["production_filesystem_mutation"] = "NOT_STARTED"
    result["rename_1"] = "NOT_RUN"
    result["rename_2"] = "NOT_RUN"
    phase = "READ_ONLY_MATERIAL"

    try:
        verifier = WindowsCngVerifier()
        signed = r4c.load_fixed_signed_material(verifier)
        reader = r4w.WindowsArch128ReadOnlyReader()
        writer = r4w.WindowsArch128StagingBackend()

        phase = "STAGING"
        result["production_filesystem_mutation"] = "POSSIBLE_PARTIAL_STAGING"
        admission = r4c._construct_staging(
            signed,
            writer,
            reader,
            verifier,
            r3._observe_scheduler,
        )
        result["production_filesystem_mutation"] = "STAGING_CREATED_AND_VERIFIED"

        phase = "RENAME_OLD_TO_RETIRED"
        session = r4c._ReplacementSession(
            reader,
            verifier,
            r3._observe_scheduler,
            admission,
            r4w.rename_fixed_step,
        )
        first = session.retire_old()
        result.update(_session_evidence(first))
        if first.phase is not r4.Phase.READY_TO_PUBLISH_NEW:
            result["status"] = "STOPPED_INDETERMINATE"
            result["stop_phase"] = phase
            return result

        phase = "RENAME_STAGING_TO_CANONICAL"
        second = session.publish_new()
        result.update(_session_evidence(second))
        if second.phase is not r4.Phase.COMPLETE:
            result["status"] = "STOPPED_INDETERMINATE"
            result["stop_phase"] = phase
            return result
    except Exception as exc:
        result["status"] = "STOPPED"
        result["stop_phase"] = phase
        result["reason"] = type(exc).__name__
        result["detail"] = str(exc)
        return result

    result.update(
        {
            "status": "PASS",
            "production_filesystem_mutation": "REPLACEMENT_COMPLETE_AND_VERIFIED",
            "halted_s5r10_retired": "EXACT_AND_VERIFIED",
            "new_canonical": "EXACT_AND_VERIFIED",
            "new_staging_destination": "ABSENT_AND_VERIFIED",
            "scheduler_state": "DISABLED_NONRUNNING_EXACT",
        }
    )
    return result


def _dispatch(
    arguments: tuple[str, ...],
    environment: Mapping[str, str],
) -> dict[str, object]:
    if arguments == (READ_ONLY_FLAG,):
        return _read_only_preflight()

    if arguments != (EXECUTE_FLAG,):
        result = _base("INTERLOCK")
        result["production_filesystem_mutation"] = "NOT_RUN"
        result["rename_1"] = "NOT_RUN"
        result["rename_2"] = "NOT_RUN"
        result["reason"] = "execution_flag_not_exact"
        return result

    if environment.get(AUTH_ENV) != AUTH_VALUE:
        result = _base("PROTECTED_REPLACEMENT")
        result["production_filesystem_mutation"] = "NOT_RUN"
        result["rename_1"] = "NOT_RUN"
        result["rename_2"] = "NOT_RUN"
        result["reason"] = "authorization_interlock_not_exact"
        return result

    return _execute_once()


def main() -> int:
    result = _dispatch(tuple(sys.argv[1:]), os.environ)
    print(json.dumps(result, indent=2, sort_keys=True))

    if result["status"] != "PASS":
        return 1

    if result["mode"] == "READ_ONLY_PREFLIGHT":
        print("D10_ARCH128_R4_OPERATOR_READONLY_PREFLIGHT=PASS")
    else:
        print("D10_ARCH128_R4_PROTECTED_REPLACEMENT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
