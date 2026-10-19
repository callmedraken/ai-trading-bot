"""Focused Architecture 142-A offline runner and evidence coverage."""

import ast
import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from trading_bot.analytics.analyzer import PerformanceAnalyzer
from trading_bot.backtesting.engine import BacktestEngine
from trading_bot.domain import Bar, Symbol
from trading_bot.experiments.research_strategy_backtest import (
    CompletedResearchStrategyBacktest,
    ResearchStrategyBacktestError,
    ResearchStrategyBacktestEvidence,
    backtest_result_fingerprint,
    build_backtest_config,
    derive_backtest_run_id,
    historical_data_fingerprint,
    run_research_strategy_backtest,
    verify_research_strategy_backtest,
    verify_research_strategy_backtest_evidence,
)
from trading_bot.experiments.research_strategy_definition import (
    ResearchStrategyDefinition,
    ResearchStrategyEvaluationPolicy,
)
from trading_bot.market_calendar.nyse import NYSEMarketCalendar
from trading_bot.market_data.models import (
    AdjustmentType,
    HistoricalDataRequest,
    HistoricalDataResult,
    MultiSymbolHistoricalDataResult,
)
from trading_bot.strategies import (
    MovingAverageCrossoverConfig,
    MovingAverageCrossoverStrategy,
)

HEAD = "a" * 40
TREE = "b" * 40
EVALUATION_HEAD = "c" * 40
EVALUATION_TREE = "d" * 40


class _Provider:
    def __init__(self, data: HistoricalDataResult) -> None:
        self.data = data

    def get_bars(self, request: HistoricalDataRequest) -> HistoricalDataResult:
        assert request == self.data.request
        return self.data


@pytest.fixture
def data() -> HistoricalDataResult:
    symbol = Symbol("SPY")
    request = HistoricalDataRequest(
        symbol,
        datetime(2024, 1, 2, tzinfo=UTC),
        datetime(2024, 1, 10, tzinfo=UTC),
    )
    timestamps = (
        datetime(2024, 1, 2, 20, tzinfo=UTC),
        datetime(2024, 1, 3, 20, tzinfo=UTC),
        datetime(2024, 1, 4, 20, tzinfo=UTC),
        datetime(2024, 1, 5, 20, tzinfo=UTC),
        datetime(2024, 1, 8, 20, tzinfo=UTC),
    )
    opens = ("99", "99", "99", "101", "103")
    closes = ("100", "100", "100", "105", "103")
    bars = tuple(
        Bar(
            symbol,
            timestamp,
            Decimal(open_price),
            max(Decimal(open_price), Decimal(close)),
            min(Decimal(open_price), Decimal(close)),
            Decimal(close),
            1000 + index,
        )
        for index, (timestamp, open_price, close) in enumerate(
            zip(timestamps, opens, closes, strict=True)
        )
    )
    return HistoricalDataResult(request, bars, "test-memory")


@pytest.fixture
def definition() -> ResearchStrategyDefinition:
    return ResearchStrategyDefinition(
        HEAD,
        TREE,
        Symbol("SPY"),
        MovingAverageCrossoverConfig(2, 3, Decimal("1")),
    )


@pytest.fixture
def policy() -> ResearchStrategyEvaluationPolicy:
    return ResearchStrategyEvaluationPolicy(
        starting_cash=Decimal("10000"),
        fixed_commission=Decimal("0"),
        slippage_basis_points=Decimal("0"),
        trading_enabled=True,
        allow_missing_sessions=False,
        max_position_percent=Decimal("0.20"),
        max_total_exposure_percent=Decimal("0.80"),
        max_order_notional=None,
        max_new_position_percent=None,
        minimum_cash_reserve_percent=Decimal("0.10"),
        allow_fractional_shares=True,
        fractional_increment=Decimal("0.001"),
        allow_buying=True,
        allow_selling=True,
        estimated_commission=Decimal("0"),
    )


@pytest.fixture
def completed(definition, policy, data) -> CompletedResearchStrategyBacktest:
    return run_research_strategy_backtest(
        definition,
        policy,
        data,
        evaluation_source_head=EVALUATION_HEAD,
        evaluation_source_tree=EVALUATION_TREE,
    )


