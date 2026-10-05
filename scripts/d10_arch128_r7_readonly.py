"""Architecture-128 R7A read-only activation admission.

This module has no evidence writer, scheduler writer, lease writer, credential
prompt, process launch, provider, Paper-v2, broker, or live-trading authority.
It only reuses the accepted Architecture-128 COMPLETE-state observer.
"""

from __future__ import annotations

from typing import Final

from scripts import d10_arch128_r3_preflight as r3
from scripts import d10_arch128_r4_orchestration as r4c
from scripts import d10_arch128_r4_replacement as r4
from scripts import d10_arch128_r4_windows as r4w
from scripts.d10_protected_deployment_windows import WindowsCngVerifier

SCHEMA: Final = "architecture-128-r7-readonly-admission/v1"


def _base() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "status": "BLOCKED",
        "production_filesystem_mutation": "NOT_RUN",
        "evidence_provision": "NOT_RUN",
        "scheduler_mutation": "NOT_RUN",
        "lease_publication": "NOT_RUN",
        "manual_task_start": "NOT_RUN",
        "source_launch": "NOT_RUN",
        "provider": "NOT_RUN",
        "Paper-v2": "NOT_RUN",
        "broker": "NOT_RUN",
        "live": "NOT_RUN",
    }


def preflight() -> dict[str, object]:
    """Re-prove the exact inert post-R4 state without constructing writers."""

    result = _base()
    try:
        observation = r4c.observe_post(
            r4w.WindowsArch128ReadOnlyReader(),
            WindowsCngVerifier(),
            r3._observe_scheduler,
            r4.NamespaceState.COMPLETE,
        )
        scheduler = dict(observation.scheduler)
        if scheduler.get("enabled") is not False or scheduler.get("task_state") != 1:
            raise RuntimeError("arch128_r7_scheduler_not_inert")
    except Exception as exc:
        result["reason"] = type(exc).__name__
        result["detail"] = str(exc)
        return result

    result.update(
        status="PASS",
        canonical_deployment="NEW_EXACT_AND_VERIFIED",
        canonical_deployment_id=r4.NEW_DEPLOYMENT_ID,
        old_incident_retired="EXACT_AND_VERIFIED",
        historical_s5r8_retired="ABSENT_AND_VERIFIED",
        replacement_staging="ABSENT_AND_VERIFIED",
        evidence_root="EXACT_EMPTY_AND_VERIFIED",
        activation_lease="FINAL_INSTALLING_TMP_ABSENT_AND_VERIFIED",
        scheduler="EXACT_DISABLED_NONRUNNING_AND_VERIFIED",
        activation_plan="DERIVED_ONLY_AT_PROTECTED_EXECUTION",
    )
    return result
