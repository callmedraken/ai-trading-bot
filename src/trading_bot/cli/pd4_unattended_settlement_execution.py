"""Sanitized zero-semantic-argument D8-B settlement launcher."""

from __future__ import annotations

import argparse
import json
import sys

from trading_bot.runtime.personal_desktop_unattended_settlement_execution import (
    SettlementExecutionResult,
    Status,
    execute_personal_desktop_unattended_settlement,
)

_SCHEMA = "personal-desktop-unattended-settlement-execution-launcher/v1"


class _CliUsageError(ValueError):
    pass


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise _CliUsageError("invalid settlement arguments")


def build_parser() -> argparse.ArgumentParser:
    """Accept no caller-selected settlement facts or effect flags."""

    return _SanitizedArgumentParser(
        prog="run_personal_desktop_unattended_settlement_execution",
        description="Run one D8-B source-owned settlement attempt.",
    )


def main(argv: list[str] | None = None) -> int:
    """Invoke D8-B at most once and emit only bounded diagnostic evidence."""

    try:
        build_parser().parse_args(argv)
    except _CliUsageError:
        print(
            json.dumps({"schema": _SCHEMA, "reason": "INVALID_ARGUMENTS"}),
            file=sys.stderr,
        )
        return 2
    try:
        result = execute_personal_desktop_unattended_settlement()
        if type(result) is not SettlementExecutionResult:
            raise ValueError("invalid settlement result")
        result.__post_init__()
        record = {
            "schema": _SCHEMA,
            "classification": result.classification.value,
            "completed_execution_session": None
            if result.completed_execution_session is None
            else result.completed_execution_session.session_date.isoformat(),
            "decision_id": None
            if result.decision_id is None
            else str(result.decision_id),
            "final_plan_id": None
            if result.final_plan_id is None
            else str(result.final_plan_id),
            "invocation_id": None
            if result.invocation_id is None
            else str(result.invocation_id),
            "operation_id": None
            if result.operation_id is None
            else str(result.operation_id),
            "application_id": None
            if result.application_id is None
            else str(result.application_id),
            "account_predecessor_checkpoint_id": None
            if result.account_predecessor_checkpoint_id is None
            else str(result.account_predecessor_checkpoint_id),
            "final_checkpoint_id": None
            if result.final_checkpoint_id is None
            else str(result.final_checkpoint_id),
            "all_eight_gates_closed": result.all_eight_gates_closed,
            "real_effect_performed": result.real_effect_performed,
        }
    except Exception:
        print(
            json.dumps({"schema": _SCHEMA, "reason": "RESULT_INVALID"}), file=sys.stderr
        )
        return 5
    print(json.dumps(record, sort_keys=True, separators=(",", ":")))
    return (
        0
        if result.classification
        in {
            Status.SETTLEMENT_NOT_READY,
            Status.SETTLEMENT_COMPLETED,
            Status.SETTLEMENT_ALREADY_APPLIED,
        }
        else 6
    )


if __name__ == "__main__":
    raise SystemExit(main())
