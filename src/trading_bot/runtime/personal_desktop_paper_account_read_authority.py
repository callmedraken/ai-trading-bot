"""Read-only Windows v2 account authority reconciled through A61/A66/A67.

Only the production entry point issues a registered authority, after C1, token,
fixed-object, and complete offline verification. Configuration dependencies are
bounded exact bytes: A67 receipts retain their hash/length, not their contents.
They never supply filesystem paths, checkpoint candidates, or a selected tip.
"""

from __future__ import annotations

import threading
import weakref
from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    IdentifiedMarketCalendar,
)
from trading_bot.runtime.checkpointed_paper_cycle_report import (
    CheckpointedPaperCycleReport,
    parse_checkpointed_paper_cycle_report,
)
from trading_bot.runtime.checkpointed_verified_snapshot_execution import (
    VerifiedPriorCheckpoint,
    verified_prior_from_full_lineage,
)
from trading_bot.runtime.paper_account_checkpoint import (
    PaperAccountCheckpointVerificationStatus,
    verify_genesis_paper_account_checkpoint,
)
from trading_bot.runtime.paper_account_lineage_verification import (
    PaperAccountLineageArtifact,
    PaperAccountLineageArtifactKind,
    PaperAccountLineageEvidence,
    PaperAccountLineageVerificationStatus,
    verify_paper_account_lineage,
)
from trading_bot.runtime.paper_account_successor_checkpoint import (
    PaperAccountSuccessorCheckpoint,
    parse_successor_paper_account_checkpoint,
)
from trading_bot.runtime.paper_operation import (
    PaperOperationReceipt,
    PaperOperationReceiptVerificationStatus,
    PaperOperationStatus,
    parse_paper_operation_receipt,
    verify_paper_operation_receipt,
)
from trading_bot.runtime.personal_desktop_paper_account_authority import (
    PersonalDesktopPaperAccountAnchor,
    PersonalDesktopPaperAccountError,
    parse_personal_desktop_paper_account_anchor,
)
from trading_bot.runtime.personal_desktop_paper_account_security import (
    PERSONAL_DESKTOP_PAPER_V2_ANCHOR,
    PERSONAL_DESKTOP_PAPER_V2_OPERATIONS,
    PERSONAL_DESKTOP_PAPER_V2_ROOT,
    PERSONAL_DESKTOP_PAPER_V2_RUNTIME,
    PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS,
    PaperReadNativeApi,
    PinnedPaperReadSession,
    PinnedTradingPaperReadSession,
    WindowsPaperReadNativeApi,
    historical_snapshot_path,
)
from trading_bot.runtime.personal_desktop_paper_account_token import (
    TradingTokenObserver,
    WindowsTradingTokenObserver,
    require_trading_token,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    require_validated_production_authority,
)

MAX_HISTORICAL_CONFIGURATIONS = 1024
MAX_HISTORICAL_CONFIGURATION_BYTES = 256 * 1024
MAX_HISTORICAL_CONFIGURATION_TOTAL_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class PersonalDesktopPaperAccountReadEvidence:
    """Immutable verified evidence, not a permit for later filesystem mutation."""

    anchor: PersonalDesktopPaperAccountAnchor
    anchor_bytes: bytes
    prior_checkpoint: VerifiedPriorCheckpoint
    lineage: PaperAccountLineageEvidence
    genesis: PaperAccountLineageArtifact
    successors: tuple[PaperAccountLineageArtifact, ...]
    reports: tuple[PaperAccountLineageArtifact, ...]
    snapshots: tuple[PaperAccountLineageArtifact, ...]
    receipts: tuple[PaperOperationReceipt, ...]


@dataclass(frozen=True, slots=True)
class PersonalDesktopPaperAccountRecoveryReadEvidence:
    """Fully verified account state with at most one terminal missing receipt.

    This evidence is read-only and non-authorizing.  In particular, the
    missing application identity is not a caller idempotency or operation ID.
    """

    account: PersonalDesktopPaperAccountReadEvidence
    missing_application_id: UUID | None
    missing_predecessor_checkpoint_id: UUID | None

    def __post_init__(self) -> None:
        missing = self.missing_application_id is not None
        if (
            type(self.account) is not PersonalDesktopPaperAccountReadEvidence
            or (missing != (self.missing_predecessor_checkpoint_id is not None))
            or (
                self.missing_application_id is not None
                and type(self.missing_application_id) is not UUID
            )
            or (
                self.missing_predecessor_checkpoint_id is not None
                and type(self.missing_predecessor_checkpoint_id) is not UUID
            )
        ):
            raise ValueError("paper-account recovery read evidence is invalid")


