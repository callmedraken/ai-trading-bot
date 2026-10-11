"""Read-only current-product prior from an already-open exact review-paper store."""

from __future__ import annotations

from dataclasses import InitVar, dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Context, localcontext
from uuid import UUID

from trading_bot.domain import Position, Symbol
from trading_bot.ledger import CompactPaperLedgerState
from trading_bot.review_paper.store import ReviewPaperStore

# Freeze the retained PaperLedger arithmetic; never inherit caller precision/traps.
_LEDGER_CONTEXT = Context(prec=28, rounding=ROUND_HALF_EVEN)
_PRIOR_AUTHORITY = object()


@dataclass(frozen=True, slots=True)
class ReviewPaperStrategyPrior:
    """Immutable evidence of one stable durable history; no execution authority."""

    symbol: Symbol
    compact_state: CompactPaperLedgerState
    fill_ids: tuple[UUID, ...]
    positions: tuple[Position, ...]
    _authority: InitVar[object]

    def __post_init__(self, _authority: object) -> None:
        if _authority is not _PRIOR_AUTHORITY:
            raise ValueError("prior must come from exact ReviewPaperStore history")
        if type(self.symbol) is not Symbol:
            raise TypeError("prior symbol must be exact")
        if type(self.compact_state) is not CompactPaperLedgerState:
            raise TypeError("prior compact state must be exact")
        if (
            type(self.fill_ids) is not tuple
            or any(type(item) is not UUID for item in self.fill_ids)
            or len(set(self.fill_ids)) != len(self.fill_ids)
            or any(item.symbol != self.symbol for item in self.compact_state.positions)
            or type(self.positions) is not tuple
            or any(type(item) is not Position for item in self.positions)
            or tuple((item.symbol, item.quantity) for item in self.positions)
            != tuple(
                (item.symbol, item.quantity) for item in self.compact_state.positions
            )
        ):
            raise ValueError("prior history/account state is inconsistent")

    @property
    def sequence(self) -> int:
        return len(self.fill_ids)


def build_review_paper_strategy_prior(
    store: ReviewPaperStore, *, symbol: Symbol, as_of: datetime
) -> ReviewPaperStrategyPrior:
    """Reconstruct durable accounting without initializing or writing a store."""
    if type(store) is not ReviewPaperStore:
        raise TypeError("store must be exactly ReviewPaperStore")
    if type(symbol) is not Symbol:
        raise TypeError("symbol must be exact")
    if type(as_of) is not datetime or as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be an explicit aware datetime")
    as_of = as_of.astimezone(UTC)
    if not store.path.is_file():
        raise ValueError("already-open durable store is missing")
    with localcontext(_LEDGER_CONTEXT):
        history = store.history()
        if any(
            item.intent.symbol != symbol or item.filled_at > as_of for item in history
        ):
            raise ValueError(
                "durable history contains an unsupported symbol or future fill"
            )
        ledger = store.reconstruct_ledger()
        after = store.history()
        fills = ledger.fills
        if (
            after != history
            or len(fills) != len(history)
            or any(
                (
                    fill.fill_id,
                    fill.order_id,
                    fill.symbol,
                    fill.side,
                    fill.quantity,
                    fill.price,
                    fill.commission,
                    fill.filled_at,
                )
                != (
                    record.fill_id,
                    record.intent.order_id,
                    record.intent.symbol,
                    record.intent.side,
                    record.intent.approved_quantity,
                    record.fill_price,
                    record.commission,
                    record.filled_at,
                )
                for fill, record in zip(fills, history, strict=True)
            )
        ):
            raise ValueError(
                "durable history changed or ledger reconstruction disagrees"
            )
        state = ledger.export_compact_checkpoint_state(as_of=as_of)
        positions = tuple(ledger.positions.values())
    return ReviewPaperStrategyPrior(
        symbol,
        state,
        tuple(item.fill_id for item in history),
        positions,
        _PRIOR_AUTHORITY,
    )
