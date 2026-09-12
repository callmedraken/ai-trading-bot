"""Effects-closed PD4-E zero-semantic-argument production entry point."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass

from trading_bot.runtime.personal_desktop_paper_account_security import (
    PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED,
    PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED,
)
from trading_bot.runtime.personal_desktop_paper_receipt_recovery_execution import (
    PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED,
)
from trading_bot.runtime.personal_desktop_supervised_paper_operation_execution import (
    PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED,
)
from trading_bot.runtime.personal_desktop_unattended_paper_operation_execution import (
    PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED,
)
from trading_bot.runtime.personal_desktop_unattended_paper_storage_provisioning import (
    PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED,
)
from trading_bot.runtime.personal_desktop_unattended_scheduler_contract import (
    is_frozen_personal_desktop_unattended_scheduler_contract,
    personal_desktop_unattended_scheduler_contract,
)

_SCHEMA = "personal-desktop-unattended-paper-launcher/v1"
_EXIT_USAGE = 2
_EXIT_CONTRACT = 3
_EXIT_GATE = 4


class _CliUsageError(ValueError):
    pass


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise _CliUsageError("invalid unattended launcher arguments")


@dataclass(frozen=True, slots=True)
class _EffectGateState:
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
            "Validate the frozen PD4-E unattended launcher contract with all "
            "Paper-v2 effects closed."
        ),
    )


def _effect_gate_state() -> _EffectGateState:
    return _EffectGateState(
        PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED,
        PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED,
        PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED,
        PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED,
        PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED,
        PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED,
    )


def _all_effect_gates_are_closed(state: _EffectGateState | None = None) -> bool:
    observed = _effect_gate_state() if state is None else state
    return type(observed) is _EffectGateState and all(
        type(value) is bool and value is False
        for value in (
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


def main(argv: list[str] | None = None) -> int:
    """Validate the source-only boundary without deriving semantic authority."""

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
    _emit(
        {
            "diagnostic": "SOURCE_ONLY_ZERO_ARGUMENT_BOUNDARY",
            "execution_performed": False,
            "invocation_published": False,
            "qualification_performed": False,
            "recovery_performed": False,
            "schema": _SCHEMA,
            "scheduler_modified": False,
            "status": "EFFECTS_CLOSED",
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
