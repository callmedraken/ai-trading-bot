"""Offline PD1A bundles, exact Architecture-61 reuse, and retained P2 provenance."""

import builtins
import gc
import inspect
import json
import os
import socket
import sqlite3
import time
import uuid
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from decimal import Context, Decimal, localcontext
from hashlib import sha256
from pathlib import Path

import pytest

import trading_bot.runtime.personal_desktop_paper_account_provisioning as provisioning
from trading_bot.domain import Symbol
from trading_bot.market_data import ALPACA_DAILY_SNAPSHOT_DESCRIPTOR
from trading_bot.portfolio import MetadataEntry
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    SelectedC3SnapshotPermit,
    require_selected_c3_snapshot_permit,
)
from trading_bot.runtime.paper_account_checkpoint import (
    PaperAccountCheckpointPosition,
    PaperAccountGenesisRequest,
    create_genesis_paper_account_checkpoint,
    parse_paper_account_checkpoint,
    serialize_paper_account_checkpoint,
)
from trading_bot.runtime.personal_desktop_paper_account_authority import (
    PersonalDesktopPaperAccountAnchor,
    PersonalDesktopPaperAccountError,
    derive_personal_desktop_paper_account_id,
    parse_personal_desktop_paper_account_anchor,
    serialize_personal_desktop_paper_account_anchor,
)
from trading_bot.runtime.personal_desktop_paper_account_provisioning import (
    PersonalDesktopPaperAccountBundle,
    PersonalDesktopPaperAccountProvisioningManifest,
    parse_personal_desktop_paper_account_manifest,
    prepare_personal_desktop_paper_account_bundle,
    prepare_personal_desktop_paper_account_bundle_for_test,
    serialize_personal_desktop_paper_account_manifest,
    verify_personal_desktop_paper_account_bundle,
    verify_personal_desktop_paper_account_bundle_for_test,
)
from trading_bot.runtime.windows_authority import (
    WindowsAuthorityBootstrap,
    WindowsAuthorityError,
)
from trading_bot.runtime.windows_authority_schema import (
    PRODUCTION_SCHEMA_ARTIFACT_SHA256,
    PRODUCTION_SCHEMA_ID,
    PRODUCTION_SCHEMA_VERSION,
    ProductionAuthorityEvidence,
)
from trading_bot.runtime.windows_authority_validation import (
    issue_validated_production_authority_for_test,
)

from .test_manual_paper_selected_c3_snapshot import selected_case as selected_case


def canonical(tree: object) -> bytes:
    return (json.dumps(tree, sort_keys=True, separators=(",", ":")) + "\n").encode()


@pytest.fixture
def inputs(selected_case):
    # Public C1 test issuer and genuine full disposable P2 read; no forged permit.
    bootstrap = WindowsAuthorityBootstrap(
        bootstrap_schema=1,
        bootstrap_generation=1,
        machine_authority_id="22222222-2222-4222-8222-222222222222",
        authority_epoch_id="11111111-1111-4111-8111-111111111111",
        signing_key_id="test-key/v1",
        approved_account_sid="S-1-5-21-1-2-3-1009",
        database_path=r"F:\AITradingBot\Authority\authority.sqlite3",
        output_root=r"F:\AITradingBot\Authority\capture-output",
        provider_id=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id,
        permitted_provider_operation=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation,
        authority_policy_version="authority-policy/v1",
        claim_policy_version="claim-policy/v1",
        database_identity_digest="64" * 32,
    )
    evidence = ProductionAuthorityEvidence(
        database_path=str(selected_case.database),
        schema_id=PRODUCTION_SCHEMA_ID,
        schema_version=PRODUCTION_SCHEMA_VERSION,
        schema_digest=PRODUCTION_SCHEMA_ARTIFACT_SHA256,
        metadata_digest="33" * 32,
        migration_id="migration/v1",
        release_manifest_digest="44" * 32,
        sqlite_build_manifest_digest="55" * 32,
    )
    return dict(
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap.digest,
        production_evidence=evidence,
        selected_snapshot=selected_case.authority.read_selected_snapshot(
            selected_case.ids["selection_id"]
        ),
        starting_cash=Decimal("12345.67"),
    )


