"""Pure production-v1 vectors and hostile bundle inputs (no production data)."""

import json
import os
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from decimal import ROUND_DOWN, ROUND_UP, Decimal, localcontext
from hashlib import sha256
from uuid import UUID, uuid5

import pytest
from tests.market_data.daily_snapshot_test_support import accepted_result, calendar

from trading_bot.market_data import serialize_daily_snapshot, verify_daily_snapshot
from trading_bot.runtime.manual_paper_account_authority import (
    parse_manual_paper_account_anchor,
)
from trading_bot.runtime.manual_paper_account_provisioning import (
    ManualPaperAccountProvisioningBundle,
    ManualPaperAccountProvisioningError,
    build_manual_paper_account_provisioning_bundle,
    derive_manual_paper_account_id,
    parse_manual_paper_account_provisioning_manifest,
    serialize_manual_paper_account_provisioning_manifest,
    verify_manual_paper_account_provisioning_bundle,
)
from trading_bot.runtime.paper_account_checkpoint import (
    verify_genesis_paper_account_checkpoint,
)

MACHINE = "22222222-2222-5222-8222-222222222222"
SID = "S-1-5-21-1-2-3-1009"


def snapshot_result():
    return verify_daily_snapshot(
        serialize_daily_snapshot(accepted_result().snapshot), calendar()
    )


def make_bundle(**kwargs):
    inputs = dict(
        machine_authority_id=MACHINE,
        approved_trading_sid=SID,
        starting_cash=Decimal("1234.5600000000000000000000001"),
        snapshot_verification=snapshot_result(),
    )
    inputs.update(kwargs)
    return build_manual_paper_account_provisioning_bundle(**inputs)


def canonical(tree):
    return (json.dumps(tree, sort_keys=True, separators=(",", ":")) + "\n").encode()


def test_bundle_roundtrip_and_frozen_opening_shape():
    bundle = make_bundle()
    evidence = verify_manual_paper_account_provisioning_bundle(bundle)
    manifest = evidence.manifest
    assert str(manifest.paper_account_id) == "2075ac92-ab8a-5a56-b0d6-3e286d9a55d8"
    assert evidence.manifest_sha256 == sha256(bundle.manifest_bytes).hexdigest()
    assert (
        serialize_manual_paper_account_provisioning_manifest(manifest)
        == bundle.manifest_bytes
    )
    anchor = parse_manual_paper_account_anchor(bundle.anchor_bytes)
    genesis = verify_genesis_paper_account_checkpoint(bundle.genesis_bytes).checkpoint
    assert genesis.account_state.as_of == snapshot_result().snapshot.audit.captured_at
    assert genesis.account_state.positions == ()
    assert genesis.account_state.realized_profit_loss == Decimal("0")
    assert genesis.metadata == ()
    assert genesis.sequence == 0
    assert anchor.paper_account_id == manifest.paper_account_id
    parts = (
        "manual-paper-account-provisioning-id-v1",
        MACHINE,
        SID,
        str(genesis.checkpoint_id),
        sha256(bundle.genesis_bytes).hexdigest(),
        str(len(bundle.genesis_bytes)),
    )
    assert manifest.paper_account_id == uuid5(
        UUID("32a20ea3-acb3-556f-ac96-2518bbf52f01"),
        "".join(f"{len(p.encode('utf-8'))}:{p}" for p in parts),
    )
    with pytest.raises(FrozenInstanceError):
        bundle.genesis_bytes = b"other"


@pytest.mark.parametrize(
    "cash",
    [
        Decimal("0"),
        Decimal("-1"),
        Decimal("NaN"),
        Decimal("sNaN"),
        Decimal("Infinity"),
        1,
        1.2,
        "1234",
        True,
        None,
    ],
)
def test_bad_cash(cash):
    with pytest.raises(ManualPaperAccountProvisioningError):
        make_bundle(starting_cash=cash)


@pytest.mark.parametrize(
    "field,value",
    [
        ("positions", (1,)),
        ("realized_profit_loss", Decimal("1")),
        ("metadata", ("x",)),
        ("open_orders", (1,)),
        ("as_of", None),
        ("paper_account_id", UUID(int=1)),
        ("authority_epoch", UUID(int=1)),
        ("provider", "other"),
        ("credential_version", "v3"),
        ("selection_id", UUID(int=1)),
    ],
)
def test_no_opening_or_identity_overrides(field, value):
    with pytest.raises(TypeError):
        make_bundle(**{field: value})


