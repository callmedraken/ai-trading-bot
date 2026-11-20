"""Fakeable, source-owned Robinhood MCP facts and effect boundary for Arch 148.

The adapter accepts an explicit transport factory. It does not create OAuth,
discover tools, open a session, or make a provider call during import or
construction. The production transport remains the owner of its OAuth/session
lifecycle; this module owns only the Architecture-148 argument and fact
bindings around that transport.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Protocol, cast
from uuid import UUID

from trading_bot.desktop_paper.robinhood_read import parse_portfolio
from trading_bot.domain import OrderSide, Position, Symbol
from trading_bot.domain._validation import normalize_utc
from trading_bot.robinhood_mcp.account_resolution import (
    RobinhoodAgenticAccountResolver,
)
from trading_bot.robinhood_mcp.models import (
    RobinhoodEquityOrder,
    RobinhoodEquityQuotesResponse,
)
from trading_bot.robinhood_mcp.parsing import (
    parse_equity_orders_response,
    parse_equity_quotes_response,
    parse_quote_data,
    parse_review_equity_order_response,
)

from .identity import create_order_intent
from .models import (
    TRADED_SYMBOLS,
    UNIVERSE_SYMBOLS,
    AccountFacts,
    ApprovalFacts,
    ApprovalRequestStatus,
    BrokerOrderFact,
    BrokerReviewFacts,
    BrokerSnapshot,
    IntentKind,
    IntentLifecycle,
    LogicalOrderIntent,
    OrderState,
    PriceObservation,
    ProviderApprovalFact,
    ReviewStatus,
    RuntimeState,
    ScopeFacts,
    TradabilityFacts,
)
from .order_tracker import InProcessWritePermit, OrderWriteAction, OrderWriteReservation

MAX_READ_PAGES = 20
MAX_CURSOR_LENGTH = 4096
MAX_ROWS_PER_PAGE = 1000
REGULAR_MARKET_TIF = "gfd"
PROTECTIVE_STOP_TIF = "gtc"
REGULAR_MARKET_HOURS = "regular_hours"
_ACCOUNT_NUMBER = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
_REF_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")


class RobinhoodAdapterError(RuntimeError):
    """Sanitized adapter failure; provider messages and credentials stay private."""


class RobinhoodAdapterUnavailableError(RobinhoodAdapterError):
    """Required broker facts or an exact supported argument shape are unavailable."""


class RobinhoodAdapterIdentityError(RobinhoodAdapterError):
    """The fresh provider account does not match durable runtime identity."""


class RobinhoodEffectStatus(StrEnum):
    PLACED = "PLACED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class RobinhoodAdapterCapabilities:
    """Fake-test-only facts that are not established by current transport.

    Each field is deliberately prefixed ``test_only``. The current production
    path must leave them false until current-symbol provider scope, approval
    enumeration, or stop terms are independently accepted. They never create
    write authority.
    """

    test_only_positions_account_wide: bool = False
    test_only_orders_account_wide_all_agents: bool = False
    test_only_approval_requests_exhaustive: bool = False
    test_only_stop_market_gtc_supported: bool = False


@dataclass(frozen=True, slots=True)
class RobinhoodEffectOutcome:
    """Sanitized result of one attempted effect, including ambiguous outcomes."""

    status: RobinhoodEffectStatus
    operation_id: UUID
    intent_id: UUID
    ref_id: str
    provider_order_id: str | None
    approval_id: str | None
    observed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.status, RobinhoodEffectStatus):
            raise TypeError("status must be RobinhoodEffectStatus")
        if not isinstance(self.operation_id, UUID) or not isinstance(
            self.intent_id, UUID
        ):
            raise TypeError("operation and intent IDs must be UUID values")
        for name in ("ref_id",):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} must be nonblank")
        for name in ("provider_order_id", "approval_id"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value):
                raise ValueError(f"{name} must be nonblank or None")
        object.__setattr__(
            self, "observed_at", normalize_utc(self.observed_at, "observed_at")
        )


class RobinhoodMcpOperation(Protocol):
    """The already-accepted typed MCP operation surface, injected by caller."""

    def __enter__(self) -> RobinhoodMcpOperation: ...

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool: ...

    def get_accounts(self) -> Mapping[str, object]: ...

    def get_portfolio(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]: ...

    def get_equity_positions(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]: ...

    def get_equity_quotes(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]: ...

    def get_equity_orders(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]: ...

    def get_equity_tradability(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]: ...

    def get_trade_approval_setting(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]: ...

    def review_equity_order(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]: ...

    def place_equity_order(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]: ...

    def cancel_equity_order(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]: ...


@dataclass(frozen=True, slots=True)
class _AccountIdentity:
    number: str
    fingerprint: str
    active: bool
    agentic_allowed: bool
    account_type: str | None


class RobinhoodMcpAdapter:
    """Compose current facts and one-shot writes around an injected MCP scope."""

    __slots__ = ("_transport_factory", "_capabilities", "_max_fact_age")

    def __init__(
        self,
        transport_factory: Callable[[], AbstractContextManager[object]],
        *,
        capabilities: RobinhoodAdapterCapabilities | None = None,
        max_fact_age: timedelta = timedelta(seconds=30),
    ) -> None:
        if not callable(transport_factory):
            raise TypeError("transport_factory must be callable")
        if capabilities is not None and not isinstance(
            capabilities, RobinhoodAdapterCapabilities
        ):
            raise TypeError("capabilities must be RobinhoodAdapterCapabilities")
        if not isinstance(max_fact_age, timedelta) or max_fact_age <= timedelta(0):
            raise ValueError("max_fact_age must be positive")
        self._transport_factory = transport_factory
        self._capabilities = capabilities or RobinhoodAdapterCapabilities()
        self._max_fact_age = max_fact_age

    @property
    def capabilities(self) -> RobinhoodAdapterCapabilities:
        """The explicitly supplied non-authorizing read/term capability facts."""
        return self._capabilities

    def read_snapshot(
        self,
        as_of: datetime,
        state: RuntimeState,
    ) -> BrokerSnapshot:
        """Read bounded broker facts; incomplete scope remains explicit."""
        at = normalize_utc(as_of, "as_of")
        if not isinstance(state, RuntimeState):
            raise TypeError("state must be RuntimeState")
        with self._operation() as transport:
            account = self._resolve_account(transport, state.account_fingerprint)
            portfolio = self._read_portfolio(transport, account.number)
            position_rows, position_pages, positions_exhausted = self._read_pages(
                transport.get_equity_positions,
                {"account_number": account.number},
                "positions",
            )
            order_args: dict[str, object] = {"account_number": account.number}
            if not self._capabilities.test_only_orders_account_wide_all_agents:
                # This exact accepted repository query is only the agentic
                # partition. It is never represented as all-agent evidence.
                order_args["placed_agent"] = "agentic"
            order_rows, order_pages, orders_exhausted = self._read_pages(
                transport.get_equity_orders, order_args, "orders"
            )
            orders, orders_valid = self._normalize_orders(
                order_rows,
                account_fingerprint=account.fingerprint,
                state=state,
                observed_at=at,
            )
            positions, positions_valid = self._normalize_positions(position_rows)
            exact_scope = (
                positions_exhausted
                and positions_valid
                and orders_exhausted
                and orders_valid
                and self._capabilities.test_only_positions_account_wide
                and self._capabilities.test_only_orders_account_wide_all_agents
            )
            owners = (
                self._position_owners(positions, orders, state)
                if exact_scope
                else {symbol: None for symbol in positions}
            )
            tradability = self._read_tradability(transport, account, at)
            setting_enabled = self._read_approval_setting(transport, account.number)
            requests, approvals_exhaustive = self._read_approval_requests(
                transport,
                account=account,
                state=state,
                observed_at=at,
            )

        positions_scope = ScopeFacts(
            account_fingerprint=account.fingerprint,
            all_agents=(
                self._capabilities.test_only_positions_account_wide
                and positions_exhausted
                and positions_valid
            ),
            exhausted=positions_exhausted and positions_valid,
            page_count=max(1, position_pages),
            observed_at=at,
        )
        orders_scope = ScopeFacts(
            account_fingerprint=account.fingerprint,
            all_agents=(
                self._capabilities.test_only_orders_account_wide_all_agents
                and orders_exhausted
                and orders_valid
            ),
            exhausted=orders_exhausted and orders_valid,
            page_count=max(1, order_pages),
            observed_at=at,
        )
        approvals = ApprovalFacts(
            account_fingerprint=account.fingerprint,
            source_identity=state.source_identity,
            session_fingerprint=state.session_fingerprint,
            state_revision=state.revision,
            setting_enabled=setting_enabled,
            unresolved_refs=tuple(
                fact.ref_id
                for fact in requests
                if fact.ref_id is not None
                and fact.status is ApprovalRequestStatus.PENDING
            ),
            exhaustive=approvals_exhaustive,
            observed_at=at,
            requests=requests,
        )
        account_facts = AccountFacts(
            fingerprint=account.fingerprint,
            active=account.active,
            agentic_allowed=account.agentic_allowed,
            cash=portfolio.cash,
            buying_power=portfolio.buying_power,
            unleveraged_buying_power=portfolio.unleveraged_buying_power,
            equity=portfolio.equity_value,
            total_market_exposure=portfolio.equity_value,
            observed_at=at,
        )
        return BrokerSnapshot(
            observed_at=at,
            source_identity=state.source_identity,
            session_fingerprint=state.session_fingerprint,
            state_revision=state.revision,
            account=account_facts,
            positions=positions,
            position_owners=owners,
            orders=orders,
            position_scope=positions_scope,
            order_scope=orders_scope,
            tradability=tradability,
            approvals=approvals,
            review=None,
        )

    def read_quotes(
        self,
        as_of: datetime,
        *,
        now: datetime,
    ) -> Mapping[Symbol, PriceObservation]:
        """Read exactly QQQ/TQQQ/SQQQ last-trade prices with age checks."""
        at = normalize_utc(as_of, "as_of")
        current = normalize_utc(now, "now")
        if current < at or current - at > self._max_fact_age:
            raise RobinhoodAdapterUnavailableError("quote observation is stale")
        with self._operation() as transport:
            try:
                payload = transport.get_equity_quotes(
                    {"symbols": [str(symbol) for symbol in UNIVERSE_SYMBOLS]}
                )
                parsed = parse_equity_quotes_response(payload)
            except Exception:
                raise RobinhoodAdapterUnavailableError(
                    "quote facts are unavailable"
                ) from None
        quotes = self._quote_map(parsed, current)
        if set(quotes) != set(UNIVERSE_SYMBOLS):
            raise RobinhoodAdapterUnavailableError(
                "the exact QQQ/TQQQ/SQQQ quote set is incomplete"
            )
        return {symbol: quotes[symbol] for symbol in UNIVERSE_SYMBOLS}

    def review_order(
        self,
        intent: LogicalOrderIntent,
        broker: BrokerSnapshot,
        *,
        observed_at: datetime,
    ) -> BrokerReviewFacts:
        """Review one supported exact intent and locally bind un-echoed terms."""
        at = normalize_utc(observed_at, "observed_at")
        if not isinstance(intent, LogicalOrderIntent):
            raise TypeError("intent must be LogicalOrderIntent")
        self._require_snapshot_binding(broker, at)
        if (
            intent.lifecycle is not IntentLifecycle.PROPOSED
            or intent.source_identity != broker.source_identity
            or not broker.account.active
            or not broker.account.agentic_allowed
            or broker.account.fingerprint != broker.approvals.account_fingerprint
            or broker.approvals.source_identity != broker.source_identity
            or broker.approvals.session_fingerprint != broker.session_fingerprint
            or broker.approvals.state_revision != broker.state_revision
        ):
            raise RobinhoodAdapterIdentityError("review facts are not identity-bound")
        args_without_account = self._order_arguments(
            intent,
            broker,
            include_ref_id=False,
            now=at,
        )
        with self._operation() as transport:
            account = self._resolve_account(transport, broker.account.fingerprint)
            self._require_active_account(account)
            args = {"account_number": account.number, **args_without_account}
            try:
                payload = transport.review_equity_order(args)
            except Exception:
                raise RobinhoodAdapterUnavailableError(
                    "broker review is unavailable"
                ) from None
        status, warnings, approval_required = self._normalize_review(
            payload,
            intent=intent,
            expected=args_without_account,
            observed_at=at,
        )
        return BrokerReviewFacts(
            account_fingerprint=broker.account.fingerprint,
            source_identity=broker.source_identity,
            session_fingerprint=broker.session_fingerprint,
            state_revision=broker.state_revision,
            ref_id=intent.ref_id,
            terms_digest=intent.terms_digest,
            status=status,
            warnings=warnings,
            approval_required=approval_required,
            observed_at=at,
        )

    def place_order(
        self,
        *,
        state: RuntimeState,
        reservation: OrderWriteReservation,
        broker: BrokerSnapshot,
        permit: InProcessWritePermit,
        observed_at: datetime,
    ) -> RobinhoodEffectOutcome:
        """Consume a fresh one-shot permit immediately before one place call."""

        at = normalize_utc(observed_at, "observed_at")
        if not isinstance(permit, InProcessWritePermit):
            raise RobinhoodAdapterUnavailableError(
                "a fresh in-process placement permit is required"
            )
        self._require_durable_write(
            state=state,
            reservation=reservation,
            broker=broker,
            action=OrderWriteAction.PLACE,
            now=at,
        )
        if (
            reservation.review is None
            or reservation.review_revision
            not in (reservation.expected_revision, reservation.expected_revision - 1)
            or reservation.review.state_revision != reservation.review_revision
            or reservation.review.ref_id != reservation.ref_id
            or reservation.review.terms_digest != reservation.terms_digest
            or reservation.review.account_fingerprint != reservation.account_fingerprint
            or reservation.review.source_identity != reservation.source_identity
            or reservation.review.session_fingerprint != reservation.session_fingerprint
            or reservation.review.status is not ReviewStatus.ACCEPTED
            or reservation.review.warnings
            or reservation.review.approval_required
            or not self._fresh(reservation.review.observed_at, at)
            or broker.state_revision != reservation.expected_revision
            or (broker.review is not None and broker.review != reservation.review)
        ):
            raise RobinhoodAdapterUnavailableError(
                "placement review is stale or mismatched"
            )
        intent = self._reserved_intent(state, reservation)
        if reservation.approval_id is not None:
            raise RobinhoodAdapterUnavailableError(
                "approval linkage is not established for placement"
            )
        order = self._order_arguments(
            intent,
            broker,
            include_ref_id=True,
            now=at,
        )
        with self._operation() as transport:
            account = self._resolve_account(transport, reservation.account_fingerprint)
            self._require_active_account(account)
            args = {"account_number": account.number, **order}
            # No operation, account lookup, argument shaping, or retry lies
            # between one-shot permission consumption and this single call.
            if not permit.consume(reservation, action=OrderWriteAction.PLACE):
                raise RobinhoodAdapterUnavailableError(
                    "one-shot placement permit was already consumed"
                )
            try:
                payload = transport.place_equity_order(args)
            except Exception:
                return self._effect_outcome(
                    status=RobinhoodEffectStatus.UNKNOWN,
                    reservation=reservation,
                    observed_at=at,
                )
        return self._placement_outcome(payload, reservation, at)

    def cancel_order(
        self,
        *,
        state: RuntimeState,
        reservation: OrderWriteReservation,
        broker: BrokerSnapshot,
        permit: InProcessWritePermit,
        observed_at: datetime,
    ) -> RobinhoodEffectOutcome:
        """Cancel only the exact fresh-account order owned by a durable stop."""

        at = normalize_utc(observed_at, "observed_at")
        if not isinstance(permit, InProcessWritePermit):
            raise RobinhoodAdapterUnavailableError(
                "a fresh in-process cancellation permit is required"
            )
        self._require_durable_write(
            state=state,
            reservation=reservation,
            broker=broker,
            action=OrderWriteAction.CANCEL,
            now=at,
        )
        target_id = reservation.target_provider_order_id
        if target_id is None:
            raise RobinhoodAdapterUnavailableError("cancel target is missing")
        intent = self._reserved_intent(state, reservation)
        if intent.kind is not IntentKind.PROTECTIVE_STOP:
            raise RobinhoodAdapterUnavailableError(
                "only an owned protective stop may be canceled"
            )
        matches = tuple(
            fact
            for fact in broker.orders
            if fact.provider_order_id == target_id
            and fact.account_fingerprint == reservation.account_fingerprint
            and fact.intent_id == intent.intent_id
            and fact.ref_id in (None, intent.ref_id)
            and fact.symbol == intent.symbol
            and fact.side is OrderSide.SELL
            and fact.kind is IntentKind.PROTECTIVE_STOP
            and fact.requested_quantity == intent.quantity
            and fact.filled_quantity + fact.remaining_quantity == intent.quantity
            and (
                fact.source_identity is None
                or fact.source_identity == reservation.source_identity
            )
            and fact.stop_price == intent.stop_price
        )
        if len(matches) != 1 or matches[0].state not in (
            OrderState.OPEN,
            OrderState.PARTIALLY_FILLED,
        ):
            raise RobinhoodAdapterUnavailableError(
                "cancel target lacks exact current ownership and open state"
            )
        with self._operation() as transport:
            account = self._resolve_account(transport, reservation.account_fingerprint)
            self._require_active_account(account)
            args = {
                "account_number": account.number,
                "order_id": target_id,
            }
            if not permit.consume(reservation, action=OrderWriteAction.CANCEL):
                raise RobinhoodAdapterUnavailableError(
                    "one-shot cancellation permit was already consumed"
                )
            try:
                payload = transport.cancel_equity_order(args)
            except Exception:
                return self._effect_outcome(
                    status=RobinhoodEffectStatus.UNKNOWN,
                    reservation=reservation,
                    observed_at=at,
                )
        return self._cancellation_outcome(payload, reservation, at)

    def _operation(self) -> AbstractContextManager[object]:
        try:
            operation = self._transport_factory()
        except Exception:
            raise RobinhoodAdapterUnavailableError(
                "Robinhood MCP operation is unavailable"
            ) from None
        if not callable(getattr(operation, "__enter__", None)) or not callable(
            getattr(operation, "__exit__", None)
        ):
            raise RobinhoodAdapterUnavailableError(
                "Robinhood MCP operation has no session scope"
            )
        return cast(AbstractContextManager[object], operation)

    @staticmethod
    def _resolve_account(
        transport: object,
        expected_fingerprint: str,
    ) -> _AccountIdentity:
        try:
            payload = transport.get_accounts()
            number = RobinhoodAgenticAccountResolver(lambda: payload).resolve()
            fingerprint = hashlib.sha256(number.encode("utf-8")).hexdigest()
            root = _data(payload)
            accounts = root.get("accounts")
            if not isinstance(accounts, list):
                raise ValueError
            record = next(
                item
                for item in accounts
                if isinstance(item, Mapping) and item.get("account_number") == number
            )
            allowed = record.get("agentic_allowed")
            state_value = record.get("state")
            deactivated = record.get("deactivated")
            permanently_deactivated = record.get("permanently_deactivated")
            if type(allowed) is not bool:
                raise ValueError
            active = (
                state_value == "active"
                and deactivated is False
                and permanently_deactivated is False
            )
            account_type = record.get("brokerage_account_type")
            if account_type is not None and not isinstance(account_type, str):
                raise ValueError
            if fingerprint != expected_fingerprint:
                raise RobinhoodAdapterIdentityError(
                    "fresh Robinhood account does not match runtime identity"
                )
            return _AccountIdentity(
                number,
                fingerprint,
                active,
                allowed,
                account_type,
            )
        except RobinhoodAdapterIdentityError:
            raise
        except Exception:
            raise RobinhoodAdapterUnavailableError(
                "eligible Robinhood account identity is unavailable"
            ) from None

    @staticmethod
    def _require_active_account(account: _AccountIdentity) -> None:
        if not account.active or not account.agentic_allowed:
            raise RobinhoodAdapterUnavailableError(
                "Robinhood account is inactive or ineligible"
            )

    @staticmethod
    def _read_portfolio(transport: object, account_number: str) -> object:
        try:
            payload = transport.get_portfolio({"account_number": account_number})
            return parse_portfolio(payload)
        except Exception:
            raise RobinhoodAdapterUnavailableError(
                "portfolio cash and buying-power facts are unavailable"
            ) from None

    @staticmethod
    def _read_pages(
        reader: Callable[[Mapping[str, object]], Mapping[str, object]],
        base_arguments: Mapping[str, object],
        collection_name: str,
    ) -> tuple[tuple[Mapping[str, object], ...], int, bool]:
        rows: list[Mapping[str, object]] = []
        cursor: str | None = None
        seen: set[str] = set()
        pages = 0
        for _ in range(MAX_READ_PAGES):
            arguments = dict(base_arguments)
            if cursor is not None:
                arguments["cursor"] = cursor
            pages += 1
            try:
                payload = reader(arguments)
                data = _data(payload)
                page_rows = data.get(collection_name)
                if type(page_rows) is not list or len(page_rows) > MAX_ROWS_PER_PAGE:
                    return tuple(rows), pages, False
                if any(not isinstance(row, Mapping) for row in page_rows):
                    return tuple(rows), pages, False
                rows.extend(cast(Sequence[Mapping[str, object]], page_rows))
                if len(rows) > MAX_READ_PAGES * MAX_ROWS_PER_PAGE:
                    return tuple(rows), pages, False
                if "next" not in data:
                    return tuple(rows), pages, False
                next_cursor = data["next"]
            except Exception:
                return tuple(rows), pages, False
            if next_cursor is None or next_cursor == "":
                return tuple(rows), pages, True
            if (
                not isinstance(next_cursor, str)
                or len(next_cursor) > MAX_CURSOR_LENGTH
                or next_cursor in seen
            ):
                return tuple(rows), pages, False
            seen.add(next_cursor)
            cursor = next_cursor
        return tuple(rows), pages, False

    @staticmethod
    def _normalize_positions(
        rows: tuple[Mapping[str, object], ...],
    ) -> tuple[dict[Symbol, Position], bool]:
        positions: dict[Symbol, Position] = {}
        complete = True
        for row in rows:
            try:
                symbol = Symbol(_required_text(row.get("symbol"), "symbol"))
                quantity = _decimal(row.get("quantity"), "quantity")
                available = _decimal(
                    row.get("shares_available_for_sells"),
                    "shares_available_for_sells",
                )
                position_type = row.get("type")
                if position_type not in ("long", "short", "empty") or available < 0:
                    complete = False
                    continue
                if quantity == 0:
                    if position_type != "empty":
                        complete = False
                    continue
                if quantity < 0 or position_type != "long" or available > quantity:
                    complete = False
                    continue
                average = _decimal(row.get("average_buy_price"), "average_buy_price")
                if average <= 0:
                    complete = False
                    continue
                if symbol in positions:
                    complete = False
                    continue
                positions[symbol] = Position(symbol, quantity, average)
            except Exception:
                complete = False
        return positions, complete

    @classmethod
    def _normalize_orders(
        cls,
        rows: tuple[Mapping[str, object], ...],
        *,
        account_fingerprint: str,
        state: RuntimeState,
        observed_at: datetime,
    ) -> tuple[tuple[BrokerOrderFact, ...], bool]:
        result: list[BrokerOrderFact] = []
        complete = True
        seen_order_ids: set[str] = set()
        for row in rows:
            try:
                order = cls._parse_order_row(row)
                if order.order_id in seen_order_ids:
                    complete = False
                    continue
                seen_order_ids.add(order.order_id)
                if order.dollar_based_amount is not None or order.quantity is None:
                    complete = False
                    continue
                requested = order.quantity
                filled = order.cumulative_quantity
                if requested <= 0 or filled > requested:
                    complete = False
                    continue
                remaining = _decimal_difference_exact(requested, filled)
                kind = _kind_for_order(order)
                intent = cls._matching_intent(
                    order,
                    state,
                    account_fingerprint=account_fingerprint,
                )
                result.append(
                    BrokerOrderFact(
                        provider_order_id=order.order_id,
                        account_fingerprint=account_fingerprint,
                        source_identity=(state.source_identity if intent else None),
                        intent_id=(intent.intent_id if intent else None),
                        ref_id=order.ref_id,
                        kind=kind,
                        symbol=order.symbol,
                        side=order.side,
                        state=_order_state(order.state),
                        requested_quantity=requested,
                        filled_quantity=filled,
                        remaining_quantity=remaining,
                        stop_price=order.stop_price,
                        observed_at=observed_at,
                        average_fill_price=order.average_price,
                    )
                )
            except Exception:
                complete = False
        return tuple(result), complete

    @staticmethod
    def _parse_order_row(row: Mapping[str, object]) -> RobinhoodEquityOrder:
        return cast(
            RobinhoodEquityOrder,
            parse_equity_orders_response({"data": {"orders": [dict(row)]}}).orders[0],
        )

    @staticmethod
    def _matching_intent(
        order: RobinhoodEquityOrder,
        state: RuntimeState,
        *,
        account_fingerprint: str,
    ) -> LogicalOrderIntent | None:
        candidates = (
            tuple(item for item in state.intents if item.ref_id == order.ref_id)
            if order.ref_id is not None
            else ()
        )
        if not candidates:
            bound_intent_ids = tuple(
                tracked.intent_id
                for tracked in state.tracked_orders
                if tracked.provider_order_id == order.order_id
                or (order.ref_id is not None and tracked.approval_id == order.ref_id)
            )
            candidates = tuple(
                item for item in state.intents if item.intent_id in bound_intent_ids
            )
        if not candidates and order.ref_id is None:
            from .order_tracker import OrderWriteAction, OrderWriteStatus

            reserved_intent_ids = {
                reservation.intent_id
                for reservation in state.write_reservations
                if reservation.action is OrderWriteAction.PLACE
                and reservation.status is OrderWriteStatus.MAY_HAVE_OCCURRED
                and reservation.owner_id == state.owner_id
                and reservation.source_identity == state.source_identity
                and reservation.account_fingerprint == account_fingerprint
                and reservation.session_fingerprint == state.session_fingerprint
            }
            candidates = tuple(
                item
                for item in state.intents
                if item.intent_id in reserved_intent_ids
                and item.lifecycle is IntentLifecycle.MAY_HAVE_OCCURRED
                and not any(
                    tracked.intent_id == item.intent_id
                    and tracked.provider_order_id not in (None, order.order_id)
                    for tracked in state.tracked_orders
                )
                and RobinhoodMcpAdapter._order_matches_intent(order, item)
            )
        if len(candidates) != 1:
            return None
        intent = candidates[0]
        if intent.lifecycle not in (
            IntentLifecycle.MAY_HAVE_OCCURRED,
            IntentLifecycle.UNKNOWN,
            IntentLifecycle.RECONCILED,
        ):
            return None
        if not RobinhoodMcpAdapter._order_matches_intent(order, intent):
            return None
        return intent

    @staticmethod
    def _order_matches_intent(
        order: RobinhoodEquityOrder,
        intent: LogicalOrderIntent,
    ) -> bool:
        expected_type = (
            "stop_market" if intent.kind is IntentKind.PROTECTIVE_STOP else "market"
        )
        return not (
            order.symbol != intent.symbol
            or order.side is not intent.side
            or order.quantity != intent.quantity
            or order.stop_price != intent.stop_price
            or order.order_type != expected_type
            or order.market_hours != REGULAR_MARKET_HOURS
            or order.time_in_force != _time_in_force(intent)
        )

    @staticmethod
    def _position_owners(
        positions: Mapping[Symbol, Position],
        orders: tuple[BrokerOrderFact, ...],
        state: RuntimeState,
    ) -> dict[Symbol, UUID | None]:
        owners: dict[Symbol, UUID | None] = {}
        strategy_positions = tuple(
            symbol for symbol in positions if symbol in TRADED_SYMBOLS
        )
        multiple_strategy_positions = len(strategy_positions) > 1
        tracked_intent_ids = {item.intent_id for item in state.tracked_orders}
        for symbol, position in positions.items():
            owned = state.positions.get(symbol)
            exact_entry_facts = tuple(
                fact
                for fact in orders
                if fact.intent_id is not None
                and fact.kind is IntentKind.ENTRY
                and fact.side is OrderSide.BUY
                and fact.symbol == symbol
                and fact.state is OrderState.FILLED
                and fact.filled_quantity == fact.requested_quantity
                and fact.remaining_quantity == 0
                and fact.average_fill_price is not None
            )
            candidate_ids: list[UUID] = []
            for entry_fact in exact_entry_facts:
                entry_intent = next(
                    (
                        item
                        for item in state.intents
                        if item.intent_id == entry_fact.intent_id
                    ),
                    None,
                )
                tracked = next(
                    (
                        item
                        for item in state.tracked_orders
                        if item.intent_id == entry_fact.intent_id
                        and (
                            item.provider_order_id == entry_fact.provider_order_id
                            or (
                                entry_fact.ref_id is not None
                                and (
                                    item.ref_id == entry_fact.ref_id
                                    or item.approval_id == entry_fact.ref_id
                                )
                            )
                            or (
                                entry_fact.ref_id is None
                                and item.provider_order_id is None
                                and any(
                                    reservation.intent_id == item.intent_id
                                    and reservation.ref_id == item.ref_id
                                    and reservation.account_fingerprint
                                    == entry_fact.account_fingerprint
                                    and reservation.action.value == "PLACE"
                                    and reservation.status.value == "MAY_HAVE_OCCURRED"
                                    for reservation in state.write_reservations
                                )
                            )
                        )
                    ),
                    None,
                )
                if (
                    entry_intent is None
                    or tracked is None
                    or entry_intent.kind is not IntentKind.ENTRY
                    or entry_intent.side is not OrderSide.BUY
                    or entry_intent.symbol != symbol
                    or entry_intent.quantity != entry_fact.requested_quantity
                    or entry_intent.ref_id != tracked.ref_id
                    or entry_fact.average_fill_price != position.average_cost
                ):
                    continue
                if owned is None:
                    # The first observed fill must be attributable before the
                    # application can create its OwnedPositionRecord.
                    if position.quantity == entry_fact.filled_quantity:
                        candidate_ids.append(entry_intent.intent_id)
                    continue
                if (
                    entry_intent.intent_id != owned.entry_intent_id
                    or entry_fact.requested_quantity != owned.quantity
                    or entry_fact.average_fill_price != owned.average_entry_fill
                    or position.quantity > owned.quantity
                ):
                    continue
                exact_sells = tuple(
                    fact
                    for fact in orders
                    if fact.symbol == symbol
                    and fact.side is OrderSide.SELL
                    and fact.kind in (IntentKind.EXIT, IntentKind.PROTECTIVE_STOP)
                    and fact.intent_id is not None
                    and any(
                        tracked_order.intent_id == fact.intent_id
                        for tracked_order in state.tracked_orders
                    )
                )
                sells_known = all(
                    fact.state
                    in (
                        OrderState.FILLED,
                        OrderState.CANCELED,
                        OrderState.REJECTED,
                        OrderState.OPEN,
                        OrderState.PARTIALLY_FILLED,
                    )
                    for fact in exact_sells
                )
                if sells_known and _quantity_balance_matches(
                    entry_fact.filled_quantity,
                    position.quantity,
                    tuple(fact.filled_quantity for fact in exact_sells),
                ):
                    candidate_ids.append(entry_intent.intent_id)
            candidate_entry_id = candidate_ids[0] if len(candidate_ids) == 1 else None
            conflicting_order = any(
                fact.symbol == symbol
                and fact.intent_id not in tracked_intent_ids
                and (
                    fact.filled_quantity > 0
                    or fact.state
                    in (
                        OrderState.OPEN,
                        OrderState.PARTIALLY_FILLED,
                        OrderState.PENDING_CANCEL,
                        OrderState.UNKNOWN,
                    )
                )
                for fact in orders
            ) or any(
                fact.symbol == symbol
                and fact.kind is IntentKind.ENTRY
                and fact.intent_id != candidate_entry_id
                and (
                    fact.filled_quantity > 0
                    or fact.state
                    in (
                        OrderState.OPEN,
                        OrderState.PARTIALLY_FILLED,
                        OrderState.PENDING_CANCEL,
                        OrderState.UNKNOWN,
                    )
                )
                for fact in orders
            )
            owners[symbol] = (
                candidate_ids[0]
                if len(candidate_ids) == 1
                and not conflicting_order
                and not multiple_strategy_positions
                else None
            )
        return owners

    def _read_tradability(
        self,
        transport: object,
        account: _AccountIdentity,
        observed_at: datetime,
    ) -> dict[Symbol, TradabilityFacts]:
        result: dict[Symbol, TradabilityFacts] = {}
        for symbol in UNIVERSE_SYMBOLS:
            facts = TradabilityFacts(
                symbol,
                observed_at,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            )
            try:
                payload = transport.get_equity_tradability(
                    {"account_number": account.number, "symbols": [str(symbol)]}
                )
                facts = self._parse_tradability(
                    payload,
                    symbol=symbol,
                    account_type=account.account_type,
                    observed_at=observed_at,
                )
            except Exception:
                pass
            result[symbol] = facts
        return result

    @staticmethod
    def _parse_tradability(
        payload: Mapping[str, object],
        *,
        symbol: Symbol,
        account_type: str | None,
        observed_at: datetime,
    ) -> TradabilityFacts:
        data = _data(payload)
        results = data.get("results")
        if (
            type(results) is not list
            or len(results) != 1
            or not isinstance(results[0], Mapping)
        ):
            raise ValueError("tradability result set is not exact")
        row = results[0]
        if row.get("symbol") != str(symbol):
            raise ValueError("tradability symbol differs from request")
        state_value = row.get("state")
        active = state_value == "active" if isinstance(state_value, str) else None
        halted = row.get("halted") if type(row.get("halted")) is bool else None
        if halted is None and isinstance(state_value, str):
            if state_value.lower() == "halted":
                halted = True
            elif state_value.lower() == "active":
                halted = False
        regular = (
            row.get("regular_session_eligible")
            if type(row.get("regular_session_eligible")) is bool
            else None
        )
        fractional = _optional_bool(row.get("fractional_entry_supported"))
        if fractional is None:
            generic = row.get("fractional_tradability")
            if generic in ("tradable", "not_tradable"):
                fractional = generic == "tradable"
        if fractional is None and account_type is not None:
            types = row.get("account_type_tradabilities")
            if isinstance(types, list):
                exact = tuple(
                    item
                    for item in types
                    if isinstance(item, Mapping)
                    and item.get("account_type") == account_type
                )
                if len(exact) == 1:
                    status = exact[0].get("account_type_tradability")
                    if status in ("tradable", "not_tradable"):
                        fractional = status == "tradable"
        tradable = row.get("tradeable")
        if active is None and type(tradable) is bool:
            active = tradable
        return TradabilityFacts(
            symbol=symbol,
            observed_at=observed_at,
            active=active,
            halted=halted,
            regular_session_eligible=regular,
            fractional_entry_supported=fractional,
            stop_market_supported=_optional_bool(row.get("stop_market_supported")),
            fractional_stop_supported=_optional_bool(
                row.get("fractional_stop_supported")
            ),
            exact_stop_price_supported=_optional_bool(
                row.get("exact_stop_price_supported")
            ),
        )

    @staticmethod
    def _read_approval_setting(transport: object, account_number: str) -> bool | None:
        try:
            payload = transport.get_trade_approval_setting(
                {"account_number": account_number}
            )
            value = _data(payload).get("enabled")
            return value if type(value) is bool else None
        except Exception:
            return None

    def _read_approval_requests(
        self,
        transport: object,
        *,
        account: _AccountIdentity,
        state: RuntimeState,
        observed_at: datetime,
    ) -> tuple[tuple[ProviderApprovalFact, ...], bool]:
        if not self._capabilities.test_only_approval_requests_exhaustive:
            return (), False
        reader = getattr(transport, "get_trade_approvals", None)
        if not callable(reader):
            return (), False
        rows, _, exhausted = self._read_pages(
            reader,
            {"account_number": account.number},
            "approvals",
        )
        facts: list[ProviderApprovalFact] = []
        valid = exhausted
        for row in rows:
            try:
                facts.append(
                    self._parse_approval(
                        row,
                        account=account,
                        state=state,
                        observed_at=observed_at,
                    )
                )
            except Exception:
                valid = False
        return tuple(facts), valid

    @staticmethod
    def _parse_approval(
        row: Mapping[str, object],
        *,
        account: _AccountIdentity,
        state: RuntimeState,
        observed_at: datetime,
    ) -> ProviderApprovalFact:
        approval_id = _required_text(row.get("approval_id"), "approval_id")
        symbol = Symbol(_required_text(row.get("symbol"), "symbol"))
        side_value = row.get("side")
        side = (
            OrderSide.BUY
            if side_value == "buy"
            else OrderSide.SELL
            if side_value == "sell"
            else None
        )
        if side is None:
            raise ValueError("approval side is invalid")
        status_value = row.get("status")
        status = {
            "pending": ApprovalRequestStatus.PENDING,
            "approved": ApprovalRequestStatus.APPROVED,
            "rejected": ApprovalRequestStatus.REJECTED,
        }.get(status_value, ApprovalRequestStatus.UNKNOWN)
        raw_intent = row.get("intent_id")
        intent_id = _optional_uuid(raw_intent)
        ref_id = row.get("ref_id")
        if ref_id is not None and not isinstance(ref_id, str):
            raise ValueError("approval ref_id is invalid")
        return ProviderApprovalFact(
            approval_id=approval_id,
            account_fingerprint=account.fingerprint,
            source_identity=None,
            session_fingerprint=state.session_fingerprint,
            state_revision=state.revision,
            intent_id=intent_id,
            ref_id=ref_id,
            symbol=symbol,
            side=side,
            quantity=_decimal(row.get("quantity"), "quantity"),
            status=status,
            observed_at=observed_at,
        )

    def _quote_map(
        self,
        parsed: RobinhoodEquityQuotesResponse,
        now: datetime,
    ) -> dict[Symbol, PriceObservation]:
        result: dict[Symbol, PriceObservation] = {}
        for item in parsed.results:
            if item is None or item.quote is None:
                continue
            quote = item.quote
            if quote.symbol in result:
                raise RobinhoodAdapterUnavailableError(
                    "duplicate symbol quote facts were returned"
                )
            if (
                quote.symbol not in UNIVERSE_SYMBOLS
                or not quote.has_traded
                or quote.venue_last_trade_time is None
            ):
                continue
            price_at = normalize_utc(
                quote.venue_last_trade_time, "venue_last_trade_time"
            )
            if price_at > now or now - price_at > self._max_fact_age:
                continue
            result[quote.symbol] = PriceObservation(
                quote.symbol,
                quote.last_trade_price,
                price_at,
            )
        return result

    def _order_arguments(
        self,
        intent: LogicalOrderIntent,
        broker: BrokerSnapshot,
        *,
        include_ref_id: bool,
        now: datetime,
    ) -> dict[str, object]:
        if intent.symbol not in TRADED_SYMBOLS:
            raise RobinhoodAdapterUnavailableError("order symbol is unsupported")
        if _REF_ID.fullmatch(intent.ref_id) is None:
            raise RobinhoodAdapterUnavailableError(
                "deterministic order ref_id is invalid"
            )
        try:
            if str(UUID(intent.ref_id)) != intent.ref_id:
                raise ValueError
        except (ValueError, AttributeError):
            raise RobinhoodAdapterUnavailableError(
                "deterministic order ref_id is invalid"
            ) from None
        try:
            canonical = create_order_intent(
                owner_id=intent.owner_id,
                source_identity=intent.source_identity,
                logical_sequence=intent.logical_sequence,
                kind=intent.kind,
                symbol=intent.symbol,
                side=intent.side,
                quantity=intent.quantity,
                stop_price=intent.stop_price,
                created_at=intent.created_at,
                lifecycle=intent.lifecycle,
            )
        except Exception:
            raise RobinhoodAdapterUnavailableError(
                "deterministic logical-order identity is invalid"
            ) from None
        if (
            canonical.intent_id != intent.intent_id
            or canonical.ref_id != intent.ref_id
            or canonical.terms_digest != intent.terms_digest
        ):
            raise RobinhoodAdapterUnavailableError(
                "deterministic logical-order identity does not match its terms"
            )
        facts = broker.tradability.get(intent.symbol)
        if (
            facts is None
            or facts.active is not True
            or facts.halted is not False
            or facts.regular_session_eligible is not True
            or not self._fresh(facts.observed_at, now)
        ):
            raise RobinhoodAdapterUnavailableError(
                "exact-symbol regular-session tradability is unavailable"
            )
        if intent.kind is IntentKind.PROTECTIVE_STOP:
            if (
                intent.side is not OrderSide.SELL
                or intent.stop_price is None
                or intent.quantity != intent.quantity.to_integral_value()
                or facts.stop_market_supported is not True
                or facts.exact_stop_price_supported is not True
                or not self._capabilities.test_only_stop_market_gtc_supported
            ):
                raise RobinhoodAdapterUnavailableError(
                    "whole-share GTC stop-market capability is unavailable"
                )
            order_type = "stop_market"
            tif = PROTECTIVE_STOP_TIF
        elif intent.kind in (IntentKind.ENTRY, IntentKind.EXIT):
            if intent.stop_price is not None:
                raise RobinhoodAdapterUnavailableError(
                    "market order cannot include stop_price"
                )
            if (
                intent.quantity != intent.quantity.to_integral_value()
                and facts.fractional_entry_supported is not True
            ):
                raise RobinhoodAdapterUnavailableError(
                    "fractional market quantity is not established"
                )
            order_type = "market"
            tif = REGULAR_MARKET_TIF
        else:
            raise RobinhoodAdapterUnavailableError("order kind is unsupported")
        arguments: dict[str, object] = {
            "market_hours": REGULAR_MARKET_HOURS,
            "quantity": _decimal_text(intent.quantity),
            "side": "buy" if intent.side is OrderSide.BUY else "sell",
            "symbol": str(intent.symbol),
            "time_in_force": tif,
            "type": order_type,
        }
        if intent.stop_price is not None:
            arguments["stop_price"] = _decimal_text(intent.stop_price)
        if include_ref_id:
            arguments["ref_id"] = intent.ref_id
        return arguments

    def _normalize_review(
        self,
        payload: Mapping[str, object],
        *,
        intent: LogicalOrderIntent,
        expected: Mapping[str, object],
        observed_at: datetime,
    ) -> tuple[ReviewStatus, tuple[str, ...], bool]:
        try:
            data = _data(payload)
            if intent.kind is IntentKind.PROTECTIVE_STOP:
                self._validate_stop_review(data, intent, expected)
            else:
                parsed = parse_review_equity_order_response(
                    payload,
                    received_at=observed_at,
                )
                if (
                    parsed.symbol != intent.symbol
                    or parsed.side is not intent.side
                    or parsed.quantity != intent.quantity
                    or parsed.order_type.value.lower() != "market"
                ):
                    return ReviewStatus.REJECTED, ("REVIEW_TERMS_MISMATCH",), True
                if "ref_id" in data and data.get("ref_id") != intent.ref_id:
                    return ReviewStatus.REJECTED, ("REVIEW_REF_ID_MISMATCH",), True
                for key in ("market_hours", "time_in_force"):
                    if key in data and data.get(key) != expected[key]:
                        return ReviewStatus.REJECTED, ("REVIEW_TERMS_MISMATCH",), True
            order_checks = data.get("order_checks")
            if not isinstance(order_checks, Mapping):
                return ReviewStatus.UNKNOWN, ("REVIEW_CHECKS_UNAVAILABLE",), True
            approval_value = data.get("customer_approval_required")
            if type(approval_value) is not bool:
                return (
                    ReviewStatus.UNKNOWN,
                    ("REVIEW_APPROVAL_STATE_UNAVAILABLE",),
                    False,
                )
            warnings: list[str] = []
            if order_checks:
                warnings.append("ROBINHOOD_ORDER_CHECKS_PRESENT")
            if approval_value:
                warnings.append("ROBINHOOD_CUSTOMER_APPROVAL_REQUIRED")
            status = ReviewStatus.ACCEPTED if not warnings else ReviewStatus.REJECTED
            return status, tuple(warnings), approval_value
        except Exception:
            return ReviewStatus.UNKNOWN, ("REVIEW_RESPONSE_UNAVAILABLE",), True

    @staticmethod
    def _validate_stop_review(
        data: Mapping[str, object],
        intent: LogicalOrderIntent,
        expected: Mapping[str, object],
    ) -> None:
        if (
            data.get("symbol") != str(intent.symbol)
            or data.get("side") != "sell"
            or data.get("type") != "stop_market"
            or _decimal(data.get("quantity"), "quantity") != intent.quantity
            or _decimal(data.get("stop_price"), "stop_price") != intent.stop_price
        ):
            raise ValueError("stop review terms differ")
        quote = parse_quote_data(data.get("quote_data"))
        if quote.symbol != intent.symbol:
            raise ValueError("stop review quote symbol differs")
        if "ref_id" in data and data.get("ref_id") != intent.ref_id:
            raise ValueError("stop review ref_id differs")
        for key in ("market_hours", "time_in_force"):
            if key in data and data.get(key) != expected[key]:
                raise ValueError("stop review terms differ")

    def _require_durable_write(
        self,
        *,
        state: RuntimeState,
        reservation: OrderWriteReservation,
        broker: BrokerSnapshot,
        action: object,
        now: datetime,
    ) -> None:
        from .order_tracker import validate_order_write_reservation

        if not isinstance(state, RuntimeState) or not isinstance(
            broker, BrokerSnapshot
        ):
            raise TypeError("state and broker must be Architecture-148 models")
        try:
            valid = validate_order_write_reservation(state, cast(object, reservation))
        except Exception:
            valid = False
        if not valid or reservation.action is not action:
            raise RobinhoodAdapterUnavailableError(
                "durable MAY_HAVE_OCCURRED reservation is invalid"
            )
        if (
            reservation.reserved_revision != state.revision
            or reservation.owner_id != state.owner_id
            or reservation.source_identity != state.source_identity
            or reservation.account_fingerprint != state.account_fingerprint
            or reservation.session_fingerprint != state.session_fingerprint
            or reservation not in state.write_reservations
        ):
            raise RobinhoodAdapterIdentityError(
                "durable reservation identity does not match runtime state"
            )
        if (
            broker.account.fingerprint != reservation.account_fingerprint
            or broker.source_identity != reservation.source_identity
            or broker.session_fingerprint != reservation.session_fingerprint
            or broker.state_revision != reservation.expected_revision
            or not broker.account.active
            or not broker.account.agentic_allowed
            or not broker.position_scope.all_agents
            or not broker.position_scope.exhausted
            or not broker.order_scope.all_agents
            or not broker.order_scope.exhausted
            or not broker.approvals.exhaustive
            or broker.approvals.setting_enabled is not False
            or broker.approvals.unresolved_refs
            or any(
                request.status is ApprovalRequestStatus.PENDING
                for request in broker.approvals.requests
            )
            or broker.approvals.account_fingerprint != reservation.account_fingerprint
            or broker.approvals.source_identity != reservation.source_identity
            or broker.approvals.session_fingerprint != reservation.session_fingerprint
            or broker.approvals.state_revision != reservation.expected_revision
            or any(
                request.account_fingerprint != reservation.account_fingerprint
                or request.session_fingerprint != reservation.session_fingerprint
                or request.state_revision != reservation.expected_revision
                or request.status is ApprovalRequestStatus.UNKNOWN
                for request in broker.approvals.requests
            )
            or broker.approvals.requests
            or broker.position_scope.account_fingerprint
            != reservation.account_fingerprint
            or broker.order_scope.account_fingerprint != reservation.account_fingerprint
            or any(
                fact.account_fingerprint != reservation.account_fingerprint
                or (
                    fact.source_identity is not None
                    and fact.source_identity != reservation.source_identity
                )
                for fact in broker.orders
            )
            or not self._fresh(broker.account.observed_at, now)
            or not self._fresh(broker.position_scope.observed_at, now)
            or not self._fresh(broker.order_scope.observed_at, now)
            or not self._fresh(broker.approvals.observed_at, now)
        ):
            raise RobinhoodAdapterUnavailableError(
                "fresh complete broker admission facts are unavailable"
            )
        self._require_snapshot_binding(broker, now)

    def _fresh(self, observed_at: datetime, now: datetime) -> bool:
        try:
            observed = normalize_utc(observed_at, "observed_at")
            current = normalize_utc(now, "now")
        except (TypeError, ValueError):
            return False
        return observed <= current and current - observed <= self._max_fact_age

    def _require_snapshot_binding(
        self,
        broker: BrokerSnapshot,
        now: datetime,
    ) -> None:
        if not isinstance(broker, BrokerSnapshot):
            raise TypeError("broker must be BrokerSnapshot")
        current = normalize_utc(now, "now")
        observations = (
            broker.observed_at,
            broker.account.observed_at,
            broker.position_scope.observed_at,
            broker.order_scope.observed_at,
            broker.approvals.observed_at,
            *(facts.observed_at for facts in broker.tradability.values()),
            *(fact.observed_at for fact in broker.orders),
            *(fact.observed_at for fact in broker.approvals.requests),
            *((broker.review.observed_at,) if broker.review is not None else ()),
        )
        if any(not self._fresh(observed, current) for observed in observations):
            raise RobinhoodAdapterUnavailableError("broker snapshot is stale")

    @staticmethod
    def _reserved_intent(
        state: RuntimeState,
        reservation: OrderWriteReservation,
    ) -> LogicalOrderIntent:
        if reservation not in state.write_reservations:
            raise RobinhoodAdapterUnavailableError(
                "reservation is not present in durable runtime state"
            )
        matches = tuple(
            item for item in state.intents if item.intent_id == reservation.intent_id
        )
        if len(matches) != 1:
            raise RobinhoodAdapterUnavailableError(
                "reserved logical intent is missing or ambiguous"
            )
        intent = matches[0]
        required_lifecycle = (
            IntentLifecycle.MAY_HAVE_OCCURRED
            if getattr(reservation.action, "value", None) == "PLACE"
            else IntentLifecycle.RECONCILED
        )
        if (
            intent.lifecycle is not required_lifecycle
            or intent.ref_id != reservation.ref_id
            or intent.terms_digest != reservation.terms_digest
            or intent.source_identity != reservation.source_identity
        ):
            raise RobinhoodAdapterUnavailableError(
                "reserved logical intent does not match durable reservation"
            )
        return intent

    @staticmethod
    def _effect_outcome(
        *,
        status: RobinhoodEffectStatus,
        reservation: OrderWriteReservation,
        observed_at: datetime,
        provider_order_id: str | None = None,
        approval_id: str | None = None,
    ) -> RobinhoodEffectOutcome:
        return RobinhoodEffectOutcome(
            status,
            reservation.operation_id,
            reservation.intent_id,
            reservation.ref_id,
            provider_order_id,
            approval_id,
            observed_at,
        )

    @classmethod
    def _placement_outcome(
        cls,
        payload: Mapping[str, object],
        reservation: OrderWriteReservation,
        observed_at: datetime,
    ) -> RobinhoodEffectOutcome:
        try:
            data = _data(payload)
            order = data.get("order")
            if not isinstance(order, Mapping):
                return cls._effect_outcome(
                    status=RobinhoodEffectStatus.UNKNOWN,
                    reservation=reservation,
                    observed_at=observed_at,
                )
            provider_id = _required_text(order.get("id"), "order id")
            response_ref = order.get("ref_id")
            if response_ref is not None and response_ref != reservation.ref_id:
                return cls._effect_outcome(
                    status=RobinhoodEffectStatus.UNKNOWN,
                    reservation=reservation,
                    observed_at=observed_at,
                )
            return cls._effect_outcome(
                status=RobinhoodEffectStatus.PLACED,
                reservation=reservation,
                observed_at=observed_at,
                provider_order_id=provider_id,
            )
        except Exception:
            return cls._effect_outcome(
                status=RobinhoodEffectStatus.UNKNOWN,
                reservation=reservation,
                observed_at=observed_at,
            )

    @classmethod
    def _cancellation_outcome(
        cls,
        payload: Mapping[str, object],
        reservation: OrderWriteReservation,
        observed_at: datetime,
    ) -> RobinhoodEffectOutcome:
        try:
            data = _data(payload)
            order = data.get("order")
            target_id = reservation.target_provider_order_id
            if not isinstance(order, Mapping) or order.get("id") != target_id:
                return cls._effect_outcome(
                    status=RobinhoodEffectStatus.UNKNOWN,
                    reservation=reservation,
                    observed_at=observed_at,
                )
            state_value = order.get("state")
            status = (
                RobinhoodEffectStatus.CANCEL_REQUESTED
                if state_value
                in ("cancel_requested", "pending_cancel", "cancel_pending")
                else RobinhoodEffectStatus.UNKNOWN
            )
            return cls._effect_outcome(
                status=status,
                reservation=reservation,
                observed_at=observed_at,
                provider_order_id=target_id,
            )
        except Exception:
            return cls._effect_outcome(
                status=RobinhoodEffectStatus.UNKNOWN,
                reservation=reservation,
                observed_at=observed_at,
            )


def _data(payload: object) -> Mapping[str, object]:
    if not isinstance(payload, Mapping) or not isinstance(payload.get("data"), Mapping):
        raise ValueError("MCP result data is malformed")
    return cast(Mapping[str, object], payload["data"])


def _required_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a nonblank string")
    return value


def _decimal(value: object, name: str) -> Decimal:
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ValueError(f"{name} must be a bounded decimal string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"{name} must be a decimal string") from error
    if not parsed.is_finite():
        raise ValueError(f"{name} must be finite")
    return parsed


def _decimal_text(value: Decimal) -> str:
    if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        raise RobinhoodAdapterUnavailableError(
            "order quantity or stop price is invalid"
        )
    if value == 0:
        return "0"
    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def _decimal_parts_at_exponent(value: Decimal, exponent: int) -> int:
    sign, digits, value_exponent = value.as_tuple()
    coefficient = int("".join(str(digit) for digit in digits)) if digits else 0
    if sign:
        coefficient = -coefficient
    return coefficient * 10 ** (value_exponent - exponent)


def _decimal_from_scaled_integer(value: int, exponent: int) -> Decimal:
    sign = 1 if value < 0 else 0
    digits = tuple(int(character) for character in str(abs(value)))
    return Decimal((sign, digits, exponent))


def _decimal_difference_exact(left: Decimal, right: Decimal) -> Decimal:
    exponent = min(left.as_tuple().exponent, right.as_tuple().exponent)
    return _decimal_from_scaled_integer(
        _decimal_parts_at_exponent(left, exponent)
        - _decimal_parts_at_exponent(right, exponent),
        exponent,
    )


def _quantity_balance_matches(
    entry_quantity: Decimal,
    current_quantity: Decimal,
    sold_quantities: tuple[Decimal, ...],
) -> bool:
    values = (entry_quantity, current_quantity, *sold_quantities)
    exponent = min(value.as_tuple().exponent for value in values)
    return _decimal_parts_at_exponent(current_quantity, exponent) + sum(
        _decimal_parts_at_exponent(value, exponent) for value in sold_quantities
    ) == _decimal_parts_at_exponent(entry_quantity, exponent)


def _optional_bool(value: object) -> bool | None:
    return value if type(value) is bool else None


def _optional_uuid(value: object) -> UUID | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = UUID(value)
    except ValueError:
        return None
    return parsed if str(parsed) == value else None


def _kind_for_intent(intent: LogicalOrderIntent) -> IntentKind:
    return intent.kind


def _kind_for_order(order: RobinhoodEquityOrder) -> IntentKind:
    if order.side is OrderSide.BUY:
        return IntentKind.ENTRY
    if order.stop_price is not None or order.order_type == "stop_market":
        return IntentKind.PROTECTIVE_STOP
    return IntentKind.EXIT


def _time_in_force(intent: LogicalOrderIntent) -> str:
    return (
        PROTECTIVE_STOP_TIF
        if intent.kind is IntentKind.PROTECTIVE_STOP
        else REGULAR_MARKET_TIF
    )


def _order_state(value: str) -> OrderState:
    return {
        "open": OrderState.OPEN,
        "confirmed": OrderState.OPEN,
        "queued": OrderState.OPEN,
        "partially_filled": OrderState.PARTIALLY_FILLED,
        "partial_fill": OrderState.PARTIALLY_FILLED,
        "pending_cancel": OrderState.PENDING_CANCEL,
        "cancel_requested": OrderState.PENDING_CANCEL,
        "filled": OrderState.FILLED,
        "cancelled": OrderState.CANCELED,
        "canceled": OrderState.CANCELED,
        "rejected": OrderState.REJECTED,
    }.get(value.lower(), OrderState.UNKNOWN)


__all__ = [
    "RobinhoodAdapterCapabilities",
    "RobinhoodAdapterError",
    "RobinhoodAdapterIdentityError",
    "RobinhoodAdapterUnavailableError",
    "RobinhoodEffectOutcome",
    "RobinhoodEffectStatus",
    "RobinhoodMcpAdapter",
    "RobinhoodMcpOperation",
]
