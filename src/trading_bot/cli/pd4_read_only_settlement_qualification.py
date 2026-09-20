"""D8-A sanitized zero-semantic-argument settlement qualification CLI."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields
from enum import StrEnum
from uuid import UUID

from trading_bot.market_calendar import TradingSession
from trading_bot.runtime.personal_desktop_unattended_settlement_qualification import (
    SettlementQualificationResult,
    Status,
    qualify_personal_desktop_unattended_settlement,
)

_SCHEMA = "personal-desktop-read-only-settlement-qualification/v1"


class _CliUsageError(ValueError):
    pass


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise _CliUsageError("invalid D8-A arguments")


def build_parser() -> argparse.ArgumentParser:
    """Accept no caller-selected trading facts or effects."""

    return _SanitizedArgumentParser(
        prog="run_personal_desktop_read_only_settlement_qualification",
        description=(
            "Qualify one completed unattended settlement with every effect closed."
        ),
        allow_abbrev=False,
    )


def diagnostic_record(result: SettlementQualificationResult) -> dict[str, object]:
    """Emit bounded non-authorizing evidence in deterministic JSON order."""

    if type(result) is not SettlementQualificationResult:
        raise ValueError("D8-A result is invalid")
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
    """Print diagnostics only; an exit code is never execution authority."""

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
        result = qualify_personal_desktop_unattended_settlement()
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
    return 0 if result.classification is not Status.BLOCKED else 6


if __name__ == "__main__":
    raise SystemExit(main())
