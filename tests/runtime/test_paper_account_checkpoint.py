"""Focused schema-1 GENESIS paper-account checkpoint coverage."""

import json
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Context, Decimal, localcontext
from hashlib import sha256
from uuid import UUID

import pytest

from trading_bot.domain import Symbol
from trading_bot.ledger import CompactPaperLedgerHistoryMode
from trading_bot.portfolio import MetadataEntry
from trading_bot.runtime import (
    InvalidPaperAccountCheckpointRequestError,
    PaperAccountCheckpointKind,
    PaperAccountCheckpointPosition,
    PaperAccountCheckpointReference,
    PaperAccountCheckpointReplayError,
    PaperAccountCheckpointSchemaError,
    PaperAccountCheckpointSyntaxError,
    PaperAccountCheckpointVerificationStatus,
    PaperAccountGenesisRequest,
    create_genesis_paper_account_checkpoint,
    parse_paper_account_checkpoint,
    replay_verified_genesis_paper_account_checkpoint,
    serialize_paper_account_checkpoint,
    verify_genesis_paper_account_checkpoint,
)

NOW = datetime(2026, 2, 3, 4, 5, 6, tzinfo=UTC)
SPY = Symbol("SPY")
QQQ = Symbol("QQQ")


def _position(
    symbol: Symbol = SPY,
    quantity: str = "2",
    basis: str = "201",
) -> PaperAccountCheckpointPosition:
    return PaperAccountCheckpointPosition.from_exact_basis(
        symbol, Decimal(quantity), Decimal(basis)
    )


def _request(
    *,
    cash: Decimal = Decimal("1000"),
    positions: tuple[PaperAccountCheckpointPosition, ...] = (_position(),),
    realized: Decimal = Decimal("-5"),
    metadata: tuple[MetadataEntry, ...] = (MetadataEntry("source", "manual"),),
) -> PaperAccountGenesisRequest:
    return PaperAccountGenesisRequest(NOW, cash, positions, realized, metadata)


def _canonical_tree(payload: bytes) -> dict[str, object]:
    return json.loads(payload.decode("utf-8"))


