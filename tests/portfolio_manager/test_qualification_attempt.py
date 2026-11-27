from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock

import pytest

from trading_bot.portfolio_manager import qualification_attempt as attempt
from trading_bot.robinhood_mcp.current_read_schema_qualification import (
    ArgumentSchemaFact,
    CurrentReadSchemaQualification,
    OrderScopeQualification,
    ReadToolSchemaFact,
    SchemaFieldStatus,
    SchemaQualificationStatus,
)
from trading_bot.robinhood_mcp.current_read_transport import READ_TOOLS

_ACCOUNT = "SYNTHETIC-ACCOUNT-DO-NOT-PUBLISH"
_ACCOUNT_FINGERPRINT = hashlib.sha256(_ACCOUNT.encode("utf-8")).hexdigest()
_ATTEMPT_ID = "0123456789abcdef0123456789abcdef"


def _source() -> attempt._SourceIdentity:
    return attempt._SourceIdentity(
        repository="F:\\AI\\worktrees\\ai-trading-bot-portfolio-manager-current",
        branch="feature/robinhood-portfolio-manager-current",
        head="a" * 40,
        tree="b" * 40,
        origin="https://github.com/callmedraken/ai-trading-bot.git",
        remote_feature_head="a" * 40,
        remote_develop_head="c" * 40,
        feature_authority="PASS",
        prospective_develop_authority="PASS",
    )


def _schema_result(*, status=SchemaQualificationStatus.COMPLETE):
    def fact(
        name: str,
        arguments: dict[str, tuple[str, ...]],
        *,
        account_paths: tuple[str, ...] = (),
        page_paths: tuple[str, ...] = (),
    ) -> ReadToolSchemaFact:
        args = tuple(
            ArgumentSchemaFact(argument, False, types)
            for argument, types in arguments.items()
        )
        account_status = (
            SchemaFieldStatus.PRESENT_OPTIONAL
            if "account_number" in arguments
            else SchemaFieldStatus.ABSENT
        )
        return ReadToolSchemaFact(
            name=name,
            advertised=True,
            input_schema_sha256="1" * 64,
            output_schema_sha256="2" * 64,
            input_arguments_complete=True,
            arguments=args,
            account_argument_status=account_status,
            pagination_arguments=tuple(name for name in arguments if name == "cursor"),
            order_filter_arguments=tuple(
                name for name in arguments if name in {"placed_agent", "created_at_gte"}
            ),
            result_schema_shape_complete=True,
            result_account_binding_paths=account_paths,
            result_pagination_paths=page_paths,
        )

    facts = (
        fact(
            "get_accounts",
            {},
            account_paths=("data.accounts[].account_number",),
        ),
        fact(
            "get_portfolio",
            {"account_number": ("string",)},
            account_paths=("data.account_number",),
        ),
        fact(
            "get_equity_positions",
            {"account_number": ("string",), "cursor": ("null", "string")},
            account_paths=("data.positions[].account_number",),
            page_paths=("data.next",),
        ),
        fact("get_equity_quotes", {"symbols": ("array",)}),
        fact(
            "get_equity_orders",
            {
                "account_number": ("string",),
                "cursor": ("null", "string"),
                "placed_agent": ("string",),
                "created_at_gte": ("string",),
            },
            account_paths=("data.orders[].account_number",),
            page_paths=("data.next",),
        ),
    )
    return CurrentReadSchemaQualification(
        status=status,
        read_tools=facts,
        tools_list_pages=1,
        pagination_complete=True,
        quarantined_tool_count=0,
        order_scope=OrderScopeQualification.SCHEMA_ONLY_UNPROVEN,
    )


