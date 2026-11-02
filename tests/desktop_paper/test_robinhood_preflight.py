"""All protected collaborators are replaced by synthetic boundaries."""

import ast
import json
from pathlib import Path

import pytest

from trading_bot.desktop_paper import robinhood_preflight as preflight
from trading_bot.robinhood_mcp.current_read_transport import READ_TOOLS

from .test_robinhood_read import ACCOUNT, FakeReads


class FakeTransport(FakeReads):
    @property
    def observed_read_tools(self):
        return READ_TOOLS

    @property
    def call_counts(self):
        return tuple(
            (name, sum(n == name for n, _ in self.calls)) for name in READ_TOOLS
        )


def setup_fake(monkeypatch, tmp_path):
    paths = (tmp_path / "simulated-paper.sqlite", tmp_path / "lifecycle.jsonl")
    paths[0].write_bytes(b"synthetic database bytes")
    paths[1].write_bytes(b"synthetic lifecycle bytes")
    monkeypatch.setattr(preflight, "PRODUCTION_FILES", paths)
    transport = FakeTransport()
    # Relative to the runtime observation clock, keep synthetic history empty.
    transport.orders = []
    monkeypatch.setattr(preflight, "_transport", lambda: transport)
    return paths, transport


def test_preflight_zero_mutations_and_read_only_state_hashes(monkeypatch, tmp_path):
    paths, transport = setup_fake(monkeypatch, tmp_path)
    original = Path.open
    modes = []

    def opened(path, mode="r", *args, **kwargs):
        if path in paths:
            modes.append(mode)
            assert mode == "rb"
        return original(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", opened)
    result = preflight.preflight()
    assert result["status"] == "PASS"
    assert result["production_state_before"] == result["production_state_after"]
    assert modes == ["rb"] * 4
    assert set(result["provider_call_counts"]) == set(READ_TOOLS)
    assert sum(result["provider_call_counts"].values()) == 5
    for key in (
        "mutation_call_count",
        "order_review_count",
        "order_preview_count",
        "order_placement_count",
        "order_cancel_count",
        "p5_financial_state_mutation_count",
        "alpaca_call_count",
        "final_holdout_access_count",
    ):
        assert result[key] == 0
    assert result["credential_values_exposed"] is False
    assert ACCOUNT not in json.dumps(result)
    assert len(transport.calls) == 5


@pytest.mark.parametrize("stage", ["oauth", *READ_TOOLS])
def test_failures_never_leak_account_tokens_payload_or_retry(
    monkeypatch, tmp_path, stage
):
    _, transport = setup_fake(monkeypatch, tmp_path)
    calls = []

    def fail(*args, **kwargs):
        calls.append(1)
        raise RuntimeError(ACCOUNT + " secret-token unnecessary provider payload")

    if stage == "oauth":
        monkeypatch.setattr(preflight, "_transport", fail)
    else:
        monkeypatch.setattr(transport, stage, fail)
    result = preflight.preflight()
    assert result["status"] == "BLOCKED"
    assert result["reconciliation_status"] == "RECONCILIATION_FAILED"
    serialized = json.dumps(result)
    assert ACCOUNT not in serialized and "secret-token" not in serialized
    assert "unnecessary provider payload" not in serialized
    assert len(calls) == 1
    assert result["mutation_call_count"] == 0
    assert result["production_state_unchanged"]


def test_before_identity_failure_prevents_oauth(monkeypatch):
    def fail():
        raise RuntimeError("private state path")

    def forbidden():
        pytest.fail("OAuth attempted")

    monkeypatch.setattr(preflight, "_production_identities", fail)
    monkeypatch.setattr(preflight, "_transport", forbidden)
    assert preflight.preflight()["status"] == "BLOCKED"


def test_changed_production_state_fails_closed(monkeypatch, tmp_path):
    paths, transport = setup_fake(monkeypatch, tmp_path)
    original = transport.get_accounts

    def externally_changed():
        paths[1].write_bytes(b"external synthetic modification")
        return original()

    monkeypatch.setattr(transport, "get_accounts", externally_changed)
    result = preflight.preflight()
    assert result["status"] == "BLOCKED"
    assert result["production_state_unchanged"] is False


def test_no_paper_write_or_holdout_alpaca_effect_imports():
    root = Path(preflight.__file__).parent
    for name in (
        "robinhood_read.py",
        "robinhood_reconciliation.py",
        "robinhood_preflight.py",
    ):
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not any(
                    word in (node.module or "").lower()
                    for word in (
                        "alpaca",
                        "final_holdout",
                        "sqlite",
                        "desktop_paper.store",
                        "desktop_paper.engine",
                        "desktop_paper.worker",
                    )
                )
            if isinstance(node, ast.Attribute):
                assert node.attr not in {
                    "review_equity_order",
                    "place_equity_order",
                    "cancel_equity_order",
                    "connect",
                    "execute",
                    "advance_cursor",
                }
