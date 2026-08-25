"""Immutable presentation-only records for the desktop GUI."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class OperatingMode(Enum):
    """Operator-visible mode label; this enum grants no operating authority."""

    RESEARCH = "research"
    SIMULATED_PAPER = "simulated-paper"
    BROKER_PAPER = "broker-paper"
    LIVE = "live"


class PresentationStatus(Enum):
    """Bounded status vocabulary for read-only GUI presentation."""

    INFO = "info"
    HEALTHY = "healthy"
    UNAVAILABLE = "unavailable"
    BLOCKED = "blocked"


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


@dataclass(frozen=True, slots=True)
class ComponentStatus:
    """One bounded, presentation-only component status card."""

    key: str
    title: str
    status: PresentationStatus
    detail: str

    def __post_init__(self) -> None:
        _require_text(self.key, "key")
        _require_text(self.title, "title")
        _require_text(self.detail, "detail")
        if not isinstance(self.status, PresentationStatus):
            raise TypeError("status must be a PresentationStatus")


@dataclass(frozen=True, slots=True)
class ApplicationOverview:
    """Read-only application overview consumed by the GUI shell."""

    mode: OperatingMode
    environment: str
    summary: str
    components: tuple[ComponentStatus, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.mode, OperatingMode):
            raise TypeError("mode must be an OperatingMode")
        _require_text(self.environment, "environment")
        _require_text(self.summary, "summary")

        components = tuple(self.components)
        if not components:
            raise ValueError("components must not be empty")
        if not all(isinstance(item, ComponentStatus) for item in components):
            raise TypeError("components must contain ComponentStatus values")

        keys = tuple(item.key for item in components)
        if len(keys) != len(set(keys)):
            raise ValueError("component keys must be unique")

        object.__setattr__(self, "components", components)


MAX_RESEARCH_SOURCE_PATH_CHARACTERS = 512


class ResearchReportStatus(Enum):
    """Bounded availability state for the read-only Research page."""

    LOADED = "loaded"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ResearchResultRow:
    """One bounded compact-report row prepared for GUI presentation."""

    caller_ordinal: int
    rank: int | None
    variant_label: str
    parameter_label: str
    total_return: Decimal
    maximum_drawdown_percentage: Decimal
    turnover: Decimal
    trade_count: int
    exposure: Decimal | None
    return_over_drawdown: Decimal | None

    def __post_init__(self) -> None:
        if type(self.caller_ordinal) is not int or self.caller_ordinal < 0:
            raise ValueError("caller_ordinal must be a nonnegative integer")
        if self.rank is not None and (type(self.rank) is not int or self.rank <= 0):
            raise ValueError("rank must be a positive integer or None")
        _require_text(self.variant_label, "variant_label")
        _require_text(self.parameter_label, "parameter_label")
        for name in (
            "total_return",
            "maximum_drawdown_percentage",
            "turnover",
        ):
            value = getattr(self, name)
            if type(value) is not Decimal or not value.is_finite():
                raise TypeError(f"{name} must be a finite Decimal")
        if type(self.trade_count) is not int or self.trade_count < 0:
            raise ValueError("trade_count must be a nonnegative integer")
        for name in ("exposure", "return_over_drawdown"):
            value = getattr(self, name)
            if value is not None and (
                type(value) is not Decimal or not value.is_finite()
            ):
                raise TypeError(f"{name} must be a finite Decimal or None")


@dataclass(frozen=True, slots=True)
class ResearchReportView:
    """Immutable compact-report summary consumed by the Research widget."""

    report_id: str
    experiment_result_id: str
    variant_source: str
    ranking_summary: str
    metadata_summary: str
    rows: tuple[ResearchResultRow, ...]
    source_path: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "report_id",
            "experiment_result_id",
            "variant_source",
            "ranking_summary",
            "metadata_summary",
        ):
            _require_text(getattr(self, name), name)
        if self.source_path is not None:
            _require_text(self.source_path, "source_path")
            if len(self.source_path) > MAX_RESEARCH_SOURCE_PATH_CHARACTERS:
                raise ValueError("source_path exceeds the presentation bound")
        rows = tuple(self.rows)
        if not rows:
            raise ValueError("rows must not be empty")
        if not all(type(item) is ResearchResultRow for item in rows):
            raise TypeError("rows must contain ResearchResultRow values")
        if tuple(item.caller_ordinal for item in rows) != tuple(range(len(rows))):
            raise ValueError("row caller ordinals must be sequential")
        object.__setattr__(self, "rows", rows)

    @property
    def row_count(self) -> int:
        """Return the bounded number of displayed compact-report rows."""
        return len(self.rows)


@dataclass(frozen=True, slots=True)
class ResearchPageState:
    """Loaded or bounded-unavailable state for the Research page."""

    status: ResearchReportStatus
    message: str
    report: ResearchReportView | None

    def __post_init__(self) -> None:
        if type(self.status) is not ResearchReportStatus:
            raise TypeError("status must be a ResearchReportStatus")
        _require_text(self.message, "message")
        if self.status is ResearchReportStatus.LOADED:
            if type(self.report) is not ResearchReportView:
                raise ValueError("loaded research state requires a report")
        elif self.report is not None:
            raise ValueError("unavailable research state must not contain a report")
