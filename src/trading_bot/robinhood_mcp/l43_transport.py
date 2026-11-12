"""Narrow, effect-unwired Robinhood transport for the L43 source boundary.

This adapter validates the bounded L43 order argument shapes against the
consumed L41R5 input-schema facts.  It has no OAuth factory or production
composition.  Input schema evidence does not establish provider review or
placement semantics; review responses are normalized only as UNKNOWN unless a
later separately accepted contract establishes affirmative semantics.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from trading_bot.desktop_live.ownership import provider_order_id
from trading_bot.live_prototype.consumed_l41r5_evidence import (
    L41R5FieldSemantics,
)
from trading_bot.live_prototype.durable_state import IntentKind
from trading_bot.live_prototype.l43_provider_contracts import (
    L43PlacementReceipt,
    L43ReviewNormalization,
    L43ReviewStatus,
    L43TransportError,
)
from trading_bot.live_prototype.live_controller import PreparedInvocation
from trading_bot.live_prototype.tiny_live_policy import (
    EXACT_SELL_REVIEW_CONTRACT_ID,
    ExactOwnedSellProposal,
    ManualCloseTrigger,
    NormalizedReviewOutcome,
    NormalizedReviewSemantics,
    NormalizedSellReview,
    SellOrderArguments,
    SellOrderType,
    SellSession,
    SellSide,
    SellTimeInForce,
    evaluate_exact_owned_sell_proposal,
)

L43_TOOL_NAMES = ("review_equity_order", "place_equity_order")
MAX_DISCOVERY_PAGES = 20
MAX_CURSOR_LENGTH = 4096
MAX_ORDER_SCHEMA_ROWS = 20
MAX_RESPONSE_BYTES = 262_144
MAX_RESPONSE_DEPTH = 16
_ACCOUNT_NUMBER = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_INTENT_ID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
_L41R5_EXPECTED_ORDER_FIELD = L41R5FieldSemantics(
    present=True,
    direct_type="string",
    logical_non_null_type="string",
    required=False,
    nullable=False,
)
_L41R5_FRACTIONAL_PRECISION = (6,)
_ENTRY_LIMIT = Decimal("10.00")
_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class _AdvertisedTool:
    name: str
    properties: Mapping[str, Mapping[str, object]]
    required: frozenset[str]
    additional_properties: object


class _McpClient(Protocol):
    async def list_tools(self, *, cursor: str | None = None) -> object: ...

    async def call_tool(self, name: str, arguments: Mapping[str, object]) -> object: ...


class _L43PreparedCall:
    """One schema-checked call on an already-open session, invocable once."""

    __slots__ = (
        "_client",
        "_name",
        "_arguments",
        "_counts",
        "_expected_kind",
        "_expected_dollars",
        "_expected_quantity",
        "_expected_authority_sha256",
        "_resolved",
        "_invoked",
        "_closed",
    )

    def __init__(
        self,
        client: _McpClient,
        name: str,
        arguments: Mapping[str, object],
        counts: dict[str, int],
        *,
        expected_kind: IntentKind,
        expected_dollars: Decimal | None,
        expected_quantity: Decimal | None,
    ) -> None:
        self._client = client
        self._name = name
        self._arguments = dict(arguments)
        self._counts = counts
        self._expected_kind = expected_kind
        self._expected_dollars = expected_dollars
        self._expected_quantity = expected_quantity
        self._expected_authority_sha256: str | None = None
        self._resolved = False
        self._invoked = False
        self._closed = False

    def resolve_callable(
        self, *, authority_sha256: str | None = None
    ) -> Callable[[PreparedInvocation], Awaitable[L43PlacementReceipt]]:
        """Return an already validated callable without provider I/O."""
        if self._closed:
            raise L43TransportError("L43_PREPARED_CALL_CLOSED")
        if self._resolved:
            raise L43TransportError("L43_CALL_ALREADY_RESOLVED")
        if self._expected_kind is IntentKind.ENTRY:
            if authority_sha256 is not None:
                raise L43TransportError("L43_PREPARED_INVOCATION_MISMATCH")
        elif (
            not isinstance(authority_sha256, str)
            or _SHA256.fullmatch(authority_sha256) is None
        ):
            raise L43TransportError("L43_PREPARED_INVOCATION_MISMATCH")
        self._expected_authority_sha256 = authority_sha256
        self._resolved = True

        def invoke(permit: PreparedInvocation) -> Awaitable[L43PlacementReceipt]:
            if self._closed:
                raise L43TransportError("L43_PREPARED_CALL_CLOSED")
            if self._invoked:
                raise L43TransportError("L43_CALL_ALREADY_INVOKED")
            self._invoked = True
            if (
                type(permit) is not PreparedInvocation
                or _INTENT_ID.fullmatch(permit.intent_id) is None
                or permit.kind is not self._expected_kind
                or permit.requested_dollars != self._expected_dollars
                or permit.requested_quantity != self._expected_quantity
                or permit.authority_sha256 != self._expected_authority_sha256
            ):
                raise L43TransportError("L43_PREPARED_INVOCATION_MISMATCH")
            return self._invoke_once()

        return invoke

    async def _invoke_once(self) -> L43PlacementReceipt:
        if self._closed:
            raise L43TransportError("L43_PREPARED_CALL_CLOSED")
        self._counts[self._name] += 1
        try:
            result = await self._client.call_tool(self._name, dict(self._arguments))
        except Exception:
            raise L43TransportError("L43_PLACEMENT_RESULT_UNKNOWN") from None
        payload = _structured_payload(result)
        if payload is None:
            raise L43TransportError("L43_PLACEMENT_RESULT_UNKNOWN")
        order_id = _provider_order_id_from_envelope(payload)
        if order_id is None:
            raise L43TransportError("L43_PLACEMENT_RESULT_UNKNOWN")
        return L43PlacementReceipt(order_id)

    def invalidate(self) -> None:
        self._closed = True


class L43RobinhoodTransport:
    """Injected-session L43 boundary with only review and placement methods.

    Production credentials and production session construction deliberately
    remain outside this module.
    """

    __slots__ = ("_session_factory", "_counts")

    def __init__(self, session_factory: Callable[[], object]) -> None:
        if not callable(session_factory):
            raise TypeError("L43 session factory must be callable")
        self._session_factory = session_factory
        self._counts = dict.fromkeys(L43_TOOL_NAMES, 0)

    @classmethod
    def for_test(cls, session_factory: Callable[[], object]) -> L43RobinhoodTransport:
        return cls(session_factory)

    @property
    def call_counts(self) -> tuple[tuple[str, int], ...]:
        """Invocation attempts only; schema discovery is not a tool call."""
        return tuple((name, self._counts[name]) for name in L43_TOOL_NAMES)

    async def review_sell_order(
        self,
        *,
        account_number: str,
        proposal: ExactOwnedSellProposal,
    ) -> L43ReviewNormalization:
        _require_account_number(account_number)
        if type(proposal) is not ExactOwnedSellProposal:
            return _blocked_review(
                ManualCloseTrigger.SELL_REVIEW_MALFORMED, "L43_PROPOSAL_INVALID"
            )
        eligibility = evaluate_exact_owned_sell_proposal(proposal)
        if not eligibility.eligible_for_nonplacing_review:
            return _blocked_review(
                eligibility.manual_close_trigger
                or ManualCloseTrigger.UNSUPPORTED_EXACT_RESIDUAL,
                "L43_PROPOSAL_BLOCKED",
            )
        arguments = proposal.review_arguments
        try:
            wire = _sell_order_arguments(account_number, arguments)
        except (TypeError, ValueError):
            return _blocked_review(
                ManualCloseTrigger.UNSUPPORTED_EXACT_RESIDUAL,
                "L43_SELL_ARGUMENTS_UNSUPPORTED",
            )

        try:
            async with self._validated_session() as (client, tools):
                _validate_request_schema(
                    tools["review_equity_order"], wire, for_place=False
                )
                self._counts["review_equity_order"] += 1
                try:
                    result = await client.call_tool("review_equity_order", wire)
                except Exception:
                    return _blocked_review(
                        ManualCloseTrigger.SELL_REVIEW_UNKNOWN,
                        "L43_REVIEW_RESULT_UNKNOWN",
                    )
                payload = _structured_payload(result)
                if payload is None:
                    return _blocked_review(
                        ManualCloseTrigger.SELL_REVIEW_UNKNOWN,
                        "L43_REVIEW_RESULT_UNKNOWN",
                    )
                try:
                    return _normalize_review_payload(
                        payload,
                        proposal=proposal,
                        arguments=arguments,
                        request=wire,
                    )
                except (TypeError, ValueError, L43TransportError):
                    return _blocked_review(
                        ManualCloseTrigger.SELL_REVIEW_MALFORMED,
                        "L43_REVIEW_WIRE_SHAPE_UNKNOWN",
                    )
        except L43TransportError:
            return _blocked_review(
                ManualCloseTrigger.SELL_REVIEW_UNKNOWN,
                "L43_REVIEW_TRANSPORT_UNKNOWN",
            )

    @asynccontextmanager
    async def prepare_entry_order(
        self,
        *,
        account_number: str,
        requested_dollars: Decimal,
        ref_id: str | None = None,
    ) -> AsyncIterator[_L43PreparedCall]:
        """Discover/validate before reservation; keep the client open for one call."""
        _require_account_number(account_number)
        _validate_entry_dollars(requested_dollars)
        _validate_optional_ref_id(ref_id)
        async with self._validated_session() as (client, tools):
            arguments: dict[str, object] = {
                "account_number": account_number,
                "dollar_amount": _decimal_text(requested_dollars),
                "market_hours": "regular_hours",
                "side": "buy",
                "symbol": "SPY",
                "time_in_force": "gfd",
                "type": "market",
            }
            place_schema = tools["place_equity_order"]
            if ref_id is not None:
                if "ref_id" not in place_schema.properties:
                    raise L43TransportError("L43_REF_ID_UNSUPPORTED")
                arguments["ref_id"] = ref_id
            _validate_request_schema(place_schema, arguments, for_place=True)
            prepared = _L43PreparedCall(
                client,
                "place_equity_order",
                arguments,
                self._counts,
                expected_kind=IntentKind.ENTRY,
                expected_dollars=requested_dollars,
                expected_quantity=None,
            )
            try:
                yield prepared
            finally:
                prepared.invalidate()

    @asynccontextmanager
    async def prepare_sell_order(
        self,
        *,
        account_number: str,
        arguments: SellOrderArguments,
    ) -> AsyncIterator[_L43PreparedCall]:
        """Prepare exact quantity placement using the review argument mapping."""
        _require_account_number(account_number)
        wire = _sell_order_arguments(account_number, arguments)
        async with self._validated_session() as (client, tools):
            _validate_request_schema(tools["place_equity_order"], wire, for_place=True)
            prepared = _L43PreparedCall(
                client,
                "place_equity_order",
                wire,
                self._counts,
                expected_kind=IntentKind.EXIT,
                expected_dollars=None,
                expected_quantity=arguments.quantity,
            )
            try:
                yield prepared
            finally:
                prepared.invalidate()

    @asynccontextmanager
    async def _validated_session(
        self,
    ) -> AsyncIterator[tuple[_McpClient, dict[str, _AdvertisedTool]]]:
        try:
            manager = self._session_factory()
        except Exception:
            raise L43TransportError("L43_SESSION_FACTORY_FAILED") from None
        try:
            client = await manager.__aenter__()
        except Exception:
            raise L43TransportError("L43_SESSION_OPEN_FAILED") from None
        try:
            try:
                tools = await _discover_required_tools(client)
            except L43TransportError:
                raise
            except Exception:
                raise L43TransportError("L43_SCHEMA_DISCOVERY_FAILED") from None
            yield client, tools
        except BaseException as error:
            try:
                await manager.__aexit__(type(error), error, error.__traceback__)
            except Exception:
                pass
            raise
        else:
            try:
                await manager.__aexit__(None, None, None)
            except Exception:
                raise L43TransportError("L43_SESSION_CLOSE_FAILED") from None


async def _discover_required_tools(
    client: _McpClient,
) -> dict[str, _AdvertisedTool]:
    found: dict[str, _AdvertisedTool] = {}
    cursor: str | None = None
    seen: set[str] = set()
    for _ in range(MAX_DISCOVERY_PAGES):
        listing = await client.list_tools(cursor=cursor)
        entries = _listing_tools(listing)
        if len(entries) > MAX_ORDER_SCHEMA_ROWS:
            raise L43TransportError("L43_TOOL_PAGE_BOUND_EXCEEDED")
        for entry in entries:
            tool = _advertised_tool(entry)
            if tool.name not in L43_TOOL_NAMES:
                continue
            if tool.name in found:
                raise L43TransportError("L43_DUPLICATE_TOOL_SCHEMA")
            found[tool.name] = tool
        cursor = _listing_cursor(listing)
        if cursor is None:
            break
        if (
            not isinstance(cursor, str)
            or not cursor
            or len(cursor) > MAX_CURSOR_LENGTH
            or cursor in seen
        ):
            raise L43TransportError("L43_DISCOVERY_CURSOR_INVALID")
        seen.add(cursor)
    else:
        raise L43TransportError("L43_DISCOVERY_BOUND_EXCEEDED")
    if set(found) != set(L43_TOOL_NAMES):
        raise L43TransportError("L43_CAPABILITY_MISSING")
    _validate_static_l41r5_inputs(found)
    return found


def _validate_static_l41r5_inputs(
    tools: Mapping[str, _AdvertisedTool],
) -> None:
    """Apply L41R5's checked-in field facts, not its lexical action labels."""
    for name in L43_TOOL_NAMES:
        tool = tools[name]
        if tool.additional_properties is not False:
            raise L43TransportError("L43_ADDITIONAL_PROPERTIES_UNSUPPORTED")
        for field_name in ("quantity", "dollar_amount"):
            schema = tool.properties.get(field_name)
            if schema is None:
                raise L43TransportError("L43_ORDER_FIELD_SCHEMA_UNSUPPORTED")
            actual_semantics = L41R5FieldSemantics(
                present=True,
                direct_type=schema.get("type")
                if isinstance(schema.get("type"), str)
                else None,
                logical_non_null_type=schema.get("type")
                if isinstance(schema.get("type"), str)
                else None,
                required=field_name in tool.required,
                nullable=schema.get("nullable") is True
                or any(key in schema for key in ("anyOf", "oneOf", "allOf", "$ref")),
            )
            if (
                actual_semantics != _L41R5_EXPECTED_ORDER_FIELD
                or not {"type", "description"} <= set(schema)
                or set(schema) - {"type", "description"}
                or type(schema.get("description")) is not str
            ):
                raise L43TransportError("L43_ORDER_FIELD_SCHEMA_UNSUPPORTED")
        common_properties = {
            "account_number",
            "symbol",
            "side",
            "type",
            "market_hours",
            "time_in_force",
            "quantity",
            "dollar_amount",
        }
        if not common_properties <= set(tool.properties):
            raise L43TransportError("L43_ORDER_SCHEMA_MISSING")
        if not tool.required <= set(tool.properties):
            raise L43TransportError("L43_ORDER_SCHEMA_REQUIREDNESS_INVALID")
        if not {"account_number", "symbol", "side", "type"} <= tool.required:
            raise L43TransportError("L43_ORDER_SCHEMA_REQUIREDNESS_INVALID")
        if _L41R5_FRACTIONAL_PRECISION != (6,):
            raise L43TransportError("L43_L41R5_PRECISION_UNSUPPORTED")
    place = tools["place_equity_order"]
    if "ref_id" in place.properties and (
        place.properties["ref_id"].get("type") != "string" or "ref_id" in place.required
    ):
        raise L43TransportError("L43_REF_ID_SCHEMA_UNSUPPORTED")


