"""Focused deterministic lineage-head record and pointer coverage."""

from __future__ import annotations

import json
from hashlib import sha256
from uuid import UUID

import pytest

from trading_bot.runtime import (
    LineageHeadAdvancementCauseEvidence,
    LineageHeadAdvancementCauseKind,
    LineageHeadTerminalCheckpointEvidence,
    LineageManifestEvidence,
    LocalLineageHeadReference,
    LocalLineageHeadSchemaError,
    LocalLineageHeadSyntaxError,
    create_paper_account_lineage_head_record,
    parse_local_lineage_head_reference,
    parse_paper_account_lineage_head_record,
    serialize_local_lineage_head_reference,
    serialize_paper_account_lineage_head_record,
)

EPOCH_ID = UUID("11111111-1111-5111-8111-111111111111")
LINEAGE_EVIDENCE_ID = UUID("22222222-2222-5222-8222-222222222222")
CHECKPOINT_ID = UUID("33333333-3333-5333-8333-333333333333")


def _record():
    terminal = LineageHeadTerminalCheckpointEvidence(
        CHECKPOINT_ID,
        "a" * 64,
        123,
        0,
    )
    return create_paper_account_lineage_head_record(
        EPOCH_ID,
        0,
        None,
        LineageManifestEvidence(
            LINEAGE_EVIDENCE_ID,
            "b" * 64,
            456,
        ),
        LINEAGE_EVIDENCE_ID,
        terminal,
        LineageHeadAdvancementCauseKind.GENESIS,
        LineageHeadAdvancementCauseEvidence(
            CHECKPOINT_ID,
            "a" * 64,
            123,
        ),
    )


def test_reviewed_head_record_golden_identity_and_bytes() -> None:
    record = _record()
    payload = serialize_paper_account_lineage_head_record(record)

    assert str(record.record_id) == "cf2712b4-0ba3-5b12-ae6e-aa0cdc9f0ca9"
    assert len(payload) == 799
    assert (
        sha256(payload).hexdigest()
        == "b0935a1f64f8be1bde1825c87d43a66dfe48871599feeedc93fa7927fe7e9afa"
    )
    assert parse_paper_account_lineage_head_record(payload) == record


def test_head_record_identity_has_no_path_input() -> None:
    first = _record()
    second = _record()

    assert first == second
    assert serialize_paper_account_lineage_head_record(first) == (
        serialize_paper_account_lineage_head_record(second)
    )


def test_pointer_canonical_round_trip() -> None:
    payload = serialize_paper_account_lineage_head_record(_record())
    reference = LocalLineageHeadReference(
        1,
        EPOCH_ID,
        0,
        _record().record_id,
        sha256(payload).hexdigest(),
        len(payload),
    )

    serialized = serialize_local_lineage_head_reference(reference)

    assert serialized.endswith(b"\n")
    assert parse_local_lineage_head_reference(serialized) == reference


@pytest.mark.parametrize(
    "mutation",
    (
        lambda tree: tree.update({"unknown": True}),
        lambda tree: tree.pop("record_id"),
        lambda tree: tree.update({"generation": 0.0}),
        lambda tree: tree.update({"record_id": str(_record().record_id).upper()}),
    ),
)
def test_head_record_rejects_unknown_missing_float_and_noncanonical_values(
    mutation,
) -> None:
    tree = json.loads(serialize_paper_account_lineage_head_record(_record()))
    mutation(tree)
    payload = (json.dumps(tree, sort_keys=True, separators=(",", ":")) + "\n").encode()

    with pytest.raises((LocalLineageHeadSchemaError, LocalLineageHeadSyntaxError)):
        parse_paper_account_lineage_head_record(payload)


def test_head_record_rejects_duplicate_fields_and_constants() -> None:
    payload = serialize_paper_account_lineage_head_record(_record())
    duplicate = payload.replace(
        b'{"advancement_cause":',
        b'{"schema_version":1,"advancement_cause":',
        1,
    )
    constant = payload.replace(b'"generation":0', b'"generation":NaN', 1)

    with pytest.raises(LocalLineageHeadSchemaError):
        parse_paper_account_lineage_head_record(duplicate)
    with pytest.raises(LocalLineageHeadSchemaError):
        parse_paper_account_lineage_head_record(constant)


def test_head_record_rejects_semantic_genesis_mismatch() -> None:
    tree = json.loads(serialize_paper_account_lineage_head_record(_record()))
    tree["advancement_cause"]["artifact_id"] = "44444444-4444-5444-8444-444444444444"
    payload = (json.dumps(tree, sort_keys=True, separators=(",", ":")) + "\n").encode()

    with pytest.raises(LocalLineageHeadSchemaError):
        parse_paper_account_lineage_head_record(payload)
