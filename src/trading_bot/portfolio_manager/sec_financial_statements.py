"""Bounded, offline extraction of normalized facts from native SEC XBRL XML.

This module intentionally supports one dated US GAAP namespace at a time. It
does not interpret inline XBRL, resolve schemas or taxonomies, fetch filings, or
turn the extracted data into operational evidence.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import stat
import sys
import xml.etree.ElementTree as ET
from collections import ChainMap
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from hashlib import sha256
from pathlib import Path, PureWindowsPath

type QName = tuple[str, str]
type Dimensions = tuple[tuple[QName, QName], ...]

MAX_INSTANCE_BYTES = 16 * 1024 * 1024
MAX_XML_NODES = 250_000
MAX_XML_DEPTH = 64
MAX_XML_NAMESPACE_DECLARATIONS = 512
MAX_FACTS = 100_000
MAX_CONTEXTS = 50_000
MAX_UNITS = 10_000
MAX_DIMENSIONS_PER_CONTEXT = 32
MAX_FACT_TEXT_CHARS = MAX_INSTANCE_BYTES
US_GAAP_2018 = "http://fasb.org/us-gaap/2018-01-31"
SEC_FINANCIAL_FIELD_NAMESPACE = US_GAAP_2018
ISO4217 = "http://www.xbrl.org/2003/iso4217"
XBRLI = "http://www.xbrl.org/2003/instance"
XBRLDI = "http://xbrl.org/2006/xbrldi"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
_CIK_SCHEME = "http://www.sec.gov/CIK"
_ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z")
_CIK = re.compile(r"[0-9]{1,10}\Z")
_XML_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]{0,119}\Z")
_DECIMALS = re.compile(r"(?:INF|-?[0-9]{1,4})\Z")
_PRECISION = re.compile(r"(?:INF|[1-9][0-9]{0,3})\Z")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_DECIMAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)\Z")
_USD: QName = (ISO4217, "USD")
_SHARES: QName = (XBRLI, "shares")


class SECFinancialField(StrEnum):
    """Exact source accounting concepts; bases are never silently combined.

    ``NET_INCOME`` is the generic ``NetIncomeLoss`` concept. It does not claim
    attribution to common shareholders and must not satisfy that distinct PM2B
    catalog field without a separately reviewed exact mapping.
    """

    REVENUE_INCLUDING_ASSESSED_TAX = "revenue_including_assessed_tax"
    REVENUE_EXCLUDING_ASSESSED_TAX = "revenue_excluding_assessed_tax"
    OPERATING_INCOME = "operating_income"
    NET_INCOME = "net_income"
    DILUTED_EPS = "diluted_eps"
    OPERATING_CASH_FLOW = "operating_cash_flow"
    CAPITAL_EXPENDITURES_PROPERTY_PLANT_EQUIPMENT = (
        "capital_expenditures_property_plant_equipment"
    )
    PAYMENTS_TO_ACQUIRE_PRODUCTIVE_ASSETS = "payments_to_acquire_productive_assets"
    CASH_AND_CASH_EQUIVALENTS = "cash_and_cash_equivalents"
    TOTAL_ASSETS = "total_assets"
    TOTAL_LIABILITIES = "total_liabilities"
    STOCKHOLDERS_EQUITY = "stockholders_equity"
    LONG_TERM_DEBT_CURRENT = "long_term_debt_current"
    LONG_TERM_DEBT_NONCURRENT = "long_term_debt_noncurrent"
    LONG_TERM_DEBT = "long_term_debt"
    LONG_TERM_DEBT_AND_CAPITAL_LEASE_OBLIGATIONS = (
        "long_term_debt_and_capital_lease_obligations"
    )
    LONG_TERM_DEBT_AND_CAPITAL_LEASE_OBLIGATIONS_CURRENT = (
        "long_term_debt_and_capital_lease_obligations_current"
    )
    LONG_TERM_DEBT_AND_FINANCE_LEASE_OBLIGATIONS_CURRENT = (
        "long_term_debt_and_finance_lease_obligations_current"
    )
    LONG_TERM_DEBT_AND_FINANCE_LEASE_OBLIGATIONS_NONCURRENT = (
        "long_term_debt_and_finance_lease_obligations_noncurrent"
    )


class SECFinancialPeriodKind(StrEnum):
    DURATION = "duration"
    INSTANT = "instant"


class SECFinancialFieldStatus(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    UNAVAILABLE = "unavailable"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class SECFinancialUnit:
    """An exact expanded XBRL unit numerator and optional denominator."""

    numerator: QName
    denominator: QName | None = None


@dataclass(frozen=True, slots=True)
class SECVerifiedSource:
    """Source identifiers verified by the caller and the supplied XML bytes."""

    sha256: str
    length: int
    accession: str
    document_name: str
    issuer_cik: str


@dataclass(frozen=True, slots=True)
class SECFinancialFact:
    """One source fact with unscaled signed value and original XBRL metadata."""

    source: SECVerifiedSource
    namespace: str
    concept: str
    source_fact_id: str | None
    context_id: str
    period_kind: SECFinancialPeriodKind
    period_start: date | None
    period_end: date
    unit_id: str
    unit: SECFinancialUnit
    dimensions: Dimensions
    signed_decimal_value: Decimal | None
    decimals: str | None
    precision: str | None
    is_nil: bool

    @property
    def field(self) -> SECFinancialField:
        """Return the field mapped from the exact namespace and concept."""

        return _FIELD_BY_QNAME[(self.namespace, self.concept)].field

    @property
    def value(self) -> Decimal | None:
        """Convenient value alias; nil remains distinct from numeric zero."""

        return self.signed_decimal_value


@dataclass(frozen=True, slots=True)
class SECUnsupportedObservation:
    """A recognized concept that cannot satisfy its exact mapping contract."""

    field: SECFinancialField
    namespace: str
    concept: str
    context_id: str | None
    source_fact_id: str | None
    reason_code: str
    fact: SECFinancialFact | None = None
    period_kind: SECFinancialPeriodKind | None = None
    period_start: date | None = None
    period_end: date | None = None
    dimensions: Dimensions | None = None


@dataclass(frozen=True, slots=True)
class SECUnsupportedConcept:
    """Known nearby source concepts that have no reviewed field mapping."""

    namespace: str
    concept: str
    context_id: str | None
    source_fact_id: str | None
    reason_code: str
    period_kind: SECFinancialPeriodKind | None = None
    period_start: date | None = None
    period_end: date | None = None
    unit_id: str | None = None
    unit: SECFinancialUnit | None = None
    dimensions: Dimensions | None = None
    raw_value_text: str = ""


@dataclass(frozen=True, slots=True)
class SECFinancialFieldResult:
    field: SECFinancialField
    status: SECFinancialFieldStatus
    facts: tuple[SECFinancialFact, ...] = ()
    reason_code: str | None = None
    conflicts: tuple[SECFinancialFact, ...] = ()
    unsupported: tuple[SECUnsupportedObservation, ...] = ()


@dataclass(frozen=True, slots=True)
class SECFinancialStatementReport:
    source: SECVerifiedSource
    results: tuple[SECFinancialFieldResult, ...]
    unsupported_observations: tuple[SECUnsupportedObservation, ...] = ()
    unsupported_concepts: tuple[SECUnsupportedConcept, ...] = ()

    def field_result(self, field: SECFinancialField) -> SECFinancialFieldResult:
        for result in self.results:
            if result.field is field:
                return result
        raise ValueError("unknown SEC financial field")


class SECFinancialInputError(ValueError):
    """Input could not be verified or is outside the bounded native parser."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class SECFinancialFieldDefinition:
    """Reviewed field mapping for one exact dated namespace/concept basis."""

    field: SECFinancialField
    namespace: str
    concept: str
    period_kind: SECFinancialPeriodKind
    unit: SECFinancialUnit


