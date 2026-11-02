"""Sanitized immutable P6 observations, plan states, and execution records."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import StrEnum
from typing import Final

from trading_bot.desktop_live.configuration import (
    LIVE_OBSERVATION_BASIS,
    MAX_BOT_GROSS_EXPOSURE_DOLLARS,
    MAX_ORDER_DOLLARS,
    TinyLivePolicy,
)
from trading_bot.desktop_paper.robinhood_read import decimal_value, text

PLAN_SCHEMA: Final = "arch147-p6-tiny-live-plan/v1"


class LivePlanState(StrEnum):
    READY = "READY"
    NO_ACTION = "NO_ACTION"
    OPERATOR_ACTION_REQUIRED = "OPERATOR_ACTION_REQUIRED"
    BLOCKED = "BLOCKED"


class LiveMutationDisposition(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    LIVE_MUTATION_ATTEMPT_STARTED = "LIVE_MUTATION_ATTEMPT_STARTED"
    MAY_HAVE_OCCURRED = "MAY_HAVE_OCCURRED"
    RECONCILED = "RECONCILED"


@dataclass(frozen=True, slots=True)
class TradabilityObservation:
    symbol: str
    tradable: bool
    supports_fractional: bool
    supports_dollar_market: bool
    warning: str | None = None

    def __post_init__(self) -> None:
        if self.symbol != "SPY" or not all(
            isinstance(value, bool)
            for value in (
                self.tradable,
                self.supports_fractional,
                self.supports_dollar_market,
            )
        ):
            raise ValueError("invalid SPY tradability observation")
        if self.warning is not None:
            text(self.warning)

    @property
    def eligible(self) -> bool:
        return (
            self.tradable and self.supports_fractional and self.supports_dollar_market
        )


@dataclass(frozen=True, slots=True)
class TradeApprovalObservation:
    enabled: bool
    status: str

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool) or not self.status:
            raise ValueError("invalid trade-approval observation")
        text(self.status)


@dataclass(frozen=True, slots=True)
class OrderReviewObservation:
    symbol: str
    side: str
    order_type: str
    dollar_amount: Decimal
    market_hours: str
    time_in_force: str
    warnings: tuple[str, ...]
    digest: str

    def __post_init__(self) -> None:
        if (
            self.symbol != "SPY"
            or self.side != "buy"
            or self.order_type != "market"
            or self.market_hours != "regular_hours"
            or self.time_in_force != "gfd"
            or type(self.dollar_amount) is not Decimal
            or self.dollar_amount <= 0
        ):
            raise ValueError("review does not match the P6 order contract")
        if not isinstance(self.warnings, tuple) or any(
            not isinstance(warning, str) or not warning for warning in self.warnings
        ):
            raise ValueError("review warnings must be bounded text")
        if len(self.digest) != 64 or any(
            c not in "0123456789abcdef" for c in self.digest
        ):
            raise ValueError("review digest must be lowercase SHA256")

    @property
    def clean(self) -> bool:
        return not self.warnings


@dataclass(frozen=True, slots=True)
class LiveExecutionPlan:
    """One immutable, sanitized plan bound to a source and target session."""

    source_head: str
    source_tree: str
    policy: TinyLivePolicy
    observation_basis: str
    target_session: str
    previous_completed_session: str
    signal_values_digest: str
    decision: str
    account_fingerprint: str
    position_baseline_count: int
    spy_position_quantity: Decimal
    order_baseline_count: int
    current_quote: Decimal
    risk_outcome: str
    approved_quantity: Decimal
    requested_dollars: Decimal
    trade_approval_enabled: bool
    tradability: TradabilityObservation
    review: OrderReviewObservation | None
    provider_warning_summary: tuple[str, ...]
    state: LivePlanState
    plan_sha256: str

    def __post_init__(self) -> None:
        _sha(self.source_head, 40)
        _sha(self.source_tree, 40)
        if not isinstance(self.policy, TinyLivePolicy):
            raise TypeError("policy must be TinyLivePolicy")
        if self.observation_basis != LIVE_OBSERVATION_BASIS:
            raise ValueError("P6 observation basis mismatch")
        for value in (
            self.target_session,
            self.previous_completed_session,
            self.decision,
            self.risk_outcome,
        ):
            text(value)
        _sha(self.signal_values_digest, 64)
        _sha(self.account_fingerprint, 64)
        if (
            type(self.position_baseline_count) is not int
            or self.position_baseline_count < 0
        ):
            raise ValueError("invalid position baseline count")
        if type(self.order_baseline_count) is not int or self.order_baseline_count < 0:
            raise ValueError("invalid order baseline count")
        for value in (
            self.spy_position_quantity,
            self.current_quote,
            self.approved_quantity,
            self.requested_dollars,
        ):
            if type(value) is not Decimal or not value.is_finite() or value < 0:
                raise ValueError("invalid plan Decimal")
        if type(self.trade_approval_enabled) is not bool:
            raise TypeError("trade approval must be bool")
        if not isinstance(self.tradability, TradabilityObservation):
            raise TypeError("tradability must be typed")
        if self.review is not None and not isinstance(
            self.review, OrderReviewObservation
        ):
            raise TypeError("review must be typed")
        if type(self.provider_warning_summary) is not tuple:
            raise TypeError("provider warnings must be a tuple")
        if not isinstance(self.state, LivePlanState):
            raise TypeError("state must be LivePlanState")
        _sha(self.plan_sha256, 64)
        if self.plan_sha256 != "0" * 64 and self.plan_sha256 != _plan_digest(self):
            raise ValueError("plan digest does not match immutable plan material")
        if self.requested_dollars > MAX_ORDER_DOLLARS:
            raise ValueError("plan exceeds the source-owned P6 order ceiling")
        if self.state is LivePlanState.READY:
            if self.decision != "BUY" or self.review is None or not self.review.clean:
                raise ValueError("READY requires a clean reviewed BUY plan")
            if not self.tradability.eligible or self.trade_approval_enabled:
                raise ValueError("READY requires compatible live capabilities")
            if self.requested_dollars <= 0 or self.approved_quantity <= 0:
                raise ValueError("READY requires a positive bounded order")
        elif self.state is LivePlanState.NO_ACTION:
            if self.decision != "NO_ACTION" or self.requested_dollars != 0:
                raise ValueError("NO_ACTION cannot carry a live order")

    @classmethod
    def create(cls, **kwargs: object) -> LiveExecutionPlan:
        provisional = cls(plan_sha256="0" * 64, **kwargs)
        return replace(provisional, plan_sha256=_plan_digest(provisional))

    def sanitized(self) -> dict[str, object]:
        return {
            "schema": PLAN_SCHEMA,
            "source_head": self.source_head,
            "source_tree": self.source_tree,
            "strategy_family": self.policy.strategy_family,
            "strategy_version": self.policy.strategy_version,
            "campaign_id": str(self.policy.campaign_id),
            "bundle_id": str(self.policy.bundle_id),
            "candidate_id": str(self.policy.candidate_id),
            "observation_basis": self.observation_basis,
            "symbol": "SPY",
            "target_session": self.target_session,
            "previous_completed_session": self.previous_completed_session,
            "signal_values_digest": self.signal_values_digest,
            "decision": self.decision,
            "account_fingerprint": self.account_fingerprint,
            "position_baseline_count": self.position_baseline_count,
            "spy_position_quantity": str(self.spy_position_quantity),
            "order_baseline_count": self.order_baseline_count,
            "current_quote": str(self.current_quote),
            "risk_outcome": self.risk_outcome,
            "approved_risk_quantity": str(self.approved_quantity),
            "requested_dollar_amount": str(self.requested_dollars),
            "max_order_dollars": str(MAX_ORDER_DOLLARS),
            "max_gross_exposure_dollars": str(MAX_BOT_GROSS_EXPOSURE_DOLLARS),
            "trade_approval_enabled": self.trade_approval_enabled,
            "tradability": {
                "tradable": self.tradability.tradable,
                "supports_fractional": self.tradability.supports_fractional,
                "supports_dollar_market": self.tradability.supports_dollar_market,
            },
            "review_digest": None if self.review is None else self.review.digest,
            "provider_warning_summary": list(self.provider_warning_summary),
            "plan_state": self.state.value,
            "plan_sha256": self.plan_sha256,
        }


@dataclass(frozen=True, slots=True)
class LiveExecutionReceipt:
    """Sanitized post-mutation result; provider history is authoritative."""

    local_order_id: str
    provider_order_id: str | None
    state: str
    requested_dollars: Decimal
    filled_quantity: Decimal
    average_fill_price: Decimal | None
    post_trade_position_quantity: Decimal
    reconciliation_status: str
    disposition: LiveMutationDisposition

    def __post_init__(self) -> None:
        text(self.local_order_id)
        if self.provider_order_id is not None:
            text(self.provider_order_id)
        text(self.state)
        for value in (
            self.requested_dollars,
            self.filled_quantity,
            self.post_trade_position_quantity,
        ):
            decimal_value(value)
        if self.average_fill_price is not None:
            decimal_value(self.average_fill_price)
        text(self.reconciliation_status)
        if not isinstance(self.disposition, LiveMutationDisposition):
            raise TypeError("disposition must be LiveMutationDisposition")


def parse_tradability(payload: Mapping[str, object]) -> TradabilityObservation:
    row = _one_row(payload, "tradability")
    return TradabilityObservation(
        _required_text(row.get("symbol")),
        _required_bool(row.get("tradable")),
        _first_bool(row, "fractional_trading", "supports_fractional", "fractional"),
        _first_bool(row, "dollar_orders", "supports_dollar_market", "dollar_order"),
        _optional_text(row.get("warning")),
    )


def parse_trade_approval(payload: Mapping[str, object]) -> TradeApprovalObservation:
    row = _one_row(payload, "trade approval")
    enabled = _first_bool(row, "enabled", "trade_approval_enabled", "approval_required")
    return TradeApprovalObservation(
        enabled, "ENABLED" if enabled else "AUTONOMOUS_ALLOWED"
    )


def parse_order_review(payload: Mapping[str, object]) -> OrderReviewObservation:
    row = _one_row(payload, "order review")
    warnings = row.get("warnings", row.get("warning", []))
    if isinstance(warnings, str):
        warnings = [warnings]
    if not isinstance(warnings, list) or any(
        not isinstance(item, str) for item in warnings
    ):
        raise ValueError("review warnings are invalid")
    amount = decimal_value(row.get("dollar_amount"))
    material = {
        "symbol": _required_text(row.get("symbol")),
        "side": _required_text(row.get("side")),
        "type": _required_text(row.get("type", row.get("order_type"))),
        "dollar_amount": format(amount, "f"),
        "market_hours": _required_text(row.get("market_hours")),
        "time_in_force": _required_text(row.get("time_in_force")),
        "warnings": warnings,
    }
    digest = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()
    return OrderReviewObservation(
        material["symbol"],
        material["side"],
        material["type"],
        amount,
        material["market_hours"],
        material["time_in_force"],
        tuple(warnings),
        digest,
    )


def _one_row(payload: Mapping[str, object], label: str) -> Mapping[str, object]:
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise ValueError(f"{label} data is invalid")
    rows = data.get("results", data.get("result"))
    if isinstance(rows, list):
        if len(rows) != 1 or not isinstance(rows[0], Mapping):
            raise ValueError(f"{label} result is invalid")
        return rows[0]
    if isinstance(rows, Mapping):
        return rows
    return data


def _required_text(value: object) -> str:
    text(value)
    return value


def _optional_text(value: object) -> str | None:
    return None if value is None else _required_text(value)


def _required_bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError("boolean capability is required")
    return value


def _first_bool(row: Mapping[str, object], *names: str) -> bool:
    for name in names:
        if name in row:
            return _required_bool(row[name])
    raise ValueError("required capability field is unavailable")


def _sha(value: str, length: int) -> None:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError("invalid lowercase SHA256/SHA1 identity")


def _plan_digest(plan: LiveExecutionPlan) -> str:
    material = plan.sanitized()
    material.pop("plan_sha256", None)
    return hashlib.sha256(
        json.dumps(
            material, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
    ).hexdigest()
