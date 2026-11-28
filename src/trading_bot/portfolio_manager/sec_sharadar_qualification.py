"""Fake-only bounded SEC/SF1 fact qualification contracts for PM2D-B1.

This module parses small, frozen JSON envelopes supplied by the injected fake
providers.  It does not contain a transport, persistence layer, or provider
adapter.  Provider facts and independently supplied version/availability
witnesses are separate types so timestamps such as SEC acceptance, SF1
``datekey``, ``lastupdated``, or local observation time cannot silently become
historical availability.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import PureWindowsPath
from typing import Any
from uuid import UUID

from trading_bot.domain._validation import normalize_utc
from trading_bot.portfolio_manager.research_catalog import (
    CatalogEntry,
    EntryKind,
    EvidenceBasis,
    PeriodSpec,
    ResearchCatalog,
    ScopeSpec,
    ValueKind,
    research_identity,
)
from trading_bot.portfolio_manager.research_evidence import (
    AvailabilityStatus,
    EvidenceOutcome,
    EvidenceSubject,
    EvidenceTimeframe,
    EvidenceTimeframeKind,
    SourceFact,
    VersionAsOfWitness,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_OBJECT_RE = re.compile(r"^[0-9a-f]{40}$")
_CIK_RE = re.compile(r"^[0-9]{10}$")
_ACCESSION_RE = re.compile(r"^[0-9]{10}-[0-9]{2}-[0-9]{6}$")
_DECIMAL_TEXT_RE = re.compile(
    r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$"
)
_KNOWN_SHARADAR_DIMENSIONS = frozenset({"ARQ", "ARY", "ART", "MRQ", "MRY", "MRT"})
_ALLOWED_MAX_BYTES = 20_000_000
_ALLOWED_MAX_SEC_DOCUMENTS = 3
_ALLOWED_MAX_SEC_FACTS = 200
_ALLOWED_MAX_SHARADAR_PAGES = 5
_ALLOWED_MAX_SHARADAR_ROWS = 500
_ALLOWED_MAX_PROVIDER_ATTEMPTS = 8
_MAX_DECIMAL_DIGITS = 64
_MAX_DECIMAL_EXPONENT = 64
_MAX_DIMENSIONS = 32
_MAX_TOKEN_LENGTH = 256


def _safe_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{name} must be nonblank text")
    if value != value.strip() or len(value) > _MAX_TOKEN_LENGTH:
        raise ValueError(f"{name} must use bounded canonical text")
    return value


def _safe_token(value: object, name: str) -> str:
    text = _safe_text(value, name)
    if any(character.isspace() for character in text) or "/" in text or "\\" in text:
        raise ValueError(f"{name} must be a canonical token")
    return text


class QualificationInputError(ValueError):
    """Raised when a fake response or frozen plan violates its typed shape."""


class PeriodRole(StrEnum):
    ANNUAL = "ANNUAL"
    DIRECT_Q1 = "DIRECT_Q1"
    YTD_Q2 = "YTD_Q2"
    YTD_Q3 = "YTD_Q3"
    ANNUAL_MINUS_Q3_YTD_Q4 = "ANNUAL_MINUS_Q3_YTD_Q4"


class QualificationOutcome(StrEnum):
    QUALIFIED_CANDIDATE = "QUALIFIED_CANDIDATE"
    SOURCE_FACT_MISMATCH = "SOURCE_FACT_MISMATCH"
    SOURCE_VERSION_UNPROVEN = "SOURCE_VERSION_UNPROVEN"
    SOURCE_AVAILABILITY_UNPROVEN = "SOURCE_AVAILABILITY_UNPROVEN"
    SEC_CONTEXT_UNSUPPORTED = "SEC_CONTEXT_UNSUPPORTED"
    SHARADAR_FIELD_UNSUPPORTED = "SHARADAR_FIELD_UNSUPPORTED"
    SEC_FACT_MISSING = "SEC_FACT_MISSING"
    SHARADAR_ROW_MISSING = "SHARADAR_ROW_MISSING"
    CONFLICTED = "CONFLICTED"
    PAGE_LIMIT_REACHED = "PAGE_LIMIT_REACHED"
    ATTEMPT_LIMIT_REACHED = "ATTEMPT_LIMIT_REACHED"
    SOURCE_ADMISSION_FAILED = "SOURCE_ADMISSION_FAILED"
    EVIDENCE_WRITE_FAILED = "EVIDENCE_WRITE_FAILED"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    UNSUPPORTED_QUARTERIZATION = "UNSUPPORTED_QUARTERIZATION"


class SecAvailabilityProof(StrEnum):
    PUBLIC_ARCHIVE_WITNESS = "PUBLIC_ARCHIVE_WITNESS"


class SharadarAvailabilityProof(StrEnum):
    IMMUTABLE_VERSION_WITNESS = "IMMUTABLE_VERSION_WITNESS"


@dataclass(frozen=True, slots=True)
class XbrlDimension:
    axis: str
    member: str

    def __post_init__(self) -> None:
        _safe_token(self.axis, "dimension axis")
        _safe_token(self.member, "dimension member")


@dataclass(frozen=True, slots=True)
class SecDocumentBinding:
    """One exact accession/member pair; independent sets cannot be cross-wired."""

    accession: str
    document_name: str

    def __post_init__(self) -> None:
        _accession(self.accession, "SEC document accession")
        _safe_token(self.document_name, "SEC document name")
        if "/" in self.document_name or "\\" in self.document_name:
            raise ValueError("SEC document name must be an exact member name")


@dataclass(frozen=True, slots=True)
class FieldMapping:
    """One fixed B1 sample hypothesis; this is not a blanket source mapping."""

    period_role: PeriodRole
    sf1_dimension: str
    sf1_field: str
    sec_concept: str
    pm2c_raw_key: str
    pm2c_unit: str
    provider_unit: str
    currency: str
    reporting_basis: str = "AS_REPORTED"
    scope_name: str = "security"

    def __post_init__(self) -> None:
        if not isinstance(self.period_role, PeriodRole):
            raise TypeError("period_role must be PeriodRole")
        _safe_token(self.sf1_dimension, "SF1 dimension")
        _safe_token(self.sf1_field, "SF1 field")
        _safe_token(self.sec_concept, "SEC concept")
        _safe_token(self.pm2c_raw_key, "PM2C RAW key")
        _safe_token(self.pm2c_unit, "PM2C unit")
        _safe_token(self.provider_unit, "provider unit")
        _safe_token(self.currency, "currency")
        _safe_token(self.reporting_basis, "reporting_basis")
        _safe_token(self.scope_name, "scope_name")


ANNUAL_REVENUE_MAPPING = FieldMapping(
    PeriodRole.ANNUAL,
    "ARY",
    "revenue",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "raw.fiscal.annual.revenue",
    "currency",
    "USD",
    "USD",
)
DIRECT_Q1_REVENUE_MAPPING = FieldMapping(
    PeriodRole.DIRECT_Q1,
    "ARQ",
    "revenue",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "raw.fiscal.quarter.revenue.discrete",
    "currency",
    "USD",
    "USD",
)
_SUPPORTED_MAPPINGS = {
    PeriodRole.ANNUAL: ANNUAL_REVENUE_MAPPING,
    PeriodRole.DIRECT_Q1: DIRECT_Q1_REVENUE_MAPPING,
}


@dataclass(frozen=True, slots=True)
class QualificationPlan:
    """Exact finite request and comparison contract for one target fact."""

    attempt_id: str
    expected_source_head: str
    expected_source_tree: str
    issuer_cik: str
    primary_accession: str
    sec_document_bindings: tuple[SecDocumentBinding, ...]
    sf1_table: str
    sf1_dimension: str
    ticker: str
    perma_ticker: str
    sf1_field: str
    field_mapping: FieldMapping
    catalog: ResearchCatalog
    target_entry: CatalogEntry
    target_subject: EvidenceSubject
    expected_raw_basis: EvidenceBasis
    expected_raw_scope: ScopeSpec
    expected_raw_period: PeriodSpec
    share_class: str | None
    context_id: str
    period_role: PeriodRole
    period_start: date
    period_end: date
    fiscal_year: int
    dimensions: tuple[XbrlDimension, ...]
    provider_unit: str
    currency: str
    sec_scale: int
    availability_cutoff: datetime
    evidence_root: str
    max_sec_response_bytes: int
    max_sharadar_page_bytes: int
    max_sec_documents: int
    max_sec_facts: int
    max_sharadar_pages: int
    max_sharadar_rows: int
    max_provider_attempts: int
    amendment_accession: str | None = None
    amendment_form: str | None = None
    early_8k_accession: str | None = None
    early_8k_form: str | None = None
    primary_form: str | None = None
    expected_calendar_date: date | None = None
    automatic_retry: bool = False

    def __post_init__(self) -> None:
        _safe_token(self.attempt_id, "attempt_id")
        for name in ("expected_source_head", "expected_source_tree"):
            value = getattr(self, name)
            if not isinstance(value, str) or not _GIT_OBJECT_RE.fullmatch(value):
                raise ValueError(f"{name} must be a lowercase 40-character Git ID")
        if not isinstance(self.issuer_cik, str) or not _CIK_RE.fullmatch(
            self.issuer_cik
        ):
            raise ValueError("issuer_cik must be a 10-digit CIK")
        _accession(self.primary_accession, "primary_accession")
        if self.amendment_accession is not None:
            _accession(self.amendment_accession, "amendment_accession")
        if self.early_8k_accession is not None:
            _accession(self.early_8k_accession, "early_8k_accession")
        accessions = tuple(
            item
            for item in (
                self.primary_accession,
                self.amendment_accession,
                self.early_8k_accession,
            )
            if item is not None
        )
        if len(set(accessions)) != len(accessions):
            raise ValueError("SEC accession roles must be distinct")

        bindings = _tuple(self.sec_document_bindings, "sec_document_bindings")
        if not bindings or len(bindings) > _ALLOWED_MAX_SEC_DOCUMENTS:
            raise ValueError("sec_document_bindings must contain one to three pairs")
        if not all(isinstance(item, SecDocumentBinding) for item in bindings):
            raise TypeError("sec_document_bindings must contain SecDocumentBinding")
        if len({(item.accession, item.document_name) for item in bindings}) != len(
            bindings
        ):
            raise ValueError("SEC accession/member pairs must be unique")
        object.__setattr__(self, "sec_document_bindings", bindings)
        if self.sf1_table != "SHARADAR/SF1":
            raise ValueError("only the frozen SHARADAR/SF1 table is supported")

        if not isinstance(self.field_mapping, FieldMapping):
            raise TypeError("field_mapping must be FieldMapping")
        if self.period_role not in (PeriodRole.ANNUAL, PeriodRole.DIRECT_Q1):
            raise ValueError(
                "Q2/Q3/Q4 need explicit reviewed component lineage and are unsupported"
            )
        if self.field_mapping != _SUPPORTED_MAPPINGS[self.period_role]:
            raise ValueError("field_mapping is not an exact frozen B1 mapping")
        if self.sf1_dimension != self.field_mapping.sf1_dimension:
            raise ValueError("SF1 dimension does not match the frozen mapping")
        if self.sf1_field != self.field_mapping.sf1_field:
            raise ValueError("SF1 field does not match the frozen mapping")
        _safe_token(self.ticker, "ticker")
        _safe_token(self.perma_ticker, "perma_ticker")
        _safe_token(self.context_id, "context_id")
        _safe_token(self.provider_unit, "provider_unit")
        _safe_token(self.currency, "currency")
        if (
            self.provider_unit != self.field_mapping.provider_unit
            or self.currency != self.field_mapping.currency
        ):
            raise ValueError("provider unit/currency do not match the frozen mapping")
        if not isinstance(self.catalog, ResearchCatalog):
            raise TypeError("catalog must be ResearchCatalog")
        if not isinstance(self.target_entry, CatalogEntry):
            raise TypeError("target_entry must be CatalogEntry")
        if self.target_entry.kind is not EntryKind.RAW:
            raise ValueError("target_entry must be a PM2C RAW catalog entry")
        if self.target_entry.key != self.field_mapping.pm2c_raw_key:
            raise ValueError("target RAW key does not match the frozen mapping")
        if self.target_entry.value_spec.kind is not ValueKind.DECIMAL:
            raise ValueError("target RAW entry must have a DECIMAL value")
        if self.target_entry.value_spec.unit != self.field_mapping.pm2c_unit:
            raise ValueError("target RAW amount unit does not match the frozen mapping")
        if self.target_entry.value_spec.currency != self.currency:
            raise ValueError("target RAW entry currency does not match the plan")
        if not isinstance(self.expected_raw_basis, EvidenceBasis):
            raise TypeError("expected_raw_basis must be EvidenceBasis")
        if not isinstance(self.expected_raw_scope, ScopeSpec):
            raise TypeError("expected_raw_scope must be ScopeSpec")
        if not isinstance(self.expected_raw_period, PeriodSpec):
            raise TypeError("expected_raw_period must be PeriodSpec")
        if self.target_entry.basis != self.expected_raw_basis:
            raise ValueError("target RAW basis differs from the exact plan basis")
        if self.target_entry.scope != self.expected_raw_scope:
            raise ValueError("target RAW scope differs from the exact plan scope")
        if self.target_entry.period_basis != self.expected_raw_period:
            raise ValueError("target RAW period differs from the exact plan period")
        if (
            self.expected_raw_basis.reporting_basis
            != self.field_mapping.reporting_basis
        ):
            raise ValueError("RAW reporting basis does not match the frozen mapping")
        if self.expected_raw_scope.name != self.field_mapping.scope_name:
            raise ValueError("RAW scope must be the exact frozen security scope")
        if (
            self.catalog.lookup(self.target_entry.key, self.target_entry.version)
            != self.target_entry
        ):
            raise ValueError("target entry is not the exact registered catalog entry")
        if not isinstance(self.target_subject, EvidenceSubject):
            raise TypeError("target_subject must be EvidenceSubject")
        if self.target_subject.issuer_id != self.issuer_cik:
            raise ValueError("target subject issuer_id must be the exact SEC CIK")
        if self.target_subject.security_id != self.perma_ticker:
            raise ValueError(
                "target subject security_id must be the exact Sharadar permaTicker"
            )
        if (
            self.target_subject.symbol is None
            or self.target_subject.symbol.value != self.ticker
        ):
            raise ValueError("target subject symbol must be the exact frozen ticker")
        if self.target_subject.share_class != self.share_class:
            raise ValueError("target subject share class differs from the exact plan")
        if (
            self.target_subject.portfolio_account_id is not None
            or self.target_subject.portfolio_snapshot_id is not None
        ):
            raise ValueError(
                "qualification target cannot include portfolio/account scope"
            )
        if self.target_subject.scope is not None:
            raise ValueError(
                "qualification target cannot include an unrelated typed scope"
            )
        if not isinstance(self.period_role, PeriodRole):
            raise TypeError("period_role must be PeriodRole")
        _date(self.period_start, "period_start")
        _date(self.period_end, "period_end")
        if self.period_start >= self.period_end:
            raise ValueError("period_start must precede period_end")
        if isinstance(self.fiscal_year, bool) or not isinstance(self.fiscal_year, int):
            raise TypeError("fiscal_year must be an integer")
        if self.fiscal_year < 1900 or self.fiscal_year > 9999:
            raise ValueError("fiscal_year is outside the supported date range")
        dimensions = _tuple(self.dimensions, "dimensions")
        if not all(isinstance(item, XbrlDimension) for item in dimensions):
            raise TypeError("dimensions must contain XbrlDimension values")
        if len({item.axis for item in dimensions}) != len(dimensions):
            raise ValueError("XBRL dimensions must not repeat an axis")
        object.__setattr__(
            self,
            "dimensions",
            tuple(sorted(dimensions, key=lambda item: (item.axis, item.member))),
        )
        if isinstance(self.sec_scale, bool) or not isinstance(self.sec_scale, int):
            raise TypeError("sec_scale must be an integer")
        if abs(self.sec_scale) > 12:
            raise ValueError("sec_scale is outside the bounded numeric contract")
        object.__setattr__(
            self,
            "availability_cutoff",
            normalize_utc(self.availability_cutoff, "availability_cutoff"),
        )
        _f_root(self.evidence_root)
        for name, upper in (
            ("max_sec_response_bytes", _ALLOWED_MAX_BYTES),
            ("max_sharadar_page_bytes", _ALLOWED_MAX_BYTES),
            ("max_sec_documents", _ALLOWED_MAX_SEC_DOCUMENTS),
            ("max_sec_facts", _ALLOWED_MAX_SEC_FACTS),
            ("max_sharadar_pages", _ALLOWED_MAX_SHARADAR_PAGES),
            ("max_sharadar_rows", _ALLOWED_MAX_SHARADAR_ROWS),
            ("max_provider_attempts", _ALLOWED_MAX_PROVIDER_ATTEMPTS),
        ):
            _positive_bounded_int(getattr(self, name), name, upper)
        if self.max_sec_documents < len(bindings):
            raise ValueError("max_sec_documents must cover every named member")
        if (
            self.max_provider_attempts
            > self.max_sec_documents + self.max_sharadar_pages
        ):
            raise ValueError(
                "provider attempts cannot exceed named SEC docs plus pages"
            )
        if self.amendment_accession is not None and self.amendment_form is None:
            raise ValueError("amendment_accession requires amendment_form")
        if self.amendment_accession is None and self.amendment_form is not None:
            raise ValueError("amendment_form requires amendment_accession")
        if self.early_8k_accession is not None and self.early_8k_form is None:
            raise ValueError("early_8k_accession requires early_8k_form")
        if self.early_8k_accession is None and self.early_8k_form is not None:
            raise ValueError("early_8k_form requires early_8k_accession")
        expected_form = "10-K" if self.period_role is PeriodRole.ANNUAL else "10-Q"
        if self.primary_form is None:
            object.__setattr__(self, "primary_form", expected_form)
        elif self.primary_form != expected_form:
            raise ValueError("primary_form does not match the frozen period role")
        if (
            self.amendment_form is not None
            and self.amendment_form != f"{expected_form}/A"
        ):
            raise ValueError("amendment_form must be the exact primary form amendment")
        if self.early_8k_form is not None and self.early_8k_form != "8-K":
            raise ValueError("early_8k_form must be 8-K")
        bound_accessions = {item.accession for item in bindings}
        required_accessions = {self.primary_accession}
        if self.amendment_accession is not None:
            required_accessions.add(self.amendment_accession)
        if self.early_8k_accession is not None:
            required_accessions.add(self.early_8k_accession)
        if not required_accessions.issubset(bound_accessions):
            raise ValueError(
                "every enabled SEC lineage role needs an exact member binding"
            )
        if any(item.accession not in required_accessions for item in bindings):
            raise ValueError("SEC document binding contains an unapproved accession")
        if self.expected_calendar_date is not None:
            _date(self.expected_calendar_date, "expected_calendar_date")
        if not isinstance(self.automatic_retry, bool):
            raise TypeError("automatic_retry must be bool")
        if self.automatic_retry:
            raise ValueError("automatic retry is forbidden")

    @property
    def plan_id(self) -> UUID:
        """Stable semantic plan identity; evidence_root is deliberately excluded."""

        return research_identity(
            "pm2d-b1-qualification-plan-v1",
            self.attempt_id,
            self.expected_source_head,
            self.expected_source_tree,
            self.issuer_cik,
            self.primary_accession,
            self.primary_form,
            self.amendment_accession,
            self.amendment_form,
            self.early_8k_accession,
            self.early_8k_form,
            tuple(
                (item.accession, item.document_name)
                for item in self.sec_document_bindings
            ),
            self.sf1_table,
            self.sf1_dimension,
            self.ticker,
            self.perma_ticker,
            self.sf1_field,
            (
                self.field_mapping.period_role.value,
                self.field_mapping.sf1_dimension,
                self.field_mapping.sf1_field,
                self.field_mapping.sec_concept,
                self.field_mapping.pm2c_raw_key,
                self.field_mapping.pm2c_unit,
                self.field_mapping.provider_unit,
                self.field_mapping.currency,
                self.field_mapping.reporting_basis,
                self.field_mapping.scope_name,
            ),
            self.catalog.catalog_id,
            self.target_entry.entry_id,
            self.target_subject.identity_material,
            self.expected_raw_basis.calendar,
            self.expected_raw_basis.adjustment.value,
            self.expected_raw_basis.data_basis,
            self.expected_raw_basis.reporting_basis,
            self.expected_raw_scope.name,
            self.expected_raw_scope.anchor,
            self.expected_raw_period.name,
            self.expected_raw_period.relation,
            self.expected_raw_period.anchor,
            self.share_class,
            self.context_id,
            self.period_role.value,
            self.period_start.isoformat(),
            self.period_end.isoformat(),
            self.fiscal_year,
            tuple((item.axis, item.member) for item in self.dimensions),
            self.provider_unit,
            self.currency,
            self.sec_scale,
            self.availability_cutoff,
            self.max_sec_response_bytes,
            self.max_sharadar_page_bytes,
            self.max_sec_documents,
            self.max_sec_facts,
            self.max_sharadar_pages,
            self.max_sharadar_rows,
            self.max_provider_attempts,
            None
            if self.expected_calendar_date is None
            else self.expected_calendar_date.isoformat(),
        )

    def source_matches(self, head: str, tree: str) -> bool:
        return head == self.expected_source_head and tree == self.expected_source_tree

    @property
    def sec_document_names(self) -> tuple[str, ...]:
        """Compatibility projection; SEC requests must use paired bindings."""

        return tuple(item.document_name for item in self.sec_document_bindings)

    def to_manifest(self) -> dict[str, object]:
        """Return a safe plan projection for operator evidence (never credentials)."""

        return {
            "schema_version": "pm2d-b1-v1",
            "plan_id": str(self.plan_id),
            "attempt_id": self.attempt_id,
            "expected_source_head": self.expected_source_head,
            "expected_source_tree": self.expected_source_tree,
            "issuer_cik": self.issuer_cik,
            "primary_accession": self.primary_accession,
            "primary_form": self.primary_form,
            "amendment_accession": self.amendment_accession,
            "amendment_form": self.amendment_form,
            "early_8k_accession": self.early_8k_accession,
            "early_8k_form": self.early_8k_form,
            "sec_document_bindings": [
                {"accession": item.accession, "document_name": item.document_name}
                for item in self.sec_document_bindings
            ],
            "sf1_table": self.sf1_table,
            "sf1_dimension": self.sf1_dimension,
            "ticker": self.ticker,
            "perma_ticker": self.perma_ticker,
            "sf1_field": self.sf1_field,
            "sec_concept": self.field_mapping.sec_concept,
            "pm2c_raw_key": self.field_mapping.pm2c_raw_key,
            "target_entry_id": str(self.target_entry.entry_id),
            "target_subject_id": str(self.target_subject.subject_id),
            "share_class": self.share_class,
            "raw_basis": {
                "calendar": self.expected_raw_basis.calendar,
                "adjustment": self.expected_raw_basis.adjustment.value,
                "data_basis": self.expected_raw_basis.data_basis,
                "reporting_basis": self.expected_raw_basis.reporting_basis,
            },
            "raw_scope": {
                "name": self.expected_raw_scope.name,
                "anchor": self.expected_raw_scope.anchor,
            },
            "raw_period": {
                "name": self.expected_raw_period.name,
                "relation": self.expected_raw_period.relation,
                "anchor": self.expected_raw_period.anchor,
            },
            "context_id": self.context_id,
            "period_role": self.period_role.value,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "fiscal_year": self.fiscal_year,
            "dimensions": [
                {"axis": item.axis, "member": item.member} for item in self.dimensions
            ],
            "target_unit": self.field_mapping.pm2c_unit,
            "provider_unit": self.provider_unit,
            "currency": self.currency,
            "sec_scale": self.sec_scale,
            "availability_cutoff": self.availability_cutoff.isoformat(),
            "evidence_root": self.evidence_root,
            "limits": {
                "max_sec_response_bytes": self.max_sec_response_bytes,
                "max_sharadar_page_bytes": self.max_sharadar_page_bytes,
                "max_sec_documents": self.max_sec_documents,
                "max_sec_facts": self.max_sec_facts,
                "max_sharadar_pages": self.max_sharadar_pages,
                "max_sharadar_rows": self.max_sharadar_rows,
                "max_provider_attempts": self.max_provider_attempts,
            },
            "automatic_retry": False,
        }


@dataclass(frozen=True, slots=True)
class SecFactCandidate:
    locator: str
    concept: str
    context_id: str
    context_cik: str
    period_start: date
    period_end: date
    dimensions: tuple[XbrlDimension, ...]
    unit: str
    currency: str
    scale: int
    decimals: str | None
    value: Decimal
    source_record_id: str | None = None


@dataclass(frozen=True, slots=True)
class ParsedSecResponse:
    issuer_cik: str
    accession: str
    form: str
    accepted_at: datetime | None
    filing_date: date
    report_period: date
    document_name: str
    facts: tuple[SecFactCandidate, ...]
    content_sha256: str
    content_length: int
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class SharadarRowCandidate:
    locator: str
    ticker: str
    perma_ticker: str
    report_period: date
    calendar_date: date | None
    datekey: date | None
    lastupdated: date | None
    field_present: bool
    value: Decimal | None
    source_record_id: str | None = None


@dataclass(frozen=True, slots=True)
class ParsedSharadarPage:
    table: str
    dimension: str
    requested_cursor: str | None
    next_cursor: str | None
    rows: tuple[SharadarRowCandidate, ...]
    content_sha256: str
    content_length: int
    observed_at: datetime

    @property
    def terminal(self) -> bool:
        return self.next_cursor is None


@dataclass(frozen=True, slots=True)
class SecProvenanceWitness:
    """Operator-supplied SEC public visibility proof for one exact fact locator."""

    record_locator: str
    response_sha256: str
    source_version: str
    public_available_from: datetime
    visible_until: datetime
    proof_reference: str
    source_record_id: str | None = None
    proof_basis: SecAvailabilityProof = SecAvailabilityProof.PUBLIC_ARCHIVE_WITNESS

    def __post_init__(self) -> None:
        _safe_token(self.record_locator, "SEC record_locator")
        _sha256(self.response_sha256, "SEC response_sha256")
        _safe_token(self.source_version, "SEC source_version")
        _safe_token(self.proof_reference, "SEC proof_reference")
        if self.source_record_id is not None:
            _safe_token(self.source_record_id, "SEC source_record_id")
        if not isinstance(self.proof_basis, SecAvailabilityProof):
            raise TypeError("proof_basis must be SecAvailabilityProof")
        object.__setattr__(
            self,
            "public_available_from",
            normalize_utc(self.public_available_from, "SEC public_available_from"),
        )
        until = normalize_utc(self.visible_until, "SEC visible_until")
        if until < self.public_available_from:
            raise ValueError("SEC visibility end precedes publication")
        object.__setattr__(self, "visible_until", until)


@dataclass(frozen=True, slots=True)
class SharadarProvenanceWitness:
    """Operator-supplied exact SF1 immutable-version and period-grain proof."""

    record_locator: str
    response_sha256: str
    source_version: str
    vendor_available_from: datetime
    visible_until: datetime
    proof_reference: str
    sec_accession: str
    sec_record_locator: str
    sec_response_sha256: str
    pm2c_raw_key: str
    sf1_field: str
    sec_concept: str
    unit: str
    currency: str
    period_role: PeriodRole
    period_start: date
    period_end: date
    fiscal_year: int
    source_record_id: str | None = None
    proof_basis: SharadarAvailabilityProof = (
        SharadarAvailabilityProof.IMMUTABLE_VERSION_WITNESS
    )

    def __post_init__(self) -> None:
        _safe_token(self.record_locator, "SF1 record_locator")
        _sha256(self.response_sha256, "SF1 response_sha256")
        _safe_token(self.source_version, "SF1 source_version")
        _safe_token(self.proof_reference, "SF1 proof_reference")
        if self.source_record_id is not None:
            _safe_token(self.source_record_id, "SF1 source_record_id")
        _accession(self.sec_accession, "SF1 witness SEC accession")
        _safe_token(self.sec_record_locator, "SF1 witness SEC record_locator")
        _sha256(self.sec_response_sha256, "SF1 witness SEC response_sha256")
        _safe_token(self.pm2c_raw_key, "SF1 witness PM2C RAW key")
        _safe_token(self.sf1_field, "SF1 witness field")
        _safe_token(self.sec_concept, "SF1 witness SEC concept")
        _safe_token(self.unit, "SF1 witness unit")
        _safe_token(self.currency, "SF1 witness currency")
        if not isinstance(self.proof_basis, SharadarAvailabilityProof):
            raise TypeError("proof_basis must be SharadarAvailabilityProof")
        if not isinstance(self.period_role, PeriodRole):
            raise TypeError("period_role must be PeriodRole")
        _date(self.period_start, "SF1 period_start")
        _date(self.period_end, "SF1 period_end")
        if self.period_start >= self.period_end:
            raise ValueError("SF1 period_start must precede period_end")
        if isinstance(self.fiscal_year, bool) or not isinstance(self.fiscal_year, int):
            raise TypeError("SF1 fiscal_year must be an integer")
        object.__setattr__(
            self,
            "vendor_available_from",
            normalize_utc(self.vendor_available_from, "vendor_available_from"),
        )
        until = normalize_utc(self.visible_until, "SF1 visible_until")
        if until < self.vendor_available_from:
            raise ValueError("SF1 visibility end precedes version availability")
        object.__setattr__(self, "visible_until", until)


@dataclass(frozen=True, slots=True)
class QualificationResult:
    outcome: QualificationOutcome
    reason: str
    plan_id: UUID
    selected_sec_fact: SecFactCandidate | None = None
    selected_sharadar_row: SharadarRowCandidate | None = None
    sec_available_at: datetime | None = None
    sf1_available_at: datetime | None = None
    available_at: datetime | None = None
    observed_at: datetime | None = None
    sec_response_sha256: str | None = None
    sf1_response_sha256: str | None = None
    sec_source_version: str | None = None
    sf1_source_version: str | None = None
    sec_proof_reference: str | None = None
    sf1_proof_reference: str | None = None
    visibility_ends_at: datetime | None = None
    _plan: QualificationPlan | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, QualificationOutcome):
            raise TypeError("outcome must be QualificationOutcome")
        _safe_text(self.reason, "reason")
        if not isinstance(self.plan_id, UUID):
            raise TypeError("plan_id must be a UUID")
        for name in (
            "sec_available_at",
            "sf1_available_at",
            "available_at",
            "observed_at",
            "visibility_ends_at",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, normalize_utc(value, name))
        for name in ("sec_response_sha256", "sf1_response_sha256"):
            value = getattr(self, name)
            if value is not None:
                _sha256(value, name)
        if self.outcome is QualificationOutcome.QUALIFIED_CANDIDATE:
            required = (
                self.selected_sec_fact,
                self.selected_sharadar_row,
                self.sec_available_at,
                self.sf1_available_at,
                self.available_at,
                self.observed_at,
                self.sec_response_sha256,
                self.sf1_response_sha256,
                self.sec_source_version,
                self.sf1_source_version,
                self.sec_proof_reference,
                self.sf1_proof_reference,
                self._plan,
            )
            if any(item is None for item in required):
                raise ValueError("qualified candidate is missing bridge evidence")

    def to_source_fact(self) -> SourceFact:
        """Mint the inert PM2C candidate only after every proof succeeded."""

        if (
            self.outcome is not QualificationOutcome.QUALIFIED_CANDIDATE
            or self._plan is None
        ):
            raise QualificationInputError(
                "only a qualified candidate can bridge to PM2C"
            )
        assert self.selected_sec_fact is not None
        assert self.selected_sharadar_row is not None
        assert self.available_at is not None
        assert self.observed_at is not None
        assert self.sec_response_sha256 is not None
        assert self.sf1_response_sha256 is not None
        assert self.sec_source_version is not None
        assert self.sf1_source_version is not None
        assert self.sec_proof_reference is not None
        assert self.sf1_proof_reference is not None
        content_digest = _combined_digest(
            (self.sec_response_sha256, self.sf1_response_sha256)
        )
        source_identity = "synthetic:pm2d-b1:sec-sharadar-candidate-v1"
        source_version = f"sec:{self.sec_source_version}:sf1:{self.sf1_source_version}"
        source_record_id = (
            f"sec:{self.sec_proof_reference}:{self.selected_sec_fact.locator}:"
            f"sf1:{self.sf1_proof_reference}:{self.selected_sharadar_row.locator}"
        )
        value = self.selected_sharadar_row.value
        if value is None:
            raise QualificationInputError("qualified SF1 row unexpectedly has no value")
        timeframe = EvidenceTimeframe(
            EvidenceTimeframeKind.PERIOD,
            _utc_midnight(self._plan.period_start),
            _utc_midnight(self._plan.period_end),
            anchor=f"FY{self._plan.fiscal_year}:{self._plan.period_role.value}",
        )
        source_fact = SourceFact(
            entry=self._plan.target_entry,
            subject=self._plan.target_subject,
            source_identity=source_identity,
            source_version=source_version,
            outcome=EvidenceOutcome(AvailabilityStatus.AVAILABLE, value),
            timeframe=timeframe,
            available_at=self.available_at,
            observed_at=self.observed_at,
            revision_id=source_version,
            source_record_id=source_record_id,
            source_content_digest=content_digest,
        )
        witness = VersionAsOfWitness(
            source_fact_id=source_fact.evidence_id,
            source_version=source_fact.source_version,
            publication_at=self.available_at,
            source_record_id=source_record_id,
            source_content_digest=content_digest,
            source_identity=source_identity,
            revision_id=source_version,
            visibility_ends_at=self.visibility_ends_at,
        )
        return SourceFact(
            entry=source_fact.entry,
            subject=source_fact.subject,
            source_identity=source_fact.source_identity,
            source_version=source_fact.source_version,
            outcome=source_fact.outcome,
            timeframe=source_fact.timeframe,
            available_at=source_fact.available_at,
            observed_at=source_fact.observed_at,
            effective_at=source_fact.effective_at,
            revision_id=source_fact.revision_id,
            revision_predecessor=source_fact.revision_predecessor,
            revision_predecessor_available_at=source_fact.revision_predecessor_available_at,
            source_record_id=source_fact.source_record_id,
            source_content_digest=source_fact.source_content_digest,
            as_of_witness=witness,
        )


def parse_sec_response(
    raw_bytes: bytes,
    plan: QualificationPlan,
    observed_at: datetime,
    *,
    max_facts: int | None = None,
) -> ParsedSecResponse:
    """Parse one exact SEC-member fake envelope under the frozen plan bounds."""

    _bytes_within(raw_bytes, plan.max_sec_response_bytes, "SEC response")
    payload = _load_json_object(raw_bytes, "SEC response")
    _require_keys(
        payload,
        required={
            "issuer_cik",
            "accession",
            "form",
            "filing_date",
            "report_period",
            "document_name",
            "facts",
        },
        optional={"accepted_at"},
        name="SEC response",
    )
    issuer_cik = _safe_token(_string(payload["issuer_cik"], "issuer_cik"), "issuer_cik")
    if not _CIK_RE.fullmatch(issuer_cik):
        raise QualificationInputError("issuer_cik must be a 10-digit CIK")
    accession = _safe_token(_string(payload["accession"], "accession"), "accession")
    _accession(accession, "accession")
    form = _string(payload["form"], "form")
    if form not in {"10-K", "10-K/A", "10-Q", "10-Q/A", "8-K"}:
        raise QualificationInputError("unsupported SEC form")
    filing_date = _parse_date(payload["filing_date"], "filing_date")
    report_period = _parse_date(payload["report_period"], "report_period")
    document_name = _safe_token(
        _string(payload["document_name"], "document_name"), "document_name"
    )
    if "/" in document_name or "\\" in document_name:
        raise QualificationInputError("document_name must be an exact SEC member")
    fact_limit = (
        plan.max_sec_facts if max_facts is None else min(max_facts, plan.max_sec_facts)
    )
    _positive_bounded_int(fact_limit, "max_facts", plan.max_sec_facts)
    facts_raw = payload["facts"]
    if not isinstance(facts_raw, list) or len(facts_raw) > fact_limit:
        raise QualificationInputError("facts must be a bounded JSON array")
    facts: list[SecFactCandidate] = []
    for index, raw_fact in enumerate(facts_raw):
        if not isinstance(raw_fact, dict):
            raise QualificationInputError("each SEC fact must be an object")
        _require_keys(
            raw_fact,
            required={
                "concept",
                "context_id",
                "context_cik",
                "period_start",
                "period_end",
                "dimensions",
                "unit",
                "currency",
                "scale",
                "value",
            },
            optional={"decimals", "record_id"},
            name="SEC fact",
        )
        dimensions_raw = raw_fact["dimensions"]
        if (
            not isinstance(dimensions_raw, list)
            or len(dimensions_raw) > _MAX_DIMENSIONS
        ):
            raise QualificationInputError("SEC fact dimensions must be an array")
        dimensions: list[XbrlDimension] = []
        for item in dimensions_raw:
            if not isinstance(item, dict):
                raise QualificationInputError("each XBRL dimension must be an object")
            _require_keys(
                item, required={"axis", "member"}, optional=set(), name="XBRL dimension"
            )
            dimensions.append(
                XbrlDimension(
                    _safe_token(
                        _string(item["axis"], "dimension axis"), "dimension axis"
                    ),
                    _safe_token(
                        _string(item["member"], "dimension member"), "dimension member"
                    ),
                )
            )
        if len({item.axis for item in dimensions}) != len(dimensions):
            raise QualificationInputError("SEC fact repeats an XBRL dimension axis")
        decimals = raw_fact.get("decimals")
        if decimals is not None:
            decimals = _safe_token(_string(decimals, "SEC decimals"), "SEC decimals")
        source_record_id = raw_fact.get("record_id")
        if source_record_id is not None:
            source_record_id = _safe_token(
                _string(source_record_id, "SEC record_id"), "SEC record_id"
            )
        scale = _integer(raw_fact["scale"], "SEC scale")
        value = _decimal(raw_fact["value"], "SEC fact value")
        facts.append(
            SecFactCandidate(
                locator=f"synthetic-sec-member-fact:{document_name}:{index}",
                concept=_safe_token(
                    _string(raw_fact["concept"], "SEC concept"), "SEC concept"
                ),
                context_id=_safe_token(
                    _string(raw_fact["context_id"], "SEC context_id"), "SEC context_id"
                ),
                context_cik=_safe_token(
                    _string(raw_fact["context_cik"], "SEC context_cik"),
                    "SEC context_cik",
                ),
                period_start=_parse_date(raw_fact["period_start"], "SEC period_start"),
                period_end=_parse_date(raw_fact["period_end"], "SEC period_end"),
                dimensions=tuple(
                    sorted(dimensions, key=lambda item: (item.axis, item.member))
                ),
                unit=_safe_token(_string(raw_fact["unit"], "SEC unit"), "SEC unit"),
                currency=_safe_token(
                    _string(raw_fact["currency"], "SEC currency"), "SEC currency"
                ),
                scale=scale,
                decimals=decimals,
                value=value,
                source_record_id=source_record_id,
            )
        )
    accepted_at = payload.get("accepted_at")
    if accepted_at is not None:
        accepted_at = _parse_datetime(accepted_at, "SEC accepted_at")
    return ParsedSecResponse(
        issuer_cik=issuer_cik,
        accession=accession,
        form=form,
        accepted_at=accepted_at,
        filing_date=filing_date,
        report_period=report_period,
        document_name=document_name,
        facts=tuple(facts),
        content_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        content_length=len(raw_bytes),
        observed_at=normalize_utc(observed_at, "SEC observed_at"),
    )


def parse_sharadar_page(
    raw_bytes: bytes,
    plan: QualificationPlan,
    observed_at: datetime,
    requested_cursor: str | None = None,
    *,
    max_rows: int | None = None,
) -> ParsedSharadarPage:
    """Parse one exact SF1 fake page; cursor continuation comes from its bytes."""

    _bytes_within(raw_bytes, plan.max_sharadar_page_bytes, "SF1 page")
    if requested_cursor is not None:
        _safe_token(requested_cursor, "requested_cursor")
    payload = _load_json_object(raw_bytes, "SF1 page")
    _require_keys(
        payload,
        required={"table", "dimension", "rows"},
        optional={"next_cursor"},
        name="SF1 page",
    )
    table = _string(payload["table"], "SF1 table")
    dimension = _safe_token(
        _string(payload["dimension"], "SF1 dimension"), "SF1 dimension"
    )
    if table != "SHARADAR/SF1":
        raise QualificationInputError("only the frozen SHARADAR/SF1 table is supported")
    if dimension not in _KNOWN_SHARADAR_DIMENSIONS:
        raise QualificationInputError("unknown SF1 dimension")
    next_cursor = payload.get("next_cursor")
    if next_cursor is not None:
        next_cursor = _string(next_cursor, "next_cursor")
        _safe_token(next_cursor, "next_cursor")
        if next_cursor == requested_cursor:
            raise QualificationInputError("SF1 cursor repeated")
    row_limit = (
        plan.max_sharadar_rows
        if max_rows is None
        else min(max_rows, plan.max_sharadar_rows)
    )
    _positive_bounded_int(row_limit, "max_rows", plan.max_sharadar_rows)
    rows_raw = payload["rows"]
    if not isinstance(rows_raw, list) or len(rows_raw) > row_limit:
        raise QualificationInputError("rows must be a bounded JSON array")
    rows: list[SharadarRowCandidate] = []
    for index, raw_row in enumerate(rows_raw):
        if not isinstance(raw_row, dict):
            raise QualificationInputError("each SF1 row must be an object")
        _require_keys(
            raw_row,
            required={"ticker", "permaTicker", "reportperiod", "fields"},
            optional={"calendardate", "datekey", "lastupdated", "row_id"},
            name="SF1 row",
        )
        fields = raw_row["fields"]
        if not isinstance(fields, dict):
            raise QualificationInputError("SF1 fields must be an object")
        unknown_fields = set(fields) - {plan.sf1_field}
        if unknown_fields:
            raise QualificationInputError("SF1 row contains unrequested fields")
        field_present = plan.sf1_field in fields
        value = (
            _decimal(fields[plan.sf1_field], "SF1 selected field", allow_null=True)
            if field_present
            else None
        )
        row_id = raw_row.get("row_id")
        if row_id is not None:
            _safe_token(_string(row_id, "SF1 row_id"), "SF1 row_id")
        rows.append(
            SharadarRowCandidate(
                locator=f"synthetic-sf1-page-row:{index}",
                ticker=_safe_token(
                    _string(raw_row["ticker"], "SF1 ticker"), "SF1 ticker"
                ),
                perma_ticker=_safe_token(
                    _string(raw_row["permaTicker"], "SF1 permaTicker"),
                    "SF1 permaTicker",
                ),
                report_period=_parse_date(raw_row["reportperiod"], "SF1 reportperiod"),
                calendar_date=_optional_date(raw_row, "calendardate"),
                datekey=_optional_date(raw_row, "datekey"),
                lastupdated=_optional_date(raw_row, "lastupdated"),
                field_present=field_present,
                value=value,
                source_record_id=None
                if row_id is None
                else _string(row_id, "SF1 row_id"),
            )
        )
    return ParsedSharadarPage(
        table=table,
        dimension=dimension,
        requested_cursor=requested_cursor,
        next_cursor=next_cursor,
        rows=tuple(rows),
        content_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        content_length=len(raw_bytes),
        observed_at=normalize_utc(observed_at, "SF1 observed_at"),
    )


def compare_candidate(
    plan: QualificationPlan,
    sec_responses: tuple[ParsedSecResponse, ...],
    sf1_pages: tuple[ParsedSharadarPage, ...],
    sec_witnesses: tuple[SecProvenanceWitness, ...],
    sharadar_witnesses: tuple[SharadarProvenanceWitness, ...],
    observed_at: datetime,
) -> QualificationResult:
    """Compare only the exact frozen target; never searches for a fallback."""

    if not isinstance(plan, QualificationPlan):
        raise TypeError("plan must be QualificationPlan")
    observed_at = normalize_utc(observed_at, "observed_at")
    sec_responses = _tuple(sec_responses, "sec_responses")
    sf1_pages = _tuple(sf1_pages, "sf1_pages")
    sec_witnesses = _tuple(sec_witnesses, "sec_witnesses")
    sharadar_witnesses = _tuple(sharadar_witnesses, "sharadar_witnesses")
    if not all(isinstance(item, ParsedSecResponse) for item in sec_responses):
        raise TypeError("sec_responses must contain ParsedSecResponse")
    if not all(isinstance(item, ParsedSharadarPage) for item in sf1_pages):
        raise TypeError("sf1_pages must contain ParsedSharadarPage")
    if not all(isinstance(item, SecProvenanceWitness) for item in sec_witnesses):
        raise TypeError("sec_witnesses must contain SecProvenanceWitness")
    if not all(
        isinstance(item, SharadarProvenanceWitness) for item in sharadar_witnesses
    ):
        raise TypeError("sharadar_witnesses must contain SharadarProvenanceWitness")

    sec_fact_count = sum(len(item.facts) for item in sec_responses)
    sf1_row_count = sum(len(item.rows) for item in sf1_pages)
    if (
        len(sec_responses) > plan.max_sec_documents
        or sec_fact_count > plan.max_sec_facts
    ):
        return _result(
            plan,
            QualificationOutcome.PAGE_LIMIT_REACHED,
            "SEC document/fact limit reached",
        )
    if (
        len(sf1_pages) > plan.max_sharadar_pages
        or sf1_row_count > plan.max_sharadar_rows
    ):
        return _result(
            plan, QualificationOutcome.PAGE_LIMIT_REACHED, "SF1 page/row limit reached"
        )
    if len(sec_responses) + len(sf1_pages) > plan.max_provider_attempts:
        return _result(
            plan,
            QualificationOutcome.ATTEMPT_LIMIT_REACHED,
            "provider attempt limit reached",
        )

    expected_pairs = tuple(
        (item.accession, item.document_name) for item in plan.sec_document_bindings
    )
    received_pairs = tuple(
        (item.accession, item.document_name) for item in sec_responses
    )
    if any(pair not in expected_pairs for pair in received_pairs):
        return _result(
            plan,
            QualificationOutcome.SOURCE_FACT_MISMATCH,
            "SEC accession/member pair is outside the exact plan",
        )
    if len(set(received_pairs)) != len(received_pairs):
        return _result(
            plan,
            QualificationOutcome.CONFLICTED,
            "duplicate SEC accession/member response",
        )
    if set(received_pairs) != set(expected_pairs):
        return _result(
            plan,
            QualificationOutcome.SEC_FACT_MISSING,
            "one or more exact SEC accession/member responses are absent",
        )
    if any(item.issuer_cik != plan.issuer_cik for item in sec_responses):
        return _result(
            plan,
            QualificationOutcome.SOURCE_FACT_MISMATCH,
            "SEC issuer does not match the exact plan",
        )
    expected_forms = {
        plan.primary_accession: plan.primary_form,
        plan.amendment_accession: plan.amendment_form,
        plan.early_8k_accession: plan.early_8k_form,
    }
    if any(item.form != expected_forms[item.accession] for item in sec_responses):
        return _result(
            plan,
            QualificationOutcome.SOURCE_FACT_MISMATCH,
            "SEC filing form does not match the exact accession role",
        )
    primary_responses = tuple(
        item for item in sec_responses if item.accession == plan.primary_accession
    )
    if any(item.report_period != plan.period_end for item in primary_responses):
        return _result(
            plan,
            QualificationOutcome.SOURCE_FACT_MISMATCH,
            "SEC report period does not match the exact target",
        )
    primary_matches = _mapped_facts(primary_responses, plan)
    if not primary_matches:
        return _result(
            plan,
            QualificationOutcome.SEC_FACT_MISSING,
            "exact SEC concept is absent from the primary accession",
        )
    primary_context = _exact_context_facts(primary_matches, plan)
    if not primary_context:
        return _result(
            plan,
            QualificationOutcome.SEC_CONTEXT_UNSUPPORTED,
            "SEC context, period, issuer, or dimensions do not match",
        )
    if len(primary_context) != 1:
        return _result(
            plan,
            QualificationOutcome.CONFLICTED,
            "multiple exact SEC facts match the frozen context",
        )
    primary_response, sec_fact = primary_context[0]
    if (
        sec_fact.unit != plan.provider_unit
        or sec_fact.currency != plan.currency
        or sec_fact.scale != plan.sec_scale
    ):
        return _result(
            plan,
            QualificationOutcome.SOURCE_FACT_MISMATCH,
            "SEC unit, currency, or scale differs from the frozen mapping",
        )
    scaled_sec_value = _apply_scale(sec_fact.value, sec_fact.scale)

    amendment_response: ParsedSecResponse | None = None
    amendment_fact: SecFactCandidate | None = None
    if plan.amendment_accession is not None:
        amendment_responses = tuple(
            item for item in sec_responses if item.accession == plan.amendment_accession
        )
        amendment_matches = _mapped_facts(amendment_responses, plan)
        if not amendment_matches:
            return _result(
                plan,
                QualificationOutcome.SEC_FACT_MISSING,
                "enabled amendment has no exact mapped fact",
            )
        amendment_context = _exact_context_facts(amendment_matches, plan)
        if not amendment_context:
            return _result(
                plan,
                QualificationOutcome.SEC_CONTEXT_UNSUPPORTED,
                "amendment context does not match the exact target",
            )
        if len(amendment_context) != 1:
            return _result(
                plan,
                QualificationOutcome.CONFLICTED,
                "multiple amendment facts match the exact context",
            )
        amendment_response, amendment_fact = amendment_context[0]
        amendment_witness = _exact_sec_witness(
            sec_witnesses, amendment_fact.locator, amendment_response.content_sha256
        )
        if not _valid_sec_witness(
            amendment_witness, amendment_response, amendment_fact
        ):
            return _result(
                plan,
                QualificationOutcome.SOURCE_VERSION_UNPROVEN,
                "amendment version is not separately bound",
            )
        # The amendment is retained as a distinct later version. Its value never
        # replaces the primary accession's original value in this candidate.

    early_response: ParsedSecResponse | None = None
    early_fact: SecFactCandidate | None = None
    if plan.early_8k_accession is not None:
        early_responses = tuple(
            item for item in sec_responses if item.accession == plan.early_8k_accession
        )
        early_matches = _mapped_facts(early_responses, plan)
        exact_early = tuple(
            (response, fact)
            for response, fact in _exact_context_facts(early_matches, plan)
            if fact.unit == sec_fact.unit
            and fact.currency == sec_fact.currency
            and fact.scale == sec_fact.scale
            and fact.decimals == sec_fact.decimals
            and _apply_scale(fact.value, fact.scale) == scaled_sec_value
        )
        if not exact_early:
            return _result(
                plan,
                QualificationOutcome.SOURCE_FACT_MISMATCH,
                "early 8-K does not prove the exact same SEC fact lineage",
            )
        if len(exact_early) != 1:
            return _result(
                plan,
                QualificationOutcome.CONFLICTED,
                "multiple early 8-K facts match the exact lineage",
            )
        early_response, early_fact = exact_early[0]
        early_witness = _exact_sec_witness(
            sec_witnesses, early_fact.locator, early_response.content_sha256
        )
        if not _valid_sec_witness(early_witness, early_response, early_fact):
            return _result(
                plan,
                QualificationOutcome.SOURCE_VERSION_UNPROVEN,
                "early 8-K public fact witness is absent or mismatched",
            )
        # The early 8-K is corroboration only. It cannot lower either source's
        # independently witnessed availability boundary or replace the primary.

    if not sf1_pages:
        return _result(
            plan,
            QualificationOutcome.SHARADAR_ROW_MISSING,
            "no SF1 response page was received",
        )
    if sf1_pages[0].requested_cursor is not None:
        return _result(
            plan,
            QualificationOutcome.PROVIDER_FAILURE,
            "first SF1 page must use the exact initial cursor",
        )
    used_cursors: set[str] = set()
    expected_cursor: str | None = None
    for index, page in enumerate(sf1_pages):
        if page.table != plan.sf1_table:
            return _result(
                plan,
                QualificationOutcome.SHARADAR_FIELD_UNSUPPORTED,
                "SF1 table is outside the frozen mapping",
            )
        if page.dimension in {"ART", "MRQ", "MRY", "MRT"}:
            return _result(
                plan,
                QualificationOutcome.SHARADAR_FIELD_UNSUPPORTED,
                "ART and MR dimensions are rejected for historical PM2C facts",
            )
        if page.dimension != plan.sf1_dimension:
            return _result(
                plan,
                QualificationOutcome.SOURCE_FACT_MISMATCH,
                "SF1 dimension differs from the frozen mapping",
            )
        if page.requested_cursor != expected_cursor:
            return _result(
                plan,
                QualificationOutcome.PROVIDER_FAILURE,
                "SF1 cursor chain is discontinuous",
            )
        if page.requested_cursor is not None:
            if page.requested_cursor in used_cursors:
                return _result(
                    plan,
                    QualificationOutcome.PROVIDER_FAILURE,
                    "SF1 cursor chain cycles",
                )
            used_cursors.add(page.requested_cursor)
        if page.next_cursor is not None:
            if page.next_cursor in used_cursors:
                return _result(
                    plan,
                    QualificationOutcome.PROVIDER_FAILURE,
                    "SF1 next cursor repeats",
                )
        expected_cursor = page.next_cursor
        if index < len(sf1_pages) - 1 and page.terminal:
            return _result(
                plan,
                QualificationOutcome.PROVIDER_FAILURE,
                "SF1 terminal page was followed by another page",
            )
    if not sf1_pages[-1].terminal:
        if len(sf1_pages) >= plan.max_sharadar_pages:
            return _result(
                plan,
                QualificationOutcome.PAGE_LIMIT_REACHED,
                "SF1 page limit reached before terminal pagination",
            )
        return _result(
            plan,
            QualificationOutcome.PROVIDER_FAILURE,
            "SF1 response set is truncated before terminal pagination",
        )

    all_rows = tuple((page, row) for page in sf1_pages for row in page.rows)
    target_rows = tuple(
        (page, row)
        for page, row in all_rows
        if row.ticker == plan.ticker
        and row.perma_ticker == plan.perma_ticker
        and row.report_period == plan.period_end
    )
    if not target_rows:
        same_security = tuple(
            row
            for _, row in all_rows
            if row.ticker == plan.ticker and row.perma_ticker == plan.perma_ticker
        )
        if same_security:
            return _result(
                plan,
                QualificationOutcome.SOURCE_FACT_MISMATCH,
                "SF1 fiscal period differs from the exact target",
            )
        if any(row.ticker == plan.ticker for _, row in all_rows):
            return _result(
                plan,
                QualificationOutcome.SOURCE_FACT_MISMATCH,
                "ticker resolves to a different permaTicker/security",
            )
        return _result(
            plan,
            QualificationOutcome.SHARADAR_ROW_MISSING,
            "exact ticker/permaTicker/reportperiod row is absent",
        )
    if len(target_rows) != 1:
        return _result(
            plan,
            QualificationOutcome.CONFLICTED,
            "multiple SF1 rows match the frozen subject and period",
        )
    sf1_page, sf1_row = target_rows[0]
    if (
        plan.expected_calendar_date is not None
        and sf1_row.calendar_date != plan.expected_calendar_date
    ):
        return _result(
            plan,
            QualificationOutcome.SOURCE_FACT_MISMATCH,
            "SF1 calendardate differs from the exact plan",
        )
    if not sf1_row.field_present:
        return _result(
            plan,
            QualificationOutcome.SHARADAR_FIELD_UNSUPPORTED,
            "selected SF1 field is absent",
        )
    if sf1_row.value is None:
        return _result(
            plan,
            QualificationOutcome.SHARADAR_FIELD_UNSUPPORTED,
            "selected SF1 field is null, not zero",
        )
    if sf1_row.value != scaled_sec_value:
        return _result(
            plan,
            QualificationOutcome.SOURCE_FACT_MISMATCH,
            "SEC and SF1 signed values differ",
        )

    sec_witness = _exact_sec_witness(
        sec_witnesses, sec_fact.locator, primary_response.content_sha256
    )
    if not _valid_sec_witness(sec_witness, primary_response, sec_fact):
        return _result(
            plan,
            QualificationOutcome.SOURCE_VERSION_UNPROVEN,
            "exact SEC public/version witness is absent or mismatched",
        )
    sf1_witness = _exact_sf1_witness(
        sharadar_witnesses, sf1_row.locator, sf1_page.content_sha256
    )
    if sf1_witness is None:
        return _result(
            plan,
            QualificationOutcome.SOURCE_VERSION_UNPROVEN,
            "exact immutable SF1 row/version witness is absent or conflicted",
        )
    if (
        sf1_witness.sec_accession != plan.primary_accession
        or sf1_witness.sec_record_locator != sec_fact.locator
        or sf1_witness.sec_response_sha256 != primary_response.content_sha256
        or sf1_witness.pm2c_raw_key != plan.target_entry.key
        or sf1_witness.sf1_field != plan.sf1_field
        or sf1_witness.sec_concept != plan.field_mapping.sec_concept
        or sf1_witness.unit != plan.provider_unit
        or sf1_witness.currency != plan.currency
    ):
        return _result(
            plan,
            QualificationOutcome.SOURCE_FACT_MISMATCH,
            "SF1 sidecar does not bind the exact SEC fact/mapping",
        )
    if (
        sf1_witness.period_role is not plan.period_role
        or sf1_witness.period_start != plan.period_start
        or sf1_witness.period_end != plan.period_end
        or sf1_witness.fiscal_year != plan.fiscal_year
    ):
        return _result(
            plan,
            QualificationOutcome.SHARADAR_FIELD_UNSUPPORTED,
            "SF1 grain/period is not proven for this mapping",
        )
    if (
        sf1_row.source_record_id is not None
        and sf1_witness.source_record_id != sf1_row.source_record_id
    ):
        return _result(
            plan,
            QualificationOutcome.SOURCE_VERSION_UNPROVEN,
            "SF1 source record ID differs from the exact row",
        )
    if (
        sf1_row.datekey is not None
        and sf1_witness.source_version == sf1_row.datekey.isoformat()
    ):
        return _result(
            plan,
            QualificationOutcome.SOURCE_VERSION_UNPROVEN,
            "datekey is not an immutable version witness",
        )
    if (
        sf1_row.lastupdated is not None
        and sf1_witness.source_version == sf1_row.lastupdated.isoformat()
    ):
        return _result(
            plan,
            QualificationOutcome.SOURCE_VERSION_UNPROVEN,
            "lastupdated is not an immutable version witness",
        )
    if sf1_witness.source_version == sf1_page.content_sha256:
        return _result(
            plan,
            QualificationOutcome.SOURCE_VERSION_UNPROVEN,
            "response digest alone is not an immutable version witness",
        )
    if sf1_witness.period_role not in {PeriodRole.ANNUAL, PeriodRole.DIRECT_Q1}:
        return _result(
            plan,
            QualificationOutcome.UNSUPPORTED_QUARTERIZATION,
            "SF1 quarterization is outside the direct annual/Q1 contract",
        )
    if sf1_witness.vendor_available_from < _utc_midnight(plan.period_end):
        return _result(
            plan,
            QualificationOutcome.SOURCE_AVAILABILITY_UNPROVEN,
            "SF1 version availability predates the economic period end",
        )
    if not _within_visibility(sf1_witness, plan.availability_cutoff):
        return _result(
            plan,
            QualificationOutcome.SOURCE_AVAILABILITY_UNPROVEN,
            "SF1 exact version window does not cover the cutoff",
        )
    if not _within_visibility(sec_witness, plan.availability_cutoff):
        return _result(
            plan,
            QualificationOutcome.SOURCE_AVAILABILITY_UNPROVEN,
            "SEC public visibility window does not cover the cutoff",
        )
    if sf1_witness.vendor_available_from > plan.availability_cutoff:
        return _result(
            plan,
            QualificationOutcome.SOURCE_AVAILABILITY_UNPROVEN,
            "SF1 exact version was not available by cutoff",
        )
    if sec_witness.public_available_from < _utc_midnight(plan.period_end):
        return _result(
            plan,
            QualificationOutcome.SOURCE_AVAILABILITY_UNPROVEN,
            "SEC public availability predates the economic period end",
        )
    if (
        primary_response.accepted_at is not None
        and sec_witness.public_available_from < primary_response.accepted_at
    ):
        return _result(
            plan,
            QualificationOutcome.SOURCE_AVAILABILITY_UNPROVEN,
            "SEC public visibility predates acceptance",
        )
    if sec_witness.proof_reference == sf1_witness.proof_reference:
        return _result(
            plan,
            QualificationOutcome.SOURCE_VERSION_UNPROVEN,
            "SEC and SF1 require independently identified proof references",
        )

    available_at = max(
        sec_witness.public_available_from, sf1_witness.vendor_available_from
    )
    visibility_ends_at = min(sec_witness.visible_until, sf1_witness.visible_until)
    if not (available_at <= plan.availability_cutoff <= visibility_ends_at):
        return _result(
            plan,
            QualificationOutcome.SOURCE_AVAILABILITY_UNPROVEN,
            "both independent version windows must cover the cutoff",
        )
    result_observed_at = max(
        observed_at, primary_response.observed_at, sf1_page.observed_at
    )
    if result_observed_at < available_at:
        return _result(
            plan,
            QualificationOutcome.SOURCE_AVAILABILITY_UNPROVEN,
            "local observation precedes proven source availability",
        )
    return QualificationResult(
        outcome=QualificationOutcome.QUALIFIED_CANDIDATE,
        reason="exact SEC/SF1 fact, mapping, and independent version windows match",
        plan_id=plan.plan_id,
        selected_sec_fact=sec_fact,
        selected_sharadar_row=sf1_row,
        sec_available_at=sec_witness.public_available_from,
        sf1_available_at=sf1_witness.vendor_available_from,
        available_at=available_at,
        observed_at=result_observed_at,
        sec_response_sha256=primary_response.content_sha256,
        sf1_response_sha256=sf1_page.content_sha256,
        sec_source_version=sec_witness.source_version,
        sf1_source_version=sf1_witness.source_version,
        sec_proof_reference=sec_witness.proof_reference,
        sf1_proof_reference=sf1_witness.proof_reference,
        visibility_ends_at=visibility_ends_at,
        _plan=plan,
    )


def quarterization_outcome(period_role: PeriodRole) -> QualificationOutcome | None:
    """Return an explicit unsupported outcome for non-direct Q2/Q3/Q4 math."""

    if not isinstance(period_role, PeriodRole):
        raise TypeError("period_role must be PeriodRole")
    if period_role in {
        PeriodRole.YTD_Q2,
        PeriodRole.YTD_Q3,
        PeriodRole.ANNUAL_MINUS_Q3_YTD_Q4,
    }:
        return QualificationOutcome.UNSUPPORTED_QUARTERIZATION
    return None


def _exact_sec_witness(
    witnesses: tuple[SecProvenanceWitness, ...], locator: str, digest: str
) -> SecProvenanceWitness | None:
    matches = tuple(
        item
        for item in witnesses
        if item.record_locator == locator and item.response_sha256 == digest
    )
    return matches[0] if len(matches) == 1 else None


def _mapped_facts(
    responses: tuple[ParsedSecResponse, ...], plan: QualificationPlan
) -> tuple[tuple[ParsedSecResponse, SecFactCandidate], ...]:
    return tuple(
        (response, fact)
        for response in responses
        for fact in response.facts
        if fact.concept == plan.field_mapping.sec_concept
    )


def _exact_context_facts(
    candidates: tuple[tuple[ParsedSecResponse, SecFactCandidate], ...],
    plan: QualificationPlan,
) -> tuple[tuple[ParsedSecResponse, SecFactCandidate], ...]:
    return tuple(
        (response, fact)
        for response, fact in candidates
        if fact.context_id == plan.context_id
        and fact.context_cik == plan.issuer_cik
        and fact.period_start == plan.period_start
        and fact.period_end == plan.period_end
        and fact.dimensions == plan.dimensions
    )


def _valid_sec_witness(
    witness: SecProvenanceWitness | None,
    response: ParsedSecResponse,
    fact: SecFactCandidate,
) -> bool:
    if witness is None:
        return False
    return (
        witness.record_locator == fact.locator
        and witness.response_sha256 == response.content_sha256
        and witness.source_version
        == f"sec:{response.accession}:{response.content_sha256}"
        and witness.proof_basis is SecAvailabilityProof.PUBLIC_ARCHIVE_WITNESS
        and (
            fact.source_record_id is None
            or witness.source_record_id == fact.source_record_id
        )
        and witness.public_available_from >= _utc_midnight(fact.period_end)
    )


def _exact_sf1_witness(
    witnesses: tuple[SharadarProvenanceWitness, ...], locator: str, digest: str
) -> SharadarProvenanceWitness | None:
    matches = tuple(
        item
        for item in witnesses
        if item.record_locator == locator and item.response_sha256 == digest
    )
    return matches[0] if len(matches) == 1 else None


def _result(
    plan: QualificationPlan,
    outcome: QualificationOutcome,
    reason: str,
) -> QualificationResult:
    return QualificationResult(outcome, reason, plan.plan_id)


def _load_json_object(raw_bytes: bytes, name: str) -> dict[str, Any]:
    if not isinstance(raw_bytes, bytes):
        raise TypeError(f"{name} must be exact response bytes")

    def reject_constant(value: str) -> None:
        raise QualificationInputError("non-finite JSON numbers are forbidden")

    def no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise QualificationInputError(f"duplicate JSON key in {name}")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw_bytes.decode("utf-8", errors="strict"),
            parse_float=Decimal,
            parse_int=int,
            parse_constant=reject_constant,
            object_pairs_hook=no_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, InvalidOperation) as error:
        raise QualificationInputError(
            f"{name} is not valid strict UTF-8 JSON"
        ) from error
    if not isinstance(value, dict):
        raise QualificationInputError(f"{name} must be a JSON object")
    return value


def _require_keys(
    value: dict[str, Any], *, required: set[str], optional: set[str], name: str
) -> None:
    missing = required - set(value)
    unknown = set(value) - required - optional
    if missing:
        raise QualificationInputError(f"{name} is missing required fields")
    if unknown:
        raise QualificationInputError(f"{name} has unknown fields")


def _bytes_within(value: bytes, limit: int, name: str) -> None:
    if not isinstance(value, bytes):
        raise TypeError(f"{name} must be bytes")
    if not value or len(value) > limit:
        raise QualificationInputError(
            f"{name} is empty or exceeds its exact byte bound"
        )


def _string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value or not value.strip():
        raise QualificationInputError(f"{name} must be nonblank text")
    if value != value.strip() or len(value) > _MAX_TOKEN_LENGTH:
        raise QualificationInputError(f"{name} must use bounded canonical text")
    return value


def _integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise QualificationInputError(f"{name} must be an integer")
    return value


def _decimal(value: object, name: str, *, allow_null: bool = False) -> Decimal | None:
    if value is None and allow_null:
        return None
    if isinstance(value, bool):
        raise QualificationInputError(f"{name} cannot be bool")
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int):
        result = Decimal(value)
    elif (
        isinstance(value, str)
        and len(value) <= 80
        and _DECIMAL_TEXT_RE.fullmatch(value)
    ):
        try:
            result = Decimal(value)
        except InvalidOperation as error:
            raise QualificationInputError(f"{name} is not a finite decimal") from error
    else:
        raise QualificationInputError(f"{name} must be an exact decimal or null")
    if not result.is_finite():
        raise QualificationInputError(f"{name} must be finite")
    _, digits, exponent = result.as_tuple()
    if len(digits) > _MAX_DECIMAL_DIGITS or abs(exponent) > _MAX_DECIMAL_EXPONENT:
        raise QualificationInputError(
            f"{name} exceeds the bounded decimal representation"
        )
    return result


def _date(value: object, name: str) -> date:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise TypeError(f"{name} must be a date")
    return value


def _parse_date(value: object, name: str) -> date:
    if not isinstance(value, str):
        raise QualificationInputError(f"{name} must be an ISO date string")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise QualificationInputError(f"{name} must be an ISO date string") from error
    if parsed.isoformat() != value:
        raise QualificationInputError(f"{name} must use canonical YYYY-MM-DD form")
    return parsed


def _optional_date(payload: dict[str, Any], name: str) -> date | None:
    if name not in payload or payload[name] is None:
        return None
    return _parse_date(payload[name], name)


def _parse_datetime(value: object, name: str) -> datetime:
    if not isinstance(value, str):
        raise QualificationInputError(f"{name} must be an ISO datetime string")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return normalize_utc(datetime.fromisoformat(candidate), name)
    except (ValueError, TypeError) as error:
        raise QualificationInputError(
            f"{name} must include a valid timezone"
        ) from error


def _accession(value: str, name: str) -> None:
    if not isinstance(value, str) or not _ACCESSION_RE.fullmatch(value):
        raise ValueError(f"{name} must use SEC accession format")


def _positive_bounded_int(value: object, name: str, upper: int) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
        or value > upper
    ):
        raise ValueError(
            f"{name} must be a positive bounded integer no greater than {upper}"
        )


def _tuple(value: object, name: str) -> tuple[Any, ...]:
    if not isinstance(value, (tuple, list)):
        raise TypeError(f"{name} must be an ordered tuple or list")
    return tuple(value)


def _f_root(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise TypeError("evidence_root must be nonblank text")
    root = PureWindowsPath(value)
    if not root.is_absolute() or root.drive.upper() != "F:":
        raise ValueError("evidence_root must be an absolute F: path")


def _sha256(value: str, name: str) -> None:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")


def _apply_scale(value: Decimal, scale: int) -> Decimal:
    sign, digits, exponent = value.as_tuple()
    scaled_exponent = exponent + scale
    if (
        len(digits) > _MAX_DECIMAL_DIGITS
        or abs(scaled_exponent) > _MAX_DECIMAL_EXPONENT
    ):
        raise QualificationInputError(
            "scaled SEC fact exceeds the bounded decimal representation"
        )
    result = Decimal((sign, digits, scaled_exponent))
    if result != 0 and abs(result.adjusted()) > _MAX_DECIMAL_EXPONENT:
        raise QualificationInputError(
            "scaled SEC fact exceeds the bounded decimal magnitude"
        )
    return result


def _combined_digest(digests: tuple[str, ...]) -> str:
    body = b"pm2d-b1-composite-v1\x00" + b"\x00".join(
        bytes.fromhex(item) for item in digests
    )
    return hashlib.sha256(body).hexdigest()


def _within_visibility(
    witness: SecProvenanceWitness | SharadarProvenanceWitness, cutoff: datetime
) -> bool:
    start = (
        witness.public_available_from
        if isinstance(witness, SecProvenanceWitness)
        else witness.vendor_available_from
    )
    return start <= cutoff <= witness.visible_until


def _utc_midnight(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=UTC)
