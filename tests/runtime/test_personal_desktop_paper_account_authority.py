"""Frozen PD1A identity vectors and strict closed anchor syntax."""

import json
from dataclasses import FrozenInstanceError, asdict, replace
from decimal import Decimal
from uuid import UUID, uuid5

import pytest

from trading_bot.runtime.personal_desktop_paper_account_authority import (
    PersonalDesktopPaperAccountAnchor,
    PersonalDesktopPaperAccountError,
    derive_personal_desktop_paper_account_id,
    parse_personal_desktop_paper_account_anchor,
    serialize_personal_desktop_paper_account_anchor,
)


@pytest.fixture
def anchor() -> PersonalDesktopPaperAccountAnchor:
    identity = dict(
        machine_authority_id="abcdefab-cdef-4abc-8def-abcdefabcdef",
        approved_trading_sid="S-1-5-21-1-2-3-1009",
        genesis_checkpoint_id="fedcbafe-dcba-5fed-8cba-fedcbafedcba",
        genesis_sha256="ab" * 32,
        genesis_byte_length=1234,
    )
    return PersonalDesktopPaperAccountAnchor(
        paper_account_id=derive_personal_desktop_paper_account_id(**identity),
        **identity,
    )


def canonical(tree: object) -> bytes:
    return (json.dumps(tree, sort_keys=True, separators=(",", ":")) + "\n").encode()


def test_frozen_namespace_and_ordered_framing(anchor) -> None:
    material = (
        "36:personal-desktop-paper-account-id-v1"
        "36:abcdefab-cdef-4abc-8def-abcdefabcdef"
        "19:S-1-5-21-1-2-3-1009"
        "36:fedcbafe-dcba-5fed-8cba-fedcbafedcba"
        "64:" + "ab" * 32 + "4:1234"
    )
    # Literal independent framing is intentionally not shared with production.
    expected = str(uuid5(UUID("022bbd87-6bea-5fd0-a323-5fa355616643"), material))
    assert anchor.paper_account_id == expected
    assert UUID(anchor.paper_account_id).version == 5


def test_exact_anchor_bytes_and_immutable_roundtrip(anchor) -> None:
    payload = serialize_personal_desktop_paper_account_anchor(anchor)
    assert payload == canonical(asdict(anchor))
    assert payload.endswith(b"\n") and not payload.endswith(b"\n\n")
    assert parse_personal_desktop_paper_account_anchor(payload) == anchor
    with pytest.raises(FrozenInstanceError):
        anchor.layout = "other"


