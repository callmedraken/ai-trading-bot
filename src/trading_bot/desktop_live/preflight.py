"""Effect-bounded P6 plan construction; no placement or cancellation occurs."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from trading_bot.desktop_live.configuration import (
    LIVE_OBSERVATION_BASIS,
    LIVE_SYMBOL,
    TinyLivePolicy,
)
from trading_bot.desktop_live.models import (
    LiveExecutionPlan,
    LivePlanState,
    TradabilityObservation,
    parse_order_review,
    parse_tradability,
    parse_trade_approval,
)
from trading_bot.desktop_live.risk import build_live_risk
from trading_bot.desktop_live.strategy import (
    LiveStrategyDecision,
    decide_live_strategy,
)
from trading_bot.desktop_paper.robinhood_read import resolve_account, utc
from trading_bot.desktop_paper.robinhood_reconciliation import (
    RobinhoodReconciliationSnapshot,
    observe_robinhood_baseline,
)
from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import XNYS_CALENDAR_DESCRIPTOR, BoundMarketCalendar
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.robinhood_mcp.current_live_transport import (
    CurrentLiveTransportError,
    RobinhoodCurrentLiveTransport,
)
from trading_bot.robinhood_mcp.historical import RobinhoodDailyHistoryRequest

P5B_EVIDENCE_ROOT = (
    Path(r"F:\AI\temp\ai-trading-bot-checkpoints")
    / "arch147-p5b-robinhood-read-reconcile"
)
P5B_BASE_HEAD = "7ff86d06a99bcdf349d5e20846d139a554d8be46"
P5B_BASE_TREE = "095c51cedc1c656616123c3acf88148b16b71aa2"
P6_STATE_FILES = (
    Path(r"F:\AI\desktop-bot-state\p6\live.sqlite"),
    Path(r"F:\AI\desktop-bot-state\p6\lifecycle.jsonl"),
)
NEW_YORK = ZoneInfo("America/New_York")


class LivePreflightError(RuntimeError):
    """Sanitized P6 preflight rejection."""


# Only exact reviewed exception types and exact fixed codes may enter evidence.
_FAILURE_CODES = {
    LivePreflightError: frozenset(
        {
            "P5B_EVIDENCE_UNAVAILABLE",
            "P5B_EVIDENCE_MATCH_COUNT",
            "ACCOUNT_FINGERPRINT_DRIFT",
            "P5B_BROKER_BASELINE_DRIFT",
            "FIRST_SPY_POSITION_NOT_ZERO",
            "UNEXPECTED_WORKING_ORDER",
            "PUBLISHED_SESSION_UNAVAILABLE",
        }
    ),
    CurrentLiveTransportError: frozenset(
        {
            "LIVE_METHOD_REJECTED",
            "LIVE_EVENT_LOOP_REJECTED",
            "LIVE_REQUEST_FAILED",
            "LIVE_CAPABILITY_MISSING",
            "LIVE_RESULT_INVALID",
            "LIVE_DISCOVERY_FAILED",
            "LIVE_DISCOVERY_INVALID",
            "LIVE_DISCOVERY_CURSOR_INVALID",
            "LIVE_DISCOVERY_BOUND_EXCEEDED",
            "LIVE_DOLLAR_ORDER_SCHEMA_MISSING",
            "LIVE_SCHEMA_INVALID",
        }
    ),
}


def _failure_code(error: Exception) -> str:
    codes = _FAILURE_CODES.get(type(error), ())
    if len(error.args) == 1 and type(error.args[0]) is str and error.args[0] in codes:
        return error.args[0]
    return "NONE"


@dataclass(frozen=True, slots=True)
class P5BBaselineEvidence:
    source_head: str
    source_tree: str
    account_fingerprint: str
    position_count: int
    order_count: int


def load_p5b_baseline_evidence(
    evidence_root: Path = P5B_EVIDENCE_ROOT,
    *,
    expected_source_head: str,
    expected_source_tree: str,
) -> P5BBaselineEvidence:
    """Load exactly one matching PASS report from the stable P5B root."""
    try:
        reports = sorted(evidence_root.glob("preflight-*/report.json"))
    except (OSError, ValueError):
        raise LivePreflightError("P5B_EVIDENCE_UNAVAILABLE") from None

    matches: list[tuple[dict[str, object], dict[str, object], str]] = []
    for path in reports:
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError, RecursionError):
            continue
        if not isinstance(body, dict) or body.get("status") != "PASS":
            continue
        if (
            body.get("source_head") != expected_source_head
            or body.get("source_tree") != expected_source_tree
        ):
            continue
        result = body.get("result")
        if not isinstance(result, dict):
            result = body
        observation = result.get("observation")
        if not isinstance(observation, dict):
            continue
        if any(
            result.get(field) != 0
            for field in (
                "mutation_call_count",
                "order_review_count",
                "order_preview_count",
                "order_placement_count",
                "order_cancel_count",
                "p5_financial_state_mutation_count",
            )
        ):
            continue
        if result.get("production_state_unchanged") is not True:
            continue
        if any(
            observation.get(field) != 0
            for field in (
                "position_count",
                "order_count",
                "local_expected_broker_effect_count",
            )
        ):
            continue
        fingerprint = observation.get("account_fingerprint")
        if (
            not isinstance(fingerprint, str)
            or len(fingerprint) != 64
            or any(c not in "0123456789abcdef" for c in fingerprint)
        ):
            continue
        matches.append((body, observation, fingerprint))

    if len(matches) != 1:
        raise LivePreflightError("P5B_EVIDENCE_MATCH_COUNT")
    _, observation, fingerprint = matches[0]
    return P5BBaselineEvidence(
        expected_source_head,
        expected_source_tree,
        fingerprint,
        0,
        0,
    )


def build_live_plan(
    *,
    transport: object,
    p5b: P5BBaselineEvidence,
    source_head: str,
    source_tree: str,
    now: datetime,
    policy: TinyLivePolicy | None = None,
) -> LiveExecutionPlan:
    """Construct a plan using synthetic or real typed boundaries."""
    policy = policy or TinyLivePolicy()
    if not isinstance(transport, RobinhoodCurrentLiveTransport) and not all(
        callable(getattr(transport, name, None))
        for name in (
            "discover_required_capabilities",
            "get_accounts",
            "get_portfolio",
            "get_equity_positions",
            "get_equity_quotes",
            "get_equity_orders",
            "get_equity_historicals",
            "get_equity_tradability",
            "get_trade_approval_setting",
            "review_equity_order",
        )
    ):
        raise TypeError("transport does not expose the reviewed P6 surface")
    now = utc(now)
    transport.discover_required_capabilities()
    account_number = resolve_account(transport.get_accounts()).account_number
    observation = observe_robinhood_baseline(transport, observed_at=now)
    _require_clean_first_baseline(observation, p5b)
    calendar = BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())
    history_request = RobinhoodDailyHistoryRequest(LIVE_SYMBOL, now, 60, calendar)
    history_response = transport.get_equity_historicals(history_request.arguments())
    from trading_bot.robinhood_mcp.historical import parse_equity_historicals_response

    history = parse_equity_historicals_response(history_response, history_request)
    strategy = decide_live_strategy(history, None, policy)
    target_session, _ = resolve_target_session(now)
    if strategy.decision is LiveStrategyDecision.NO_ACTION:
        return LiveExecutionPlan.create(
            source_head=source_head,
            source_tree=source_tree,
            policy=policy,
            observation_basis=LIVE_OBSERVATION_BASIS,
            target_session=target_session,
            previous_completed_session=strategy.previous_completed_session,
            signal_values_digest=strategy.values_digest,
            decision="NO_ACTION",
            account_fingerprint=observation.account_fingerprint,
            position_baseline_count=len(observation.positions),
            spy_position_quantity=_spy_quantity(observation),
            order_baseline_count=len(observation.orders),
            current_quote=observation.spy_quote.current_trade_candidate()[0],
            risk_outcome="NOT_EVALUATED",
            approved_quantity=Decimal("0"),
            requested_dollars=Decimal("0"),
            trade_approval_enabled=False,
            tradability=TradabilityObservation("SPY", False, False, False),
            review=None,
            provider_warning_summary=(),
            state=LivePlanState.NO_ACTION,
        )
    tradability = parse_tradability(
        transport.get_equity_tradability({"symbols": ["SPY"]})
    )
    if not tradability.eligible:
        return _blocked_plan(
            source_head,
            source_tree,
            policy,
            target_session,
            strategy,
            observation,
            "SPY_TRADABILITY_OR_DOLLAR_CAPABILITY_MISSING",
            tradability=tradability,
        )
    approval = parse_trade_approval(
        transport.get_trade_approval_setting({"account_number": account_number})
    )
    risk = build_live_risk(
        portfolio=observation.portfolio,
        positions=observation.positions,
        quote=observation.spy_quote,
        as_of=now,
        policy=policy,
        target_session=target_session,
    )
    if risk.decision.outcome.value == "REJECTED":
        return _blocked_plan(
            source_head,
            source_tree,
            policy,
            target_session,
            strategy,
            observation,
            "RISK_REJECTED",
            tradability=tradability,
            trade_approval_enabled=approval.enabled,
            risk_outcome=risk.decision.outcome.value,
            approved_quantity=risk.approved_quantity,
            requested_dollars=risk.requested_dollars,
        )
    review = parse_order_review(
        transport.review_equity_order(
            _order_arguments(
                observation,
                risk.requested_dollars,
                account_number,
                None,
            )
        )
    )
    if approval.enabled:
        state = LivePlanState.OPERATOR_ACTION_REQUIRED
    elif not review.clean:
        state = LivePlanState.BLOCKED
    elif review.dollar_amount != risk.requested_dollars:
        state = LivePlanState.BLOCKED
    else:
        state = LivePlanState.READY
    warnings = tuple(review.warnings)
    return LiveExecutionPlan.create(
        source_head=source_head,
        source_tree=source_tree,
        policy=policy,
        observation_basis=LIVE_OBSERVATION_BASIS,
        target_session=target_session,
        previous_completed_session=strategy.previous_completed_session,
        signal_values_digest=strategy.values_digest,
        decision="BUY",
        account_fingerprint=observation.account_fingerprint,
        position_baseline_count=len(observation.positions),
        spy_position_quantity=_spy_quantity(observation),
        order_baseline_count=len(observation.orders),
        current_quote=observation.spy_quote.current_trade_candidate()[0],
        risk_outcome=risk.decision.outcome.value,
        approved_quantity=risk.approved_quantity,
        requested_dollars=risk.requested_dollars,
        trade_approval_enabled=approval.enabled,
        tradability=tradability,
        review=review,
        provider_warning_summary=warnings,
        state=state,
    )


def preflight() -> dict[str, object]:
    """The later registered P6 preflight; never place or cancel an order."""
    before = _production_identities()
    transport = None
    source_head = source_tree = None
    plan = None
    failure_code = "NONE"
    diagnostic = "P6_SOURCE_IDENTITY_BLOCKED"
    try:
        source_head, source_tree = _source_identity()
        diagnostic = "P5B_EVIDENCE_BLOCKED"
        baseline = load_p5b_baseline_evidence(
            expected_source_head=P5B_BASE_HEAD,
            expected_source_tree=P5B_BASE_TREE,
        )
        diagnostic = "P6_TRANSPORT_CONSTRUCTION_BLOCKED"
        transport = _transport()
        diagnostic = "P6_PLAN_BUILD_BLOCKED"
        plan = build_live_plan(
            transport=transport,
            p5b=baseline,
            source_head=source_head,
            source_tree=source_tree,
            now=datetime.now(UTC),
        )
        status = "PASS"
        diagnostic = "NONE"
    except Exception as error:
        status = "BLOCKED"
        failure_code = _failure_code(error)
    after = _production_identities()
    unchanged = before == after and all(
        identity["exists"] is not None
        for snapshot in (before, after)
        for identity in snapshot.values()
    )
    if not unchanged:
        status = "BLOCKED"
        diagnostic = "P6_STATE_CHANGED_OR_UNAVAILABLE"
    counts = {} if transport is None else dict(transport.call_counts)
    result = {
        "schema": "arch147-p6-tiny-live-preflight/v1",
        "source_head": source_head,
        "source_tree": source_tree,
        "status": status,
        "diagnostic": diagnostic,
        "failure_code": failure_code,
        "plan": None if plan is None else plan.sanitized(),
        "provider_call_counts": counts,
        "order_review_count": counts.get("review_equity_order", 0),
        "order_placement_count": counts.get("place_equity_order", 0),
        "order_cancel_count": counts.get("cancel_equity_order", 0),
        "production_state_before": before,
        "production_state_after": after,
        "production_state_unchanged": unchanged,
        "live_state_mutation_count": 0,
        "final_holdout_access_count": 0,
        "alpaca_call_count": 0,
    }
    return result


def _transport() -> RobinhoodCurrentLiveTransport:
    from trading_bot.robinhood_mcp.windows_oauth import (
        create_windows_robinhood_oauth_factory,
    )

    return RobinhoodCurrentLiveTransport(
        create_windows_robinhood_oauth_factory(
            redirect_uri="http://127.0.0.1:8765/robinhood/callback"
        )
    )


def _source_identity() -> tuple[str, str]:
    root = Path(__file__).resolve().parents[3]

    def run(*args: str) -> str:
        return subprocess.check_output(
            ("git", "-C", str(root), *args), text=True, encoding="utf-8"
        ).strip()

    return run("rev-parse", "HEAD"), run("rev-parse", "HEAD^{tree}")


def _production_identities() -> dict[str, object]:
    result = {}
    for path in P6_STATE_FILES:
        try:
            result[path.name] = {
                "exists": path.exists(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()
                if path.is_file()
                else None,
            }
        except OSError:
            result[path.name] = {"exists": None, "sha256": None}
    return result


def _require_clean_first_baseline(
    observation: RobinhoodReconciliationSnapshot, baseline: P5BBaselineEvidence
) -> None:
    if observation.account_fingerprint != baseline.account_fingerprint:
        raise LivePreflightError("ACCOUNT_FINGERPRINT_DRIFT")
    if (
        len(observation.positions) != baseline.position_count
        or len(observation.orders) != baseline.order_count
    ):
        raise LivePreflightError("P5B_BROKER_BASELINE_DRIFT")
    if _spy_quantity(observation) != 0:
        raise LivePreflightError("FIRST_SPY_POSITION_NOT_ZERO")
    if any(_working(order.state) for order in observation.orders):
        raise LivePreflightError("UNEXPECTED_WORKING_ORDER")


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


def _spy_quantity(observation: RobinhoodReconciliationSnapshot) -> Decimal:
    return next(
        (
            position.quantity
            for position in observation.positions
            if position.symbol == "SPY"
        ),
        Decimal("0"),
    )


def resolve_target_session(now: datetime) -> tuple[str, bool]:
    """Return the next executable published session and whether it is open."""
    local = utc(now).astimezone(NEW_YORK)
    authority = NYSEPublishedRegularSessionAuthority()
    schedule = authority.schedule_for(local.date())
    if schedule is None or local >= schedule.closes_at:
        session = NYSEMarketCalendar().next_session(now).session_date
        schedule = authority.schedule_for(session)
    if schedule is None:
        raise LivePreflightError("PUBLISHED_SESSION_UNAVAILABLE")
    regular_open = schedule.opens_at <= local < schedule.closes_at
    return schedule.session_date.isoformat(), regular_open


def _order_arguments(
    observation: RobinhoodReconciliationSnapshot,
    amount: object,
    account_number: str,
    idempotency_key: str | None,
) -> dict[str, object]:
    args: dict[str, object] = {
        "account_number": account_number,
        "symbol": "SPY",
        "side": "buy",
        "type": "market",
        "market_hours": "regular_hours",
        "time_in_force": "gfd",
        "dollar_amount": format(amount, "f"),
    }
    if idempotency_key is not None:
        args["client_order_id"] = idempotency_key
    del observation
    return args


def _blocked_plan(
    source_head: str,
    source_tree: str,
    policy: TinyLivePolicy,
    target_session: str,
    strategy: object,
    observation: RobinhoodReconciliationSnapshot,
    warning: str,
    *,
    tradability: TradabilityObservation | None = None,
    trade_approval_enabled: bool = False,
    risk_outcome: str = "NOT_EVALUATED",
    approved_quantity: object = 0,
    requested_dollars: object = 0,
) -> LiveExecutionPlan:
    from decimal import Decimal

    return LiveExecutionPlan.create(
        source_head=source_head,
        source_tree=source_tree,
        policy=policy,
        observation_basis=LIVE_OBSERVATION_BASIS,
        target_session=target_session,
        previous_completed_session=str(strategy.previous_completed_session),
        signal_values_digest=str(strategy.values_digest),
        decision="BUY",
        account_fingerprint=observation.account_fingerprint,
        position_baseline_count=len(observation.positions),
        spy_position_quantity=_spy_quantity(observation),
        order_baseline_count=len(observation.orders),
        current_quote=observation.spy_quote.current_trade_candidate()[0],
        risk_outcome=risk_outcome,
        approved_quantity=Decimal(str(approved_quantity)),
        requested_dollars=Decimal(str(requested_dollars)),
        trade_approval_enabled=trade_approval_enabled,
        tradability=tradability or TradabilityObservation("SPY", False, False, False),
        review=None,
        provider_warning_summary=(warning,),
        state=LivePlanState.BLOCKED,
    )
