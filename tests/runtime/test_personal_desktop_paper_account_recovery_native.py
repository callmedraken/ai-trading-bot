"""FR3A fake kernel only; never load a native DLL or access production paths."""

import ast
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_bot.runtime import personal_desktop_paper_account_recovery_native as native
from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime.windows_authority import WindowsAuthorityError

from .test_personal_desktop_paper_account_publication import (
    prohibit_production_effects as prohibit_production_effects,
)


def forbidden(*args, **kwargs):
    raise AssertionError("real native boundary reached")


@pytest.fixture(autouse=True)
def block_real_native(monkeypatch, prohibit_production_effects):
    monkeypatch.setattr(native.ctypes, "WinDLL", forbidden, raising=False)
    monkeypatch.setattr(native, "require_windows_platform", forbidden)


@pytest.fixture
def kernel(monkeypatch):
    state = SimpleNamespace(calls=[], result=1, error=None, loads=0)

    class Move:
        def __call__(self, *args):
            state.calls.append(args)
            if state.error:
                raise state.error
            return state.result

    state.move = Move()

    def load(*args, **kwargs):
        state.loads += 1
        assert args == ("kernel32",)
        assert kwargs == {"use_last_error": True}
        return SimpleNamespace(MoveFileExW=state.move)

    monkeypatch.setattr(native.ctypes, "WinDLL", load)
    monkeypatch.setattr(native, "require_windows_platform", lambda: None)
    return state


@pytest.mark.parametrize("value", [False, 0, 1, None, "True"])
def test_constructor_gate_before_platform_or_dll(monkeypatch, value):
    monkeypatch.setattr(
        security, "PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED", value
    )
    with pytest.raises(WindowsAuthorityError, match="disabled"):
        native.WindowsPaperRecoveryFinalizeApi()


@pytest.mark.parametrize("value", [True, 0, 1, None, "False"])
def test_constructor_requires_original_publisher_disarmed(kernel, monkeypatch, value):
    with monkeypatch.context() as patch:
        patch.setattr(
            security, "PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED", True
        )
        patch.setattr(
            security, "PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED", value
        )
        with pytest.raises(WindowsAuthorityError, match="disarmed"):
            native.WindowsPaperRecoveryFinalizeApi()
    assert kernel.loads == 0


@pytest.mark.parametrize("outcome", ["success", "failure", "response-loss"])
def test_exact_native_call_and_consumed_attempt(kernel, monkeypatch, outcome):
    with monkeypatch.context() as patch:
        patch.setattr(
            security, "PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED", True
        )
        api = native.WindowsPaperRecoveryFinalizeApi()
        if outcome == "failure":
            kernel.result = 0
        elif outcome == "response-loss":
            kernel.error = OSError("lost response")
        if outcome == "success":
            api.rename_no_clobber()
        else:
            with pytest.raises((WindowsAuthorityError, OSError)):
                api.rename_no_clobber()
        assert api._attempted is True
        with pytest.raises(WindowsAuthorityError, match="consumed"):
            api.rename_no_clobber()
    assert kernel.calls == [
        (r"F:\AITradingBot\.Paper-v2.provisioning", r"F:\AITradingBot\Paper-v2", 0x8)
    ]
    assert kernel.move.argtypes == [
        native.ctypes.c_wchar_p,
        native.ctypes.c_wchar_p,
        native.ctypes.c_uint32,
    ]
    assert kernel.move.restype is native.ctypes.c_int32
    assert {name for name in dir(api) if not name.startswith("_")} == {
        "rename_no_clobber"
    }
    assert not inspect.signature(native.WindowsPaperRecoveryFinalizeApi).parameters
    assert not inspect.signature(api.rename_no_clobber).parameters
    with pytest.raises(TypeError):
        api.rename_no_clobber("alternate", "destination")


@pytest.mark.parametrize(
    "gate,value",
    [
        ("RECOVERY", False),
        ("RECOVERY", 1),
        ("RECOVERY", None),
        ("PRODUCTION", True),
        ("PRODUCTION", 0),
        ("PRODUCTION", None),
    ],
)
def test_method_independently_rechecks_both_gates(kernel, monkeypatch, gate, value):
    with monkeypatch.context() as patch:
        patch.setattr(
            security, "PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED", True
        )
        api = native.WindowsPaperRecoveryFinalizeApi()
        patch.setattr(
            security, f"PERSONAL_DESKTOP_PAPER_V2_{gate}_EFFECTS_ENABLED", value
        )
        with pytest.raises(WindowsAuthorityError):
            api.rename_no_clobber()
    assert kernel.calls == []
    assert api._attempted is False


def test_attempt_consumed_before_native_invocation(kernel, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(
            security, "PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED", True
        )
        api = native.WindowsPaperRecoveryFinalizeApi()

        class ObserveMove:
            def __call__(self, *args):
                assert api._attempted is True
                with pytest.raises(WindowsAuthorityError, match="consumed"):
                    api.rename_no_clobber()
                return 1

        api._kernel = SimpleNamespace(MoveFileExW=ObserveMove())
        api.rename_no_clobber()


def test_source_gates_have_single_certified_literal_assignment():
    tree = ast.parse(Path(security.__file__).read_text())
    for name, expected in (
        ("PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED", True),
        ("PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED", False),
    ):
        assignments = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == name
                for target in node.targets
            )
        ]
        assert len(assignments) == 1
        assert isinstance(assignments[0].value, ast.Constant)
        assert assignments[0].value.value is expected
    assert security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED is True
    assert security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is False
