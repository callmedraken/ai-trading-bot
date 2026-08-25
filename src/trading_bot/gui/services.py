"""Plain-Python service boundary consumed by GUI presentation code."""

from typing import Protocol

from trading_bot.gui.models import ApplicationOverview, ResearchPageState


class GuiApplicationService(Protocol):
    """Provide bounded application state without exposing framework objects."""

    def get_overview(self) -> ApplicationOverview:
        """Return the current read-only application overview."""
        ...

    def get_research_state(self) -> ResearchPageState:
        """Return bounded read-only historical research presentation state."""
        ...
