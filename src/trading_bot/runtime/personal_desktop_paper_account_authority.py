"""Pure Architecture-103 v2 account identity and canonical authority anchor."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from uuid import UUID, uuid5

from trading_bot.runtime.windows_authority import WindowsAuthorityError

PERSONAL_DESKTOP_PAPER_ACCOUNT_AUTHORITY_SCHEMA = (
    "personal-desktop-paper-account-authority/v1"
)
PERSONAL_DESKTOP_PAPER_LAYOUT = "personal-desktop-paper-layout/v1"
PERSONAL_DESKTOP_PAPER_ACCOUNT_NAMESPACE = UUID("022bbd87-6bea-5fd0-a323-5fa355616643")

_FIELDS = frozenset(
    {
        "schema",
        "layout",
        "paper_account_id",
        "machine_authority_id",
        "approved_trading_sid",
        "genesis_checkpoint_id",
        "genesis_sha256",
        "genesis_byte_length",
    }
)
_SID = re.compile(r"S-(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*))+")
_SHA256 = re.compile(r"[0-9a-f]{64}")


class PersonalDesktopPaperAccountError(WindowsAuthorityError, ValueError):
    """V2 identity, canonical bytes, or offline evidence failed reconciliation."""


def _uuid_text(value: object, field: str) -> str:
    if type(value) is not str:
        raise PersonalDesktopPaperAccountError(f"{field} must be canonical UUID text")
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise PersonalDesktopPaperAccountError(f"{field} must be a UUID") from error
    if str(parsed) != value:
        raise PersonalDesktopPaperAccountError(f"{field} must be lowercase UUID text")
    return value


def derive_personal_desktop_paper_account_id(
    *,
    machine_authority_id: str,
    approved_trading_sid: str,
    genesis_checkpoint_id: str,
    genesis_sha256: str,
    genesis_byte_length: int,
) -> str:
    """Derive UUID5 from the six ordered, UTF-8 byte-length-framed v1 parts."""

    _uuid_text(machine_authority_id, "machine_authority_id")
    _uuid_text(genesis_checkpoint_id, "genesis_checkpoint_id")
    if (
        type(approved_trading_sid) is not str
        or _SID.fullmatch(approved_trading_sid) is None
    ):
        raise PersonalDesktopPaperAccountError("approved_trading_sid must be canonical")
    if type(genesis_sha256) is not str or _SHA256.fullmatch(genesis_sha256) is None:
        raise PersonalDesktopPaperAccountError(
            "genesis_sha256 must be lowercase SHA-256"
        )
    if type(genesis_byte_length) is not int or genesis_byte_length <= 0:
        raise PersonalDesktopPaperAccountError(
            "genesis_byte_length must be positive int"
        )
    parts = (
        "personal-desktop-paper-account-id-v1",
        machine_authority_id,
        approved_trading_sid,
        genesis_checkpoint_id,
        genesis_sha256,
        str(genesis_byte_length),
    )
    framed = "".join(f"{len(part.encode('utf-8'))}:{part}" for part in parts)
    return str(uuid5(PERSONAL_DESKTOP_PAPER_ACCOUNT_NAMESPACE, framed))


@dataclass(frozen=True, slots=True)
class PersonalDesktopPaperAccountAnchor:
    """Closed immutable v2 identity evidence; it grants no runtime authority."""

    paper_account_id: str
    machine_authority_id: str
    approved_trading_sid: str
    genesis_checkpoint_id: str
    genesis_sha256: str
    genesis_byte_length: int
    schema: str = PERSONAL_DESKTOP_PAPER_ACCOUNT_AUTHORITY_SCHEMA
    layout: str = PERSONAL_DESKTOP_PAPER_LAYOUT

    def __post_init__(self) -> None:
        if (
            type(self.schema) is not str
            or self.schema != PERSONAL_DESKTOP_PAPER_ACCOUNT_AUTHORITY_SCHEMA
            or type(self.layout) is not str
            or self.layout != PERSONAL_DESKTOP_PAPER_LAYOUT
        ):
            raise PersonalDesktopPaperAccountError(
                "unsupported anchor schema or layout"
            )
        _uuid_text(self.paper_account_id, "paper_account_id")
        expected = derive_personal_desktop_paper_account_id(
            machine_authority_id=self.machine_authority_id,
            approved_trading_sid=self.approved_trading_sid,
            genesis_checkpoint_id=self.genesis_checkpoint_id,
            genesis_sha256=self.genesis_sha256,
            genesis_byte_length=self.genesis_byte_length,
        )
        if self.paper_account_id != expected:
            raise PersonalDesktopPaperAccountError(
                "paper_account_id does not reconcile"
            )


def canonical_personal_desktop_paper_json(tree: dict[str, object]) -> bytes:
    """Encode shared v2 anchor/manifest canonical JSON, including its final newline."""

    return (
        json.dumps(
            tree,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _unique_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    fields: dict[str, object] = {}
    for key, value in pairs:
        if key in fields:
            raise PersonalDesktopPaperAccountError("duplicate JSON field")
        fields[key] = value
    return fields


def _reject_number(value: str) -> object:
    raise PersonalDesktopPaperAccountError("float or non-finite JSON number")


def parse_personal_desktop_paper_json(
    payload: bytes, *, fields: frozenset[str]
) -> dict[str, object]:
    """Parse shared closed v2 JSON syntax; callers validate every field's semantics."""

    if type(payload) is not bytes or not payload or payload.startswith(b"\xef\xbb\xbf"):
        raise PersonalDesktopPaperAccountError(
            "expected nonempty UTF-8 bytes without BOM"
        )
    try:
        tree = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_fields,
            parse_float=_reject_number,
            parse_constant=_reject_number,
        )
        if type(tree) is not dict or tree.keys() != fields:
            raise PersonalDesktopPaperAccountError("JSON fields are not exact")
        if canonical_personal_desktop_paper_json(tree) != payload:
            raise PersonalDesktopPaperAccountError("JSON bytes are not canonical")
    except (UnicodeError, ValueError, RecursionError) as error:
        raise PersonalDesktopPaperAccountError("invalid canonical v2 JSON") from error
    return tree


def serialize_personal_desktop_paper_account_anchor(
    anchor: PersonalDesktopPaperAccountAnchor,
) -> bytes:
    """Validate and serialize exactly the frozen anchor fields."""

    if type(anchor) is not PersonalDesktopPaperAccountAnchor:
        raise PersonalDesktopPaperAccountError("expected exact v2 anchor")
    anchor.__post_init__()
    return canonical_personal_desktop_paper_json(asdict(anchor))


def parse_personal_desktop_paper_account_anchor(
    payload: bytes,
) -> PersonalDesktopPaperAccountAnchor:
    """Reject malformed, noncanonical, or identity-inconsistent anchor bytes."""

    return PersonalDesktopPaperAccountAnchor(
        **parse_personal_desktop_paper_json(payload, fields=_FIELDS)
    )
