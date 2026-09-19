"""Exact Win32 token query coverage with no LSA or account API dependency."""

import ctypes
import os
from dataclasses import replace
from types import SimpleNamespace

import pytest

from trading_bot.runtime import personal_desktop_paper_account_token as token
from trading_bot.runtime.windows_authority import AuthorityPrincipalError

SID = "S-1-5-21-1-2-3-1009"


def observation(**changes):
    return replace(token.TradingTokenObservation(SID, 1, False, False, ()), **changes)


@pytest.mark.parametrize("flags", [None, 0, 0x10, 0x14, 0x12])
def test_absent_disabled_and_deny_only_admin_membership_is_not_enabled(flags):
    groups = () if flags is None else ((token.ADMINISTRATORS_SID, flags),)
    token.require_trading_token(SID, observation(groups=groups))


@pytest.mark.parametrize(
    "changes",
    [
        {"user_sid": SID + "0"},
        {"token_type": 2},
        {"token_type": True},
        {"thread_token_present": True},
        {"thread_token_present": 0},
        {"elevated": True},
        {"elevated": 0},
        {"groups": ((token.ADMINISTRATORS_SID, 0x4),)},
        {"groups": ((token.ADMINISTRATORS_SID, 0x7),)},
        {"groups": ((SID, -1),)},
        {"groups": ((SID, 0), (SID, 0))},
        {"groups": ((SID, 0x100000000),)},
        {"groups": ((SID, False),)},
        {"groups": [(SID, 0)]},
    ],
)
def test_runtime_token_gate_fails_closed(changes):
    with pytest.raises(AuthorityPrincipalError):
        token.require_trading_token(SID, observation(**changes))


def sid_bytes(sid):
    parts = [int(part) for part in sid.split("-")[1:]]
    return (
        bytes((parts[0], len(parts) - 2))
        + parts[1].to_bytes(6, "big")
        + b"".join(part.to_bytes(4, "little") for part in parts[2:])
    )


class Function:
    def __init__(self, function):
        self.function = function

    def __call__(self, *args):
        return self.function(*args)


class QueryOnlyLibrary:
    def __init__(self, **functions):
        self.functions = functions
        self.accesses = []

    def __getattr__(self, name):
        self.accesses.append(name)
        assert not name.startswith("Lsa"), "LSA access is expressly forbidden"
        assert name in self.functions, f"unexpected native dependency: {name}"
        return Function(self.functions[name])


def native_case(*, changes=None, thread_error=1008, thread_present=False):
    state = SimpleNamespace(
        error=0, closed=[], kinds=[], changes=changes or {}, allocations=[]
    )

    def close(handle):
        state.closed.append(getattr(handle, "value", handle))
        return 1

    def open_process(_process, access, pointer):
        assert access == 0x8
        ctypes.cast(pointer, ctypes.POINTER(ctypes.c_void_p))[0] = 100
        return 1

    def open_thread(_thread, access, open_as_self, pointer):
        assert access == 0x8 and open_as_self is True
        if thread_present:
            ctypes.cast(pointer, ctypes.POINTER(ctypes.c_void_p))[0] = 101
            return 1
        state.error = thread_error
        return 0

    def information(_handle, kind, buffer, length, returned):
        pointer = ctypes.cast(returned, ctypes.POINTER(ctypes.c_uint32))
        size = 128 if kind in {1, 2} else 4
        if buffer is None:
            state.error = 122
            pointer[0] = state.changes.get("size", size)
            return 0
        state.kinds.append(kind)
        state.allocations.append(ctypes.sizeof(buffer))
        pointer[0] = state.changes.get("used", size)
        if kind == token.TOKEN_USER:
            entry = token._SidAndAttributes.from_buffer(buffer)
            entry.sid = ctypes.addressof(buffer) + state.changes.get("sid_offset", 80)
            ctypes.memmove(
                ctypes.addressof(buffer) + 80, sid_bytes(SID), len(sid_bytes(SID))
            )
        elif kind == token.TOKEN_GROUPS:
            groups = token._TokenGroups.from_buffer(buffer)
            groups.count = state.changes.get("count", 1)
            groups.groups[0].sid = ctypes.addressof(buffer) + 80
            groups.groups[0].attributes = state.changes.get("admin_flags", 0x10)
            raw = sid_bytes(token.ADMINISTRATORS_SID)
            ctypes.memmove(ctypes.addressof(buffer) + 80, raw, len(raw))
        else:
            ctypes.c_uint32.from_buffer(buffer).value = state.changes.get(
                kind, 1 if kind == token.TOKEN_TYPE else 0
            )
        return 1

    kernel = QueryOnlyLibrary(
        GetCurrentProcess=lambda: -1, GetCurrentThread=lambda: -2, CloseHandle=close
    )
    advapi = QueryOnlyLibrary(
        OpenProcessToken=open_process,
        OpenThreadToken=open_thread,
        GetTokenInformation=information,
    )
    return state, kernel, advapi


