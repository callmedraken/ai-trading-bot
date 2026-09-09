"""Focused source-only tests for the PD2D2-B one-shot execution harness."""

from __future__ import annotations

import ast
import json
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

import trading_bot.cli.pd2d2_first_paper_execution as harness
from trading_bot.cli.paper_operation_execution import (
    PaperOperationExecutionClassification,
)
from trading_bot.domain import Symbol
from trading_bot.execution import PaperFillPolicy
from trading_bot.market_calendar import TradingSession
from trading_bot.portfolio import PortfolioConstraints
from trading_bot.rebalancing import RebalanceAssumptions, RebalanceProposalPolicy
from trading_bot.risk import PortfolioRiskPolicy, RiskLimits
from trading_bot.runtime import (
    personal_desktop_paper_account_security as paper_security,
)
from trading_bot.runtime import (
    personal_desktop_supervised_paper_operation_execution as execution_boundary,
)
from trading_bot.runtime.personal_desktop_supervised_paper_operation_execution import (  # noqa: E501
    SupervisedPaperOperationExecutionResult,
)

_SECRET_TEXT = (
    r"token=private-token F:\private\operation-root handle=0xDEADBEEF sid=secret"
)
_CYCLE_RESULT_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
_SUCCESSOR_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


class _FakeSeed:
    def __init__(self) -> None:
        self.seed = SimpleNamespace(
            seed_id=harness._EXPECTED_SEED_ID,
            symbol=Symbol("SPY"),
        )
        self.target_session = TradingSession(date(2026, 8, 28))
        self.strategy_config = harness._frozen_strategy_config()
        self.artifact_sha256 = harness._EXPECTED_SEED_SHA256
        self.artifact_byte_length = harness._EXPECTED_SEED_BYTE_LENGTH


class _FakeSelectedSnapshot:
    def __init__(self, payload: bytes) -> None:
        symbol = Symbol("SPY")
        self.audit = SimpleNamespace(
            selection_id=harness._EXPECTED_SELECTION_ID,
            snapshot_id=harness._EXPECTED_SELECTED_SNAPSHOT_ID,
            artifact_sha256=sha256(payload).hexdigest(),
            artifact_byte_length=len(payload),
        )
        self.snapshot_bytes = payload
        self.verification = SimpleNamespace(
            snapshot=SimpleNamespace(
                snapshot_id=harness._EXPECTED_SELECTED_SNAPSHOT_ID,
                target_session=TradingSession(date(2026, 8, 28)),
                request=SimpleNamespace(symbols=(symbol,)),
                bars=(SimpleNamespace(bar=SimpleNamespace(symbol=symbol)),),
            )
        )
        self.provider_call_performed = False
        self.database_mutation_performed = False


def _result(
    classification: PaperOperationExecutionClassification = (
        PaperOperationExecutionClassification.COMPLETED
    ),
    *,
    diagnostic: str = "COMPLETED",
    operation_id: UUID = harness._EXPECTED_OPERATION_ID,
    application_id: UUID = harness._EXPECTED_APPLICATION_ID,
    cycle_result_id: UUID | None = _CYCLE_RESULT_ID,
    successor_checkpoint_id: UUID | None = _SUCCESSOR_ID,
    transition_evidence_produced: bool = True,
    receipt_evidence_produced: bool = True,
) -> SupervisedPaperOperationExecutionResult:
    return SupervisedPaperOperationExecutionResult(
        operation_id=operation_id,
        application_id=application_id,
        execution_classification=classification,
        diagnostic_code=diagnostic,
        cycle_result_id=cycle_result_id,
        successor_checkpoint_id=successor_checkpoint_id,
        transition_evidence_produced=transition_evidence_produced,
        receipt_evidence_produced=receipt_evidence_produced,
        executor_called=True,
    )


def _corrupt(
    result: SupervisedPaperOperationExecutionResult,
    field: str,
    value: object,
) -> SupervisedPaperOperationExecutionResult:
    object.__setattr__(result, field, value)
    return result


