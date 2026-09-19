"""Pure adapters from verified PD4 runtime evidence to operator presentation models."""

from __future__ import annotations

from trading_bot.gui.operator_observability_models import (
    OPERATOR_WARMUP_TARGET_COUNT,
    OperatorEffectGateState,
    OperatorObservabilityState,
    OperatorWarmupClassification,
    OperatorWarmupView,
    SelectedC3WarmupSessionView,
)
from trading_bot.market_data import replay_verified_daily_snapshot
from trading_bot.runtime.personal_desktop_unattended_c3_history import (
    SelectedC3StrategyHistoryWindowClassification,
    SelectedC3StrategyHistoryWindowResult,
    SessionIndexedSelectedC3SnapshotReadResult,
)
from trading_bot.runtime.personal_desktop_unattended_capture_warmup import (
    PersonalDesktopUnattendedCaptureWarmupGateState,
)


class OperatorObservabilityAdapterError(ValueError):
    """Verified runtime evidence cannot be represented safely for the operator."""


_CLASSIFICATION_MAP = {
    SelectedC3StrategyHistoryWindowClassification.WARMING_UP: (
        OperatorWarmupClassification.WARMING_UP
    ),
    SelectedC3StrategyHistoryWindowClassification.READY: (
        OperatorWarmupClassification.READY
    ),
    SelectedC3StrategyHistoryWindowClassification.SESSION_GAP: (
        OperatorWarmupClassification.SESSION_GAP
    ),
    SelectedC3StrategyHistoryWindowClassification.BLOCKED: (
        OperatorWarmupClassification.BLOCKED
    ),
}


def adapt_effect_gate_state(
    state: PersonalDesktopUnattendedCaptureWarmupGateState,
) -> OperatorEffectGateState:
    """Map one exact runtime gate-state observation into immutable presentation data."""

    if type(state) is not PersonalDesktopUnattendedCaptureWarmupGateState:
        raise OperatorObservabilityAdapterError("effect-gate evidence type is invalid")
    return OperatorEffectGateState(
        market_data_capture=state.market_data_capture,
        decision_publication=state.decision_publication,
        production=state.production,
        recovery=state.recovery,
        supervised_execution=state.supervised_execution,
        receipt_recovery=state.receipt_recovery,
        unattended_execution=state.unattended_execution,
        unattended_storage_provisioning=state.unattended_storage_provisioning,
    )


def adapt_selected_c3_history_window(
    window: SelectedC3StrategyHistoryWindowResult,
) -> OperatorWarmupView:
    """Map exact selected-C3 history evidence into the bounded warm-up display."""

    if type(window) is not SelectedC3StrategyHistoryWindowResult:
        raise OperatorObservabilityAdapterError(
            "selected-C3 history evidence is invalid"
        )
    if len(window.required_sessions) != OPERATOR_WARMUP_TARGET_COUNT:
        raise OperatorObservabilityAdapterError(
            "selected-C3 history window is not the frozen six-session profile"
        )

    try:
        classification = _CLASSIFICATION_MAP[window.classification]
    except KeyError as error:
        raise OperatorObservabilityAdapterError(
            "selected-C3 history classification is unsupported"
        ) from error

    selected = tuple(_adapt_selected_session(item) for item in window.selected)
    return OperatorWarmupView(
        classification=classification,
        required_sessions=tuple(
            session.session_date for session in window.required_sessions
        ),
        selected_sessions=selected,
    )


def adapt_operator_observability_state(
    window: SelectedC3StrategyHistoryWindowResult,
    gates: PersonalDesktopUnattendedCaptureWarmupGateState,
) -> OperatorObservabilityState:
    """Compose one pure operator state from independently verified runtime evidence."""

    return OperatorObservabilityState(
        warmup=adapt_selected_c3_history_window(window),
        gates=adapt_effect_gate_state(gates),
    )


def _adapt_selected_session(
    item: SessionIndexedSelectedC3SnapshotReadResult,
) -> SelectedC3WarmupSessionView:
    if type(item) is not SessionIndexedSelectedC3SnapshotReadResult:
        raise OperatorObservabilityAdapterError(
            "selected-C3 session evidence type is invalid"
        )

    try:
        replay = replay_verified_daily_snapshot(item.selected.verification)
    except BaseException as error:
        raise OperatorObservabilityAdapterError(
            "selected-C3 snapshot could not be replayed for presentation"
        ) from error

    if (
        replay.target_session != item.session
        or len(replay.symbols) != 1
        or len(replay.bars) != 1
        or replay.bars[0].session != item.session
        or replay.bars[0].bar.symbol != replay.symbols[0]
    ):
        raise OperatorObservabilityAdapterError(
            "selected-C3 replay does not match its session-indexed evidence"
        )

    bar = replay.bars[0].bar
    audit = item.selected.audit
    if replay.snapshot_id != audit.snapshot_id:
        raise OperatorObservabilityAdapterError(
            "selected-C3 replay snapshot identity does not match audit evidence"
        )

    return SelectedC3WarmupSessionView(
        session_date=item.session.session_date,
        symbol=str(bar.symbol),
        close=bar.close,
        snapshot_id=audit.snapshot_id,
        selection_id=audit.selection_id,
    )
