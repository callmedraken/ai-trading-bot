"""O4 equivalence and containment against the accepted current strategy."""

import ast
import builtins
import inspect
import os
import socket
import subprocess
from dataclasses import FrozenInstanceError, fields, replace
from decimal import Context, Decimal, localcontext

import pytest
from tests.strategies.test_moving_average import (
    AMBIENT_CONTEXTS,
    GOLDEN_PROPOSAL_ID,
    GOLDEN_REASON,
    make_context,
)

from trading_bot.gui import operator_strategy_preview as module
from trading_bot.gui.operator_observability_models import (
    OperatorStrategyPreview,
    unavailable_operator_operations_state,
)
from trading_bot.gui.operator_observability_models import (
    OperatorStrategyPreviewStatus as Status,
)
from trading_bot.strategies import (
    MovingAverageCrossoverConfig,
    MovingAverageCrossoverStrategy,
)


@pytest.mark.parametrize("ambient", AMBIENT_CONTEXTS)
def test_current_golden_proposal_and_caller_context_are_preserved(
    ambient: Context,
) -> None:
    context = make_context(["10", "10", "9", "12"])
    config = MovingAverageCrossoverConfig(2, 3, Decimal("1.23456789"))
    before = repr(context)
    with localcontext(ambient) as active:
        flags = dict(active.flags)
        current = MovingAverageCrossoverStrategy(config).evaluate(context)
        first = module.evaluate_operator_strategy_preview(context, config)
        second = module.evaluate_operator_strategy_preview(context, config)
        assert active.flags == flags
    assert current is not None
    assert first == second
    assert first.status is Status.PROPOSAL
    assert first.proposal_id == current.proposal_id == GOLDEN_PROPOSAL_ID
    assert first.reason == current.reason == GOLDEN_REASON
    assert first.side == current.side.value == "BUY"
    assert first.quantity is current.desired_quantity is config.desired_quantity
    assert repr(context) == before


@pytest.mark.parametrize(
    "quantity", [Decimal("1.00"), Decimal("1.2345678901234567890123456789012345")]
)
def test_quantity_representation_is_not_normalized(quantity: Decimal) -> None:
    context = make_context(["10", "10", "9", "12"])
    config = MovingAverageCrossoverConfig(2, 3, quantity)
    current = MovingAverageCrossoverStrategy(config).evaluate(context)
    view = module.evaluate_operator_strategy_preview(context, config)
    assert current is not None
    assert view.proposal_id == current.proposal_id
    assert view.quantity is quantity
    assert view.quantity.as_tuple() == quantity.as_tuple()


def test_current_decimal_subclass_configuration_contract_is_preserved() -> None:
    class CompatibleDecimal(Decimal):
        pass

    quantity = CompatibleDecimal("1.00")
    view = module.evaluate_operator_strategy_preview(
        make_context(["10", "10", "9", "12"]),
        MovingAverageCrossoverConfig(2, 3, quantity),
    )
    assert view.status is Status.PROPOSAL
    assert view.quantity is quantity


@pytest.mark.parametrize(
    ("closes", "invested"),
    [
        (["9", "12", "12", "10"], True),
        (["10", "10", "9", "12"], True),
        (["9", "12", "12", "10"], False),
        (["10", "11", "12", "13"], False),
        (["10", "10", "10", "10"], False),
        (["10", "10", "9"], False),
    ],
)
def test_sell_filters_equality_and_history_match_current(closes, invested) -> None:
    context = make_context(closes, invested=invested)
    config = MovingAverageCrossoverConfig(2, 3, Decimal("99"))
    current = MovingAverageCrossoverStrategy(config).evaluate(context)
    view = module.evaluate_operator_strategy_preview(context, config)
    if current is None:
        assert view == OperatorStrategyPreview(Status.NO_PROPOSAL)
    else:
        assert view.proposal_id == current.proposal_id
        assert view.quantity is current.desired_quantity
        assert view.quantity == Decimal("2.5")
        assert view.side == current.side.value == "SELL"
        assert view.reason == current.reason


def test_evaluates_exactly_once_with_original_ordered_inputs(monkeypatch) -> None:
    context = make_context(["10", "10", "9", "12"], step_index=8)
    config = MovingAverageCrossoverConfig(2, 3, Decimal("1"))
    original = MovingAverageCrossoverStrategy.evaluate
    calls = []

    def evaluate(self, supplied):
        assert self.config is config
        assert supplied is context
        calls.append(supplied)
        return original(self, supplied)

    monkeypatch.setattr(MovingAverageCrossoverStrategy, "evaluate", evaluate)
    view = module.evaluate_operator_strategy_preview(context, config)
    assert calls == [context]
    assert {field.name for field in fields(view)} == {
        "status",
        "proposal_id",
        "reason",
        "side",
        "quantity",
    }
    with pytest.raises(FrozenInstanceError):
        view.reason = "changed"