SEC_FINANCIAL_FIELD_DEFINITIONS = (
    SECFinancialFieldDefinition(
        SECFinancialField.REVENUE_INCLUDING_ASSESSED_TAX,
        US_GAAP_2018,
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        SECFinancialPeriodKind.DURATION,
        SECFinancialUnit(_USD),
    ),
    SECFinancialFieldDefinition(
        SECFinancialField.REVENUE_EXCLUDING_ASSESSED_TAX,
        US_GAAP_2018,
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        SECFinancialPeriodKind.DURATION,
        SECFinancialUnit(_USD),
    ),
    SECFinancialFieldDefinition(
        SECFinancialField.OPERATING_INCOME,
        US_GAAP_2018,
        "OperatingIncomeLoss",
        SECFinancialPeriodKind.DURATION,
        SECFinancialUnit(_USD),
    ),
    SECFinancialFieldDefinition(
        SECFinancialField.NET_INCOME,
        US_GAAP_2018,
        "NetIncomeLoss",
        SECFinancialPeriodKind.DURATION,
        SECFinancialUnit(_USD),
    ),
    SECFinancialFieldDefinition(
        SECFinancialField.DILUTED_EPS,
        US_GAAP_2018,
        "EarningsPerShareDiluted",
        SECFinancialPeriodKind.DURATION,
        SECFinancialUnit(_USD, _SHARES),
    ),
    SECFinancialFieldDefinition(
        SECFinancialField.OPERATING_CASH_FLOW,
        US_GAAP_2018,
        "NetCashProvidedByUsedInOperatingActivities",
        SECFinancialPeriodKind.DURATION,
        SECFinancialUnit(_USD),
    ),
    SECFinancialFieldDefinition(
        SECFinancialField.CAPITAL_EXPENDITURES_PROPERTY_PLANT_EQUIPMENT,
        US_GAAP_2018,
        "PaymentsToAcquirePropertyPlantAndEquipment",
        SECFinancialPeriodKind.DURATION,
        SECFinancialUnit(_USD),
    ),
    SECFinancialFieldDefinition(
        SECFinancialField.PAYMENTS_TO_ACQUIRE_PRODUCTIVE_ASSETS,
        US_GAAP_2018,
        "PaymentsToAcquireProductiveAssets",
        SECFinancialPeriodKind.DURATION,
        SECFinancialUnit(_USD),
    ),
    SECFinancialFieldDefinition(
        SECFinancialField.CASH_AND_CASH_EQUIVALENTS,
        US_GAAP_2018,
        "CashAndCashEquivalentsAtCarryingValue",
        SECFinancialPeriodKind.INSTANT,
        SECFinancialUnit(_USD),
    ),
    SECFinancialFieldDefinition(
        SECFinancialField.TOTAL_ASSETS,
        US_GAAP_2018,
        "Assets",
        SECFinancialPeriodKind.INSTANT,
        SECFinancialUnit(_USD),
    ),
    SECFinancialFieldDefinition(
        SECFinancialField.TOTAL_LIABILITIES,
        US_GAAP_2018,
        "Liabilities",
        SECFinancialPeriodKind.INSTANT,
        SECFinancialUnit(_USD),
    ),
    SECFinancialFieldDefinition(
        SECFinancialField.STOCKHOLDERS_EQUITY,
        US_GAAP_2018,
        "StockholdersEquity",
        SECFinancialPeriodKind.INSTANT,
        SECFinancialUnit(_USD),
    ),
    SECFinancialFieldDefinition(
        SECFinancialField.LONG_TERM_DEBT_CURRENT,
        US_GAAP_2018,
        "LongTermDebtCurrent",
        SECFinancialPeriodKind.INSTANT,
        SECFinancialUnit(_USD),
    ),
    SECFinancialFieldDefinition(
        SECFinancialField.LONG_TERM_DEBT_NONCURRENT,
        US_GAAP_2018,
        "LongTermDebtNoncurrent",
        SECFinancialPeriodKind.INSTANT,
        SECFinancialUnit(_USD),
    ),
    SECFinancialFieldDefinition(
        SECFinancialField.LONG_TERM_DEBT,
        US_GAAP_2018,
        "LongTermDebt",
        SECFinancialPeriodKind.INSTANT,
        SECFinancialUnit(_USD),
    ),
    SECFinancialFieldDefinition(
        SECFinancialField.LONG_TERM_DEBT_AND_CAPITAL_LEASE_OBLIGATIONS,
        US_GAAP_2018,
        "LongTermDebtAndCapitalLeaseObligations",
        SECFinancialPeriodKind.INSTANT,
        SECFinancialUnit(_USD),
    ),
    SECFinancialFieldDefinition(
        SECFinancialField.LONG_TERM_DEBT_AND_CAPITAL_LEASE_OBLIGATIONS_CURRENT,
        US_GAAP_2018,
        "LongTermDebtAndCapitalLeaseObligationsCurrent",
        SECFinancialPeriodKind.INSTANT,
        SECFinancialUnit(_USD),
    ),
    SECFinancialFieldDefinition(
        SECFinancialField.LONG_TERM_DEBT_AND_FINANCE_LEASE_OBLIGATIONS_CURRENT,
        US_GAAP_2018,
        "LongTermDebtAndFinanceLeaseObligationsCurrent",
        SECFinancialPeriodKind.INSTANT,
        SECFinancialUnit(_USD),
    ),
    SECFinancialFieldDefinition(
        SECFinancialField.LONG_TERM_DEBT_AND_FINANCE_LEASE_OBLIGATIONS_NONCURRENT,
        US_GAAP_2018,
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
        SECFinancialPeriodKind.INSTANT,
        SECFinancialUnit(_USD),
    ),
)
_FIELD_BY_QNAME = {
    (spec.namespace, spec.concept): spec for spec in SEC_FINANCIAL_FIELD_DEFINITIONS
}
_FIELD_BY_LOCAL_NAME = {spec.concept: spec for spec in SEC_FINANCIAL_FIELD_DEFINITIONS}
_UNSUPPORTED_CONCEPT_LOCAL_NAMES = frozenset(
    {
        "DebtAndCapitalLeaseObligations",
        "LongTermDebtFairValue",
        "OperatingLeaseLiability",
    }
)
_FIELD_BY_VALUE = {
    definition.field: definition for definition in SEC_FINANCIAL_FIELD_DEFINITIONS
}


