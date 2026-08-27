"""Plain-Python service boundary consumed by GUI presentation code."""

from pathlib import Path
from typing import Protocol

from trading_bot.gui.market_data_models import MarketDataPageState
from trading_bot.gui.models import ApplicationOverview, ResearchPageState
from trading_bot.gui.paper_models import PaperPageState


class ResearchReportLoader(Protocol):
    """Load one explicitly selected local report into bounded GUI state."""

    def load_research_report(self, artifact_path: Path) -> ResearchPageState:
        """Load one explicit path without exposing adapter details to Qt."""
        ...


class GuiApplicationService(ResearchReportLoader, Protocol):
    """Provide bounded application state without exposing framework objects."""

    def get_overview(self) -> ApplicationOverview:
        """Return the current read-only application overview."""
        ...

    def get_research_state(self) -> ResearchPageState:
        """Return bounded read-only historical research presentation state."""
        ...

    def get_paper_state(self) -> PaperPageState:
        """Return bounded read-only paper-operation presentation state."""
        ...

    def get_market_data_state(self) -> MarketDataPageState:
        """Return bounded read-only verified market-data presentation state."""
        ...
