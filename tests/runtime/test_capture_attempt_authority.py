from __future__ import annotations

# ruff: noqa: I001

import hashlib
import os
from datetime import UTC, datetime, date
from pathlib import Path
from uuid import UUID

import pytest
import trading_bot.runtime.capture_attempt_authority as authority

from trading_bot.domain import Symbol
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data import AdjustmentType, ProviderDescriptor, Timeframe
from trading_bot.runtime.capture_attempt_authority import (
    AttemptHistoryState,
    AttemptHistoryCause,
    AtomicAttemptHistoryPointerReplacementError,
    CaptureAllocationClassification,
    CaptureAttemptAuthorityError,
    CaptureAttemptHistoryClassification,
    CaptureAttemptTerminalClassification,
    CaptureRetryClassification,
    CaptureRetryPolicyInputs,
    CurrentAttemptHistoryReference,
    CredentialPersistence,
    CredentialPurpose,
    CredentialStoreType,
    ManualCaptureAttemptRecoveryAction,
    ProviderCallDisposition,
    SecretCleanupResult,
    SnapshotTerminalVerification,
    ZeroProviderCallProofClassification,
    WindowsAtomicAttemptHistoryPointerReplacer,
    allocate_capture_attempt,
    apply_capture_attempt_recovery,
    classify_capture_retry_policy,
    create_capture_attempt_allocation,
    create_capture_attempt_terminal,
    create_capture_attempt_terminal_v2,
    create_attempt_history_head,
    create_manual_capture_attempt_recovery,
    create_windows_market_data_credential_reference,
    create_zero_provider_call_proof,
    derive_scheduled_capture_attempt_id,
    initialize_capture_attempt_history,
    parse_capture_attempt_allocation,
    parse_capture_attempt_terminal_v2,
    parse_windows_market_data_credential_reference,
    parse_zero_provider_call_proof,
    serialize_capture_attempt_allocation,
    serialize_current_attempt_history_reference,
    serialize_capture_attempt_terminal_v2,
    serialize_zero_provider_call_proof,
    serialize_attempt_history_head_record,
    serialize_windows_market_data_credential_reference,
    publish_capture_attempt_terminal,
    publish_zero_provider_call_proof,
    reconcile_allocation_with_readiness,
    select_capture_attempt_terminal,
    verify_capture_attempt_history,
)
from trading_bot.runtime.guarded_capture_readiness import (
    NextEligibleAction,
    ScheduledCaptureReadinessDecision,
    ScheduledReadinessClassification,
    create_scheduled_capture_readiness_decision,
    derive_scheduled_capture_readiness_decision_id,
    serialize_scheduled_capture_readiness_decision,
)
from trading_bot.runtime.scheduled_readiness import (
    ArtifactEvidence,
    HeadRecordEvidence,
    TerminalCheckpointEvidence,
)


NOW = datetime(2026, 1, 5, 15, 30, tzinfo=UTC)


def evidence(label: str) -> ArtifactEvidence:
    payload = label.encode("ascii")
    return ArtifactEvidence(
        uuid5_for(label), hashlib.sha256(payload).hexdigest(), len(payload)
    )


def uuid5_for(label: str) -> UUID:
    return UUID(bytes=hashlib.sha256(label.encode("ascii")).digest()[:16])


def make_credential() -> object:
    return create_windows_market_data_credential_reference(
        owner_account_sid="S-1-5-21-100-200-300-1001",
        api_key_id_target_name="AITradingBot/AlpacaMarketData/v1/paper/KeyId/1",
        api_secret_key_target_name="AITradingBot/AlpacaMarketData/v1/paper/SecretKey/1",
        credential_version="v1",
        permission_profile="read-only-market-data",
        permission_attestation_evidence=evidence("permission"),
        rotation_generation=0,
        reference_policy_version="credential-reference-v1",
    )


def make_allocation(
    root: Path,
    *,
    head_record: HeadRecordEvidence | None = None,
    previous_head: ArtifactEvidence | None = None,
):
    session_id = UUID("11111111-1111-5111-8111-111111111111")
    launch_id = UUID("22222222-2222-5222-8222-222222222222")
    epoch_id = UUID("33333333-3333-5333-8333-333333333333")
    head = evidence("head") if head_record is None else head_record.record
    head_record = (
        HeadRecordEvidence(epoch_id, head, 0) if head_record is None else head_record
    )
    terminal = TerminalCheckpointEvidence(evidence("checkpoint"), 0, NOW)
    symbols = (Symbol("SPY"), Symbol("QQQ"))
    configuration = evidence("configuration")
    attempt_id = derive_scheduled_capture_attempt_id(
        session_id,
        0,
        symbols,
        Timeframe.DAY_1,
        AdjustmentType.RAW,
        ProviderDescriptor("ALPACA", 1, "DAILY_SNAPSHOT", "IEX"),
        "IEX",
        "USD",
        "capture-policy-v1",
        configuration,
    )
    allocation = create_capture_attempt_allocation(
        attempt_id=attempt_id,
        attempt_ordinal=0,
        scheduled_session_id=session_id,
        scheduled_launch_id=launch_id,
        authority_epoch_id=epoch_id,
        head_record=head_record,
        verified_lineage_evidence_id=UUID("44444444-4444-5444-8444-444444444444"),
        terminal_checkpoint=terminal,
        terminal_as_of=NOW,
        readiness_decision=evidence("decision"),
        market_hours_schedule=evidence("hours"),
        capture_policy=evidence("policy"),
        capture_policy_version="capture-policy-v1",
        capture_configuration=configuration,
        snapshot_capture_request_id=UUID("55555555-5555-5555-8555-555555555555"),
        target_session=TradingSession(date(2026, 1, 5)),
        request_timestamp_utc=NOW,
        symbols=symbols,
        timeframe=Timeframe.DAY_1,
        adjustment=AdjustmentType.RAW,
        provider=ProviderDescriptor("ALPACA", 1, "DAILY_SNAPSHOT", "IEX"),
        feed="IEX",
        currency="USD",
        credential_reference=evidence("credential-reference"),
        credential_reference_version="credential-reference-v1",
        destination_reference=evidence("destination"),
        software_release=evidence("release"),
        observed_allocation_at=NOW,
        previous_attempt_history_head=(
            evidence("previous-head") if previous_head is None else previous_head
        ),
        allocation_classification=CaptureAllocationClassification.CAPTURE_ONLY_AUTHORIZED,
        provider_call_budget=1,
        allocation_policy_version="allocation-policy-v1",
    )
    decision_fields = dict(
        scheduled_session_id=session_id,
        scheduled_launch_id=launch_id,
        authority_epoch_id=epoch_id,
        lease_start=evidence("lease"),
        head_record=head_record,
        terminal_checkpoint=terminal,
        market_hours_schedule=allocation.market_hours_schedule,
        capture_policy=allocation.capture_policy,
        capture_attempts=(),
        snapshot_selection=None,
        observed_at=NOW,
        readiness_classification=ScheduledReadinessClassification.READY,
        diagnostics=(),
        provider_invocation_permitted=True,
        next_eligible_action=NextEligibleAction.CAPTURE_ATTEMPT_ALLOWED,
        capture_attempt_ordinal=0,
        capture_attempt_id=attempt_id,
        runner_policy_version="runner-policy-v1",
    )
    decision = ScheduledCaptureReadinessDecision(
        1,
        derive_scheduled_capture_readiness_decision_id(**decision_fields),
        *decision_fields.values(),
    )
    decision_payload = serialize_scheduled_capture_readiness_decision(decision)
    decision_evidence = ArtifactEvidence(
        decision.decision_id,
        hashlib.sha256(decision_payload).hexdigest(),
        len(decision_payload),
    )
    allocation_values = {
        field.name: getattr(allocation, field.name)
        for field in allocation.__dataclass_fields__.values()
    }
    allocation_values["readiness_decision"] = decision_evidence
    allocation = create_capture_attempt_allocation(**allocation_values)
    return allocation, decision, session_id, launch_id, epoch_id


