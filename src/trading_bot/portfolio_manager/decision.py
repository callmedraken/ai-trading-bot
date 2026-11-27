"""Typed provider boundary and deterministic synthetic decision reference."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from trading_bot.domain import Symbol
from trading_bot.domain._validation import normalize_utc
from trading_bot.portfolio_manager.models import (
    AccountBinding,
    PortfolioObservation,
    _identity,
    canonical_decimal,
    decimal_multiply,
)

_ZERO = Decimal("0")
_HALF = Decimal("0.5")
_BUY_THRESHOLD = Decimal("0.10")
_REDUCE_THRESHOLD = Decimal("-0.10")
_SELL_THRESHOLD = Decimal("-0.20")


class Action(StrEnum):
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    REDUCE = "REDUCE"
    REBALANCE = "REBALANCE"
    NO_ACTION = "NO_ACTION"


class RecommendationDiagnosticKind(StrEnum):
    RISK_CONTEXT = "RISK_CONTEXT"
    UNCERTAINTY = "UNCERTAINTY"
    PROVIDER_LIMITATION = "PROVIDER_LIMITATION"


@dataclass(frozen=True, slots=True)
class RecommendationDiagnostic:
    code: str
    message: str
    kind: RecommendationDiagnosticKind

    def __post_init__(self) -> None:
        for name in ("code", "message"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonblank")
        if not isinstance(self.kind, RecommendationDiagnosticKind):
            raise TypeError("kind must be RecommendationDiagnosticKind")


@dataclass(frozen=True, slots=True)
class InvestmentHorizon:
    label: str
    trading_days: int

    def __post_init__(self) -> None:
        if not isinstance(self.label, str) or not self.label.strip():
            raise ValueError("label must be nonblank")
        if (
            not isinstance(self.trading_days, int)
            or isinstance(self.trading_days, bool)
            or self.trading_days <= 0
        ):
            raise ValueError("trading_days must be a positive integer")


@dataclass(frozen=True, slots=True)
class MarketQuote:
    """Price fact supplied with research, never by a recommendation itself."""

    symbol: Symbol
    price: Decimal
    observed_at: datetime
    source_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        if (
            not isinstance(self.price, Decimal)
            or not self.price.is_finite()
            or self.price <= _ZERO
        ):
            raise ValueError("price must be a positive finite Decimal")
        object.__setattr__(
            self, "observed_at", normalize_utc(self.observed_at, "observed_at")
        )
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError("source_id must be nonblank")


@dataclass(frozen=True, slots=True)
class MarketSignal:
    """One descriptive research input; its score has no order authority."""

    symbol: Symbol
    score: Decimal | None
    rationale: str
    evidence_available: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        if self.score is not None and (
            not isinstance(self.score, Decimal) or not self.score.is_finite()
        ):
            raise ValueError("score must be a finite Decimal or None")
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise ValueError("rationale must be nonblank")
        if not isinstance(self.evidence_available, bool):
            raise TypeError("evidence_available must be a bool")


@dataclass(frozen=True, slots=True)
class MarketResearchInput:
    portfolio_snapshot_id: UUID
    observed_at: datetime
    quotes: tuple[MarketQuote, ...]
    signals: tuple[MarketSignal, ...]
    provider_id: str
    provider_version: str
    evidence_available: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.portfolio_snapshot_id, UUID):
            raise TypeError("portfolio_snapshot_id must be a UUID")
        object.__setattr__(
            self, "observed_at", normalize_utc(self.observed_at, "observed_at")
        )
        quotes = tuple(self.quotes)
        signals = tuple(self.signals)
        if any(not isinstance(item, MarketQuote) for item in quotes):
            raise TypeError("quotes must contain MarketQuote values")
        if any(not isinstance(item, MarketSignal) for item in signals):
            raise TypeError("signals must contain MarketSignal values")
        if len({item.symbol for item in quotes}) != len(quotes):
            raise ValueError("quote symbols must be unique")
        if len({item.symbol for item in signals}) != len(signals):
            raise ValueError("signal symbols must be unique")
        for name in ("provider_id", "provider_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonblank")
        if not isinstance(self.evidence_available, bool):
            raise TypeError("evidence_available must be a bool")
        object.__setattr__(self, "quotes", quotes)
        object.__setattr__(self, "signals", signals)

    @property
    def research_input_id(self) -> UUID:
        values = [
            str(self.portfolio_snapshot_id),
            self.observed_at.isoformat(),
            self.provider_id,
            self.provider_version,
            str(self.evidence_available),
        ]
        for quote in self.quotes:
            values.extend(
                (
                    "quote",
                    str(quote.symbol),
                    canonical_decimal(quote.price),
                    quote.observed_at.isoformat(),
                    quote.source_id,
                )
            )
        for signal in self.signals:
            values.extend(
                (
                    "signal",
                    str(signal.symbol),
                    "none" if signal.score is None else canonical_decimal(signal.score),
                    signal.rationale,
                    str(signal.evidence_available),
                )
            )
        return _identity("market-research", tuple(values))

    def quote_for(self, symbol: Symbol) -> MarketQuote | None:
        return next((item for item in self.quotes if item.symbol == symbol), None)

    def signal_for(self, symbol: Symbol) -> MarketSignal | None:
        return next((item for item in self.signals if item.symbol == symbol), None)


@dataclass(frozen=True, slots=True)
class Recommendation:
    symbol: Symbol
    action: Action
    portfolio_snapshot_id: UUID
    account_fingerprint: str
    research_input_id: UUID
    strategy_id: str
    strategy_version: str
    decision_at: datetime
    investment_horizon: InvestmentHorizon
    target_quantity: Decimal | None
    rationale: str
    evidence_available: bool
    diagnostics: tuple[RecommendationDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        if not isinstance(self.action, Action):
            raise TypeError("action must be Action")
        for name in ("portfolio_snapshot_id", "research_input_id"):
            if not isinstance(getattr(self, name), UUID):
                raise TypeError(f"{name} must be a UUID")
        AccountBinding(self.account_fingerprint)
        for name in ("strategy_id", "strategy_version", "rationale"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonblank")
        object.__setattr__(
            self, "decision_at", normalize_utc(self.decision_at, "decision_at")
        )
        if not isinstance(self.investment_horizon, InvestmentHorizon):
            raise TypeError("investment_horizon must be InvestmentHorizon")
        if self.target_quantity is not None and (
            not isinstance(self.target_quantity, Decimal)
            or not self.target_quantity.is_finite()
            or self.target_quantity < _ZERO
        ):
            raise ValueError(
                "target_quantity must be nonnegative finite Decimal or None"
            )
        target_required = self.action in {
            Action.BUY,
            Action.SELL,
            Action.REDUCE,
            Action.REBALANCE,
        }
        if target_required != (self.target_quantity is not None):
            raise ValueError("trade actions require an ending target_quantity")
        if not isinstance(self.evidence_available, bool):
            raise TypeError("evidence_available must be a bool")
        diagnostics = tuple(self.diagnostics)
        if any(not isinstance(item, RecommendationDiagnostic) for item in diagnostics):
            raise TypeError("diagnostics must contain RecommendationDiagnostic values")
        if len({item.code for item in diagnostics}) != len(diagnostics):
            raise ValueError("recommendation diagnostic codes must be unique")
        object.__setattr__(self, "diagnostics", diagnostics)

    @property
    def recommendation_id(self) -> UUID:
        values = (
            str(self.portfolio_snapshot_id),
            self.account_fingerprint,
            str(self.research_input_id),
            str(self.symbol),
            self.action.value,
            self.strategy_id,
            self.strategy_version,
            self.decision_at.isoformat(),
            self.investment_horizon.label,
            str(self.investment_horizon.trading_days),
            "none"
            if self.target_quantity is None
            else canonical_decimal(self.target_quantity),
            self.rationale,
            str(self.evidence_available),
            *(
                part
                for item in self.diagnostics
                for part in (item.code, item.message, item.kind.value)
            ),
        )
        return _identity("recommendation", values)


@dataclass(frozen=True, slots=True)
class UnavailableDiagnostic:
    symbol: Symbol
    code: str
    message: str

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        for name in ("code", "message"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonblank")


@dataclass(frozen=True, slots=True)
class DecisionBatch:
    portfolio_snapshot_id: UUID
    account_fingerprint: str | None
    research_input_id: UUID
    strategy_id: str
    strategy_version: str
    decision_at: datetime
    recommendations: tuple[Recommendation, ...]
    unavailable: tuple[UnavailableDiagnostic, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.portfolio_snapshot_id, UUID) or not isinstance(
            self.research_input_id, UUID
        ):
            raise TypeError("snapshot and research IDs must be UUID values")
        if self.account_fingerprint is not None:
            AccountBinding(self.account_fingerprint)
        for name in ("strategy_id", "strategy_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonblank")
        object.__setattr__(
            self, "decision_at", normalize_utc(self.decision_at, "decision_at")
        )
        recommendations = tuple(self.recommendations)
        unavailable = tuple(self.unavailable)
        if any(not isinstance(item, Recommendation) for item in recommendations):
            raise TypeError("recommendations must contain Recommendation values")
        if any(not isinstance(item, UnavailableDiagnostic) for item in unavailable):
            raise TypeError("unavailable must contain UnavailableDiagnostic values")
        symbols = tuple(item.symbol for item in recommendations) + tuple(
            item.symbol for item in unavailable
        )
        if len(set(symbols)) != len(symbols):
            raise ValueError(
                "each symbol must have exactly one recommendation or diagnostic"
            )
        for item in recommendations:
            if (
                item.portfolio_snapshot_id != self.portfolio_snapshot_id
                or item.account_fingerprint != self.account_fingerprint
                or item.research_input_id != self.research_input_id
                or item.strategy_id != self.strategy_id
                or item.strategy_version != self.strategy_version
                or item.decision_at != self.decision_at
            ):
                raise ValueError("recommendation context must match its batch")
        object.__setattr__(self, "recommendations", recommendations)
        object.__setattr__(self, "unavailable", unavailable)

    @property
    def decision_batch_id(self) -> UUID:
        values = [
            str(self.portfolio_snapshot_id),
            self.account_fingerprint or "none",
            str(self.research_input_id),
            self.strategy_id,
            self.strategy_version,
            self.decision_at.isoformat(),
        ]
        for item in self.recommendations:
            values.extend(("recommendation", str(item.recommendation_id)))
        for item in self.unavailable:
            values.extend(("unavailable", str(item.symbol), item.code, item.message))
        return _identity("decision-batch", tuple(values))


class DecisionProvider(Protocol):
    """Research-only interface; implementations do not create order authority."""

    def evaluate(
        self,
        observation: PortfolioObservation,
        research: MarketResearchInput,
        *,
        decision_at: datetime,
    ) -> DecisionBatch: ...


class SyntheticReferenceDecisionProvider:
    """Small deterministic momentum reference, not a validated profitable strategy."""

    strategy_id = "SYNTHETIC_MOMENTUM_REFERENCE"
    strategy_version = "v1"
    horizon = InvestmentHorizon("REFERENCE_90_TRADING_DAYS", 90)

    def evaluate(
        self,
        observation: PortfolioObservation,
        research: MarketResearchInput,
        *,
        decision_at: datetime,
    ) -> DecisionBatch:
        if not isinstance(observation, PortfolioObservation):
            raise TypeError("observation must be PortfolioObservation")
        if not isinstance(research, MarketResearchInput):
            raise TypeError("research must be MarketResearchInput")
        stamp = normalize_utc(decision_at, "decision_at")
        held = {item.symbol: item for item in observation.positions}
        ordered_symbols = [item.symbol for item in observation.positions]
        ordered_symbols.extend(
            signal.symbol for signal in research.signals if signal.symbol not in held
        )
        recommendations: list[Recommendation] = []
        unavailable: list[UnavailableDiagnostic] = []
        account_fp = observation.account_fingerprint
        for symbol in ordered_symbols:
            position = held.get(symbol)
            signal = research.signal_for(symbol)
            quote = research.quote_for(symbol)
            if research.portfolio_snapshot_id != observation.snapshot_id:
                unavailable.append(
                    UnavailableDiagnostic(
                        symbol,
                        "RESEARCH_SNAPSHOT_MISMATCH",
                        "Research input is not bound to this portfolio snapshot.",
                    )
                )
                continue
            if account_fp is None:
                unavailable.append(
                    UnavailableDiagnostic(
                        symbol,
                        "ACCOUNT_NOT_BOUND",
                        "No selected account fingerprint is bound to the observation.",
                    )
                )
                continue
            if position is not None and not position.supported:
                unavailable.append(
                    UnavailableDiagnostic(
                        symbol,
                        "UNSUPPORTED_ASSET",
                        "Unsupported equity or ETF asset.",
                    )
                )
                continue
            if (
                signal is None
                or signal.score is None
                or not signal.evidence_available
                or not research.evidence_available
            ):
                unavailable.append(
                    UnavailableDiagnostic(
                        symbol,
                        "RESEARCH_UNAVAILABLE",
                        "A complete, available research signal is not present.",
                    )
                )
                continue
            if quote is None:
                unavailable.append(
                    UnavailableDiagnostic(
                        symbol,
                        "MARKET_PRICE_UNAVAILABLE",
                        "No price observation is bound to this research input.",
                    )
                )
                continue
            if position is not None and position.quantity < _ZERO:
                unavailable.append(
                    UnavailableDiagnostic(
                        symbol,
                        "SHORT_POSITION_UNSUPPORTED",
                        "Observed short position blocks a recommendation.",
                    )
                )
                continue
            action: Action
            target: Decimal | None
            if position is None:
                if signal.score >= _BUY_THRESHOLD:
                    action, target = Action.BUY, Decimal("1")
                    reason = (
                        "Synthetic reference score "
                        + canonical_decimal(signal.score)
                        + " exceeded the fixed opportunity threshold; "
                        + "one share is a preview request only."
                    )
                else:
                    action, target = Action.NO_ACTION, None
                    reason = (
                        "Synthetic reference score "
                        + canonical_decimal(signal.score)
                        + " did not meet the fixed opportunity threshold."
                    )
            elif signal.score <= _SELL_THRESHOLD:
                action, target = Action.SELL, _ZERO
                reason = (
                    "Synthetic reference score "
                    + canonical_decimal(signal.score)
                    + " crossed the exit threshold; average cost was not used."
                )
            elif signal.score <= _REDUCE_THRESHOLD:
                action = Action.REDUCE
                target = decimal_multiply(position.quantity, _HALF)
                reason = (
                    "Synthetic reference score "
                    + canonical_decimal(signal.score)
                    + " crossed the reduction threshold; average cost was not used."
                )
            else:
                action, target = Action.HOLD, None
                reason = (
                    "Synthetic reference score "
                    + canonical_decimal(signal.score)
                    + " did not meet a trade threshold."
                )
            recommendations.append(
                Recommendation(
                    symbol=symbol,
                    action=action,
                    portfolio_snapshot_id=observation.snapshot_id,
                    account_fingerprint=account_fp,
                    research_input_id=research.research_input_id,
                    strategy_id=self.strategy_id,
                    strategy_version=self.strategy_version,
                    decision_at=stamp,
                    investment_horizon=self.horizon,
                    target_quantity=target,
                    rationale=reason,
                    evidence_available=signal.evidence_available
                    and research.evidence_available,
                    diagnostics=(
                        RecommendationDiagnostic(
                            "SYNTHETIC_REFERENCE_UNVALIDATED",
                            "Synthetic reference; no profitability claim is made.",
                            RecommendationDiagnosticKind.PROVIDER_LIMITATION,
                        ),
                        *(
                            (
                                RecommendationDiagnostic(
                                    "COST_BASIS_UNKNOWN",
                                    "Cost basis unknown; lots and entry dates omitted.",
                                    RecommendationDiagnosticKind.UNCERTAINTY,
                                ),
                            )
                            if position is not None and position.average_cost is None
                            else ()
                        ),
                    ),
                )
            )
        return DecisionBatch(
            portfolio_snapshot_id=observation.snapshot_id,
            account_fingerprint=account_fp,
            research_input_id=research.research_input_id,
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            decision_at=stamp,
            recommendations=tuple(recommendations),
            unavailable=tuple(unavailable),
        )


@dataclass(frozen=True, slots=True)
class AIRecommendationSuggestion:
    """One fake AI output; contains no market price or execution authority."""

    symbol: Symbol
    action: Action
    target_quantity: Decimal | None
    rationale: str
    evidence_available: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol) or not isinstance(self.action, Action):
            raise TypeError("suggestion requires Symbol and Action")
        if self.target_quantity is not None and (
            not isinstance(self.target_quantity, Decimal)
            or not self.target_quantity.is_finite()
            or self.target_quantity < _ZERO
        ):
            raise ValueError(
                "target_quantity must be nonnegative finite Decimal or None"
            )
        if self.action in {Action.BUY, Action.SELL, Action.REDUCE, Action.REBALANCE}:
            if self.target_quantity is None:
                raise ValueError("trade suggestions require a target quantity")
        elif self.target_quantity is not None:
            raise ValueError("non-trade suggestions cannot include target quantity")
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise ValueError("rationale must be nonblank")
        if not isinstance(self.evidence_available, bool):
            raise TypeError("evidence_available must be a bool")


class FakeAIRecommendationProvider:
    """Injectable fake-provider adapter that binds outputs and checks coverage."""

    def __init__(
        self,
        suggestions: tuple[AIRecommendationSuggestion, ...],
        *,
        provider_id: str = "FAKE_AI_RECOMMENDATION_PROVIDER",
        provider_version: str = "v1",
        investment_horizon: InvestmentHorizon | None = None,
    ) -> None:
        items = tuple(suggestions)
        if any(not isinstance(item, AIRecommendationSuggestion) for item in items):
            raise TypeError(
                "suggestions must contain AIRecommendationSuggestion values"
            )
        if len({item.symbol for item in items}) != len(items):
            raise ValueError("suggestion symbols must be unique")
        for name, value in (
            ("provider_id", provider_id),
            ("provider_version", provider_version),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonblank")
        if investment_horizon is None:
            investment_horizon = InvestmentHorizon(
                "FAKE_PROVIDER_UNSPECIFIED_HORIZON", 90
            )
        if not isinstance(investment_horizon, InvestmentHorizon):
            raise TypeError("investment_horizon must be InvestmentHorizon")
        self._suggestions = items
        self._provider_id = provider_id
        self._provider_version = provider_version
        self._horizon = investment_horizon

    def evaluate(
        self,
        observation: PortfolioObservation,
        research: MarketResearchInput,
        *,
        decision_at: datetime,
    ) -> DecisionBatch:
        if not isinstance(observation, PortfolioObservation) or not isinstance(
            research, MarketResearchInput
        ):
            raise TypeError("fake AI provider requires observation and research inputs")
        stamp = normalize_utc(decision_at, "decision_at")
        held = {item.symbol: item for item in observation.positions}
        opportunity_symbols = tuple(
            signal.symbol for signal in research.signals if signal.symbol not in held
        )
        expected = (
            tuple(item.symbol for item in observation.positions) + opportunity_symbols
        )
        suggestions = {item.symbol: item for item in self._suggestions}
        unavailable: list[UnavailableDiagnostic] = []
        recommendations: list[Recommendation] = []
        account_fp = observation.account_fingerprint
        for symbol in expected:
            position = held.get(symbol)
            suggestion = suggestions.get(symbol)
            if research.portfolio_snapshot_id != observation.snapshot_id:
                unavailable.append(
                    UnavailableDiagnostic(
                        symbol,
                        "RESEARCH_SNAPSHOT_MISMATCH",
                        "Research input is not bound to this portfolio snapshot.",
                    )
                )
                continue
            if account_fp is None:
                unavailable.append(
                    UnavailableDiagnostic(
                        symbol,
                        "ACCOUNT_NOT_BOUND",
                        "No selected account fingerprint is bound to the observation.",
                    )
                )
                continue
            if position is not None and (
                not position.supported or position.quantity < _ZERO
            ):
                unavailable.append(
                    UnavailableDiagnostic(
                        symbol,
                        "UNSUPPORTED_HOLDING",
                        "Short/unsupported holdings cannot receive AI actions.",
                    )
                )
                continue
            if suggestion is None:
                unavailable.append(
                    UnavailableDiagnostic(
                        symbol,
                        "AI_RECOMMENDATION_MISSING",
                        "Fake provider returned no explicit decision.",
                    )
                )
                continue
            if research.quote_for(symbol) is None:
                unavailable.append(
                    UnavailableDiagnostic(
                        symbol,
                        "MARKET_PRICE_UNAVAILABLE",
                        "Independent price is missing from this research input.",
                    )
                )
                continue
            diagnostics = [
                RecommendationDiagnostic(
                    "FAKE_AI_OUTPUT_UNVALIDATED",
                    "Fake AI-shaped output; not independently validated.",
                    RecommendationDiagnosticKind.PROVIDER_LIMITATION,
                )
            ]
            if position is not None and position.average_cost is None:
                diagnostics.append(
                    RecommendationDiagnostic(
                        "COST_BASIS_UNKNOWN",
                        "Unknown cost basis; no entry date or tax lots inferred.",
                        RecommendationDiagnosticKind.UNCERTAINTY,
                    )
                )
            recommendations.append(
                Recommendation(
                    symbol=symbol,
                    action=suggestion.action,
                    portfolio_snapshot_id=observation.snapshot_id,
                    account_fingerprint=account_fp,
                    research_input_id=research.research_input_id,
                    strategy_id=self._provider_id,
                    strategy_version=self._provider_version,
                    decision_at=stamp,
                    investment_horizon=self._horizon,
                    target_quantity=suggestion.target_quantity,
                    rationale=suggestion.rationale,
                    evidence_available=suggestion.evidence_available
                    and research.evidence_available,
                    diagnostics=tuple(diagnostics),
                )
            )
        for symbol in self._suggestions:
            if symbol.symbol not in set(expected):
                unavailable.append(
                    UnavailableDiagnostic(
                        symbol.symbol,
                        "AI_SYMBOL_NOT_IN_EVALUATION",
                        "Fake output named a symbol outside this portfolio evaluation.",
                    )
                )
        return DecisionBatch(
            portfolio_snapshot_id=observation.snapshot_id,
            account_fingerprint=account_fp,
            research_input_id=research.research_input_id,
            strategy_id=self._provider_id,
            strategy_version=self._provider_version,
            decision_at=stamp,
            recommendations=tuple(recommendations),
            unavailable=tuple(unavailable),
        )
