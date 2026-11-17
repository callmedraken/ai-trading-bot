import importlib
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from scripts.run_live_prototype import main, prepare_state_root


def test_help_does_not_construct_gui_or_state(capsys):
    with pytest.raises(SystemExit) as result:
        main(["--help"])
    assert result.value.code == 0
    help_text = capsys.readouterr().out
    assert "--synthetic" in help_text
    assert "--restricted-live" in help_text
    with pytest.raises(SystemExit):
        main(["--live"])


def test_launcher_import_and_help_do_not_compose_runtime(monkeypatch, capsys):
    import scripts.run_live_prototype as launcher

    from trading_bot.live_prototype import l43_runtime

    calls = []

    def build(_repo_root):
        calls.append("built")
        raise AssertionError("help must not compose the production runtime")

    monkeypatch.setattr(l43_runtime, "build_production_l43_runtime", build)
    importlib.reload(launcher)
    with pytest.raises(SystemExit) as result:
        launcher.main(["--help"])

    assert result.value.code == 0
    assert calls == []
    assert "--restricted-live" in capsys.readouterr().out


def test_restricted_live_routes_to_canonical_application_without_cli_state(
    monkeypatch,
):
    from trading_bot.live_prototype import application

    captured = []

    def run_application(arguments):
        captured.extend(arguments)
        return 17

    monkeypatch.setattr(application, "main", run_application)

    assert main(["--restricted-live"]) == 17
    assert captured == ["--mode", "RESTRICTED_LIVE"]


def test_restricted_live_rejects_cli_state_and_modes_are_exclusive():
    with pytest.raises(SystemExit):
        main(["--restricted-live", "--state-root", "F:\\AI\\temp\\state"])
    with pytest.raises(SystemExit):
        main(["--restricted-live", "--synthetic"])


def test_fresh_synthetic_state_only_and_no_reuse_or_source_write(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    state = tmp_path / "isolated"
    prepare_state_root(state, source, allowed_temp_root=tmp_path)
    assert (state / "synthetic-workspace.json").read_text().find("SYNTHETIC") >= 0
    with pytest.raises(ValueError):
        prepare_state_root(state, source, allowed_temp_root=tmp_path)
    with pytest.raises(ValueError):
        prepare_state_root(source / "child", source, allowed_temp_root=tmp_path)
    with pytest.raises(ValueError):
        prepare_state_root(Path("relative"), source, allowed_temp_root=tmp_path)


def test_actual_five_page_composition_and_close_during_work():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QListWidget

    from trading_bot.live_prototype.contracts import Command, Lifecycle
    from trading_bot.live_prototype.synthetic_service import SyntheticApplicationService
    from trading_bot.live_prototype.window import PrototypeWindow

    app = QApplication.instance() or QApplication([])
    service = SyntheticApplicationService()
    window = PrototypeWindow(service)
    window.show()
    navigation = window.findChild(QListWidget, "prototypeNavigation")
    assert navigation.count() == 5
    for index in range(5):
        navigation.setCurrentRow(index)
        app.processEvents()
    service.submit(Command.START)
    window.close()
    from time import monotonic

    deadline = monotonic() + 3
    while window.isVisible() and monotonic() < deadline:
        app.processEvents()
        window._refresh()
    assert not window.isVisible()
    assert service.shutdown_complete()
    assert service.snapshot().lifecycle is Lifecycle.STOPPED
    assert not service.snapshot().ready_to_trade
