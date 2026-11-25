"""Synthetic durability and one-shot tests for the Arch151 operator."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid5

import pytest

from trading_bot.experiments import arch151_intraday_walkforward as arch151
from trading_bot.experiments import arch151_intraday_walkforward_evaluator as evaluator
from trading_bot.experiments import arch151_intraday_walkforward_operator as operator

_SOURCE_DIGEST = "a" * 64
_HEAD = "b" * 40
_TREE = "c" * 40


@dataclass(frozen=True)
class _FakeReplay:
    replay_id: UUID
    replay_digest: str
    slot: arch151.TrialSlot
    cost_case: arch151.FillCostCase
    scored_year: int
    complete: bool = True
    failure: evaluator.ReplayFailureEvidence | None = None


@dataclass(frozen=True)
class _FakeBatch:
    scored_year: int
    batch_id: UUID
    source_digest: str
    source_binding: SimpleNamespace
    manifest_id: UUID
    manifest_fingerprint: str
    evaluations: tuple[_FakeReplay, ...]
    complete: bool


def _revision() -> operator.SourceRevision:
    return operator.SourceRevision(
        operator.EXPECTED_BRANCH,
        operator.EXPECTED_ORIGIN,
        _HEAD,
        _TREE,
        _seal=operator._SOURCE_REVISION_SEAL,
    )


@pytest.fixture
def expected_worktree(monkeypatch: pytest.MonkeyPatch) -> Path:
    repo_root = Path(__file__).resolve(strict=True).parents[2]
    monkeypatch.setattr(operator, "EXPECTED_WORKTREE", repo_root)
    return repo_root


def test_source_revision_reads_exact_clean_checkout_identity(
    monkeypatch: pytest.MonkeyPatch, expected_worktree: Path
) -> None:
    outputs = iter(
        (operator.EXPECTED_BRANCH, operator.EXPECTED_ORIGIN, _HEAD, _TREE, "")
    )
    commands: list[tuple[str, ...]] = []

    def fake_git(arguments, **_kwargs):
        commands.append(tuple(arguments))
        return SimpleNamespace(returncode=0, stdout=next(outputs))

    monkeypatch.setattr(operator.subprocess, "run", fake_git)

    revision = operator._read_source_revision()

    assert revision == _revision()
    assert len(commands) == 5
    assert all(arguments[1] == "-C" for arguments in commands)
    assert all(
        Path(arguments[2]).resolve() == expected_worktree for arguments in commands
    )


def test_source_revision_rejects_incorrect_physical_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(operator, "EXPECTED_WORKTREE", tmp_path)
    monkeypatch.setattr(
        operator.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("wrong root must fail before Git"),
    )

    with pytest.raises(operator.OperatorError) as error:
        operator._read_source_revision()
    assert error.value.code is operator.OperatorFailureCode.SOURCE_IDENTITY_UNAVAILABLE


def test_source_revision_rejects_unavailable_git_identity(
    monkeypatch: pytest.MonkeyPatch, expected_worktree: Path
) -> None:
    monkeypatch.setattr(
        operator.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=128, stdout=""),
    )

    with pytest.raises(operator.OperatorError) as error:
        operator._read_source_revision()
    assert error.value.code is operator.OperatorFailureCode.SOURCE_IDENTITY_UNAVAILABLE


@pytest.mark.parametrize(
    ("changed_index", "replacement", "expected_code"),
    [
        (0, "develop", operator.OperatorFailureCode.SOURCE_BRANCH_INVALID),
        (
            1,
            "https://example.invalid/repo.git",
            operator.OperatorFailureCode.SOURCE_ORIGIN_INVALID,
        ),
        (4, " M source.py", operator.OperatorFailureCode.SOURCE_DIRTY),
    ],
)
def test_source_revision_rejects_branch_origin_or_dirty_checkout(
    monkeypatch: pytest.MonkeyPatch,
    expected_worktree: Path,
    changed_index: int,
    replacement: str,
    expected_code: operator.OperatorFailureCode,
) -> None:
    outputs = [operator.EXPECTED_BRANCH, operator.EXPECTED_ORIGIN, _HEAD, _TREE, ""]
    outputs[changed_index] = replacement
    responses = iter(outputs)
    monkeypatch.setattr(
        operator.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=next(responses)),
    )

    with pytest.raises(operator.OperatorError) as error:
        operator._read_source_revision()
    assert error.value.code is expected_code


def _failure() -> evaluator.ReplayFailureEvidence:
    return evaluator.ReplayFailureEvidence(
        UUID(int=6001),
        evaluator.ReplayFailureKind.MANDATORY_LIQUIDATION_UNOBSERVED,
        date(2023, 1, 3),
        datetime(2023, 1, 3, 20, 55, tzinfo=UTC),
        datetime(2023, 1, 3, 19, 0, tzinfo=UTC),
        None,
        Decimal("0.5"),
        Decimal("99"),
        Decimal("100"),
        Decimal("105"),
        evaluator.ExitReason.SESSION_LIQUIDATION,
        datetime(2023, 1, 3, 20, 50, tzinfo=UTC),
        _SOURCE_DIGEST,
    )


def _batch(
    year: int,
    *,
    failure: evaluator.ReplayFailureEvidence | None = None,
    incomplete: bool = False,
) -> _FakeBatch:
    records = tuple(
        _FakeReplay(
            uuid5(slot.slot_id, f"operator-test/{year}/{case.value}"),
            hashlib.sha256(f"{slot.slot_id}/{year}/{case.value}".encode()).hexdigest(),
            slot,
            case,
            year,
            complete=failure is None or ordinal != 0,
            failure=failure if ordinal == 0 else None,
        )
        for ordinal, (slot, case) in enumerate(
            (slot, case)
            for slot in arch151.CANONICAL_SLOTS
            for case in arch151.EVALUATION_ECONOMICS_ORDER
        )
    )
    if incomplete:
        records = records[:-1]
    binding = SimpleNamespace(binding_id=UUID(int=7001))
    is_complete = len(records) == 96 and failure is None
    return _FakeBatch(
        year,
        UUID(int=year),
        _SOURCE_DIGEST,
        binding,
        arch151.CANONICAL_MANIFEST.manifest_id,
        arch151.CANONICAL_MANIFEST.fingerprint,
        records,
        is_complete,
    )


def _install_synthetic_operator(monkeypatch, evidence_root: Path) -> list[int]:
    calls: list[int] = []
    monkeypatch.setattr(operator, "EVIDENCE_ROOT", evidence_root)
    monkeypatch.setattr(operator, "_read_source_revision", _revision)
    monkeypatch.setattr(
        arch151,
        "load_arch150_d1r_source_history",
        lambda: pytest.fail(
            "operator tests must not invoke the accepted source loader"
        ),
    )
    monkeypatch.setattr(
        operator,
        "_load_accepted_source_history",
        lambda: (
            SimpleNamespace(source_digest=_SOURCE_DIGEST)
            if (evidence_root / "source-revision.json").is_file()
            else pytest.fail("source identity must be persisted before source load")
        ),
    )

    def simulate(_history, year: int) -> _FakeBatch:
        calls.append(year)
        return _batch(year)

    monkeypatch.setattr(evaluator, "simulate_canonical_year", simulate)
    monkeypatch.setattr(
        evaluator,
        "compose_development_evaluation",
        lambda batches: (
            SimpleNamespace(
                run_id=UUID(int=8001),
                source_binding=SimpleNamespace(binding_id=UUID(int=7001)),
                final_freeze=SimpleNamespace(
                    status=(
                        arch151.FinalFreezeStatus.ZERO_CANDIDATES_STATISTICAL_EVIDENCE_UNAVAILABLE
                    ),
                    candidate_slot_id=None,
                ),
            )
            if tuple(item.scored_year for item in batches) == arch151.SCORED_YEARS
            else pytest.fail("operator must compose the exact five development years")
        ),
    )

    # This persistence harness deliberately uses non-domain fake outputs. The
    # sealed synthetic composition test below covers the real context checks.
    def bind_fake_run(context, run):
        context._run = run

    def bind_fake_report(context, report):
        context._report = report

    monkeypatch.setattr(
        operator._ActiveDevelopmentInvocation, "bind_run", bind_fake_run
    )
    monkeypatch.setattr(
        operator._ActiveDevelopmentInvocation, "bind_report", bind_fake_report
    )
    canonical_report = b'{"schema":"synthetic-canonical-report"}'
    monkeypatch.setattr(
        evaluator,
        "serialize_development_evaluation",
        lambda run: SimpleNamespace(
            report_id=UUID(int=8002),
            run_id=run.run_id,
            canonical_json_bytes=canonical_report,
            sha256=hashlib.sha256(canonical_report).hexdigest(),
        ),
    )

    def fake_attestation(context, run, report):
        body = json.dumps(
            {
                "attempt_id": str(context.attempt_id),
                "invocation_id": str(context.invocation_id),
                "revision_head": context.source_revision.head,
                "run_id": str(run.run_id),
                "report_id": str(report.report_id),
                "report_sha256": report.sha256,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return SimpleNamespace(
            attestation_id=UUID(int=8003),
            attestation_digest=hashlib.sha256(body).hexdigest(),
            canonical_json_bytes=body,
        )

    monkeypatch.setattr(
        operator, "_issue_development_source_attestation", fake_attestation
    )
    return calls


def test_operator_persists_exact_report_and_binds_source_and_invocation_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "arch151-evidence"
    calls = _install_synthetic_operator(monkeypatch, root)

    result = operator.run_development_evaluation_once()

    assert result.status is operator.OperatorStatus.COMPLETED
    assert result.attempt_id is not None
    assert result.invocation_id == operator._invocation_id(_revision())
    assert result.report_id == UUID(int=8002)
    report_bytes = (root / "development-report.json").read_bytes()
    assert report_bytes == b'{"schema":"synthetic-canonical-report"}'
    assert result.report_sha256 == hashlib.sha256(report_bytes).hexdigest()
    claim = json.loads((root / "attempt.json").read_text(encoding="utf-8"))
    source_revision = json.loads(
        (root / "source-revision.json").read_text(encoding="utf-8")
    )
    terminal = json.loads((root / "attempt-result.json").read_text(encoding="utf-8"))
    assert claim["invocation_id"] is None
    assert not any(key.startswith("source_") for key in claim)
    assert source_revision["source_head"] == _HEAD
    assert source_revision["source_tree"] == _TREE
    assert source_revision["invocation_id"] == str(result.invocation_id)
    assert claim["attempt_id"] == str(result.attempt_id)
    assert claim["development_start"] == "2016-01-01"
    assert claim["development_end"] == "2023-12-31"
    assert claim["automatic_retry"] == "FORBIDDEN"
    assert terminal["status"] == "COMPLETED"
    assert terminal["report_sha256"] == result.report_sha256
    assert result.source_attestation is not None
    assert result.development_evidence_handoff is None
    assert terminal["source_attestation_id"] == str(
        result.source_attestation.attestation_id
    )
    assert terminal["source_attestation_digest"] == (
        result.source_attestation.attestation_digest
    )
    assert "development_evidence_id" not in terminal
    assert (
        root / "source-attestation.json"
    ).read_bytes() == result.source_attestation.canonical_json_bytes
    assert len(terminal["year_artifacts"]) == 5
    for year in arch151.SCORED_YEARS:
        year_record = json.loads((root / f"year-{year}.json").read_text())
        assert year_record["scored_year"] == year
        assert year_record["attempt_id"] == str(result.attempt_id)
        assert year_record["invocation_id"] == str(result.invocation_id)
        assert year_record["source_head"] == _HEAD
        assert year_record["source_tree"] == _TREE
        assert year_record["observed_replay_count"] == 96
    assert calls == list(arch151.SCORED_YEARS)
    assert not (root / "replay-integrity-failures.json").exists()

    before = {path.name: path.read_bytes() for path in root.iterdir()}
    with pytest.raises(operator.OperatorError) as error:
        operator.run_development_evaluation_once()
    assert error.value.code is operator.OperatorFailureCode.EVIDENCE_ROOT_ALREADY_EXISTS
    assert {path.name: path.read_bytes() for path in root.iterdir()} == before
    assert calls == list(arch151.SCORED_YEARS)


@pytest.mark.parametrize(
    "failure_code",
    (
        operator.OperatorFailureCode.SOURCE_BRANCH_INVALID,
        operator.OperatorFailureCode.SOURCE_ORIGIN_INVALID,
        operator.OperatorFailureCode.SOURCE_DIRTY,
    ),
)
def test_source_preflight_failure_is_durable_without_source_or_evaluation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_code: operator.OperatorFailureCode,
) -> None:
    root = tmp_path / f"preflight-{failure_code.value.lower()}"
    _install_synthetic_operator(monkeypatch, root)
    source_loads: list[None] = []
    simulated_years: list[int] = []

    def reject_source_revision() -> operator.SourceRevision:
        raise operator.OperatorError(failure_code)

    def reject_source_load():
        source_loads.append(None)
        pytest.fail("source loading must not follow failed source preflight")

    def reject_simulation(_history, year: int):
        simulated_years.append(year)
        pytest.fail("simulation must not follow failed source preflight")

    monkeypatch.setattr(operator, "_read_source_revision", reject_source_revision)
    monkeypatch.setattr(operator, "_load_accepted_source_history", reject_source_load)
    monkeypatch.setattr(evaluator, "simulate_canonical_year", reject_simulation)

    result = operator.run_development_evaluation_once()

    assert result.status is operator.OperatorStatus.FAILED
    assert result.attempt_id is not None
    assert result.invocation_id is None
    assert result.report_id is None
    assert result.failure_code is failure_code
    assert result.source_attestation is None
    assert (root / "attempt.json").is_file()
    assert (root / "operator-failure.json").is_file()
    assert (root / "attempt-result.json").is_file()
    assert not (root / "source-revision.json").exists()
    assert not (root / "development-report.json").exists()
    assert not tuple(root.glob("year-*.json"))

    claim = json.loads((root / "attempt.json").read_text(encoding="utf-8"))
    failure = json.loads((root / "operator-failure.json").read_text(encoding="utf-8"))
    terminal = json.loads((root / "attempt-result.json").read_text(encoding="utf-8"))
    for record in (claim, failure, terminal):
        assert record["attempt_id"] == str(result.attempt_id)
        assert record["invocation_id"] is None
        assert not any(key.startswith("source_") for key in record)
    assert failure["failure_code"] == failure_code.value
    assert failure["year_artifacts"] == []
    assert terminal["candidate_evaluation"] == "NOT_EVALUATED"
    assert source_loads == []
    assert simulated_years == []


def test_source_attestation_issuer_rejects_bare_ids_and_operator_outcomes() -> None:
    revision = _revision()
    outcome = operator.OperatorOutcome(
        operator.OperatorStatus.COMPLETED,
        UUID(int=8201),
        operator._invocation_id(revision),
        Path("unused"),
        UUID(int=8202),
        "a" * 64,
        None,
    )
    with pytest.raises(operator.OperatorError):
        operator._issue_development_source_attestation(
            outcome,
            UUID(int=8203),
            UUID(int=8204),
        )
    assert outcome.source_attestation is None
    assert outcome.development_evidence_handoff is None
    with pytest.raises(arch151.AuthorizationUnavailableError):
        arch151.authorize_holdout(outcome)  # type: ignore[arg-type]
    with pytest.raises(operator.OperatorError):
        operator.DevelopmentEvidenceHandoff(
            authenticated_evidence=outcome,
            final_freeze=outcome,
            selection_bias_evidence=outcome,
            source_attestation=outcome,
        )
    with pytest.raises(TypeError):
        operator.DevelopmentSourceAttestation(
            attestation_id=UUID(int=8205),
            attestation_digest="b" * 64,
        )


def test_replay_integrity_failure_is_separate_and_never_becomes_report_or_idle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "arch151-replay-failure"
    _install_synthetic_operator(monkeypatch, root)
    failure_batch = _batch(arch151.SCORED_YEARS[0], failure=_failure())
    monkeypatch.setattr(
        evaluator,
        "simulate_canonical_year",
        lambda _history, _year: failure_batch,
    )

    result = operator.run_development_evaluation_once()

    assert result.status is operator.OperatorStatus.REPLAY_INTEGRITY_FAILURE
    assert result.report_id is result.report_sha256 is None
    assert result.failure_code is None
    failure_body = (root / "replay-integrity-failures.json").read_bytes()
    failure_record = json.loads(failure_body)
    terminal = json.loads((root / "attempt-result.json").read_text(encoding="utf-8"))
    assert failure_record["failures"][0]["failure"]["failure_id"] == str(
        _failure().failure_id
    )
    assert failure_record["failures"][0]["failure"]["evidence_digest"] == _SOURCE_DIGEST
    assert failure_record["candidate_evaluation"] == "NOT_EVALUATED"
    assert terminal["status"] == "REPLAY_INTEGRITY_FAILURE"
    assert terminal["candidate_evaluation"] == "NOT_EVALUATED"
    assert (
        terminal["failure_evidence_sha256"] == hashlib.sha256(failure_body).hexdigest()
    )
    assert terminal["attempted_years"] == [arch151.SCORED_YEARS[0]]
    assert not (root / "development-report.json").exists()
    assert not (root / "year-2020.json").exists()


def test_incomplete_batch_is_retained_without_zero_filling_or_later_years(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "arch151-incomplete"
    calls = _install_synthetic_operator(monkeypatch, root)
    incomplete_batch = _batch(arch151.SCORED_YEARS[0], incomplete=True)
    monkeypatch.setattr(
        evaluator,
        "simulate_canonical_year",
        lambda _history, year: calls.append(year) or incomplete_batch,
    )

    result = operator.run_development_evaluation_once()

    assert result.status is operator.OperatorStatus.INCOMPLETE
    incomplete = json.loads((root / "incomplete-evaluation.json").read_text())
    terminal = json.loads((root / "attempt-result.json").read_text())
    assert incomplete["expected_replay_count"] == 96
    assert incomplete["observed_replay_count"] == 95
    assert incomplete["candidate_evaluation"] == "NOT_EVALUATED"
    assert terminal["status"] == "INCOMPLETE"
    assert terminal["attempted_years"] == [arch151.SCORED_YEARS[0]]
    assert calls == [arch151.SCORED_YEARS[0]]
    assert not (root / "development-report.json").exists()
    assert not (root / "year-2020.json").exists()


def test_source_failure_is_sanitized_and_attempt_is_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "arch151-source-failure"
    monkeypatch.setattr(operator, "EVIDENCE_ROOT", root)
    monkeypatch.setattr(operator, "_read_source_revision", _revision)
    monkeypatch.setattr(
        operator,
        "_load_accepted_source_history",
        lambda: (_ for _ in ()).throw(
            operator.OperatorError(operator.OperatorFailureCode.SOURCE_HISTORY_INVALID)
        ),
    )

    result = operator.run_development_evaluation_once()

    assert result.status is operator.OperatorStatus.FAILED
    assert result.failure_code is operator.OperatorFailureCode.SOURCE_HISTORY_INVALID
    terminal = json.loads((root / "attempt-result.json").read_text())
    failure = json.loads((root / "operator-failure.json").read_text())
    assert terminal["status"] == "FAILED"
    assert terminal["candidate_evaluation"] == "NOT_EVALUATED"
    assert failure["failure_code"] == "SOURCE_HISTORY_INVALID"
    assert "F:\\AI" not in json.dumps(failure)
    assert not (root / "development-report.json").exists()


def test_create_only_writer_preserves_collision_and_cli_has_no_period_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "arch151-attempt"
    root.mkdir()
    artifact = root / "attempt.json"
    artifact.write_bytes(b"original evidence")
    with pytest.raises(operator.OperatorError):
        operator._write_once(artifact, b"replacement", attempt_root=root)
    assert artifact.read_bytes() == b"original evidence"

    monkeypatch.setattr(
        operator,
        "_read_source_revision",
        lambda: pytest.fail(
            "argument parsing must reject overrides before source inspection"
        ),
    )
    with pytest.raises(SystemExit) as error:
        operator.main(["--period", "2024"])
    assert error.value.code == 2
