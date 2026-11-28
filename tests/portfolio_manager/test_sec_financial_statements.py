from __future__ import annotations

from datetime import date
from decimal import Decimal
from hashlib import sha256

import pytest

from trading_bot.portfolio_manager.sec_financial_statements import (
    SEC_FINANCIAL_FIELD_DEFINITIONS,
    SEC_FINANCIAL_FIELD_NAMESPACE,
    SECFinancialField,
    SECFinancialFieldStatus,
    SECFinancialInputError,
    SECFinancialPeriodKind,
    SECFinancialUnit,
    extract_sec_financial_statement,
    extract_sec_financial_statement_bytes,
    financial_field_definition,
    select_fact,
)

_ROOT = "http://www.xbrl.org/2003/instance"
_USD = ("http://www.xbrl.org/2003/iso4217", "USD")
_SHARES = (_ROOT, "shares")
_CIK = "0000878927"
_ACCESSION = "0001564590-19-004755"


def _context(
    context_id: str,
    period: str,
    *,
    start: str | None = None,
    member: str | None = None,
) -> str:
    period_xml = (
        f"<xbrli:period><xbrli:startDate>{start}</xbrli:startDate>"
        f"<xbrli:endDate>{period}</xbrli:endDate></xbrli:period>"
        if start
        else f"<xbrli:period><xbrli:instant>{period}</xbrli:instant></xbrli:period>"
    )
    segment = (
        f'<xbrli:segment><xbrldi:explicitMember dimension="test:ServiceAxis">'
        f"test:{member}Member</xbrldi:explicitMember></xbrli:segment>"
        if member
        else ""
    )
    return (
        f'<xbrli:context id="{context_id}"><xbrli:entity>'
        f'<xbrli:identifier scheme="http://www.sec.gov/CIK">{_CIK}'
        f"</xbrli:identifier>{segment}</xbrli:entity>{period_xml}</xbrli:context>"
    )


def _fact(
    concept: str,
    context: str,
    value: str,
    *,
    unit: str = "usd",
    decimals: str = "-3",
    fact_id: str = "fact",
    attributes: str = "",
    namespace: str = "us-gaap",
    child: str = "",
) -> str:
    return (
        f'<{namespace}:{concept} id="{fact_id}" contextRef="{context}" '
        f'unitRef="{unit}" decimals="{decimals}" {attributes}>'
        f"{value}{child}</{namespace}:{concept}>"
    )


