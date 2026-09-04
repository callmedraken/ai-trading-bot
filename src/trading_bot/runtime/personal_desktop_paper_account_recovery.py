"""FR2 read-only qualification of the fixed retained v2 staging tree.

Returned facts are historical observations, never a capability, retry permit,
or authorization for a later recovery effect. No recovery effects exist here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from hashlib import sha256

from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime.personal_desktop_paper_account_authority import (
    PersonalDesktopPaperAccountAnchor,
    PersonalDesktopPaperAccountError,
    parse_personal_desktop_paper_account_anchor,
)
from trading_bot.runtime.personal_desktop_paper_account_provisioning import (
    PersonalDesktopPaperAccountBundle,
    PersonalDesktopPaperAccountProvisioningManifest,
    serialize_personal_desktop_paper_account_manifest,
)
from trading_bot.runtime.personal_desktop_paper_account_publication import (
    PaperPublicationState,
    paper_publication_layout,
    require_paper_publication_administrator,
)
from trading_bot.runtime.personal_desktop_paper_account_publication_freeze import (
    PersonalDesktopPaperPublicationFreeze,
    require_production_paper_publication_freeze,
    verify_personal_desktop_paper_publication_freeze,
)
from trading_bot.runtime.personal_desktop_paper_account_token import (
    WindowsTradingTokenObserver,
)
from trading_bot.runtime.windows_authority import (
    AuthorityObjectError,
    AuthorityPathError,
    require_windows_platform,
)
from trading_bot.runtime.windows_authority_validation import (
    InstalledAuthorityValidation,
    require_initialized_supported_authority_evidence,
    validate_installed_authority_complete,
)

_ROOT = security.PERSONAL_DESKTOP_PAPER_V2_STAGING_ROOT
_ANCHOR = _ROOT + r"\personal-desktop-paper-account-authority.json"
_PARENT = security.PERSONAL_DESKTOP_PAPER_PARENT


@dataclass(frozen=True, slots=True)
class PersonalDesktopPaperStagingRecoveryQualification:
    """Immutable reporting evidence only; no consumer may treat it as authority."""

    paper_account_id: str
    genesis_checkpoint_id: str
    machine_authority_id: str
    approved_trading_sid: str
    starting_cash: Decimal
    genesis_as_of: datetime
    anchor_sha256: str
    anchor_byte_length: int
    genesis_sha256: str
    genesis_byte_length: int
    manifest_sha256: str
    manifest_byte_length: int
    objects: tuple[tuple[str, security.PaperObjectObservation], ...]
    v2_state: PaperPublicationState
    v1_final_present: bool
    v1_historical_staging_present: bool


class _RecoveryPaths:
    """Only the fixed anchor can bind the two GENESIS names for this interval."""

    def __init__(self) -> None:
        self._specs = {
            path: security.paper_object_spec(path) for path in ("F:\\", _PARENT)
        }
        self._specs[_ROOT] = security.paper_object_spec(
            security.PERSONAL_DESKTOP_PAPER_V2_ROOT
        )
        self._specs[_ANCHOR] = security.paper_object_spec(
            security.PERSONAL_DESKTOP_PAPER_V2_ANCHOR
        )
        self._bound = False

    def object_spec(self, path: str) -> security.PaperObjectSpec:
        if type(path) is not str or path not in self._specs:
            raise AuthorityPathError("path is outside the exact recovery read layout")
        return self._specs[path]

    def bind(self, anchor: PersonalDesktopPaperAccountAnchor) -> tuple[str, ...]:
        if self._bound or type(anchor) is not PersonalDesktopPaperAccountAnchor:
            raise AuthorityPathError("recovery anchor binding cannot be replaced")
        anchor.__post_init__()
        paths = []
        for entry in paper_publication_layout(anchor.genesis_checkpoint_id):
            path = _ROOT + ("\\" + entry.relative if entry.relative else "")
            self._specs[path] = entry.spec
            paths.append(path)
        self._bound = True
        return tuple(paths)


class _WindowsRecoveryReadApi(security.WindowsPaperReadNativeApi):
    """Reuse OPEN_EXISTING/no-follow mechanics with separate staging admission."""

    def __init__(self, paths: _RecoveryPaths) -> None:
        super().__init__()
        self._paths = paths

    def object_spec(self, path: str) -> security.PaperObjectSpec:
        return self._paths.object_spec(path)


class _RecoveryReadSession(security.PinnedPaperReadSession):
    """All ordinary strict drift checks apply, including parent size/link facts."""

    def __init__(
        self, api: security.PaperReadNativeApi, sid: str, paths: _RecoveryPaths
    ) -> None:
        super().__init__(api, sid)
        self._paths = paths

    def object_spec(self, path: str) -> security.PaperObjectSpec:
        return self._paths.object_spec(path)


def _require_disarmed() -> None:
    if security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is not False:
        raise PersonalDesktopPaperAccountError(
            "recovery qualification requires production publication disarmed"
        )


def _administrator(
    freeze: PersonalDesktopPaperPublicationFreeze,
) -> InstalledAuthorityValidation:
    require_windows_platform()
    require_paper_publication_administrator(WindowsTradingTokenObserver().observe())
    validation = validate_installed_authority_complete()
    require_initialized_supported_authority_evidence(validation)
    bootstrap = validation.bootstrap_verification.bootstrap
    if (
        bootstrap.machine_authority_id != freeze.machine_authority_id
        or bootstrap.approved_account_sid != freeze.approved_trading_sid
    ):
        raise PersonalDesktopPaperAccountError("recovery C1 differs from source freeze")
    return validation


def _require_occupancy(session: _RecoveryReadSession) -> None:
    names = session.names(_PARENT)
    # Reject Windows aliases even when they refer to otherwise unrelated siblings.
    if any(name.endswith((".", " ")) or "~" in name for name in names):
        raise AuthorityPathError("unsafe recovery parent inventory")
    expected = {".Paper.provisioning-v1", ".Paper-v2.provisioning"}
    governed = {"Paper", "Paper-v2", *expected}
    present = {
        name for name in names if name.casefold() in {n.casefold() for n in governed}
    }
    if present != expected:
        raise AuthorityObjectError("recovery requires exact frozen v1/v2 occupancy")


def _require_digest(payload: bytes, digest: str, length: int) -> None:
    if len(payload) != length or sha256(payload).hexdigest() != digest:
        raise PersonalDesktopPaperAccountError("staged bytes differ from source freeze")


def qualify_personal_desktop_paper_staging_recovery() -> (
    PersonalDesktopPaperStagingRecoveryQualification
):
    """Independently qualify current fixed staging; accepts no caller authority.

    No handles, runtime capability, bundle, or effect permit escape this call.
    Every failure raises, including final interval/close failures.
    """
    _require_disarmed()  # First gate, before any token/C1/native reader construction.
    freeze = require_production_paper_publication_freeze()
    validation = _administrator(freeze)
    paths = _RecoveryPaths()
    api = _WindowsRecoveryReadApi(paths)
    with _RecoveryReadSession(api, freeze.approved_trading_sid, paths) as session:
        _require_occupancy(session)
        session.finish()  # Trust occupancy before opening the retained tree.
        session.pin(_ROOT)
        anchor_bytes = session.read(_ANCHOR)
        anchor = parse_personal_desktop_paper_account_anchor(anchor_bytes)
        _require_digest(anchor_bytes, freeze.anchor_sha256, freeze.anchor_byte_length)
        staged_paths = paths.bind(anchor)
        _, _, genesis_directory, genesis_path, runtime, operations = staged_paths
        expected_names = {
            _ROOT: {
                _ANCHOR.rsplit("\\", 1)[1],
                genesis_directory.rsplit("\\", 1)[1],
                "runtime",
            },
            genesis_directory: {genesis_path.rsplit("\\", 1)[1]},
            runtime: {"paper-operations"},
            operations: set(),
        }
        for path, expected in expected_names.items():
            if set(session.names(path)) != expected:
                raise AuthorityObjectError("recovery staging layout is not exact")
        genesis_bytes = session.read(genesis_path)
        _require_digest(
            genesis_bytes, freeze.genesis_sha256, freeze.genesis_byte_length
        )
        # Reconstruct deployment evidence from observed bytes, never from a
        # caller bundle or prepared/replayed Trading/P2 capability.
        manifest = PersonalDesktopPaperAccountProvisioningManifest(
            paper_account_id=anchor.paper_account_id,
            machine_authority_id=anchor.machine_authority_id,
            approved_trading_sid=anchor.approved_trading_sid,
            genesis_checkpoint_id=anchor.genesis_checkpoint_id,
            genesis_sha256=sha256(genesis_bytes).hexdigest(),
            genesis_byte_length=len(genesis_bytes),
            anchor_sha256=sha256(anchor_bytes).hexdigest(),
            anchor_byte_length=len(anchor_bytes),
        )
        manifest_bytes = serialize_personal_desktop_paper_account_manifest(manifest)
        bundle = PersonalDesktopPaperAccountBundle(
            genesis_bytes, anchor_bytes, manifest_bytes
        )
        verify_personal_desktop_paper_publication_freeze(
            bundle, freeze=freeze, administrator_validation=validation
        )
        objects = tuple((path, session.pin(path).observation) for path in staged_paths)
        session.finish()
        _require_disarmed()
        if require_production_paper_publication_freeze() != freeze:
            raise PersonalDesktopPaperAccountError("recovery source freeze drift")
        if _administrator(freeze) != validation:
            raise PersonalDesktopPaperAccountError("recovery Administrator C1 drift")
        _require_occupancy(session)
        # Context exit independently reopens every name, rechecks all security,
        # identity, bytes and inventories, then releases every held read handle.
    return PersonalDesktopPaperStagingRecoveryQualification(
        paper_account_id=anchor.paper_account_id,
        genesis_checkpoint_id=anchor.genesis_checkpoint_id,
        machine_authority_id=anchor.machine_authority_id,
        approved_trading_sid=anchor.approved_trading_sid,
        starting_cash=freeze.starting_cash,
        genesis_as_of=freeze.genesis_as_of,
        anchor_sha256=sha256(anchor_bytes).hexdigest(),
        anchor_byte_length=len(anchor_bytes),
        genesis_sha256=sha256(genesis_bytes).hexdigest(),
        genesis_byte_length=len(genesis_bytes),
        manifest_sha256=sha256(manifest_bytes).hexdigest(),
        manifest_byte_length=len(manifest_bytes),
        objects=objects,
        v2_state=PaperPublicationState.STAGING_REQUIRES_REVIEW,
        v1_final_present=False,
        v1_historical_staging_present=True,
    )
