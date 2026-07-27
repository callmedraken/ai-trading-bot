from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Context, Decimal, localcontext
from uuid import UUID, uuid5

import pytest

from trading_bot.domain import OrderFill, OrderSide, Symbol
from trading_bot.execution import current_paper_ledger_state_id
from trading_bot.ledger import (
    COMPACT_PAPER_LEDGER_ARITHMETIC_VERSION,
    CompactPaperLedgerHistoryMode,
    CompactPaperLedgerPosition,
    CompactPaperLedgerReconciliationStatus,
    CompactPaperLedgerState,
    InvalidCompactPaperLedgerStateError,
    PaperLedger,
    PaperLedgerInitializationMode,
    PaperLedgerInitializationPosition,
    PaperLedgerInitializationRequest,
    compact_paper_ledger_state_id,
    export_compact_paper_ledger_state,
    initialize_paper_ledger,
    restore_paper_ledger_from_compact_state,
)

NOW = datetime(2026, 1, 5, 19, tzinfo=UTC)
LATER = datetime(2026, 1, 6, 19, tzinfo=UTC)
SPY = Symbol("SPY")
QQQ = Symbol("QQQ")
NAMESPACE = UUID("b8c40659-b147-5960-8fd1-6f6d66db6a17")


def _fill(
    name: str,
    symbol: Symbol,
    side: OrderSide,
    quantity: str,
    price: str,
    commission: str = "0",
) -> OrderFill:
    return OrderFill(
        uuid5(NAMESPACE, f"{name}:fill"),
        uuid5(NAMESPACE, f"{name}:order"),
        symbol,
        side,
        Decimal(quantity),
        Decimal(price),
        Decimal(commission),
        NOW,
    )


def _state(
    *,
    cash: Decimal = Decimal("100"),
    positions: tuple[CompactPaperLedgerPosition, ...] = (),
    realized: Decimal = Decimal("0"),
) -> CompactPaperLedgerState:
    return CompactPaperLedgerState.create(
        as_of=NOW,
        cash=cash,
        positions=positions,
        realized_profit_loss=realized,
    )


def _position(
    symbol: Symbol = SPY,
    quantity: str = "2",
    basis: str = "201",
) -> CompactPaperLedgerPosition:
    return CompactPaperLedgerPosition.from_exact_basis(
        symbol,
        Decimal(quantity),
        Decimal(basis),
    )


def test_exports_and_restores_empty_position_cash_account() -> None:
    ledger = PaperLedger(Decimal("1000"))

    state = export_compact_paper_ledger_state(ledger, as_of=NOW)
    restored, evidence = restore_paper_ledger_from_compact_state(state)

    assert state.cash == Decimal("1000")
    assert state.positions == ()
    assert state.realized_profit_loss == Decimal("0")
    assert state.as_of == NOW
    assert state.history_mode is CompactPaperLedgerHistoryMode.EMPTY
    assert restored.cash == state.cash
    assert dict(restored.positions) == {}
    assert restored.realized_profit_loss == Decimal("0")
    assert restored.fills == ()
    assert restored.is_compact_restored
    assert evidence.compact_state_id == state.compact_state_id
    assert evidence.restored_ledger_state_id == current_paper_ledger_state_id(restored)
    assert evidence.reconciliation_status is CompactPaperLedgerReconciliationStatus.PASS
    with pytest.raises(FrozenInstanceError):
        evidence.compact_state_id = state.compact_state_id  # type: ignore[misc]


def test_exports_and_restores_zero_cash_with_positive_position() -> None:
    ledger = PaperLedger(Decimal("100"))
    ledger.apply_fill(_fill("all-cash-buy", SPY, OrderSide.BUY, "2", "50"))

    state = export_compact_paper_ledger_state(ledger, as_of=NOW)
    restored, _ = restore_paper_ledger_from_compact_state(state)

    assert state.cash == Decimal("0")
    assert state.positions == (_position(quantity="2", basis="100"),)
    assert restored.cash == Decimal("0")
    assert restored.positions[SPY].quantity == Decimal("2")
    assert restored.positions[SPY].average_cost == Decimal("50")