def test_historical_fingerprint_is_deterministic_and_single_symbol_only(data) -> None:
    assert historical_data_fingerprint(data) == historical_data_fingerprint(data)
    assert historical_data_fingerprint(data).version == 5
    with pytest.raises(ResearchStrategyBacktestError):
        historical_data_fingerprint(object())  # type: ignore[arg-type]
    with pytest.raises(ResearchStrategyBacktestError):
        historical_data_fingerprint(MultiSymbolHistoricalDataResult)  # type: ignore[arg-type]


def test_runner_requires_definition_symbol_and_raw_daily_data(
    definition, policy, data
) -> None:
    wrong_symbol = Symbol("QQQ")
    wrong_request = HistoricalDataRequest(
        wrong_symbol,
        data.request.start,
        data.request.end,
    )
    wrong_data = HistoricalDataResult(
        wrong_request,
        tuple(
            Bar(
                wrong_symbol,
                bar.timestamp,
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.volume,
            )
            for bar in data.bars
        ),
        data.provider_name,
    )
    with pytest.raises(ResearchStrategyBacktestError):
        run_research_strategy_backtest(
            definition,
            policy,
            wrong_data,
            evaluation_source_head=EVALUATION_HEAD,
            evaluation_source_tree=EVALUATION_TREE,
        )
    split_adjusted = HistoricalDataRequest(
        data.request.symbol,
        data.request.start,
        data.request.end,
        adjustment=AdjustmentType.SPLIT_ADJUSTED,
    )
    split_data = HistoricalDataResult(split_adjusted, data.bars, data.provider_name)
    with pytest.raises(ResearchStrategyBacktestError):
        run_research_strategy_backtest(
            definition,
            policy,
            split_data,
            evaluation_source_head=EVALUATION_HEAD,
            evaluation_source_tree=EVALUATION_TREE,
        )


def test_run_id_is_framed_and_standalone_is_not_caller_selectable() -> None:
    values = [UUID(int=1), UUID(int=2), UUID(int=3)]
    run_id = derive_backtest_run_id(*values)
    assert run_id == derive_backtest_run_id(*values)
    with pytest.raises(ResearchStrategyBacktestError):
        derive_backtest_run_id(*values, fold_role="CUSTOM")
    with pytest.raises(ResearchStrategyBacktestError):
        derive_backtest_run_id(*values, fold_role="STANDALONE", fold_id=UUID(int=4))


def test_runner_matches_direct_backtest_engine_and_analyzer(
    definition, policy, data, completed
) -> None:
    run_id = completed.result.config.run_id
    direct_config = build_backtest_config(policy, run_id, data)
    direct_result = BacktestEngine(_Provider(data), NYSEMarketCalendar()).run(
        direct_config,
        MovingAverageCrossoverStrategy(definition.strategy_config),
    )
    assert direct_result == completed.result
    assert PerformanceAnalyzer().analyze(direct_result) == completed.performance_report
    assert completed.evidence.final_equity == direct_result.final_equity


def test_inherited_no_lookahead_and_next_open_fill_behavior(completed) -> None:
    assert all(step.proposal is None for step in completed.result.steps[:3])
    proposal_step = completed.result.steps[3]
    assert proposal_step.proposal is not None
    assert proposal_step.proposal.created_at == proposal_step.bar.timestamp
    assert proposal_step.opening_fill is None
    next_step = completed.result.steps[4]
    assert next_step.opening_fill is not None
    assert next_step.opening_fill.filled_at == next_step.bar.timestamp
    assert next_step.opening_fill.price == next_step.bar.open


def test_complete_result_fingerprint_changes_for_semantic_mutations(completed) -> None:
    original = backtest_result_fingerprint(completed.result)
    provider_changed = replace(completed.result, provider_name="other-memory")
    assert backtest_result_fingerprint(provider_changed) != original
    proposal = completed.result.proposals[0]
    proposal_changed = replace(proposal, reason="semantically changed")
    proposals = (proposal_changed, *completed.result.proposals[1:])
    result_changed = replace(completed.result, proposals=proposals)
    assert backtest_result_fingerprint(result_changed) != original