def rebuild_allocation(
    allocation: object,
    **changes: object,
) -> object:
    values = {
        field.name: getattr(allocation, field.name)
        for field in allocation.__dataclass_fields__.values()
    }
    values.update(changes)
    if {
        "attempt_ordinal",
        "scheduled_session_id",
        "symbols",
        "timeframe",
        "adjustment",
        "provider",
        "feed",
        "currency",
        "capture_policy_version",
        "capture_configuration",
    } & changes.keys():
        values["attempt_id"] = derive_scheduled_capture_attempt_id(
            values["scheduled_session_id"],
            values["attempt_ordinal"],
            values["symbols"],
            values["timeframe"],
            values["adjustment"],
            values["provider"],
            values["feed"],
            values["currency"],
            values["capture_policy_version"],
            values["capture_configuration"],
        )
    values.pop("allocation_record_id", None)
    return create_capture_attempt_allocation(**values)


def decision_for(
    decision: ScheduledCaptureReadinessDecision,
    **changes: object,
) -> ScheduledCaptureReadinessDecision:
    values = {
        name: getattr(decision, name)
        for name in (
            "scheduled_session_id",
            "scheduled_launch_id",
            "authority_epoch_id",
            "lease_start",
            "head_record",
            "terminal_checkpoint",
            "market_hours_schedule",
            "capture_policy",
            "capture_attempts",
            "snapshot_selection",
            "observed_at",
            "readiness_classification",
            "diagnostics",
            "provider_invocation_permitted",
            "next_eligible_action",
            "capture_attempt_ordinal",
            "capture_attempt_id",
            "runner_policy_version",
        )
    }
    values.update(changes)
    return create_scheduled_capture_readiness_decision(**values)


def allocation_evidence(root: Path, allocation: object) -> ArtifactEvidence:
    payload = serialize_capture_attempt_allocation(allocation)
    return ArtifactEvidence(
        allocation.allocation_record_id,
        hashlib.sha256(payload).hexdigest(),
        len(payload),
    )


def terminal_values(
    allocation_record: object,
    *,
    classification: CaptureAttemptTerminalClassification,
    **changes: object,
) -> dict[str, object]:
    values: dict[str, object] = {
        "allocation": evidence("allocation"),
        "attempt_id": allocation_record.attempt_id,
        "attempt_ordinal": allocation_record.attempt_ordinal,
        "scheduled_session_id": allocation_record.scheduled_session_id,
        "scheduled_launch_id": allocation_record.scheduled_launch_id,
        "child_request": None,
        "child_launch": None,
        "resume_authorization": None,
        "credential_access": None,
        "child_result": None,
        "provider_call_disposition": ProviderCallDisposition.RESPONSE_CONFIRMED,
        "completed_at": NOW,
        "classification": classification,
        "diagnostics": (classification.value.lower(),),
        "native_child_exit_code": 0,
        "timeout_termination": None,
        "snapshot": evidence("snapshot")
        if classification is CaptureAttemptTerminalClassification.SUCCEEDED
        else None,
        "recovery_candidate": evidence("recovery-candidate")
        if classification is CaptureAttemptTerminalClassification.OUTPUT_FAILED
        else None,
        "snapshot_verification": SnapshotTerminalVerification.PASS
        if classification is CaptureAttemptTerminalClassification.SUCCEEDED
        else SnapshotTerminalVerification.NOT_APPLICABLE,
        "secret_cleanup": SecretCleanupResult.PASS,
        "terminal_policy_version": "terminal-v2",
    }
    if classification in {
        CaptureAttemptTerminalClassification.NETWORK_FAILED,
        CaptureAttemptTerminalClassification.CHILD_CRASHED,
    }:
        values["provider_call_disposition"] = ProviderCallDisposition.MAY_HAVE_STARTED
    if classification in {
        CaptureAttemptTerminalClassification.TIMEOUT,
        CaptureAttemptTerminalClassification.INCOMPLETE_RESPONSE,
        CaptureAttemptTerminalClassification.UNKNOWN_AFTER_LAUNCH,
    }:
        values["provider_call_disposition"] = ProviderCallDisposition.UNKNOWN
    if classification is CaptureAttemptTerminalClassification.TIMEOUT:
        values["timeout_termination"] = evidence("timeout")
    values.update(changes)
    return values


def initialized_case(
    tmp_path: Path,
) -> tuple[
    Path,
    object,
    ScheduledCaptureReadinessDecision,
    UUID,
    UUID,
    UUID,
    ArtifactEvidence,
]:
    root = tmp_path / "authority"
    root.mkdir(parents=True)
    _, _, session_id, launch_id, epoch_id = make_allocation(tmp_path)
    genesis = initialize_capture_attempt_history(
        root, session_id, epoch_id, "history-v1"
    )
    genesis_payload = serialize_attempt_history_head_record(genesis)
    genesis_evidence = ArtifactEvidence(
        genesis.history_head_record_id,
        hashlib.sha256(genesis_payload).hexdigest(),
        len(genesis_payload),
    )
    allocation, decision, _, _, _ = make_allocation(
        tmp_path,
        head_record=HeadRecordEvidence(epoch_id, genesis_evidence, 0),
        previous_head=genesis_evidence,
    )
    return root, allocation, decision, session_id, launch_id, epoch_id, genesis_evidence


def install_head(root: Path, head: object) -> None:
    session_root = root / str(head.scheduled_session_id)
    payload = serialize_attempt_history_head_record(head)
    head_evidence = ArtifactEvidence(
        head.history_head_record_id,
        hashlib.sha256(payload).hexdigest(),
        len(payload),
    )
    (
        session_root
        / "history-head-records"
        / f"capture-attempt-history-head-{head.history_head_record_id}.json"
    ).write_bytes(payload)
    pointer = CurrentAttemptHistoryReference(
        1,
        head.scheduled_session_id,
        head.authority_epoch_id,
        head.generation,
        head_evidence,
    )
    (session_root / "current-attempt-history.json").write_bytes(
        serialize_current_attempt_history_reference(pointer)
    )


class FakePointerReplacer:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[Path, bytes, bytes, tuple[int, int]]] = []

    def replace(
        self,
        pointer_path: Path,
        *,
        expected_payload: bytes,
        replacement_payload: bytes,
        parent_identity: tuple[int, int],
    ) -> None:
        self.calls.append(
            (pointer_path, expected_payload, replacement_payload, parent_identity)
        )
        if self.fail:
            raise AtomicAttemptHistoryPointerReplacementError("forced CAS failure")
        pointer_path.write_bytes(replacement_payload)