def test_multiple_positions_preserve_exact_order_and_basis() -> None:
    ledger = PaperLedger(Decimal("2000"))
    ledger.apply_fill(_fill("spy-buy", SPY, OrderSide.BUY, "3", "100", "1"))
    ledger.apply_fill(_fill("qqq-buy", QQQ, OrderSide.BUY, "2", "200", "2"))

    state = export_compact_paper_ledger_state(ledger, as_of=NOW)
    restored, _ = restore_paper_ledger_from_compact_state(state)

    assert tuple(item.symbol for item in state.positions) == (SPY, QQQ)
    assert tuple(item.total_cost_basis for item in state.positions) == (
        Decimal("301"),
        Decimal("402"),
    )
    assert tuple(restored.positions) == (SPY, QQQ)
    assert export_compact_paper_ledger_state(restored, as_of=NOW) == state


@pytest.mark.parametrize(
    ("sale_price", "expected_realized"),
    (("120", Decimal("19")), ("80", Decimal("-21"))),
)
def test_positive_and_negative_cumulative_realized_profit_loss_restore_exactly(
    sale_price: str,
    expected_realized: Decimal,
) -> None:
    ledger = PaperLedger(Decimal("1000"))
    ledger.apply_fill(_fill("basis-buy", SPY, OrderSide.BUY, "2", "100"))
    ledger.apply_fill(
        _fill("realizing-sale", SPY, OrderSide.SELL, "1", sale_price, "1")
    )
    assert ledger.realized_profit_loss == expected_realized

    state = export_compact_paper_ledger_state(ledger, as_of=NOW)
    restored, _ = restore_paper_ledger_from_compact_state(state)

    assert state.realized_profit_loss == expected_realized
    assert restored.realized_profit_loss == expected_realized


def test_partial_sale_retains_basis_that_rounded_average_cannot_reconstruct() -> None:
    ledger = PaperLedger(Decimal("10"))
    ledger.apply_fill(
        _fill("fractional-basis-buy", SPY, OrderSide.BUY, "6", ".1", ".4")
    )
    ledger.apply_fill(_fill("partial-sale", SPY, OrderSide.SELL, "3", ".2"))

    state = export_compact_paper_ledger_state(ledger, as_of=NOW)
    position = state.positions[0]
    with localcontext(Context(prec=1024, Emax=999_999, Emin=-999_999)):
        reconstructed_basis = position.quantity * position.average_cost

    assert position.quantity == Decimal("3")
    assert position.total_cost_basis == Decimal("0.4999999999999999999999999999")
    assert reconstructed_basis != position.total_cost_basis

    restored, _ = restore_paper_ledger_from_compact_state(state)
    assert export_compact_paper_ledger_state(restored, as_of=NOW) == state


def test_export_identity_and_restoration_ignore_hostile_decimal_contexts() -> None:
    ledger = PaperLedger(Decimal("1000"))
    ledger.apply_fill(
        _fill(
            "hostile-context-buy",
            SPY,
            OrderSide.BUY,
            "3",
            ".3",
            ".1",
        )
    )

    with localcontext(Context(prec=2, Emax=9, Emin=-9)):
        low_state = export_compact_paper_ledger_state(ledger, as_of=NOW)
        low_restored, low_evidence = restore_paper_ledger_from_compact_state(low_state)
    with localcontext(Context(prec=80, Emax=9999, Emin=-9999)):
        high_state = export_compact_paper_ledger_state(ledger, as_of=NOW)
        high_restored, high_evidence = restore_paper_ledger_from_compact_state(
            high_state
        )

    assert low_state == high_state
    assert low_evidence == high_evidence
    assert export_compact_paper_ledger_state(low_restored, as_of=NOW) == low_state
    assert export_compact_paper_ledger_state(high_restored, as_of=NOW) == high_state


