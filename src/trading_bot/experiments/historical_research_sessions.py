"""Immutable Architecture-146 published authority; no global calendar revision."""

from __future__ import annotations

from datetime import date, datetime, time
from hashlib import sha256
from importlib.resources import files
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from trading_bot.experiments.historical_research_custody import (
        HistoricalSessionAuthority,
    )
from zoneinfo import ZoneInfo

AUTHORITY_IDENTITY = "nyse-published-regular-sessions-2016-2026-v1"
AUTHORITY_DIGEST = "7129170764896ad87c8110ec83523c234149393ae53739fed3764ed371ade6e1"
SOURCE_BUNDLE_SHA256 = (
    "6db5b3c039dc98e6a21d5dc8e917de60305c919ea6fdf4cc8b8141185b774607"
)
SOURCE_MANIFEST_SHA256 = (
    "e1f9f6f0048114f2307255a7fa1b40c3661c115c1e8cc22c992246207e084735"
)
MODELED_EXCEPTION_GAP = (date(2018, 12, 5), date(2025, 1, 9))


def published_historical_session_authority() -> HistoricalSessionAuthority:
    """Load only the packaged resource and prove its exact canonical commitment."""
    from trading_bot.experiments.historical_research_custody import (
        HistoricalResearchCustodyError,
        HistoricalSessionAuthority,
        canonical_json_bytes,
        parse_custody_json,
    )

    raw = (
        files("trading_bot.experiments")
        .joinpath("resources", AUTHORITY_IDENTITY + ".json")
        .read_bytes()
    )
    if sha256(raw).hexdigest() != AUTHORITY_DIGEST:
        raise HistoricalResearchCustodyError("published authority resource drift")
    material = parse_custody_json(raw)
    if canonical_json_bytes(material) != raw:
        raise HistoricalResearchCustodyError("noncanonical published authority")
    authority = HistoricalSessionAuthority(
        material["identity"],
        tuple(date.fromisoformat(item) for item in material["sessions"]),
        material["source_sha256"],
    )
    if (
        authority.identity != AUTHORITY_IDENTITY
        or authority.source_sha256 != SOURCE_BUNDLE_SHA256
        or authority.digest != AUTHORITY_DIGEST
        or len(authority.sessions) != 2718
    ):
        raise HistoricalResearchCustodyError("published authority commitment drift")
    return authority


def reconcile_historical_session_model(authority: HistoricalSessionAuthority) -> str:
    """Only the frozen modeled exception gap is accepted; all other deltas STOP."""
    from trading_bot.experiments.historical_research_custody import (
        HistoricalResearchCustodyError,
        require_accepted_historical_session_authority,
    )
    from trading_bot.market_calendar.nyse import NYSEMarketCalendar

    require_accepted_historical_session_authority(authority)
    zone = ZoneInfo("America/New_York")
    modeled = tuple(
        item.session_date
        for item in NYSEMarketCalendar()
        .sessions_between(
            datetime.combine(date(2016, 1, 1), time.min, zone),
            datetime.combine(date(2026, 10, 24), time.min, zone),
        )
        .sessions
    )
    published = set(authority.sessions)
    if tuple(
        item for item in modeled if item not in published
    ) != MODELED_EXCEPTION_GAP or set(authority.sessions) - set(modeled):
        raise HistoricalResearchCustodyError(
            "unexpected model/published authority delta"
        )
    return "REPOSITORY_MODELED_CALENDAR_EXCEPTION_GAP"
