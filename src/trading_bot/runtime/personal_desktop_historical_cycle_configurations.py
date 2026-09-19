"""Read-only source authority for installed Paper-v2 configuration dependencies."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import XNYS_CALENDAR_DESCRIPTOR, BoundMarketCalendar
from trading_bot.runtime.paper_operation import parse_paper_operation_receipt
from trading_bot.runtime.personal_desktop_first_paper_configuration import (
    read_personal_desktop_first_paper_cycle_configuration,
)
from trading_bot.runtime.personal_desktop_first_paper_operation import (
    PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE,
)
from trading_bot.runtime.personal_desktop_paper_account_security import (
    PERSONAL_DESKTOP_PAPER_V2_OPERATIONS,
    PERSONAL_DESKTOP_PAPER_V2_RUNTIME,
    PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS,
    PaperReadNativeApi,
    PinnedTradingPaperReadSession,
    WindowsPaperReadNativeApi,
)
from trading_bot.runtime.personal_desktop_paper_account_token import (
    TradingTokenObserver,
    WindowsTradingTokenObserver,
    require_trading_token,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation import (
    verify_personal_desktop_unattended_paper_invocation,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation_storage import (
    unattended_paper_invocation_artifact_name,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    require_validated_production_authority,
)

_UUID_TEXT = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_RECEIPT_DIRECTORY = re.compile(rf"paper-operation-({_UUID_TEXT})")
_INVOCATION_DIRECTORY = re.compile(rf"unattended-paper-invocation-({_UUID_TEXT})")
_FIRST_KEY = (
    PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.plan_sha256,
    PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.plan_byte_length,
)


class PersonalDesktopHistoricalCycleConfigurationError(ValueError):
    """Installed receipt dependencies cannot be resolved exactly and uniquely."""


@dataclass(frozen=True, slots=True)
class _ConfigurationSource:
    key: tuple[str, int]
    payload: bytes


def resolve_personal_desktop_historical_cycle_configurations(
    authority: ValidatedProductionAuthority,
) -> tuple[bytes, ...]:
    """Return exactly the canonical configuration bytes used by installed receipts."""

    c1 = require_validated_production_authority(authority)
    observer = WindowsTradingTokenObserver()
    result = _read_and_resolve(
        c1.approved_account_sid,
        api=WindowsPaperReadNativeApi(),
        observer=observer,
        first_configuration_loader=lambda: (
            read_personal_desktop_first_paper_cycle_configuration(c1)
        ),
    )
    require_validated_production_authority(c1)
    return result


def _resolve_personal_desktop_historical_cycle_configurations_for_test(
    trading_sid: str,
    *,
    api: PaperReadNativeApi,
    observer: TradingTokenObserver,
    first_configuration_loader: Callable[[], bytes],
) -> tuple[bytes, ...]:
    """Exercise the fixed read-only resolver with explicit disposable seams."""

    return _read_and_resolve(
        trading_sid,
        api=api,
        observer=observer,
        first_configuration_loader=first_configuration_loader,
    )


def _read_and_resolve(
    trading_sid: str,
    *,
    api: PaperReadNativeApi,
    observer: TradingTokenObserver,
    first_configuration_loader: Callable[[], bytes],
) -> tuple[bytes, ...]:
    initial_token = observer.observe()
    require_trading_token(trading_sid, initial_token)
    try:
        required = _read_receipt_dependency_keys(api, trading_sid)
        invocation_sources = _read_invocation_configuration_sources(api, trading_sid)
        sources = list(invocation_sources)
        if _FIRST_KEY in required:
            payload = first_configuration_loader()
            sources.append(_ConfigurationSource(_FIRST_KEY, payload))
        return _resolve_required_configuration_payloads(required, tuple(sources))
    except PersonalDesktopHistoricalCycleConfigurationError:
        raise
    except Exception as error:
        raise PersonalDesktopHistoricalCycleConfigurationError(
            "historical configuration source inspection failed closed"
        ) from error
    finally:
        final_token = observer.observe()
        require_trading_token(trading_sid, final_token)
        if final_token != initial_token:
            raise PersonalDesktopHistoricalCycleConfigurationError(
                "Trading token changed during historical configuration resolution"
            )


def _read_receipt_dependency_keys(
    api: PaperReadNativeApi,
    trading_sid: str,
) -> tuple[tuple[str, int], ...]:
    dependencies: list[tuple[str, int]] = []
    with PinnedTradingPaperReadSession(api, trading_sid) as session:
        names = sorted(session.names(PERSONAL_DESKTOP_PAPER_V2_OPERATIONS))
        for name in names:
            match = _RECEIPT_DIRECTORY.fullmatch(name)
            if match is None:
                raise PersonalDesktopHistoricalCycleConfigurationError(
                    "paper-operation receipt namespace is malformed"
                )
            operation_id = _canonical_uuid(match.group(1), "operation")
            directory = PERSONAL_DESKTOP_PAPER_V2_OPERATIONS + "\\" + name
            artifact_name = f"paper-operation-receipt-{operation_id}.json"
            if session.names(directory) != (artifact_name,):
                raise PersonalDesktopHistoricalCycleConfigurationError(
                    "paper-operation receipt directory contents are invalid"
                )
            receipt = parse_paper_operation_receipt(
                session.read(directory + "\\" + artifact_name)
            )
            if receipt.receipt_id != operation_id:
                raise PersonalDesktopHistoricalCycleConfigurationError(
                    "paper-operation receipt name and identity disagree"
                )
            artifact = receipt.intent.cycle_configuration_artifact
            dependencies.append((artifact.sha256, artifact.byte_length))
    return tuple(dict.fromkeys(dependencies))


def _read_invocation_configuration_sources(
    api: PaperReadNativeApi,
    trading_sid: str,
) -> tuple[_ConfigurationSource, ...]:
    calendar = BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())
    sources: list[_ConfigurationSource] = []
    with PinnedTradingPaperReadSession(api, trading_sid) as session:
        namespace_name = PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS.rsplit(
            "\\", 1
        )[-1]
        if namespace_name not in session.names(PERSONAL_DESKTOP_PAPER_V2_RUNTIME):
            return ()
        names = sorted(session.names(PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS))
        for name in names:
            match = _INVOCATION_DIRECTORY.fullmatch(name)
            if match is None:
                raise PersonalDesktopHistoricalCycleConfigurationError(
                    "unattended invocation namespace is malformed"
                )
            invocation_id = _canonical_uuid(match.group(1), "invocation")
            directory = PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS + "\\" + name
            artifact_name = unattended_paper_invocation_artifact_name(invocation_id)
            if session.names(directory) != (artifact_name,):
                raise PersonalDesktopHistoricalCycleConfigurationError(
                    "finalized unattended invocation contents are invalid"
                )
            binding = verify_personal_desktop_unattended_paper_invocation(
                session.read(directory + "\\" + artifact_name), calendar
            )
            if binding.invocation.invocation_id != invocation_id:
                raise PersonalDesktopHistoricalCycleConfigurationError(
                    "unattended invocation name and identity disagree"
                )
            sources.append(
                _ConfigurationSource(
                    (
                        binding.invocation.plan_sha256,
                        binding.invocation.plan_byte_length,
                    ),
                    binding.invocation.plan_artifact,
                )
            )
    return tuple(sources)


def _resolve_required_configuration_payloads(
    required: tuple[tuple[str, int], ...],
    sources: tuple[_ConfigurationSource, ...],
) -> tuple[bytes, ...]:
    if type(required) is not tuple or type(sources) is not tuple:
        raise PersonalDesktopHistoricalCycleConfigurationError(
            "historical configuration inventory is invalid"
        )
    required_set = set(required)
    if len(required_set) != len(required):
        raise PersonalDesktopHistoricalCycleConfigurationError(
            "receipt configuration dependency inventory is duplicated"
        )
    matches: dict[tuple[str, int], list[bytes]] = {key: [] for key in required}
    for source in sources:
        if type(source) is not _ConfigurationSource:
            raise PersonalDesktopHistoricalCycleConfigurationError(
                "historical configuration source is invalid"
            )
        payload = source.payload
        actual = (
            (
                sha256(payload).hexdigest(),
                len(payload),
            )
            if type(payload) is bytes
            else None
        )
        if actual != source.key:
            raise PersonalDesktopHistoricalCycleConfigurationError(
                "historical configuration source bytes do not match their key"
            )
        if source.key in required_set:
            matches[source.key].append(payload)
    if any(len(matches[key]) != 1 for key in required):
        raise PersonalDesktopHistoricalCycleConfigurationError(
            "each receipt requires exactly one authoritative configuration source"
        )
    return tuple(matches[key][0] for key in required)


def _canonical_uuid(value: str, label: str) -> UUID:
    try:
        result = UUID(value)
    except ValueError:
        raise PersonalDesktopHistoricalCycleConfigurationError(
            f"{label} identity is malformed"
        ) from None
    if str(result) != value:
        raise PersonalDesktopHistoricalCycleConfigurationError(
            f"{label} identity is noncanonical"
        )
    return result
