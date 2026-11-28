from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from trading_bot.domain import Symbol
from trading_bot.portfolio_manager.research_catalog import (
    AdjustmentBasis,
    CatalogEntry,
    EntryKind,
    EvidenceBasis,
    PeriodSpec,
    ResearchCatalog,
    ScopeSpec,
    ValueKind,
    ValueSpec,
)
from trading_bot.portfolio_manager.research_evidence import EvidenceSubject
from trading_bot.portfolio_manager.sec_sharadar_qualification import (
    ANNUAL_REVENUE_MAPPING,
    DIRECT_Q1_REVENUE_MAPPING,
    PeriodRole,
    QualificationInputError,
    QualificationOutcome,
    QualificationPlan,
    SecAvailabilityProof,
    SecDocumentBinding,
    SecProvenanceWitness,
    SharadarAvailabilityProof,
    SharadarProvenanceWitness,
    XbrlDimension,
    compare_candidate,
    parse_sec_response,
    parse_sharadar_page,
    quarterization_outcome,
)

OBSERVED = datetime(2025, 3, 1, 12, tzinfo=UTC)
SEC_AVAILABLE = datetime(2025, 2, 15, 18, tzinfo=UTC)
SF1_AVAILABLE = datetime(2025, 2, 16, 9, tzinfo=UTC)
VISIBLE_UNTIL = datetime(2025, 4, 1, tzinfo=UTC)
CIK = "0000000001"
PRIMARY = "0000000001-24-000001"
AMENDMENT = "0000000001-24-000002"
EARLY_8K = "0000000001-24-000003"
TICKER = "TEST"
PERMA = "TEST-PERM"
CONCEPT = "RevenueFromContractWithCustomerExcludingAssessedTax"
RAW_SHA = "a" * 40
TREE_SHA = "b" * 40


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _plan(
    *,
    role: PeriodRole = PeriodRole.ANNUAL,
    cutoff: datetime = OBSERVED,
    amendment: bool = False,
    early_8k: bool = False,
    max_pages: int = 1,
    evidence_root: str = r"F:\AI\temp\pm2d-b1-tests",
    dimensions: tuple[XbrlDimension, ...] = (),
) -> QualificationPlan:
    mapping = (
        ANNUAL_REVENUE_MAPPING
        if role is PeriodRole.ANNUAL
        else DIRECT_Q1_REVENUE_MAPPING
    )
    if role is PeriodRole.ANNUAL:
        period_start = date(2024, 1, 1)
        period_end = date(2024, 12, 31)
        period_spec = PeriodSpec("annual_fiscal", "completed", "period_end")
    else:
        period_start = date(2024, 1, 1)
        period_end = date(2024, 3, 31)
        period_spec = PeriodSpec("direct_q1", "discrete", "period_end")
    basis = EvidenceBasis(
        calendar="FISCAL",
        adjustment=AdjustmentBasis.UNADJUSTED,
        data_basis="SF1_AS_REPORTED",
        reporting_basis="AS_REPORTED",
    )
    scope = ScopeSpec("security", "ticker")
    entry = CatalogEntry(
        catalog_version="synthetic-v1",
        key=mapping.pm2c_raw_key,
        version="1",
        family="fiscal",
        kind=EntryKind.RAW,
        value_spec=ValueSpec(ValueKind.DECIMAL, mapping.pm2c_unit, mapping.currency),
        scope=scope,
        period_basis=period_spec,
        basis=basis,
    )
    catalog = ResearchCatalog("synthetic-v1", (entry,))
    amendments = ((AMENDMENT, "amendment.xml"),) if amendment else ()
    earlier = ((EARLY_8K, "earnings.xml"),) if early_8k else ()
    bindings = ((PRIMARY, "primary.xml"),) + amendments + earlier
    return QualificationPlan(
        attempt_id="synthetic-attempt-1",
        expected_source_head=RAW_SHA,
        expected_source_tree=TREE_SHA,
        issuer_cik=CIK,
        primary_accession=PRIMARY,
        sec_document_bindings=tuple(
            SecDocumentBinding(accession, document_name)
            for accession, document_name in bindings
        ),
        sf1_table="SHARADAR/SF1",
        sf1_dimension=mapping.sf1_dimension,
        ticker=TICKER,
        perma_ticker=PERMA,
        sf1_field=mapping.sf1_field,
        field_mapping=mapping,
        catalog=catalog,
        target_entry=entry,
        target_subject=EvidenceSubject(
            symbol=Symbol(TICKER),
            issuer_id=CIK,
            security_id=PERMA,
            share_class=None,
        ),
        expected_raw_basis=basis,
        expected_raw_scope=scope,
        expected_raw_period=period_spec,
        share_class=None,
        context_id="FY2024",
        period_role=role,
        period_start=period_start,
        period_end=period_end,
        fiscal_year=2024,
        dimensions=dimensions,
        provider_unit="USD",
        currency="USD",
        sec_scale=6,
        availability_cutoff=cutoff,
        evidence_root=evidence_root,
        max_sec_response_bytes=200_000,
        max_sharadar_page_bytes=100_000,
        max_sec_documents=len(bindings),
        max_sec_facts=20,
        max_sharadar_pages=max_pages,
        max_sharadar_rows=100,
        max_provider_attempts=len(bindings) + max_pages,
        amendment_accession=AMENDMENT if amendment else None,
        amendment_form="10-K/A" if amendment else None,
        early_8k_accession=EARLY_8K if early_8k else None,
        early_8k_form="8-K" if early_8k else None,
        primary_form="10-K" if role is PeriodRole.ANNUAL else "10-Q",
    )