def test_credential_reference_round_trip_and_path_independent_identity() -> None:
    reference = make_credential()
    payload = serialize_windows_market_data_credential_reference(reference)
    assert parse_windows_market_data_credential_reference(payload) == reference
    assert (
        reference.store_type is CredentialStoreType.WINDOWS_CREDENTIAL_MANAGER_GENERIC
    )
    assert str(reference.credential_reference_id) == (
        "7b646b65-c2da-5ebc-8252-cfb627d17305"
    )
    assert hashlib.sha256(payload).hexdigest() == (
        "b06f5c29134cefa360671996c5575ef09588ca424fc46f68263fdf38cd7cab01"
    )
    assert reference.persistence is CredentialPersistence.LOCAL_MACHINE
    assert reference.purpose is CredentialPurpose.MARKET_DATA_CAPTURE_ONLY
    assert b"TEST-SECRET-VALUE" not in payload
    assert serialize_windows_market_data_credential_reference(reference) == payload


def test_credential_hostile_json_rejected() -> None:
    reference = make_credential()
    payload = serialize_windows_market_data_credential_reference(reference)
    with pytest.raises(CaptureAttemptAuthorityError):
        parse_windows_market_data_credential_reference(
            payload.replace(b"\n", b',"extra":1}\n')
        )
    with pytest.raises(CaptureAttemptAuthorityError):
        parse_windows_market_data_credential_reference(b"\xef\xbb\xbf" + payload)


def test_genesis_and_allocation_consume_ordinal(tmp_path: Path) -> None:
    root = tmp_path / "authority"
    root.mkdir()
    _, _, session_id, _, epoch_id = make_allocation(tmp_path)
    genesis = initialize_capture_attempt_history(
        root, session_id, epoch_id, "history-v1"
    )
    genesis_payload = serialize_attempt_history_head_record(genesis)
    genesis_evidence = ArtifactEvidence(
        genesis.history_head_record_id,
        hashlib.sha256(genesis_payload).hexdigest(),
        len(genesis_payload),
    )
    allocation, decision, _, _, _ = make_allocation(
        tmp_path,
        head_record=HeadRecordEvidence(epoch_id, genesis_evidence, 0),
        previous_head=genesis_evidence,
    )
    head = allocate_capture_attempt(root, allocation, decision)
    assert genesis.state is AttemptHistoryState.EMPTY
    assert head.state is AttemptHistoryState.ALLOCATED_NOT_LAUNCHED
    assert head.next_attempt_ordinal == 1
    assert str(head.predecessor.artifact_id) == str(genesis.history_head_record_id)
    assert str(allocation.allocation_record_id) == (
        "89630432-4c19-5680-a67d-0faf5d252950"
    )
    assert decision.capture_attempt_id == allocation.attempt_id
    assert allocation.attempt_ordinal == 0
    assert (
        verify_capture_attempt_history(
            root, allocation.scheduled_session_id
        ).classification
        is CaptureAttemptHistoryClassification.PASS
    )


def test_terminal_success_requires_verified_snapshot(tmp_path: Path) -> None:
    root = tmp_path / "authority"
    root.mkdir()
    provisional, _, session_id, launch_id, epoch_id = make_allocation(tmp_path)
    genesis = initialize_capture_attempt_history(
        root, session_id, epoch_id, "history-v1"
    )
    assert genesis.generation == 0
    with pytest.raises(CaptureAttemptAuthorityError):
        create_capture_attempt_terminal_v2(
            allocation=evidence("allocation"),
            attempt_id=provisional.attempt_id,
            attempt_ordinal=provisional.attempt_ordinal,
            scheduled_session_id=session_id,
            scheduled_launch_id=launch_id,
            child_request=None,
            child_launch=None,
            resume_authorization=None,
            credential_access=None,
            child_result=None,
            provider_call_disposition=ProviderCallDisposition.RESPONSE_CONFIRMED,
            completed_at=NOW,
            classification=CaptureAttemptTerminalClassification.SUCCEEDED,
            diagnostics=("missing-snapshot",),
            native_child_exit_code=0,
            timeout_termination=None,
            snapshot=None,
            recovery_candidate=None,
            snapshot_verification=SnapshotTerminalVerification.NOT_APPLICABLE,
            secret_cleanup=SecretCleanupResult.NOT_APPLICABLE,
            terminal_policy_version="terminal-v2",
        )
    genesis_payload = serialize_attempt_history_head_record(genesis)
    genesis_evidence = ArtifactEvidence(
        genesis.history_head_record_id,
        hashlib.sha256(genesis_payload).hexdigest(),
        len(genesis_payload),
    )
    allocation, decision, _, _, _ = make_allocation(
        tmp_path,
        head_record=HeadRecordEvidence(epoch_id, genesis_evidence, 0),
        previous_head=genesis_evidence,
    )
    allocate_capture_attempt(root, allocation, decision)
    allocation_payload = serialize_capture_attempt_allocation(allocation)
    allocation_evidence = ArtifactEvidence(
        allocation.allocation_record_id,
        hashlib.sha256(allocation_payload).hexdigest(),
        len(allocation_payload),
    )
    terminal = create_capture_attempt_terminal_v2(
        allocation=allocation_evidence,
        attempt_id=allocation.attempt_id,
        attempt_ordinal=allocation.attempt_ordinal,
        scheduled_session_id=session_id,
        scheduled_launch_id=launch_id,
        child_request=None,
        child_launch=None,
        resume_authorization=None,
        credential_access=None,
        child_result=None,
        provider_call_disposition=ProviderCallDisposition.RESPONSE_CONFIRMED,
        completed_at=NOW,
        classification=CaptureAttemptTerminalClassification.SUCCEEDED,
        diagnostics=("ok",),
        native_child_exit_code=0,
        timeout_termination=None,
        snapshot=evidence("snapshot"),
        recovery_candidate=None,
        snapshot_verification=SnapshotTerminalVerification.PASS,
        secret_cleanup=SecretCleanupResult.PASS,
        terminal_policy_version="terminal-v2",
    )
    assert str(terminal.terminal_record_id) == ("d334b31e-ff5f-5ebf-bba5-59a273462afc")
    assert (
        parse_capture_attempt_terminal_v2(
            serialize_capture_attempt_terminal_v2(terminal)
        )
        == terminal
    )
    assert publish_capture_attempt_terminal(root, terminal).state.value == (
        "TERMINAL_SELECTED"
    )


def test_zero_call_proof_and_pure_policy() -> None:
    allocation, _, session_id, launch_id, _ = make_allocation(Path("C:/unused"))
    proof = create_zero_provider_call_proof(
        allocation=evidence("allocation"),
        attempt_id=allocation.attempt_id,
        scheduled_session_id=session_id,
        scheduled_launch_id=launch_id,
        child_request=None,
        process_creation=None,
        child_resume=None,
        provider_adapter_stage=None,
        transport_entry=None,
        process_exit_or_termination=None,
        classification=ZeroProviderCallProofClassification.CHILD_NOT_CREATED,
        diagnostics=("not-created",),
        proof_policy_version="proof-v1",
    )
    assert proof.classification is ZeroProviderCallProofClassification.CHILD_NOT_CREATED
    assert str(proof.proof_id) == "a9d63e1a-0e23-5d9c-89d3-2bf05d27d878"
    assert (
        parse_zero_provider_call_proof(serialize_zero_provider_call_proof(proof))
        == proof
    )
    decision = classify_capture_retry_policy(
        CaptureRetryPolicyInputs(
            AttemptHistoryState.ALLOCATED_NOT_LAUNCHED,
            None,
            None,
            True,
            NOW,
            NOW.replace(hour=16),
            2,
            None,
            False,
            None,
        )
    )
    assert (
        decision.classification
        is CaptureRetryClassification.SAME_ATTEMPT_CONTINUATION_ALLOWED
    )