def _validate_request_schema(
    schema: _AdvertisedTool,
    arguments: Mapping[str, object],
    *,
    for_place: bool,
) -> None:
    if not set(arguments) <= set(schema.properties):
        raise L43TransportError("L43_REQUEST_PROPERTY_UNSUPPORTED")
    if not schema.required <= set(arguments):
        raise L43TransportError("L43_REQUEST_REQUIRED_PROPERTY_MISSING")
    if for_place:
        if "dollar_amount" in schema.required and "dollar_amount" not in arguments:
            raise L43TransportError("L43_DOLLAR_ENTRY_SCHEMA_REQUIRED")
        if "quantity" in schema.required and "quantity" not in arguments:
            raise L43TransportError("L43_QUANTITY_SELL_SCHEMA_REQUIRED")
    elif "dollar_amount" in schema.required:
        raise L43TransportError("L43_REVIEW_SCHEMA_REQUIRES_DOLLARS")


def _advertised_tool(entry: object) -> _AdvertisedTool:
    if isinstance(entry, Mapping):
        name = entry.get("name")
        input_schema = entry.get("input_schema", entry.get("inputSchema"))
    else:
        name = getattr(entry, "name", None)
        input_schema = getattr(entry, "input_schema", None)
        if input_schema is None:
            input_schema = getattr(entry, "inputSchema", None)
    if not isinstance(name, str) or not name or not isinstance(input_schema, Mapping):
        raise L43TransportError("L43_TOOL_SCHEMA_INVALID")
    properties = input_schema.get("properties")
    required = input_schema.get("required", [])
    if (
        not isinstance(properties, Mapping)
        or not isinstance(required, list)
        or any(not isinstance(key, str) for key in properties)
        or any(not isinstance(key, str) for key in required)
    ):
        raise L43TransportError("L43_TOOL_SCHEMA_INVALID")
    parsed_properties: dict[str, Mapping[str, object]] = {}
    for key, value in properties.items():
        if not isinstance(value, Mapping):
            raise L43TransportError("L43_TOOL_SCHEMA_INVALID")
        parsed_properties[key] = value
    return _AdvertisedTool(
        name=name,
        properties=parsed_properties,
        required=frozenset(required),
        additional_properties=input_schema.get("additionalProperties"),
    )


