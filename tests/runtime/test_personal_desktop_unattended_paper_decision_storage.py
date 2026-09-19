"""Focused PD4-G4 fixed read-only decision-storage tests."""

from __future__ import annotations

from dataclasses import replace

import pytest
from tests.runtime.test_personal_desktop_paper_account_security import (
    SID,
    MemoryReadApi,
)
from tests.runtime.test_personal_desktop_unattended_paper_invocation_storage import (
    Observer,
)

from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime import (
    personal_desktop_unattended_paper_decision_storage as storage,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    FinalizedUnattendedDecisionForSessionClassification,
    PersonalDesktopUnattendedDecisionStorageClassification,
    PersonalDesktopUnattendedDecisionStorageError,
)

from .test_personal_desktop_unattended_paper_decision_intent import (
    _calendar,
    _decision_binding,
    _session_read,
)


def _directory(binding, *, staging: bool = False):
    return (
        security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS
        + "\\"
        + storage.unattended_paper_decision_directory_name(
            binding.decision.decision_id, staging=staging
        )
    )


def _put_final(api, binding, *, directory_binding=None):
    directory_binding = directory_binding or binding
    directory = _directory(directory_binding)
    api.put(directory)
    api.put(
        directory
        + "\\"
        + storage.unattended_paper_decision_artifact_name(
            directory_binding.decision.decision_id
        ),
        binding.artifact_bytes,
    )
    return directory


def _read(api, binding):
    return storage._read_personal_desktop_unattended_decision_storage_for_test(
        binding,
        SID,
        api=api,
        observer=Observer(),
        calendar=_calendar(),
    )


def _find(api, binding):
    return storage._find_finalized_unattended_decision_for_execution_session_for_test(
        binding.decision.intended_execution_session,
        SID,
        api=api,
        observer=Observer(),
        calendar=_calendar(),
    )


def _empty_api():
    api = MemoryReadApi()
    api.trading_runtime = True
    api.put(security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS)
    return api


def test_fixed_namespace_and_names_are_exact(monkeypatch: pytest.MonkeyPatch) -> None:
    binding = _decision_binding(monkeypatch)
    identity = binding.decision.decision_id
    assert security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS == (
        r"F:\AITradingBot\Paper-v2\runtime\unattended-decisions"
    )
    assert storage.unattended_paper_decision_directory_name(identity) == (
        f"unattended-paper-decision-{identity}"
    )
    assert (
        storage.unattended_paper_decision_directory_name(identity, staging=True)
        == f".unattended-paper-decision-{identity}.staging"
    )
    assert storage.unattended_paper_decision_artifact_name(identity) == (
        f"personal-desktop-unattended-paper-decision-intent-{identity}.json"
    )


def test_safe_empty_namespace_is_absent_and_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _decision_binding(monkeypatch)
    api = _empty_api()
    result = _read(api, binding)
    assert (
        result.classification
        is PersonalDesktopUnattendedDecisionStorageClassification.ABSENT
    )
    assert not any(
        call[0] in {"write", "create", "rename", "delete"} for call in api.calls
    )


def test_staging_presence_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    binding = _decision_binding(monkeypatch)
    api = _empty_api()
    api.put(_directory(binding, staging=True))
    assert _read(api, binding).classification is (
        PersonalDesktopUnattendedDecisionStorageClassification.STAGING_PRESENT
    )


def test_identical_final_bytes_converge_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _decision_binding(monkeypatch)
    api = _empty_api()
    _put_final(api, binding)
    result = _read(api, binding)
    assert result.classification is (
        PersonalDesktopUnattendedDecisionStorageClassification.FINALIZED_IDENTICAL
    )
    assert result.matching_decision_id == binding.decision.decision_id


def test_conflicting_valid_final_bytes_are_classified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = _decision_binding(monkeypatch, caller_key="expected")
    different = _decision_binding(monkeypatch, caller_key="different")
    api = _empty_api()
    _put_final(api, different, directory_binding=expected)
    assert _read(api, expected).classification is (
        PersonalDesktopUnattendedDecisionStorageClassification.CONFLICTING
    )


def test_unknown_entry_or_missing_namespace_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _decision_binding(monkeypatch)
    missing = MemoryReadApi()
    missing.trading_runtime = True
    assert _read(missing, binding).classification is (
        PersonalDesktopUnattendedDecisionStorageClassification.BLOCKED
    )
    unknown = _empty_api()
    unknown.overrides[security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS] = (
        "unexpected",
    )
    assert _read(unknown, binding).classification is (
        PersonalDesktopUnattendedDecisionStorageClassification.BLOCKED
    )