def _run_private(
    monkeypatch: pytest.MonkeyPatch,
    *,
    publication_preflight=None,  # type: ignore[no-untyped-def]
    history_seed_loader=None,  # type: ignore[no-untyped-def]
    authority_loader=None,  # type: ignore[no-untyped-def]
    selected_reader_factory=None,  # type: ignore[no-untyped-def]
    supervised_executor=None,  # type: ignore[no-untyped-def]
) -> tuple[int, dict[str, object]]:
    payload = b"s" * harness._EXPECTED_SELECTED_BYTE_LENGTH
    selected = _FakeSelectedSnapshot(payload)
    monkeypatch.setattr(
        harness,
        "_EXPECTED_SELECTED_SHA256",
        sha256(payload).hexdigest(),
    )
    authority = SimpleNamespace(
        machine_authority_id=harness._EXPECTED_MACHINE_AUTHORITY_ID,
        authority_epoch_id=harness._EXPECTED_AUTHORITY_EPOCH_ID,
        approved_account_sid=harness._EXPECTED_TRADING_SID,
    )
    calls: dict[str, object] = {
        "publication": 0,
        "seed": 0,
        "authority": 0,
        "reader_authority": [],
        "read": [],
        "execution": [],
    }

    def publication() -> None:
        calls["publication"] = int(calls["publication"]) + 1

    def seed_loader() -> object:
        calls["seed"] = int(calls["seed"]) + 1
        return _FakeSeed()

    def acquire() -> object:
        calls["authority"] = int(calls["authority"]) + 1
        return authority

    class Reader:
        def __init__(self, candidate: object) -> None:
            cast = calls["reader_authority"]
            assert isinstance(cast, list)
            cast.append(candidate)

        def read_selected_snapshot(self, *args: object, **kwargs: object) -> object:
            cast = calls["read"]
            assert isinstance(cast, list)
            cast.append((args, kwargs))
            return selected

    def execute(*args: object, **kwargs: object) -> object:
        cast = calls["execution"]
        assert isinstance(cast, list)
        cast.append((args, kwargs))
        return _result()

    exit_code = harness._run_after_gate_preflight_for_test(
        authority=(
            harness._open_disposable_first_paper_execution_harness_authority_for_test()
        ),
        publication_preflight=publication_preflight or publication,
        history_seed_loader=history_seed_loader or seed_loader,
        authority_loader=authority_loader or acquire,
        selected_reader_factory=selected_reader_factory or Reader,
        supervised_executor=supervised_executor or execute,
    )
    return exit_code, calls


def _json_output(capsys: pytest.CaptureFixture[str]) -> tuple[object, object]:
    captured = capsys.readouterr()
    stdout = json.loads(captured.out) if captured.out else None
    stderr = json.loads(captured.err) if captured.err else None
    return stdout, stderr


