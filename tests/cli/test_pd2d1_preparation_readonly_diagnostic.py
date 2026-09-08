"""Focused source-only coverage for the PD2D1 preparation diagnostic."""

from __future__ import annotations

import ast
import ctypes
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

import trading_bot.cli.pd2d1_preparation_readonly_diagnostic as diagnostic
from trading_bot.domain import Symbol
from trading_bot.market_calendar import TradingSession
from trading_bot.strategies import MovingAverageCrossoverConfig

_HOSTILE = r"token=private F:\secret handle=0xDEADBEEF dynamic-class"
_PLAN_ID = UUID("11111111-1111-4111-8111-111111111111")
_OPERATION_ID = UUID("22222222-2222-4222-8222-222222222222")
_APPLICATION_ID = UUID("33333333-3333-4333-8333-333333333333")


class _FakeDailySnapshot:
    def __init__(self, *, symbol: Symbol | None = None) -> None:
        symbol = Symbol("SPY") if symbol is None else symbol
        self.snapshot_id = diagnostic._EXPECTED_SELECTED_SNAPSHOT_ID
        self.target_session = TradingSession(date(2026, 8, 28))
        self.request = SimpleNamespace(symbols=(symbol,))
        self.bars = (SimpleNamespace(bar=SimpleNamespace(symbol=symbol)),)


class _FakeSelectedResult:
    def __init__(self) -> None:
        self.snapshot_bytes = b"s" * diagnostic._EXPECTED_SELECTED_BYTE_LENGTH
        self.audit = SimpleNamespace(
            selection_id=diagnostic._EXPECTED_SELECTION_ID,
            snapshot_id=diagnostic._EXPECTED_SELECTED_SNAPSHOT_ID,
            artifact_sha256=sha256(self.snapshot_bytes).hexdigest(),
            artifact_byte_length=len(self.snapshot_bytes),
        )
        self.verification = SimpleNamespace(snapshot=_FakeDailySnapshot())


class _FakeHistorySeed:
    def __init__(self) -> None:
        self.seed = SimpleNamespace(
            seed_id=diagnostic._EXPECTED_SEED_ID,
            symbol=Symbol("SPY"),
        )
        self.target_session = diagnostic._EXPECTED_TARGET_SESSION
        self.strategy_config = MovingAverageCrossoverConfig(3, 5, Decimal("1"))
        self.artifact_sha256 = diagnostic._EXPECTED_SEED_SHA256
        self.artifact_byte_length = diagnostic._EXPECTED_SEED_BYTE_LENGTH


class _FakeExecutionInputs:
    def __init__(self) -> None:
        self.intent = SimpleNamespace(operation_id=_OPERATION_ID)
        self.application_id = _APPLICATION_ID
        self.verified_prior = SimpleNamespace(
            checkpoint_id=diagnostic._EXPECTED_TERMINAL_CHECKPOINT_ID
        )


class _Preparation:
    def __init__(
        self,
        calls: dict[str, object],
        *,
        enter_error: BaseException | None = None,
        release_error: Exception | None = None,
        return_self: bool = True,
    ) -> None:
        self.calls = calls
        self.enter_error = enter_error
        self.release_error = release_error
        self.return_self = return_self
        self.active = False
        self.paper_account_id = diagnostic._EXPECTED_PAPER_ACCOUNT_ID
        self.plan_id = _PLAN_ID
        self.operation_id = _OPERATION_ID
        self.application_id = _APPLICATION_ID
        self.selected_snapshot_id = diagnostic._EXPECTED_SELECTED_SNAPSHOT_ID
        self.plan_artifact_sha256 = "a" * 64
        self.plan_artifact_byte_length = 123
        self.mutex_acquisition_state = diagnostic.PaperAccountMutexState.OWNED

    def __enter__(self) -> object:
        self.calls["enter"] = int(self.calls["enter"]) + 1
        if self.enter_error is not None:
            raise self.enter_error
        self.active = True
        return self if self.return_self else object()

    def __exit__(self, *args: object) -> bool:
        self.calls["exit"] = int(self.calls["exit"]) + 1
        assert self.active is True
        self.active = False
        if self.release_error is not None:
            raise self.release_error
        return False


