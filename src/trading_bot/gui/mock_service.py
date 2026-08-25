"""Deterministic mock application service for the GUI-A1 shell."""

from trading_bot.gui.models import (
    ApplicationOverview,
    ComponentStatus,
    OperatingMode,
    PresentationStatus,
    ResearchPageState,
)
from trading_bot.gui.research_service import unavailable_research_state


class MockGuiApplicationService:
    """Return static presentation data without invoking application effects."""

    def get_overview(self) -> ApplicationOverview:
        """Return deterministic GUI-A2 preview state."""
        return ApplicationOverview(
            mode=OperatingMode.RESEARCH,
            environment="GUI preview",
            summary="Read-only GUI using bounded application presentation state.",
            components=(
                ComponentStatus(
                    key="research",
                    title="Research",
                    status=PresentationStatus.INFO,
                    detail="Compact historical reports are presented read-only.",
                ),
                ComponentStatus(
                    key="paper",
                    title="Paper Operation",
                    status=PresentationStatus.INFO,
                    detail="GUI-A2 exposes no paper-operation actions.",
                ),
                ComponentStatus(
                    key="market-data",
                    title="Market Data",
                    status=PresentationStatus.UNAVAILABLE,
                    detail="Production capture is intentionally not connected.",
                ),
                ComponentStatus(
                    key="system",
                    title="System",
                    status=PresentationStatus.INFO,
                    detail="The shell is running against deterministic mock data.",
                ),
            ),
        )

    def get_research_state(self) -> ResearchPageState:
        """Return the deterministic GUI-A2 empty research state."""
        return unavailable_research_state()