def test_position_order_is_identity_material() -> None:
    spy = _position(SPY, "2", "201")
    qqq = _position(QQQ, "3", "303")

    first = _state(positions=(spy, qqq))
    second = _state(positions=(qqq, spy))

    assert first.compact_state_id != second.compact_state_id
    assert compact_paper_ledger_state_id(first) == first.compact_state_id
    assert compact_paper_ledger_state_id(second) == second.compact_state_id


def test_compact_state_id_is_deterministic_and_pinned() -> None:
    first = _state(positions=(_position(),), realized=Decimal("-12.5"))
    second = _state(positions=(_position(),), realized=Decimal("-12.5"))

    assert first == second
    assert str(first.compact_state_id) == "1d0c133a-aba4-5e5e-9b41-db56560a75f9"


def test_equal_independent_restorations_have_equal_evidence_and_state() -> None:
    state = _state(
        cash=Decimal("0"),
        positions=(_position(SPY, "2", "201"), _position(QQQ, "3", "303")),
        realized=Decimal("4.5"),
    )

    first, first_evidence = restore_paper_ledger_from_compact_state(state)
    second, second_evidence = restore_paper_ledger_from_compact_state(state)

    assert first is not second
    assert first_evidence == second_evidence
    assert export_compact_paper_ledger_state(first, as_of=NOW) == state
    assert export_compact_paper_ledger_state(second, as_of=NOW) == state


@pytest.mark.parametrize(
    "value",
    (
        1,
        1.0,
        True,
        "1",
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
        Decimal("0"),
        Decimal("-1"),
        Decimal("1E-1025"),
        Decimal("1E1025"),
    ),
)
@pytest.mark.parametrize("field", ("quantity", "total_cost_basis"))
def test_position_rejects_invalid_authoritative_values(
    field: str,
    value: object,
) -> None:
    values: dict[str, object] = {
        "symbol": SPY,
        "quantity": Decimal("1"),
        "total_cost_basis": Decimal("1"),
    }
    values[field] = value
    with pytest.raises(InvalidCompactPaperLedgerStateError, match=field):
        CompactPaperLedgerPosition.from_exact_basis(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "value",
    (
        -1,
        0.0,
        False,
        "0",
        Decimal("-1"),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("1E-1025"),
        Decimal("1E1025"),
    ),
)
def test_state_rejects_invalid_cash(value: object) -> None:
    with pytest.raises(InvalidCompactPaperLedgerStateError, match="cash"):
        _state(cash=value)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "value",
    (
        0,
        0.0,
        False,
        "0",
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
        Decimal("1E-1025"),
        Decimal("1E1025"),
    ),
)
def test_state_rejects_invalid_realized_profit_loss(value: object) -> None:
    with pytest.raises(
        InvalidCompactPaperLedgerStateError,
        match="realized_profit_loss",
    ):
        _state(realized=value)  # type: ignore[arg-type]


def test_rejects_duplicate_symbols_all_zero_and_mismatched_average() -> None:
    position = _position()
    with pytest.raises(InvalidCompactPaperLedgerStateError, match="unique"):
        _state(positions=(position, position))
    with pytest.raises(InvalidCompactPaperLedgerStateError, match="all-zero"):
        _state(cash=Decimal("-0"), positions=(), realized=Decimal("5"))
    with pytest.raises(InvalidCompactPaperLedgerStateError, match="average_cost"):
        CompactPaperLedgerPosition(
            SPY,
            Decimal("3"),
            Decimal("1"),
            Decimal("0.333333333333333333"),
        )
    with pytest.raises(
        InvalidCompactPaperLedgerStateError,
        match="average_cost",
    ):
        CompactPaperLedgerPosition(
            SPY,
            Decimal("1"),
            Decimal("1"),
            Decimal("1." + ("0" * 1025)),
        )


