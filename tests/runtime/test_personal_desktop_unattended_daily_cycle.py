"""Focused PD4-G6 unattended daily-cycle controller tests."""

from __future__ import annotations

import hashlib
import inspect
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import pytest

from trading_bot.runtime import PersonalDesktopUnattendedPaperStartupStatus
from trading_bot.runtime.personal_desktop_unattended_daily_cycle import (
    DisposablePersonalDesktopUnattendedDailyCycleDependencies,
    PersonalDesktopUnattendedDailyCycleClassification,
    _all_eight_gate_state,
    _AuthoritativeHistorySessionGap,
    _InsufficientAuthoritativeHistory,
    _SettlementResult,
    derive_personal_desktop_unattended_daily_cycle_idempotency_key,
    personal_desktop_unattended_paper_policies,
    personal_desktop_unattended_strategy_config,
    run_personal_desktop_unattended_daily_cycle,
    run_personal_desktop_unattended_daily_cycle_for_test,
)
from trading_bot.runtime.personal_desktop_unattended_market_data_capture import (
    PersonalDesktopUnattendedMarketDataCaptureClassification,
    PersonalDesktopUnattendedMarketDataCaptureResult,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_publication import (
    PersonalDesktopUnattendedDecisionPublicationStatus,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    FinalizedUnattendedDecisionForSessionClassification,
    FinalizedUnattendedDecisionForSessionResult,
)

from .test_personal_desktop_unattended_paper_decision_intent import (
    _decision_binding,
    _session_read,
)

_OBSERVED = datetime(2026, 8, 26, 1, tzinfo=UTC)
_COMPLETED = date(2026, 8, 25)
_NEXT_CHECKPOINT = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


def _g5(classification, current):
    request = current.capture_request
    return PersonalDesktopUnattendedMarketDataCaptureResult(
        classification,
        current.session,
        request,
        hashlib.sha256(request.canonical_c2_request_json()).hexdigest(),
    )


def _dependencies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    g5=PersonalDesktopUnattendedMarketDataCaptureClassification.NO_NEW_COMPLETED_SESSION,
    pending=None,
    settlement=PersonalDesktopUnattendedPaperStartupStatus.READY_SAME_INVOCATION,
    publication=PersonalDesktopUnattendedDecisionPublicationStatus.DECISION_READY_EFFECTS_DISABLED,
    history_error: Exception | None = None,
    calls: list[str] | None = None,
    expected_observed: datetime = _OBSERVED,
):
    calls = [] if calls is None else calls
    current = _session_read(_COMPLETED, 106)
    original = _session_read(date(2026, 8, 24), 105)
    next_binding = pending or _decision_binding(monkeypatch)
    predecessor = (
        _NEXT_CHECKPOINT
        if pending is not None
        else next_binding.decision.predecessor_checkpoint_id
    )
    account = SimpleNamespace(
        anchor=SimpleNamespace(paper_account_id="paper.account-g4"),
        prior_checkpoint=SimpleNamespace(checkpoint_id=predecessor),
    )

    def read_selected(authority, session):
        del authority
        calls.append(f"selected:{session.session_date}")
        return original if session == original.session else current

    def find_pending(authority, session):
        del authority
        calls.append("find-pending")
        binding = pending
        return FinalizedUnattendedDecisionForSessionResult(
            (
                FinalizedUnattendedDecisionForSessionClassification.NONE
                if binding is None
                else FinalizedUnattendedDecisionForSessionClassification.FINALIZED
            ),
            session,
            None if binding is None else binding.decision.decision_id,
            binding,
        )

    def settle(authority, prior_selected, execution_selected, binding, historical):
        del authority, binding, historical
        calls.append("settle")
        assert prior_selected.session == original.session
        assert execution_selected.session == current.session
        return _SettlementResult(
            settlement,
            UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
            UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
            configuration_payload=b"verified-plan\n",
        )

    def read_account(authority, historical):
        del authority
        calls.append(f"account:{len(historical)}")
        return account

    def build_history(authority, selected, config):
        del authority, selected, config
        calls.append("history")
        if history_error is not None:
            raise history_error
        return object()

    def build_next(authority, selected, history, evidence, observed, config, policies):
        del authority, selected, history, evidence
        calls.append("next-decision")
        assert observed == expected_observed
        assert config == personal_desktop_unattended_strategy_config()
        assert policies == personal_desktop_unattended_paper_policies()
        return next_binding

    return DisposablePersonalDesktopUnattendedDailyCycleDependencies(
        validate_c1=lambda value: value,
        reconcile_market_data=lambda authority, observed: _g5(g5, current),
        read_selected=read_selected,
        find_pending=find_pending,
        require_pending=lambda authority, result: result.binding,
        settle_pending=settle,
        read_account=read_account,
        require_account=lambda value: value,
        build_history=build_history,
        build_next_decision=build_next,
        qualify_decision=lambda authority, decision, observed: SimpleNamespace(
            status=publication
        ),
        historical_configurations=lambda: (),
        gate_state=lambda: (False,) * 8,
    )