def test_no_cash_default():
    with pytest.raises(TypeError):
        build_manual_paper_account_provisioning_bundle(
            machine_authority_id=MACHINE,
            approved_trading_sid=SID,
            snapshot_verification=snapshot_result(),
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("machine_authority_id", MACHINE.upper().replace("2", "A", 1)),
        ("machine_authority_id", "not-a-uuid"),
        ("machine_authority_id", UUID(MACHINE)),
        ("machine_authority_id", "{" + MACHINE + "}"),
        ("approved_trading_sid", "S-1-5-21-01-2-3-1009"),
        ("approved_trading_sid", "S-1-5-21-4294967296-2-3-1009"),
        ("approved_trading_sid", "S-1-5-32-544"),
        ("approved_trading_sid", SID + " "),
        ("approved_trading_sid", SID.lower()),
    ],
)
def test_invalid_principals(field, value):
    with pytest.raises(ManualPaperAccountProvisioningError):
        make_bundle(**{field: value})


@pytest.mark.parametrize(
    "mode", ["wrong_type", "fail", "hash", "length", "incomplete", "changed_snapshot"]
)
def test_snapshot_requires_complete_matching_pass(mode):
    result = snapshot_result()
    if mode == "wrong_type":
        result = object()
    elif mode == "fail":
        result = verify_daily_snapshot(b"{}", calendar())
    elif mode == "hash":
        result = replace(result, sha256="0" * 64)
    elif mode == "length":
        result = replace(result, byte_length=result.byte_length + 1)
    elif mode == "incomplete":
        object.__setattr__(result, "snapshot", None)
    else:
        # A changed timestamp without rederived identity is not verified proof.
        from datetime import timedelta

        audit = replace(
            result.snapshot.audit,
            captured_at=result.snapshot.audit.captured_at + timedelta(seconds=1),
        )
        object.__setattr__(result.snapshot, "audit", audit)
    with pytest.raises(ManualPaperAccountProvisioningError):
        make_bundle(snapshot_verification=result)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", "v2"),
        ("paper_account_id", str(UUID(int=1))),
        ("machine_authority_id", MACHINE.upper().replace("2", "A", 1)),
        ("approved_trading_sid", "S-1-5-21-01-2-3-4"),
        ("genesis_checkpoint_id", "bad"),
        ("genesis_sha256", "A" * 64),
        ("genesis_byte_length", True),
        ("genesis_byte_length", 0),
        ("anchor_sha256", "0" * 63),
        ("anchor_byte_length", -1),
        ("anchor_byte_length", 1.0),
        ("anchor_byte_length", "1"),
    ],
)
def test_manifest_fields_strict(field, value):
    tree = json.loads(make_bundle().manifest_bytes)
    tree[field] = value
    with pytest.raises(ManualPaperAccountProvisioningError):
        parse_manual_paper_account_provisioning_manifest(canonical(tree))


@pytest.mark.parametrize(
    "mode",
    [
        "duplicate",
        "unknown",
        "missing",
        "indent",
        "newline",
        "bom",
        "trailing",
        "utf8",
        "constant",
        "array",
        "overflow",
    ],
)
def test_manifest_syntax_strict(mode):
    payload = make_bundle().manifest_bytes
    tree = json.loads(payload)
    if mode == "duplicate":
        payload = payload.replace(b"{", b'{"schema":"duplicate",', 1)
    elif mode == "unknown":
        payload = canonical(dict(tree, extra=0))
    elif mode == "missing":
        del tree["schema"]
        payload = canonical(tree)
    elif mode == "indent":
        payload = json.dumps(tree, indent=2).encode()
    elif mode == "newline":
        payload = payload.rstrip()
    elif mode == "bom":
        payload = b"\xef\xbb\xbf" + payload
    elif mode == "trailing":
        payload += b"{}"
    elif mode == "utf8":
        payload = b"\xff"
    elif mode == "constant":
        payload = payload.replace(
            b'"anchor_byte_length":', b'"anchor_byte_length":NaN,"x":'
        )
    elif mode == "array":
        payload = b"[]\n"
    else:
        payload = b" " * 4097
    with pytest.raises(ManualPaperAccountProvisioningError):
        parse_manual_paper_account_provisioning_manifest(payload)


@pytest.mark.parametrize(
    "artifact", ["genesis_bytes", "anchor_bytes", "manifest_bytes"]
)
@pytest.mark.parametrize("mode", ["append", "other", "type"])
def test_bundle_rejects_modified_artifacts(artifact, mode):
    bundle = make_bundle()
    changed = (
        getattr(bundle, artifact) + b" "
        if mode == "append"
        else getattr(make_bundle(starting_cash=Decimal("10")), artifact)
        if mode == "other"
        else bytearray(getattr(bundle, artifact))
    )
    with pytest.raises(ManualPaperAccountProvisioningError):
        verify_manual_paper_account_provisioning_bundle(
            replace(bundle, **{artifact: changed})
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("machine_authority_id", str(UUID(int=3))),
        ("approved_trading_sid", "S-1-5-21-1-2-3-1010"),
        ("genesis_checkpoint_id", UUID(int=4)),
        ("genesis_sha256", "0" * 64),
        ("genesis_byte_length", 1),
    ],
)
def test_every_frozen_id_input_changes_identity(field, value):
    manifest = verify_manual_paper_account_provisioning_bundle(make_bundle()).manifest
    inputs = {
        name: getattr(manifest, name)
        for name in (
            "machine_authority_id",
            "approved_trading_sid",
            "genesis_checkpoint_id",
            "genesis_sha256",
            "genesis_byte_length",
        )
    }
    assert (
        derive_manual_paper_account_id(**(inputs | {field: value}))
        != manifest.paper_account_id
    )


