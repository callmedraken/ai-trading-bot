"""Plain-Python service boundary consumed by GUI presentation code."""

from pathlib import Path
from typing import Protocol

from trading_bot.gui.models import ApplicationOverview, ResearchPageState


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