@pytest.fixture(scope="module")
def bundle():
    # Parser cases need only fixed bytes, not a database per malformed input.
    genesis = create_genesis_paper_account_checkpoint(
        PaperAccountGenesisRequest(
            datetime(2026, 8, 29, 12, 0, 1, tzinfo=UTC),
            Decimal("12345.67"),
            (),
            Decimal("0"),
        )
    )
    genesis_bytes = serialize_paper_account_checkpoint(genesis)
    identity = dict(
        machine_authority_id="22222222-2222-4222-8222-222222222222",
        approved_trading_sid="S-1-5-21-1-2-3-1009",
        genesis_checkpoint_id=str(genesis.checkpoint_id),
        genesis_sha256=sha256(genesis_bytes).hexdigest(),
        genesis_byte_length=len(genesis_bytes),
    )
    common = dict(
        paper_account_id=derive_personal_desktop_paper_account_id(**identity),
        **identity,
    )
    anchor_bytes = canonical(
        dict(
            schema="personal-desktop-paper-account-authority/v1",
            layout="personal-desktop-paper-layout/v1",
            **common,
        )
    )
    manifest_bytes = canonical(
        dict(
            schema="personal-desktop-paper-account-provisioning/v1",
            **common,
            anchor_sha256=sha256(anchor_bytes).hexdigest(),
            anchor_byte_length=len(anchor_bytes),
        )
    )
    return PersonalDesktopPaperAccountBundle(
        genesis_bytes, anchor_bytes, manifest_bytes
    )


def test_preparation_exactly_reuses_a61_and_retains_immutable_bytes(
    inputs, bundle
) -> None:
    assert prepare_personal_desktop_paper_account_bundle_for_test(**inputs) == bundle
    captured_at = inputs["selected_snapshot"].verification.snapshot.audit.captured_at
    expected = create_genesis_paper_account_checkpoint(
        PaperAccountGenesisRequest(
            as_of=captured_at,
            cash=inputs["starting_cash"],
            positions=(),
            realized_profit_loss=Decimal("0"),
            open_orders=(),
            metadata=(),
        )
    )
    assert bundle.genesis_bytes == serialize_paper_account_checkpoint(expected)
    assert parse_paper_account_checkpoint(bundle.genesis_bytes) == expected
    assert expected.account_state.as_of == captured_at
    assert expected.account_state.cash == inputs["starting_cash"]
    assert expected.account_state.positions == expected.metadata == ()
    assert expected.account_state.realized_profit_loss == Decimal("0")
    manifest = parse_personal_desktop_paper_account_manifest(bundle.manifest_bytes)
    anchor = parse_personal_desktop_paper_account_anchor(bundle.anchor_bytes)
    assert manifest.anchor() == anchor
    assert manifest.genesis_checkpoint_id == str(expected.checkpoint_id)
    assert manifest.genesis_sha256 == sha256(bundle.genesis_bytes).hexdigest()
    assert manifest.genesis_byte_length == len(bundle.genesis_bytes)
    assert manifest.anchor_sha256 == sha256(bundle.anchor_bytes).hexdigest()
    assert manifest.anchor_byte_length == len(bundle.anchor_bytes)
    assert (
        serialize_personal_desktop_paper_account_manifest(manifest)
        == bundle.manifest_bytes
    )
    verify_personal_desktop_paper_account_bundle_for_test(bundle, **inputs)
    for value, field in ((bundle, "genesis_bytes"), (manifest, "anchor_sha256")):
        with pytest.raises(FrozenInstanceError):
            setattr(value, field, b"changed")


@pytest.mark.parametrize("precision", [1, 6, 28, 80])
def test_preparation_is_decimal_context_independent(inputs, bundle, precision) -> None:
    with localcontext(Context(prec=precision, Emin=-9, Emax=9)):
        assert (
            prepare_personal_desktop_paper_account_bundle_for_test(**inputs) == bundle
        )


