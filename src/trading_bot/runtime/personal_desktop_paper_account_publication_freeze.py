"""Pure PD1E freeze contract for the administrator publication plane.

Trading/P2 establishes provenance during preparation and readiness. A later
reviewed source diff freezes those exact bytes here; this model neither carries
nor recreates a Trading runtime capability or P2 permit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

from trading_bot.runtime.personal_desktop_paper_account_authority import (
    PersonalDesktopPaperAccountError,
    parse_personal_desktop_paper_account_anchor,
)
from trading_bot.runtime.personal_desktop_paper_account_provisioning import (
    PersonalDesktopPaperAccountBundle,
    reconcile_personal_desktop_paper_account_artifacts,
)
from trading_bot.runtime.personal_desktop_paper_account_security import (
    PaperObjectRole,
    paper_security_policy,
)
from trading_bot.runtime.windows_authority import (
    PRODUCTION_AUTHORITY_PATHS,
    BootstrapVerification,
    WindowsAuthorityBootstrap,
)
from trading_bot.runtime.windows_authority_validation import (
    InstalledAuthorityValidation,
    ProvisioningEvidence,
    ProvisioningState,
    require_initialized_supported_authority_evidence,
)


@dataclass(frozen=True, slots=True)
class PersonalDesktopPaperPublicationFreeze:
    """Exact reviewed data, never a transferable authorization capability."""

    machine_authority_id: str
    approved_trading_sid: str
    paper_account_id: str
    starting_cash: Decimal
    genesis_as_of: datetime
    genesis_sha256: str
    genesis_byte_length: int
    anchor_sha256: str
    anchor_byte_length: int
    manifest_sha256: str
    manifest_byte_length: int

    def __post_init__(self) -> None:
        for field in ("machine_authority_id", "paper_account_id"):
            value = getattr(self, field)
            if type(value) is not str:
                raise PersonalDesktopPaperAccountError("freeze UUID must be exact text")
            try:
                canonical = str(UUID(value))
            except ValueError as error:
                raise PersonalDesktopPaperAccountError(
                    "freeze UUID is invalid"
                ) from error
            if value != canonical:
                raise PersonalDesktopPaperAccountError("freeze UUID must be canonical")
        # Reuse the accepted exact Trading SID policy; no account lookup occurs.
        paper_security_policy(PaperObjectRole.ROOT, self.approved_trading_sid)
        if (
            type(self.starting_cash) is not Decimal
            or not self.starting_cash.is_finite()
            or self.starting_cash <= 0
        ):
            raise PersonalDesktopPaperAccountError(
                "freeze cash must be explicit positive Decimal"
            )
        if (
            type(self.genesis_as_of) is not datetime
            or self.genesis_as_of.tzinfo is not UTC
        ):
            raise PersonalDesktopPaperAccountError(
                "freeze chronology must be exact UTC datetime"
            )
        for artifact in ("genesis", "anchor", "manifest"):
            digest = getattr(self, artifact + "_sha256")
            length = getattr(self, artifact + "_byte_length")
            if type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
                raise PersonalDesktopPaperAccountError(
                    "freeze hash must be lowercase SHA-256"
                )
            if type(length) is not int or length <= 0:
                raise PersonalDesktopPaperAccountError(
                    "freeze length must be a positive int"
                )


# Exact PD1E readiness values; this data freeze does not enable production effects.
# There is deliberately no loader, environment override, setter, or CLI input.
PERSONAL_DESKTOP_PAPER_V2_PUBLICATION_FREEZE: (
    PersonalDesktopPaperPublicationFreeze | None
) = PersonalDesktopPaperPublicationFreeze(
    machine_authority_id="223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1",
    approved_trading_sid="S-1-5-21-1397534616-3988210162-180023805-1009",
    paper_account_id="9415cd7b-bf36-5fba-bd58-a0f99119dc21",
    starting_cash=Decimal("25000"),
    genesis_as_of=datetime(2026, 8, 29, 9, 46, 43, 769105, tzinfo=UTC),
    genesis_sha256="d1a7ff14425c8a797a952860a1102489a4c81cac2a24a45bc3127eb8eb2e9548",
    genesis_byte_length=533,
    anchor_sha256="16c4dba01835c5bc2def91f0103ad79c3da0b5d18af72091b4fdd37fe4353c85",
    anchor_byte_length=465,
    manifest_sha256="8fe1d705d59a79207ab6236af71becee0051042dc7b3ecaf23bb7f5531cb0029",
    manifest_byte_length=532,
)


def require_production_paper_publication_freeze() -> (
    PersonalDesktopPaperPublicationFreeze
):
    """Fail closed until an exact production freeze is configured in source."""
    freeze = PERSONAL_DESKTOP_PAPER_V2_PUBLICATION_FREEZE
    if type(freeze) is not PersonalDesktopPaperPublicationFreeze:
        raise PersonalDesktopPaperAccountError(
            "production publication freeze is unconfigured"
        )
    freeze.__post_init__()
    return freeze


def verify_personal_desktop_paper_publication_freeze(
    bundle: PersonalDesktopPaperAccountBundle,
    *,
    freeze: PersonalDesktopPaperPublicationFreeze,
    administrator_validation: InstalledAuthorityValidation,
) -> None:
    """Reconcile reviewed bytes against complete administrator C1 evidence.

    This is pure evidence comparison, not signature/database validation or P2
    permit issuance. Production must obtain administrator_validation internally
    from validate_installed_authority_complete(), never from a caller.
    """
    if type(freeze) is not PersonalDesktopPaperPublicationFreeze:
        raise PersonalDesktopPaperAccountError("expected exact publication freeze")
    freeze.__post_init__()
    if type(bundle) is not PersonalDesktopPaperAccountBundle:
        raise PersonalDesktopPaperAccountError("expected exact v2 bundle")
    checkpoint = reconcile_personal_desktop_paper_account_artifacts(
        genesis_bytes=bundle.genesis_bytes,
        anchor_bytes=bundle.anchor_bytes,
        manifest_bytes=bundle.manifest_bytes,
    )
    if (
        type(administrator_validation) is not InstalledAuthorityValidation
        or type(administrator_validation.provisioning) is not ProvisioningEvidence
        or type(administrator_validation.bootstrap_verification)
        is not BootstrapVerification
        or type(administrator_validation.bootstrap_verification.bootstrap)
        is not WindowsAuthorityBootstrap
    ):
        raise PersonalDesktopPaperAccountError(
            "expected complete administrator C1 evidence"
        )
    require_initialized_supported_authority_evidence(administrator_validation)
    verification = administrator_validation.bootstrap_verification
    bootstrap = verification.bootstrap
    bootstrap.__post_init__()
    provisioning = administrator_validation.provisioning
    if (
        provisioning.state is not ProvisioningState.VALIDATED
        or provisioning.authority_root != str(PRODUCTION_AUTHORITY_PATHS.root)
        or provisioning.database_present is not True
        or provisioning.journal_present is not True
        or verification.bootstrap_digest != bootstrap.digest
        or verification.signing_key_id != bootstrap.signing_key_id
        or provisioning.signing_key_id != bootstrap.signing_key_id
        or type(verification.signature_length) is not int
        or verification.signature_length != 64
    ):
        raise PersonalDesktopPaperAccountError(
            "administrator bootstrap evidence does not reconcile"
        )
    for artifact in ("genesis", "anchor", "manifest"):
        payload = getattr(bundle, artifact + "_bytes")
        if sha256(payload).hexdigest() != getattr(freeze, artifact + "_sha256") or len(
            payload
        ) != getattr(freeze, artifact + "_byte_length"):
            raise PersonalDesktopPaperAccountError(
                "bundle differs from exact publication freeze"
            )
    anchor = parse_personal_desktop_paper_account_anchor(bundle.anchor_bytes)
    if (
        anchor.paper_account_id != freeze.paper_account_id
        or anchor.machine_authority_id != freeze.machine_authority_id
        or anchor.approved_trading_sid != freeze.approved_trading_sid
        or bootstrap.machine_authority_id != freeze.machine_authority_id
        or bootstrap.approved_account_sid != freeze.approved_trading_sid
        or checkpoint.account_state.cash != freeze.starting_cash
        or checkpoint.account_state.as_of != freeze.genesis_as_of
    ):
        raise PersonalDesktopPaperAccountError(
            "freeze identity/opening evidence does not reconcile"
        )
