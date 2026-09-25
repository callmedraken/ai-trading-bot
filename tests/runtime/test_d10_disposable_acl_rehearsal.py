"""Pure tests for the opt-in disposable ACL rehearsal boundary."""

from __future__ import annotations

import importlib

import pytest
from scripts.d10_protected_deployment import DeploymentBlocked

from scripts import d10_disposable_acl_rehearsal as rehearsal
from scripts import d10_protected_deployment_windows as windows


def test_rehearsal_import_is_inert(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden_init(self: object) -> None:
        raise AssertionError("native backend constructed during import")

    monkeypatch.setattr(windows.WindowsDeploymentBackend, "__init__", forbidden_init)
    importlib.reload(rehearsal)


def test_disposable_path_restriction() -> None:
    accepted = r"F:\AI\temp\p124-acl-rehearsal-sourceonly01"
    assert rehearsal.require_disposable_root(accepted) == accepted
    for path in (
        r"F:\AITradingBot\D10",
        r"F:\AI\temp\..\AITradingBot\D10",
        r"F:\AI\temp\other",
        r"F:\AI\temp\p124-acl-rehearsal-a\child",
        r"C:\AI\temp\p124-acl-rehearsal-sourceonly01",
    ):
        with pytest.raises(DeploymentBlocked, match="path_unreviewed"):
            rehearsal.require_disposable_root(path)


def test_disposable_backend_allows_only_its_fixed_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(windows.WindowsDeploymentBackend, "__init__", lambda self: None)
    backend = rehearsal._DisposableBackend(
        r"F:\AI\temp\p124-acl-rehearsal-sourceonly01"
    )
    assert backend._allowed_directory_create(backend.root)
    assert backend._allowed_directory_create(backend.installing_dir)
    assert backend._allowed_file_create(backend.installing_file)
    assert backend._allowed_object_path(backend.final_dir, directory=True)
    assert backend._allowed_object_path(backend.final_file, directory=False)
    assert not backend._allowed_directory_create(r"F:\AITradingBot\D10")
    assert not backend._allowed_file_create(r"F:\AITradingBot\D10\launch-guard.py")
    assert not backend._allowed_object_path(r"F:\AITradingBot\D10", directory=True)
    with pytest.raises(DeploymentBlocked, match="absence_path_unreviewed"):
        backend._open_absence(r"F:\AITradingBot\D10")
    with pytest.raises(DeploymentBlocked, match="rename_unreviewed"):
        backend.publish_create_only(backend.installing_file, r"F:\AITradingBot\D10")