def test_timeout_policy_requires_manual_review() -> None:
    result = classify_capture_retry_policy(
        CaptureRetryPolicyInputs(
            AttemptHistoryState.LAUNCH_MAY_HAVE_OCCURRED,
            CaptureAttemptTerminalClassification.TIMEOUT,
            ProviderCallDisposition.UNKNOWN,
            False,
            NOW,
            NOW.replace(hour=16),
            2,
            None,
            False,
            None,
        )
    )
    assert result.classification is CaptureRetryClassification.MANUAL_REVIEW_REQUIRED


@pytest.mark.parametrize(
    ("label", "changes"),
    [
        ("wrong-ordinal", {"attempt_ordinal": 1}),
        ("wrong-session", {"scheduled_session_id": uuid5_for("session-other")}),
        ("wrong-launch", {"scheduled_launch_id": uuid5_for("launch-other")}),
        (
            "wrong-epoch",
            {
                "authority_epoch_id": uuid5_for("epoch-other"),
                "head_record": HeadRecordEvidence(
                    uuid5_for("epoch-other"), evidence("head-other"), 0
                ),
            },
        ),
        (
            "wrong-head",
            {
                "head_record": HeadRecordEvidence(
                    UUID("33333333-3333-5333-8333-333333333333"),
                    evidence("head-other"),
                    0,
                )
            },
        ),
        (
            "wrong-terminal",
            {
                "terminal_checkpoint": TerminalCheckpointEvidence(
                    evidence("checkpoint-other"), 0, NOW
                )
            },
        ),
        ("wrong-policy", {"capture_policy": evidence("policy-other")}),
    ],
)
def test_allocation_reconciliation_rejects_wrong_authority_evidence(
    tmp_path: Path, label: str, changes: dict[str, object]
) -> None:
    _ = tmp_path
    _, allocation, decision, _, _, _, _ = initialized_case(tmp_path)
    with pytest.raises(CaptureAttemptAuthorityError, match="authorized"):
        reconcile_allocation_with_readiness(
            rebuild_allocation(allocation, **changes), decision
        )


@pytest.mark.parametrize(
    ("label", "changes"),
    [
        ("wrong-attempt-id", {"capture_attempt_id": uuid5_for("attempt-other")}),
        ("wrong-session", {"scheduled_session_id": uuid5_for("session-other")}),
        ("wrong-launch", {"scheduled_launch_id": uuid5_for("launch-other")}),
        (
            "wrong-epoch",
            {
                "authority_epoch_id": uuid5_for("epoch-other"),
                "head_record": HeadRecordEvidence(
                    uuid5_for("epoch-other"), evidence("head-other"), 0
                ),
            },
        ),
        (
            "wrong-head",
            {
                "head_record": HeadRecordEvidence(
                    UUID("33333333-3333-5333-8333-333333333333"),
                    evidence("head-other"),
                    0,
                )
            },
        ),
        (
            "wrong-terminal",
            {
                "terminal_checkpoint": TerminalCheckpointEvidence(
                    evidence("checkpoint-other"), 0, NOW
                )
            },
        ),
        ("wrong-policy", {"capture_policy": evidence("policy-other")}),
    ],
)
def test_readiness_reconciliation_rejects_mismatched_decision_fields(
    tmp_path: Path, label: str, changes: dict[str, object]
) -> None:
    _, allocation, decision, _, _, _, _ = initialized_case(tmp_path)
    with pytest.raises(CaptureAttemptAuthorityError, match="authorized"):
        reconcile_allocation_with_readiness(
            allocation, decision_for(decision, **changes)
        )


@pytest.mark.parametrize(
    ("label", "changes"),
    [
        ("credential", {"credential_reference": evidence("credential-other")}),
        ("destination", {"destination_reference": evidence("destination-other")}),
        ("release", {"software_release": evidence("release-other")}),
        ("allocation-policy", {"allocation_policy_version": "allocation-policy-v2"}),
    ],
)
def test_allocation_reconciliation_rejects_wrong_allocation_references(
    tmp_path: Path, label: str, changes: dict[str, object]
) -> None:
    root, allocation, decision, session_id, _, _, _ = initialized_case(tmp_path)
    alternate = rebuild_allocation(allocation, **changes)
    # These references are part of the immutable allocation identity.  A
    # substituted value must not be accepted as the pointer-selected record.
    assert alternate.allocation_record_id != allocation.allocation_record_id
    allocate_capture_attempt(root, allocation, decision)
    allocation_path = (
        root
        / str(session_id)
        / "allocations"
        / f"capture-attempt-allocation-{allocation.allocation_record_id}.json"
    )
    allocation_path.write_bytes(serialize_capture_attempt_allocation(alternate))
    assert (
        verify_capture_attempt_history(root, session_id).classification
        is CaptureAttemptHistoryClassification.CONFLICTING
    )


def test_non_ready_decision_cannot_allocate(tmp_path: Path) -> None:
    root, allocation, decision, _, _, _, _ = initialized_case(tmp_path)
    not_ready = decision_for(
        decision,
        readiness_classification=ScheduledReadinessClassification.NOT_READY,
        provider_invocation_permitted=False,
        next_eligible_action=NextEligibleAction.WAIT,
        capture_attempt_ordinal=None,
        capture_attempt_id=None,
    )
    with pytest.raises(CaptureAttemptAuthorityError):
        allocate_capture_attempt(root, allocation, not_ready)


def test_allocation_consumes_ordinal_and_never_reuses_without_terminal(
    tmp_path: Path,
) -> None:
    root, allocation, decision, session_id, _, _, _ = initialized_case(tmp_path)
    first = allocate_capture_attempt(root, allocation, decision)
    assert first.next_attempt_ordinal == 1
    with pytest.raises(CaptureAttemptAuthorityError):
        allocate_capture_attempt(root, allocation, decision)
    result = verify_capture_attempt_history(root, session_id)
    assert result.head is not None
    assert result.head.state is AttemptHistoryState.ALLOCATED_NOT_LAUNCHED
    assert result.head.next_attempt_ordinal == 1


def test_next_allocation_uses_next_ordinal_after_terminal(tmp_path: Path) -> None:
    root, allocation, decision, session_id, _, epoch_id, _ = initialized_case(tmp_path)
    allocate_capture_attempt(root, allocation, decision)
    failed = create_capture_attempt_terminal(
        **terminal_values(
            allocation,
            classification=CaptureAttemptTerminalClassification.PROVIDER_REJECTED,
            allocation=allocation_evidence(root, allocation),
        )
    )
    publish_capture_attempt_terminal(root, failed)
    current = verify_capture_attempt_history(root, session_id)
    assert current.pointer is not None and current.head is not None
    head_payload = serialize_attempt_history_head_record(current.head)
    head_evidence = ArtifactEvidence(
        current.head.history_head_record_id,
        hashlib.sha256(head_payload).hexdigest(),
        len(head_payload),
    )
    checkpoint = TerminalCheckpointEvidence(evidence("checkpoint-next"), 1, NOW)
    next_allocation = rebuild_allocation(
        allocation,
        attempt_ordinal=1,
        head_record=HeadRecordEvidence(epoch_id, head_evidence, 1),
        terminal_checkpoint=checkpoint,
        terminal_as_of=NOW,
        previous_attempt_history_head=current.pointer.head_record,
    )
    next_decision = decision_for(
        decision,
        head_record=next_allocation.head_record,
        terminal_checkpoint=next_allocation.terminal_checkpoint,
        capture_attempt_ordinal=1,
        capture_attempt_id=next_allocation.attempt_id,
    )
    decision_payload = serialize_scheduled_capture_readiness_decision(next_decision)
    next_allocation = rebuild_allocation(
        next_allocation,
        readiness_decision=ArtifactEvidence(
            next_decision.decision_id,
            hashlib.sha256(decision_payload).hexdigest(),
            len(decision_payload),
        ),
    )
    next_head = allocate_capture_attempt(root, next_allocation, next_decision)
    assert next_allocation.attempt_ordinal == 1
    assert next_head.next_attempt_ordinal == 2


