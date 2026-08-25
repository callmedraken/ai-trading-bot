"""Public, Qt-free presentation contracts for the desktop GUI."""

from trading_bot.gui.models import (
    ApplicationOverview,
    ComponentStatus,
    OperatingMode,
    PresentationStatus,
    ResearchComparisonState,
    ResearchPageState,
    ResearchReportStatus,
    ResearchReportView,
    ResearchResultRow,
)
from trading_bot.gui.research_service import CompactReportResearchService
from trading_bot.gui.services import GuiApplicationService

__all__ = [
    "ApplicationOverview",
    "ComponentStatus",
    "CompactReportResearchService",
    "GuiApplicationService",
    "OperatingMode",
    "PresentationStatus",
    "ResearchComparisonState",
    "ResearchPageState",
    "ResearchReportStatus",
    "ResearchReportView",
    "ResearchResultRow",
]
