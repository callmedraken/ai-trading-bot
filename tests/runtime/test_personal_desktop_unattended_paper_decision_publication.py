"""Focused PD4-G4 pre-open permit and effects-closed qualification tests."""

from __future__ import annotations

import copy
import pickle
from datetime import timedelta
from types import SimpleNamespace

import pytest

from trading_bot.runtime import (
    personal_desktop_paper_account_security as security,
)
from trading_bot.runtime import (
    personal_desktop_paper_receipt_recovery_execution as recovery_execution,
)
from trading_bot.runtime import (
    personal_desktop_supervised_paper_operation_execution as supervised_execution,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_decision_publication as publication,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_operation_execution as unattended_execution,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_storage_provisioning as storage_provisioning,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle_timing import (
    xnys_regular_open,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_publication import (
    PERSONAL_DESKTOP_UNATTENDED_DECISION_PUBLICATION_EFFECTS_ENABLED,
    PersonalDesktopUnattendedDecisionPublicationError,
    PersonalDesktopUnattendedDecisionPublicationStatus,
    PreOpenDecisionPublicationPermit,
    consume_disposable_pre_open_decision_publication_permit_for_test,
    issue_disposable_pre_open_decision_publication_permit_for_test,
    issue_pre_open_decision_publication_permit,
    qualify_personal_desktop_unattended_decision_publication,
    require_pre_open_decision_publication_permit,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    PersonalDesktopUnattendedDecisionStorageClassification,
    PersonalDesktopUnattendedDecisionStorageDiagnostic,
    PersonalDesktopUnattendedDecisionStorageReadResult,
)

from .test_personal_desktop_unattended_paper_decision_intent import _decision_binding


def _absent(binding):
    return PersonalDesktopUnattendedDecisionStorageReadResult(
        PersonalDesktopUnattendedDecisionStorageClassification.ABSENT,
        binding.decision.decision_id,
        0,
        None,
        PersonalDesktopUnattendedDecisionStorageDiagnostic.VERIFIED_ABSENT,
    )


def _permit(monkeypatch: pytest.MonkeyPatch):
    binding = _decision_binding(monkeypatch)
    storage = _absent(binding)
    deadline = xnys_regular_open(binding.decision.intended_execution_session)
    permit = issue_disposable_pre_open_decision_publication_permit_for_test(
        binding,
        storage,
        binding.decision.intended_execution_session,
        deadline - timedelta(microseconds=1),
    )
    return binding, storage, permit, deadline


def test_strictly_before_open_can_qualify(monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, permit, _ = _permit(monkeypatch)
    assert type(permit) is PreOpenDecisionPublicationPermit


@pytest.mark.parametrize("offset", [timedelta(0), timedelta(microseconds=1)])
def test_at_or_after_open_fails(
    monkeypatch: pytest.MonkeyPatch, offset: timedelta
) -> None:
    binding = _decision_binding(monkeypatch)
    storage = _absent(binding)
    deadline = xnys_regular_open(binding.decision.intended_execution_session)
    with pytest.raises(PersonalDesktopUnattendedDecisionPublicationError):
        issue_disposable_pre_open_decision_publication_permit_for_test(
            binding,
            storage,
            binding.decision.intended_execution_session,
            deadline + offset,
        )


def test_naive_timestamp_and_wrong_execution_session_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _decision_binding(monkeypatch)
    storage = _absent(binding)
    deadline = xnys_regular_open(binding.decision.intended_execution_session)
    with pytest.raises(PersonalDesktopUnattendedDecisionPublicationError):
        issue_disposable_pre_open_decision_publication_permit_for_test(
            binding,
            storage,
            binding.decision.intended_execution_session,
            deadline.replace(tzinfo=None),
        )
    with pytest.raises(PersonalDesktopUnattendedDecisionPublicationError):
        issue_disposable_pre_open_decision_publication_permit_for_test(
            binding,
            storage,
            binding.decision.selected_session,
            deadline - timedelta(minutes=1),
        )


def test_permit_cannot_be_copied_deepcopied_pickled_or_constructed() -> None:
    with pytest.raises(TypeError):
        PreOpenDecisionPublicationPermit()
    permit = object.__new__(PreOpenDecisionPublicationPermit)
    for operation in (copy.copy, copy.deepcopy, pickle.dumps):
        with pytest.raises(TypeError):
            operation(permit)


def test_durable_decision_bytes_cannot_mint_a_permit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _decision_binding(monkeypatch)
    storage = _absent(binding)
    forged = object.__new__(PreOpenDecisionPublicationPermit)
    deadline = xnys_regular_open(binding.decision.intended_execution_session)
    assert binding.artifact_bytes
    with pytest.raises(PersonalDesktopUnattendedDecisionPublicationError):
        consume_disposable_pre_open_decision_publication_permit_for_test(
            forged, binding, storage, deadline - timedelta(microseconds=1)
        )


def test_permit_is_consumable_exactly_once(monkeypatch: pytest.MonkeyPatch) -> None:
    binding, storage, permit, deadline = _permit(monkeypatch)
    consume_disposable_pre_open_decision_publication_permit_for_test(
        permit, binding, storage, deadline - timedelta(microseconds=1)
    )
    with pytest.raises(PersonalDesktopUnattendedDecisionPublicationError):
        consume_disposable_pre_open_decision_publication_permit_for_test(
            permit, binding, storage, deadline - timedelta(microseconds=1)
        )


def test_wrong_decision_or_storage_provenance_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding, storage, permit, deadline = _permit(monkeypatch)
    different = _decision_binding(monkeypatch, caller_key="other")
    with pytest.raises(PersonalDesktopUnattendedDecisionPublicationError):
        consume_disposable_pre_open_decision_publication_permit_for_test(
            permit,
            different,
            storage,
            deadline - timedelta(microseconds=1),
        )
    with pytest.raises(PersonalDesktopUnattendedDecisionPublicationError):
        consume_disposable_pre_open_decision_publication_permit_for_test(
            permit,
            binding,
            _absent(binding),
            deadline - timedelta(microseconds=1),
        )


def test_public_issuer_reconciles_exact_c1_and_storage_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _decision_binding(monkeypatch)
    storage = _absent(binding)
    authority = SimpleNamespace(
        machine_authority_id="machine",
        approved_account_sid="S-1-5-21-1-2-3-1009",
        authority_epoch_id="epoch",
    )
    verified_storage = SimpleNamespace(
        authority=authority,
        expected=binding,
        classification=PersonalDesktopUnattendedDecisionStorageClassification.ABSENT,
    )
    monkeypatch.setattr(
        publication, "require_validated_production_authority", lambda value: value
    )
    monkeypatch.setattr(
        publication,
        "require_validated_personal_desktop_unattended_decision_storage_read",
        lambda value: verified_storage,
    )
    deadline = xnys_regular_open(binding.decision.intended_execution_session)
    permit = issue_pre_open_decision_publication_permit(
        binding,
        storage,
        authority,  # type: ignore[arg-type]
        binding.decision.intended_execution_session,
        deadline - timedelta(seconds=1),
    )
    assert type(permit) is PreOpenDecisionPublicationPermit
    wrong_authority = SimpleNamespace(
        machine_authority_id="wrong-machine",
        approved_account_sid=authority.approved_account_sid,
        authority_epoch_id=authority.authority_epoch_id,
    )
    with pytest.raises(PersonalDesktopUnattendedDecisionPublicationError):
        require_pre_open_decision_publication_permit(
            permit,
            binding,
            storage,
            wrong_authority,  # type: ignore[arg-type]
        )


def test_committed_gate_is_false() -> None:
    assert PERSONAL_DESKTOP_UNATTENDED_DECISION_PUBLICATION_EFFECTS_ENABLED is False
    assert security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is False
    assert security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED is False
    assert (
        supervised_execution.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED
        is False
    )
    assert (
        recovery_execution.PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED
        is False
    )
    assert (
        unattended_execution.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED
        is False
    )
    assert (
        storage_provisioning.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED
        is False
    )


def test_gate_false_qualification_is_read_only_and_never_opens_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _decision_binding(monkeypatch)
    storage = _absent(binding)
    calls = []
    monkeypatch.setattr(
        publication,
        "read_personal_desktop_unattended_decision_storage",
        lambda authority, expected: calls.append((authority, expected)) or storage,
    )
    deadline = xnys_regular_open(binding.decision.intended_execution_session)
    result = qualify_personal_desktop_unattended_decision_publication(
        object(),
        binding,
        deadline - timedelta(minutes=1),  # type: ignore[arg-type]
    )
    assert result.status is (
        PersonalDesktopUnattendedDecisionPublicationStatus.DECISION_READY_EFFECTS_DISABLED
    )
    assert result.output_capability_opened is False
    assert result.filesystem_mutation_performed is False
    assert len(calls) == 1
    assert calls[0][1] == binding


def test_gate_false_late_qualification_is_missed_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _decision_binding(monkeypatch)
    storage = _absent(binding)
    monkeypatch.setattr(
        publication,
        "read_personal_desktop_unattended_decision_storage",
        lambda authority, expected: storage,
    )
    deadline = xnys_regular_open(binding.decision.intended_execution_session)
    result = qualify_personal_desktop_unattended_decision_publication(
        object(),
        binding,
        deadline,  # type: ignore[arg-type]
    )
    assert result.status is (
        PersonalDesktopUnattendedDecisionPublicationStatus.MISSED_DECISION_DEADLINE
    )
    assert result.filesystem_mutation_performed is False