def test_stale_expected_pointer_and_compare_and_swap_failure_preserve_old_head(
    tmp_path: Path,
) -> None:
    root, allocation, decision, session_id, _, _, genesis_evidence = initialized_case(
        tmp_path
    )
    stale = rebuild_allocation(
        allocation, previous_attempt_history_head=evidence("stale-head")
    )
    with pytest.raises(CaptureAttemptAuthorityError):
        allocate_capture_attempt(root, stale, decision)
    replacer = FakePointerReplacer(fail=True)
    with pytest.raises(AtomicAttemptHistoryPointerReplacementError):
        allocate_capture_attempt(root, allocation, decision, pointer_replacer=replacer)
    result = verify_capture_attempt_history(root, session_id)
    assert result.head is not None
    assert result.head.generation == 0
    assert result.head.state is AttemptHistoryState.EMPTY
    assert result.pointer is not None
    assert result.pointer.head_record == genesis_evidence


def test_allocation_retry_after_replacement_failure_uses_old_pointer_authority(
    tmp_path: Path,
) -> None:
    root, allocation, decision, session_id, _, _, _ = initialized_case(tmp_path)
    with pytest.raises(AtomicAttemptHistoryPointerReplacementError):
        allocate_capture_attempt(
            root, allocation, decision, pointer_replacer=FakePointerReplacer(fail=True)
        )
    head = allocate_capture_attempt(root, allocation, decision)
    assert head.state is AttemptHistoryState.ALLOCATED_NOT_LAUNCHED
    assert (
        verify_capture_attempt_history(root, session_id).classification
        is CaptureAttemptHistoryClassification.PASS
    )


@pytest.mark.parametrize(
    "kind",
    ["generation-gap", "rollback", "fork", "changed-epoch", "altered-predecessor"],
)
def test_history_rejects_generation_rollback_fork_epoch_and_predecessor_conflicts(
    tmp_path: Path, kind: str
) -> None:
    root, allocation, decision, session_id, _, epoch_id, genesis_evidence = (
        initialized_case(tmp_path)
    )
    allocate_capture_attempt(root, allocation, decision)
    current = verify_capture_attempt_history(root, session_id).head
    assert current is not None
    if kind == "generation-gap":
        generation, predecessor, epoch, next_ordinal = (
            3,
            current.predecessor,
            epoch_id,
            2,
        )
    elif kind == "rollback":
        generation, predecessor, epoch, next_ordinal = (
            current.generation + 1,
            current.predecessor,
            epoch_id,
            0,
        )
    elif kind == "fork":
        generation, predecessor, epoch, next_ordinal = (
            current.generation + 1,
            genesis_evidence,
            epoch_id,
            current.next_attempt_ordinal + 1,
        )
    elif kind == "changed-epoch":
        epoch = uuid5_for("epoch-other")
        generation, predecessor, next_ordinal = (
            current.generation + 1,
            current.predecessor,
            current.next_attempt_ordinal + 1,
        )
    else:
        generation, predecessor, epoch, next_ordinal = (
            current.generation + 1,
            evidence("missing-predecessor"),
            epoch_id,
            current.next_attempt_ordinal,
        )
    forged = create_attempt_history_head(
        scheduled_session_id=session_id,
        authority_epoch_id=epoch,
        generation=generation,
        predecessor=predecessor,
        latest_allocation=current.latest_allocation,
        latest_terminal=current.latest_terminal,
        latest_zero_call_proof=current.latest_zero_call_proof,
        latest_recovery=current.latest_recovery,
        state=current.state,
        next_attempt_ordinal=next_ordinal,
        advancement_cause=AttemptHistoryCause.ALLOCATION,
        policy_version=current.policy_version,
    )
    install_head(root, forged)
    assert verify_capture_attempt_history(root, session_id).classification in {
        CaptureAttemptHistoryClassification.CONFLICTING,
        CaptureAttemptHistoryClassification.BLOCKED,
    }


def test_history_ignores_filenames_directory_counts_and_maximum_ordinals(
    tmp_path: Path,
) -> None:
    root, allocation, decision, session_id, _, _, _ = initialized_case(tmp_path)
    allocate_capture_attempt(root, allocation, decision)
    session_root = root / str(session_id)
    (session_root / "allocations" / "capture-attempt-999999.json").write_bytes(
        b"not-authoritative"
    )
    (session_root / "history-head-records" / "fork.json").write_bytes(
        b"not-authoritative"
    )
    (session_root / "unexpected-entry.txt").write_bytes(b"ignored")
    result = verify_capture_attempt_history(root, session_id)
    assert result.classification is CaptureAttemptHistoryClassification.PASS


@pytest.mark.parametrize(
    "classification",
    list(CaptureAttemptTerminalClassification),
    ids=lambda value: value.value,
)
def test_schema2_terminal_classifications_have_canonical_records(
    classification: CaptureAttemptTerminalClassification,
) -> None:
    allocation, _, _, _, _ = make_allocation(Path("C:/unused"))
    terminal = create_capture_attempt_terminal(
        **terminal_values(allocation, classification=classification)
    )
    assert terminal.classification is classification
    assert (
        parse_capture_attempt_terminal_v2(
            serialize_capture_attempt_terminal_v2(terminal)
        )
        == terminal
    )


def test_terminal_invariants_reject_snapshot_and_ambiguous_claims() -> None:
    allocation, _, session_id, launch_id, _ = make_allocation(Path("C:/unused"))
    success_values = terminal_values(
        allocation,
        classification=CaptureAttemptTerminalClassification.SUCCEEDED,
        snapshot=None,
    )
    with pytest.raises(CaptureAttemptAuthorityError, match="snapshot"):
        create_capture_attempt_terminal(**success_values)
    failed_values = terminal_values(
        allocation,
        classification=CaptureAttemptTerminalClassification.NETWORK_FAILED,
        snapshot=evidence("accepted-snapshot"),
        snapshot_verification=SnapshotTerminalVerification.PASS,
    )
    with pytest.raises(CaptureAttemptAuthorityError, match="failed terminal"):
        create_capture_attempt_terminal(**failed_values)
    for classification in (
        CaptureAttemptTerminalClassification.TIMEOUT,
        CaptureAttemptTerminalClassification.UNKNOWN_AFTER_LAUNCH,
    ):
        values = terminal_values(
            allocation,
            classification=classification,
            provider_call_disposition=ProviderCallDisposition.NOT_STARTED,
        )
        with pytest.raises(CaptureAttemptAuthorityError, match="NOT_STARTED"):
            create_capture_attempt_terminal(**values)
    mismatched = terminal_values(
        allocation,
        classification=CaptureAttemptTerminalClassification.PROVIDER_REJECTED,
        attempt_id=uuid5_for("wrong-attempt"),
        scheduled_session_id=session_id,
        scheduled_launch_id=launch_id,
    )
    terminal = create_capture_attempt_terminal(**mismatched)
    assert terminal.attempt_id == uuid5_for("wrong-attempt")