def financial_field_definition(
    field: SECFinancialField,
) -> SECFinancialFieldDefinition:
    """Return one exact immutable source mapping, if this field is supported."""

    try:
        return _FIELD_BY_VALUE[field]
    except (KeyError, TypeError) as error:
        raise ValueError("unknown SEC financial field") from error


@dataclass(frozen=True, slots=True)
class _Context:
    cik: str
    period_kind: SECFinancialPeriodKind
    period_start: date | None
    period_end: date
    dimensions: Dimensions


@dataclass(frozen=True, slots=True)
class _ContextDates:
    period_kind: SECFinancialPeriodKind
    period_start: date | None
    period_end: date
    dimensions: Dimensions


@dataclass(frozen=True, slots=True)
class _RawFact:
    namespace: str
    concept: str
    attributes: dict[str, str]
    text: str
    has_children: bool


class _BoundedTarget:
    """Small XML target with DTD rejection and parser-side resource bounds."""

    def __init__(self) -> None:
        self.root: ET.Element | None = None
        self._stack: list[ET.Element] = []
        self._namespace_stack: list[Mapping[str, str]] = []
        self._pending_namespaces: dict[str, str] = {}
        self._last: ET.Element | None = None
        self.namespace_declarations = 0
        self.qname_scopes: dict[int, Mapping[str, str]] = {}
        self.nodes = 0
        self.max_depth = 0

    def start_ns(self, prefix: str, uri: str) -> None:
        self.namespace_declarations += 1
        if self.namespace_declarations > MAX_XML_NAMESPACE_DECLARATIONS:
            raise SECFinancialInputError("XML_NAMESPACE_LIMIT_REACHED")
        self._pending_namespaces[prefix or ""] = uri

    def end_ns(self, _prefix: str) -> None:
        return

    def start(self, tag: str, attributes: dict[str, str]) -> ET.Element:
        self.nodes += 1
        if self.nodes > MAX_XML_NODES:
            raise SECFinancialInputError("XML_NODE_LIMIT_REACHED")
        depth = len(self._stack) + 1
        self.max_depth = max(self.max_depth, depth)
        if depth > MAX_XML_DEPTH:
            raise SECFinancialInputError("XML_DEPTH_LIMIT_REACHED")
        parent_scope = self._namespace_stack[-1] if self._namespace_stack else {}
        scope: Mapping[str, str] = (
            ChainMap(dict(self._pending_namespaces), parent_scope)
            if self._pending_namespaces
            else parent_scope
        )
        self._pending_namespaces.clear()
        self._namespace_stack.append(scope)
        self._last = None
        element = ET.Element(tag, attributes)
        if self._stack:
            self._stack[-1].append(element)
        elif self.root is None:
            self.root = element
        else:
            raise SECFinancialInputError("XML_MULTIPLE_ROOTS")
        if tag in (f"{{{XBRLDI}}}explicitMember", f"{{{XBRLI}}}measure"):
            self.qname_scopes[id(element)] = scope
        self._stack.append(element)
        return element

    def end(self, _tag: str) -> ET.Element:
        if not self._stack or not self._namespace_stack:
            raise SECFinancialInputError("XML_ELEMENT_STACK_INVALID")
        element = self._stack.pop()
        self._namespace_stack.pop()
        self._last = element
        return element

    def data(self, data: str) -> None:
        if not self._stack:
            if data.strip():
                raise SECFinancialInputError("XML_TEXT_OUTSIDE_ROOT")
            return
        if self._last is not None:
            self._last.tail = (self._last.tail or "") + data
            text = self._last.tail
        else:
            element = self._stack[-1]
            element.text = (element.text or "") + data
            text = element.text
        if len(text) > MAX_FACT_TEXT_CHARS:
            raise SECFinancialInputError("XML_TEXT_LIMIT_REACHED")

    def doctype(
        self, _name: str, _public_id: str | None, _system_id: str | None
    ) -> None:
        raise SECFinancialInputError("XML_DTD_FORBIDDEN")

    def close(self) -> ET.Element:
        if self.root is None:
            raise SECFinancialInputError("XML_ROOT_MISSING")
        return self.root