class ValidatedPersonalDesktopPaperAccount:
    """Process-local production read provenance; constructed only after success."""

    __slots__ = ("__weakref__",)

    def __new__(cls) -> ValidatedPersonalDesktopPaperAccount:
        raise TypeError("v2 account authority requires the production read boundary")

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("v2 account authority cannot be subclassed")

    @property
    def evidence(self) -> PersonalDesktopPaperAccountReadEvidence:
        return require_validated_personal_desktop_paper_account(self)

    @property
    def operation_root(self) -> str:
        require_validated_personal_desktop_paper_account(self)
        return PERSONAL_DESKTOP_PAPER_V2_RUNTIME


_REGISTRY: weakref.WeakKeyDictionary[
    ValidatedPersonalDesktopPaperAccount, PersonalDesktopPaperAccountReadEvidence
] = weakref.WeakKeyDictionary()
_REGISTRY_LOCK = threading.Lock()


def require_validated_personal_desktop_paper_account(
    authority: ValidatedPersonalDesktopPaperAccount,
) -> PersonalDesktopPaperAccountReadEvidence:
    """Require successful production issuance, never fields copied by a caller."""
    with _REGISTRY_LOCK:
        if (
            type(authority) is not ValidatedPersonalDesktopPaperAccount
            or authority not in _REGISTRY
        ):
            raise PersonalDesktopPaperAccountError(
                "v2 account lacks production read provenance"
            )
        return _REGISTRY[authority]


def read_personal_desktop_paper_account(
    authority: ValidatedProductionAuthority,
    *,
    historical_cycle_configuration_payloads: tuple[bytes, ...] = (),
) -> ValidatedPersonalDesktopPaperAccount:
    """Read the fixed installed account; no path, API, token, or calendar override.

    Retained A67 configurations must be supplied as exact bytes when receipts
    exist. Missing/mismatching dependencies block authority; they are never
    guessed, reconstructed from a hash, or read through a caller path.
    """
    c1 = require_validated_production_authority(authority)
    observer = WindowsTradingTokenObserver()
    # Verify the token before even constructing the filesystem boundary.
    require_trading_token(c1.approved_account_sid, observer.observe())
    evidence = _read_account_evidence(
        c1.machine_authority_id,
        c1.approved_account_sid,
        api=WindowsPaperReadNativeApi(),
        observer=observer,
        calendar=BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar()),
        configurations=historical_cycle_configuration_payloads,
    )
    require_validated_production_authority(c1)
    result = object.__new__(ValidatedPersonalDesktopPaperAccount)
    with _REGISTRY_LOCK:
        _REGISTRY[result] = evidence
    return result


def _read_account_evidence(
    machine_authority_id: str,
    trading_sid: str,
    *,
    api: PaperReadNativeApi,
    observer: TradingTokenObserver,
    calendar: IdentifiedMarketCalendar,
    configurations: tuple[bytes, ...] = (),
) -> PersonalDesktopPaperAccountReadEvidence:
    """Strict ordinary-reader core; every transition still requires a receipt."""

    recovery_read = verify_personal_desktop_paper_account_recovery_read(
        machine_authority_id,
        trading_sid,
        api=api,
        observer=observer,
        calendar=calendar,
        configurations=configurations,
    )
    if recovery_read.missing_application_id is not None:
        raise PersonalDesktopPaperAccountError(
            "finalized transition has no verified receipt; recovery is required"
        )
    return recovery_read.account


@dataclass(frozen=True, slots=True)
class _Transition:
    checkpoint: PaperAccountSuccessorCheckpoint
    report: CheckpointedPaperCycleReport
    checkpoint_artifact: PaperAccountLineageArtifact
    report_artifact: PaperAccountLineageArtifact


def _artifact(
    kind: PaperAccountLineageArtifactKind, identity: UUID, payload: bytes
) -> PaperAccountLineageArtifact:
    return PaperAccountLineageArtifact(
        kind, identity, payload, sha256(payload).hexdigest(), len(payload)
    )


def _named_uuid(name: str, prefix: str, suffix: str = "") -> UUID:
    if not name.startswith(prefix) or (suffix and not name.endswith(suffix)):
        raise PersonalDesktopPaperAccountError("unrecognized installed v2 layout")
    value = name[len(prefix) : len(name) - len(suffix) if suffix else None]
    try:
        identity = UUID(value)
    except ValueError:
        raise PersonalDesktopPaperAccountError(
            "malformed installed v2 identity name"
        ) from None
    if str(identity) != value:
        raise PersonalDesktopPaperAccountError(
            "noncanonical installed v2 identity name"
        )
    return identity