def _listing_tools(listing: object) -> Sequence[object]:
    entries = (
        listing.get("tools")
        if isinstance(listing, Mapping)
        else getattr(listing, "tools", None)
    )
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        raise L43TransportError("L43_TOOL_LIST_INVALID")
    return entries


def _listing_cursor(listing: object) -> object:
    return (
        listing.get("next_cursor")
        if isinstance(listing, Mapping)
        else getattr(listing, "next_cursor", None)
    )


def _structured_payload(result: object) -> Mapping[str, object] | None:
    if isinstance(result, Mapping):
        is_error = result.get("is_error")
        payload = result.get("structured_content")
    else:
        is_error = getattr(result, "is_error", None)
        payload = getattr(result, "structured_content", None)
    if is_error is not False or not isinstance(payload, Mapping):
        return None
    if not _bounded_json(payload):
        return None
    return payload


def _normalize_review_payload(
    payload: Mapping[str, object],
    *,
    proposal: ExactOwnedSellProposal,
    arguments: SellOrderArguments,
    request: Mapping[str, object],
) -> L43ReviewNormalization:
    """Normalize only echoed current fields; unknown status remains blocked."""
    root = payload
    data = root.get("data")
    if not isinstance(data, Mapping) or set(root) != {"data"}:
        return _blocked_review(
            ManualCloseTrigger.SELL_REVIEW_MALFORMED,
            "L43_REVIEW_WIRE_SHAPE_UNKNOWN",
        )
    expected_data = {
        "market_data_disclosure",
        "order_checks",
        "quantity",
        "quote_data",
        "side",
        "symbol",
        "type",
    }
    if not {"order_checks", "quantity", "quote_data", "side", "symbol", "type"} <= set(
        data
    ):
        return _blocked_review(
            ManualCloseTrigger.SELL_REVIEW_MALFORMED,
            "L43_REVIEW_WIRE_SHAPE_UNKNOWN",
        )
    unknown = set(data) - expected_data
    quote = data.get("quote_data")
    if not isinstance(quote, Mapping):
        return _blocked_review(
            ManualCloseTrigger.SELL_REVIEW_MALFORMED,
            "L43_REVIEW_WIRE_SHAPE_UNKNOWN",
        )
    quote_fields = {
        "adjusted_previous_close",
        "ask_price",
        "bid_price",
        "has_traded",
        "last_non_reg_trade_price",
        "last_trade_price",
        "previous_close",
        "previous_close_date",
        "state",
        "symbol",
        "venue_ask_time",
        "venue_bid_time",
        "venue_last_non_reg_trade_time",
        "venue_last_trade_time",
    }
    unknown.update(set(quote) - quote_fields)
    if set(quote) != quote_fields:
        return _blocked_review(
            ManualCloseTrigger.SELL_REVIEW_MALFORMED,
            "L43_REVIEW_WIRE_SHAPE_UNKNOWN",
        )
    if unknown:
        return _blocked_review(
            ManualCloseTrigger.SELL_REVIEW_MALFORMED,
            "L43_REVIEW_FIELDS_UNKNOWN",
        )
    disclosure = data.get("market_data_disclosure")
    if disclosure is not None and type(disclosure) is not str:
        return _blocked_review(
            ManualCloseTrigger.SELL_REVIEW_MALFORMED,
            "L43_REVIEW_WIRE_SHAPE_UNKNOWN",
        )
    checks = data.get("order_checks")
    if not isinstance(checks, Mapping):
        return _blocked_review(
            ManualCloseTrigger.SELL_REVIEW_MALFORMED,
            "L43_REVIEW_WIRE_SHAPE_UNKNOWN",
        )
    if (
        data.get("side") != "sell"
        or data.get("symbol") != "SPY"
        or data.get("type") != "market"
        or not _decimal_equal(data.get("quantity"), arguments.quantity)
        or request.get("account_number") is None
    ):
        return _blocked_review(
            ManualCloseTrigger.SELL_REVIEW_MALFORMED,
            "L43_REVIEW_ECHO_MISMATCH",
        )
    if checks:
        return _blocked_review(
            ManualCloseTrigger.SELL_REVIEW_WARNING,
            "L43_REVIEW_CHECKS_PRESENT",
        )
    proposal_sha256 = evaluate_exact_owned_sell_proposal(proposal).proposal_sha256
    if proposal_sha256 is None:
        return _blocked_review(
            ManualCloseTrigger.SELL_REVIEW_MALFORMED,
            "L43_PROPOSAL_DIGEST_UNAVAILABLE",
        )
    evidence_sha256 = _review_evidence_digest(payload, request, proposal_sha256)
    review_id = f"l43-{evidence_sha256[:64]}"
    normalized = NormalizedSellReview(
        contract_id=EXACT_SELL_REVIEW_CONTRACT_ID,
        review_id=review_id,
        evidence_sha256=evidence_sha256,
        proposal_sha256=proposal_sha256,
        identity=proposal.position.identity,
        reviewed_arguments=arguments,
        outcome=NormalizedReviewOutcome.UNKNOWN,
        semantics=NormalizedReviewSemantics.UNKNOWN,
        warnings=(),
        unknown_fields=(),
        rejection_code=None,
        provider_order_id=None,
    )
    return L43ReviewNormalization(
        L43ReviewStatus.NORMALIZED_UNKNOWN,
        normalized,
        ManualCloseTrigger.SELL_REVIEW_UNKNOWN,
        "L43_REVIEW_SEMANTICS_UNPROVEN",
    )


