from trading_bot.portfolio import (
    PortfolioOptimizationRequest,
    PortfolioOptimizationResult,
    PortfolioOptimizer,
)


class FakeOptimizer:
    def optimize(
        self, request: PortfolioOptimizationRequest
    ) -> PortfolioOptimizationResult:
        raise NotImplementedError


def accepts_optimizer(optimizer: PortfolioOptimizer) -> PortfolioOptimizer:
    return optimizer


def test_fake_optimizer_conforms_without_runtime_protocol_checking() -> None:
    optimizer = FakeOptimizer()
    assert accepts_optimizer(optimizer) is optimizer
