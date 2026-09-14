"""Effects-closed PD4-D2 zero-argument daily-cycle launcher."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass

from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime import (
    personal_desktop_paper_receipt_recovery_execution as receipt_recovery,
)
from trading_bot.runtime import (
    personal_desktop_supervised_paper_operation_execution as supervised_execution,
)
from trading_bot.runtime import (
    personal_desktop_unattended_market_data_capture as market_data_capture,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_decision_publication as decision_publication,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_operation_execution as unattended_execution,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_storage_provisioning as storage_provisioning,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle import (
    PersonalDesktopUnattendedDailyCycleClassification,
    PersonalDesktopUnattendedDailyCycleResult,
    run_personal_desktop_unattended_daily_cycle,
)
from trading_bot.runtime.personal_desktop_unattended_scheduler_contract import (
    is_frozen_personal_desktop_unattended_scheduler_contract,
    personal_desktop_unattended_scheduler_contract,
)

_SCHEMA = "personal-desktop-unattended-paper-launcher/v2"
_EXIT_USAGE = 2
_EXIT_CONTRACT = 3
_EXIT_GATE = 4
_EXIT_RESULT = 5
_EXIT_UNSAFE_CLASSIFICATION = 6

# Exit status is diagnostic only. The frozen task has no automatic retry, and
# neither its exit status nor Task Scheduler history grants retry authority.
_UNSAFE_CLASSIFICATIONS = frozenset(
    {
        PersonalDesktopUnattendedDailyCycleClassification.BLOCKED,
        PersonalDesktopUnattendedDailyCycleClassification.SESSION_GAP,
        PersonalDesktopUnattendedDailyCycleClassification.RECEIPT_RECOVERY_REQUIRED,
        PersonalDesktopUnattendedDailyCycleClassification.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS,
        PersonalDesktopUnattendedDailyCycleClassification.MISSED_DECISION_DEADLINE,
    }
)


class _CliUsageError(ValueError):
    pass


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise _CliUsageError("invalid unattended launcher arguments")


@dataclass(frozen=True, slots=True)
class _EffectGateState:
    market_data_capture: bool
    decision_publication: bool
    production: bool
    recovery: bool
    supervised_execution: bool
    receipt_recovery: bool
    unattended_execution: bool
    unattended_storage_provisioning: bool


def build_parser() -> argparse.ArgumentParser:
    """Build the production parser, which has no semantic arguments."""

    return _SanitizedArgumentParser(
        prog="run_personal_desktop_unattended_paper_operation",
        description=(
            "Run the frozen PD4-D2 zero-argument daily-cycle launcher with all "
            "eight production effects closed."
        ),
    )


def _effect_gate_state() -> _EffectGateState:
    return _EffectGateState(
        market_data_capture.PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED,
        decision_publication.PERSONAL_DESKTOP_UNATTENDED_DECISION_PUBLICATION_EFFECTS_ENABLED,
        security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED,
        security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED,
        supervised_execution.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED,
        receipt_recovery.PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED,
        unattended_execution.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED,
        storage_provisioning.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED,
    )


def _all_effect_gates_are_closed(state: _EffectGateState | None = None) -> bool:
    observed = _effect_gate_state() if state is None else state
    return type(observed) is _EffectGateState and all(
        type(value) is bool and value is False
        for value in (
            observed.market_data_capture,
            observed.decision_publication,
            observed.production,
            observed.recovery,
            observed.supervised_execution,
            observed.receipt_recovery,
            observed.unattended_execution,
            observed.unattended_storage_provisioning,
        )
    )


def _emit(record: dict[str, object], *, stream: object | None = None) -> None:
    print(
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        file=sys.stdout if stream is None else stream,
    )


def _sanitized_result_record(
    result: object,
) -> dict[str, object]:
    if (
        type(result) is not PersonalDesktopUnattendedDailyCycleResult
        or result.real_effect_performed is not False
    ):
        raise ValueError("daily-cycle result is not safe launcher evidence")
    return {
        "classification": result.classification.value,
        "completed_session": (
            result.completed_session.session_date.isoformat()
            if result.completed_session is not None
            else None
        ),
        "decision_publication_status": (
            result.decision_publication_status.value
            if result.decision_publication_status is not None
            else None
        ),
        "market_data_classification": (
            result.market_data_classification.value
            if result.market_data_classification is not None
            else None
        ),
        "real_effect_performed": False,
        "scheduler_modified": False,
        "schema": _SCHEMA,
        "settlement_status": (
            result.settlement_status.value
            if result.settlement_status is not None
            else None
        ),
        "status": "EFFECTS_CLOSED",
    }


def main(argv: list[str] | None = None) -> int:
    """Run G6 once after validating the frozen contract and all closed gates."""

    try:
        build_parser().parse_args(argv)
    except _CliUsageError:
        _emit({"reason": "INVALID_ARGUMENTS", "schema": _SCHEMA}, stream=sys.stderr)
        return _EXIT_USAGE
    contract = personal_desktop_unattended_scheduler_contract()
    if not is_frozen_personal_desktop_unattended_scheduler_contract(contract):
        _emit(
            {"reason": "SCHEDULER_CONTRACT_INVALID", "schema": _SCHEMA},
            stream=sys.stderr,
        )
        return _EXIT_CONTRACT
    if not _all_effect_gates_are_closed():
        _emit(
            {"reason": "EFFECT_GATE_STATE_INVALID", "schema": _SCHEMA},
            stream=sys.stderr,
        )
        return _EXIT_GATE
    try:
        result = run_personal_desktop_unattended_daily_cycle()
        record = _sanitized_result_record(result)
    except Exception:
        _emit(
            {"reason": "DAILY_CYCLE_RESULT_INVALID", "schema": _SCHEMA},
            stream=sys.stderr,
        )
        return _EXIT_RESULT
    _emit(record)
    if result.classification in _UNSAFE_CLASSIFICATIONS:
        return _EXIT_UNSAFE_CLASSIFICATION
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