def _quote(symbol: str) -> dict[str, object]:
    stamp = (
        (datetime.now(UTC) - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    )
    return {
        "data": {
            "results": [
                {
                    "quote": {
                        "symbol": symbol,
                        "state": "active",
                        "has_traded": True,
                        "adjusted_previous_close": "100",
                        "previous_close": "100",
                        "ask_price": "101",
                        "bid_price": "99",
                        "last_trade_price": "100",
                        "last_non_reg_trade_price": None,
                        "venue_ask_time": stamp,
                        "venue_bid_time": stamp,
                        "venue_last_trade_time": stamp,
                        "venue_last_non_reg_trade_time": None,
                    }
                }
            ]
        }
    }


class _FakeRead:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.account_rows = [{"account_number": _ACCOUNT, "agentic_allowed": True}]

    def get_accounts(self):
        self.calls.append("get_accounts")
        return {"data": {"accounts": self.account_rows}}

    def get_portfolio(self, arguments):
        self.calls.append("get_portfolio")
        assert arguments["account_number"] == _ACCOUNT
        return {
            "data": {
                "account_number": _ACCOUNT,
                "total_value": "10100",
                "cash": "10000",
                "equity_value": "100",
                "currency": "USD",
                "buying_power": {
                    "buying_power": "10000",
                    "unleveraged_buying_power": "10000",
                    "display_currency": "USD",
                },
            }
        }

    def get_equity_positions(self, arguments):
        self.calls.append("get_equity_positions")
        assert arguments["account_number"] == _ACCOUNT
        return {
            "data": {
                "account_number": _ACCOUNT,
                "positions": [
                    {
                        "account_number": _ACCOUNT,
                        "symbol": "SPY",
                        "quantity": "1.25",
                        "shares_available_for_sells": "1.0",
                        "average_buy_price": None,
                        "type": "long",
                        "asset_type": "stock",
                    }
                ],
                "next": None,
            }
        }

    def get_equity_quotes(self, arguments):
        self.calls.append("get_equity_quotes")
        return _quote(arguments["symbols"][0])

    def get_equity_orders(self, arguments):
        self.calls.append("get_equity_orders")
        assert arguments["account_number"] == _ACCOUNT
        assert arguments["placed_agent"] == "agentic"
        return {
            "data": {
                "account_number": _ACCOUNT,
                "orders": [],
                "next": None,
            }
        }


class _FakeTransport(_FakeRead):
    _provider_attempt_counts = (
        ("oauth_factory_attempts", 1),
        ("mcp_session_open_attempts", 1),
        ("tools_list_call_attempts", 1),
        ("tools_list_pages_received", 1),
    )


def _prepare(monkeypatch, tmp_path, *, schema=None, reader_factory=None):
    monkeypatch.setattr(
        attempt, "_resolve_attempt_root", lambda: tmp_path.resolve(strict=True)
    )
    monkeypatch.setattr(attempt, "_capture_source_identity", _source)
    events: list[str] = []

    async def qualify(oauth_factory, *, on_attempt=None):
        if on_attempt is not None:
            for event in (
                "oauth_factory",
                "mcp_session",
                "tools_list_call",
                "tools_list_page",
            ):
                on_attempt(event)
        events.append("schema")
        return schema or _schema_result()

    monkeypatch.setattr(attempt, "qualify_current_read_provider", qualify)
    if reader_factory is None:
        monkeypatch.setattr(attempt, "_make_read_transport", lambda _: _FakeTransport())
    else:
        monkeypatch.setattr(attempt, "_make_read_transport", reader_factory)
    return events


def _run_attempt(
    *,
    attempt_id=_ATTEMPT_ID,
    selected_account_fingerprint=_ACCOUNT_FINGERPRINT,
    oauth_factory,
    expected_source_head=None,
    expected_source_tree=None,
):
    source = _source()
    return attempt.run_pm2a_qualification_attempt(
        attempt_id=attempt_id,
        expected_source_head=expected_source_head or source.head,
        expected_source_tree=expected_source_tree or source.tree,
        selected_account_fingerprint=selected_account_fingerprint,
        oauth_factory=oauth_factory,
    )


def test_default_attempt_root_rejects_non_f_drive(monkeypatch) -> None:
    non_f_root = Path(r"C:\Windows")
    assert non_f_root.is_dir()
    monkeypatch.setattr(attempt, "_ATTEMPT_ROOT", non_f_root)

    with pytest.raises(ValueError, match="attempt root rejected"):
        attempt._resolve_attempt_root()


def test_schema_incomplete_reserves_before_provider_and_stops_before_reads(
    monkeypatch, tmp_path
) -> None:
    events = _prepare(
        monkeypatch,
        tmp_path,
        schema=_schema_result(status=SchemaQualificationStatus.INCOMPLETE),
        reader_factory=lambda _: (_ for _ in ()).throw(
            AssertionError("schema failure must stop before read construction")
        ),
    )

    async def qualify_after_reservation(factory, *, on_attempt):
        del factory, on_attempt
        record = tmp_path / f"arch152-pm2a-attempt-{_ATTEMPT_ID}" / "attempt.json"
        events.append("reserved" if record.exists() else "missing")
        return _schema_result(status=SchemaQualificationStatus.INCOMPLETE)

    monkeypatch.setattr(
        attempt, "qualify_current_read_provider", qualify_after_reservation
    )

    result = _run_attempt(
        oauth_factory=lambda: (_ for _ in ()).throw(
            AssertionError("fake qualification must not read credentials")
        ),
    )

    evidence = json.loads(result.evidence_file.read_text(encoding="ascii"))
    reservation = json.loads(
        (tmp_path / f"arch152-pm2a-attempt-{_ATTEMPT_ID}" / "attempt.json").read_text(
            encoding="ascii"
        )
    )
    assert result.status is attempt.QualificationAttemptStatus.SCHEMA_INCOMPLETE
    assert events == ["reserved"]
    assert evidence["read_tools_invoked"] == []
    assert set(evidence["read_tool_invocation_counts"].values()) == {0}
    assert evidence["provider_attempts"]["tools_list_call_attempts"] == 0
    assert evidence["order_scope"] == "SCHEMA_ONLY_UNPROVEN"
    assert reservation["expected_source_head"] == "a" * 40
    assert reservation["expected_source_tree"] == "b" * 40
    assert reservation["selected_account_fingerprint"] == _ACCOUNT_FINGERPRINT
    assert reservation["consumption"] == "CONSUMED_ON_RESERVATION"
    assert evidence["effect_attempts"] == {
        "review": 0,
        "placement": 0,
        "cancellation": 0,
        "transfer": 0,
        "other": 0,
    }
    assert _ACCOUNT not in result.evidence_file.read_text(encoding="ascii")


def test_complete_fake_observation_records_only_sanitized_facts(
    monkeypatch, tmp_path
) -> None:
    events = _prepare(monkeypatch, tmp_path)
    result = _run_attempt(
        oauth_factory=lambda: (_ for _ in ()).throw(
            AssertionError("fake attempt must not invoke credentials")
        ),
    )

    evidence = json.loads(result.evidence_file.read_text(encoding="ascii"))
    assert result.status is attempt.QualificationAttemptStatus.OBSERVED
    assert events == ["schema"]
    assert evidence["account_fingerprint"] == _ACCOUNT_FINGERPRINT
    assert evidence["observed_account_count"] == 1
    assert evidence["eligible_account_count"] == 1
    assert evidence["selected_account_bound"]
    assert evidence["read_tools_invoked"] == list(READ_TOOLS)
    assert evidence["read_tool_invocation_counts"] == dict.fromkeys(READ_TOOLS, 1)
    assert evidence["position_pages"] == {"attempts": 1, "received": 1, "rows": 1}
    assert evidence["order_pages"] == {"attempts": 1, "received": 1, "rows": 0}
    assert evidence["pagination_complete"]
    assert evidence["quotes_available_positions"] == 1
    assert evidence["quotes_fresh_positions"] == 1
    assert evidence["cash_available"]
    assert evidence["buying_power_available"]
    assert evidence["unleveraged_buying_power_available"]
    assert evidence["cash_reservation_semantics"] == "UNKNOWN"
    assert evidence["order_scope"] == "ROBINHOOD_AGENTIC_BOUNDED"
    assert evidence["effect_attempts"]["placement"] == 0
    raw = result.evidence_file.read_text(encoding="ascii")
    assert _ACCOUNT not in raw
    assert "10100" not in raw and "10000" not in raw
    assert "dispatch_authorized" not in raw


@pytest.mark.parametrize("surface_gap", ["placed_agent", "account_echo", "pagination"])
def test_schema_missing_static_account_or_order_filter_arguments_blocks_reads(
    monkeypatch, tmp_path, surface_gap: str
) -> None:
    schema = _schema_result()
    facts = list(schema.read_tools)
    orders = facts[-1]
    if surface_gap == "placed_agent":
        facts[-1] = replace(
            orders,
            arguments=tuple(
                item for item in orders.arguments if item.name != "placed_agent"
            ),
            order_filter_arguments=("created_at_gte",),
        )
    elif surface_gap == "account_echo":
        facts[-1] = replace(orders, result_account_binding_paths=())
    else:
        facts[-1] = replace(orders, result_pagination_paths=())
    schema = CurrentReadSchemaQualification(
        status=schema.status,
        read_tools=tuple(facts),
        tools_list_pages=schema.tools_list_pages,
        pagination_complete=schema.pagination_complete,
        quarantined_tool_count=0,
        order_scope=schema.order_scope,
    )
    _prepare(
        monkeypatch,
        tmp_path,
        schema=schema,
        reader_factory=lambda _: (_ for _ in ()).throw(
            AssertionError("schema surface mismatch must stop before reads")
        ),
    )

    result = _run_attempt(
        oauth_factory=lambda: None,
    )
    evidence = json.loads(result.evidence_file.read_text(encoding="ascii"))

    assert result.status is attempt.QualificationAttemptStatus.SCHEMA_INCOMPLETE
    assert evidence["reason"] == "CURRENT_READ_SCHEMA_INSUFFICIENT"
    assert evidence["read_tools_invoked"] == []


@pytest.mark.parametrize(
    ("tool_name", "argument_name", "argument_types"),
    [
        ("get_accounts", "synthetic_required_argument", ("string",)),
        ("get_portfolio", "synthetic_required_argument", ("boolean",)),
        ("get_equity_positions", "cursor", ("null", "string")),
        ("get_equity_quotes", "synthetic_required_argument", ("string",)),
        ("get_equity_orders", "cursor", ("null", "string")),
    ],
)
def test_required_argument_missing_from_static_first_call_blocks_all_reads(
    monkeypatch,
    tmp_path,
    tool_name: str,
    argument_name: str,
    argument_types: tuple[str, ...],
) -> None:
    schema = _schema_result()
    facts = list(schema.read_tools)
    index = READ_TOOLS.index(tool_name)
    tool = facts[index]
    arguments = list(tool.arguments)
    existing = next(
        (
            position
            for position, item in enumerate(arguments)
            if item.name == argument_name
        ),
        None,
    )
    required_fact = ArgumentSchemaFact(argument_name, True, argument_types)
    if existing is None:
        arguments.append(required_fact)
    else:
        arguments[existing] = required_fact
    facts[index] = replace(tool, arguments=tuple(arguments))
    schema = replace(schema, read_tools=tuple(facts))

    reader_constructions: list[bool] = []

    def fail_if_transport_constructed(_oauth_factory):
        reader_constructions.append(True)
        raise AssertionError("incompatible first-call schema must stop before reads")

    events = _prepare(
        monkeypatch,
        tmp_path,
        schema=schema,
        reader_factory=fail_if_transport_constructed,
    )

    result = _run_attempt(oauth_factory=lambda: None)

    evidence = json.loads(result.evidence_file.read_text(encoding="ascii"))
    assert result.status is attempt.QualificationAttemptStatus.SCHEMA_INCOMPLETE
    assert evidence["reason"] == "CURRENT_READ_SCHEMA_INSUFFICIENT"
    assert evidence["read_tools_invoked"] == []
    assert set(evidence["read_tool_invocation_counts"].values()) == {0}
    assert reader_constructions == []
    assert events == ["schema"]


def test_required_arguments_supplied_by_static_first_calls_are_supported() -> None:
    schema = _schema_result()
    facts = list(schema.read_tools)
    required_by_tool = {
        "get_accounts": (),
        "get_portfolio": ("account_number",),
        "get_equity_positions": ("account_number",),
        "get_equity_quotes": ("symbols",),
        "get_equity_orders": (
            "account_number",
            "placed_agent",
            "created_at_gte",
        ),
    }
    for index, tool in enumerate(facts):
        required = set(required_by_tool[tool.name])
        facts[index] = replace(
            tool,
            arguments=tuple(
                replace(argument, required=argument.name in required)
                for argument in tool.arguments
            ),
        )

    assert attempt._schema_supports_current_read_surface(
        replace(schema, read_tools=tuple(facts))
    )


def test_optional_string_only_cursors_support_static_page_calls() -> None:
    schema = _schema_result()
    facts = list(schema.read_tools)
    for index, tool in enumerate(facts):
        if tool.name not in {"get_equity_positions", "get_equity_orders"}:
            continue
        facts[index] = replace(
            tool,
            arguments=tuple(
                replace(argument, types=("string",), required=False)
                if argument.name == "cursor"
                else argument
                for argument in tool.arguments
            ),
        )

    assert attempt._schema_supports_current_read_surface(
        replace(schema, read_tools=tuple(facts))
    )


def test_reviewed_source_head_and_tree_are_required_before_reservation(
    monkeypatch, tmp_path
) -> None:
    events = _prepare(
        monkeypatch,
        tmp_path,
        schema=_schema_result(status=SchemaQualificationStatus.INCOMPLETE),
    )

    result = _run_attempt(
        expected_source_head="d" * 40,
        oauth_factory=lambda: (_ for _ in ()).throw(
            AssertionError("source mismatch must block before credentials")
        ),
    )

    assert result.status is attempt.QualificationAttemptStatus.SOURCE_AUTHORITY_BLOCKED
    assert result.reason == "REVIEWED_SOURCE_MISMATCH"
    assert not (tmp_path / f"arch152-pm2a-attempt-{_ATTEMPT_ID}").exists()
    assert not events


def test_explicit_account_fingerprint_does_not_override_multiple_account_block(
    monkeypatch, tmp_path
) -> None:
    reader = _FakeTransport()
    second_account = "SECOND-SYNTHETIC-ACCOUNT-DO-NOT-PUBLISH"
    reader.account_rows.append(
        {"account_number": second_account, "agentic_allowed": True}
    )
    _prepare(monkeypatch, tmp_path, reader_factory=lambda _: reader)

    result = _run_attempt(oauth_factory=lambda: None)

    evidence = json.loads(result.evidence_file.read_text(encoding="ascii"))
    assert result.status is attempt.QualificationAttemptStatus.READ_INCOMPLETE
    assert result.reason == "MULTIPLE_ELIGIBLE_ACCOUNTS"
    assert evidence["account_fingerprint"] == _ACCOUNT_FINGERPRINT
    assert evidence["observed_account_count"] == 2
    assert evidence["eligible_account_count"] == 2
    assert evidence["selected_account_bound"] is False
    assert evidence["read_tools_invoked"] == ["get_accounts"]
    assert evidence["read_tool_invocation_counts"]["get_accounts"] == 1
    assert evidence["read_tool_invocation_counts"]["get_portfolio"] == 0
    assert evidence["position_pages"]["attempts"] == 0
    assert evidence["order_pages"]["attempts"] == 0
    raw = result.evidence_file.read_text(encoding="ascii")
    assert _ACCOUNT not in raw and second_account not in raw
    assert reader.calls == ["get_accounts"]


def test_source_change_after_schema_preflight_blocks_before_read_tools(
    monkeypatch, tmp_path
) -> None:
    _prepare(
        monkeypatch,
        tmp_path,
        reader_factory=lambda _: (_ for _ in ()).throw(
            AssertionError("source change must block read construction")
        ),
    )
    source = _source()
    changed = replace(source, head="d" * 40, tree="e" * 40)
    identities = iter((source, source, changed, changed))
    monkeypatch.setattr(attempt, "_capture_source_identity", lambda: next(identities))

    result = _run_attempt(oauth_factory=lambda: None)
    evidence = json.loads(result.evidence_file.read_text(encoding="ascii"))

    assert (
        result.status
        is attempt.QualificationAttemptStatus.SOURCE_CHANGED_DURING_ATTEMPT
    )
    assert evidence["read_tools_invoked"] == []
    assert evidence["source_stable_after_attempt"] is False


def test_attempt_id_collision_and_crash_reserved_slot_are_never_reused(
    monkeypatch, tmp_path
) -> None:
    events = _prepare(
        monkeypatch,
        tmp_path,
        schema=_schema_result(status=SchemaQualificationStatus.INCOMPLETE),
    )
    first = _run_attempt(
        oauth_factory=lambda: None,
    )
    calls_after_first = len(events)
    second = _run_attempt(
        attempt_id=_ATTEMPT_ID,
        oauth_factory=lambda: (_ for _ in ()).throw(
            AssertionError("consumed attempt must not retry")
        ),
    )

    assert first.status is attempt.QualificationAttemptStatus.SCHEMA_INCOMPLETE
    assert second.status is attempt.QualificationAttemptStatus.ATTEMPT_ALREADY_CONSUMED
    assert len(events) == calls_after_first

    crash_id = "f" * 32
    crash_directory = tmp_path / f"arch152-pm2a-attempt-{crash_id}"
    crash_directory.mkdir()
    (crash_directory / "attempt.json").write_text(
        '{"consumption":"CONSUMED_ON_RESERVATION"}\n', encoding="ascii"
    )
    crashed = _run_attempt(
        attempt_id=crash_id,
        oauth_factory=lambda: (_ for _ in ()).throw(
            AssertionError("crash-reserved attempt must not retry")
        ),
    )
    assert crashed.status is attempt.QualificationAttemptStatus.ATTEMPT_ALREADY_CONSUMED
    assert not (crash_directory / "evidence.json").exists()


def test_concurrent_attempt_id_has_one_provider_winner(monkeypatch, tmp_path) -> None:
    events: list[str] = []
    event_lock = Lock()
    _prepare(
        monkeypatch,
        tmp_path,
        schema=_schema_result(status=SchemaQualificationStatus.INCOMPLETE),
    )

    async def qualify(factory, *, on_attempt=None):
        with event_lock:
            events.append("provider")
        return _schema_result(status=SchemaQualificationStatus.INCOMPLETE)

    monkeypatch.setattr(attempt, "qualify_current_read_provider", qualify)

    def invoke():
        return _run_attempt(
            oauth_factory=lambda: None,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(lambda _: invoke(), range(2)))

    assert sorted(item.status.value for item in results) == sorted(
        [
            attempt.QualificationAttemptStatus.ATTEMPT_ALREADY_CONSUMED.value,
            attempt.QualificationAttemptStatus.SCHEMA_INCOMPLETE.value,
        ]
    )
    assert events == ["provider"]