def _document(
    facts: str,
    *,
    contexts: str | None = None,
    units: str | None = None,
    us_gaap_namespace: str = "http://fasb.org/us-gaap/2018-01-31",
) -> bytes:
    if contexts is None:
        contexts = (
            _context("annual", "2018-12-31", start="2018-01-01")
            + _context("quarter", "2018-12-31", start="2018-10-01")
            + _context("prior", "2017-12-31", start="2017-01-01")
            + _context("instant", "2018-12-31")
            + _context("ltl", "2018-12-31", start="2018-01-01", member="Ltl")
            + _context("other", "2018-12-31", start="2018-01-01", member="Other")
        )
    if units is None:
        units = (
            '<xbrli:unit id="usd"><xbrli:measure>iso4217:USD'
            "</xbrli:measure></xbrli:unit>"
            '<xbrli:unit id="usd_shares"><xbrli:divide>'
            "<xbrli:unitNumerator><xbrli:measure>iso4217:USD"
            "</xbrli:measure></xbrli:unitNumerator>"
            "<xbrli:unitDenominator><xbrli:measure>xbrli:shares"
            "</xbrli:measure></xbrli:unitDenominator>"
            "</xbrli:divide></xbrli:unit>"
            '<xbrli:unit id="shares"><xbrli:measure>xbrli:shares'
            "</xbrli:measure></xbrli:unit>"
        )
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl xmlns:xbrli="{_ROOT}"
 xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xmlns:iso4217="http://www.xbrl.org/2003/iso4217"
 xmlns:us-gaap="{us_gaap_namespace}"
 xmlns:test="https://example.test/axis"
 xmlns:custom="https://example.test/custom">
{contexts}
{units}
{facts}
</xbrli:xbrl>'''
    return xml.encode("utf-8")


def _extract(raw_bytes: bytes):
    return extract_sec_financial_statement_bytes(
        raw_bytes,
        expected_sha256=sha256(raw_bytes).hexdigest(),
        expected_length=len(raw_bytes),
        accession=_ACCESSION,
        document_name="odfl-20181231.xml",
        expected_cik=_CIK,
    )


def test_exact_2018_mappings_preserve_period_unit_tax_basis_and_dimensions() -> None:
    raw = _document(
        "".join(
            (
                _fact(
                    "RevenueFromContractWithCustomerIncludingAssessedTax",
                    "annual",
                    "4043695000",
                    fact_id="consolidated-revenue",
                ),
                _fact(
                    "RevenueFromContractWithCustomerIncludingAssessedTax",
                    "ltl",
                    "3982658000",
                    fact_id="ltl-revenue",
                ),
                _fact(
                    "RevenueFromContractWithCustomerIncludingAssessedTax",
                    "other",
                    "61037000",
                    fact_id="other-revenue",
                ),
                _fact(
                    "RevenueFromContractWithCustomerIncludingAssessedTax",
                    "quarter",
                    "1026944000",
                    fact_id="quarter-revenue",
                ),
                _fact(
                    "RevenueFromContractWithCustomerExcludingAssessedTax",
                    "annual",
                    "3999999000",
                    fact_id="excluding-revenue",
                ),
                _fact("OperatingIncomeLoss", "annual", "817051000"),
                _fact(
                    "NetCashProvidedByUsedInOperatingActivities",
                    "annual",
                    "-123.4500",
                    decimals="4",
                ),
                _fact(
                    "PaymentsToAcquireProductiveAssets",
                    "annual",
                    "588292000",
                    fact_id="productive-assets",
                ),
                _fact(
                    "EarningsPerShareDiluted",
                    "annual",
                    "7.38",
                    unit="usd_shares",
                    decimals="2",
                ),
                _fact(
                    "NetIncomeLoss",
                    "prior",
                    "0",
                    fact_id="zero-net-income",
                ),
                _fact(
                    "NetIncomeLoss",
                    "annual",
                    "",
                    fact_id="nil-net-income",
                    attributes='xsi:nil="true"',
                ),
                _fact(
                    "CashAndCashEquivalentsAtCarryingValue",
                    "instant",
                    "0",
                    fact_id="zero-cash",
                ),
                _fact(
                    "LongTermDebt",
                    "instant",
                    "45000000",
                    fact_id="long-term-debt",
                    decimals="-6",
                ),
                _fact(
                    "LongTermDebtAndCapitalLeaseObligations",
                    "instant",
                    "45000000",
                    fact_id="debt-capital-lease",
                ),
                _fact(
                    "LongTermDebtAndCapitalLeaseObligationsCurrent",
                    "instant",
                    "0",
                    fact_id="debt-capital-lease-current-zero",
                ),
                _fact(
                    "DebtAndCapitalLeaseObligations",
                    "instant",
                    "45000000",
                    fact_id="unmapped-combined-debt",
                ),
            )
        )
    )
    report = _extract(raw)

    revenue = select_fact(
        report,
        SECFinancialField.REVENUE_INCLUDING_ASSESSED_TAX,
        period_start=date(2018, 1, 1),
        period_end=date(2018, 12, 31),
    )
    assert revenue.status is SECFinancialFieldStatus.AVAILABLE
    assert revenue.facts[0].value == Decimal("4043695000")
    assert revenue.facts[0].context_id == "annual"
    assert revenue.facts[0].source_fact_id == "consolidated-revenue"
    assert revenue.facts[0].decimals == "-3"
    assert revenue.facts[0].dimensions == ()

    dimensional_revenue = report.field_result(
        SECFinancialField.REVENUE_INCLUDING_ASSESSED_TAX
    ).facts
    assert [fact.value for fact in dimensional_revenue[:3]] == [
        Decimal("4043695000"),
        Decimal("3982658000"),
        Decimal("61037000"),
    ]
    assert dimensional_revenue[1].dimensions[0][1][1] == "LtlMember"
    assert dimensional_revenue[2].dimensions[0][1][1] == "OtherMember"
    assert len(dimensional_revenue) == 4  # No consolidated/segment summation.

    quarter = select_fact(
        report,
        SECFinancialField.REVENUE_INCLUDING_ASSESSED_TAX,
        period_start=date(2018, 10, 1),
        period_end=date(2018, 12, 31),
    )
    assert quarter.status is SECFinancialFieldStatus.AVAILABLE
    assert quarter.facts[0].period_kind is SECFinancialPeriodKind.DURATION
    assert quarter.facts[0].value == Decimal("1026944000")

    excluding = select_fact(
        report,
        SECFinancialField.REVENUE_EXCLUDING_ASSESSED_TAX,
        period_start=date(2018, 1, 1),
        period_end=date(2018, 12, 31),
    )
    assert excluding.facts[0].value == Decimal("3999999000")
    assert excluding.facts[0].concept.endswith("ExcludingAssessedTax")

    eps = report.field_result(SECFinancialField.DILUTED_EPS).facts[0]
    assert eps.unit_id == "usd_shares"
    assert eps.unit == SECFinancialUnit(_USD, _SHARES)
    assert eps.value == Decimal("7.38")
    assert eps.decimals == "2"

    cash = select_fact(
        report,
        SECFinancialField.CASH_AND_CASH_EQUIVALENTS,
        period_start=None,
        period_end=date(2018, 12, 31),
    )
    assert cash.facts[0].period_kind is SECFinancialPeriodKind.INSTANT
    assert cash.facts[0].period_start is None
    assert cash.facts[0].value == Decimal("0")

    net_income = report.field_result(SECFinancialField.NET_INCOME)
    assert net_income.status is SECFinancialFieldStatus.AVAILABLE
    assert net_income.facts[0].value == Decimal("0")
    nil_net_income = select_fact(
        report,
        SECFinancialField.NET_INCOME,
        period_start=date(2018, 1, 1),
        period_end=date(2018, 12, 31),
    )
    assert nil_net_income.status is SECFinancialFieldStatus.UNAVAILABLE
    assert nil_net_income.reason_code == "EXACT_GRAIN_FACTS_ARE_NIL"
    assert nil_net_income.facts[0].is_nil is True
    assert nil_net_income.facts[0].value is None

    cash_flow = report.field_result(SECFinancialField.OPERATING_CASH_FLOW).facts[0]
    assert cash_flow.value == Decimal("-123.4500")
    assert cash_flow.decimals == "4"
    assert cash_flow.source.sha256 == sha256(raw).hexdigest()
    assert cash_flow.source.length == len(raw)
    assert cash_flow.source.accession == _ACCESSION
    assert cash_flow.source.document_name == "odfl-20181231.xml"
    assert cash_flow.source.issuer_cik == _CIK

    capex = report.field_result(
        SECFinancialField.CAPITAL_EXPENDITURES_PROPERTY_PLANT_EQUIPMENT
    )
    assert capex.status is SECFinancialFieldStatus.MISSING
    productive_assets = report.field_result(
        SECFinancialField.PAYMENTS_TO_ACQUIRE_PRODUCTIVE_ASSETS
    )
    assert productive_assets.facts[0].value == Decimal("588292000")
    assert productive_assets.facts[0].concept == "PaymentsToAcquireProductiveAssets"
    assert report.field_result(SECFinancialField.LONG_TERM_DEBT).facts[0].value == (
        Decimal("45000000")
    )
    assert (
        report.field_result(
            SECFinancialField.LONG_TERM_DEBT_AND_CAPITAL_LEASE_OBLIGATIONS
        )
        .facts[0]
        .concept
        == "LongTermDebtAndCapitalLeaseObligations"
    )
    debt_zero = report.field_result(
        SECFinancialField.LONG_TERM_DEBT_AND_CAPITAL_LEASE_OBLIGATIONS_CURRENT
    ).facts[0]
    assert debt_zero.value == Decimal("0")
    assert debt_zero.concept == "LongTermDebtAndCapitalLeaseObligationsCurrent"
    assert report.unsupported_concepts[0].concept == "DebtAndCapitalLeaseObligations"
    assert report.unsupported_concepts[0].raw_value_text == "45000000"
    assert report.unsupported_concepts[0].context_id == "instant"


def test_mapping_is_exactly_scoped_and_unknown_namespace_is_unavailable() -> None:
    raw = _document(
        "<custom:RevenueFromContractWithCustomerIncludingAssessedTax "
        'id="custom" contextRef="annual" unitRef="usd" decimals="0">42'
        "</custom:RevenueFromContractWithCustomerIncludingAssessedTax>",
    )
    report = _extract(raw)
    result = report.field_result(SECFinancialField.REVENUE_INCLUDING_ASSESSED_TAX)
    assert result.status is SECFinancialFieldStatus.UNAVAILABLE
    assert (
        report.unsupported_observations[0].reason_code == "US_GAAP_NAMESPACE_NOT_MAPPED"
    )
    selected = select_fact(
        report,
        SECFinancialField.REVENUE_INCLUDING_ASSESSED_TAX,
        period_start=date(2018, 1, 1),
        period_end=date(2018, 12, 31),
    )
    assert selected.status is SECFinancialFieldStatus.UNAVAILABLE
    assert selected.unsupported[0].namespace == "https://example.test/custom"
    both = _extract(
        _document(
            _fact(
                "RevenueFromContractWithCustomerIncludingAssessedTax",
                "annual",
                "4043695000",
                fact_id="supported",
            )
            + "<custom:RevenueFromContractWithCustomerIncludingAssessedTax "
            'id="unmapped" contextRef="annual" unitRef="usd" decimals="0">42'
            "</custom:RevenueFromContractWithCustomerIncludingAssessedTax>"
        )
    )
    exact = select_fact(
        both,
        SECFinancialField.REVENUE_INCLUDING_ASSESSED_TAX,
        period_start=date(2018, 1, 1),
        period_end=date(2018, 12, 31),
    )
    assert exact.status is SECFinancialFieldStatus.AVAILABLE
    assert exact.facts[0].value == Decimal("4043695000")
    assert (
        both.unsupported_observations[0].reason_code == "US_GAAP_NAMESPACE_NOT_MAPPED"
    )
    later_namespace = _extract(
        _document(
            _fact(
                "RevenueFromContractWithCustomerIncludingAssessedTax",
                "annual",
                "4043695000",
            ),
            us_gaap_namespace="http://fasb.org/us-gaap/2019-01-31",
        )
    )
    assert (
        later_namespace.field_result(
            SECFinancialField.REVENUE_INCLUDING_ASSESSED_TAX
        ).status
        is SECFinancialFieldStatus.UNAVAILABLE
    )
    definition = financial_field_definition(
        SECFinancialField.REVENUE_INCLUDING_ASSESSED_TAX
    )
    assert definition.namespace == SEC_FINANCIAL_FIELD_NAMESPACE
    assert definition.namespace == "http://fasb.org/us-gaap/2018-01-31"
    assert len(SEC_FINANCIAL_FIELD_DEFINITIONS) == len(SECFinancialField)


def test_wrong_unit_and_wrong_period_are_typed_unavailable_at_exact_grain() -> None:
    raw = _document(
        _fact(
            "OperatingIncomeLoss",
            "annual",
            "2",
            unit="shares",
            fact_id="bad-unit",
        )
        + _fact(
            "OperatingIncomeLoss",
            "instant",
            "3",
            fact_id="bad-period",
        )
    )
    report = _extract(raw)
    assert report.field_result(SECFinancialField.OPERATING_INCOME).status is (
        SECFinancialFieldStatus.UNAVAILABLE
    )
    annual = select_fact(
        report,
        SECFinancialField.OPERATING_INCOME,
        period_start=date(2018, 1, 1),
        period_end=date(2018, 12, 31),
    )
    assert annual.status is SECFinancialFieldStatus.UNAVAILABLE
    assert annual.unsupported[0].reason_code == "XBRL_UNIT_BASIS_UNSUPPORTED_FOR_FIELD"
    instant = select_fact(
        report,
        SECFinancialField.OPERATING_INCOME,
        period_start=None,
        period_end=date(2018, 12, 31),
    )
    assert instant.status is SECFinancialFieldStatus.UNAVAILABLE
    assert (
        instant.unsupported[0].reason_code == "XBRL_PERIOD_KIND_UNSUPPORTED_FOR_FIELD"
    )


def test_equivalent_context_and_unit_ids_preserve_duplicate_provenance() -> None:
    contexts = _context("instant", "2018-12-31") + _context(
        "instant-alias", "2018-12-31"
    )
    units = (
        '<xbrli:unit id="usd"><xbrli:measure>iso4217:USD'
        "</xbrli:measure></xbrli:unit>"
        '<xbrli:unit id="usd-alias"><xbrli:measure>iso4217:USD'
        "</xbrli:measure></xbrli:unit>"
    )
    facts = _fact("Assets", "instant", "0", fact_id="asset-one") + _fact(
        "Assets", "instant-alias", "0", unit="usd-alias", fact_id="asset-two"
    )
    report = _extract(_document(facts, contexts=contexts, units=units))
    result = select_fact(
        report,
        SECFinancialField.TOTAL_ASSETS,
        period_start=None,
        period_end=date(2018, 12, 31),
    )
    assert result.status is SECFinancialFieldStatus.AVAILABLE
    assert [fact.source_fact_id for fact in result.facts] == ["asset-one", "asset-two"]
    assert [fact.unit_id for fact in result.facts] == ["usd", "usd-alias"]


def test_conflicting_duplicates_fail_closed_at_selected_grain() -> None:
    facts = _fact("Assets", "instant", "10", fact_id="asset-one") + _fact(
        "Assets", "instant", "11", fact_id="asset-two"
    )
    report = _extract(_document(facts))
    result = report.field_result(SECFinancialField.TOTAL_ASSETS)
    assert result.status is SECFinancialFieldStatus.AMBIGUOUS
    assert len(result.facts) == 2
    selected = select_fact(
        report,
        SECFinancialField.TOTAL_ASSETS,
        period_start=None,
        period_end=date(2018, 12, 31),
    )
    assert selected.status is SECFinancialFieldStatus.AMBIGUOUS
    assert selected.reason_code == "MULTIPLE_EXACT_PERIOD_AND_DIMENSION_OBSERVATIONS"
    assert len(selected.conflicts) == 2


def test_conflict_at_quarterly_grain_does_not_mask_clean_annual_fact() -> None:
    facts = (
        _fact(
            "RevenueFromContractWithCustomerIncludingAssessedTax",
            "annual",
            "4043695000",
            fact_id="annual",
        )
        + _fact(
            "RevenueFromContractWithCustomerIncludingAssessedTax",
            "quarter",
            "1026944000",
            fact_id="quarter-one",
        )
        + _fact(
            "RevenueFromContractWithCustomerIncludingAssessedTax",
            "quarter",
            "1026944001",
            fact_id="quarter-two",
        )
    )
    report = _extract(_document(facts))
    assert (
        report.field_result(SECFinancialField.REVENUE_INCLUDING_ASSESSED_TAX).status
        is SECFinancialFieldStatus.AMBIGUOUS
    )
    annual = select_fact(
        report,
        SECFinancialField.REVENUE_INCLUDING_ASSESSED_TAX,
        period_start=date(2018, 1, 1),
        period_end=date(2018, 12, 31),
    )
    assert annual.status is SECFinancialFieldStatus.AVAILABLE
    assert annual.facts[0].value == Decimal("4043695000")


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16"])
def test_doctype_and_entities_are_rejected_by_xml_parser_callbacks(
    encoding: str,
) -> None:
    xml = f'''<?xml version="1.0"?>