def test_rejects_invalid_state_structure_and_timestamp() -> None:
    with pytest.raises(InvalidCompactPaperLedgerStateError, match="positions"):
        CompactPaperLedgerState.create(
            as_of=NOW,
            cash=Decimal("1"),
            positions=(object(),),  # type: ignore[arg-type]
            realized_profit_loss=Decimal("0"),
        )
    with pytest.raises(InvalidCompactPaperLedgerStateError, match="as_of"):
        CompactPaperLedgerState.create(
            as_of=datetime(2026, 1, 5, 19),
            cash=Decimal("1"),
            positions=(),
            realized_profit_loss=Decimal("0"),
        )
    with pytest.raises(InvalidCompactPaperLedgerStateError, match="symbol"):
        CompactPaperLedgerPosition.from_exact_basis(  # type: ignore[arg-type]
            "SPY",
            Decimal("1"),
            Decimal("1"),
        )


def test_signed_zero_is_normalized_and_models_are_immutable() -> None:
    state = _state(cash=Decimal("-0"), positions=(_position(),), realized=Decimal("-0"))

    assert state.cash.as_tuple().sign == 0
    assert state.realized_profit_loss.as_tuple().sign == 0
    with pytest.raises(FrozenInstanceError):
        state.cash = Decimal("1")  # type: ignore[misc]


def test_restoration_has_intentionally_empty_historical_fill_membership() -> None:
    ledger = PaperLedger(Decimal("1000"))
    old_fill = _fill("historical", SPY, OrderSide.BUY, "2", "100")
    ledger.apply_fill(old_fill)
    assert ledger.fills == (old_fill,)

    state = export_compact_paper_ledger_state(ledger, as_of=NOW)
    restored, _ = restore_paper_ledger_from_compact_state(state)

    assert restored.fills == ()
    assert restored.is_compact_restored
    assert not ledger.is_compact_restored


def test_future_supported_buy_and_sell_accounting_matches_after_restoration() -> None:
    original = PaperLedger(Decimal("1000"))
    original.apply_fill(_fill("opening", SPY, OrderSide.BUY, "3", "100", "1"))
    opening = export_compact_paper_ledger_state(original, as_of=NOW)
    restored, _ = restore_paper_ledger_from_compact_state(opening)
    future_fills = (
        _fill("future-buy", QQQ, OrderSide.BUY, "2", "50", "1"),
        _fill("future-sell", SPY, OrderSide.SELL, "1", "120", "1"),
    )

    with localcontext(Context(prec=1024, Emax=999_999, Emin=-999_999)):
        for item in future_fills:
            original.apply_fill(item)
            restored.apply_fill(item)
        original_state = export_compact_paper_ledger_state(original, as_of=LATER)
        restored_state = export_compact_paper_ledger_state(restored, as_of=LATER)

    assert restored_state == original_state
    assert restored.cash == original.cash
    assert restored.realized_profit_loss == original.realized_profit_loss
    assert dict(restored.positions) == dict(original.positions)


def test_existing_public_initialization_and_ledger_fingerprint_are_unchanged() -> None:
    request = PaperLedgerInitializationRequest(
        PaperLedgerInitializationMode.BOOTSTRAP_FILLS,
        NOW,
        Decimal("1000"),
        (PaperLedgerInitializationPosition(SPY, Decimal("2"), Decimal("100")),),
        UUID("20e175f9-81ad-5985-b460-15a79acbb41e"),
        (
            "optimized-simulation-cli-bootstrap-v1",
            "00000000-0000-0000-0000-000000000001",
            "BOOTSTRAP_FILLS",
        ),
    )

    ledger, evidence = initialize_paper_ledger(request)

    assert str(evidence.bootstrap_fills[0].fill_id) == (
        "ae7a1847-84ef-5f10-9f12-57a451a15574"
    )
    assert str(current_paper_ledger_state_id(ledger)) == (
        "223c9a68-b17c-5b98-bb30-01478a58c39f"
    )
    assert COMPACT_PAPER_LEDGER_ARITHMETIC_VERSION == (
        "compact-paper-ledger-arithmetic-v1"
    )
