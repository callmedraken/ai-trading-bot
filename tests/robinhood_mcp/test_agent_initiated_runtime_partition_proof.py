from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Final

import pytest

from trading_bot.domain import OrderSide
from trading_bot.live_prototype.l43_production_owner import L43SourceIdentity
from trading_bot.live_prototype.l43_provider_contracts import (
    L43AccountIdentity,
    L43DollarAmountFact,
    L43ExecutionFact,
    L43OrderFact,
    L43ReadPage,
)
from trading_bot.robinhood_mcp import agent_initiated_runtime_partition_proof as proof

_ACCOUNT_NUMBER: Final = "account-secret-147"
_ACCOUNT_FINGERPRINT: Final = "a" * 64
_SOURCE: Final = L43SourceIdentity(source_head="b" * 40, source_tree="c" * 40)
_OTHER_SOURCE: Final = L43SourceIdentity(source_head="d" * 40, source_tree="e" * 40)
_NOW: Final = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)


class _Read:
    def __init__(
        self,
        pages: dict[tuple[bool | None, str | None], L43ReadPage],
        *,
        fail_at: int | None = None,
        account: L43AccountIdentity | None = None,
        all_after: L43ReadPage | None = None,
    ) -> None:
        self.pages = pages
        self.fail_at = fail_at
        self.account = account or L43AccountIdentity(
            _ACCOUNT_NUMBER, _ACCOUNT_FINGERPRINT
        )
        self.all_after = all_after
        self.all_root_calls = 0
        self.calls: list[dict[str, object]] = []

    def get_accounts(self) -> L43AccountIdentity:
        return self.account

    def get_equity_orders(self, arguments: dict[str, object]) -> L43ReadPage:
        self.calls.append(dict(arguments))
        if self.fail_at == len(self.calls):
            raise RuntimeError("provider response must not be surfaced")
        filter_value = arguments.get("agent_initiated")
        cursor = arguments.get("cursor")
        if filter_value is not None and type(filter_value) is not bool:
            raise AssertionError("test request filter is malformed")
        if cursor is not None and type(cursor) is not str:
            raise AssertionError("test request cursor is malformed")
        if filter_value is None and cursor is None:
            self.all_root_calls += 1
            if self.all_root_calls == 2 and self.all_after is not None:
                return self.all_after
        return self.pages[(filter_value, cursor)]


def _order(
    order_id: str,
    agent_initiated: bool,
    *,
    symbol: str = "SPY",
    quantity: str = "0.5",
    state: str = "filled",
    executions: tuple[L43ExecutionFact, ...] = (),
    dollar_based_amount: L43DollarAmountFact | None = None,
) -> L43OrderFact:
    return L43OrderFact(
        order_id=order_id,
        symbol=symbol,
        side=OrderSide.BUY,
        state=state,
        placed_agent="agentic",
        agent_initiated=agent_initiated,
        created_at=_NOW,
        market_hours="regular_hours",
        time_in_force="day",
        order_type="market",
        cumulative_quantity=Decimal(quantity),
        average_price=Decimal("20"),
        dollar_based_amount=dollar_based_amount,
        executions=executions,
    )


