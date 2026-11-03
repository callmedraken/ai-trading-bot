"""Exact-owned P6 kill operator. No placement authority or arbitrary ID input."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Protocol

from trading_bot.desktop_live.execution import (
    LIVE_ATTEMPT_MARKER,
    LIVE_LIFECYCLE_PATH,
    LiveStateStore,
    create_live_transport,
    kill_owned_order,
    plan_from_sanitized,
)
from trading_bot.desktop_live.models import LiveExecutionPlan, LivePlanState
from trading_bot.desktop_live.ownership import OwnedOrderBinding, load_binding
from trading_bot.desktop_paper.robinhood_read import (
    EquityOrderObservation,
    resolve_account,
)
from trading_bot.desktop_paper.robinhood_reconciliation import (
    ReadBoundary,
    RobinhoodReconciliationSnapshot,
    observe_robinhood_baseline,
)

KILL_ARM_ENV = "AI_TRADING_BOT_P6_KILL_ARM"
KILL_ARM_VALUE = "CANCEL_EXACT_OWNED_P6_ORDER"
WORKING = frozenset(
    {"new", "queued", "confirmed", "open", "pending", "submitted", "partially_filled"}
)
TERMINAL = frozenset({"filled", "canceled", "cancelled", "rejected"})


class KillTransport(ReadBoundary, Protocol):
    def cancel_equity_order(self, arguments: dict[str, object]) -> object: ...


@dataclass(frozen=True, slots=True)
class KillResult:
    status: str
    reason: str
    effect_disposition: str
    cancel_call_count: int = 0
    attempt_consumed: bool = False
    pre_cancel_state: str | None = None
    post_cancel_state: str | None = None
    cumulative_fill_quantity: str | None = None
    spy_position_quantity: str | None = None
    classification: str = "UNRECONCILED"
    place_call_count: int = 0
    automatic_retry: str = "NO_AUTOMATIC_RETRY"
    additional_buy_enabled: bool = False


def prepare_kill(
    plan: LiveExecutionPlan,
    *,
    plan_digest: str,
    source_head: str,
    source_tree: str,
    state_store: LiveStateStore,
    arm_token: str | None,
) -> OwnedOrderBinding:
    """All local interlocks, before any transport/credential construction."""
    checked = plan_from_sanitized(plan.sanitized())
    if checked != plan or plan_digest != plan.plan_sha256:
        raise ValueError("KILL_PLAN_DIGEST_INVALID")
    if plan.state is not LivePlanState.READY or (
        plan.source_head,
        plan.source_tree,
    ) != (source_head, source_tree):
        raise ValueError("KILL_READY_SOURCE_PLAN_REQUIRED")
    if (
        plan.position_baseline_count,
        plan.order_baseline_count,
        plan.spy_position_quantity,
    ) != (0, 0, Decimal("0")):
        raise ValueError("KILL_PLAN_BASELINE_INVALID")
    binding = load_binding(state_store.ownership_path, plan)
    if arm_token != KILL_ARM_VALUE:
        raise ValueError("KILL_DISARMED")
    return binding


def _state(order: EquityOrderObservation) -> str:
    value = order.state.casefold().replace("-", "_")
    return value.upper() if value in WORKING | TERMINAL else "UNKNOWN"


def _owned(
    snapshot: RobinhoodReconciliationSnapshot,
    binding: OwnedOrderBinding,
    plan: LiveExecutionPlan,
) -> EquityOrderObservation:
    if snapshot.account_fingerprint != plan.account_fingerprint:
        raise ValueError("KILL_ACCOUNT_DRIFT")
    matches = tuple(
        o for o in snapshot.orders if o.order_id == binding.provider_order_id
    )
    if len(matches) != 1:
        raise ValueError("KILL_EXACT_ORDER_ABSENT")
    order = matches[0]
    # Ownership comes ONLY from the durable binding. These are corroboration.
    from zoneinfo import ZoneInfo

    if (order.symbol, order.side, order.placed_agent) != ("SPY", "buy", "agentic") or (
        order.created_at.astimezone(ZoneInfo("America/New_York")).date().isoformat()
        != plan.target_session
    ):
        raise ValueError("KILL_ORDER_SEMANTICS_INVALID")
    return order


def _facts(
    snapshot: RobinhoodReconciliationSnapshot, order: EquityOrderObservation
) -> tuple[str, str]:
    position = next(
        (p.quantity for p in snapshot.positions if p.symbol == "SPY"), Decimal("0")
    )
    return str(order.cumulative_quantity), str(position)


def _terminal(
    snapshot: RobinhoodReconciliationSnapshot,
    order: EquityOrderObservation,
    plan: LiveExecutionPlan,
    *,
    calls: int,
    consumed: bool,
    pre: str,
    minimum_fill: Decimal,
) -> KillResult | None:
    state = _state(order)
    if state.casefold() not in TERMINAL:
        return None
    fill, position = _facts(snapshot, order)
    quantity = order.cumulative_quantity
    with localcontext() as context:
        context.prec = 256
        expected_position = plan.spy_position_quantity + quantity
    consistent = (
        quantity >= minimum_fill
        and Decimal(position) == expected_position
        and (
            state != "FILLED"
            or (quantity > 0 and (order.quantity is None or order.quantity == quantity))
        )
        and (state != "REJECTED" or quantity == 0)
    )
    if not consistent:
        return KillResult(
            "STOPPED",
            "TERMINAL_POSITION_OR_FILL_MISMATCH",
            "MAY_HAVE_OCCURRED" if calls or consumed else "NO_MUTATION",
            calls,
            consumed,
            pre,
            state,
            fill,
            position,
        )
    classification = {
        "FILLED": "TERMINAL_FILLED",
        "REJECTED": "TERMINAL_REJECTED",
        "CANCELED": "TERMINAL_CANCELED_REMAINDER" if quantity else "TERMINAL_CANCELED",
        "CANCELLED": "TERMINAL_CANCELED_REMAINDER" if quantity else "TERMINAL_CANCELED",
    }[state]
    return KillResult(
        "PASS",
        "TERMINAL_BROKER_OBSERVATION",
        "RECONCILED",
        calls,
        consumed,
        pre,
        state,
        fill,
        position,
        classification,
    )


def observe_and_kill(
    plan: LiveExecutionPlan,
    *,
    binding: OwnedOrderBinding,
    transport: KillTransport,
    state_store: LiveStateStore,
    now: datetime,
) -> KillResult:
    """One pre-observation, at most one cancel, one immediate post-observation."""
    marker = state_store.marker.with_name("cancel-attempt.json")
    consumed = True
    pre = None
    fill = position = None
    try:
        consumed = marker.exists()
        # Reload durable ownership so an in-memory caller cannot supply a target.
        if binding != load_binding(state_store.ownership_path, plan):
            raise ValueError("KILL_BINDING_CHANGED")
        account = resolve_account(transport.get_accounts())
        if account.fingerprint != plan.account_fingerprint:
            raise ValueError("KILL_ACCOUNT_DRIFT")
        before = observe_robinhood_baseline(transport, observed_at=now)
        order = _owned(before, binding, plan)
        pre = _state(order)
        fill, position = _facts(before, order)
        terminal = _terminal(
            before,
            order,
            plan,
            calls=0,
            consumed=consumed,
            pre=pre,
            minimum_fill=Decimal("0"),
        )
        if terminal is not None:
            return terminal
        if pre.casefold() not in WORKING:
            raise ValueError("KILL_ORDER_STATE_UNKNOWN")
    except Exception:
        return KillResult(
            "STOPPED" if consumed else "BLOCKED",
            "KILL_OBSERVATION_REJECTED",
            "MAY_HAVE_OCCURRED" if consumed else "NO_MUTATION",
            0,
            consumed,
            pre,
            None,
            fill,
            position,
        )

    try:
        attempt = kill_owned_order(
            plan=plan,
            transport=transport,
            account_number=account.account_number,
            kill_latched=True,
            state_store=state_store,
            expected_binding=binding,
        )
    except Exception:
        # The primitive catches every post-invocation exception. A failure to
        # inspect/resolve its pre-call marker must still forbid automatic retry.
        return KillResult(
            "STOPPED",
            "CANCEL_ADMISSION_UNAVAILABLE",
            "MAY_HAVE_OCCURRED",
            0,
            True,
            pre,
            None,
            fill,
            position,
        )
    if attempt.reason != "EXACT_OWNED_ORDER_CANCEL_REQUESTED":
        return KillResult(
            "STOPPED" if attempt.attempt_consumed else "BLOCKED",
            attempt.reason,
            attempt.effect_disposition,
            attempt.cancel_call_count,
            attempt.attempt_consumed,
            pre,
            None,
            fill,
            position,
        )
    try:
        after = observe_robinhood_baseline(transport, observed_at=now)
        observed = _owned(after, binding, plan)
        post = _state(observed)
        terminal = _terminal(
            after,
            observed,
            plan,
            calls=1,
            consumed=True,
            pre=pre,
            minimum_fill=order.cumulative_quantity,
        )
        if terminal is not None:
            return terminal
        fill, position = _facts(after, observed)
        return KillResult(
            "STOPPED",
            "CANCEL_NOT_TERMINALLY_RECONCILED",
            "MAY_HAVE_OCCURRED",
            1,
            True,
            pre,
            post,
            fill,
            position,
        )
    except Exception:
        return KillResult(
            "STOPPED",
            "POST_CANCEL_OBSERVATION_REJECTED",
            "MAY_HAVE_OCCURRED",
            1,
            True,
            pre,
            None,
            fill,
            position,
        )


def _write_create_only(path: Path, body: dict[str, object]) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(body, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def _state_store() -> LiveStateStore:
    return LiveStateStore(LIVE_ATTEMPT_MARKER, LIVE_LIFECYCLE_PATH)


def run_operator(
    *,
    repo_root: Path,
    plan_path: Path,
    plan_digest: str,
    evidence_directory: Path,
) -> dict[str, object]:
    """Protected entry point; tests substitute admission, state and transport."""
    from scripts.arch147_p6_tiny_live_source import require_kill_source

    try:
        head, tree = require_kill_source(repo_root, evidence_directory)
        raw = json.loads(plan_path.read_text(encoding="utf-8"))
        plan = plan_from_sanitized(raw.get("result", {}).get("plan", raw.get("plan")))
        store = _state_store()
        binding = prepare_kill(
            plan,
            plan_digest=plan_digest,
            source_head=head,
            source_tree=tree,
            state_store=store,
            arm_token=os.environ.get(KILL_ARM_ENV),
        )
        # Reserve a fresh external destination and durable sanitized intent BEFORE
        # transport construction. A reused/partial destination blocks all calls.
        evidence_directory.mkdir(parents=True, exist_ok=False)
        identity = {
            "schema": "arch147-p6-kill-evidence/v1",
            "source_head": head,
            "source_tree": tree,
            "plan_sha256": plan.plan_sha256,
            "local_order_id": binding.local_order_id,
            "provider_order_sha256": binding.provider_order_sha256,
        }
        _write_create_only(
            evidence_directory / "attempt.json",
            {
                **identity,
                "status": "STARTED",
                "automatic_retry": "NO_AUTOMATIC_RETRY",
            },
        )
    except Exception:
        return asdict(
            KillResult("BLOCKED", "KILL_LOCAL_ADMISSION_REJECTED", "NO_MUTATION")
        )
    try:
        transport = create_live_transport()
    except Exception:
        result = KillResult("BLOCKED", "KILL_TRANSPORT_UNAVAILABLE", "NO_MUTATION")
    else:
        result = observe_and_kill(
            plan,
            binding=binding,
            transport=transport,
            state_store=store,
            now=datetime.now(UTC),
        )
    report = {**identity, **asdict(result)}
    try:
        _write_create_only(evidence_directory / "report.json", report)
    except Exception:
        # Keep the effect/consumption facts even if the evidence disk fails.
        report = {**report, "status": "STOPPED", "evidence_persistence": "FAILED"}
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    report = run_operator(
        repo_root=Path(__file__).resolve().parents[3],
        plan_path=args.plan,
        plan_digest=args.plan_sha256,
        evidence_directory=args.evidence_dir,
    )
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