def _install_happy_path(
    monkeypatch: pytest.MonkeyPatch,
    *,
    selected: _FakeSelectedResult | None = None,
    preparation_factory: object | None = None,
) -> tuple[dict[str, object], object, _FakeSelectedResult, _Preparation]:
    authority = SimpleNamespace(
        machine_authority_id=diagnostic._EXPECTED_MACHINE_AUTHORITY_ID,
        authority_epoch_id=diagnostic._EXPECTED_AUTHORITY_EPOCH_ID,
        approved_account_sid=diagnostic._EXPECTED_TRADING_SID,
    )
    selected = selected or _FakeSelectedResult()
    calls: dict[str, object] = {
        "acquire": 0,
        "p2_construct": [],
        "p2_read": [],
        "construct": [],
        "enter": 0,
        "exit": 0,
        "binding": 0,
    }
    if preparation_factory is None:
        preparation = _Preparation(calls)
    else:
        assert callable(preparation_factory)
        preparation = preparation_factory(calls)

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

    def construct(*args: object, **kwargs: object) -> object:
        cast = calls["construct"]
        assert isinstance(cast, list)
        cast.append((args, kwargs, int(calls["enter"])))
        return preparation

    def binding_getter(active: object) -> object:
        calls["binding"] = int(calls["binding"]) + 1
        assert active is preparation
        assert preparation.active is True
        return SimpleNamespace(
            operation_root=diagnostic._EXPECTED_OPERATION_ROOT,
            execution_inputs=_FakeExecutionInputs(),
        )

    monkeypatch.setattr(diagnostic, "_require_all_effect_gates_false", lambda: None)
    monkeypatch.setattr(diagnostic, "_require_frozen_publication", lambda: None)
    monkeypatch.setattr(diagnostic, "_load_frozen_history_seed", _FakeHistorySeed)
    monkeypatch.setattr(diagnostic, "acquire_validated_production_authority", acquire)
    monkeypatch.setattr(diagnostic, "WindowsSelectedC3SnapshotReadAuthority", Reader)
    monkeypatch.setattr(diagnostic, "SelectedC3SnapshotReadResult", _FakeSelectedResult)
    monkeypatch.setattr(diagnostic, "DailyMarketDataSnapshot", _FakeDailySnapshot)
    monkeypatch.setattr(
        diagnostic,
        "_EXPECTED_SELECTED_SHA256",
        sha256(selected.snapshot_bytes).hexdigest(),
    )
    monkeypatch.setattr(
        diagnostic,
        "supervised_personal_desktop_paper_operation_preparation",
        construct,
    )
    monkeypatch.setattr(
        diagnostic, "_require_active_prepared_paper_operation_binding", binding_getter
    )
    monkeypatch.setattr(
        diagnostic, "VerifiedPaperOperationExecutionInputs", _FakeExecutionInputs
    )
    return calls, authority, selected, preparation


def _captured(capsys: pytest.CaptureFixture[str]) -> tuple[str, str]:
    output = capsys.readouterr()
    assert _HOSTILE not in output.out
    assert _HOSTILE not in output.err
    return output.out, output.err


def test_invalid_arguments_stop_before_preflight_or_c1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    parser = diagnostic.build_parser()
    assert {
        option for action in parser._actions for option in action.option_strings
    } == {"-h", "--help"}
    monkeypatch.setattr(
        diagnostic,
        "_require_all_effect_gates_false",
        lambda: pytest.fail("arguments reached preflight"),
    )
    monkeypatch.setattr(
        diagnostic,
        "acquire_validated_production_authority",
        lambda: pytest.fail("arguments reached C1"),
    )

    assert diagnostic.main(["--selection-id", _HOSTILE]) == diagnostic._EXIT_USAGE
    out, err = _captured(capsys)
    assert out == ""
    assert json.loads(err) == {
        "reason": "INVALID_ARGUMENTS",
        "schema": diagnostic._SCHEMA,
    }


@pytest.mark.parametrize(
    ("module", "attribute", "value", "replace_callable"),
    (
        (
            diagnostic.paper_security,
            "PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED",
            True,
            False,
        ),
        (
            diagnostic.paper_security,
            "PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED",
            None,
            False,
        ),
        (
            diagnostic,
            "_supervised_execution_gate_is_source_false",
            False,
            True,
        ),
    ),
)
def test_each_gate_must_be_exact_false_before_c1(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    module: object,
    attribute: str,
    value: object,
    replace_callable: bool,
) -> None:
    replacement = (lambda: value) if replace_callable else value
    monkeypatch.setattr(module, attribute, replacement)
    monkeypatch.setattr(
        diagnostic,
        "acquire_validated_production_authority",
        lambda: pytest.fail("gate mismatch reached C1"),
    )

    assert diagnostic.main([]) == diagnostic._EXIT_PREFLIGHT
    out, err = _captured(capsys)
    assert out == ""
    assert json.loads(err)["reason"] == "PREFLIGHT_BLOCKED"