@pytest.mark.parametrize(
    "cash",
    [
        Decimal("0"),
        Decimal("-0"),
        Decimal("-1"),
        Decimal("NaN"),
        Decimal("sNaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
        100,
        100.0,
        True,
        "100",
        None,
    ],
)
def test_starting_cash_is_explicit_positive_finite_decimal(inputs, cash) -> None:
    with pytest.raises(PersonalDesktopPaperAccountError):
        prepare_personal_desktop_paper_account_bundle_for_test(
            **{**inputs, "starting_cash": cash}
        )


def test_no_default_cash_or_caller_opening_state(inputs) -> None:
    for function in (
        prepare_personal_desktop_paper_account_bundle,
        prepare_personal_desktop_paper_account_bundle_for_test,
        verify_personal_desktop_paper_account_bundle,
        verify_personal_desktop_paper_account_bundle_for_test,
    ):
        assert (
            inspect.signature(function).parameters["starting_cash"].default
            is inspect.Parameter.empty
        )
    missing = {k: v for k, v in inputs.items() if k != "starting_cash"}
    with pytest.raises(TypeError, match="starting_cash"):
        prepare_personal_desktop_paper_account_bundle_for_test(**missing)
    for field in (
        "as_of",
        "captured_at",
        "positions",
        "realized_profit_loss",
        "metadata",
        "open_orders",
        "path",
    ):
        with pytest.raises(TypeError):
            prepare_personal_desktop_paper_account_bundle_for_test(
                **inputs, **{field: "caller override"}
            )


@pytest.mark.parametrize(
    "field", tuple(PersonalDesktopPaperAccountProvisioningManifest.__dataclass_fields__)
)
def test_manifest_closed_missing_duplicate_fields(bundle, field) -> None:
    tree = json.loads(bundle.manifest_bytes)
    value = tree.pop(field)
    with pytest.raises(PersonalDesktopPaperAccountError):
        parse_personal_desktop_paper_account_manifest(canonical(tree))
    duplicate = (
        b"{"
        + json.dumps(field).encode()
        + b":"
        + json.dumps(value).encode()
        + b","
        + bundle.manifest_bytes[1:]
    )
    with pytest.raises(PersonalDesktopPaperAccountError):
        parse_personal_desktop_paper_account_manifest(duplicate)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: b"\xef\xbb\xbf" + p,
        lambda p: p[:-1],
        lambda p: p + b"\n",
        lambda p: p + b" ",
        lambda p: p + b"{}",
        lambda p: p.replace(b":", b": "),
        lambda p: p.replace(b"schema", b"sch\\u0065ma"),
        lambda p: canonical({**json.loads(p), "layout": "unexpected"}),
        lambda p: canonical([]),
        lambda p: b"\xff",
        lambda p: bytearray(p),
    ],
)
def test_manifest_noncanonical_syntax(bundle, mutation) -> None:
    with pytest.raises(PersonalDesktopPaperAccountError):
        parse_personal_desktop_paper_account_manifest(mutation(bundle.manifest_bytes))


@pytest.mark.parametrize("field", ["genesis_byte_length", "anchor_byte_length"])
@pytest.mark.parametrize(
    "token",
    [
        b"0",
        b"-1",
        b"-0",
        b"1.0",
        b"1e3",
        b"NaN",
        b"Infinity",
        b"-Infinity",
        b"true",
        b'"100"',
        b"null",
        b"010",
        b"+10",
    ],
)
def test_manifest_invalid_numbers(bundle, field, token) -> None:
    tree = json.loads(bundle.manifest_bytes)
    original = f'"{field}":{tree[field]}'.encode()
    payload = bundle.manifest_bytes.replace(original, f'"{field}":'.encode() + token)
    with pytest.raises(PersonalDesktopPaperAccountError):
        parse_personal_desktop_paper_account_manifest(payload)


