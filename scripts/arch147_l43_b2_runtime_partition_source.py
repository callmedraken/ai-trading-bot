"""Explicit manual runner for the Architecture 147 L43 B2 observation."""

from __future__ import annotations

import asyncio
from uuid import uuid4

_EVIDENCE_PREFIX = "arch147-agent-initiated-runtime-partition-"


def run_preflight() -> dict[str, object]:
    """Dispatch the one-use observer only from its separately named checkpoint."""
    from trading_bot.robinhood_mcp import (
        agent_initiated_runtime_partition_observer as b2,
    )

    evidence_dir = b2._EVIDENCE_ROOT / (_EVIDENCE_PREFIX + uuid4().hex)
    observer = b2.RobinhoodAgentInitiatedRuntimePartitionObserver()
    try:
        result = asyncio.run(observer.observe(evidence_dir=evidence_dir))
    except (Exception, asyncio.CancelledError, KeyboardInterrupt):
        return {
            "status": "BLOCKED",
            "reason": "OBSERVER_EXCEPTION",
            "production_order_scope_authority": "NOT_GRANTED",
        }
    captured = (
        result.evidence_file is not None
        and result.source_recheck_status == "PASS"
        and result.status
        in {
            b2.AgentInitiatedRuntimePartitionObservationStatus.PROVEN,
            b2.AgentInitiatedRuntimePartitionObservationStatus.NOT_PROVEN,
        }
    )
    return {
        "status": "PASS" if captured else "BLOCKED",
        "reason": result.reason,
        "observer_status": result.status.value,
        "observer_evidence_path": (
            None if result.evidence_file is None else str(result.evidence_file)
        ),
        "observer_evidence_sha256": result.evidence_sha256,
        "attempt_counters": result.attempt_counters,
        "source_head": result.source_head,
        "source_tree": result.source_tree,
        "source_recheck_status": result.source_recheck_status,
        "production_order_scope_authority": "NOT_GRANTED",
        "provider_effects": "ZERO",
    }


__all__ = ["run_preflight"]
