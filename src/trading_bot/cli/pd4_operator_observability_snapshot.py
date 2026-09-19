"""PD4 O2 zero-semantic-argument operator observability snapshot CLI."""

from __future__ import annotations

import argparse
import json
import sys

from trading_bot.runtime.operator_observability_snapshot import (
    OperatorObservabilitySnapshotResult,
    read_personal_desktop_operator_observability_snapshot,
)

_SCHEMA = "personal-desktop-operator-observability-snapshot/v1"
_EXIT_USAGE = 2
_EXIT_BLOCKED = 5
_EXIT_ATTENTION = 6

_ATTENTION_CLASSIFICATIONS = frozenset(
    {
        "BLOCKED",
        "SESSION_GAP",
        "PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS",
        "RECEIPT_RECOVERY_REQUIRED",
        "MISSED_DECISION_DEADLINE",
    }
)


class _CliUsageError(ValueError):
    pass


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise _CliUsageError("invalid operator observability arguments")


def build_parser() -> argparse.ArgumentParser:
    """Accept no caller-selected authority, session, path, or effect option."""

    return _SanitizedArgumentParser(
        prog="run_personal_desktop_operator_observability_snapshot",
        description=(
            "Read one effects-closed PD4 operator observability snapshot."
        ),
        allow_abbrev=False,
    )


def diagnostic_record(
    result: OperatorObservabilitySnapshotResult,
) -> dict[str, object]:
    """Serialize one bounded non-authorizing O2 snapshot."""

    if type(result) is not OperatorObservabilitySnapshotResult:
        raise ValueError("operator observability result is invalid")
    result.__post_init__()

    warmup: dict[str, object] | None = None
    if result.warmup is not None:
        warmup = {
            "classification": result.warmup.classification.value,
            "target_count": result.warmup.target_count,
            "selected_count": result.warmup.selected_count,
            "required_sessions": [
                value.isoformat() for value in result.warmup.required_sessions
            ],
            "missing_sessions": [
                value.isoformat() for value in result.warmup.missing_sessions
            ],
            "selected_sessions": [
                {
                    "session": item.session_date.isoformat(),
                    "symbol": item.symbol,
                    "close": str(item.close),
                    "snapshot_id": str(item.snapshot_id),
                    "selection_id": str(item.selection_id),
                }
                for item in result.warmup.selected_sessions
            ],
        }

    account = {
        "paper_account_id": result.account.paper_account_id,
        "checkpoint_id": str(result.account.checkpoint_id),
        "sequence": result.account.sequence,
        "as_of": result.account.as_of.isoformat(),
        "cash": str(result.account.cash),
        "realized_profit_loss": str(result.account.realized_profit_loss),
        "lineage_edge_count": result.account.lineage_edge_count,
        "receipt_count": result.account.receipt_count,
        "positions": [
            {
                "symbol": item.symbol,
                "quantity": str(item.quantity),
                "total_cost_basis": str(item.total_cost_basis),
                "average_cost": str(item.average_cost),
            }
            for item in result.account.positions
        ],
    }

    gates = {
        "market_data_capture": result.gates.market_data_capture,
        "decision_publication": result.gates.decision_publication,
        "production": result.gates.production,
        "recovery": result.gates.recovery,
        "supervised_execution": result.gates.supervised_execution,
        "receipt_recovery": result.gates.receipt_recovery,
        "unattended_execution": result.gates.unattended_execution,
        "unattended_storage_provisioning": (
            result.gates.unattended_storage_provisioning
        ),
        "all_closed": result.gates.all_closed,
    }

    return {
        "schema": _SCHEMA,
        "cycle_classification": result.cycle_classification.value,
        "completed_session": (
            result.completed_session.session_date.isoformat()
            if result.completed_session is not None
            else None
        ),
        "market_data_classification": (
            result.market_data_classification.value
            if result.market_data_classification is not None
            else None
        ),
        "selected_snapshot_id": (
            str(result.selected_snapshot_id)
            if result.selected_snapshot_id is not None
            else None
        ),
        "warmup": warmup,
        "account": account,
        "gates": gates,
        "real_effect_performed": result.real_effect_performed,
    }


def main(argv: list[str] | None = None) -> int:
    """Print bounded read-only diagnostics; exit status grants no authority."""

    try:
        build_parser().parse_args(argv)
    except _CliUsageError:
        print(
            json.dumps(
                {
                    "schema": _SCHEMA,
                    "reason": "INVALID_ARGUMENTS",
                    "real_effect_performed": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return _EXIT_USAGE

    try:
        result = read_personal_desktop_operator_observability_snapshot()
        record = diagnostic_record(result)
    except Exception:
        print(
            json.dumps(
                {
                    "schema": _SCHEMA,
                    "reason": "VALIDATION_BLOCKED",
                    "real_effect_performed": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return _EXIT_BLOCKED

    print(json.dumps(record, sort_keys=True, separators=(",", ":")))
    return (
        _EXIT_ATTENTION
        if result.cycle_classification.value in _ATTENTION_CLASSIFICATIONS
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
