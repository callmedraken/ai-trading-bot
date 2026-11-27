"""Explicitly synthetic Portfolio Manager observation and research inputs."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from trading_bot.domain import Symbol
from trading_bot.domain._validation import normalize_utc
from trading_bot.portfolio_manager.application_service import (
    DecisionDisplay,
    OutcomePresentation,
    PipelineEvaluation,
    PreviewLegDisplay,
)
from trading_bot.portfolio_manager.decision import (
    DecisionBatch,
    DecisionProvider,
    MarketQuote,
    MarketResearchInput,
    MarketSignal,
    Recommendation,
    SyntheticReferenceDecisionProvider,
    UnavailableDiagnostic,
)
from trading_bot.portfolio_manager.models import (
    AccountBinding,
    ObservationCoverage,
    ObservationProvenance,
    OrderCoverage,
    PortfolioObservation,
    PositionObservation,
    canonical_decimal,
)
from trading_bot.portfolio_manager.observation import observe_robinhood_portfolio
from trading_bot.portfolio_manager.planning import OrderPlan, PreviewLeg, plan_preview
from trading_bot.portfolio_manager.risk import (
    RiskDisposition,
    RiskEvaluation,
    RiskPolicy,
    evaluate_recommendations,
)
from trading_bot.robinhood_mcp.current_read_transport import (
    READ_TOOLS,
    RobinhoodCurrentReadTransport,
)

_SYNTHETIC_ACCOUNT_FINGERPRINT = hashlib.sha256(
    b"portfolio-manager/synthetic-demo-account/v1"
).hexdigest()
_FAKE_ROBINHOOD_ACCOUNT = "PM1-FAKE-ACCOUNT-01"


def synthetic_account_binding() -> AccountBinding:
    """Return the fixed synthetic profile binding; it is not a broker account."""
    return AccountBinding(_SYNTHETIC_ACCOUNT_FINGERPRINT)


class SyntheticDemoObservationSource:
    """Known-complete synthetic planning universe with two adopted holdings."""

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable")
        self._clock = clock or (lambda: datetime.now(UTC))
        self._binding = synthetic_account_binding()

    def observe(self) -> PortfolioObservation:
        stamp = normalize_utc(self._clock(), "observed_at")
        positions = (
            PositionObservation(
                symbol=Symbol("SPY"),
                quantity=Decimal("3.25"),
                available_to_sell=Decimal("3.25"),
                average_cost=Decimal("450"),
                current_price=Decimal("520"),
                price_observed_at=stamp,
            ),
            PositionObservation(
                symbol=Symbol("TLT"),
                quantity=Decimal("4"),
                available_to_sell=Decimal("4"),
                average_cost=None,
                current_price=Decimal("95"),
                price_observed_at=stamp,
            ),
        )
        return PortfolioObservation(
            observed_at=stamp,
            account_fingerprint=self._binding.fingerprint,
            observed_account_fingerprint=self._binding.fingerprint,
            broker_reported_equity=Decimal("6070"),
            broker_reported_position_value=Decimal("2070"),
            cash=Decimal("4000"),
            buying_power=Decimal("4000"),
            unleveraged_buying_power=Decimal("4000"),
            positions=positions,
            orders=(),
            coverage=ObservationCoverage(
                account_bound=True,
                portfolio_complete=True,
                positions_complete=True,
                quotes_complete=True,
                pagination_complete=True,
                order_scope=OrderCoverage.SYNTHETIC_COMPLETE,
            ),
            provenance=ObservationProvenance.SYNTHETIC,
        )


class FakeRobinhoodObservationSource:
    """Run the current read transport and PM observer against an async fake."""

    account_fingerprint = hashlib.sha256(
        _FAKE_ROBINHOOD_ACCOUNT.encode("utf-8")
    ).hexdigest()

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable")
        self._clock = clock or (lambda: datetime.now(UTC))
        self.calls: list[tuple[str, dict[str, object]]] = []
        self._last_session: _FakeAsyncReadSession | None = None

    def observe(self) -> PortfolioObservation:
        stamp = normalize_utc(self._clock(), "observed_at")
        session = _FakeAsyncReadSession(stamp, self.calls)
        self._last_session = session
        transport = RobinhoodCurrentReadTransport.for_test(session.connect)
        return observe_robinhood_portfolio(
            transport,
            observed_at=stamp,
            selected_account_fingerprint=self.account_fingerprint,
        )


class _FakeAsyncReadSession:
    """Tiny fake SDK session; all five responses are local synthetic mappings."""

    def __init__(
        self,
        stamp: datetime,
        calls: list[tuple[str, dict[str, object]]],
    ) -> None:
        self._stamp = stamp
        self._calls = calls

    async def list_tools(self, *, cursor):
        del cursor
        return SimpleNamespace(
            tools=[SimpleNamespace(name=name) for name in READ_TOOLS],
            next_cursor=None,
        )

    async def call_tool(self, name, arguments):
        self._calls.append((name, dict(arguments)))
        payload = self._response(name)
        return SimpleNamespace(is_error=False, structured_content=payload)

    @asynccontextmanager
    async def connect(self):
        yield self

    def _response(self, name: str) -> Mapping[str, object]:
        if name == "get_accounts":
            data: dict[str, object] = {
                "accounts": [
                    {
                        "account_number": _FAKE_ROBINHOOD_ACCOUNT,
                        "agentic_allowed": True,
                    }
                ]
            }
        elif name == "get_portfolio":
            data = {
                "total_value": "6070",
                "cash": "4000",
                "equity_value": "2070",
                "currency": "USD",
                "buying_power": {
                    "buying_power": "4000",
                    "unleveraged_buying_power": "4000",
                    "display_currency": "USD",
                },
            }
        elif name == "get_equity_positions":
            data = {
                "positions": [
                    {
                        "symbol": "SPY",
                        "quantity": "3.25",
                        "shares_available_for_sells": "3.25",
                        "average_buy_price": "450",
                        "type": "long",
                    },
                    {
                        "symbol": "TLT",
                        "quantity": "4",
                        "shares_available_for_sells": "4",
                        "average_buy_price": None,
                        "type": "long",
                    },
                ],
                "next": None,
            }
        elif name == "get_equity_quotes":
            symbols = [str(item) for item in arguments_symbols(self._calls[-1][1])]
            symbol = symbols[0]
            price = "520" if symbol == "SPY" else "95"
            quote_time = self._stamp.isoformat().replace("+00:00", "Z")
            data = {
                "results": [
                    {
                        "quote": {
                            "symbol": symbol,
                            "state": "active",
                            "has_traded": True,
                            "adjusted_previous_close": price,
                            "previous_close": price,
                            "ask_price": price,
                            "bid_price": price,
                            "last_trade_price": price,
                            "last_non_reg_trade_price": price,
                            "venue_ask_time": quote_time,
                            "venue_bid_time": quote_time,
                            "venue_last_trade_time": quote_time,
                            "venue_last_non_reg_trade_time": quote_time,
                        }
                    }
                ]
            }
        elif name == "get_equity_orders":
            data = {
                "orders": [
                    {
                        "id": "synthetic-observed-order-01",
                        "symbol": "SPY",
                        "side": "buy",
                        "state": "new",
                        "quantity": "1",
                        "cumulative_quantity": "0",
                        "created_at": self._stamp.isoformat(),
                        "placed_agent": "agentic",
                        "agent_initiated": True,
                    }
                ],
                "next": None,
            }
        else:
            raise AssertionError("fake transport received an unsupported read")
        return {"data": data}


def arguments_symbols(arguments: Mapping[str, object]) -> tuple[object, ...]:
    value = arguments.get("symbols")
    return tuple(value) if isinstance(value, (list, tuple)) else ()


class SyntheticPortfolioPipeline:
    """Compose research, decision, risk, and non-dispatchable plan boundaries."""

    def __init__(
        self,
        *,
        decision_provider: DecisionProvider | None = None,
        risk_policy: RiskPolicy | None = None,
    ) -> None:
        self._provider = decision_provider or SyntheticReferenceDecisionProvider()
        self._policy = risk_policy or RiskPolicy()

    def __call__(
        self, observation: PortfolioObservation, *, decision_at: datetime
    ) -> PipelineEvaluation:
        research = self._research_input(observation)
        batch = self._provider.evaluate(observation, research, decision_at=decision_at)
        risk = evaluate_recommendations(
            observation,
            research,
            batch,
            self._policy,
            decision_at=decision_at,
        )
        plan = plan_preview(observation, batch, risk)
        presentation = self._presentation(observation, research, batch, risk, plan)
        return PipelineEvaluation(
            presentation=presentation,
            semantic_inputs=self._semantic_inputs(research, batch),
            audit_payload=self._audit_payload(observation, research, batch, risk, plan),
        )

    def _research_input(self, observation: PortfolioObservation) -> MarketResearchInput:
        quotes: list[MarketQuote] = []
        for position in observation.positions:
            if position.current_price is None or position.price_observed_at is None:
                continue
            quotes.append(
                MarketQuote(
                    position.symbol,
                    position.current_price,
                    position.price_observed_at,
                    "SYNTHETIC_DEMO_PRICE_V1",
                )
            )
        gld = Symbol("GLD")
        if gld not in {position.symbol for position in observation.positions}:
            quotes.append(
                MarketQuote(
                    gld,
                    Decimal("200"),
                    observation.observed_at,
                    "SYNTHETIC_DEMO_PRICE_V1",
                )
            )
        signals = (
            MarketSignal(
                Symbol("SPY"),
                Decimal("0"),
                "Synthetic neutral reference signal for an existing holding.",
            ),
            MarketSignal(
                Symbol("TLT"),
                Decimal("-0.15"),
                "Synthetic reference signal for a partial reduction example.",
            ),
            MarketSignal(
                Symbol("GLD"),
                Decimal("0.20"),
                "Synthetic opportunity input; it is not a validated strategy result.",
            ),
        )
        return MarketResearchInput(
            portfolio_snapshot_id=observation.snapshot_id,
            observed_at=observation.observed_at,
            quotes=tuple(quotes),
            signals=signals,
            provider_id="SYNTHETIC_DEMO_RESEARCH_INPUTS",
            provider_version="v1",
            evidence_available=True,
        )

    def _presentation(
        self,
        observation: PortfolioObservation,
        research: MarketResearchInput,
        batch: DecisionBatch,
        risk: tuple[RiskEvaluation, ...],
        plan: OrderPlan,
    ) -> OutcomePresentation:
        risk_by_id = {item.recommendation_id: item for item in risk}
        decisions = [
            self._decision_display(
                recommendation, risk_by_id[recommendation.recommendation_id]
            )
            for recommendation in batch.recommendations
        ]
        decisions.extend(self._unavailable_display(item) for item in batch.unavailable)
        recommendations = {
            item.recommendation_id: item for item in batch.recommendations
        }
        previews = []
        for leg in plan.legs:
            evaluation = risk_by_id[leg.recommendation_id]
            previews.append(
                PreviewLegDisplay(
                    symbol=str(leg.symbol),
                    side=leg.side.value,
                    quantity=_display_decimal(leg.quantity),
                    reference_price=_display_decimal(leg.reference_price),
                    status="PREVIEW_ONLY",
                    reasons=tuple(code.value for code in evaluation.codes),
                )
            )
        for evaluation in plan.blocked:
            recommendation = recommendations[evaluation.recommendation_id]
            previews.append(
                PreviewLegDisplay(
                    symbol=str(evaluation.symbol),
                    side=evaluation.order_side or recommendation.action.value,
                    quantity=_display_decimal(evaluation.order_quantity),
                    reference_price=_display_decimal(evaluation.price),
                    status="BLOCKED",
                    reasons=tuple(code.value for code in evaluation.codes),
                )
            )
        return OutcomePresentation(
            portfolio_snapshot_id=observation.snapshot_id,
            research_input_id=research.research_input_id,
            decision_batch_id=batch.decision_batch_id,
            strategy_id=batch.strategy_id,
            strategy_version=batch.strategy_version,
            decision_at=batch.decision_at,
            decisions=tuple(decisions),
            preview_legs=tuple(previews),
            diagnostics=tuple(
                f"{item.symbol}:{item.code}" for item in batch.unavailable
            ),
        )

    @staticmethod
    def _decision_display(
        recommendation: Recommendation, risk: RiskEvaluation
    ) -> DecisionDisplay:
        status = (
            "PREVIEW_ONLY"
            if risk.disposition is RiskDisposition.PREVIEW_APPROVED
            else "RISK_BLOCKED"
            if risk.disposition is RiskDisposition.BLOCKED
            else "NO_ORDER"
        )
        return DecisionDisplay(
            symbol=str(recommendation.symbol),
            action=recommendation.action.value,
            target_quantity=_display_decimal(recommendation.target_quantity),
            rationale=recommendation.rationale,
            evidence_available=recommendation.evidence_available,
            provider_diagnostics=tuple(
                f"{item.kind.value}:{item.code}: {item.message}"
                for item in recommendation.diagnostics
            ),
            risk_status=status,
            risk_reasons=tuple(code.value for code in risk.codes),
            recommendation_id=str(recommendation.recommendation_id),
        )

    @staticmethod
    def _unavailable_display(item: UnavailableDiagnostic) -> DecisionDisplay:
        return DecisionDisplay(
            symbol=str(item.symbol),
            action="UNAVAILABLE",
            target_quantity=None,
            rationale=item.message,
            evidence_available=False,
            provider_diagnostics=(f"{item.code}: {item.message}",),
            risk_status="UNAVAILABLE",
            risk_reasons=(item.code,),
            recommendation_id=f"UNAVAILABLE:{item.symbol}:{item.code}",
        )

    def _semantic_inputs(
        self, research: MarketResearchInput, batch: DecisionBatch
    ) -> dict[str, object]:
        policy = self._policy
        return {
            "research_provider": {
                "id": research.provider_id,
                "version": research.provider_version,
                "evidence_available": research.evidence_available,
                "quotes": [
                    {
                        "symbol": str(item.symbol),
                        "price": canonical_decimal(item.price),
                        "source_id": item.source_id,
                    }
                    for item in research.quotes
                ],
                "signals": [
                    {
                        "symbol": str(item.symbol),
                        "score": (
                            None
                            if item.score is None
                            else canonical_decimal(item.score)
                        ),
                        "rationale": item.rationale,
                        "evidence_available": item.evidence_available,
                    }
                    for item in research.signals
                ],
            },
            "decision_model": {
                "id": batch.strategy_id,
                "version": batch.strategy_version,
                "recommendations": [
                    {
                        "symbol": str(item.symbol),
                        "action": item.action.value,
                        "target_quantity": (
                            None
                            if item.target_quantity is None
                            else canonical_decimal(item.target_quantity)
                        ),
                        "rationale": item.rationale,
                        "evidence_available": item.evidence_available,
                        "diagnostics": _recommendation_diagnostics(item),
                    }
                    for item in batch.recommendations
                ],
                "unavailable": [
                    {
                        "symbol": str(item.symbol),
                        "code": item.code,
                        "message": item.message,
                    }
                    for item in batch.unavailable
                ],
                "recommendation_horizons": [
                    {
                        "symbol": str(item.symbol),
                        "label": item.investment_horizon.label,
                        "trading_days": item.investment_horizon.trading_days,
                    }
                    for item in batch.recommendations
                ],
            },
            "risk_policy": {
                "maximum_observation_age_seconds": int(
                    policy.maximum_observation_age.total_seconds()
                ),
                "maximum_quote_age_seconds": int(
                    policy.maximum_quote_age.total_seconds()
                ),
                "maximum_position_weight": canonical_decimal(
                    policy.maximum_position_weight
                ),
                "maximum_total_exposure_weight": canonical_decimal(
                    policy.maximum_total_exposure_weight
                ),
                "minimum_cash_reserve_weight": canonical_decimal(
                    policy.minimum_cash_reserve_weight
                ),
                "estimated_commission": canonical_decimal(policy.estimated_commission),
                "slippage_bps": canonical_decimal(policy.slippage_bps),
                "maximum_order_notional": (
                    None
                    if policy.maximum_order_notional is None
                    else canonical_decimal(policy.maximum_order_notional)
                ),
            },
        }

    def _audit_payload(
        self,
        observation: PortfolioObservation,
        research: MarketResearchInput,
        batch: DecisionBatch,
        risk: tuple[RiskEvaluation, ...],
        plan: OrderPlan,
    ) -> dict[str, object]:
        return {
            "semantic_inputs": self._semantic_inputs(research, batch),
            "research": {
                "input_id": str(research.research_input_id),
                "observed_at": research.observed_at.isoformat(),
                "provider_id": research.provider_id,
                "provider_version": research.provider_version,
                "evidence_available": research.evidence_available,
                "quotes": [
                    {
                        "symbol": str(item.symbol),
                        "price": canonical_decimal(item.price),
                        "observed_at": item.observed_at.isoformat(),
                        "source_id": item.source_id,
                    }
                    for item in research.quotes
                ],
                "signals": [
                    {
                        "symbol": str(item.symbol),
                        "score": (
                            None
                            if item.score is None
                            else canonical_decimal(item.score)
                        ),
                        "rationale": item.rationale,
                        "evidence_available": item.evidence_available,
                    }
                    for item in research.signals
                ],
            },
            "strategy": {
                "id": batch.strategy_id,
                "version": batch.strategy_version,
                "decision_at": batch.decision_at.isoformat(),
                "batch_id": str(batch.decision_batch_id),
            },
            "recommendations": [
                {
                    "id": str(item.recommendation_id),
                    "symbol": str(item.symbol),
                    "action": item.action.value,
                    "target_quantity": (
                        None
                        if item.target_quantity is None
                        else canonical_decimal(item.target_quantity)
                    ),
                    "rationale": item.rationale,
                    "evidence_available": item.evidence_available,
                    "diagnostics": _recommendation_diagnostics(item),
                    "investment_horizon": item.investment_horizon.label,
                    "horizon_trading_days": item.investment_horizon.trading_days,
                }
                for item in batch.recommendations
            ],
            "provider_diagnostics": [
                {
                    "symbol": str(item.symbol),
                    "status": "RECOMMENDATION_AVAILABLE",
                    "recommendation_id": str(item.recommendation_id),
                    "action": item.action.value,
                    "rationale": item.rationale,
                    "evidence_available": item.evidence_available,
                    "diagnostics": _recommendation_diagnostics(item),
                }
                for item in batch.recommendations
            ]
            + [
                {
                    "symbol": str(item.symbol),
                    "status": "UNAVAILABLE",
                    "code": item.code,
                    "message": item.message,
                }
                for item in batch.unavailable
            ],
            "unavailable": [
                {"symbol": str(item.symbol), "code": item.code, "message": item.message}
                for item in batch.unavailable
            ],
            "risk_evaluations": [self._risk_record(item) for item in risk],
            "order_plan": {
                "plan_id": str(plan.plan_id),
                "account_fingerprint": plan.account_fingerprint,
                "portfolio_snapshot_id": str(plan.portfolio_snapshot_id),
                "decision_batch_id": str(plan.decision_batch_id),
                "legs": [self._leg_record(item) for item in plan.legs],
                "blocked_recommendations": [
                    self._risk_record(item) for item in plan.blocked
                ],
                "sell_proceeds_assumed_available": canonical_decimal(
                    plan.sell_proceeds_assumed_available
                ),
                "preview_only": plan.preview_only,
                "dispatch_authorized": plan.dispatch_authorized,
            },
            "observation_binding": {
                "account_fingerprint": observation.account_fingerprint,
                "portfolio_snapshot_id": str(observation.snapshot_id),
            },
        }

    @staticmethod
    def _risk_record(item: RiskEvaluation) -> dict[str, object]:
        return {
            "recommendation_id": str(item.recommendation_id),
            "symbol": str(item.symbol),
            "disposition": item.disposition.value,
            "codes": [code.value for code in item.codes],
            "price": _display_decimal(item.price),
            "order_side": item.order_side,
            "order_quantity": canonical_decimal(item.order_quantity),
            "estimated_gross_notional": canonical_decimal(
                item.estimated_gross_notional
            ),
            "estimated_slippage": canonical_decimal(item.estimated_slippage),
            "estimated_commission": canonical_decimal(item.estimated_commission),
            "preview_only": item.preview_only,
            "dispatch_authorized": item.dispatch_authorized,
        }

    @staticmethod
    def _leg_record(item: PreviewLeg) -> dict[str, object]:
        return {
            "leg_id": str(item.leg_id),
            "recommendation_id": str(item.recommendation_id),
            "symbol": str(item.symbol),
            "side": item.side.value,
            "quantity": canonical_decimal(item.quantity),
            "reference_price": canonical_decimal(item.reference_price),
            "gross_notional": canonical_decimal(item.gross_notional),
            "estimated_slippage": canonical_decimal(item.estimated_slippage),
            "estimated_commission": canonical_decimal(item.estimated_commission),
            "depends_on": [str(value) for value in item.depends_on],
            "preview_only": item.preview_only,
            "dispatch_authorized": item.dispatch_authorized,
        }


def default_risk_policy() -> RiskPolicy:
    """Return PM1's explicit conservative default policy."""
    return RiskPolicy()


def _display_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _recommendation_diagnostics(
    item: Recommendation,
) -> list[dict[str, str]]:
    return [
        {
            "code": diagnostic.code,
            "message": diagnostic.message,
            "kind": diagnostic.kind.value,
        }
        for diagnostic in item.diagnostics
    ]