def _pages(
    *,
    all_rows: tuple[L43OrderFact, ...],
    true_rows: tuple[L43OrderFact, ...],
    false_rows: tuple[L43OrderFact, ...],
    paginated: bool = False,
) -> dict[tuple[bool | None, str | None], L43ReadPage]:
    rows_by_filter = {None: all_rows, True: true_rows, False: false_rows}
    pages: dict[tuple[bool | None, str | None], L43ReadPage] = {}
    for filter_value, rows in rows_by_filter.items():
        if not paginated:
            pages[(filter_value, None)] = L43ReadPage(rows=rows, next_cursor=None)
            continue
        split = max(1, len(rows) // 2)
        cursor = f"cursor-{filter_value}"
        pages[(filter_value, None)] = L43ReadPage(rows=rows[:split], next_cursor=cursor)
        pages[(filter_value, cursor)] = L43ReadPage(rows=rows[split:], next_cursor=None)
    return pages


def _run(
    read: _Read,
    *,
    source_values: list[L43SourceIdentity] | None = None,
    **kwargs: object,
) -> proof.AgentInitiatedRuntimePartitionProofResult:
    values = source_values or [_SOURCE]

    def source_reader() -> L43SourceIdentity:
        return values.pop(0) if len(values) > 1 else values[0]

    return proof.prove_agent_initiated_partition(
        read,
        source_reader=source_reader,
        expected_source=_SOURCE,
        **kwargs,
    )


@pytest.mark.parametrize(
    ("all_rows", "true_rows", "false_rows"),
    (
        ((), (), ()),
        ((_order("true-only", True),), (_order("true-only", True),), ()),
        ((_order("false-only", False),), (), (_order("false-only", False),)),
        (
            (_order("true-mixed", True), _order("false-mixed", False)),
            (_order("true-mixed", True),),
            (_order("false-mixed", False),),
        ),
    ),
)
def test_proves_empty_and_true_false_partition_shapes(
    all_rows: tuple[L43OrderFact, ...],
    true_rows: tuple[L43OrderFact, ...],
    false_rows: tuple[L43OrderFact, ...],
) -> None:
    read = _Read(_pages(all_rows=all_rows, true_rows=true_rows, false_rows=false_rows))

    result = _run(read)

    assert result.status is proof.AgentInitiatedRuntimePartitionProofStatus.PROVEN
    assert result.partition_equality_proof == "PROVEN"
    assert result.production_order_scope_authority == "NOT_GRANTED"
    assert [item.label for item in result.logical_reads] == [
        "ALL_BEFORE",
        "TRUE",
        "FALSE",
        "ALL_AFTER",
    ]
    assert all(item.exhaustive for item in result.logical_reads)
    assert result.account_fingerprint == _ACCOUNT_FINGERPRINT
    assert result.source_head == _SOURCE.source_head
    assert result.source_tree == _SOURCE.source_tree


def test_multi_page_reads_preserve_each_filter_and_order_exactly() -> None:
    all_rows = tuple(_order(f"order-{index}", index < 2) for index in range(4))
    true_rows = all_rows[:2]
    false_rows = all_rows[2:]
    read = _Read(
        _pages(
            all_rows=all_rows,
            true_rows=true_rows,
            false_rows=false_rows,
            paginated=True,
        )
    )

    result = _run(read)

    assert result.proven
    assert read.calls == [
        {"account_number": _ACCOUNT_NUMBER, "symbol": "SPY"},
        {
            "account_number": _ACCOUNT_NUMBER,
            "symbol": "SPY",
            "cursor": "cursor-None",
        },
        {
            "account_number": _ACCOUNT_NUMBER,
            "symbol": "SPY",
            "agent_initiated": True,
        },
        {
            "account_number": _ACCOUNT_NUMBER,
            "symbol": "SPY",
            "agent_initiated": True,
            "cursor": "cursor-True",
        },
        {
            "account_number": _ACCOUNT_NUMBER,
            "symbol": "SPY",
            "agent_initiated": False,
        },
        {
            "account_number": _ACCOUNT_NUMBER,
            "symbol": "SPY",
            "agent_initiated": False,
            "cursor": "cursor-False",
        },
        {"account_number": _ACCOUNT_NUMBER, "symbol": "SPY"},
        {
            "account_number": _ACCOUNT_NUMBER,
            "symbol": "SPY",
            "cursor": "cursor-None",
        },
    ]
    assert [item.page_count for item in result.logical_reads] == [2, 2, 2, 2]
    assert [item.row_count for item in result.logical_reads] == [4, 2, 2, 4]
    assert len({item.query_sha256 for item in result.logical_reads}) == 3
    assert result.logical_reads[0].query_sha256 == result.logical_reads[3].query_sha256


@pytest.mark.parametrize(
    ("all_rows", "true_rows", "false_rows", "expected_reason"),
    (
        (
            (_order("stable", True),),
            (_order("stable", True),),
            (_order("stable", False),),
            "ORDER_FACT_CONFLICT",
        ),
        (
            (_order("one", True), _order("two", False)),
            (_order("one", True),),
            (),
            "PARTITION_UNION_MISMATCH",
        ),
        (
            (_order("one", True),),
            (_order("one", True), _order("extra", True)),
            (),
            "PARTITION_UNION_MISMATCH",
        ),
        (
            (_order("one", True),),
            (_order("one", False),),
            (),
            "TRUE_PARTITION_ROW_INVALID",
        ),
        (
            (_order("one", False),),
            (),
            (_order("one", True),),
            "FALSE_PARTITION_ROW_INVALID",
        ),
        (
            (_order("duplicate", True), _order("duplicate", True)),
            (_order("duplicate", True),),
            (),
            "ALL_BEFORE_DUPLICATE_ORDER_ID",
        ),
    ),
)
def test_partition_invariants_fail_closed(
    all_rows: tuple[L43OrderFact, ...],
    true_rows: tuple[L43OrderFact, ...],
    false_rows: tuple[L43OrderFact, ...],
    expected_reason: str,
) -> None:
    read = _Read(_pages(all_rows=all_rows, true_rows=true_rows, false_rows=false_rows))

    result = _run(read)

    assert result.status is proof.AgentInitiatedRuntimePartitionProofStatus.NOT_PROVEN
    assert result.reason == expected_reason
    assert result.partition_equality_proof == "NOT_PROVEN"
    assert result.production_order_scope_authority == "NOT_GRANTED"


def test_all_before_and_all_after_universe_mismatch_fails_closed() -> None:
    before = _order("before", True)
    after = _order("after", True)
    read = _Read(
        _pages(all_rows=(before,), true_rows=(before,), false_rows=()),
        all_after=L43ReadPage(rows=(after,), next_cursor=None),
    )

    result = _run(read)

    assert result.status is proof.AgentInitiatedRuntimePartitionProofStatus.NOT_PROVEN
    assert result.reason == "ALL_UNIVERSE_CHANGED"


@pytest.mark.parametrize(
    "mutation",
    (
        replace(_order("mutating", True), state="canceled"),
        replace(_order("mutating", True), cumulative_quantity=Decimal("0.7")),
        replace(
            _order("mutating", True),
            executions=(
                L43ExecutionFact(
                    execution_id="execution-147",
                    quantity=Decimal("0.1"),
                    price=Decimal("20"),
                    timestamp=_NOW,
                ),
            ),
        ),
        replace(
            _order("mutating", True),
            dollar_based_amount=L43DollarAmountFact(
                amount=Decimal("10"), currency_code="USD"
            ),
        ),
    ),
)
def test_same_order_id_material_mutation_fails_closed(
    mutation: L43OrderFact,
) -> None:
    base = _order("mutating", True)
    read = _Read(
        _pages(
            all_rows=(base,),
            true_rows=(mutation,),
            false_rows=(),
        )
    )

    result = _run(read)

    assert result.status is proof.AgentInitiatedRuntimePartitionProofStatus.NOT_PROVEN
    assert result.reason == "ORDER_FACT_CONFLICT"


def test_malformed_normalized_fact_and_non_spy_rows_fail_closed() -> None:
    malformed = _Read(
        {
            (None, None): L43ReadPage(rows=(object(),), next_cursor=None),
            (True, None): L43ReadPage(rows=(), next_cursor=None),
            (False, None): L43ReadPage(rows=(), next_cursor=None),
        }
    )
    non_spy = _Read(
        _pages(
            all_rows=(_order("not-spy", True, symbol="QQQ"),),
            true_rows=(),
            false_rows=(),
        )
    )

    malformed_result = _run(malformed)
    non_spy_result = _run(non_spy)

    assert malformed_result.reason == "ALL_BEFORE_FACT_INVALID"
    assert non_spy_result.reason == "ALL_BEFORE_FACT_INVALID"


@pytest.mark.parametrize("next_cursor", (1, ""))
def test_invalid_pagination_next_fails_closed(next_cursor: object) -> None:
    read = _Read(
        {
            (None, None): L43ReadPage(rows=(), next_cursor=next_cursor),
            (True, None): L43ReadPage(rows=(), next_cursor=None),
            (False, None): L43ReadPage(rows=(), next_cursor=None),
        }
    )

    result = _run(read)

    assert result.reason == "ALL_BEFORE_CURSOR_INVALID"


def test_repeated_cursor_and_incomplete_pagination_fail_closed(monkeypatch) -> None:
    repeated = _Read(
        {
            (None, None): L43ReadPage(rows=(), next_cursor="repeat"),
            (None, "repeat"): L43ReadPage(rows=(), next_cursor="repeat"),
            (True, None): L43ReadPage(rows=(), next_cursor=None),
            (False, None): L43ReadPage(rows=(), next_cursor=None),
        }
    )
    incomplete = _Read(
        {
            (None, None): L43ReadPage(rows=(), next_cursor="next"),
            (True, None): L43ReadPage(rows=(), next_cursor=None),
            (False, None): L43ReadPage(rows=(), next_cursor=None),
        }
    )

    assert _run(repeated).reason == "ALL_BEFORE_CURSOR_REPEATED"
    monkeypatch.setattr(proof, "_MAX_PAGES", 1)
    assert _run(incomplete).reason == "ALL_BEFORE_PAGINATION_INCOMPLETE"


def test_account_and_source_mismatch_fail_closed_without_order_reads() -> None:
    read = _Read(_pages(all_rows=(), true_rows=(), false_rows=()))
    wrong_account = _run(read, expected_account_fingerprint="f" * 64)

    source_read = _Read(_pages(all_rows=(), true_rows=(), false_rows=()))
    wrong_source = proof.prove_agent_initiated_partition(
        source_read,
        source_reader=lambda: _SOURCE,
        expected_source=_OTHER_SOURCE,
    )

    assert wrong_account.reason == "ACCOUNT_MISMATCH"
    assert (
        wrong_account.status
        is proof.AgentInitiatedRuntimePartitionProofStatus.NOT_PROVEN
    )
    assert read.calls == []
    assert wrong_source.reason == "SOURCE_MISMATCH"
    assert source_read.calls == []


def test_source_changes_during_four_read_window_fail_closed() -> None:
    read = _Read(_pages(all_rows=(), true_rows=(), false_rows=()))

    result = _run(read, source_values=[_SOURCE, _OTHER_SOURCE])

    assert result.reason == "SOURCE_CHANGED"
    assert len(read.calls) == 4


@pytest.mark.parametrize(
    ("fail_at", "expected_reason"),
    (
        (1, "ALL_BEFORE_READ_EXCEPTION"),
        (2, "TRUE_READ_EXCEPTION"),
        (3, "FALSE_READ_EXCEPTION"),
        (4, "ALL_AFTER_READ_EXCEPTION"),
    ),
)
def test_provider_read_exception_at_each_stage_fails_closed(
    fail_at: int,
    expected_reason: str,
) -> None:
    read = _Read(_pages(all_rows=(), true_rows=(), false_rows=()), fail_at=fail_at)

    result = _run(read)

    assert result.reason == expected_reason
    assert result.status is proof.AgentInitiatedRuntimePartitionProofStatus.NOT_PROVEN


def test_successful_evidence_is_bound_and_contains_no_raw_account_or_ids() -> None:
    order_id = "provider-order-secret-147"
    read = _Read(
        _pages(
            all_rows=(_order(order_id, True),),
            true_rows=(_order(order_id, True),),
            false_rows=(),
        )
    )

    result = _run(read)

    assert result.proven
    assert result.stable_all_universe_digest is not None
    assert result.true_partition_digest is not None
    assert result.false_partition_digest is not None
    assert result.canonical_order_material_digest is not None
    assert result.evidence_sha256
    evidence = result.evidence_json.decode("ascii")
    assert _ACCOUNT_NUMBER not in evidence
    assert order_id not in evidence
    assert "provider response" not in evidence
    assert result.evidence_sha256 == hashlib.sha256(result.evidence_json).hexdigest()


def test_default_source_reader_binds_current_git_identity() -> None:
    read = _Read(_pages(all_rows=(), true_rows=(), false_rows=()))

    result = proof.prove_agent_initiated_partition(
        read,
        repo_root=Path(__file__).resolve().parents[2],
    )

    assert result.proven
    assert result.source_head is not None and len(result.source_head) == 40
    assert result.source_tree is not None and len(result.source_tree) == 40
