"""Pure production-v1 opening bundle; no filesystem or effect authority."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid5

from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    DailySnapshotVerificationResult,
    DailySnapshotVerificationStatus,
    serialize_daily_snapshot,
    verify_daily_snapshot,
)
from trading_bot.runtime.manual_paper_account_authority import (
    MAX_MANUAL_PAPER_ANCHOR_BYTES,
    ManualPaperAccountAnchor,
    parse_manual_paper_account_anchor,
    serialize_manual_paper_account_anchor,
)
from trading_bot.runtime.paper_account_checkpoint import (
    MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES,
    PaperAccountCheckpoint,
    PaperAccountCheckpointVerificationStatus,
    PaperAccountGenesisRequest,
    create_genesis_paper_account_checkpoint,
    serialize_paper_account_checkpoint,
    verify_genesis_paper_account_checkpoint,
)

MANUAL_PAPER_ACCOUNT_PROVISIONING_SCHEMA = "manual-paper-account-provisioning/v1"
MANUAL_PAPER_ACCOUNT_PROVISIONING_NAMESPACE = UUID(
    "32a20ea3-acb3-556f-ac96-2518bbf52f01"
)
MAX_MANUAL_PAPER_PROVISIONING_MANIFEST_BYTES = 4096


class ManualPaperAccountProvisioningError(ValueError):
    """Bounded, nonsecret bundle rejection."""


def _uuid(value: object) -> None:
    if type(value) is not str:
        raise ManualPaperAccountProvisioningError("UUID_INVALID")
    try:
        valid = str(UUID(value)) == value
    except ValueError:
        valid = False
    if not valid:
        raise ManualPaperAccountProvisioningError("UUID_INVALID")


def _sid(value: object) -> None:
    # Exact local account SID, with canonical unsigned DWORD subauthorities.
    if (
        type(value) is not str
        or re.fullmatch(
            r"S-1-5-21-(?:0|[1-9][0-9]{0,9})-(?:0|[1-9][0-9]{0,9})-"
            r"(?:0|[1-9][0-9]{0,9})-(?:0|[1-9][0-9]{0,9})",
            value,
        )
        is None
    ):
        raise ManualPaperAccountProvisioningError("SID_INVALID")
    if any(int(part) > 0xFFFFFFFF for part in value.split("-")[4:]):
        raise ManualPaperAccountProvisioningError("SID_INVALID")


def _artifact(digest: object, length: object, maximum: int) -> None:
    if (
        type(digest) is not str
        or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        or type(length) is not int
        or not 1 <= length <= maximum
    ):
        raise ManualPaperAccountProvisioningError("ARTIFACT_EVIDENCE_INVALID")


def derive_manual_paper_account_id(
    *,
    machine_authority_id: str,
    approved_trading_sid: str,
    genesis_checkpoint_id: UUID,
    genesis_sha256: str,
    genesis_byte_length: int,
) -> UUID:
    """Frozen UUID5 deployment identity, distinct from A61 domain identities."""
    _uuid(machine_authority_id)
    _sid(approved_trading_sid)
    if type(genesis_checkpoint_id) is not UUID:
        raise ManualPaperAccountProvisioningError("GENESIS_ID_INVALID")
    _artifact(genesis_sha256, genesis_byte_length, MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES)
    parts = (
        "manual-paper-account-provisioning-id-v1",
        machine_authority_id,
        approved_trading_sid,
        str(genesis_checkpoint_id),
        genesis_sha256,
        str(genesis_byte_length),
    )
    material = "".join(f"{len(part.encode('utf-8'))}:{part}" for part in parts)
    return uuid5(MANUAL_PAPER_ACCOUNT_PROVISIONING_NAMESPACE, material)


@dataclass(frozen=True, slots=True)
class ManualPaperAccountProvisioningManifest:
    paper_account_id: UUID
    machine_authority_id: str
    approved_trading_sid: str
    genesis_checkpoint_id: UUID
    genesis_sha256: str
    genesis_byte_length: int
    anchor_sha256: str
    anchor_byte_length: int
    schema: str = MANUAL_PAPER_ACCOUNT_PROVISIONING_SCHEMA

    def __post_init__(self) -> None:
        if (
            type(self.schema) is not str
            or self.schema != MANUAL_PAPER_ACCOUNT_PROVISIONING_SCHEMA
            or type(self.paper_account_id) is not UUID
        ):
            raise ManualPaperAccountProvisioningError("MANIFEST_FIELDS_INVALID")
        expected = derive_manual_paper_account_id(
            machine_authority_id=self.machine_authority_id,
            approved_trading_sid=self.approved_trading_sid,
            genesis_checkpoint_id=self.genesis_checkpoint_id,
            genesis_sha256=self.genesis_sha256,
            genesis_byte_length=self.genesis_byte_length,
        )
        if self.paper_account_id != expected:
            raise ManualPaperAccountProvisioningError("ACCOUNT_ID_MISMATCH")
        _artifact(
            self.anchor_sha256, self.anchor_byte_length, MAX_MANUAL_PAPER_ANCHOR_BYTES
        )


def serialize_manual_paper_account_provisioning_manifest(
    manifest: ManualPaperAccountProvisioningManifest,
) -> bytes:
    if type(manifest) is not ManualPaperAccountProvisioningManifest:
        raise ManualPaperAccountProvisioningError("MANIFEST_TYPE_INVALID")
    manifest.__post_init__()
    tree = asdict(manifest)
    tree["paper_account_id"] = str(manifest.paper_account_id)
    tree["genesis_checkpoint_id"] = str(manifest.genesis_checkpoint_id)
    return (
        json.dumps(tree, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ManualPaperAccountProvisioningError("MANIFEST_DUPLICATE_FIELD")
        result[key] = value
    return result


def _reject_number(value: str) -> None:
    raise ManualPaperAccountProvisioningError("MANIFEST_NUMBER_INVALID")


def parse_manual_paper_account_provisioning_manifest(
    payload: bytes,
) -> ManualPaperAccountProvisioningManifest:
    try:
        if (
            type(payload) is not bytes
            or not 0 < len(payload) <= MAX_MANUAL_PAPER_PROVISIONING_MANIFEST_BYTES
        ):
            raise ManualPaperAccountProvisioningError("MANIFEST_LENGTH_INVALID")
        tree = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_float=_reject_number,
            parse_constant=_reject_number,
        )
        if type(tree) is not dict or set(tree) != {
            "schema",
            "paper_account_id",
            "machine_authority_id",
            "approved_trading_sid",
            "genesis_checkpoint_id",
            "genesis_sha256",
            "genesis_byte_length",
            "anchor_sha256",
            "anchor_byte_length",
        }:
            raise ManualPaperAccountProvisioningError("MANIFEST_FIELDS_INVALID")
        for field in ("paper_account_id", "genesis_checkpoint_id"):
            _uuid(tree[field])
            tree[field] = UUID(tree[field])
        manifest = ManualPaperAccountProvisioningManifest(**tree)
        if serialize_manual_paper_account_provisioning_manifest(manifest) != payload:
            raise ManualPaperAccountProvisioningError("MANIFEST_NONCANONICAL")
        return manifest
    except ManualPaperAccountProvisioningError:
        raise
    except Exception:
        raise ManualPaperAccountProvisioningError("MANIFEST_PARSE_FAILED") from None


@dataclass(frozen=True, slots=True)
class ManualPaperAccountProvisioningEvidence:
    """Exact review expectation, including all three artifacts; no capability."""

    manifest: ManualPaperAccountProvisioningManifest
    manifest_sha256: str
    manifest_byte_length: int

    def __post_init__(self) -> None:
        payload = serialize_manual_paper_account_provisioning_manifest(self.manifest)
        _artifact(
            self.manifest_sha256,
            self.manifest_byte_length,
            MAX_MANUAL_PAPER_PROVISIONING_MANIFEST_BYTES,
        )
        if (self.manifest_sha256, self.manifest_byte_length) != (
            sha256(payload).hexdigest(),
            len(payload),
        ) or type(self.manifest_byte_length) is not int:
            raise ManualPaperAccountProvisioningError("MANIFEST_EVIDENCE_MISMATCH")


@dataclass(frozen=True, slots=True)
class ManualPaperAccountProvisioningBundle:
    """Transport bytes only; construction is not proof. Always verify at use."""

    genesis_bytes: bytes
    anchor_bytes: bytes
    manifest_bytes: bytes


def verify_manual_paper_account_provisioning_bundle(
    bundle: ManualPaperAccountProvisioningBundle,
) -> ManualPaperAccountProvisioningEvidence:
    """Reconcile canonical artifacts, production opening shape, and account ID."""
    try:
        if type(bundle) is not ManualPaperAccountProvisioningBundle:
            raise ManualPaperAccountProvisioningError("BUNDLE_TYPE_INVALID")
        manifest = parse_manual_paper_account_provisioning_manifest(
            bundle.manifest_bytes
        )
        anchor = parse_manual_paper_account_anchor(bundle.anchor_bytes)
        verification = verify_genesis_paper_account_checkpoint(
            bundle.genesis_bytes,
            expected_checkpoint_sha256=manifest.genesis_sha256,
            expected_checkpoint_byte_length=manifest.genesis_byte_length,
        )
        verification.__post_init__()
        checkpoint = verification.checkpoint
        if (
            verification.status is not PaperAccountCheckpointVerificationStatus.PASS
            or type(checkpoint) is not PaperAccountCheckpoint
        ):
            raise ManualPaperAccountProvisioningError("GENESIS_VERIFICATION_FAILED")
        state = checkpoint.account_state
        if (
            state.cash <= 0
            or state.positions
            or state.realized_profit_loss != 0
            or checkpoint.metadata
        ):
            raise ManualPaperAccountProvisioningError("OPENING_STATE_INVALID")
        if (
            checkpoint.checkpoint_id != manifest.genesis_checkpoint_id
            or serialize_paper_account_checkpoint(checkpoint) != bundle.genesis_bytes
            or anchor
            != ManualPaperAccountAnchor(
                manifest.paper_account_id,
                manifest.machine_authority_id,
                manifest.approved_trading_sid,
                manifest.genesis_checkpoint_id,
                manifest.genesis_sha256,
                manifest.genesis_byte_length,
            )
            or (sha256(bundle.anchor_bytes).hexdigest(), len(bundle.anchor_bytes))
            != (manifest.anchor_sha256, manifest.anchor_byte_length)
        ):
            raise ManualPaperAccountProvisioningError("BUNDLE_RECONCILIATION_FAILED")
        return ManualPaperAccountProvisioningEvidence(
            manifest,
            sha256(bundle.manifest_bytes).hexdigest(),
            len(bundle.manifest_bytes),
        )
    except ManualPaperAccountProvisioningError:
        raise
    except Exception:
        raise ManualPaperAccountProvisioningError(
            "BUNDLE_VERIFICATION_FAILED"
        ) from None


def build_manual_paper_account_provisioning_bundle(
    *,
    machine_authority_id: str,
    approved_trading_sid: str,
    starting_cash: Decimal,
    snapshot_verification: DailySnapshotVerificationResult,
) -> ManualPaperAccountProvisioningBundle:
    """Build v1 from explicit cash and one complete, reverified XNYS snapshot.

    No timestamp, account ID, positions, P&L, orders, or metadata override exists.
    The rollout's call-#6 selection and exact bundle are frozen outside this pure
    generic API; a snapshot result grants no P2 or provider authority.
    """
    try:
        _uuid(machine_authority_id)
        _sid(approved_trading_sid)
        if (
            type(starting_cash) is not Decimal
            or not starting_cash.is_finite()
            or starting_cash <= 0
        ):
            raise ManualPaperAccountProvisioningError("STARTING_CASH_INVALID")
        if type(snapshot_verification) is not DailySnapshotVerificationResult:
            raise ManualPaperAccountProvisioningError("SNAPSHOT_RESULT_INVALID")
        snapshot_verification.__post_init__()
        if snapshot_verification.status is not DailySnapshotVerificationStatus.PASS:
            raise ManualPaperAccountProvisioningError("SNAPSHOT_RESULT_INVALID")
        payload = serialize_daily_snapshot(snapshot_verification.snapshot)
        verified = verify_daily_snapshot(
            payload,
            BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar()),
            expected_sha256=snapshot_verification.sha256,
            expected_byte_length=snapshot_verification.byte_length,
        )
        if (
            verified != snapshot_verification
            or not verified.passed
            or verified.snapshot is None
        ):
            raise ManualPaperAccountProvisioningError("SNAPSHOT_REVERIFICATION_FAILED")
        checkpoint = create_genesis_paper_account_checkpoint(
            PaperAccountGenesisRequest(
                as_of=verified.snapshot.audit.captured_at,
                cash=starting_cash,
                positions=(),
                realized_profit_loss=Decimal("0"),
                metadata=(),
                open_orders=(),
            )
        )
        genesis = serialize_paper_account_checkpoint(checkpoint)
        digest = sha256(genesis).hexdigest()
        account_id = derive_manual_paper_account_id(
            machine_authority_id=machine_authority_id,
            approved_trading_sid=approved_trading_sid,
            genesis_checkpoint_id=checkpoint.checkpoint_id,
            genesis_sha256=digest,
            genesis_byte_length=len(genesis),
        )
        anchor = serialize_manual_paper_account_anchor(
            ManualPaperAccountAnchor(
                account_id,
                machine_authority_id,
                approved_trading_sid,
                checkpoint.checkpoint_id,
                digest,
                len(genesis),
            )
        )
        manifest = serialize_manual_paper_account_provisioning_manifest(
            ManualPaperAccountProvisioningManifest(
                account_id,
                machine_authority_id,
                approved_trading_sid,
                checkpoint.checkpoint_id,
                digest,
                len(genesis),
                sha256(anchor).hexdigest(),
                len(anchor),
            )
        )
        bundle = ManualPaperAccountProvisioningBundle(genesis, anchor, manifest)
        verify_manual_paper_account_provisioning_bundle(bundle)
        return bundle
    except ManualPaperAccountProvisioningError:
        raise
    except Exception:
        raise ManualPaperAccountProvisioningError("BUNDLE_BUILD_FAILED") from None
