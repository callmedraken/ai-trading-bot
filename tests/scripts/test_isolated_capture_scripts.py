import importlib


def test_isolated_capture_scripts_import_without_running() -> None:
    child = importlib.import_module("scripts.run_isolated_capture_child")
    launcher = importlib.import_module("scripts.launch_isolated_capture_child")

    assert callable(child.main)
    assert callable(launcher.main)