def extract_sec_financial_statement_bytes(
    raw_bytes: bytes,
    *,
    expected_sha256: str,
    expected_length: int,
    accession: str,
    document_name: str,
    expected_cik: str,
) -> SECFinancialStatementReport:
    """Verify and extract one native XBRL instance entirely from supplied bytes."""

    if type(raw_bytes) is not bytes:
        raise SECFinancialInputError("INSTANCE_BYTES_REQUIRED")
    if len(raw_bytes) > MAX_INSTANCE_BYTES:
        raise SECFinancialInputError("INSTANCE_BYTE_LIMIT_REACHED")
    if type(expected_length) is not int or expected_length != len(raw_bytes):
        raise SECFinancialInputError("INSTANCE_LENGTH_MISMATCH")
    if not isinstance(expected_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", expected_sha256
    ):
        raise SECFinancialInputError("EXPECTED_SHA256_INVALID")
    actual_sha256 = sha256(raw_bytes).hexdigest()
    if actual_sha256 != expected_sha256:
        raise SECFinancialInputError("INSTANCE_SHA256_MISMATCH")
    if not isinstance(accession, str) or not _ACCESSION.fullmatch(accession):
        raise SECFinancialInputError("ACCESSION_INVALID")
    if (
        not isinstance(document_name, str)
        or not document_name
        or len(document_name) > 255
        or Path(document_name).name != document_name
        or "/" in document_name
        or "\\" in document_name
        or "\x00" in document_name
    ):
        raise SECFinancialInputError("DOCUMENT_NAME_INVALID")
    if not isinstance(expected_cik, str) or not _CIK.fullmatch(expected_cik):
        raise SECFinancialInputError("EXPECTED_CIK_INVALID")

    target = _BoundedTarget()
    parser = ET.XMLParser(target=target)
    contexts: dict[str, _Context] = {}
    units: dict[str, SECFinancialUnit] = {}
    raw_facts: list[_RawFact] = []
    raw_unsupported_concepts: list[_RawFact] = []
    try:
        parser.feed(raw_bytes)
        root = parser.close()
    except SECFinancialInputError:
        raise
    except (ET.ParseError, ValueError, UnicodeError) as error:
        raise SECFinancialInputError("XML_DOCUMENT_INVALID") from error

    if root.tag != f"{{{XBRLI}}}xbrl":
        raise SECFinancialInputError("NATIVE_XBRL_INSTANCE_REQUIRED")
    for child in root:
        if child.tag == f"{{{XBRLI}}}context":
            context = _parse_context(child, target.qname_scopes)
            context_id = child.attrib.get("id")
            if not context_id or context_id in contexts:
                raise SECFinancialInputError("XBRL_CONTEXT_ID_MISSING_OR_DUPLICATE")
            if len(contexts) >= MAX_CONTEXTS:
                raise SECFinancialInputError("XBRL_CONTEXT_LIMIT_REACHED")
            contexts[context_id] = context
        elif child.tag == f"{{{XBRLI}}}unit":
            unit_id = child.attrib.get("id")
            if not unit_id or unit_id in units:
                raise SECFinancialInputError("XBRL_UNIT_ID_MISSING_OR_DUPLICATE")
            if len(units) >= MAX_UNITS:
                raise SECFinancialInputError("XBRL_UNIT_LIMIT_REACHED")
            units[unit_id] = _parse_unit(child, target.qname_scopes)
        elif isinstance(child.tag, str) and child.tag.startswith("{"):
            namespace, concept = child.tag[1:].split("}", 1)
            if (
                concept in _FIELD_BY_LOCAL_NAME
                or concept in _UNSUPPORTED_CONCEPT_LOCAL_NAMES
            ):
                if len(raw_facts) + len(raw_unsupported_concepts) >= MAX_FACTS:
                    raise SECFinancialInputError("XBRL_FACT_LIMIT_REACHED")
                raw_fact = _RawFact(
                    namespace,
                    concept,
                    dict(child.attrib),
                    (child.text or "").strip(),
                    bool(list(child)),
                )
                if concept in _FIELD_BY_LOCAL_NAME:
                    raw_facts.append(raw_fact)
                else:
                    raw_unsupported_concepts.append(raw_fact)

    source_ciks = {context.cik for context in contexts.values()}
    if not source_ciks or source_ciks != {expected_cik}:
        raise SECFinancialInputError("XBRL_ISSUER_CIK_MISMATCH")
    source = SECVerifiedSource(
        sha256=actual_sha256,
        length=len(raw_bytes),
        accession=accession,
        document_name=document_name,
        issuer_cik=expected_cik,
    )
    valid_by_field: dict[SECFinancialField, list[SECFinancialFact]] = {
        field: [] for field in SECFinancialField
    }
    unsupported: list[SECUnsupportedObservation] = []
    unsupported_concepts: list[SECUnsupportedConcept] = []

    for raw_fact in raw_unsupported_concepts:
        context_id = raw_fact.attributes.get("contextRef")
        context = contexts.get(context_id) if context_id is not None else None
        unit_id = raw_fact.attributes.get("unitRef")
        unsupported_concepts.append(
            SECUnsupportedConcept(
                namespace=raw_fact.namespace,
                concept=raw_fact.concept,
                context_id=context_id,
                source_fact_id=raw_fact.attributes.get("id"),
                reason_code=(
                    "UNSUPPORTED_CONCEPT_NAMESPACE"
                    if raw_fact.namespace != US_GAAP_2018
                    else "CONCEPT_BASIS_NOT_MAPPED"
                ),
                period_kind=context.period_kind if context else None,
                period_start=context.period_start if context else None,
                period_end=context.period_end if context else None,
                unit_id=unit_id,
                unit=units.get(unit_id) if unit_id is not None else None,
                dimensions=context.dimensions if context else None,
                raw_value_text=("" if raw_fact.has_children else raw_fact.text),
            )
        )

    for raw_fact in raw_facts:
        spec = _FIELD_BY_LOCAL_NAME[raw_fact.concept]
        context_id = raw_fact.attributes.get("contextRef")
        fact_id = raw_fact.attributes.get("id")
        context = contexts.get(context_id) if context_id is not None else None
        if raw_fact.namespace != US_GAAP_2018:
            unsupported.append(
                SECUnsupportedObservation(
                    spec.field,
                    raw_fact.namespace,
                    raw_fact.concept,
                    context_id,
                    fact_id,
                    "US_GAAP_NAMESPACE_NOT_MAPPED",
                    period_kind=context.period_kind if context else None,
                    period_start=context.period_start if context else None,
                    period_end=context.period_end if context else None,
                    dimensions=context.dimensions if context else None,
                )
            )
            continue
        if (raw_fact.namespace, raw_fact.concept) not in _FIELD_BY_QNAME:
            raise SECFinancialInputError("XBRL_CONCEPT_MAPPING_INVALID")
        if not context_id or context_id not in contexts:
            raise SECFinancialInputError("XBRL_FACT_CONTEXT_REFERENCE_INVALID")
        context = contexts[context_id]
        allowed_fact_attributes = {
            "id",
            "contextRef",
            "unitRef",
            "decimals",
            "precision",
            f"{{{XSI}}}nil",
        }
        if raw_fact.has_children:
            unsupported.append(
                SECUnsupportedObservation(
                    spec.field,
                    raw_fact.namespace,
                    raw_fact.concept,
                    context_id,
                    fact_id,
                    "XBRL_MAPPED_FACT_CHILD_ELEMENTS_UNSUPPORTED",
                    period_kind=context.period_kind,
                    period_start=context.period_start,
                    period_end=context.period_end,
                    dimensions=context.dimensions,
                )
            )
            continue
        if set(raw_fact.attributes) - allowed_fact_attributes:
            unsupported.append(
                SECUnsupportedObservation(
                    spec.field,
                    raw_fact.namespace,
                    raw_fact.concept,
                    context_id,
                    fact_id,
                    "XBRL_MAPPED_FACT_ATTRIBUTES_UNSUPPORTED",
                    period_kind=context.period_kind,
                    period_start=context.period_start,
                    period_end=context.period_end,
                    dimensions=context.dimensions,
                )
            )
            continue
        unit_id = raw_fact.attributes.get("unitRef")
        if not unit_id or unit_id not in units:
            raise SECFinancialInputError("XBRL_FACT_UNIT_REFERENCE_INVALID")
        is_nil = _parse_nil(raw_fact.attributes.get(f"{{{XSI}}}nil"))
        value = _parse_fact_value(raw_fact.text, is_nil)
        decimals = raw_fact.attributes.get("decimals")
        precision = raw_fact.attributes.get("precision")
        _validate_precision(decimals, precision)
        fact = SECFinancialFact(
            source=source,
            namespace=raw_fact.namespace,
            concept=raw_fact.concept,
            source_fact_id=fact_id,
            context_id=context_id,
            period_kind=context.period_kind,
            period_start=context.period_start,
            period_end=context.period_end,
            unit_id=unit_id,
            unit=units[unit_id],
            dimensions=context.dimensions,
            signed_decimal_value=value,
            decimals=decimals,
            precision=precision,
            is_nil=is_nil,
        )
        if context.period_kind is not spec.period_kind:
            unsupported.append(
                SECUnsupportedObservation(
                    spec.field,
                    raw_fact.namespace,
                    raw_fact.concept,
                    context_id,
                    fact_id,
                    "XBRL_PERIOD_KIND_UNSUPPORTED_FOR_FIELD",
                    fact,
                    context.period_kind,
                    context.period_start,
                    context.period_end,
                    context.dimensions,
                )
            )
        elif fact.unit != spec.unit:
            unsupported.append(
                SECUnsupportedObservation(
                    spec.field,
                    raw_fact.namespace,
                    raw_fact.concept,
                    context_id,
                    fact_id,
                    "XBRL_UNIT_BASIS_UNSUPPORTED_FOR_FIELD",
                    fact,
                    context.period_kind,
                    context.period_start,
                    context.period_end,
                    context.dimensions,
                )
            )
        else:
            valid_by_field[spec.field].append(fact)

    results: list[SECFinancialFieldResult] = []
    for spec in SEC_FINANCIAL_FIELD_DEFINITIONS:
        facts = tuple(valid_by_field[spec.field])
        conflicts = _find_conflicts(facts)
        if conflicts:
            results.append(
                SECFinancialFieldResult(
                    spec.field,
                    SECFinancialFieldStatus.AMBIGUOUS,
                    facts=facts,
                    reason_code="CONFLICTING_DUPLICATE_FACTS",
                    conflicts=conflicts,
                )
            )
        elif facts:
            results.append(
                SECFinancialFieldResult(
                    spec.field,
                    SECFinancialFieldStatus.AVAILABLE,
                    facts=facts,
                )
            )
        else:
            has_unsupported = any(item.field is spec.field for item in unsupported)
            results.append(
                SECFinancialFieldResult(
                    spec.field,
                    (
                        SECFinancialFieldStatus.UNAVAILABLE
                        if has_unsupported
                        else SECFinancialFieldStatus.MISSING
                    ),
                    reason_code=(
                        "SUPPORTED_CONCEPT_HAS_UNSUPPORTED_OBSERVATION"
                        if has_unsupported
                        else "SUPPORTED_CONCEPT_NOT_PRESENT"
                    ),
                )
            )
    return SECFinancialStatementReport(
        source,
        tuple(results),
        tuple(unsupported),
        tuple(unsupported_concepts),
    )


