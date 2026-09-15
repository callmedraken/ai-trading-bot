"""Zero-argument Architecture-112 D5 capture-only warm-up launcher."""

from __future__ import annotations

import argparse
import json
import sys

from trading_bot.runtime import (
    personal_desktop_unattended_capture_warmup_scheduler_contract as d5_contract,
)
from trading_bot.runtime.personal_desktop_unattended_capture_warmup import (
    PersonalDesktopUnattendedCaptureWarmupGateState,
    PersonalDesktopUnattendedCaptureWarmupResult,
    personal_desktop_unattended_capture_warmup_gate_state,
    run_personal_desktop_unattended_capture_warmup,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle import (
    PersonalDesktopUnattendedDailyCycleClassification,
)

_SCHEMA = "personal-desktop-unattended-capture-warmup-launcher/v1"
_EXIT_USAGE = 2
_EXIT_CONTRACT = 3
_EXIT_GATE = 4
_EXIT_RESULT = 5
_EXIT_UNSAFE_CLASSIFICATION = 6

_SAFE_CLASSIFICATIONS = frozenset(
    {
        PersonalDesktopUnattendedDailyCycleClassification.WARMING_UP,
        PersonalDesktopUnattendedDailyCycleClassification.DECISION_READY,
    }
)


class _CliUsageError(ValueError):
    pass


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise _CliUsageError("invalid capture warm-up launcher arguments")


def build_parser() -> argparse.ArgumentParser:
    """Build the D5 parser, which accepts no semantic arguments."""

    return _SanitizedArgumentParser(
        prog="run_personal_desktop_unattended_capture_warmup",
        description=(
            "Run the frozen PD4-D5 zero-argument capture-only warm-up launcher."
        ),
    )


def _all_effect_gates_are_closed(state: object) -> bool:
    return type(state) is PersonalDesktopUnattendedCaptureWarmupGateState and all(
        type(value) is bool and value is False
        for value in (
            state.market_data_capture,
            state.decision_publication,
            state.production,
            state.recovery,
            state.supervised_execution,
            state.receipt_recovery,
            state.unattended_execution,
            state.unattended_storage_provisioning,
        )
    )


def _emit(record: dict[str, object], *, stream: object | None = None) -> None:
    print(
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        file=sys.stdout if stream is None else stream,
    )


def _sanitized_result_record(result: object) -> dict[str, object]:
    if type(result) is not PersonalDesktopUnattendedCaptureWarmupResult:
        raise ValueError("capture warm-up result type is invalid")
    return {
        "capture_performed": result.capture_performed,
        "classification": result.classification.value,
        "completed_session": (
            result.completed_session.session_date.isoformat()
            if result.completed_session is not None
            else None
        ),
        "cycle_classification": (
            result.cycle_classification.value
            if result.cycle_classification is not None
            else None
        ),
        "market_data_classification": (
            result.market_data_classification.value
            if result.market_data_classification is not None
            else None
        ),
        "provider_attempt_may_have_occurred": (
            result.provider_attempt_may_have_occurred
        ),
        "real_effect_performed": result.real_effect_performed,
        "scheduler_modified": False,
        "schema": _SCHEMA,
        "status": "CAPTURE_WARMUP",
    }


def main(argv: list[str] | None = None) -> int:
    """Run exactly one D5 capture-only wake after closed-state validation."""

    try:
        build_parser().parse_args(argv)
    except _CliUsageError:
        _emit({"reason": "INVALID_ARGUMENTS", "schema": _SCHEMA}, stream=sys.stderr)
        return _EXIT_USAGE

    contract = d5_contract.personal_desktop_unattended_capture_warmup_scheduler_contract()
    if not d5_contract.is_frozen_personal_desktop_unattended_capture_warmup_scheduler_contract(
        contract
    ):
        _emit(
            {"reason": "SCHEDULER_CONTRACT_INVALID", "schema": _SCHEMA},
            stream=sys.stderr,
        )
        return _EXIT_CONTRACT

    try:
        initial_gates = personal_desktop_unattended_capture_warmup_gate_state()
    except Exception:
        initial_gates = None
    if not _all_effect_gates_are_closed(initial_gates):
        _emit(
            {"reason": "EFFECT_GATE_STATE_INVALID", "schema": _SCHEMA},
            stream=sys.stderr,
        )
        return _EXIT_GATE

    try:
        result = run_personal_desktop_unattended_capture_warmup()
        record = _sanitized_result_record(result)
    except Exception:
        _emit(
            {"reason": "CAPTURE_WARMUP_RESULT_INVALID", "schema": _SCHEMA},
            stream=sys.stderr,
        )
        return _EXIT_RESULT

    _emit(record)
    if result.classification not in _SAFE_CLASSIFICATIONS:
        return _EXIT_UNSAFE_CLASSIFICATION
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