@pytest.mark.parametrize(
    ("g5", "expected"),
    (
        (
            PersonalDesktopUnattendedMarketDataCaptureClassification.CAPTURE_REQUIRED,
            PersonalDesktopUnattendedDailyCycleClassification.CAPTURE_REQUIRED,
        ),
        (
            PersonalDesktopUnattendedMarketDataCaptureClassification.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS,
            PersonalDesktopUnattendedDailyCycleClassification.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS,
        ),
        (
            PersonalDesktopUnattendedMarketDataCaptureClassification.SESSION_GAP,
            PersonalDesktopUnattendedDailyCycleClassification.SESSION_GAP,
        ),
        (
            PersonalDesktopUnattendedMarketDataCaptureClassification.BLOCKED,
            PersonalDesktopUnattendedDailyCycleClassification.BLOCKED,
        ),
    ),
)
def test_g5_terminal_classifications_stop_before_downstream_authority(
    monkeypatch: pytest.MonkeyPatch, g5, expected
) -> None:
    calls: list[str] = []
    result = run_personal_desktop_unattended_daily_cycle_for_test(
        object(), _OBSERVED, _dependencies(monkeypatch, g5=g5, calls=calls)
    )
    assert result.classification is expected
    assert calls == []
    assert result.real_effect_performed is False


def test_selected_snapshot_is_not_misclassified_as_no_new_completed_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    result = run_personal_desktop_unattended_daily_cycle_for_test(
        object(), _OBSERVED, _dependencies(monkeypatch, calls=calls)
    )
    assert (
        result.classification
        is PersonalDesktopUnattendedDailyCycleClassification.DECISION_READY
    )
    assert calls == [
        "selected:2026-08-25",
        "find-pending",
        "account:0",
        "history",
        "next-decision",
    ]


def test_insufficient_history_is_warming_up_after_strict_account_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    result = run_personal_desktop_unattended_daily_cycle_for_test(
        object(),
        _OBSERVED,
        _dependencies(
            monkeypatch,
            history_error=_InsufficientAuthoritativeHistory(),
            calls=calls,
        ),
    )
    assert (
        result.classification
        is PersonalDesktopUnattendedDailyCycleClassification.WARMING_UP
    )
    assert calls[-2:] == ["account:0", "history"]


def test_invalid_selected_history_is_blocked_not_warmup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = run_personal_desktop_unattended_daily_cycle_for_test(
        object(),
        _OBSERVED,
        _dependencies(monkeypatch, history_error=ValueError("corrupt C3")),
    )
    assert (
        result.classification
        is PersonalDesktopUnattendedDailyCycleClassification.BLOCKED
    )


def test_established_history_gap_has_distinct_session_gap_classification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = run_personal_desktop_unattended_daily_cycle_for_test(
        object(),
        _OBSERVED,
        _dependencies(monkeypatch, history_error=_AuthoritativeHistorySessionGap()),
    )
    assert result.classification is (
        PersonalDesktopUnattendedDailyCycleClassification.SESSION_GAP
    )


