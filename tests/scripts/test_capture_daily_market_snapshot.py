import importlib


def test_thin_capture_script_imports_without_running() -> None:
    module = importlib.import_module("scripts.capture_daily_market_snapshot")

    assert callable(module.main)
