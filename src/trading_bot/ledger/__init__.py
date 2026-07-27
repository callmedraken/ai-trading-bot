"""Public API for simulated account accounting."""

from trading_bot.ledger.checkpoint_state import (
    COMPACT_PAPER_LEDGER_ARITHMETIC_VERSION,
    COMPACT_PAPER_LEDGER_STATE_MATERIAL_VERSION,
    COMPACT_PAPER_LEDGER_STATE_NAMESPACE,
    MAX_COMPACT_PAPER_LEDGER_POSITIONS,
    CompactPaperLedgerHistoryMode,
    CompactPaperLedgerPosition,
    CompactPaperLedgerReconciliationStatus,
    CompactPaperLedgerRestorationEvidence,
    CompactPaperLedgerState,
    compact_paper_ledger_state_id,
    derive_compact_paper_ledger_average_cost,
    export_compact_paper_ledger_state,
    restore_paper_ledger_from_compact_state,
)
from trading_bot.ledger.exceptions import (
    CompactPaperLedgerRestorationError,
    DuplicateFillError,
    InsufficientCashError,
    InsufficientPositionError,
    InvalidCompactPaperLedgerStateError,
    InvalidPaperLedgerInitializationError,
    LedgerError,
    PositionNotFoundError,
    PriceNotAvailableError,
)
from trading_bot.ledger.initialization import (
    PaperLedgerInitializationEvidence,
    PaperLedgerInitializationMode,
    PaperLedgerInitializationPosition,
    PaperLedgerInitializationRequest,
    initialize_paper_ledger,
)
from trading_bot.ledger.ledger import PaperLedger
from trading_bot.ledger.models import AccountSnapshot

__all__ = [
    "AccountSnapshot",
    "COMPACT_PAPER_LEDGER_ARITHMETIC_VERSION",
    "COMPACT_PAPER_LEDGER_STATE_MATERIAL_VERSION",
    "COMPACT_PAPER_LEDGER_STATE_NAMESPACE",
    "CompactPaperLedgerHistoryMode",
    "CompactPaperLedgerPosition",
    "CompactPaperLedgerReconciliationStatus",
    "CompactPaperLedgerRestorationError",
    "CompactPaperLedgerRestorationEvidence",
    "CompactPaperLedgerState",
    "DuplicateFillError",
    "InsufficientCashError",
    "InsufficientPositionError",
    "InvalidCompactPaperLedgerStateError",
    "InvalidPaperLedgerInitializationError",
    "LedgerError",
    "MAX_COMPACT_PAPER_LEDGER_POSITIONS",
    "PaperLedger",
    "PaperLedgerInitializationEvidence",
    "PaperLedgerInitializationMode",
    "PaperLedgerInitializationPosition",
    "PaperLedgerInitializationRequest",
    "PositionNotFoundError",
    "PriceNotAvailableError",
    "compact_paper_ledger_state_id",
    "derive_compact_paper_ledger_average_cost",
    "export_compact_paper_ledger_state",
    "initialize_paper_ledger",
    "restore_paper_ledger_from_compact_state",
]
