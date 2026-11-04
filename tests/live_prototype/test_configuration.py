from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from trading_bot.live_prototype.configuration import (
    CompletedSignalInputs,
    PrototypeSessionConfiguration,
    ResearchCampaignSpec,
    SelectedStrategyBinding,
)


def inputs():
    return CompletedSignalInputs(
        "SPY",
        (date(2026, 1, 2),),
        (date(2026, 1, 2),),
        (Decimal("100.00"),),
        "ALPACA_ALL_ADJUSTED_PRICE_V1",
        "a" * 64,
        datetime(2026, 1, 5, 15, tzinfo=UTC),
        datetime(2026, 1, 5, tzinfo=UTC),
    )


def test_completed_input_identity_is_ambient_independent_and_basis_bound():
    original = inputs()
    with localcontext() as context:
        context.prec = 2
        assert original.digest == replace(original, closes=(Decimal("100"),)).digest
    assert (
        original.digest
        != replace(
            original, price_basis="ROBINHOOD_HISTORY59_PLUS_OFFICIAL_CLOSE_V1"
        ).digest
    )
    for updates in (
        {"sessions": ()},
        {"closes": (Decimal("NaN"),)},
        {"sessions": (date(2026, 1, 3),)},
        {"cutoff": datetime(2026, 1, 2, tzinfo=UTC)},
    ):
        with pytest.raises(ValueError):
            replace(original, **updates)

    same_date_completion = replace(
        original,
        as_of=datetime(2026, 1, 2, 16, tzinfo=UTC),
        cutoff=datetime(2026, 1, 2, 16, tzinfo=UTC),
    )
    assert same_date_completion.cutoff == same_date_completion.as_of


def test_research_binding_and_configuration_never_promote_live():
    assert ResearchCampaignSpec().comparison_configurations == 3
    with pytest.raises(ValueError):
        ResearchCampaignSpec(independent_holdout=True)
    binding = SelectedStrategyBinding("PRICE_SMA200_V1", "a" * 64, "b" * 64)
    with pytest.raises(ValueError):
        replace(binding, live_eligible=True)
    configuration = PrototypeSessionConfiguration(
        "SYNTHETIC",
        "a" * 40,
        "b" * 40,
        Path(r"F:\AI\temp\synthetic-config-test"),
        binding,
    )
    with pytest.raises(ValueError):
        replace(configuration, mode="LIVE")
    with pytest.raises(ValueError):
        replace(configuration, read_policy="CONNECT")