@pytest.mark.parametrize(
    ("startup", "expected"),
    (
        (
            PersonalDesktopUnattendedPaperStartupStatus.READY_SAME_INVOCATION,
            PersonalDesktopUnattendedDailyCycleClassification.EXECUTION_READY,
        ),
        (
            PersonalDesktopUnattendedPaperStartupStatus.HEALTHY_NO_PENDING_INVOCATION,
            PersonalDesktopUnattendedDailyCycleClassification.EXECUTION_READY,
        ),
        (
            PersonalDesktopUnattendedPaperStartupStatus.RECEIPT_RECOVERY_REQUIRED,
            PersonalDesktopUnattendedDailyCycleClassification.RECEIPT_RECOVERY_REQUIRED,
        ),
        (
            PersonalDesktopUnattendedPaperStartupStatus.BLOCKED,
            PersonalDesktopUnattendedDailyCycleClassification.BLOCKED,
        ),
    ),
)
def test_pending_settlement_classification_stops_unsafe_next_decision(
    monkeypatch: pytest.MonkeyPatch, startup, expected
) -> None:
    pending = _decision_binding(monkeypatch)
    calls: list[str] = []
    result = run_personal_desktop_unattended_daily_cycle_for_test(
        object(),
        _OBSERVED,
        _dependencies(monkeypatch, pending=pending, settlement=startup, calls=calls),
    )
    assert result.classification is expected
    assert "next-decision" not in calls
    assert not any(item.startswith("account:") for item in calls)


def test_already_applied_rereads_account_then_constructs_next_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pending = _decision_binding(monkeypatch)
    calls: list[str] = []
    result = run_personal_desktop_unattended_daily_cycle_for_test(
        object(),
        _OBSERVED,
        _dependencies(
            monkeypatch,
            pending=pending,
            settlement=PersonalDesktopUnattendedPaperStartupStatus.ALREADY_APPLIED,
            calls=calls,
        ),
    )
    assert (
        result.classification
        is PersonalDesktopUnattendedDailyCycleClassification.ALREADY_APPLIED
    )
    assert (
        calls.index("settle") < calls.index("account:1") < calls.index("next-decision")
    )
    assert result.account_predecessor_checkpoint_id == _NEXT_CHECKPOINT


@pytest.mark.parametrize(
    ("publication", "expected"),
    (
        (
            PersonalDesktopUnattendedDecisionPublicationStatus.DECISION_ALREADY_FINALIZED,
            PersonalDesktopUnattendedDailyCycleClassification.DECISION_ALREADY_FINALIZED,
        ),
        (
            PersonalDesktopUnattendedDecisionPublicationStatus.MISSED_DECISION_DEADLINE,
            PersonalDesktopUnattendedDailyCycleClassification.MISSED_DECISION_DEADLINE,
        ),
        (
            PersonalDesktopUnattendedDecisionPublicationStatus.BLOCKED,
            PersonalDesktopUnattendedDailyCycleClassification.BLOCKED,
        ),
    ),
)
def test_next_decision_publication_classifications(
    monkeypatch: pytest.MonkeyPatch, publication, expected
) -> None:
    result = run_personal_desktop_unattended_daily_cycle_for_test(
        object(),
        _OBSERVED,
        _dependencies(monkeypatch, publication=publication),
    )
    assert result.classification is expected
    assert result.decision_publication_status is publication


@pytest.mark.parametrize(
    "observed",
    (
        datetime(2026, 8, 26, 13, 30, tzinfo=UTC),
        datetime(2026, 8, 26, 18, tzinfo=UTC),
    ),
)
def test_at_or_after_open_is_missed_decision_deadline(
    monkeypatch: pytest.MonkeyPatch, observed: datetime
) -> None:
    result = run_personal_desktop_unattended_daily_cycle_for_test(
        object(),
        observed,
        _dependencies(
            monkeypatch,
            publication=(
                PersonalDesktopUnattendedDecisionPublicationStatus.MISSED_DECISION_DEADLINE
            ),
            expected_observed=observed,
        ),
    )
    assert result.classification is (
        PersonalDesktopUnattendedDailyCycleClassification.MISSED_DECISION_DEADLINE
    )