def _sec_payload(
    plan: QualificationPlan,
    *,
    accession: str = PRIMARY,
    document_name: str = "primary.xml",
    value: str = "123.45",
    issuer_cik: str = CIK,
    concept: str = CONCEPT,
    context_id: str = "FY2024",
    context_cik: str = CIK,
    period_start: date | None = None,
    period_end: date | None = None,
    dimensions: tuple[XbrlDimension, ...] | None = None,
    unit: str = "USD",
    currency: str = "USD",
    scale: int = 6,
    record_id: str = "sec-fact-record-17",
) -> dict[str, object]:
    return {
        "issuer_cik": issuer_cik,
        "accession": accession,
        "form": (
            "10-K"
            if accession == PRIMARY and plan.period_role is PeriodRole.ANNUAL
            else "10-Q"
            if accession == PRIMARY
            else "10-K/A"
            if accession == AMENDMENT
            else "8-K"
        ),
        "accepted_at": "2025-02-15T17:55:00Z",
        "filing_date": "2025-02-15",
        "report_period": plan.period_end.isoformat(),
        "document_name": document_name,
        "facts": [
            {
                "concept": concept,
                "context_id": context_id,
                "context_cik": context_cik,
                "period_start": (period_start or plan.period_start).isoformat(),
                "period_end": (period_end or plan.period_end).isoformat(),
                "dimensions": [
                    {"axis": item.axis, "member": item.member}
                    for item in (plan.dimensions if dimensions is None else dimensions)
                ],
                "unit": unit,
                "currency": currency,
                "scale": scale,
                "decimals": "-6",
                "value": value,
                "record_id": record_id,
            }
        ],
    }


def _sf1_payload(
    plan: QualificationPlan,
    *,
    dimension: str | None = None,
    ticker: str = TICKER,
    perma_ticker: str = PERMA,
    report_period: date | None = None,
    calendar_date: date | None = None,
    datekey: date | None = date(2025, 2, 15),
    lastupdated: date | None = date(2025, 2, 17),
    field_present: bool = True,
    value: int | str | None = 123_450_000,
    next_cursor: str | None = None,
    row_id: str | None = "sf1-row-record-8",
    extra_rows: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "ticker": ticker,
        "permaTicker": perma_ticker,
        "reportperiod": (report_period or plan.period_end).isoformat(),
        "calendardate": (calendar_date or plan.period_end).isoformat(),
        "datekey": None if datekey is None else datekey.isoformat(),
        "lastupdated": None if lastupdated is None else lastupdated.isoformat(),
        "fields": {},
    }
    if row_id is not None:
        row["row_id"] = row_id
    if field_present:
        row["fields"] = {plan.sf1_field: value}
    rows = [row]
    if extra_rows:
        rows.extend(extra_rows)
    result: dict[str, object] = {
        "table": "SHARADAR/SF1",
        "dimension": dimension or plan.sf1_dimension,
        "rows": rows,
    }
    if next_cursor is not None:
        result["next_cursor"] = next_cursor
    return result