@pytest.mark.parametrize(
    "field", tuple(PersonalDesktopPaperAccountAnchor.__dataclass_fields__)
)
def test_missing_or_duplicate_fields_rejected(anchor, field) -> None:
    tree = asdict(anchor)
    del tree[field]
    with pytest.raises(PersonalDesktopPaperAccountError):
        parse_personal_desktop_paper_account_anchor(canonical(tree))
    payload = serialize_personal_desktop_paper_account_anchor(anchor)
    duplicate = (
        b"{"
        + json.dumps(field).encode()
        + b":"
        + json.dumps(getattr(anchor, field)).encode()
        + b","
        + payload[1:]
    )
    with pytest.raises(PersonalDesktopPaperAccountError):
        parse_personal_desktop_paper_account_anchor(duplicate)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: b"\xef\xbb\xbf" + p,
        lambda p: p.rstrip(b"\n"),
        lambda p: p + b"\n",
        lambda p: p + b" ",
        lambda p: p + b"{}",
        lambda p: b" " + p,
        lambda p: p.replace(b":", b": "),
        lambda p: p.replace(b"schema", b"sch\\u0065ma"),
        lambda p: p.replace(b"1234", b"1.234e3"),
        lambda p: p.replace(b"1234", b"1234.0"),
        lambda p: p.replace(b"1234", b"01234"),
        lambda p: p.replace(b"1234", b"+1234"),
        lambda p: p.replace(b"1234", b"NaN"),
        lambda p: p.replace(b"1234", b"Infinity"),
        lambda p: p.replace(b"1234", b"-Infinity"),
        lambda p: p.replace(b"1234", b"-0"),
        lambda p: canonical({**json.loads(p), "path": "F:/elsewhere"}),
        lambda p: json.dumps(json.loads(p), indent=2).encode() + b"\n",
        lambda p: canonical(list(json.loads(p).items())),
        lambda p: b"\xff",
        lambda p: b"",
        lambda p: bytearray(p),
    ],
)
def test_noncanonical_json_rejected(anchor, mutation) -> None:
    with pytest.raises(PersonalDesktopPaperAccountError):
        parse_personal_desktop_paper_account_anchor(
            mutation(serialize_personal_desktop_paper_account_anchor(anchor))
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema", "personal-desktop-paper-account-authority/v2"),
        ("layout", "personal-desktop-paper-layout/v2"),
        ("approved_trading_sid", "s-1-5-21-1-2-3-1009"),
        ("approved_trading_sid", "S-1-5-21-01-2-3-1009"),
        ("approved_trading_sid", "Trading"),
        ("approved_trading_sid", "S-1-5-21-1-2-3-1010"),
        ("machine_authority_id", "abcdefab-cdef-4abc-8def-abcdefabcdee"),
        ("genesis_checkpoint_id", "fedcbafe-dcba-5fed-8cba-fedcbafedcbb"),
        ("genesis_sha256", "cd" * 32),
        ("genesis_sha256", "g" * 64),
        ("genesis_sha256", "ab" * 31),
        ("genesis_byte_length", 1235),
        ("genesis_byte_length", 0),
        ("genesis_byte_length", -1),
        ("genesis_byte_length", True),
        ("genesis_byte_length", "1234"),
        ("genesis_byte_length", 1234.0),
    ],
)
def test_invalid_values_and_identity_mismatch_rejected(anchor, field, value) -> None:
    with pytest.raises(PersonalDesktopPaperAccountError):
        replace(anchor, **{field: value})
    tree = {**asdict(anchor), field: value}
    with pytest.raises(PersonalDesktopPaperAccountError):
        parse_personal_desktop_paper_account_anchor(canonical(tree))


@pytest.mark.parametrize(
    "field",
    [
        "paper_account_id",
        "machine_authority_id",
        "genesis_checkpoint_id",
        "genesis_sha256",
    ],
)
@pytest.mark.parametrize(
    "transform",
    [
        str.upper,
        lambda s: s + "\n",
        lambda s: "{" + s + "}",
        lambda s: s.replace("-", ""),
        lambda s: "invalid",
    ],
)
def test_uuid_and_sha_text_is_canonical(anchor, field, transform) -> None:
    value = transform(getattr(anchor, field))
    if value == getattr(anchor, field):
        return
    with pytest.raises(PersonalDesktopPaperAccountError):
        parse_personal_desktop_paper_account_anchor(
            canonical({**asdict(anchor), field: value})
        )


def test_lengths_reject_decimal_and_ambient_values_cannot_enter_identity(
    anchor, monkeypatch
) -> None:
    identity = asdict(anchor)
    for key in ("paper_account_id", "schema", "layout"):
        del identity[key]
    for value in (Decimal("1234"), float("nan"), float("inf")):
        with pytest.raises(PersonalDesktopPaperAccountError):
            derive_personal_desktop_paper_account_id(
                **{**identity, "genesis_byte_length": value}
            )
    monkeypatch.setenv("PAPER_ROOT", "Z:/different/path")
    monkeypatch.setenv("STARTING_CASH", "1")
    assert (
        derive_personal_desktop_paper_account_id(**identity) == anchor.paper_account_id
    )
    for key in ("path", "timestamp", "pid", "selection_id", "credential_version"):
        with pytest.raises(TypeError):
            derive_personal_desktop_paper_account_id(**identity, **{key: "ambient"})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("machine_authority_id", "abcdefab-cdef-4abc-8def-abcdefabcdee"),
        ("approved_trading_sid", "S-1-5-21-1-2-3-1010"),
        ("genesis_checkpoint_id", "fedcbafe-dcba-5fed-8cba-fedcbafedcbb"),
        ("genesis_sha256", "cd" * 32),
        ("genesis_byte_length", 1235),
    ],
)
def test_every_identity_component_changes_account_id(anchor, field, value) -> None:
    identity = asdict(anchor)
    for key in ("paper_account_id", "schema", "layout"):
        del identity[key]
    assert (
        derive_personal_desktop_paper_account_id(**{**identity, field: value})
        != anchor.paper_account_id
    )