def test_frozen_identity_constants_are_exact() -> None:
    assert harness._EXPECTED_PAPER_ACCOUNT_ID == (
        "9415cd7b-bf36-5fba-bd58-a0f99119dc21"
    )
    assert harness._EXPECTED_TERMINAL_CHECKPOINT_ID == UUID(
        "1832a2b5-8b63-501a-8f7d-f1722c32307b"
    )
    assert harness._EXPECTED_SELECTION_ID == UUID(
        "36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280"
    )
    assert harness._EXPECTED_SELECTED_SNAPSHOT_ID == UUID(
        "eba46838-44ae-5bec-97bf-98c6639ae6a7"
    )
    assert harness._EXPECTED_SELECTED_SHA256 == (
        "31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d"
    )
    assert harness._EXPECTED_SELECTED_BYTE_LENGTH == 1291
    assert harness._EXPECTED_SEED_ID == UUID("5dc95e10-ba22-5b91-94b2-0d851aa8e2d7")
    assert harness._EXPECTED_SEED_SHA256 == (
        "40dda54c82324f358d640cce89e467295b8f5b73a32fed76c52e7ca90d398e64"
    )
    assert harness._EXPECTED_SEED_BYTE_LENGTH == 1060
    assert harness._EXPECTED_CALLER_IDEMPOTENCY_KEY == UUID(
        "c762ad22-8d10-43d7-a38b-7d95e730c5ea"
    )
    assert harness._EXPECTED_REQUEST_ID == UUID("bc0c3aa7-09a0-5534-83bf-0acdf649a2a0")
    assert harness._EXPECTED_PLAN_ID == UUID("78292abe-6d6c-5ddf-8ffb-46eb8a914fdb")
    assert harness._EXPECTED_PLAN_SHA256 == (
        "7f62c90df051f5c4998cc3303b7a97dfb80294dfd743662c2f9930422cb83666"
    )
    assert harness._EXPECTED_PLAN_BYTE_LENGTH == 6199
    assert harness._EXPECTED_OPERATION_ID == UUID(
        "307f769a-f09a-539d-b12d-3fb51b973809"
    )
    assert harness._EXPECTED_APPLICATION_ID == UUID(
        "78a1bae8-51ac-5bf0-b159-500768c758fc"
    )
    assert harness._EXPECTED_PUBLICATION_FREEZE_BLOB == (
        "b125cbb1c80a827f74018cf2955b9a27ba69fa90"
    )


def test_frozen_inputs_are_exact() -> None:
    seed = _FakeSeed()
    inputs = harness._frozen_inputs(seed)  # type: ignore[arg-type]
    assert inputs.history_seed is seed
    assert inputs.strategy_config.short_window == 3
    assert inputs.strategy_config.long_window == 5
    assert inputs.strategy_config.desired_quantity == Decimal("1")
    assert inputs.caller_idempotency_key == harness._EXPECTED_CALLER_IDEMPOTENCY_KEY
    assert inputs.planning_at == datetime(2026, 8, 29, 9, 46, 43, 769105, tzinfo=UTC)
    assert inputs.submitted_at == datetime(2026, 8, 31, 13, 30, tzinfo=UTC)
    assert inputs.filled_at == datetime(2026, 8, 31, 13, 30, tzinfo=UTC)
    assert inputs.open_reference.symbol == Symbol("SPY")
    assert inputs.open_reference.session == TradingSession(date(2026, 8, 31))
    assert inputs.open_reference.caller_asserted_open_reference_price == Decimal(
        "767.33"
    )
    policies = inputs.policies
    assert policies.rebalance_assumptions == RebalanceAssumptions(
        fixed_commission=Decimal("0"),
        allow_fractional_quantities=False,
        quantity_increment=Decimal("1"),
        minimum_trade_notional=Decimal("0"),
        minimum_trade_quantity=Decimal("1"),
        target_weight_tolerance=Decimal("0"),
        additional_execution_cash_buffer=Decimal("0"),
        use_planned_sell_proceeds=False,
    )
    assert policies.portfolio_constraints == PortfolioConstraints(
        minimum_cash_weight=Decimal("0.90"),
        maximum_cash_weight=Decimal("1"),
        maximum_position_weight=Decimal("0.10"),
        maximum_one_way_rebalance_turnover=Decimal("0.10"),
        minimum_position_weight=None,
        long_only=True,
        allow_leverage=False,
    )
    assert policies.proposal_policy == RebalanceProposalPolicy(
        allow_partial_plans=False
    )
    assert policies.proposal_confidence is None
    assert policies.risk_limits == RiskLimits(
        max_position_percent=Decimal("0.10"),
        max_total_exposure_percent=Decimal("0.10"),
        max_order_notional=Decimal("2500"),
        max_new_position_percent=Decimal("0.10"),
        minimum_cash_reserve_percent=Decimal("0.90"),
        allow_fractional_shares=False,
        fractional_increment=Decimal("1"),
        allow_buying=True,
        allow_selling=True,
        estimated_commission=Decimal("0"),
    )
    assert policies.risk_policy == PortfolioRiskPolicy(
        allow_sell_proceeds_for_later_buys=False
    )
    assert policies.fill_policy == PaperFillPolicy(
        slippage_basis_points=Decimal("0"), fixed_commission=Decimal("0")
    )
    assert policies.trading_enabled is True


