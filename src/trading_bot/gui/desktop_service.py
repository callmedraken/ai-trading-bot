"""Current artifact-only presentation service; no legacy operational adapters."""

from pathlib import Path

from trading_bot.gui.desktop_campaign_service import DesktopCampaignResearchService
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
from trading_bot.gui.production_strategy_models import (
    ProductionStrategyPageState,
    unavailable_production_strategy_state,
)
from trading_bot.gui.research_candidate_lifecycle_models import (
    ResearchCandidateLifecyclePageState,
    unavailable_research_candidate_lifecycle_state,
)
from trading_bot.gui.research_service import unavailable_research_state
from trading_bot.gui.runtime_models import RuntimePageState, unavailable_runtime_state


class DesktopGuiService:
    """Existing Research page plus unavailable historical evidence surfaces.

    Active runtime controls use the separate supervisor boundary. Artifact data
    never becomes operating strategy, promotion, paper or broker authority.
    """

    def __init__(self, research_report: Path | None = None) -> None:
        self._research = (
            DesktopCampaignResearchService(research_report).get_research_state()
            if research_report is not None
            else unavailable_research_state()
        )

    def get_overview(self) -> ApplicationOverview:
        return ApplicationOverview(
            mode=OperatingMode.SIMULATED_PAPER,
            environment="Local desktop · P4 inert workers",
            summary=(
                "Explicit Start/Stop. Trading transport NOT_CONNECTED; LIVE disabled."
            ),
            components=(
                ComponentStatus(
                    key="trading",
                    title="Trading · P4 inert worker",
                    status=PresentationStatus.INFO,
                    detail="No strategy or orders. External transport NOT_CONNECTED.",
                ),
                ComponentStatus(
                    key="research",
                    title="Offline research",
                    status=PresentationStatus.INFO,
                    detail=(
                        "Read-only P3 campaign verification; no promotion authority."
                    ),
                ),
            ),
        )

    def get_research_state(self) -> ResearchPageState:
        return self._research

    def load_research_report(self, artifact_path: Path) -> ResearchPageState:
        self._research = DesktopCampaignResearchService(
            artifact_path
        ).get_research_state()
        return self._research

    def get_market_data_state(self) -> MarketDataPageState:
        return unavailable_market_data_state()

    def get_paper_state(self) -> PaperPageState:
        return unavailable_paper_state()

    def get_paper_account_state(self) -> PaperAccountPageState:
        return unavailable_paper_account_state()

    def get_operator_observability_state(self) -> OperatorOperationsPageState:
        return unavailable_operator_operations_state()

    def get_runtime_state(self) -> RuntimePageState:
        return unavailable_runtime_state()

    def get_production_strategy_state(self) -> ProductionStrategyPageState:
        return unavailable_production_strategy_state()

    def get_research_candidate_lifecycle_state(
        self,
    ) -> ResearchCandidateLifecyclePageState:
        return unavailable_research_candidate_lifecycle_state()
