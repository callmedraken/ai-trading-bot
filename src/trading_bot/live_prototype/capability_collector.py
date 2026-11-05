"""Effect-disabled L41 collection from the two permitted Robinhood reads."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from trading_bot.desktop_paper.robinhood_read import data, resolve_account
from trading_bot.live_prototype.capability_observer import (
    CapabilityEvidence,
    CapabilityReport,
    OverallStatus,
    classify_capabilities,
)

_SYMBOL = "SPY"
_ACCOUNT_TYPE = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_REASON = re.compile(r"L41_[A-Z0-9_]{1,64}\Z")


class ReadOnlyCapabilityBoundary(Protocol):
    """Only these account and SPY tradability reads are exposed to collection."""

    def get_accounts(self) -> Mapping[str, object]: ...

    def get_equity_tradability(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]: ...


@dataclass(frozen=True, slots=True)
class CapabilityCallCounts:
    """Attempts made directly through this collector's read-only boundary."""

    get_accounts: int
    get_equity_tradability: int
    other_tool_calls: int = field(default=0, init=False)
    review_equity_order: int = field(default=0, init=False)
    place_equity_order: int = field(default=0, init=False)
    cancel_equity_order: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if any(
            type(count) is not int or count < 0
            for count in (self.get_accounts, self.get_equity_tradability)
        ):
            raise ValueError("L41_CALL_COUNTS_INVALID")
        if self.get_accounts > 1 or self.get_equity_tradability > 1:
            raise ValueError("L41_CALL_LIMIT_EXCEEDED")


@dataclass(frozen=True, slots=True)
class CapabilityCollection:
    """Sanitized collector result with truthful invocation-attempt counts."""

    report: CapabilityReport
    reason: str
    call_counts: CapabilityCallCounts

    def __post_init__(self) -> None:
        if type(self.report) is not CapabilityReport:
            raise TypeError("L41_COLLECTION_REPORT_INVALID")
        if _REASON.fullmatch(self.reason) is None:
            raise ValueError("L41_COLLECTION_REASON_INVALID")
        if type(self.call_counts) is not CapabilityCallCounts:
            raise TypeError("L41_COLLECTION_COUNTS_INVALID")


def collect_capabilities(tools: ReadOnlyCapabilityBoundary) -> CapabilityCollection:
    """Attempt get_accounts once, then one account-bound SPY tradability read.

    The caller owns source admission and any future credential scope. This
    collector only dispatches through the two-method read-only interface and
    never constructs credentials, another provider, a review, or an order.
    """
    if not callable(getattr(tools, "get_accounts", None)) or not callable(
        getattr(tools, "get_equity_tradability", None)
    ):
        return _collection(
            "L41_TOOL_BOUNDARY_INVALID", 0, 0, fingerprint=None, account_type=None
        )

    accounts_calls = 0
    tradability_calls = 0
    try:
        accounts_calls += 1
        accounts_response = tools.get_accounts()
    except Exception:
        return _collection(
            "L41_ACCOUNTS_READ_FAILED",
            accounts_calls,
            tradability_calls,
            fingerprint=None,
            account_type=None,
        )

    try:
        identity = resolve_account(accounts_response)
        accounts = data(accounts_response).get("accounts")
        if not isinstance(accounts, list):
            raise ValueError("L41_ACCOUNT_COLLECTION_INVALID")
        matches = [
            item
            for item in accounts
            if isinstance(item, Mapping)
            and item.get("account_number") == identity.account_number
        ]
        if len(matches) != 1:
            raise ValueError("L41_SELECTED_ACCOUNT_INVALID")
        account = matches[0]
        account_type = account.get("brokerage_account_type")
        if (
            type(account_type) is not str
            or _ACCOUNT_TYPE.fullmatch(account_type) is None
        ):
            raise ValueError("L41_ACCOUNT_TYPE_INVALID")
        account_active = (
            account.get("state") == "active"
            and account.get("deactivated") is False
            and account.get("permanently_deactivated") is False
        )
        account_state = "ACTIVE" if account_active else "INACTIVE"
        fingerprint = identity.fingerprint
    except Exception:
        return _collection(
            "L41_ACCOUNT_RESPONSE_INVALID",
            accounts_calls,
            tradability_calls,
            fingerprint=None,
            account_type=None,
        )

    if not account_active:
        return _collection(
            "L41_ACCOUNT_NOT_ACTIVE",
            accounts_calls,
            tradability_calls,
            fingerprint=fingerprint,
            account_type=account_type,
            agentic_account_count=1,
            account_is_active=account_state,
        )

    try:
        tradability_calls += 1
        tradability_response = tools.get_equity_tradability(
            {"account_number": identity.account_number, "symbols": [_SYMBOL]}
        )
    except Exception:
        return _collection(
            "L41_TRADABILITY_READ_FAILED",
            accounts_calls,
            tradability_calls,
            fingerprint=fingerprint,
            account_type=account_type,
            agentic_account_count=1,
            account_is_active=account_state,
        )

    try:
        tradeability = _parse_tradability(tradability_response, account_type)
    except Exception:
        return _collection(
            "L41_TRADABILITY_RESPONSE_INVALID",
            accounts_calls,
            tradability_calls,
            fingerprint=fingerprint,
            account_type=account_type,
            agentic_account_count=1,
            account_is_active=account_state,
        )

    evidence = _evidence(
        reason="L41_CAPABILITY_FACTS_BLOCKED",
        fingerprint=fingerprint,
        agentic_account_count=1,
        account_is_active=account_state,
        account_type=account_type,
        spy_account_type_tradability=tradeability[0],
        spy_fractional_tradability=tradeability[1],
    )
    report = classify_capabilities(evidence)
    return CapabilityCollection(
        report,
        "L41_CAPABILITY_FACTS_BLOCKED"
        if report.status is not OverallStatus.READY_FOR_L42
        else "L41_CAPABILITY_FACTS_READY",
        CapabilityCallCounts(accounts_calls, tradability_calls),
    )


