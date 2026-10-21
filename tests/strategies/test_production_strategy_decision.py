from __future__ import annotations

import ast
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from tests.runtime.test_manual_paper_strategy_plan import (
    _DEFAULT_CONFIG,
    _NEXT_SESSION,
    QQQ,
    SPY,
    _decision_request,
    _request,
    calendar,
)

from scripts import checkpoint_runner
from scripts import run_test_certification as certification
from trading_bot.runtime import ManualPaperStrategySignalStatus
from trading_bot.runtime.manual_paper_strategy_plan import (
    build_manual_paper_strategy_decision,
)
from trading_bot.strategies import MovingAverageCrossoverConfig
from trading_bot.strategies import production_decision as subject
from trading_bot.strategies.production import ProductionStrategyContract

NAME = "arch134-production-strategy-decision"


def _contract(
    *,
    target: date = _NEXT_SESSION.session_date,
    symbol=SPY,
    config: MovingAverageCrossoverConfig = _DEFAULT_CONFIG,
) -> ProductionStrategyContract:
    return ProductionStrategyContract(
        target,
        "a" * 40,
        "b" * 40,
        symbol,
        config,
    )


def _decision_request_default(**kwargs):
    return _decision_request(_request(**kwargs))


def test_real_arch94_bridge_returns_exact_trade_proposal() -> None:
    request = _decision_request_default()
    result = subject.build_production_strategy_decision(
        _contract(),
        request,
        calendar(),
    )

    assert result.contract == _contract()
    assert result.status is subject.ProductionStrategyDecisionStatus.TRADE_PROPOSAL
    assert (
        result.prepared.signal_status is ManualPaperStrategySignalStatus.TRADE_PROPOSAL
    )
    assert result.proposal is result.prepared.strategy_proposal
    assert result.proposal is not None
    assert result.proposal.symbol == SPY
    assert result.prepared.intended_execution_session == _NEXT_SESSION


def test_real_arch94_bridge_preserves_no_signal() -> None:
    request = _decision_request_default(
        closes=("10", "11", "12"),
        selected_close="13",
    )
    result = subject.build_production_strategy_decision(
        _contract(),
        request,
        calendar(),
    )

    assert result.status is subject.ProductionStrategyDecisionStatus.NO_SIGNAL
    assert result.prepared.signal_status is ManualPaperStrategySignalStatus.NO_SIGNAL
    assert result.prepared.strategy_proposal is None
    assert result.proposal is None


def test_arch94_builder_is_invoked_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _decision_request_default()
    calls = []

    def build_once(actual_request, actual_calendar):
        calls.append((actual_request, actual_calendar))
        return build_manual_paper_strategy_decision(
            actual_request,
            actual_calendar,
        )

    monkeypatch.setattr(subject, "build_manual_paper_strategy_decision", build_once)
    result = subject.build_production_strategy_decision(
        _contract(),
        request,
        calendar(),
    )

    assert result.proposal is result.prepared.strategy_proposal
    assert len(calls) == 1
    assert calls[0][0] is request