<!DOCTYPE xbrli:xbrl [<!ENTITY injected SYSTEM "file:///C:/sensitive.txt">]>
<xbrli:xbrl xmlns:xbrli="{_ROOT}">&injected;</xbrli:xbrl>'''
    raw = xml.encode(encoding)
    with pytest.raises(SECFinancialInputError) as error:
        _extract(raw)
    assert error.value.reason_code == "XML_DTD_FORBIDDEN"


def test_schema_reference_is_ignored_and_inline_shapes_are_not_scaled() -> None:
    xml = (
        _document(
            _fact(
                "RevenueFromContractWithCustomerIncludingAssessedTax",
                "annual",
                "4043",
                fact_id="inline-scaled",
                attributes='scale="6"',
            )
        )
        .replace(
            b"<xbrli:xbrl ",
            b'<xbrli:xbrl xmlns:xlink="http://www.w3.org/1999/xlink" '
            b'xmlns:xbrll="http://www.xbrl.org/2003/linkbase" ',
        )
        .replace(
            b"</xbrli:xbrl>",
            b'<xbrll:schemaRef xlink:href="https://example.invalid/taxonomy.xsd" />'
            b"</xbrli:xbrl>",
        )
    )
    report = _extract(xml)
    result = report.field_result(SECFinancialField.REVENUE_INCLUDING_ASSESSED_TAX)
    assert result.status is SECFinancialFieldStatus.UNAVAILABLE
    assert result.facts == ()
    assert report.unsupported_observations[0].reason_code == (
        "XBRL_MAPPED_FACT_ATTRIBUTES_UNSUPPORTED"
    )


@pytest.mark.parametrize("value", ["1e3", "1_000", "١٢", "+", "--1"])
def test_decimal_lexical_value_does_not_accept_non_xsd_decimal_forms(
    value: str,
) -> None:
    with pytest.raises(SECFinancialInputError) as error:
        _extract(_document(_fact("Assets", "instant", value, fact_id="bad-decimal")))
    assert error.value.reason_code == "XBRL_DECIMAL_VALUE_INVALID"


def test_nested_mapped_fact_is_unavailable_instead_of_read_as_a_scalar() -> None:
    raw = _document(
        _fact(
            "Assets",
            "instant",
            "10",
            fact_id="nested",
            child="<custom:unexpected>20</custom:unexpected>",
        )
    )
    report = _extract(raw)
    assert report.field_result(SECFinancialField.TOTAL_ASSETS).status is (
        SECFinancialFieldStatus.UNAVAILABLE
    )
    assert report.unsupported_observations[0].reason_code == (
        "XBRL_MAPPED_FACT_CHILD_ELEMENTS_UNSUPPORTED"
    )


def test_source_hash_and_length_are_verified_before_parsing() -> None:
    raw = _document(_fact("Assets", "instant", "0"))
    with pytest.raises(SECFinancialInputError) as hash_error:
        extract_sec_financial_statement_bytes(
            raw,
            expected_sha256="0" * 64,
            expected_length=len(raw),
            accession=_ACCESSION,
            document_name="odfl-20181231.xml",
            expected_cik=_CIK,
        )
    assert hash_error.value.reason_code == "INSTANCE_SHA256_MISMATCH"
    with pytest.raises(SECFinancialInputError) as length_error:
        extract_sec_financial_statement_bytes(
            raw + b" ",
            expected_sha256=sha256(raw).hexdigest(),
            expected_length=len(raw),
            accession=_ACCESSION,
            document_name="odfl-20181231.xml",
            expected_cik=_CIK,
        )
    assert length_error.value.reason_code == "INSTANCE_LENGTH_MISMATCH"


def test_local_file_extractor_rejects_unc_and_reads_only_verified_file(
    tmp_path,
) -> None:
    raw = _document(_fact("Assets", "instant", "0"))
    path = tmp_path / "instance.xml"
    path.write_bytes(raw)
    report = extract_sec_financial_statement(
        path,
        expected_sha256=sha256(raw).hexdigest(),
        expected_length=len(raw),
        accession=_ACCESSION,
        document_name="odfl-20181231.xml",
        expected_cik=_CIK,
    )
    assert report.source.sha256 == sha256(raw).hexdigest()
    with pytest.raises(SECFinancialInputError) as error:
        extract_sec_financial_statement(
            r"\\server\share\instance.xml",
            expected_sha256=sha256(raw).hexdigest(),
            expected_length=len(raw),
            accession=_ACCESSION,
            document_name="odfl-20181231.xml",
            expected_cik=_CIK,
        )
    assert error.value.reason_code == "UNC_OR_DEVICE_PATH_FORBIDDEN"
