"""Focused fake-only tests for the L41 two-read collector."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping

import pytest

from trading_bot.live_prototype.capability_collector import (
    CapabilityCallCounts,
    CapabilityCollection,
    ReadOnlyCapabilityBoundary,
    collect_capabilities,
)
from trading_bot.live_prototype.capability_observer import (
    Classification,
    FactId,
    OverallStatus,
)

_ACCOUNT = "SECRET_ACCOUNT_NUMBER_4831"
_OTHER_ACCOUNT = "OTHER_ACCOUNT_NUMBER_1059"


def _account(
    account_number: str,
    *,
    agentic_allowed: bool,
    state: str = "active",
    deactivated: bool = False,
    permanently_deactivated: bool = False,
) -> dict[str, object]:
    return {
        "account_number": account_number,
        "agentic_allowed": agentic_allowed,
        "brokerage_account_type": "individual",
        "state": state,
        "deactivated": deactivated,
        "permanently_deactivated": permanently_deactivated,
    }


def _accounts_response(
    accounts: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "data": {
            "accounts": accounts
            if accounts is not None
            else [
                _account(_OTHER_ACCOUNT, agentic_allowed=False),
                _account(_ACCOUNT, agentic_allowed=True),
            ]
        }
    }


def _tradability_response(
    *,
    symbol: str = "SPY",
    tradeable: object = True,
    state: object = "active",
    fractional: object = "tradable",
    account_type: str = "individual",
    account_status: object = "tradable",
) -> dict[str, object]:
    return {
        "data": {
            "results": [
                {
                    "symbol": symbol,
                    "tradeable": tradeable,
                    "state": state,
                    "fractional_tradability": fractional,
                    "account_type_tradabilities": [
                        {
                            "account_type": account_type,
                            "account_type_tradability": account_status,
                        }
                    ],
                }
            ]
        }
    }


class _FakeReadBoundary:
    def __init__(
        self,
        *,
        accounts: object | Exception | None = None,
        tradability: object | Exception | None = None,
    ) -> None:
        self._accounts = _accounts_response() if accounts is None else accounts
        self._tradability = (
            _tradability_response() if tradability is None else tradability
        )
        self.calls: list[tuple[str, object | None]] = []

    def get_accounts(self) -> Mapping[str, object]:
        self.calls.append(("get_accounts", None))
        if isinstance(self._accounts, Exception):
            raise self._accounts
        assert isinstance(self._accounts, Mapping)
        return self._accounts

    def get_equity_tradability(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        self.calls.append(("get_equity_tradability", dict(arguments)))
        if isinstance(self._tradability, Exception):
            raise self._tradability
        assert isinstance(self._tradability, Mapping)
        return self._tradability

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"unexpected tool access: {name}")


def _facts(result: CapabilityCollection) -> dict[FactId, object]:
    return {fact.fact_id: fact for fact in result.report.facts}


def test_collector_uses_exactly_the_two_allowed_reads_and_sanitizes_account() -> None:
    boundary = _FakeReadBoundary()

    result = collect_capabilities(boundary)

    assert boundary.calls == [
        ("get_accounts", None),
        (
            "get_equity_tradability",
            {"account_number": _ACCOUNT, "symbols": ["SPY"]},
        ),
    ]
    assert type(result.call_counts) is CapabilityCallCounts
    assert result.call_counts.get_accounts == 1
    assert result.call_counts.get_equity_tradability == 1
    assert result.call_counts.other_tool_calls == 0
    assert result.call_counts.review_equity_order == 0
    assert result.call_counts.place_equity_order == 0
    assert result.call_counts.cancel_equity_order == 0
    assert (
        result.report.account_fingerprint
        == hashlib.sha256(_ACCOUNT.encode("utf-8")).hexdigest()
    )
    assert result.report.account_type == "individual"
    assert result.report.status is OverallStatus.BLOCKED
    assert _facts(result)[FactId.INTENDED_AGENTIC_ACCOUNT].classification is (
        Classification.PROVEN
    )
    assert _facts(result)[FactId.SPY_TRADABILITY].classification is (
        Classification.PROVEN
    )
    assert _facts(result)[FactId.FRACTIONAL_ELIGIBILITY].classification is (
        Classification.PROVEN
    )
    for fact_id in (
        FactId.SELL_QUANTITY_FIELD,
        FactId.DECIMAL_INTERFACE_PRECISION,
        FactId.QUANTITY_INCREMENT,
        FactId.MINIMUM_QUANTITY,
        FactId.MAXIMUM_QUANTITY_OR_ABSENCE,
        FactId.MINIMUM_SELL_NOTIONAL_OR_ABSENCE,
        FactId.BELOW_MINIMUM_FULL_CLOSE,
        FactId.RESIDUAL_FULL_OWNED_CLOSE,
        FactId.REVIEW_PREVIEW_ONLY,
    ):
        assert _facts(result)[fact_id].classification is Classification.BLOCKING_L42
    assert _facts(result)[FactId.INSTANCE_REVIEW_REQUIRES_POSITION].classification is (
        Classification.DEFER_TO_FIRST_OWNED_POSITION
    )
    assert _ACCOUNT not in repr(result)
    assert _OTHER_ACCOUNT not in repr(result)


@pytest.mark.parametrize(
    "accounts, reason",
    [
        (
            [
                _account(_ACCOUNT, agentic_allowed=True),
                _account(_OTHER_ACCOUNT, agentic_allowed=True),
            ],
            "L41_ACCOUNT_RESPONSE_INVALID",
        ),
        (
            [_account(_ACCOUNT, agentic_allowed=False)],
            "L41_ACCOUNT_RESPONSE_INVALID",
        ),
        (
            [_account(_ACCOUNT, agentic_allowed=True, state="restricted")],
            "L41_ACCOUNT_NOT_ACTIVE",
        ),
        (
            [_account(_ACCOUNT, agentic_allowed=True, deactivated=True)],
            "L41_ACCOUNT_NOT_ACTIVE",
        ),
        (
            [
                _account(
                    _ACCOUNT,
                    agentic_allowed=True,
                    permanently_deactivated=True,
                )
            ],
            "L41_ACCOUNT_NOT_ACTIVE",
        ),
    ],
)
def test_invalid_or_inactive_account_blocks_before_tradability(
    accounts: list[dict[str, object]], reason: str
) -> None:
    boundary = _FakeReadBoundary(accounts=_accounts_response(accounts))

    result = collect_capabilities(boundary)

    assert result.reason == reason
    assert boundary.calls == [("get_accounts", None)]
    assert result.call_counts.get_accounts == 1
    assert result.call_counts.get_equity_tradability == 0
    assert result.report.status is OverallStatus.BLOCKED
    assert _ACCOUNT not in repr(result)
    assert _OTHER_ACCOUNT not in repr(result)


def test_account_read_failure_is_sanitized_and_never_retried() -> None:
    boundary = _FakeReadBoundary(
        accounts=RuntimeError(f"SECRET_PROVIDER_TEXT {_ACCOUNT}")
    )

    result = collect_capabilities(boundary)

    assert result.reason == "L41_ACCOUNTS_READ_FAILED"
    assert boundary.calls == [("get_accounts", None)]
    assert result.call_counts.get_accounts == 1
    assert result.call_counts.get_equity_tradability == 0
    assert "SECRET_PROVIDER_TEXT" not in repr(result)
    assert _ACCOUNT not in repr(result)


def test_tradability_read_failure_is_sanitized_and_never_retried() -> None:
    boundary = _FakeReadBoundary(
        tradability=RuntimeError(f"SECRET_PROVIDER_TEXT {_ACCOUNT}")
    )

    result = collect_capabilities(boundary)

    assert result.reason == "L41_TRADABILITY_READ_FAILED"
    assert [name for name, _ in boundary.calls] == [
        "get_accounts",
        "get_equity_tradability",
    ]
    assert result.call_counts.get_accounts == 1
    assert result.call_counts.get_equity_tradability == 1
    assert "SECRET_PROVIDER_TEXT" not in repr(result)
    assert _ACCOUNT not in repr(result)


@pytest.mark.parametrize(
    "changes, expected_spy, expected_fractional",
    [
        (
            {"tradeable": False},
            Classification.BLOCKING_L42,
            Classification.BLOCKING_L42,
        ),
        (
            {"state": "inactive"},
            Classification.BLOCKING_L42,
            Classification.BLOCKING_L42,
        ),
        (
            {"account_status": "position_closing_only"},
            Classification.BLOCKING_L42,
            Classification.BLOCKING_L42,
        ),
        (
            {"account_type": "ira_roth"},
            Classification.BLOCKING_L42,
            Classification.BLOCKING_L42,
        ),
        ({"fractional": None}, Classification.PROVEN, Classification.BLOCKING_L42),
        ({"fractional": "unknown"}, Classification.PROVEN, Classification.BLOCKING_L42),
    ],
)
def test_positive_spy_facts_require_active_matching_account_type_and_fractional(
    changes: dict[str, object],
    expected_spy: Classification,
    expected_fractional: Classification,
) -> None:
    boundary = _FakeReadBoundary(tradability=_tradability_response(**changes))

    result = collect_capabilities(boundary)

    facts = _facts(result)
    assert facts[FactId.SPY_TRADABILITY].classification is expected_spy
    assert facts[FactId.FRACTIONAL_ELIGIBILITY].classification is expected_fractional
    assert result.report.status is OverallStatus.BLOCKED


def test_malformed_spy_response_returns_fixed_reason_without_provider_text() -> None:
    boundary = _FakeReadBoundary(
        tradability=_tradability_response(symbol="SECRET_PROVIDER_TEXT")
    )

    result = collect_capabilities(boundary)

    assert result.reason == "L41_TRADABILITY_RESPONSE_INVALID"
    assert result.call_counts.get_accounts == 1
    assert result.call_counts.get_equity_tradability == 1
    assert "SECRET_PROVIDER_TEXT" not in repr(result)


def test_read_boundary_exposes_only_the_two_allowed_methods() -> None:
    public_members = {
        name for name in vars(ReadOnlyCapabilityBoundary) if not name.startswith("_")
    }

    assert public_members == {"get_accounts", "get_equity_tradability"}
