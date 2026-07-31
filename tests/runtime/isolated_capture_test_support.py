from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

from trading_bot.domain import Symbol
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data import (
    MAX_ALPACA_RESPONSE_BYTES,
    MAX_DAILY_SNAPSHOT_SYMBOLS,
    XNYS_CALENDAR_DESCRIPTOR,
    AdjustmentType,
    Timeframe,
)
from trading_bot.market_data.alpaca_daily_snapshot import (
    ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
)
from trading_bot.runtime.capture_attempt_authority import (
    CaptureAllocationClassification,
    create_capture_attempt_allocation,
    create_windows_market_data_credential_reference,
    serialize_capture_attempt_allocation,
    serialize_windows_market_data_credential_reference,
)
from trading_bot.runtime.isolated_capture_artifacts import (
    ISOLATED_CAPTURE_CHILD_OPERATION_VERSION,
    ISOLATED_CAPTURE_CURRENCY,
    ISOLATED_CAPTURE_FEED,
    ISOLATED_CAPTURE_PROVIDER_ID,
    create_isolated_capture_child_request,
    evidence_for_payload,
    serialize_isolated_capture_child_request,
)
from trading_bot.runtime.scheduled_readiness import (
    ArtifactEvidence,
    HeadRecordEvidence,
    TerminalCheckpointEvidence,
    derive_scheduled_capture_attempt_id,
)

REQUESTED_AT = datetime(2026, 1, 6, 15, 30, tzinfo=UTC)
TARGET_SESSION = TradingSession(date(2026, 1, 5))
OWNER_SID = "S-1-5-21-100-200-300-1001"


def evidence(label: str) -> ArtifactEvidence:
    digest = hashlib.sha256(label.encode("ascii")).digest()
    return ArtifactEvidence(
        UUID(bytes=digest[:16]),
        hashlib.sha256(label.encode("ascii")).hexdigest(),
        len(label),
    )


