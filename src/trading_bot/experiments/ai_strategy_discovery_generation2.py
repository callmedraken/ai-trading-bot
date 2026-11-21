"""Bounded, in-memory Generation-2 confirmation evaluation.

This module composes only the six frozen G1 parent pairs. It has no artifact
reader, provider, AI, broker, CLI, or candidate-lifecycle interface. The
one-proposal evaluator is intended for the accepted G2 batch runner after the
complete population has been accepted.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import ClassVar
from uuid import UUID
from zoneinfo import ZoneInfo

from trading_bot.domain import Bar
from trading_bot.experiments.ai_strategy_discovery import (
    ConjunctiveTrendSpec,
    ProposalKind,
    ProposalSemanticStatus,
    ResearchProposal,
    StrategySpec,
    VisibilityStage,
    frozen_generation2_parent_pairs,
)
from trading_bot.experiments.ai_strategy_discovery_generation1 import (
    generation1_signal_series,
)
from trading_bot.experiments.filtered_trend_campaign import (
    CellEvidence,
    Regime,
    evaluate_prepared_signal_cell,
    semantic_identity,
)
from trading_bot.experiments.filtered_trend_data import (
    PRICE_BASIS,
    UNIVERSE,
    MultiAssetDataset,
    ProviderProvenance,
)

NY = ZoneInfo("America/New_York")
VIEW_START = date(2016, 1, 1)
CONFIRMATION_START = date(2022, 1, 1)
CONFIRMATION_END_EXCLUSIVE = date(2024, 1, 1)
RESULT_SCHEMA = "ai-strategy-discovery-generation2-result/v1"

_ANNUAL_REGIMES = (
    Regime("2022", date(2022, 1, 1), date(2023, 1, 1)),
    Regime("2023", date(2023, 1, 1), date(2024, 1, 1)),
)
_CONTINUOUS_REGIME = Regime(
    "continuous", CONFIRMATION_START, CONFIRMATION_END_EXCLUSIVE
)
_G2_REGIMES = _ANNUAL_REGIMES + (_CONTINUOUS_REGIME,)
_EXPECTED_CELL_ORDER = tuple(
    (symbol, regime.label) for symbol in UNIVERSE for regime in _G2_REGIMES
)

_FROZEN_G2_PARENT_PAIRS = frozen_generation2_parent_pairs()
_PARENT_ID_BY_SPEC = {
    spec: parent_id for pair in _FROZEN_G2_PARENT_PAIRS for parent_id, spec in pair
}
_ALLOWED_PARENT_PAIRS = frozenset(
    frozenset((left[0], right[0])) for left, right in _FROZEN_G2_PARENT_PAIRS
)


@dataclass(frozen=True, slots=True)
class SymbolConfirmationBars:
    """One ordered symbol series retaining warmup through confirmation only."""

    symbol: str
    bars: tuple[Bar, ...]

    def __post_init__(self) -> None:
        if type(self.symbol) is not str or self.symbol not in UNIVERSE:
            raise ValueError("symbol is outside the accepted A147 universe")
        if type(self.bars) is not tuple or not self.bars:
            raise ValueError("confirmation bars must be a nonempty immutable tuple")
        previous: datetime | None = None
        dates: list[date] = []
        for bar in self.bars:
            if type(bar) is not Bar or bar.symbol.value != self.symbol:
                raise ValueError("bars must match their ordered symbol series")
            if bar.timestamp.tzinfo is None or bar.timestamp.utcoffset() is None:
                raise ValueError("daily confirmation timestamps must be timezone-aware")
            if previous is not None and bar.timestamp <= previous:
                raise ValueError("confirmation bars must be strictly ordered")
            previous = bar.timestamp
            session = bar.timestamp.astimezone(NY).date()
            if not VIEW_START <= session < CONFIRMATION_END_EXCLUSIVE:
                raise ValueError(
                    "confirmation view cannot retain bars outside 2016-2023"
                )
            dates.append(session)
        if any(left >= right for left, right in zip(dates, dates[1:], strict=False)):
            raise ValueError("daily confirmation sessions must be unique and ordered")
        first_confirmation_index = next(
            (
                index
                for index, session in enumerate(dates)
                if session >= CONFIRMATION_START
            ),
            None,
        )
        if first_confirmation_index is None or first_confirmation_index < 253:
            raise ValueError(
                "confirmation history lacks the accepted 253-session warmup"
            )
        if not any(
            session < date(2023, 1, 1) for session in dates[first_confirmation_index:]
        ):
            raise ValueError("confirmation view lacks calendar 2022")
        if not any(session >= date(2023, 1, 1) for session in dates):
            raise ValueError("confirmation view lacks calendar 2023")


@dataclass(frozen=True, slots=True, init=False)
class ConfirmationView:
    """Immutable accepted A147 input with 2022-2023 as its only report window.

    Pre-2022 bars remain available for point-in-time signal warmup. Bars on or
    after 2024-01-01 are rejected before any signal or replay is evaluated.
    """

    dataset_identity: str
    price_basis: str
    provider_provenance: ProviderProvenance
    symbol_bars: tuple[SymbolConfirmationBars, ...]
    identity: str

    def __init__(self, dataset: MultiAssetDataset) -> None:
        if type(dataset) is not MultiAssetDataset:
            raise ValueError("an accepted in-memory MultiAssetDataset is required")
        if dataset.price_basis != PRICE_BASIS or dataset.symbols != UNIVERSE:
            raise ValueError(
                "dataset price basis or universe is not the accepted A147 input"
            )
        if not dataset.datasets or any(
            item.provider_provenance != ProviderProvenance()
            for item in dataset.datasets
        ):
            raise ValueError(
                "dataset provenance is outside the accepted adjusted basis"
            )
        _require_uuid5(dataset.identity, "dataset identity")

        clipped: list[SymbolConfirmationBars] = []
        for source in dataset.datasets:
            if any(
                bar.timestamp.astimezone(NY).date() >= CONFIRMATION_END_EXCLUSIVE
                for bar in source.bars
            ):
                raise ValueError("2024 and later sessions are outside G2 confirmation")
            bars = tuple(
                bar
                for bar in source.bars
                if VIEW_START
                <= bar.timestamp.astimezone(NY).date()
                < CONFIRMATION_END_EXCLUSIVE
            )
            clipped.append(SymbolConfirmationBars(source.symbol, bars))
        symbol_bars = tuple(clipped)
        view_identity = semantic_identity(
            "generation2-confirmation-view",
            (
                dataset.identity,
                PRICE_BASIS,
                VIEW_START.isoformat(),
                CONFIRMATION_START.isoformat(),
                CONFIRMATION_END_EXCLUSIVE.isoformat(),
                UNIVERSE,
            ),
        )
        object.__setattr__(self, "dataset_identity", dataset.identity)
        object.__setattr__(self, "price_basis", PRICE_BASIS)
        object.__setattr__(
            self, "provider_provenance", dataset.datasets[0].provider_provenance
        )
        object.__setattr__(self, "symbol_bars", symbol_bars)
        object.__setattr__(self, "identity", view_identity)

    @classmethod
    def from_dataset(cls, dataset: MultiAssetDataset) -> ConfirmationView:
        """Validate and bind the fixed in-memory A147 dataset."""
        return cls(dataset)

    @property
    def report_window(self) -> tuple[date, date]:
        """The half-open reported confirmation interval."""
        return CONFIRMATION_START, CONFIRMATION_END_EXCLUSIVE

    @property
    def regimes(self) -> tuple[Regime, ...]:
        """2022, 2023, and continuous 2022-2023 report slices."""
        return _G2_REGIMES

    def bars_for(self, symbol: str) -> tuple[Bar, ...]:
        for item in self.symbol_bars:
            if item.symbol == symbol:
                return item.bars
        raise ValueError("symbol is outside the accepted A147 universe")


@dataclass(frozen=True, slots=True)
class Generation2ProgramResult:
    """Deterministic 2022-2023 confirmation cells for one accepted G2 proposal."""

    proposal_id: str
    semantic_program_id: str
    dataset_identity: str
    confirmation_view_identity: str
    cells: tuple[CellEvidence, ...]
    identity: str = field(init=False)

    schema: ClassVar[str] = RESULT_SCHEMA

    def __post_init__(self) -> None:
        _require_uuid5(self.proposal_id, "proposal identity")
        _require_uuid5(self.semantic_program_id, "semantic program identity")
        _require_uuid5(self.dataset_identity, "dataset identity")
        _require_uuid5(self.confirmation_view_identity, "confirmation view identity")
        if (
            type(self.cells) is not tuple
            or any(type(cell) is not CellEvidence for cell in self.cells)
            or tuple((cell.symbol, cell.regime) for cell in self.cells)
            != _EXPECTED_CELL_ORDER
        ):
            raise ValueError("G2 result cells must be complete and canonically ordered")
        if any(cell.candidate_id != self.proposal_id for cell in self.cells):
            raise ValueError("G2 result cells must bind the exact proposal")
        for cell in self.cells:
            regime = next(item for item in _G2_REGIMES if item.label == cell.regime)
            first = _session_date(cell.first_session)
            last = _session_date(cell.last_session)
            if first < regime.start or last >= regime.end or first > last:
                raise ValueError("G2 result evidence escaped its frozen date slice")
            if cell.session_count < 1:
                raise ValueError("G2 result evidence must contain scored sessions")
            for metrics in (
                cell.base,
                cell.stress,
                cell.buy_and_hold,
                cell.buy_and_hold_stress,
            ):
                for fill in metrics.fills:
                    fill_session = _session_date(fill.session)
                    if not regime.start <= fill_session < regime.end:
                        raise ValueError(
                            "G2 fill evidence escaped its scored date slice"
                        )
                    if fill.information_through is not None and not (
                        _session_datetime(fill.information_through)
                        < _session_datetime(fill.session)
                    ):
                        raise ValueError("G2 fill information must precede execution")
        material = (
            RESULT_SCHEMA,
            self.proposal_id,
            self.semantic_program_id,
            self.dataset_identity,
            self.confirmation_view_identity,
            tuple(asdict(cell) for cell in self.cells),
        )
        object.__setattr__(
            self,
            "identity",
            semantic_identity("generation2-program-result", material),
        )


def evaluate_generation2_program(
    proposal: ResearchProposal, view: ConfirmationView
) -> Generation2ProgramResult:
    """Evaluate one accepted frozen G2 proposal over the bounded view.

    The caller is the G2 one-shot batch runner, which accepts the complete
    frozen population before invoking this per-proposal seam.
    """
    _validate_g2_proposal(proposal)
    if type(view) is not ConfirmationView:
        raise ValueError("a bounded Generation-2 ConfirmationView is required")

    components = proposal.strategy_spec.components
    cells: list[CellEvidence] = []
    for item in view.symbol_bars:
        parent_states = tuple(
            _parent_position_states(spec, item.bars) for spec in components
        )
        if any(len(states) != len(item.bars) for states in parent_states):
            raise ValueError("G1 parent signal series length mismatch")
        combined_states = _combine_position_states(*parent_states)
        for regime in _G2_REGIMES:
            cell = evaluate_prepared_signal_cell(
                item.bars,
                regime,
                proposal.proposal_id,
                prepared_states=combined_states,
            )
            if cell.symbol != item.symbol or cell.regime != regime.label:
                raise ValueError("G2 evaluator produced a mismatched confirmation cell")
            cells.append(cell)

    return Generation2ProgramResult(
        proposal.proposal_id,
        proposal.semantic_program_id,
        view.dataset_identity,
        view.identity,
        tuple(cells),
    )


def _validate_g2_proposal(proposal: ResearchProposal) -> None:
    if type(proposal) is not ResearchProposal:
        raise ValueError("a canonical ResearchProposal is required")
    if (
        proposal.generation != 2
        or proposal.proposal_kind is not ProposalKind.RECOMBINATION
        or proposal.semantic_status is not ProposalSemanticStatus.SUPPORTED
        or type(proposal.strategy_spec) is not ConjunctiveTrendSpec
    ):
        raise ValueError("only supported Generation-2 recombinations can be evaluated")
    visibility = proposal.information_visibility
    if (
        visibility.stage is not VisibilityStage.GENERATION_2_PRE_CONFIRMATION
        or visibility.confirmation_results_visible
        or visibility.final_holdout_accessed
        or len(visibility.visible_generation1_diagnostics) != 2
        or tuple(
            item.parent_proposal_id
            for item in visibility.visible_generation1_diagnostics
        )
        != proposal.parent_proposal_ids
    ):
        raise ValueError("G2 proposal must bind both exact visible G1 diagnostics")
    spec_components = proposal.strategy_spec.components
    if type(spec_components) is not tuple or len(spec_components) != 2:
        raise ValueError("G2 recombination requires exactly two typed G1 parents")
    if any(component not in _PARENT_ID_BY_SPEC for component in spec_components):
        raise ValueError("G2 component is not an exact supported G1 semantic program")
    component_parent_ids = frozenset(
        _PARENT_ID_BY_SPEC[item] for item in spec_components
    )
    if component_parent_ids not in _ALLOWED_PARENT_PAIRS:
        raise ValueError("G2 component pair is outside the six frozen compositions")
    if component_parent_ids != frozenset(proposal.parent_proposal_ids):
        raise ValueError("G2 component semantics do not match the exact parent IDs")
    if len(proposal.parent_proposal_ids) != 2:
        raise ValueError("G2 recombination requires exactly two distinct parents")


def _parent_position_states(
    spec: StrategySpec,
    bars: tuple[Bar, ...],
) -> tuple[str, ...]:
    """Return one point-in-time LONG/FLAT state per close for one G1 parent."""
    signals = generation1_signal_series(spec, bars)
    if len(signals) != len(bars):
        raise ValueError("G1 parent signal series length mismatch")

    position = "SELL"
    states: list[str] = []
    for signal in signals:
        if signal == "BUY":
            position = "BUY"
        elif signal == "SELL":
            position = "SELL"
        elif signal != "HOLD":
            raise ValueError("G1 parent emitted an unsupported signal state")
        states.append(position)
    return tuple(states)


def _combine_position_states(
    first: tuple[str, ...], second: tuple[str, ...]
) -> tuple[str, ...]:
    """Apply fixed ALL_OF to two already-resolved LONG/FLAT state tapes."""
    if (
        type(first) is not tuple
        or type(second) is not tuple
        or len(first) != len(second)
    ):
        raise ValueError("G2 parent position states must be equal-length tuples")
    if any(state not in ("BUY", "SELL") for state in (*first, *second)):
        raise ValueError("G2 parents must supply resolved LONG/FLAT position states")
    return tuple(
        "BUY" if left == "BUY" and right == "BUY" else "SELL"
        for left, right in zip(first, second, strict=True)
    )


def _session_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError("session timestamps must be ISO-8601") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("session timestamps must be timezone-aware")
    return parsed


def _session_date(value: str) -> date:
    return _session_datetime(value).astimezone(NY).date()


def _require_uuid5(value: str, label: str) -> None:
    try:
        parsed = UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise ValueError(f"{label} must be a canonical UUID5") from None
    if str(parsed) != value or parsed.version != 5:
        raise ValueError(f"{label} must be a canonical UUID5")