def _blocked_review(
    trigger: ManualCloseTrigger, reason_code: str
) -> L43ReviewNormalization:
    return L43ReviewNormalization(
        L43ReviewStatus.BLOCKED,
        None,
        trigger,
        reason_code,
    )


def _sell_order_arguments(
    account_number: str,
    arguments: SellOrderArguments,
) -> dict[str, object]:
    if type(arguments) is not SellOrderArguments:
        raise TypeError("exact SellOrderArguments required")
    context = arguments.context
    if (
        arguments.side is not SellSide.SELL
        or arguments.symbol != "SPY"
        or arguments.order_type is not SellOrderType.MARKET
        or arguments.session is not SellSession.REGULAR_HOURS
        or arguments.time_in_force is not SellTimeInForce.DAY
        or arguments.dollar_amount is not None
        or not _finite_decimal(arguments.quantity)
        or arguments.quantity <= _ZERO
        or _effective_decimal_places(arguments.quantity) > 6
        or arguments.quantity != context.exact_owned_remainder
        or arguments.quantity != context.broker_position_quantity
        or context.broker_sellable_quantity < arguments.quantity
        or context.identity.account_fingerprint == ""
    ):
        raise ValueError("exact full-owned sell arguments are unsupported")
    return {
        "account_number": account_number,
        "market_hours": "regular_hours",
        "quantity": _decimal_text(arguments.quantity),
        "side": "sell",
        "symbol": "SPY",
        "time_in_force": "gfd",
        "type": "market",
    }


