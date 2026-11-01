"""The narrow filtered-trend BASE_MA evaluator for P5A."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid5

from trading_bot.desktop_paper.configuration import (
    PaperStrategyBinding,
    PaperStrategyEvaluationInput,
)
from trading_bot.desktop_paper.research_binding import (
    FILTERED_TREND_STRATEGY_FAMILY,
    FILTERED_TREND_STRATEGY_VERSION,
)
from trading_bot.domain import OrderSide, TradeProposal
from trading_bot.experiments.filtered_trend_strategies import StrategyConfig, signal

_PROPOSAL_NAMESPACE = UUID("eebbb7c0-79bb-5f24-ae0f-9d0db70e3500")
_BASE_MA = StrategyConfig("BASE_MA", 35, 50, "none")
_DEFAULT_DESIRED_QUANTITY = Decimal("1")


class FilteredTrendBaseMaEvaluator:
    """Translate the accepted BASE_MA signal into intent only."""

    def __init__(self, desired_quantity: Decimal = _DEFAULT_DESIRED_QUANTITY) -> None:
        if (
            type(desired_quantity) is not Decimal
            or not desired_quantity.is_finite()
            or desired_quantity <= 0
            or desired_quantity != desired_quantity.to_integral_value()
        ):
            raise ValueError("desired_quantity must be a positive whole Decimal")
        self._desired_quantity = desired_quantity

    def evaluate(self, value: PaperStrategyEvaluationInput) -> TradeProposal | None:
        if type(value) is not PaperStrategyEvaluationInput:
            raise TypeError("value must be an exact PaperStrategyEvaluationInput")
        binding = value.binding
        if not _is_accepted_base_ma_binding(binding):
            raise ValueError("PAPER_EVALUATION_BINDING_REJECTED")
        position = (
            None
            if value.prior_account is None
            else value.prior_account.positions.get(binding.symbol)
        )
        invested = position is not None and position.quantity > 0
        action = signal(_BASE_MA, value.completed_history, invested)
        if action == "HOLD":
            return None
        side = OrderSide.BUY if action == "BUY" else OrderSide.SELL
        quantity = (
            self._desired_quantity if side is OrderSide.BUY else position.quantity  # type: ignore[union-attr]
        )
        last_timestamp = (
            value.completed_history[-1].timestamp.isoformat()
            if value.completed_history
            else "none"
        )
        proposal_id = uuid5(
            _PROPOSAL_NAMESPACE,
            ":".join(
                (
                    str(binding.research_campaign_id),
                    str(binding.research_bundle_id),
                    str(binding.research_candidate_id),
                    binding.symbol.value,
                    "35",
                    "50",
                    side.value,
                    value.execution_timestamp.isoformat(),
                    str(len(value.completed_history)),
                    last_timestamp,
                )
            ),
        )
        return TradeProposal(
            proposal_id,
            binding.symbol,
            side,
            quantity,
            value.execution_timestamp,
            f"Filtered-trend BASE_MA 35/50 signal {action} from completed bars.",
        )


def _is_accepted_base_ma_binding(binding: PaperStrategyBinding) -> bool:
    return (
        type(binding) is PaperStrategyBinding
        and binding.strategy_family == FILTERED_TREND_STRATEGY_FAMILY
        and binding.strategy_version == FILTERED_TREND_STRATEGY_VERSION
        and binding.parameter_set == (("fast", 35), ("slow", 50))
    )
