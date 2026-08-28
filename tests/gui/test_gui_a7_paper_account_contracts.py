"""Pure-Python GUI-A7a verified paper-account presentation contract tests."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from trading_bot.gui import (
    MAX_PAPER_ACCOUNT_MESSAGE_CHARACTERS,
    MAX_PAPER_ACCOUNT_POSITIONS,
    MAX_PAPER_ACCOUNT_SYMBOL_CHARACTERS,
    PaperAccountCheckpointKindView,
    PaperAccountPageState,
    PaperAccountPageStatus,
    PaperAccountPositionView,
    VerifiedPaperAccountView,
    unavailable_paper_account_state,
)
from trading_bot.gui.mock_service import (
    MockGuiApplicationService,
    ResearchReportGuiApplicationService,
)

_CHECKPOINT_ID = UUID("00000000-0000-0000-0000-000000000101")
_LINEAGE_ID = UUID("00000000-0000-0000-0000-000000000102")
_ACCOUNT_STATE_ID = UUID("00000000-0000-0000-0000-000000000103")
_COMPACT_STATE_ID = UUID("00000000-0000-0000-0000-000000000104")
_AS_OF = datetime(2026, 8, 27, 22, 0, tzinfo=UTC)
_ARTIFACT_SHA256 = "a" * 64


def _position(
    symbol: str = "SPY",
    quantity: str = "2",
    total_cost_basis: str = "20",
    average_cost: str = "10",
) -> PaperAccountPositionView:
    return PaperAccountPositionView(
        symbol=symbol,
        quantity=Decimal(quantity),
        total_cost_basis=Decimal(total_cost_basis),
        average_cost=Decimal(average_cost),
    )


def _account(**overrides: object) -> VerifiedPaperAccountView:
    values: dict[str, object] = {
        "checkpoint_kind": PaperAccountCheckpointKindView.GENESIS,
        "sequence": 0,
        "checkpoint_id": _CHECKPOINT_ID,
        "lineage_id": _LINEAGE_ID,
        "account_state_id": _ACCOUNT_STATE_ID,
        "compact_state_id": _COMPACT_STATE_ID,
        "as_of": _AS_OF,
        "cash": Decimal("1000.00"),
        "realized_profit_loss": Decimal("-12.50"),
        "positions": (_position(),),
        "artifact_sha256": _ARTIFACT_SHA256,
        "artifact_byte_length": 1234,
    }
    values.update(overrides)
    return VerifiedPaperAccountView(**values)  # type: ignore[arg-type]


def test_paper_account_page_state_requires_exact_payload_for_status() -> None:
    account = _account()

    assert (
        PaperAccountPageState(
            status=PaperAccountPageStatus.VERIFIED,
            message="One checkpoint was verified offline.",
            account=account,
        ).account
        is account
    )

    with pytest.raises(ValueError, match="requires one account"):
        PaperAccountPageState(
            status=PaperAccountPageStatus.VERIFIED,
            message="Missing account.",
            account=None,
        )

    with pytest.raises(ValueError, match="must not contain"):
        PaperAccountPageState(
            status=PaperAccountPageStatus.UNAVAILABLE,
            message="Unavailable.",
            account=account,
        )

    with pytest.raises(TypeError, match="PaperAccountPageStatus"):
        PaperAccountPageState(
            status="verified",  # type: ignore[arg-type]
            message="Wrong status type.",
            account=None,
        )


def test_paper_account_page_message_is_nonblank_and_bounded() -> None:
    PaperAccountPageState(
        status=PaperAccountPageStatus.UNAVAILABLE,
        message="x" * MAX_PAPER_ACCOUNT_MESSAGE_CHARACTERS,
        account=None,
    )

    with pytest.raises(ValueError, match="non-empty text"):
        PaperAccountPageState(
            status=PaperAccountPageStatus.UNAVAILABLE,
            message="   ",
            account=None,
        )

    with pytest.raises(ValueError, match="exceeds the presentation bound"):
        PaperAccountPageState(
            status=PaperAccountPageStatus.UNAVAILABLE,
            message="x" * (MAX_PAPER_ACCOUNT_MESSAGE_CHARACTERS + 1),
            account=None,
        )


def test_verified_account_enforces_checkpoint_kind_and_sequence() -> None:
    genesis = _account()
    successor = _account(
        checkpoint_kind=PaperAccountCheckpointKindView.CYCLE_SUCCESSOR,
        sequence=1,
    )

    assert genesis.sequence == 0
    assert successor.sequence == 1

    with pytest.raises(TypeError, match="checkpoint_kind"):
        _account(checkpoint_kind="GENESIS")

    with pytest.raises(ValueError, match="nonnegative exact integer"):
        _account(sequence=-1)

    with pytest.raises(ValueError, match="nonnegative exact integer"):
        _account(sequence=True)

    with pytest.raises(ValueError, match="GENESIS sequence must be zero"):
        _account(sequence=1)

    with pytest.raises(ValueError, match="CYCLE_SUCCESSOR sequence must be positive"):
        _account(
            checkpoint_kind=PaperAccountCheckpointKindView.CYCLE_SUCCESSOR,
            sequence=0,
        )


@pytest.mark.parametrize(
    "field_name",
    ("checkpoint_id", "lineage_id", "account_state_id", "compact_state_id"),
)
def test_verified_account_enforces_exact_identity_types(field_name: str) -> None:
    with pytest.raises(TypeError, match=field_name):
        _account(**{field_name: str(_CHECKPOINT_ID)})


def test_verified_account_enforces_exact_as_of_type() -> None:
    with pytest.raises(TypeError, match="as_of"):
        _account(as_of="2026-08-27T22:00:00Z")

    with pytest.raises(ValueError, match="timezone-aware"):
        _account(as_of=datetime(2026, 8, 27, 22, 0))


def test_verified_account_enforces_exact_financial_decimals() -> None:
    account = _account(
        cash=Decimal("0"),
        realized_profit_loss=Decimal("-25.125"),
    )

    assert account.cash == Decimal("0")
    assert account.realized_profit_loss == Decimal("-25.125")

    with pytest.raises(TypeError, match="cash"):
        _account(cash=1000)

    with pytest.raises(ValueError, match="cash must be nonnegative"):
        _account(cash=Decimal("-0.01"))

    with pytest.raises(ValueError, match="realized_profit_loss must be finite"):
        _account(realized_profit_loss=Decimal("NaN"))


def test_position_contract_preserves_order_and_exact_accounting() -> None:
    positions = (
        _position("SPY", "2", "20", "10"),
        _position("QQQ", "3", "30", "10"),
    )
    account = _account(positions=positions)

    assert account.positions is positions
    assert tuple(item.symbol for item in account.positions) == ("SPY", "QQQ")

    with pytest.raises(ValueError, match="average_cost does not match"):
        _position(average_cost="11")

    with pytest.raises(ValueError, match="must be unique"):
        _account(positions=(_position("SPY"), _position("SPY")))

    with pytest.raises(ValueError, match="domain ticker contract"):
        _position(symbol="NOT/VALID")

    with pytest.raises(ValueError, match="canonical uppercase"):
        _position(symbol="spy")

    with pytest.raises(ValueError, match="domain ticker contract"):
        _position(symbol="X" * (MAX_PAPER_ACCOUNT_SYMBOL_CHARACTERS + 1))


def test_position_contract_enforces_exact_finite_decimals() -> None:
    with pytest.raises(TypeError, match="quantity"):
        PaperAccountPositionView(
            symbol="SPY",
            quantity=2,  # type: ignore[arg-type]
            total_cost_basis=Decimal("20"),
            average_cost=Decimal("10"),
        )

    with pytest.raises(ValueError, match="total_cost_basis must be finite"):
        PaperAccountPositionView(
            symbol="SPY",
            quantity=Decimal("2"),
            total_cost_basis=Decimal("NaN"),
            average_cost=Decimal("10"),
        )

    with pytest.raises(ValueError, match="average_cost must be finite"):
        PaperAccountPositionView(
            symbol="SPY",
            quantity=Decimal("2"),
            total_cost_basis=Decimal("20"),
            average_cost=Decimal("Infinity"),
        )


def test_position_count_uses_existing_compact_ledger_bound() -> None:
    positions = tuple(
        _position(symbol=f"S{index}") for index in range(MAX_PAPER_ACCOUNT_POSITIONS)
    )
    assert len(_account(positions=positions).positions) == MAX_PAPER_ACCOUNT_POSITIONS

    with pytest.raises(ValueError, match="presentation count bound"):
        _account(
            positions=tuple(
                _position(symbol=f"S{index}")
                for index in range(MAX_PAPER_ACCOUNT_POSITIONS + 1)
            )
        )


def test_verified_account_enforces_artifact_evidence() -> None:
    with pytest.raises(ValueError, match="artifact_sha256"):
        _account(artifact_sha256="A" * 64)

    with pytest.raises(ValueError, match="artifact_byte_length"):
        _account(artifact_byte_length=-1)

    with pytest.raises(ValueError, match="artifact_byte_length"):
        _account(artifact_byte_length=True)


def test_default_services_return_deterministic_unavailable_paper_account_state(
    tmp_path,
) -> None:
    mock = MockGuiApplicationService()
    research = ResearchReportGuiApplicationService(tmp_path / "missing-report.json")

    assert mock.get_paper_account_state() == unavailable_paper_account_state()
    assert research.get_paper_account_state() == unavailable_paper_account_state()
    assert mock.get_paper_account_state().status is PaperAccountPageStatus.UNAVAILABLE


def test_public_paper_account_contract_is_qt_free() -> None:
    state = unavailable_paper_account_state()

    assert state.status is PaperAccountPageStatus.UNAVAILABLE
    assert state.account is None