def extract_sec_financial_statement(
    path: str | os.PathLike[str],
    *,
    expected_sha256: str,
    expected_length: int,
    accession: str,
    document_name: str,
    expected_cik: str,
) -> SECFinancialStatementReport:
    """Read one verified local file and delegate to the public bytes extractor."""

    raw_bytes = _read_bounded_local_file(path, expected_length)
    return extract_sec_financial_statement_bytes(
        raw_bytes,
        expected_sha256=expected_sha256,
        expected_length=expected_length,
        accession=accession,
        document_name=document_name,
        expected_cik=expected_cik,
    )


def select_fact(
    report: SECFinancialStatementReport,
    field: SECFinancialField,
    *,
    period_start: date | None,
    period_end: date,
    dimensions: Dimensions = (),
) -> SECFinancialFieldResult:
    """Select exactly one date/dimension observation, preserving uncertainty."""

    result = report.field_result(field)
    candidates = tuple(
        fact
        for fact in result.facts
        if fact.period_start == period_start
        and fact.period_end == period_end
        and fact.dimensions == dimensions
    )
    unsupported_items: list[SECUnsupportedObservation] = []
    for item in report.unsupported_observations:
        if item.field is not field:
            continue
        item_start = item.fact.period_start if item.fact else item.period_start
        item_end = item.fact.period_end if item.fact else item.period_end
        item_dimensions = item.fact.dimensions if item.fact else item.dimensions
        if (
            item_start == period_start
            and item_end == period_end
            and item_dimensions == dimensions
        ):
            unsupported_items.append(item)
    unsupported = tuple(unsupported_items)
    blocking_unsupported = tuple(
        item
        for item in unsupported
        if item.reason_code != "US_GAAP_NAMESPACE_NOT_MAPPED"
    )
    if blocking_unsupported:
        return SECFinancialFieldResult(
            field,
            SECFinancialFieldStatus.UNAVAILABLE,
            facts=candidates,
            reason_code="EXACT_GRAIN_HAS_UNSUPPORTED_CANDIDATE",
            unsupported=blocking_unsupported,
        )
    if not candidates:
        if unsupported:
            return SECFinancialFieldResult(
                field,
                SECFinancialFieldStatus.UNAVAILABLE,
                reason_code="EXACT_GRAIN_HAS_UNMAPPED_NAMESPACE_CANDIDATE",
                unsupported=unsupported,
            )
        return SECFinancialFieldResult(
            field,
            SECFinancialFieldStatus.MISSING,
            reason_code="EXACT_PERIOD_AND_DIMENSION_OBSERVATION_NOT_FOUND",
        )
    semantic_variants = {
        (
            fact.concept,
            fact.period_kind,
            fact.period_start,
            fact.period_end,
            fact.unit,
            fact.dimensions,
            fact.signed_decimal_value,
            fact.decimals,
            fact.precision,
            fact.is_nil,
        )
        for fact in candidates
    }
    if len(semantic_variants) > 1:
        return SECFinancialFieldResult(
            field,
            SECFinancialFieldStatus.AMBIGUOUS,
            reason_code="MULTIPLE_EXACT_PERIOD_AND_DIMENSION_OBSERVATIONS",
            conflicts=candidates,
        )
    if all(fact.is_nil for fact in candidates):
        return SECFinancialFieldResult(
            field,
            SECFinancialFieldStatus.UNAVAILABLE,
            facts=candidates,
            reason_code="EXACT_GRAIN_FACTS_ARE_NIL",
        )
    return SECFinancialFieldResult(
        field,
        SECFinancialFieldStatus.AVAILABLE,
        facts=candidates,
    )


