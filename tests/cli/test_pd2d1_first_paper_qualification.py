"""Focused source-only coverage for the frozen PD2D1 operator harness."""

from __future__ import annotations

import ast
import importlib
import json
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

import trading_bot.cli.pd2d1_first_paper_qualification as harness
from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification,
    PaperOperationInspectionCode,
)
from trading_bot.domain import Symbol
from trading_bot.market_calendar import TradingSession
from trading_bot.runtime.personal_desktop_supervised_paper_operation_qualification import (  # noqa: E501
    SupervisedPaperOperationQualificationResult,
    SupervisedPaperOperationQualificationStatus,
)
from trading_bot.strategies import MovingAverageCrossoverConfig

_SECRET_DIAGNOSTIC_TEXT = (
    r"token=private-token F:\private\operation-root handle=0xDEADBEEF sid=secret"
)


class _FakeDailySnapshot:
    def __init__(self, *, symbol: Symbol | None = None) -> None:
        symbol = Symbol("SPY") if symbol is None else symbol
        self.snapshot_id = harness._EXPECTED_SELECTED_SNAPSHOT_ID
        self.target_session = TradingSession(date(2026, 8, 28))
        self.request = SimpleNamespace(symbols=(symbol,))
        self.bars = (SimpleNamespace(bar=SimpleNamespace(symbol=symbol)),)


class _FakeSelectedResult:
    def __init__(self) -> None:
        self.snapshot_bytes = b"s" * harness._EXPECTED_SELECTED_BYTE_LENGTH
        self.audit = SimpleNamespace(
            selection_id=harness._EXPECTED_SELECTION_ID,
            snapshot_id=harness._EXPECTED_SELECTED_SNAPSHOT_ID,
            artifact_sha256=sha256(self.snapshot_bytes).hexdigest(),
            artifact_byte_length=len(self.snapshot_bytes),
        )
        self.verification = SimpleNamespace(snapshot=_FakeDailySnapshot())


class _FakeVerifiedStrategyHistorySeed:
    def __init__(self) -> None:
        self.seed = SimpleNamespace(
            seed_id=harness._EXPECTED_SEED_ID,
            symbol=Symbol("SPY"),
        )
        self.target_session = TradingSession(date(2026, 8, 28))
        self.strategy_config = MovingAverageCrossoverConfig(3, 5, Decimal("1"))
        self.artifact_sha256 = harness._EXPECTED_SEED_SHA256
        self.artifact_byte_length = harness._EXPECTED_SEED_BYTE_LENGTH


def _install_checkout_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    seed_path = (
        Path(__file__).resolve().parents[2]
        / "docs/validation/evidence/pd2d1-spy-strategy-history-seed-2026-08-28.json"
    )
    monkeypatch.setattr(harness, "_resolve_frozen_seed_path", lambda: seed_path)
    # Verify the tracked LF bytes independently of Windows checkout EOLs.
    monkeypatch.setattr(
        harness,
        "_read_frozen_seed_bytes",
        lambda path: path.read_text(encoding="utf-8").encode("utf-8"),
    )


def _qualification_result(
    *,
    ready: bool = True,
    paper_account_id: str = harness._EXPECTED_PAPER_ACCOUNT_ID,
    terminal_checkpoint_id: UUID = harness._EXPECTED_TERMINAL_CHECKPOINT_ID,
) -> SupervisedPaperOperationQualificationResult:
    return SupervisedPaperOperationQualificationResult(
        paper_account_id=paper_account_id,
        selected_snapshot_id=harness._EXPECTED_SELECTED_SNAPSHOT_ID,
        plan_id=UUID("11111111-1111-4111-8111-111111111111"),
        operation_id=UUID("22222222-2222-4222-8222-222222222222"),
        application_id=UUID("33333333-3333-4333-8333-333333333333"),
        terminal_checkpoint_id=terminal_checkpoint_id,
        inspection_classification=(
            PaperOperationClassification.PENDING
            if ready
            else PaperOperationClassification.ALREADY_APPLIED
        ),
        inspection_diagnostic=(
            PaperOperationInspectionCode.PENDING
            if ready
            else PaperOperationInspectionCode.ALREADY_APPLIED
        ),
        qualification_status=(
            SupervisedPaperOperationQualificationStatus.READY
            if ready
            else SupervisedPaperOperationQualificationStatus.NOT_READY
        ),
        inspector_called=True,
    )


