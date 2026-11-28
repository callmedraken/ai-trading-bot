"""Native SEC plan, bounded parser, custody model, and synthetic test harness.

This module has no network transport. The separately loaded real SEC boundary
is not imported by application startup, source admission, pytest, or CI. A
parsed result remains blocked and never becomes PM2C evidence while public
availability and security-identity witnesses are unproven.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import stat
import subprocess
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path
from typing import Protocol, runtime_checkable
from urllib.parse import urlsplit
from uuid import UUID, uuid5

from trading_bot.domain._validation import normalize_utc

_GIT_ID = re.compile(r"^[0-9a-f]{40}$")
_CIK = re.compile(r"^[0-9]{10}$")
_ACCESSION = re.compile(r"^[0-9]{10}-[0-9]{2}-[0-9]{6}$")
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}\.xml$")
_DECIMAL = re.compile(r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[Ee][+-]?[0-9]+)?$")
_MAX_DECIMAL_CHARS = 128
_MAX_ABS_DECIMAL_EXPONENT = 100
_XBRLI = "http://www.xbrl.org/2003/instance"
_XBRLDI = "http://xbrl.org/2006/xbrldi"
_ISO4217 = "http://www.xbrl.org/2003/iso4217"
_XSI = "http://www.w3.org/2001/XMLSchema-instance"
_XI = "http://www.w3.org/2001/XInclude"
_REVENUE_CONCEPT = "RevenueFromContractWithCustomerExcludingAssessedTax"
_MAX_RESPONSE_BYTES = 10_000_000
_MAX_FILING_MEMBERS = 200
_MAX_XML_ELEMENTS = 100_000
_MAX_REVENUE_FACT_CANDIDATES = 10_000
_MAX_REQUEST_TIMEOUT = 10
_MAX_TOTAL_SECONDS = 30
_EVIDENCE_ROOT = r"F:\AI\temp"
_SEC_OBSERVATION_DIRECTORY = "pm2d-b1-sec-observations"
_SEC_ATTEMPT_NAMESPACE = UUID("d4b3de7a-3bd5-5b21-b96d-0ae85d0f5584")
_MAX_AUTHORITY_RECORD_BYTES = 128_000
_PREPUBLICATION_ADMISSION_SCHEMA = "ai-trading-bot-checkpoint-runner/v1"
_PREPUBLICATION_ADMISSION_NAME = "arch132-r3n-prepublication-admission"
_EXPECTED_WORKTREE = Path(r"F:\AI\worktrees\ai-trading-bot-portfolio-manager-current")
_EXPECTED_BRANCH = "feature/robinhood-portfolio-manager-current"
_EXPECTED_ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"


class SECObservationError(ValueError):
    """A fixed, non-provider-specific native-input or plan error."""


class SECObservationOutcome(StrEnum):
    SOURCE_ADMISSION_FAILED = "SOURCE_ADMISSION_FAILED"
    EFFECT_AUTHORIZATION_FAILED = "EFFECT_AUTHORIZATION_FAILED"
    ATTEMPT_CONSUMED = "ATTEMPT_CONSUMED"
    EVIDENCE_WRITE_FAILED = "EVIDENCE_WRITE_FAILED"
    PROVIDER_FAILED = "PROVIDER_FAILED"
    RESPONSE_REJECTED = "RESPONSE_REJECTED"
    NATIVE_DOCUMENT_UNSUPPORTED = "NATIVE_DOCUMENT_UNSUPPORTED"
    SEC_FACT_MISSING = "SEC_FACT_MISSING"
    SEC_FACT_CONFLICTED = "SEC_FACT_CONFLICTED"
    SEC_FACT_CONTEXT_MISMATCH = "SEC_FACT_CONTEXT_MISMATCH"
    SEC_OBSERVATION_BLOCKED = "SEC_OBSERVATION_BLOCKED"


@dataclass(frozen=True, slots=True)
class SECObservationPlan:
    """Immutable plan for exactly one annual USD revenue fact.

    The single SEC request is the complete submission text, which embeds the
    exact ``EX-101.INS`` instance document. No current public SEC route has
    been accepted as an adequate historical availability witness.
    """

    attempt_id: UUID
    expected_source_head: str
    expected_source_tree: str
    issuer_cik: str
    accession: str
    filing_form: str
    document_name: str
    document_sequence: str
    fiscal_year: int
    period_start: date
    period_end: date
    context_id: str
    entity_identifier_scheme: str
    concept_namespace: str
    concept_local_name: str
    unit_id: str
    unit_namespace: str
    unit_local_name: str
    dimensions: tuple[tuple[tuple[str, str], tuple[str, str]], ...]
    user_agent: str
    evidence_root: str
    max_response_bytes: int = _MAX_RESPONSE_BYTES
    max_filing_members: int = _MAX_FILING_MEMBERS
    max_xml_elements: int = _MAX_XML_ELEMENTS
    request_timeout_seconds: int = _MAX_REQUEST_TIMEOUT
    total_time_limit_seconds: int = _MAX_TOTAL_SECONDS
    automatic_retry: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.attempt_id, UUID):
            raise TypeError("attempt_id must be UUID")
        for name in ("expected_source_head", "expected_source_tree"):
            value = getattr(self, name)
            if not isinstance(value, str) or not _GIT_ID.fullmatch(value):
                raise ValueError(f"{name} must be a lowercase 40-character Git ID")
        if not isinstance(self.issuer_cik, str) or not _CIK.fullmatch(self.issuer_cik):
            raise ValueError("issuer_cik must be an exact 10-digit CIK")
        if not isinstance(self.accession, str) or not _ACCESSION.fullmatch(
            self.accession
        ):
            raise ValueError("accession must be an exact dashed EDGAR accession")
        if self.filing_form != "10-K":
            raise ValueError("only an original annual 10-K is supported")
        if not isinstance(self.document_name, str) or not _FILENAME.fullmatch(
            self.document_name
        ):
            raise ValueError("document_name must be one exact XML member name")
        if type(self.period_start) is not date or type(self.period_end) is not date:
            raise TypeError("period bounds must be dates")
        if (
            isinstance(self.fiscal_year, bool)
            or not isinstance(self.fiscal_year, int)
            or self.fiscal_year != self.period_end.year
        ):
            raise ValueError("fiscal_year must match the exact annual period end")
        duration = (self.period_end - self.period_start).days
        if duration < 330 or duration > 400:
            raise ValueError("the selected duration is outside the annual bound")
        for name in ("context_id", "unit_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not _TOKEN.fullmatch(value):
                raise ValueError(f"{name} is not a safe exact identifier")
        if (
            self.concept_local_name != _REVENUE_CONCEPT
            or not _safe_namespace(self.concept_namespace)
            or "/us-gaap/" not in self.concept_namespace
        ):
            raise ValueError(
                "only the frozen US-GAAP annual revenue concept is supported"
            )
        if (
            self.entity_identifier_scheme != "http://www.sec.gov/CIK"
            or self.unit_namespace != _ISO4217
            or self.unit_local_name != "USD"
        ):
            raise ValueError("the exact SEC CIK and USD unit binding is required")
        if (
            not isinstance(self.user_agent, str)
            or "\r" in self.user_agent
            or "\n" in self.user_agent
            or "@" not in self.user_agent
            or len(self.user_agent) > 200
        ):
            raise ValueError("user_agent must be a bounded declared contact string")
        if not _under_external_evidence_root(self.evidence_root):
            raise ValueError("evidence_root must be below F:\\AI\\temp")
        if (
            isinstance(self.max_response_bytes, bool)
            or not isinstance(self.max_response_bytes, int)
            or self.max_response_bytes <= 0
            or self.max_response_bytes > _MAX_RESPONSE_BYTES
        ):
            raise ValueError("max_response_bytes exceeds the reviewed ceiling")
        if (
            isinstance(self.max_filing_members, bool)
            or not isinstance(self.max_filing_members, int)
            or self.max_filing_members <= 0
            or self.max_filing_members > _MAX_FILING_MEMBERS
        ):
            raise ValueError("max_filing_members exceeds the reviewed ceiling")
        if (
            not isinstance(self.document_sequence, str)
            or not re.fullmatch(r"[1-9][0-9]{0,2}", self.document_sequence)
            or int(self.document_sequence) > self.max_filing_members
        ):
            raise ValueError("document_sequence must identify one bounded member")
        if (
            isinstance(self.max_xml_elements, bool)
            or not isinstance(self.max_xml_elements, int)
            or self.max_xml_elements <= 0
            or self.max_xml_elements > _MAX_XML_ELEMENTS
        ):
            raise ValueError("max_xml_elements exceeds the reviewed ceiling")
        if (
            isinstance(self.request_timeout_seconds, bool)
            or not isinstance(self.request_timeout_seconds, int)
            or not 1 <= self.request_timeout_seconds <= _MAX_REQUEST_TIMEOUT
        ):
            raise ValueError("request timeout exceeds the reviewed ceiling")
        if (
            isinstance(self.total_time_limit_seconds, bool)
            or not isinstance(self.total_time_limit_seconds, int)
            or not 1 <= self.total_time_limit_seconds <= _MAX_TOTAL_SECONDS
        ):
            raise ValueError("total time limit exceeds the reviewed ceiling")
        if self.automatic_retry is not False:
            raise ValueError("automatic_retry must remain false")
        if not isinstance(self.dimensions, tuple):
            raise TypeError("dimensions must be a tuple")
        axes = []
        for axis, member in self.dimensions:
            if not _qname_pair(axis) or not _qname_pair(member):
                raise ValueError("dimensions must contain exact expanded QNames")
            axes.append(axis)
        if len(axes) != len(set(axes)):
            raise ValueError("dimension axes must be unique")

    @property
    def accession_compact(self) -> str:
        return self.accession.replace("-", "")

    @property
    def base_url(self) -> str:
        cik_path = str(int(self.issuer_cik))
        return (
            "https://www.sec.gov/Archives/edgar/data/"
            f"{cik_path}/{self.accession_compact}"
        )

    @property
    def submission_url(self) -> str:
        return f"{self.base_url}/{self.accession}.txt"

    @property
    def plan_id(self) -> str:
        body = json.dumps(self.to_manifest(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    def source_matches(self, head: str, tree: str) -> bool:
        return head == self.expected_source_head and tree == self.expected_source_tree

    def to_manifest(self) -> dict[str, object]:
        return {
            "schema": "pm2d-b1-r-sec-observation-plan/v1",
            "attempt_id": str(self.attempt_id),
            "expected_source_head": self.expected_source_head,
            "expected_source_tree": self.expected_source_tree,
            "issuer_cik": self.issuer_cik,
            "accession": self.accession,
            "filing_form": self.filing_form,
            "document_name": self.document_name,
            "document_sequence": self.document_sequence,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "fiscal_year": self.fiscal_year,
            "context_id": self.context_id,
            "entity_identifier_scheme": self.entity_identifier_scheme,
            "concept_namespace": self.concept_namespace,
            "concept_local_name": self.concept_local_name,
            "dimensions": [
                {"axis": list(axis), "member": list(member)}
                for axis, member in self.dimensions
            ],
            "unit_id": self.unit_id,
            "unit_namespace": self.unit_namespace,
            "unit_local_name": self.unit_local_name,
            "currency": "USD",
            "scale": 0,
            "request_method": "GET",
            "accept_header": "text/plain",
            "submission_url": self.submission_url,
            "public_availability_witness": "UNPROVEN",
            "requested_endpoints": [self.submission_url],
            "request_parameters": [],
            "max_request_attempts": 1,
            "max_document_responses": 1,
            "max_filing_members": self.max_filing_members,
            "max_xml_elements": self.max_xml_elements,
            "max_revenue_fact_candidates": _MAX_REVENUE_FACT_CANDIDATES,
            "max_response_bytes_each": self.max_response_bytes,
            "max_total_response_bytes": self.max_response_bytes,
            "request_timeout_seconds": self.request_timeout_seconds,
            "total_time_limit_seconds": self.total_time_limit_seconds,
            "user_agent_sha256": hashlib.sha256(
                self.user_agent.encode("utf-8")
            ).hexdigest(),
            "user_agent": self.user_agent,
            "evidence_root": self.evidence_root,
            "retention": (
                "create-once raw SEC responses and terminal record "
                "under the external evidence root"
            ),
            "automatic_retry": False,
        }


def sec_observation_evidence_root() -> Path:
    """Return the one production custody root below the external temp root."""

    return Path(_EVIDENCE_ROOT) / _SEC_OBSERVATION_DIRECTORY


def canonical_sec_attempt_id(plan: SECObservationPlan) -> UUID:
    """Bind one non-reusable attempt ID to source and selected fact identity.

    Evidence paths, request limits, and presentation details are intentionally
    excluded so they cannot create a new attempt for the same source fact.
    """

    material = {
        "schema": "pm2d-b1-r-sec-attempt/v1",
        "source_head": plan.expected_source_head,
        "source_tree": plan.expected_source_tree,
        "issuer_cik": plan.issuer_cik,
        "accession": plan.accession,
        "filing_form": plan.filing_form,
        "document_name": plan.document_name,
        "document_sequence": plan.document_sequence,
        "fiscal_year": plan.fiscal_year,
        "period_start": plan.period_start.isoformat(),
        "period_end": plan.period_end.isoformat(),
        "concept_namespace": plan.concept_namespace,
        "concept_local_name": plan.concept_local_name,
        "unit_namespace": plan.unit_namespace,
        "unit_local_name": plan.unit_local_name,
    }
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return uuid5(_SEC_ATTEMPT_NAMESPACE, canonical)


@dataclass(frozen=True, slots=True)
class SECSourceAdmission:
    """Recorded general admission result for the exact plan source."""

    source_head: str
    source_tree: str
    feature: str
    prospective_develop: str
    evidence_sha256: str
    evidence_path: str | None = None
    evidence_bytes: bytes | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not _GIT_ID.fullmatch(self.source_head) or not _GIT_ID.fullmatch(
            self.source_tree
        ):
            raise ValueError("admission must bind exact Git identities")
        if self.feature != "PASS" or self.prospective_develop != "PASS":
            raise ValueError("both FEATURE and PROSPECTIVE_DEVELOP must pass")
        if not re.fullmatch(r"[0-9a-f]{64}", self.evidence_sha256):
            raise ValueError("admission evidence must be SHA-256 bound")
        if self.evidence_path is not None and not isinstance(self.evidence_path, str):
            raise TypeError("evidence_path must be a string when present")
        if self.evidence_bytes is not None and (
            not isinstance(self.evidence_bytes, bytes)
            or hashlib.sha256(self.evidence_bytes).hexdigest() != self.evidence_sha256
        ):
            raise ValueError("admission bytes must match their exact SHA-256")


@dataclass(frozen=True, slots=True)
class SECObservationAuthorization:
    """Separate, exact-bound effect grant; source admission does not create it."""

    authorization_id: str
    approved_plan_id: str
    approved_source_head: str
    approved_source_tree: str
    approved_attempt_id: UUID
    review_record_sha256: str
    issued_at: datetime
    expires_at: datetime
    max_request_attempts: int = 1
    source_admission_sha256: str | None = None
    authorization_record_path: str | None = None
    authorization_record_bytes: bytes | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        for name in ("authorization_id",):
            if not _TOKEN.fullmatch(getattr(self, name)):
                raise ValueError(f"{name} must be a safe opaque ID")
        if not re.fullmatch(r"[0-9a-f]{64}", self.approved_plan_id):
            raise ValueError("approved_plan_id must be the exact plan digest")
        if not _GIT_ID.fullmatch(self.approved_source_head) or not _GIT_ID.fullmatch(
            self.approved_source_tree
        ):
            raise ValueError("authorization must bind exact Git identities")
        if not isinstance(self.approved_attempt_id, UUID):
            raise TypeError("approved_attempt_id must be UUID")
        if not re.fullmatch(r"[0-9a-f]{64}", self.review_record_sha256):
            raise ValueError("review_record_sha256 must be SHA-256")
        if self.source_admission_sha256 is not None and not re.fullmatch(
            r"[0-9a-f]{64}", self.source_admission_sha256
        ):
            raise ValueError("source_admission_sha256 must be SHA-256")
        if self.authorization_record_path is not None and not isinstance(
            self.authorization_record_path, str
        ):
            raise TypeError("authorization_record_path must be a string when present")
        if self.authorization_record_bytes is not None and (
            not isinstance(self.authorization_record_bytes, bytes)
            or hashlib.sha256(self.authorization_record_bytes).hexdigest()
            != self.review_record_sha256
        ):
            raise ValueError("authorization bytes must match their exact SHA-256")
        issued = normalize_utc(self.issued_at, "issued_at")
        expires = normalize_utc(self.expires_at, "expires_at")
        if expires <= issued or expires - issued > timedelta(hours=1):
            raise ValueError(
                "authorization window must be positive and at most one hour"
            )
        object.__setattr__(self, "issued_at", issued)
        object.__setattr__(self, "expires_at", expires)
        if self.max_request_attempts != 1:
            raise ValueError("authorization must allow exactly one planned request")

    def matches(self, plan: SECObservationPlan, now: datetime) -> bool:
        now = normalize_utc(now, "authorization check time")
        return (
            self.approved_plan_id == plan.plan_id
            and self.approved_source_head == plan.expected_source_head
            and self.approved_source_tree == plan.expected_source_tree
            and self.approved_attempt_id == plan.attempt_id
            and self.issued_at <= now <= self.expires_at
        )


@dataclass(frozen=True, slots=True)
class SECSubmission:
    issuer_cik: str
    accession: str
    form: str
    filing_date: date
    report_period: date
    accepted_timestamp_raw: str
    document_type: str
    document_name: str
    document_sequence: str
    content_sha256: str
    content_length: int
    embedded_document_range: tuple[int, int]
    embedded_document_sha256: str
    embedded_document_length: int
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class SECRevenueFact:
    accession: str
    document_name: str
    namespace: str
    concept: str
    context_id: str
    issuer_cik: str
    period_start: date
    period_end: date
    dimensions: tuple[tuple[tuple[str, str], tuple[str, str]], ...]
    unit_id: str
    unit_namespace: str
    unit_local_name: str
    currency: str
    scale: int
    decimals: str | None
    signed_decimal_value: Decimal
    source_record_id: str


@dataclass(frozen=True, slots=True)
class SECTransportResponse:
    status_code: int
    content_type: str
    body: bytes
    final_url: str
    received_at: datetime | None = None


@runtime_checkable
class SECTransport(Protocol):
    def get(
        self,
        url: str,
        *,
        user_agent: str,
        timeout_seconds: int,
        total_time_limit_seconds: float,
        max_bytes: int,
    ) -> SECTransportResponse: ...


@runtime_checkable
class SECEvidenceStore(Protocol):
    def reserve_attempt(self, plan: SECObservationPlan) -> bool: ...

    def write_request_intent(
        self, ordinal: int, material: Mapping[str, object]
    ) -> None: ...

    def write_response(
        self,
        ordinal: int,
        label: str,
        body: bytes,
        content_type: str,
        *,
        received_at: datetime | None = None,
    ) -> str: ...

    def write_terminal(self, material: Mapping[str, object]) -> None: ...


@dataclass(frozen=True, slots=True)
class SECObservationCounters:
    provider_invocations: int = 0
    request_intents: int = 0
    response_documents: int = 0
    response_bytes: int = 0
    response_bytes_received: int = 0
    xbrl_records: int = 0
    credential_reads: int = 0
    account_reads: int = 0
    ai_calls: int = 0
    broker_effects: int = 0
    production_mutations: int = 0


@dataclass(frozen=True, slots=True)
class SECObservationResult:
    outcome: SECObservationOutcome
    reason_code: str
    plan_id: str
    source_head: str
    source_tree: str
    counters: SECObservationCounters
    submission: SECSubmission | None = None
    fact: SECRevenueFact | None = None
    response_sha256: tuple[str, ...] = ()
    source_fact_created: bool = False
    public_availability_witness: str = "UNPROVEN"
    security_identity_witness: str = "UNPROVEN"


class SECNativeInputError(SECObservationError):
    def __init__(self, code: SECObservationOutcome, reason_code: str) -> None:
        super().__init__(reason_code)
        self.code = code
        self.reason_code = reason_code


def parse_sec_submission(
    raw_bytes: bytes,
    plan: SECObservationPlan,
    observed_at: datetime,
) -> SECSubmission:
    """Parse the exact SEC complete-submission header and one member binding."""

    _require_response_bytes(raw_bytes, plan.max_response_bytes, "submission")
    header_start = raw_bytes.find(b"<SEC-HEADER>")
    header_end = raw_bytes.find(b"</SEC-HEADER>", header_start + 1)
    if header_start < 0 or header_end < 0:
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            "SEC_HEADER_SHAPE_UNSUPPORTED",
        )
    header_bytes = raw_bytes[header_start + len(b"<SEC-HEADER>") : header_end]
    try:
        header = header_bytes.decode("ascii", errors="strict")
    except UnicodeDecodeError:
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            "SEC_HEADER_ENCODING_UNSUPPORTED",
        ) from None

    accession = _header_value(header, "ACCESSION NUMBER")
    form = _header_value(header, "CONFORMED SUBMISSION TYPE")
    filed = _header_value(header, "FILED AS OF DATE")
    period = _header_value(header, "CONFORMED PERIOD OF REPORT")
    cik_values = re.findall(r"(?im)^\s*CENTRAL INDEX KEY:\s*([0-9]{10})\s*$", header)
    accepted_values = re.findall(
        rb"(?im)^\s*<ACCEPTANCE-DATETIME>([0-9]{14})\s*$", raw_bytes
    )
    if (
        accession != plan.accession
        or form != plan.filing_form
        or cik_values != [plan.issuer_cik]
        or not accepted_values
        or not re.fullmatch(r"[0-9]{8}", filed)
        or not re.fullmatch(r"[0-9]{8}", period)
        or period != plan.period_end.strftime("%Y%m%d")
    ):
        raise SECNativeInputError(
            SECObservationOutcome.SEC_FACT_CONTEXT_MISMATCH,
            "SEC_SUBMISSION_IDENTITY_MISMATCH",
        )
    if len(accepted_values) != 1:
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            "SEC_ACCEPTANCE_TIMESTAMP_MISSING_OR_DUPLICATE",
        )
    accepted_raw = accepted_values[0].decode("ascii")
    try:
        datetime.strptime(accepted_raw, "%Y%m%d%H%M%S")
    except ValueError:
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            "SEC_ACCEPTANCE_TIMESTAMP_INVALID",
        ) from None
    member_count = raw_bytes.count(b"<DOCUMENT>")
    if member_count <= 0 or member_count > plan.max_filing_members:
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            "SEC_FILING_MEMBER_LIMIT_OR_SHAPE",
        )
    filename_entries = tuple(
        re.finditer(rb"(?m)^<FILENAME>[ \t]*([^\r\n]*)\r?$", raw_bytes)
    )
    expected_name = plan.document_name.encode("ascii")
    exact_filename_entries = tuple(
        item for item in filename_entries if item.group(1).strip() == expected_name
    )
    if len(exact_filename_entries) != 1:
        raise SECNativeInputError(
            SECObservationOutcome.SEC_FACT_CONTEXT_MISMATCH,
            "SEC_DOCUMENT_NAME_MISSING_OR_DUPLICATE",
        )
    filename_at = exact_filename_entries[0].start()
    document_start = raw_bytes.rfind(b"<DOCUMENT>", 0, filename_at)
    text_start = raw_bytes.find(b"<TEXT>", filename_at)
    next_document = raw_bytes.find(b"<DOCUMENT>", filename_at)
    if (
        document_start < 0
        or text_start < 0
        or (next_document >= 0 and next_document < text_start)
    ):
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            "SEC_DOCUMENT_BLOCK_UNSUPPORTED",
        )
    document_header = raw_bytes[document_start:text_start]
    type_values = re.findall(rb"(?m)^<TYPE>([^\r\n<]+)", document_header)
    sequence_values = re.findall(rb"(?m)^<SEQUENCE>([0-9]+)", document_header)
    if len(type_values) != 1 or len(sequence_values) != 1:
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            "SEC_DOCUMENT_METADATA_UNSUPPORTED",
        )
    try:
        document_type = type_values[0].decode("ascii", errors="strict").strip()
    except UnicodeDecodeError:
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            "SEC_DOCUMENT_TYPE_ENCODING_UNSUPPORTED",
        ) from None
    if document_type != "EX-101.INS":
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            "SEC_DOCUMENT_TYPE_UNSUPPORTED",
        )
    document_sequence = sequence_values[0].decode("ascii")
    if document_sequence != plan.document_sequence:
        raise SECNativeInputError(
            SECObservationOutcome.SEC_FACT_CONTEXT_MISMATCH,
            "SEC_DOCUMENT_SEQUENCE_MISMATCH",
        )
    text_body_start = text_start + len(b"<TEXT>")
    text_body_end = raw_bytes.find(b"</TEXT>", text_body_start)
    document_end = raw_bytes.find(b"</DOCUMENT>", text_body_start)
    if text_body_end < 0 or document_end < text_body_end:
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            "SEC_DOCUMENT_TEXT_BLOCK_UNSUPPORTED",
        )
    if raw_bytes[text_body_start : text_body_start + 2] == b"\r\n":
        text_body_start += 2
    elif raw_bytes[text_body_start : text_body_start + 1] in {b"\r", b"\n"}:
        text_body_start += 1
    if raw_bytes[text_body_end - 2 : text_body_end] == b"\r\n":
        text_body_end -= 2
    elif raw_bytes[text_body_end - 1 : text_body_end] in {b"\r", b"\n"}:
        text_body_end -= 1
    embedded = raw_bytes[text_body_start:text_body_end]
    return SECSubmission(
        issuer_cik=plan.issuer_cik,
        accession=accession,
        form=form,
        filing_date=_parse_yyyymmdd(filed, "FILED AS OF DATE"),
        report_period=_parse_yyyymmdd(period, "CONFORMED PERIOD OF REPORT"),
        accepted_timestamp_raw=accepted_raw,
        document_type=document_type,
        document_name=plan.document_name,
        document_sequence=document_sequence,
        content_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        content_length=len(raw_bytes),
        embedded_document_range=(text_body_start, text_body_end),
        embedded_document_sha256=hashlib.sha256(embedded).hexdigest(),
        embedded_document_length=len(embedded),
        observed_at=normalize_utc(observed_at, "observed_at"),
    )


def extract_sec_submission_member(raw_bytes: bytes, submission: SECSubmission) -> bytes:
    """Verify and extract the exact embedded document recorded by its parent."""

    if not isinstance(raw_bytes, bytes) or type(submission) is not SECSubmission:
        raise TypeError("exact submission bytes and SECSubmission are required")
    start, end = submission.embedded_document_range
    if (
        submission.content_length != len(raw_bytes)
        or submission.content_sha256 != hashlib.sha256(raw_bytes).hexdigest()
        or isinstance(start, bool)
        or isinstance(end, bool)
        or not isinstance(start, int)
        or not isinstance(end, int)
        or start < 0
        or end <= start
        or end > len(raw_bytes)
    ):
        raise SECNativeInputError(
            SECObservationOutcome.SEC_FACT_CONTEXT_MISMATCH,
            "SEC_PARENT_SUBMISSION_IDENTITY_MISMATCH",
        )
    embedded = raw_bytes[start:end]
    if (
        len(embedded) != submission.embedded_document_length
        or hashlib.sha256(embedded).hexdigest() != submission.embedded_document_sha256
    ):
        raise SECNativeInputError(
            SECObservationOutcome.SEC_FACT_CONTEXT_MISMATCH,
            "SEC_EMBEDDED_DOCUMENT_DIGEST_OR_RANGE_MISMATCH",
        )
    return embedded


def parse_native_xbrl_revenue(
    raw_bytes: bytes,
    plan: SECObservationPlan,
    submission: SECSubmission,
) -> SECRevenueFact:
    """Parse one strict native XBRL instance; never dereference external links."""

    _require_response_bytes(raw_bytes, plan.max_response_bytes, "instance")
    if (
        submission.accession != plan.accession
        or submission.document_name != plan.document_name
    ):
        raise SECNativeInputError(
            SECObservationOutcome.SEC_FACT_CONTEXT_MISMATCH,
            "SEC_INSTANCE_BINDING_MISMATCH",
        )
    try:
        xml_text = raw_bytes.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            "NATIVE_XBRL_ENCODING_UNSUPPORTED",
        ) from None
    upper = xml_text.upper()
    if "<!DOCTYPE" in upper or "<!ENTITY" in upper:
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            "XML_DTD_OR_ENTITY_REJECTED",
        )
    namespace_map: dict[str, str] = {}
    try:
        element_count = 0
        for event, item in ET.iterparse(
            io.BytesIO(raw_bytes), events=("start-ns", "start")
        ):
            if event == "start":
                element_count += 1
                if element_count > plan.max_xml_elements:
                    raise SECNativeInputError(
                        SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
                        "XBRL_ELEMENT_LIMIT_REACHED",
                    )
                continue
            prefix, namespace = item
            prefix = prefix or ""
            previous = namespace_map.get(prefix)
            if previous is not None and previous != namespace:
                raise SECNativeInputError(
                    SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
                    "XML_NAMESPACE_REBINDING_UNSUPPORTED",
                )
            namespace_map[prefix] = namespace
        root = ET.fromstring(raw_bytes)
    except SECNativeInputError:
        raise
    except (ET.ParseError, ValueError, OSError):
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            "NATIVE_XBRL_XML_UNSUPPORTED",
        ) from None
    if root.tag != f"{{{_XBRLI}}}xbrl":
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            "NATIVE_XBRL_ROOT_UNSUPPORTED",
        )
    elements = tuple(root.iter())
    for element in elements:
        if isinstance(element.tag, str) and element.tag.startswith(f"{{{_XI}}}"):
            raise SECNativeInputError(
                SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
                "XML_EXTERNAL_INCLUDE_REJECTED",
            )
        if "{http://www.w3.org/1999/xlink}href" in element.attrib:
            if element.tag != "{http://www.xbrl.org/2003/linkbase}schemaRef":
                raise SECNativeInputError(
                    SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
                    "XML_EXTERNAL_REFERENCE_REJECTED",
                )

    contexts = _parse_contexts(root, namespace_map)
    units = _parse_units(root, namespace_map)
    expected_tag = f"{{{plan.concept_namespace}}}{plan.concept_local_name}"
    candidates = [item for item in root if item.tag == expected_tag]
    if not candidates:
        raise SECNativeInputError(
            SECObservationOutcome.SEC_FACT_MISSING, "SEC_REVENUE_FACT_MISSING"
        )
    if len(candidates) > _MAX_REVENUE_FACT_CANDIDATES:
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            "SEC_REVENUE_FACT_LIMIT_REACHED",
        )
    matches = [
        item for item in candidates if item.attrib.get("contextRef") == plan.context_id
    ]
    if not matches:
        raise SECNativeInputError(
            SECObservationOutcome.SEC_FACT_CONTEXT_MISMATCH,
            "SEC_REVENUE_CONTEXT_MISMATCH",
        )
    if len(matches) != 1:
        raise SECNativeInputError(
            SECObservationOutcome.SEC_FACT_CONFLICTED,
            "SEC_REVENUE_DUPLICATE_FACTS",
        )
    fact_element = matches[0]
    if fact_element.attrib.get(f"{{{_XSI}}}nil", "false").lower() == "true":
        raise SECNativeInputError(
            SECObservationOutcome.SEC_FACT_MISSING, "SEC_REVENUE_FACT_NIL"
        )
    if "scale" in fact_element.attrib:
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            "INLINE_XBRL_SCALE_ATTRIBUTE_UNSUPPORTED",
        )
    context = contexts.get(plan.context_id)
    if context is None:
        raise SECNativeInputError(
            SECObservationOutcome.SEC_FACT_CONTEXT_MISMATCH,
            "SEC_REVENUE_CONTEXT_MISSING",
        )
    context_cik, period_start, period_end, dimensions = context
    if (
        context_cik != plan.issuer_cik
        or period_start != plan.period_start
        or period_end != plan.period_end
        or dimensions != tuple(sorted(plan.dimensions))
        or submission.report_period != plan.period_end
    ):
        raise SECNativeInputError(
            SECObservationOutcome.SEC_FACT_CONTEXT_MISMATCH,
            "SEC_REVENUE_GRAIN_OR_ISSUER_MISMATCH",
        )
    unit_ref = fact_element.attrib.get("unitRef")
    if unit_ref != plan.unit_id or unit_ref not in units:
        raise SECNativeInputError(
            SECObservationOutcome.SEC_FACT_CONTEXT_MISMATCH,
            "SEC_REVENUE_UNIT_REFERENCE_MISMATCH",
        )
    unit_namespace, unit_local = units[unit_ref]
    if unit_namespace != plan.unit_namespace or unit_local != plan.unit_local_name:
        raise SECNativeInputError(
            SECObservationOutcome.SEC_FACT_CONTEXT_MISMATCH,
            "SEC_REVENUE_UNIT_OR_CURRENCY_MISMATCH",
        )
    lexical = (fact_element.text or "").strip()
    if len(lexical) > _MAX_DECIMAL_CHARS or not _DECIMAL.fullmatch(lexical):
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            "SEC_REVENUE_DECIMAL_LEXICAL_UNSUPPORTED",
        )
    try:
        value = Decimal(lexical)
    except InvalidOperation:
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            "SEC_REVENUE_DECIMAL_INVALID",
        ) from None
    if not value.is_finite():
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            "SEC_REVENUE_DECIMAL_NONFINITE",
        )
    if (
        len(value.as_tuple().digits) > _MAX_DECIMAL_CHARS
        or abs(value.as_tuple().exponent) > _MAX_ABS_DECIMAL_EXPONENT
        or abs(value.adjusted()) > _MAX_ABS_DECIMAL_EXPONENT
    ):
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            "SEC_REVENUE_DECIMAL_MAGNITUDE_UNSUPPORTED",
        )
    decimals = fact_element.attrib.get("decimals")
    if decimals is not None and not re.fullmatch(r"(?:-?[0-9]+|INF)", decimals):
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            "SEC_REVENUE_DECIMALS_UNSUPPORTED",
        )
    record_id = ":".join(
        (
            "sec-edgar",
            submission.accession,
            submission.document_name,
            plan.context_id,
            plan.concept_namespace,
            plan.concept_local_name,
        )
    )
    return SECRevenueFact(
        accession=submission.accession,
        document_name=submission.document_name,
        namespace=plan.concept_namespace,
        concept=plan.concept_local_name,
        context_id=plan.context_id,
        issuer_cik=context_cik,
        period_start=period_start,
        period_end=period_end,
        dimensions=dimensions,
        unit_id=unit_ref,
        unit_namespace=unit_namespace,
        unit_local_name=unit_local,
        currency=unit_local,
        scale=0,
        decimals=decimals,
        signed_decimal_value=value,
        source_record_id=record_id,
    )


def load_sec_source_admission_record(
    path: str | Path, plan: SECObservationPlan
) -> SECSourceAdmission:
    """Load and validate the actual successful prepublication admission report."""

    report, raw, digest, record_path = _read_external_json_record(path)
    if (
        report.get("schema") != _PREPUBLICATION_ADMISSION_SCHEMA
        or report.get("kind") != "source_gate"
        or report.get("checkpoint") != _PREPUBLICATION_ADMISSION_NAME
        or report.get("mode") != "FULL"
        or report.get("phase") != "all"
        or report.get("status") != "PASS"
        or report.get("authority_checked") is not True
        or report.get("authority_failures") != []
        or report.get("identity_stable") is not True
    ):
        raise SECObservationError(
            "actual successful FEATURE/PROSPECTIVE admission required"
        )
    started = report.get("started_from")
    finished = report.get("finished_at")
    if not isinstance(started, dict) or not isinstance(finished, dict):
        raise SECObservationError("admission source identity is missing")
    for state in (started, finished):
        if (
            state.get("head") != plan.expected_source_head
            or state.get("tree") != plan.expected_source_tree
            or state.get("branch") != _EXPECTED_BRANCH
            or state.get("porcelain") != ""
        ):
            raise SECObservationError(
                "admission report is not bound to the exact clean source"
            )
    commands = report.get("commands")
    if not isinstance(commands, list):
        raise SECObservationError("admission command evidence is missing")
    command_codes: dict[str, int] = {}
    for item in commands:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise SECObservationError("admission command evidence is malformed")
        name = item["name"]
        if name in command_codes:
            raise SECObservationError("admission command evidence is duplicated")
        code = item.get("exit_code")
        if type(code) is not int:
            raise SECObservationError("admission command result is malformed")
        command_codes[name] = code
    if set(command_codes) != {
        "git_diff_check",
        "ruff_check",
        "ruff_format",
        "pytest",
    }:
        raise SECObservationError("admission command evidence is incomplete or extra")
    if not all(
        command_codes.get(name) == 0
        for name in ("git_diff_check", "ruff_check", "ruff_format", "pytest")
    ):
        raise SECObservationError("admission verification commands did not all pass")
    for effect_name in (
        "production_effects",
        "provider_effects",
        "scheduler_mutation",
        "broker_live_effects",
    ):
        if report.get(effect_name) != "NOT_RUN":
            raise SECObservationError("admission report records a non-source effect")
    return SECSourceAdmission(
        source_head=plan.expected_source_head,
        source_tree=plan.expected_source_tree,
        feature="PASS",
        prospective_develop="PASS",
        evidence_sha256=digest,
        evidence_path=str(record_path),
        evidence_bytes=raw,
    )


def load_sec_effect_authorization_record(
    path: str | Path,
    plan: SECObservationPlan,
    admission: SECSourceAdmission,
    now: datetime,
) -> SECObservationAuthorization:
    """Load the actual separate reviewed effect grant and bind its exact bytes."""

    record, raw, digest, record_path = _read_external_json_record(path)
    required = {
        "schema",
        "decision",
        "authorization_id",
        "plan_id",
        "approved_source_head",
        "approved_source_tree",
        "approved_attempt_id",
        "source_admission_sha256",
        "reviewed_by",
        "issued_at",
        "expires_at",
        "max_request_attempts",
    }
    if set(record) != required:
        raise SECObservationError(
            "effect authorization record has an unsupported shape"
        )
    if (
        record["schema"] != "pm2d-b1-r-sec-effect-authorization/v1"
        or record["decision"] != "APPROVED"
        or not isinstance(record["reviewed_by"], str)
        or not _TOKEN.fullmatch(record["reviewed_by"])
        or record["plan_id"] != plan.plan_id
        or record["approved_source_head"] != plan.expected_source_head
        or record["approved_source_tree"] != plan.expected_source_tree
        or record["approved_attempt_id"] != str(plan.attempt_id)
        or record["source_admission_sha256"] != admission.evidence_sha256
        or type(record["max_request_attempts"]) is not int
        or record["max_request_attempts"] != 1
    ):
        raise SECObservationError(
            "effect authorization does not bind reviewed evidence and plan"
        )
    if not isinstance(record["issued_at"], str) or not isinstance(
        record["expires_at"], str
    ):
        raise SECObservationError("effect authorization window is malformed")
    try:
        issued_at = datetime.fromisoformat(record["issued_at"])
        expires_at = datetime.fromisoformat(record["expires_at"])
    except ValueError:
        raise SECObservationError("effect authorization window is malformed") from None
    authorization = SECObservationAuthorization(
        authorization_id=record["authorization_id"],
        approved_plan_id=record["plan_id"],
        approved_source_head=record["approved_source_head"],
        approved_source_tree=record["approved_source_tree"],
        approved_attempt_id=plan.attempt_id,
        review_record_sha256=digest,
        issued_at=issued_at,
        expires_at=expires_at,
        max_request_attempts=record["max_request_attempts"],
        source_admission_sha256=admission.evidence_sha256,
        authorization_record_path=str(record_path),
        authorization_record_bytes=raw,
    )
    if not authorization.matches(plan, now):
        raise SECObservationError("effect authorization is expired or not yet valid")
    return authorization


def _read_external_json_record(
    path: str | Path,
) -> tuple[dict[str, object], bytes, str, Path]:
    candidate = Path(path)
    if not candidate.is_absolute() or ".." in candidate.parts:
        raise SECObservationError("evidence record path must be absolute and contained")
    if not _under_external_evidence_root(str(candidate)):
        raise SECObservationError("evidence record must be below F:\\AI\\temp")
    _reject_reparse_ancestors(Path(_EVIDENCE_ROOT).parent, candidate)
    if not candidate.is_file():
        raise SECObservationError("evidence record file is missing")
    try:
        with candidate.open("rb") as handle:
            raw = handle.read(_MAX_AUTHORITY_RECORD_BYTES + 1)
    except OSError as error:
        raise SECObservationError("evidence record could not be read") from error
    if not raw or len(raw) > _MAX_AUTHORITY_RECORD_BYTES:
        raise SECObservationError("evidence record exceeds its fixed byte bound")
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeError, ValueError, json.JSONDecodeError):
        raise SECObservationError("evidence record JSON is invalid") from None
    if not isinstance(value, dict):
        raise SECObservationError("evidence record root must be an object")
    return value, raw, hashlib.sha256(raw).hexdigest(), candidate


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"unsupported JSON constant: {value}")


def _read_sec_response_bounded(
    response: object,
    max_bytes: int,
    timeout_seconds: int,
    deadline: float,
    *,
    monotonic: Callable[[], float] = time.monotonic,
) -> bytes:
    """Bound body bytes and each socket read by the remaining request budget.

    The standard-library opener also bounds its blocking socket operations.
    DNS resolution, runtime scheduling, and urllib's connection/header setup do
    not provide a hard end-to-end wall-clock guarantee; callers check elapsed
    time after the request returns and report that limitation accurately.
    """

    http_response = getattr(response, "fp", None)
    buffer = getattr(http_response, "fp", None)
    raw = getattr(buffer, "raw", None)
    sock = getattr(raw, "_sock", None)
    if sock is None:
        raise SECObservationError("bounded SEC response socket is unavailable")
    body = bytearray()
    while len(body) <= max_bytes:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError("SEC total observation time limit reached")
        sock.settimeout(min(timeout_seconds, remaining))
        chunk = response.read(min(64 * 1024, max_bytes + 1 - len(body)))
        if not chunk:
            break
        body.extend(chunk)
    return bytes(body)


def _authorization_is_current(
    plan: SECObservationPlan,
    admission: SECSourceAdmission,
    authorization: SECObservationAuthorization,
    *,
    now: Callable[[], datetime],
    authorization_recheck: Callable[[], bool] | None,
) -> bool:
    try:
        current = normalize_utc(now(), "authorization recheck time")
        if not authorization.matches(plan, current):
            return False
        if (
            authorization.source_admission_sha256 is not None
            and authorization.source_admission_sha256 != admission.evidence_sha256
        ):
            return False
        if authorization_recheck is not None and not authorization_recheck():
            return False
        return authorization.matches(
            plan, normalize_utc(now(), "final authorization recheck time")
        )
    except (OSError, ValueError, RuntimeError, TypeError):
        return False


def _observe_sec_once_with_transport(
    plan: SECObservationPlan,
    admission: SECSourceAdmission,
    authorization: SECObservationAuthorization,
    transport: SECTransport,
    evidence_store: SECEvidenceStore,
    *,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    monotonic: Callable[[], float] = time.monotonic,
    authorization_recheck: Callable[[], bool] | None = None,
    require_response_receipt_timestamp: bool = False,
) -> SECObservationResult:
    """Run one exact SEC GET after independent source/effect gates.

    Tests may provide synthetic bytes through an exact fake transport. No
    default call is made by import, application startup, source admission, or
    pytest. A successful parse still returns ``SEC_OBSERVATION_BLOCKED`` and
    does not create a PM2C SourceFact. An operational bridge may use the
    preserved local receipt only after independent security mapping; historical
    reconstruction separately requires an exact version/availability witness.
    """

    counters = SECObservationCounters()
    current = normalize_utc(now(), "current time")
    if not isinstance(admission, SECSourceAdmission) or not plan.source_matches(
        admission.source_head, admission.source_tree
    ):
        return _result(
            plan,
            SECObservationOutcome.SOURCE_ADMISSION_FAILED,
            "EXACT_FEATURE_AND_PROSPECTIVE_DEVELOP_ADMISSION_REQUIRED",
            counters,
        )
    if (
        not isinstance(authorization, SECObservationAuthorization)
        or not authorization.matches(plan, current)
        or (
            authorization.source_admission_sha256 is not None
            and authorization.source_admission_sha256 != admission.evidence_sha256
        )
    ):
        return _result(
            plan,
            SECObservationOutcome.EFFECT_AUTHORIZATION_FAILED,
            "SEPARATE_PLAN_BOUND_EFFECT_AUTHORIZATION_REQUIRED",
            counters,
        )
    if not isinstance(transport, SECTransport) or not isinstance(
        evidence_store, SECEvidenceStore
    ):
        return _result(
            plan,
            SECObservationOutcome.EFFECT_AUTHORIZATION_FAILED,
            "EXPLICIT_TRANSPORT_AND_CREATE_ONCE_EVIDENCE_STORE_REQUIRED",
            counters,
        )
    if not _current_source_is_admitted(plan):
        return _result(
            plan,
            SECObservationOutcome.SOURCE_ADMISSION_FAILED,
            "CURRENT_FEATURE_AND_PROSPECTIVE_DEVELOP_ADMISSION_FAILED",
            counters,
        )
    if not _authorization_is_current(
        plan,
        admission,
        authorization,
        now=now,
        authorization_recheck=authorization_recheck,
    ):
        return _result(
            plan,
            SECObservationOutcome.EFFECT_AUTHORIZATION_FAILED,
            "EFFECT_AUTHORIZATION_EXPIRED_OR_EVIDENCE_CHANGED_AFTER_ADMISSION",
            counters,
        )
    try:
        if not evidence_store.reserve_attempt(plan):
            return _result(
                plan,
                SECObservationOutcome.ATTEMPT_CONSUMED,
                "ATTEMPT_ID_ALREADY_CONSUMED",
                counters,
            )
    except (OSError, ValueError, RuntimeError):
        return _result(
            plan,
            SECObservationOutcome.EVIDENCE_WRITE_FAILED,
            "ATTEMPT_RESERVATION_FAILED",
            counters,
        )

    started = monotonic()
    response_hashes: list[str] = []
    stored_responses: list[tuple[bytes, str, datetime]] = []
    response_bytes = 0
    response_bytes_received = 0
    request_intents = 0
    provider_invocations = 0
    if type(evidence_store) is SECFileEvidenceStore:
        try:
            evidence_store.write_authority_evidence(admission, authorization)
        except (OSError, ValueError, RuntimeError, TypeError):
            return _finish_result(
                plan,
                evidence_store,
                SECObservationOutcome.EVIDENCE_WRITE_FAILED,
                "REVIEWED_AUTHORITY_EVIDENCE_CUSTODY_FAILED",
                _counters(0, 0, 0, 0, 0),
            )
    request_specs = ((plan.submission_url, "submission"),)
    try:
        for ordinal, (url, label) in enumerate(request_specs, start=1):
            elapsed = monotonic() - started
            if elapsed >= plan.total_time_limit_seconds:
                return _finish_result(
                    plan,
                    evidence_store,
                    SECObservationOutcome.PROVIDER_FAILED,
                    "TOTAL_TIME_LIMIT_REACHED",
                    _counters(
                        provider_invocations,
                        request_intents,
                        len(stored_responses),
                        response_bytes,
                        0,
                    ),
                    hashes=tuple(response_hashes),
                )
            intent = {
                "schema": "pm2d-b1-r-sec-request-intent/v1",
                "plan_id": plan.plan_id,
                "attempt_id": str(plan.attempt_id),
                "ordinal": ordinal,
                "effect_authorization": {
                    "authorization_id": authorization.authorization_id,
                    "approved_plan_id": authorization.approved_plan_id,
                    "approved_source_head": authorization.approved_source_head,
                    "approved_source_tree": authorization.approved_source_tree,
                    "approved_attempt_id": str(authorization.approved_attempt_id),
                    "review_record_sha256": authorization.review_record_sha256,
                    "source_admission_sha256": admission.evidence_sha256,
                    "issued_at": authorization.issued_at.isoformat(),
                    "expires_at": authorization.expires_at.isoformat(),
                    "max_request_attempts": authorization.max_request_attempts,
                },
                "method": "GET",
                "endpoint": url,
                "accept_header": "text/plain",
                "request_parameters": [],
                "user_agent_sha256": hashlib.sha256(
                    plan.user_agent.encode("utf-8")
                ).hexdigest(),
                "max_response_bytes": plan.max_response_bytes,
                "timeout_seconds": plan.request_timeout_seconds,
                "total_time_limit_seconds": plan.total_time_limit_seconds,
                "automatic_retry": False,
                "intent_recorded_at": normalize_utc(now(), "intent time").isoformat(),
                "source_admission_evidence_path": admission.evidence_path,
                "effect_authorization_record_path": (
                    authorization.authorization_record_path
                ),
            }
            intent_recorded_at = datetime.fromisoformat(intent["intent_recorded_at"])
            request_intents += 1
            try:
                evidence_store.write_request_intent(ordinal, intent)
            except (OSError, ValueError, RuntimeError):
                return _finish_result(
                    plan,
                    evidence_store,
                    SECObservationOutcome.EVIDENCE_WRITE_FAILED,
                    "DURABLE_REQUEST_INTENT_WRITE_FAILED",
                    _counters(
                        provider_invocations,
                        request_intents,
                        len(stored_responses),
                        response_bytes,
                        0,
                    ),
                    hashes=tuple(response_hashes),
                )
            # The durable intent is the persisted attempt-accounting increment
            # and is written before the transport call below.
            if not _current_source_is_admitted(plan):
                return _finish_result(
                    plan,
                    evidence_store,
                    SECObservationOutcome.SOURCE_ADMISSION_FAILED,
                    "CURRENT_FEATURE_AND_PROSPECTIVE_DEVELOP_ADMISSION_CHANGED_BEFORE_REQUEST",
                    _counters(
                        provider_invocations,
                        request_intents,
                        len(stored_responses),
                        response_bytes,
                        0,
                        response_bytes_received=response_bytes_received,
                    ),
                    hashes=tuple(response_hashes),
                )
            if not _authorization_is_current(
                plan,
                admission,
                authorization,
                now=now,
                authorization_recheck=authorization_recheck,
            ):
                return _finish_result(
                    plan,
                    evidence_store,
                    SECObservationOutcome.EFFECT_AUTHORIZATION_FAILED,
                    "EFFECT_AUTHORIZATION_EXPIRED_OR_EVIDENCE_CHANGED_BEFORE_REQUEST",
                    _counters(
                        provider_invocations,
                        request_intents,
                        len(stored_responses),
                        response_bytes,
                        0,
                        response_bytes_received=response_bytes_received,
                    ),
                    hashes=tuple(response_hashes),
                )
            elapsed = monotonic() - started
            if elapsed >= plan.total_time_limit_seconds:
                return _finish_result(
                    plan,
                    evidence_store,
                    SECObservationOutcome.PROVIDER_FAILED,
                    "TOTAL_TIME_LIMIT_REACHED_BEFORE_REQUEST",
                    _counters(
                        provider_invocations,
                        request_intents,
                        len(stored_responses),
                        response_bytes,
                        0,
                        response_bytes_received=response_bytes_received,
                    ),
                    hashes=tuple(response_hashes),
                )
            if not authorization.matches(
                plan, normalize_utc(now(), "immediate pre-request authorization time")
            ):
                return _finish_result(
                    plan,
                    evidence_store,
                    SECObservationOutcome.EFFECT_AUTHORIZATION_FAILED,
                    "EFFECT_AUTHORIZATION_EXPIRED_IMMEDIATELY_BEFORE_REQUEST",
                    _counters(
                        provider_invocations,
                        request_intents,
                        len(stored_responses),
                        response_bytes,
                        0,
                        response_bytes_received=response_bytes_received,
                    ),
                    hashes=tuple(response_hashes),
                )
            remaining_time_limit = plan.total_time_limit_seconds - elapsed
            provider_invocations += 1
            try:
                response = transport.get(
                    url,
                    user_agent=plan.user_agent,
                    timeout_seconds=plan.request_timeout_seconds,
                    total_time_limit_seconds=remaining_time_limit,
                    max_bytes=plan.max_response_bytes,
                )
            except (TimeoutError, OSError, SECObservationError):
                return _finish_result(
                    plan,
                    evidence_store,
                    SECObservationOutcome.PROVIDER_FAILED,
                    "SEC_TRANSPORT_OR_PROVIDER_FAILURE",
                    _counters(
                        provider_invocations,
                        request_intents,
                        len(stored_responses),
                        response_bytes,
                        0,
                    ),
                    hashes=tuple(response_hashes),
                )
            except Exception:
                return _finish_result(
                    plan,
                    evidence_store,
                    SECObservationOutcome.PROVIDER_FAILED,
                    "SEC_TRANSPORT_OR_PROVIDER_FAILURE",
                    _counters(
                        provider_invocations,
                        request_intents,
                        len(stored_responses),
                        response_bytes,
                        0,
                    ),
                    hashes=tuple(response_hashes),
                )
            if not isinstance(response, SECTransportResponse):
                return _finish_result(
                    plan,
                    evidence_store,
                    SECObservationOutcome.RESPONSE_REJECTED,
                    "RESPONSE_SHAPE_UNSUPPORTED",
                    _counters(
                        provider_invocations,
                        request_intents,
                        len(stored_responses),
                        response_bytes,
                        0,
                    ),
                    hashes=tuple(response_hashes),
                )
            if (
                isinstance(response.status_code, bool)
                or not isinstance(response.status_code, int)
                or not 100 <= response.status_code <= 599
                or not isinstance(response.content_type, str)
                or not isinstance(response.final_url, str)
            ):
                return _finish_result(
                    plan,
                    evidence_store,
                    SECObservationOutcome.RESPONSE_REJECTED,
                    "RESPONSE_METADATA_UNSUPPORTED",
                    _counters(
                        provider_invocations,
                        request_intents,
                        len(stored_responses),
                        response_bytes,
                        0,
                    ),
                    hashes=tuple(response_hashes),
                )
            if (
                not isinstance(response.body, bytes)
                or len(response.body) > plan.max_response_bytes
            ):
                if isinstance(response.body, bytes):
                    response_bytes_received += len(response.body)
                return _finish_result(
                    plan,
                    evidence_store,
                    SECObservationOutcome.RESPONSE_REJECTED,
                    "RESPONSE_BYTE_LIMIT_REACHED",
                    _counters(
                        provider_invocations,
                        request_intents,
                        len(stored_responses),
                        response_bytes,
                        0,
                        response_bytes_received=response_bytes_received,
                    ),
                    hashes=tuple(response_hashes),
                )
            response_bytes_received += len(response.body)
            if response.received_at is None:
                if require_response_receipt_timestamp:
                    return _finish_result(
                        plan,
                        evidence_store,
                        SECObservationOutcome.RESPONSE_REJECTED,
                        "LOCAL_RESPONSE_RECEIPT_TIMESTAMP_REQUIRED",
                        _counters(
                            provider_invocations,
                            request_intents,
                            len(stored_responses),
                            response_bytes,
                            0,
                            response_bytes_received=response_bytes_received,
                        ),
                        hashes=tuple(response_hashes),
                    )
                received_at = normalize_utc(now(), "synthetic response receipt time")
            else:
                try:
                    received_at = normalize_utc(
                        response.received_at, "local response receipt time"
                    )
                except (TypeError, ValueError):
                    return _finish_result(
                        plan,
                        evidence_store,
                        SECObservationOutcome.RESPONSE_REJECTED,
                        "LOCAL_RESPONSE_RECEIPT_TIMESTAMP_INVALID",
                        _counters(
                            provider_invocations,
                            request_intents,
                            len(stored_responses),
                            response_bytes,
                            0,
                            response_bytes_received=response_bytes_received,
                        ),
                        hashes=tuple(response_hashes),
                    )
            if received_at < intent_recorded_at or received_at > normalize_utc(
                now(), "post-response local time"
            ):
                return _finish_result(
                    plan,
                    evidence_store,
                    SECObservationOutcome.RESPONSE_REJECTED,
                    "LOCAL_RESPONSE_RECEIPT_TIMESTAMP_OUTSIDE_REQUEST_WINDOW",
                    _counters(
                        provider_invocations,
                        request_intents,
                        len(stored_responses),
                        response_bytes,
                        0,
                        response_bytes_received=response_bytes_received,
                    ),
                    hashes=tuple(response_hashes),
                )
            try:
                digest = evidence_store.write_response(
                    ordinal,
                    label,
                    response.body,
                    response.content_type,
                    received_at=received_at,
                )
            except (OSError, ValueError, RuntimeError):
                return _finish_result(
                    plan,
                    evidence_store,
                    SECObservationOutcome.EVIDENCE_WRITE_FAILED,
                    "DURABLE_RESPONSE_WRITE_FAILED",
                    _counters(
                        provider_invocations,
                        request_intents,
                        len(stored_responses),
                        response_bytes,
                        0,
                        response_bytes_received=response_bytes_received,
                    ),
                    hashes=tuple(response_hashes),
                )
            expected_digest = hashlib.sha256(response.body).hexdigest()
            if digest != expected_digest:
                return _finish_result(
                    plan,
                    evidence_store,
                    SECObservationOutcome.EVIDENCE_WRITE_FAILED,
                    "RESPONSE_CUSTODY_DIGEST_MISMATCH",
                    _counters(
                        provider_invocations,
                        request_intents,
                        len(stored_responses),
                        response_bytes,
                        0,
                        response_bytes_received=response_bytes_received,
                    ),
                    hashes=tuple(response_hashes),
                )
            response_hashes.append(expected_digest)
            response_bytes += len(response.body)
            stored_responses.append((response.body, response.content_type, received_at))
            if response.final_url != url:
                return _finish_result(
                    plan,
                    evidence_store,
                    SECObservationOutcome.RESPONSE_REJECTED,
                    "REDIRECT_OR_ENDPOINT_MISMATCH",
                    _counters(
                        provider_invocations,
                        request_intents,
                        len(stored_responses),
                        response_bytes,
                        0,
                    ),
                    hashes=tuple(response_hashes),
                )
            if response.status_code != 200:
                return _finish_result(
                    plan,
                    evidence_store,
                    SECObservationOutcome.PROVIDER_FAILED,
                    f"SEC_HTTP_STATUS_{response.status_code}",
                    _counters(
                        provider_invocations,
                        request_intents,
                        len(stored_responses),
                        response_bytes,
                        0,
                    ),
                    hashes=tuple(response_hashes),
                )
            content_type = response.content_type.split(";", 1)[0].strip().lower()
            allowed_types = {"text/plain", "application/octet-stream"}
            if content_type not in allowed_types:
                return _finish_result(
                    plan,
                    evidence_store,
                    SECObservationOutcome.RESPONSE_REJECTED,
                    f"{label.upper()}_CONTENT_TYPE_UNSUPPORTED",
                    _counters(
                        provider_invocations,
                        request_intents,
                        len(stored_responses),
                        response_bytes,
                        0,
                    ),
                    hashes=tuple(response_hashes),
                )
            if monotonic() - started > plan.total_time_limit_seconds:
                return _finish_result(
                    plan,
                    evidence_store,
                    SECObservationOutcome.PROVIDER_FAILED,
                    "TOTAL_TIME_LIMIT_REACHED",
                    _counters(
                        provider_invocations,
                        request_intents,
                        len(stored_responses),
                        response_bytes,
                        0,
                    ),
                    hashes=tuple(response_hashes),
                )
    except (OSError, ValueError, RuntimeError):
        return _result(
            plan,
            SECObservationOutcome.EVIDENCE_WRITE_FAILED,
            "DURABLE_REQUEST_OR_RESPONSE_WRITE_FAILED",
            _counters(
                provider_invocations,
                request_intents,
                len(stored_responses),
                response_bytes,
                0,
            ),
            hashes=tuple(response_hashes),
        )

    try:
        raw_submission = stored_responses[0][0]
        submission = parse_sec_submission(raw_submission, plan, stored_responses[0][2])
        embedded_document = extract_sec_submission_member(raw_submission, submission)
        fact = parse_native_xbrl_revenue(embedded_document, plan, submission)
    except SECNativeInputError as error:
        return _finish_result(
            plan,
            evidence_store,
            error.code,
            error.reason_code,
            _counters(
                provider_invocations,
                request_intents,
                len(stored_responses),
                response_bytes,
                0,
            ),
            hashes=tuple(response_hashes),
        )
    return _finish_result(
        plan,
        evidence_store,
        SECObservationOutcome.SEC_OBSERVATION_BLOCKED,
        "SEC_HISTORICAL_VERSION_WITNESS_AND_SECURITY_MAPPING_UNPROVEN",
        _counters(
            provider_invocations,
            request_intents,
            len(stored_responses),
            response_bytes,
            1,
        ),
        submission=submission,
        fact=fact,
        hashes=tuple(response_hashes),
    )


class SECFileEvidenceStore:
    """Create-once, external-root custody for a future separately authorized run."""

    def __init__(self, plan: SECObservationPlan) -> None:
        if type(plan) is not SECObservationPlan:
            raise TypeError("SECFileEvidenceStore requires the exact SEC plan type")
        if Path(os.path.abspath(plan.evidence_root)) != Path(
            os.path.abspath(sec_observation_evidence_root())
        ):
            raise ValueError("plan must bind the canonical SEC evidence root")
        if plan.attempt_id != canonical_sec_attempt_id(plan):
            raise ValueError("plan attempt ID is not canonical for this source fact")
        self._root = sec_observation_evidence_root() / str(plan.attempt_id)
        self._plan = plan

    def is_bound_to(self, plan: SECObservationPlan) -> bool:
        return (
            type(plan) is SECObservationPlan
            and self._plan.plan_id == plan.plan_id
            and self._root == sec_observation_evidence_root() / str(plan.attempt_id)
        )

    def reserve_attempt(self, plan: SECObservationPlan) -> bool:
        if not self.is_bound_to(plan):
            raise ValueError("evidence store is bound to a different exact plan")
        _reject_reparse_ancestors(Path(_EVIDENCE_ROOT), self._root.parent)
        try:
            self._root.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            return False
        _reject_reparse_ancestors(Path(_EVIDENCE_ROOT), self._root)
        _write_once(self._root / "plan.json", _canonical_json_bytes(plan.to_manifest()))
        return True

    def write_request_intent(
        self, ordinal: int, material: Mapping[str, object]
    ) -> None:
        if ordinal != 1:
            raise ValueError("request ordinal is outside the fixed single-request plan")
        folder = self._root / "requests"
        folder.mkdir(exist_ok=True)
        _reject_reparse_ancestors(Path(_EVIDENCE_ROOT), folder)
        _write_once(
            folder / f"{ordinal:02d}.intent.json", _canonical_json_bytes(dict(material))
        )

    def write_authority_evidence(
        self,
        admission: SECSourceAdmission,
        authorization: SECObservationAuthorization,
    ) -> None:
        if (
            type(admission) is not SECSourceAdmission
            or type(authorization) is not SECObservationAuthorization
            or not self._plan.source_matches(
                admission.source_head, admission.source_tree
            )
            or not authorization.matches(self._plan, authorization.issued_at)
            or authorization.source_admission_sha256 != admission.evidence_sha256
            or admission.evidence_bytes is None
            or authorization.authorization_record_bytes is None
        ):
            raise ValueError("actual exact-bound authority records are required")
        if (
            hashlib.sha256(admission.evidence_bytes).hexdigest()
            != admission.evidence_sha256
            or hashlib.sha256(authorization.authorization_record_bytes).hexdigest()
            != authorization.review_record_sha256
        ):
            raise ValueError("authority record bytes do not match reviewed digests")
        folder = self._root / "authorities"
        folder.mkdir(exist_ok=True)
        _reject_reparse_ancestors(Path(_EVIDENCE_ROOT), folder)
        _write_once(folder / "source-admission.json", admission.evidence_bytes)
        _write_once(
            folder / "effect-authorization.json",
            authorization.authorization_record_bytes,
        )
        self._authority_evidence = {
            "source_admission_evidence": {
                "path": admission.evidence_path,
                "sha256": admission.evidence_sha256,
            },
            "effect_authorization_evidence": {
                "authorization_id": authorization.authorization_id,
                "path": authorization.authorization_record_path,
                "sha256": authorization.review_record_sha256,
            },
        }

    def authority_evidence_manifest(self) -> dict[str, object]:
        return dict(getattr(self, "_authority_evidence", {}))

    def write_response(
        self,
        ordinal: int,
        label: str,
        body: bytes,
        content_type: str,
        *,
        received_at: datetime | None = None,
    ) -> str:
        if ordinal != 1 or label != "submission":
            raise ValueError("response label is outside the fixed plan")
        if not isinstance(body, bytes):
            raise TypeError("raw response must be exact bytes")
        if len(body) > self._plan.max_response_bytes:
            raise ValueError("raw response exceeds the plan byte limit")
        if received_at is None:
            raise ValueError("local response receipt time is required for custody")
        received_at = normalize_utc(received_at, "local response receipt time")
        folder = self._root / "responses"
        folder.mkdir(exist_ok=True)
        _reject_reparse_ancestors(Path(_EVIDENCE_ROOT), folder)
        path = folder / f"{ordinal:02d}-{label}.bin"
        _write_once(path, body)
        digest = hashlib.sha256(body).hexdigest()
        try:
            preserved = path.read_bytes()
        except OSError as error:
            raise OSError("preserved response could not be verified") from error
        if preserved != body or hashlib.sha256(preserved).hexdigest() != digest:
            raise OSError("preserved response bytes differ from provider bytes")
        _write_once(
            folder / f"{ordinal:02d}-{label}.meta.json",
            _canonical_json_bytes(
                {
                    "content_type": content_type,
                    "content_length": len(body),
                    "content_sha256": digest,
                    "received_at": received_at.isoformat(),
                    "receipt_semantics": "LOCAL_FIRST_RECEIPT_NOT_PUBLICATION_TIME",
                }
            ),
        )
        return digest

    def write_terminal(self, material: Mapping[str, object]) -> None:
        _reject_reparse_ancestors(Path(_EVIDENCE_ROOT), self._root)
        _write_once(self._root / "terminal.json", _canonical_json_bytes(dict(material)))


def is_valid_sec_production_boundary(
    plan: SECObservationPlan, evidence_store: object
) -> bool:
    """Pure exact-type guard used only by the real SEC entry boundary."""

    return (
        type(plan) is SECObservationPlan
        and type(evidence_store) is SECFileEvidenceStore
        and Path(os.path.abspath(plan.evidence_root))
        == Path(os.path.abspath(sec_observation_evidence_root()))
        and plan.attempt_id == canonical_sec_attempt_id(plan)
        and evidence_store.is_bound_to(plan)
    )


def _current_source_is_admitted(plan: SECObservationPlan) -> bool:
    """Recheck the exact clean feature source under both current contexts."""

    root = Path(__file__).resolve().parents[3]
    if root != _EXPECTED_WORKTREE:
        return False
    try:

        def git(*arguments: str) -> str:
            completed = subprocess.run(
                ("git", "-C", str(root), *arguments),
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return completed.stdout.strip()

        head = git("rev-parse", "--verify", "HEAD").lower()
        tree = git("show", "-s", "--format=%T", "HEAD").lower()
        if (
            git("branch", "--show-current") != _EXPECTED_BRANCH
            or git("remote", "get-url", "origin") != _EXPECTED_ORIGIN
            or git("status", "--porcelain=v1", "--untracked-files=all")
            or not plan.source_matches(head, tree)
        ):
            return False
        remote = git(
            "ls-remote",
            "--refs",
            "origin",
            "refs/heads/feature/robinhood-portfolio-manager-current",
            "refs/heads/develop",
        )
        refs: dict[str, str] = {}
        for line in remote.splitlines():
            sha, ref = line.split("\t", 1)
            if ref in refs:
                return False
            refs[ref] = sha.lower()
        feature_ref = "refs/heads/feature/robinhood-portfolio-manager-current"
        develop_ref = "refs/heads/develop"
        if set(refs) != {feature_ref, develop_ref} or refs[feature_ref] != head:
            return False
        ancestor = subprocess.run(
            (
                "git",
                "-C",
                str(root),
                "merge-base",
                "--is-ancestor",
                refs[develop_ref],
                head,
            ),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if ancestor.returncode != 0:
            return False
        from scripts import current_source_authority

        if Path(current_source_authority.__file__).resolve().parents[1] != root:
            return False
        feature = current_source_authority.evaluate_source_authority(
            root,
            publication_context=current_source_authority.PublicationContext.FEATURE,
        )
        prospective = current_source_authority.evaluate_source_authority(
            root,
            publication_context=current_source_authority.PublicationContext.PROSPECTIVE_DEVELOP,
        )
        return all(
            result.passed and result.head == head and result.tree == tree
            for result in (feature, prospective)
        )
    except (
        OSError,
        RuntimeError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ):
        return False


def _submission_manifest(value: SECSubmission | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "issuer_cik": value.issuer_cik,
        "accession": value.accession,
        "form": value.form,
        "filing_date": value.filing_date.isoformat(),
        "report_period": value.report_period.isoformat(),
        "accepted_timestamp_raw": value.accepted_timestamp_raw,
        "document_type": value.document_type,
        "document_name": value.document_name,
        "document_sequence": value.document_sequence,
        "content_sha256": value.content_sha256,
        "content_length": value.content_length,
        "embedded_document_range": list(value.embedded_document_range),
        "embedded_document_sha256": value.embedded_document_sha256,
        "embedded_document_length": value.embedded_document_length,
        "observed_at": value.observed_at.isoformat(),
        "observation_time_semantics": "LOCAL_FIRST_RECEIPT_NOT_PUBLICATION_TIME",
    }


def _fact_manifest(value: SECRevenueFact | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "accession": value.accession,
        "document_name": value.document_name,
        "namespace": value.namespace,
        "concept": value.concept,
        "context_id": value.context_id,
        "issuer_cik": value.issuer_cik,
        "period_start": value.period_start.isoformat(),
        "period_end": value.period_end.isoformat(),
        "dimensions": [
            {"axis": list(axis), "member": list(member)}
            for axis, member in value.dimensions
        ],
        "unit_id": value.unit_id,
        "unit_namespace": value.unit_namespace,
        "unit_local_name": value.unit_local_name,
        "currency": value.currency,
        "scale": value.scale,
        "decimals": value.decimals,
        "signed_decimal_value": str(value.signed_decimal_value),
        "source_record_id": value.source_record_id,
    }


def _parse_contexts(
    root: ET.Element, namespace_map: Mapping[str, str]
) -> dict[
    str,
    tuple[
        str,
        date,
        date,
        tuple[tuple[tuple[str, str], tuple[str, str]], ...],
    ],
]:
    contexts: dict[
        str,
        tuple[
            str,
            date,
            date,
            tuple[tuple[tuple[str, str], tuple[str, str]], ...],
        ],
    ] = {}
    for context in root.findall(f"{{{_XBRLI}}}context"):
        context_id = context.attrib.get("id")
        if not context_id or context_id in contexts:
            raise SECNativeInputError(
                SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
                "XBRL_CONTEXT_ID_MISSING_OR_DUPLICATE",
            )
        entities = context.findall(f"{{{_XBRLI}}}entity")
        periods = context.findall(f"{{{_XBRLI}}}period")
        if len(entities) != 1 or len(periods) != 1:
            raise SECNativeInputError(
                SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
                "XBRL_CONTEXT_SHAPE_UNSUPPORTED",
            )
        identifiers = entities[0].findall(f"{{{_XBRLI}}}identifier")
        if len(identifiers) != 1:
            raise SECNativeInputError(
                SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
                "XBRL_ENTITY_IDENTIFIER_UNSUPPORTED",
            )
        identifier = identifiers[0]
        if identifier.attrib.get("scheme") != "http://www.sec.gov/CIK":
            raise SECNativeInputError(
                SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
                "XBRL_ENTITY_SCHEME_UNSUPPORTED",
            )
        cik = (identifier.text or "").strip()
        if not _CIK.fullmatch(cik):
            raise SECNativeInputError(
                SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
                "XBRL_ENTITY_CIK_UNSUPPORTED",
            )
        period = periods[0]
        starts = period.findall(f"{{{_XBRLI}}}startDate")
        ends = period.findall(f"{{{_XBRLI}}}endDate")
        instants = period.findall(f"{{{_XBRLI}}}instant")
        if len(starts) != 1 or len(ends) != 1 or instants:
            raise SECNativeInputError(
                SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
                "XBRL_DURATION_CONTEXT_REQUIRED",
            )
        dimensions: list[tuple[tuple[str, str], tuple[str, str]]] = []
        segments = entities[0].findall(f"{{{_XBRLI}}}segment")
        scenarios = context.findall(f"{{{_XBRLI}}}scenario")
        if len(segments) > 1 or len(scenarios) > 1:
            raise SECNativeInputError(
                SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
                "XBRL_DIMENSION_CONTAINER_DUPLICATE",
            )
        for container in (*segments, *scenarios):
            for child in list(container):
                if child.tag == f"{{{_XBRLDI}}}typedMember":
                    raise SECNativeInputError(
                        SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
                        "TYPED_XBRL_DIMENSION_UNSUPPORTED",
                    )
                if child.tag != f"{{{_XBRLDI}}}explicitMember":
                    raise SECNativeInputError(
                        SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
                        "XBRL_DIMENSION_SHAPE_UNSUPPORTED",
                    )
                axis = _resolve_qname(child.attrib.get("dimension", ""), namespace_map)
                member = _resolve_qname((child.text or "").strip(), namespace_map)
                dimensions.append((axis, member))
        if len({axis for axis, _ in dimensions}) != len(dimensions):
            raise SECNativeInputError(
                SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
                "XBRL_DUPLICATE_DIMENSION_AXIS",
            )
        try:
            start_date = date.fromisoformat((starts[0].text or "").strip())
            end_date = date.fromisoformat((ends[0].text or "").strip())
        except ValueError:
            raise SECNativeInputError(
                SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
                "XBRL_PERIOD_DATE_UNSUPPORTED",
            ) from None
        if start_date >= end_date:
            raise SECNativeInputError(
                SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
                "XBRL_PERIOD_ORDER_INVALID",
            )
        contexts[context_id] = (
            cik,
            start_date,
            end_date,
            tuple(sorted(dimensions)),
        )
    return contexts


def _parse_units(
    root: ET.Element, namespace_map: Mapping[str, str]
) -> dict[str, tuple[str, str]]:
    units: dict[str, tuple[str, str]] = {}
    for unit in root.findall(f"{{{_XBRLI}}}unit"):
        unit_id = unit.attrib.get("id")
        measures = unit.findall(f"{{{_XBRLI}}}measure")
        if not unit_id or unit_id in units or len(measures) != 1:
            raise SECNativeInputError(
                SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
                "XBRL_UNIT_SHAPE_UNSUPPORTED",
            )
        units[unit_id] = _resolve_qname((measures[0].text or "").strip(), namespace_map)
    return units


def _resolve_qname(value: str, namespace_map: Mapping[str, str]) -> tuple[str, str]:
    if not value or value.count(":") != 1:
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            "XBRL_QNAME_UNSUPPORTED",
        )
    prefix, local = value.split(":", 1)
    namespace = namespace_map.get(prefix)
    if namespace is None or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,119}", local):
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            "XBRL_QNAME_NAMESPACE_UNSUPPORTED",
        )
    return namespace, local


def _header_value(header: str, name: str) -> str:
    matches = re.findall(rf"(?im)^\s*{re.escape(name)}:\s*([^\r\n]+?)\s*$", header)
    if len(matches) != 1:
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            "SEC_REQUIRED_HEADER_FIELD_MISSING_OR_DUPLICATE",
        )
    return matches[0].strip()


def _parse_yyyymmdd(value: str, label: str) -> date:
    if not re.fullmatch(r"[0-9]{8}", value):
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            f"{label.replace(' ', '_')}_UNSUPPORTED",
        )
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        raise SECNativeInputError(
            SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            f"{label.replace(' ', '_')}_INVALID",
        ) from None


def _safe_namespace(value: str, *, require_https: bool = False) -> bool:
    parsed = urlsplit(value)
    allowed_scheme = {"https"} if require_https else {"http", "https"}
    return (
        parsed.scheme in allowed_scheme
        and parsed.hostname is not None
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
    )


def _qname_pair(value: object) -> bool:
    return (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[0], str)
        and _safe_namespace(value[0])
        and isinstance(value[1], str)
        and bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,119}", value[1]))
    )


def _require_response_bytes(raw_bytes: bytes, limit: int, label: str) -> None:
    if not isinstance(raw_bytes, bytes):
        raise TypeError(f"{label} must be exact response bytes")
    if len(raw_bytes) > limit:
        raise SECNativeInputError(
            SECObservationOutcome.RESPONSE_REJECTED,
            f"{label.upper()}_BYTE_LIMIT_REACHED",
        )


def _under_external_evidence_root(value: str) -> bool:
    if not isinstance(value, str) or ".." in Path(value).parts:
        return False
    normalized = os.path.normcase(os.path.abspath(value))
    base = os.path.normcase(os.path.abspath(_EVIDENCE_ROOT))
    return normalized.startswith(base + os.sep)


def _reject_reparse_ancestors(root: Path, target: Path) -> None:
    resolved_root = Path(os.path.abspath(root))
    resolved_target = Path(os.path.abspath(target))
    if not resolved_target.is_relative_to(resolved_root):
        raise ValueError("evidence path escapes the external root")
    cursor = resolved_root
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if cursor.exists() or cursor.is_symlink():
        info = cursor.lstat()
        if cursor.is_symlink() or getattr(info, "st_file_attributes", 0) & reparse_flag:
            raise ValueError("evidence root contains a reparse point")
    for component in resolved_target.relative_to(resolved_root).parts:
        cursor = cursor / component
        if cursor.exists() or cursor.is_symlink():
            info = cursor.lstat()
            if (
                cursor.is_symlink()
                or getattr(info, "st_file_attributes", 0) & reparse_flag
            ):
                raise ValueError("evidence root contains a reparse point")


def _write_once(path: Path, body: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def _counters(
    provider_invocations: int,
    request_intents: int,
    response_documents: int,
    response_bytes: int,
    xbrl_records: int,
    *,
    response_bytes_received: int | None = None,
) -> SECObservationCounters:
    return SECObservationCounters(
        provider_invocations=provider_invocations,
        request_intents=request_intents,
        response_documents=response_documents,
        response_bytes=response_bytes,
        response_bytes_received=(
            response_bytes
            if response_bytes_received is None
            else response_bytes_received
        ),
        xbrl_records=xbrl_records,
    )


def _result(
    plan: SECObservationPlan,
    outcome: SECObservationOutcome,
    reason_code: str,
    counters: SECObservationCounters,
    *,
    hashes: tuple[str, ...] = (),
) -> SECObservationResult:
    return SECObservationResult(
        outcome,
        reason_code,
        plan.plan_id,
        plan.expected_source_head,
        plan.expected_source_tree,
        counters,
        response_sha256=hashes,
    )


def _finish_result(
    plan: SECObservationPlan,
    store: SECEvidenceStore,
    outcome: SECObservationOutcome,
    reason_code: str,
    counters: SECObservationCounters,
    *,
    submission: SECSubmission | None = None,
    fact: SECRevenueFact | None = None,
    hashes: tuple[str, ...] = (),
) -> SECObservationResult:
    result = SECObservationResult(
        outcome,
        reason_code,
        plan.plan_id,
        plan.expected_source_head,
        plan.expected_source_tree,
        counters,
        submission=submission,
        fact=fact,
        response_sha256=hashes,
    )
    authority_evidence = (
        store.authority_evidence_manifest()
        if type(store) is SECFileEvidenceStore
        else {}
    )
    terminal = {
        "schema": "pm2d-b1-r-sec-observation-terminal/v1",
        "plan_id": plan.plan_id,
        "attempt_id": str(plan.attempt_id),
        "source_head": plan.expected_source_head,
        "source_tree": plan.expected_source_tree,
        "outcome": outcome.value,
        "reason_code": reason_code,
        "provider_invocations": counters.provider_invocations,
        "request_intents": counters.request_intents,
        "response_documents": counters.response_documents,
        "response_bytes": counters.response_bytes,
        "response_bytes_received": counters.response_bytes_received,
        "xbrl_records": counters.xbrl_records,
        "source_admission_evidence": authority_evidence.get(
            "source_admission_evidence", {"path": None, "sha256": None}
        ),
        "effect_authorization_evidence": authority_evidence.get(
            "effect_authorization_evidence",
            {"authorization_id": None, "path": None, "sha256": None},
        ),
        "response_sha256": list(hashes),
        "normalized_submission": _submission_manifest(submission),
        "normalized_fact": _fact_manifest(fact),
        "credential_reads": 0,
        "account_reads": 0,
        "ai_calls": 0,
        "broker_effects": 0,
        "production_mutations": 0,
        "public_availability_witness": "UNPROVEN",
        "security_identity_witness": "UNPROVEN",
        "source_fact_created": False,
    }
    try:
        store.write_terminal(terminal)
    except (OSError, ValueError, RuntimeError):
        return _result(
            plan,
            SECObservationOutcome.EVIDENCE_WRITE_FAILED,
            "TERMINAL_EVIDENCE_WRITE_FAILED",
            counters,
            hashes=hashes,
        )
    return result