def _case(
    *,
    plan: QualificationPlan | None = None,
    sec_data: dict[str, object] | None = None,
    sf1_data: dict[str, object] | None = None,
    sec_available: datetime = SEC_AVAILABLE,
    sf1_available: datetime = SF1_AVAILABLE,
    sf1_version: str = "vendor-version:fixture-01",
    sec_proof_reference: str = "sec-public-proof-01",
    sf1_proof_reference: str = "sf1-version-proof-01",
) -> tuple[
    QualificationPlan, object, object, SecProvenanceWitness, SharadarProvenanceWitness
]:
    plan = plan or _plan()
    sec_data = sec_data or _sec_payload(plan)
    sf1_data = sf1_data or _sf1_payload(plan)
    sec_response = parse_sec_response(_json_bytes(sec_data), plan, OBSERVED)
    sf1_page = parse_sharadar_page(_json_bytes(sf1_data), plan, OBSERVED)
    sec_fact = sec_response.facts[0]
    row = sf1_page.rows[0]
    sec_witness = SecProvenanceWitness(
        record_locator=sec_fact.locator,
        response_sha256=sec_response.content_sha256,
        source_version=f"sec:{sec_response.accession}:{sec_response.content_sha256}",
        public_available_from=sec_available,
        visible_until=VISIBLE_UNTIL,
        proof_reference=sec_proof_reference,
        source_record_id=sec_fact.source_record_id,
        proof_basis=SecAvailabilityProof.PUBLIC_ARCHIVE_WITNESS,
    )
    sf1_witness = SharadarProvenanceWitness(
        record_locator=row.locator,
        response_sha256=sf1_page.content_sha256,
        source_version=sf1_version,
        vendor_available_from=sf1_available,
        visible_until=VISIBLE_UNTIL,
        proof_reference=sf1_proof_reference,
        sec_accession=sec_response.accession,
        sec_record_locator=sec_fact.locator,
        sec_response_sha256=sec_response.content_sha256,
        pm2c_raw_key=plan.target_entry.key,
        sf1_field=plan.sf1_field,
        sec_concept=plan.field_mapping.sec_concept,
        unit=plan.provider_unit,
        currency=plan.currency,
        period_role=plan.period_role,
        period_start=plan.period_start,
        period_end=plan.period_end,
        fiscal_year=plan.fiscal_year,
        source_record_id=row.source_record_id,
        proof_basis=SharadarAvailabilityProof.IMMUTABLE_VERSION_WITNESS,
    )
    return plan, sec_response, sf1_page, sec_witness, sf1_witness


def _compare(
    case: tuple[
        QualificationPlan,
        object,
        object,
        SecProvenanceWitness,
        SharadarProvenanceWitness,
    ],
):
    plan, sec, sf1, sec_witness, sf1_witness = case
    return compare_candidate(
        plan,
        (sec,),
        (sf1,),
        (sec_witness,),
        (sf1_witness,),
        OBSERVED,
    )


def test_exact_fake_match_builds_only_synthetic_pm2c_candidate() -> None:
    case = _case()
    result = _compare(case)
    assert result.outcome is QualificationOutcome.QUALIFIED_CANDIDATE
    source_fact = result.to_source_fact()
    assert source_fact.value == Decimal("123450000")
    assert source_fact.source_identity.startswith("synthetic:")
    assert source_fact.as_of_witness is not None
    assert source_fact.as_of_witness.proves(source_fact, case[0].availability_cutoff)


def test_direct_q1_comparison_requires_exact_independent_grain_witness() -> None:
    plan = _plan(role=PeriodRole.DIRECT_Q1)
    case = _case(plan=plan)
    result = _compare(case)
    assert result.outcome is QualificationOutcome.QUALIFIED_CANDIDATE

    plan, sec, sf1, sec_witness, _ = case
    without_witness = compare_candidate(
        plan, (sec,), (sf1,), (sec_witness,), (), OBSERVED
    )
    assert without_witness.outcome is QualificationOutcome.SOURCE_VERSION_UNPROVEN


