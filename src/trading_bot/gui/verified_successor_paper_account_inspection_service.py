"""Qt-free adaptation of one explicit verified successor-checkpoint edge."""

from __future__ import annotations

from pathlib import Path

from trading_bot.gui.paper_account_models import (
    PaperAccountCheckpointKindView,
    PaperAccountPageState,
    PaperAccountPageStatus,
    PaperAccountPositionView,
    VerifiedPaperAccountView,
    unavailable_paper_account_state,
)
from trading_bot.ledger import PaperLedger
from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES,
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
)
from trading_bot.runtime.checkpointed_paper_cycle_report import (
    MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES,
)
from trading_bot.runtime.checkpointed_verified_snapshot_execution import (
    CheckpointedVerifiedSnapshotPaperCycleResult,
    VerifiedPriorCheckpoint,
    VerifiedPriorCheckpointKind,
)
from trading_bot.runtime.paper_account_checkpoint import (
    MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES,
)
from trading_bot.runtime.paper_account_successor_checkpoint import (
    MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES,
    PaperAccountCheckpointEdgeVerificationResult,
    PaperAccountCheckpointEdgeVerificationStatus,
    PaperAccountSuccessorCheckpoint,
    PaperAccountSuccessorCheckpointKind,
    SuccessorPaperAccountState,
    verify_checkpointed_paper_cycle_successor_edge,
)

_VERIFIED_MESSAGE = (
    "One local successor paper-account checkpoint edge was verified offline."
)


class VerifiedSuccessorPaperAccountInspectionService:
    """Inspect one explicit successor edge without operational side effects."""

    def __init__(
        self,
        prior_checkpoint_path: Path,
        snapshot_path: Path,
        cycle_report_path: Path,
        successor_checkpoint_path: Path,
        *,
        expected_successor_sha256: str | None = None,
        expected_successor_byte_length: int | None = None,
        verified_prior: VerifiedPriorCheckpoint | None = None,
    ) -> None:
        self._prior_checkpoint_path = prior_checkpoint_path
        self._snapshot_path = snapshot_path
        self._cycle_report_path = cycle_report_path
        self._successor_checkpoint_path = successor_checkpoint_path
        self._expected_successor_sha256 = expected_successor_sha256
        self._expected_successor_byte_length = expected_successor_byte_length
        self._verified_prior = verified_prior

    def get_paper_account_state(self) -> PaperAccountPageState:
        """Return one bounded verified state without exposing inspection failures."""
        try:
            prior_limit = _prior_checkpoint_limit(self._verified_prior)
            prior_payload = _read_explicit_artifact(
                self._prior_checkpoint_path,
                prior_limit,
            )
            snapshot_payload = _read_explicit_artifact(
                self._snapshot_path,
                MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES,
            )
            report_payload = _read_explicit_artifact(
                self._cycle_report_path,
                MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES,
            )
            successor_payload = _read_explicit_artifact(
                self._successor_checkpoint_path,
                MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES,
            )
            verification = verify_checkpointed_paper_cycle_successor_edge(
                report_payload,
                prior_payload,
                snapshot_payload,
                successor_payload,
                BoundMarketCalendar(
                    XNYS_CALENDAR_DESCRIPTOR,
                    NYSEMarketCalendar(),
                ),
                expected_successor_sha256=self._expected_successor_sha256,
                expected_successor_byte_length=self._expected_successor_byte_length,
                verified_prior=self._verified_prior,
            )
            return _adapt_verification(verification)
        except Exception:
            return unavailable_paper_account_state()


def _prior_checkpoint_limit(verified_prior: object) -> int:
    if verified_prior is None:
        return MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES
    if type(verified_prior) is not VerifiedPriorCheckpoint:
        raise TypeError("verified prior has an unsupported type")
    if verified_prior.kind is VerifiedPriorCheckpointKind.GENESIS:
        return MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES
    if verified_prior.kind is VerifiedPriorCheckpointKind.CYCLE_SUCCESSOR:
        return MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES
    raise TypeError("verified prior has an unsupported kind")


def _read_explicit_artifact(path: Path, maximum_bytes: int) -> bytes:
    if not isinstance(path, Path):
        raise TypeError("paper-account proof artifact path must be a Path")
    with path.open("rb") as stream:
        payload = stream.read(maximum_bytes + 1)
    if len(payload) > maximum_bytes:
        raise ValueError("paper-account proof artifact exceeds its size bound")
    return payload


def _adapt_verification(
    verification: PaperAccountCheckpointEdgeVerificationResult,
) -> PaperAccountPageState:
    if type(verification) is not PaperAccountCheckpointEdgeVerificationResult:
        raise TypeError("successor-edge verification result has an unsupported type")
    if (
        verification.status is not PaperAccountCheckpointEdgeVerificationStatus.PASS
        or type(verification.cycle_result)
        is not CheckpointedVerifiedSnapshotPaperCycleResult
        or type(verification.successor_checkpoint)
        is not PaperAccountSuccessorCheckpoint
        or type(verification.restored_successor_ledger) is not PaperLedger
        or verification.diagnostics
    ):
        return unavailable_paper_account_state()

    successor = verification.successor_checkpoint
    account_state = successor.account_state
    if (
        successor.kind is not PaperAccountSuccessorCheckpointKind.CYCLE_SUCCESSOR
        or type(account_state) is not SuccessorPaperAccountState
    ):
        return unavailable_paper_account_state()

    compact_state = account_state.compact_state
    return PaperAccountPageState(
        status=PaperAccountPageStatus.VERIFIED,
        message=_VERIFIED_MESSAGE,
        account=VerifiedPaperAccountView(
            checkpoint_kind=PaperAccountCheckpointKindView.CYCLE_SUCCESSOR,
            sequence=successor.sequence,
            checkpoint_id=successor.checkpoint_id,
            lineage_id=successor.lineage_id,
            account_state_id=account_state.account_state_id,
            compact_state_id=compact_state.compact_state_id,
            as_of=account_state.as_of,
            cash=account_state.cash,
            realized_profit_loss=account_state.realized_profit_loss_after,
            positions=tuple(
                PaperAccountPositionView(
                    symbol=str(position.symbol),
                    quantity=position.quantity,
                    total_cost_basis=position.total_cost_basis,
                    average_cost=position.average_cost,
                )
                for position in account_state.positions
            ),
            artifact_sha256=verification.successor_sha256,
            artifact_byte_length=verification.successor_byte_length,
        ),
    )
