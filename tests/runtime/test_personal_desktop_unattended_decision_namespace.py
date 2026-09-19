"""Trading namespace qualification with disposable read-only memory objects."""

import ctypes
from dataclasses import replace
from types import SimpleNamespace

import pytest

from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime import personal_desktop_unattended_decision_namespace as ns
from trading_bot.runtime.personal_desktop_paper_account_token import (
    TradingTokenObservation,
)

from . import test_personal_desktop_paper_account_security as memory


@pytest.fixture
def harness(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("namespace qualifier reached native production state")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)
    monkeypatch.setattr(
        memory,
        "SID",
        ns.PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid,
    )
    api = memory.MemoryReadApi()
    api.trading_runtime = True
    api.put(memory.RUNTIME)
    token = TradingTokenObservation(memory.SID, 1, False, False, ())
    observer = SimpleNamespace(observe=lambda: token)
    return api, observer, token


def qualify(api, observer):
    result = ns.qualify_trading_unattended_decision_namespace_for_test(observer, api)
    assert not api.handles
    assert not any(c[0] == "read" for c in api.calls)
    return result


def test_exact_missing(harness):
    api, observer, _ = harness
    assert qualify(api, observer) is ns.TradingDecisionNamespaceClassification.MISSING
    assert not any(c[0] == "open" and c[1] == memory.DECISIONS for c in api.calls)
    assert api.inspections[memory.ROOT] >= 3
    assert api.inspections[memory.RUNTIME] >= 3


def test_exact_valid(harness):
    api, observer, _ = harness
    api.put(memory.DECISIONS)
    assert (
        qualify(api, observer)
        is ns.TradingDecisionNamespaceClassification.PRESENT_VALID
    )
    assert api.inspections[memory.DECISIONS] >= 3


@pytest.mark.parametrize(
    "names",
    [
        ("Unattended-Decisions",),
        ("UNATTENDED-DECISIONS",),
        ("unattended-decisions", "Unattended-Decisions"),
        ("../unsafe",),
        ("unattended-decisions ",),
    ],
)
def test_ambiguous_inventory(harness, names):
    api, observer, _ = harness
    api.overrides[memory.RUNTIME] = names
    # Trailing-space Win32 aliases must also fail closed.
    assert qualify(api, observer) is ns.TradingDecisionNamespaceClassification.BLOCKED


@pytest.mark.parametrize(
    "failure", ["reparse", "security", "identity", "replace", "drift", "inventory"]
)
def test_unsafe_namespace(harness, failure):
    api, observer, _ = harness
    api.put(memory.DECISIONS)
    node = api.nodes[memory.DECISIONS]
    if failure == "reparse":
        node.observation = replace(
            node.observation,
            security=replace(node.observation.security, is_reparse_point=True),
        )
    elif failure == "security":
        node.observation = replace(
            node.observation,
            security=replace(node.observation.security, owner_sid=memory.SID),
        )
    elif failure == "identity":
        node.observation = replace(node.observation, identity=(7, 0))
    else:

        def drift(path, count, pinned):
            if failure == "inventory" and path == memory.RUNTIME and count == 2:
                api.overrides[memory.RUNTIME] = ()
            if path == memory.DECISIONS and count == 2:
                if failure == "replace":
                    api.put(memory.DECISIONS)
                    api.nodes[memory.DECISIONS].observation = replace(
                        node.observation, identity=(7, 999)
                    )
                elif failure == "drift":
                    pinned.observation = replace(pinned.observation, identity=(7, 999))
                else:
                    api.overrides[memory.RUNTIME] = ()

        api.on_inspect = drift
    assert qualify(api, observer) is ns.TradingDecisionNamespaceClassification.BLOCKED


@pytest.mark.parametrize("bad", ["admin", "sid", "thread", "type", "elevated", "drift"])
def test_token_required_and_unchanged(harness, bad):
    api, observer, token = harness
    changes = {
        "admin": {"groups": (("S-1-5-32-544", 4),)},
        "sid": {"user_sid": "S-1-5-21-1-2-3-1009"},
        "thread": {"thread_token_present": True},
        "type": {"token_type": 2},
        "elevated": {"elevated": True},
    }
    if bad == "drift":
        values = iter((token, replace(token, groups=(("S-1-1-0", 4),))))
        observer.observe = lambda: next(values)
    else:
        observer.observe = lambda: replace(token, **changes[bad])
    assert qualify(api, observer) is ns.TradingDecisionNamespaceClassification.BLOCKED


def test_production_validates_token_before_native(monkeypatch):
    bad = TradingTokenObservation("S-1-5-21-1-2-3-1009", 1, False, True, ())
    monkeypatch.setattr(
        ns, "WindowsTradingTokenObserver", lambda: SimpleNamespace(observe=lambda: bad)
    )

    def forbidden():
        pytest.fail("invalid Trading token constructed a filesystem boundary")

    monkeypatch.setattr(security, "WindowsPaperReadNativeApi", forbidden)
    assert (
        ns.qualify_trading_unattended_decision_namespace()
        is ns.TradingDecisionNamespaceClassification.BLOCKED
    )


def test_no_admin_or_mutation_imports():
    import inspect

    source = inspect.getsource(ns)
    assert "personal_desktop_unattended_paper_storage_provisioning" not in source
    for name in (
        "_ProvisioningTarget",
        "_WindowsProvisioningReadNativeApi",
        "require_paper_publication_administrator",
        "create_fixed_child",
    ):
        assert name not in source


def test_production_token_drift_from_initial_observation(harness, monkeypatch):
    api, observer, token = harness
    values = iter((token, replace(token, groups=(("S-1-1-0", 4),))))
    observer.observe = lambda: next(values)
    monkeypatch.setattr(ns, "WindowsTradingTokenObserver", lambda: observer)
    monkeypatch.setattr(security, "WindowsPaperReadNativeApi", lambda: api)
    assert (
        ns.qualify_trading_unattended_decision_namespace()
        is ns.TradingDecisionNamespaceClassification.BLOCKED
    )
    assert not api.handles


@pytest.mark.parametrize("present", [False, True])
@pytest.mark.parametrize("path", [memory.ROOT, memory.RUNTIME])
def test_parent_replace_or_inventory_drift_blocks(harness, present, path):
    api, observer, _ = harness
    if present:
        api.put(memory.DECISIONS)

    def replace_parent(current_path, count, pinned):
        if current_path == path and count == 2:
            api.put(path)
            api.nodes[path].observation = replace(pinned.observation, identity=(7, 999))

    api.on_inspect = replace_parent
    assert qualify(api, observer) is ns.TradingDecisionNamespaceClassification.BLOCKED


def test_verified_missing_becomes_present_blocks(harness):
    api, observer, _ = harness

    def appeared(path, count, pinned):
        if path == memory.RUNTIME and count == 2:
            api.put(memory.DECISIONS)

    api.on_inspect = appeared
    assert qualify(api, observer) is ns.TradingDecisionNamespaceClassification.BLOCKED