@pytest.mark.parametrize(
    "field",
    ["child_launch", "resume_authorization", "credential_access", "child_result"],
)
def test_terminal_rejects_child_evidence_without_its_predecessor(field: str) -> None:
    allocation, _, _, _, _ = make_allocation(Path("C:/unused"))
    with pytest.raises(CaptureAttemptAuthorityError, match="child evidence"):
        create_capture_attempt_terminal(
            **terminal_values(
                allocation,
                classification=CaptureAttemptTerminalClassification.PROVIDER_REJECTED,
                **{field: evidence(f"orphan-{field}")},
            )
        )


def test_terminal_publication_rejects_allocation_identity_mismatches(
    tmp_path: Path,
) -> None:
    root, allocation, decision, session_id, launch_id, _, _ = initialized_case(tmp_path)
    allocate_capture_attempt(root, allocation, decision)
    actual_allocation = allocation_evidence(root, allocation)
    cases = {
        "allocation": {"allocation": evidence("substituted-allocation")},
        "attempt": {"attempt_id": uuid5_for("wrong-attempt")},
        "ordinal": {"attempt_ordinal": allocation.attempt_ordinal + 1},
        "session": {"scheduled_session_id": uuid5_for("wrong-session")},
        "launch": {"scheduled_launch_id": uuid5_for("wrong-launch")},
    }
    for _label, changes in cases.items():
        values = terminal_values(
            allocation,
            classification=CaptureAttemptTerminalClassification.PROVIDER_REJECTED,
            allocation=actual_allocation,
        )
        values.update(changes)
        terminal = create_capture_attempt_terminal(**values)
        with pytest.raises(CaptureAttemptAuthorityError):
            publish_capture_attempt_terminal(root, terminal)
    assert verify_capture_attempt_history(root, session_id).head is not None
    assert launch_id == allocation.scheduled_launch_id


@pytest.mark.parametrize(
    "classification",
    list(ZeroProviderCallProofClassification),
    ids=lambda value: value.value,
)
def test_every_zero_provider_call_proof_classification_requires_its_evidence(
    classification: ZeroProviderCallProofClassification,
) -> None:
    allocation, _, session_id, launch_id, _ = make_allocation(Path("C:/unused"))
    values: dict[str, object] = {
        "allocation": evidence("allocation"),
        "attempt_id": allocation.attempt_id,
        "scheduled_session_id": session_id,
        "scheduled_launch_id": launch_id,
        "child_request": None,
        "process_creation": None,
        "child_resume": None,
        "provider_adapter_stage": None,
        "transport_entry": None,
        "process_exit_or_termination": None,
        "classification": classification,
        "diagnostics": (classification.value.lower(),),
        "proof_policy_version": "proof-v1",
    }
    if classification is not ZeroProviderCallProofClassification.CHILD_NOT_CREATED:
        values.update(
            child_request=evidence("child-request"),
            process_creation=evidence("process-creation"),
            process_exit_or_termination=evidence("process-exit"),
        )
    if classification in {
        ZeroProviderCallProofClassification.CHILD_EXITED_BEFORE_PROVIDER_ADAPTER,
        ZeroProviderCallProofClassification.PROVIDER_ADAPTER_NOT_ENTERED,
        ZeroProviderCallProofClassification.TRANSPORT_NOT_ENTERED,
    }:
        values["child_resume"] = evidence("child-resume")
    if classification in {
        ZeroProviderCallProofClassification.PROVIDER_ADAPTER_NOT_ENTERED,
        ZeroProviderCallProofClassification.TRANSPORT_NOT_ENTERED,
    }:
        values["provider_adapter_stage"] = evidence("adapter-stage")
    if classification is ZeroProviderCallProofClassification.TRANSPORT_NOT_ENTERED:
        values["transport_entry"] = evidence("transport-entry")
    proof = create_zero_provider_call_proof(**values)
    assert proof.classification is classification


@pytest.mark.parametrize(
    "changes",
    [
        {"child_request": evidence("contradictory-child")},
        {"process_creation": evidence("process-only")},
        {"process_exit_or_termination": evidence("termination-only")},
        {"process_exit_or_termination": evidence("timeout-only")},
        {"child_request": evidence("child"), "process_creation": evidence("creation")},
        {
            "child_request": evidence("child"),
            "process_creation": evidence("creation"),
            "child_resume": evidence("resume"),
            "provider_adapter_stage": evidence("adapter"),
        },
        {
            "child_request": evidence("child"),
            "process_creation": evidence("creation"),
            "child_resume": evidence("resume"),
            "provider_adapter_stage": evidence("adapter"),
            "transport_entry": evidence("transport"),
        },
    ],
    ids=[
        "child-request",
        "process-only",
        "termination-only",
        "timeout-only",
        "missing-exit",
        "adapter-contradiction",
        "transport-contradiction",
    ],
)
def test_zero_provider_call_proof_rejects_missing_or_contradictory_evidence(
    changes: dict[str, object],
) -> None:
    allocation, _, session_id, launch_id, _ = make_allocation(Path("C:/unused"))
    values = {
        "allocation": evidence("allocation"),
        "attempt_id": allocation.attempt_id,
        "scheduled_session_id": session_id,
        "scheduled_launch_id": launch_id,
        "child_request": None,
        "process_creation": None,
        "child_resume": None,
        "provider_adapter_stage": None,
        "transport_entry": None,
        "process_exit_or_termination": None,
        "classification": ZeroProviderCallProofClassification.CHILD_NOT_CREATED,
        "diagnostics": ("rejected",),
        "proof_policy_version": "proof-v1",
    }
    values.update(changes)
    with pytest.raises(CaptureAttemptAuthorityError):
        create_zero_provider_call_proof(**values)


def test_zero_provider_call_proof_publication_rejects_substituted_allocation(
    tmp_path: Path,
) -> None:
    root, allocation, decision, _, launch_id, _, _ = initialized_case(tmp_path)
    allocate_capture_attempt(root, allocation, decision)
    proof = create_zero_provider_call_proof(
        allocation=evidence("substituted-allocation"),
        attempt_id=allocation.attempt_id,
        scheduled_session_id=allocation.scheduled_session_id,
        scheduled_launch_id=launch_id,
        child_request=None,
        process_creation=None,
        child_resume=None,
        provider_adapter_stage=None,
        transport_entry=None,
        process_exit_or_termination=None,
        classification=ZeroProviderCallProofClassification.CHILD_NOT_CREATED,
        diagnostics=("not-created",),
        proof_policy_version="proof-v1",
    )
    with pytest.raises(CaptureAttemptAuthorityError):
        publish_zero_provider_call_proof(root, proof)


def recovery_record_for(
    *,
    history_head: ArtifactEvidence,
    allocation: ArtifactEvidence,
    action: ManualCaptureAttemptRecoveryAction,
    resulting_state: AttemptHistoryState,
    zero_call_proof: ArtifactEvidence | None = None,
    terminal: ArtifactEvidence | None = None,
    snapshot_candidate: ArtifactEvidence | None = None,
    operator_approval: ArtifactEvidence | None = None,
) -> object:
    return create_manual_capture_attempt_recovery(
        history_head=history_head,
        allocation=allocation,
        zero_call_proof=zero_call_proof,
        terminal=terminal,
        snapshot_candidate=snapshot_candidate,
        operator_approval=evidence("approval")
        if operator_approval is None
        else operator_approval,
        action=action,
        resulting_state=resulting_state,
        recovery_policy_version="recovery-v1",
    )


