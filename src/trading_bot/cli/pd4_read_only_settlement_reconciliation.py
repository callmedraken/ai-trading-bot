"""D9-A zero-semantic-argument, sanitized settlement reconciliation CLI."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields
from enum import StrEnum
from uuid import UUID

from trading_bot.market_calendar import TradingSession
from trading_bot.runtime.personal_desktop_unattended_settlement_reconciliation import (
    SettlementReconciliationResult,
    Status,
    reconcile_personal_desktop_unattended_settlement,
)

_SCHEMA = "personal-desktop-read-only-settlement-reconciliation/v1"


class _CliUsageError(ValueError):
    pass


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise _CliUsageError("invalid D9-A arguments")


def build_parser() -> argparse.ArgumentParser:
    """Accept no caller-selected session, authority, path, or effect option."""

    return _SanitizedArgumentParser(
        prog="run_personal_desktop_read_only_settlement_reconciliation",
        description=(
            "Reconcile one completed unattended settlement with all effects closed."
        ),
        allow_abbrev=False,
    )


def diagnostic_record(result: SettlementReconciliationResult) -> dict[str, object]:
    """Return bounded non-authorizing evidence in deterministic JSON order."""

    if type(result) is not SettlementReconciliationResult:
        raise ValueError("D9-A result is invalid")
    result.__post_init__()
    record: dict[str, object] = {"schema": _SCHEMA}
    for field in fields(result):
        value = getattr(result, field.name)
        if isinstance(value, (UUID, StrEnum)):
            value = str(value)
        elif isinstance(value, TradingSession):
            value = value.session_date.isoformat()
        record[field.name] = value
    return record


def main(argv: list[str] | None = None) -> int:
    """Print diagnostics only; only an exact RECONCILED result exits zero."""

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
        result = reconcile_personal_desktop_unattended_settlement()
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
