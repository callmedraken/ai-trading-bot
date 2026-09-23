"""Focused PD4-G4 fixed read-only decision-storage tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

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
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    SingleDeferredDecisionClassification as Deferred,
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


def _deferred(api, *, observer=None, observed_at=None):
    return storage._find_single_deferred_unattended_decision_for_test(
        SID,
        observed_at or datetime(2026, 8, 27, 12, tzinfo=UTC),
        api=api,
        observer=observer or Observer(),
        calendar=_calendar(),
    )


def test_single_deferred_complete_namespace_zero_one_multiple_and_no_writes(
    monkeypatch,
):
    first = _decision_binding(monkeypatch, caller_key="first")
    second = _decision_binding(monkeypatch, caller_key="second")
    empty = _empty_api()
    assert _deferred(empty).classification is Deferred.NONE
    api = _empty_api()
    _put_final(api, first)
    result = _deferred(api)
    assert result.classification is Deferred.FINALIZED
    assert result.binding == first
    assert result.execution_session == first.decision.intended_execution_session
    assert result.execution_session < result.current_completed_session
    with pytest.raises(PersonalDesktopUnattendedDecisionStorageError):
        storage.require_single_deferred_unattended_decision(result, object())
    _put_final(api, second)
    assert _deferred(api).classification is Deferred.BLOCKED
    assert not any(
        call[0] in {"write", "create", "rename", "delete"} for call in api.calls
    )


@pytest.mark.parametrize(
    "bad", ["staging", "unknown", "malformed", "conflict", "missing"]
)
def test_single_deferred_rejects_invalid_complete_namespace(monkeypatch, bad):
    first = _decision_binding(monkeypatch, caller_key="first")
    second = _decision_binding(monkeypatch, caller_key="second")
    api = _empty_api() if bad != "missing" else MemoryReadApi()
    api.trading_runtime = True
    if bad == "staging":
        api.put(_directory(first, staging=True))
    elif bad == "unknown":
        api.overrides[security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS] = (
            "unknown",
        )
    elif bad == "malformed":
        directory = _put_final(api, first)
        api.put(
            directory
            + "\\"
            + storage.unattended_paper_decision_artifact_name(
                first.decision.decision_id
            ),
            b"not-canonical-json",
        )
    elif bad == "conflict":
        _put_final(api, second, directory_binding=first)
    assert _deferred(api).classification is Deferred.BLOCKED


@pytest.mark.parametrize(
    "observed_at",
    [
        datetime(2026, 8, 25, 12, tzinfo=UTC),
        datetime(2026, 8, 26, 12, tzinfo=UTC),
    ],
)
def test_single_deferred_rejects_current_or_future_candidate(monkeypatch, observed_at):
    binding = _decision_binding(monkeypatch)
    api = _empty_api()
    _put_final(api, binding)
    assert _deferred(api, observed_at=observed_at).classification is Deferred.BLOCKED


def test_single_deferred_requires_stable_genuine_trading_token(monkeypatch):
    from .test_personal_desktop_unattended_paper_invocation_storage import _token

    binding = _decision_binding(monkeypatch)
    api = _empty_api()
    _put_final(api, binding)
    assert (
        _deferred(api, observer=Observer(_token(elevated=True))).classification
        is Deferred.BLOCKED
    )
    assert (
        _deferred(
            api, observer=Observer(_token(), _token(groups=(("S-1-1-0", 0),)))
        ).classification
        is Deferred.BLOCKED
    )


def test_single_deferred_public_read_registers_only_current_c1(monkeypatch):
    binding = _decision_binding(monkeypatch)
    api = _empty_api()
    _put_final(api, binding)
    c1 = type("C1", (), {"approved_account_sid": SID})()
    monkeypatch.setattr(
        storage, "require_validated_production_authority", lambda value: value
    )
    monkeypatch.setattr(storage, "WindowsTradingTokenObserver", Observer)
    monkeypatch.setattr(storage, "WindowsPaperReadNativeApi", lambda: api)
    monkeypatch.setattr(
        storage, "personal_desktop_unattended_decision_calendar", _calendar
    )
    monkeypatch.setattr(
        storage,
        "completed_xnys_session_at",
        lambda observed: storage.TradingSession(
            binding.decision.intended_execution_session.session_date.replace(day=26)
        ),
    )
    result = storage.find_single_deferred_unattended_decision(c1)
    assert result.classification is Deferred.FINALIZED
    assert (
        storage.require_single_deferred_unattended_decision(result, c1)
        is result.binding
    )
    with pytest.raises(PersonalDesktopUnattendedDecisionStorageError):
        storage.require_single_deferred_unattended_decision(
            result, type("C1", (), {"approved_account_sid": SID})()
        )
    forged = replace(result)
    with pytest.raises(PersonalDesktopUnattendedDecisionStorageError):
        storage.require_single_deferred_unattended_decision(forged, c1)
