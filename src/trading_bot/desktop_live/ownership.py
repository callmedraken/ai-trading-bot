"""Create-only local evidence of the exact order returned by P6 placement."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from trading_bot.desktop_live.models import LiveExecutionPlan
from trading_bot.desktop_paper.robinhood_read import text

OWNERSHIP_SCHEMA = "arch147-p6-owned-order/v1"


def local_order_id(plan: LiveExecutionPlan) -> str:
    return hashlib.sha256(
        ("p6-local-order/v1:" + plan.plan_sha256).encode("ascii")
    ).hexdigest()


def provider_order_id(value: object) -> str:
    """Accept a bounded opaque provider token, never a URL or control text."""
    value = text(value)
    if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) is None:
        raise ValueError("OWNED_PROVIDER_ID_INVALID")
    return value


@dataclass(frozen=True, slots=True)
class OwnedOrderBinding:
    schema: str
    plan_sha256: str
    local_order_id: str
    provider_order_id: str = field(repr=False)

    def __post_init__(self) -> None:
        if self.schema != OWNERSHIP_SCHEMA or any(
            not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
            for value in (self.plan_sha256, self.local_order_id)
        ):
            raise ValueError("OWNERSHIP_BINDING_INVALID")
        provider_order_id(self.provider_order_id)

    def require_plan(self, plan: LiveExecutionPlan) -> None:
        if (self.plan_sha256, self.local_order_id) != (
            plan.plan_sha256,
            local_order_id(plan),
        ):
            raise ValueError("OWNERSHIP_PLAN_MISMATCH")

    @property
    def provider_order_sha256(self) -> str:
        return hashlib.sha256(self.provider_order_id.encode("ascii")).hexdigest()


def create_binding(path: Path, plan: LiveExecutionPlan, provider_id: str) -> None:
    binding = OwnedOrderBinding(
        OWNERSHIP_SCHEMA, plan.plan_sha256, local_order_id(plan), provider_id
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    # Even an identical existing binding is never rewritten or repaired.
    with path.open("x", encoding="utf-8") as stream:
        json.dump(asdict(binding), stream, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def load_binding(path: Path, plan: LiveExecutionPlan) -> OwnedOrderBinding:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {
        "schema",
        "plan_sha256",
        "local_order_id",
        "provider_order_id",
    }:
        raise ValueError("OWNERSHIP_BINDING_INVALID")
    binding = OwnedOrderBinding(**raw)
    binding.require_plan(plan)
    return binding