def _expected_evidence_record(*, ready: bool) -> dict[str, object]:
    return {
        "all_effect_gates_false": True,
        "application_id": "33333333-3333-4333-8333-333333333333",
        "authority_epoch_id": harness._EXPECTED_AUTHORITY_EPOCH_ID,
        "inspection_classification": "PENDING" if ready else "ALREADY_APPLIED",
        "inspection_diagnostic": "PENDING" if ready else "ALREADY_APPLIED",
        "machine_authority_id": harness._EXPECTED_MACHINE_AUTHORITY_ID,
        "open_reference_price": "767.33",
        "open_reference_session": "2026-08-31",
        "open_reference_symbol": "SPY",
        "operation_id": "22222222-2222-4222-8222-222222222222",
        "paper_account_id": harness._EXPECTED_PAPER_ACCOUNT_ID,
        "plan_id": "11111111-1111-4111-8111-111111111111",
        "qualification_status": "READY" if ready else "NOT_READY",
        "schema": harness._SCHEMA,
        "seed_byte_length": harness._EXPECTED_SEED_BYTE_LENGTH,
        "seed_id": str(harness._EXPECTED_SEED_ID),
        "seed_sha256": harness._EXPECTED_SEED_SHA256,
        "selected_snapshot_id": str(harness._EXPECTED_SELECTED_SNAPSHOT_ID),
        "selection_id": str(harness._EXPECTED_SELECTION_ID),
        "terminal_checkpoint_id": str(harness._EXPECTED_TERMINAL_CHECKPOINT_ID),
    }


def _install_happy_runtime(
    monkeypatch: pytest.MonkeyPatch,
    *,
    selected: _FakeSelectedResult | None = None,
    result: SupervisedPaperOperationQualificationResult | None = None,
) -> tuple[SimpleNamespace, _FakeSelectedResult, dict[str, object]]:
    authority = SimpleNamespace(
        machine_authority_id=harness._EXPECTED_MACHINE_AUTHORITY_ID,
        authority_epoch_id=harness._EXPECTED_AUTHORITY_EPOCH_ID,
        approved_account_sid=harness._EXPECTED_TRADING_SID,
    )
    selected = selected or _FakeSelectedResult()
    result = result or _qualification_result()
    calls: dict[str, object] = {
        "acquire": 0,
        "p2_construct": [],
        "p2_read": [],
        "qualification": [],
    }

    def acquire() -> object:
        calls["acquire"] = int(calls["acquire"]) + 1
        return authority

    class Reader:
        def __init__(self, candidate: object) -> None:
            cast = calls["p2_construct"]
            assert isinstance(cast, list)
            cast.append(candidate)

        def read_selected_snapshot(self, *args: object, **kwargs: object) -> object:
            cast = calls["p2_read"]
            assert isinstance(cast, list)
            cast.append((args, kwargs))
            return selected

    def qualify(*args: object, **kwargs: object) -> object:
        cast = calls["qualification"]
        assert isinstance(cast, list)
        cast.append((args, kwargs))
        return result

    monkeypatch.setattr(harness, "acquire_validated_production_authority", acquire)
    monkeypatch.setattr(
        harness, "_load_frozen_history_seed", _FakeVerifiedStrategyHistorySeed
    )
    monkeypatch.setattr(harness, "WindowsSelectedC3SnapshotReadAuthority", Reader)
    monkeypatch.setattr(
        harness, "qualify_supervised_personal_desktop_paper_operation", qualify
    )
    monkeypatch.setattr(harness, "SelectedC3SnapshotReadResult", _FakeSelectedResult)
    monkeypatch.setattr(harness, "DailyMarketDataSnapshot", _FakeDailySnapshot)
    monkeypatch.setattr(
        harness,
        "_EXPECTED_SELECTED_SHA256",
        sha256(selected.snapshot_bytes).hexdigest(),
    )
    return authority, selected, calls


