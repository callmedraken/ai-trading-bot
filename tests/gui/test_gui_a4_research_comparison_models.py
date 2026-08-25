"""Plain-Python contract checks for bounded GUI-A4 comparison state."""

import pytest

from trading_bot.gui.models import ResearchComparisonState


def test_gui_a4_comparison_selection_is_canonical_and_bounded() -> None:
    state = ResearchComparisonState().select(3).select(1).select(2).select(0)

    assert state.caller_ordinals == (0, 1, 2, 3)
    assert state.is_ready
    assert state.select(4) is state
    assert state.select(2) is state


def test_gui_a4_comparison_model_rejects_invalid_identity_sets() -> None:
    with pytest.raises(ValueError, match="four variants"):
        ResearchComparisonState((0, 1, 2, 3, 4))
    with pytest.raises(ValueError, match="unique"):
        ResearchComparisonState((0, 0))
    with pytest.raises(ValueError, match="caller order"):
        ResearchComparisonState((1, 0))
    with pytest.raises(ValueError, match="nonnegative integers"):
        ResearchComparisonState((True,))
    with pytest.raises(ValueError, match="nonnegative integer"):
        ResearchComparisonState((1,)).remove(True)


def test_gui_a4_comparison_remove_and_clear_are_immutable() -> None:
    original = ResearchComparisonState((0, 1, 3))

    removed = original.remove(1)
    cleared = removed.clear()

    assert original.caller_ordinals == (0, 1, 3)
    assert removed.caller_ordinals == (0, 3)
    assert cleared.caller_ordinals == ()
