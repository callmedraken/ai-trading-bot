"""Architecture-128 R7B protected-dispatch contract.

This module freezes the R7 authorization interlock and composition boundary only.
It intentionally contains no Windows evidence writer, Trading-token acquisition,
scheduler transport, activation-lease writer, process launch, provider, Paper-v2,
broker, or live-trading implementation. The unified checkpoint runner MUST NOT
register this module as an executable checkpoint until the concrete R7C host
bindings are separately source-reviewed.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Final

from scripts import d10_arch128_r6_reactivation as r6

SCHEMA: Final = "architecture-128-r7-protected-dispatch/v1"
EXECUTE_FLAG: Final = "--execute-reviewed-r7-protected-activation"
AUTH_ENV: Final = "AI_TRADING_BOT_ARCH128_R7_AUTHORIZATION"
AUTH_VALUE: Final = "ARCH128_R7_PROTECTED_ACTIVATION_AUTHORIZED"


R7Factory = Callable[[], tuple[r6.Boundaries, Callable[[], datetime]]]


def _base() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "status": "BLOCKED",
        "stage": "EXECUTION_INTERLOCK",
        "authorization": "NOT_ACCEPTED",
        "production_filesystem_mutation": "NOT_RUN",
        "evidence_provision": r6.MutationDisposition.NOT_RUN,
        "scheduler_mutation": r6.MutationDisposition.NOT_RUN,
        "lease_publication": r6.MutationDisposition.NOT_RUN,
        "manual_task_start": "NOT_RUN",
        "source_launch": "NOT_RUN",
        "provider": "NOT_RUN",
        "Paper-v2": "NOT_RUN",
        "broker": "NOT_RUN",
        "live": "NOT_RUN",
        "automatic_retry": False,
        "automatic_rollback": False,
        "automatic_cleanup": False,
        "reconciliation_required": False,
    }


def _dispatch(
    argv: Sequence[str],
    environment: Mapping[str, str],
    factory: R7Factory,
) -> dict[str, object]:
    """Compose R6 only after the exact one-shot R7 authorization interlock."""

    result = _base()
    if tuple(argv) != (EXECUTE_FLAG,) or environment.get(AUTH_ENV) != AUTH_VALUE:
        return result

    result["authorization"] = "ACCEPTED"
    result["stage"] = "R6_COMPOSITION"

    try:
        boundaries, clock = factory()
        primary = r6.ReactivationOperator(boundaries, clock).run(execute_r7=True)
    except (Exception, KeyboardInterrupt) as exc:
        result.update(
            status="STOPPED",
            stage="FACTORY_OR_COMPOSITION_FAILURE",
            reason=type(exc).__name__,
            detail=str(exc),
            reconciliation_required=True,
        )
        return result

    if type(primary) is not dict:
        result.update(
            status="STOPPED",
            stage="PRIMARY_RESULT_TYPE",
            reconciliation_required=True,
        )
        return result

    for field in (
        "evidence_provision",
        "scheduler_mutation",
        "lease_publication",
        "manual_task_start",
        "source_launch",
        "provider",
        "Paper-v2",
        "broker",
        "live",
        "automatic_retry",
        "automatic_rollback",
        "automatic_cleanup",
        "reconciliation_required",
    ):
        if field in primary:
            result[field] = primary[field]

    result["primary"] = primary
    result["stage"] = primary.get("stage", "UNKNOWN")
    result["status"] = primary.get("status", "STOPPED")

    if result["status"] == "PASS":
        if (
            result["stage"] != "COMPLETE"
            or result["evidence_provision"] is not r6.MutationDisposition.CALL_RETURNED
            or result["scheduler_mutation"] is not r6.MutationDisposition.CALL_RETURNED
            or result["lease_publication"]
            is not r6.MutationDisposition.PUBLISHED_VERIFIED
            or result["manual_task_start"] != "NOT_RUN"
            or result["source_launch"] != "NOT_RUN"
            or result["provider"] != "NOT_RUN"
            or result["Paper-v2"] != "NOT_RUN"
            or result["broker"] != "NOT_RUN"
            or result["live"] != "NOT_RUN"
            or result["automatic_retry"] is not False
            or result["automatic_rollback"] is not False
            or result["automatic_cleanup"] is not False
        ):
            result.update(
                status="STOPPED",
                stage="PASS_CONTRACT_MISMATCH",
                reconciliation_required=True,
            )
    return result
