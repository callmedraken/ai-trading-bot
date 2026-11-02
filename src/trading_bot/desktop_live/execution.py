"""Explicitly armed, once-only P6 mutation and bounded reconciliation."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from trading_bot.desktop_live.configuration import TinyLivePolicy
from trading_bot.desktop_live.models import (
    LiveExecutionPlan,
    LiveExecutionReceipt,
    LiveMutationDisposition,
    LivePlanState,
    OrderReviewObservation,
    TradabilityObservation,
    parse_order_review,
)
from trading_bot.desktop_live.preflight import (
    _order_arguments,
    _source_identity,
    _target_session,
)
from trading_bot.desktop_paper.robinhood_read import resolve_account
from trading_bot.desktop_paper.robinhood_reconciliation import (
    observe_robinhood_baseline,
)

LIVE_ARM_ENV = "AI_TRADING_BOT_P6_LIVE_ARM"
LIVE_ARM_VALUE = "LIVE_SPY_MAX_10_USD"
LIVE_PLAN_DIGEST_ENV = "AI_TRADING_BOT_P6_PLAN_SHA256"
LIVE_PLAN_PATH_ENV = "AI_TRADING_BOT_P6_PLAN_PATH"
LIVE_PLAN_PATH = Path(r"F:\AI\desktop-bot-state\p6\ready-plan.json")
LIVE_STATE_ROOT = Path(r"F:\AI\desktop-bot-state\p6")
LIVE_ATTEMPT_MARKER = LIVE_STATE_ROOT / "mutation-attempt.json"
LIVE_LIFECYCLE_PATH = LIVE_STATE_ROOT / "lifecycle.jsonl"


class LiveExecutionBlocked(RuntimeError):
    """A protected execution stopped before or after a bounded effect."""


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    status: str
    receipt: LiveExecutionReceipt | None
    reason: str
    place_call_count: int
    cancel_call_count: int
    attempt_consumed: bool = False

    @property
    def effect_disposition(self) -> str:
        if self.receipt is not None:
            return "RECONCILED"
        if self.place_call_count or self.reason == "PRESERVE_CONSUMED_ATTEMPT_NO_RETRY":
            return "MAY_HAVE_OCCURRED"
        if self.attempt_consumed:
            return "LIVE_MUTATION_ATTEMPT_STARTED"
        return "NO_MUTATION"


class LiveStateStore:
    """Create-only marker and append-only sanitized lifecycle for P6."""

    def __init__(self, marker: Path, lifecycle: Path) -> None:
        self.marker = marker
        self.lifecycle = lifecycle

    def start_attempt(self, *, local_order_id: str, plan_sha256: str) -> None:
        self.marker.parent.mkdir(parents=True, exist_ok=True)
        with self.marker.open("x", encoding="utf-8") as stream:
            json.dump(
                {
                    "schema": "arch147-p6-live-attempt/v1",
                    "status": "LIVE_MUTATION_ATTEMPT_STARTED",
                    "local_order_id": local_order_id,
                    "plan_sha256": plan_sha256,
                    "automatic_retry": "NO_AUTOMATIC_RETRY",
                },
                stream,
                sort_keys=True,
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())

    def append(self, record: dict[str, object]) -> None:
        self.lifecycle.parent.mkdir(parents=True, exist_ok=True)
        with self.lifecycle.open("a", encoding="utf-8") as stream:
            json.dump(record, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())


def execute_plan(
    plan: LiveExecutionPlan,
    *,
    transport: object,
    now: datetime,
    state_store: LiveStateStore,
    source_head: str,
    source_tree: str,
    arm_token: str | None,
    plan_digest: str | None,
) -> ExecutionResult:
    """Consume one READY plan, invoke place at most once, then reconcile."""
    if arm_token != LIVE_ARM_VALUE:
        return _blocked("LIVE_DISARMED", 0, 0)
    if plan_digest != plan.plan_sha256:
        return _blocked("PLAN_DIGEST_MISMATCH", 0, 0)
    if plan.state is not LivePlanState.READY:
        return _blocked("PLAN_NOT_READY", 0, 0)
    if (plan.source_head, plan.source_tree) != (source_head, source_tree):
        return _blocked("SOURCE_IDENTITY_CHANGED", 0, 0)
    if plan_digest != plan.plan_sha256:
        return _blocked("PLAN_DIGEST_MISMATCH", 0, 0)
    now = now.astimezone(UTC)
    target, opening = _target_session(now)
    if target != plan.target_session or not opening:
        return _blocked("TARGET_SESSION_OR_OPENING_WINDOW_CHANGED", 0, 0)
    if state_store.marker.exists():
        return _blocked("PRESERVE_CONSUMED_ATTEMPT_NO_RETRY", 0, 0, consumed=True)

    account_number = resolve_account(transport.get_accounts()).account_number
    fresh = observe_robinhood_baseline(transport, observed_at=now)
    if fresh.account_fingerprint != plan.account_fingerprint:
        return _blocked("ACCOUNT_FINGERPRINT_DRIFT", 0, 0)
    if len(fresh.positions) != plan.position_baseline_count:
        return _blocked("UNEXPECTED_POSITION", 0, 0)
    if len(fresh.orders) != plan.order_baseline_count or any(
        _working(order.state) for order in fresh.orders
    ):
        return _blocked("UNEXPECTED_BROKER_ORDER", 0, 0)
    if _spy_quantity(fresh) != plan.spy_position_quantity:
        return _blocked("POSITION_DRIFT", 0, 0)
    if plan.requested_dollars > Decimal("10.00"):
        return _blocked("P6_DOLLAR_CEILING", 0, 0)

    arguments = _order_arguments(
        fresh,
        plan.requested_dollars,
        account_number,
        _idempotency_key(plan, transport),
    )
    review = parse_order_review(transport.review_equity_order(arguments))
    if (
        not review.clean
        or review.dollar_amount != plan.requested_dollars
        or review.symbol != "SPY"
        or review.side != "buy"
        or review.order_type != "market"
        or review.market_hours != "regular_hours"
        or review.time_in_force != "gfd"
    ):
        return _blocked("EXECUTION_REVIEW_DRIFT", 0, 0)

    # Resolve the callable before consuming authority; attribute lookup is not
    # a placement invocation.
    place = transport.place_equity_order
    local_order_id = _local_order_id(plan)
    try:
        state_store.start_attempt(
            local_order_id=local_order_id,
            plan_sha256=plan.plan_sha256,
        )
    except FileExistsError:
        return _blocked("PRESERVE_CONSUMED_ATTEMPT_NO_RETRY", 0, 0, consumed=True)
    except Exception:
        # Even a partial marker write consumes the attempt. If marker inspection
        # fails, preserve the uncertainty rather than allowing a retry.
        try:
            consumed = state_store.marker.exists()
        except OSError:
            consumed = True
        return ExecutionResult(
            "STOPPED" if consumed else "BLOCKED",
            None,
            "ATTEMPT_MARKER_PERSISTENCE_FAILED",
            0,
            0,
            consumed,
        )
    try:
        state_store.append(
            {
                "status": "LIVE_MUTATION_ATTEMPT_STARTED",
                "local_order_id": local_order_id,
                "plan_sha256": plan.plan_sha256,
            }
        )
    except Exception:
        return ExecutionResult("STOPPED", None, "CONSUMED_BEFORE_PLACEMENT", 0, 0, True)
    try:
        response = place(arguments)
        return _reconcile_placement(
            plan,
            response=response,
            transport=transport,
            now=now,
            state_store=state_store,
            local_order_id=local_order_id,
        )
    except Exception:
        # Placement invocation, parsing, reconciliation and lifecycle persistence
        # share one consumed boundary. A failed diagnostic write cannot erase it.
        try:
            state_store.append(
                {
                    "status": "MAY_HAVE_OCCURRED",
                    "local_order_id": local_order_id,
                    "automatic_retry": "NO_AUTOMATIC_RETRY",
                }
            )
        except Exception:
            pass
        return ExecutionResult("STOPPED", None, "MAY_HAVE_OCCURRED", 1, 0, True)


def _reconcile_placement(
    plan: LiveExecutionPlan,
    *,
    response: object,
    transport: object,
    now: datetime,
    state_store: LiveStateStore,
    local_order_id: str,
) -> ExecutionResult:
    """Reconcile an already invoked placement inside its consumed boundary."""
    provider_order_id = _provider_order_id(response)
    if provider_order_id is None:
        return ExecutionResult("STOPPED", None, "MAY_HAVE_OCCURRED", 1, 0, True)

    post = observe_robinhood_baseline(transport, observed_at=now)
    matching = tuple(
        order for order in post.orders if order.order_id == provider_order_id
    )
    if len(matching) != 1:
        return ExecutionResult("STOPPED", None, "AMBIGUOUS_PROVIDER_ORDER", 1, 0, True)
    order = matching[0]
    quantity = order.cumulative_quantity
    position_quantity = _spy_quantity(post)
    state = order.state.casefold()
    if state == "filled":
        if position_quantity <= 0 or quantity <= 0:
            return ExecutionResult(
                "STOPPED", None, "POST_TRADE_POSITION_MISMATCH", 1, 0, True
            )
        status = "FILLED"
        disposition = LiveMutationDisposition.RECONCILED
    elif state in {"rejected", "canceled", "cancelled"} and position_quantity == 0:
        status = state.upper()
        disposition = LiveMutationDisposition.RECONCILED
    else:
        return ExecutionResult(
            "STOPPED", None, "POST_TRADE_RECONCILIATION_BLOCKED", 1, 0, True
        )
    receipt = LiveExecutionReceipt(
        local_order_id,
        provider_order_id,
        status,
        plan.requested_dollars,
        quantity,
        None,
        position_quantity,
        "POST_TRADE_HISTORY_AND_POSITION_MATCHED",
        disposition,
    )
    state_store.append(
        {
            "status": "RECONCILED",
            "local_order_id": local_order_id,
            "provider_order_id": provider_order_id,
            "provider_state": status,
            "requested_dollars": str(plan.requested_dollars),
            "filled_quantity": str(quantity),
            "post_trade_position_quantity": str(position_quantity),
            "additional_buy_enabled": False,
        }
    )
    return ExecutionResult("PASS", receipt, "RECONCILED", 1, 0, True)


def kill_owned_order(
    *,
    plan: LiveExecutionPlan,
    transport: object,
    account_number: str,
    provider_order_id: str,
    kill_latched: bool,
    state_store: LiveStateStore,
) -> ExecutionResult:
    """Cancel only one exact owned open order; never liquidate a fill."""
    if not kill_latched:
        return _blocked("KILL_NOT_LATCHED", 0, 0)
    if not provider_order_id:
        return _blocked("ORDER_OWNERSHIP_AMBIGUOUS", 0, 0)
    cancel_marker = state_store.marker.with_name("cancel-attempt.json")
    if cancel_marker.exists():
        return _blocked("PRESERVE_CONSUMED_CANCEL_NO_RETRY", 0, 1)
    cancel_store = LiveStateStore(cancel_marker, state_store.lifecycle)
    try:
        cancel_store.start_attempt(
            local_order_id=_local_order_id(plan), plan_sha256=plan.plan_sha256
        )
    except FileExistsError:
        return _blocked("PRESERVE_CONSUMED_CANCEL_NO_RETRY", 0, 1)
    response = transport.cancel_equity_order(
        {"account_number": account_number, "order_id": provider_order_id}
    )
    del response
    return ExecutionResult("PASS", None, "EXACT_OWNED_ORDER_CANCEL_REQUESTED", 0, 1)


def execute() -> dict[str, object]:
    """Registered runner entry point; disarmed until both process env values match."""
    if os.environ.get(LIVE_ARM_ENV) != LIVE_ARM_VALUE:
        return {
            "status": "BLOCKED",
            "plan_state": "DISARMED",
            "effect_disposition": "NO_MUTATION",
            "place_call_count": 0,
            "cancel_call_count": 0,
        }
    plan_path = Path(os.environ.get(LIVE_PLAN_PATH_ENV, str(LIVE_PLAN_PATH)))
    if not plan_path.is_file():
        return {"status": "BLOCKED", "reason": "READY_PLAN_UNAVAILABLE"}
    try:
        body = json.loads(plan_path.read_text(encoding="utf-8"))
        raw = body.get("result", {}).get("plan", body.get("plan"))
        plan = plan_from_sanitized(raw)
        if os.environ.get(LIVE_PLAN_DIGEST_ENV) != plan.plan_sha256:
            return {"status": "BLOCKED", "reason": "PLAN_DIGEST_MISMATCH"}
        head, tree = _source_identity()
        transport = _transport()
        result = execute_plan(
            plan,
            transport=transport,
            now=datetime.now(UTC),
            state_store=LiveStateStore(LIVE_ATTEMPT_MARKER, LIVE_LIFECYCLE_PATH),
            source_head=head,
            source_tree=tree,
            arm_token=os.environ.get(LIVE_ARM_ENV),
            plan_digest=os.environ.get(LIVE_PLAN_DIGEST_ENV),
        )
    except Exception:
        return {
            "status": "BLOCKED",
            "reason": "P6_EXECUTION_REJECTED",
            "place_call_count": 0,
            "cancel_call_count": 0,
            "effect_disposition": "NO_MUTATION",
            "attempt_consumed": False,
            "automatic_retry": "NO_AUTOMATIC_RETRY",
        }

    return {
        "status": result.status,
        "reason": result.reason,
        "receipt": None if result.receipt is None else asdict(result.receipt),
        "place_call_count": result.place_call_count,
        "cancel_call_count": result.cancel_call_count,
        "effect_disposition": result.effect_disposition,
        "attempt_consumed": result.attempt_consumed,
        "automatic_retry": "NO_AUTOMATIC_RETRY",
    }


def plan_from_sanitized(raw: object) -> LiveExecutionPlan:
    """Rehydrate only the sanitized immutable plan projection."""
    if not isinstance(raw, dict) or raw.get("schema") != "arch147-p6-tiny-live-plan/v1":
        raise LiveExecutionBlocked("PLAN_SCHEMA_INVALID")
    tradability = raw.get("tradability")
    if not isinstance(tradability, dict):
        raise LiveExecutionBlocked("PLAN_TRADABILITY_MISSING")
    policy = TinyLivePolicy()
    if {
        "strategy_family": raw.get("strategy_family"),
        "strategy_version": raw.get("strategy_version"),
        "campaign_id": raw.get("campaign_id"),
        "bundle_id": raw.get("bundle_id"),
        "candidate_id": raw.get("candidate_id"),
        "symbol": raw.get("symbol"),
        "max_order_dollars": raw.get("max_order_dollars"),
        "max_gross_exposure_dollars": raw.get("max_gross_exposure_dollars"),
    } != {
        "strategy_family": policy.strategy_family,
        "strategy_version": policy.strategy_version,
        "campaign_id": str(policy.campaign_id),
        "bundle_id": str(policy.bundle_id),
        "candidate_id": str(policy.candidate_id),
        "symbol": str(policy.symbol),
        "max_order_dollars": "10.00",
        "max_gross_exposure_dollars": "10.00",
    }:
        raise LiveExecutionBlocked("PLAN_POLICY_INVALID")
    review_digest = raw.get("review_digest")
    review = None
    if review_digest is not None:
        review = OrderReviewObservation(
            "SPY",
            "buy",
            "market",
            Decimal(str(raw["requested_dollar_amount"])),
            "regular_hours",
            "gfd",
            (),
            str(review_digest),
        )
    plan = LiveExecutionPlan.create(
        source_head=raw["source_head"],
        source_tree=raw["source_tree"],
        policy=policy,
        observation_basis=raw["observation_basis"],
        target_session=raw["target_session"],
        previous_completed_session=raw["previous_completed_session"],
        signal_values_digest=raw["signal_values_digest"],
        decision=raw["decision"],
        account_fingerprint=raw["account_fingerprint"],
        position_baseline_count=raw["position_baseline_count"],
        spy_position_quantity=Decimal(str(raw["spy_position_quantity"])),
        order_baseline_count=raw["order_baseline_count"],
        current_quote=Decimal(str(raw["current_quote"])),
        risk_outcome=raw["risk_outcome"],
        approved_quantity=Decimal(str(raw["approved_risk_quantity"])),
        requested_dollars=Decimal(str(raw["requested_dollar_amount"])),
        trade_approval_enabled=raw["trade_approval_enabled"],
        tradability=TradabilityObservation(
            "SPY",
            tradability["tradable"],
            tradability["supports_fractional"],
            tradability["supports_dollar_market"],
        ),
        review=review,
        provider_warning_summary=tuple(raw.get("provider_warning_summary", ())),
        state=LivePlanState(raw["plan_state"]),
    )
    if raw.get("plan_sha256") != plan.plan_sha256:
        raise LiveExecutionBlocked("PLAN_DIGEST_INVALID")
    return plan


def _transport() -> object:
    from trading_bot.robinhood_mcp.current_live_transport import (
        RobinhoodCurrentLiveTransport,
    )
    from trading_bot.robinhood_mcp.windows_oauth import (
        create_windows_robinhood_oauth_factory,
    )

    return RobinhoodCurrentLiveTransport(
        create_windows_robinhood_oauth_factory(
            redirect_uri="http://127.0.0.1:8765/robinhood/callback"
        )
    )


def _idempotency_key(plan: LiveExecutionPlan, transport: object) -> str | None:
    schemas = getattr(transport, "advertised_schemas", ())
    place = next((item for item in schemas if item.name == "place_equity_order"), None)
    if place is None:
        return None
    for field in ("client_order_id", "idempotency_key", "ref_id"):
        if field in place.properties:
            return _local_order_id(plan)
    return None


def _local_order_id(plan: LiveExecutionPlan) -> str:
    import hashlib

    return hashlib.sha256(
        ("p6-local-order/v1:" + plan.plan_sha256).encode("ascii")
    ).hexdigest()


def _provider_order_id(response: object) -> str | None:
    if not isinstance(response, dict):
        return None
    data = response.get("data")
    if not isinstance(data, dict):
        return None
    value = data.get("id", data.get("order_id"))
    return value if isinstance(value, str) and value else None


def _spy_quantity(snapshot: object) -> Decimal:
    positions = getattr(snapshot, "positions", ())
    return next(
        (position.quantity for position in positions if position.symbol == "SPY"),
        Decimal("0"),
    )


def _working(state: str) -> bool:
    return state.casefold() in {
        "new",
        "queued",
        "confirmed",
        "open",
        "pending",
        "submitted",
        "partially_filled",
    }


def _blocked(
    reason: str, place: int, cancel: int, *, consumed: bool = False
) -> ExecutionResult:
    return ExecutionResult("BLOCKED", None, reason, place, cancel, consumed)