@pytest.mark.parametrize(
    "witness_changes",
    [
        {"period_role": PeriodRole.ANNUAL},
        {"period_start": date(2024, 1, 2)},
        {"period_end": date(2024, 3, 30)},
    ],
)
def test_direct_q1_rejects_incompatible_witness_grain_or_period(
    witness_changes: dict[str, object],
) -> None:
    plan, sec, sf1, sec_witness, sf1_witness = _case(
        plan=_plan(role=PeriodRole.DIRECT_Q1)
    )
    incompatible = replace(sf1_witness, **witness_changes)
    result = compare_candidate(
        plan, (sec,), (sf1,), (sec_witness,), (incompatible,), OBSERVED
    )
    assert result.outcome is QualificationOutcome.SHARADAR_FIELD_UNSUPPORTED


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("accession", "0000000001-24-000099"),
        ("issuer_cik", "0000000002"),
    ],
)
def test_wrong_sec_accession_or_issuer_fails_closed(field: str, value: str) -> None:
    plan = _plan()
    payload = _sec_payload(plan)
    payload[field] = value
    assert (
        _compare(_case(plan=plan, sec_data=payload)).outcome
        is QualificationOutcome.SOURCE_FACT_MISMATCH
    )


def test_wrong_period_and_wrong_security_mapping_fail_closed() -> None:
    plan = _plan()
    wrong_period = _sf1_payload(plan, report_period=date(2023, 12, 31))
    assert (
        _compare(_case(plan=plan, sf1_data=wrong_period)).outcome
        is QualificationOutcome.SOURCE_FACT_MISMATCH
    )
    wrong_perma = _sf1_payload(plan, perma_ticker="REUSED-SYMBOL")
    assert (
        _compare(_case(plan=plan, sf1_data=wrong_perma)).outcome
        is QualificationOutcome.SOURCE_FACT_MISMATCH
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [("unit", "EUR"), ("currency", "EUR"), ("scale", 0)],
)
def test_unit_currency_or_scale_mismatch_fails_closed(
    field: str, value: object
) -> None:
    plan = _plan()
    payload = _sec_payload(plan)
    payload["facts"][0][field] = value  # type: ignore[index]
    assert (
        _compare(_case(plan=plan, sec_data=payload)).outcome
        is QualificationOutcome.SOURCE_FACT_MISMATCH
    )


@pytest.mark.parametrize("value", [123_450_001, -123_450_000])
def test_signed_value_mismatch_does_not_normalize_sign_or_round(value: int) -> None:
    plan = _plan()
    assert (
        _compare(_case(plan=plan, sf1_data=_sf1_payload(plan, value=value))).outcome
        is QualificationOutcome.SOURCE_FACT_MISMATCH
    )


@pytest.mark.parametrize("dimension", ["ART", "MRQ", "MRY", "MRT"])
def test_art_and_most_recent_dimensions_are_rejected(dimension: str) -> None:
    plan = _plan()
    result = _compare(
        _case(plan=plan, sf1_data=_sf1_payload(plan, dimension=dimension))
    )
    assert result.outcome is QualificationOutcome.SHARADAR_FIELD_UNSUPPORTED


def test_q2_q3_and_q4_have_explicit_unsupported_quarterization_outcome() -> None:
    assert (
        quarterization_outcome(PeriodRole.YTD_Q2)
        is QualificationOutcome.UNSUPPORTED_QUARTERIZATION
    )
    assert (
        quarterization_outcome(PeriodRole.YTD_Q3)
        is QualificationOutcome.UNSUPPORTED_QUARTERIZATION
    )
    assert (
        quarterization_outcome(PeriodRole.ANNUAL_MINUS_Q3_YTD_Q4)
        is QualificationOutcome.UNSUPPORTED_QUARTERIZATION
    )
    assert quarterization_outcome(PeriodRole.DIRECT_Q1) is None
    assert quarterization_outcome(PeriodRole.ANNUAL) is None


@pytest.mark.parametrize("source_version", ["2025-02-15", "2025-02-17"])
def test_datekey_and_lastupdated_are_not_immutable_version_witnesses(
    source_version: str,
) -> None:
    case = _case(sf1_version=source_version)
    assert _compare(case).outcome is QualificationOutcome.SOURCE_VERSION_UNPROVEN


