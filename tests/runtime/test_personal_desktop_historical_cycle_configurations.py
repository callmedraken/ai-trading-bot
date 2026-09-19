"""Focused source-only coverage for G6 historical configuration authority."""

from __future__ import annotations

from hashlib import sha256

import pytest

from trading_bot.runtime import (
    personal_desktop_historical_cycle_configurations as resolver,
)
from trading_bot.runtime.personal_desktop_first_paper_operation import (
    PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE,
)
from trading_bot.runtime.personal_desktop_paper_account_security import (
    PERSONAL_DESKTOP_PAPER_V2_OPERATIONS,
    PERSONAL_DESKTOP_PAPER_V2_RUNTIME,
    PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS,
)

from .test_personal_desktop_paper_account_read_authority import (
    Observer,
    memory_case,
    read_case,
)
from .test_personal_desktop_paper_account_security import SID, MemoryReadApi
from .test_personal_desktop_unattended_paper_invocation_storage import (
    _expected,
    _put_final,
)


def _key(payload: bytes) -> tuple[str, int]:
    return sha256(payload).hexdigest(), len(payload)


def _source(payload: bytes) -> resolver._ConfigurationSource:
    return resolver._ConfigurationSource(_key(payload), payload)


def test_existing_receipt_resolves_exact_bytes_and_strict_account_read_succeeds() -> (
    None
):
    case = memory_case(1)
    required = (_key(case.configurations[0]),)

    configurations = resolver._resolve_required_configuration_payloads(
        required, (_source(case.configurations[0]),)
    )

    assert configurations == case.configurations
    assert read_case(case, configurations=configurations).receipts == tuple(
        case.receipts
    )


def test_missing_or_wrong_configuration_source_fails_closed() -> None:
    payload = b"reviewed configuration"
    required = (_key(payload),)
    with pytest.raises(
        resolver.PersonalDesktopHistoricalCycleConfigurationError,
        match="exactly one",
    ):
        resolver._resolve_required_configuration_payloads(required, ())

    with pytest.raises(
        resolver.PersonalDesktopHistoricalCycleConfigurationError,
        match="do not match their key",
    ):
        resolver._resolve_required_configuration_payloads(
            required,
            (resolver._ConfigurationSource(required[0], b"wrong configuration"),),
        )


def test_extra_source_without_receipt_is_not_returned_to_strict_account_reader() -> (
    None
):
    case = memory_case(0)

    configurations = resolver._resolve_required_configuration_payloads(
        (), (_source(b"finalized but not receipted"),)
    )

    assert configurations == ()
    assert read_case(case, configurations=configurations).receipts == ()


def test_first_and_later_receipts_resolve_exactly_both_required_plans() -> None:
    first = b"first reviewed plan"
    later = b"later finalized unattended plan"
    required = (_key(first), _key(later))

    result = resolver._resolve_required_configuration_payloads(
        required, (_source(later), _source(first))
    )

    assert result == (first, later)


def test_pending_finalized_invocation_is_filtered_by_receipt_inventory() -> None:
    installed = b"installed receipt plan"
    pending = b"finalized invocation without receipt"

    result = resolver._resolve_required_configuration_payloads(
        (_key(installed),), (_source(installed), _source(pending))
    )

    assert result == (installed,)


def test_duplicate_authoritative_source_for_one_receipt_key_blocks() -> None:
    payload = b"same exact plan"

    with pytest.raises(
        resolver.PersonalDesktopHistoricalCycleConfigurationError,
        match="exactly one",
    ):
        resolver._resolve_required_configuration_payloads(
            (_key(payload),), (_source(payload), _source(payload))
        )


def test_malformed_finalized_unattended_invocation_blocks_read_only_resolver() -> None:
    api = MemoryReadApi()
    api.trading_runtime = True
    api.put(PERSONAL_DESKTOP_PAPER_V2_OPERATIONS)
    invocation = _expected()
    directory = _put_final(api, invocation)
    artifact = (
        directory
        + "\\"
        + resolver.unattended_paper_invocation_artifact_name(
            invocation.invocation.invocation_id
        )
    )
    api.put(artifact, b"malformed")

    with pytest.raises(resolver.PersonalDesktopHistoricalCycleConfigurationError):
        resolver._resolve_personal_desktop_historical_cycle_configurations_for_test(
            SID,
            api=api,
            observer=Observer(),
            first_configuration_loader=lambda: pytest.fail(
                "first configuration is not required"
            ),
        )

    assert {call[0] for call in api.calls} <= {
        "open",
        "close",
        "inspect",
        "names",
        "read",
    }


def test_safe_finalized_invocation_without_receipt_is_not_supplied_or_mutated() -> None:
    api = MemoryReadApi()
    api.trading_runtime = True
    api.put(PERSONAL_DESKTOP_PAPER_V2_OPERATIONS)
    _put_final(api, _expected())

    result = (
        resolver._resolve_personal_desktop_historical_cycle_configurations_for_test(
            SID,
            api=api,
            observer=Observer(),
            first_configuration_loader=lambda: pytest.fail(
                "first configuration is not required"
            ),
        )
    )

    assert result == ()
    assert {call[0] for call in api.calls} <= {
        "open",
        "close",
        "inspect",
        "names",
        "read",
    }


def test_frozen_first_configuration_source_key_and_namespace_are_exact() -> None:
    profile = PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE
    assert resolver._FIRST_KEY == (
        "7f62c90df051f5c4998cc3303b7a97dfb80294dfd743662c2f9930422cb83666",
        6199,
    )
    assert resolver._FIRST_KEY == (profile.plan_sha256, profile.plan_byte_length)
    assert PERSONAL_DESKTOP_PAPER_V2_RUNTIME == r"F:\AITradingBot\Paper-v2\runtime"
    assert PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS.endswith(
        r"\unattended-invocations"
    )