def test_unavailable_and_blocked_are_sanitized_and_do_not_evaluate(monkeypatch) -> None:
    def forbidden(*args):
        raise AssertionError("must not evaluate")

    class Capability:
        def __repr__(self):
            raise AssertionError("must not inspect capability")

    monkeypatch.setattr(MovingAverageCrossoverStrategy, "evaluate", forbidden)
    assert module.evaluate_operator_strategy_preview() == OperatorStrategyPreview()
    invalid = Capability()
    config = MovingAverageCrossoverConfig(2, 3, Decimal("1"))
    for context, supplied_config in (
        (invalid, config),
        (None, config),
        (invalid, invalid),
    ):
        view = module.evaluate_operator_strategy_preview(context, supplied_config)
        assert view == OperatorStrategyPreview(Status.BLOCKED)
        assert (
            view.message
            == "Strategy preview blocked: diagnostic evaluation unavailable."
        )
    context = make_context(["10", "10", "9", "12"])
    # BacktestContext does not validate every history entry; O4 must reject it.
    contaminated = replace(context, history=(invalid, context.current_bar))
    assert (
        module.evaluate_operator_strategy_preview(contaminated, config).status
        is Status.BLOCKED
    )


def test_unexpected_evaluation_error_is_sanitized(monkeypatch) -> None:
    def fail(*args):
        raise RuntimeError("SECRET <b> C:/private/credential")

    monkeypatch.setattr(MovingAverageCrossoverStrategy, "evaluate", fail)
    view = module.evaluate_operator_strategy_preview(
        make_context(["10", "10", "9", "12"]),
        MovingAverageCrossoverConfig(2, 3, Decimal("1")),
    )
    assert view == OperatorStrategyPreview(Status.BLOCKED)
    assert (
        view.message == "Strategy preview blocked: diagnostic evaluation unavailable."
    )
    assert "SECRET" not in repr(view) + view.message


def test_preview_shape_cannot_expose_details_when_unavailable() -> None:
    with pytest.raises(ValueError):
        OperatorStrategyPreview(Status.BLOCKED, reason="private")
    with pytest.raises(ValueError):
        replace(
            unavailable_operator_operations_state(),
            strategy_preview=OperatorStrategyPreview(Status.NO_PROPOSAL),
        )


def test_adapter_has_no_effect_dependencies_or_identity_arithmetic() -> None:
    tree = ast.parse(inspect.getsource(module))
    imports = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    assert imports == {
        "dataclasses",
        "datetime",
        "decimal",
        "types",
        "uuid",
        "trading_bot.backtesting",
        "trading_bot.domain",
        "trading_bot.ledger",
        "trading_bot.market_calendar",
        "trading_bot.strategies",
        "trading_bot.gui.operator_observability_models",
    }
    calls = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    assert calls.isdisjoint(
        {
            "publish",
            "execute",
            "settle",
            "recover",
            "capture",
            "provision",
            "open",
            "uuid4",
            "uuid5",
            "normalize",
            "quantize",
            "localcontext",
        }
    )


def test_preview_evaluation_has_no_file_network_or_process_effect(monkeypatch) -> None:
    context = make_context(["10", "10", "9", "12"])
    config = MovingAverageCrossoverConfig(2, 3, Decimal("1"))

    def forbidden(*args, **kwargs):
        raise AssertionError("preview attempted an external effect")

    with monkeypatch.context() as guard:
        guard.setattr(builtins, "open", forbidden)
        guard.setattr(os, "open", forbidden)
        guard.setattr(socket, "socket", forbidden)
        guard.setattr(subprocess, "Popen", forbidden)
        view = module.evaluate_operator_strategy_preview(context, config)
    assert view.status is Status.PROPOSAL


def test_oversized_diagnostic_history_blocks_before_strategy(monkeypatch) -> None:
    context = make_context(["10", "10", "9", "12"])
    context = replace(context, history=(context.current_bar,) * 4097)

    def forbidden(*args):
        raise AssertionError("oversized history must not evaluate")

    monkeypatch.setattr(MovingAverageCrossoverStrategy, "evaluate", forbidden)
    assert module.evaluate_operator_strategy_preview(
        context, MovingAverageCrossoverConfig(2, 3, Decimal("1"))
    ) == OperatorStrategyPreview(Status.BLOCKED)
