"""Focused compatibility coverage for the unattended decision namespace."""

from trading_bot.runtime import personal_desktop_paper_account_read_authority as reader
from trading_bot.runtime import personal_desktop_paper_account_security as security

from .test_personal_desktop_paper_account_read_authority import memory_case, read_case


def test_unattended_decision_container_is_pinned_and_excluded_from_transitions(
    monkeypatch,
) -> None:
    case = memory_case(1, no_action=True)
    decisions = security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS
    case.api.put(decisions)
    case.api.overrides[decisions] = (
        ".unattended-paper-decision-conflict.staging",
        "unattended-paper-decision-malformed",
    )
    case.api.calls.clear()

    transition_names: list[str] = []
    original_read_transition = reader._read_transition

    def observe_transition(session, name):
        transition_names.append(name)
        return original_read_transition(session, name)

    monkeypatch.setattr(reader, "_read_transition", observe_transition)

    result = read_case(case)

    assert result.lineage == case.full.evidence
    assert transition_names == [
        directory.rsplit("\\", 1)[-1] for directory in case.directories
    ]
    assert case.api.inspections[decisions] == 3
    assert not any(
        call[0] == "names" and call[1] == decisions for call in case.api.calls
    )
    assert not case.api.handles
