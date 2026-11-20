"""Fixed fake-only Architecture 148 churn policy tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trading_bot.experiments.arch148_churn_policy import (
    CHURN_POLICIES,
    CONTROL,
    OPPOSITE_CONFIRMATION_EXIT,
    OPPOSITE_EXIT_COOLDOWN_15M,
    OPPOSITE_EXIT_COOLDOWN_30M,
)
from trading_bot.live_runtime.models import (
    MarketQuality,
    MarketRegime,
    SignalAnalysis,
    SignalPoint,
    TargetPosition,
)

_AT = datetime(2023, 11, 24, 15, 0, tzinfo=UTC)


def _signal(
    previous: MarketRegime,
    latest: MarketRegime,
    *,
    confirmation: MarketRegime | None = None,
    quality: MarketQuality = MarketQuality.READY,
    gap: timedelta = timedelta(minutes=5),
) -> SignalAnalysis:
    return SignalAnalysis(
        quality,
        latest if quality is MarketQuality.READY else None,
        confirmation if quality is MarketQuality.READY else None,
        SignalPoint(
            _AT,
            Decimal("100"),
            Decimal("100"),
            Decimal("100"),
            Decimal("100"),
            Decimal("50"),
            latest,
        ),
        SignalPoint(
            _AT - gap,
            Decimal("100"),
            Decimal("100"),
            Decimal("100"),
            Decimal("100"),
            Decimal("50"),
            previous,
        ),
        "SYNTHETIC_CHURN_POLICY_SIGNAL",
    )


def test_exact_fixed_variant_set_and_cooldown_durations() -> None:
    assert CHURN_POLICIES == (
        CONTROL,
        OPPOSITE_CONFIRMATION_EXIT,
        OPPOSITE_EXIT_COOLDOWN_15M,
        OPPOSITE_EXIT_COOLDOWN_30M,
    )
    assert tuple(policy.name for policy in CHURN_POLICIES) == (
        "CONTROL",
        "OPPOSITE_CONFIRMATION_EXIT",
        "OPPOSITE_EXIT_COOLDOWN_15M",
        "OPPOSITE_EXIT_COOLDOWN_30M",
    )
    assert tuple(policy.cooldown_duration for policy in CHURN_POLICIES) == (
        timedelta(),
        timedelta(),
        timedelta(minutes=15),
        timedelta(minutes=30),
    )
    with pytest.raises(AttributeError):
        CONTROL.value = "UNREVIEWED_VARIANT"


def test_control_keeps_the_existing_any_nonheld_two_bar_exit() -> None:
    neutral = _signal(MarketRegime.NEUTRAL, MarketRegime.NEUTRAL)

    assert CONTROL.should_exit_regime(neutral, TargetPosition.TQQQ)
    assert CONTROL.reversal_source(neutral) is None


@pytest.mark.parametrize(
    ("held", "opposite"),
    [
        (TargetPosition.TQQQ, MarketRegime.BEARISH),
        (TargetPosition.SQQQ, MarketRegime.BULLISH),
    ],
)
def test_candidate_requires_two_adjacent_opposite_candidate_bars(
    held: TargetPosition, opposite: MarketRegime
) -> None:
    confirmed = _signal(opposite, opposite, confirmation=opposite)
    one_opposite = _signal(MarketRegime.NEUTRAL, opposite, confirmation=opposite)
    nonadjacent = _signal(
        opposite,
        opposite,
        confirmation=opposite,
        gap=timedelta(minutes=10),
    )
    invalid = _signal(opposite, opposite, quality=MarketQuality.GAP)

    assert OPPOSITE_CONFIRMATION_EXIT.should_exit_regime(confirmed, held)
    assert OPPOSITE_CONFIRMATION_EXIT.reversal_source(confirmed) is opposite
    assert not OPPOSITE_CONFIRMATION_EXIT.should_exit_regime(one_opposite, held)
    assert OPPOSITE_CONFIRMATION_EXIT.reversal_source(one_opposite) is None
    assert not OPPOSITE_CONFIRMATION_EXIT.should_exit_regime(nonadjacent, held)
    assert OPPOSITE_CONFIRMATION_EXIT.reversal_source(nonadjacent) is None
    assert not OPPOSITE_CONFIRMATION_EXIT.should_exit_regime(invalid, held)