def test_datekey_filing_date_and_acceptance_do_not_replace_witnesses() -> None:
    plan, sec, sf1, _, sf1_witness = _case()
    result = compare_candidate(plan, (sec,), (sf1,), (), (sf1_witness,), OBSERVED)
    assert result.outcome is QualificationOutcome.SOURCE_VERSION_UNPROVEN
    assert sec.accepted_at == datetime(2025, 2, 15, 17, 55, tzinfo=UTC)
    assert sec.filing_date == date(2025, 2, 15)
    assert sf1.rows[0].datekey == date(2025, 2, 15)


def test_sec_period_end_is_not_public_availability() -> None:
    case = _case(sec_available=datetime(2024, 12, 31, tzinfo=UTC))
    assert _compare(case).outcome is QualificationOutcome.SOURCE_AVAILABILITY_UNPROVEN


def test_vendor_version_availability_after_cutoff_is_not_inherited_from_sec() -> None:
    cutoff = datetime(2025, 2, 20, tzinfo=UTC)
    plan = _plan(cutoff=cutoff)
    case = _case(
        plan=plan,
        sf1_available=datetime(2025, 2, 21, tzinfo=UTC),
    )
    assert _compare(case).outcome is QualificationOutcome.SOURCE_AVAILABILITY_UNPROVEN


def test_true_zero_is_available_and_null_or_missing_is_not_zero() -> None:
    plan = _plan()
    sec_zero = _sec_payload(plan, value="0")
    sf1_zero = _sf1_payload(plan, value=0)
    zero_case = _case(plan=plan, sec_data=sec_zero, sf1_data=sf1_zero)
    assert _compare(zero_case).outcome is QualificationOutcome.QUALIFIED_CANDIDATE
    null_case = _case(
        plan=plan, sec_data=sec_zero, sf1_data=_sf1_payload(plan, value=None)
    )
    assert (
        _compare(null_case).outcome is QualificationOutcome.SHARADAR_FIELD_UNSUPPORTED
    )
    missing_case = _case(
        plan=plan, sec_data=sec_zero, sf1_data=_sf1_payload(plan, field_present=False)
    )
    assert (
        _compare(missing_case).outcome
        is QualificationOutcome.SHARADAR_FIELD_UNSUPPORTED
    )
    assert null_case[2].rows[0].field_present is True
    assert null_case[2].rows[0].value is None
    assert missing_case[2].rows[0].field_present is False


def test_custom_dimension_context_mismatch_is_unsupported() -> None:
    dimension = XbrlDimension("ProductAxis", "WidgetMember")
    plan = _plan(dimensions=(dimension,))
    payload = _sec_payload(plan, dimensions=())
    assert (
        _compare(_case(plan=plan, sec_data=payload)).outcome
        is QualificationOutcome.SEC_CONTEXT_UNSUPPORTED
    )


def test_duplicate_conflicting_sec_facts_and_sf1_rows_fail_closed() -> None:
    plan = _plan()
    sec_data = _sec_payload(plan)
    sec_data["facts"].append(dict(sec_data["facts"][0]))  # type: ignore[union-attr,index]
    assert (
        _compare(_case(plan=plan, sec_data=sec_data)).outcome
        is QualificationOutcome.CONFLICTED
    )
    sf1_data = _sf1_payload(plan, extra_rows=[_sf1_payload(plan)["rows"][0]])
    assert (
        _compare(_case(plan=plan, sf1_data=sf1_data)).outcome
        is QualificationOutcome.CONFLICTED
    )


def test_exact_zero_result_is_not_created_from_an_incomplete_page_chain() -> None:
    plan = _plan(max_pages=1)
    case = _case(plan=plan, sf1_data=_sf1_payload(plan, next_cursor="cursor-next"))
    assert _compare(case).outcome is QualificationOutcome.PAGE_LIMIT_REACHED