def test_native_boundary_queries_exact_information_and_never_uses_lsa():
    state, kernel, advapi = native_case()
    observed = token.WindowsTradingTokenObserver()._observe(
        kernel, advapi, lambda: state.error
    )
    token.require_trading_token(SID, observed)
    assert observed.user_sid == SID
    assert observed.groups == ((token.ADMINISTRATORS_SID, 0x10),)
    assert state.kinds == [1, 8, 20, 2]
    assert state.closed == [100]
    assert set(advapi.accesses) == {
        "OpenProcessToken",
        "OpenThreadToken",
        "GetTokenInformation",
    }
    assert set(kernel.accesses) == {
        "GetCurrentProcess",
        "GetCurrentThread",
        "CloseHandle",
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"size": token.MAX_TOKEN_INFORMATION_BYTES + 1},
        {"size": 0},
        {"used": 129},
        {"used": 0},
        {"used": 2},
        {"sid_offset": -1},
        {"sid_offset": 127},
        {"count": token.MAX_TOKEN_GROUPS + 1},
        {"count": 20},
        {token.TOKEN_TYPE: 0},
        {token.TOKEN_ELEVATION: 2},
    ],
)
def test_native_token_information_bounds_and_handle_cleanup(changes):
    state, kernel, advapi = native_case(changes=changes)
    with pytest.raises(AuthorityPrincipalError):
        token.WindowsTradingTokenObserver()._observe(
            kernel, advapi, lambda: state.error
        )
    assert state.closed == [100]
    if changes.get("size") in (0, token.MAX_TOKEN_INFORMATION_BYTES + 1):
        assert state.allocations == []


@pytest.mark.parametrize("error", [5, 0, 6, 122])
def test_no_thread_token_requires_error_no_token_exactly(error):
    state, kernel, advapi = native_case(thread_error=error)
    with pytest.raises(AuthorityPrincipalError, match="absence"):
        token.WindowsTradingTokenObserver()._observe(
            kernel, advapi, lambda: state.error
        )
    assert state.kinds == []


def test_thread_impersonation_handles_are_closed_and_gate_rejects():
    state, kernel, advapi = native_case(thread_present=True)
    observed = token.WindowsTradingTokenObserver()._observe(
        kernel, advapi, lambda: state.error
    )
    assert state.closed == [101, 101, 100]
    with pytest.raises(AuthorityPrincipalError):
        token.require_trading_token(SID, observed)


@pytest.mark.parametrize(
    "raw", [b"\x02\x00" + b"\0" * 6, b"\x01\x10" + b"\0" * 6, b"\x01\x02" + b"\0" * 6]
)
def test_sid_parser_rejects_revision_count_and_truncation(raw):
    buffer = ctypes.create_string_buffer(raw, len(raw))
    with pytest.raises(AuthorityPrincipalError):
        token._bounded_sid(buffer, len(raw), ctypes.addressof(buffer))


@pytest.mark.skipif(os.name != "nt", reason="read-only native Windows token query")
def test_windows_current_token_observation_is_read_only():
    observed = token.WindowsTradingTokenObserver().observe()
    assert observed.user_sid.startswith("S-1-")
    assert observed.token_type == 1
    assert type(observed.elevated) is bool
    assert type(observed.thread_token_present) is bool
