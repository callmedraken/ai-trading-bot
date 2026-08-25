"""Deterministic mock application service for the GUI-A1 shell."""

from trading_bot.gui.models import (
    ApplicationOverview,
    ComponentStatus,
    OperatingMode,
    PresentationStatus,
)


class MockGuiApplicationService:
    """Return static presentation data without invoking application effects."""

    def get_overview(self) -> ApplicationOverview:
        """Return deterministic GUI-A1 preview state."""
        return ApplicationOverview(
            mode=OperatingMode.RESEARCH,
            environment="GUI preview",
            summary=(
                "Read-only GUI foundation using deterministic mock application state."
            ),
            components=(
                ComponentStatus(
                    key="research",
                    title="Research",
                    status=PresentationStatus.HEALTHY,
                    detail="Offline research and backtesting views can be added next.",
                ),
                ComponentStatus(
                    key="paper",
                    title="Paper Operation",
                    status=PresentationStatus.INFO,
                    detail="GUI-A1 exposes no paper-operation actions.",
                ),
                ComponentStatus(
                    key="market-data",
                    title="Market Data",
                    status=PresentationStatus.UNAVAILABLE,
                    detail="Production capture is intentionally not connected to GUI-A1.",
                ),
                ComponentStatus(
                    key="system",
                    title="System",
                    status=PresentationStatus.INFO,
                    detail="The shell is running against deterministic mock data.",
                ),
            ),
        )
