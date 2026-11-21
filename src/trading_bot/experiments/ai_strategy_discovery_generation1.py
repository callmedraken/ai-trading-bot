"""Bounded, deterministic daily Generation-1 strategy evaluation.

This module accepts only in-memory A147 daily adjusted data and closed typed
G1 proposals. It exposes discovery-period evidence only; it has no artifact
reader, provider, AI, broker, or lifecycle interface.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Context, Decimal, localcontext
from typing import ClassVar
from uuid import UUID
from zoneinfo import ZoneInfo

from trading_bot.domain import Bar
from trading_bot.experiments.ai_strategy_discovery import (
    AbsoluteMomentumSpec,
    MomentumGate,
    MultiHorizonTrendSpec,
    ProposalSemanticStatus,
    ResearchProposal,
    TrendVote,
    compile_generation1_program,
)
from trading_bot.experiments.filtered_trend_campaign import (
    CellEvidence,
    Regime,
    _evaluate_prepared_cell,
    evaluate_cell,
    regime_plan,
    semantic_identity,
)
from trading_bot.experiments.filtered_trend_data import (
    MAX_DECIMAL_TEXT_LENGTH,
    PRICE_BASIS,
    UNIVERSE,
    MultiAssetDataset,
    ProviderProvenance,
)
from trading_bot.experiments.filtered_trend_strategies import StrategyConfig

NY = ZoneInfo("America/New_York")
DISCOVERY_START = date(2019, 1, 1)
DISCOVERY_END_EXCLUSIVE = date(2022, 1, 1)
VIEW_START = date(2016, 1, 1)
VIEW_END_EXCLUSIVE = DISCOVERY_END_EXCLUSIVE
RESULT_SCHEMA = "ai-strategy-discovery-generation1-result/v1"

_ANNUAL_REGIMES = tuple(
    Regime(str(year), date(year, 1, 1), date(year + 1, 1, 1))
    for year in (2019, 2020, 2021)
)
_CONTINUOUS_REGIME = Regime("continuous", DISCOVERY_START, DISCOVERY_END_EXCLUSIVE)
_G1_REGIMES = _ANNUAL_REGIMES + (_CONTINUOUS_REGIME,)
_A147_REGIMES_BY_LABEL = {item.label: item for item in regime_plan()}
_EXPECTED_CELL_ORDER = tuple(
    (symbol, regime.label) for symbol in UNIVERSE for regime in _G1_REGIMES
)
_SMA_CONTEXT = Context(prec=2 * MAX_DECIMAL_TEXT_LENGTH + 3)


@dataclass(frozen=True, slots=True)
class SymbolDiscoveryBars:
    """One ordered symbol series clipped to the G1 visibility boundary."""

    symbol: str
    bars: tuple[Bar, ...]

    def __post_init__(self) -> None:
        if type(self.symbol) is not str or self.symbol not in UNIVERSE:
            raise ValueError("symbol is outside the accepted A147 universe")
        if type(self.bars) is not tuple or not self.bars:
            raise ValueError("discovery bars must be a nonempty immutable tuple")
        previous: datetime | None = None
        dates: list[date] = []
        for bar in self.bars:
            if type(bar) is not Bar or bar.symbol.value != self.symbol:
                raise ValueError("bars must match their ordered symbol series")
            if bar.timestamp.tzinfo is None:
                raise ValueError("daily discovery timestamps must be timezone-aware")
            if previous is not None and bar.timestamp <= previous:
                raise ValueError("discovery bars must be strictly ordered")
            previous = bar.timestamp
            session = bar.timestamp.astimezone(NY).date()
            if not VIEW_START <= session < VIEW_END_EXCLUSIVE:
                raise ValueError("discovery view cannot retain bars outside 2016-2021")
            dates.append(session)
        if any(left >= right for left, right in zip(dates, dates[1:], strict=False)):
            raise ValueError("daily discovery sessions must be unique and ordered")
        first_discovery_index = next(
            (
                index
                for index, session in enumerate(dates)
                if session >= DISCOVERY_START
            ),
            None,
        )
        if first_discovery_index is None or first_discovery_index < 253:
            raise ValueError("discovery history lacks the accepted 253-session warmup")


@dataclass(frozen=True, slots=True, init=False)
class DiscoveryView:
    """Immutable in-memory A147 view that cannot retain post-2021 bars."""

    dataset_identity: str
    price_basis: str
    provider_provenance: ProviderProvenance
    symbol_bars: tuple[SymbolDiscoveryBars, ...]
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
        try:
            parsed_identity = UUID(dataset.identity)
        except (ValueError, TypeError, AttributeError):
            raise ValueError(
                "accepted dataset identity must be a canonical UUID5"
            ) from None
        if str(parsed_identity) != dataset.identity or parsed_identity.version != 5:
            raise ValueError("accepted dataset identity must be a canonical UUID5")

        clipped: list[SymbolDiscoveryBars] = []
        for source in dataset.datasets:
            bars = tuple(
                bar
                for bar in source.bars
                if VIEW_START
                <= bar.timestamp.astimezone(NY).date()
                < VIEW_END_EXCLUSIVE
            )
            clipped.append(SymbolDiscoveryBars(source.symbol, bars))
        symbol_bars = tuple(clipped)
        identity = semantic_identity(
            "generation1-discovery-view",
            (
                dataset.identity,
                PRICE_BASIS,
                VIEW_START.isoformat(),
                VIEW_END_EXCLUSIVE.isoformat(),
                UNIVERSE,
            ),
        )
        object.__setattr__(self, "dataset_identity", dataset.identity)
        object.__setattr__(self, "price_basis", PRICE_BASIS)
        object.__setattr__(
            self, "provider_provenance", dataset.datasets[0].provider_provenance
        )
        object.__setattr__(self, "symbol_bars", symbol_bars)
        object.__setattr__(self, "identity", identity)

    @classmethod
    def from_dataset(cls, dataset: MultiAssetDataset) -> DiscoveryView:
        """Clip a caller-supplied accepted dataset before any signal evaluation."""
        return cls(dataset)

    def bars_for(self, symbol: str) -> tuple[Bar, ...]:
        for item in self.symbol_bars:
            if item.symbol == symbol:
                return item.bars
        raise ValueError("symbol is outside the accepted A147 universe")


@dataclass(frozen=True, slots=True)
class Generation1ProgramResult:
    """Deterministic G1 cell evidence for one predeclared proposal."""

    proposal_id: str
    semantic_program_id: str
    dataset_identity: str
    cells: tuple[CellEvidence, ...]
    identity: str = field(init=False)

    schema: ClassVar[str] = RESULT_SCHEMA

    def __post_init__(self) -> None:
        _require_uuid5(self.proposal_id, "proposal identity")
        _require_uuid5(self.semantic_program_id, "semantic program identity")
        _require_uuid5(self.dataset_identity, "dataset identity")
        if (
            type(self.cells) is not tuple
            or any(type(cell) is not CellEvidence for cell in self.cells)
            or tuple((cell.symbol, cell.regime) for cell in self.cells)
            != _EXPECTED_CELL_ORDER
        ):
            raise ValueError("G1 result cells must be complete and canonically ordered")
        if any(cell.candidate_id != self.proposal_id for cell in self.cells):
            raise ValueError("G1 result cells must bind the exact proposal")
        for cell in self.cells:
            first_stamp = datetime.fromisoformat(cell.first_session)
            last_stamp = datetime.fromisoformat(cell.last_session)
            if (
                first_stamp.tzinfo is None
                or first_stamp.utcoffset() is None
                or last_stamp.tzinfo is None
                or last_stamp.utcoffset() is None
            ):
                raise ValueError("G1 result session timestamps must be timezone-aware")
            first = first_stamp.astimezone(NY).date()
            last = last_stamp.astimezone(NY).date()
            regime = next(item for item in _G1_REGIMES if item.label == cell.regime)
            if first < regime.start or last >= regime.end or first > last:
                raise ValueError("G1 result evidence escaped its frozen date slice")
        material = (
            RESULT_SCHEMA,
            self.proposal_id,
            self.semantic_program_id,
            self.dataset_identity,
            tuple(asdict(cell) for cell in self.cells),
        )
        object.__setattr__(
            self,
            "identity",
            semantic_identity("generation1-program-result", material),
        )


def evaluate_generation1_program(
    proposal: ResearchProposal, view: DiscoveryView
) -> Generation1ProgramResult:
    """Evaluate one supported G1 proposal over the clipped discovery view."""
    if type(proposal) is not ResearchProposal:
        raise ValueError("a canonical ResearchProposal is required")
    if type(view) is not DiscoveryView:
        raise ValueError("a bounded DiscoveryView is required")
    if (
        proposal.generation != 1
        or proposal.semantic_status is not ProposalSemanticStatus.SUPPORTED
    ):
        raise ValueError("only supported Generation-1 proposals can be evaluated")

    program = compile_generation1_program(proposal.strategy_spec)
    if type(program) is StrategyConfig:
        signal_states_by_symbol = None
    elif type(program) in (AbsoluteMomentumSpec, MultiHorizonTrendSpec):
        signal_states_by_symbol = {
            item.symbol: _new_program_states(program, item.bars)
            for item in view.symbol_bars
        }
    else:
        raise ValueError("proposal did not compile to a supported G1 program")

    cells: list[CellEvidence] = []
    for item in view.symbol_bars:
        prepared_states = (
            signal_states_by_symbol[item.symbol]
            if signal_states_by_symbol is not None
            else None
        )
        for g1_regime in _G1_REGIMES:
            if type(program) is StrategyConfig:
                a147_regime = _A147_REGIMES_BY_LABEL[g1_regime.label]
                cell = evaluate_cell(
                    item.bars, program, a147_regime, proposal.proposal_id
                )
            else:
                assert prepared_states is not None
                cell = _evaluate_prepared_cell(
                    item.bars,
                    g1_regime,
                    proposal.proposal_id,
                    prepared_states=prepared_states,
                )
            if (
                cell.symbol != item.symbol
                or cell.regime != g1_regime.label
                or datetime.fromisoformat(cell.last_session).astimezone(NY).date()
                >= DISCOVERY_END_EXCLUSIVE
            ):
                raise ValueError("G1 evaluator produced evidence outside its view")
            cells.append(cell)

    return Generation1ProgramResult(
        proposal.proposal_id,
        proposal.semantic_program_id,
        view.dataset_identity,
        tuple(cells),
    )


def _new_program_states(
    program: AbsoluteMomentumSpec | MultiHorizonTrendSpec,
    bars: tuple[Bar, ...],
) -> tuple[str, ...]:
    """Compile the two frozen new G1 families into A147 replay states."""
    closes = tuple(bar.close for bar in bars)
    if type(program) is AbsoluteMomentumSpec:
        rolling_sums = (
            _rolling_sums(closes, 200)
            if program.gate is MomentumGate.ABOVE_SMA200
            else None
        )
        with localcontext(_SMA_CONTEXT):
            predicates: list[bool] = []
            for index, close in enumerate(closes):
                if index < program.lookback_sessions:
                    predicates.append(False)
                    continue
                momentum_positive = close > closes[index - program.lookback_sessions]
                if rolling_sums is None:
                    predicates.append(momentum_positive)
                    continue
                rolling_sum = rolling_sums[index]
                predicates.append(
                    momentum_positive
                    and rolling_sum is not None
                    and close * Decimal(200) > rolling_sum
                )
            return tuple("BUY" if value else "SELL" for value in predicates)

    if type(program) is MultiHorizonTrendSpec:
        threshold = 2 if program.vote is TrendVote.TWO_OF_THREE else 3
        predicates = []
        maximum_horizon = max(program.horizons)
        for index, close in enumerate(closes):
            if index < maximum_horizon:
                predicates.append(False)
                continue
            positive_votes = sum(
                close > closes[index - horizon] for horizon in program.horizons
            )
            predicates.append(positive_votes >= threshold)
        return tuple("BUY" if value else "SELL" for value in predicates)

    raise ValueError("unsupported Generation-1 signal program")


def _rolling_sums(
    values: tuple[Decimal, ...], window: int
) -> tuple[Decimal | None, ...]:
    """Exact fixed-context inclusive window sums aligned to completed closes."""
    with localcontext(_SMA_CONTEXT):
        total = Decimal(0)
        result: list[Decimal | None] = []
        for index, value in enumerate(values):
            total += value
            if index >= window:
                total -= values[index - window]
            result.append(total if index + 1 >= window else None)
        return tuple(result)


def _require_uuid5(value: str, label: str) -> None:
    try:
        parsed = UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise ValueError(f"{label} must be a canonical UUID5") from None
    if str(parsed) != value or parsed.version != 5:
        raise ValueError(f"{label} must be a canonical UUID5")