def _canonical_bytes(tree: dict[str, object]) -> bytes:
    return (
        json.dumps(tree, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


@pytest.mark.parametrize(
    ("cash", "positions", "realized"),
    (
        (Decimal("100"), (), Decimal("0")),
        (Decimal("0"), (_position(),), Decimal("3.5")),
        (Decimal("100"), (_position(), _position(QQQ, "3", "303")), Decimal("-3.5")),
    ),
)
def test_genesis_preserves_supported_caller_asserted_account_states(
    cash: Decimal,
    positions: tuple[PaperAccountCheckpointPosition, ...],
    realized: Decimal,
) -> None:
    checkpoint = create_genesis_paper_account_checkpoint(
        _request(cash=cash, positions=positions, realized=realized)
    )

    assert checkpoint.kind is PaperAccountCheckpointKind.GENESIS
    assert checkpoint.sequence == 0
    assert checkpoint.prior_checkpoint is None
    assert checkpoint.producing_cycle is None
    assert checkpoint.account_state.cash == cash
    assert checkpoint.account_state.positions == positions
    assert checkpoint.account_state.realized_profit_loss == realized
    assert checkpoint.account_state.as_of == NOW
    assert checkpoint.account_state.compact_state().history_mode is (
        CompactPaperLedgerHistoryMode.EMPTY
    )


def test_genesis_canonical_round_trip_and_offline_restoration() -> None:
    checkpoint = create_genesis_paper_account_checkpoint(_request())
    payload = serialize_paper_account_checkpoint(checkpoint)
    result = verify_genesis_paper_account_checkpoint(
        payload,
        expected_checkpoint_byte_length=len(payload),
        expected_checkpoint_sha256=sha256(payload).hexdigest(),
    )

    assert parse_paper_account_checkpoint(payload) == checkpoint
    assert payload.endswith(b"\n")
    assert result.status is PaperAccountCheckpointVerificationStatus.PASS
    assert result.checkpoint == checkpoint
    assert result.restored_ledger is not None
    assert result.restored_ledger.cash == Decimal("1000")
    assert result.restored_ledger.positions[SPY].quantity == Decimal("2")
    assert result.restored_ledger.fills == ()
    assert result.restored_ledger.is_compact_restored
    assert result.restoration_evidence is not None
    replayed = replay_verified_genesis_paper_account_checkpoint(result)
    assert replayed[0] == checkpoint
    with pytest.raises(FrozenInstanceError):
        checkpoint.sequence = 1  # type: ignore[misc]


def test_partial_sale_basis_is_authoritative_not_reconstructed_from_average() -> None:
    position = _position(SPY, "3", "0.4999999999999999999999999999")
    checkpoint = create_genesis_paper_account_checkpoint(
        _request(cash=Decimal("5"), positions=(position,))
    )
    restored = verify_genesis_paper_account_checkpoint(
        serialize_paper_account_checkpoint(checkpoint)
    ).restored_ledger

    with localcontext(Context(prec=1024, Emax=999_999, Emin=-999_999)):
        reconstructed_basis = position.quantity * position.average_cost
    assert reconstructed_basis != position.total_cost_basis
    assert restored is not None
    assert restored.export_compact_checkpoint_state(as_of=NOW) == (
        checkpoint.account_state.compact_state()
    )


def test_golden_identity_and_canonical_artifact_vector() -> None:
    checkpoint = create_genesis_paper_account_checkpoint(_request())
    payload = serialize_paper_account_checkpoint(checkpoint)

    assert str(checkpoint.account_state.account_state_id) == (
        "6f40f494-8152-592e-a8f6-7be0d9b9265c"
    )
    assert str(checkpoint.lineage_id) == "b93a898d-e0fa-5bf1-bcee-6523138c0c40"
    assert str(checkpoint.checkpoint_id) == "7be45812-6cfe-53c7-a47f-6c143b1d624c"
    assert str(checkpoint.compact_ledger_state_id) == (
        "340c8d6e-a517-58bf-bdd5-ac21c14097cd"
    )
    assert str(checkpoint.empty_engine_state_id) == (
        "6bec5d03-e88e-5383-b8ec-82b2ec4db4d4"
    )
    assert payload == (
        b'{"checkpoint":{"account_state":{"account_state_id":"6f40f494-8152-592e-a8f6-7be0d9b9265c","as_of":"2026-02-03T04:05:06Z","cash":"1000","compact_ledger_state_id":"340c8d6e-a517-58bf-bdd5-ac21c14097cd","positions":[{"average_cost":"100.5","quantity":"2","symbol":"SPY","total_cost_basis":"201"}],"realized_profit_loss":"-5"},"checkpoint_id":"7be45812-6cfe-53c7-a47f-6c143b1d624c","empty_engine_state_id":"6bec5d03-e88e-5383-b8ec-82b2ec4db4d4","kind":"GENESIS","lineage_id":"b93a898d-e0fa-5bf1-bcee-6523138c0c40","metadata":[{"key":"source","value":"manual"}],"prior_checkpoint":null,"producing_cycle":null,"sequence":0},"schema_version":1}\n'
    )
    assert len(payload) == 638
    assert sha256(payload).hexdigest() == (
        "739f1d17705834c3d2a806c4ea1d7561a45a0f269bcb633e89a46eeecbe21b59"
    )


def test_order_is_identity_material_and_independent_requests_are_equal() -> None:
    first = create_genesis_paper_account_checkpoint(
        _request(positions=(_position(SPY), _position(QQQ, "3", "303")))
    )
    second = create_genesis_paper_account_checkpoint(
        _request(positions=(_position(QQQ, "3", "303"), _position(SPY)))
    )
    equivalent = create_genesis_paper_account_checkpoint(_request())

    assert first.checkpoint_id != second.checkpoint_id
    assert equivalent == create_genesis_paper_account_checkpoint(_request())


def test_metadata_order_is_identity_material() -> None:
    first = create_genesis_paper_account_checkpoint(
        _request(
            metadata=(
                MetadataEntry("source", "manual"),
                MetadataEntry("operator", "one"),
            )
        )
    )
    second = create_genesis_paper_account_checkpoint(
        _request(
            metadata=(
                MetadataEntry("operator", "one"),
                MetadataEntry("source", "manual"),
            )
        )
    )

    assert first.lineage_id != second.lineage_id
    assert first.checkpoint_id != second.checkpoint_id


def test_hostile_decimal_context_does_not_change_identifiers_or_bytes() -> None:
    request = _request(
        cash=Decimal("10"),
        positions=(_position(SPY, "3", "1"),),
    )
    with localcontext(Context(prec=2, Emax=9, Emin=-9)):
        low = create_genesis_paper_account_checkpoint(request)
        low_bytes = serialize_paper_account_checkpoint(low)
    with localcontext(Context(prec=80, Emax=9999, Emin=-9999)):
        high = create_genesis_paper_account_checkpoint(request)
        high_bytes = serialize_paper_account_checkpoint(high)

    assert low == high
    assert low_bytes == high_bytes


@pytest.mark.parametrize(
    "request_factory",
    (
        lambda: _request(cash=Decimal("0"), positions=()),
        lambda: _request(positions=(_position(), _position())),
        lambda: _request(metadata=(MetadataEntry("checkpoint.note", "x"),)),
        lambda: PaperAccountGenesisRequest(
            NOW,
            Decimal("1"),
            (),
            Decimal("0"),
            (),
            (object(),),
        ),
    ),
)
def test_genesis_rejects_invalid_account_or_reserved_metadata(
    request_factory: object,
) -> None:
    with pytest.raises(InvalidPaperAccountCheckpointRequestError):
        request_factory()  # type: ignore[operator]


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("quantity", 1.0),
        ("quantity", True),
        ("quantity", Decimal("0")),
        ("total_cost_basis", Decimal("NaN")),
        ("total_cost_basis", Decimal("1E-1025")),
        ("total_cost_basis", Decimal("1E1025")),
    ),
)
def test_position_rejects_invalid_exact_scalars(field: str, value: object) -> None:
    values: dict[str, object] = {
        "symbol": SPY,
        "quantity": Decimal("1"),
        "total_cost_basis": Decimal("1"),
    }
    values[field] = value
    with pytest.raises(InvalidPaperAccountCheckpointRequestError):
        PaperAccountCheckpointPosition.from_exact_basis(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ("cash", "realized_profit_loss"))
