"""PD4 D7-A sanitized zero-semantic-argument read-only diagnostic CLI."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from trading_bot.market_calendar import TradingSession
from trading_bot.runtime.personal_desktop_unattended_decision_qualification import (
    UnattendedDecisionQualificationClassification as Status,
)
from trading_bot.runtime.personal_desktop_unattended_decision_qualification import (
    UnattendedDecisionQualificationResult,
    qualify_personal_desktop_unattended_decision,
)

_SCHEMA = "personal-desktop-read-only-decision-qualification/v1"


class _CliUsageError(ValueError):
    pass


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _CliUsageError("invalid D7-A arguments")


def build_parser() -> argparse.ArgumentParser:
    """Accept no semantic authority or overrides."""
    return _SanitizedArgumentParser(
        prog="run_personal_desktop_read_only_decision_qualification",
        description="Observe PD4 D7-A decision qualification with all effects closed.",
        allow_abbrev=False,
    )


def diagnostic_record(
    result: UnattendedDecisionQualificationResult,
) -> dict[str, object]:
    """Serialize only bounded diagnostic fields in canonical JSON order."""
    if type(result) is not UnattendedDecisionQualificationResult:
        raise ValueError("D7-A result is invalid")
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
    """Read-only evidence and exit codes never authorize D7-C."""
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
        result = qualify_personal_desktop_unattended_decision()
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
    return (
        0
        if result.classification
        in (Status.READY, Status.ALREADY_FINALIZED, Status.WARMING_UP)
        else 6
    )


if __name__ == "__main__":
    raise SystemExit(main())