@pytest.mark.parametrize(
    "field",
    [
        "paper_account_id",
        "machine_authority_id",
        "genesis_checkpoint_id",
        "genesis_sha256",
        "anchor_sha256",
    ],
)
def test_manifest_malformed_and_uppercase_identities(bundle, field) -> None:
    tree = json.loads(bundle.manifest_bytes)
    for value in ("bad", "ABCDEFAB-CDEF-4ABC-8DEF-ABCDEFABCDEF", "AB" * 32, None, 12):
        with pytest.raises(PersonalDesktopPaperAccountError):
            parse_personal_desktop_paper_account_manifest(
                canonical({**tree, field: value})
            )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema", "wrong/v1"),
        ("approved_trading_sid", "Trading"),
        ("approved_trading_sid", "S-1-5-21-1-2-3-1010"),
    ],
)
def test_manifest_wrong_schema_or_sid(bundle, field, value) -> None:
    with pytest.raises(PersonalDesktopPaperAccountError):
        parse_personal_desktop_paper_account_manifest(
            canonical({**json.loads(bundle.manifest_bytes), field: value})
        )


@pytest.mark.parametrize(
    "field",
    [
        "paper_account_id",
        "machine_authority_id",
        "approved_trading_sid",
        "genesis_checkpoint_id",
        "genesis_sha256",
        "genesis_byte_length",
        "anchor_sha256",
        "anchor_byte_length",
    ],
)
def test_changed_manifest_evidence_fails_reconciliation(bundle, field) -> None:
    tree = json.loads(bundle.manifest_bytes)
    value = tree[field]
    tree[field] = (
        value + 1
        if type(value) is int
        else (
            "S-1-5-21-1-2-3-1010"
            if field == "approved_trading_sid"
            else "cd" * 32
            if "sha256" in field
            else "abcdefab-cdef-4abc-8def-abcdefabcdef"
        )
    )
    with pytest.raises(PersonalDesktopPaperAccountError):
        replace(bundle, manifest_bytes=canonical(tree))


@pytest.mark.parametrize("field", ["genesis_bytes", "anchor_bytes", "manifest_bytes"])
def test_bundle_rejects_byte_corruption(bundle, field) -> None:
    with pytest.raises(PersonalDesktopPaperAccountError):
        replace(bundle, **{field: getattr(bundle, field) + b"\n"})


def rebuilt_bundle(bundle, genesis_bytes=None, **identity_changes):
    """Attack helper: rehash all artifacts so only contextual/policy checks catch it."""
    original = parse_personal_desktop_paper_account_anchor(bundle.anchor_bytes)
    payload = bundle.genesis_bytes if genesis_bytes is None else genesis_bytes
    genesis = parse_paper_account_checkpoint(payload)
    identity = dict(
        machine_authority_id=original.machine_authority_id,
        approved_trading_sid=original.approved_trading_sid,
        genesis_checkpoint_id=str(genesis.checkpoint_id),
        genesis_sha256=sha256(payload).hexdigest(),
        genesis_byte_length=len(payload),
    )
    identity.update(identity_changes)
    anchor = PersonalDesktopPaperAccountAnchor(
        paper_account_id=derive_personal_desktop_paper_account_id(**identity),
        **identity,
    )
    anchor_bytes = serialize_personal_desktop_paper_account_anchor(anchor)
    manifest = PersonalDesktopPaperAccountProvisioningManifest(
        paper_account_id=anchor.paper_account_id,
        **identity,
        anchor_sha256=sha256(anchor_bytes).hexdigest(),
        anchor_byte_length=len(anchor_bytes),
    )
    return PersonalDesktopPaperAccountBundle(
        payload,
        anchor_bytes,
        serialize_personal_desktop_paper_account_manifest(manifest),
    )


@pytest.mark.parametrize("change", ["positions", "realized_profit_loss", "metadata"])
def test_rehashed_non_cash_opening_state_rejected(inputs, bundle, change) -> None:
    request = PaperAccountGenesisRequest(
        inputs["selected_snapshot"].verification.snapshot.audit.captured_at,
        inputs["starting_cash"],
        (),
        Decimal("0"),
    )
    values = dict(
        positions=(
            PaperAccountCheckpointPosition.from_exact_basis(
                Symbol("AAPL"), Decimal("1"), Decimal("100")
            ),
        ),
        realized_profit_loss=Decimal("1"),
        metadata=(MetadataEntry("source", "caller"),),
    )
    genesis_bytes = serialize_paper_account_checkpoint(
        create_genesis_paper_account_checkpoint(
            replace(request, **{change: values[change]})
        )
    )
    with pytest.raises(PersonalDesktopPaperAccountError, match="cash-only"):
        rebuilt_bundle(bundle, genesis_bytes)


