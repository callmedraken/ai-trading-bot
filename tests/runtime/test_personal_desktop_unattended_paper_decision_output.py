"""Focused PD4-G4 hardened one-shot decision output tests."""

from __future__ import annotations

import copy
import pickle
from datetime import timedelta
from types import SimpleNamespace

import pytest
from tests.runtime.test_personal_desktop_unattended_paper_invocation_output import (
    FakeNative,
    _observation,
)

from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime import personal_desktop_paper_runtime_output as output
from trading_bot.runtime.personal_desktop_unattended_daily_cycle_timing import (
    next_xnys_execution_session,
    xnys_regular_open,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_publication import (
    PersonalDesktopUnattendedDecisionPublicationError,
    PreOpenDecisionPublicationPermit,
    consume_disposable_pre_open_decision_publication_permit_for_test,
    issue_disposable_pre_open_decision_publication_permit_for_test,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    PersonalDesktopUnattendedDecisionStorageClassification,
    PersonalDesktopUnattendedDecisionStorageDiagnostic,
    PersonalDesktopUnattendedDecisionStorageReadResult,
    unattended_paper_decision_directory_name,
)
from trading_bot.runtime.windows_authority import (
    AuthorityObjectError,
    AuthorityPathError,
)

from .test_personal_desktop_unattended_paper_decision_intent import _decision_binding

_OPEN_DECISION_OUTPUT_FOR_TEST = (
    output._open_personal_desktop_unattended_decision_output_capability_for_test
)


class DecisionNative(FakeNative):
    def __init__(self) -> None:
        super().__init__()
        path = security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS
        self.objects[path] = (_observation(path, (7, 3)), None)


def _storage(binding):
    return PersonalDesktopUnattendedDecisionStorageReadResult(
        PersonalDesktopUnattendedDecisionStorageClassification.ABSENT,
        binding.decision.decision_id,
        0,
        None,
        PersonalDesktopUnattendedDecisionStorageDiagnostic.VERIFIED_ABSENT,
    )


def _before_open(binding):
    return xnys_regular_open(binding.decision.intended_execution_session) - timedelta(
        microseconds=1
    )


def _assert_no_publication_mutation(api: DecisionNative) -> None:
    mutation_events = {
        "create-directory",
        "write-file",
        "rename-unattended-write-through",
    }
    assert not any(event[0] in mutation_events for event in api.events)


def _capability(monkeypatch: pytest.MonkeyPatch, api=None):
    binding = _decision_binding(monkeypatch)
    storage = _storage(binding)
    permit = issue_disposable_pre_open_decision_publication_permit_for_test(
        binding,
        storage,
        binding.decision.intended_execution_session,
        _before_open(binding),
    )
    return (
        binding,
        storage,
        permit,
        _OPEN_DECISION_OUTPUT_FOR_TEST(
            binding, storage, permit, api or DecisionNative()
        ),
    )


def test_disposable_output_publishes_exact_bytes_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = DecisionNative()
    binding, _, _, capability = _capability(monkeypatch, api)
    with capability as active:
        result = active.publish(_before_open(binding))
        with pytest.raises(output.PersonalDesktopPaperRuntimeOutputError):
            active.publish(_before_open(binding))
    assert result.decision_id == binding.decision.decision_id
    final = (
        security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS
        + "\\unattended-paper-decision-"
        + str(binding.decision.decision_id)
    )
    artifact = (
        final
        + "\\personal-desktop-unattended-paper-decision-intent-"
        + str(binding.decision.decision_id)
        + ".json"
    )
    assert api.objects[artifact][1] == binding.artifact_bytes
    assert not any(path.startswith("F:\\test") for path in api.objects)


@pytest.mark.parametrize("offset", [timedelta(0), timedelta(microseconds=1)])
def test_at_or_after_open_publication_fails_before_filesystem_mutation(
    monkeypatch: pytest.MonkeyPatch, offset: timedelta
) -> None:
    api = DecisionNative()
    binding, _, _, capability = _capability(monkeypatch, api)
    deadline = xnys_regular_open(binding.decision.intended_execution_session)
    with pytest.raises(PersonalDesktopUnattendedDecisionPublicationError):
        with capability as active:
            active.publish(deadline + offset)
    _assert_no_publication_mutation(api)
    assert capability.real_effect_performed is False


def test_naive_publication_observation_fails_before_filesystem_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = DecisionNative()
    binding, _, _, capability = _capability(monkeypatch, api)
    naive = _before_open(binding).replace(tzinfo=None)
    with pytest.raises(PersonalDesktopUnattendedDecisionPublicationError):
        with capability as active:
            active.publish(naive)
    _assert_no_publication_mutation(api)


def test_publication_uses_exact_bound_execution_session_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = DecisionNative()
    binding, _, _, capability = _capability(monkeypatch, api)
    wrong_session = next_xnys_execution_session(
        binding.decision.intended_execution_session
    )
    observation_before_wrong_deadline = xnys_regular_open(wrong_session) - timedelta(
        microseconds=1
    )
    with pytest.raises(PersonalDesktopUnattendedDecisionPublicationError):
        with capability as active:
            active.publish(observation_before_wrong_deadline)
    _assert_no_publication_mutation(api)


def test_publication_observation_does_not_change_identity_or_artifact_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _decision_binding(monkeypatch)
    deadline = xnys_regular_open(binding.decision.intended_execution_session)
    publications = []
    for offset in (timedelta(seconds=2), timedelta(seconds=1)):
        api = DecisionNative()
        storage = _storage(binding)
        permit = issue_disposable_pre_open_decision_publication_permit_for_test(
            binding,
            storage,
            binding.decision.intended_execution_session,
            deadline - timedelta(seconds=3),
        )
        capability = _OPEN_DECISION_OUTPUT_FOR_TEST(binding, storage, permit, api)
        with capability as active:
            result = active.publish(deadline - offset)
        artifact_payloads = tuple(
            payload
            for path, (_, payload) in api.objects.items()
            if path.endswith(".json")
        )
        publications.append((result, artifact_payloads))

    first, second = publications
    assert first[0].decision_id == second[0].decision_id == binding.decision.decision_id
    assert first[0].artifact_sha256 == second[0].artifact_sha256
    assert first[0].artifact_byte_length == second[0].artifact_byte_length
    assert first[1] == second[1] == (binding.artifact_bytes,)


def test_output_capability_cannot_be_copied_or_pickled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    *_, capability = _capability(monkeypatch)
    for operation in (copy.copy, copy.deepcopy, pickle.dumps):
        with pytest.raises(TypeError):
            operation(capability)


def test_parent_replacement_fails_before_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = DecisionNative()
    api.parent_drift_after_write = None
    binding, _, _, capability = _capability(monkeypatch, api)
    parent = security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS
    original_open = api.open
    opens = 0

    def replace_on_reopen(path, kind):
        nonlocal opens
        if path == parent:
            opens += 1
            if opens == 2:
                observation, payload = api.objects[parent]
                api.objects[parent] = (
                    security.PaperObjectObservation(
                        observation.security, (99, 99), 0, 1
                    ),
                    payload,
                )
        return original_open(path, kind)

    api.open = replace_on_reopen
    with pytest.raises(output.PersonalDesktopPaperRuntimeOutputError):
        with capability:
            pass
    assert not any(event[0] == "create-directory" for event in api.events)
    assert binding.artifact_bytes not in tuple(
        payload for _, payload in api.objects.values()
    )


def test_failed_finalization_spends_permit(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailRename(DecisionNative):
        def rename_unattended_write_through(self, staging: str, final: str) -> None:
            self.events.append(("rename-unattended-write-through", staging, final))
            raise AuthorityObjectError("simulated durable finalization failure")

    binding, storage, permit, capability = _capability(monkeypatch, FailRename())
    with pytest.raises(AuthorityObjectError):
        with capability as active:
            active.publish(_before_open(binding))
    with pytest.raises(PersonalDesktopUnattendedDecisionPublicationError):
        consume_disposable_pre_open_decision_publication_permit_for_test(
            permit, binding, storage, _before_open(binding)
        )


def test_failed_write_spends_permit(monkeypatch: pytest.MonkeyPatch) -> None:
    api = DecisionNative()
    api.write_error = AuthorityObjectError("simulated write failure")
    binding, storage, permit, capability = _capability(monkeypatch, api)
    with pytest.raises(AuthorityObjectError):
        with capability as active:
            active.publish(_before_open(binding))
    with pytest.raises(PersonalDesktopUnattendedDecisionPublicationError):
        consume_disposable_pre_open_decision_publication_permit_for_test(
            permit, binding, storage, _before_open(binding)
        )


def test_failed_flush_spends_permit(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailFlush(DecisionNative):
        def write_file(self, path, payload, policy) -> None:
            self.events.append(("write-file", path, payload, policy))
            raise AuthorityObjectError("simulated durable flush failure")

    binding, storage, permit, capability = _capability(monkeypatch, FailFlush())
    with pytest.raises(AuthorityObjectError):
        with capability as active:
            active.publish(_before_open(binding))
    with pytest.raises(PersonalDesktopUnattendedDecisionPublicationError):
        consume_disposable_pre_open_decision_publication_permit_for_test(
            permit, binding, storage, _before_open(binding)
        )


def test_failed_readback_spends_permit(monkeypatch: pytest.MonkeyPatch) -> None:
    class TamperReadback(DecisionNative):
        def read(self, handle: object, maximum: int) -> bytes:
            payload = super().read(handle, maximum)
            if (
                "\\unattended-paper-decision-" in handle.path
                and "\\.unattended-paper-decision-" not in handle.path
            ):
                return bytes((payload[0] ^ 1,)) + payload[1:]
            return payload

    binding, storage, permit, capability = _capability(monkeypatch, TamperReadback())
    with pytest.raises(output.PersonalDesktopPaperRuntimeOutputError):
        with capability as active:
            active.publish(_before_open(binding))
    with pytest.raises(PersonalDesktopUnattendedDecisionPublicationError):
        consume_disposable_pre_open_decision_publication_permit_for_test(
            permit, binding, storage, _before_open(binding)
        )


def test_capability_rejects_parent_outside_fixed_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    *_, capability = _capability(monkeypatch)
    with capability:
        with pytest.raises(AuthorityPathError):
            capability._pin_parent(r"F:\test")


def test_finalized_identical_state_does_not_open_fresh_writer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _decision_binding(monkeypatch)
    finalized = PersonalDesktopUnattendedDecisionStorageReadResult(
        PersonalDesktopUnattendedDecisionStorageClassification.FINALIZED_IDENTICAL,
        binding.decision.decision_id,
        1,
        binding.decision.decision_id,
        PersonalDesktopUnattendedDecisionStorageDiagnostic.VERIFIED_FINALIZED_IDENTICAL,
    )
    deadline = binding.decision.prepared_decision.submitted_at
    with pytest.raises(PersonalDesktopUnattendedDecisionPublicationError):
        issue_disposable_pre_open_decision_publication_permit_for_test(
            binding,
            finalized,
            binding.decision.intended_execution_session,
            deadline,
        )


def test_production_gate_false_never_opens_native_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _decision_binding(monkeypatch)
    storage = _storage(binding)
    authority = SimpleNamespace(
        machine_authority_id="machine",
        approved_account_sid="S-1-5-21-1-2-3-1009",
        authority_epoch_id="epoch",
    )
    verified = SimpleNamespace(
        authority=authority,
        expected=binding,
        classification=PersonalDesktopUnattendedDecisionStorageClassification.ABSENT,
    )
    monkeypatch.setattr(
        output,
        "require_validated_personal_desktop_unattended_decision_storage_read",
        lambda value: verified,
    )
    monkeypatch.setattr(
        output, "require_validated_production_authority", lambda value: value
    )
    monkeypatch.setattr(
        output, "require_pre_open_decision_publication_permit", lambda *args: None
    )
    opened: list[bool] = []
    monkeypatch.setattr(
        output,
        "_WindowsPaperRuntimeOutputNativeApi",
        lambda: opened.append(True),
    )
    with pytest.raises(output.PersonalDesktopPaperRuntimeOutputError):
        output.open_personal_desktop_unattended_decision_output_capability(
            storage,
            object.__new__(PreOpenDecisionPublicationPermit),
        )
    assert opened == []


def test_native_decision_finalizer_is_exact_and_write_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _decision_binding(monkeypatch)
    parent = security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS
    staging = (
        parent
        + "\\"
        + unattended_paper_decision_directory_name(
            binding.decision.decision_id, staging=True
        )
    )
    final = (
        parent
        + "\\"
        + unattended_paper_decision_directory_name(binding.decision.decision_id)
    )
    calls: list[tuple[str, str, int]] = []

    class Move:
        argtypes = None
        restype = None

        def __call__(self, source: str, destination: str, flags: int) -> int:
            calls.append((source, destination, flags))
            return 1

    native = object.__new__(output._WindowsPaperRuntimeOutputNativeApi)
    native._kernel = SimpleNamespace(MoveFileExW=Move())
    native.rename_unattended_write_through(staging, final)
    assert calls == [(staging, final, 0x8)]

    wrong_final = (
        parent
        + "\\"
        + unattended_paper_decision_directory_name(
            binding.decision.current_c3.snapshot_id
        )
    )
    with pytest.raises(AuthorityPathError):
        native.rename_unattended_write_through(staging, wrong_final)
    assert calls == [(staging, final, 0x8)]
