"""Cached, descriptive research comparison presentation."""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from trading_bot.live_prototype.contracts import (
    CandidateView,
    PrototypeSnapshot,
)

_MAX_CANDIDATE_CARDS = 12
_MAX_LIST_ITEMS = 20
_MAX_TEXT_CHARS = 1200


class ResearchPage(QWidget):
    """Display cached research outcomes without choosing an active strategy."""

    def __init__(
        self, snapshot: PrototypeSnapshot, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("prototypeResearchPage")
        self._snapshot = _require_snapshot(snapshot)
        self._values: dict[str, QLabel] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setObjectName("prototypeResearchScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget(scroll)
        content.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = _label("Research Comparison", content)
        title.setObjectName("researchTitle")
        layout.addWidget(title)
        scope = _label(
            "Compare research results and their evidence. Opening a report "
            "does not change the active strategy.",
            content,
        )
        scope.setObjectName("researchScope")
        layout.addWidget(scope)

        summary = QGridLayout()
        summary.setHorizontalSpacing(12)
        summary.setVerticalSpacing(12)
        summary.setColumnStretch(0, 1)
        summary.setColumnStretch(1, 1)
        self._add_summary_card(
            summary,
            content,
            "Research result",
            "researchSummaryCard",
            0,
            0,
            (
                ("selected", "Research selection"),
                ("policy", "Qualification policy"),
                ("bundle_digest", "Report / bundle digest"),
                ("dataset_digest", "Dataset identity"),
                ("prior_trials", "Prior configurations"),
                ("new_trials", "New configurations"),
                ("live_eligible", "Research live eligibility"),
            ),
        )
        self._add_summary_card(
            summary,
            content,
            "Active binding (separate)",
            "researchActiveBindingCard",
            0,
            1,
            (
                ("active_strategy", "Active strategy"),
                ("active_binding_digest", "Active binding digest"),
                ("active_source_head", "Executable source HEAD"),
            ),
        )
        layout.addLayout(summary)

        assumptions_card = QFrame(content)
        assumptions_card.setObjectName("researchAssumptionsCard")
        assumptions_card.setFrameShape(QFrame.Shape.StyledPanel)
        assumptions_layout = QVBoxLayout(assumptions_card)
        assumptions_layout.setContentsMargins(12, 10, 12, 10)
        assumptions_layout.setSpacing(7)
        assumptions_heading = _label("Assumptions", assumptions_card)
        assumptions_heading.setObjectName("researchAssumptionsTitle")
        assumptions_layout.addWidget(assumptions_heading)
        assumptions = _label("", assumptions_card)
        assumptions.setObjectName("research_assumptions")
        self._values["assumptions"] = assumptions
        assumptions_layout.addWidget(assumptions)
        layout.addWidget(assumptions_card)

        candidates_heading = _label("Candidate results", content)
        candidates_heading.setObjectName("researchCandidatesTitle")
        layout.addWidget(candidates_heading)
        self._candidate_host = QWidget(content)
        self._candidate_layout = QVBoxLayout(self._candidate_host)
        self._candidate_layout.setContentsMargins(0, 0, 0, 0)
        self._candidate_layout.setSpacing(10)
        layout.addWidget(self._candidate_host)
        layout.addStretch(1)
        scroll.setWidget(content)
        self.update_snapshot(snapshot)

    def update_snapshot(self, snapshot: PrototypeSnapshot) -> None:
        """Refresh the page from a new immutable cached snapshot."""
        self._snapshot = _require_snapshot(snapshot)
        values = _research_values(snapshot)
        for name, label in self._values.items():
            label.setText(values[name])
        self._render_candidates(snapshot.research.candidates)

    def _add_summary_card(
        self,
        layout: QGridLayout,
        parent: QWidget,
        title: str,
        object_name: str,
        row: int,
        column: int,
        fields: tuple[tuple[str, str], ...],
    ) -> None:
        card = QFrame(parent)
        card.setObjectName(object_name)
        card.setFrameShape(QFrame.Shape.StyledPanel)
        grid = QGridLayout(card)
        grid.setContentsMargins(12, 10, 12, 10)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(7)
        grid.setColumnMinimumWidth(0, 148)
        grid.setColumnStretch(1, 1)
        heading = _label(title, card)
        heading.setObjectName(f"{object_name}Title")
        grid.addWidget(heading, 0, 0, 1, 2)
        for index, (name, caption) in enumerate(fields, start=1):
            caption_label = _label(caption, card)
            caption_label.setObjectName(f"researchCaption_{name}")
            value_label = _label("", card)
            value_label.setObjectName(f"research_{name}")
            self._values[name] = value_label
            grid.addWidget(caption_label, index, 0)
            grid.addWidget(value_label, index, 1)
        layout.addWidget(card, row, column)

    def _render_candidates(self, candidates: tuple[CandidateView, ...] | None) -> None:
        _clear_layout(self._candidate_layout)
        if candidates is None:
            self._candidate_layout.addWidget(
                _label("Candidate results unavailable.", self._candidate_host)
            )
            return
        if not candidates:
            empty = _label("No candidate results recorded.", self._candidate_host)
            empty.setObjectName("researchNoCandidates")
            self._candidate_layout.addWidget(empty)
            return
        for index, candidate in enumerate(candidates[:_MAX_CANDIDATE_CARDS]):
            self._candidate_layout.addWidget(
                _candidate_card(candidate, index, self._candidate_host)
            )
        if len(candidates) > _MAX_CANDIDATE_CARDS:
            omitted = len(candidates) - _MAX_CANDIDATE_CARDS
            label = _label(
                f"{omitted} additional candidate(s) omitted from this bounded view.",
                self._candidate_host,
            )
            label.setObjectName("researchCandidatesOmitted")
            self._candidate_layout.addWidget(label)


def _candidate_card(candidate: CandidateView, index: int, parent: QWidget) -> QFrame:
    card = QFrame(parent)
    card.setObjectName(f"researchCandidate_{index}")
    card.setFrameShape(QFrame.Shape.StyledPanel)
    grid = QGridLayout(card)
    grid.setContentsMargins(12, 10, 12, 10)
    grid.setHorizontalSpacing(12)
    grid.setVerticalSpacing(7)
    grid.setColumnMinimumWidth(0, 148)
    grid.setColumnStretch(1, 1)

    heading = _label(_display(candidate.candidate), card)
    heading.setObjectName(f"researchCandidate_{index}_name")
    grid.addWidget(heading, 0, 0, 1, 2)
    rows = (
        ("base_return", "Median continuous base return", candidate.base_return),
        ("stress_return", "Median continuous stress return", candidate.stress_return),
        (
            "stress_drawdown",
            "Worst continuous stress drawdown",
            candidate.stress_drawdown,
        ),
        ("turnover", "Median annual stress turnover", candidate.turnover),
        ("qualified", "Qualified", candidate.qualified),
        ("reasons", "Failure reasons", _reasons(candidate.reasons)),
    )
    for row, (name, caption, value) in enumerate(rows, start=1):
        caption_label = _label(caption, card)
        caption_label.setObjectName(f"researchCandidateCaption_{index}_{name}")
        value_label = _label(_display(value), card)
        value_label.setObjectName(f"researchCandidate_{index}_{name}")
        grid.addWidget(caption_label, row, 0)
        grid.addWidget(value_label, row, 1)
    return card


def _research_values(snapshot: PrototypeSnapshot) -> dict[str, str]:
    research = snapshot.research
    return {
        "selected": _display(research.selected),
        "policy": _display(research.policy),
        "bundle_digest": _display(research.bundle_digest),
        "dataset_digest": _display(research.dataset_digest),
        "prior_trials": _display(research.prior_trials),
        "new_trials": _display(research.new_trials),
        "live_eligible": _display(research.live_eligible),
        "assumptions": _sequence(research.assumptions, empty="None recorded"),
        "active_strategy": _active_strategy(snapshot.strategy),
        "active_binding_digest": _display(snapshot.binding_digest),
        "active_source_head": _display(snapshot.source_head),
    }


def _active_strategy(value: object) -> str:
    if value is None or value == "UNSELECTED":
        return "Unavailable (UNSELECTED)"
    return _display(value)


def _reasons(values: tuple[str, ...] | None) -> str:
    return _sequence(values, empty="None reported", separator="; ")


def _sequence(
    values: tuple[object, ...] | None,
    *,
    empty: str,
    separator: str = "\n",
) -> str:
    if values is None:
        return "Unavailable"
    if not values:
        return empty
    shown = [_display(value) for value in values[:_MAX_LIST_ITEMS]]
    if len(values) > _MAX_LIST_ITEMS:
        shown.append(f"{len(values) - _MAX_LIST_ITEMS} additional item(s) omitted.")
    return separator.join(shown)


def _clear_layout(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


def _require_snapshot(snapshot: PrototypeSnapshot) -> PrototypeSnapshot:
    if type(snapshot) is not PrototypeSnapshot:
        raise TypeError("snapshot must be exactly PrototypeSnapshot")
    return snapshot


def _display(value: object) -> str:
    if value is None:
        return "Unavailable"
    if isinstance(value, Enum):
        value = value.value
    elif isinstance(value, bool):
        value = "Yes" if value else "No"
    text = str(value)
    if len(text) > _MAX_TEXT_CHARS:
        return f"{text[:_MAX_TEXT_CHARS]}… (truncated)"
    return text


def _label(text: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    label.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse
        | Qt.TextInteractionFlag.TextSelectableByKeyboard
    )
    label.setMinimumWidth(0)
    label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    return label