def test_public_parser_rejects_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    assert harness.main(["--operation-id", str(harness._EXPECTED_OPERATION_ID)]) == (
        harness._EXIT_INVALID_ARGUMENTS
    )
    stdout, stderr = _json_output(capsys)
    assert stdout is None
    assert stderr == {"reason": "INVALID_ARGUMENTS", "schema": harness._SCHEMA}


def test_public_parser_has_zero_semantic_options() -> None:
    parser = harness.build_parser()
    assert [action.dest for action in parser._actions] == ["help"]


def test_current_source_gate_stops_public_main_before_any_downstream_stage(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        execution_boundary.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED
        is False
    )

    def forbidden(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("downstream stage must not run")

    monkeypatch.setattr(harness, "_require_frozen_publication", forbidden)
    monkeypatch.setattr(harness, "_load_frozen_history_seed", forbidden)
    monkeypatch.setattr(harness, "acquire_validated_production_authority", forbidden)
    monkeypatch.setattr(harness, "WindowsSelectedC3SnapshotReadAuthority", forbidden)
    monkeypatch.setattr(
        harness, "execute_supervised_personal_desktop_paper_operation", forbidden
    )
    assert harness.main([]) == harness._EXIT_SUPERVISED_EXECUTION_GATE_DISABLED
    stdout, stderr = _json_output(capsys)
    assert stdout is None
    assert stderr == {
        "reason": "SUPERVISED_EXECUTION_GATE_DISABLED",
        "schema": harness._SCHEMA,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED", True),
        ("PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED", True),
    ),
)
def test_public_main_rejects_publisher_or_recovery_gate_mismatch_before_c1(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    field: str,
    value: bool,
) -> None:
    monkeypatch.setattr(paper_security, field, value)
    monkeypatch.setattr(
        harness,
        "acquire_validated_production_authority",
        lambda: pytest.fail("C1 must not run"),
    )
    assert harness.main([]) == harness._EXIT_EFFECT_GATE_STATE_INVALID
    assert _json_output(capsys) == (
        None,
        {"reason": "EFFECT_GATE_STATE_INVALID", "schema": harness._SCHEMA},
    )