@pytest.mark.parametrize("value", (1.0, True, Decimal("NaN"), Decimal("Infinity")))
def test_request_rejects_invalid_account_scalars(field: str, value: object) -> None:
    values: dict[str, object] = {
        "as_of": NOW,
        "cash": Decimal("1"),
        "positions": (),
        "realized_profit_loss": Decimal("0"),
    }
    values[field] = value
    with pytest.raises(InvalidPaperAccountCheckpointRequestError):
        PaperAccountGenesisRequest(**values)  # type: ignore[arg-type]


def test_checkpoint_reference_keeps_artifact_evidence_outside_domain_identity() -> None:
    checkpoint = create_genesis_paper_account_checkpoint(_request())
    first = PaperAccountCheckpointReference(
        checkpoint.checkpoint_id,
        0,
        "0" * 64,
        1,
    )
    second = PaperAccountCheckpointReference(
        checkpoint.checkpoint_id,
        0,
        "1" * 64,
        2,
    )

    assert first.checkpoint_id == second.checkpoint_id == checkpoint.checkpoint_id
    with pytest.raises(InvalidPaperAccountCheckpointRequestError):
        PaperAccountCheckpointReference(checkpoint.checkpoint_id, 1, "0" * 64, 1)


@pytest.mark.parametrize(
    "mutate",
    (
        lambda tree: tree["checkpoint"].update({"checkpoint_id": str(UUID(int=1))}),  # type: ignore[index]
        lambda tree: tree["checkpoint"].update(
            {"empty_engine_state_id": str(UUID(int=1))}
        ),  # type: ignore[index]
        lambda tree: tree["checkpoint"].update({"lineage_id": str(UUID(int=1))}),  # type: ignore[index]
        lambda tree: tree["checkpoint"].update({"kind": "OTHER"}),  # type: ignore[index]
        lambda tree: tree["checkpoint"].update({"sequence": 1}),  # type: ignore[index]
        lambda tree: tree["checkpoint"].update({"prior_checkpoint": "x"}),  # type: ignore[index]
        lambda tree: tree["checkpoint"].update({"producing_cycle": "x"}),  # type: ignore[index]
        lambda tree: tree["checkpoint"]["account_state"].update(
            {"account_state_id": str(UUID(int=1))}
        ),  # type: ignore[index]
        lambda tree: tree["checkpoint"]["account_state"].update(
            {"compact_ledger_state_id": str(UUID(int=1))}
        ),  # type: ignore[index]
        lambda tree: tree["checkpoint"]["account_state"].update(
            {"as_of": "2026-02-04T04:05:06Z"}
        ),  # type: ignore[index]
        lambda tree: tree["checkpoint"]["account_state"].update({"cash": "999"}),  # type: ignore[index]
        lambda tree: tree["checkpoint"]["account_state"].update(
            {"realized_profit_loss": "0"}
        ),  # type: ignore[index]
        lambda tree: tree["checkpoint"]["account_state"]["positions"][0].update(
            {"symbol": "QQQ"}
        ),  # type: ignore[index]
        lambda tree: tree["checkpoint"]["account_state"]["positions"][0].update(
            {"quantity": "3"}
        ),  # type: ignore[index]
        lambda tree: tree["checkpoint"]["account_state"]["positions"][0].update(
            {"total_cost_basis": "202"}
        ),  # type: ignore[index]
        lambda tree: tree["checkpoint"]["account_state"]["positions"][0].update(
            {"average_cost": "101"}
        ),  # type: ignore[index]
        lambda tree: tree["checkpoint"]["metadata"][0].update({"value": "operator"}),  # type: ignore[index]
        lambda tree: tree["checkpoint"]["metadata"][0].update({"key": "origin"}),  # type: ignore[index]
    ),
)
def test_tampering_each_retained_field_or_identity_fails_strict_verification(
    mutate: object,
) -> None:
    payload = serialize_paper_account_checkpoint(
        create_genesis_paper_account_checkpoint(_request())
    )
    tree = _canonical_tree(payload)
    mutate(tree)  # type: ignore[operator]
    tampered = _canonical_bytes(tree)

    with pytest.raises(
        (PaperAccountCheckpointSchemaError, PaperAccountCheckpointSyntaxError)
    ):
        parse_paper_account_checkpoint(tampered)
    result = verify_genesis_paper_account_checkpoint(tampered)
    assert result.status is PaperAccountCheckpointVerificationStatus.FAIL
    assert result.checkpoint is None
    assert result.restored_ledger is None
    with pytest.raises(PaperAccountCheckpointReplayError):
        replay_verified_genesis_paper_account_checkpoint(result)