def _validate_entry_dollars(value: Decimal) -> None:
    if (
        not _finite_decimal(value)
        or value <= _ZERO
        or value > _ENTRY_LIMIT
        or _effective_decimal_places(value) > 2
    ):
        raise ValueError("entry dollars must be positive cents no greater than $10")


def _validate_optional_ref_id(value: str | None) -> None:
    if value is None:
        return
    if not isinstance(value, str) or len(value) > 128 or not value.isascii():
        raise ValueError("ref_id must be a bounded ASCII value")
    try:
        import uuid

        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        raise ValueError("ref_id must be a UUID") from None
    if str(parsed) != value:
        raise ValueError("ref_id must be canonical lowercase UUID text")


def _require_account_number(value: str) -> None:
    if type(value) is not str or _ACCOUNT_NUMBER.fullmatch(value) is None:
        raise ValueError("account number must be bounded ASCII text")


def _provider_order_id_from_envelope(
    payload: Mapping[str, object],
) -> str | None:
    data = payload.get("data")
    if not isinstance(data, Mapping):
        return None
    order = data.get("order")
    if not isinstance(order, Mapping):
        return None
    try:
        return provider_order_id(order.get("id"))
    except (TypeError, ValueError):
        return None


def _decimal_equal(value: object, expected: Decimal) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = Decimal(value)
    except Exception:
        return False
    return parsed.is_finite() and parsed == expected


