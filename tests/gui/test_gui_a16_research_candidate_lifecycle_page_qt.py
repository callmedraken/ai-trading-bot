"""Real PySide6, bounded selectable evidence and exact local verification scope."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QScrollArea
from tests.gui.test_gui_a16_research_candidate_lifecycle_models import available_state

from trading_bot.gui.research_candidate_lifecycle_models import (
    LOCAL_VERIFICATION_SCOPE,
    RANK_NOTICE,
    unavailable_research_candidate_lifecycle_state,
)
from trading_bot.gui.research_candidate_lifecycle_models import (
    ResearchCandidateLifecycleDiagnostic as Diagnostic,
)
from trading_bot.gui.research_candidate_lifecycle_models import (
    ResearchCandidateLifecyclePageState as State,
)
from trading_bot.gui.research_candidate_lifecycle_models import (
    ResearchCandidateLifecyclePageStatus as Status,
)
from trading_bot.gui.research_candidate_lifecycle_page import (
    ResearchCandidateLifecyclePage,
)


@pytest.mark.parametrize("status", list(Status))
@pytest.mark.parametrize("size", [(1180, 760), (920, 620)])
def test_real_qt_all_states_resolutions_selectable_no_overflow_or_actions(
    tmp_path, status, size
):
    application = QApplication.instance() or QApplication([])
    state = {
        Status.UNAVAILABLE: unavailable_research_candidate_lifecycle_state(),
        Status.ATTENTION: State(Status.ATTENTION, Diagnostic.INVALID),
        Status.AVAILABLE: available_state(tmp_path),
    }[status]
    page = ResearchCandidateLifecyclePage(state)
    # Reserve the actual MainWindow navigation width for the isolated page.
    page.resize(size[0] - 210, size[1])
    page.show()
    application.processEvents()
    labels = page.findChildren(QLabel)
    text = "\n".join(label.text() for label in labels)
    assert status.value in text
    assert not page.findChildren(QPushButton)
    for label in labels:
        assert label.textFormat() is Qt.TextFormat.PlainText
        assert (
            label.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse
        )
    for fixed in (
        "Real observation acquisition: Not connected",
        "Automatic promotion: Disabled",
        "Promotion authority: Not connected",
        "Production compatibility: Not established",
        "PAPER_CANDIDATE: Not materialized",
        "AWAITING_HUMAN_PROMOTION: Not materialized",
        "Trading authority: None",
    ):
        assert fixed in text
    assert "no source acceptance, promotion eligibility" in text
    assert "production readiness or trading readiness" in text
    if status is Status.AVAILABLE:
        e = state.evidence
        assert LOCAL_VERIFICATION_SCOPE in text and RANK_NOTICE in text
        assert "Stage: SHADOW" in text
        assert str(e.shadow_candidate_id) in text
        assert e.candidate_source.head in text and e.binding_source.tree in text
        assert "123456+00:00" in text
        assert "minimum_session_count: 2" in text
        assert "minimum_total_observation_count: 4" in text
        assert "minimum_observations_per_session: 2" in text
        assert "observation_count: 5" in text and "distinct_session_count: 2" in text
        assert "minimum_observations_in_any_session: 2" in text
        assert "status: PASSED" in text and "ordered empty reasons" in text
        for counter in (
            "CREDENTIAL_READS",
            "PROVIDER_CALLS",
            "ROBINHOOD_READS",
            "BROKER_CALLS",
            "PAPER_MUTATIONS",
            "SCHEDULER_CALLS",
            "ACL_MUTATIONS",
            "PRODUCTION_SQLITE_READS",
            "PRODUCTION_SQLITE_WRITES",
        ):
            assert f"{counter}: 0" in text
        assert "Original rank: 2" in text
    else:
        assert "Stage: SHADOW" not in text and LOCAL_VERIFICATION_SCOPE not in text
    scroll = page.findChild(QScrollArea, "researchLifecycleScroll")
    assert scroll.horizontalScrollBar().maximum() == 0
    assert scroll.widget().width() <= scroll.viewport().width()
    if status is Status.AVAILABLE:
        assert scroll.verticalScrollBar().maximum() > 0
    page.close()


def test_page_requires_exact_presentation_state():
    application = QApplication.instance() or QApplication([])
    assert application is not None
    with pytest.raises(TypeError):
        ResearchCandidateLifecyclePage(None)