def test_config_mismatch_blocks_before_strategy_evaluation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _decision_request_default()
    different = MovingAverageCrossoverConfig(2, 4, _DEFAULT_CONFIG.desired_quantity)
    calls = 0

    def forbidden(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("builder must not run")

    monkeypatch.setattr(subject, "build_manual_paper_strategy_decision", forbidden)
    with pytest.raises(ValueError, match="does not match production contract"):
        subject.build_production_strategy_decision(
            _contract(config=different),
            request,
            calendar(),
        )
    assert calls == 0


def test_history_seed_symbol_mismatch_blocks_before_strategy_evaluation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _decision_request_default()
    calls = 0

    def forbidden(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("builder must not run")

    monkeypatch.setattr(subject, "build_manual_paper_strategy_decision", forbidden)
    with pytest.raises(ValueError, match="does not match production contract"):
        subject.build_production_strategy_decision(
            _contract(symbol=QQQ),
            request,
            calendar(),
        )
    assert calls == 0


def test_target_session_mismatch_blocks_after_single_verified_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _decision_request_default()
    calls = 0

    def build_once(actual_request, actual_calendar):
        nonlocal calls
        calls += 1
        return build_manual_paper_strategy_decision(actual_request, actual_calendar)

    monkeypatch.setattr(subject, "build_manual_paper_strategy_decision", build_once)
    with pytest.raises(ValueError, match="outside production contract"):
        subject.build_production_strategy_decision(
            _contract(target=date(2025, 1, 8)),
            request,
            calendar(),
        )
    assert calls == 1


def test_prepared_config_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _decision_request_default()
    prepared = build_manual_paper_strategy_decision(request, calendar())
    different = MovingAverageCrossoverConfig(2, 4, _DEFAULT_CONFIG.desired_quantity)
    drifted = replace(prepared, strategy_config=different)

    monkeypatch.setattr(
        subject,
        "build_manual_paper_strategy_decision",
        lambda *_: drifted,
    )
    with pytest.raises(ValueError, match="outside production contract"):
        subject.build_production_strategy_decision(
            _contract(),
            request,
            calendar(),
        )


def test_invalid_builder_result_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _decision_request_default()
    monkeypatch.setattr(
        subject,
        "build_manual_paper_strategy_decision",
        lambda *_: object(),
    )
    with pytest.raises(ValueError, match="invalid material"):
        subject.build_production_strategy_decision(
            _contract(),
            request,
            calendar(),
        )


def test_exact_input_types_are_required() -> None:
    request = _decision_request_default()
    with pytest.raises(TypeError):
        subject.build_production_strategy_decision(object(), request, calendar())
    with pytest.raises(TypeError):
        subject.build_production_strategy_decision(_contract(), object(), calendar())


def test_result_model_rejects_status_proposal_inconsistency() -> None:
    request = _decision_request_default()
    prepared = build_manual_paper_strategy_decision(request, calendar())
    assert prepared.strategy_proposal is not None

    with pytest.raises(ValueError):
        subject.ProductionStrategyDecision(
            _contract(),
            prepared,
            subject.ProductionStrategyDecisionStatus.NO_SIGNAL,
            None,
        )
    with pytest.raises(ValueError):
        subject.ProductionStrategyDecision(
            _contract(),
            prepared,
            subject.ProductionStrategyDecisionStatus.TRADE_PROPOSAL,
            replace(prepared.strategy_proposal, reason="different"),
        )


def test_bridge_import_and_call_surface_has_no_effect_or_research_authority() -> None:
    path = Path(subject.__file__)
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert imported <= {
        "__future__",
        "dataclasses",
        "enum",
        "typing",
        "trading_bot.strategies.daily_decision",
        "trading_bot.strategies.history_seed",
        "trading_bot.domain",
        "trading_bot.market_data",
        "trading_bot.runtime.manual_paper_strategy_plan",
        "trading_bot.runtime.strategy_history_seed",
        "trading_bot.strategies.production",
    }
    assert not any(
        fragment in module.lower()
        for module in imported
        for fragment in (
            "robinhood",
            "oauth",
            "sqlite",
            "review_paper",
            "risk",
            "execution",
            "scheduler",
            "experiments",
            "optimization",
            "backtesting",
            "openai",
        )
    )

    calls = {
        getattr(node.func, "attr", getattr(node.func, "id", ""))
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert not calls & {
        "open",
        "eval",
        "exec",
        "__import__",
        "sleep",
        "now",
        "utcnow",
        "run",
        "Popen",
        "connect",
        "request",
        "review_equity_order",
        "place_order",
        "execute",
    }


def test_checkpoint_registration_and_inventory_are_exact() -> None:
    spec = checkpoint_runner._checkpoint_specs()[NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-production-strategy-decision"
    assert (
        spec.authority_check
        is checkpoint_runner._arch134_production_strategy_decision_authority_check
    )
    a = checkpoint_runner.ACTIVE_CI_CHECKPOINTS.index(
        "arch134-production-strategy-contract"
    )
    assert checkpoint_runner.ACTIVE_CI_CHECKPOINTS[a : a + 2] == (
        "arch134-production-strategy-contract",
        NAME,
    )
    assert len(checkpoint_runner.ACTIVE_CI_CHECKPOINTS) == 70

    root = Path(certification.__file__).resolve().parents[1]
    inventory = certification.discover_inventory(root)
    profiles = {
        name: certification.select_inventory(inventory, name)
        for name in ("full", "robinhood", "legacy", "exhaustive")
    }
    assert {name: len(value) for name, value in profiles.items()} == {
        "full": 192,
        "robinhood": 103,
        "legacy": 222,
        "exhaustive": 414,
    }
    assert "tests/strategies/test_production_strategy_decision.py" in profiles["full"]
    assert (
        "tests/strategies/test_production_strategy_decision.py"
        not in profiles["robinhood"]
    )
