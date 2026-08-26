"""Deterministic read-only application services for the GUI shell."""

from pathlib import Path

from trading_bot.gui.models import (
    ApplicationOverview,
    ComponentStatus,
    OperatingMode,
    PresentationStatus,
    ResearchPageState,
)
from trading_bot.gui.research_service import (
    CompactReportResearchService,
    unavailable_research_state,
)


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

    def load_research_report(self, artifact_path: Path) -> ResearchPageState:
        """Load one operator-selected report through the application boundary."""
        return CompactReportResearchService(artifact_path).get_research_state()


class ResearchReportGuiApplicationService:
    """Compose the normal overview with one explicit read-only report adapter."""

    def __init__(self, artifact_path: Path) -> None:
        self._overview_service = MockGuiApplicationService()
        self._research_service = CompactReportResearchService(artifact_path)

    def get_overview(self) -> ApplicationOverview:
        """Return the existing deterministic read-only overview."""
        return self._overview_service.get_overview()

    def get_research_state(self) -> ResearchPageState:
        """Return the bounded state for the explicit compact report path."""
        return self._research_service.get_research_state()

    def load_research_report(self, artifact_path: Path) -> ResearchPageState:
        """Load one operator-selected report through the application boundary."""
        return CompactReportResearchService(artifact_path).get_research_state()
