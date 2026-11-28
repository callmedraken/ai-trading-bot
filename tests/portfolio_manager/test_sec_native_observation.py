from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid5

import pytest

from trading_bot.portfolio_manager import sec_native_observation as sec

NOW = datetime(2026, 11, 27, 12, tzinfo=UTC)
HEAD = "a" * 40
TREE = "b" * 40
CIK = "0000000001"
ACCESSION = "0000000001-24-000001"
DOCUMENT = "instance.xml"
CONCEPT_NS = "http://fasb.org/us-gaap/2024"
CONCEPT = "RevenueFromContractWithCustomerExcludingAssessedTax"
CONTEXT = "FY2023"
UNIT = "USD"


def _plan(**changes: object) -> sec.SECObservationPlan:
    values: dict[str, object] = {
        "attempt_id": uuid5(UUID(int=0), "sec-observation-test-attempt"),
        "expected_source_head": HEAD,
        "expected_source_tree": TREE,
        "issuer_cik": CIK,
        "accession": ACCESSION,
        "filing_form": "10-K",
        "document_name": DOCUMENT,
        "document_sequence": "2",
        "fiscal_year": 2023,
        "period_start": date(2023, 1, 1),
        "period_end": date(2023, 12, 31),
        "context_id": CONTEXT,
        "entity_identifier_scheme": "http://www.sec.gov/CIK",
        "concept_namespace": CONCEPT_NS,
        "concept_local_name": CONCEPT,
        "unit_id": UNIT,
        "unit_namespace": "http://www.xbrl.org/2003/iso4217",
        "unit_local_name": "USD",
        "dimensions": (),
        "user_agent": "PM2D observation review contact@example.invalid",
        "evidence_root": r"F:\AI\temp\pm2d-b1-r-tests",
    }
    values.update(changes)
    return sec.SECObservationPlan(**values)  # type: ignore[arg-type]


def _submission(
    plan: sec.SECObservationPlan,
    *,
    accession: str | None = None,
    cik: str | None = None,
    form: str | None = None,
    period_end: date | None = None,
    sequence: str = "2",
    instance: bytes | None = None,
) -> bytes:
    accession = accession or plan.accession
    cik = cik or plan.issuer_cik
    form = form or plan.filing_form
    period_end = period_end or plan.period_end
    instance_text = (instance or _instance(plan)).decode("ascii")
    return (
        f"""<SEC-DOCUMENT>{accession}.txt
<TYPE>{form}
<ACCEPTANCE-DATETIME>20250215175500
<SEC-HEADER>
ACCESSION NUMBER: {accession}
CONFORMED SUBMISSION TYPE: {form}
FILED AS OF DATE: 20250215
CONFORMED PERIOD OF REPORT: {period_end:%Y%m%d}
CENTRAL INDEX KEY: {cik}
</SEC-HEADER>
<DOCUMENT>
<TYPE>EX-101.INS
<SEQUENCE>{sequence}
<FILENAME>{plan.document_name}
<TEXT>
{instance_text}
</TEXT>
</DOCUMENT>
</SEC-DOCUMENT>
"""
    ).encode("ascii")


