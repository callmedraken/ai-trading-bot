from decimal import Decimal

import pytest

from trading_bot.config import TradingBotConfig


def test_defaults_are_safe_for_paper_trading() -> None:
    config = TradingBotConfig()

    assert config.starting_cash == Decimal("10000.00")
    assert config.paper_trading is True
    assert config.allow_margin is False
    assert config.allow_short_selling is False
    assert config.allow_options is False
    assert config.allow_crypto is False


def test_accepts_custom_positive_starting_cash() -> None:
    config = TradingBotConfig(starting_cash=Decimal("2500.50"))

    assert config.starting_cash == Decimal("2500.50")


@pytest.mark.parametrize(
    "setting",
    [
        "allow_margin",
        "allow_short_selling",
        "allow_options",
        "allow_crypto",
    ],
)
def test_rejects_enabling_prohibited_feature(setting: str) -> None:
    with pytest.raises(ValueError, match=setting):
        TradingBotConfig(**{setting: True})


def test_rejects_disabling_paper_trading() -> None:
    with pytest.raises(ValueError, match="paper_trading must remain enabled"):
        TradingBotConfig(paper_trading=False)


@pytest.mark.parametrize("starting_cash", [Decimal("0"), Decimal("-0.01")])
def test_rejects_non_positive_starting_cash(starting_cash: Decimal) -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        TradingBotConfig(starting_cash=starting_cash)


def test_rejects_non_decimal_starting_cash() -> None:
    with pytest.raises(TypeError, match="must be a Decimal"):
        TradingBotConfig(starting_cash=10_000)  # type: ignore[arg-type]