def test_deterministic_under_decimal_environment_and_fresh_process(monkeypatch):
    expected = make_bundle()
    for precision, rounding in ((2, ROUND_DOWN), (50, ROUND_UP)):
        with localcontext() as context:
            context.prec = precision
            context.rounding = rounding
            monkeypatch.setenv("TZ", "Pacific/Honolulu")
            monkeypatch.setenv("LC_ALL", "C")
            monkeypatch.setenv("AUTHORITY_EPOCH", str(UUID(int=12)))
            assert make_bundle() == expected
    script = (
        "from tests.runtime.test_manual_paper_account_provisioning import make_bundle\n"
        "from hashlib import sha256\n"
        "b=make_bundle()\n"
        "print(*(sha256(x).hexdigest() for x in "
        "(b.genesis_bytes,b.anchor_bytes,b.manifest_bytes)))"
    )
    environment = dict(os.environ, PYTHONPATH="src", PYTHONHASHSEED="321")
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.stdout.strip() == " ".join(
        sha256(x).hexdigest()
        for x in (
            expected.genesis_bytes,
            expected.anchor_bytes,
            expected.manifest_bytes,
        )
    )


def test_bundle_transport_is_not_accepted_without_verification():
    with pytest.raises(ManualPaperAccountProvisioningError):
        verify_manual_paper_account_provisioning_bundle(
            ManualPaperAccountProvisioningBundle(b"x", b"x", b"x")
        )


@pytest.mark.parametrize("opening", ["positions", "realized", "metadata"])
def test_valid_a61_broader_opening_state_is_not_a_production_v1_bundle(opening):
    from trading_bot.domain import Symbol
    from trading_bot.portfolio import MetadataEntry
    from trading_bot.runtime.manual_paper_account_authority import (
        ManualPaperAccountAnchor,
        serialize_manual_paper_account_anchor,
    )
    from trading_bot.runtime.manual_paper_account_provisioning import (
        ManualPaperAccountProvisioningManifest,
    )
    from trading_bot.runtime.paper_account_checkpoint import (
        PaperAccountCheckpointPosition,
        PaperAccountGenesisRequest,
        create_genesis_paper_account_checkpoint,
        serialize_paper_account_checkpoint,
    )

    position = PaperAccountCheckpointPosition.from_exact_basis(
        Symbol("SPY"), Decimal("1"), Decimal("2")
    )
    checkpoint = create_genesis_paper_account_checkpoint(
        PaperAccountGenesisRequest(
            as_of=snapshot_result().snapshot.audit.captured_at,
            cash=Decimal("10"),
            positions=(position,) if opening == "positions" else (),
            realized_profit_loss=Decimal("1")
            if opening == "realized"
            else Decimal("0"),
            metadata=(MetadataEntry("note", "test"),) if opening == "metadata" else (),
        )
    )
    genesis = serialize_paper_account_checkpoint(checkpoint)
    assert verify_genesis_paper_account_checkpoint(genesis).status.value == "PASS"
    digest = sha256(genesis).hexdigest()
    account = derive_manual_paper_account_id(
        machine_authority_id=MACHINE,
        approved_trading_sid=SID,
        genesis_checkpoint_id=checkpoint.checkpoint_id,
        genesis_sha256=digest,
        genesis_byte_length=len(genesis),
    )
    anchor = serialize_manual_paper_account_anchor(
        ManualPaperAccountAnchor(
            account, MACHINE, SID, checkpoint.checkpoint_id, digest, len(genesis)
        )
    )
    manifest = serialize_manual_paper_account_provisioning_manifest(
        ManualPaperAccountProvisioningManifest(
            account,
            MACHINE,
            SID,
            checkpoint.checkpoint_id,
            digest,
            len(genesis),
            sha256(anchor).hexdigest(),
            len(anchor),
        )
    )
    with pytest.raises(
        ManualPaperAccountProvisioningError, match="OPENING_STATE_INVALID"
    ):
        verify_manual_paper_account_provisioning_bundle(
            ManualPaperAccountProvisioningBundle(genesis, anchor, manifest)
        )
