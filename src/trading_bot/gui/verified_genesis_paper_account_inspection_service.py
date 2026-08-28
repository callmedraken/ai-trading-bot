"""Qt-free adaptation of one explicit verified GENESIS checkpoint artifact."""

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
from trading_bot.ledger import CompactPaperLedgerRestorationEvidence, PaperLedger
from trading_bot.runtime.paper_account_checkpoint import (
    MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES,
    PaperAccountCheckpoint,
    PaperAccountCheckpointAccountState,
    PaperAccountCheckpointKind,
    PaperAccountCheckpointVerificationResult,
    PaperAccountCheckpointVerificationStatus,
    verify_genesis_paper_account_checkpoint,
)

_VERIFIED_MESSAGE = "One local GENESIS paper-account checkpoint was verified offline."


class VerifiedGenesisPaperAccountInspectionService:
    """Inspect one explicit GENESIS checkpoint without operational side effects."""

    def __init__(
        self,
        checkpoint_path: Path,
        *,
        expected_sha256: str | None = None,
        expected_byte_length: int | None = None,
    ) -> None:
        self._checkpoint_path = checkpoint_path
        self._expected_sha256 = expected_sha256
        self._expected_byte_length = expected_byte_length

    def get_paper_account_state(self) -> PaperAccountPageState:
        """Return one bounded verified state without exposing inspection failures."""
        try:
            payload = _read_explicit_checkpoint(self._checkpoint_path)
            verification = verify_genesis_paper_account_checkpoint(
                payload,
                expected_checkpoint_sha256=self._expected_sha256,
                expected_checkpoint_byte_length=self._expected_byte_length,
            )
            return _adapt_verification(verification)
        except Exception:
            return unavailable_paper_account_state()


def _read_explicit_checkpoint(path: Path) -> bytes:
    if not isinstance(path, Path):
        raise TypeError("paper-account checkpoint path must be a Path")
    with path.open("rb") as stream:
        payload = stream.read(MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES + 1)
    if len(payload) > MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES:
        raise ValueError("paper-account checkpoint exceeds the supported size bound")
    return payload


def _adapt_verification(
    verification: PaperAccountCheckpointVerificationResult,
) -> PaperAccountPageState:
    if type(verification) is not PaperAccountCheckpointVerificationResult:
        raise TypeError("paper-account verification result has an unsupported type")
    if (
        verification.status is not PaperAccountCheckpointVerificationStatus.PASS
        or type(verification.checkpoint) is not PaperAccountCheckpoint
        or type(verification.restored_ledger) is not PaperLedger
        or type(verification.restoration_evidence)
        is not CompactPaperLedgerRestorationEvidence
        or verification.diagnostics
    ):
        return unavailable_paper_account_state()

    checkpoint = verification.checkpoint
    account_state = checkpoint.account_state
    if (
        checkpoint.kind is not PaperAccountCheckpointKind.GENESIS
        or type(account_state) is not PaperAccountCheckpointAccountState
    ):
        return unavailable_paper_account_state()

    return PaperAccountPageState(
        status=PaperAccountPageStatus.VERIFIED,
        message=_VERIFIED_MESSAGE,
        account=VerifiedPaperAccountView(
            checkpoint_kind=PaperAccountCheckpointKindView.GENESIS,
            sequence=checkpoint.sequence,
            checkpoint_id=checkpoint.checkpoint_id,
            lineage_id=checkpoint.lineage_id,
            account_state_id=account_state.account_state_id,
            compact_state_id=account_state.compact_ledger_state_id,
            as_of=account_state.as_of,
            cash=account_state.cash,
            realized_profit_loss=account_state.realized_profit_loss,
            positions=tuple(
                PaperAccountPositionView(
                    symbol=str(position.symbol),
                    quantity=position.quantity,
                    total_cost_basis=position.total_cost_basis,
                    average_cost=position.average_cost,
                )
                for position in account_state.positions
            ),
            artifact_sha256=verification.checkpoint_sha256,
            artifact_byte_length=verification.checkpoint_byte_length,
        ),
    )