def _configurations(payloads: tuple[bytes, ...]) -> dict[tuple[str, int], bytes]:
    if type(payloads) is not tuple or len(payloads) > MAX_HISTORICAL_CONFIGURATIONS:
        raise PersonalDesktopPaperAccountError(
            "historical configuration count is invalid"
        )
    retained: dict[tuple[str, int], bytes] = {}
    total = 0
    for payload in payloads:
        if (
            type(payload) is not bytes
            or not 0 < len(payload) <= MAX_HISTORICAL_CONFIGURATION_BYTES
        ):
            raise PersonalDesktopPaperAccountError(
                "historical configuration byte bound exceeded"
            )
        total += len(payload)
        if total > MAX_HISTORICAL_CONFIGURATION_TOTAL_BYTES:
            raise PersonalDesktopPaperAccountError(
                "historical configuration total bound exceeded"
            )
        key = (sha256(payload).hexdigest(), len(payload))
        if key in retained:
            raise PersonalDesktopPaperAccountError(
                "duplicate historical configuration dependency"
            )
        retained[key] = payload
    return retained


def _read_transition(session: PinnedPaperReadSession, name: str) -> _Transition:
    application_id = _named_uuid(name, "paper-account-transition-")
    directory = PERSONAL_DESKTOP_PAPER_V2_RUNTIME + "\\" + name
    names = session.names(directory)
    reports = [n for n in names if n.startswith("checkpointed-paper-cycle-report-")]
    checkpoints = [n for n in names if n.startswith("paper-account-checkpoint-")]
    if len(names) != 2 or len(reports) != 1 or len(checkpoints) != 1:
        raise PersonalDesktopPaperAccountError("unrecognized transition contents")
    report_bytes = session.read(directory + "\\" + reports[0])
    checkpoint_bytes = session.read(directory + "\\" + checkpoints[0])
    report = parse_checkpointed_paper_cycle_report(report_bytes)
    checkpoint = parse_successor_paper_account_checkpoint(checkpoint_bytes)
    if (
        reports[0]
        != f"checkpointed-paper-cycle-report-{report.evidence.cycle_result_id}.json"
        or checkpoints[0] != f"paper-account-checkpoint-{checkpoint.checkpoint_id}.json"
        or report.evidence.application_id != application_id
        or checkpoint.application_id != application_id
    ):
        raise PersonalDesktopPaperAccountError("transition names and contents disagree")
    return _Transition(
        checkpoint,
        report,
        _artifact(
            PaperAccountLineageArtifactKind.SUCCESSOR_CHECKPOINT,
            checkpoint.checkpoint_id,
            checkpoint_bytes,
        ),
        _artifact(
            PaperAccountLineageArtifactKind.CYCLE_REPORT, report.report_id, report_bytes
        ),
    )


def _read_receipts(
    session: PinnedPaperReadSession,
) -> tuple[tuple[bytes, PaperOperationReceipt], ...]:
    receipts: list[tuple[bytes, PaperOperationReceipt]] = []
    for name in session.names(PERSONAL_DESKTOP_PAPER_V2_OPERATIONS):
        operation_id = _named_uuid(name, "paper-operation-")
        directory = PERSONAL_DESKTOP_PAPER_V2_OPERATIONS + "\\" + name
        expected = f"paper-operation-receipt-{operation_id}.json"
        if session.names(directory) != (expected,):
            raise PersonalDesktopPaperAccountError(
                "unrecognized operation receipt contents"
            )
        payload = session.read(directory + "\\" + expected)
        receipt = parse_paper_operation_receipt(payload)
        if receipt.receipt_id != operation_id:
            raise PersonalDesktopPaperAccountError(
                "receipt name and content identity disagree"
            )
        receipts.append((payload, receipt))
    return tuple(receipts)


