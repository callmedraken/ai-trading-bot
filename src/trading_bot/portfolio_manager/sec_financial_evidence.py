"""Operational PM2C bridge for exact, qualified SEC XBRL facts.

This module has no transport, filesystem, provider, account, or broker calls.
It accepts the exact preserved B1-R response bytes and typed verification
records supplied by the caller, re-extracts the embedded instance, and only
then creates a PM2C ``SourceFact``. Verification-reference hashes are trust
inputs: this module checks their shape and binds them to the exact fact, but
cannot authenticate who created them or the external records they identify.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import UUID

from trading_bot.domain import Symbol
from trading_bot.domain._validation import normalize_utc
from trading_bot.portfolio_manager.research_catalog import (
    CatalogEntry,
    EntryKind,
    EvidenceBasis,
    PeriodSpec,
    ResearchCatalog,
    ScopeSpec,
    ValueKind,
    ValueSpec,
    WindowSpec,
    research_identity,
)
from trading_bot.portfolio_manager.research_evidence import (
    AvailabilityStatus,
    EvidenceGraph,
    EvidenceOutcome,
    EvidenceSubject,
    EvidenceTimeframe,
    EvidenceTimeframeKind,
    SnapshotMode,
    SourceFact,
)
from trading_bot.portfolio_manager.research_snapshot import (
    MembershipBinding,
    ResearchSnapshot,
    SnapshotSlotRequest,
)
from trading_bot.portfolio_manager.sec_financial_statements import (
    SEC_FINANCIAL_FIELD_NAMESPACE,
    SECFinancialFact,
    SECFinancialField,
    SECFinancialFieldStatus,
    SECFinancialPeriodKind,
    SECFinancialStatementReport,
    extract_sec_financial_statement_bytes,
    financial_field_definition,
    select_fact,
)
from trading_bot.portfolio_manager.sec_native_observation import (
    SECObservationOutcome,
    SECObservationPlan,
    SECObservationResult,
    SECRevenueFact,
    SECSubmission,
    SECTransportResponse,
    canonical_sec_attempt_id,
    extract_sec_submission_member,
    parse_sec_submission,
)

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_CIK = re.compile(r"[0-9]{10}\Z")
_ISO4217 = "http://www.xbrl.org/2003/iso4217"
_USD = (_ISO4217, "USD")
_B1R_BLOCKED_REASON = "SEC_HISTORICAL_VERSION_WITNESS_AND_SECURITY_MAPPING_UNPROVEN"
_B1R_INSTANT_CONTEXT_LIMITATION = "XBRL_DURATION_CONTEXT_REQUIRED"


class SECFinancialBridgeError(ValueError):
    """A source or provenance record cannot satisfy operational admission."""


@dataclass(frozen=True, slots=True)
class _FieldDefinition:
    field: SECFinancialField
    key: str
    unit_label: str
    reporting_basis: str


_FIELD_DEFINITIONS = (
    _FieldDefinition(
        SECFinancialField.REVENUE_INCLUDING_ASSESSED_TAX,
        "raw.fiscal.annual.sec.revenue_including_assessed_tax",
        "USD",
        "US_GAAP_2018_REVENUE_INCLUDING_ASSESSED_TAX",
    ),
    _FieldDefinition(
        SECFinancialField.REVENUE_EXCLUDING_ASSESSED_TAX,
        "raw.fiscal.annual.sec.revenue_excluding_assessed_tax",
        "USD",
        "US_GAAP_2018_REVENUE_EXCLUDING_ASSESSED_TAX",
    ),
    _FieldDefinition(
        SECFinancialField.OPERATING_INCOME,
        "raw.fiscal.annual.sec.operating_income_loss",
        "USD",
        "US_GAAP_2018_OPERATING_INCOME_LOSS",
    ),
    _FieldDefinition(
        SECFinancialField.NET_INCOME,
        "raw.fiscal.annual.sec.net_income_loss",
        "USD",
        "US_GAAP_2018_NET_INCOME_LOSS_NOT_ATTRIBUTABLE_COMMON",
    ),
    _FieldDefinition(
        SECFinancialField.DILUTED_EPS,
        "raw.fiscal.annual.sec.diluted_eps",
        "USD/share",
        "US_GAAP_2018_DILUTED_EPS_USD_PER_SHARE",
    ),
    _FieldDefinition(
        SECFinancialField.OPERATING_CASH_FLOW,
        "raw.fiscal.annual.sec.operating_cash_flow",
        "USD",
        "US_GAAP_2018_NET_CASH_OPERATING_ACTIVITIES",
    ),
    _FieldDefinition(
        SECFinancialField.CAPITAL_EXPENDITURES_PROPERTY_PLANT_EQUIPMENT,
        "raw.fiscal.annual.sec.ppe_acquisition_payments",
        "USD",
        "US_GAAP_2018_PPE_ACQUISITION_PAYMENTS_SIGN_AS_REPORTED",
    ),
    _FieldDefinition(
        SECFinancialField.PAYMENTS_TO_ACQUIRE_PRODUCTIVE_ASSETS,
        "raw.fiscal.annual.sec.payments_to_acquire_productive_assets",
        "USD",
        "US_GAAP_2018_PAYMENTS_TO_ACQUIRE_PRODUCTIVE_ASSETS",
    ),
    _FieldDefinition(
        SECFinancialField.CASH_AND_CASH_EQUIVALENTS,
        "raw.fiscal.balance_sheet.sec.cash_and_cash_equivalents",
        "USD",
        "US_GAAP_2018_CASH_AND_CASH_EQUIVALENTS_AT_CARRYING_VALUE",
    ),
    _FieldDefinition(
        SECFinancialField.TOTAL_ASSETS,
        "raw.fiscal.balance_sheet.sec.assets",
        "USD",
        "US_GAAP_2018_ASSETS",
    ),
    _FieldDefinition(
        SECFinancialField.TOTAL_LIABILITIES,
        "raw.fiscal.balance_sheet.sec.liabilities",
        "USD",
        "US_GAAP_2018_LIABILITIES",
    ),
    _FieldDefinition(
        SECFinancialField.STOCKHOLDERS_EQUITY,
        "raw.fiscal.balance_sheet.sec.stockholders_equity",
        "USD",
        "US_GAAP_2018_STOCKHOLDERS_EQUITY_NOT_ATTRIBUTABLE_COMMON",
    ),
    _FieldDefinition(
        SECFinancialField.LONG_TERM_DEBT_CURRENT,
        "raw.fiscal.balance_sheet.sec.long_term_debt_current",
        "USD",
        "US_GAAP_2018_LONG_TERM_DEBT_CURRENT",
    ),
    _FieldDefinition(
        SECFinancialField.LONG_TERM_DEBT_NONCURRENT,
        "raw.fiscal.balance_sheet.sec.long_term_debt_noncurrent",
        "USD",
        "US_GAAP_2018_LONG_TERM_DEBT_NONCURRENT",
    ),
    _FieldDefinition(
        SECFinancialField.LONG_TERM_DEBT_AND_FINANCE_LEASE_OBLIGATIONS_CURRENT,
        "raw.fiscal.balance_sheet.sec.long_term_debt_and_finance_lease_current",
        "USD",
        "US_GAAP_2018_LONG_TERM_DEBT_AND_FINANCE_LEASE_CURRENT",
    ),
    _FieldDefinition(
        SECFinancialField.LONG_TERM_DEBT_AND_FINANCE_LEASE_OBLIGATIONS_NONCURRENT,
        "raw.fiscal.balance_sheet.sec.long_term_debt_and_finance_lease_noncurrent",
        "USD",
        "US_GAAP_2018_LONG_TERM_DEBT_AND_FINANCE_LEASE_NONCURRENT",
    ),
    _FieldDefinition(
        SECFinancialField.LONG_TERM_DEBT,
        "raw.fiscal.balance_sheet.sec.long_term_debt",
        "USD",
        "US_GAAP_2018_LONG_TERM_DEBT",
    ),
    _FieldDefinition(
        SECFinancialField.LONG_TERM_DEBT_AND_CAPITAL_LEASE_OBLIGATIONS,
        "raw.fiscal.balance_sheet.sec.long_term_debt_and_capital_lease_obligations",
        "USD",
        "US_GAAP_2018_LONG_TERM_DEBT_AND_CAPITAL_LEASE_OBLIGATIONS",
    ),
    _FieldDefinition(
        SECFinancialField.LONG_TERM_DEBT_AND_CAPITAL_LEASE_OBLIGATIONS_CURRENT,
        "raw.fiscal.balance_sheet.sec.long_term_debt_and_capital_lease_current",
        "USD",
        "US_GAAP_2018_LONG_TERM_DEBT_AND_CAPITAL_LEASE_CURRENT",
    ),
)
_DEFINITION_BY_FIELD = {item.field: item for item in _FIELD_DEFINITIONS}


def sec_financial_catalog_entries(catalog_version: str) -> tuple[CatalogEntry, ...]:
    """Return exact RAW entries, keeping each SEC concept/accounting basis apart."""

    if not isinstance(catalog_version, str) or not catalog_version.strip():
        raise ValueError("catalog_version must be nonblank")
    entries: list[CatalogEntry] = []
    for definition in _FIELD_DEFINITIONS:
        is_flow = (
            financial_field_definition(definition.field).period_kind
            is SECFinancialPeriodKind.DURATION
        )
        entries.append(
            CatalogEntry(
                catalog_version=catalog_version,
                key=definition.key,
                version="1",
                family="sec_fundamental",
                kind=EntryKind.RAW,
                value_spec=ValueSpec(
                    ValueKind.DECIMAL,
                    unit=definition.unit_label,
                    currency="USD",
                ),
                scope=ScopeSpec("security"),
                period_basis=PeriodSpec(
                    "annual_fiscal_period" if is_flow else "fiscal_instant",
                    relation=(
                        "exact_10k_duration"
                        if is_flow
                        else "exact_balance_sheet_instant"
                    ),
                    anchor="period_end",
                ),
                window=WindowSpec("one_exact_sec_filing"),
                basis=EvidenceBasis(
                    calendar="SEC_FISCAL",
                    data_basis="SEC_NATIVE_XBRL",
                    reporting_basis=definition.reporting_basis,
                ),
                availability_rules=(
                    "trusted_local_receipt_required",
                    "operational_cutoff_required",
                ),
                domain_rules=(
                    "exact_field_concept_only",
                    "consolidated_no_dimensions",
                    "signed_decimal_preserved",
                    "no_implicit_accounting_conversion",
                ),
            )
        )
    return tuple(entries)


def sec_financial_fact_fingerprint(fact: SECFinancialFact) -> str:
    """Return UUID5 identity over the exact original XBRL fact and source."""

    if type(fact) is not SECFinancialFact:
        raise TypeError("fact must be the exact SECFinancialFact type")
    source = fact.source
    return str(
        research_identity(
            "sec-financial-original-fact-v1",
            fact.field.value,
            source.sha256,
            source.length,
            source.accession,
            source.document_name,
            source.issuer_cik,
            fact.namespace,
            fact.concept,
            fact.source_fact_id,
            fact.context_id,
            fact.period_kind.value,
            fact.period_start.isoformat() if fact.period_start is not None else None,
            fact.period_end.isoformat(),
            fact.unit_id,
            fact.unit.numerator,
            fact.unit.denominator,
            fact.signed_decimal_value,
            fact.decimals,
            fact.precision,
            fact.dimensions,
            fact.is_nil,
        )
    )


def _require_reference(value: str, name: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 reference")
    return value


@dataclass(frozen=True, slots=True)
class SECOperationalDocumentQualification:
    """External verification references bound to one exact B1-R acquisition.

    This is a typed trust-boundary input, not an authenticated signature. The
    caller must load it from the separately reviewed verification record. The
    terminal reference preserves the one-shot outcome, while the exact typed
    response carries the saved bytes, transport provenance, and local receipt.
    """

    plan: SECObservationPlan
    observation: SECObservationResult
    response: SECTransportResponse
    request_intent_at: datetime
    verification_completed_at: datetime
    request_intent_reference: str
    acquisition_record_reference: str
    response_provenance_reference: str
    document_verification_reference: str
    accession_verification_reference: str
    issuer_verification_reference: str
    fact_verification_references: tuple[tuple[str, str], ...]
    publication_at: datetime | None = None
    publication_verification_reference: str | None = None

    def __post_init__(self) -> None:
        if type(self.plan) is not SECObservationPlan:
            raise TypeError("plan must be the exact SECObservationPlan type")
        if type(self.observation) is not SECObservationResult:
            raise TypeError("observation must be the exact SECObservationResult type")
        if type(self.response) is not SECTransportResponse:
            raise TypeError("response must be the exact SECTransportResponse type")
        for name in (
            "request_intent_at",
            "verification_completed_at",
        ):
            object.__setattr__(self, name, normalize_utc(getattr(self, name), name))
        if self.publication_at is not None:
            object.__setattr__(
                self,
                "publication_at",
                normalize_utc(self.publication_at, "publication_at"),
            )
            if self.publication_verification_reference is None:
                raise ValueError(
                    "publication_at requires an independent verification reference"
                )
            _require_reference(
                self.publication_verification_reference,
                "publication_verification_reference",
            )
        elif self.publication_verification_reference is not None:
            raise ValueError(
                "publication verification reference requires publication_at"
            )
        refs = (
            self.request_intent_reference,
            self.acquisition_record_reference,
            self.response_provenance_reference,
            self.document_verification_reference,
            self.accession_verification_reference,
            self.issuer_verification_reference,
        )
        for name, value in zip(
            (
                "request_intent_reference",
                "acquisition_record_reference",
                "response_provenance_reference",
                "document_verification_reference",
                "accession_verification_reference",
                "issuer_verification_reference",
            ),
            refs,
            strict=True,
        ):
            _require_reference(value, name)
        if len(set(refs)) != len(refs):
            raise ValueError("independent qualification references must be distinct")
        if self.publication_verification_reference is not None and (
            self.publication_verification_reference in refs
        ):
            raise ValueError("publication verification reference must be distinct")
        fact_refs = tuple(self.fact_verification_references)
        fingerprints: set[str] = set()
        references: set[str] = set(refs)
        if self.publication_verification_reference is not None:
            references.add(self.publication_verification_reference)
        for fingerprint, reference in fact_refs:
            try:
                parsed_id = UUID(fingerprint)
            except (TypeError, ValueError, AttributeError) as error:
                raise ValueError("fact fingerprint must be a canonical UUID") from error
            if str(parsed_id) != fingerprint or fingerprint in fingerprints:
                raise ValueError("fact fingerprints must be canonical and unique")
            _require_reference(reference, "fact verification reference")
            if reference in references:
                raise ValueError("verification references must be unique")
            fingerprints.add(fingerprint)
            references.add(reference)
        if not fact_refs:
            raise ValueError("at least one independently verified fact is required")
        object.__setattr__(self, "fact_verification_references", fact_refs)


@dataclass(frozen=True, slots=True)
class SECIndependentSecurityMapping:
    """Caller-supplied independent issuer-to-security/share-class evidence."""

    issuer_cik: str
    subject: EvidenceSubject
    verified_at: datetime
    issuer_reference: str
    security_reference: str

    def __post_init__(self) -> None:
        if not isinstance(self.issuer_cik, str) or not _CIK.fullmatch(self.issuer_cik):
            raise ValueError("issuer_cik must be an exact 10-digit CIK")
        if type(self.subject) is not EvidenceSubject:
            raise TypeError("subject must be the exact EvidenceSubject type")
        if (
            self.subject.symbol is None
            or self.subject.issuer_id != f"CIK:{self.issuer_cik}"
            or not self.subject.security_id
            or not self.subject.share_class
            or self.subject.portfolio_account_id is not None
            or self.subject.portfolio_snapshot_id is not None
            or self.subject.scope is not None
        ):
            raise ValueError(
                "mapping must bind exact CIK, symbol, security ID, and share class"
            )
        object.__setattr__(
            self, "verified_at", normalize_utc(self.verified_at, "verified_at")
        )
        _require_reference(self.issuer_reference, "issuer_reference")
        _require_reference(self.security_reference, "security_reference")
        if self.issuer_reference == self.security_reference:
            raise ValueError("issuer and security mapping references must be distinct")


@dataclass(frozen=True, slots=True)
class SECBridgedFact:
    """PM2C source fact with the complete original XBRL fact retained beside it."""

    source_fact: SourceFact
    original_fact: SECFinancialFact
    submission: SECSubmission
    receipt_at: datetime
    publication_at: datetime | None
    publication_verification_reference: str | None
    source_version: str
    response_sha256: str
    response_length: int
    b1r_terminal_outcome: SECObservationOutcome
    b1r_terminal_reason: str
    acquisition_record_reference: str
    response_provenance_reference: str
    fact_verification_reference: str
    issuer_mapping_references: tuple[str, str]


def _definition(field: SECFinancialField) -> _FieldDefinition:
    if not isinstance(field, SECFinancialField):
        raise TypeError("field must be SECFinancialField")
    try:
        return _DEFINITION_BY_FIELD[field]
    except KeyError as error:
        raise SECFinancialBridgeError("SEC_FIELD_UNREGISTERED") from error


def _verify_observation(
    raw_response: bytes, qualification: SECOperationalDocumentQualification
) -> tuple[SECSubmission, bytes, datetime, SECObservationResult]:
    plan = qualification.plan
    observation = qualification.observation
    response = qualification.response
    if type(raw_response) is not bytes:
        raise TypeError("raw_response must be exact preserved response bytes")
    if raw_response != response.body:
        raise SECFinancialBridgeError("B1R_RESPONSE_BODY_MISMATCH")
    if (
        response.received_at is None
        or response.status_code != 200
        or response.final_url != plan.submission_url
        or response.content_type.split(";", 1)[0].strip().lower()
        not in {"text/plain", "application/octet-stream"}
    ):
        raise SECFinancialBridgeError("B1R_RESPONSE_PROVENANCE_MISMATCH")
    if (
        plan.filing_form != "10-K"
        or plan.concept_namespace
        != financial_field_definition(
            SECFinancialField.REVENUE_EXCLUDING_ASSESSED_TAX
        ).namespace
        or plan.concept_local_name
        != financial_field_definition(
            SECFinancialField.REVENUE_EXCLUDING_ASSESSED_TAX
        ).concept
        or plan.unit_namespace != _USD[0]
        or plan.unit_local_name != _USD[1]
        or plan.dimensions != ()
    ):
        raise SECFinancialBridgeError("EXACT_B1R_REVENUE_PLAN_REQUIRED")
    if (
        plan.attempt_id != canonical_sec_attempt_id(plan)
        or observation.plan_id != plan.plan_id
        or observation.source_head != plan.expected_source_head
        or observation.source_tree != plan.expected_source_tree
    ):
        raise SECFinancialBridgeError("B1R_PLAN_AND_OBSERVATION_MISMATCH")
    counters = observation.counters
    terminal_shape = (
        observation.outcome is SECObservationOutcome.SEC_OBSERVATION_BLOCKED
        and observation.reason_code == _B1R_BLOCKED_REASON
        and type(observation.submission) is SECSubmission
        and type(observation.fact) is SECRevenueFact
        and counters.xbrl_records == 1
    ) or (
        observation.outcome is SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED
        and observation.reason_code == _B1R_INSTANT_CONTEXT_LIMITATION
        and observation.submission is None
        and observation.fact is None
        and counters.xbrl_records == 0
    )
    if (
        not terminal_shape
        or observation.source_fact_created
        or observation.public_availability_witness != "UNPROVEN"
        or observation.security_identity_witness != "UNPROVEN"
    ):
        raise SECFinancialBridgeError("B1R_TYPED_TERMINAL_QUALIFICATION_REQUIRED")
    if (
        counters.provider_invocations != 1
        or counters.request_intents != 1
        or counters.response_documents != 1
        or counters.response_bytes != len(raw_response)
        or counters.response_bytes_received != len(raw_response)
        or any(
            getattr(counters, field_name) != 0
            for field_name in (
                "credential_reads",
                "account_reads",
                "ai_calls",
                "broker_effects",
                "production_mutations",
            )
        )
    ):
        raise SECFinancialBridgeError("B1R_RESPONSE_OR_EFFECT_COUNTER_MISMATCH")
    response_digest = hashlib.sha256(raw_response).hexdigest()
    response_receipt = normalize_utc(response.received_at, "local_response_receipt")
    if len(raw_response) > plan.max_response_bytes:
        raise SECFinancialBridgeError("B1R_RESPONSE_BYTE_LIMIT_MISMATCH")
    if observation.response_sha256 != (response_digest,):
        raise SECFinancialBridgeError("B1R_RESPONSE_DIGEST_MISMATCH")
    try:
        submission = parse_sec_submission(raw_response, plan, response_receipt)
    except (TypeError, ValueError) as error:
        raise SECFinancialBridgeError("B1R_SUBMISSION_REPARSE_FAILED") from error
    if observation.submission is not None and observation.submission != submission:
        raise SECFinancialBridgeError("B1R_SUBMISSION_IDENTITY_MISMATCH")
    if (
        submission.form != "10-K"
        or submission.document_type != "EX-101.INS"
        or submission.document_name != plan.document_name
        or submission.document_sequence != plan.document_sequence
        or submission.issuer_cik != plan.issuer_cik
        or submission.accession != plan.accession
        or submission.report_period != plan.period_end
        or submission.filing_date < submission.report_period
        or submission.content_sha256 != response_digest
        or submission.content_length != len(raw_response)
        or submission.observed_at != response_receipt
    ):
        raise SECFinancialBridgeError("B1R_SUBMISSION_IDENTITY_MISMATCH")
    receipt_at = submission.observed_at
    request_intent_at = qualification.request_intent_at
    verified_at = qualification.verification_completed_at
    if (
        request_intent_at > receipt_at
        or verified_at < receipt_at
        or receipt_at.date() < submission.filing_date
        or (
            qualification.publication_at is not None
            and qualification.publication_at > receipt_at
        )
    ):
        raise SECFinancialBridgeError("RECEIPT_CHRONOLOGY_INCONSISTENT")
    try:
        embedded = extract_sec_submission_member(raw_response, submission)
    except (TypeError, ValueError) as error:
        raise SECFinancialBridgeError(
            "B1R_EMBEDDED_DOCUMENT_VERIFICATION_FAILED"
        ) from error
    if len(embedded) != submission.embedded_document_length:
        raise SECFinancialBridgeError("B1R_EMBEDDED_DOCUMENT_LENGTH_MISMATCH")
    return submission, embedded, receipt_at, observation


def _verify_revenue_anchor(
    report: SECFinancialStatementReport,
    plan: SECObservationPlan,
    source_fact: SECRevenueFact | None,
) -> SECFinancialFact:
    """Independently reproduce B1-R's exact annual revenue plan anchor."""

    revenue_definition = financial_field_definition(
        SECFinancialField.REVENUE_EXCLUDING_ASSESSED_TAX
    )
    if (
        plan.concept_namespace != revenue_definition.namespace
        or plan.concept_local_name != revenue_definition.concept
        or plan.unit_namespace != revenue_definition.unit.numerator[0]
        or plan.unit_local_name != revenue_definition.unit.numerator[1]
        or plan.period_start is None
        or plan.period_end is None
        or not 330 <= (plan.period_end - plan.period_start).days <= 400
        or plan.dimensions != ()
    ):
        raise SECFinancialBridgeError("B1R_REVENUE_FACT_PLAN_MISMATCH")
    selected = select_fact(
        report,
        SECFinancialField.REVENUE_EXCLUDING_ASSESSED_TAX,
        period_start=plan.period_start,
        period_end=plan.period_end,
        dimensions=plan.dimensions,
    )
    if (
        selected.status is not SECFinancialFieldStatus.AVAILABLE
        or len(selected.facts) != 1
    ):
        raise SECFinancialBridgeError("B1R_REVENUE_ANCHOR_NOT_REPRODUCED")
    parsed = selected.facts[0]
    if (
        parsed.namespace != plan.concept_namespace
        or parsed.concept != plan.concept_local_name
        or parsed.context_id != plan.context_id
        or parsed.period_start != plan.period_start
        or parsed.period_end != plan.period_end
        or parsed.dimensions != plan.dimensions
        or parsed.unit_id != plan.unit_id
        or parsed.unit.numerator != (plan.unit_namespace, plan.unit_local_name)
        or parsed.unit.denominator is not None
    ):
        raise SECFinancialBridgeError("B1R_REVENUE_ANCHOR_MISMATCH")
    if source_fact is not None:
        if type(source_fact) is not SECRevenueFact:
            raise SECFinancialBridgeError("B1R_REVENUE_FACT_REQUIRED")
        if (
            source_fact.accession != plan.accession
            or source_fact.document_name != plan.document_name
            or source_fact.issuer_cik != plan.issuer_cik
            or source_fact.period_start != parsed.period_start
            or source_fact.period_end != parsed.period_end
            or source_fact.namespace != parsed.namespace
            or source_fact.concept != parsed.concept
            or source_fact.context_id != parsed.context_id
            or source_fact.dimensions != parsed.dimensions
            or source_fact.unit_id != parsed.unit_id
            or source_fact.unit_namespace != parsed.unit.numerator[0]
            or source_fact.unit_local_name != parsed.unit.numerator[1]
            or source_fact.signed_decimal_value != parsed.signed_decimal_value
            or source_fact.decimals != parsed.decimals
            or source_fact.currency != "USD"
            or source_fact.scale != 0
        ):
            raise SECFinancialBridgeError("B1R_REVENUE_ANCHOR_MISMATCH")
    return parsed