def test_evidence_canonical_json_and_parser_does_not_execute(
    completed, monkeypatch
) -> None:
    encoded = completed.evidence.to_json()
    assert encoded == json.dumps(
        json.loads(encoded), sort_keys=True, separators=(",", ":")
    )
    monkeypatch.setattr(
        BacktestEngine,
        "run",
        lambda *args, **kwargs: pytest.fail("evidence parser executed research"),
    )
    assert ResearchStrategyBacktestEvidence.from_json(encoded) == completed.evidence


def test_external_verifier_replays_exact_result_report_and_evidence(
    completed, data
) -> None:
    verify_research_strategy_backtest(
        completed,
        data,
        evaluation_source_head=EVALUATION_HEAD,
        evaluation_source_tree=EVALUATION_TREE,
    )
    verify_research_strategy_backtest_evidence(
        completed.evidence,
        completed.definition,
        completed.evaluation_policy,
        data,
        completed.result,
        completed.performance_report,
        evaluation_source_head=EVALUATION_HEAD,
        evaluation_source_tree=EVALUATION_TREE,
    )


@pytest.mark.parametrize("attribute", ["result", "performance_report", "evidence"])
def test_external_verifier_rejects_tampering(completed, data, attribute) -> None:
    if attribute == "result":
        tampered = replace(completed.result, provider_name="tampered")
        with pytest.raises(ResearchStrategyBacktestError):
            verify_research_strategy_backtest_evidence(
                completed.evidence,
                completed.definition,
                completed.evaluation_policy,
                data,
                tampered,
                completed.performance_report,
                evaluation_source_head=EVALUATION_HEAD,
                evaluation_source_tree=EVALUATION_TREE,
            )
    elif attribute == "performance_report":
        tampered = replace(
            completed.performance_report,
            total_return=completed.performance_report.total_return + Decimal("1"),
        )
        with pytest.raises(ResearchStrategyBacktestError):
            verify_research_strategy_backtest_evidence(
                completed.evidence,
                completed.definition,
                completed.evaluation_policy,
                data,
                completed.result,
                tampered,
                evaluation_source_head=EVALUATION_HEAD,
                evaluation_source_tree=EVALUATION_TREE,
            )
    else:
        tampered = replace(completed.evidence, total_return=Decimal("1"))
        with pytest.raises(ResearchStrategyBacktestError):
            verify_research_strategy_backtest_evidence(
                tampered,
                completed.definition,
                completed.evaluation_policy,
                data,
                completed.result,
                completed.performance_report,
                evaluation_source_head=EVALUATION_HEAD,
                evaluation_source_tree=EVALUATION_TREE,
            )


def test_caller_data_is_not_changed_by_success_or_failure(
    completed, data, definition, policy
) -> None:
    before = data
    assert completed.historical_data == before
    with pytest.raises(ResearchStrategyBacktestError):
        run_research_strategy_backtest(
            definition,
            policy,
            object(),  # type: ignore[arg-type]
            evaluation_source_head=EVALUATION_HEAD,
            evaluation_source_tree=EVALUATION_TREE,
        )
    assert data == before


def test_package_exports_are_additive() -> None:
    import trading_bot.experiments as package
    from trading_bot.experiments import research_strategy_backtest as backtest
    from trading_bot.experiments import research_strategy_definition as definition

    for name in (*definition.__all__, *backtest.__all__):
        assert getattr(package, name) is getattr(
            definition if hasattr(definition, name) else backtest, name
        )


def test_source_surface_has_no_prohibited_capability_imports() -> None:
    source = open(
        "src/trading_bot/experiments/research_strategy_backtest.py",
        encoding="utf-8",
    ).read()
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    )
    banned = {
        "ProductionStrategyContract",
        "build_production_strategy",
        "HistoricalExperimentRunner",
        "HistoricalExperimentWalkForwardRunner",
        "OptimizedPaperPortfolioSimulator",
        "MultiSymbolBacktestEngine",
        "uuid4",
        "random",
        "runtime",
        "Robinhood",
        "Alpaca",
        "subprocess",
        "socket",
        "sqlite3",
    }
    assert not imported & banned
