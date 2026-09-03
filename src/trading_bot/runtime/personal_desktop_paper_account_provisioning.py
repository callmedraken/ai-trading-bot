"""Pure Architecture-103 PD1A preparation; no publication or runtime effects."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from decimal import Decimal
from hashlib import sha256

from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    verify_daily_snapshot,
)
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    SelectedC3SnapshotReadResult,
    require_disposable_selected_c3_snapshot_matches_identity_for_test,
    require_selected_c3_snapshot_matches_authority,
)
from trading_bot.runtime.paper_account_checkpoint import (
    PaperAccountCheckpoint,
    PaperAccountCheckpointVerificationStatus,
    PaperAccountGenesisRequest,
    create_genesis_paper_account_checkpoint,
    serialize_paper_account_checkpoint,
    verify_genesis_paper_account_checkpoint,
)
from trading_bot.runtime.personal_desktop_paper_account_authority import (
    PersonalDesktopPaperAccountAnchor,
    PersonalDesktopPaperAccountError,
    canonical_personal_desktop_paper_json,
    derive_personal_desktop_paper_account_id,
    parse_personal_desktop_paper_account_anchor,
    parse_personal_desktop_paper_json,
    serialize_personal_desktop_paper_account_anchor,
)
from trading_bot.runtime.windows_authority import WindowsAuthorityBootstrap
from trading_bot.runtime.windows_authority_schema import ProductionAuthorityEvidence
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    issue_validated_production_authority_for_test,
    require_validated_production_authority,
)

PERSONAL_DESKTOP_PAPER_ACCOUNT_PROVISIONING_SCHEMA = (
    "personal-desktop-paper-account-provisioning/v1"
)
_FIELDS = frozenset(
    {
        "schema",
        "paper_account_id",
        "machine_authority_id",
        "approved_trading_sid",
        "genesis_checkpoint_id",
        "genesis_sha256",
        "genesis_byte_length",
        "anchor_sha256",
        "anchor_byte_length",
    }
)


@dataclass(frozen=True, slots=True)
class PersonalDesktopPaperAccountProvisioningManifest:
    """Closed deployment evidence, never an installed authority or capability."""

    paper_account_id: str
    machine_authority_id: str
    approved_trading_sid: str
    genesis_checkpoint_id: str
    genesis_sha256: str
    genesis_byte_length: int
    anchor_sha256: str
    anchor_byte_length: int
    schema: str = PERSONAL_DESKTOP_PAPER_ACCOUNT_PROVISIONING_SCHEMA

    def __post_init__(self) -> None:
        if (
            type(self.schema) is not str
            or self.schema != PERSONAL_DESKTOP_PAPER_ACCOUNT_PROVISIONING_SCHEMA
        ):
            raise PersonalDesktopPaperAccountError("unsupported provisioning schema")
        # The same closed identity policy applies to both artifacts.
        self.anchor()
        if (
            type(self.anchor_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", self.anchor_sha256) is None
        ):
            raise PersonalDesktopPaperAccountError(
                "anchor_sha256 must be lowercase SHA-256"
            )
        if type(self.anchor_byte_length) is not int or self.anchor_byte_length <= 0:
            raise PersonalDesktopPaperAccountError(
                "anchor_byte_length must be positive int"
            )

    def anchor(self) -> PersonalDesktopPaperAccountAnchor:
        """Reconstruct the exact anchor identity asserted by this manifest."""

        return PersonalDesktopPaperAccountAnchor(
            paper_account_id=self.paper_account_id,
            machine_authority_id=self.machine_authority_id,
            approved_trading_sid=self.approved_trading_sid,
            genesis_checkpoint_id=self.genesis_checkpoint_id,
            genesis_sha256=self.genesis_sha256,
            genesis_byte_length=self.genesis_byte_length,
        )


def serialize_personal_desktop_paper_account_manifest(
    manifest: PersonalDesktopPaperAccountProvisioningManifest,
) -> bytes:
    """Validate and encode canonical manifest bytes."""

    if type(manifest) is not PersonalDesktopPaperAccountProvisioningManifest:
        raise PersonalDesktopPaperAccountError("expected exact provisioning manifest")
    manifest.__post_init__()
    return canonical_personal_desktop_paper_json(asdict(manifest))


def parse_personal_desktop_paper_account_manifest(
    payload: bytes,
) -> PersonalDesktopPaperAccountProvisioningManifest:
    """Parse only the closed, canonical manifest schema."""

    return PersonalDesktopPaperAccountProvisioningManifest(
        **parse_personal_desktop_paper_json(payload, fields=_FIELDS)
    )


def reconcile_personal_desktop_paper_account_artifacts(
    *, genesis_bytes: bytes, anchor_bytes: bytes, manifest_bytes: bytes
) -> PaperAccountCheckpoint:
    """Verify manifest -> anchor -> GENESIS and the fresh cash-only policy.

    This proves internal artifact consistency only. Use the contextual bundle
    verifier below to reconcile C1, P2 chronology, and approved starting cash.
    """

    manifest = parse_personal_desktop_paper_account_manifest(manifest_bytes)
    anchor = parse_personal_desktop_paper_account_anchor(anchor_bytes)
    if (
        manifest.anchor() != anchor
        or sha256(anchor_bytes).hexdigest() != manifest.anchor_sha256
        or len(anchor_bytes) != manifest.anchor_byte_length
    ):
        raise PersonalDesktopPaperAccountError("manifest and anchor do not reconcile")
    if type(genesis_bytes) is not bytes:
        raise PersonalDesktopPaperAccountError("GENESIS must be exact bytes")
    verified = verify_genesis_paper_account_checkpoint(
        genesis_bytes,
        expected_checkpoint_sha256=anchor.genesis_sha256,
        expected_checkpoint_byte_length=anchor.genesis_byte_length,
    )
    checkpoint = verified.checkpoint
    if (
        verified.status is not PaperAccountCheckpointVerificationStatus.PASS
        or verified.diagnostics
        or checkpoint is None
        or str(checkpoint.checkpoint_id) != anchor.genesis_checkpoint_id
    ):
        raise PersonalDesktopPaperAccountError("anchor and GENESIS do not reconcile")
    state = checkpoint.account_state
    if (
        state.cash <= 0
        or state.positions != ()
        or state.realized_profit_loss != Decimal("0")
        or checkpoint.metadata != ()
    ):
        raise PersonalDesktopPaperAccountError(
            "GENESIS violates cash-only opening policy"
        )
    # Architecture 61 proves the empty engine/open-order state and exact bytes.
    return checkpoint


@dataclass(frozen=True, slots=True)
class PersonalDesktopPaperAccountBundle:
    """Three exact immutable reconciled byte strings; never a publication permit."""

    genesis_bytes: bytes
    anchor_bytes: bytes
    manifest_bytes: bytes

    def __post_init__(self) -> None:
        reconcile_personal_desktop_paper_account_artifacts(
            genesis_bytes=self.genesis_bytes,
            anchor_bytes=self.anchor_bytes,
            manifest_bytes=self.manifest_bytes,
        )


def _prepare(
    authority: ValidatedProductionAuthority,
    selected_snapshot: SelectedC3SnapshotReadResult,
    starting_cash: Decimal,
) -> PersonalDesktopPaperAccountBundle:
    # Entry points must establish C1/P2 provenance before calling this pure core.
    if (
        type(starting_cash) is not Decimal
        or not starting_cash.is_finite()
        or starting_cash <= 0
    ):
        raise PersonalDesktopPaperAccountError(
            "starting_cash must be explicit positive Decimal"
        )
    selected_snapshot.__post_init__()
    verified = verify_daily_snapshot(
        selected_snapshot.snapshot_bytes,
        BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar()),
        expected_sha256=selected_snapshot.audit.artifact_sha256,
        expected_byte_length=selected_snapshot.audit.artifact_byte_length,
    )
    if (
        not verified.passed
        or verified.diagnostics
        or verified.snapshot is None
        or verified != selected_snapshot.verification
    ):
        raise PersonalDesktopPaperAccountError(
            "independent selected snapshot verification failed"
        )
    genesis = create_genesis_paper_account_checkpoint(
        PaperAccountGenesisRequest(
            as_of=verified.snapshot.audit.captured_at,
            cash=starting_cash,
            positions=(),
            realized_profit_loss=Decimal("0"),
            open_orders=(),
            metadata=(),
        )
    )
    genesis_bytes = serialize_paper_account_checkpoint(genesis)
    verified_genesis = verify_genesis_paper_account_checkpoint(genesis_bytes)
    if (
        verified_genesis.status is not PaperAccountCheckpointVerificationStatus.PASS
        or verified_genesis.diagnostics
        or verified_genesis.checkpoint != genesis
    ):
        raise PersonalDesktopPaperAccountError("prepared GENESIS did not verify")
    identity = {
        "machine_authority_id": authority.machine_authority_id,
        "approved_trading_sid": authority.approved_account_sid,
        "genesis_checkpoint_id": str(genesis.checkpoint_id),
        "genesis_sha256": verified_genesis.checkpoint_sha256,
        "genesis_byte_length": verified_genesis.checkpoint_byte_length,
    }
    anchor = PersonalDesktopPaperAccountAnchor(
        paper_account_id=derive_personal_desktop_paper_account_id(**identity),
        **identity,
    )
    anchor_bytes = serialize_personal_desktop_paper_account_anchor(anchor)
    if parse_personal_desktop_paper_account_anchor(anchor_bytes) != anchor:
        raise PersonalDesktopPaperAccountError("prepared anchor did not reconcile")
    manifest = PersonalDesktopPaperAccountProvisioningManifest(
        paper_account_id=anchor.paper_account_id,
        **identity,
        anchor_sha256=sha256(anchor_bytes).hexdigest(),
        anchor_byte_length=len(anchor_bytes),
    )
    manifest_bytes = serialize_personal_desktop_paper_account_manifest(manifest)
    if parse_personal_desktop_paper_account_manifest(manifest_bytes) != manifest:
        raise PersonalDesktopPaperAccountError("prepared manifest did not reconcile")
    return PersonalDesktopPaperAccountBundle(
        genesis_bytes, anchor_bytes, manifest_bytes
    )


def prepare_personal_desktop_paper_account_bundle(
    *,
    authority: ValidatedProductionAuthority,
    selected_snapshot: SelectedC3SnapshotReadResult,
    starting_cash: Decimal,
) -> PersonalDesktopPaperAccountBundle:
    """Prepare offline bytes from genuine matching C1/P2 and explicit cash only.

    Retain the P2 reader while consuming its process-local permit. This function
    performs no new read, filesystem output, or provider operation.
    """

    require_validated_production_authority(authority)
    if type(selected_snapshot) is not SelectedC3SnapshotReadResult:
        raise PersonalDesktopPaperAccountError("expected exact P2 read result")
    require_selected_c3_snapshot_matches_authority(
        selected_snapshot.permit, selected_snapshot.audit, authority
    )
    return _prepare(authority, selected_snapshot, starting_cash)


def prepare_personal_desktop_paper_account_bundle_for_test(
    *,
    bootstrap: WindowsAuthorityBootstrap,
    bootstrap_digest: str,
    production_evidence: ProductionAuthorityEvidence,
    selected_snapshot: SelectedC3SnapshotReadResult,
    starting_cash: Decimal,
) -> PersonalDesktopPaperAccountBundle:
    """Disposable-only preparation through the existing public C1/P2 test seams.

    Test provenance is never promoted into a production C1 or P2 capability.
    Returned bytes remain data and require production contextual verification.
    """

    authority = issue_validated_production_authority_for_test(
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap_digest,
        production_evidence=production_evidence,
    )
    if type(selected_snapshot) is not SelectedC3SnapshotReadResult:
        raise PersonalDesktopPaperAccountError("expected exact P2 read result")
    require_disposable_selected_c3_snapshot_matches_identity_for_test(
        selected_snapshot.permit,
        selected_snapshot.audit,
        machine_authority_id=authority.machine_authority_id,
        approved_trading_sid=authority.approved_account_sid,
        authority_epoch_id=authority.authority_epoch_id,
    )
    return _prepare(authority, selected_snapshot, starting_cash)


def verify_personal_desktop_paper_account_bundle(
    bundle: PersonalDesktopPaperAccountBundle,
    *,
    authority: ValidatedProductionAuthority,
    selected_snapshot: SelectedC3SnapshotReadResult,
    starting_cash: Decimal,
) -> None:
    """Fail closed unless every byte matches independently prepared C1/P2 evidence."""

    if type(bundle) is not PersonalDesktopPaperAccountBundle:
        raise PersonalDesktopPaperAccountError("expected exact v2 bundle")
    expected = prepare_personal_desktop_paper_account_bundle(
        authority=authority,
        selected_snapshot=selected_snapshot,
        starting_cash=starting_cash,
    )
    if bundle != expected:
        raise PersonalDesktopPaperAccountError(
            "bundle does not match C1/P2/opening evidence"
        )


def verify_personal_desktop_paper_account_bundle_for_test(
    bundle: PersonalDesktopPaperAccountBundle,
    *,
    bootstrap: WindowsAuthorityBootstrap,
    bootstrap_digest: str,
    production_evidence: ProductionAuthorityEvidence,
    selected_snapshot: SelectedC3SnapshotReadResult,
    starting_cash: Decimal,
) -> None:
    """Contextual reconciliation for disposable-only C1/P2 test provenance."""

    if type(bundle) is not PersonalDesktopPaperAccountBundle:
        raise PersonalDesktopPaperAccountError("expected exact v2 bundle")
    expected = prepare_personal_desktop_paper_account_bundle_for_test(
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap_digest,
        production_evidence=production_evidence,
        selected_snapshot=selected_snapshot,
        starting_cash=starting_cash,
    )
    if bundle != expected:
        raise PersonalDesktopPaperAccountError(
            "bundle does not match disposable C1/P2/opening evidence"
        )