def test_wrong_parent_owner_or_reparse_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _decision_binding(monkeypatch)
    for change in (
        {"owner_sid": SID},
        {"is_reparse_point": True},
    ):
        api = _empty_api()
        path = security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS
        node = api.nodes[path]
        node.observation = replace(
            node.observation,
            security=replace(node.observation.security, **change),
        )
        assert _read(api, binding).classification is (
            PersonalDesktopUnattendedDecisionStorageClassification.BLOCKED
        )


def test_parent_identity_drift_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    binding = _decision_binding(monkeypatch)
    api = _empty_api()
    path = security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS
    calls = 0

    def drift(observed_path, count, node):
        nonlocal calls
        if observed_path == path:
            calls += 1
            if count == 2:
                node.observation = replace(node.observation, identity=(9, 999))

    api.on_inspect = drift
    assert _read(api, binding).classification is (
        PersonalDesktopUnattendedDecisionStorageClassification.BLOCKED
    )


def test_disposable_read_never_mints_production_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _decision_binding(monkeypatch)
    result = _read(_empty_api(), binding)
    with pytest.raises(PersonalDesktopUnattendedDecisionStorageError):
        storage.require_validated_personal_desktop_unattended_decision_storage_read(
            result
        )


def test_session_indexed_discovery_reads_the_complete_fixed_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _decision_binding(monkeypatch)
    empty = _find(_empty_api(), binding)
    assert (
        empty.classification is FinalizedUnattendedDecisionForSessionClassification.NONE
    )

    api = _empty_api()
    _put_final(api, binding)
    found = _find(api, binding)
    assert found.classification is (
        FinalizedUnattendedDecisionForSessionClassification.FINALIZED
    )
    assert found.binding == binding
    assert found.decision_id == binding.decision.decision_id
    assert not any(
        call[0] in {"write", "create", "rename", "delete"} for call in api.calls
    )


def test_session_indexed_discovery_blocks_duplicate_target_or_staging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _decision_binding(monkeypatch, caller_key="first")
    second = _decision_binding(monkeypatch, caller_key="second")
    api = _empty_api()
    _put_final(api, first)
    _put_final(api, second)
    assert _find(api, first).classification is (
        FinalizedUnattendedDecisionForSessionClassification.BLOCKED
    )

    staging = _empty_api()
    staging.put(_directory(first, staging=True))
    assert _find(staging, first).classification is (
        FinalizedUnattendedDecisionForSessionClassification.BLOCKED
    )


def test_session_indexed_discovery_blocks_malformed_or_unknown_namespace_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _decision_binding(monkeypatch)
    malformed = _empty_api()
    directory = _put_final(malformed, binding)
    artifact = (
        directory
        + "\\"
        + storage.unattended_paper_decision_artifact_name(binding.decision.decision_id)
    )
    malformed.put(artifact, b"not-canonical-json")
    assert _find(malformed, binding).classification is (
        FinalizedUnattendedDecisionForSessionClassification.BLOCKED
    )

    unknown = _empty_api()
    unknown.overrides[security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS] = (
        "unknown",
    )
    assert _find(unknown, binding).classification is (
        FinalizedUnattendedDecisionForSessionClassification.BLOCKED
    )


def test_disposable_session_discovery_cannot_be_reused_as_current_c1_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _decision_binding(monkeypatch)
    result = _find(_empty_api(), binding)
    with pytest.raises(PersonalDesktopUnattendedDecisionStorageError):
        storage.require_finalized_unattended_decision_for_execution_session(
            result,
            object(),  # type: ignore[arg-type]
        )


def test_session_discovery_rejects_c3_evidence_from_wrong_current_c1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _decision_binding(monkeypatch)
    monkeypatch.setattr(
        storage,
        "WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority",
        lambda authority: type(
            "WrongC1Reader",
            (),
            {
                "read_selected_snapshot_for_session": staticmethod(
                    lambda session: _session_read(session.session_date, 999)
                )
            },
        )(),
    )
    with pytest.raises(PersonalDesktopUnattendedDecisionStorageError):
        storage._require_decision_c3_matches_current_authority(
            binding,
            object(),  # type: ignore[arg-type]
        )