def publish_allocated_success(
    tmp_path: Path,
) -> tuple[
    Path,
    object,
    ArtifactEvidence,
    ArtifactEvidence,
    ArtifactEvidence,
    ArtifactEvidence,
]:
    root, allocation, decision, session_id, _, _, _ = initialized_case(tmp_path)
    allocate_capture_attempt(root, allocation, decision)
    allocation_ref = allocation_evidence(root, allocation)
    terminal = create_capture_attempt_terminal(
        **terminal_values(
            allocation,
            classification=CaptureAttemptTerminalClassification.SUCCEEDED,
            allocation=allocation_ref,
        )
    )
    publish_capture_attempt_terminal(root, terminal)
    result = verify_capture_attempt_history(root, session_id)
    assert result.pointer is not None and result.head is not None
    assert result.head.latest_terminal is not None
    assert terminal.snapshot is not None
    return (
        root,
        allocation,
        result.pointer.head_record,
        allocation_ref,
        result.head.latest_terminal,
        terminal.snapshot,
    )


def test_every_manual_recovery_action_can_be_applied_provider_free(
    tmp_path: Path,
) -> None:
    root, allocation, decision, session_id, _, _, _ = initialized_case(tmp_path)
    allocate_capture_attempt(root, allocation, decision)
    allocation_ref = allocation_evidence(root, allocation)
    proof = create_zero_provider_call_proof(
        allocation=allocation_ref,
        attempt_id=allocation.attempt_id,
        scheduled_session_id=session_id,
        scheduled_launch_id=allocation.scheduled_launch_id,
        child_request=None,
        process_creation=None,
        child_resume=None,
        provider_adapter_stage=None,
        transport_entry=None,
        process_exit_or_termination=None,
        classification=ZeroProviderCallProofClassification.CHILD_NOT_CREATED,
        diagnostics=("not-created",),
        proof_policy_version="proof-v1",
    )
    proof_ref = publish_zero_provider_call_proof(root, proof)
    current = verify_capture_attempt_history(root, session_id)
    assert current.pointer is not None
    continuation = recovery_record_for(
        history_head=current.pointer.head_record,
        allocation=allocation_ref,
        action=ManualCaptureAttemptRecoveryAction.CONTINUE_ALLOCATED_ATTEMPT_WITH_ZERO_CALL_PROOF,
        resulting_state=AttemptHistoryState.ALLOCATED_NOT_LAUNCHED,
        zero_call_proof=proof_ref,
    )
    head = apply_capture_attempt_recovery(root, continuation, session_id)
    assert head.state is AttemptHistoryState.ALLOCATED_NOT_LAUNCHED

    (
        root2,
        allocation2,
        terminal_head,
        allocation_ref2,
        terminal_ref2,
        snapshot_ref2,
    ) = publish_allocated_success(tmp_path / "select")
    selection = recovery_record_for(
        history_head=terminal_head,
        allocation=allocation_ref2,
        terminal=terminal_ref2,
        action=ManualCaptureAttemptRecoveryAction.SELECT_EXISTING_TERMINAL,
        resulting_state=AttemptHistoryState.TERMINAL_SELECTED,
    )
    selected_head = apply_capture_attempt_recovery(
        root2, selection, allocation2.scheduled_session_id
    )
    assert selected_head.state is AttemptHistoryState.TERMINAL_SELECTED

    current2 = verify_capture_attempt_history(root2, allocation2.scheduled_session_id)
    assert current2.pointer is not None
    snapshot_recovery = recovery_record_for(
        history_head=current2.pointer.head_record,
        allocation=allocation_ref2,
        snapshot_candidate=snapshot_ref2,
        action=ManualCaptureAttemptRecoveryAction.RECOVER_COMMITTED_SNAPSHOT_AS_SUCCESS,
        resulting_state=AttemptHistoryState.SUCCESS_SELECTED,
    )
    success_head = apply_capture_attempt_recovery(
        root2, snapshot_recovery, allocation2.scheduled_session_id
    )
    assert success_head.state is AttemptHistoryState.SUCCESS_SELECTED

    root3, allocation3, decision3, session3, _, _, _ = initialized_case(
        tmp_path / "ambiguous"
    )
    allocate_capture_attempt(root3, allocation3, decision3)
    alloc3_ref = allocation_evidence(root3, allocation3)
    timeout = create_capture_attempt_terminal(
        **terminal_values(
            allocation3,
            classification=CaptureAttemptTerminalClassification.TIMEOUT,
            allocation=alloc3_ref,
        )
    )
    publish_capture_attempt_terminal(root3, timeout)
    ambiguous = verify_capture_attempt_history(root3, session3)
    assert ambiguous.pointer is not None
    review = recovery_record_for(
        history_head=ambiguous.pointer.head_record,
        allocation=alloc3_ref,
        action=ManualCaptureAttemptRecoveryAction.MARK_ATTEMPT_AMBIGUOUS_AND_REQUIRE_NEW_REVIEW,
        resulting_state=AttemptHistoryState.RECOVERY_REQUIRED,
    )
    assert (
        apply_capture_attempt_recovery(root3, review, session3).state
        is AttemptHistoryState.RECOVERY_REQUIRED
    )

    root4, allocation4, decision4, session4, _, _, _ = initialized_case(
        tmp_path / "close"
    )
    allocate_capture_attempt(root4, allocation4, decision4)
    alloc4_ref = allocation_evidence(root4, allocation4)
    closed = verify_capture_attempt_history(root4, session4)
    assert closed.pointer is not None
    close = recovery_record_for(
        history_head=closed.pointer.head_record,
        allocation=alloc4_ref,
        action=ManualCaptureAttemptRecoveryAction.CLOSE_SESSION_WITHOUT_CAPTURE,
        resulting_state=AttemptHistoryState.SESSION_CLOSED,
    )
    assert (
        apply_capture_attempt_recovery(root4, close, session4).state
        is AttemptHistoryState.SESSION_CLOSED
    )


def test_select_existing_success_terminal_advances_authoritative_state(
    tmp_path: Path,
) -> None:
    root, allocation, _, _, _, _ = publish_allocated_success(tmp_path)
    selection = select_capture_attempt_terminal(
        root,
        allocation.scheduled_session_id,
        "selection-v1",
    )
    assert selection.result == "SUCCESS_SELECTED"
    result = verify_capture_attempt_history(root, allocation.scheduled_session_id)
    assert result.head is not None
    assert result.head.state is AttemptHistoryState.SUCCESS_SELECTED


@pytest.mark.parametrize(
    "action",
    [
        ManualCaptureAttemptRecoveryAction.CONTINUE_ALLOCATED_ATTEMPT_WITH_ZERO_CALL_PROOF,
        ManualCaptureAttemptRecoveryAction.SELECT_EXISTING_TERMINAL,
        ManualCaptureAttemptRecoveryAction.RECOVER_COMMITTED_SNAPSHOT_AS_SUCCESS,
    ],
    ids=lambda value: value.value,
)
def test_recovery_actions_reject_illegal_missing_required_evidence(
    action: ManualCaptureAttemptRecoveryAction,
) -> None:
    kwargs = {
        "history_head": evidence("head"),
        "allocation": evidence("allocation"),
        "zero_call_proof": None,
        "terminal": None,
        "snapshot_candidate": None,
        "operator_approval": evidence("approval"),
        "action": action,
        "resulting_state": AttemptHistoryState.SESSION_CLOSED,
        "recovery_policy_version": "recovery-v1",
    }
    with pytest.raises(CaptureAttemptAuthorityError):
        create_manual_capture_attempt_recovery(**kwargs)


