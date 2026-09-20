"""Deterministic read-only application services for the GUI shell."""

from pathlib import Path

from trading_bot.gui.market_data_models import (
    MarketDataPageState,
    unavailable_market_data_state,
)
from trading_bot.gui.models import (
    ApplicationOverview,
    ComponentStatus,
    OperatingMode,
    PresentationStatus,
    ResearchPageState,
)
from trading_bot.gui.operator_observability_models import (
    OperatorOperationsPageState,
    unavailable_operator_operations_state,
)
from trading_bot.gui.paper_account_models import (
    PaperAccountPageState,
    unavailable_paper_account_state,
)
from trading_bot.gui.paper_models import PaperPageState, unavailable_paper_state
from trading_bot.gui.research_service import (
    CompactReportResearchService,
    unavailable_research_state,
)


class MockGuiApplicationService:
    """Return static presentation data without invoking application effects."""

    def get_overview(self) -> ApplicationOverview:
        """Return deterministic read-only overview state."""
        return ApplicationOverview(
            mode=OperatingMode.RESEARCH,
            environment="Local read-only GUI",
            summary="Read-only GUI; local compact research reports may be displayed.",
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
                    detail=(
                        "Paper Operation is read-only; execution controls are not "
                        "connected."
                    ),
                ),
                ComponentStatus(
                    key="paper-account",
                    title="Paper Account",
                    status=PresentationStatus.UNAVAILABLE,
                    detail=(
                        "No verified paper-account checkpoint is connected to "
                        "this read-only GUI."
                    ),
                ),
                ComponentStatus(
                    key="market-data",
                    title="Market Data",
                    status=PresentationStatus.UNAVAILABLE,
                    detail=(
                        "No verified market-data snapshot artifact is connected "
                        "to this read-only GUI."
                    ),
                ),
                ComponentStatus(
                    key="operations",
                    title="Operations",
                    status=PresentationStatus.UNAVAILABLE,
                    detail=(
                        "Production operator observability is not connected to "
                        "this GUI service."
                    ),
                ),
                ComponentStatus(
                    key="system",
                    title="System",
                    status=PresentationStatus.INFO,
                    detail="The GUI is read-only; no production authority is granted.",
                ),
            ),
        )

    def get_research_state(self) -> ResearchPageState:
        """Return the deterministic empty research state."""
        return unavailable_research_state()

    def get_paper_state(self) -> PaperPageState:
        """Return the deterministic unavailable paper-inspection state."""
        return unavailable_paper_state()

    def get_market_data_state(self) -> MarketDataPageState:
        """Return the deterministic unavailable market-data state."""
        return unavailable_market_data_state()

    def get_paper_account_state(self) -> PaperAccountPageState:
        """Return the deterministic unavailable paper-account state."""
        return unavailable_paper_account_state()

    def get_operator_observability_state(self) -> OperatorOperationsPageState:
        """Return the deterministic unavailable Operations state."""
        return unavailable_operator_operations_state()

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

    def get_paper_state(self) -> PaperPageState:
        """Return the deterministic unavailable paper-inspection state."""
        return self._overview_service.get_paper_state()

    def get_market_data_state(self) -> MarketDataPageState:
        """Return the deterministic unavailable market-data state."""
        return self._overview_service.get_market_data_state()

    def get_paper_account_state(self) -> PaperAccountPageState:
        """Return the deterministic unavailable paper-account state."""
        return self._overview_service.get_paper_account_state()

    def get_operator_observability_state(self) -> OperatorOperationsPageState:
        """Return the deterministic unavailable Operations state."""
        return unavailable_operator_operations_state()

    def load_research_report(self, artifact_path: Path) -> ResearchPageState:
        """Load one operator-selected report through the application boundary."""
        return CompactReportResearchService(artifact_path).get_research_state()