def test_publication_failure_stops_before_seed_and_c1(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = {"seed": 0, "c1": 0}

    def publication() -> None:
        raise ValueError(_SECRET_TEXT)

    def seed() -> object:
        calls["seed"] += 1
        return _FakeSeed()

    def c1() -> object:
        calls["c1"] += 1
        return object()

    exit_code, _ = _run_private(
        monkeypatch,
        publication_preflight=publication,
        history_seed_loader=seed,
        authority_loader=c1,
    )
    assert exit_code == harness._EXIT_PREFLIGHT_BLOCKED
    assert calls == {"seed": 0, "c1": 0}
    assert _json_output(capsys) == (
        None,
        {"reason": "PREFLIGHT_BLOCKED", "schema": harness._SCHEMA},
    )


def test_seed_failure_stops_before_c1(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = {"c1": 0}

    def seed() -> object:
        raise ValueError(_SECRET_TEXT)

    def c1() -> object:
        calls["c1"] += 1
        return object()

    exit_code, _ = _run_private(
        monkeypatch,
        history_seed_loader=seed,
        authority_loader=c1,
    )
    assert exit_code == harness._EXIT_PREFLIGHT_BLOCKED
    assert calls["c1"] == 0
    assert _SECRET_TEXT not in capsys.readouterr().err


def test_c1_failure_stops_before_p2(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reads = {"reader": 0}

    def c1() -> object:
        raise RuntimeError(_SECRET_TEXT)

    def reader(authority: object) -> object:
        del authority
        reads["reader"] += 1
        return object()

    exit_code, _ = _run_private(
        monkeypatch,
        authority_loader=c1,
        selected_reader_factory=reader,
    )
    assert exit_code == harness._EXIT_PRODUCTION_AUTHORITY_BLOCKED
    assert reads["reader"] == 0
    assert _SECRET_TEXT not in capsys.readouterr().err


def test_c1_identity_mismatch_stops_before_p2(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    wrong = SimpleNamespace(
        machine_authority_id="00000000-0000-0000-0000-000000000000",
        authority_epoch_id=harness._EXPECTED_AUTHORITY_EPOCH_ID,
        approved_account_sid=harness._EXPECTED_TRADING_SID,
    )
    exit_code, calls = _run_private(monkeypatch, authority_loader=lambda: wrong)
    assert exit_code == harness._EXIT_AUTHORITY_IDENTITY_MISMATCH
    assert calls["reader_authority"] == []
    assert _json_output(capsys)[1] == {
        "reason": "AUTHORITY_IDENTITY_MISMATCH",
        "schema": harness._SCHEMA,
    }


def test_p2_failure_stops_before_execution(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class Reader:
        def __init__(self, authority: object) -> None:
            del authority

        def read_selected_snapshot(self, selection_id: str) -> object:
            del selection_id
            raise RuntimeError(_SECRET_TEXT)

    exit_code, calls = _run_private(monkeypatch, selected_reader_factory=Reader)
    assert exit_code == harness._EXIT_SELECTED_SNAPSHOT_BLOCKED
    assert calls["execution"] == []
    assert _SECRET_TEXT not in capsys.readouterr().err


def test_selected_snapshot_mismatch_stops_before_execution(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = b"s" * harness._EXPECTED_SELECTED_BYTE_LENGTH
    wrong = _FakeSelectedSnapshot(payload)
    wrong.audit.selection_id = UUID("00000000-0000-0000-0000-000000000000")

    class Reader:
        def __init__(self, authority: object) -> None:
            del authority

        def read_selected_snapshot(self, selection_id: str) -> object:
            del selection_id
            return wrong

    exit_code, calls = _run_private(monkeypatch, selected_reader_factory=Reader)
    assert exit_code == harness._EXIT_SELECTED_SNAPSHOT_MISMATCH
    assert calls["execution"] == []
    assert _json_output(capsys)[1] == {
        "reason": "SELECTED_SNAPSHOT_MISMATCH",
        "schema": harness._SCHEMA,
    }


def test_private_seam_passes_same_authority_to_p2_and_execution_and_no_path(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code, calls = _run_private(monkeypatch)
    assert exit_code == 0
    reader_authorities = calls["reader_authority"]
    executions = calls["execution"]
    reads = calls["read"]
    assert isinstance(reader_authorities, list)
    assert isinstance(executions, list)
    assert isinstance(reads, list)
    assert len(reader_authorities) == len(executions) == len(reads) == 1
    args, kwargs = executions[0]
    assert args[0] is reader_authorities[0]
    assert reads == [((str(harness._EXPECTED_SELECTION_ID),), {})]
    assert "artifact_path" not in kwargs
    _json_output(capsys)


def test_private_seam_forwards_exact_frozen_inputs_once(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code, calls = _run_private(monkeypatch)
    assert exit_code == 0
    executions = calls["execution"]
    assert isinstance(executions, list) and len(executions) == 1
    _, kwargs = executions[0]
    assert kwargs["strategy_config"] == harness._frozen_strategy_config()
    assert kwargs["caller_idempotency_key"] == harness._EXPECTED_CALLER_IDEMPOTENCY_KEY
    assert kwargs["planning_at"] == harness._EXPECTED_GENESIS_AS_OF
    assert kwargs["submitted_at"] == datetime(2026, 8, 31, 13, 30, tzinfo=UTC)
    assert kwargs["filled_at"] == datetime(2026, 8, 31, 13, 30, tzinfo=UTC)
    assert kwargs["metadata"] == ()
    assert kwargs["historical_cycle_configuration_payloads"] == ()
    assert kwargs["history_seed"].seed.seed_id == harness._EXPECTED_SEED_ID
    _json_output(capsys)


def test_private_authority_rejects_forgery_and_reuse(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(TypeError, match="test issuer"):
        harness._DisposableFirstPaperExecutionHarnessAuthorityForTest()
    forged = object.__new__(
        harness._DisposableFirstPaperExecutionHarnessAuthorityForTest
    )
    with pytest.raises(TypeError, match="invalid"):
        harness._run_after_gate_preflight_for_test(
            authority=forged,
            publication_preflight=lambda: None,
            history_seed_loader=lambda: _FakeSeed(),  # type: ignore[arg-type]
            authority_loader=lambda: object(),
            selected_reader_factory=lambda authority: object(),  # type: ignore[arg-type,return-value]
            supervised_executor=lambda *args, **kwargs: object(),
        )

    issued = harness._open_disposable_first_paper_execution_harness_authority_for_test()

    class Reader:
        def __init__(self, authority: object) -> None:
            del authority

        def read_selected_snapshot(self, selection_id: str) -> object:
            del selection_id
            raise RuntimeError

    kwargs = {
        "authority": issued,
        "publication_preflight": lambda: None,
        "history_seed_loader": lambda: _FakeSeed(),
        "authority_loader": lambda: SimpleNamespace(
            machine_authority_id=harness._EXPECTED_MACHINE_AUTHORITY_ID,
            authority_epoch_id=harness._EXPECTED_AUTHORITY_EPOCH_ID,
            approved_account_sid=harness._EXPECTED_TRADING_SID,
        ),
        "selected_reader_factory": Reader,
        "supervised_executor": lambda *args, **values: object(),
    }
    assert harness._run_after_gate_preflight_for_test(**kwargs) == (
        harness._EXIT_SELECTED_SNAPSHOT_BLOCKED
    )
    with pytest.raises(TypeError, match="consumed"):
        harness._run_after_gate_preflight_for_test(**kwargs)
    capsys.readouterr()


def test_private_seam_rejects_genuine_production_callables() -> None:
    base = {
        "authority": (
            harness._open_disposable_first_paper_execution_harness_authority_for_test()
        ),
        "publication_preflight": lambda: None,
        "history_seed_loader": lambda: _FakeSeed(),
        "authority_loader": lambda: object(),
        "selected_reader_factory": lambda authority: object(),
        "supervised_executor": lambda *args, **kwargs: object(),
    }
    for field, value in (
        ("publication_preflight", harness._require_frozen_publication),
        ("history_seed_loader", harness._load_frozen_history_seed),
        ("authority_loader", harness.acquire_validated_production_authority),
        ("selected_reader_factory", harness.WindowsSelectedC3SnapshotReadAuthority),
        (
            "supervised_executor",
            harness.execute_supervised_personal_desktop_paper_operation,
        ),
    ):
        with pytest.raises(TypeError, match="no-effect"):
            harness._run_after_gate_preflight_for_test(**(base | {field: value}))


def test_execution_exception_is_sanitized_and_never_retried(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = {"count": 0}

    def execute(*args: object, **kwargs: object) -> object:
        del args, kwargs
        calls["count"] += 1
        raise RuntimeError(_SECRET_TEXT)

    exit_code, _ = _run_private(monkeypatch, supervised_executor=execute)
    assert exit_code == harness._EXIT_EXECUTION_BOUNDARY_EXCEPTION
    assert calls["count"] == 1
    stdout, stderr = _json_output(capsys)
    assert stdout is None
    assert stderr == {
        "exception_family": "RUNTIME_ERROR",
        "reason": "EXECUTION_BOUNDARY_EXCEPTION",
        "schema": harness._SCHEMA,
    }
    assert _SECRET_TEXT not in json.dumps(stderr)


@pytest.mark.parametrize(
    ("classification", "diagnostic", "reason", "exit_code"),
    (
        (
            PaperOperationExecutionClassification.BLOCKED,
            "OUTPUT_SAFETY_FAILURE",
            "BLOCKED",
            14,
        ),
        (
            PaperOperationExecutionClassification.CONFLICTING,
            "LINEAGE_CONFLICT",
            "CONFLICTING",
            15,
        ),
        (
            PaperOperationExecutionClassification.ALREADY_APPLIED,
            "ALREADY_APPLIED",
            "ALREADY_APPLIED",
            16,
        ),
        (
            PaperOperationExecutionClassification.EXECUTION_FAILED,
            "INSUFFICIENT_CASH",
            "EXECUTION_FAILED",
            17,
        ),
        (
            PaperOperationExecutionClassification.RECEIPT_RECOVERED,
            "RECEIPT_RECOVERED",
            "RECEIPT_RECOVERED",
            18,
        ),
    ),
)
def test_non_normal_result_has_stable_distinct_exit_and_sanitized_evidence(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    classification: PaperOperationExecutionClassification,
    diagnostic: str,
    reason: str,
    exit_code: int,
) -> None:
    def execute(*args: object, **kwargs: object) -> object:
        del args, kwargs
        return _result(classification, diagnostic=diagnostic)

    actual, _ = _run_private(monkeypatch, supervised_executor=execute)
    assert actual == exit_code
    stdout, stderr = _json_output(capsys)
    assert stdout is None
    assert stderr == {
        "diagnostic_code": diagnostic,
        "execution_classification": classification.value,
        "reason": reason,
        "schema": harness._SCHEMA,
    }


def test_non_normal_untrusted_diagnostic_is_not_echoed(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def execute(*args: object, **kwargs: object) -> object:
        del args, kwargs
        return _result(
            PaperOperationExecutionClassification.BLOCKED, diagnostic=_SECRET_TEXT
        )

    assert _run_private(monkeypatch, supervised_executor=execute)[0] == (
        harness._EXIT_BLOCKED
    )
    _, stderr = _json_output(capsys)
    assert isinstance(stderr, dict)
    assert stderr["diagnostic_code"] == "UNEXPECTED_DIAGNOSTIC"
    assert _SECRET_TEXT not in json.dumps(stderr)


def test_wrong_result_type_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code, _ = _run_private(
        monkeypatch,
        supervised_executor=lambda *args, **kwargs: object(),
    )
    assert exit_code == harness._EXIT_RESULT_TYPE_INVALID
    assert _json_output(capsys)[1]["reason"] == "RESULT_TYPE_INVALID"


@pytest.mark.parametrize(
    "result",
    (
        _result(operation_id=UUID("00000000-0000-0000-0000-000000000001")),
        _result(application_id=UUID("00000000-0000-0000-0000-000000000002")),
    ),
)
def test_wrong_result_identity_fails_without_echoing_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    result: SupervisedPaperOperationExecutionResult,
) -> None:
    exit_code, _ = _run_private(
        monkeypatch,
        supervised_executor=lambda *args, **kwargs: result,
    )
    assert exit_code == harness._EXIT_RESULT_IDENTITY_MISMATCH
    _, stderr = _json_output(capsys)
    assert stderr == {
        "reason": "RESULT_IDENTITY_MISMATCH",
        "schema": harness._SCHEMA,
    }


@pytest.mark.parametrize(
    "result",
    (
        _result(cycle_result_id=None),
        _result(successor_checkpoint_id=None),
        _result(transition_evidence_produced=False),
        _result(receipt_evidence_produced=False),
        _result(diagnostic="BLOCKED"),
        _corrupt(_result(), "executor_called", False),
    ),
)
def test_incomplete_completed_result_fails_reconciliation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    result: SupervisedPaperOperationExecutionResult,
) -> None:
    exit_code, _ = _run_private(
        monkeypatch,
        supervised_executor=lambda *args, **kwargs: result,
    )
    assert exit_code == harness._EXIT_COMPLETED_RESULT_RECONCILIATION_BLOCKED
    assert _json_output(capsys)[1]["reason"] == (
        "COMPLETED_RESULT_RECONCILIATION_BLOCKED"
    )


def test_exact_completed_result_emits_exact_success_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert _run_private(monkeypatch)[0] == 0
    stdout, stderr = _json_output(capsys)
    assert stderr is None
    assert stdout == {
        "application_id": str(harness._EXPECTED_APPLICATION_ID),
        "cycle_result_id": str(_CYCLE_RESULT_ID),
        "diagnostic_code": "COMPLETED",
        "execution_classification": "COMPLETED",
        "executor_called": True,
        "operation_id": str(harness._EXPECTED_OPERATION_ID),
        "paper_account_id": harness._EXPECTED_PAPER_ACCOUNT_ID,
        "production_effects_gate": False,
        "receipt_evidence_produced": True,
        "recovery_effects_gate": False,
        "result": "COMPLETED",
        "schema": harness._SCHEMA,
        "seed_id": str(harness._EXPECTED_SEED_ID),
        "selected_snapshot_id": str(harness._EXPECTED_SELECTED_SNAPSHOT_ID),
        "selection_id": str(harness._EXPECTED_SELECTION_ID),
        "successor_checkpoint_id": str(_SUCCESSOR_ID),
        "supervised_execution_gate": True,
        "transition_evidence_produced": True,
    }


def test_all_exit_categories_are_distinct() -> None:
    exits = {
        value for name, value in vars(harness).items() if name.startswith("_EXIT_")
    }
    assert exits == set(range(2, 20))


def test_static_source_has_only_supervised_public_execution_entrypoint() -> None:
    source_path = Path(harness.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    forbidden = {
        "execute_paper_operation_once",
        "commit_transition_directory",
        "commit_paper_operation_receipt",
    }
    assert imported.isdisjoint(forbidden)
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert calls.isdisjoint(forbidden)
    assert "execute_supervised_personal_desktop_paper_operation" in imported
    assert not any(isinstance(node, (ast.For, ast.While)) for node in ast.walk(tree))
    assert not any(
        isinstance(node, (ast.Import, ast.ImportFrom))
        and any(alias.name == "subprocess" for alias in node.names)
        for node in ast.walk(tree)
    )
    mutation_calls = {"write_bytes", "write_text", "unlink", "rename", "replace"}
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in mutation_calls
        for node in ast.walk(tree)
    )


def test_supervised_source_gate_remains_false_and_tests_do_not_toggle_it() -> None:
    assert (
        execution_boundary.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED
        is False
    )
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "setattr"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value
        == "PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED"
        for node in ast.walk(tree)
    )


def test_script_is_thin_delegate_only() -> None:
    script = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "execute_first_personal_desktop_paper_operation.py"
    )
    tree = ast.parse(script.read_text(encoding="utf-8"))
    imports = [node for node in tree.body if isinstance(node, ast.ImportFrom)]
    assert len(imports) == 1
    assert imports[0].module == "trading_bot.cli.pd2d2_first_paper_execution"
    assert [alias.name for alias in imports[0].names] == ["main"]
    assert sum(isinstance(node, ast.Call) for node in ast.walk(tree)) == 2


def test_publication_freeze_values_are_fully_reconciled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    freeze = harness.publication_freeze.require_production_paper_publication_freeze()
    harness._require_frozen_publication()
    monkeypatch.setattr(
        harness.publication_freeze,
        "require_production_paper_publication_freeze",
        lambda: replace(freeze, anchor_byte_length=freeze.anchor_byte_length + 1),
    )
    with pytest.raises(harness._HarnessReconciliationError):
        harness._require_frozen_publication()
