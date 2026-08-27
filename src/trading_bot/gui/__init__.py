"""Public, Qt-free presentation contracts for the desktop GUI."""

from trading_bot.gui.market_data_models import (
    MAX_MARKET_DATA_MESSAGE_CHARACTERS,
    MAX_MARKET_DATA_PRESENTATION_TEXT_CHARACTERS,
    MAX_MARKET_DATA_SYMBOL_CHARACTERS,
    MAX_MARKET_DATA_SYMBOLS,
    MarketDataPageState,
    MarketDataPageStatus,
    VerifiedMarketSnapshotView,
    unavailable_market_data_state,
)
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
    format_decimal_for_display,
    format_percentage_for_display,
)
from trading_bot.gui.paper_inspection_service import PaperOperationInspectionService
from trading_bot.gui.paper_models import (
    MAX_PAPER_RECEIPT_PATH_CHARACTERS,
    PaperInspectionClassification,
    PaperInspectionDiagnostic,
    PaperOperationInspectionView,
    PaperPageState,
    PaperPageStatus,
    unavailable_paper_state,
)
from trading_bot.gui.research_service import CompactReportResearchService
from trading_bot.gui.services import GuiApplicationService, ResearchReportLoader

__all__ = [
    "ApplicationOverview",
    "ComponentStatus",
    "CompactReportResearchService",
    "GuiApplicationService",
    "MAX_MARKET_DATA_MESSAGE_CHARACTERS",
    "MAX_MARKET_DATA_PRESENTATION_TEXT_CHARACTERS",
    "MAX_MARKET_DATA_SYMBOL_CHARACTERS",
    "MAX_MARKET_DATA_SYMBOLS",
    "MAX_PAPER_RECEIPT_PATH_CHARACTERS",
    "MarketDataPageState",
    "MarketDataPageStatus",
    "OperatingMode",
    "PaperInspectionClassification",
    "PaperInspectionDiagnostic",
    "PaperOperationInspectionView",
    "PaperOperationInspectionService",
    "PaperPageState",
    "PaperPageStatus",
    "PresentationStatus",
    "ResearchComparisonState",
    "ResearchPageState",
    "ResearchReportStatus",
    "ResearchReportView",
    "ResearchResultRow",
    "ResearchReportLoader",
    "VerifiedMarketSnapshotView",
    "format_decimal_for_display",
    "format_percentage_for_display",
    "unavailable_market_data_state",
    "unavailable_paper_state",
]