def verify_personal_desktop_paper_account_recovery_read(
    machine_authority_id: str,
    trading_sid: str,
    *,
    api: PaperReadNativeApi,
    observer: TradingTokenObserver,
    calendar: IdentifiedMarketCalendar,
    configurations: tuple[bytes, ...] = (),
) -> PersonalDesktopPaperAccountRecoveryReadEvidence:
    """Verify a healthy account or exactly one terminal missing receipt.

    This injectable core reuses the ordinary reader's complete A61/A66/A67
    verification lineage.  It returns evidence only and never registers
    production provenance or grants mutation authority.
    """
    initial_token = observer.observe()
    require_trading_token(trading_sid, initial_token)
    configuration_bytes = _configurations(configurations)
    if api.fixed_staging_present() is not False:
        raise PersonalDesktopPaperAccountError("v2 staging absence is required")
    with PinnedTradingPaperReadSession(api, trading_sid) as session:
        root_names = session.names(PERSONAL_DESKTOP_PAPER_V2_ROOT)
        genesis_names = tuple(
            name for name in root_names if name.startswith("paper-account-genesis-")
        )
        if len(genesis_names) != 1 or set(root_names) != {
            "personal-desktop-paper-account-authority.json",
            genesis_names[0],
            "runtime",
        }:
            raise PersonalDesktopPaperAccountError(
                "unexpected immutable v2 root contents"
            )
        genesis_name = genesis_names[0]
        # A directory name supplies a candidate to pin, never account identity.
        genesis_id = _named_uuid(genesis_name, "paper-account-genesis-")
        genesis_dir = PERSONAL_DESKTOP_PAPER_V2_ROOT + "\\" + genesis_name
        genesis_file = f"paper-account-checkpoint-{genesis_id}.json"
        if session.names(genesis_dir) != (genesis_file,):
            raise PersonalDesktopPaperAccountError("unexpected GENESIS contents")
        session.pin(genesis_dir + "\\" + genesis_file)
        session.pin(PERSONAL_DESKTOP_PAPER_V2_ANCHOR)
        session.pin(PERSONAL_DESKTOP_PAPER_V2_RUNTIME)
        session.pin(PERSONAL_DESKTOP_PAPER_V2_OPERATIONS)
        anchor_bytes = session.read(PERSONAL_DESKTOP_PAPER_V2_ANCHOR)
        anchor = parse_personal_desktop_paper_account_anchor(anchor_bytes)
        # The PD1A strict parser also rederives paper_account_id from every field.
        if (
            anchor.machine_authority_id != machine_authority_id
            or anchor.approved_trading_sid != trading_sid
            or anchor.genesis_checkpoint_id != str(genesis_id)
        ):
            raise PersonalDesktopPaperAccountError(
                "v2 anchor does not match production C1/installed GENESIS"
            )
        genesis_bytes = session.read(genesis_dir + "\\" + genesis_file)
        verified_genesis = verify_genesis_paper_account_checkpoint(
            genesis_bytes,
            expected_checkpoint_sha256=anchor.genesis_sha256,
            expected_checkpoint_byte_length=anchor.genesis_byte_length,
        )
        checkpoint = verified_genesis.checkpoint
        if (
            verified_genesis.status is not PaperAccountCheckpointVerificationStatus.PASS
            or verified_genesis.diagnostics
            or checkpoint is None
            or checkpoint.checkpoint_id != genesis_id
            or checkpoint.account_state.cash <= 0
            or checkpoint.account_state.positions
            or checkpoint.account_state.realized_profit_loss != 0
            or checkpoint.metadata
        ):
            raise PersonalDesktopPaperAccountError(
                "installed GENESIS fails A61/opening policy"
            )
        genesis = _artifact(
            PaperAccountLineageArtifactKind.GENESIS_CHECKPOINT,
            genesis_id,
            genesis_bytes,
        )
        runtime_names = session.names(PERSONAL_DESKTOP_PAPER_V2_RUNTIME)
        if "paper-operations" not in runtime_names:
            raise PersonalDesktopPaperAccountError("missing paper-operations container")
        reserved_runtime_names = {"paper-operations"}
        unattended_name = PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS.rsplit(
            "\\", 1
        )[-1]
        if unattended_name in runtime_names:
            session.pin(PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS)
            reserved_runtime_names.add(unattended_name)
        transitions = tuple(
            _read_transition(session, name)
            for name in runtime_names
            if name not in reserved_runtime_names
        )
        receipts = _read_receipts(session)
        successors = tuple(t.checkpoint_artifact for t in transitions)
        reports = tuple(t.report_artifact for t in transitions)
        if len({a.artifact_id for a in successors}) != len(successors) or len(
            {a.artifact_id for a in reports}
        ) != len(reports):
            raise PersonalDesktopPaperAccountError(
                "duplicate/conflicting transition artifacts"
            )
        # Enumeration supplies candidates only. The graph's unique leaf comes
        # from parsed predecessor links; A66 alone verifies the entire lineage.
        candidates = {genesis_id, *(a.artifact_id for a in successors)} - {
            t.checkpoint.prior_checkpoint.checkpoint_id for t in transitions
        }
        if len(candidates) != 1:
            raise PersonalDesktopPaperAccountError(
                "v2 lineage has no unique terminal candidate"
            )
        terminal_id = next(iter(candidates))
        snapshots: dict[UUID, PaperAccountLineageArtifact] = {}
        references = [t.report.evidence.request.snapshot_reference for t in transitions]
        references.extend(r.intent.request.snapshot_reference for _, r in receipts)
        for reference in references:
            payload = session.read(historical_snapshot_path(reference.snapshot_id))
            artifact = PaperAccountLineageArtifact(
                PaperAccountLineageArtifactKind.DAILY_SNAPSHOT,
                reference.snapshot_id,
                payload,
                reference.artifact_sha256,
                reference.artifact_byte_length,
            )
            if (
                reference.snapshot_id in snapshots
                and snapshots[reference.snapshot_id] != artifact
            ):
                raise PersonalDesktopPaperAccountError(
                    "conflicting historical snapshot references"
                )
            snapshots[reference.snapshot_id] = artifact
        lineage_snapshots = tuple(
            snapshots[t.report.evidence.request.snapshot_reference.snapshot_id]
            for t in transitions
        )
        # A66 accepts unique artifacts; repeated snapshot dependencies are one
        # artifact, with each edge's original evidence still verified by A66.
        lineage_snapshots = tuple(
            {a.artifact_id: a for a in lineage_snapshots}.values()
        )
        lineage = verify_paper_account_lineage(
            genesis, terminal_id, successors, reports, lineage_snapshots, calendar
        )
        if (
            lineage.status is not PaperAccountLineageVerificationStatus.PASS
            or lineage.evidence is None
            or lineage.diagnostics
            or set(lineage.evidence.checkpoint_ids)
            != {genesis_id, *(a.artifact_id for a in successors)}
            or lineage.evidence.edge_count != len(transitions)
        ):
            raise PersonalDesktopPaperAccountError(
                "v2 complete A66 lineage verification failed"
            )
        missing_applications = _verify_receipts(
            receipts,
            transitions,
            genesis,
            snapshots,
            configuration_bytes,
            lineage.evidence,
            calendar,
        )
        missing_application_id: UUID | None = None
        missing_predecessor_checkpoint_id: UUID | None = None
        if len(missing_applications) > 1:
            raise PersonalDesktopPaperAccountError(
                "multiple finalized transitions lack verified receipts"
            )
        if missing_applications:
            missing_application_id = missing_applications[0]
            transition_map = {
                transition.checkpoint.application_id: transition
                for transition in transitions
            }
            missing_transition = transition_map[missing_application_id]
            missing_predecessor_checkpoint_id = (
                missing_transition.checkpoint.prior_checkpoint.checkpoint_id
            )
            checkpoint_ids = lineage.evidence.checkpoint_ids
            if (
                len(checkpoint_ids) < 2
                or missing_transition.checkpoint.checkpoint_id != terminal_id
                or checkpoint_ids[-1] != terminal_id
                or checkpoint_ids[-2] != missing_predecessor_checkpoint_id
            ):
                raise PersonalDesktopPaperAccountError(
                    "a nonterminal transition lacks its verified receipt"
                )
        # Evidence leaves this scope only after __exit__ completes every pinned
        # identity, named-object, ACL, inventory, and exact-byte reread check.
        successor_map = {a.artifact_id: a for a in successors}
        report_map = {a.artifact_id: a for a in reports}
        account_evidence = PersonalDesktopPaperAccountReadEvidence(
            anchor,
            anchor_bytes,
            verified_prior_from_full_lineage(lineage),
            lineage.evidence,
            genesis,
            tuple(successor_map[i] for i in lineage.evidence.checkpoint_ids[1:]),
            tuple(report_map[a.artifact_id] for a in lineage.evidence.report_artifacts),
            tuple(
                {
                    a.artifact_id: snapshots[a.artifact_id]
                    for a in lineage.evidence.snapshot_artifacts
                }.values()
            ),
            tuple(
                r for _, r in sorted(receipts, key=lambda item: str(item[1].receipt_id))
            ),
        )
    if api.fixed_staging_present() is not False:
        raise PersonalDesktopPaperAccountError("v2 staging absence is required")
    final_token = observer.observe()
    require_trading_token(trading_sid, final_token)
    if final_token != initial_token:
        raise PersonalDesktopPaperAccountError(
            "Trading token changed during account read"
        )
    return PersonalDesktopPaperAccountRecoveryReadEvidence(
        account=account_evidence,
        missing_application_id=missing_application_id,
        missing_predecessor_checkpoint_id=missing_predecessor_checkpoint_id,
    )