def test_recovery_rejects_illegal_resulting_state() -> None:
    with pytest.raises(CaptureAttemptAuthorityError):
        create_manual_capture_attempt_recovery(
            history_head=evidence("head"),
            allocation=evidence("allocation"),
            zero_call_proof=None,
            terminal=None,
            snapshot_candidate=None,
            operator_approval=evidence("approval"),
            action=ManualCaptureAttemptRecoveryAction.MARK_ATTEMPT_AMBIGUOUS_AND_REQUIRE_NEW_REVIEW,
            resulting_state=AttemptHistoryState.TERMINAL_SELECTED,
            recovery_policy_version="recovery-v1",
        )


def test_recovery_failures_cover_stale_binding_missing_approval_and_divergent_conflict(
    tmp_path: Path,
) -> None:
    root, allocation, decision, session_id, _, _, _ = initialized_case(tmp_path)
    allocate_capture_attempt(root, allocation, decision)
    allocation_ref = allocation_evidence(root, allocation)
    current = verify_capture_attempt_history(root, session_id)
    assert current.pointer is not None
    with pytest.raises(CaptureAttemptAuthorityError):
        create_manual_capture_attempt_recovery(
            history_head=current.pointer.head_record,
            allocation=allocation_ref,
            zero_call_proof=None,
            terminal=None,
            snapshot_candidate=None,
            operator_approval=None,
            action=ManualCaptureAttemptRecoveryAction.CLOSE_SESSION_WITHOUT_CAPTURE,
            resulting_state=AttemptHistoryState.SESSION_CLOSED,
            recovery_policy_version="recovery-v1",
        )
    with pytest.raises(CaptureAttemptAuthorityError):
        recovery_record_for(
            history_head=current.pointer.head_record,
            allocation=allocation_ref,
            action=ManualCaptureAttemptRecoveryAction.CONTINUE_ALLOCATED_ATTEMPT_WITH_ZERO_CALL_PROOF,
            resulting_state=AttemptHistoryState.ALLOCATED_NOT_LAUNCHED,
        )
    stale = recovery_record_for(
        history_head=evidence("stale-head"),
        allocation=allocation_ref,
        action=ManualCaptureAttemptRecoveryAction.CLOSE_SESSION_WITHOUT_CAPTURE,
        resulting_state=AttemptHistoryState.SESSION_CLOSED,
    )
    with pytest.raises(CaptureAttemptAuthorityError):
        apply_capture_attempt_recovery(root, stale, session_id)
    mismatched = recovery_record_for(
        history_head=current.pointer.head_record,
        allocation=evidence("other-allocation"),
        action=ManualCaptureAttemptRecoveryAction.CLOSE_SESSION_WITHOUT_CAPTURE,
        resulting_state=AttemptHistoryState.SESSION_CLOSED,
    )
    with pytest.raises(CaptureAttemptAuthorityError):
        apply_capture_attempt_recovery(root, mismatched, session_id)
    valid = recovery_record_for(
        history_head=current.pointer.head_record,
        allocation=allocation_ref,
        action=ManualCaptureAttemptRecoveryAction.CLOSE_SESSION_WITHOUT_CAPTURE,
        resulting_state=AttemptHistoryState.SESSION_CLOSED,
    )
    apply_capture_attempt_recovery(root, valid, session_id)
    with pytest.raises(CaptureAttemptAuthorityError):
        apply_capture_attempt_recovery(root, valid, session_id)


def test_recovery_rejects_invalid_snapshot_candidate(tmp_path: Path) -> None:
    root, allocation, terminal_head, allocation_ref, terminal_ref, _ = (
        publish_allocated_success(tmp_path)
    )
    current = verify_capture_attempt_history(root, allocation.scheduled_session_id)
    assert current.pointer is not None
    invalid = recovery_record_for(
        history_head=current.pointer.head_record,
        allocation=allocation_ref,
        terminal=terminal_ref,
        snapshot_candidate=evidence("not-the-committed-snapshot"),
        action=ManualCaptureAttemptRecoveryAction.RECOVER_COMMITTED_SNAPSHOT_AS_SUCCESS,
        resulting_state=AttemptHistoryState.SUCCESS_SELECTED,
    )
    with pytest.raises(CaptureAttemptAuthorityError, match="snapshot candidate"):
        apply_capture_attempt_recovery(root, invalid, allocation.scheduled_session_id)


def test_filesystem_publication_handles_staging_conflict_and_identical_bytes(
    tmp_path: Path,
) -> None:
    allocation, _, _, _, _ = make_allocation(tmp_path)
    directory = tmp_path / "publication"
    directory.mkdir()
    path = directory / "artifact.json"
    payload = serialize_capture_attempt_allocation(allocation)
    authority._publish_exclusive(path, payload, parse_capture_attempt_allocation)
    authority._publish_exclusive(path, payload, parse_capture_attempt_allocation)
    path.write_bytes(payload[:-1] + b" ")
    with pytest.raises(CaptureAttemptAuthorityError):
        authority._publish_exclusive(path, payload, parse_capture_attempt_allocation)
    path.unlink()
    staging = directory / ".artifact.json.staging"
    staging.write_bytes(payload)
    with pytest.raises(CaptureAttemptAuthorityError, match="staging"):
        authority._publish_exclusive(path, payload, parse_capture_attempt_allocation)


@pytest.mark.skipif(os.name != "nt", reason="case-fold collision requires Windows")
def test_filesystem_case_fold_collision_and_unexpected_entries_are_not_discovered(
    tmp_path: Path,
) -> None:
    allocation, _, _, _, _ = make_allocation(tmp_path)
    directory = tmp_path / "case"
    directory.mkdir()
    path = directory / "Capture.json"
    payload = serialize_capture_attempt_allocation(allocation)
    authority._publish_exclusive(path, payload, parse_capture_attempt_allocation)
    folded = directory / "capture.JSON"
    authority._publish_exclusive(folded, payload, parse_capture_attempt_allocation)
    folded.write_bytes(payload[:-1] + b" ")
    with pytest.raises(CaptureAttemptAuthorityError):
        authority._publish_exclusive(path, payload, parse_capture_attempt_allocation)
    (directory / "unexpected-entry").write_bytes(b"ignored")


def test_pointer_parent_identity_change_fails_closed(tmp_path: Path) -> None:
    root, _, _, session_id, _, _, _ = initialized_case(tmp_path)
    pointer_path = root / str(session_id) / "current-attempt-history.json"
    replacer = WindowsAtomicAttemptHistoryPointerReplacer()
    with pytest.raises(AtomicAttemptHistoryPointerReplacementError, match="parent"):
        replacer.replace(
            pointer_path,
            expected_payload=pointer_path.read_bytes(),
            replacement_payload=pointer_path.read_bytes(),
            parent_identity=(0, 0),
        )


def test_link_or_reparse_artifact_is_rejected_when_supported(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_bytes(b"payload")
    link = tmp_path / "link"
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are unavailable")
    with pytest.raises(CaptureAttemptAuthorityError):
        authority._safe_read(link)