def test_parser_has_no_semantic_arguments_and_rejects_unexpected_before_activity(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    parser = harness.build_parser()
    assert {
        option for action in parser._actions for option in action.option_strings
    } == {"-h", "--help"}
    monkeypatch.setattr(
        harness,
        "_require_all_effect_gates_false",
        lambda: pytest.fail("unexpected arguments reached source gates"),
    )
    monkeypatch.setattr(
        harness,
        "acquire_validated_production_authority",
        lambda: pytest.fail("unexpected arguments reached C1"),
    )
    monkeypatch.setattr(
        harness,
        "WindowsSelectedC3SnapshotReadAuthority",
        lambda authority: pytest.fail("unexpected arguments reached P2"),
    )

    assert harness.main(["--selection-id", "anything"]) == harness._EXIT_USAGE
    output = capsys.readouterr()
    assert output.out == ""
    assert json.loads(output.err) == {
        "reason": "INVALID_ARGUMENTS",
        "schema": harness._SCHEMA,
    }


@pytest.mark.parametrize(
    ("module", "name", "value"),
    (
        (
            harness.paper_security,
            "PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED",
            True,
        ),
        (
            harness.paper_security,
            "PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED",
            None,
        ),
        (
            harness.pd2c,
            "PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED",
            0,
        ),
    ),
)
def test_each_gate_must_be_exact_false_before_c1(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    module: object,
    name: str,
    value: object,
) -> None:
    monkeypatch.setattr(module, name, value)
    monkeypatch.setattr(
        harness,
        "acquire_validated_production_authority",
        lambda: pytest.fail("gate mismatch reached C1"),
    )

    assert harness.main([]) == harness._EXIT_PREFLIGHT
    output = capsys.readouterr()
    assert output.out == ""
    assert json.loads(output.err)["reason"] == "PREFLIGHT_BLOCKED"


def test_preflight_failure_preserves_exit_and_safe_evidence(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        harness,
        "_require_all_effect_gates_false",
        lambda: (_ for _ in ()).throw(RuntimeError(_SECRET_DIAGNOSTIC_TEXT)),
    )
    monkeypatch.setattr(
        harness,
        "acquire_validated_production_authority",
        lambda: pytest.fail("preflight failure reached C1"),
    )

    assert harness.main([]) == harness._EXIT_PREFLIGHT
    output = capsys.readouterr()
    assert output.out == ""
    assert json.loads(output.err) == {
        "reason": "PREFLIGHT_BLOCKED",
        "schema": harness._SCHEMA,
    }
    assert _SECRET_DIAGNOSTIC_TEXT not in output.err


def test_c1_failure_preserves_exit_and_stops_before_p2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _, _, calls = _install_happy_runtime(monkeypatch)
    monkeypatch.setattr(
        harness,
        "acquire_validated_production_authority",
        lambda: (_ for _ in ()).throw(RuntimeError(_SECRET_DIAGNOSTIC_TEXT)),
    )

    assert harness.main([]) == harness._EXIT_AUTHORITY
    assert calls["p2_construct"] == []
    assert calls["qualification"] == []
    output = capsys.readouterr()
    assert output.out == ""
    assert json.loads(output.err) == {
        "reason": "PRODUCTION_AUTHORITY_BLOCKED",
        "schema": harness._SCHEMA,
    }
    assert _SECRET_DIAGNOSTIC_TEXT not in output.err


def test_p2_failure_preserves_exit_and_stops_before_qualification(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    authority, _, calls = _install_happy_runtime(monkeypatch)

    class BlockedReader:
        def __init__(self, candidate: object) -> None:
            assert candidate is authority

        def read_selected_snapshot(self, selection_id: str) -> object:
            assert selection_id == str(harness._EXPECTED_SELECTION_ID)
            raise RuntimeError(_SECRET_DIAGNOSTIC_TEXT)

    monkeypatch.setattr(
        harness, "WindowsSelectedC3SnapshotReadAuthority", BlockedReader
    )

    assert harness.main([]) == harness._EXIT_SELECTED_SNAPSHOT
    assert calls["qualification"] == []
    output = capsys.readouterr()
    assert output.out == ""
    assert json.loads(output.err) == {
        "reason": "SELECTED_SNAPSHOT_BLOCKED",
        "schema": harness._SCHEMA,
    }
    assert _SECRET_DIAGNOSTIC_TEXT not in output.err


def test_publication_freeze_mismatch_stops_before_seed_and_c1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    freeze = harness.publication_freeze.require_production_paper_publication_freeze()
    monkeypatch.setattr(
        harness.publication_freeze,
        "require_production_paper_publication_freeze",
        lambda: replace(freeze, paper_account_id=str(UUID(int=99))),
    )
    monkeypatch.setattr(
        harness,
        "_load_frozen_history_seed",
        lambda: pytest.fail("publication mismatch reached seed"),
    )
    monkeypatch.setattr(
        harness,
        "acquire_validated_production_authority",
        lambda: pytest.fail("publication mismatch reached C1"),
    )

    assert harness.main([]) == harness._EXIT_PREFLIGHT


@pytest.mark.parametrize("payload", (b"", b"x" * 1060, b"x" * 1059))
def test_wrong_seed_bytes_hash_or_length_stop_before_verification_and_c1(
    monkeypatch: pytest.MonkeyPatch, payload: bytes
) -> None:
    monkeypatch.setattr(harness, "_resolve_frozen_seed_path", lambda: Path("unused"))
    monkeypatch.setattr(harness, "_read_frozen_seed_bytes", lambda path: payload)
    monkeypatch.setattr(
        harness,
        "verify_strategy_history_seed",
        lambda *args, **kwargs: pytest.fail("bad seed reached semantic verification"),
    )
    monkeypatch.setattr(
        harness,
        "acquire_validated_production_authority",
        lambda: pytest.fail("bad seed reached C1"),
    )

    assert harness.main([]) == harness._EXIT_PREFLIGHT


def test_missing_seed_stops_before_c1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        harness,
        "_resolve_frozen_seed_path",
        lambda: (_ for _ in ()).throw(FileNotFoundError()),
    )
    monkeypatch.setattr(
        harness,
        "acquire_validated_production_authority",
        lambda: pytest.fail("missing seed reached C1"),
    )

    assert harness.main([]) == harness._EXIT_PREFLIGHT


@pytest.mark.parametrize("mismatch", ("seed_id", "symbol", "session", "config"))
def test_wrong_verified_seed_identity_session_or_config_stops_before_c1(
    monkeypatch: pytest.MonkeyPatch, mismatch: str
) -> None:
    _install_checkout_seed(monkeypatch)
    verified = _FakeVerifiedStrategyHistorySeed()
    if mismatch == "seed_id":
        verified.seed.seed_id = UUID(int=91)
    elif mismatch == "symbol":
        verified.seed.symbol = Symbol("QQQ")
    elif mismatch == "session":
        verified.target_session = TradingSession(date(2026, 8, 27))
    else:
        verified.strategy_config = MovingAverageCrossoverConfig(2, 5, Decimal("1"))
    monkeypatch.setattr(
        harness, "VerifiedStrategyHistorySeed", _FakeVerifiedStrategyHistorySeed
    )
    monkeypatch.setattr(
        harness, "verify_strategy_history_seed", lambda *args, **kwargs: verified
    )
    monkeypatch.setattr(
        harness,
        "acquire_validated_production_authority",
        lambda: pytest.fail("bad verified seed reached C1"),
    )

    assert harness.main([]) == harness._EXIT_PREFLIGHT


def test_seed_verifier_receives_exact_frozen_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_checkout_seed(monkeypatch)
    original = harness.verify_strategy_history_seed
    observed: dict[str, object] = {}

    def verify(payload: bytes, **kwargs: object) -> object:
        observed.update(kwargs)
        return original(payload, **kwargs)

    monkeypatch.setattr(harness, "verify_strategy_history_seed", verify)
    verified = harness._load_frozen_history_seed()

    assert verified.seed.seed_id == harness._EXPECTED_SEED_ID
    assert verified.artifact_sha256 == harness._EXPECTED_SEED_SHA256
    assert verified.artifact_byte_length == harness._EXPECTED_SEED_BYTE_LENGTH
    assert observed["expected_symbol"] == Symbol("SPY")
    assert observed["target_session"] == TradingSession(date(2026, 8, 28))
    assert observed["strategy_config"] == MovingAverageCrossoverConfig(
        3, 5, Decimal("1")
    )
    assert observed["calendar"].descriptor == harness.XNYS_CALENDAR_DESCRIPTOR


def test_source_uses_no_wall_clock_or_environment_semantic_inputs() -> None:
    source = Path(harness.__file__).read_text(encoding="utf-8")
    assert "datetime.now" not in source
    assert "datetime.today" not in source
    assert "date.today" not in source
    assert "uuid4" not in source
    assert "os.environ" not in source
    assert "getenv" not in source


@pytest.mark.parametrize(
    "field",
    ("machine_authority_id", "authority_epoch_id", "approved_account_sid"),
)
def test_authority_identity_mismatch_stops_before_p2(
    monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    authority, _, _ = _install_happy_runtime(monkeypatch)
    setattr(authority, field, "wrong")
    monkeypatch.setattr(
        harness, "acquire_validated_production_authority", lambda: authority
    )
    monkeypatch.setattr(
        harness,
        "WindowsSelectedC3SnapshotReadAuthority",
        lambda candidate: pytest.fail("authority mismatch reached P2"),
    )

    assert harness.main([]) == harness._EXIT_RECONCILIATION


@pytest.mark.parametrize(
    "mismatch", ("selection_id", "snapshot_id", "hash", "length", "session", "symbol")
)
def test_selected_snapshot_mismatch_blocks_before_qualification(
    monkeypatch: pytest.MonkeyPatch, mismatch: str
) -> None:
    selected = _FakeSelectedResult()
    expected_hash = selected.audit.artifact_sha256
    if mismatch == "selection_id":
        selected.audit.selection_id = UUID(int=81)
    elif mismatch == "snapshot_id":
        selected.audit.snapshot_id = UUID(int=82)
        selected.verification.snapshot.snapshot_id = UUID(int=82)
    elif mismatch == "hash":
        selected.audit.artifact_sha256 = "0" * 64
    elif mismatch == "length":
        selected.audit.artifact_byte_length -= 1
    elif mismatch == "session":
        selected.verification.snapshot.target_session = TradingSession(
            date(2026, 8, 27)
        )
    else:
        selected.verification.snapshot.request.symbols = (Symbol("QQQ"),)
        selected.verification.snapshot.bars = (
            SimpleNamespace(bar=SimpleNamespace(symbol=Symbol("QQQ"))),
        )
    _, _, calls = _install_happy_runtime(monkeypatch, selected=selected)
    monkeypatch.setattr(harness, "_EXPECTED_SELECTED_SHA256", expected_hash)

    assert harness.main([]) == harness._EXIT_RECONCILIATION
    assert calls["qualification"] == []


def test_production_path_uses_one_c1_for_p2_and_qualification_with_exact_inputs(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    authority, selected, calls = _install_happy_runtime(monkeypatch)

    assert harness.main([]) == 0
    assert calls["acquire"] == 1
    assert calls["p2_construct"] == [authority]
    assert calls["p2_read"] == [((str(harness._EXPECTED_SELECTION_ID),), {})]
    assert len(calls["qualification"]) == 1
    args, kwargs = calls["qualification"][0]
    assert args[0] is authority
    assert args[1] is selected
    assert kwargs["history_seed"].seed.seed_id == harness._EXPECTED_SEED_ID
    assert kwargs["strategy_config"] == MovingAverageCrossoverConfig(3, 5, Decimal("1"))
    assert kwargs["caller_idempotency_key"] == UUID(
        "c762ad22-8d10-43d7-a38b-7d95e730c5ea"
    )
    assert kwargs["planning_at"] == datetime(2026, 8, 29, 9, 46, 43, 769105, tzinfo=UTC)
    assert kwargs["submitted_at"] == datetime(2026, 8, 31, 13, 30, tzinfo=UTC)
    assert kwargs["filled_at"] == datetime(2026, 8, 31, 13, 30, tzinfo=UTC)
    assert kwargs["metadata"] == ()
    assert kwargs["historical_cycle_configuration_payloads"] == ()
    open_reference = kwargs["open_reference"]
    assert open_reference.symbol == Symbol("SPY")
    assert open_reference.session == TradingSession(date(2026, 8, 31))
    assert open_reference.caller_asserted_open_reference_price == Decimal("767.33")
    policies = kwargs["policies"]
    assert policies.rebalance_assumptions == harness.RebalanceAssumptions(
        fixed_commission=Decimal("0"),
        allow_fractional_quantities=False,
        quantity_increment=Decimal("1"),
        minimum_trade_notional=Decimal("0"),
        minimum_trade_quantity=Decimal("1"),
        target_weight_tolerance=Decimal("0"),
        additional_execution_cash_buffer=Decimal("0"),
        use_planned_sell_proceeds=False,
    )
    assert policies.portfolio_constraints == harness.PortfolioConstraints(
        minimum_cash_weight=Decimal("0.90"),
        maximum_cash_weight=Decimal("1"),
        maximum_position_weight=Decimal("0.10"),
        maximum_one_way_rebalance_turnover=Decimal("0.10"),
        minimum_position_weight=None,
        long_only=True,
        allow_leverage=False,
    )
    assert policies.proposal_policy.allow_partial_plans is False
    assert policies.proposal_confidence is None
    assert policies.risk_limits == harness.RiskLimits(
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
    assert policies.risk_policy.allow_sell_proceeds_for_later_buys is False
    assert policies.fill_policy.slippage_basis_points == Decimal("0")
    assert policies.fill_policy.fixed_commission == Decimal("0")
    assert policies.trading_enabled is True
    assert capsys.readouterr().err == ""


def test_ready_pending_pending_succeeds_and_stdout_is_exact_safe_surface(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install_happy_runtime(monkeypatch)

    assert harness.main([]) == 0
    output = capsys.readouterr()
    assert output.err == ""
    assert output.out.count("\n") == 1
    record = json.loads(output.out)
    assert record == _expected_evidence_record(ready=True)
    for prohibited in (
        "F:\\",
        "operation_root",
        "artifact_path",
        "execution_inputs",
        "preparation",
        "binding",
        "native_handle",
        "mutex",
        "credential",
        "receipt_path",
        "transition_path",
    ):
        assert prohibited not in output.out


def test_not_ready_is_emitted_once_and_returns_nonzero_without_retry(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _, _, calls = _install_happy_runtime(
        monkeypatch, result=_qualification_result(ready=False)
    )

    assert harness.main([]) == harness._EXIT_NOT_READY
    assert len(calls["qualification"]) == 1
    output = capsys.readouterr()
    assert output.err == ""
    assert output.out.count("\n") == 1
    assert json.loads(output.out) == _expected_evidence_record(ready=False)


@pytest.mark.parametrize(
    ("error_type", "reason"),
    (
        (
            harness.SupervisedPaperOperationQualificationGateError,
            "QUALIFICATION_GATE_CHANGED",
        ),
        (
            harness.SupervisedPaperOperationQualificationRootMismatchError,
            "QUALIFICATION_ROOT_MISMATCH",
        ),
        (
            harness.SupervisedPaperOperationQualificationReconciliationError,
            "QUALIFICATION_IDENTITY_MISMATCH",
        ),
        (
            harness.SupervisedPaperOperationQualificationError,
            "QUALIFICATION_INTERNAL_BLOCKED",
        ),
        (
            harness.PaperOperationPreparationReconciliationRequiredError,
            "ABANDONED_OWNER_RECONCILIATION_REQUIRED",
        ),
        (harness.PaperAccountMutexSecurityError, "PAPER_MUTEX_SECURITY_BLOCKED"),
        (harness.PaperAccountMutexBusyError, "PAPER_MUTEX_BUSY"),
        (harness.PaperAccountMutexWaitError, "PAPER_MUTEX_WAIT_BLOCKED"),
        (harness.PaperAccountMutexReentrantError, "PAPER_MUTEX_REENTRANT"),
        (harness.PaperAccountMutexReleaseError, "PAPER_MUTEX_RELEASE_BLOCKED"),
        (harness.PaperAccountMutexPoisonedError, "PAPER_MUTEX_POISONED"),
        (harness.PaperAccountMutexError, "PAPER_MUTEX_BLOCKED"),
        (harness.ManualPaperStrategyPlanError, "STRATEGY_PLAN_BLOCKED"),
        (
            harness.VerifiedSnapshotPaperCyclePreparationError,
            "VERIFIED_CYCLE_PREPARATION_BLOCKED",
        ),
        (harness.SelectedC3SnapshotReadError, "P2_REVALIDATION_BLOCKED"),
        (harness.PaperOperationError, "OPERATION_INTENT_BLOCKED"),
        (
            harness.PaperOperationExecutionInputsError,
            "EXECUTION_INPUT_RECONCILIATION_BLOCKED",
        ),
        (
            harness.SupervisedPaperOperationPreparationError,
            "SUPERVISED_PREPARATION_BLOCKED",
        ),
        (
            harness.SupervisedPersonalDesktopPaperCycleError,
            "SUPERVISED_CYCLE_BLOCKED",
        ),
        (
            harness.PersonalDesktopPaperAccountError,
            "PAPER_ACCOUNT_READ_OR_AUTHORITY_BLOCKED",
        ),
        (harness.WindowsAuthorityError, "WINDOWS_AUTHORITY_BLOCKED"),
        (RuntimeError, "QUALIFICATION_BLOCKED"),
    ),
)
def test_qualification_exception_is_typed_stderr_only_and_never_retried(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error_type: type[Exception],
    reason: str,
) -> None:
    _, _, calls = _install_happy_runtime(monkeypatch)

    def fail(*args: object, **kwargs: object) -> object:
        cast = calls["qualification"]
        assert isinstance(cast, list)
        cast.append((args, kwargs))
        raise error_type(_SECRET_DIAGNOSTIC_TEXT)

    monkeypatch.setattr(
        harness, "qualify_supervised_personal_desktop_paper_operation", fail
    )

    assert harness.main([]) == harness._EXIT_QUALIFICATION
    assert len(calls["qualification"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err.count("\n") == 1
    assert json.loads(output.err) == {"reason": reason, "schema": harness._SCHEMA}
    assert _SECRET_DIAGNOSTIC_TEXT not in output.err


@pytest.mark.parametrize(
    ("operation", "error_code", "invalid_code", "expected_fields"),
    (
        (
            "GetSecurityInfo",
            5,
            False,
            {"native_error_code": 5, "native_operation": "GetSecurityInfo"},
        ),
        (_SECRET_DIAGNOSTIC_TEXT, 5, False, {"native_error_code": 5}),
        (
            "GetSecurityInfo",
            None,
            False,
            {"native_error_code": None, "native_operation": "GetSecurityInfo"},
        ),
        (
            "GetSecurityInfo",
            None,
            True,
            {"native_operation": "GetSecurityInfo"},
        ),
    ),
)
def test_windows_native_exception_emits_only_allowlisted_typed_fields(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    operation: str,
    error_code: int | None,
    invalid_code: bool,
    expected_fields: dict[str, object],
) -> None:
    _, _, calls = _install_happy_runtime(monkeypatch)
    error = harness.WindowsNativeError(operation, error_code)
    if invalid_code:
        error.error_code = _SECRET_DIAGNOSTIC_TEXT  # type: ignore[assignment]
    error.args = (_SECRET_DIAGNOSTIC_TEXT,)

    def fail(*args: object, **kwargs: object) -> object:
        cast = calls["qualification"]
        assert isinstance(cast, list)
        cast.append((args, kwargs))
        raise error

    monkeypatch.setattr(
        harness, "qualify_supervised_personal_desktop_paper_operation", fail
    )

    assert harness.main([]) == harness._EXIT_QUALIFICATION
    assert len(calls["qualification"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err.count("\n") == 1
    expected = {
        "reason": "WINDOWS_NATIVE_BLOCKED",
        "schema": harness._SCHEMA,
        **expected_fields,
    }
    assert json.loads(output.err) == expected
    assert _SECRET_DIAGNOSTIC_TEXT not in output.err


@pytest.mark.parametrize(
    "result",
    (
        _qualification_result(paper_account_id=str(UUID(int=71))),
        _qualification_result(terminal_checkpoint_id=UUID(int=72)),
    ),
)
def test_returned_account_or_terminal_mismatch_blocks_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    result: SupervisedPaperOperationQualificationResult,
) -> None:
    _, _, calls = _install_happy_runtime(monkeypatch, result=result)

    assert harness.main([]) == harness._EXIT_RECONCILIATION
    assert len(calls["qualification"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert json.loads(output.err)["reason"] == ("QUALIFICATION_RECONCILIATION_BLOCKED")


def test_frozen_production_identities_are_exact() -> None:
    assert harness._EXPECTED_SEED_PATH == Path(
        r"F:\AI\worktrees\ai-trading-bot-personal-desktop"
        r"\docs\validation\evidence"
        r"\pd2d1-spy-strategy-history-seed-2026-08-28.json"
    )
    assert harness._EXPECTED_MACHINE_AUTHORITY_ID == (
        "223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1"
    )
    assert harness._EXPECTED_AUTHORITY_EPOCH_ID == (
        "e6f3de5d-1412-40ad-a022-8b33e72a5f6d"
    )
    assert harness._EXPECTED_TRADING_SID == (
        "S-1-5-21-1397534616-3988210162-180023805-1009"
    )
    assert str(harness._EXPECTED_SELECTION_ID) == (
        "36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280"
    )
    assert str(harness._EXPECTED_SELECTED_SNAPSHOT_ID) == (
        "eba46838-44ae-5bec-97bf-98c6639ae6a7"
    )
    assert harness._EXPECTED_SELECTED_SHA256 == (
        "31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d"
    )
    assert harness._EXPECTED_SELECTED_BYTE_LENGTH == 1291
    assert harness._EXPECTED_PAPER_ACCOUNT_ID == (
        "9415cd7b-bf36-5fba-bd58-a0f99119dc21"
    )
    assert str(harness._EXPECTED_TERMINAL_CHECKPOINT_ID) == (
        "1832a2b5-8b63-501a-8f7d-f1722c32307b"
    )
    assert str(harness._EXPECTED_SEED_ID) == ("5dc95e10-ba22-5b91-94b2-0d851aa8e2d7")
    assert harness._EXPECTED_SEED_SHA256 == (
        "40dda54c82324f358d640cce89e467295b8f5b73a32fed76c52e7ca90d398e64"
    )
    assert harness._EXPECTED_SEED_BYTE_LENGTH == 1060
    assert harness._EXPECTED_TARGET_SESSION == TradingSession(date(2026, 8, 28))
    assert harness._EXPECTED_OPEN_SESSION == TradingSession(date(2026, 8, 31))
    assert harness._EXPECTED_SYMBOL == Symbol("SPY")
    assert harness._EXPECTED_GENESIS_SHA256 == (
        "d1a7ff14425c8a797a952860a1102489a4c81cac2a24a45bc3127eb8eb2e9548"
    )
    assert harness._EXPECTED_GENESIS_BYTE_LENGTH == 533
    assert harness._EXPECTED_GENESIS_AS_OF == datetime(
        2026, 8, 29, 9, 46, 43, 769105, tzinfo=UTC
    )
    assert (
        harness.paper_security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED
        is False
    )
    assert (
        harness.paper_security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED
        is False
    )
    assert (
        harness.pd2c.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED
        is False
    )


def test_source_has_no_effect_writer_or_external_effect_path() -> None:
    source = Path(harness.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    imported_modules = {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert {
        "execute_paper_operation_once",
        "execute_supervised_personal_desktop_paper_operation",
        "commit_transition_directory",
        "commit_paper_operation_receipt",
        "ProcessPoolExecutor",
        "ThreadPoolExecutor",
    }.isdisjoint(imported_names)
    assert not any(
        boundary in module
        for module in imported_modules
        for boundary in (
            "provider",
            "broker",
            "alpaca",
            "scheduler",
            "provisioning",
            "recovery",
            "requests",
            "socket",
            "subprocess",
            "urllib",
        )
    )
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert {
        "execute_paper_operation_once",
        "commit_transition_directory",
        "commit_paper_operation_receipt",
        "Popen",
        "check_call",
        "check_output",
        "open",
        "run",
    }.isdisjoint(called_names)
    forbidden_attributes = {
        "write_bytes",
        "write_text",
        "rename",
        "replace",
        "unlink",
        "mkdir",
        "rmdir",
        "touch",
    }
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in forbidden_attributes
        for node in ast.walk(tree)
    )
    assert source.count("qualify_supervised_personal_desktop_paper_operation(") == 1
    assert source.count("read_selected_snapshot(") == 1
    assert "artifact_path" not in source


def test_thin_script_imports_without_running() -> None:
    module = importlib.import_module(
        "scripts.qualify_first_personal_desktop_paper_operation"
    )

    assert module.main is harness.main