def _parse_context(
    element: ET.Element, qname_scopes: dict[int, Mapping[str, str]]
) -> _Context:
    context_id = element.attrib.get("id")
    _require_attributes(element, {"id"}, "XBRL_CONTEXT_ATTRIBUTES_UNSUPPORTED")
    _require_child_tags(
        element,
        {f"{{{XBRLI}}}entity", f"{{{XBRLI}}}period", f"{{{XBRLI}}}scenario"},
        "XBRL_CONTEXT_CHILDREN_UNSUPPORTED",
    )
    entities = element.findall(f"{{{XBRLI}}}entity")
    periods = element.findall(f"{{{XBRLI}}}period")
    if not context_id or len(entities) != 1 or len(periods) != 1:
        raise SECFinancialInputError("XBRL_CONTEXT_SHAPE_UNSUPPORTED")
    identifiers = entities[0].findall(f"{{{XBRLI}}}identifier")
    _require_attributes(entities[0], set(), "XBRL_ENTITY_ATTRIBUTES_UNSUPPORTED")
    _require_child_tags(
        entities[0],
        {f"{{{XBRLI}}}identifier", f"{{{XBRLI}}}segment"},
        "XBRL_ENTITY_CHILDREN_UNSUPPORTED",
    )
    if len(identifiers) != 1 or identifiers[0].attrib.get("scheme") != _CIK_SCHEME:
        raise SECFinancialInputError("XBRL_ENTITY_IDENTIFIER_UNSUPPORTED")
    _require_attributes(
        identifiers[0], {"scheme"}, "XBRL_ENTITY_IDENTIFIER_ATTRIBUTES_UNSUPPORTED"
    )
    if list(identifiers[0]):
        raise SECFinancialInputError("XBRL_ENTITY_IDENTIFIER_SHAPE_UNSUPPORTED")
    cik = (identifiers[0].text or "").strip()
    if not _CIK.fullmatch(cik):
        raise SECFinancialInputError("XBRL_ENTITY_CIK_UNSUPPORTED")
    period = periods[0]
    _require_attributes(period, set(), "XBRL_PERIOD_ATTRIBUTES_UNSUPPORTED")
    _require_child_tags(
        period,
        {
            f"{{{XBRLI}}}startDate",
            f"{{{XBRLI}}}endDate",
            f"{{{XBRLI}}}instant",
        },
        "XBRL_PERIOD_CHILDREN_UNSUPPORTED",
    )
    starts = period.findall(f"{{{XBRLI}}}startDate")
    ends = period.findall(f"{{{XBRLI}}}endDate")
    instants = period.findall(f"{{{XBRLI}}}instant")
    if len(starts) == 1 and len(ends) == 1 and not instants:
        period_kind = SECFinancialPeriodKind.DURATION
        if list(starts[0]) or list(ends[0]):
            raise SECFinancialInputError("XBRL_PERIOD_DATE_SHAPE_UNSUPPORTED")
        period_start = _parse_date(starts[0].text, "XBRL_PERIOD_START_INVALID")
        period_end = _parse_date(ends[0].text, "XBRL_PERIOD_END_INVALID")
        if period_start >= period_end:
            raise SECFinancialInputError("XBRL_PERIOD_ORDER_INVALID")
    elif len(instants) == 1 and not starts and not ends:
        period_kind = SECFinancialPeriodKind.INSTANT
        period_start = None
        if list(instants[0]):
            raise SECFinancialInputError("XBRL_PERIOD_DATE_SHAPE_UNSUPPORTED")
        period_end = _parse_date(instants[0].text, "XBRL_INSTANT_INVALID")
    else:
        raise SECFinancialInputError("XBRL_PERIOD_SHAPE_UNSUPPORTED")

    dimensions: list[tuple[QName, QName]] = []
    segments = entities[0].findall(f"{{{XBRLI}}}segment")
    scenarios = element.findall(f"{{{XBRLI}}}scenario")
    if len(segments) > 1 or len(scenarios) > 1:
        raise SECFinancialInputError("XBRL_DIMENSION_CONTAINER_DUPLICATE")
    for container in (*segments, *scenarios):
        _require_attributes(
            container, set(), "XBRL_DIMENSION_CONTAINER_ATTRIBUTES_UNSUPPORTED"
        )
        for child in list(container):
            if child.tag == f"{{{XBRLDI}}}typedMember":
                raise SECFinancialInputError("TYPED_XBRL_DIMENSION_UNSUPPORTED")
            if child.tag != f"{{{XBRLDI}}}explicitMember":
                raise SECFinancialInputError("XBRL_DIMENSION_SHAPE_UNSUPPORTED")
            _require_attributes(
                child, {"dimension"}, "XBRL_DIMENSION_ATTRIBUTES_UNSUPPORTED"
            )
            if list(child):
                raise SECFinancialInputError("XBRL_DIMENSION_MEMBER_SHAPE_UNSUPPORTED")
            scope = qname_scopes.get(id(child), {})
            axis = _resolve_qname(child.attrib.get("dimension", ""), scope)
            member = _resolve_qname((child.text or "").strip(), scope)
            dimensions.append((axis, member))
            if len(dimensions) > MAX_DIMENSIONS_PER_CONTEXT:
                raise SECFinancialInputError("XBRL_DIMENSION_LIMIT_REACHED")
    if len({axis for axis, _member in dimensions}) != len(dimensions):
        raise SECFinancialInputError("XBRL_DUPLICATE_DIMENSION_AXIS")
    return _Context(
        cik, period_kind, period_start, period_end, tuple(sorted(dimensions))
    )


def _parse_unit(
    element: ET.Element, qname_scopes: dict[int, Mapping[str, str]]
) -> SECFinancialUnit:
    _require_attributes(element, {"id"}, "XBRL_UNIT_ATTRIBUTES_UNSUPPORTED")
    measures = element.findall(f"{{{XBRLI}}}measure")
    divides = element.findall(f"{{{XBRLI}}}divide")
    if len(divides) == 1 and not measures and len(list(element)) == 1:
        divide = divides[0]
        _require_attributes(divide, set(), "XBRL_DIVIDED_UNIT_ATTRIBUTES_UNSUPPORTED")
        _require_child_tags(
            divide,
            {f"{{{XBRLI}}}unitNumerator", f"{{{XBRLI}}}unitDenominator"},
            "XBRL_DIVIDED_UNIT_CHILDREN_UNSUPPORTED",
        )
        numerators = divide.findall(f"{{{XBRLI}}}unitNumerator")
        denominators = divide.findall(f"{{{XBRLI}}}unitDenominator")
        if len(numerators) != 1 or len(denominators) != 1:
            raise SECFinancialInputError("XBRL_DIVIDED_UNIT_SHAPE_UNSUPPORTED")
        numerator = _unit_measure(numerators[0], qname_scopes)
        denominator = _unit_measure(denominators[0], qname_scopes)
        return SECFinancialUnit(numerator, denominator)
    if len(measures) == 1 and not divides and len(list(element)) == 1:
        return SECFinancialUnit(_resolve_measure(measures[0], qname_scopes))
    raise SECFinancialInputError("XBRL_UNIT_SHAPE_UNSUPPORTED")


def _unit_measure(
    element: ET.Element, qname_scopes: dict[int, Mapping[str, str]]
) -> QName:
    _require_attributes(element, set(), "XBRL_UNIT_COMPONENT_ATTRIBUTES_UNSUPPORTED")
    measures = element.findall(f"{{{XBRLI}}}measure")
    if len(measures) != 1 or len(list(element)) != 1:
        raise SECFinancialInputError("XBRL_UNIT_COMPONENT_UNSUPPORTED")
    return _resolve_measure(measures[0], qname_scopes)


def _resolve_measure(
    element: ET.Element, qname_scopes: dict[int, Mapping[str, str]]
) -> QName:
    _require_attributes(element, set(), "XBRL_MEASURE_ATTRIBUTES_UNSUPPORTED")
    if list(element):
        raise SECFinancialInputError("XBRL_MEASURE_SHAPE_UNSUPPORTED")
    scope = qname_scopes.get(id(element), {})
    return _resolve_qname((element.text or "").strip(), scope)


def _resolve_qname(value: str, namespace_scope: Mapping[str, str]) -> QName:
    if not value or value.count(":") > 1:
        raise SECFinancialInputError("XBRL_QNAME_UNSUPPORTED")
    if ":" in value:
        prefix, local = value.split(":", 1)
    else:
        prefix, local = "", value
    namespace = namespace_scope.get(prefix)
    if namespace is None or not _XML_NAME.fullmatch(local):
        raise SECFinancialInputError("XBRL_QNAME_NAMESPACE_UNSUPPORTED")
    return namespace, local


def _require_attributes(
    element: ET.Element, allowed: set[str], reason_code: str
) -> None:
    if set(element.attrib) - allowed:
        raise SECFinancialInputError(reason_code)


def _require_child_tags(
    element: ET.Element, allowed: set[str], reason_code: str
) -> None:
    if any(child.tag not in allowed for child in list(element)):
        raise SECFinancialInputError(reason_code)


def _parse_date(value: str | None, reason_code: str) -> date:
    if not isinstance(value, str) or not _DATE.fullmatch(value.strip()):
        raise SECFinancialInputError(reason_code)
    try:
        return date.fromisoformat(value.strip())
    except ValueError as error:
        raise SECFinancialInputError(reason_code) from error


def _parse_nil(value: str | None) -> bool:
    if value is None or value in {"false", "0"}:
        return False
    if value in {"true", "1"}:
        return True
    raise SECFinancialInputError("XBRL_NIL_ATTRIBUTE_INVALID")


def _parse_fact_value(text: str, is_nil: bool) -> Decimal | None:
    if is_nil:
        if text:
            raise SECFinancialInputError("XBRL_NIL_FACT_HAS_VALUE")
        return None
    if not text:
        raise SECFinancialInputError("XBRL_NUMERIC_FACT_VALUE_MISSING")
    if len(text) > 128 or not _DECIMAL.fullmatch(text):
        raise SECFinancialInputError("XBRL_DECIMAL_VALUE_INVALID")
    try:
        value = Decimal(text)
    except InvalidOperation as error:
        raise SECFinancialInputError("XBRL_DECIMAL_VALUE_INVALID") from error
    if not value.is_finite():
        raise SECFinancialInputError("XBRL_DECIMAL_VALUE_NONFINITE")
    return value


def _validate_precision(decimals: str | None, precision: str | None) -> None:
    if decimals is not None and precision is not None:
        raise SECFinancialInputError("XBRL_DECIMALS_AND_PRECISION_BOTH_PRESENT")
    if decimals is not None and not _DECIMALS.fullmatch(decimals):
        raise SECFinancialInputError("XBRL_DECIMALS_ATTRIBUTE_INVALID")
    if precision is not None and not _PRECISION.fullmatch(precision):
        raise SECFinancialInputError("XBRL_PRECISION_ATTRIBUTE_INVALID")


def _find_conflicts(
    facts: tuple[SECFinancialFact, ...],
) -> tuple[SECFinancialFact, ...]:
    grouped: dict[tuple[object, ...], list[SECFinancialFact]] = {}
    for fact in facts:
        key = (
            fact.concept,
            fact.period_kind,
            fact.period_start,
            fact.period_end,
            fact.dimensions,
        )
        grouped.setdefault(key, []).append(fact)
    conflicts: list[SECFinancialFact] = []
    for duplicate_group in grouped.values():
        variants = {
            (
                fact.period_kind,
                fact.period_start,
                fact.period_end,
                fact.unit,
                fact.dimensions,
                fact.signed_decimal_value,
                fact.decimals,
                fact.precision,
                fact.is_nil,
            )
            for fact in duplicate_group
        }
        if len(variants) > 1:
            conflicts.extend(duplicate_group)
    return tuple(conflicts)


def _read_bounded_local_file(
    value: str | os.PathLike[str], expected_length: int
) -> bytes:
    if isinstance(value, os.PathLike):
        raw_path = os.fspath(value)
    elif isinstance(value, str):
        raw_path = value
    else:
        raise SECFinancialInputError("LOCAL_PATH_REQUIRED")
    if not raw_path or "\x00" in raw_path:
        raise SECFinancialInputError("LOCAL_PATH_INVALID")
    if raw_path.startswith(("\\\\", "//", "\\\\?\\", "\\\\.\\")):
        raise SECFinancialInputError("UNC_OR_DEVICE_PATH_FORBIDDEN")
    if ".." in PureWindowsPath(raw_path).parts:
        raise SECFinancialInputError("PATH_TRAVERSAL_FORBIDDEN")
    if os.name == "nt":
        windows_path = PureWindowsPath(raw_path)
        if not windows_path.is_absolute() or not re.fullmatch(
            r"[A-Za-z]:", windows_path.drive
        ):
            raise SECFinancialInputError("LOCAL_DRIVE_ABSOLUTE_PATH_REQUIRED")
        drive_type = ctypes.windll.kernel32.GetDriveTypeW(f"{windows_path.drive}\\")
        if drive_type == 4:  # DRIVE_REMOTE: reject mapped SMB/network drives too.
            raise SECFinancialInputError("REMOTE_DRIVE_FORBIDDEN")
    else:
        if not Path(raw_path).is_absolute():
            raise SECFinancialInputError("ABSOLUTE_LOCAL_PATH_REQUIRED")
    path = Path(os.path.abspath(raw_path))
    _reject_reparse_components(path)
    if (
        type(expected_length) is not int
        or not 0 <= expected_length <= MAX_INSTANCE_BYTES
    ):
        raise SECFinancialInputError("EXPECTED_LENGTH_INVALID")
    try:
        with path.open("rb") as handle:
            file_info = os.fstat(handle.fileno())
            if not stat.S_ISREG(file_info.st_mode):
                raise SECFinancialInputError("LOCAL_REGULAR_FILE_REQUIRED")
            if file_info.st_size != expected_length:
                raise SECFinancialInputError("INSTANCE_LENGTH_MISMATCH")
            raw_bytes = handle.read(MAX_INSTANCE_BYTES + 1)
    except SECFinancialInputError:
        raise
    except OSError as error:
        raise SECFinancialInputError("LOCAL_FILE_READ_FAILED") from error
    if len(raw_bytes) != expected_length:
        raise SECFinancialInputError("INSTANCE_LENGTH_MISMATCH")
    return raw_bytes


def _reject_reparse_components(path: Path) -> None:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    cursor = Path(path.anchor)
    for component in path.parts[1:]:
        cursor = cursor / component
        try:
            info = cursor.lstat()
        except OSError as error:
            raise SECFinancialInputError("LOCAL_PATH_COMPONENT_UNAVAILABLE") from error
        if (
            stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & reparse_flag
        ):
            raise SECFinancialInputError("LOCAL_REPARSE_PATH_FORBIDDEN")


def _report_json(
    report: SECFinancialStatementReport,
    *,
    period_start: date | None = None,
    period_end: date | None = None,
) -> dict[str, object]:
    def qname(value: QName) -> dict[str, str]:
        return {"namespace": value[0], "local_name": value[1]}

    def fact_json(fact: SECFinancialFact) -> dict[str, object]:
        return {
            "source_fact_id": fact.source_fact_id,
            "field": fact.field.value,
            "namespace": fact.namespace,
            "concept": fact.concept,
            "context_id": fact.context_id,
            "period_kind": fact.period_kind.value,
            "period_start": fact.period_start.isoformat()
            if fact.period_start
            else None,
            "period_end": fact.period_end.isoformat(),
            "unit_id": fact.unit_id,
            "unit": {
                "numerator": qname(fact.unit.numerator),
                "denominator": (
                    qname(fact.unit.denominator) if fact.unit.denominator else None
                ),
            },
            "dimensions": [
                {"axis": qname(axis), "member": qname(member)}
                for axis, member in fact.dimensions
            ],
            "signed_decimal_value": (
                str(fact.signed_decimal_value)
                if fact.signed_decimal_value is not None
                else None
            ),
            "decimals": fact.decimals,
            "precision": fact.precision,
            "is_nil": fact.is_nil,
        }

    def in_selection(fact: SECFinancialFact) -> bool:
        if period_end is None:
            return True
        if fact.period_end != period_end:
            return False
        if fact.period_kind is SECFinancialPeriodKind.INSTANT:
            return True
        return period_start is None or fact.period_start == period_start

    def unsupported_in_selection(item: SECUnsupportedObservation) -> bool:
        if period_end is None:
            return True
        if item.fact is not None:
            return in_selection(item.fact)
        if item.period_end != period_end:
            return False
        return (
            item.period_kind is SECFinancialPeriodKind.INSTANT
            or period_start is None
            or item.period_start == period_start
        )

    def unsupported_concept_in_selection(item: SECUnsupportedConcept) -> bool:
        if period_end is None:
            return True
        if item.period_end != period_end:
            return False
        return (
            item.period_kind is SECFinancialPeriodKind.INSTANT
            or period_start is None
            or item.period_start == period_start
        )

    return {
        "schema": "arch152-pm2d-native-financial-statement/v1",
        "source": {
            "sha256": report.source.sha256,
            "length": report.source.length,
            "accession": report.source.accession,
            "document_name": report.source.document_name,
            "issuer_cik": report.source.issuer_cik,
        },
        "selection": {
            "duration_start": (
                period_start.isoformat() if period_start is not None else None
            ),
            "period_end": period_end.isoformat() if period_end is not None else None,
            "instant_facts_at_period_end_included": period_end is not None,
        },
        "fields": [
            {
                "field": result.field.value,
                "status": result.status.value,
                "reason_code": result.reason_code,
                "facts": [
                    fact_json(fact) for fact in result.facts if in_selection(fact)
                ],
                "conflicts": [
                    fact_json(fact) for fact in result.conflicts if in_selection(fact)
                ],
            }
            for result in report.results
        ],
        "unsupported_observations": [
            {
                "field": item.field.value,
                "namespace": item.namespace,
                "concept": item.concept,
                "context_id": item.context_id,
                "source_fact_id": item.source_fact_id,
                "reason_code": item.reason_code,
                "fact": fact_json(item.fact) if item.fact is not None else None,
            }
            for item in report.unsupported_observations
            if unsupported_in_selection(item)
        ],
        "unsupported_concepts": [
            {
                "namespace": item.namespace,
                "concept": item.concept,
                "context_id": item.context_id,
                "source_fact_id": item.source_fact_id,
                "reason_code": item.reason_code,
                "period_kind": (
                    item.period_kind.value if item.period_kind is not None else None
                ),
                "period_start": (
                    item.period_start.isoformat()
                    if item.period_start is not None
                    else None
                ),
                "period_end": (
                    item.period_end.isoformat() if item.period_end is not None else None
                ),
                "unit_id": item.unit_id,
                "unit": (
                    {
                        "numerator": qname(item.unit.numerator),
                        "denominator": (
                            qname(item.unit.denominator)
                            if item.unit.denominator
                            else None
                        ),
                    }
                    if item.unit is not None
                    else None
                ),
                "dimensions": (
                    [
                        {"axis": qname(axis), "member": qname(member)}
                        for axis, member in item.dimensions
                    ]
                    if item.dimensions is not None
                    else None
                ),
                "raw_value_text": item.raw_value_text,
            }
            for item in report.unsupported_concepts
            if unsupported_concept_in_selection(item)
        ],
        "external_effect_counters": {
            "http_requests": 0,
            "taxonomy_resolutions": 0,
            "credential_reads": 0,
            "broker_effects": 0,
            "account_reads": 0,
            "ai_calls": 0,
            "repository_writes": 0,
        },
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Extract mapped facts from one digest-verified native SEC XBRL "
            "instance; reads a local file only and does not contact SEC."
        )
    )
    parser.add_argument("instance", help="absolute local path to existing XML")
    parser.add_argument("--sha256", required=True, help="expected lowercase SHA-256")
    parser.add_argument(
        "--length", required=True, type=int, help="expected byte length"
    )
    parser.add_argument("--accession", required=True, help="reviewed SEC accession")
    parser.add_argument("--document-name", required=True, help="reviewed document name")
    parser.add_argument("--cik", required=True, help="expected 10-digit issuer CIK")
    parser.add_argument(
        "--period-start",
        type=_cli_date,
        help=(
            "optional exact start date for duration facts (instant facts at end remain)"
        ),
    )
    parser.add_argument(
        "--period-end",
        type=_cli_date,
        help="optional exact period end; pair with --period-start for one fiscal year",
    )
    return parser


def _cli_date(value: str) -> date:
    if not _DATE.fullmatch(value):
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("date is invalid") from error


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if (args.period_start is None) != (args.period_end is None):
        parser.error("--period-start and --period-end must be supplied together")
    try:
        report = extract_sec_financial_statement(
            args.instance,
            expected_sha256=args.sha256,
            expected_length=args.length,
            accession=args.accession,
            document_name=args.document_name,
            expected_cik=args.cik,
        )
    except SECFinancialInputError as error:
        print(
            json.dumps({"status": "rejected", "reason_code": error.reason_code}),
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            _report_json(
                report,
                period_start=args.period_start,
                period_end=args.period_end,
            ),
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
