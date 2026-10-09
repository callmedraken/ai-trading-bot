"""133-S sanitized, read-only parent-security diagnosis; no effect adapters."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from trading_bot.arch133_acl import read_only
from trading_bot.arch133_parent_security_diagnostic import admission
from trading_bot.arch133_reprovision import namespace
from trading_bot.arch133_reprovision.material import (
    read_material,
    require_fresh,
    require_stale,
)

SCHEMA = "arch133s-parent-security-diagnostic/v1"
ZERO_EFFECTS = (
    "credential_reads",
    "credential_writes",
    "provider_calls",
    "scheduler_reads",
    "scheduler_writes",
    "publication_writes",
    "archive_writes",
    "paper_mutations",
    "state_mutations",
    "acl_mutations",
    "wake_delegations",
    "execution_delegations",
    "consumed_wake_authority",
    "broker_effects",
    "manual_task_starts",
)
PREDECESSOR_STAGES = (
    "PREDECESSOR_RUNTIME",
    "PREDECESSOR_ADMINISTRATOR",
    "PREDECESSOR_ROOT",
    "PREDECESSOR_NAMESPACE",
    "PREDECESSOR_FILES",
    "PREDECESSOR_PUBLICATION_PATH",
    "PREDECESSOR_PUBLICATION_PARSE",
    "PREDECESSOR_PUBLICATION_SEMANTICS",
    "PREDECESSOR_STATE_PATH",
    "PREDECESSOR_STATE",
    "PREDECESSOR_PAPER",
    "PREDECESSOR_FINAL_REOBSERVATION",
    "PREDECESSOR_RUNTIME_REOBSERVATION",
    "PREDECESSOR_ADMINISTRATOR_REOBSERVATION",
)
VOLUME_STAGES = (
    "PARENT_VOLUME_OPEN",
    "PARENT_VOLUME_OBSERVE",
    "PARENT_VOLUME_FILESYSTEM",
    "PARENT_VOLUME_REPARSE",
    "PARENT_VOLUME_OWNER",
    "PARENT_VOLUME_ACL",
    "PARENT_VOLUME_REOBSERVATION",
    "PARENT_VOLUME_CLOSE",
)
HOST_STAGES = (
    "PARENT_HOST_OPEN",
    "PARENT_HOST_OBSERVE",
    "PARENT_HOST_FILESYSTEM",
    "PARENT_HOST_REPARSE",
    "PARENT_HOST_OWNER",
    "PARENT_HOST_ACL",
    "PARENT_HOST_REOBSERVATION",
    "PARENT_HOST_CLOSE",
)
COMBINED_STAGES = (
    "PARENT_COMBINED_VOLUME_OPEN",
    "PARENT_COMBINED_VOLUME_OBSERVE",
    "PARENT_COMBINED_VOLUME_POLICY",
    "PARENT_COMBINED_HOST_OPEN",
    "PARENT_COMBINED_HOST_OBSERVE",
    "PARENT_COMBINED_HOST_POLICY",
    "PARENT_COMBINED_VOLUME_REOBSERVATION",
    "PARENT_COMBINED_HOST_REOBSERVATION",
    "PARENT_COMBINED_HOST_CLOSE",
    "PARENT_COMBINED_VOLUME_CLOSE",
)
STAGES = (
    "ARGUMENTS",
    "MATERIAL_READ",
    "PREDECESSOR_ADMISSION",
    *PREDECESSOR_STAGES,
    "PREDECESSOR_MATERIAL",
    "PREDECESSOR_STALE",
    "FRESH_MATERIAL",
    "NAMESPACE_VACANCY",
    *VOLUME_STAGES,
    *HOST_STAGES,
    *COMBINED_STAGES,
    "ADMISSION_COMPLETE",
)


class ParentStageError(RuntimeError):
    """Internal fixed marker, without observation or exception details."""

    def __init__(self, stage: str) -> None:
        super().__init__(stage)
        self.stage = stage


def _stage(stage, function, /, *args):
    try:
        return function(*args)
    except BaseException:
        raise ParentStageError(stage) from None


def _require(condition: bool) -> None:
    if not condition:
        raise ValueError


def _filesystem(observation) -> None:
    _require(observation.filesystem == "NTFS")


def _reparse(observation) -> None:
    _require(observation.reparse is False)


def _owner(observation) -> None:
    _require(observation.owner_sid == read_only.ADMINISTRATORS_SID)


def _acl(observation) -> None:
    _require(
        not any(
            sid not in (read_only.ADMINISTRATORS_SID, read_only.SYSTEM_SID)
            and not flags & 8
            and mask & 0xD0046
            for sid, mask, _, flags in observation.aces
        )
    )


def _policy(observation) -> None:
    for predicate in (_filesystem, _reparse, _owner, _acl):
        predicate(observation)


def _unchanged(handle, path, expected) -> None:
    _require(read_only.inspect_directory_security(handle, path) == expected)


def _parent(path: str, stages: tuple[str, ...]) -> None:
    handle = _stage(stages[0], read_only.open_directory, path)
    try:
        observed = _stage(stages[1], read_only.inspect_directory_security, handle, path)
        for stage, predicate in zip(
            stages[2:6], (_filesystem, _reparse, _owner, _acl), strict=True
        ):
            _stage(stage, predicate, observed[0])
        _stage(stages[6], _unchanged, handle, path, observed)
    finally:
        # Exactly one attempt after successful acquisition. A close rejection
        # deliberately takes precedence over an earlier policy/observation error.
        _stage(stages[7], read_only.close_handle, handle)


def _combined() -> None:
    held = []
    try:
        for path, stages in (
            ("F:\\", COMBINED_STAGES[:3]),
            (r"F:\AITradingBot", COMBINED_STAGES[3:6]),
        ):
            handle = _stage(stages[0], read_only.open_directory, path)
            # Register cleanup before any observation or policy can fail.
            held.append((path, handle))
            observed = _stage(
                stages[1], read_only.inspect_directory_security, handle, path
            )
            _stage(stages[2], _policy, observed[0])
            held[-1] = (path, handle, observed)
        for stage, (path, handle, observed) in zip(
            COMBINED_STAGES[6:8], held, strict=True
        ):
            _stage(stage, _unchanged, handle, path, observed)
    finally:
        first_close_failure = None
        for item in reversed(held):
            path, handle = item[:2]
            stage = COMBINED_STAGES[8 if path == r"F:\AITradingBot" else 9]
            try:
                _stage(stage, read_only.close_handle, handle)
            except ParentStageError as error:
                # Attempt all remaining closes even when one close fails.
                if first_close_failure is None:
                    first_close_failure = error
        if first_close_failure is not None:
            raise first_close_failure from None


def stage_result(stage: str, *, passed: bool = False) -> dict:
    if stage not in STAGES or (passed and stage != "ADMISSION_COMPLETE"):
        stage, passed = "PREDECESSOR_ADMISSION", False
    return {
        "schema": SCHEMA,
        "status": "PASS" if passed else "BLOCKED",
        "reason": (
            "PARENT_SECURITY_DIAGNOSTIC_COMPLETE"
            if passed
            else "PARENT_SECURITY_DIAGNOSTIC_BLOCKED"
        ),
        "stage": stage,
        **dict.fromkeys(ZERO_EFFECTS, 0),
    }


def diagnose(path: Path) -> dict:
    stage = "MATERIAL_READ"
    try:
        material = read_material(path)
        stage = "PREDECESSOR_ADMISSION"
        old, facts = admission.observe_predecessor()
        stage = "PREDECESSOR_MATERIAL"
        admission.require_retained(old)
        stage = "PREDECESSOR_STALE"
        require_stale(old, datetime.now(UTC))
        stage = "FRESH_MATERIAL"
        require_fresh(material, old, facts["runtime"], datetime.now(UTC))
        stage = "NAMESPACE_VACANCY"
        namespace.require_vacant()
        _parent("F:\\", VOLUME_STAGES)
        _parent(r"F:\AITradingBot", HOST_STAGES)
        _combined()
        return stage_result("ADMISSION_COMPLETE", passed=True)
    except admission.AdmissionStageError as error:
        return stage_result(error.stage if error.stage in PREDECESSOR_STAGES else stage)
    except ParentStageError as error:
        return stage_result(error.stage)
    except BaseException:
        return stage_result(stage)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if (
        len(args) != 2
        or args[0] != "--material-file"
        or not Path(args[1]).is_absolute()
    ):
        result = stage_result("ARGUMENTS")
    else:
        result = diagnose(Path(args[1]))
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0 if result["status"] == "PASS" else 3