def test_cursor_chain_must_be_contiguous_and_terminal() -> None:
    plan = _plan(max_pages=2)
    first_data = _sf1_payload(plan, ticker="OTHER", next_cursor="cursor-2")
    sec_data = _sec_payload(plan)
    sec = parse_sec_response(_json_bytes(sec_data), plan, OBSERVED)
    page_1 = parse_sharadar_page(_json_bytes(first_data), plan, OBSERVED)
    second_data = _sf1_payload(plan)
    page_2 = parse_sharadar_page(_json_bytes(second_data), plan, OBSERVED, "cursor-2")
    row = page_2.rows[0]
    sec_fact = sec.facts[0]
    sec_witness = SecProvenanceWitness(
        sec_fact.locator,
        sec.content_sha256,
        f"sec:{sec.accession}:{sec.content_sha256}",
        SEC_AVAILABLE,
        VISIBLE_UNTIL,
        "sec-proof-cursor",
        sec_fact.source_record_id,
    )
    sf1_witness = SharadarProvenanceWitness(
        record_locator=row.locator,
        response_sha256=page_2.content_sha256,
        source_version="vendor-version:cursor-2",
        vendor_available_from=SF1_AVAILABLE,
        visible_until=VISIBLE_UNTIL,
        proof_reference="sf1-proof-cursor",
        sec_accession=sec.accession,
        sec_record_locator=sec_fact.locator,
        sec_response_sha256=sec.content_sha256,
        pm2c_raw_key=plan.target_entry.key,
        sf1_field=plan.sf1_field,
        sec_concept=plan.field_mapping.sec_concept,
        unit=plan.provider_unit,
        currency=plan.currency,
        period_role=plan.period_role,
        period_start=plan.period_start,
        period_end=plan.period_end,
        fiscal_year=plan.fiscal_year,
        source_record_id=row.source_record_id,
    )
    assert (
        compare_candidate(
            plan, (sec,), (page_1, page_2), (sec_witness,), (sf1_witness,), OBSERVED
        ).outcome
        is QualificationOutcome.QUALIFIED_CANDIDATE
    )

    disconnected = replace(page_2, requested_cursor="different-cursor")
    assert (
        compare_candidate(
            plan,
            (sec,),
            (page_1, disconnected),
            (sec_witness,),
            (sf1_witness,),
            OBSERVED,
        ).outcome
        is QualificationOutcome.PROVIDER_FAILURE
    )


def test_amendment_is_append_only_and_never_replaces_original_value() -> None:
    plan = _plan(amendment=True)
    case = _case(plan=plan)
    _, original, sf1, original_witness, sf1_witness = case
    amendment_data = _sec_payload(
        plan,
        accession=AMENDMENT,
        document_name="amendment.xml",
        value="200.00",
        record_id="sec-amendment-record-18",
    )
    amendment = parse_sec_response(_json_bytes(amendment_data), plan, OBSERVED)
    amendment_fact = amendment.facts[0]
    amendment_witness = SecProvenanceWitness(
        record_locator=amendment_fact.locator,
        response_sha256=amendment.content_sha256,
        source_version=f"sec:{amendment.accession}:{amendment.content_sha256}",
        public_available_from=datetime(2025, 2, 20, tzinfo=UTC),
        visible_until=VISIBLE_UNTIL,
        proof_reference="sec-amendment-proof",
        source_record_id=amendment_fact.source_record_id,
    )
    result = compare_candidate(
        plan,
        (original, amendment),
        (sf1,),
        (original_witness, amendment_witness),
        (sf1_witness,),
        OBSERVED,
    )
    assert result.outcome is QualificationOutcome.QUALIFIED_CANDIDATE
    assert result.selected_sec_fact is original.facts[0]
    assert result.to_source_fact().value == Decimal("123450000")