@pytest.mark.parametrize(
    "payload",
    (
        b"\xef\xbb\xbf{}",
        b"\xff",
        b'{"schema_version":1,"schema_version":1,"checkpoint":{}}',
        b'{"schema_version":1,"checkpoint":{}} trailing',
        b'{"schema_version":1.0,"checkpoint":{}}',
    ),
)
def test_strict_parser_rejects_noncanonical_or_invalid_json(payload: bytes) -> None:
    with pytest.raises(
        (PaperAccountCheckpointSchemaError, PaperAccountCheckpointSyntaxError)
    ):
        parse_paper_account_checkpoint(payload)


@pytest.mark.parametrize(
    "mutate",
    (
        lambda tree: tree["checkpoint"].update(  # type: ignore[index]
            {"checkpoint_id": tree["checkpoint"]["checkpoint_id"].upper()}  # type: ignore[index]
        ),
        lambda tree: tree["checkpoint"]["account_state"].update(  # type: ignore[index]
            {"as_of": "2026-02-03T04:05:06+00:00"}
        ),
        lambda tree: tree["checkpoint"]["account_state"].update(  # type: ignore[index]
            {"cash": "1000.0"}
        ),
        lambda tree: tree["checkpoint"]["account_state"]["positions"][0].update(  # type: ignore[index]
            {"symbol": "spy"}
        ),
        lambda tree: tree["checkpoint"].update({"sequence": "0"}),  # type: ignore[index]
    ),
)
def test_strict_parser_rejects_noncanonical_scalar_text(mutate: object) -> None:
    tree = _canonical_tree(
        serialize_paper_account_checkpoint(
            create_genesis_paper_account_checkpoint(_request())
        )
    )
    mutate(tree)  # type: ignore[operator]
    with pytest.raises(PaperAccountCheckpointSchemaError):
        parse_paper_account_checkpoint(_canonical_bytes(tree))
