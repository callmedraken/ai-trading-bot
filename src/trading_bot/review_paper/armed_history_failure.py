"""D1R1 closed external history diagnostics; no retry or effect authority."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from datetime import date
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from trading_bot.market_data import (
    AlpacaResponseMetadataFailureReason,
    AlpacaTransportFailureStage,
)

MAX_HISTORY_FAILURE_BYTES = 4096


class HistoryFailureClassification(StrEnum):
    PROVIDER_CONSTRUCTION_FAILED = "PROVIDER_CONSTRUCTION_FAILED"
    TRANSPORT_FAILED = "TRANSPORT_FAILED"
    HTTP_FAILED = "HTTP_FAILED"
    PROVIDER_RESPONSE_INVALID = "PROVIDER_RESPONSE_INVALID"
    CAPTURE_OBSERVATION_REJECTED = "CAPTURE_OBSERVATION_REJECTED"
    SNAPSHOT_ACCEPTANCE_REJECTED = "SNAPSHOT_ACCEPTANCE_REJECTED"
    SNAPSHOT_VERIFICATION_REJECTED = "SNAPSHOT_VERIFICATION_REJECTED"
    VERIFIED_HISTORY_REJECTED = "VERIFIED_HISTORY_REJECTED"
    HISTORY_SEED_REJECTED = "HISTORY_SEED_REJECTED"
    INTERNAL_FAILED = "INTERNAL_FAILED"


@dataclass(frozen=True, slots=True)
class HistoryFailureDetails:
    history_session: date | None
    read_ordinal: int
    classification: HistoryFailureClassification
    transport_stage: AlpacaTransportFailureStage | None = None
    metadata_reason: AlpacaResponseMetadataFailureReason | None = None
    http_status: int | None = None
    provider_code: int | None = None

    def __post_init__(self) -> None:
        if type(self.classification) is not HistoryFailureClassification:
            raise ValueError("invalid history failure classification")
        if type(self.read_ordinal) is not int or not 0 <= self.read_ordinal <= 253:
            raise ValueError("invalid history read ordinal")
        if self.history_session is None:
            if self.read_ordinal != 0 or self.classification not in {
                HistoryFailureClassification.PROVIDER_CONSTRUCTION_FAILED,
                HistoryFailureClassification.INTERNAL_FAILED,
            }:
                raise ValueError("invalid unattributed failure")
        elif type(self.history_session) is not date or self.read_ordinal == 0:
            raise ValueError("invalid history session")
        if (
            self.classification
            is HistoryFailureClassification.PROVIDER_CONSTRUCTION_FAILED
        ):
            if self.history_session is not None or self.read_ordinal != 0:
                raise ValueError("invalid construction failure")
        if self.classification is HistoryFailureClassification.TRANSPORT_FAILED:
            if type(self.transport_stage) is not AlpacaTransportFailureStage:
                raise ValueError("invalid transport stage")
            if self.transport_stage is AlpacaTransportFailureStage.RESPONSE_METADATA:
                if (
                    type(self.metadata_reason)
                    is not AlpacaResponseMetadataFailureReason
                ):
                    raise ValueError("invalid metadata reason")
            elif self.metadata_reason is not None:
                raise ValueError("unexpected metadata reason")
        elif self.transport_stage is not None or self.metadata_reason is not None:
            raise ValueError("unexpected transport classification")
        if self.classification is HistoryFailureClassification.HTTP_FAILED:
            if self.http_status is not None and (
                type(self.http_status) is not int or not 100 <= self.http_status <= 599
            ):
                raise ValueError("invalid HTTP status")
            # Same numeric range as the reviewed Alpaca HTTP sanitizer.
            if self.provider_code is not None and (
                type(self.provider_code) is not int
                or not 0 <= self.provider_code <= (1 << 63) - 1
            ):
                raise ValueError("invalid provider code")
        elif self.http_status is not None or self.provider_code is not None:
            raise ValueError("unexpected HTTP material")


@dataclass(frozen=True, slots=True)
class ArmedHistoryFailureEvidence:
    schema: str
    source_head: str
    source_tree: str
    contract_id: UUID
    target_session: date
    operation_id: UUID
    history_session: date | None
    read_ordinal: int
    classification: HistoryFailureClassification
    transport_stage: AlpacaTransportFailureStage | None
    metadata_reason: AlpacaResponseMetadataFailureReason | None
    http_status: int | None
    provider_code: int | None
    alpaca_reads: int

    def __post_init__(self) -> None:
        if (
            type(self.schema) is not str
            or self.schema != "armed-paper-history-failure/v1"
        ):
            raise ValueError("invalid history failure schema")
        for value in (self.source_head, self.source_tree):
            if (
                type(value) is not str
                or len(value) != 40
                or any(c not in "0123456789abcdef" for c in value)
            ):
                raise ValueError("invalid source identity")
        if type(self.contract_id) is not UUID or type(self.operation_id) is not UUID:
            raise ValueError("invalid history failure identity")
        if type(self.target_session) is not date:
            raise ValueError("invalid target session")
        self.failure_details()
        if (
            self.history_session is not None
            and self.history_session >= self.target_session
        ):
            raise ValueError("history must precede target")
        if type(self.alpaca_reads) is not int or not 0 <= self.alpaca_reads <= 253:
            raise ValueError("invalid history attempt count")
        if (
            self.classification
            is HistoryFailureClassification.PROVIDER_CONSTRUCTION_FAILED
            and self.alpaca_reads != 0
        ):
            raise ValueError("construction cannot consume a read")
        if self.history_session is not None and self.alpaca_reads != self.read_ordinal:
            raise ValueError("failure ordinal differs from attempted reads")

    def failure_details(self) -> HistoryFailureDetails:
        return HistoryFailureDetails(
            self.history_session,
            self.read_ordinal,
            self.classification,
            self.transport_stage,
            self.metadata_reason,
            self.http_status,
            self.provider_code,
        )


def serialize_history_failure(value: ArmedHistoryFailureEvidence) -> bytes:
    if type(value) is not ArmedHistoryFailureEvidence:
        raise ValueError("exact history failure evidence required")
    value.__post_init__()
    material = asdict(value)
    for name in ("contract_id", "operation_id", "target_session", "history_session"):
        item = material[name]
        material[name] = (
            None
            if item is None
            else item.isoformat()
            if type(item) is date
            else str(item)
        )
    payload = (
        json.dumps(material, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    if len(payload) > MAX_HISTORY_FAILURE_BYTES:
        raise ValueError("history failure evidence exceeds bound")
    return payload


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate history failure field")
        result[key] = value
    return result


def parse_history_failure(payload: bytes) -> ArmedHistoryFailureEvidence:
    if type(payload) is not bytes or len(payload) > MAX_HISTORY_FAILURE_BYTES:
        raise ValueError("invalid history failure bytes")
    try:
        value = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object)
        if type(value) is not dict or set(value) != {
            field.name for field in fields(ArmedHistoryFailureEvidence)
        }:
            raise ValueError("invalid history failure fields")
        for name in ("contract_id", "operation_id"):
            if type(value[name]) is not str:
                raise ValueError("invalid identity")
            value[name] = UUID(value[name])
        for name in ("target_session", "history_session"):
            if value[name] is not None:
                if type(value[name]) is not str:
                    raise ValueError("invalid date")
                value[name] = date.fromisoformat(value[name])
        value["classification"] = HistoryFailureClassification(value["classification"])
        for name, kind in (
            ("transport_stage", AlpacaTransportFailureStage),
            ("metadata_reason", AlpacaResponseMetadataFailureReason),
        ):
            if value[name] is not None:
                value[name] = kind(value[name])
        evidence = ArmedHistoryFailureEvidence(**value)
        if serialize_history_failure(evidence) != payload:
            raise ValueError("noncanonical history failure bytes")
        return evidence
    except Exception:
        # Never retain parser input or raw exception text in the public error.
        pass
    raise ValueError("invalid canonical history failure evidence") from None


def history_failure_path(session_evidence: Path) -> Path:
    return session_evidence.with_name(session_evidence.name + ".history-failure.json")


def write_history_failure(path: Path, evidence: ArmedHistoryFailureEvidence) -> None:
    payload = serialize_history_failure(evidence)
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
