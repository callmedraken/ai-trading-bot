"""Pure-Python tests for GUI presentation contracts."""

import pytest

from trading_bot.gui import (
    ApplicationOverview,
    ComponentStatus,
    OperatingMode,
    PresentationStatus,
)
from trading_bot.gui.mock_service import MockGuiApplicationService


def test_mock_service_returns_deterministic_overview() -> None:
    service = MockGuiApplicationService()

    first = service.get_overview()
    second = service.get_overview()

    assert first == second
    assert first.mode is OperatingMode.RESEARCH
    assert tuple(item.key for item in first.components) == (
        "research",
        "paper",
        "paper-account",
        "market-data",
        "operations",
        "system",
    )
    assert first.components[2].status is PresentationStatus.UNAVAILABLE
    assert first.components[3].status is PresentationStatus.UNAVAILABLE


def test_application_overview_rejects_duplicate_component_keys() -> None:
    component = ComponentStatus(
        key="research",
        title="Research",
        status=PresentationStatus.INFO,
        detail="Read-only status.",
    )

    with pytest.raises(ValueError, match="component keys must be unique"):
        ApplicationOverview(
            mode=OperatingMode.RESEARCH,
            environment="test",
            summary="test overview",
            components=(component, component),
        )


def test_gui_public_api_remains_qt_free() -> None:
    overview = MockGuiApplicationService().get_overview()

    assert isinstance(overview, ApplicationOverview)
