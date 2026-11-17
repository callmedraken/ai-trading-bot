"""Effect-free production composition for the L43 read-only boundary.

This module is the provider-side composition owner.  It may assemble lazy
providers and source-owned callbacks, but construction itself never reads
credentials, opens OAuth/browser state, calls a provider, mutates durable
state, or exposes a mutation/review transport.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from scripts.checkpoint_runner import _git_output

from trading_bot.live_prototype.alpaca_runtime_signal_provider import (
    AlpacaRuntimeSignalProvider,
)
from trading_bot.live_prototype.l43_pre_effect_observation import (
    _MAX_ORDER_PAGES,
    _MAX_ORDERS,
    L43OrderScope,
    L43OrderScopeProof,
    L43PreEffectDependencies,
    _account_wide_spy_order_query_digest,
)
from trading_bot.live_prototype.l43_production_owner import (
    L43ProductionOwner,
    L43SourceIdentity,
    Q62JournalOrigin,
    read_canonical_q62_origin,
)
from trading_bot.live_prototype.l43_provider_contracts import (
    L43AccountIdentity,
    L43PreEffectReadBoundary,
)
from trading_bot.live_prototype.l43_state import read_production_l43_state_snapshot
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.robinhood_mcp.current_read_transport import (
    RobinhoodCurrentReadTransport,
)
from trading_bot.robinhood_mcp.l43_read_adapter import (
    RobinhoodL43PreEffectReadAdapter,
)
from trading_bot.robinhood_mcp.order_scope_evidence_admission import (
    OrderScopeEvidenceAuthority,
    load_order_scope_evidence_authority,
)

DEFAULT_ROBINHOOD_REDIRECT_URI = "http://127.0.0.1:8765/robinhood/callback"
_PRODUCTION_VERIFIER_SEAL = object()


class RobinhoodL43AccountWideOrderScopeVerifier:
    """Admit the fixed A2/RHC2 chain for the exact Q62-bound L43 SPY read."""

    __slots__ = ("_origin",)

    def __init__(
        self,
        *,
        origin: Q62JournalOrigin,
        _source_seal: object,
    ) -> None:
        if (
            type(origin) is not Q62JournalOrigin
            or _source_seal is not _PRODUCTION_VERIFIER_SEAL
        ):
            raise TypeError("order-scope verifier requires the canonical Q62 origin")
        self._origin = origin

    def verify_account_wide_spy_orders(
        self,
        *,
        account_fingerprint: str,
        query_sha256: str,
        order_arguments: Mapping[str, object],
        pages_read: int,
        row_count: int,
        exhausted: bool,
    ) -> L43OrderScopeProof | None:
        try:
            origin_fingerprint = self._origin.runtime_identity.account_fingerprint
            if (
                type(account_fingerprint) is not str
                or account_fingerprint != origin_fingerprint
                or type(order_arguments) is not dict
                or set(order_arguments) != {"account_number", "symbol"}
                or type(order_arguments["account_number"]) is not str
                or type(order_arguments["symbol"]) is not str
                or order_arguments["symbol"] != "SPY"
                or type(query_sha256) is not str
                or len(query_sha256) != 64
                or any(char not in "0123456789abcdef" for char in query_sha256)
                or type(pages_read) is not int
                or not 1 <= pages_read <= _MAX_ORDER_PAGES
                or type(row_count) is not int
                or not 0 <= row_count <= _MAX_ORDERS
                or exhausted is not True
            ):
                return None
            account_number = order_arguments["account_number"]
            current_account = L43AccountIdentity(
                account_number=account_number,
                account_fingerprint=account_fingerprint,
            )
            if (
                hashlib.sha256(
                    current_account.account_number.encode("utf-8")
                ).hexdigest()
                != current_account.fingerprint
            ):
                return None
            expected_query_sha256 = _account_wide_spy_order_query_digest(
                origin_fingerprint, order_arguments
            )
            if query_sha256 != expected_query_sha256:
                return None

            authority = load_order_scope_evidence_authority(self._origin)
            if (
                type(authority) is not OrderScopeEvidenceAuthority
                or authority.account_fingerprint != origin_fingerprint
            ):
                return None
            evidence_sha256 = _rhc3_evidence_digest(
                authority.a2_evidence_sha256,
                authority.rhc2_report_sha256,
                authority.rhc2_observer_evidence_sha256,
                authority.inner_b2_evidence_sha256,
                origin_fingerprint,
                query_sha256,
                pages_read,
                row_count,
                exhausted,
            )
            return L43OrderScopeProof(
                scope=L43OrderScope.ACCOUNT_WIDE_ALL_AGENTS,
                query_sha256=query_sha256,
                pages_read=pages_read,
                row_count=row_count,
                exhausted=True,
                evidence_sha256=evidence_sha256,
            )
        except (OSError, TypeError, ValueError, KeyError, AttributeError):
            return None


def _rhc3_evidence_digest(
    a2_sha256: str,
    rhc2_report_sha256: str,
    rhc2_observer_sha256: str,
    inner_b2_sha256: str,
    account_fingerprint: str,
    query_sha256: str,
    pages_read: int,
    row_count: int,
    exhausted: bool,
) -> str:
    material = (
        "ARCH147_RHC3_PRODUCTION_ORDER_SCOPE_EVIDENCE_V1",
        a2_sha256,
        rhc2_report_sha256,
        rhc2_observer_sha256,
        inner_b2_sha256,
        account_fingerprint,
        query_sha256,
        pages_read,
        row_count,
        exhausted,
    )
    payload = json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


class L43ProductionPreEffectComposition:
    """One narrow provider-side constructor for normalized L43 read inputs."""

    __slots__ = ("dependencies", "origin")

    def __init__(
        self,
        *,
        dependencies: L43PreEffectDependencies,
        origin: Q62JournalOrigin,
    ) -> None:
        if type(dependencies) is not L43PreEffectDependencies:
            raise TypeError("production composition requires normalized dependencies")
        if type(origin) is not Q62JournalOrigin:
            raise TypeError("production composition requires the accepted Q62 origin")
        self.dependencies = dependencies
        self.origin = origin

    @classmethod
    def for_production(
        cls,
        *,
        repo_root: Path,
    ) -> L43ProductionPreEffectComposition:
        """Assemble lazy read-only dependencies without invoking any boundary."""

        if not isinstance(repo_root, Path):
            raise TypeError("production composition requires a concrete repo Path")

        origin = read_canonical_q62_origin()
        owner = L43ProductionOwner.for_production(repo_root=repo_root)
        session_authority = NYSEPublishedRegularSessionAuthority()
        scope_verifier = RobinhoodL43AccountWideOrderScopeVerifier(
            origin=origin,
            _source_seal=_PRODUCTION_VERIFIER_SEAL,
        )

        def source_reader() -> L43SourceIdentity:
            return L43SourceIdentity(
                source_head=_git_output(repo_root, "rev-parse", "HEAD"),
                source_tree=_git_output(repo_root, "rev-parse", "HEAD^{tree}"),
            )

        def robinhood_builder() -> RobinhoodL43PreEffectReadAdapter:
            from trading_bot.robinhood_mcp.windows_oauth import (
                create_windows_robinhood_oauth_factory,
            )

            factory = create_windows_robinhood_oauth_factory(
                redirect_uri=DEFAULT_ROBINHOOD_REDIRECT_URI
            )
            return RobinhoodL43PreEffectReadAdapter(
                RobinhoodCurrentReadTransport(factory)
            )

        def signal_provider_builder() -> AlpacaRuntimeSignalProvider:
            return AlpacaRuntimeSignalProvider(
                session_authority=session_authority,
            )

        dependencies = L43PreEffectDependencies(
            source_reader=source_reader,
            continuity_owner=owner,
            origin=origin,
            state_snapshot_reader=read_production_l43_state_snapshot,
            robinhood_builder=robinhood_builder,
            signal_provider_builder=signal_provider_builder,
            clock=lambda: datetime.now(UTC),
            session_authority=session_authority,
            order_scope_verifier=scope_verifier,
            read_operation_scope_factory=_read_operation_scope,
        )
        return cls(dependencies=dependencies, origin=origin)


def _read_operation_scope(
    boundary: L43PreEffectReadBoundary,
) -> AbstractContextManager[object]:
    """Select the explicit scope for the exact production read adapter."""

    if type(boundary) is not RobinhoodL43PreEffectReadAdapter:
        raise TypeError("production scope requires the normalized L43 read adapter")
    adapter = cast(RobinhoodL43PreEffectReadAdapter, boundary)
    return adapter._operation_scope()


__all__ = [
    "DEFAULT_ROBINHOOD_REDIRECT_URI",
    "L43ProductionPreEffectComposition",
    "RobinhoodL43AccountWideOrderScopeVerifier",
]