def _fact_entry(catalog: ResearchCatalog, definition: _FieldDefinition) -> CatalogEntry:
    try:
        registered = catalog.lookup(definition.key, "1")
    except KeyError as error:
        raise SECFinancialBridgeError("SEC_FINANCIAL_CATALOG_ENTRY_MISSING") from error
    expected = next(
        entry
        for entry in sec_financial_catalog_entries(catalog.version)
        if entry.key == definition.key
    )
    if registered != expected or registered.entry_id != expected.entry_id:
        raise SECFinancialBridgeError("SEC_FINANCIAL_CATALOG_ENTRY_MISMATCH")
    return registered


def bridge_sec_financial_fact(
    raw_response: bytes,
    *,
    qualification: SECOperationalDocumentQualification,
    security_mapping: SECIndependentSecurityMapping,
    catalog: ResearchCatalog,
    field: SECFinancialField,
    period_start: date | None,
    period_end: date,
) -> SECBridgedFact:
    """Re-extract and bridge one exact consolidated fact for operational use.

    This function accepts only the exact completed B1-R observation shape and
    the original response bytes. Discovery reports or hashes alone cannot be
    converted into operational evidence. No historical witness is produced.
    """

    if type(qualification) is not SECOperationalDocumentQualification:
        raise TypeError("qualification must be the exact typed qualification")
    if type(security_mapping) is not SECIndependentSecurityMapping:
        raise TypeError("security_mapping must be the exact independent mapping")
    if type(catalog) is not ResearchCatalog:
        raise TypeError("catalog must be ResearchCatalog")
    if type(period_end) is not date or (
        period_start is not None and type(period_start) is not date
    ):
        raise TypeError("fact period bounds must be dates")
    definition = _definition(field)
    source_definition = financial_field_definition(field)
    entry = _fact_entry(catalog, definition)
    submission, embedded, receipt_at, observation = _verify_observation(
        raw_response, qualification
    )
    plan = qualification.plan
    mapping = security_mapping
    if mapping.issuer_cik != plan.issuer_cik:
        raise SECFinancialBridgeError("ISSUER_SECURITY_MAPPING_CIK_MISMATCH")
    if mapping.subject.issuer_id != f"CIK:{plan.issuer_cik}":
        raise SECFinancialBridgeError("ISSUER_SECURITY_MAPPING_SUBJECT_MISMATCH")
    try:
        report = extract_sec_financial_statement_bytes(
            embedded,
            expected_sha256=submission.embedded_document_sha256,
            expected_length=submission.embedded_document_length,
            accession=submission.accession,
            document_name=submission.document_name,
            expected_cik=submission.issuer_cik,
        )
    except (TypeError, ValueError) as error:
        raise SECFinancialBridgeError(
            "SEC_FINANCIAL_DOCUMENT_EXTRACTION_FAILED"
        ) from error
    source = report.source
    if (
        source.sha256 != submission.embedded_document_sha256
        or source.length != submission.embedded_document_length
        or source.accession != submission.accession
        or source.document_name != submission.document_name
        or source.issuer_cik != submission.issuer_cik
    ):
        raise SECFinancialBridgeError("SEC_FINANCIAL_SOURCE_IDENTITY_MISMATCH")
    if source.issuer_cik != mapping.issuer_cik:
        raise SECFinancialBridgeError("ISSUER_SECURITY_MAPPING_CIK_MISMATCH")
    revenue_anchor = _verify_revenue_anchor(report, plan, observation.fact)
    fact_references = dict(qualification.fact_verification_references)
    if sec_financial_fact_fingerprint(revenue_anchor) not in fact_references:
        raise SECFinancialBridgeError("INDEPENDENT_B1R_ANCHOR_VERIFICATION_REQUIRED")
    selected = select_fact(
        report,
        field,
        period_start=period_start,
        period_end=period_end,
        dimensions=(),
    )
    if (
        selected.status is not SECFinancialFieldStatus.AVAILABLE
        or len(selected.facts) != 1
    ):
        raise SECFinancialBridgeError(f"SEC_FINANCIAL_FACT_{selected.status.name}")
    fact = selected.facts[0]
    if (
        fact.source != source
        or fact.field is not field
        or fact.namespace != SEC_FINANCIAL_FIELD_NAMESPACE
        or fact.concept != source_definition.concept
        or fact.period_kind is not source_definition.period_kind
        or fact.unit != source_definition.unit
        or fact.dimensions != ()
        or fact.is_nil
        or not isinstance(fact.signed_decimal_value, Decimal)
        or not fact.signed_decimal_value.is_finite()
        or fact.period_start != period_start
        or fact.period_end != period_end
    ):
        raise SECFinancialBridgeError("SEC_FINANCIAL_FACT_CONTRACT_MISMATCH")
    if source_definition.period_kind is SECFinancialPeriodKind.DURATION:
        if period_start != plan.period_start or period_end != plan.period_end:
            raise SECFinancialBridgeError("APPROVED_FILING_PERIOD_REQUIRED")
        if period_start is None or not 330 <= (period_end - period_start).days <= 400:
            raise SECFinancialBridgeError("ANNUAL_DURATION_REQUIRED")
    elif period_start is not None:
        raise SECFinancialBridgeError("INSTANT_FACT_PERIOD_REQUIRED")
    elif period_end != plan.period_end:
        raise SECFinancialBridgeError("APPROVED_FILING_PERIOD_REQUIRED")
    fingerprint = sec_financial_fact_fingerprint(fact)
    fact_verification_reference = fact_references.get(fingerprint)
    if fact_verification_reference is None:
        raise SECFinancialBridgeError("INDEPENDENT_EXACT_FACT_VERIFICATION_REQUIRED")

    receipt = submission.observed_at
    bridge_observed_at = max(
        receipt,
        qualification.verification_completed_at,
        mapping.verified_at,
    )
    source_version = (
        f"SEC_EDGAR:{submission.accession}:{submission.document_name}:{source.sha256}"
    )
    source_record_id = str(
        research_identity(
            "sec-financial-source-record-v1",
            fingerprint,
            source_version,
            qualification.plan.plan_id,
            qualification.plan.expected_source_head,
            qualification.plan.expected_source_tree,
            observation.outcome.value,
            observation.reason_code,
            qualification.response.status_code,
            qualification.response.content_type,
            qualification.response.final_url,
            submission.content_sha256,
            submission.content_length,
            submission.embedded_document_sha256,
            submission.embedded_document_length,
            submission.filing_date.isoformat(),
            submission.report_period.isoformat(),
            submission.accepted_timestamp_raw,
            submission.document_sequence,
            submission.form,
            qualification.request_intent_reference,
            qualification.acquisition_record_reference,
            qualification.response_provenance_reference,
            qualification.document_verification_reference,
            qualification.accession_verification_reference,
            qualification.issuer_verification_reference,
            fact_verification_reference,
            mapping.issuer_reference,
            mapping.security_reference,
            receipt,
            qualification.verification_completed_at,
            mapping.verified_at,
            qualification.publication_at,
            qualification.publication_verification_reference,
        )
    )
    # XBRL filing dates are date-only. PM2C timeframe anchors use UTC midnight
    # for those economic dates; they do not stand in for publication or receipt.
    start_at = datetime.combine(
        period_end if period_start is None else period_start, time.min, UTC
    )
    end_at = (
        None if period_start is None else datetime.combine(period_end, time.min, UTC)
    )
    timeframe_kind = (
        EvidenceTimeframeKind.INSTANT
        if period_start is None
        else EvidenceTimeframeKind.PERIOD
    )
    pm2c_fact = SourceFact(
        entry=entry,
        subject=mapping.subject,
        source_identity="SEC_EDGAR_NATIVE_XBRL",
        source_version=source_version,
        outcome=EvidenceOutcome(
            AvailabilityStatus.AVAILABLE,
            fact.signed_decimal_value,
        ),
        timeframe=EvidenceTimeframe(timeframe_kind, start_at, end_at),
        available_at=receipt,
        observed_at=bridge_observed_at,
        effective_at=datetime.combine(period_end, time.min, UTC),
        source_record_id=source_record_id,
        source_content_digest=source.sha256,
        receipt_annotation="SEC_LOCAL_RECEIPT_IS_NOT_PUBLICATION",
    )
    return SECBridgedFact(
        source_fact=pm2c_fact,
        original_fact=fact,
        submission=submission,
        receipt_at=receipt,
        publication_at=qualification.publication_at,
        publication_verification_reference=(
            qualification.publication_verification_reference
        ),
        source_version=source_version,
        response_sha256=submission.content_sha256,
        response_length=submission.content_length,
        b1r_terminal_outcome=observation.outcome,
        b1r_terminal_reason=observation.reason_code,
        acquisition_record_reference=qualification.acquisition_record_reference,
        response_provenance_reference=qualification.response_provenance_reference,
        fact_verification_reference=fact_verification_reference,
        issuer_mapping_references=(
            mapping.issuer_reference,
            mapping.security_reference,
        ),
    )


