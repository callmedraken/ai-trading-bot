"""Immutable source-owned configuration for the first P6 live trial."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID, uuid5

from trading_bot.desktop_paper.research_binding import (
    FILTERED_TREND_BUNDLE_ID,
    FILTERED_TREND_CAMPAIGN_ID,
    FILTERED_TREND_CANDIDATE_ID,
    FILTERED_TREND_STRATEGY_FAMILY,
    FILTERED_TREND_STRATEGY_VERSION,
)
from trading_bot.domain import Symbol

LIVE_SYMBOL: Final = Symbol("SPY")
LIVE_FAST: Final = 35
LIVE_SLOW: Final = 50
LIVE_PURPOSE: Final = "LIVE_PRODUCTION_TRIAL"
MAX_ORDER_DOLLARS: Final = Decimal("10.00")
MAX_BOT_GROSS_EXPOSURE_DOLLARS: Final = Decimal("10.00")
LIVE_OBSERVATION_BASIS: Final = "ROBINHOOD_RAW_DAILY_REGULAR_V1"
LIVE_POLICY_SCHEMA: Final = "arch147-tiny-live-policy/v1"
LIVE_POLICY_NAMESPACE: Final = UUID("3b2b2dd1-4be7-5a3d-9611-34dc0e0d6c6d")


@dataclass(frozen=True, slots=True)
class TinyLivePolicy:
    """The only strategy and dollar ceiling accepted by P6 source."""

    strategy_family: str = FILTERED_TREND_STRATEGY_FAMILY
    strategy_version: str = FILTERED_TREND_STRATEGY_VERSION
    campaign_id: UUID = UUID(FILTERED_TREND_CAMPAIGN_ID)
    bundle_id: UUID = UUID(FILTERED_TREND_BUNDLE_ID)
    candidate_id: UUID = UUID(FILTERED_TREND_CANDIDATE_ID)
    symbol: Symbol = LIVE_SYMBOL
    fast: int = LIVE_FAST
    slow: int = LIVE_SLOW
    purpose: Literal["LIVE_PRODUCTION_TRIAL"] = LIVE_PURPOSE
    max_order_dollars: Decimal = MAX_ORDER_DOLLARS
    max_gross_exposure_dollars: Decimal = MAX_BOT_GROSS_EXPOSURE_DOLLARS

    def __post_init__(self) -> None:
        if (
            self.strategy_family != FILTERED_TREND_STRATEGY_FAMILY
            or self.strategy_version != FILTERED_TREND_STRATEGY_VERSION
            or self.campaign_id != UUID(FILTERED_TREND_CAMPAIGN_ID)
            or self.bundle_id != UUID(FILTERED_TREND_BUNDLE_ID)
            or self.candidate_id != UUID(FILTERED_TREND_CANDIDATE_ID)
            or self.symbol != LIVE_SYMBOL
            or self.fast != LIVE_FAST
            or self.slow != LIVE_SLOW
            or self.purpose != LIVE_PURPOSE
            or self.max_order_dollars != MAX_ORDER_DOLLARS
            or self.max_gross_exposure_dollars != MAX_BOT_GROSS_EXPOSURE_DOLLARS
        ):
            raise ValueError("P6 policy is source-owned and immutable")
        if type(self.symbol) is not Symbol:
            raise TypeError("symbol must be an exact Symbol")
        if type(self.fast) is not int or type(self.slow) is not int:
            raise TypeError("P6 moving-average windows must be integers")
        for value in (self.max_order_dollars, self.max_gross_exposure_dollars):
            if type(value) is not Decimal or not value.is_finite() or value <= 0:
                raise ValueError("P6 dollar ceilings must be positive finite Decimals")

    def semantic_material(self) -> tuple[object, ...]:
        return (
            LIVE_POLICY_SCHEMA,
            self.strategy_family,
            self.strategy_version,
            str(self.campaign_id),
            str(self.bundle_id),
            str(self.candidate_id),
            str(self.symbol),
            self.fast,
            self.slow,
            self.purpose,
            _decimal(self.max_order_dollars),
            _decimal(self.max_gross_exposure_dollars),
        )

    @property
    def policy_id(self) -> UUID:
        return uuid5(
            LIVE_POLICY_NAMESPACE,
            json.dumps(self.semantic_material(), separators=(",", ":")),
        )


def _decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("policy Decimal must be finite")
    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered
