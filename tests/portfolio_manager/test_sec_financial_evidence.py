"""Synthetic tests for the exact SEC-to-PM2C operational bridge."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

import pytest

from trading_bot.domain import Symbol
from trading_bot.portfolio_manager.research_catalog import (
    CatalogEntry,
    EntryKind,
    EvidenceBasis,
    ResearchCatalog,
    ValueKind,
    ValueSpec,
)
from trading_bot.portfolio_manager.research_evidence import (
    AvailabilityStatus,
    EvidenceContractError,
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
    SnapshotAdmissionError,
)
from trading_bot.portfolio_manager.sec_financial_evidence import (
    SECFinancialBridgeError,
    SECIndependentSecurityMapping,
    SECOperationalDocumentQualification,
    admit_sec_operational_snapshot,
    bridge_sec_financial_fact,
    sec_financial_catalog_entries,
    sec_financial_fact_fingerprint,
)
from trading_bot.portfolio_manager.sec_financial_statements import (
    SECFinancialField,
    extract_sec_financial_statement_bytes,
    select_fact,
)
from trading_bot.portfolio_manager.sec_native_observation import (
    SECObservationCounters,
    SECObservationOutcome,
    SECObservationPlan,
    SECObservationResult,
    SECTransportResponse,
    canonical_sec_attempt_id,
    extract_sec_submission_member,
    parse_native_xbrl_revenue,
    parse_sec_submission,
)

CIK = "0000000001"
ACCESSION = "0000000001-23-000001"
DOCUMENT = "synthetic-instance.xml"
NAMESPACE = "http://fasb.org/us-gaap/2018-01-31"
ISO4217 = "http://www.xbrl.org/2003/iso4217"
XBRLI = "http://www.xbrl.org/2003/instance"
START = date(2023, 1, 1)
END = date(2023, 12, 31)
RECEIPT = datetime(2024, 1, 16, 12, tzinfo=UTC)
VERIFY_AT = RECEIPT + timedelta(hours=1)
MAPPING_AT = RECEIPT + timedelta(hours=2)
NOW_CUTOFF = RECEIPT + timedelta(hours=3)


def _plan(*, namespace: str = NAMESPACE) -> SECObservationPlan:
    initial = SECObservationPlan(
        attempt_id=UUID(int=0),
        expected_source_head="0" * 40,
        expected_source_tree="1" * 40,
        issuer_cik=CIK,
        accession=ACCESSION,
        filing_form="10-K",
        document_name=DOCUMENT,
        document_sequence="11",
        fiscal_year=END.year,
        period_start=START,
        period_end=END,
        context_id="FY2023",
        entity_identifier_scheme="http://www.sec.gov/CIK",
        concept_namespace=namespace,
        concept_local_name="RevenueFromContractWithCustomerExcludingAssessedTax",
        unit_id="USD",
        unit_namespace=ISO4217,
        unit_local_name="USD",
        dimensions=(),
        user_agent="synthetic bridge test contact@example.invalid",
        evidence_root=r"F:\AI\temp\pm2d-b1-r-synthetic-tests",
    )
    return replace(initial, attempt_id=canonical_sec_attempt_id(initial))


def _fact(
    concept: str,
    *,
    context: str = "FY2023",
    unit: str = "USD",
    value: str,
    fact_id: str,
    nil: bool = False,
) -> str:
    nil_attr = ' xsi:nil="true"' if nil else ""
    value_text = "" if nil else value
    return (
        f'<us-gaap:{concept} id="{fact_id}" contextRef="{context}" '
        f'unitRef="{unit}" decimals="0"{nil_attr}>{value_text}'
        f"</us-gaap:{concept}>"
    )


def _instance(
    plan: SECObservationPlan,
    *,
    include_instant_contexts: bool = True,
    include_annual_operating_income: bool = True,
    include_segment_operating_income: bool = False,
    include_quarterly_operating_income: bool = False,
    duplicate_operating_income: bool = False,
    nil_operating_income: bool = False,
    invalid_operating_income_unit: bool = False,
    namespace: str = NAMESPACE,
) -> bytes:
    facts: list[str] = [
        _fact(
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            value="1000.125",
            fact_id="fact-revenue-excluding",
        ),
        _fact(
            "RevenueFromContractWithCustomerIncludingAssessedTax",
            value="1110.125",
            fact_id="fact-revenue-including",
        ),
    ]
    if include_annual_operating_income:
        facts.append(
            _fact(
                "OperatingIncomeLoss",
                unit="Shares" if invalid_operating_income_unit else "USD",
                value="100.25",
                fact_id="fact-operating-income",
                nil=nil_operating_income,
            )
        )
    if duplicate_operating_income:
        facts.append(
            _fact(
                "OperatingIncomeLoss",
                value="101.25",
                fact_id="fact-operating-income-conflict",
            )
        )
    if include_segment_operating_income:
        facts.append(
            _fact(
                "OperatingIncomeLoss",
                context="FY2023Segment",
                value="900.00",
                fact_id="fact-operating-income-segment",
            )
        )
    if include_quarterly_operating_income:
        facts.append(
            _fact(
                "OperatingIncomeLoss",
                context="Q4-2023",
                value="25.00",
                fact_id="fact-operating-income-quarter",
            )
        )
    facts.extend(
        (
            _fact("NetIncomeLoss", value="80.00", fact_id="fact-net-income"),
            _fact(
                "EarningsPerShareDiluted",
                unit="USDPerShare",
                value="2.50",
                fact_id="fact-diluted-eps",
            ),
            _fact(
                "NetCashProvidedByUsedInOperatingActivities",
                value="120.00",
                fact_id="fact-operating-cash-flow",
            ),
            _fact(
                "PaymentsToAcquirePropertyPlantAndEquipment",
                value="-40.00",
                fact_id="fact-ppe-payments",
            ),
            _fact(
                "CashAndCashEquivalentsAtCarryingValue",
                context="FY2023Instant",
                value="50.00",
                fact_id="fact-cash",
            ),
            _fact(
                "Assets",
                context="FY2023Instant",
                value="2000.00",
                fact_id="fact-assets",
            ),
            _fact(
                "Liabilities",
                context="FY2023Instant",
                value="900.00",
                fact_id="fact-liabilities",
            ),
            _fact(
                "StockholdersEquity",
                context="FY2023Instant",
                value="1100.00",
                fact_id="fact-equity",
            ),
            _fact(
                "LongTermDebtCurrent",
                context="FY2023Instant",
                value="100.00",
                fact_id="fact-debt-current",
            ),
            _fact(
                "LongTermDebtNoncurrent",
                context="FY2023Instant",
                value="200.00",
                fact_id="fact-debt-noncurrent",
            ),
            _fact(
                "LongTermDebtAndFinanceLeaseObligationsCurrent",
                context="FY2023Instant",
                value="300.00",
                fact_id="fact-debt-lease-current",
            ),
            _fact(
                "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
                context="FY2023Instant",
                value="400.00",
                fact_id="fact-debt-lease-noncurrent",
            ),
        )
    )
    if not include_instant_contexts:
        facts = [
            value
            for value in facts
            if 'contextRef="FY2023Instant"' not in value
            and 'unitRef="USDPerShare"' not in value
        ]
    if include_segment_operating_income:
        segment_context = f"""
  <xbrli:context id="FY2023Segment">
    <xbrli:entity>
      <xbrli:identifier scheme="http://www.sec.gov/CIK">{CIK}</xbrli:identifier>
      <xbrli:segment>
        <xbrldi:explicitMember dimension="us-gaap:ProductOrServiceAxis">
          us-gaap:ProductMember
        </xbrldi:explicitMember>
      </xbrli:segment>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:startDate>{START.isoformat()}</xbrli:startDate>
      <xbrli:endDate>{END.isoformat()}</xbrli:endDate>
    </xbrli:period>
  </xbrli:context>"""
    else:
        segment_context = ""
    if include_quarterly_operating_income:
        quarterly_context = """
  <xbrli:context id="Q4-2023">
    <xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000000001</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2023-10-01</xbrli:startDate><xbrli:endDate>2023-12-31</xbrli:endDate></xbrli:period>
  </xbrli:context>"""
    else:
        quarterly_context = ""
    instant_context = (
        f"""  <xbrli:context id="FY2023Instant">
    <xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">{CIK}</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:instant>{END.isoformat()}</xbrli:instant></xbrli:period>
  </xbrli:context>"""
        if include_instant_contexts
        else ""
    )
    usd_per_share_unit = (
        '<xbrli:unit id="USDPerShare"><xbrli:divide>'
        "<xbrli:unitNumerator><xbrli:measure>iso4217:USD</xbrli:measure>"
        "</xbrli:unitNumerator><xbrli:unitDenominator>"
        "<xbrli:measure>xbrli:shares</xbrli:measure>"
        "</xbrli:unitDenominator></xbrli:divide></xbrli:unit>"
        if include_instant_contexts
        else ""
    )
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl xmlns:xbrli="{XBRLI}" xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:us-gaap="{namespace}"
 xmlns:iso4217="{ISO4217}">
  <xbrli:context id="FY2023">
    <xbrli:entity>
      <xbrli:identifier scheme="http://www.sec.gov/CIK">{CIK}</xbrli:identifier>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:startDate>{START.isoformat()}</xbrli:startDate>
      <xbrli:endDate>{END.isoformat()}</xbrli:endDate>
    </xbrli:period>
  </xbrli:context>
  {instant_context}
  {segment_context}
  {quarterly_context}
  <xbrli:unit id="USD"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
  <xbrli:unit id="Shares"><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unit>
  {usd_per_share_unit}
  {"".join(facts)}
</xbrli:xbrl>
"""
    return xml.encode("ascii")


def _raw_response(plan: SECObservationPlan, **xml_options: object) -> bytes:
    instance = _instance(plan, **xml_options)
    return (
        f"""<SEC-DOCUMENT>{plan.accession}.txt
<TYPE>{plan.filing_form}
<ACCEPTANCE-DATETIME>20240115170000
<SEC-HEADER>
ACCESSION NUMBER: {plan.accession}
CONFORMED SUBMISSION TYPE: {plan.filing_form}
FILED AS OF DATE: 20240115
CONFORMED PERIOD OF REPORT: {plan.period_end:%Y%m%d}
CENTRAL INDEX KEY: {plan.issuer_cik}
</SEC-HEADER>
<DOCUMENT>
<TYPE>EX-101.INS
<SEQUENCE>{plan.document_sequence}
<FILENAME>{plan.document_name}
<TEXT>
{instance.decode("ascii")}
</TEXT>
</DOCUMENT>
</SEC-DOCUMENT>
"""
    ).encode("ascii")


def _ref(label: str) -> str:
    return sha256(f"synthetic-verification-reference:{label}".encode()).hexdigest()


def _prepare(
    field: SECFinancialField,
    *,
    plan_namespace: str = NAMESPACE,
    b1r_shape: str = "instant_context_unsupported",
    **xml_options: object,
) -> tuple[
    bytes,
    SECOperationalDocumentQualification,
    SECIndependentSecurityMapping,
    ResearchCatalog,
]:
    plan = _plan(namespace=plan_namespace)
    if b1r_shape == "revenue_blocked":
        xml_options.setdefault("include_instant_contexts", False)
    response = _raw_response(plan, namespace=plan_namespace, **xml_options)
    submission = parse_sec_submission(response, plan, RECEIPT)
    embedded = extract_sec_submission_member(response, submission)
    transport_response = SECTransportResponse(
        200,
        "text/plain",
        response,
        plan.submission_url,
        RECEIPT,
    )
    response_sha = sha256(response).hexdigest()
    result_kwargs: dict[str, object] = {
        "plan_id": plan.plan_id,
        "source_head": plan.expected_source_head,
        "source_tree": plan.expected_source_tree,
        "counters": SECObservationCounters(
            provider_invocations=1,
            request_intents=1,
            response_documents=1,
            response_bytes=len(response),
            response_bytes_received=len(response),
        ),
        "response_sha256": (response_sha,),
    }
    if b1r_shape == "instant_context_unsupported":
        observation = SECObservationResult(
            outcome=SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED,
            reason_code="XBRL_DURATION_CONTEXT_REQUIRED",
            counters=replace(result_kwargs["counters"], xbrl_records=0),
            **{key: value for key, value in result_kwargs.items() if key != "counters"},
        )
    elif b1r_shape == "revenue_blocked":
        revenue_fact = parse_native_xbrl_revenue(embedded, plan, submission)
        observation = SECObservationResult(
            outcome=SECObservationOutcome.SEC_OBSERVATION_BLOCKED,
            reason_code="SEC_HISTORICAL_VERSION_WITNESS_AND_SECURITY_MAPPING_UNPROVEN",
            counters=replace(result_kwargs["counters"], xbrl_records=1),
            submission=submission,
            fact=revenue_fact,
            **{key: value for key, value in result_kwargs.items() if key != "counters"},
        )
    else:
        raise AssertionError(f"unknown synthetic B1-R shape: {b1r_shape}")
    report = extract_sec_financial_statement_bytes(
        embedded,
        expected_sha256=submission.embedded_document_sha256,
        expected_length=submission.embedded_document_length,
        accession=submission.accession,
        document_name=submission.document_name,
        expected_cik=submission.issuer_cik,
    )
    field_result = select_fact(
        report,
        field,
        period_start=None
        if field.value
        in {
            "cash_and_cash_equivalents",
            "total_assets",
            "total_liabilities",
            "stockholders_equity",
            "long_term_debt_current",
            "long_term_debt_noncurrent",
            "long_term_debt_and_finance_lease_obligations_current",
            "long_term_debt_and_finance_lease_obligations_noncurrent",
        }
        else START,
        period_end=END,
        dimensions=(),
    )
    facts = list(field_result.facts)
    revenue_result = select_fact(
        report,
        SECFinancialField.REVENUE_EXCLUDING_ASSESSED_TAX,
        period_start=START,
        period_end=END,
        dimensions=(),
    )
    facts.extend(revenue_result.facts)
    fingerprints = tuple(
        dict.fromkeys(sec_financial_fact_fingerprint(fact) for fact in facts)
    )
    if not fingerprints:
        fingerprints = (str(UUID(int=42)),)
    qualification = SECOperationalDocumentQualification(
        plan=plan,
        observation=observation,
        response=transport_response,
        request_intent_at=RECEIPT - timedelta(minutes=1),
        verification_completed_at=VERIFY_AT,
        request_intent_reference=_ref("intent"),
        acquisition_record_reference=_ref("acquisition"),
        response_provenance_reference=_ref("response"),
        document_verification_reference=_ref("document"),
        accession_verification_reference=_ref("accession"),
        issuer_verification_reference=_ref("issuer"),
        fact_verification_references=tuple(
            (fingerprint, _ref(f"fact-{index}"))
            for index, fingerprint in enumerate(fingerprints)
        ),
    )
    subject = EvidenceSubject(
        symbol=Symbol("SYN"),
        issuer_id=f"CIK:{CIK}",
        security_id="SYN-CLASS-A",
        share_class="COMMON",
    )
    mapping = SECIndependentSecurityMapping(
        issuer_cik=CIK,
        subject=subject,
        verified_at=MAPPING_AT,
        issuer_reference=_ref("mapped-issuer"),
        security_reference=_ref("mapped-security"),
    )
    catalog_version = "sec-bridge-tests-v1"
    membership_entry = CatalogEntry(
        catalog_version,
        "raw.classification.membership",
        "1",
        "relative",
        EntryKind.RAW,
        value_spec=ValueSpec(ValueKind.IDENTIFIER_VECTOR),
        basis=EvidenceBasis("PIT", data_basis="synthetic_membership"),
    )
    catalog = ResearchCatalog(
        catalog_version,
        (*sec_financial_catalog_entries(catalog_version), membership_entry),
    )
    return response, qualification, mapping, catalog


def _bridge(field: SECFinancialField, **options: object):
    response, qualification, mapping, catalog = _prepare(field, **options)
    is_instant = field.value in {
        "cash_and_cash_equivalents",
        "total_assets",
        "total_liabilities",
        "stockholders_equity",
        "long_term_debt_current",
        "long_term_debt_noncurrent",
        "long_term_debt_and_finance_lease_obligations_current",
        "long_term_debt_and_finance_lease_obligations_noncurrent",
    }
    bridged = bridge_sec_financial_fact(
        response,
        qualification=qualification,
        security_mapping=mapping,
        catalog=catalog,
        field=field,
        period_start=None if is_instant else START,
        period_end=END,
    )
    return response, qualification, mapping, catalog, bridged


def _membership_graph(
    catalog: ResearchCatalog, *, effective_at: datetime
) -> tuple[EvidenceGraph, MembershipBinding]:
    entry = catalog.lookup("raw.classification.membership", "1")
    subject = EvidenceSubject(scope="peer-panel", security_id="synthetic-panel")
    fact = SourceFact(
        entry=entry,
        subject=subject,
        source_identity="SYNTHETIC_MEMBERSHIP",
        source_version="synthetic-membership-v1",
        outcome=EvidenceOutcome(AvailabilityStatus.AVAILABLE, ("SYN",)),
        timeframe=EvidenceTimeframe(EvidenceTimeframeKind.INSTANT, effective_at),
        available_at=effective_at,
        observed_at=effective_at,
        effective_at=effective_at,
        source_record_id="synthetic-membership-record-v1",
        source_content_digest="synthetic-membership-digest-v1",
    )
    membership = MembershipBinding(
        entry=entry,
        subject=subject,
        evidence_id=fact.evidence_id,
        version=fact.source_version,
        effective_at=effective_at,
        members=("SYN",),
    )
    return EvidenceGraph(catalog, (fact,)), membership


def test_assessed_tax_bases_have_separate_raw_usd_definitions_and_values() -> None:
    response, qualification, mapping, catalog, including = _bridge(
        SECFinancialField.REVENUE_INCLUDING_ASSESSED_TAX
    )
    excluding = bridge_sec_financial_fact(
        response,
        qualification=qualification,
        security_mapping=mapping,
        catalog=catalog,
        field=SECFinancialField.REVENUE_EXCLUDING_ASSESSED_TAX,
        period_start=START,
        period_end=END,
    )

    assert including.source_fact.value == Decimal("1110.125")
    assert excluding.source_fact.value == Decimal("1000.125")
    assert including.source_fact.entry.key.endswith("including_assessed_tax")
    assert excluding.source_fact.entry.key.endswith("excluding_assessed_tax")
    assert including.source_fact.entry.entry_id != excluding.source_fact.entry.entry_id
    assert including.source_fact.entry.basis != excluding.source_fact.entry.basis
    assert including.original_fact.concept != excluding.original_fact.concept
    assert (
        including.original_fact.dimensions == excluding.original_fact.dimensions == ()
    )
    assert including.source_fact.unit == excluding.source_fact.unit == "USD"


def test_catalog_keeps_eps_and_basis_names_exact() -> None:
    entries = sec_financial_catalog_entries("catalog-v1")
    by_key = {item.key: item for item in entries}
    assert by_key["raw.fiscal.annual.sec.diluted_eps"].value_spec.unit == "USD/share"
    assert by_key["raw.fiscal.annual.sec.diluted_eps"].value_spec.currency == "USD"
    assert (
        by_key["raw.fiscal.annual.sec.net_income_loss"].basis.reporting_basis
        == "US_GAAP_2018_NET_INCOME_LOSS_NOT_ATTRIBUTABLE_COMMON"
    )
    assert (
        by_key["raw.fiscal.balance_sheet.sec.stockholders_equity"].basis.reporting_basis
        == "US_GAAP_2018_STOCKHOLDERS_EQUITY_NOT_ATTRIBUTABLE_COMMON"
    )
    assert not any("attributable_common" in item.key for item in entries)
    debt_entries = tuple(item for item in entries if "debt" in item.key)
    assert len({item.key for item in debt_entries}) == len(debt_entries)
    assert "raw.fiscal.balance_sheet.sec.total_debt" not in by_key


def test_decimal_values_and_original_source_metadata_survive_the_bridge() -> None:
    _, _, _, _, bridged = _bridge(
        SECFinancialField.CAPITAL_EXPENDITURES_PROPERTY_PLANT_EQUIPMENT
    )
    assert bridged.source_fact.value == Decimal("-40.00")
    assert bridged.original_fact.signed_decimal_value == Decimal("-40.00")
    assert bridged.original_fact.namespace == NAMESPACE
    assert bridged.original_fact.concept == "PaymentsToAcquirePropertyPlantAndEquipment"
    assert bridged.original_fact.context_id == "FY2023"
    assert bridged.original_fact.unit_id == "USD"
    assert bridged.original_fact.decimals == "0"
    assert bridged.original_fact.dimensions == ()
    assert bridged.submission.accession == ACCESSION
    assert bridged.submission.document_name == DOCUMENT
    assert bridged.submission.issuer_cik == CIK
    assert bridged.source_version.startswith(f"SEC_EDGAR:{ACCESSION}:{DOCUMENT}:")
    assert bridged.receipt_at == RECEIPT
    assert bridged.publication_at is None
    assert bridged.source_fact.available_at == RECEIPT
    assert bridged.source_fact.observed_at == MAPPING_AT
    assert (
        bridged.b1r_terminal_outcome
        is SECObservationOutcome.NATIVE_DOCUMENT_UNSUPPORTED
    )
    assert bridged.b1r_terminal_reason == "XBRL_DURATION_CONTEXT_REQUIRED"
    assert bridged.source_fact.effective_at == datetime.combine(END, time.min, UTC)
    assert (
        bridged.source_fact.source_content_digest == bridged.original_fact.source.sha256
    )
    assert re.fullmatch(r"[0-9a-f-]{36}", bridged.source_fact.source_record_id)


def test_eps_preserves_exact_usd_per_share_unit_algebra() -> None:
    _, _, _, _, bridged = _bridge(SECFinancialField.DILUTED_EPS)
    assert bridged.source_fact.value == Decimal("2.50")
    assert bridged.source_fact.unit == "USD/share"
    assert bridged.original_fact.unit.numerator == (ISO4217, "USD")
    assert bridged.original_fact.unit.denominator == (XBRLI, "shares")


def test_consolidated_value_is_selected_without_adding_segment_facts() -> None:
    _, _, _, _, bridged = _bridge(
        SECFinancialField.OPERATING_INCOME,
        include_segment_operating_income=True,
    )
    assert bridged.source_fact.value == Decimal("100.25")
    assert bridged.original_fact.dimensions == ()


def test_segment_only_or_quarterly_facts_cannot_satisfy_annual_consolidated_entry() -> (
    None
):
    with pytest.raises(SECFinancialBridgeError, match="SEC_FINANCIAL_FACT_MISSING"):
        _bridge(
            SECFinancialField.OPERATING_INCOME,
            include_annual_operating_income=False,
            include_segment_operating_income=True,
        )

    with pytest.raises(
        SECFinancialBridgeError, match="APPROVED_FILING_PERIOD_REQUIRED"
    ):
        response, qualification, mapping, catalog = _prepare(
            SECFinancialField.OPERATING_INCOME,
            include_annual_operating_income=False,
            include_quarterly_operating_income=True,
        )
        bridge_sec_financial_fact(
            response,
            qualification=qualification,
            security_mapping=mapping,
            catalog=catalog,
            field=SECFinancialField.OPERATING_INCOME,
            period_start=date(2023, 10, 1),
            period_end=END,
        )


@pytest.mark.parametrize(
    "options,reason",
    [
        ({"nil_operating_income": True}, "SEC_FINANCIAL_FACT_UNAVAILABLE"),
        ({"invalid_operating_income_unit": True}, "SEC_FINANCIAL_FACT_UNAVAILABLE"),
        ({"duplicate_operating_income": True}, "SEC_FINANCIAL_FACT_AMBIGUOUS"),
    ],
)
def test_unavailable_wrong_unit_and_conflicting_facts_fail_closed(
    options, reason
) -> None:
    with pytest.raises(SECFinancialBridgeError, match=reason):
        _bridge(SECFinancialField.OPERATING_INCOME, **options)


def test_namespace_change_is_unavailable_instead_of_aliased() -> None:
    with pytest.raises(
        SECFinancialBridgeError, match="EXACT_B1R_REVENUE_PLAN_REQUIRED"
    ):
        _bridge(
            SECFinancialField.OPERATING_INCOME,
            plan_namespace="http://fasb.org/us-gaap/2024",
        )


def test_response_and_exact_fact_verification_references_are_required() -> None:
    response, qualification, mapping, catalog = _prepare(
        SECFinancialField.OPERATING_INCOME
    )
    changed_response = response + b" "
    with pytest.raises(SECFinancialBridgeError, match="B1R_RESPONSE_BODY_MISMATCH"):
        bridge_sec_financial_fact(
            changed_response,
            qualification=qualification,
            security_mapping=mapping,
            catalog=catalog,
            field=SECFinancialField.OPERATING_INCOME,
            period_start=START,
            period_end=END,
        )
    with pytest.raises(
        SECFinancialBridgeError, match="INDEPENDENT_EXACT_FACT_VERIFICATION_REQUIRED"
    ):
        selected_fingerprint = qualification.fact_verification_references[0][0]
        no_fact_ref = replace(
            qualification,
            fact_verification_references=tuple(
                (fingerprint, reference)
                for fingerprint, reference in qualification.fact_verification_references
                if fingerprint != selected_fingerprint
            ),
        )
        bridge_sec_financial_fact(
            response,
            qualification=no_fact_ref,
            security_mapping=mapping,
            catalog=catalog,
            field=SECFinancialField.OPERATING_INCOME,
            period_start=START,
            period_end=END,
        )


def test_b1r_revenue_validated_blocked_terminal_shape_is_also_supported() -> None:
    response, qualification, mapping, catalog = _prepare(
        SECFinancialField.REVENUE_EXCLUDING_ASSESSED_TAX,
        b1r_shape="revenue_blocked",
    )
    bridged = bridge_sec_financial_fact(
        response,
        qualification=qualification,
        security_mapping=mapping,
        catalog=catalog,
        field=SECFinancialField.REVENUE_EXCLUDING_ASSESSED_TAX,
        period_start=START,
        period_end=END,
    )
    assert bridged.b1r_terminal_outcome is SECObservationOutcome.SEC_OBSERVATION_BLOCKED
    assert bridged.b1r_terminal_reason == (
        "SEC_HISTORICAL_VERSION_WITNESS_AND_SECURITY_MAPPING_UNPROVEN"
    )


def test_other_b1r_terminal_reason_and_counter_mismatch_are_rejected() -> None:
    response, qualification, mapping, catalog = _prepare(
        SECFinancialField.OPERATING_INCOME
    )
    wrong_reason = replace(
        qualification,
        observation=replace(qualification.observation, reason_code="OTHER_FAILURE"),
    )
    with pytest.raises(
        SECFinancialBridgeError, match="B1R_TYPED_TERMINAL_QUALIFICATION_REQUIRED"
    ):
        bridge_sec_financial_fact(
            response,
            qualification=wrong_reason,
            security_mapping=mapping,
            catalog=catalog,
            field=SECFinancialField.OPERATING_INCOME,
            period_start=START,
            period_end=END,
        )
    bad_counts = replace(
        qualification,
        observation=replace(
            qualification.observation,
            counters=replace(
                qualification.observation.counters, provider_invocations=2
            ),
        ),
    )
    with pytest.raises(
        SECFinancialBridgeError, match="B1R_RESPONSE_OR_EFFECT_COUNTER_MISMATCH"
    ):
        bridge_sec_financial_fact(
            response,
            qualification=bad_counts,
            security_mapping=mapping,
            catalog=catalog,
            field=SECFinancialField.OPERATING_INCOME,
            period_start=START,
            period_end=END,
        )


def test_receipt_chronology_and_mapping_identity_are_independently_checked() -> None:
    response, qualification, mapping, catalog = _prepare(
        SECFinancialField.OPERATING_INCOME
    )
    late_intent = replace(
        qualification, request_intent_at=RECEIPT + timedelta(seconds=1)
    )
    with pytest.raises(
        SECFinancialBridgeError, match="RECEIPT_CHRONOLOGY_INCONSISTENT"
    ):
        bridge_sec_financial_fact(
            response,
            qualification=late_intent,
            security_mapping=mapping,
            catalog=catalog,
            field=SECFinancialField.OPERATING_INCOME,
            period_start=START,
            period_end=END,
        )
    wrong_cik = replace(
        mapping,
        issuer_cik="0000000002",
        subject=EvidenceSubject(
            symbol=Symbol("SYN"),
            issuer_id="CIK:0000000002",
            security_id="SYN-CLASS-A",
            share_class="COMMON",
        ),
    )
    with pytest.raises(
        SECFinancialBridgeError, match="ISSUER_SECURITY_MAPPING_CIK_MISMATCH"
    ):
        bridge_sec_financial_fact(
            response,
            qualification=qualification,
            security_mapping=wrong_cik,
            catalog=catalog,
            field=SECFinancialField.OPERATING_INCOME,
            period_start=START,
            period_end=END,
        )


def test_discovery_hash_alone_cannot_enter_the_bridge() -> None:
    response, _, mapping, catalog = _prepare(SECFinancialField.OPERATING_INCOME)
    with pytest.raises(
        TypeError, match="qualification must be the exact typed qualification"
    ):
        bridge_sec_financial_fact(
            response,
            qualification=sha256(response).hexdigest(),  # type: ignore[arg-type]
            security_mapping=mapping,
            catalog=catalog,
            field=SECFinancialField.OPERATING_INCOME,
            period_start=START,
            period_end=END,
        )


def test_pm2c_operational_snapshot_enforces_cutoff_and_membership() -> None:
    response, qualification, mapping, catalog = _prepare(SECFinancialField.TOTAL_ASSETS)
    graph, membership = _membership_graph(
        catalog, effective_at=RECEIPT - timedelta(days=1)
    )
    snapshot = admit_sec_operational_snapshot(
        response,
        qualification=qualification,
        security_mapping=mapping,
        field=SECFinancialField.TOTAL_ASSETS,
        period_start=None,
        period_end=END,
        graph=graph,
        membership=membership,
        universe=("SYN",),
        decision_cutoff=NOW_CUTOFF,
    )
    slot = snapshot.slot("raw.fiscal.balance_sheet.sec.assets", mapping.subject)
    assert slot is not None
    assert slot.status is AvailabilityStatus.AVAILABLE
    assert slot.value == Decimal("2000.00")
    assert snapshot.mode is SnapshotMode.OPERATIONAL
    assert snapshot.membership == membership

    with pytest.raises(
        SnapshotAdmissionError, match="operational source receipt is after cutoff"
    ):
        admit_sec_operational_snapshot(
            response,
            qualification=qualification,
            security_mapping=mapping,
            field=SECFinancialField.TOTAL_ASSETS,
            period_start=None,
            period_end=END,
            graph=graph,
            membership=membership,
            universe=("SYN",),
            decision_cutoff=RECEIPT + timedelta(minutes=30),
        )

    wrong_membership = replace(membership, members=("OTHER",))
    with pytest.raises(SnapshotAdmissionError, match="ordered universe must equal"):
        admit_sec_operational_snapshot(
            response,
            qualification=qualification,
            security_mapping=mapping,
            field=SECFinancialField.TOTAL_ASSETS,
            period_start=None,
            period_end=END,
            graph=graph,
            membership=wrong_membership,
            universe=("SYN",),
            decision_cutoff=NOW_CUTOFF,
        )


def test_bridge_mints_no_historical_witness_or_route() -> None:
    _, _, _, _, bridged = _bridge(SECFinancialField.OPERATING_CASH_FLOW)
    with pytest.raises(
        EvidenceContractError, match="historical fact lacks exact version witness"
    ):
        bridged.source_fact.validate_cutoff(
            NOW_CUTOFF,
            SnapshotMode.HISTORICAL_RECONSTRUCTION,
        )
    assert not hasattr(bridged, "as_of_witness")