def _parse_tradability(payload: object, account_type: str) -> tuple[str, str]:
    if not isinstance(payload, Mapping):
        raise ValueError("L41_TRADABILITY_RESPONSE_INVALID")
    body = data(payload)
    rows = body.get("results")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], Mapping):
        raise ValueError("L41_TRADABILITY_ROWS_INVALID")
    row = rows[0]
    if row.get("symbol") != _SYMBOL:
        raise ValueError("L41_TRADABILITY_SYMBOL_INVALID")
    tradeable = row.get("tradeable")
    state = row.get("state")
    if type(tradeable) is not bool or type(state) is not str:
        raise ValueError("L41_TRADABILITY_STATE_INVALID")
    account_entries = row.get("account_type_tradabilities")
    matched: list[Mapping[str, object]] = []
    if isinstance(account_entries, list):
        matched = [
            item
            for item in account_entries
            if isinstance(item, Mapping) and item.get("account_type") == account_type
        ]
    if len(matched) > 1:
        raise ValueError("L41_ACCOUNT_TYPE_TRADABILITY_DUPLICATE")
    account_status = matched[0].get("account_type_tradability") if matched else None
    account_statuses = {"tradable", "untradable", "position_closing_only"}
    if account_status not in account_statuses:
        account_tradability = "UNKNOWN"
        account_is_eligible = False
    elif tradeable is False or state != "active":
        account_tradability = "UNTRADABLE"
        account_is_eligible = False
    else:
        account_tradability = account_status.upper()
        account_is_eligible = account_status == "tradable"

    fractional_status = row.get("fractional_tradability")
    if fractional_status == "tradable" and account_is_eligible:
        fractional_tradability = "TRADABLE"
    elif fractional_status == "untradable":
        fractional_tradability = "UNTRADABLE"
    else:
        fractional_tradability = "UNKNOWN"
    return account_tradability, fractional_tradability


def _collection(
    reason: str,
    accounts_calls: int,
    tradability_calls: int,
    *,
    fingerprint: str | None,
    account_type: str | None,
    agentic_account_count: int | None = None,
    account_is_active: str | None = None,
    spy_account_type_tradability: str | None = None,
    spy_fractional_tradability: str | None = None,
) -> CapabilityCollection:
    evidence = _evidence(
        reason=reason,
        fingerprint=fingerprint,
        agentic_account_count=agentic_account_count,
        account_is_active=account_is_active,
        account_type=account_type,
        spy_account_type_tradability=spy_account_type_tradability,
        spy_fractional_tradability=spy_fractional_tradability,
    )
    return CapabilityCollection(
        classify_capabilities(evidence),
        reason,
        CapabilityCallCounts(accounts_calls, tradability_calls),
    )


def _evidence(
    *,
    reason: str,
    fingerprint: str | None,
    agentic_account_count: int | None,
    account_is_active: str | None,
    account_type: str | None,
    spy_account_type_tradability: str | None,
    spy_fractional_tradability: str | None,
) -> CapabilityEvidence:
    projection = {
        "schema": "arch147-l41-sanitized-observation-projection/v1",
        "reason": reason,
        "account_fingerprint": fingerprint,
        "agentic_account_count": agentic_account_count,
        "account_is_active": account_is_active,
        "account_type": account_type,
        "spy_account_type_tradability": spy_account_type_tradability,
        "spy_fractional_tradability": spy_fractional_tradability,
    }
    digest = hashlib.sha256(
        json.dumps(
            projection,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("ascii")
    ).hexdigest()
    return CapabilityEvidence(
        observation_sha256=digest,
        account_fingerprint=fingerprint,
        agentic_account_count=agentic_account_count,
        account_is_active=account_is_active,
        account_type=account_type,
        spy_account_type_tradability=spy_account_type_tradability,
        spy_fractional_tradability=spy_fractional_tradability,
        interface=None,
        official_rule_claims=(),
    )
