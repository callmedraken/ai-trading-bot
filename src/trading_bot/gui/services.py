"""Plain-Python service boundary consumed by GUI presentation code."""

from typing import Protocol

from trading_bot.gui.models import ApplicationOverview


class GuiApplicationService(Protocol):
    """Provide bounded application state without exposing framework objects."""

    def get_overview(self) -> ApplicationOverview:
        """Return the current read-only application overview."""
        ...