def test_wrong_execution_session_or_original_c3_evidence_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pending = _decision_binding(monkeypatch)
    dependencies = _dependencies(monkeypatch, pending=pending)
    wrong_current = _session_read(date(2026, 8, 26), 107)
    dependencies = replace(
        dependencies,
        reconcile_market_data=lambda authority, observed: _g5(
            PersonalDesktopUnattendedMarketDataCaptureClassification.NO_NEW_COMPLETED_SESSION,
            wrong_current,
        ),
        read_selected=lambda authority, session: wrong_current,
    )
    result = run_personal_desktop_unattended_daily_cycle_for_test(
        object(), _OBSERVED, dependencies
    )
    assert (
        result.classification
        is PersonalDesktopUnattendedDailyCycleClassification.BLOCKED
    )


def test_idempotency_is_restart_stable_and_binds_predecessor() -> None:
    current = _session_read(_COMPLETED, 106)
    first = derive_personal_desktop_unattended_daily_cycle_idempotency_key(
        "paper.account-g4", _NEXT_CHECKPOINT, current
    )
    second = derive_personal_desktop_unattended_daily_cycle_idempotency_key(
        "paper.account-g4", _NEXT_CHECKPOINT, current
    )
    changed = derive_personal_desktop_unattended_daily_cycle_idempotency_key(
        "paper.account-g4",
        UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"),
        current,
    )
    assert first == second
    assert first != changed


def test_source_owned_strategy_and_paper_policy_are_exact() -> None:
    config = personal_desktop_unattended_strategy_config()
    policies = personal_desktop_unattended_paper_policies()
    assert (config.short_window, config.long_window, config.desired_quantity) == (
        3,
        5,
        Decimal("1"),
    )
    assert policies.rebalance_assumptions.minimum_trade_quantity == Decimal("1")
    assert policies.rebalance_assumptions.use_planned_sell_proceeds is False
    assert policies.portfolio_constraints is not None
    assert policies.portfolio_constraints.minimum_cash_weight == Decimal("0.90")
    assert policies.portfolio_constraints.maximum_position_weight == Decimal("0.10")
    assert policies.risk_limits.max_order_notional == Decimal("2500")
    assert policies.risk_limits.max_total_exposure_percent == Decimal("0.10")
    assert policies.risk_policy.allow_sell_proceeds_for_later_buys is False
    assert policies.fill_policy.slippage_basis_points == Decimal("0")
    assert policies.trading_enabled is True


def test_disposable_concurrent_duplicate_cycles_converge_without_effect_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dependencies = _dependencies(monkeypatch)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(
            executor.map(
                lambda unused: run_personal_desktop_unattended_daily_cycle_for_test(
                    object(), _OBSERVED, dependencies
                ),
                range(2),
            )
        )
    assert {item.classification for item in results} == {
        PersonalDesktopUnattendedDailyCycleClassification.DECISION_READY
    }
    assert len({item.next_decision_id for item in results}) == 1
    assert all(item.real_effect_performed is False for item in results)


def test_production_entry_is_zero_argument_and_all_eight_gates_are_false() -> None:
    assert (
        tuple(inspect.signature(run_personal_desktop_unattended_daily_cycle).parameters)
        == ()
    )
    assert _all_eight_gate_state() == (False,) * 8


@pytest.mark.parametrize("armed_index", range(8))
def test_each_independent_effect_gate_must_be_exactly_false(
    monkeypatch: pytest.MonkeyPatch, armed_index: int
) -> None:
    dependencies = _dependencies(monkeypatch)
    gates = [False] * 8
    gates[armed_index] = True
    dependencies = replace(dependencies, gate_state=lambda: tuple(gates))
    result = run_personal_desktop_unattended_daily_cycle_for_test(
        object(), _OBSERVED, dependencies
    )
    assert (
        result.classification
        is PersonalDesktopUnattendedDailyCycleClassification.BLOCKED
    )


def test_result_is_frozen_and_contains_no_authority_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = run_personal_desktop_unattended_daily_cycle_for_test(
        object(), _OBSERVED, _dependencies(monkeypatch)
    )
    with pytest.raises(FrozenInstanceError):
        result.classification = (
            PersonalDesktopUnattendedDailyCycleClassification.BLOCKED
        )
    assert not {
        "permit",
        "capability",
        "credential",
        "path",
        "handle",
        "connection",
    }.intersection(result.__dataclass_fields__)