def test_publication_mismatch_stops_before_seed_and_c1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    freeze = diagnostic.publication_freeze.require_production_paper_publication_freeze()
    monkeypatch.setattr(
        diagnostic.publication_freeze,
        "require_production_paper_publication_freeze",
        lambda: replace(freeze, manifest_byte_length=freeze.manifest_byte_length + 1),
    )
    monkeypatch.setattr(
        diagnostic,
        "_load_frozen_history_seed",
        lambda: pytest.fail("publication mismatch reached seed"),
    )
    monkeypatch.setattr(
        diagnostic,
        "acquire_validated_production_authority",
        lambda: pytest.fail("publication mismatch reached C1"),
    )

    assert diagnostic.main([]) == diagnostic._EXIT_PREFLIGHT


def test_supervised_execution_gate_is_verified_without_importing_executor() -> None:
    assert diagnostic._supervised_execution_gate_is_source_false() is True


def test_frozen_seed_bytes_identity_and_semantics_are_exact() -> None:
    verified = diagnostic._load_frozen_history_seed()
    assert verified.seed.seed_id == diagnostic._EXPECTED_SEED_ID
    assert verified.seed.symbol == Symbol("SPY")
    assert verified.target_session == TradingSession(date(2026, 8, 28))
    assert verified.strategy_config == MovingAverageCrossoverConfig(3, 5, Decimal("1"))
    assert verified.artifact_sha256 == diagnostic._EXPECTED_SEED_SHA256
    assert verified.artifact_byte_length == diagnostic._EXPECTED_SEED_BYTE_LENGTH


def test_c1_failure_stops_before_p2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls, _, _, _ = _install_happy_path(monkeypatch)
    monkeypatch.setattr(
        diagnostic,
        "acquire_validated_production_authority",
        lambda: (_ for _ in ()).throw(RuntimeError(_HOSTILE)),
    )

    assert diagnostic.main([]) == diagnostic._EXIT_C1
    assert calls["p2_construct"] == []
    assert calls["construct"] == []
    out, err = _captured(capsys)
    assert out == ""
    assert json.loads(err)["reason"] == "C1_BLOCKED"


