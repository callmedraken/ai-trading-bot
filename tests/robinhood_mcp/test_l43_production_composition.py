from __future__ import annotations

import ast
from pathlib import Path

import pytest

from trading_bot.live_prototype.durable_state import RuntimeIdentity
from trading_bot.live_prototype.l43_pre_effect_observation import (
    L43PreEffectDependencies,
)
from trading_bot.live_prototype.l43_production_owner import (
    L43ProductionOwner,
    Q62JournalOrigin,
)
from trading_bot.robinhood_mcp import l43_production_composition as composition
from trading_bot.robinhood_mcp.current_read_transport import (
    RobinhoodCurrentReadTransport,
)
from trading_bot.robinhood_mcp.l43_read_adapter import (
    RobinhoodL43PreEffectReadAdapter,
)


def _origin() -> Q62JournalOrigin:
    return Q62JournalOrigin(
        runtime_identity=RuntimeIdentity(
            account_fingerprint="a" * 64,
            source_head="1" * 40,
            source_tree="2" * 40,
            config_digest="3" * 64,
            binding_digest="4" * 64,
            lifecycle_id="00000000-0000-0000-0000-000000000147",
        ),
        journal_label="arch147-q62-test-origin",
        journal_sha256="5" * 64,
        initialization_event_sha256="6" * 64,
        consumed_observation_sha256="7" * 64,
    )


class _Authority:
    def verify(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("source authority must remain deferred")


class _Journal:
    def replay(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("journal replay must be supplied by the patched owner")


def test_production_composition_is_inert_and_wires_normalized_read_dependencies(
    monkeypatch: pytest.MonkeyPatch,
):
    origin = _origin()
    owner = L43ProductionOwner(
        authority_verifier=_Authority(), journal_reader=_Journal()
    )
    oauth_calls: list[str] = []
    alpaca_transport_calls: list[str] = []
    alpaca_credential_calls: list[str] = []

    def oauth_factory() -> object:
        oauth_calls.append("oauth")
        return object()

    def alpaca_transport_factory() -> object:
        alpaca_transport_calls.append("transport")
        return object()

    def alpaca_credential_reader() -> object:
        alpaca_credential_calls.append("credentials")
        return object()

    monkeypatch.setattr(composition, "read_canonical_q62_origin", lambda: origin)
    monkeypatch.setattr(
        composition.L43ProductionOwner,
        "for_production",
        classmethod(lambda cls, *, repo_root: owner),
    )

    built = composition.L43ProductionPreEffectComposition.for_production(
        repo_root=Path(r"F:\AI\worktrees\ai-trading-bot-live-prototype-current"),
        oauth_factory=oauth_factory,
        alpaca_transport_factory=alpaca_transport_factory,
        alpaca_credential_reader=alpaca_credential_reader,
    )

    assert built.origin is origin
    assert type(built.dependencies) is L43PreEffectDependencies
    assert built.dependencies.continuity_owner is owner
    assert built.dependencies.origin is origin
    assert built.dependencies.state_snapshot_reader.__name__ == (
        "read_production_l43_state_snapshot"
    )
    assert isinstance(
        built.dependencies.order_scope_verifier,
        composition.RobinhoodL43AccountWideOrderScopeVerifier,
    )
    assert oauth_calls == []
    assert alpaca_transport_calls == []
    assert alpaca_credential_calls == []

    read = built.dependencies.robinhood_builder()
    signal = built.dependencies.signal_provider_builder()
    assert isinstance(read, RobinhoodL43PreEffectReadAdapter)
    assert isinstance(read._read, RobinhoodCurrentReadTransport)
    assert hasattr(signal, "snapshot")
    assert oauth_calls == []
    assert alpaca_transport_calls == []
    assert alpaca_credential_calls == []

    source_values = iter(("8" * 40, "9" * 40))
    monkeypatch.setattr(
        composition,
        "_git_output",
        lambda _root, *_arguments: next(source_values),
    )
    assert built.dependencies.source_reader() == composition.L43SourceIdentity(
        source_head="8" * 40,
        source_tree="9" * 40,
    )


def test_production_scope_verifier_cannot_be_caller_asserted():
    verifier = composition.RobinhoodL43AccountWideOrderScopeVerifier()

    assert (
        verifier.verify_account_wide_spy_orders(
            account_fingerprint="a" * 64,
            query_sha256="b" * 64,
            pages_read=1,
            row_count=0,
            exhausted=True,
        )
        is None
    )
    with pytest.raises(TypeError):
        composition.RobinhoodL43AccountWideOrderScopeVerifier(  # type: ignore[call-arg]
            scope="ACCOUNT_WIDE_ALL_AGENTS"
        )


def test_production_composition_has_no_effect_or_raw_provider_dependency():
    path = Path(composition.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    assert "trading_bot.live_prototype.l43_effect_operator" not in imports
    assert "trading_bot.robinhood_mcp.current_live_transport" not in imports
    assert "trading_bot.robinhood_mcp.models" not in imports
    assert "trading_bot.robinhood_mcp.parsing" not in imports
    assert "FINAL_HOLDOUT" not in path.read_text(encoding="utf-8")