def test_early_8k_requires_exact_lineage_and_cannot_backdate_sf1_availability() -> None:
    cutoff = datetime(2025, 2, 25, tzinfo=UTC)
    plan = _plan(cutoff=cutoff, early_8k=True)
    _, original, sf1, original_witness, sf1_witness = _case(
        plan=plan,
        sf1_available=datetime(2025, 2, 10, tzinfo=UTC),
    )
    early_data = _sec_payload(
        plan,
        accession=EARLY_8K,
        document_name="earnings.xml",
        value="123.45",
        record_id="sec-8k-record-19",
    )
    early = parse_sec_response(_json_bytes(early_data), plan, OBSERVED)
    early_fact = early.facts[0]
    early_witness = SecProvenanceWitness(
        record_locator=early_fact.locator,
        response_sha256=early.content_sha256,
        source_version=f"sec:{early.accession}:{early.content_sha256}",
        public_available_from=datetime(2025, 2, 1, tzinfo=UTC),
        visible_until=VISIBLE_UNTIL,
        proof_reference="sec-8k-proof",
        source_record_id=early_fact.source_record_id,
    )
    result = compare_candidate(
        plan,
        (original, early),
        (sf1,),
        (original_witness, early_witness),
        (sf1_witness,),
        OBSERVED,
    )
    assert result.outcome is QualificationOutcome.QUALIFIED_CANDIDATE
    assert result.available_at == SEC_AVAILABLE
    assert result.available_at > early_witness.public_available_from

    mismatched_early = parse_sec_response(
        _json_bytes(
            _sec_payload(
                plan, accession=EARLY_8K, document_name="earnings.xml", value="124.00"
            )
        ),
        plan,
        OBSERVED,
    )
    mismatched_fact = mismatched_early.facts[0]
    mismatched_witness = replace(
        early_witness,
        record_locator=mismatched_fact.locator,
        response_sha256=mismatched_early.content_sha256,
        source_version=f"sec:{mismatched_early.accession}:{mismatched_early.content_sha256}",
    )
    assert (
        compare_candidate(
            plan,
            (original, mismatched_early),
            (sf1,),
            (original_witness, mismatched_witness),
            (sf1_witness,),
            OBSERVED,
        ).outcome
        is QualificationOutcome.SOURCE_FACT_MISMATCH
    )


def test_plan_identity_excludes_evidence_root_but_binds_source_tree() -> None:
    plan = _plan()
    other_root = replace(plan, evidence_root=r"F:\AI\temp\different-location")
    assert plan.plan_id == other_root.plan_id
    assert plan.source_matches(RAW_SHA, TREE_SHA)
    assert not plan.source_matches(RAW_SHA, "c" * 40)
    assert plan.to_manifest()["automatic_retry"] is False


def test_plan_rejects_unfrozen_alias_or_unapproved_mapping() -> None:
    plan = _plan()
    guessed = replace(ANNUAL_REVENUE_MAPPING, sec_concept="Revenues")
    with pytest.raises(ValueError, match="exact frozen B1 mapping"):
        replace(plan, field_mapping=guessed)


def test_plan_cannot_bind_non_security_or_unrelated_subject() -> None:
    plan = _plan()
    bad_subject = EvidenceSubject(
        symbol=Symbol(TICKER),
        issuer_id=CIK,
        security_id=PERMA,
        portfolio_account_id="synthetic-account",
    )
    with pytest.raises(ValueError, match="portfolio/account"):
        replace(plan, target_subject=bad_subject)


def test_parsers_reject_unknown_duplicate_boolean_and_unbounded_values() -> None:
    plan = _plan()
    with pytest.raises(QualificationInputError, match="duplicate JSON key"):
        parse_sec_response(
            b'{"issuer_cik":"0000000001","issuer_cik":"0000000001"}', plan, OBSERVED
        )
    with pytest.raises(QualificationInputError, match="unknown fields"):
        parse_sec_response(
            _json_bytes({**_sec_payload(plan), "unsafe-key-should-not-echo": "secret"}),
            plan,
            OBSERVED,
        )
    boolean = _sec_payload(plan)
    boolean["facts"][0]["value"] = True  # type: ignore[index]
    with pytest.raises(QualificationInputError, match="cannot be bool"):
        parse_sec_response(_json_bytes(boolean), plan, OBSERVED)
    huge = _sec_payload(plan, value="1e100000")
    with pytest.raises(QualificationInputError, match="bounded decimal"):
        parse_sec_response(_json_bytes(huge), plan, OBSERVED)


def test_parser_limits_are_enforced_before_candidate_materialization() -> None:
    plan = _plan()
    payload = _sec_payload(plan)
    payload["facts"].append(dict(payload["facts"][0]))  # type: ignore[union-attr,index]
    with pytest.raises(QualificationInputError, match="bounded JSON array"):
        parse_sec_response(_json_bytes(payload), plan, OBSERVED, max_facts=1)
    with pytest.raises(QualificationInputError, match="bounded JSON array"):
        parse_sharadar_page(
            _json_bytes(_sf1_payload(plan, extra_rows=[_sf1_payload(plan)["rows"][0]])),
            plan,
            OBSERVED,
            max_rows=1,
        )
