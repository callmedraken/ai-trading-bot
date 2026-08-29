"""Qt-native bounded bar visualization for research variant comparison."""

from dataclasses import dataclass
from decimal import Context, Decimal, localcontext

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from trading_bot.gui.models import (
    ResearchResultRow,
    format_decimal_for_display,
    format_percentage_for_display,
)


@dataclass(frozen=True, slots=True)
class RenderedComparisonBar:
    """Inspectable geometry for one truthful metric value."""

    metric: str
    caller_ordinal: int
    value: Decimal
    start_x: int
    end_x: int
    zero_x: int
    context: str


@dataclass(frozen=True, slots=True)
class _MetricDefinition:
    key: str
    title: str
    context: str
    percentage: bool = False
    bipolar: bool = False


_METRICS = (
    _MetricDefinition(
        "total_return",
        "Total return",
        "Negative left • zero centered • positive right",
        percentage=True,
        bipolar=True,
    ),
    _MetricDefinition(
        "maximum_drawdown_percentage",
        "Maximum drawdown",
        "Lower drawdown is better • larger bars mean more drawdown",
        percentage=True,
    ),
    _MetricDefinition(
        "aggregate_one_way_turnover",
        "One-way turnover",
        "Magnitude only • no preference inferred",
    ),
    _MetricDefinition(
        "total_fills",
        "Total fills",
        "Count only • no preference inferred",
    ),
)
_HEADER_LEFT = 8
_HEADER_GAP = 12


class ResearchComparisonChart(QWidget):
    """Render approved comparison metrics without deriving scores."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: tuple[ResearchResultRow, ...] = ()
        self.setObjectName("researchComparisonChart")
        self.setMinimumHeight(120)

    @property
    def rows(self) -> tuple[ResearchResultRow, ...]:
        """Return the immutable caller-ordered rows currently visualized."""
        return self._rows

    def set_rows(self, rows: tuple[ResearchResultRow, ...]) -> None:
        """Replace the visualization with zero or two-to-four rows."""
        values = tuple(sorted(rows, key=lambda item: item.caller_ordinal))
        if len(values) not in (0, 2, 3, 4):
            raise ValueError("comparison chart requires zero or two-to-four rows")
        if len({item.caller_ordinal for item in values}) != len(values):
            raise ValueError("comparison chart rows must have unique identities")
        self._rows = values
        height = 80 if not values else sum(34 + len(values) * 22 for _ in _METRICS)
        self.setMinimumHeight(height)
        self.update()

    def bar_layout(self, width: int) -> tuple[RenderedComparisonBar, ...]:
        """Return deterministic pixel spans used by the Qt paint path."""
        if type(width) is not int or width <= 0:
            raise ValueError("width must be a positive integer")
        if not self._rows:
            return ()
        plot_left = min(210, max(100, width // 3))
        plot_width = max(width - plot_left - 14, 40)
        bars: list[RenderedComparisonBar] = []
        for metric in _METRICS:
            values = tuple(_metric_value(row, metric.key) for row in self._rows)
            if metric.bipolar:
                zero_x = plot_left + plot_width // 2
                half_width = plot_width // 2
                scale = max((abs(value) for value in values), default=Decimal("0"))
                for row, value in zip(self._rows, values, strict=True):
                    length = _scaled_length(abs(value), scale, half_width)
                    start_x = zero_x - length if value < 0 else zero_x
                    end_x = zero_x + length if value > 0 else zero_x
                    if value < 0:
                        end_x = zero_x
                    bars.append(
                        RenderedComparisonBar(
                            metric=metric.key,
                            caller_ordinal=row.caller_ordinal,
                            value=value,
                            start_x=start_x,
                            end_x=end_x,
                            zero_x=zero_x,
                            context=metric.context,
                        )
                    )
            else:
                zero_x = plot_left
                scale = max(values, default=Decimal("0"))
                for row, value in zip(self._rows, values, strict=True):
                    length = _scaled_length(value, scale, plot_width)
                    bars.append(
                        RenderedComparisonBar(
                            metric=metric.key,
                            caller_ordinal=row.caller_ordinal,
                            value=value,
                            start_x=zero_x,
                            end_x=zero_x + length,
                            zero_x=zero_x,
                            context=metric.context,
                        )
                    )
        return tuple(bars)

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#111827"))
        if not self._rows:
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Select at least two variants to compare.",
            )
            return

        layouts = self.bar_layout(max(self.width(), 1))
        layout_lookup = {(item.metric, item.caller_ordinal): item for item in layouts}
        y = 8
        colors = ("#60a5fa", "#34d399", "#f59e0b", "#c084fc")
        for metric in _METRICS:
            title_x, context_x = _metric_header_positions(
                painter.fontMetrics(), metric.title
            )
            painter.setPen(QColor("#f8fafc"))
            painter.drawText(title_x, y + 12, metric.title)
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(context_x, y + 12, metric.context)
            y += 22
            for color_index, row in enumerate(self._rows):
                item = layout_lookup[(metric.key, row.caller_ordinal)]
                painter.setPen(QColor("#cbd5e1"))
                painter.drawText(8, y + 13, _bounded_label(row.variant_label))
                painter.setPen(QColor("#475569"))
                painter.drawLine(item.zero_x, y, item.zero_x, y + 16)
                left = min(item.start_x, item.end_x)
                bar_width = abs(item.end_x - item.start_x)
                if bar_width:
                    painter.fillRect(
                        QRectF(left, y + 2, bar_width, 12),
                        QColor(colors[color_index]),
                    )
                painter.setPen(QColor("#e5e7eb"))
                painter.drawText(
                    min(max(item.end_x + 5, item.zero_x + 5), self.width() - 70),
                    y + 13,
                    _format_metric(item.value, metric),
                )
                y += 22
            y += 12


def _metric_value(row: ResearchResultRow, key: str) -> Decimal:
    if key == "total_fills":
        return Decimal(row.total_fills)
    value = getattr(row, key)
    if type(value) is not Decimal:
        raise TypeError("comparison chart metric must be a Decimal")
    return value


def _metric_header_positions(font_metrics: QFontMetrics, title: str) -> tuple[int, int]:
    """Return non-overlapping title and context x-positions."""
    title_x = _HEADER_LEFT
    context_x = title_x + font_metrics.horizontalAdvance(title) + _HEADER_GAP
    return title_x, context_x


def _scaled_length(value: Decimal, scale: Decimal, width: int) -> int:
    if value == 0 or scale == 0:
        return 0
    digits = max(len(value.as_tuple().digits), len(scale.as_tuple().digits), 28)
    with localcontext(Context(prec=digits + 10)):
        return int((value / scale) * Decimal(width))


def _bounded_label(value: str) -> str:
    return value if len(value) <= 18 else value[:17] + "…"


def _format_metric(value: Decimal, metric: _MetricDefinition) -> str:
    if metric.percentage:
        return format_percentage_for_display(value)
    return format_decimal_for_display(value)