def install_child_case(root: Path):
    destination = root / "snapshots"
    destination.mkdir()
    credential = create_windows_market_data_credential_reference(
        owner_account_sid=OWNER_SID,
        api_key_id_target_name=("AITradingBot/AlpacaMarketData/v1/test/KeyId/1"),
        api_secret_key_target_name=(
            "AITradingBot/AlpacaMarketData/v1/test/SecretKey/1"
        ),
        credential_version="v1",
        permission_profile="read-only-market-data",
        permission_attestation_evidence=evidence("permission"),
        rotation_generation=0,
        reference_policy_version="credential-reference-v1",
    )
    credential_payload = serialize_windows_market_data_credential_reference(credential)
    credential_path = root / "credential-reference.json"
    credential_path.write_bytes(credential_payload)
    credential_evidence = evidence_for_payload(
        credential.credential_reference_id,
        credential_payload,
    )
    configuration_payload = (
        json.dumps(
            {
                "adjustment": "RAW",
                "calendar": {
                    "calendar_id": XNYS_CALENDAR_DESCRIPTOR.calendar_id,
                    "exchange_timezone": (XNYS_CALENDAR_DESCRIPTOR.exchange_timezone),
                    "version": XNYS_CALENDAR_DESCRIPTOR.version,
                },
                "provider": {
                    "adapter_version": (
                        ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.adapter_version
                    ),
                    "feed": ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.feed,
                    "operation": ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation,
                    "provider_id": ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id,
                },
                "request_id": "55555555-5555-5555-8555-555555555555",
                "schema_version": 1,
                "symbols": ["SPY", "QQQ"],
                "timeframe": "1D",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")
    configuration_path = root / "capture-config.json"
    configuration_path.write_bytes(configuration_payload)
    configuration_evidence = evidence_for_payload(
        UUID("66666666-6666-5666-8666-666666666666"),
        configuration_payload,
    )
    session_id = UUID("11111111-1111-5111-8111-111111111111")
    launch_id = UUID("22222222-2222-5222-8222-222222222222")
    epoch_id = UUID("33333333-3333-5333-8333-333333333333")
    symbols = (Symbol("SPY"), Symbol("QQQ"))
    attempt_id = derive_scheduled_capture_attempt_id(
        session_id,
        0,
        symbols,
        Timeframe.DAY_1,
        AdjustmentType.RAW,
        ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
        ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.feed,
        "USD",
        "capture-policy-v1",
        configuration_evidence,
    )
    allocation = create_capture_attempt_allocation(
        attempt_id=attempt_id,
        attempt_ordinal=0,
        scheduled_session_id=session_id,
        scheduled_launch_id=launch_id,
        authority_epoch_id=epoch_id,
        head_record=HeadRecordEvidence(epoch_id, evidence("head"), 0),
        verified_lineage_evidence_id=UUID("44444444-4444-5444-8444-444444444444"),
        terminal_checkpoint=TerminalCheckpointEvidence(
            evidence("checkpoint"),
            0,
            REQUESTED_AT,
        ),
        terminal_as_of=REQUESTED_AT,
        readiness_decision=evidence("decision"),
        market_hours_schedule=evidence("hours"),
        capture_policy=evidence("policy"),
        capture_policy_version="capture-policy-v1",
        capture_configuration=configuration_evidence,
        snapshot_capture_request_id=UUID("55555555-5555-5555-8555-555555555555"),
        target_session=TARGET_SESSION,
        request_timestamp_utc=REQUESTED_AT,
        symbols=symbols,
        timeframe=Timeframe.DAY_1,
        adjustment=AdjustmentType.RAW,
        provider=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
        feed=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.feed,
        currency="USD",
        credential_reference=credential_evidence,
        credential_reference_version=credential.credential_version,
        destination_reference=evidence("destination"),
        software_release=evidence("release"),
        observed_allocation_at=REQUESTED_AT,
        previous_attempt_history_head=evidence("history-head"),
        allocation_classification=(
            CaptureAllocationClassification.CAPTURE_ONLY_AUTHORIZED
        ),
        provider_call_budget=1,
        allocation_policy_version="allocation-policy-v1",
    )
    allocation_payload = serialize_capture_attempt_allocation(allocation)
    allocation_path = root / "allocation.json"
    allocation_path.write_bytes(allocation_payload)
    allocation_evidence = evidence_for_payload(
        allocation.allocation_record_id, allocation_payload
    )
    request = create_isolated_capture_child_request(
        allocation=allocation_evidence,
        allocation_path=allocation_path,
        attempt_id=allocation.attempt_id,
        attempt_ordinal=allocation.attempt_ordinal,
        scheduled_session_id=allocation.scheduled_session_id,
        scheduled_launch_id=allocation.scheduled_launch_id,
        credential_reference=credential_evidence,
        credential_reference_path=credential_path,
        snapshot_capture_request_id=allocation.snapshot_capture_request_id,
        capture_configuration=configuration_evidence,
        capture_configuration_path=configuration_path,
        symbols=symbols,
        calendar=XNYS_CALENDAR_DESCRIPTOR,
        timeframe=Timeframe.DAY_1,
        adjustment=AdjustmentType.RAW,
        provider_id=ISOLATED_CAPTURE_PROVIDER_ID,
        adapter_version=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.adapter_version,
        provider_operation=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation,
        feed=ISOLATED_CAPTURE_FEED,
        currency=ISOLATED_CAPTURE_CURRENCY,
        target_session=TARGET_SESSION,
        request_timestamp_utc=REQUESTED_AT,
        request_new_york_date=REQUESTED_AT.astimezone(
            ZoneInfo("America/New_York")
        ).date(),
        socket_timeout_seconds=15,
        wall_timeout_seconds=30,
        maximum_response_bytes=MAX_ALPACA_RESPONSE_BYTES,
        maximum_candidate_count=MAX_DAILY_SNAPSHOT_SYMBOLS,
        snapshot_destination_reference=allocation.destination_reference,
        snapshot_destination_path=destination,
        child_result_path=root / "child-result.json",
        software_release=allocation.software_release,
        child_operation_version=ISOLATED_CAPTURE_CHILD_OPERATION_VERSION,
    )
    request_payload = serialize_isolated_capture_child_request(request)
    request_path = root / "child-request.json"
    request_path.write_bytes(request_payload)
    return {
        "allocation": allocation,
        "credential": credential,
        "configuration_payload": configuration_payload,
        "request": request,
        "request_path": request_path,
        "request_payload": request_payload,
    }