@pytest.mark.parametrize(
    "change", ["as_of", "cash", "machine_authority_id", "approved_trading_sid"]
)
def test_rehashed_contextual_bundle_substitution_rejected(
    inputs, bundle, change
) -> None:
    if change in ("as_of", "cash"):
        request = PaperAccountGenesisRequest(
            inputs["selected_snapshot"].verification.snapshot.audit.captured_at,
            inputs["starting_cash"],
            (),
            Decimal("0"),
        )
        value = (
            request.as_of + timedelta(seconds=1)
            if change == "as_of"
            else Decimal("999")
        )
        changed = rebuilt_bundle(
            bundle,
            serialize_paper_account_checkpoint(
                create_genesis_paper_account_checkpoint(
                    replace(request, **{change: value})
                )
            ),
        )
    else:
        value = (
            "abcdefab-cdef-4abc-8def-abcdefabcdef"
            if change == "machine_authority_id"
            else "S-1-5-21-1-2-3-1010"
        )
        changed = rebuilt_bundle(bundle, **{change: value})
    with pytest.raises(PersonalDesktopPaperAccountError, match="C1/P2/opening"):
        verify_personal_desktop_paper_account_bundle_for_test(changed, **inputs)


@pytest.mark.parametrize(
    "field", ["machine_authority_id", "approved_account_sid", "authority_epoch_id"]
)
def test_c1_and_p2_must_match(inputs, field) -> None:
    value = (
        "S-1-5-21-1-2-3-1010"
        if field == "approved_account_sid"
        else "abcdefab-cdef-4abc-8def-abcdefabcdef"
    )
    bootstrap = replace(inputs["bootstrap"], **{field: value})
    with pytest.raises(WindowsAuthorityError, match="identity mismatch"):
        prepare_personal_desktop_paper_account_bundle_for_test(
            **{**inputs, "bootstrap": bootstrap, "bootstrap_digest": bootstrap.digest}
        )


def test_c1_invalid_evidence_rejected(inputs) -> None:
    with pytest.raises(WindowsAuthorityError):
        prepare_personal_desktop_paper_account_bundle_for_test(
            **{**inputs, "bootstrap_digest": "aa" * 32}
        )
    with pytest.raises(WindowsAuthorityError):
        prepare_personal_desktop_paper_account_bundle_for_test(
            **{
                **inputs,
                "production_evidence": replace(
                    inputs["production_evidence"], schema_version=999
                ),
            }
        )


def test_disposable_inputs_never_pass_production_boundary(inputs, bundle) -> None:
    selected = inputs["selected_snapshot"]
    authority = issue_validated_production_authority_for_test(
        **{
            k: inputs[k]
            for k in ("bootstrap", "bootstrap_digest", "production_evidence")
        }
    )
    with pytest.raises(WindowsAuthorityError, match="provenance"):
        require_selected_c3_snapshot_permit(selected.permit, selected.audit)
    for c1 in (authority, object(), inputs["bootstrap"]):
        with pytest.raises(WindowsAuthorityError):
            prepare_personal_desktop_paper_account_bundle(
                authority=c1,
                selected_snapshot=selected,
                starting_cash=inputs["starting_cash"],
            )
        with pytest.raises(WindowsAuthorityError):
            verify_personal_desktop_paper_account_bundle(
                bundle,
                authority=c1,
                selected_snapshot=selected,
                starting_cash=inputs["starting_cash"],
            )


def test_forged_permit_or_substituted_audit_cannot_prepare(inputs) -> None:
    selected = inputs["selected_snapshot"]
    forged = object.__new__(SelectedC3SnapshotPermit)
    for changed in (
        replace(selected, permit=forged),
        replace(selected, audit=replace(selected.audit)),
    ):
        with pytest.raises(WindowsAuthorityError, match="provenance"):
            prepare_personal_desktop_paper_account_bundle_for_test(
                **{**inputs, "selected_snapshot": changed}
            )
    with pytest.raises(TypeError):
        SelectedC3SnapshotPermit()
    with pytest.raises(PersonalDesktopPaperAccountError):
        prepare_personal_desktop_paper_account_bundle_for_test(
            **{**inputs, "selected_snapshot": object()}
        )


