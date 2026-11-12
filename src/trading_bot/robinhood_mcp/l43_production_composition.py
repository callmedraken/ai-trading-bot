"""Effect-free production composition for the L43 read-only boundary.

This module is the provider-side composition owner.  It may assemble lazy
providers and source-owned callbacks, but construction itself never reads
credentials, opens OAuth/browser state, calls a provider, mutates durable
state, or exposes a mutation/review transport.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from scripts.checkpoint_runner import _git_output

from trading_bot.live_prototype.alpaca_runtime_signal_provider import (
    AlpacaRuntimeSignalProvider,
)
from trading_bot.live_prototype.l43_pre_effect_observation import (
    L43PreEffectDependencies,
)
from trading_bot.live_prototype.l43_production_owner import (
    L43ProductionOwner,
    L43SourceIdentity,
    Q62JournalOrigin,
    read_canonical_q62_origin,
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

DEFAULT_ROBINHOOD_REDIRECT_URI = "http://127.0.0.1:8765/robinhood/callback"


class RobinhoodL43AccountWideOrderScopeVerifier:
    """Fail closed because the accepted current provider schema lacks proof.

    Omitting ``placed_agent`` from an order request is not an account-wide
    all-agent semantic.  The current read transport discovers tool names only;
    it does not authenticate an input-schema or provider contract that proves
    every relevant agent is included.  Consequently this verifier deliberately
    returns no proof, which the inward observer converts to its typed
    ``ORDER_SCOPE_UNPROVEN`` blocker.  A caller cannot assert positive scope by
    constructing or configuring this production verifier.
    """

    __slots__ = ()

    def verify_account_wide_spy_orders(
        self,
        *,
        account_fingerprint: str,
        query_sha256: str,
        pages_read: int,
        row_count: int,
        exhausted: bool,
    ) -> None:
        del account_fingerprint, query_sha256, pages_read, row_count, exhausted
        return None


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
        oauth_factory: Callable[[], object] | None = None,
        alpaca_transport_factory: Callable[[], object] | None = None,
        alpaca_credential_reader: Callable[[], object] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> L43ProductionPreEffectComposition:
        """Assemble lazy read-only dependencies without invoking any boundary."""

        if not isinstance(repo_root, Path):
            raise TypeError("production composition requires a concrete repo Path")
        for callback, label in (
            (oauth_factory, "OAuth factory"),
            (alpaca_transport_factory, "Alpaca transport factory"),
            (alpaca_credential_reader, "Alpaca credential reader"),
            (clock, "clock"),
        ):
            if callback is not None and not callable(callback):
                raise TypeError(f"{label} must be callable")

        origin = read_canonical_q62_origin()
        owner = L43ProductionOwner.for_production(repo_root=repo_root)
        session_authority = NYSEPublishedRegularSessionAuthority()
        scope_verifier = RobinhoodL43AccountWideOrderScopeVerifier()

        def source_reader() -> L43SourceIdentity:
            return L43SourceIdentity(
                source_head=_git_output(repo_root, "rev-parse", "HEAD"),
                source_tree=_git_output(repo_root, "rev-parse", "HEAD^{tree}"),
            )

        def robinhood_builder() -> RobinhoodL43PreEffectReadAdapter:
            factory = oauth_factory
            if factory is None:
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
                transport_factory=alpaca_transport_factory,
                credential_reader=alpaca_credential_reader,
                session_authority=session_authority,
                clock=clock,
            )

        dependencies = L43PreEffectDependencies(
            source_reader=source_reader,
            continuity_owner=owner,
            origin=origin,
            state_snapshot_reader=read_production_l43_state_snapshot,
            robinhood_builder=robinhood_builder,
            signal_provider_builder=signal_provider_builder,
            clock=(clock if clock is not None else lambda: datetime.now(UTC)),
            session_authority=session_authority,
            order_scope_verifier=scope_verifier,
        )
        return cls(dependencies=dependencies, origin=origin)


__all__ = [
    "DEFAULT_ROBINHOOD_REDIRECT_URI",
    "L43ProductionPreEffectComposition",
    "RobinhoodL43AccountWideOrderScopeVerifier",
]
