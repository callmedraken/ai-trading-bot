import importlib


def test_thin_guarded_capture_readiness_script_imports_without_running() -> None:
    module = importlib.import_module("scripts.evaluate_guarded_capture_readiness")

    assert callable(module.main)