@pytest.mark.parametrize(
    "field",
    [
        "snapshot_bytes",
        "verification",
        "provider_call_performed",
        "database_mutation_performed",
    ],
)
def test_tampered_p2_result_fails_closed(inputs, field) -> None:
    selected = inputs["selected_snapshot"]
    changed = replace(selected)
    value = (
        selected.snapshot_bytes + b"\n"
        if field == "snapshot_bytes"
        else None
        if field == "verification"
        else True
    )
    object.__setattr__(changed, field, value)
    with pytest.raises(WindowsAuthorityError):
        prepare_personal_desktop_paper_account_bundle_for_test(
            **{**inputs, "selected_snapshot": changed}
        )


def test_preparation_independently_verifies_snapshot(inputs, monkeypatch) -> None:
    calls = []
    real_verify = provisioning.verify_daily_snapshot

    def verify(payload, calendar, **kwargs):
        calls.append(payload)
        return real_verify(payload, calendar, **kwargs)

    monkeypatch.setattr(provisioning, "verify_daily_snapshot", verify)
    prepare_personal_desktop_paper_account_bundle_for_test(**inputs)
    assert calls == [inputs["selected_snapshot"].snapshot_bytes]


def test_preparation_has_no_io_or_ambient_identity_dependency(
    inputs, bundle, selected_case, monkeypatch
) -> None:
    # Warmed verified P2 fixtures precede the pure boundary under test.
    def forbidden(*args, **kwargs):
        pytest.fail("pure preparation attempted an external or ambient operation")

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbidden)
        patch.setattr(Path, "open", forbidden)
        patch.setattr(Path, "write_bytes", forbidden)
        patch.setattr(Path, "write_text", forbidden)
        patch.setattr(os, "getenv", forbidden)
        patch.setattr(os, "getpid", forbidden)
        patch.setattr(os, "getcwd", forbidden)
        patch.setattr(time, "time", forbidden)
        patch.setattr(uuid, "uuid4", forbidden)
        patch.setattr(socket, "socket", forbidden)
        patch.setattr(sqlite3, "connect", forbidden)
        patch.setattr(selected_case.api, "open_final_artifact", forbidden)
        assert (
            prepare_personal_desktop_paper_account_bundle_for_test(**inputs) == bundle
        )
    # Database location and release metadata are test transport/deployment facts.
    evidence = replace(
        inputs["production_evidence"],
        database_path="Z:/elsewhere/db.sqlite3",
        release_manifest_digest="77" * 32,
    )
    monkeypatch.setenv("PAPER_ROOT", "Z:/caller-selected")
    assert (
        prepare_personal_desktop_paper_account_bundle_for_test(
            **{**inputs, "production_evidence": evidence}
        )
        == bundle
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("genesis_checkpoint_id", "abcdefab-cdef-4abc-8def-abcdefabcdef"),
        ("genesis_sha256", "cd" * 32),
        ("genesis_byte_length", 1),
    ],
)
def test_rehashed_anchor_cannot_misdescribe_genesis(bundle, field, value) -> None:
    with pytest.raises(PersonalDesktopPaperAccountError, match="GENESIS"):
        rebuilt_bundle(bundle, **{field: value})


def test_genesis_open_order_material_is_rejected(bundle) -> None:
    tree = json.loads(bundle.genesis_bytes)
    tree["checkpoint"]["open_orders"] = [{"symbol": "AAPL"}]
    with pytest.raises(ValueError):
        rebuilt_bundle(bundle, canonical(tree))


def test_expired_p2_reader_cannot_prepare(inputs, selected_case) -> None:
    del selected_case.authority
    gc.collect()
    with pytest.raises(WindowsAuthorityError, match="provenance"):
        prepare_personal_desktop_paper_account_bundle_for_test(**inputs)
