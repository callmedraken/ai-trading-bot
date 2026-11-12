"""Fake-only tests for the narrow L43 request transport."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace

import pytest

from trading_bot.live_prototype.contracts import EffectDisposition, Lifecycle
from trading_bot.live_prototype.durable_state import IntentKind
from trading_bot.live_prototype.live_contract import OwnershipSnapshot
from trading_bot.live_prototype.live_controller import PreparedInvocation
from trading_bot.live_prototype.readiness_contracts import ReadinessIdentity
from trading_bot.live_prototype.tiny_live_policy import (
    EXACT_SELL_REVIEW_CONTRACT_ID,
    EntryTerminalOutcome,
    ExactOwnedSellProposal,
    ManualCloseTrigger,
    NormalizedReviewOutcome,
    NormalizedReviewSemantics,
    ReconciledOwnedPosition,
    SellOrderArguments,
    SellOrderContext,
    SellOrderType,
    SellSession,
    SellSide,
    SellTimeInForce,
    TerminalEntryEvidence,
    validate_normalized_sell_review,
)
from trading_bot.robinhood_mcp.l43_transport import (
    L43PlacementReceipt,
    L43ReviewStatus,
    L43RobinhoodTransport,
    L43TransportError,
)

_IDENTITY = ReadinessIdentity(
    source_head="a" * 40,
    source_tree="b" * 40,
    config_digest="c" * 64,
    account_fingerprint="d" * 64,
    target_session="2026-11-10",
)
_BINDING = "e" * 64
_OWNED = Decimal("0.123456")
_AUTHORITY = "f" * 64


def _schemas(*, missing: tuple[str, str] | None = None, quantity_union=False):
    result = []
    for name in ("review_equity_order", "place_equity_order"):
        properties: dict[str, object] = {
            key: {"type": "string"}
            for key in (
                "account_number",
                "symbol",
                "side",
                "type",
                "market_hours",
                "time_in_force",
                "quantity",
                "dollar_amount",
            )
        }
        properties["quantity"] = {
            "description": "synthetic schema description",
            "type": "string",
        }
        properties["dollar_amount"] = {
            "description": "synthetic schema description",
            "type": "string",
        }
        if quantity_union:
            properties["quantity"] = {"anyOf": [{"type": "string"}, {"type": "null"}]}
        if name == "place_equity_order":
            properties["ref_id"] = {"type": "string"}
        if missing is not None and missing[0] == name:
            properties.pop(missing[1], None)
        result.append(
            SimpleNamespace(
                name=name,
                input_schema={
                    "properties": properties,
                    "required": ["account_number", "symbol", "side", "type"],
                    "additionalProperties": False,
                },
            )
        )
    return result


class _FakeSession:
    def __init__(
        self, schemas, *, result=None, results=None, pages=None, call_gate=None
    ):
        self.schemas = schemas
        self.result = result or SimpleNamespace(
            is_error=False,
            structured_content={"data": {"order": {"id": "provider-order-1"}}},
        )
        self.results = results
        self.pages = pages
        self.call_gate = call_gate
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.list_calls: list[str | None] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def list_tools(self, *, cursor=None):
        self.list_calls.append(cursor)
        if self.pages is None:
            return SimpleNamespace(tools=self.schemas, next_cursor=None)
        return self.pages[cursor]

    async def call_tool(self, name, arguments):
        self.calls.append((name, dict(arguments)))
        if self.call_gate is not None:
            await self.call_gate.wait()
        if self.results is not None:
            return self.results[len(self.calls) - 1]
        return self.result


def _arguments(*, quantity: Decimal = _OWNED, dollar_amount=None):
    return SellOrderArguments(
        side=SellSide.SELL,
        symbol="SPY",
        order_type=SellOrderType.MARKET,
        session=SellSession.REGULAR_HOURS,
        time_in_force=SellTimeInForce.DAY,
        quantity=quantity,
        context=SellOrderContext(
            identity=_IDENTITY,
            binding_digest=_BINDING,
            lifecycle_id="l43-life-1",
            entry_local_intent_id="entry-intent-1",
            entry_provider_order_id="entry-order-1",
            exact_owned_remainder=_OWNED,
            broker_position_quantity=_OWNED,
            broker_sellable_quantity=_OWNED,
            terminal_entry_outcome=EntryTerminalOutcome.FILLED,
            reserved_usd_cents=1000,
            confirmed_entry_filled_quantity=_OWNED,
            confirmed_entry_filled_notional=Decimal("10.01"),
        ),
        dollar_amount=dollar_amount,
    )


def _proposal(arguments: SellOrderArguments | None = None):
    chosen = _arguments() if arguments is None else arguments
    snapshot = OwnershipSnapshot(
        account_fingerprint=_IDENTITY.account_fingerprint,
        symbol="SPY",
        strategy="BASE_MA35_50_V1",
        source_head=_IDENTITY.source_head,
        source_tree=_IDENTITY.source_tree,
        config_digest=_IDENTITY.config_digest,
        binding_digest=_BINDING,
        lifecycle_id="l43-life-1",
        target_session=_IDENTITY.target_session,
        lifecycle=Lifecycle.RUNNING,
        effect_disposition=EffectDisposition.CONFIRMED,
        baseline_quantity=Decimal("0"),
        cumulative_bought=_OWNED,
        cumulative_sold=Decimal("0"),
        cumulative_entry_filled_dollars=Decimal("10.01"),
        entry_reserved_dollars=Decimal("10.00"),
        working_remainder=Decimal("0"),
        entries_used=1,
        exits_used=0,
        entry_local_intent_id="entry-intent-1",
        entry_provider_order_id="entry-order-1",
    )

    position = ReconciledOwnedPosition(
        identity=_IDENTITY,
        ownership_snapshot=snapshot,
        broker_position_quantity=_OWNED,
        broker_sellable_quantity=_OWNED,
        working_order_count=0,
        unresolved_order_count=0,
        evidence_sha256="f" * 64,
    )
    terminal_entry = TerminalEntryEvidence(
        local_intent_id="entry-intent-1",
        provider_order_id="entry-order-1",
        outcome=EntryTerminalOutcome.FILLED,
        requested_usd_cents=1000,
        reserved_usd_cents=1000,
        confirmed_filled_quantity=_OWNED,
        confirmed_filled_notional=Decimal("10.01"),
    )
    return ExactOwnedSellProposal(
        position=position,
        terminal_entry=terminal_entry,
        review_arguments=chosen,
        placement_arguments=chosen,
    )


def _permit(
    kind: IntentKind,
    *,
    dollars: Decimal | None = None,
    quantity: Decimal | None = None,
    authority_sha256: str | None = None,
) -> PreparedInvocation:
    return PreparedInvocation(
        intent_id="11111111-1111-4111-8111-111111111111",
        kind=kind,
        requested_dollars=dollars,
        requested_quantity=quantity,
        authority_sha256=authority_sha256,
    )


def _review_payload(quantity="0.123456"):
    quote = {
        "adjusted_previous_close": "495.00",
        "ask_price": "500.10",
        "bid_price": "500.00",
        "has_traded": True,
        "last_non_reg_trade_price": None,
        "last_trade_price": "500.05",
        "previous_close": "495.00",
        "previous_close_date": "2026-10-01",
        "state": "active",
        "symbol": "SPY",
        "venue_ask_time": "2026-10-02T15:00:01+00:00",
        "venue_bid_time": "2026-10-02T15:00:01+00:00",
        "venue_last_non_reg_trade_time": None,
        "venue_last_trade_time": "2026-10-02T15:00:00+00:00",
    }
    return {
        "data": {
            "market_data_disclosure": "known disclosure",
            "order_checks": {},
            "quantity": quantity,
            "quote_data": quote,
            "side": "sell",
            "symbol": "SPY",
            "type": "market",
        }
    }


def test_l43_transport_has_only_closed_review_and_place_tool_names():
    session = _FakeSession(_schemas())
    transport = L43RobinhoodTransport.for_test(lambda: session)

    async def scenario():
        async with transport.prepare_entry_order(
            account_number="account-one", requested_dollars=Decimal("0.50")
        ) as prepared:
            assert session.list_calls == [None]
            assert session.calls == []
            prepared.resolve_callable()
            assert session.calls == []

    asyncio.run(scenario())
    assert not hasattr(transport, "call_tool")
    assert transport.call_counts == (
        ("review_equity_order", 0),
        ("place_equity_order", 0),
    )


def test_prepared_callable_is_one_shot_even_for_duplicate_or_concurrent_awaits():
    gate = asyncio.Event()
    session = _FakeSession(_schemas(), call_gate=gate)
    transport = L43RobinhoodTransport.for_test(lambda: session)

    async def scenario():
        async with transport.prepare_entry_order(
            account_number="account-one", requested_dollars=Decimal("1.00")
        ) as prepared:
            invoke = prepared.resolve_callable()
            permit = _permit(IntentKind.ENTRY, dollars=Decimal("1.00"))
            first = invoke(permit)
            task = asyncio.create_task(first)
            await asyncio.sleep(0)
            with pytest.raises(L43TransportError, match="L43_CALL_ALREADY_INVOKED"):
                invoke(permit)
            gate.set()
            assert await task == L43PlacementReceipt("provider-order-1")

    asyncio.run(scenario())
    assert len(session.calls) == 1
    assert dict(transport.call_counts)["place_equity_order"] == 1


def test_prepared_callable_is_invalidated_when_session_context_exits():
    session = _FakeSession(_schemas())
    transport = L43RobinhoodTransport.for_test(lambda: session)

    async def scenario():
        async with transport.prepare_entry_order(
            account_number="account-one", requested_dollars=Decimal("1.00")
        ) as prepared:
            invoke = prepared.resolve_callable()
            pending = invoke(_permit(IntentKind.ENTRY, dollars=Decimal("1.00")))
        with pytest.raises(L43TransportError, match="L43_PREPARED_CALL_CLOSED"):
            await pending
        with pytest.raises(L43TransportError, match="L43_PREPARED_CALL_CLOSED"):
            invoke(_permit(IntentKind.ENTRY, dollars=Decimal("1.00")))

    asyncio.run(scenario())
    assert session.calls == []
    assert dict(transport.call_counts)["place_equity_order"] == 0


def test_prepared_callable_does_not_relabel_caller_body_exception_as_discovery():
    session = _FakeSession(_schemas())
    transport = L43RobinhoodTransport.for_test(lambda: session)

    async def scenario():
        with pytest.raises(RuntimeError, match="caller-body-failure"):
            async with transport.prepare_entry_order(
                account_number="account-one", requested_dollars=Decimal("1.00")
            ):
                raise RuntimeError("caller-body-failure")

    asyncio.run(scenario())
    assert session.calls == []


def test_prepared_callable_requires_exact_durable_invocation_permit():
    session = _FakeSession(_schemas())
    transport = L43RobinhoodTransport.for_test(lambda: session)

    async def scenario():
        async with transport.prepare_entry_order(
            account_number="account-one", requested_dollars=Decimal("1.00")
        ) as prepared:
            invoke = prepared.resolve_callable()
            with pytest.raises(
                L43TransportError, match="L43_PREPARED_INVOCATION_MISMATCH"
            ):
                invoke(_permit(IntentKind.ENTRY, dollars=Decimal("0.99")))
            with pytest.raises(L43TransportError, match="L43_CALL_ALREADY_INVOKED"):
                invoke(_permit(IntentKind.ENTRY, dollars=Decimal("1.00")))

    asyncio.run(scenario())
    assert session.calls == []
    assert dict(transport.call_counts)["place_equity_order"] == 0


def test_entry_order_is_exact_cent_dollar_buy_and_invokes_same_discovered_session():
    session = _FakeSession(_schemas())
    transport = L43RobinhoodTransport.for_test(lambda: session)

    async def scenario():
        async with transport.prepare_entry_order(
            account_number="account-one",
            requested_dollars=Decimal("0.50"),
            ref_id="11111111-1111-4111-8111-111111111111",
        ) as prepared:
            invoke = prepared.resolve_callable()
            assert session.list_calls == [None]
            receipt = await invoke(_permit(IntentKind.ENTRY, dollars=Decimal("0.50")))
            assert receipt.provider_order_id == "provider-order-1"
            assert session.list_calls == [None]

    asyncio.run(scenario())
    assert session.calls == [
        (
            "place_equity_order",
            {
                "account_number": "account-one",
                "dollar_amount": "0.5",
                "market_hours": "regular_hours",
                "ref_id": "11111111-1111-4111-8111-111111111111",
                "side": "buy",
                "symbol": "SPY",
                "time_in_force": "gfd",
                "type": "market",
            },
        )
    ]
    assert dict(transport.call_counts)["place_equity_order"] == 1


@pytest.mark.parametrize(
    "value",
    [Decimal("0"), Decimal("10.01"), Decimal("0.001"), Decimal("NaN")],
)
def test_entry_order_rejects_invalid_dollar_amount_before_discovery(value):
    session = _FakeSession(_schemas())
    transport = L43RobinhoodTransport.for_test(lambda: session)

    async def scenario():
        with pytest.raises(ValueError):
            async with transport.prepare_entry_order(
                account_number="account-one", requested_dollars=value
            ):
                raise AssertionError("invalid request must not open a session")

    asyncio.run(scenario())
    assert session.list_calls == []
    assert session.calls == []


def test_sell_review_and_place_arguments_match_exact_full_owned_quantity():
    args = _arguments()
    proposal = _proposal(args)
    session = _FakeSession(
        _schemas(),
        results=[
            SimpleNamespace(is_error=False, structured_content=_review_payload()),
            SimpleNamespace(
                is_error=False,
                structured_content={"data": {"order": {"id": "provider-order-1"}}},
            ),
        ],
    )
    transport = L43RobinhoodTransport.for_test(lambda: session)

    async def scenario():
        review = await transport.review_sell_order(
            account_number="account-one", proposal=proposal
        )
        assert review.status is L43ReviewStatus.NORMALIZED_UNKNOWN
        assert review.manual_close_trigger is ManualCloseTrigger.SELL_REVIEW_UNKNOWN
        assert review.review is not None
        assert review.review.contract_id == EXACT_SELL_REVIEW_CONTRACT_ID
        assert review.review.outcome is NormalizedReviewOutcome.UNKNOWN
        assert review.review.semantics is NormalizedReviewSemantics.UNKNOWN
        assert validate_normalized_sell_review(
            proposal, review.review
        ).manual_close_trigger is (ManualCloseTrigger.SELL_REVIEW_UNKNOWN)
        async with transport.prepare_sell_order(
            account_number="account-one", arguments=args
        ) as prepared:
            invoke = prepared.resolve_callable(authority_sha256=_AUTHORITY)
            await invoke(
                _permit(
                    IntentKind.EXIT,
                    quantity=args.quantity,
                    authority_sha256=_AUTHORITY,
                )
            )

    asyncio.run(scenario())
    review_args = session.calls[0][1]
    place_args = session.calls[1][1]
    assert session.calls[0][0] == "review_equity_order"
    assert session.calls[1][0] == "place_equity_order"
    assert review_args == place_args
    assert review_args == {
        "account_number": "account-one",
        "market_hours": "regular_hours",
        "quantity": "0.123456",
        "side": "sell",
        "symbol": "SPY",
        "time_in_force": "gfd",
        "type": "market",
    }


def test_sell_review_unknown_fields_and_order_checks_fail_closed():
    payload = _review_payload()
    payload["data"]["unexpected"] = "untrusted"
    session = _FakeSession(
        _schemas(), result=SimpleNamespace(is_error=False, structured_content=payload)
    )
    transport = L43RobinhoodTransport.for_test(lambda: session)

    async def scenario():
        result = await transport.review_sell_order(
            account_number="account-one", proposal=_proposal()
        )
        assert result.status is L43ReviewStatus.BLOCKED
        assert result.review is None
        assert result.manual_close_trigger is ManualCloseTrigger.SELL_REVIEW_MALFORMED

    asyncio.run(scenario())

    payload["data"].pop("unexpected")
    payload["data"]["order_checks"] = {"unknown": "warning text"}
    warning_session = _FakeSession(
        _schemas(), result=SimpleNamespace(is_error=False, structured_content=payload)
    )
    warning_transport = L43RobinhoodTransport.for_test(lambda: warning_session)

    async def warning_case():
        result = await warning_transport.review_sell_order(
            account_number="account-one", proposal=_proposal()
        )
        assert result.status is L43ReviewStatus.BLOCKED
        assert result.manual_close_trigger is ManualCloseTrigger.SELL_REVIEW_WARNING

    asyncio.run(warning_case())


def test_sell_arguments_reject_dollar_substitution_manual_position_and_scale():
    invalid = (
        _arguments(dollar_amount=Decimal("1.00")),
        _arguments(quantity=Decimal("0.1234567")),
        _arguments(quantity=Decimal("0.123455")),
    )
    for args in invalid:

        async def scenario(arguments=args):
            session = _FakeSession(_schemas())
            transport = L43RobinhoodTransport.for_test(lambda: session)
            with pytest.raises(ValueError):
                async with transport.prepare_sell_order(
                    account_number="account-one", arguments=arguments
                ):
                    raise AssertionError("invalid sell must not open a session")
            assert session.list_calls == []
            assert session.calls == []

        asyncio.run(scenario())


@pytest.mark.parametrize(
    "schemas",
    [
        _schemas(missing=("place_equity_order", "quantity")),
        _schemas(quantity_union=True),
    ],
)
def test_unsupported_schema_blocks_before_any_order_invocation(schemas):
    session = _FakeSession(schemas)
    transport = L43RobinhoodTransport.for_test(lambda: session)

    async def scenario():
        with pytest.raises(L43TransportError):
            async with transport.prepare_entry_order(
                account_number="account-one", requested_dollars=Decimal("1.00")
            ):
                raise AssertionError("invalid schema must block")

    asyncio.run(scenario())
    assert session.calls == []
    assert dict(transport.call_counts)["place_equity_order"] == 0


@pytest.mark.parametrize(
    "response",
    [
        SimpleNamespace(
            is_error=True, structured_content={"data": {"order": {"id": "x"}}}
        ),
        SimpleNamespace(is_error=False, structured_content={"data": {"id": "x"}}),
        SimpleNamespace(
            is_error=False, structured_content={"data": {"order": {"id": "bad id"}}}
        ),
    ],
)
def test_placement_only_binds_supported_nested_order_id_envelope(response):
    session = _FakeSession(_schemas(), result=response)
    transport = L43RobinhoodTransport.for_test(lambda: session)

    async def scenario():
        async with transport.prepare_entry_order(
            account_number="account-one", requested_dollars=Decimal("1.00")
        ) as prepared:
            invoke = prepared.resolve_callable()
            with pytest.raises(L43TransportError, match="L43_PLACEMENT_RESULT_UNKNOWN"):
                await invoke(_permit(IntentKind.ENTRY, dollars=Decimal("1.00")))

    asyncio.run(scenario())
    assert len(session.calls) == 1
