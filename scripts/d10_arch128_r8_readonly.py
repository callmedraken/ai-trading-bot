"""R8 first-wake policy over the accepted Architecture-127 read-only observer.

Durable acceptance alone does not prove scheduler origin. Natural-wake acceptance
also relies on controlled operator history with no manual task start.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Final

from scripts import d10_durable_wake_evidence_observe as observer
from trading_bot.runtime.personal_desktop_d10_wake_evidence_log import (
    MAX_D10_EVIDENCE_LOG_BYTES,
)

SCHEMA: Final = "architecture-128-r8-readonly-first-wake/v1"
EXPECTED_IDENTITY: Final = {
    "schema": "personal-desktop-d10-evidence-observation/v1",
    "status": "OBSERVED",
    "deployment_id": "d2071f25-5a7c-5293-a28f-5b722c9917a2",
    "attestation_sha256": (
        "3ffe4ecf1745599e7edb233d3f08a9707a1b27384d2f050a1805ee4929ebbd71"
    ),
    "soak_id": "30e31396-9f51-57ca-a480-d2a3e9cae4a0",
    "activation_utc": "2026-09-30T22:07:24.000000Z",
    "end_utc": "2026-10-07T22:07:24.000000Z",
    "evidence_path": (
        r"F:\AITradingBot\D10\evidence\wake-30e31396-9f51-57ca-a480-d2a3e9cae4a0.jsonl"
    ),
}
OBSERVER_EFFECT_FIELDS: Final = (
    "scheduler_mutation",
    "source_launch",
    "provider",
    "Paper-v2",
    "broker",
    "live",
)
OBSERVATION_FIELDS: Final = (
    *EXPECTED_IDENTITY,
    "evidence_byte_length",
    "evidence_sha256",
    "record_count",
    "wake_count",
    "terminal",
    "terminal_kind",
    "first_observed_at_utc",
    "last_observed_at_utc",
    "last_outcome",
    "last_stop_reason",
    "last_guard_reason",
    *OBSERVER_EFFECT_FIELDS,
)


def _base() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "status": "BLOCKED",
        "production_filesystem_mutation": "NOT_RUN",
        "evidence_mutation": "NOT_RUN",
        "scheduler_mutation": "NOT_RUN",
        "lease_mutation": "NOT_RUN",
        "manual_task_start": "NOT_RUN",
        "source_launch": "NOT_RUN",
        "provider": "NOT_RUN",
        "Paper-v2": "NOT_RUN",
        "broker": "NOT_RUN",
        "live": "NOT_RUN",
    }


def _timestamp(value: object) -> datetime:
    if (
        type(value) is not str
        or re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{6})?Z",
            value,
        )
        is None
    ):
        raise ValueError("observation_timestamps_invalid")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not UTC or parsed.isoformat().replace("+00:00", "Z") != value:
        raise ValueError("observation_timestamps_invalid")
    return parsed


def preflight() -> dict[str, object]:
    """Observe once; require exactly the first accepted nonterminal wake."""
    result = _base()
    try:
        observation = observer.observe()
    except Exception:
        result.update(reason="observer_blocked", detail="Read-only observation failed.")
        return result

    reason = "observer_shape_invalid"
    try:
        if type(observation) is not dict or set(observation) != set(OBSERVATION_FIELDS):
            raise ValueError
        reason = "observation_identity_mismatch"
        if any(
            type(observation[field]) is not str or observation[field] != expected
            for field, expected in EXPECTED_IDENTITY.items()
        ):
            raise ValueError
        reason = "observer_effect_drift"
        if any(
            type(observation[field]) is not str or observation[field] != "NOT_RUN"
            for field in OBSERVER_EFFECT_FIELDS
        ):
            raise ValueError
        reason = "first_wake_not_accepted"
        if (
            type(observation["record_count"]) is not int
            or observation["record_count"] != 3
            or type(observation["wake_count"]) is not int
            or observation["wake_count"] != 1
            or observation["terminal"] is not False
            or observation["terminal_kind"] is not None
            or type(observation["last_outcome"]) is not str
            or observation["last_outcome"] not in ("COMPLETED", "NO_ACTION")
            or observation["last_stop_reason"] is not None
            or observation["last_guard_reason"] is not None
        ):
            raise ValueError
        reason = "evidence_summary_invalid"
        if (
            type(observation["evidence_byte_length"]) is not int
            or not 0 < observation["evidence_byte_length"] <= MAX_D10_EVIDENCE_LOG_BYTES
            or type(observation["evidence_sha256"]) is not str
            or re.fullmatch(r"[0-9a-f]{64}", observation["evidence_sha256"]) is None
        ):
            raise ValueError
        reason = "observation_timestamps_invalid"
        first = _timestamp(observation["first_observed_at_utc"])
        last = _timestamp(observation["last_observed_at_utc"])
        if first > last:
            raise ValueError
    except Exception:
        result.update(reason=reason, detail="First-wake observation policy blocked.")
        return result

    result.update(
        status="PASS",
        first_wake_durable_sequence="ACCEPTED",
        observation=dict(observation),
    )
    return result