def _verify_receipts(
    receipts: tuple[tuple[bytes, PaperOperationReceipt], ...],
    transitions: tuple[_Transition, ...],
    genesis: PaperAccountLineageArtifact,
    snapshots: dict[UUID, PaperAccountLineageArtifact],
    configurations: dict[tuple[str, int], bytes],
    full_lineage: PaperAccountLineageEvidence,
    calendar: IdentifiedMarketCalendar,
) -> tuple[UUID, ...]:
    checkpoint_map = {
        t.checkpoint.checkpoint_id: t.checkpoint_artifact for t in transitions
    }
    report_map = {t.report.report_id: t.report_artifact for t in transitions}
    application_map = {t.checkpoint.application_id: t for t in transitions}
    if len(application_map) != len(transitions):
        raise PersonalDesktopPaperAccountError("duplicate successor application edges")
    seen_keys: set[UUID] = set()
    seen_applications: set[UUID] = set()
    completed: set[UUID] = set()
    used_configurations: set[tuple[str, int]] = set()
    for payload, receipt in receipts:
        if (
            receipt.intent.caller_idempotency_key in seen_keys
            or receipt.application_id in seen_applications
        ):
            raise PersonalDesktopPaperAccountError(
                "duplicate/conflicting operation receipts"
            )
        seen_keys.add(receipt.intent.caller_idempotency_key)
        seen_applications.add(receipt.application_id)
        prior = receipt.prior_lineage_evidence
        if (
            prior.checkpoint_ids
            != full_lineage.checkpoint_ids[: len(prior.checkpoint_ids)]
        ):
            raise PersonalDesktopPaperAccountError(
                "receipt prior is not in the installed lineage"
            )
        config = receipt.intent.cycle_configuration_artifact
        key = (config.sha256, config.byte_length)
        if key not in configurations:
            raise PersonalDesktopPaperAccountError(
                "exact historical cycle configuration is unavailable"
            )
        used_configurations.add(key)
        transition = application_map.get(receipt.application_id)
        if receipt.status is PaperOperationStatus.COMPLETED:
            if transition is None:
                raise PersonalDesktopPaperAccountError(
                    "completed receipt has no installed transition"
                )
            completed.add(receipt.application_id)
        elif transition is not None:
            raise PersonalDesktopPaperAccountError(
                "failed receipt conflicts with a transition"
            )
        try:
            verified = verify_paper_operation_receipt(
                payload,
                cycle_configuration_payload=configurations[key],
                prior_genesis_checkpoint=genesis,
                prior_successor_checkpoints=tuple(
                    checkpoint_map[i] for i in prior.checkpoint_ids[1:]
                ),
                prior_cycle_reports=tuple(
                    report_map[a.artifact_id] for a in prior.report_artifacts
                ),
                prior_snapshots=tuple(
                    {
                        a.artifact_id: snapshots[a.artifact_id]
                        for a in prior.snapshot_artifacts
                    }.values()
                ),
                completed_snapshot_payload=snapshots[
                    receipt.intent.completed_snapshot_artifact.artifact_id
                ].payload,
                calendar=calendar,
                transition_report_payload=transition.report_artifact.payload
                if transition
                else None,
                successor_checkpoint_payload=transition.checkpoint_artifact.payload
                if transition
                else None,
                expected_receipt_sha256=sha256(payload).hexdigest(),
                expected_receipt_byte_length=len(payload),
            )
        except KeyError:
            raise PersonalDesktopPaperAccountError(
                "receipt dependency is absent from installed lineage"
            ) from None
        if (
            verified.status is not PaperOperationReceiptVerificationStatus.PASS
            or verified.diagnostics
            or verified.receipt != receipt
        ):
            raise PersonalDesktopPaperAccountError(
                "installed receipt fails A67 verification"
            )
    if used_configurations != set(configurations):
        raise PersonalDesktopPaperAccountError(
            "unrecognized historical configuration dependency"
        )
    return tuple(sorted(set(application_map) - completed, key=str))
