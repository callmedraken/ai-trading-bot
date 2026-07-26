from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Context, Decimal, localcontext
from uuid import UUID

import pytest

from trading_bot.cli._simulation_bootstrap import (
    InitializationMode,
    InitialLedgerConfig,
    InitialPositionConfig,
    initialize_ledger,
)
from trading_bot.domain import OrderSide, Symbol
from trading_bot.execution.state_fingerprints import ledger_snapshot, ledger_state_id
from trading_bot.ledger import (
    InvalidPaperLedgerInitializationError,
    PaperLedgerInitializationMode,
    PaperLedgerInitializationPosition,
    PaperLedgerInitializationRequest,
    initialize_paper_ledger,
)

NOW = datetime(2026, 1, 5, 19, tzinfo=UTC)
REQUEST_ID = UUID("00000000-0000-0000-0000-000000000001")
NAMESPACE = UUID("20e175f9-81ad-5985-b460-15a79acbb41e")
SPY = Symbol("SPY")
QQQ = Symbol("QQQ")


def _request(
    *,
    mode: PaperLedgerInitializationMode = PaperLedgerInitializationMode.BOOTSTRAP_FILLS,
    cash: Decimal = Decimal("1000"),
    positions: tuple[PaperLedgerInitializationPosition, ...] = (
        PaperLedgerInitializationPosition(SPY, Decimal("2"), Decimal("100")),
    ),
) -> PaperLedgerInitializationRequest:
    return PaperLedgerInitializationRequest(
        mode,
        NOW,
        cash,
        positions,
        NAMESPACE,
        ("optimized-simulation-cli-bootstrap-v1", str(REQUEST_ID), mode.value),
    )


def test_cash_only_initialization_returns_empty_synthetic_evidence() -> None:
    ledger, evidence = initialize_paper_ledger(
        _request(
            mode=PaperLedgerInitializationMode.CASH_ONLY,
            positions=(),
        )
    )

    assert ledger.cash == Decimal("1000")
    assert ledger.realized_profit_loss == Decimal("0")
    assert dict(ledger.positions) == {}
    assert ledger.fills == ()
    assert evidence.bootstrap_fills == ()
    assert evidence.request.mode is PaperLedgerInitializationMode.CASH_ONLY
    with pytest.raises(FrozenInstanceError):
        evidence.bootstrap_fills = ()  # type: ignore[misc]


def test_populated_initialization_returns_ordered_synthetic_bootstrap_fills() -> None:
    positions = (
        PaperLedgerInitializationPosition(SPY, Decimal("2"), Decimal("100")),
        PaperLedgerInitializationPosition(QQQ, Decimal("3.5"), Decimal("40.25")),
    )
    ledger, evidence = initialize_paper_ledger(_request(positions=positions))

    assert ledger.cash == Decimal("1000")
    assert ledger.realized_profit_loss == Decimal("0")
    assert tuple(ledger.fills) == evidence.bootstrap_fills
    assert [fill.symbol for fill in evidence.bootstrap_fills] == [SPY, QQQ]
    assert all(fill.side is OrderSide.BUY for fill in evidence.bootstrap_fills)
    assert all(fill.commission == Decimal("0") for fill in evidence.bootstrap_fills)
    assert all(fill.filled_at == NOW for fill in evidence.bootstrap_fills)
    assert ledger.positions[SPY].quantity == Decimal("2")
    assert ledger.positions[SPY].average_cost == Decimal("100")
    assert ledger.positions[QQQ].quantity == Decimal("3.5")
    assert ledger.positions[QQQ].average_cost == Decimal("40.25")


@pytest.mark.parametrize(
    "value",
    (Decimal("-1"), Decimal("NaN"), Decimal("Infinity"), 1, 1.0, True, "1"),
)
def test_initialization_rejects_invalid_cash_scalars(value: object) -> None:
    with pytest.raises(InvalidPaperLedgerInitializationError, match="available_cash"):
        _request(cash=value)  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ("quantity", "average_cost"))
@pytest.mark.parametrize(
    "value",
    (Decimal("-1"), Decimal("0"), Decimal("NaN"), 1, 1.0, True, "1"),
)
def test_initialization_rejects_invalid_position_scalars(
    field: str,
    value: object,
) -> None:
    values: dict[str, object] = {
        "symbol": SPY,
        "quantity": Decimal("1"),
        "average_cost": Decimal("100"),
    }
    values[field] = value
    with pytest.raises(InvalidPaperLedgerInitializationError, match=field):
        PaperLedgerInitializationPosition(**values)  # type: ignore[arg-type]


def test_initialization_rejects_duplicate_symbols_and_invalid_mode_shapes() -> None:
    position = PaperLedgerInitializationPosition(SPY, Decimal("1"), Decimal("100"))
    with pytest.raises(InvalidPaperLedgerInitializationError, match="unique"):
        _request(positions=(position, position))
    with pytest.raises(InvalidPaperLedgerInitializationError, match="CASH_ONLY"):
        _request(mode=PaperLedgerInitializationMode.CASH_ONLY)
    with pytest.raises(
        InvalidPaperLedgerInitializationError, match="requires at least"
    ):
        _request(mode=PaperLedgerInitializationMode.BOOTSTRAP_FILLS, positions=())


def test_initialization_arithmetic_is_independent_of_the_ambient_decimal_context() -> (
    None
):
    request = _request(
        cash=Decimal("1000.12345678901234567890123456789"),
        positions=(
            PaperLedgerInitializationPosition(
                SPY,
                Decimal("3.14159265358979323846264338327"),
                Decimal("271.828182845904523536028747135"),
            ),
        ),
    )
    with localcontext(Context(prec=2)):
        low_ledger, low_evidence = initialize_paper_ledger(request)
    with localcontext(Context(prec=50)):
        high_ledger, high_evidence = initialize_paper_ledger(request)

    assert low_ledger.cash == high_ledger.cash == request.available_cash
    assert low_evidence == high_evidence
    assert low_ledger.fills == high_ledger.fills


def test_existing_optimized_bootstrap_ids_and_ledger_state_are_unchanged() -> None:
    initial = InitialLedgerConfig(
        InitializationMode.BOOTSTRAP_FILLS,
        NOW,
        Decimal("1000"),
        (InitialPositionConfig(SPY, Decimal("2"), Decimal("100")),),
    )
    delegated_ledger, delegated_fills = initialize_ledger(REQUEST_ID, initial)
    public_ledger, public_evidence = initialize_paper_ledger(
        _request(
            positions=(
                PaperLedgerInitializationPosition(SPY, Decimal("2"), Decimal("100")),
            )
        )
    )

    assert str(delegated_fills[0].fill_id) == "ae7a1847-84ef-5f10-9f12-57a451a15574"
    assert str(delegated_fills[0].order_id) == "f26b6bfe-3cc6-574b-aff8-49009ed96c1d"
    assert delegated_fills == public_evidence.bootstrap_fills
    assert ledger_state_id(ledger_snapshot(delegated_ledger)) == ledger_state_id(
        ledger_snapshot(public_ledger)
    )
    assert str(ledger_state_id(ledger_snapshot(delegated_ledger))) == (
        "223c9a68-b17c-5b98-bb30-01478a58c39f"
    )