def admit_sec_operational_snapshot(
    raw_response: bytes,
    *,
    qualification: SECOperationalDocumentQualification,
    security_mapping: SECIndependentSecurityMapping,
    field: SECFinancialField,
    period_start: date | None,
    period_end: date,
    graph: EvidenceGraph,
    membership: MembershipBinding,
    universe: tuple[str | Symbol, ...],
    decision_cutoff: datetime,
    additional_slots: tuple[SnapshotSlotRequest, ...] = (),
) -> ResearchSnapshot:
    """Admit the bridged fact through PM2C's exact operational snapshot gate."""

    if type(graph) is not EvidenceGraph:
        raise TypeError("graph must be EvidenceGraph")
    if type(membership) is not MembershipBinding:
        raise TypeError("membership must be MembershipBinding")
    bridged_fact = bridge_sec_financial_fact(
        raw_response,
        qualification=qualification,
        security_mapping=security_mapping,
        catalog=graph.catalog,
        field=field,
        period_start=period_start,
        period_end=period_end,
    )
    if any(
        node.evidence_id == bridged_fact.source_fact.evidence_id for node in graph.nodes
    ):
        raise SECFinancialBridgeError("SEC_FACT_ALREADY_IN_GRAPH")
    combined_graph = EvidenceGraph(
        graph.catalog,
        (*graph.nodes, bridged_fact.source_fact),
    )
    sec_slot = SnapshotSlotRequest(
        entry=bridged_fact.source_fact.entry,
        subject=bridged_fact.source_fact.subject,
        evidence_id=bridged_fact.source_fact.evidence_id,
    )
    return ResearchSnapshot.admit(
        graph=combined_graph,
        decision_cutoff=decision_cutoff,
        mode=SnapshotMode.OPERATIONAL,
        universe=universe,
        membership=membership,
        slots=(*additional_slots, sec_slot),
        version_witnesses=(),
    )


__all__ = [
    "SECBridgedFact",
    "SECFinancialBridgeError",
    "SECIndependentSecurityMapping",
    "SECOperationalDocumentQualification",
    "admit_sec_operational_snapshot",
    "bridge_sec_financial_fact",
    "sec_financial_catalog_entries",
    "sec_financial_fact_fingerprint",
]
