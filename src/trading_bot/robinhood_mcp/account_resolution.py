"""Internal canonical Agentic equities-account resolution for paper cycles."""

from __future__ import annotations

from collections.abc import Callable, Mapping


class RobinhoodAgenticAccountResolutionError(RuntimeError):
    """Account metadata cannot establish one canonical Agentic account."""


class RobinhoodAgenticAccountResolver:
    """Resolve metadata in memory without caching or exposing a raw MCP tool."""

    __slots__ = ("_read_accounts",)

    def __init__(self, read_accounts: Callable[[], Mapping[str, object]]) -> None:
        if not callable(read_accounts):
            raise TypeError("read_accounts must be callable")
        self._read_accounts = read_accounts

    def resolve(self) -> str:
        """Require one eligible account from the equities Trading MCP metadata."""
        try:
            response = self._read_accounts()
        except Exception:
            raise RobinhoodAgenticAccountResolutionError(
                "Agentic account metadata request failed"
            ) from None
        if not isinstance(response, Mapping):
            raise RobinhoodAgenticAccountResolutionError("invalid account response")
        data = response.get("data")
        if not isinstance(data, Mapping):
            raise RobinhoodAgenticAccountResolutionError("invalid account data")
        accounts = data.get("accounts")
        if not isinstance(accounts, list):
            raise RobinhoodAgenticAccountResolutionError("invalid accounts collection")
        eligible: list[str] = []
        for account in accounts:
            if not isinstance(account, Mapping):
                raise RobinhoodAgenticAccountResolutionError("invalid account record")
            allowed = account.get("agentic_allowed")
            if not isinstance(allowed, bool):
                raise RobinhoodAgenticAccountResolutionError(
                    "invalid Agentic eligibility"
                )
            number = account.get("account_number")
            if (
                not isinstance(number, str)
                or not number
                or number != number.strip()
                or len(number) > 128
                or any(
                    char.isspace() or ord(char) < 32 or ord(char) == 127
                    for char in number
                )
            ):
                raise RobinhoodAgenticAccountResolutionError("invalid account number")
            if allowed is True:
                eligible.append(number)
        if len(eligible) != 1:
            raise RobinhoodAgenticAccountResolutionError(
                "expected exactly one eligible Agentic account"
            )
        return eligible[0]
