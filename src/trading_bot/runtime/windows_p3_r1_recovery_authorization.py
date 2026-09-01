"""Signed authority for the one frozen Architecture-96 P3-R1 recovery.

The signed document is transport evidence until this module verifies its
dedicated domain, reconciles the exact operator/C1/installed release, and
issues a process-local permit.  It is deliberately not a generic action token.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import re
import sys
import threading
import weakref
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from uuid import UUID

from trading_bot.runtime.windows_authority import (
    PRODUCTION_PINNED_BOOTSTRAP_KEYS,
    PinnedBootstrapKeyRegistry,
    WindowsAuthorityError,
    require_windows_platform,
    verify_p256_p1363_sha256_signature,
)
from trading_bot.runtime.windows_authority_security import (
    require_administrator_token,
    resolve_current_token_sid,
)
from trading_bot.runtime.windows_authority_validation import (
    require_initialized_supported_authority_evidence,
    validate_installed_authority_complete,
)

RECOVERY_AUTHORIZATION_DOMAIN = b"ai-trading-bot/p3-r1-recovery-authorization/v1"
RECOVERY_AUTHORIZATION_SCHEMA = "p3-r1-recovery-authorization/v1"
RECOVERY_SIGNING_KEY_ID = "AITradingBot/Authority/Bootstrap/v1"

_MACHINE_AUTHORITY_ID = "223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1"
_APPROVED_TRADING_SID = "S-1-5-21-1397534616-3988210162-180023805-1009"
_PAPER_ACCOUNT_ID = "d1510a4b-6ebf-58ef-92a4-e743ca91151e"
_GENESIS_CHECKPOINT_ID = "7b7b83ba-69e2-5ed8-a033-b4306cd1ffc7"
_BOOTSTRAP_SHA256 = "53b8b72ab18b1c477c5eab50857e4dc2d47efc6e74030e380ed6a53387922ae4"
_AUTHORITY_DATABASE_SHA256 = (
    "6a8fb988d1cb223fbb66b09e8dab1e0de4b6aafd148dfdf01df08029203f4b76"
)
_AUTHORITY_DATABASE_BYTES = 331776
_STAGING_ROOT = r"F:\AITradingBot\.Paper.provisioning-v1"
_FINAL_ROOT = r"F:\AITradingBot\Paper"
_RUNTIME = PureWindowsPath(r"F:\AITradingBot\runtime")
_SITE_PACKAGES = _RUNTIME / "Lib" / "site-packages"
_PACKAGE_ROOT = _SITE_PACKAGES / "trading_bot"
_RECORD_NAME = "ai_trading_bot-0.1.0.dist-info/RECORD"

_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_OPERATOR_SID = re.compile(r"^S-1-5-21-(?:[1-9][0-9]*-){3}[1-9][0-9]*$")
_WINDOWS_RESERVED_NAME = re.compile(
    r"^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$", re.IGNORECASE
)
_FIELDS = frozenset(
    {
        "administrator_operator_sid",
        "approved_trading_sid",
        "authority_database_bytes",
        "authority_database_sha256",
        "bootstrap_sha256",
        "final_root",
        "genesis_checkpoint_id",
        "installed_record_bytes",
        "installed_record_sha256",
        "machine_authority_id",
        "paper_account_id",
        "schema",
        "signing_key_id",
        "source_commit",
        "source_tree",
        "staging_root",
        "wheel_bytes",
        "wheel_sha256",
    }
)


class P3R1RecoveryAuthorizationError(WindowsAuthorityError, ValueError):
    """Base class for rejected Architecture-96 recovery authorization."""


class P3R1RecoveryAuthorizationSyntaxError(P3R1RecoveryAuthorizationError):
    """The authorization is not strict canonical JSON."""


class P3R1RecoveryAuthorizationSchemaError(P3R1RecoveryAuthorizationError):
    """The authorization field set or a field value is not exact."""


class P3R1RecoveryAuthorizationSignatureError(P3R1RecoveryAuthorizationError):
    """The dedicated detached signature is malformed or invalid."""


class P3R1RecoveryPermitError(P3R1RecoveryAuthorizationError):
    """A recovery permit lacks exact process-local provenance."""


def _duplicate_rejector(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise P3R1RecoveryAuthorizationSyntaxError(
                "recovery authorization contains duplicate keys"
            )
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise P3R1RecoveryAuthorizationSyntaxError(
        f"recovery authorization contains invalid numeric constant: {value}"
    )


def _strict_json(data: bytes) -> dict[str, object]:
    if type(data) is not bytes:
        raise P3R1RecoveryAuthorizationSyntaxError(
            "recovery authorization input must be bytes"
        )
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise P3R1RecoveryAuthorizationSyntaxError(
            "recovery authorization is not UTF-8"
        ) from error
    if text.startswith("\ufeff"):
        raise P3R1RecoveryAuthorizationSyntaxError(
            "recovery authorization must not contain a UTF-8 BOM"
        )
    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_duplicate_rejector,
            parse_constant=_reject_constant,
        )
    except P3R1RecoveryAuthorizationSyntaxError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise P3R1RecoveryAuthorizationSyntaxError(
            "recovery authorization is not valid JSON"
        ) from error
    if type(parsed) is not dict:
        raise P3R1RecoveryAuthorizationSchemaError(
            "recovery authorization root must be an object"
        )
    return parsed


def _text(value: object, field: str) -> str:
    if type(value) is not str or not value:
        raise P3R1RecoveryAuthorizationSchemaError(
            f"recovery authorization field {field} must be non-empty text"
        )
    return value


def _canonical_uuid(value: object, field: str) -> str:
    text = _text(value, field)
    try:
        parsed = UUID(text)
    except (ValueError, AttributeError) as error:
        raise P3R1RecoveryAuthorizationSchemaError(
            f"recovery authorization field {field} must be a UUID"
        ) from error
    if str(parsed) != text:
        raise P3R1RecoveryAuthorizationSchemaError(
            f"recovery authorization field {field} is not canonical"
        )
    return text


def _positive_int(value: object, field: str, maximum: int) -> int:
    if type(value) is not int or not 0 < value <= maximum:
        raise P3R1RecoveryAuthorizationSchemaError(
            f"recovery authorization field {field} is not a bounded positive integer"
        )
    return value


@dataclass(frozen=True, slots=True)
class P3R1RecoveryAuthorization:
    """Exact secret-free signed facts for the frozen P3-R1 incident."""

    schema: str
    signing_key_id: str
    machine_authority_id: str
    approved_trading_sid: str
    administrator_operator_sid: str
    paper_account_id: str
    genesis_checkpoint_id: str
    bootstrap_sha256: str
    authority_database_sha256: str
    authority_database_bytes: int
    source_commit: str
    source_tree: str
    wheel_sha256: str
    wheel_bytes: int
    installed_record_sha256: str
    installed_record_bytes: int
    staging_root: str
    final_root: str

    def __post_init__(self) -> None:
        exact = {
            "schema": RECOVERY_AUTHORIZATION_SCHEMA,
            "signing_key_id": RECOVERY_SIGNING_KEY_ID,
            "machine_authority_id": _MACHINE_AUTHORITY_ID,
            "approved_trading_sid": _APPROVED_TRADING_SID,
            "paper_account_id": _PAPER_ACCOUNT_ID,
            "genesis_checkpoint_id": _GENESIS_CHECKPOINT_ID,
            "bootstrap_sha256": _BOOTSTRAP_SHA256,
            "authority_database_sha256": _AUTHORITY_DATABASE_SHA256,
            "authority_database_bytes": _AUTHORITY_DATABASE_BYTES,
            "staging_root": _STAGING_ROOT,
            "final_root": _FINAL_ROOT,
        }
        for field, expected in exact.items():
            if getattr(self, field) != expected:
                raise P3R1RecoveryAuthorizationSchemaError(
                    "recovery authorization field "
                    f"{field} is not the frozen incident value"
                )
        _canonical_uuid(self.machine_authority_id, "machine_authority_id")
        _canonical_uuid(self.paper_account_id, "paper_account_id")
        _canonical_uuid(self.genesis_checkpoint_id, "genesis_checkpoint_id")
        if (
            type(self.administrator_operator_sid) is not str
            or _OPERATOR_SID.fullmatch(self.administrator_operator_sid) is None
        ):
            raise P3R1RecoveryAuthorizationSchemaError(
                "administrator_operator_sid is not canonical"
            )
        for field in (
            "bootstrap_sha256",
            "authority_database_sha256",
            "wheel_sha256",
            "installed_record_sha256",
        ):
            if (
                type(getattr(self, field)) is not str
                or _HEX_64.fullmatch(getattr(self, field)) is None
            ):
                raise P3R1RecoveryAuthorizationSchemaError(
                    f"recovery authorization field {field} is not lowercase SHA-256"
                )
        for field in ("source_commit", "source_tree"):
            if (
                type(getattr(self, field)) is not str
                or _HEX_40.fullmatch(getattr(self, field)) is None
            ):
                raise P3R1RecoveryAuthorizationSchemaError(
                    "recovery authorization field "
                    f"{field} is not lowercase Git identity"
                )
        _positive_int(self.authority_database_bytes, "authority_database_bytes", 2**31)
        _positive_int(self.wheel_bytes, "wheel_bytes", 2**31)
        _positive_int(
            self.installed_record_bytes, "installed_record_bytes", 16 * 1024 * 1024
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "administrator_operator_sid": self.administrator_operator_sid,
            "approved_trading_sid": self.approved_trading_sid,
            "authority_database_bytes": self.authority_database_bytes,
            "authority_database_sha256": self.authority_database_sha256,
            "bootstrap_sha256": self.bootstrap_sha256,
            "final_root": self.final_root,
            "genesis_checkpoint_id": self.genesis_checkpoint_id,
            "installed_record_bytes": self.installed_record_bytes,
            "installed_record_sha256": self.installed_record_sha256,
            "machine_authority_id": self.machine_authority_id,
            "paper_account_id": self.paper_account_id,
            "schema": self.schema,
            "signing_key_id": self.signing_key_id,
            "source_commit": self.source_commit,
            "source_tree": self.source_tree,
            "staging_root": self.staging_root,
            "wheel_bytes": self.wheel_bytes,
            "wheel_sha256": self.wheel_sha256,
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")


def parse_p3_r1_recovery_authorization(data: bytes) -> P3R1RecoveryAuthorization:
    """Parse only the exact canonical Architecture-96 authorization bytes."""

    values = _strict_json(data)
    if frozenset(values) != _FIELDS:
        raise P3R1RecoveryAuthorizationSchemaError(
            "recovery authorization field set is not exact"
        )
    authorization = P3R1RecoveryAuthorization(
        schema=_text(values["schema"], "schema"),
        signing_key_id=_text(values["signing_key_id"], "signing_key_id"),
        machine_authority_id=_canonical_uuid(
            values["machine_authority_id"], "machine_authority_id"
        ),
        approved_trading_sid=_text(
            values["approved_trading_sid"], "approved_trading_sid"
        ),
        administrator_operator_sid=_text(
            values["administrator_operator_sid"], "administrator_operator_sid"
        ),
        paper_account_id=_canonical_uuid(
            values["paper_account_id"], "paper_account_id"
        ),
        genesis_checkpoint_id=_canonical_uuid(
            values["genesis_checkpoint_id"], "genesis_checkpoint_id"
        ),
        bootstrap_sha256=_text(values["bootstrap_sha256"], "bootstrap_sha256"),
        authority_database_sha256=_text(
            values["authority_database_sha256"], "authority_database_sha256"
        ),
        authority_database_bytes=_positive_int(
            values["authority_database_bytes"], "authority_database_bytes", 2**31
        ),
        source_commit=_text(values["source_commit"], "source_commit"),
        source_tree=_text(values["source_tree"], "source_tree"),
        wheel_sha256=_text(values["wheel_sha256"], "wheel_sha256"),
        wheel_bytes=_positive_int(values["wheel_bytes"], "wheel_bytes", 2**31),
        installed_record_sha256=_text(
            values["installed_record_sha256"], "installed_record_sha256"
        ),
        installed_record_bytes=_positive_int(
            values["installed_record_bytes"],
            "installed_record_bytes",
            16 * 1024 * 1024,
        ),
        staging_root=_text(values["staging_root"], "staging_root"),
        final_root=_text(values["final_root"], "final_root"),
    )
    if authorization.canonical_bytes() != data:
        raise P3R1RecoveryAuthorizationSyntaxError(
            "recovery authorization bytes are not canonical"
        )
    return authorization


def p3_r1_recovery_signing_preimage(authorization_bytes: bytes) -> bytes:
    """Return the exact length-framed Architecture-96 signing preimage."""

    if type(authorization_bytes) is not bytes:
        raise P3R1RecoveryAuthorizationSyntaxError(
            "recovery authorization input must be bytes"
        )
    return (
        len(RECOVERY_AUTHORIZATION_DOMAIN).to_bytes(2, "big")
        + RECOVERY_AUTHORIZATION_DOMAIN
        + len(authorization_bytes).to_bytes(8, "big")
        + authorization_bytes
    )


@dataclass(frozen=True, slots=True)
class P3R1RecoveryAuthorizationVerification:
    authorization: P3R1RecoveryAuthorization
    authorization_sha256: str
    signing_key_id: str
    signature_length: int


def verify_p3_r1_recovery_authorization(
    authorization_bytes: bytes,
    signature: bytes,
    *,
    key_registry: PinnedBootstrapKeyRegistry = PRODUCTION_PINNED_BOOTSTRAP_KEYS,
) -> P3R1RecoveryAuthorizationVerification:
    """Verify the dedicated domain with the source-pinned C1 public key."""

    require_windows_platform()
    authorization = parse_p3_r1_recovery_authorization(authorization_bytes)
    if type(signature) is not bytes or len(signature) != 64:
        raise P3R1RecoveryAuthorizationSignatureError(
            "recovery authorization signature must be exactly 64 bytes"
        )
    try:
        key = key_registry.get(authorization.signing_key_id)
        verify_p256_p1363_sha256_signature(
            key.public_key,
            p3_r1_recovery_signing_preimage(authorization_bytes),
            signature,
        )
    except WindowsAuthorityError:
        raise P3R1RecoveryAuthorizationSignatureError(
            "recovery authorization signature verification failed"
        ) from None
    return P3R1RecoveryAuthorizationVerification(
        authorization,
        hashlib.sha256(authorization_bytes).hexdigest(),
        key.key_id,
        len(signature),
    )


class P3R1RecoveryPermit:
    """Sealed, immutable, process-local Architecture-96 recovery authority."""

    __slots__ = ("__weakref__",)

    def __init__(self, *, _issuer: object | None = None) -> None:
        if _issuer is not _PERMIT_ISSUER:
            raise TypeError("P3-R1 recovery permits are issued by Architecture 96")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("P3R1RecoveryPermit cannot be subclassed")

    def __copy__(self) -> object:
        raise TypeError("P3-R1 recovery permits cannot be copied")

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError("P3-R1 recovery permits cannot be deep-copied")

    def __reduce__(self) -> object:
        raise TypeError("P3-R1 recovery permits cannot be serialized")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("P3-R1 recovery permits cannot be pickled")

    def __getstate__(self) -> object:
        raise TypeError("P3-R1 recovery permits cannot be serialized")

    def __repr__(self) -> str:
        return "P3R1RecoveryPermit(<sealed>)"


@dataclass(frozen=True, slots=True)
class _PermitBinding:
    authorization: P3R1RecoveryAuthorization
    authorization_sha256: str
    provenance: object


_PERMIT_ISSUER = object()
_PRODUCTION_PROVENANCE = object()
_DISPOSABLE_TEST_PROVENANCE = object()
_PERMITS: weakref.WeakKeyDictionary[P3R1RecoveryPermit, _PermitBinding] = (
    weakref.WeakKeyDictionary()
)
_ATTEMPTED_AUTHORIZATIONS: set[str] = set()
_PERMIT_LOCK = threading.Lock()


def _issue_permit(
    verification: P3R1RecoveryAuthorizationVerification, provenance: object
) -> P3R1RecoveryPermit:
    with _PERMIT_LOCK:
        if (
            provenance is _PRODUCTION_PROVENANCE
            and verification.authorization_sha256 in _ATTEMPTED_AUTHORIZATIONS
        ):
            raise P3R1RecoveryPermitError(
                "recovery authorization was already admitted in this process"
            )
        permit = P3R1RecoveryPermit(_issuer=_PERMIT_ISSUER)
        _PERMITS[permit] = _PermitBinding(
            verification.authorization,
            verification.authorization_sha256,
            provenance,
        )
        if provenance is _PRODUCTION_PROVENANCE:
            _ATTEMPTED_AUTHORIZATIONS.add(verification.authorization_sha256)
    return permit


def require_p3_r1_recovery_permit(
    permit: P3R1RecoveryPermit,
) -> P3R1RecoveryAuthorization:
    """Require exact unconsumed production verification provenance."""

    if type(permit) is not P3R1RecoveryPermit:
        raise P3R1RecoveryPermitError("P3-R1 recovery permit type is invalid")
    with _PERMIT_LOCK:
        binding = _PERMITS.get(permit)
        if binding is None or binding.provenance is not _PRODUCTION_PROVENANCE:
            raise P3R1RecoveryPermitError("P3-R1 recovery permit provenance is invalid")
        return binding.authorization


def consume_p3_r1_recovery_permit(
    permit: P3R1RecoveryPermit,
) -> P3R1RecoveryAuthorization:
    """Consume the exact production permit at the native mutation boundary."""

    authorization = require_p3_r1_recovery_permit(permit)
    with _PERMIT_LOCK:
        binding = _PERMITS.pop(permit, None)
        if binding is None or binding.authorization is not authorization:
            raise P3R1RecoveryPermitError("P3-R1 recovery permit was already consumed")
    return authorization


def issue_disposable_p3_r1_recovery_permit_for_test(
    authorization: P3R1RecoveryAuthorization,
) -> P3R1RecoveryPermit:
    """Issue explicitly non-production provenance for fake-native tests only."""

    if type(authorization) is not P3R1RecoveryAuthorization:
        raise P3R1RecoveryPermitError("disposable authorization type is invalid")
    verification = P3R1RecoveryAuthorizationVerification(
        authorization,
        hashlib.sha256(authorization.canonical_bytes()).hexdigest(),
        authorization.signing_key_id,
        64,
    )
    return _issue_permit(verification, _DISPOSABLE_TEST_PROVENANCE)


def consume_disposable_p3_r1_recovery_permit_for_test(
    permit: P3R1RecoveryPermit,
) -> P3R1RecoveryAuthorization:
    """Consume only explicitly disposable test provenance."""

    if type(permit) is not P3R1RecoveryPermit:
        raise P3R1RecoveryPermitError("disposable permit type is invalid")
    with _PERMIT_LOCK:
        binding = _PERMITS.pop(permit, None)
        if binding is None or binding.provenance is not _DISPOSABLE_TEST_PROVENANCE:
            raise P3R1RecoveryPermitError("disposable permit provenance is invalid")
    return binding.authorization


def _enumerate_installed_package_payloads() -> set[str]:
    root = Path(str(_PACKAGE_ROOT))
    site_packages = Path(str(_SITE_PACKAGES))
    payloads: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise P3R1RecoveryAuthorizationError(
                "installed recovery package contains a link"
            )
        if path.is_file():
            payloads.add(path.relative_to(site_packages).as_posix())
    return payloads


def _read_and_reconcile_installed_release(
    authorization: P3R1RecoveryAuthorization,
) -> None:
    record_path = Path(str(_SITE_PACKAGES / _RECORD_NAME))
    record = record_path.read_bytes()
    if (hashlib.sha256(record).hexdigest(), len(record)) != (
        authorization.installed_record_sha256,
        authorization.installed_record_bytes,
    ):
        raise P3R1RecoveryAuthorizationError("installed RECORD identity mismatches")
    try:
        text = record.decode("utf-8", errors="strict")
        rows = tuple(csv.reader(io.StringIO(text), strict=True))
    except (UnicodeDecodeError, csv.Error) as error:
        raise P3R1RecoveryAuthorizationError("installed RECORD is malformed") from error
    names: set[str] = set()
    windows_names: set[str] = set()
    hashed: set[str] = set()
    for row in rows:
        if len(row) != 3:
            raise P3R1RecoveryAuthorizationError("installed RECORD row is malformed")
        name, digest, length = row
        relative = PurePosixPath(name)
        windows_name = name.casefold()
        if (
            not name
            or name in names
            or windows_name in windows_names
            or name != relative.as_posix()
            or relative.is_absolute()
            or any(part in {".", ".."} for part in relative.parts)
            or any(part.endswith((" ", ".")) for part in relative.parts)
            or any(_WINDOWS_RESERVED_NAME.fullmatch(part) for part in relative.parts)
            or any(char in name for char in "\\:*")
            or any(ord(char) < 0x20 for char in name)
        ):
            raise P3R1RecoveryAuthorizationError("installed RECORD path is unsafe")
        names.add(name)
        windows_names.add(windows_name)
        if name == _RECORD_NAME and (digest or length):
            raise P3R1RecoveryAuthorizationError(
                "installed RECORD self-entry must be unhashed"
            )
        if not digest:
            if length or (
                name.startswith("trading_bot/") and not name.endswith(".pyc")
            ):
                raise P3R1RecoveryAuthorizationError(
                    "installed recovery payload is unhashed"
                )
            continue
        if re.fullmatch(r"sha256=[A-Za-z0-9_-]{43}", digest) is None:
            raise P3R1RecoveryAuthorizationError("installed RECORD digest is invalid")
        payload = Path(str(_SITE_PACKAGES.joinpath(*relative.parts))).read_bytes()
        actual = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=")
        if digest != "sha256=" + actual.decode("ascii") or length != str(len(payload)):
            raise P3R1RecoveryAuthorizationError(
                "installed recovery payload mismatches RECORD"
            )
        hashed.add(name)
    if _RECORD_NAME not in names:
        raise P3R1RecoveryAuthorizationError("installed RECORD does not list itself")
    installed = {
        name
        for name in _enumerate_installed_package_payloads()
        if not name.endswith(".pyc")
    }
    if installed != {name for name in hashed if name.startswith("trading_bot/")}:
        raise P3R1RecoveryAuthorizationError(
            "installed recovery package inventory mismatches RECORD"
        )
    for name, module in tuple(sys.modules.items()):
        if name == "trading_bot" or name.startswith("trading_bot."):
            source = PureWindowsPath(getattr(module, "__file__", ""))
            if not source.is_relative_to(_SITE_PACKAGES):
                raise P3R1RecoveryAuthorizationError(
                    "loaded trading_bot module is outside the sealed release"
                )
            if source.relative_to(_SITE_PACKAGES).as_posix() not in hashed:
                raise P3R1RecoveryAuthorizationError(
                    "loaded trading_bot module is not a hashed release payload"
                )


def _require_sealed_recovery_runtime() -> None:
    if sys.executable != str(_RUNTIME / "python.exe") or str(
        PureWindowsPath(__file__)
    ) != str(
        _SITE_PACKAGES / "trading_bot/runtime/windows_p3_r1_recovery_authorization.py"
    ):
        raise P3R1RecoveryAuthorizationError("sealed recovery runtime is not exact")


def authorize_p3_r1_recovery(
    authorization_bytes: bytes, signature: bytes
) -> P3R1RecoveryPermit:
    """Verify all pre-staging Architecture-96 gates and issue one permit."""

    require_windows_platform()
    require_administrator_token()
    verification = verify_p3_r1_recovery_authorization(authorization_bytes, signature)
    authorization = verification.authorization
    if resolve_current_token_sid() != authorization.administrator_operator_sid:
        raise P3R1RecoveryAuthorizationError(
            "current token SID does not match signed recovery operator"
        )
    _require_sealed_recovery_runtime()
    validation = validate_installed_authority_complete()
    require_initialized_supported_authority_evidence(validation)
    bootstrap_verification = validation.bootstrap_verification
    bootstrap = bootstrap_verification.bootstrap
    if (
        bootstrap.machine_authority_id != authorization.machine_authority_id
        or bootstrap.approved_account_sid != authorization.approved_trading_sid
        or bootstrap_verification.bootstrap_digest != authorization.bootstrap_sha256
    ):
        raise P3R1RecoveryAuthorizationError(
            "installed C1 does not match signed recovery authorization"
        )
    _read_and_reconcile_installed_release(authorization)
    return _issue_permit(verification, _PRODUCTION_PROVENANCE)
