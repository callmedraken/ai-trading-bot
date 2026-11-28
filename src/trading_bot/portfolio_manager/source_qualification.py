"""Fake-only, one-shot operator boundary for PM2D-B1 qualification.

This module accepts only immutable preloaded response bytes and exact fake
provider implementations.  It has no HTTP, SDK, credential, account, AI,
broker, recommendation, or dispatch dependency.  Its source admission object is
explicitly synthetic fixture evidence and grants no real observation authority.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Final, final

from scripts.current_source_authority import AuthorityResult, PublicationContext

from trading_bot.domain._validation import normalize_utc
from trading_bot.portfolio_manager.sec_sharadar_qualification import (
    ParsedSecResponse,
    ParsedSharadarPage,
    QualificationOutcome,
    QualificationPlan,
    QualificationResult,
    SecDocumentBinding,
    SecProvenanceWitness,
    SharadarProvenanceWitness,
    compare_candidate,
    parse_sec_response,
    parse_sharadar_page,
)

PM2D_B1_CHECKPOINT: Final = "arch152-pm2d-b1-sec-sharadar-bounded-qualification-source"
CANONICAL_ORIGIN: Final = "https://github.com/callmedraken/ai-trading-bot.git"
FEATURE_BRANCH: Final = "feature/robinhood-portfolio-manager-current"
_PLANNED_EVIDENCE_ROOT: Final = Path(r"F:\AI\temp")
# Tests may replace this module-local destination with a temporary directory;
# callers cannot supply a runtime override through the public operation.
EVIDENCE_ROOT = _PLANNED_EVIDENCE_ROOT
_REPO_ROOT: Final = Path(__file__).resolve().parents[3]
_ATTEMPT_PREFIX: Final = "arch152-pm2d-b1-"
_SAFE_CURSOR = re.compile(r"[A-Za-z0-9._~:-]{1,256}\Z")
_SAFE_MEMBER = re.compile(r"[A-Za-z0-9._-]{1,160}\Z")
_SAFE_VERSION = re.compile(r"[A-Za-z0-9._:+-]{1,512}\Z")
_ATTEMPT_ID = re.compile(r"[0-9a-f]{32}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_REPARSE_POINT: Final = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

# These fixed ceilings sit below the planned type bounds so a malformed future
# plan cannot make this inert fake operator unbounded.
_MAX_SEC_DOCUMENTS: Final = 3
_MAX_SHARADAR_PAGES: Final = 5
_MAX_TOTAL_PROVIDER_ATTEMPTS: Final = 8
_MAX_SEC_RESPONSE_BYTES: Final = 20_000_000
_MAX_SHARADAR_PAGE_BYTES: Final = 20_000_000
_MAX_SEC_FACTS: Final = 200
_MAX_SHARADAR_ROWS: Final = 500


class OperatorStatus(StrEnum):
    QUALIFIED_CANDIDATE = "QUALIFIED_CANDIDATE"
    SOURCE_ADMISSION_FAILED = "SOURCE_ADMISSION_FAILED"
    ATTEMPT_ALREADY_CONSUMED = "ATTEMPT_ALREADY_CONSUMED"
    EVIDENCE_WRITE_FAILED = "EVIDENCE_WRITE_FAILED"
    FAKE_BOUNDARY_REJECTED = "FAKE_BOUNDARY_REJECTED"
    PLAN_BOUNDS_REJECTED = "PLAN_BOUNDS_REJECTED"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    SEC_RESPONSE_INVALID = "SEC_RESPONSE_INVALID"
    SHARADAR_RESPONSE_INVALID = "SHARADAR_RESPONSE_INVALID"
    PAGE_LIMIT_REACHED = "PAGE_LIMIT_REACHED"
    ATTEMPT_LIMIT_REACHED = "ATTEMPT_LIMIT_REACHED"
    PAGE_CURSOR_CYCLE = "PAGE_CURSOR_CYCLE"
    COMPARISON_FAILED = "COMPARISON_FAILED"


@dataclass(frozen=True, slots=True)
class SyntheticSourceDeclaration:
    """Offline source facts used only to exercise the fake operator boundary."""

    repository_root: str
    branch: str
    origin: str
    head: str
    tree: str
    clean: bool


@dataclass(frozen=True, slots=True)
class SyntheticSourceAdmission:
    """Two exact typed authority fixtures; never a real admission grant."""

    declaration: SyntheticSourceDeclaration
    feature: AuthorityResult
    prospective_develop: AuthorityResult


@dataclass(frozen=True, slots=True)
class FakeSecDocument:
    """One already-materialized synthetic SEC response and witness set."""

    document_name: str
    raw_bytes: bytes
    witnesses: tuple[SecProvenanceWitness, ...]

    def __post_init__(self) -> None:
        if (
            type(self.document_name) is not str
            or _SAFE_MEMBER.fullmatch(self.document_name) is None
        ):
            raise ValueError("document_name must be a safe exact member name")
        if type(self.raw_bytes) is not bytes:
            raise TypeError("raw_bytes must be immutable bytes")
        if type(self.witnesses) is not tuple or any(
            type(item) is not SecProvenanceWitness for item in self.witnesses
        ):
            raise TypeError("witnesses must be an immutable SEC witness tuple")


@dataclass(frozen=True, slots=True)
class FakeSharadarPage:
    """One already-materialized synthetic SF1 page and witness set."""

    requested_cursor: str | None
    raw_bytes: bytes
    witnesses: tuple[SharadarProvenanceWitness, ...]

    def __post_init__(self) -> None:
        if self.requested_cursor is not None and (
            type(self.requested_cursor) is not str
            or _SAFE_CURSOR.fullmatch(self.requested_cursor) is None
        ):
            raise ValueError("requested_cursor must be a safe cursor or None")
        if type(self.raw_bytes) is not bytes:
            raise TypeError("raw_bytes must be immutable bytes")
        if type(self.witnesses) is not tuple or any(
            type(item) is not SharadarProvenanceWitness for item in self.witnesses
        ):
            raise TypeError("witnesses must be an immutable Sharadar witness tuple")


@final
@dataclass(frozen=True, slots=True)
class FakeSecProvider:
    """Exact in-memory lookup over preloaded SEC fixture bytes only."""

    documents: tuple[FakeSecDocument, ...]

    def __post_init__(self) -> None:
        if type(self.documents) is not tuple or any(
            type(item) is not FakeSecDocument for item in self.documents
        ):
            raise TypeError("documents must be an immutable fake-document tuple")

    def document(self, document_name: str) -> FakeSecDocument:
        matches = tuple(
            item for item in self.documents if item.document_name == document_name
        )
        if len(matches) != 1:
            raise _FakeProviderFailure
        return matches[0]


@final
@dataclass(frozen=True, slots=True)
class FakeSharadarProvider:
    """Exact in-memory lookup over preloaded SF1 fixture bytes only."""

    pages: tuple[FakeSharadarPage, ...]

    def __post_init__(self) -> None:
        if type(self.pages) is not tuple or any(
            type(item) is not FakeSharadarPage for item in self.pages
        ):
            raise TypeError("pages must be an immutable fake-page tuple")

    def page(self, requested_cursor: str | None) -> FakeSharadarPage:
        matches = tuple(
            item for item in self.pages if item.requested_cursor == requested_cursor
        )
        if len(matches) != 1:
            raise _FakeProviderFailure
        return matches[0]


@dataclass(frozen=True, slots=True)
class OperatorCounters:
    source_admission_attempts: int = 0
    sec_provider_attempts: int = 0
    sharadar_provider_attempts: int = 0
    sec_documents_received: int = 0
    sharadar_pages_received: int = 0
    sec_facts_inspected: int = 0
    sharadar_rows_inspected: int = 0
    custody_write_attempts: int = 0
    custody_writes_succeeded: int = 0
    comparison_attempts: int = 0
    credential_read_attempts: int = 0
    account_read_attempts: int = 0
    ai_call_attempts: int = 0
    broker_effect_attempts: int = 0
    production_mutation_attempts: int = 0

    @property
    def provider_attempts(self) -> int:
        return self.sec_provider_attempts + self.sharadar_provider_attempts


@dataclass(frozen=True, slots=True)
class QualificationRunResult:
    """Sanitized in-memory result; raw provider errors and payloads are absent."""

    status: OperatorStatus
    reason: str
    attempt_id: str
    attempt_directory: Path | None
    terminal_manifest: Path | None
    terminal_sha256: str | None
    counters: OperatorCounters
    qualification: QualificationResult | None = None


@dataclass(slots=True)
class _MutableCounters:
    source_admission_attempts: int = 0
    sec_provider_attempts: int = 0
    sharadar_provider_attempts: int = 0
    sec_documents_received: int = 0
    sharadar_pages_received: int = 0
    sec_facts_inspected: int = 0
    sharadar_rows_inspected: int = 0
    custody_write_attempts: int = 0
    custody_writes_succeeded: int = 0
    comparison_attempts: int = 0
    response_events: list[dict[str, object]] = field(default_factory=list)
    source_admission: SyntheticSourceAdmission | None = None

    @property
    def provider_attempts(self) -> int:
        return self.sec_provider_attempts + self.sharadar_provider_attempts

    def frozen(self) -> OperatorCounters:
        return OperatorCounters(
            source_admission_attempts=self.source_admission_attempts,
            sec_provider_attempts=self.sec_provider_attempts,
            sharadar_provider_attempts=self.sharadar_provider_attempts,
            sec_documents_received=self.sec_documents_received,
            sharadar_pages_received=self.sharadar_pages_received,
            sec_facts_inspected=self.sec_facts_inspected,
            sharadar_rows_inspected=self.sharadar_rows_inspected,
            custody_write_attempts=self.custody_write_attempts,
            custody_writes_succeeded=self.custody_writes_succeeded,
            comparison_attempts=self.comparison_attempts,
        )


class _FakeProviderFailure(Exception):
    pass


class _RunFailure(Exception):
    def __init__(self, status: OperatorStatus, reason: str) -> None:
        self.status = status
        self.reason = reason
        super().__init__(reason)


def run_fake_qualification(
    *,
    plan: QualificationPlan,
    source_admission: SyntheticSourceAdmission,
    sec_provider: FakeSecProvider,
    sharadar_provider: FakeSharadarProvider,
    observed_at: datetime,
) -> QualificationRunResult:
    """Run one bounded source-only attempt against exact preloaded fake bytes.

    This function never accepts a callback, transport, URL, credential, network
    client, or structurally compatible provider. A matching attempt ID is
    consumed before source admission and cannot be retried.
    """

    if type(plan) is not QualificationPlan:
        raise TypeError("plan must be an exact QualificationPlan")
    attempt_id = plan.attempt_id
    if type(observed_at) is not datetime:
        raise TypeError("observed_at must be an explicit timezone-aware datetime")
    observed_at = normalize_utc(observed_at, "observed_at")
    bounds_reason = _validate_plan_bounds(plan)
    if bounds_reason is not None:
        return QualificationRunResult(
            OperatorStatus.PLAN_BOUNDS_REJECTED,
            bounds_reason,
            attempt_id,
            None,
            None,
            None,
            OperatorCounters(),
        )

    try:
        attempt_directory = _reserve_attempt(plan)
    except FileExistsError:
        return QualificationRunResult(
            OperatorStatus.ATTEMPT_ALREADY_CONSUMED,
            "ATTEMPT_ALREADY_CONSUMED",
            attempt_id,
            None,
            None,
            None,
            OperatorCounters(),
        )
    except Exception:
        return QualificationRunResult(
            OperatorStatus.EVIDENCE_WRITE_FAILED,
            "ATTEMPT_RESERVATION_FAILED",
            attempt_id,
            None,
            None,
            None,
            OperatorCounters(),
        )

    counts = _MutableCounters()
    try:
        plan_body = _canonical_json_bytes(plan.to_manifest())
        plan_digest = hashlib.sha256(plan_body).hexdigest()
        _write_once(
            attempt_directory / "intent.json",
            _canonical_json_bytes(
                {
                    "schema": "arch152-pm2d-b1-fake-intent/v1",
                    "attempt_id": attempt_id,
                    "plan_id": str(plan.plan_id),
                    "plan_sha256": plan_digest,
                    "plan": plan.to_manifest(),
                    "source_admission_kind": "SYNTHETIC_FIXTURE_ONLY",
                    "source_authority_grant": "NONE",
                }
            ),
        )
    except Exception:
        return _finish(
            plan,
            attempt_directory,
            counts,
            OperatorStatus.EVIDENCE_WRITE_FAILED,
            "INTENT_WRITE_FAILED",
            observed_at,
            qualification=None,
        )

    counts.source_admission_attempts += 1
    if not _valid_synthetic_admission(plan, source_admission):
        return _finish(
            plan,
            attempt_directory,
            counts,
            OperatorStatus.SOURCE_ADMISSION_FAILED,
            "SYNTHETIC_SOURCE_ADMISSION_REJECTED",
            observed_at,
            qualification=None,
        )
    counts.source_admission = source_admission

    try:
        _write_once(
            attempt_directory / "admission.json",
            _canonical_json_bytes(_admission_manifest(source_admission)),
        )
    except Exception:
        return _finish(
            plan,
            attempt_directory,
            counts,
            OperatorStatus.EVIDENCE_WRITE_FAILED,
            "ADMISSION_MANIFEST_WRITE_FAILED",
            observed_at,
            qualification=None,
        )

    if (
        type(sec_provider) is not FakeSecProvider
        or type(sharadar_provider) is not FakeSharadarProvider
    ):
        return _finish(
            plan,
            attempt_directory,
            counts,
            OperatorStatus.FAKE_BOUNDARY_REJECTED,
            "EXACT_FAKE_PROVIDER_REQUIRED",
            observed_at,
            qualification=None,
        )

    if (
        type(sec_provider.documents) is not tuple
        or type(sharadar_provider.pages) is not tuple
    ):
        return _finish(
            plan,
            attempt_directory,
            counts,
            OperatorStatus.FAKE_BOUNDARY_REJECTED,
            "IMMUTABLE_PRELOADED_RESPONSES_REQUIRED",
            observed_at,
            qualification=None,
        )
    for response in (*sec_provider.documents, *sharadar_provider.pages):
        if type(response) not in (FakeSecDocument, FakeSharadarPage):
            return _finish(
                plan,
                attempt_directory,
                counts,
                OperatorStatus.FAKE_BOUNDARY_REJECTED,
                "EXACT_FAKE_RESPONSE_REQUIRED",
                observed_at,
                qualification=None,
            )

    if (
        tuple(item.document_name for item in sec_provider.documents)
        != tuple(item.document_name for item in plan.sec_document_bindings)
        or not sharadar_provider.pages
        or len(sharadar_provider.pages) > _MAX_SHARADAR_PAGES
        or len({item.requested_cursor for item in sharadar_provider.pages})
        != len(sharadar_provider.pages)
        or sharadar_provider.pages[0].requested_cursor is not None
    ):
        return _finish(
            plan,
            attempt_directory,
            counts,
            OperatorStatus.FAKE_BOUNDARY_REJECTED,
            "PRELOADED_RESPONSE_SET_MISMATCH",
            observed_at,
            qualification=None,
        )

    if len(plan.sec_document_bindings) > _MAX_SEC_DOCUMENTS:
        return _finish(
            plan,
            attempt_directory,
            counts,
            OperatorStatus.PLAN_BOUNDS_REJECTED,
            "SEC_DOCUMENT_BOUND_EXCEEDED",
            observed_at,
            qualification=None,
        )

    parsed_sec = []
    parsed_pages = []
    sec_witnesses = []
    sharadar_witnesses = []
    try:
        for binding in plan.sec_document_bindings:
            document_name = binding.document_name
            if counts.sec_facts_inspected >= min(plan.max_sec_facts, _MAX_SEC_FACTS):
                raise _RunFailure(
                    OperatorStatus.SEC_RESPONSE_INVALID,
                    "SEC_FACT_BOUND_EXCEEDED",
                )
            if counts.provider_attempts >= plan.max_provider_attempts:
                raise _RunFailure(
                    OperatorStatus.ATTEMPT_LIMIT_REACHED, "ATTEMPT_LIMIT_REACHED"
                )
            try:
                _write_call_intent(
                    attempt_directory,
                    provider="SEC_EDGAR",
                    ordinal=counts.provider_attempts + 1,
                    request_identity=document_name,
                    expected_accession=binding.accession,
                    source_head=plan.expected_source_head,
                    source_tree=plan.expected_source_tree,
                    observed_at=observed_at,
                )
            except Exception:
                raise _RunFailure(
                    OperatorStatus.EVIDENCE_WRITE_FAILED,
                    "SEC_CALL_INTENT_WRITE_FAILED",
                ) from None
            counts.sec_provider_attempts += 1
            try:
                response = sec_provider.document(document_name)
            except Exception:
                raise _RunFailure(
                    OperatorStatus.PROVIDER_FAILURE, "SEC_PROVIDER_FAILURE"
                ) from None
            counts.sec_documents_received += 1
            if len(response.raw_bytes) > min(
                plan.max_sec_response_bytes, _MAX_SEC_RESPONSE_BYTES
            ):
                counts.response_events.append(
                    {
                        "provider": "SEC_EDGAR",
                        "request_identity": response.document_name,
                        "expected_accession": binding.accession,
                        "request_ordinal": counts.sec_documents_received,
                        "content_type": "application/json",
                        "response_sha256": None,
                        "content_length": len(response.raw_bytes),
                        "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
                        "record_count": None,
                        "pagination_terminal": None,
                        "next_cursor_sha256": None,
                        "parsed": False,
                    }
                )
                raise _RunFailure(
                    OperatorStatus.SEC_RESPONSE_INVALID,
                    "SEC_RESPONSE_BYTE_LIMIT_EXCEEDED",
                )
            raw_digest = hashlib.sha256(response.raw_bytes).hexdigest()
            counts.response_events.append(
                {
                    "provider": "SEC_EDGAR",
                    "request_identity": response.document_name,
                    "expected_accession": binding.accession,
                    "request_ordinal": counts.sec_documents_received,
                    "content_type": "application/json",
                    "response_sha256": raw_digest,
                    "content_length": len(response.raw_bytes),
                    "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
                    "record_count": None,
                    "pagination_terminal": None,
                    "next_cursor_sha256": None,
                    "parsed": False,
                }
            )
            try:
                parsed = parse_sec_response(
                    response.raw_bytes,
                    plan,
                    observed_at,
                    max_facts=min(
                        plan.max_sec_facts - counts.sec_facts_inspected,
                        _MAX_SEC_FACTS - counts.sec_facts_inspected,
                    ),
                )
            except Exception:
                raise _RunFailure(
                    OperatorStatus.SEC_RESPONSE_INVALID, "SEC_RESPONSE_INVALID"
                ) from None
            if (
                type(parsed) is not ParsedSecResponse
                or parsed.document_name != document_name
                or parsed.content_length != len(response.raw_bytes)
                or parsed.content_sha256 != raw_digest
            ):
                raise _RunFailure(
                    OperatorStatus.SEC_RESPONSE_INVALID,
                    "SEC_RESPONSE_IDENTITY_MISMATCH",
                )
            counts.sec_facts_inspected += len(parsed.facts)
            counts.response_events[-1]["record_count"] = len(parsed.facts)
            counts.response_events[-1]["parsed"] = True
            scope_reason = _sec_scope_failure(plan, binding, parsed)
            if scope_reason is not None:
                counts.response_events[-1]["scope_status"] = scope_reason
                raise _RunFailure(
                    OperatorStatus.SEC_RESPONSE_INVALID,
                    scope_reason,
                )
            if counts.sec_facts_inspected > min(plan.max_sec_facts, _MAX_SEC_FACTS):
                raise _RunFailure(
                    OperatorStatus.SEC_RESPONSE_INVALID,
                    "SEC_FACT_BOUND_EXCEEDED",
                )
            _validate_sec_witnesses(response.witnesses, parsed, raw_digest)
            try:
                _write_custody_once(
                    attempt_directory,
                    "sec",
                    document_name,
                    response.raw_bytes,
                    counts,
                )
            except Exception:
                raise _RunFailure(
                    OperatorStatus.EVIDENCE_WRITE_FAILED,
                    "SEC_CUSTODY_WRITE_FAILED",
                ) from None
            parsed_sec.append(parsed)
            sec_witnesses.extend(response.witnesses)

        cursor: str | None = None
        seen_cursors: set[str | None] = set()
        terminal = False
        while not terminal:
            if len(parsed_pages) >= min(plan.max_sharadar_pages, _MAX_SHARADAR_PAGES):
                raise _RunFailure(
                    OperatorStatus.PAGE_LIMIT_REACHED, "PAGE_LIMIT_REACHED"
                )
            if counts.sharadar_rows_inspected >= min(
                plan.max_sharadar_rows, _MAX_SHARADAR_ROWS
            ):
                raise _RunFailure(
                    OperatorStatus.SHARADAR_RESPONSE_INVALID,
                    "SHARADAR_ROW_BOUND_EXCEEDED",
                )
            if cursor in seen_cursors:
                raise _RunFailure(OperatorStatus.PAGE_CURSOR_CYCLE, "PAGE_CURSOR_CYCLE")
            seen_cursors.add(cursor)
            if counts.provider_attempts >= plan.max_provider_attempts or (
                counts.provider_attempts >= _MAX_TOTAL_PROVIDER_ATTEMPTS
            ):
                raise _RunFailure(
                    OperatorStatus.ATTEMPT_LIMIT_REACHED, "ATTEMPT_LIMIT_REACHED"
                )
            cursor_hash = _cursor_digest(cursor)
            try:
                _write_call_intent(
                    attempt_directory,
                    provider="SHARADAR_SF1",
                    ordinal=counts.provider_attempts + 1,
                    request_identity=cursor_hash,
                    source_head=plan.expected_source_head,
                    source_tree=plan.expected_source_tree,
                    observed_at=observed_at,
                )
            except Exception:
                raise _RunFailure(
                    OperatorStatus.EVIDENCE_WRITE_FAILED,
                    "SHARADAR_CALL_INTENT_WRITE_FAILED",
                ) from None
            counts.sharadar_provider_attempts += 1
            try:
                response = sharadar_provider.page(cursor)
            except Exception:
                raise _RunFailure(
                    OperatorStatus.PROVIDER_FAILURE, "SHARADAR_PROVIDER_FAILURE"
                ) from None
            if response.requested_cursor != cursor:
                raise _RunFailure(
                    OperatorStatus.SHARADAR_RESPONSE_INVALID,
                    "SHARADAR_REQUEST_CURSOR_MISMATCH",
                )
            counts.sharadar_pages_received += 1
            if len(response.raw_bytes) > min(
                plan.max_sharadar_page_bytes, _MAX_SHARADAR_PAGE_BYTES
            ):
                counts.response_events.append(
                    {
                        "provider": "SHARADAR_SF1",
                        "request_cursor_sha256": cursor_hash,
                        "request_ordinal": counts.sharadar_pages_received,
                        "content_type": "application/json",
                        "response_sha256": None,
                        "content_length": len(response.raw_bytes),
                        "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
                        "record_count": None,
                        "pagination_terminal": None,
                        "next_cursor_sha256": None,
                        "parsed": False,
                    }
                )
                raise _RunFailure(
                    OperatorStatus.SHARADAR_RESPONSE_INVALID,
                    "SHARADAR_RESPONSE_BYTE_LIMIT_EXCEEDED",
                )
            raw_digest = hashlib.sha256(response.raw_bytes).hexdigest()
            counts.response_events.append(
                {
                    "provider": "SHARADAR_SF1",
                    "request_cursor_sha256": cursor_hash,
                    "request_ordinal": counts.sharadar_pages_received,
                    "content_type": "application/json",
                    "response_sha256": raw_digest,
                    "content_length": len(response.raw_bytes),
                    "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
                    "record_count": None,
                    "pagination_terminal": None,
                    "next_cursor_sha256": None,
                    "parsed": False,
                }
            )
            try:
                parsed = parse_sharadar_page(
                    response.raw_bytes,
                    plan,
                    observed_at,
                    requested_cursor=cursor,
                    max_rows=min(
                        plan.max_sharadar_rows - counts.sharadar_rows_inspected,
                        _MAX_SHARADAR_ROWS - counts.sharadar_rows_inspected,
                    ),
                )
            except Exception:
                raise _RunFailure(
                    OperatorStatus.SHARADAR_RESPONSE_INVALID,
                    "SHARADAR_RESPONSE_INVALID",
                ) from None
            if (
                type(parsed) is not ParsedSharadarPage
                or parsed.requested_cursor != cursor
                or parsed.content_length != len(response.raw_bytes)
                or parsed.content_sha256 != raw_digest
            ):
                raise _RunFailure(
                    OperatorStatus.SHARADAR_RESPONSE_INVALID,
                    "SHARADAR_RESPONSE_IDENTITY_MISMATCH",
                )
            counts.sharadar_rows_inspected += len(parsed.rows)
            counts.response_events[-1]["record_count"] = len(parsed.rows)
            counts.response_events[-1]["pagination_terminal"] = parsed.terminal
            counts.response_events[-1]["next_cursor_sha256"] = (
                _cursor_digest(parsed.next_cursor)
                if parsed.next_cursor is not None
                else None
            )
            counts.response_events[-1]["parsed"] = True
            scope_reason = _sharadar_scope_failure(plan, parsed)
            if scope_reason is not None:
                counts.response_events[-1]["scope_status"] = scope_reason
                raise _RunFailure(
                    OperatorStatus.SHARADAR_RESPONSE_INVALID,
                    scope_reason,
                )
            if counts.sharadar_rows_inspected > min(
                plan.max_sharadar_rows, _MAX_SHARADAR_ROWS
            ):
                raise _RunFailure(
                    OperatorStatus.SHARADAR_RESPONSE_INVALID,
                    "SHARADAR_ROW_BOUND_EXCEEDED",
                )
            _validate_sharadar_witnesses(response.witnesses, parsed, raw_digest)
            try:
                _write_custody_once(
                    attempt_directory,
                    "sharadar",
                    cursor_hash,
                    response.raw_bytes,
                    counts,
                )
            except Exception:
                raise _RunFailure(
                    OperatorStatus.EVIDENCE_WRITE_FAILED,
                    "SHARADAR_CUSTODY_WRITE_FAILED",
                ) from None
            parsed_pages.append(parsed)
            sharadar_witnesses.extend(response.witnesses)
            cursor = parsed.next_cursor
            terminal = parsed.terminal

        if len(parsed_pages) != len(sharadar_provider.pages):
            raise _RunFailure(
                OperatorStatus.FAKE_BOUNDARY_REJECTED,
                "UNUSED_PRELOADED_RESPONSE_REJECTED",
            )

        counts.comparison_attempts += 1
        try:
            qualification = compare_candidate(
                plan,
                tuple(parsed_sec),
                tuple(parsed_pages),
                tuple(sec_witnesses),
                tuple(sharadar_witnesses),
                observed_at,
            )
        except Exception:
            raise _RunFailure(
                OperatorStatus.COMPARISON_FAILED, "COMPARISON_FAILED"
            ) from None
        if qualification.outcome is QualificationOutcome.QUALIFIED_CANDIDATE:
            return _finish(
                plan,
                attempt_directory,
                counts,
                OperatorStatus.QUALIFIED_CANDIDATE,
                "QUALIFIED_CANDIDATE",
                observed_at,
                qualification=qualification,
            )
        reason = _safe_domain_reason(qualification.reason)
        return _finish(
            plan,
            attempt_directory,
            counts,
            OperatorStatus.COMPARISON_FAILED,
            reason,
            observed_at,
            qualification=qualification,
        )
    except _RunFailure as failure:
        return _finish(
            plan,
            attempt_directory,
            counts,
            failure.status,
            failure.reason,
            observed_at,
            qualification=None,
        )
    except Exception:
        return _finish(
            plan,
            attempt_directory,
            counts,
            OperatorStatus.EVIDENCE_WRITE_FAILED,
            "OPERATOR_OPERATION_FAILED",
            observed_at,
            qualification=None,
        )


def _valid_synthetic_admission(
    plan: QualificationPlan, admission: SyntheticSourceAdmission
) -> bool:
    if type(admission) is not SyntheticSourceAdmission:
        return False
    declaration = admission.declaration
    if type(declaration) is not SyntheticSourceDeclaration:
        return False
    if (
        type(declaration.repository_root) is not str
        or type(declaration.branch) is not str
        or type(declaration.origin) is not str
        or type(declaration.head) is not str
        or type(declaration.tree) is not str
        or type(declaration.clean) is not bool
        or declaration.repository_root != str(_REPO_ROOT)
        or declaration.branch != FEATURE_BRANCH
        or declaration.origin != CANONICAL_ORIGIN
        or declaration.head != plan.expected_source_head
        or declaration.tree != plan.expected_source_tree
        or declaration.clean is not True
    ):
        return False
    expected = (
        (admission.feature, PublicationContext.FEATURE),
        (admission.prospective_develop, PublicationContext.PROSPECTIVE_DEVELOP),
    )
    for result, context in expected:
        if (
            type(result) is not AuthorityResult
            or result.context is not context
            or result.head != plan.expected_source_head
            or result.tree != plan.expected_source_tree
            or type(result.failures) is not tuple
            or result.failures
            or type(result.checkpoints) is not tuple
            or PM2D_B1_CHECKPOINT not in result.checkpoints
            or not result.checkpoints
            or len(result.checkpoints) != len(set(result.checkpoints))
            or any(
                type(item) is not str
                or re.fullmatch(r"[a-z0-9._-]{1,128}", item) is None
                for item in result.checkpoints
            )
        ):
            return False
    return True


def _validate_plan_bounds(plan: QualificationPlan) -> str | None:
    try:
        if (
            type(plan.attempt_id) is not str
            or _ATTEMPT_ID.fullmatch(plan.attempt_id) is None
        ):
            return "ATTEMPT_ID_INVALID"
        if plan.automatic_retry is not False:
            return "AUTOMATIC_RETRY_NOT_DISABLED"
        bindings = plan.sec_document_bindings
        if type(bindings) is not tuple or not 1 <= len(bindings) <= _MAX_SEC_DOCUMENTS:
            return "SEC_DOCUMENT_BOUND_EXCEEDED"
        if plan.sf1_table != "SHARADAR/SF1" or any(
            type(item) is not SecDocumentBinding
            or type(item.document_name) is not str
            or _SAFE_MEMBER.fullmatch(item.document_name) is None
            for item in bindings
        ):
            return "SEC_DOCUMENT_BINDING_INVALID"
        required_accessions = {
            plan.primary_accession,
            plan.amendment_accession,
            plan.early_8k_accession,
        } - {None}
        if (
            len({item.accession for item in bindings}) != len(bindings)
            or {item.accession for item in bindings} != required_accessions
        ):
            return "SEC_DOCUMENT_BINDING_INCOMPLETE"
        if not 1 <= plan.max_sec_documents <= _MAX_SEC_DOCUMENTS:
            return "SEC_DOCUMENT_BOUND_EXCEEDED"
        if len(bindings) > plan.max_sec_documents:
            return "SEC_DOCUMENT_BOUND_EXCEEDED"
        if not 1 <= plan.max_sharadar_pages <= _MAX_SHARADAR_PAGES:
            return "SHARADAR_PAGE_BOUND_EXCEEDED"
        if not 1 <= plan.max_provider_attempts <= _MAX_TOTAL_PROVIDER_ATTEMPTS:
            return "PROVIDER_ATTEMPT_BOUND_EXCEEDED"
        if not 1 <= plan.max_sec_response_bytes <= _MAX_SEC_RESPONSE_BYTES:
            return "SEC_RESPONSE_BYTE_BOUND_EXCEEDED"
        if not 1 <= plan.max_sharadar_page_bytes <= _MAX_SHARADAR_PAGE_BYTES:
            return "SHARADAR_PAGE_BYTE_BOUND_EXCEEDED"
        if not 1 <= plan.max_sec_facts <= _MAX_SEC_FACTS:
            return "SEC_FACT_BOUND_EXCEEDED"
        if not 1 <= plan.max_sharadar_rows <= _MAX_SHARADAR_ROWS:
            return "SHARADAR_ROW_BOUND_EXCEEDED"
        if any(
            type(name) is not str or _SAFE_MEMBER.fullmatch(name) is None
            for name in plan.sec_document_names
        ):
            return "SEC_DOCUMENT_NAME_UNSAFE"
        if len(set(plan.sec_document_names)) != len(plan.sec_document_names):
            return "SEC_DOCUMENT_NAME_DUPLICATE"
        if plan.max_provider_attempts < len(bindings) + 1:
            return "PROVIDER_ATTEMPT_BOUND_INSUFFICIENT"
        plan_root = Path(plan.evidence_root)
        if not _same_path(plan_root, _PLANNED_EVIDENCE_ROOT):
            return "EVIDENCE_ROOT_OUTSIDE_BOUND"
        return None
    except Exception:
        return "PLAN_BOUNDS_INVALID"


def _validate_sec_witnesses(
    witnesses: tuple[SecProvenanceWitness, ...], parsed: object, digest: str
) -> None:
    if type(witnesses) is not tuple:
        raise _RunFailure(
            OperatorStatus.SEC_RESPONSE_INVALID, "SEC_WITNESS_SET_INVALID"
        )
    fact_locators = {fact.locator for fact in parsed.facts}
    seen: set[str] = set()
    for witness in witnesses:
        if (
            type(witness) is not SecProvenanceWitness
            or witness.record_locator not in fact_locators
            or witness.response_sha256 != digest
            or _SAFE_VERSION.fullmatch(witness.source_version) is None
            or witness.record_locator in seen
        ):
            raise _RunFailure(
                OperatorStatus.SEC_RESPONSE_INVALID, "SEC_WITNESS_MISMATCH"
            )
        seen.add(witness.record_locator)


def _validate_sharadar_witnesses(
    witnesses: tuple[SharadarProvenanceWitness, ...], parsed: object, digest: str
) -> None:
    if type(witnesses) is not tuple:
        raise _RunFailure(
            OperatorStatus.SHARADAR_RESPONSE_INVALID,
            "SHARADAR_WITNESS_SET_INVALID",
        )
    row_locators = {row.locator for row in parsed.rows}
    seen: set[str] = set()
    for witness in witnesses:
        if (
            type(witness) is not SharadarProvenanceWitness
            or witness.record_locator not in row_locators
            or witness.response_sha256 != digest
            or _SAFE_VERSION.fullmatch(witness.source_version) is None
            or witness.record_locator in seen
        ):
            raise _RunFailure(
                OperatorStatus.SHARADAR_RESPONSE_INVALID,
                "SHARADAR_WITNESS_MISMATCH",
            )
        seen.add(witness.record_locator)


def _sec_scope_failure(
    plan: QualificationPlan,
    binding: SecDocumentBinding,
    parsed: ParsedSecResponse,
) -> str | None:
    expected_forms = {
        plan.primary_accession: plan.primary_form,
        plan.amendment_accession: plan.amendment_form,
        plan.early_8k_accession: plan.early_8k_form,
    }
    if (
        binding.accession not in expected_forms
        or parsed.document_name != binding.document_name
        or parsed.accession != binding.accession
    ):
        return "SEC_MEMBER_ACCESSION_MISMATCH"
    if (
        parsed.issuer_cik != plan.issuer_cik
        or parsed.form != expected_forms[binding.accession]
        or parsed.report_period != plan.period_end
    ):
        return "SEC_ISSUER_FORM_OR_PERIOD_MISMATCH"
    for fact in parsed.facts:
        if fact.concept != plan.field_mapping.sec_concept:
            return "SEC_CONCEPT_OUTSIDE_PLAN"
        if (
            fact.context_id != plan.context_id
            or fact.context_cik != plan.issuer_cik
            or fact.period_start != plan.period_start
            or fact.period_end != plan.period_end
            or fact.dimensions != plan.dimensions
        ):
            return "SEC_CONTEXT_OUTSIDE_PLAN"
        if (
            fact.unit != plan.provider_unit
            or fact.currency != plan.currency
            or fact.scale != plan.sec_scale
        ):
            return "SEC_FACT_BASIS_OUTSIDE_PLAN"
    return None


def _sharadar_scope_failure(
    plan: QualificationPlan, parsed: ParsedSharadarPage
) -> str | None:
    if parsed.table != plan.sf1_table or parsed.dimension != plan.sf1_dimension:
        return "SHARADAR_TABLE_OR_DIMENSION_MISMATCH"
    for row in parsed.rows:
        if (
            row.ticker != plan.ticker
            or row.perma_ticker != plan.perma_ticker
            or row.report_period != plan.period_end
        ):
            return "SHARADAR_SUBJECT_OR_PERIOD_OUTSIDE_PLAN"
    return None


def _reserve_attempt(plan: QualificationPlan) -> Path:
    root = _resolve_evidence_root(Path(EVIDENCE_ROOT))
    directory = root / f"{_ATTEMPT_PREFIX}{plan.attempt_id}"
    _assert_no_reparse_points(root, directory.parent)
    directory.mkdir()
    _assert_no_reparse_points(root, directory)
    custody = directory / "custody"
    custody.mkdir()
    _assert_no_reparse_points(root, custody)
    calls = directory / "calls"
    calls.mkdir()
    _assert_no_reparse_points(root, calls)
    return directory


def _resolve_evidence_root(candidate: Path) -> Path:
    if not _same_path(candidate, EVIDENCE_ROOT):
        raise ValueError("evidence root outside bound")
    root = candidate.resolve(strict=True)
    if not _same_path(root, candidate):
        raise ValueError("evidence root is a reparse path")
    _assert_no_reparse_points(root, root)
    return root


def _assert_no_reparse_points(root: Path, target: Path) -> None:
    current = target
    while _same_path(current, root) or root in current.parents:
        info = current.lstat()
        attrs = getattr(info, "st_file_attributes", 0)
        if stat.S_ISLNK(info.st_mode) or attrs & _REPARSE_POINT:
            raise ValueError("reparse point rejected")
        if _same_path(current, root):
            return
        current = current.parent
    raise ValueError("path escapes evidence root")


def _write_custody_once(
    attempt_directory: Path,
    source: str,
    request_identity: str,
    body: bytes,
    counts: _MutableCounters,
) -> Path:
    digest = hashlib.sha256(body).hexdigest()
    identity_digest = hashlib.sha256(request_identity.encode("utf-8")).hexdigest()
    path = attempt_directory / "custody" / f"{source}-{identity_digest}-{digest}.json"
    counts.custody_write_attempts += 1
    evidence_root = _resolve_evidence_root(EVIDENCE_ROOT)
    _write_bytes_once(path, body, evidence_root=evidence_root)
    counts.custody_writes_succeeded += 1
    return path


def _write_call_intent(
    attempt_directory: Path,
    *,
    provider: str,
    ordinal: int,
    request_identity: str,
    expected_accession: str | None = None,
    source_head: str,
    source_tree: str,
    observed_at: datetime,
) -> None:
    if provider == "SEC_EDGAR" and _SAFE_MEMBER.fullmatch(request_identity):
        safe_identity = request_identity
    elif provider == "SHARADAR_SF1" and _SHA256.fullmatch(request_identity):
        safe_identity = request_identity
    else:
        raise ValueError("unsafe provider request identity")
    body = _canonical_json_bytes(
        {
            "schema": "arch152-pm2d-b1-fake-call-intent/v1",
            "provider": provider,
            "ordinal": ordinal,
            "request_identity": safe_identity,
            "expected_accession": expected_accession,
            "source_head": source_head,
            "source_tree": source_tree,
            "source_admission_kind": "SYNTHETIC_FIXTURE_ONLY",
            "authority_grant": "NONE",
            "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
            "automatic_retry": False,
        }
    )
    provider_slug = "sec" if provider == "SEC_EDGAR" else "sharadar"
    path = attempt_directory / "calls" / f"{provider_slug}-{ordinal:03d}.json"
    _write_once(path, body)


def _write_once(path: Path, body: bytes) -> None:
    evidence_root = _resolve_evidence_root(EVIDENCE_ROOT)
    _write_bytes_once(path, body, evidence_root=evidence_root)


def _write_bytes_once(path: Path, body: bytes, *, evidence_root: Path) -> None:
    _assert_no_reparse_points(evidence_root, path.parent)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(body)
            stream.flush()
            os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _finish(
    plan: QualificationPlan,
    attempt_directory: Path,
    counts: _MutableCounters,
    status: OperatorStatus,
    reason: str,
    observed_at: datetime,
    *,
    qualification: QualificationResult | None,
) -> QualificationRunResult:
    frozen = counts.frozen()
    manifest = {
        "schema": "arch152-pm2d-b1-fake-terminal/v1",
        "attempt_id": plan.attempt_id,
        "plan_id": str(plan.plan_id),
        "expected_source_head": plan.expected_source_head,
        "expected_source_tree": plan.expected_source_tree,
        "source_admission_kind": "SYNTHETIC_FIXTURE_ONLY",
        "source_authority_grant": "NONE",
        "source_admission": (
            _admission_manifest(counts.source_admission)
            if type(counts.source_admission) is SyntheticSourceAdmission
            else None
        ),
        "status": status.value,
        "reason": _safe_reason(reason),
        "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
        "counters": _counter_dict(frozen),
        "response_events": counts.response_events,
        "qualification": _qualification_manifest(qualification),
    }
    terminal = attempt_directory / "terminal.json"
    try:
        terminal_bytes = _canonical_json_bytes(manifest)
        _write_once(terminal, terminal_bytes)
    except Exception:
        return QualificationRunResult(
            OperatorStatus.EVIDENCE_WRITE_FAILED,
            "TERMINAL_MANIFEST_WRITE_FAILED",
            plan.attempt_id,
            attempt_directory,
            None,
            None,
            frozen,
            None,
        )
    if status not in (
        OperatorStatus.QUALIFIED_CANDIDATE,
        OperatorStatus.COMPARISON_FAILED,
    ):
        qualification = None
    return QualificationRunResult(
        status,
        _safe_reason(reason),
        plan.attempt_id,
        attempt_directory,
        terminal,
        hashlib.sha256(terminal_bytes).hexdigest(),
        frozen,
        qualification,
    )


def _counter_dict(counters: OperatorCounters) -> dict[str, int]:
    return {
        "source_admission_attempts": counters.source_admission_attempts,
        "sec_provider_attempts": counters.sec_provider_attempts,
        "sharadar_provider_attempts": counters.sharadar_provider_attempts,
        "provider_attempts": counters.provider_attempts,
        "sec_documents_received": counters.sec_documents_received,
        "sharadar_pages_received": counters.sharadar_pages_received,
        "sec_facts_inspected": counters.sec_facts_inspected,
        "sharadar_rows_inspected": counters.sharadar_rows_inspected,
        "custody_write_attempts": counters.custody_write_attempts,
        "custody_writes_succeeded": counters.custody_writes_succeeded,
        "comparison_attempts": counters.comparison_attempts,
        "credential_read_attempts": counters.credential_read_attempts,
        "account_read_attempts": counters.account_read_attempts,
        "ai_call_attempts": counters.ai_call_attempts,
        "broker_effect_attempts": counters.broker_effect_attempts,
        "production_mutation_attempts": counters.production_mutation_attempts,
    }


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(str(left))) == os.path.normcase(
        os.path.abspath(str(right))
    )


def _cursor_digest(cursor: str | None) -> str:
    if cursor is None:
        return hashlib.sha256(b"<first-page>").hexdigest()
    if type(cursor) is not str or _SAFE_CURSOR.fullmatch(cursor) is None:
        raise _RunFailure(
            OperatorStatus.SHARADAR_RESPONSE_INVALID, "UNSAFE_CURSOR_REJECTED"
        )
    return hashlib.sha256(cursor.encode("utf-8")).hexdigest()


def _safe_reason(reason: str) -> str:
    if type(reason) is str and re.fullmatch(r"[A-Z0-9_]{1,64}", reason):
        return reason
    return "QUALIFICATION_UNAVAILABLE"


def _safe_domain_reason(reason: object) -> str:
    return _safe_reason(reason) if type(reason) is str else "COMPARISON_UNQUALIFIED"


def _admission_manifest(
    admission: SyntheticSourceAdmission,
) -> dict[str, object]:
    return {
        "kind": "SYNTHETIC_FIXTURE_ONLY",
        "authority_grant": "NONE",
        "repository_root": str(_REPO_ROOT),
        "branch": FEATURE_BRANCH,
        "origin_identity": "CANONICAL_ORIGIN",
        "head": admission.declaration.head,
        "tree": admission.declaration.tree,
        "clean_fixture": admission.declaration.clean,
        "contexts": [
            _authority_manifest(admission.feature),
            _authority_manifest(admission.prospective_develop),
        ],
    }


def _authority_manifest(result: AuthorityResult) -> dict[str, object]:
    return {
        "context": result.context.value,
        "head": result.head,
        "tree": result.tree,
        "checkpoints": list(result.checkpoints),
        "failure_count": len(result.failures),
    }


def _qualification_manifest(
    qualification: QualificationResult | None,
) -> dict[str, object] | None:
    if type(qualification) is not QualificationResult:
        return None
    selected_sec = qualification.selected_sec_fact
    selected_sf1 = qualification.selected_sharadar_row
    return {
        "outcome": qualification.outcome.value,
        "reason": _safe_domain_reason(qualification.reason),
        "plan_id": str(qualification.plan_id),
        "source_identity": (
            "synthetic:pm2d-b1:sec-sharadar-candidate-v1"
            if qualification.outcome is QualificationOutcome.QUALIFIED_CANDIDATE
            else None
        ),
        "sec_source_channel": "SEC_PUBLIC_ARCHIVE_WITNESS",
        "sharadar_source_channel": "SHARADAR_SF1_IMMUTABLE_VERSION_WITNESS",
        "selected_sec_record_locator": (
            selected_sec.locator if selected_sec is not None else None
        ),
        "selected_sharadar_record_locator": (
            selected_sf1.locator if selected_sf1 is not None else None
        ),
        "sec_response_sha256": qualification.sec_response_sha256,
        "sf1_response_sha256": qualification.sf1_response_sha256,
        "sec_source_version": (
            qualification.sec_source_version
            if type(qualification.sec_source_version) is str
            and _SAFE_VERSION.fullmatch(qualification.sec_source_version)
            else None
        ),
        "sf1_source_version": (
            qualification.sf1_source_version
            if type(qualification.sf1_source_version) is str
            and _SAFE_VERSION.fullmatch(qualification.sf1_source_version)
            else None
        ),
        "sec_proof_reference": qualification.sec_proof_reference,
        "sf1_proof_reference": qualification.sf1_proof_reference,
        "sec_available_at": _optional_time(qualification.sec_available_at),
        "sf1_available_at": _optional_time(qualification.sf1_available_at),
        "available_at": _optional_time(qualification.available_at),
        "visibility_ends_at": _optional_time(qualification.visibility_ends_at),
    }


def _optional_time(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value is not None else None


__all__ = [
    "FakeSecDocument",
    "FakeSecProvider",
    "FakeSharadarPage",
    "FakeSharadarProvider",
    "OperatorCounters",
    "OperatorStatus",
    "PM2D_B1_CHECKPOINT",
    "QualificationRunResult",
    "SyntheticSourceAdmission",
    "SyntheticSourceDeclaration",
    "run_fake_qualification",
]