@pytest.mark.parametrize(
    "field", ("machine_authority_id", "authority_epoch_id", "approved_account_sid")
)
def test_c1_identity_mismatch_stops_before_p2(
    monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    calls, authority, _, _ = _install_happy_path(monkeypatch)
    setattr(authority, field, "wrong")

    assert diagnostic.main([]) == diagnostic._EXIT_C1
    assert calls["p2_construct"] == []


def test_p2_failure_stops_before_preparation(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls, authority, _, _ = _install_happy_path(monkeypatch)

    class Reader:
        def __init__(self, candidate: object) -> None:
            assert candidate is authority

        def read_selected_snapshot(self, selection_id: str) -> object:
            assert selection_id == str(diagnostic._EXPECTED_SELECTION_ID)
            raise diagnostic.SelectedC3SnapshotReadError(_HOSTILE)

    monkeypatch.setattr(diagnostic, "WindowsSelectedC3SnapshotReadAuthority", Reader)

    assert diagnostic.main([]) == diagnostic._EXIT_P2
    assert calls["construct"] == []
    out, err = _captured(capsys)
    assert out == ""
    assert json.loads(err)["exception_family"] == "SELECTED_C3_SNAPSHOT_READ_ERROR"


@pytest.mark.parametrize(
    "mismatch", ("selection", "snapshot", "hash", "length", "session", "symbol")
)
def test_p2_identity_mismatch_stops_before_preparation(
    monkeypatch: pytest.MonkeyPatch, mismatch: str
) -> None:
    selected = _FakeSelectedResult()
    expected_hash = selected.audit.artifact_sha256
    if mismatch == "selection":
        selected.audit.selection_id = UUID(int=31)
    elif mismatch == "snapshot":
        selected.audit.snapshot_id = UUID(int=32)
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
    calls, _, _, _ = _install_happy_path(monkeypatch, selected=selected)
    monkeypatch.setattr(diagnostic, "_EXPECTED_SELECTED_SHA256", expected_hash)

    assert diagnostic.main([]) == diagnostic._EXIT_P2
    assert calls["construct"] == []


def test_same_c1_exact_p2_selection_and_frozen_inputs_are_forwarded_once(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls, authority, selected, _ = _install_happy_path(monkeypatch)

    assert diagnostic.main([]) == 0
    _captured(capsys)
    assert calls["acquire"] == 1
    assert calls["p2_construct"] == [authority]
    assert calls["p2_read"] == [((str(diagnostic._EXPECTED_SELECTION_ID),), {})]
    assert len(calls["construct"]) == 1
    args, kwargs, enter_count = calls["construct"][0]
    assert args == (authority, selected)
    assert enter_count == 0
    assert "artifact_path" not in kwargs
    assert kwargs["history_seed"].seed.seed_id == diagnostic._EXPECTED_SEED_ID
    assert kwargs["strategy_config"] == MovingAverageCrossoverConfig(3, 5, Decimal("1"))
    assert kwargs["caller_idempotency_key"] == UUID(
        "c762ad22-8d10-43d7-a38b-7d95e730c5ea"
    )
    assert kwargs["planning_at"] == datetime(2026, 8, 29, 9, 46, 43, 769105, tzinfo=UTC)
    assert kwargs["submitted_at"] == datetime(2026, 8, 31, 13, 30, tzinfo=UTC)
    assert kwargs["filled_at"] == datetime(2026, 8, 31, 13, 30, tzinfo=UTC)
    assert kwargs["metadata"] == ()
    assert kwargs["historical_cycle_configuration_payloads"] == ()
    assert kwargs[
        "open_reference"
    ] == diagnostic.CallerAssertedNextSessionOpenReference(
        Symbol("SPY"), TradingSession(date(2026, 8, 31)), Decimal("767.33")
    )
    policies = kwargs["policies"]
    assert policies.rebalance_assumptions == diagnostic.RebalanceAssumptions(
        fixed_commission=Decimal("0"),
        allow_fractional_quantities=False,
        quantity_increment=Decimal("1"),
        minimum_trade_notional=Decimal("0"),
        minimum_trade_quantity=Decimal("1"),
        target_weight_tolerance=Decimal("0"),
        additional_execution_cash_buffer=Decimal("0"),
        use_planned_sell_proceeds=False,
    )
    assert policies.portfolio_constraints == diagnostic.PortfolioConstraints(
        minimum_cash_weight=Decimal("0.90"),
        maximum_cash_weight=Decimal("1"),
        maximum_position_weight=Decimal("0.10"),
        maximum_one_way_rebalance_turnover=Decimal("0.10"),
        minimum_position_weight=None,
        long_only=True,
        allow_leverage=False,
    )
    assert policies.proposal_policy == diagnostic.RebalanceProposalPolicy(
        allow_partial_plans=False
    )
    assert policies.proposal_confidence is None
    assert policies.risk_limits == diagnostic.RiskLimits(
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
    assert policies.risk_policy == diagnostic.PortfolioRiskPolicy(
        allow_sell_proceeds_for_later_buys=False
    )
    assert policies.fill_policy == diagnostic.PaperFillPolicy(
        slippage_basis_points=Decimal("0"), fixed_commission=Decimal("0")
    )
    assert policies.trading_enabled is True


def test_preparation_construction_failure_stops_before_entry(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls, _, _, _ = _install_happy_path(monkeypatch)
    monkeypatch.setattr(
        diagnostic,
        "supervised_personal_desktop_paper_operation_preparation",
        lambda *args, **kwargs: (_ for _ in ()).throw(TypeError(_HOSTILE)),
    )

    assert diagnostic.main([]) == diagnostic._EXIT_PREPARATION_CONSTRUCTION
    assert calls["enter"] == 0
    out, err = _captured(capsys)
    assert out == ""
    assert json.loads(err) == {
        "exception_family": "TYPE_ERROR",
        "reason": "PREPARATION_CONSTRUCTION_BLOCKED",
        "schema": diagnostic._SCHEMA,
    }


def test_enter_failure_is_called_once_without_diagnostic_exit(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls, _, _, _ = _install_happy_path(
        monkeypatch,
        preparation_factory=lambda values: _Preparation(
            values,
            enter_error=diagnostic.SupervisedPaperOperationPreparationError(_HOSTILE),
        ),
    )

    assert diagnostic.main([]) == diagnostic._EXIT_PREPARATION_ENTER
    assert calls["enter"] == 1
    assert calls["exit"] == 0
    assert calls["binding"] == 0
    out, err = _captured(capsys)
    assert out == ""
    assert json.loads(err)["reason"] == "PREPARATION_ENTER_BLOCKED"


@pytest.mark.parametrize(
    ("error", "family"),
    (
        (
            diagnostic.PaperAccountMutexSecurityError(_HOSTILE),
            "PAPER_MUTEX_SECURITY_ERROR",
        ),
        (diagnostic.PaperAccountMutexBusyError(_HOSTILE), "PAPER_MUTEX_BUSY_ERROR"),
        (diagnostic.PaperAccountMutexWaitError(_HOSTILE), "PAPER_MUTEX_WAIT_ERROR"),
        (
            diagnostic.PaperAccountMutexReentrantError(_HOSTILE),
            "PAPER_MUTEX_REENTRANT_ERROR",
        ),
        (
            diagnostic.PaperAccountMutexReleaseError(_HOSTILE),
            "PAPER_MUTEX_RELEASE_ERROR",
        ),
        (
            diagnostic.PaperAccountMutexPoisonedError(_HOSTILE),
            "PAPER_MUTEX_POISONED_ERROR",
        ),
        (diagnostic.PaperAccountMutexError(_HOSTILE), "PAPER_MUTEX_ERROR"),
        (
            diagnostic.SupervisedPaperOperationPreparationError(_HOSTILE),
            "SUPERVISED_PREPARATION_ERROR",
        ),
        (
            diagnostic.SupervisedPersonalDesktopPaperCycleError(_HOSTILE),
            "SUPERVISED_CYCLE_ERROR",
        ),
        (
            diagnostic.PersonalDesktopPaperAccountError(_HOSTILE),
            "PERSONAL_DESKTOP_PAPER_ACCOUNT_ERROR",
        ),
        (
            diagnostic.SelectedC3SnapshotReadError(_HOSTILE),
            "SELECTED_C3_SNAPSHOT_READ_ERROR",
        ),
        (
            diagnostic.ManualPaperStrategyPlanError(_HOSTILE),
            "MANUAL_PAPER_STRATEGY_PLAN_ERROR",
        ),
        (
            diagnostic.VerifiedSnapshotPaperCyclePreparationError(_HOSTILE),
            "VERIFIED_CYCLE_PREPARATION_ERROR",
        ),
        (diagnostic.PaperOperationError(_HOSTILE), "PAPER_OPERATION_ERROR"),
        (
            diagnostic.PaperOperationExecutionInputsError(_HOSTILE),
            "PAPER_OPERATION_EXECUTION_INPUTS_ERROR",
        ),
        (diagnostic.WindowsAuthorityError(_HOSTILE), "WINDOWS_AUTHORITY_ERROR"),
        (ctypes.ArgumentError(_HOSTILE), "CTYPES_ARGUMENT_ERROR"),
        (TypeError(_HOSTILE), "TYPE_ERROR"),
        (ValueError(_HOSTILE), "VALUE_ERROR"),
        (OSError(_HOSTILE), "OS_ERROR"),
        (AttributeError(_HOSTILE), "ATTRIBUTE_ERROR"),
        (KeyError(_HOSTILE), "KEY_ERROR"),
        (IndexError(_HOSTILE), "INDEX_ERROR"),
        (RuntimeError(_HOSTILE), "RUNTIME_ERROR"),
        (Exception(_HOSTILE), "UNKNOWN_EXCEPTION"),
    ),
)
def test_exception_families_are_fixed_and_messages_are_sanitized(
    error: Exception, family: str
) -> None:
    record = diagnostic._exception_record("PREPARATION_ENTER_BLOCKED", error)
    assert record == {
        "exception_family": family,
        "reason": "PREPARATION_ENTER_BLOCKED",
        "schema": diagnostic._SCHEMA,
    }
    assert _HOSTILE not in json.dumps(record)


def test_windows_native_fields_are_allowlisted_only() -> None:
    allowed = diagnostic.WindowsNativeError("GetSecurityInfo", 5)
    hostile = diagnostic.WindowsNativeError(_HOSTILE, 6)
    hostile.args = (_HOSTILE,)
    assert diagnostic._exception_record("PREPARATION_ENTER_BLOCKED", allowed) == {
        "exception_family": "WINDOWS_NATIVE_ERROR",
        "native_error_code": 5,
        "native_operation": "GetSecurityInfo",
        "reason": "PREPARATION_ENTER_BLOCKED",
        "schema": diagnostic._SCHEMA,
    }
    record = diagnostic._exception_record("PREPARATION_ENTER_BLOCKED", hostile)
    assert "native_operation" not in record
    assert _HOSTILE not in json.dumps(record)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("paper_account_id", "wrong"),
        ("plan_id", "not-a-uuid"),
        ("operation_id", "not-a-uuid"),
        ("application_id", "not-a-uuid"),
        ("selected_snapshot_id", UUID(int=9)),
        ("plan_artifact_sha256", "A" * 64),
        ("plan_artifact_byte_length", 0),
        ("mutex_acquisition_state", diagnostic.PaperAccountMutexState.ABANDONED_OWNER),
    ),
)
def test_active_preparation_mismatch_blocks_while_active_then_releases(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    field: str,
    value: object,
) -> None:
    calls, _, _, preparation = _install_happy_path(monkeypatch)
    setattr(preparation, field, value)

    assert diagnostic.main([]) == diagnostic._EXIT_ACTIVE_RECONCILIATION
    assert calls["enter"] == 1
    assert calls["exit"] == 1
    assert preparation.active is False
    out, err = _captured(capsys)
    assert out == ""
    assert json.loads(err)["reason"] == "ACTIVE_PREPARATION_RECONCILIATION_BLOCKED"


def test_enter_must_return_exact_preparation_and_still_releases(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls, _, _, preparation = _install_happy_path(
        monkeypatch,
        preparation_factory=lambda values: _Preparation(values, return_self=False),
    )

    assert diagnostic.main([]) == diagnostic._EXIT_ACTIVE_RECONCILIATION
    assert calls["binding"] == 0
    assert calls["exit"] == 1
    assert preparation.active is False
    out, err = _captured(capsys)
    assert out == ""
    assert json.loads(err)["reason"] == "ACTIVE_PREPARATION_RECONCILIATION_BLOCKED"


@pytest.mark.parametrize(
    "mismatch", ("root", "type", "operation", "application", "terminal")
)
def test_private_binding_mismatch_blocks_inside_active_scope(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mismatch: str,
) -> None:
    calls, _, _, preparation = _install_happy_path(monkeypatch)

    def getter(active: object) -> object:
        calls["binding"] = int(calls["binding"]) + 1
        assert active is preparation and preparation.active is True
        inputs = _FakeExecutionInputs()
        root = diagnostic._EXPECTED_OPERATION_ROOT
        if mismatch == "root":
            root = _HOSTILE
        elif mismatch == "type":
            inputs = SimpleNamespace(
                intent=inputs.intent,
                application_id=inputs.application_id,
                verified_prior=inputs.verified_prior,
            )
        elif mismatch == "operation":
            inputs.intent.operation_id = UUID(int=10)
        elif mismatch == "application":
            inputs.application_id = UUID(int=11)
        else:
            inputs.verified_prior.checkpoint_id = UUID(int=12)
        return SimpleNamespace(operation_root=root, execution_inputs=inputs)

    monkeypatch.setattr(
        diagnostic, "_require_active_prepared_paper_operation_binding", getter
    )

    assert diagnostic.main([]) == diagnostic._EXIT_ACTIVE_RECONCILIATION
    assert calls["binding"] == 1
    assert calls["exit"] == 1
    out, err = _captured(capsys)
    assert out == ""
    assert json.loads(err)["reason"] == "ACTIVE_PREPARATION_RECONCILIATION_BLOCKED"


@pytest.mark.parametrize("error", (KeyboardInterrupt(), SystemExit(17)))
def test_base_exception_after_successful_entry_releases_then_reraises_original(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: BaseException,
) -> None:
    calls, _, _, preparation = _install_happy_path(monkeypatch)

    def interrupt(*args: object) -> object:
        assert preparation.active is True
        raise error

    monkeypatch.setattr(diagnostic, "_active_preparation_record", interrupt)

    with pytest.raises(type(error)) as raised:
        diagnostic.main([])
    assert raised.value is error
    if isinstance(error, SystemExit):
        assert raised.value.code == 17
    assert calls["enter"] == 1
    assert calls["exit"] == 1
    assert preparation.active is False
    assert _captured(capsys) == ("", "")


def test_release_failure_fails_closed_once_and_overrides_body_result(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls, _, _, _ = _install_happy_path(
        monkeypatch,
        preparation_factory=lambda values: _Preparation(
            values,
            release_error=diagnostic.PaperAccountMutexReleaseError(_HOSTILE),
        ),
    )

    assert diagnostic.main([]) == diagnostic._EXIT_PREPARATION_RELEASE
    assert calls["enter"] == 1
    assert calls["exit"] == 1
    out, err = _captured(capsys)
    assert out == ""
    assert json.loads(err) == {
        "exception_family": "PAPER_MUTEX_RELEASE_ERROR",
        "reason": "PREPARATION_RELEASE_BLOCKED",
        "schema": diagnostic._SCHEMA,
    }


def test_success_json_is_exact_safe_and_binding_was_checked_while_active(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls, _, _, preparation = _install_happy_path(monkeypatch)

    assert diagnostic.main([]) == 0
    out, err = _captured(capsys)
    assert err == ""
    assert out.count("\n") == 1
    assert json.loads(out) == {
        "active_binding_verified": True,
        "all_effect_gates_false": True,
        "application_id": str(_APPLICATION_ID),
        "authority_epoch_id": diagnostic._EXPECTED_AUTHORITY_EPOCH_ID,
        "machine_authority_id": diagnostic._EXPECTED_MACHINE_AUTHORITY_ID,
        "mutex_acquisition_state": "OWNED",
        "operation_id": str(_OPERATION_ID),
        "operation_root_matches": True,
        "paper_account_id": diagnostic._EXPECTED_PAPER_ACCOUNT_ID,
        "plan_id": str(_PLAN_ID),
        "result": "PREPARATION_READY",
        "schema": diagnostic._SCHEMA,
        "seed_id": str(diagnostic._EXPECTED_SEED_ID),
        "selected_snapshot_id": str(diagnostic._EXPECTED_SELECTED_SNAPSHOT_ID),
        "selection_id": str(diagnostic._EXPECTED_SELECTION_ID),
        "terminal_checkpoint_id": str(diagnostic._EXPECTED_TERMINAL_CHECKPOINT_ID),
    }
    assert calls["enter"] == 1
    assert calls["binding"] == 1
    assert calls["exit"] == 1
    assert preparation.active is False
    for prohibited in (
        "F:\\",
        'operation_root"',
        "artifact_path",
        "execution_inputs",
        "intent",
        'binding"',
        "handle",
        "mutex_name",
        "credential",
    ):
        assert prohibited not in out


def test_source_stops_before_a67_and_has_no_external_effect_boundary() -> None:
    source = Path(diagnostic.__file__).read_text(encoding="utf-8")
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
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    forbidden = {
        "inspect_paper_operation_root",
        "qualify_supervised_personal_desktop_paper_operation",
        "execute_supervised_personal_desktop_paper_operation",
        "execute_paper_operation_once",
        "commit_transition_directory",
        "commit_paper_operation_receipt",
    }
    assert imported_names.isdisjoint(forbidden)
    assert called_names.isdisjoint(forbidden)
    assert not any(
        boundary in module
        for module in imported_modules
        for boundary in (
            "paper_operation_inspection",
            "personal_desktop_supervised_paper_operation_qualification",
            "provider",
            "broker",
            "scheduler",
            "recovery",
            "requests",
            "socket",
            "subprocess",
        )
    )
    assert source.count("supervised_personal_desktop_paper_operation_preparation(") == 1
    assert source.count("read_selected_snapshot(") == 1
    assert "artifact_path" not in source
    assert "datetime.now" not in source
    assert "uuid4" not in source
    assert "os.environ" not in source


def test_thin_script_imports_without_running() -> None:
    module = importlib.import_module("scripts.diagnose_pd2d1_preparation_readonly")
    assert module.main is diagnostic.main
