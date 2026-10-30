"""Bounded nonsecret partial-state evidence; no acquisition or write authority."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable

from trading_bot.experiments.historical_research_native_custody import (
    ADMIN,
    CUSTODY_PARENT,
    SYSTEM,
    CustodyPartialState,
    WindowsCustodyNative,
)
from trading_bot.runtime.windows_authority_security import AuthorityObjectKind

CLASSIFICATIONS = frozenset(
    {
        "PARTIAL_STATE_OBSERVED_EXACT",
        "HOST_PARENT_UNAVAILABLE",
        "HOST_PARENT_POLICY",
        "HOST_VOLUME_POLICY",
        "HOST_REPARSE_OR_ALIAS",
        "HOST_CLAIM_PRESENT",
        "HOST_PROTECTED_ROOT_PRESENT",
        "HOST_OPEN_PARENT_PRESENT",
        "HOST_OPEN_ROOT_PRESENT",
        "HOST_STATE_DRIFT",
        "HOST_CLOSE_AMBIGUITY",
        "HOST_UNKNOWN",
    }
)
EFFECT_COUNTERS = (
    "credential_secret_reads",
    "provider_calls",
    "data_reads",
    "writes",
    "files_created",
    "directories_created",
    "files_deleted",
    "directories_deleted",
    "acl_mutations",
    "scheduler_operations",
    "paper_mutations",
    "broker_placements",
    "live_effects",
)


def _classification(state: CustodyPartialState) -> str:
    if state.close_ambiguous:
        return "HOST_CLOSE_AMBIGUITY"
    if state.classification != "OBSERVED":
        return (
            state.classification
            if state.classification
            in CLASSIFICATIONS - {"PARTIAL_STATE_OBSERVED_EXACT"}
            else "HOST_UNKNOWN"
        )
    parent = state.parent
    if parent is None:
        return "HOST_PARENT_UNAVAILABLE"
    if (
        parent.expected_path != CUSTODY_PARENT
        or parent.final_path.casefold() != CUSTODY_PARENT.casefold()
        or parent.is_reparse_point is not False
    ):
        return "HOST_REPARSE_OR_ALIAS"
    if (
        state.local_fixed is not True
        or parent.volume_root.casefold() != "f:\\"
        or parent.filesystem.upper() != "NTFS"
    ):
        return "HOST_VOLUME_POLICY"
    actual = tuple(
        (ace.principal_sid, ace.access_mask, ace.ace_type, ace.ace_flags)
        for ace in parent.aces
    )
    if (
        parent.kind is not AuthorityObjectKind.DIRECTORY
        or parent.owner_sid != ADMIN
        or parent.dacl_protected is not True
        or Counter(actual)
        != Counter(((ADMIN, 0x1F01FF, 0, 3), (SYSTEM, 0x1F01FF, 0, 3)))
    ):
        return "HOST_PARENT_POLICY"
    if len(state.absent) != 4 or any(type(value) is not bool for value in state.absent):
        return "HOST_UNKNOWN"
    for absent, code in zip(
        state.absent,
        (
            "HOST_CLAIM_PRESENT",
            "HOST_PROTECTED_ROOT_PRESENT",
            "HOST_OPEN_PARENT_PRESENT",
            "HOST_OPEN_ROOT_PRESENT",
        ),
        strict=True,
    ):
        if not absent:
            return code
    return "PARTIAL_STATE_OBSERVED_EXACT"


def _observe(observe: Callable[[], CustodyPartialState]) -> CustodyPartialState:
    try:
        state = observe()
        if type(state) is CustodyPartialState:
            return state
    except Exception:
        pass
    return CustodyPartialState("HOST_UNKNOWN")


def partial_state_readonly_preflight(
    *, observe: Callable[[], CustodyPartialState] | None = None
) -> dict[str, object]:
    """Observe twice; only the registered runner supplies source/evidence binding.

    Injection is a fake-native test seam. This result cannot mint a B2 readiness
    or credential capability. Failed observations disclose only closed codes.
    """
    if observe is None:
        observe = WindowsCustodyNative().observe_partial_state_readonly
    first, second = _observe(observe), _observe(observe)
    try:
        codes = (_classification(first), _classification(second))
        if "HOST_CLOSE_AMBIGUITY" in codes:
            code = "HOST_CLOSE_AMBIGUITY"
        elif first != second:
            code = "HOST_STATE_DRIFT"
        else:
            code = codes[0]
    except Exception:
        code = "HOST_UNKNOWN"
    passed = code == "PARTIAL_STATE_OBSERVED_EXACT"
    parent = first.parent if passed else None
    return {
        "schema": "historical-research-partial-state-observer/v1",
        "status": "PASS" if passed else "BLOCKED",
        "classification": code,
        "parent_path": CUSTODY_PARENT,
        "parent_kind": parent.kind.value if parent else None,
        "filesystem": parent.filesystem if parent else None,
        "volume_root": parent.volume_root if parent else None,
        "local_fixed": first.local_fixed if passed else None,
        "non_reparse": not parent.is_reparse_point if parent else None,
        "owner_sid": parent.owner_sid if parent else None,
        "dacl_protected": parent.dacl_protected if parent else None,
        "ace_multiset": [
            [ace.principal_sid, ace.access_mask, ace.ace_type, ace.ace_flags]
            for ace in parent.aces
        ]
        if parent
        else None,
        "claim_absent": first.absent[0] if passed else None,
        "protected_root_absent": first.absent[1] if passed else None,
        "open_parent_absent": first.absent[2] if passed else None,
        "open_root_absent": first.absent[3] if passed else None,
        "stable_repetitions": 2 if first == second else 0,
        **dict.fromkeys(EFFECT_COUNTERS, 0),
        "acquisition_authorized": False,
        "open_parent_creation_authorized": False,
        "protected_execution": "NOT_AUTHORIZED",
    }
