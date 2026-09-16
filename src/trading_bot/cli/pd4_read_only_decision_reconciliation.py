"""PD4 D7-D sanitized zero-semantic-argument reconciliation CLI."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from trading_bot.market_calendar import TradingSession
from trading_bot.runtime.personal_desktop_unattended_decision_reconciliation import (
    Status,
    UnattendedDecisionReconciliationResult,
    reconcile_personal_desktop_unattended_decision,
)

_SCHEMA = "personal-desktop-read-only-decision-reconciliation/v1"


class _CliUsageError(ValueError):
    pass


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _CliUsageError("invalid D7-D arguments")


def build_parser() -> argparse.ArgumentParser:
    """Accept no semantic authority, identity, session, path, or effect input."""

    return _SanitizedArgumentParser(
        prog="run_personal_desktop_read_only_decision_reconciliation",
        description=(
            "Reconcile PD4 D7-D finalized-decision state with all effects closed."
        ),
        allow_abbrev=False,
    )


def diagnostic_record(
    result: UnattendedDecisionReconciliationResult,
) -> dict[str, object]:
    """Serialize only bounded diagnostic evidence in canonical JSON order."""

    if type(result) is not UnattendedDecisionReconciliationResult:
        raise ValueError("D7-D result is invalid")
    result.__post_init__()
    record: dict[str, object] = {"schema": _SCHEMA}
    for field in fields(result):
        key, value = field.name, getattr(result, field.name)
        if isinstance(value, (UUID, StrEnum)):
            value = str(value)
        elif isinstance(value, datetime):
            value = value.isoformat()
        elif isinstance(value, TradingSession):
            value = value.session_date.isoformat()
        record[key] = value
    return record


def main(argv: list[str] | None = None) -> int:
    """Emit diagnostics only; exit status is never reconciliation authority."""

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
        return 2
    try:
        result = reconcile_personal_desktop_unattended_decision()
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
        return 5
    print(json.dumps(record, sort_keys=True, separators=(",", ":")))
    return 0 if result.classification is Status.RECONCILED else 6


if __name__ == "__main__":
    raise SystemExit(main())
