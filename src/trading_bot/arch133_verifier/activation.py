"""Frozen read-only projection of Architecture-133 activation/wake models.

No model grants provider or paper-write authority. Durable single-use admission
belongs to 133-B. Store paths are retained exactly in serialized material but,
under the repository identity contract, are excluded from domain identities;
store_identity binds the store independently of its filesystem location.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, fields
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.domain import OrderSide, Symbol, TradeProposal
from trading_bot.domain._validation import require_decimal, require_positive_decimal


@dataclass(frozen=True, slots=True)
class RiskLimits:
    """Deterministic limits expressed as Decimal fractions and amounts."""

    max_position_percent: Decimal = Decimal("0.20")
    max_total_exposure_percent: Decimal = Decimal("0.80")
    max_order_notional: Decimal | None = None
    max_new_position_percent: Decimal | None = None
    minimum_cash_reserve_percent: Decimal = Decimal("0.10")
    allow_fractional_shares: bool = True
    fractional_increment: Decimal = Decimal("0.001")
    allow_buying: bool = True
    allow_selling: bool = True
    estimated_commission: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        for field_name in (
            "max_position_percent",
            "max_total_exposure_percent",
        ):
            value = require_positive_decimal(getattr(self, field_name), field_name)
            if value > Decimal("1"):
                raise ValueError(f"{field_name} must be no greater than 1")
        require_decimal(
            self.minimum_cash_reserve_percent, "minimum_cash_reserve_percent"
        )
        if not Decimal("0") <= self.minimum_cash_reserve_percent <= Decimal("1"):
            raise ValueError("minimum_cash_reserve_percent must be between 0 and 1")
        for field_name in ("max_order_notional", "max_new_position_percent"):
            value = getattr(self, field_name)
            if value is not None:
                require_positive_decimal(value, field_name)
        if (
            self.max_new_position_percent is not None
            and self.max_new_position_percent > Decimal("1")
        ):
            raise ValueError("max_new_position_percent must be no greater than 1")
        require_positive_decimal(self.fractional_increment, "fractional_increment")
        require_decimal(self.estimated_commission, "estimated_commission")
        if self.estimated_commission < Decimal("0"):
            raise ValueError("estimated_commission must be zero or greater")
        for field_name in (
            "allow_fractional_shares",
            "allow_buying",
            "allow_selling",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be a bool")


ACTIVATION_SCHEMA = "arch133-review-paper-activation/v1"
WAKE_SCHEMA = "arch133-review-paper-wake/v1"
WAKE_CONTRACT_ID = "arch133-review-paper-zero-argument-wake/v1"
EXPIRY_RULE = "TARGET_SESSION_ADMISSION_CLOSE"
_ACTIVATION_NAMESPACE = UUID("b69739f6-111a-51bd-964b-95119b9df3e8")
_WAKE_NAMESPACE = UUID("bde0c953-f3e8-5191-8823-8d989875e8a5")
_RISK_BOOLEANS = ("allow_fractional_shares", "allow_buying", "allow_selling")


def _exact(value: object, expected: type, name: str) -> None:
    if type(value) is not expected:
        raise TypeError(f"{name} must be exactly {expected.__name__}")


def _utc(value: datetime, name: str) -> datetime:
    _exact(value, datetime, name)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _timestamp(value: datetime) -> str:
    return _utc(value, "timestamp").isoformat(timespec="microseconds")


def _finite(value: Decimal, name: str) -> None:
    _exact(value, Decimal, name)
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")


def _canonical_decimal(value: Decimal) -> str:
    # Keep the accepted finite fixed-point convention without importing the
    # market_data package's provider exports or the execution fingerprint layer.
    _finite(value, "Decimal")
    if value == Decimal("0"):
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _digest(value: str, length: int, name: str) -> None:
    _exact(value, str, name)
    if re.fullmatch(f"[0-9a-f]{{{length}}}", value) is None:
        raise ValueError(f"{name} must be a lowercase {length}-character digest")


def _store_path(value: str) -> None:
    # Lexical identity validation only: never resolve or inspect a filesystem.
    _exact(value, str, "store_path")
    if re.fullmatch(r"[A-Z]:\\[^/\x00-\x1f<>:\"|?*]+", value) is None:
        raise ValueError("store_path must be an exact absolute Windows file path")
    for part in value[3:].split("\\"):
        if not part or part in (".", "..") or part != part.strip().rstrip("."):
            raise ValueError("store_path must have canonical nonempty components")
        if re.fullmatch(r"(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part):
            raise ValueError("store_path must not contain device names")


def _duration_us(value: timedelta) -> int:
    return (value.days * 86400 + value.seconds) * 1000000 + value.microseconds


def _proposal_payload(proposal: TradeProposal) -> dict[str, object]:
    return {
        "proposal_id": str(proposal.proposal_id),
        "symbol": str(proposal.symbol),
        "side": proposal.side.value,
        "desired_quantity": _canonical_decimal(proposal.desired_quantity),
        "created_at": _timestamp(proposal.created_at),
        "reason": proposal.reason,
        "confidence": (
            None
            if proposal.confidence is None
            else _canonical_decimal(proposal.confidence)
        ),
    }


def _risk_payload(limits: RiskLimits) -> dict[str, object]:
    return {
        item.name: (
            getattr(limits, item.name)
            if item.name in _RISK_BOOLEANS or getattr(limits, item.name) is None
            else _canonical_decimal(getattr(limits, item.name))
        )
        for item in fields(RiskLimits)
    }


def _scalar(value: object) -> str:
    if value is None:
        return "none"
    if type(value) is bool:
        return "true" if value else "false"
    return str(value)


def _material(version: str, facts: tuple[tuple[str, object], ...]) -> str:
    # Length-framed facts, never JSON/artifact bytes, paths, clocks or hashes.
    scalars = (
        version,
        *(text for name, value in facts for text in (name, _scalar(value))),
    )
    return "".join(f"{len(text.encode('utf-8'))}:{text}" for text in scalars)


def _json(payload: dict[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _object(value: object, expected_keys: set[str]) -> dict[str, object]:
    _exact(value, dict, "payload")
    if set(value) != expected_keys:
        raise ValueError("payload must contain exactly the closed schema fields")
    return value


def _load(value: str) -> dict[str, object]:
    _exact(value, str, "serialized material")
    payload = json.loads(value)
    _exact(payload, dict, "payload")
    return payload


def _decimal_text(value: object) -> Decimal:
    _exact(value, str, "Decimal text")
    if re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?", value) is None:
        raise ValueError("Decimal text must be canonical")
    result = Decimal(value)
    _finite(result, "Decimal text")
    if _canonical_decimal(result) != value:
        raise ValueError("Decimal text must be canonical")
    return result


def _uuid_text(value: object) -> UUID:
    _exact(value, str, "UUID text")
    return UUID(value)


def _datetime_text(value: object) -> datetime:
    _exact(value, str, "timestamp text")
    return _utc(datetime.fromisoformat(value), "timestamp")


def _date_text(value: object) -> date:
    _exact(value, str, "session date text")
    return date.fromisoformat(value)


def _duration_value(value: object) -> timedelta:
    _exact(value, int, "duration microseconds")
    return timedelta(microseconds=value)


@dataclass(frozen=True, slots=True, kw_only=True)
class ReviewPaperActivation:
    """One complete frozen activation; its derived ID conveys no effect authority."""

    source_head: str
    source_tree: str
    deployment_identity: str
    target_session_date: date
    proposal: TradeProposal
    risk_limits: RiskLimits
    new_trading_enabled: bool
    store_identity: UUID
    store_path: str
    starting_cash: Decimal
    opening_buffer: timedelta
    closing_buffer: timedelta
    max_quote_age: timedelta
    slippage_basis_points: Decimal
    commission: Decimal
    local_order_id: UUID
    created_at: datetime
    schema: str = ACTIVATION_SCHEMA
    wake_contract_id: str = WAKE_CONTRACT_ID
    expiry_rule: str = EXPIRY_RULE
    activation_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        for name, expected in (
            ("schema", ACTIVATION_SCHEMA),
            ("wake_contract_id", WAKE_CONTRACT_ID),
            ("expiry_rule", EXPIRY_RULE),
        ):
            _exact(getattr(self, name), str, name)
            if getattr(self, name) != expected:
                raise ValueError(f"{name} is not the frozen v1 contract")
        _digest(self.source_head, 40, "source_head")
        _digest(self.source_tree, 40, "source_tree")
        _digest(self.deployment_identity, 64, "deployment_identity")
        for name, expected in (
            ("target_session_date", date),
            ("proposal", TradeProposal),
            ("risk_limits", RiskLimits),
            ("new_trading_enabled", bool),
            ("store_identity", UUID),
            ("local_order_id", UUID),
        ):
            _exact(getattr(self, name), expected, name)
        _store_path(self.store_path)
        _exact(self.proposal.symbol, Symbol, "proposal.symbol")
        _exact(self.proposal.side, OrderSide, "proposal.side")
        _exact(self.proposal.proposal_id, UUID, "proposal.proposal_id")
        _utc(self.proposal.created_at, "proposal.created_at")
        _finite(self.proposal.desired_quantity, "proposal.desired_quantity")
        if self.proposal.confidence is not None:
            _finite(self.proposal.confidence, "proposal.confidence")
        # Reuse canonical domain validation without a UUID-generating factory.
        TradeProposal(
            **{
                item.name: getattr(self.proposal, item.name)
                for item in fields(TradeProposal)
            }
        )
        for item in fields(RiskLimits):
            value = getattr(self.risk_limits, item.name)
            if item.name in _RISK_BOOLEANS:
                _exact(value, bool, item.name)
            elif value is not None:
                _finite(value, item.name)
        RiskLimits(
            **{
                item.name: getattr(self.risk_limits, item.name)
                for item in fields(RiskLimits)
            }
        )
        for name in ("starting_cash", "slippage_basis_points", "commission"):
            value = getattr(self, name)
            _finite(value, name)
            if value < Decimal("0"):
                raise ValueError(f"{name} must be nonnegative")
        if self.starting_cash == Decimal("0"):
            raise ValueError("starting_cash must be strictly positive")
        if self.slippage_basis_points > Decimal("9999"):
            raise ValueError("slippage_basis_points must be between 0 and 9999")
        for name in ("opening_buffer", "closing_buffer", "max_quote_age"):
            value = getattr(self, name)
            _exact(value, timedelta, name)
            if value < timedelta(0) or (
                name == "max_quote_age" and value == timedelta(0)
            ):
                raise ValueError(f"{name} must satisfy the frozen duration bounds")
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))
        if self.proposal.created_at > self.created_at:
            raise ValueError("activation must not precede proposal creation")
        payload = self._payload()
        facts = (
            tuple(
                (name, value)
                for name, value in payload.items()
                if name not in ("store_path", "proposal", "risk_limits")
            )
            + tuple(
                (f"proposal.{name}", value)
                for name, value in _proposal_payload(self.proposal).items()
            )
            + tuple(
                (f"risk_limits.{name}", value)
                for name, value in _risk_payload(self.risk_limits).items()
            )
        )
        object.__setattr__(
            self,
            "activation_id",
            uuid5(_ACTIVATION_NAMESPACE, _material(ACTIVATION_SCHEMA, facts)),
        )

    def _payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "source_head": self.source_head,
            "source_tree": self.source_tree,
            "deployment_identity": self.deployment_identity,
            "target_session_date": self.target_session_date.isoformat(),
            "proposal": _proposal_payload(self.proposal),
            "risk_limits": _risk_payload(self.risk_limits),
            "new_trading_enabled": self.new_trading_enabled,
            "store_identity": str(self.store_identity),
            "store_path": self.store_path,
            "starting_cash": _canonical_decimal(self.starting_cash),
            "opening_buffer_us": _duration_us(self.opening_buffer),
            "closing_buffer_us": _duration_us(self.closing_buffer),
            "max_quote_age_us": _duration_us(self.max_quote_age),
            "slippage_basis_points": _canonical_decimal(self.slippage_basis_points),
            "commission": _canonical_decimal(self.commission),
            "local_order_id": str(self.local_order_id),
            "wake_contract_id": self.wake_contract_id,
            "created_at": _timestamp(self.created_at),
            "expiry_rule": self.expiry_rule,
        }

    def to_json(self) -> str:
        """Return closed canonical storage material, including the exact store path."""
        return _json({**self._payload(), "activation_id": str(self.activation_id)})

    @classmethod
    def from_json(cls, value: str) -> ReviewPaperActivation:
        """Reject unknown/missing fields, noncanonical text, and identity tampering."""
        keys = {item.name for item in fields(cls)} - {
            "opening_buffer",
            "closing_buffer",
            "max_quote_age",
        } | {"opening_buffer_us", "closing_buffer_us", "max_quote_age_us"}
        payload = _object(_load(value), keys)
        proposal = _object(
            payload["proposal"], {item.name for item in fields(TradeProposal)}
        )
        limits = _object(
            payload["risk_limits"], {item.name for item in fields(RiskLimits)}
        )
        result = cls(
            **{
                name: payload[name]
                for name in (
                    "schema",
                    "source_head",
                    "source_tree",
                    "deployment_identity",
                    "new_trading_enabled",
                    "store_path",
                    "wake_contract_id",
                    "expiry_rule",
                )
            },
            target_session_date=_date_text(payload["target_session_date"]),
            proposal=TradeProposal(
                proposal_id=_uuid_text(proposal["proposal_id"]),
                symbol=Symbol(proposal["symbol"]),
                side=OrderSide(proposal["side"]),
                desired_quantity=_decimal_text(proposal["desired_quantity"]),
                created_at=_datetime_text(proposal["created_at"]),
                reason=proposal["reason"],
                confidence=None
                if proposal["confidence"] is None
                else _decimal_text(proposal["confidence"]),
            ),
            risk_limits=RiskLimits(
                **{
                    name: raw
                    if name in _RISK_BOOLEANS or raw is None
                    else _decimal_text(raw)
                    for name, raw in limits.items()
                }
            ),
            store_identity=_uuid_text(payload["store_identity"]),
            starting_cash=_decimal_text(payload["starting_cash"]),
            opening_buffer=_duration_value(payload["opening_buffer_us"]),
            closing_buffer=_duration_value(payload["closing_buffer_us"]),
            max_quote_age=_duration_value(payload["max_quote_age_us"]),
            slippage_basis_points=_decimal_text(payload["slippage_basis_points"]),
            commission=_decimal_text(payload["commission"]),
            local_order_id=_uuid_text(payload["local_order_id"]),
            created_at=_datetime_text(payload["created_at"]),
        )
        if result.to_json() != value:
            raise ValueError("activation material or identity is not canonical")
        return result


class ReviewPaperWakeState(StrEnum):
    READY = "READY"
    PREPARE_STARTED = "PREPARE_STARTED"
    PREPARED = "PREPARED"
    REVIEW_STARTED = "REVIEW_STARTED"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"
    INDETERMINATE = "INDETERMINATE"


def review_paper_wake_id(
    activation_id: UUID,
    target_session_date: date,
    proposal_id: UUID,
    local_order_id: UUID,
) -> UUID:
    """Bind one wake to exactly these four canonical facts, independent of state."""
    for name, value, expected in (
        ("activation_id", activation_id, UUID),
        ("target_session_date", target_session_date, date),
        ("proposal_id", proposal_id, UUID),
        ("local_order_id", local_order_id, UUID),
    ):
        _exact(value, expected, name)
    return uuid5(
        _WAKE_NAMESPACE,
        _material(
            WAKE_SCHEMA,
            (
                ("activation_id", activation_id),
                ("target_session_date", target_session_date.isoformat()),
                ("proposal_id", proposal_id),
                ("local_order_id", local_order_id),
            ),
        ),
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class ReviewPaperWake:
    """Immutable state snapshot; persisted admission/replay fencing is a later layer."""

    activation: ReviewPaperActivation
    updated_at: datetime
    state: ReviewPaperWakeState = ReviewPaperWakeState.READY
    schema: str = WAKE_SCHEMA
    wake_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        _exact(self.activation, ReviewPaperActivation, "activation")
        _exact(self.state, ReviewPaperWakeState, "state")
        _exact(self.schema, str, "schema")
        if self.schema != WAKE_SCHEMA:
            raise ValueError("wake schema is not the frozen v1 contract")
        object.__setattr__(self, "updated_at", _utc(self.updated_at, "updated_at"))
        if self.updated_at < self.activation.created_at:
            raise ValueError("wake must not precede activation creation")
        object.__setattr__(
            self,
            "wake_id",
            review_paper_wake_id(
                self.activation.activation_id,
                self.activation.target_session_date,
                self.activation.proposal.proposal_id,
                self.activation.local_order_id,
            ),
        )

    def to_json(self) -> str:
        return _json(
            {
                "schema": self.schema,
                "wake_id": str(self.wake_id),
                "activation_id": str(self.activation.activation_id),
                "target_session_date": self.activation.target_session_date.isoformat(),
                "proposal_id": str(self.activation.proposal.proposal_id),
                "local_order_id": str(self.activation.local_order_id),
                "state": self.state.value,
                "updated_at": _timestamp(self.updated_at),
            }
        )

    @classmethod
    def from_json(
        cls, value: str, *, activation: ReviewPaperActivation
    ) -> ReviewPaperWake:
        payload = _object(
            _load(value),
            {
                "schema",
                "wake_id",
                "activation_id",
                "target_session_date",
                "proposal_id",
                "local_order_id",
                "state",
                "updated_at",
            },
        )
        _exact(payload["state"], str, "state text")
        result = cls(
            activation=activation,
            schema=payload["schema"],
            state=ReviewPaperWakeState(payload["state"]),
            updated_at=_datetime_text(payload["updated_at"]),
        )
        if result.to_json() != value:
            raise ValueError("wake material must be canonical and match its activation")
        return result
