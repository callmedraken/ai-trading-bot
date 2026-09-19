"""Zero-semantic-argument D6 source-checkout launcher."""

from __future__ import annotations

import argparse
import json
import sys

from trading_bot.runtime.personal_desktop_unattended_decision_publication import (
    PersonalDesktopUnattendedDecisionPublicationClassification as Status,
)
from trading_bot.runtime.personal_desktop_unattended_decision_publication import (
    PersonalDesktopUnattendedDecisionPublicationResult,
    run_personal_desktop_unattended_decision_publication,
)

_SCHEMA = "personal-desktop-unattended-decision-publication-launcher/v1"


class _CliUsageError(ValueError):
    pass


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise _CliUsageError("invalid decision publication arguments")


def build_parser() -> argparse.ArgumentParser:
    """Accept no semantic trading overrides."""

    return _SanitizedArgumentParser(
        prog="run_personal_desktop_unattended_decision_publication",
        description="Run the frozen PD4-D6 zero-argument decision-only launcher.",
    )


def main(argv: list[str] | None = None) -> int:
    """Invoke D6 once; sanitized output and exit codes are diagnostic only."""

    try:
        build_parser().parse_args(argv)
    except _CliUsageError:
        print(
            json.dumps({"schema": _SCHEMA, "reason": "INVALID_ARGUMENTS"}),
            file=sys.stderr,
        )
        return 2
    try:
        result = run_personal_desktop_unattended_decision_publication()
        if type(result) is not PersonalDesktopUnattendedDecisionPublicationResult:
            raise ValueError("invalid publication result")
        record = {
            "schema": _SCHEMA,
            "classification": result.classification.value,
            "decision_id": None
            if result.decision_id is None
            else str(result.decision_id),
            "selected_session": None
            if result.selected_session is None
            else result.selected_session.session_date.isoformat(),
            "intended_execution_session": None
            if result.intended_execution_session is None
            else result.intended_execution_session.session_date.isoformat(),
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
        in (
            Status.DECISION_NOT_READY,
            Status.DECISION_PUBLISHED,
            Status.DECISION_ALREADY_FINALIZED,
        )
        else 6
    )


if __name__ == "__main__":
    raise SystemExit(main())
