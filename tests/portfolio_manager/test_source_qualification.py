"""Focused fake-only PM2D-B1 operator boundary tests."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from scripts.current_source_authority import AuthorityResult, PublicationContext

from trading_bot.domain import Symbol
from trading_bot.portfolio_manager import source_qualification as operator
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
    PeriodRole,
    QualificationInputError,
    QualificationOutcome,
    QualificationPlan,
    SecDocumentBinding,
    SecProvenanceWitness,
    SharadarProvenanceWitness,
)

_HEAD = "a" * 40
_TREE = "b" * 40
_CIK = "9999999999"
_ACCESSION = "9999999999-24-000001"
_MEMBER = "synthetic-annual.htm"
_TICKER = "SYN"
_PERMA_TICKER = "SYN_COMMON"
_PERIOD_START = date(2023, 1, 1)
_PERIOD_END = date(2023, 12, 31)
_OBSERVED_AT = datetime(2024, 11, 8, 12, 0, tzinfo=UTC)
_SEC_AVAILABLE = datetime(2024, 11, 1, 18, 5, tzinfo=UTC)
_SF1_AVAILABLE = datetime(2024, 11, 4, 12, 0, tzinfo=UTC)
_CUTOFF = datetime(2024, 11, 10, 0, 0, tzinfo=UTC)
_VISIBLE_UNTIL = datetime(2024, 12, 1, 0, 0, tzinfo=UTC)
_SEC_SOURCE_RECORD = "SYNTH-SEC-FACT-1"


def _plan(attempt_id: str = "1" * 32) -> QualificationPlan:
    basis = EvidenceBasis(
        "SEC_FILING",
        AdjustmentBasis.UNADJUSTED,
        data_basis="SEC_AS_REPORTED",
        reporting_basis="AS_REPORTED",
    )
    scope = ScopeSpec("security")
    period = PeriodSpec("fiscal_period", relation="annual", anchor="FY2023")
    entry = CatalogEntry(
        "v1",
        ANNUAL_REVENUE_MAPPING.pm2c_raw_key,
        "1",
        "fundamentals",
        EntryKind.RAW,
        value_spec=ValueSpec(ValueKind.DECIMAL, "currency", "USD"),
        scope=scope,
        period_basis=period,
        basis=basis,
    )
    catalog = ResearchCatalog("v1", (entry,))
    return QualificationPlan(
        attempt_id=attempt_id,
        expected_source_head=_HEAD,
        expected_source_tree=_TREE,
        issuer_cik=_CIK,
        primary_accession=_ACCESSION,
        sec_document_bindings=(SecDocumentBinding(_ACCESSION, _MEMBER),),
        sf1_table="SHARADAR/SF1",
        sf1_dimension="ARY",
        ticker=_TICKER,
        perma_ticker=_PERMA_TICKER,
        sf1_field="revenue",
        field_mapping=ANNUAL_REVENUE_MAPPING,
        catalog=catalog,
        target_entry=entry,
        target_subject=EvidenceSubject(
            symbol=Symbol(_TICKER),
            issuer_id=_CIK,
            security_id=_PERMA_TICKER,
            share_class="COMMON",
        ),
        expected_raw_basis=basis,
        expected_raw_scope=scope,
        expected_raw_period=period,
        share_class="COMMON",
        context_id="synthetic-annual-context",
        period_role=PeriodRole.ANNUAL,
        period_start=_PERIOD_START,
        period_end=_PERIOD_END,
        fiscal_year=2023,
        dimensions=(),
        provider_unit="USD",
        currency="USD",
        sec_scale=0,
        availability_cutoff=_CUTOFF,
        evidence_root=r"F:\AI\temp",
        max_sec_response_bytes=100_000,
        max_sharadar_page_bytes=100_000,
        max_sec_documents=1,
        max_sec_facts=8,
        max_sharadar_pages=2,
        max_sharadar_rows=8,
        max_provider_attempts=3,
        primary_form="10-K",
    )


def _admission(
    plan: QualificationPlan | None = None,
) -> operator.SyntheticSourceAdmission:
    plan = plan or _plan()
    feature = AuthorityResult(
        PublicationContext.FEATURE,
        plan.expected_source_head,
        plan.expected_source_tree,
        (operator.PM2D_B1_CHECKPOINT,),
        (),
    )
    prospective = AuthorityResult(
        PublicationContext.PROSPECTIVE_DEVELOP,
        plan.expected_source_head,
        plan.expected_source_tree,
        (operator.PM2D_B1_CHECKPOINT,),
        (),
    )
    declaration = operator.SyntheticSourceDeclaration(
        repository_root=str(Path(operator.__file__).resolve().parents[3]),
        branch=operator.FEATURE_BRANCH,
        origin=operator.CANONICAL_ORIGIN,
        head=plan.expected_source_head,
        tree=plan.expected_source_tree,
        clean=True,
    )
    return operator.SyntheticSourceAdmission(declaration, feature, prospective)


def _providers(
    plan: QualificationPlan,
    *,
    sec_accession: str | None = None,
    sf1_ticker: str | None = None,
    sec_source_version: str | None = None,
    sf1_next_cursor: str | None = None,
    empty_sf1: bool = False,
) -> tuple[operator.FakeSecProvider, operator.FakeSharadarProvider, bytes, bytes]:
    accession = sec_accession or plan.primary_accession
    sec_payload = {
        "issuer_cik": plan.issuer_cik,
        "accession": accession,
        "form": plan.primary_form,
        "filing_date": "2024-11-01",
        "report_period": plan.period_end.isoformat(),
        "document_name": plan.sec_document_bindings[0].document_name,
        "accepted_at": "2024-11-01T18:00:00Z",
        "facts": [
            {
                "concept": plan.field_mapping.sec_concept,
                "context_id": plan.context_id,
                "context_cik": plan.issuer_cik,
                "period_start": plan.period_start.isoformat(),
                "period_end": plan.period_end.isoformat(),
                "dimensions": [],
                "unit": plan.provider_unit,
                "currency": plan.currency,
                "scale": plan.sec_scale,
                "value": "100.25",
                "record_id": _SEC_SOURCE_RECORD,
            }
        ],
    }
    sec_bytes = _json_bytes(sec_payload)
    sec_digest = hashlib.sha256(sec_bytes).hexdigest()
    sec_locator = (
        f"synthetic-sec-member-fact:{plan.sec_document_bindings[0].document_name}:0"
    )
    sec_witness = SecProvenanceWitness(
        record_locator=sec_locator,
        response_sha256=sec_digest,
        source_version=sec_source_version or f"sec:{accession}:{sec_digest}",
        public_available_from=_SEC_AVAILABLE,
        visible_until=_VISIBLE_UNTIL,
        proof_reference="synth-sec-public-proof-1",
        source_record_id=_SEC_SOURCE_RECORD,
    )

    sf1_rows = (
        []
        if empty_sf1
        else [
            {
                "ticker": sf1_ticker or plan.ticker,
                "permaTicker": plan.perma_ticker,
                "reportperiod": plan.period_end.isoformat(),
                "datekey": "2024-11-01",
                "lastupdated": "2024-11-06",
                "fields": {plan.sf1_field: "100.25"},
            }
        ]
    )
    sf1_payload = {
        "table": plan.sf1_table,
        "dimension": plan.sf1_dimension,
        "rows": sf1_rows,
        "next_cursor": sf1_next_cursor,
    }
    sf1_bytes = _json_bytes(sf1_payload)
    sf1_digest = hashlib.sha256(sf1_bytes).hexdigest()
    sf1_witnesses = (
        (
            SharadarProvenanceWitness(
                record_locator="synthetic-sf1-page-row:0",
                response_sha256=sf1_digest,
                source_version="sf1-immutable-version-synthetic-1",
                vendor_available_from=_SF1_AVAILABLE,
                visible_until=_VISIBLE_UNTIL,
                proof_reference="synth-sf1-version-proof-1",
                sec_accession=plan.primary_accession,
                sec_record_locator=sec_locator,
                sec_response_sha256=sec_digest,
                pm2c_raw_key=plan.field_mapping.pm2c_raw_key,
                sf1_field=plan.sf1_field,
                sec_concept=plan.field_mapping.sec_concept,
                unit=plan.provider_unit,
                currency=plan.currency,
                period_role=plan.period_role,
                period_start=plan.period_start,
                period_end=plan.period_end,
                fiscal_year=plan.fiscal_year,
            ),
        )
        if sf1_rows
        else ()
    )
    sec = operator.FakeSecProvider(
        (
            operator.FakeSecDocument(
                plan.sec_document_bindings[0].document_name,
                sec_bytes,
                (sec_witness,),
            ),
        )
    )
    sharadar = operator.FakeSharadarProvider(
        (operator.FakeSharadarPage(None, sf1_bytes, sf1_witnesses),)
    )
    return sec, sharadar, sec_bytes, sf1_bytes


def _json_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _run(monkeypatch, tmp_path, plan, sec, sharadar, admission=None):
    monkeypatch.setattr(operator, "EVIDENCE_ROOT", tmp_path)
    return operator.run_fake_qualification(
        plan=plan,
        source_admission=admission or _admission(plan),
        sec_provider=sec,
        sharadar_provider=sharadar,
        observed_at=_OBSERVED_AT,
    )


def test_exact_fake_candidate_is_custodied_with_truthful_zero_effect_counts(
    monkeypatch, tmp_path
) -> None:
    plan = _plan()
    sec, sharadar, sec_bytes, sf1_bytes = _providers(plan)

    result = _run(monkeypatch, tmp_path, plan, sec, sharadar)

    assert result.status is operator.OperatorStatus.QUALIFIED_CANDIDATE
    assert result.qualification is not None
    assert result.qualification.outcome is QualificationOutcome.QUALIFIED_CANDIDATE
    assert result.qualification.to_source_fact().outcome.status.value == "AVAILABLE"
    counts = result.counters
    assert counts.source_admission_attempts == 1
    assert counts.sec_provider_attempts == counts.sharadar_provider_attempts == 1
    assert counts.sec_documents_received == counts.sharadar_pages_received == 1
    assert counts.sec_facts_inspected == counts.sharadar_rows_inspected == 1
    assert counts.custody_write_attempts == counts.custody_writes_succeeded == 2
    assert counts.comparison_attempts == 1
    assert counts.credential_read_attempts == counts.account_read_attempts == 0
    assert counts.ai_call_attempts == counts.broker_effect_attempts == 0
    assert counts.production_mutation_attempts == 0
    assert result.attempt_directory is not None
    custody = sorted((result.attempt_directory / "custody").glob("*.json"))
    assert len(custody) == 2
    assert {path.read_bytes() for path in custody} == {sec_bytes, sf1_bytes}
    terminal_text = result.terminal_manifest.read_text(encoding="utf-8")
    terminal = json.loads(terminal_text)
    assert terminal["source_admission"]["kind"] == "SYNTHETIC_FIXTURE_ONLY"
    assert terminal["source_admission"]["authority_grant"] == "NONE"
    assert terminal["qualification"]["outcome"] == "QUALIFIED_CANDIDATE"
    assert (
        terminal["qualification"]["sec_source_channel"] == "SEC_PUBLIC_ARCHIVE_WITNESS"
    )
    assert "https://" not in terminal_text
    assert "100.25" not in terminal_text
    assert (result.attempt_directory / "calls" / "sec-001.json").exists()
    assert (result.attempt_directory / "calls" / "sharadar-002.json").exists()

    terminal_bytes = result.terminal_manifest.read_bytes()
    repeated = operator.run_fake_qualification(
        plan=plan,
        source_admission=_admission(plan),
        sec_provider=sec,
        sharadar_provider=sharadar,
        observed_at=_OBSERVED_AT,
    )
    assert repeated.status is operator.OperatorStatus.ATTEMPT_ALREADY_CONSUMED
    assert repeated.counters.provider_attempts == 0
    assert result.terminal_manifest.read_bytes() == terminal_bytes


def test_source_mismatch_stops_before_provider_attempts(monkeypatch, tmp_path) -> None:
    plan = _plan()
    sec, sharadar, _, _ = _providers(plan)
    bad = _admission(plan)
    bad_feature = AuthorityResult(
        PublicationContext.FEATURE,
        "c" * 40,
        plan.expected_source_tree,
        (operator.PM2D_B1_CHECKPOINT,),
        (),
    )
    bad = operator.SyntheticSourceAdmission(
        bad.declaration, bad_feature, bad.prospective_develop
    )

    result = _run(monkeypatch, tmp_path, plan, sec, sharadar, admission=bad)

    assert result.status is operator.OperatorStatus.SOURCE_ADMISSION_FAILED
    assert result.counters.source_admission_attempts == 1
    assert result.counters.provider_attempts == 0
    assert result.counters.credential_read_attempts == 0
    assert result.attempt_directory is not None
    assert list((result.attempt_directory / "calls").iterdir()) == []
    assert result.terminal_manifest is not None


@pytest.mark.parametrize(
    "rejected_context",
    [PublicationContext.FEATURE, PublicationContext.PROSPECTIVE_DEVELOP],
)
def test_b1_checkpoint_must_be_named_in_each_context_before_fake_providers(
    monkeypatch, tmp_path, rejected_context
) -> None:
    plan = _plan()
    sec, sharadar, _, _ = _providers(plan)
    admission = _admission(plan)
    rejected = AuthorityResult(
        rejected_context,
        plan.expected_source_head,
        plan.expected_source_tree,
        ("arch152-portfolio-manager-foundation",),
        (),
    )
    if rejected_context is PublicationContext.FEATURE:
        admission = replace(admission, feature=rejected)
    else:
        admission = replace(admission, prospective_develop=rejected)

    result = _run(monkeypatch, tmp_path, plan, sec, sharadar, admission=admission)

    assert result.status is operator.OperatorStatus.SOURCE_ADMISSION_FAILED
    assert result.counters.source_admission_attempts == 1
    assert result.counters.provider_attempts == 0
    assert result.counters.sec_provider_attempts == 0
    assert result.counters.sharadar_provider_attempts == 0
    assert result.counters.credential_read_attempts == 0
    assert result.attempt_directory is not None
    assert list((result.attempt_directory / "calls").iterdir()) == []
    assert result.terminal_manifest is not None


def test_provider_exception_is_counted_and_raw_exception_text_is_discarded(
    monkeypatch, tmp_path
) -> None:
    plan = _plan()
    sec, sharadar, sec_bytes, _ = _providers(plan)

    def fail_after_intent(self, document_name: str):
        raise RuntimeError("private https://user:secret@example.invalid/token")

    monkeypatch.setattr(operator.FakeSecProvider, "document", fail_after_intent)
    result = _run(monkeypatch, tmp_path, plan, sec, sharadar)

    assert result.status is operator.OperatorStatus.PROVIDER_FAILURE
    assert result.reason == "SEC_PROVIDER_FAILURE"
    assert result.counters.sec_provider_attempts == 1
    assert result.counters.sec_documents_received == 0
    assert result.counters.custody_write_attempts == 0
    assert result.terminal_manifest is not None
    terminal_text = result.terminal_manifest.read_text(encoding="utf-8")
    assert "private" not in terminal_text
    assert "secret" not in terminal_text
    assert "example.invalid" not in terminal_text
    assert not any(
        sec_bytes in path.read_bytes()
        for path in result.attempt_directory.rglob("*.json")
    )
    assert (result.attempt_directory / "calls" / "sec-001.json").exists()


def test_wrong_accession_and_wrong_sf1_subject_are_not_custodied(
    monkeypatch, tmp_path
) -> None:
    plan = _plan()
    wrong_sec, sharadar, _, sf1_bytes = _providers(
        plan, sec_accession="9999999999-24-000002"
    )
    wrong_sec_root = tmp_path / "wrong-sec"
    wrong_sec_root.mkdir()
    sec_result = _run(monkeypatch, wrong_sec_root, plan, wrong_sec, sharadar)
    assert sec_result.status is operator.OperatorStatus.SEC_RESPONSE_INVALID
    assert sec_result.reason == "SEC_MEMBER_ACCESSION_MISMATCH"
    assert sec_result.counters.sec_provider_attempts == 1
    assert sec_result.counters.sec_facts_inspected == 1
    assert sec_result.counters.custody_write_attempts == 0
    assert list((sec_result.attempt_directory / "custody").iterdir()) == []

    plan2 = _plan("2" * 32)
    sec2, wrong_sharadar, sec_bytes, _ = _providers(plan2, sf1_ticker="OTHER")
    wrong_sf1_root = tmp_path / "wrong-sf1"
    wrong_sf1_root.mkdir()
    sf1_result = _run(
        monkeypatch,
        wrong_sf1_root,
        plan2,
        sec2,
        wrong_sharadar,
    )
    assert sf1_result.status is operator.OperatorStatus.SHARADAR_RESPONSE_INVALID
    assert sf1_result.reason == "SHARADAR_SUBJECT_OR_PERIOD_OUTSIDE_PLAN"
    assert sf1_result.counters.sharadar_provider_attempts == 1
    assert sf1_result.counters.sharadar_rows_inspected == 1
    assert sf1_result.counters.custody_writes_succeeded == 1
    assert {
        path.read_bytes()
        for path in (sf1_result.attempt_directory / "custody").glob("*.json")
    } == {sec_bytes}
    assert sf1_bytes not in {
        path.read_bytes()
        for path in (sf1_result.attempt_directory / "custody").glob("*.json")
    }


def test_custody_failure_keeps_parse_and_write_attempt_counts_without_candidate(
    monkeypatch, tmp_path
) -> None:
    plan = _plan()
    sec, sharadar, _, _ = _providers(plan)
    original = operator._write_bytes_once

    def fail_custody(path: Path, body: bytes, *, evidence_root: Path) -> None:
        if path.parent.name == "custody":
            raise OSError("private custody detail")
        original(path, body, evidence_root=evidence_root)

    monkeypatch.setattr(operator, "_write_bytes_once", fail_custody)
    result = _run(monkeypatch, tmp_path, plan, sec, sharadar)

    assert result.status is operator.OperatorStatus.EVIDENCE_WRITE_FAILED
    assert result.reason == "SEC_CUSTODY_WRITE_FAILED"
    assert result.qualification is None
    assert result.counters.sec_provider_attempts == 1
    assert result.counters.sec_facts_inspected == 1
    assert result.counters.custody_write_attempts == 1
    assert result.counters.custody_writes_succeeded == 0
    assert result.counters.sharadar_provider_attempts == 0
    assert result.terminal_manifest is not None
    terminal = json.loads(result.terminal_manifest.read_text(encoding="utf-8"))
    assert terminal["counters"]["sec_facts_inspected"] == 1
    assert terminal["counters"]["custody_write_attempts"] == 1
    assert terminal["counters"]["custody_writes_succeeded"] == 0


def test_typed_comparison_failure_is_preserved_without_pm2c_candidate(
    monkeypatch, tmp_path
) -> None:
    plan = _plan()
    sec, sharadar, _, _ = _providers(plan, sec_source_version="sec:unproven-version")

    result = _run(monkeypatch, tmp_path, plan, sec, sharadar)

    assert result.status is operator.OperatorStatus.COMPARISON_FAILED
    assert result.qualification is not None
    assert result.qualification.outcome is QualificationOutcome.SOURCE_VERSION_UNPROVEN
    with pytest.raises(QualificationInputError):
        result.qualification.to_source_fact()
    terminal = json.loads(result.terminal_manifest.read_text(encoding="utf-8"))
    assert terminal["qualification"]["outcome"] == "SOURCE_VERSION_UNPROVEN"
    assert terminal["qualification"]["source_identity"] is None


def test_terminal_empty_sf1_page_is_received_and_compared_as_missing_row(
    monkeypatch, tmp_path
) -> None:
    plan = _plan()
    sec, sharadar, _, _ = _providers(plan, empty_sf1=True)

    result = _run(monkeypatch, tmp_path, plan, sec, sharadar)

    assert result.status is operator.OperatorStatus.COMPARISON_FAILED
    assert result.qualification is not None
    assert result.qualification.outcome is QualificationOutcome.SHARADAR_ROW_MISSING
    assert result.counters.sharadar_provider_attempts == 1
    assert result.counters.sharadar_pages_received == 1
    assert result.counters.sharadar_rows_inspected == 0
    terminal = json.loads(result.terminal_manifest.read_text(encoding="utf-8"))
    assert terminal["response_events"][-1]["pagination_terminal"] is True
    assert terminal["response_events"][-1]["record_count"] == 0
    assert len(list((result.attempt_directory / "custody").glob("*.json"))) == 2


def test_page_limit_stops_before_second_page_call(monkeypatch, tmp_path) -> None:
    plan = replace(_plan(), max_sharadar_pages=1, max_provider_attempts=2)
    sec, first_page_provider, _, first_bytes = _providers(plan, sf1_next_cursor="next")
    # The second page is already inert in memory. The operator must enforce
    # the plan cap before consuming its exact cursor seam.
    second_page = operator.FakeSharadarPage("next", first_bytes, ())
    sharadar = operator.FakeSharadarProvider((*first_page_provider.pages, second_page))

    result = _run(monkeypatch, tmp_path, plan, sec, sharadar)

    assert result.status is operator.OperatorStatus.PAGE_LIMIT_REACHED
    assert result.reason == "PAGE_LIMIT_REACHED"
    assert result.qualification is None
    assert result.counters.sec_provider_attempts == 1
    assert result.counters.sharadar_provider_attempts == 1
    assert result.counters.provider_attempts == 2
    assert result.counters.sec_documents_received == 1
    assert result.counters.sharadar_pages_received == 1
    assert sorted(
        path.name for path in (result.attempt_directory / "calls").glob("*.json")
    ) == [
        "sec-001.json",
        "sharadar-002.json",
    ]


def test_attempt_limit_stops_before_next_preloaded_page_call(
    monkeypatch, tmp_path
) -> None:
    plan = replace(_plan(), max_provider_attempts=2)
    sec, first_page_provider, _, first_bytes = _providers(plan, sf1_next_cursor="next")
    second_page = operator.FakeSharadarPage("next", first_bytes, ())
    sharadar = operator.FakeSharadarProvider((*first_page_provider.pages, second_page))

    result = _run(monkeypatch, tmp_path, plan, sec, sharadar)

    assert result.status is operator.OperatorStatus.ATTEMPT_LIMIT_REACHED
    assert result.reason == "ATTEMPT_LIMIT_REACHED"
    assert result.qualification is None
    assert result.counters.sec_provider_attempts == 1
    assert result.counters.sharadar_provider_attempts == 1
    assert result.counters.provider_attempts == 2
    assert result.counters.sec_documents_received == 1
    assert result.counters.sharadar_pages_received == 1
    assert sorted(
        path.name for path in (result.attempt_directory / "calls").glob("*.json")
    ) == [
        "sec-001.json",
        "sharadar-002.json",
    ]


def test_structurally_compatible_non_fake_provider_is_rejected(
    monkeypatch, tmp_path
) -> None:
    plan = _plan()
    sec, sharadar, _, _ = _providers(plan)

    @dataclass(frozen=True)
    class StructuralProvider:
        documents: tuple[object, ...]
        calls: list[str]

        def document(self, document_name: str) -> object:
            self.calls.append(document_name)
            return sec.documents[0]

    structural = StructuralProvider(sec.documents, [])
    result = _run(monkeypatch, tmp_path, plan, structural, sharadar)

    assert result.status is operator.OperatorStatus.FAKE_BOUNDARY_REJECTED
    assert structural.calls == []
    assert result.counters.provider_attempts == 0