def _instance(
    plan: sec.SECObservationPlan,
    *,
    cik: str | None = None,
    start: date | None = None,
    end: date | None = None,
    context_id: str | None = None,
    namespace: str | None = None,
    value: str = "123456789.125",
    include_fact: bool = True,
    unit: str = "USD",
    extra_dimensions: str = "",
    extra_facts: str = "",
) -> bytes:
    fact = (
        f"""<us-gaap:{plan.concept_local_name}
      contextRef="{context_id or plan.context_id}" unitRef="USD" decimals="0">
        {value}
      </us-gaap:{plan.concept_local_name}>"""
        if include_fact
        else ""
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
 xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
 xmlns:us-gaap="{namespace or plan.concept_namespace}"
 xmlns:iso4217="http://www.xbrl.org/2003/iso4217">
  <xbrli:context id="{context_id or plan.context_id}">
    <xbrli:entity>
      <xbrli:identifier scheme="http://www.sec.gov/CIK">
        {cik or plan.issuer_cik}
      </xbrli:identifier>
      {extra_dimensions}
    </xbrli:entity>
    <xbrli:period>
      <xbrli:startDate>{start or plan.period_start}</xbrli:startDate>
      <xbrli:endDate>{end or plan.period_end}</xbrli:endDate>
    </xbrli:period>
  </xbrli:context>
  <xbrli:unit id="USD"><xbrli:measure>iso4217:{unit}</xbrli:measure></xbrli:unit>
  {fact}
  {extra_facts}
</xbrli:xbrl>
""".encode("ascii")


def _authorization(plan: sec.SECObservationPlan) -> sec.SECObservationAuthorization:
    return sec.SECObservationAuthorization(
        authorization_id="review-2026-11-27",
        approved_plan_id=plan.plan_id,
        approved_source_head=plan.expected_source_head,
        approved_source_tree=plan.expected_source_tree,
        approved_attempt_id=plan.attempt_id,
        review_record_sha256="c" * 64,
        issued_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(minutes=10),
    )


class MemoryEvidenceStore:
    def __init__(self, *, consumed: bool = False, fail_intent: int | None = None):
        self.consumed = consumed
        self.fail_intent = fail_intent
        self.intents: list[dict[str, object]] = []
        self.responses: list[tuple[int, str, bytes, str]] = []
        self.response_received_at: list[datetime | None] = []
        self.terminal: dict[str, object] | None = None

    def reserve_attempt(self, plan: sec.SECObservationPlan) -> bool:
        del plan
        return not self.consumed

    def write_request_intent(self, ordinal: int, material: dict[str, object]) -> None:
        if ordinal == self.fail_intent:
            raise OSError("synthetic write failure")
        self.intents.append(dict(material))

    def write_response(
        self,
        ordinal: int,
        label: str,
        body: bytes,
        content_type: str,
        *,
        received_at: datetime | None = None,
    ) -> str:
        self.responses.append((ordinal, label, body, content_type))
        self.response_received_at.append(received_at)
        return hashlib.sha256(body).hexdigest()

    def write_terminal(self, material: dict[str, object]) -> None:
        self.terminal = dict(material)


class FakeTransport:
    def __init__(
        self,
        plan: sec.SECObservationPlan,
        store: MemoryEvidenceStore,
        *,
        fail_at: int | None = None,
        over_limit_at: int | None = None,
    ):
        self.plan = plan
        self.store = store
        self.fail_at = fail_at
        self.over_limit_at = over_limit_at
        self.calls: list[str] = []

    def get(
        self,
        url: str,
        *,
        user_agent: str,
        timeout_seconds: int,
        total_time_limit_seconds: float,
        max_bytes: int,
    ) -> sec.SECTransportResponse:
        ordinal = len(self.calls) + 1
        assert ordinal == 1
        assert len(self.store.intents) == ordinal
        intent = self.store.intents[-1]
        assert intent["method"] == "GET"
        assert intent["accept_header"] == "text/plain"
        assert intent["endpoint"] == url == self.plan.submission_url
        assert intent["request_parameters"] == []
        assert intent["automatic_retry"] is False
        assert intent["total_time_limit_seconds"] == self.plan.total_time_limit_seconds
        assert user_agent == self.plan.user_agent
        assert timeout_seconds == self.plan.request_timeout_seconds
        assert 0 < total_time_limit_seconds <= self.plan.total_time_limit_seconds
        self.calls.append(url)
        if ordinal == self.fail_at:
            raise TimeoutError("synthetic timeout")
        body = _submission(self.plan)
        content_type = "text/plain"
        if ordinal == self.over_limit_at:
            body = b"x" * (max_bytes + 1)
        return sec.SECTransportResponse(200, content_type, body, url, NOW)


def _run(
    monkeypatch: pytest.MonkeyPatch,
    plan: sec.SECObservationPlan,
    transport: FakeTransport,
    store: MemoryEvidenceStore,
    *,
    admission: sec.SECSourceAdmission | None = None,
    authorization: sec.SECObservationAuthorization | None = None,
    monotonic_values: tuple[float, ...] = (0.0, 0.0, 0.0, 0.0, 0.0),
) -> sec.SECObservationResult:
    monkeypatch.setattr(sec, "_current_source_is_admitted", lambda _: True)
    values = iter(monotonic_values)
    return sec._observe_sec_once_with_transport(
        plan,
        admission or sec.SECSourceAdmission(HEAD, TREE, "PASS", "PASS", "d" * 64),
        authorization or _authorization(plan),
        transport,
        store,
        now=lambda: NOW,
        monotonic=lambda: next(values),
    )


def test_plan_binds_only_one_exact_annual_usd_revenue_observation() -> None:
    plan = _plan()
    manifest = plan.to_manifest()
    assert manifest["filing_form"] == "10-K"
    assert manifest["currency"] == "USD"
    assert manifest["scale"] == 0
    assert manifest["max_request_attempts"] == 1
    assert manifest["automatic_retry"] is False
    assert manifest["requested_endpoints"] == [plan.submission_url]
    assert plan.source_matches(HEAD, TREE)
    assert not plan.source_matches("c" * 40, TREE)


@pytest.mark.parametrize(
    "changes",
    [
        {"filing_form": "10-Q"},
        {"document_name": "../instance.xml"},
        {"automatic_retry": True},
        {"evidence_root": r"C:\temp\evidence"},
        {"max_response_bytes": 10_000_001},
    ],
)
def test_plan_rejects_scope_or_bound_changes(changes: dict[str, object]) -> None:
    with pytest.raises((TypeError, ValueError)):
        _plan(**changes)


def test_native_submission_binds_accession_document_cik_and_acceptance() -> None:
    plan = _plan()
    submission = sec.parse_sec_submission(_submission(plan), plan, NOW)
    assert submission.issuer_cik == CIK
    assert submission.accession == ACCESSION
    assert submission.document_type == "EX-101.INS"
    assert submission.document_sequence == "2"
    assert submission.embedded_document_length == len(_instance(plan))
    start, end = submission.embedded_document_range
    assert _submission(plan)[start:end] == _instance(plan)
    assert submission.accepted_timestamp_raw == "20250215175500"
    assert submission.observed_at == NOW


def test_native_submission_requires_exact_filename_not_a_prefix() -> None:
    plan = _plan()
    raw = _submission(plan).replace(
        f"<FILENAME>{plan.document_name}".encode(),
        f"<FILENAME>{plan.document_name}.unexpected".encode(),
    )
    with pytest.raises(sec.SECNativeInputError) as caught:
        sec.parse_sec_submission(raw, plan, NOW)
    assert caught.value.reason_code == "SEC_DOCUMENT_NAME_MISSING_OR_DUPLICATE"


def test_embedded_document_must_match_parent_digest_length_and_byte_range() -> None:
    plan = _plan()
    raw = _submission(plan)
    submission = sec.parse_sec_submission(raw, plan, NOW)
    assert sec.extract_sec_submission_member(raw, submission) == _instance(plan)

    changed_digest = replace(submission, embedded_document_sha256="0" * 64)
    with pytest.raises(sec.SECNativeInputError) as caught:
        sec.extract_sec_submission_member(raw, changed_digest)
    assert caught.value.reason_code == "SEC_EMBEDDED_DOCUMENT_DIGEST_OR_RANGE_MISMATCH"

    changed_parent = replace(submission, content_sha256="0" * 64)
    with pytest.raises(sec.SECNativeInputError) as caught:
        sec.extract_sec_submission_member(raw, changed_parent)
    assert caught.value.reason_code == "SEC_PARENT_SUBMISSION_IDENTITY_MISMATCH"

    changed_range = replace(
        submission,
        embedded_document_range=(0, submission.embedded_document_length),
    )
    with pytest.raises(sec.SECNativeInputError):
        sec.extract_sec_submission_member(raw, changed_range)


def test_native_submission_accepts_utf8_filing_bytes_without_losing_raw_identity() -> (
    None
):
    plan = _plan()
    raw = _submission(plan).replace(b"<us-gaap:", b"<!-- caf\xc3\xa9 -->\n<us-gaap:", 1)
    submission = sec.parse_sec_submission(raw, plan, NOW)
    assert submission.content_length == len(raw)
    assert submission.content_sha256 == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize(
    "changes",
    [
        {"accession": "0000000001-24-000099"},
        {"cik": "0000000002"},
        {"form": "10-Q"},
    ],
)
def test_native_submission_rejects_wrong_identity(changes: dict[str, str]) -> None:
    plan = _plan()
    with pytest.raises(sec.SECNativeInputError):
        sec.parse_sec_submission(_submission(plan, **changes), plan, NOW)


def test_native_submission_rejects_wrong_document_sequence() -> None:
    plan = _plan()
    with pytest.raises(sec.SECNativeInputError) as caught:
        sec.parse_sec_submission(_submission(plan, sequence="3"), plan, NOW)
    assert caught.value.reason_code == "SEC_DOCUMENT_SEQUENCE_MISMATCH"


def test_native_submission_rejects_period_header_mismatch() -> None:
    plan = _plan()
    with pytest.raises(sec.SECNativeInputError) as caught:
        sec.parse_sec_submission(
            _submission(plan, period_end=date(2023, 12, 30)), plan, NOW
        )
    assert caught.value.reason_code == "SEC_SUBMISSION_IDENTITY_MISMATCH"


def test_native_submission_rejects_duplicate_issuer_identity() -> None:
    plan = _plan()
    raw = _submission(plan).replace(
        b"CENTRAL INDEX KEY: " + CIK.encode("ascii") + b"\n</SEC-HEADER>",
        b"CENTRAL INDEX KEY: "
        + CIK.encode("ascii")
        + b"\nCENTRAL INDEX KEY: "
        + CIK.encode("ascii")
        + b"\n</SEC-HEADER>",
    )
    with pytest.raises(sec.SECNativeInputError) as caught:
        sec.parse_sec_submission(raw, plan, NOW)
    assert caught.value.reason_code == "SEC_SUBMISSION_IDENTITY_MISMATCH"


def test_native_xbrl_preserves_exact_signed_decimal_and_grain() -> None:
    plan = _plan()
    submission = sec.parse_sec_submission(_submission(plan), plan, NOW)
    fact = sec.parse_native_xbrl_revenue(
        _instance(plan, value="-0.0000001"), plan, submission
    )
    assert fact.signed_decimal_value == Decimal("-0.0000001")
    assert fact.signed_decimal_value.as_tuple().exponent == -7
    assert fact.issuer_cik == plan.issuer_cik
    assert fact.period_start == plan.period_start
    assert fact.period_end == plan.period_end
    assert fact.currency == "USD"
    assert fact.scale == 0


def test_native_xbrl_binds_exact_explicit_dimensions() -> None:
    axis = (CONCEPT_NS, "ProductOrServiceAxis")
    member = (CONCEPT_NS, "SoftwareMember")
    plan = _plan(dimensions=((axis, member),))
    submission = sec.parse_sec_submission(_submission(plan), plan, NOW)
    dimension_xml = (
        "<xbrli:segment><xbrldi:explicitMember "
        'dimension="us-gaap:ProductOrServiceAxis">'
        "us-gaap:SoftwareMember</xbrldi:explicitMember></xbrli:segment>"
    )
    fact = sec.parse_native_xbrl_revenue(
        _instance(plan, extra_dimensions=dimension_xml), plan, submission
    )
    assert fact.dimensions == plan.dimensions

    undimensioned_plan = _plan()
    undimensioned_submission = sec.parse_sec_submission(
        _submission(undimensioned_plan), undimensioned_plan, NOW
    )
    with pytest.raises(sec.SECNativeInputError) as caught:
        sec.parse_native_xbrl_revenue(
            _instance(undimensioned_plan, extra_dimensions=dimension_xml),
            undimensioned_plan,
            undimensioned_submission,
        )
    assert caught.value.code is sec.SECObservationOutcome.SEC_FACT_CONTEXT_MISMATCH


def test_native_xbrl_binds_dimensions_from_context_scenario() -> None:
    plan = _plan()
    submission = sec.parse_sec_submission(_submission(plan), plan, NOW)
    scenario = (
        b"<xbrli:scenario><xbrldi:explicitMember "
        b'dimension="us-gaap:ProductOrServiceAxis">'
        b"us-gaap:SoftwareMember</xbrldi:explicitMember></xbrli:scenario>"
    )
    raw = _instance(plan).replace(
        b"  </xbrli:context>", scenario + b"\n  </xbrli:context>"
    )
    with pytest.raises(sec.SECNativeInputError) as caught:
        sec.parse_native_xbrl_revenue(raw, plan, submission)
    assert caught.value.code is sec.SECObservationOutcome.SEC_FACT_CONTEXT_MISMATCH

    axis = (CONCEPT_NS, "ProductOrServiceAxis")
    member = (CONCEPT_NS, "SoftwareMember")
    dimensional_plan = _plan(dimensions=((axis, member),))
    dimensional_submission = sec.parse_sec_submission(
        _submission(dimensional_plan), dimensional_plan, NOW
    )
    dimensional_raw = _instance(dimensional_plan).replace(
        b"  </xbrli:context>", scenario + b"\n  </xbrli:context>"
    )
    fact = sec.parse_native_xbrl_revenue(
        dimensional_raw, dimensional_plan, dimensional_submission
    )
    assert fact.dimensions == dimensional_plan.dimensions


@pytest.mark.parametrize(
    ("xml_changes", "outcome"),
    [
        ({"cik": "0000000002"}, sec.SECObservationOutcome.SEC_FACT_CONTEXT_MISMATCH),
        (
            {"start": date(2023, 1, 2)},
            sec.SECObservationOutcome.SEC_FACT_CONTEXT_MISMATCH,
        ),
        (
            {"end": date(2023, 12, 30)},
            sec.SECObservationOutcome.SEC_FACT_CONTEXT_MISMATCH,
        ),
        ({"context_id": "OTHER"}, sec.SECObservationOutcome.SEC_FACT_CONTEXT_MISMATCH),
        (
            {"namespace": "http://fasb.org/us-gaap/2099"},
            sec.SECObservationOutcome.SEC_FACT_MISSING,
        ),
        ({"unit": "CAD"}, sec.SECObservationOutcome.SEC_FACT_CONTEXT_MISMATCH),
    ],
)
def test_native_xbrl_rejects_context_period_namespace_and_unit_mismatch(
    xml_changes: dict[str, object], outcome: sec.SECObservationOutcome
) -> None:
    plan = _plan()
    submission = sec.parse_sec_submission(_submission(plan), plan, NOW)
    with pytest.raises(sec.SECNativeInputError) as caught:
        sec.parse_native_xbrl_revenue(_instance(plan, **xml_changes), plan, submission)
    assert caught.value.code is outcome


def test_native_xbrl_rejects_duplicate_conflict_missing_and_keeps_true_zero() -> None:
    plan = _plan()
    submission = sec.parse_sec_submission(_submission(plan), plan, NOW)
    zero = sec.parse_native_xbrl_revenue(_instance(plan, value="0"), plan, submission)
    assert zero.signed_decimal_value == Decimal(0)
    absent = _instance(plan, include_fact=False)
    with pytest.raises(sec.SECNativeInputError) as caught:
        sec.parse_native_xbrl_revenue(absent, plan, submission)
    assert caught.value.code is sec.SECObservationOutcome.SEC_FACT_MISSING
    duplicate_fact = (
        f'<us-gaap:{CONCEPT} contextRef="{CONTEXT}" unitRef="USD">4</us-gaap:{CONCEPT}>'
    )
    with pytest.raises(sec.SECNativeInputError) as caught:
        sec.parse_native_xbrl_revenue(
            _instance(plan, extra_facts=duplicate_fact),
            plan,
            submission,
        )
    assert caught.value.code is sec.SECObservationOutcome.SEC_FACT_CONFLICTED


def test_native_xbrl_rejects_dtd_external_entities_and_element_overflow() -> None:
    plan = _plan()
    submission = sec.parse_sec_submission(_submission(plan), plan, NOW)
    with pytest.raises(sec.SECNativeInputError) as caught:
        sec.parse_native_xbrl_revenue(
            b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///secret">]>' + _instance(plan),
            plan,
            submission,
        )
    assert caught.value.reason_code == "XML_DTD_OR_ENTITY_REJECTED"

    utf16_dtd = (
        '<!DOCTYPE x [<!ENTITY e SYSTEM "file:///secret">]>'
        + _instance(plan).decode("ascii")
    ).encode("utf-16")
    with pytest.raises(sec.SECNativeInputError) as caught:
        sec.parse_native_xbrl_revenue(utf16_dtd, plan, submission)
    assert caught.value.reason_code == "NATIVE_XBRL_ENCODING_UNSUPPORTED"

    bounded = _plan(max_xml_elements=4)
    bounded_submission = sec.parse_sec_submission(_submission(bounded), bounded, NOW)
    with pytest.raises(sec.SECNativeInputError) as caught:
        sec.parse_native_xbrl_revenue(_instance(bounded), bounded, bounded_submission)
    assert caught.value.reason_code == "XBRL_ELEMENT_LIMIT_REACHED"


def test_native_response_size_limit_precedes_parsing() -> None:
    plan = _plan(max_response_bytes=100)
    with pytest.raises(sec.SECNativeInputError) as caught:
        sec.parse_sec_submission(_submission(plan), plan, NOW)
    assert caught.value.code is sec.SECObservationOutcome.RESPONSE_REJECTED


def test_source_and_effect_authorization_fail_before_any_transport_call() -> None:
    plan = _plan()
    store = MemoryEvidenceStore()
    transport = FakeTransport(plan, store)
    wrong_source = sec.SECSourceAdmission("c" * 40, TREE, "PASS", "PASS", "d" * 64)
    result = sec._observe_sec_once_with_transport(
        plan,
        wrong_source,
        _authorization(plan),
        transport,
        store,
        now=lambda: NOW,
    )
    assert result.outcome is sec.SECObservationOutcome.SOURCE_ADMISSION_FAILED
    assert result.counters.provider_invocations == 0
    assert not transport.calls
    assert not store.intents

    wrong_auth = _authorization(plan)
    wrong_auth = sec.SECObservationAuthorization(
        wrong_auth.authorization_id,
        "e" * 64,
        wrong_auth.approved_source_head,
        wrong_auth.approved_source_tree,
        wrong_auth.approved_attempt_id,
        wrong_auth.review_record_sha256,
        wrong_auth.issued_at,
        wrong_auth.expires_at,
    )
    result = sec._observe_sec_once_with_transport(
        plan,
        sec.SECSourceAdmission(HEAD, TREE, "PASS", "PASS", "d" * 64),
        wrong_auth,
        transport,
        store,
        now=lambda: NOW,
    )
    assert result.outcome is sec.SECObservationOutcome.EFFECT_AUTHORIZATION_FAILED
    assert result.counters.provider_invocations == 0
    assert not transport.calls


def test_authorization_expiry_during_source_admission_stops_before_reservation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan()
    store = MemoryEvidenceStore()
    transport = FakeTransport(plan, store)
    moments = iter((NOW, NOW + timedelta(minutes=11)))
    monkeypatch.setattr(sec, "_current_source_is_admitted", lambda _: True)
    result = sec._observe_sec_once_with_transport(
        plan,
        sec.SECSourceAdmission(HEAD, TREE, "PASS", "PASS", "d" * 64),
        _authorization(plan),
        transport,
        store,
        now=lambda: next(moments),
    )
    assert result.outcome is sec.SECObservationOutcome.EFFECT_AUTHORIZATION_FAILED
    assert (
        result.reason_code
        == "EFFECT_AUTHORIZATION_EXPIRED_OR_EVIDENCE_CHANGED_AFTER_ADMISSION"
    )
    assert result.counters.provider_invocations == 0
    assert not store.consumed
    assert not transport.calls


def test_authorization_evidence_change_after_intent_stops_before_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan()
    store = MemoryEvidenceStore()
    transport = FakeTransport(plan, store)
    monkeypatch.setattr(sec, "_current_source_is_admitted", lambda _: True)
    rechecks = iter((True, False))
    authorization = replace(_authorization(plan), source_admission_sha256="d" * 64)
    result = sec._observe_sec_once_with_transport(
        plan,
        sec.SECSourceAdmission(HEAD, TREE, "PASS", "PASS", "d" * 64),
        authorization,
        transport,
        store,
        now=lambda: NOW,
        authorization_recheck=lambda: next(rechecks),
    )
    assert result.outcome is sec.SECObservationOutcome.EFFECT_AUTHORIZATION_FAILED
    assert (
        result.reason_code
        == "EFFECT_AUTHORIZATION_EXPIRED_OR_EVIDENCE_CHANGED_BEFORE_REQUEST"
    )
    assert result.counters.request_intents == 1
    assert result.counters.provider_invocations == 0
    assert not transport.calls


def test_current_source_admission_failure_precedes_attempt_reservation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan()
    store = MemoryEvidenceStore()
    transport = FakeTransport(plan, store)
    monkeypatch.setattr(sec, "_current_source_is_admitted", lambda _: False)
    result = sec._observe_sec_once_with_transport(
        plan,
        sec.SECSourceAdmission(HEAD, TREE, "PASS", "PASS", "d" * 64),
        _authorization(plan),
        transport,
        store,
        now=lambda: NOW,
    )
    assert result.outcome is sec.SECObservationOutcome.SOURCE_ADMISSION_FAILED
    assert result.counters.provider_invocations == 0
    assert not store.consumed
    assert not transport.calls


def test_successful_synthetic_transport_keeps_raw_bytes_separate_and_still_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan()
    store = MemoryEvidenceStore()
    transport = FakeTransport(plan, store)
    authorization = _authorization(plan)
    result = _run(monkeypatch, plan, transport, store, authorization=authorization)
    assert result.outcome is sec.SECObservationOutcome.SEC_OBSERVATION_BLOCKED
    assert (
        result.reason_code
        == "SEC_HISTORICAL_VERSION_WITNESS_AND_SECURITY_MAPPING_UNPROVEN"
    )
    assert result.counters.provider_invocations == 1
    assert result.counters.request_intents == 1
    assert result.counters.response_documents == 1
    assert result.counters.response_bytes == len(_submission(plan))
    assert result.counters.response_bytes_received == len(_submission(plan))
    assert result.counters.xbrl_records == 1
    assert result.fact is not None
    assert result.fact.signed_decimal_value == Decimal("123456789.125")
    assert not result.source_fact_created
    assert result.counters.credential_reads == 0
    assert result.counters.account_reads == 0
    assert result.counters.ai_calls == 0
    assert result.counters.broker_effects == 0
    assert result.counters.production_mutations == 0
    assert len(store.responses) == 1
    assert store.responses[0][2] == _submission(plan)
    assert store.response_received_at == [NOW]
    assert result.submission is not None
    assert result.submission.observed_at == NOW
    assert store.intents[0]["effect_authorization"] == {
        "authorization_id": authorization.authorization_id,
        "approved_plan_id": plan.plan_id,
        "approved_source_head": HEAD,
        "approved_source_tree": TREE,
        "approved_attempt_id": str(plan.attempt_id),
        "review_record_sha256": authorization.review_record_sha256,
        "source_admission_sha256": "d" * 64,
        "issued_at": authorization.issued_at.isoformat(),
        "expires_at": authorization.expires_at.isoformat(),
        "max_request_attempts": 1,
    }
    assert store.terminal is not None
    assert store.terminal["public_availability_witness"] == "UNPROVEN"
    normalized_fact = store.terminal["normalized_fact"]
    assert isinstance(normalized_fact, dict)
    assert normalized_fact["signed_decimal_value"] == "123456789.125"


def test_provider_timeout_is_counted_once_and_never_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan()
    store = MemoryEvidenceStore()
    transport = FakeTransport(plan, store, fail_at=1)
    result = _run(monkeypatch, plan, transport, store)
    assert result.outcome is sec.SECObservationOutcome.PROVIDER_FAILED
    assert result.counters.provider_invocations == 1
    assert result.counters.request_intents == 1
    assert len(transport.calls) == 1
    assert len(store.responses) == 0
    assert store.terminal is not None


def test_consumed_attempt_and_intent_write_failure_cannot_invoke_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan()
    consumed_store = MemoryEvidenceStore(consumed=True)
    consumed_transport = FakeTransport(plan, consumed_store)
    consumed = _run(monkeypatch, plan, consumed_transport, consumed_store)
    assert consumed.outcome is sec.SECObservationOutcome.ATTEMPT_CONSUMED
    assert consumed.counters.provider_invocations == 0
    assert not consumed_transport.calls

    failed_store = MemoryEvidenceStore(fail_intent=1)
    failed_transport = FakeTransport(plan, failed_store)
    failed = _run(monkeypatch, plan, failed_transport, failed_store)
    assert failed.outcome is sec.SECObservationOutcome.EVIDENCE_WRITE_FAILED
    assert failed.counters.provider_invocations == 0
    assert failed.counters.request_intents == 1
    assert not failed_transport.calls


def test_response_and_total_time_limits_stop_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan(max_response_bytes=100)
    store = MemoryEvidenceStore()
    transport = FakeTransport(plan, store, over_limit_at=1)
    oversized = _run(monkeypatch, plan, transport, store)
    assert oversized.outcome is sec.SECObservationOutcome.RESPONSE_REJECTED
    assert oversized.counters.provider_invocations == 1
    assert oversized.counters.response_documents == 0
    assert oversized.counters.response_bytes == 0
    assert oversized.counters.response_bytes_received == 101
    assert len(transport.calls) == 1

    plan = _plan()
    store = MemoryEvidenceStore()
    transport = FakeTransport(plan, store)
    timed_out = _run(
        monkeypatch,
        plan,
        transport,
        store,
        monotonic_values=(0.0, 31.0),
    )
    assert timed_out.outcome is sec.SECObservationOutcome.PROVIDER_FAILED
    assert timed_out.counters.provider_invocations == 0
    assert not transport.calls


def test_elapsed_limit_after_transport_preserves_truthful_response_accounting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan()
    store = MemoryEvidenceStore()
    transport = FakeTransport(plan, store)
    result = _run(
        monkeypatch,
        plan,
        transport,
        store,
        monotonic_values=(0.0, 0.0, 0.0, 31.0),
    )
    assert result.outcome is sec.SECObservationOutcome.PROVIDER_FAILED
    assert result.reason_code == "TOTAL_TIME_LIMIT_REACHED"
    assert result.counters.provider_invocations == 1
    assert result.counters.response_documents == 1
    assert result.counters.response_bytes == len(_submission(plan))
    assert result.counters.response_bytes_received == len(_submission(plan))


def test_response_custody_digest_mismatch_is_rejected_and_counted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class WrongDigestStore(MemoryEvidenceStore):
        def write_response(
            self,
            ordinal: int,
            label: str,
            body: bytes,
            content_type: str,
            *,
            received_at: datetime | None = None,
        ) -> str:
            super().write_response(
                ordinal,
                label,
                body,
                content_type,
                received_at=received_at,
            )
            return "0" * 64

    plan = _plan()
    store = WrongDigestStore()
    transport = FakeTransport(plan, store)
    monkeypatch.setattr(sec, "_current_source_is_admitted", lambda _: True)
    result = sec._observe_sec_once_with_transport(
        plan,
        sec.SECSourceAdmission(HEAD, TREE, "PASS", "PASS", "d" * 64),
        _authorization(plan),
        transport,
        store,
        now=lambda: NOW,
    )
    assert result.outcome is sec.SECObservationOutcome.EVIDENCE_WRITE_FAILED
    assert result.reason_code == "RESPONSE_CUSTODY_DIGEST_MISMATCH"
    assert result.counters.provider_invocations == 1
    assert result.counters.response_documents == 0
    assert result.counters.response_bytes == 0
    assert result.counters.response_bytes_received == len(_submission(plan))


def test_real_path_requires_receipt_timestamp_before_response_custody(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MissingReceiptTransport(FakeTransport):
        def get(
            self,
            url: str,
            *,
            user_agent: str,
            timeout_seconds: int,
            total_time_limit_seconds: float,
            max_bytes: int,
        ) -> sec.SECTransportResponse:
            response = super().get(
                url,
                user_agent=user_agent,
                timeout_seconds=timeout_seconds,
                total_time_limit_seconds=total_time_limit_seconds,
                max_bytes=max_bytes,
            )
            return replace(response, received_at=None)

    plan = _plan()
    store = MemoryEvidenceStore()
    transport = MissingReceiptTransport(plan, store)
    monkeypatch.setattr(sec, "_current_source_is_admitted", lambda _: True)
    result = sec._observe_sec_once_with_transport(
        plan,
        sec.SECSourceAdmission(HEAD, TREE, "PASS", "PASS", "d" * 64),
        _authorization(plan),
        transport,
        store,
        now=lambda: NOW,
        require_response_receipt_timestamp=True,
    )
    assert result.outcome is sec.SECObservationOutcome.RESPONSE_REJECTED
    assert result.reason_code == "LOCAL_RESPONSE_RECEIPT_TIMESTAMP_REQUIRED"
    assert result.counters.provider_invocations == 1
    assert result.counters.response_documents == 0
    assert result.counters.response_bytes_received == len(_submission(plan))
    assert not store.responses


def test_real_path_rejects_receipt_outside_the_local_request_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FutureReceiptTransport(FakeTransport):
        def get(
            self,
            url: str,
            *,
            user_agent: str,
            timeout_seconds: int,
            total_time_limit_seconds: float,
            max_bytes: int,
        ) -> sec.SECTransportResponse:
            response = super().get(
                url,
                user_agent=user_agent,
                timeout_seconds=timeout_seconds,
                total_time_limit_seconds=total_time_limit_seconds,
                max_bytes=max_bytes,
            )
            return replace(response, received_at=NOW + timedelta(seconds=1))

    plan = _plan()
    store = MemoryEvidenceStore()
    transport = FutureReceiptTransport(plan, store)
    monkeypatch.setattr(sec, "_current_source_is_admitted", lambda _: True)
    result = sec._observe_sec_once_with_transport(
        plan,
        sec.SECSourceAdmission(HEAD, TREE, "PASS", "PASS", "d" * 64),
        _authorization(plan),
        transport,
        store,
        now=lambda: NOW,
        require_response_receipt_timestamp=True,
    )
    assert result.outcome is sec.SECObservationOutcome.RESPONSE_REJECTED
    assert (
        result.reason_code == "LOCAL_RESPONSE_RECEIPT_TIMESTAMP_OUTSIDE_REQUEST_WINDOW"
    )
    assert result.counters.provider_invocations == 1
    assert result.counters.response_bytes_received == len(_submission(plan))
    assert not store.responses


def test_plan_uses_only_the_exact_planned_sec_archive_endpoint() -> None:
    plan = _plan()
    assert plan.submission_url == (
        "https://www.sec.gov/Archives/edgar/data/1/"
        "000000000124000001/0000000001-24-000001.txt"
    )


def _admission_report(plan: sec.SECObservationPlan) -> dict[str, object]:
    state = {
        "head": plan.expected_source_head,
        "tree": plan.expected_source_tree,
        "branch": sec._EXPECTED_BRANCH,
        "porcelain": "",
    }
    return {
        "schema": "ai-trading-bot-checkpoint-runner/v1",
        "kind": "source_gate",
        "checkpoint": "arch132-r3n-prepublication-admission",
        "mode": "FULL",
        "phase": "all",
        "status": "PASS",
        "authority_checked": True,
        "authority_failures": [],
        "identity_stable": True,
        "started_from": state,
        "finished_at": state,
        "commands": [
            {"name": name, "exit_code": 0}
            for name in ("git_diff_check", "ruff_check", "ruff_format", "pytest")
        ],
        "production_effects": "NOT_RUN",
        "provider_effects": "NOT_RUN",
        "scheduler_mutation": "NOT_RUN",
        "broker_live_effects": "NOT_RUN",
    }


def _write_json(path, material: dict[str, object]) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    path.write_bytes(raw)
    return raw


def test_actual_admission_and_effect_authorization_records_are_bound(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    external_root = tmp_path / "external-temp"
    external_root.mkdir()
    monkeypatch.setattr(sec, "_EVIDENCE_ROOT", str(external_root))
    plan = _plan(
        evidence_root=str(sec.sec_observation_evidence_root()),
    )
    plan = replace(plan, attempt_id=sec.canonical_sec_attempt_id(plan))
    admission_path = external_root / "admission" / "report.json"
    admission_bytes = _write_json(admission_path, _admission_report(plan))
    admission = sec.load_sec_source_admission_record(admission_path, plan)
    assert admission.evidence_sha256 == hashlib.sha256(admission_bytes).hexdigest()

    authorization_path = external_root / "authorization" / "review.json"
    authorization_record: dict[str, object] = {
        "schema": "pm2d-b1-r-sec-effect-authorization/v1",
        "decision": "APPROVED",
        "authorization_id": "review-2026-11-28",
        "plan_id": plan.plan_id,
        "approved_source_head": plan.expected_source_head,
        "approved_source_tree": plan.expected_source_tree,
        "approved_attempt_id": str(plan.attempt_id),
        "source_admission_sha256": admission.evidence_sha256,
        "reviewed_by": "owner-review-1",
        "issued_at": (NOW - timedelta(minutes=1)).isoformat(),
        "expires_at": (NOW + timedelta(minutes=10)).isoformat(),
        "max_request_attempts": 1,
    }
    authorization_bytes = _write_json(authorization_path, authorization_record)
    authorization = sec.load_sec_effect_authorization_record(
        authorization_path, plan, admission, NOW
    )
    assert (
        authorization.review_record_sha256
        == hashlib.sha256(authorization_bytes).hexdigest()
    )
    assert authorization.source_admission_sha256 == admission.evidence_sha256

    evidence_store = sec.SECFileEvidenceStore(plan)
    assert evidence_store.reserve_attempt(plan)
    evidence_store.write_authority_evidence(admission, authorization)
    attempt_root = sec.sec_observation_evidence_root() / str(plan.attempt_id)
    assert (
        attempt_root / "authorities" / "source-admission.json"
    ).read_bytes() == admission_bytes
    assert (
        attempt_root / "authorities" / "effect-authorization.json"
    ).read_bytes() == authorization_bytes
    assert evidence_store.authority_evidence_manifest() == {
        "source_admission_evidence": {
            "path": str(admission_path),
            "sha256": admission.evidence_sha256,
        },
        "effect_authorization_evidence": {
            "authorization_id": authorization.authorization_id,
            "path": str(authorization_path),
            "sha256": authorization.review_record_sha256,
        },
    }

    authorization_record["source_admission_sha256"] = "f" * 64
    _write_json(authorization_path, authorization_record)
    with pytest.raises(sec.SECObservationError, match="does not bind"):
        sec.load_sec_effect_authorization_record(
            authorization_path, plan, admission, NOW
        )


def test_admission_record_rejects_incompatible_source_or_missing_context(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    external_root = tmp_path / "external-temp"
    external_root.mkdir()
    monkeypatch.setattr(sec, "_EVIDENCE_ROOT", str(external_root))
    plan = _plan(evidence_root=str(sec.sec_observation_evidence_root()))
    report = _admission_report(plan)
    report["started_from"] = {
        "head": "c" * 40,
        "tree": plan.expected_source_tree,
        "branch": sec._EXPECTED_BRANCH,
        "porcelain": "",
    }
    report_path = external_root / "admission" / "report.json"
    _write_json(report_path, report)
    with pytest.raises(sec.SECObservationError, match="exact clean source"):
        sec.load_sec_source_admission_record(report_path, plan)

    report = _admission_report(plan)
    del report["provider_effects"]
    _write_json(report_path, report)
    with pytest.raises(sec.SECObservationError, match="non-source effect"):
        sec.load_sec_source_admission_record(report_path, plan)


def test_production_boundary_rejects_structural_store_and_attempt_path_replay(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    external_root = tmp_path / "external-temp"
    external_root.mkdir()
    monkeypatch.setattr(sec, "_EVIDENCE_ROOT", str(external_root))
    evidence_root = str(sec.sec_observation_evidence_root())
    provisional = _plan(evidence_root=evidence_root)
    plan = replace(
        provisional,
        attempt_id=sec.canonical_sec_attempt_id(provisional),
    )
    store = sec.SECFileEvidenceStore(plan)
    assert sec.is_valid_sec_production_boundary(plan, store)
    assert not sec.is_valid_sec_production_boundary(plan, MemoryEvidenceStore())

    changed_path = replace(plan, evidence_root=str(external_root / "alternate"))
    assert sec.canonical_sec_attempt_id(changed_path) == plan.attempt_id
    with pytest.raises(ValueError, match="canonical SEC evidence root"):
        sec.SECFileEvidenceStore(changed_path)

    assert store.reserve_attempt(plan)
    assert not store.reserve_attempt(plan)
    store.write_request_intent(1, {"request": "synthetic"})
    body = _submission(plan)
    assert (
        store.write_response(1, "submission", body, "text/plain", received_at=NOW)
        == hashlib.sha256(body).hexdigest()
    )
    stored_path = (
        sec.sec_observation_evidence_root()
        / str(plan.attempt_id)
        / "responses"
        / "01-submission.bin"
    )
    assert stored_path.read_bytes() == body
    response_meta = json.loads(stored_path.with_suffix(".meta.json").read_text())
    assert response_meta["received_at"] == NOW.isoformat()
    assert (
        response_meta["receipt_semantics"] == "LOCAL_FIRST_RECEIPT_NOT_PUBLICATION_TIME"
    )


def test_external_record_path_containment_and_reparse_guards(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    external_root = tmp_path / "external-temp"
    external_root.mkdir()
    monkeypatch.setattr(sec, "_EVIDENCE_ROOT", str(external_root))
    plan = _plan(evidence_root=str(sec.sec_observation_evidence_root()))
    outside = tmp_path / "outside.json"
    _write_json(outside, _admission_report(plan))
    with pytest.raises(sec.SECObservationError, match="below F"):
        sec.load_sec_source_admission_record(outside, plan)

    reparse = external_root / "link"
    reparse.mkdir()
    original_is_symlink = sec.Path.is_symlink
    monkeypatch.setattr(
        sec.Path,
        "is_symlink",
        lambda value: value == reparse or original_is_symlink(value),
    )
    with pytest.raises(ValueError, match="reparse point"):
        sec._reject_reparse_ancestors(external_root, reparse)


def test_standard_library_read_loop_enforces_byte_and_per_read_deadline_bounds() -> (
    None
):
    class FakeSocket:
        def __init__(self) -> None:
            self.timeouts: list[float] = []

        def settimeout(self, value: float) -> None:
            self.timeouts.append(value)

    class FakeResponse:
        def __init__(self, chunks: list[bytes]) -> None:
            self.socket = FakeSocket()
            self.fp = SimpleNamespace(
                fp=SimpleNamespace(raw=SimpleNamespace(_sock=self.socket))
            )
            self.chunks = list(chunks)
            self.requested_sizes: list[int] = []

        def read(self, size: int) -> bytes:
            self.requested_sizes.append(size)
            return self.chunks.pop(0) if self.chunks else b""

    oversized = FakeResponse([b"abcd"])
    body = sec._read_sec_response_bounded(oversized, 3, 2, 5.0, monotonic=lambda: 0.0)
    assert body == b"abcd"
    assert oversized.requested_sizes == [4]
    assert oversized.socket.timeouts == [2]

    deadline_response = FakeResponse([b"a", b"b"])
    moments = iter((0.0, 2.0))
    with pytest.raises(TimeoutError):
        sec._read_sec_response_bounded(
            deadline_response,
            10,
            8,
            1.0,
            monotonic=lambda: next(moments),
        )
    assert deadline_response.socket.timeouts == [1.0]
    assert len(deadline_response.requested_sizes) == 1