def _finite_decimal(value: object) -> bool:
    return type(value) is Decimal and value.is_finite()


def _effective_decimal_places(value: Decimal) -> int:
    parts = value.as_tuple()
    exponent = parts.exponent
    if exponent >= 0:
        return 0
    trailing = 0
    for digit in reversed(parts.digits):
        if digit != 0:
            break
        trailing += 1
    return max(0, -exponent - trailing)


def _decimal_text(value: Decimal) -> str:
    if not _finite_decimal(value):
        raise ValueError("decimal must be finite")
    if value == 0:
        return "0"
    result = format(value, "f")
    if "." in result:
        result = result.rstrip("0").rstrip(".")
    return result


def _bounded_json(value: object, *, depth: int = 0) -> bool:
    remaining_bytes = [MAX_RESPONSE_BYTES]
    remaining_nodes = [10_000]

    def visit(item: object, current_depth: int) -> bool:
        remaining_nodes[0] -= 1
        if remaining_nodes[0] < 0 or current_depth > MAX_RESPONSE_DEPTH:
            return False
        if item is None or type(item) is bool:
            return True
        if type(item) is int:
            return item.bit_length() <= 4096
        if type(item) is str:
            try:
                remaining_bytes[0] -= len(item.encode("utf-8"))
            except UnicodeError:
                return False
            return remaining_bytes[0] >= 0
        if type(item) is float:
            return False
        if isinstance(item, Mapping):
            if len(item) > 512:
                return False
            for key, child in item.items():
                if type(key) is not str or not visit(key, current_depth + 1):
                    return False
                if not visit(child, current_depth + 1):
                    return False
            return True
        if isinstance(item, (list, tuple)):
            return len(item) <= 2048 and all(
                visit(child, current_depth + 1) for child in item
            )
        return False

    return visit(value, depth)


def _review_evidence_digest(
    payload: Mapping[str, object],
    request: Mapping[str, object],
    proposal_sha256: str,
) -> str:
    """Hash bounded response material without retaining or returning payload text."""
    safe_request = tuple(
        (key, value)
        for key, value in sorted(request.items())
        if key != "account_number"
    )
    document = json.dumps(
        (
            "ARCH147_L43_SELL_REVIEW_RAW_UNKNOWN_V1",
            proposal_sha256,
            safe_request,
            _plain_json(payload),
        ),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    if len(document) > MAX_RESPONSE_BYTES:
        raise L43TransportError("L43_REVIEW_RESPONSE_BOUND_EXCEEDED")
    return hashlib.sha256(document).hexdigest()


def _plain_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _plain_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_json(item) for item in value]
    return value


__all__ = [
    "L43PlacementReceipt",
    "L43ReviewNormalization",
    "L43ReviewStatus",
    "L43RobinhoodTransport",
    "L43TransportError",
]
